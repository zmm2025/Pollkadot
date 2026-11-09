# County-level US election results, 2000-2024

County-level Democratic / Republican / other votes for **President (2000-2024), U.S. Senate and Governor
(2000-2024) and U.S. House (2016-2024)**. Everything is built from as few sources as possible, in this
order of preference:

1. **MIT Election Data + Science Lab (MEDSL)** on Harvard Dataverse: the main source.
2. **Amlani & Algara county returns** (Harvard Dataverse): Senate and Governor before 2016, which MEDSL
   doesn't publish by county, plus the few 2016-2020 races where MEDSL is incomplete.
3. **Official state results** (state election offices): only for the specific races both of the above get
   wrong or leave out. Each one is a documented patch in `patches/`.

| file | content |
|---|---|
| `county_results.csv` | `year,office,special,state_po,fips,dem,rep,oth,total,source`, one row per county x race |
| `races.csv` | candidate names per state-race (`dem_cand`, `rep_cand`, `top_other_cand`, ...) |
| `house_districts.csv` | `year,state_po,district,dem,rep,oth,contested` (regular House races, 2016-2024) |
| `validation.csv` | every state-race compared with an independent statewide total, plus counties with no votes |
| `data_quality.csv` | known gaps, approximations and fixes, by year x office x state (shown under **Details** on the site) |
| `patches/` | official-state-results patches: one CSV + JSON (sources, method, validation) per race |

Build: `python -P pipeline/fetch.py` (downloads, pinned in `pipeline/sources.json`, checksums in
`data/raw/dataverse_lock.csv`), the MEDSL precinct stages in `pipeline/data_sources/medsl/`, then
`python -P pipeline/build_results.py` and `python -P pipeline/validate_results.py`. See DEVELOPMENT.md.

## 1. Sources

| what | dataset | version |
|---|---|---|
| President 2000-2024 | MEDSL, *County Presidential Election Returns 2000-2024*, doi:10.7910/DVN/VOQCHQ | 20.0 |
| Senate / House / Governor 2016 | MEDSL, *U.S. Senate / U.S. House / State Precinct-Level Returns 2016*, doi:10.7910/DVN/NLTQAD, PSKDUJ, GSZG1O | 11.1, 12.0, 10.1 |
| Senate / House / Governor 2018-2024 | MEDSL, *Precinct-Level Returns 20xx by Individual State*, doi:10.7910/DVN/NVQYMG (2018), NT66Z3 (2020), UYQIEP (2022), NYTPDU (2024) | 1.1, 8.0, 5.0, 1.0 |
| Senate 2022 | MEDSL, *U.S. Senate county-level results 2022*, doi:10.7910/DVN/YB60EJ (state county results, used where it covers at least as many counties as the precinct data) | 3.0 |
| Senate / Governor 2000-2014; fills | Amlani & Algara, *Replication Data for: Partisanship & Nationalization in American Elections ... 1872-2020*, doi:10.7910/DVN/DGUMFI | 1.1 |
| Alaska Senate 2000-2014, Alaska President | MEDSL, *U.S. Senate statewide 1976-2024* (PEJ5QU) and *U.S. President 1976-2024* (42MVDX) | 8.0, 10.1 |
| Gaps | official state results, `patches/` (see section 4) | |

All Dataverse files are CC0. Several MEDSL datasets require a one-time Dataverse guestbook response;
`fetch.py` submits it from `DATAVERSE_GUESTBOOK` / `.dataverse-guestbook.json` (git-ignored).

## 2. How the sources are combined (`pipeline/build_results.py`)

* **President.** MEDSL county returns. A county-candidate can have one `TOTAL` row, vote-method rows, or both;
  when both exist `TOTAL` is used (2020/2024 otherwise double-count). Non-candidate rows ("TOTAL VOTES CAST",
  under/over votes, spoiled) are dropped. Alaska (reported by state house district) uses MEDSL's statewide
  totals. Maine and Mississippi 2004 use Amlani & Algara, because MEDSL's county file is 4-8% off the certified
  result there and Amlani & Algara matches it.
* **Senate, House, Governor 2016-2024.** MEDSL precinct returns summed to counties with the rules in section 3.
  2022 Senate uses MEDSL's county-level file wherever it covers at least as many counties (this fixes California,
  which has no Senate rows in the precinct data, and Indiana, where most counties released no precinct data).
* **Senate and Governor 2000-2014.** Amlani & Algara, even-year November elections. Their Senate data omits
  Alaska (filled from MEDSL statewide) and their Governor data omits Alaska and Utah's 2010 special election
  (both patched). They code Angus King (ME 2012) and Bernie Sanders (VT 2006, 2012) as Democrats; here they are
  independents (`oth`), like 2016+. From 2004 their Jackson County, MO excludes Kansas City (patched). The
  January 2010 Massachusetts special is left out (not a November election). Louisiana's 2002 and 2014 Senate
  values are the December runoffs (the decisive round), as in their data.
* **Amlani & Algara fills, 2016-2020.** Counties MEDSL has no votes for (NH 2016 Governor: Sullivan;
  IN 2018 Senate: Washington) come from Amlani & Algara. Whole races come from them where MEDSL is incomplete in
  many counties: NY 2018 Senate and Governor, IN 2020 Governor.
* **Patches** are applied last (`replace` a state-race, `fill` listed counties, or `add` to a county).
* `source` on every row says where it came from.

## 3. MEDSL precinct processing rules (`pipeline/data_sources/medsl/`)

These apply to the 2016-2024 precinct returns before they are merged.

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

## 4. Patches from official state results

Each patch's JSON has the full source list, the method and its validation against the certified totals.
Every `replace` patch matches the certified state or district totals (to the vote, except where noted).

| patch | mode | source |
|---|---|---|
| `2002_AK_GOV` | replace | [Alaska Division of Elections](https://www.elections.alaska.gov/results/02GENR/data/results.pdf) |
| `2004_MO_GOV_kc` | add | [Missouri Secretary of State](https://www.sos.mo.gov/CMSImages/ElectionResultsStatistics/CountyGeneral2004.pdf) |
| `2004_MO_SEN_kc` | add | [Missouri Secretary of State](https://www.sos.mo.gov/CMSImages/ElectionResultsStatistics/CountyGeneral2004.pdf) |
| `2006_AK_GOV` | replace | [Alaska Division of Elections](https://www.elections.alaska.gov/results/06GENR/data/results.pdf) |
| `2006_MO_SEN_kc` | add | [Missouri Secretary of State](https://www.sos.mo.gov/CMSImages/ElectionResultsStatistics/CountyGeneral2006.pdf) |
| `2008_MO_GOV_kc` | add | [Missouri Secretary of State](https://www.sos.mo.gov/CMSImages/ElectionResultsStatistics/CountyGeneral2008.pdf) |
| `2010_AK_GOV` | replace | [Alaska Division of Elections](https://www.elections.alaska.gov/results/10GENR/data/resultsOF.pdf) |
| `2010_MO_SEN_kc` | add | [Missouri Secretary of State](https://www.sos.mo.gov/CMSImages/ElectionResultsStatistics/CountyGeneral2010.pdf) |
| `2010_UT_GOV_special` | replace | [Utah Lieutenant Governor](https://vote.utah.gov/wp-content/uploads/2023/09/2010Gen.xls) |
| `2012_ME_SEN` | replace | [Maine Secretary of State](https://www.maine.gov/sos/sites/maine.gov.sos/files/inline-files/2012ussenatemuni.xls) |
| `2012_MO_GOV_kc` | add | [Missouri Secretary of State](https://www.sos.mo.gov/CMSImages/ElectionResultsStatistics/OfficialResults11-6-12.pdf) |
| `2012_MO_SEN_kc` | add | [Missouri Secretary of State](https://www.sos.mo.gov/CMSImages/ElectionResultsStatistics/OfficialResults11-6-12.pdf) |
| `2014_AK_GOV` | replace | [Alaska Division of Elections](https://www.elections.alaska.gov/results/14GENR/data/results.pdf) |
| `2016_HI_HOUSE_honolulu` | fill | [Hawaii Office of Elections](https://files.hawaii.gov/elections/files/results/2016/general/media.txt) |
| `2016_IN_HOUSE_fix` | fill | [Indiana Election Division](https://enr.indianavoters.in.gov/archive/2016General/data/OffCatC_1753_A.json) |
| `2018_ME_HOUSE_d2` | add | [Maine Secretary of State](https://www.maine.gov/sos/elections-voting/election-results-data/election-results-2018) |
| `2018_NY_HOUSE` | replace | [New York State Board of Elections](https://www.elections.ny.gov/NYSBOE/elections/2018/general/2018Congress.xlsx) |
| `2020_IN_HOUSE` | replace | [Indiana Election Division](https://enr.indianavoters.in.gov/archive/2020General/data/OffCatC_1005_A.json) |
| `2022_AR_GOV_phillips` | fill | [Arkansas Secretary of State](https://results.tally-enr.com/results/arkansas/1844/FullDataFile.json) |
| `2022_AR_HOUSE_phillips` | fill | [Arkansas Secretary of State](https://results.tally-enr.com/results/arkansas/1844/FullDataFile.json) |
| `2022_CA_SEN_special` | replace | [California Secretary of State](https://elections.cdn.sos.ca.gov/sov/2022-general/sov/45-uss-pt.xlsx) |
| `2022_ID_GOV_power` | fill | [Idaho Secretary of State canvass database](https://canvass.sos.idaho.gov/eng/contests/download/17251/show_granularity_dt_id:3/.csv) |
| `2022_ID_HOUSE_power` | fill | [Idaho Secretary of State canvass database](https://canvass.sos.idaho.gov/eng/contests/download/17249/show_granularity_dt_id:3/.csv) |
| `2022_IN_HOUSE` | replace | [Indiana Election Division](https://enr.indianavoters.in.gov/archive/2022General/data/OffCatC_1005_A.json) |
| `2022_MI_GOV_wayne` | fill | [Michigan Secretary of State](https://mvic.sos.state.mi.us/VoteHistory/GetElectionResultFile?electionId=691) |
| `2022_MI_HOUSE_midland` | fill | [Michigan Secretary of State](https://mvic.sos.state.mi.us/VoteHistory/GetElectionResultFile?electionId=691) |
| `2022_TN_GOV` | replace | [Tennessee Secretary of State](https://sos-prod.tnsosgovfiles.com/s3fs-public/document/20221108AllbyPrecinct.xlsx) |
| `2024_IN_GOV_monroe` | fill | [Indiana Election Division](https://enr.indianavoters.in.gov/archive/2024General/data/OffCatC_1007_A.json) |
| `2024_IN_HOUSE_monroe` | fill | [Indiana Election Division](https://enr.indianavoters.in.gov/archive/2024General/data/OffCatC_1005_A.json) |
| `2024_IN_SEN_monroe` | fill | [Indiana Election Division](https://enr.indianavoters.in.gov/archive/2024General/data/OffCatC_1006_A.json) |
| `2024_LA_HOUSE` | replace | [Louisiana Secretary of State](https://voterportal.sos.la.gov/ElectionResults/ElectionResults/Data?blob=20241105/csv/ByParish_67171.csv) |
| `2024_ND_GOV` | fill | [North Dakota Secretary of State](https://results.sos.nd.gov/ResultsSW.aspx?text=Race&type=SW&map=CTY) |
| `2024_NJ_HOUSE_mercer` | fill | [NJ Division of Elections](https://www.nj.gov/state/elections/assets/pdf/election-results/2024/2024-official-general-results-us-house.pdf) |
| `2024_NJ_SEN_mercer` | fill | [NJ Division of Elections](https://www.nj.gov/state/elections/assets/pdf/election-results/2024/2024-official-general-results-us-senate.pdf) |

## 5. Validation (`pipeline/validate_results.py` → `validation.csv`)

Each state-race's county sum is compared with an independent statewide total: MEDSL's statewide President and
Senate files (compiled from state-certified totals, separately from the county data) and, for Governor 2016-2020,
Amlani & Algara. Of 1,358 state-races, 864 have a reference; 40 differ by more than 0.5% in D or R.
Every one of those is explained:

* **Fusion and candidate-level parties** (NY, CT, SC, OR; NY President 2000-2016): votes on a nominee's minor-party
  lines count for the nominee here; the reference counts party lines.
* **Jungle and runoff races** (LA, MS 2018 special, MN 2002): Louisiana 2002/2014 here are the December runoffs; the
  reference sums every Democrat and Republican in the November round.
* **The reference is wrong**: WV 2006 and UT 2010 Senate (MEDSL statewide figures differ from the certified results,
  which Amlani & Algara match), MS 2004 President, MO 2016 Governor (Amlani & Algara leaves out Kansas City; the
  MEDSL value used here includes it).
* **Small known gaps** listed in `data_quality.csv`: Maine overseas ballots (2012, 2018, 2020, 2024), NJ and IN 2018 Senate,
  ME 2024 Senate.

Counties with no votes in a race: Broomfield, CO in 2000 (created in 2001), Washington County, IN in the
2018 House, and counties wholly in uncontested House districts (FL, LA, OK, TX don't print unopposed races).

## 6. Known caveats (also in `data_quality.csv`)

* No House results before 2016: no free source publishes them by county.
* **Alaska** is a single statewide unit in every race (results aren't reported by borough).
* Ranked-choice races (AK 2022/2024, ME) use first-round counts.
* Independents (King, Sanders, Orman, Osborn, McMullin, Walker) are `oth`, so races they won show only the D-R share
  of the remaining vote.
* Nevada "None of these candidates" is excluded from totals; redacted (`*`) precinct counts are zero.
* Statewide-only ballots (overseas/military and similar) are in `SS000` rows and not in any county.
