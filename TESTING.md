# Testing

Two quick checks run in seconds with no download; the full runs below rebuild everything from the public sources.
The expected values come from the entries' original runs (documentation: 23 and 25 Sep 2026; discovery: 24 and
25 Sep 2026), and every one of them was reproduced by a full run on 25 Sep 2026: fresh virtual environments made
from the requirements files, Python 3.11.15 on Linux x86-64, 2 cores and 8 GB of memory, one job at a time, with the
challenge layers already in the cache. The times and peak memory below are from that run; peak memory is the
resident size of the largest single process. The documentation entry's runs were repeated on 26 Sep 2026 on the same
machine type from local copies with `--data-dir`, after the organisers removed four layers from the bucket (below);
section 1 gives those times too. So was the discovery's full run, from a clean folder with an empty cache (section 2).
Three things were added to the discovery later on 26 Sep 2026 and checked on their own (section 2b): step 28, the NOAA
Storm Events step, whose outputs came out byte for byte as the entry's own; the comparison of the imagery audit's two
readings (`audit_agreement.py`, in step 20); and the two figures, redrawn with reworded legends. The next section
lists every input a run checks against a manifest and every one it reads live.

## Set up

Python 3.11 (tested with 3.11.15), from the repository root:

    python3 -m venv .venv
    . .venv/bin/activate
    pip install -r documentation/requirements.txt -r discovery/requirements.txt

## Quick checks

    bash smoke_test.sh
    bash scan_public_repo.sh

`smoke_test.sh` compiles every module, imports every library, runs every script's `--help`, parses the shell
scripts, prints the projection fingerprint and runs the road-name matcher's self-test. Once
`documentation/out/counts.parquet` exists (section 1b) it also rebuilds `out/sensitivity.csv`, rebuilds the scored
file from the counts and checks its sha256, and checks the column sums of the acceptance window.
`scan_public_repo.sh` checks every file git would commit for credentials, email addresses, local paths, other
projects' names, files over 5 MB, binary data files, challenge layers, strata-table columns in a CSV header and
dashes; it prints PASS or each finding.

State on 26 Sep 2026 at 04:31 UTC, after the additions of section 2b: both PASS, `smoke_test.sh` with the counts of
section 1b in place, `scan_public_repo.sh` reading 95 files.

## What the runs check, and what they read live

Checked by sha256 against a manifest that ships with the repository:

| Input | Manifest | Checked by | If it differs |
|---|---|---|---|
| Documentation: the 44 challenge files, and the four strata tables the tools read | `documentation/INPUTS_MANIFEST.csv` | `pipeline.py --check` (the 44 files), `tools/scorecard_ratios.py` (the strata tables) | stops before building |
| Documentation: the PROJ 9.5.1 source tarball | its sha256 in `tools/build_proj_fma.sh` | `tools/build_proj_fma.sh` | stops |
| Discovery: the nine challenge layers | `discovery/INPUTS_MANIFEST.csv` | step 0b, `fetch_challenge.py`: every copy with `--data-dir`; from the cache, each file it downloads, and cached files with `--verify` | stops |
| Discovery: the Overture extra road classes (`work/extra_segments.parquet`, 577,230,247 bytes, downloaded from Overture's S3 bucket) | `discovery/INPUTS_MANIFEST.csv` | step 0e, `fetch_overture_extra.py`: after a download, or `--check` on an existing file | reported, and the run goes on: DuckDB can write the same rows as different bytes, so the result hashes of section 2 are the test |
| Discovery: the 90 NOAA Storm Events files (337 MB) | `results/ncei/ncei_manifest.json` | step 28, `ncei_events.py`, which downloads only the files missing from `raw/ncei/` (or `NCEI_DIR`) | stops; `--refresh` takes NCEI's current files, and the numbers may then change |

Shipped in the repository, so git keeps them intact: the crossing inventories of 24 Sep and the OSM tags of 23 Sep
(`discovery/inputs/`, each file's sha256 in its README) and the imagery audit's sample and two readings
(`results/audit/`, sha256 in section 2; `audit_summary.py` stops if the sample a run draws differs from
`audit_sample.csv`).

Read live and not checked by hash:

- the 2020 Census blocks from TIGERweb (`block_pop.py`, `block_pop_v4.py`, `occupancy.py`), queried at run time. The
  blocks do not change; any difference would show in the result hashes of section 2, and `occupancy.py` records the
  time of its queries;
- the DuckDB extensions `httpfs` and `spatial`, installed on first use from the DuckDB extension repository;
- USGS orthoimagery, only for optional images (section 3, `imagery_check.py`, `nearmiss_imgs.py`,
  `nearmiss_sample.py`), never for a number;
- with `LWC_SOURCE=live`, today's crossing inventories (retrieval time and sha256 logged in `raw/retrieval_log.json`,
  not compared), and with `OSM_PBF`, an OpenStreetMap extract of your own.

## 1. Documentation entry (run from `documentation/`)

**Inputs.** `pipeline.py` reads 44 challenge files, listed with size and sha256 in `documentation/INPUTS_MANIFEST.csv`
(plus the four strata tables the tools read). On 25 Sep 2026 the organisers removed the TIGER roads, Microsoft
footprints, USGS facility and CBP layers from the bucket; on 26 Sep 2026 at 01:06 UTC those 24 files returned HTTP 404,
and the other 20 and the strata tables had the manifest's size and S3 ETag. So DIR below is a folder holding all 44
(names as in the bucket or as in `cache/`: `documentation/README.md`); without `--data-dir` the pipeline reads `cache/`.

**1a. The scored column.** 181 s on 26 Sep with the inputs in DIR, 5 s of it checking them against the manifest (186 s
on 25 Sep from `cache/`, peak memory 2.6 GB).

    python pipeline.py --check --data-dir DIR

Expected: `inputs verified: 44 files, 4,963,212,120 bytes, every size and sha256 as in INPUTS_MANIFEST.csv`,
`README counts reproduced: scored rows 591 / 1,192 / 1,593 / 6,003, no road component 218 / 253 / 869 / 1,704`,
`undefined components: road 3044, building 6, POI 32`, `9379 rows, all-tract mean 0.058437`, and

    sha256 40aea8185bdf0aa7b2653d237581e6cb8adfa3df59de4a15b1ec06fcc5f7c289

(the file scored as submission 1S1Ei46w). Per region the log counts, in order northern-ca, eastern-ok, maricopa-az,
south-central-tx: Overture named-highway segments 26,050 / 59,436 / 57,516 / 353,790; TIGER 996 / 5,721 / 1,126 /
11,429; Overture footprints 1,164,724 / 2,551,694 / 2,908,224 / 11,463,801; Microsoft footprints 1,138,335 /
2,404,448 / 2,610,544 / 10,619,119; places 116,897 / 207,369 / 300,046 / 1,300,334. In south-central-tx it lists the
7 water tracts the organisers dropped.

**1b. Every alternative convention.** 1,098 s on 26 Sep (1,131 s on 25 Sep, peak 2.9 GB); writes
`out/counts.parquet`, which the discovery also needs. The scored file is unchanged: same sha256 as 1a.

    python pipeline.py --check --extra --data-dir DIR
    python sensitivity.py --error 0.00000301

Expected: 19 variants in `out/sensitivity.csv` (written in half a second), sha256
`cb75545a6e33c37f93cc6dfcdd655635a9d5cdfc5ac390d6b31e301dbd1107f2`, matching the tables in sections 6 and 7 of
`WRITEUP.md` (for example the midpoint rule moves 3,927 tracts, mean change 0.0359, largest 0.444).

**1c. The reference's arithmetic** (Linux on x86-64 with FMA; needs cmake, a C++ compiler and sqlite3; the build
took 100 s on 25 Sep and 207 s on 26 Sep, download included; the fused run 184 s):

    bash tools/build_proj_fma.sh
    PYTHONPATH=proj_fma python tools/fingerprint.py
    PYTHONPATH=proj_fma python pipeline.py --check --data-dir DIR

Expected: the build checks the PROJ 9.5.1 tarball's sha256; the fingerprint reads `800570.8529844118` (fused
multiply-add; the plain wheel reads `800570.8529844111`); the output sha256 is

    30110feb61ee848973a9b7543741c7d586fdf850e26da3854816cd26e2486908

(the file that scored exactly 0, submission RkEkksFb). Then the arithmetic row of the sensitivity table (the run
under the fused build took 185 s, peak 2.6 GB):

    BIAS_OUT=out_fma PYTHONPATH=proj_fma python pipeline.py --check --data-dir DIR --out submission_fma.csv
    python sensitivity.py --error 0.00000301 --arith out_fma/counts.parquet

Expected last line: `arithmetic ... 21 tracts  mean 1.628e-06  max 3.841e-03`. The control build,
`FLAGS="-O2 -mno-fma -ffp-contract=off" OUT=proj_nofma bash tools/build_proj_fma.sh`, should read `800570.8529844111`
and reproduce the sha256 of 1a.

**1d. The three later tools.** After 1b:

    BIAS_DATA_DIR=DIR python tools/extra_variants.py --error 0.00000301
    BIAS_DATA_DIR=DIR python tools/scorecard_ratios.py
    python tools/acceptance_window.py out/counts.parquet

`extra_variants.py` took 589 s on 26 Sep (495 s on 25 Sep, before it also took each centroid in EPSG:5070; peak
2.4 GB). Expected: `control passed; centroid taken in EPSG:5070 changes the count in 0 tracts` for both building
layers in all four regions; TIGER byte-identical geometry repeats of 8.8475%, 10.1074%, 6.9040% and 7.1236% of
named-highway length; `CRS spelling: 9,462,710 projected coordinates compared, 0 differ in any bit`;
`USGS facilities exactly on a tract boundary: 0; building centroids exactly on a tract boundary: 0`; eight table
lines from `TIGER records with byte-identical geometry kept once  1283 tracts  mean 5.726e-03  max 2.300e-01  ruled out  tribal 2.886`
to `permanently closed places left out  213 tracts  mean 5.199e-04  max 2.500e-01  ruled out  tribal 2.876`; and
`out/sensitivity_v4.csv` with sha256 `4b429f7690a302ec23674767cd6a700109143af0217abb696b6606504ae7a084`.

`scorecard_ratios.py` takes a second or two. Expected, after `inputs verified: 4 files, 4,587,505 bytes`:

    ratio                                     in   out   scored  midpoint   change
    SVI above vs below median               4647  4647   1.2445    1.1629  -0.0817
    CVI above vs below median               4688  4689   1.5775    1.4263  -0.1511
    tribal vs non-tribal                     858  8521   2.9012    2.6107  -0.2905
    legally-defined tribal vs non-tribal      64  9315   2.3307    2.4842  +0.1535

then the four ratios under all 19 variants of `sensitivity.py`, and `out/scorecard_ratios.csv` with sha256
`0e430893a70ecf8502f26e053c62be459c078826c7bbc90958b6696153a1808d`.

`acceptance_window.py` takes about a second. Expected:

    out/counts.parquet
      transport_gap        sum 1048.3122362295   window [1048.2955, 1048.3049]   above by 0.0073
      building_gap         sum 52.5301969502   window [52.5271, 52.5365]   inside
      poi_gap              sum 482.2154991143   window [482.2072, 482.2166]   inside
      coverage_gap_score   sum 548.0809320000   window [548.0666, 548.0759]   above by 0.0050

**1e. Missing or altered inputs** (26 Sep; each stops before any output is written, with exit status 1):
`--data-dir` pointing at a folder without the 24 removed files names all 24 and says how to supply them; a folder where
one file differs (an EMS layer replaced by a fire-station layer) names that file with both sizes and sha256 values;
`python pipeline.py --check` with an empty `cache/` names the 24 removed files and downloads nothing. A folder in any
of the accepted layouts (the bucket's tree, one folder per region, all in one folder, or `cache/`'s names) resolves
all 48 manifest files.

## 2. Discovery entry (run from `discovery/`, after 1b)

    bash run_all.sh --data-dir DIR

DIR holds copies of the nine Texas challenge layers the discovery reads, made before the organisers removed five of
them from the bucket on 25 Sep 2026 (the Microsoft footprints, the TIGER roads and the fire station, EMS station and
school layers); `discovery/INPUTS_MANIFEST.csv` lists all nine with size and sha256, and step 0b checks the copies
against it before anything else runs. On 26 Sep at 01:19 UTC those five returned HTTP 404 from the bucket and the
other four had the manifest's sizes. Without `--data-dir` the run reads the shared cache and stops at step 0b, naming
the missing files, if the five are not there. The run downloads 577 MB of Overture roads (release 2026-08-19.0,
while Overture keeps it online; 263 s on 25 Sep and 256 s on 26 Sep, both times byte for byte the file of 24 Sep),
then queries the Census Bureau's TIGERweb for 2020 blocks. The run of 25 Sep took 1,409 s in all (peak memory
4.4 GB): 263 s of download, about 500 s of TIGERweb queries (`block_pop.py` 200 s, `block_pop_v4.py` 303 s) and about
650 s of analysis. On 26 Sep, from local copies in a clean folder with an empty cache, it took 1,278 s with the
Overture roads already downloaded (peak memory 4.4 GB, on a machine shared with other jobs), steps 24 to 27 included.
It writes about 1.1 GB to `work/`. Step 28, added later that day, then checks the 90 NOAA files and downloads any that
are missing (337 MB, 96 s on 26 Sep) and runs in 47 s (section 2b). Lines to expect:

- challenge (with `--data-dir`): nine `ok` lines, then `all 9 layers are in DIR, each matching INPUTS_MANIFEST.csv`
- overture_extra (file already there): `work/extra_segments.parquet: 577,230,247 bytes, sha256 as in
  INPUTS_MANIFEST.csv (the file the entry read)`

- prepare: `records 17661 in region tracts 14655`, `TWDB records within 50 m of a TxGIO record: 6974 of 9322`,
  `tracts with >=1 crossing: 1892`
- overture: `segments scanned 1937009 pairs 37760 crossings with any segment within 100 m 13942 of 14655`
- attribute: `unique crossings in region: 8454`, `segment within 30 m: 7868 (93.1%)`,
  `name-verified within 100 m: 6236 (84.6%)  median distance of verified: 2.5`, `attributed to an Overture segment: 7940`
- osm_eval: `official crossings with an OSM ford/flood tag within 30 m: 353 of 8454 (4.2%)`, `401 of 7940`
- graph (first build only): `built graph 2741215 nodes 3262198 edges` (base), `built graph 7297800 nodes 8522268 edges` (plus)
- buildings plus strict: `buildings stranded 37270 people 50244 groups with buildings 739 | single crossing: groups 224 buildings 7646 people 11899`
- tiger single: `{'agrees_isolated': 95, 'tiger_has_other_way': 41, 'mixed': 13, 'crossing_road_not_in_tiger': 2}`;
  multi: `{'agrees_isolated': 135, 'tiger_has_other_way': 35, 'mixed': 5, 'crossing_road_not_in_tiger': 5}` (230 of 331)
- blocks: `buildings 37270 people (tract ratio) 50244 people (block) 43573 homes (block HU) 18490`
- core: `work/core_numbers.json` with areas 216, buildings 22469, residents_block 26257, homes_block 11236, tracts 162,
  counties 49, single_areas 90, single_buildings 5549, pct_rural_residents 68.9, svi_core 0.47 against svi_region 0.57,
  cvi_ee_core 0.6 against cvi_ee_region 0.51
- blocks for all six versions: `== base all: buildings 68155, located 68155, residents (block) 78327.5, homes 34233.7`,
  `failed fetches: []` and `check vs block_pop.py (plus strict): max |d residents| 1.36...e-11 ... located differs in 0 areas`
- variants: the careful set's row (216 areas, 22,469 buildings, 90 single-crossing areas with 5,549 buildings, 26,257
  residents, 11,236 homes) and `inconsistencies vs variants_table.csv: none`
- audit: `verdicts: 40 areas; images cited: 164` (the sample drawn equals `../results/audit/audit_sample.csv`, or the
  step stops), then from `audit_agreement.py`: `two readings of 40 areas: same verdict in 24 (kappa 0.366); both settle
  12, agree on 11 of them (kappa 0.824)`, `cut off among the areas each settles: reading 1 11 of 20 (55.0%, Wilson
  34.2% to 74.2%); reading 2 5 of 19 (26.3%, Wilson 11.8% to 48.8%)` and `building-weighted: reading 1 14,426, reading 2
  5,067 of 22,469 buildings; wrote work/v4_audit_agreement.json`
- `work/discovery_numbers_v4.json`: among others the rural and urban rates 147.12 and 14.11 crossings per 100,000
  residents (ratio 10.428, tract cluster bootstrap 8.581 to 12.73), the first reading's precision, 11 of 20 settled
  areas (Wilson 0.3421 to 0.7418), and imagery-adjusted buildings, 14,426 (bootstrap 8,034 to 20,164), which
  `work/v4_audit_agreement.json` sets beside the second reading's 5 of 19 (0.1181 to 0.4879) and 5,067 buildings, and
  TIGER reach none in 153 of the 216 areas
- facilities (about 75 s, peak 1.7 GB): `footprints within 300 m of a cut-off piece: 57,120`, then the check
  `'careful_buildings_reference': 22469, 'reassigned_same_area': 22469, 'reference_only': 0, 'rule_only': 0,
  'different_area': 0` with `'lead_version_reassigned_same_area': 37268, 'lead_version_ties': 2`, and the summary
  `"usgs_hifld": {"fire station": 5, "EMS station": 0, "school": 1}, "usgs_hifld_areas": 5` and
  `"overture_places": {"fire station": 5, "EMS station": 0, "school": 4}`
- occupancy: the table in `work/v5_occupancy.txt`, with `careful set (216)  22,469  26,256.7  11,236.0  0.43  2.34`
  and `region, all tracts  25,758,569  10,173,613  0.40  2.53` (columns abridged)
- by_tract: `{'Bexar': 2, 'Johnson': 1, 'Guadalupe': 1, 'Hays': 1, 'Bee': 1, 'Kerr': 1} tracts per place`
- ncei (step 28): `90 NCEI files verified against raw/ncei/ncei_manifest.json`, `region events 12981 (flash flood 11496,
  flood 1485), deaths 550, injuries 6945`, `low-water-crossing events 738, deaths 43, injuries 155`, `confirmed: events
  128, crossings 112, deaths 21; ordinary-road crossings 56; careful set 6`, `ambiguous: pairs 1464, events 615`,
  `vehicle share {'fatality_rows': 549, 'vehicle_rows': 259, 'vehicle_share_pct': 47.2}` and `wrote ../results/ncei:
  ncei_events_region.csv 12,981 rows (without ncei_url and source_file), ncei_crossing_matches.csv 1,598 rows (1 of the
  669 reports behind it name a person; 0 excerpts changed), ncei_summary.json, ncei_manifest.json`. The confirmed and
  vehicle lines cover every confirmed match and every year; the entry quotes the fatal subset
  (`matches.fatal_at_named_crossing` in `ncei_summary.json`: 16 events, 20 deaths) and 1996 to 2019 (225 of 386)

`run_all.sh` rewrites `../results/` in place (steps 23 and 28), so in a git checkout `git status --short ../results`
lists any shipped file a rerun changed. On 25 Sep none changed, and on 26 Sep, from local copies, none changed either;
the values below are the files as they now ship, after the additions of section 2b:

| File | sha256 |
|---|---|
| `results/crossings.csv` | `e553a39c6768af655de0b62a7c474cafac08a634ca0e72aacbfb8c3b795e2c7e` |
| `results/areas.csv` | `68c431a41d140463e7c33023fcd7e0bd6fdbdce1ff35941eeed6b8db6eaf409f` |
| `results/careful_tracts.csv` | `d487b4489cf40fd4996657ee75e177bd4c0b39e06ee6c5aeb9b9e93d061f6fbf` |
| `results/crossing_tracts.csv` | `1a404adf029a83538b2c2d3b50b1c95f563916950c31b9c06c651faf6f2c6bd8` |
| `results/variants.csv` | `9614e11d9a19c2493117d6e8217f560b2f082b687c15ea221944f432b773a09c` |
| `results/core_numbers.json` | `47ae78b903c0d2a70d1b5ae308138f07a492ae340fd3b46b5ee4c3387419a90b` |
| `results/figures/v4_region_map.png` | `a2d0bd3bcbfc3df67150bd828a2c2598a3814e537c79fbc7adeca975a8afc81a` |
| `results/figures/v4_bexar_979.png` | `28d547c9fee48e9c3031d77776afc01be5e032f929d9930b844f16c022575f37` |
| `results/ncei/ncei_manifest.json` | `c0c0921e87ea11a0840563eba459d55c7ccf8221fcfc24356adb06b723c9599b` |
| `results/ncei/ncei_summary.json` | `163981fadf1c2e727577c9fd91f3f6a17cd5b446ab1767ebc70d4199870481ed` |
| `results/ncei/ncei_events_region.csv` | `63f10c1cd5eb36f3756e0de533e9c741ebea28f3c72249fe67dddc13b697cde9` |
| `results/ncei/ncei_crossing_matches.csv` | `9c42663b7a205241a96147a9d3d76aabf9b4db2967bdcb45835e5ed071a6024c` |
| `discovery/work/core_numbers.json` | `40fa342a10ebe410fff35cc8d43d3b42f9786b6268f4306039b119fd7f174850` |
| `discovery/work/examples_confirmed.csv` | `f3828ca87b3b3bb0b93a74f3be12ba2d438aae8a26c492eb59082a86a68f70bc` |
| `discovery/work/report_who.json` | `4fd2d1f25790d83d4bdd7b79d862eb72a3755ffa19b60625963e84fe19b82547` |
| `discovery/work/variants_table.csv` | `cf4c61aef1dd84ddc182656635d18c05722e64b659c87a6c43544d3ba1665ce8` |
| `discovery/work/discovery_numbers_v4.json` | `79b99dbf9643c65f651e40888f5a9c31aa2d4d1f01b0386f05fc323eb3b9ec85` |
| `discovery/work/v4_audit_agreement.json` | `cbe8a511287681ef420afa9fa8510444df1ce101cdf99ebb421cd6f5a0de5aba` |
| `discovery/work/ncei_events_region.csv` | `5598deb9c5fbc58a366ee321e524d0bb93c742caf34fbc7efbaac0692b03bd20` |
| `discovery/work/ncei_crossing_matches.csv` | `9c42663b7a205241a96147a9d3d76aabf9b4db2967bdcb45835e5ed071a6024c` |
| `discovery/work/ncei_summary.json` | `163981fadf1c2e727577c9fd91f3f6a17cd5b446ab1767ebc70d4199870481ed` |
| `discovery/work/v5_facilities.json` | `787dde06c434bf9b3d7045ab1363a1a0c953a93fa8802a933285fbbbdc21fcf1` |
| `discovery/work/v5_facilities_candidates.csv` | `fc79aab0fe8fbafad8f5eb196846bb9c23ca0501f96588159b18d110ca967892` |
| `discovery/work/v5_occupancy.txt` | `53f5b20d0933b03133301a6311114bdc97d39dd7cd15a973e25204bc83a3829d` |
| `discovery/work/v5_example_tracts.csv` | `8ec89b5c7107e7190227ab9a61f1b62d4d9eeb84e85ad5db1234da03cc171394` |
| `discovery/work/v5_example_tracts.txt` | `b65a885e1ca0ff2ce70ef31f638591ac0c3ee737323c39425be9d03d3ba5648a` |

The first four `discovery/work/` files are byte for byte the original run's. `work/discovery_numbers.json` matches
the original in every value but one, `T_OVT`, the time the Overture roads were downloaded (the original file,
sha256 `60705a38372c53cdfd2533866952ad71dc1fbc3089934a0b92dc1cfd4c219a2f`, carries 24 Sep). Every number in
`work/discovery_numbers_v4.json` equals the original analysis's; this repository's version of the file leaves out
the original's checks against the entry's text and names `work/bias_components.parquet` as the road-gap source, so
its hash is its own. Of the later steps' own files in `work/` and `figs/` (`v4_*`), all came out byte for byte as in
the original run except two that differ in text only: `v4_flood_attr_gap.json` (that source's name) and
`v4_who.json` (the wording of one note); the figures have since been redrawn with reworded legends (section 2b), so
the table gives their new sha256 and that of `discovery_numbers_v4.json`, which records them. If a live source ever
changes (the Overture release, or TIGERweb's Census blocks), these hashes are where it will show. The five `v5_` rows
(steps 24 to 26) are from the entry's run of 26 Sep and were reproduced byte for byte by the run from local copies the
same day; `work/v5_occupancy.json`, `work/v5_tigerweb_tract_sums.json` and `work/discovery_numbers_v5.json` also carry
the time of the TIGERweb query, so only their values repeat.

The shipped records the run reads but never writes: `results/audit/audit_sample.csv`
`02e8eae6a851967b745aff9bad67d98ffd894fd117b8b04f57c4d2bfd2ef6aaf`, `audit_verdicts.csv`
`36dcc65bcbc1ba60325841f0a4e9d3f1029210b2662410fa4fac991d906eb89a`, `second_rater.csv`
`0649fde16008a926372d2fd6ef96a3a9b23106274fb80d4923f5d0c0db3f276d`, `agreement_summary.md`
`b72c0d6fdf2d0b39a6ba0b71791094640a0b603b364f4ee8b8a0525307ab4316` and `extra_views.csv`
`c9652a2b5167e4ce14921b9500d1fbbddfefb973b2510610d3ea0e5d837ea915`.

`python join_strata.py` then adds strata columns to the result tables in `work/joined/`; on 25 Sep the SVI it joined
to `careful_tracts.csv` equalled, in all 162 rows, the `svi` column that `per_tract_table.py` writes to `work/`.

## 2b. What was added on 26 Sep 2026, checked on its own

These came after the full runs above and were checked from the `work/` folder of the run of 26 Sep (same machine type,
same virtual environment), with the challenge layers from local copies:

- **Step 28.** `NCEI_DIR=DIR python ncei_events.py`, with DIR holding the 90 NOAA files the entry downloaded on 26 Sep
  between 00:51 and 00:53 UTC (96 s): 47 s, peak memory 1.2 GB. `work/ncei_events_region.csv`,
  `work/ncei_crossing_matches.csv` and `work/ncei_summary.json` came out byte for byte as the entry's own run, twice,
  and `raw/ncei/ncei_manifest.json` as the manifest shipped. With one file missing from DIR, the step downloaded it
  from NCEI and it matched its sha256; with one file altered, it stopped with exit status 1, naming the file and both
  sha256 values.
- **The two readings of the imagery audit.** `python audit_agreement.py` gives every figure of
  `results/audit/agreement_summary.md` and the building-weighted counts of both readings (14,426 and 5,067), the same
  file twice.
- **The Overture extra road classes.** `python fetch_overture_extra.py --check`: the file downloaded on 24 Sep matches
  its row in `INPUTS_MANIFEST.csv`.
- **The figures.** Their legends now read "no mapped road out" (region map) and "no mapped way out" (Bexar), and the
  Bexar panel gives both readings of the imagery for area 979. `python figures.py` drew both files twice with the same
  bytes; against the earlier files (sha256 `08109c6d...` and `94c29668...`) only pixels of the reworded text changed.
  `python numbers_v4.py` then wrote `work/discovery_numbers_v4.json`, which differs from its earlier version
  (`02dcc6e8...`) only in the two figure hashes it records, and `python export_results.py` wrote every table in
  `results/` byte for byte as shipped.

## 3. The imagery audit's images (optional, network)

    AUDIT_IMAGES=1 bash run_all.sh

or, after a run, the three steps on their own:

    python precision_audit.py prep
    python precision_audit.py render
    python precision_audit.py extras

On 25 Sep the three steps took 529 s (peak 1.6 GB, one imagery request retried) and wrote all 164 images the
verdicts cite, about 83 MB, into `figs_audit/`. 155 of them came out byte for byte as the images the two readings
looked at, and `work/v4_audit_prep.parquet` and `work/v4_audit_render.csv` as in the original run. The other 9 are extra
close-ups whose centres had more decimal places than the 5 their image titles show, which is what `extra_views.csv`
records; they differ from the originals by 1.7 to 3.6 grey levels in 255 on average, a shift of under a metre.

Optional, with network for the imagery: `FIGURES=1 bash run_all.sh` draws `figs/example_*.png` for the six named
places; `python imagery_check.py 979 623 921 952 1030 266` puts USGS imagery under them.

After any change: `bash smoke_test.sh` and `bash scan_public_repo.sh` again.
