"""TANTRANSCO SLDC "Grid Details (Instantaneous)" — the live-ish heartbeat of Tamil Nadu's grid.

https://tnebsldc.org/reports1/peakdet.pdf is re-issued by the SLDC shift engineer several
times a day (minimum load ~04:00, morning peak ~07:30-12:00, evening lighting peak ~18:30),
always at the same URL. We poll it, archive every distinct version (keyed by the PDF's own
modification time) under raw/sldc/archive/, and parse all rows into `sldc_rows`.

Columns in the PDF: Total Capacity (MW) | Lighting Peak (MW, previous evening) |
Minimum Load (MW, early today) | Morning Peak (MW, today) | Consumption (MU, previous day).
Capacities marked * are "not included in total installed capacity" (RE, captive, REMC).

Column positions drift row to row (it is an Excel print), so values are assigned per row by
role, not by fixed x: capacity sits left of x=320, MU is the 3-decimal figure right of x=470,
and the MW figures between are Lighting/Minimum/Morning in order.
"""
import hashlib
import os
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

import pdfplumber
import requests
import urllib3

from store import connect, log

urllib3.disable_warnings()
URL = "https://tnebsldc.org/reports1/peakdet.pdf"
ROOT = Path(__file__).resolve().parent.parent
ARCHIVE = ROOT / "raw" / "sldc" / "archive"
UA = {"User-Agent": "Mozilla/5.0 (reclaimchennai power map; +https://power.reclaimchennai.city)"}

SCHEMA = """
CREATE TABLE IF NOT EXISTS sldc_versions (
    pdf_modified TEXT PRIMARY KEY,   -- ISO UTC from the PDF / Last-Modified
    report_date TEXT, fetched TEXT, sha1 TEXT, file TEXT,
    lighting_date TEXT, lighting_time TEXT, lighting_hz REAL,
    min_date TEXT, min_time TEXT, min_hz REAL,
    morning_date TEXT, morning_time TEXT, morning_hz REAL,
    mu_date TEXT, extra TEXT
);
CREATE TABLE IF NOT EXISTS sldc_rows (
    pdf_modified TEXT NOT NULL, key TEXT NOT NULL, label TEXT,
    capacity_mw REAL, capacity_excluded INTEGER DEFAULT 0,
    lighting_mw REAL, min_mw REAL, morning_mw REAL, mu REAL,
    PRIMARY KEY (pdf_modified, key)
);
"""

# (key, label regex matched against the row's joined label text). Order matters: first match wins.
ITEMS = [
    ("hydro", r"^a\)\s*Hydro"), ("thermal", r"^b\)\s*Thermal"), ("gas", r"^c\)\s*Gas"),
    ("ipp_ppn", r"PPN"), ("ipp_taqa", r"TAQA"), ("ipp_sepc", r"SEPC"),
    ("cpp", r"Captive Power Plant"), ("cpp_purchase", r"CPP \(Purchase\)"),
    ("cpp_wheeling", r"CPP \(Wheeling\)"),
    ("nces", r"Non-Conventional"), ("cogen", r"Co-Generation"), ("biomass", r"Bio\s*mass"),
    ("wind", r"^\(iii\)\s*Wind|^Wind"), ("solar", r"^\(iv\)\s*Solar|^Solar"),
    ("cgs", r"CGS \(capacity\)"),
    ("cgs_ramagundam_12", r"Ramagundam Stage 1&2"), ("cgs_ramagundam_3", r"Ramagundam Stage 3"),
    ("cgs_talcher_2", r"Talcher"), ("cgs_simhadri_2", r"Simhadri"), ("cgs_kudgi_1", r"Kudgi"),
    ("cgs_vallur", r"NTECL Vallur"), ("cgs_er_power", r"ER Power"),
    ("cgs_neyveli_ts2", r"Neyveli TS2 Stage"), ("cgs_neyveli_ts1_exp", r"Neyveli TS1 Exp"),
    ("cgs_neyveli_ts2_exp", r"Neyveli TS2 Exp"), ("cgs_nnttp", r"New Neyveli"),
    ("cgs_ntpl", r"NTPL"), ("cgs_maps", r"MAPS"), ("cgs_kaiga", r"Kaiga"),
    ("cgs_kudankulam", r"Kudankulam"), ("cgs_ntpc_ts", r"NTPC stations"),
    ("ltoa", r"^LTOA"), ("mtoa", r"^MTOA"), ("mtoa_tnpdcl", r"^TNPDCL$"), ("mtoa_others", r"^Others$"),
    ("stoa", r"STOA"), ("exchange", r"Exchange"), ("exchange_tnpdcl", r"^\(i\)\s*TNPDCL"),
    ("exchange_others", r"^\(ii\)\s*Others"), ("remc", r"REMC"), ("urs", r"URS Power"),
    ("dsm", r"DSM"), ("total", r"^Total"), ("load_shedding", r"Load Shedding"),
    ("ht_relief", r"HT Relief"),
]
NUM = re.compile(r"^\*?-?[\d,]+(?:\.\d+)?$")


def _num(t):
    try:
        return float(t.replace(",", "").replace("*", ""))
    except ValueError:
        return None


def _lines(words, tol=2.6):
    rows = []
    for w in sorted(words, key=lambda w: (w["top"], w["x0"])):
        if rows and abs(rows[-1]["top"] - w["top"]) <= tol:
            rows[-1]["words"].append(w)
        else:
            rows.append({"top": w["top"], "words": [w]})
    for r in rows:
        r["words"].sort(key=lambda w: w["x0"])
        r["label"] = " ".join(w["text"] for w in r["words"] if w["x0"] < 235)
        r["nums"] = [w for w in r["words"] if NUM.match(w["text"]) and w["x0"] >= 235]
    return rows


def _assign(nums):
    """nums: words right of the label area -> dict of columns."""
    out = {"capacity_mw": None, "capacity_excluded": 0, "lighting_mw": None, "min_mw": None,
           "morning_mw": None, "mu": None}
    mids = []
    for w in nums:
        t, v = w["text"], _num(w["text"])
        if v is None:
            continue
        if w["x0"] < 320 and out["capacity_mw"] is None and not (w["x0"] > 300 and "." not in t and len(nums) >= 4 and False):
            out["capacity_mw"] = v
            out["capacity_excluded"] = int(t.startswith("*"))
        elif w["x0"] >= 470 and re.search(r"\.\d{3}$", t):
            out["mu"] = v
        else:
            mids.append(w)
    cols = ["lighting_mw", "min_mw", "morning_mw"]
    if len(mids) == 3:
        for c, w in zip(cols, mids):
            out[c] = _num(w["text"])
    else:
        centres = {"lighting_mw": 362, "min_mw": 410, "morning_mw": 457}
        for w in mids:
            c = min(centres, key=lambda k: abs(centres[k] - (w["x0"] + w["x1"]) / 2))
            out[c] = _num(w["text"])
    return out


def parse(path):
    with pdfplumber.open(path) as pdf:
        page = pdf.pages[0]
        words = page.extract_words()
        meta_pdf = pdf.metadata or {}
    lines = _lines(words)
    text = "\n".join(" ".join(w["text"] for w in l["words"]) for l in lines)
    meta = {}
    m = re.search(r"Date\s*:\s*(\d{1,2}-\w{3}-\d{2})", text)
    meta["report_date"] = datetime.strptime(m.group(1), "%d-%b-%y").date().isoformat() if m else None
    for l in lines:
        toks = [w["text"] for w in l["words"]]
        if toks[:1] == ["Date"] and len(toks) >= 5:
            meta["lighting_date"], meta["min_date"], meta["morning_date"], meta["mu_date"] = toks[1:5]
        elif toks[:1] == ["Time"]:
            vals = [t for t in toks[1:] if t != "Hrs."]
            for k, v in zip(["lighting_time", "min_time", "morning_time"], vals):
                meta[k] = v.replace("Hrs", "").replace(".", ":")
        elif toks[:1] == ["Frequency"]:
            vals = [_num(t.replace("Hz", "")) for t in toks[1:] if t != "HZ."]
            for k, v in zip(["lighting_hz", "min_hz", "morning_hz"], vals):
                meta[k] = v
    for d in ("lighting_date", "min_date", "morning_date", "mu_date"):
        if meta.get(d):
            try:
                meta[d] = datetime.strptime(meta[d], "%d-%m-%Y").date().isoformat()
            except ValueError:
                pass

    # label lines anchor items; numeric-only lines attach to the nearest label within 8 pt below/above
    bare = re.compile(r"^\(?[ivx]+\)?$|^\d+$")
    for l in lines:                      # "(ii)" alone is numbering, not a label
        if bare.match(l["label"].strip()):
            l["label"] = ""
    labelled = [l for l in lines if l["label"].strip()]
    rows = {}
    used = set()
    for key, rx in ITEMS:
        for i, l in enumerate(labelled):
            if i in used:
                continue
            lab = re.sub(r"^\(?[ivx]+\)\s*|^\d+\s+|^[a-c]\)\s*", "", l["label"]).strip()
            if re.search(rx, l["label"]) or re.search(rx, lab):
                used.add(i)
                rows[key] = {"label": lab, "top": l["top"], "nums": list(l["nums"])}
                break
    # orphan numeric lines -> nearest item within 9 pt; farther ones are group subtotals
    anchors = sorted(rows.items(), key=lambda kv: kv[1]["top"])
    for l in lines:
        if l["label"].strip() or not l["nums"]:
            continue
        near = [kv for kv in anchors if abs(kv[1]["top"] - l["top"]) <= 9]
        near.sort(key=lambda kv: (bool(kv[1]["nums"]), abs(kv[1]["top"] - l["top"])))
        has_cap = any(w["x0"] < 320 for w in l["nums"])
        ok = [kv for kv in near if not (has_cap and any(w["x0"] < 320 for w in kv[1]["nums"]))]
        if ok:
            ok[0][1]["nums"].extend(l["nums"])
        elif near and near[0][0].startswith("cgs_"):
            rows["cgs"]["nums"].extend(l["nums"])
        else:
            prev = [kv for kv in anchors if kv[1]["top"] < l["top"]]
            k = f"subtotal_after_{prev[-1][0]}" if prev else "subtotal"
            rows[k] = {"label": "subtotal", "top": l["top"], "nums": l["nums"]}
    out = {}
    for k, r in rows.items():
        v = _assign(sorted(r["nums"], key=lambda w: w["x0"]))
        v["label"] = r["label"]
        out[k] = v
    # all-time highs and yesterday's solar max
    m = re.search(r"Consumption\s+([\d.]+)\s+MU\s+on\s+([\d-]+)", text)
    if m:
        meta["alltime_mu"], meta["alltime_mu_date"] = float(m.group(1)), m.group(2)
    m = re.search(r"Demand\s+([\d.]+)\s+MW\s+on\s+([\d-]+)\s+([\d:]+)", text)
    if m:
        meta["alltime_mw"], meta["alltime_mw_date"], meta["alltime_mw_time"] = float(m.group(1)), m.group(2), m.group(3)
    m = re.search(r"solar generation\(max\):\s*([\d.]+)", text)
    if m:
        meta["solar_max_yesterday_mw"] = float(m.group(1))
    meta["pdf_created"] = meta_pdf.get("CreationDate")
    return meta, out


def _pdf_time(meta_pdf_date, last_modified):
    # "D:20260924063814Z" or Last-Modified header
    m = re.match(r"D:(\d{14})(?:([+-])(\d{2})'?(\d{2})'?|Z)?", meta_pdf_date or "")
    if m:
        from datetime import timedelta
        t = datetime.strptime(m.group(1), "%Y%m%d%H%M%S")
        if m.group(2):
            off = timedelta(hours=int(m.group(3)), minutes=int(m.group(4)))
            t = t - off if m.group(2) == "+" else t + off
        return t.replace(tzinfo=timezone.utc).isoformat()
    if last_modified:
        from email.utils import parsedate_to_datetime
        return parsedate_to_datetime(last_modified).astimezone(timezone.utc).isoformat()
    return datetime.now(timezone.utc).isoformat()


def save(meta, rows, pdf_modified, sha1, file):
    con = connect()
    con.executescript(SCHEMA)
    with con:
        extra = {k: v for k, v in meta.items() if k.startswith("alltime") or k.startswith("solar")}
        con.execute("""INSERT OR REPLACE INTO sldc_versions VALUES
            (?,?,?,?,?, ?,?,?, ?,?,?, ?,?,?, ?,?)""",
                    (pdf_modified, meta.get("report_date"), datetime.now(timezone.utc).isoformat(), sha1, file,
                     meta.get("lighting_date"), meta.get("lighting_time"), meta.get("lighting_hz"),
                     meta.get("min_date"), meta.get("min_time"), meta.get("min_hz"),
                     meta.get("morning_date"), meta.get("morning_time"), meta.get("morning_hz"),
                     meta.get("mu_date"), json.dumps(extra)))
        for k, v in rows.items():
            con.execute("INSERT OR REPLACE INTO sldc_rows VALUES (?,?,?,?,?,?,?,?,?)",
                        (pdf_modified, k, v["label"], v["capacity_mw"], v["capacity_excluded"],
                         v["lighting_mw"], v["min_mw"], v["morning_mw"], v["mu"]))
    con.close()


def _proxy_uri():
    """Optional socks5h:// URI from POWERMAP_SOCKS5_URI (unset = no proxy fallback)."""
    return os.environ.get("POWERMAP_SOCKS5_URI") or None


def _get():
    """tnebsldc.org drops this server's datacenter IP (blocked since ~2026-09-28), so on a
    connect failure retry through the optional SOCKS5 proxy in POWERMAP_SOCKS5_URI."""
    try:
        r = requests.get(URL, headers=UA, timeout=15, verify=False)
        r.raise_for_status()
        return r
    except requests.exceptions.ConnectionError as e:
        uri = _proxy_uri()
        if not uri:
            raise
        log("sldc_peakdet", "info", f"direct failed ({type(e).__name__}); using residential proxy")
        r = requests.get(URL, headers=UA, timeout=60, verify=False, proxies={"https": uri, "http": uri})
        r.raise_for_status()
        return r


def fetch_and_store(path=None):
    ARCHIVE.mkdir(parents=True, exist_ok=True)
    last_mod = None
    if path is None:
        r = _get()
        if not r.content.startswith(b"%PDF"):
            raise RuntimeError("peakdet: not a PDF")
        last_mod = r.headers.get("Last-Modified")
        tmp = ARCHIVE / "_latest.pdf"
        tmp.write_bytes(r.content)
        path = tmp
    data = Path(path).read_bytes()
    sha1 = hashlib.sha1(data).hexdigest()
    with pdfplumber.open(path) as pdf:
        pdf_meta = pdf.metadata or {}
    pdf_modified = _pdf_time(pdf_meta.get("ModDate") or pdf_meta.get("CreationDate"), last_mod)
    con = connect()
    con.executescript(SCHEMA)
    seen = con.execute("SELECT 1 FROM sldc_versions WHERE pdf_modified=? AND sha1=?", (pdf_modified, sha1)).fetchone()
    con.close()
    if seen:
        return pdf_modified, False
    stamp = pdf_modified[:16].replace(":", "").replace("T", "_")
    dest = ARCHIVE / f"peakdet_{stamp}.pdf"
    dest.write_bytes(data)
    meta, rows = parse(dest)
    save(meta, rows, pdf_modified, sha1, str(dest.relative_to(ROOT)))
    log("sldc_peakdet", "ok", f"{pdf_modified} {len(rows)} rows")
    return pdf_modified, True


def main():
    if len(sys.argv) > 1 and sys.argv[1] == "--parse":
        meta, rows = parse(sys.argv[2])
        print(json.dumps(meta, indent=1))
        for k, v in rows.items():
            print(f"{k:22s} {v}")
        return
    files = sys.argv[1:] or [None]
    for f in files:
        print(fetch_and_store(f))


if __name__ == "__main__":
    main()
