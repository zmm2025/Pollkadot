"""Stage 2: from stage-1 extracts build county / race / house-district tables (2018-2024).

usage: python3 -I stage2_aggregate.py YEAR [YEAR ...]
writes data/work/s2_{county,cands,house}_{YEAR}.csv and diagnostics
"""
import sys, re
import numpy as np
import pandas as pd
sys.path.insert(0, 'pipeline/data_sources/medsl')
from common import load_s1

W = 'data/work'

META_RE = re.compile(
    r'^(UNDER ?/ ?OVER|REGISTERED|PUBLIC COUNTER|ABSENTEE ?/ ?MILITARY$|.*BALLOTS( CAST)?$|BALLOTS|ELIGIBLE|BLANKS?( BALLOTS| VOTES|/VOID)?$|UNDER ?VOTE|OVER ?VOTE|^OVER$|'
    r'TOTAL|CONTEST TOTAL|CAST VOTES|ABSENTEE / MILITARY|AFFIDAVIT|FEDERAL( VOTES)?$|STATE BALLOTS|'
    r'SPECIAL VOTES|VOID|SPOILED|TIMES (BLANK|OVER)|NOT ASSIGNED|EMERGENCY|MANUALLY COUNTED|'
    r'.*VOTERS$|NO VOTE|NONE OF THESE CANDIDATES|NOT QUALIFIED|UNDERVOTES|OVERVOTES|UNDERVOTES-VOIDS|'
    r'STATISTICAL ADJUSTMENT|UNRESOLVED WRITE|REJECTED|EXHAUSTED|STATE VOTES$)', re.I)

D_DET = re.compile(r'^(DEMOCRAT|DEMOCRATIC|DEM|DFL|DEMOCRATIC-FARMER-LABOR|DEMOCRATIC FARMER LABOR|'
                   r'DEMOCRATIC-NPL|DEMOCRATIC-NONPARTISAN LEAGUE)$', re.I)
R_DET = re.compile(r'^(REPUBLICAN|REP|GOP)$', re.I)

# Wisconsin 2018 has county names only; build name->fips from WI 2020
_wi = None
def wi_lookup():
    global _wi
    if _wi is None:
        d = pd.read_csv(f'{W}/s1_2020.csv', dtype=str, keep_default_na=False,
                        usecols=['state_po', 'county_name', 'county_fips'])
        d = d[d.state_po == 'WI'][['county_name', 'county_fips']].drop_duplicates()
        _wi = {re.sub(r'[^A-Z]', '', n.upper()): f for n, f in zip(d.county_name, d.county_fips)}
    return _wi

STFIPS = {}
_tm = None
_fu = None


def fips_universe():
    global _fu
    if _fu is None:
        r = pd.read_csv('data/raw/tonmcg/2020_US_County_Level_Presidential_Results.csv', dtype={'county_fips': str})
        _fu = set(r.county_fips.str.zfill(5)) | {'46102', '02000'}
    return _fu


def norm_town(x):
    x = str(x).upper()
    x = re.sub(r'\b(CITY|TOWN|TOWNSHIP|TWP|OF|PLANTATION|PLT)\b', '', x)
    return re.sub(r'[^A-Z]', '', x)


def town_lookup():
    global _tm
    if _tm is None:
        fr = []
        for yy in (2018, 2020):
            t = pd.read_csv(f'{W}/s1_{yy}.csv', dtype=str, keep_default_na=False,
                            usecols=['state_po', 'jurisdiction_name', 'county_fips'])
            fr.append(t[t.county_fips.str.fullmatch(r'\d{5}')].drop_duplicates())
        t = pd.concat(fr).drop_duplicates()
        t['k'] = t.jurisdiction_name.map(norm_town)
        g = t.groupby(['state_po', 'k']).county_fips.agg(lambda x: x.iloc[0] if x.nunique() == 1 else '')
        _tm = g[g != ''].to_dict()
    return _tm

# MEDSL special-election flags that are wrong for our purpose
SPEC_OVERRIDE = {
    (2020, 'MD', 'HOUSE', '007'): 0,   # Nov-2020 MD-7 race is the regular general (special was Apr 2020)
    (2024, 'TX', 'HOUSE', '018'): 0,   # rows are the regular TX-18 race (Turner v Centonze); concurrent special absent
}

# candidates whose party is blank in every MEDSL row (verified against known nominees)
OVERRIDE = {
    (2022, 'NM', 'MICHELLE LUJAN GRISHAM'): 'D',
    (2022, 'NM', 'MARK V RONCHETTI'): 'R',
    (2024, 'NJ', 'HERB CONAWAY'): 'D',
    (2024, 'NJ', 'RAJESH MOHAN'): 'R',
    (2016, 'ND', 'JOHN HOEVEN'): 'R', (2016, 'ND', 'KEVIN CRAMER'): 'R',
    (2016, 'ND', 'CHASE IRON EYES'): 'D', (2016, 'ND', 'ELIOT GLASSHEIM'): 'D',
    (2016, 'KY', 'JAMES R COMER'): 'R', (2016, 'KY', 'SAMUEL L GASKINS'): 'D',
    (2016, 'VT', 'HILLARY CLINTON'): 'D', (2016, 'VT', 'DONALD TRUMP'): 'R',
    (2016, 'NE', 'BRAD ASHFORD'): 'D',
    (2024, 'NE', 'DAN OSBORN'): 'O',  # independent; MEDSL labels him DEMOCRAT (Democrats endorsed, no D nominee)
}
LABEL_OVERRIDE = {(2024, 'NE', 'DAN OSBORN'): 'INDEPENDENT'}


def fix_fips(d, year):
    f = d.county_fips.str.strip().str.replace(r'\.0$', '', regex=True)
    f = f.where(~f.str.fullmatch(r'\d{1,4}'), f.str.zfill(5))
    # state fips per state (mode of valid values, else state_fips column not kept -> derive)
    st = d.state_po
    # Kansas City, MO reported separately; KC Board of Elections covers the Jackson County part
    kc = (st == 'MO') & (d.county_name.str.upper().str.contains('KANSAS CITY') |
                         d.jurisdiction_name.str.upper().str.contains('KANSAS CITY') | f.isin(['36000', '29380']))
    f = f.mask(kc, '29095')
    f = f.mask(f == '46113', '46102')  # Shannon County SD renamed Oglala Lakota (2015)
    f = f.mask((st == 'NY') & (f == '36122'), '36123')  # 2016 typo for Yates County
    # anything not a real county-equivalent code is treated as missing (then filled from town names)
    f = f.where(f.isin(fips_universe()), '')
    if year == 2018:
        wi = wi_lookup()
        m = st == 'WI'
        f = f.mask(m, d.county_name.str.upper().str.replace(r'[^A-Z]', '', regex=True).map(wi).fillna(''))
    valid = f.str.fullmatch(r'\d{5}')
    # fill missing county fips from the same jurisdiction (town) name elsewhere in the state-year
    jn = d.jurisdiction_name.str.upper().str.strip()
    jm = pd.DataFrame({'st': st[valid], 'jn': jn[valid], 'f': f[valid]}).drop_duplicates()
    jm = jm[jm.jn != ''].groupby(['st', 'jn']).f.agg(lambda x: x.iloc[0] if x.nunique() == 1 else '')
    jmd = jm[jm != ''].to_dict()
    fill = ~valid & (st != 'AK')
    if fill.any():
        newf = pd.Series([jmd.get((a, b), '') for a, b in zip(st[fill], jn[fill])], index=f[fill].index)
        print(f'  fips filled from jurisdiction name: {int((newf != "").sum())} rows')
        f = f.copy()
        f[fill] = newf.where(newf != '', f[fill])
        valid = f.str.fullmatch(r'\d{5}')
        # second fallback: town->county map from the 2018/2020 files (New England cities etc.)
        fill2 = ~valid & (st != 'AK')
        if fill2.any():
            tm = town_lookup()
            nf2 = pd.Series([tm.get((a, norm_town(b)), '') for a, b in zip(st[fill2], jn[fill2])], index=f[fill2].index)
            print(f'  fips filled from 2018/2020 town map: {int((nf2 != "").sum())} rows')
            f[fill2] = nf2.where(nf2 != '', f[fill2])
            valid = f.str.fullmatch(r'\d{5}')
    sf = f[valid].str[:2].groupby(st[valid]).agg(lambda s: s.mode()[0])
    STFIPS.update(sf.to_dict())
    pref = st.map(STFIPS)
    ok = valid & (f.str[:2] == pref)
    d['fips_raw'] = d.county_fips
    d['fips'] = f.where(ok, pref + '000')  # SS000 = not allocable to a county
    d.loc[st == 'AK', 'fips'] = '02000'   # Alaska: reported by state house district -> statewide row
    return d


def norm_cand(s):
    s = s.str.upper().str.strip()
    s = s.str.replace(r'\s+', ' ', regex=True)
    s = s.str.replace('.', '', regex=False)
    return s


def norm_district(off, dist):
    x = dist.str.upper().str.strip()
    x = x.where(~x.isin(['AT-LARGE', 'AT LARGE', '0', '00', '000', 'AL']), '000')
    x = x.where(~x.isin(['STATEWIDE', 'NA', 'N/A']), '')
    x = x.where(~x.str.fullmatch(r'\d+'), x.str.zfill(3))
    return np.where(off == 'HOUSE', x, '')


def run(year):
    d = load_s1(year)
    d['stage'] = d.stage.str.upper().str.strip()
    log = []
    pri = d[d.stage.str.startswith('PRI')]
    if len(pri):
        log.append(f'dropped primary rows: {len(pri)} votes={pri.votes.sum():.0f}')
    d = d[~d.stage.str.startswith('PRI')].copy()
    d.loc[d.stage.str.contains('RUNOFF'), 'spec'] = 2
    d['district_n'] = norm_district(d.off, d.district)
    d.loc[d.off == 'HOUSE', 'district_n'] = d.loc[d.off == 'HOUSE', 'district_n']
    # recount: if a contest has GEN RECOUNT rows, keep only those for that contest
    ck = ['state_po', 'off', 'spec', 'district_n']
    rc = d[d.stage.str.contains('RECOUNT')]
    if len(rc):
        keys = set(map(tuple, rc[ck].drop_duplicates().values))
        inrc = d[ck].apply(tuple, axis=1).isin(keys)
        log.append(f'recount contests: {sorted(keys)}')
        d = d[~inrc | d.stage.str.contains('RECOUNT')]
    d['cand'] = norm_cand(d.candidate)
    # NM 2020 codes suppressed small counts as -1 -> 0. Other negatives (MI precinct 9999
    # 'statistical adjustment' rows) are genuine corrections and are kept.
    neg = (d.votes < 0) & (d.state_po == 'NM')
    if neg.any():
        log.append('NM negative (-1 suppression) values set to 0: ' + '; '.join(
            f'{k}={v:.0f}' for k, v in d[neg].groupby(['state_po', 'off', 'cand']).votes.sum().items()))
        d.loc[neg, 'votes'] = 0
    if year == 2016:
        # MEDSL 2016: Jackson County IN governor rows are filed under US Senate
        m = (d.state_po == 'IN') & (d.off == 'SEN') & d.cand.isin(['ERIC HOLCOMB', 'JOHN GREGG', 'REX BELL'])
        if m.any():
            log.append(f'2016 IN governor rows found under SEN moved to GOV: {int(m.sum())} rows {d.loc[m, "votes"].sum():.0f} votes')
            d.loc[m, 'off'] = 'GOV'
    # rows with a blank candidate name are (almost all) aggregated write-ins -> keep as 'oth'
    d.loc[d.cand == '', 'cand'] = 'UNNAMED WRITE-IN'
    meta = d.cand.str.match(META_RE)
    mm = d[meta]
    log.append('meta rows excluded: ' + '; '.join(
        f'{k}={v:.0f}' for k, v in mm.groupby('cand').votes.sum().sort_values(ascending=False).head(25).items()))
    d = d[~meta].copy()
    d = fix_fips(d, year)
    for (yy, st, off, dist), newspec in SPEC_OVERRIDE.items():
        if yy == year:
            m = (d.state_po == st) & (d.off == off) & (d.district_n == dist)
            if m.any():
                log.append(f'special-flag override {st} {off} {dist}: {sorted(set(d.loc[m, "spec"]))} -> {newspec}')
                d.loc[m, 'spec'] = newspec
    # House rows with blank district: at-large states -> '000'; else infer from county if the county
    # lies in a single district this year; otherwise 'UNK'
    hm = d.off == 'HOUSE'
    one_seat = {'AK', 'DE', 'ND', 'SD', 'VT', 'WY'} | ({'MT'} if year < 2022 else set())
    single = d.state_po.isin(one_seat)
    d.loc[hm & ~single & (d.district_n == '000'), 'district_n'] = ''
    d.loc[hm & single, 'district_n'] = '000'
    blank = hm & (d.district_n == '')
    if blank.any():
        d.loc[blank & single, 'district_n'] = '000'
        rest = blank & ~single
        if rest.any():
            cd = d[hm & (d.district_n != '')].groupby(['state_po', 'fips', 'spec']).district_n.agg(
                lambda x: x.iloc[0] if x.nunique() == 1 else 'UNK').to_dict()
            nd = [cd.get((a, b, c), 'UNK') for a, b, c in zip(d.loc[rest, 'state_po'], d.loc[rest, 'fips'], d.loc[rest, 'spec'])]
            d.loc[rest, 'district_n'] = nd
            r = d[rest]
            log.append('House rows with blank district (multi-district states) -> ' + '; '.join(
                f'{k}={v:.0f}' for k, v in r.groupby(['state_po', 'district_n']).votes.sum().items()))

    # ---- party resolution at contest-candidate level
    ps = d.party_simplified.str.upper().str.strip()
    pdt = d.party_detailed.str.upper().str.strip()
    notdr = ~ps.isin(['DEMOCRAT', 'REPUBLICAN'])
    dlike = (pdt.str.match(D_DET) | pdt.str.contains('DEMOCRAT')) & ~pdt.str.contains('REPUBLICAN|SOCIAL')
    rlike = (pdt.str.match(R_DET) | pdt.str.contains('REPUBLICAN')) & ~pdt.str.contains('DEMOCRAT')
    explicit_o = (ps.isin(['LIBERTARIAN', 'OTHER']) | (ps.isin(['', 'NONPARTISAN']) & ~pdt.isin(['', 'NA', 'NONE', 'NONPARTISAN', 'NON-PARTISAN'])))
    cls = np.select([ps == 'DEMOCRAT', ps == 'REPUBLICAN', notdr & dlike, notdr & rlike, explicit_o],
                    ['D', 'R', 'D', 'R', 'O'], '')
    d['cls_row'] = cls
    cc = ['state_po', 'off', 'spec', 'district_n', 'cand']
    # candidate-level label = label carrying most of the candidate's votes in the contest (D, R or an
    # explicit other party); fusion lines therefore follow the candidate's major-party line
    tmp = d[d.cls_row != ''].groupby(cc + ['cls_row']).votes.sum().reset_index()
    tmp = tmp.sort_values('votes').drop_duplicates(cc, keep='last')
    tmp = tmp[tmp.cls_row != 'O']
    conflict = d[d.cls_row.isin(['D', 'R'])].groupby(cc).cls_row.nunique()
    conflict = conflict[conflict > 1]
    if len(conflict):
        log.append('candidates with both D and R rows (resolved to max-vote label): ' +
                   '; '.join('/'.join(map(str, k)) for k in conflict.index[:30]))
    d = d.merge(tmp[cc + ['cls_row']].rename(columns={'cls_row': 'cls'}), on=cc, how='left')
    # fallback: same candidate name labelled D/R in another contest in the same state-year
    generic = d.cand.str.contains(r'WRITE|SCATTER|ALL OTHERS|^OTHERS?$|MISCELLANEOUS', regex=True)
    fb = d[d.cls_row.isin(['D', 'R']) & ~generic].groupby(['state_po', 'cand', 'cls_row']).votes.sum().reset_index()
    fb = fb.sort_values('votes').drop_duplicates(['state_po', 'cand'], keep='last')
    fbm = dict(zip(zip(fb.state_po, fb.cand), fb.cls_row))
    # only candidates with no explicit label at all in this contest use the fallbacks
    has_o = d[d.cls_row == 'O'][cc].drop_duplicates()
    has_o['has_o'] = True
    d = d.merge(has_o, on=cc, how='left')
    d['has_o'] = d.has_o.fillna(False).astype(bool)
    generic = d.cand.str.contains(r'WRITE|SCATTER|ALL OTHERS|^OTHERS?$|MISCELLANEOUS', regex=True)
    miss = d.cls.isna() & ~d.has_o & ~generic
    d.loc[miss, 'cls'] = [fbm.get((a, b), np.nan) for a, b in zip(d.loc[miss, 'state_po'], d.loc[miss, 'cand'])]
    # surname fallback: unlabeled name variant of a labelled D/R candidate in the same contest
    def surname(x):
        x = x.str.replace(r'\b(JR|SR|II|III|IV)\b', '', regex=True).str.strip()
        flip = x.str.contains(',')
        last = x.str.split(',').str[0].str.strip()
        tok = x.str.replace(r'["(].*?[")]', '', regex=True).str.split().str[-1]
        return last.where(flip, tok).fillna('')
    lab = d[d.cls.isin(['D', 'R'])][cc[:-1] + ['cand', 'cls']].drop_duplicates()
    lab['sn'] = surname(lab.cand)
    lab = lab.groupby(cc[:-1] + ['sn']).cls.agg(lambda x: x.iloc[0] if x.nunique() == 1 and len(x) == 1 else '')
    lab = lab[lab != ''].to_dict()
    miss = d.cls.isna() & ~d.has_o & ~generic
    if miss.any():
        sn = surname(d.loc[miss, 'cand'])
        keys = list(zip(*[d.loc[miss, k] for k in cc[:-1]], sn))
        got = pd.Series([lab.get(k, np.nan) for k in keys], index=d.index[miss])
        if got.notna().any():
            gg = d.loc[got.dropna().index].groupby(['state_po', 'off', 'cand']).votes.sum()
            log.append('surname-matched party: ' + '; '.join(f'{k}={v:.0f}' for k, v in gg.sort_values().tail(15).items()))
        d.loc[miss, 'cls'] = got
    for (yy, st, cn), c in OVERRIDE.items():
        if yy == year:
            m = (d.state_po == st) & (d.cand == cn)
            if m.any():
                log.append(f'party override {st} {cn} -> {c} ({d.loc[m, "votes"].sum():.0f} votes)')
                d.loc[m, 'cls'] = c
    d['cls'] = d.cls.fillna('O')
    # report big unlabeled candidates
    unl = d[(d.cls == 'O') & d.party_simplified.str.strip().isin(['', 'NONPARTISAN'])]
    big = unl.groupby(['state_po', 'off', 'cand']).votes.sum().sort_values(ascending=False)
    log.append('largest candidates with no party label anywhere (counted as oth): ' +
               '; '.join(f'{k}={v:.0f}' for k, v in big.head(20).items()))
    # party detail label per candidate (for races.csv)
    pdl = d.groupby(cc + ['party_detailed']).votes.sum().reset_index().sort_values('votes')
    pdl = pdl.drop_duplicates(cc, keep='last').rename(columns={'party_detailed': 'party_label'})
    cands = d.groupby(cc + ['cls']).agg(votes=('votes', 'sum'), nstar=('nstar', 'sum')).reset_index()
    cands = cands.merge(pdl[cc + ['party_label']], on=cc, how='left')
    for (yy, st, cn), lab in LABEL_OVERRIDE.items():
        if yy == year:
            cands.loc[(cands.state_po == st) & (cands.cand == cn), 'party_label'] = lab
    cands.insert(0, 'year', year)
    cands.to_csv(f'{W}/s2_cands_{year}.csv', index=False)

    # ---- county table
    d['dem'] = np.where(d.cls == 'D', d.votes, 0)
    d['rep'] = np.where(d.cls == 'R', d.votes, 0)
    d['oth'] = np.where(d.cls == 'O', d.votes, 0)
    cty = d.groupby(['off', 'spec', 'state_po', 'fips'])[['dem', 'rep', 'oth']].sum().reset_index()
    cty['total'] = cty.dem + cty.rep + cty.oth
    cty.insert(0, 'year', year)
    cty.to_csv(f'{W}/s2_county_{year}.csv', index=False)

    # ---- house districts
    h = d[d.off == 'HOUSE'].groupby(['state_po', 'spec', 'district_n'])[['dem', 'rep', 'oth']].sum().reset_index()
    h.insert(0, 'year', year)
    h.to_csv(f'{W}/s2_house_{year}.csv', index=False)
    with open(f'{W}/s2_log_{year}.txt', 'w') as fh:
        fh.write('\n'.join(log) + '\n')
    print(year, 'done', len(cty), len(cands), len(h))
    print('\n'.join(log)[:6000])


for y in sys.argv[1:]:
    run(int(y))
