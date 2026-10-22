# Open data

Datasets behind <https://power.reclaimchennai.city>: India's power stations, the **coal supply chain**
(mines, rail, ports, imports, plant stock and receipts), gas, nuclear fuel, hydro, the Tamil Nadu grid and emissions.
Everything is open: see [LICENSES.md](LICENSES.md) for sources and terms. Column definitions: [DICTIONARY.md](DICTIONARY.md).
File list with row counts and SHA-256 checksums: [MANIFEST.csv](MANIFEST.csv).

## Formats

| Format | Where | Notes |
|---|---|---|
| **CSV** (`.csv`, or `.csv.gz` when over 5 MB) | `data/<theme>/` | UTF-8, header row, ISO dates. `pandas`/R read `.gz` directly. Nested values are JSON text in one cell. |
| **Parquet** (zstd) | next to every CSV | Typed, compact; use for `merit_rt`, `coal_plants_daily`, `dgr_stations`. |
| **GeoJSON** | `data/geo/geojson/` | EPSG:4326. Source of truth for geometry. |
| **GeoPackage** | `data/geo/power_map_india.gpkg` | All 21 layers in one file (QGIS, GeoPandas, ArcGIS). |
| **Shapefile** (zipped) | `data/geo/shapefile/` | One zip per layer, UTF-8, mixed layers split by geometry type. Field names are cut to 10 characters by the format, so prefer GeoPackage/GeoJSON for full names. |
| **SQLite** (everything in one DB) | [Release asset](https://github.com/reclaimchennai/power-map-india/releases) `power-map-india-sqlite.zip` | 26 tables, 300 MB unzipped. Too large for git. |
| Raw coal reports | Release asset `coal-source-reports.zip` | 484 CEA / Ministry PDFs and 73 XLS the coal tables were parsed from (254 MB). |
| Original nested JSON | `data/*/*_full.json`, `stations/tn_plants_dossier.json` | Lossless versions with `sources` per record. |

```python
import pandas as pd
coal = pd.read_csv("data/coal/coal_plants_daily.csv.gz", parse_dates=["date"])   # daily plant coal stock, 2017-08 -> now
stations = pd.read_parquet("data/stations/plants_master.parquet")
import geopandas as gpd
lines = gpd.read_file("data/geo/power_map_india.gpkg", layer="grid_lines_400")
```

## Themes

| Folder | Contents | Coverage |
|---|---|---|
| `coal/` | **Plant stock and receipts**: `coal_plants_daily` (CEA daily stock, days of cover, receipt, consumption, critical flag), `coal_plants_monthly` (receipts by CIL / SCCL / captive / e-auction / import), `coal_import_power_monthly`. **Supply chain**: `coal_supply` (393 series: production, offtake, despatch, rakes, port coal, imports in tonnes and USD), `mines` + `coal_companies`, `gem_coal_mines`/`gem_coal_terminals` (Global Energy Monitor), `ports`, `foreign_loading_ports`, `sea_lanes`, `plant_source_links` (mine to rail to port to plant, per plant), `cea_receipts_*`, `supply_chain_nodes/routes` | daily 2017-08 → now; monthly 2014-04 → 2026-08; series from 2012 |
| `gas/` | `gas_plants_monthly/annual` (CEA, to 2025-05), `gas_fields`, `lng_terminals`, `gas_pipelines`, `gas_processing_terminals`, `gas_plant_supply` | 2012 → 2025-05 (CEA); assets current |
| `nuclear/` | fuel chain nodes and chains per plant (heavy water, uranium, safeguards) | current |
| `stations/` | `plants_master` (2,666 stations, positions checked against OSM), `npp_stations`, `npcil_units`, Tamil Nadu dossier (304 plants: units, makes, cooling, stacks, history) | current |
| `generation/` | `dgr_stations` (per-station daily), `npp_station_daily`, `npp_state_daily`, `merit_rt` (national MW by source, near-real-time), `merit_state_daily`, `res_stations_daily` | DGR 2025-08 → now; MERIT 2025-09 → now |
| `hydro/` | `cwc_reservoir_weekly` (179 reservoirs) | 2015-04 → now |
| `tn_grid/` | TN SLDC statements (`sldc_versions`, `sldc_rows`), TN generation mix, districts, 15-min `vp_blocks`, official EHV substations | statements saved from 2026-09 (not 2026-09-29..10-12) |
| `emissions/` | CEA CO2 baseline, FGD status per unit, fly ash, CAAQMS monitors, incidents, 2015 norms, SO2 measured (RTI), per-station run-rate estimates (labelled estimates) | FY2025 baselines |
| `power_quality/` | NFMS hours of supply and SAIFI/SAIDI | recent |
| `geo/` | transmission lines by voltage (110/220/400/765 kV, HVDC), substations, towers, wind turbines, solar arrays, plant footprints (OSM, ODbL); stations, supply-chain nodes and routes, coal mines, GEM mines/terminals | 2026-09 OSM extract |

## Refreshing

The collector runs every 15 minutes on the live site (`scrapers/collect.py`) into SQLite (`data/power.db`, not in git).
`python tools/export_open_data.py` and `python tools/export_geo.py` regenerate every file here from it. Snapshot date of the tables in this folder: **2026-10-22**.

**Daily updates.** [`latest/`](latest/README.md) holds plain CSVs of the series that move every day (national coal stock and days of coal,
coal trains per day, production and offtake per day, every monthly supply series, reservoir storage), committed daily. The full tables
and the SQLite database are replaced daily on the [`data-latest` release](https://github.com/reclaimchennai/power-map-india/releases/tag/data-latest)
(`power-map-india-tables.zip`, `power-map-india-sqlite.zip`), so they do not pile up in git history. `tools/publish_daily.sh` does both.

## Known gaps

- Tamil Nadu SLDC statements for 2026-09-29 to 2026-10-12 were not captured (the SLDC keeps no archive).
- CEA monthly gas reports end 2025-05 (the CEA site was rebuilt).
- NPP map feed history starts 2026-09; DGR per-station history starts 2025-08.
- Positions of some older stations come from NPP and were corrected against OSM; each record's `q` field says how.
