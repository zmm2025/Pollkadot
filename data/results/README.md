# County-level US election results from MEDSL precinct returns (2016-2024)

County-level Democratic / Republican / other votes for **President, U.S. Senate, U.S. House and
Governor**, built by summing the MIT Election Data + Science Lab (MEDSL) official precinct-level
returns. Covers the 2018, 2020, 2022 and 2024 general elections, plus 2016 (from MEDSL's older
`precinct-returns` repo).

| file | content |
|---|---|
| `county_results.csv` | `year,office,special,state_po,fips,dem,rep,oth,total`, one row per county x race |
| `races.csv` | statewide candidate summary for PRES / SEN / GOV (one row per state-race) |
| `house_districts.csv` | `year,state_po,district,dem,rep,oth,contested` (regular House races only) |
| `data_quality.csv` | every known gap / problem / manual fix, by year x office x state (machine-readable) |

## 1. Sources (all from GitHub; nothing came from Dataverse)

| year | repo | commit used | files |
|---|---|---|---|
| 2016 | `MEDSL/precinct-returns` | `5965d5e572dfb9affaf8b295e6ddee94773a6cf8` (2021-03-12) | `2016-precinct-president/2016-precinct-president.zip`, `2016-precinct-senate/…senate.zip`, `2016-precinct-house/…house.zip`, `2016-precinct-state/…state.zip` (governor rows only) |
| 2018 | `MEDSL/2018-elections-official` | HEAD `42055b11dcd5477bc125cdec5a18fbcc60fb6bed` (data files last changed in `a0507734`, 2022-11-01; README says "deprecated, see Dataverse" but the files are still in the tree) | `individual_states/2018-xx-precinct-general.zip` (51 files) |
| 2020 | `MEDSL/2020-elections-official` | **`ad22f37e3f1e3355f078ba5a1efce6c221333ef1`** (2022-03-14, the last commit before the data were moved to Dataverse; HEAD has only a README) | `individual_states/2020-xx-precinct-general.zip` (50 files: **no Indiana file**) |
| 2022 | `MEDSL/2022-elections-official` | HEAD `a8126c5790b8d1f438a3e63c3506cdcdc7406d9f` | `individual_states/2022-xx-local-precinct-general.zip` (51 files; these hold all offices) |
| 2024 | `MEDSL/2024-elections-official` | HEAD `df531089c78e6d0098db1a6bfb3849a066a06995` | `individual_states/xx24.zip` (51 files); `2024-president-state.csv` and `2024-senate-state.csv` were used only for validation |

None of the files were Git LFS pointers. Codebooks were read from the repos (`codebook.md` for
2022/2024, `codebook.md` from 2018 commit `fd8fce0^`, `field_details.md` for 2020, the 2016
`codebook-*.md` / `coverage-notes-*.md`). Raw zips are under `build/downloads/medsl_*` and
`build/downloads/medsl_repo_precinct-returns`. The zips were read as streams, so nothing was
unpacked to disk.

Validation references, which were not used to build the outputs: tonmcg county presidential files in
`data/raw/tonmcg/{2016,2020,2024}_US_County_Level_Presidential_Results.csv`; MEDSL
`2018-elections-unoffical/election-context-2018.csv` (`aaf8e49d…`), which has 2016 county
pres/sen/house/gov data; MEDSL 2024 state-level files; and a list of certified statewide results.

## 2. Pipeline (`pipeline/data_sources/medsl/`, run with `python3 -I`)

1. `stage1_extract.py YEAR OUT ZIP…` (2018-2024) and `stage1_2016.py` (2016 schema). These keep only the
   target offices, clean the data at precinct level (section 3.3), and then sum away the
   precinct dimension. Output goes to `build/s1_YEAR.csv`. Shared rules are in
   `aggrules.py`.
2. `stage2_aggregate.py YEAR…` handles office/special/stage, meta rows, FIPS, party classes and House
   districts. It writes `s2_{county,cands,house}_YEAR.csv` and a log `s2_log_YEAR.txt` that lists every
   exclusion and override.
3. `build_outputs.py YEAR…` writes the three CSVs here.
4. `validate.py`, `check_known.py` and the coverage checks are described in section 5.

## 3. Rules applied

### 3.1 Offices, specials, stages
* Office mapping (case-insensitive): `US PRESIDENT`→PRES; `US SENATE`, `US SENATE - 2 YEAR TERM`
  (NE 2024), `US SENATE PARTIAL` (CA 2024)→SEN; `US HOUSE`→HOUSE; `GOVERNOR`,
  `GOVERNOR/LIEUTENANT GOVERNOR` (IA 2018), `GOVERNOR / LT. GOVERNOR` (WI 2018),
  `GOVERNOR AND LIEUTENANT GOVERNOR` (MT 2020, ND 2024), `Governor and Lt. Governor` (ND 2016)→GOV.
  Non-voting delegate races and DC "US Senate/US House" shadow seats are excluded (DC has PRES only).
* `special`: 0 = regular, 1 = special election (from MEDSL `special`, and forced to 1 for the CA-2024 partial
  term and the NE-2024 2-year term), 2 = runoff. Specials in the output: 2018 SEN MN and MS (the Nov-6 jungle
  round), 2020 SEN AZ and GA (jungle), 2022 SEN OK, 2024 SEN CA (partial) and NE. Same-day House
  specials: 2016 KY-1, 2018 MI-13 and NY-25, 2022 IN-2, 2024 WI-8.
  Overrides: the 2020 MD-7 November race was flagged special by MEDSL, so it is treated as regular. The 2024 TX-18 rows
  are the regular race (Turner v Centonze) but were flagged special, so they are treated as regular. The concurrent TX-18
  special (Erica Lee Carter) is not in the data. OR 2016 governor was technically a special election but
  is kept at special=0 because it was the only governor race that year.
* Stage: general only. Primary rows (`PRI`) are dropped. `GEN RECOUNT` rows exist only for state
  legislative offices, so no target race is affected. **Runoffs:** the Georgia Jan-5-2021 runoffs are
  *not* in the MEDSL 2020 data. The Georgia **Dec-6-2022 Senate runoff is present** and is output as
  `office=SEN, special=2`. The Mississippi Nov-27-2018 runoff is not in the data.

### 3.2 Candidates / meta rows / parties
* Rows that are not candidate votes are excluded, matched by name pattern: registered voters, ballots
  cast, public counter, over/under votes, blank/void/spoiled, "total" rows, NY ballot-count rows
  (ABSENTEE/MILITARY, AFFIDAVIT, FEDERAL, SPECIAL VOTES, MANUALLY COUNTED EMERGENCY), rejected
  write-ins, and Nevada's **"None of these candidates"**, which is excluded from `total`. Everything
  excluded is listed in `s2_log_YEAR.txt`. Write-in, scattering and "all others" rows are counted
  in `oth`. Rows with a blank candidate name are almost all aggregated write-ins and are kept as `oth`.
* Party is assigned **per candidate within a contest**, not per row:
  1. Each row gets D/R from `party_simplified` (DEMOCRAT/REPUBLICAN). When `party_simplified` is not D/R, it
     can also get D/R from `party_detailed` (DFL, Democratic-NPL, "Progressive/Democrat", "Republican/Libertarian"…).
     **Minnesota DFL (2020, 2022) and North Dakota Dem-NPL (2020, 2022) have
     `party_simplified=OTHER` in MEDSL. They are recoded to D here.** VT Prog/Dem fusion nominees
     (Zuckerman 2020, Siegel 2022, Charlestin 2024) are also D.
  2. Each candidate gets the label (D, R or an explicit other party) that carries most of their votes
     in that contest. Fusion lines therefore follow the candidate: Hochul's WFP line counts as dem, and
     Zeldin's Conservative line counts as rep. In CT/NY this differs from MEDSL's own line-level party
     totals by up to about 5% (for example, Murphy CT-2024).
  3. Fallbacks for candidates with no label in any row: the same name labelled elsewhere in the
     state-year, or a surname match to a labelled candidate in the same contest (this handles name
     variants). These fallbacks are never applied to generic write-in rows.
  4. Manual overrides (these are listed in the log). 2022 NM Lujan Grisham=D and Ronchetti=R (blank labels).
     2024 NJ Conaway=D and Mohan=R. 2016: ND Hoeven/Cramer=R, Iron Eyes/Glassheim=D; KY Comer=R,
     Gaskins=D; VT Clinton=D, Trump=R; NE Ashford=D. **2024 NE Dan Osborn is reclassified from
     MEDSL's DEMOCRAT to independent (oth).**
  Independents are `oth`: King (ME), Sanders (VT, who declined the Democratic nomination), McMullin
  (UT-2022), Osborn (NE-2024), Walker (AK-2022 GOV). Al Gross (AK-2020) and similar nominees keep
  MEDSL's party label.
* `total = dem + rep + oth`.

### 3.3 Modes and double counting (precinct-level)
* Within each precinct x contest x candidate, rows with mode `TOTAL` (and NY-2022's `UNSPECIFIED`,
  which MEDSL uses for unsplit totals) are compared with the split-mode rows. If total ≥ the sum of the modes, the
  total row is kept and the mode rows are dropped (this also covers partial mode breakdowns). If total < the sum of the modes,
  the modes are kept. Actual de-duplications: 2022 AZ, DE, GA (15.3M duplicate votes across offices), MI, NY, SC.
  2024 CT, DE, NJ, NY, OK, RI. 2020 UT, where the mode rows were all 0.
* Sub-total rows posing as precincts are removed:
  * Precincts named "…TOTAL…" whose votes equal the sum of the county's other precincts:
    2022 ID (`COUNTY TOTAL` rows in every county), NJ (`<County> Totals`), MI, MS. 2018 OR (Tillamook).
    2024 NJ (Gloucester).
  * Municipal sub-totals: a precinct whose name is a prefix of ≥2 other precincts and that exactly equals their
    sum. This was needed for NJ 2024 (for example, "Allendale" vs "Allendale 1..4"). It removed 1.27M duplicate votes.
  * Duplicated precinct sets: the same county-contest reported twice under different precinct names,
    for example IN-2024 St. Joseph, where "110003" also appears as "PENN TWP 3 110003". A record is removed only when >30% of the county's
    precincts have an identical multi-candidate vote vector.
  * A row that is a duplicate precinct-mode key and equals the county sum of the other rows: IN-2024 Hendricks, where
    the county total was folded into one precinct.
  * All of these rules were tuned so that they fire nowhere else. Earlier, looser versions produced false
    positives (for example, an absentee precinct that happened to hold exactly half of a county's votes), and those
    versions were rejected.
* NC 2020: the zip has two CSVs, the second a re-sorted duplicate. Only `2020-nc-precinct-general.csv` is used.
* Redacted counts (`*`, small precincts in CA, KS, NM, NV) are counted as 0. NM 2020 codes suppressed
  counts as -1, and these are set to 0. Other negative values (MI precinct-9999 statistical adjustments) are genuine
  corrections and are kept.
* 2016: the coverage notes say AL/SC straight-ticket votes must be added to candidates. Tests showed
  that MEDSL's 2016 candidate totals **already include** them (adding them overshot by 50-70%), so no
  allocation is done. 2018+ candidate totals likewise already include straight-ticket votes. The
  exception is the MEDSL warning for some IN-2024 counties for SEN and GOV.

### 3.4 Geography (`fips`)
* `fips` is the 5-digit county FIPS from MEDSL `county_fips`. Short codes are zero-padded (AL 2022 had
  4-digit codes). Any code outside the real county list is treated as missing.
* Missing or invalid codes are filled from the jurisdiction (town) name, using first the same file and then a
  2018/2020 town→county lookup (2016 NH cities, some ME townships). Anything still unassignable goes to
  a statewide row **`SS000`**: ME `23000` (statewide UOCAVA), RI `44000` (federal precincts), GA `13000`
  ("state floating" 2022/2024). These rows hold <0.3% of a state's votes. Drop them when mapping, but keep them
  for state totals.
* **Alaska**: precincts are by state house district. MEDSL gives no borough for 2016-2022 and only
  about half the votes for 2024. **Alaska is therefore one row `02000` in every year.** 2022/2024 AK numbers
  are MEDSL's first-choice (RCV round-1) counts.
* **Connecticut**: MEDSL uses the **old 8 counties (09001-09015) in every year, including 2022
  and 2024** (towns carry old-county `county_fips`), so no planning-region remapping was needed.
* New England (ME, MA, NH, VT, RI, CT) and WI report by town or ward. They are aggregated via `county_fips`.
  WI 2018 uses a legacy schema with no FIPS. Its counties are mapped from county names using WI 2020.
* Kansas City, MO (reported separately; MEDSL code `36000`, and `29380` in 2016) is assigned to Jackson
  County `29095`, since the KC election board covers only the Jackson part. SD `46113` (Shannon) becomes
  `46102` (Oglala Lakota). NY 2016 `36122` is a typo for Yates and becomes `36123`.

### 3.5 House
* County HOUSE = the sum over all regular districts touching the county (`special=0`). Same-day specials are
  separate `special=1` rows.
* `district` is 3-digit (`001`…). At-large states (AK, DE, ND, SD, VT, WY, and MT before 2022) are `000`.
  Rows with a blank, `STATEWIDE` or at-large code in multi-district states are assigned to the county's district
  when the county is in only one district. Otherwise they are kept in county totals but **left out of
  `house_districts.csv`** (code UNK): IN-2018 34k votes, WA-2022 28k, AZ-2016 1.4k, NY/RI-2024 <3k.
* `contested = 1` if both a D and an R candidate received votes. D-vs-D or R-vs-R top-two races (CA, WA)
  and races not printed on the ballot are 0 or absent. FL, LA-2022 (LA-4), OK-2016 (OK-1), OK-2024 (OK-3) and TX-2016
  (TX-8) omit unopposed races, so those districts are missing. `house_districts.csv` has regular races
  only.

### 3.6 `races.csv`
`dem_cand` and `rep_cand` are the largest D or R candidate with ≥0.5% of the vote. Name variants are merged, so stray write-ins such
as 2 votes for "Peter Welch" in VT-2018 are ignored. `dem_votes` and `rep_votes` are **all** D or R votes, the same as
county_results. Extra columns: `dem_cand_votes`, `rep_cand_votes`, `n_dem_cands`, `n_rep_cands`
(candidates ≥0.5%), `dem2_*` and `rep2_*` (second D or R, for jungle and top-two races such as CA-2018 Feinstein v de León,
AK-2022 Murkowski v Tshibaka, GA-2020 special, LA), `oth_votes`, `winner_cand`, `winner_class`.
`top_other_*` is the largest named non-D/R candidate (generic write-in rows are used only if there is no
named one), with MEDSL `party_detailed` as its party.

## 4. Coverage (state-races present / expected)

| | PRES | SEN | GOV | HOUSE |
|---|---|---|---|---|
| 2016 | 51/51 | 34/34 | 12/12 | 50/50 (HI-1 and IN problems) |
| 2018 | - | 33/33 + 2 specials | 36/36 (NY incomplete) | 50/50 (NY and ME-2 incomplete) |
| 2020 | **50/51: no IN** | 33/33 + 2 specials | **10/11: no IN** | **49/50: no IN** |
| 2022 | - | **33/34: no CA** + OK special (**CA special missing**) + GA runoff | **35/36: no TN** | 50/50 (IN about 40% of counties) |
| 2024 | 51/51 (**LA missing early vote**) | 33/33 + 2 specials | 11/11 (ND missing 2 counties) | 50/50 |

All gaps are listed in `data_quality.csv`.

## 5. Validation
* **PRES national** (sum of county rows): 2016 D 65,850,245 / R 62,978,715 (certified 65,853,514 /
  62,984,828). 2020 D 80,035,956 / R 72,493,156 without Indiana; adding Indiana's certified result
  (about 1.24M / 1.73M) gives about 81.28M / 74.22M, matching certified 81,283,501 / 74,223,975 to within
  0.01%. 2024 D 74,588,779 / R 76,672,361 (certified 75,017,613 / 77,302,580). The gap is almost
  entirely LA (missing early votes), plus IN, NJ and ME.
* **PRES by state vs tonmcg 2020**: every state within 0.5% for D and R except KS and ME. For those two, tonmcg
  itself is off and our values equal the certified results (KS 570,323 / 771,406; ME 435,072 / 360,737).
  41 counties differ by more than 2%, almost all of them KS (a tonmcg issue).
* **2024 PRES and SEN vs MEDSL state-level files**: D and R match within 0.5% everywhere except LA (-48%), IN
  (PRES D -2.1% / R -0.8%; SEN D -2.4% / R -1.0%), NJ (about -1% / -0.6%), ME (PRES D -1.2%, SEN D -2.7%)
  and CT SEN D +4.9% (expected, because the Working Families fusion line is included in our count). Total-vote differences of about 1-4% are blank or
  over-vote lines in the MEDSL state file.
* **2016 vs MEDSL election-context county data** (Pettigrew sen/house/gov, MEDSL pres): D and R are within 0.5%
  in every state except these:
  * Reference problems: MO, because the reference leaves Kansas City out of Jackson County while ours adds it, and our MO statewide values
    equal certified (Clinton 1,071,068). AZ SEN and ND SEN/GOV, which are broken or missing in the reference.
  * Our own issues: HI House (HI-1 merge), IN House R +1.7%, SC SEN D -6.9% and House D -2.9% (fusion-line name
    variants), and OR House R +10.7% / UT House D -2.3% (candidate-level vs line-level fusion counting).
  * The national 2016 PRES matches certified totals to within 0.01%.
* **Certified statewide spot checks** (`build/known_check.csv`): 52 of 57 within 0.5%.
  Examples: 2018 TX SEN Cruz 4,259,630 / O'Rourke 4,044,073 (certified 4,260,553 / 4,045,632, -0.03%). 2022 GA
  SEN Warnock 1,946,117 / Walker 1,908,442 (exact). 2022 GA runoff 1,820,633 / 1,721,244 (exact). 2018 FL,
  GA, AZ, NV, MO, WI, MN-special, MS-special. 2020 GA (both), AZ, NC, MI, ME, TX. 2022 PA, AZ, NV, OH, WI, NC, FL, NY,
  TX, AZ, PA, OK, SC. 2024 TX, PA. 2016 PA, WI, IN SEN, NC/MO/IN GOV, NV, NH SEN. The 5 deviations: **2018 NY GOV**
  (D -9.6%, R -15.5%, incomplete counties), **2018 IN SEN** (about -1%), **2022 MI GOV** (D -1.2%, R -0.6%),
  **2016 NH GOV** (-3%, Sullivan County missing) and **2022 CA SEN** (missing).
* Cross-office consistency: county totals for each office were compared with the county's largest-office total.
  This flagged the missing counties listed in `data_quality.csv`, ME-2 2018, NY 2018, ND GOV 2024, and
  the 2016 HI-1 and Kosciusko House doubling. It also flagged uncontested House races, where low House totals are expected.

## 6. Known caveats (also in `data_quality.csv`)
* **Missing races:** IN 2020 (all offices), CA 2022 SEN (regular and special), TN 2022 GOV.
* **Do not trust LA 2024 shares.** Early votes are absent from MEDSL's precinct file (about 48% of votes), which
  skews results Republican.
* **NY 2018** is incomplete for GOV, SEN and HOUSE. **ME 2018 House** has no ME-2. **IN 2022**: 54 of 92 counties are
  absent. **IN 2024**: Monroe is partial. **ND 2024 GOV**: Burleigh and Divide are absent. **NJ 2024**: Mercer has no
  early vote. **AR 2022**: Phillips is absent. **ID 2022**: Power County SEN/HOUSE are absent.
* **2016 HI House**: the HI-1 regular and same-day special are merged by MEDSL (Honolulu House votes about double).
  **2016 IN House**: Kosciusko is doubled and Wabash is absent. **2016 NH GOV**: Sullivan is absent.
* Ranked choice: AK (2022, 2024) and ME (ME-2 2018 is missing; ME-2 2022 and 2024; ME SEN) use MEDSL's
  first-round / first-choice counts. They are not final-round results.
* Nevada "None of these candidates" is excluded from totals. Redacted `*` counts are zero, which affects
  small precincts in CA, KS, NM and NV, and minor candidates the most.
* Statewide-only ballots (UOCAVA and similar) are in `SS000` rows and not in any county.
