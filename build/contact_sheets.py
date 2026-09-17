#!/usr/bin/env python3
"""
Build contact sheets so a whole shoot can be reviewed in a couple of dozen
images instead of hundreds.

Reads _scan.json if scan_photos.py has already run, and orders photos by
place then date - so near-duplicates of the same moment land side by side
and are easy to cull. Falls back to filename order if there's no scan yet.

Each cell is stamped with an index; index_map.json maps every index back to
its original file, so picking "042" is unambiguous.

HEIC is routed through macOS `sips`, since Pillow 9 can't decode it.

Usage:  python3 contact_sheets.py ~/Desktop/dad-map [out_dir]
"""

import json
import os
import subprocess
import sys
import tempfile

from PIL import Image, ImageDraw, ImageFont, ImageOps

IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".heic", ".heif", ".tif", ".tiff", ".webp"}

COLS, ROWS = 5, 5
CELL = 300           # thumbnail box, px
LABEL_H = 34         # caption strip under each thumbnail
PAD = 12
BG = (22, 27, 34)
FG = (223, 229, 225)
DIM = (147, 163, 171)


def load_font(size, bold=False):
    candidates = [
        "/System/Library/Fonts/SFNSMono.ttf",
        "/System/Library/Fonts/Menlo.ttc",
        "/Library/Fonts/Arial.ttf",
        "/System/Library/Fonts/Helvetica.ttc",
    ]
    for path in candidates:
        if os.path.exists(path):
            try:
                return ImageFont.truetype(path, size)
            except OSError:
                continue
    return ImageFont.load_default()


def open_image(path):
    """Pillow 9 can't read HEIC; macOS ships sips, which can."""
    ext = os.path.splitext(path)[1].lower()
    if ext in (".heic", ".heif"):
        if sys.platform != "darwin":
            return None
        tmp = tempfile.NamedTemporaryFile(suffix=".jpg", delete=False)
        tmp.close()
        try:
            subprocess.run(
                ["sips", "-s", "format", "jpeg", path, "--out", tmp.name],
                capture_output=True, timeout=30, check=True,
            )
            img = Image.open(tmp.name)
            img.load()
            return img
        except (OSError, subprocess.SubprocessError):
            return None
        finally:
            try:
                os.unlink(tmp.name)
            except OSError:
                pass
    try:
        img = Image.open(path)
        img.load()
        return img
    except Exception:
        return None


def apply_orientation(img):
    """Honor the EXIF rotation flag so portraits aren't reviewed sideways."""
    try:
        exif = img._getexif() or {}
        orientation = exif.get(274)
    except Exception:
        return img
    try:
        return ImageOps.exif_transpose(img)
    except Exception:
        return img


def gather(folder):
    scan_path = os.path.join(folder, "_scan.json")
    if os.path.exists(scan_path):
        try:
            with open(scan_path, "r", encoding="utf-8") as fh:
                rows = json.load(fh)
            # Group by place so duplicates of one moment sit together.
            rows.sort(key=lambda r: (
                r.get("place") or "zzz-unknown",
                r.get("date") or "",
                r.get("file") or "",
            ))
            return [{
                "path": os.path.join(folder, r["file"]),
                "label": r.get("place") or "no location",
                "year": r.get("year"),
            } for r in rows if os.path.exists(os.path.join(folder, r["file"]))]
        except (OSError, ValueError):
            pass

    out = []
    for root, dirs, names in os.walk(folder):
        dirs[:] = [d for d in dirs if not d.startswith("_")]
        for name in sorted(names):
            if name.startswith(".") or os.path.splitext(name)[1].lower() not in IMAGE_EXTS:
                continue
            out.append({"path": os.path.join(root, name), "label": "", "year": None})
    return out


def main():
    if len(sys.argv) < 2:
        sys.exit("usage: contact_sheets.py <folder> [out_dir]")
    folder = os.path.expanduser(sys.argv[1])
    out_dir = os.path.expanduser(sys.argv[2]) if len(sys.argv) > 2 \
        else os.path.join(folder, "_sheets")
    os.makedirs(out_dir, exist_ok=True)

    items = gather(folder)
    if not items:
        sys.exit("no images found under %s" % folder)

    font = load_font(15)
    small = load_font(12)

    per_sheet = COLS * ROWS
    sheet_w = COLS * CELL + (COLS + 1) * PAD

    def sheet_height(n_items):
        """Size to the rows actually used, so a partial last sheet isn't
        two-thirds empty - dead pixels cost review resolution."""
        rows_used = max(1, -(-n_items // COLS))
        return rows_used * (CELL + LABEL_H) + (rows_used + 1) * PAD + 34

    index_map = {}
    sheet_count = 0
    skipped = []

    for start in range(0, len(items), per_sheet):
        chunk = items[start:start + per_sheet]
        sheet_count += 1
        sheet = Image.new("RGB", (sheet_w, sheet_height(len(chunk))), BG)
        draw = ImageDraw.Draw(sheet)
        draw.text((PAD, 10),
                  "sheet %02d  ·  %d-%d of %d"
                  % (sheet_count, start + 1, start + len(chunk), len(items)),
                  fill=DIM, font=font)

        for n, item in enumerate(chunk):
            idx = start + n + 1
            col, row = n % COLS, n // COLS
            x = PAD + col * (CELL + PAD)
            y = 34 + PAD + row * (CELL + LABEL_H + PAD)

            img = open_image(item["path"])
            if img is None:
                skipped.append(item["path"])
                draw.rectangle([x, y, x + CELL, y + CELL], outline=DIM)
                draw.text((x + 8, y + CELL // 2), "unreadable", fill=DIM, font=small)
            else:
                # sips copies the orientation tag onto its JPEG rather than
                # baking the rotation in, so it applies to every format.
                img = apply_orientation(img).convert("RGB")
                img.thumbnail((CELL, CELL), Image.LANCZOS)
                sheet.paste(img, (x + (CELL - img.width) // 2,
                                  y + (CELL - img.height) // 2))

            tag = "%03d" % idx
            draw.text((x, y + CELL + 4), tag, fill=FG, font=font)
            meta = item["label"] or os.path.basename(item["path"])
            if item["year"]:
                meta = "%s  %s" % (item["year"], meta)
            draw.text((x + 34, y + CELL + 5), meta[:30], fill=DIM, font=small)

            index_map[tag] = os.path.relpath(item["path"], folder)

        sheet.save(os.path.join(out_dir, "sheet_%02d.jpg" % sheet_count),
                   quality=82, optimize=True)

    with open(os.path.join(out_dir, "index_map.json"), "w", encoding="utf-8") as fh:
        json.dump(index_map, fh, indent=2)

    print("%d photos -> %d sheets in %s" % (len(items), sheet_count, out_dir))
    if skipped:
        print("%d unreadable (listed in the sheets as 'unreadable'):" % len(skipped))
        for path in skipped[:10]:
            print("   ", os.path.basename(path))


if __name__ == "__main__":
    main()
