"""India's coal supply chain upstream of the power stations: one table, many sources.

Table coal_supply (series, period, value, unit, source): period is 'YYYY-MM-DD' for daily figures and
'YYYY-MM' for monthly ones. Series names are '<measure>:<entity>', e.g.
  prod_d:CIL        production on the day, '000 t          (CIL "MOC Dashboard", Oracle APEX app 119)
  prod_mtd:MCL      month to date, Mt
  prod_ytd:Captive  financial year to date, Mt
  offtake_d:SECL    dispatch (offtake) on the day, '000 t
Other modules (coal_msg, cea_monthly, ports_coal, tradestat, coal_rakes) write their own series through put().

    python -m scrapers.coal_supply                 # yesterday and the day before (collect.py, hourly)
    python -m scrapers.coal_supply --back 1100     # backfill daily CIL figures (to Oct 2023), skipping stored days
"""
import html as htmllib
import re
import sys
import time
from datetime import date, timedelta

import requests
import urllib3

from store import connect, log

urllib3.disable_warnings()
UA = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36 (reclaimchennai power map)"}
APEX = "https://apps.coalindia.in/ords/safety/r/coyla/{page}?p0_report_date={d:%d-%m-%Y}"
SCHEMA = """
CREATE TABLE IF NOT EXISTS coal_supply (
    series TEXT NOT NULL, period TEXT NOT NULL, value REAL, unit TEXT, source TEXT,
    PRIMARY KEY (series, period)
);
"""
COMPANY = {"Singareni": "SCCL", "SCCL": "SCCL", "Captive": "Captive", "Commercial": "Commercial", "CIL": "CIL",
           "BCCL": "BCCL", "CCL": "CCL", "ECL": "ECL", "MCL": "MCL", "NCL": "NCL", "SECL": "SECL", "WCL": "WCL", "NEC": "NEC"}


def put(rows):
    """rows: iterable of (series, period, value, unit, source)."""
    con = connect()
    con.executescript(SCHEMA)
    with con:
        con.executemany("INSERT OR REPLACE INTO coal_supply VALUES (?,?,?,?,?)", list(rows))
    con.close()


def have(series, period):
    con = connect()
    con.executescript(SCHEMA)
    try:
        return con.execute("SELECT 1 FROM coal_supply WHERE series=? AND period=?", (series, period)).fetchone() is not None
    finally:
        con.close()


def num(v):
    try:
        return float(str(v).replace(",", "").strip())
    except ValueError:
        return None


def tables(page):
    out = []
    for t in re.findall(r"<table.*?</table>", page, re.S):
        rows = []
        for r in re.findall(r"<tr.*?</tr>", t, re.S):
            cells = [htmllib.unescape(re.sub(r"<[^>]+>", "", c)).strip() for c in re.findall(r"<t[dh][^>]*>(.*?)</t[dh]>", r, re.S)]
            if any(cells):
                rows.append(cells)
        if rows:
            out.append(rows)
    return out


def apex_day(d, kind):
    """kind 'prod' or 'offtake': the on-day, month-to-date and year-to-date tables for every company."""
    page = requests.get(APEX.format(page="company-coal-production" if kind == "prod" else "company-coal-offtake", d=d), headers=UA, timeout=90).text
    src = "CIL MOC Dashboard (apps.coalindia.in)"
    rows = []
    for t in tables(page):
        head = " ".join(t[0]).lower()
        col = None
        if "ondt actual" in head:
            col, key, unit = next(i for i, c in enumerate(t[0]) if "OnDt Actual" in c), f"{kind}_d", "kt"
        elif "mtd actual" in head and "month target" in head:
            col, key, unit = next(i for i, c in enumerate(t[0]) if c.startswith("MTD Actual")), f"{kind}_mtd", "Mt"
        elif "ytd actual" in head and "year target" in head:
            col, key, unit = next(i for i, c in enumerate(t[0]) if c.startswith("YTD Actual")), f"{kind}_ytd", "Mt"
        if col is None:
            continue
        for r in t[1:]:
            co = COMPANY.get(r[0].strip())
            if not co or col >= len(r):
                continue
            v = num(r[col])
            if v is None:
                continue
            if key.endswith("_d") and co in ("Captive", "Commercial"):
                continue          # captive / commercial on-day cells are monthly CCO figures, not daily
            rows.append((f"{key}:{co}", d.isoformat(), v, unit, src))
    return rows


NCP_ROW = {"CIL": "CIL", "Singareni": "SCCL", "Captive & Others *": "Captive", "Commercial": "Commercial", "Total(Coal)": "Total",
           "NLCIL": "NLCIL", "Total(Lig)": "Total"}


def ncp_snapshot():
    """National Coal Portal (CMPDI): all-India production and offtake on the latest day and for the year so far,
    including captive and commercial mines (which the CIL dashboard only has monthly). Latest day only: snapshot it."""
    page = requests.get("https://coaldashboard.cmpdi.co.in/dashboard.php", headers=UA, timeout=60, verify=False).text
    src = "National Coal Portal (coaldashboard.cmpdi.co.in)"
    rows = []
    for block, kind in (("prod", "prod"), ("offtk", "offtake")):
        m = re.search(r'id="%s"><table.*?</table>' % block, page, re.S)
        if not m:
            continue
        fuel, last_day = "coal", None
        for r in tables(m.group(0))[0][1:]:
            label = re.sub(r"\s+", " ", r[0]).strip()
            ent = next((v for k, v in NCP_ROW.items() if k.replace(" ", "").lower() == label.replace(" ", "").lower()), None)
            if not ent:
                continue
            if label == "NLCIL":
                fuel = "lig"
            if r[1]:
                dd, mm, yy = r[1].split("-")
                last_day = f"20{yy}-{mm}-{dd}"
            day = last_day
            pre = f"ncp_{kind}" if fuel == "coal" else f"ncp_lig_{kind}"
            if num(r[2]) is not None and day:
                rows.append((f"{pre}_d:{ent}", day, num(r[2]), "Mt", src))
            if num(r[3]) is not None and day:
                rows.append((f"{pre}_ytd:{ent}", day, num(r[3]), "Mt", src))
            if label.startswith("Total"):
                fuel = "lig" if fuel == "coal" else fuel
    put(rows)
    return len(rows)


def npp_stock_buckets():
    """NPP gc-map dashboard: how many stations hold 0-5, 5-15, 15-25 and 25+ days of coal (N non-pithead, P pithead)."""
    from datetime import datetime, timezone
    r = requests.get("https://npp.gov.in/dashBoard/getAllZoneGen?ID=IND", headers={**UA, "Referer": "https://npp.gov.in/dashBoard/gc-map-dashboard",
                     "X-Requested-With": "XMLHttpRequest"}, timeout=60, verify=False)
    rows = []
    for b in r.json().get("dailyColeStock") or []:
        day = (datetime.fromtimestamp(b["coal_date"] / 1000, timezone.utc) + timedelta(hours=5, minutes=30)).date().isoformat()
        for k in ("coal_0_5", "coal_5_15", "coal_15_25", "coal_gt_25"):
            if b.get(k) is not None:
                rows.append((f"npp_days_bucket:{b['mode_transport']}_{k[5:]}", day, b[k], "stations", "National Power Portal dashboard"))
    put(rows)
    return len(rows)


def run(back=2, start=None):
    n, days = 0, 0
    d = date.today() - timedelta(days=1)
    stop = start or d - timedelta(days=back - 1)
    while d >= stop:
        if back > 3 and have("prod_d:CIL", d.isoformat()) and have("offtake_d:CIL", d.isoformat()):
            d -= timedelta(days=1)
            continue
        try:
            rows = apex_day(d, "prod") + apex_day(d, "offtake")
            put(rows)
            n += len(rows)
            days += 1
            if back > 3:
                print(d, len(rows), flush=True)
        except Exception as e:
            print(d, "error", e, flush=True)
        if back > 3:
            time.sleep(1.2)
        d -= timedelta(days=1)
    if back <= 3:
        for f in (ncp_snapshot, npp_stock_buckets):
            try:
                n += f()
            except Exception as e:
                print(f.__name__, "error", e)
    log("coal_supply", "ok", f"CIL APEX {days} days, {n} rows")
    return n


if __name__ == "__main__":
    back = int(sys.argv[sys.argv.index("--back") + 1]) if "--back" in sys.argv else 2
    print(run(back))
