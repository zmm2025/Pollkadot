"""Stage 1 for MEDSL 2016 precinct returns (MEDSL/precinct-returns repo, older schema).
Keeps PRES/SEN/HOUSE/GOV rows + straight-ticket rows; applies precinct-level TOTAL-vs-mode
dedupe; allocates AL and SC straight-ticket votes to the party's candidate in each contest
(per MEDSL coverage notes); aggregates away precincts.

usage: python3 -I stage1_2016.py OUTCSV ZIP:CSVNAME [ZIP:CSVNAME ...]
"""
import sys, zipfile, io, re
import pandas as pd, numpy as np
sys.path.insert(0, 'pipeline/data_sources/medsl')
from aggrules import drop_aggregate_rows

out = sys.argv[1]
specs = sys.argv[2:]
TARGET = {'us president': 'PRES', 'us senate': 'SEN', 'us house': 'HOUSE', 'governor': 'GOV',
          'governor and lt. governor': 'GOV'}
STRAIGHT_RE = re.compile(r'^straight', re.I)
COLS = ['state_postal', 'county_fips', 'county_name', 'jurisdiction', 'precinct', 'office', 'district',
        'stage', 'special', 'candidate', 'writein', 'party', 'mode', 'votes']
PK = ['state_postal', 'county_fips', 'jurisdiction', 'precinct', 'off', 'district', 'stage', 'special',
      'candidate', 'party']


def party_cls(p):
    p = p.str.lower().str.strip()
    d = p.str.contains('democrat') | p.isin(['dem', 'dfl']) | p.str.contains('farmer')
    d &= ~p.str.contains('social|republican')
    r = (p.str.contains('republican') | p.isin(['rep', 'gop'])) & ~p.str.contains('democrat')
    return np.select([d, r], ['D', 'R'], 'O')


frames = []
def _open(spec):
    """ZIP:CSVNAME (MEDSL precinct-returns repo) or a plain CSV path (Dataverse original files)."""
    if ':' in spec and spec.split(':', 1)[0].lower().endswith('.zip'):
        zp, n = spec.split(':', 1)
        zf = zipfile.ZipFile(zp); return zf.open(n)
    return open(spec, 'rb')


for spec in specs:
    parts, sparts = [], []
    with _open(spec) as fh:
        rd = pd.read_csv(io.TextIOWrapper(fh, encoding='latin-1'), dtype=str, keep_default_na=False,
                         usecols=COLS, chunksize=1000000)
        for ch in rd:
            o = ch.office.str.lower().str.strip()
            t = ch[o.isin(TARGET.keys())].copy()
            t['off'] = o[o.isin(TARGET.keys())].map(TARGET)
            parts.append(t)
            s = ch[o.str.match(STRAIGHT_RE) & ch.state_postal.isin(['AL', 'SC'])].copy()
            sparts.append(s)
    df = pd.concat(parts, ignore_index=True)
    df['votes'] = pd.to_numeric(df.votes, errors='coerce').fillna(0)
    # precinct-level TOTAL vs split-mode dedupe (same rule as 2018+)
    df['is_tot'] = df['mode'].str.lower().str.strip().eq('total')
    df['not_tot'] = ~df.is_tot
    g = df.groupby(PK, dropna=False)
    both = g.is_tot.transform('any') & g.not_tot.transform('any')
    msg = ''
    if both.any():
        sub = df[both]
        tot = sub[sub.is_tot].groupby(PK)['votes'].sum()
        oth = sub[~sub.is_tot].groupby(PK)['votes'].sum()
        cmp = pd.concat([tot.rename('tot'), oth.rename('oth')], axis=1).fillna(0)
        totge = cmp.tot >= cmp.oth - 0.5
        idx = pd.MultiIndex.from_frame(df[PK])
        keep_tot = idx.isin(cmp.index[totge])
        drop = both & ((keep_tot & ~df.is_tot) | (~keep_tot & df.is_tot))
        msg = f' mode-dedupe groups={len(cmp)} dropped_rows={int(drop.sum())} ({df.loc[drop, "votes"].sum():.0f} votes)'
        df = df[~drop]
    # straight-ticket allocation (AL, SC): add precinct straight-party votes to that party's candidate
    st = pd.concat(sparts, ignore_index=True)
    smsg = ''
    if False and len(st):  # disabled: MEDSL 2016 AL/SC candidate totals already include straight-ticket votes
        st['votes'] = pd.to_numeric(st.votes, errors='coerce').fillna(0)
        st['pcls'] = party_cls(st.party.where(st.party != '', st.candidate))
        st = st[st.pcls.isin(['D', 'R'])]
        sk = ['state_postal', 'county_fips', 'jurisdiction', 'precinct', 'mode']
        sv = st.groupby(sk + ['pcls']).votes.sum().rename('svotes').reset_index()
        df['pcls'] = party_cls(df.party)
        # one recipient row per precinct-mode-contest-party: the largest candidate row of that party
        cand = df[df.pcls.isin(['D', 'R'])]
        ck = sk + ['off', 'district', 'pcls']
        tot_c = cand.groupby(ck + ['candidate']).votes.sum().reset_index().sort_values('votes')
        rec = tot_c.drop_duplicates(ck, keep='last')[ck + ['candidate']]
        rec = rec.merge(sv, on=sk + ['pcls'], how='inner')
        add = rec.groupby(['state_postal', 'off']).svotes.sum()
        smsg = ' straight-ticket allocated: ' + '; '.join(f'{a}/{b}={v:.0f}' for (a, b), v in add.items())
        # append as extra rows (mode tagged)
        extra = df.drop_duplicates(ck + ['candidate']).merge(rec, on=ck + ['candidate'], how='inner')
        extra['votes'] = extra.svotes
        extra['mode'] = extra['mode'] + ' (straight ticket)'
        df = pd.concat([df, extra[df.columns]], ignore_index=True)
    df['state_po'] = df.state_postal
    df['jurisdiction_fips'] = df.jurisdiction
    df['dup_dropped'] = 0
    amsg = drop_aggregate_rows(df)
    df = df[df.dup_dropped == 0]
    agg = df.groupby(['state_postal', 'county_fips', 'county_name', 'jurisdiction', 'off', 'office', 'district',
                      'stage', 'special', 'candidate', 'party', 'mode', 'writein'], dropna=False).agg(
        votes=('votes', 'sum'), nprec=('precinct', 'nunique')).reset_index()
    agg['srcfile'] = spec.split('/')[-1]
    frames.append(agg)
    print(spec, 'rows', len(df), msg, smsg, amsg, flush=True)

res = pd.concat(frames)
res.insert(0, 'year', 2016)
res.to_csv(out, index=False)
print('wrote', out, len(res))
