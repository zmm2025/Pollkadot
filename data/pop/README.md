# county_pop.csv: US county resident population, 2008 to 2026

Columns: `fips` (5-digit string), `year` (int), `pop` (int), `source` (the input file the value came from, plus a note on any adjustment).
Every year has 3,143 rows (50 states + DC, Puerto Rico excluded). That makes 59,717 rows in all.
All values are Census Bureau Population Estimates for **July 1** of the year (`POPESTIMATEyyyy`). None of them are April 1 census counts.

Build script: `pipeline/data_sources/population/build_county_pop.py`, run with `python3 -I`. Log of integrity checks: `pipeline/data_sources/population/build_log.txt`.
The build is deterministic: repeated runs give the same output, sha256 `4851798db208e7f988b841b9f95693008d5f6a9f9901d68fb4991d556db57427`.

## Input files (cloned from public GitHub; census.gov is unreachable from this sandbox)

| Years | Census file | Repo (commit) and path | sha256 |
|---|---|---|---|
| 2008–2009 | `co-est00int-tot.csv`: intercensal 2000–2010 county totals | https://github.com/waddell/CP255 (`a03e218f0d4bf8586243692a26ca5c4d655db090`), `04-pandas/data/co-est00int-tot.csv` | `098cb7fe…af5e` |
| 2010–2019 | `co-est2019-alldata.csv`: Vintage 2019 county totals | https://github.com/programminghistorian/jekyll (`0cb4d0dddd5ce407dbc43ef4e3c0356c564343bb`), `assets/choropleth-maps-python-folium/co-est2019-alldata.csv` | `654032fb…77d8` |
| 2020–2025 | `co-est2025-alldata.csv`: Vintage 2025 county totals | https://github.com/anirbanmukherjee2709/pybenford (`061071ee94ee17aa98bbcc0a457550b813eb6c86`), `examples/data/co-est2025-alldata.csv` | `4f5a499d…35d5` |
| CT 2020–2025 | `sub-est2024_9.csv`: Vintage 2024 sub-county (CT towns) | https://github.com/notpac93/usa-representative-map-2 (`281aeafa0d4942392c7d32033539d5b5f23a6021`), `data/raw/census-csv/sub-est2024_9.csv` (also `sub-est2024.csv`, the national file) | `e5bd2cb1…83df` |
| CT crosswalk | CT town → old county FIPS (10-digit 09+county+cousub) | https://github.com/CT-Data-Collaborative/ct-town-county-fips-list (`6a0f6b3e118aa180b7ea713b1e3befb88e0fc276`), `ct-town-county-fips-list.csv` | `8489a213…5b3b` |

### Cross-validation (copies committed independently in other repos)
- **co-est00int-tot.csv**: after stripping CR, the content is byte-identical in 9 other repos. Examples: waddell/urban-informatics-and-visualization `0c542cc2`, tliddell4/stagg_paper_figures `8dd597dd`, mxndrwgrdnr/UCB_CYPLAN255_2024 `24c74a20`, reesejcarlton/CA-Fire-Predictions `747b656d`, MIDS-at-Duke/pds-2025-opioids-study_on_opioids `072fe513`, jasonschen3/cs4641-datacenter `ac0c6a5e`, nghitrampham/air_pollution_death_rate_related `3fd72b96`, MIDS-at-Duke/Data-Science-Project `c8c80b14`. The CRLF variant also matches the Git LFS oid `273e5620…` in wan-robert/ids720-opioids-analysis. Census 2010 counts agree with co-est2019 for all 3,140 shared counties. The 2008 national total is 304,093,966 and the 2009 total is 306,771,529. (shanag/final-project-rails-cs64 has a hand-edited copy with a duplicate Baltimore row. It was rejected.)
- **co-est2019-alldata.csv**: the same sha256 appears in databricks/devrel `edf902c4`, swe4s/lectures `11f77903` (2 copies), diegoolano/us_per_capita_covid `be8ea92d` and fm75/DS `3e6f206a`. It is also the LFS oid in wan-robert/ids720-opioids-analysis and mbruns13/redfin_housing_data. The 2019 national total is 328,239,523.
- **co-est2025-alldata.csv**: county and state POPESTIMATE2020–2025 are identical in palism1/stroke-burden-index `d9d206b3` (`data/scai_data/hospitals/co-est2025-alldata.csv`). County values are also identical in The-Art-of-Data-Journalism/the-art-of-data-journalism.github.io `24ac0f31` (`tutorial-data/census-estimates/*.csv`, split by state) and in the 432-county fixture in lrcarey222/Electro-Industrial-Geos `dca6ed39`. That fixture was recorded from census.gov on 2026-09-30. Check values: Los Angeles 06037 was 9,996,510 in 2020. Loving TX 48301 was 52 in 2025. The 2025 national total is 341,784,857.
- **sub-est2024_9.csv**: identical to the CT rows of the national `sub-est2024.csv`. The 169 towns sum exactly to the 9 planning regions for every year. All 169 COUSUB codes and names match the CT town crosswalk.
- In every file, county rows (SUMLEV 050) sum exactly to the state rows for every year used.

## Which years come from which file
- 2008, 2009: co-est00int-tot.csv (intercensal, consistent with Census 2010).
- 2010–2019: co-est2019-alldata.csv (Vintage 2019 postcensal, based on Census 2010).
- 2020–2025: co-est2025-alldata.csv (Vintage 2025, based on Census 2020). There is a vintage break between 2019 and 2020: V2019 and V2025 do not reconcile. No 2010–2020 intercensal county file was found on GitHub.
- 2026: no estimate exists. **Every county's 2026 row is a copy of its 2025 value**, and its `source` starts with "2025 value carried forward (no 2026 estimate)".

## FIPS normalization (target = 2019-era county set plus 02063/02066, CT as 8 old counties)
- 46113 Shannon → 46102 Oglala Lakota (2008–2009 only; later files already use 46102).
- 02270 Wade Hampton → 02158 Kusilvak (2008–2009 only).
- 51515 Bedford city added into 51019 Bedford County (2008–2009 only; co-est2019 already folds it in for 2010+).
- 02201, 02232, 02280: checked absent in all files. The intercensal file already uses 2010 geography: 02105, 02195, 02198, 02230, 02275.
- Puerto Rico (72), state rows and national rows are excluded.

## Approximations (every one is flagged in `source`)
1. **Valdez-Cordova 02261, 2008–2019**: split into 02063 Chugach and 02066 Copper River using their V2025 July-2020 shares. 02063 gets round(p × 0.730254) and 02066 gets the remainder. 24 rows are affected. *Note:* if the base geometry (cb_2019) still has the single polygon 02261, use 02063 + 02066 = 02261. This file has no 02261 row, so it holds 3,143 counties per year, one more than 3,142.
2. **Alaska 2013 Petersburg Borough change, 2008–2009**: the intercensal file uses the 2010 boundaries of Petersburg CA (02195). Those were later redrawn: most of the remainder moved to Prince of Wales-Hyder (02198), and a sliver of Hoonah-Angoon (02105) moved into 02195. To make 2008–2009 match the 2010+ boundaries, the script moves a share of each county's value. The shares come from the 2010 census-to-base deltas in co-est2019: 609/3815 of 02195 goes to 02198, and 47/2150 of 02105 goes to 02195. Totals are preserved. 6 rows are affected. Without this, 02195 would show an artificial 15% drop between 2009 and 2010.
3. **Connecticut 2020–2025**: V2025 publishes only the 9 planning regions (09110–09190). Old-county values (09001–09015) are built from the 169 towns in sub-est2024_9.csv, which are mapped to old counties with the CT-Data crosswalk:
   - **2020–2024**: each town's V2024 share of its planning region is applied to the V2025 planning-region total ("raked"), and the results are summed by old county. Integers are assigned by largest remainder, so the 8 counties sum exactly to the V2025 CT total. The raked values differ from the plain V2024 town sums by at most about 2,000 per county (see build_log.txt). This is a deterministic, standard method. Treat it as close, not as an official Census number.
   - **2025** (and therefore 2026): no Vintage 2025 town file was found on GitHub, so **the 2024 town shares are used** with the 2025 V2025 region totals. Source is tagged "(approx)". This is region-level growth applied to towns, which is better than scaling by state growth.
   - 2008–2019 CT values are official old-county estimates from the files above.
   - Note: Tolland 09013 falls from 150,721 (V2019, 2019) to 142,901 (2020). This comes straight from the Census town data (the July 2020 college-population effect at UConn/Mansfield). It is not an artifact of the build.
4. **2026** = 2025 for every county (see above).

Small ESTIMATESBASE-vs-census differences (Count Question Resolution corrections, minor boundary fixes such as Granville NC and Calhoun IA) are left as the Census files publish them.
