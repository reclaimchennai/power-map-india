"""Backfill CEA DGR2 (station-wise daily generation, coal days, outages) for past days.

    python -m scrapers.backfill_dgr 365      # the last 365 days, newest first; skips days already stored

The XLS for each day is kept in raw/downloads/dgr2/ (gitignored, on-disk archive). Polite: one
request every 2 s.
"""
import sys
import time
from datetime import date, timedelta
from pathlib import Path

import requests
import urllib3

from scrapers import npp_dgr
from store import connect, log

urllib3.disable_warnings()
DL = Path(__file__).resolve().parent.parent / "raw" / "downloads" / "dgr2"


def main():
    days = int(sys.argv[1]) if len(sys.argv) > 1 else 90
    DL.mkdir(parents=True, exist_ok=True)
    con = connect()
    have = {r[0] for r in con.execute("SELECT DISTINCT date FROM dgr_stations")}
    con.close()
    ok = miss = 0
    for back in range(1, days + 1):
        day = date.today() - timedelta(days=back)
        if day.isoformat() in have:
            continue
        p = DL / f"dgr2-{day:%Y-%m-%d}.xls"
        if not p.exists():
            url = npp_dgr.DGR2.format(d=day.strftime("%d-%m-%Y"), f=f"dgr2-{day:%Y-%m-%d}.xls")
            try:
                r = requests.get(url, headers={"User-Agent": "Mozilla/5.0 (reclaimchennai power map)"}, timeout=90, verify=False)
                r.raise_for_status()
                p.write_bytes(r.content)
            except Exception as e:
                miss += 1
                print(day, "missing", e)
                time.sleep(2)
                continue
            time.sleep(2)
        try:
            d, rows = npp_dgr.parse(p)
            npp_dgr.save(d or day.isoformat(), rows)
            ok += 1
            print(day, len(rows))
        except Exception as e:
            print(day, "parse failed", e)
    log("backfill_dgr", "ok", f"{ok} days added, {miss} missing")


if __name__ == "__main__":
    main()
