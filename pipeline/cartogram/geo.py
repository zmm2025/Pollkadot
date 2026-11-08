"""Read Census cartographic-boundary county shapefile, project with d3-style
Albers USA composite, build shared-arc topology (like TopoJSON).
Output: work/topo.pkl  {ids, names, state, arcs(list of Nx2 float arrays), polys}
polys[i] = list of rings; ring = list of signed arc refs (~k means reversed)."""
import struct, math, pickle, sys
import numpy as np

SHP = sys.argv[1]; DBF = sys.argv[2]; OUT = sys.argv[3]

def read_dbf(path):
    b = open(path, 'rb').read()
    n = struct.unpack('<I', b[4:8])[0]; hl, rl = struct.unpack('<HH', b[8:12])
    fields = []; off = 32
    while b[off] != 0x0D:
        name = b[off:off+11].split(b'\0')[0].decode(); ln = b[off+16]
        fields.append((name, ln)); off += 32
    recs = []
    for i in range(n):
        r = b[hl+i*rl: hl+(i+1)*rl]; p = 1; d = {}
        for name, ln in fields:
            d[name] = r[p:p+ln].decode('latin-1').strip(); p += ln
        recs.append(d)
    return recs

def read_shp(path):
    b = open(path, 'rb').read(); off = 100; shapes = []
    while off < len(b):
        _, clen = struct.unpack('>ii', b[off:off+8]); off += 8
        rec = b[off:off+clen*2]; off += clen*2
        st = struct.unpack('<i', rec[:4])[0]
        if st == 0: shapes.append([]); continue
        nparts, npts = struct.unpack('<ii', rec[36:44])
        parts = list(struct.unpack('<%di' % nparts, rec[44:44+4*nparts])) + [npts]
        pts = np.frombuffer(rec[44+4*nparts:44+4*nparts+16*npts], dtype='<f8').reshape(-1, 2)
        shapes.append([pts[parts[k]:parts[k+1]].copy() for k in range(nparts)])
    return shapes

# ---- d3 conicEqualArea + albersUsa composite ----
R = math.pi/180
def conic(lon0rot, center, parallels, k, tx, ty):
    s0, s1 = math.sin(parallels[0]*R), math.sin(parallels[1]*R)
    n = (s0+s1)/2; c = 1 + s0*(2*n - s0); r0 = math.sqrt(c)/n
    def raw(lam, phi):
        r = np.sqrt(c - 2*n*np.sin(phi))/n
        return r*np.sin(lam*n), r0 - r*np.cos(lam*n)
    cx, cy = raw(center[0]*R, center[1]*R)
    def proj(lon, lat):
        l = (lon + lon0rot + 180) % 360 - 180
        x, y = raw(l*R, lat*R)
        return tx + (x - cx)*k, ty - (y - cy)*k
    return proj

K = 1070; TX, TY = 480, 250
lower48 = conic(96, (-0.6, 38.7), (29.5, 45.5), K, TX, TY)
alaska = conic(154, (-2, 58.5), (55, 65), 0.35*K, TX - 0.307*K, TY + 0.201*K)
hawaii = conic(157, (-3, 19.9), (8, 18), K, TX - 0.205*K, TY + 0.212*K)

recs = read_dbf(DBF); shapes = read_shp(SHP)
keep = []
for r, s in zip(recs, shapes):
    if r['STATEFP'] in ('60', '66', '69', '72', '78'): continue
    proj = alaska if r['STATEFP'] == '02' else hawaii if r['STATEFP'] == '15' else lower48
    rings = []
    for ring in s:
        x, y = proj(ring[:, 0], ring[:, 1])
        rings.append(np.round(np.stack([x, y], 1), 6))
    keep.append((r['GEOID'], r['NAME'], r['STATEFP'], rings))
keep.sort(key=lambda t: t[0])
print('counties', len(keep), 'points', sum(len(r) for k in keep for r in k[3]))

# ---- topology: find junctions, cut rings into arcs, dedupe ----
def key(p): return (round(p[0]*1e5), round(p[1]*1e5))
nbr = {}   # point key -> set of frozenset(prev,next) ; junction if >1 distinct
for _, _, _, rings in keep:
    for ring in rings:
        ks = [key(p) for p in ring[:-1]]
        m = len(ks)
        for i in range(m):
            pk = ks[i]; pair = frozenset((ks[i-1], ks[(i+1) % m]))
            s = nbr.get(pk)
            if s is None: nbr[pk] = {pair}
            elif pair not in s: s.add(pair)
junction = {k for k, s in nbr.items() if len(s) > 1}
# also: a point used by >=3 rings with same pair is impossible in valid topology
print('junctions', len(junction))

arcs = []; arcindex = {}
def add_arc(pts_keys, pts):
    fk = tuple(pts_keys); rk = fk[::-1]
    if fk in arcindex: return arcindex[fk]
    if rk in arcindex: return ~arcindex[rk]
    arcindex[fk] = len(arcs); arcs.append(pts); return len(arcs) - 1

polys = []
for gid, name, st, rings in keep:
    pr = []
    for ring in rings:
        pts = ring[:-1]; ks = [key(p) for p in pts]; m = len(ks)
        js = [i for i in range(m) if ks[i] in junction]
        refs = []
        if not js:
            # closed arc with no junction: canonicalize start at min key, orientation kept
            i0 = min(range(m), key=lambda i: ks[i])
            order = list(range(i0, m)) + list(range(0, i0)) + [i0]
            okeys = [ks[i] for i in order]
            # check reversed canonical too
            fk = tuple(okeys); rk = fk[::-1]
            if fk in arcindex: refs.append(arcindex[fk])
            elif rk in arcindex: refs.append(~arcindex[rk])
            else:
                # reversed ring would start at i0 too: build reversed order to compare later
                arcindex[fk] = len(arcs); arcs.append(pts[order]); refs.append(len(arcs) - 1)
        else:
            for a in range(len(js)):
                s, e = js[a], js[(a+1) % len(js)]
                idx = list(range(s, e+1)) if e > s else list(range(s, m)) + list(range(0, e+1))
                refs.append(add_arc([ks[i] for i in idx], pts[idx]))
        pr.append(refs)
    polys.append(pr)
print('arcs', len(arcs), 'arc points', sum(len(a) for a in arcs))
pickle.dump(dict(ids=[k[0] for k in keep], names=[k[1] for k in keep], state=[k[2] for k in keep],
                 arcs=arcs, polys=polys), open(OUT, 'wb'))
