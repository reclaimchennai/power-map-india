import json, re
P='raw/downloads/tn_energy_database.pdf:p'
OUT='/tmp/powermap_scratch/part_pdf.json'
recs=[]
def d(s):
    """dd.mm.yyyy -> yyyy-mm-dd ; yyyy -> yyyy"""
    if s is None: return None
    s=s.strip()
    m=re.match(r'(\d{1,2})[.\-/](\d{1,2})[.\-/]+(\d{2,4})$',s)
    if m:
        dd,mm,yy=m.groups()
        if len(yy)==2: yy=('19' if int(yy)>30 else '20')+yy
        return f'{yy}-{int(mm):02d}-{int(dd):02d}'
    return s
def rec(id,name,type,status,district,cap,units=None,operator=None,sector=None,fuel=None,kind=None,water=None,history='',pages=(),aliases=None,cluster=False,**extra):
    r={"id":id,"name":name,"aliases":aliases or [],"type":type,"status":status,"state":"Tamil Nadu","district":district,
       "lat":None,"lon":None,"loc_quality":None,"capacity_mw":cap,
       "units":[{"no":u[0],"mw":u[1],"commissioned":d(u[2]) if len(u)>2 else None,"make":u[3] if len(u)>3 else None,"status":u[4] if len(u)>4 else status} for u in (units or [])],
       "operator":operator,"owner_sector":sector,
       "fuel":{"primary":fuel,"grade_or_kind":kind,"sources":[],"route":[],"annual_requirement":None},
       "water":{"source":water,"cooling":None},
       "structure":{"stacks":None,"cooling_towers":None,"boiler_units":None,"coal_yard":None,"ash_pond":None,"dam_h_m":None,"dam_len_m":None,"hub_h_m":None,"rotor_d_m":None,"turbines":None,"area_ha":None},
       "evacuation":[],"emissions":{"fgd":None,"co2_t_per_mwh":None,"notes":""},
       "history":history,
       "links":{"npp_station_id":None,"dgr_name":None,"cea_coal_name":None,"sldc_item":None},
       "sources":[P+str(p) for p in pages]}
    if cluster: r["cluster"]=True
    r.update(extra)
    recs.append(r); return r

# ---------------- COAL (TANGEDCO) Table 1 p25, text p23-25
rec("ennore-tps","Ennore Thermal Power Station","coal","retired","Tiruvallur",450,
    [(1,60,"31.03.1970",None,"retired"),(2,60,"14.02.1971",None,"retired"),(3,110,"17.05.1972",None,"retired"),(4,110,"26.05.1973",None,"retired"),(5,110,"02.12.1975",None,"retired")],
    "TANGEDCO","state","coal","Mahanadi Coalfields (IB Valley, Talcher) + Eastern Coalfields (Raniganj)",None,
    "Shut down permanently on 2017-03-31 after more than four decades; to be replaced by a single 660 MW supercritical unit (Ennore Expansion). Table 35 shows capacity 340 MW in 2013-17.",
    (23,25,107),["ETPS","Ennore TPS"])
rec("mettur-tps-1","Mettur Thermal Power Station I","coal","operating","Salem",840,
    [(1,210,"07.01.1987"),(2,210,"01.12.1987"),(3,210,"22.03.1989"),(4,210,"27.03.1990")],
    "TANGEDCO","state","coal","MCL (Talcher, IB Valley) + ECL Raniganj + imported Indonesian coal",None,
    "First inland thermal station of TANGEDCO. Stage I (units 1-2) cost Rs 384.30 cr, stage II (units 3-4) Rs 351.76 cr.",
    (24,25,107),["MTPS-I","MTPS"])
rec("mettur-tps-2","Mettur Thermal Power Station II","coal","operating","Salem",600,
    [(1,600,"12.10.2013")],"TANGEDCO","state","coal",None,None,
    "First 600 MW unit of TANGEDCO and second inland station; project cost Rs 3550 cr; construction started 2008-06-25, first synchronised 2012-05-04.",
    (24,25,107),["MTPS-II","MTPS Stage III"])
rec("nctps-1","North Chennai Thermal Power Station Stage I","coal","operating","Tiruvallur",630,
    [(1,210,"25.10.1994"),(2,210,"27.03.1995"),(3,210,"24.02.1996")],"TANGEDCO","state","coal",
    "MCL (Talcher, IB Valley) + ECL Raniganj",None,
    "Located ~25 km north of Chennai at Ennore-Puzhudivakkam village, Ponneri taluk.",(24,25,107),["NCTPS-I"])
rec("nctps-2","North Chennai Thermal Power Station Stage II","coal","operating","Tiruvallur",1200,
    [(1,600,"30.06.2013"),(2,600,"17.12.2012")],"TANGEDCO","state","coal","MCL (Talcher, IB Valley) + ECL",None,
    "Adjacent to NCTPS-I on its northern side. PDF lists Unit I 30.06.2013 and Unit II 17.12.2012 (unit II earlier than unit I as printed).",
    (24,25,107),["NCTPS-II"])
rec("ttps","Tuticorin Thermal Power Station","coal","operating","Thoothukudi",1050,
    [(1,210,"09.07.1979"),(2,210,"17.12.1980"),(3,210,"16.04.1982"),(4,210,"11.02.1992"),(5,210,"31.03.1991")],
    "TANGEDCO","state","coal","Odisha/Bengal/Bihar coal via Haldia, Paradip, Vizag ports by ship to Tuticorin port",None,
    "In Thoothukudi Harbour Estate 8 km from town on 160 ha leased from the Port Trust; ~5 MTPA coal.",
    (25,107),["TTPS","Tuticorin TPS"],
    )
recs[-1]["fuel"]["route"]=["rail: coalfields -> Haldia/Paradip/Vizag","sea: -> Tuticorin (V.O.C.) port"]
recs[-1]["fuel"]["annual_requirement"]="~5 MTPA"
recs[-1]["structure"]["area_ha"]=160

# ---------------- planned thermal Table 2 p27 / Table 51 p124
pl=[("ennore-expansion-tpp","Ennore Expansion Thermal Power Project",[660],"Tiruvallur"),
    ("ennore-sez-tpp","Ennore SEZ Supercritical Power Plant",[660,660],"Tiruvallur"),
    ("nctps-3","North Chennai Thermal Power Plant Stage III",[800],"Tiruvallur"),
    ("uppur-tpp","Uppur Thermal Power Project",[800,800],"Ramanathapuram"),
    ("ennore-replacement-tpp","Ennore Replacement Thermal Power Project",[660],"Tiruvallur"),
    ("udangudi-tpp-1","Udangudi Thermal Power Project Stage I",[660,660],"Thoothukudi"),
    ("udangudi-tpp-2","Udangudi Thermal Power Project Stage II",[660,660],"Thoothukudi"),
    ("udangudi-tpp-3","Udangudi Thermal Power Project Stage III",[660,660],"Thoothukudi"),
    ("cheyyur-umpp","Cheyyur Ultra Mega Power Project",[800]*5,"Kancheepuram"),
    ("kadaladi-tpp","Kadaladi Thermal Power Project",[800]*5,"Ramanathapuram")]
for i,n,u,dist in pl:
    rec(i,n,"coal","planned",None,sum(u),[(k+1,m,None,None,"planned") for k,m in enumerate(u)],"TANGEDCO","state","coal",None,None,
        "Listed as ongoing/upcoming TANGEDCO project (no commissioning date) in the 2020 database. District not stated in PDF (commonly: %s)."%dist,(27,124))
# ---------------- private coal Table 3 p30, text p27-28
rec("ind-barath-power-gencom","Ind-Barath Power Gencom Limited (IBPGL)","coal","operating","Thoothukudi",189,
    [(1,63,None,"Hangzhou Steam Turbine / Hangzhou Boiler (CFBC)"),(2,63,None,"Hangzhou Steam Turbine / Hangzhou Boiler (CFBC)"),(3,63,None,"Hangzhou Steam Turbine / Hangzhou Boiler (CFBC)")],
    "Ind-Barath Power Gencom Ltd","private","coal",None,None,
    "3x63 MW CFBC units with air-cooled condensers; evacuates via 230 kV line to TNEB Meelavittan substation. Commissioning date not given.",(27,30),["IBPGL"])
recs[-1]["water"]["cooling"]="air-cooled condenser"; recs[-1]["evacuation"]=["230 kV line to Meelavittan substation"]
rec("ind-barath-thermal-power-ph1","Ind-Barath Thermal Power Limited Phase I (IBTPL)","coal","operating","Thoothukudi",300,
    [(1,150,None,"Hangzhou Steam Turbine / Hangzhou Boiler (CFBC)"),(2,150,None,"Hangzhou Steam Turbine / Hangzhou Boiler (CFBC)")],
    "Ind-Barath Thermal Power Ltd","private","coal",None,None,"2x150 MW CFBC with air-cooled condensers; commissioning date not given.",(28,30),["IBTPL"])
recs[-1]["water"]["cooling"]="air-cooled condenser"
rec("mutiara-tpp","Mutiara Thermal Power Plant (Coastal Energen)","coal","operating","Thoothukudi",1200,
    [(1,600,"23.12.2014"),(2,600,"16.01.2016")],"Coastal Energen Pvt Ltd","private","coal",None,None,
    "Coal & Oil Group; 15-year PPA with TANGEDCO signed 2014-12-19. Unit 1 began supply 2014-12-23, Unit 2 live 2016-01-16.",(28,30),["MTPP","Mutiara","Muthiara"])
rec("ntpl-tuticorin","NLC Tamil Nadu Power Ltd, Tuticorin","coal","operating","Thoothukudi",1000,
    [(1,500,"18.06.2015"),(2,500,"29.08.2015")],"NLC Tamilnadu Power Ltd (NLC India 89% : TANGEDCO 11%)","jv","coal",None,None,
    "JV of NLC India and TANGEDCO (89:11) in V.O.C. Port Trust Harbour Estate adjacent to TTPS; COD U1 2015-06-18, U2 2015-08-29. PPA shares: TN 439.02, KA 179.13, PY 10.78, KL 82.24, AP 133.18, TS 155.65 MW.",
    (29,30),["NTPL"])
rec("itpcl-cuddalore","IL&FS Tamil Nadu Power Company Ltd (ITPCL), Cuddalore","coal","operating","Cuddalore",1200,
    [(1,600,"29.09.2015"),(2,600,"30.04.2016")],"IL&FS Tamil Nadu Power Co Ltd","private","coal",None,None,
    "At Kothattai, Ariyagoshti and Villianallur villages, Chidambaram taluk. Planned 3180 MW; Phase I 2x600 (COD U1 2015-09-29, U2 2016-04-30); Phase II 3x660 MW planned.",(28,30),["ITPCL"])
rec("itpcl-cuddalore-ph2","ITPCL Cuddalore Phase II","coal","planned","Cuddalore",1980,
    [(1,660,None,None,"planned"),(2,660,None,None,"planned"),(3,660,None,None,"planned")],"IL&FS Tamil Nadu Power Co Ltd","private","coal",None,None,
    "Second phase of the 3180 MW ITPCL project (3x660 MW) per 2020 database.",(28,))

# ---------------- lignite Table 4/5 p32, text p30-31
rec("neyveli-tps-1","Neyveli Thermal Power Station I","lignite","operating","Cuddalore",600,
    [(k+1,50) for k in range(6)]+[(7,100),(8,100),(9,100)],"NLC India Ltd","central","lignite","Neyveli Mine-I lignite",None,
    "6x50 + 3x100 MW; first unit synchronised May 1962, last Sept 1970; life extension 1992-99; kept in service pending Neyveli New TPP (2x500, sanctioned June 2011) which replaces it. Status as of 2020 PDF.",
    (30,104),["NLC TPS-I","Neyveli TPS-I"])
rec("neyveli-tps-2","Neyveli Thermal Power Station II","lignite","operating","Cuddalore",1470,
    [(1,210,"1978"),(2,210,"1978"),(3,210,"1978"),(4,210,"1986"),(5,210,"1986"),(6,210,"1993"),(7,210,"1993")],
    "NLC India Ltd","central","lignite","Neyveli Mine-II lignite",None,
    "Stage I (3x210) sanctioned Feb 1978, expansion to 1470 MW sanctioned Feb 1983; first unit synchronised March 1986, unit VII June 1993. Unit years in Table 4 (1978/1986/1993) look like sanction years, not COD.",
    (30,32),["NLC TPS-II","Neyveli TPS-II"])
rec("neyveli-tps-1-exp","Neyveli Thermal Power Station I Expansion","lignite","operating","Cuddalore",420,
    [(1,210,"2002-10"),(2,210,"2003-07")],"NLC India Ltd","central","lignite","Neyveli Mine-I Expansion lignite",None,
    "Sanctioned Feb 1996; Unit I synchronised Oct 2002, Unit II July 2003.",(31,32),["NLC TPS-I Expansion","Neyveli TPS-I Exp"])
rec("neyveli-tps-2-exp","Neyveli Thermal Power Station II Expansion","lignite","operating","Cuddalore",500,
    [(1,250,"2015-07"),(2,250,"2015-04")],"NLC India Ltd","central","lignite","Neyveli Mine-II expansion lignite",None,
    "2x250 MW CFBC (first 250 MW CFBC units in India); Unit II COD April 2015, Unit I July 2015.",(31,32),["NLC TPS-II Expansion"])
rec("neyveli-new-tpp","Neyveli New Thermal Power Project (NNTPS)","lignite","under_construction","Cuddalore",1000,
    [(1,500,None,None,"under_construction"),(2,500,None,None,"under_construction")],"NLC India Ltd","central","lignite",None,None,
    "2x500 MW sanctioned June 2011 as replacement for TPS-I (status per 2020 PDF).",(30,),["NNTPS"])
rec("taqa-neyveli","TAQA Neyveli Lignite Thermal Power Plant","lignite","operating","Cuddalore",250,
    [(1,250,"2002")],"TAQA (Abu Dhabi National Energy Co)","private","lignite",None,None,
    "In operation since 2002; entire output sold to TANGEDCO under 30-year PPA.",(32,),["TAQA","ST-CMS"])

# ---------------- gas Table 6 p36, text p35-37; Table 36 p108
rec("bbgtps","Basin Bridge Gas Turbine Power Station","gas","operating","Chennai",120,
    [(k+1,30,"1996") for k in range(4)],"TANGEDCO","state","naphtha","naphtha (dual fuel naphtha/natural gas, HSD start)",None,
    "OECF Japan-aided, ~3 km from Chennai Central. Open cycle, run on naphtha as no gas at Chennai; since 2010-01-20 also run as synchronous condensers for reactive power.",
    (35,36,108),["BBGTPS","Basin Bridge GT"])
rec("kgtps","Kuttalam Gas Turbine Power Station","gas","operating","Nagapattinam",101,None,"TANGEDCO","state","gas","natural gas",None,
    "Combined cycle at Maruthur village near Kuttalam, 15 km from Mayiladuthurai. Table 6 gives 2003, Table 36 gives 2004 as year of operation.",
    (36,108),["KGTPS","Kuttalam GTPS"])
rec("tkgtps","Thirumakottai (Kovilkalappal) Gas Turbine Power Station","gas","operating","Thiruvarur",107.88,None,"TANGEDCO","state","gas","natural gas from ONGC wells ~10 km away",None,
    "TANGEDCO's first combined-cycle gas station, at Thirumakottai 18 km from Mannargudi; commissioned 2001.",(35,36,108),["TKGTPS","Kovilkalappal","Thirumakkottai GTPS"])
rec("vgtps-1","Valuthur Gas Turbine Power Station Phase I","gas","operating","Ramanathapuram",95,None,"TANGEDCO","state","gas","natural gas",None,
    "Combined cycle at Valuthur village; commissioned 2003.",(35,36,108),["VGTPS","VGTPS-I"])
rec("vgtps-2","Valuthur Gas Turbine Power Station Phase II","gas","operating","Ramanathapuram",92.2,None,"TANGEDCO","state","gas","natural gas",None,
    "Phase II combined cycle; commissioned 2008 (Table 36 lists 92 MW).",(36,108),["VGTPS Phase II","VGTPS-II"])
rec("ppn-power","PPN Power Generating Company (Pillaiperumalnallur) CCPP","gas","operating","Nagapattinam",330.5,
    [(1,330.5,"2001-04")],"PPN Power Generating Co Pvt Ltd","private","gas","natural gas cum naphtha",None,
    "Combined cycle at Pillaiperumalnallur and Manickapangu villages, Tharangambadi taluk; operating since April 2001; entire output to TANGEDCO under long-term PPA.",(36,39,109),["PPN","P.Nallur"])
rec("lanco-tanjore","Lanco Tanjore Power Company (Karuppur) CCPP","gas","operating","Thanjavur",119,
    [(1,67.8,"2005-08"),(2,51.2,"2005-08")],"Lanco Tanjore Power Co Ltd (Aban)","private","gas","natural gas (GAIL)",None,
    "Combined cycle at Karuppur village, Thiruvidaimaruthur taluk; commercial operation Aug 2005; 15-year PPA with TNEB. Table 7 labels it 'Lanco Tanjore Power Company ABAN'.",(37,39,109),["LTPCL","Karuppur","ABAN"])
rec("arkay-valantharavai","Arkay Energy (Rameswarm) Ltd, Valantharavai CCPP","gas","operating","Ramanathapuram",150,None,"Arkay Energy (Rameswarm) Ltd (Ind-Barath group)","private","gas","natural gas (GAIL)",None,
    "150 MW combined cycle at Valantharavai; 35 MW expansion under development. Table 7 labels it 'Arkay Energy Ltd.(PENNA) PIONEER'.",(37,39,109),["AERL","Valantharavai","Penna"])

# ---------------- captive gas/oil/waste heat Table 24 p85, Tables 38-39 p109
cap=[("captive-sedco-thiruvarur","SEDCO captive co-gen","gas","Thiruvarur",7.98,[(1,2.74),(2,2.74),(3,2.5)],"natural gas","14.12.1998","Thiruvarur EDC / 33 kV",(85,109)),
     ("captive-mms-steel-koilkalappal","MMS Steel & Power (Koilkalappal)","gas","Nagapattinam",6.12,[(1,3.06),(2,3.06)],"natural gas","19.09.2006","Thiruvarur EDC / 33 kV (mere parallel)",(85,109)),
     ("captive-sabari-industries","Sabari Industries captive co-gen","cogen","Pudukkottai",6.0,None,"waste heat","02.10.2005","Pudukottai EDC / 11 kV",(85,)),
     ("captive-jagannath-textile","Jagannath Textile Company","diesel","Tiruppur",5.4,[(1,2.7),(2,2.7)],"diesel / HFO","01.12.2006","Coimbatore South EDC / 33 kV (mere parallel)",(85,109)),
     ("captive-noble-tech","Noble Tech Industries captive co-gen","cogen","Kancheepuram",8.0,None,"waste heat","07.05.2007","Kanchipuram EDC / 33 kV",(85,)),
     ("captive-loyal-textile","Loyal Textile Mills","diesel","Thoothukudi",4.1,None,"HFO","30.04.2010","Tuticorin EDC / 11 kV (mere parallel)",(85,109)),
     ("captive-thiagaraja-mills","Thiagaraja Mills","diesel","Madurai",3.08,None,"diesel / FO","28.06.1999","Madurai Metro EDC / 11 kV (mere parallel)",(85,109)),
     ("captive-sun-paper-mill","Sun Paper Mill","cogen","Tirunelveli",6.0,None,"lignite & biomass","1998","Tirunelveli EDC / 11 kV (mere parallel)",(85,)),
     ("captive-basudha-udyog","Basudha Udyog Pvt Ltd","cogen","Tiruvallur",10.0,None,"waste heat","2012-03","Chennai North EDC / 33 kV (mere parallel)",(85,)),
     ("captive-opg-renewable-waste-heat","OPG Renewable Energy Pvt Ltd (waste heat)","cogen","Tiruvallur",10.0,None,"waste heat","26.08.2008","Chennai North EDC / 33 kV (mere parallel)",(85,))]
fmap={"natural gas":"gas","diesel / HFO":"naphtha","HFO":None,"diesel / FO":None,"waste heat":None,"lignite & biomass":"biomass"}
for i,n,t,dist,c,u,f,dt,ev,pg in cap:
    prim={"gas":"gas","diesel":None,"cogen":None}[t]
    if f=="lignite & biomass": prim="biomass"
    r=rec(i,n,t,"operating",dist,c,[(x[0],x[1],dt) for x in u] if u else None,n,"private",prim,f,None,
        "Captive/co-gen plant (33 kV and below) synchronised %s; %s."%(d(dt),ev),pg)
    r["evacuation"]=[ev]
recs[[r["id"] for r in recs].index("captive-loyal-textile")]["history"]+=" Table 24 lists district Thoothukudi, Table 39 lists Viruthunagar."

# Table 29 p93 co-gen selling to TANGEDCO
rec("cpcl-manali-cogen","CPCL Manali captive power plant","cogen","operating","Tiruvallur",129.9,None,"Chennai Petroleum Corporation Ltd","central","naphtha","naphtha",None,
    "Refinery captive plant at Manali, Chennai; sells 3.0 MW infirm power to TANGEDCO (agreement 2016-03-31 to 2019-03-30). Data as on 2018-05-29.",(93,),["CPCL"])
rec("sipcot-gummidipoondi-k16-waste-heat","Waste-heat plant, K16 Phase II SIPCOT Gummidipoondi","cogen","operating","Tiruvallur",33.7,None,None,"private",None,"waste heat",None,
    "Company name not printed (only address K16, Phase II, SIPCOT Industrial Complex, Gummidipoondi); sells 2.0 MW firm to TANGEDCO (2015-06-29 to 2018-06-28).",(93,))
rec("jsw-steel-salem-cpp","JSW Steel Salem captive power plant","coal","operating","Salem",60,None,"JSW Steel Ltd","private","coal",None,None,
    "Captive plant at Pottaneri, Mecheri, Mettur taluk; sells 15 MW infirm to TANGEDCO (2015-12-26 to 2018-12-25).",(93,),["JSW Salem"])
rec("tnpl-mondipatti-cpp","TNPL Mondipatti (Unit II) captive power plant","coal","operating","Tiruchirappalli",30,None,"Tamil Nadu Newsprint and Papers Ltd","state","coal",None,None,
    "Captive plant at Mondipatty village, Manaparai taluk; sells 8 MW infirm to TANGEDCO (2015-11-13 to 2018-11-12).",(93,),["TNPL"])

# ---------------- nuclear p58-59, Table 15/51
rec("maps","Madras Atomic Power Station (Kalpakkam)","nuclear","operating","Chengalpattu",440,
    [(1,220,"1984-01-27",None,"operating"),(2,220,"1986-03-21",None,"operating")],"NPCIL","central","uranium","natural uranium PHWR",None,
    "First indigenously built nuclear station in India (DAE with L&T). MAPS-1 critical 1983, full power Jan 1984; MAPS-2 critical 1985, full power March 1986. PDF gives district as Kancheepuram (pre-2019 district split).",
    (58,110,111),["MAPS","Madras APS"])
rec("kudankulam","Kudankulam Nuclear Power Project","nuclear","operating","Tirunelveli",2000,
    [(1,1000,"2014-12-31",None,"operating"),(2,1000,"2017-03-31",None,"operating"),(3,1000,None,None,"planned"),(4,1000,None,None,"planned"),(5,1000,None,None,"planned"),(6,1000,None,None,"planned")],
    "NPCIL","central","uranium","enriched uranium VVER-1000",None,
    "On the Gulf of Mannar shore 4 km south of Kudankulam village, Radhapuram taluk. Six VVER-1000 planned with Atomstroyexport. Unit 1 grid-synchronised 2013-10-22 (COD 2014-12-31); Unit 2 critical 2016-07-10, synchronised 2016-08-29 (COD 2017-03-31). Units 3-6 'approved' as of 2020 PDF (status to be updated from NPCIL). capacity_mw counts only operating units 1-2.",
    (59,110,111,124),["KKNPP","KKNPS","Kudankulam NPP"])
recs[-1]["water"]["source"]="Gulf of Mannar (sea water)"
rec("pfbr-kalpakkam","Prototype Fast Breeder Reactor (MAPS Unit 3), Kalpakkam","nuclear","under_construction","Chengalpattu",500,
    [(1,500,None,None,"under_construction")],"BHAVINI (PDF lists NPCIL)","central","uranium","U-Pu MOX fast breeder",None,
    "Listed as 'MAPS, Unit-3 PFBR 500 MWe' among new nuclear projects in the 2020 database.",(59,124),["PFBR","MAPS Unit-3"])
rec("fbr-kalpakkam-4-5","Fast Breeder Reactors 1&2 (MAPS Units 4-5), Kalpakkam","nuclear","planned","Chengalpattu",1200,
    [(4,600,None,None,"planned"),(5,600,None,None,"planned")],"NPCIL (per PDF)","central","uranium","fast breeder",None,
    "Listed as MAPS Unit-4 and Unit-5 FBR 600 MWe each (planned) in 2020 database.",(59,124),["FBR 1&2"])

# ---------------- hydro: Tables 9-12 p46-55 (+ Table 43 p113-116 for district/year)
H=[
# id,name,district,circle,source/reservoir,elev_ft,units[(no,mw,date)],pages,aliases,type
("kundah-1","Kundah Power House I","Nilgiris","Kundah","Avalanche & Emerald dams",5353,[(1,20,"08.07.1960"),(2,20,"22.07.1960"),(3,20,"01.04.1964")],(46,113),["Kundah PH-1","Kundah-I"]),
("kundah-2","Kundah Power House II","Nilgiris","Kundah","Kundah forebay dam + tail race of PH-I (forebay 1000 cusec)",2876,[(1,35,"30.10.1960"),(2,35,"10.01.1961"),(3,35,"02.05.1961"),(4,35,"16.06.1961"),(5,35,"23.02.1964")],(46,113),["Kundah PH-2","Kundah-II"]),
("kundah-3","Kundah Power House III","Coimbatore","Kundah","Pegumbahallah dam, Nirali pallam and Kattery weir",1429,[(1,60,"07.04.1965"),(2,60,"11.06.1965"),(3,60,"18.02.1978")],(46,113),["Kundah PH-3","Kundah-III"]),
("kundah-4","Kundah Power House IV","Coimbatore","Kundah","Pillur dam, tail race of PH-III",1193,[(1,50,"27.02.1966"),(2,50,"19.10.1978")],(46,113),["Kundah PH-4","Kundah-IV"]),
("kundah-5","Kundah Power House V","Nilgiris","Kundah","Western Catchment-1, Upper Bhavani dam",6527,[(1,20,"30.10.1964"),(2,20,"06.12.1989")],(47,114),["Kundah PH-5","Kundah-V"]),
("kundah-6","Kundah Power House VI (Parsons Valley)","Nilgiris","Kundah","Western Catchment 2 & 3, Porthimund dam, Parsons Valley dam",6519,[(1,30,"20.03.2000")],(47,113),["Kundah PH-6","Parsons Valley","Kundah-VI"]),
("pykara-micro","Pykara Micro Power House","Nilgiris","Kundah","Pykara dam",6550,[(1,1,"09.10.1989"),(2,1,"09.10.1989")],(47,113),["Pykara Micro Hydel"]),
("moyar","Moyar Power House","Nilgiris","Kundah","Moyar forebay dam, Maravakandy dam, Pykara PH tail race",2000,[(1,12,"10.04.1952"),(2,12,"19.09.1952"),(3,12,"06.01.1953")],(47,113),["Moyar"]),
("maravakandy-micro","Maravakandy Power House","Nilgiris","Kundah","discharge from Pykara PH",2900,[(1,0.75,"14.10.1992")],(47,113),["Maravakandi Micro Hydel"]),
("mukurthy-micro","Mukurthy Micro Power House","Nilgiris","Kundah","discharge from Mukurthy dam",6800,[(1,0.35,"27.06.2001"),(2,0.35,"01.11.2003")],(48,115),["Mukuruthy Micro"]),
("pushep","Pykara Ultimate Stage Hydro Electric Project (PUSHEP)","Nilgiris","Kundah","Pykara (non-irrigation)",4420,[(1,50,"06.09.2005"),(2,50,"06.09.2005"),(3,50,"06.09.2005")],(48,113),["PUSHEP","Pykara Ultimate"]),
("pykara","Pykara Power House (Singara)","Nilgiris","Kundah","Mukurthy, Pykara, Sandynallah and Glenmorgan dams",3400,[(1,7,"09.06.1933"),(2,7,"22.11.1932"),(3,7,"05.09.1932"),(5,11,"28.08.1939"),(6,13.6,"30.05.1954"),(7,13.6,"11.06.1954")],(48,113),["Pykara","Singara"]),
("sholayar-1","Sholayar Power House I","Coimbatore","Kadamparai","Sholayar reservoir (4800 Mcft at FRL)",1931,[(1,35,"22.04.1971"),(2,35,"04.05.1971")],(49,116),["Sholayar-1","Manomboli"]),
("sholayar-2","Sholayar Power House II","Coimbatore","Kadamparai","Sholayar reservoir (interstate sharing with Kerala)",2750,[(1,25,"29.03.1971")],(49,116),["Sholayar-2"]),
("aliyar","Aliyar Power House","Coimbatore","Kadamparai","Upper Aliyar dam (914.89 Mcft)",1083,[(1,60,"21.03.1970")],(49,116),["Aliyar"]),
("aliyar-mini","Aliyar Mini Power House (Lower Aliyar)","Coimbatore","Kadamparai","Lower Aliyar dam (3553 Mcft)",1083,[(1,1.25,"23.09.2002"),(2,1.25,"23.09.2002")],(49,115),["Lower Aliyar"]),
("sarkarpathy","Sarkarpathy Power House","Coimbatore","Kadamparai","Parambikulam, Thunakadavu (11820 Mcft)",1429,[(1,30,"14.08.1966")],(50,116),["Sakarapathy","Sarkarpathy"]),
("thirumurthy-mini","Thirumurthy Mini Power House","Tiruppur","Kadamparai","Thirumurthy dam (irrigation)",None,[(1,0.65,"20.03.2000"),(2,0.65,"20.03.2000"),(3,0.65,"20.03.2000")],(50,115),["Thirumoorthi Micro"]),
("poonachi-mini","Poonachi Mini Power House","Coimbatore","Kadamparai","Punachi river (run-of-river)",None,[(1,1,"12.11.1992"),(2,1,"16.12.1992")],(50,115),["Poonachi Micro"]),
("amaravathi","Amaravathi Power House","Coimbatore","Kadamparai","Amaravathy dam (3749 Mcft)",None,[(1,2,"21.09.2006"),(2,2,"30.11.2006")],(50,115),["Amaravathy"]),
("mettur-dam","Mettur Dam Power House","Salem","Erode","Mettur (Stanley) reservoir",650,[(1,12.5,"13.06.1937"),(2,12.5,"21.08.1937"),(3,12.5,"21.01.1938"),(4,12.5,"28.10.1946")],(51,114),["Mettur Dam"]),
("mettur-tunnel","Mettur Tunnel Power House","Salem","Erode","Mettur (Stanley) reservoir",726,[(1,50,"16.08.1965"),(2,50,"21.07.1966"),(3,50,"21.07.1966"),(4,50,"31.07.1966")],(51,114),["Mettur Tunnel"]),
("lower-mettur-1","Lower Mettur Barrage Power House 1 (Chekkanur)","Salem","Erode","Cauvery pondage, Lower Mettur barrage 1",626,[(1,15,"12.08.1988"),(2,15,"07.08.1988")],(51,114),["LMHEP Barrage 1","Chekkanur"]),
("lower-mettur-2","Lower Mettur Barrage Power House 2 (Nerinjipettai)","Salem","Erode","Cauvery pondage",577,[(1,15,"26.08.1988"),(2,15,"04.08.1988")],(51,114),["LMHEP Barrage 2","Nerinjipettai"]),
("lower-mettur-3","Lower Mettur Barrage Power House 3 (Kuthiraikkalmedu / Koneripatti)","Erode","Erode","Cauvery pondage",564,[(1,15,"04.01.1988"),(2,15,"30.09.1988")],(52,114),["LMHEP Barrage 3","Konerpatti","Kuthiraikkalmedu"]),
("lower-mettur-4","Lower Mettur Barrage Power House 4 (Uratchikottai)","Erode","Erode","Cauvery pondage",530,[(1,15,"18.09.1989"),(2,15,"28.12.1988")],(52,114),["LMHEP Barrage 4","Uratchikottai"]),
("bhavani-kattalai-1","Bhavani Kattalai Barrage Power House I","Erode","Erode","Cauvery (Bhavani Kattalai barrage I, near Uratchikottai)",500,[(1,15,"01.08.2006"),(2,15,"22.09.2006")],(52,114),["Bhavani Kattalai PH-1","BKB-I"]),
("sathanur","Sathanur Power House","Tiruvannamalai","Erode","Sathanur dam",680,[(1,7.5,"10.03.1999")],(52,115),["Sathanur Micro"]),
("lower-bhavani-micro","Lower Bhavani Micro Hydel Power House (Bhavanisagar)","Erode","Erode","Bhavanisagar dam",835,[(1,2,"26.05.1990"),(2,2,"17.04.1990"),(3,2,"11.04.1990"),(4,2,"03.04.1990")],(52,115),["Bhavanisagar Micro Hydel","Lower Bhavani-1"]),
("lower-bhavani-rbc","Lower Bhavani RBC Power House","Erode","Erode","Bhavanisagar dam (Right Bank Canal)",835,[(1,4,"10.02.1998"),(2,4,"28.02.1998")],(53,115),["Bhavanisagar RBC"]),
("bhavani-kattalai-2","Bhavani Kattalai Barrage Power House II","Erode","Erode","Bhavani Kattalai barrage-I tail (~3 km from Pallipalayam)",465,[(1,15,"28.07.2011"),(2,15,"29.09.2011")],(53,114),["Bhavani Kattalai PH-2","BKB-II"]),
("kodayar-1","Kodayar Power House I","Kanyakumari","Tirunelveli","Upper Kodayar (Kodayar dam I, 2589.8 Mcft)",1319.78,[(1,60,"09.12.1970")],(53,116),["Kodayar-1"]),
("kodayar-2","Kodayar Power House II","Kanyakumari","Tirunelveli","Lower Kodayar (Kodayar dam II)",340.77,[(1,40,"17.11.1971")],(54,116),["Kodayar-2"]),
("servalar","Servalar Power House","Tirunelveli","Tirunelveli","Servalar dam (interlinked with Karaiyar dam, 1135 Mcft)",205.2,[(1,20,"23.03.1986")],(54,116),["Servalar"]),
("papanasam","Papanasam Power House","Tirunelveli","Tirunelveli","Papanasam (Karaiyar) dam",98,[(1,8,"08.07.1944"),(2,8,"12.12.1944"),(3,8,"10.06.1945"),(4,8,"08.07.1951")],(54,116),["Papanasam"]),
("suruliyar","Suruliyar Power House","Theni","Tirunelveli","Suruliyar (tributary of Vaigai); rated head 979.15 m",1028.8,[(1,35,"27.08.1978")],(54,116),["Suruliyar"]),
("periyar","Periyar Power House","Theni","Tirunelveli","Periyar stream (Mullaperiyar); rated head 373.38 m",1574,[(1,42,"12.10.1958"),(2,42,"19.02.1959"),(3,35,"07.06.1959"),(4,35,"22.12.1965")],(54,115),["Periyar","Lower Camp"]),
("vaigai-micro","Vaigai Power House","Theni","Tirunelveli","Vaigai river; rated head 27.54 m",261.76,[(1,3,"04.03.1990"),(2,3,"04.03.1990")],(55,115),["Vaigai Micro Hydel"]),
("perunchani","Perunchani Power House","Kanyakumari","Tirunelveli","Perunchani river",1574,[(1,0.65,"21.12.2005"),(2,0.65,"22.01.2006")],(55,115),["Perunchani"]),
("periyar-vaigai-mini-1","Periyar Vaigai Mini Power House I","Theni","Tirunelveli","Periyar stream",462,[(1,2,"02.10.2010"),(2,2,"21.01.2011")],(55,116),["Periyar Vaigai Micro I"]),
("periyar-vaigai-mini-2","Periyar Vaigai Mini Power House II","Theni","Tirunelveli","Periyar stream",450,[(1,1.25,"30.01.2012"),(2,1.25,"30.01.2012")],(55,116),["Periyar Vaigai Micro II"]),
]
for i,n,dist,circle,src,el,u,pg,al in H:
    cap=round(sum(x[1] for x in u),3)
    hist="TANGEDCO %s hydro circle."%circle + (" Powerhouse elevation %s ft (PDF)."%el if el else "")
    if i=="periyar": hist+=" PDF prints '2 X 35 / 2 X 42 = 154 MW'; unit-to-rating mapping (U1-2 42 MW per dates list) and current rating (DGR 168 MW) differ."
    if i=="pykara": hist+=" PDF prints 7 units '3x7 + 1x11 + 2x13.6 = 59.2 MW' but lists dates only for units 1,2,3,5,6,7; mw-to-unit mapping inferred from stage chronology (1932-33 stage I 3x7, 1939 unit 11 MW, 1954 2x13.6)."
    if i in("kundah-3","kundah-4"): hist+=" PDF places it in Coimbatore district."
    if i=="amaravathi": hist+=" PDF says Coimbatore district (Amaravathi dam is in present Tiruppur district)."
    if i=="lower-bhavani-micro": hist+=" 4x2 MW per Table 11."
    r=rec(i,n,"hydro","operating",dist,cap,[(x[0],x[1],x[2]) for x in u],"TANGEDCO (now TNGECL)","state","water",None,src,hist,pg,al)
rec("kadamparai-psp","Kadamparai Pumped Storage Power House","pumped_storage","operating","Coimbatore",400,
    [(1,100,"17.10.1987"),(2,100,"26.02.1988"),(3,100,"12.04.1989"),(4,100,"16.12.1988")],"TANGEDCO (now TNGECL)","state","water",None,
    "Kadamparai reservoir (upper) / Upper Aliyar dam (lower); net capacity 940.38/737 Mcft",
    "TANGEDCO Kadamparai hydro circle; pumped storage scheme 4x100 MW. Powerhouse elevation 710 ft (PDF). Table 10 gives Coimbatore district, Table 43 gives Tiruppur.",(50,116),["Kadamparai","Kadampari"])
# generation-table-only hydro entries
rec("bhavani-kattalai-3","Bhavani Kattalai Power House III","hydro","operating","Erode",None,None,"TANGEDCO (now TNGECL)","state","water",None,"Cauvery",
    "Appears only in Table 43 (generation) with year of operation 2013; no capacity given in circle tables.",(114,),["Bhavani Kattalai PH-3"])
rec("bhavani-barrage-2","Bhavani Barrage 2 Power House","hydro","operating","Erode",None,None,"TANGEDCO (now TNGECL)","state","water",None,"Bhavani",
    "Appears only in Table 43 (generation) with year of operation 2012 (2.42 MU in 2016-17); no capacity given in circle tables.",(114,),["Bhavani Barrage 2 PH"])
rec("periyar-vaigai-mini-3","Periyar Vaigai Mini Power House III","hydro","operating","Theni",None,None,"TANGEDCO (now TNGECL)","state","water",None,"Periyar stream",
    "Table 43 reports combined generation for 'Periyar Vaigai Micro I, II and III' (from 2010); unit III capacity not given.",(116,),["Periyar Vaigai Micro III"])
# planned hydro Table 8 p44
rec("kollimalai-hep","Kollimalai Hydro Electric Project","hydro","planned","Namakkal",20,[(1,20,None,None,"planned")],"TANGEDCO","state","water",None,None,"Ongoing project per 2020 database.",(44,124))
rec("kundah-psp","Kundah Pumped Storage Hydro-electric Project","pumped_storage","under_construction","Nilgiris",500,[(k+1,125,None,None,"under_construction") for k in range(4)],"TANGEDCO","state","water",None,
    "Upper: Porthimund reservoir (live 20.10 Mm3, FRL 2220.46 m, MDDL 2207.55 m); lower: Avalanche-Emerald reservoir (live 130.84 Mm3, FRL 1985.80 m, MDDL 1957.98 m)",
    "4x125 MW pumped storage in the Nilgiris for peaking (ongoing per 2020 database).",(44,124),["Kundah PSP"])
rec("sillahalla-psp-1","Sillahalla Pumped Storage Project Stage I","pumped_storage","planned","Nilgiris",1000,[(k+1,250,None,None,"planned") for k in range(4)],"TANGEDCO","state","water",None,
    "Upper dam on Sillahalla stream (tributary of Kundah river, joins ~1.4 km upstream of Kundah Palam dam)",
    "Upper reservoir in Udhagamandalam & Kundah taluks, lower reservoir in Kundah taluk.",(44,124),["Sillahallah PSP"])
rec("sillahalla-psp-2","Sillahalla Pumped Storage Project Stage II","pumped_storage","planned","Nilgiris",1000,[(k+1,250,None,None,"planned") for k in range(4)],"TANGEDCO","state","water",None,None,
    "Second stage of Sillahalla PSP (4x250 MW).",(44,124),["Sillahallah PSP Stage II"])

# ---------------- biomass Table 27 p91 (MNRE biomass portal 2020)
B=[("Coimbatore","Venkatesteshwar Paper Mill",2.5,"1996-97/1997-98"),("Coimbatore","Orient Green Power Co. Ltd",10.0,"04.07.11"),
("Dindigul","Shriram Power Gen Ltd",7.5,"02.11.07"),("Kancheepuram","Nandha Energy Ltd (c/o Mohan Breweries & Distilleries)",18.0,"31.03.97"),
("Krishnagiri","Synergy Shakthi Renewable Energy Ltd",10.0,"22.02.10"),("Madurai","Servall Engineering Industries Ltd",2.5,"1995-96/1996-97"),
("Madurai","Auro Mira Bio Energy Madurai Ltd",10.0,"04.02.09"),("Madurai","Astro Energy and Biom Systems Ltd",10.0,None),
("Pudukkottai","Empee Distilleries Ltd",10.0,"17.04.08"),("Pudukkottai","Chitra Bio Energy Ltd",7.5,"22.03.06"),
("Ramanathapuram","Raghu Rama Renewable Energy Ltd",18.0,None),("Sivaganga","Aurobindo Energy Pvt Ltd",15.0,"05.09.06"),
("Sivaganga","TCP Limited (biomass)",9.0,"24.11.06"),("Thanjavur","G.B. Engineering Pvt Ltd",6.0,"2008"),
("Thanjavur","Shriram Non-Conventional Energy Ltd",7.5,"04.02.09"),("Theni","Shri Renuga Textiles Ltd",4.5,"25.10.08"),
("Tiruvannamalai","Southern Power Tech Equipments Pvt Ltd",6.0,None),("Thoothukudi","Ind-Barath Energies Ltd",20.0,"22.03.06"),
("Thoothukudi","Rajkumar Impex Pvt Ltd",6.0,"12.04.12"),("Thoothukudi","SPIC Electric Power Corporation Ltd",7.0,None),
("Tirunelveli","Prathyusha Power Pvt Ltd",10.0,"03.08.07"),("Tirunelveli","Auro Mira Bio Power India Pvt Ltd",15.0,"06.07.11"),
("Tiruvallur","Manali Petro Chemicals Ltd",4.7,"15.11.08"),("Tiruvallur","Cetex Energy Generation Pvt Ltd",12.0,None),
("Tiruvannamalai","Global Power Tech Equipments Ltd",7.5,"04.02.10"),("Thoothukudi","Continental Warehousing Corporation Ltd",6.0,None),
("Virudhunagar","ETA Powergen Pvt Ltd",10.0,"22.05.09"),("Virudhunagar","Sripathi Paper and Boards Pvt Ltd",4.9,"09.03.11")]
def slug(s): return re.sub(r'[^a-z0-9]+','-',s.lower()).strip('-')
seen=set()
for dist,n,c,dt in B:
    i="biomass-"+slug(n.split('(')[0])+"-"+slug(dist)
    dd=d(dt) if dt and '/' not in dt else None
    h="MNRE Biomass Portal 2020 via Table 27 (biomass-based co-gen)."+(" Commissioned %s."%dt if dt and not dd else "")
    rec(i,n,"biomass","operating",dist,c,[(1,c,dd)] if dd else None,n,"private","biomass",None,None,h,(91,))
# ---------------- bagasse Table 28 p92
G=[("Cuddalore","M.R.K. Coop. Sugar Mills Ltd",3.5,"1992","coop"),("Cuddalore","EID Parry (India) Ltd",14.0,"1997",None),
("Cuddalore","Supreme Renewable Energy Ltd",24.0,None,None),("Cuddalore","EID Parry (India) Ltd",12.0,None,None),
("Dharmapuri","Subramaniya Siva Coop. Sugar Mills Ltd",2.0,"1998","coop"),("Erode","Bannari Amman Sugar Ltd",13.5,None,None),
("Erode","Sakthi Sugars",18.0,None,None),("Erode","Sakthi Sugars",18.0,None,None),("Kancheepuram","S.V. Sugars",2.5,"1997",None),
("Madurai","Rajshree Sugars and Chemicals Ltd",8.0,"1996",None),("Madurai","Astro Energy and Biom Systems Ltd",10.0,"2009",None),
("Perambalur","Kothari Sugars and Chemicals Ltd",12.0,None,None),("Perambalur","Mahalakshmi Srinivasan Sugar Mills",15.0,None,None),
("Pudukkottai","EID Parry (India) Ltd",10.0,None,None),("Sivaganga","Sakthi Sugars Ltd",2.0,"2002",None),
("Thanjavur","Thiru Arooran Sugars Ltd",9.0,"1996",None),("Thanjavur","Thiru Arooran Sugars Ltd",8.0,"1998",None),("Thanjavur","Auro Energy Ltd",7.0,None,None),
("Tiruvannamalai","Arunachalam Sugar",8.0,"2002",None),("Tiruvannamalai","Cheyyar Coop. Sugar Mills Ltd",3.5,"1993","coop"),
("Tiruchirappalli","EID Parry (India) Ltd",15.0,"2002",None),("Tiruchirappalli","EID Parry (India) Ltd",2.0,"2009",None),
("Tiruchirappalli","Kothari Sugars and Chemicals",8.5,"1996",None),("Tirunelveli","Thiru Arooran Sugars Ltd",13.0,"1997",None),
("Tirunelveli","Prathyusha Power Pvt Ltd",10.0,None,None),("Tirunelveli","Empee Sugars and Chemicals Ltd",18.0,None,None),
("Tirunelveli","Dharani Sugars and Chemicals Ltd",9.5,"1996",None),("Villupuram","Rajshree Sugars and Chemicals Ltd",15.0,None,None),
("Villupuram","Rajshree Sugars and Chemicals Ltd",15.0,"2008",None)]
ids=[r["id"] for r in recs]
for dist,n,c,yr,coop in G:
    base="cogen-"+slug(n)+"-"+slug(dist); i=base; k=2
    while i in ids: i=base+"-%d"%k; k+=1
    ids.append(i)
    h="Bagasse co-generation plant, Table 28 (TANGEDCO 2020)."+(" Year of commissioning %s."%yr if yr else "")
    if n.startswith("Astro Energy") : h+=" Same developer/capacity also listed as biomass plant in Table 27 (likely same plant)."
    if n.startswith("Prathyusha"): h+=" Same developer/capacity also listed as biomass plant in Table 27 (likely same plant)."
    if i!=base: h+=" Table lists this company/district more than once; separate row kept (may be a second unit or a duplicate)."
    rec(i,n,"cogen","operating",dist,c,[(1,c,yr)] if yr else None,n,"state" if coop else "private","bagasse",None,None,h,(92,))
# ---------------- biogas Table 30 p96 / Table 46 p118
rec("biogas-cmda-koyambedu","CMDA Koyambedu vegetable-market biomethanation plant","waste","operating","Chennai",0.25,None,"Chennai Metropolitan Development Authority","state","biomass","biogas from vegetable waste (~30 t/day)",None,
    "Commissioned late 2005 at Koyambedu wholesale market; ~40% of output used in-plant, rest exported to TANGEDCO.",(96,118))
rec("biogas-iot-mabagas-namakkal","IOT Mabagas biogas power plant","biomass","operating","Namakkal",2.4,None,"IOT Mabagas Ltd","private","biomass","biogas: chicken litter, sugar & starch industrial waste, cow dung",None,
    "Biogas-to-power plant; also produces compost.",(96,97,118))
rec("biogas-subhashri-bio-energies","Subhashri Bio Energies biogas power plant","biomass","operating","Namakkal",4.0,None,"Subhashri Bio Energies (P) Ltd","private","biomass","biogas: poultry waste",None,
    "4 MW biogas power cum organic manure plant (Tiruchengode group).",(96,97,118))
rec("biogas-gk-bio-energy","G.K. Bio Energy biogas power plant","biomass","operating","Namakkal",1.5,None,"G.K. Bio Energy Pvt Ltd","private","biomass","biogas: poultry waste",None,
    "1.5 MW power from poultry-waste biogas.",(96,118))
# Table 31 p99-100 other biogas (MWeq)
O=[("Sri Velmurugan Sago Factory","Malaiyalapatty","Perambalur","tapioca starch industry waste",2600,0.22),
("Palaniandavar Sago Factory","Paithur, Attur Tk","Salem","tapioca starch industry waste",3177,0.26),
("Sri Krishna Industrial Starch Factory","Gangavalli Tk","Salem","tapioca starch industry waste",5068,0.42),
("R.S. Sago Factory","Siteri, Attur Tk","Salem","tapioca starch industry waste",3755,0.31),
("Mappilai Sago Factory","Siteri, Attur Tk","Salem","tapioca starch industry waste",2020,0.17),
("Varalakshmi Company","Kommapalayam, Rasipuram","Namakkal","sago starch industry waste",20160,1.68),
("SPAC Starch Products (India) Ltd","Poonachi village, Anthiyur Tk","Erode","starch industry effluent",7200,0.60),
("Tannery fleshings & sludge biogas project","Melvisharam","Vellore","tannery fleshings and sludge",300,0.03),
("Varalakshmi Starch Industries Ltd","Salem","Salem","tapioca processing waste water",6000,0.50),
("Tamil Nadu Newsprint and Papers Ltd","Karur","Karur","paper mill effluents",15000,None),
("Varalakshmi Starch Industries Ltd","Salem","Salem","starch industry waste",12000,1.00),
("Varalakshmi Company","Mallur","Namakkal","starch industry waste",9000,0.75),
("SPAC Tapioca Products (India) Ltd","Poonachi, Bhavani Tk","Erode","tapioca starch industry waste",12000,1.00),
("Anbu Rice, Oil & Sago Factory","Ammampalayam, Attur Tk","Salem","tapioca starch industry waste",2890,0.24),
("Sri Velmurugan Sago Factory","Oduvankurichi, Rasipuram Tk","Namakkal","tapioca starch industry waste",2890,0.24),
("Sri Senthil Kumar Sago Factory","Thimmanaickenpatty, Rasipuram Tk","Namakkal","tapioca starch industry waste",2890,0.24),
("Vetrivel Sago Products","Vellakkalpatti, Rasipuram Tk","Namakkal","tapioca starch industry waste",2890,0.24),
("Sri Thirumalaivasan Sago & Starch Products","Toppapatty, Rasipuram Tk","Namakkal","tapioca starch industry waste",2890,0.24),
("Sri Venkateswara Sago & Starch Products","O. Jedarpalayam, Rasipuram Tk","Namakkal","tapioca starch industry waste",2890,0.24),
("M.R. Samy Sago Factory","Tammampatty, Gangavalli Tk","Salem","starch industry waste",2890,0.24),
("Murugan Sago Factory","Ulipuram, Gangavalli Tk","Salem","starch industry waste",3396,0.283),
("Vetrivel Sago Factory","Ulipuram Pudur, Gangavalli Tk","Salem","starch industry waste",1992,0.166),
("Annai Sago Factory","Ulipuram, Gangavalli Tk","Salem","starch industry waste",1992,0.166),
("Sri Soorya Sago Factory","Echampatty, Attur Tk","Salem","starch industry waste",1992,0.166),
("Jayamurugan Sago Factory","Kopampatty, Thuraiyur Tk","Namakkal","starch industry waste",288,0.24),
("Ganesa Samy Sago Factory","Ariyagoundampatty, Namagiripet, Rasipuram Tk","Namakkal","starch industry waste",3960,0.33),
("Sri Venkateswara Sago Factory","Namagiripet, Rasipuram Tk","Namakkal","starch industry waste",2496,0.208),
("Varalakshmi Starch Industries Ltd","Salem","Salem","starch industry waste",13000,3.28),
("Varalakshmi Starch Industries Ltd","Mallur, Salem","Salem","waste water treatment plant at sago manufacturing",None,0.20),
("Trichy Distillers & Chemicals Ltd","Senthannipuram","Tiruchirappalli","distillery waste",None,1.40)]
for n,loc,dist,f,m3,c in O:
    base="biogas-"+slug(n)+"-"+slug(loc.split(',')[0]); i=base; k=2
    while i in ids: i=base+"-%d"%k; k+=1
    ids.append(i)
    rec(i,n+" biogas plant, "+loc,"biomass","operating",dist,c,None,n,"private","biomass","biogas: "+f,None,
        "Table 31 'Other biogas plants' (GoI Ministry of Energy 2018); capacity printed as MW-equivalent of biogas (%s m3/day) - may not be grid-connected electrical capacity."%(m3 if m3 else "n/a"),(99,100))

# ---------------- wind / solar clusters Table 44/45 p117-118
W=[("Tirunelveli",3700),("Thoothukudi",245.97),("Kanyakumari",118.81),("Ramanathapuram",2.15),("Coimbatore",355.25),("Tiruppur",2264.98),("Dindigul",420.00),("Theni",534.70),("Chennai",0.22)]
for dist,c in W:
    rec("wind-cluster-"+slug(dist)+"-2018","Wind generators, %s district (2018 total)"%dist,"wind","operating",dist,c,None,"various","private","wind",None,None,
        "District total from Table 44 (state total 7642.09 MW; text says 8631 MW end-2018 statewide). Wind passes: Aralvaimozhi (Kanyakumari/Tirunelveli), Senkottah (Tirunelveli/Thoothukudi), Cumbum (Dindigul/Theni), Palghat (Coimbatore/Tiruppur/Erode).",(76,117),cluster=True)
S=[("Sivaganga",11.55),("Nagapattinam",1.00),("Madurai",1.00),("Thoothukudi",28.00),("Coimbatore",7.00),("Tiruppur",37.26),("Erode",4.00),("Virudhunagar",199.40),("Dindigul",59.6),("Tirunelveli",9.36),("Tiruchirappalli",166.00),("Vellore",5.00),("Karur",151.49),("Krishnagiri",0.75),("Ramanathapuram",348.00),("Perambalur",10.00),("Cuddalore",10.00),("Tiruvannamalai",30.00),("Pudukkottai",20.00),("Kanyakumari",1.00)]
for dist,c in S:
    rec("solar-cluster-"+slug(dist)+"-2018","Private solar plants, %s district (2018 total)"%dist,"solar","operating",dist,c,None,"various","private","sun",None,None,
        "District total from Table 45 (sum 1100.41 MW; text says 2055 MW statewide end-2018, Table 50 says 2724.55 MW).",(117,118),cluster=True)
rec("kamuthi-solar","Kamuthi Solar Power Project","solar","operating","Ramanathapuram",648,None,"Adani Green Energy","private","sun",None,None,
    "PDF only mentions it in a figure caption: 'World's largest solar power plant 648 MW at Kamudhi'.",(63,),["Kamudhi","Kamuthi 648 MW"])

for r in recs:
    r["history"]=r["history"].strip()
json.dump(recs,open(OUT,'w'),indent=1,ensure_ascii=False)
from collections import Counter
print(len(recs),Counter(r['type'] for r in recs))
print(len(ids),len(set(r['id'] for r in recs)))
