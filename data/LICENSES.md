# Licences and attribution

**Code** (`scrapers/`, `scripts/`, `api/`, `tools/`, `web/` code): MIT, see `../LICENSE`.

**Data.** Everything in `data/` is a compilation of public sources plus our own cleaning, position checks and
joins. Reuse is allowed under the terms of each underlying source; where we added value we release it as
CC BY 4.0, *except* the share-alike sources below, which keep their licence on anything derived from them.

| Source | What we took | Terms |
|---|---|---|
| Central Electricity Authority (CEA) | daily generation reports (DGR), daily/monthly coal stock and receipts, CO2 baseline database, FGD status, fly-ash, gas reports | Government of India publication; reuse with attribution (GODL-India) |
| National Power Portal (npp.gov.in) | station list, positions, daily generation, state capacity | Government of India open data (GODL-India) |
| MERIT India, Vidyut Pravah, NFMS (Ministry of Power) | real-time demand/generation, state supply data, feeder monitoring | Government of India open data |
| TN SLDC / TANTRANSCO / TNPGCL / TNPCB / CPCB | Tamil Nadu grid statements, substation lists, thermal unit data, monitors | Government publications; attribute the source |
| Central Water Commission | weekly reservoir bulletins | Government of India publication |
| Ministry of Coal / Coal India / PPAC / DGCIS tradestat / ports | coal production, offtake, rakes, imports, port throughput, gas consumption | Government of India publications |
| **OpenStreetMap** | transmission lines, substations, towers, wind turbines, solar arrays, plant footprints, mine pits (`data/geo/*grid*`, parts of mines) | **ODbL 1.0**, (c) OpenStreetMap contributors. Derived databases must stay ODbL and credit OSM. |
| **Global Energy Monitor** | Global Coal Mine Tracker, coal terminals (`gem_coal_*`) | **CC BY 4.0**, attribute Global Energy Monitor |
| **Wikipedia / Wikidata** | some descriptive text and facts in the TN dossier and supply-chain notes | **CC BY-SA 4.0** (Wikidata CC0) |
| Natural Earth, DataMeet | country / state outlines | Public domain / CC BY 4.0 |

Every record carries `sources` (URLs or file references) where the original is known. Mining or ownership
facts compiled from news or company pages are linked to their source in that field. We are not affiliated with
any of the publishing bodies. Data is provided as is; check the original before relying on a figure.
Estimates (for example per-plant emissions run-rates) are labelled `estimate` with a `method`.
