# tneb — India / Tamil Nadu electricity archive & live dashboard

Live dashboard + scheduled scrapers for Indian electricity infrastructure,
Tamil Nadu and Chennai first, expanding to all-India.

**Run it:**

```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
.venv/bin/python -m scrapers.run_all            # one collection pass
.venv/bin/python -m scrapers.run_all --loop 900 # keep collecting every 15 min
.venv/bin/python -W ignore -m uvicorn api.main:app --port 8300
# open http://localhost:8300
```

## What's live now

| Source | What we get | Scraper |
|---|---|---|
| CEA Fuel Mgmt daily coal report (via NPP) | Per-plant coal stocks (kt, % of normative), critical flags, day's receipt/consumption, coal-source remarks (mine/company, rail/sea, port stock e.g. LDG/UL) | `scrapers/cea_coal.py` |
| CEA Daily Renewable Generation Report | State-wise wind/solar/RES MU (daily + MTD) **and station-level** generation for ~350+ wind/solar farms | `scrapers/res_generation.py` |
| TNEB SLDC `reports1/peakdet.pdf` | TN installed capacity, peak demand, morning/evening peak, daily MU | `scrapers/tneb_sldc.py` |
| TNEB SLDC grid details (same PDF) | **Full source mix**: hydro/thermal/gas/wind/solar/cogen/biomass (cap, instantaneous MW, MU), **nuclear share** (Kudankulam, MAPS, Kaiga), **imports**: CGS share, LTOA/MTOA/STOA, REMC-ISTS, exchange (+imp/−exp), DSM | `scrapers/tn_mix.py` |
| Plant atlas (`data/plants_tn.csv`) | 51 TN generation sites — nuclear, coal, gas, hydro, wind, solar — with coordinates (exact where verified) | `scrapers/build_plants.py` → `/geo/tn_plants` |
| TNGIS `tn_substation` | 1,872 TNEB substations with voltage ratio, MVA capacity, feeders, circle — served at `/geo/tn_substation` | already ingested in `data/geo/` |
| TNGIS in_feeder + SRLDC map | **943-line transmission network** by kV class at `/geo/tn_lines` | `scrapers/build_lines.py` |
| NPP `publishedReports` dgr2 (daily XLS) | **Per-station, all-India**: generation today (program/actual MU), YTD, **coal stock in days**, capacity under outage + outage dates/remarks — 583 stations | `scrapers/npp_dgr.py` |
| coal.nic.in | Company-wise coal **production & offtake** vs target (CIL/SCCL/captive), **state-wise geological reserves**, monthly-statistics archive links | `scrapers/coal_india.py` |
| npcil.nic.in | **Nuclear fleet** unit performance (capacity, commercial date, cumulative MU) | `scrapers/npcil.py` |

> **Security note:** gov.in sites have incomplete TLS chains, so scrapers use
> `verify=False` (MITM risk on read-only public data). Remove it and add the
> certs to the trust store if you want strict verification.

**District-wise generation/consumption:** not published by TNEB/SLDC in real
time. Best available proxies: (a) TNEB circle-wise substation/capacity data
already in the substations layer (`circle_name` field), (b) TNERC's annual
tariff filings (district/category-wise sales, yearly PDF), (c) Consumptive
data per HT consumer via SLDC's EXEGYSTMT statements. Annual district sales
from TNERC is the next dataset to ingest.

Dashboard (`web/index.html`, served at `/`): dark Leaflet map of all TN substations
coloured by voltage class, live coal-stock table with map markers for major plants,
today's TN peak-demand cards, top-states renewables ranking, per-station TN
renewable output. Auto-refresh every 5 min.

## PDF handling

NPP/CEA rotate their direct asset URLs behind their Angular apps. Each scraper
therefore accepts `--file` (drop the daily PDF into `data/downloads/`, which
`run_all` also reads via `--latest` known-URL attempts) or an explicit `--url`.
Your existing daily downloads (`dailyCoal1-*.pdf`, `Report-*.pdf`) drop straight in.

## Layout

```
scrapers/   cea_coal.py  res_generation.py  tneb_sldc.py  run_all.py
api/        FastAPI (SQLite-backed, serves geojson + static web/)
web/        dashboard (Leaflet, vendored from maps-site)
data/       tneb.db (SQLite), downloads/, geo/
docs/       ROADMAP.md — plan for all-India archive + 3D pixelated models
```

## Scheduling (realtime collection)

macOS launchd or cron, e.g. every 15 minutes:

```
*/15 * * * * cd /Users/admin/Desktop/projects/tneb && .venv/bin/python -m scrapers.run_all >> data/scraper.log 2>&1
```

SLDC peaks update daily; CEA coal daily; renewables daily (the reports are
daily — NPP's interactive dashboards can be added later for 15-min granularity).
