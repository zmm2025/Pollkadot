# places.csv: the largest cities in each county and state

Shown in the map tooltip. Columns: `fips` (5-digit county, or 2-digit state), `rank` (1–3), `name`, `pop` (residents inside that county or state), `part` (1 when the city also spills into other counties, so `pop` is only the part inside this one).

Build script: `pipeline/data_sources/places/build_places.py`, run from the repo root with `python -P`. Then `pipeline/build_data2.py` turns it into `site/data/places.bin`, which the page loads after the map.
The build is deterministic: repeated runs give the same output, sha256 `c6c063f162ca35d92cce6e3c060c380d01cff053edb634fd3654c9aaf9692a8c` (8,921 rows: 3,086 counties and 51 states).

## Input files (downloaded from the Census Bureau, www2.census.gov)

| File | URL | sha256 |
|---|---|---|
| `acsdt5y2024-b01003.dat`: ACS 2020–2024 5-year, table B01003 (total population), every geography | https://www2.census.gov/programs-surveys/acs/summary_file/2024/table-based-SF/data/5YRData/acsdt5y2024-b01003.dat | `38d1a992…b6ca90` |
| `Geos20245YR.txt`: names and codes for the geographies in that file | https://www2.census.gov/programs-surveys/acs/summary_file/2024/table-based-SF/documentation/Geos20245YR.txt | `b87a1d1a…aea344` |
| CT town → old county crosswalk | the same file as the population build (see `data/pop/README.md`) | `8489a213…0d35b3b` |

Save them in `build/downloads/census/`. The ACS is used rather than the Census city estimates (`sub-est2025.csv`) because those cover only incorporated cities, and some of the biggest communities are unincorporated: Honolulu, Arlington VA, Metairie LA, Columbia MD, and every place in Hawaii and most of Maryland and Virginia's counties.

## What counts as a city

- **Most states:** Census places, which are incorporated cities, towns and villages plus unincorporated communities (census-designated places). Each county gets the part of each place that lies inside it (ACS summary level 155). Places in more than one county are flagged `part`.
- **New England, New York, New Jersey and Pennsylvania:** towns, townships, boroughs and cities (county subdivisions, summary level 060). These are the actual municipalities there, and the Census places mostly sit inside them. For example, Nassau County shows the town of Hempstead (790,000) rather than the village of Hempstead (59,000). Unorganized territory, gores, grants and purchases are left out. Connecticut towns are mapped to the 8 old counties with the crosswalk.
- **New York City's five counties** use places, so they show New York City (part) rather than their borough, and New York State's list starts with New York City as a whole.
- **States:** the same cities, summed over the state's counties, top 3.

## Names

Census type words are dropped ("Phoenix city" → Phoenix, "Urban Honolulu CDP" → Honolulu), as are the county notes that tell same-named places apart ("Kailua CDP (Hawaii County)" → Kailua). Where the Census name has a common name in parentheses, the common name is used ("El Paso de Robles (Paso Robles)" → Paso Robles). Consolidated city-counties use their everyday name (Nashville-Davidson → Nashville, Louisville/Jefferson County → Louisville; the full list is `NAME_FIX` in the script).

## Counties with no list

56 counties show no cities:

- **The county is the city.** A city with the county's name and at least 95% of its people adds nothing, so it's left out: San Francisco, Denver, Broomfield, Philadelphia, Baltimore city, St. Louis city, Carson City, Arlington VA, Nantucket, Alaska's Anchorage, Juneau, Sitka, Wrangell and Yakutat, and Virginia's 38 independent cities.
- **Only a county-wide government:** Echols and Webster GA have no other place. Rest-of-county places named after the county (for example Greeley County KS's "balance") are skipped everywhere.
- **No places at all:** James City County VA and Kalawao HI.
