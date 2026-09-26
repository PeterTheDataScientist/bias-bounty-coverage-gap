"""Step 6. Which buildings lose every road connection when the official low-water crossings close?

Graph: Overture road segments split at their connectors, undirected. Network 'base' is the challenge file
(7 road classes). Network 'plus' adds the classes the challenge file leaves out (service, track,
living_street, unknown) from the same Overture release, so every private lane and farm track counts as a
possible way out. For each variant of the crossing list, remove the sub-edge that holds each crossing.
Nodes that belonged to the main network and no longer reach it are 'stranded'. A stranded group touched by
exactly one crossing that leads straight to the main network sits behind a single crossing.

Usage: python lwc_graph.py NETWORK VARIANT   (NETWORK base|plus; VARIANT all|strict|fords)
Outputs: work/graph_base_{NETWORK}.parquet (cached), work/edges_{NETWORK}_{VARIANT}.parquet,
         work/groups_{NETWORK}_{VARIANT}.parquet, work/cuts_{NETWORK}_{VARIANT}.parquet
"""
import argparse, sys, os, time, numpy as np, pandas as pd, pyarrow.parquet as pq, shapely, pyproj
from scipy.sparse import coo_matrix
from scipy.sparse.csgraph import connected_components
from common import EXTRA_SEGMENTS, OVT_ROADS, need
ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
ap.add_argument("network", choices=["base", "plus"]); ap.add_argument("variant", choices=["all", "strict", "fords"])
args = ap.parse_args(); NET, VAR = args.network, args.variant
ROADS = [OVT_ROADS]
if NET == "plus": ROADS.append(EXTRA_SEGMENTS)
need("work/lwc_unique.parquet", OVT_ROADS, *([] if os.path.exists(f"work/graph_base_{NET}.parquet") else ROADS[1:]))
U = pd.read_parquet("work/lwc_unique.parquet")
A = U[U.seg_id.notna()].copy()
if VAR == "strict": A = A[A.tier.isin(["A_name_verified", "B_unnamed_within_15m"])]
elif VAR == "fords": A = A[A.tier.isin(["A_name_verified", "B_unnamed_within_15m"]) & A.lwc_type.isin(["VENTED FORD", "UNVENTED FORD"])]
elif VAR != "all": raise SystemExit("variant?")
print(NET, VAR, "crossings cut:", len(A), flush=True)
tf = pyproj.Transformer.from_crs("EPSG:4326", "EPSG:3083", always_xy=True)
def proj(c):
    x, y = tf.transform(c[:, 0], c[:, 1]); return np.column_stack([x, y])
base = f"work/graph_base_{NET}.parquet"
t0 = time.time()
if not os.path.exists(base):
    nid = {}; eu = []; ev = []; eseg = []; ea0 = []; ea1 = []; ecl = []
    for f in ROADS:
        pf = pq.ParquetFile(f)
        for rg in range(pf.num_row_groups):
            t = pf.read_row_group(rg, columns=["id", "class", "connectors"]).to_pandas()
            for sid, cl, cons in zip(t.id.values, t["class"].values, t.connectors.values):
                if cons is None or len(cons) < 2: continue
                ids = [nid.setdefault(c["connector_id"], len(nid)) for c in cons]
                ats = [c["at"] for c in cons]
                for k in range(len(ids) - 1):
                    eu.append(ids[k]); ev.append(ids[k + 1]); eseg.append(sid); ea0.append(ats[k]); ea1.append(ats[k + 1]); ecl.append(cl)
    E = pd.DataFrame(dict(u=np.array(eu, np.int64), v=np.array(ev, np.int64), seg_id=eseg, a0=np.array(ea0), a1=np.array(ea1), cls=ecl))
    del eu, ev, eseg, ea0, ea1, ecl
    E.to_parquet(base)
    print("built graph", len(nid), "nodes", len(E), "edges", f"{time.time()-t0:.0f}s", flush=True)
else:
    E = pd.read_parquet(base)
n = int(max(E.u.max(), E.v.max())) + 1
need = set(A.seg_id)
geoms = {}
pf = pq.ParquetFile(ROADS[0])
for rg in range(pf.num_row_groups):
    t = pf.read_row_group(rg, columns=["id", "geometry"]).to_pandas()
    t = t[t.id.isin(need)]
    if len(t): geoms.update(zip(t.id.values, shapely.transform(shapely.from_wkb(t.geometry.values), proj)))
A["pos"] = [shapely.line_locate_point(geoms[s], shapely.Point(x, y), normalized=True) for s, x, y in zip(A.seg_id, A.x, A.y)]
sub = E[E.seg_id.isin(need)]
bys = {}
for i, s_, a0, a1 in zip(sub.index.values, sub.seg_id.values, sub.a0.values, sub.a1.values):
    bys.setdefault(s_, []).append((i, a0, a1))
A["edge"] = [next((i for i, a0, a1 in bys[s] if a0 <= p + 1e-9 and p <= a1 + 1e-9), bys[s][0][0]) for s, p in zip(A.seg_id, A["pos"])]
A[["src", "src_id", "GEOID", "seg_id", "pos", "edge", "tier", "lwc_type"]].to_parquet(f"work/cuts_{NET}_{VAR}.parquet")
cut = np.zeros(len(E), bool); cut[A.edge.unique()] = True
def comps(mask):
    m = coo_matrix((np.ones(mask.sum()), (E.u.values[mask], E.v.values[mask])), shape=(n, n))
    return connected_components(m, directed=False)[1]
c0 = comps(np.ones(len(E), bool)); c1 = comps(~cut)
g0 = np.bincount(c0).argmax(); g1 = np.bincount(c1[c0 == g0]).argmax()
stranded = (c0 == g0) & (c1 != g1)
print("main network nodes", int((c0 == g0).sum()), "stranded nodes", int(stranded.sum()), "groups", len(np.unique(c1[stranded])), flush=True)
out = pd.DataFrame(dict(cu=c1[E.u.values], cv=c1[E.v.values], su=stranded[E.u.values], sv=stranded[E.v.values], cut=cut))
out.to_parquet(f"work/edges_{NET}_{VAR}.parquet")
Ec = out[out.cut]
rows = []
for cs, co, ss in (("cu", "cv", "su"), ("cv", "cu", "sv")):
    x = Ec[Ec[ss]]
    rows.append(pd.DataFrame(dict(comp=x[cs].values, edge=x.index.values, other=x[co].values)))
T = pd.concat(rows).drop_duplicates()
T["to_main"] = T.other == g1
G = T.groupby("comp").agg(n_cross=("edge", "nunique"), n_to_main=("to_main", "sum")).reset_index()
nn = pd.Series(c1[stranded]).value_counts().rename("n_nodes")
G = G.merge(nn, left_on="comp", right_index=True, how="right").fillna({"n_cross": 0, "n_to_main": 0})
G["single_crossing"] = (G.n_cross == 1) & (G.n_to_main == 1)
G.to_parquet(f"work/groups_{NET}_{VAR}.parquet")
print("groups", len(G), "single-crossing groups", int(G.single_crossing.sum()), f"{time.time()-t0:.0f}s")
