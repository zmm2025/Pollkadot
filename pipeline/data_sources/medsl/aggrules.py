import pandas as pd
import numpy as np

CKEY = ['state_po', 'county_fips', 'office', 'district', 'stage', 'special']


def drop_aggregate_rows(df):
    """Flag rows of 'precincts' that are really sub-totals: (a) a precinct whose votes equal the sum
    of all other precincts in the county-contest (county-total row), (b) a precinct whose name is a
    prefix (followed by a space) of other precincts in the same jurisdiction and whose votes equal
    their sum (e.g. NJ 2024 municipal totals 'Allendale' vs 'Allendale 1', 'Allendale 2'...)."""
    live = df[df.dup_dropped == 0]
    if live.empty:
        return ''
    pk = CKEY + ['jurisdiction_fips', 'precinct']
    pt = live.groupby(pk, dropna=False)['votes'].sum().rename('T').reset_index()
    msgs = []
    drop_keys = []
    # (a) county-total rows
    g = pt.groupby(CKEY, dropna=False)
    pt['ctot'] = g['T'].transform('sum')
    pt['n'] = g['T'].transform('size')
    pt['rest'] = pt.ctot - pt['T']
    a = pt[(pt.n >= 3) & (pt.rest >= 20) & ((pt['T'] - pt.rest).abs() <= np.maximum(1, 0.002 * pt.rest))
           & pt.precinct.astype(str).str.contains('TOTAL', case=False)]
    if len(a):
        drop_keys.append(a[pk])
        msgs.append(f' | county-total rows dropped: {len(a)} ({a["T"].sum():.0f} votes) in '
                    + ','.join(sorted(set(a.county_fips.astype(str))))[:200])
    # (b) sub-total rows by name prefix
    pt2 = pt.copy()
    names = pt2.precinct.astype(str)
    rows = []
    for i, nm in enumerate(names):
        parts = nm.split(' ')
        for k in range(1, len(parts)):
            rows.append((i, ' '.join(parts[:k])))
    if rows:
        ch = pd.DataFrame(rows, columns=['i', 'parent'])
        ch = ch.join(pt2[CKEY + ['jurisdiction_fips', 'T']], on='i')
        par = ch.groupby(CKEY + ['jurisdiction_fips', 'parent'], dropna=False)['T'].agg(['sum', 'size']).reset_index()
        par = par.rename(columns={'parent': 'precinct', 'sum': 'childT', 'size': 'nchild'})
        mm = pt2.merge(par, on=CKEY + ['jurisdiction_fips', 'precinct'], how='inner')
        b = mm[(mm.nchild >= 2) & (mm.childT > 0) & ((mm['T'] - mm.childT).abs() <= 0.5)]
        if len(b):
            drop_keys.append(b[pk])
            msgs.append(f' | sub-total rows dropped: {len(b)} ({b["T"].sum():.0f} votes)')
    # (c) duplicated precinct sets (same county-contest reported twice under different precinct names)
    vec = live.groupby(pk + ['candidate'], dropna=False)['votes'].sum().reset_index()
    vec = vec[vec.votes > 0].sort_values(pk + ['candidate'])
    vec['cv'] = vec.candidate.astype(str) + ':' + vec.votes.astype(int).astype(str)
    vs = vec.groupby(pk, dropna=False)['cv'].agg('|'.join).rename('vec').reset_index()
    vs = vs.merge(pt[pk + ['T']], on=pk)
    vs = vs.merge(vec.groupby(pk, dropna=False).size().rename('nc').reset_index(), on=pk)
    vs = vs[(vs['T'] >= 20) & (vs.nc >= 2)]
    vs['dupn'] = vs.groupby(CKEY + ['vec'], dropna=False)['vec'].transform('size')
    gg = vs.groupby(CKEY, dropna=False)
    vs['frac'] = gg['dupn'].transform(lambda x: (x > 1).mean())
    vs['ndup'] = gg['dupn'].transform(lambda x: (x > 1).sum())
    c = vs[(vs.frac > 0.3) & (vs.ndup >= 6) & (vs.dupn > 1)]
    c = c[c.duplicated(CKEY + ['vec'], keep='first')]
    if len(c):
        drop_keys.append(c[pk])
        msgs.append(f' | duplicated-precinct rows dropped: {len(c)} ({c["T"].sum():.0f} votes) in '
                    + ','.join(sorted(set(c.county_fips.astype(str))))[:200])
    # (d) single rows equal to the county sum of the other rows for >=2 candidates (county total
    #     folded into one precinct, e.g. IN 2024 Hendricks)
    rk = CKEY + ['candidate', 'mode']
    rr = live[rk + ['jurisdiction_fips', 'precinct', 'votes']].copy()
    gr = rr.groupby(rk, dropna=False)['votes']
    rr['rest'] = gr.transform('sum') - rr['votes']
    rr['n'] = gr.transform('size')
    rr['second'] = gr.transform(lambda x: x.nlargest(2).iloc[-1] if len(x) > 1 else 0)
    rr['dupkey'] = rr.groupby(rk + ['jurisdiction_fips', 'precinct'], dropna=False)['votes'].transform('size') > 1
    hit = rr[rr.dupkey & (rr.n >= 3) & (rr.rest >= 20) & (rr.votes > 2 * rr.second) & ((rr.votes - rr.rest).abs() <= np.maximum(1, 0.002 * rr.rest))]
    if len(hit):
        nh = hit.groupby(CKEY + ['mode', 'jurisdiction_fips', 'precinct'], dropna=False).size()
        nh = nh[nh >= 2].reset_index()[CKEY + ['mode', 'jurisdiction_fips', 'precinct']]
        hit = hit.merge(nh, on=CKEY + ['mode', 'jurisdiction_fips', 'precinct'])
        if len(hit):
            hk = pd.MultiIndex.from_frame(hit[rk + ['jurisdiction_fips', 'precinct', 'votes']].astype(str))
            ik = pd.MultiIndex.from_frame(df[rk + ['jurisdiction_fips', 'precinct', 'votes']].astype(str))
            m = ik.isin(hk) & (df.dup_dropped == 0)
            df.loc[m, 'dup_dropped'] = 3
            msgs.append(f' | county-total single rows dropped: {int(m.sum())} ({df.loc[m, "votes"].sum():.0f} votes) in '
                        + ','.join(sorted(set(hit.county_fips.astype(str))))[:200])
    if drop_keys:
        dk = pd.concat(drop_keys).drop_duplicates()
        idx = pd.MultiIndex.from_frame(df[pk].astype(str))
        kk = pd.MultiIndex.from_frame(dk.astype(str))
        m = idx.isin(kk) & (df.dup_dropped == 0)
        df.loc[m, 'dup_dropped'] = 2
    return ''.join(msgs)

