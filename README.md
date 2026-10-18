# Power Map of India

Open data and code behind **<https://power.reclaimchennai.city>**, a pixel-art 3D map of India's electricity
system with Tamil Nadu and Chennai in most detail: every power station, the coal / gas / nuclear fuel supply
chains that feed them, the transmission grid, live Tamil Nadu demand and emissions.

Made by [Reclaim Chennai](https://reclaimchennai.city). Researchers: the datasets are in **[`data/`](data/README.md)**
in CSV, Parquet, GeoJSON, GeoPackage, Shapefile and SQLite, with licences and a data dictionary.

## What's here

| Path | |
|---|---|
| [`data/`](data/README.md) | **Open datasets**: coal supply chain, stations, generation, gas, nuclear, hydro, TN grid, emissions, GIS layers |
| `web/` | Frontend: static site (MapLibre GL + three.js), voxel models, Coal Tracker at `/coal/` |
| `scrapers/`, `store.py` | Backend collectors (CEA, NPP, MERIT, SLDC, Vidyut Pravah, CWC, PPAC, ports...) writing to SQLite |
| `scripts/`, `api/` | Build scripts (site, grid, feedstock, emissions, posters) and a small FastAPI service |
| `build/` | Research intermediates with `sources` per record (dossier, feedstock, grid, emissions); contract in `build/SCHEMA.md` |
| `tools/` | Regenerate `data/` from the database |
| `docs/ARCHITECTURE.md` | How it all fits together |

## Run it

```bash
python -m venv .venv && .venv/bin/pip install -r requirements.txt
.venv/bin/python -m scrapers.collect         # one collection pass -> data/power.db and web/data/live/*.json
python -m http.server -d web 8000            # open http://localhost:8000
```
Large inputs (OSM extracts, raw reports) are not in git: see the release assets and `scripts/grid_*.py` for re-extraction.

## Using the data

Cite as in [`CITATION.cff`](CITATION.cff) and credit the original publishers ([`data/LICENSES.md`](data/LICENSES.md)):
CEA, NPP, MERIT, CWC, Coal India, PPAC and others (Government of India publications); OpenStreetMap (ODbL);
Global Energy Monitor (CC BY 4.0). Code is MIT. Corrections and requests: open an issue.
