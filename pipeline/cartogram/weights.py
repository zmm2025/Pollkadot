"""Write area weights: data/weights/pop/pop_<year>.csv and data/weights/w/<metric>_<key>.csv  (fips,pop)
  pop_<year>    : Census July-1 county population (data/pop/county_pop.csv) on the map's 3,142 units
                  (Chugach 02063 + Copper River 02066 = the map's single Valdez-Cordova 02261)
  votes_<year>  : total presidential ballots counted in the county (D+R+all others).
                  Alaska reports by state-house district, so its statewide total is split
                  across boroughs by population.
  ev_<year>     : state electoral votes x (county population / state population)
  senate_<year> : 2 x (county population / state population)  -> every state the same total
"""
import csv, json, gzip, base64, collections, os, pickle
W = 'build'; os.makedirs('data/weights/w', exist_ok=True)
T = pickle.load(open('data/geometry/topo_s.pkl', 'rb')); ids = T['ids']
# population on the map's units
_cp = collections.defaultdict(dict)
for r in csv.DictReader(open('data/pop/county_pop.csv')):
    f = '02261' if r['fips'] in ('02063', '02066') else r['fips']
    _cp[int(r['year'])][f] = _cp[int(r['year'])].get(f, 0) + int(r['pop'])
os.makedirs('data/weights/pop', exist_ok=True)
for y, d in _cp.items():
    assert sorted(d) == sorted(ids), (y, set(d) ^ set(ids))
    with open(f'data/weights/pop/pop_{y}.csv', 'w', newline='') as f:
        f.write('fips,pop\n'); [f.write(f'{k},{d[k]}\n') for k in sorted(ids)]
# GDP (BEA, $ thousands) and college graduates (USDA ERS) from data/metrics; a county missing from a
# year (Broomfield CO before it existed) gets 0
_g = collections.defaultdict(dict)
for r in csv.DictReader(open('data/metrics/gdp.csv')):
    _g[r['year']][r['fips']] = float(r['gdp_thousands_current_dollars'] or 0)
for y, d in _g.items():
    if int(y) % 2 and int(y) != 2001: continue   # even (election) years; 2001 stands in for 2000
    with open(f'data/weights/w/gdp_{y}.csv', 'w', newline='') as f:
        f.write('fips,pop\n'); [f.write(f'{k},{d.get(k, 0.0)}\n') for k in sorted(ids)]
_e = collections.defaultdict(dict)
for r in csv.DictReader(open('data/metrics/education.csv')):
    _e[r['period']][r['fips']] = float(r['bachelors_plus'])
for p, d in _e.items():
    with open(f'data/weights/w/edu_{p}.csv', 'w', newline='') as f:
        f.write('fips,pop\n'); [f.write(f'{k},{d.get(k, 0.0)}\n') for k in sorted(ids)]
def pop(y): return {r['fips']: int(r['pop']) for r in csv.DictReader(open(f'data/weights/pop/pop_{y}.csv'))}
def write(name, d):
    with open(f'data/weights/w/{name}.csv', 'w') as f:
        f.write('fips,pop\n'); [f.write(f'{k},{v:.6f}\n') for k, v in sorted(d.items())]

# House seats by state: 2010-census apportionment and 2020-census apportionment counted from the
# district files (2016-2020 elections use 2010 seats, 2022+ use 2020 seats).
hd = collections.defaultdict(set)
for r in csv.DictReader(open('data/results/house_districts.csv')):
    hd[(int(r['year']), r['state_po'])].add(r['district'])
ST = {'AL':'01','AK':'02','AZ':'04','AR':'05','CA':'06','CO':'08','CT':'09','DE':'10','DC':'11','FL':'12','GA':'13','HI':'15','ID':'16','IL':'17','IN':'18','IA':'19','KS':'20','KY':'21','LA':'22','ME':'23','MD':'24','MA':'25','MI':'26','MN':'27','MS':'28','MO':'29','MT':'30','NE':'31','NV':'32','NH':'33','NJ':'34','NM':'35','NY':'36','NC':'37','ND':'38','OH':'39','OK':'40','OR':'41','PA':'42','RI':'44','SC':'45','SD':'46','TN':'47','TX':'48','UT':'49','VT':'50','VA':'51','WA':'53','WV':'54','WI':'55','WY':'56'}
def seats(years):
    return {st: len(set().union(*[hd[(y, st)] for y in years])) for st in ST if st != 'DC'}
S2010 = seats((2016, 2018, 2020)); S2020 = seats((2022, 2024))
assert sum(S2010.values()) == 435 and sum(S2020.values()) == 435, (sum(S2010.values()), sum(S2020.values()))
# 2000-census seats (used for 2004 and 2008): undo the 2010 reapportionment changes
CH2010 = {'TX': 4, 'FL': 2, 'AZ': 1, 'GA': 1, 'NV': 1, 'SC': 1, 'UT': 1, 'WA': 1,
          'NY': -2, 'OH': -2, 'IL': -1, 'IA': -1, 'LA': -1, 'MA': -1, 'MI': -1, 'MO': -1, 'NJ': -1, 'PA': -1}
S2000 = {k: v - CH2010.get(k, 0) for k, v in S2010.items()}
assert sum(S2000.values()) == 435
# 1990-census seats (used for 2000): undo the 2000 reapportionment changes
CH2000 = {'AZ': 2, 'FL': 2, 'GA': 2, 'TX': 2, 'CA': 1, 'CO': 1, 'NV': 1, 'NC': 1,
          'NY': -2, 'PA': -2, 'CT': -1, 'IL': -1, 'IN': -1, 'MI': -1, 'MS': -1, 'OH': -1, 'OK': -1, 'WI': -1}
S1990 = {k: v - CH2000.get(k, 0) for k, v in S2000.items()}
assert sum(S1990.values()) == 435
CH2020 = {k: S2020[k]-S2010[k] for k in ST if k != 'DC' and S2020[k] != S2010[k]}
print('2020 apportionment changes', CH2020)
def ev(seatmap):
    e = {ST[k]: v + 2 for k, v in seatmap.items()}; e['11'] = 3; assert sum(e.values()) == 538; return e
EV = {2000: ev(S1990), 2004: ev(S2000), 2008: ev(S2000), 2012: ev(S2010), 2016: ev(S2010), 2020: ev(S2010), 2024: ev(S2020)}
json.dump({str(k): v for k, v in EV.items()}, open(f'data/weights/w/ev_tables.json', 'w'))

def share_weights(y, per_state):
    p = pop(y); tot = collections.Counter()
    for f, v in p.items(): tot[f[:2]] += v
    return {f: per_state[f[:2]]*v/tot[f[:2]] for f, v in p.items()}
for y, e in EV.items(): write(f'ev_{y}', share_weights(y, e))
for y in range(2000, 2027, 2): write(f'senate_{y}', share_weights(y, {s: 2 for s in set(f[:2] for f in ids)}))

# presidential votes cast, from the built page payload (already de-duplicated, AK statewide)
d = json.loads(gzip.decompress(base64.b64decode(open('build/payload.b64').read())))
for c in d['contests']:
    if c['office'] != 'PRES': continue
    y = c['year']; p = pop(y)
    tot = {f: c['dem'][i]+c['rep'][i]+c['oth'][i] for i, f in enumerate(ids)}
    ak = [f for f in ids if f[:2] == '02']; akv = tot[ak[0]]; akp = sum(p[f] for f in ak)
    for f in ak: tot[f] = akv*p[f]/akp
    tot['15005'] = 0.0   # Kalawao's votes are reported with Maui
    write(f'votes_{y}', tot)
    print(y, 'votes', round(sum(tot.values())))
print('done')
