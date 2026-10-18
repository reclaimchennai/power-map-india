"""One collection pass for the live power map; run every 15 min by deploy/power-collect.timer.

Each source runs on its own cadence (tracked in scrape_log), so a 15-minute timer is cheap:
  sldc_peakdet   every pass      TN grid source mix, issued about once a day ~noon IST (archived per version)
  vidyut_pravah  every pass      demand met per 15-min block: India + TN every pass, all states hourly
  npp_merit      every pass      all-India demand + generation by source, ~4-min step (NPP merit chart)
  nfms           every 3 h       hours of supply by feeder type, feeder integration, city SAIFI/SAIDI (NFMS)
  npp_map        every 3 h       all-India station list + latest daily generation
  dgr2 (CEA)     until today's   per-station daily generation, coal days, outages (dated XLS)
  dailyCoal1     until today's   per-plant coal stock report (dated PDF)
  coal_supply    every 60 min    CIL daily production / offtake by company, National Coal Portal totals, NPP days-of-coal buckets
  cea_monthly    every 12 h      CEA monthly coal report per plant (receipts by source, burn, stock) and imports for power
  coal_msg       daily           Ministry of Coal monthly statistics: production, dispatch (by sector), rakes, lignite
  ports_coal     daily           coal handled at major / non-major ports (Ports ministry) and coal imports by HS code (TradeStat)
  gas_power      daily           gas burnt for power (PPAC, monthly) and CEA's per-plant gas allotted vs consumed
  coal_rakes     every 6 h       coal trains loaded per day by CIL subsidiary (CIL Rakes Data, FOIS), via Playwright
  gem_coal       weekly          Global Energy Monitor coal mine and terminal trackers (CC BY 4.0)
  cwc_reservoirs daily           Central Water Commission weekly bulletin: live storage in 150+ reservoirs (hydro's fuel)
  weather        every 60 min    Open-Meteo wind/cloud at thermal & RE sites (plume direction)
then scripts/export_live.py writes web/data/live/*.json and scripts/export_coal.py web/data/coal/coal.json (atomic renames).
"""
import sys
import time
import traceback
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import requests
import urllib3

from store import connect, log

urllib3.disable_warnings()
ROOT = Path(__file__).resolve().parent.parent
DL = ROOT / "raw" / "downloads"
UA = {"User-Agent": "Mozilla/5.0 (reclaimchennai power map; +https://power.reclaimchennai.city)"}


def last_ok(source):
    con = connect()
    r = con.execute("SELECT max(ts) FROM scrape_log WHERE source=? AND status='ok'", (source,)).fetchone()[0]
    con.close()
    return datetime.fromisoformat(r).replace(tzinfo=timezone.utc) if r else None


def due(source, minutes):
    t = last_ok(source)
    return t is None or datetime.now(timezone.utc) - t > timedelta(minutes=minutes)


def have(table, col, value):
    con = connect()
    try:
        return con.execute(f"SELECT 1 FROM {table} WHERE {col}=? LIMIT 1", (value,)).fetchone() is not None
    except Exception:
        return False
    finally:
        con.close()


def get(url, timeout=90):
    r = requests.get(url, headers=UA, timeout=timeout, verify=False)
    r.raise_for_status()
    return r.content


def job_sldc():
    from scrapers import sldc_peakdet
    print("sldc", sldc_peakdet.fetch_and_store())


def job_npp():
    if not due("npp_map", 170):
        return
    from scrapers import npp_map
    print("npp", npp_map.run(with_capacity=due("npp_map_capacity", 24 * 60)))
    log("npp_map_capacity", "ok", "")


def job_dgr():
    from scrapers import npp_dgr
    DL.mkdir(parents=True, exist_ok=True)
    for back in (1, 2, 3):
        day = date.today() - timedelta(days=back)
        if have("dgr_stations", "date", day.isoformat()):
            continue
        url = npp_dgr.DGR2.format(d=day.strftime("%d-%m-%Y"), f=f"dgr2-{day:%Y-%m-%d}.xls")
        try:
            data = get(url)
        except Exception as e:
            print("dgr", day, "not yet:", e)
            continue
        p = DL / f"dgr2-{day:%Y-%m-%d}.xls"
        p.write_bytes(data)
        d, rows = npp_dgr.parse(p)
        npp_dgr.save(d or day.isoformat(), rows)
        log("npp_dgr", "ok", f"{d}: {len(rows)} rows")
        print("dgr", d, len(rows))


def job_coal():
    from scrapers import cea_coal
    for back in (0, 1, 2):
        day = date.today() - timedelta(days=back)
        p = DL / f"dailyCoal1-{day:%Y-%m-%d}.pdf"
        if p.exists():
            continue
        url = f"https://npp.gov.in/public-reports/cea/daily/fuel/{day:%d-%m-%Y}/dailyCoal1-{day:%Y-%m-%d}.pdf"
        try:
            data = get(url)
            if not data.startswith(b"%PDF"):
                raise ValueError("not a pdf")
        except Exception as e:
            print("coal", day, "not yet:", e)
            continue
        p.write_bytes(data)
        d, rows = cea_coal.parse_pdf(p)
        cea_coal.save(d, rows)
        log("cea_coal", "ok", f"{d}: {len(rows)} plants")
        print("coal", d, len(rows))


def job_vp():
    from scrapers import vidyut_pravah
    print("vidyut_pravah", vidyut_pravah.run(all_states=due("vidyut_pravah_all", 55)))


def job_merit():
    from scrapers import npp_merit
    print("npp_merit", npp_merit.run(1))


def job_nfms():
    if not due("nfms", 175):
        return
    from scrapers import nfms
    print("nfms", nfms.run())


def job_coal_supply():
    if not due("coal_supply", 55):
        return
    from scrapers import coal_supply
    print("coal_supply", coal_supply.run(2))


def job_cea_monthly():
    if not due("cea_monthly", 12 * 60):
        return
    from scrapers import cea_monthly
    print("cea_monthly", cea_monthly.run())


def job_coal_msg():
    if not due("coal_msg", 24 * 60):
        return
    from scrapers import coal_msg
    print("coal_msg", coal_msg.run())


def job_ports_trade():
    if not due("ports_coal", 24 * 60):
        return
    from scrapers import ports_coal, tradestat
    print("ports_coal", ports_coal.run())
    print("tradestat", tradestat.run())


def job_gas_power():
    if not due("gas_power", 24 * 60):
        return
    from scrapers import gas_power
    print("gas_power", gas_power.run())


def job_rakes():
    if not due("coal_rakes", 6 * 60):
        return
    from scrapers import coal_rakes
    print("coal_rakes", coal_rakes.run(3))


def job_gem():
    if not due("gem_coal", 7 * 24 * 60):
        return
    from scrapers import gem_coal
    print("gem_coal", gem_coal.run())


def job_cwc():
    if not due("cwc_reservoirs", 24 * 60):
        return
    from scrapers import cwc_reservoirs
    print("cwc_reservoirs", cwc_reservoirs.run())


def job_weather():
    if not due("weather", 55):
        return
    from scrapers import weather
    print("weather", weather.run())


JOBS = [("sldc_peakdet", job_sldc), ("vidyut_pravah", job_vp), ("npp_merit", job_merit), ("nfms", job_nfms), ("npp_map", job_npp), ("npp_dgr", job_dgr),
        ("cea_coal", job_coal), ("coal_supply", job_coal_supply),
        ("cea_monthly", job_cea_monthly), ("coal_msg", job_coal_msg), ("ports_coal", job_ports_trade), ("gas_power", job_gas_power), ("coal_rakes", job_rakes), ("gem_coal", job_gem), ("cwc_reservoirs", job_cwc),
        ("weather", job_weather)]


def export():
    sys.path.insert(0, str(ROOT / "scripts"))
    import export_live
    export_live.main()
    import export_coal
    export_coal.main()


def main():
    only = set(sys.argv[1:])
    for name, fn in JOBS:
        if only and name not in only:
            continue
        t0 = time.time()
        try:
            fn()
        except Exception as e:
            log(name, "error", f"{e}\n{traceback.format_exc()}")
            print(f"[{name}] ERROR: {e}")
        print(f"  {name} {time.time() - t0:.1f}s")
    try:
        export()
    except Exception as e:
        log("export_live", "error", f"{e}\n{traceback.format_exc()}")
        print("[export] ERROR", e)
        raise


if __name__ == "__main__":
    main()
