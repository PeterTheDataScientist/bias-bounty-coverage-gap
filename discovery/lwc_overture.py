"""Step 2. For every in-region crossing, find the Overture road segments within 100 m in the challenge's own
Overture roads file (release 2026-08-19.0, south-central-tx), with class, primary name, route refs,
road_flags, surface and the OSM way behind the segment (sources.record_id).

Output: work/lwc_seg_candidates.parquet (one row per crossing x segment pair within 100 m).
"""
import argparse, numpy as np, pandas as pd, pyarrow.parquet as pq, shapely, pyproj, time
from shapely import STRtree
from common import OVT_ROADS as F, need
argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter).parse_args()
need("work/lwc_all.parquet", F)
L = pd.read_parquet("work/lwc_all.parquet")
L = L[L.GEOID.notna()].reset_index(drop=True)
pts = shapely.points(L.x.values, L.y.values)
tree = STRtree(pts)
tf = pyproj.Transformer.from_crs("EPSG:4326", "EPSG:3083", always_xy=True)
def proj(c):
    x, y = tf.transform(c[:, 0], c[:, 1]); return np.column_stack([x, y])
pf = pq.ParquetFile(F)
cols = ["id", "names", "class", "subclass", "road_flags", "road_surface", "sources", "routes", "connectors", "geometry"]
out = []; t0 = time.time(); nseg = 0
for rg in range(pf.num_row_groups):
    t = pf.read_row_group(rg, columns=cols).to_pandas()
    nseg += len(t)
    geo = shapely.transform(shapely.from_wkb(t.geometry.values), proj)
    si, pi = tree.query(geo, predicate="dwithin", distance=100)
    if len(si) == 0: continue
    dist = shapely.distance(geo[si], pts[pi])
    sub = t.iloc[si].reset_index(drop=True)
    rec = pd.DataFrame(dict(
        lwc_row=pi, seg_id=sub.id.values, dist_m=dist, cls=sub["class"].values, subclass=sub.subclass.values,
        name=[(n or {}).get("primary") if isinstance(n, dict) else None for n in sub.names],
        refs=["|".join(sorted({str(r.get("ref")) for r in rs if r.get("ref")})) if rs is not None else "" for rs in sub.routes],
        flags=["|".join(sorted({v for f in fl for v in (f.get("values") if f.get("values") is not None else [])})) if fl is not None else "" for fl in sub.road_flags],
        surface=["|".join(sorted({s.get("value") for s in sf if s.get("value")})) if sf is not None else "" for sf in sub.road_surface],
        osm_way=[next((s.get("record_id") for s in src if s.get("dataset") == "OpenStreetMap" and s.get("property", "") in ("", None)), None)
                 if src is not None else None for src in sub.sources],
        n_conn=[len(c) if c is not None else 0 for c in sub.connectors],
        seg_len_m=shapely.length(geo[si])))
    out.append(rec)
    if rg % 10 == 0: print(rg, pf.num_row_groups, nseg, sum(len(o) for o in out), f"{time.time()-t0:.0f}s", flush=True)
C = pd.concat(out, ignore_index=True)
C.to_parquet("work/lwc_seg_candidates.parquet")
print("segments scanned", nseg, "pairs", len(C), "crossings with any segment within 100 m", C.lwc_row.nunique(), "of", len(L))
