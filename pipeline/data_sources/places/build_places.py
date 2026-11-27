"""Largest cities and towns in each county and state -> data/places/places.csv

Source: Census ACS 2020-2024 5-year, table B01003 (total population), table-based summary file, plus its
geography file for names. Run from the repo root with `python -P`. Inputs (build/downloads/census/):
  acsdt5y2024-b01003.dat, Geos20245YR.txt, ct-town-county-fips-list.csv (see data/places/README.md)

Which units count as a "city":
  - Most states: Census places, i.e. incorporated cities, towns and villages plus unincorporated communities
    (CDPs), using the part of each place that lies in the county (summary level 155).
  - New England, New York, New Jersey and Pennsylvania: county subdivisions (summary level 060), because there
    the towns, townships and boroughs are the municipalities and CDPs sit inside them. The five New York City
    counties use places instead, so they show New York City rather than their borough.
"""
import csv, collections, hashlib, pickle, re

DL = 'build/downloads/census'
OUT = 'data/places/places.csv'
TOP = 3
MCD_STATES = {'09', '23', '25', '33', '44', '50', '34', '42', '36'}   # CT ME MA NH RI VT NJ PA NY
NYC = {'36005', '36047', '36061', '36081', '36085'}
FIX = {'02063': '02261', '02066': '02261'}   # Chugach + Copper River -> the map's Valdez-Cordova
# County subdivisions that are not municipalities (unorganized territory, NH/VT/ME gores, grants, purchases).
NOT_TOWN = re.compile(r' (UT|unorganized territory|gore|grant|location|purchase|surplus|academy grant)$', re.I)
SUFFIX = re.compile(
    r' (city and borough|consolidated government|metropolitan government|metro government|unified government|'
    r'urban county|charter township|municipality|corporation|township|borough|village|plantation|city|town|CDP)$')
SAME_NAME = re.compile(r' \([^()]* Count(y|ies)\)$')   # 'Kailua CDP (Hawaii County)' -> 'Kailua CDP'
NAME_FIX = {  # consolidated city-county names -> the name people use
    'Nashville-Davidson': 'Nashville', 'Louisville/Jefferson County': 'Louisville', 'Lexington-Fayette': 'Lexington',
    'Athens-Clarke County': 'Athens', 'Augusta-Richmond County': 'Augusta', 'Macon-Bibb County': 'Macon',
    'Urban Honolulu': 'Honolulu', 'Butte-Silver Bow': 'Butte',
    'Anaconda-Deer Lodge County': 'Anaconda', 'Cusseta-Chattahoochee County': 'Cusseta',
    'Georgetown-Quitman County': 'Georgetown', 'Hartsville/Trousdale County': 'Hartsville',
    'Lynchburg, Moore County': 'Lynchburg',
    'Boise City': 'Boise', 'New York': 'New York City',
}


def check(ok, msg):
    print(('ok   ' if ok else 'FAIL ') + msg)
    if not ok: raise SystemExit(1)


def clean(name):
    n = SAME_NAME.sub('', name.replace(' (balance)', ''))
    for _ in range(2): n = SUFFIX.sub('', n)
    n = re.sub(r'^.+ \((.+)\)$', r'\1', n)   # 'El Paso de Robles (Paso Robles)' -> the common name
    return NAME_FIX.get(n, n)


T = pickle.load(open('data/geometry/topo_s.pkl', 'rb'))
ids = T['ids']; idset = set(ids)
pop = {}
for r in csv.DictReader(open(f'{DL}/acsdt5y2024-b01003.dat', encoding='utf-8'), delimiter='|'):
    pop[r['GEO_ID']] = int(r['B01003_E001'])
ct_town = {}   # 5-digit town cousub code -> old county FIPS
for r in csv.DictReader(open(f'{DL}/ct-town-county-fips-list.csv', encoding='utf-8-sig')):
    ct_town[r['FIPS'][5:]] = r['FIPS'][:5]
check(len(ct_town) == 169, f'CT crosswalk has 169 towns ({len(ct_town)})')

placename = {}                     # state+place -> whole-place name (summary level 160)
parts = collections.defaultdict(list)  # county FIPS -> [(city key, population inside the county)]
cnt = collections.Counter()           # place -> how many counties it touches
county_pop = {}
geos = [r for r in csv.DictReader(open(f'{DL}/Geos20245YR.txt', encoding='utf-8'), delimiter='|')
        if r['SUMLEVEL'] in ('050', '060', '155', '160') and r['STATE'] != '72']   # no Puerto Rico on the map
for r in geos:
    if r['SUMLEVEL'] == '160': placename[r['STATE'] + r['PLACE']] = clean(r['NAME'].rsplit(', ', 1)[0])
for r in geos:
    sl, s, c = r['SUMLEVEL'], r['STATE'], r['COUNTY']
    if sl == '050': county_pop[FIX.get(s + c, s + c)] = county_pop.get(FIX.get(s + c, s + c), 0) + pop[r['GEO_ID']]
    elif sl == '155':
        f = FIX.get(s + c, s + c)
        if s in MCD_STATES and f not in NYC: continue
        if placename[s + r['PLACE']].endswith(' County'): continue   # rest-of-county balances (Greeley County KS)
        parts[f].append((('p', s + r['PLACE']), pop[r['GEO_ID']]))
        cnt[s + r['PLACE']] += 1
    elif sl == '060' and s in MCD_STATES and r['COUSUB'] != '00000':
        f = ct_town[r['COUSUB']] if s == '09' else s + c
        if f in NYC: continue
        nm = r['NAME'].split(', ')[0]
        if NOT_TOWN.search(nm): continue
        parts[f].append((('m', s + r['COUSUB'], clean(nm)), pop[r['GEO_ID']]))
for f in [f for f in county_pop if f[:2] == '09' and f[2:] >= '110']: del county_pop[f]   # CT planning regions
county_pop.update({f: sum(p for _, p in parts[f]) for f in ids if f[:2] == '09'})


def name_of(key): return placename[key[1]] if key[0] == 'p' else key[2]


rows, empty = [], []
for f, cn in zip(ids, T['names']):
    top = sorted(parts.get(f, []), key=lambda e: (-e[1], name_of(e[0])))
    # A county that is one city (San Francisco, Denver, Virginia's independent cities) has nothing to add.
    top = [e for e in top if not (name_of(e[0]) == cn and e[1] >= 0.95 * county_pop.get(f, 1e18))]
    top = [e for e in top if e[1] > 0][:TOP]
    if not top: empty.append(f)
    for k, (key, p) in enumerate(top):
        part = int(key[0] == 'p' and cnt[key[1]] > 1)
        rows.append(dict(fips=f, rank=k + 1, name=name_of(key), pop=p, part=part))
# States: whole places (or towns), summed over the state's counties.
by_state = collections.defaultdict(collections.Counter)
for f in ids:
    for key, p in parts.get(f, []): by_state[f[:2]][key] += p
for s in sorted(by_state):
    for k, (key, p) in enumerate(sorted(by_state[s].items(), key=lambda e: (-e[1], name_of(e[0])))[:TOP]):
        rows.append(dict(fips=s, rank=k + 1, name=name_of(key), pop=p, part=0))

check(not set(parts) - idset, 'every county with cities is on the map')
check(len({r['fips'] for r in rows if len(r['fips']) == 2}) == 51, '51 states (with DC) have cities')
print(f'     {len(empty)} counties with no city listed: {" ".join(empty)}')
with open(OUT, 'w', newline='', encoding='utf-8') as fh:
    w = csv.DictWriter(fh, ['fips', 'rank', 'name', 'pop', 'part'], lineterminator='\n'); w.writeheader(); w.writerows(rows)
print(OUT, len(rows), 'rows, sha256', hashlib.sha256(open(OUT, 'rb').read()).hexdigest())
