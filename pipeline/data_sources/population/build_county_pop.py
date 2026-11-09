"""Build data/pop/county_pop.csv (fips, year, pop, source) for 2000-2026.

Inputs are Census Bureau files downloaded from www2.census.gov into build/downloads/census
(see data/pop/README.md for URLs and hashes), plus the CT-Data-Collaborative town->county list.
Run with: python -P pipeline/data_sources/population/build_county_pop.py
"""
import glob
import os
import sys

import numpy as np
import pandas as pd

DL = "build/downloads"
F_INT = f"{DL}/census/co-est00int-tot.csv"
F_19 = f"{DL}/census/co-est2019-alldata.csv"
F_25 = f"{DL}/census/co-est2025-alldata.csv"
F_SUB24 = f"{DL}/census/sub-est2024_9.csv"
F_CTFIPS = f"{DL}/census/ct-town-county-fips-list.csv"
OUT = "data/pop/county_pop.csv"

S_INT = "co-est00int-tot.csv"
S_19 = "co-est2019-alldata.csv"
S_25 = "co-est2025-alldata.csv"

STATES51 = {f"{i:02d}" for i in [1, 2, 4, 5, 6, 8, 9, 10, 11, 12, 13, 15, 16, 17, 18, 19, 20,
                                   21, 22, 23, 24, 25, 26, 27, 28, 29, 30, 31, 32, 33, 34, 35,
                                   36, 37, 38, 39, 40, 41, 42, 44, 45, 46, 47, 48, 49, 50, 51,
                                   53, 54, 55, 56]}
CT_OLD = ["09001", "09003", "09005", "09007", "09009", "09011", "09013", "09015"]

checks = []


def check(cond, msg):
    checks.append(("OK  " if cond else "FAIL") + " " + msg)
    if not cond:
        print("\n".join(checks))
        sys.exit("integrity check failed: " + msg)


def rd(path):
    return pd.read_csv(path, dtype=str, encoding="latin-1", keep_default_na=False)


# ---------------------------------------------------------------- intercensal 2000-2010
it = rd(F_INT)
it["SUMLEV"] = it["SUMLEV"].str.zfill(3)
it["fips"] = it["STATE"].str.zfill(2) + it["COUNTY"].str.zfill(3)
it_st = it[it.SUMLEV == "040"]
it = it[it.SUMLEV == "050"].copy()
Y_INT = list(range(2000, 2010))
for c in [f"POPESTIMATE{y}" for y in Y_INT] + ["CENSUS2010POP"]:
    it[c] = it[c].astype(np.int64)
    it_st[c] = it_st[c].astype(np.int64)
check(len(it) == 3143 and it.fips.is_unique, f"intercensal: 3143 unique county rows (got {len(it)})")
for c in [f"POPESTIMATE{y}" for y in Y_INT]:
    check(it[c].sum() == it_st[c].sum(), f"intercensal {c}: county sum == sum of state rows ({it[c].sum():,})")
us08, us09 = it.POPESTIMATE2008.sum(), it.POPESTIMATE2009.sum()

# ---------------------------------------------------------------- vintage 2019
v19 = rd(F_19)
v19["fips"] = v19["STATE"] + v19["COUNTY"]
v19_st = v19[v19.SUMLEV == "040"]
v19 = v19[v19.SUMLEV == "050"].copy()
Y19 = list(range(2010, 2020))
for c in [f"POPESTIMATE{y}" for y in Y19] + ["CENSUS2010POP"]:
    v19[c] = v19[c].astype(np.int64)
    v19_st[c] = v19_st[c].astype(np.int64)
check(len(v19) == 3142 and v19.fips.is_unique, f"co-est2019: 3142 unique county rows (got {len(v19)})")
for y in Y19:
    c = f"POPESTIMATE{y}"
    check(v19[c].sum() == v19_st[c].sum(), f"co-est2019 {c}: county sum == state rows")
check(v19.POPESTIMATE2019.sum() == 328239523, f"co-est2019 US 2019 = 328,239,523 (got {v19.POPESTIMATE2019.sum():,})")
check(v19.set_index("fips").POPESTIMATE2019["48301"] < 200, "co-est2019 Loving TX 2019 < 200")

# intercensal file vs co-est2019 : Census 2010 counts by county (independent files)
m = it[["fips", "CENSUS2010POP"]].merge(v19[["fips", "CENSUS2010POP"]], on="fips", how="outer",
                                         suffixes=("_int", "_v19"), indicator=True)
both = m[m._merge == "both"]
ndiff = int((both.CENSUS2010POP_int != both.CENSUS2010POP_v19).sum())
check(ndiff <= 30, f"intercensal vs co-est2019 CENSUS2010POP: {ndiff} of {len(both)} counties differ (CQR corrections expected few)")
only_int = sorted(m[m._merge == "left_only"].fips)
only_19 = sorted(m[m._merge == "right_only"].fips)
checks.append(f"INFO intercensal-only fips: {only_int}; co-est2019-only fips: {only_19}")
checks.append("INFO CENSUS2010POP differences: " + ", ".join(
    f"{r.fips}:{r.CENSUS2010POP_int}->{r.CENSUS2010POP_v19}" for r in both[both.CENSUS2010POP_int != both.CENSUS2010POP_v19].itertuples()))

# ---------------------------------------------------------------- vintage 2025
v25 = rd(F_25)
v25["fips"] = v25["STATE"] + v25["COUNTY"]
v25_st = v25[v25.SUMLEV == "040"]
v25 = v25[(v25.SUMLEV == "050")].copy()
Y25 = list(range(2020, 2026))
cols25 = [f"POPESTIMATE{y}" for y in Y25]
for c in cols25:
    v25[c] = v25[c].astype(np.int64)
    v25_st[c] = v25_st[c].astype(np.int64)
checks.append(f"INFO co-est2025 states present: {sorted(v25.STATE.unique())}")
v25 = v25[v25.STATE.isin(STATES51)]
v25_st = v25_st[v25_st.STATE.isin(STATES51)]


def popcols(d, lvl="050"):
    d = d.copy()
    d["SUMLEV"] = d["SUMLEV"].str.zfill(3)
    d["fips"] = d["STATE"].str.zfill(2) + d["COUNTY"].str.zfill(3)
    return d[d.SUMLEV == lvl].set_index("fips")[cols25].astype(np.int64).sort_index()


mine = v25.set_index("fips")[cols25].sort_index()
check(len(v25) == 3144 and v25.fips.is_unique, f"co-est2025: 3144 unique county rows in 50+DC (got {len(v25)})")
check(v25_st.STATE.nunique() == 51 and len(v25_st) == 51, "co-est2025: 51 state rows")
for y in Y25:
    c = f"POPESTIMATE{y}"
    check(v25[c].sum() == v25_st[c].sum(), f"co-est2025 {c}: county sum == state rows ({v25[c].sum():,})")
la = v25.set_index("fips").POPESTIMATE2020["06037"]
check(9_900_000 < la < 10_100_000, f"co-est2025 LA County 2020 ~10.0M (got {la:,})")
check(v25.set_index("fips").POPESTIMATE2025["48301"] < 200, "co-est2025 Loving TX 2025 < 200")
# ---------------------------------------------------------------- CT towns (vintage 2024 sub-county)
sub = rd(F_SUB24)
Y24 = list(range(2020, 2025))
for c in [f"POPESTIMATE{y}" for y in Y24]:
    sub[c] = sub[c].astype(np.int64)
towns = sub[sub.SUMLEV == "061"].copy()
regs24 = sub[sub.SUMLEV == "050"].copy()
check(len(towns) == 169 and towns.COUSUB.is_unique, f"sub-est2024 CT: 169 towns (got {len(towns)})")
for y in Y24:
    c = f"POPESTIMATE{y}"
    tsum = towns.groupby("COUNTY")[c].sum()
    rsum = regs24.set_index("COUNTY")[c]
    check(tsum.sort_index().equals(rsum.sort_index()), f"sub-est2024 CT {c}: towns sum to planning regions")
ctx = rd(F_CTFIPS)
ctx.columns = [c.strip("﻿").strip("ï»¿") for c in ctx.columns]
ctx["COUSUB"] = ctx["FIPS"].str[5:10]
ctx["old"] = ctx["FIPS"].str[0:5]
check(len(ctx) == 169 and ctx.COUSUB.is_unique, f"CT town list: 169 towns (got {len(ctx)})")
towns = towns.merge(ctx[["COUSUB", "old", "Town"]], on="COUSUB", how="left")
check(towns.old.notna().all(), "every V2024 CT town COUSUB found in CT town->county FIPS list")
nm = (towns.NAME.str.replace(r" town$", "", regex=True).str.strip() != towns.Town.str.strip()).sum()
check(nm == 0, f"CT town names agree between sub-est2024 and crosswalk ({nm} mismatches)")
check(sorted(towns.old.unique()) == CT_OLD, "CT towns map onto the 8 old counties")

ct_old_v19 = v19.set_index("fips").loc[CT_OLD]
regs25 = v25[v25.STATE == "09"].set_index("COUNTY")


def ct_old_counties(year):
    """Old-county values for `year` (2020-2025): V2024 town shares within planning regions,
    controlled to the V2025 planning-region totals, integerised by largest remainder."""
    ty = min(year, 2024)
    t = towns[["COUSUB", "COUNTY", "old", f"POPESTIMATE{ty}"]].copy()
    t["v"] = t[f"POPESTIMATE{ty}"].astype(float)
    rtot = t.groupby("COUNTY")["v"].transform("sum")
    t["w"] = t["v"] / rtot * regs25.loc[t.COUNTY, f"POPESTIMATE{year}"].to_numpy()
    f = t.groupby("old")["w"].sum().reindex(CT_OLD)
    target = int(regs25[f"POPESTIMATE{year}"].sum())
    fl = np.floor(f).astype(np.int64)
    rem = target - int(fl.sum())
    order = sorted(CT_OLD, key=lambda k: (-(f[k] - fl[k]), k))
    for k in order[:rem]:
        fl[k] += 1
    raw = t.groupby("old")[f"POPESTIMATE{ty}"].sum().reindex(CT_OLD)
    return fl, raw


# ---------------------------------------------------------------- assemble
rows = []


def add(fips, year, pop, source):
    rows.append((fips, year, int(pop), source))


def normalize(series, year, source, v2020_shares):
    """series: dict fips->pop for one year, in the file's native geography."""
    s = dict(series)
    for bad in ["02201", "02232", "02280"]:
        check(bad not in s, f"{year}: obsolete AK code {bad} absent from {source}")
    out = {}
    notes = {}
    for f, p in s.items():
        if f[:2] not in STATES51:
            continue
        if f == "46113":
            out["46102"] = out.get("46102", 0) + p
            notes["46102"] = f"{source}; 46113 recoded"
        elif f == "02270":
            out["02158"] = out.get("02158", 0) + p
            notes["02158"] = f"{source}; 02270 recoded"
        elif f == "51515":
            out["51019"] = out.get("51019", 0) + p
            notes["51019"] = f"{source}; +51515"
        elif f == "02261":
            sh063 = v2020_shares
            p063 = int(round(p * sh063))
            out["02063"] = p063
            out["02066"] = p - p063
            notes["02063"] = notes["02066"] = f"{source}; 02261 split by 2020 shares (approx)"
        else:
            out[f] = out.get(f, 0) + p
    if source == S_INT:
        # 2013 Petersburg Borough formation: remainder of Petersburg CA (02195) went to
        # Prince of Wales-Hyder (02198); a piece of Hoonah-Angoon (02105) went to 02195.
        # Transfer shares measured at Census 2010 (co-est2019 ESTIMATESBASE2010 vs CENSUS2010POP).
        t1 = AK_T["02198"] / AK_C["02195"]
        t2 = -AK_T["02105"] / AK_C["02105"]
        m1 = int(round(out["02195"] * t1))
        m2 = int(round(out["02105"] * t2))
        out["02195"] += m2 - m1
        out["02198"] += m1
        out["02105"] -= m2
        for f in ["02195", "02198", "02105"]:
            notes[f] = f"{source}; 2013 AK boundary transfer (approx)"
    return out, notes


_v = v19.set_index("fips")
AK_C = {f: int(_v.CENSUS2010POP[f]) for f in ["02195", "02198", "02105"]}
AK_T = {f: int(_v.ESTIMATESBASE2010.astype(np.int64)[f]) - AK_C[f] for f in ["02195", "02198", "02105"]}
checks.append(f"INFO AK 2010 census vs 2013-boundary base deltas: {AK_T}")
check(AK_T["02198"] > 500 and AK_T["02105"] < 0, "AK Petersburg transfer deltas look as expected")

v25i = v25.set_index("fips")
sh063 = v25i.POPESTIMATE2020["02063"] / (v25i.POPESTIMATE2020["02063"] + v25i.POPESTIMATE2020["02066"])

target = sorted([f for f in v25.fips if not f.startswith("09")] + CT_OLD)
check(len(target) == 3143, f"target county set = 3143 (3144 V2025 - 9 CT regions + 8 CT counties)")

ct_report = []
for year in range(2000, 2026):
    if year <= 2009:
        ser = dict(zip(it.fips, it[f"POPESTIMATE{year}"]))
        src = S_INT
    elif year <= 2019:
        ser = dict(zip(v19.fips, v19[f"POPESTIMATE{year}"]))
        src = S_19
    else:
        ser = dict(zip(v25.fips, v25[f"POPESTIMATE{year}"]))
        src = S_25
    out, notes = normalize(ser, year, src, sh063)
    if year >= 2020:
        for f in [k for k in out if k.startswith("091")]:
            del out[f]
        ct, raw = ct_old_counties(year)
        for f in CT_OLD:
            out[f] = int(ct[f])
            if year <= 2024:
                notes[f] = "sub-est2024_9.csv towns raked to co-est2025-alldata.csv regions"
            else:
                notes[f] = "sub-est2024_9.csv 2024 town shares x co-est2025-alldata.csv regions (approx)"
        ct_report.append((year, {f: (int(ct[f]), int(raw[f])) for f in CT_OLD}))
    check(sorted(out) == target, f"{year}: county set matches target ({len(out)} counties; "
          f"missing {sorted(set(target)-set(out))[:5]} extra {sorted(set(out)-set(target))[:5]})")
    tot_in = sum(p for f, p in ser.items() if f[:2] in STATES51)
    check(sum(out.values()) == tot_in, f"{year}: total preserved through normalization ({tot_in:,})")
    for f in target:
        add(f, year, out[f], notes.get(f, src))

# 2026 = latest available (2025)
for f, y, p, s in [r for r in rows if r[1] == 2025]:
    add(f, 2026, p, "2025 value carried forward (no 2026 estimate); " + s)

df = pd.DataFrame(rows, columns=["fips", "year", "pop", "source"]).sort_values(["fips", "year"])
check(not df.duplicated(["fips", "year"]).any(), "no duplicate fips-year")
check((df["pop"] > 0).all(), "all pop > 0")
os.makedirs(os.path.dirname(OUT), exist_ok=True)
df.to_csv(OUT, index=False, lineterminator="\n")

print("\n".join(checks))
print("\nrows per year:\n", df.groupby("year").size().to_string())
print("\nUS total per year:\n", df.groupby("year")["pop"].sum().map("{:,}".format).to_string())
print("\nsources:\n", df.groupby(["source"]).size().to_string())
print(f"\n02063 share of 02261 (V2025 July 2020): {sh063:.6f}")
print("\nCT old counties (controlled, raw V2024 town sums):")
for y, d in ct_report:
    print(y, d)
print("\nCT old counties 2019 (co-est2019):", ct_old_v19.POPESTIMATE2019.to_dict())
