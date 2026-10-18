"""Build data/geo/tn_plants.geojson from the hand-curated plant atlas
(data/plants_tn.csv) — nuclear, thermal, gas, hydro, wind, solar.
Coordinates are exact where marked, otherwise approximate (district-level).
"""
import csv
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "data" / "plants_tn.csv"
OUT = ROOT / "data" / "geo" / "tn_plants.geojson"


def main():
    feats = []
    with open(SRC) as f:
        for row in csv.DictReader(r for r in f if not r.startswith("#")):
            feats.append({
                "type": "Feature",
                "properties": {
                    "name": row["name"], "type": row["type"],
                    "capacity_mw": float(row["capacity_mw"]),
                    "operator": row["operator"], "accuracy": row["accuracy"],
                },
                "geometry": {"type": "Point",
                             "coordinates": [float(row["lon"]), float(row["lat"])]},
            })
    OUT.write_text(json.dumps({"type": "FeatureCollection", "features": feats}))
    print(f"{len(feats)} plants -> {OUT}")


if __name__ == "__main__":
    main()
