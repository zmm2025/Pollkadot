# Developing Pollkadot

Everything technical lives here. The user guide is [README.md](README.md).

## Quick start

```bash
# Serve the site locally. It must be served over HTTP; file:// can't fetch the data files.
cd site && python3 -m http.server 8000
# open http://localhost:8000/
```

The site is static: one `index.html` (markup, CSS and JS in one file) plus gzipped binary data under `site/data/`. It has no build step, framework or dependencies. You only need to run the Python pipeline if you change the **data**.

## Repository layout

```
site/                      ← deployed as-is to GitHub Pages
  index.html               ← the whole app (source of truth for UI code)
  data/core.bin            ← gzip JSON: contests, results, metrics, topology, scales
  data/v/*.bin             ← gzip Int16 delta-encoded vertex arrays, one per shape variant
  data/c/*.bin             ← gzip circle layouts (packed/Dorling), per metric × year
  CNAME, .nojekyll
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
  raw/                     ← the few raw inputs needed to rebuild results (tonmcg, MEDSL countypres)
  geometry/topo_s.pkl      ← simplified shared-arc county topology (Albers USA, 3,142 units)
  weights/                 ← population by year, metric weights, electoral vote tables
  circles/                 ← circle centers/radii per metric × year + circle_meta.json
  cartograms/              ← base.npz (geographic vertices + arc offsets) + contig_<metric>_<year>.npz (float32 xy)
build/                     ← scratch output, git-ignored
```

## Rebuilding the data

Run every command from the **repository root**. The scripts use repo-relative paths and should be run with `python3 -I`. Requirements: Python 3.10+, `numpy`, `scipy`, `pandas`, `Pillow` (`render.py` only). `geo.py` reads the shapefile with its own pure-Python reader.

Typical change (results or metrics only, shapes unchanged):

```bash
python3 -I pipeline/build_data.py      # → build/payload.b64
python3 -I pipeline/build_data2.py     # → site/data/core.bin, v/*.bin, c/*.bin
```

These two steps were checked from a clean copy of the repo. They rebuild `site/data` matching the committed files, apart from tiny float32 rounding differences.

Full rebuild, in dependency order:

1. **Sources** → `data/pop`, `data/results`, `data/metrics`. These scripts download into `build/downloads/` (git clones of public mirrors, see each `data/*/README.md`). Their paths were rewritten from the original workspace and **have not been re-run in this repo layout**, so expect a few fixes.
   - `pipeline/data_sources/population/build_county_pop.py`
   - `pipeline/data_sources/medsl/stage1_extract.py`, `stage1_2016.py`, `stage2_aggregate.py`, `build_outputs.py`, `validate.py`, `check_known.py`
   - `pipeline/data_sources/metrics/build_metrics.py`
2. **Geometry**: `geo.py <shp> <dbf> <out.pkl>`, then `simplify.py <in> <out> <tol>` → `data/geometry/topo_s.pkl` (Census `cb_2019_us_county_500k`).
3. **Weights**: `pipeline/cartogram/weights.py` → `data/weights/`.
4. **Cartograms**: `carto2.py data/geometry/topo_s.pkl <weights.csv> data/cartograms/contig_<metric>_<year>.npz [--init <npz>] [--grid 1024] [--iters 24]`. Population runs state-first then county (warm start with `--init`). Each run takes minutes. Output keeps the RMS area error in `err`/`hist`.
5. **Circles**: `build_circles.py` (uses `dorling.py`) → `data/circles/`.
6. **Site data**: `build_data.py` then `build_data2.py` as above.

### Data conventions

- 3,142 county units: 50 states + DC. Connecticut uses its 8 old counties, Virginia's independent cities are separate, Alaska is one statewide unit (results aren't reported by borough), Kansas City is folded into Jackson County MO, and DC wards map to 11001.
- Presidential: MEDSL `countypres` for 2008–2016, tonmcg for 2020 and 2024. KS and ME 2020 come from MEDSL.
- Senate, House and Governor: MEDSL precinct returns 2016–2024, aggregated to county. House is summed across every district that touches a county.
- Population: Census intercensal, V2019 and V2025 estimates. GDP: BEA CAGDP1 (thousands of dollars; `build_data2.py` multiplies its circle scale by 1000). Education: USDA ERS.
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

- **2026 results**: the 2026 contests are placeholders and the user loads a CSV (Details → Load results CSV…). The Details text still says a page "can't fetch live feeds". That was true inside a Claude artifact, but GitHub Pages can fetch a CORS-enabled feed or a JSON committed to the repo by a scheduled Action. Wiring that up is the obvious next feature.
- `data_sources/*` scripts haven't been re-run since moving to this layout (see above).
- The contiguous cartogram plus state outlines at full-map zoom is the slowest frame (about 45–55 ms in headless Chromium). Possible fixes: decimate outlines further while interacting, or use OffscreenCanvas/WebGL.
- `index.html` is about 600 very long lines (~78 KB of minified-style code). Splitting it into modules (with or without a bundler) would make collaboration easier but isn't required.
- Mobile: touch pan/zoom works through pointer events, but the dock layout on narrow screens has had less testing than desktop.
