import pandas as pd, numpy as np, re
OFFMAP = {'US PRESIDENT':('PRES',0),'US SENATE':('SEN',None),'US SENATE - 2 YEAR TERM':('SEN',1),
          'US SENATE PARTIAL':('SEN',1),'US HOUSE':('HOUSE',None),'GOVERNOR':('GOV',None),
          'GOVERNOR/LIEUTENANT GOVERNOR':('GOV',None),'GOVERNOR / LT. GOVERNOR':('GOV',None),
          'GOVERNOR AND LIEUTENANT GOVERNOR':('GOV',None)}
def _party16(p):
    p = p.str.lower().str.strip()
    d = (p.str.contains('democrat') | p.isin(['dem', 'dfl']) | p.str.contains('farmer')) & ~p.str.contains('social|republican')
    d |= p.eq('democratic/republican')
    r = (p.str.contains('republican') | p.isin(['rep', 'gop'])) & ~p.str.contains('democrat')
    return np.select([d, r], ['DEMOCRAT', 'REPUBLICAN'], np.where(p.isin(['', 'na', 'none']), '', 'OTHER'))


def load_s1_2016():
    d = pd.read_csv('build/work/s1_2016.csv', dtype=str, keep_default_na=False)
    d = d.rename(columns={'state_postal': 'state_po', 'jurisdiction': 'jurisdiction_name'})
    d['county_fips'] = d.county_fips.where(~d.county_fips.isin(['NA']), '')
    d['jurisdiction_fips'] = ''
    d['party_detailed'] = d.party.str.upper()
    d['party_simplified'] = _party16(d.party)
    d['office'] = d.off.map({'PRES': 'US PRESIDENT', 'SEN': 'US SENATE', 'HOUSE': 'US HOUSE', 'GOV': 'GOVERNOR'})
    d['nstar'] = '0'
    d['county_name'] = d.county_name.str.upper().str.replace(r' (COUNTY|PARISH)$', '', regex=True)
    return d


def load_s1(y):
    if y == 2016:
        d = load_s1_2016()
    else:
        d = pd.read_csv(f'build/work/s1_{y}.csv', dtype=str, keep_default_na=False)
    d['votes'] = d.votes.astype(float)
    d['nprec'] = d.nprec.astype(int)
    d['nstar'] = pd.to_numeric(d.get('nstar', 0), errors='coerce').fillna(0).astype(int)
    up = d.office.str.upper().str.strip()
    d = d[up.isin(OFFMAP.keys())].copy()
    up = d.office.str.upper().str.strip()
    d['off'] = up.map(lambda o: OFFMAP[o][0])
    sp_forced = up.map(lambda o: OFFMAP[o][1])
    sp = d.special.str.upper().map({'TRUE':1,'FALSE':0}).fillna(0).astype(int)
    d['spec'] = np.where(sp_forced.notna(), sp_forced.fillna(0), sp).astype(int)
    d['stage'] = d.stage.str.upper()
    d = d[~((d.state_po=='DC') & d.off.isin(['SEN','HOUSE','GOV']))]
    return d
