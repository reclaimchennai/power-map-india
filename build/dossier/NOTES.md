# Tamil Nadu generation dossier — notes

`tn_plants.json` has **304 plant records** in the `build/SCHEMA.md` format. It was compiled on 2026-09-24.
- **Coordinates:** 179 records have them, and 96 of those are `loc_quality: "exact"`. Exact means two sources agree within about 1 km, or the point was checked against an OSM polygon, generator or chimney.
- **Unknown values are `null`.** Estimates carry `"estimate": true` and `"method"`; only the wind-belt capacities are estimates.

**Extra fields beyond the schema:**
- On records: `cluster` (wind belts / offshore zone), `estimate`, `method`, `part_of` (a named ISTS wind farm pointing to its belt), `bbox`, `loc_note`, `unit_conflict`, `cea_re_name` and `programme*`.
- On units: per-unit `lat`/`lon`, `first_criticality`, `grid_sync`, `construction_start` and `note` (Kudankulam, for example).

## How it was built
Four research streams were merged by `parts/merge.py`, which uses `parts/idmap.json` for the cross-part id mapping. `parts/finalize.py` then does the clean-up and sorting.
- **Priority order:** part_tnpgcl > part_tngecl > part_other > part_pdf. A lower-priority part only fills fields that are null; aliases and sources are unioned.
- **The scripts still contain absolute scratchpad paths.** Change the `SP` variable before re-running them.

| part | scope | main sources |
|---|---|---|
| `part_tnpgcl.json` (20) | TNPGCL coal/gas stations, projects, JV stations (Vallur, NTPL), retired Ennore TPS and Narimanam | tnpgcl.org station and project pages, **TNPGCL Data Card 2025-26** (installed capacity as on 01.04.2026, `raw/tn/pdf/tnpgcl_datacard_2025-26.txt`), MoEF EC PDFs, Wikipedia, OSM, CEA monthly coal report Jul-2026 |
| `part_tngecl.json` (70) | all 47 hydro stations, Kundah PSP, Kollimalai, 15 new PSHEPs, TNGECL legacy wind | tngecl.org, Data Card 2025-26, archived TANGEDCO circle pages, DRIP ESDD/ESMP dam reports, GEO, OSM, CEA PSP status Feb-2026 |
| `part_other.json` (109) | nuclear, NLCIL, IPPs, captive plants, major solar, wind belts, ISTS wind, BESS, offshore | NPCIL/BHAVINI/NLCIL pages, Wikipedia, data card IPP/LTOA/MTOA tables, TNPCB thermal list, CEA RE/coal reports, OSM (turbine counts, polygons), IWTMA |
| `part_pdf.json` (224 raw → 105 unique kept) | "Database on Energy Resources in Tamil Nadu" (ENVIS/DoE, 2020, 174 pp.) | `raw/downloads/tn_energy_database.pdf`; text is in `raw/tn/pdf/tn_energy_database.txt` |

Every fetched page and PDF is saved under `raw/tn/`:
- `html/`: TNPGCL and TNGECL crawls, `wiki/`, `geo/`, `other/`, and Wayback copies of TANGEDCO pages.
- `pdf/`: 96+ TNPGCL/TNGECL PDFs, including EC compliance reports and the DRIP dam reports.
- OSM pulls: `osm_power_plants_tn.json`, `osm_chimneys_ct_tn.json`, `osm_nctps_area.json`, plus hydro, dam and mine pulls.

## Counts by type and status

| type | status | records | MW | with coords | exact |
|---|---|---|---|---|---|
| nuclear | operating | 2 | 2440 | 2 | 2 |
| nuclear | under_construction | 1 | 500 | 1 | 1 |
| nuclear | planned | 1 | 1200 | 1 | 0 |
| coal | operating | 23 | 12130 | 21 | 20 |
| coal | under_construction | 2 | 2640 | 2 | 2 |
| coal | planned | 7 | 15680 | 3 | 0 |
| coal | retired | 2 | 610 | 2 | 1 |
| coal | unknown (null) | 2 | 200 | 2 | 2 |
| lignite | operating | 5 | 3640 | 5 | 5 |
| lignite | retired | 1 | 600 | 1 | 0 |
| gas | operating | 9 | 839.5 | 7 | 6 |
| gas | mothballed | 2 | 438.4 | 2 | 2 |
| gas | retired | 1 | 10 | 0 | 0 |
| gas | unknown (null) | 2 | 110.8 | 2 | 1 |
| diesel | operating (captive) | 3 | 12.6 | 0 | 0 |
| diesel | retired | 1 | 196 | 1 | 0 |
| diesel | unknown (null) | 2 | 211.7 | 2 | 1 |
| hydro | operating | 46 | 1925.9 | 42 | 30 |
| hydro | under_construction | 1 | 20 | 0 | 0 |
| pumped_storage | operating | 1 | 400 | 1 | 1 |
| pumped_storage | under_construction | 1 | 500 | 1 | 0 |
| pumped_storage | planned | 15 | 15500 | 8 | 0 |
| wind | operating | 19 | 13137* | 17 | 0 |
| wind | mothballed / retired | 5 | 1.1 | 5 | 0 |
| wind | planned | 2 | 4034.8 | 1 | 0 |
| solar | operating | 40 | 3354.3 | 38 | 22 |
| battery | under_construction / planned | 13 | n/a (MWh programme) | 12 | 0 |
| biomass | operating | 61 | 280.1 | 0 | 0 |
| cogen | operating | 33 | 359.7 | 0 | 0 |
| waste | operating | 1 | 0.2 | 0 | 0 |

\* **Wind double-counting.** The wind total double-counts: 10 belt clusters (11,354 MW, estimated from OSM turbine counts) plus 9 named ISTS/NLC farms that sit inside those belts. Sum only `cluster: true` records, or use `part_of` to de-duplicate.

**Hydro check.** The 46 operating hydro stations plus Kadamparai total **2325.90 MW**. That matches Data Card 2025-26 and the SLDC peakdet figure exactly.

## Key decisions and contradictions (lead / TNPGCL part)
- **NPP station coordinates are unreliable.** More than 30 NPP points were wrong; station ids and names are still correct. Where NPP was wrong, the record uses OSM generator or polygon positions and names the rejected NPP value in `sources`. Examples:
  - Hydro: Kundah II-V, Lower Mettur II-IV and Kodayar-II are 100-380 km off in the plains.
  - `VALLUR TPP` duplicates NCTPS-I's point.
  - `NTPL TUTICORIN TPP` sits at Udangudi.
  - `KOVIKALPAL CCPP` is 170 km off.
  - `KUTTALAM CCPP` sits on the PPN site.
  - `P.NALLUR CCPP` sits on Kudankulam.
  - `B. BRIDGE DG` sits at Mettur.
  - `BHAVINI PFBR` has latitude 2.55 and `ENNORE SCTPP` has latitude 3.29 (13.29 with a digit dropped).
- **NCTPS I, II and III are separate records.** Each is placed from OSM generator nodes and the named buildings "NCTPS-1" and "NCTPS-2"; Stage III is placed from its chimney and its 400 kV substation.
  - DGR used a combined `NORTH CHENNAI TPS` (1830 MW) row until Nov 2025. That alias is on both nctps-1 and nctps-2, and the notes explain how to split it.
  - NCTPS-III COD was declared 24.01.2026 (Data Card). The TNPGCL project page also says it was "synchronized 08.12.2025" after its trial run.
- **The TNPGCL website has copy errors:**
  - The NCTPS-II technical block repeats the Stage-I 210 MW data.
  - The VGTPS Phase-II page duplicates Phase I, so the Phase II 92.2 MW GT/ST split is unknown.
  - The MTPS-I page has no technical data.
- **NCTPS-II commissioning dates:** the TNPGCL site gives U1 20.03.2014 and U2 08.05.2014. The 2020 ENVIS PDF gives U1 30.06.2013 and U2 17.12.2012. The TNPGCL dates are used.
- **TTPS units 4 and 5:** first-sync dates run in reverse (U4 11.02.1992, U5 31.03.1991). The unit records use the regular-generation months (U4 Jan-1994, U5 Mar-1995).
- **Capacities that disagree:**
  - Valuthur: 187.2 MW (Data Card) vs 186.2 MW (NPP/DGR).
  - Kuttalam: 101 MW (TNPGCL) vs 100 MW (DGR).
  - Basin Bridge: TNPGCL calls it combined cycle, but CEA and Wikipedia list it as open-cycle naphtha GTs. It now runs as synchronous condensers.
- **Thirumakottai (Kovilkalappal) is `mothballed`.** It has been shut since 01.08.2023, when the GAIL gas supply agreement expired, and is excluded from installed capacity.
- **Narimanam GPS (10 MW naphtha, 1991-92) is `retired`.** This is inferred: it is absent from the 2020 and 2026 capacity lists, and no decommissioning date was found.
- **Uppur 2x800 MW is `planned`, meaning on hold.** Work was suspended in 2021 by an NGT order and the project is shelved. GO(Ms) 45 of 14.03.2026 moves its materials to a new 1x800 MW unit at Udangudi, which has its own record.
- **ETPS Expansion (1x660) is `planned`.** Two EPC contracts were terminated, the 275 m chimney shell is built, and it is to be completed under PPP/DBFOO.
- **Other projects:**
  - The 2020 PDF's separate "Ennore Replacement TPP 660 MW" was dropped as a duplicate or superseded concept.
  - Cheyyur UMPP (4000), Kadaladi (4000) and ITPCL Phase II (3x660) are kept as `planned` with **null coordinates** and a "treat as shelved" note.
  - Udangudi Stage II/III have null coordinates because land acquisition is still under way.
- **Udangudi Stage I** is 2x660 MW, BHEL, 95.6% complete, with a fresh EC dated 02.03.2026. Its fuel mix changed to 50:50 imported/domestic (SCCL bridge linkage), 5.89 MTPA. It uses cooling towers with seawater make-up and one 275 m twin-flue stack. DGR already carries `UDANGUDI TPP` with 0 MW.
- **Ennore SEZ** is 2x660 MW (EC originally for 2x800), about 74% complete, with target U1 31.08.2026 and U2 30.09.2026. It is being built on the NCTPS-I ash dyke.
- **NTPL's coal is now captive.** CEA Jul-2026 lists all receipts as "Captive", which is NLC's Talabira mines in Odisha. The other TNPGCL coal plants take CIL/MCL coal by rail to Paradip, then ship to Ennore or Tuticorin.

## Contradictions from the other parts (summaries; full detail below)
- **Hydro:**
  - Moyar is 40 MW after RMU (the 2023-24 data card and the website say 36).
  - Periyar is 168 MW (other sources give 126, 140, 154 or 161).
  - Sholayar I is 84 MW; the 2020 PDF gives 70.
  - The DGR names `BHAWANI KATTAL` / `BHAWANI BARRAGE-II HPS` / `BHAWANI BARRAGE-III HPS` are Bhavani **Kattalai** barrages I/II/III (30 MW each). They are *not* the 2x5 MW Bhavani Barrage 1/2 PHs.
  - `SHOLAYAR HPS (TN)` has PH-I's 84 MW but NPP places it at PH-II.
- **Aliyar PSHEP:** 1800 MW (Data Card 2025-26) vs 700 (website). **Vellimalai:** 1000 vs 1100.
- **Mutiara / Coastal Energen / Moxie Power** are the same plant (1 record).
- **Ind-Barath Tuticorin (IBTPL 2x150)** now sells as "Orissa Alloy Steel". **SEPC** = NPP "TUTICORIN TPP ST-IV".
- **Valantharavai** has two adjacent plants, Penna (52.8 MW) and Arkay (150 MW). Mapping NPP `VALANTARVY CCPP` to Penna is an inference.
- **Some CEA "Tamil Nadu" RE rows are really in Karnataka or AP** (GADAG_*, HIRIYUR_*, KURNOOL_*, probably HIRITUR OSTRO). They were excluded.
- **2020 PDF district totals for wind (7642 MW) and solar (1100 MW, end-2018)** are stale and partial. They were dropped in favour of the wind belts and named solar farms. The 2018 table is still in `data/power.db` table `tn_district`.
- **Duplicate rows in the 2020 bagasse table** (Sakthi Erode, Rajshree Villupuram, EID Parry Cuddalore/Trichy, Thiru Arooran Thanjavur) are kept as separate `-2` records with a note. They may be real second plants or double entries. Astro Energy and Prathyusha appeared in both the biomass and bagasse tables and were merged into the biomass record.

## Still unknown / gaps
- **Coordinates:**
  - All 61 biomass and 33 cogen/captive records from the 2020 PDF have none (village names are in `history` / `notes_tngecl` for future geocoding).
  - Also missing: Poonachi, Periyar-Vaigai mini II-IV, Kollimalai, 7 PSHEPs, NLC Onamakulam/Poolangal solar, the Mytrah 250 and JSW Renew Two 130 wind farms, and the Thappagundu BESS.
- **Status null (unknown):** Samalpatti DG, Samayanallur DG, Penna, Arkay, Sai Regency, Karuppur (Lanco Tanjore), IBPGL, MALCO and Kamachi. All show zero generation or zero capacity in DGR, or have no current source.
- **Structure:** stack heights are known only where a source states them (NCTPS I/II 275 m, Udangudi, Ennore SEZ and ETPS-Exp 275 m). There are no stack or cooling-tower counts for private coal plants beyond OSM, and FGD status for most plants is unknown. Ash-pond polygons exist only for ETPS, TTPS (assumed) and Neyveli.
- **Solar:** the ~10 GW of small solar is not represented plant by plant. Only 40 major farms (≈3.35 GW) are. A density layer from OSM solar polygons is recommended.
- **Other gaps:**
  - Per-site MW/MWh of the TNGECL BESS programmes.
  - Per-site capacity of the legacy TNEB demonstration wind farms.
  - The Phase II split at Valuthur.
  - Unit commissioning dates for several mini hydro stations.
- **Not recorded** (no location or current source): small captive plants such as India Cements, Dalmia, Coromandel Electric, Sri Andal and Jeppiaar; and the Hinduja Cuddalore and Chettinad Power proposals.
- **gem.wiki now returns 403.** GEM data could not be used for unit or coordinate cross-checks this round.

## Privacy
- No personal names, phone numbers or e-mails of officials are included in the dataset.
- A TANGEDCO contact PDF was deleted from `raw/`. One archived TEDA page (`raw/tn/html/wayback_teda_bio.html`) and several EC PDFs contain officials' names and contacts. They are kept only as raw source copies and must not be surfaced.

---

# Appendix: part_tngecl notes
## TNGECL part: hydro, pumped storage and legacy wind

Output: `part_tngecl.json` has 70 records, built by `build_tngecl.py` in the scratchpad.
- **47 operating hydro stations** (46 hydro + Kadamparai pumped storage), totalling **2325.90 MW**. This matches the Data Card 2025-26 total (installed capacity as on 01.04.2026) exactly.
- **2 under construction:** Kundah PSP (4x125 MW) and Kollimalai HEP (1x20 MW).
- **15 planned pumped-storage projects** (15,500 MW in total).
- **6 wind records:**
  - 5 legacy TNEB/TNGECL demonstration wind-farm sites.
  - 1 planned 34.75 MW wind-solar hybrid repowering project.
- **No solar, biomass or cogen records:**
  - TNGECL owns no ground-mounted solar. Its only solar item is a tendered 15 MW solar + 15 MW/45 MWh BESS project, BOO, location unknown.
  - Biomass and cogen plants are private or cooperative, not TNGECL-owned. The sibling `part_pdf.json` already has 61 biomass and 36 cogen records, so I did not add them again. The location hints listed below can help geocode those records.

### Sources used
- **TNGECL site.** Crawled pages are in `raw/tn/html/www.tngecl.org__*`.
  - All pages are static Django-CMS HTML. There are no JSON or tab endpoints, and nothing is loaded dynamically.
  - The hydro-stations page lists the 47 stations by circle with unit count and MW:
    - Kundah circle: 833.65 MW
    - Kadamparai circle: 609.45 MW
    - Erode circle: 503.5 MW
    - Tirunelveli circle: 375.3 MW
  - The hydro-projects page lists Kundah PSP, Kollimalai and 15 PSHEPs.
  - The wind, solar and biomass pages give statewide totals only:
    - Wind: 11,361.855 MW (9,331.365 MW STU-connected + 2,030.49 MW CTU-connected).
    - Solar: 10,159.61 MW.
    - Biomass: 206.79 MW.
    - The Generation page gives slightly different totals: wind 11,398.31, solar 10,655.95, cogen 684.4, hydro 2,323.90.
- **Data Card 2025-26** (TNPGCL copy, `datacard.pdf`, hydro on PDF p7-8, projects on p11-12). This is the authoritative capacity list. The TNGECL copy of the data card is the **2023-24** vintage (as on 01.04.2024). It shows hydro at 2321.90 MW and Moyar at 36 MW; Moyar was uprated to 40 MW after RMU in Dec 2024 and Nov 2025.
- **Old TANGEDCO circle pages** (2011-12, Wayback, saved as `raw/tn/html/wayback_tangedco_hydro*.html`). These give unit-wise commissioning dates, elevations, source reservoirs and heads for almost every station.
- **DRIP ESDD/ESMP PDFs** (`raw/tn/pdf/www.tngecl.org__*drip*`, `*linkpdf*`, `*media*`). These give dam coordinates, heights and lengths, and state which powerhouse each dam feeds. They also settled several identifications:
  - Avalanche feeds PH-V.
  - Kundah PH-I is at Kundah Palam.
  - Kodayar Dam-II receives PH-I tail water.
  - The Pykara, Mukurthi and Maravakandy micro PHs sit at their dam toes.
- **GEO (globalenergyobservatory.org).** 26 TN hydro pages are saved in `raw/tn/html/geo/`. They supply coordinates and turbine/generator makes (used as `units[].make`).
- **OSM Overpass.** Saved as:
  - `raw/tn/osm_power_plants_tn.json`: power=plant plus hydro/nuclear generators, 446 elements.
  - `raw/tn/osm_hydro_related_tn.json`: substations, penstocks and PH buildings.
  - `raw/tn/osm_dams_reservoirs_tn.json`
- **CEA PSP status, Feb 2026** (`raw/tn/pdf/cea_psp_status_2026-02.pdf`).
- **Wikipedia TNGECL page** (`raw/tn/html/wikipedia_TNGECL.html`), used for PSHEP unit configurations and costs.

### Coordinates
- **31 records are `exact`.** Each has either a named OSM plant polygon or node plus a matching OSM switchyard or substation, or two sources (OSM, GEO or NPP) within about 1 km.
- **For the unnamed OSM hydro polygons**, identities were assigned by proximity, DRIP text, and satellite imagery in some cases:
  - Kundah-V: way 1470127962. A penstock and a GEO point coincide with it.
  - Sholayar-II: way 1468881078.
  - Sathanur: way 995868195.
  - Aliyar mini: way 1468881080.
  - Bhavani Barrage 1/2: ways 1468887801 and 1470127960. Imagery shows a barrage with a powerhouse at each site, but which one is PH-1 and which is PH-2 is inferred.
  - Kodayar-I: way 1431930232.
  - PVSHEP-I: way 1468094721.
- **Dam-toe micro and mini PHs** without their own map feature are placed on the dam and marked `approx`: Pykara micro, Mukurthy, Thirumurthy, Amaravathi, Perunchani and LBRBC.
- **Null coordinates:** Poonachi mini PH, PVSHEP II-IV, Kollimalai HEP, and 6 PSHEPs (Upper Bhavani, Sigur, Vellimalai, Sillahalla I/II, Palar-Poranthalar, Athur).
- **The other 9 PSHEPs** are placed on the existing reservoir they are named after. They are marked `approx` and the location note says so.

#### NPP station_details coordinates are unreliable for hydro
Of 27 hydro stations with an NPP coordinate:
- **Only 5 are within 0.5 km:** Kundah-VI, PUSHEP, Sarkarpathy, Bhavani Kattalai-I and Suruliyar.
- **These are 100-380 km off**, in the plains: Kundah II-V, Lower Mettur II-IV and Kodayar-II.
- **Pykara** is placed at Pykara dam, 8 km from the Singara PH.
- **Periyar** is placed at the forebay dam, 3.4 km from the PH.
- **BHAWANI BARRAGE-III HPS** duplicates the Bhavani Kattalai-I point.
- **SHOLAYAR HPS (TN)** carries PH-I's 84 MW but PH-II's location.

The `npp_station_id` and `dgr_name` links are still correct.

### Name mapping (DGR/NPP to station)
- `BHAWANI KATTAL` = Bhavani Kattalai Barrage PH-I (Samayasangili)
- `BHAWANI BARRAGE-II HPS` = Bhavani Kattalai Barrage PH-II (Vendipalayam)
- `BHAWANI BARRAGE-III HPS` = Bhavani Kattalai Barrage PH-III (Cholasiramani)

These are **not** the 2x5 MW "Bhavani Barrage 1/2" PHs near Mettupalayam, which have no DGR entry.

Other mappings:
- `PARSON`S VALLEY HPS` = Kundah PH-VI
- `SHOLAYAR HPS (TN)` = Sholayar PH-I. PH-II (25 MW) has no DGR row.
- `PYKARA ULTMATE HPS` = PUSHEP
- `KADAMPARI HPS` = Kadamparai

DGR covers only 30 hydro rows (units of 25 MW and above, plus Kundah PSP). SLDC peakdet gives hydro only as the aggregate "a) Hydro 2325.9", so `sldc_item` is null on every record.

### Contradictions
- **Moyar:** 36 MW (website, DC 2023-24) vs 40 MW (DC 2025-26, after RMU). Used 40 MW. NPP lists 12 MW and DGR lists 40 MW.
- **Periyar:** 168 MW (DC, DGR) vs NPP 126 MW, OSM 161 MW, GEO 140 MW, and the 2012 page "2x35 + 2x42". Used 168 MW (4x42 after uprating).
- **Pykara:** 59.2 MW vs NPP 70.2 MW. 70.2 MW is the pre-2004 figure; the 11 MW unit 4 was removed in 2004.
- **Sholayar PH-I:** 2x35 MW (2011 page) vs 2x42 MW (DC). Uprated.
- **Pykara micro:** 1x2 MW (DC) vs 2x1 MW (2011 page).
- **Bhavani Kattalai-II commissioning:** Jul/Sep 2011 (TANGEDCO page) vs 2013 (GEO).
- **Kodayar PH-I location:**
  - GEO and OSM "KODAYAR-I&II" put it on Kodayar Dam-II.
  - The DRIP text (Dam-II receives PH-I tail water) implies it lies upstream, below Upper Kodayar dam.
  - I used the unnamed OSM plant below Upper Kodayar dam and marked it `approx`.
- **Aliyar PSHEP:** 1800 MW (DC 2025-26) vs 700 MW (website, Wikipedia).
- **Vellimalai PSHEP:** 1000 MW (DC 2025-26) vs 1100 MW (website, Wikipedia).
- **Kollimalai:** the website says 200 MW; the DC says 1x20 MW. Probably a website typo.
- **Kundah PSP cost:** Rs 1831 cr (2019), 3,522 cr (DC 2023-24), 3,926 cr (DC 2025-26); press reports Rs 18,085 cr, which looks wrong or like a different scope.
  - CEA expects commissioning in Sept 2026.
  - NPP/DGR already show a programme for it but zero actual generation.
- **Wrong DRIP dam coordinates:**
  - Pillur dam: 76°41'E given, actual about 76°48'.
  - Periyar forebay dam: 77°36'57"E given, actual about 77°12'53".
  - Servalar dam: 77°08'10"E given, actual about 77°18'.
- **District errors on the old pages:** the 2012 TANGEDCO page puts PVSHEP I/II in "Kanyakumari district"; they are in Theni.
- **Legacy wind totals:** 19.355 MW / 120 WEGs (TANGEDCO NCES PDF), 17.55 MW / 111 WEGs (TEDA 2011), and 17.355 MW / 110 WEGs (2025 press). Only 15 WEGs are operational.

### Still unknown
- Coordinates of the Poonachi mini PH. The TANGEDCO schematic puts it near Aliyar/Kadamparai.
- Coordinates of PVSHEP II-IV. A tender notice places PVSHEP-III at Vettukadu, Theni.
- Coordinates of the Kollimalai project at Puliancholai village.
- The Kundah PSP underground PH site. It is placed at Emerald village.
- Coordinates of most PSHEP sites.
- Unit commissioning dates for Bhavani Kattalai-III, Bhavani Barrage 1/2, PVSHEP III/IV, and the individual PUSHEP units (only 06.09.2005 is known).
- Per-site capacity of the legacy wind farms, and which turbines survive.
- Dam height and length for most non-DRIP dams.
- Hydro evacuation voltages. Only those visible on OSM substations were recorded.

### Hints for sibling biomass/cogen records (saved raw lists)
- `raw/tn/pdf/wayback_tangedco_cogen.pdf` has 29 bagasse cogen plants (659.4 MW) with village names. Examples:
  - MRK Co-op Sugar Mills, Senthiathope
  - Cheyyar Co-op
  - Rajashree Sugars, Vaigai Dam
  - Kothari Sugars, Kattur/Lalgudi and Sathamangalam/Ariyalur
  - Dharani Sugars, Karaipoondi/Polur and Kalayanallur/Tirukoilur
  - EID Parry at Nellikuppam, Aranthangi, Pugalur and Pettavaithalai
  - Sakthi Sugars at Padamathur, Appakudal and Poondurai-Semur
  - Bannari Amman at Alathukombai and Kolundampattu
  - Terra Energy at Thirumandangudi and A.Chittoor
  - Ambika Sugars, Pennadam
  - Dhanalakshmi Srinivasan, Udumbiam
  - Empee Sugars, Iddaikal
  - Madras Sugars, Vengur
  - Ponni Sugars, Odapalli
  - S.V. Sugar, Palayaseevaram
  - Arunachala Sugars, Melapambadi
  - Subramania Siva Co-op, Gopalapuram
  - Auro Energy, Kottur
- `raw/tn/pdf/wayback_tangedco_biomass.pdf` has 24 biomass plants (177.4 MW) with villages and fuel type.
- `raw/tn/html/wayback_teda_bio.html` has 18 biomass plants with commissioning dates. That page contains personal phone numbers and emails, so do not copy them into any output.
- The DGR TN list has no biomass or cogen stations.

### Not included, and possibly relevant to the lead
In Oct 2025 TNERC approved 375 MW / 1500 MWh of standalone BESS at 7 substations: Palladam, Tiruvarur, Karamadai, Pudukkottai, Thatchankurichi, Thappagundu and Anaikadavu. The source is the DownToEarth article. Per-site sizes are unknown.

# Appendix: part_other notes
## Notes for part_other.json (fork #4: nuclear, NLCIL, private/captive, major solar, wind clusters, ISTS RE, BESS, offshore)

Builder: `scratchpad/build_other.py` (rerunnable; it reads `wind_belts.json` + `build/grid/substations.geojson`).
109 records: 40 solar, 20 wind (10 geographic belt clusters, 8 ISTS farms, NLC 51 MW, offshore zone), 16 coal, 13 battery (sites), 7 gas, 6 lignite, 4 nuclear, 3 diesel.
Out of scope, left to other workers: TNPGCL own stations, Vallur NTECL, NTPL, Ennore, Narimanam, Kovilkalappal, Kuttalam, Valuthur, Basin Bridge GT, and hydro.

### New raw files saved
- `raw/tn/osm_power_plants_tn.json`: Overpass power=plant for TN, from the kumi.systems mirror (the main overpass-api.de returns 406 here). Also `raw/tn/osm_mines_tn.json`.
- `raw/tn/html/wiki/*.wikitext|html`: Kudankulam, MAPS, PFBR, Neyveli TPS, NLC India, Kamuthi, Muppandal, Cuddalore IL&FS, Aralvaimozhi and Kalpakkam. Also `wikidata_osm_plants.json` (Wikidata P625 coordinates for the OSM-linked plants).
- `raw/tn/html/nlcindia_renewableprojects.html`: NLC's site-by-site solar and wind list.
- `raw/tn/html/other/*`: JSW Tuticorin wind, Mercom and offshorewind.biz (offshore), Mercom, ESS News and BlackRidge (BESS), IndianKanoon (Penna Electricity SC judgment), NTPC REL Ettayapuram, pv-magazine and Mercom (NLC solar), PRNewswire (Orange), GEO pages 5242/5243 (Samalpatti/Samayanallur coordinates), WNN and NewsMill (KKNPP-3), and the Wikipedia GMR Vasavi page.
- `raw/tn/pdf/cea_list_power_stations_2021.pdf`, `cea_List_of_Power_Stations_31.03.2022.pdf` (+ .txt): unit-wise capacity and year of commissioning for every utility plant in TN.
- `raw/tn/pdf/iwtma_*.pdf`: IWTMA wind profile (2019 data) and the 2026 IWTMA TN report (repowering belts).
- `raw/tn/pdf/mnre_plantwise_RE_2020_p783-1173.pdf`: MNRE plant-wise RE list. This is a partial chunk only: TN wind rows 5370-9279, 2008-2017. It was not used for totals.
- `raw/tn/photon_geocode_cache.json`: Photon (OSM) geocoder cache. Nominatim is rate-limited from this IP.

### Coordinates: NPP points rejected (NPP `station_details` is unreliable for these)
| NPP name | NPP point | Problem | Used |
|---|---|---|---|
| P.NALLUR CCPP | 8.169,77.713 | Kudankulam site | OSM PPN polygon 11.0743,79.8333 |
| NEYVELI TPS-II | 11.592,79.450 | near NNTPS, 3.8 km off | OSM 7 generators 11.5586,79.4407 |
| NEYVELI TPS-II EXP | 11.593,79.476 | TPS-I Exp area | OSM generators 11.5476,79.4432 |
| NEYVELI ( EXT) TPS | 11.593,79.448 | 2.2 km W | OSM generators 11.5926,79.4676 |
| NEYVELI NEW TPP | 11.549,79.501 | 6 km SE | OSM generators 11.5901,79.4533 |
| MADRAS A.P.S. | 12.556,80.154 | 2.4 km W, inland | OSM generators and Wikipedia 12.5577,80.1755 |
| BHAVINI PFBR | 2.5531,80.1734 | latitude typo | OSM node and Wikipedia 12.5530,80.1737 |
| TUTICORIN TPP ST-IV (SEPC) | 8.45,78.10 | placeholder in the sea | OSM 'SEPC' polygon 8.7555,78.1576 |
| MUTHIARA TPP | 8.943,78.180 | 5 km NE | GEM exact, Wikidata and OSM 8.9143,78.1446 |
| KARUPPUR CCPP | 11.771,77.848 | near Mettur | OSM, Wikidata and GEM 11.1216,79.5288 (Thanjavur dist.) |
| VALANTARVY CCPP | 11.120,79.818 | Mayiladuthurai dist. | OSM 9.3279,78.9214 (Ramanathapuram) |
| B. BRIDGE DG (GMR Vasavi) | 11.787,77.883 | near Mettur | Wikipedia 13.0983,80.2702 (approx) |
| SAMALPATTI DG | 13.025,80.263 | Chennai office | GEO 12.2995,78.4038 + unnamed OSM polygon 12.2870,78.4085 |
| TCP Limited | 13.038,80.264 | Chennai office | OSM 'TCPL' 13.3835,80.1131 |
| Tulsyan NEC / Nagai TPP | none | no coordinates | OSM named polygons |

Also noticed (lead's scope): the NPP point for KUTTALAM CCPP (11.0751,79.848) is actually the PPN site. OSM puts Kuttalam GTPS at 11.0338,79.5861.
NPP points I accepted (agree with OSM or Wikidata within 1 km): Kudankulam, TAQA/NEYVELI TPS(Z), ITPCL (1.1 km), OPG and Samayanallur (agrees with GEO).

### Contradictions and identity resolutions
- **TUTICORIN (P) TPP**: this is Ind-Barath Thermal Power (IBTPL, 2x150, 2013). In 2026 the TNPDCL data card lists it as "Orissa Alloy Steel Pvt Ltd, Thoothukudi 2x150" under MTOA. CEA shows zero coal receipts in FY25-26 and CIL coal in FY26-27, so it restarted in 2026. A second, separate Ind-Barath plant, **IBPGL** (3x63 MW, Keelavelayuthapuram, TNPCB + OSM), has unknown status.
- **Coastal Energen / Moxie**: the data card lists both "Coastal Energen 2x600 (LTOA 558 MW)" and "Moxie Power Generation 2x600 (MTOA 558 MW from 01.04.2026)". Both are the same Mutiara/Melamaruthur plant, transferred to Moxie after NCLT (GEM). They form one record.
- **OPG Gummidipoondi capacity** differs across sources: DGR/CEA 414 MW; data card LTOA 1x77+1x81+1x80+1x180 = 418; TNPCB and data card MTOA 2x81+1x80+1x180 = 422. The units array follows LTOA.
- **Valantharavai** has two adjacent gas plants:
  - (a) NPP "VALANTARVY CCPP" / CEA "Pioneer Power Ltd", 38+14.8 MW (2005/06). I identified it as **Penna Electricity**: the Supreme Court judgment gives the same site and dates. This is an inference.
  - (b) **Arkay Energy (Rameswarm)** Wärtsilä gas engines, 150 MW per GEM/OSM, not in any CEA or TNPDCL list.
  - DGR 2026 shows VALANTARVY at 0 MW.
- **Sai Regency (KSK) 58 MW CCPP**: the OSM polygon sits 3 km NW of Valuthur GTPS. It is not in CEA 2022 or DGR, so status is unknown (`status: null`).
- **Karuppur CCPP (Lanco Tanjore, ex-Aban Power)** is 0 MW in DGR 2026, but GEM says operating. Status left null.
- **PPN (P.NALLUR CCPP)**: DGR shows 330.5 MW entirely on outage and SLDC shows 0 MW, yet the PPA runs to 2031. I set status `mothballed`; this is inferred from the outage.
- **Samalpatti DG / Samayanallur DG**: still listed in DGR at ~106 MW each with zero generation. Status left null (idle).
- **GMR Vasavi (B. BRIDGE DG)**: 196 vs 200 MW (4x50 per Wikipedia). Decommissioned 2018. Its Wikipedia coordinates duplicate those of the Basin Bridge GTPS next door.
- **MAPS**: unit 1 is under long-term suspension (npcil_units 0 MW, Wikipedia "operation suspended"), but DGR still counts 440 MW with a 220 MW outage. Unit 1 is marked `mothballed`.
- **PFBR**: first criticality 6 Apr 2026 (Wikipedia). DGR (Sep 2026) lists 0 MW capacity with programme generation only, i.e. not yet commercial. Status is `under_construction`.
- **KKNPP**: units 3-6 are under construction. Unit 3 reached "spill to open reactor" in Apr 2026 and awaits first criticality. OSM has all six reactor buildings (refs U1-U6); their coordinates are stored per unit.
- **Neyveli TPS-II EXP unit 1**: CEA commissioning year is 2012 (synchronisation). The commercial date was later (~2015).
- **Kamuthi**: the OSM relation centroid is 1.8 km from the Wikidata point. Both lie inside the site, so it is marked exact.

### Alias and join notes
- DGR names are copied verbatim, including double spaces ("MADRAS  A.P.S.") and the trailing space in "BHAVINI PFBR " (NPP).
- `tn_generation_mix` parse issues:
  - PPN is stored as item '2 Independent Power Plant' (330.5): the "(i) PPN" row merged with its heading.
  - "Neyveli TS2 Exp" (244.6 MW share) and "Kudankulam 1 & 2" are truncated or missing.
  - I used the peakdet labels in `sldc_item` (e.g. 'Kudankulam 1 &' as stored). Both spellings are in `aliases`.
- CEA ISGS RE-report codes are in `cea_re_name` (extra field): GREEN INFRA, MYTRA, ORANGE, TUTICORINJSWRENEWW, JSW RENEW ENERGY TWO LTD, KARUR_*, GRT, NTPC ETTAYAPURAM SOLAR PLANT, PGLR_SREPL.
- **res_stations_daily rows tagged "Tamil Nadu" that are physically outside TN** (the state column looks like the beneficiary or reporting state): GADAG_RSPPL_W, GADAG_GREENINFRA_W, GADAG_SERENTICA3_W, HIRIYUR_ZREPL_W (Karnataka) and KURNOOL_AMGREEN_W (Andhra Pradesh). HIRITUR OSTRO (300 MW) is probably Hiriyur, Karnataka. No records were made for these. VIVID SOLAIRE (BEETAM) 220 MW wind: location unknown, no record.

### Wind method
- The TN wind fleet has no per-farm public register. I built 10 geographic "belt" clusters (`cluster: true`) from the 12,807 OSM wind turbines (`build/grid/tn_wind_turbines.geojson`). Each point is the median turbine position, `bbox` is the 5-95 percentile extent, and `structure.turbines` is the turbine count.
- Capacity is an estimate (`estimate: true`): count x 0.887 MW, where 0.887 = the TNGECL statewide 11,361.855 MW (STU 9,331.365 + CTU 2,030.49) divided by 12,807 OSM turbines. Belt estimates sum to 11,354 MW.
- The uniform rating over-states old belts (Muppandal/Aralvaimozhi: many 55-600 kW machines) and under-states new ones.
- OSM coverage looks thin in Theni (466 turbines vs 534.7 MW in 2019) and the Dindigul/Palani area.
- District figures from Table 44 of the TN Env Dept database (~2018-19, total 7,642 MW) are attached as `district_capacity_table44`:
  - Tirunelveli 3,700 (includes present-day Tenkasi), Tiruppur 2,264.98, Theni 534.7, Dindigul 420, Coimbatore 355.25, Thoothukudi 245.97, Kanyakumari 118.81, Ramanathapuram 2.15, Chennai 0.22.
- ISTS/SECI wind farms are separate records with `part_of` pointing to their belt. Do **not** sum them with the belt estimates.
- Muppandal: Wikipedia/OSM quote "1,500 MW". It is an alias of the Muppandal belt, not a separate record.

### Solar
- TN solar is ~10-13 GW, mostly small and rooftop:
  - TNGECL page: 10,159.61 MW (9,006.27 MW STU + 150 MW CTU + 1,003.34 MW rooftop).
  - Data card at 01.04.2026: 13,414.62 MW (11,849.72 MW STU + 1,564.90 MW rooftop) + 150 MW CTU.
  - SLDC peakdet: 14,369.03 MW.
- Only these are recorded:
  - Kamuthi.
  - All 16 NLCIL sites (130 + 10 + 10 + 50 at Neyveli, plus the 13-site 500 MW and 709 MW TANGEDCO programmes).
  - NTPC Ettayapuram 230, Sprng Pugalur 300 (ISTS), GRT 150 (ISTS) and SPIC floating 25.3.
  - 19 OSM-named farms of at least 10 MW (operators unknown).
- Table 45 district solar (2019, total ~1.3 GW) is obsolete and was not used for clusters. `build/grid/tn_solar_arrays.geojson` (476 OSM arrays) is the better base for a solar density layer.
- NLC site locations are village-level approximations: several villages don't geocode. Onamakulam (Thoothukudi) and Poolangal (Virudhunagar) have `lat/lon: null`.

### BESS
TNGECL has two standalone programmes, all at TANTRANSCO substations. The per-site MW split is not published, so `capacity_mw` is null and programme totals are in extra fields.
- 500 MW / 1,000 MWh, TNERC-approved, under construction: Thennampatti, Anuppankulam, Ottapidaram, Vellalaviduthi, Kayathar, Karaikudi.
- 375 MW / 1,500 MWh, tendered Nov 2025: Palladam, Pudukkottai, Thatchankurichi, Thiruvarur, Karamadai, Thappagundu, Anaikadavu.
- Points come from the OSM substation layer. Thappagundu was not found, so its coordinates are null.

### Offshore
- One symbolic record for the Gulf of Mannar zone (4 GW seabed-lease RfS, Feb 2024, sub-blocks 2/3/4/7, plus a 500 MW VGF tender). Both tenders were cancelled in Aug 2025.
- Status is `planned` and the point is symbolic. Block polygons were not collected (NIWE/MNRE maps would give them).

### Not found / still unknown
- Not included:
  - Hinduja Cuddalore (a cancelled proposal) and Chettinad Power: no current source.
  - "NCTPS JV": nothing beyond NTECL Vallur (lead's scope).
- Small captives from the data card and TNPCB not recorded because their location is unknown: Jeppiaar Power 30 MW (Thiruvenkaranai, Kancheepuram), India Cements 48 MW, Dalmia Cement 27 MW, Coromandel Electric 26.19 MW gas, Sri Andal Paper 14.75 MW.
- Small captives not recorded because they are small: Saheli Exports 8.81, MMS Steel & Power (~6-9 MW), Kaveri Gas Power 6.79 and Terra Energy cogen 18.68 (Keerambur).
- Operating status unknown for: MALCO Energy Mettur 130 MW, Kamachi Gummidipoondi 70 MW, IBPGL 189 MW, Sai Regency 58 MW and Arkay 150 MW.
- Mytrah 250 MW and JSW Renew Energy Two 130 MW ISTS wind: district not verified (coordinates null).
- Stack heights, FGD status of private coal plants, ash-pond locations (except NLC), Nagai Power commissioning year, the Mine-IA polygon, and PPA/fuel details for the gas IPPs.
- GEM wiki (gem.wiki) returns 403 now. Earlier-saved GEM pages in `raw/feedstock/gem` and `raw/feedstock/gas` were used where available.
- No personal names or phone numbers are included in any record.

# Appendix: part_pdf notes
## tn_energy_database.pdf — extraction notes

The file is "Database on Energy Resources in Tamil Nadu" from the ENVIS Centre, Dept. of Environment, GoTN. It has 174 pages and was created on 2020-03-17.
- **Vintage:** mostly "Source: TANGEDCO, 2020", "NPCIL, 2020" and "MNRE Biomass Portal, 2020". The wind and solar district totals are for the end of 2018. The co-gen sales table is "as on 29.05.2018". The generation series run from 2007-08 to 2016-17.
- **Text layer:** present on every content page. Pages 160–173 have no text; they are scanned images of the TN Solar Energy Policy 2019 (Annexure III), not plant data. Page 175 is blank.
- **Full layout text:** `raw/tn/pdf/tn_energy_database.txt`. Pages are separated by form feeds, so PDF page N = split('\f')[N-1].
- **Coordinates:** the PDF has none. Its location maps (Figs 3, 4, 5, 8, 11, 20, 25, 26) are images with no grid or numbers. Every record has lat/lon = null.

### Page index (PDF page numbers, not printed page numbers)
| PDF p. | Content |
|---|---|
| 3–10 | contents, list of tables/figures, abbreviations |
| 23–25 | coal: ETPS / MTPS / NCTPS / TTPS text; **Table 1** (TANGEDCO coal units + COD dates), p25 |
| 27 | **Table 2**: ongoing TANGEDCO thermal projects (Ennore Exp, Ennore SEZ, NCTPS-III, Uppur, Ennore Replacement, Udangudi I–III, Cheyyur UMPP, Kadaladi); Ind-Barath Power Gencom text |
| 28–29 | IBTPL, Mutiara (Coastal Energen), ITPCL, NTPL text; NTPL unit table and PPA shares |
| 30 | **Table 3**: private coal (IBPGL, IBTPL, Mutiara, NTPL, ITPCL); NLC TPS-I and TPS-II text |
| 31–32 | NLC TPS-I Exp and TPS-II Exp text; **Table 4** (NLC lignite units); **Table 5** (TAQA) |
| 35–37 | gas text; **Table 6** TANGEDCO GTPS (p36); PPN, Lanco Tanjore, Arkay text |
| 39 | **Table 7**: private gas (PPN, Lanco Tanjore/ABAN, Arkay/PENNA) |
| 43–44 | list of hydro circles and powerhouses; Kundah PSP / Sillahalla text; **Table 8** ongoing hydro (Kollimalai 20, Kundah PSP 500, Sillahalla I and II 1000 each) |
| 46–48 | **Table 9**: Kundah circle (12 powerhouses: source, location, elevation in ft, units, COD per unit) |
| 49–50 | **Table 10**: Kadamparai circle (9) |
| 51–53 | **Table 11**: Erode circle (11) |
| 53–55 | **Table 12**: Tirunelveli circle (11) |
| 58–59 | **Tables 13–15**: MAPS units, KKNPP 1–2, new nuclear (PFBR, KKNPP 3–6, FBR 4–5) |
| 63 | Kamuthi 648 MW (figure caption only) |
| 65–66 | Table 17: TEDA small SPV installations (kW-scale rooftop at colleges and firms). **Not extracted**: none is a power plant |
| 76 | Table 20: wind passes and districts |
| 78 | Table 22: statewide wind capacity and generation by year up to 2015-16 (no per-farm data) |
| 81–84 | Table 23: NIWE wind-monitoring **masts** (95 sites; station, district, mast height, MAWS/MAWPD). Not plants, so not extracted |
| 85 | **Table 24**: captive / co-gen plants at 33 kV and below (10 plants) |
| 91 | **Table 27**: biomass co-gen plants by district (28 plants, 164.6 MW) |
| 92 | **Table 28**: bagasse co-gen plants (29 rows, 306 MW) |
| 93 | **Table 29**: co-gen plants selling to TANGEDCO (CPCL 129.9 naphtha; K16 SIPCOT Gummidipoondi 33.7 waste heat; JSW Steel Salem 60 coal; TNPL Mondipatti 30 coal) |
| 96, 99–100 | **Table 30**: biogas plants connected to TANGEDCO (4); **Table 31**: 30 other biogas plants (MW-equivalent) |
| 104 | Table 33: TN allocation from central stations |
| 107–109 | Tables 35–39: district-wise coal/gas generation 2007–17; private gas; captive gas/oil |
| 110–111 | Tables 40–41: nuclear by state and district, generation |
| 113–116 | **Table 43**: hydro powerhouse district, year of operation, and generation (MU) 2007–17 |
| 117–118 | **Table 44**: wind MW by district (9 districts, 7642.09); **Table 45**: solar MW by district (20 districts, 1100.41); Table 46: biogas |
| 123–124 | Table 50: existing vs planned capacity; **Table 51**: upcoming thermal, hydro and nuclear projects (same as Tables 2, 8 and 15) |

### What went into part_pdf.json (224 records)
Counts by type: biomass 61 (28 MNRE biomass co-gen, 3 biogas to TANGEDCO, 30 "other biogas"), hydro 45, cogen 36 (29 bagasse, 5 waste-heat/lignite captive, CPCL naphtha, K16 SIPCOT), coal 24 (6 TANGEDCO incl. retired ETPS, 11 planned TANGEDCO, 5 private/JV, ITPCL Ph-II planned, JSW Salem, TNPL), solar 21 (20 district clusters and Kamuthi), gas 10 (5 TANGEDCO incl. VGTPS I and II split, 3 IPP, 2 captive), wind 9 (district clusters), lignite 6, nuclear 4 (MAPS, KKNPP with units 3–6 as planned units, PFBR, FBR 4–5), pumped_storage 4 (Kadamparai, Kundah PSP, Sillahalla I and II), diesel 3 (captive), waste 1 (Koyambedu).

How the records were built:
- Cluster records carry `"cluster": true`. Their ids end in `-2018` because the district totals date from 2018.
- Hydro records carry per-unit COD from Tables 9–12. The powerhouse elevation (ft) and the source dam/reservoir are in `history` and `water.source`.
- `operator` for existing hydro is "TANGEDCO (now TNGECL)", because the PDF predates the TNGECL split.

### Contradictions and anomalies
1. **Periyar PH:** PDF gives 2x35 + 2x42 = 154 MW. DGR/NPP give 168 MW and NPP 126 MW, which suggests an uprating to 4x42. The unit list marks U1 and U2 as 42 MW.
2. **Pykara PH:** PDF says "7 units" but lists 3x7 + 1x11 + 2x13.6 = 59.2 MW, and dates only for U1, 2, 3, 5, 6, 7. U4 is missing, which suggests a retired unit. I inferred which rating goes with which unit number from the COD years.
3. **Sholayar:** PDF gives PH-I 2x35 = 70 and PH-II 25. DGR "SHOLAYAR HPS (TN)" is 84 MW (possibly PH-I uprated to 2x42). Check against TNGECL.
4. **Moyar:** PDF 3x12 = 36 MW; DGR 40 MW, NPP 12 MW.
5. **Kundah 1–4 districts:** Table 9 places PH-3 and PH-4 in Coimbatore district. PH-4 is at Pillur/Parali. **Kadamparai:** Table 10 says Coimbatore, Table 43 says Tiruppur. **Amaravathi:** PDF says Coimbatore; the dam is in present Tiruppur district.
6. **Bhavani barrages:** the circle tables list only Bhavani Kattalai Barrage I (2006, 2x15) and II (2011, 2x15). Table 43 also lists "Bhavani Kattalai PH-3" (2013) and "Bhavani Barrage 2 PH" (2012) without capacity. I added both with capacity null. NPP/DGR list BHAWANI KATTAL, BHAWANI BARRAGE-II and BHAWANI BARRAGE-III at 30 MW each, so reconcile with TNGECL.
7. **Periyar Vaigai minis:** Table 12 has Mini I (4 MW) and Mini II (2.5 MW). Table 43 says "Micro I, II and III". I added Mini III with capacity null.
8. **Hydro total:** operating hydro plus Kadamparai with capacity here sums to 2237.4 MW. Table 50 says 2307.9 MW and SLDC now 2325.9. The ~70 MW gap is roughly the capacity-less barrage PHs and the Periyar/Sholayar uprates.
9. **KGTPS:** Table 6 gives 101 MW / 2003; Table 36 gives 101 MW / 2004. DGR gives 100 MW.
10. **VGTPS Phase II:** 92.2 MW in Table 6 vs 92 in Table 36. DGR has Valuthur combined at 186.2, so VGTPS I may now be counted at 94.
11. **NCTPS-II:** Table 1 prints Unit I COD 30.06.2013 and Unit II 17.12.2012, so unit 2 comes first.
12. **Mettur TPS-I Unit II date:** printed as "01.12..1987" (typo); read as 1987-12-01.
13. **NLC TPS-II unit years** in Table 4 (1978/1986/1993) are sanction years, not CODs. The text says the first unit synchronised in March 1986 and the last in June 1993.
14. **NLC TPS-I:** the PDF (2020) says it is kept in service until NNTPS is commissioned. I set status "operating" per the PDF, but it is now decommissioned, so override from NLC/NPP. NNTPS is marked under_construction per the PDF; it is now operating.
15. **KKNPP 3–6:** the PDF only says "approved"; I set them to planned. PFBR: the PDF lists it as "MAPS Unit-3, NPCIL", but it is actually BHAVINI.
16. **Loyal Textile Mills:** Table 24 says Thoothukudi district; Table 39 says Viruthunagar.
17. **Duplicates across tables:** Astro Energy & Biom Systems (Madurai, 10 MW) and Prathyusha Power (Tirunelveli, 10 MW) appear in both the biomass table (27) and the bagasse table (28). I kept both records and flagged them in `history`. Table 28 also repeats rows for Sakthi Sugars Erode (18 + 18), Rajshree Villupuram (15 + 15), EID Parry Cuddalore (14 + 12), EID Parry Trichy (15 + 2) and Thiru Arooran Thanjavur (9 + 8). I kept each row with a `-2` suffix and a note.
18. **Wind/solar totals disagree inside the PDF:** Table 44 sums to 7642.09 MW wind, but the text says 8631 MW (end-2018) and Table 50 says 8468.11. Table 45 sums to 1100.41 MW solar, but the text says 2055 MW and Table 50 says 2724.55. Treat the district clusters as partial; the current SLDC figures are wind 9546 and solar 14369.
19. **Table 31 biogas capacities** are "MWeq" of biogas. They may be thermal-equivalent or captive, not grid-electric. The TNPL Karur entry has no capacity. Varalakshmi Starch Salem appears several times with different capacities.
20. **ETPS:** Table 35 lists 340 MW for 2013-17 (units 1–2 already retired) against the 450 MW nameplate; it shut down on 31.03.2017.
21. **Captive "MP":** "MP" means mere parallel (no export). Table 29's Gummidipoondi waste-heat plant has no company name, only the address "K16, Phase II SIPCOT".
22. **Arkay:** Table 7 names it "Arkay Energy Ltd.(PENNA) PIONEER" and Lanco Tanjore "ABAN", which reflects ownership changes. DGR's "VALANTARVY CCPP" is Arkay (Valantharavai) and "KARUPPUR CCPP" is Lanco Tanjore.

### Not in the PDF (for other sources)
- There are no coordinates, no stack/ash-pond/cooling data, and no wind or solar farm-level list apart from Kamuthi.
- Offshore wind, NLC solar, Muppandal and Kayathar appear only as mast or pass names.
- There is no Kundah PH-1 to PH-6 uprating data and no micro-hydel lists beyond those above.
