"""Build data/results/patches/2020_IN_HOUSE.csv from the Indiana Election Division's certified
election-night-reporting archive for the Nov 3, 2020 general election (all 9 U.S. House districts).

Input: data/raw/state/2020_IN_HOUSE/OffCatC_1005_A.json, downloaded from
https://enr.indianavoters.in.gov/archive/2020General/data/OffCatC_1005_A.json (office category 1005,
"US Representative"; one record per district x county, keyed by county FIPS). settings.json from the
same folder shows Certified = "T".

A county's value is the sum over every district that touches it. dem/rep = candidates with party
D/R; all others (Libertarian, independents, write-ins) are oth. Special elections are excluded.

Run from the repo root: python -P pipeline/patches/2020_IN_HOUSE.py
"""
import json
from pathlib import Path

import pandas as pd

YEAR = 2020
RAW = Path(f"data/raw/state/{YEAR}_IN_HOUSE/OffCatC_1005_A.json")
OUT = Path(f"data/results/patches/{YEAR}_IN_HOUSE.csv")


def as_list(x):
    return x if isinstance(x, list) else [x]


def col(party):
    return "dem" if party == "D" else "rep" if party == "R" else "oth"


def main():
    root = json.loads(RAW.read_bytes().decode("utf-8-sig", errors="replace"))["Root"]
    regular = {r["OFFICEID"] for r in as_list(root["StatewideSummary"]["Race"])
               if "special" not in r["OFFICE_TITLE"].lower()}
    rows = []
    for region in as_list(root["OfficeCategory"]["Regions"]["Region"]):
        for race in as_list(region["Races"]["Race"]):
            if race["OFFICEID"] not in regular:
                continue
            rec = {"fips": race["Jurisdiction"]["FIPS"], "dem": 0, "rep": 0, "oth": 0}
            for c in as_list(race["Candidates"]["Candidate"]):
                rec[col(c["PARTY_ABBREV"])] += int(c["TOTAL_VOTES"])
            rows.append(rec)
    out = pd.DataFrame(rows).groupby("fips", as_index=False)[["dem", "rep", "oth"]].sum()
    assert len(out) == 92, len(out)
    for i, (k, v) in enumerate([("year", YEAR), ("office", "HOUSE"), ("special", 0), ("state_po", "IN")]):
        out.insert(i, k, v)
    out = out.sort_values("fips")
    OUT.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(OUT, index=False)
    print(f"wrote {OUT} ({len(out)} rows)")

    # Check against the official district totals (statewide summary of the same file).
    tot = {"dem": 0, "rep": 0, "oth": 0}
    for r in as_list(root["StatewideSummary"]["Race"]):
        if r["OFFICEID"] in regular:
            for c in as_list(r["Candidates"]["Candidate"]):
                tot[col(c["PARTY"])] += int(c["TOTAL"])
    for k in tot:
        print(f"{k}: csv {out[k].sum():,}  official {tot[k]:,}")


if __name__ == "__main__":
    main()
