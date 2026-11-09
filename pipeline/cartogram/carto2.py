"""Contiguous density-equalizing cartograms on the county topology.

Method: fast flow-based algorithm of Gastner, Seguy & More (PNAS 2018).
  rho(r,t) = (1-t) rho0(r) + t rhobar ;  v = grad(psi) / rho(r,t) ;  lap(psi) = rho0 - rhobar
Each county is a uniform-density block (weight / county area), so nothing inside a county
is distorted differently from the rest of it.

Modes
  free      : one global flow; the sea has the mean land density, so coasts may move.
  anchored  : stage 1 = state-level cartogram (each county gets its state's density);
              stage 2 = county flow with NO flux across state borders (Poisson solved per
              state with Neumann boundaries), so state outlines stay close to stage 1;
              stage 3 = a few unconstrained iterations to remove the residual error.
Options
  --init file.npz  start from another cartogram's vertex positions (warm start)
usage: carto2.py topo.pkl weights.csv out.npz --mode free|anchored [--init X.npz] [--iters N] [--grid G]
"""
import pickle, sys, time, csv, argparse, os
import numpy as np
from scipy.fft import dctn, idctn
from scipy.ndimage import map_coordinates, gaussian_filter, distance_transform_edt
from scipy.sparse import coo_matrix, csr_matrix
from scipy.sparse.linalg import spsolve, cg
from scipy.sparse import diags
from scipy.sparse.csgraph import connected_components
from PIL import Image, ImageDraw

ap = argparse.ArgumentParser()
ap.add_argument('topo'); ap.add_argument('weights'); ap.add_argument('out')
ap.add_argument('--mode', default='free'); ap.add_argument('--init'); ap.add_argument('--iters', type=int, default=24)
ap.add_argument('--grid', type=int, default=1024); ap.add_argument('--s1iters', type=int, default=14)
ap.add_argument('--keep-best', dest='keep_best', action='store_true'); ap.add_argument('--s3iters', type=int, default=4); ap.add_argument('--taper', type=float, default=3.0)
A_ = ap.parse_args(); TAPER = A_.taper

T = pickle.load(open(A_.topo, 'rb'))
wt = {r['fips']: float(r['pop']) for r in csv.DictReader(open(A_.weights))}
ids = T['ids']; N = len(ids)
P_true = np.maximum(np.array([wt.get(i, 0.0) for i in ids]), 1e-6*max(wt.values()))
miss = [i for i in ids if i not in wt]
if miss: print('WARNING no weight for', len(miss), miss[:8])
state_of = np.array([int(s) for s in T['state']])
ust = np.unique(state_of); sidx = np.searchsorted(ust, state_of)   # 0..50

arcs = [a.astype(np.float64) for a in T['arcs']]
offs = None
def set_arcs(new):
    global arcs, offs
    arcs = new; offs = np.concatenate([[0], np.cumsum([len(a) for a in arcs])])
    return np.concatenate(arcs)
def split(XY): return [XY[offs[k]:offs[k+1]] for k in range(len(offs)-1)]
def split_by(XY, o): return [XY[o[k]:o[k+1]] for k in range(len(o)-1)]

def rings_of(XY, i):
    out = []
    for ring in T['polys'][i]:
        seg = []
        for a in ring:
            k = a if a >= 0 else ~a; pts = XY[offs[k]:offs[k+1]]
            if a < 0: pts = pts[::-1]
            seg.append(pts if not seg else pts[1:])
        out.append(np.concatenate(seg))
    return out
def signed_area(r): x, y = r[:, 0], r[:, 1]; return 0.5*np.sum(x[:-1]*y[1:] - x[1:]*y[:-1])
def county_areas(XY):
    A = np.zeros(N)
    for i in range(N):
        s = [signed_area(r) for r in rings_of(XY, i)]; sg = np.sign(s[int(np.argmax(np.abs(s)))]); A[i] = sg*sum(s)
    return A

FLAG = None
def densify(arcl, maxlen, flags):
    out = []; fo = []
    for a, fl in zip(arcl, flags):
        seg = np.hypot(*np.diff(a, axis=0).T); n = np.maximum(1, np.ceil(seg/maxlen).astype(int))
        if n.max() == 1: out.append(a); fo.append(fl); continue
        pts = [a[:1]]; ff = [fl[:1]]
        for j in range(len(a)-1):
            if n[j] == 1: pts.append(a[j+1:j+2]); ff.append(fl[j+1:j+2])
            else:
                f = (np.arange(1, n[j]+1)/n[j])[:, None]; pts.append(a[j] + f*(a[j+1]-a[j]))
                z = np.zeros(n[j], np.int8); z[-1] = fl[j+1]; ff.append(z)
        out.append(np.concatenate(pts)); fo.append(np.concatenate(ff))
    return out, fo
def redensify(g, maxlen):
    global FLAG
    a, f = densify(split(g), maxlen, [FLAG[offs[k]:offs[k+1]] for k in range(len(offs)-1)])
    FLAG = np.concatenate(f); return set_arcs(a)

# permanent vertices: base arcs densified to 1 map unit (identical for every run)
XY0 = set_arcs(densify(arcs, 1.0, [np.ones(len(a), np.int8) for a in arcs])[0])
BASE_OFFS = offs.copy(); BASE_XY = XY0.copy(); FLAG = np.ones(len(XY0), np.int8)
A_geo = county_areas(XY0)
START = XY0
if A_.init:
    z = np.load(A_.init); START = z['xy'].astype(np.float64); assert len(START) == len(BASE_XY)

# fixed frame (same for every run so warm starts line up)
x0, y0 = XY0.min(0); x1, y1 = XY0.max(0); pad = 0.35*max(x1-x0, y1-y0)
DX0, DY0 = x0-pad, y0-pad; W = (x1-x0)+2*pad; H = (y1-y0)+2*pad
LX = A_.grid; LY = int(round(LX*H/W)); cell = W/LX
def to_grid(XY): return (XY - [DX0, DY0])/cell
def from_grid(g): return g*cell + [DX0, DY0]

SS = 4
def rasterize(gxy, P, want_regions=False):
    A = county_areas(gxy)
    img = Image.new('I', (LX*SS, LY*SS), 0); d = ImageDraw.Draw(img)
    for i in np.argsort(-A):
        rs = rings_of(gxy, i); s = [signed_area(r) for r in rs]; sg = np.sign(s[int(np.argmax(np.abs(s)))])
        for r, si in zip(rs, s):
            if np.sign(si) == sg and len(r) >= 3: d.polygon([tuple(p) for p in (r*SS - 0.5)], fill=int(i)+1)
    lab = np.asarray(img, dtype=np.int32)
    land = P.sum()/A.sum()
    dens = np.concatenate([[land], P/np.maximum(A, 1e-9)])
    D = dens[lab].reshape(LY, SS, LX, SS).mean(axis=(1, 3))
    cnt = np.bincount(lab.ravel(), minlength=N+1)[1:]
    for i in np.where(cnt == 0)[0]:
        c = rings_of(gxy, i)[0].mean(0); cx, cy = int(np.clip(c[0], 0, LX-1)), int(np.clip(c[1], 0, LY-1))
        D[cy, cx] += P[i]
    D = np.maximum(D, 5e-3*land)
    reg = None
    if want_regions:
        cl = lab[SS//2::SS, SS//2::SS]
        reg = np.where(cl > 0, np.concatenate([[0], sidx+1])[cl], 0)
    return D, A, reg

def integrate(vel, pts, nsteps, maxmove=0.25):
    """RK4 with a separate clock per point: each point takes steps of at most `maxmove` cells,
    so only the few fast-moving points need many steps."""
    p = pts.copy(); t = np.zeros(len(p)); total = 0; it = 0
    act = np.arange(len(p))
    while len(act):
        q = p[act]; ta = t[act]
        k1 = vel(q, ta); sp = np.hypot(k1[:, 0], k1[:, 1])
        dt = np.minimum(np.minimum(1.0/nsteps, maxmove/np.maximum(sp, 1e-9)), 1.0 - ta)[:, None]
        k2 = vel(q + 0.5*dt*k1, ta+0.5*dt[:, 0]); k3 = vel(q + 0.5*dt*k2, ta+0.5*dt[:, 0]); k4 = vel(q + dt*k3, ta+dt[:, 0])
        q = q + dt/6*(k1+2*k2+2*k3+k4)
        q[:, 0] = np.clip(q[:, 0], 0.5, LX-0.5); q[:, 1] = np.clip(q[:, 1], 0.5, LY-0.5)
        p[act] = q; t[act] = ta + dt[:, 0]; total += len(act); it += 1
        act = act[t[act] < 1.0 - 1e-12]
    return p, it

def make_vel(D, gx, gy, rbar):
    def vel(p, t):
        c = [p[:, 1]-0.5, p[:, 0]-0.5]
        r0 = map_coordinates(D, c, order=1, mode='nearest'); rb = map_coordinates(rbar, c, order=1, mode='nearest')
        vx = map_coordinates(gx, c, order=1, mode='nearest'); vy = map_coordinates(gy, c, order=1, mode='nearest')
        rt = (1-t)*r0 + t*rb
        return np.stack([vx/rt, vy/rt], 1)
    return vel

def flow_free(D, pts):
    rhobar = D.mean(); f = dctn(D - rhobar, type=2, norm='ortho')
    ky = np.pi*np.arange(LY)/LY; kx = np.pi*np.arange(LX)/LX
    K2 = ky[:, None]**2 + kx[None, :]**2; K2[0, 0] = 1
    ph = -f/K2; ph[0, 0] = 0; psi = idctn(ph, type=2, norm='ortho')
    gy, gx = np.gradient(psi)
    return integrate(make_vel(D, gx, gy, np.full_like(D, rhobar)), pts, 25)

def flow_regions(D, reg, pts):
    """Poisson with no flux between different regions (states); sea (0) is static."""
    land = reg > 0; n = int(land.sum()); idx = -np.ones(reg.shape, np.int64); idx[land] = np.arange(n)
    rows = []; cols = []
    for dy, dx in ((0, 1), (1, 0)):
        a = idx[:LY-dy, :LX-dx]; b = idx[dy:, dx:]
        same = (a >= 0) & (b >= 0) & (reg[:LY-dy, :LX-dx] == reg[dy:, dx:])
        rows.append(a[same]); cols.append(b[same])
    r = np.concatenate(rows); c = np.concatenate(cols)
    Adj = coo_matrix((np.ones(len(r)), (r, c)), shape=(n, n)); Adj = Adj + Adj.T
    deg = np.asarray(Adj.sum(1)).ravel()
    # each connected piece of a state is its own closed region (mass cannot cross water)
    ncomp, R = connected_components(Adj, directed=False)
    rsum = np.bincount(R, weights=D[land], minlength=ncomp); rcnt = np.bincount(R, minlength=ncomp)
    rmean = rsum/np.maximum(rcnt, 1)
    comp = -np.ones(reg.shape, np.int64); comp[land] = R
    L = (coo_matrix((deg, (np.arange(n), np.arange(n))), shape=(n, n)) - Adj).tocsr()
    rhs = rmean[R] - D[land]            # L psi = rbar - rho0   <=>  lap(psi) = rho0 - rbar
    # singular but consistent (rhs sums to 0 on every component): Jacobi-preconditioned CG
    Minv = diags(1.0/np.maximum(deg, 1))
    tt = time.time()
    psi_l, info = cg(L, rhs, rtol=1e-7, maxiter=20000, M=Minv)
    psi_l -= (np.bincount(R, weights=psi_l, minlength=ncomp)/np.maximum(rcnt, 1))[R]
    print(f'   [cg {time.time()-tt:.1f}s info {info}]', end='', flush=True)
    psi = np.zeros(reg.shape); psi[land] = psi_l
    # face gradients, zero across region borders and sea
    gxf = np.zeros((LY, LX+1)); gyf = np.zeros((LY+1, LX))
    same_x = land[:, :-1] & land[:, 1:] & (reg[:, :-1] == reg[:, 1:])
    gxf[:, 1:-1] = np.where(same_x, psi[:, 1:] - psi[:, :-1], 0)
    same_y = land[:-1, :] & land[1:, :] & (reg[:-1, :] == reg[1:, :])
    gyf[1:-1, :] = np.where(same_y, psi[1:, :] - psi[:-1, :], 0)
    gx = 0.5*(gxf[:, :-1] + gxf[:, 1:]); gy = 0.5*(gyf[:-1, :] + gyf[1:, :])
    # taper the flux to zero at state borders so border vertices stay put (no slip, no folds)
    inner = land.copy()
    inner[:, 1:] &= same_x; inner[:, :-1] &= same_x; inner[1:, :] &= same_y; inner[:-1, :] &= same_y
    dist = distance_transform_edt(inner)
    taper = np.clip((dist - 0.5)/TAPER, 0, 1)
    gx *= taper; gy *= taper
    rbar = np.where(land, rmean[np.maximum(comp, 0)], D.mean())
    return integrate(make_vel(D, gx, gy, rbar), pts, 25)

def errors(A, P):
    tgt = P/P.sum()*A.sum(); e = A/tgt - 1; w = P/P.sum()
    return e, float(np.sum(w*np.abs(e))), float(np.median(np.abs(e)))

t0 = time.time(); hist = []
g = redensify(to_grid(START), 0.5)
def log(tag, it, P, A, sig, steps):
    e, wm, med = errors(A, P); hist.append((wm, med))
    print(f'{tag} {it}: sigma {sig:.2f} steps {steps} weighted|err| {wm:.4f} median {med:.4f} ({time.time()-t0:.0f}s)', flush=True)

def sigma_for(it, start): return max(0.5, start*0.5**it)

if A_.mode == 'anchored' and not A_.init:
    # stage 1: state-level densities (county keeps its state's density)
    Ps = np.bincount(sidx, weights=P_true); As = np.bincount(sidx, weights=A_geo)
    P1 = A_geo*(Ps/As)[sidx]
    import os
    s1file = A_.out.replace('.npz', '_s1.npy')
    if os.path.exists(s1file):
        z = np.load(s1file, allow_pickle=True).item(); g = set_arcs(split_by(z['g'], z['offs'])); FLAG = z['flag']; A_.s1iters = 0
    D, A, _ = rasterize(g, P1)
    for it in range(A_.s1iters):
        sg = sigma_for(it, 4.0); Db = gaussian_filter(D, sg)
        g, st = flow_free(Db, g); g = redensify(g, 0.5); D, A, _ = rasterize(g, P1); log('S1', it+1, P1, A, sg, st)
    if A_.s1iters: np.save(s1file, dict(g=g, offs=offs, flag=FLAG))
    # stage 2: county densities, state borders closed
    D, A, reg = rasterize(g, P_true, True)
    for it in range(A_.iters):
        sg = sigma_for(it, 2.0); Db = gaussian_filter(D, sg)
        g, st = flow_regions(Db, reg, g); g = redensify(g, 0.5); D, A, reg = rasterize(g, P_true, True); log("S2", it+1, P_true, A, sg, st)
    # stage 3: short global clean-up
    for it in range(A_.s3iters):
        g, st = flow_free(gaussian_filter(D, 0.5), g); g = redensify(g, 0.5); D, A, _ = rasterize(g, P_true); log('S3', it+1, P_true, A, 0.5, st)
else:
    D, A, _ = rasterize(g, P_true)
    start_sigma = 1.0 if A_.init else 4.0
    best = (np.inf, g)
    for it in range(A_.iters):
        sg = sigma_for(it, start_sigma); g, st = flow_free(gaussian_filter(D, sg), g)
        g = redensify(g, 0.5); D, A, _ = rasterize(g, P_true); log('F', it+1, P_true, A, sg, st)
        if A_.keep_best and hist[-1][0] < best[0]: best = (hist[-1][0], g.copy(), FLAG.copy(), [x.copy() for x in arcs])
    if A_.keep_best:   # free flow at the finest scale can slowly drift; keep the most accurate iterate
        _, g, FLAG, _a = best; set_arcs(_a); print(f'keeping best iterate: weighted|err| {best[0]:.4f}')

XY = from_grid(g); Af = county_areas(XY); e, wm, med = errors(Af, P_true)
keep = FLAG == 1
np.savez_compressed(A_.out, xy=XY[keep].astype(np.float32), err=e.astype(np.float32), hist=np.array(hist))
if not os.path.exists('data/cartograms/base.npz'): np.savez_compressed('data/cartograms/base.npz', base_xy=BASE_XY, base_offs=BASE_OFFS)
print('final', wm, med)
