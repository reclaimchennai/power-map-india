"""NPCIL nuclear operating performance scraper.

npcil.nic.in publishes one OperatingPerformance page per station (unit-wise
reactor type, capacity, commercial operation date, cumulative generation in
MU). Station page ids are stable; found via /content/<id>_1_OperatingPerformance.
"""
import re
import html as htmllib
from datetime import datetime

import requests

from store import connect, log

STATION_PAGES = {
    "MAPS": "/content/324_1_OperatingPerformance.aspx",
    "RAPS": "/content/320_1_OperatingPerformance.aspx",
    "KGS": "/content/321_1_OperatingPerformance.aspx",
    "NAPS": "/content/322_1_OperatingPerformance.aspx",
    "KAPS": "/content/323_1_OperatingPerformance.aspx",
    "KKNPP": "/content/151_1_OperatingPerformance.aspx",
    "TAPS": "/content/253_1_OperatingPerformance.aspx",
}
# unit names carry their own station prefix ("KGS Unit-1") — pages mix
STATION_BY_PREFIX = {p: s for s, p in [
    ("MAPS", "MAPS"), ("RAPS", "RAPS"), ("Kaiga", "KGS"), ("Narora", "NAPS"),
    ("Kakrapar", "KAPS"), ("Kudankulam", "KKNPP"), ("Tarapur", "TAPS")]}
BASE = "https://www.npcil.nic.in/"


def scrape(url):
    s = requests.get(url, timeout=60, verify=False,
                     headers={"User-Agent": "Mozilla/5.0"}).text
    station = None
    m = re.search(r"<h1[^>]*>|<title>(.*?)</title>", s, re.S)
    title = htmllib.unescape(re.sub(r"<[^>]+>", "", m.group(1))).strip() if m and "</" in (m.group(1) or "") else ""
    units = []
    for tab in re.findall(r"<table.*?</table>", s, re.S):
        rows = re.findall(r"<tr.*?</tr>", tab, re.S)
        for r in rows[1:]:
            cells = [htmllib.unescape(re.sub(r"<[^>]+>", "", c)).strip()
                     for c in re.findall(r"<t[dh][^>]*>(.*?)</t[dh]>", r, re.S)]
            if not cells or not cells[0]:
                continue
            units.append(cells)
    # station name: the page has per-station tables; use first unit's prefix if possible
    return station or title, units


def main():
    con = connect()
    with con:
        con.executescript("""
        CREATE TABLE IF NOT EXISTS npcil_units (
            station TEXT, unit TEXT, reactor_type TEXT, capacity_mwe REAL,
            commercial_operation TEXT, cumulative_gen_mu REAL,
            ts TEXT DEFAULT (datetime('now')), PRIMARY KEY (station, unit));
        """)
        for name, path in STATION_PAGES.items():
            try:
                title, units = scrape(BASE + path)
                if not units:
                    continue
                for cells in units:
                    unit = cells[0]
                    if unit.lower().startswith(("total", "gross")):
                        continue
                    matched = [s2 for pre, s2 in STATION_BY_PREFIX.items()
                               if pre in unit]
                    if not matched:
                        continue
                    name = matched[0] + (" (Kaiga)" if matched[0] == "KGS" else "")
                    cap = _f = None
                    try:
                        cap = float(re.sub(r"[^\d.]", "", cells[2])) if len(cells) > 2 else None
                    except (ValueError, IndexError):
                        pass
                    cum = None
                    try:
                        cum = float(re.sub(r"[^\d.]", "", cells[-1])) if cells[-1] else None
                    except ValueError:
                        pass
                    con.execute(
                        """INSERT OR REPLACE INTO npcil_units
                        (station, unit, reactor_type, capacity_mwe,
                         commercial_operation, cumulative_gen_mu)
                        VALUES (?,?,?,?,?,?)""",
                        (name, unit, cells[1] if len(cells) > 1 else "",
                         cap, cells[3] if len(cells) > 3 else "", cum))
            except Exception as e:
                log("npcil", "error", f"{name}: {e}")
                print(f"[{name}] ERROR {e}")
    con.close()
    print("npcil units updated")
    log("npcil", "ok", "unit performance scraped")


if __name__ == "__main__":
    main()
