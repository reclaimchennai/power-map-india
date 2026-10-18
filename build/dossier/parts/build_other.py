"""Build part_other.json: nuclear, NLCIL, private IPPs/captive, major solar, wind clusters,
ISTS RE, BESS, offshore — for Tamil Nadu. Source files are under raw/ (see sources lists)."""
import json, statistics

ROOT = '.'
OUT = '/tmp/powermap_scratch/part_other.json'

# ---- common source refs -------------------------------------------------------------
NPP = 'file:raw/pages/npp_tn.json:station_details'
DGR = 'file:data/power.db:dgr_stations (NPP DGR, 2026-09)'
CEA_COAL = 'file:data/power.db:coal_plants_daily (CEA daily coal, 2026-09)'
CEA_RCPT = 'file:build/feedstock/_parsed/coal_receipts_cea_monthly.json (CEA monthly coal receipts FY2025-26/FY2026-27)'
CEA_LIST22 = 'https://cea.nic.in/wp-content/uploads/pdm/2023/01/List_of_Power_Stations_31.03.2022.pdf'
CEA_LIST21 = 'https://cea.nic.in/wp-content/uploads/pdm/2021/06/list_power_stations_2021.pdf'
DATACARD = 'https://www.tnpgcl.org/static/tnpdcl/assets/files/linkpdf/datacard/datacard.pdf'
TNPCB = 'file:raw/feedstock/tnpcb_thermal_units.pdf (TNPCB list of thermal power industries)'
OSM_PLANTS = 'file:raw/tn/osm_power_plants_tn.json (Overpass power=plant, TN, 2026-07)'
OSM_PLANTS2 = 'file:build/grid/osm_plants.geojson'
OSM_STRUCT = 'file:raw/tn/osm_chimneys_ct_tn.json (OSM chimneys/cooling towers/generators)'
PEAKDET = 'file:raw/downloads/peakdet.pdf (TANTRANSCO/SLDC grid details 17-Sep-2026)'
RESRPT = 'file:raw/downloads/Report-2026-09-15.pdf (CEA daily RE generation report, ISGS section)'
CAG_NLC = 'file:raw/feedstock/mines/cag_nlc_2025.txt (CAG Report No. 35 of 2025, NLC India)'
NLC_RE = 'https://www.nlcindia.in/website/en/corebusiness/renewableprojects.html'
WIKI = 'https://en.wikipedia.org/wiki/'
OSMW = 'https://www.openstreetmap.org/way/'
OSMN = 'https://www.openstreetmap.org/node/'
OSMR = 'https://www.openstreetmap.org/relation/'


def struct(**kw):
    s = {"stacks": None, "cooling_towers": None, "boiler_units": None, "coal_yard": None,
         "ash_pond": None, "dam_h_m": None, "dam_len_m": None, "hub_h_m": None,
         "rotor_d_m": None, "turbines": None, "area_ha": None}
    s.update(kw)
    return s


def rec(id, name, type, status, district, lat, lon, loc_quality, capacity_mw, *, aliases=(),
        units=None, operator=None, owner_sector=None, fuel=None, water=None, structure=None,
        evacuation=None, emissions=None, history=None, links=None, sources=(), **extra):
    r = {"id": id, "name": name, "aliases": sorted(set(a for a in aliases if a)), "type": type,
         "status": status, "state": "Tamil Nadu", "district": district,
         "lat": lat, "lon": lon, "loc_quality": loc_quality, "capacity_mw": capacity_mw,
         "units": units or [], "operator": operator, "owner_sector": owner_sector,
         "fuel": fuel or {"primary": None, "grade_or_kind": None, "sources": [], "route": [], "annual_requirement": None},
         "water": water or {"source": None, "cooling": None},
         "structure": structure or struct(),
         "evacuation": evacuation or [],
         "emissions": emissions or {"fgd": None, "co2_t_per_mwh": None, "notes": ""},
         "history": history,
         "links": {"npp_station_id": None, "dgr_name": None, "cea_coal_name": None, "sldc_item": None, **(links or {})},
         "sources": list(dict.fromkeys(sources))}
    r.update(extra)
    return r


def U(no, mw, commissioned=None, make=None, status="operating", **kw):
    u = {"no": no, "mw": mw, "commissioned": commissioned, "make": make, "status": status}
    u.update(kw)
    return u


def fuel(primary, kind=None, srcs=(), route=(), req=None):
    return {"primary": primary, "grade_or_kind": kind, "sources": list(srcs), "route": list(route), "annual_requirement": req}


R = []

# =====================================================================================
# NUCLEAR
# =====================================================================================
R.append(rec(
    "kudankulam", "Kudankulam Nuclear Power Project (KKNPP)", "nuclear", "operating", "Tirunelveli",
    8.1686, 77.7128, "exact", 2000,
    aliases=["KUDANKULAM", "KKNPP", "Kudankulam NPP", "Kudankulam 1 & 2", "Kudankulam 1 &", "Koodankulam", "Kudankulam Nuclear Power Plant"],
    units=[U(1, 1000, "2014-12", "Rosatom/Atomstroyexport VVER-1000 (V-412)", first_criticality="2013-07-13", grid_sync="2013-10-22", lat=8.1686, lon=77.7139),
           U(2, 1000, "2017-03", "Rosatom/Atomstroyexport VVER-1000 (V-412)", first_criticality="2016-07-10", grid_sync="2016-08-29", lat=8.1681, lon=77.7117),
           U(3, 1000, None, "VVER-1000", "under_construction", construction_start="2017-06-29", note="'spill to open reactor' Apr 2026; fuel delivered Dec 2025; commissioning expected 2026-27", lat=8.1666, lon=77.7045),
           U(4, 1000, None, "VVER-1000", "under_construction", construction_start="2017-10-23", lat=8.1661, lon=77.7024),
           U(5, 1000, None, "VVER-1000", "under_construction", construction_start="2021-06-29", note="RPV installed Jun 2026", lat=8.1654, lon=77.6993),
           U(6, 1000, None, "VVER-1000", "under_construction", construction_start="2021-12-20", lat=8.1649, lon=77.6972)],
    operator="NPCIL", owner_sector="central",
    fuel=fuel("uranium", "low-enriched UO2 (TVS-2M assemblies, Russian supply by TVEL)",
              [{"name": "TVEL (Rosatom) fuel fabrication, Russia", "kind": "fuel_fabricator", "lat": None, "lon": None, "share": 1.0}],
              ["sea: Russia -> Kudankulam small port/barge jetty (site port opened 2004)"]),
    water={"source": "Gulf of Mannar / Laccadive Sea (sea water)", "cooling": "once-through seawater; desalination for process water"},
    structure=struct(boiler_units=None, area_ha=1145),
    evacuation=["400 kV Kudankulam NPP switchyard (OSM substation 8.171,77.713)"],
    emissions={"fgd": "n/a", "co2_t_per_mwh": 0, "notes": "nuclear"},
    history="Indo-Soviet IGA 1988; construction of units 1-2 from 2002; unit 1 commercial Dec 2014, unit 2 Mar 2017. Units 3-6 (VVER-1000) under construction; unit 3 in pre-commissioning (2026).",
    links={"npp_station_id": 100201, "dgr_name": "KUDANKULAM", "sldc_item": "Kudankulam 1 &"},
    sources=[WIKI + "Kudankulam_Nuclear_Power_Plant", "file:raw/tn/html/wiki/Kudankulam_Nuclear_Power_Plant.wikitext", NPP, DGR, OSM_STRUCT,
             OSMW + "384663588", OSMW + "1429814528", OSMW + "385260247", PEAKDET, DATACARD,
             "https://www.world-nuclear-news.org/articles/flushing-of-safety-systems-begins-for-kudankulam-unit-3",
             "https://thenewsmill.com/2026/04/kudankulam-nuclear-power-plant-unit-3-moves-closer-to-commissioning-with-spillage-to-open-reactor/"]))

R.append(rec(
    "maps-kalpakkam", "Madras Atomic Power Station (MAPS), Kalpakkam", "nuclear", "operating", "Chengalpattu",
    12.5577, 80.1755, "exact", 440,
    aliases=["MADRAS  A.P.S.", "MADRAS A.P.S.", "MAPS", "Madras Atomic Power Station", "Kalpakkam MAPS"],
    units=[U(1, 220, "1984-01", "IPHWR-220 (BARC/NPCIL)", "mothballed", first_criticality="1983-07-02", grid_sync="1983-07-23",
             note="operation suspended (long outage); NPCIL unit table shows 0 MW; DGR still counts 440 MW with 220 MW outage", lat=12.5581, lon=80.1757),
           U(2, 220, "1986-03", "IPHWR-220 (BARC/NPCIL)", first_criticality="1985-08-12", grid_sync="1985-09-20", lat=12.5572, lon=80.1753)],
    operator="NPCIL", owner_sector="central",
    fuel=fuel("uranium", "natural UO2 (PHWR), heavy water moderated",
              [{"name": "Nuclear Fuel Complex, Hyderabad", "kind": "fuel_fabricator", "lat": None, "lon": None, "share": None}]),
    water={"source": "Bay of Bengal (sea water)", "cooling": "once-through seawater"},
    structure=struct(area_ha=597),
    emissions={"fgd": "n/a", "co2_t_per_mwh": 0, "notes": "nuclear"},
    history="India's first fully indigenous nuclear power station; unit 1 commercial Jan 1984, unit 2 Mar 1986. Unit 1 is under extended shutdown; unit 2 operating.",
    links={"npp_station_id": 100672, "dgr_name": "MADRAS  A.P.S.", "sldc_item": "MAPS"},
    sources=[WIKI + "Madras_Atomic_Power_Station", "file:raw/tn/html/wiki/Madras_Atomic_Power_Station.wikitext", NPP, DGR,
             "file:data/power.db:npcil_units", OSMW + "98366375", OSMW + "220250564", OSMW + "220250566", CEA_LIST22, PEAKDET]))

R.append(rec(
    "pfbr-kalpakkam", "Prototype Fast Breeder Reactor (PFBR), Kalpakkam", "nuclear", "under_construction", "Chengalpattu",
    12.5530, 80.1737, "exact", 500,
    aliases=["BHAVINI PFBR", "BHAVINI PFBR ", "PFBR", "Prototype Fast Breeder Reactor", "MAPS Unit 3 (PFBR)"],
    units=[U(1, 500, None, "IGCAR design / BHAVINI, pool-type sodium-cooled FBR (1253 MWth)", "under_construction",
             first_criticality="2026-04-06", note="first criticality 6 Apr 2026; grid synchronisation/commercial operation pending (DGR 2026-09 shows 0 MW capacity, programme only)")],
    operator="BHAVINI", owner_sector="central",
    fuel=fuel("uranium", "U-Pu mixed oxide (MOX); sodium coolant",
              [{"name": "BARC Fuel Fabrication Facility, Tarapur", "kind": "fuel_fabricator", "lat": None, "lon": None, "share": None}]),
    water={"source": "Bay of Bengal (sea water)", "cooling": "once-through seawater (tertiary loop)"},
    emissions={"fgd": "n/a", "co2_t_per_mwh": 0, "notes": "nuclear"},
    history="Construction from 2004 (sanctioned 2003); core loading initiated Mar 2024, final fuel loading Oct 2025, first criticality 6 Apr 2026. Cost revised to Rs 8,181 crore.",
    links={"npp_station_id": 100866, "dgr_name": "BHAVINI PFBR"},
    sources=[WIKI + "Prototype_Fast_Breeder_Reactor", "file:raw/tn/html/wiki/Prototype_Fast_Breeder_Reactor.wikitext", OSMN + "6861924154", NPP, DGR,
             "file:raw/feedstock/wiki_coords_nuclear_gas.json"]))

R.append(rec(
    "fbr-1-2-kalpakkam", "Fast Breeder Reactors FBR-1 & FBR-2 (FBR-600), Kalpakkam", "nuclear", "planned", "Chengalpattu",
    12.553, 80.172, "approx", 1200,
    aliases=["FBR 1&2", "FBR-600 Kalpakkam", "MAPS Units 4-5"],
    units=[U(1, 600, None, "FBR-600 (IGCAR/BHAVINI)", "planned"), U(2, 600, None, "FBR-600 (IGCAR/BHAVINI)", "planned")],
    operator="BHAVINI", owner_sector="central",
    fuel=fuel("uranium", "U-Pu MOX"),
    water={"source": "Bay of Bengal (sea water)", "cooling": None},
    emissions={"fgd": "n/a", "co2_t_per_mwh": 0, "notes": "nuclear"},
    history="Two commercial 600 MWe fast breeders planned at the Kalpakkam site after PFBR operating experience. Exact site within Kalpakkam not published; point placed next to PFBR.",
    sources=[WIKI + "Madras_Atomic_Power_Station", WIKI + "Prototype_Fast_Breeder_Reactor"]))

# =====================================================================================
# NLC INDIA (lignite) — Neyveli
# =====================================================================================
MINE1 = {"name": "NLC Mine-I, Neyveli (lignite, 8.0-10.5 MTPA)", "kind": "mine", "lat": 11.5622, "lon": 79.5052, "share": None}
MINE1A = {"name": "NLC Mine-IA, Neyveli (lignite, 3.0-4.0 MTPA)", "kind": "mine", "lat": None, "lon": None, "share": None}
MINE2 = {"name": "NLC Mine-II, Neyveli (lignite, 13-15 MTPA)", "kind": "mine", "lat": 11.5153, "lon": 79.4321, "share": None}
NLC_SRC = [CAG_NLC, CEA_LIST22, DATACARD, TNPCB, NPP, DGR, OSM_PLANTS, OSM_STRUCT, WIKI + "Neyveli_Thermal_Power_Station", WIKI + "NLC_India_Limited"]

R.append(rec(
    "neyveli-tps-1", "Neyveli Thermal Power Station I (TPS-I)", "lignite", "retired", "Cuddalore",
    11.6133, 79.4810, "approx", 600,
    aliases=["NEYVELI TPS-I", "TPS-I", "Neyveli TS I", "NLC TPS-1"],
    units=[U(i, 50, None, "LMZ / Electrosila (USSR)", "retired") for i in range(1, 7)] +
          [U(i, 100, None, "LMZ / Electrosila (USSR)", "retired") for i in range(7, 10)],
    operator="NLC India Ltd", owner_sector="central",
    fuel=fuel("lignite", "Neyveli lignite (pit-head)", [MINE1], ["conveyor: Mine-I -> TPS-I"]),
    history="India's first lignite pit-head station (units from 1962-1970; 6x50 + 3x100 MW). Unit 7 closed Sep 2018, units 1 and 9 Mar 2020, remaining six in 2020-21 as NNTPS replaced it.",
    links={"npp_station_id": 100685},
    sources=NLC_SRC + ["file:raw/tn/html/wiki/Neyveli_Thermal_Power_Station.wikitext"],
    loc_note="NPP station point (unverified on OSM; old TPS-I block demolished/decommissioned). Unit commissioning years per Wikipedia: U1 Jul-1962, U2-4 Sep-1963, U5 1964, U6 1965, U7 1967, U8 1969, U9 1970."))

R.append(rec(
    "neyveli-tps-1-expansion", "Neyveli Thermal Power Station I Expansion (TPS-I Exp)", "lignite", "operating", "Cuddalore",
    11.5926, 79.4676, "exact", 420,
    aliases=["NEYVELI ( EXT) TPS", "NEYVELI (EXT) TPS", "Neyveli TS1 Exp", "Neyveli TS1 Expansion", "TPS-IE", "TPS-I Expansion", "NLC-TPS 1 - Expansion", "Neyveli Thermal Power Station I"],
    units=[U(1, 210, "2002", None), U(2, 210, "2003", None)],
    operator="NLC India Ltd", owner_sector="central",
    fuel=fuel("lignite", "Neyveli lignite (pit-head)", [MINE1], ["conveyor: Mine-I -> TPS-I Expansion"]),
    water={"source": None, "cooling": "closed-cycle, natural-draught cooling towers (2 on OSM)"},
    structure=struct(stacks=[{"h_m": None, "flues": None, "lat": 11.5912, "lon": 79.4677}], cooling_towers=2, boiler_units=2,
                     ash_pond={"lat": 11.5824, "lon": 79.4701, "area_ha": None}, area_ha=88.6),
    emissions={"fgd": "not installed; FGD contract not finalised (CAG 2025), SO2 above limits", "co2_t_per_mwh": None, "notes": "CAG: TPS-IE exceeded SO2 limits; FGD deadline Dec 2026"},
    history="2x210 MW lignite expansion commissioned 2002-03 next to the original TPS-I.",
    links={"npp_station_id": 100684, "dgr_name": "NEYVELI ( EXT) TPS", "sldc_item": "Neyveli TS1 Exp"},
    sources=NLC_SRC + [OSMW + "465874233", OSMN + "7675638595", OSMN + "7675638596", PEAKDET],
    loc_note="OSM generators (11.5926,79.4680/79.4673) and plant polygon way/465874233; NPP point (11.5927,79.4476) is ~2.2 km west — NPP rejected."))

R.append(rec(
    "neyveli-tps-2", "Neyveli Thermal Power Station II (TPS-II)", "lignite", "operating", "Cuddalore",
    11.5586, 79.4407, "exact", 1470,
    aliases=["NEYVELI TPS-II", "NEYVELI TPS- II", "Neyveli TS2 Stage", "Neyveli TS2 Stage 1", "Neyveli TS2 Stage 2", "NLC-TPS 2 Stage 1", "NLC-TPS 2 Stage 2", "TPS-II", "Neyveli Thermal Power Station II"],
    units=[U(1, 210, "1988"), U(2, 210, "1987"), U(3, 210, "1986"), U(4, 210, "1991"), U(5, 210, "1991"), U(6, 210, "1992"), U(7, 210, "1993")],
    operator="NLC India Ltd", owner_sector="central",
    fuel=fuel("lignite", "Neyveli lignite (pit-head)", [MINE2], ["conveyor: Mine-II -> TPS-II"]),
    water={"source": None, "cooling": "closed-cycle cooling towers (7 on OSM)"},
    structure=struct(stacks=[{"h_m": None, "flues": None}] * 7, cooling_towers=7, boiler_units=7, coal_yard=True),
    emissions={"fgd": "not installed; FGD contract not finalised (CAG 2025), SO2 above limits", "co2_t_per_mwh": None, "notes": "Stage-I (U1-3) and Stage-II (U4-7). Fire accidents in units 5 and 6 in 2020 (CAG)."},
    history="Seven 210 MW lignite units commissioned 1986-1993 in two stages (3x210 + 4x210).",
    links={"npp_station_id": 100686, "dgr_name": "NEYVELI TPS-II", "sldc_item": "Neyveli TS2 Stage"},
    sources=NLC_SRC + [OSMW + "136727943", OSMN + "7675638586", PEAKDET],
    loc_note="Centroid of 7 OSM generator nodes/chimneys (11.557-11.560, 79.439-79.442). NPP point (11.5917,79.4501) lies ~3.8 km NE near NNTPS — NPP rejected."))

R.append(rec(
    "neyveli-tps-2-expansion", "Neyveli Thermal Power Station II Expansion (TPS-II Exp)", "lignite", "operating", "Cuddalore",
    11.5476, 79.4432, "exact", 500,
    aliases=["NEYVELI TPS-II EXP", "Neyveli TS2 Exp", "TPS-IIE", "NLC-TPS 2 - Expansion", "Neyveli TPS-II Expansion"],
    units=[U(1, 250, "2012", "CFBC boiler", note="CEA year of commissioning; COD later"), U(2, 250, "2015", "CFBC boiler")],
    operator="NLC India Ltd", owner_sector="central",
    fuel=fuel("lignite", "Neyveli lignite (pit-head), CFBC with limestone", [MINE2], ["conveyor: Mine-II -> TPS-II Expansion"]),
    water={"source": None, "cooling": "closed-cycle cooling towers (2 on OSM)"},
    structure=struct(stacks=[{"h_m": None, "flues": None, "lat": 11.5466, "lon": 79.4446}], cooling_towers=2, boiler_units=2),
    emissions={"fgd": "CFBC in-furnace limestone desulphurisation; largely within SO2 limits (CAG 2025)", "co2_t_per_mwh": None,
               "notes": "CAG: APC 15-17% vs 10% norm; FBHE design deficiency outages"},
    history="2x250 MW circulating-fluidised-bed lignite units, first in India at this size.",
    links={"npp_station_id": 100312, "dgr_name": "NEYVELI TPS-II EXP", "sldc_item": "Neyveli TS2 Exp"},
    sources=NLC_SRC + [OSMN + "7675617784", OSMN + "7675638585", PEAKDET],
    loc_note="OSM generator nodes 11.5480,79.4434 / 11.5475,79.4429; NPP point (11.5927,79.4757) is at TPS-I Exp area — NPP rejected."))

R.append(rec(
    "neyveli-new-tps", "Neyveli New Thermal Power Station (NNTPS)", "lignite", "operating", "Cuddalore",
    11.5901, 79.4533, "exact", 1000,
    aliases=["NEYVELI NEW TPP", "NNTPS", "NNTPP", "New Neyveli", "New Neyveli TPS", "Neyveli New Thermal Power Project"],
    units=[U(1, 500, "2019-12"), U(2, 500, "2021-02")],
    operator="NLC India Ltd", owner_sector="central",
    fuel=fuel("lignite", "Neyveli lignite (pit-head)", [MINE1], ["conveyor: Mine-I -> NNTPS"]),
    water={"source": None, "cooling": "closed-cycle cooling towers (2 on OSM)"},
    structure=struct(stacks=[{"h_m": None, "flues": None, "lat": 11.5901, "lon": 79.4552}], cooling_towers=2, boiler_units=2,
                     ash_pond={"lat": 11.5774, "lon": 79.4536, "area_ha": None}, area_ha=100.5),
    history="2x500 MW lignite replacement for TPS-I; units commissioned Dec 2019 and Feb 2021.",
    links={"npp_station_id": 100801, "dgr_name": "NEYVELI NEW TPP", "sldc_item": "New Neyveli"},
    sources=NLC_SRC + [OSMW + "345057949", OSMN + "7675638593", OSMN + "7675638594", PEAKDET],
    loc_note="OSM generators 11.5896/11.5906, 79.4533; NPP point (11.5486,79.5014) ~6 km SE — NPP rejected."))

R.append(rec(
    "taqa-neyveli", "TAQA Neyveli Power (ST-CMS Electric) — Neyveli Zero Unit", "lignite", "operating", "Cuddalore",
    11.5420, 79.4150, "exact", 250,
    aliases=["NEYVELI TPS(Z)", "TAQA", "TAQA Neyveli", "ST-CMS", "ST-CMS Electric Co. Pvt ltd", "Neyveli Zero Power Plant", "TAQA Neyveli Power Company"],
    units=[U(1, 250, "2002", "CFBC")],
    operator="TAQA Neyveli Power Company Pvt Ltd", owner_sector="private",
    fuel=fuel("lignite", "Neyveli lignite", [MINE1A], ["conveyor/truck: NLC Mine-IA -> plant"]),
    structure=struct(stacks=[{"h_m": None, "flues": None, "lat": 11.542, "lon": 79.4161}], boiler_units=1, area_ha=24.6),
    history="250 MW IPP at Uthangal village selling to TANGEDCO under a 30-year PPA (15.12.2002-14.12.2032); lignite from NLC Mine-IA.",
    links={"npp_station_id": 100691, "dgr_name": "NEYVELI TPS(Z)", "sldc_item": "TAQA"},
    sources=[DATACARD, CEA_LIST22, TNPCB, NPP, DGR, OSMW + "924966809", OSMN + "8680037148", CAG_NLC, PEAKDET]))



# =====================================================================================
# PRIVATE COAL IPPs / MERCHANT
# =====================================================================================
R.append(rec(
    "itpcl-cuddalore", "IL&FS Tamil Nadu Power Company (ITPCL) Cuddalore TPP", "coal", "operating", "Cuddalore",
    11.5213, 79.7502, "exact", 1200,
    aliases=["ITPCL TPP", "ITPCL", "IL&FS Tamil Nadu Power Co. Ltd", "Cuddalore IL&FS power station", "IL&FS Tamil Nadu Thermal Power Station", "Cuddalore IL&FS Thermal Power Station"],
    units=[U(1, 600, "2015-09", "supercritical"), U(2, 600, "2016-03", "supercritical"),
           U(3, 660, None, None, "planned", note="Phase II (3x660) cancelled per GEM"), ],
    operator="IL&FS Tamil Nadu Power Company Ltd", owner_sector="private",
    fuel=fuel("coal", "imported bituminous (100% import FY2025-26 per CEA)",
              [{"name": "Imported coal (Indonesia/Australia/South Africa per IL&FS)", "kind": "import", "lat": None, "lon": None, "share": 1.0}],
              ["sea: import -> plant (CEA mode 'Sea')"]),
    water={"source": "Bay of Bengal (sea water; 10 MLD desalination plant)", "cooling": None},
    structure=struct(stacks=[{"h_m": None, "flues": None, "lat": 11.5216, "lon": 79.7519}], boiler_units=2, coal_yard=True, area_ha=291.2),
    emissions={"fgd": "required by NGT order (Jun 2012); installation status not verified", "co2_t_per_mwh": None, "notes": ""},
    history="Phase I (2x600 MW) at Kothattai/C.Pudupettai, Parangipettai commissioned 2015-16; Phase II cancelled. 540 MW contracted to TNPDCL under LTOA (valid to 30.09.2028).",
    links={"npp_station_id": 100782, "dgr_name": "ITPCL TPP", "cea_coal_name": "ITPCL TPP"},
    sources=[CEA_LIST22, DATACARD, TNPCB, NPP, DGR, CEA_COAL, CEA_RCPT, OSMW + "645959123", OSMN + "7671425729", OSMN + "7671425730",
             WIKI + "Cuddalore_IL%26FS_Thermal_Power_Station", "file:raw/feedstock/gem/Cuddalore_IL_26FS_power_station.html"]))
R[-1]["units"] = [u for u in R[-1]["units"] if u["no"] in (1, 2)]

R.append(rec(
    "mutiara-coastal-energen", "Mutiara (Coastal Energen / Moxie Power) Melamaruthur TPP", "coal", "operating", "Thoothukudi",
    8.9143, 78.1446, "exact", 1200,
    aliases=["MUTHIARA TPP", "Muthiara", "Mutiara Thermal Power Plant", "Coastal Energen", "Coastal Energen Pvt Ltd", "Moxie Power Generation Ltd",
             "Moxie Power Melamaruthur Thermal Power Plant", "Melamaruthur Power Station", "Mutiara Coastal Energen Thermal Power Plant"],
    units=[U(1, 600, "2015", "subcritical", lat=8.9147, lon=78.1449), U(2, 600, "2016", "subcritical", lat=8.9140, lon=78.1442)],
    operator="Moxie Power Generation Ltd (ex-Coastal Energen)", owner_sector="private",
    fuel=fuel("coal", "imported + domestic blend (FY2025-26: 74% import, 26% CIL)",
              [{"name": "Imported coal", "kind": "import", "lat": None, "lon": None, "share": 0.742},
               {"name": "Coal India Ltd (subsidiary not specified)", "kind": "mine", "lat": None, "lon": None, "share": 0.258}],
              ["sea: -> V.O. Chidambaranar (Tuticorin) port (CEA mode 'Sea')", "road/conveyor: port -> plant"]),
    structure=struct(stacks=[{"h_m": None, "flues": 2, "lat": 8.9131, "lon": 78.1458}], boiler_units=2, coal_yard=True, area_ha=431.9),
    history="Coastal Energen (Coal & Oil Group) plant; went through NCLT insolvency and was transferred to Moxie Power Generation (Dickey Alternative Investment Trust 51% / Adani Power 49% per GEM). 558 MW contracted to TNPDCL (LTOA to 2028; MTOA from 01.04.2026).",
    links={"npp_station_id": 100575, "dgr_name": "MUTHIARA TPP", "cea_coal_name": "MUTHIARA TPP"},
    sources=[CEA_LIST22, DATACARD, NPP, DGR, CEA_COAL, CEA_RCPT, OSMW + "733764035", OSMN + "6872308328", OSMN + "6872308329",
             "file:raw/feedstock/gem/Mutiara_Coastal_Energen_Thermal_Power_Plant.html"],
    loc_note="GEM (exact) 8.9127,78.1450, Wikidata 8.9144,78.1445 and OSM generators agree; NPP point (8.9428,78.1798) ~5 km NE — NPP rejected."))

R.append(rec(
    "sepc-tuticorin", "SEPC Power Tuticorin TPP (Tuticorin Stage IV)", "coal", "operating", "Thoothukudi",
    8.7555, 78.1576, "exact", 525,
    aliases=["TUTICORIN TPP ST-IV", "SEPC", "SEPC Power Pvt Ltd", "SEPC Power Private Limited", "Tuticorin TPP Stage IV", "Tuticorin Stage-IV"],
    units=[U(1, 525, "2021", None)],
    operator="SEPC Power Pvt Ltd", owner_sector="private",
    fuel=fuel("coal", "mostly imported (FY2025-26: 94.5% import, 5.5% CIL)",
              [{"name": "Imported coal", "kind": "import", "lat": None, "lon": None, "share": 0.945},
               {"name": "Coal India Ltd", "kind": "mine", "lat": None, "lon": None, "share": 0.055}],
              ["sea: -> V.O. Chidambaranar port (CEA mode 'RAIL-SEA')"]),
    structure=struct(stacks=[{"h_m": None, "flues": None, "lat": 8.7551, "lon": 78.1596}], boiler_units=1, area_ha=25.7),
    history="525 MW IPP in the Tuticorin harbour estate; PPA with TANGEDCO for 30 years from 30.11.2021.",
    links={"npp_station_id": 100845, "dgr_name": "TUTICORIN TPP ST-IV", "cea_coal_name": "TUTICORIN TPP ST-IV", "sldc_item": "SEPC"},
    sources=[CEA_LIST22, DATACARD, NPP, DGR, CEA_COAL, CEA_RCPT, OSMW + "822892679", PEAKDET],
    loc_note="OSM plant polygon 'SEPC' + chimney; NPP point (8.45,78.10) is a placeholder in the sea — NPP rejected."))

R.append(rec(
    "ind-barath-tuticorin", "Ind-Barath Thermal Power (IBTPL) Tuticorin — now Orissa Alloy Steel", "coal", "operating", "Thoothukudi",
    8.8856, 78.0546, "exact", 300,
    aliases=["TUTICORIN (P) TPP", "Ind Barath Power infra Ltd", "Ind-Barath Thermal Power Ltd", "IBTPL", "Thoothukudi IBTPL power station", "Orissa Alloy Steel Pvt Ltd, Thoothukudi"],
    units=[U(1, 150, "2013", lat=8.8824, lon=78.0533), U(2, 150, "2013", lat=8.8829, lon=78.0533)],
    operator="Orissa Alloy Steel Pvt Ltd (per TNPDCL MTOA 2026); built by Ind-Barath Power Infra", owner_sector="private",
    fuel=fuel("coal", "domestic (CIL) in FY2026-27; no receipts in FY2025-26",
              [{"name": "Coal India Ltd", "kind": "mine", "lat": None, "lon": None, "share": 1.0}],
              ["rail -> port -> road (CEA mode 'RAIL-SEA- ROAD')"]),
    structure=struct(stacks=[{"h_m": None, "flues": None, "lat": 8.8826, "lon": 78.0524}], boiler_units=2, area_ha=42.6),
    history="2x150 MW at Swaminatham/Ottapidaram villages (2013). Idle through FY2025-26; restarted 2026 with 150 MW MTOA to TNPDCL (01.02.2026-31.01.2031).",
    links={"npp_station_id": 100573, "dgr_name": "TUTICORIN (P) TPP", "cea_coal_name": "TUTICORIN (P) TPP"},
    sources=[CEA_LIST22, DATACARD, TNPCB, NPP, DGR, CEA_COAL, CEA_RCPT, OSMW + "385432388", OSMN + "5848822937", OSMN + "5848822938"],
    loc_note="OSM polygon named 'Thoothukudi IBTPL power station' (300 MW, 2013); NPP point 8.8848,78.0698 is 1.6 km E."))

R.append(rec(
    "ind-barath-gencom-tuticorin", "Ind-Barath Power Gencom (IBPGL) Keelavelayuthapuram", "coal", None, "Thoothukudi",
    8.8657, 78.1081, "exact", 189,
    aliases=["IBPGL", "Thoothukudi IBPGL", "Ind Barath Power Gencom Limited"],
    units=[U(i, 63, None, None, None) for i in (1, 2, 3)],
    operator="Ind-Barath Power Gencom Ltd", owner_sector="private",
    fuel=fuel("coal"),
    structure=struct(stacks=[{"h_m": None, "flues": None, "lat": 8.8648, "lon": 78.1067}], boiler_units=3, area_ha=18.4),
    history="3x63 MW consented by TNPCB at Keelavelayuthapuram village; OSM maps 3 generator blocks and a chimney. Not in CEA/NPP lists — operating status unknown.",
    sources=[TNPCB, OSMW + "385432381", OSMN + "5848822934"]))

R.append(rec(
    "opg-gummidipoondi", "OPG Power Generation, Gummidipoondi", "coal", "operating", "Tiruvallur",
    13.4365, 80.0971, "exact", 414,
    aliases=["OPG Power Generation Private Limited", "OPG Power Generation Pvt. Ltd", "OPG", "Chennai OPG Power Plant", "OPG Power Gummidipoondi"],
    units=[U(1, 77, None, note="data card LTOA lists 1x77, 1x81, 1x80, 1x180"), U(2, 81), U(3, 80), U(4, 180)],
    operator="OPG Power Generation Pvt Ltd", owner_sector="private",
    fuel=fuel("coal", "imported + domestic (FY2025-26: 60% import, 30% CIL, 9% other)",
              [{"name": "Imported coal", "kind": "import", "lat": None, "lon": None, "share": 0.604},
               {"name": "Coal India Ltd", "kind": "mine", "lat": None, "lon": None, "share": 0.302}],
              ["sea -> Chennai/Kamarajar port -> rail/road (CEA mode 'RAIL-SEA- ROAD')"]),
    structure=struct(stacks=[{"h_m": None, "flues": None}] * 3, area_ha=65.1),
    history="Merchant/group-captive plant at Periya Obulapuram, Gummidipoondi. Capacity quoted as 414 MW (DGR/CEA) or 422 MW (TNPCB: 2x81+1x80+1x180).",
    links={"npp_station_id": 100861, "dgr_name": "OPG Power Generation Private Limited", "cea_coal_name": "OPG Power Generation Private Limited"},
    sources=[DATACARD, TNPCB, NPP, DGR, CEA_COAL, CEA_RCPT, OSMW + "840721288", OSM_STRUCT],
    unit_conflict="Data card LTOA: 1x77+1x81+1x80+1x180 (=418); TNPCB & data card MTOA: 2x81+1x80+1x180 (=422); DGR/CEA 414."))

R.append(rec(
    "tulsyan-nec-gummidipoondi", "Tulsyan NEC captive power plant (Manikaran Power), Gummidipoondi", "coal", "operating", "Tiruvallur",
    13.4166, 80.0576, "exact", 70,
    aliases=["Tulsyan NEC Limited", "Tulsyan NEC", "Manikaran Power Limited (Tulsyan, Chennai)", "Tulsyan Steel Gummidipoondi Captive Power Plant"],
    units=[U(1, 35), U(2, 35)],
    operator="Tulsyan NEC Ltd", owner_sector="private",
    fuel=fuel("coal", "domestic (CIL) FY2026-27", [{"name": "Coal India Ltd", "kind": "mine", "lat": None, "lon": None, "share": 1.0}],
              ["rail-sea (CEA mode 'RAIL-SEA')"]),
    structure=struct(stacks=[{"h_m": None, "flues": None, "lat": 13.4158, "lon": 80.0560}], area_ha=17.5),
    history="2x35 MW coal plant at Chitoornatham village, Gummidipoondi; 60 MW sold to TNPDCL via Manikaran Power (MTOA from 01.04.2026).",
    links={"npp_station_id": 100886, "dgr_name": "Tulsyan NEC Limited", "cea_coal_name": "Tulsyan NEC Limited"},
    sources=[DATACARD, TNPCB, NPP, DGR, CEA_COAL, CEA_RCPT, OSM_PLANTS2, OSMW + "636898416"]))

R.append(rec(
    "nagai-power", "Nagai Power, Nagapattinam (Okkur)", "coal", "operating", "Nagapattinam",
    10.8233, 79.7539, "exact", 150,
    aliases=["Nagai TPP", "Nagai Power Private Limited", "Nagai Power Nagaipattinam", "Nagai Nagapattinam Power Project"],
    units=[U(1, 150)],
    operator="Nagai Power Pvt Ltd", owner_sector="private",
    fuel=fuel("coal", None, [], ["rail -> port -> road (CEA mode 'RAIL-SEA- ROAD')"]),
    structure=struct(stacks=[{"h_m": None, "flues": None, "lat": 10.8241, "lon": 79.7526}], area_ha=11.0),
    history="1x150 MW at Okkur, Kilvelur taluk; 120 MW sold to TNPDCL via PTC (MTOA from 01.02.2026). Commissioning year not found.",
    links={"npp_station_id": 100887, "dgr_name": "Nagai TPP", "cea_coal_name": "Nagai TPP"},
    sources=[DATACARD, TNPCB, NPP, DGR, CEA_COAL, OSM_PLANTS2, OSMW + "1187708883", "file:build/build_notes.txt"]))

R.append(rec(
    "tcp-gummidipoondi", "TCP Limited captive power plant, Gummidipoondi", "coal", "operating", "Tiruvallur",
    13.3835, 80.1131, "exact", 63.5,
    aliases=["TCP Limited", "TCPL", "TCP Ltd"],
    units=[],
    operator="TCP Ltd", owner_sector="private",
    fuel=fuel("coal", None, [], ["rail (CEA mode 'RAIL')"]),
    structure=struct(area_ha=34.4),
    history="63.5 MW (TNPCB: 63.75 MW) coal plant at New Gummidipoondi; no coal receipts in FY2025-26 (CEA).",
    links={"npp_station_id": 100870, "dgr_name": "TCP Limited", "cea_coal_name": "TCP Limited"},
    sources=[TNPCB, NPP, DGR, CEA_COAL, CEA_RCPT, OSMW + "840721284"],
    loc_note="OSM polygon 'TCPL' (matches TNPCB address); NPP point 13.0382,80.2643 is in central Chennai (registered office) — NPP rejected."))

R.append(rec(
    "suryadev-gummidipoondi", "Surya Dev Alloys & Power, Gummidipoondi", "coal", "operating", "Tiruvallur",
    13.3837, 80.1078, "exact", 160,
    aliases=["Suryadev Alloys & Power Pvt Ltd", "Surya Dev Alloys and Powers Pvt Ltd", "Gummidipoondi Suryadev Power Plant"],
    units=[U(1, 80), U(2, 80)],
    operator="Surya Dev Alloys & Power Pvt Ltd", owner_sector="private",
    fuel=fuel("coal"),
    structure=struct(stacks=[{"h_m": None, "flues": None, "lat": 13.3847, "lon": 80.1075}], area_ha=20.5),
    history="2x80 MW steel-plant-linked coal plant; 50 MW sold to TNPDCL under MTOA (01.02.2026-31.01.2031).",
    sources=[DATACARD, TNPCB, OSMW + "840721283"]))

R.append(rec(
    "ars-energy-gummidipoondi", "ARS Energy (ARS Metals) captive power station, Gummidipoondi", "coal", "operating", "Tiruvallur",
    13.4228, 80.0650, "exact", 60,
    aliases=["ARS Energy Private Limited", "ARS Metals Gummidipoondi captive power station"],
    units=[U(1, 60, "2013")], operator="ARS Energy Pvt Ltd", owner_sector="private",
    fuel=fuel("coal"),
    structure=struct(stacks=[{"h_m": None, "flues": None, "lat": 13.4220, "lon": 80.0661}], area_ha=25.1),
    history="1x60 MW captive coal unit at Eguvarpalayam (TNPCB); OSM start date 2013.",
    sources=[TNPCB, OSMW + "840721291"]))

R.append(rec(
    "kamachi-gummidipoondi", "Kamachi Industries captive power plant, Gummidipoondi", "coal", None, "Tiruvallur",
    13.4262, 80.0874, "exact", 70,
    aliases=["Gummidipoondi Kamachi Power Plant"],
    operator="Kamachi Industries (per OSM name)", owner_sector="private",
    fuel=fuel("coal"),
    structure=struct(stacks=[{"h_m": None, "flues": None, "lat": 13.4230, "lon": 80.0879}], area_ha=60.3),
    history="Steel-plant captive power plant mapped on OSM (70 MW). Not in CEA/NPP/TNPCB lists collected; status unknown.",
    sources=[OSM_PLANTS2, OSMW + "840721289"]))

R.append(rec(
    "sterlite-tuticorin-cpp", "Vedanta (Sterlite Copper) captive power plant, Thoothukudi SIPCOT", "coal", "retired", "Thoothukudi",
    8.8168, 78.0903, "approx", 160,
    aliases=["Vedanta Limited - Thermal Power Division", "Sterlite Copper CPP"],
    units=[U(1, 80, None, None, "retired", lat=8.8166, lon=78.0902), U(2, 80, None, None, "retired", lat=8.8171, lon=78.0904)],
    operator="Vedanta Ltd", owner_sector="private",
    fuel=fuel("coal"),
    structure=struct(stacks=[{"h_m": None, "flues": None, "lat": 8.8166, "lon": 78.0910}], area_ha=94.5),
    history="2x80 MW captive plant of the Sterlite copper smelter at SIPCOT Meelavittan (TNPCB). The smelter was sealed by GoTN in May 2018 and closure upheld by the Supreme Court (2024); plant idle.",
    sources=[TNPCB, OSMW + "385432377", OSMN + "5848822939", OSMN + "5848822940"],
    loc_note="OSM coal plant polygon is unnamed; attribution to Vedanta/Sterlite inferred from TNPCB address (SIPCOT Meelavittan) — approx."))

R.append(rec(
    "malco-energy-mettur", "MALCO Energy power plant, Mettur", "coal", None, "Salem",
    11.8123, 77.8275, "exact", 130,
    aliases=["MALCO ENERGY LIMITED", "Mettur Malco Power Plant"],
    operator="MALCO Energy Ltd (Vedanta group)", owner_sector="private",
    fuel=fuel("coal"),
    structure=struct(stacks=[{"h_m": None, "flues": None, "lat": 11.8130, "lon": 77.8265}, {"h_m": None, "flues": None, "lat": 11.8127, "lon": 77.8264}], area_ha=7.3),
    history="Former captive plant of the MALCO aluminium smelter at P.N.Patti, Mettur (TNPCB consent 130 MW). Current operating status not verified.",
    sources=[TNPCB, OSMW + "876239840", OSM_STRUCT]))

R.append(rec(
    "chemplast-mettur-cpp", "Chemplast Sanmar captive coal power plant, Mettur", "coal", "operating", "Salem",
    11.8130, 77.9180, "approx", 48.5,
    aliases=["Chemplast Sanmar Ltd", "CHEMPLAST SANMAR LIMITED, COAL POWER PLANT"],
    operator="Chemplast Sanmar Ltd", owner_sector="private",
    fuel=fuel("coal"),
    history="48.5 MW captive coal plant at Raman Nagar, Mettur Dam; in-principle wheeling approval 2026-29 (TNPDCL data card).",
    sources=[DATACARD, TNPCB, OSM_STRUCT],
    loc_note="Placed at a cluster of unnamed OSM chimneys east of Mettur (11.809-11.816, 77.912-77.924) near Raman Nagar — approx."))

R.append(rec(
    "tnpl-kagithapuram-cpp", "TNPL Kagithapuram mill power station", "coal", "operating", "Karur",
    11.0536, 77.9951, "exact", 40,
    aliases=["Kagithapuram Mill Power Station", "Tamil Nadu Newsprint & Papers CPP"],
    operator="Tamil Nadu Newsprint & Papers Ltd", owner_sector="state",
    fuel=fuel("coal", "coal + mill biomass/black liquor (captive cogeneration)"),
    structure=struct(stacks=[{"h_m": None, "flues": None}] * 2, area_ha=7.6),
    history="Captive power station of the TNPL newsprint mill (40 MW per OSM).",
    sources=[OSMW + "947395686", OSM_STRUCT]))

R.append(rec(
    "cpcl-manali-cpp", "CPCL Manali Refinery captive power station", "gas", "operating", "Chennai",
    13.1672, 80.2822, "exact", None,
    aliases=["CPCL Manali Refinery Captive Power Station"],
    operator="Chennai Petroleum Corporation Ltd", owner_sector="central",
    fuel=fuel("gas", "refinery fuel gas / naphtha / fuel oil (unverified mix)"),
    history="Captive power plant inside the Manali refinery; capacity not found.",
    sources=[OSMW + "1134607892", OSM_STRUCT]))

# =====================================================================================
# GAS / DIESEL IPPs
# =====================================================================================
R.append(rec(
    "ppn-pillaiperumalnallur", "PPN Power Generating Company CCPP, Pillaiperumalnallur", "gas", "mothballed", "Mayiladuthurai",
    11.0743, 79.8333, "exact", 330.5,
    aliases=["P.NALLUR CCPP", "PPN", "(i) PPN", "PPN Power Gen. Co. Pvt Ltd", "M/s. PPN Power Generating Company Pvt Ltd", "Pillaiperumalnallur Gas Power Plant"],
    units=[U(1, 225.0, "2001", "GT", None), U(2, 105.5, "2001", "ST", None)],
    operator="PPN Power Generating Company Pvt Ltd", owner_sector="private",
    fuel=fuel("gas", "natural gas (Cauvery basin) / naphtha capable",
              [{"name": "Cauvery basin gas (GAIL network)", "kind": "gas_field", "lat": None, "lon": None, "share": None}]),
    structure=struct(stacks=[{"h_m": None, "flues": None, "lat": 11.0743, "lon": 79.8349}], area_ha=86.4),
    history="330.5 MW combined-cycle IPP; PPA with TANGEDCO 26.04.2001-25.04.2031. DGR (Sep 2026) shows the full 330.5 MW on outage and SLDC shows 0 MW generation.",
    links={"npp_station_id": 100692, "dgr_name": "P.NALLUR CCPP", "sldc_item": "(i) PPN"},
    sources=[CEA_LIST22, DATACARD, NPP, DGR, PEAKDET, OSMW + "156177503"],
    loc_note="OSM polygon + chimney; NPP point (8.1690,77.7127) is the Kudankulam site — NPP rejected. Status 'mothballed' inferred from 100% outage in DGR."))

R.append(rec(
    "lanco-tanjore-karuppur", "Lanco Tanjore Power (ex-Aban Power) CCPP, Karuppur", "gas", None, "Thanjavur",
    11.1216, 79.5288, "exact", 119.8,
    aliases=["KARUPPUR CCPP", "Aban Power Co. Ltd", "Lanco Tanjore Power Plant", "Karappur Combined Cycle power plant", "Lanco Tanjore"],
    units=[U(1, 70.0, "2005", "GT", None), U(2, 49.8, "2005", "ST", None)],
    operator="Lanco Tanjore Power Co. Ltd (ex-Aban Power)", owner_sector="private",
    fuel=fuel("gas", "natural gas (Cauvery basin)"),
    structure=struct(stacks=[{"h_m": None, "flues": None}] * 3, area_ha=9.2),
    history="120 MW combined cycle commissioned 2005. DGR 2026 lists it with 0 MW capacity (dropped from monitored capacity); GEM lists it operating — current status unclear.",
    links={"npp_station_id": 100743, "dgr_name": "KARUPPUR CCPP"},
    sources=[CEA_LIST22, NPP, DGR, OSMW + "374825637", "file:raw/feedstock/gas/gem_Karappur_Combined_Cycle_power_plant.html"],
    loc_note="OSM polygon, Wikidata (11.1207,79.5288) and GEM (11.1218,79.5279 exact) agree; NPP point (11.7711,77.8480) near Mettur — NPP rejected."))

R.append(rec(
    "penna-valantharavai", "Penna Electricity (ex-Pioneer Power) CCPP, Valantharavai", "gas", None, "Ramanathapuram",
    9.3279, 78.9214, "approx", 52.8,
    aliases=["VALANTARVY CCPP", "Pioneer Power Ltd", "Penna Electricity Ltd", "Valantharavai Combined Cycle Gas Power Plant"],
    units=[U(1, 38.0, "2005", "GT", None), U(2, 14.8, "2006", "ST", None)],
    operator="Penna Electricity Ltd", owner_sector="private",
    fuel=fuel("gas", "natural gas (Cauvery basin)"),
    structure=struct(stacks=[{"h_m": None, "flues": None}] * 2, area_ha=1.7),
    history="52.8 MW combined cycle at Valantharavai; GT synchronised 29.10.2005, combined cycle 01.07.2006 (Supreme Court judgment TANGEDCO v Penna Electricity, Dec 2025). DGR 2026 shows 0 MW capacity.",
    links={"npp_station_id": 100716, "dgr_name": "VALANTARVY CCPP"},
    sources=[CEA_LIST22, NPP, DGR, OSMW + "969654405", "https://indiankanoon.org/doc/124155164/"],
    loc_note="Identity inference: CEA owner 'Pioneer Power Ltd' 38+14.8 MW 2005/2006 matches Penna Electricity's plant dates; OSM polygon 'Valantharavai Combined Cycle Gas Power Plant'. NPP point (11.1204,79.8178) is in Mayiladuthurai district — NPP rejected."))

R.append(rec(
    "arkay-valantharavai", "Arkay Energy (Rameswarm) gas engine plant, Valantharavai", "gas", None, "Ramanathapuram",
    9.3282, 78.9237, "exact", 150,
    aliases=["Arkay Energy Rameswarm power station", "Arkay Valantharvi Power Plant", "Valantharavai power station"],
    units=[], operator="Arkay Energy (Rameswarm) Ltd (Ind-Barath Power Infra)", owner_sector="private",
    fuel=fuel("gas", "natural gas; Wärtsilä 34SG engines (captive heat+power per GEM)"),
    structure=struct(stacks=[{"h_m": None, "flues": None}] * 4, area_ha=4.2),
    history="Gas-engine plant (GEM/OSM: 150 MW, start 2006) adjacent to the Penna CCPP; capacity not confirmed by CEA/TNPDCL sources.",
    sources=[OSMW + "969657153", OSMR + "13555371", "file:raw/feedstock/gas/gem_Valantharavai_power_station.html"]))

R.append(rec(
    "sai-regency-kalugoorani", "Sai Regency Power (KSK) CCPP, Ramanathapuram", "gas", None, "Ramanathapuram",
    9.3661, 78.8962, "exact", 58,
    aliases=["Sai Regency Power Plant", "Sai Regency Power Corporation"],
    units=[U(1, 38, "2007-09", "BHEL GT", None), U(2, 20, "2007-09", "BHEL ST", None)],
    operator="Sai Regency Power Corporation Pvt Ltd (KSK Energy)", owner_sector="private",
    fuel=fuel("gas", "Cauvery basin gas (GAIL)"),
    structure=struct(stacks=[{"h_m": None, "flues": None}] * 2, area_ha=6.3),
    history="58 MW combined cycle at Kalugoorani village (2007), power sold to TNEB. Not in the 2022 CEA utility list or 2026 DGR — current status unknown.",
    sources=[OSM_PLANTS2, OSMW + "310430065", "https://www.gem.wiki/Sai_Regency_Power_power_plant"]))

R.append(rec(
    "opg-energy-kuttalam", "OPG Energy gas plant, Maruthur (Kuthalam)", "gas", "operating", "Mayiladuthurai",
    11.034, 79.586, "approx", 17.5,
    aliases=["OPG Energy Pvt Ltd", "OPG ENERGY(P) LIMITED"],
    operator="OPG Energy Pvt Ltd", owner_sector="private",
    fuel=fuel("gas"),
    history="17.5-17.7 MW gas captive at Maruthur village, Kuthalam taluk (same village as TNPGCL Kuttalam GTPS); wheeling approval to 2027.",
    sources=[DATACARD, TNPCB],
    loc_note="Placed at Maruthur/Kuttalam GTPS vicinity — exact plot not identified."))

R.append(rec(
    "samalpatti-dg", "Samalpatti Power Company diesel plant", "diesel", None, "Krishnagiri",
    12.2870, 78.4085, "approx", 105.7,
    aliases=["SAMALPATTI DG", "Samalpatti Power Co. Pvt Ltd", "Samalpatti Oil Power Plant"],
    units=[],
    operator="Samalpatti Power Company Pvt Ltd", owner_sector="private",
    fuel=fuel("diesel", "LSHS/heavy fuel oil"),
    history="105.7 MW liquid-fuel engine plant (7 engines per GEO; CEA lists commissioning 2000, GEO 2001) near Samalpatti, ~35 km W of Dharmapuri. Still in DGR 2026 at 105.7 MW with zero generation.",
    links={"npp_station_id": 100697, "dgr_name": "SAMALPATTI DG"},
    sources=[CEA_LIST22, NPP, DGR, "https://globalenergyobservatory.org/geoid/5242", "file:raw/tn/html/other/globalenergyobservatory.org_geoid_5242", OSMW + "386718594"],
    loc_note="Unnamed OSM industrial polygon way/386718594 (11 ha) 1.4 km from the GEO point (12.2995,78.4038); NPP point 13.0251,80.2629 is in Chennai (office) — NPP rejected."))

R.append(rec(
    "samayanallur-dg", "Madurai Power Corporation diesel plant, Samayanallur", "diesel", None, "Madurai",
    9.9746, 78.0440, "exact", 106.0,
    aliases=["SAMAYANALLUR DG", "Madurai Power Corp. Pvt Ltd", "Covanta Madurai", "Samayanallur Oil Power Plant"],
    units=[],
    operator="Madurai Power Corporation Pvt Ltd", owner_sector="private",
    fuel=fuel("diesel", "LSHS/heavy fuel oil"),
    history="106 MW diesel-engine IPP (7 engines per GEO; 2001; Covanta-operated). Still in DGR 2026 with zero generation.",
    links={"npp_station_id": 100698, "dgr_name": "SAMAYANALLUR DG"},
    sources=[CEA_LIST22, NPP, DGR, "https://globalenergyobservatory.org/geoid/5243", "file:raw/tn/html/other/globalenergyobservatory.org_geoid_5243"],
    loc_note="NPP (9.9740,78.0436) and GEO (9.9751,78.0445) agree within 0.2 km."))

R.append(rec(
    "gmr-vasavi-basin-bridge", "GMR Vasavi diesel power plant, Basin Bridge", "diesel", "retired", "Chennai",
    13.0983, 80.2702, "approx", 196,
    aliases=["B. BRIDGE DG", "GMR Vasavi", "GMR Vasavi Diesel Power Plant", "Basin Bridge DG"],
    units=[U(i, 49, "1999", "MAN B&W two-stroke diesel", "retired") for i in (1, 2, 3, 4)],
    operator="GMR Power Corporation Ltd", owner_sector="private",
    fuel=fuel("diesel", "LSHS (low-sulphur heavy stock)"),
    history="196-200 MW LSHS plant on 29 acres of TNEB land at Basin Bridge (lease Mar 1997, 20 yrs); commissioned 1998-99, decommissioned 2018 and dismantled.",
    links={"npp_station_id": 100742, "dgr_name": "B. BRIDGE DG"},
    sources=[WIKI + "GMR_Vasavi_Diesel_Power_Plant", NPP, "file:raw/feedstock/gas/gem_Basin_Bridge_power_station.html"],
    loc_note="Wikipedia coordinates (13.0983,80.2702) coincide with the adjacent TNPGCL Basin Bridge GTPS; NPP point (11.7867,77.8829) near Mettur is wrong. approx.",
    unit_conflict="Wikipedia: 4x50 MW (200 MW); other sources 196 MW — per-unit 49 MW assumed from 196/4 is NOT verified"))
R[-1]["units"] = []  # per-unit sizes unverified

# =====================================================================================
# SOLAR (major farms)
# =====================================================================================
R.append(rec(
    "kamuthi-solar", "Kamuthi Solar Power Project (Adani)", "solar", "operating", "Ramanathapuram",
    9.3316, 78.3937, "exact", 648,
    aliases=["Kamuthi Solar Power Project", "Solarpark Kamuthi", "Adani Kamuthi"],
    operator="Adani Green Energy", owner_sector="private",
    fuel=fuel("sun", "PV"),
    structure=struct(area_ha=1012),
    history="648 MWp PV park built Feb 2016-Mar 2017 on ~2,500 acres; world's largest single-location PV plant at commissioning.",
    sources=[WIKI + "Kamuthi_Solar_Power_Project", "file:raw/tn/html/wiki/Kamuthi_Solar_Power_Project.wikitext", OSMR + "8550920"],
    loc_note="OSM relation centroid; Wikidata point 9.3476,78.3922 lies 1.8 km N inside the same site."))

nlc_solar = [
    # id, name, district, lat, lon, cap, programme, year, loc_note
    ("nlc-solar-neyveli-130", "NLC 130 MW Solar, Neyveli", "Cuddalore", 11.6045, 79.4965, 130, "MNRE CPSU", "2017", "exact", "OSM relation 'Neyveli Solar Project' 130 MW"),
    ("nlc-solar-neyveli-10", "NLC 10 MW Solar, Neyveli (first RE plant)", "Cuddalore", 11.60, 79.49, 10, "PPA with TANGEDCO", "2015-09", "approx", "Neyveli township, plot not identified"),
    ("nlc-solar-neyveli-captive-10", "NLC 10 MW captive solar (Mini Smart City), Neyveli", "Cuddalore", 11.60, 79.49, 10, "captive", "2023", "approx", "Neyveli township, plot not identified"),
    ("nlc-solar-neyveli-mine-50", "NLC 50 MW captive solar on reclaimed mine land, Neyveli", "Cuddalore", 11.55, 79.48, 50, "captive", "2026-01", "approx", "reclaimed Neyveli mine area, plot not identified"),
    ("nlc-solar-chelliyanallur-200", "NLC 200 MW Solar, Chelliyanallur (Sezhiyanallur)", "Tirunelveli", 8.9174, 77.7146, 200, "500 MW TANGEDCO programme", "2018-19", "approx", "OSM solar polygon 'Shezhilanallur' (village spelling variant)"),
    ("nlc-solar-thoppalakarai-100", "NLC 100 MW Solar, Thoppalakarai (Aruppukottai)", "Virudhunagar", 9.4084, 78.1978, 100, "500 MW TANGEDCO programme", "2018-19", "approx", "Thoppalakarai road geocode"),
    ("nlc-solar-kadamangalam-50", "NLC 50 MW Solar, Kadamangalam", "Ramanathapuram", 9.222, 78.3859, 50, "500 MW TANGEDCO programme", "2018-19", "approx", "unnamed OSM solar polygon ~2 km from Kadamangalam tank"),
    ("nlc-solar-saminatham-100", "NLC 100 MW Solar, Saminatham (Tiruchuli)", "Virudhunagar", 9.51, 78.22, 100, "500 MW TANGEDCO programme", "2018-19", "approx", "Tiruchuli-taluk solar cluster centroid; village not geocoded"),
    ("nlc-solar-ettankulam-50", "NLC 50 MW Solar, Ettankulam", "Tirunelveli", 8.8648, 77.6186, 50, "500 MW TANGEDCO programme", "2018-19", "approx", "Ettankulam village (Manur taluk)"),
    ("nlc-solar-kamuthi-100", "NLC 100 MW Solar, Kamuthi", "Ramanathapuram", 9.4086, 78.3684, 100, "709 MW TANGEDCO programme", "2019", "approx", "Kamuthi town point; plot not identified"),
    ("nlc-solar-maranthai-100", "NLC 100 MW Solar, Maranthai", "Tirunelveli", 8.818, 77.5639, 100, "709 MW TANGEDCO programme", "2019-08", "approx", "Maranthai village (Alangulam taluk); COD 05.08.2019 with Pudur"),
    ("nlc-solar-therkkupatti-100", "NLC 100 MW Solar, Therkkupatti/Subbaiyapuram", "Tirunelveli", 8.8938, 77.5649, 100, "709 MW TANGEDCO programme", "2019", "approx", "unnamed OSM solar polygon 1.5 km from Therkupatti village (Manur taluk)"),
    ("nlc-solar-avathandai-109", "NLC 109 MW Solar, Avathandai (Kadaladi)", "Ramanathapuram", 9.2211, 78.4087, 109, "709 MW TANGEDCO programme", "2019-09", "approx", "unnamed OSM solar polygon near T.Veppankulam (Kadaladi taluk)"),
    ("nlc-solar-onamakulam-100", "NLC 100 MW Solar, Onamakulam", "Thoothukudi", None, None, 100, "709 MW TANGEDCO programme", "2019", "approx", "village not geocoded"),
    ("nlc-solar-pudur-100", "NLC 100 MW Solar, Pudur", "Tirunelveli", 8.8085, 77.5783, 100, "709 MW TANGEDCO programme", "2019-08", "approx", "Pudur (Alangulam) point"),
    ("nlc-solar-poolangal-100", "NLC 100 MW Solar, Poolangal", "Virudhunagar", None, None, 100, "709 MW TANGEDCO programme", "2019", "approx", "village not geocoded"),
]
for (i, n, dist, la, lo, cap, prog, yr, lq, ln) in nlc_solar:
    R.append(rec(i, n, "solar", "operating", dist, la, lo, lq, cap,
                 aliases=[n.replace("NLC ", "NLCIL ")],
                 operator="NLC India Ltd", owner_sector="central", fuel=fuel("sun", "PV"),
                 history=f"NLCIL ground-mounted PV ({prog}), commissioned {yr}.",
                 sources=[NLC_RE, "https://www.pv-magazine-india.com/2019/09/26/nlc-completes-709-mw-solar-for-tamil-nadu-utility/",
                          "https://www.mercomindia.com/nlc-india-solar-tamil-nadu"] + ([OSMR + "8553387"] if i == "nlc-solar-neyveli-130" else []),
                 loc_note=ln))

R.append(rec(
    "ntpc-ettayapuram-solar", "NTPC Ettayapuram Solar PV (230 MW)", "solar", "operating", "Thoothukudi",
    9.15, 77.99, "approx", 230,
    aliases=["NTPC ETTAYAPURAM SOLAR PLANT", "Ettayapuram Solar PV Project", "ETTAYAPURAM SOLAR 230MW"],
    operator="NTPC Renewable Energy Ltd", owner_sector="central", fuel=fuel("sun", "PV (DCR modules)"),
    structure=struct(area_ha=364),
    evacuation=["19 km 230 kV line to PGCIL Tuticorin-II GIS"],
    history="CPSU Scheme Phase-II PV (~900 acres, 1.05 million modules); COD of 162.27 MW on 10.12.2022, balance Dec 2022; power to Telangana discoms.",
    links={"sldc_item": None},
    sources=[RESRPT, "https://ntpcrel.co.in/230mw-ettayapuram-solar-pv-project/", "https://renewablewatch.in/2022/12/12/ntpc-commissions-230-mw-solar-capacity-in-ettayapuram-tamil-nadu/"],
    loc_note="Ettayapuram taluk; exact plot not identified.", cea_re_name="NTPC ETTAYAPURAM SOLAR PLANT"))

R.append(rec(
    "sprng-pugalur-solar", "Sprng Renewable (SREPL) 300 MW ISTS solar, Pugalur", "solar", "operating", "Karur",
    10.7907, 77.7669, "approx", 300,
    aliases=["PGLR_SREPL", "Spring Pugalur", "Sprng Renewable Energy Pvt Ltd"],
    operator="Sprng Renewable Energy Pvt Ltd (inferred from CEA code SREPL)", owner_sector="private", fuel=fuel("sun", "PV"),
    history="300 MW ISTS-connected PV listed in CEA daily RE report under code PGLR_SREPL (Pugalur pooling).",
    sources=[RESRPT, "file:build/grid/substations.geojson ('Spring Pugalur' 230 kV)"],
    loc_note="Placed at the OSM 'Spring Pugalur' 230 kV pooling substation; plant arrays not identified.", cea_re_name="PGLR_SREPL"))

R.append(rec(
    "grt-solar", "GRT 150 MW ISTS solar", "solar", "operating", "Virudhunagar",
    9.4413, 78.0519, "approx", 150,
    aliases=["GRT", "GRT 6"],
    operator=None, owner_sector="private", fuel=fuel("sun", "PV"),
    history="150 MW listed as 'GRT' (Tamil Nadu, IPP) in the CEA ISGS RE report; OSM has a solar polygon 'GRT 6' near Sattur/Virudhunagar.",
    sources=[RESRPT, OSMW + "830287986"],
    loc_note="Identity of CEA 'GRT' with OSM 'GRT 6' polygon is an inference.", cea_re_name="GRT"))

R.append(rec(
    "spic-floating-solar", "SPIC Thoothukudi floating solar PV", "solar", "operating", "Thoothukudi",
    8.7349, 78.1293, "exact", 25.3,
    aliases=["SPIC Thoothukudi Floating Solar PV Park"], operator="SPIC", owner_sector="private", fuel=fuel("sun", "floating PV"),
    sources=[OSMR + "17348197"]))

osm_named_solar = [
    ("w466142896", "Kayanathar", 8.912, 77.7447, 49, "Tirunelveli"),
    ("w590858784", "Narikudi", 9.5701, 78.3127, 60, "Virudhunagar"),
    ("w590858788", "Tiruchuli", 9.5222, 78.2273, 50, "Virudhunagar"),
    ("w830292750", "Kallurani Aadhavan", 9.4461, 78.15, 50, "Virudhunagar"),
    ("w986247881", "Ponnusangampatti", 11.0664, 78.493, 50, "Tiruchirappalli"),
    ("w986279203", "Sattur", 9.4115, 78.0041, 50, "Virudhunagar"),
    ("w986279202", "unnamed 50 MW (Rajapalayam area)", 9.3249, 77.6014, 50, "Virudhunagar"),
    ("w1002687119", "Moolippatti", 9.6442, 77.8502, 40, "Virudhunagar"),
    ("w751947969", "Chengam", 12.3451, 78.9482, 36, "Tiruvannamalai"),
    ("w986260254", "Eluvanampatty", 10.1333, 77.6918, 30, "Dindigul"),
    ("w986247883", "Musri", 11.0805, 78.5055, 20, "Tiruchirappalli"),
    ("w986260257", "Agaram A", 10.4556, 77.9249, 20, "Dindigul"),
    ("w590858783", "Melamudimannar", 9.4156, 78.2475, 18, "Virudhunagar"),
    ("w1227641007", "Moovanur", 11.0013, 78.6115, 15, "Tiruchirappalli"),
    ("w618569316", "Amathur", 9.5539, 77.8845, 14, "Virudhunagar"),
    ("w618569337", "Valathadippatti", 10.5787, 78.6348, 10, "Pudukkottai"),
    ("w986279205", "Pambur", 9.4531, 78.5721, 10, "Ramanathapuram"),
    ("w998307433", "Karur", 10.8155, 78.1865, 10, "Karur"),
    ("w999684607", "Kottathur", 11.1217, 78.6894, 10, "Tiruchirappalli"),
]
for (oid, nm, la, lo, cap, dist) in osm_named_solar:
    slug = "solar-osm-" + nm.lower().replace(" ", "-").replace("(", "").replace(")", "")
    R.append(rec(slug, f"{nm} solar farm", "solar", "operating", dist, la, lo, "exact", cap,
                 aliases=[nm], operator=None, owner_sector="private", fuel=fuel("sun", "PV"),
                 history="Named PV farm on OpenStreetMap with tagged capacity; operator not tagged.",
                 sources=[OSMW + oid[1:]],
                 loc_note="OSM polygon centroid; district assigned from coordinates (approximate)."))

# =====================================================================================
# WIND — belts (clusters) + ISTS farms + NLC wind
# =====================================================================================
wb = json.load(open('/tmp/powermap_scratch/wind_belts.json'))
TOTAL_TURB = sum(v['n'] for v in wb.values())
STATE_WIND = 11361.855  # TNGECL wind installed (STU 9331.365 + CTU 2030.49)
AVG = STATE_WIND / 12807
belts = [
    ("muppandal", "wind-cluster-muppandal-aralvaimozhi", "Muppandal–Aralvaimozhi wind belt (Aralvaimozhi pass)", "Kanyakumari / Tirunelveli",
     ["Muppandal Wind Farm", "Aralvaimozhi", "Aralvoimozhi Pass", "Kanyakumari wind"], "Kanyakumari 118.81 MW (+ part of Tirunelveli 3,700 MW)",
     "India's oldest large wind cluster (from 1986); Wikipedia/OSM quote 1,500 MW for the Muppandal farm. Largest sub-MW turbine cluster in India (IWTMA)."),
    ("panagudi", "wind-cluster-panagudi-radhapuram", "Panagudi–Radhapuram–Kudankulam wind belt", "Tirunelveli",
     ["Radhapuram", "Panagudi", "Tirunelveli wind"], "part of Tirunelveli 3,700 MW",
     "Eastern continuation of the Aralvaimozhi-pass belt in Radhapuram taluk."),
    ("tenkasi", "wind-cluster-tenkasi-sengottai", "Tenkasi–Kadayam–Alangulam wind belt (Sengottai pass)", "Tenkasi / Tirunelveli",
     ["Sengottah Pass", "Kadayam", "Alangulam", "Sankaneri"], "part of Tirunelveli 3,700 MW (Tenkasi district carved out 2019)",
     "Sengottai-pass belt; includes NLCIL 51 MW Kaluneerkulam."),
    ("kayathar", "wind-cluster-kayathar-thoothukudi", "Kayathar–Kovilpatti–Ottapidaram wind belt", "Thoothukudi / Tirunelveli",
     ["Kayathar", "Kovilpatti", "Ottapidaram", "Tuticorin wind", "Thoothukudi wind"], "Thoothukudi 245.97 MW (2019) — since grown via ISTS (SECI) farms",
     "Includes ISTS farms connected to Tuticorin-II / Kayathar pooling (Sembcorp Green Infra, Orange, JSW, Mytrah)."),
    ("palladam", "wind-cluster-palladam-dharapuram", "Palladam–Dharapuram–Kethanur wind belt", "Tiruppur",
     ["Palladam", "Dharapuram", "Kethanur", "Gudimangalam", "Tirupur wind"], "Tiruppur 2,264.98 MW (with Udumalpet)",
     "Palghat-gap belt east of Coimbatore."),
    ("udumalpet", "wind-cluster-udumalpet-pollachi", "Udumalpet–Pollachi–Palani wind belt", "Tiruppur / Coimbatore / Dindigul",
     ["Udumalpet", "Udumalaipettai", "Pollachi", "Palani"], "Tiruppur 2,264.98 + Coimbatore 355.25 + Dindigul 420 MW (shared)",
     "Densest turbine belt in western TN (Palghat gap)."),
    ("coimbatore", "wind-cluster-coimbatore-sulur", "Coimbatore (Sulur–Kinathukadavu) wind belt", "Coimbatore",
     ["Coimbatore wind", "Sulur", "Kinathukadavu"], "Coimbatore 355.25 MW (2019)", "Palghat-gap belt south-east of Coimbatore."),
    ("theni", "wind-cluster-theni-kambam", "Theni–Kambam pass wind belt", "Theni",
     ["Kambam Pass", "Theni wind", "Andipatti"], "Theni 534.70 MW (2019)", "Kambam-pass belt."),
    ("dindigul", "wind-cluster-dindigul-east", "Dindigul (Oddanchatram–Vedasandur) wind belt", "Dindigul / Karur",
     ["Dindigul wind"], "Dindigul 420 MW (2019, shared with Palani area)", "Small eastern belt."),
    ("karur", "wind-cluster-karur", "Karur wind belt (Karur ISTS pooling)", "Karur",
     ["Karur wind"], "not in 2019 table (new ISTS capacity)", "New ISTS wind connected to Karur pooling station (JSW, Tata Power Vardhaman)."),
]
for (k, i, n, dist, al, dcap, hist) in belts:
    b = wb[k]
    est = round(b['n'] * AVG)
    R.append(rec(i, n, "wind", "operating", dist, b['lat'], b['lon'], "approx", est,
                 aliases=al, operator="multiple (private)", owner_sector="private", fuel=fuel("wind"),
                 structure=struct(turbines=b['n']),
                 history=hist,
                 sources=["file:build/grid/tn_wind_turbines.geojson (OSM generator:source=wind nodes)",
                          "https://www.tngecl.org/en/greenenergy/trenew/wind-generation/",
                          "file:raw/downloads/tn_energy_database.pdf:Table 44 (district wind capacity, ~2018-19)",
                          "file:raw/tn/pdf/iwtma_IWTMA-Tamil-Nadu-Report.pdf"] + ([WIKI + "Muppandal_Wind_Farm", OSMR + "14700384"] if k == "muppandal" else []),
                 cluster=True, estimate=True,
                 method=f"capacity = OSM turbine count in belt bbox ({b['n']}) x state-average rating {AVG:.3f} MW (TNGECL wind installed 11,361.855 MW incl. 2,030.49 MW CTU / 12,807 OSM turbines statewide). Point = median of turbine coordinates.",
                 bbox=b['bbox'], district_capacity_table44=dcap))

ists_wind = [
    ("wind-ists-sembcorp-green-infra-tuticorin", "Sembcorp Green Infra 250 MW ISTS wind, Chandragiri", 250, ["GREEN INFRA", "Green Infra Wind Energy", "Sembcorp Tuticorin"], "2018-10", "Sembcorp Green Infra Wind Energy", "SECI Tranche I/II ISTS; commissioned Oct 2018 at Chandragiri, Thoothukudi district."),
    ("wind-ists-mytrah-tn", "Mytrah Vayu 250 MW ISTS wind (Tamil Nadu)", 250, ["MYTRA", "Mytrah Vayu"], None, "Mytrah Vayu", "SECI Tranche-I 250 MW in Tamil Nadu (delays/disputes with SECI reported 2023). Exact district not verified."),
    ("wind-ists-orange-tuticorin", "Orange Renewable 200 MW ISTS wind, Thoothukudi", 200, ["ORANGE", "Orange Renewable"], None, "Orange Renewable (AT Holdings)", "SECI ISTS wind in Thoothukudi district."),
    ("wind-ists-jsw-tuticorin", "JSW Renew Energy ISTS wind, Tuticorin", 540, ["TUTICORINJSWRENEWW", "JSW Energy Tuticorin Wind Farm"], "2024-25", "JSW Renew Energy (JSW Energy)", "SECI Tranche X ISTS; JSW site states 302 MW commissioned FY2024-25 while CEA lists 540 MW under this code."),
    ("wind-ists-jsw-renew-two", "JSW Renew Energy Two ISTS wind", 130, ["JSW RENEW ENERGY TWO LTD"], None, "JSW Renew Energy Two Ltd", "ISTS wind listed under Tamil Nadu in CEA RE report; location not verified."),
]
for (i, n, cap, al, yr, op, h) in ists_wind:
    kb = wb['kayathar']
    has_loc = i in ("wind-ists-sembcorp-green-infra-tuticorin", "wind-ists-orange-tuticorin", "wind-ists-jsw-tuticorin")
    R.append(rec(i, n, "wind", "operating", "Thoothukudi" if has_loc else None,
                 kb['lat'] if has_loc else None, kb['lon'] if has_loc else None, "approx", cap,
                 aliases=al, operator=op, owner_sector="private", fuel=fuel("wind"),
                 history=h, sources=[RESRPT, "https://www.mercomindia.com/cea-transmission-infrastructure-plan-wind",
                                     "https://www.jswenergy.in/businesses/power-generation/tuticorin-wind-farm/" if "jsw" in i else
                                     "https://www.prnewswire.com/in/news-releases/orange-renewable-awarded-200-mw-wind-project-in-the-state-of-tamil-nadu-651042303.html" if "orange" in i else
                                     "https://windinsider.com/2023/12/06/mytrah-vayu-faces-disputes-with-seci-over-delays-in-its-250-mw-wind-power-project-in-tamil-nadu/" if "mytrah" in i else
                                     "https://www.sembcorp.com/media/froiuf5s/sembcorp-wins-india-wind-power-project-with-close-to-250-megawatts-capacity.pdf"],
                 cea_re_name=al[0], part_of="wind-cluster-kayathar-thoothukudi" if has_loc else None,
                 loc_note="Placed at Kayathar–Thoothukudi belt centroid (district-level)" if has_loc else "location not verified"))
karur_sub = (10.8438, 77.6586)
for (i, n, cap, al, op, lat, lon, note) in [
    ("wind-ists-karur-jswretwo", "JSW Renew Energy Two ISTS wind (Karur pooling)", 150, ["KARUR_JSWRETWO_W"], "JSW Renew Energy Two Ltd", karur_sub[0], karur_sub[1], "placed at Karur 400 kV pooling station"),
    ("wind-ists-karur-jswrenew", "JSW Renew Energy ISTS wind (Karur pooling)", 162, ["KARUR_JSWRENEW_W"], "JSW Renew Energy Ltd", karur_sub[0], karur_sub[1], "placed at Karur 400 kV pooling station"),
    ("wind-ists-karur-tp-vardhaman", "Tata Power (TP Vardhaman) ISTS wind, Karur", 50, ["KARUR_TPVARDHAMAN_W", "TATA POWER (TPVARDHAMAN) KARUR"], "TP Vardhaman Surya Ltd (Tata Power)", 10.9024, 77.7501, "placed at OSM 'TATA POWER (TPVARDHAMAN) KARUR' 230 kV substation"),
]:
    R.append(rec(i, n, "wind", "operating", "Karur", lat, lon, "approx", cap, aliases=al, operator=op, owner_sector="private",
                 fuel=fuel("wind"), history="ISTS wind listed under Tamil Nadu in CEA daily RE report (Karur pooling).",
                 sources=[RESRPT, "file:build/grid/substations.geojson"], cea_re_name=al[0], part_of="wind-cluster-karur", loc_note=note))

R.append(rec(
    "nlc-wind-kaluneerkulam", "NLC 51 MW Wind, Kaluneerkulam", "wind", "operating", "Tenkasi",
    8.9136, 77.4465, "approx", 51,
    aliases=["NLCIL 51 MW Wind Power Project", "Kazhuneerkulam wind"], units=[],
    operator="NLC India Ltd", owner_sector="central", fuel=fuel("wind"),
    structure=struct(turbines=34),
    history="34 x 1.5 MW WTGs at Kaluneerkulam, Alangulam taluk; first WTG commissioned Aug 2014; PPA with TANGEDCO.",
    sources=[NLC_RE], part_of="wind-cluster-tenkasi-sengottai", loc_note="Kazhuneerkulam village point (OSM via Photon)"))

R.append(rec(
    "offshore-wind-gulf-of-mannar", "Gulf of Mannar offshore wind zone (Dhanushkodi–Kanyakumari)", "wind", "planned", "Ramanathapuram / Thoothukudi / Kanyakumari",
    8.9, 78.9, "approx", 4000,
    aliases=["Tamil Nadu offshore wind", "SECI 4 GW offshore wind seabed lease", "Gulf of Mannar sub-blocks 2,3,4,7", "FOWIND Tamil Nadu"],
    operator="SECI / MNRE (tendering)", owner_sector="central", fuel=fuel("wind", "offshore"),
    history="SECI RfS (Feb 2024) for seabed lease rights for 4 GW in Gulf of Mannar sub-blocks 2, 3, 4 and 7, plus a 500 MW VGF-backed project; both tenders cancelled Aug 2025 for lack of response. NIWE/FOWIND studies identified zones off Dhanushkodi/Kanyakumari.",
    sources=["https://www.mercomindia.com/seci-invites-offshore-wind-projects-in-tamil-nadu",
             "https://www.offshorewind.biz/2025/08/13/india-cancels-two-offshore-wind-tenders/",
             "file:raw/tn/pdf/iwtma_Wind-Power-Profile-of-Tamilnadu-State.pdf"],
    cluster=True, loc_note="Symbolic point in the Gulf of Mannar; block boundaries not collected."))

# =====================================================================================
# BATTERY STORAGE (TNGECL programmes)
# =====================================================================================
subs = json.load(open(ROOT + '/build/grid/substations.geojson'))
def sub_pt(name):
    best = None
    for ft in subs['features']:
        p = ft['properties']
        if (p.get('name') or '').lower().startswith(name.lower()):
            v = p.get('voltage_kv') or 0
            if best is None or v > best[0]:
                best = (v, ft['geometry']['coordinates'])
    if best:
        return (round(best[1][1], 4), round(best[1][0], 4))
    extra = {"thatchankurichi": (10.9443, 78.8245)}  # TNPDCL substation layer (data/geo/tn_substation.geojson)
    return extra.get(name.lower(), (None, None))

for prog, sites, mwh, mw, st, hist in [
    ("tngecl-bess-1000mwh", ["Thennampatti", "Anuppankulam", "Ottapidaram", "Vellalaviduthi", "Kayathar", "Karaikudi"], 1000, 500, "under_construction",
     "TNERC approved (2026) TNGECL procurement of 1,000 MWh from standalone BESS at six TANTRANSCO substations (VGF/PSDF); tariffs Rs 2.46-2.48 lakh/MW/month."),
    ("tngecl-bess-1500mwh", ["Palladam", "Pudukkottai", "Thatchankurichi", "Thiruvarur", "Karamadai", "Thappagundu", "Anaikadavu"], 1500, 375, "planned",
     "TNGECL tender (Nov 2025) for 375 MW / 1,500 MWh standalone BESS at seven substations; 18-month commissioning after BESPA."),
]:
    for s in sites:
        la, lo = sub_pt(s)
        R.append(rec(f"{prog}-{s.lower()}", f"TNGECL standalone BESS at {s} substation", "battery", st, None, la, lo, "approx", None,
                     aliases=[f"{s} BESS"], operator="TNGECL (developer via tariff-based bidding)", owner_sector="state",
                     fuel=fuel(None, "lithium-ion BESS (2-4 h)"),
                     history=hist + f" Programme total {mw} MW / {mwh} MWh; per-site split not published in sources collected.",
                     sources=["https://www.mercomindia.com/tnerc-approves-tngecls-1000-mwh-battery-storage-power-purchase",
                              "https://www.ess-news.com/2025/11/19/indias-tngecl-invites-bids-for-1-5-gwh-of-standalone-battery-energy-storage-projects/",
                              "https://www.blackridgeresearch.com/news-releases/tamil-nadu-approves-1500-mwh-battery-energy-storage-project-tamil-nadu-india",
                              "file:build/grid/substations.geojson"],
                     programme=prog, programme_mw=mw, programme_mwh=mwh,
                     loc_note="placed at the named TANTRANSCO substation (OSM)" if la else "substation not found in OSM grid layer"))

# ---------------------------------------------------------------------------------
# post-process: clean None keys, check ids unique
ids = [r['id'] for r in R]
assert len(ids) == len(set(ids)), [i for i in ids if ids.count(i) > 1]
json.dump(R, open(OUT, 'w'), indent=1, ensure_ascii=False)
from collections import Counter
print(len(R), Counter(r['type'] for r in R), Counter(r['status'] for r in R))
