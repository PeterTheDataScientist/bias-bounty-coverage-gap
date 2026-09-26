"""SUPERSEDED by nearmiss.py (v2, 24 Sep 2026). Kept as the record of the v1 test, whose whole-segment comparison
flagged 116 false near-misses (see discovery/README.md). It writes its own *_v1 files and never touches the v2 results.

Step 9, version 1. Near-miss test: does any road of a stranded area come within D metres of a road of the main
network somewhere other than at its crossings? If so the isolation may be a mapping gap (an unmapped short
link) rather than terrain, and the area is kept out of the named examples. Usage: python nearmiss_v1_wholeseg.py NET VAR"""
import argparse, sys, numpy as np, pandas as pd, pyarrow.parquet as pq, shapely, shapely.ops, pyproj
from shapely import STRtree
from common import EXTRA_SEGMENTS, OVT_ROADS, need
ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
ap.add_argument("network", choices=["base", "plus"]); ap.add_argument("variant", choices=["all", "strict", "fords"])
args = ap.parse_args(); NET, VAR = args.network, args.variant
ROADS = [OVT_ROADS] + ([EXTRA_SEGMENTS] if NET == "plus" else [])
need(f"work/edges_{NET}_{VAR}.parquet", f"work/graph_base_{NET}.parquet", f"work/cuts_{NET}_{VAR}.parquet",
     f"work/groups_b_{NET}_{VAR}.parquet", "work/lwc_unique.parquet", *ROADS)
tf = pyproj.Transformer.from_crs("EPSG:4326", "EPSG:3083", always_xy=True)
def P(c): x, y = tf.transform(c[:, 0], c[:, 1]); return np.column_stack([x, y])
e = pq.read_table(f"work/edges_{NET}_{VAR}.parquet"); b = pq.read_table(f"work/graph_base_{NET}.parquet", columns=["seg_id", "a0", "a1"])
su = e.column("su").to_numpy(); sv = e.column("sv").to_numpy(); cu = e.column("cu").to_numpy(); cut = e.column("cut").to_numpy()
lab = np.where(cut, -2, np.where(su & sv, cu, -1))
seg = b.column("seg_id").to_numpy(zero_copy_only=False); a0 = b.column("a0").to_numpy(); a1 = b.column("a1").to_numpy()
S_ids = set(seg[lab >= 0])
g1 = np.bincount(cu).argmax()                       # the main network after the cut
MAIN = pd.Index(pd.unique(seg[(cu == g1) & ~cut]))  # only roads that actually lead to the main network count
sel = np.where(pd.Series(seg).isin(S_ids).values)[0]
bys = {}
for i in sel:
    bys.setdefault(seg[i], []).append((a0[i], a1[i], lab[i]))
geoms = {}
for f in ROADS:
    pf = pq.ParquetFile(f)
    for rg in range(pf.num_row_groups):
        t = pf.read_row_group(rg, columns=["id", "geometry"]).to_pandas(); t = t[t.id.isin(S_ids)]
        if len(t): geoms.update(zip(t.id.values, shapely.transform(shapely.from_wkb(t.geometry.values), P)))
sg, sl = [], []
for sid, parts in bys.items():
    for x0, x1, lb in parts:
        if lb >= 0:
            try: sg.append(shapely.ops.substring(geoms[sid], x0, x1, normalized=True))
            except Exception: sg.append(geoms[sid])
            sl.append(lb)
sg = np.array(sg, dtype=object); sl = np.array(sl)
st = STRtree(sg)
# main-network pieces near stranded ones (whole segments are fine here: a main segment never contains stranded parts
# except the crossing segment itself, which is excluded by distance to the crossing below)
# prefilter by bounding box in lon/lat before projecting anything
inv = pyproj.Transformer.from_crs("EPSG:3083", "EPSG:4326", always_xy=True)
env = [shapely.bounds(g) for g in sg]
boxes = [shapely.box(*inv.transform(b[0] - 100, b[1] - 100), *inv.transform(b[2] + 100, b[3] + 100)) for b in env]
bt = STRtree(boxes)
mg = []
for f in ROADS:
    pf = pq.ParquetFile(f)
    for rg in range(pf.num_row_groups):
        t = pf.read_row_group(rg, columns=["id", "bbox", "geometry"]).to_pandas()
        bb = pd.DataFrame(list(t.bbox.values))
        cand = np.unique(bt.query(shapely.box(bb.xmin.values, bb.ymin.values, bb.xmax.values, bb.ymax.values), predicate="intersects")[0])
        if len(cand) == 0: continue
        t = t.iloc[cand]; t = t[(MAIN.get_indexer(t.id.values) >= 0) & ~t.id.isin(S_ids)]
        if len(t) == 0: continue
        g = shapely.transform(shapely.from_wkb(t.geometry.values), P)
        hit = np.unique(st.query(g, predicate="dwithin", distance=40)[0])
        mg += list(g[hit])
mg = np.array(mg, dtype=object); mt = STRtree(mg)
C = pd.read_parquet(f"work/cuts_{NET}_{VAR}.parquet").merge(pd.read_parquet("work/lwc_unique.parquet")[["src", "src_id", "x", "y"]], on=["src", "src_id"])
cp = STRtree(shapely.points(C.x.values, C.y.values))
# cut an 80 m disc around every crossing out of the stranded pieces, so the crossing itself never counts,
# but the far end of a long piece still does
cpts = shapely.points(C.x.values, C.y.values)
ci = cp.query(sg, predicate="dwithin", distance=80)
sg2 = sg.copy()
for k in np.unique(ci[0]):
    discs = shapely.union_all(shapely.buffer(cpts[ci[1][ci[0] == k]], 80))
    sg2[k] = shapely.difference(sg[k], discs)
ok = ~shapely.is_empty(sg2)
res = {}
for D in (10, 20, 40):
    si, mi = mt.query(sg2[ok], predicate="dwithin", distance=D)
    res[D] = set(sl[ok][si]) if len(si) else set()
# closest stranded/main pair per flagged group at 20 m, for the imagery check
si, mi = mt.query(sg2[ok], predicate="dwithin", distance=20)
if len(si):
    A_ = sg2[ok][si]; M_ = mg[mi]; dd = shapely.distance(A_, M_)
    P = pd.DataFrame(dict(comp=sl[ok][si], d=dd, k=np.arange(len(si)))).sort_values("d").drop_duplicates("comp")
    pts = [shapely.ops.nearest_points(A_[k], M_[k]) for k in P.k]
    P["x1"] = [p[0].x for p in pts]; P["y1"] = [p[0].y for p in pts]; P["x2"] = [p[1].x for p in pts]; P["y2"] = [p[1].y for p in pts]
    P.drop(columns="k").to_csv(f"work/nearmiss_pairs_{NET}_{VAR}_v1.csv", index=False)
G = pd.read_parquet(f"work/groups_b_{NET}_{VAR}.parquet")
for D in (10, 20, 40): G[f"nearmiss_{D}m"] = G.comp.isin(res[D])
G.to_parquet(f"work/groups_b_{NET}_{VAR}_nearmiss_v1.parquet")
for D in (10, 20, 40):
    m = G[f"nearmiss_{D}m"]
    print(f"near-miss within {D} m: groups {int(m.sum())} of {len(G)}, buildings {int(G.bldg[m].sum())} of {int(G.bldg.sum())}; "
          f"single-crossing buildings {int(G.bldg[m & G.single_crossing].sum())} of {int(G.bldg[G.single_crossing].sum())}")
