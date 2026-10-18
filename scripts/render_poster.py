#!/usr/bin/env python3
"""Posters in the house style of the flights / boats sheets (tn-flights/flights/scripts/render_poster.py):
cream land, pink spaced kicker, black headline, credits at the foot.

    .venv/bin/python scripts/render_poster.py            # both sheets -> web/posters/
    .venv/bin/python scripts/render_poster.py --only tn  # just Tamil Nadu

Sheets (20 x 16.5 in, 300 dpi; the map runs the full width, neighbouring countries included)
  india  every mapped station, 400/765 kV and HVDC lines, every supply chain and coal link
  tn     every Tamil Nadu station, the 110-765 kV grid, 12.8k wind turbines, supply chains into TN

Rules the layout enforces (the run fails or reports rather than overlapping):
  * one spatial index holds every placed thing: pillar, mine/port icon, label bubble, route label,
    country and sea name, legend row, card text. Nothing is placed where it would touch something already there.
  * stations in crowded areas (Korba, Talcher, Singrauli...) are spread out: a pillar that cannot stand on
    its own point moves to the nearest free spot and a thin leader line runs back to a dot at the true spot.
  * station labels: the fuel's pixel SVG icon (same ASCII art as web/icons.svg) + the station's name without
    type suffixes (TPS, STPS, Thermal Power Station...) + capacity; long names wrap, never truncate; the
    bubble is sized to its content.
  * sea and coal routes are drawn like old shipping maps: curved, arrowed, labelled "From → To".
"""
import argparse
import json
import math
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.font_manager as fm                       # noqa: E402
import matplotlib.pyplot as plt                            # noqa: E402
from matplotlib.collections import LineCollection, PolyCollection, PatchCollection  # noqa: E402
from matplotlib.patches import Rectangle, Polygon          # noqa: E402
from matplotlib.transforms import IdentityTransform        # noqa: E402
import matplotlib.patheffects as pe                        # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
from build_icons import ART                                # noqa: E402  the icons.svg pixel art

WEB = ROOT / "web"
OUT = WEB / "posters"
IST = timezone(timedelta(hours=5, minutes=30))
ID = IdentityTransform()

PAPER = "#f4f1ea"; LAND = "#f3f1ec"; INDIA = "#fbfaf7"; WATER = "#dfe3e6"; STATE = "#d3cec4"; BORDER = "#a9a49a"
INK = "#1a1a1a"; MUTED = "#6f6b64"; ACCENT = "#e8447f"; CARD = "#ffffff"; EDGE = "#1f2229"; SEA_INK = "#4d6f8c"
FUEL = {"coal": "#e34948", "lignite": "#c0392b", "gas": "#eb6834", "diesel": "#6b7385", "nuclear": "#e87ba4",
        "hydro": "#2a78d6", "pumped_storage": "#1c5cab", "wind": "#1baf7a", "solar": "#eda100",
        "biomass": "#008300", "cogen": "#2e7d32", "waste": "#556b2f", "battery": "#8a90a8"}
LABEL = {"coal": "Coal", "lignite": "Lignite", "gas": "Gas", "diesel": "Diesel / naphtha", "nuclear": "Nuclear",
         "hydro": "Hydro", "pumped_storage": "Pumped storage", "wind": "Wind", "solar": "Solar", "biomass": "Biomass",
         "cogen": "Bagasse cogen", "waste": "Waste to energy", "battery": "Battery storage"}
ICON = {"coal": "coal", "lignite": "lignite", "gas": "gas", "diesel": "diesel", "nuclear": "nuclear", "hydro": "hydro",
        "pumped_storage": "pumped_storage", "wind": "wind", "solar": "solar", "biomass": "biomass", "cogen": "cogen",
        "waste": "biomass", "battery": "substation"}
ORDER = ["coal", "lignite", "wind", "gas", "hydro", "pumped_storage", "solar", "nuclear", "biomass", "cogen", "waste", "diesel", "battery"]
KV = {"765": ("#7f2704", 1.1), "hvdc": ("#8e1f6b", 1.0), "400": ("#c2410c", 0.75), "220": ("#ea8a2e", 0.45), "110": ("#d9a066", 0.3)}
SEA = "#1f6fb5"; RAIL = "#6b4fc4"; PIPE = "#d9660b"; CONV = "#5d6470"
NODE = {"mine": ("mine", "#9a5b00"), "coal_mine": ("mine", "#9a5b00"), "lignite_mine": ("mine", "#9a5b00"), "coalfield": ("mine", "#9a5b00"),
        "captive_block": ("mine", "#9a5b00"), "port": ("ship", SEA), "terminal": ("ship", SEA), "foreign_port": ("ship", SEA),
        "lng": ("gas", PIPE), "gasfield": ("gas", PIPE), "gas_terminal": ("gas", PIPE)}

for f in ("NotoSans-Regular.ttf", "NotoSans-Bold.ttf", "NotoSans-Italic.ttf", "NotoSans-SemiBold.ttf"):
    p = Path("/usr/share/fonts/truetype/noto") / f
    if p.exists():
        fm.fontManager.addfont(str(p))
FAMILY = ["Noto Sans", "DejaVu Sans"]


def font(size, weight="normal", style="normal"):
    return fm.FontProperties(family=FAMILY, size=size, weight=weight, style=style)


def fmt(v, d=0):
    return "–" if v is None else f"{v:,.{d}f}"


def hrs(h):
    return "–" if h is None else f"{int(h)}:{round((h - int(h)) * 60):02d}"


# --- names without type suffixes ------------------------------------------------------------------------
SUFFIX = [
    r"super thermal power (station|project|plant)", r"thermal power (station|project|plant)( project)?", r"atomic power (station|project|plant)",
    r"nuclear power (station|project|plant)", r"gas turbine power (station|plant)", r"combined cycle (power )?(plant|station|project)",
    r"hydro ?electric (power )?(station|project|plant)", r"hydel (power )?(station|project)", r"pumped storage (power )?(station|project|plant|house)?",
    r"solar (power )?(park|project|plant|station)", r"(offshore )?wind (farm|park|belt|zone|power project)", r"power (station|plant|project|house|generation)",
    r"gas engine power plant", r"gas engine plant", r"gas plant", r"diesel power plant", r"captive power (plant|station)", r"captive",
    r"thermal plant", r"thermal power", r"power house", r"\bproject\b",
    r"\b(u?mtpp|umtpp|stpp|stps|sctpp|ctpp|tpp|tps|ccpp|ccgt|gtps|gps|hps|pshep|shep|hep|aps|npp|psp|gt|dg|pp)\b",
    r"\b(limited|ltd|pvt|private|company|corporation|co)\b\.?", r"\b\d+(\.\d+)? ?mw\b", r"\bists\b",
]
SUFFIX_RX = re.compile("|".join(SUFFIX), re.I)


def clean_name(n):
    s = re.sub(r"\s+—.*$", "", n)                        # "... — now Orissa Alloy Steel": a note, not the name
    s = re.sub(r"\s*\([^)]*\)", "", s)                   # "(NTPC Tamil Nadu Energy Company)", "(KKNPP)"
    s = SUFFIX_RX.sub(" ", s)
    s = re.sub(r"\s+,", ",", s)
    s = re.sub(r"\s{2,}", " ", s).strip(" ,.–-")
    s = re.sub(r"\s*[–—-]\s*$", "", s)
    s = re.sub(r"\s+-\s*(?=[IVX\d])", " ", s)              # "Pragati CCGT-III" -> "Pragati III"
    return s                                            # "" when the name was only a type ("Solar Power Station")


def label_names(plants):
    """Clean names, keeping two stations that share a town apart ("Suratgarh" / "Suratgarh Super")."""
    out, seen = {}, {}
    for p in plants:
        out[p["id"]] = clean_name(p["name"])
        seen.setdefault(out[p["id"]].lower(), []).append(p)
    for k, group in seen.items():
        if k and len(group) > 1:
            for p in group:
                if re.search(r"\bstps\b|super thermal|\bstpp\b", p["name"], re.I):
                    out[p["id"]] += " Super"
                elif re.search(r"\b(ccgt|ccpp|gas)\b", p["name"], re.I) and p["type"] == "gas":
                    out[p["id"]] += " Gas"
    return out


def place_name(s):
    """Short place for route labels: "Richards Bay Coal Terminal, South Africa" -> "Richards Bay"."""
    s = re.sub(r"\s*\(.*?\)", "", s or "").split(",")[0]
    s = re.sub(r"^Port of |\s+(Port|coal anchorages|coal ports|Coal Terminal|Chemical Concentrates Plant|railway station|captive offshore coal jetty)\b.*$", "", s)
    return s.strip()


# --- sheet with a spatial index ---------------------------------------------------------------------------
class Index:
    def __init__(self, cell=60):
        self.cell, self.grid, self.items = cell, {}, []

    def _cells(self, b):
        c = self.cell
        for i in range(int(b[0] // c), int(b[2] // c) + 1):
            for j in range(int(b[1] // c), int(b[3] // c) + 1):
                yield i, j

    def add(self, b, tag):
        k = len(self.items)
        self.items.append((b, tag))
        for ij in self._cells(b):
            self.grid.setdefault(ij, []).append(k)

    def hits(self, b, pad=2, ignore=()):
        seen, out = set(), []
        q = (b[0] - pad, b[1] - pad, b[2] + pad, b[3] + pad)
        for ij in self._cells(q):
            for k in self.grid.get(ij, ()):
                if k in seen:
                    continue
                seen.add(k)
                o, tag = self.items[k]
                if tag in ignore:
                    continue
                if q[0] < o[2] and q[2] > o[0] and q[1] < o[3] and q[3] > o[1]:
                    out.append(tag)
        return out


class Sheet:
    def __init__(self, w_in, h_in, dpi):
        self.fig = plt.figure(figsize=(w_in, h_in), dpi=dpi, facecolor=PAPER)
        self.W, self.H, self.pt = w_in * dpi, h_in * dpi, dpi / 72.0
        self.R = self.fig.canvas.get_renderer()
        self.ix = Index(cell=24 * self.pt)
        self._m = {}

    def measure(self, s, fp):
        k = (s, fp.get_size_in_points(), fp.get_weight(), fp.get_style())
        if k not in self._m:
            t = self.fig.text(0, 0, s, fontproperties=fp)
            bb = t.get_window_extent(self.R)
            t.remove()
            self._m[k] = (bb.width, bb.height)
        return self._m[k]

    def line_h(self, fp):
        return self.measure("Ag", fp)[1]

    def text(self, x, y, s, fp, color=INK, ha="left", tag=None, check=True, z=70, halo=None):
        """(x, y) is the bottom of the text box; the box is registered and must be free."""
        w, h = self.measure(s, fp)
        x0 = x - (w if ha == "right" else w / 2 if ha == "center" else 0)
        box = (x0, y, x0 + w, y + h)
        if check:
            hit = self.ix.hits(box, pad=1)
            if hit:
                raise RuntimeError(f"overlap: {s!r} touches {hit[0]!r}")
        t = self.fig.text(x0 / self.W, y / self.H, s, fontproperties=fp, color=color, ha="left", va="bottom", zorder=z)
        if halo:
            t.set_path_effects([pe.withStroke(linewidth=2.6, foreground=halo)])
        self.ix.add(box, tag or f"text:{s[:30]}")
        return box

    def free(self, box, pad=2, ignore=()):
        return not self.ix.hits(box, pad=pad, ignore=ignore)

    def wrap_lines(self, s, fp, width):
        words, line, lines = s.split(), "", []
        for w in words:
            t = f"{line} {w}".strip()
            if self.measure(t, fp)[0] <= width or not line:
                line = t
            else:
                lines.append(line); line = w
        if line:
            lines.append(line)
        return lines

    def icon(self, name, x, y, size, color, z=66):
        art = ART[name].strip("\n").split("\n")
        n = len(art)
        px = size / n
        rects = [Rectangle((x + i * px, y + (n - 1 - j) * px), px * 1.02, px * 1.02)
                 for j, row in enumerate(art) for i, ch in enumerate(row) if ch in "#~"]
        self.fig.add_artist(PatchCollection(rects, facecolor=color, edgecolor="none", transform=ID, zorder=z))

    def swatch(self, name, x, y, size, fill, z=65, tag=None, register=True):
        pad = size * 0.14
        self.fig.add_artist(Rectangle((x, y), size, size, facecolor=fill, edgecolor=EDGE, linewidth=0.8, transform=ID, zorder=z))
        self.icon(name, x + pad, y + pad, size - 2 * pad, "#05060a", z=z + 1)
        if register:
            self.ix.add((x, y, x + size, y + size), tag or f"icon:{name}")


# --- voxel pillars ------------------------------------------------------------------------------------------
def shade(hex_, k):
    h = hex_.lstrip("#")
    r, g, b = (int(h[i:i + 2], 16) for i in (0, 2, 4))
    if k >= 1:
        return "#%02x%02x%02x" % tuple(int(c + (255 - c) * (k - 1)) for c in (r, g, b))
    return "#%02x%02x%02x" % tuple(int(c * k) for c in (r, g, b))


def pillar(x, y, a, n, color, hollow=False):
    hw, hh = a, a / 2
    top = y + n * a
    left = [(x - hw, y + hh), (x, y), (x, top), (x - hw, top + hh)]
    right = [(x, y), (x + hw, y + hh), (x + hw, top + hh), (x, top)]
    cap = [(x - hw, top + hh), (x, top), (x + hw, top + hh), (x, top + 2 * hh)]
    faces = ([(left, "#ffffff"), (right, "#f0eee8"), (cap, "#ffffff")] if hollow else
             [(left, shade(color, 1.0)), (right, shade(color, 0.72)), (cap, shade(color, 1.35))])
    seams = [[(x - hw, y + k * a + hh), (x, y + k * a), (x + hw, y + k * a + hh)] for k in range(1, n)]
    return faces, seams, (x - hw, y, x + hw, top + 2 * hh)


def levels(cap):
    return max(1, round(math.sqrt(max(cap, 1)) / 7.5))


def geoms(fc):
    for f in fc["features"]:
        g = f.get("geometry")
        if not g:
            continue
        t, c = g["type"], g["coordinates"]
        if t == "Polygon":
            yield "poly", c, f.get("properties", {})
        elif t == "MultiPolygon":
            for p in c:
                yield "poly", p, f.get("properties", {})
        elif t == "LineString":
            yield "line", c, f.get("properties", {})
        elif t == "MultiLineString":
            for l in c:
                yield "line", l, f.get("properties", {})


def countries(bbox, tol):
    """Natural Earth admin-0 clipped to the sheet and simplified; cached per sheet."""
    from shapely.geometry import shape, box as sbox, mapping
    cache = ROOT / "build" / f"poster_countries_{'_'.join(str(round(v, 1)) for v in bbox)}.json"
    if cache.exists():
        return json.load(open(cache))
    src = json.load(open(ROOT / "raw" / "geo" / "ne_10m_admin_0_countries.geojson"))
    clip = sbox(*bbox)
    out = []
    for f in src["features"]:
        pr = f["properties"]
        g = shape(f["geometry"])
        if not g.intersects(clip):
            continue
        g = g.intersection(clip).simplify(tol)
        if g.is_empty:
            continue
        out.append({"type": "Feature", "properties": {"name": pr.get("NAME") or pr.get("NAME_EN"), "iso": pr.get("ADM0_A3"),
                                                      "lx": pr.get("LABEL_X"), "ly": pr.get("LABEL_Y")},
                    "geometry": mapping(g)})
    fc = {"type": "FeatureCollection", "features": out}
    json.dump(fc, open(cache, "w"))
    return fc


def curve(p0, p1, bend=0.14, n=24):
    """Quadratic arc from p0 to p1 bowed to the left of travel, like old shipping-route maps."""
    (x0, y0), (x1, y1) = p0, p1
    mx, my = (x0 + x1) / 2, (y0 + y1) / 2
    dx, dy = x1 - x0, y1 - y0
    cx, cy = mx - dy * bend, my + dx * bend
    return [((1 - t) ** 2 * x0 + 2 * (1 - t) * t * cx + t * t * x1, (1 - t) ** 2 * y0 + 2 * (1 - t) * t * cy + t * t * y1)
            for t in (i / n for i in range(n + 1))]


def smooth(pts, n=6):
    """Catmull-Rom through waypoints (sea lanes arrive as hand-picked waypoints)."""
    if len(pts) < 3:
        return pts
    out = []
    Pp = [pts[0]] + pts + [pts[-1]]
    for i in range(1, len(Pp) - 2):
        p0, p1, p2, p3 = Pp[i - 1], Pp[i], Pp[i + 1], Pp[i + 2]
        for k in range(n):
            t = k / n
            out.append(tuple(0.5 * ((2 * p1[j]) + (-p0[j] + p2[j]) * t + (2 * p0[j] - 5 * p1[j] + 4 * p2[j] - p3[j]) * t * t +
                                    (-p0[j] + 3 * p1[j] - 3 * p2[j] + p3[j]) * t ** 3) for j in (0, 1)))
    out.append(pts[-1])
    return out


def arrow_at(S, pts, frac, size, color, z=24):
    """A filled arrowhead on the path at fraction frac of its length, pointing along travel."""
    L = [0]
    for a, b in zip(pts, pts[1:]):
        L.append(L[-1] + math.hypot(b[0] - a[0], b[1] - a[1]))
    tgt = L[-1] * frac
    for i in range(1, len(L)):
        if L[i] >= tgt:
            a, b = pts[i - 1], pts[i]
            f = (tgt - L[i - 1]) / ((L[i] - L[i - 1]) or 1)
            x, y = a[0] + (b[0] - a[0]) * f, a[1] + (b[1] - a[1]) * f
            ang = math.atan2(b[1] - a[1], b[0] - a[0])
            tip = (x + math.cos(ang) * size, y + math.sin(ang) * size)
            l = (x + math.cos(ang + 2.6) * size * 0.8, y + math.sin(ang + 2.6) * size * 0.8)
            r = (x + math.cos(ang - 2.6) * size * 0.8, y + math.sin(ang - 2.6) * size * 0.8)
            S.fig.add_artist(Polygon([tip, l, r], closed=True, facecolor=color, edgecolor="none", transform=ID, zorder=z))
            return (x, y, ang)
    return None


# --- data ---------------------------------------------------------------------------------------------------
def load():
    j = lambda p: json.load(open(p))
    derived = ROOT / "build" / "feedstock" / "derived_links.json"
    return (j(WEB / "data" / "plants.json")["plants"], j(WEB / "data" / "live" / "now.json"), j(WEB / "data" / "basemap.json"),
            j(WEB / "data" / "feed.json"), j(WEB / "data" / "grid" / "index.json"), j(derived) if derived.exists() else {"routes": []})


# --- one sheet ----------------------------------------------------------------------------------------------
def draw(which, dpi):
    plants, now, base, feed, grid, derived = load()
    tn = which == "tn"
    W_IN, H_IN = 20.0, 16.5
    S = Sheet(W_IN, H_IN, dpi)
    fig, W, H, pt = S.fig, S.W, S.H, S.pt
    M = 0.03 * W

    sel_all = [p for p in plants if (p.get("state") == "Tamil Nadu" if tn else True) and not p.get("part_of")]
    op = [p for p in sel_all if p.get("status") in (None, "operating")]

    # --- header -----------------------------------------------------------------------------------------
    gw = sum(p.get("cap") or 0 for p in op) / 1000
    kicker = (f"{' '.join('TAMIL NADU')}   /   {len(sel_all):,} STATIONS · {gw:,.1f} GW OPERATING" if tn else
              f"{' '.join('INDIA')}   /   {len(sel_all):,} POWER STATIONS · {gw:,.0f} GW OPERATING")
    kf = font(15)
    y = H * 0.975 - S.line_h(kf)
    S.text(M, y, kicker, kf, color=ACCENT, tag="header")
    head = ("Where Tamil Nadu's power is made, and how the fuel reaches it" if tn else
            "Where India's electricity is made, and how the fuel gets there")
    hf = font(32, "bold")
    y -= S.line_h(hf) * 1.08
    S.text(M, y, head, hf, tag="header")
    header_bottom = y - 8 * pt

    # --- map frame: full width, from under the header to above the cards ----------------------------------
    cards_top = H * 0.243
    ox, mw = M, W - 2 * M
    oy, mh = cards_top + 10 * pt, header_bottom - (cards_top + 10 * pt)
    lat0, lat1 = (7.45, 13.85) if tn else (5.4, 37.8)
    clon = 78.9 if tn else 82.0
    sc = mh / (lat1 - lat0)
    kx = math.cos(math.radians((lat0 + lat1) / 2))
    half = mw / (sc * kx) / 2
    lon0, lon1 = clon - half, clon + half
    bbox = (lon0, lat0, lon1, lat1)
    P = lambda lon, lat: (ox + (lon - lon0) * kx * sc, oy + (lat - lat0) * sc)
    inside = lambda x, y, m=0: ox + m <= x <= ox + mw - m and oy + m <= y <= oy + mh - m
    ax = fig.add_axes([ox / W, oy / H, mw / W, mh / H])
    ax.set_xlim(ox, ox + mw); ax.set_ylim(oy, oy + mh); ax.axis("off")
    ax.add_patch(Rectangle((ox, oy), mw, mh, facecolor=WATER, edgecolor="none", zorder=0))
    frame = (ox, oy, ox + mw, oy + mh)

    ctry = countries(bbox, 0.004 if tn else 0.02)
    ax.add_collection(PolyCollection([[P(*c) for c in ring[0]] for kind, ring, pr in geoms(ctry) if kind == "poly" and pr.get("iso") != "IND"],
                                     facecolor=LAND, edgecolor=BORDER, linewidth=0.7, zorder=1))
    # India from DataMeet (the Survey of India outline), drawn whole over Natural Earth's neighbours
    ax.add_collection(PolyCollection([[P(*c) for c in ring[0]] for kind, ring, _ in geoms(base["india"]) if kind == "poly"],
                                     facecolor=INDIA, edgecolor="#8f8a80", linewidth=0.9, zorder=2))
    ax.add_collection(PolyCollection([[P(*c) for c in ring[0]] for kind, ring, _ in geoms(base["lakes"]) if kind == "poly"],
                                     facecolor=WATER, edgecolor="none", zorder=3))
    ax.add_collection(LineCollection([[P(*c) for c in ln] for kind, ln, _ in geoms(base["states"]) if kind == "line"],
                                     colors=STATE, linewidths=0.7, zorder=4))

    for k in (["110", "220", "400", "hvdc", "765"] if tn else ["400", "hvdc", "765"]):
        f = grid["lines"].get(k)
        if not f:
            continue
        segs = [[P(*c) for c in ln] for kind, ln, _ in geoms(json.load(open(WEB / "data" / "grid" / f["file"])))
                if kind == "line" and any(lon0 <= c[0] <= lon1 and lat0 <= c[1] <= lat1 for c in ln)]
        col, lw = KV[k]
        ax.add_collection(LineCollection(segs, colors=col, linewidths=lw * (1.25 if tn else 0.85),
                                         alpha=(0.55 if k in ("110", "220") else 0.7) if tn else 0.45, zorder=6))
    if tn and grid.get("turbines"):
        pts = [P(p[0], p[1]) for p in json.load(open(WEB / "data" / "grid" / grid["turbines"]["file"]))]
        ax.scatter([x for x, _ in pts], [y for _, y in pts], s=0.35, c=FUEL["wind"], alpha=0.5, linewidths=0, zorder=7)

    # --- markers: nodes (mines, ports, gas) and station pillars, spread out where crowded --------------------
    a_big, a_small = (3.2 * pt, 1.7 * pt) if tn else (2.5 * pt, 1.25 * pt)
    node_px = 8.5 * pt if tn else 7 * pt
    items = []
    for n in feed["nodes"]:
        if n["kind"] in NODE:
            x, y = P(n["lon"], n["lat"])
            if inside(x, y, 4 * pt):
                items.append((100000, "node", n, (x, y)))
    for p in sel_all:
        x, y = P(p["lon"], p["lat"])
        if inside(x, y, 6 * pt):
            items.append((p.get("cap") or 0, "plant", p, (x, y)))

    def mbox(kind, obj, x, y):
        if kind == "node":
            return (x - node_px / 2, y - node_px / 2, x + node_px / 2, y + node_px / 2)
        cap = obj.get("cap") or 0
        a = a_big if cap >= 100 else a_small
        n_ = levels(cap) if cap >= 100 else 1
        return (x - a, y, x + a, y + n_ * a + a)

    # land mask in sheet pixels: a pillar or icon has to stand on land, never in the sea
    from PIL import Image, ImageDraw
    mask = Image.new("1", (int(W) + 1, int(H) + 1), 0)
    md = ImageDraw.Draw(mask)
    for src in (ctry, base["india"]):
        for kind, ring, _ in geoms(src):
            if kind == "poly" and len(ring[0]) > 2:
                md.polygon([(px_, H - py_) for px_, py_ in (P(*c) for c in ring[0])], fill=1)
    land_px = mask.load()

    def on_land(*pts_):
        return all(0 <= px_ < W and 0 <= py_ < H and land_px[int(px_), int(H - py_)] for px_, py_ in pts_)

    placed, dropped, moved = [], [], 0
    step = 2.5 * pt
    for pri, kind, obj, (x, y) in sorted(items, key=lambda t: -t[0]):
        big = kind == "node" or (obj.get("cap") or 0) >= 100
        max_r = (70 if big else 50) * pt
        step = (2.5 if big else 1.5) * pt
        spot, r = None, 0.0
        while r <= max_r and spot is None:
            ks = [0] if r == 0 else range(int(max(8, 2 * math.pi * r / ((3 if big else 2) * pt))))
            for k in ks:
                th = 0 if r == 0 else 2 * math.pi * k / len(ks)
                cx_, cy_ = x + r * math.cos(th), y + r * math.sin(th)
                b = mbox(kind, obj, cx_, cy_)
                if b[0] < ox + 2 * pt or b[2] > ox + mw - 2 * pt or b[1] < oy + 2 * pt or b[3] > oy + mh - 2 * pt:
                    continue
                foot = [(cx_, cy_)] if kind == "node" else [(cx_, cy_), (b[0], cy_ + (b[2] - b[0]) / 4), (b[2], cy_ + (b[2] - b[0]) / 4)]
                if on_land(*foot) and S.free(b, pad=(0.8 if big else 0.4) * pt):
                    spot = (cx_, cy_, b)
                    break
            r += step
        if spot is None:
            dropped.append(obj)
            continue
        cx_, cy_, b = spot
        S.ix.add(b, f"{kind}:{obj.get('id')}")
        if abs(cx_ - x) + abs(cy_ - y) > 1.5 * pt:
            moved += 1
        placed.append((kind, obj, (x, y), (cx_, cy_), b))
    pos_of = {obj.get("id"): (cx_, cy_, b) for kind, obj, _, (cx_, cy_), b in placed}

    # --- supply routes: under the markers; old-map style for the long hauls -----------------------------------
    route_labels = []
    rank = {"port": 0, "foreign_port": 0, "fuel_fabrication": 0}
    ends = [(n["lon"], n["lat"], n["name"], rank.get(n["kind"], 1)) for n in feed["nodes"]] + [(q["lon"], q["lat"], q["name"], 2) for q in plants]

    def end_name(c):
        """The port (before any berth or terminal inside it, before a station) at a route's end."""
        near = [e for e in ends if (e[0] - c[0]) ** 2 + (e[1] - c[1]) ** 2 < 0.05]
        return min(near, key=lambda e: (e[3], (e[0] - c[0]) ** 2 + (e[1] - c[1]) ** 2))[2] if near else None

    for r in feed["routes"]:
        cs = [P(*c) for c in r["coords"]]
        if not any(inside(*c) for c in cs):
            continue
        r = dict(r, from_name=end_name(r["coords"][0]), to_name=end_name(r["coords"][-1]))
        if r["mode"] == "air":
            path = curve(cs[0], cs[-1], bend=-0.12, n=40)
            ax.plot([q[0] for q in path], [q[1] for q in path], color=FUEL["nuclear"], linewidth=1.0, linestyle=(0, (4, 2, 1, 2)), alpha=0.9, zorder=8)
            if inside(*path[-1]):
                arrow_at(S, path, 0.97, 4 * pt, FUEL["nuclear"])
            route_labels.append((path, r))
        elif r["mode"] == "sea":
            path = smooth(cs)
            ax.plot([p[0] for p in path], [p[1] for p in path], color=SEA, linewidth=1.0, linestyle=(0, (1.2, 2.2)), alpha=0.9, zorder=8,
                    dash_capstyle="round")
            if inside(*path[-1]):
                arrow_at(S, path, 0.965, 4 * pt, SEA)
            route_labels.append((path, r))
        else:
            col = {"rail": RAIL, "pipeline": PIPE}.get(r["mode"], CONV)
            ls = {"rail": (0, (5, 2)), "pipeline": "solid"}.get(r["mode"], (0, (2, 2)))
            ax.plot([c[0] for c in cs], [c[1] for c in cs], color=col, linewidth=0.8 if tn else 0.65, linestyle=ls, alpha=0.8, zorder=8)
    for r in derived.get("routes", []):
        cs = [P(*c) for c in r["coords"]]
        if not all(inside(*c) for c in cs):
            continue
        pid = r["serves"][0] if r.get("serves") else None
        end = pos_of.get(pid, (cs[1][0], cs[1][1], None))[:2]      # to the pillar where it now stands
        path = curve(cs[0], end, bend=0.16 if r["mode"] == "rail" else 0.22)
        col = RAIL if r["mode"] == "rail" else SEA
        ls = (0, (5, 2)) if r["mode"] == "rail" else (0, (1.2, 2.2))
        ax.plot([p[0] for p in path], [p[1] for p in path], color=col, linewidth=0.7, linestyle=ls, alpha=0.75, zorder=8, dash_capstyle="round")
        arrow_at(S, path, 0.88, 3.2 * pt, col)
        if r["mode"] == "sea":
            route_labels.append((path, r))

    # draw the markers where they were placed
    faces, cols, edges, seams, leaders, dots = [], [], [], [], [], []
    for kind, obj, (x, y), (cx_, cy_), b in sorted(placed, key=lambda t: -t[3][1]):
        if abs(cx_ - x) + abs(cy_ - y) > 1.5 * pt:
            leaders.append([(x, y), (cx_, cy_)])
            dots.append((x, y))
        if kind == "node":
            ic, c = NODE[obj["kind"]]
            fig.add_artist(Rectangle((b[0], b[1]), node_px, node_px, facecolor="#ffffff", edgecolor=c, linewidth=1.1, transform=ID, zorder=20))
            S.icon(ic, b[0] + node_px * 0.13, b[1] + node_px * 0.13, node_px * 0.74, c, z=21)
            continue
        cap = obj.get("cap") or 0
        a = a_big if cap >= 100 else a_small
        n_ = levels(cap) if cap >= 100 else 1
        fc = FUEL.get(obj["type"], "#8a90a8")
        fs, ss, _ = pillar(cx_, cy_, a, n_, fc, obj.get("status") not in (None, "operating"))
        for poly, c in fs:
            faces.append(poly); cols.append(c); edges.append("#1b1d22" if cap >= 100 else shade(fc, 0.55))
        seams += ss
    fig.add_artist(LineCollection(leaders, colors="#5a564e", linewidths=0.45, transform=ID, zorder=18))
    if dots:
        fig.add_artist(PatchCollection([Rectangle((x - 0.7 * pt, y - 0.7 * pt), 1.4 * pt, 1.4 * pt) for x, y in dots],
                                       facecolor="#5a564e", edgecolor="none", transform=ID, zorder=19))
    fig.add_artist(PolyCollection(faces, facecolors=cols, edgecolors=edges, linewidths=0.35, transform=ID, zorder=30))
    fig.add_artist(LineCollection(seams, colors="#00000033", linewidths=0.35, transform=ID, zorder=31))

    # --- station labels: icon + full name (wrapped) + capacity, in a bubble sized to fit ----------------------
    f1, f2 = font(7.4 if tn else 7.0, "bold"), font(6.4 if tn else 6.1)
    isz = 8.2 * pt if tn else 7.6 * pt
    maxw = 118 * pt
    lh1, lh2 = S.line_h(f1), S.line_h(f2)
    cands = sorted([t for t in placed if t[0] == "plant" and t[1].get("status") in (None, "operating") and (t[1].get("cap") or 0) >= 100
                    and not re.match(r"^(solar|wind) plant \(", t[1]["name"], re.I)], key=lambda t: -(t[1].get("cap") or 0))
    n_lab, n_done = (48 if tn else 46), 0
    names = label_names([t[1] for t in cands])
    for kind, p, _, (cx_, cy_), b in cands:
        if n_done >= n_lab:
            break
        if not names.get(p["id"]):
            continue
        lines = S.wrap_lines(names[p["id"]], f1, maxw)
        sub = f"{fmt(p.get('cap'))} MW"
        tw = max(max(S.measure(l, f1)[0] for l in lines), S.measure(sub, f2)[0])
        bw = 2.5 * pt + isz + 4 * pt + tw + 4 * pt
        bh = max(isz, lh1 * len(lines) + lh2) + 5 * pt
        top = b[3]
        done = False
        for rr in (8, 16, 26, 38, 52, 68, 86, 108):
            for ang in (40, 140, 0, 180, 70, 110, -25, 205, 90, -60, 240, -90):
                dx, dy = math.cos(math.radians(ang)) * rr * pt, math.sin(math.radians(ang)) * rr * pt
                lx = cx_ + dx + (3 * pt if dx >= 0 else -bw - 3 * pt)
                ly = top + dy - (bh / 2 if abs(dy) < 1 else 0)
                box = (lx, ly, lx + bw, ly + bh)
                if not (frame[0] + 3 * pt < box[0] and box[2] < frame[2] - 3 * pt and frame[1] + 3 * pt < box[1] and box[3] < frame[3] - 3 * pt):
                    continue
                if not S.free(box, pad=1.5 * pt):
                    continue
                c = FUEL.get(p["type"], INK)
                fig.add_artist(Rectangle((lx, ly), bw, bh, facecolor="#fffffff2", edgecolor=c, linewidth=0.9, transform=ID, zorder=60))
                S.ix.add(box, f"label:{p['id']}")
                ix_ = lx + 2.5 * pt
                S.swatch(ICON[p["type"]], ix_, ly + bh - 2.5 * pt - isz, isz, c, z=62, register=False)
                tx, yy = ix_ + isz + 4 * pt, ly + bh - 2.5 * pt
                for l in lines:
                    yy -= lh1
                    fig.text(tx / W, yy / H, l, fontproperties=f1, color=INK, zorder=63)
                yy -= lh2
                fig.text(tx / W, yy / H, sub, fontproperties=f2, color=MUTED, zorder=63)
                ex, ey = min(max(cx_, lx), lx + bw), min(max(top, ly), ly + bh)
                fig.add_artist(LineCollection([[(cx_, top), (ex, ey)]], colors=INK, linewidths=0.55, transform=ID, zorder=59))
                n_done += 1
                done = True
                break
            if done:
                break

    # --- route labels "From → To", old-map italics, where they fit -------------------------------------------
    rl = font(6.4 if tn else 6.0, style="italic")
    seen = set()
    for path, r in route_labels:
        fr, to = place_name(r.get("from_name")), place_name(r.get("to_name"))
        to = names.get((r.get("serves") or [None])[0]) if r["mode"] == "air" else to
        if not fr or not to or fr == to:
            continue
        txt = f"{fr} → {to}"
        if txt in seen:
            continue
        seen.add(txt)
        w_, h_ = S.measure(txt, rl)
        placed_lab = False
        for frac in (0.5, 0.4, 0.6, 0.3, 0.7, 0.2, 0.8):
            x, y = path[int(frac * (len(path) - 1))]
            for off in (3, -3 - h_ / pt, 9, -9 - h_ / pt):
                box = (x - w_ / 2, y + off * pt, x + w_ / 2, y + off * pt + h_)
                if inside(box[0], box[1], 3 * pt) and inside(box[2], box[3], 3 * pt) and S.free(box, pad=1.5 * pt):
                    S.text(box[0], box[1], txt, rl, color=SEA_INK, tag="route label", halo=WATER)
                    placed_lab = True
                    break
            if placed_lab:
                break

    # --- country and sea names ---------------------------------------------------------------------------
    cn = font(8.5 if not tn else 9, "bold")
    for f in ctry["features"]:
        pr = f["properties"]
        if pr.get("iso") in ("IND", "KAS") or pr.get("lx") is None or "Glacier" in (pr.get("name") or ""):
            continue
        x, y = P(pr["lx"], pr["ly"])
        name = " ".join(pr["name"].upper())
        w_, h_ = S.measure(name, cn)
        for dy in (0, 12, -12, 24, -24):
            box = (x - w_ / 2, y + dy * pt - h_ / 2, x + w_ / 2, y + dy * pt + h_ / 2)
            if inside(box[0], box[1], 6 * pt) and inside(box[2], box[3], 6 * pt) and S.free(box, pad=3 * pt):
                S.text(box[0], box[1], name, cn, color="#9d978c", tag="country", halo=LAND)
                break
    seas = ([("Bay of Bengal", 81.4, 11.3), ("Gulf of Mannar", 79.0, 8.35), ("Palk Strait", 79.7, 9.95), ("Arabian Sea", 74.3, 9.2), ("Laccadive Sea", 75.8, 8.0)] if tn else
            [("Arabian Sea", 65.0, 15.0), ("Bay of Bengal", 88.5, 15.5), ("Indian Ocean", 80.0, 6.4), ("Andaman Sea", 96.5, 11.0)])
    sf = font(10 if tn else 11, style="italic")
    for name, lo, la in seas:
        x, y = P(lo, la)
        w_, h_ = S.measure(name, sf)
        for dy in (0, 14, -14, 28, -28, 42):
            box = (x - w_ / 2, y + dy * pt - h_ / 2, x + w_ / 2, y + dy * pt + h_ / 2)
            if inside(box[0], box[1], 4 * pt) and inside(box[2], box[3], 4 * pt) and S.free(box, pad=3 * pt):
                S.text(box[0], box[1], name, sf, color=SEA_INK, tag="sea", halo=WATER)
                break

    # --- cards ----------------------------------------------------------------------------------------------
    gap = 9 * pt
    cy0, cy1 = H * 0.058, cards_top
    ncard = 5
    cw = (W - 2 * M - (ncard - 1) * gap) / ncard
    X = [M + i * (cw + gap) for i in range(ncard)]
    pad = 8 * pt
    sw = 10 * pt

    class Flow:
        def __init__(self, x, top, w):
            self.x, self.y, self.w = x, top, w

        def line(self, s, fp, color=INK, right=None, gap_after=0.35):
            h = S.line_h(fp)
            S.text(self.x, self.y - h, s, fp, color=color)
            if right is not None:
                S.text(self.x + self.w, self.y - h, right, fp, ha="right")
            self.y -= h * (1 + gap_after)

        def para(self, s, fp, color=MUTED):
            h = S.line_h(fp) * 1.1
            for l in S.wrap_lines(s, fp, self.w):
                S.text(self.x, self.y - h, l, fp, color=color)
                self.y -= h
            self.y -= 2 * pt

        def space(self, pts):
            self.y -= pts * pt

        def icon_row(self, name, fill, label, value=None, fp=None):
            fp = fp or font(6.8)
            S.swatch(name, self.x, self.y - sw, sw, fill)
            th = S.line_h(fp)
            S.text(self.x + sw + 4 * pt, self.y - sw / 2 - th / 2, label, fp)
            if value is not None:
                S.text(self.x + self.w, self.y - sw / 2 - th / 2, value, font(fp.get_size_in_points(), "bold"), ha="right")
            self.y -= sw + 3 * pt

        def stack(self, vals):
            """One stacked bar, 1.5 px gaps between segments (like the site's mix bars)."""
            tv = sum(v for _, v in vals) or 1
            cur, bh = self.x, 7 * pt
            for c, v in vals:
                w = max(1.5 * pt, self.w * v / tv - 1.5)
                fig.add_artist(Rectangle((cur, self.y - bh), w, bh, facecolor=c, edgecolor="none", transform=ID, zorder=66))
                cur += w + 1.5
            S.ix.add((self.x, self.y - bh, self.x + self.w, self.y), "stack")
            self.y -= bh + 5 * pt

    flows = []

    def card(i, name):
        x = X[i]
        fig.add_artist(Rectangle((x + 6, cy0 - 6), cw, cy1 - cy0, facecolor="#00000022", edgecolor="none", transform=ID, zorder=44))
        fig.add_artist(Rectangle((x, cy0), cw, cy1 - cy0, facecolor=CARD, edgecolor=EDGE, linewidth=1.6, transform=ID, zorder=45))
        f = Flow(x + pad, cy1 - pad, cw - 2 * pad)
        f.line(name.upper(), font(9.5, "bold"), gap_after=0.8)
        flows.append((name, f))
        return f

    # 1 legend: stations
    f = card(0, "Legend: stations")
    f.line("Pillar height = installed capacity", font(6.8, "bold"), gap_after=0.4)
    top = f.y
    demo_x = f.x + a_big
    tallest = levels(4000) * a_big + 2 * a_big
    for cap, lbl in ((100, "100 MW"), (1000, "1 GW"), (4000, "4 GW")):
        fs, ss, bb = pillar(demo_x, top - tallest, a_big, levels(cap), "#8a90a8")
        fig.add_artist(PolyCollection([q[0] for q in fs], facecolors=[q[1] for q in fs], edgecolors="#1b1d22", linewidths=0.35, transform=ID, zorder=66))
        fig.add_artist(LineCollection(ss, colors="#00000033", linewidths=0.35, transform=ID, zorder=67))
        S.ix.add(bb, "demo")
        S.text(demo_x + a_big + 3 * pt, bb[1], lbl, font(6.2), color=MUTED)
        demo_x += f.w / 3
    f.y = top - tallest - 5 * pt
    fs, ss, bb = pillar(f.x + a_big, f.y - 3 * a_big, a_big, 2, "#8a90a8", hollow=True)
    fig.add_artist(PolyCollection([q[0] for q in fs], facecolors=[q[1] for q in fs], edgecolors="#1b1d22", linewidths=0.35, transform=ID, zorder=66))
    S.ix.add(bb, "demo")
    S.text(f.x + 3 * a_big, bb[1], "hollow = planned or being built", font(6.2), color=MUTED)
    f.y = bb[1] - 5 * pt
    ly_ = f.y - 4 * pt
    fig.add_artist(LineCollection([[(f.x + 2 * pt, ly_), (f.x + 12 * pt, ly_)]], colors="#5a564e", linewidths=0.6, transform=ID, zorder=66))
    fig.add_artist(Rectangle((f.x + 1.3 * pt, ly_ - 0.7 * pt), 1.4 * pt, 1.4 * pt, facecolor="#5a564e", edgecolor="none", transform=ID, zorder=66))
    f.x += 16 * pt; f.w -= 16 * pt
    f.para("moved apart where crowded; the dot marks the true spot", font(6.2))
    f.x -= 16 * pt; f.w += 16 * pt
    f.space(2)
    used = [t for t in ORDER if any(p["type"] == t for p in sel_all)]
    col_w = f.w / 2
    y0 = f.y
    th = S.line_h(font(6.4))
    for i, t in enumerate(used):
        cx_, cyy = f.x + (i % 2) * col_w, y0 - (i // 2) * (sw + 3 * pt)
        S.swatch(ICON[t], cx_, cyy - sw, sw, FUEL[t])
        S.text(cx_ + sw + 3 * pt, cyy - sw / 2 - th / 2, LABEL[t], font(6.4))
    f.y = y0 - ((len(used) + 1) // 2) * (sw + 3 * pt)

    # 2 legend: lines and fuel routes
    f = card(1, "Legend: grid and fuel")
    rows = [(KV["765"][0], "solid", 2.0, "765 kV line"), (KV["400"][0], "solid", 2.0, "400 kV line")]
    rows += ([(KV["220"][0], "solid", 2.0, "230 / 220 kV line"), (KV["110"][0], "solid", 2.0, "110 / 132 kV line")] if tn else [(KV["hvdc"][0], "solid", 2.0, "HVDC line")])
    rows += [(SEA, (0, (1.2, 2.2)), 1.4, "Coal or LNG by sea"), (RAIL, (0, (5, 2)), 1.4, "Coal by rail"), (PIPE, "solid", 1.4, "Gas pipeline"),
             (CONV, (0, (2, 2)), 1.4, "Conveyor or road"), (FUEL["nuclear"], (0, (4, 2, 1, 2)), 1.4, "Nuclear fuel by air")]
    rh = 10.2 * pt
    tf = font(6.6)
    for c, ls, lw, lbl in rows:
        yy = f.y - rh / 2
        fig.add_artist(LineCollection([[(f.x, yy), (f.x + 16 * pt, yy)]], colors=c, linewidths=lw, linestyles=[ls], transform=ID, zorder=66))
        S.text(f.x + 20 * pt, yy - S.line_h(tf) / 2, lbl, tf)
        f.y -= rh
    f.space(3)
    arc = curve((f.x, f.y - 9 * pt), (f.x + 22 * pt, f.y - 3 * pt), bend=0.3)
    fig.add_artist(LineCollection([arc], colors=SEA, linewidths=1.2, linestyles=[(0, (1.2, 2.2))], transform=ID, zorder=66))
    arrow_at(S, arc, 0.95, 3.5 * pt, SEA, z=67)
    S.ix.add((f.x, f.y - 11 * pt, f.x + 25 * pt, f.y), "legend arc")
    S.text(f.x + 28 * pt, f.y - 6 * pt - S.line_h(tf) / 2, "arrow = direction of haul; From → To", tf)
    f.y -= 14 * pt
    for ic, c, lbl in (("mine", "#9a5b00", "Mine or coalfield"), ("ship", SEA, "Port"), ("gas", PIPE, "Gas field or LNG terminal")):
        fig.add_artist(Rectangle((f.x, f.y - sw), sw, sw, facecolor="#ffffff", edgecolor=c, linewidth=1.1, transform=ID, zorder=66))
        S.icon(ic, f.x + sw * 0.13, f.y - sw * 0.87, sw * 0.74, c, z=67)
        S.ix.add((f.x, f.y - sw, f.x + sw, f.y), "legend node")
        S.text(f.x + sw + 4 * pt, f.y - sw / 2 - S.line_h(tf) / 2, lbl, tf)
        f.y -= sw + 3.5 * pt
    f.space(2)
    n_chain = len(feed.get("chains") or {})
    n_der = len([r for r in derived.get("routes", []) if r["mode"] == "rail"])
    f.para(f"Researched supply chains for {n_chain} stations (mine, rail junctions, port, ship, conveyor). "
           f"{n_der} more coal links from the company CEA names in its daily coal report; imported coal is drawn from the nearest coal port.", font(6.0))

    # 3 installed capacity: one stacked bar, then the rows
    f = card(2, "Installed capacity" + (", Tamil Nadu" if tn else ", India"))
    tot = {}
    for p in op:
        tot[p["type"]] = tot.get(p["type"], 0) + (p.get("cap") or 0)
    f.line(f"{sum(tot.values()) / 1000:,.1f} GW", font(20, "bold"), gap_after=0.15)
    f.para(f"operating, across {len(sel_all):,} mapped stations", font(6.4))
    ranked = sorted(tot.items(), key=lambda kv: -kv[1])
    f.stack([(FUEL[t], v) for t, v in ranked])
    for t, v in ranked[:10]:
        f.icon_row(ICON[t], FUEL[t], LABEL[t], f"{v / 1000:,.1f} GW" if v >= 1000 else f"{v:,.0f} MW")

    # 4 generation
    f = card(3, "Tamil Nadu supply" if tn else "Generation right now")
    if tn and now.get("tn"):
        r = now["tn"]["rows"]; v = now["tn"]["version"]
        vp = (now.get("vp") or {}).get("states", {}).get("Tamil Nadu") or {}
        f.line(f"{fmt(vp.get('mw') or r['total']['morning_mw'])} MW", font(20, "bold"), gap_after=0.15)
        f.para(f"demand met at {(vp.get('block') or '')[11:16]} IST on {(vp.get('block') or '')[:10]} (Vidyut Pravah)", font(6.2))
        mm = lambda *ks: sum((r.get(k) or {}).get("morning_mw") or 0 for k in ks)
        mix = [("coal", mm("thermal", "ipp_sepc", "ipp_taqa"), "Coal and lignite"), ("wind", mm("wind"), "Wind"), ("solar", mm("solar"), "Solar"),
               ("hydro", mm("hydro"), "Hydro"), ("gas", mm("gas", "ipp_ppn"), "Gas"), ("biomass", mm("cogen", "biomass"), "Cogen and biomass"),
               ("battery", mm("cgs"), "Central stations' share"), ("diesel", mm("ltoa", "mtoa_tnpdcl", "stoa", "remc"), "Bought in")]
        caption = f"Source mix at the SLDC morning peak, {v.get('morning_time')} on {v.get('morning_date')}:"
    else:
        m = now.get("merit") or {}
        L = m.get("latest") or {}
        f.line(f"{fmt((L.get('demand') or 0) / 1000, 1)} GW", font(20, "bold"), gap_after=0.15)
        t = datetime.fromisoformat(m["ts"]).astimezone(IST) if m.get("ts") else None
        f.para(f"India's demand at {t:%H:%M IST on %d %b %Y}" if t else "India's demand", font(6.2))
        mix = [("coal", L.get("thermal"), "Coal and lignite"), ("solar", L.get("solar"), "Solar"), ("wind", L.get("wind"), "Wind"),
               ("hydro", L.get("hydro"), "Hydro"), ("nuclear", L.get("nuclear"), "Nuclear"), ("gas", L.get("gas"), "Gas")]
        caption = "Generation at that moment (NPP merit chart, ~4-minute data):"
    f.para(caption, font(6.2))
    vals = [(k, v or 0, l) for k, v, l in mix if (v or 0) > 0]
    f.stack([(FUEL[k], v) for k, v, _ in vals])
    for k, v, l in vals:
        f.icon_row(ICON[k], FUEL[k], l, f"{v / 1000:,.1f} GW" if v >= 1000 else f"{v:,.0f} MW")
    if not tn and (now.get("merit") or {}).get("daily"):
        d = [x for x in now["merit"]["daily"] if x.get("demand")]
        if len(d) >= 2:
            last = d[-2]
            f.space(1)
            f.para(f"{last['date']}: {fmt(last['demand'])} MU met in the day; coal {fmt(last.get('thermal'))} MU, solar {fmt(last.get('solar'))} MU, "
                   f"wind {fmt(last.get('wind'))} MU, hydro {fmt(last.get('hydro'))} MU.", font(6.0))

    # 5 supply to consumers (no bars)
    f = card(4, "Supply to consumers")
    n = now.get("nfms") or {}
    stt = n.get("states") or {}
    one = stt.get("TN" if tn else "ALL") or {}
    f.line(f"{hrs(one.get('hrs_inc_ag'))} h a day", font(20, "bold"), gap_after=0.15)
    f.para(f"average supply, {'Tamil Nadu' if tn else 'India'}, all feeders (NFMS, {str(one.get('data_refresh') or '')[:10]})", font(6.2))
    for l, v in (("Urban feeders", one.get("urban")), ("Rural feeders", one.get("rural")), ("Farm feeders", one.get("agri"))):
        if v is not None:
            f.line(l, font(6.8), right=f"{hrs(v)} h", gap_after=0.45)
    f.space(2)
    if tn:
        city = [c for c in n.get("cities") or [] if c.get("state") == "Tamil Nadu"]
        ch_ = next((c for c in city if c["city"] == "Chennai"), None)
        if ch_:
            f.para(f"Chennai this month: {ch_['saidi']:.2f} h of interruption per consumer (SAIDI), {ch_['saifi']:.3f} interruptions (SAIFI).", font(6.4))
        coal = sorted([(p, now["plants"].get(p["id"], {})) for p in op if p["type"] in ("coal", "lignite")
                       and now["plants"].get(p["id"], {}).get("stock_pct") is not None], key=lambda pl: pl[1]["stock_pct"])
        crit = [p for p, l in coal if l.get("crit")]
        f.para(f"Coal in the yards: {len(coal)} stations reporting, {len(crit)} critical (under 25% of the normative stock).", font(6.4))
        f.line("Lowest coal stock, % of normative", font(6.4, "bold"), gap_after=0.3)
        for p_, l_ in coal[:5]:
            val = f"{l_['stock_pct']:.0f}%{' critical' if l_.get('crit') else ''}"
            vw = S.measure(val, font(6.4))[0] + 6 * pt
            for i, ln in enumerate(S.wrap_lines(clean_name(p_["name"]), font(6.4), f.w - vw)):
                f.line(ln, font(6.4, "bold" if l_.get("crit") else "normal"), right=val if i == 0 else None, gap_after=0.1)
            f.space(0.8)
    else:
        f.line("Fewest hours, all feeders", font(6.4, "bold"), gap_after=0.3)
        low = sorted([(k, v) for k, v in stt.items() if k != "ALL" and v.get("hrs_inc_ag") is not None], key=lambda kv: kv[1]["hrs_inc_ag"])[:6]
        for k, v in low:
            f.line(v["state"], font(6.6), right=f"{hrs(v['hrs_inc_ag'])} h", gap_after=0.2)
        f.space(2)
        fd = n.get("feeders") or {}
        f.para(f"{fmt(float(fd.get('totalIntegrated') or 0))} of {fmt(float(fd.get('totalFeeders') or 0))} feeders are metered "
               f"({fd.get('IntegrationPercent')}%). Farm feeders are rationed by design.", font(6.2))

    for name, f in flows:
        if f.y < cy0 + 3 * pt:
            raise RuntimeError(f"{which}: card overflow: {name!r} runs {cy0 + 3 * pt - f.y:.0f} px past its frame")

    # --- footer ----------------------------------------------------------------------------------------------
    built = datetime.now(IST)
    lines = [f"Rendered {built:%d %b %Y %H:%M} IST from power.reclaimchennai.city. Station positions checked against state boundaries, OpenStreetMap and the TN dossier;"
             " in crowded places pillars are moved apart and tied to their true spot.",
             "Sources: National Power Portal and CEA (stations, daily generation, merit chart, coal), TANTRANSCO SLDC, Vidyut Pravah and NFMS (Ministry of Power), TNPGCL, TNGECL,"
             " TN Environment Dept; supply chains from CEA coal statements, port and company records.",
             "Grid, plant footprints and wind turbines © OpenStreetMap contributors (ODbL). India and state boundaries: DataMeet (CC BY 4.0). Other countries: Natural Earth."]
    fy = H * 0.012
    ff = font(6.6)
    for ln in reversed(lines):
        S.text(M, fy, ln, ff, color=MUTED, tag="footer")
        fy += S.line_h(ff) * 1.3

    OUT.mkdir(parents=True, exist_ok=True)
    out = OUT / f"power_{which}_en.png"
    fig.savefig(out, dpi=dpi, facecolor=PAPER)
    plt.close(fig)
    from PIL import Image
    im = Image.open(out)
    im.thumbnail((2000, 1650))
    im.convert("RGB").save(OUT / f"power_{which}_en_preview.jpg", quality=86)
    kinds = {}
    for d in dropped:
        kinds[d.get("type", d.get("kind", "?"))] = kinds.get(d.get("type", d.get("kind", "?")), 0) + 1
    print(f"{out}  {out.stat().st_size / 1e6:.1f} MB · {len(placed)} markers ({moved} moved apart) · could not fit: {kinds or 'none'} · {n_done} labels")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", choices=["india", "tn"])
    ap.add_argument("--dpi", type=int, default=300)
    a = ap.parse_args()
    for w in ([a.only] if a.only else ["india", "tn"]):
        draw(w, a.dpi)


if __name__ == "__main__":
    main()
