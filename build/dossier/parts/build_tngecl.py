"""Build part_tngecl.json: TNGECL hydro / pumped storage / legacy wind records in build/SCHEMA.md format."""
import json, math
from pathlib import Path

OUT = Path(__file__).parent / "part_tngecl.json"

# ---------------- sources ----------------
DC26 = "https://www.tnpgcl.org/static/tnpdcl/assets/files/linkpdf/datacard/datacard.pdf:p7-8"   # Data card 2025-26 (as on 01.04.2026)
DC26P = "https://www.tnpgcl.org/static/tnpdcl/assets/files/linkpdf/datacard/datacard.pdf:p11-12"
DC24 = "https://www.tngecl.org/static/greenenergy/assets/files/linkpdf/datacard/datacard.pdf:p6-7"  # Data card 2023-24 (as on 01.04.2024)
WEB = "https://www.tngecl.org/en/greenenergy/trenew/hydro-generation/hydro-stations/"
WEBP = "https://www.tngecl.org/en/greenenergy/renew/hydro-generation/hydro-projects/"
PROF = "https://www.tngecl.org/en/greenenergy/about-us/tngecl-profile/"
OLD = {
    "kundah": "https://web.archive.org/web/20111206021014/http://www.tangedco.gov.in/hydrokundah.html",
    "kadam": "https://web.archive.org/web/20121013005907/http://www.tangedco.gov.in/hydrokadam.html",
    "erode": "https://web.archive.org/web/20121013005901/http://www.tangedco.gov.in/hydroerode.html",
    "koday": "https://web.archive.org/web/20121013005912/http://www.tangedco.gov.in/hydrokoday.html",
}
NPPF = "file:raw/pages/npp_tn.json#station_details"
CEAPSP = "https://cea.nic.in/wp-content/uploads/hpi/2026/02/PSP_Annex_VI_PSP_Status_of_development_-1.pdf"
WIKI = "https://en.wikipedia.org/wiki/Tamil_Nadu_Green_Energy_Corporation_Limited"
MAP = "https://web.archive.org/web/2023/https://www.tangedco.gov.in/images/hydromap.jpg"
DRIP = "https://www.tngecl.org/static/greenenergy/assets/files/"
def osm(kind, i): return f"https://www.openstreetmap.org/{kind}/{i}"
def geo(i): return f"https://globalenergyobservatory.org/geoid/{i}"

NPP = {s["station_id"]: s for s in json.load(open("./raw/pages/npp_tn.json"))["station_details"]}

def dist_km(a, b):
    (la1, lo1), (la2, lo2) = a, b
    dx = (lo2 - lo1) * 111.32 * math.cos(math.radians((la1 + la2) / 2)); dy = (la2 - la1) * 110.57
    return round(math.hypot(dx, dy), 2)

def U(spec):
    """spec: list of (mw, 'YYYY-MM' or None, make or None)"""
    return [{"no": i + 1, "mw": mw, "commissioned": c, "make": mk, "status": "operating"} for i, (mw, c, mk) in enumerate(spec)]

def res(name, lat=None, lon=None):
    return {"name": name, "kind": "reservoir", "lat": lat, "lon": lon, "share": None}

def hydro(id, name, aliases, district, lat, lon, lq, cap, units, circle, water_src, fuel_sources, route, dam_h=None, dam_len=None,
          evac=None, history="", npp=None, dgr=None, sources=(), kind="storage", status="operating", typ="hydro", notes_loc=""):
    links = {"npp_station_id": npp, "dgr_name": dgr, "cea_coal_name": None, "sldc_item": None}
    al = list(dict.fromkeys(a for a in aliases if a))
    if npp and NPP.get(npp):
        al.append(NPP[npp]["station_name"])
    if dgr: al.append(dgr)
    al = list(dict.fromkeys(al))
    h = history
    if circle: h = (h + f" TNGECL Generation Circle: {circle}.").strip()
    if notes_loc: h = (h + " Location note: " + notes_loc).strip()
    return {
        "id": id, "name": name, "aliases": al, "type": typ, "status": status,
        "state": "Tamil Nadu", "district": district, "lat": lat, "lon": lon, "loc_quality": lq,
        "capacity_mw": cap, "units": units, "operator": "TNGECL", "owner_sector": "state",
        "fuel": {"primary": "water", "grade_or_kind": kind, "sources": fuel_sources, "route": route, "annual_requirement": None},
        "water": {"source": water_src, "cooling": None},
        "structure": {"stacks": [], "cooling_towers": 0, "boiler_units": 0, "coal_yard": False, "ash_pond": None,
                      "dam_h_m": dam_h, "dam_len_m": dam_len, "hub_h_m": None, "rotor_d_m": None, "turbines": None, "area_ha": None},
        "evacuation": evac or [],
        "emissions": {"fgd": None, "co2_t_per_mwh": 0.0 if status == "operating" else None, "notes": "hydro: no combustion emissions"},
        "history": h,
        "links": links,
        "sources": list(dict.fromkeys(sources)),
    }

R = []
K, KD, ER, TV = "Kundah", "Kadamparai", "Erode", "Tirunelveli"

# ---------------- KUNDAH CIRCLE ----------------
R.append(hydro("kundah-1", "Kundah Power House I", ["Kundah PH I", "Kundah PH. I", "Kundah Power House-1", "KUNDAH I", "Kundah PH I Hydroelectric Power Plant"],
    "Nilgiris", 11.28622, 76.65145, "exact", 60,
    U([(20, "1960-07", "Dominion Engineering (turbine) / Canadian Westinghouse (generator)"), (20, "1960-07", "Dominion Engineering / Canadian Westinghouse"), (20, "1964-04", "Dominion Engineering / Canadian Westinghouse")]),
    K, "Avalanche and Emerald reservoirs (Kundah river)",
    [res("Avalanche dam", 11.3189, 76.6167), res("Emerald reservoir", None, None)],
    ["tunnel/penstock: Avalanche-Emerald -> Kundah PH-I (Pelton)", "tailrace -> Kundah Palam forebay dam -> Kundah PH-II"],
    evac=[],
    history="Commissioned 1960-64 (3x20 MW, vertical Pelton) as the first stage of the Kundah hydro-electric scheme (Canadian-supplied turbines/generators per GEO); powerhouse at Kundah Palam, elevation 5353 ft.",
    npp=100765, dgr="KUNDAH-I HPS",
    sources=[DC26, DC24, WEB, OLD["kundah"], osm("way", 823190927), geo(3916), DRIP + "drip/ESDDAvalanche030523.pdf", NPPF]))

R.append(hydro("kundah-2", "Kundah Power House II", ["Kundah PH II", "Kundah PH. II", "Kundah Power House-2", "KUNDAH II/Geddai", "Kundah2 HPP", "Kundah PH II Hydroelectric Power Plant"],
    "Nilgiris", 11.25048, 76.6802, "exact", 175,
    U([(35, "1960-10", "Dominion Engineering / Canadian General Electric"), (35, "1961-01", None), (35, "1961-05", None), (35, "1961-06", None), (35, "1964-02", None)]),
    K, "Kundah Palam forebay dam (tailrace of Kundah PH-I)",
    [res("Kundah Palam dam", 11.2833, 76.65)],
    ["Kundah Palam forebay -> head race tunnel -> penstock -> PH-II at Pegumbahallah/Geddai", "tailrace -> Geddai dam -> Kundah PH-III"],
    dam_h=None, evac=["230 kV switchyard 'Kundah2 HPP' (OSM way 1494896787)"],
    history="5x35 MW vertical Pelton units commissioned 1960-64; located at Pegumbahallah (Geddai), elevation 2876 ft.",
    npp=100820, dgr="KUNDAH-II HPS",
    sources=[DC26, DC24, WEB, OLD["kundah"], osm("way", 1463910410), osm("way", 1494896787), geo(41246), DRIP + "drip/ESDDKundahpallamdam.pdf", NPPF],
    notes_loc="NPP station_details coordinate (11.899, 79.727) is in the Cuddalore plains, ~340 km off; ignored."))

R.append(hydro("kundah-3", "Kundah Power House III", ["Kundah PH III", "Kundah Power House-3", "KUNDAH III/Parali", "Kundah3 HPP", "Parali Power House", "Kundah PH III Hydroelectric Power Plant"],
    "Coimbatore", 11.24291, 76.76948, "exact", 180,
    U([(60, "1965-04", "Vancouver Iron & Engineering / Canadian Westinghouse"), (60, "1965-06", "Vancouver Iron & Engineering / Canadian Westinghouse"), (60, "1978-02", "Dominion Engineering / Canadian General Electric")]),
    K, "Geddai dam (Pegumbahallah, Nirali Pallam, Kattery weir diversions)",
    [res("Geddai dam", None, None), res("Kattery dam", 11.3404, 76.7325)],
    ["Geddai forebay -> tunnel/penstock -> PH-III at Parali", "tailrace -> Pillur reservoir -> Kundah PH-IV"],
    evac=["230 kV switchyard 'Kundah3 HPP' (OSM way 337856906)"],
    history="3x60 MW Pelton units at Parali (elev. 1429 ft), units 1-2 in 1965, unit 3 in 1978.",
    npp=100821, dgr="KUNDAH-III HPS",
    sources=[DC26, DC24, WEB, OLD["kundah"], osm("way", 234170806), osm("way", 337856906), geo(41247), NPPF],
    notes_loc="NPP coordinate (10.939, 78.688) is near Tiruchirappalli; ignored."))

R.append(hydro("kundah-4", "Kundah Power House IV", ["Kundah PH IV", "Kundah Power House-4", "KUNDAH IV/Pillur", "Kundah4 HPP", "Pillur Power House", "Kundah PH IV Hydroelectric Power Plant"],
    "Coimbatore", 11.26048, 76.80614, "exact", 100,
    U([(50, "1966-02", "Canadian Vickers / Canadian General Electric"), (50, "1978-10", "Dominion Engineering / Canadian General Electric")]),
    K, "Pillur dam (tailrace of Kundah PH-III + Bhavani inflows)",
    [res("Pillur dam", 11.2599, 76.8059)],
    ["Pillur reservoir -> penstock -> PH-IV at dam toe (vertical Francis)", "tailrace -> Bhavani river"],
    dam_h=87.78, evac=["230 kV switchyard 'Kundah4 HPP' (OSM way 337856847)"],
    history="Tail-end station of the Kundah complex at Pillur dam; 2x50 MW Francis units (1966, 1978).",
    npp=100822, dgr="KUNDAH-IV HPS",
    sources=[DC26, DC24, WEB, OLD["kundah"], osm("way", 823190928), osm("way", 337856847), geo(41248), DRIP + "drip/ESDDPillur08022024.pdf", NPPF],
    notes_loc="NPP coordinate (10.726, 79.375) is near Thanjavur; ignored. DRIP ESDD gives Pillur dam at 11°15'N 76°41'E, which is ~13 km west of the actual dam (OSM 11.2599, 76.8059) - DRIP longitude appears wrong."))

R.append(hydro("kundah-5", "Kundah Power House V", ["Kundah PH V", "Kundah Power House-5", "Kundah PH V Hydroelectric Power Plant", "Avalanche Power House"],
    "Nilgiris", 11.30445, 76.57571, "exact", 40,
    U([(20, "1964-10", "Dominion Engineering / Canadian Westinghouse"), (20, "1989-12", "BHEL Bhopal")]),
    K, "Upper Bhavani dam and Western Catchment weir I",
    [res("Upper Bhavani dam", None, None), res("Western Catchment Weir I", 11.2508, 76.5111)],
    ["Upper Bhavani -> tunnel/penstock -> PH-V", "tailrace -> Avalanche reservoir"],
    evac=[],
    history="2x20 MW (1964, 1989) station using Upper Bhavani and Western Catchment water; discharges into Avalanche reservoir (elev. 6527 ft).",
    npp=100823, dgr="KUNDAH-V HPS",
    sources=[DC26, DC24, WEB, OLD["kundah"], osm("way", 1470127962), osm("way", 1543174843), geo(41249), DRIP + "drip/ESDDAvalanche030523.pdf", DRIP + "drip/ESDDWesternCatchmentI.pdf", NPPF],
    notes_loc="Unnamed OSM hydro plant polygon (way 1470127962) with penstock (way 1543174843) coincides with GEO 11.3044,76.5759. OSM feature named 'KUNDAH V/Avalanchi' (way 1463910409, 11.230,76.524, tagged waterway=dam) is a dam near Upper Bhavani, not the powerhouse. NPP coordinate (12.057, 79.016) is near Tiruvannamalai; ignored."))

R.append(hydro("kundah-6", "Kundah Power House VI (Parsons Valley)", ["Kundah PH VI", "Kundah Power House-6", "Kundah PH 6", "Parsons Valley Power House", "Kundah PH VI (Parsons Valley) Hydroelectric Power Plant"],
    "Nilgiris", 11.36477, 76.60426, "exact", 30,
    U([(30, "2000-03", None)]),
    K, "Parsons Valley dam, Porthimund dam, Western Catchment weirs II & III",
    [res("Parsons Valley dam", 11.3933, 76.595), res("Western Catchment Weir II", 11.3181, 76.5444), res("Western Catchment Weir III", 11.3306, 76.5547)],
    ["Parsons Valley reservoir -> penstock -> PH-VI", "tailrace -> Emerald reservoir"],
    dam_h=None, evac=["110 kV switchyard 'Kundah PH 6' (OSM way 1202687585)"],
    history="1x30 MW unit commissioned 20.03.2000 (elev. 6519 ft) using Parsons Valley storage before the water enters Emerald reservoir.",
    npp=100448, dgr="PARSON`S VALLEY HPS",
    sources=[DC26, DC24, WEB, OLD["kundah"], osm("way", 1470127963), osm("way", 1202687585), geo(41250), DRIP + "linkpdf/ESDDParsonsValleyDam(27121).pdf", NPPF]))

R.append(hydro("pykara", "Pykara Power House (Singara)", ["Pykara PH", "Singara Power House", "Pykara (Singara) Heritage Power House", "Singara Hydro Electric Power Station", "Pykara (Singara) Hydroelectric Power Plant", "PYKARA POWER HOUSE /SINGARA"],
    "Nilgiris", 11.53367, 76.60115, "exact", 59.2,
    U([(7, "1933-06", "Escher Wyss (horizontal Pelton) / Metropolitan-Vickers"), (7, "1932-11", "Escher Wyss / Metropolitan-Vickers"), (7, "1932-09", "Escher Wyss / Metropolitan-Vickers"),
       (11, "1939-08", "Escher Wyss / Metropolitan-Vickers"), (13.6, "1954-05", "Escher Wyss / Metropolitan-Vickers"), (13.6, "1954-06", "Escher Wyss / Metropolitan-Vickers")]),
    K, "Mukurthi, Pykara, Sandynallah and Glenmorgan reservoirs (Pykara river)",
    [res("Pykara dam", 11.4617, 76.6033), res("Mukurthi dam", 11.4102, 76.5637), res("Sandynallah dam", 11.4422, 76.6536), res("Glenmorgan dam", 11.503, 76.5907), res("Pykara new forebay dam", 11.4833, 76.6)],
    ["Pykara/Glenmorgan forebay -> penstocks (head ~3030 ft) -> Singara PH", "tailrace -> Maravakandy dam -> Moyar PH"],
    evac=["110 kV switchyard 'Pykara PH' (OSM way 590285279)"],
    history="First hydro scheme of the Madras Government (1929), first units 1932-33; originally 70.2 MW with 7 units, unit 4 (11 MW) damaged and removed in 2004, now 59.2 MW (3x7 + 1x11 + 2x13.6). Unit-to-rating mapping inferred from commissioning order.",
    npp=100459, dgr="PYKARA HPS",
    sources=[DC26, DC24, WEB, PROF, OLD["kundah"], osm("way", 1036169310), osm("way", 590285279), geo(41262), "https://www.tngecl.org/media/filer_public/07/a3/07a3a858-d2e6-4372-b236-7c0aa4e101a0/esdd_pykara892020.pdf", NPPF],
    notes_loc="NPP coordinate (11.4625, 76.6033) is the Pykara dam, 8 km south of the Singara powerhouse; ignored. NPP capacity 70.2 MW is the pre-2004 value."))

R.append(hydro("pykara-micro", "Pykara Micro Power House", ["Pykara Micro PH", "Pykara Mini Power House", "PYKARA MICRO POWER HOUSE"],
    "Nilgiris", 11.4617, 76.6033, "approx", 2,
    U([(2, "1989-10", None)]),
    K, "Pykara dam (toe of dam)",
    [res("Pykara dam", 11.4617, 76.6033)],
    ["Pykara dam -> dam-toe micro PH (head 25-113 ft)"],
    dam_len=193,
    history="Dam-toe micro hydel station at Pykara dam commissioned 09.10.1989. Data card lists 1x2 MW; the 2011 TANGEDCO page says 2x1 MW.",
    sources=[DC26, DC24, WEB, OLD["kundah"], osm("way", 24657704), "https://www.tngecl.org/media/filer_public/07/a3/07a3a858-d2e6-4372-b236-7c0aa4e101a0/esdd_pykara892020.pdf"],
    notes_loc="Placed at Pykara dam (DRIP ESDD 11°27'42\"N 76°36'12\"E; OSM dam way 24657704); powerhouse at dam toe not individually mapped."))

R.append(hydro("moyar", "Moyar Power House", ["Moyar PH", "Moyar Hydroelectric Power Station", "Moyar hydro-electric power house", "MOYAR POWER HOUSE"],
    "Nilgiris", 11.61399, 76.6923, "exact", 40,
    U([(14, "1952-04", "Boving (Pelton) / Metropolitan-Vickers; uprated 12->14 MW after RMU w.e.f. 11.12.2024"), (14, "1952-09", "Boving / Metropolitan-Vickers; uprated 12->14 MW after RMU w.e.f. 10.11.2025"), (12, "1953-01", "Boving / Metropolitan-Vickers")]),
    K, "Moyar forebay dam and Maravakandy dam (tailrace of Pykara PH / PUSHEP)",
    [res("Moyar forebay dam", 11.6044, 76.6919), res("Maravakandy dam", 11.5731, 76.6547)],
    ["Pykara + PUSHEP tailrace -> Maravakandy dam -> Moyar forebay -> penstock -> PH at bottom of Moyar gorge"],
    dam_h=13.0, dam_len=731.0, evac=["110 kV switchyard 'Moyar PH' (OSM way 590285278)"],
    history="3x12 MW (1952-53); capacity raised to 40 MW after RMU of units 1 and 2 (2024-25). Website still lists 36 MW.",
    npp=100480, dgr="MOYAR  HPS",
    sources=[DC26, DC24, WEB, OLD["kundah"], osm("way", 1036169314), osm("way", 590285278), geo(41260), DRIP + "linkpdf/ESDDMOYAR23092022.pdf", NPPF]))

R.append(hydro("maravakandy-micro", "Maravakandy Mini Micro Power House", ["Maravakandy PH", "Maravakandy Mini PH", "Maravakandy Hydroelectric Power Station", "MARAVAKANDY POWER HOUSE"],
    "Nilgiris", 11.57471, 76.65399, "exact", 0.75,
    U([(0.75, "1992-10", None)]),
    K, "Maravakandy dam (toe of dam; Pykara PH tailrace)",
    [res("Maravakandy dam", 11.5731, 76.6547)],
    ["Maravakandy dam -> dam-toe micro PH"],
    dam_h=17.3, dam_len=414.5, evac=["110 kV substation 'Maravakandy PH' (OSM way 1036169312)"],
    history="1x0.75 MW dam-toe micro hydel commissioned 14.10.1992.",
    sources=[DC26, DC24, WEB, OLD["kundah"], osm("way", 1036169313), osm("way", 1036169312), DRIP + "linkpdf/MaravakandyESDD.pdf"]))

R.append(hydro("mukurthy-micro", "Mukurthy Mini Power House", ["Mukurthy Mini PH", "Mukkuruthy Power House", "Mukurthi Micro Power House", "MUKURTHY MICRO POWER HOUSE"],
    "Nilgiris", 11.4102, 76.5637, "approx", 0.7,
    U([(0.35, "2001-06", None), (0.35, "2003-11", None)]),
    K, "Mukurthi dam (toe of dam)",
    [res("Mukurthi dam", 11.4102, 76.5637)],
    ["Mukurthi dam -> dam-toe mini PH"],
    dam_h=34.0, dam_len=161.54,
    history="2x0.35 MW mini hydel at the toe of Mukurthi dam (elev. 6800 ft), units 2001 and 2003.",
    sources=[DC26, DC24, WEB, OLD["kundah"], osm("way", 622366324), "https://www.tngecl.org/media/filer_public/1b/f1/1bf1933e-cb31-42b0-93ed-c43db5783936/mukurthy_dam.pdf"],
    notes_loc="Placed at Mukurthi dam (OSM way 622366324; DRIP gives 11°24'N 76°34'E); powerhouse not individually mapped."))

R.append(hydro("pushep", "Pykara Ultimate Stage Hydro Electric Project (PUSHEP)", ["PUSHEP", "PUSHEPH", "Pykara Ultimate Stage HEP", "Pykara Ultimate Stage Hydroelectric Power Plant", "Pykara (PUSHEP) Ultimate Stage Hydroelectric Power Plant"],
    "Nilgiris", 11.52276, 76.60087, "exact", 150,
    U([(50, None, None), (50, None, None), (50, None, None)]),
    K, "Pykara new forebay dam (Pykara, Mukurthi, Sandynallah, Glenmorgan storages)",
    [res("Pykara new forebay dam", 11.4833, 76.6), res("Sandynallah dam", 11.4422, 76.6536)],
    ["Pykara new forebay -> underground PH (3x50 MW)", "tailrace -> Maravakandy -> Moyar PH"],
    evac=["230 kV switchyard 'PUSHEP' (OSM way 357561237)"],
    history="Underground 3x50 MW station commissioned 06.09.2005 (per 2011 TANGEDCO page), using the same Pykara storages as the Singara powerhouse. Surface switchyard location given.",
    npp=100497, dgr="PYKARA ULTMATE HPS",
    sources=[DC26, DC24, WEB, OLD["kundah"], osm("node", 9546484166), osm("way", 357561237), geo(41266), NPPF, "https://www.tngecl.org/media/filer_public/74/a3/74a35e08-071b-4d1e-a0a4-229dc9486295/pykara_new_forebay_dam.pdf"]))

# ---------------- KADAMPARAI CIRCLE ----------------
R.append(hydro("kadamparai-psp", "Kadamparai Pumped Storage Power House", ["Kadamparai PH", "Kadamparai Power House", "Kadamparai Hydroelectric Power Plant", "Kadamparai Hydroelectric Pumped Storage Power Plant", "KADAMPARAI POWER HOUSE (PUMPED STORAGE SCHEME)"],
    "Coimbatore", 10.41042, 77.04337, "exact", 400,
    U([(100, "1987-10", "Boving (reversible Francis) / GEC UK"), (100, "1988-02", "BHEL Bhopal"), (100, "1989-04", "BHEL Bhopal"), (100, "1988-12", "BHEL Bhopal")]),
    KD, "Kadamparai reservoir (upper) / Upper Aliyar reservoir (lower)",
    [res("Kadamparai dam (upper reservoir)", 10.3938, 77.0457), res("Upper Aliyar dam (lower reservoir)", 10.4376, 77.0132)],
    ["generation: Kadamparai reservoir -> underground PH -> Upper Aliyar", "pumping (off-peak): Upper Aliyar -> Kadamparai"],
    evac=["230 kV switchyard 'Kadamparai' (OSM way 373398388)"],
    history="First underground pumped-storage scheme of TNEB, in the Anamalai hills (Pollachi taluk); 4x100 MW reversible units commissioned 1987-89. Pump mode at night when frequency >49.4 Hz.",
    npp=100205, dgr="KADAMPARI HPS", typ="pumped_storage", kind="pumped storage",
    sources=[DC26, DC24, WEB, PROF, OLD["kadam"], osm("node", 9567098999), osm("way", 373398388), geo(3766), NPPF, CEAPSP],
    notes_loc="Underground powerhouse; coordinate is the surface switchyard (OSM + GEO agree). NPP coordinate (10.3896, 77.0435) is 2.3 km south near Kadamparai dam."))

R.append(hydro("aliyar", "Aliyar Power House", ["Aliyar PH", "Aliyar hydro power station", "Aliyar Hydroelectric Power Plant", "ALIYAR POWER HOUSE", "Aliyar Power Hosue"],
    "Coimbatore", 10.45467, 77.00784, "exact", 60,
    U([(60, "1970-03", "Neyrpic (vertical Pelton) / Alstom")]),
    KD, "Upper Aliyar reservoir (Parambikulam-Aliyar Project)",
    [res("Upper Aliyar dam", 10.4376, 77.0132)],
    ["Upper Aliyar -> tunnel/penstock -> PH at Navamalai", "tailrace -> Aliyar reservoir"],
    evac=["230/110 kV substation 'Aliyar' (OSM way 373398416)"],
    history="1x60 MW Pelton unit commissioned 21.03.1970 at Navamalai (elev. 1083 ft), part of the Parambikulam-Aliyar Project.",
    npp=100495, dgr="ALIYAR  HPS",
    sources=[DC26, DC24, WEB, OLD["kadam"], osm("way", 373398417), osm("way", 373398416), geo(41259), NPPF],
    notes_loc="NPP coordinate (10.4718, 76.9729) is near Aliyar dam, ~4 km NW of the powerhouse."))

R.append(hydro("aliyar-mini", "Aliyar Mini Power House", ["Aliyar Mini PH", "Mini Aliyar Power House", "ALIYAR MINI POWER HOUSE", "Lower Aliyar Mini PH"],
    "Coimbatore", 10.48422, 76.96603, "approx", 2.5,
    U([(1.25, "2002-09", None), (1.25, "2002-09", None)]),
    KD, "Aliyar (lower) reservoir",
    [res("Aliyar dam", 10.4828, 76.9709)],
    ["Aliyar dam -> irrigation outlet mini PH"],
    history="2x1.25 MW irrigation mini hydel at Aliyar dam, commissioned 23.09.2002.",
    sources=[DC26, DC24, WEB, OLD["kadam"], osm("way", 1468881080), osm("way", 84635275)],
    notes_loc="Unnamed OSM hydro plant (way 1468881080) 0.5 km from Aliyar dam; identification by proximity only."))

R.append(hydro("sarkarpathy", "Sarkarpathy Power House", ["Sarkarpathy PH", "Sakarapathy Power House", "Sarkarpathy Hydroelectric Power Plant", "SARKARPATHY POWER HOUSE"],
    "Coimbatore", 10.47044, 76.85848, "exact", 30,
    U([(30, "1966-08", "Hitachi (vertical Francis) / Hitachi")]),
    KD, "Parambikulam and Thunakadavu reservoirs (Parambikulam-Aliyar Project)",
    [res("Parambikulam reservoir", 10.3859, 76.8087)],
    ["Parambikulam/Thunakadavu -> contour tunnel -> Sarkarpathy PH", "tailrace -> Parambikulam-Aliyar contour canal"],
    evac=["110 kV substation 'Sarkarpathy' (OSM way 370180423)"],
    history="1x30 MW unit commissioned 14.08.1966 (elev. 1429 ft), part of the Parambikulam-Aliyar Project (irrigation).",
    npp=100512, dgr="SARKARPATHY HPS",
    sources=[DC26, DC24, WEB, OLD["kadam"], osm("node", 337555791), osm("way", 370180423), NPPF, geo(41258)],
    notes_loc="OSM node + OSM substation + NPP agree within 0.3 km; GEO point (10.4558, 76.8302) is 3.3 km off."))

R.append(hydro("sholayar-1", "Sholayar Power House I", ["Sholayar PH-I", "Sholayar Power Hosue - 1", "SHOLAYAR POWER HOUSE – I", "Sholayar I Hydroelectric Power House", "SHOLAYAR I&II"],
    "Coimbatore", 10.35563, 76.88054, "exact", 84,
    U([(42, "1971-04", "Litostroj (vertical Francis) / Rade Koncar; uprated 35->42 MW"), (42, "1971-05", "Litostroj / Rade Koncar; uprated 35->42 MW")]),
    KD, "Upper Sholayar reservoir",
    [res("Upper Sholayar dam", 10.2958, 76.8795)],
    ["Upper Sholayar -> tunnel -> PH-I at Manomboli", "tailrace -> Parambikulam system"],
    history="Commissioned April-May 1971 as 2x35 MW at Manomboli (elev. 1931 ft); now 2x42 MW. Sholayar water is shared inter-state with Kerala.",
    npp=100294, dgr="SHOLAYAR HPS (TN)",
    sources=[DC26, DC24, WEB, OLD["kadam"], osm("way", 1463910406), geo(41254), NPPF],
    notes_loc="OSM polygon 'SHOLAYAR I&II' and GEO 'Sholayar I' agree (0.2 km). The DGR/NPP entry 'SHOLAYAR HPS (TN)' (84 MW) matches PH-I capacity but its coordinate (10.2983, 76.8808) sits at PH-II near the dam."))

R.append(hydro("sholayar-2", "Sholayar Power House II", ["Sholayar PH-II", "Sholayar Power Hosue - 2", "SHOLAYAR POWER HOUSE – II", "Sholayar II Hydroelectric Power House"],
    "Coimbatore", 10.30367, 76.87338, "exact", 25,
    U([(25, "1971-03", "Litostroj (vertical Francis) / Rade Koncar")]),
    KD, "Upper Sholayar reservoir",
    [res("Upper Sholayar dam", 10.2958, 76.8795)],
    ["Upper Sholayar dam -> PH-II below dam", "tailrace -> Lower Sholayar (Kerala)"],
    history="1x25 MW unit commissioned 29.03.1971 near Sholayar dam (elev. 2750 ft); releases water to Kerala under inter-state sharing.",
    sources=[DC26, DC24, WEB, OLD["kadam"], osm("way", 1468881078), geo(41255), NPPF],
    notes_loc="Unnamed OSM hydro plant way 1468881078, GEO 'Sholayar II' (0.6 km) and the NPP 'SHOLAYAR HPS (TN)' point (1.2 km) cluster here."))

R.append(hydro("thirumurthy-mini", "Thirumurthy Mini Power House", ["Thirumurthy Mini PH", "Thirumoorthy Power House", "THIRUMURTHY MINI PH."],
    "Tiruppur", 10.4748, 77.1485, "approx", 1.95,
    U([(0.65, "2000-03", None), (0.65, "2000-03", None), (0.65, "2000-03", None)]),
    KD, "Thirumurthy dam (irrigation)",
    [res("Thirumoorthi dam", 10.4748, 77.1485)],
    ["Thirumurthy dam -> irrigation outlet mini PH"],
    history="3x0.65 MW irrigation mini hydel near Udumalpet, commissioned 20.03.2000.",
    sources=[DC26, DC24, WEB, OLD["kadam"], osm("way", 840910471)],
    notes_loc="Placed at Thirumoorthi dam (OSM way 840910471); powerhouse not mapped."))

R.append(hydro("poonachi-mini", "Poonachi Mini Power House", ["Poonachi Mini PH", "Poonachi Power Hosue", "POONACHI MINI PH", "Punachi"],
    "Coimbatore", None, None, "approx", 2,
    U([(1, "1992-11", None), (1, "1992-12", None)]),
    KD, "Punachi river (run-of-river)",
    [res("Punachi river (run of river)", None, None)],
    ["run-of-river diversion -> mini PH"],
    kind="run-of-river",
    history="2x1 MW run-of-river mini hydel commissioned Nov-Dec 1992, Kadamparai circle; the TANGEDCO schematic map shows it between Aliyar and Kadamparai (Anamalai hills).",
    sources=[DC26, DC24, WEB, OLD["kadam"], MAP],
    notes_loc="Exact location unknown; not in OSM/GEO/NPP. OSM substation 'Poonachi' (Anthiyur, Erode) is a different place."))

R.append(hydro("amaravathi", "Amaravathi Power House", ["Amaravathy Power House", "Amaravathi PH", "AMARAVATHI", "Amaravathy Power Hosue"],
    "Tiruppur", 10.4181, 77.2638, "approx", 4,
    U([(2, "2006-09", None), (2, "2006-11", None)]),
    KD, "Amaravathi reservoir (irrigation)",
    [res("Amaravathi dam", 10.4181, 77.2638)],
    ["Amaravathi dam -> irrigation outlet PH"],
    history="2x2 MW irrigation hydel at Amaravathi dam, commissioned Sept-Nov 2006.",
    sources=[DC26, DC24, WEB, OLD["kadam"], osm("way", 203611386)],
    notes_loc="Placed at Amaravathi dam (OSM way 203611386); powerhouse not mapped."))

# ---------------- ERODE CIRCLE ----------------
R.append(hydro("mettur-dam", "Mettur Dam Power House", ["Mettur Dam PH", "Dam Power Hosue/Mettur", "METTUR DAM POWER HOUSE", "Mettur Dam and Tunnel Hydro Power Plant"],
    "Salem", 11.8007, 77.80962, "exact", 50,
    U([(12.5, "1937-06", "BTH England (horizontal Francis); renovated 2007-04"), (12.5, "1937-08", "BTH England; renovated 2004-09"), (12.5, "1938-01", "BTH England; renovated 2006-08"), (12.5, "1946-10", "BTH England; renovated 2005-01")]),
    ER, "Stanley reservoir (Mettur dam, Cauvery) - irrigation releases",
    [res("Mettur dam / Stanley reservoir", 11.8035, 77.8063)],
    ["Mettur dam -> dam-toe PH (head 18-49 m)", "tailrace -> Cauvery -> Lower Mettur barrages"],
    dam_h=40, dam_len=1700, evac=["110 kV substation 'Mettur Dam PH' (OSM way 340479153)"],
    history="4x12.5 MW units 1937-46 at the toe of Mettur (Stanley) dam, renovated 2004-07. Dam height/length from GEO.",
    npp=100472, dgr="METTUR DAM HPS",
    sources=[DC26, DC24, WEB, OLD["erode"], osm("way", 429967365), osm("way", 340479153), geo(4261), NPPF]))

R.append(hydro("mettur-tunnel", "Mettur Tunnel Power House", ["Mettur Tunnel PH", "Tunnel Power Hosue/Mettur", "METTUR TUNNEL POWER HOUSE"],
    "Salem", 11.79797, 77.81076, "exact", 200,
    U([(50, "1965-08", "Machinoexport USSR (vertical Kaplan)"), (50, "1966-07", "Machinoexport USSR"), (50, "1966-07", "Machinoexport USSR"), (50, "1966-07", "Machinoexport USSR")]),
    ER, "Stanley reservoir (Mettur dam) via tunnel - irrigation releases",
    [res("Mettur dam / Stanley reservoir", 11.8035, 77.8063)],
    ["Stanley reservoir -> tunnel -> Tunnel PH", "tailrace -> Cauvery"],
    evac=["230 kV switchyard 'Mettur Tunnel Power House' (OSM way 340479063)"],
    history="4x50 MW Kaplan units commissioned 1965-66 (Soviet supply).",
    npp=100473, dgr="METTUR TUNNEL HPS",
    sources=[DC26, DC24, WEB, OLD["erode"], osm("way", 429967367), osm("way", 340479063), geo(4261), NPPF],
    notes_loc="NPP coordinate (11.772, 77.806) is 2.9 km south (near Mettur TPS); OSM polygon + switchyard used."))

for i, (vil, dist, lat, lon, osmw, npp, dgr, units, extra_src) in enumerate([
    ("Chekkanur", "Salem", 11.72751, 77.77932, 429967361, 100218, "LOWER METTUR-I HPS", [(15, "1988-08"), (15, "1988-08")], [osm("way", 340479170)]),
    ("Nerinjipettai", "Erode", 11.6436, 77.75647, 429967362, 100824, "LOWER METTUR-II HPS", [(15, "1988-08"), (15, "1988-08")], [geo(4099)]),
    ("Kuthiraikalmedu (Koneripatti)", "Erode", 11.5752, 77.74198, 429967363, 100825, "LOWER METTUR-III HPS", [(15, "1988-01"), (15, "1988-09")], []),
    ("Uratchikottai", "Erode", 11.48545, 77.70171, 429967364, 100826, "LOWER METTUR-IV HPS", [(15, "1989-09"), (15, "1988-12")], [osm("way", 508747380)]),
], start=1):
    rom = ["I", "II", "III", "IV"][i - 1]
    R.append(hydro(f"lower-mettur-{i}", f"Lower Mettur Barrage Power House {rom} ({vil})",
        [f"Lower Mettur Barrage PH-{rom}", f"LM Barrage Power Hosue {i}/ {vil.split(' ')[0]}", f"LMHEP-{i}", f"Lower Mettur Barrage {rom} Power House", "Lower Mettur (LMHEP) Hydro Power Plant"],
        dist, lat, lon, "exact", 30,
        U([(mw, c, "Fuji Electric (bulb turbine/generator)") for mw, c in units]),
        ER, "Cauvery river pondage below Mettur dam (irrigation releases)",
        [res("Mettur dam / Stanley reservoir", 11.8035, 77.8063)],
        ["Mettur releases -> Cauvery -> barrage pondage -> bulb units (head 3-7.5 m)"],
        kind="run-of-river (barrage)",
        evac={1: ["110 kV substation 'Lower Mettur Barrage I PH' (OSM way 340479170)"], 4: ["110 kV substation 'Lower Mettur Barrage IV PH' (OSM way 508747380)"]}.get(i, []),
        history=f"One of four barrage powerhouses (Lower Mettur Hydro-Electric Project, 4x2x15 MW bulb units, Fuji Electric) built 1987-89 on the Cauvery below Mettur; near {vil}.",
        npp=npp, dgr=dgr,
        sources=[DC26, DC24, WEB, OLD["erode"], osm("way", osmw), NPPF] + extra_src,
        notes_loc="NPP coordinate for this station is wrong (off by >8 km; II-IV are 50-150 km away); OSM named polygon used."))

for i, (vil, dist, lat, lon, osmw, npp, dgr, units, gid, hist) in enumerate([
    ("Samayasangili", "Namakkal", 11.38418, 77.71474, 429967371, 100295, "BHAWANI KATTAL", [(15, "2006-08"), (15, "2006-09")], 41243, "commissioned Aug-Sep 2006."),
    ("Vendipalayam", "Erode", 11.33091, 77.75807, 429967370, 100117, "BHAWANI BARRAGE-II HPS", [(15, "2011-07"), (15, "2011-09")], 44619, "units dated 28.07.2011 and 29.09.2011 by the TANGEDCO page; GEO gives 2013."),
    ("Cholasiramani", "Namakkal", 11.24286, 77.86595, 429967372, 100118, "BHAWANI BARRAGE-III HPS", [(15, None), (15, None)], 44620, "commissioned 2012-13 (GEO); exact unit dates not found."),
], start=1):
    rom = ["I", "II", "III"][i - 1]
    loc = "OSM polygon, NPP and GEO agree." if i == 1 else ("NPP coordinate (11.3077, 77.7399) is 3.2 km off; OSM polygon + GEO agree." if i == 2 else "NPP coordinate for 'BHAWANI BARRAGE-III HPS' duplicates Bhavani Kattalai-I (11.385, 77.716), ~23 km off; OSM polygon + GEO agree.")
    R.append(hydro(f"bhavani-kattalai-{i}", f"Bhavani Kattalai Barrage Power House {rom} ({vil})",
        [f"Bhavani Kattalai Barrage PH-{rom}", f"BK Barrage Power Hosue {i}/ {vil}", f"Bhavani Kattalai {rom}", f"Bhawani Kattalai Barrage {rom} Hydroelectric Power Plant", f"Bhavani Kattalai {rom} Hydroelectric Power Plant", f"BHAVANI KATTALAI BARRGAE - {rom}"],
        dist, lat, lon, "exact", 30, U([(mw, c, None) for mw, c in units]),
        ER, "Cauvery river pondage (below Lower Mettur barrages)",
        [res("Mettur dam / Stanley reservoir", 11.8035, 77.8063)],
        ["Mettur releases -> Cauvery -> barrage pondage -> bulb units"],
        kind="run-of-river (barrage)",
        history=f"Barrage powerhouse (2x15 MW) on the Cauvery between Bhavani and Pasur; {hist}",
        npp=npp, dgr=dgr,
        sources=[DC26, DC24, WEB, OLD["erode"], osm("way", osmw), geo(gid), NPPF], notes_loc=loc))

R.append(hydro("sathanur", "Sathanur Dam Power House", ["Sathanur Dam PH", "Sathanur Power House", "SATHANUR", "Sathanur Dam Hydroelectric Power Plant"],
    "Tiruvannamalai", 12.18266, 78.85137, "exact", 7.5,
    U([(7.5, "1999-03", None)]),
    ER, "Sathanur reservoir (Thenpennai river, irrigation)",
    [res("Sathanur dam", 12.1832, 78.8503)],
    ["Sathanur dam -> dam-toe PH"],
    dam_h=36.28,
    history="1x7.5 MW irrigation hydel at Sathanur dam (Chengam taluk), commissioned 10.03.1999. Dam height from GEO.",
    sources=[DC26, DC24, WEB, OLD["erode"], osm("way", 995868195), geo(41244)]))

R.append(hydro("lower-bhavani-micro", "Lower Bhavani Micro Hydel Power House (Bhavanisagar)", ["Lower Bhavani Micro Hydel PH", "Micro Hydel Power Hosue/ Bhavani Sagar", "LOWER BHAVANI -1/Micro Hydel PH/Bhavani Sagar", "BhavaniSagar Micro PH", "Bhavanisagar hydroelectric power station", "LB Micro"],
    "Erode", 11.47084, 77.11513, "exact", 8,
    U([(2, "1990-05", None), (2, "1990-04", None), (2, "1990-04", None), (2, "1990-04", None)]),
    ER, "Bhavanisagar (Lower Bhavani) reservoir - irrigation releases",
    [res("Bhavanisagar dam", 11.4739, 77.106)],
    ["Bhavanisagar dam -> dam-toe micro PH"],
    evac=["110 kV substation 'BhavaniSagar Micro PH' (OSM way 336571787)"],
    history="4x2 MW micro hydel at Bhavanisagar dam commissioned April-May 1990. The OSM relation tags 32 MW, which does not match any official figure.",
    sources=[DC26, DC24, WEB, OLD["erode"], osm("relation", 13876404), osm("way", 336571787)]))

R.append(hydro("lower-bhavani-rbc", "Lower Bhavani Right Bank Canal Power House", ["Lower Bhavani RBC", "LBRBC", "RBC Power Hosue/ Bhavani Sagar", "LOWER BHAVANI RBC", "Lower Bhavani Right Bank Canal PH"],
    "Erode", 11.4739, 77.106, "approx", 8,
    U([(4, "1998-02", None), (4, "1998-02", None)]),
    ER, "Bhavanisagar reservoir - Right Bank Canal releases",
    [res("Bhavanisagar dam", 11.4739, 77.106)],
    ["Bhavanisagar dam -> Right Bank Canal head -> canal PH"],
    history="2x4 MW canal-head powerhouse at Bhavanisagar (18 km from Sathyamangalam), commissioned Feb 1998.",
    sources=[DC26, DC24, WEB, OLD["erode"], osm("way", 164744315)],
    notes_loc="Placed at Bhavanisagar dam centre (OSM way 164744315); canal-head powerhouse not individually mapped."))

for i, (vil, lat, lon, osmw) in enumerate([("Samayapuram", 11.31654, 76.94553, 1468887801), ("Umaipalayam", 11.30703, 76.90003, 1470127960)], start=1):
    R.append(hydro(f"bhavani-barrage-{i}", f"Bhavani Barrage Power House {i} ({vil})",
        [f"Bhavani Barrage {i} PH", f"BB Power Hosue {i}/ {vil}", f"Bhavani Barrage PH-{'I' * i}"],
        "Coimbatore", lat, lon, "approx", 10,
        U([(5, None, "bulb turbines" + (" (SSEB EPC)" if i == 1 else "")), (5, None, None)]),
        ER, "Bhavani river pondage (downstream of Pillur/Kundah releases, near Mettupalayam)",
        [res("Bhavani river barrage pondage", lat, lon)],
        ["Bhavani river barrage -> bulb units"],
        kind="run-of-river (barrage)",
        history=f"2x5 MW bulb-turbine barrage powerhouse on the Bhavani near Mettupalayam ({vil}). Commissioning dates not found (post-2012; not on 2011-12 TANGEDCO pages).",
        sources=[DC26, DC24, WEB, osm("way", osmw), "https://www.sseb.in/projects/completed-projects/bhavani-barrage-1.php"],
        notes_loc="Two unnamed OSM hydro plant polygons on the Bhavani near Mettupalayam; satellite imagery shows a barrage with an attached powerhouse at each. Which is PH-1 (Samayapuram) and which PH-2 (Umaipalayam) is inferred, not confirmed."))

# ---------------- TIRUNELVELI CIRCLE ----------------
R.append(hydro("kodayar-1", "Kodayar Power House I", ["Kodayar PH I", "Kodayar Power Hosue 1", "KODAYAR POWER HOUSE – I", "Kodayar I Hydroelectric Power Plant"],
    "Kanyakumari", 8.52249, 77.35688, "approx", 60,
    U([(60, "1970-12", "Vevey Engineering (vertical Pelton) / Alstom")]),
    TV, "Upper Kodayar reservoir (Kodayar Dam-I)",
    [res("Upper Kodayar dam (Kodayar Dam-I)", 8.5221, 77.3596)],
    ["Upper Kodayar -> PH-I", "tailrace -> Lower Kodayar (Kodayar Dam-II) reservoir -> Kodayar PH-II"],
    history="1x60 MW unit commissioned 09.12.1970.",
    npp=100761, dgr="KODAYAR-I HPS",
    sources=[DC26, DC24, WEB, OLD["koday"], osm("way", 1431930232), osm("way", 204957247), geo(3878), NPPF, "https://www.tngecl.org/media/filer_public/68/b0/68b06a66-d91d-4b66-bb2e-f0c33bd4ee80/kodayar_ii_dam.pdf"],
    notes_loc="Sources disagree. Placed at an unnamed OSM hydro plant polygon (way 1431930232) just below Upper Kodayar dam, which fits the DRIP statement that Kodayar Dam-II receives PH-I tail water. OSM 'KODAYAR-I&II' and GEO 'Kodayar I' (8.532, 77.312) sit on Kodayar Dam-II instead. NPP (8.486, 77.280) is ~9 km away."))

R.append(hydro("kodayar-2", "Kodayar Power House II", ["Kodayar PH II", "Kodayar Power Hosue 2", "KODAYAR POWER HOUSE – II", "Kodayar II Hydroelectric Power Plant"],
    "Kanyakumari", 8.5032, 77.3122, "approx", 40,
    U([(40, "1971-11", "Litostroj (vertical Francis) / Rade Koncar")]),
    TV, "Lower Kodayar reservoir (Kodayar Dam-II, forebay)",
    [res("Kodayar Dam-II (Lower Kodayar)", 8.5294, 77.3117)],
    ["Kodayar Dam-II forebay -> tunnel/penstock (~2.7 km) -> PH-II", "tailrace -> Pechiparai reservoir"],
    dam_h=61, dam_len=152,
    history="1x40 MW unit commissioned 17.11.1971 (elev. 340.8 m). Kodayar Dam-II (61 m high, 152 m long) is its forebay.",
    npp=100819, dgr="KODAYAR-II HPS",
    sources=[DC26, DC24, WEB, OLD["koday"], geo(41257), NPPF, "https://www.tngecl.org/media/filer_public/68/b0/68b06a66-d91d-4b66-bb2e-f0c33bd4ee80/kodayar_ii_dam.pdf"],
    notes_loc="GEO point only (2.9 km south of Dam-II, consistent with GEO's 2672 m from dam); not verified on OSM. NPP coordinate (11.226, 79.426) is in Cuddalore district; ignored."))

R.append(hydro("servalar", "Servalar Power House", ["Servalar PH", "Servalar Power Hosue", "SERVALAR POWER HOUSE", "Servalar Hydroelectric Power Plant"],
    "Tirunelveli", 8.68939, 77.30483, "exact", 20,
    U([(20, "1986-03", "BHEL Haridwar (vertical Kaplan)")]),
    TV, "Servalar dam (interlinked with Karaiyar dam by 3.3 km tunnel)",
    [res("Servalar dam", 8.6895, 77.3048), res("Karaiyar (Papanasam upper) reservoir", 8.645, 77.3064)],
    ["Karaiyar -> tunnel -> Servalar dam -> dam-toe PH (head 22-55 m)", "tailrace -> Papanasam forebay"],
    dam_h=57.1, dam_len=88, evac=["110 kV substation 'Servalar' (OSM way 1199229609)"],
    history="1x20 MW Kaplan unit at the toe of Servalar dam, commissioned 23.03.1986.",
    sources=[DC26, DC24, WEB, OLD["koday"], osm("way", 1463910407), osm("way", 1199229609), geo(41263), DRIP + "linkpdf/ESDD%20Servalar%20Dam.pdf"],
    notes_loc="The DRIP ESMP gives Servalar dam at 8°41'40\"N 77°08'10\"E; the longitude is ~18 km off (probably a typo for 77°18'); OSM/GEO used."))

R.append(hydro("papanasam", "Papanasam Power House", ["Papanasam PH", "Papanasam Power Hosue", "PAPANASAM POWER HOUSE", "Papanasam Hydroelectric Power Plant"],
    "Tirunelveli", 8.70658, 77.36265, "exact", 32,
    U([(8, "1944-07", "English Electric (vertical Francis); renovated 2004-02"), (8, "1944-12", "English Electric; renovated 2004-06"), (8, "1945-06", "English Electric; renovated 2005-07"), (8, "1951-07", "English Electric; renovated 2005-10")]),
    TV, "Papanasam (Karaiyar) reservoir, Thamirabarani river",
    [res("Papanasam dam", 8.6507, 77.3115), res("Karaiyar reservoir", 8.645, 77.3064)],
    ["Papanasam/Karaiyar -> forebay -> penstock -> PH", "tailrace -> Thamirabarani (irrigation)"],
    evac=["110 kV substation 'Papanasam' (OSM way 309492199)"],
    history="4x8 MW units 1944-51, renovated 2004-05; irrigation station on the Thamirabarani.",
    npp=100447, dgr="PAPANASAM HPS",
    sources=[DC26, DC24, WEB, OLD["koday"], osm("way", 1463910408), osm("way", 309492199), geo(41261), NPPF],
    notes_loc="NPP coordinate (8.712, 77.393) is 3.4 km east; OSM polygon + substation + GEO agree."))

R.append(hydro("suruliyar", "Suruliyar Power House", ["Suruliyar PH", "Suruliyar Power Hosue", "SURULIYAR POWER HOUSE", "Suruliyar Hydroelectric Power Plant"],
    "Theni", 9.62023, 77.27265, "exact", 35,
    U([(35, "1978-08", "Voith Austria (horizontal Pelton) / Elin Union")]),
    TV, "Suruliyar (tributary of Vaigai): Eravangalar, Vennirar and Manalar dams",
    [res("Manalar dam", 9.638, 77.3459), res("Vennirar dam", 9.6081, 77.3008)],
    ["High Wavys dams -> tunnel/penstock (rated head 979 m) -> PH", "tailrace -> Suruli river"],
    evac=["110 kV substation 'Suruliyar' (OSM way 310070120)"],
    history="1x35 MW Pelton unit commissioned 27.08.1978 with a rated head of 979 m.",
    npp=100527, dgr="SURULIYAR HPS",
    sources=[DC26, DC24, WEB, OLD["koday"], osm("way", 310070120), geo(41264), NPPF, "https://www.tngecl.org/media/filer_public/4f/d2/4fd2b734-ac89-42fd-bef8-d5d21e02076d/manalar_dam.pdf", DRIP + "linkpdf/esddvenirardam(270121).pdf"]))

R.append(hydro("periyar", "Periyar Power House", ["Periyar PH", "Periyar Power Hosue", "PERIYAR POWER HOUSE", "Periyar hydro power station", "Periyar Hydroelectric Power Project", "Lower Camp Power House"],
    "Theni", 9.6267, 77.19052, "exact", 168,
    U([(42, "1958-10", "J.M. Voith (vertical Francis) / AEG; renovated 2011-07"), (42, "1959-02", "J.M. Voith / AEG; renovated and uprated 2012-09"), (42, "1959-06", "J.M. Voith / AEG; uprated 35->42 MW"), (42, "1965-12", "Litostroj / Rade Koncar; uprated 35->42 MW")]),
    TV, "Mullaperiyar reservoir (Kerala) via tunnel and Periyar forebay dam",
    [res("Periyar forebay dam", 9.6464, 77.2148)],
    ["Mullaperiyar -> tunnel -> Periyar forebay dam -> penstocks (rated head 373 m) -> PH at Lower Camp", "tailrace -> Periyar-Vaigai canal -> Vaigai dam"],
    dam_h=37.8, dam_len=88, evac=["110 kV substation 'Periyar PH' (OSM way 310070102)"],
    history="Units commissioned 1958-65 at Lower Camp (elev. 1574 ft); after renovation and uprating all four units are 42 MW (168 MW). Older sources list 140 MW (4x35), 154 MW or 161 MW. dam_h/dam_len refer to the forebay dam.",
    npp=100454, dgr="PERIYAR HPS",
    sources=[DC26, DC24, WEB, OLD["koday"], osm("way", 310070118), osm("way", 310070102), osm("way", 831548783), geo(4756), DRIP + "drip/ESDDPeriyaarDam010221.pdf", NPPF],
    notes_loc="NPP coordinate (9.6461, 77.2148) is the Periyar forebay dam (OSM way 842918866), 3.4 km NE of the powerhouse. NPP capacity 126 MW is stale."))

R.append(hydro("vaigai-micro", "Vaigai Small Power House", ["Vaigai Small PH", "Vaigai MPH", "Vaigai Power House", "VAIGAI POWER HOUSE", "VAIGAI DAM"],
    "Theni", 10.05377, 77.5906, "exact", 6,
    U([(3, "1990-03", None), (3, "1990-03", None)]),
    TV, "Vaigai reservoir (irrigation releases)",
    [res("Vaigai dam", 10.0463, 77.5858)],
    ["Vaigai dam -> dam-toe PH (rated head 27.5 m)"],
    evac=["110 kV substation 'Vaigai Dam' (OSM way 310099513)"],
    history="2x3 MW irrigation hydel at Vaigai dam, commissioned 04.03.1990.",
    sources=[DC26, DC24, WEB, OLD["koday"], osm("way", 1463910405), osm("way", 310099513)]))

R.append(hydro("perunchani", "Perunchani Mini Power House", ["Perunchani MPH", "Perunchani PH", "PERUNCHANI"],
    "Kanyakumari", 8.3644, 77.3577, "approx", 1.3,
    U([(0.65, "2005-12", None), (0.65, "2006-01", None)]),
    TV, "Perunchani reservoir (Paralayar, irrigation)",
    [res("Perunchani dam", 8.3644, 77.3577)],
    ["Perunchani dam -> irrigation outlet mini PH"],
    history="2x0.65 MW mini hydel commissioned Dec 2005 and Jan 2006.",
    sources=[DC26, DC24, WEB, OLD["koday"], osm("way", 104710227)],
    notes_loc="Placed at Perunchani dam (OSM way 104710227); powerhouse not mapped."))

for i, (mw, dates, lat, lon, lq, extra, note) in enumerate([
    (2, ["2010-10", "2011-01"], 9.64914, 77.24392, "approx", [osm("way", 1468094721)], "Unnamed OSM hydro plant (way 1468094721) on the river near Gudalur/Kuruvanuthu; satellite imagery shows a small weir powerhouse. A tender notice places PVSHEP-I near Kuruvanathu bridge. Identification is inferred."),
    (1.25, ["2012-01", "2012-01"], None, None, "approx", [], "Location unknown (Periyar-Vaigai system, Theni district)."),
    (2, [None, None], None, None, "approx", [], "Location unknown; a tender notice places PVSHEP-III at Vettukadu, Theni district (not geocoded)."),
    (1.25, [None, None], None, None, "approx", [], "Location unknown (Periyar-Vaigai system, Theni district)."),
], start=1):
    rom = ["I", "II", "III", "IV"][i - 1]
    R.append(hydro(f"periyar-vaigai-mini-{i}", f"Periyar Vaigai Mini Power House {rom}",
        [f"Periyar Vaigai Mini PH-{rom}", f"PVSHEP-{rom}", f"Periyar Vaigai Small Hydro Electric Project {rom}", f"PERIYAR VAGAI MINI {rom}"],
        "Theni", lat, lon, lq, mw * 2, U([(mw, d, None) for d in dates]),
        TV, "Periyar water released from Periyar PH (Periyar-Vaigai canal/river system)",
        [res("Periyar PH tailrace", 9.6267, 77.19052)],
        ["Periyar PH tailrace -> Periyar/Suruli river -> weir -> mini PH -> Vaigai dam"],
        kind="run-of-river (canal/weir)",
        history=f"Periyar-Vaigai small hydro scheme {rom} (2x{mw} MW)." + (" Commissioning dates from the 2012 TANGEDCO page, which wrongly gives the district as Kanyakumari." if i <= 2 else ""),
        sources=[DC26, DC24, WEB] + ([OLD["koday"]] if i <= 2 else []) + extra + ["https://tenderkart.in/tender/21814716-b76e-452f-994c-271b0b009c67"],
        notes_loc=note))

# ---------------- ONGOING / PLANNED ----------------
R.append(hydro("kundah-psp", "Kundah Pumped Storage Hydro-electric Project", ["Kundah PSP", "Kundah Pumped Storage Hydro Electric Project", "KUNDAH PSP", "Kundah (Stage I,II&III)"],
    "Nilgiris", 11.3205, 76.6247, "approx", 500,
    [{"no": n, "mw": 125, "commissioned": None, "make": "GE Renewable Energy (pump-turbines, via MEIL)", "status": "under_construction"} for n in range(1, 5)],
    K, "Porthimund reservoir (upper) / Emerald reservoir (lower)",
    [res("Porthimund reservoir (upper)", None, None), res("Emerald reservoir (lower)", None, None)],
    ["generation: Porthimund -> underground PH -> Emerald", "pumping: Emerald -> Porthimund"],
    status="under_construction", typ="pumped_storage", kind="pumped storage",
    history="4x125 MW pumped storage under construction since 2018 (zero date 15.02.2018; EPC Phase I Patel Engineering / Kundah PSP Consortium; E&M later MEIL with GE pump-turbines). Cost estimates: Rs 1831 cr (2019), 3,522 cr (DC 2023-24), 3,926 cr (DC 2025-26). CEA (Feb 2026) expects commissioning in 2026-27 (Sept 2026). NPP/DGR already list 'KUNDAH PSP' with a generation programme but zero actual generation.",
    npp=100874, dgr="KUNDAH PSP",
    sources=[DC26P, DC24, WEBP, CEAPSP, "https://web.archive.org/web/2024/https://www.tangedco.gov.in/linkpdf/Kundahpump.pdf", "https://www.smec.com/project/kundah-pumped-storage-hydroelectric-project/", "https://www.renewableenergyworld.com/energy-storage/pumped-storage/meil-names-ge-renewable-energy-to-supply-turbines-for-500-mw-kundah-pumped-storage/", NPPF],
    notes_loc="Underground powerhouse location not published; placed at Emerald village (OSM node 910344193) on the lower reservoir."))

R.append(hydro("kollimalai-hep", "Kollimalai Hydro Electric Project", ["Kollimalai HEP", "Kollimalai Hydro Electric Project (1 X 20 MW)"],
    "Namakkal", None, None, "approx", 20,
    [{"no": 1, "mw": 20, "commissioned": None, "make": None, "status": "under_construction"}],
    None, "Kolli hills streams (Aiyaru), Puliancholai village",
    [], ["intake on Kolli hills -> power tunnel -> PH at Puliancholai foothills"],
    status="under_construction", kind="storage/diversion",
    history="1x20 MW project at Puliancholai village (Namakkal/Tiruchirappalli border). LoI 21.09.2016 to a K. Rajagopalan & Co-led consortium; originally due April 2021. Cost Rs 338.79 cr (2016), 591.20 cr (DC 2023-24), 595.46 cr (DC 2025-26). Wikipedia reports ~67% progress. Website lists it as 200 MW, which looks like a typo for 20 MW.",
    sources=[DC26P, DC24, WEBP, WIKI, "https://web.archive.org/web/2024/https://www.tangedco.gov.in/linkpdf/kollimalaiH.pdf"],
    notes_loc="Puliancholai village not geocoded; coordinates null."))

PSHEP = [
    # id, name, MW(DC26), district, config(wiki), lat, lon, loc note, extra history
    ("upper-bhavani-psp", "Upper Bhavani PSHEP", 1000, "Nilgiris", "4x250", None, None,
     "Upper reservoir Upper Bhavani, lower Avalanche-Emerald (CEA). Allotted to NTECL (NTPC-TANGEDCO JV) under G.O.(Ms) No.33 dt 11.03.2024; DPR due 06/26 (CEA, S&I stage)."),
    ("sandynallah-psp", "Sandy Nalla PSHEP", 1200, "Nilgiris", "4x300", 11.4422, 76.6536, "IFC engaged as transaction advisor (G.O. 139 & 140 dt 14.03.24). Placed at the existing Sandynallah dam (DRIP) - project layout unknown."),
    ("sigur-psp", "Sigur PSHEP", 800, "Nilgiris", "4x200", None, None, "IFC transaction advisor; Sigur plateau (Nilgiris)."),
    ("vellimalai-psp", "Vellimalai PSHEP", 1000, "Kanyakumari", "4x275", None, None,
     "Project cost Rs 5320 cr; ToR approved by MoEF&CC 25.02.2026; PPP developer tender to open 17.06.2026; G.O.(Ms) No.43 dt 14.03.2026. The website lists 1100 MW, DC 2025-26 lists 1000 MW."),
    ("sillahalla-psp-1", "Sillahalla PSHEP Stage-I", 1000, "Nilgiris", "4x250", None, None, "State sector per Wikipedia; DPR preparation."),
    ("sillahalla-psp-2", "Sillahalla PSHEP Stage-II", 1000, "Nilgiris", "4x250", None, None, "PPP; DPR preparation."),
    ("palar-poranthalar-psp", "Palar-Poranthalar PSHEP", 1100, "Dindigul", "4x275", None, None, "PPP, in-principle approval G.O.(Ms) No.106 dt 13.12.2023."),
    ("manjalar-psp", "Manjalar PSHEP", 500, "Theni", "2x250", 10.196, 77.6338, "PPP. Placed at existing Manjalar dam (OSM way 339268071) - layout unknown. DC 2025-26 lists Theni district; the Manjalar dam is in Dindigul/Theni border area."),
    ("kodayar-psp", "Kodayar PSHEP", 1500, "Kanyakumari", "6x250", 8.5221, 77.3596, "PPP; cost Rs 10,838 cr (Wikipedia). Placed at Upper Kodayar dam (OSM way 204957247) - layout unknown."),
    ("manalar-psp", "Manalar PSHEP", 1200, "Theni", "6x200", 9.638, 77.3459, "PPP; cost Rs 9,887 cr (Wikipedia). Placed at existing Manalar dam (OSM way 842918875) - layout unknown."),
    ("aliyar-psp", "Aliyar PSHEP", 1800, "Coimbatore", "4x175 (700 MW per website/Wikipedia)", 10.4828, 76.9709,
     "Capacity conflict: 1800 MW in DC 2025-26 vs 700 MW on the TNGECL hydro-projects page and Wikipedia. Placed at Aliyar dam - layout unknown."),
    ("mettur-psp", "Mettur PSHEP", 1000, "Salem", "4x250", 11.8035, 77.8063, "PPP; placed at Mettur dam - layout unknown."),
    ("karaiyar-psp", "Karaiyar PSHEP", 1000, "Tirunelveli", "4x250", 8.645, 77.3064, "PPP; area falls within a wildlife sanctuary (DC 2025-26). Placed at Karaiyar reservoir - layout unknown."),
    ("chattar-psp", "Chattar PSHEP", 1100, "Kanyakumari", "4x275", 8.4354, 77.2859, "PPP; area falls within a wildlife sanctuary. Placed at Chittar Dam-1 (OSM) assuming 'Chattar' = Chittar - unverified."),
    ("athur-psp", "Athur PSHEP", 300, "Dindigul", "2x150", None, None, "PPP; DPR preparation."),
]
for pid, pname, mw, dist, cfg, lat, lon, note in PSHEP:
    n, per = (None, None)
    try:
        n, per = cfg.split(" ")[0].split("x"); n = int(n); per = float(per)
    except Exception:
        pass
    units = [{"no": k + 1, "mw": per, "commissioned": None, "make": None, "status": "planned"} for k in range(n)] if n and n * per == mw else []
    R.append(hydro(pid, pname, [pname.replace("PSHEP", "Pumped Storage Hydro Electric Project"), pname.replace("PSHEP", "PSP"), pname.replace("PSHEP", "Pumped Storage Project")],
        dist, lat, lon, "approx", mw, units, None, None, [], [],
        status="planned", typ="pumped_storage", kind="pumped storage (proposed)",
        history=f"One of 15 new pumped-storage projects listed by TNPGCL/TNGECL (DC 2025-26: {mw} MW; unit configuration per Wikipedia {cfg}). {note}",
        sources=[DC26P, WEBP, WIKI] + ([CEAPSP] if pid == "upper-bhavani-psp" else []),
        notes_loc=("Coordinates are the existing reservoir named after the project, not the project site." if lat else "Site coordinates unknown.")))
    if pid == "upper-bhavani-psp":
        R[-1]["operator"] = "NTECL (NTPC-TNGECL JV)"; R[-1]["owner_sector"] = "jv"

# ---------------- TNGECL legacy wind (demonstration wind farms, 1986-93) ----------------
WSRC = ["https://web.archive.org/web/2022/https://www.tangedco.gov.in/linkpdf/windnces.pdf",
        "https://web.archive.org/web/20141129211716/http://teda.in/achievements/wind-energy-2/",
        "https://www.downtoearth.org.in/energy/tamil-nadu-advances-1500-mwh-storage-wind-repowering-initiatives-to-build-a-resilient-renewable-grid"]
def wind(id, name, aliases, district, lat, lon, cap, status, hist, src, osmref=None):
    return {"id": id, "name": name, "aliases": aliases, "type": "wind", "status": status, "state": "Tamil Nadu", "district": district,
            "lat": lat, "lon": lon, "loc_quality": "approx", "capacity_mw": cap, "units": [], "operator": "TNGECL", "owner_sector": "state",
            "fuel": {"primary": "wind", "grade_or_kind": None, "sources": [], "route": [], "annual_requirement": None},
            "water": {"source": None, "cooling": None},
            "structure": {"stacks": [], "cooling_towers": 0, "boiler_units": 0, "coal_yard": False, "ash_pond": None, "dam_h_m": None, "dam_len_m": None,
                          "hub_h_m": None, "rotor_d_m": None, "turbines": None, "area_ha": None},
            "evacuation": [], "emissions": {"fgd": None, "co2_t_per_mwh": None, "notes": ""},
            "history": hist, "links": {"npp_station_id": None, "dgr_name": None, "cea_coal_name": None, "sldc_item": None},
            "sources": src + ([osmref] if osmref else [])}
LEG = ("TNEB demonstration wind farm (TEDA/MNES-aided, Danida technical collaboration). TNEB erected 120 WEGs totalling 19.355 MW at Mullaikadu, Kayathar, Muppandal, Puliyankulam and Kethanur in 1986-93 "
       "(TEDA, 2011: 111 WEGs / 17.55 MW). As of 2025 only 15 of 110 machines (17.355 MW) were operational and 95 had been condemned. Per-site capacity was not found. Placed at the village/substation, not the turbines.")
R.append(wind("tngecl-wind-mullaikadu", "Mullaikadu Demonstration Wind Farm (TNEB)", ["Mullakadu wind farm", "Mullaikadu"], "Thoothukudi", 8.7367, 78.1201, 1.1, "retired",
    "India's first demonstration wind farm: 20 WEGs x 55 kW = 1.1 MW, erected in 1986. Not among the sites listed for repowering in 2025, so presumed retired. " + LEG, WSRC, osm("node", 13620204814)))
R.append(wind("tngecl-wind-kayathar", "Kayathar I & II Demonstration Wind Farms (TNGECL)", ["Kayathar wind farm", "Kayathar I", "Kayathar II"], "Thoothukudi", 8.9479, 77.7724, None, "mothballed", LEG, WSRC, osm("node", 648672820)))
R.append(wind("tngecl-wind-puliyankulam", "Puliyankulam Demonstration Wind Farm (TNGECL)", ["Puliankulam wind farm"], "Tirunelveli", 8.6286, 77.8649, None, "mothballed",
    LEG + " Which of several Puliyankulam villages is meant is uncertain.", WSRC, osm("node", 3591775233)))
R.append(wind("tngecl-wind-muppandal", "Muppandal Demonstration Wind Farm (TNGECL)", ["Muppandal TNEB wind farm"], "Kanyakumari", 8.2593, 77.554, None, "mothballed",
    LEG + " Coordinate is the Muppandal 110 kV substation.", WSRC, osm("way", 309123860)))
R.append(wind("tngecl-wind-kethanur", "Kethanur Demonstration Wind Farm (TNGECL)", ["Kethanoor wind farm"], "Tiruppur", 10.9155, 77.2656, None, "mothballed",
    LEG + " Kethanur is in present-day Tiruppur district (formerly Coimbatore).", WSRC, osm("node", 11808991808)))
rp = wind("tngecl-repowering-hybrid", "TNGECL Wind-Solar Hybrid Repowering Project (Kayathar, Puliyankulam, Muppandal)", ["34.75 MW hybrid repowering"], None, None, None, 34.75, "planned",
    "TNERC (Oct 2025) approved a TNGECL tariff-based bid for a 34.75 MW hybrid (18.75 MW wind + 16 MW solar) on the legacy demonstration wind-farm sites at Kayathar I & II, Puliyankulam and Muppandal. BOO model; land leased from TEDA for 30 years and sub-leased for 27; discovered tariff Rs 2.93/kWh. Spread across several sites, so no single coordinate.",
    WSRC + ["https://solarquarter.com/2025/10/22/tamil-nadus-first-repowering-based-wind-solar-hybrid-project-receives-tnerc-approval/"])
R.append(rp)

# ---------------- sanity ----------------
ids = [r["id"] for r in R]
assert len(ids) == len(set(ids)), [i for i in ids if ids.count(i) > 1]
op_h = sum(r["capacity_mw"] for r in R if r["type"] in ("hydro", "pumped_storage") and r["status"] == "operating")
print("records", len(R), "operating hydro+PSP MW", round(op_h, 2), "stations", sum(1 for r in R if r["type"] in ("hydro", "pumped_storage") and r["status"] == "operating"))
# NPP distance report
for r in R:
    npp = r["links"]["npp_station_id"]
    if npp and r["lat"] and NPP[npp]["latitude"]:
        print(f'{r["id"]:24s} npp_dist_km={dist_km((r["lat"], r["lon"]), (NPP[npp]["latitude"], NPP[npp]["longitude"]))}')
OUT.write_text(json.dumps(R, indent=1, ensure_ascii=False))
print("wrote", OUT)
