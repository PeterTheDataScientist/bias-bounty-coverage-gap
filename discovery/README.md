# Texas low-water crossings, where roads go under water, appear on the open map as ordinary roads (Part 2 of my writeup, Best Bias Discovery)

Texas keeps two public lists of its low-water crossings, the places where a road dips through a creek bed and goes
under when the creek rises. Inside the challenge's Texas region they hold 8,454 distinct crossings. The Overture
road layer the challenge scores has the road at 93.1% of them and marks none of them as a crossing that floods,
because its schema has no value that could say so. Closing the crossings in Overture's own road network leaves
22,469 buildings in 216 areas with no mapped road out, after two independent checks (about 26,300 residents in about
11,200 homes, 162 tracts, 49 counties). The scorecard sees none of it. The entry, as posted, is Part 2 of
[../WRITEUP.md](../WRITEUP.md); this folder is the code behind every number in it, and [../results/](../results/) holds the
outcomes as tables and figures, the NOAA flood reports the entry quotes (`ncei/`) and the record of the imagery audit,
a random 40 of the 216 areas read twice (`audit/`).

**Data change, 25 September 2026.** The organisers' README for the challenge bucket now opens: "2026-09-25: TIGER/Line
roads, Microsoft building footprints, HIFLD facilities and CBP establishments were removed from every region at the
challenge organizers' request." Five of the nine Texas files this folder reads are among them: the Microsoft
footprints (every building count), the TIGER roads (the independent check of every cut) and the fire station, EMS
station and school layers (step 24). On 26 September all five returned 404 from the bucket, and the other four (tract
polygons, strata table, Overture roads, Overture places) were still there with the sizes the entry read. A fresh run
therefore needs copies made before 25 September: `bash run_all.sh --data-dir DIR` reads every challenge layer from DIR
and downloads none. [INPUTS_MANIFEST.csv](INPUTS_MANIFEST.csv) gives the size and sha256 of each of the nine files the
entry read (and of the Overture extra road classes step 0e downloads), and `python fetch_challenge.py --data-dir DIR`
checks a copy against it. The original public sources are
Microsoft Global ML Building Footprints (https://github.com/microsoft/GlobalMLBuildingFootprints) and the U.S. Census
Bureau's TIGER/Line 2025 roads (https://www2.census.gov/geo/tiger/TIGER2025/ROADS/); the facility layers are USGS The
National Map structures. The challenge's copies were clipped to the region, so a download from those sources is not
the same file, and it has not been tested here as a substitute. Without the removed layers, every outcome up to step 23
can still be checked against the tables in [../results/](../results/); the facility count of step 24 needs the copies
(its Overture places half runs from the bucket as it is). On 26 September the whole of `run_all.sh --data-dir` was
rerun in a clean folder with the challenge layers read from local copies and nothing from the bucket or the cache,
and every result came out as before: `core_numbers.json` with 216 areas, 22,469 buildings and 26,257 residents, and
every table in `../results/` and both figures byte for byte. Later that day the two figures were redrawn with their
legends reworded ("no mapped road out"), and step 28 (the NOAA flood reports) and the second reading of the imagery
audit were added; [../TESTING.md](../TESTING.md) gives the sha256 values as they now stand.

Every command below runs from this folder. Each script prints its own help with `--help`, and stops with the
command that makes an input when that input is missing. `python common.py` lists every input and says which are
present.

## Run it

    cd ../documentation && pip install -r requirements.txt && python pipeline.py --check --extra --data-dir DIR && cd ../discovery
    pip install -r requirements.txt
    bash run_all.sh --data-dir DIR

DIR is a folder holding the challenge layers, under the bucket's names (`DIR/reference/south-central-tx/FILE`,
`DIR/strata/south-central-tx/FILE`, `DIR/south-central-tx/FILE` or `DIR/FILE`) or under the cache's
(`DIR/reference__south-central-tx__FILE`); both parts look in the same places. The documentation run (about 18
minutes) writes the per-tract counts the discovery takes its scorecard values from. `run_all.sh` then checks the nine
layers against the manifest, fetches what else is missing and runs every step in order. Without `--data-dir` the
layers come from the shared cache (`../documentation/cache`, or `BIAS_CACHE`), and whatever is missing there is
downloaded from the bucket, which since 25 September no longer works for the five removed files. On 2 cores and 8 GB
the clean run of 25 Sep 2026 took 1,409 s in all (peak memory 4.4 GB): 263 s to download 577 MB of Overture roads,
about 500 s of TIGERweb queries for Census blocks (`block_pop.py` and `block_pop_v4.py`) and about 650 s of analysis,
the road graphs included; the run of 26 Sep from local copies took 1,278 s with the Overture roads already
downloaded. Step 28, added on 26 Sep, downloads 337 MB of NOAA files in about 100 s (into `raw/ncei/`, or the folder
`NCEI_DIR` names) and then runs in under a minute (47 s, peak memory 1.2 GB). The run writes about 1.1 GB to `work/`.
Python 3.11 and the versions pinned in `requirements.txt`.

Network access is needed for the Overture bucket on S3 (release 2026-08-19.0), the Census Bureau's TIGERweb service
(`block_pop.py`, `block_pop_v4.py`, `occupancy.py`), NOAA's NCEI file server (`ncei_events.py`, for any of its 90 files
not already in `raw/ncei/` or `NCEI_DIR`) and the DuckDB extension repository (`httpfs` and `spatial`, installed on
first use), and for the Source Cooperative bucket when you run without `--data-dir`; the audit's images also need the
USGS imagery service. The two inventories and the OSM tags come from [inputs/](inputs/) unless you ask
otherwise (`LWC_SOURCE=live`, `OSM_PBF=...`; see the top of `run_all.sh`).

## The steps

| Step | Script | What it does | Writes |
|---|---|---|---|
| 0a | `scorecard_inputs.py` | Scorecard components and Microsoft footprints per tract, from `../documentation/out/counts.parquet` | `work/bias_components.parquet`, `work/tract_ms_bldg.parquet` |
| 0b | `fetch_challenge.py` | The nine Texas challenge layers: with `--data-dir`, checks the local copies against `INPUTS_MANIFEST.csv`; without it, downloads into the shared cache what is missing and still in the bucket | cache, or nothing |
| 0c | `fetch_lwc.py` | The TxGIO and TWDB inventories: the 24 Sep snapshot, or today's lists | `raw/` |
| 0d | `osm_fords.py` | OSM ford and flood tags, and the highway ways through ford nodes | `work/osm_*.parquet` |
| 0e | `fetch_overture_extra.py` | Overture's service, track, living_street and unknown roads in Texas, compared with their row in `INPUTS_MANIFEST.csv` (an existing file is only compared: `--check`) | `work/extra_segments.parquet` |
| 1 | `lwc_prepare.py` | One table of crossings, placed in tracts; TWDB points within 50 m of a TxGIO point are the same crossing | `work/lwc_all.parquet` |
| 2 | `lwc_overture.py` | Every Overture segment within 100 m of each crossing | `work/lwc_seg_candidates.parquet` |
| 3 | `lwc_match_eval.py` | The segment that carries each crossing, by name or distance, and its flags (uses `lwc_names.py`) | `work/lwc_unique.parquet` |
| 4 | `lwc_tracts.py` | Crossings per tract, and what the scorecard says about those tracts | `work/tracts_lwc.parquet` |
| 5 | `lwc_osm_eval.py` | Which crossings OpenStreetMap tags as fords or flood-prone, and what reaches Overture | `work/lwc_unique_osm.parquet` |
| 6 | `lwc_graph.py NETWORK VARIANT` | Split roads at connectors, remove each crossing's piece, find the areas cut off | `work/graph_base_*`, `edges_*`, `groups_*`, `cuts_*` |
| 7 | `lwc_buildings.py NETWORK VARIANT` | Buildings whose nearest road is in a cut-off area | `work/bldg_*`, `work/groups_b_*` |
| 8 | `tiger_check.py plus strict 10 single` and `30 multi` | The same cut in the Census Bureau's TIGER roads | `work/tiger_check_*` |
| 9 | `nearmiss.py plus strict` | Flags areas where a road inside passes near a road outside away from any crossing | `work/nearmiss_pairs_*`, columns in `groups_b_*` |
| 10 | `block_pop.py plus strict` | Residents and homes from 2020 Census blocks | columns in `groups_b_*` |
| 11 | `stranded_segs.py plus strict` | Which segments are cut off in which area, for the maps | `work/stranded_segs_*` |
| 12 | `report_who.py`, `examples.py` | Who is behind the crossings; the named places with everything needed to check them | `work/report_who.json`, `work/examples_confirmed.csv` |
| 13 | `disc_numbers.py`, `core_numbers.py` | Every number the entry quotes, from the outputs above | `work/discovery_numbers.json`, `work/variants_table.csv`, `work/core_numbers.json` |
| 14 | `block_pop_v4.py` | Census block residents and homes for all six versions, not only the lead one; checks plus/strict against step 10 | `work/v4_blockpop_*`, `work/v4_blocks_cache.parquet` |
| 15 | `variants_v4.py` | The six versions and the careful set in one table, checked against step 13 | `work/v4_variants_table.csv`, `.txt`, `work/v4_variants.json` |
| 16 | `uncertainty.py` | Bootstrap intervals for the SVI and CVI contrasts (by area and by tract, within rural and urban tracts), and the rural against urban crossing rate with exact, cluster bootstrap and permutation tests | `work/v4_uncertainty.json` |
| 17 | `flood_attr_gap.py` | The challenge's own gap formula applied to a ford or flood attribute: every road_flags value in the release, and per tract 1 - min(1, marked / official) beside the scorecard road gap | `work/v4_flood_attr_gap.json`, `work/v4_flood_attr_gap_tracts.csv` |
| 18 | `who_v4.py` | Every SVI theme and CVI component of the careful set against the region, with intervals | `work/v4_who.json` |
| 19 | `per_tract_table.py` | One row per tract holding a careful-set building, as a table and as fixed-width text for posting; both carry the strata table's SVI, so they stay in `work/` and step 23 ships the table without it | `work/v4_per_tract_table.csv`, `.txt` |
| 20 | `precision_audit.py sample`, `audit_summary.py`, `audit_agreement.py` | The imagery audit: the seeded sample of 40 careful-set areas, checked against the one in `../results/audit/`; the first reading's precision and imagery-adjusted counts; and the two readings compared (agreement, each reading's precision, the building-weighted counts) | `work/v4_audit_sample.csv`, `work/v4_audit_strata.csv`, `work/v4_audit_verdicts.csv`, `work/v4_audit_summary.json`, `work/v4_audit_agreement.json` |
| 21 | `figures.py` | The region map and the Bexar map, vector data only | `figs/v4_region_map.png`, `figs/v4_bexar_979.png` |
| 22 | `numbers_v4.py` | Every number of steps 14 to 21 in one file | `work/discovery_numbers_v4.json` |
| 23 | `export_results.py` | The tables and figures in `../results/` | `../results/` |
| 24 | `facilities.py` | Schools, fire stations and EMS stations inside the careful set's areas, placed by the rule that places the buildings (nearest road piece within 300 m); checks first that the rule gives back the 22,469 buildings area by area. Reads the facility layers (a local copy, see above) and Overture places | `work/v5_facilities.json`, `work/v5_facilities_candidates.csv` |
| 25 | `occupancy.py` | Homes per resident for the careful set and the six named places from the same 2020 Census blocks, beside the region and its rural tracts (one TIGERweb statistics query per condition, cached with its retrieval time). The block layer holds residents and housing units only, so no vacant or seasonal share | `work/v5_occupancy.json`, `.txt`, `work/v5_tigerweb_tract_sums.json` |
| 26 | `example_tracts.py` | The six named places tract by tract: buildings, residents and homes per tract, each tract's scorecard road gap and SVI, and each crossing with its tract | `work/v5_example_tracts.csv`, `.txt`, `.json` |
| 27 | `numbers_v5.py` | Every number of steps 24 to 26 in one file | `work/discovery_numbers_v5.json` |
| 28 | `ncei_events.py` | NOAA NCEI Storm Events, 1996 to 2025: the 90 bulk files checked against `../results/ncei/ncei_manifest.json` by sha256 (a missing one downloaded, a different one stops the run); flood events in the region's counties, reports that mention a low-water crossing, the vehicle share of deaths, and the reports matched to named inventory crossings. Skipped with `NCEI=0` | `work/ncei_events_region.csv`, `work/ncei_crossing_matches.csv`, `work/ncei_summary.json`; `../results/ncei/` |

NETWORK is `base` (the challenge's road file) or `plus` (also service lanes and farm tracks); VARIANT is `all`,
`strict` (crossings matched by name, or unnamed within 15 m) or `fords` (the strict list, fords only). The entry
leads with `plus strict`. `common.py` holds the paths every script shares; `v4_common.py` rebuilds the careful set
exactly as `core_numbers.py` does, for steps 14 to 28. Every random step uses a fixed seed (20260926 from step 14 on).
Steps 24 to 27 keep their outputs in `work/`: steps 25 and 26 carry strata-table values, and step 24 names records of
a layer the organisers have since removed from their bucket. Step 28 writes its own four files to `../results/ncei/`:
the file manifest, the summary, the event table without two columns that repeat others, and the match table with any
personal name removed from the report excerpts (`python ncei_events.py --results DIR` writes them elsewhere).

## Outside the main run

- `join_strata.py`: adds columns of the challenge's strata table (for example `svi_overall`, `ur_class`) to every
  table in `../results/` by GEOID, into `work/joined/`, for your own analysis (see the licence note in
  [../results/README.md](../results/README.md)).
- `precision_audit.py prep`, `render` and `extras` (`AUDIT_IMAGES=1 bash run_all.sh`): draw again, into
  `figs_audit/`, the 164 images the audit's verdicts cite: an overview of each sampled area over USGS imagery with
  the network cut on top, 1.5 km tiles for large areas, close-ups where its roads come nearest the main network, and
  the 24 extra close-ups listed in `../results/audit/extra_views.csv`. `zoom`, `tiles`, `px` and `pxzoom` make further
  close-ups. The images are never committed.
- `make_maps.py 979 623 921 952 1030 266`: the maps of the six named places (`FIGURES=1 bash run_all.sh`).
- `imagery_check.py AREA ...`: USGS orthoimagery under an area's roads and crossings, for a look at any area. Of the
  six named places, only area 979 is in the audit's sample (`../results/audit/README.md`).
- `nearmiss_touch.py`: classifies the near-misses where the roads touch (bridge or underpass, missing junction).
- `nearmiss_imgs.py N`: imagery at the closest point of N flagged near-miss pairs.
- `nearmiss_v1_wholeseg.py` and `nearmiss_sample.py`: the first version of the near-miss test and its imagery
  sample, kept as a record. Version 1 compared the cut-off roads with whole main-network segments, so a main segment
  whose crossing piece reaches into the cut-off side touched it at its own far end; 116 of its 126 zero-distance
  flags were that artefact. `nearmiss.py` compares with the main network's own pieces only. The version 1 script
  writes its own `_v1` files and never touches the results.

## What reproduces exactly

The inputs that change over time are fixed in [inputs/](inputs/): the two inventories as retrieved on 24 Sep 2026
and the OSM tags of the 23 Sep extract. On 25 Sep 2026 the whole of `run_all.sh` was rerun from a clean folder in a
fresh virtual environment, downloads included, and every output matched the entry's own run: every table in
`../results/` and both figures byte for byte, `core_numbers.json`, `report_who.json`, `examples_confirmed.csv` and
`variants_table.csv` byte for byte, and every value of `discovery_numbers.json` and `discovery_numbers_v4.json`
(the first differs only in the time of the Overture download it records). The Overture roads downloaded that day
were byte for byte the file of 24 Sep. [../TESTING.md](../TESTING.md) lists what the run prints and the sha256 of
each file. On 26 Sep 2026, after the organisers had removed five of the layers from their bucket, the run was repeated
from a clean folder with `--data-dir` pointing at copies that match `INPUTS_MANIFEST.csv`: the Overture roads,
downloaded again, were once more byte for byte the file of 24 Sep, the same files matched byte for byte (the two
`v4_` files that differ in wording aside, see TESTING.md), and the new steps 24 to 27 gave the same outputs as the
entry's own run, the TIGERweb retrieval time aside.

Three things cannot be pinned here. Overture release 2026-08-19.0 is needed for the road network (the challenge file
and the extra classes); Overture keeps only recent releases online, and once it is retired `../results/` carries the
outcomes. `block_pop.py`, `block_pop_v4.py` and `occupancy.py` ask TIGERweb for 2020 Census blocks, which do not
change, over the network. And since 25 September 2026 the Microsoft footprints, TIGER roads and facility layers can
only come from a copy made before then (see the note at the top); `INPUTS_MANIFEST.csv` says whether a copy is the
one the entry read. The NOAA files are not shipped but pinned: `../results/ncei/ncei_manifest.json` holds the sha256
of each of the 90, step 28 stops if one differs (NCEI replaces a year's file when it corrects it; `--refresh` takes the
current files, and the numbers may then change), and on 26 Sep 2026, run from cached copies of those files, it gave
`work/ncei_*` byte for byte as the entry's own run. The imagery audit's two readings, made independently from the
same renders following written rules, are shipped in `../results/audit/` rather than recomputed; `audit_agreement.py` recomputes
every figure drawn from them.

## Adding a step

New analysis scripts drop in the way steps 14 to 28 did:

1. Put the script in this folder and import its paths from `common.py` instead of writing them out:
   `STRATA`, `TRACTS`, `COMPONENTS`, `OVT_ROADS`, `EXTRA_SEGMENTS`, `MS_BUILDINGS`, `TIGER_ROADS`, `FIRE_STATIONS`,
   `EMS_STATIONS`, `SCHOOLS`, `OVT_PLACES`. They follow `--data-dir` (or `BIAS_DATA_DIR`) by themselves. Relative
   paths such as `work/...` keep working, because `common.py` moves into this folder. A new challenge layer goes into
   `CHALLENGE_KEYS` in `common.py` and gets a row in `INPUTS_MANIFEST.csv`.
2. Give it an `argparse` parser (so `--help` works) and a `need(...)` call listing its inputs.
3. Add one line to `run_all.sh`, below `export_results.py`, or above it if `export_results.py` should ship its output.
4. If it writes a table for `../results/`, add the table to `export_results.py` and to `../results/README.md`.
   Tables there carry no value read or computed from the challenge's strata table (social and climate
   vulnerability, population, rurality): those are CC BY-SA 4.0 and the tables are ODbL, so keep the tract GEOID
   and let `join_strata.py` add the strata columns locally ([../DATA_LICENCES.md](../DATA_LICENCES.md)).
5. Run `bash ../smoke_test.sh` and `bash ../scan_public_repo.sh` before committing.
