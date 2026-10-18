"""NPP/CEA daily generation report scraper (publishedReports).

Parses dgr2 ("Region wise, State wise, Station wise Operation Performance")
— the all-India per-station daily feed with: monitored capacity, today's
generation program/actual (MU), year-to-date program/actual, COAL STOCK IN
DAYS for thermal stations, capacity under outage with outage dates and
remarks. This is the closest public thing to end-to-end supply-chain
monitoring: one row per power station, all India, daily.

URL pattern: https://npp.gov.in/public-reports/cea/daily/dgr/DD-MM-YYYY/dgr2-YYYY-MM-DD.xls
"""
import argparse
import re
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

import requests
import xlrd

from store import connect, log

DGR2 = "https://npp.gov.in/public-reports/cea/daily/dgr/{d}/{f}"
REGIONS = {"NORTHERN", "WESTERN", "SOUTHERN", "EASTERN", "NORTH-EASTERN", "ISGS"}


def _f(v):
    try:
        s = str(v).replace(",", "").strip()
        return float(s) if s not in ("", "*") else None
    except (TypeError, ValueError):
        return None


def parse(xls_path):
    sh = xlrd.open_workbook(xls_path).sheet_by_index(0)
    # report date from the title row ("... GENERATION REPORT FOR 16/09/2026")
    title = " ".join(str(sh.cell_value(r, c)) for r in range(4) for c in range(sh.ncols))
    m = re.search(r"(\d{2}/\d{2}/\d{4})", title)
    day = None
    if m:
        day = datetime.strptime(m.group(1), "%d/%m/%Y").date().isoformat()
    region = state = sector = ptype = None
    rows = []
    for r in range(5, sh.nrows):
        vals = sh.row_values(r)
        name = str(vals[0]).strip()
        cap = _f(vals[7])
        if not name:
            continue
        if name in REGIONS and cap is None:
            region, state = name.title(), None
            continue
        if name.upper().startswith("SECTOR:"):
            sector = str(vals[4]).strip() if len(vals) > 4 else None
            continue
        if name.upper().startswith("TYPE:"):
            ptype = str(vals[4]).strip() if len(vals) > 4 else None
            continue
        if name.upper().startswith("REGION TOTAL"):
            rows.append(dict(region=region, state=None, sector=None, type=None,
                             station="__REGION_TOTAL__", cap_mw=cap,
                             gen_prog_mu=_f(vals[8]), gen_actual_mu=_f(vals[9]),
                             ytd_prog_mu=_f(vals[10]), ytd_actual_mu=_f(vals[11]),
                             coal_stock_days=None, outage_mw=_f(vals[13]),
                             remarks=""))
            continue
        if name.upper().startswith("STATE TOTAL"):
            state = state  # totals attach to current state
            rows.append(dict(region=region, state=state, sector=None, type=None,
                             station="__STATE_TOTAL__", cap_mw=cap,
                             gen_prog_mu=_f(vals[8]), gen_actual_mu=_f(vals[9]),
                             ytd_prog_mu=_f(vals[10]), ytd_actual_mu=_f(vals[11]),
                             coal_stock_days=None, outage_mw=_f(vals[13]),
                             remarks=""))
            continue
        if cap is None:
            # state header rows have a name but no capacity
            if not any(_f(v) is not None for v in vals[7:14]):
                state = name.title()
                sector = ptype = None
            continue
        if name == "Unit":
            continue  # unit-level rows — skip, keep station rollups
        rows.append(dict(region=region, state=state, sector=sector, type=ptype,
                         station=name, cap_mw=cap,
                         gen_prog_mu=_f(vals[8]), gen_actual_mu=_f(vals[9]),
                         ytd_prog_mu=_f(vals[10]), ytd_actual_mu=_f(vals[11]),
                         coal_stock_days=_f(vals[12]), outage_mw=_f(vals[13]),
                         remarks=str(vals[17] or "").strip()))
    return day, rows


def save(day, rows):
    con = connect()
    with con:
        con.executescript("""
        CREATE TABLE IF NOT EXISTS dgr_stations (
            date TEXT NOT NULL, region TEXT, state TEXT,
            station TEXT NOT NULL, cap_mw REAL, gen_prog_mu REAL,
            gen_actual_mu REAL, ytd_prog_mu REAL, ytd_actual_mu REAL,
            coal_stock_days REAL, outage_mw REAL, remarks TEXT,
            sector TEXT DEFAULT '', type TEXT DEFAULT '',
            PRIMARY KEY (date, station, sector, type));
        """)
        con.executemany(
            """INSERT OR REPLACE INTO dgr_stations
            (date, region, state, sector, type, station, cap_mw, gen_prog_mu,
             gen_actual_mu, ytd_prog_mu, ytd_actual_mu, coal_stock_days,
             outage_mw, remarks)
            VALUES (:date,:region,:state,:sector,:type,:station,:cap_mw,
             :gen_prog_mu,:gen_actual_mu,:ytd_prog_mu,:ytd_actual_mu,
             :coal_stock_days,:outage_mw,:remarks)""",
            [dict(r, date=day) for r in rows])
    con.close()


def fetch(day):
    url = DGR2.format(d=day.strftime("%d-%m-%Y"),
                      f=f"dgr2-{day:%Y-%m-%d}.xls")
    r = requests.get(url, timeout=90, verify=False,
                     headers={"User-Agent": "Mozilla/5.0"})
    r.raise_for_status()
    p = Path("data/downloads") / f"dgr2-{day:%Y-%m-%d}.xls"
    p.write_bytes(r.content)
    return p


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--file")
    ap.add_argument("--days-back", type=int, default=1,
                    help="report is published next day; 1 = yesterday")
    args = ap.parse_args()
    if args.file:
        path = Path(args.file)
        day, rows = parse(path)
    else:
        day = date.today() - timedelta(days=args.days_back)
        try:
            path = fetch(day)
        except Exception as e:
            # reports lag; retry the day before
            day = day - timedelta(days=1)
            try:
                path = fetch(day)
            except Exception as e2:
                log("npp_dgr", "fail", str(e2))
                sys.exit(1)
        day, rows = parse(path)
    save(day, rows)
    tn = sum(1 for r in rows if (r["state"] or "").upper() == "TAMILNADU"
             or "TAMIL" in (r["state"] or "").upper())
    msg = f"{day}: {len(rows)} station rows ({tn} TN)"
    print(msg)
    log("npp_dgr", "ok", msg)


if __name__ == "__main__":
    main()
