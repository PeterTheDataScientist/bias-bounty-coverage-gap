"""Step 12. Who is behind the crossings: SVI and rurality of stranded buildings against the region, and what the
automated scorecard says about their tracts."""
import argparse, numpy as np, pandas as pd, json
from common import COMPONENTS, STRATA, need
argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter).parse_args()
need(STRATA, COMPONENTS, *(f"work/{k}_{n}_{v}.parquet" for k in ("bldg", "groups_b") for n in ("base", "plus") for v in ("all", "strict", "fords")))
S = pd.read_parquet(STRATA)
K = pd.read_parquet(COMPONENTS)
S = S.merge(K, on="GEOID", how="inner")
reg_pop = S.pop_total.sum()
reg_svi = np.average(S.svi_overall.fillna(S.svi_overall.median()), weights=S.pop_total)
reg_rural = S.loc[S.ur_class == "Rural", "pop_total"].sum() / reg_pop
out = {}
for net in ("base", "plus"):
    for var in ("all", "strict", "fords"):
        B = pd.read_parquet(f"work/bldg_{net}_{var}.parquet")
        G = pd.read_parquet(f"work/groups_b_{net}_{var}.parquet")
        single = set(G.comp[G.single_crossing])
        B["single"] = B.comp.isin(single)
        def summ(b):
            b = b[b.ppl.notna()]
            w = b.ppl
            return dict(buildings=int(len(b)), people=int(round(w.sum())),
                        svi_w=round(float(np.average(b.svi_overall.fillna(reg_svi), weights=w)) if w.sum() > 0 else float("nan"), 3),
                        rural_share=round(float(w[b.ur_class == "Rural"].sum() / w.sum()), 3) if w.sum() > 0 else None,
                        svi_q4_share=round(float(w[b.svi_overall >= S.svi_overall.quantile(0.75)].sum() / w.sum()), 3) if w.sum() > 0 else None,
                        tracts=int(b.GEOID.nunique()))
        r = dict(all=summ(B), single=summ(B[B.single]))
        tr = S[S.GEOID.isin(B.GEOID.unique())]
        r["scorecard_tracts"] = dict(n=int(len(tr)), transport_defined=round(float(tr._t_def.mean()), 3),
                                     transport_zero_of_defined=round(float((tr.loc[tr._t_def, "transport_gap"] == 0).mean()), 3),
                                     composite_mean=round(float(tr.coverage_gap_score.mean()), 4))
        out[f"{net}_{var}"] = r
out["region"] = dict(people=int(reg_pop), svi_w=round(float(reg_svi), 3), rural_share=round(float(reg_rural), 3),
                     composite_mean=round(float(S.coverage_gap_score.mean()), 4))
json.dump(out, open("work/report_who.json", "w"), indent=1)
print(json.dumps(out, indent=1))
