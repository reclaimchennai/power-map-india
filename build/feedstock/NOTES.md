# Feedstock and emissions datasets: notes

Built 2026-09-24. Nothing here is committed; the lead reviews and commits.

The contract is `build/SCHEMA.md` ("Feedstock / pollution"). Rules that apply throughout:
- Every record carries `sources` (a URL or a `file:` path under `raw/`).
- Unknown values are `null`.
- Estimates carry `"estimate": true` and a `"method"`.
- Coordinates carry `loc_precision`.

## Files and counts

| file | contents | count |
|---|---|---|
| `feedstock/mines.json` | coal/lignite coalfields, mines, captive blocks; company-level production (CIL subsidiaries, SCCL, captive, lignite companies) | 99 mines (17 coalfields, 45 mines, 21 captive blocks, 16 lignite), 21 companies; 92 with coordinates, 44 with production |
| `feedstock/ports.json` | Indian coal ports and terminals, foreign loading ports, TN plant-to-port map, approximate sea lanes | 15 ports (9 terminal points), 5 foreign ports, 18 TN plant mappings, 15 sea lanes |
| `feedstock/gas.json` | gas fields, processing terminals, LNG terminals, pipelines, TN gas-plant supply, CEA gas allotment table | 25 fields, 4 terminals, 9 LNG terminals, 31 pipelines (21 with LineString), 10 plant-supply records |
| `feedstock/nuclear_fuel.json` | uranium mines and mills, NFC, heavy-water plants, reprocessing, Kudankulam/MAPS/PFBR fuel chains | 32 nodes (20 with coordinates), 3 chains |
| `feedstock/links.json` | `links[plant_id]` = ordered chains (mine or field → rail → port → ship → port/berth → conveyor or rail → plant), each with node coordinates, leg geometry, share and sources; `plants[plant_id]` carries the water source | 188 nodes, 57 plants, 111 chains; all 35 TN thermal/gas/nuclear plants plus 20 of India's largest coal plants |
| `emissions/stations.json` | per station: CO2 (CEA DB v22), unit FGD status and deadlines, fly ash, 2015 norm per unit, TN CAAQMS, TN incidents, 2021 measured SO2, TN estimates | 277 stations (35 TN; 242 other coal/lignite/gas/oil/diesel) |
| `feedstock/_parsed/` | `coal_receipts_cea_monthly.json` (FY2025-26 and FY2026-27 YTD receipts by source, 190 plants); `cea_daily_coal_remarks_decoded.json`; `cea_daily_remarks_45d.json` | |
| `emissions/_parsed/` | `co2_baseline.json` (590 stations), `fgd_units.json` (600 units), `flyash.json`, `norms_2015.json`, `caaqms_tn.json` (40 stations), `incidents_tn.json` (16), `so2_measured_tn_2021.json` (41 units) | |

Rebuild scripts:
- `raw/feedstock/_scripts/` covers ports, stations, links and the parsers.
- `raw/feedstock/mines/build_mines.py` rebuilds mines.json.
- `raw/feedstock/gas/_build_gas_json.py` rebuilds gas.json.
- `raw/feedstock/nuclear/_build_nuclear_fuel_json.py` rebuilds nuclear_fuel.json.
- The builders for the `emissions/_parsed/` files sit in that folder.

Build order: parsers → `build_ports.py` → `build_stations.py` → `build_links.py`. links.json reads all the other files.

## Main sources

**Coal flows**
- CEA Fuel Management Division, via npp.gov.in: the daily coal stock report (PDF plus 39 daily XLS files, 2026-08-09 to 2026-09-22) and 16 monthly "Coal Statement" files (Apr-2025 to Jul-2026). The monthly files give each plant's receipts split by CIL / SCCL / captive / e-auction / import / others. **These splits are the basis for every `share` in links.json.**
- Ministry of Coal, *Integrated Coal Logistics Plan* (Jan 2024, `raw/feedstock/coal_logistics/`). It gives FY22 rail-sea-rail tonnages by plant and loading port (Paradip, Dhamra, Vizag), unloading ports (Ennore, Tuticorin, Krishnapatnam), and the linkages for NCTPS-III, Ennore SEZ and Udangudi.
- TNPGCL station pages (`raw/feedstock/tnpgcl/`): coal sources, conveyors, NCTPS wagon loaders feeding Mettur, and cooling water.
- IL&FS ITPCL investment teaser (Nov 2023): coal lands at Karaikal and is railed about 133 km; a captive jetty was 50% built; ITPCL holds an Upau (South Kalimantan) coal licence; wet-limestone FGD.
- CAG NLC audit (Report 35 of 2025): which Neyveli mine feeds which station.

**Ports and terminals**
- Global Energy Monitor wiki (GEM), CC BY 4.0: terminal pages for Kamarajar CB-1/2/3 and ECTPL, and VOC NCB-I. GEM started returning HTTP 403 partway through the run, so the Paradip, Vizag and Gangavaram terminal pages were not fetched.
- Wikipedia (CC BY-SA) and OSM (ODbL): port points, piers, railway-station nodes and plant polygons.

**Emissions**
- CEA CO2 Baseline Database **v22.0** (2026-08-01, FY2017-18 to FY2025-26).
- CEA unit-wise FGD sheet, **Nov 2023**. This is the latest unit-wise sheet; later ones return 404. The MoEFCC 11-Jul-2025 amendment sets category deadlines: A by 2027-12-31; B case by case; C exempt from SO2 limits if the stack-height rule is met by 2029-12-31.
- CEA fly-ash report **2021-22**, the latest with station-wise data; TN also has Apr–Sep 2022. The 2024-25 report publishes only state totals.
- MoEFCC S.O. 3305(E) of 2015, with NOx at 450 per G.S.R. 662(E) of 2020.
- CPCB/TNPCB CAAQMS station metadata.
- CREA & Poovulagin Nanbargal, *Emission Watch TN* (2021): RTI stack SO2 readings and the 2019 satellite SO2 hotspots.
- NITI/NEERI FGD study (2025): Indian coal sulphur below 0.5%.

**Licences.** Government of India publications (CEA, MoC, MoEFCC, CPCB, PNGRB, PPAC) are public and reusable with attribution. OSM is ODbL: attribute it and share derived geometry alike. Wikipedia is CC BY-SA. GEM is CC BY 4.0. The CREA report is reused with attribution. News and company pages are cited only for facts; the saved copies are for provenance, not redistribution.

## Findings and decisions

1. **"LDG Port" and "UL Port" in CEA daily remarks mean the loading port and the unloading port.** The brief read them as "LDG = Kamarajar/Ennore" and "UL = V.O.C.", but the data don't fit that:
   - Andhra Pradesh plants (Dr NTTPS, Rayalaseema) and ITPCL also carry LDG stocks.
   - ITPCL's 100 kt appears as LDG on one day and UL on another, so the labels are not always applied consistently.

   In `_parsed/cea_daily_coal_remarks_decoded.json` I decode LDG as coal waiting at the east-coast loading port (Paradip, Vizag, Dhamra, Haldia) and UL as coal at the destination port. Treat this as an interpretation: CEA publishes no legend.
2. **Tamil Nadu coal logistics** (the numbers are FY2025-26 CEA receipt shares):

   | Plants | Coal source | Route | Share |
   |---|---|---|---|
   | NCTPS I/II, Vallur | MCL Talcher / Ib Valley | railed to Paradip (plus Dhamra 1.3 Mt for Vallur), shipped to Kamarajar, then conveyor: CB-1 to NCTPS, CB-2 plus a 4.4 km pipe conveyor to Vallur | about 99% CIL |
   | Mettur I/II | MCL | same route to Kamarajar CB-1 and the NCTPS yard, then about 360 km by rail (Ennore–Arakkonam–Jolarpettai–Salem–Mettur Dam) | Mettur I 99.9% CIL; Mettur II 6.5% imported |
   | NCTPS-III (COD Jan-2026) | SCCL, by rail about 606 km; MMTC imports | via Kamarajar | FY2026-27 YTD: CIL 78%, SCCL 22% |
   | Tuticorin TPS | MCL | via Paradip and Vizag to VOC coal jetties | 100% CIL |
   | NTPL | NLC Talabira II & III captive coal | via Paradip to VOC NCB-I | 84.5% captive, 15.5% imported |
   | SEPC Stage-IV | imports | via VOC | 94.5% imported |
   | Mutiara | imports | via VOC | 74% imported |
   | ITPCL | Indonesian imports | via Karaikal, then rail | 100% imported |
   | OPG | imports | — | 60% imported |

   Udangudi (unit 1 synchronised) and Ennore SEZ (under construction) were planned around TANGEDCO's Chandrabila block. The block is undeveloped and a termination notice was reported, so those chains are labelled PLANNED and the block is drawn at the Talcher coalfield point as a placeholder. Udangudi has an SCCL bridge linkage.
3. **Lignite.**

   | Mine | Feeds |
   |---|---|
   | NLC Mine-I | NNTPS, TPS-I Expansion |
   | Mine-IA | TAQA (1.70 Mt in FY25); also NLC's own stations |
   | Mine-II | TPS-II, TPS-II Expansion |
   | Mine-III | planned |

   OSM's polygon labelled "Neyveli III" actually falls inside Mine-II (see `mines.json` geometry_note).
4. **Gas.**
   - Every TN gas plant is on GAIL's isolated Cauvery-basin network; none burns Ennore LNG yet.
   - Thirumakottai has been shut since Aug 2023, when its gas supply agreement lapsed.
   - PPN got no gas in May 2025.
   - Basin Bridge now runs on diesel (HSD), for emergencies only.
5. **Nuclear.**
   - **Kudankulam:** TVEL fuel from NCCP Novosibirsk, flown in. The Indian arrival airport is not published, so that leg is merged.
   - **MAPS:** unsafeguarded, so domestic uranium only: UCIL (Jaduguda, Turamdih, Tummalapalle) → NFC Hyderabad.
   - **PFBR:** MOX fuel from BARC Tarapur using plutonium from KARP (Kalpakkam) and PREFRE (Tarapur). First criticality 6-Apr-2026.
6. **Water.** Recorded for 20 TN plants:
   - NCTPS, Vallur, Tuticorin, NTPL, SEPC, ITPCL, Udangudi: seawater. Vallur uses seawater cooling towers.
   - Mettur: Cauvery river.
   - Nagai: treated municipal sewage and an air-cooled condenser.
   - Neyveli stations: NLC mine-seepage water (low confidence).
   - Kudankulam and MAPS: seawater.
   - PFBR: not confirmed.
7. **SO2 estimates.** The headline `so2_t_best` uses a sulphur mass balance: domestic coal 0.45% S, imports 0.6%, lignite 0.8%. At cluster level it matches CREA's 2019 satellite hotspot figures:

   | Cluster | This dataset (FY2025-26) | CREA 2019 |
   |---|---|---|
   | Neyveli | 239 kt | 299 kt |
   | Chennai | 124 kt | 142 kt |
   | Mettur | 55 kt | 47 kt |
   | Tuticorin | 116 kt | 52 kt |

   Tuticorin is higher mainly because SEPC was added in 2021. The RTI stack concentrations imply totals 3–10× lower, so that figure is kept only as a lower bound (`so2_t_from_measured_conc`). NOx (450 mg/Nm³ assumed; 250 for CFBC boilers) and PM (ESP mass balance) are order-of-magnitude figures.

   TN FY2025-26 estimates: **CO2 67.6 Mt** (from the CEA DB), **SO2 about 553 kt**, **NOx about 115 kt**, **PM about 17 kt**. `fy2026_27_run_rate` scales these by annualised DGR year-to-date generation (to 2026-09-22).
8. **The seed file `data/plants_tn_seed.csv` has wrong coordinates.** Kuttalam GT is placed at Courtallam (8.95, 77.32; the real site is 11.034, 79.586). PPN is placed near Gummidipoondi (real: 11.075, 79.832). SEPC is labelled Cuddalore (it is at Tuticorin, 8.756, 78.157). Every coordinate here comes from OSM polygons cross-checked against GEM, GEO or Wikipedia. Some coordinates in CEA's own fly-ash report are also wrong: SEPC is placed inland, and TAQA at Cuddalore town.

## Geometry caveats

- **Sea lanes:** hand-picked open-sea waypoints, densified along great circles (`geometry_precision: approximate_waypoints`, `estimate: true`). East-coast to Tuticorin traffic is routed round Sri Lanka, not through the Palk Strait.
- **Rail legs:** straight lines between real station nodes, not traced track. Some long hauls marked "schematic" skip intermediate stations: Raniganj–Haldia, SECL–Vizag, Gudur–Tuticorin, SECL–Tiroda.
- **Conveyors, MGR and in-port moves:** straight schematic lines. Every chain carries `estimate_geometry: true`.
- **Pipelines:** geometry is in gas.json. Traced from OSM where available; otherwise approximate waypoints or schematic straight segments, each labelled.

## Gaps

- No per-plant split between Talcher and Ib Valley coal, or between loading ports, for FY2025-26. Those chains carry `share: null` with a `share_group` holding the category total. Loading-port tonnage from the MoC plan is FY22.
- Nagai TPP has no verified coordinate. Its chain ends at Karaikal, which is itself an inferred unloading port. Unloading ports for OPG and Tulsyan are also inferred (Kamarajar); all three are marked low confidence.
- No coordinates for the VOC Coal Jetties I & II (TTPS), NCB-II or NCB-III; the port point is used instead.
- The FGD unit-wise status is from Nov 2023. Since then, TNPGCL put FGD tendering on hold (July 2025) and NTPL has an FGD project under way (BHEL packages); neither is reflected unit by unit.
- Fly ash for stations commissioned after 2021-22 is missing: NCTPS-III, SEPC, Udangudi.
- Outside TN, fly-ash, coal-receipt and OSM coordinate joins are fuzzy name matches, each flagged with a `match` or `loc_precision` note. 156 of 242 non-TN stations have coordinates.
- Missing locations: Chandrabila block; several UCIL mines and mills; the Hazira heavy-water plant; offshore gas fields (PY-1, KG-D6, KG-DWN-98/2). PPN's supplying field (HOEC PY-1) is offshore with no coordinate, so its chain has no geometry.
- GEM was blocked (HTTP 403) partway through, and Wikipedia rate-limited some queries.
- The TN water sources for NCTPS-III and PFBR are not published in the sources used.
