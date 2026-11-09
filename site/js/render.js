// Canvas rendering: fills, borders, rings, path caches and the pan/zoom bitmap.
import { countyRing, D, NC, NS, ringStart, shared, stArcs, stCent, stMembers, stRep } from './data.js';
import { colorOf, dark, LUT, LUTN, NONERGB } from './color.js';
import { app, scene, st, unitOf } from './state.js';

// ================= drawing =================
export const cv = document.getElementById('map'); // the visible map canvas
// Scenes are painted into an offscreen buffer (bcv), then copied to the visible canvas with the selection on top.
const mctx = cv.getContext('2d');
export const bcv = document.createElement('canvas');
let ctx = bcv.getContext('2d'); // current drawing target; temporarily swapped by buildExtent and drawSel
// Sizes the map canvases to their element and refits the map, then redraws it.
export function resizeMap() {
  const r = cv.getBoundingClientRect();
  app.DPR = Math.min(2, window.devicePixelRatio || 1);
  app.W = r.width;
  app.H = r.height;
  cv.width = bcv.width = Math.round(app.W * app.DPR);
  cv.height = bcv.height = Math.round(app.H * app.DPR);
  // Fit the map into the stage without touching the overlays: the chip row on top, the legend (bottom right) and zoom buttons (bottom left,
  // hidden on phones, where the legend is full width). Try the ways the map's box can clear both bottom overlays and keep the largest fit.
  const b = D.bbox,
    bw = b[2] - b[0],
    bh = b[3] - b[1],
    pad = 8,
    g = 6,
    top = Math.max(pad, document.getElementById('chips').getBoundingClientRect().bottom - r.top + 2);
  const lg = document.getElementById('legcard').getBoundingClientRect(),
    zb = document.querySelector('.zoombtns').getBoundingClientRect();
  const L = { w: r.right - lg.left + g, h: r.bottom - lg.top + g },
    Z = zb.width ? { w: zb.right - r.left + g, h: r.bottom - zb.top + g } : { w: pad, h: pad }; // zoom buttons are hidden on phones
  const { W, H } = app;
  let best = null;
  for (const [x0, x1, y1] of [
    [pad, W - pad, H - Math.max(L.h, Z.h)],
    [Z.w, W - L.w, H - pad],
    [pad, W - L.w, H - Z.h],
    [Z.w, W - pad, H - L.h],
  ]) {
    const w = x1 - x0,
      h = y1 - top;
    if (w <= 0 || h <= 0) continue;
    const k = Math.min(w / bw, h / bh);
    if (!best || k > best.k) best = { k, x: x0 + (w - bw * k) / 2 - b[0] * k, y: top + (h - bh * k) / 2 - b[1] * k };
  }
  if (!best) {
    const k = Math.max(1e-6, Math.min((W - 2 * pad) / bw, (H - 2 * pad) / bh));
    best = { k, x: (W - bw * k) / 2 - b[0] * k, y: (H - bh * k) / 2 - b[1] * k };
  }
  app.fit = best;
  draw();
}
const T = () => {
  const k = app.fit.k * app.view.k;
  return { k, ox: app.fit.x * app.view.k + app.view.x, oy: app.fit.y * app.view.k + app.view.y };
};
function dispT(i) {
  const t = scene.colT[i];
  return scene.winnerness > 0 ? t + ((t > 0.5 ? 1 : t < 0.5 ? 0 : 0.5) - t) * scene.winnerness : t;
}
export const hf = i => (app.hl ? app.hl[unitOf(i)] : 1);
let img = null,
  accR = null,
  accV = null,
  accN = null;
function drawCirclesBlended(c) {
  // Pixel colour = OKLab(Σ R-weight / Σ vote-weight) over all circles covering the pixel; each circle's weight is its
  // two-party votes per unit of circle area (its colour value is its share, or 0/1 in Winner mode).
  // full resolution during shape transitions (a low-res pass reads as blur that snaps sharp at the end); reduced only while panning/zooming
  const { k, ox, oy } = T();
  const RS = app.interacting && !scene.animating ? Math.min(1, app.DPR) : app.DPR;
  const w = Math.round(app.W * RS),
    h = Math.round(app.H * RS),
    s = k * RS;
  const DPR_ = RS;
  if (!img || img.width !== w || img.height !== h) {
    img = ctx.createImageData(w, h);
    accR = new Float32Array(w * h);
    accV = new Float32Array(w * h);
    accN = new Float32Array(w * h);
  } else {
    accR.fill(0);
    accV.fill(0);
    accN.fill(0);
  }
  const data = img.data;
  data.fill(0);
  for (let i = 0; i < NC; i++) {
    const r = c[2 * NC + i] * s;
    if (r < 0.05) continue;
    const cx = (c[i] * k + ox) * DPR_,
      cy = (c[NC + i] * k + oy) * DPR_;
    const y0 = Math.max(0, Math.floor(cy - r - 1)),
      y1 = Math.min(h - 1, Math.ceil(cy + r + 1));
    if (y0 > y1 || cx + r < 0 || cx - r > w) continue;
    const hh = hf(i),
      dens = scene.colV[i] / (Math.PI * r * r),
      rd = dens * dispT(i),
      nn = scene.colN[i];
    for (let y = y0; y <= y1; y++) {
      const dy = y + 0.5 - cy;
      const half = Math.sqrt(Math.max(0, (r + 1) * (r + 1) - dy * dy));
      const x0 = Math.max(0, Math.floor(cx - half)),
        x1 = Math.min(w - 1, Math.ceil(cx + half));
      let o = y * w + x0;
      for (let x = x0; x <= x1; x++, o++) {
        const dx = x + 0.5 - cx;
        const a = Math.min(1, Math.max(0, r - Math.sqrt(dx * dx + dy * dy) + 0.5));
        if (a <= 0) continue;
        if (nn < 1) {
          const q = a * hh * (1 - nn);
          accV[o] += q * dens;
          accR[o] += q * rd;
        }
        accN[o] = Math.min(1, accN[o] + a * hh);
      }
    }
  }
  for (let o = 0; o < w * h; o++) {
    const cov = accN[o];
    if (cov <= 0) continue;
    const p = 4 * o;
    if (accV[o] > 0) {
      const li = 3 * Math.round((accR[o] / accV[o]) * LUTN);
      data[p] = LUT[li];
      data[p + 1] = LUT[li + 1];
      data[p + 2] = LUT[li + 2];
    } else {
      data[p] = NONERGB[0];
      data[p + 1] = NONERGB[1];
      data[p + 2] = NONERGB[2];
    }
    data[p + 3] = Math.round(255 * cov);
  }
  // composite over whatever is already drawn (e.g. state borders) via a scratch canvas
  if (!drawCirclesBlended.sc) {
    drawCirclesBlended.sc = document.createElement('canvas');
  }
  const sc = drawCirclesBlended.sc;
  if (sc.width !== w || sc.height !== h) {
    sc.width = w;
    sc.height = h;
  }
  sc.getContext('2d').putImageData(img, 0, 0);
  ctx.setTransform(1, 0, 0, 1, 0, 0);
  ctx.imageSmoothingEnabled = true;
  ctx.drawImage(sc, 0, 0, w, h, 0, 0, bcv.width, bcv.height);
}
function drawCirclesFlat(c) {
  const { k } = T();
  for (let i = 0; i < NC; i++) {
    const r = c[2 * NC + i];
    if (r * k < 0.05) continue;
    ctx.globalAlpha = hf(i);
    ctx.beginPath();
    ctx.arc(c[i], c[NC + i], r, 0, 2 * Math.PI);
    ctx.fillStyle = colorOf(dispT(i), scene.colN[i]);
    ctx.fill();
  }
  ctx.globalAlpha = 1;
}
function tracePath(pos, i) {
  for (const r of countyRing[i]) {
    const s = ringStart[r],
      e = ringStart[r + 1];
    ctx.moveTo(pos[2 * s], pos[2 * s + 1]);
    for (let k = s + 1; k < e; k++) ctx.lineTo(pos[2 * k], pos[2 * k + 1]);
    ctx.closePath();
  }
}
function arcsPath(pos, list, P = null) {
  const t = P || ctx;
  for (const a of list) {
    const s = D.arcOff[a],
      e = D.arcOff[a + 1];
    t.moveTo(pos[2 * s], pos[2 * s + 1]);
    for (let i = s + 1; i < e; i++) t.lineTo(pos[2 * i], pos[2 * i + 1]);
  }
}
function strokeArcs(pos, list) {
  ctx.beginPath();
  arcsPath(pos, list);
  ctx.stroke();
}
function whiteLine(k, w) {
  ctx.strokeStyle = 'rgba(255,255,255,.95)';
  ctx.lineWidth = w / k;
  ctx.lineJoin = 'round';
}
function noShadow() {
  ctx.shadowColor = 'transparent';
  ctx.shadowBlur = 0;
}
function expandedPath(E2, skip) {
  const P = new Path2D();
  for (let i = 0; i < NC; i++) {
    if (skip && skip(i)) continue;
    for (const r of countyRing[i]) {
      const s = ringStart[r],
        e = ringStart[r + 1];
      P.moveTo(E2[2 * s], E2[2 * s + 1]);
      for (let k = s + 1; k < e; k++) P.lineTo(E2[2 * k], E2[2 * k + 1]);
      P.closePath();
    }
  }
  return P;
}
const OTOL = 0.3; // map units (~0.4 px at full view): outlines are guides, so tiny wiggles are dropped
function decimatedPath(E2, skip) {
  const P = new Path2D();
  for (let i = 0; i < NC; i++) {
    if (skip && skip(i)) continue;
    for (const r of countyRing[i]) {
      const s = ringStart[r],
        e = ringStart[r + 1];
      let lx = E2[2 * s],
        ly = E2[2 * s + 1];
      P.moveTo(lx, ly);
      let n = 0;
      for (let k = s + 1; k < e; k++) {
        const x = E2[2 * k],
          y = E2[2 * k + 1];
        if (Math.abs(x - lx) + Math.abs(y - ly) < OTOL) continue;
        P.lineTo(x, y);
        lx = x;
        ly = y;
        n++;
      }
      P.closePath();
    }
  }
  return P;
}
function outlinePath(o) {
  // cached per outline object (static shapes)
  if (o.path && o.pathHl === app.hl) return o.path;
  let P;
  if (o.gran === 'state') {
    P = new Path2D();
    const cent = scene.dispL.cent,
      g = shared.geo;
    let Atot = 0;
    for (let i = 0; i < NC; i++) Atot += cent.county[3 * i + 2];
    for (let s = 0; s < NS; s++) {
      if (app.hl && app.hl[s] < 0.5) continue;
      let ga = 0;
      for (const i of stMembers[s]) ga += D.area[i];
      const f = Math.sqrt((o.share[s] * Atot) / ga);
      if (!(f > 0)) continue;
      const cx = cent.state[3 * s],
        cy = cent.state[3 * s + 1],
        gx = stCent[s][0],
        gy = stCent[s][1];
      for (const a of stArcs[s]) {
        const p = D.arcOff[a],
          e = D.arcOff[a + 1];
        let lx = cx + (g[2 * p] - gx) * f,
          ly = cy + (g[2 * p + 1] - gy) * f;
        P.moveTo(lx, ly);
        for (let q = p + 1; q < e; q++) {
          const x = cx + (g[2 * q] - gx) * f,
            y = cy + (g[2 * q + 1] - gy) * f;
          if (q < e - 1 && Math.abs(x - lx) + Math.abs(y - ly) < OTOL) continue;
          P.lineTo(x, y);
          lx = x;
          ly = y;
        }
      }
    }
  } else P = decimatedPath(o.E, i => app.hl && app.hl[i] < 0.5);
  o.path = P;
  o.pathHl = app.hl;
  return P;
}
// ---- static path caches (map coordinates; reused across pan/zoom frames) ----
const SC = {};
function groupPaths(kind) {
  // one Path2D per (colour, alpha) for the current shapes: ~hundreds of fills instead of 3,142
  const key = kind + '|' + app.colorVer;
  if (SC.groups && SC.groups.key === key && SC.groups.disp === scene.disp) return SC.groups.list;
  const m = new Map();
  for (let i = 0; i < NC; i++) {
    let P0;
    if (kind === 'circ') {
      const r = scene.disp.c[2 * NC + i];
      if (!(r > 0)) continue;
      P0 = null;
    }
    const col = colorOf(dispT(i), scene.colN[i]),
      a = hf(i),
      gk = col + '|' + a;
    let g = m.get(gk);
    if (!g) {
      g = { col, a, P: new Path2D() };
      m.set(gk, g);
    }
    if (kind === 'circ') {
      const c = scene.disp.c,
        r = c[2 * NC + i];
      g.P.moveTo(c[i] + r, c[NC + i]);
      g.P.arc(c[i], c[NC + i], r, 0, 2 * Math.PI);
    } else g.P.addPath(scene.disp.paths[i]);
  }
  const list = [...m.values()];
  SC.groups = { key, disp: scene.disp, list };
  return list;
}
function cachedArcs(name, pos, list) {
  const c = SC[name];
  if (c && c.pos === pos) return c.P;
  const P = new Path2D();
  arcsPath(pos, list, P);
  SC[name] = { pos, P };
  return P;
}
function ringPath() {
  if (SC.ring && SC.ring.r === scene.ringC && SC.ring.disp === scene.disp && SC.ring.v === app.colorVer)
    return SC.ring.P;
  const P = new Path2D(),
    c = scene.disp.c,
    thr = 0;
  for (let i = 0; i < NC; i++) {
    const r = scene.ringC[i];
    if (!(r > 0) || hf(i) < 0.5) continue;
    P.moveTo(c[i] + r, c[NC + i]);
    P.arc(c[i], c[NC + i], r, 0, 2 * Math.PI);
  }
  SC.ring = { r: scene.ringC, disp: scene.disp, v: app.colorVer, P };
  return P;
}
let interactTimer = null;
export function markInteracting() {
  app.interacting = true;
  clearTimeout(interactTimer);
  interactTimer = setTimeout(() => {
    app.interacting = false;
    if (scene.disp && (scene.disp.type === 'shape' || scene.disp.overlap > 0.001)) requestDraw();
  }, 160);
}
// ---- contiguous: whole-map bitmap used while panning/zooming (always complete and exactly aligned) ----
const EXT = { canvas: null, key: null, S: 1, x0: 0, y0: 0 };
export let extTimer = null;
function extKey() {
  return [scene.disp, app.colorVer, st.gran, dark]
    .map(v => (typeof v === 'object' && v ? v.__id || (v.__id = Math.random()) : v))
    .join('|');
}
function buildExtent() {
  if (!scene.disp || scene.disp.type !== 'shape' || scene.animating) return;
  const key = extKey();
  if (EXT.key === key) return;
  const b = D.bbox,
    maxDim = Math.min(4096, innerWidth < 700 ? 2600 : 4096),
    bw = b[2] - b[0],
    bh = b[3] - b[1];
  const S = Math.min(maxDim / bw, maxDim / bh);
  if (!EXT.canvas) EXT.canvas = document.createElement('canvas');
  const c = EXT.canvas;
  c.width = Math.ceil(bw * S);
  c.height = Math.ceil(bh * S);
  const saved = ctx;
  ctx = c.getContext('2d');
  ctx.setTransform(1, 0, 0, 1, 0, 0);
  ctx.clearRect(0, 0, c.width, c.height);
  ctx.setTransform(S, 0, 0, S, -b[0] * S, -b[1] * S);
  paintScene(app.fit.k * Math.max(1, app.view.k), 'fills');
  ctx = saved;
  Object.assign(EXT, { key, S, x0: b[0], y0: b[1] });
}
function scheduleExtent() {
  clearTimeout(extTimer);
  extTimer = setTimeout(buildExtent, 60);
}
export function renderBase() {
  const { k, ox, oy } = T();
  ctx.setTransform(1, 0, 0, 1, 0, 0);
  ctx.clearRect(0, 0, bcv.width, bcv.height);
  if (scene.disp.type === 'shape' && !scene.animating && app.interacting && EXT.key === extKey()) {
    ctx.imageSmoothingEnabled = true;
    ctx.setTransform(
      (k * app.DPR) / EXT.S,
      0,
      0,
      (k * app.DPR) / EXT.S,
      (EXT.x0 * k + ox) * app.DPR,
      (EXT.y0 * k + oy) * app.DPR,
    );
    ctx.drawImage(EXT.canvas, 0, 0);
    ctx.setTransform(app.DPR * k, 0, 0, app.DPR * k, app.DPR * ox, app.DPR * oy);
    paintScene(k, 'lines');
    return;
  }
  ctx.setTransform(app.DPR * k, 0, 0, app.DPR * k, app.DPR * ox, app.DPR * oy);
  paintScene(k, 'all');
  if (scene.disp.type === 'shape' && !scene.animating && !app.interacting) scheduleExtent();
}
function paintScene(k, part) {
  const F = part !== 'lines',
    LN = part !== 'fills';
  // optional geographic state borders under circles
  const bA = st.borders ? 1 - scene.lineAlpha : 0;
  if (LN && bA > 0.01) {
    ctx.globalAlpha = bA;
    ctx.strokeStyle = dark ? 'rgba(255,255,255,.28)' : 'rgba(0,0,0,.22)';
    ctx.lineWidth = 0.9 / k;
    ctx.lineJoin = 'round';
    ctx.stroke(cachedArcs('geoB', shared.geo, D.stateArcs));
    ctx.globalAlpha = 1;
  }
  if (!F) {
  } else if (scene.disp.type === 'circ' && scene.disp.overlap > 0.001) {
    const t = T();
    drawCirclesBlended(scene.disp.c);
    ctx.setTransform(app.DPR * t.k, 0, 0, app.DPR * t.k, app.DPR * t.ox, app.DPR * t.oy);
  } else if (scene.disp.type === 'circ') {
    if (scene.animating) drawCirclesFlat(scene.disp.c);
    else
      for (const g of groupPaths('circ')) {
        ctx.globalAlpha = g.a;
        ctx.fillStyle = g.col;
        ctx.fill(g.P);
      }
    ctx.globalAlpha = 1;
  } else {
    if (!scene.animating && !scene.disp.paths) {
      scene.disp.paths = [];
      for (let i = 0; i < NC; i++) {
        const P = new Path2D();
        for (const r of countyRing[i]) {
          const s = ringStart[r],
            e = ringStart[r + 1];
          P.moveTo(scene.disp.pos[2 * s], scene.disp.pos[2 * s + 1]);
          for (let q = s + 1; q < e; q++) P.lineTo(scene.disp.pos[2 * q], scene.disp.pos[2 * q + 1]);
          P.closePath();
        }
        scene.disp.paths.push(P);
      }
    }
    // the hairline stroke hides seams between touching contiguous shapes; fade it out as shapes become circles so the last frame matches the true arcs
    const sw = scene.animating ? scene.lineAlpha : 1;
    ctx.lineWidth = (0.35 * sw) / k;
    ctx.lineJoin = 'round';
    if (scene.disp.paths && !scene.animating) {
      for (const g of groupPaths('shape')) {
        ctx.globalAlpha = g.a;
        ctx.fillStyle = ctx.strokeStyle = g.col;
        ctx.fill(g.P);
        ctx.stroke(g.P);
      }
    } else
      for (let i = 0; i < NC; i++) {
        ctx.globalAlpha = hf(i);
        const s = colorOf(dispT(i), scene.colN[i]);
        ctx.fillStyle = s;
        ctx.strokeStyle = s;
        ctx.beginPath();
        tracePath(scene.disp.pos, i);
        ctx.fill();
        if (sw > 0.01) ctx.stroke();
      }
    ctx.globalAlpha = 1;
  }
  if (LN && scene.lineShared && scene.lineAlpha > 0.01) {
    ctx.globalAlpha = scene.lineAlpha;
    ctx.lineJoin = 'round';
    const still = !scene.animating;
    if (app.view.k > 2.5 && st.gran === 'county') {
      ctx.strokeStyle = dark ? 'rgba(0,0,0,.35)' : 'rgba(255,255,255,.45)';
      ctx.lineWidth = 0.5 / k;
      if (still) ctx.stroke(cachedArcs('allL', scene.lineShared, D.allArcs));
      else strokeArcs(scene.lineShared, D.allArcs);
    }
    ctx.strokeStyle = dark ? 'rgba(20,20,22,.9)' : 'rgba(255,255,255,.85)';
    ctx.lineWidth = (0.8 * Math.min(2, Math.sqrt(app.view.k))) / k;
    if (still) ctx.stroke(cachedArcs('stL', scene.lineShared, D.stateArcs));
    else strokeArcs(scene.lineShared, D.stateArcs);
    ctx.globalAlpha = 1;
  }
  // comparison lines (white)
  if (LN && scene.ringAlpha > 0.01) {
    ctx.globalAlpha = scene.ringAlpha;
    if (scene.ringE) {
      whiteLine(k, 0.9);
      ctx.stroke(expandedPath(scene.ringE, i => app.hl && hf(i) < 0.5));
    } else if (scene.outl && scene.disp.type === 'shape' && scene.dispL && scene.dispL.type === 'shape') {
      whiteLine(k, scene.outl.gran === 'state' ? 1.3 : 0.8);
      ctx.stroke(
        scene.animating
          ? scene.outl.gran === 'county'
            ? expandedPath(scene.outl.E)
            : outlinePath(scene.outl)
          : outlinePath(scene.outl),
      );
    } else if (scene.ringC && scene.disp.type === 'circ') {
      whiteLine(k, 0.9);
      if (scene.animating) {
        ctx.beginPath();
        const c = scene.disp.c;
        for (let i = 0; i < NC; i++) {
          const r = scene.ringC[i];
          if (r * k < 0.6 || hf(i) < 0.5) continue;
          ctx.moveTo(c[i] + r, c[NC + i]);
          ctx.arc(c[i], c[NC + i], r, 0, 2 * Math.PI);
        }
        ctx.stroke();
      } else ctx.stroke(ringPath());
    }
    noShadow();
    ctx.globalAlpha = 1;
  }
}
let drawPending = false;
export function requestDraw() {
  if (drawPending) return;
  drawPending = true;
  requestAnimationFrame(() => {
    drawPending = false;
    draw();
  });
}
export function draw() {
  document.getElementById('zout').disabled = app.view.k <= 1;
  if (!scene.disp) return;
  renderBase();
  drawOverlay();
}
export function drawOverlay() {
  mctx.setTransform(1, 0, 0, 1, 0, 0);
  mctx.clearRect(0, 0, cv.width, cv.height);
  mctx.drawImage(bcv, 0, 0);
  drawSel();
}
function drawSel() {
  if (app.sel < 0 || !scene.disp) return;
  const { k, ox, oy } = T();
  const saved = ctx;
  ctx = mctx;
  ctx.setTransform(app.DPR * k, 0, 0, app.DPR * k, app.DPR * ox, app.DPR * oy);
  ctx.beginPath();
  if (scene.disp.type === 'circ') {
    const c = scene.disp.c;
    const i = st.gran === 'state' ? stRep[app.sel] : app.sel;
    ctx.arc(c[i], c[NC + i], Math.max(c[2 * NC + i], 1.5 / k), 0, 2 * Math.PI);
  } else if (st.gran === 'state' && scene.lineShared) arcsPath(scene.lineShared, stArcs[app.sel]);
  else tracePath(scene.disp.pos, app.sel);
  ctx.strokeStyle = '#fff';
  ctx.lineWidth = 2.2 / k;
  ctx.shadowColor = 'rgba(0,0,0,.55)';
  ctx.shadowBlur = 3 * app.DPR;
  ctx.stroke();
  ctx.shadowBlur = 0;
  ctx.shadowColor = 'transparent';
  ctx = saved;
}
