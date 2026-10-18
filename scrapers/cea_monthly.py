"""CEA monthly fuel reports from the National Power Portal: coal receipts by source, consumption and closing stock
per thermal plant, and imported-coal receipts at power plants.

Source (CEA Fuel Management Division, JasperReports XLS; a PDF of each sits beside it):
  https://npp.gov.in/public-reports/cea/monthly/fuel/YYYY/MON/monthCoal1-YYYY-Mon.xls        from Apr 2023
  https://npp.gov.in/public-reports/cea/monthly/fuel/YYYY/MON/monthImportCoal1-YYYY-Mon.xls  from Jan 2024
(MON = AUG, Mon = Aug). Earlier months 404 under every filename variant tried. A month's report appears
around the 20th-25th of the following month.

Table coal_plants_monthly (month 'YYYY-MM', plant): region, capacity_mw, receipts by source ('000 t: CIL, SCCL,
captive, e-auction, import, others, total), consumption_kt, closing_stock_kt, straight from monthCoal1.
Apr-Dec 2023 reports also carry CIL/SCCL allocation, opening stock, receipt % of allocation and consumption split
domestic/imported (alloc_cil_sccl_kt, opening_stock_kt, rcpt_pct_alloc, consumption_domestic_kt/_import_kt);
those columns are NULL from Jan 2024. National series use CEA's "Total ALL INDIA" row.
Seven Adani plants renamed in Jul 2023 are stored under their current names (RENAMED).
The report itself carries only region; state and utility are filled from the latest matching row of
coal_plants_daily (same CEA plant names), NULL when the plant is not found there.
Table coal_import_power_monthly (month, category 'Blending'|'Design', entity): sector, capacity_mw,
receipt_kt, receipt_ytd_kt (FY to date), from monthImportCoal1 (blending entries are utilities or plants).

National series go to coal_supply (scrapers.coal_supply.put), Mt:
  cea_rcpt_m:Total|Domestic|Import|CIL|SCCL|Captive|E-Auction|Others   receipts at power plants in the month
  cea_cons_m:Total                                                    consumption in the month
  cea_stock_m:Total                                                   closing stock at month end
  import_power_m:Blending|Design|Total                                imported coal received by power plants
The "same month last year" columns extend cea_rcpt_m:Total/Domestic/Import and cea_cons_m:Total back to
Apr 2022 and import_power_m back to Jan 2023 (only for months that have no report of their own).

    python -m scrapers.cea_monthly               # latest 3 months, re-downloaded (collect.py)
    python -m scrapers.cea_monthly --backfill    # every month from Apr 2023, cached files reused
    python -m scrapers.cea_monthly --month 2026-08
Downloads are cached in raw/coal/cea_monthly/.
"""
import re
import sys
import time
from datetime import date
from pathlib import Path

import requests
import urllib3
import xlrd

from scrapers.coal_supply import put
from store import connect, log

urllib3.disable_warnings()
UA = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36 (reclaimchennai power map)"}
URL = "https://npp.gov.in/public-reports/cea/monthly/fuel/{y}/{MON}/{name}-{y}-{Mon}.xls"
RAW = Path(__file__).resolve().parent.parent / "raw" / "coal" / "cea_monthly"
MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
FIRST_COAL, FIRST_IMPORT = "2023-04", "2024-01"
SCHEMA = """
CREATE TABLE IF NOT EXISTS coal_plants_monthly (
    month TEXT NOT NULL, plant TEXT NOT NULL,
    region TEXT, state TEXT, utility TEXT, capacity_mw REAL,
    alloc_cil_sccl_kt REAL, opening_stock_kt REAL,                   -- 2023 layout only
    rcpt_cil_kt REAL, rcpt_sccl_kt REAL, rcpt_captive_kt REAL, rcpt_eauction_kt REAL,
    rcpt_import_kt REAL, rcpt_other_kt REAL, rcpt_total_kt REAL,
    rcpt_pct_alloc REAL,                                              -- 2023 layout only: receipt % of CIL/SCCL allocation
    consumption_domestic_kt REAL, consumption_import_kt REAL,        -- 2023 layout only
    consumption_kt REAL, closing_stock_kt REAL,
    PRIMARY KEY (month, plant)
);
CREATE TABLE IF NOT EXISTS coal_import_power_monthly (
    month TEXT NOT NULL, category TEXT NOT NULL, entity TEXT NOT NULL,
    sector TEXT, capacity_mw REAL, receipt_kt REAL, receipt_ytd_kt REAL,
    PRIMARY KEY (month, category, entity)
);
"""
# receipt sub-header label -> column name / series entity
SOURCES = {"CIL": ("rcpt_cil_kt", "CIL"), "SCCL": ("rcpt_sccl_kt", "SCCL"), "CAPTIVE": ("rcpt_captive_kt", "Captive"),
           "E-AUCTION": ("rcpt_eauction_kt", "E-Auction"), "IMPORT": ("rcpt_import_kt", None),
           "OTHERS": ("rcpt_other_kt", "Others"), "TOTAL": ("rcpt_total_kt", None)}
COLS = ["capacity_mw", "alloc_cil_sccl_kt", "opening_stock_kt", "rcpt_cil_kt", "rcpt_sccl_kt", "rcpt_captive_kt",
        "rcpt_eauction_kt", "rcpt_import_kt", "rcpt_other_kt", "rcpt_total_kt", "rcpt_pct_alloc",
        "consumption_domestic_kt", "consumption_import_kt", "consumption_kt", "closing_stock_kt"]
# Adani plants renamed from Jul 2023 (same capacity, same slot): stored under the current name so series continue
RENAMED = {"KAWAI TPS": "ADANI POWER LIMITED KAWAI TPP", "MUNDRA TPS-I & II": "ADANI POWER LIMITED MUNDRA TPP - I & II",
           "MUNDRA TPS-III": "ADANI POWER LIMITED MUNDRA TPP - III", "AVANTHA BHANDAR": "ADANI POWER LIMITED RAIGARH TPP",
           "RAIKHEDA TPP": "ADANI POWER LIMITED RAIPUR TPP", "TIRORA TPS": "ADANI POWER LIMITED TIRODA TPP",
           "UDUPI TPP": "ADANI POWER LIMITED UDUPI TPP"}
SUMMABLE = [c for c in COLS if c.endswith("_kt")]


def _f(v):
    if isinstance(v, (int, float)):
        return float(v)
    s = str(v).replace(",", "").strip()
    try:
        return float(s)
    except ValueError:
        return None


def _txt(v):
    return re.sub(r"\s+", " ", str(v)).strip()


def _ym(month):
    y, m = map(int, month.split("-"))
    return y, m


def _shift(month, k):
    y, m = _ym(month)
    i = y * 12 + m - 1 + k
    return f"{i // 12:04d}-{i % 12 + 1:02d}"


def fetch(name, month, refresh=False):
    """Local path of the cached XLS, downloading it if needed; None when NPP has no such file (404)."""
    y, m = _ym(month)
    mon = MONTHS[m - 1]
    path = RAW / f"{name}-{y}-{mon}.xls"
    if path.exists() and path.stat().st_size and not refresh:
        return path
    r = requests.get(URL.format(y=y, MON=mon.upper(), Mon=mon, name=name), headers=UA, verify=False, timeout=90)
    time.sleep(1)
    if r.status_code == 404:
        return None
    r.raise_for_status()
    if not r.content.startswith(b"\xd0\xcf\x11\xe0"):
        raise ValueError(f"{name} {month}: not an XLS ({r.headers.get('content-type')})")
    RAW.mkdir(parents=True, exist_ok=True)
    path.write_bytes(r.content)
    return path


def _grid(path):
    sh = xlrd.open_workbook(str(path)).sheet_by_index(0)
    return [[_txt(v) if isinstance(v, str) else v for v in sh.row_values(r)] for r in range(sh.nrows)]


def parse_coal(path):
    """-> (report month, plant rows [dict], all-India dict, footer dict).

    footer: {domestic|imported|total|consumption: (same month last year, this month) in Mt,
             'regions': {region: its "Total of <region>" row}}."""
    g = _grid(path)
    month = None
    for row in g[:8]:
        mt = re.search(r"FOR\s+([A-Za-z]+)\s+(\d{4})", " ".join(map(str, row)))
        if mt:
            month = f"{mt.group(2)}-{MONTHS.index(mt.group(1)[:3].title()) + 1:02d}"
            break
    # header: "Name of TPS | Installed Capacity | RECEIPT ... | Total Consumption | Closing Stocks" with the
    # sources (CIL ... Total) on the next row. Up to Dec 2023 the report also has "Monthly Allocation from CIL/SCCL",
    # "Opening Stocks", "% Receipt w.r.t. Alloted Coal" and consumption split Domestic / Imported / Total.
    # Jasper's merged header cells do not sit over their data cells, so the field list is built from the label
    # order and matched to the columns that hold numbers in the body.
    h = next(i for i, row in enumerate(g) if str(row[0]).upper().startswith("NAME OF"))
    top = [str(v).upper().replace(" ", "") for v in g[h][1:] if str(v).strip()]
    subs = [str(v).upper().replace(" ", "") for v in g[h + 1] if str(v).strip()]
    fields = []
    for t in top:
        if "CAPACITY" in t:
            fields.append("capacity_mw")
        elif "ALLOCATION" in t:
            fields.append("alloc_cil_sccl_kt")
        elif "OPENING" in t:
            fields.append("opening_stock_kt")
        elif t == "RECEIPT":
            if subs[:len(SOURCES)] != list(SOURCES):
                raise ValueError(f"{path.name}: unexpected receipt sources {subs}")
            fields += [v[0] for v in SOURCES.values()]
            if any(l.startswith("%RECEIPT") for l in subs):
                fields.append("rcpt_pct_alloc")
        elif "CONSUMPTION" in t:
            if "DOMESTIC" in subs:
                fields += ["consumption_domestic_kt", "consumption_import_kt"]
            fields.append("consumption_kt")
        elif "CLOSING" in t:
            fields.append("closing_stock_kt")
        else:
            raise ValueError(f"{path.name}: unknown header {t!r}")
    stop = next((i for i, row in enumerate(g) if str(row[0]).upper().startswith("TOTAL ALL INDIA")), None)
    if stop is None:
        raise ValueError(f"{path.name}: no 'Total ALL INDIA' row")
    numcols = sorted({c for row in g[h + 2:stop + 1] for c, v in enumerate(row[1:], 1) if isinstance(v, float)})
    if len(numcols) != len(fields) or "rcpt_total_kt" not in fields or "closing_stock_kt" not in fields:
        raise ValueError(f"{path.name}: {len(numcols)} numeric columns {numcols} for fields {fields}")
    col = dict(zip(fields, numcols))
    plants, india, region, regtot = [], None, None, {}
    r = h + 2
    while r < len(g):
        row = g[r]
        name = str(row[0]).strip()
        vals = {k: _f(row[c]) for k, c in col.items()}
        r += 1
        if not name or re.fullmatch(r"[\d.| ]+", name):          # column-number row
            continue
        if name.upper().startswith("TOTAL ALL INDIA"):
            india = vals
            break
        if name.upper().startswith("TOTAL OF"):
            regtot[region] = vals
            continue
        if all(v is None for v in vals.values()):
            region = name
            continue
        prev = plants[-1] if plants else None
        if (prev and prev["region"] == region and all(prev[k] == v for k, v in vals.items())
                and any(vals[k] for k in ("rcpt_total_kt", "consumption_kt", "closing_stock_kt"))):
            prev["plant"] += " " + name     # Jasper sometimes splits a long name over two rows, repeating the numbers
            continue
        plants.append(dict(plant=name, region=region, **vals))
    # footer: "RECEIPT | <MON- prev> | <MON- cur> | <cum prev> | <cum cur>" then Domestic / Imported / Total Receipt / Total Consumption
    foot = {"regions": regtot}
    for i in range(r, len(g)):
        row = g[i]
        lab = " ".join(str(v) for v in row).upper()
        nums = [v for v in (_f(x) for x in row[1:]) if v is not None]
        for key, pat in (("domestic", "DOMESTIC"), ("imported", "IMPORTED"), ("total", "TOTAL RECEIPT"),
                         ("consumption", "TOTAL CONSUMPTION")):
            if pat in lab and len(nums) >= 2:
                foot[key] = (nums[0], nums[1])
    for p in plants:
        p["plant"] = RENAMED.get(p["plant"], p["plant"])
    return month, plants, india, foot


def parse_import(path):
    """-> (month, entity rows [dict], totals {'Blending'|'Design'|'Total': (cur, ytd, prev_month, prev_ytd)})."""
    g = _grid(path)
    month = None
    for row in g[:4]:
        mt = re.search(r"([A-Za-z]{3})[A-Za-z]*\s*-\s*(\d{4})", " ".join(map(str, row)))
        if mt and mt.group(1).title() in MONTHS:
            month = f"{mt.group(2)}-{MONTHS.index(mt.group(1).title()) + 1:02d}"
            break
    rows, tot, cat, sector = [], {}, None, None
    for row in g:
        a, b = str(row[0]).upper(), str(row[1]).strip()
        nums = [_f(v) for v in row[2:7]]
        lab = (a + " " + b.upper())
        if "IMPORTED COAL FOR BLENDING" in lab:
            key = "Blending"
        elif "DESIGNED ON IMPORTED COAL" in lab:
            key = "Design"
        elif "GRAND TOTAL" in lab:
            key = "Total"
        else:
            key = None
        if key and a.startswith(("TOTAL", "GRAND")):
            tot[key] = tuple(nums[1:5])
            continue
        if key:
            cat = key
            continue
        if a.endswith("SECTOR") and not a.startswith("TOTAL"):
            sector = a.replace("SECTOR", "").strip().title()
            continue
        if _f(row[0]) is not None and b and cat:
            rows.append(dict(category=cat, entity=b, sector=sector, capacity_mw=nums[0], receipt_kt=nums[1],
                             receipt_ytd_kt=nums[2]))
    return month, rows, tot


def _lookup(con):
    """plant name (upper, single-spaced) -> (state, utility) from the latest coal_plants_daily row."""
    out = {}
    try:
        for plant, state, util in con.execute(
                "SELECT plant, state, utility FROM coal_plants_daily ORDER BY date"):
            out[_txt(plant).upper()] = (state, util)
    except Exception:
        pass
    return out


def store_coal(month, plants, india, foot, con, look):
    """Write plant rows and national series for one monthCoal1 report; returns a check string."""
    mon = MONTHS[_ym(month)[1] - 1]
    src = f"CEA monthly coal report (NPP), {mon} {month[:4]}"
    seen = {}
    for p in plants:                                   # a plant listed twice in a month: keep the sum
        k = p["plant"]
        if k in seen:
            for c in SUMMABLE:
                if p.get(c) is not None:
                    seen[k][c] = (seen[k].get(c) or 0) + p[c]
        else:
            seen[k] = dict(p)
    with con:
        con.execute("DELETE FROM coal_plants_monthly WHERE month=?", (month,))
        con.executemany(
            f"INSERT INTO coal_plants_monthly (month, plant, region, state, utility, {', '.join(COLS)}) "
            f"VALUES ({', '.join('?' * (5 + len(COLS)))})",
            [(month, p["plant"], p["region"], *look.get(p["plant"].upper(), (None, None)), *[p.get(c) for c in COLS])
             for p in seen.values()])
    mt = lambda v: None if v is None else round(v / 1000, 4)
    rows = [(f"cea_rcpt_m:{ent}", month, mt(india[c]), "Mt", src) for c, ent in SOURCES.values() if ent]
    rows += [("cea_rcpt_m:Total", month, mt(india["rcpt_total_kt"]), "Mt", src),
             ("cea_rcpt_m:Import", month, mt(india["rcpt_import_kt"]), "Mt", src),
             ("cea_rcpt_m:Domestic", month, mt(india["rcpt_total_kt"] - india["rcpt_import_kt"]), "Mt", src),
             ("cea_cons_m:Total", month, mt(india["consumption_kt"]), "Mt", src),
             ("cea_stock_m:Total", month, mt(india["closing_stock_kt"]), "Mt", src)]
    prev = _shift(month, -12)
    if prev < FIRST_COAL and foot:                      # months before the archive: last-year column of this report
        psrc = f"CEA monthly coal report (NPP), {mon} {month[:4]} (same month last year)"
        for key, ser in (("domestic", "cea_rcpt_m:Domestic"), ("imported", "cea_rcpt_m:Import"),
                         ("total", "cea_rcpt_m:Total"), ("consumption", "cea_cons_m:Total")):
            if key in foot:
                rows.append((ser, prev, round(foot[key][0], 4), "Mt", psrc))
    put(rows)
    # consistency (CEA's own totals are what the series use): plants vs their region's total row, region totals
    # vs the All-India row, and the footer summary vs the All-India row
    bad = []
    for reg, t in foot.get("regions", {}).items():
        for c in ("rcpt_total_kt", "consumption_kt", "closing_stock_kt"):
            s = sum(p[c] or 0 for p in plants if p["region"] == reg)
            if t.get(c) is not None and abs(s - t[c]) > 1:
                bad.append(f"{reg} plants {c[:-3]} {s:.0f} vs region total {t[c]:.0f}")
    for c in ("rcpt_total_kt", "consumption_kt"):
        s = sum(t[c] or 0 for t in foot.get("regions", {}).values())
        if abs(s - india[c]) > 1:
            bad.append(f"region totals {c[:-3]} {s:.0f} vs all-India {india[c]:.0f}")
    # (up to Mar 2024 the footer's this-month column is a slightly earlier cut, and in 2023 its "Imported" figure is
    # imported coal *consumed*; the same-month-last-year column matches the later reports, so only gross gaps count)
    for key, c in (("total", "rcpt_total_kt"), ("consumption", "consumption_kt")):
        if key in foot and abs(foot[key][1] * 1000 - india[c]) > 100:
            bad.append(f"footer {key} {foot[key][1]:.3f} Mt vs all-India row {india[c] / 1000:.3f}")
    if len(seen) != len(plants):
        bad.append(f"{len(plants) - len(seen)} duplicate plant names summed")
    return "; ".join(bad)


def store_import(month, rows, tot, con):
    mon = MONTHS[_ym(month)[1] - 1]
    src = f"CEA monthly import coal report (NPP), {mon} {month[:4]}"
    with con:
        con.execute("DELETE FROM coal_import_power_monthly WHERE month=?", (month,))
        con.executemany("INSERT OR REPLACE INTO coal_import_power_monthly VALUES (?,?,?,?,?,?,?)",
                        [(month, r["category"], r["entity"], r["sector"], r["capacity_mw"], r["receipt_kt"],
                          r["receipt_ytd_kt"]) for r in rows])
    out = [(f"import_power_m:{k}", month, round(v[0] / 1000, 4), "Mt", src) for k, v in tot.items() if v[0] is not None]
    prev = _shift(month, -12)
    if prev < FIRST_IMPORT:
        psrc = f"CEA monthly import coal report (NPP), {mon} {month[:4]} (same month last year)"
        out += [(f"import_power_m:{k}", prev, round(v[2] / 1000, 4), "Mt", psrc) for k, v in tot.items() if v[2] is not None]
    put(out)
    bad = []
    for k in ("Blending", "Design"):
        s = sum(r["receipt_kt"] or 0 for r in rows if r["category"] == k)
        if k in tot and abs(s - tot[k][0]) > 1:
            bad.append(f"{k} entity sum {s:.1f} vs total {tot[k][0]:.1f}")
    if {"Blending", "Design", "Total"} <= tot.keys() and abs(tot["Blending"][0] + tot["Design"][0] - tot["Total"][0]) > 1:
        bad.append("blending+design != total")
    return "; ".join(bad)


def do_month(month, con, look, refresh=False):
    """Fetch, parse and store both reports for one month -> (status dict)."""
    st = {}
    for name in ("monthCoal1", "monthImportCoal1"):
        if name == "monthImportCoal1" and month < FIRST_IMPORT:
            continue
        try:
            path = fetch(name, month, refresh)
            if path is None:
                st[name] = "missing"
                continue
            if name == "monthCoal1":
                m, plants, india, foot = parse_coal(path)
                if m != month:
                    raise ValueError(f"file says {m}")
                warn = store_coal(month, plants, india, foot, con, look)
                st[name] = f"{len(plants)} plants, rcpt {india['rcpt_total_kt'] / 1000:.2f} Mt" + (f" [{warn}]" if warn else "")
            else:
                m, rows, tot = parse_import(path)
                if m != month:
                    raise ValueError(f"file says {m}")
                warn = store_import(month, rows, tot, con)
                st[name] = f"{len(rows)} entities, total {tot.get('Total', (0,))[0] / 1000:.3f} Mt" + (f" [{warn}]" if warn else "")
        except Exception as e:
            st[name] = f"error {type(e).__name__}: {e}"
    return st


def months_back(n, end=None):
    end = end or _shift(date.today().strftime("%Y-%m"), -1)
    return [_shift(end, -k) for k in range(n)]


def run(months=None, refresh=True, verbose=False):
    con = connect()
    con.executescript(SCHEMA)
    look = _lookup(con)
    months = months or months_back(3)
    got, failed, warned = 0, [], []
    for mo in months:
        st = do_month(mo, con, look, refresh)
        if verbose:
            print(mo, st, flush=True)
        if "plants" in st.get("monthCoal1", ""):
            got += 1
        for k, v in st.items():
            if v.startswith("error") or (v == "missing" and mo < months_back(1)[0]):
                failed.append(f"{mo} {k}: {v}")
            elif "[" in v:
                warned.append(f"{mo} {k}: {v[v.index('[') + 1:-1]}")
    con.close()
    log("cea_monthly", "ok" if not failed else "partial",
        f"{got}/{len(months)} months {min(months)}..{max(months)}, {len(warned)} total mismatches"
        + (f"; failed: {' | '.join(failed)}" if failed else ""))
    return got, failed, warned


if __name__ == "__main__":
    if "--backfill" in sys.argv:
        end = months_back(1)[0]
        n = (_ym(end)[0] - 2023) * 12 + _ym(end)[1] - 4 + 1
        res = run(sorted(months_back(n, end)), refresh=False, verbose=True)
    elif "--month" in sys.argv:
        res = run([sys.argv[sys.argv.index("--month") + 1]], refresh=True, verbose=True)
    else:
        res = run(verbose=True)
    got, failed, warned = res
    print(f"{got} monthly coal reports stored; {len(failed)} failed; {len(warned)} with CEA total mismatches")
    for line in failed + warned:
        print("  " + line)
