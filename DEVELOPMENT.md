# Developing Pollkadot

Everything technical lives here. The user guide is [README.md](README.md).

## Quick start

The site must be served over HTTP, because `file://` can't fetch the data files.

```bash
python scripts/preview.py      # or python3; standard library only
```

This serves `site/` from the checkout or worktree it runs in on `http://127.0.0.1:8765/` (or the next free port) and opens it in your default browser. **Closing the tab is the whole cleanup:** the server exits about 3 seconds after the last tab closes, so there's nothing to stop. Running it again while a preview of the same `site/` is already up just opens another tab on that server. Ctrl+C stops it immediately. Flags: `--port N`, `--no-browser`.

How it notices the tab closing: the dev server injects a one-line `EventSource` snippet into the HTML it serves (never into `site/index.html` on disk, so the deployed site is unchanged). A tab keeps that stream open while it's alive, and reloads reconnect within the 3-second grace period. Every open tab counts, in any browser, so the server runs until the **last** one closes. A tab that a browser's memory saver discards counts as closed. A tab left open after its server stopped (say after Ctrl+C) doesn't reconnect to the next preview, so reload it.

**T3 Code:** the project's **Preview site** action opens the site in T3's built-in browser instead. It's configured in T3's project settings, not in this repo:

- Command: `python scripts/preview.py --no-browser; if ($LASTEXITCODE -eq 0) { exit }`. The `exit` closes the terminal once the server is done. The script exits non-zero only when something went wrong (for example, no tab connected within 2 minutes), so the terminal stays open to show why.
- Preview URL `http://127.0.0.1:8765/`, with "open preview automatically" on.

T3 keeps a preview tab loaded even while its panel is hidden or you're in another thread, so the server keeps running until you close that preview tab. If T3 ever shows "Connection refused", it loaded the page before the server was ready; reload the tab.

The plain alternative still works if you want a server you control yourself: `cd site && python3 -m http.server 8000`.

The site is static: one `index.html` (markup, CSS and JS in one file) plus gzipped binary data under `site/data/`. It has no build step, framework or dependencies. You only need to run the Python pipeline if you change the **data**.

## Repository layout

```
site/                      ← deployed as-is to GitHub Pages
  index.html               ← the whole app (source of truth for UI code)
  data/core.bin            ← gzip JSON: contests, results, metrics, topology, scales
  data/v/*.bin             ← gzip Int16 delta-encoded vertex arrays, one per shape variant
  data/c/*.bin             ← gzip circle layouts (packed/Dorling), per metric × year
  CNAME, .nojekyll
scripts/preview.py         ← local dev server: opens the browser, exits when the tab closes
pipeline/
  build_data.py            ← results + metrics → build/payload.b64 (the contests payload)
  build_data2.py           ← payload + geometry + cartograms + circles → site/data/*
  cartogram/
    geo.py                 ← Census shapefile → shared-arc topology (TopoJSON-like) pickle
    simplify.py            ← Douglas–Peucker mask over shared arcs
    carto2.py              ← Gastner–Seguy–More flow-based contiguous cartogram
    weights.py             ← per-county weights per metric/year → data/weights/w/*.csv
    dorling.py, build_circles.py ← circle packing layouts → data/circles/
    render.py              ← quick PNG preview of a cartogram (debugging)
  data_sources/
    population/            ← Census county population estimates → data/pop/
    medsl/                 ← MEDSL precinct/county returns → data/results/
    metrics/               ← USDA ERS education, BEA GDP → data/metrics/
  tests/                   ← Playwright UI checks (sweep.js, pantest.js, exptest.js)
data/
  pop/ results/ metrics/   ← cleaned county tables (each has its own README with provenance + hashes)
  raw/                     ← dataverse_lock.csv (exact inputs + checksums), state/ (official files behind the patches)
  geometry/topo_s.pkl      ← simplified shared-arc county topology (Albers USA, 3,142 units)
  weights/                 ← population by year, metric weights, electoral vote tables
  circles/                 ← circle centers/radii per metric × year + circle_meta.json
  cartograms/              ← base.npz (geographic vertices + arc offsets) + contig_<metric>_<year>.npz (float32 xy)
build/                     ← scratch output, git-ignored
```

## Rebuilding the data

Run every command from the **repository root** with `python -P` (Python 3.10+; `numpy`, `scipy`, `pandas`, `Pillow`, `pyreadr`). The scripts use repo-relative paths.

**Results** (`data/results/`). The sources are pinned in `pipeline/sources.json`; see `data/results/README.md` for what each one covers.

```bash
python -P pipeline/fetch.py                     # ~12 GB of MIT / Amlani & Algara files -> build/downloads/dataverse/
python -P pipeline/data_sources/medsl/stage1_2016.py build/work/s1_2016.csv     build/downloads/dataverse/prec2016_senate/2016-precinct-senate.csv     build/downloads/dataverse/prec2016_house/2016-precinct-house.tab     build/downloads/dataverse/prec2016_state/2016-precinct-state.csv
for y in 2018 2020 2022 2024; do
  python -P pipeline/data_sources/medsl/stage1_extract.py $y build/work/s1_$y.csv build/downloads/dataverse/prec$y/*.{csv,tab,zip}
done
python -P pipeline/data_sources/medsl/stage2_aggregate.py 2016 2018 2020 2022 2024   # uses the 2018/2020 stage-1 files as a town->county map
python -P pipeline/data_sources/medsl/build_outputs.py 2016 2018 2020 2022 2024
python -P pipeline/build_results.py             # merges MIT + Amlani & Algara + data/results/patches -> data/results/
python -P pipeline/validate_results.py          # data/results/validation.csv; prints anything >0.5% off a statewide total
```

Some MIT datasets require a one-time Dataverse "guestbook" response (name, email, institution, position). `fetch.py` reads it from the `DATAVERSE_GUESTBOOK` environment variable (JSON) or a git-ignored `.dataverse-guestbook.json` at the repo root.

**Patches** (`data/results/patches/`) are official state results for races the main sources miss. Each has a CSV, a JSON with its sources, method and validation, the raw official file under `data/raw/state/<name>/` when small, and (for machine-readable sources) `pipeline/patches/<name>.py`, which regenerates the CSV. See `data/results/patches/README.md` for the format.

**Population and metrics** (`data/pop/`, `data/metrics/`): download the Census, BEA and USDA files listed in their READMEs into `build/downloads/{census,bea,ers}/`, then run `pipeline/data_sources/population/build_county_pop.py` and `pipeline/data_sources/metrics/build_metrics.py`.

**Site data** (results or metrics changed, shapes unchanged):

```bash
python -P pipeline/build_data.py        # contests payload -> build/payload.b64
python -P pipeline/cartogram/weights.py # area weights (needs build/payload.b64 for votes_*)
python -P pipeline/build_data2.py       # -> site/data/core.bin, v/*.bin, c/*.bin
```

**New years or new weights** also need cartograms and circles (minutes per cartogram):

1. **Geometry** (rarely): `geo.py <shp> <dbf> <out.pkl>`, then `simplify.py <in> <out> <tol>` → `data/geometry/topo_s.pkl` (Census `cb_2019_us_county_500k`).
2. **Cartograms**: `carto2.py data/geometry/topo_s.pkl <weights.csv> data/cartograms/contig_<metric>_<year>.npz --mode free --init <start.npz> --iters 6 --keep-best`. Each new map starts from the nearest well-converged map of the same metric where one exists (population 2000–2006 from population 2008, Senate 2000–2014 from Senate 2016, GDP 2001–2006 from GDP 2008, education 2000 from education 2008–12, `--iters 12` for GDP and education); votes cast and electoral votes start from that year's population map (votes `--iters 12`). Free flow at the finest scale improves for a few iterations and then slowly drifts, so `--keep-best` saves the most accurate iterate. Each output keeps its error history in `hist`. The 2008–2026 population and 2016–2026 Senate maps were made with `--mode anchored --iters 16` (a state-level stage, then a county stage inside closed state borders), but the current `carto2.py` no longer reproduces that county stage (its first county iteration lands at ~0.56 weighted error instead of the recorded ~0.20), so use warm starts until that is tracked down.
3. **Circles**: `build_circles.py` (uses `dorling.py`) adds layouts for any new keys → `data/circles/`. Existing scales in `circle_meta.json` are kept so earlier layouts stay valid.
4. **Site data** as above.

### Weekly data check

`.github/workflows/data-check.yml` runs `python -P pipeline/fetch.py --check` every Monday. It opens (or comments on) a "New election data available" issue when a pinned dataset has a newer version or MIT has published a dataset for a newer election (for example its 2026 precinct returns). Updating is then: bump `pipeline/sources.json`, rebuild as above, and review `validation.csv`.


### Data conventions

- 3,142 county units: 50 states + DC. Connecticut uses its 8 old counties, Virginia's independent cities are separate, Alaska is one statewide unit (results aren't reported by borough), Kansas City is folded into Jackson County MO, and DC wards map to 11001.
- President 2000–2024: MEDSL county presidential returns (Alaska from MEDSL statewide totals).
- Senate, House and Governor 2016–2024: MEDSL precinct returns aggregated to county; House is summed across every district that touches a county. Senate and Governor 2000–2014: Amlani & Algara county returns. Gaps: official state results (`data/results/patches/`).
- Population: Census intercensal (2000–2009), V2019 and V2025 estimates. GDP: BEA CAGDP1, 2001–2024 (thousands of dollars; `build_data2.py` multiplies its circle scale by 1000). Education: USDA ERS (Census 2000, ACS 2008–12, ACS 2019–23).
- Everything is deterministic: no randomness and no live fetching.

## How the app works (`site/index.html`)

- **Loading**: `getBin(path)` fetches a `.bin` and gunzips it with `DecompressionStream`. `core.bin` loads first, then shape variants and circle layouts load lazily when needed.
- **Geometry**: one shared-arc topology. Each variant (geographic or a contiguous cartogram) is just a vertex array on the same arcs, so morphing is a per-vertex lerp. Simplification is the union of DP masks across all variants, so every variant uses the same point set.
- **Projection**: Census Albers USA (d3-style composite), precomputed in the pipeline.
- **Rendering**: Canvas2D.
  - `renderBase`/`paintScene(k, part)` draws fills grouped by color into cached `Path2D`s (`groupPaths`), then white lines.
  - In contiguous mode, panning and zooming reuse a whole-map extent bitmap for fills (`buildExtent`/`EXT`) and stroke lines live, so the bitmap never drifts out of alignment.
  - **Circles in place** blends overlaps per pixel in OKLab, weighted by votes (`drawCirclesBlended`, lower resolution while interacting).
  - Draws are coalesced with `requestDraw` (one per animation frame). `markInteracting` switches to the cheap paths while the user is interacting.
- **Transitions**: `go()` picks a strategy (radii-only, stay, morph or fade) based on what changed. Rings/outlines come from `computeCompare`, `ringExpanded` and `outlineExpanded`.
- **Color**: OKLab interpolation between fixed red and blue endpoints through a LUT.
- **Legend curve**: weighted KDE (`computeCurve`/`drawLegend`), range selection with snapping (`snap`, `setBand`), wheel zoom and right/middle-drag pan. `auxDrag` suppresses the context menu after aux-button drags, even when the button is released outside the element.
- **Export**: `renderExport()` re-renders the full map off-screen and ignores zoom, hover and selection. `exportName()` builds the file name. On the standalone site, `browserDownloads.save` falls back to an `<a download>` link.
- **URL hash**: `#<year>-<race>` (for example `#2024-pres`) picks the contest.

## Tests

The tests use Playwright (Chromium) against a local server on port 8000:

```bash
(cd site && python3 -m http.server 8000) &
npm i -D playwright && npx playwright install chromium
node pipeline/tests/sweep.js     # every contest × metric × shape × rings × color × granularity; screenshots → build/sweep/
node pipeline/tests/pantest.js   # pan/zoom frame times, cursor, context-menu suppression
node pipeline/tests/exptest.js   # PNG export
```

`sweep.js` fails on any console error, any blank or misaligned render, or any broken control state.

## Deployment

GitHub Pages deploys through Actions (`.github/workflows/pages.yml`). Every push to `main` uploads `site/` as-is.

One-time setup:

1. Repo **Settings → Pages → Build and deployment → Source: GitHub Actions**.
2. **Custom domain**: `pollkadot.zain.build`. `site/CNAME` already contains it. Tick **Enforce HTTPS** once the certificate has been issued, which can take up to an hour.
3. DNS at Namecheap (**Domain List → zain.build → Advanced DNS**): add a **CNAME Record**, Host `pollkadot`, Value `zmm2025.github.io.`, TTL Automatic.
4. Optional: verify `zain.build` under GitHub **Settings → Pages → Verified domains** so no one else can claim subdomains.

## Known issues / TODO

- **2026 results**: there are no 2026 contests yet. The site only shows results built into `site/data`, so 2026 races appear once their results are added to the pipeline. Once states certify (December 2026), they can be added the same way as the patches (official state results, `data/results/patches/`), then replaced by MIT's 2026 precinct data when the weekly check reports it. The 2026 population and Senate weights, cartograms and circle layouts are already built.
- **House before 2016**: no free source has House results by county for earlier years.
- The contiguous cartogram plus state outlines at full-map zoom is the slowest frame (about 45–55 ms in headless Chromium). Possible fixes: decimate outlines further while interacting, or use OffscreenCanvas/WebGL.
- `index.html` is about 600 very long lines (~78 KB of minified-style code). Splitting it into modules (with or without a bundler) would make collaboration easier but isn't required.
- Mobile: touch pan/zoom works through pointer events. Phones (≤640px) use the same layout with a two-line header, full-width legend and full-width chip menus over a dimmed map.
