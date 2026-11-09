"""Build data/metrics/education.csv and gdp.csv from vendored federal files.

Run: python3 -I pipeline/data_sources/metrics/build_metrics.py
Deterministic: no randomness, sorted output, integer largest-remainder allocation.
"""
import hashlib
import numpy as np
import pandas as pd

DL = "build/downloads"
OUT = "data/metrics"
# official downloads (see data/metrics/README.md for URLs)
F_EDU = f"{DL}/ers/Education2023.csv"                      # ers.usda.gov
F_EDU_PCT = f"{DL}/ers/zreller_education2023.csv"           # optional cross-check, skipped if absent
F_GDP_ZIP = f"{DL}/bea/CAGDP1.zip"                          # apps.bea.gov/regional/zip/CAGDP1.zip
F_GDP = f"{DL}/bea/x/CAGDP1__ALL_AREAS_2001_2024.csv"      # extracted from the zip
F_POP = "data/pop/county_pop.csv"
F_SUB24 = f"{DL}/census/sub-est2024_9.csv"
F_CTFIPS = f"{DL}/census/ct-town-county-fips-list.csv"

LOG = []


def log(msg):
    print(msg)
    LOG.append(msg)


def check(cond, msg, quiet=False):
    if not (quiet and cond):
        log(("OK   " if cond else "FAIL ") + msg)
    if not cond:
        raise SystemExit("check failed: " + msg)


def sha(p):
    return hashlib.sha256(open(p, "rb").read()).hexdigest()


def lr_int(frac: pd.Series, target: int) -> pd.Series:
    """Largest-remainder integerisation; ties broken by index (deterministic)."""
    fl = np.floor(frac).astype(np.int64)
    rem = int(target - fl.sum())
    order = sorted(frac.index, key=lambda k: (-(frac[k] - fl[k]), k))
    for k in order[:rem]:
        fl[k] += 1
    return fl


for p in [F_EDU, F_GDP, F_GDP_ZIP, F_POP, F_SUB24, F_CTFIPS]:
    log(f"sha256 {sha(p)}  {p}")

# ------------------------------------------------------------------ common: target set, pop, CT towns
pop = pd.read_csv(F_POP, dtype={"fips": str})
TARGET = sorted(set(pop.fips) - {"02063", "02066"} | {"02261"})
check(len(TARGET) == 3142, f"target county set has 3142 FIPS (got {len(TARGET)})")
popw = pop.pivot(index="fips", columns="year", values="pop")
CT_OLD = [f"09{c:03d}" for c in range(1, 16, 2)]

sub = pd.read_csv(F_SUB24, dtype=str, encoding="latin-1")
towns = sub[sub.SUMLEV == "061"].copy()
ctx = pd.read_csv(F_CTFIPS, dtype=str, encoding="utf-8-sig")
ctx["COUSUB"] = ctx["FIPS"].str[5:10]
ctx["old"] = ctx["FIPS"].str[0:5]
towns = towns.merge(ctx[["COUSUB", "old"]], on="COUSUB", how="left")
check(len(towns) == 169 and towns.old.notna().all(), "169 CT towns, all mapped to an old county")
towns["region"] = "09" + towns.COUNTY
for y in range(2020, 2025):
    towns[f"p{y}"] = towns[f"POPESTIMATE{y}"].astype(np.int64)


def ct_region_matrix(popcol: pd.Series) -> pd.DataFrame:
    """Rows = planning region FIPS, cols = old county FIPS, values = share of region pop."""
    t = towns.assign(v=popcol.astype(float).to_numpy())
    m = t.pivot_table(index="region", columns="old", values="v", aggfunc="sum", fill_value=0.0)
    m = m.reindex(columns=CT_OLD, fill_value=0.0)
    return m.div(m.sum(axis=1), axis=0)


def ct_allocate(region_vals: pd.Series, M: pd.DataFrame) -> pd.Series:
    frac = (M.loc[region_vals.index].mul(region_vals.astype(float), axis=0)).sum(axis=0)
    return lr_int(frac, int(region_vals.sum()))


# ================================================================== EDUCATION
log("\n==== EDUCATION ====")
e = pd.read_csv(F_EDU, dtype=str, encoding="latin-1")
e["fips"] = e["FIPS Code"].str.zfill(5)
check(e.duplicated(["fips", "Attribute"]).sum() == 0, "ERS: no duplicate fips x attribute")
CATS = {
    "2019-23": ["Less than high school graduate, 2019-23", "High school graduate (or equivalency), 2019-23",
                "Some college or associate degree, 2019-23", "Bachelor's degree or higher, 2019-23"],
    "2008-12": ["Less than high school graduate, 2008-12", "High school graduate (or equivalency), 2008-12",
                "Some college or associate degree, 2008-12", "Bachelor's degree or higher, 2008-12"],
    "2000": ["Less than high school graduate, 2000", "High school graduate (or equivalency), 2000",
             "Some college or associate degree, 2000", "Bachelor's degree or higher, 2000"],
}
SRC_BASE = "USDA ERS Education2023.csv (ACS 2019-23 5yr / ACS 2008-12 5yr / Census 2000)"
edu_rows = []
wide = {}
for per, cats in CATS.items():
    w = e[e.Attribute.isin(cats)].pivot(index="fips", columns="Attribute", values="Value")[cats]
    check(w.notna().all().all(), f"ERS {per}: no blank counts")
    w = w.astype(np.int64)
    w.columns = ["lt_hs", "hs", "some", "ba"]
    wide[per] = w
    us = w.loc["00000"]
    states = w[(w.index.str[2:] == "000") & (w.index != "00000") & (w.index.str[:2] != "72")]
    check((states.sum() == us).all(), f"ERS {per}: 51 state rows sum to US row")
    cty = w[(w.index.str[2:] != "000") & (w.index.str[:2] != "72")].copy()
    st_of = cty.index.str[:2] + "000"
    check((cty.groupby(st_of).sum().reindex(states.index) == states).all().all(),
          f"ERS {per}: county rows sum to state rows")
    wide[per + "_cty"] = cty

# 2008-12 shares used for Alaska 2000 splits
c12 = wide["2008-12_cty"]
PER_SRC = {"2019-23": "ACS 2019-23 5-year", "2008-12": "ACS 2008-12 5-year", "2000": "Census 2000"}
for per in CATS:
    SRC_BASE = f"USDA ERS Education2023.csv ({PER_SRC[per]})"
    cty = wide[per + "_cty"].copy()
    src = pd.Series(SRC_BASE, index=cty.index)

    def merge_into(dst, parts, note):
        global cty, src
        present = [p for p in parts if p in cty.index]
        if not present:
            return
        tot = cty.loc[present].sum()
        cty = cty.drop(present)
        if dst in cty.index:
            tot = tot + cty.loc[dst]
        cty.loc[dst] = tot
        src.loc[dst] = SRC_BASE + "; " + note
        src.drop([p for p in present if p != dst and p in src.index], inplace=True)

    merge_into("51019", ["51515"], "Bedford city 51515 summed into 51019")
    merge_into("51005", ["51560"], "Clifton Forge city 51560 summed into 51005")
    merge_into("46102", ["46113"], "46113 Shannon recoded 46102")
    merge_into("02158", ["02270"], "02270 Wade Hampton recoded 02158")
    merge_into("02261", ["02063", "02066"], "02063 Chugach + 02066 Copper River summed into 02261 Valdez-Cordova")

    if per == "2000":
        # Alaska 2000-era areas -> 2008+ areas, split by 2008-12 per-category counts
        note = "Alaska 2000-geography area split by ERS 2008-12 per-category shares (approx)"
        for old, news in [("02232", ["02105", "02230"]), ("02280", ["02195", "02275"])]:
            v = cty.loc[old]
            for i, col in enumerate(cty.columns):
                sh = c12.loc[news, col].astype(float)
                alloc = lr_int(sh / sh.sum() * v[col], int(v[col]))
                for n in news:
                    cty.loc[n, col] = alloc[n]
            cty = cty.drop(old)
            src = src.drop(old)
            for n in news:
                src.loc[n] = SRC_BASE + f"; from {old} 2000: " + note
        cty.loc["02198"] = cty.loc["02201"]
        cty = cty.drop("02201")
        src = src.drop("02201")
        src.loc["02198"] = SRC_BASE + "; 02201 Prince of Wales-Outer Ketchikan 2000 used as 02198 Prince of Wales-Hyder (approx; ignores small 2008 Ketchikan annexation)"
        cty = cty.astype(np.int64)

    if per == "2019-23":
        regs = [f"09{c}" for c in range(110, 200, 10)]
        check(all(r in cty.index for r in regs) and not any(c in cty.index for c in CT_OLD),
              "ERS 2019-23: CT has 9 planning regions and no old counties")
        # town population averaged over 2020-2023 (ACS 2019-23 period, V2024 town estimates)
        M = ct_region_matrix(towns[[f"p{y}" for y in range(2020, 2024)]].mean(axis=1))
        for col in cty.columns:
            a = ct_allocate(cty.loc[regs, col], M)
            for c in CT_OLD:
                cty.loc[c, col] = a[c]
        cty = cty.drop(regs).astype(np.int64)
        for c in CT_OLD:
            src.loc[c] = (SRC_BASE + "; CT planning-region counts allocated to old county by town population share "
                          "(Census V2024 sub-county est., mean 2020-23) within each region (approx)")
        src = src.drop(regs)
        # comparison with fallback: state 2019-23 x 2008-12 old-county shares
        fb = c12.loc[CT_OLD]
        st = cty.loc[CT_OLD].sum()
        for c in CT_OLD:
            r_new = cty.loc[c, "ba"] / cty.loc[c].sum()
            r_old = c12.loc[c, "ba"] / c12.loc[c].sum()
            log(f"  CT {c}: 2019-23 alloc ba={cty.loc[c,'ba']:,} adults25={cty.loc[c].sum():,} rate={r_new:.3f} | "
                f"2008-12 rate={r_old:.3f} | fallback(state x 08-12 share) ba={st['ba']*fb.loc[c,'ba']/fb['ba'].sum():,.0f}")

    have = set(cty.index)
    missing = sorted(set(TARGET) - have)
    extra = sorted(have - set(TARGET))
    log(f"ERS {per}: {len(cty)} counties; missing vs target {missing}; extra {extra}")
    check(not extra, f"ERS {per}: no FIPS outside target set")
    cty = cty.loc[sorted(have)]
    us = wide[per].loc["00000"]
    check((cty.sum() == us).all(), f"ERS {per}: final counties sum exactly to US totals")
    for f in cty.index:
        edu_rows.append((f, per, int(cty.loc[f, "ba"]), int(cty.loc[f].sum()), src[f]))

edu = pd.DataFrame(edu_rows, columns=["fips", "period", "bachelors_plus", "adults25", "source"])
edu["po"] = edu.period.map({"2019-23": 0, "2008-12": 1, "2000": 2})
edu = edu.sort_values(["po", "fips"]).drop(columns="po").reset_index(drop=True)
check(not edu.duplicated(["fips", "period"]).any(), "education: unique fips x period")
check((edu.bachelors_plus <= edu.adults25).all() and (edu.adults25 > 0).all(), "education: 0 < ba <= adults25")
for per, g in edu.groupby("period", sort=False):
    log(f"education {per}: rows={len(g)} states={g.fips.str[:2].nunique()} "
        f"bachelors_plus={g.bachelors_plus.sum():,} adults25={g.adults25.sum():,} "
        f"share={g.bachelors_plus.sum()/g.adults25.sum():.4f}")

# cross-check: independent copy of 2019-23 percent column (zreller/Personal_Work)
try:
    z = pd.read_csv(F_EDU_PCT, dtype=str)
    z["fips"] = z["FIPS Code"].str.zfill(5)
    z = z.set_index("fips")["Bachelors Percent"].astype(float)
    w23 = wide["2019-23_cty"]
    pct = (w23["ba"] / w23.sum(axis=1) * 100)
    common = pct.index.intersection(z.index)
    diff = (pct[common] - z[common]).abs()
    log(f"cross-check zreller 'Bachelors Percent' vs ERS 2019-23 counts: n={len(common)} max|diff|={diff.max():.4f} pp")
except Exception as ex:  # informational only
    log(f"cross-check zreller skipped: {ex}")

edu.to_csv(f"{OUT}/education.csv", index=False, lineterminator="\n")

# ================================================================== GDP
log("\n==== GDP ====")
g = pd.read_csv(F_GDP, dtype=str, skipinitialspace=True, encoding="latin-1")
g = g[g.LineCode.notna()]
g["fips"] = g.GeoFIPS.str.strip()
check(g.TableName.eq("CAGDP1").all(), "GDP: all rows are CAGDP1")
g3 = g[g.LineCode == "3"].copy()
check(g3.Description.str.strip().eq("Current-dollar GDP (thousands of current dollars)").all()
      and g3.Unit.eq("Thousands of dollars").all(), "GDP: line 3 = current-dollar GDP, thousands of dollars")
check(not g3.fips.duplicated().any(), "GDP: one line-3 row per GeoFIPS")
YEARS = list(range(2001, 2025))
vals = g3.set_index("fips")[[str(y) for y in YEARS]]
vals.columns = YEARS
flags = vals.isin(["(D)", "(NA)"])
num = vals.where(~flags).apply(pd.to_numeric).astype("Int64")

US = num.loc["00000"]
states = num[(num.index.str[2:] == "000") & (num.index != "00000") & (num.index.str[:2] < "60")]
check(len(states) == 51, "GDP: 51 state rows")
log("GDP: state sum - US total by year: " + ", ".join(f"{y}:{int(states[y].sum()-US[y])}" for y in YEARS))

cty = num[(num.index.str[2:] != "000") & (num.index.str[:2] < "60")]
cflags = flags.loc[cty.index]
SRC = "BEA CAGDP1 line 3 (Feb 5 2026 release)"
VA = {
    "51901": ["51003", "51540"], "51903": ["51005", "51580"], "51907": ["51015", "51790", "51820"],
    "51911": ["51031", "51680"], "51913": ["51035", "51640"], "51918": ["51053", "51570", "51730"],
    "51919": ["51059", "51600", "51610"], "51921": ["51069", "51840"], "51923": ["51081", "51595"],
    "51929": ["51089", "51690"], "51931": ["51095", "51830"], "51933": ["51121", "51750"],
    "51939": ["51143", "51590"], "51941": ["51149", "51670"], "51942": ["51153", "51683", "51685"],
    "51944": ["51161", "51775"], "51945": ["51163", "51530", "51678"], "51947": ["51165", "51660"],
    "51949": ["51175", "51620"], "51951": ["51177", "51630"], "51953": ["51191", "51520"],
    "51955": ["51195", "51720"], "51958": ["51199", "51735"], "15901": ["15009", "15005"],
}
members = [m for v in VA.values() for m in v]
check(len(members) == len(set(members)), "combo members unique")
check(set(members) <= set(TARGET), "combo members all in target set")
REGS = [f"09{c}" for c in range(110, 200, 10)]
# pre-2008 Alaska areas and the current areas they became
AK_OLD = {"02280": ["02195", "02275"], "02232": ["02105", "02230"], "02201": ["02198"]}
AK_NAMES = {"02280": "Wrangell-Petersburg", "02232": "Skagway-Hoonah-Angoon", "02201": "Prince of Wales-Outer Ketchikan"}
# town-pop-share puts Hartford-area (Capitol region) GDP onto Tolland towns (x2.4 vs 2023); see README
CT_GDP_METHOD = "prev_year_gdp_share"

gdp_rows = []
supp = []
for y in YEARS:
    col = cty[y]
    fl = cflags[y]
    out, src = {}, {}
    for f in cty.index:
        if f in VA or f in REGS or f in CT_OLD or f in ("02063", "02066", "02261") or f in AK_OLD:
            continue
        if pd.isna(col[f]) and any(f in v for v in AK_OLD.values()):
            continue
        out[f] = col[f]
        src[f] = SRC
        if fl[f]:
            supp.append((f, y, vals.loc[f, y]))
    # Alaska Valdez-Cordova
    if pd.notna(col["02261"]):
        out["02261"], src["02261"] = col["02261"], SRC
    else:
        check(pd.notna(col["02063"]) and pd.notna(col["02066"]), f"{y}: 02063 and 02066 present when 02261 absent", quiet=True)
        out["02261"] = col["02063"] + col["02066"]
        src["02261"] = SRC + "; 02063 Chugach + 02066 Copper River summed into 02261"
    # Alaska areas BEA publishes under older geography: split onto today's areas by the GDP shares of
    # the first later year in which all successor areas have values
    for old, succ in AK_OLD.items():
        if pd.isna(col[old]):
            check(all(pd.notna(col[m]) for m in succ), f"{y}: AK {succ} present when {old} is (NA)", quiet=True)
            continue
        ry = next(yy for yy in YEARS if yy > y and all(pd.notna(cty[yy][m]) for m in succ))
        if len(succ) == 1:
            out[succ[0]] = col[old]
            src[succ[0]] = SRC + f"; {y} {old} {AK_NAMES[old]} used as {succ[0]} (approx)"
        else:
            sh = cty[ry][succ].astype(float)
            a = lr_int(sh / sh.sum() * int(col[old]), int(col[old]))
            for m in succ:
                out[m] = a[m]
                src[m] = SRC + f"; {y} {old} {AK_NAMES[old]} split by {ry} GDP shares of {'/'.join(succ)} (approx)"
    # Combo areas
    for combo, mem in VA.items():
        v = col[combo]
        check(pd.notna(v), f"{y}: combo {combo} has a value", quiet=True)
        p = popw.loc[mem, y].astype(float)
        a = lr_int(p / p.sum() * int(v), int(v))
        for m in mem:
            out[m] = a[m]
            src[m] = SRC + f"; BEA combo area {combo} split by {y} population share (approx)"
    # Connecticut
    if col[CT_OLD].notna().all():
        check(col[REGS].isna().all(), f"{y}: CT old counties only", quiet=True)
        for c in CT_OLD:
            out[c], src[c] = col[c], SRC
    else:
        check(col[REGS].notna().all() and col[CT_OLD].isna().all(), f"{y}: CT planning regions only")
        state_tot = int(col[REGS].sum())
        M = ct_region_matrix(towns[f"p{min(y, 2024)}"])
        a_pop = ct_allocate(col[REGS].astype(np.int64), M)
        py = cty[y - 1][CT_OLD].astype(float)
        check(py.notna().all(), f"{y}: previous year has CT old-county GDP")
        a_prev = lr_int(py / py.sum() * state_tot, state_tot)
        for c in CT_OLD:
            log(f"  CT {y} {c}: prev-yr GDP share alloc={a_prev[c]:,}  town-pop-share alloc={a_pop[c]:,}  "
                f"ratio pop/prev={a_pop[c]/a_prev[c]:.3f}")
        if CT_GDP_METHOD == "prev_year_gdp_share":
            a = a_prev
            note = (f"; CT {y} published only for planning regions: CT state total (sum of 9 regions) allocated to "
                    f"old counties by BEA {y-1} old-county GDP shares (approx)")
        else:
            a = a_pop
            note = (f"; CT planning-region GDP allocated to old county by town population share {y} "
                    f"(Census V2024 sub-county est.) (approx)")
        for c in CT_OLD:
            out[c] = a[c]
            src[c] = SRC + note
    s = pd.Series(out)
    check(sorted(s.index) == TARGET, f"GDP {y}: output FIPS == target set (3142)")
    # state consistency (BEA county values are independently rounded, so allow small differences)
    st_sum = s.groupby(s.index.str[:2] + "000").sum()
    d = (st_sum.reindex(states.index).astype(float) - states[y].astype(float))
    rel = (d.abs() / states[y].astype(float)).max()
    log(f"GDP {y}: rows={len(s)} blank={int(s.isna().sum())} county_sum={int(s.sum()):,} US={int(US[y]):,} "
        f"(US - county sum = {int(US[y]) - int(s.sum()):,}); county-vs-state max |diff|={int(d.abs().max()):,}k "
        f"(max rel {rel:.2e})")
    check(rel < 1e-4, f"GDP {y}: every state's county sum within 0.01% of BEA state row", quiet=True)
    for f in sorted(s.index):
        v = s[f]
        gdp_rows.append((f, y, "" if pd.isna(v) else str(int(v)),
                         src[f] + ("; suppressed " + vals.loc[f, y] if pd.isna(v) and f in vals.index else "")))

gdp = pd.DataFrame(gdp_rows, columns=["fips", "year", "gdp_thousands_current_dollars", "source"])
log(f"GDP suppressed cells in output: {len(supp)} " + str(sorted(set((f, v) for f, _, v in supp))))
gdp.to_csv(f"{OUT}/gdp.csv", index=False, lineterminator="\n")
for p in [f"{OUT}/education.csv", f"{OUT}/gdp.csv"]:
    log(f"output sha256 {sha(p)}  {p}")
open("build/metrics_build_log.txt", "w").write("\n".join(LOG) + "\n")
