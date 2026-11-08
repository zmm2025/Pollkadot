"""Assemble final outputs from stage-2 files.
usage: python3 -I build_outputs.py YEAR [YEAR ...]
"""
import sys, re
import numpy as np, pandas as pd

W = 'data/work'
R = 'data/results'
years = [int(y) for y in sys.argv[1:]]
OFF = {'PRES': 'PRES', 'SEN': 'SEN', 'HOUSE': 'HOUSE', 'GOV': 'GOV'}
GENERIC = re.compile(r'UNNAMED|WRITE|SCATTER|ALL OTHERS|^OTHER|MISCELLANEOUS|UNQUALIFIED|PERSONAL CHOICE', re.I)

cty, races, house = [], [], []
for y in years:
    c = pd.read_csv(f'{W}/s2_county_{y}.csv', dtype={'fips': str})
    c = c.rename(columns={'off': 'office', 'spec': 'special'})
    cty.append(c)

    k = pd.read_csv(f'{W}/s2_cands_{y}.csv', dtype=str, keep_default_na=False)
    k['votes'] = k.votes.astype(float)
    k['spec'] = k.spec.astype(int)
    k = k[k.off.isin(['PRES', 'SEN', 'GOV'])]
    # merge name variants of the same candidate (e.g. 'JOHN GREGG', 'JOHN R GREGG', 'GREGG \\ HALE')
    def skey(n):
        n = re.split(r'\\| AND |/', n)[0].strip()
        if ',' in n:
            return n.split(',')[0].strip()
        n = re.sub(r'\b(JR|SR|II|III|IV)\b', '', n).strip()
        return n.split()[-1] if n.split() else n
    k['skey'] = [skey(n) if not GENERIC.search(n) else n for n in k.cand]
    disp = k.sort_values('votes').drop_duplicates(['off', 'spec', 'state_po', 'cls', 'skey'], keep='last')
    disp = disp.set_index(['off', 'spec', 'state_po', 'cls', 'skey'])[['cand', 'party_label']]
    k = k.groupby(['off', 'spec', 'state_po', 'cls', 'skey']).votes.sum().reset_index()
    k = k.join(disp, on=['off', 'spec', 'state_po', 'cls', 'skey'])
    for (off, sp, st), g in k.groupby(['off', 'spec', 'state_po']):
        g = g.sort_values('votes', ascending=False)
        tot = g.votes.sum()
        # main D/R candidate = largest of that party with >= 0.5% of the vote (ignores stray write-ins
        # such as 2 votes for Peter Welch in the 2018 VT Senate race); party totals keep everyone
        Dall = g[g.cls == 'D']; Rall = g[g.cls == 'R']; O = g[g.cls == 'O']
        D = Dall[Dall.votes >= 0.005 * tot]; Rr = Rall[Rall.votes >= 0.005 * tot]
        On = O[~O.cand.str.contains(GENERIC)]
        top_o = On.iloc[0] if len(On) else (O.iloc[0] if len(O) else None)
        races.append(dict(
            year=y, office=off, special=sp, state_po=st,
            dem_cand=D.cand.iloc[0] if len(D) else '', rep_cand=Rr.cand.iloc[0] if len(Rr) else '',
            top_other_cand=top_o.cand if top_o is not None else '',
            top_other_party=(top_o.party_label if top_o is not None else ''),
            dem_votes=Dall.votes.sum(), rep_votes=Rall.votes.sum(),
            top_other_votes=top_o.votes if top_o is not None else 0, total=g.votes.sum(),
            dem_cand_votes=D.votes.iloc[0] if len(D) else 0, rep_cand_votes=Rr.votes.iloc[0] if len(Rr) else 0,
            n_dem_cands=int(len(D)), n_rep_cands=int(len(Rr)),
            dem2_cand=D.cand.iloc[1] if len(D) > 1 else '', dem2_votes=D.votes.iloc[1] if len(D) > 1 else 0,
            rep2_cand=Rr.cand.iloc[1] if len(Rr) > 1 else '', rep2_votes=Rr.votes.iloc[1] if len(Rr) > 1 else 0,
            oth_votes=O.votes.sum(),
            winner_cand=g.cand.iloc[0], winner_class=g.cls.iloc[0],
        ))

    h = pd.read_csv(f'{W}/s2_house_{y}.csv', dtype={'district_n': str})
    h = h[(h.spec == 0) & (h.district_n != 'UNK')]
    h = h.rename(columns={'district_n': 'district'})
    house.append(h)

cty = pd.concat(cty)
for col in ['dem', 'rep', 'oth', 'total']:
    cty[col] = cty[col].round().astype(np.int64)
cty['total'] = cty.dem + cty.rep + cty.oth
cty = cty[['year', 'office', 'special', 'state_po', 'fips', 'dem', 'rep', 'oth', 'total']]
cty = cty.sort_values(['year', 'office', 'special', 'state_po', 'fips'])
cty.to_csv(f'{R}/county_results.csv', index=False)

races = pd.DataFrame(races)
for col in ['dem_votes', 'rep_votes', 'top_other_votes', 'total', 'dem_cand_votes', 'rep_cand_votes',
            'dem2_votes', 'rep2_votes', 'oth_votes']:
    races[col] = races[col].round().astype(np.int64)
races = races.sort_values(['year', 'office', 'special', 'state_po'])
races.to_csv(f'{R}/races.csv', index=False)

house = pd.concat(house)
for col in ['dem', 'rep', 'oth']:
    house[col] = house[col].round().astype(np.int64)
house['contested'] = ((house.dem > 0) & (house.rep > 0)).astype(int)
house = house[['year', 'state_po', 'district', 'dem', 'rep', 'oth', 'contested']].sort_values(['year', 'state_po', 'district'])
house.to_csv(f'{R}/house_districts.csv', index=False)
print('county rows', len(cty), 'races', len(races), 'house', len(house))
