#!/usr/bin/env bash
# The low-water-crossing discovery, from inputs to the result tables, in order:
#
#     bash run_all.sh
#
# Before it, run the documentation pipeline once with --extra: it writes ../documentation/out/counts.parquet, which
# scorecard_inputs.py reads, and it fills the challenge-data cache this run shares (see README.md).
#
#     bash run_all.sh --data-dir DIR               read the challenge layers from local copies in DIR and download
#                                                  none of them (the same as BIAS_DATA_DIR=DIR). Needed since
#                                                  25 Sep 2026, when the organisers removed the Microsoft footprints,
#                                                  TIGER roads and facility layers from their bucket: see README.md
#                                                  and INPUTS_MANIFEST.csv (size and sha256 of every layer read here)
#     LWC_SOURCE=live bash run_all.sh              download today's crossing inventories instead of using the
#                                                  snapshot of 24 Sep 2026 that the entry's numbers come from
#     OSM_PBF=raw/texas.osm.pbf bash run_all.sh    read the OSM tags from a Texas extract instead of the shipped tables
#     NCEI_DIR=DIR bash run_all.sh                 read the 90 NOAA Storm Events files of step 28 from DIR (any missing
#                                                  file is downloaded into DIR); default raw/ncei/
#     NCEI=0 bash run_all.sh                       skip step 28, the NOAA Storm Events step
#     FIGURES=1 bash run_all.sh                    also draw the maps of the six named places
#     AUDIT_IMAGES=1 bash run_all.sh               also re-render the imagery audit's 164 images into figs_audit/
#                                                  (USGS imagery, about 85 MB; never committed)
#
# Downloads run only when their output is missing, except the two small snapshot copies, which always run. Every
# download that has a pinned version is checked against it: the challenge layers and the Overture extra classes
# against INPUTS_MANIFEST.csv, the NOAA files against ../results/ncei/ncei_manifest.json (see ../TESTING.md).
# On 2 cores and 8 GB the clean run of 25 Sep 2026 took 1,409 s (peak memory 4.4 GB): 263 s downloading 577 MB of
# Overture roads, about 500 s of TIGERweb queries for Census blocks (block_pop.py, block_pop_v4.py) and about 650 s
# of analysis. Step 28 was added on 26 Sep 2026: about 100 s to download 337 MB of NOAA files, then about 1 minute.
set -euo pipefail
if [ "${1:-}" = "--data-dir" ]; then
  [ -n "${2:-}" ] || { echo "run_all.sh: --data-dir needs a folder" >&2; exit 2; }
  BIAS_DATA_DIR="$2"; shift 2
fi
[ $# -eq 0 ] || { echo "run_all.sh: unknown argument $1 (only --data-dir DIR; options are environment variables, see the top of this file)" >&2; exit 2; }
if [ -n "${BIAS_DATA_DIR:-}" ]; then                       # made absolute before the cd below
  [ -d "$BIAS_DATA_DIR" ] || { echo "run_all.sh: $BIAS_DATA_DIR is not a folder" >&2; exit 2; }
  BIAS_DATA_DIR="$(cd "$BIAS_DATA_DIR" && pwd)"; export BIAS_DATA_DIR
  echo "challenge layers from local copies in $BIAS_DATA_DIR (nothing downloaded from the bucket)"
fi
if [ -n "${NCEI_DIR:-}" ]; then                            # made absolute before the cd below, created if new
  mkdir -p "$NCEI_DIR" && NCEI_DIR="$(cd "$NCEI_DIR" && pwd)"; export NCEI_DIR
fi
cd "$(dirname "$0")"
PY="${PYTHON:-python3}"
T0=$(date +%s)
step() { echo "== $1 $(date -u +%H:%M:%S)"; }

step scorecard;  "$PY" scorecard_inputs.py                  # fails at once, with the fix, if the --extra counts are missing
step challenge;  "$PY" fetch_challenge.py
step crossings
if [ "${LWC_SOURCE:-snapshot}" = "live" ]; then "$PY" fetch_lwc.py; else "$PY" fetch_lwc.py --snapshot inputs/lwc_2026-09-24; fi
step osm
if [ -n "${OSM_PBF:-}" ]; then "$PY" osm_fords.py --pbf "$OSM_PBF"; else "$PY" osm_fords.py --extract inputs/osm_2026-09-23; fi
step overture_extra                                          # an existing file is compared with INPUTS_MANIFEST.csv
if [ -f work/extra_segments.parquet ]; then "$PY" fetch_overture_extra.py --check; else "$PY" fetch_overture_extra.py; fi

step prepare;    "$PY" lwc_prepare.py
step overture;   "$PY" lwc_overture.py
step attribute;  "$PY" lwc_match_eval.py
step tracts;     "$PY" lwc_tracts.py                        # before osm_eval, which reads its output
step osm_eval;   "$PY" lwc_osm_eval.py
for n in base plus; do for v in all strict fords; do step "graph $n $v"; "$PY" lwc_graph.py $n $v; done; done
for n in base plus; do for v in all strict fords; do step "buildings $n $v"; "$PY" lwc_buildings.py $n $v; done; done
step tiger;      "$PY" tiger_check.py plus strict 10 single; "$PY" tiger_check.py plus strict 30 multi
step nearmiss;   "$PY" nearmiss.py plus strict
step blocks;     "$PY" block_pop.py plus strict              # residents and homes from Census blocks (network)
step stranded;   "$PY" stranded_segs.py plus strict
step who;        "$PY" report_who.py
step examples;   "$PY" examples.py
step numbers;    "$PY" disc_numbers.py
step core;       "$PY" core_numbers.py
step blocks_all; "$PY" block_pop_v4.py                      # residents and homes for all six versions (network)
step variants;   "$PY" variants_v4.py
step intervals;  "$PY" uncertainty.py
step flood_gap;  "$PY" flood_attr_gap.py
step who_more;   "$PY" who_v4.py
step per_tract;  "$PY" per_tract_table.py
step audit;      "$PY" precision_audit.py sample; "$PY" audit_summary.py   # checks the shipped verdicts against the run
"$PY" audit_agreement.py                                    # the two readings of the imagery audit compared
step figures_v4; "$PY" figures.py
step numbers_v4; "$PY" numbers_v4.py
step results;    "$PY" export_results.py
step facilities; "$PY" facilities.py                        # schools, fire and EMS stations inside the careful set's areas
step occupancy;  "$PY" occupancy.py                         # homes per resident (network: TIGERweb block sums, cached)
step by_tract;   "$PY" example_tracts.py                    # the six named places, tract by tract
step numbers_v5; "$PY" numbers_v5.py
if [ "${NCEI:-1}" != "0" ]; then
  step ncei;     "$PY" ncei_events.py                        # NOAA Storm Events: files checked against ../results/ncei/
fi                                                           # ncei_manifest.json; writes work/ncei_* and ../results/ncei/

# Later analysis steps go here, one line each, reading work/ and writing work/; above export_results.py if it ships
# their output.

if [ "${AUDIT_IMAGES:-0}" = "1" ]; then
  step audit_images; "$PY" precision_audit.py prep; "$PY" precision_audit.py render; "$PY" precision_audit.py extras
fi
if [ "${FIGURES:-0}" = "1" ]; then
  step figures;  "$PY" make_maps.py 979 623 921 952 1030 266  # Bexar, Johnson, Guadalupe, Hays, Bee, Kerr
fi
echo "total $(( $(date +%s) - T0 )) s"
