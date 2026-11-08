"""Assemble the page payload: geometry variants + election contests + population.
usage: build_data.py  (paths fixed below)"""
import pickle, csv, json, gzip, base64, collections, os, sys
import numpy as np
sys.path.insert(0, 'pipeline/cartogram')
from simplify import dp_mask

W = 'build'; DATA = 'data'; os.makedirs(W, exist_ok=True)
YEARS = [2008, 2010, 2012, 2014, 2016, 2018, 2020, 2022, 2024, 2026]
T = pickle.load(open('data/geometry/topo_s.pkl', 'rb'))
ids = T['ids']; N = len(ids); idx = {f: i for i, f in enumerate(ids)}
ST = {'AL':'01','AK':'02','AZ':'04','AR':'05','CA':'06','CO':'08','CT':'09','DE':'10','DC':'11','FL':'12','GA':'13','HI':'15','ID':'16','IL':'17','IN':'18','IA':'19','KS':'20','KY':'21','LA':'22','ME':'23','MD':'24','MA':'25','MI':'26','MN':'27','MS':'28','MO':'29','MT':'30','NE':'31','NV':'32','NH':'33','NJ':'34','NM':'35','NY':'36','NC':'37','ND':'38','OH':'39','OK':'40','OR':'41','PA':'42','RI':'44','SC':'45','SD':'46','TN':'47','TX':'48','UT':'49','VT':'50','VA':'51','WA':'53','WV':'54','WI':'55','WY':'56'}
NAMES = {'01':'Alabama','02':'Alaska','04':'Arizona','05':'Arkansas','06':'California','08':'Colorado','09':'Connecticut','10':'Delaware','11':'District of Columbia','12':'Florida','13':'Georgia','15':'Hawaii','16':'Idaho','17':'Illinois','18':'Indiana','19':'Iowa','20':'Kansas','21':'Kentucky','22':'Louisiana','23':'Maine','24':'Maryland','25':'Massachusetts','26':'Michigan','27':'Minnesota','28':'Mississippi','29':'Missouri','30':'Montana','31':'Nebraska','32':'Nevada','33':'New Hampshire','34':'New Jersey','35':'New Mexico','36':'New York','37':'North Carolina','38':'North Dakota','39':'Ohio','40':'Oklahoma','41':'Oregon','42':'Pennsylvania','44':'Rhode Island','45':'South Carolina','46':'South Dakota','47':'Tennessee','48':'Texas','49':'Utah','50':'Vermont','51':'Virginia','53':'Washington','54':'West Virginia','55':'Wisconsin','56':'Wyoming'}
FIX = {'46113': '46102', '02270': '02158', '51515': '51019', '02261': '02261', '02063': '02261', '02066': '02261'}
AK = [i for i, f in enumerate(ids) if f[:2] == '02']
MAUI, KALAWAO = idx['15009'], idx['15005']

# ---------------- geometry ----------------
def load_variant(y):
    return np.load(f'data/cartograms/contig_pop_{y}.npz')
_b = np.load('data/cartograms/base.npz'); base_offs = _b['base_offs']; base = _b['base_xy']
variants = {'geo': base}; errs = {}
for y in YEARS:
    z = load_variant(y)
    variants[str(y)] = z['xy']
    e = z['err'].astype(float); P = np.array([1.0]*N)
    pop = {r['fips']: float(r['pop']) for r in csv.DictReader(open(f'data/weights/pop/pop_{y}.csv'))}
    P = np.array([pop[f] for f in ids]); w = P/P.sum()
    errs[str(y)] = dict(wm=float(np.sum(w*np.abs(e))), med=float(np.median(np.abs(e))),
                        within10=float(np.mean(np.abs(e) < .10)), popWithin10=float(np.sum(w*(np.abs(e) < .10))))
narcs = len(base_offs)-1
TOL = 0.12
keep_masks = []
for k in range(narcs):
    s, e = base_offs[k], base_offs[k+1]; m = np.zeros(e-s, bool)
    for v in variants.values(): m |= dp_mask(v[s:e], TOL)
    keep_masks.append(m)
keep = np.concatenate(keep_masks)
new_offs = np.concatenate([[0], np.cumsum([m.sum() for m in keep_masks])])
allxy = np.concatenate([v[keep] for v in variants.values()])
x0, y0 = allxy.min(0) - 1; x1, y1 = allxy.max(0) + 1
Q = int(32000/max(x1-x0, y1-y0))
def enc(v):
    q = np.round((v[keep] - [x0, y0])*Q).astype(np.int64)
    d = np.diff(np.vstack([[0, 0], q]), axis=0); assert np.abs(d).max() < 32767
    return base64.b64encode(d.astype('<i2').tobytes()).decode()
NP = int(keep.sum()); print('final points', NP, 'Q', Q)
# state boundary arcs: arcs used once (outer edge) or shared by counties of different states
use = collections.defaultdict(list)
for i, poly in enumerate(T['polys']):
    for ring in poly:
        for a in ring: use[a if a >= 0 else ~a].append(T['state'][i])
stateArcs = [k for k in range(narcs) if len(use[k]) == 1 or len(set(use[k])) > 1]

# ---------------- population ----------------
popY = {}
for y in YEARS:
    pop = {r['fips']: int(r['pop']) for r in csv.DictReader(open(f'data/weights/pop/pop_{y}.csv'))}
    popY[str(y)] = [pop[f] for f in ids]

# ---------------- results ----------------
contests = []
def blank(): return np.zeros((N, 3), np.int64)
def finish(year, office, arr, statewide=(), special=0, note='', cand=None, partial=False, label=None, src=''):
    arr = arr.copy(); dedupe = np.zeros(N, np.int8)
    for st, (d, r, o) in dict(statewide).items():
        rows = [i for i, f in enumerate(ids) if f[:2] == st]
        for j, i in enumerate(rows): arr[i] = (d, r, o); dedupe[i] = 1 if j else 0
    if arr[KALAWAO].sum() == 0 and arr[MAUI].sum() > 0:
        arr[KALAWAO] = arr[MAUI]; dedupe[KALAWAO] = 1
    ol = {'PRES': 'President', 'SEN': 'Senate', 'HOUSE': 'House', 'GOV': 'Governor'}[office]
    key = f'{year}-{office.lower()}' + ('-special' if special == 1 else '')
    contests.append(dict(key=key, office=office, year=year, cyear=year, special=special, officeLabel=ol,
        label=label or (f'{year} special' if special == 1 else str(year)),
        title=f'{year} {ol}' + (' (special elections)' if special == 1 else ''),
        popLabel=f'July {year}' if year < 2026 else 'July 2025 (latest)',
        note=note, partial=partial, src=src,
        dem=arr[:, 0].tolist(), rep=arr[:, 1].tolist(), oth=arr[:, 2].tolist(),
        dedupe=dedupe.tolist(), statewide={s: True for s in dict(statewide)}, cand=cand or {}))

def add(arr, f, d, r, o):
    f = FIX.get(f, f)
    if f in idx: arr[idx[f]] += (d, r, o); return True
    return False

unplaced = collections.Counter()
PRESC = {2008: dict(d='Obama', r='McCain'), 2012: dict(d='Obama', r='Romney'), 2016: dict(d='Clinton', r='Trump'),
         2020: dict(d='Biden', r='Trump'), 2024: dict(d='Harris', r='Trump')}
# President 2008-2016: MEDSL county presidential returns
medsl = collections.defaultdict(blank); ak_pres = collections.defaultdict(lambda: [0, 0, 0])
for r in csv.DictReader(open('data/raw/medsl/countypres_2000-2016.csv')):
    y = int(r['year'])
    if y not in (2008, 2012, 2016): continue
    v = r['candidatevotes']; v = 0 if v in ('NA', '') else int(float(v))
    col = 0 if r['party'] == 'democrat' else 1 if r['party'] == 'republican' else 2
    t = [0, 0, 0]; t[col] = v
    if r['state_po'] == 'AK': ak_pres[y][col] += v; continue
    f = r['FIPS']
    if f == 'NA': unplaced[(y, 'PRES')] += v; continue
    f = f.zfill(5)
    if f in ('2938000', '36000') and r['state_po'] == 'MO': f = '29095'   # Kansas City reported separately from Jackson County
    if not add(medsl[y], f, *t): unplaced[(y, 'PRES', f)] += v
for y in (2008, 2012, 2016):
    finish(y, 'PRES', medsl[y], statewide={'02': tuple(ak_pres[y])}, src='MEDSL county presidential returns 2000-2016', cand={'*': PRESC[y]})

# President 2020, 2024: tonmcg (Alaska districts summed statewide; CT 2024 from MEDSL old counties)
TM = 'data/raw/tonmcg'
medsl_ak = {}; medsl_ksme = []
if os.path.exists(f'{DATA}/results/county_results.csv'):
    for r in csv.DictReader(open(f'{DATA}/results/county_results.csv')):
        if r['office'] == 'PRES' and r['fips'] == '02000': medsl_ak[(int(r['year']), '02000')] = [int(r['dem']), int(r['rep']), int(r['oth'])]
        if r['office'] == 'PRES' and r['year'] == '2020' and r['state_po'] in ('KS', 'ME'): medsl_ksme.append(r)
for y in (2020, 2024):
    arr = blank(); ak = [0, 0, 0]
    for r in csv.DictReader(open(f'{TM}/{y}_US_County_Level_Presidential_Results.csv')):
        f = r['county_fips'].zfill(5); d, rp, t = int(float(r['votes_dem'])), int(float(r['votes_gop'])), int(float(r['total_votes']))
        o = t - d - rp
        if f[:2] == '02': ak[0] += d; ak[1] += rp; ak[2] += o; continue
        if y == 2024 and f[:3] == '091': continue
        if y == 2020 and f[:2] in ('20', '23'): continue   # tonmcg KS/ME 2020 differ from certified; MEDSL matches
        if f[:2] == '11': f = '11001'   # DC reported by ward
        if not add(arr, f, d, rp, o): unplaced[(y, 'PRES', f)] += t
    if y == 2020:
        for r in medsl_ksme: add(arr, r['fips'], int(r['dem']), int(r['rep']), int(r['oth']))
    if (y, '02000') in medsl_ak: ak = medsl_ak[(y, '02000')]   # MEDSL statewide AK matches certified totals
    finish(y, 'PRES', arr, statewide={'02': tuple(ak)}, src='tonmcg county presidential results', cand={'*': PRESC[y]})
    if y == 2024: ct_pending = len(contests)-1

# MEDSL 2018-2024 Senate / House / Governor (+ CT 2024 President)
CR = f'{DATA}/results/county_results.csv'
races = collections.defaultdict(dict)
import re
def nm(x):
    x = (x or '').strip()
    if not x: return ''
    t = x.title()
    t = re.sub(r"\bMc([a-z])", lambda m: 'Mc' + m.group(1).upper(), t)
    t = re.sub(r"\b(Ii|Iii|Iv|Jr|Sr)\b(?!\.)", lambda m: {'Ii':'II','Iii':'III','Iv':'IV'}.get(m.group(1), m.group(1)+'.'), t)
    return t
if os.path.exists(f'{DATA}/results/races.csv'):
    for r in csv.DictReader(open(f'{DATA}/results/races.csv')):
        st = ST.get(r['state_po']);
        if not st: continue
        races[(int(r['year']), r['office'], int(r['special']))][st] = dict(d=nm(r['dem_cand']), r=nm(r['rep_cand']), o=nm(r['top_other_cand']) if r['top_other_cand'].upper() not in ('WRITEIN', 'OTHER', '') else '')
if os.path.exists(CR):
    groups = collections.defaultdict(blank); ak = collections.defaultdict(lambda: [0, 0, 0]); ct24 = blank()
    for r in csv.DictReader(open(CR)):
        y = int(r['year']); off = r['office']; sp = int(r['special']); f = r['fips'].zfill(5)
        d, rp, o = int(r['dem']), int(r['rep']), int(r['oth'])
        if off == 'PRES':
            if y == 2024 and f[:2] == '09': add(ct24, f, d, rp, o)
            continue
        if sp == 2 or (off == 'HOUSE' and sp): continue
        k = (y, off, sp)
        if f[:2] == '02': ak[k][0] += d; ak[k][1] += rp; ak[k][2] += o; continue
        if not add(groups[k], f, d, rp, o): unplaced[(y, off, f)] += d+rp+o
    c = contests[ct_pending]
    for i in range(N):
        if ids[i][:2] == '09': c['dem'][i], c['rep'][i], c['oth'][i] = map(int, ct24[i])
    hd = collections.defaultdict(lambda: [0, 0])
    if os.path.exists(f'{DATA}/results/house_districts.csv'):
        for r in csv.DictReader(open(f'{DATA}/results/house_districts.csv')):
            hd[int(r['year'])][0] += 1; hd[int(r['year'])][1] += 1 - int(r['contested'])
    for k in sorted(groups.keys() | ak.keys()):
        y, off, sp = k; arr = groups.get(k, blank())
        sw = {'02': tuple(ak[k])} if sum(ak[k]) else {}
        nst = len({ids[i][:2] for i in range(N) if arr[i].sum() > 0} | set(sw))
        note = ''
        if off == 'SEN': note = f'{nst} states held {"special " if sp else ""}Senate elections.'
        if off == 'GOV': note = f'{nst} states elected governors.'
        if off == 'HOUSE':
            n, u = hd[y]; note = f'Each county shows the sum of all U.S. House votes cast in it.' + (f' {u} of {n} districts lacked a D-vs-R contest, which tilts their counties toward the party that ran.' if n else '')
        finish(y, off, arr, statewide=sw, special=sp, note=note, cand=races.get(k, {}), src='MEDSL precinct returns')
else:
    print('WARNING: no MEDSL county results yet')
for k, v in sorted(unplaced.items(), key=lambda kv: -kv[1])[:15]: print('unplaced', k, v)

# data-quality notes from the MEDSL aggregation (major / missing issues only)
STN = {v: k for k, v in ST.items()}
dq = []
if os.path.exists(f'{DATA}/results/data_quality.csv'):
    dq = [r for r in csv.DictReader(open(f'{DATA}/results/data_quality.csv')) if r['severity'] in ('major', 'missing')]
for c in contests:
    if c['office'] == 'PRES' and c['year'] != 2024: continue   # PRES 2008-2020 do not come from MEDSL precinct files
    msgs = []
    for r in dq:
        if int(r['year']) != c['year']: continue
        offs = r['office'].replace(';', ' ').split()
        if 'ALL' not in offs and c['office'] not in offs: continue
        sts = r['state_po'].replace(';', ' ').split()
        if c['office'] == 'PRES' and 'CT' not in sts: continue   # 2024 PRES uses MEDSL only for Connecticut
        # only mention states that actually held this race
        keep_sts = []
        for x in sts:
            stf = ST.get(x, '')
            had = any(c['dem'][i] + c['rep'][i] + c['oth'][i] > 0 for i, f in enumerate(ids) if f[:2] == stf)
            if had or (c['office'] == 'HOUSE' and not c['special']) or ('ALL' not in offs and not c['special']): keep_sts.append(x)
        if not keep_sts: continue
        if c['year'] == 2024 and 'LA' in keep_sts and c['office'] != 'PRES':
            for i, f in enumerate(ids):
                if f[:2] == '22': c['dem'][i] = c['rep'][i] = c['oth'][i] = 0
            msgs.append('Louisiana is left blank: its early votes are missing from the precinct source, which would skew every parish.'); continue
        names = [NAMES.get(ST.get(x, ''), x) for x in keep_sts]
        txt = re.sub(r'^MEDSL README: ', '', r['issue']).replace('->', '→').rstrip('.')
        msgs.append(f"{', '.join(names)}: {txt}.")
    c['gaps'] = list(dict.fromkeys(msgs))

order = {'PRES': 0, 'SEN': 1, 'HOUSE': 2, 'GOV': 3}
contests.sort(key=lambda c: (order[c['office']], c['year'], c['special']))
for c in contests:
    d = sum(v for v, dd in zip(c['dem'], c['dedupe']) if not dd); r = sum(v for v, dd in zip(c['rep'], c['dedupe']) if not dd)
    print(f"{c['key']:20s} D {d:>11,} R {r:>11,}")

payload = dict(frame=dict(x0=float(x0), y0=float(y0), q=Q), bbox=[float(x0), float(y0), float(x1), float(y1)],
    nPts=NP, arcOff=new_offs.tolist(), variants={k: enc(v) for k, v in variants.items()},
    polys=T['polys'], names=T['names'], st=T['state'], ids=ids, states={k: dict(name=v) for k, v in NAMES.items()},
    stateArcs=stateArcs, pop=popY, cartoErr=errs, contests=contests, defaultKey='2024-pres')
raw = json.dumps(payload, separators=(',', ':')).encode()
gz = gzip.compress(raw, 9, mtime=0)
print('json', len(raw)//1024, 'KB  gzip', len(gz)//1024, 'KB')
open('build/payload.b64', 'w').write(base64.b64encode(gz).decode())
