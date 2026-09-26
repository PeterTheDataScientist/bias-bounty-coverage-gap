"""Step 13. The conservative core behind the Discovery entry's headline (25 Sep 2026): areas that TIGER confirms are cut off
AND that the 20 m near-miss test does not flag. Every figure the entry quotes for 'the careful number' and for
'who lives there' comes from this file's output (work/core_numbers.json), so no core figure is typed by hand."""
import argparse, json
import numpy as np, pandas as pd
from common import STRATA, need
argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter).parse_args()
need("work/tiger_check_plus_strict.parquet", "work/tiger_check_plus_strict_multi.parquet", "work/bldg_plus_strict.parquet",
     STRATA, "work/lwc_all.parquet", "work/groups_b_plus_strict.parquet",
     columns={"work/groups_b_plus_strict.parquet": ["nearmiss_20m", "pop_block", "hu_block"]})
R = pd.concat([pd.read_parquet("work/tiger_check_plus_strict.parquet"), pd.read_parquet("work/tiger_check_plus_strict_multi.parquet")])
a = R[R.verdict == "agrees_isolated"]
G = pd.read_parquet("work/groups_b_plus_strict.parquet")
core = G[G.comp.isin(set(a.comp)) & ~G.nearmiss_20m & (G.bldg > 0)]
B = pd.read_parquet("work/bldg_plus_strict.parquet"); Bc = B[B.comp.isin(core.comp)]
Sx = pd.read_parquet(STRATA)
w = lambda d, c, wt: float(np.average(d[c].fillna(d[c].median()), weights=d[wt]))
B2 = Bc.merge(Sx[["GEOID", "cvi_climate_extreme_events"]], on="GEOID", how="left")
L = pd.read_parquet("work/lwc_all.parquet")
names = L[L.src == "txgio"].groupby(L.GEOID.str[:5]).county_src.agg(lambda s: s.mode().iloc[0])
top = Bc.groupby(Bc.GEOID.str[:5]).size().sort_values(ascending=False).head(8)
N = dict(areas=int(len(core)), buildings=int(core.bldg.sum()), residents_block=int(round(core.pop_block.sum())),
         homes_block=int(round(core.hu_block.sum())), tracts=int(Bc.GEOID.nunique()), counties=int(Bc.GEOID.str[:5].nunique()),
         single_areas=int(core.single_crossing.sum()), single_buildings=int(core[core.single_crossing].bldg.sum()),
         pct_rural_residents=round(100 * Bc.loc[Bc.ur_class == "Rural", "ppl"].sum() / Bc.ppl.sum(), 1),
         svi_core=round(w(Bc, "svi_overall", "ppl"), 2), svi_region=round(w(Sx, "svi_overall", "pop_total"), 2),
         cvi_ee_core=round(w(B2, "cvi_climate_extreme_events", "ppl"), 2), cvi_ee_region=round(w(Sx, "cvi_climate_extreme_events", "pop_total"), 2),
         top_counties={names.get(k, k): int(v) for k, v in top.items()})
json.dump(N, open("work/core_numbers.json", "w"), indent=1); print(json.dumps(N, indent=1))
