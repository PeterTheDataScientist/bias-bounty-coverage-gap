"""Step 17. The challenge's own gap formula applied to the flood hazard attribute, per tract:

    flood_crossing_attribute_gap = 1 - min(1, crossings Overture marks as a ford or flood-prone / official crossings)

  1. Every road_flags value present in the release, in the challenge's roads file AND in the service/track/
     living_street/unknown file (work/extra_segments.parquet), counted with DuckDB; none can mean ford or flood.
  2. Per official crossing: does ANY Overture segment within 30 m carry such a value (work/lwc_seg_candidates.parquet,
     all segment pairs within 100 m, built by lwc_overture.py)?  Service/track segments carry the same seven flags.
  3. Per scored tract with at least one official crossing (work/tracts_lwc.parquet, the object disc_numbers.py uses):
     the gap, and beside it the scorecard road gap. Road-gap values: transport_gap and _t_def in
     work/bias_components.parquet (scorecard_inputs.py, from the documentation pipeline's per-tract counts), the
     published road formula with segments clipped at tract boundaries; checked here against the README's published
     count of South-Central Texas tracts with no road component (1,704 of 6,003).
Outputs: work/v4_flood_attr_gap.json, work/v4_flood_attr_gap_tracts.csv
"""
import argparse, json, re, duckdb, numpy as np, pandas as pd
from common import COMPONENTS, EXTRA_SEGMENTS, OVT_ROADS, need
from v4_common import careful_set
argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter).parse_args()
ROADS = {"challenge roads file": OVT_ROADS, "service/track/living_street/unknown": EXTRA_SEGMENTS}
need(*ROADS.values(), COMPONENTS, "work/lwc_unique.parquet", "work/lwc_all.parquet", "work/lwc_seg_candidates.parquet", "work/tracts_lwc.parquet")
HAZ = re.compile(r"ford|flood|water|wet|low", re.I)
out = {}
con = duckdb.connect(); con.execute("SET threads=2; SET memory_limit='1500MB'; SET enable_progress_bar=false;")
flags = {}
for k, f in ROADS.items():
    d = con.execute(f"""SELECT v, count(*) n FROM (SELECT unnest(rf."values") v FROM (SELECT unnest(road_flags) rf FROM '{f}'
                        WHERE road_flags IS NOT NULL)) GROUP BY v ORDER BY n DESC""").df()
    flags[k] = dict(zip(d.v, d.n.astype(int)))
out["road_flags_values_in_release"] = flags
out["road_flags_values_matching_ford_flood_water_wet_low"] = sorted({v for d in flags.values() for v in d if HAZ.search(str(v))})
# 2. per crossing, any segment within 30 m marked?
U = pd.read_parquet("work/lwc_unique.parquet", columns=["src", "src_id", "GEOID", "on_overture_30m", "seg_flags"])
L = pd.read_parquet("work/lwc_all.parquet", columns=["src", "src_id", "GEOID"]); L = L[L.GEOID.notna()].reset_index(drop=True)
C = pd.read_parquet("work/lwc_seg_candidates.parquet", columns=["lwc_row", "dist_m", "flags"])
C = C[C.dist_m <= 30].merge(L[["src", "src_id"]], left_on="lwc_row", right_index=True)
C["haz"] = C["flags"].fillna("").map(lambda s: bool(HAZ.search(s)))
m = C.groupby(["src", "src_id"]).haz.any().rename("marked_30m").reset_index()
U = U.merge(m, on=["src", "src_id"], how="left"); U["marked_30m"] = U.marked_30m.fillna(False).astype(bool)
out["crossings"] = dict(official=int(len(U)), with_overture_segment_30m=int(U.on_overture_30m.sum()),
                        segment_pairs_within_30m=int(len(C)), marked_ford_or_flood=int(U.marked_30m.sum()))
# 3. per tract
S = pd.read_parquet("work/tracts_lwc.parquet", columns=["GEOID", "n_lwc", "ur_class"])
K = pd.read_parquet(COMPONENTS, columns=["GEOID", "transport_gap", "_t_def", "coverage_gap_score", "region"])
K = K[K.region == "south-central-tx"]
out["road_gap_source"] = dict(file=COMPONENTS, script="scorecard_inputs.py, from the per-tract counts of documentation/pipeline.py --check --extra",
                              rule="Overture motorway/trunk/primary/secondary length v TIGER S1100/S1200, clipped at tract boundaries, 1 - min(1, ratio)",
                              scored_tracts=int(len(K)), tracts_without_road_component=int((~K._t_def).sum()), readme_published="1,704 of 6,003")
T = S.merge(K, on="GEOID", how="left")
mk = U.groupby("GEOID").agg(n_official=("src_id", "size"), n_on_ovt_30m=("on_overture_30m", "sum"), n_marked=("marked_30m", "sum")).reset_index()
T = T.merge(mk, on="GEOID", how="left").fillna({"n_official": 0, "n_on_ovt_30m": 0, "n_marked": 0})
assert (T.n_official == T.n_lwc).all()
h = T[T.n_official > 0].copy()
h["flood_crossing_attribute_gap"] = 1 - np.minimum(1, h.n_marked / h.n_official)
d = h[h._t_def]
_, core, Bc = careful_set()
ct = h[h.GEOID.isin(set(Bc.GEOID))]; ctd = ct[ct._t_def]
out["tracts_with_crossings"] = dict(
    n=int(len(h)), flood_gap_min=float(h.flood_crossing_attribute_gap.min()), flood_gap_max=float(h.flood_crossing_attribute_gap.max()),
    flood_gap_all_equal_1=bool((h.flood_crossing_attribute_gap == 1).all()),
    road_gap_defined=int(len(d)), road_gap_defined_share=round(len(d) / len(h), 4),
    road_gap_exactly_0=int((d.transport_gap == 0).sum()),
    road_gap_exactly_0_share_of_defined=round(float((d.transport_gap == 0).mean()), 4),
    road_gap_exactly_0_share_of_all=round(float((d.transport_gap == 0).sum() / len(h)), 4),
    road_gap_not_scored=int((~h._t_def).sum()),
    road_gap_mean_defined=round(float(d.transport_gap.mean()), 4), road_gap_median_defined=round(float(d.transport_gap.median()), 4),
    road_gap_below_0_1_share_of_defined=round(float((d.transport_gap < 0.1).mean()), 4))
out["careful_set_tracts"] = dict(
    n=int(len(ct)), flood_gap_all_equal_1=bool((ct.flood_crossing_attribute_gap == 1).all()),
    road_gap_defined=int(len(ctd)), road_gap_exactly_0=int((ctd.transport_gap == 0).sum()),
    road_gap_exactly_0_share_of_defined=round(float((ctd.transport_gap == 0).mean()), 4),
    road_gap_exactly_0_share_of_all=round(float((ctd.transport_gap == 0).sum() / len(ct)), 4),
    road_gap_not_scored=int((~ct._t_def).sum()), road_gap_mean_defined=round(float(ctd.transport_gap.mean()), 4),
    road_gap_median_defined=round(float(ctd.transport_gap.median()), 4))
h[["GEOID", "n_official", "n_on_ovt_30m", "n_marked", "flood_crossing_attribute_gap", "transport_gap", "_t_def", "coverage_gap_score"]].rename(
    columns={"_t_def": "road_gap_defined"}).to_csv("work/v4_flood_attr_gap_tracts.csv", index=False)
json.dump(out, open("work/v4_flood_attr_gap.json", "w"), indent=1)
print(json.dumps(out, indent=1))
