"""Download OSM power infrastructure for India (per state) + TN/Chennai detail.

Raw Overpass JSON is cached in raw/osm/. Run: .venv/bin/python scripts/grid_fetch_osm.py
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from grid_overpass import RAW  # noqa: E402
from grid_overpass import fetch as _fetch  # noqa: E402

FAILED = []


def fetch(name, query):
    """Non-fatal wrapper: record failures and move on (re-run the script to fill gaps)."""
    try:
        return _fetch(name, query)
    except RuntimeError as e:
        FAILED.append(name)
        print(f"  FAILED {name}: {str(e)[:120]}", file=sys.stderr)

# voltage list contains any value >= 66 kV (66000..999999, optional +/- sign for HVDC)
HV = r'(^|;) *[-+]?(6[6-9][0-9]{3}|[7-9][0-9]{4}|[1-9][0-9]{5})( *;|$)'
CHENNAI_BBOX = "12.75,79.95,13.35,80.40"

states = json.load(open(os.path.join(RAW, "india_states.json")))["elements"]
states = sorted(states, key=lambda e: e["tags"]["ISO3166-2"])
only = set(sys.argv[1:])

for st in states:
    code = st["tags"]["ISO3166-2"]
    if only and code not in only:
        continue
    aid = 3600000000 + st["id"]
    a = f"area({aid})->.a;"
    print(code, file=sys.stderr)
    fetch(f"lines_hv_{code}", a + f'way[power~"^(line|cable)$"][voltage~"{HV}"](area.a);out geom tags;')
    fetch(f"lines_novolt_count_{code}", a + 'way[power=line][!voltage](area.a);out count;')
    fetch(f"substations_{code}", a + "nwr[power=substation](area.a);out center tags;")
    fetch(f"plants_{code}", a + "nwr[power=plant](area.a);out geom;")
    fetch(f"generators_{code}", a + "nwr[power=generator](area.a);out center tags;")

if not only or "IN-TN" in only:
    tn = 3600000000 + 96905
    a = f"area({tn})->.a;"
    fetch("tn_lines_all", a + 'way[power~"^(line|minor_line|cable)$"](area.a);out geom tags;')
    fetch("chennai_lines_all", f'way[power~"^(line|minor_line|cable)$"]({CHENNAI_BBOX});out geom tags;')
    fetch("tn_substation_polygons", a + "(way[power=substation](area.a);rel[power=substation](area.a););out geom;")
    fetch("tn_generator_polygons", a + "(way[power=generator](area.a);rel[power=generator](area.a););out geom;")
    fetch("tn_towers_400_765", a + 'way[power=line][voltage~"(^|;)(400000|765000)(;|$)"](area.a)->.l;'
          'node(w.l)[power~"^(tower|portal|terminal)$"];out;')

print("FAILED:", FAILED if FAILED else "none", file=sys.stderr)
