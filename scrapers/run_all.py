"""Run all scrapers once, or loop on an interval (realtime-ish collection).

    python -m scrapers.run_all            # one pass
    python -m scrapers.run_all --loop 900 # every 15 minutes
"""
import argparse
import time
import traceback
from importlib import import_module

from store import log, connect

JOBS = ["scrapers.cea_coal", "scrapers.res_generation", "scrapers.tneb_sldc",
        "scrapers.tn_mix", "scrapers.npp_dgr"]

# weekly-ish sources — run separately: coal_india, npcil, tn_district


def run_one(mod_name):
    try:
        mod = import_module(mod_name)
        sys_argv = mod.sys.argv
        mod.sys.argv = [mod_name, "--latest"] if mod_name != "scrapers.tneb_sldc" else [mod_name]
        try:
            mod.main()
        finally:
            mod.sys.argv = sys_argv
    except SystemExit:
        pass
    except Exception as e:
        log(mod_name, "error", f"{e}\n{traceback.format_exc()}")
        print(f"[{mod_name}] ERROR: {e}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--loop", type=int, default=0, help="seconds between passes")
    args = ap.parse_args()

    while True:
        for job in JOBS:
            run_one(job)
        con = connect()
        n = con.execute("SELECT count(*) FROM scrape_log WHERE status='ok'").fetchone()[0]
        con.close()
        print(f"pass done, {n} total ok scrapes")
        if not args.loop:
            break
        time.sleep(args.loop)


if __name__ == "__main__":
    main()
