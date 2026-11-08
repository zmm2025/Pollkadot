"""Quick PNG preview of a cartogram: render.py topo.pkl carto.npz out.png"""
import pickle, sys
import numpy as np
from PIL import Image, ImageDraw
T = pickle.load(open(sys.argv[1], 'rb'))
xy = np.load(sys.argv[2])['xy'] if sys.argv[2] != 'geo' else np.concatenate(T['arcs'])
lens = [len(a) for a in T['arcs']]; offs = np.concatenate([[0], np.cumsum(lens)])
x0, y0 = xy.min(0); x1, y1 = xy.max(0); S = 1600/(x1-x0)
img = Image.new('RGB', (1600, int((y1-y0)*S)+2), 'white'); d = ImageDraw.Draw(img)
rng = np.random.default_rng(0)
for i, poly in enumerate(T['polys']):
    col = tuple(int(c) for c in rng.integers(80, 230, 3))
    for ring in poly:
        pts = []
        for a in ring:
            k = a if a >= 0 else ~a; p = xy[offs[k]:offs[k+1]]
            if a < 0: p = p[::-1]
            pts += [tuple(q) for q in ((p - [x0, y0])*S)]
        if len(pts) > 2: d.polygon(pts, fill=col, outline=(60, 60, 60))
img.save(sys.argv[3])
