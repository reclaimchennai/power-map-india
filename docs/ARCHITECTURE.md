# Power Map of India (power.reclaimchennai.city)

Live at **https://power.reclaimchennai.city/** (static site + a 15-minute collector). Started
2026-09-24 from the `tneb` prototype (`tneb.zip`, kept on disk untouched as the backup; its
contents are the first commit of this repo).

## What it is

A pixel-art ("Minecraft / Dangerous Dave") 3D map of India's electricity system, with
Tamil Nadu and Chennai in the most detail. It is the same family as
`maps.reclaimchennai.city/lighthouses`.

- **Every power station where it really is.** NPP positions are checked against the station's
  state, against copied points, and against OSM plant footprints and TN dossiers.
- **How much it generates.** Each station is a voxel pillar: shell height = installed
  capacity, bright core = yesterday's average output (CEA/NPP energy ÷ 24 h).
- **Tamil Nadu's grid live**, from the SLDC's instantaneous statement (re-issued a few times a day):
  - demand, frequency and the full source mix at the night minimum, morning peak and evening peak
  - central-station shares, open-access purchases, exchange imports and exports
- **Coal.** Stock days and % of normative, critical flags, receipt/consumption and mode
  (rail / rail-sea-rail), from the CEA daily coal report.
- **Smoke** from every burning station: square pixel puffs sized by output and blown by the live
  Open-Meteo wind at the site. Emissions per plant are CO2 from generation × emission factor
  (labelled estimate until the CEA CO2-database figure is joined).
- **Transmission.** OSM lines by voltage class (765 / HVDC / 400 / 230-220 / 110-132 kV, TN
  distribution), 1,872 TNGIS substations merged with OSM, and 12,807 OSM wind turbines in TN
  spinning at the statewide wind output and facing the live wind.
- **Close-up voxel models** (z ≥ 10.5) of each station archetype, animated by load
  (`web/js/models.js`), plus pixel scenes on every card (`web/js/scenes.js`).
- **History and time machine.** About 400 days of per-station daily generation from the CEA DGR
  archive:
  - a sparkline on every card
  - national daily generation by fuel, as small multiples
  - a slider (with play) that replays any past day across the whole fleet
- **Pylons and conductors** (z ≥ 12.8). Voxel lattice towers stand on every vertex of every line in
  view, plus one every 450 / 380 / 320 / 260 m by class. Conductors sag between the model's arm
  points; below z 15.2 only the top phase on each side is drawn.
- **Fuel supply chains** (`web/data/feed.json`):
  - mines, ports and terminals, gas fields and LNG, nuclear fuel
  - sea lanes, rail legs and pipelines drawn by mode, each with its own dash and icon
  - voxel coal ships, LNG tankers and trains moving at one simulated hour per second
  - opening a station lights up its own chain
- **Emissions per station** (`web/data/emissions.json`):
  - CEA CO2 Baseline DB v22 intensity and history
  - unit-wise FGD status and SO2 deadline, and the 2015 norms
  - SO2 measured in 2021 (obtained by RTI) against the limit
  - fly-ash generation and utilisation
  - nearby CAAQMS monitors and incidents
  - labelled run-rate estimates of CO2 / SO2 / NOx / PM
- **Tamil Nadu dossier** (`build/dossier/tn_plants.json`): 304 records covering units,
  commissioning, makes, fuel chain, water/cooling, structure (stacks, cooling towers),
  evacuation and history. Every NPP / DGR / CEA-coal spelling is kept as an alias. The card loads
  `web/data/dossier/<id>.json`.
- **Close-zoom context** (lazy below z 10): OSM solar arrays as 3D blocks (Kamuthi etc.) and OSM
  plant footprints.

## Layout

```
power-map-india/
├── scrapers/          live collectors (python, .venv)
│   ├── collect.py         one pass; each source on its own cadence (run by power-collect.timer)
│   ├── sldc_peakdet.py    TANTRANSCO SLDC peakdet.pdf -> sldc_versions/sldc_rows, PDF archived per issue
│   ├── npp_map.py         npp.gov.in gc-map XHR -> npp_stations (coords) + npp_station_daily
│   ├── npp_dgr.py         CEA DGR2 xls (daily, per station: gen, coal days, outages)
│   ├── backfill_dgr.py    DGR2 history backfill (python -m scrapers.backfill_dgr 400)
│   ├── cea_coal.py        CEA daily coal report pdf (per plant stock/receipt/consumption; header-driven, two 2026 layouts)
│   ├── backfill_coal.py   CEA daily coal pdf backfill, Jul 2024 on (one-off)
│   ├── cea_coal_hist.py   CEA daily coal xlsx/xls/pdf, Aug 2017 to Jun 2024 (one-off; sections normalised)
│   ├── coal_supply.py     table coal_supply (series, period, value, unit, source) + CIL daily production/offtake
│   │                      by company (APEX MOC dashboard, Oct 2023 on), National Coal Portal totals, NPP days buckets
│   ├── coal_msg.py        Ministry of Coal monthly statistics pdf, Apr 2021 on (production, dispatch by sector, rakes, lignite)
│   ├── cea_monthly.py     CEA monthly coal report per plant (NPP xls, Apr 2023 on) + imported coal for power (Jan 2024 on)
│   ├── cea_monthly_hist.py  the same from CEA's pdf archive, Apr 2014 to Mar 2023 (one-off)
│   ├── coal_rakes.py      coal trains loaded per day by CIL subsidiary (FOIS via CIL APEX, Playwright), Mar 2022 on
│   ├── ports_coal.py      coal through major / non-major ports, monthly (Ports ministry pdfs), 2016 on
│   ├── tradestat.py       coal imports by HS code, monthly (Commerce ministry TradeStat), 2017 on
│   ├── gas_power.py       gas burnt for power (PPAC, 2015 on) + CEA per-plant gas allotted vs consumed (2012 to May 2025)
│   ├── cwc_reservoirs.py  CWC weekly reservoir bulletins, per reservoir and region, 2015 on (hydro's fuel)
│   ├── gem_coal.py        Global Energy Monitor coal mine + terminal trackers (CC BY 4.0) -> build/feedstock/gem/
│   ├── weather.py         Open-Meteo current wind/cloud on a 0.5° grid of plant sites
│   ├── vidyut_pravah.py   demand met per 15-min block, India + every state (vidyutpravah.in)
│   ├── npp_merit.py       all-India demand + generation by source, ~4-min step (NPP merit chart; --back N backfills)
│   ├── nfms.py            hours of supply by feeder type, feeder integration, city SAIFI/SAIDI (NFMS, via page auth)
│   └── (prototype) res_generation.py, coal_india.py, npcil.py, tn_mix.py, tn_district.py
├── scripts/
│   ├── build_site.py      merge NPP + DGR + OSM + dossiers -> web/data/plants.json (+ build/build_notes.txt)
│   ├── build_grid.py      build/grid (OSM) -> web/data/grid/*.geojson + index.json manifest
│   ├── export_live.py     DB -> web/data/live/{now,tn_history,history,history_totals}.json (atomic)
│   ├── build_feed.py      build/feedstock -> web/data/feed.json (resolves research plant ids to site ids)
│   ├── build_emissions.py build/emissions/stations.json -> web/data/emissions.json (exact + state/first-word join)
│   ├── build_icons.py     web/icons.svg (pixelarticons + 16×16 ASCII-art fuel icons)
│   ├── export_coal.py     DB -> web/data/coal/coal.json (dashboard) + series.json (every supply series), atomic
│   ├── render_poster.py   web/posters/power_{india,tn}_en.png (+ _preview.jpg), 20×16.5 in @300 dpi
│   ├── render_coal_poster.py  web/posters/coal_india_en.png: supply-chain map, days of coal 2017-, mine to boiler
│   └── grid_*.py          (grid agent) Overpass extraction, TN official substations merge
├── build/             intermediates + research outputs (SCHEMA.md is the contract)
│   ├── dossier/           TN plant dossiers (units, fuel chain, water, structure, sources)
│   ├── grid/              OSM lines/substations/plants/turbines/towers, NOTES.md
│   ├── feedstock/         mines, ports, gas, nuclear fuel, plant->source links
│   └── emissions/         CEA CO2 database, FGD status, fly ash, CAAQMS, estimates
├── raw/               fetched sources (pages, pdf text); big binaries & OSM extracts gitignored
├── data/power.db      SQLite archive (not in git; published as a release asset, see data/README.md)
├── web/               the static site (any web server can serve this directory)
│   ├── index.html, css/style.css, icons.svg, fonts/ (Silkscreen digits, OFL)
│   ├── coal/              the Coal Tracker at /coal/ (index.html, coal.css, coal.js; reads data/coal/coal.json)
│   ├── js/app.js          map, panel, cards, live polling
│   ├── js/layer3d.js      three.js custom layer: pillars, smoke, models, turbines
│   ├── js/models.js       voxel archetypes (coal, gas, nuclear VVER/PHWR/FBR, hydro, wind, solar, pylon…)
│   ├── js/scenes.js       96×54 pixel scenes per archetype
│   ├── js/fuels.js        fuel colours/icons/labels, kV ramp
│   └── data/              plants.json, basemap.json, grid/, dossier/, live/ (live is gitignored)
├── deploy/power-collect.{service,timer}   systemd --user, every 15 min (:03/:18/:33/:48 UTC)
├── deploy/power-posters.{service,timer}   systemd --user, daily 13:00 UTC (18:30 IST)
├── tneb-dashboard-v0/ the prototype's Leaflet dashboard (parked)
└── docs/              prototype README + roadmap
```

## Running

```
.venv/bin/python -m scrapers.collect          # one pass (what the timer runs)
.venv/bin/python scripts/build_site.py        # after new dossiers / OSM plants
.venv/bin/python scripts/build_grid.py        # after a new OSM grid extraction
.venv/bin/python scripts/build_feed.py        # after feedstock research updates
.venv/bin/python scripts/build_emissions.py   # after emissions research updates (run build_site first)
.venv/bin/python scripts/export_live.py       # rewrite live JSON from the DB
systemctl --user status power-collect.timer
```
The venv is Python 3.11 on this host (the prototype's mac venv was 3.14; not reused).

## Hosting

- Any static file server works; the live site is served by Caddy with `web/` mounted read-only.
- Cache rules:
  - `/data/live/*` and `/data/coal/*` are `no-store`: rewritten every 15 minutes. `/coal/` is `no-cache` like `/`.
  - the rest of `/data/*` is 1 h with revalidation.
  - JS and CSS are 10 minutes. Modules import each other without `?v=`, so bump `?v=` in
    index.html and in the imports when they change.
- The page polls `data/live/now.json` every 5 minutes.

## Data decisions worth knowing

- **Station output is the previous day's average, not instantaneous.** Per-station
  instantaneous output isn't public. The TN statewide figures are instantaneous (the SLDC
  statement), and TN wind/solar/hydro models run at the statewide load factor.
- **SLDC statement parsing** (`sldc_peakdet.py`): the PDF is an Excel print whose columns
  drift, so values are assigned by role per row:
  - capacity is left of x=320
  - MU is the 3-decimal figure right of x=470
  - the MW figures between are Lighting / Minimum / Morning in order
  - a line labelled only "(ii)" is numbering, not a label
  - the CGS group total is the orphan numeric row inside the CGS block

  PDF times carry `+05'30'` and are converted to UTC. Every distinct issue is kept in
  `raw/sldc/archive/`, because SLDC keeps no history.
- **NPP positions are often wrong**: latitude digit slips (Ennore SCTPP 3.29°N, PFBR 2.55°N),
  stations copied onto a neighbour's point (Kudankulam = P.Nallur, NCTPS-1 = Vallur), and hydro
  stations dropped into the plains. `build_site.py` keeps a point only if:
  - it is inside or within 8 km of its state (state polygons: `raw/geo/india_states_polygons.geojson`,
    from ~/projects/nfhs)
  - it is not shared with a differently named station (the same complex may share: URI-I/II)
  - it agrees with the dossier

  Otherwise it takes the OSM plant position. Every decision is in `build/build_notes.txt`.
- **The NPP `genDate` parameter is ignored.** The map endpoints only ever return the latest
  day, so history comes from the dated DGR2 spreadsheets.
- **Fuel colours** are the dataviz reference dark slots, validated as a stacked set in the order
  coal · wind · gas · hydro · solar · nuclear · bio (CVD warn band). So every fuel also has its
  own pixel icon and label.
  - The national daily chart uses small multiples, not a stack: three warm hues (coal, gas,
    nuclear) fail adjacency in any order.
- **Lines "shimmer"** (stepped dash animation) to show energised circuits; the direction of flow
  is not published and the legend says so.

- **Positions in Tamil Nadu**: 96 exact, 83 approximate (wind belts, clusters). A station the
  dossier researched without finding a verifiable position is left off; NPP's point alone is not
  trusted (Narimanam sat at Neyveli). The 125 dossier records with no coordinates (all 94
  biomass/cogen, planned pumped storage, shelved projects) are not mapped. Their village names are
  in `build/dossier/NOTES.md` for geocoding later.
- **India-wide positions**: an NPP point is replaced by a same-named OSM plant in the same state when
  the two are more than 8 km apart. This caught Simhadri (611 km), Konaseema and Lower/Upper Sileru.
  Direction words (Upper/Lower/…) are ignored in the match; they had snapped Upper Indravati onto
  Upper Sileru.
- **Wind belts vs farms**: belt clusters carry the capacity (estimated from OSM turbine counts, and
  labelled). Named farms inside a belt have `part_of`, and the fleet totals skip them.
- **Privacy**: page mirrors in `raw/pages/*.html` and `raw/tn/html/` can contain officials' names
  and phone numbers. They are kept on disk as source backups but are gitignored and never served
  (only `web/` is public).

- **Feedstock findings** (`build/feedstock/NOTES.md`):
  - In CEA coal remarks, "LDG Port" is stock at the *loading* port (Paradip/Vizag/Dhamra) and "UL Port"
    the *unloading* port. CEA publishes no legend, so this is an interpretation, and the prototype's
    ROADMAP had it backwards.
  - TN coal: NCTPS/Vallur/Mettur burn MCL coal (Talcher/Ib) railed to Paradip and shipped to
    Kamarajar; Mettur is railed ~360 km on from the NCTPS yard. Tuticorin goes via VOC. NTPL burns
    NLC Talabira captive coal. ITPCL burns imported coal landed at Karaikal and railed ~133 km.
    No TN gas plant uses Ennore LNG (all are on GAIL's Cauvery-basin gas).
  - Udangudi and Ennore SEZ were planned around the undeveloped Chandrabila block, so those chains
    are marked PLANNED.
- **Emissions figures**: the SO2 headline is a sulphur mass balance. It agrees with CREA's satellite
  estimates better than the 2021 RTI stack readings, which imply 3–10× less and are kept as a lower
  bound. TN FY2025-26 estimates: CO2 67.6 Mt, SO2 ~553 kt, NOx ~115 kt, PM ~17 kt (NOx and PM are
  order-of-magnitude only).
- **All-India grid source**: Overpass timed out, so 34 states come from the Geofabrik India extract
  (2026-09-23, `raw/osm/`, 1.8 GB, gitignored), and TN/Arunachal from Overpass. Re-run order is in
  `build/grid/NOTES.md`. OSM renewables: 1,991 solar/wind/biomass plants were added with a 1.5 km
  duplicate check; capacity is area-estimated (~2 ha/MW) where untagged and flagged `cap_est`.

## Live sources added 2026-09-25

- **SLDC peakdet.pdf is issued about once a day, around noon IST**, not several times a day. For
  "now", `vidyut_pravah.py` scrapes Vidyut Pravah (Ministry of Power):
  - demand met in the current 15-minute block for TN and every state, plus exchange MW and price
  - TN and India on every pass (the TN page takes about 17 s server-side), all states hourly
  - `vp_blocks` builds up today's curve
- **NPP merit chart** (`gc-map-dashboard-meritchart`): `demandmet1chartdata` / `demandmet2chartdata`
  `?date=` give all-India demand and thermal/gas/nuclear/hydro/wind/solar generation at a ~4-minute step.
  History is available back to at least Sep 2025 (`python -m scrapers.npp_merit --back 400`). Table
  `merit_rt`; the panel's "India right now" mix and the poster use it.
- **NFMS** (nfms.powermin.gov.in, REC PDCL):
  - An Angular app; its API is `https://nfmsweb-prod-api.recpdcl.net/v11/`.
  - The Basic credentials visible in `main.js` get a 401; the app builds its header at runtime.
    `nfms.py` opens the public homepage in headless Chromium (Python playwright, the Chromium in
    `~/.cache/ms-playwright`) and reuses the Authorization header the page itself sends. Nothing is
    stored.
  - `Homepage` is national only, whatever state you ask for. `AvgPowerSupDur` and `FeederStatsV2` take
    state codes (from the site's `Search` list). `MajorCitiesMonthlyDaily` Monthly/ALL gives city
    SAIFI/SAIDI.
  - Tables `nfms_state`, `nfms_city`, `nfms_national`. Refreshes daily, scraped every 3 h.
- **Basemap**: CARTO's raster tiles (`light_all`/`dark_all`, which the MTC app uses) now carry an
  "API KEY REQUIRED" watermark. The map uses CARTO's key-free **vector** Positron / Dark Matter styles
  instead, vendored in `web/data/basemap/` with layer ids prefixed `p-` / `d-`, both drawn from one
  `carto` source and swapped by visibility. Glyphs come from CARTO's font server, so our own symbol
  layers use `Open Sans Regular`.
- **Posters** (`scripts/render_poster.py`), in the flights / boats house style, 20×16.5 in:
  - the map runs the full width: DataMeet's India drawn whole over Natural Earth neighbours
    (`raw/geo/ne_10m_admin_0_countries.geojson`, clipped and cached as `build/poster_countries_*.json`)
  - every station as an isometric voxel pillar, every mine / port / gas node as a pixel icon. One
    spatial index (`Index`) holds everything placed; crowded markers (Korba, Talcher, Singrauli) spiral
    out to the nearest free spot with a leader line and a dot at the true position. What still cannot
    fit is dropped and printed.
  - station labels: fuel icon + the full name without type suffixes (`clean_name`: TPS, STPS,
    Thermal Power Station...; same-town pairs become "Suratgarh" / "Suratgarh Super") + MW, wrapped,
    never truncated, bubble sized to the content
  - sea, air and CEA-derived coal links (`build/feedstock/derived_links.json`, poster only; the site's
    `feed.json` is unchanged) are curved and arrowed, with italic "From → To" labels
  - cards: two legends, installed capacity, generation now, supply to consumers; one stacked bar per
    card, no per-row bars
  - Every string goes through `Sheet.text`, which refuses an overlap, and cards fail the render if the
    content leaves the frame. Change layout numbers in points (`* pt`), never raw pixels: pixel offsets
    broke at other dpis. Text metrics differ slightly between 150 and 300 dpi, so render at 300 before
    committing a layout change.

## Coal Tracker (/coal/) and the coal poster, added 2026-09-30

- **The daily record** is CEA's Daily Coal Stock Report per plant, 3 Aug 2017 to today (2,900+ days; gap 9 Jan to
  24 Sep 2018 is missing on NPP). Before mid-2024 NPP has .xlsx, not .pdf, at the same path. Receipt exists from
  Sep 2021, consumption from Nov 2021; before that only stock and requirement.
- **Days of coal** on the page and poster = stock of the plants that state a requirement ÷ that daily requirement
  (@85% PLF): CEA's yardstick, the only measure comparable across the whole record. "Days left" per station =
  stock ÷ the last 7 days' burn.
- **Coverage break 14 Nov 2021**: CEA added ~27 plants (no-linkage, coal-block, imported-coal); totals step up.
  "Critical" meant <7 days (<4 pithead) before the Dec 2021 norms and <25% of normative stock after.
- **Typos in CEA's reports** (e.g. Thamminapatnam 27,728 kt on 2 Oct 2025) are kept out of totals: a row over 3 Mt
  and 4× its normative stock (`GOOD` in export_coal.py).
- **This financial year**: running total from the National Coal Portal (daily, all mines); the year-on-year from
  the Ministry of Coal's monthly statistics over the same completed months. coal.nic.in's production page
  (coal_india.py) is stale and no longer shown.
- **coal_supply** is one generic table for every upstream series (coal, gas, hydro): '<measure>:<entity>' names,
  period 'YYYY-MM-DD' or 'YYYY-MM'. export_coal.DERIVED picks and sums the ones the page draws.

## Gotchas

- Same three.js-in-MapLibre rules as lighthouses: world y is south, no negative scales, the scene
  is re-centred every frame.
- `models.js` is dynamically imported. If it fails, the map still runs with pillars only.
- Don't name a module-level helper `history` in app.js: it shadows `window.history`
  (`replaceState` broke the card).
- Server clock is UTC; the SLDC and the UI are IST.

## Source notes

- **TN SLDC statement** (`scrapers/sldc_peakdet.py`): tnebsldc.org sometimes refuses datacenter IPs.
  The fetch tries directly, then through an optional SOCKS5 proxy given in `POWERMAP_SOCKS5_URI`.
  The SLDC keeps no archive, so statements are saved at every re-issue; **TN source-mix history for
  2026-09-29..2026-10-12 was not captured** (TN demand for those days is still in `vp_blocks`).
- **NPP map feed** (`getAllZoneGen`) can stall for days (stuck on 2026-10-10 once). `export_live.plants_block`
  prefers CEA's DGR (`dgr_stations`, up to a day newer) per plant whenever it is newer than the NPP row.
- **Fetch resilience** (`scrapers/netfetch.py`): retries 429/5xx/connect errors with backoff, then one optional proxy attempt.
- **CEA monthly gas reports**: cea.nic.in was rebuilt in 2026 (WordPress archive gone), so that series ends
  2025-05. PPAC gas data still updates. Rebuilding it means scraping the new site's report pages.
