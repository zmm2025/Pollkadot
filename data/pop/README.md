# county_pop.csv: US county resident population, 2000 to 2026

Columns: `fips` (5-digit string), `year` (int), `pop` (int), `source` (the input file the value came from, plus a note on any adjustment).
Every year has 3,143 rows (50 states + DC, Puerto Rico excluded). That makes 84,861 rows in all.
All values are Census Bureau Population Estimates for **July 1** of the year (`POPESTIMATEyyyy`). None of them are April 1 census counts.

Build script: `pipeline/data_sources/population/build_county_pop.py`, run with `python -P`. Log of integrity checks: `pipeline/data_sources/population/build_log.txt`.
The build is deterministic: repeated runs give the same output, sha256 `ea67d13252c0c9e0dd97dc26c33ea0e83581623f2d55ef3761c9344276f2ded0`.

## Input files (downloaded from the Census Bureau, www2.census.gov)

| Years | Census file | URL | sha256 |
|---|---|---|---|
| 2000–2009 | `co-est00int-tot.csv`: intercensal 2000–2010 county totals | https://www2.census.gov/programs-surveys/popest/datasets/2000-2010/intercensal/county/co-est00int-tot.csv | `273e5620…6ae8f6` |
| 2010–2019 | `co-est2019-alldata.csv`: Vintage 2019 county totals | https://www2.census.gov/programs-surveys/popest/datasets/2010-2019/counties/totals/co-est2019-alldata.csv | `654032fb…fde77d8` |
| 2020–2025 | `co-est2025-alldata.csv`: Vintage 2025 county totals | https://www2.census.gov/programs-surveys/popest/datasets/2020-2025/counties/totals/co-est2025-alldata.csv | `4f5a499d…e264f35d5` |
| CT 2020–2025 | `sub-est2024_9.csv`: Vintage 2024 sub-county (CT towns) | https://www2.census.gov/programs-surveys/popest/datasets/2020-2024/cities/totals/sub-est2024_9.csv | `e5bd2cb1…7ca83df` |
| CT crosswalk | CT town → old county FIPS (10-digit 09+county+cousub), CT Data Collaborative | https://raw.githubusercontent.com/CT-Data-Collaborative/ct-town-county-fips-list/6a0f6b3e118aa180b7ea713b1e3befb88e0fc276/ct-town-county-fips-list.csv | `8489a213…0d35b3b` |

Save them in `build/downloads/census/` before running the script. These official files are byte-identical to
the GitHub copies an earlier version of this build used (the intercensal file differs only in line endings),
so 2008–2026 values did not change when the inputs moved to census.gov. In every file, county rows (SUMLEV 050)
sum exactly to the state rows for every year used. National totals: 2000 282,162,411; 2008 304,093,966;
2019 328,239,523; 2025 341,784,857.

## Which years come from which file
- 2000–2009: co-est00int-tot.csv (intercensal, consistent with Census 2010, on 2010 county geography).
- 2010–2019: co-est2019-alldata.csv (Vintage 2019 postcensal, based on Census 2010).
- 2020–2025: co-est2025-alldata.csv (Vintage 2025, based on Census 2020). There is a vintage break between 2019 and 2020: V2019 and V2025 do not reconcile. No 2010–2020 intercensal county file was found on GitHub.
- 2026: no estimate exists. **Every county's 2026 row is a copy of its 2025 value**, and its `source` starts with "2025 value carried forward (no 2026 estimate)".

## FIPS normalization (target = 2019-era county set plus 02063/02066, CT as 8 old counties)
- 46113 Shannon → 46102 Oglala Lakota (2000–2009 only; later files already use 46102).
- 02270 Wade Hampton → 02158 Kusilvak (2000–2009 only).
- 51515 Bedford city added into 51019 Bedford County (2000–2009 only; co-est2019 already folds it in for 2010+).
- 02201, 02232, 02280: checked absent in all files. The intercensal file already uses 2010 geography: 02105, 02195, 02198, 02230, 02275.
- Puerto Rico (72), state rows and national rows are excluded.

## Approximations (every one is flagged in `source`)
1. **Valdez-Cordova 02261, 2000–2019**: split into 02063 Chugach and 02066 Copper River using their V2025 July-2020 shares. 02063 gets round(p × 0.730254) and 02066 gets the remainder. 40 rows are affected. *Note:* if the base geometry (cb_2019) still has the single polygon 02261, use 02063 + 02066 = 02261. This file has no 02261 row, so it holds 3,143 counties per year, one more than 3,142.
2. **Alaska 2013 Petersburg Borough change, 2000–2009**: the intercensal file uses the 2010 boundaries of Petersburg CA (02195). Those were later redrawn: most of the remainder moved to Prince of Wales-Hyder (02198), and a sliver of Hoonah-Angoon (02105) moved into 02195. To make 2000–2009 match the 2010+ boundaries, the script moves a share of each county's value. The shares come from the 2010 census-to-base deltas in co-est2019: 609/3815 of 02195 goes to 02198, and 47/2150 of 02105 goes to 02195. Totals are preserved. 30 rows are affected. Without this, 02195 would show an artificial 15% drop between 2009 and 2010.
3. **Connecticut 2020–2025**: V2025 publishes only the 9 planning regions (09110–09190). Old-county values (09001–09015) are built from the 169 towns in sub-est2024_9.csv, which are mapped to old counties with the CT-Data crosswalk:
   - **2020–2024**: each town's V2024 share of its planning region is applied to the V2025 planning-region total ("raked"), and the results are summed by old county. Integers are assigned by largest remainder, so the 8 counties sum exactly to the V2025 CT total. The raked values differ from the plain V2024 town sums by at most about 2,000 per county (see build_log.txt). This is a deterministic, standard method. Treat it as close, not as an official Census number.
   - **2025** (and therefore 2026): no Vintage 2025 town file was found on GitHub, so **the 2024 town shares are used** with the 2025 V2025 region totals. Source is tagged "(approx)". This is region-level growth applied to towns, which is better than scaling by state growth.
   - 2000–2019 CT values are official old-county estimates from the files above.
   - Note: Tolland 09013 falls from 150,721 (V2019, 2019) to 142,901 (2020). This comes straight from the Census town data (the July 2020 college-population effect at UConn/Mansfield). It is not an artifact of the build.
4. **2026** = 2025 for every county (see above).

Small ESTIMATESBASE-vs-census differences (Count Question Resolution corrections, minor boundary fixes such as Granville NC and Calhoun IA) are left as the Census files publish them.
