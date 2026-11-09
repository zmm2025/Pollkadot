"""Regenerate data/results/patches/2018_NY_HOUSE.csv from the NY State Board of Elections certified results.

Source: https://www.elections.ny.gov/NYSBOE/elections/2018/general/2018Congress.xlsx (certified December 14,
2018; retrieved through the Internet Archive copy of 2018ElectionResults.html because the live site sits
behind a browser challenge), saved as data/raw/state/2018_NY_HOUSE/2018Congress.xlsx. One sheet per
district, one column per county (or part of county), one row per candidate and party line.

Every party line goes to its candidate; a candidate with a DEM line is dem, with a REP line rep, anyone else
oth (e.g. Crowley's WOR/WEP lines in NY-14). Scattering counts as oth; Blank and Void are left out. Counties
split between districts get every district's votes summed. Run from the repository root.
"""
import collections
import csv
import os
import pickle
import re
import sys
import zipfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _xlsx import read_rows  # noqa: E402

SRC = 'data/raw/state/2018_NY_HOUSE/2018Congress.xlsx'
OUT = 'data/results/patches/2018_NY_HOUSE.csv'
NYC = {'Bronx': '36005', 'Kings': '36047', 'New York': '36061', 'Queens': '36081', 'Richmond': '36085',
       'Chenago': '36017'}  # misspelling of Chenango in the source


def sheets(path):
    z = zipfile.ZipFile(path)
    wb = z.read('xl/workbook.xml').decode()
    rels = dict(re.findall(r'Id="([^"]*)"[^>]*Target="([^"]*)"', z.read('xl/_rels/workbook.xml.rels').decode()))
    for name, rid in re.findall(r'<sheet [^>]*name="([^"]*)"[^>]*r:id="([^"]*)"', wb):
        yield name, int(re.search(r'sheet(\d+)\.xml', rels[rid]).group(1))


def main():
    topo = pickle.load(open('data/geometry/topo_s.pkl', 'rb'))
    fips = {n: i for i, n, s in zip(topo['ids'], topo['names'], topo['state']) if s == '36'}
    fips.update(NYC)
    out = collections.defaultdict(lambda: [0, 0, 0])
    state = [0, 0, 0]
    report = []
    for name, k in sheets(SRC):
        rows = [r for r in read_rows(SRC, k) if r and any(x.strip() for x in r)]
        head = rows[1]
        cols = {}
        for j, h in enumerate(head):
            m = re.match(r'(?:Part of )?(.+?) County Vote Results$', h)
            if m:
                cols[j] = fips[m.group(1).strip()]
        jtot = head.index('Total Votes by Party')
        jcand = head.index('Total Votes by Candidate')
        lines, cand_tot = [], {}
        for r in rows[2:]:
            label = r[0].strip()
            if label in ('Blank', 'Void') or label.startswith('Total Votes'):
                continue
            if label == 'Scattering':
                cand, party = 'Scattering', ''
            else:
                cand, party = re.match(r'(.+?)\s*\((\w+)\)$', label).groups()
            vals = {j: int(r[j] or 0) for j in cols}
            assert sum(vals.values()) == int(r[jtot]), (name, label)
            if len(r) > jcand and r[jcand]:
                cand_tot[cand] = int(r[jcand])
            lines.append((cand, party, vals))
        parties = collections.defaultdict(set)
        for cand, party, _ in lines:
            parties[cand].add(party)
        cls = {}
        for cand, ps in parties.items():
            assert not ('DEM' in ps and 'REP' in ps), (name, cand)
            cls[cand] = 0 if 'DEM' in ps else 1 if 'REP' in ps else 2
        dist = [0, 0, 0]
        cand_sum = collections.Counter()
        for cand, party, vals in lines:
            for j, v in vals.items():
                out[cols[j]][cls[cand]] += v
                dist[cls[cand]] += v
                cand_sum[cand] += v
        for cand, t in cand_tot.items():
            assert cand_sum[cand] == t, (name, cand, cand_sum[cand], t)
        state = [a + b for a, b in zip(state, dist)]
        dem = [c for c in cls if cls[c] == 0]
        rep = [c for c in cls if cls[c] == 1]
        report.append((name, dem, rep, dist))
    for name, dem, rep, dist in report:
        print(f'{name:8s} D {dist[0]:>8,} {dem}  R {dist[1]:>8,} {rep}  O {dist[2]:,}')
    print('statewide', state, 'counties', len(out))
    assert len(out) == 62
    with open(OUT, 'w', newline='') as fh:
        w = csv.writer(fh)
        w.writerow(['year', 'office', 'special', 'state_po', 'fips', 'dem', 'rep', 'oth'])
        for f in sorted(out):
            w.writerow([2018, 'HOUSE', 0, 'NY', f, *out[f]])


if __name__ == '__main__':
    main()
