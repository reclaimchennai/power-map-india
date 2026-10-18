# build/grid — physical grid layers (lines, substations, plant footprints)

Built 2026-09-24. Everything here can be rebuilt with these scripts, run in this order:

```
.venv/bin/python scripts/grid_fetch_osm.py IN-TN                 # Overpass: TN detail layers (cached in raw/osm/)
.venv/bin/python scripts/grid_pbf_extract.py raw/osm/india-260923.osm.pbf   # India-wide layers from the Geofabrik extract
.venv/bin/python scripts/grid_build.py        # -> lines_*, substations*, osm_plants, tn_wind_turbines, tn_solar_arrays, towers_tn, osm_stats.json
.venv/bin/python scripts/grid_tn_official.py  # -> tn_ehv_substations_official.json, npp_transmission_stats.json
.venv/bin/python scripts/grid_tn_merge.py     # -> tn_substations_merged.geojson, tn_ehv_osm_check.json
.venv/bin/python scripts/grid_corridors.py    # -> corridor_check.json
```

## Licence and attribution (required)

* **OpenStreetMap data:** © OpenStreetMap contributors, available under the **Open Database Licence (ODbL) 1.0**.
  The site must show "© OpenStreetMap contributors" linked to https://www.openstreetmap.org/copyright
  wherever these layers are drawn. Every OSM-derived FeatureCollection has an `attribution` field.
  ODbL is share-alike: if we publish a derived *database* (for example the merged TN substation file),
  it has to be offered under ODbL as well.
* **TNGIS substations** (`data/geo/tn_substation.geojson`) are from the Tamil Nadu Government GIS portal.
  Cite the source. The licence is not stated on the portal.
* **TANTRANSCO and SLDC lists** are public web pages of Government of Tamil Nadu undertakings. We cite the URLs.
  Officer names and phone numbers from the SLDC page were **dropped** and are not in any build file.
  The raw HTML under `raw/pages/` is gitignored.
* **NPP** (npp.gov.in, Ministry of Power) is public dashboard data. We cite the URL.

## Where the OSM data came from

| Scope | Source | Timestamp |
|---|---|---|
| Tamil Nadu layers: HV lines, substations, plants, generators, all-voltage lines, Chennai bbox lines, substation and generator polygons, 400/765 kV towers | Overpass API (overpass-api.de, overpass.kumi.systems) | 2026-09-24 ~09:40Z |
| Arunachal Pradesh (its boundary could not be assembled from the Geofabrik extract) | Overpass | 2026-09-24 ~10:20Z |
| Other 34 states and UTs | Geofabrik `india-260923.osm.pbf` (1.7 GB, md5 checked), filtered with pyosmium (`scripts/grid_pbf_extract.py`), and written in the same Overpass-JSON shape | extract of 2026-09-23 |

Per-state Overpass queries for all of India kept failing with HTTP 504 on all three mirrors
(about 7 states per 40 minutes). So I stopped them and used the Geofabrik extract for the India-wide layers.
For Andhra Pradesh, where both sources exist, the counts agree:
Overpass gave 784 substations and 3,871 generators; the PBF gave 786 and 3,865.
Provenance for each file is in `raw/osm/manifest.json`, and a copy is in `osm_stats.json → osm_provenance`.
The raw files are in `raw/osm/`, which is gitignored and can be re-fetched.

## Files

| File | What | Features | Size (raw / gzip) |
|---|---|---|---|
| `lines_765.geojson` | AC 765 kV lines, India | 1,357 ways, 40,768 route-km | 0.96 / 0.23 MB |
| `lines_400.geojson` | AC 400 kV lines | 10,177 ways, 119,233 km | 4.62 / 0.80 MB |
| `lines_220.geojson` | AC 220 and 230 kV lines | 11,251 ways, 117,223 km | 5.08 / 0.90 MB |
| `lines_110.geojson` | AC 66, 110 and 132 kV lines | 19,020 ways, 177,814 km | 8.50 / 1.51 MB |
| `lines_hvdc.geojson` | HVDC lines (±500, ±800, ±320, plus the 200 kV Sileru–Barsoor) | 145 ways, 9,966 km | 0.17 / 0.05 MB |
| `lines_tn_distribution.geojson` | TN lines at 33 kV or below (`minor_line`, 11/22/25/33 kV) | 1,123 ways, about 168 km | 0.32 / 0.02 MB |
| `lines_tn_unknown_voltage.geojson` | TN `power=line` with no voltage tag | 171 | 0.07 / 0.01 MB |
| `lines_chennai_all.geojson` | All power lines in the Chennai bbox (12.75,79.95 to 13.35,80.40), with `class` 765/400/220/110/dist/unknown | 1,160 | 0.41 / 0.05 MB |
| `substations.geojson` | Points: India substations of 66 kV and above, plus **all** TN substations | 9,678 (TN 1,322) | 3.27 / 0.25 MB |
| `substations_tn_polygons.geojson` | TN substation outlines (ways and multipolygons), with `area_ha` | 1,308 | 0.73 / 0.09 MB |
| `osm_plants.geojson` | `power=plant` polygons and points for India (4,003), plus 365 standalone generators (1 MW or more, or named, and not inside a mapped plant) | 4,368 | 3.75 / 0.74 MB |
| `tn_wind_turbines.geojson` | TN wind turbine generator nodes | 12,807 | 2.34 / 0.17 MB |
| `tn_solar_arrays.geojson` | TN solar generator polygons of 0.5 ha or more (panel-block footprints), with the enclosing plant | 476 | 1.06 / 0.19 MB |
| `towers_tn.geojson` | TN tower, portal and terminal nodes on 400/765 kV lines, with `line_voltage_kv` | 27,623 (400: 22,398; 765: 5,225) | 4.44 / 0.29 MB |
| `tn_substations_merged.geojson` | TNGIS 1,872 plus OSM TN, matched (see below) | 2,503 | 1.45 MB |
| `tn_ehv_substations_official.json` | TANTRANSCO 765/400/230 kV lists joined to the SLDC list | 139 | — |
| `tn_ehv_osm_check.json` | Each official EHV substation: in OSM, missing, or tagged differently | 139 | — |
| `npp_transmission_stats.json` | NPP transmission dashboard summary (all-India only) | — | — |
| `corridor_check.json` | Checks that the major HVDC, interstate and Chennai-ring corridors are present | — | — |
| `osm_stats.json` | All counts, km, sizes, and provenance | — | — |

"Route-km" is the length of the mapped way geometry. It is not circuit-km (ckm):
a double-circuit line counts once here and twice in CEA/NPP ckm figures.

### Geometry and properties

* Lines are simplified to about 15 m (Shapely `simplify(0.000135°)`; about 5 m for distribution and Chennai lines).
  Coordinates are rounded to 5 decimals.
* Polygons are simplified to about 3 m (plants and solar arrays) or about 1 m (substations).
* Line properties follow the SCHEMA: `voltage_kv` (the highest value when the tag has several, e.g. "400000;220000"),
  `circuits`, `name`, `operator`, `source` ("osm") and `osm_id`. These are always present, null when unknown.
  Optional extras: `voltages[]` when there is more than one, `circuits_from_cables` (cables ÷ 3, labelled so it is
  not mistaken for a tagged value), `cables`, `ref`, `owner`, `location`, `line_type`, `frequency`, `states[]`.
  To keep line files small, per-feature `sources` is replaced by a collection-level
  `sources_template` = `https://www.openstreetmap.org/{osm_id}`.
  `build_site.py` should expand it if it needs `sources` on every record.
* Substation points: `name, voltage_kv, voltages[], mva, owner, operator, circle, state, source, osm_id, sources`.
  `mva` and `circle` are null for OSM. MVA and circle for TN come from TNGIS and are in the merged file.
* Classification: 765 means 700 kV or more. 400 means 380–699. 220 means 200–379. 110 means 66–199.
  **HVDC** means `frequency=0`, or "hvdc" in the name/ref/`line` tag, or a voltage of 320, 500 or 800 kV
  (India has no AC line at those voltages).
  Lines with no voltage tag are **not** in the class files, because a voltage cannot be guessed.

## Counts by voltage class

| Class | India ways | India route-km | TN ways | TN route-km | TANTRANSCO ckm (31.03.2025) |
|---|---|---|---|---|---|
| 765 kV | 1,357 | 40,768 | 30 | 2,042 | 733 |
| 400 kV | 10,177 | 119,233 | 373 | 7,803 | 5,215 |
| 220/230 kV | 11,251 | 117,223 | 760 | 10,092 | 11,985 |
| 66–132 kV | 19,020 | 177,814 | 1,590 | 13,752 | 21,364 (110 + 66) |
| HVDC | 145 | 9,966 | 4 | 568 | — |

The TN OSM km are higher than TANTRANSCO's for 765 and 400 kV because OSM also includes
PGCIL/ISTS lines and generator evacuation lines, which TANTRANSCO does not own.
NPP gives an all-India total of 508,535 ckm at 220 kV and above (FY 2026-27 header).
The OSM route-km for 220 kV and above is about 287,000 km, which fits once double circuits are counted twice.

Substations (points, India, 66 kV and above plus all TN) by highest voltage:
765 kV: 129. 400 kV: 693. 220/230 kV: 2,289. 66–132 kV: 6,178.
TN with no voltage tag: 385. TN below 66 kV: 4.
Across India, **7,632** OSM substations have no voltage tag and were left out; 385 of those are in TN and were kept.

## Tamil Nadu official data

* **TANTRANSCO** (`raw/grid/tantransco_substations_{765,400,230}.html`) lists 2 substations at 765 kV,
  19 at 400 kV and 116 at 230 kV, each with voltage ratio and commissioning date.
  `raw/grid/tantransco_network_as_on_31032025.pdf` gives totals: 1,102 substations and 39,297 ckm.
  The network page itself is `raw/grid/tantransco_network.html`.
* **SLDC Sslist** (a 2018 Word export): 105 EHV substations with operation circle and EDC.
  On some circles the EDC column holds officer names; I detected these and set EDC to null.
  Joined to TANTRANSCO by spelling-insensitive name matching plus a few manual aliases
  (for example Ottiyambakkam = Sholinganallur 400 kV, SP Koil = Singaperumalkoil,
  Muthiahpuram (Auto) = Tuticorin Auto). This gives 139 records.
  Three are only in the SLDC list: Thervoikandigai 400 kV, Checkkanoorani 230 kV switching station, and Myvadi 230 kV.
* **TNGIS ↔ OSM merge** (`tn_substations_merged.geojson`):
  * Candidates are OSM substations within 3 km.
  * They are accepted on a name match (score 0.8 or higher, with a small bonus for the same voltage class and a
    penalty for distance), or on proximity when the OSM feature is unnamed, is within 400 m, and has the same
    voltage class.
  * Matching is greedy and one-to-one.
  * Result: 691 of the 1,872 TNGIS substations matched (634 by name, 57 by proximity).
    1,181 are TNGIS-only; most are 33/11 kV, which OSM rarely maps. 631 are OSM-only.
  * Fields: TNGIS `voltage_ratio, mva (total_capacity), transformers, feeders_in/out, circle, tneb_ss_id`,
    plus `osm_*`, `match`, `match_dist_m` and `match_name_score`. Where a TNGIS point matches an official EHV record
    there are also `official_name, commissioned, operation_circle, edc`.

### TN EHV substations missing from OSM (`tn_ehv_osm_check.json`)

* All 2 × 765 kV (Ariyalur; North Chennai Pooling, which is "NCPS" in OSM) and all 20 × 400 kV are in OSM.
  That includes Pulianthope 400 kV GIS, Ottiyambakkam (Sholinganallur), Thervoy Kandigai, Vellalaviduthi,
  Thappakundu, Kamudhi and Ottapidaram.
* **230 kV not found in OSM (11):**
  * Chennai GIS/UG stations: Alandur CMRL GIS, Ambattur 3rd Main Road, CMRL Central, Mylapore I, Mylapore II GIS,
    Porur GIS, R.A. Puram, and TNEB Head Quarters GIS.
  * Elsewhere: Kinnimangalam, Myvadi, and Tuticorin SIPCOT.
  * Several have an unnamed OSM substation within about 30 m of the TNGIS point
    (see `nearest_osm_substation_within_1km_of_tngis_point`), so they are mapped but not named.
* **Guindy 230 kV GIS** is in OSM but has no voltage tag.

## Corridor check (`corridor_check.json`)

* **HVDC:**
  * Present and named:
    * Raigarh–Pugalur ±800 kV (12 segments, with Pugalur HVDC station 400/320 kV)
    * Pugalur–Thrissur (Madakkathara) ±320 kV VSC
    * Talcher–Kolar ±500 kV (both converter stations)
    * Champa–Kurukshetra ±800
    * Biswanath Chariali–Alipurduar–Agra ±800
    * Rihand–Dadri, Mundra–Mahendragarh, Ballia–Bhiwadi and Chandrapur–Padghe ±500
    * Sileru–Barsoor
  * Back-to-back HVDC stations (Vindhyachal, Chandrapur, Gazuwaka/Vizag, Sasaram, Bhadrawati) have no line,
    so they appear only as substations if they are mapped.
* **TN 765/400 kV nodes** (all present, with 765/400 kV line ends nearby):
  * Kudankulam NPP switchyard (25 line ends at 400 kV; the "Kudankulam - Thirunelveli" 400 kV line is named)
  * Tirunelveli (PGCIL)
  * Tuticorin Pooling (765/400)
  * Virudhunagar 765
  * Dharmapuri (Salem) 765
  * Thiruvalam 765/400
  * Ariyalur 765
  * NCPS 765
  * Nagapattinam 765
  * Madurai (Chekkanurani)
  * Udumalpet
* **Chennai 400 kV ring** (all present):
  * Alamathy, Manali, Sriperumbudur (PGCIL, plus TANTRANSCO Pennalur), Thiruvalam, NCTPS stages I/II/III,
    Vallur, Kalivanthapattu, Pulianthope, Sunguvarchatram, Ottiyambakkam, Thervoy Kandigai, Ennore SEZ, and NCPS.
  * Weak spots: Manali and Pulianthope have only 2 × 400 kV line ends nearby. The urban 400/230 kV feeds into
    Pulianthope and Manali are partly underground cable, which OSM often leaves unmapped or without a voltage tag.
    This needs a manual check against imagery or the TANTRANSCO line list.
  * Chennai-bbox lines by class: 400 kV 128, 220/230 kV 158, 110 kV 98, 765 kV 2, distribution 242,
    and **no voltage tag 532**.
* Almost all 765 kV ways in TN are unnamed (30 of 30). In TN, 359 of 373 400 kV ways are unnamed.
  So a corridor can be shown geometrically, but the line can rarely be named from OSM alone.
  Naming needs the SLDC/CEA line lists.

## Coverage caveats (OSM completeness)

* **Transmission (220 kV and above)** is well mapped across India, and PGCIL/ISTS lines are close to complete.
* **66–132 kV** is patchy by state.
  * In TN, OSM 110 kV route-km is about 13.8k against TANTRANSCO's 21.3k ckm.
    Many 110 kV lines are double-circuit, so the real gap is smaller, but some radial 110 kV feeders are unmapped.
  * `data/geo/tn_lines.geojson` (TNGIS in_feeder straight segments) can fill topology, but not geometry.
* **Voltage tagging:**
  * Most TN 230 kV lines are tagged `220000` in OSM (664 ways tagged 220 kV against 94 tagged 230 kV),
    so the 220 class merges them.
  * 161 TN `power=line` ways (171 including cables) have no voltage tag and are excluded from the class files.
    They are kept in `lines_tn_unknown_voltage.geojson`. Many substations nationally also have no voltage tag;
    the TN ones stay in the substations file.
* **Distribution (33 kV and below)** in TN is very sparse in OSM: about 168 km, mostly `minor_line` in a few areas.
  Treat it as illustrative only.
* **Plants:**
  * 3,021 of the 4,368 features are solar.
  * 165 plants have no `plant:source`.
  * Capacity (`plant:output:electricity`) is often missing or "yes", which gives `capacity_mw: null`.
    Use it only as a footprint and cross-reference; take capacity from the plant dossiers.
* **Wind:** TN has 12,807 mapped turbines, but only 165 carry `generator:output:electricity`.
  India-wide there are 35,821 wind generators; only TN's are exported.
* **Towers:** only on lines tagged 400/765 kV in TN. Most carry no `height` or `design` tag,
  so pylon models must use archetype defaults.
* **Official TN lists:** TANTRANSCO's pages are current (Ariyalur and NCPS 765 kV were commissioned in 2023–24).
  The SLDC Sslist page is a 2018 document, so its circle and EDC assignments may be out of date.

## NPP transmission dashboard

* `GET https://npp.gov.in/dashBoard/getTransmissionLine?ID=IND` returns **all-India figures only**.
  `ID=TN`, `ID=33` and `ID=SR` return a byte-identical payload, so there is no state-wise ckm or MVA.
* Contents:
  * FY-to-date additions by voltage (220, 400, 765 kV and ±320/500/800 kV), current FY against the same period last FY.
  * Annual additions for FY 2022-23 to 2026-27.
  * Header totals: 508,535 ckm at 220 kV and above, and 1,469,041 MVA transformation capacity.
* NPP's field names are misleading. `transmission_line_intra_state_ckm_cum` is actually the all-India cumulative ckm.
  See `npp_transmission_stats.json → notes`.
* Raw file: `raw/grid/npp_trans.json`.
