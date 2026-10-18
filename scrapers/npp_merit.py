"""All-India demand met and generation by source, every ~4 minutes (NPP gc-map-dashboard-meritchart).

The National Power Portal's merit chart page reads two public endpoints for any day:
  demandmet1chartdata?date=YYYY-MM-DD   DEMAND MET (MW)
  demandmet2chartdata?date=YYYY-MM-DD   THERMAL / GAS / NUCLEAR / HYDRO / WIND / SOLAR GENERATION (MW)
at about a 4-minute step, with history going back at least a year. This is the real-time national mix.

    python -m scrapers.npp_merit            # today and yesterday (collect.py, every pass)
    python -m scrapers.npp_merit --back 400 # backfill 400 days (skips days already complete)
"""
import sys
import time
from datetime import date, datetime, timedelta, timezone

import requests
import urllib3

from store import connect, log

urllib3.disable_warnings()
BASE = "https://npp.gov.in/dashBoard/"
H = {"User-Agent": "Mozilla/5.0 (reclaimchennai power map)", "X-Requested-With": "XMLHttpRequest",
     "Referer": "https://npp.gov.in/dashBoard/gc-map-dashboard-meritchart"}
KEY = {"DEMAND MET": "demand", "THERMAL GENERATION": "thermal", "GAS GENERATION": "gas", "NUCLEAR GENERATION": "nuclear",
       "HYDRO GENERATION": "hydro", "WIND GENERATION": "wind", "SOLAR GENERATION": "solar"}
SCHEMA = """
CREATE TABLE IF NOT EXISTS merit_rt (
    ts TEXT NOT NULL, series TEXT NOT NULL, mw REAL,
    PRIMARY KEY (ts, series)
);
CREATE INDEX IF NOT EXISTS merit_rt_ts ON merit_rt (ts);
"""


def fetch_day(d):
    rows = []
    for ep in ("demandmet1chartdata", "demandmet2chartdata"):
        r = requests.get(BASE + ep, params={"date": d.isoformat()}, headers=H, timeout=90, verify=False)
        r.raise_for_status()
        for x in r.json() or []:
            k = KEY.get((x.get("name_of_data") or "").strip().upper())
            if not k or x.get("updated_on") is None:
                continue
            ts = datetime.fromtimestamp(x["updated_on"] / 1000, timezone.utc).isoformat(timespec="seconds")
            rows.append((ts, k, x.get("value_of_data")))
    return rows


def store(rows):
    con = connect()
    con.executescript(SCHEMA)
    with con:
        con.executemany("INSERT OR REPLACE INTO merit_rt VALUES (?,?,?)", rows)
    con.close()


def day_count(d):
    con = connect()
    con.executescript(SCHEMA)
    lo = datetime(d.year, d.month, d.day, tzinfo=timezone(timedelta(hours=5, minutes=30))).astimezone(timezone.utc)
    n = con.execute("SELECT count(*) FROM merit_rt WHERE series='demand' AND ts >= ? AND ts < ?",
                    (lo.isoformat(), (lo + timedelta(days=1)).isoformat())).fetchone()[0]
    con.close()
    return n


def run(back=1):
    n = 0
    for k in range(back + 1):
        d = date.today() - timedelta(days=k)
        if k >= 2 and day_count(d) > 300:          # a finished past day: already complete
            continue
        rows = fetch_day(d)
        store(rows)
        n += len(rows)
        if back > 1:
            time.sleep(1.5)
    log("npp_merit", "ok", f"{n} rows")
    return n


if __name__ == "__main__":
    back = int(sys.argv[sys.argv.index("--back") + 1]) if "--back" in sys.argv else 1
    print(run(back))
