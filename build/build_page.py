#!/usr/bin/env python3
"""
Generate the chart page from the scanned photo data.

Reads _scan.json, _panels/panels.json and _web/manifest.json; writes a single
self-contained HTML file with the data baked in, plus a publish_files.json
listing every image that has to be published alongside it.

Rerun after adding photos or labels - it is the whole build.

Usage:  python3 build_page.py ~/Desktop/dad-map/_work <out.html>
"""

import json
import math
import os
import sys
import unicodedata
from collections import Counter

CLUSTER_KM = 25

# Nominatim returns administrative names that read like a database, not a place
# anyone says out loud. Only unambiguous corrections belong here - everything
# else is Nick's to rename in the page's edit mode.
NAME_OVERRIDES = {
    "Area A (Upper Flathead/Elk Valley)": "Elk Valley",
    "Th\u00e0nh ph\u1ed1 \u0110\u00e0 N\u1eb5ng": "\u0110\u00e0 N\u1eb5ng",
}


def km_between(a, b):
    R = 6371.0
    t = math.pi / 180
    dla = (b[0] - a[0]) * t
    dlo = (b[1] - a[1]) * t
    h = (math.sin(dla / 2) ** 2 +
         math.cos(a[0] * t) * math.cos(b[0] * t) * math.sin(dlo / 2) ** 2)
    return 2 * R * math.asin(math.sqrt(h))


def slug(text):
    norm = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    out = "".join(c.lower() if c.isalnum() else "_" for c in norm)
    return "_".join(p for p in out.split("_") if p)[:24] or "place"


def build_waypoints(rows):
    located = [r for r in rows if r.get("lat") is not None]
    clusters = []
    for r in sorted(located, key=lambda x: x.get("date") or ""):
        pt = (r["lat"], r["lng"])
        for c in clusters:
            if km_between(pt, c["center"]) < CLUSTER_KM:
                c["rows"].append(r)
                n = len(c["rows"])
                c["center"] = (sum(x["lat"] for x in c["rows"]) / n,
                               sum(x["lng"] for x in c["rows"]) / n)
                break
        else:
            clusters.append({"center": pt, "rows": [r]})

    waypoints = []
    for c in clusters:
        names = Counter((x.get("place") or "").split(",")[0].strip()
                        for x in c["rows"] if x.get("place"))
        # prefer a real town name over the vague state-level fallbacks
        vague = {"California", "Colorado", "", "?"}
        ranked = sorted(names, key=lambda k: (k in vague, -names[k]))
        label = ranked[0] if ranked else "Unnamed place"
        label = NAME_OVERRIDES.get(label, label)
        region = ""
        for x in c["rows"]:
            parts = [p.strip() for p in (x.get("place") or "").split(",")]
            if len(parts) > 1:
                region = ", ".join(parts[1:])
                break
        years = sorted({x["year"] for x in c["rows"] if x.get("year")})
        waypoints.append({
            "id": "wp_" + slug(label),
            "name": label,
            "region": region,
            "lat": round(c["center"][0], 6),
            "lng": round(c["center"][1], 6),
            "years": years,
            "story": "",
            "files": [x["file"] for x in sorted(c["rows"], key=lambda r: r.get("date") or "")],
        })

    # earliest first, so the index reads as a chronology
    waypoints.sort(key=lambda w: (w["years"][0] if w["years"] else 9999, w["name"]))
    seen = {}
    for w in waypoints:                      # guarantee unique ids
        if w["id"] in seen:
            seen[w["id"]] += 1
            w["id"] = "%s_%d" % (w["id"], seen[w["id"]])
        else:
            seen[w["id"]] = 1
    return waypoints


def collect_data(work, writing):
    """Build using only repository sources; the raw work directory is not needed."""
    from pathlib import Path
    import hashlib
    root = Path(__file__).resolve().parent.parent
    writing = Path(writing)
    read = lambda path: json.loads(path.read_text(encoding="utf-8"))
    catalog = read(root / "content/catalog.json")
    edits = {name: read(writing / (name + ".json")) for name in ("meta", "waypoints", "photos", "places")}
    data = {"meta": edits["meta"], "edits": edits, "journey": read(writing / "journey.json"),
            "panels": catalog["panels"], "waypoints": catalog["waypoints"],
            "photos": catalog["photos"], "unplaced": catalog["unplaced"]}
    data["version"] = hashlib.sha256(json.dumps(data, sort_keys=True).encode()).hexdigest()[:12]
    validate_data(data)
    paths = [p["src"] for p in data["panels"]]
    paths += [p[size] for p in data["photos"].values() for size in ("thumb", "full")]
    assets = {}
    for relative in paths:
        if relative.startswith("/") or ".." in Path(relative).parts:
            raise ValueError("Unsafe asset path: " + relative)
        source = root / "assets" / relative
        if not source.is_file(): raise ValueError("Missing web asset: " + relative)
        assets[relative] = source
    return data, assets


def collect_scanned_data(work, writing):
    """Build the independent gift from media metadata and the authored snapshot."""
    from pathlib import Path
    import hashlib
    work, writing = Path(work), Path(writing)
    read = lambda path: json.loads(path.read_text(encoding="utf-8"))
    rows = read(work / "_scan.json")
    panels = read(work / "_panels/panels.json")
    manifest = read(work / "_web/manifest.json")
    edits = {name: read(writing / (name + ".json")) for name in ("meta", "waypoints", "photos", "places")}
    journey = read(writing / "journey.json")
    photos = {}
    for r in rows:
        m = manifest.get(r["file"])
        if m:
            photos[r["file"]] = {k: m[k] for k in ("thumb", "full", "w", "h")}
            photos[r["file"]].update(year=r.get("year"), date=r.get("date"), caption="", approx=r.get("source") == "inferred-by-date")
    waypoints = build_waypoints(rows)
    for w in waypoints:
        w["files"] = [f for f in w["files"] if f in photos]
    waypoints = [w for w in waypoints if w["files"]]
    for p in panels:
        p["src"] = "panels/" + p["file"]
        if p["title"] == "Thành phố Đà Nẵng": p["title"] = "Đà Nẵng"
    data = {"meta": edits["meta"], "edits": edits, "journey": journey, "panels": panels,
            "waypoints": waypoints, "photos": photos,
            "unplaced": [r["file"] for r in rows if r.get("lat") is None and r["file"] in photos]}
    data["version"] = hashlib.sha256(json.dumps(data, sort_keys=True).encode()).hexdigest()[:12]
    validate_data(data)
    assets = {p["src"]: work / "_panels" / p["file"] for p in panels}
    for f, photo in photos.items():
        m = manifest[f]
        for size in ("thumb", "full"):
            assets[photo[size]] = work / "_web" / size / (m["key"] + ".jpg")
    for dest, src in assets.items():
        if dest.startswith("/") or ".." in Path(dest).parts:
            raise ValueError("Unsafe asset path: " + dest)
        if not src.is_file(): raise ValueError("Missing image: " + str(src))
    return data, assets


def validate_data(data):
    photos, edits = data["photos"], data["edits"]
    ids = {w["id"] for w in data["waypoints"]} | set(edits["places"])
    if len({w["id"] for w in data["waypoints"]}) != len(data["waypoints"]):
        raise ValueError("Duplicate place identifiers")
    for file, p in edits["photos"].items():
        if file not in photos: raise ValueError("Writing references an unknown photo: " + file)
        if p.get("waypoint") and p["waypoint"] not in ids: raise ValueError("Unknown place: " + p["waypoint"])
        year = p.get("year")
        if year is not None and (type(year) is not int or not 1900 <= year <= 2100): raise ValueError("Invalid year for " + file)
    for id, w in edits["places"].items():
        if not w.get("name") or not -85 <= w["lat"] <= 85 or not -180 <= w["lng"] <= 180: raise ValueError("Invalid place: " + id)
    for id, w in edits["waypoints"].items():
        if id not in ids: raise ValueError("Unknown edited place: " + id)
        if w.get("cover"):
            file=w["cover"]
            if file not in photos: raise ValueError("Unknown cover: " + file)
            assigned=edits["photos"].get(file,{}).get("waypoint")
            if assigned is None:
                assigned=next((base["id"] for base in data["waypoints"] if file in base["files"]),None)
            if assigned != id: raise ValueError("Cover is assigned to another place: " + file)
    for file in [data["journey"]["hero"]] + [s["file"] for s in data["journey"]["stops"]]:
        if file not in photos: raise ValueError("Unknown journey photograph: " + file)
    if not data["journey"]["stops"]: raise ValueError("The journey needs at least one memory")


def render_page(data):
    from pathlib import Path
    here = Path(__file__).resolve().parent
    template = (here / "page_template.html").read_text(encoding="utf-8")
    payload = json.dumps(data, ensure_ascii=True, separators=(",", ":")).replace("<", "\\u003c")
    for token, content in [("/*__DATA__*/null", payload), ("/*__STYLE__*/", (here / "web/style.css").read_text()),
                           ("/*__CORE__*/", (here / "web/core.js").read_text()), ("/*__MAP__*/", (here / "web/map.js").read_text()), ("/*__APP__*/", (here / "web/app.js").read_text())]:
        template = template.replace(token, content)
    return template


def main():
    from pathlib import Path
    if len(sys.argv) < 3: sys.exit("usage: build_page.py <work_dir> <out.html> [writing_dir]")
    work = Path(sys.argv[1]).expanduser()
    writing = Path(sys.argv[3]).expanduser() if len(sys.argv) > 3 else work.parent / "your-writing"
    data, assets = collect_data(work, writing)
    Path(sys.argv[2]).write_text(render_page(data), encoding="utf-8")
    (work / "publish_files.json").write_text(json.dumps({k: str(v.resolve()) for k,v in assets.items()}, indent=2))
    print("Built %d photographs and %d journey stops." % (len(data["photos"]), len(data["journey"]["stops"])))


if __name__ == "__main__":
    main()
