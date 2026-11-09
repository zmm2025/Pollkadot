"""Build data/results/patches/2022_ID_GOV_power.csv (Power County, ID, 2022 Governor) from the Idaho
Secretary of State's official canvass database.

Input: data/raw/state/2022_ID_GOV_power/contest_17251_by_county.csv, downloaded from
https://canvass.sos.idaho.gov/eng/contests/download/17251/show_granularity_dt_id:3/.csv
(contest page https://canvass.sos.idaho.gov/contests/view/17251). The header gives each candidate's
name and party ("Name\nParty"); Democratic -> dem, Republican -> rep, all others (independents,
Libertarian, Constitution, write-ins) -> oth. "Total Votes Cast" is not a candidate.

Run from the repo root: python -P pipeline/patches/2022_ID_GOV_power.py
"""
import csv
from pathlib import Path

NAME, OFFICE = "2022_ID_GOV_power", "GOV"
SRC = Path(f"data/raw/state/{NAME}/contest_17251_by_county.csv")
COUNTY, FIPS = "Power", "16077"


def col(header):
    party = header.split("\n")[-1].strip()
    return "dem" if party == "Democratic" else "rep" if party == "Republican" else "oth"


def main():
    rows = list(csv.reader(open(SRC, encoding="utf-8-sig")))
    head = rows[0]
    (row,) = [r for r in rows[1:] if r and r[0] == COUNTY]
    tot = {"dem": 0, "rep": 0, "oth": 0}
    for h, v in zip(head[1:], row[1:]):
        if h != "Total Votes Cast":
            tot[col(h)] += int(v.replace(",", ""))
    assert sum(tot.values()) == int(row[-1].replace(",", ""))
    out = Path(f"data/results/patches/{NAME}.csv")
    with open(out, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["year", "office", "special", "state_po", "fips", "dem", "rep", "oth"])
        w.writerow([2022, OFFICE, 0, "ID", FIPS, tot["dem"], tot["rep"], tot["oth"]])
    print(f"wrote {out}: {tot}")


if __name__ == "__main__":
    main()
