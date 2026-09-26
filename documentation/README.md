# Coverage gap score, Bias Bounty Mapping Equity Challenge

The pipeline behind my scored column in Zindi's Bias Bounty Mapping Equity Challenge, and the
measurements behind Part 1 of my writeup on the competition's discussion board (the methodology, for Best
Documentation).

Author: Peter Tinashe Mundowa (Zindi: PeterTheAnalyst).

The writeup itself, one post in two parts, with its tables rendered and the detail the forum post leaves out, is
[../WRITEUP.md](../WRITEUP.md). The repository's front page, [../README.md](../README.md), covers both parts.
Every command below runs from this folder.

## The inputs, and the change of 25 September 2026

`pipeline.py` reads 44 challenge files: per region, the tract polygons, the sample submission, the Overture roads,
buildings and places, the TIGER roads, the Microsoft footprints, the three USGS facility layers and the CBP
establishments. [INPUTS_MANIFEST.csv](INPUTS_MANIFEST.csv) lists each with its region, size and sha256, plus the four
strata tables that only `tools/extra_variants.py` and `tools/scorecard_ratios.py` read:

| column | meaning |
|---|---|
| `file` | the file's name in the bucket, under `reference/REGION/` or `strata/REGION/` |
| `region`, `bytes`, `sha256` | the copy every result in the entry was built from |
| `read_by` | `pipeline.py` for the 44 inputs of the scored column, `tools` for the strata tables |
| `bucket_2026_09_26` | `present`: the bucket served the same size and S3 ETag on 26 September 2026; `removed`: HTTP 404 |

On 25 September 2026 the bucket's README gained this line: "TIGER/Line roads, Microsoft building footprints, HIFLD
facilities and CBP establishments were removed from every region at the challenge organizers' request." So 24 of the
44 inputs can no longer be downloaded. The other 20, and the strata tables, are still in the bucket, unchanged. The
organisers hold the removed files; their public sources are:

| layer | source |
|---|---|
| TIGER/Line 2025 roads | https://www2.census.gov/geo/tiger/TIGER2025/ROADS/ |
| Microsoft GlobalML Building Footprints (February 2026 refresh, per the challenge README) | https://github.com/microsoft/GlobalMLBuildingFootprints |
| USGS National Map structures (the facility layers, named `hifld`) | https://carto.nationalmap.gov/arcgis/rest/services/structures/MapServer |
| County Business Patterns | https://www.census.gov/programs-surveys/cbp.html |
| HUD USPS ZIP crosswalk (CBP from ZIP to tract) | https://www.huduser.gov/portal/datasets/usps_crosswalk.html |

The challenge cut these layers to each region (and apportioned CBP to tracts), so a rebuild from the sources is not
guaranteed to give the same bytes, and I have not tested one. The manifest says whether a copy is the right one.

With `--data-dir DIR`, `pipeline.py` reads every input from `DIR` and downloads nothing. `DIR` may hold the files
under the bucket's names, in any of these layouts, or under the names this folder's `cache/` uses:

    DIR/reference/REGION/FILE and DIR/strata/REGION/FILE     the bucket's own tree (aws s3 sync of both folders)
    DIR/REGION/FILE                                          one folder per region
    DIR/FILE                                                 all in one folder
    DIR/reference__REGION__FILE and DIR/strata__REGION__FILE the names in cache/

It checks that all 44 are there before any work and, with `--check`, that each has the manifest's size and sha256,
and stops with the list of files that are missing or differ. `BIAS_DATA_DIR=DIR` does the same for the tools. Without
`--data-dir`, the pipeline uses `cache/`, downloads what is missing and still in the bucket, and stops before any work
if a removed layer is not already in `cache/`.

## Run it

    pip install -r requirements.txt
    python pipeline.py --check --data-dir DIR

It checks the inputs against the manifest, builds all four regions, writes `submission.csv` (9,379 rows, GEOID and
coverage_gap_score), asserts the counts the bucket README publishes, and prints the sha256 of the file:
`40aea8185bdf0aa7b2653d237581e6cb8adfa3df59de4a15b1ec06fcc5f7c289`, the file scored as 1S1Ei46w (public error
0.00000301). Under 4 minutes on 2 cores. No model, no random seed, no manual step, and no score file is read.

## The last 0.00000301: projection arithmetic

The remaining error is not a convention. A few highway pieces lie exactly on tract boundaries, and after projection
to EPSG:5070 the last bit of the arithmetic decides which side they fall on. The reference was built with fused
multiply-add, which compilers use by default for ARM processors. To get that arithmetic on an Intel or AMD machine
running Linux:

    bash tools/build_proj_fma.sh
    PYTHONPATH=proj_fma python pipeline.py --check --data-dir DIR

The script downloads PROJ 9.5.1, checks its sha256, builds it with `-mfma` (about 2 minutes on 2 cores; needs cmake,
a C++ compiler and sqlite3) and lays it over the installed pyproj wheel in `./proj_fma`. Output sha256:
`30110feb61ee848973a9b7543741c7d586fdf850e26da3854816cd26e2486908`. That file scored exactly 0 on the public board
(submission RkEkksFb, 24 September 2026).

`python tools/fingerprint.py` tells you which arithmetic your Python is using before you spend four minutes on a run.

## Measure the open choices

    python pipeline.py --check --extra --data-dir DIR
    python sensitivity.py --error 0.00000301

`--extra` also counts every alternative convention the writeup measures and saves the per-tract counts to
`out/counts.parquet` (about 18 minutes). `sensitivity.py` then rebuilds the writeup's sensitivity tables from those
counts in under a second: each line changes one convention, recomputes all 9,379 values, and reports the tracts that
move, the mean absolute change and the largest change. For the arithmetic row, add a second run under the FMA build:

    BIAS_OUT=out_fma PYTHONPATH=proj_fma python pipeline.py --check --data-dir DIR --out submission_fma.csv
    python sensitivity.py --error 0.00000301 --arith out_fma/counts.parquet

The low-water-crossing analysis in `../discovery/` reads the same `out/counts.parquet`, so run the `--extra` build
before it.

## Three more tools

    BIAS_DATA_DIR=DIR python tools/extra_variants.py --error 0.00000301
    BIAS_DATA_DIR=DIR python tools/scorecard_ratios.py
    python tools/acceptance_window.py out/counts.parquet

`extra_variants.py` measures the lines of the sensitivity table that need geometry again (TIGER's duplicate
geometries, the source CRS spelling, point on surface, facilities and centroids with intersects, a boundary place
counted once, permanently closed places), the same way `sensitivity.py` does, after asserting that every base count
it recomputes equals `out/counts.parquet`. About 10 minutes; it writes `out/sensitivity_v4.csv` and
`out/counts_v4.parquet`, and prints the scorecard's tribal ratio under each line.

`scorecard_ratios.py` recomputes four scorecard-style ratios from the composite as written (6 decimal places): social
and climate vulnerability above against below the median (`svi_overall`, `cvi_overall`, tracts with no value left
out), tribal against non-tribal (`tribal_any`, the definition that gives this column the scorecard's 2.90) and
legally-defined tribal against the rest (`tribal_legal`). It prints the scored build against the whole-segment midpoint
rule, then all four ratios under every variant of `sensitivity.py`, and writes `out/scorecard_ratios.csv`. It checks
the strata tables against the manifest first and takes a second or two.

`acceptance_window.py` sums each score column of the scored build and checks it against the window the Data page's
sample-submission constants allow, read as column means over all 9,379 tracts rounded to 6 decimals (the constants
are written into the script: check them against your copy of SampleSubmission.csv).

## The four conventions that decide the scored column

They sit in the `CONV` dictionary at the top of `pipeline.py`:

| key | value used | alternative |
|---|---|---|
| `road_assignment` | `clip`: split every segment at tract boundaries in EPSG:5070 | `midpoint` |
| `building_point` | `centroid`: the true polygon centroid | `bbox` |
| `place_predicate` | `intersects`: a place on a boundary counts in every tract it touches | `within` |
| `output_decimals` | `6`, the precision the reference is stored at | `None` |

## Machine

Tested on Python 3.11.15, 2 cores, 8 GB of memory, on two different machines with the same bytes out. The building
layers are read one parquet row group at a time, so the largest region never holds a whole layer in memory: the
largest process peaked at 2.9 GB (the `--extra` run). Measured times and outputs: [../TESTING.md](../TESTING.md).

## Data

The inputs are the challenge's files from https://data.source.coop/humane-intelligence/bias-bounty-mapping-equity-challenge/ ,
shared by the organisers under CC BY-SA 4.0; each layer also keeps its source's terms
([../DATA_LICENCES.md](../DATA_LICENCES.md)). Nothing here redistributes them: they stay in `cache/` or in your own
folder, and neither is ever committed. This folder holds only their sizes and sha256 values.

## Credit

The projection-arithmetic explanation was first published by the Zindi user wangwu (thread 34972, 23 September 2026),
who reproduced the reference on arm64. The FMA build here is my independent check of it on x86. Every other idea I
took from another entrant is credited in [../WRITEUP.md](../WRITEUP.md), with the full dated list in its appendix D.

## Licence

MIT, for the code in this repository (see [../LICENSE](../LICENSE)).
