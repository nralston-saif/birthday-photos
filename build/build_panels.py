#!/usr/bin/env python3
"""
Build real map backdrops for the chart.

Artifact pages can't fetch map tiles at runtime (blocked by CSP), so we fetch
and stitch them here and ship the result as an image. Pin placement on the page
uses the same Web Mercator math, so pins land exactly where they belong.

Clusters the waypoints, then emits:
  - one MAIN panel covering everything inside the main landmass, and
  - an INSET panel per dense or far-flung cluster (the way a real chart carries
    inset detail for a harbour it can't show at the main scale)

Writes panels/<id>.jpg plus panels.json with each panel's exact geographic
bounds, which the page needs to project pins onto it.

Usage:  python3 build_panels.py ~/Desktop/dad-map/_work [out_dir]
"""

import io
import json
import math
import os
import sys
import time
import unicodedata
import urllib.error
import urllib.request

from PIL import Image

# Carto's basemaps now watermark every tile unless you hold an API key.
# OSM's own tiles are free for modest use; we restyle them below into the
# chart palette, which also stops the map looking like a stock basemap.
TILE_URL = "https://tile.openstreetmap.org/{z}/{x}/{y}.png"
UA = "chart-of-a-life/1.0 (personal family map; contact nick@saif.vc)"
TILE_PX = 256
TARGET_PX = 1400          # stitched panel width before downscale
MAX_ZOOM = 16
MIN_ZOOM = 2
CLUSTER_KM = 25           # waypoints closer than this share a cluster
INSET_TRIGGER_KM = 400    # a cluster this far from the main body gets its own inset


# ---------- mercator ----------

def lon_to_x(lon, z):
    return (lon + 180.0) / 360.0 * (2 ** z)


def lat_to_y(lat, z):
    lat = max(-85.05112878, min(85.05112878, lat))
    r = math.radians(lat)
    return (1.0 - math.log(math.tan(r) + 1.0 / math.cos(r)) / math.pi) / 2.0 * (2 ** z)


def km_between(a, b):
    R = 6371.0
    t = math.pi / 180
    dla = (b[0] - a[0]) * t
    dlo = (b[1] - a[1]) * t
    h = (math.sin(dla / 2) ** 2 +
         math.cos(a[0] * t) * math.cos(b[0] * t) * math.sin(dlo / 2) ** 2)
    return 2 * R * math.asin(math.sqrt(h))


# ---------- clustering ----------

def slug(text):
    """ASCII-safe id for a filename. Đà Nẵng -> da_nang."""
    norm = unicodedata.normalize("NFKD", text)
    norm = norm.encode("ascii", "ignore").decode("ascii")
    out = "".join(ch.lower() if ch.isalnum() else "_" for ch in norm)
    out = "_".join(part for part in out.split("_") if part)
    return out[:20] or "panel"


def cluster(points, radius_km):
    clusters = []
    for p in points:
        pt = (p["lat"], p["lng"])
        for c in clusters:
            if km_between(pt, c["center"]) < radius_km:
                c["points"].append(p)
                n = len(c["points"])
                c["center"] = (sum(x["lat"] for x in c["points"]) / n,
                               sum(x["lng"] for x in c["points"]) / n)
                break
        else:
            clusters.append({"center": pt, "points": [p]})
    return clusters


# ---------- tiles ----------

_cache = {}


def fetch_tile(z, x, y, retina=False):
    key = (z, x, y, retina)
    if key in _cache:
        return _cache[key]
    url = TILE_URL.format(z=z, x=x, y=y)
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=20) as resp:
                img = Image.open(io.BytesIO(resp.read())).convert("RGB")
            _cache[key] = img
            time.sleep(0.12)          # be a polite client
            return img
        except (urllib.error.URLError, OSError):
            if attempt == 2:
                blank = Image.new("RGB", (TILE_PX * (2 if retina else 1),) * 2,
                                  (238, 240, 236))
                _cache[key] = blank
                return blank
            time.sleep(0.6 * (attempt + 1))


def choose_zoom(west, south, east, north, target_px=TARGET_PX, max_zoom=MAX_ZOOM):
    for z in range(max_zoom, MIN_ZOOM - 1, -1):
        width = (lon_to_x(east, z) - lon_to_x(west, z)) * TILE_PX
        height = (lat_to_y(south, z) - lat_to_y(north, z)) * TILE_PX
        if width <= target_px * 1.35 and height <= target_px * 1.35:
            return z
    return MIN_ZOOM


def chart_treatment(img):
    """Restyle a stock basemap into the chart's palette.

    Desaturate hard, lift the whites so the sheet reads as paper, then tint
    the midtones toward the chart's slate-blue ink. Keeps roads and coastlines
    legible while killing the tourist-map green and tan.
    """
    from PIL import ImageEnhance, ImageOps

    grey = ImageOps.grayscale(img)
    grey = ImageOps.autocontrast(grey, cutoff=1)
    # duotone: paper white -> slate ink, not pure black
    tinted = ImageOps.colorize(grey, black=(74, 92, 108), white=(240, 241, 236))
    tinted = ImageEnhance.Contrast(tinted).enhance(0.92)
    # fold a little of the original colour back so water still reads as water
    return Image.blend(tinted, img.convert("RGB"), 0.13)


def stitch(west, south, east, north, zoom):
    """Stitch whole tiles covering the box, then crop to the exact bounds."""
    retina = False
    px = TILE_PX

    x0f, x1f = lon_to_x(west, zoom), lon_to_x(east, zoom)
    y0f, y1f = lat_to_y(north, zoom), lat_to_y(south, zoom)
    x0, x1 = int(math.floor(x0f)), int(math.ceil(x1f))
    y0, y1 = int(math.floor(y0f)), int(math.ceil(y1f))

    n = 2 ** zoom
    cols, rows = x1 - x0, y1 - y0
    if cols * rows > 420:                      # guard against an absurd fetch
        raise RuntimeError("tile count %d too large at z%d" % (cols * rows, zoom))

    canvas = Image.new("RGB", (cols * px, rows * px), (238, 240, 236))
    for xi in range(x0, x1):
        for yi in range(y0, y1):
            tile = fetch_tile(zoom, xi % n, max(0, min(n - 1, yi)), retina)
            if tile.size != (px, px):
                tile = tile.resize((px, px), Image.LANCZOS)
            canvas.paste(tile, ((xi - x0) * px, (yi - y0) * px))

    left = int((x0f - x0) * px)
    top = int((y0f - y0) * px)
    right = int((x1f - x0) * px)
    bottom = int((y1f - y0) * px)
    cropped = canvas.crop((left, top, max(right, left + 1), max(bottom, top + 1)))
    return chart_treatment(cropped)


def pad_bounds(points, pad_frac=0.28, min_span_deg=0.02):
    lats = [p["lat"] for p in points]
    lngs = [p["lng"] for p in points]
    south, north = min(lats), max(lats)
    west, east = min(lngs), max(lngs)

    dlat = max(north - south, min_span_deg)
    dlng = max(east - west, min_span_deg)
    south -= dlat * pad_frac
    north += dlat * pad_frac
    west -= dlng * pad_frac
    east += dlng * pad_frac
    return (max(-85, south), min(85, north), max(-180, west), min(180, east))


def main():
    if len(sys.argv) < 2:
        sys.exit("usage: build_panels.py <work_dir> [out_dir]")
    work = os.path.expanduser(sys.argv[1])
    out_dir = os.path.expanduser(sys.argv[2]) if len(sys.argv) > 2 \
        else os.path.join(work, "_panels")
    os.makedirs(out_dir, exist_ok=True)

    with open(os.path.join(work, "_scan.json"), "r", encoding="utf-8") as fh:
        rows = json.load(fh)
    located = [r for r in rows if r.get("lat") is not None]
    if not located:
        sys.exit("no located photos in _scan.json")

    groups = cluster(located, CLUSTER_KM)
    groups.sort(key=lambda c: -len(c["points"]))
    print("%d waypoint clusters" % len(groups))

    # The main panel covers the biggest body of clusters; anything far away
    # from that body becomes its own inset.
    anchor = groups[0]["center"]
    main_groups, far_groups = [], []
    for g in groups:
        (main_groups if km_between(g["center"], anchor) <= 3000 else far_groups).append(g)

    panels = []

    def emit(pid, title, pts, kind, pad=0.28):
        # A single waypoint has no extent at all, so the box would collapse to
        # a few hundred pixels and upscale badly. Give sparse clusters a real
        # span - roughly a city's worth of ground.
        min_span = 0.25 if len(pts) <= 2 else 0.02
        south, north, west, east = pad_bounds(pts, pad, min_span)
        target_px = TARGET_PX
        if pid == "world":
            # The whole globe, so anything searched for lands somewhere on it,
            # and at a resolution that stands being zoomed into rather than a
            # 1400px strip magnified into mush.
            west, east = -180.0, 180.0
            north, south = 79.0, -58.0
            target_px = 4200
        # A one- or two-photo cluster has almost no extent, so the fitter would
        # pick maximum zoom and show a city block with no context. Cap it.
        cap = 13 if len(pts) <= 2 else MAX_ZOOM
        if pid == "world":
            cap = 4
        zoom = choose_zoom(west, south, east, north, target_px, max_zoom=cap)
        print("  %-14s %-26s z%-3d %d pts" % (pid, title[:26], zoom, len(pts)))
        img = stitch(west, south, east, north, zoom)
        if img.width > target_px:
            ratio = target_px / float(img.width)
            img = img.resize((target_px, max(1, int(img.height * ratio))), Image.LANCZOS)
        path = os.path.join(out_dir, "%s.jpg" % pid)
        img.save(path, quality=86, optimize=True, progressive=True)
        panels.append({
            "id": pid, "title": title, "kind": kind,
            "west": west, "east": east, "south": south, "north": north,
            "zoom": zoom, "file": "%s.jpg" % pid,
            "w": img.width, "h": img.height,
            "count": sum(len(p.get("_files", [1])) for p in pts),
        })

    all_pts = [p for g in groups for p in g["points"]]
    lng_span = max(p["lng"] for p in all_pts) - min(p["lng"] for p in all_pts)
    if lng_span > 60 or far_groups:
        # everything on one sheet, so the whole reach of it reads at a glance
        emit("world", "The World", all_pts, "main", pad=0.14)

    all_main_pts = [p for g in main_groups for p in g["points"]]
    emit("main", "The West", all_main_pts, "main" if lng_span <= 60 else "inset", pad=0.22)

    # Dense clusters earn a detail inset; distant ones need their own sheet.
    for g in main_groups:
        if len(g["points"]) >= 6:
            label = (g["points"][0].get("place") or "Detail").split(",")[0]
            pid = "inset_" + slug(label)
            emit(pid, label, g["points"], "inset", pad=0.45)

    for g in far_groups:
        label = (g["points"][0].get("place") or "Elsewhere").split(",")[0]
        pid = "inset_" + slug(label)
        emit(pid, label, g["points"], "inset", pad=0.5)

    with open(os.path.join(out_dir, "panels.json"), "w", encoding="utf-8") as fh:
        json.dump(panels, fh, indent=2)

    total = sum(os.path.getsize(os.path.join(out_dir, p["file"])) for p in panels)
    print("\n%d panels, %.1f MB total -> %s" % (len(panels), total / 1e6, out_dir))


if __name__ == "__main__":
    main()
