"""Build data/results/patches/2024_LA_HOUSE.csv from the Louisiana Secretary of State's
official parish-level results (Nov 5, 2024, all 6 U.S. House districts).

Inputs: data/raw/state/2024_LA_HOUSE/ByParish_<raceid>.csv, downloaded from
https://voterportal.sos.la.gov/ElectionResults/ElectionResults/Data?blob=20241105/csv/ByParish_<raceid>.csv
(the "Download Results" CSV of the SOS Graphical results site; parish totals include early,
absentee and provisional votes). Votes_Multiparish.json holds the official district totals and is
used only for the check printed at the end.

A parish's value is the sum over every district that touches it. dem/rep = all candidates labelled
(DEM)/(REP); everything else (NOPTY, other parties) is oth.

Run from the repo root: python -P pipeline/patches/2024_LA_HOUSE.py
"""
import json
import re
from pathlib import Path

import pandas as pd

RAW = Path("data/raw/state/2024_LA_HOUSE")
OUT = Path("data/results/patches/2024_LA_HOUSE.csv")
RACES = ["67171", "67187", "67188", "67174", "67175", "67189"]  # CD1..CD6 (SOS race ids)

PARISHES = [
    "Acadia", "Allen", "Ascension", "Assumption", "Avoyelles", "Beauregard", "Bienville",
    "Bossier", "Caddo", "Calcasieu", "Caldwell", "Cameron", "Catahoula", "Claiborne",
    "Concordia", "De Soto", "East Baton Rouge", "East Carroll", "East Feliciana", "Evangeline",
    "Franklin", "Grant", "Iberia", "Iberville", "Jackson", "Jefferson", "Jefferson Davis",
    "Lafayette", "Lafourche", "Lasalle", "Lincoln", "Livingston", "Madison", "Morehouse",
    "Natchitoches", "Orleans", "Ouachita", "Plaquemines", "Pointe Coupee", "Rapides",
    "Red River", "Richland", "Sabine", "St. Bernard", "St. Charles", "St. Helena", "St. James",
    "St. John The Baptist", "St. Landry", "St. Martin", "St. Mary", "St. Tammany", "Tangipahoa",
    "Tensas", "Terrebonne", "Union", "Vermilion", "Vernon", "Washington", "Webster",
    "West Baton Rouge", "West Carroll", "West Feliciana", "Winn",
]
# Louisiana parish FIPS codes are the odd numbers 001..127 in alphabetical order.
FIPS = {name: f"22{2 * i + 1:03d}" for i, name in enumerate(PARISHES)}


def party(col):
    m = re.search(r"\(([A-Z]+)\)\s*$", col)
    p = m.group(1) if m else ""
    return "dem" if p == "DEM" else "rep" if p == "REP" else "oth"


def main():
    rows = []
    for race in RACES:
        df = pd.read_csv(RAW / f"ByParish_{race}.csv", dtype=str)
        for _, r in df.iterrows():
            rec = {"fips": FIPS[r["Parish"]], "race": race, "dem": 0, "rep": 0, "oth": 0}
            for col in df.columns[2:]:
                rec[party(col)] += int(str(r[col]).replace(",", ""))
            rows.append(rec)
    long = pd.DataFrame(rows)
    out = long.groupby("fips", as_index=False)[["dem", "rep", "oth"]].sum()
    assert len(out) == 64, len(out)
    out.insert(0, "state_po", "LA")
    out.insert(0, "special", 0)
    out.insert(0, "office", "HOUSE")
    out.insert(0, "year", 2024)
    out = out.sort_values("fips")
    OUT.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(OUT, index=False)
    print(f"wrote {OUT} ({len(out)} rows)")

    # Check against the official district totals.
    races = json.load(open(RAW / "RacesCandidates_Multiparish.json"))["Races"]["Race"]
    votes = json.load(open(RAW / "Votes_Multiparish.json"))["Races"]["Race"]
    desc = {c["ID"]: c["Desc"] for r in races if r["ID"] in RACES for c in r["Choice"]}
    tot = {"dem": 0, "rep": 0, "oth": 0}
    for r in votes:
        if r["ID"] in RACES:
            for c in r["Choice"]:
                tot[party(desc[c["ID"]])] += int(c["VoteTotal"])
    for k in tot:
        print(f"{k}: csv {out[k].sum():,}  official {tot[k]:,}")


if __name__ == "__main__":
    main()
