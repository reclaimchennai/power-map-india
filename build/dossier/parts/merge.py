import json, re, sys, copy
SP='/tmp/powermap_scratch/'
parts=[('tnpgcl',json.load(open(SP+'part_tnpgcl.json'))),('tngecl',json.load(open(SP+'part_tngecl.json'))),
       ('other',json.load(open(SP+'part_other.json'))),('pdf',json.load(open(SP+'part_pdf.json')))]
MAP=json.load(open(SP+'idmap.json'))   # {"part:id": "canonical id" or null to drop}
def norm(s): return re.sub(r'[^a-z0-9]','',(s or '').lower())
def empty(v): return v is None or v=='' or v==[] or v=={}
def merge(a,b):
    """fill a from b (a has priority)"""
    for k,v in b.items():
        if k in ('aliases','sources','evacuation'):
            for x in v or []:
                if x not in a.setdefault(k,[]) : a[k].append(x)
        elif k in ('fuel','water','structure','emissions','links') and isinstance(v,dict):
            a.setdefault(k,{}) 
            if a[k] is None: a[k]={}
            for kk,vv in v.items():
                if empty(a[k].get(kk)) and not empty(vv): a[k][kk]=vv
                elif kk=='notes' and vv and vv not in (a[k].get(kk) or ''): a[k][kk]=(a[k].get(kk) or '')+(' | ' if a[k].get(kk) else '')+vv
        elif k=='history':
            if v and not a.get('history'): a['history']=v
        elif k=='units':
            if empty(a.get('units')) and v: a['units']=v
        elif empty(a.get(k)) and not empty(v): a[k]=v
    return a
out={}; order=[]
for pname,recs in parts:
    for r in recs:
        key=f"{pname}:{r['id']}"
        cid=MAP.get(key, r['id'])
        if cid is None: continue
        if cid in out: merge(out[cid],r)
        else:
            rr=copy.deepcopy(r); rr['id']=cid; out[cid]=rr; order.append(cid)
res=[out[i] for i in order]
json.dump(res,open(SP+'merged.json','w'),indent=1)
print(len(res))
