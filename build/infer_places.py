#!/usr/bin/env python3
"""
Fill in locations the camera didn't record, by matching a photo's timestamp
against photos that DO have coordinates. Two people at a party, one phone with
location on and one without, produce exactly this gap.

Also applies any manual labels from places_manual.json, which always win:

    { "IMG_4370.HEIC": {"place": "Tahoe City, California",
                        "lat": 39.1785, "lng": -120.1305} }

Rerun after every scan - scan_photos.py overwrites _scan.json.

Usage:  python3 infer_places.py ~/Desktop/dad-map/_work [window_hours]
"""

import json
import os
import sys
from datetime import datetime

DEFAULT_WINDOW_H = 18          # deliberately tighter than a day: people travel


def parse(d):
    try:
        return datetime.fromisoformat(d)
    except (TypeError, ValueError):
        return None


def main():
    if len(sys.argv) < 2:
        sys.exit("usage: infer_places.py <work_dir> [window_hours]")
    work = os.path.expanduser(sys.argv[1])
    window = float(sys.argv[2]) if len(sys.argv) > 2 else DEFAULT_WINDOW_H

    scan_path = os.path.join(work, "_scan.json")
    with open(scan_path, "r", encoding="utf-8") as fh:
        rows = json.load(fh)

    # --- manual labels first: they are ground truth ---
    manual_path = os.path.join(os.path.dirname(work), "places_manual.json")
    manual = {}
    if os.path.exists(manual_path):
        try:
            with open(manual_path, "r", encoding="utf-8") as fh:
                manual = json.load(fh)
        except ValueError as exc:
            sys.exit("places_manual.json is not valid JSON: %s" % exc)

    applied = 0
    for r in rows:
        key = os.path.basename(r["file"])
        if key in manual:
            m = manual[key]
            r["lat"] = m.get("lat", r.get("lat"))
            r["lng"] = m.get("lng", r.get("lng"))
            r["place"] = m.get("place", r.get("place"))
            r["source"] = "manual"
            applied += 1

    located = [r for r in rows if r["lat"] is not None and r["date"]]
    todo = [r for r in rows if r["lat"] is None]

    rescued = []
    for r in todo:
        dt = parse(r.get("date"))
        if not dt:
            continue
        best, gap = None, None
        for l in located:
            ldt = parse(l["date"])
            if not ldt:
                continue
            delta = abs((ldt - dt).total_seconds())
            if gap is None or delta < gap:
                gap, best = delta, l
        if best and gap <= window * 3600:
            r["lat"], r["lng"] = best["lat"], best["lng"]
            r["place"] = best["place"]
            r["source"] = "inferred-by-date"
            r["inferred_gap_h"] = round(gap / 3600.0, 1)
            rescued.append(r)

    with open(scan_path, "w", encoding="utf-8") as fh:
        json.dump(rows, fh, indent=2)

    placed = sum(1 for r in rows if r["lat"] is not None)
    print("manual labels applied: %d" % applied)
    print("inferred within %.0fh: %d" % (window, len(rescued)))
    for r in sorted(rescued, key=lambda x: x.get("inferred_gap_h", 0)):
        print("   %-34s -> %-32s (%.1fh)"
              % (os.path.basename(r["file"])[:34], (r["place"] or "?")[:32],
                 r.get("inferred_gap_h", 0)))
    print("placed: %d of %d (%.0f%%)" % (placed, len(rows), 100.0 * placed / len(rows)))

    missing = [r for r in rows if r["lat"] is None]
    if missing:
        print("\nstill unplaced (%d):" % len(missing))
        for r in missing:
            print("   %-34s %s" % (os.path.basename(r["file"])[:34], r.get("year") or "????"))


if __name__ == "__main__":
    main()
