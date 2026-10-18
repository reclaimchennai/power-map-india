# build/ — intermediate datasets and their contracts

Everything under `build/` is produced by scripts or research agents and consumed by
`scripts/build_site.py`, which writes the published `web/data/*.json`. Every record
must carry `sources` (list of URLs or `file:page` references) so the site can cite it.
Unknown = `null`, never a guess. Estimates are allowed only when labelled
(`"estimate": true` plus `"method"`).

## Plant record (`build/dossier/*.json` → list of these)

```jsonc
{
  "id": "nctps-2",                  // kebab slug, stable
  "name": "North Chennai Thermal Power Station Stage II",
  "aliases": ["NCTPS-2", "NORTH CHENNAI TPS STAGE 2"],   // every spelling seen in NPP/CEA/SLDC/DGR
  "type": "coal",                   // coal|lignite|gas|diesel|nuclear|hydro|pumped_storage|wind|solar|biomass|cogen|waste|battery
  "status": "operating",            // operating|under_construction|planned|retired|mothballed
  "state": "Tamil Nadu", "district": "Tiruvallur",
  "lat": 13.2463, "lon": 80.3208,   // WGS84, main block / powerhouse
  "loc_quality": "exact",           // exact (checked on imagery/OSM/NPP) | approx
  "capacity_mw": 1200,
  "units": [{"no": 1, "mw": 600, "commissioned": "2013-03", "make": "BHEL", "status": "operating"}],
  "operator": "TNPGCL", "owner_sector": "state",   // central|state|private|jv
  "fuel": {
    "primary": "coal",              // coal|lignite|gas|naphtha|uranium|water|wind|sun|bagasse|biomass
    "grade_or_kind": "domestic + imported blend",
    "sources": [{"name": "MCL Talcher coalfields", "kind": "mine", "lat": 20.95, "lon": 85.2, "share": null}],
    "route": ["rail: Talcher -> Paradip port", "sea: Paradip -> Kamarajar (Ennore) port", "conveyor: port -> plant"],
    "annual_requirement": "5.2 MTPA"
  },
  "water": {"source": "Bay of Bengal (sea water)", "cooling": "once-through seawater"},  // or cooling tower / reservoir
  "structure": {                     // drives the voxel model; nulls fall back to archetype defaults
    "stacks": [{"h_m": 275, "flues": 2}], "cooling_towers": 0, "boiler_units": 2,
    "coal_yard": true, "ash_pond": {"lat": 13.26, "lon": 80.31, "area_ha": null},
    "dam_h_m": null, "dam_len_m": null, "hub_h_m": null, "rotor_d_m": null, "turbines": null, "area_ha": null
  },
  "evacuation": ["400 kV NCTPS-Alamathy DC line"],
  "emissions": {"fgd": "under installation", "co2_t_per_mwh": null, "notes": ""},
  "history": "one or two sentences",
  "links": {"npp_station_id": 100034, "dgr_name": "NORTH CHENNAI TPS STAGE 2", "cea_coal_name": null, "sldc_item": null},
  "sources": ["https://www.tnpgcl.org/en/generation/generation/thermal-power-stations/nctps2/"]
}
```

## Grid (`build/grid/`)
- `substations.geojson` — Point features: `name, voltage_kv (max), voltages[], mva, owner, circle, source, osm_id`.
- `lines_<class>.geojson` — LineString features: `voltage_kv, circuits, name, operator, source, osm_id`.
  Classes: `765`, `400`, `220` (220/230), `110` (132/110/66), plus `hvdc`.

## Feedstock / pollution (`build/feedstock/`, `build/emissions/`)
- `mines.json`, `ports.json`, `gas.json` (fields, pipelines as LineString coords, LNG terminals),
  `nuclear_fuel.json`, `links.json` (`plant_id -> [{from, mode, via[], share, source}]`).
- `emissions/stations.json` — per plant: CO2 factor (CEA CO2 baseline DB), FGD status (CEA),
  fly-ash generation/utilisation (CEA fly-ash report), stack emission norms (MoEFCC 2015),
  nearby CAAQMS stations, and labelled estimates of annual SO2/NOx/PM/CO2.
