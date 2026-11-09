"""Merge every results source into data/results/.

Sources, in order of preference (see data/results/README.md):
  1. MIT Election Data + Science Lab (MEDSL)
     - President 2000-2024: County Presidential Election Returns 2000-2024
     - Senate / House / Governor 2016-2024: precinct returns summed to counties
       (build/work/medsl_*.csv from pipeline/data_sources/medsl/)
     - Senate 2022: MEDSL's county-level Senate file (taken straight from state county results)
     - Alaska Senate 2000-2014: MEDSL statewide Senate returns
  2. Amlani & Algara county returns: Senate and Governor 2000-2014, and counties MEDSL lacks in 2016-2020
  3. Official state results, only where 1 and 2 are missing or incomplete (data/results/patches/)

usage: python -P pipeline/build_results.py
writes data/results/{county_results,races,house_districts}.csv
"""
import glob, json, os, pickle, re, sys
import numpy as np, pandas as pd

DV = 'build/downloads/dataverse'
W = 'build/work'
R = 'data/results'
ids = pickle.load(open('data/geometry/topo_s.pkl', 'rb'))['ids']
UNITS = set(ids) | {'02000'}
ST = {'AL':'01','AK':'02','AZ':'04','AR':'05','CA':'06','CO':'08','CT':'09','DE':'10','DC':'11','FL':'12','GA':'13','HI':'15','ID':'16','IL':'17','IN':'18','IA':'19','KS':'20','KY':'21','LA':'22','ME':'23','MD':'24','MA':'25','MI':'26','MN':'27','MS':'28','MO':'29','MT':'30','NE':'31','NV':'32','NH':'33','NJ':'34','NM':'35','NY':'36','NC':'37','ND':'38','OH':'39','OK':'40','OR':'41','PA':'42','RI':'44','SC':'45','SD':'46','TN':'47','TX':'48','UT':'49','VT':'50','VA':'51','WA':'53','WV':'54','WI':'55','WY':'56'}
FIPS_FIX = {'46113': '46102', '51515': '51019', '51560': '51005', '2938000': '29095', '36000': '29095', '29380': '29095'}
COLS = ['year', 'office', 'special', 'state_po', 'fips', 'dem', 'rep', 'oth', 'total', 'source']
log = []


def say(msg):
    log.append(msg); print(msg)


def unit(fips, st):
    """Map a source FIPS code to a map unit; anything unplaceable becomes the statewide row SS000."""
    f = str(fips).strip().replace('.0', '')
    f = FIPS_FIX.get(f, f)
    f = f.zfill(5) if f.isdigit() and len(f) <= 5 else f
    if st == 'AK': return '02000'
    if f in UNITS and f[:2] == ST[st]: return f
    return ST[st] + '000'


def finish(df, source):
    df = df.groupby(['year', 'office', 'special', 'state_po', 'fips'], as_index=False)[['dem', 'rep', 'oth']].sum()
    for c in ('dem', 'rep', 'oth'): df[c] = df[c].round().astype(np.int64)
    df['total'] = df.dem + df.rep + df.oth
    df['source'] = source
    return df[COLS]


# ---------------------------------------------------------------- 1a. President 2000-2024 (MEDSL county)
META = re.compile(r'^(TOTAL VOTES|UNDERVOTE|OVERVOTE|SPOILED|BLANK|REGISTERED|BALLOTS)', re.I)
cp = pd.read_csv(f'{DV}/countypres/countypres_2000-2024.csv', dtype=str, keep_default_na=False)
cp['v'] = pd.to_numeric(cp.candidatevotes, errors='coerce')
say(f'countypres: dropped {cp.v.isna().sum()} rows with non-numeric votes, '
    f'{cp.candidate.str.match(META).sum()} non-candidate rows ({cp[cp.candidate.str.match(META)].v.sum():,.0f} votes)')
cp = cp[cp.v.notna() & ~cp.candidate.str.match(META)]
# A county-candidate has either one TOTAL row, vote-method rows, or both; when both, TOTAL is the count.
k = ['year', 'state_po', 'county_fips', 'candidate', 'party']
cp['is_tot'] = cp['mode'].eq('TOTAL')
has_tot = cp.groupby(k).is_tot.transform('any')
cp = cp[cp.is_tot | ~has_tot]
cp['fips'] = [unit(f, s) for f, s in zip(cp.county_fips, cp.state_po)]
cp['dem'] = np.where(cp.party == 'DEMOCRAT', cp.v, 0)
cp['rep'] = np.where(cp.party == 'REPUBLICAN', cp.v, 0)
cp['oth'] = np.where(~cp.party.isin(['DEMOCRAT', 'REPUBLICAN']), cp.v, 0)
cp['year'] = cp.year.astype(int); cp['office'] = 'PRES'; cp['special'] = 0
pres = finish(cp, 'MEDSL county presidential returns')
# Alaska is one map unit: use MEDSL's statewide presidential totals (the 2004 district rows in the county
# file add up to ~1.6x the certified total)
sp_ = pd.read_csv(f'{DV}/pres_statewide/1976-2024-president.csv', dtype=str, keep_default_na=False)
sp_ = sp_[(sp_.state_po == 'AK') & sp_.year.astype(int).isin(sorted(set(pres.year)))]
sp_['v'] = sp_.candidatevotes.astype(float); pp = sp_.party_simplified.str.upper()
sp_['dem'] = np.where(pp == 'DEMOCRAT', sp_.v, 0); sp_['rep'] = np.where(pp == 'REPUBLICAN', sp_.v, 0)
sp_['oth'] = np.where(~pp.isin(['DEMOCRAT', 'REPUBLICAN']), sp_.v, 0)
sp_['year'] = sp_.year.astype(int); sp_['office'] = 'PRES'; sp_['special'] = 0; sp_['fips'] = '02000'
pres = pd.concat([pres[pres.state_po != 'AK'], finish(sp_, 'MEDSL statewide presidential returns')])
# State-years where the county file disagrees with the certified result and Amlani & Algara matches it
PRES_AA_REPLACE = {(2004, 'ME'), (2004, 'MS')}
pcand = (cp[cp.party.isin(['DEMOCRAT', 'REPUBLICAN'])].groupby(['year', 'party', 'candidate']).v.sum()
         .reset_index().sort_values('v').drop_duplicates(['year', 'party'], keep='last'))
for (y, p), g in pcand.groupby(['year', 'party']):
    say(f'  PRES {y} {p[:3]} {g.candidate.iloc[0]} {g.v.iloc[0]:,.0f}')

# ---------------------------------------------------------------- 1b. Senate/House/Governor 2016-2024 (MEDSL precincts)
med = pd.read_csv(f'{W}/medsl_county_results.csv', dtype={'fips': str})
med = med[med.office != 'PRES']
med['fips'] = [unit(f, s) for f, s in zip(med.fips, med.state_po)]
med = finish(med, 'MEDSL precinct returns')
mraces = pd.read_csv(f'{W}/medsl_races.csv', dtype=str, keep_default_na=False)
mraces = mraces[mraces.office != 'PRES']

# ---------------------------------------------------------------- 1c. Senate 2022 (MEDSL county-level file)
s22 = pd.read_csv(f'{DV}/senate_county_2022/senate_2022.csv', dtype=str, keep_default_na=False)
s22 = s22[s22.stage.str.upper().eq('GEN')]
s22['v'] = s22.candidatevotes.astype(float)
s22['is_tot'] = s22['mode'].eq('TOTAL')
s22 = s22[s22.is_tot | ~s22.groupby(['state_po', 'county_fips', 'special', 'candidate']).is_tot.transform('any')]
s22['fips'] = [unit(f, s) for f, s in zip(s22.county_fips, s22.state_po)]
s22['year'] = 2022; s22['office'] = 'SEN'; s22['special'] = s22.special.str.upper().eq('TRUE').astype(int)
ps = s22.party_simplified.str.upper()
# same party rules as the precinct build: Utah's McMullin and other independents are oth
s22['dem'] = np.where(ps == 'DEMOCRAT', s22.v, 0); s22['rep'] = np.where(ps == 'REPUBLICAN', s22.v, 0)
s22['oth'] = np.where(~ps.isin(['DEMOCRAT', 'REPUBLICAN']), s22.v, 0)
s22 = finish(s22, 'MEDSL county Senate returns 2022')
# use it for every state-race where it has at least as many counties as the precinct build
for (sp, st), g in s22.groupby(['special', 'state_po']):
    m = (med.year == 2022) & (med.office == 'SEN') & (med.special == sp) & (med.state_po == st)
    n_med = (med[m & ~med.fips.str.endswith('000')].total > 0).sum()
    n_cty = (g[~g.fips.str.endswith('000')].total > 0).sum()
    if n_cty >= n_med or st == 'AK':
        if n_cty > n_med: say(f'2022 SEN {st} sp{sp}: county file has {n_cty} counties vs precinct {n_med}')
        med = pd.concat([med[~m], g])

# ---------------------------------------------------------------- 2. Amlani & Algara Senate/Governor
import pyreadr
AA = {'PRES': ('dataverse_shareable_presidential_county_returns_1868_2020', 'pres_elections_release'),
      'SEN': ('dataverse_shareable_us_senate_county_returns_1908_2020', 'senate_elections_release'),
      'GOV': ('dataverse_shareable_gubernatorial_county_returns_1865_2020', 'gov_elections_release')}
AA_INDEPENDENT_CODED_D = {('SEN', 2006, 'VT'), ('SEN', 2012, 'VT'), ('SEN', 2012, 'ME')}   # Sanders, King
AA_NON_NOVEMBER = {('SEN', 2010, 'MA')}   # January 2010 special
aa_rows, aa_cands = [], []
for off, (fn, obj) in AA.items():
    a = pyreadr.read_r(f'{DV}/amlani_algara/{fn}.Rdata')[obj]
    a = a[(a.election_year >= 2000) & (a.election_year % 2 == 0)].copy()
    a['year'] = a.election_year.astype(int); a['office'] = off
    a['special'] = (a.election_type == 'S').astype(int)
    a = a[[(off, y, s) not in AA_NON_NOVEMBER for y, s in zip(a.year, a.state)]]
    a['state_po'] = a.state
    a['fips'] = [unit(f, s) for f, s in zip(a.fips, a.state)]
    d = a.democratic_raw_votes.fillna(0); r = a.republican_raw_votes.fillna(0)
    t = a.raw_county_vote_totals.fillna(d + r)
    ind = np.array([(off, y, s) in AA_INDEPENDENT_CODED_D for y, s in zip(a.year, a.state)])
    a['dem'] = np.where(ind, 0, d); a['rep'] = r; a['oth'] = (t - d - r).clip(lower=0) + np.where(ind, d, 0)
    aa_rows.append(finish(a, 'Amlani & Algara county returns'))
    nm = lambda x: '' if x is None or (isinstance(x, float) and np.isnan(x)) else (' '.join(reversed([p.strip() for p in x.split(',', 1)])) if ',' in x else x)
    c = a.groupby(['year', 'office', 'special', 'state_po']).agg(dc=('dem_nominee', 'first'), rc=('rep_nominee', 'first')).reset_index()
    c['dem_cand'] = [('' if (off, y, s) in AA_INDEPENDENT_CODED_D else nm(x)) for y, s, x in zip(c.year, c.state_po, c.dc)]
    c['top_other_cand'] = [(nm(x) if (off, y, s) in AA_INDEPENDENT_CODED_D else '') for y, s, x in zip(c.year, c.state_po, c.dc)]
    c['rep_cand'] = c.rc.map(nm)
    aa_cands.append(c[['year', 'office', 'special', 'state_po', 'dem_cand', 'rep_cand', 'top_other_cand']])
aa = pd.concat(aa_rows); aac = pd.concat(aa_cands)
aac = aac[aac.office != 'PRES']
for y, st in sorted(PRES_AA_REPLACE):
    g = aa[(aa.office == 'PRES') & (aa.year == y) & (aa.state_po == st)]
    m = (pres.year == y) & (pres.state_po == st)
    say(f'replace {y} PRES {st}: MEDSL county file D {pres[m].dem.sum():,} R {pres[m].rep.sum():,} -> Amlani & Algara D {g.dem.sum():,} R {g.rep.sum():,}')
    pres = pd.concat([pres[~m], g.assign(source='Amlani & Algara county returns (MEDSL county file off)')])
aa = aa[aa.office != 'PRES']
early = aa[aa.year <= 2014]
# Alaska is absent from Amlani & Algara: Senate from MEDSL's statewide file (Governor comes from patches)
ss = pd.read_csv(f'{DV}/senate_statewide/1976-2024-senate-state.csv', dtype=str, keep_default_na=False)
ss = ss[(ss.state_po == 'AK') & ss.year.astype(int).between(2000, 2014) & ss.stage.str.upper().eq('GEN')]
ss['v'] = ss.candidatevotes.astype(float); ps = ss.party_simplified.str.upper()
ss['year'] = ss.year.astype(int); ss['office'] = 'SEN'; ss['special'] = ss.special.str.upper().eq('TRUE').astype(int)
ss['fips'] = '02000'
ss['dem'] = np.where(ps == 'DEMOCRAT', ss.v, 0); ss['rep'] = np.where(ps == 'REPUBLICAN', ss.v, 0)
ss['oth'] = np.where(~ps.isin(['DEMOCRAT', 'REPUBLICAN']), ss.v, 0)
early = pd.concat([early, finish(ss, 'MEDSL statewide Senate returns')])
akc = (ss.assign(p=ps).sort_values('v').groupby(['year', 'office', 'special', 'state_po', 'p']).candidate.last().unstack('p').reset_index())
akc['dem_cand'] = akc.get('DEMOCRAT', '').fillna('').str.title(); akc['rep_cand'] = akc.get('REPUBLICAN', '').fillna('').str.title()
akc['top_other_cand'] = ''
aac = pd.concat([aac, akc[['year', 'office', 'special', 'state_po', 'dem_cand', 'rep_cand', 'top_other_cand']]])

# Fill: counties MEDSL lacks in 2016-2020 Senate/Governor races, from Amlani & Algara
late = aa[aa.year >= 2016]
filled = []
for key, g in late.groupby(['year', 'office', 'special', 'state_po']):
    y, off, sp, st = key
    m = (med.year == y) & (med.office == off) & (med.special == sp) & (med.state_po == st)
    have = set(med[m & (med.total > 0)].fips)
    if not m.any():
        add = g
    else:
        add = g[~g.fips.isin(have) & ~g.fips.str.endswith('000') & (g.total > 0)]
    if len(add):
        filled.append(add.assign(source='Amlani & Algara county returns (fills MEDSL gaps)'))
        say(f'fill {y} {off} {st} sp{sp}: {len(add)} counties from Amlani & Algara ({add.total.sum():,} votes)')
# Whole state-races where MEDSL's precinct data is known to be incomplete in many counties:
AA_REPLACE = {(2018, 'GOV', 0, 'NY'), (2018, 'SEN', 0, 'NY'),   # NY 2018: counties absent or partial
              (2020, 'GOV', 0, 'IN')}                            # IN 2020: only 56 counties released precinct data
for key in AA_REPLACE:
    y, off, sp, st = key
    g = late[(late.year == y) & (late.office == off) & (late.special == sp) & (late.state_po == st)]
    m = (med.year == y) & (med.office == off) & (med.special == sp) & (med.state_po == st)
    say(f'replace {y} {off} {st}: MEDSL D {med[m].dem.sum():,} R {med[m].rep.sum():,} -> Amlani & Algara D {g.dem.sum():,} R {g.rep.sum():,}')
    med = med[~m]
    filled = [f[~((f.year == y) & (f.office == off) & (f.special == sp) & (f.state_po == st))] for f in filled]
    filled.append(g.assign(source='Amlani & Algara county returns (MEDSL incomplete)'))
cty = pd.concat([pres, early, med] + filled, ignore_index=True)

# ---------------------------------------------------------------- 3. official state patches
pcands = []
for jp in sorted(glob.glob(f'{R}/patches/*.json')):
    meta = json.load(open(jp, encoding='utf-8'))
    name = os.path.basename(jp)[:-5]
    p = pd.read_csv(f'{R}/patches/{name}.csv', dtype={'fips': str})
    for c in ('dem', 'rep', 'oth'): p[c] = p[c].astype(np.int64)
    bad = p[~p.fips.isin(UNITS)]
    if len(bad): sys.exit(f'patch {name}: unknown fips {list(bad.fips)}')
    p['total'] = p.dem + p.rep + p.oth
    src = 'official state results: ' + '; '.join(s.get('title', '') for s in meta.get('sources', []))[:200]
    p['source'] = src
    y, off, sp, st = int(meta['year']), meta['office'], int(meta['special']), meta['state_po']
    assert (p.year == y).all() and (p.office == off).all() and (p.special == sp).all() and (p.state_po == st).all(), name
    m = (cty.year == y) & (cty.office == off) & (cty.special == sp) & (cty.state_po == st)
    mode = meta['mode']
    before = cty[m][['dem', 'rep']].sum().tolist()
    if mode == 'replace':
        cty = pd.concat([cty[~m], p[COLS]], ignore_index=True)
    elif mode == 'fill':
        cty = pd.concat([cty[~(m & cty.fips.isin(p.fips))], p[COLS]], ignore_index=True)
    elif mode == 'add':
        for _, r in p.iterrows():
            mm = m & (cty.fips == r.fips)
            if mm.any():
                i = cty.index[mm][0]
                for c in ('dem', 'rep', 'oth'): cty.at[i, c] += r[c]
                cty.at[i, 'total'] = cty.at[i, 'dem'] + cty.at[i, 'rep'] + cty.at[i, 'oth']
                cty.at[i, 'source'] = cty.at[i, 'source'] + ' + ' + src
            else:
                cty = pd.concat([cty, r.to_frame().T[COLS]], ignore_index=True)
    else:
        sys.exit(f'patch {name}: unknown mode {mode}')
    m = (cty.year == y) & (cty.office == off) & (cty.special == sp) & (cty.state_po == st)
    after = cty[m][['dem', 'rep']].sum().tolist()
    say(f'patch {name} ({mode}): D {before[0]:,} -> {after[0]:,}  R {before[1]:,} -> {after[1]:,}')
    if off != 'HOUSE' and (meta.get('dem_cand') or meta.get('rep_cand')):
        pcands.append(dict(year=y, office=off, special=sp, state_po=st, dem_cand=meta.get('dem_cand', ''),
                           rep_cand=meta.get('rep_cand', ''), top_other_cand=meta.get('top_other_cand', '')))

for c in ('dem', 'rep', 'oth', 'total'): cty[c] = cty[c].astype(np.int64)
cty['year'] = cty.year.astype(int); cty['special'] = cty.special.astype(int)
cty = cty[cty.total != 0].sort_values(['year', 'office', 'special', 'state_po', 'fips'])
dup = cty.duplicated(['year', 'office', 'special', 'state_po', 'fips'])
assert not dup.any(), cty[dup].head()
cty.to_csv(f'{R}/county_results.csv', index=False, lineterminator='\n')

# ---------------------------------------------------------------- races (candidate names for the page)
mr = mraces[['year', 'office', 'special', 'state_po', 'dem_cand', 'rep_cand', 'top_other_cand', 'top_other_party']].copy()
mr['year'] = mr.year.astype(int); mr['special'] = mr.special.astype(int)
aac = aac.copy(); aac['top_other_party'] = ''
races = pd.concat([aac[aac.year <= 2014], mr], ignore_index=True)
# fill races that exist only through Amlani & Algara (2016-2020 gaps) or patches
have = set(zip(races.year, races.office, races.special, races.state_po))
extra = aac[[(a, b, c, d) not in have for a, b, c, d in zip(aac.year, aac.office, aac.special, aac.state_po)]]
races = pd.concat([races, extra], ignore_index=True)
for pc in pcands:
    k = (races.year == pc['year']) & (races.office == pc['office']) & (races.special == pc['special']) & (races.state_po == pc['state_po'])
    races = races[~k]
    races = pd.concat([races, pd.DataFrame([dict(pc, top_other_party='')])], ignore_index=True)
pr = pcand.pivot(index='year', columns='party', values='candidate').reset_index()
pr = pd.DataFrame(dict(year=pr.year, office='PRES', special=0, state_po='US', dem_cand=pr.DEMOCRAT, rep_cand=pr.REPUBLICAN,
                       top_other_cand='', top_other_party=''))
races = pd.concat([pr, races], ignore_index=True).fillna('')
races = races.sort_values(['year', 'office', 'special', 'state_po'])
races.to_csv(f'{R}/races.csv', index=False, lineterminator='\n')

# ---------------------------------------------------------------- house districts (MEDSL only)
hd = pd.read_csv(f'{W}/medsl_house_districts.csv', dtype={'district': str})
hd.to_csv(f'{R}/house_districts.csv', index=False, lineterminator='\n')

# ---------------------------------------------------------------- summary
s = cty[~cty.fips.str.endswith('000') | (cty.state_po == 'AK')]
summ = cty.groupby(['year', 'office', 'special']).agg(states=('state_po', 'nunique'), counties=('fips', 'nunique'),
                                                     dem=('dem', 'sum'), rep=('rep', 'sum')).reset_index()
print(summ.to_string())
print(cty.groupby('source').size().to_string())
open(f'{W}/build_results_log.txt', 'w').write('\n'.join(log) + '\n')
print('wrote', f'{R}/county_results.csv', len(cty), 'rows;', f'{R}/races.csv', len(races))
