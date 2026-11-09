// PNG export of the full map.
import { D, NC, shared } from './data.js';
import { app, scene, st } from './state.js';
import { bcv, extTimer, renderBase, resizeMap } from './render.js';

// ================= PNG export (full map, current settings; ignores zoom, hover, selection and highlights) =================
function downloadBlob(blob, filename) {
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 4000);
}
function contentBBox() {
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
  if (scene.disp.type === 'circ') {
    const c = scene.disp.c;
    for (let i = 0; i < NC; i++) {
      let r = c[2 * NC + i];
      if (scene.ringC && scene.ringC[i] > r) r = scene.ringC[i];
      if (!(r > 0)) continue;
      add(c[i] - r, c[NC + i] - r);
      add(c[i] + r, c[NC + i] + r);
    }
  } else {
    const p = scene.disp.pos;
    for (let k = 0; k < p.length; k += 2) add(p[k], p[k + 1]);
  }
  if (st.borders && scene.disp.type === 'circ') {
    const g = shared.geo;
    for (const a of D.stateArcs) for (let i = D.arcOff[a]; i < D.arcOff[a + 1]; i++) add(g[2 * i], g[2 * i + 1]);
  }
  return [x0, y0, x1, y1];
}
export function renderExport(outW = 1800, scale = 2) {
  const saved = {
    W: app.W,
    H: app.H,
    DPR: app.DPR,
    fit: app.fit,
    view: app.view,
    hl: app.hl,
    sel: app.sel,
    interacting: app.interacting,
    bw: bcv.width,
    bh: bcv.height,
  };
  const [x0, y0, x1, y1] = contentBBox();
  const bw = x1 - x0,
    bh = y1 - y0,
    pad = 0.03 * Math.max(bw, bh);
  app.W = outW;
  app.H = Math.round((outW * (bh + 2 * pad)) / (bw + 2 * pad));
  app.DPR = scale;
  const k = app.W / (bw + 2 * pad);
  app.fit = { k, x: -(x0 - pad) * k, y: -(y0 - pad) * k };
  app.view = { k: 1, x: 0, y: 0 };
  app.hl = null;
  app.sel = -1;
  app.interacting = false;
  app.colorVer++;
  bcv.width = Math.round(app.W * app.DPR);
  bcv.height = Math.round(app.H * app.DPR);
  renderBase();
  const out = document.createElement('canvas');
  out.width = bcv.width;
  out.height = bcv.height;
  const o = out.getContext('2d');
  o.fillStyle = getComputedStyle(document.body).backgroundColor || '#fff';
  o.fillRect(0, 0, out.width, out.height);
  o.drawImage(bcv, 0, 0);
  ({
    W: app.W,
    H: app.H,
    DPR: app.DPR,
    fit: app.fit,
    view: app.view,
    hl: app.hl,
    sel: app.sel,
    interacting: app.interacting,
  } = saved);
  bcv.width = saved.bw;
  bcv.height = saved.bh;
  app.colorVer++;
  clearTimeout(extTimer);
  resizeMap();
  return out;
}
function exportName() {
  const c = st.contest;
  const parts = [
    c.label.replace(/\s+/g, '-'),
    { PRES: 'president', SEN: 'senate', HOUSE: 'house', GOV: 'governor' }[c.office],
    'by-' + st.metric,
    { circ: 'packed-circles', place: 'circles-in-place', contig: 'contiguous' }[st.method],
  ];
  if (st.gran === 'state') parts.push('states');
  if (st.cmp !== 'none') parts.push('rings-' + st.cmp);
  if (st.shade === 'winner') parts.push('winner');
  return parts.join('_').toLowerCase() + '.png';
}
document.getElementById('exportBtn').onclick = async () => {
  const btn = document.getElementById('exportBtn'),
    lab = btn.querySelector('.t');
  if (btn.disabled) return;
  btn.disabled = true;
  lab.textContent = 'Preparing…';
  try {
    await new Promise(r => requestAnimationFrame(() => r()));
    const cnv = renderExport();
    const blob = await new Promise(r => cnv.toBlob(r, 'image/png'));
    downloadBlob(blob, exportName());
    lab.textContent = 'Saved';
  } catch (e) {
    console.error(e);
    lab.textContent = 'Export failed';
  }
  setTimeout(() => {
    lab.textContent = '';
    btn.disabled = false;
  }, 1600);
};
