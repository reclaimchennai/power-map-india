#!/usr/bin/env python3
"""Fuel supply chains -> web/data/feed.json (nodes + routes) for the map's supply layer.

Reads whatever the feedstock research produced in build/feedstock/ (see SCHEMA.md):
  ports.json (ports, terminals, sea lanes, TN plant -> port map), mines.json, gas.json,
  nuclear_fuel.json, links.json (plant -> ordered chain of nodes with modes)
and resolves every plant reference to the site's plant ids (web/data/plants.json) through the
dossier ids/aliases and name matching, so selecting a station can light up its own chain.

nodes:  {id, kind, name, lat, lon, note, serves[]}
routes: {id, mode (sea|rail|conveyor|pipeline|road|river|air), cargo, serves[], coords, approx}
"""
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
F = ROOT / "build" / "feedstock"
OUT = ROOT / "web" / "data" / "feed.json"


def norm(s):
    return re.sub(r"[^a-z0-9]+", " ", (s or "").lower()).strip()


def load(name):
    p = F / name
    if not p.exists():
        return None
    try:
        return json.load(open(p))
    except Exception as e:
        print("unreadable", name, e)
        return None


def plant_resolver():
    plants = json.load(open(ROOT / "web" / "data" / "plants.json"))["plants"]
    ids = {p["id"] for p in plants}
    alias = {}
    for p in plants:
        alias[norm(p["name"])] = p["id"]
        if p.get("npp_name"):
            alias[norm(p["npp_name"])] = p["id"]
    for d in (ROOT / "build" / "dossier").glob("*.json"):
        try:
            recs = json.load(open(d))
        except Exception:
            continue
        for r in recs if isinstance(recs, list) else recs.get("plants", []):
            target = r["id"] if r["id"] in ids else alias.get(norm(r.get("name")))
            for a in [r["id"], r.get("name")] + (r.get("aliases") or []):
                if a and target:
                    alias.setdefault(norm(a), target)
    # the research files' own short ids -> site ids, by hand where names don't overlap
    HAND = {"nctps-1": "north chennai tps stage 1", "nctps-2": "north chennai tps stage 2", "nctps-3": "north chennai tps stage 3",
            "mettur-1": "mettur tps", "mettur-2": "mettur tps ii", "ttps": "tuticorin tps", "vallur-ntecl": "vallur tpp",
            "ntpl": "ntpl tuticorin tpp", "ennore-sez": "ennore sctpp", "etps": "ennore tps"}
    DIRECT = {"neyveli-ts1": "neyveli-tps-1", "neyveli-ts2": "neyveli-tps-2", "nnttp": "neyveli-new-tps", "ppn-power": "ppn-pillaiperumalnallur",
              "udangudi": "udangudi-stpp-1", "mundra-umpp": "mundra-umtpp", "adani-mundra": "adani-power-limited-mundra-tpp-i-ii",
              "mundra-tpp": "adani-power-limited-mundra-tpp-i-ii"}
    for k, v in DIRECT.items():
        if v in ids:
            alias[norm(k)] = v
    for k, v in HAND.items():
        if norm(v) in alias:
            alias.setdefault(norm(k), alias[norm(v)])
    missing = set()

    GENERIC = set("gt gtps ccpp tps tpp stps power station plant generating co corp ltd limited gas turbine combined cycle "
                  "thermal project stage st the of and village formerly pvt private energen coastal umpp".split())
    words = {}
    for p in plants:
        for w in norm(p["name"] + " " + (p.get("npp_name") or "")).split():
            if w not in GENERIC and len(w) > 3:
                words.setdefault(w, set()).add(p["id"])

    def resolve(ref):
        if not ref:
            return None
        if ref in ids:
            return ref
        r = alias.get(norm(ref))
        if not r:
            # distinctive word of the reference (kuttalam-gt -> kuttalam) naming exactly one station
            for w in norm(ref.replace("-", " ")).split():
                if w in GENERIC or len(w) <= 3:
                    continue
                c = words.get(w, set())
                if len(c) == 1:
                    r = next(iter(c))
                    break
        if not r:
            missing.add(ref)
        return r
    return resolve, missing


def main():
    resolve, missing = plant_resolver()
    nodes, routes = {}, []

    def node(id_, kind, name, lat, lon, **kw):
        if lat is None or lon is None:
            return
        n = nodes.setdefault(id_, {"id": id_, "kind": kind, "name": name, "lat": round(lat, 5), "lon": round(lon, 5), "serves": []})
        for k, v in kw.items():
            if v not in (None, "", []):
                n[k] = v

    def serves(lst):
        return sorted({x for x in (resolve(r) for r in (lst or [])) if x})

    ports = load("ports.json") or {}
    for p in ports.get("ports", []):
        node(p["id"], "port", p["name"], p.get("lat"), p.get("lon"), note=(p.get("notes") or "")[:400], role=p.get("role"))
        for t in p.get("terminals") or []:
            node(t["id"], "terminal", t["name"], t.get("lat"), t.get("lon"), serves=serves(t.get("serves")),
                 capacity_mtpa=t.get("capacity_mtpa"))
    for p in ports.get("foreign_loading_ports", []):
        node(p["id"], "foreign_port", p["name"], p.get("lat"), p.get("lon"), note=(p.get("notes") or "")[:300])
    for l in ports.get("sea_lanes", []):
        g = l.get("geometry") or {}
        if g.get("type") == "LineString":
            routes.append({"id": l["id"], "mode": "sea", "kind": l.get("kind"), "cargo": l.get("cargo"),
                           "serves": serves(l.get("serves")), "coords": g["coordinates"], "approx": True})
    for name, kind in (("mines.json", "mine"), ("nuclear_fuel.json", "nuclear_fuel")):
        d = load(name) or {}
        for m in d.get("mines", d.get("nodes", d.get("facilities", []))) if isinstance(d, dict) else d:
            if isinstance(m, dict):
                node(m.get("id") or norm(m.get("name")).replace(" ", "-"), m.get("kind") or kind, m.get("name"), m.get("lat"), m.get("lon"),
                     note=(m.get("notes") or m.get("note") or "")[:300], production=m.get("production_mt") or m.get("production"))
    gas = load("gas.json") or {}
    pipe_serves = {}
    for ps in gas.get("plant_supply", []):
        pid = resolve(ps.get("plant_id")) or resolve(ps.get("name"))
        for pl in ps.get("pipeline_ids") or []:
            if pid:
                pipe_serves.setdefault(pl, set()).add(pid)
        for src in ps.get("sources_of_fuel") or []:
            sid = src if isinstance(src, str) else src.get("id")
            if sid and sid in nodes and pid:
                nodes[sid]["serves"].append(pid)
    for key, kind in (("fields", "gasfield"), ("processing_terminals", "gas_terminal"), ("lng_terminals", "lng")):
        for g in gas.get(key, []):
            node(g["id"], kind, g.get("name"), g.get("lat"), g.get("lon"),
                 note=(g.get("notes") or g.get("loc_note") or "")[:300], status=g.get("status"),
                 capacity=g.get("capacity_mtpa") or g.get("capacity"))
    for pl in gas.get("pipelines", []):
        g = pl.get("geometry") or {}
        parts = [g["coordinates"]] if g.get("type") == "LineString" else g.get("coordinates", []) if g.get("type") == "MultiLineString" else []
        for k, cs in enumerate(parts):
            if len(cs) >= 2:
                routes.append({"id": f"{pl['id']}-{k}", "mode": "pipeline", "cargo": pl.get("name"),
                               "serves": sorted(pipe_serves.get(pl["id"], set())), "coords": cs,
                               "approx": pl.get("geometry_precision") not in ("osm", "exact", "osm_ways"), "status": pl.get("status")})
    nf = load("nuclear_fuel.json") or {}
    for n in nf.get("nodes", []):
        node(n["id"], n.get("kind") or "nuclear_fuel", n.get("name"), n.get("lat"), n.get("lon"),
             note=(n.get("notes") or n.get("status") or "")[:300])
    for ch in nf.get("chains", []):
        pid = resolve(ch.get("plant_id"))
        for i, st in enumerate(ch.get("steps", [])):
            a, b = nodes.get(st.get("from")), nodes.get(st.get("to"))
            if not a or not b or st.get("mode") == "unknown":
                continue
            routes.append({"id": f"nf-{ch.get('plant_id')}-{i}", "mode": st.get("mode") or "road",
                           "cargo": f"{st.get('material') or ch.get('fuel_type')}", "serves": [pid] if pid else [],
                           "coords": [[a["lon"], a["lat"]], [b["lon"], b["lat"]]], "approx": True, "note": st.get("notes")})
            for x in (a, b):
                if pid and pid not in x["serves"]:
                    x["serves"].append(pid)
    links = load("links.json") or {}
    lnodes = links.get("nodes", {}) if isinstance(links, dict) else {}
    for nid, n in lnodes.items():
        node(nid, n.get("kind") or "node", n.get("name"), n.get("lat"), n.get("lon"), note=(n.get("loc_precision") or "")[:120])
    seen_leg = {}
    chains_out = {}
    for plant_ref, chains in (links.get("links", {}) if isinstance(links, dict) else {}).items():
        pid = resolve(plant_ref)
        for ch in chains:
            status = ch.get("status") or ("planned" if "planned" in json.dumps(ch.get("confidence", "")).lower() else None)
            cid = ch.get("id") or f"{plant_ref}-{len(chains_out.get(pid, []))}"
            chain_rec = {"id": cid, "fuel": ch.get("fuel"), "share": ch.get("share"), "share_basis": ch.get("share_basis"),
                         "status": status, "confidence": ch.get("confidence"), "legs": [], "source_name": (nodes.get(ch.get("from")) or {}).get("name")}
            if pid:
                chains_out.setdefault(pid, []).append(chain_rec)
            for k, leg in enumerate(ch.get("legs") or []):
                a, b = nodes.get(leg.get("from")) or lnodes.get(leg.get("from")) or {}, nodes.get(leg.get("to")) or lnodes.get(leg.get("to")) or {}
                chain_rec["legs"].append({"mode": leg.get("mode"), "from": a.get("name") or leg.get("from"), "to": b.get("name") or leg.get("to"),
                                          "from_kind": a.get("kind"), "to_kind": b.get("kind"), "km": leg.get("distance_km_approx"),
                                          "note": (leg.get("note") or "")[:160]})
                g = leg.get("geometry") or {}
                cs = g.get("coordinates") if g.get("type") == "LineString" else None
                if not cs:
                    a, b = nodes.get(leg.get("from")), nodes.get(leg.get("to"))
                    cs = [[a["lon"], a["lat"]], [b["lon"], b["lat"]]] if a and b else None
                if not cs or len(cs) < 2:
                    continue
                for x in (leg.get("from"), leg.get("to")):
                    if x in nodes and pid and pid not in nodes[x]["serves"]:
                        nodes[x]["serves"].append(pid)
                # legs shared by several plants (Paradip -> Kamarajar) are drawn once and serve them all
                key = (leg.get("mode"), leg.get("from"), leg.get("to"))
                if key in seen_leg and key[1] and key[2]:
                    r = seen_leg[key]
                    if pid and pid not in r["serves"]:
                        r["serves"].append(pid)
                    r.setdefault("chains", []).append(cid)
                    continue
                prec = (leg.get("geometry_precision") or "").lower()
                r = {"id": f"{ch.get('id') or plant_ref}-{k}", "mode": (leg.get("mode") or "rail").lower(),
                     "cargo": ch.get("fuel") or ch.get("cargo"), "serves": [pid] if pid else [], "coords": cs,
                     "approx": not prec.startswith("osm") and "exact" not in prec, "share": ch.get("share"),
                     "km": leg.get("distance_km_approx"), "note": (leg.get("note") or "")[:160],
                     "from_name": (nodes.get(leg.get("from")) or {}).get("name"), "to_name": (nodes.get(leg.get("to")) or {}).get("name")}
                r["chains"] = [cid]
                if status:
                    r["status"] = status
                seen_leg[key] = r
                routes.append(r)
    # --- derived links for every other coal plant ------------------------------------------------------
    # (a) CEA daily coal report remarks name the supplying company (MCL, SECL, NCL, ...): a link from that
    #     company's nearest coalfield to the plant. (b) CEA monthly coal statements give the import share:
    #     plants taking > 20% imported coal get a sea link from the nearest coal-import port (assumed).
    import math
    km = lambda a, b: 6371 * 2 * math.asin(math.sqrt(math.sin(math.radians(b[1] - a[1]) / 2) ** 2 + math.cos(math.radians(a[1])) * math.cos(math.radians(b[1])) * math.sin(math.radians(b[0] - a[0]) / 2) ** 2))
    plants_by = {p["id"]: p for p in json.load(open(ROOT / "web" / "data" / "plants.json"))["plants"]}
    fields = {}
    for m in (load("mines.json") or {}).get("mines", []):
        if m.get("kind") == "coalfield" and m.get("subsidiary_code") and m.get("lat") is not None:
            fields.setdefault(m["subsidiary_code"], []).append(m)
    have_chain = set(chains_out)
    remarks = json.load(open(F / "_parsed" / "cea_daily_coal_remarks_decoded.json")).get("plants", []) if (F / "_parsed" / "cea_daily_coal_remarks_decoded.json").exists() else []
    n_links = 0
    derived = []                      # poster-only: kept out of the live map's feed.json
    for r_ in remarks:
        pid = resolve(r_.get("cea_name"))
        p_ = plants_by.get(pid)
        if not p_ or pid in have_chain:
            continue
        for c in r_.get("coal_companies_named") or []:
            cands = fields.get(c["code"]) or []
            if not cands:
                continue
            f_ = min(cands, key=lambda m: km((m["lon"], m["lat"]), (p_["lon"], p_["lat"])))
            derived.append({"id": f"cea-{pid}-{c['code']}", "mode": "rail", "cargo": f"coal ({c['code']})", "serves": [pid],
                           "coords": [[f_["lon"], f_["lat"]], [p_["lon"], p_["lat"]]], "approx": True, "derived": "cea_remarks",
                           "from_name": f_["name"], "to_name": p_["name"], "km": round(km((f_["lon"], f_["lat"]), (p_["lon"], p_["lat"])))})
            n_links += 1
    rec_path = F / "_parsed" / "coal_receipts_cea_monthly.json"
    import_ports = [n for n in nodes.values() if n["kind"] == "port" and n["id"] in {"port-kamarajar", "port-voc", "port-karaikal", "port-paradip",
                    "port-visakhapatnam", "port-gangavaram", "port-dhamra", "port-krishnapatnam", "port-mundra", "port-haldia"}]
    n_imp = 0
    if rec_path.exists() and import_ports:
        for r_ in json.load(open(rec_path)).get("fy2025_26", []):
            share = (r_.get("share") or {}).get("import") or 0
            if not isinstance(r_.get("plant"), str) or share <= 0.2 or (r_.get("months") or 0) < 3 or (r_.get("total") or 0) <= 0:
                continue
            pid = resolve(r_["plant"])
            p_ = plants_by.get(pid)
            if not p_ or pid in have_chain:
                continue
            port = min(import_ports, key=lambda n: km((n["lon"], n["lat"]), (p_["lon"], p_["lat"])))
            derived.append({"id": f"imp-{pid}", "mode": "sea", "cargo": f"imported coal, {share:.0%} of receipts", "serves": [pid],
                           "coords": [[port["lon"], port["lat"]], [p_["lon"], p_["lat"]]], "approx": True, "derived": "cea_receipts",
                           "from_name": port["name"], "to_name": p_["name"], "share": share, "port_assumed": True})
            n_imp += 1
    json.dump({"routes": derived, "coalfields": {k: [{"id": m["id"], "name": m["name"], "lat": m["lat"], "lon": m["lon"]} for m in v] for k, v in fields.items()}},
              open(F / "derived_links.json", "w"), separators=(",", ":"))
    print(f"derived (poster only, build/feedstock/derived_links.json): {n_links} coal-company links, {n_imp} import links")

    # free-text modes -> the five drawn modes; nodes that duplicate stations or are only rail waypoints are not drawn
    def mode_of(m):
        m = (m or "").lower()
        if "pipeline" in m and "conveyor" not in m: return "pipeline"
        if m.startswith("air"): return "air"
        if "sea" in m or "ship" in m or "coastal" in m: return "sea"
        if "rail" in m or "mgr" in m: return "rail"
        if m in ("unknown", ""): return None
        return "conveyor"
    for r in routes:
        r["mode"] = mode_of(r["mode"])
    for lst in chains_out.values():
        for ch in lst:
            for lg in ch["legs"]:
                lg["mode"] = mode_of(lg["mode"]) or "unknown"
    routes[:] = [r for r in routes if r["mode"]]
    for k in [k for k, n in nodes.items() if n["kind"] in ("plant", "rail_station", "reactor")]:
        del nodes[k]
    # plants served by a node -> node.serves; routes ending at a served terminal inherit
    for r in routes:
        r["coords"] = [[round(c[0], 4), round(c[1], 4)] for c in r["coords"]]
    out = {"nodes": list(nodes.values()), "routes": routes, "chains": chains_out,
           "note": "Sea lanes and many rail legs are approximate illustrations of the documented chain, not vessel or rake tracks."}
    json.dump(out, open(OUT, "w"), separators=(",", ":"))
    print(f"feed: {len(nodes)} nodes, {len(routes)} routes -> {OUT} ({OUT.stat().st_size // 1024} KB); unresolved plant refs: {sorted(missing)[:30]}")


if __name__ == "__main__":
    main()
