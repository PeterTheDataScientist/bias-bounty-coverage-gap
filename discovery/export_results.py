"""Step 23. The result tables this repository ships in ../results/, written from the run's own outputs so that a
rerun can be compared with them file for file. Every value comes from the two crossing inventories, OpenStreetMap,
Overture, the Microsoft footprints (counted per area or tract), TIGER roads, 2020 Census blocks and the scorecard's
road gap; nothing is copied or derived from the challenge's strata table (CC BY-SA 4.0), which join_strata.py joins
back locally. Licences: ../DATA_LICENCES.md.

  crossings.csv        one row per official crossing in the region (8,454): the inventory record, the Overture
                       segment it sits on, distance and name match, road flags, any OSM ford or flood tag nearby,
                       whether it is on the strict list, and the areas it cuts off
  areas.csv            one row per area that loses every road out when the strict list closes, on the network that
                       also counts service lanes and farm tracks (903 areas, 739 with buildings): buildings, residents
                       and homes from Census blocks, the crossings around it, the TIGER verdict, the near-miss flags,
                       and whether it is in the careful set that the entry's headline counts
  careful_tracts.csv   one row per tract holding a careful-set building (162), from per_tract_table.py without its
                       strata column
  crossing_tracts.csv  one row per scored tract holding an official crossing (1,848): the crossings, those Overture
                       carries and marks, the flood attribute gap and the scorecard road gap (flood_attr_gap.py)
  variants.csv         the six versions of the closure test (crossing list x road network) and the careful set,
                       with Census-block residents and homes (variants_v4.py)
  core_numbers.json    the careful set's counts, from core_numbers.py (its strata-table figures stay in work/)
  figures/             the two figures of figures.py

    python export_results.py                  from work/ into ../results/
    python export_results.py --out DIR        somewhere else, for example to compare a rerun with the shipped tables

The imagery audit's record in ../results/audit/ is not written here: the two readings are shipped as they were made,
and audit_summary.py and audit_agreement.py check and count them. Step 28, ncei_events.py, writes ../results/ncei/."""
import argparse, json, os, shutil
import numpy as np, pandas as pd
from common import arg_path, need

ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
ap.add_argument("--out", default=os.path.join(os.pardir, "results"), help="output folder (default ../results)")
args = ap.parse_args()
OUT = arg_path(args.out) if args.out != ap.get_default("out") else args.out
FIGS = ["figs/v4_region_map.png", "figs/v4_bexar_979.png"]
IN = ["work/lwc_unique_osm.parquet", "work/groups_b_plus_strict.parquet", "work/bldg_plus_strict.parquet",
      "work/edges_plus_strict.parquet", "work/cuts_plus_strict.parquet", "work/tiger_check_plus_strict.parquet",
      "work/tiger_check_plus_strict_multi.parquet", "work/core_numbers.json", "work/v4_variants_table.csv",
      "work/v4_per_tract_table.csv", "work/v4_flood_attr_gap_tracts.csv", *FIGS]
need(*IN, columns={"work/groups_b_plus_strict.parquet": ["nearmiss_20m", "pop_block", "hu_block"]})
STRATA_DERIVED = {"svi", "svi_overall", "pct_rural_residents", "svi_core", "svi_region", "cvi_ee_core", "cvi_ee_region",
                  "people_tract_ratio"}                 # values read or computed from the challenge's strata table
os.makedirs(os.path.join(OUT, "figures"), exist_ok=True)

# which crossings bound which stranded area (plus network, strict list)
X = pd.read_parquet("work/edges_plus_strict.parquet"); C = pd.read_parquet("work/cuts_plus_strict.parquet")
Xc = X[X.cut]
touch = pd.concat([pd.DataFrame(dict(comp=Xc.cu[Xc.su].values, edge=Xc.index[Xc.su].values)),
                   pd.DataFrame(dict(comp=Xc.cv[Xc.sv].values, edge=Xc.index[Xc.sv].values))]).drop_duplicates()
touch = touch.merge(C[["edge", "src", "src_id"]], on="edge")
touch["crossing"] = touch.src + ":" + touch.src_id

# crossings.csv
U = pd.read_parquet("work/lwc_unique_osm.parquet")
keep = ["src", "src_id", "lon", "lat", "GEOID", "county_src", "road", "road_eff", "stream", "lwc_type", "owner", "origin",
        "signage", "flood_freq", "exp_type", "desc", "has_name", "tier", "name_verified", "d_any", "d_named", "on_overture_30m",
        "seg_id", "seg_dist_m", "seg_cls", "seg_name", "seg_refs", "seg_flags", "seg_surface", "seg_osm_way", "seg_len_m",
        "osm_tag_30m", "osm_tag_60m", "osm_tag_100m", "osm_tag_200m"]
T = U[keep].copy()
key = T.src + ":" + T.src_id
T["in_strict_list"] = key.isin(set(C.src + ":" + C.src_id))
areas_of = touch.groupby("crossing").comp.agg(lambda s: " ".join(str(int(x)) for x in sorted(set(s))))
T["areas_plus_strict"] = key.map(areas_of).fillna("")
T[["lon", "lat"]] = T[["lon", "lat"]].round(7)
T[["d_any", "d_named", "seg_dist_m", "seg_len_m"]] = T[["d_any", "d_named", "seg_dist_m", "seg_len_m"]].round(2)
T.to_csv(os.path.join(OUT, "crossings.csv"), index=False)

# areas.csv
G = pd.read_parquet("work/groups_b_plus_strict.parquet")
R = pd.concat([pd.read_parquet("work/tiger_check_plus_strict.parquet"),
               pd.read_parquet("work/tiger_check_plus_strict_multi.parquet")])[["comp", "verdict", "frac_reach_main"]]
assert not R.comp.duplicated().any(), "an area was checked against TIGER twice"
B = pd.read_parquet("work/bldg_plus_strict.parquet")
county = U.assign(crossing=key)[["crossing", "county_src"]].merge(touch[["comp", "crossing"]], on="crossing")
A = pd.DataFrame({"area_id": G.comp, "buildings": G.bldg.astype(int), "residents_block": G.pop_block, "homes_block": G.hu_block,
                  "n_cross": G.n_cross.astype(int), "n_to_main": G.n_to_main.astype(int), "road_nodes": G.n_nodes.astype(int),
                  "single_crossing": G.single_crossing, "tract": G.GEOID})
A["county"] = A.area_id.map(county.groupby("comp").county_src.agg(lambda s: s.mode().iloc[0]))
A["crossings"] = A.area_id.map(touch.groupby("comp").crossing.agg(lambda s: " ".join(sorted(set(s)))))
xy = B.groupby("comp")[["lon", "lat"]].mean().round(6)
A["lon"] = A.area_id.map(xy.lon); A["lat"] = A.area_id.map(xy.lat)
for d in (10, 20, 40):
    A[f"nearmiss_{d}m"] = G[f"nearmiss_{d}m"].values
A = A.merge(R.rename(columns={"comp": "area_id", "verdict": "tiger_verdict", "frac_reach_main": "tiger_share_reaching_main"}),
            on="area_id", how="left")
A["careful_set"] = (A.tiger_verdict == "agrees_isolated") & ~A.nearmiss_20m & (A.buildings > 0)
A = A.sort_values(["buildings", "area_id"], ascending=[False, True])
A.to_csv(os.path.join(OUT, "areas.csv"), index=False)

# careful_tracts.csv: the per-tract table without its strata column
P = pd.read_csv("work/v4_per_tract_table.csv", dtype={"GEOID": str})
P.drop(columns=[c for c in P.columns if c in STRATA_DERIVED]).to_csv(os.path.join(OUT, "careful_tracts.csv"), index=False)

# crossing_tracts.csv: the flood attribute gap beside the scorecard road gap, every tract holding an official crossing
F = pd.read_csv("work/v4_flood_attr_gap_tracts.csv", dtype={"GEOID": str})
F = pd.DataFrame({"GEOID": F.GEOID, "crossings_official": F.n_official.astype(int), "crossings_overture_30m": F.n_on_ovt_30m.astype(int),
                  "crossings_marked_ford_flood": F.n_marked.astype(int), "flood_crossing_attribute_gap": F.flood_crossing_attribute_gap,
                  "road_gap": F.transport_gap.where(F.road_gap_defined).round(6)}).sort_values("GEOID")
F.to_csv(os.path.join(OUT, "crossing_tracts.csv"), index=False)

# variants.csv: the six versions and the careful set, Census-block residents and homes (no tract-ratio estimate: it
# rests on the strata table's population)
V = pd.read_csv("work/v4_variants_table.csv")
V = V.drop(columns=[c for c in V.columns if c in STRATA_DERIVED]).rename(columns={
    "residents": "residents_block", "homes": "homes_block", "single_residents": "single_residents_block", "single_homes": "single_homes_block"})
for c in ("crossings_closed", "all_stranded_groups"):
    V[c] = V[c].astype("Int64")
V.to_csv(os.path.join(OUT, "variants.csv"), index=False)

# core_numbers.json: the careful set's counts; its strata-table figures stay in work/core_numbers.json
N = json.load(open("work/core_numbers.json"))
json.dump({k: v for k, v in N.items() if k not in STRATA_DERIVED}, open(os.path.join(OUT, "core_numbers.json"), "w"), indent=1)
for f in FIGS:
    shutil.copyfile(f, os.path.join(OUT, "figures", os.path.basename(f)))
c = A[A.careful_set]
print(f"wrote {OUT}: crossings.csv {len(T):,} rows, areas.csv {len(A):,} rows ({int((A.buildings > 0).sum())} with buildings), "
      f"careful set {len(c)} areas, {int(c.buildings.sum()):,} buildings, {int(round(c.residents_block.sum())):,} residents, "
      f"{int(round(c.homes_block.sum())):,} homes; careful_tracts.csv {len(P)} rows, crossing_tracts.csv {len(F):,} rows, "
      f"variants.csv {len(V)} rows, core_numbers.json, figures/ ({len(FIGS)})")
