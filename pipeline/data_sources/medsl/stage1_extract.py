"""Stage 1: extract PRES/SEN/HOUSE/GOV rows from MEDSL precinct zips (2018-2024 format).
Keeps precinct-level rows for target offices, detects TOTAL-vs-mode double counting at the
precinct level, then aggregates away the precinct dimension.

usage: python3 -I stage1_extract.py YEAR OUTCSV ZIP [ZIP ...]
"""
import sys, zipfile, io, re
import pandas as pd
import numpy as np

year = sys.argv[1]
out = sys.argv[2]
zips = sys.argv[3:]

TARGET = {'US PRESIDENT', 'US SENATE', 'US SENATE - 2 YEAR TERM', 'US SENATE PARTIAL', 'US HOUSE',
          'GOVERNOR', 'GOVERNOR/LIEUTENANT GOVERNOR', 'GOVERNOR / LT. GOVERNOR',
          'GOVERNOR AND LIEUTENANT GOVERNOR'}
KEYS = ['state_po', 'county_fips', 'county_name', 'jurisdiction_name', 'jurisdiction_fips',
        'office', 'district', 'stage', 'special', 'candidate', 'party_detailed',
        'party_simplified', 'mode', 'writein', 'date', 'dataverse']
PKEY = ['state_po', 'county_fips', 'jurisdiction_fips', 'precinct', 'office', 'district', 'stage',
        'special', 'candidate', 'party_detailed']


sys.path.insert(0, 'pipeline/data_sources/medsl')
from aggrules import CKEY, drop_aggregate_rows

frames = []
for zp in zips:
    with zipfile.ZipFile(zp) as zf:
        names = [n for n in zf.namelist() if n.lower().endswith('.csv') and '__MACOSX' not in n]
        if len(names) > 1:
            print('multiple csvs', zp, names, '-> dropping *-sorted.csv duplicates')
            names = [n for n in names if not n.endswith('-sorted.csv')]
        for n in names:
            nrows = 0
            parts = []
            with zf.open(n) as fh:
                reader = pd.read_csv(io.TextIOWrapper(fh, encoding='utf-8', errors='replace'),
                                     dtype=str, keep_default_na=False, chunksize=500000,
                                     low_memory=False)
                for ch in reader:
                    nrows += len(ch)
                    if 'party' in ch.columns and 'party_detailed' not in ch.columns:
                        # legacy schema (2018 WI): party/county/jurisdiction, no fips
                        pu = ch['party'].str.upper().str.strip()
                        ch['party_detailed'] = pu
                        ch['party_simplified'] = pu.map({'DEMOCRAT': 'DEMOCRAT', 'DEMOCRATIC': 'DEMOCRAT',
                                                         'REPUBLICAN': 'REPUBLICAN',
                                                         'LIBERTARIAN': 'LIBERTARIAN'}).fillna(
                            pu.where(pu == '', 'OTHER'))
                        ch['county_name'] = ch['county'].str.upper().str.strip()
                        ch['jurisdiction_name'] = ch['jurisdiction'].str.upper().str.strip()
                    for k in KEYS + ['precinct']:
                        if k not in ch.columns:
                            ch[k] = ''
                    ch = ch[ch['office'].str.upper().str.strip().isin(TARGET)]
                    if not ch.empty:
                        parts.append(ch[KEYS + ['precinct', 'votes']].copy())
            if not parts:
                print(f'{zp}:{n} rows={nrows} target=0', flush=True)
                continue
            df = pd.concat(parts, ignore_index=True)
            raw = df['votes'].str.replace(',', '', regex=False).str.strip()
            v = pd.to_numeric(raw, errors='coerce')
            df['nstar'] = (v.isna() & (raw != '')).astype(int)
            df['votes'] = v.fillna(0)
            # precinct-level TOTAL vs split-mode detection
            # total-like rows: TOTAL, or UNSPECIFIED (NY 2022 uses UNSPECIFIED for county totals)
            df['is_tot'] = df['mode'].str.upper().str.strip().isin(['TOTAL', 'UNSPECIFIED'])
            df['not_tot'] = ~df['is_tot']
            g = df.groupby(PKEY, dropna=False)
            both = g['is_tot'].transform('any') & g['not_tot'].transform('any')
            df['dup_dropped'] = 0
            msg = ''
            if both.any():
                sub = df[both]
                tot = sub[sub.is_tot].groupby(PKEY, dropna=False)['votes'].sum()
                oth = sub[~sub.is_tot].groupby(PKEY, dropna=False)['votes'].sum()
                cmp = pd.concat([tot.rename('tot'), oth.rename('oth')], axis=1).fillna(0)
                eq = (cmp.tot - cmp.oth).abs() <= 0.5
                totge = cmp.tot >= cmp.oth - 0.5
                msg = (f' | groups_with_totallike_and_modes={len(cmp)} equal={int(eq.sum())}'
                       f' total_gt_modes={int((totge & ~eq).sum())} total_lt_modes={int((~totge).sum())}'
                       f' tot_votes={cmp.tot.sum():.0f} modes_votes={cmp.oth.sum():.0f}'
                       f' modes_in_total_lt={",".join(sorted(set(sub[~sub.is_tot]["mode"])))[:80]}')
                idx = pd.MultiIndex.from_frame(df[PKEY])
                keep_tot_keys = cmp.index[totge]
                in_keep_tot = idx.isin(keep_tot_keys)
                # total-like >= modes: keep total-like, drop modes; otherwise drop the total-like row
                drop = both & ((in_keep_tot & ~df['is_tot']) | (~in_keep_tot & df['is_tot']))
                df.loc[drop, 'dup_dropped'] = 1
            agg_msg = drop_aggregate_rows(df)
            kept = df[df.dup_dropped == 0]
            dropped = df[df.dup_dropped == 1]
            agg = kept.groupby(KEYS, dropna=False, as_index=False).agg(
                votes=('votes', 'sum'), nprec=('precinct', 'nunique'), nstar=('nstar', 'sum'))
            agg['srcfile'] = zp.split('/')[-1] + ':' + n
            frames.append(agg)
            print(f'{zp}:{n} rows={nrows} target={len(df)} nstar={int(df.nstar.sum())}'
                  f' dropped_dup_rows={len(dropped)} ({dropped.votes.sum():.0f} votes){msg}{agg_msg}', flush=True)

res = pd.concat(frames)
res.insert(0, 'year', year)
res.to_csv(out, index=False)
print('wrote', out, len(res))
