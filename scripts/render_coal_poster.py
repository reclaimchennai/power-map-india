#!/usr/bin/env python3
"""The coal poster: India's coal supply chain and the stock at its power stations, in the house style
of the station posters (scripts/render_poster.py, whose layout engine it reuses: one collision index,
text that refuses to overlap, markers that stay on land, cards that fail the render if they overflow).

    .venv/bin/python scripts/render_coal_poster.py          # web/posters/coal_india_en.png (+ _preview.jpg)
    .venv/bin/python scripts/render_coal_poster.py --dpi 150

Reads web/data/coal/coal.json (scripts/export_coal.py). 20 x 16.5 in:
  left   the supply chain map: coalfields and mines, ports, rail / sea / conveyor routes and the CEA-named
         coal links, every station a voxel pillar (height = capacity) coloured by the coal it has left;
         the biggest stations in trouble labelled with their days of coal
  right  the long record of stock at power stations with the lowest points marked, arrivals against burn,
         four headline figures, and the stations with the fewest days left
"""
import argparse
import json
import math
from datetime import date, datetime, timedelta
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
from matplotlib.collections import LineCollection, PolyCollection, PatchCollection  # noqa: E402
from matplotlib.patches import Rectangle  # noqa: E402

import render_poster as R  # noqa: E402
from render_poster import (Sheet, font, fmt, pillar, levels, countries, geoms, curve, smooth, arrow_at, label_names,
                           ID, PAPER, LAND, INDIA, WATER, STATE, BORDER, INK, MUTED, ACCENT, CARD, EDGE, SEA, RAIL, CONV, SEA_INK)  # noqa: E402

ROOT = R.ROOT
OUT = R.OUT
CRIT = "#c42b2b"; LOW = "#d98a00"; OK = "#2e8540"; IDLE = "#9aa0ab"; STOCK = "#1f5fae"; STOCK_LY = "#9aa3b5"; RCPT = "#6b4fc4"; BURN = "#e34948"
MINE = "#8a5200"


def status(p):
    if not p.get("req") or p.get("pct") is None:
        return "idle"
    return "crit" if p.get("crit") else "low" if p["pct"] < 50 else "ok"


COL = {"crit": CRIT, "low": LOW, "ok": OK, "idle": IDLE}


def draw(dpi):
    D = json.load(open(ROOT / "web" / "data" / "coal" / "coal.json"))
    plants = {p["id"]: p for p in json.load(open(ROOT / "web" / "data" / "plants.json"))["plants"]}
    base = json.load(open(ROOT / "web" / "data" / "basemap.json"))
    cols = D["national"]["cols"]
    NAT = [dict(zip(cols, r)) for r in D["national"]["rows"]]
    for i, p in enumerate(NAT):
        t = date.fromisoformat(p["date"])
        w = [q for q in NAT[max(0, i - 6):i + 1] if (t - date.fromisoformat(q["date"])).days < 7]
        c = [q["consumption_kt"] for q in w if q["consumption_kt"]]
        r = [q["receipt_kt"] for q in w if q["receipt_kt"]]
        p["c7"] = sum(c) / len(c) if c else None          # receipt and burn exist only from late 2021
        p["r7"] = sum(r) / len(r) if r else None
        p["days"] = p["stock_mt"] * 1000 / p["c7"] if p["c7"] else None
        p["dreq"] = p.get("days_req")                      # days at CEA's daily requirement: comparable 2017 → today
        p["t"] = t
    last = NAT[-1]
    ago30 = min(NAT, key=lambda q: abs((q["t"] - (last["t"] - timedelta(days=30))).days))
    ly = min(NAT, key=lambda q: abs((q["t"] - (last["t"] - timedelta(days=365))).days))
    ly = ly if abs((ly["t"] - (last["t"] - timedelta(days=365))).days) <= 5 else None
    low_since = next((q for q in reversed(NAT) if q["t"] < last["t"] - timedelta(days=20) and q["stock_mt"] <= last["stock_mt"]), None)
    peak = max(NAT, key=lambda q: q["stock_mt"])
    low_since_d = next((q for q in reversed(NAT) if q["t"] < last["t"] - timedelta(days=20) and q["dreq"] is not None
                        and last["dreq"] is not None and q["dreq"] <= last["dreq"]), None)
    rec_low = min((q for q in NAT if q["dreq"] is not None), key=lambda q: q["dreq"])
    SUP = D["supply"]["series"]

    W_IN, H_IN = 20.0, 16.5
    S = Sheet(W_IN, H_IN, dpi)
    fig, W, H, pt = S.fig, S.W, S.H, S.pt
    M = 0.03 * W

    # --- header -----------------------------------------------------------------------------------------
    kf, hf, df = font(15), font(32, "bold"), font(12.5)
    y = H * 0.975 - S.line_h(kf)
    S.text(M, y, f"{' '.join('INDIA')}   /   COAL AT THE POWER STATIONS · {last['t']:%d %b %Y}".upper().replace("  /  ", "  /  "), kf, color=ACCENT)
    y -= S.line_h(hf) * 1.08
    drop30 = 1 - last["stock_mt"] / ago30["stock_mt"] if ago30 else 0
    head = ("India's power stations are burning through their coal" if drop30 > 0.1 else "Coal at India's power stations")
    S.text(M, y, head, hf)
    dek = (f"{fmt(last['stock_mt'], 1)} million tonnes in the yards, {fmt(last['dreq'], 1)} days of what the stations need"
           + (f", the least since {low_since_d['t']:%-d %B %Y}" if low_since_d else "") + ". "
           + (f"In tonnes, the lowest since {low_since['t']:%B %Y}. " if low_since else "")
           + f"{fmt(last['critical'])} of {fmt(last['plants'])} stations are critical.")
    y -= S.line_h(df) * 1.6
    S.text(M, y, dek, df, color=INK)
    header_bottom = y - 10 * pt
    foot_top = H * 0.052

    # --- left: map panel ------------------------------------------------------------------------------------
    ox, oy = M, foot_top + 6 * pt
    mw, mh = W * 0.565, header_bottom - oy
    lat0, lat1 = 6.4, 37.3
    sc = mh / (lat1 - lat0)
    kx = math.cos(math.radians((lat0 + lat1) / 2))
    clon = 82.4
    half = mw / (sc * kx) / 2
    lon0, lon1 = clon - half, clon + half
    P = lambda lon, lat: (ox + (lon - lon0) * kx * sc, oy + (lat - lat0) * sc)
    inside = lambda x, y, m=0: ox + m <= x <= ox + mw - m and oy + m <= y <= oy + mh - m
    ax = fig.add_axes([ox / W, oy / H, mw / W, mh / H])
    ax.set_xlim(ox, ox + mw); ax.set_ylim(oy, oy + mh); ax.axis("off")
    ax.add_patch(Rectangle((ox, oy), mw, mh, facecolor=WATER, edgecolor=EDGE, linewidth=1.6, zorder=0))
    S.ix.add((ox, oy + mh - 1, ox + mw, oy + mh + 1), "frame")
    ctry = countries((lon0, lat0, lon1, lat1), 0.02)
    ax.add_collection(PolyCollection([[P(*c) for c in ring[0]] for k, ring, pr in geoms(ctry) if k == "poly" and pr.get("iso") != "IND"],
                                     facecolor=LAND, edgecolor=BORDER, linewidth=0.7, zorder=1))
    ax.add_collection(PolyCollection([[P(*c) for c in ring[0]] for k, ring, _ in geoms(base["india"]) if k == "poly"],
                                     facecolor=INDIA, edgecolor="#8f8a80", linewidth=0.9, zorder=2))
    ax.add_collection(LineCollection([[P(*c) for c in ln] for k, ln, _ in geoms(base["states"]) if k == "line"], colors=STATE, linewidths=0.7, zorder=4))

    from PIL import Image, ImageDraw
    mask = Image.new("1", (int(W) + 1, int(H) + 1), 0)
    md = ImageDraw.Draw(mask)
    for src in (ctry, base["india"]):
        for k, ring, _ in geoms(src):
            if k == "poly" and len(ring[0]) > 2:
                md.polygon([(a, H - b) for a, b in (P(*c) for c in ring[0])], fill=1)
    land = mask.load()
    on_land = lambda *q: all(0 <= a < W and 0 <= b < H and land[int(a), int(H - b)] for a, b in q)

    # markers: mines first (pixel icons), then stations (pillars by status), spread on land where crowded
    node_px = 7.5 * pt
    a_big, a_small = 2.6 * pt, 1.6 * pt
    items = []
    for m in D["map"]["mines"]:
        x, y = P(m["lon"], m["lat"])
        if inside(x, y, 6 * pt):
            items.append((1e6 + (m.get("prod") or 0), "mine", m, (x, y)))
    for n in D["map"]["ports"]:
        x, y = P(n["lon"], n["lat"])
        if inside(x, y, 6 * pt) and n["kind"] == "port":
            items.append((9e5, "port", n, (x, y)))
    for p in D["plants"]:
        if p.get("lat") is None:
            continue
        x, y = P(p["lon"], p["lat"])
        if inside(x, y, 6 * pt):
            items.append((p.get("cap") or 0, "plant", p, (x, y)))

    def mbox(kind, obj, x, y):
        if kind in ("mine", "port"):
            return (x - node_px / 2, y - node_px / 2, x + node_px / 2, y + node_px / 2)
        cap = obj.get("cap") or 0
        a = a_big if cap >= 500 else a_small
        return (x - a, y, x + a, y + levels(cap) * a + a)

    placed, dropped = [], []
    for pri, kind, obj, (x, y) in sorted(items, key=lambda t: -t[0]):
        spot, r = None, 0.0
        while r <= 60 * pt and spot is None:
            ks = [0] if r == 0 else range(int(max(8, 2 * math.pi * r / (2.5 * pt))))
            for k in ks:
                th = 0 if r == 0 else 2 * math.pi * k / len(ks)
                cx, cy = x + r * math.cos(th), y + r * math.sin(th)
                b = mbox(kind, obj, cx, cy)
                if not (inside(b[0], b[1], 2 * pt) and inside(b[2], b[3], 2 * pt)):
                    continue
                foot = [(cx, cy)] if kind != "plant" else [(cx, cy), (b[0], cy + (b[2] - b[0]) / 4), (b[2], cy + (b[2] - b[0]) / 4)]
                if on_land(*foot) and S.free(b, pad=0.6 * pt):
                    spot = (cx, cy, b)
                    break
            r += 2 * pt
        if not spot:
            dropped.append(obj)
            continue
        S.ix.add(spot[2], f"{kind}:{obj.get('id') or obj.get('n')}")
        placed.append((kind, obj, (x, y), spot))
    pos = {(o.get("id") or o.get("n")): s for k, o, _, s in placed}

    # routes under the markers
    for r in D["map"]["routes"]:
        cs = [P(*c) for c in r["c"]]
        if not any(inside(*c) for c in cs):
            continue
        if r.get("derived"):
            end = pos.get((r.get("serves") or [None])[0])
            path = curve(cs[0], end[:2] if end else cs[-1], bend=0.16)
            col, ls, lw = (RAIL, (0, (5, 2)), 0.6) if r["mode"] == "rail" else (SEA, (0, (1.2, 2.2)), 0.7)
            ax.plot([q[0] for q in path], [q[1] for q in path], color=col, linewidth=lw, linestyle=ls, alpha=0.55, zorder=8)
            arrow_at(S, path, 0.9, 2.8 * pt, col)
        elif r["mode"] == "sea":
            path = smooth(cs)
            ax.plot([q[0] for q in path], [q[1] for q in path], color=SEA, linewidth=1.0, linestyle=(0, (1.2, 2.2)), alpha=0.9, zorder=8)
            if inside(*path[-1]):
                arrow_at(S, path, 0.965, 3.5 * pt, SEA)
        else:
            col, ls = (RAIL, (0, (5, 2))) if r["mode"] == "rail" else (CONV, (0, (2, 2)))
            ax.plot([c[0] for c in cs], [c[1] for c in cs], color=col, linewidth=0.8, linestyle=ls, alpha=0.85, zorder=8)

    faces, fcols, edges, seams, leaders, dots = [], [], [], [], [], []
    for kind, obj, (x, y), (cx, cy, b) in sorted(placed, key=lambda t: -t[3][1]):
        if abs(cx - x) + abs(cy - y) > 1.5 * pt:
            leaders.append([(x, y), (cx, cy)]); dots.append((x, y))
        if kind in ("mine", "port"):
            c = MINE if kind == "mine" else SEA
            fig.add_artist(Rectangle((b[0], b[1]), node_px, node_px, facecolor="#ffffff", edgecolor=c, linewidth=1.0, transform=ID, zorder=20))
            S.icon("mine" if kind == "mine" else "ship", b[0] + node_px * 0.13, b[1] + node_px * 0.13, node_px * 0.74, c, z=21)
            continue
        cap = obj.get("cap") or 0
        a = a_big if cap >= 500 else a_small
        fc = COL[status(obj)]
        fs, ss, _ = pillar(cx, cy, a, levels(cap), fc)
        for poly, c in fs:
            faces.append(poly); fcols.append(c); edges.append("#1b1d22")
        seams += ss
    fig.add_artist(LineCollection(leaders, colors="#5a564e", linewidths=0.45, transform=ID, zorder=18))
    if dots:
        fig.add_artist(PatchCollection([Rectangle((x - 0.7 * pt, y - 0.7 * pt), 1.4 * pt, 1.4 * pt) for x, y in dots], facecolor="#5a564e", edgecolor="none", transform=ID, zorder=19))
    fig.add_artist(PolyCollection(faces, facecolors=fcols, edgecolors=edges, linewidths=0.35, transform=ID, zorder=30))
    fig.add_artist(LineCollection(seams, colors="#00000033", linewidths=0.35, transform=ID, zorder=31))

    # labels: the biggest stations in trouble (critical first, then low), with their days of coal
    names = label_names([plants[p["id"]] for p in D["plants"] if p.get("id") in plants])
    f1, f2 = font(7.2, "bold"), font(6.4)
    lh1, lh2 = S.line_h(f1), S.line_h(f2)
    isz = 7.6 * pt
    cands = sorted([t for t in placed if t[0] == "plant" and status(t[1]) in ("crit", "low") and (t[1].get("cap") or 0) >= 600],
                   key=lambda t: (status(t[1]) != "crit", -(t[1].get("cap") or 0)))
    n_lab = 0
    for kind, p, _, (cx, cy, b) in cands:
        if n_lab >= 34:
            break
        nm = names.get(p.get("id")) or p["n"].title()
        lines = S.wrap_lines(nm, f1, 110 * pt)
        sub = f"{fmt(p['days'], 1) if p.get('days') is not None and p['days'] < 10 else fmt(p.get('days'))} days · {fmt(p.get('pct'))}% of normative" if p.get("days") is not None else f"{fmt(p.get('pct'))}% of normative"
        tw = max(max(S.measure(l, f1)[0] for l in lines), S.measure(sub, f2)[0])
        bw, bh = 2.5 * pt + isz + 4 * pt + tw + 4 * pt, max(isz, lh1 * len(lines) + lh2) + 5 * pt
        done = False
        for rr in (8, 16, 26, 38, 52, 68, 86):
            for ang in (40, 140, 0, 180, 70, 110, -25, 205, 90, -60, 240, -90):
                dx, dy = math.cos(math.radians(ang)) * rr * pt, math.sin(math.radians(ang)) * rr * pt
                lx = cx + dx + (3 * pt if dx >= 0 else -bw - 3 * pt)
                ly_ = b[3] + dy - (bh / 2 if abs(dy) < 1 else 0)
                box = (lx, ly_, lx + bw, ly_ + bh)
                if not (inside(box[0], box[1], 3 * pt) and inside(box[2], box[3], 3 * pt)) or not S.free(box, pad=1.5 * pt):
                    continue
                c = COL[status(p)]
                fig.add_artist(Rectangle((lx, ly_), bw, bh, facecolor="#fffffff2", edgecolor=c, linewidth=0.9, transform=ID, zorder=60))
                S.ix.add(box, f"label:{p['n']}")
                S.swatch("coal" if plants.get(p.get("id"), {}).get("type") != "lignite" else "lignite", lx + 2.5 * pt, ly_ + bh - 2.5 * pt - isz, isz, c, z=62, register=False)
                tx, yy = lx + 2.5 * pt + isz + 4 * pt, ly_ + bh - 2.5 * pt
                for l in lines:
                    yy -= lh1
                    fig.text(tx / W, yy / H, l, fontproperties=f1, color=INK, zorder=63)
                yy -= lh2
                fig.text(tx / W, yy / H, sub, fontproperties=f2, color=CRIT if status(p) == "crit" else MUTED, zorder=63)
                ex, ey = min(max(cx, lx), lx + bw), min(max(b[3], ly_), ly_ + bh)
                fig.add_artist(LineCollection([[(cx, b[3]), (ex, ey)]], colors=INK, linewidths=0.55, transform=ID, zorder=59))
                n_lab += 1
                done = True
                break
            if done:
                break

    # coalfield names where they fit
    cf = font(6.6, "bold", "italic")
    for kind, m, _, (cx, cy, b) in placed:
        if kind != "mine" or m.get("kind") != "coalfield":
            continue
        name = m["name"].replace(" Coalfield", "").replace(" coalfield", "")
        w_, h_ = S.measure(name, cf)
        for dx, dy in ((node_px / 2 + 2 * pt, -h_ / 2), (-node_px / 2 - 2 * pt - w_, -h_ / 2), (-w_ / 2, node_px / 2 + 1.5 * pt), (-w_ / 2, -node_px / 2 - 1.5 * pt - h_)):
            box = (cx + dx, cy + dy, cx + dx + w_, cy + dy + h_)
            if inside(box[0], box[1], 3 * pt) and inside(box[2], box[3], 3 * pt) and S.free(box, pad=1 * pt):
                S.text(box[0], box[1], name, cf, color=MINE, tag="coalfield", halo=INDIA)
                break

    # --- right column -----------------------------------------------------------------------------------
    rx0 = ox + mw + 12 * pt
    rw = W - M - rx0
    pad = 9 * pt

    def card(x, y_top, w, h, title):
        fig.add_artist(Rectangle((x + 6, y_top - h - 6), w, h, facecolor="#00000022", edgecolor="none", transform=ID, zorder=44))
        fig.add_artist(Rectangle((x, y_top - h), w, h, facecolor=CARD, edgecolor=EDGE, linewidth=1.6, transform=ID, zorder=45))
        tf = font(9.5, "bold")
        S.text(x + pad, y_top - pad - S.line_h(tf), title.upper(), tf)
        return y_top - pad - S.line_h(tf) * 1.9

    def line_chart(x, y, w, h, series, t0, t1, lo, hi, ticks, fmt_t, xticks, gap=12):
        """Series in sheet pixels; y axis on the right (labels registered), x labels below."""
        X = lambda t: x + (t - t0) / ((t1 - t0) or 1) * (w - 34 * pt)
        Y = lambda v: y + (v - lo) / ((hi - lo) or 1) * h
        tf = font(6.6)
        for v in ticks:
            fig.add_artist(LineCollection([[(x, Y(v)), (x + w - 34 * pt, Y(v))]], colors="#e3ddd0", linewidths=0.6, transform=ID, zorder=46))
            S.text(x + w - 30 * pt, Y(v) - S.line_h(tf) / 2, fmt_t(v), tf, color=MUTED)
        for t, l in xticks:                        # a label that would touch the axis numbers is left out
            w_ = S.measure(l, tf)[0]
            if S.free((X(t) - w_ / 2, y - S.line_h(tf) - 3 * pt, X(t) + w_ / 2, y - 3 * pt), pad=2 * pt):
                S.text(X(t), y - S.line_h(tf) - 3 * pt, l, tf, color=MUTED, ha="center")
        for pts, col, lw, ls in series:
            segs, cur, prev = [], [], None
            for t, v in pts:
                if prev is not None and t - prev > gap:
                    segs.append(cur); cur = []
                cur.append((X(t), Y(v))); prev = t
            segs.append(cur)
            fig.add_artist(LineCollection([s_ for s_ in segs if len(s_) > 1], colors=col, linewidths=lw, linestyles=ls, transform=ID, zorder=47))
        S.ix.add((x, y, x + w, y + h), "chart")
        return X, Y

    def xticks_for(d0, d1):
        span = (d1 - d0).days
        step = 12 if span > 1500 else 6 if span > 700 else 3 if span > 250 else 1
        out, d = [], date(d0.year, d0.month, 1)
        while d <= d1:
            if d > d0 and (d.month - 1) % step == 0:
                out.append(((d - d0).days, f"{d:%b}\n{d.year}".split("\n")[0] + (f" {d.year}" if d.month == 1 or step >= 6 else "")))
            d = date(d.year + (d.month // 12), d.month % 12 + 1, 1)
        return out

    # card 1: the record, as days of coal (comparable across the report's changes in coverage)
    top = header_bottom
    h1 = (top - foot_top) * 0.40
    y = card(rx0, top, rw, h1, f"Days of coal at India's power stations, {NAT[0]['t'].year} to {last['t'].year}")
    S.text(rx0 + pad, y - S.line_h(font(6.4)), "Stock ÷ what the stations need a day at 85% load (CEA's yardstick). Gaps: CEA reports missing.", font(6.4), color=MUTED)
    y -= S.line_h(font(6.4)) * 1.6
    d0 = NAT[0]["t"]
    tt = lambda q: (q["t"] - d0).days
    t1 = tt(last)
    DQ = [q for q in NAT if q["dreq"] is not None]
    hi = max(q["dreq"] for q in DQ) * 1.08
    ticks = list(range(0, int(hi) + 1, 5 if hi <= 40 else 10))
    crit_from = date(2021, 12, 1)                  # the revised stocking norms: "critical" has meant under 25% of normative since
    cy0 = top - h1 + pad + S.line_h(font(6.4)) + 3 * pt + 26 * pt + 18 * pt
    chart_h = y - cy0 - 6 * pt
    X, Y = line_chart(rx0 + pad, cy0, rw - 2 * pad, chart_h, [([(tt(q), q["dreq"]) for q in DQ], STOCK, 1.8, "solid")], 0, t1, 0, max(ticks[-1], hi),
                      ticks, lambda v: f"{v:,.0f}", xticks_for(d0, last["t"]))
    # the report widened on 14 Nov 2021: a dashed rule
    xb = X((date(2021, 11, 14) - d0).days)
    fig.add_artist(LineCollection([[(xb, cy0), (xb, cy0 + chart_h)]], colors="#9aa0ab", linewidths=0.7, linestyles=[(0, (2, 2))], transform=ID, zorder=46))
    # critical count bars along the bottom, from the Dec 2021 norms
    bh_max = 26 * pt
    CQ = [q for q in NAT if q["t"] >= crit_from]
    cmax = max(q["critical"] for q in CQ) or 1
    b0 = top - h1 + pad + S.line_h(font(6.4)) + 3 * pt
    bw_ = max(1.0, (X(1) - X(0)) * 0.8)
    bars = [Rectangle((X(tt(q)) - bw_ / 2, b0), bw_, q["critical"] / cmax * bh_max) for q in CQ]
    fig.add_artist(PatchCollection(bars, facecolor=CRIT, edgecolor="none", transform=ID, zorder=47, alpha=0.8))
    S.ix.add((X(tt(CQ[0])) - 1, b0, rx0 + rw - pad, b0 + bh_max), "crit bars")
    S.text(rx0 + pad, top - h1 + pad, f"Red bars: stations with critical stock each day since the December 2021 norms (most: {cmax})", font(6.4), color=CRIT)
    # annotations: today, the record low, the dashed rule
    line_pts = [(X(tt(r_)), Y(r_["dreq"])) for r_ in DQ]
    af = font(7.2, "bold")
    notes = [(last, f"{fmt(last['dreq'], 1)} days ({fmt(last['stock_mt'], 1)} Mt), {last['t']:%-d %b %Y}", CRIT)]
    if rec_low["t"] < last["t"] - timedelta(days=60):
        notes.append((rec_low, f"{fmt(rec_low['dreq'], 1)} days, {rec_low['t']:%-d %b %Y}: the 2021 shortage" if rec_low["t"].year == 2021 else
                      f"Lowest: {fmt(rec_low['dreq'], 1)} days, {rec_low['t']:%-d %b %Y}", INK))
    for q, txt, colr in notes:
        x_, y_ = X(tt(q)), Y(q["dreq"])
        fig.add_artist(Rectangle((x_ - 2 * pt, y_ - 2 * pt), 4 * pt, 4 * pt, facecolor=colr, edgecolor="#ffffff", linewidth=0.8, transform=ID, zorder=49))
        w_, h_ = S.measure(txt, af)
        for bx, by in ((x_ - w_ - 5 * pt, y_ - h_ / 2), (x_ + 6 * pt, y_ - h_ / 2), (x_ - w_ / 2, y_ - h_ - 7 * pt), (x_ - w_ - 5 * pt, y_ + 8 * pt),
                       (x_ + 6 * pt, y_ + 4 * pt), (x_ - w_ / 2, y_ + 10 * pt), (x_ - w_ - 5 * pt, y_ - h_ - 8 * pt)):
            box = (bx, by, bx + w_, by + h_)
            hits_line = any(box[0] - 2 * pt <= lx_ <= box[2] + 2 * pt and box[1] - 2 * pt <= ly2 <= box[3] + 2 * pt for lx_, ly2 in line_pts)
            if box[0] > rx0 + pad and box[2] < rx0 + rw - 34 * pt and box[1] > cy0 and not hits_line and S.free(box, pad=1 * pt, ignore=("chart",)):
                S.text(bx, by, txt, af, color=colr, check=False, halo="#ffffff")
                S.ix.add(box, "annot")
                break
    rf = font(6.2)
    rt = "CEA adds 27 plants to the report"
    rw_, rh_ = S.measure(rt, rf)
    S.text(xb + 3 * pt, cy0 + chart_h - rh_, rt, rf, color=MUTED, check=False, halo="#ffffff")

    # card 2: headline tiles
    top2 = top - h1 - 12 * pt
    th = (top - foot_top) * 0.105
    tw = (rw - 3 * 9 * pt) / 4
    FYp = (D.get("fy") or {}).get("prod") or {}
    FYd = (D.get("fy") or {}).get("dispatch") or {}
    tiles = [
        ("mine", MINE, "Mined since 1 April", f"{fmt(FYp.get('ytd'), 0)} Mt" if FYp.get("ytd") else "–",
         (f"{date.fromisoformat(FYp['months'][0] + '-01'):%b}–{date.fromisoformat(FYp['months'][1] + '-01'):%b} {'down' if FYp['yoy'] < 0 else 'up'} {fmt(abs(FYp['yoy']) * 100, 1)}% on last year; dispatch {'down' if FYd.get('yoy', 0) < 0 else 'up'} {fmt(abs(FYd.get('yoy') or 0) * 100, 1)}%"
          if FYp.get("yoy") is not None else "all mines, National Coal Portal")),
        ("smoke", BURN, "Burnt a day", f"{fmt(last['c7'] / 1000, 2)} Mt", f"arriving {fmt(last['r7'] / 1000, 2)} Mt a day"),
        ("coal", STOCK, "In the yards", f"{fmt(last['stock_mt'], 1)} Mt", f"{fmt(last['dreq'], 1)} days of need; {fmt(last['stock_mt'] / last['normative_mt'] * 100)}% of the normative stock"),
        ("mine", "#6b7385", "In the ground", f"{fmt((D.get('reserves', {}).get('total') or {}).get('coal_bt'), 0)} bn t", "geological coal resources, GSI"),
    ]
    for i, (ic, c, h_, big, sub) in enumerate(tiles):
        x = rx0 + i * (tw + 9 * pt)
        fig.add_artist(Rectangle((x + 5, top2 - th - 5), tw, th, facecolor="#00000022", edgecolor="none", transform=ID, zorder=44))
        fig.add_artist(Rectangle((x, top2 - th), tw, th, facecolor=CARD, edgecolor=CRIT if ic == "coal" and last["critical"] >= 50 else EDGE, linewidth=1.6, transform=ID, zorder=45))
        sw = 11 * pt
        S.swatch(ic, x + 7 * pt, top2 - 7 * pt - sw, sw, c)
        hf_ = font(7.2, "bold")
        S.text(x + 7 * pt + sw + 5 * pt, top2 - 7 * pt - sw / 2 - S.line_h(hf_) / 2, h_.upper(), hf_, color=MUTED)
        bf = font(19, "bold")
        S.text(x + 7 * pt, top2 - 7 * pt - sw - 6 * pt - S.line_h(bf), big, bf, color=CRIT if ic == "coal" and last["critical"] >= 50 else INK)
        yy = top2 - 7 * pt - sw - 6 * pt - S.line_h(bf) - 4 * pt
        for l in S.wrap_lines(sub, font(6.6), tw - 14 * pt):
            yy -= S.line_h(font(6.6)) * 1.15
            S.text(x + 7 * pt, yy, l, font(6.6), color=MUTED)
        if yy < top2 - th + 4 * pt:
            raise RuntimeError(f"tile overflow: {h_}")

    # card 3 (left half): arriving vs burnt; card 4 (right half): fewest days left
    top3 = top2 - th - 12 * pt
    h3 = top3 - foot_top
    cw = (rw - 12 * pt) / 2
    y = card(rx0, top3, cw, h3, "From mine to boiler, Mt a month")
    kf_ = font(6.8)
    MS = [("dispatch_power", RAIL, "Sent from the mines to power stations"),
          ("cea_rcpt", STOCK, "Received by power stations"), ("cea_cons", BURN, "Burnt")]
    MS = [m for m in MS if m[0] in SUP]
    ky, kx_ = y - S.line_h(kf_) * 1.5, rx0 + pad
    for i, (k, col, lbl) in enumerate(MS):
        if kx_ + 18 * pt + S.measure(lbl, kf_)[0] > rx0 + cw - pad:      # the key wraps inside the card
            ky -= S.line_h(kf_) * 1.5
            kx_ = rx0 + pad
        fig.add_artist(LineCollection([[(kx_, ky + 3 * pt), (kx_ + 14 * pt, ky + 3 * pt)]], colors=col, linewidths=1.8, transform=ID, zorder=46))
        S.ix.add((kx_, ky, kx_ + 14 * pt, ky + 6 * pt), "key")
        kx_ = S.text(kx_ + 18 * pt, ky, lbl, kf_)[2] + 10 * pt
    mdate = lambda p_: date(int(p_[:4]), int(p_[5:7]), 1)
    m1 = max(mdate(v[-1][0]) for k, *_ in MS for v in [SUP[k]])
    m0 = date(m1.year - 3, m1.month, 1)
    tm = lambda d_: (d_ - m0).days
    ser = [([(tm(mdate(p_)), v) for p_, v in SUP[k] if mdate(p_) >= m0], col, 1.6, "solid") for k, col, _ in MS]
    vals = [v for sr in ser for _, v in sr[0]]
    lo_v = math.floor(min(vals) / 10) * 10
    hi_v = max(vals) * 1.06
    tk = list(range(int(lo_v), int(hi_v) + 1, 10 if hi_v - lo_v <= 70 else 20))
    line_chart(rx0 + pad, top3 - h3 + pad + 16 * pt, cw - 2 * pad, ky - 12 * pt - (top3 - h3 + pad + 16 * pt), ser, 0, tm(m1), lo_v, max(tk[-1], hi_v), tk,
               lambda v: f"{v:.0f}", xticks_for(m0, m1), gap=40)

    x4 = rx0 + cw + 12 * pt
    y = card(x4, top3, cw, h3, "Fewest days of coal left")
    lf = font(6.9)
    worst = sorted([p for p in D["plants"] if p.get("days") is not None and (p.get("c7") or 0) > 1 and (p.get("cap") or 0) >= 300], key=lambda p: p["days"])
    S.text(x4 + pad, y - S.line_h(font(6.4)), "Stations of 300 MW or more, stock ÷ last 7 days' burn", font(6.4), color=MUTED)
    y -= S.line_h(font(6.4)) * 1.8
    rows_done = 0
    for p in worst:
        nm = names.get(p.get("id")) or p["n"].title()
        val = f"{fmt(p['days'], 1)} d"
        vw = S.measure(val, font(6.9, "bold"))[0]
        lines = S.wrap_lines(f"{nm}, {p.get('st') or ''}", lf, cw - 2 * pad - vw - 16 * pt)
        need = len(lines) * S.line_h(lf) * 1.12 + 2.5 * pt
        if y - need < top3 - h3 + pad:
            break
        sw = 6 * pt
        fig.add_artist(Rectangle((x4 + pad, y - S.line_h(lf) + 1 * pt), sw, sw, facecolor=COL[status(p)], edgecolor="none", transform=ID, zorder=46))
        S.ix.add((x4 + pad, y - S.line_h(lf) + 1 * pt, x4 + pad + sw, y - S.line_h(lf) + 1 * pt + sw), "sq")
        for i, l in enumerate(lines):
            y -= S.line_h(lf) * 1.12
            S.text(x4 + pad + sw + 5 * pt, y, l, lf)
            if i == 0:
                S.text(x4 + cw - pad, y, val, font(6.9, "bold"), ha="right", color=CRIT if p["days"] < 3 else INK)
        y -= 2.5 * pt
        rows_done += 1

    # map legend inside the map, bottom-left, in its own box
    lg = [("sq", CRIT, "Critical: under 25% of normative stock"), ("sq", LOW, "Under 50%"), ("sq", OK, "50% or more"), ("sq", IDLE, "Not burning coal now"),
          ("icon", MINE, "Mine or coalfield"), ("icon", SEA, "Coal port"), ("line", RAIL, "Coal by rail (dashed arcs: company-named links)"), ("line", SEA, "Coal by sea"),
          ("line", CONV, "Conveyor or road")]
    lf2 = font(6.6)
    lw_ = max(S.measure(t, lf2)[0] for *_, t in lg) + 30 * pt
    lh_ = len(lg) * 11 * pt + 30 * pt
    lx0, ly0 = ox + 8 * pt, oy + 8 * pt
    fig.add_artist(Rectangle((lx0, ly0), lw_, lh_, facecolor="#ffffffee", edgecolor=EDGE, linewidth=1.0, transform=ID, zorder=64))
    if not S.free((lx0, ly0, lx0 + lw_, ly0 + lh_), pad=0):
        raise RuntimeError("map legend would cover markers or labels")
    S.ix.add((lx0, ly0, lx0 + lw_, ly0 + lh_), "legend")
    yy = ly0 + lh_ - 7 * pt - S.line_h(font(7.4, "bold"))
    S.text(lx0 + 7 * pt, yy, "Pillar height = capacity; colour = coal left", font(7.4, "bold"), check=False, z=66)
    for kind, c, t in lg:
        yy -= 11 * pt
        if kind == "sq":
            fig.add_artist(Rectangle((lx0 + 7 * pt, yy), 8 * pt, 8 * pt, facecolor=c, edgecolor="#1b1d22", linewidth=0.5, transform=ID, zorder=66))
        elif kind == "icon":
            fig.add_artist(Rectangle((lx0 + 7 * pt, yy), 8 * pt, 8 * pt, facecolor="#ffffff", edgecolor=c, linewidth=0.9, transform=ID, zorder=66))
            S.icon("mine" if c == MINE else "ship", lx0 + 8 * pt, yy + 1 * pt, 6 * pt, c, z=67)
        else:
            fig.add_artist(LineCollection([[(lx0 + 6 * pt, yy + 4 * pt), (lx0 + 17 * pt, yy + 4 * pt)]], colors=c, linewidths=1.4, linestyles=[(0, (3, 1.5))], transform=ID, zorder=66))
        S.text(lx0 + 21 * pt, yy + 4 * pt - S.line_h(lf2) / 2, t, lf2, check=False, z=66)

    # --- footer --------------------------------------------------------------------------------------------
    lines = [f"Rendered {datetime.now(R.IST):%d %b %Y %H:%M} IST from power.reclaimchennai.city/coal. Stock, receipts and burn: Central Electricity Authority Daily Coal Stock Report "
             f"(National Power Portal), {NAT[0]['t']:%-d %b %Y} to {last['t']:%-d %b %Y}, {len(NAT)} report days. Station days left = stock ÷ 7-day average burn.",
             "Monthly: Ministry of Coal (mined, sent to power), CEA monthly coal report (received, burnt). Resources: Geological Survey of India. Mines, ports and routes: company records, CEA remarks, OpenStreetMap (ODbL). "
             "Boundaries: DataMeet (CC BY 4.0), Natural Earth. In crowded places pillars are moved apart and tied to their true spot."]
    ff = font(6.6)
    fy = H * 0.012
    for ln in reversed(lines):
        S.text(M, fy, ln, ff, color=MUTED, tag="footer")
        fy += S.line_h(ff) * 1.3

    OUT.mkdir(parents=True, exist_ok=True)
    out = OUT / "coal_india_en.png"
    fig.savefig(out, dpi=dpi, facecolor=PAPER)
    import matplotlib.pyplot as plt
    plt.close(fig)
    im = Image.open(out)
    im.thumbnail((2000, 1650))
    im.convert("RGB").save(OUT / "coal_india_en_preview.jpg", quality=86)
    print(f"{out} {out.stat().st_size / 1e6:.1f} MB · {len(placed)} markers · could not fit {len(dropped)} · {n_lab} labels · {rows_done} list rows")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dpi", type=int, default=300)
    draw(ap.parse_args().dpi)


if __name__ == "__main__":
    main()
