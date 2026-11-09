"""Build data/results/patches/2022_MI_HOUSE_midland.csv (Midland County, MI, 2022 U.S. House) from the
Michigan Secretary of State's official county-level results file for the Nov 8, 2022 general election.

Input: data/raw/state/2022_MI_HOUSE_midland/2022STATE_GENERAL_MI_CENR_BY_COUNTY.txt, the "Election Data"
download of https://mvic.sos.state.mi.us/votehistory/Index?type=C&electionDate=11-8-2022
(https://mvic.sos.state.mi.us/VoteHistory/GetElectionResultFile?electionId=691; tab-separated, one row
per county x candidate, file trailer "RESULTS: OFFICIAL").

Office code 6 = Representative in Congress; Midland is split between the 2nd and 8th districts and
both are summed. Democratic -> dem, Republican -> rep, all other parties and write-ins -> oth.
Michigan county codes are 1..83 in alphabetical order, so FIPS = 26 + (2*code - 1).

Run from the repo root: python -P pipeline/patches/2022_MI_HOUSE_midland.py
"""
import csv
from pathlib import Path

NAME, OFFICE, OFFICE_CODE = "2022_MI_HOUSE_midland", "HOUSE", "6"
COUNTIES = ["MIDLAND"]
SRC = Path(f"data/raw/state/{NAME}/2022STATE_GENERAL_MI_CENR_BY_COUNTY.txt")


def col(party):
    return "dem" if party == "Democratic" else "rep" if party == "Republican" else "oth"


def main():
    lines = SRC.read_text(encoding="latin-1").splitlines()
    rows = list(csv.DictReader(lines[1:], delimiter="\t"))
    assert "RESULTS: OFFICIAL" in lines[-1] or "RESULTS: OFFICIAL" in rows[-1]["ElectionDate"]
    out = {}
    for r in rows:
        if r["OfficeCode(text)"] != OFFICE_CODE or r["CountyName"] not in COUNTIES:
            continue
        fips = f"26{2 * int(r['CountyCode']) - 1:03d}"
        rec = out.setdefault(fips, {"dem": 0, "rep": 0, "oth": 0})
        rec[col(r["PartyDescription"])] += int(r["CandidateVotes"].replace(",", ""))
    assert len(out) == len(COUNTIES)
    path = Path(f"data/results/patches/{NAME}.csv")
    with open(path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["year", "office", "special", "state_po", "fips", "dem", "rep", "oth"])
        for fips, t in sorted(out.items()):
            w.writerow([2022, OFFICE, 0, "MI", fips, t["dem"], t["rep"], t["oth"]])
    print(f"wrote {path}: {out}")


if __name__ == "__main__":
    main()
