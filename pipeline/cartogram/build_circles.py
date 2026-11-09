"""Dorling circles for every metric/key: work/k/circ_<metric>_<key>.npy  (cx, cy, r) float32.
One scale per metric (map area per unit of weight) so sizes compare across years."""
import sys, csv, os, numpy as np
sys.path.insert(0, 'pipeline/cartogram')
import dorling as dl
W = 'build'; ids = dl.T['ids']
def load(path): d = {r['fips']: float(r['pop']) for r in csv.DictReader(open(path))}; return np.array([d.get(f, 0.0) for f in ids])
PRES_YEARS = range(2000, 2025, 4)
jobs = {'land': [('all', None)], 'pop': [(str(y), f'data/weights/pop/pop_{y}.csv') for y in range(2000, 2027, 2)],
        'votes': [(str(y), f'data/weights/w/votes_{y}.csv') for y in PRES_YEARS],
        'ev': [(str(y), f'data/weights/w/ev_{y}.csv') for y in PRES_YEARS],
        'senate': [(str(y), f'data/weights/w/senate_{y}.csv') for y in range(2000, 2027, 2)],
        'edu': [(k, f'data/weights/w/edu_{k}.csv') for k in ('2000', '2008-12', '2019-23')],
        'gdp': [('2001', 'data/weights/w/gdp_2001.csv')] + [(str(y), f'data/weights/w/gdp_{y}.csv') for y in range(2002, 2025, 2)]}
FILL = 0.5
# One scale per metric: circles cover half the land area of a reference key. Scales already published in
# circle_meta.json are kept, so adding years doesn't resize (or force rebuilding) the existing layouts.
import json
old = json.load(open('data/circles/circle_meta.json'))['scales'] if os.path.exists('data/circles/circle_meta.json') else {}
scales = {}
for metric, lst in jobs.items():
    if metric in old: k = old[metric]
    else: ref = load(lst[len(lst)//2][1]) if metric != 'land' else dl.AREA; k = FILL*dl.AREA.sum()/ref.sum()
    scales[metric] = k
    for key, path in lst:
        out = f'data/circles/circ_{metric}_{key}.npy'
        if os.path.exists(out): continue
        w = dl.AREA if metric == 'land' else load(path); cx, cy, r = dl.circles(w, k, iters=2500)
        np.save(out, np.stack([cx, cy, r]).astype(np.float32))
        print(metric, key, 'max overlap', dl.overlap_report(cx, cy, r), flush=True)

json.dump(dict(scales=scales, cent=np.round(dl.CENT, 3).tolist(), area=np.round(dl.AREA, 4).tolist()), open('data/circles/circle_meta.json', 'w'))
