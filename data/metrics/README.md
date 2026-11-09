# County metrics: educational attainment and GDP

Build script: `pipeline/data_sources/metrics/build_metrics.py`, run with `python -P`. Check log: `pipeline/data_sources/metrics/build_log.txt`.
The build is deterministic: two runs in a row gave the same sha256 for both outputs.
- `education.csv`: `13c8d3c59ab2a839424bfee83527e7c7e684ad33e327608872b2bb4254a6da08`
- `gdp.csv`: `f4c842debe97d23987b97f861a734c49be1a10173b76dd66eaf274472fb8be2b`

The county set is the one in `data/pop/county_pop.csv`, except that Alaska uses **02261 Valdez-Cordova** (02063 Chugach + 02066 Copper River combined). Connecticut is the 8 old counties (09001–09015) and Virginia's independent cities are separate. That makes **3,142 FIPS**: 50 states + DC, no Puerto Rico, no state or national rows.

## Input files (downloaded from the publishing agencies)

| File | URL | sha256 |
|---|---|---|
| USDA ERS `Education2023.csv` (long format: FIPS Code, State, Area name, Attribute, Value) | https://ers.usda.gov/sites/default/files/_laserfiche/DataFiles/48747/Education2023.csv | `4348b20e…8dae2b7b` |
| BEA `CAGDP1.zip` → `CAGDP1__ALL_AREAS_2001_2024.csv` ("Last updated: February 5, 2026-- new statistics for 2024; revised statistics for 2020-2023") | https://apps.bea.gov/regional/zip/CAGDP1.zip | zip `95b49283…3b166fe1`, csv `444b10c6…28750f14` |
| CT town population and CT town→old-county crosswalk | the same files as the population build (see `data/pop/README.md`) | |
| Population (for splitting the BEA combo areas) | `data/pop/county_pop.csv` | |

Save them as `build/downloads/ers/Education2023.csv`, `build/downloads/bea/CAGDP1.zip` and
`build/downloads/bea/x/CAGDP1__ALL_AREAS_2001_2024.csv` (extracted). The BEA zip is byte-identical to the GitHub
copy an earlier version of this build used. The ERS file is not byte-identical to that earlier copy, but
`education.csv` built from it is (same sha256 as before).

Outputs: `education.csv` sha256 `13c8d3c59ab2a839424bfee83527e7c7e684ad33e327608872b2bb4254a6da08`,
`gdp.csv` sha256 `9758fedef55ca9bc43aed8bd5f5f39a69a7c74f2a21c9684b5fa55aeebf40014`.


## education.csv

Columns: `fips, period, bachelors_plus, adults25, source`. `adults25` is the sum of the four ERS count columns: less than high school, high school graduate, some college or associate degree, and bachelor's or higher.

| period | underlying data | rows | bachelors_plus | adults25 | share |
|---|---|---|---|---|---|
| 2019-23 | ACS 5-year | 3,142 | 79,954,302 | 228,434,661 | 35.0% |
| 2008-12 | ACS 5-year | 3,142 | 58,205,022 | 204,336,017 | 28.5% |
| 2000 | Decennial census | 3,141 (no 08014 Broomfield, which did not exist in 2000) | 44,462,605 | 182,211,639 | 24.4% |

Checks:
- For each period, the ERS county rows sum exactly to the ERS state rows, and the state rows sum to the US row. The output counties also sum exactly to the ERS US totals.
- The bachelor's percentage computed from the counts matches the independent zreller copy to within 0.0000 percentage points (3,097 counties overlap).
- The 1970/1980/1990 periods in the file were not used.

FIPS handling, all exact sums (the `source` column notes each one):
- 51515 Bedford city → 51019 (2008-12, 2000).
- 51560 Clifton Forge → 51005 Alleghany (2000).
- 02063 + 02066 → 02261 (2019-23).
- ERS already uses 46102 and 02158 for every period.

Approximations (each is flagged "(approx)" in `source`):
1. **Connecticut 2019-23.** ERS has only the 9 planning regions (09110–09190), and no town-level ACS education source was found on GitHub. Each region's counts, category by category, were allocated to its towns by town population share. The shares use the Census V2024 sub-county estimates averaged over 2020–2023. The towns were then summed to their old counties. Integers are assigned by largest remainder, so the CT totals are exact. The method assumes attainment is uniform within each region. Sanity check: every old county's bachelor's share is 4–7 percentage points above its own 2008-12 share, in line with the state trend. The other fallback (CT 2019-23 total × 2008-12 old-county shares) gives values within about 7% of these for 7 counties; Windham is about 12% lower. See the log.
2. **Alaska 2000** (5 rows). The 2000 geography was split onto the current areas:
   - 02232 Skagway-Hoonah-Angoon → 02105 + 02230, using the ERS 2008-12 per-category shares.
   - 02280 Wrangell-Petersburg → 02195 + 02275, the same way.
   - 02201 Prince of Wales-Outer Ketchikan is used as 02198 Prince of Wales-Hyder. This ignores the small parts later moved to Ketchikan and Petersburg.
   - The 2013 Petersburg boundary change is not adjusted in the 2008-12 period.
3. 08014 Broomfield has no 2000 row.

## gdp.csv

Columns: `fips, year, gdp_thousands_current_dollars, source`. The values are BEA CAGDP1 LineCode 3, "Current-dollar GDP (thousands of current dollars)". This equals CAGDP2 line 1 "All industry total". It is the February 5, 2026 release.

- **Years:** 2001–2024 (24 years), 3,142 rows per year, 75,408 rows in all. County GDP starts in 2001; elections in 2000 use 2001.
- **Suppression:** there are no "(D)" values in this line for any output county-year. The one blank is 08014 Broomfield in 2001 ("(NA)": the county was created in November 2001; its area's GDP is in its parent counties). The only "(NA)" cells in the source are structural ones that are handled below: retired Alaska areas, CT old counties in 2024, and CT planning regions before 2024.
- **Cross-check:** the 2008–2024 values are identical to the previous build of this file.
- **Consistency:** every state's output county sum is within 9k (rel. <2e-7) of the BEA state row, which is rounding.
- **Not in any county:** the US total exceeds the sum of the states by $91–160 B a year (BEA's overseas federal military and civilian activity, which no county gets).

| year | county sum ($ thousands) | BEA US total |
|---|---|---|
| 2008 | 14,678,473,997 | 14,769,862,000 |
| 2019 | 21,414,018,022 | 21,539,982,000 |
| 2022 | 25,907,032,003 | 26,054,614,000 |
| 2023 | 27,658,314,991 | 27,811,517,000 |
| 2024 | 29,137,790,991 | 29,298,013,000 |

Note: in this vintage, 2022 US GDP is $26.05 T, not the ≈$25.7 T first published. That gap is the BEA comprehensive and annual revisions.

Exact transformations:
- 02261 = 02063 + 02066 for 2020–2024. BEA publishes 02261 itself through 2019.

Approximations (each is flagged "(approx)" in `source`):
1. **Virginia combo areas** (23 BEA areas, 51901–51958, covering 53 county/city FIPS) and **Hawaii 15901 Maui + Kalawao.** Each combo's GDP is split across its members by that year's population from `county_pop.csv`. Integers are assigned by largest remainder, so the combo totals are exact. This assumes GDP per person is the same within each combo, which is not true for city/county pairs such as Charlottesville and Albemarle. Every year has 53 such rows.
2. **Connecticut 2024.** BEA publishes only the 9 planning regions for 2024. The CT total (the sum of the regions) was allocated to the 8 old counties by their **2023 BEA GDP shares**. **This is not the method in the brief**, which was population share within each planning region. I computed that method as well, and it is still in the script (`CT_GDP_METHOD = "town_pop_share"`). Spreading each region's GDP over its towns by population moves Hartford-area (Capitol region) output onto the Tolland County towns. That would give Tolland $17.2 B in 2024, against $6.9 B published for 2023. Compared with the 2023-share allocation, it is 2.39× for Tolland, 1.20× for Litchfield and 1.14× for Middlesex, and 0.92× for Hartford and Fairfield. The 2023-share method keeps the 2023→2024 change uniform at 4.38% for every old county instead. Both allocations are in `build_log.txt`.
3. **Alaska 2001–2008.** BEA still uses older borough geography in these years. Each retired area is moved onto today's
   areas by the GDP shares of the first later year in which all of them are published:
   - 02280 Wrangell-Petersburg (through 2008) → 02195 + 02275, split by their 2009 GDP shares.
   - 02232 Skagway-Hoonah-Angoon (through 2007) → 02105 + 02230, split by their 2008 GDP shares.
   - 02201 Prince of Wales-Outer Ketchikan (through 2008) is used as 02198.
