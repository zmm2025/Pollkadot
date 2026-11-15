// Settings, shared runtime state, per-unit (county/state) helpers and comparison rings/outlines.
import {
  countyRing,
  D,
  E,
  expandCircles,
  expandShared,
  NC,
  NS,
  ringStart,
  shared,
  SIDS,
  stArcs,
  stateSum,
  stOf,
  weightsFor,
} from './data.js';

// ================= state =================
export const st = {
  metric: 'pop',
  method: 'circ',
  shade: 'share',
  cmp: 'none',
  gran: 'county',
  borders: true,
  region: null, // FIPS code of the one state the view is limited to, or null for the whole country
  contest: null,
};
// Runtime state that more than one module changes. Everything else lives in the module that owns it.
export const app = {
  W: 0, // map canvas size in CSS pixels
  H: 0,
  DPR: 1, // device pixel ratio used for the canvases
  fit: { k: 1, x: 0, y: 0 }, // transform that fits the whole map in the canvas
  view: { k: 1, x: 0, y: 0 }, // the user's pan/zoom on top of `fit`
  interacting: false, // true while panning/zooming, so drawing takes cheaper paths
  colorVer: 0, // bumped whenever colors or highlights change, to invalidate cached paths
  sel: -1, // hovered or tapped county/state, or -1
  hl: null, // per-unit opacity from the curve selection, or null when nothing is selected
  selBand: null, // selected vote-share range [lo, hi] on the curve
  preview: null, // range previewed while hovering the curve
  xr: [0, 1], // visible vote-share range of the curve (zoom)
  box: null, // map-space box that `fit` frames: the chosen state's extent, or null for the whole map (D.bbox)
  baseK: 1, // `fit.k` for the whole map, so line widths and detail follow the zoom relative to the national view
};

// What's currently on screen. Only transition.js changes these; render.js draws them.
export const scene = {
  disp: null, // displayed geometry: {type:'circ', c, overlap} or {type:'shape', pos}
  dispL: null, // the layout `disp` came from (or is heading to)
  colT: null, // per-county vote share (0 = D, 1 = R) as displayed
  colN: null, // per-county "no data" amount
  colV: null, // per-county two-party votes
  winnerness: 0, // 0 = vote-share colors, 1 = winner colors
  lineShared: null, // vertex array for county/state lines in contiguous mode
  lineAlpha: 0,
  ringC: null, // comparison ring radii (circle layouts)
  ringAlpha: 0,
  outl: null, // comparison outlines (contiguous layout)
  ringE: null, // expanded outline positions while morphing between circles and contiguous
  animating: false, // true while a transition is running
  vis: null, // per-county opacity when the view is limited to one state (fades during transitions), or null
  region: null, // the `st.region` on screen
};
// Fixes setting combinations the current contest can't show (e.g. Senate seats on a governor race).
export function normalizeSettings() {
  const c = st.contest;
  if (st.region != null && !D.states[st.region]) st.region = null;
  if (st.region != null) st.gran = 'county'; // a single state shows its counties
  if (!metricAvailable(c, st.metric)) st.metric = 'pop';
  if (st.cmp !== 'none' && (!metricAvailable(c, st.cmp) || st.cmp === st.metric)) st.cmp = 'none';
}
export const metricInfo = k => D.metrics.find(m => m.key === k);
export const wkeyFor = (c, m) => c.w[m] ?? null;
export const metricAvailable = (c, m) => {
  const wk = wkeyFor(c, m);
  return wk != null && !!D.weights[m + '|' + wk];
};
export const UNIT = () =>
  st.gran === 'state' ? { one: 'state', many: 'states' } : { one: 'county', many: 'counties' };
let aggCache = new Map();
function stateAgg(c) {
  if (aggCache.has(c)) return aggCache.get(c);
  const d = new Float64Array(NS),
    r = new Float64Array(NS),
    o = new Float64Array(NS);
  for (let i = 0; i < NC; i++) {
    if (c.dedupe[i]) continue;
    const s = stOf[i];
    d[s] += c.dem[i];
    r[s] += c.rep[i];
    o[s] += c.oth[i];
  }
  const a = { d, r, o };
  aggCache.set(c, a);
  return a;
}
// per-unit values: units are counties or states; unitOf(i) maps county -> unit index
export const unitOf = i => (st.gran === 'state' ? stOf[i] : i);
export const NU = () => (st.gran === 'state' ? NS : NC);
export function unitVotes(c) {
  if (st.gran === 'state') {
    const a = stateAgg(c);
    return a;
  }
  return { d: c.dem, r: c.rep, o: c.oth };
}
export function unitWeights(m, key) {
  const w = weightsFor(m, key);
  return st.gran === 'state' ? stateSum(w) : w;
}
// Whether county i is in the view: every county, or only those of the chosen state.
export const inRegion = i => st.region == null || SIDS[stOf[i]] === st.region;
// Units left out of totals, the curve and the vote bar: duplicated counties and counties outside the chosen state.
export function unitSkip(c, u) {
  return st.gran === 'county' && (c.dedupe[u] || !inRegion(u));
}
// Whether contest c has any votes in the chosen state (always true for the whole country).
export function hasRace(c, region = st.region) {
  if (region == null) return true;
  for (let i = 0; i < NC; i++) if (SIDS[stOf[i]] === region && c.dem[i] + c.rep[i] + c.oth[i] > 0) return true;
  return false;
}
// Per-county opacity for the chosen state: 1 inside, 0 outside, or null for the whole country.
export function visFor() {
  if (st.region == null) return null;
  const v = new Float32Array(NC);
  for (let i = 0; i < NC; i++) v[i] = inRegion(i) ? 1 : 0;
  return v;
}
// Map-space extent of the chosen state in layout L (with comparison rings and geographic borders), or null.
export function regionBox(L, cmp) {
  if (st.region == null) return null;
  let x0 = 1e9,
    y0 = 1e9,
    x1 = -1e9,
    y1 = -1e9;
  const add = (x, y) => {
    if (x < x0) x0 = x;
    if (y < y0) y0 = y;
    if (x > x1) x1 = x;
    if (y > y1) y1 = y;
  };
  for (let i = 0; i < NC; i++) {
    if (!inRegion(i)) continue;
    if (L.type === 'circ') {
      let r = L.c[2 * NC + i];
      if (cmp && cmp.kind === 'ring' && cmp.r[i] > r) r = cmp.r[i];
      if (!(r > 0)) continue;
      add(L.c[i] - r, L.c[NC + i] - r);
      add(L.c[i] + r, L.c[NC + i] + r);
    } else
      for (const r of countyRing[i])
        for (let k = ringStart[r]; k < ringStart[r + 1]; k++) add(L.pos[2 * k], L.pos[2 * k + 1]);
  }
  if (st.borders && L.type === 'circ') {
    const g = shared.geo;
    for (const a of stArcs[SIDS.indexOf(st.region)])
      for (let k = D.arcOff[a]; k < D.arcOff[a + 1]; k++) add(g[2 * k], g[2 * k + 1]);
  }
  return x1 > x0 && y1 > y0 ? [x0, y0, x1, y1] : null;
}
export function contestArrays(c) {
  const t = new Float32Array(NC),
    n = new Float32Array(NC),
    v = new Float32Array(NC);
  const U = unitVotes(c);
  for (let i = 0; i < NC; i++) {
    const u = unitOf(i);
    const d = U.d[u],
      r = U.r[u];
    if (d + r > 0) {
      t[i] = r / (d + r);
      v[i] = d + r;
    } else {
      t[i] = 0.5;
      n[i] = 1;
    }
  }
  return { t, n, v };
}
export const ease = x => (x < 0.5 ? 4 * x * x * x : 1 - Math.pow(-2 * x + 2, 3) / 2);
export function lerpArr(a, b, e, out) {
  for (let i = 0; i < out.length; i++) out[i] = a[i] + (b[i] - a[i]) * e;
  return out;
}
// ================= comparison rings / outlines =================
let geoE = null;
function compareShares() {
  const c = st.contest;
  if (st.cmp === 'none') return null;
  const wk = wkeyFor(c, st.metric),
    bk = wkeyFor(c, st.cmp);
  const w = unitWeights(st.metric, wk),
    b = unitWeights(st.cmp, bk);
  if (!w || !b) return null;
  let sw = 0,
    sb = 0;
  for (let u = 0; u < w.length; u++) {
    if (st.gran === 'county' && !inRegion(u)) continue; // rings compare shares of the chosen state's totals
    sw += w[u];
    sb += b[u];
  }
  return { w, b, sw, sb };
}
export function computeCompare(L) {
  const S = compareShares();
  if (!S) return null;
  const { w, b, sw, sb } = S;
  if (L.type === 'circ') {
    const r = new Float32Array(NC);
    for (let i = 0; i < NC; i++) {
      const u = unitOf(i),
        ri = L.c[2 * NC + i];
      r[i] = ri > 0 && w[u] > 0 ? ri * Math.sqrt(b[u] / sb / (w[u] / sw)) : 0;
    }
    return { kind: 'ring', r };
  }
  const share = new Float32Array(w.length);
  for (let u = 0; u < w.length; u++) share[u] = b[u] / sb;
  const o = { kind: 'outline', share, gran: st.gran };
  if (st.gran === 'county') o.E = outlineExpanded(L, share);
  return o;
}
function outlineExpanded(L, share) {
  // each county's real (geographic) shape, centred on its spot in the cartogram, area = share x total map area
  const cent = L.cent;
  if (!geoE) geoE = expandShared(shared.geo);
  let Atot = 0;
  for (let i = 0; i < NC; i++) if (inRegion(i)) Atot += cent.county[3 * i + 2];
  const out = new Float32Array(2 * E);
  for (let i = 0; i < NC; i++) {
    let f = Math.sqrt((share[i] * Atot) / D.area[i]);
    if (!isFinite(f)) f = 0;
    const cx = cent.county[3 * i],
      cy = cent.county[3 * i + 1],
      gx = D.cent[i][0],
      gy = D.cent[i][1];
    for (const r of countyRing[i])
      for (let k = ringStart[r]; k < ringStart[r + 1]; k++) {
        out[2 * k] = cx + (geoE[2 * k] - gx) * f;
        out[2 * k + 1] = cy + (geoE[2 * k + 1] - gy) * f;
      }
  }
  return out;
}
export function ringExpanded(c, r) {
  const t = new Float32Array(3 * NC);
  t.set(c.subarray(0, 2 * NC));
  t.set(r, 2 * NC);
  return expandCircles(t);
}
