"""Regenerate data/results/patches/2022_CA_SEN_special.csv from the California Statement of Vote.

Source: https://elections.cdn.sos.ca.gov/sov/2022-general/sov/45-uss-pt.xlsx (United States Senator,
partial/unexpired term, by county), saved as data/raw/state/2022_CA_SEN_special/45-uss-pt.xlsx.
Run from the repository root.
"""
import csv, pickle, re, zipfile, xml.etree.ElementTree as ET

SRC = 'data/raw/state/2022_CA_SEN_special/45-uss-pt.xlsx'
OUT = 'data/results/patches/2022_CA_SEN_special.csv'
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
    fips = {n: i for i, n, s in zip(topo['ids'], topo['names'], topo['state']) if s == '06'}
    rows = read_xlsx(SRC)
    names = [(c or '').replace('\n', ' ').split() for c in rows[0]]
    parties = rows[1]
    out, state = {}, None
    for r in rows[2:]:
        if not r or not r[0] or r[0].strip() == 'Percent':
            continue
        vals = [int(float(v)) for v in r[1:] if v not in (None, '')]
        d = sum(v for v, p in zip(vals, parties[1:]) if p == 'DEM')
        rp = sum(v for v, p in zip(vals, parties[1:]) if p == 'REP')
        rec = (d, rp, sum(vals) - d - rp)
        if r[0].strip() == 'State Totals':
            state = rec
        else:
            out[fips[r[0].strip()]] = rec
    assert len(out) == 58, len(out)
    sums = tuple(sum(v[i] for v in out.values()) for i in range(3))
    assert sums == state, (sums, state)
    print('candidates', [' '.join(n) for n in names[1:]], 'state totals', state)
    with open(OUT, 'w', newline='') as fh:
        w = csv.writer(fh)
        w.writerow(['year', 'office', 'special', 'state_po', 'fips', 'dem', 'rep', 'oth'])
        for f in sorted(out):
            w.writerow([2022, 'SEN', 1, 'CA', f, *out[f]])


if __name__ == '__main__':
    main()
