"""Build data/results/patches/2022_AR_GOV_phillips.csv (Phillips County, AR, 2022 Governor) from the
Arkansas Secretary of State's official results file for the Nov 8, 2022 general election.

Source: https://results.tally-enr.com/results/arkansas/1844/FullDataFile.json (the data file behind
https://arkansas.tally-enr.com/#election=1844, linked from the SOS "Election Results" page; the file's
ElectionInfo.IsOfficial is true). It is ~26 MB, so it is not kept in data/raw; it is downloaded to
build/downloads/state/2022_AR_phillips/ if absent (or pass a path as the first argument).

dem/rep = candidates whose PartyName is Democratic/Republican Party; everyone else is oth.

Run from the repo root: python -P pipeline/patches/2022_AR_GOV_phillips.py
"""
import csv
import json
import sys
import urllib.request
from pathlib import Path

URL = "https://results.tally-enr.com/results/arkansas/1844/FullDataFile.json"
SRC = Path(sys.argv[1] if len(sys.argv) > 1 else "build/downloads/state/2022_AR_phillips/FullDataFile_arkansas.json")
CONTEST, OFFICE, NAME = "Governor", "GOV", "2022_AR_GOV_phillips"
COUNTY, FIPS = "PHILLIPS", "05107"


def col(party):
    return "dem" if party.startswith("Democratic") else "rep" if party.startswith("Republican") else "oth"


def main():
    if not SRC.exists():
        SRC.parent.mkdir(parents=True, exist_ok=True)
        req = urllib.request.Request(URL, headers={"User-Agent": "Mozilla/5.0"})
        SRC.write_bytes(urllib.request.urlopen(req).read())
    data = json.loads(SRC.read_bytes().decode("utf-8-sig"))
    assert data["ElectionInfo"]["IsOfficial"]
    (contest,) = [c for c in data["ContestData"] if c["ContestName"] == CONTEST]
    party = {c["Name"]: c["PartyName"] for c in contest["Candidates"]}
    tot = {"dem": 0, "rep": 0, "oth": 0}
    for county in contest["Counties"]:
        if county["CountyName"].upper() == COUNTY:
            for c in county["Candidates"]:
                tot[col(party[c["Name"]])] += int(c["TotalVotes"])
    out = Path(f"data/results/patches/{NAME}.csv")
    with open(out, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["year", "office", "special", "state_po", "fips", "dem", "rep", "oth"])
        w.writerow([2022, OFFICE, 0, "AR", FIPS, tot["dem"], tot["rep"], tot["oth"]])
    print(f"wrote {out}: {tot}")


if __name__ == "__main__":
    main()
