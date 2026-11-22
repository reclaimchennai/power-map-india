#!/usr/bin/env python3
"""Freshness check: is every source still arriving? Writes web/data/health.json and logs to scrape_log.

    python scripts/freshness.py        (also run by scrapers/collect.py after every pass)

Each check reads the newest DATA date (not the last fetch: in Nov 2026 the NPP map job logged "ok" for 18 days while
saving nothing), compares it with how late that source normally is, and marks it late past that allowance. The Coal
Tracker lists these in its footer, so a source that stops is visible on the page the same day.
"""
import json
import os
import sqlite3
import time
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DB = ROOT / "data" / "power.db"
OUT = ROOT / "web" / "data" / "health.json"
# the public repo's daily CSV readme (rewritten by its publisher each day); override where the checkout lives elsewhere
PUBLIC = Path(os.environ.get("POWERMAP_PUBLIC_README", Path.home() / "projects" / "_public" / "power-map-india" / "data" / "latest" / "README.md"))

# (key, label, kind, sql returning the newest date/time, allowance in days)
#   kind "day":   a dated day; late when more than `allow` days before today (IST)
#   kind "month": a month; late when more than `allow` days have passed since that month ended
#   kind "ts":    a UTC timestamp; allowance in days (fractions for hours)
CHECKS = [
    ("cea_coal", "CEA daily coal stock report", "day", "SELECT max(date) FROM coal_plants_daily", 2),
    ("dgr", "CEA daily generation report", "day", "SELECT max(date) FROM dgr_stations", 4),  # fetched 1-3 days after
    ("rail", "Indian Railways loading (RailSAHAY)", "day", "SELECT max(day) FROM rail_loading_snap", 2),
    ("cil_daily", "Coal India daily production", "day", "SELECT max(period) FROM coal_supply WHERE series='prod_d:CIL'", 3),
    ("rakes", "Coal India rakes (FOIS)", "day", "SELECT max(period) FROM coal_supply WHERE series='rakes_loaded_d:CIL'", 3),
    ("ncp", "National Coal Portal", "day", "SELECT max(period) FROM coal_supply WHERE series='ncp_prod_ytd:Total'", 5),
    ("npp_station", "NPP station generation", "day", "SELECT max(date) FROM npp_station_daily", 4),
    ("nfms", "NFMS feeder supply", "day", "SELECT max(date) FROM nfms_national", 2),
    ("sldc", "Tamil Nadu SLDC statement", "day", "SELECT max(report_date) FROM sldc_versions", 3),
    ("cwc", "CWC reservoir bulletin", "day", "SELECT max(date) FROM cwc_reservoir_weekly", 10),
    ("merit", "NPP merit order (all India, live)", "ts", "SELECT max(ts) FROM merit_rt", 0.25),
    ("vp", "Vidyut Pravah demand (live)", "ts", "SELECT max(ts) FROM vp_blocks", 0.25),
    ("moc_monthly", "Ministry of Coal monthly statistics", "month", "SELECT max(period) FROM coal_supply WHERE series='prod_m:Total'", 45),
    ("cea_monthly", "CEA monthly coal report", "month", "SELECT max(period) FROM coal_supply WHERE series='cea_rcpt_m:Total'", 75),
    ("imports", "Coal imports (TradeStat / Koyla Shakti)", "month",
     "SELECT max(period) FROM coal_supply WHERE series IN ('imports_m:Total','ks_imports_fytd:Total')", 75),
    ("ports", "Coal at ports (Ports ministry)", "month", "SELECT max(period) FROM coal_supply WHERE series='port_coal_m:Total-Thermal'", 50),
]
FILES = [  # (key, label, path, allowance in days)
    ("posters", "Posters (redrawn daily)", ROOT / "web" / "posters" / "coal_india_en.png", 1.5),
    ("github", "Open data on GitHub (daily)", PUBLIC, 1.5),
]


def ist_today():
    return (datetime.now(timezone.utc) + timedelta(hours=5, minutes=30)).date()


def month_end(p):
    y, m = int(p[:4]), int(p[5:7])
    return date(y + (m == 12), m % 12 + 1, 1) - timedelta(days=1)


def check():
    con = sqlite3.connect(f"file:{DB}?mode=ro", uri=True, timeout=60)
    now = datetime.now(timezone.utc)
    out = []
    for key, label, kind, sql, allow in CHECKS:
        try:
            v = con.execute(sql).fetchone()[0]
        except sqlite3.OperationalError:
            v = None
        age = None
        if v:
            if kind == "day":
                age = (ist_today() - date.fromisoformat(str(v)[:10])).days
            elif kind == "month":
                age = (ist_today() - month_end(str(v)[:7])).days
            else:
                t = datetime.fromisoformat(str(v)[:19].replace("T", " ")).replace(tzinfo=timezone.utc)
                age = round((now - t).total_seconds() / 86400, 2)
        out.append({"key": key, "label": label, "kind": kind, "latest": v and str(v)[:19], "age_days": age, "allow_days": allow,
                    "late": age is None or age > allow})
    con.close()
    for key, label, path, allow in FILES:
        age = round((time.time() - path.stat().st_mtime) / 86400, 2) if path.exists() else None
        out.append({"key": key, "label": label, "kind": "ts", "latest": path.exists() and datetime.fromtimestamp(path.stat().st_mtime, timezone.utc).strftime("%Y-%m-%d %H:%M"),
                    "age_days": age, "allow_days": allow, "late": age is None or age > allow})
    return out


def main():
    res = check()
    late = [r for r in res if r["late"]]
    doc = {"generated": datetime.now(timezone.utc).isoformat(timespec="seconds"), "late": [r["key"] for r in late], "sources": res}
    OUT.parent.mkdir(parents=True, exist_ok=True)
    tmp = OUT.with_suffix(".tmp")
    tmp.write_text(json.dumps(doc, indent=1))
    os.replace(tmp, OUT)
    # log only when the set of late sources changes, so the log shows when each one stopped and came back
    import sys
    sys.path.insert(0, str(ROOT))
    from store import connect, log
    detail = ", ".join(f"{r['label']} (latest {r['latest'] or 'none'})" for r in late) or "all sources current"
    c = connect()
    prev = c.execute("SELECT detail FROM scrape_log WHERE source='freshness' ORDER BY id DESC LIMIT 1").fetchone()
    c.close()
    if not prev or prev[0] != detail:
        log("freshness", "error" if late else "ok", detail)
    return doc


if __name__ == "__main__":
    d = main()
    for r in d["sources"]:
        print(f"{'LATE' if r['late'] else 'ok  '} {r['label']:<45} {r['latest']}  ({r['age_days']} d, allowed {r['allow_days']})")
