import json
SP='/tmp/powermap_scratch/'
d=json.load(open(SP+'merged.json'))
R={r['id']:r for r in d}
for r in d:
    if r['lat'] is None: r['loc_quality']=None; r['lon']=None
def al(i,*a):
    for x in a:
        if x not in R[i]['aliases']: R[i]['aliases'].append(x)
al('mettur-tps-2','METTUR TPS - II')
al('nctps-1','NORTH CHENNAI TPS'); al('nctps-2','NORTH CHENNAI TPS')
for i in ('nctps-1','nctps-2'):
    R[i]['emissions']['notes']=(R[i]['emissions'].get('notes') or '')+(' | ' if R[i]['emissions'].get('notes') else '')+"DGR row 'NORTH CHENNAI TPS' (1830 MW, Aug-Nov 2025) is Stage I + Stage II combined; split by capacity when joining."
u=R['udangudi-stpp-2-3']; u['lat']=u['lon']=None; u['loc_quality']=None
for i in ('cheyyur-umpp','kadaladi-tpp','itpcl-cuddalore-ph2'):
    if i in R:
        R[i]['lat']=R[i]['lon']=None; R[i]['loc_quality']=None
R['cheyyur-umpp']['history']=(R['cheyyur-umpp'].get('history') or '')+" Not in TNPGCL Data Card 2025-26 project list; no current activity found (treat as shelved)."
R['kadaladi-tpp']['history']=(R['kadaladi-tpp'].get('history') or '')+" Not in TNPGCL Data Card 2025-26 project list; no current activity found (treat as shelved)."
R['itpcl-cuddalore-ph2']['history']=(R['itpcl-cuddalore-ph2'].get('history') or '')+" IL&FS group insolvency since 2018; no current activity found (treat as shelved)."
# sort: by type then capacity desc
order={'nuclear':0,'coal':1,'lignite':2,'gas':3,'diesel':4,'hydro':5,'pumped_storage':6,'wind':7,'solar':8,'battery':9,'biomass':10,'cogen':11,'waste':12}
d.sort(key=lambda r:(order[r['type']],-(r['capacity_mw'] or 0),r['id']))
json.dump(d,open('./build/dossier/tn_plants.json','w'),indent=1,ensure_ascii=False)
print(len(d))
