"""Regenerate data/results/patches/2016_IN_HOUSE_fix.csv from the Indiana Election Division results archive.

Source: https://enr.indianavoters.in.gov/archive/2016General/data/OffCatC_1753_A.json (the data file behind the
Election Division's archived 2016 general election results site, "US Representative" office category; one
record per district and county), saved as data/raw/state/2016_IN_HOUSE_fix/OffCatC_1753_A.json.

Only Grant (18053), Kosciusko (18085) and Wabash (18169) are written (mode fill); each county's value is the
sum over every district record for that county. Democratic candidates are dem, Republicans rep, all others
(Libertarians, write-ins) oth. Each district's county records are checked against its district total.
Run from the repository root.
"""
import collections
import csv
import json

SRC = 'data/raw/state/2016_IN_HOUSE_fix/OffCatC_1753_A.json'
OUT = 'data/results/patches/2016_IN_HOUSE_fix.csv'
COUNTIES = ['18053', '18085', '18169']


def aslist(x):
    return x if isinstance(x, list) else [x]


def main():
    root = json.load(open(SRC, encoding='utf-8-sig'))['Root']
    out = collections.defaultdict(lambda: [0, 0, 0])
    for reg in aslist(root['OfficeCategory']['Regions']['Region']):
        dist = reg['MAP_JURISDICTION_NAME']
        summ = {c['NAME_ON_BALLOT']: int(c['TOTAL']) for c in aslist(reg['RegionSummary']['Race']['Candidates']['Candidate'])}
        csum = collections.Counter()
        dist_vals = [0, 0, 0]
        for race in aslist(reg['Races']['Race']):
            f = race['Jurisdiction']['FIPS']
            for c in aslist(race['Candidates']['Candidate']):
                v = int(c['TOTAL_VOTES'])
                k = 0 if c['PARTY_ABBREV'] == 'D' else 1 if c['PARTY_ABBREV'] == 'R' else 2
                csum[c['NAME_ON_BALLOT']] += v
                dist_vals[k] += v
                if f in COUNTIES:
                    out[f][k] += v
        assert csum == summ, (dist, csum, summ)
        print('IN-%s' % dist, 'D %d R %d O %d' % tuple(dist_vals))
    assert sorted(out) == COUNTIES
    with open(OUT, 'w', newline='') as fh:
        w = csv.writer(fh)
        w.writerow(['year', 'office', 'special', 'state_po', 'fips', 'dem', 'rep', 'oth'])
        for f in COUNTIES:
            print(f, out[f])
            w.writerow([2016, 'HOUSE', 0, 'IN', f, *out[f]])


if __name__ == '__main__':
    main()
