"""Minimal stdlib reader for simple .xlsx files (first sheet -> list of rows of strings)."""
import re
import zipfile
import xml.etree.ElementTree as ET

NS = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}


def _col(ref):
    letters = re.match(r"[A-Z]+", ref).group(0)
    n = 0
    for ch in letters:
        n = n * 26 + ord(ch) - 64
    return n - 1


def read_rows(path, sheet=1):
    with zipfile.ZipFile(path) as z:
        shared = []
        if "xl/sharedStrings.xml" in z.namelist():
            for si in ET.fromstring(z.read("xl/sharedStrings.xml")).findall("m:si", NS):
                shared.append("".join(t.text or "" for t in si.iter(f"{{{NS['m']}}}t")))
        root = ET.fromstring(z.read(f"xl/worksheets/sheet{sheet}.xml"))
    rows = []
    for row in root.iter(f"{{{NS['m']}}}row"):
        vals = {}
        for c in row.findall("m:c", NS):
            t = c.get("t")
            v = c.find("m:v", NS)
            if t == "inlineStr":
                text = "".join(x.text or "" for x in c.iter(f"{{{NS['m']}}}t"))
            elif v is None:
                text = ""
            elif t == "s":
                text = shared[int(v.text)]
            else:
                text = v.text
            vals[_col(c.get("r"))] = text
        rows.append([vals.get(i, "") for i in range(max(vals) + 1)] if vals else [])
    return rows
