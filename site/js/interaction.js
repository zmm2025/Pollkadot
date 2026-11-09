// Map interaction: tooltips, hit testing, pan, pinch and wheel zoom.
import { countyRing, D, KM2, NC, ringStart, SIDS, stMembers, stRep, weightsFor } from './data.js';
import { fmt, OFF, pct } from './format.js';
import { beginAuxDrag } from './aux-drag.js';
import { app, ease, metricInfo, scene, st, unitOf, unitVotes, unitWeights, wkeyFor } from './state.js';
import { cv, draw, drawOverlay, hf, markInteracting, requestDraw } from './render.js';

// ================= tooltip / interaction =================
const tip = document.getElementById('tip');
let tipPos = [0, 0];
function toMap(px, py) {
  const k = app.fit.k * app.view.k;
  return [(px - (app.fit.x * app.view.k + app.view.x)) / k, (py - (app.fit.y * app.view.k + app.view.y)) / k];
}
function hit(px, py) {
  if (!scene.disp) return -1;
  const [x, y] = toMap(px, py);
  if (scene.disp.type === 'circ') {
    const c = scene.disp.c;
    let best = -1,
      br = 1e9;
    const tol = 4 / (app.fit.k * app.view.k);
    for (let i = 0; i < NC; i++) {
      const r = c[2 * NC + i];
      if (r <= 0 || (app.hl && hf(i) < 0.5)) continue;
      const d = Math.hypot(x - c[i], y - c[NC + i]);
      if (d <= Math.max(r, tol) && r < br) {
        br = r;
        best = i;
      }
    }
    return best < 0 ? -1 : unitOf(best);
  }
  const p = scene.disp.pos;
  for (let i = NC - 1; i >= 0; i--) {
    let inside = false;
    for (const r of countyRing[i]) {
      const s = ringStart[r],
        e = ringStart[r + 1];
      for (let a = s, b = e - 1; a < e; b = a++) {
        const xa = p[2 * a],
          ya = p[2 * a + 1],
          xb = p[2 * b],
          yb = p[2 * b + 1];
        if (ya > y !== yb > y && x < ((xb - xa) * (y - ya)) / (yb - ya) + xa) inside = !inside;
      }
    }
    if (inside) return unitOf(i);
  }
  return -1;
}
function valueOf(m, key, u) {
  const w = unitWeights(m, key);
  if (!w) return null;
  let v = w[u];
  if (m === 'land') {
    if (st.gran === 'state') {
      const raw = weightsFor('land', 'all');
      v = 0;
      for (const i of stMembers[u]) v += raw[i] * (D.ids[i].startsWith('02') ? 1 / (0.35 * 0.35) : 1);
      v *= KM2;
    } else v = v * KM2 * (D.ids[u].startsWith('02') ? 1 / (0.35 * 0.35) : 1);
  }
  return v;
}
function valueText(m, key, u) {
  const mi = metricInfo(m);
  const v = valueOf(m, key, u);
  return v == null
    ? ''
    : (mi.fmt || '{}').replace('{}', (+v).toLocaleString('en-US', { maximumFractionDigits: mi.dp || 0 }));
}
function shareOf(m, key, u) {
  const w = unitWeights(m, key);
  if (!w) return null;
  let s = 0;
  for (const v of w) s += v;
  return w[u] / s;
}
export function updateTip() {
  if (app.sel < 0) {
    tip.style.display = 'none';
    drawOverlay();
    return;
  }
  if (animViewing) {
    tip.style.display = 'none';
    drawOverlay();
    return;
  }
  if (!animViewing && lastTapZoom) {
    const b = unitBBox(app.sel);
    const k = app.fit.k * app.view.k;
    tipPos = [
      ((b[0] + b[2]) / 2) * k + app.fit.x * app.view.k + app.view.x,
      b[3] * k + app.fit.y * app.view.k + app.view.y,
    ];
    lastTapZoom = false;
  }
  const c = st.contest,
    u = app.sel,
    U = unitVotes(c);
  const d = U.d[u],
    r = U.r[u],
    o = U.o[u],
    t = d + r + o;
  const sfips = st.gran === 'state' ? SIDS[u] : D.st[u];
  const cand = (c.cand && (c.cand[sfips] || c.cand['*'])) || {};
  const name = st.gran === 'state' ? (D.states[SIDS[u]] || {}).name : D.names[u];
  const subn =
    st.gran === 'state'
      ? c.office === 'HOUSE'
        ? 'All districts combined'
        : ''
      : ((D.states[D.st[u]] || {}).name || '') + (c.statewide && c.statewide[D.st[u]] ? ' · statewide result' : '');
  let h = `<b>${name}</b>${subn ? `<div class="sub">${subn}</div>` : ''}`;
  if (t > 0)
    h += `<div class="bar"><div style="width:${(100 * d) / t}%;background:var(--dem)"></div><div style="width:${(100 * o) / t}%;background:var(--oth)"></div><div style="width:${(100 * r) / t}%;background:var(--rep)"></div></div><table>
   <tr><td><span class="dot" style="background:var(--dem)"></span>${cand.d || 'Democratic'}</td><td>${fmt(d)} · ${pct(d / t)}</td></tr><tr><td><span class="dot" style="background:var(--rep)"></span>${cand.r || 'Republican'}</td><td>${fmt(r)} · ${pct(r / t)}</td></tr>
   <tr><td><span class="dot" style="background:var(--oth)"></span>${cand.o ? cand.o + ' + others' : 'Others'}</td><td>${fmt(o)} · ${pct(o / t)}</td></tr></table>`;
  else
    h += `<div class="sub" style="margin-top:4px">No ${OFF[c.office]} race${st.gran === 'county' ? ' data for this county' : ' here'} in ${c.year}.</div>`;
  const m = st.metric,
    wk = wkeyFor(c, m),
    bm = st.cmp !== 'none' ? st.cmp : m === 'pop' ? null : 'pop';
  h += `<div class="ratio">${metricInfo(m).label}: ${valueText(m, wk, u)}`;
  if (bm) {
    const bk = wkeyFor(c, bm);
    h += `<br>${metricInfo(bm).label}: ${valueText(bm, bk, u)}`;
    const a = shareOf(m, wk, u),
      b = shareOf(bm, bk, u);
    if (a != null && b > 0) {
      const q = a / b;
      h += `<br><b>${q >= 10 || q < 0.1 ? q.toPrecision(2) : q.toFixed(2)}×</b> its share of ${metricInfo(bm).label.toLowerCase()}`;
    }
  }
  h += '</div>';
  tip.innerHTML = h;
  tip.style.display = 'block';
  const tw = tip.offsetWidth,
    th = tip.offsetHeight;
  let [x, y] = tipPos;
  x = Math.min(Math.max(6, x + 12), app.W - tw - 6);
  y = y + 14 + th > app.H ? y - th - 14 : y + 14;
  tip.style.left = x + 'px';
  tip.style.top = Math.max(4, y) + 'px';
  drawOverlay();
}
const pts = new Map();
let gest = null,
  moved = false;
cv.addEventListener('contextmenu', e => e.preventDefault());
cv.addEventListener('auxclick', e => e.preventDefault());
cv.addEventListener('pointerdown', e => {
  if (e.button === 1 || e.button === 2) {
    e.preventDefault();
    beginAuxDrag();
  }
  tapButton = e.button;
  cv.style.cursor = 'grabbing';
  viewAnim++;
  animViewing = false;
  cv.setPointerCapture(e.pointerId);
  pts.set(e.pointerId, [e.offsetX, e.offsetY]);
  moved = false;
  gest = null;
});
cv.addEventListener('pointermove', e => {
  if (!pts.has(e.pointerId)) {
    if (e.pointerType === 'mouse') {
      const i = hit(e.offsetX, e.offsetY);
      tipPos = [e.offsetX, e.offsetY];
      cv.style.cursor = i >= 0 ? 'pointer' : 'default';
      if (i !== app.sel) {
        app.sel = i;
        updateTip();
      } else if (app.sel >= 0) updateTip();
    }
    return;
  }
  const prev = pts.get(e.pointerId);
  pts.set(e.pointerId, [e.offsetX, e.offsetY]);
  if (pts.size === 1) {
    const dx = e.offsetX - prev[0],
      dy = e.offsetY - prev[1];
    if (Math.abs(dx) + Math.abs(dy) > 0.5) moved = true;
    app.view.x += dx;
    app.view.y += dy;
    tip.style.display = 'none';
    markInteracting();
    requestDraw();
  } else if (pts.size === 2) {
    const [a, b] = [...pts.values()];
    const dist = Math.hypot(a[0] - b[0], a[1] - b[1]);
    const mx = (a[0] + b[0]) / 2,
      my = (a[1] + b[1]) / 2;
    if (gest) {
      zoomAt(mx, my, dist / gest.d);
      app.view.x += mx - gest.mx;
      app.view.y += my - gest.my;
    }
    gest = { d: dist, mx, my };
    moved = true;
    markInteracting();
    requestDraw();
  }
});
function unitBBox(u) {
  let x0 = 1e9,
    y0 = 1e9,
    x1 = -1e9,
    y1 = -1e9;
  if (scene.disp.type === 'circ') {
    const c = scene.disp.c;
    const i = st.gran === 'state' ? stRep[u] : u;
    const r = Math.max(c[2 * NC + i], 2 / app.fit.k);
    return [c[i] - r, c[NC + i] - r, c[i] + r, c[NC + i] + r];
  }
  const list = st.gran === 'state' ? stMembers[u] : [u];
  for (const i of list)
    for (const r of countyRing[i])
      for (let k = ringStart[r]; k < ringStart[r + 1]; k++) {
        const x = scene.disp.pos[2 * k],
          y = scene.disp.pos[2 * k + 1];
        if (x < x0) x0 = x;
        if (y < y0) y0 = y;
        if (x > x1) x1 = x;
        if (y > y1) y1 = y;
      }
  return [x0, y0, x1, y1];
}
let animViewing = false,
  lastTapZoom = false;
function zoomToUnit(u) {
  lastTapZoom = true;
  const [x0, y0, x1, y1] = unitBBox(u);
  const cx = (x0 + x1) / 2,
    cy = (y0 + y1) / 2;
  const span = Math.max(x1 - x0, y1 - y0, 1e-6);
  let k = Math.min(40, Math.max(1, (0.42 * Math.min(app.W, app.H)) / (span * app.fit.k)));
  const x = app.W / 2 - (cx * app.fit.k + app.fit.x) * k,
    y = app.H / 2 - (cy * app.fit.k + app.fit.y) * k;
  animateView(k === 1 ? { k: 1, x: 0, y: 0 } : { k, x, y });
}
let tapButton = 0;
function end(e) {
  cv.style.cursor = 'default';
  if (pts.size === 1 && !moved && tapButton === 0) {
    app.sel = hit(e.offsetX, e.offsetY);
    tipPos = [e.offsetX, e.offsetY];
    if (app.sel >= 0) zoomToUnit(app.sel);
    updateTip();
  }
  pts.delete(e.pointerId);
  if (pts.size < 2) gest = null;
}
cv.addEventListener('pointerup', end);
cv.addEventListener('pointercancel', e => {
  pts.delete(e.pointerId);
  gest = null;
  cv.style.cursor = 'default';
});
cv.addEventListener('pointerleave', e => {
  if (e.pointerType === 'mouse' && !pts.size) {
    app.sel = -1;
    updateTip();
  }
});
function zoomAt(px, py, f) {
  const nk = Math.max(1, Math.min(60, app.view.k * f));
  f = nk / app.view.k;
  app.view.x = px - (px - app.view.x) * f;
  app.view.y = py - (py - app.view.y) * f;
  app.view.k = nk;
  if (nk === 1) {
    app.view.x = 0;
    app.view.y = 0;
  }
}
cv.addEventListener(
  'wheel',
  e => {
    e.preventDefault();
    viewAnim++;
    animViewing = false;
    zoomAt(
      e.offsetX,
      e.offsetY,
      Math.exp(-(e.deltaMode === 1 ? e.deltaY * 16 : e.deltaY) * (e.ctrlKey ? 0.01 : 0.0015)),
    );
    tip.style.display = 'none';
    markInteracting();
    requestDraw();
  },
  { passive: false },
);
let viewAnim = 0;
function animateView(to) {
  const id = ++viewAnim;
  const from = { ...app.view },
    t0 = performance.now();
  animViewing = true;
  const s = now => {
    if (id !== viewAnim) {
      animViewing = false;
      return;
    }
    const e = ease(Math.min(1, (now - t0) / 350));
    app.view = { k: from.k + (to.k - from.k) * e, x: from.x + (to.x - from.x) * e, y: from.y + (to.y - from.y) * e };
    if (e >= 1) app.view = { ...to };
    tip.style.display = 'none';
    markInteracting();
    draw();
    if (e < 1) requestAnimationFrame(s);
    else {
      animViewing = false;
      if (app.sel >= 0) updateTip();
    }
  };
  requestAnimationFrame(s);
}
document.getElementById('zin').onclick = () => {
  animateView(zoomed(1.6));
};
document.getElementById('zout').onclick = () => {
  animateView(zoomed(1 / 1.6));
};
function zoomed(f) {
  const v0 = { ...app.view };
  zoomAt(app.W / 2, app.H / 2, f);
  const v1 = { ...app.view };
  app.view = v0;
  return v1;
}
