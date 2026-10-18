"""Build the TN transmission-line layer from real topology.

Two sources, merged:
 1. TNGIS tn_substation `in_feeder` fields — each substation names the
    substation that feeds it. Fuzzy-resolved into edges (this is the bulk
    of the 110/230 kV network).
 2. data/lines_topology.csv — hand-digitised 400/230 kV corridors from the
    SRLDC "Power Map of Tamil Nadu" (June 2014), which labels generator
    switchyards and inter-regional lines the TNGIS layer doesn't carry.
    Schema: from_station,to_station,kv,source

Output: data/geo/tn_lines.geojson (LineStrings, props: kv, source, from, to)
        + unmatched feeder names printed for data/feeder_aliases.csv.
"""
import csv
import json
import re
from difflib import get_close_matches
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
GEO_IN = ROOT / "data" / "geo" / "tn_substation.geojson"
GEO_OUT = ROOT / "data" / "geo" / "tn_lines.geojson"
TOPO_CSV = ROOT / "data" / "lines_topology.csv"
ALIAS_CSV = ROOT / "data" / "feeder_aliases.csv"

STRIP = re.compile(
    r"(\d+(/\d+)*\s*KV|\d+(/\d+)*\s*K\b|"
    r"\b(KV|SS|SUB\s*STATION|STN|FEEDER|BUS|TL|LINE|CIRCUIT|TO|FROM|"
    r"INCOMING|INCOM)\b)", re.I)


def norm(s):
    s = STRIP.sub(" ", (s or "").upper())
    return re.sub(r"[^A-Z]", "", s)  # drop leftover digits/slashes


def load_aliases():
    aliases = {}
    if ALIAS_CSV.exists():
        with open(ALIAS_CSV) as f:
            for row in csv.DictReader(f):
                aliases[norm(row["feeder_name"])] = row["station"]
    return aliases


def main():
    gj = json.load(open(GEO_IN))
    feats = gj["features"]

    pts = {}          # norm name -> (lon, lat, display name)
    for f in feats:
        p = f["properties"]
        name = p.get("sub_station")
        c = f["geometry"]["coordinates"]
        if name and c:
            pts.setdefault(norm(name), (c[0], c[1], name))

    # substation-name spelling variants collapse into one point each; keep all keys
    keys = list(pts)
    aliases = load_aliases()
    edges = {}
    unmatched = {}

    def kv_of(volt_ratio):
        try:
            return max(int(x) for x in re.findall(r"\d+", volt_ratio or ""))
        except ValueError:
            return None

    def add_edge(a, b, kv, source):
        if a == b or a not in pts or b not in pts:
            return False
        key = tuple(sorted((a, b)))
        if key not in edges or (kv or 0) > (edges[key]["kv"] or 0):
            edges[key] = {"kv": kv, "source": source,
                          "from": pts[key[0]][2], "to": pts[key[1]][2],
                          "coords": [pts[key[0]][:2], pts[key[1]][:2]]}
        return True

    def resolve(target):
        """Map a raw in_feeder label to a substation point key."""
        t = norm(target)
        if t in aliases:
            a = norm(aliases[t])
            if a in pts:
                return a
        if t in pts:
            return t
        words = (target or "").upper().replace("-", " ").split()
        # labels like "KAYATAR ARUMUGANERI" or "SEMBATTI RENGANATHAPURAM 2"
        # often end with the feeding station's name — try trailing words
        for n in (2, 1):
            if len(words) >= n:
                cand = norm(" ".join(words[-n:]))
                if cand and (cand in pts or cand in aliases and norm(aliases[cand]) in pts):
                    return cand if cand in pts else norm(aliases[cand])
        if len(t) > 4:
            m = get_close_matches(t, keys, n=1, cutoff=0.85)
            if m:
                return m[0]
            hits = [k for k in keys if t in k or k in t]
            if len(hits) == 1:
                return hits[0]
        return None

    matched = 0
    for f in feats:
        p = f["properties"]
        me = norm(p.get("sub_station"))
        kv = kv_of(p.get("volt_ratio"))
        for raw in (p.get("in_feeder"), p.get("in_feeder_one"), p.get("in_feeder_two")):
            if not raw:
                continue
            other = resolve(raw)
            if other:
                if add_edge(me, other, kv, "tngis_in_feeder"):
                    matched += 1
            else:
                unmatched[raw.strip()] = me

    # hand-digitised corridors from the SRLDC power map
    manual = 0
    if TOPO_CSV.exists():
        with open(TOPO_CSV) as f:
            rows = [r for r in csv.DictReader(
                line for line in f if not line.lstrip().startswith("#"))]
        for row in rows:
            if add_edge(norm(row["from_station"]), norm(row["to_station"]),
                        int(row["kv"]), f"sreldc_map ({row.get('source','')})"):
                manual += 1

    out = {"type": "FeatureCollection", "features": [
        {"type": "Feature",
         "properties": {"from": e["from"], "to": e["to"], "kv": e["kv"],
                        "source": e["source"]},
         "geometry": {"type": "LineString", "coordinates": e["coords"]}}
        for e in edges.values()]}
    GEO_OUT.write_text(json.dumps(out))
    print(f"edges: {len(out['features'])} ({matched} from in_feeder, {manual} manual)")
    print(f"unmatched feeder labels: {len(unmatched)} — extend data/feeder_aliases.csv")
    for k in sorted(unmatched)[:40]:
        print("   ", k, "←", unmatched[k])


if __name__ == "__main__":
    main()
