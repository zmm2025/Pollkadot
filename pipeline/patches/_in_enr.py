"""Shared reader for the Indiana Election Division's certified ENR archive JSON
(https://enr.indianavoters.in.gov/archive/2024General/data/OffCatC_<officecategory>_A.json).

county_totals() sums, for one county, every race of the office category whose county
breakdown includes that county (so a county split between House districts gets all of them).
Candidates with PARTY_ABBREV D -> dem, R -> rep, everything else (L, I, write-ins) -> oth.
"""
import json
from pathlib import Path

import pandas as pd


def _list(x):
    return x if isinstance(x, list) else [x]


def _agg(cands, key):
    out = {"dem": 0, "rep": 0, "oth": 0}
    for c in _list(cands):
        p = c.get("PARTY_ABBREV", c.get("PARTY"))
        out["dem" if p == "D" else "rep" if p == "R" else "oth"] += int(c[key])
    return out


def county_totals(path, fips, county_name):
    root = json.load(open(path, encoding="utf-8-sig"))["Root"]
    tot = {"dem": 0, "rep": 0, "oth": 0}
    n = 0
    for reg in _list(root["OfficeCategory"]["Regions"]["Region"]):
        for race in _list(reg["Races"]["Race"]):
            jname = race.get("Jurisdiction", {}).get("JURISDICTION_NAME")
            # Statewide offices: one region per county (MAP_FIPS). Districts: one race per county.
            if reg.get("MAP_FIPS") == fips or (reg.get("MAP_JURISDICTION_TYPE") == "District"
                                               and jname == county_name):
                for k, v in _agg(race["Candidates"]["Candidate"], "TOTAL_VOTES").items():
                    tot[k] += v
                n += 1
    assert n > 0, (path, fips)
    return tot, n


def statewide_totals(path):
    root = json.load(open(path, encoding="utf-8-sig"))["Root"]
    tot = {"dem": 0, "rep": 0, "oth": 0}
    for race in _list(root["StatewideSummary"]["Race"]):
        for k, v in _agg(race["Candidates"]["Candidate"], "TOTAL").items():
            tot[k] += v
    return tot


def build(name, office, category_file, fips="18105", county_name="Monroe"):
    raw = Path("data/raw/state") / name / category_file
    tot, n = county_totals(raw, fips, county_name)
    out = pd.DataFrame([{"year": 2024, "office": office, "special": 0, "state_po": "IN",
                         "fips": fips, **tot}])
    dest = Path("data/results/patches") / f"{name}.csv"
    out.to_csv(dest, index=False)
    print(f"wrote {dest}: {tot} ({n} race(s)); statewide official {statewide_totals(raw)}")
