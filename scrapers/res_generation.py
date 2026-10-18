"""CEA Daily Renewable Generation Report scraper.

The report (formerly served from npp.gov.in MERIT dashboards, today from the
CEA Renewable Project Monitoring Division) contains:
  * page with "(All India)": state-wise daily + month-cumulative generation
    in MU for Wind / Solar / Others RES / Total.
  * pages with "(ISGS)" and "(State Control Area)": station-level rows
    (station, state, sector, owner, type, operational capacity MW, actual
    generation MU today and cumulative for the month) — this is the closest
    public per-station live generation feed for wind and solar farms.

Usage:
    python -m scrapers.res_generation --file data/downloads/Report-2026-09-15.pdf
"""
import argparse
import re
import sys
from datetime import datetime
from pathlib import Path

import pdfplumber
import requests

from store import connect, log

DATE_RE = re.compile(r"(\d{2}-\w+-(?:\d{2}|\d{4}))")
MONTHS = dict(JAN=1, FEB=2, MAR=3, APR=4, MAY=5, JUN=6, JUL=7, AUG=8,
              SEP=9, OCT=10, NOV=11, DEC=12)


def _f(v):
    if v is None:
        return None
    v = str(v).replace(",", "").strip()
    try:
        return float(v)
    except ValueError:
        return None


def parse_date(text):
    m = DATE_RE.search(text)
    if not m:
        return None
    d, mon, y = m.group(1).split("-")
    return datetime(int("20" + y if len(y) == 2 else y), MONTHS[mon[:3].upper()], int(d)).date().isoformat()


def parse_state_rows(path):
    """Daily + cumulative state-wise RES generation (MU)."""
    out, date = [], None
    with pdfplumber.open(path) as pdf:
        for page in pdf.pages:
            head = page.extract_text() or ""
            if "(All India" not in head:
                continue
            date = date or parse_date(head)
            for table in page.extract_tables():
                for row in table:
                    row = [(c or "").replace("\n", " ").strip() for c in row]
                    if len(row) < 9 or "/" not in row[0]:
                        continue
                    state = row[0].split("/")[-1].strip()
                    if state in ("Region",) or not _f(row[1]):
                        continue
                    out.append(dict(state=state, metric="energy_mu",
                                    wind=_f(row[1]), solar=_f(row[2]),
                                    res_other=_f(row[3]), res_total=_f(row[4])))
                    out.append(dict(state=state, metric="energy_mu_mtd",
                                    wind=_f(row[5]), solar=_f(row[6]),
                                    res_other=_f(row[7]), res_total=_f(row[8])))
    return date, out


def parse_station_rows(path):
    """Station-level daily + cumulative generation (MU)."""
    out, date = [], None
    with pdfplumber.open(path) as pdf:
        for page in pdf.pages:
            head = page.extract_text() or ""
            if "Report (ISGS" not in head and "State Control Area" not in head:
                continue
            date = date or parse_date(head)
            for table in page.extract_tables():
                for row in table:
                    row = [(c or "").replace("\n", " ").strip() for c in row]
                    if len(row) < 8 or not row[0] or row[0] in ("Station",):
                        continue
                    station, state, sector, owner, rtype = row[:5]
                    if not _f(row[5]):
                        continue
                    out.append(dict(station=station, state=state, sector=sector,
                                    owner=owner, type=rtype,
                                    capacity_mw=_f(row[5]),
                                    gen_today_mu=_f(row[6]),
                                    gen_mtd_mu=_f(row[7])))
    return date, out


def save(date, state_rows, station_rows):
    con = connect()
    with con:
        con.executemany(
            """INSERT OR REPLACE INTO merit_state_daily
            (date, state, metric, wind, solar, res_other, res_total)
            VALUES (:date,:state,:metric,:wind,:solar,:res_other,:res_total)""",
            [dict(r, date=date) for r in state_rows])
        con.executescript("""
        CREATE TABLE IF NOT EXISTS res_stations_daily (
            date TEXT NOT NULL, station TEXT NOT NULL, state TEXT,
            sector TEXT, owner TEXT, type TEXT,
            capacity_mw REAL, gen_today_mu REAL, gen_mtd_mu REAL,
            PRIMARY KEY (date, station));
        """)
        con.executemany(
            """INSERT OR REPLACE INTO res_stations_daily
            (date, station, state, sector, owner, type, capacity_mw,
             gen_today_mu, gen_mtd_mu)
            VALUES (:date,:station,:state,:sector,:owner,:type,:capacity_mw,
             :gen_today_mu,:gen_mtd_mu)""",
            [dict(r, date=date) for r in station_rows])
    con.close()


REPORT_URL = ("https://cea.nic.in/api/upload/rpm/Report_{d}.pdf")  # observed pattern


def fetch(url, timeout=60):
    r = requests.get(url, timeout=timeout, verify=False,
                     headers={"User-Agent": "Mozilla/5.0"})
    r.raise_for_status()
    p = Path("data/downloads") / f"res-report-{datetime.now():%Y-%m-%d}.pdf"
    p.parent.mkdir(exist_ok=True)
    p.write_bytes(r.content)
    return p


def main():
    ap = argparse.ArgumentParser()
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--file")
    g.add_argument("--url")
    g.add_argument("--latest", action="store_true")
    args = ap.parse_args()

    if args.file:
        path = Path(args.file)
    elif args.url:
        path = fetch(args.url)
    else:
        today = datetime.now().strftime("%d%m%Y")
        try:
            path = fetch(REPORT_URL.format(d=today))
        except Exception as e:
            log("res_generation", "fail", str(e))
            sys.exit(1)

    sdate, srows = parse_state_rows(path)
    date, stations = parse_station_rows(path)
    date = date or sdate
    save(date, srows, stations)
    msg = f"{date}: {len(srows)} state rows, {len(stations)} station rows"
    print(msg)
    log("res_generation", "ok", msg)


if __name__ == "__main__":
    main()
