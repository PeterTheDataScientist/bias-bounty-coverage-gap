"""Step 26. The six named places, tract by tract.

An area can span tracts (the Bexar area's 1,865 buildings lie in two), so this script splits every named area by the tract each building lies in (the point-in-polygon tract that
lwc_buildings.py gave it) and gives, per tract: buildings, residents and homes (2020 Census blocks, the per-building
shares block_pop_v4.py wrote for plus/strict, whose area sums equal block_pop.py's), the scorecard road gap and the
SVI. It also lists each area's crossings with the tract they sit in and the Overture flags of the segment they are on.
Road gap: transport_gap and _t_def of work/bias_components.parquet (scorecard_inputs.py; the road component is the
scored column's in every tract); _t_def False means the tract has no road score. SVI: svi_overall of the challenge's
strata table, so the outputs stay in work/.
Outputs: work/v5_example_tracts.csv, work/v5_example_tracts.txt, work/v5_example_tracts.json
"""
import argparse, json
import numpy as np, pandas as pd
from common import COMPONENTS, need
from v4_common import careful_set, strata, county_names

argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter).parse_args()
need(COMPONENTS, "work/v4_blockpop_bldg_plus_strict.parquet", "work/v4_blocks_cache.parquet", "work/edges_plus_strict.parquet",
     "work/cuts_plus_strict.parquet", "work/lwc_unique.parquet")

EXAMPLES = [(979, "Bexar"), (623, "Johnson"), (921, "Guadalupe"), (952, "Hays"), (1030, "Bee"), (266, "Kerr")]
G, core, Bc = careful_set()
assert set(c for c, _ in EXAMPLES) <= set(core.comp), "every named place is in the careful set"
bp = pd.read_parquet("work/v4_blockpop_bldg_plus_strict.parquet", columns=["rg", "row", "comp", "block", "ppl_blk", "hu_blk"])
B = Bc.merge(bp, on=["rg", "row", "comp"], how="left", validate="one_to_one")
assert B.ppl_blk.notna().all()
K = pd.read_parquet(COMPONENTS, columns=["GEOID", "transport_gap", "_t_def"]).rename(columns={"_t_def": "t_def"})
S = strata(["GEOID", "svi_overall", "ur_class"])
names = county_names()
# crossings around each area
X = pd.read_parquet("work/edges_plus_strict.parquet", columns=["cu", "cv", "su", "sv", "cut"]); Xc = X[X.cut]; del X
touch = pd.concat([pd.DataFrame(dict(comp=Xc.cu[Xc.su].values, edge=Xc.index[Xc.su].values)),
                   pd.DataFrame(dict(comp=Xc.cv[Xc.sv].values, edge=Xc.index[Xc.sv].values))]).drop_duplicates()
C = pd.read_parquet("work/cuts_plus_strict.parquet", columns=["edge", "src", "src_id"]).merge(
    pd.read_parquet("work/lwc_unique.parquet", columns=["src", "src_id", "GEOID", "road_eff", "stream", "lwc_type", "seg_flags"]), on=["src", "src_id"])
touch = touch.merge(C, on="edge")
rows, out, txt = [], {}, []
def txt_or(v, alt): return v if isinstance(v, str) and v.strip() else alt
KB = pd.read_parquet("work/v4_blocks_cache.parquet", columns=["GEOID", "POP100", "HU100", "nb"]).rename(columns={"GEOID": "block"})
def largest_block(b):
    """The block holding most of the area's footprints: its share of them, and the block's own Census counts."""
    k = b.groupby("block").size().sort_values(ascending=False)
    blk, n = k.index[0], int(k.iloc[0]); r = KB[KB.block == blk].iloc[0]
    return dict(block=blk, area_footprints_in_it=n, share_of_area_footprints=round(n / len(b), 4), block_residents=int(r.POP100),
                block_homes=int(r.HU100), block_footprints=int(r.nb), blocks_touched=int(len(k)))
for comp, county in EXAMPLES:
    b = B[B.comp == comp]; g = G[G.comp == comp].iloc[0]
    t = b.groupby("GEOID").agg(buildings=("row", "size"), residents=("ppl_blk", "sum"), homes=("hu_blk", "sum")).reset_index()
    t = t.merge(K, on="GEOID", how="left").merge(S, on="GEOID", how="left").sort_values(["buildings", "GEOID"], ascending=[False, True])
    t["block_tract_mismatch"] = [int((b[b.GEOID == x].block.str[:11] != x).sum()) for x in t.GEOID]
    cr = touch[touch.comp == comp].sort_values(["src", "src_id"])
    for r in t.itertuples():
        rows.append(dict(area=comp, county=county, tract=r.GEOID, buildings=int(r.buildings), residents=round(r.residents, 1), homes=round(r.homes, 1),
                         road_gap=round(float(r.transport_gap), 4) if r.t_def else None, road_gap_scored=bool(r.t_def), svi=r.svi_overall, ur_class=r.ur_class,
                         blocks_in_other_tract=r.block_tract_mismatch))
    out[county] = dict(area=comp, buildings=int(b.shape[0]), residents=round(float(b.ppl_blk.sum()), 1), homes=round(float(b.hu_blk.sum()), 1),
                       single_crossing=bool(g.single_crossing), cut_pieces=int(g.n_cross), crossing_records=int(len(cr)),
                       crossings=[dict(id=f"{r.src}:{r.src_id}", road=txt_or(r.road_eff, "unnamed road"), stream=txt_or(r.stream, "unnamed stream"),
                                       type=txt_or(r.lwc_type, "TWDB record, no type"), tract=r.GEOID,
                                       overture_flags=r.seg_flags if isinstance(r.seg_flags, str) and r.seg_flags else "none") for r in cr.itertuples()],
                       tracts=[x for x in rows if x["area"] == comp],
                       largest_block=largest_block(b))
R = pd.DataFrame(rows); R.to_csv("work/v5_example_tracts.csv", index=False)
# plain text, no pipes, at most 118 characters a line
W = 118
txt += ["THE SIX NAMED PLACES, TRACT BY TRACT", "",
        "Buildings are Microsoft footprints in the careful-set area; residents and homes are 2020 Census block counts shared",
        "over the footprints in each block. Road gap = the scorecard's road (transport) gap for the tract; SVI = CDC social",
        "vulnerability percentile (strata table). Crossing IDs are the inventory's own (TxGIO or TWDB).", ""]
hdr = f"  {'tract':<13}{'buildings':>10}{'residents':>11}{'homes':>8}{'SVI':>7}  {'road gap':<11}{'class':<6}"
for comp, county in EXAMPLES:
    o = out[county]
    kinds = "single crossing" if o["single_crossing"] else f"{o['cut_pieces']} crossing pieces, {o['crossing_records']} inventory records"
    flags = sorted(set(c["overture_flags"] for c in o["crossings"]))
    txt.append(f"{county} (area {comp}): {o['buildings']:,} buildings, about {o['residents']:,.0f} residents, about {o['homes']:,.0f} homes")
    txt.append(f"  {kinds}; Overture flag on the crossing segments: {', '.join(flags)}")
    for c in o["crossings"]:
        txt.append(f"  {c['id']:<16}{c['road']} over {c['stream']} ({c['type']}), in tract {c['tract']}")
    lb = o["largest_block"]
    if lb["share_of_area_footprints"] >= 0.5 and lb["block_homes"] < 0.1 * lb["block_footprints"]:   # a block of mostly non-home footprints
        txt.append(f"  {lb['area_footprints_in_it']:,} of the {o['buildings']:,} buildings lie in one block ({lb['block']}) that holds "
                   f"{lb['block_homes']:,} homes and {lb['block_residents']:,} residents")
    txt.append(hdr)
    for x in o["tracts"]:
        txt.append(f"  {x['tract']:<13}{x['buildings']:>10,}{x['residents']:>11,.0f}{x['homes']:>8,.0f}{x['svi']:>7.2f}  "
                   f"{('%.3f' % x['road_gap']) if x['road_gap_scored'] else 'not scored':<11}{x['ur_class'] or '':<6}")
    txt.append("")
assert max(len(l) for l in txt) <= W, [l for l in txt if len(l) > W]
txt = [l.rstrip() for l in txt]
open("work/v5_example_tracts.txt", "w").write("\n".join(txt) + "\n")
json.dump(out, open("work/v5_example_tracts.json", "w"), indent=1, default=str)
print("\n".join(txt))
print("wrote work/v5_example_tracts.csv, .txt and .json:", {c: len(o["tracts"]) for c, o in out.items()}, "tracts per place")
