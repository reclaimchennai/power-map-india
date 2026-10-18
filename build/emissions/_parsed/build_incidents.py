"""Build build/emissions/_parsed/incidents_tn.json (fork 'caaqms')."""
import json

ROOT = "."
OUT = f"{ROOT}/build/emissions/_parsed/incidents_tn.json"
plants = json.load(open(f"{ROOT}/build/emissions/_parsed/caaqms_tn.json"))["meta"]["plant_coords_used"]
R = "raw/emissions/incidents/"


def P(pid, prec=None):
    p = plants[pid]
    return {"lat": p["lat"], "lon": p["lon"], "loc_precision": prec or f"plant centroid ({p['osm']})"}


WIKI = "https://en.wikipedia.org/w/api.php?action=query&prop=coordinates (saved raw/emissions/incidents/wikipedia_coords.json)"
LOC = {
    "ennore_creek": {"lat": 13.23611, "lon": 80.31667, "loc_precision": "area (Wikipedia coordinate for Ennore Creek)", "loc_source": WIKI},
    "kosasthalaiyar": {"lat": 13.212822, "lon": 80.27696, "loc_precision": "area (Wikipedia coordinate for Kosasthalaiyar River, lower reach)", "loc_source": WIKI},
    "periya_kuppam": {"lat": 13.2121, "lon": 80.3242, "loc_precision": "locality (Wikipedia coordinate for Periya Kuppam, Ennore, where the Coromandel plant is)", "loc_source": WIKI},
    "cpcl": {"lat": 13.17411, "lon": 80.27494, "loc_precision": "OSM polygon centroid 'CPCL Refinery' (way/102565505)", "loc_source": "https://www.openstreetmap.org/way/102565505"},
    "neyveli": {"lat": 11.53599, "lon": 79.48244, "loc_precision": "locality (OSM place node 'Neyveli', node/984171124)", "loc_source": "https://www.openstreetmap.org/node/984171124"},
    "idinthakarai": {"lat": 8.17875, "lon": 77.74509, "loc_precision": "locality (OSM place node 'Idinthakarai', node/1811823206)", "loc_source": "https://www.openstreetmap.org/node/1811823206"},
    "kolathur": {"lat": 11.84847, "lon": 77.75176, "loc_precision": "locality (OSM place node 'Kolathur', Mettur taluk, node/5223170546)", "loc_source": "https://www.openstreetmap.org/node/5223170546"},
    "sipcot_cud": {"lat": 11.68299, "lon": 79.75321, "loc_precision": "CAAQMS site at SIPCOT Kudikadu (plot A-3) as proxy for the SIPCOT Cuddalore estate", "loc_source": "CPCB CCR station metadata"},
    "none": {"lat": None, "lon": None, "loc_precision": "unknown / multi-site"},
}

I = []


def add(**k):
    loc = k.pop("loc")
    rec = {"id": k["id"], "title": k["title"], "date": k["date"], "location": k["location"], **loc,
           "plants_involved": k.get("plants", []), "power_related": k.get("power_related", True),
           "category": k["category"], "issue": k["issue"], "summary": k["summary"], "status_outcome": k.get("status"),
           "sources": k["sources"]}
    if k.get("points"):
        rec["points"] = k["points"]
    if k.get("caveats"):
        rec["caveats"] = k["caveats"]
    I.append(rec)


# ---------------------------------------------------------------- Ennore / Chennai
add(id="ennore-wetlands-ngt-final-order-2022",
    title="NGT (Southern Zone) final order on ash-choked Ennore wetlands / Kosasthalaiyar",
    date="2022-07 (final order; case filed by fishers R. Ravimaran (late), R.L. Srinivasan and K. Saravanan)",
    location="Ennore Creek and Kosasthalaiyar backwaters, Tiruvallur district", loc=LOC["ennore_creek"],
    plants=["nctps-1", "nctps-2", "nctps-3", "ennore-tps", "vallur-ntecl"],
    category="water/land pollution - fly ash", issue="fly ash deposition and encroachment of Ennore wetlands by TANGEDCO ash pipelines/ponds",
    summary=("A Joint Experts Committee (ToR issued March 2022) found that, within a 905 ha study area, natural wetlands shrank from 855.69 ha (1996) to 277.92 ha (2022) while "
             "area covered by fly ash grew from 0 to 260.28 ha. The NGT directed Tamil Nadu to notify the un-encroached Ennore wetlands under the TN Wetland Mission and to prepare a "
             "remediation DPR within 9 months per the committee's ToR."),
    status=("Order directs a Collector-led grievance committee (GCC, TNPCB, TANGEDCO) with quarterly meetings and tasks TNPCB to prosecute and penalise TANGEDCO for unlicensed operation. "
            "Case number not stated in the sources consulted."),
    sources=["https://storyofennore.wordpress.com/2022/07/07/press-release-ngt-directs-gotn-to-bring-full-extent-of-ennore-wetlands-into-tamilnadu-wetlands-mission-calls-for-dpr-for-remediation/",
             "https://icsf.net/newss/tamil-nadu-ennore-creek-to-be-protected-under-wetland-mission/",
             R + "storyofennore.wordpress.com_2022_07_07_press-release-ngt-directs-gotn-to-bring-full-extent-of-ennore-wetlands-into-tamilnadu-wetlands-mission-calls-fo.html", R + "icsf.net_newss_tamil-nadu-ennore-creek-to-be-protected-under-wetland-mission_.html"],
    caveats=["Press release by the petitioners' campaign (Save Ennore Creek); area figures are those quoted from the Joint Experts Committee report via TNIE/ICSF."])

add(id="ennore-creek-fly-ash-removal",
    title="NGT-directed removal of fly ash from Ennore Creek backwaters and Kosasthalaiyar (Rs 28.5 crore deposit by TANGEDCO)",
    date="2020 (dredging began) - 2025-05 (fresh removal proposal)",
    location="2.5 km backwater stretch between NCTPS and Kamarajar Port; North Buckingham Canal; 1.7 km Kosasthalaiyar stretch from NCTPS Stage I gate to Ennore Creek flyover",
    loc=LOC["kosasthalaiyar"], plants=["nctps-1", "nctps-2"],
    category="water/land pollution - fly ash", issue="fly-ash slurry leakage from NCTPS ash pipeline and hot-water discharge silting the creek",
    summary=("Following an NGT Southern Bench directive, TANGEDCO deposited Rs 28.5 crore with the Water Resources Department to remove an estimated 4.30-4.35 lakh m3 of fly ash from the Ennore Creek backwaters "
             "and North Buckingham Canal, where ash slurry leaks from the NCTPS pipeline had built up for nearly two decades. In May 2025 TNPGCL proposed removing a further 1.35 lakh m3 of dredged ash, silt and debris "
             "left on the bunds of a 1.7 km Kosasthalaiyar stretch near NCTPS-I."),
    status=("Dredging work started 2020 (The Hindu via ICSF). 2025: tender for removal of dredged material; WRD also sought Rs 20 crore from TANGEDCO to remove invasive mussels linked to warm-water discharge (DT Next, 2025-05-04)."),
    sources=["https://icsf.net/newss/tamil-nadu-work-begins-to-dredge-ennore-creek-backwaters-of-fly-ash/",
             "https://www.dtnext.in/news/chennai/under-ngt-fire-tnpgcl-takes-steps-to-remove-ash-silt-from-kosasthalaiyar-832451",
             R + "icsf.net_newss_tamil-nadu-work-begins-to-dredge-ennore-creek-backwaters-of-fly-ash_.html",
             R + "www.dtnext.in_news_chennai_under-ngt-fire-tnpgcl-takes-steps-to-remove-ash-silt-from-kosasthalaiyar-832451.html"])

add(id="sepakkam-ash-pipeline-leaks",
    title="Recurring NCTPS ash-slurry pipeline leaks at Sepakkam / Kattukuppam; Stage III ash-pipeline bridge on riverbed",
    date="ongoing; reported leak 2020-08-24; pipeline-bridge complaint 2021-07",
    location="Sepakkam village (Kattupalli panchayat) ash pond and Kosasthalaiyar riverbed, Ennore", loc=LOC["kosasthalaiyar"],
    plants=["nctps-1", "nctps-2", "nctps-3"],
    category="water/land/air pollution - fly ash", issue="ash slurry and seawater leaks from ~30-year-old pipelines to the Sepakkam ash pond",
    summary=("Residents of Sepakkam reported repeated leaks from NCTPS ash-slurry pipelines that flooded homes with saltwater and fly ash, with complaints of ash in food and water, skin and breathing problems; "
             "the number of families in the village reportedly fell from over 150 to 60. In 2021 the Coastal Resource Centre alleged TANGEDCO was building a bridge for the NCTPS Stage III ash pipeline to the Sepakkam ash dyke "
             "by dumping debris on the riverbed without Air/Water Act consent."),
    status="No regulatory outcome found in the consulted sources beyond the NGT proceedings recorded in ennore-wetlands-ngt-final-order-2022. Al Jazeera (Nov 2019) reported that the NGT had threatened in ~2017 to close the plant over illegal ash dumping.",
    sources=["https://www.thenewsminute.com/article/coal-ash-food-constant-thirst-itch-tn-s-sepakkam-living-hell-its-residents-131643",
             "https://citizenmatters.in/fly-ash-pollution-at-ennore-creek/",
             "https://www.aljazeera.com/gallery/2019/11/26/india-as-industries-pollute-water-fishermen-lose-livelihood",
             R + "www.thenewsminute.com_article_coal-ash-food-constant-thirst-itch-tn-s-sepakkam-living-hell-its-residents-131643.html",
             R + "citizenmatters.in_fly-ash-pollution-at-ennore-creek_.html",
             R + "www.aljazeera.com_gallery_2019_11_26_india-as-industries-pollute-water-fishermen-lose-livelihood.html"],
    caveats=["Sepakkam ash-pond coordinates not available in OSM; point is the Kosasthalaiyar lower-reach coordinate."])

add(id="kosasthalaiyar-dredged-sand-metals-2021",
    title="Toxic metals in dredged sand dumped in Kosasthalaiyar backwaters (Healthy Energy Initiative sampling)",
    date="2021-07 (sampling); report released 2021-08-03",
    location="Kosasthalaiyar backwaters, Ennore", loc=LOC["kosasthalaiyar"], plants=["nctps-1", "nctps-2", "nctps-3", "vallur-ntecl"],
    category="sediment contamination", issue="arsenic, cadmium, copper, chromium above Canadian ISQG sediment guidelines",
    summary=("Sand samples taken in July 2021 by Healthy Energy Initiative India (tested at Chester LabNet, Oregon) showed arsenic 14.96 mg/kg (~2x ISQG), cadmium 15.23 mg/kg (~20x), copper 23.54 mg/kg and chromium 106.1 mg/kg (~2x). "
             "The campaign attributed the elevated metals to historical fly-ash and coal-handling pollution; TANGEDCO said a ministerial inspection found no deviations."),
    status="Campaign report; no regulatory finding cited. The campaign referenced a January 2020 joint-committee report to the NGT that also found high metal levels in sand dumped by Kamarajar Port.",
    sources=["https://magazine.watertoday.org/news/national/dredged-sea-sand-dumped-into-tns-kosasthalaiyar-river-has-toxic-metals",
             R + "magazine.watertoday.org_news_national_dredged-sea-sand-dumped-into-tns-kosasthalaiyar-river-has-toxic-metals.html"],
    caveats=["NGO sampling, not an official survey; mercury was not reported in this source."])

add(id="ennore-stack-emission-violations-2019-2020",
    title="OCEMS stack data show Ennore coal plants exceeding / not reporting emission norms (HEI 2021; CCAG 'Poison in the Air 2020')",
    date="data 2019-2020; reports 2021-05 and 2021-09",
    location="Ennore thermal cluster (NCTPS I & II, NTECL Vallur)", loc=P("nctps-2", "NCTPS complex centroid (cluster-level finding)"),
    plants=["nctps-1", "nctps-2", "vallur-ntecl"],
    category="air pollution - stack emissions", issue="SO2/NOx/PM stack emissions above TNPCB thresholds and monitoring gaps (CARE Air Centre OCEMS data via RTI)",
    summary=("Healthy Energy Initiative India reported that two Ennore thermal plants violated MoEFCC norms up to 53% of operating time in 2019-2020. The Chennai Climate Action Group's analysis of 2020 hourly CARE Air Centre data "
             "found NCTPS Stage I and II non-compliant (emission or monitoring) for 48% and 53% of the year (Stage II SO2 non-compliant 70% of the year) and NTECL Vallur for 45% (SO2 60%)."),
    status="NGO analyses of TNPCB data; 'violation' includes missing/unreported data as well as exceedances. No penalty found in the consulted sources.",
    sources=["https://citizenmatters.in/ennore-thermal-power-plants-causing-pollution-health-risks/",
             "https://chennaiclimateactiongroup.wordpress.com/2021/09/06/poison-in-the-air-2020-why-ennore-manali-always-polluted/",
             "https://chennaiclimateactiongroup.wordpress.com/wp-content/uploads/2021/09/poison-in-the-air-2020_final.pdf",
             R + "ccag_poison-in-the-air-2020_final.pdf", R + "citizenmatters.in_ennore-thermal-power-plants-causing-pollution-health-risks_.html"])

add(id="ennore-oil-spill-2023",
    title="Ennore oil spill after Cyclone Michaung (CPCL Manali refinery)",
    date="2023-12-04/05",
    location="Buckingham Canal - Kosasthalaiyar - Ennore Creek, from CPCL Manali refinery", loc=LOC["cpcl"],
    plants=[], power_related=False,
    category="oil spill (refinery, not a power plant)", issue="crude/slop oil washed out of CPCL during Michaung floods; mangroves and ~2,300 fisher families affected",
    summary=("Oil from the CPCL refinery at Manali spread through the Buckingham Canal and Kosasthalaiyar into Ennore Creek during Cyclone Michaung flooding, affecting mangroves, 787 boats and 2,301 fisher families. "
             "An IIT-Madras civil-engineering assessment for TNPCB estimated 517 t (conservative) to 2,569 t of oil in sediments; a later IIT-M ocean-engineering report for CPCL put it at 14.48 t."),
    status=("NGT Southern Bench suo motu case. Relief fund Rs 8.68 crore fixed by TN govt, of which CPCL pays Rs 7.53 crore. TNPCB demanded Rs 73 crore environmental compensation; CPCL appealed and the NGT granted an interim stay (reported 2025-03)."),
    sources=["https://www.icsf.net/newss/tamil-nadu-cpcl-to-pay-%E2%82%B97-5-crore-compensation-for-oil-spill-in-ennore/",
             "https://www.dtnext.in/news/tamilnadu/tnpcb-to-calculate-environmental-compensation-for-ennore-oil-spill-803551",
             "https://www.dtnext.in/news/chennai/ennore-oil-spill-assessment-by-one-dept-debunked-by-another-of-same-institute-828325",
             R + "www.dtnext.in_news_tamilnadu_tnpcb-to-calculate-environmental-compensation-for-ennore-oil-spill-803551.html",
             R + "www.dtnext.in_news_chennai_ennore-oil-spill-assessment-by-one-dept-debunked-by-another-of-same-institute-828325.html"])

add(id="ennore-ammonia-leak-2023",
    title="Ammonia leak from Coromandel International's subsea pipeline, Ennore",
    date="2023-12-26 ~23:30",
    location="Coromandel International Ltd fertiliser plant and marine ammonia pipeline, Periya Kuppam, Ennore", loc=LOC["periya_kuppam"],
    plants=[], power_related=False,
    category="toxic gas release (fertiliser plant, not a power plant)", issue="67.638 t ammonia released in ~15 minutes",
    summary=("During pre-cooling of the sea-bed ammonia pipeline, pressure dropped and about 67.6 t of ammonia leaked in ~15 minutes; 42-44 residents were hospitalised. "
             "A state technical committee said granite boulders near the shore may have damaged the pipeline during Cyclone Michaung (3-4 Dec 2023); none of the 19 plant ammonia sensors detected the leak because of their placement relative to the wind."),
    status=("TNPCB levied Rs 5.92 crore environmental compensation. NGT Southern Bench (suo motu) on 2024-05-21 allowed reopening subject to TNPCB/technical-committee conditions and NOCs from DISH, IRS and TN Maritime Board; "
            "the Rs 5.92 crore is to be used for mitigation in the Ennore industrial area."),
    sources=["https://www.thenewsminute.com/tamil-nadu/ennore-gas-leak-tnpcb-says-67-tonnes-of-ammonia-leaked-from-coromandel",
             "https://www.thenewsminute.com/tamil-nadu/ennore-gas-leak-ngt-gives-nod-to-reopen-coromandel-international-places-conditions",
             R + "www.thenewsminute.com_tamil-nadu_ennore-gas-leak-tnpcb-says-67-tonnes-of-ammonia-leaked-from-coromandel.html",
             R + "www.thenewsminute.com_tamil-nadu_ennore-gas-leak-ngt-gives-nod-to-reopen-coromandel-international-places-conditions.html"])

# ---------------------------------------------------------------- statewide
add(id="tn-so2-hotspots-2019",
    title="Neyveli, Chennai (Ennore), Tuticorin and Mettur in global SO2 hotspot list",
    date="2019 emissions (CREA & Greenpeace list, 2020; cited in CREA/Poovulagin Nanbargal 'Emission Watch: Tamil Nadu', Oct 2021)",
    location="Four coal/lignite clusters", loc=LOC["none"],
    plants=["neyveli-ts1-exp", "neyveli-ts2", "neyveli-ts2-exp", "nnttp", "taqa-neyveli", "nctps-1", "nctps-2", "vallur-ntecl",
            "tuticorin-tps", "ntpl-tuticorin", "indbarath-tuticorin", "muthiara-coastal-energen", "mettur-1", "mettur-2"],
    category="air pollution - SO2 (satellite-derived)", issue="large point-source SO2 emissions detected by OMI satellite",
    summary=("Satellite-based SO2 hotspot ranking for 2019: Neyveli rank 14 (299 kt), Chennai rank 36 (142 kt), Tuticorin rank 131 (52 kt), Mettur rank 144 (47 kt). "
             "The CREA report also noted that only 2 of 40 operational coal/lignite units in TN (ITPCL 2x600 MW) had FGD installed as of Aug 2021, and found discrepancies between RTI-obtained OCEMS data and PCB-published data."),
    status="Analytical finding; FGD deadlines subsequently extended by MoEFCC (see CEA FGD status in stations.json).",
    points=[{"cluster": "Neyveli", "rank": 14, "so2_kt_2019": 299, **{k: P("neyveli-ts2")[k] for k in ("lat", "lon")}},
            {"cluster": "Chennai", "rank": 36, "so2_kt_2019": 142, **{k: P("nctps-2")[k] for k in ("lat", "lon")}},
            {"cluster": "Tuticorin", "rank": 131, "so2_kt_2019": 52, **{k: P("tuticorin-tps")[k] for k in ("lat", "lon")}},
            {"cluster": "Mettur", "rank": 144, "so2_kt_2019": 47, **{k: P("mettur-1")[k] for k in ("lat", "lon")}}],
    sources=["https://energyandcleanair.org/wp/wp-content/uploads/2021/10/TN-Emission-report_final.pdf", R + "crea_TN-Emission-report_2021.pdf (Table 01, Key messages)"],
    caveats=["Point coordinates are the principal plant in each cluster (OSM), used only to pin the cluster."])

# ---------------------------------------------------------------- Mettur
add(id="mettur-ash-water-noncompliance-2019",
    title="Mettur TPS: fly-ash utilisation, coal-ash content and water-use non-compliance (CAG Chennai analysis)",
    date="data FY2015-16 to FY2018-19; report 2019-09",
    location="Mettur Thermal Power Station, Salem district (Cauvery river intake)", loc=P("mettur-1"),
    plants=["mettur-1", "mettur-2"],
    category="fly ash / water use / coal quality", issue="ash utilisation below 100% mandate; coal ash >34%; water use ~1.8-1.9x the 3.5 m3/MWh norm (MTPS-I)",
    summary=("Using the plant's environmental statements, Citizen consumer and civic Action Group (CAG, a Chennai NGO) found fly-ash utilisation fell to 36.8% (MTPS-I) and 73.1% (MTPS-II) in 2017-18 against the 100% target of the 2009 notification; "
             "MTPS-II coal ash content rose to 35.91%, above the 34% EC/2014 rules limit; and MTPS-I water consumption was 180-191% of the 2015 MoEFCC limit of 3.5 m3/MWh. "
             "TNPCB's CEPI action plan for Mettur (cited by CREA 2021) records asthma cases at Kolathur PHC rising from 24 (2012) to 44 (2018) and bronchitis from 21 to 55."),
    status="NGO analysis; no penalty identified in consulted sources. Mettur is assessed under CPCB's Comprehensive Environmental Pollution Index (CEPI) programme.",
    sources=["https://www.cag.org.in/sites/default/files/database/declining_efficiency_of_mettur_thermal_power_station_newsletter_december_2019_11-09-2019_aakanksha_0.pdf",
             "https://energyandcleanair.org/wp/wp-content/uploads/2021/10/TN-Emission-report_final.pdf",
             R + "www.cag.org.in_sites_default_files_database_declining_efficiency_of_mettur_thermal_power_station_newsletter_december_2019_11-09-2019_aakanksha_0.pdf",
             R + "crea_TN-Emission-report_2021.pdf"],
    caveats=["'CAG' here is the NGO Citizen consumer and civic Action Group, not the Comptroller and Auditor General."])

# ---------------------------------------------------------------- Neyveli
add(id="neyveli-ts2-boiler-explosions-2020",
    title="Boiler explosions at NLC Neyveli Thermal Power Station-II (Units 6 and 5)",
    date="2020-05-07 (Unit 6) and 2020-07-01 (Unit 5)",
    location="NLCIL TPS-II, Neyveli", loc=P("neyveli-ts2"), plants=["neyveli-ts2"],
    category="industrial safety", issue="boiler explosion during restart/maintenance",
    summary=("On 1 July 2020 a boiler blast in Unit 5 of TPS-II killed workers during a restart after a trip; 13 had died by 8 July, most of the 23 present being contract labourers. "
             "It followed a 7 May 2020 blast in Unit 6 that killed five."),
    status="FIR for culpable homicide/negligence by Cuddalore police; NLCIL shut all TPS-II units temporarily, suspended the unit in-charge and ordered a high-level inquiry.",
    sources=["https://india.mongabay.com/2020/07/with-boiler-blast-the-neyveli-power-station-becomes-a-fiery-grave/",
             R + "india.mongabay.com_2020_07_with-boiler-blast-the-neyveli-power-station-becomes-a-fiery-grave_.html"])

add(id="nlc-mine2-land-protest-2023",
    title="Protests over NLC lignite Mine-II expansion land acquisition (Valayamadevi canal diversion)",
    date="2023-07 (canal work at Valayamadevi; violent protest 2023-07-28)",
    location="Valayamadevi / Karivetti villages, Neyveli, Cuddalore district", loc=LOC["neyveli"],
    plants=["neyveli-ts2", "neyveli-ts2-exp", "nnttp", "neyveli-ts1-exp"],
    category="land / mining conflict (lignite feedstock)", issue="acquisition and repossession of farmland for Mine-II expansion; Upper Paravanar canal diversion through standing paddy",
    summary=("NLC India moved to repossess land acquired in 2006-2013 and diverted the Upper Paravanar canal at Valayamadevi through standing paddy to flood-proof its mines, drawing farmer opposition. "
             "A PMK protest on 28 July 2023 turned violent after Anbumani Ramadoss was detained; police fired three rounds in the air."),
    status="Political/land dispute; no environmental order identified.",
    sources=["https://thesouthfirst.com/tamilnadu/pmk-protest-against-nlc-turns-violent-in-tns-neyveli-police-fire-3-rounds-in-air-detain-anbumani-ramadoss/",
             R + "thesouthfirst.com_tamilnadu_pmk-protest-against-nlc-turns-violent-in-tns-neyveli-police-fire-3-rounds-in-air-detain-anbumani-ramadoss_.html"],
    caveats=["Valayamadevi village has no OSM place node; point is Neyveli town."])

# ---------------------------------------------------------------- Cuddalore
add(id="sipcot-cuddalore-cepi",
    title="SIPCOT Cuddalore declared a critically polluted industrial cluster (CEPI)",
    date="2009 (CEPI 77.45); scores 2011 54.69, 2013 70.12, 2017 62.56",
    location="SIPCOT Industrial Complex, Cuddalore", loc=LOC["sipcot_cud"], plants=[], power_related=False,
    category="industrial air/water pollution (chemical estate, not a power plant)", issue="critically polluted area; toxic gas releases and groundwater contamination",
    summary=("CPCB rated SIPCOT Cuddalore critically polluted in 2009 (CEPI 77.45) and MoEF imposed a moratorium on new projects in January 2010, lifted in February 2011 after an action plan. "
             "Local residents' groundwater-contamination case against TNPCB and SIPCOT was decided by the NGT Southern Zone in December 2021. The ITPCL coal plant lies ~17 km south of the Kudikadu CAAQMS."),
    status="CPCB CEPI action plan; NGT (SZ) O.A. No. 34 of 2015, S. Pugazhendhi & ors v. TNPCB & SIPCOT, order dated 2021-12-22.",
    sources=["https://cpcb.nic.in/industrial_pollution/New_Action_Plans/CEPI_Action%20Plan_CUDDLORE.pdf",
             "https://indiankanoon.org/doc/122672170/", R + "indiankanoon_122672170_pugazhendhi_v_tnpcb.html",
             R + "cpcb.nic.in_industrial_pollution_New_Action_Plans_CEPI_Action_20Plan_CUDDLORE.pdf"])

# ---------------------------------------------------------------- Tuticorin
add(id="thoothukudi-non-attainment",
    title="Thoothukudi listed as a non-attainment city (NCAP) - TNPCB action plan",
    date="NCAP (2019-) ongoing",
    location="Thoothukudi city and port-industrial cluster", loc=P("tuticorin-tps", "cluster pin (TTPS centroid)"),
    plants=["tuticorin-tps", "ntpl-tuticorin", "sepc-tuticorin-st4", "indbarath-tuticorin", "muthiara-coastal-energen"],
    category="ambient air quality", issue="PM10 exceeding NAAQS over several years",
    summary=("TNPCB publishes an 'Action plan for the Non Attainment city - Thoothukudi' under the National Clean Air Programme; the city hosts ~4 GW of coal capacity (TTPS, NTPL, SEPC, Ind-Barath, Coastal Energen) plus the V.O. Chidambaranar port coal handling."),
    status="Action plan under NCAP. Continuous monitoring: one CAAQMS (Meelavittan, ~9-12 km from the plants) plus 3 NAMP sites.",
    sources=["https://tnpcb.gov.in/airquality.php", "raw/emissions/caaqms/tnpcb_airquality.php.html"],
    caveats=["Attribution of PM to power plants vs port/other industry not established in the source."])

add(id="udangudi-coal-jetty-protests",
    title="Fishers' opposition to Udangudi supercritical plant coal jetty; NGT suo motu on coal-corridor route",
    date="2018 (jetty protests) - 2023-04 (NGT suo motu)",
    location="Kallamozhi coast / Udangudi, Thoothukudi district", loc=P("udangudi"), plants=["udangudi"],
    category="coastal / livelihood", issue="8 km coal jetty into the sea, seawater intrusion, anticipated fly ash",
    summary=("Fishers from coastal villages protested construction of the Udangudi coal jetty at Kallamozhi in 2018, citing exclusion zones and erosion; a Madurai Bench PIL against the jetty was dismissed in 2019. "
             "In April 2023 the NGT took up a suo motu case on changes to the coal-corridor route and impacts on water bodies, requiring TANGEDCO to resubmit to the Coastal Zone Management Authority."),
    status="Project proceeded (Stage I 2x660 MW).",
    sources=["https://www.landconflictwatch.org/conflicts/new-thermal-power-plant-causes-protests-in-udangudi-tamil-nadu",
             "https://icsf.net/newss/tamil-nadu-udangudi-thermal-station-a-threat-to-environment-livelihood-of-fishermen/",
             R + "www.landconflictwatch.org_conflicts_new-thermal-power-plant-causes-protests-in-udangudi-tamil-nadu.html"])

add(id="sterlite-thoothukudi-closure-2018",
    title="Sterlite Copper smelter closure after protests and police firing (not a power plant)",
    date="2018-05-22 (police firing) / 2018-05-28 (closure order); SC dismissed Vedanta's plea 2024-02-29",
    location="Sterlite Copper smelter, SIPCOT Thoothukudi", loc=LOC["none"], plants=[], power_related=False,
    category="industrial air/water pollution (copper smelter)", issue="SO2 and effluent/slag pollution allegations",
    summary=("After years of protests over pollution from Vedanta's Sterlite copper smelter, police firing on 22 May 2018 and related violence killed 13 people and the TN government ordered permanent closure on 28 May 2018 under the Water Act. "
             "The Madras High Court upheld the closure in 2020 and the Supreme Court dismissed Vedanta's appeal on 29 February 2024."),
    status="Plant closed.",
    sources=["https://thesouthfirst.com/news/seven-years-on-justice-eludes-thoothukudi-protesters-firing-victims/",
             "https://organiser.org/2024/03/02/224610/bharat/tamil-nadu-supreme-court-rejects-sterlite-industries-plea-to-reopen-thoothukudi-unit/",
             R + "thesouthfirst.com_news_seven-years-on-justice-eludes-thoothukudi-protesters-firing-victims_.html"],
    caveats=["Included only as context for Thoothukudi air quality; smelter site not geocoded (no OSM feature found)."])

# ---------------------------------------------------------------- Kudankulam
add(id="kudankulam-protests-sc-2013",
    title="Anti-nuclear protests at Idinthakarai and Supreme Court judgment clearing Kudankulam",
    date="2011-2013 (protests); 2013-05-06 (SC judgment, G. Sundarrajan v. Union of India)",
    location="Idinthakarai, ~1 km from Kudankulam NPP", loc=LOC["idinthakarai"], plants=["kudankulam"],
    category="nuclear safety / public opposition", issue="reactor safety, radiological risk, spent-fuel disposal",
    summary=("The People's Movement Against Nuclear Energy (PMANE) led sustained protests from Idinthakarai against commissioning of Kudankulam Units 1-2. "
             "On 6 May 2013 the Supreme Court dismissed petitions challenging the AERB and TNPCB consents, while directing the government to report on safety and spent-fuel/waste-disposal arrangements."),
    status="Plant subsequently commissioned. No radiological-release incident found in the consulted sources.",
    sources=["https://www.downtoearth.org.in/environment/supreme-court-gives-go-ahead-to-kudankulam-nuclear-power-plant-40969",
             R + "www.downtoearth.org.in_environment_supreme-court-gives-go-ahead-to-kudankulam-nuclear-power-plant-40969.html"])

out = {"meta": {"built": "2026-09-24",
                "description": "Documented pollution/safety incidents and findings around Tamil Nadu power plants (plus nearby non-power incidents that shape local air/water quality, flagged power_related=false).",
                "notes": ["Every record cites at least one public source; local copies of pages/PDFs are under raw/emissions/incidents/.",
                          "Coordinates come from OSM/Wikipedia; loc_precision says what the point represents. No coordinates were invented.",
                          "Gaps: no specific, well-sourced fly-ash incident found for Tuticorin TPS/NTPL or for Mettur ash dykes beyond the NGO analysis; NGT case numbers for the Ennore fly-ash matters were not found in the consulted sources."],
                "count": len(I)},
       "incidents": I}
json.dump(out, open(OUT, "w"), indent=1, ensure_ascii=False)
print(len(I))
