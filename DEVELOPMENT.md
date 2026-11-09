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

The plain alternative still works if you want a server you control yourself: `npm run serve` (the same as `cd site && python3 -m http.server 8000`).

The site is static: `index.html`, a stylesheet, a set of JavaScript modules, and gzipped binary data under `site/data/`. It has no build step, framework or runtime dependencies. `npm install` only pulls in dev tools (Prettier for formatting, Playwright for tests). You only need to run the Python pipeline if you change the **data**.

## Repository layout

```
site/                      ← deployed as-is to GitHub Pages
  index.html               ← page markup; loads the stylesheet and scripts below
  favicon.svg
  css/styles.css
  js/                      ← app code as layered ES modules (see "How the app works")
  data/core.bin            ← gzip JSON: contests, results, metrics, topology, scales
  data/v/*.bin             ← gzip Int16 delta-encoded vertex arrays, one per shape variant
  data/c/*.bin             ← gzip circle layouts (packed/Dorling), per metric × year
  CNAME, .nojekyll
scripts/preview.py         ← local dev server: opens the browser, exits when the tab closes
scripts/check-import-cycles.mjs ← fails if site/js modules import each other in a loop
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

## How the app works (`site/js/`)

The code is a set of ES modules. `index.html` loads only `main.js`, which imports the rest. Each file `export`s what other files use and `import`s what it needs, so nothing is global.

**Layers**: every import points down this list, never up or sideways in a loop. `npm run check:imports` checks this, and the deploy workflow runs the same check, so a loop blocks deployment.

| Layer | File | What's in it |
| --- | --- | --- |
| entry | `main.js` | imports every module, sets up `window.pollkadot`, resizes the map, chip row and curve, loads the data and shows the first contest |
| controls | `ui.js` | `go()` (apply the settings), icons, the chip row and its dropdown menus, header and popular-vote bar, details sheet |
| animation | `transition.js` | `transitionTo()`: animates what's on screen to the current settings |
| | `export.js` | PNG export |
| features | `interaction.js` | map tooltips, hit testing, pan/pinch/wheel zoom |
| | `legend.js` | the vote-share curve, range selection, snapping and scale zoom |
| drawing | `render.js` | the map canvas and fitting the map around the overlays, Canvas drawing, path caches, the contiguous-mode extent bitmap |
| state | `state.js` | settings (`st`), shared state (`app`), what's on screen (`scene`), county/state unit helpers, comparison rings and outlines |
| basics | `data.js` | loading `core.bin`, vertex decoding, circle/cartogram layouts, shared-arc geometry and state structures |
| | `color.js` | OKLab math and the blue–red color lookup table |
| | `format.js` | number and label formatting |
| | `aux-drag.js` | context-menu suppression after right/middle-button drags |

A lower module never calls up. When something low-level needs to trigger something higher up, the higher module does the coordinating. For example, `render.js` only resizes the map, and `main.js` resizes the map, the chip row's edge fades and the curve. Likewise, `go()` lives in `ui.js` because it refreshes the controls before starting the animation.

**Where state lives**:
- **`st`** (`state.js`): what the user picked, i.e. contest, size, shape, rings, color, granularity and borders.
- **`app`** (`state.js`): state several modules change, i.e. canvas size, `view`/`fit`, `sel`, `hl`, the curve selection (`selBand`, `preview`, `xr`), `interacting` and `colorVer`. Code reads and writes it as `app.view`, `app.sel` and so on.
- **`scene`** (`state.js`): what's on screen (`disp`, `colT`, `ringC`…). Only `transition.js` changes it; `render.js` draws it.
- **Everything else** belongs to the one module that changes it, and others import it read-only. For example, `data.js` owns the loaded data (`D`, `NC`…).
- **Adding something new.** If one module changes it, keep it there and export it. If several do, add it to `app`. Put it as low as it can go: in the lowest layer that everything using it can import from.

**Debug handle**: `window.pollkadot` reads `app` and `scene` fields and any exported value, all live: `pollkadot.disp`, `pollkadot.go()`, `pollkadot.st.metric = 'gdp'`. It can also assign `app` and `scene` fields, e.g. `pollkadot.view = { k: 1, x: 0, y: 0 }`. The Playwright tests use it, and it's handy in the browser console.

Code is formatted with Prettier (`npm run format`, settings in `.prettierrc.json`).

- **Loading**: `getBin(path)` fetches a `.bin` and gunzips it with `DecompressionStream`. `core.bin` loads first, then shape variants and circle layouts load lazily when needed.
- **Geometry**: one shared-arc topology. Each variant (geographic or a contiguous cartogram) is just a vertex array on the same arcs, so morphing is a per-vertex lerp. Simplification is the union of DP masks across all variants, so every variant uses the same point set.
- **Projection**: Census Albers USA (d3-style composite), precomputed in the pipeline.
- **Rendering**: Canvas2D.
  - `renderBase`/`paintScene(k, part)` draws fills grouped by color into cached `Path2D`s (`groupPaths`), then white lines.
  - In contiguous mode, panning and zooming reuse a whole-map extent bitmap for fills (`buildExtent`/`EXT`) and stroke lines live, so the bitmap never drifts out of alignment.
  - **Circles in place** blends overlaps per pixel in OKLab, weighted by votes (`drawCirclesBlended`, lower resolution while interacting).
  - Draws are coalesced with `requestDraw` (one per animation frame). `markInteracting` switches to the cheap paths while the user is interacting.
- **Transitions**: `transitionTo()` picks a strategy (radii-only, stay, morph or fade) based on what changed. Rings/outlines come from `computeCompare`, `ringExpanded` and `outlineExpanded`.
- **Color**: OKLab interpolation between fixed red and blue endpoints through a LUT.
- **Legend curve**: weighted KDE (`computeCurve`/`drawLegend`), range selection with snapping (`snap`, `setBand`), wheel zoom and right/middle-drag pan. `auxDrag` suppresses the context menu after aux-button drags, even when the button is released outside the element.
- **Export**: `renderExport()` re-renders the full map off-screen and ignores zoom, hover and selection. `exportName()` builds the file name and `downloadBlob` saves it through an `<a download>` link.
- **URL hash**: `#<year>-<race>` (for example `#2024-pres`) picks the contest.

## Tests

The tests use Playwright (Chromium) against a local server, by default `http://localhost:8000`. To test against a server on another port, set `BASE_URL`, for example `BASE_URL=http://localhost:8765 npm test`.

```bash
npm install && npx playwright install chromium
npm run serve &
npm run check:imports # no import loops between modules
npm test              # sweep.js: every contest × metric × shape × rings × color × granularity; screenshots → build/sweep/
npm run test:pan      # pantest.js: pan/zoom frame times, cursor, context-menu suppression
npm run test:export   # exptest.js: PNG export and download
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

- **2026 results**: there are no 2026 contests yet. The site only shows results built into `site/data`, so 2026 races appear once their results are added to the pipeline (`build_data.py` → `build_data2.py`). The 2026 population and Senate weights, cartograms and circle layouts are already built.
- `data_sources/*` scripts haven't been re-run since moving to this layout (see above).
- The contiguous cartogram plus state outlines at full-map zoom is the slowest frame (about 45–55 ms in headless Chromium). Possible fixes: decimate outlines further while interacting, or use OffscreenCanvas/WebGL.
- Mobile: touch pan/zoom works through pointer events. Phones (≤640px) use the same layout with a two-line header, full-width legend and full-width chip menus over a dimmed map.
