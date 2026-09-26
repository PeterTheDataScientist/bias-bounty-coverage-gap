"""Step 5. How much of the official crossing list does OpenStreetMap mark as a ford or flood-prone road,
and does anything survive into Overture?"""
import argparse, numpy as np, pandas as pd, shapely, pyproj
from shapely import STRtree
from common import need
argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter).parse_args()
need("work/lwc_unique.parquet", "work/osm_fordtags.parquet", "work/osm_ways_with_fordnodes.parquet", "work/tracts_lwc.parquet")
tf = pyproj.Transformer.from_crs("EPSG:4326", "EPSG:3083", always_xy=True)
U = pd.read_parquet("work/lwc_unique.parquet")
F = pd.read_parquet("work/osm_fordtags.parquet").dropna(subset=["lon"])
W = pd.read_parquet("work/osm_ways_with_fordnodes.parquet")
fx, fy = tf.transform(F.lon.values, F.lat.values)
F["x"], F["y"] = fx, fy
tree = STRtree(shapely.points(fx, fy))
P = shapely.points(U.x.values, U.y.values)
for r in (30, 60, 100, 200):
    ui, fi = tree.query(P, predicate="dwithin", distance=r)
    U[f"osm_tag_{r}m"] = np.isin(np.arange(len(U)), ui)
    print(f"official crossings with an OSM ford/flood tag within {r} m: {U[f'osm_tag_{r}m'].sum()} of {len(U)} ({U[f'osm_tag_{r}m'].mean():.1%})")
# what kind of tag, at 100 m
ui, fi = tree.query(P, predicate="dwithin", distance=100)
k = pd.DataFrame(dict(u=ui, f=fi)).merge(F[["ford", "flood_prone", "hazard", "type"]].reset_index(drop=True), left_on="f", right_index=True)
print("tag kinds near crossings (100 m):", k.drop_duplicates("u").assign(kind=lambda d: np.where(d.ford.notna(), "ford=" + d.ford.astype(str), np.where(d.flood_prone.notna(), "flood_prone", "hazard"))).kind.value_counts().to_dict())
# is the Overture segment built from the same OSM way that carries the ford node?
U["seg_way"] = U.seg_osm_way.str.extract(r"^w(\d+)@")[0].astype("float")
wf = set(W.way.astype(float))
A = U[U.seg_id.notna()]
print("attributed crossings whose Overture segment comes from an OSM way with a ford node on it:", A.seg_way.isin(wf).sum(), "of", len(A))
print("  ...and of those, Overture flags seen:", A[A.seg_way.isin(wf)].seg_flags.fillna("").replace("", "(none)").value_counts().to_dict())
# timing: were the OSM ford tags there before Overture's OSM snapshot (latest source edit in the file: 2026-08-04)?
F["pre_snapshot"] = pd.to_datetime(F.ts) < pd.Timestamp("2026-08-04T02:00:00Z")
print("OSM ford/flood elements last edited before 2026-08-04:", F.pre_snapshot.mean().round(4), "of", len(F))
# by who lives there
S = pd.read_parquet("work/tracts_lwc.parquet")[["GEOID", "svi_overall", "svi_q"]]
U = U.merge(S, on="GEOID", how="left")
for col in ["ur_class", "svi_q"]:
    g = U.groupby(col, observed=True).agg(n=("src_id", "size"), osm100=("osm_tag_100m", "mean"), osm60=("osm_tag_60m", "mean"),
                                          on_ovt=("on_overture_30m", "mean"), bridge=("seg_flags", lambda s: s.fillna("").str.contains("is_bridge").mean()))
    print(g.round(3))
U.to_parquet("work/lwc_unique_osm.parquet")
