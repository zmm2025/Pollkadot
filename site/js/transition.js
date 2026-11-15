// Animates the map from what's on screen to the current settings.
import { D, expandCircles, layoutFor, NC } from './data.js';
import {
  app,
  computeCompare,
  contestArrays,
  ease,
  lerpArr,
  regionBox,
  ringExpanded,
  scene,
  st,
  visFor,
  wkeyFor,
} from './state.js';
import { draw, fitBox } from './render.js';
import { computeCurve } from './legend.js';
import { updateTip } from './interaction.js';

// ================= camera =================
// The screen transform of a fit with a view on top of it.
const camOf = (fit, view) => ({ k: fit.k * view.k, x: fit.x * view.k + view.x, y: fit.y * view.k + view.y });
// A smooth camera path from a to b (van Wijk & Nuij): it zooms out, pans and zooms back in, so a move between two
// zoomed-in states passes over the map instead of sweeping across it close up. Returns e (0..1) -> camera.
function camPath(a, b) {
  const { W, H } = app,
    view = c => [(W / 2 - c.x) / c.k, (H / 2 - c.y) / c.k, W / c.k], // map-space centre and width on screen
    cam = ([ux, uy, w]) => ({ k: W / w, x: W / 2 - (ux * W) / w, y: H / 2 - (uy * W) / w });
  const [ux0, uy0, w0] = view(a),
    [ux1, uy1, w1] = view(b),
    dx = ux1 - ux0,
    dy = uy1 - uy0,
    d2 = dx * dx + dy * dy,
    rho = Math.SQRT2;
  if (d2 < 1e-12) {
    const S = Math.log(w1 / w0);
    return e => cam([ux0, uy0, w0 * Math.exp(e * S)]);
  }
  const d1 = Math.sqrt(d2),
    b0 = (w1 * w1 - w0 * w0 + 4 * d2) / (4 * w0 * d1),
    b1 = (w1 * w1 - w0 * w0 - 4 * d2) / (4 * w1 * d1),
    r0 = Math.log(Math.sqrt(b0 * b0 + 1) - b0),
    r1 = Math.log(Math.sqrt(b1 * b1 + 1) - b1),
    S = (r1 - r0) / rho;
  return e => {
    if (e >= 1) return { ...b };
    const s = e * S,
      u = (w0 / (2 * d1)) * (Math.cosh(r0) * Math.tanh(rho * s + r0) - Math.sinh(r0));
    return cam([ux0 + u * dx, uy0 + u * dy, (w0 * Math.cosh(r0)) / Math.cosh(rho * s + r0)]);
  };
}
const sameBox = (a, b) => a === b || (a && b && a.every((v, i) => Math.abs(v - b[i]) < 1e-6));
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
    cmp = computeCompare(L),
    V = visFor(),
    box = regionBox(L, cmp),
    regionChanged = scene.region !== st.region;
  computeCurve();
  // Picking a state (or going back to the whole country) frames its extent and resets the user's zoom.
  const moveCam = regionChanged || !sameBox(app.box, box),
    viewTo = regionChanged ? { k: 1, x: 0, y: 0 } : { ...app.view },
    camFrom = camOf(app.fit, app.view);
  app.box = box;
  const cam = moveCam ? camPath(camFrom, camOf(fitBox(box || D.bbox), viewTo)) : null;
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
    scene.vis = V;
    scene.region = st.region;
    if (moveCam) {
      app.fit = fitBox(app.box || D.bbox);
      app.view = viewTo;
    }
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
    fOutl = scene.outl,
    fVis = scene.vis ? scene.vis.slice() : new Float32Array(NC).fill(1),
    tVis = V || new Float32Array(NC).fill(1),
    fades = !!(scene.vis || V);
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
    dur = sameLayout ? (moveCam ? 800 : 450) : 950;
  scene.animating = true;
  if (fades) scene.vis = fVis.slice();
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
    if (fades) lerpArr(fVis, tVis, e, scene.vis);
    if (moveCam) {
      app.fit = cam(e);
      app.view = { k: 1, x: 0, y: 0 };
    }
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
