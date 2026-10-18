# ROADMAP — every energy asset in India, archived and live

## Phase 0 — done (this repo, v0.1)
- Coal stock scraper (CEA daily report): stocks, % normative, critical flags,
  receipts/consumption, coal-source remarks incl. port stock.
- Renewable generation scraper: state + station level wind/solar/RES (MU).
- TNEB SLDC peak demand scraper.
- 1,872-substation TN GeoJSON ingested and mapped.
- SQLite archive + FastAPI + live dashboard.

## Phase 1 — physical map of every asset (static archive)
Goal: one GeoJSON per asset class, all-India, TN/Chennai most detailed.

1. **Generation plants** (thermal, hydro, nuclear, solar, wind, biomass):
   - CEA installed-capacity reports + NPP gc-map-dashboard APIs (`npp.gov.in`
     Angular app — inspect XHR under DevTools; endpoints power the dashboards).
   - **OpenStreetMap** as the backbone for geometry: `power=plant`,
     `power=generator` (tags carry `plant:source=coal/solar/wind/hydro/...`,
     `plant:capacity:MW`). Overpass extract → reconcile with CEA/NPP by name.
   - Global sources for cross-check: Global Energy Monitor Global Coal Plant
     Tracker / Global Solar & Wind Power Trackers (CC-licensed datasets with
     coordinates), WRI Global Power Plant Database.
   - **energymap.in grid endpoints** — already 200 OK; probe their developer
     API for plant/line GeoJSON.
   - Nuclear: NPCIL plant list (Kudankulam, Kalpakkam incl. PFBR) — hand-verify.
2. **Substations**: TN done (1,872). Extend: OSM `power=substation` by voltage
   tag (33/110/230/400/765 kV), CEA transmission planning reports, state
   SLDC/GIS portals (TNGIS already mined; more layers flagged dead_backend —
   retry WFS periodically).
3. **Transmission lines**: hardest layer. OSM `power=line` with `voltage` tag;
   CEA/PGCIL 400/765 kV corridor maps (georeference the PDF maps); energymap.in.
   Chennai region first (highest density), then TN, then India.
4. **Coal logistics** ("source everything from coals"): CEA daily coal report
   remarks already encode supplying subsidiaries (BCCL/CCL/ECL...) and port
   stock (LDG = Kamarajar/Ennore, UL = V.O.C. port). Build a mines layer
   (Coal India mine locations, GMI/IBM data) + rail rake routes; link
   plant → mine/port → stock from the remarks column.
5. **Resource layers**: Solar DNI shapefile (`~/Downloads/solardni`) and the
   India PVOUT poster TIF (`~/Downloads/India_PVOUT_poster-map_*.tif`) →
   convert to raster tiles/vecor contours and serve as `/geo/*` overlays.
   Wind: NIWE wind atlas / NWPC data.

## Phase 2 — live operations (realtime-ish)
- 15-min SLDC regional data: POSOCO/Grid-India reports API, state SLDCs.
- NPP MERIT dashboards (`gc-map-dashboard`, `trans-map-dashboard`,
  `gc-map-dashboard-meritchart`) — drive their XHR endpoints directly.
- vidyutpravah.in state data (blocked from curl today; use browser session /
  Playwright fallback).
- Archive everything: this DB is append-only by date — it becomes the
  historical record (nothing public keeps long history).

## Phase 3 — 3D pixelated models ("as it is", from real images)
Inspired by reclaimchennai/lighthouses (Gaussian-splat scans in
`~/Desktop/projects/gpu/lighthouses` — pipeline: fetch_views.py → opensplat →
publish).

1. **Voxel/pixel style**: build low-poly + voxel-ised models of each asset
   class from satellite + ground imagery (thermal stacks with plume height,
   cooling towers, boiler houses; switchyard bays per voltage class; wind
   turbines scaled to hub height/rotor; solar array rows; hydro dam sections).
   One parametric model per archetype, parameters filled from real dims
   (capacity, stack height, tower count) — this is what makes "as it is".
2. **Photoreal upgrades** per site using the lighthouses pipeline
   (Mapillary/Google Street View scrubber + drone imagery → Gaussian splats)
   for flagship sites: North Chennai TPS, Mettur, Kudankulam, Muppandal wind
   farms, Kamuthi solar.
3. **Rendering**: MapLibre GL 3D terrain + custom layer (Three.js/deck.gl)
   or Godot/unity web export for the "walk the plant" archive view; models
   geolocated, click → live data from this dashboard's API (coal stock,
   generation today, substations on the feeder).

## Phase 4 — dashboards & archive UX
- Per-state pages (Tamil Nadu first, Chennai metro drill-down to feeder level).
- Time-machine slider over the archive (generation, coal stock, outages).
- Public API + downloadable snapshots (it's an archive, not just a dashboard).
