"""National Power Portal (npp.gov.in) map dashboards — every generating station in India.

The gc-map-dashboard's own XHR endpoints (no auth) give, per state:
  station_details  : station id, name, type (100001 hydro, 100002 thermal, 100003 nuclear),
                     lat/lon, installed capacity   (positions are often wrong — QA in build)
  dailyGenStn      : per-station programme vs actual generation (MU) for the latest day,
                     same day last year, and financial-year cumulative
Zones (getAllZoneGen) -> states (getAllZoneStateGen) -> stations (getZoneStateWiseGen).

Also snapshots cp-map-dashboard getStateCpt (installed capacity by source, daily demand)
for each state. Raw JSON responses are archived gzipped under raw/npp/<date>/.
"""
import gzip
import json
import sys
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path

import requests
import urllib3

from store import connect, log

urllib3.disable_warnings()
BASE = "https://npp.gov.in/dashBoard/"
ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "raw" / "npp"
H = {"User-Agent": "Mozilla/5.0 (reclaimchennai power map)", "X-Requested-With": "XMLHttpRequest",
     "Referer": "https://npp.gov.in/dashBoard/gc-map-dashboard"}
IST = timezone(timedelta(hours=5, minutes=30))
TYPES = {100001: "hydro", 100002: "thermal", 100003: "nuclear"}

SCHEMA = """
CREATE TABLE IF NOT EXISTS npp_stations (
    station_id INTEGER PRIMARY KEY, name TEXT, type TEXT, state TEXT, state_id INTEGER,
    zone TEXT, lat REAL, lon REAL, capacity_mw REAL, first_seen TEXT, last_seen TEXT
);
CREATE TABLE IF NOT EXISTS npp_station_daily (
    date TEXT NOT NULL, station_id INTEGER NOT NULL, name TEXT, state TEXT,
    prog_mu REAL, actual_mu REAL, prog_mu_ly REAL, actual_mu_ly REAL,
    prog_cum_mu REAL, actual_cum_mu REAL, actual_cum_mu_ly REAL,
    PRIMARY KEY (date, station_id)
);
CREATE TABLE IF NOT EXISTS npp_state_daily (
    date TEXT NOT NULL, state_id INTEGER NOT NULL, state TEXT, zone TEXT,
    prog_mu REAL, actual_mu REAL, actual_mu_ly REAL, actual_cum_mu REAL,
    PRIMARY KEY (date, state_id)
);
CREATE TABLE IF NOT EXISTS npp_state_capacity (
    date TEXT NOT NULL, state_id INTEGER NOT NULL, state TEXT, payload TEXT,
    PRIMARY KEY (date, state_id)
);
"""


def get(ep, **params):
    for attempt in range(4):
        try:
            r = requests.get(BASE + ep, params=params, headers=H, timeout=90, verify=False)
            r.raise_for_status()
            return r.json()
        except Exception as e:  # NPP is flaky; back off
            if attempt == 3:
                raise
            time.sleep(4 * (attempt + 1))


def ms_to_date(ms):
    return datetime.fromtimestamp(ms / 1000, IST).date().isoformat() if ms else None


def archive(day, name, obj):
    d = RAW / day
    d.mkdir(parents=True, exist_ok=True)
    with gzip.open(d / f"{name}.json.gz", "wt") as f:
        json.dump(obj, f)


def run(with_capacity=True):
    con = connect()
    con.executescript(SCHEMA)
    now = datetime.now(timezone.utc).isoformat()
    allz = get("getAllZoneGen", ID="IND")
    day = ms_to_date(allz["headerMap"]["GN_OBJ"]["generation_date"])
    archive(day, "allzone", allz)
    zones = [(z["zone_id"], z["zone_name"]) for z in allz["dailyGenStn"] if z["zone_id"] < 100006]
    n_st = n_day = 0
    for zid, zname in zones:
        zs = get("getAllZoneStateGen", zoneId=zid)
        archive(day, f"zone_{zid}", zs)
        for s in zs["dailyGenStn"] or []:
            sid, sname = s["station_id"], s["station_name"]
            with con:
                con.execute("INSERT OR REPLACE INTO npp_state_daily VALUES (?,?,?,?,?,?,?,?)",
                            (day, sid, sname, zname, s["program_generation"], s["actual_generation"],
                             s["actual_generation_ly"], s["actual_generation_cumulative"]))
            st = get("getZoneStateWiseGen", stateId=sid, zoneId=zid, genDate="")
            archive(day, f"state_{sid}", st)
            with con:
                for x in st.get("station_details") or []:
                    con.execute("""INSERT INTO npp_stations VALUES (?,?,?,?,?,?,?,?,?,?,?)
                        ON CONFLICT(station_id) DO UPDATE SET name=excluded.name, type=excluded.type,
                        state=excluded.state, lat=excluded.lat, lon=excluded.lon,
                        capacity_mw=excluded.capacity_mw, last_seen=excluded.last_seen""",
                                (x["station_id"], x["station_name"].strip(), TYPES.get(x["generating_type_id"], str(x["generating_type_id"])),
                                 sname, sid, zname, x["latitude"], x["longitude"], x["unit_installed_capacity"], now, now))
                    n_st += 1
                for g in st.get("dailyGenStn") or []:
                    con.execute("INSERT OR REPLACE INTO npp_station_daily VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                                (ms_to_date(g["generation_date"]) or day, g["station_id"], g["station_name"].strip(), sname,
                                 g["program_generation"], g["actual_generation"], g["program_generation_ly"],
                                 g["actual_generation_ly"], g["program_generation_cumulative"],
                                 g["actual_generation_cumulative"], g["actual_generation_cumulative_ly"]))
                    n_day += 1
            if with_capacity:
                try:
                    cp = get("getStateCpt", stateId=sid, zoneId=zid)
                    archive(day, f"cpt_{sid}", cp)
                    keep = {k: cp.get(k) for k in ("installed_Capacity", "dailyDemmandCp")}
                    with con:
                        con.execute("INSERT OR REPLACE INTO npp_state_capacity VALUES (?,?,?,?)",
                                    (day, sid, sname, json.dumps(keep)))
                except Exception as e:
                    print("capacity", sname, e)
            time.sleep(0.5)
    con.close()
    log("npp_map", "ok", f"{day}: {n_st} stations, {n_day} daily rows")
    return day, n_st, n_day


def main():
    print(run(with_capacity="--no-capacity" not in sys.argv))


if __name__ == "__main__":
    main()
