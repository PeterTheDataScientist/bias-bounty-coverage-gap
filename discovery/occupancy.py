"""Step 25. Occupancy of the careful set and of the six named places, from the same 2020 Census blocks as
block_pop.py and block_pop_v4.py.

What the block data holds. block_pop.py reads the Census Bureau's TIGERweb layer tigerWMS_Census2020/MapServer/10
(2020 Census blocks) and asks it for GEOID, POP100 and HU100 only. The layer's fields (checked 26 Sep 2026) are
identifiers, UR (urban or rural), land and water area, centroid, POP100 (residents) and HU100 (housing units): no
occupied or vacant count and no vacancy status, so neither a vacant share nor a seasonal share can come from it.
What it can give, per area (block values shared equally over the Microsoft footprints in each block, exactly as
block_pop_v4.py does):
  residents, homes (housing units), homes per resident and residents per home, homes per footprint;
  homes in blocks where the Census counted no resident at all (POP100 = 0 and HU100 > 0): every one of those homes
  was empty on Census Day (1 April 2020), whatever the reason. Block populations carry the 2020 disclosure-avoidance
  noise, housing-unit counts do not, so single small blocks are read with care; sums over areas are steadier.
Baselines from the same service: the region (the strata table's 6,010 tracts) and its rural tracts (ur_class),
summed over every block with one statistics query per condition (grouped by county and tract, Texas only),
cached in work/v5_tigerweb_tract_sums.json with the retrieval time (delete it to query again).
Inputs: work/v4_blockpop_bldg_plus_strict.parquet, work/v4_blocks_cache.parquet (block_pop_v4.py), the careful set.
Outputs (work/ only: they carry the strata table's ur_class): work/v5_occupancy.json, work/v5_occupancy.txt
"""
import argparse, json, os, time, urllib.parse, urllib.request
import numpy as np, pandas as pd
from common import UA, need
from v4_common import careful_set, strata

argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter).parse_args()
need("work/v4_blockpop_bldg_plus_strict.parquet", "work/v4_blocks_cache.parquet")

EXAMPLES = [(979, "Bexar"), (623, "Johnson"), (921, "Guadalupe"), (952, "Hays"), (1030, "Bee"), (266, "Kerr")]
URL = "https://tigerweb.geo.census.gov/arcgis/rest/services/TIGERweb/tigerWMS_Census2020/MapServer/10/query"
SUMS = "work/v5_tigerweb_tract_sums.json"
STATS = [{"statisticType": "sum", "onStatisticField": "POP100", "outStatisticFieldName": "pop"},
         {"statisticType": "sum", "onStatisticField": "HU100", "outStatisticFieldName": "hu"},
         {"statisticType": "count", "onStatisticField": "OBJECTID", "outStatisticFieldName": "blocks"}]
WHERE = {"all_blocks": "STATE='48'", "blocks_no_resident_with_homes": "STATE='48' AND POP100=0 AND HU100>0"}

def tract_sums():
    if os.path.exists(SUMS):
        return json.load(open(SUMS))
    out = dict(service=URL, retrieved_utc=time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime()), queries={})
    for k, w in WHERE.items():
        q = dict(where=w, outStatistics=json.dumps(STATS), groupByFieldsForStatistics="COUNTY,TRACT", f="json")
        for attempt in range(5):
            try:
                with urllib.request.urlopen(urllib.request.Request(URL + "?" + urllib.parse.urlencode(q), headers=UA), timeout=300) as r:
                    d = json.loads(r.read())
                if "features" in d and not d.get("exceededTransferLimit"): break
            except Exception as e:
                print("  retry", attempt, repr(e)[:120], flush=True)
            time.sleep(5 * (attempt + 1))
        else:
            raise SystemExit(f"TIGERweb statistics query failed: {w}")
        out["queries"][k] = dict(where=w, rows=sorted(([f["attributes"]["COUNTY"], f["attributes"]["TRACT"], f["attributes"]["pop"] or 0,
                                                        f["attributes"]["hu"] or 0, f["attributes"]["blocks"]] for f in d["features"]), key=lambda r: (r[0], r[1])))
    json.dump(out, open(SUMS, "w"), indent=0)
    return out

G, core, Bc = careful_set()
B = pd.read_parquet("work/v4_blockpop_bldg_plus_strict.parquet", columns=["rg", "row", "comp", "GEOID", "block", "ppl_blk", "hu_blk"])
K = pd.read_parquet("work/v4_blocks_cache.parquet", columns=["GEOID", "POP100", "HU100", "nb"]).rename(columns={"GEOID": "block"})
B = B.merge(K, on="block", how="left", validate="many_to_one")
assert B.POP100.notna().all() and B.ppl_blk.notna().all()
B["empty_block"] = (B.POP100 == 0) & (B.HU100 > 0)

def unit(b):
    res, homes, n = float(b.ppl_blk.sum()), float(b.hu_blk.sum()), len(b)
    blk = b.drop_duplicates("block")
    return dict(buildings=n, residents=round(res, 1), homes=round(homes, 1),
                homes_per_resident=round(homes / res, 3) if res else None, residents_per_home=round(res / homes, 2) if homes else None,
                homes_per_building=round(homes / n, 3),
                homes_in_blocks_with_no_resident=round(float(b.loc[b.empty_block, "hu_blk"].sum()), 1),
                share_of_homes_in_blocks_with_no_resident=round(float(b.loc[b.empty_block, "hu_blk"].sum()) / homes, 3) if homes else None,
                buildings_in_blocks_with_no_resident=int(b.empty_block.sum()),
                blocks=int(len(blk)), blocks_with_no_resident_but_homes=int(blk.empty_block.sum()),
                whole_blocks=dict(residents=int(blk.POP100.sum()), homes=int(blk.HU100.sum()), footprints=int(blk.nb.sum()),
                                  homes_per_resident=round(float(blk.HU100.sum() / blk.POP100.sum()), 3) if blk.POP100.sum() else None))

out = dict(generated_by="occupancy_v5.py", block_source="TIGERweb tigerWMS_Census2020 layer 10: POP100, HU100 (the fields block_pop.py reads)",
           block_layer_has_vacancy_fields=False,
           careful_set=unit(B[B.comp.isin(core.comp)]), lead_version=unit(B),
           examples={name: dict(area=c, **unit(B[B.comp == c])) for c, name in EXAMPLES})
# how common are areas with at least as many homes as residents (the Kerr pattern)?
A = B[B.comp.isin(core.comp)].groupby("comp").agg(buildings=("row", "size"), residents=("ppl_blk", "sum"), homes=("hu_blk", "sum"))
m = A.homes >= A.residents
out["careful_areas_homes_at_least_residents"] = dict(areas=int(m.sum()), of_areas=int(len(A)), buildings=int(A.buildings[m].sum()),
                                                      residents=round(float(A.residents[m].sum()), 1), homes=round(float(A.homes[m].sum()), 1),
                                                      areas_list=[int(c) for c in A.index[m]])
# baselines: region and its rural tracts, every block, same service
T = tract_sums()
S = strata(["GEOID", "ur_class"])
rows = {}
for k, qd in T["queries"].items():
    d = pd.DataFrame(qd["rows"], columns=["COUNTY", "TRACT", "pop", "hu", "blocks"])
    d["GEOID"] = "48" + d.COUNTY + d.TRACT
    rows[k] = d.merge(S, on="GEOID", how="inner")
a, z = rows["all_blocks"], rows["blocks_no_resident_with_homes"]
def base(mask_a, mask_z):
    pa_, ha_ = float(a.loc[mask_a, "pop"].sum()), float(a.loc[mask_a, "hu"].sum())
    return dict(tracts=int(mask_a.sum()), residents=int(pa_), homes=int(ha_), homes_per_resident=round(ha_ / pa_, 3),
                residents_per_home=round(pa_ / ha_, 2), homes_in_blocks_with_no_resident=int(z.loc[mask_z, "hu"].sum()),
                share_of_homes_in_blocks_with_no_resident=round(float(z.loc[mask_z, "hu"].sum()) / ha_, 4))
out["region"] = base(np.ones(len(a), bool), np.ones(len(z), bool))
out["region_rural_tracts"] = base((a.ur_class == "Rural").values, (z.ur_class == "Rural").values)
out["region_tracts_matched"] = int(len(a)); out["strata_tracts"] = int(len(S))
out["texas_all_blocks"] = dict(residents=int(sum(r[2] for r in T["queries"]["all_blocks"]["rows"])), homes=int(sum(r[3] for r in T["queries"]["all_blocks"]["rows"])),
                               blocks=int(sum(r[4] for r in T["queries"]["all_blocks"]["rows"])))
out["tigerweb_sums_retrieved_utc"] = T["retrieved_utc"]
# plain-text table
L = ["Homes and residents behind the crossings (2020 Census blocks, shared over footprints; homes = housing units)",
     "", f"{'':<22}{'buildings':>10}{'residents':>13}{'homes':>13}{'homes per':>11}{'residents':>11}{'homes per':>11}{'homes in blocks':>19}",
     f"{'':<22}{'':>10}{'':>13}{'':>13}{'resident':>11}{'per home':>11}{'building':>11}{'with no resident':>19}"]
def line(lbl, u):
    L.append(f"{lbl:<22}{u['buildings']:>10,}{u['residents']:>13,.1f}{u['homes']:>13,.1f}{u['homes_per_resident']:>11.2f}{u['residents_per_home']:>11.2f}"
             f"{u['homes_per_building']:>11.2f}{u['homes_in_blocks_with_no_resident']:>11,.1f} ({u['share_of_homes_in_blocks_with_no_resident']:.1%})")
for c, name in EXAMPLES: line(f"{name} (area {c})", out["examples"][name])
line("careful set (216)", out["careful_set"]); line("lead version (739)", out["lead_version"])
for lbl, k in (("region, all tracts", "region"), ("region, rural tracts", "region_rural_tracts")):
    u = out[k]
    L.append(f"{lbl:<22}{'':>10}{u['residents']:>13,}{u['homes']:>13,}{u['homes_per_resident']:>11.2f}{u['residents_per_home']:>11.2f}{'':>11}"
             f"{u['homes_in_blocks_with_no_resident']:>11,} ({u['share_of_homes_in_blocks_with_no_resident']:.1%})")
open("work/v5_occupancy.txt", "w").write("\n".join(L) + "\n")
json.dump(out, open("work/v5_occupancy.json", "w"), indent=1)
print("\n".join(L)); print(json.dumps({k: out[k] for k in ("careful_set", "region", "region_rural_tracts", "texas_all_blocks")}, indent=1))
