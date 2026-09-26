"""Step 19. One row per census tract that holds a careful-set building (expected 162), for posting.
Every count comes from the objects behind core_numbers.py; residents and homes are the Census-block estimates per
building written by block_pop_v4.py for plus/strict (their per-area sums equal block_pop.py's to 1e-11).
Columns
  GEOID, county                       tract (11-character string) and county name from the inventories' county field
  crossings_official                  official low-water crossings in the tract (the 8,454-crossing list)
  crossings_overture_30m              of those, with an Overture road segment within 30 m
  crossings_marked_ford_flood         of those, Overture marks as a ford or flood-prone road (always 0: no such flag exists)
  flood_crossing_attribute_gap        1 - min(1, marked / official); blank where the tract holds no official crossing
  careful_areas                       careful-set areas with at least one building in the tract (an area can span tracts)
  careful_buildings, careful_buildings_single, careful_residents, careful_homes
  tiger_agrees / tiger_other_way / tiger_mixed_or_road_missing / tiger_not_checked
                                      all plus/strict stranded areas with buildings in the tract, by TIGER verdict
                                      (not checked = below the 10- or 30-building threshold)
  nearmiss_20m_areas                  of the TIGER-agreeing areas, how many the 20 m near-miss test removed
  road_gap                            scorecard road (transport) gap, bias_components.parquet; blank = not scored
  svi                                 CDC SVI overall percentile (the challenge's strata table, CC BY-SA 4.0)
Outputs: work/v4_per_tract_table.csv, work/v4_per_tract_table.txt (fixed width, no pipes, for the Zindi editor).
Both carry the svi column, so they stay in work/: export_results.py ships the table without it as
../results/careful_tracts.csv, and join_strata.py adds strata columns back locally.
"""
import argparse, numpy as np, pandas as pd
from common import COMPONENTS, need
from v4_common import careful_set, tiger_results, county_names, strata
argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter).parse_args()
need("work/v4_blockpop_bldg_plus_strict.parquet", "work/lwc_unique.parquet", "work/v4_flood_attr_gap_tracts.csv", COMPONENTS)
G, core, Bc = careful_set()
assert Bc.GEOID.notna().all()
bp = pd.read_parquet("work/v4_blockpop_bldg_plus_strict.parquet", columns=["rg", "row", "comp", "ppl_blk", "hu_blk"])
Bc = Bc.merge(bp, on=["rg", "row", "comp"], how="left", validate="one_to_one")
assert Bc.ppl_blk.notna().all()
Bc["single"] = Bc.comp.isin(set(core.comp[core.single_crossing]))
T = Bc.groupby("GEOID").agg(careful_areas=("comp", "nunique"), careful_buildings=("row", "size"),
                            careful_buildings_single=("single", "sum"), careful_residents=("ppl_blk", "sum"), careful_homes=("hu_blk", "sum")).reset_index()
# official crossings per tract
U = pd.read_parquet("work/lwc_unique.parquet", columns=["src", "src_id", "GEOID", "on_overture_30m"])
c = U.groupby("GEOID").agg(crossings_official=("src_id", "size"), crossings_overture_30m=("on_overture_30m", "sum")).reset_index()
T = T.merge(c, on="GEOID", how="left").fillna({"crossings_official": 0, "crossings_overture_30m": 0})
fg = pd.read_csv("work/v4_flood_attr_gap_tracts.csv", dtype={"GEOID": str})[["GEOID", "n_marked", "flood_crossing_attribute_gap"]]
T = T.merge(fg, on="GEOID", how="left").rename(columns={"n_marked": "crossings_marked_ford_flood"})
T["crossings_marked_ford_flood"] = T.crossings_marked_ford_flood.fillna(0).astype(int)
# TIGER verdicts of all plus/strict stranded areas with buildings in each tract
R = tiger_results()[["comp", "verdict"]]
B = pd.read_parquet("work/bldg_plus_strict.parquet", columns=["comp", "GEOID"]).drop_duplicates()
B = B.merge(R, on="comp", how="left").merge(G[["comp", "nearmiss_20m"]], on="comp", how="left")
B["verdict"] = B.verdict.fillna("not_checked")
vc = pd.crosstab(B.GEOID, B.verdict)
for k in ("agrees_isolated", "tiger_has_other_way", "mixed", "crossing_road_not_in_tiger", "not_checked"):
    if k not in vc: vc[k] = 0
vc = pd.DataFrame(dict(tiger_agrees=vc.agrees_isolated, tiger_other_way=vc.tiger_has_other_way,
                       tiger_mixed_or_road_missing=vc.mixed + vc.crossing_road_not_in_tiger, tiger_not_checked=vc.not_checked))
nm = B[(B.verdict == "agrees_isolated") & B.nearmiss_20m].groupby("GEOID").comp.nunique().rename("nearmiss_20m_areas")
T = T.merge(vc, left_on="GEOID", right_index=True, how="left").merge(nm, left_on="GEOID", right_index=True, how="left").fillna({"nearmiss_20m_areas": 0})
K = pd.read_parquet(COMPONENTS, columns=["GEOID", "transport_gap", "_t_def"])
S = strata(["GEOID", "svi_overall"])
T = T.merge(K, on="GEOID", how="left").merge(S, on="GEOID", how="left")
T["road_gap"] = np.where(T._t_def == True, T.transport_gap, np.nan)
names = county_names(); T.insert(1, "county", T.GEOID.str[:5].map(names))
assert T.county.notna().all(), T[T.county.isna()]
T = T.drop(columns=["transport_gap", "_t_def"]).rename(columns={"svi_overall": "svi"})
T = T.sort_values(["careful_buildings", "GEOID"], ascending=[False, True]).reset_index(drop=True)
for k in ("crossings_official", "crossings_overture_30m", "careful_buildings_single", "tiger_agrees", "tiger_other_way", "tiger_mixed_or_road_missing", "tiger_not_checked", "nearmiss_20m_areas"):
    T[k] = T[k].astype(int)
cols = ["GEOID", "county", "crossings_official", "crossings_overture_30m", "crossings_marked_ford_flood", "flood_crossing_attribute_gap",
        "careful_areas", "careful_buildings", "careful_buildings_single", "careful_residents", "careful_homes",
        "tiger_agrees", "tiger_other_way", "tiger_mixed_or_road_missing", "tiger_not_checked", "nearmiss_20m_areas", "road_gap", "svi"]
T = T[cols]
out = T.copy(); out["careful_residents"] = out.careful_residents.round(1); out["careful_homes"] = out.careful_homes.round(1)
out["road_gap"] = out.road_gap.round(3); out["svi"] = out.svi.round(4)
out.to_csv("work/v4_per_tract_table.csv", index=False)
# fixed-width text
hdr = ["GEOID", "county", "lwc", "ovt30", "ford", "areas", "bldg", "single", "resid", "homes", "TIGER a/o/m/u", "nm", "roadgap", "SVI"]
rows = []
for r in T.itertuples():
    rows.append([r.GEOID, r.county, str(r.crossings_official), str(r.crossings_overture_30m), str(r.crossings_marked_ford_flood), str(r.careful_areas),
                 f"{r.careful_buildings:,}", f"{r.careful_buildings_single:,}", f"{r.careful_residents:,.0f}", f"{r.careful_homes:,.0f}",
                 f"{r.tiger_agrees}/{r.tiger_other_way}/{r.tiger_mixed_or_road_missing}/{r.tiger_not_checked}", str(r.nearmiss_20m_areas),
                 "n/s" if pd.isna(r.road_gap) else f"{r.road_gap:.3f}", "n/a" if pd.isna(r.svi) else f"{r.svi:.2f}"])
tot = ["TOTAL", f"{T.county.nunique()} counties", f"{T.crossings_official.sum():,}", f"{T.crossings_overture_30m.sum():,}", str(T.crossings_marked_ford_flood.sum()),
       f"{core.comp.nunique()}*", f"{T.careful_buildings.sum():,}", f"{T.careful_buildings_single.sum():,}", f"{T.careful_residents.sum():,.0f}", f"{T.careful_homes.sum():,.0f}", "", "", "", ""]
wd = [max(len(h), *(len(x[i]) for x in rows + [tot])) for i, h in enumerate(hdr)]
fmt = lambda cells: "  ".join(c.ljust(wd[i]) if i < 2 else c.rjust(wd[i]) for i, c in enumerate(cells)).rstrip()
legend = ("Census tracts holding at least one careful-set building: stranded when the official low-water crossings close,\n"
          "TIGER agrees, no 20 m near-miss. lwc = official crossings in the tract (TxGIO + TWDB); ovt30 = of those, with an\n"
          "Overture road within 30 m; ford = of those, marked by Overture as a ford or flood-prone road (0 everywhere: road_flags\n"
          "has no such value); areas = careful-set areas with buildings in the tract (*an area can span tracts; 216 distinct);\n"
          "bldg = their Microsoft footprints in the tract; single = of which behind a single crossing; resid, homes = 2020 Census\n"
          "block estimates; TIGER a/o/m/u = every stranded area here: TIGER agrees / TIGER has another way / mixed or road not in\n"
          "TIGER / too small to check; nm = TIGER-agreeing areas dropped by the 20 m near-miss test; roadgap = scorecard road gap\n"
          "(n/s = not scored); SVI = CDC SVI 2022 overall percentile. Sorted by buildings.\n")
txt = legend + "\n" + "\n".join([fmt(hdr), fmt(["-" * w for w in wd])] + [fmt(x) for x in rows] + [fmt(["-" * w for w in wd]), fmt(tot)]) + "\n"
open("work/v4_per_tract_table.txt", "w").write(txt)
print(txt[:3000]); print("...")
print("tracts", len(T), "counties", T.county.nunique(), "buildings", T.careful_buildings.sum(), "single", T.careful_buildings_single.sum(),
      "residents", round(T.careful_residents.sum(), 1), "homes", round(T.careful_homes.sum(), 1), "tracts without official crossing", int((T.crossings_official == 0).sum()),
      "road gap not scored", int(T.road_gap.isna().sum()), "road gap exactly 0", int((T.road_gap == 0).sum()), "width", max(len(l) for l in txt.splitlines()))
