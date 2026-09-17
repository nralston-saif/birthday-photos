#!/usr/bin/env python3
"""
Scan a folder of photos for date + location, three ways, best source first:

  1. Google Takeout JSON sidecar  (richest - includes locations Google inferred
     from Location History, which never appear in the file's own EXIF)
  2. EXIF GPS via Pillow          (what the camera itself stamped)
  3. macOS `mdls`                 (Spotlight's index - reads HEIC, which this
     Pillow build cannot)

Then reverse-geocodes whatever it found and prints a coverage report, so we
know immediately which places are free and which ones Nick has to supply.

Usage:  python3 scan_photos.py ~/Desktop/dad-map
"""

import json
import os
import subprocess
import sys
import time
import urllib.parse
import urllib.request
from datetime import datetime

IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".heic", ".heif", ".tif", ".tiff", ".webp"}


# ---------- source 1: Google Takeout sidecar ----------

def from_takeout_sidecar(path):
    """Takeout names sidecars inconsistently; try the known patterns."""
    base = os.path.basename(path)
    stem, _ = os.path.splitext(base)
    folder = os.path.dirname(path)
    candidates = [
        path + ".json",
        path + ".supplemental-metadata.json",
        os.path.join(folder, stem + ".json"),
    ]
    for cand in candidates:
        if not os.path.exists(cand):
            continue
        try:
            with open(cand, "r", encoding="utf-8") as fh:
                meta = json.load(fh)
        except (OSError, ValueError):
            continue

        lat = lng = None
        # geoDataExif is the camera's; geoData is Google's, which may be richer.
        for key in ("geoData", "geoDataExif"):
            geo = meta.get(key) or {}
            if geo.get("latitude") or geo.get("longitude"):
                lat, lng = geo.get("latitude"), geo.get("longitude")
                break

        taken = None
        ts = (meta.get("photoTakenTime") or {}).get("timestamp")
        if ts:
            try:
                taken = datetime.fromtimestamp(int(ts))
            except (ValueError, OSError):
                pass

        if lat or taken:
            return lat, lng, taken, "takeout"
    return None, None, None, None


# ---------- source 2: EXIF via Pillow ----------

def _ratio(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        try:
            return v[0] / v[1]
        except Exception:
            return None


def _dms_to_decimal(dms, ref):
    parts = [_ratio(x) for x in dms]
    if any(p is None for p in parts):
        return None
    deg, minutes, seconds = parts
    dec = deg + minutes / 60.0 + seconds / 3600.0
    if ref in ("S", "W"):
        dec = -dec
    return dec


def from_exif(path):
    try:
        from PIL import Image
        from PIL.ExifTags import GPSTAGS, TAGS
    except ImportError:
        return None, None, None, None

    try:
        with Image.open(path) as img:
            raw = img._getexif()
    except Exception:
        return None, None, None, None
    if not raw:
        return None, None, None, None

    tags = {TAGS.get(k, k): v for k, v in raw.items()}

    taken = None
    for key in ("DateTimeOriginal", "DateTimeDigitized", "DateTime"):
        if tags.get(key):
            try:
                taken = datetime.strptime(str(tags[key]), "%Y:%m:%d %H:%M:%S")
                break
            except ValueError:
                pass

    lat = lng = None
    gps_raw = tags.get("GPSInfo")
    if gps_raw:
        gps = {GPSTAGS.get(k, k): v for k, v in gps_raw.items()}
        if gps.get("GPSLatitude") and gps.get("GPSLongitude"):
            lat = _dms_to_decimal(gps["GPSLatitude"], gps.get("GPSLatitudeRef", "N"))
            lng = _dms_to_decimal(gps["GPSLongitude"], gps.get("GPSLongitudeRef", "E"))

    if lat or taken:
        return lat, lng, taken, "exif"
    return None, None, None, None


# ---------- source 3: macOS Spotlight (handles HEIC) ----------

def from_mdls(path):
    if sys.platform != "darwin":
        return None, None, None, None
    try:
        out = subprocess.run(
            ["mdls", "-name", "kMDItemLatitude", "-name", "kMDItemLongitude",
             "-name", "kMDItemContentCreationDate", path],
            capture_output=True, text=True, timeout=10,
        ).stdout
    except (OSError, subprocess.SubprocessError):
        return None, None, None, None

    vals = {}
    for line in out.splitlines():
        if "=" not in line:
            continue
        key, _, val = line.partition("=")
        val = val.strip()
        if val and val != "(null)":
            vals[key.strip()] = val

    lat = lng = taken = None
    try:
        if "kMDItemLatitude" in vals:
            lat = float(vals["kMDItemLatitude"])
            lng = float(vals["kMDItemLongitude"])
    except (ValueError, KeyError):
        lat = lng = None
    if "kMDItemContentCreationDate" in vals:
        try:
            taken = datetime.strptime(
                vals["kMDItemContentCreationDate"][:19], "%Y-%m-%d %H:%M:%S")
        except ValueError:
            pass

    if lat or taken:
        return lat, lng, taken, "mdls"
    return None, None, None, None


# ---------- reverse geocoding ----------

def reverse_geocode(lat, lng):
    """Nominatim asks for <=1 request/sec and a real User-Agent. Respect both."""
    url = ("https://nominatim.openstreetmap.org/reverse?format=json"
           "&lat=%s&lon=%s&zoom=14" % (lat, lng))
    req = urllib.request.Request(url, headers={"User-Agent": "chart-of-a-life/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.load(resp)
    except Exception:
        return None
    addr = data.get("address") or {}
    bits = [
        addr.get("city") or addr.get("town") or addr.get("village")
        or addr.get("hamlet") or addr.get("suburb"),
        addr.get("state"),
        addr.get("country"),
    ]
    return ", ".join(b for b in bits if b) or data.get("display_name")


# ---------- main ----------

def main():
    if len(sys.argv) < 2:
        sys.exit("usage: scan_photos.py <folder>")
    folder = os.path.expanduser(sys.argv[1])
    if not os.path.isdir(folder):
        sys.exit("not a folder: %s" % folder)

    files = []
    for root, dirs, names in os.walk(folder):
        # never scan our own generated output back in as source photos
        dirs[:] = [d for d in dirs if not d.startswith("_")]
        for name in sorted(names):
            if name.startswith("."):
                continue
            if os.path.splitext(name)[1].lower() in IMAGE_EXTS:
                files.append(os.path.join(root, name))

    if not files:
        sys.exit("no images found under %s" % folder)

    rows = []
    for path in files:
        for extractor in (from_takeout_sidecar, from_exif, from_mdls):
            lat, lng, taken, source = extractor(path)
            if lat is not None or taken is not None:
                break
        rows.append({
            "file": os.path.relpath(path, folder),
            "lat": lat, "lng": lng,
            "date": taken.isoformat() if taken else None,
            "year": taken.year if taken else None,
            "source": source,
            "place": None,
        })

    located = [r for r in rows if r["lat"] is not None]
    print("scanned %d photos - %d with location, %d with a date\n"
          % (len(rows), len(located), sum(1 for r in rows if r["year"])))

    seen = {}
    for row in located:
        key = (round(row["lat"], 3), round(row["lng"], 3))
        if key not in seen:
            seen[key] = reverse_geocode(row["lat"], row["lng"])
            time.sleep(1.1)
        row["place"] = seen[key]

    for row in rows:
        if row["lat"] is not None:
            print("  %-42s %s  %8.4f,%9.4f  %s  [%s]" % (
                row["file"][:42], row["year"] or "????",
                row["lat"], row["lng"], row["place"] or "?", row["source"]))
        else:
            print("  %-42s %s  %-20s [%s]" % (
                row["file"][:42], row["year"] or "????",
                "no location", row["source"] or "nothing"))

    out = os.path.join(folder, "_scan.json")
    with open(out, "w", encoding="utf-8") as fh:
        json.dump(rows, fh, indent=2)
    print("\nwrote %s" % out)

    missing = len(rows) - len(located)
    if missing:
        print("\n%d photo(s) need a place from you - the older scans, most likely."
              % missing)


if __name__ == "__main__":
    main()
