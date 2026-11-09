"""Build data/results/patches/2024_ND_GOV.csv (fill: Burleigh and Divide counties) from the
North Dakota Secretary of State's official county results for Governor and Lt. Governor, 2024.

Input: data/raw/state/2024_ND_GOV/Statewide County Results.xlsx, the "County" export of the
Governor contest at https://results.sos.nd.gov/ResultsSW.aspx?text=Race&type=SW&map=CTY
(sheet titled "2024 Official General Election Results").

Run from the repo root: python -P pipeline/patches/2024_ND_GOV.py
"""
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _xlsx import read_rows  # noqa: E402

RAW = Path("data/raw/state/2024_ND_GOV/Statewide County Results.xlsx")
OUT = Path("data/results/patches/2024_ND_GOV.csv")
FILL = {"Burleigh": "38015", "Divide": "38023"}


def main():
    rows = read_rows(RAW)
    assert "Official" in rows[0][0], rows[0]
    hdr_i = next(i for i, r in enumerate(rows) if len(r) > 1 and r[1] == "County")
    hdr = rows[hdr_i]
    cand = hdr[3:]
    kind = ["rep" if "Republican" in c else "dem" if "Democratic" in c else "oth" for c in cand]
    assert kind.count("rep") == 1 and kind.count("dem") == 1, cand
    recs, totals = [], None
    for r in rows[hdr_i + 1:]:
        if len(r) < 4:
            continue
        vals = [int(v) for v in r[3:3 + len(cand)]]
        agg = {"dem": 0, "rep": 0, "oth": 0}
        for k, v in zip(kind, vals):
            agg[k] += v
        if r[1] == "TOTALS":
            totals = agg
        elif r[1] in FILL:
            recs.append({"year": 2024, "office": "GOV", "special": 0, "state_po": "ND",
                         "fips": FILL[r[1]], **agg})
    out = pd.DataFrame(recs).sort_values("fips")
    assert len(out) == len(FILL)
    out.to_csv(OUT, index=False)
    print(out.to_string(index=False))
    print("official statewide totals:", totals)


if __name__ == "__main__":
    main()
