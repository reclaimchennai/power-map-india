"""Backfill the CEA daily coal stock report (per plant: stock, receipt, consumption) from the NPP archive.

NPP keeps the dated PDFs from mid-2024 on:
  https://npp.gov.in/public-reports/cea/daily/fuel/DD-MM-YYYY/dailyCoal1-YYYY-MM-DD.pdf

    python -m scrapers.backfill_coal                  # 2024-06-01 .. yesterday, skipping dates already stored
    python -m scrapers.backfill_coal --from 2025-09-01
"""
import sys
import time
from datetime import date, timedelta
from pathlib import Path

import requests
import urllib3

from scrapers import cea_coal
from store import connect, log

urllib3.disable_warnings()
ROOT = Path(__file__).resolve().parent.parent
DL = ROOT / "raw" / "downloads"
URL = "https://npp.gov.in/public-reports/cea/daily/fuel/{d:%d-%m-%Y}/dailyCoal1-{d:%Y-%m-%d}.pdf"
UA = {"User-Agent": "Mozilla/5.0 (reclaimchennai power map; +https://power.reclaimchennai.city)"}


def stored():
    con = connect()
    try:
        return {r[0] for r in con.execute("SELECT DISTINCT date FROM coal_plants_daily")}
    finally:
        con.close()


def main():
    start = date.fromisoformat(sys.argv[sys.argv.index("--from") + 1]) if "--from" in sys.argv else date(2024, 6, 1)
    have = stored()
    DL.mkdir(parents=True, exist_ok=True)
    d, ok, miss = date.today() - timedelta(days=1), 0, 0
    while d >= start:
        if d.isoformat() not in have:
            p = DL / f"dailyCoal1-{d:%Y-%m-%d}.pdf"
            try:
                if not p.exists():
                    r = requests.get(URL.format(d=d), headers=UA, timeout=90, verify=False)
                    if r.status_code != 200 or not r.content.startswith(b"%PDF"):
                        miss += 1
                        print(d, "missing", r.status_code)
                        d -= timedelta(days=1)
                        time.sleep(0.5)
                        continue
                    p.write_bytes(r.content)
                rd, rows = cea_coal.parse_pdf(p)
                cea_coal.save(rd or d.isoformat(), rows)
                ok += 1
                print(d, rd, len(rows), flush=True)
            except Exception as e:
                print(d, "error", e, flush=True)
            time.sleep(1.0)
        d -= timedelta(days=1)
    log("cea_coal_backfill", "ok", f"{ok} days, {miss} missing")


if __name__ == "__main__":
    main()
