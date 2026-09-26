"""Step 12. Named examples: TIGER-confirmed areas behind official crossings, with everything a judge needs to check them."""
import argparse, pandas as pd, numpy as np
from common import COMPONENTS, STRATA, need
argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter).parse_args()
need(STRATA, COMPONENTS, "work/lwc_unique_osm.parquet", "work/lwc_unique.parquet", "work/tiger_check_plus_strict.parquet",
     "work/tiger_check_plus_strict_multi.parquet", "work/edges_plus_strict.parquet", "work/cuts_plus_strict.parquet")
S = pd.read_parquet(STRATA)[["GEOID", "svi_overall", "ur_class", "pop_total"]]
K = pd.read_parquet(COMPONENTS)[["GEOID", "transport_gap", "_t_def", "coverage_gap_score"]]
U = pd.read_parquet("work/lwc_unique_osm.parquet")[["src", "src_id", "osm_tag_100m"]]
L = pd.read_parquet("work/lwc_unique.parquet")[["src", "src_id", "lon", "lat", "road", "road_eff", "stream", "lwc_type", "owner", "origin", "signage", "county_src", "seg_name", "seg_flags", "seg_dist_m", "tier", "flood_freq", "desc"]]
L = L.merge(U, on=["src", "src_id"], how="left")
out = []
for mode, f in (("single", "work/tiger_check_plus_strict.parquet"), ("multi", "work/tiger_check_plus_strict_multi.parquet")):
    R = pd.read_parquet(f); R = R[R.verdict == "agrees_isolated"].copy(); R["mode"] = mode
    out.append(R)
R = pd.concat(out)
X = pd.read_parquet("work/edges_plus_strict.parquet"); C = pd.read_parquet("work/cuts_plus_strict.parquet")
Xc = X[X.cut]
touch = pd.concat([pd.DataFrame(dict(comp=Xc.cu[Xc.su].values, edge=Xc.index[Xc.su].values)),
                   pd.DataFrame(dict(comp=Xc.cv[Xc.sv].values, edge=Xc.index[Xc.sv].values))]).drop_duplicates()
touch = touch.merge(C[["edge", "src", "src_id"]], on="edge").merge(L, on=["src", "src_id"], how="left")
rows = []
for _, r in R.iterrows():
    cs = touch[touch.comp == r.comp]
    g = S.merge(K, on="GEOID")
    tr = g[g.GEOID == r.GEOID].iloc[0] if (g.GEOID == r.GEOID).any() else None
    rows.append(dict(mode=r["mode"], comp=r.comp, buildings=int(r.bldg), people=round(r.people), county=cs.county_src.iloc[0],
                     crossings="; ".join(f"{a} over {b} ({c}, {d})" for a, b, c, d in zip(cs.road_eff.fillna("unnamed road"), cs.stream.fillna("unnamed stream"), cs.lwc_type.fillna("TWDB record"), cs.src + ":" + cs.src_id)),
                     n_cross=len(cs), overture_flags="|".join(sorted(set("|".join(cs.seg_flags.fillna("")).split("|")) - {""})) or "none",
                     osm_tag=bool(cs.osm_tag_100m.fillna(False).any()), signage="|".join(sorted(set(cs.signage.dropna()) - {""})),
                     tract=r.GEOID, tract_svi=None if tr is None else round(tr.svi_overall, 2), ur=None if tr is None else tr.ur_class,
                     transport_gap=None if tr is None else (round(tr.transport_gap, 3) if tr._t_def else "undefined"),
                     composite=None if tr is None else round(tr.coverage_gap_score, 3), lon=cs.lon.iloc[0], lat=cs.lat.iloc[0]))
E = pd.DataFrame(rows).sort_values(["mode", "buildings"], ascending=[False, False])
E.to_csv("work/examples_confirmed.csv", index=False)
pd.set_option("display.width", 300); pd.set_option("display.max_colwidth", 110)
print(E[E["mode"] == "single"].head(30)[["buildings", "people", "county", "crossings", "overture_flags", "osm_tag", "signage", "tract", "tract_svi", "ur", "transport_gap", "composite"]].to_string())
print(E[E["mode"] == "multi"].head(15)[["buildings", "people", "county", "n_cross", "crossings", "tract", "tract_svi", "transport_gap"]].to_string())
