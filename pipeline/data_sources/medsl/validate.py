"""Validation: PRES vs tonmcg county files, 2024 vs MEDSL state files, cross-office consistency."""
import sys
import pandas as pd, numpy as np
W = 'data/work'
years = [int(y) for y in sys.argv[1:]] or [2018, 2020, 2022, 2024]

cty = pd.concat([pd.read_csv(f'{W}/s2_county_{y}.csv', dtype={'fips': str}) for y in years])
cands = pd.concat([pd.read_csv(f'{W}/s2_cands_{y}.csv', dtype=str, keep_default_na=False) for y in years])
cands['votes'] = cands.votes.astype(float)
cands['year'] = cands.year.astype(int)
cands['spec'] = cands.spec.astype(int)

print('=== national PRES sums')
for y in [2016, 2020, 2024]:
    if y in years:
        p = cty[(cty.year == y) & (cty.off == 'PRES')]
        print(y, p[['dem', 'rep', 'oth', 'total']].sum().astype(int).to_dict())

print('\n=== PRES vs tonmcg (state level, pct diff of ours vs ref)')
for y in [2016, 2020, 2024]:
    if y not in years:
        continue
    ref = pd.read_csv(f'data/raw/tonmcg/{y}_US_County_Level_Presidential_Results.csv', dtype={'county_fips': str, 'combined_fips': str})
    if y == 2016:
        ref = ref.rename(columns={'combined_fips': 'county_fips'})
    ref['fips'] = ref.county_fips.str.zfill(5)
    ref['st'] = ref.fips.str[:2]
    p = cty[(cty.year == y) & (cty.off == 'PRES')].copy()
    p['st'] = p.fips.str[:2]
    a = p.groupby(['st', 'state_po'])[['dem', 'rep', 'total']].sum().reset_index()
    b = ref.groupby('st')[['votes_dem', 'votes_gop', 'total_votes']].sum().reset_index()
    m = a.merge(b, on='st', how='outer')
    for c1, c2 in [('dem', 'votes_dem'), ('rep', 'votes_gop'), ('total', 'total_votes')]:
        m['d_' + c1] = (m[c1] / m[c2] - 1) * 100
    bad = m[(m[['d_dem', 'd_rep', 'd_total']].abs() > 0.5).any(axis=1) | m.state_po.isna()]
    print(y, 'states >0.5% off:')
    print(bad[['state_po', 'dem', 'votes_dem', 'rep', 'votes_gop', 'total', 'total_votes', 'd_dem', 'd_rep', 'd_total']].round(2).to_string())
    # county-level
    cm = p.merge(ref[['fips', 'votes_dem', 'votes_gop', 'total_votes']], on='fips', how='outer', indicator=True)
    print(y, 'county merge:', cm._merge.value_counts().to_dict())
    print('   unmatched ours:', cm[cm._merge == 'left_only'].groupby('state_po').fips.apply(list).to_dict())
    lo = cm[cm._merge == 'right_only']
    print('   unmatched ref by state:', lo.fips.str[:2].value_counts().to_dict())
    both = cm[cm._merge == 'both'].copy()
    both['dd'] = ((both.dem - both.votes_dem).abs() + (both.rep - both.votes_gop).abs()) / both.total_votes.clip(lower=1)
    bc = both[both.dd > 0.02]
    print('   counties with |dD|+|dR| > 2% of total:', len(bc), bc.groupby('state_po').size().to_dict())

if 2024 in years:
    print('\n=== 2024 vs MEDSL state-level files')
    for off, fn in [('PRES', 'X_2024-president-state.csv'), ('SEN', 'X_2024-senate-state.csv')]:
        r = pd.read_csv(f'build/downloads/medsl_2024/{fn}', dtype=str, keep_default_na=False)
        r['votes'] = pd.to_numeric(r.votes, errors='coerce').fillna(0)
        r = r[r.stage.str.upper() == 'GEN']
        r['spec'] = (r.special.str.upper() == 'TRUE').astype(int)
        r['cls'] = np.select([r.party_simplified == 'DEMOCRAT', r.party_simplified == 'REPUBLICAN'], ['D', 'R'], 'O')
        rs = r.groupby(['state_po', 'spec', 'cls']).votes.sum().unstack().fillna(0)
        c = cands[(cands.year == 2024) & (cands.off == off)]
        cs = c.groupby(['state_po', 'spec', 'cls']).votes.sum().unstack().fillna(0)
        m = cs.join(rs, lsuffix='_ours', rsuffix='_ref', how='outer').fillna(0)
        m['tot_ours'] = m[['D_ours', 'R_ours', 'O_ours']].sum(axis=1)
        m['tot_ref'] = m[['D_ref', 'R_ref', 'O_ref']].sum(axis=1)
        for k in ['D', 'R']:
            m['d' + k] = (m[k + '_ours'] / m[k + '_ref'].replace(0, np.nan) - 1) * 100
        m['dT'] = (m.tot_ours / m.tot_ref.replace(0, np.nan) - 1) * 100
        bad = m[(m[['dD', 'dR', 'dT']].abs() > 0.5).any(axis=1) | (m.tot_ref == 0) | (m.tot_ours == 0)]
        print(off, 'state-races >0.5% off (or missing):')
        print(bad[['D_ours', 'D_ref', 'R_ours', 'R_ref', 'tot_ours', 'tot_ref', 'dD', 'dR', 'dT']].round(2).to_string())
