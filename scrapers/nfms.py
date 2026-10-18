"""National Feeder Monitoring System (nfms.powermin.gov.in, REC PDCL): electricity supply to consumers.

What the grid delivers at the end of the line: average hours of supply per day by feeder type
(urban, rural, agricultural, industrial, mixed), feeder integration per state, SAIFI/SAIDI for the
major cities, and the communication technology behind the meters.

The public site is an Angular app whose API requests carry an Authorization header built at runtime.
Like any visitor, we open the public homepage in headless Chromium and reuse the header the page itself
sends for our API calls, so no key is stored here and nothing is bypassed.
  national  Homepage (hours of supply), FeederStatsV2, FeederCommTech, DashboardTile, BestFeeders,
            IntFeeders (integration % by state), AvgPowerSupDur, MajorCitiesMonthlyDaily (month)
  states    AvgPowerSupDur + FeederStatsV2 for every state code from the site's own Search list
Raw responses are archived gzipped under raw/nfms/<date>/. Runs every 3 h from collect.py (NFMS
refreshes once a day, for the previous day).
"""
import gzip
import json
import os
import time
from datetime import date, datetime, timezone
from pathlib import Path

import requests
import urllib3

from store import connect, log

urllib3.disable_warnings()
API = "https://nfmsweb-prod-api.recpdcl.net/v11/"
SITE = "https://nfms.powermin.gov.in/"
ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "raw" / "nfms"
CHROME = os.path.expanduser("~/.cache/ms-playwright/chromium-1234/chrome-linux64/chrome")

SCHEMA = """
CREATE TABLE IF NOT EXISTS nfms_state (
    date TEXT NOT NULL, state_code TEXT NOT NULL, state TEXT, data_refresh TEXT,
    hrs_inc_ag REAL, hrs_exc_ag REAL, urban REAL, rural REAL, agri REAL, industrial REAL, mixed REAL,
    feeders_total INTEGER, feeders_integrated INTEGER, integration_pct REAL, discoms INTEGER,
    PRIMARY KEY (date, state_code)
);
CREATE TABLE IF NOT EXISTS nfms_city (
    month TEXT NOT NULL, state TEXT, discom TEXT NOT NULL, city TEXT NOT NULL, saifi REAL, saidi REAL,
    PRIMARY KEY (month, discom, city)
);
CREATE TABLE IF NOT EXISTS nfms_national (
    date TEXT PRIMARY KEY, payload TEXT
);
"""


def page_auth():
    """Open the public homepage the way a visitor does and read the Authorization its API calls use."""
    from playwright.sync_api import sync_playwright
    got = {}
    with sync_playwright() as p:
        kw = {"headless": True}
        if Path(CHROME).exists():
            kw["executable_path"] = CHROME
        b = p.chromium.launch(**kw)
        pg = b.new_page()
        def on_req(r):
            if "recpdcl.net" in r.url and r.headers.get("authorization"):
                got.setdefault("auth", r.headers["authorization"])
        pg.on("request", on_req)
        pg.goto(SITE, wait_until="networkidle", timeout=120000)
        b.close()
    if "auth" not in got:
        raise RuntimeError("NFMS: no API request seen on the homepage")
    return got["auth"]


def num(v):
    try:
        return float(str(v).replace(",", ""))
    except (TypeError, ValueError):
        return None


def last_of(v):
    """AvgPowerSupDur packs "a,b,c,value" strings; the last number is the day's figure."""
    return num(str(v).split(",")[-1]) if v is not None else None


def run():
    auth = page_auth()
    H = {"Authorization": auth, "Content-Type": "application/json", "Referer": SITE,
         "User-Agent": "Mozilla/5.0 (reclaimchennai power map; +https://power.reclaimchennai.city)"}
    today = date.today().isoformat()
    day_dir = RAW / today
    day_dir.mkdir(parents=True, exist_ok=True)

    def post(ep, body, tag=None):
        for attempt in range(3):
            try:
                r = requests.post(API + ep, json=body, headers=H, timeout=90, verify=False)
                r.raise_for_status()
                d = r.json()
                with gzip.open(day_dir / f"{tag or ep}.json.gz", "wt") as f:
                    json.dump({"body": body, "resp": d}, f)
                return d
            except Exception:
                if attempt == 2:
                    raise
                time.sleep(3 * (attempt + 1))

    nat = {}
    nat["hours"] = (post("Homepage", {"state_name": "ALL", "discomId": "ALL", "date": today, "type": "24hrs"}).get("Data") or [{}])[0]
    nat["feeders"] = (post("FeederStatsV2", {"state_name": "ALL", "discomId": "ALL", "date": today}).get("Data") or [{}])[0]
    nat["comm"] = post("FeederCommTech", {"State": "ALL", "Discom": "ALL", "Date": today})
    nat["tile"] = post("DashboardTile", {"State": "ALL", "Discom": "ALL", "Date": today})
    nat["best"] = post("BestFeeders", {"State": "ALL", "Discom": "ALL", "Date": today, "Type": "24hrs", "Method": "24x7"})
    nat["supply"] = post("AvgPowerSupDur", {"State": "ALL", "Discom": "ALL", "Date": today, "Type": "24hrs"}, "AvgPowerSupDur_ALL")
    ints = post("IntFeeders", {"date": today})
    nat["integration"] = {v["value"].split(",")[0]: num(v["value"].split(",")[1]) for v in ints.get("Data", []) if "," in v.get("value", "")}
    states = [x["data"].split(", ", 1) for x in post("Search", {"state": "ALL", "discom": "", "zone": "", "circle": "", "division": "",
              "subDivision": "", "substationName": "", "type": "STATE", "date": today}).get("Data", []) if ", " in x.get("data", "")]
    states = [s for s in states if s[0] != "ALL"]
    month = datetime.now().strftime("%B")
    fy = f"{date.today().year}-{date.today().year + 1}" if date.today().month >= 4 else f"{date.today().year - 1}-{date.today().year}"
    cities = post("MajorCitiesMonthlyDaily", {"SummarizationLevel": "Monthly", "State": "ALL", "City": "ALL", "Year": fy, "Month": month})

    con = connect()
    con.executescript(SCHEMA)
    rows = 0
    with con:
        con.execute("INSERT OR REPLACE INTO nfms_national VALUES (?,?)", (today, json.dumps(nat)))
        for code, name in [("ALL", "India")] + states:
            try:
                sup = post("AvgPowerSupDur", {"State": code, "Discom": "ALL", "Date": today, "Type": "24hrs"}, f"AvgPowerSupDur_{code}")
                fd = (post("FeederStatsV2", {"state_name": code, "discomId": "ALL", "date": today}, f"FeederStatsV2_{code}").get("Data") or [{}])[0]
            except Exception as e:
                print("nfms", code, e)
                continue
            a = (sup.get("AvgSupplyDuration") or [{}])[0]
            dd = (a.get("Data") or [{}])[0]
            con.execute("INSERT OR REPLACE INTO nfms_state VALUES (?,?,?,?, ?,?,?,?,?,?,?, ?,?,?,?)",
                        (today, code, name, a.get("dataRefresh"), num(a.get("avgSupplyIncAG")), num(a.get("avgSupplyExcAG")),
                         last_of(dd.get("Urban")), last_of(dd.get("Rural")), last_of(dd.get("Agricultural")),
                         last_of(dd.get("Dedicated_Industrial")), last_of(dd.get("Mixed")),
                         int(num(fd.get("totalFeeders")) or 0) or None, int(num(fd.get("totalIntegrated")) or 0) or None,
                         num(fd.get("IntegrationPercent")) or nat["integration"].get(code), int(num(fd.get("totalDiscoms")) or 0) or None))
            rows += 1
            time.sleep(0.4)
        for c in cities.get("Data", []) or []:
            con.execute("INSERT OR REPLACE INTO nfms_city VALUES (?,?,?,?,?,?)",
                        (f"{c.get('YEAR')}-{datetime.strptime(c.get('Month', month), '%B').month:02d}", c.get("State"), c.get("Discom"),
                         (c.get("City") or "").title(), num(c.get("SAIFI")), num(c.get("SAIDI"))))
    con.close()
    log("nfms", "ok", f"{rows} states, {len(cities.get('Data') or [])} city rows")
    return rows


if __name__ == "__main__":
    print(run())
