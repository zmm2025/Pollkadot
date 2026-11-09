"""Regenerate data/results/patches/2012_ME_SEN.csv from the Maine Secretary of State municipal results.

Source: https://www.maine.gov/sos/sites/maine.gov.sos/files/inline-files/2012ussenatemuni.xls
(saved as data/raw/state/2012_ME_SEN/2012ussenatemuni.xls). Towns are summed to counties; the
statewide-only "STATE UOCAVA" line is left out. The county file 2012ussenatecnty.xls is used as a check.
The .xls (BIFF8) files are read with a small standard-library reader below. Run from the repository root.
"""
import csv, pickle
import struct


def _ole_stream(data, want='Workbook'):
    """Extract a named stream from an OLE2 compound file (standard library only)."""
    if data[:8] != bytes.fromhex('D0CF11E0A1B11AE1'):
        raise ValueError('not an OLE2 (.xls) file')
    ssz = 1 << struct.unpack_from('<H', data, 0x1E)[0]
    msz = 1 << struct.unpack_from('<H', data, 0x20)[0]
    nfat, dir0 = struct.unpack_from('<II', data, 0x2C)
    cutoff, mfat0, nmfat, difat0, ndifat = struct.unpack_from('<IIIII', data, 0x38)
    sect = lambda i: data[512 + i * ssz: 512 + (i + 1) * ssz]
    difat = list(struct.unpack_from('<109I', data, 0x4C))
    d = difat0
    for _ in range(ndifat):
        blk = struct.unpack('<%dI' % (ssz // 4), sect(d))
        difat += blk[:-1]
        d = blk[-1]
    fat = []
    for s in difat[:nfat]:
        fat += struct.unpack('<%dI' % (ssz // 4), sect(s))

    def chain(start, table):
        out, s = [], start
        while s < 0xFFFFFFFA:
            out.append(s)
            s = table[s]
        return out

    dirdata = b''.join(sect(s) for s in chain(dir0, fat))
    entries = []
    for off in range(0, len(dirdata), 128):
        e = dirdata[off:off + 128]
        nlen = struct.unpack_from('<H', e, 0x40)[0]
        name = e[:max(nlen - 2, 0)].decode('utf-16-le')
        etype = e[0x42]
        start, size = struct.unpack_from('<II', e, 0x74)
        entries.append((name, etype, start, size))
    root = entries[0]
    for name, etype, start, size in entries:
        if name in (want, 'Book') and etype == 2:
            if size >= cutoff:
                return b''.join(sect(s) for s in chain(start, fat))[:size]
            mfat = []
            for s in chain(mfat0, fat):
                mfat += struct.unpack('<%dI' % (ssz // 4), sect(s))
            ministream = b''.join(sect(s) for s in chain(root[2], fat))
            return b''.join(ministream[s * msz:(s + 1) * msz] for s in chain(start, mfat))[:size]
    raise ValueError('no Workbook stream')


def _rk(v):
    if v & 2:
        x = v >> 2
        if x & 0x20000000:
            x -= 0x40000000
        x = float(x)
    else:
        x = struct.unpack('<d', struct.pack('<Q', (v & 0xFFFFFFFC) << 32))[0]
    return x / 100 if v & 1 else x


def read_xls(path):
    """Return {sheet name: {(row, col): value}} for a BIFF8 .xls file. Values are str or float."""
    wb = _ole_stream(open(path, 'rb').read())
    recs, pos = [], 0
    while pos + 4 <= len(wb):
        rt, ln = struct.unpack_from('<HH', wb, pos)
        recs.append((pos, rt, wb[pos + 4:pos + 4 + ln]))
        pos += 4 + ln
    sheets, sst, i = [], [], 0
    while i < len(recs):
        p, rt, body = recs[i]
        if rt == 0x85:
            off = struct.unpack_from('<I', body)[0]
            n, fl = body[6], body[7]
            name = body[8:8 + n * 2].decode('utf-16-le') if fl & 1 else body[8:8 + n].decode('latin-1')
            sheets.append((off, name))
        elif rt == 0xFC:
            pieces = [body[8:]]
            while i + 1 < len(recs) and recs[i + 1][1] == 0x3C:
                i += 1
                pieces.append(recs[i][2])
            sst = _parse_sst(pieces, struct.unpack_from('<I', body, 4)[0])
        i += 1
    bypos = {p: k for k, (p, _, _) in enumerate(recs)}
    out = {}
    for off, name in sheets:
        cells, k, pending = {}, bypos[off] + 1, None
        while k < len(recs) and recs[k][1] != 0x0A:
            _, rt, b = recs[k]
            if rt == 0xFD:
                r, c, _, ix = struct.unpack_from('<HHHI', b)
                cells[(r, c)] = sst[ix]
            elif rt == 0x203:
                r, c, _, v = struct.unpack_from('<HHHd', b)
                cells[(r, c)] = v
            elif rt == 0x27E:
                r, c, _, v = struct.unpack_from('<HHHI', b)
                cells[(r, c)] = _rk(v)
            elif rt == 0xBD:
                r, c = struct.unpack_from('<HH', b)
                for j in range((len(b) - 6) // 6):
                    cells[(r, c + j)] = _rk(struct.unpack_from('<I', b, 4 + j * 6 + 2)[0])
            elif rt == 0x204:
                r, c, _, n = struct.unpack_from('<HHHH', b)
                fl = b[8]
                cells[(r, c)] = b[9:9 + n * 2].decode('utf-16-le') if fl & 1 else b[9:9 + n].decode('latin-1')
            elif rt == 0x06:
                r, c = struct.unpack_from('<HH', b)
                res = b[6:14]
                if res[6:8] == b'\xff\xff':
                    if res[0] == 0:
                        pending = (r, c)
                else:
                    cells[(r, c)] = struct.unpack('<d', res)[0]
            elif rt == 0x207 and pending:
                n, fl = struct.unpack_from('<H', b)[0], b[2]
                cells[pending] = b[3:3 + n * 2].decode('utf-16-le') if fl & 1 else b[3:3 + n].decode('latin-1')
                pending = None
            k += 1
        out[name] = cells
    return out


def _parse_sst(pieces, count):
    strs, pi, pos = [], 0, 0
    buf = pieces[0]

    def need(n):
        nonlocal buf, pi, pos
        if pos + n > len(buf) and pos >= len(buf):
            pi += 1
            buf, pos = pieces[pi], 0

    for _ in range(count):
        need(3)
        nch = struct.unpack_from('<H', buf, pos)[0]
        fl = buf[pos + 2]
        pos += 3
        rich = ext = 0
        if fl & 8:
            rich = struct.unpack_from('<H', buf, pos)[0]
            pos += 2
        if fl & 4:
            ext = struct.unpack_from('<I', buf, pos)[0]
            pos += 4
        chars, wide = [], fl & 1
        while nch > 0:
            if pos >= len(buf):
                pi += 1
                buf, pos = pieces[pi], 0
                wide = buf[0] & 1
                pos = 1
            w = 2 if wide else 1
            avail = (len(buf) - pos) // w
            take = min(avail, nch)
            seg = buf[pos:pos + take * w]
            chars.append(seg.decode('utf-16-le') if wide else seg.decode('latin-1'))
            pos += take * w
            nch -= take
        skip = rich * 4 + ext
        while skip > 0:
            if pos >= len(buf):
                pi += 1
                buf, pos = pieces[pi], 0
            t = min(skip, len(buf) - pos)
            pos += t
            skip -= t
        strs.append(''.join(chars))
    return strs


def to_rows(cells):
    if not cells:
        return []
    nr = max(r for r, _ in cells) + 1
    nc = max(c for _, c in cells) + 1
    rows = [[None] * nc for _ in range(nr)]
    for (r, c), v in cells.items():
        rows[r][c] = v
    return rows


SRC = 'data/raw/state/2012_ME_SEN/2012ussenatemuni.xls'
CHECK = 'data/raw/state/2012_ME_SEN/2012ussenatecnty.xls'
OUT = 'data/results/patches/2012_ME_SEN.csv'


def columns(rows):
    head = rows[4]
    party = rows[6]
    cols = {}
    for j, h in enumerate(head):
        if j == 0 or not h or h in ('%', 'BLANK', 'TOTAL VOTES CAST'):
            continue
        p = party[j]
        cols[j] = 0 if p == 'Democrat' else 1 if p == 'Republican' else 2
    return cols


def tally(r, cols):
    t = [0, 0, 0]
    for j, k in cols.items():
        t[k] += int(r[j] or 0)
    return t


def main():
    topo = pickle.load(open('data/geometry/topo_s.pkl', 'rb'))
    fips = {n: i for i, n, s in zip(topo['ids'], topo['names'], topo['state']) if s == '23'}
    rows = to_rows(read_xls(SRC)['US Senate - By Municipality'])
    cols = columns(rows)
    out, block, uocava = {}, [0, 0, 0], None
    for r in rows[7:]:
        name = (r[0] or '').strip()
        if not name or not isinstance(r[1], float):
            continue
        t = tally(r, cols)
        if name.endswith(' County Totals'):
            assert t == block, (name, t, block)
            out[fips[name[:-len(' County Totals')]]] = block
            block = [0, 0, 0]
        elif name == 'STATE UOCAVA':
            uocava = t
        elif name == 'Totals':
            state = t
        else:
            block = [a + b for a, b in zip(block, t)]
    assert len(out) == 16, len(out)
    # cross-check against the official county file
    crows = to_rows(read_xls(CHECK)['U.S. Senate - By County'])
    for r in crows[7:]:
        if r[0] and r[0].strip() in fips:
            assert tally(r, columns(crows)) == out[fips[r[0].strip()]], r[0]
    sums = [sum(v[i] for v in out.values()) for i in range(3)]
    assert [a + b for a, b in zip(sums, uocava)] == state
    print('counties', sums, 'UOCAVA (left out)', uocava, 'official Totals', state)
    with open(OUT, 'w', newline='') as fh:
        w = csv.writer(fh)
        w.writerow(['year', 'office', 'special', 'state_po', 'fips', 'dem', 'rep', 'oth'])
        for f in sorted(out):
            w.writerow([2012, 'SEN', 0, 'ME', f, *out[f]])


if __name__ == '__main__':
    main()
