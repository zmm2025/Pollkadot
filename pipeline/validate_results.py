"""Check data/results/county_results.csv against independent statewide totals and for missing counties.

References (all MIT Election Data + Science Lab statewide files, compiled from state-certified totals,
separately from the county files):
  PRES  1976-2024-president.csv
  SEN   1976-2024-senate-state.csv
  GOV   none statewide; 2016-2020 races are compared with Amlani & Algara state sums instead

writes data/results/validation.csv  (one row per state-race) and prints the races that differ by >0.5%
usage: python -P pipeline/validate_results.py
"""
import pickle
import numpy as np, pandas as pd

DV = 'build/downloads/dataverse'
cr = pd.read_csv('data/results/county_results.csv', dtype={'fips': str})
cr = cr[cr.special < 2]
ids = pickle.load(open('data/geometry/topo_s.pkl', 'rb'))['ids']
by_state = pd.Series(ids).groupby(pd.Series(ids).str[:2]).apply(set).to_dict()
ST = dict(cr[['state_po', 'fips']].assign(s=cr.fips.str[:2]).drop_duplicates('state_po')[['state_po', 's']].values)


def ref_mit(path, office):
    d = pd.read_csv(path, dtype=str, keep_default_na=False)
    d = d[d.year.astype(int) >= 2000]
    if 'stage' in d: d = d[d.stage.str.upper().eq('GEN')]
    d['v'] = pd.to_numeric(d.candidatevotes, errors='coerce').fillna(0)
    d['special'] = d.special.str.upper().eq('TRUE').astype(int) if 'special' in d else 0
    p = d.party_simplified.str.upper()
    g = d.assign(D=np.where(p == 'DEMOCRAT', d.v, 0), R=np.where(p == 'REPUBLICAN', d.v, 0))
    g = g.groupby([g.year.astype(int), 'special', 'state_po'])[['D', 'R']].sum().reset_index()
    g['office'] = office; g['ref'] = 'MEDSL statewide'
    return g.rename(columns={'year': 'year'})


refs = [ref_mit(f'{DV}/pres_statewide/1976-2024-president.csv', 'PRES'),
        ref_mit(f'{DV}/senate_statewide/1976-2024-senate-state.csv', 'SEN')]
import pyreadr
a = pyreadr.read_r(f'{DV}/amlani_algara/dataverse_shareable_gubernatorial_county_returns_1865_2020.Rdata')['gov_elections_release']
a = a[a.election_year.isin([2016, 2018, 2020])]
a = a.groupby([a.election_year.astype(int), 'state'])[['democratic_raw_votes', 'republican_raw_votes']].sum().reset_index()
refs.append(pd.DataFrame(dict(year=a.election_year, special=0, state_po=a.state, D=a.democratic_raw_votes,
                              R=a.republican_raw_votes, office='GOV', ref='Amlani & Algara')))
ref = pd.concat(refs)

s = cr.groupby(['year', 'office', 'special', 'state_po']).agg(
    dem=('dem', 'sum'), rep=('rep', 'sum'), total=('total', 'sum'),
    source=('source', lambda x: x.value_counts().index[0])).reset_index()
# counties with no votes in a state that held the race (House: every state, every regular year)
miss = []
for (y, off, sp, st), g in cr.groupby(['year', 'office', 'special', 'state_po']):
    if st in ('AK', 'DC') or (off == 'HOUSE' and sp): miss.append(''); continue   # House specials cover a few counties
    have = set(g[g.total > 0].fips)
    m = sorted(by_state[ST[st]] - have - {'15005'})   # Kalawao votes with Maui
    miss.append(' '.join(m) if len(m) <= 12 else f'{len(m)} counties')
s['missing_counties'] = miss
v = s.merge(ref, on=['year', 'office', 'special', 'state_po'], how='left')
v['d_pct'] = ((v.dem - v.D) / v.D.where(v.D > 0) * 100).round(2)
v['r_pct'] = ((v.rep - v.R) / v.R.where(v.R > 0) * 100).round(2)
v = v.rename(columns={'D': 'ref_dem', 'R': 'ref_rep'})
v['ref'] = v.ref.fillna('')
for c in ('ref_dem', 'ref_rep'): v[c] = v[c].round().astype('Int64')
v = v[['year', 'office', 'special', 'state_po', 'dem', 'rep', 'total', 'ref', 'ref_dem', 'ref_rep', 'd_pct', 'r_pct',
       'missing_counties', 'source']].sort_values(['year', 'office', 'special', 'state_po'])
v.to_csv('data/results/validation.csv', index=False, lineterminator='\n')

off = v[(v.d_pct.abs() > 0.5) | (v.r_pct.abs() > 0.5)]
print(f'{len(v)} state-races; {v.ref.ne("").sum()} with a reference; {len(off)} differ by more than 0.5% in D or R:')
print(off[['year', 'office', 'special', 'state_po', 'dem', 'ref_dem', 'd_pct', 'rep', 'ref_rep', 'r_pct', 'source']].to_string(index=False))
mm = v[(v.missing_counties != '') & (v.office != 'HOUSE')]
print(f'\nstatewide races with counties lacking votes: {len(mm)}')
print(mm[['year', 'office', 'special', 'state_po', 'missing_counties']].to_string(index=False))
mh = v[(v.missing_counties != '') & (v.office == 'HOUSE')]
print(f'\nHouse state-years with counties lacking votes: {len(mh)}')
print(mh[['year', 'state_po', 'missing_counties']].to_string(index=False))
