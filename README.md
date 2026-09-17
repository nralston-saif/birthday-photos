# Some of the places we've been

Live gift: https://dads-birthday-map.vercel.app

Source: https://github.com/nralston-saif/birthday-photos

A birthday atlas for Dad: 61 family photographs, 16 places, and memories from
2002 to 2026. The complete gift is in `site/publish/`. It works independently
of Claude and does not need a database, API key, or internet connection.

## Build and preview

From this directory:

```sh
python3 build/build.py
python3 -m http.server 8777 --bind 127.0.0.1 --directory site/publish
```

Open http://127.0.0.1:8777. You can also open `site/publish/index.html` directly.
Building the existing collection uses Python's standard library only.

## The experience

- An 11-stop journey from learning to shave to walking in Paris.
- A map with grouped pins, regional sheets, and a featured photo for each place.
- All 61 photographs in chronological order, filterable by year, chapter, and place.
- A keyboard-accessible photo viewer with full, uncropped images.
- A local editor for the title, dedication, captions, dates, places, notes, and covers.

The dedication is exactly **Happy Birthday Dad!**, as requested. The booklet
was dropped from scope. No physical print artifact is required.

## Your writing is included

`your-writing/` is the source of truth for authored content. Each build bakes
those files into the page. The original Claude artifact database is no longer
required to see the complete collection.

Choose **Edit this atlas** in the footer. Changes save on that browser/device;
they do not change what another visitor sees. Save errors are shown honestly,
retried up to three times, and can be retried manually or exported.

To update the shared gift after editing:

1. Choose **Export writing**.
2. Import the downloaded file when building:

```sh
python3 build/build.py --writing ~/Downloads/birthday-atlas-writing.json
```

This validates the writing before updating `your-writing/` and rebuilding.
Commit and push the updated writing to `main` to share the changes. You can also import writing in
the browser to continue editing it there. Before switching devices or clearing
browser storage, export any changes you want to keep.

Edit `your-writing/journey.json` to choose the opening photograph, selected
journey stops, and chapter names. Place covers and notes live in
`your-writing/waypoints.json`; existing records may include `cover` and `story`.
No unrecorded personal stories were invented for the gift.

## GitHub → Vercel

This repository is connected to the existing `dads-birthday-map` Vercel project.
Pushes to `main` build, test, and publish the site at the same address. Pull
requests get a preview deployment. The root `vercel.json` specifies the build
command and serves only the generated `site/publish/` directory.

```sh
python3 build/build.py
node --test tests/atlas.test.js
python3 -m unittest discover -s tests -p 'test_*.py'
git add build content assets your-writing tests README.md vercel.json .github
git commit -m "Update the birthday atlas"
git push origin main
```

The GitHub Actions workflow runs the same checks. Vercel also runs the tests
inside its build, so a failing test prevents that deployment from publishing.
Generated HTML is not committed: a fresh clone builds everything using the
tracked catalog, web-sized assets, writing, and source code. No dependency
installation, raw original photos, macOS tools, or secret API keys are needed.

The repository and the website are public. `originals/`, `work/`, `sheets/`,
backups, local hosting settings, and environment files are ignored. Only the
web-sized photos and the metadata already used by the website are tracked.
The site asks search engines not to index it; this is not access control.

## Files

- `originals/`: local-only original exports (ignored).
- `work/`: local-only photo processing files (ignored).
- `assets/`: tracked web-sized photos and map sheets.
- `content/catalog.json`: tracked media catalog, with no original-file metadata.
- `your-writing/`: authored captions, corrections, places, and journey.
- `build/web/`: application JavaScript, collection/save logic, and styling.
- `build/page_template.html`: accessible HTML layout.
- `build/build.py`: validated, offline build and asset packaging.
- `site/publish/`: generated deployable website (ignored).
- `tests/`: regression tests for assignments, sorting, validation, and saving.

Source files from before the upgrade are preserved under
`work/_backups/before-atlas-upgrade/`.

## Checks

```sh
python3 build/build.py
node --test tests/atlas.test.js
python3 -m unittest discover -s tests -p 'test_*.py'
```

See `build/README.md` before adding photographs or rebuilding maps.
