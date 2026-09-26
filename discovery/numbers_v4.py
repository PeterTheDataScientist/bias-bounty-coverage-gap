"""Step 22. Collect every number of steps 14 to 21 into work/discovery_numbers_v4.json, from their outputs only.
Run after: block_pop_v4.py, variants_v4.py, uncertainty.py, flood_attr_gap.py, who_v4.py, per_tract_table.py,
precision_audit.py sample, audit_summary.py, figures.py."""
import argparse, json, re, hashlib, os, numpy as np, pandas as pd
from common import need
argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter).parse_args()
need("work/v4_variants.json", "work/v4_uncertainty.json", "work/v4_flood_attr_gap.json", "work/v4_who.json", "work/v4_audit_summary.json",
     "work/v4_per_tract_table.csv", "figs/v4_region_map.png", "figs/v4_bexar_979.png")
J = lambda f: json.load(open(f))
V = J("work/v4_variants.json"); U = J("work/v4_uncertainty.json"); F = J("work/v4_flood_attr_gap.json")
W = J("work/v4_who.json"); A = J("work/v4_audit_summary.json")
T = pd.read_csv("work/v4_per_tract_table.csv", dtype={"GEOID": str})
rows = {r["version"]: r for r in V["rows"]}
careful = rows["CAREFUL SET: + TIGER agrees + no 20 m near-miss"]
N = {"generated_by": "numbers_v4.py", "date": "2026-09-25", "seed": 20260926}
N["six_versions"] = [{k: r[k] for k in ("version", "crossings_closed", "areas", "buildings", "single_areas", "single_buildings", "residents", "homes",
                                         "single_residents", "single_homes", "all_stranded_groups")} for r in V["rows"]]
N["six_versions_range_buildings"] = dict(min=min(r["buildings"] for r in V["rows"][:6]), max=max(r["buildings"] for r in V["rows"][:6]),
                                         lead_plus_strict=rows["plus/strict"]["buildings"], careful=careful["buildings"])
N["six_versions_inconsistencies_vs_variants_table_csv"] = V["inconsistencies_vs_variants_table_csv"]
N["careful_set"] = {k: careful[k] for k in ("areas", "buildings", "single_areas", "single_buildings", "residents", "homes", "single_residents", "single_homes")}
N["careful_set"]["tracts"] = int(len(T)); N["careful_set"]["counties"] = int(T.county.nunique())
from v4_common import careful_set, tiger_results
_, core_, _ = careful_set(); R_ = tiger_results(); r_ = R_[R_.comp.isin(core_.comp)]
N["careful_set_tiger_reach"] = dict(areas=int(len(r_)), areas_none_reach=int((r_.frac_reach_main == 0).sum()), areas_some_reach=int((r_.frac_reach_main > 0).sum()),
                                    buildings_in_areas_some_reach=int(r_.loc[r_.frac_reach_main > 0, "bldg"].sum()), max_share_reaching=round(float(r_.frac_reach_main.max()), 3),
                                    note="tiger_check.py samples up to 40 buildings per area; 'agrees_isolated' means at most 20% reach the main TIGER network")
# 2a imagery audit
N["audit"] = dict(sample=A["sample"]["areas"], design="10 areas from each building-count quartile of the 216 (54 each), seed 20260926",
                  verdicts=A["verdict_counts"], verdicts_by_quartile=A["verdict_by_stratum"],
                  precision_flood_settled=A["precision"]["flood"]["settled"], precision_strict_settled=A["precision"]["strict"]["settled"],
                  precision_flood_bounds=[A["precision"]["flood"]["lower_bound"]["p"], A["precision"]["flood"]["upper_bound"]["p"]],
                  adjusted_flood=A["adjusted"]["flood"], adjusted_strict=A["adjusted"]["strict"], adjusted_simple=A["adjusted_simple"],
                  building_weighted_sensitivity=A["sensitivity_building_weighted_buildings"])
# 2b, 2c
N["svi_cvi_bootstrap"] = {k: U[k] for k in ("bootstrap_by_area", "bootstrap_by_tract", "within_rural_urban", "n_missing_filled")}
N["rural_urban_rate"] = U["rural_urban_rate"]
# 3
N["who"] = dict(requested_variables_present=W["requested_variables_present"], svi_columns=W["svi_columns"], cvi_columns=W["cvi_columns"],
                resident_weighted={k: {kk: v[kk] for kk in ("careful", "region", "diff", "diff_ci95_by_area", "diff_ci95_by_tract", "verdict")} for k, v in W["resident_weighted"].items()},
                inside_rural_tracts={k: {kk: v[kk] for kk in ("careful_rural", "rural_region", "diff", "diff_ci95_by_area", "verdict")} for k, v in W["inside_rural_tracts"].items()})
# 4
tw = F["tracts_with_crossings"]
ct = T[T.road_gap.notna()]
N["flood_attribute_gap"] = dict(road_flags_values_in_release=F["road_flags_values_in_release"], hazard_values=F["road_flags_values_matching_ford_flood_water_wet_low"],
                                crossings=F["crossings"], crossing_tracts=tw, road_gap_source=F["road_gap_source"],
                                careful_tracts=dict(n=int(len(T)), with_official_crossing=int((T.crossings_official > 0).sum()),
                                                    flood_gap_1_in_all_with_crossing=bool((T.loc[T.crossings_official > 0, "flood_crossing_attribute_gap"] == 1).all()),
                                                    road_gap_defined=int(len(ct)), road_gap_exactly_0=int((ct.road_gap == 0).sum()),
                                                    road_gap_exactly_0_share_of_defined=round(float((ct.road_gap == 0).mean()), 4),
                                                    road_gap_exactly_0_share_of_all=round(float((ct.road_gap == 0).sum() / len(T)), 4),
                                                    road_gap_not_scored=int(T.road_gap.isna().sum()), road_gap_median=round(float(ct.road_gap.median()), 4)))
# 5
N["per_tract_table"] = dict(rows=int(len(T)), counties=int(T.county.nunique()), buildings=int(T.careful_buildings.sum()),
                            single=int(T.careful_buildings_single.sum()), residents=round(float(T.careful_residents.sum()), 1), homes=round(float(T.careful_homes.sum()), 1),
                            official_crossings_in_these_tracts=int(T.crossings_official.sum()), with_overture_30m=int(T.crossings_overture_30m.sum()),
                            marked_ford_or_flood=int(T.crossings_marked_ford_flood.sum()),
                            files=["work/v4_per_tract_table.csv", "work/v4_per_tract_table.txt"])
# 6
sha = lambda p: hashlib.sha256(open(p, "rb").read()).hexdigest()[:16]
N["figures"] = {p: sha(p) for p in ("figs/v4_region_map.png", "figs/v4_bexar_979.png")}
json.dump(N, open("work/discovery_numbers_v4.json", "w"), indent=1, default=str)
print("wrote work/discovery_numbers_v4.json; keys:", list(N))
