"""Step 4. Who lives with the crossings, and what the automated scorecard says about their tracts."""
import argparse, numpy as np, pandas as pd
from common import COMPONENTS, STRATA, need
argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter).parse_args()
need("work/lwc_unique.parquet", STRATA, COMPONENTS)
U = pd.read_parquet("work/lwc_unique.parquet")
S = pd.read_parquet(STRATA)
K = pd.read_parquet(COMPONENTS)
S = S.merge(K, on="GEOID", how="inner")          # scored tracts only (6,003)
n = U.groupby("GEOID").size().rename("n_lwc")
S = S.merge(n, left_on="GEOID", right_index=True, how="left").fillna({"n_lwc": 0})
S["has"] = S.n_lwc > 0
print("scored tracts", len(S), "with >=1 crossing", S.has.sum(), "people", int(S.loc[S.has, "pop_total"].sum()), "of", int(S.pop_total.sum()))
S["svi_q"] = pd.qcut(S.svi_overall, 4, labels=["Q1 least", "Q2", "Q3", "Q4 most"])
g = S.groupby("svi_q", observed=True).agg(tracts=("GEOID", "size"), pop=("pop_total", "sum"), lwc=("n_lwc", "sum"), share_with=("has", "mean"))
g["lwc_per_100k"] = g.lwc / g["pop"] * 1e5
print(g)
g = S.groupby("ur_class").agg(tracts=("GEOID", "size"), pop=("pop_total", "sum"), lwc=("n_lwc", "sum"), share_with=("has", "mean"))
g["lwc_per_100k"] = g.lwc / g["pop"] * 1e5
print(g)
h = S[S.has]
print("\nscorecard view of the tracts that hold crossings:")
print(" transport defined:", h._t_def.mean().round(3), " transport gap exactly 0 (of defined):", (h.loc[h._t_def, "transport_gap"] == 0).mean().round(3),
      " mean transport gap (defined):", h.loc[h._t_def, "transport_gap"].mean().round(4))
print(" composite mean", h.coverage_gap_score.mean().round(4), "vs tracts without crossings", S.loc[~S.has, "coverage_gap_score"].mean().round(4))
print(" composite median", h.coverage_gap_score.median().round(4), "vs", S.loc[~S.has, "coverage_gap_score"].median().round(4))
S["cty"] = S.STATEFP + S.COUNTYFP
c = S.groupby("cty").agg(lwc=("n_lwc", "sum"), pop=("pop_total", "sum"), tracts=("GEOID", "size")).sort_values("lwc", ascending=False)
c["per_10k"] = c.lwc / c["pop"] * 1e4
print(c.head(15)); print(c[c["pop"] > 0].sort_values("per_10k", ascending=False).head(15))
S.to_parquet("work/tracts_lwc.parquet")
