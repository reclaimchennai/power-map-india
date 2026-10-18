"""Parse TN official EHV substation lists (TANTRANSCO 765/400/230 kV pages + SLDC Sslist)
and summarise the NPP transmission dashboard JSON.

Officer names and phone numbers in the SLDC page are deliberately dropped.
Outputs: build/grid/tn_ehv_substations_official.json, build/grid/npp_transmission_stats.json
"""
import datetime as dt
import json
import os
import re

from bs4 import BeautifulSoup

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAWG = os.path.join(ROOT, "raw", "grid")
OUT = os.path.join(ROOT, "build", "grid")
os.makedirs(OUT, exist_ok=True)

TT_URL = "https://www.tantransco.org/en/tantransco/infrastructure/list-substations/{}/"
SLDC_URL = "https://tnebsldc.org/Sslist.aspx"
SLDC_FILE = os.path.join(ROOT, "raw", "pages", "sldc_https___tnebsldc_org_Sslist_aspx.html")


def clean(s):
    return " ".join((s or "").replace("\xa0", " ").replace("Â", " ").split())


def norm_key(name):
    """Normalised key for joining lists: upper, drop kV/SS words and punctuation."""
    s = name.upper()
    s = re.sub(r"\(.*?\)", " ", s)
    s = re.sub(r"\b\d+(/\d+)*(-\d+)*\s*K\s*V\b", " ", s)
    s = re.sub(r"\b(SS|S\.S|SUB-?STATION|SUBSTATION|GIS|AUTO|SWITCHING|STATION|KV|CMRL|UG|HYBRID|WF)\b", " ", s)
    s = re.sub(r"[^A-Z ]", " ", s)
    s = s.replace("SRIPERUMPUDUR", "SRIPERUMBUDUR").replace("THIRUVALAM", "TIRUVALAM")
    return " ".join(s.split())


def parse_tantransco():
    out = []
    for v in (765, 400, 230):
        html = open(os.path.join(RAWG, f"tantransco_substations_{v}.html"), encoding="utf-8", errors="replace").read()
        t = BeautifulSoup(html, "lxml").find("table")
        for r in t.find_all("tr")[1:]:
            c = [clean(x.get_text(" ")) for x in r.find_all(["td", "th"])]
            if len(c) < 3 or not c[0].strip().isdigit():
                continue
            out.append({
                "name": c[1], "key": norm_key(c[1]), "voltage_class_kv": v, "voltage_ratio": c[2],
                "commissioned": c[3] if len(c) > 3 else None, "sources": [TT_URL.format(v)],
            })
    return out


HONORIFIC = re.compile(r"^(thiru|tmy|tmt|tmty|th\.|selvi|ms\.|mr\.|smt)", re.I)


def parse_sldc():
    html = open(SLDC_FILE, encoding="cp1252", errors="replace").read()
    t = BeautifulSoup(html, "lxml").find("table")
    out, circle = [], None
    for r in t.find_all("tr"):
        c = [clean(x.get_text(" ")) for x in r.find_all(["td", "th"])]
        c = [x for x in c if x]
        if not c:
            continue
        if re.fullmatch(r"[IVX]+", c[0]) and len(c) > 1:
            circle = c[1]
            continue
        if not c[0].isdigit() or len(c) < 2:
            continue
        name = c[1]
        m = re.search(r"(\d{2,3}(?:\s*/\s*\d{2,3})*(?:\s*-\s*\d{2,3})*)\s*k\s*v", name, re.I)
        ratio = m.group(1).replace(" ", "") if m else None
        base = clean(re.sub(r"\d{2,3}(?:\s*/\s*\d{2,3})*(?:\s*-\s*\d{2,3})*\s*k\s*v.*$", "", name, flags=re.I))
        edc = c[2] if len(c) > 2 else None
        if edc and (HONORIFIC.match(edc) or re.search(r"\d{6,}", edc) or "." in edc):
            edc = None  # column holds an officer name / phone on some circles -> drop
        vmax = max(int(x) for x in re.findall(r"\d{2,3}", ratio)) if ratio else None
        out.append({"name": name, "base_name": base, "key": norm_key(base), "voltage_ratio": ratio,
                    "voltage_class_kv": vmax, "operation_circle": circle, "edc": edc,
                    "switching_station": "switching" in name.lower(), "sources": [SLDC_URL]})
    return out


def phon(s, vowels=False):
    """Crude spelling-insensitive key for Tamil place names (Latin transliteration variants).
    vowels=False returns the consonant skeleton (first letter kept)."""
    s = re.sub(r"[^A-Z]", "", s.upper())
    for a, b in (("KOVIL", "KOIL"), ("KURCHY", "KURICHI"), ("KURCHI", "KURICHI"), ("CHY", "CHI"), ("TH", "T"),
                 ("DH", "D"), ("BH", "B"), ("PH", "P"), ("KH", "K"), ("SH", "S"), ("CH", "C"), ("OO", "U"), ("EE", "I"),
                 ("AI", "AY"), ("W", "V"), ("Y", "I")):
        s = s.replace(a, b)
    s = re.sub(r"(.)\1+", r"\1", s)  # collapse doubled letters
    if not vowels:
        s = re.sub(r"(?<=.)[AEIOU]", "", s)  # drop non-initial vowels
    return s


def aliases(name):
    """Set of normalised name variants (main name + parenthetical / 'AT x' aliases), vowels kept."""
    base = re.sub(r"\(.*?\)", " ", name)
    out = {phon(norm_key(base), vowels=True)}
    for par in re.findall(r"\((.*?)\)", name):
        par = re.sub(r"^(AT|NEAR)\s+", "", par.strip(), flags=re.I)
        out.add(phon(norm_key(par), vowels=True))
    for at in re.findall(r"\bAT\s+(.+)$", base, re.I):
        out.add(phon(norm_key(at), vowels=True))
    return {a for a in out if len(a) >= 3}


def _skel(x):
    return x[:1] + re.sub(r"[AEIOU]", "", x[1:])


def pair_sim(x, y):
    """0..1 similarity of two vowel-kept keys: mean of full-string and consonant-skeleton ratios;
    containment of a >=5-letter key in the other counts as 0.9."""
    import difflib
    if min(len(x), len(y)) >= 5 and (x in y or y in x):
        return max(0.9, difflib.SequenceMatcher(None, x, y).ratio())
    a = difflib.SequenceMatcher(None, x, y).ratio()
    b = difflib.SequenceMatcher(None, _skel(x), _skel(y)).ratio()
    return (a + b) / 2


def similar(a, b):
    return max((pair_sim(x, y) for x in a for y in b), default=0)


# SLDC spelling -> TANTRANSCO spelling where automatic matching fails
MANUAL = {"SP KOIL": "SINGAPERUMALKOIL", "OTTIYAMBAKKAM": "SHOLINGANALLUR", "KILPAUK WATER WORKS": "KILPAUK",
          "OMEGA": "OMEGA INDL ESTATE", "POIYUR": "POYYUR", "MUTHIAHPURAM": "TUTICORIN"}


def merge(tt, sl):
    recs = {}
    for r in tt:
        k = (r["key"], r["voltage_class_kv"])
        recs[k] = {"name": r["name"], "key": r["key"], "voltage_class_kv": r["voltage_class_kv"],
                   "voltage_ratio": r["voltage_ratio"], "commissioned": r["commissioned"],
                   "operation_circle": None, "edc": None, "in_tantransco_list": True, "in_sldc_list": False,
                   "sources": list(r["sources"])}
    for r in sl:
        k = (MANUAL.get(r["key"], r["key"]), r["voltage_class_kv"])
        hit = recs.get(k)
        if hit is None:  # fuzzy: best spelling-insensitive match at the same voltage class
            al = aliases(r["base_name"])
            best = max(((similar(al, aliases(rr["name"])), rr) for kk, rr in recs.items()
                        if kk[1] == r["voltage_class_kv"] and rr.get("in_tantransco_list") and not rr["in_sldc_list"]),
                       key=lambda x: x[0], default=(0, None))
            if best[0] >= 0.82:
                hit = best[1]
        if hit is None:
            hit = recs[k] = {"name": r["base_name"], "key": r["key"], "voltage_class_kv": r["voltage_class_kv"],
                             "voltage_ratio": r["voltage_ratio"], "commissioned": None,
                             "in_tantransco_list": False, "sources": []}
        hit.update({"operation_circle": r["operation_circle"], "edc": r["edc"], "in_sldc_list": True,
                    "sldc_name": r["name"], "switching_station": r["switching_station"]})
        if SLDC_URL not in hit["sources"]:
            hit["sources"].append(SLDC_URL)
    return sorted(recs.values(), key=lambda x: (-(x["voltage_class_kv"] or 0), x["name"]))


def npp_summary():
    d = json.load(open(os.path.join(RAWG, "npp_trans.json")))
    m, h = d["mapTLine"], d["headerMap"]
    fy = m["fyList"]
    def ms(x):
        return dt.datetime.utcfromtimestamp(x / 1000 + 19800).strftime("%Y-%m-%d") if x else None
    cur = fy[-1] if fy else {}
    prev = fy[0] if fy else {}
    by_v = [{"voltage": r["voltage_level"],
             "ckm_added_current_fy_to_date": r["transmission_line_ckm_cumm"],
             "mva_added_current_fy_to_date": r["transform_capacity_mva_cumm"],
             "ckm_added_same_period_prev_fy": r["transmission_line_ckm_cumm_p"],
             "mva_added_same_period_prev_fy": r["transform_capacity_mva_cumm_p"]} for r in m["transLineList"]]
    years = [{"fy": r["fin_year_id_print"], "ckm_added": r["transmission_line_growth"],
              "total_ckm_220kv_plus": r["transmission_line_intra_state_ckm_cum"],
              "total_transformation_mva": r["transform_capacity_mva_cumm"],
              "mva_added": r["transform_capacity_growth"]} for r in m["yTransList"]]
    return {
        "scope": "All India, 220 kV and above (NPP dashboard is national only; the ID parameter is ignored — "
                 "ID=TN/33/SR return identical payloads)",
        "fetched": dt.date.today().isoformat(),
        "current_fy_period": f"{cur.get('start_month_year')}..{cur.get('end_month_year')}",
        "previous_fy_period": f"{prev.get('start_month_year')}..{prev.get('end_month_year')}",
        "additions_by_voltage": by_v,
        "annual": years,
        "header": {"total_ckm_220kv_plus": h["TR_OBJ"]["transmission_line_intra_state_ckm_cum"],
                   "total_transformation_mva": h["TR_OBJ"]["transform_capacity_mva_cumm"],
                   "fy": h["TR_OBJ"]["fin_year_id_print"],
                   "installed_capacity_mw": round(h["CP_OBJ"]["installed_capacity"], 1),
                   "capacity_reporting_date": ms(h["CP_OBJ"]["reporting_date"])},
        "notes": "Field names in NPP are misleading: 'transmission_line_intra_state_ckm_cum' is the all-India "
                 "cumulative ckm (220 kV+); 'transmission_line_inter_state_ckm' equals the annual addition. "
                 "transLineList values are FY-to-date additions by voltage (current vs same period last FY).",
        "sources": ["https://npp.gov.in/dashBoard/getTransmissionLine?ID=IND", "file:raw/grid/npp_trans.json"],
    }


if __name__ == "__main__":
    tt, sl = parse_tantransco(), parse_sldc()
    merged = merge(tt, sl)
    net_pdf = "https://www.tantransco.org/static/tantransco/assets/files/tantranscopdf/networkason31032025.pdf"
    doc = {"tantransco_network_as_on_2025_03_31": {
               "substations": {"765": 2, "400": 19, "230": 116, "110": 962, "66": 3, "total": 1102},
               "line_ckm": {"765": 733, "400": 5215, "230": 11985, "110": 21281, "66": 83, "total": 39297},
               "sources": [net_pdf, "file:raw/grid/tantransco_network_as_on_31032025.pdf"]},
           "counts": {"tantransco": len(tt), "sldc": len(sl), "merged": len(merged)},
           "substations": merged}
    json.dump(doc, open(os.path.join(OUT, "tn_ehv_substations_official.json"), "w"), indent=1)
    json.dump(npp_summary(), open(os.path.join(OUT, "npp_transmission_stats.json"), "w"), indent=1)
    print(doc["counts"])
