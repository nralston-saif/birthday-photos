#!/usr/bin/env python3
"""
Convert the working photos into web-sized JPEGs for publishing.

Two sizes per photo: a 320px thumb for the gallery strip and a 1500px view
for the lightbox. HEIC goes through macOS `sips` (Pillow 9 can't decode it),
which also bakes in the EXIF rotation - so orientation is applied ONLY to
non-HEIC files, or the image flips twice.

Writes web/thumb/<stem>.jpg, web/full/<stem>.jpg and web/manifest.json.

Usage:  python3 prep_web.py ~/Desktop/dad-map/_work [out_dir]
"""

import json
import os
import subprocess
import sys
import tempfile

from PIL import Image, ImageOps

THUMB_PX = 320
FULL_PX = 1500
STILL = {".heic", ".heif", ".jpg", ".jpeg", ".png", ".tif", ".tiff", ".webp"}


def open_image(path):
    ext = os.path.splitext(path)[1].lower()
    if ext in (".heic", ".heif"):
        if sys.platform != "darwin":
            return None, False
        tmp = tempfile.NamedTemporaryFile(suffix=".jpg", delete=False)
        tmp.close()
        try:
            # Don't use check=True: sips writes warnings to stderr on files it
            # converts perfectly well, and one such file got dropped that way.
            subprocess.run(["sips", "-s", "format", "jpeg", path, "--out", tmp.name],
                           capture_output=True, timeout=60)
            if not os.path.exists(tmp.name) or os.path.getsize(tmp.name) == 0:
                return None, False
            img = Image.open(tmp.name)
            img.load()
            # sips does NOT bake the rotation in - it copies the EXIF
            # orientation tag onto the JPEG, so it still has to be applied.
            return img, False
        except (OSError, subprocess.SubprocessError):
            return None, False
        finally:
            try:
                os.unlink(tmp.name)
            except OSError:
                pass
    try:
        img = Image.open(path)
        img.load()
        return img, False
    except Exception:
        return None, False


def apply_orientation(img):
    """All eight EXIF orientations, mirrored ones included."""
    try:
        return ImageOps.exif_transpose(img)
    except Exception:
        return img


def save_at(img, px, path, quality):
    out = img.copy()
    out.thumbnail((px, px), Image.LANCZOS)
    out.save(path, "JPEG", quality=quality, optimize=True, progressive=True)
    return out.size


def main():
    if len(sys.argv) < 2:
        sys.exit("usage: prep_web.py <work_dir> [out_dir]")
    work = os.path.expanduser(sys.argv[1])
    out_dir = os.path.expanduser(sys.argv[2]) if len(sys.argv) > 2 \
        else os.path.join(work, "_web")
    thumb_dir = os.path.join(out_dir, "thumb")
    full_dir = os.path.join(out_dir, "full")
    for d in (thumb_dir, full_dir):
        os.makedirs(d, exist_ok=True)

    names = sorted(n for n in os.listdir(work)
                   if not n.startswith(".")
                   and os.path.splitext(n)[1].lower() in STILL
                   and os.path.isfile(os.path.join(work, n)))

    manifest, failed = {}, []
    for name in names:
        path = os.path.join(work, name)
        img, pre_rotated = open_image(path)
        if img is None:
            failed.append(name)
            continue
        if not pre_rotated:
            img = apply_orientation(img)
        img = img.convert("RGB")

        stem = os.path.splitext(name)[0]
        safe = "".join(c if (c.isalnum() or c in "-_") else "_" for c in stem)[:60]
        tp = os.path.join(thumb_dir, safe + ".jpg")
        fp = os.path.join(full_dir, safe + ".jpg")
        save_at(img, THUMB_PX, tp, 72)
        fw, fh = save_at(img, FULL_PX, fp, 80)

        manifest[name] = {
            "key": safe,
            "thumb": "photos/thumb/%s.jpg" % safe,
            "full": "photos/full/%s.jpg" % safe,
            "w": fw, "h": fh,
        }

    with open(os.path.join(out_dir, "manifest.json"), "w", encoding="utf-8") as fh:
        json.dump(manifest, fh, indent=2)

    tsize = sum(os.path.getsize(os.path.join(thumb_dir, f)) for f in os.listdir(thumb_dir))
    fsize = sum(os.path.getsize(os.path.join(full_dir, f)) for f in os.listdir(full_dir))
    print("converted %d photos" % len(manifest))
    print("  thumbs %.1f MB   full %.1f MB   total %.1f MB"
          % (tsize / 1e6, fsize / 1e6, (tsize + fsize) / 1e6))
    if failed:
        print("  FAILED (%d): %s" % (len(failed), ", ".join(failed)))


if __name__ == "__main__":
    main()
