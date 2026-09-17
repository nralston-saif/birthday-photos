# Build the birthday atlas

The normal build is offline and requires only Python 3:

```sh
python3 build/build.py
```

Run it from the project root. It reads the tracked catalog in `content/catalog.json`, web assets in `assets/`,
and all authored content in `your-writing/`, validates references, compiles
the HTML/CSS/JavaScript, and copies the required files into `site/publish/`.
`site/chart.html` mirrors the generated index for the original artifact workflow.

To incorporate a browser writing export:

```sh
python3 build/build.py --writing /path/to/birthday-atlas-writing.json
```

Imports are validated before replacing the writing source. Failed builds leave
the previous published output and writing intact. Vercel publishes only `site/publish/` after building from the repository root.
The website includes all captions and location/year corrections by default.

## Adding photographs

Put new still photographs directly in `work/` (not in the project root). Keep
originals separately. Do not rename existing photos: their filenames are the
identifiers used by the writing snapshot. Then run from the project root:

```sh
python3 build/scan_photos.py work
python3 build/infer_places.py work
python3 build/build_panels.py work
python3 build/prep_web.py work
python3 build/build.py --refresh-media
```

`--refresh-media` updates the tracked catalog and web-sized assets from the
local `work/` folder. Commit these changes along with any writing corrections.
Ordinary builds and CI never read `work/`, so a fresh clone is sufficient.

The media refresh uses Pillow and macOS `sips` for HEIC files. Map generation
requires network access to OpenStreetMap. It is not run by the normal build.
After refreshing, review new automatic location assignments and any changed
clusters before sharing. The build rejects writing that refers to missing
places or photos, rather than silently dropping it.

## Implementation

- `build_page.py`: combines metadata, manual writing, and journey definitions;
  validates the data and safely embeds it in a complete HTML document.
- `page_template.html`: structural HTML, including native modal dialogs.
- `web/core.js`: pure assignment/sorting/import logic and serialized save queue.
- `web/app.js`: views, map interaction, timeline, dialogs, and local editor.
- `web/style.css`: desktop and phone layouts in the original atlas palette.
- `gazetteer.txt`: offline GeoNames place search; packaged lazily as JavaScript.

The editor uses browser storage, not Claude's database. Save success is reported
only after acknowledgement; failed writes remain pending for retry. Export is
available even if browser storage is full or disabled. Each built collection
has a content version so an old browser draft cannot silently replace a newer
published collection. Export drafts before deploying a new build.

Map sheets remain pre-rendered images. Zooming changes the rendered image
width so the browser resamples the source. Coordinates use Web Mercator, as
in the original pipeline. Clusters group nearby screen positions and provide
an accessible place list when several locations overlap.

HEIC conversion must apply EXIF orientation after `sips`. Skip underscore
folders during photo scans so generated contact sheets are not re-ingested.
`IMG_8112.HEIC` fails conversion; the existing `IMG_8112_1.HEIC` replacement is
included. Twenty images still have no authored caption and use a neutral place
label until you add one.
