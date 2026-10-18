"""Build build/emissions/_parsed/caaqms_tn.json and incidents_tn.json (fork 'caaqms')."""
import json, math, csv, os

ROOT = "."
RAW = f"{ROOT}/raw/emissions"
OUT = f"{ROOT}/build/emissions/_parsed"
os.makedirs(OUT, exist_ok=True)

# ---------------------------------------------------------------- plants (OSM)
osm = {}
for fn in ["raw/feedstock/osm_tn_power_plants.json", "raw/feedstock/osm_tn_extra_pfbr_gummidipoondi.json"]:
    for e in json.load(open(f"{ROOT}/{fn}"))["elements"]:
        c = e.get("center", e)
        osm[(e["type"], e["id"])] = (round(c["lat"], 5), round(c["lon"], 5), e.get("tags", {}), fn)

# plant id -> (osm type, osm id, precision note)
PLANT_OSM = {
    "nctps-1": ("way", 102546589, "OSM polygon 'North Chennai Thermal Station' (1830 MW, covers Stage I+II); centroid"),
    "nctps-2": ("way", 102546589, "same NCTPS complex polygon; centroid"),
    "nctps-3": ("way", 102546589, "Stage III (800 MW) is adjacent to the NCTPS complex; complex centroid used"),
    "ennore-tps": ("way", 30738573, "OSM polygon centroid (old ETPS site, decommissioned)"),
    "ennore-sez": ("way", 25850550, "OSM polygon 'Ennore SEZ Super Critical Thermal Power Project (Vayalur)' centroid"),
    "mettur-1": ("way", 429967366, "OSM polygon 'Mettur Thermal Power Plant' (1440 MW, both stages); centroid"),
    "mettur-2": ("way", 429967366, "same Mettur complex polygon; centroid"),
    "tuticorin-tps": ("way", 662798207, "OSM polygon centroid"),
    "ntpl-tuticorin": ("way", 662798206, "OSM polygon centroid"),
    "vallur-ntecl": ("way", 133591372, "OSM polygon centroid"),
    "neyveli-ts1-exp": ("way", 465874233, "OSM polygon 'Neyveli Thermal Power Station I' tagged 420 MW (= TS-I Expansion 2x210); centroid"),
    "neyveli-ts2": ("way", 136727943, "OSM polygon 'Neyveli Thermal Power Station II' (1970 MW = TS-II 1470 + TS-II Exp 500); centroid"),
    "neyveli-ts2-exp": ("way", 136727943, "TS-II Expansion lies within the TS-II polygon; centroid"),
    "nnttp": ("way", 345057949, "OSM polygon 'Neyveli New Thermal Power Station' centroid"),
    "itpcl-cuddalore": ("way", 645959123, "OSM polygon 'IL&FS Tamil Nadu Thermal Power Station' centroid"),
    "muthiara-coastal-energen": ("way", 733764035, "OSM polygon 'Mutiara Thermal Power Plant' centroid"),
    "sepc-tuticorin-st4": ("way", 822892679, "OSM polygon 'SEPC' 525 MW centroid"),
    "indbarath-tuticorin": ("way", 385432388, "OSM polygon 'Thoothukudi IBTPL power station' 300 MW centroid"),
    "taqa-neyveli": ("way", 924966809, "OSM polygon 'Neyveli Zero Power Plant' 250 MW centroid"),
    "opg-gummidipoondi": ("way", 840721288, "OSM polygon 'Chennai OPG Power Plant' centroid"),
    "tulsyan-nec": ("way", 636898416, "OSM polygon 'Tulsyan Steel Gummidipoondi Captive Power Plant' centroid"),
    "ppn-power": ("way", 156177503, "OSM polygon 'Pillaiperumalnallur Gas Power Plant' centroid"),
    "basin-bridge-gt": ("way", 28342737, "OSM polygon 'Basin Bridge Gas Turbine Power Station' centroid"),
    "kuttalam-gt": ("way", 823185402, "OSM polygon 'Kuttulam Power Plant' (TANGEDCO, gas) centroid"),
    "thirumakottai-gt": ("way", 341599763, "OSM polygon 'Thirumakotai Power Station' centroid"),
    "valuthur-gt": ("way", 310430102, "OSM polygon 'Valathur' (TANGEDCO gas 187 MW) centroid"),
    "kudankulam": ("way", 384663588, "OSM polygon 'Kudankulam Nuclear Power Plant' centroid"),
    "maps": ("way", 98366375, "OSM polygon 'Madras Atomic Power Station' centroid"),
    "pfbr": ("node", 6861924154, "OSM node power=generator 'Prototype Fast Breeder Reactor'"),
    "udangudi": ("relation", 15986380, "OSM relation power=plant, operator TNPGCL, 1320 MW, near Udangudi; centroid"),
}
plants = {}
for pid, (t, i, note) in PLANT_OSM.items():
    lat, lon, tags, fn = osm[(t, i)]
    plants[pid] = {"lat": lat, "lon": lon, "osm": f"{t}/{i}", "osm_name": tags.get("name") or tags.get("name:en"),
                   "loc_precision": "osm_node" if t == "node" else "osm_polygon_centroid", "note": note,
                   "source": f"https://www.openstreetmap.org/{t}/{i}"}


def hav(a, b, c, d):
    R = 6371.0
    p1, p2 = math.radians(a), math.radians(c)
    dp, dl = p2 - p1, math.radians(d - b)
    h = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * R * math.asin(math.sqrt(h))


# ---------------------------------------------------------------- CAAQMS
feed = json.load(open(f"{RAW}/caaqms/cpcb_rss_feed_with_coordinates_2026-09-24.xml"))
live = {}
for s in feed["country"]:
    if s["stateId"] != "Tamil Nadu":
        continue
    for c in s["citiesInState"]:
        for st in c["stationsInCity"]:
            live[st["stationName"]] = dict(city=c["cityId"], site_id=st["siteId"], lat=st["latitude"], lon=st["longitude"],
                                           last_update=st["lastUpdate"], params=[p["indexId"] for p in st["pollutants"]])
hf = {}
with open(f"{RAW}/caaqms/hf_zeel_c1_station_data.csv") as f:
    for r in csv.DictReader(f):
        if r["station"].endswith("TNPCB") or "Chennai - CPCB" in r["station"]:
            hf[r["station"]] = r

FEED_URL = "https://airquality.cpcb.gov.in/caaqms/iit_rss_feed_with_coordinates"
HF_URL = "https://huggingface.co/datasets/Zeel/C1/resolve/main/station_data.csv"
DG_URL = "https://api.data.gov.in/resource/3b01bcb8-0b14-4abf-b6f2-c1bfd384ba69"


def slug(s):
    import re
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")


stations = []
for name in sorted(set(live) | set(hf)):
    L, H = live.get(name), hf.get(name)
    lat = L["lat"] if L else float(H["latitude"])
    lon = L["lon"] if L else float(H["longitude"])
    city = L["city"] if L else name.split(",")[-1].split(" - ")[0].strip()
    rec = {
        "id": "caaqms-" + slug(name.replace(" - TNPCB", "").replace(" - CPCB", "")),
        "name": name,
        "kind": "CAAQMS (continuous)",
        "operator": "CPCB" if name.endswith("CPCB") else "TNPCB",
        "city": city,
        "address": (H or {}).get("address") or None,
        "cpcb_site_id": L["site_id"] if L else None,
        "lat": lat, "lon": lon,
        "loc_precision": "station coordinates as published in CPCB CCR metadata",
        "parameters": L["params"] if L else None,
        "reporting_on_2026-09-24": bool(L),
        "sources": ([f"{FEED_URL} (saved raw/emissions/caaqms/cpcb_rss_feed_with_coordinates_2026-09-24.xml)",
                     f"{DG_URL} (saved raw/emissions/caaqms/datagov_aqi_tn_2026-09-24.json)"] if L else [])
                   + ([f"{HF_URL} (third-party copy of CPCB CCR station metadata; saved raw/emissions/caaqms/hf_zeel_c1_station_data.csv)"] if H else []),
    }
    if name.startswith("Alandur"):
        rec["loc_precision"] = "SUSPECT: CPCB-metadata coordinates (12.9099, 80.1077) fall ~11 km SW of the stated address (MKN Road, St Thomas Mount/Alandur, Chennai 600016); treat as approximate"
        rec["loc_suspect"] = True
    stations.append(rec)

# NAMP manual stations near power plants (TNPCB list; no official coordinates)
nom = json.load(open(f"{RAW}/caaqms/nominatim_localities_2026-09-24.json"))
places = {e["id"]: e for e in json.load(open(f"{RAW}/caaqms/osm_places_near_plants.json"))["elements"]}
TNPCB_NAMP = "https://tnpcb.gov.in/airquality.php (saved raw/emissions/caaqms/tnpcb_airquality.php.html)"
CPCB_NAMP = "https://cpcb.nic.in/uploads/Stations_NAMP.pdf (saved raw/emissions/caaqms/cpcb_Stations_NAMP_2024-11-19.pdf; gives city counts only)"


def nomi(q, idx=0):
    r = nom[q]["results"][idx]
    return float(r["lat"]), float(r["lon"]), f"https://www.openstreetmap.org/{r['osm_type']}/{r['osm_id']}"


namp = [
    ("Kathivakkam", "Chennai", "industrial area", ("osm", 309346479)),
    ("Manali", "Chennai", "industrial area", ("nom", "Manali, Chennai")),
    ("Thiruvottiyur", "Chennai", "industrial area", ("nom", "Tiruvottiyur, Chennai")),
    ("Raja Agencies", "Thoothukudi", "industrial zone", None),
    ("SIPCOT", "Thoothukudi", "industrial zone", None),
    ("A.V.M. Building", "Thoothukudi", "residential zone", None),
    ("Raman Nagar", "Mettur", "residential zone", ("nom", "Raman Nagar, Mettur")),
    ("SIDCO", "Mettur", "industrial zone", None),
    ("Echankadu Village", "Cuddalore", "residential zone", None),
    ("DEE Office", "Cuddalore", "commercial zone", None),
    ("SIPCOT", "Cuddalore", "industrial zone", None),
]
for nm, city, zone, loc in namp:
    lat = lon = None
    prec = "unknown - TNPCB publishes no coordinates for NAMP sites"
    srcs = [TNPCB_NAMP, CPCB_NAMP]
    if loc and loc[0] == "osm":
        e = places[loc[1]]
        lat, lon = round(e["lat"], 5), round(e["lon"], 5)
        prec = f"locality only (OSM place node {loc[1]}), not the monitoring site"
        srcs.append(f"https://www.openstreetmap.org/node/{loc[1]}")
    elif loc and loc[0] == "nom":
        lat, lon, u = nomi(loc[1])
        lat, lon = round(lat, 5), round(lon, 5)
        prec = f"locality only (Nominatim result for '{loc[1]}': {u}), not the monitoring site"
        srcs.append(u)
    stations.append({
        "id": "namp-" + slug(city + "-" + nm), "name": f"{nm}, {city} (NAMP)", "kind": "NAMP manual (24-h samples twice a week; RSPM/PM10, SO2, NO2)",
        "operator": "TNPCB (CPCB-funded NAMP)", "city": city, "land_use": zone, "lat": lat, "lon": lon,
        "loc_precision": prec, "parameters": ["PM10", "SO2", "NO2"], "sources": srcs})

# near plants
for s in stations:
    if s["lat"] is None:
        s["near_plants"] = []
        continue
    near = []
    for pid, p in plants.items():
        d = hav(s["lat"], s["lon"], p["lat"], p["lon"])
        if d <= 40:
            near.append({"plant_id": pid, "distance_km": round(d, 1)})
    near.sort(key=lambda x: x["distance_km"])
    s["near_plants"] = near

# plant -> nearest continuous station
coverage = {}
for pid, p in plants.items():
    best = sorted(((hav(p["lat"], p["lon"], s["lat"], s["lon"]), s["id"]) for s in stations
                   if s["kind"].startswith("CAAQMS") and not s.get("loc_suspect")))[:2]
    coverage[pid] = [{"station_id": sid, "distance_km": round(d, 1)} for d, sid in best]

caaqms = {
    "meta": {
        "built": "2026-09-24",
        "description": "Continuous (CAAQMS) and manual (NAMP) ambient air-quality monitoring stations in Tamil Nadu, with distances to TN thermal/gas/nuclear plants (<=40 km).",
        "notes": [
            "CAAQMS list = union of (a) stations reporting on CPCB's live feed on 2026-09-24 (11 TN stations) and (b) CPCB CCR station metadata as mirrored in the HuggingFace dataset Zeel/C1 (28 TN stations). Stations only in (b) were not reporting at fetch time.",
            "CPCB's authenticated station-master API (airquality.cpcb.gov.in/projectworkflow/...get-site-station-master-data-list) returned 401; OpenAQ v3 needs an API key - not used.",
            "There is NO CAAQMS in Neyveli, Mettur, Kalpakkam or Kudankulam: nearest continuous monitors are Kudikadu (SIPCOT Cuddalore) ~32-40 km from the Neyveli stations, Sona College Salem ~35 km from Mettur, Crescent University Chengalpattu ~37 km from MAPS/PFBR, Meelavittan Thoothukudi ~84 km from Kudankulam; see plant_nearest_caaqms. NLC/NPCIL run their own EC-compliance AAQ stations (not public as coordinates).",
            "NAMP sites have no published coordinates; where given, lat/lon are locality centroids (OSM/Nominatim) and labelled as such.",
            "Distances are great-circle km between station coordinates and OSM plant centroids.",
        ],
        "plant_coords_used": plants,
        "plant_nearest_caaqms": coverage,
        "licence": "CPCB/TNPCB data: Government of India open data (GODL); OSM data (c) OpenStreetMap contributors, ODbL.",
    },
    "stations": stations,
}
json.dump(caaqms, open(f"{OUT}/caaqms_tn.json", "w"), indent=1, ensure_ascii=False)
print("stations", len(stations), "continuous", sum(1 for s in stations if s["kind"].startswith("CAAQMS")))
for pid, c in coverage.items():
    print(pid, c)
