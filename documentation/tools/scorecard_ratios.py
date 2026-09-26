"""
Scorecard-style stratum ratios recomputed from my own column (section 8 of the entry): the mean coverage gap of the
tracts in a stratum over the mean of the tracts outside it, on the composite as written (6 decimal places), for the
scored build and for every variant of sensitivity.py, the whole-segment midpoint road rule first.

  SVI above vs below median   svi_overall above the median of the tracts that have a value, against those at or below
                              it; the 85 tracts with no value are left out
  CVI above vs below median   the same with cvi_overall (2 tracts have no value)
  tribal vs non-tribal        tribal_any true against false: the definition that gives my column the scorecard's 2.90
  legally-defined tribal      tribal_legal true against false
  vs non-tribal

Run from documentation/ after `python pipeline.py --check --extra` (the variants' counts come from --extra):

    python tools/scorecard_ratios.py
    python tools/scorecard_ratios.py --arith out_fma/counts.parquet     adds the fused multiply-add build

It reads out/counts.parquet and the four strata tables (strata/REGION/REGION-strata-tract-table.parquet, still in the
challenge bucket; with BIAS_DATA_DIR set, from that folder), checks the tables against INPUTS_MANIFEST.csv, prints
the scored build against the midpoint rule and then every variant, and writes out/scorecard_ratios.csv.
"""
import argparse, os, sys
import numpy as np, pandas as pd
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import pipeline as P
import sensitivity as S

ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
ap.add_argument("--arith", help="counts.parquet from a run under tools/build_proj_fma.sh; adds the fused multiply-add build")
a = ap.parse_args()
df = S.load()
alt = None
if a.arith:
    if not os.path.exists(a.arith):
        sys.exit(f"missing {a.arith}: run the FMA build first (README.md)")
    alt = pd.read_parquet(a.arith)
    assert (alt.GEOID.values == df.GEOID.values).all(), "the two runs must cover the same tracts in the same order"

keys = [f"strata/{r}/{r}-strata-tract-table.parquet" for r in P.REGIONS]
P.verify(keys, read_by="tools")
cols = ["GEOID", "svi_overall", "cvi_overall", "tribal_any", "tribal_legal"]
st = pd.concat([pd.read_parquet(P.fetch(k), columns=cols) for k in keys])
st["GEOID"] = P.text_geoid(st.GEOID)
st = st.drop_duplicates("GEOID").set_index("GEOID")          # the two border tracts sit in two regions' tables
assert df.GEOID.isin(st.index).all(), "a scored tract is missing from the strata tables"

GROUPS = []
for name, col in (("SVI above vs below median", "svi_overall"), ("CVI above vs below median", "cvi_overall")):
    x = df.GEOID.map(st[col]).values.astype(float)
    ok = ~np.isnan(x)
    m = np.median(x[ok])
    GROUPS.append((name, ok & (x > m), ok & (x <= m)))
for name, col in (("tribal vs non-tribal", "tribal_any"), ("legally-defined tribal vs non-tribal", "tribal_legal")):
    x = df.GEOID.map(st[col]).fillna(False).astype(bool).values
    GROUPS.append((name, x, ~x))


def ratios(v):
    return [v[i].mean() / v[o].mean() for _, i, o in GROUPS]


base = S.build(df)
assert np.array_equal(base, P.score(df, P.CONV["output_decimals"])[0]), "the scored build must equal pipeline.score"
rows = [("scored build", "as scored", *ratios(base))] + [(g, n, *ratios(v)) for g, n, v in S.variants(df, alt)]
mid = rows[1]
print(f"{'ratio':<38} {'in':>5} {'out':>5}  {'scored':>7}  {'midpoint':>8}  {'change':>7}")
for (name, i, o), r0, r1 in zip(GROUPS, rows[0][2:], mid[2:]):
    print(f"{name:<38} {i.sum():>5} {o.sum():>5}  {r0:7.4f}  {r1:8.4f}  {r1 - r0:+7.4f}")
print(f"\n{'build':<74} {'SVI':>7} {'CVI':>7} {'tribal':>7} {'legal':>7}")
for g, n, *r in rows:
    print(f"{(g + ': ' + n if g != 'scored build' else g):<74} " + " ".join(f"{x:7.3f}" for x in r))
pd.DataFrame(rows, columns=["group", "variant"] + [g[0] for g in GROUPS]).to_csv(os.path.join(P.OUTDIR, "scorecard_ratios.csv"), index=False)
