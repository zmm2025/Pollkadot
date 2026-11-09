"""Regenerate data/results/patches/2022_TN_GOV.csv from the Tennessee Secretary of State precinct file.

Source: https://sos-prod.tnsosgovfiles.com/s3fs-public/document/20221108AllbyPrecinct.xlsx
(saved as data/raw/state/2022_TN_GOV/20221108AllbyPrecinct.xlsx). Run from the repository root.
"""
import csv, pickle, re, zipfile, xml.etree.ElementTree as ET
from collections import defaultdict

SRC = 'data/raw/state/2022_TN_GOV/20221108AllbyPrecinct.xlsx'
OUT = 'data/results/patches/2022_TN_GOV.csv'
NS = '{http://schemas.openxmlformats.org/spreadsheetml/2006/main}'


def read_xlsx(path):
    """First worksheet as a list of rows (lists of strings/None); standard library only."""
    z = zipfile.ZipFile(path)
    shared = []
    if 'xl/sharedStrings.xml' in z.namelist():
        for si in ET.fromstring(z.read('xl/sharedStrings.xml')).iter(NS + 'si'):
            shared.append(''.join(t.text or '' for t in si.iter(NS + 't')))
    sheet = sorted(n for n in z.namelist() if re.match(r'xl/worksheets/sheet\d+\.xml$', n))[0]
    rows = []
    for _, el in ET.iterparse(z.open(sheet)):
        if el.tag == NS + 'row':
            row = []
            for c in el.iter(NS + 'c'):
                col = 0
                for ch in re.match(r'[A-Z]+', c.get('r')).group():
                    col = col * 26 + ord(ch) - 64
                v = c.find(NS + 'v')
                if c.get('t') == 's':
                    val = shared[int(v.text)]
                elif c.get('t') == 'inlineStr':
                    val = ''.join(t.text or '' for t in c.iter(NS + 't'))
                else:
                    val = v.text if v is not None else None
                row.extend([None] * (col - len(row)))
                row[col - 1] = val
            rows.append(row)
            el.clear()
    return rows


def main():
    topo = pickle.load(open('data/geometry/topo_s.pkl', 'rb'))
    fips = {n: i for i, n, s in zip(topo['ids'], topo['names'], topo['state']) if s == '47'}
    rows = read_xlsx(SRC)
    head = rows[0]
    tot = defaultdict(lambda: [0, 0, 0])
    for r in rows[1:]:
        r = r + [None] * (len(head) - len(r))
        rec = dict(zip(head, r))
        if rec['OFFICENAME'] != 'Governor':
            continue
        f = fips[rec['COUNTY']]
        for k in range(1, 11):
            name, party, votes = rec.get(f'RNAME{k}'), rec.get(f'PARTY{k}'), rec.get(f'PVTALLY{k}')
            if not name:
                continue
            v = int(float(votes or 0))
            col = 0 if party == 'Democratic' else 1 if party == 'Republican' else 2
            tot[f][col] += v
    assert len(tot) == 95, len(tot)
    with open(OUT, 'w', newline='') as fh:
        w = csv.writer(fh)
        w.writerow(['year', 'office', 'special', 'state_po', 'fips', 'dem', 'rep', 'oth'])
        for f in sorted(tot):
            w.writerow([2022, 'GOV', 0, 'TN', f, *tot[f]])
    d, r_, o = (sum(t[i] for t in tot.values()) for i in range(3))
    print(f'TN 2022 GOV: dem={d} rep={r_} oth={o}')


if __name__ == '__main__':
    main()
