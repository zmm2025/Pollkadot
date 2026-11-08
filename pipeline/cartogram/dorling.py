"""Dorling cartogram: one circle per county, area exactly proportional to weight,
started at the county's geographic centroid, then pushed apart until no two circles
overlap while being pulled back toward their home position.
Library use: circles(weights, k) -> (cx, cy, r)   [map units of the geographic projection]
"""
import pickle
import numpy as np
from scipy.spatial import cKDTree

T = pickle.load(open('data/geometry/topo_s.pkl', 'rb'))
N = len(T['ids'])
_offs = np.concatenate([[0], np.cumsum([len(a) for a in T['arcs']])]); _XY = np.concatenate(T['arcs'])

def _rings(i):
    out = []
    for ring in T['polys'][i]:
        seg = []
        for a in ring:
            k = a if a >= 0 else ~a; p = _XY[_offs[k]:_offs[k+1]]
            if a < 0: p = p[::-1]
            seg.append(p if not seg else p[1:])
        out.append(np.concatenate(seg))
    return out

def _centroid_area():
    C = np.zeros((N, 2)); A = np.zeros(N)
    for i in range(N):
        sx = sy = sa = 0.0
        rs = _rings(i)
        s = [0.5*np.sum(r[:-1, 0]*r[1:, 1] - r[1:, 0]*r[:-1, 1]) for r in rs]
        sg = np.sign(s[int(np.argmax(np.abs(s)))])
        for r, a in zip(rs, s):
            x, y = r[:, 0], r[:, 1]; cr = x[:-1]*y[1:] - x[1:]*y[:-1]
            sx += np.sum((x[:-1]+x[1:])*cr)/6; sy += np.sum((y[:-1]+y[1:])*cr)/6; sa += a
        C[i] = (sx/sa, sy/sa); A[i] = sg*sa
    return C, A
CENT, AREA = _centroid_area()

def circles(w, k, iters=4000, pull=0.03):
    """w: weights; k: map-area per unit weight (same k across years keeps sizes comparable)."""
    r = np.sqrt(np.maximum(w, 0)*k/np.pi)
    p = CENT.copy(); m = np.maximum(r, 1e-6)**2
    rmax = r.max(); big = np.where(r > np.percentile(r, 98))[0]
    for it in range(iters):
        tree = cKDTree(p)
        pairs = tree.query_pairs(2*np.percentile(r, 98) + 1e-9, output_type='ndarray')
        extra = []
        for b in big:
            nb = tree.query_ball_point(p[b], r[b] + rmax)
            extra += [(b, j) for j in nb if j != b]
        if extra: pairs = np.vstack([pairs, np.array(extra)])
        i, j = pairs[:, 0], pairs[:, 1]
        d = p[j] - p[i]; dist = np.hypot(d[:, 0], d[:, 1]) + 1e-9
        ov = r[i] + r[j] - dist; sel = ov > 0
        i, j, d, dist, ov = i[sel], j[sel], d[sel], dist[sel], ov[sel]
        u = d/dist[:, None]
        wi = m[j]/(m[i]+m[j]); wj = m[i]/(m[i]+m[j])          # small circles move more
        mv = np.zeros_like(p)
        np.add.at(mv, i, -u*(ov*wi)[:, None]*0.8); np.add.at(mv, j, u*(ov*wj)[:, None]*0.8)
        frac = it/iters
        p += mv + (pull*(CENT - p)*(1 - frac/0.8) if frac < 0.4 else 0)
        if sel.sum() == 0 and frac >= 0.4: break
    return p[:, 0], p[:, 1], r

def overlap_report(cx, cy, r):
    p = np.stack([cx, cy], 1); tree = cKDTree(p)
    pr = tree.query_pairs(2*r.max(), output_type='ndarray')
    d = np.hypot(*(p[pr[:, 0]] - p[pr[:, 1]]).T); ov = r[pr[:, 0]] + r[pr[:, 1]] - d
    return float(np.maximum(ov, 0).max()), int((ov > 1e-3).sum())
