#!/usr/bin/env bash
# Light checks that need no download and little memory. Run them in the environment the two requirements files
# set up, after any change and before committing:
#
#     bash smoke_test.sh
#
# Every module compiles, every library imports, every script prints its --help (so its imports and argument parsing
# work), the shell scripts parse, the projection fingerprint prints, and the road-name matcher passes its self-test.
# When documentation/out/counts.parquet from `python pipeline.py --check --extra` is present, it also rebuilds the
# sensitivity table and the scored file from those counts, checks the file's sha256, and checks the column sums
# of the acceptance window. Full runs: TESTING.md.
set -uo pipefail
cd "$(dirname "$0")"
PY="${PYTHON:-python3}"
fail=0
ok() { echo "ok    $*"; }
no() { echo "FAIL  $*"; fail=1; }

"$PY" -m py_compile documentation/*.py documentation/tools/*.py discovery/*.py && ok "every module compiles" || no "compile"
"$PY" -c "import duckdb, geopandas, matplotlib, numpy, osmium, pandas, PIL, pyarrow, pyproj, scipy, shapely" \
  && ok "every library imports" || no "a library does not import: pip install -r documentation/requirements.txt -r discovery/requirements.txt"
for s in documentation/pipeline.py documentation/sensitivity.py documentation/tools/extra_variants.py \
         documentation/tools/acceptance_window.py documentation/tools/scorecard_ratios.py discovery/*.py; do
  out="$("$PY" "$s" --help 2>&1)" && ok "$s --help" || no "$s --help: $(printf '%s' "$out" | tail -1)"
done
for s in discovery/run_all.sh documentation/tools/build_proj_fma.sh scan_public_repo.sh smoke_test.sh; do
  bash -n "$s" && ok "$s parses" || no "$s does not parse"
done
fp="$("$PY" documentation/tools/fingerprint.py 2>&1 | tail -1)" && ok "fingerprint: $fp" || no "fingerprint.py"
names="$("$PY" discovery/lwc_names.py 2>&1)"
[ "$(printf '%s\n' "$names" | grep -c -- '-> True$')" = 9 ] && [ "$(printf '%s\n' "$names" | grep -c -- '-> False$')" = 1 ] \
  && [ "$(printf '%s\n' "$names" | grep -c -- '-> None$')" = 1 ] && ok "road-name matcher self-test (9 True, 1 False, 1 None)" || no "road-name matcher self-test"

if [ -f documentation/out/counts.parquet ]; then
  (cd documentation && "$PY" sensitivity.py --error 0.00000301 > /dev/null) \
    && ok "sensitivity.py rebuilt out/sensitivity.csv ($(( $(wc -l < documentation/out/sensitivity.csv) - 1 )) variants)" || no "sensitivity.py"
  sha="$(cd documentation && "$PY" - <<'EOF'
import hashlib, os, tempfile, warnings
import pandas as pd
warnings.filterwarnings("ignore")
from pipeline import CONV, OUTDIR, score, write
df = pd.read_parquet(os.path.join(OUTDIR, "counts.parquet"))
c, t, b, p = score(df, CONV["output_decimals"])
f = os.path.join(tempfile.mkdtemp(), "submission.csv")
write(f, df.GEOID, c, CONV["output_decimals"])
print(hashlib.sha256(open(f, "rb").read()).hexdigest())
EOF
)"
  case "$sha" in
    40aea8185bdf0aa7b2653d237581e6cb8adfa3df59de4a15b1ec06fcc5f7c289) ok "scored file rebuilt from the counts: sha256 40aea818... (the pyproj wheel's arithmetic)";;
    30110feb61ee848973a9b7543741c7d586fdf850e26da3854816cd26e2486908) ok "scored file rebuilt from the counts: sha256 30110feb... (fused multiply-add)";;
    *) no "scored file rebuilt from the counts has sha256 $sha, neither of the two expected";;
  esac
  win="$(cd documentation && "$PY" tools/acceptance_window.py out/counts.parquet 2>&1)"
  if printf '%s\n' "$win" | grep -q "building_gap         sum 52.5301969502" && printf '%s\n' "$win" | grep -q "poi_gap              sum 482.2154991143" \
     && printf '%s\n' "$win" | grep -Eq "transport_gap        sum (1048.3122362295|1048.2997252134)"; then
    ok "acceptance window: column sums as in the entry ($(printf '%s\n' "$win" | grep transport_gap | awk '{print "transport_gap sum " $3 ", " $7 " " $8 " " $9}' | sed 's/ *$//'))"
  else
    no "acceptance window: $(printf '%s' "$win" | tail -1)"
  fi
else
  echo "skip  documentation/out/counts.parquet not present: run python pipeline.py --check --extra for the last three checks"
fi
[ "$fail" = 0 ] && echo "smoke test: PASS" || { echo "smoke test: FAIL"; exit 1; }
