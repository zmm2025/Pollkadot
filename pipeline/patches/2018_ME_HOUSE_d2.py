"""Regenerate data/results/patches/2018_ME_HOUSE_d2.csv (Maine 2nd District, 2018, first round) from the
Maine Secretary of State's official cast vote records.

Sources (saved in data/raw/state/2018_ME_HOUSE_d2/, from
https://www.maine.gov/sos/elections-voting/election-results-data/election-results-2018):
  Nov18CVRExportFINAL1-3.xlsx, RepCD2-8final.xlsx   cast vote records, precinct = municipality / township
  UOCAVA-FINALRepCD2.xlsx, UOCAVA-AUX-CVRRepCD2.xlsx, UOCAVA2CVRRepCD2.xlsx   statewide UOCAVA ballots
  AUXCVRProofedCVR95RepCD2.xlsx   ballots that could not be scanned (no municipality)
  updated-summary-report-CD2.xls  certified RCV summary report (round 1 used as the check)
  Rep-congress-results.xlsx       town-reported (unofficial) results, used only for the town -> county key

Each ballot's round-1 vote is its first ranked candidate under Maine's RCV rules (an overvote exhausts the
ballot; two consecutive skipped rankings exhaust it; a single skipped ranking is passed over). This reproduces
the certified round-1 totals exactly. Ballots are grouped by precinct; each precinct's county comes from its
ballot style (ballot styles are county-specific), and each style's county from the municipalities on it that
appear in the town-reported file. UOCAVA and unscannable ballots carry no municipality and are left out.
Run from the repository root.
"""
import collections
import csv
import importlib.util
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _xlsx import read_rows  # noqa: E402

RAW = 'data/raw/state/2018_ME_HOUSE_d2/'
OUT = 'data/results/patches/2018_ME_HOUSE_d2.csv'
TOWN_CVRS = ['Nov18CVRExportFINAL1.xlsx', 'Nov18CVRExportFINAL2.xlsx', 'Nov18CVRExportFINAL3.xlsx',
             'RepCD2-8final.xlsx']
OTHER_CVRS = ['UOCAVA-FINALRepCD2.xlsx', 'UOCAVA-AUX-CVRRepCD2.xlsx', 'UOCAVA2CVRRepCD2.xlsx',
              'AUXCVRProofedCVR95RepCD2.xlsx']
FIPS = {'AND': '23001', 'ARO': '23003', 'FRA': '23007', 'HAN': '23009', 'KEN': '23011', 'OXF': '23017',
        'PEN': '23019', 'PIS': '23021', 'SOM': '23025', 'WAL': '23027', 'WAS': '23029'}
# styles the town file cannot settle
STYLE_OVERRIDE = {'CAN Ballot Style 271': 'ARO',  # T11 R14 WELS (Northwest Aroostook), not in the town file
                  'CAN Ballot Style 143': 'HAN'}  # Great Pond + T3 ND Twp (both in Hancock; T3 ND votes in Burlington, Penobscot)
PARTY = {'Golden, Jared F.': 0, 'Poliquin, Bruce': 1, 'Bond, Tiffany L.': 2, 'Hoar, William R.S.': 2}


def clean(name):
    name = re.sub(r'\s*\(\d+\)$', '', name.strip())
    return re.sub(r'^(DEM|REP) ', '', name).strip()


def round1(ranks):
    skipped = 0
    for x in ranks:
        x = clean(x)
        if x == 'overvote':
            return 'overvote'
        if x == 'undervote':
            skipped += 1
            if skipped >= 2:
                return 'undervote'
            continue
        return x
    return 'undervote'


def certified():
    spec = importlib.util.spec_from_file_location('mesen', os.path.join(os.path.dirname(__file__), '2012_ME_SEN.py'))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    rows = m.to_rows(m.read_xls(RAW + 'updated-summary-report-CD2.xls')['RCV Report'])
    out = {}
    for r in rows:
        if r and isinstance(r[0], str) and isinstance(r[1] if len(r) > 1 else None, float):
            out[clean(r[0])] = int(r[1])
    return out


def town_counties():
    """name (lower case) -> set of county codes, from the town-reported file."""
    key = collections.defaultdict(set)
    for r in read_rows(RAW + 'Rep-congress-results.xlsx')[3:]:
        if len(r) > 2 and r[1] and r[2]:
            for part in re.split(r'\s*--\s*|/', r[2]):
                key[re.sub(r'\s*\(.*\)$', '', part).strip().lower()].add(r[1])
    return key


def main():
    ballots = []  # (precinct, style, round-1 choice)
    for f in TOWN_CVRS:
        for r in read_rows(RAW + f)[1:]:
            if r:
                ballots.append((r[1], r[2], round1(r[3:8])))
    other = collections.Counter()
    for f in OTHER_CVRS:
        for r in read_rows(RAW + f)[1:]:
            if r:
                other[round1(r[3:8])] += 1

    # precinct -> county via ballot style
    key = town_counties()
    style_cty = collections.defaultdict(collections.Counter)
    prec_styles = collections.defaultdict(set)
    for p, s, _ in ballots:
        prec_styles[p].add(s)
    for p, styles in prec_styles.items():
        q = re.sub(r'\s+(All|W\d+|Ward \d+)\b.*$', '', p)
        c = set()
        for part in q.split('/'):
            c |= key.get(part.strip().lower(), set())
        if len(c) == 1:
            cty = next(iter(c))
            for s in styles:
                style_cty[s][cty] += 1
    style_county = {}
    for s in {s for _, s, _ in ballots}:
        if s in STYLE_OVERRIDE:
            style_county[s] = STYLE_OVERRIDE[s]
            continue
        # A few townships are listed in the town file under the county of the town where their voters cast
        # ballots (e.g. Adamstown Twp under Rangeley, Franklin); their ballot style puts them in the county
        # where they lie (Adamstown Twp: Oxford). Take each style's majority county.
        (cty, n), *rest = style_cty[s].most_common()
        assert n > sum(k for _, k in rest), (s, style_cty[s])
        style_county[s] = cty

    out = collections.defaultdict(lambda: [0, 0, 0])
    town_total = collections.Counter()
    for p, s, v in ballots:
        town_total[v] += 1
        if v in PARTY:
            out[FIPS[style_county[s]]][PARTY[v]] += 1
        else:
            assert v in ('overvote', 'undervote'), v

    # check against the certified round 1
    cert = certified()
    allv = town_total + other
    for cand in PARTY:
        assert allv[cand] == cert[cand], (cand, allv[cand], cert[cand])
    sums = [sum(v[i] for v in out.values()) for i in range(3)]
    print('counties', sums, 'left out (UOCAVA + unscannable):', dict(other))
    print('certified round 1', {c: cert[c] for c in PARTY})
    for f in sorted(out):
        print(f, out[f])
    with open(OUT, 'w', newline='') as fh:
        w = csv.writer(fh)
        w.writerow(['year', 'office', 'special', 'state_po', 'fips', 'dem', 'rep', 'oth'])
        for f in sorted(out):
            w.writerow([2018, 'HOUSE', 0, 'ME', f, *out[f]])


if __name__ == '__main__':
    main()
