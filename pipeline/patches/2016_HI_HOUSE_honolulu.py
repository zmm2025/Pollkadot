"""Regenerate data/results/patches/2016_HI_HOUSE_honolulu.csv (Honolulu County, 2016 regular U.S. House races)
from the Hawaii Office of Elections final precinct results.

Sources (saved in data/raw/state/2016_HI_HOUSE_honolulu/):
  https://files.hawaii.gov/elections/files/results/2016/general/media.txt    precinct results (absentee mail,
      absentee walk-in and election-day votes per precinct)
  https://files.hawaii.gov/elections/files/results/2016/general/summary.txt  statewide final summary (check)
  https://files.hawaii.gov/elections/files/results/2016/general/cch.pdf      City and County of Honolulu final
      summary report (check: HI-1 Hanabusa 145,417 / Ostrov 45,958; HI-2 Gabbard 57,922 / Kaaihue 15,205)

Honolulu County is every precinct in State House districts 17-51 (Oahu). Contest 3 (U.S. Representative,
Dist I, the regular race, wholly on Oahu) and contest 5 (Dist II) are summed; contest 4, the same-day
Dist I Vacancy special election, is excluded. (D) is dem, (R) rep, everyone else oth; blank and over votes are
not in the file. Run from the repository root.
"""
import collections
import csv
import re

SRC = 'data/raw/state/2016_HI_HOUSE_honolulu/media.txt'
SUMMARY = 'data/raw/state/2016_HI_HOUSE_honolulu/summary.txt'
OUT = 'data/results/patches/2016_HI_HOUSE_honolulu.csv'
CONTESTS = {'3': 'U.S. Representative, Dist I', '5': 'U.S. Representative, Dist II'}


def cls(name):
    return 0 if name.startswith('(D)') else 1 if name.startswith('(R)') else 2


def main():
    hon = [0, 0, 0]
    state = collections.Counter()
    by_contest = collections.defaultdict(lambda: [0, 0, 0])
    for r in csv.DictReader(open(SRC, newline='', encoding='latin-1')):
        cid = r['Contest_id']
        if cid not in CONTESTS or not re.match(r'^\d\d-\d\d$', r['Precinct_Name']):
            continue
        assert r['Contest_title'].strip() == CONTESTS[cid]
        v = int(r['Absentee_votes']) + int(r['Early_votes']) + int(r['Election_Votes'])
        state[(cid, r['Candidate_name'])] += v
        if int(r['Precinct_Name'][:2]) >= 17:
            hon[cls(r['Candidate_name'])] += v
            by_contest[cid][cls(r['Candidate_name'])] += v
    # precinct sums must equal the official statewide summary
    for r in csv.DictReader(open(SUMMARY, newline='', encoding='latin-1')):
        cid = r['Contest ID']
        if cid in CONTESTS:
            assert state[(cid, r['Candidate Name'])] == int(r['Total Votes']), r
    assert by_contest['5'][:2] == [57922, 15205], by_contest['5']  # cch.pdf
    assert by_contest['3'] == [145417, 45958, 6601 + 4381], by_contest['3']
    print('HI-1 regular (all Honolulu)', by_contest['3'], 'HI-2 Honolulu part', by_contest['5'], 'Honolulu', hon)
    with open(OUT, 'w', newline='') as fh:
        w = csv.writer(fh)
        w.writerow(['year', 'office', 'special', 'state_po', 'fips', 'dem', 'rep', 'oth'])
        w.writerow([2016, 'HOUSE', 0, 'HI', '15003', *hon])


if __name__ == '__main__':
    main()
