// Animates the map from what's on screen to the current settings.
import { expandCircles, layoutFor, NC } from './data.js';
import { app, computeCompare, contestArrays, ease, lerpArr, ringExpanded, scene, st, wkeyFor } from './state.js';
import { draw } from './render.js';
import { computeCurve } from './legend.js';
import { updateTip } from './interaction.js';

// ================= transition =================
let animId = 0; // bumped by each transition, so an older one still in flight stops
export async function transitionTo() {
  const c = st.contest;
  const my = ++animId;
  const busy = document.getElementById('busy');
  const tmo = setTimeout(() => (busy.style.display = 'block'), 150);
  let L;
  try {
    L = await layoutFor(st.method, st.metric, wkeyFor(c, st.metric), st.gran);
  } catch (e) {
    busy.textContent = 'Could not load shapes';
    return;
  }
  clearTimeout(tmo);
  busy.style.display = 'none';
  if (my !== animId) return;
  const A = contestArrays(c),
    wTo = st.shade === 'winner' ? 1 : 0,
    toLine = L.type === 'shape' ? 1 : 0,
    cmp = computeCompare(L);
  computeCurve();
  const finish = () => {
    scene.disp =
      L.type === 'circ'
        ? { type: 'circ', c: L.c.slice(), overlap: L.overlap ? 1 : 0 }
        : { type: 'shape', pos: L.pos.slice() };
    scene.dispL = L;
    scene.lineShared = L.shared || null;
    scene.ringC = cmp && cmp.kind === 'ring' ? cmp.r : null;
    scene.outl = cmp && cmp.kind === 'outline' ? cmp : null;
    scene.ringAlpha = cmp ? 1 : 0;
    scene.ringE = null;
    scene.animating = false;
    app.colorVer++;
  };
  if (!scene.disp) {
    finish();
    scene.colT = A.t;
    scene.colN = A.n;
    scene.colV = A.v;
    scene.winnerness = wTo;
    scene.lineAlpha = toLine;
    draw();
    updateTip();
    return;
  }
  const sameLayout = scene.dispL && scene.dispL.id === L.id;
  const fT = scene.colT.slice(),
    fN = scene.colN.slice(),
    fV = scene.colV.slice(),
    fW = scene.winnerness,
    fLine = scene.lineAlpha,
    fRingA = scene.ringAlpha,
    fRing = scene.ringC,
    fOutl = scene.outl;
  let mode, fromC, toC, fromP, toP, fromOv, toOv;
  if (scene.disp.type === 'circ' && L.type === 'circ') {
    mode = 'circ';
    fromC = scene.disp.c.slice();
    toC = L.c;
    fromOv = scene.disp.overlap;
    toOv = L.overlap ? 1 : 0;
  } else {
    mode = 'shape';
    fromP = scene.disp.type === 'circ' ? expandCircles(scene.disp.c) : scene.disp.pos.slice();
    toP = L.type === 'circ' ? expandCircles(L.c) : L.pos;
    scene.disp = { type: 'shape', pos: fromP.slice() };
  }
  // how the comparison lines travel: radii lerp (circle->circle), vertex morph (county circles <-> county outlines), else cross-fade
  const newRing = cmp && cmp.kind === 'ring' ? cmp.r : null;
  let rmode = 'fade',
    fromRE = null,
    toRE = null;
  if (fRing && newRing && mode === 'circ') rmode = 'radii';
  else if (fOutl && cmp && cmp.kind === 'outline' && sameLayout && fOutl.gran === cmp.gran) rmode = 'stay';
  else {
    const fe =
      fOutl && fOutl.E
        ? fOutl.E
        : fRing && scene.dispL.type === 'circ' && st.gran === 'county'
          ? ringExpanded(scene.dispL.c, fRing)
          : null;
    const te =
      cmp && cmp.kind === 'outline' && cmp.E
        ? cmp.E
        : newRing && L.type === 'circ' && st.gran === 'county'
          ? ringExpanded(L.c, newRing)
          : null;
    if (fe && te && fRingA > 0.5) {
      rmode = 'morph';
      fromRE = fe;
      toRE = te;
    }
  }
  const lineFrom = scene.lineShared,
    lineTo = L.shared || null;
  let lp = null,
    rr = null;
  const t0 = performance.now(),
    dur = sameLayout ? 450 : 950;
  scene.animating = true;
  if (rmode === 'morph') {
    scene.ringC = null;
    scene.outl = null;
    scene.ringE = fromRE.slice();
  }
  const step = now => {
    if (my !== animId) return;
    const tt = Math.min(1, (now - t0) / dur),
      e = ease(tt);
    lerpArr(fT, A.t, e, scene.colT);
    lerpArr(fN, A.n, e, scene.colN);
    lerpArr(fV, A.v, e, scene.colV);
    scene.winnerness = fW + (wTo - fW) * e;
    if (mode === 'circ') {
      lerpArr(fromC, toC, e, scene.disp.c);
      scene.disp.overlap = fromOv + (toOv - fromOv) * e;
    } else lerpArr(fromP, toP, e, scene.disp.pos);
    scene.lineAlpha = fLine + (toLine - fLine) * e;
    if (lineFrom && lineTo && lineFrom !== lineTo) {
      if (!lp) lp = new Float32Array(lineTo.length);
      lerpArr(lineFrom, lineTo, e, lp);
      scene.lineShared = lp;
    } else scene.lineShared = lineTo || lineFrom;
    if (rmode === 'radii') {
      if (!rr) rr = new Float32Array(NC);
      scene.ringC = lerpArr(fRing, newRing, e, rr);
      scene.ringAlpha = 1;
    } else if (rmode === 'stay') {
      scene.outl = cmp;
      scene.ringAlpha = 1;
    } else if (rmode === 'morph') {
      lerpArr(fromRE, toRE, e, scene.ringE);
      scene.ringAlpha = 1;
    } else {
      scene.ringAlpha = cmp ? Math.max(0, (tt - 0.7) / 0.3) : fRingA * Math.max(0, 1 - tt * 3);
      scene.ringC = tt > 0.7 ? newRing : mode === 'circ' ? fRing : null;
      scene.outl = tt > 0.7 ? (cmp && cmp.kind === 'outline' ? cmp : null) : fOutl && sameLayout ? fOutl : null;
    }
    app.colorVer++;
    if (tt >= 1) finish();
    draw();
    if (tt < 1) requestAnimationFrame(step);
    else updateTip();
  };
  requestAnimationFrame(step);
}
