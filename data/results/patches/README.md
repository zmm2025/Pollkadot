# Patches from official state results

Each patch fixes one race in one state where the main sources (MIT Election Data + Science Lab, and
Amlani & Algara for Senate/Governor 2000-2014) are missing or incomplete. Only official sources are
used: state election offices, or county election boards where the state doesn't publish county figures.

A patch is two files with the same base name `<year>_<ST>_<OFFICE>[_special][_<suffix>]`:

* `<name>.csv`: `year,office,special,state_po,fips,dem,rep,oth`. Whole votes. `dem` = every vote for
  the Democratic nominee(s), including fusion lines that carry the same candidate (e.g. NY/CT Working
  Families). `rep` is the same for Republicans. `oth` = all other candidate votes, including write-ins.
  Blank, over and under votes are excluded. Independents (King, Sanders, Orman, ...) count as `oth`. Ranked-choice
  races use first-round counts.
* `<name>.json`: `mode`, the race keys, candidate names, sources and validation (see below).

`mode`:
* `replace`: these rows become the race's complete county set for that state (all other rows of the state-race are dropped).
* `fill`: only the listed counties are replaced; the rest of the state-race is kept.
* `add`: the listed values are added to the existing county values (e.g. Kansas City into Jackson County, MO).

County units follow the site's map: 5-digit FIPS; Connecticut's 8 old counties; Alaska is a single
statewide unit `02000`; Virginia independent cities are separate; Kansas City, MO is part of Jackson
County `29095`; Oglala Lakota SD is `46102`; Bedford city VA (`51515`) is part of Bedford County `51019`.

Raw official files are kept under `data/raw/state/<name>/` when small, and `pipeline/patches/<name>.py`
regenerates the CSV from them where the source is machine-readable.
