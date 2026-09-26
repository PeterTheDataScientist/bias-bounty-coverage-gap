"""Step 15. The six versions (crossing list x road network) in one table, with Census-block residents and homes for
every version (block_pop_v4.py) and the careful set marked. Areas and buildings are recomputed from the groups_b
files and checked against work/variants_table.csv (disc_numbers.py).
  crossing list  all    = every official crossing attributed to an Overture segment (lwc_graph.py VAR=all)
                 strict = name-verified, or unnamed and within 15 m (tiers A and B)
                 fords  = strict AND the TxGIO type is VENTED FORD or UNVENTED FORD
  network        base   = the challenge's Overture roads file (7 classes)
                 plus   = base + service, track, living_street, unknown from the same release (every lane and track is a way out)
  an 'area' is a stranded group with at least one building; 'single' = the area touches exactly one cut crossing that leads
  straight to the main network (lwc_graph.py).
Outputs: work/v4_variants_table.csv, work/v4_variants_table.txt, work/v4_variants.json
"""
import argparse, json, numpy as np, pandas as pd
from common import need
from v4_common import tiger_results
argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter).parse_args()
V6 = [(n, v) for n in ("base", "plus") for v in ("all", "strict", "fords")]
need("work/variants_table.csv", *(f"work/{k}_{n}_{v}.parquet" for k in ("groups_b", "v4_blockpop_groups", "cuts") for n, v in V6),
     columns={"work/groups_b_plus_strict.parquet": ["nearmiss_20m", "pop_block", "hu_block"]})
rows = []
old = pd.read_csv("work/variants_table.csv")
for net in ("base", "plus"):
    for var in ("all", "strict", "fords"):
        G = pd.read_parquet(f"work/groups_b_{net}_{var}.parquet", columns=["comp", "single_crossing", "bldg", "people"])
        P = pd.read_parquet(f"work/v4_blockpop_groups_{net}_{var}.parquet")
        G = G.merge(P, on="comp", how="left")
        assert (G.loc[G.bldg > 0, "n_bldg"] == G.loc[G.bldg > 0, "bldg"]).all()
        C = pd.read_parquet(f"work/cuts_{net}_{var}.parquet", columns=["edge"])
        g = G[G.bldg > 0]; s = g[g.single_crossing]
        rows.append(dict(version=f"{net}/{var}", network=net, crossings=var, crossings_closed=len(C), areas=len(g), buildings=int(g.bldg.sum()),
                         single_areas=len(s), single_buildings=int(s.bldg.sum()),
                         residents=int(round(g.pop_block.sum())), homes=int(round(g.hu_block.sum())),
                         single_residents=int(round(s.pop_block.sum())), single_homes=int(round(s.hu_block.sum())),
                         unlocated_buildings=int((g.n_bldg - g.n_located).sum()), people_tract_ratio=int(round(g.people.sum())),
                         all_stranded_groups=len(G)))
# careful set, in two steps, on plus/strict
R = tiger_results(); a = R[R.verdict == "agrees_isolated"]
G = pd.read_parquet("work/groups_b_plus_strict.parquet", columns=["comp", "single_crossing", "bldg", "people", "nearmiss_20m", "pop_block", "hu_block"])
for lab, m in (("plus/strict + TIGER agrees", G.comp.isin(set(a.comp)) & (G.bldg > 0)),
               ("CAREFUL SET: + TIGER agrees + no 20 m near-miss", G.comp.isin(set(a.comp)) & ~G.nearmiss_20m & (G.bldg > 0))):
    g = G[m]; s = g[g.single_crossing]
    rows.append(dict(version=lab, network="plus", crossings="strict", crossings_closed=np.nan, areas=len(g), buildings=int(g.bldg.sum()),
                     single_areas=len(s), single_buildings=int(s.bldg.sum()), residents=int(round(g.pop_block.sum())), homes=int(round(g.hu_block.sum())),
                     single_residents=int(round(s.pop_block.sum())), single_homes=int(round(s.hu_block.sum())), unlocated_buildings=0,
                     people_tract_ratio=int(round(g.people.sum())), all_stranded_groups=np.nan))
V = pd.DataFrame(rows)
# consistency with disc_numbers.py's table
chk = []
for r in old.itertuples():
    v = V[V.version == f"{r.network}/{r.crossings}"].iloc[0]
    for a_, b_ in (("cut", "crossings_closed"), ("groups", "areas"), ("buildings", "buildings"), ("single_groups", "single_areas"), ("single_buildings", "single_buildings"), ("people", "people_tract_ratio")):
        if int(getattr(r, a_)) != int(v[b_]): chk.append(f"{r.network}/{r.crossings} {a_}: old {getattr(r, a_)} v4 {v[b_]}")
V.to_csv("work/v4_variants_table.csv", index=False)
lab = {"all": "all crossings", "strict": "strict list", "fords": "strict, fords only"}
hdr = ["network", "crossing list", "closed", "areas", "buildings", "single: areas", "single: bldgs", "residents", "homes"]
lines = []
for r in V.itertuples():
    if r.version.startswith(("plus/strict +", "CAREFUL")):
        net, cl = "plus", ("  then TIGER agrees" if "CAREFUL" not in r.version else "  CAREFUL SET (TIGER + near-miss)")
        closed = "-"
    else:
        net, cl, closed = r.network, lab[r.crossings], f"{int(r.crossings_closed):,}"
    lines.append([net, cl, closed, f"{r.areas:,}", f"{r.buildings:,}", f"{r.single_areas:,}", f"{r.single_buildings:,}", f"{r.residents:,}", f"{r.homes:,}"])
wd = [max(len(h), *(len(l[i]) for l in lines)) for i, h in enumerate(hdr)]
fmt = lambda cells: "  ".join(c.ljust(wd[i]) if i < 2 else c.rjust(wd[i]) for i, c in enumerate(cells))
txt = [fmt(hdr), fmt(["-" * w for w in wd])] + [fmt(l) for l in lines]
note = ("\nnetwork: base = the challenge's Overture roads file; plus = base + service, track, living_street and unknown roads (same release).\n"
        "crossing list: all = every official crossing on an Overture segment; strict = road name matches, or unnamed within 15 m;\n"
        "fords = strict and inventory type vented or unvented ford. closed = crossings cut. areas = stranded areas with at least one\n"
        "building. single = areas behind exactly one crossing. residents and homes = 2020 Census block counts shared over the\n"
        "Microsoft footprints in each block. The two indented rows are the lead version (plus, strict) after the checks.")
open("work/v4_variants_table.txt", "w").write("\n".join(txt) + "\n" + note + "\n")
json.dump(dict(rows=V.to_dict(orient="records"), inconsistencies_vs_variants_table_csv=chk), open("work/v4_variants.json", "w"), indent=1, default=str)
print("\n".join(txt)); print(note); print("inconsistencies vs variants_table.csv:", chk or "none")
print(V[["version", "all_stranded_groups", "areas", "unlocated_buildings", "people_tract_ratio", "single_residents", "single_homes"]].to_string())
