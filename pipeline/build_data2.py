"""Build the multi-file site: site2/index.html, site2/data/core.bin, site2/data/v/*.bin, site2/data/c/*.bin"""
import pickle, csv, json, gzip, base64, os, glob, sys
import numpy as np
sys.path.insert(0, 'pipeline/cartogram')
from simplify import dp_mask

W = 'build'; OUT = 'site'
os.makedirs(f'{OUT}/data/v', exist_ok=True); os.makedirs(f'{OUT}/data/c', exist_ok=True)
T = pickle.load(open('data/geometry/topo_s.pkl', 'rb')); ids = T['ids']; N = len(ids)
old = json.loads(gzip.decompress(base64.b64decode(open('build/payload.b64').read())))

# ---------- shared-topology variants ----------
files = sorted(glob.glob('data/cartograms/contig_*.npz'))
_b = np.load('data/cartograms/base.npz'); base_offs = _b['base_offs']; base = _b['base_xy']
variants = {'geo': base}; meta = {}
def popw(metric, key):
    path = f'data/weights/pop/pop_{key}.csv' if metric == 'pop' else f'data/weights/w/{metric}_{key}.csv'
    d = {r['fips']: float(r['pop']) for r in csv.DictReader(open(path))}; return np.array([d.get(f, 0.0) for f in ids])
for f in files:
    name = os.path.basename(f)[:-4]; method, metric, key = name.split('_', 2)
    z = np.load(f)
    variants[name] = z['xy']
    e = z['err'].astype(float); w = popw(metric, key); w = w/w.sum()
    meta[name] = dict(method=method, metric=metric, key=key, wm=float(np.sum(w*np.abs(e))), w10=float(np.sum(w*(np.abs(e) < .10))))
    if method == 'soft':   # how far a softened map is from true population areas (by design)
        P = popw('pop', key); A = None
        meta[name]['note'] = 'not exact by design'
print(len(variants), 'shared variants')
narcs = len(base_offs)-1; TOL = 0.12
masks = []
for k in range(narcs):
    s, e = base_offs[k], base_offs[k+1]; m = np.zeros(e-s, bool)
    for v in variants.values(): m |= dp_mask(v[s:e], TOL)
    masks.append(m)
keep = np.concatenate(masks); new_offs = np.concatenate([[0], np.cumsum([m.sum() for m in masks])])
circles = {os.path.basename(f)[5:-4]: np.load(f) for f in sorted(glob.glob('data/circles/circ_*.npy'))}
allxy = np.concatenate([v[keep] for v in variants.values()] +
                       [np.stack([c[0]-c[2], c[1]-c[2]], 1) for c in circles.values()] + [np.stack([c[0]+c[2], c[1]+c[2]], 1) for c in circles.values()])
x0, y0 = allxy.min(0) - 1; x1, y1 = allxy.max(0) + 1
Q = int(32000/max(x1-x0, y1-y0)); NP = int(keep.sum()); print('points', NP, 'Q', Q)
def put(path, raw): open(path, 'wb').write(gzip.compress(raw, 9, mtime=0))
V = {}
for name, v in variants.items():
    q = np.round((v[keep] - [x0, y0])*Q).astype(np.int64); d = np.diff(np.vstack([[0, 0], q]), axis=0); assert np.abs(d).max() < 32767
    put(f'{OUT}/data/v/{name}.bin', d.astype('<i2').tobytes())
    if name == 'geo': V['geo'] = dict(kind='shared', file='data/v/geo.bin'); V['contig|land|all'] = dict(kind='shared', file='data/v/geo.bin', err=dict(wm=0.0, w10=1.0)); continue
    m = meta[name]; V[f"{m['method']}|{m['metric']}|{m['key']}"] = dict(kind='shared', file=f'data/v/{name}.bin', err=dict(wm=m['wm'], w10=m['w10']))
for name, c in circles.items():
    metric, key = name.split('_', 1)
    put(f'{OUT}/data/c/{name}.bin', c.astype('<f4').tobytes())
    V[f'circ|{metric}|{key}'] = dict(kind='circle', file=f'data/c/{name}.bin')

# ---------- weights for tooltips ----------
weights = {}
for kk in V:
    if kk == 'geo': continue
    method, metric, key = kk.split('|')
    wk = f'{metric}|{key}'
    if wk in weights or metric in ('pop', 'land'): continue
    w = popw(metric, key)
    if metric == 'gdp': w = np.round(w/1000, 1)          # $ thousands -> $ millions
    elif metric in ('ev', 'senate'): w = np.round(w, 4)
    else: w = np.round(w)
    weights[wk] = w.tolist()
for y, arr in old['pop'].items(): weights[f'pop|{y}'] = arr
cm = json.load(open('data/circles/circle_meta.json'))
cm['scales']['gdp'] *= 1000   # page stores GDP in $ millions; circle scale was computed in $ thousands
weights['land|all'] = cm['area']
for wk in list(weights):
    metric, key = wk.split('|')
    V[f'place|{metric}|{key}'] = dict(kind='place')
# edu shares for tooltip context
# ---------- contests: which weight key each metric uses ----------
def wmap(c):
    y = c['year']; w = {'pop': str(y), 'land': 'all'}
    if c['office'] == 'PRES': w['votes'] = str(y); w['ev'] = str(y)
    if c['office'] == 'SEN': w['senate'] = str(y)
    w['edu'] = '2000' if y <= 2004 else '2008-12' if y <= 2014 else '2019-23'
    w['gdp'] = '2001' if y < 2002 else str(min(y, 2024))   # BEA county GDP starts in 2001
    return w
contests = []
for c in old['contests']:
    c = dict(c); c['w'] = wmap(c); c.pop('popLabel', None); c.pop('partial', None); c.pop('cyear', None)
    contests.append(c)

metrics = [
 dict(key='land', label='Land area', unit='land area', short='Square kilometers of land', fmt='{} km²',
      desc='Area is proportional to land area (Albers equal-area projection). As Contiguous this is the ordinary map. Alaska and Hawaii are inset at their own scales, so they are drawn smaller than their true size in every view.'),
 dict(key='pop', label='Population', unit='residents', short='Residents (Census estimate)', fmt='{} residents',
      desc='Each county’s area is proportional to its resident population: the Census Bureau’s July 1 estimate for the election year (2026 uses the latest, July 2025). This is the default because every person counts once.'),
 dict(key='votes', label='Votes cast', unit='ballots', short='Presidential ballots counted', fmt='{} ballots',
      desc='Area is proportional to the total presidential ballots counted in the county (all candidates). This shows where the votes behind the result actually came from; turnout differences make it differ from population. Alaska reports by state-house district, so its statewide total is split across boroughs by population. Presidential races only, because other races aren’t held in every state.'),
 dict(key='ev', label='Electoral votes', unit='electoral weight', short='Its share of its state’s electoral votes', fmt='{} electoral votes', dp=3,
      desc='Each state’s electoral votes (House seats + 2; DC 3, using the apportionment in force that year) are split among its counties by population. Total area is 538 electoral votes, so small states look larger than in the population view. Presidential races only.'),
 dict(key='senate', label='Senate seats', unit='Senate weight', short='Its share of its state’s 2 senators', fmt='{} senators', dp=4,
      desc='Every state has 2 senators, so every state gets the same total area, split among its counties by population. This shows how Senate representation is distributed. Senate races only.'),
 dict(key='edu', label='College grads', unit='graduates', short='Adults 25+ with a bachelor’s degree', fmt='{} graduates',
      desc='Area is proportional to the number of adults 25 and older holding a bachelor’s degree or higher (USDA ERS: Census 2000 for elections through 2004, ACS 2008–12 5-year estimates through 2014, ACS 2019–23 after). It’s a count of people, so it adds up correctly across counties. Connecticut 2019–23 is split from planning regions to its old counties by population.'),
 dict(key='gdp', label='GDP', unit='GDP', short='Economic output, current dollars', fmt='${} million', dp=1,
      desc='Area is proportional to county GDP in current dollars (BEA, February 2026 release; county GDP starts in 2001, so 2000 uses 2001, and 2026 uses 2024). Virginia’s independent cities and Maui/Kalawao are published combined with neighbors and are split by population; Connecticut 2024 is split by 2023 shares.'),
]
methods = [
 dict(key='circ', label='Packed circles', short='Circles nudged apart so none overlap',
      desc='Dorling cartogram: each county is a circle whose area is exactly proportional to its value. Circles start at the county\u2019s center and are pushed apart until none overlap, so dense areas spread outward and a circle can sit well away from its county.'),
 dict(key='place', label='Circles in place', short='Circles centered on their county; overlaps blend',
      desc='Each circle is centered exactly on its county\u2019s geographic center, with area exactly proportional to its value. Circles may overlap. Where they do, the color shows the combined two-party share of the overlapping counties, with each county weighted by its votes per unit of circle area, so the overlap reflects the voters actually drawn there.'),
 dict(key='contig', label='Contiguous', short='Neighbors stay attached; shapes stretch',
      desc='Flow-based density-equalizing cartogram (Gastner, Seguy & More, 2018), first fitted at the state level and then refined county by county. Every county is one uniform block and borders stay connected, so shapes stretch to make room. Areas match values to within the error shown.'),
]
sources = [
 'President 2000–2024: MIT Election Data + Science Lab (MEDSL), County Presidential Election Returns 2000–2024.',
 'Senate, House, Governor 2016–2024: MEDSL official precinct returns summed to counties; Senate 2022 from MEDSL county returns.',
 'Senate and Governor 2000–2014: Amlani & Algara county returns (Electoral Studies, 2021); Alaska Senate from MEDSL statewide returns.',
 'Gaps in those sources: official state results (each one is listed under Details for its race).',
 'Population: U.S. Census Bureau county estimates (intercensal 2000–10, Vintage 2019, Vintage 2025).',
 'Education: USDA ERS county educational attainment (Census 2000, ACS 5-year).',
 'GDP: U.S. Bureau of Economic Analysis CAGDP1, current dollars.',
 'Boundaries: Census 2019 cartographic boundary file (1:500k).',
]
core = dict(frame=dict(x0=float(x0), y0=float(y0), q=Q), bbox=[float(x0), float(y0), float(x1), float(y1)], nPts=NP,
            arcOff=new_offs.tolist(), polys=T['polys'], names=T['names'], st=T['state'], ids=ids, states=old['states'],
            stateArcs=old['stateArcs'], variants=V, weights=weights, contests=contests, metrics=metrics, methods=methods,
            sources=sources, defaultKey='2024-pres', defaultMethod='circ', cent=cm['cent'], area=cm['area'], scales=cm['scales'])
put(f'{OUT}/data/core.bin', json.dumps(core, separators=(',', ':')).encode())
tot = sum(os.path.getsize(p) for p in glob.glob(f'{OUT}/**/*', recursive=True) if os.path.isfile(p))
print('variants', len(V), 'core KB', os.path.getsize(f'{OUT}/data/core.bin')//1024, 'total MB', round(tot/1e6, 1))
