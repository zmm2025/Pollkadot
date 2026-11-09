// The vote-share curve under the map: density, range selection, snapping and zoom.
import { dark, lutCss } from './color.js';
import { beginAuxDrag } from './aux-drag.js';
import { app, metricInfo, NU, st, UNIT, unitSkip, unitVotes, unitWeights, wkeyFor } from './state.js';
import { requestDraw } from './render.js';

// ================= curve, range selection, snapping, zoom =================
const NX = 300;
export let dens = null,
  unitShares = [];
const marg = (v, dp) => {
  const m = (2 * v - 1) * 100;
  const r = Math.abs(m) < 0.05 ? 0 : m;
  if (r === 0) return 'even';
  const s = dp ? Math.abs(r).toFixed(1).replace(/\.0$/, '') : Math.round(Math.abs(r)).toString();
  return s === '0' ? 'even' : (r < 0 ? 'D+' : 'R+') + s;
};
export function computeCurve() {
  const c = st.contest;
  const w = unitWeights(st.metric, wkeyFor(c, st.metric));
  const U = unitVotes(c);
  const n = NU();
  const sg = Math.max(0.0008, 0.012 * (app.xr[1] - app.xr[0])),
    inv = 1 / (2 * sg * sg);
  dens = new Float64Array(NX);
  unitShares = [];
  for (let u = 0; u < n; u++) {
    if (unitSkip(c, u)) continue;
    const d = U.d[u],
      r = U.r[u];
    if (d + r <= 0) continue;
    const t = r / (d + r);
    unitShares.push(t);
    if (!(w[u] > 0)) continue;
    const j0 = Math.max(0, Math.floor(((t - 4 * sg - app.xr[0]) / (app.xr[1] - app.xr[0])) * NX)),
      j1 = Math.min(NX - 1, Math.ceil(((t + 4 * sg - app.xr[0]) / (app.xr[1] - app.xr[0])) * NX));
    for (let j = j0; j <= j1; j++) {
      const x = app.xr[0] + ((j + 0.5) / NX) * (app.xr[1] - app.xr[0]) - t;
      dens[j] += w[u] * Math.exp(-x * x * inv);
    }
  }
  unitShares.sort((a, b) => a - b);
  applyBand();
  drawLegend();
}
const tx = (t, Wc) => ((t - app.xr[0]) / (app.xr[1] - app.xr[0])) * Wc;
function curvePath(g, Wc, Hc) {
  const mx = Math.max(...dens) || 1;
  g.beginPath();
  g.moveTo(0, Hc);
  for (let j = 0; j < NX; j++) g.lineTo(((j + 0.5) / NX) * Wc, Hc - (dens[j] / mx) * (Hc - 2));
  g.lineTo(Wc, Hc);
  g.closePath();
}
export function drawLegend() {
  if (!dens) return;
  const hc = document.getElementById('hist');
  const r = hc.getBoundingClientRect();
  if (!r.width) return;
  hc.width = Math.round(r.width * app.DPR);
  hc.height = Math.round(r.height * app.DPR);
  const h = hc.getContext('2d');
  h.clearRect(0, 0, hc.width, hc.height);
  const grad = h.createLinearGradient(0, 0, hc.width, 0);
  for (let k = 0; k <= 16; k++) grad.addColorStop(k / 16, lutCss(app.xr[0] + (k / 16) * (app.xr[1] - app.xr[0])));
  const band = app.selBand || app.preview;
  h.globalAlpha = band ? 0.22 : 0.85;
  h.fillStyle = grad;
  curvePath(h, hc.width, hc.height);
  h.fill();
  h.globalAlpha = 1;
  if (0.5 > app.xr[0] && 0.5 < app.xr[1]) {
    const x = tx(0.5, hc.width);
    h.strokeStyle = dark ? 'rgba(255,255,255,.35)' : 'rgba(0,0,0,.22)';
    h.lineWidth = app.DPR;
    h.setLineDash([3 * app.DPR, 3 * app.DPR]);
    h.beginPath();
    h.moveTo(x, 0);
    h.lineTo(x, hc.height);
    h.stroke();
    h.setLineDash([]);
  }
  const elLo = document.getElementById('elLo'),
    elHi = document.getElementById('elHi'),
    chip = document.getElementById('chip');
  if (band) {
    const x0 = Math.max(0, tx(band[0], hc.width)),
      x1 = Math.min(hc.width, tx(band[1], hc.width));
    h.save();
    h.beginPath();
    h.rect(x0, 0, Math.max(1, x1 - x0), hc.height);
    h.clip();
    h.fillStyle = grad;
    curvePath(h, hc.width, hc.height);
    h.fill();
    h.restore();
    h.fillStyle = 'rgba(255,255,255,.14)';
    h.fillRect(x0, 0, x1 - x0, hc.height);
    h.strokeStyle = '#fff';
    h.shadowColor = 'rgba(0,0,0,.45)';
    h.shadowBlur = 2 * app.DPR;
    h.lineWidth = (app.selBand ? 2 : 1.5) * app.DPR;
    h.beginPath();
    h.moveTo(x0, 0);
    h.lineTo(x0, hc.height);
    h.moveTo(x1, 0);
    h.lineTo(x1, hc.height);
    h.stroke();
    h.shadowBlur = 0;
    h.shadowColor = 'transparent';
    // edge labels: left label grows leftward from its line, right label rightward, so they never overlap
    const Wcss = r.width,
      a = x0 / app.DPR,
      b = x1 / app.DPR,
      dp = band.snapDp ?? 1;
    elLo.textContent = marg(band[0], dp);
    elHi.textContent = marg(band[1], dp);
    elLo.style.display = 'block';
    elHi.style.display = 'block';
    const wl = elLo.offsetWidth,
      wh = elHi.offsetWidth;
    let la = Math.max(0, a - wl - 3),
      ha = Math.min(Wcss - wh, b + 3);
    if (ha < la + wl + 6) {
      ha = Math.min(Wcss - wh, la + wl + 6);
      la = Math.max(0, Math.min(la, ha - wl - 6));
    }
    elLo.style.left = la + 'px';
    elHi.style.left = ha + 'px';
    elLo.style.visibility = band[0] < app.xr[0] - 1e-9 ? 'hidden' : 'visible';
    elHi.style.visibility = band[1] > app.xr[1] + 1e-9 ? 'hidden' : 'visible';
    if (app.selBand) {
      chip.style.display = 'block';
      const ci = chip.firstElementChild;
      const cw = ci.offsetWidth;
      const cx = Math.min(Wcss - cw / 2, Math.max(cw / 2, (a + b) / 2));
      chip.style.left = cx + 'px';
    } else chip.style.display = 'none';
  } else {
    elLo.style.display = elHi.style.display = 'none';
    chip.style.display = 'none';
  }
  if (band && 0.5 > app.xr[0] && 0.5 < app.xr[1]) {
    const x = tx(0.5, hc.width);
    h.strokeStyle = dark ? 'rgba(255,255,255,.45)' : 'rgba(0,0,0,.3)';
    h.lineWidth = app.DPR;
    h.setLineDash([3 * app.DPR, 3 * app.DPR]);
    h.beginPath();
    h.moveTo(x, 0);
    h.lineTo(x, hc.height);
    h.stroke();
    h.setLineDash([]);
  }
  // axis labels for the visible range
  const lgA = document.getElementById('lgA'),
    lgB = document.getElementById('lgB'),
    lgC = document.getElementById('lgC');
  const zoomed = app.xr[1] - app.xr[0] < 0.999;
  lgA.textContent = marg(app.xr[0], zoomed ? 1 : 0).replace('even', 'even');
  lgC.textContent = marg(app.xr[1], zoomed ? 1 : 0);
  lgB.textContent = marg((app.xr[0] + app.xr[1]) / 2, zoomed ? 1 : 0);
  lgA.style.left = '0px';
  lgC.style.left = r.width - lgC.offsetWidth + 'px';
  lgB.style.left = r.width / 2 - lgB.offsetWidth / 2 + 'px';
  document.getElementById('lzout').disabled = !zoomed;
  document.getElementById('lzin').disabled = app.xr[1] - app.xr[0] <= 0.011;
}
const legEl = document.getElementById('curvebox');
function applyBand() {
  const band = app.selBand || app.preview;
  if (!band) {
    app.hl = null;
    return;
  }
  const c = st.contest,
    m = metricInfo(st.metric),
    U = unitVotes(c),
    w = unitWeights(st.metric, wkeyFor(c, st.metric)),
    n = NU();
  app.hl = new Float32Array(n);
  let cnt = 0,
    tw = 0,
    all = 0;
  for (let u = 0; u < n; u++) {
    const d = U.d[u],
      rr = U.r[u];
    let inb = false;
    if (d + rr > 0) {
      const s = rr / (d + rr);
      inb = s >= band[0] - 1e-9 && s <= band[1] + 1e-9;
    }
    app.hl[u] = inb ? 1 : 0.12;
    if (!unitSkip(c, u)) {
      all += w[u];
      if (inb) {
        cnt++;
        tw += w[u];
      }
    }
  }
  const un = UNIT();
  document.getElementById('chiptxt').innerHTML =
    `<b>${cnt.toLocaleString()}</b> ${cnt === 1 ? un.one : un.many} · <b>${((100 * tw) / (all || 1)).toFixed(1)}%</b> of ${m.unit}`;
}
export function refreshBand() {
  applyBand();
  app.colorVer++;
  drawLegend();
  requestDraw();
}
const tAt = x => {
  const r = legEl.getBoundingClientRect();
  return app.xr[0] + Math.min(1, Math.max(0, (x - r.left) / r.width)) * (app.xr[1] - app.xr[0]);
};
function snap(t) {
  // priority: an exact county/state share within 7px, then a whole margin point within 5px, else nearest tenth of a point
  const r = legEl.getBoundingClientRect();
  const perPx = (app.xr[1] - app.xr[0]) / r.width;
  let best = null,
    bd = 7 * perPx;
  let lo = 0,
    hi = unitShares.length;
  while (lo < hi) {
    const mid = (lo + hi) >> 1;
    if (unitShares[mid] < t) lo = mid + 1;
    else hi = mid;
  }
  for (const j of [lo - 1, lo]) {
    if (j >= 0 && j < unitShares.length) {
      const d = Math.abs(unitShares[j] - t);
      if (d < bd) {
        bd = d;
        best = unitShares[j];
      }
    }
  }
  if (best != null) return { t: best, dp: 1 };
  const whole = Math.round((2 * t - 1) * 100);
  const tw = (whole / 100 + 1) / 2;
  if (Math.abs(tw - t) < 5 * perPx) return { t: tw, dp: 0 };
  const tenth = Math.round((2 * t - 1) * 1000) / 10;
  return { t: (tenth / 100 + 1) / 2, dp: 1 };
}
function setBand(a, b) {
  const sa = snap(a),
    sb = snap(b);
  app.selBand = [Math.max(0, sa.t), Math.min(1, sb.t)];
  app.selBand.snapDp = sa.dp || sb.dp;
}
let drag = null;
function hoverMode(t) {
  if (!app.selBand) return null;
  const r = legEl.getBoundingClientRect();
  const e = (8 * (app.xr[1] - app.xr[0])) / r.width;
  if (Math.abs(t - app.selBand[0]) < e) return 'lo';
  if (Math.abs(t - app.selBand[1]) < e) return 'hi';
  if (t > app.selBand[0] && t < app.selBand[1]) return 'move';
  return null;
}
legEl.addEventListener('contextmenu', e => e.preventDefault());
legEl.addEventListener('auxclick', e => e.preventDefault());
legEl.addEventListener('pointerdown', e => {
  if (e.button === 1 || e.button === 2) {
    e.preventDefault();
    beginAuxDrag();
    legEl.setPointerCapture(e.pointerId);
    drag = { mode: 'pan', x0: e.clientX, xr0: app.xr.slice() };
    legEl.style.cursor = 'grabbing';
    return;
  }
});
legEl.addEventListener('pointerdown', e => {
  if (e.button !== 0) return;
  legEl.setPointerCapture(e.pointerId);
  const t = tAt(e.clientX);
  const m = hoverMode(t);
  app.preview = null;
  drag = m ? { mode: m, t0: t, b0: app.selBand.slice() } : { mode: 'new', t0: t, moved: false };
  if (!m) setBand(t, t);
  refreshBand();
});
legEl.addEventListener('pointermove', e => {
  const t = tAt(e.clientX);
  if (drag && drag.mode === 'pan' && legEl.hasPointerCapture(e.pointerId)) {
    app.preview = null;
    const r = legEl.getBoundingClientRect();
    const w = drag.xr0[1] - drag.xr0[0];
    let a = drag.xr0[0] - ((e.clientX - drag.x0) / r.width) * w;
    a = Math.min(1 - w, Math.max(0, a));
    app.xr = [a, a + w];
    computeCurve();
    return;
  }
  if (drag && legEl.hasPointerCapture(e.pointerId)) {
    if (drag.mode === 'new') {
      if (Math.abs(t - drag.t0) > 0.004 * (app.xr[1] - app.xr[0])) drag.moved = true;
      setBand(Math.min(t, drag.t0), Math.max(t, drag.t0));
    } else if (drag.mode === 'move') {
      const w = drag.b0[1] - drag.b0[0];
      const lo = Math.min(1 - w, Math.max(0, drag.b0[0] + t - drag.t0));
      const s = snap(lo);
      app.selBand = [s.t, Math.min(1, s.t + w)];
      app.selBand.snapDp = 1;
    } else if (drag.mode === 'lo') setBand(Math.min(t, app.selBand[1]), app.selBand[1]);
    else setBand(app.selBand[0], Math.max(t, app.selBand[0]));
    refreshBand();
    return;
  }
  if (e.pointerType === 'mouse') {
    const m = hoverMode(t);
    legEl.style.cursor = m === 'move' ? 'grab' : m ? 'ew-resize' : 'crosshair';
    if (!app.selBand) {
      const hw = 0.05 * (app.xr[1] - app.xr[0]);
      app.preview = [Math.max(0, t - hw), Math.min(1, t + hw)];
      app.preview.snapDp = 0;
      refreshBand();
    }
  }
});
legEl.addEventListener('pointerup', () => {
  if (drag && drag.mode === 'pan') {
    drag = null;
    legEl.style.cursor = 'crosshair';
    return;
  }
  if (drag && drag.mode === 'new' && !drag.moved) {
    const hw = 0.05 * (app.xr[1] - app.xr[0]);
    setBand(Math.max(0, drag.t0 - hw), Math.min(1, drag.t0 + hw));
  }
  drag = null;
  refreshBand();
});
legEl.addEventListener('pointerleave', e => {
  if (e.pointerType === 'mouse' && !drag && app.preview) {
    app.preview = null;
    refreshBand();
  }
});
legEl.addEventListener('pointercancel', () => {
  drag = null;
});
function zoomScale(f, center) {
  app.preview = null;
  const w = Math.min(1, Math.max(0.01, (app.xr[1] - app.xr[0]) * f));
  let c = center ?? (app.selBand ? (app.selBand[0] + app.selBand[1]) / 2 : (app.xr[0] + app.xr[1]) / 2);
  let a = c - w * ((c - app.xr[0]) / (app.xr[1] - app.xr[0] || 1));
  if (center == null) a = c - w / 2;
  a = Math.min(1 - w, Math.max(0, a));
  app.xr = [a, a + w];
  computeCurve();
}
document.getElementById('legend').addEventListener(
  'wheel',
  e => {
    e.preventDefault();
    zoomScale(Math.exp(e.deltaY * 0.002), tAt(e.clientX));
  },
  { passive: false },
);
document.getElementById('lzin').onclick = () => zoomScale(0.5);
document.getElementById('lzout').onclick = () => zoomScale(2);
document.getElementById('clearSel').onclick = e => {
  e.stopPropagation();
  app.selBand = null;
  app.preview = null;
  refreshBand();
};
