// Loading and decoding the binary data files, map layouts and shared geometry.

// ================= data =================
async function gunzip(buf) {
  return new Response(new Blob([buf]).stream().pipeThrough(new DecompressionStream('gzip'))).arrayBuffer();
}
async function getBin(path) {
  const r = await fetch(path);
  if (!r.ok) throw new Error(path + ' ' + r.status);
  return gunzip(await r.arrayBuffer());
}
export let D, NC, NP, E, ringPt, ringStart, countyRing, circParam;
export const shared = {},
  cache = {};
export let NS, SIDS, stOf, stMembers, stRep, stCent, stArcs; // state structures
export const KM2 = 35.4527;
function decodeShared(buf) {
  const d = new Int16Array(buf);
  const fr = D.frame;
  const out = new Float32Array(2 * NP);
  let x = 0,
    y = 0;
  for (let i = 0; i < NP; i++) {
    x += d[2 * i];
    y += d[2 * i + 1];
    out[2 * i] = fr.x0 + x / fr.q;
    out[2 * i + 1] = fr.y0 + y / fr.q;
  }
  return out;
}
export function expandShared(s) {
  const o = new Float32Array(2 * E);
  for (let k = 0; k < E; k++) {
    const p = ringPt[k];
    o[2 * k] = s[2 * p];
    o[2 * k + 1] = s[2 * p + 1];
  }
  return o;
}
export function expandCircles(c) {
  const o = new Float32Array(2 * E);
  for (let i = 0; i < NC; i++) {
    const cx = c[i],
      cy = c[NC + i],
      r = c[2 * NC + i];
    for (const ri of countyRing[i])
      for (let k = ringStart[ri]; k < ringStart[ri + 1]; k++) {
        const a = circParam[k];
        if (a !== a || r === 0) {
          o[2 * k] = cx;
          o[2 * k + 1] = cy;
        } else {
          o[2 * k] = cx + r * Math.cos(a);
          o[2 * k + 1] = cy + r * Math.sin(a);
        }
      }
  }
  return o;
}
export const weightsFor = (m, k) => D.weights[m + '|' + k];
export function stateSum(arr) {
  const o = new Float64Array(NS);
  for (let i = 0; i < NC; i++) o[stOf[i]] += arr[i];
  return o;
}
// ---- layouts ----
function placeCircles(metric, key) {
  const w = weightsFor(metric, key),
    k = D.scales[metric],
    c = new Float32Array(3 * NC);
  for (let i = 0; i < NC; i++) {
    c[i] = D.cent[i][0];
    c[NC + i] = D.cent[i][1];
    c[2 * NC + i] = Math.sqrt((Math.max(0, w[i]) * k) / Math.PI);
  }
  return c;
}
function stateCircles(metric, key, packed) {
  // one circle per state, stored on the state's representative county
  const W = stateSum(weightsFor(metric, key)),
    k = D.scales[metric];
  const p = stCent.map(q => q.slice());
  const r = Array.from(W, w => Math.sqrt((Math.max(0, w) * k) / Math.PI));
  if (packed) {
    for (let it = 0; it < 900; it++) {
      const pull = it < 600 ? 0.02 * (1 - it / 600) : 0;
      const mv = p.map(() => [0, 0]);
      let any = false;
      for (let a = 0; a < NS; a++)
        for (let b = a + 1; b < NS; b++) {
          const dx = p[b][0] - p[a][0],
            dy = p[b][1] - p[a][1];
          const d = Math.hypot(dx, dy) || 1e-6;
          const ov = r[a] + r[b] + 0.6 - d;
          if (ov > 0) {
            any = true;
            const ux = dx / d,
              uy = dy / d,
              ma = r[a] * r[a],
              mb = r[b] * r[b],
              wa = mb / (ma + mb),
              wb = ma / (ma + mb);
            mv[a][0] -= ux * ov * wa * 0.6;
            mv[a][1] -= uy * ov * wa * 0.6;
            mv[b][0] += ux * ov * wb * 0.6;
            mv[b][1] += uy * ov * wb * 0.6;
          }
        }
      for (let s = 0; s < NS; s++) {
        p[s][0] += mv[s][0] + pull * (stCent[s][0] - p[s][0]);
        p[s][1] += mv[s][1] + pull * (stCent[s][1] - p[s][1]);
      }
      if (!any && it >= 600) break;
    }
  }
  const c = new Float32Array(3 * NC);
  for (let i = 0; i < NC; i++) {
    const s = stOf[i];
    c[i] = p[s][0];
    c[NC + i] = p[s][1];
    c[2 * NC + i] = stRep[s] === i ? r[s] : 0;
  }
  return c;
}
export async function layoutFor(method, metric, key, gran) {
  const id = [method, metric, key, gran].join('|');
  if (cache[id]) return cache[id];
  return (cache[id] = (async () => {
    if (method === 'contig') {
      const v = D.variants['contig|' + metric + '|' + key];
      if (!shared[v.file]) shared[v.file] = decodeShared(await getBin(v.file));
      const pos = expandShared(shared[v.file]);
      return { id, type: 'shape', shared: shared[v.file], pos, cent: polyCentroids(pos) };
    }
    if (gran === 'state')
      return { id, type: 'circ', c: stateCircles(metric, key, method === 'circ'), overlap: method === 'place' };
    if (method === 'place') return { id, type: 'circ', c: placeCircles(metric, key), overlap: true };
    const v = D.variants['circ|' + metric + '|' + key];
    return { id, type: 'circ', c: new Float32Array(await getBin(v.file)), overlap: false };
  })());
}
function polyCentroids(pos) {
  // per county [cx,cy,area] of the current shape, and per state
  const cc = new Float64Array(3 * NC);
  for (let i = 0; i < NC; i++) {
    let A = 0,
      X = 0,
      Y = 0;
    for (const r of countyRing[i]) {
      const s = ringStart[r],
        e = ringStart[r + 1];
      for (let k = s; k < e; k++) {
        const k2 = k + 1 < e ? k + 1 : s;
        const x0 = pos[2 * k],
          y0 = pos[2 * k + 1],
          x1 = pos[2 * k2],
          y1 = pos[2 * k2 + 1];
        const cr = x0 * y1 - x1 * y0;
        A += cr;
        X += (x0 + x1) * cr;
        Y += (y0 + y1) * cr;
      }
    }
    if (Math.abs(A) < 1e-9) {
      cc[3 * i] = pos[2 * ringStart[countyRing[i][0]]];
      cc[3 * i + 1] = pos[2 * ringStart[countyRing[i][0]] + 1];
      cc[3 * i + 2] = 0;
    } else {
      cc[3 * i] = X / (3 * A);
      cc[3 * i + 1] = Y / (3 * A);
      cc[3 * i + 2] = Math.abs(A) / 2;
    }
  }
  const sc = new Float64Array(3 * NS);
  for (let i = 0; i < NC; i++) {
    const s = stOf[i],
      a = cc[3 * i + 2];
    sc[3 * s] += cc[3 * i] * a;
    sc[3 * s + 1] += cc[3 * i + 1] * a;
    sc[3 * s + 2] += a;
  }
  for (let s = 0; s < NS; s++) {
    sc[3 * s] /= sc[3 * s + 2] || 1;
    sc[3 * s + 1] /= sc[3 * s + 2] || 1;
  }
  return { county: cc, state: sc };
}
function buildGeometry() {
  const pts = [],
    starts = [0],
    cr = [];
  let ri = 0;
  for (const rings of D.polys) {
    const mine = [];
    for (const r of rings) {
      r.forEach((a, j) => {
        const k = a >= 0 ? a : ~a;
        const s = D.arcOff[k],
          e = D.arcOff[k + 1];
        const seq = [];
        for (let i = s; i < e; i++) seq.push(i);
        if (a < 0) seq.reverse();
        for (let i = j ? 1 : 0; i < seq.length; i++) pts.push(seq[i]);
      });
      starts.push(pts.length);
      mine.push(ri++);
    }
    cr.push(mine);
  }
  ringPt = Int32Array.from(pts);
  ringStart = Int32Array.from(starts);
  countyRing = cr;
  E = pts.length;
  const g = shared.geo;
  circParam = new Float32Array(E).fill(NaN);
  for (let i = 0; i < NC; i++) {
    let best = -1,
      ba = 0;
    for (const r of countyRing[i]) {
      let a = 0;
      for (let k = ringStart[r]; k < ringStart[r + 1] - 1; k++) {
        const p = ringPt[k],
          q = ringPt[k + 1];
        a += g[2 * p] * g[2 * q + 1] - g[2 * q] * g[2 * p + 1];
      }
      if (Math.abs(a) > Math.abs(ba)) {
        ba = a;
        best = r;
      }
    }
    const s = ringStart[best],
      e = ringStart[best + 1];
    const cx = D.cent[i][0],
      cy = D.cent[i][1];
    let per = 0;
    const cum = [0];
    for (let k = s + 1; k < e; k++) {
      const p = ringPt[k - 1],
        q = ringPt[k];
      per += Math.hypot(g[2 * q] - g[2 * p], g[2 * q + 1] - g[2 * p + 1]);
      cum.push(per);
    }
    const p0 = ringPt[s];
    const a0 = Math.atan2(g[2 * p0 + 1] - cy, g[2 * p0] - cx);
    const dir = ba > 0 ? 1 : -1;
    for (let k = s; k < e; k++) circParam[k] = a0 + (dir * 2 * Math.PI * cum[k - s]) / (per || 1);
  }
  // states
  SIDS = [...new Set(D.st)].sort();
  NS = SIDS.length;
  const sidx = new Map(SIDS.map((s, i) => [s, i]));
  stOf = Int16Array.from(D.st.map(s => sidx.get(s)));
  stMembers = SIDS.map(() => []);
  for (let i = 0; i < NC; i++) stMembers[stOf[i]].push(i);
  const pop = D.weights['pop|2020'];
  stRep = stMembers.map(m => m.reduce((b, i) => (pop[i] > pop[b] ? i : b), m[0]));
  stCent = stMembers.map(m => {
    let a = 0,
      x = 0,
      y = 0;
    for (const i of m) {
      const w = D.area[i];
      a += w;
      x += D.cent[i][0] * w;
      y += D.cent[i][1] * w;
    }
    return [x / a, y / a];
  });
  // state boundary arcs per state (for outlines/selection)
  const use = Array.from({ length: D.arcOff.length - 1 }, () => new Set());
  for (let i = 0; i < NC; i++) for (const r of D.polys[i]) for (const a of r) use[a >= 0 ? a : ~a].add(stOf[i]);
  stArcs = SIDS.map(() => []);
  for (const a of D.stateArcs) for (const s of use[a]) stArcs[s].push(a);
}
// Loads core.bin and the geographic shapes, then builds the shared geometry.
export async function loadCoreData() {
  D = JSON.parse(new TextDecoder().decode(await getBin('data/core.bin')));
  NC = D.names.length;
  NP = D.nPts;
  shared[D.variants.geo.file] = shared.geo = decodeShared(await getBin(D.variants.geo.file));
  buildGeometry();
  D.allArcs = [...Array(D.arcOff.length - 1).keys()];
}
