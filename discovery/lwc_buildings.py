"""Step 7. Count the buildings (Microsoft footprints from the challenge bucket) whose nearest road lies in a
stranded group, and estimate residents from each tract's people per footprint.
Usage: python lwc_buildings.py NETWORK VARIANT"""
import argparse, sys, time, numpy as np, pandas as pd, pyarrow.parquet as pq, shapely, shapely.ops, pyproj, geopandas as gpd
from shapely import STRtree
from common import EXTRA_SEGMENTS, MS_BUILDINGS as MS, OVT_ROADS, STRATA, TRACT_BUILDINGS, TRACTS, need
ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
ap.add_argument("network", choices=["base", "plus"]); ap.add_argument("variant", choices=["all", "strict", "fords"])
args = ap.parse_args(); NET, VAR = args.network, args.variant
ROADS = [OVT_ROADS]
if NET == "plus": ROADS.append(EXTRA_SEGMENTS)
need(f"work/graph_base_{NET}.parquet", f"work/edges_{NET}_{VAR}.parquet", f"work/groups_{NET}_{VAR}.parquet", *ROADS, MS, TRACTS, TRACT_BUILDINGS, STRATA)
E = pd.read_parquet(f"work/graph_base_{NET}.parquet", columns=["seg_id", "a0", "a1"])
X = pd.read_parquet(f"work/edges_{NET}_{VAR}.parquet")
E["label"] = np.where(X.cut, -2, np.where(X.su & X.sv, X.cu, -1))
del X
tf = pyproj.Transformer.from_crs("EPSG:4326", "EPSG:3083", always_xy=True)
def proj(c):
    x, y = tf.transform(c[:, 0], c[:, 1]); return np.column_stack([x, y])
S_ids = set(E.seg_id[E.label >= 0])
lab = {}
for sid, a0, a1, lb in zip(E.seg_id.values, E.a0.values, E.a1.values, E.label.values):
    lab.setdefault(sid, []).append((a0, a1, lb))
del E
def subedges(t):
    og, ol = [], []
    g = shapely.transform(shapely.from_wkb(t.geometry.values), proj)
    for sid, geom in zip(t.id.values, g):
        for a0, a1, lb in lab[sid]:
            try: s = shapely.ops.substring(geom, a0, a1, normalized=True)
            except Exception: s = geom
            og.append(s); ol.append(lb)
    return og, ol
sg, sl = [], []
for f in ROADS:
    pf = pq.ParquetFile(f)
    for rg in range(pf.num_row_groups):
        t = pf.read_row_group(rg, columns=["id", "geometry"]).to_pandas()
        t = t[t.id.isin(S_ids)]
        if len(t):
            g, l = subedges(t); keep = [i for i, x in enumerate(l) if x >= 0]
            sg += [g[i] for i in keep]; sl += [l[i] for i in keep]
sg = np.array(sg, dtype=object); sl = np.array(sl)
st = STRtree(sg)
lg, ll = [], []
for f in ROADS:
    pf = pq.ParquetFile(f)
    for rg in range(pf.num_row_groups):
        t = pf.read_row_group(rg, columns=["id", "geometry"]).to_pandas()
        g = shapely.transform(shapely.from_wkb(t.geometry.values), proj)
        hit = np.unique(st.query(g, predicate="dwithin", distance=400)[0])
        if len(hit):
            g2, l2 = subedges(t.iloc[hit]); lg += g2; ll += l2
lg = np.array(lg, dtype=object); ll = np.array(ll); lt = STRtree(lg)
print(NET, VAR, "stranded sub-edges", len(sg), "local sub-edges", len(lg), flush=True)
pf = pq.ParquetFile(MS); bl = []
for rg in range(pf.num_row_groups):
    b = pf.read_row_group(rg, columns=["bbox"]).column("bbox").to_pandas()
    x = np.array([(d["xmin"] + d["xmax"]) / 2 for d in b]); y = np.array([(d["ymin"] + d["ymax"]) / 2 for d in b])
    pts = shapely.points(proj(np.column_stack([x, y])))
    cand = np.unique(st.query(pts, predicate="dwithin", distance=300)[0])
    if len(cand) == 0: continue
    pi, ei = lt.query_nearest(pts[cand], max_distance=300, return_distance=False, all_matches=False)
    labs = ll[ei]; ok = labs >= 0
    for p, L_ in zip(cand[pi[ok]], labs[ok]): bl.append((rg, int(p), int(L_), x[p], y[p]))
B = pd.DataFrame(bl, columns=["rg", "row", "comp", "lon", "lat"])
tr = pd.read_parquet(TRACTS)
tr = gpd.GeoDataFrame(tr[["GEOID"]], geometry=shapely.from_wkb(tr.geometry), crs="EPSG:4326")
gb = gpd.GeoDataFrame(B, geometry=gpd.points_from_xy(B.lon, B.lat), crs="EPSG:4326")
B = pd.DataFrame(gpd.sjoin(gb, tr, how="left", predicate="within").drop(columns=["geometry", "index_right"]))
B = B[~B.duplicated(["rg", "row"])]
K = pd.read_parquet(TRACT_BUILDINGS)[["GEOID", "ms_bldg"]]          # footprints per tract, bbox centre (scorecard_inputs.py)
S = pd.read_parquet(STRATA)[["GEOID", "pop_total", "svi_overall", "ur_class"]]
B = B.merge(K, on="GEOID", how="left").merge(S, on="GEOID", how="left")
B["ppl"] = np.where(B.ms_bldg > 0, B.pop_total / B.ms_bldg, 0)
B.to_parquet(f"work/bldg_{NET}_{VAR}.parquet")
G = pd.read_parquet(f"work/groups_{NET}_{VAR}.parquet")
agg = B.groupby("comp").agg(bldg=("row", "size"), people=("ppl", "sum"), svi=("svi_overall", "mean"),
                            GEOID=("GEOID", lambda s: s.mode().iloc[0] if s.notna().any() else None))
G = G.merge(agg, left_on="comp", right_index=True, how="left").fillna({"bldg": 0, "people": 0})
G.to_parquet(f"work/groups_b_{NET}_{VAR}.parquet")
s1 = G[G.single_crossing]
print(NET, VAR, "buildings stranded", int(G.bldg.sum()), "people", int(G.people.sum()), "groups with buildings", int((G.bldg > 0).sum()),
      "| single crossing: groups", int((s1.bldg > 0).sum()), "buildings", int(s1.bldg.sum()), "people", int(s1.people.sum()), flush=True)
