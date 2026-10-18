#!/usr/bin/env python3
"""Export the Power Map of India datasets to open formats under data/.

    python tools/export_open_data.py [--db data/power.db] [--out data]

Needs: pandas, pyarrow. Writes, per theme folder, every table as CSV (gzipped when >= 5 MB)
and Parquet (zstd); flattens the nested research JSON (supply chain, emissions) into tables;
writes MANIFEST.csv (rows, bytes, sha256) and DICTIONARY.md (column names/types).
GeoJSON/GPKG/Shapefile are produced by tools/export_geo.sh.
"""
import argparse, csv, gzip, hashlib, json, sqlite3
from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
GZ_OVER = 5_000_000

# theme -> db tables
DB_THEMES = {
    "stations": ["npp_stations", "npcil_units"],
    "generation": ["npp_station_daily", "npp_state_daily", "dgr_stations", "res_stations_daily",
                   "merit_state_daily", "merit_rt", "peak_demand_daily", "npp_state_capacity"],
    "coal": ["coal_plants_daily", "coal_plants_monthly", "coal_import_power_monthly", "coal_supply", "coal_india_stats"],
    "gas": ["gas_plants_monthly", "gas_plants_annual"],
    "hydro": ["cwc_reservoir_weekly"],
    "tn_grid": ["sldc_versions", "sldc_rows", "tn_generation_mix", "tn_district", "vp_blocks"],
    "power_quality": ["nfms_state", "nfms_city", "nfms_national"],
}
TABLE_DOC = {
    "npp_stations": "Every generating station on the National Power Portal map: id, type, state, position, capacity.",
    "npcil_units": "NPCIL nuclear units: type, capacity, commercial operation, cumulative generation.",
    "npp_station_daily": "NPP per-station daily generation: programme vs actual (MU), same day last year, FY cumulative.",
    "npp_state_daily": "NPP per-state daily generation totals.",
    "dgr_stations": "CEA Daily Generation Report (DGR) per station and day: capacity, programme/actual MU, YTD, coal stock days, outage MW.",
    "res_stations_daily": "Renewable station daily generation (MU).",
    "merit_state_daily": "MERIT state-wise daily energy by source.",
    "merit_rt": "MERIT India near-real-time generation by source (MW) time series.",
    "peak_demand_daily": "India peak demand / capacity daily summary.",
    "npp_state_capacity": "NPP installed capacity by source per state (payload is JSON text).",
    "coal_plants_daily": "CEA daily coal stock report per thermal plant: stock (indigenous/import), days of stock, receipt, consumption, critical flag.",
    "coal_plants_monthly": "CEA monthly coal receipts and consumption per plant by source (CIL, SCCL, captive, e-auction, import).",
    "coal_import_power_monthly": "Imported coal receipts of power plants by month and entity.",
    "coal_supply": "Generic supply-chain time series: '<measure>:<entity>' (coal production/despatch/offtake, rakes, ports, imports, gas, ...).",
    "coal_india_stats": "Coal India key statistics snapshots.",
    "gas_plants_monthly": "CEA monthly gas supply and generation per gas-based plant (to 2025-05).",
    "gas_plants_annual": "CEA annual gas consumption per gas-based plant.",
    "cwc_reservoir_weekly": "CWC weekly reservoir storage bulletin per reservoir (live storage, level, % of capacity, normal).",
    "sldc_versions": "Tamil Nadu SLDC instantaneous statement: one row per issued version (peaks, minimum, frequency).",
    "sldc_rows": "Tamil Nadu SLDC statement rows per source (capacity, lighting-peak/min/morning MW, MU).",
    "tn_generation_mix": "Tamil Nadu daily generation mix by section/item.",
    "tn_district": "Tamil Nadu district-wise capacity/generation tables.",
    "vp_blocks": "Vidyut Pravah 15-minute demand/exchange/price per state (rolling latest day).",
    "nfms_state": "National Feeder Monitoring System: hours of supply and feeder integration per state.",
    "nfms_city": "NFMS reliability (SAIFI/SAIDI) per city/discom/month.",
    "nfms_national": "NFMS national snapshot (payload is JSON text).",
}

def jsonify(v):
    return json.dumps(v, ensure_ascii=False) if isinstance(v, (list, dict)) else v

def frame(records):
    df = pd.json_normalize(records, max_level=0)
    return df.apply(lambda c: c.map(jsonify))

def rows_of(d, *path):
    for p in path:
        d = d[p]
    if isinstance(d, dict):
        return [{"id": k, **(v if isinstance(v, dict) else {"value": v})} for k, v in d.items()]
    return d

# theme -> name -> (file, path)
JSON_TABLES = {
    "stations": {
        "plants_master": ("web/data/plants.json", ["plants"]),
        "tn_plants_dossier": ("build/dossier/tn_plants.json", []),
    },
    "coal": {
        "mines": ("build/feedstock/mines.json", ["mines"]),
        "coal_companies": ("build/feedstock/mines.json", ["companies"]),
        "gem_coal_mines": ("build/feedstock/gem/india_coal_mines.json", ["records"]),
        "gem_coal_terminals": ("build/feedstock/gem/india_coal_terminals.json", ["records"]),
        "ports": ("build/feedstock/ports.json", ["ports"]),
        "foreign_loading_ports": ("build/feedstock/ports.json", ["foreign_loading_ports"]),
        "tn_plant_port_map": ("build/feedstock/ports.json", ["tn_plant_port_map"]),
        "sea_lanes": ("build/feedstock/ports.json", ["sea_lanes"]),
        "plant_source_links": ("build/feedstock/links.json", ["links"]),
        "plant_source_nodes": ("build/feedstock/links.json", ["nodes"]),
        "plant_supply_plants": ("build/feedstock/links.json", ["plants"]),
        "derived_routes": ("build/feedstock/derived_links.json", ["routes"]),
        "cea_receipts_fy2025_26": ("build/feedstock/_parsed/coal_receipts_cea_monthly.json", ["fy2025_26"]),
        "cea_receipts_fy2026_27_ytd": ("build/feedstock/_parsed/coal_receipts_cea_monthly.json", ["fy2026_27_ytd"]),
        "cea_daily_coal_remarks_decoded": ("build/feedstock/_parsed/cea_daily_coal_remarks_decoded.json", ["plants"]),
        "supply_chain_nodes": ("web/data/feed.json", ["nodes"]),
        "supply_chain_routes": ("web/data/feed.json", ["routes"]),
    },
    "gas": {
        "gas_fields": ("build/feedstock/gas.json", ["fields"]),
        "gas_processing_terminals": ("build/feedstock/gas.json", ["processing_terminals"]),
        "lng_terminals": ("build/feedstock/gas.json", ["lng_terminals"]),
        "gas_pipelines": ("build/feedstock/gas.json", ["pipelines"]),
        "gas_plant_supply": ("build/feedstock/gas.json", ["plant_supply"]),
    },
    "nuclear": {
        "nuclear_fuel_nodes": ("build/feedstock/nuclear_fuel.json", ["nodes"]),
        "nuclear_fuel_chains": ("build/feedstock/nuclear_fuel.json", ["chains"]),
    },
    "tn_grid": {
        "tn_ehv_substations_official": ("build/grid/tn_ehv_substations_official.json", ["substations"]),
    },
    "emissions": {
        "station_emissions_estimates": ("build/emissions/stations.json", ["stations"]),
        "co2_baseline_stations": ("build/emissions/_parsed/co2_baseline.json", ["stations"]),
        "fgd_units": ("build/emissions/_parsed/fgd_units.json", ["units"]),
        "flyash_stations_2021_22": ("build/emissions/_parsed/flyash.json", ["stations_2021_22"]),
        "flyash_tn_2022_23_h1": ("build/emissions/_parsed/flyash.json", ["tamil_nadu_2022_23_h1"]),
        "flyash_state_totals_2024_25": ("build/emissions/_parsed/flyash.json", ["state_totals_2024_25"]),
        "flyash_plant_list_2024_25": ("build/emissions/_parsed/flyash.json", ["plant_list_2024_25"]),
        "caaqms_tn_monitors": ("build/emissions/_parsed/caaqms_tn.json", ["stations"]),
        "incidents_tn": ("build/emissions/_parsed/incidents_tn.json", ["incidents"]),
        "so2_measured_tn_2021": ("build/emissions/_parsed/so2_measured_tn_2021.json", ["units"]),
    },
}

def write(df, theme, name, out, manifest, doc=""):
    d = out / theme
    d.mkdir(parents=True, exist_ok=True)
    csvp = d / f"{name}.csv"
    df.to_csv(csvp, index=False, quoting=csv.QUOTE_MINIMAL)
    if csvp.stat().st_size >= GZ_OVER:
        with open(csvp, "rb") as f, gzip.GzipFile(str(csvp) + ".gz", "wb", mtime=0) as g:
            g.write(f.read())
        csvp.unlink()
        csvp = Path(str(csvp) + ".gz")
    pq = d / f"{name}.parquet"
    df.to_parquet(pq, index=False, compression="zstd")
    for p, fmt in ((csvp, "csv"), (pq, "parquet")):
        manifest.append({"theme": theme, "table": name, "format": fmt, "path": str(p.relative_to(out.parent)),
                         "rows": len(df), "bytes": p.stat().st_size,
                         "sha256": hashlib.sha256(p.read_bytes()).hexdigest(), "description": doc})
    cols = "\n".join(f"| `{c}` | {t} |" for c, t in zip(df.columns, df.dtypes.astype(str)))
    return f"### `{theme}/{name}`\n{doc}\n\n{len(df):,} rows\n\n| column | type |\n|---|---|\n{cols}\n"

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default=str(ROOT / "data" / "power.db"))
    ap.add_argument("--out", default=str(ROOT / "data"))
    a = ap.parse_args()
    out = Path(a.out)
    manifest, dictionary = [], []
    con = sqlite3.connect(f"file:{a.db}?mode=ro", uri=True)
    for theme, tables in DB_THEMES.items():
        for t in tables:
            df = pd.read_sql(f"SELECT * FROM {t}", con)
            dictionary.append(write(df, theme, t, out, manifest, TABLE_DOC.get(t, "")))
    for theme, names in JSON_TABLES.items():
        for name, (f, path) in names.items():
            recs = rows_of(json.load(open(ROOT / f)), *path)
            dictionary.append(write(frame(recs), theme, name, out, manifest, f"Flattened from `{f}`" + (f" [{'.'.join(path)}]" if path else "") + "; nested values are JSON text."))
    # keep a few nested originals verbatim (lossless)
    (out / "stations").mkdir(exist_ok=True)
    for src, dst in (("build/dossier/tn_plants.json", "stations/tn_plants_dossier.json"),
                     ("build/feedstock/links.json", "coal/plant_source_links_full.json"),
                     ("web/data/feed.json", "coal/supply_chain_full.json"),
                     ("build/emissions/_parsed/norms_2015.json", "emissions/norms_2015.json"),
                     ("build/emissions/stations.json", "emissions/station_emissions_full.json"),
                     ("build/feedstock/gas.json", "gas/gas_supply_chain_full.json"),
                     ("build/feedstock/nuclear_fuel.json", "nuclear/nuclear_fuel_full.json")):
        (out / dst).parent.mkdir(parents=True, exist_ok=True)
        (out / dst).write_bytes((ROOT / src).read_bytes())
    with open(out / "MANIFEST.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(manifest[0])); w.writeheader(); w.writerows(manifest)
    (out / "DICTIONARY.md").write_text("# Data dictionary\n\nGenerated by `tools/export_open_data.py`. Dates are ISO (YYYY-MM-DD); "
        "MU = million units (GWh); kt = kilotonnes; MW/MWe as labelled; coordinates are WGS84 (lat, lon).\n\n" + "\n".join(dictionary))
    print(len(manifest) // 2, "tables")

if __name__ == "__main__":
    main()
