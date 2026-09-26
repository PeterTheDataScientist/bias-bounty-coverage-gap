"""SUPERSEDED by nearmiss_imgs.py for the v2 near-miss pairs; kept as the record of the first imagery sample.

Imagery check of the near-miss flag: for a random sample of flagged areas, find the closest point between the
area's roads (outside the 80 m discs around its crossings) and a road of the main network, and render a 250 m
window of USGS orthoimagery there. I classify each by eye: joined in reality, separated, or unclear."""
import argparse, sys, io, duckdb, numpy as np, pandas as pd, pyarrow.parquet as pq, shapely, shapely.ops, pyproj, urllib.request, matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from PIL import Image
from shapely import STRtree
from common import EXTRA_SEGMENTS, OVT_ROADS, makedirs, need
ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
ap.add_argument("n_sample", nargs="?", type=int, default=30, help="areas to draw (default 30)")
N_SAMPLE = ap.parse_args().n_sample
ROADS = [OVT_ROADS, EXTRA_SEGMENTS]
need("work/groups_b_plus_strict.parquet", "work/stranded_segs_plus_strict.parquet", "work/edges_plus_strict.parquet",
     "work/graph_base_plus.parquet", "work/cuts_plus_strict.parquet", "work/lwc_unique.parquet", *ROADS); makedirs("figs_img")
tf = pyproj.Transformer.from_crs("EPSG:4326", "EPSG:3083", always_xy=True); inv = pyproj.Transformer.from_crs("EPSG:3083", "EPSG:4326", always_xy=True)
to3857 = pyproj.Transformer.from_crs("EPSG:3083", "EPSG:3857", always_xy=True)
G = pd.read_parquet("work/groups_b_plus_strict.parquet")
flag = G[G.nearmiss_20m & (G.bldg > 0)]
S = flag.sample(min(N_SAMPLE, len(flag)), random_state=20260924)
SS = pd.read_parquet("work/stranded_segs_plus_strict.parquet")
_e = pq.read_table("work/edges_plus_strict.parquet", columns=["cu", "cut"]); _cu = _e.column("cu").to_numpy(); _cut = _e.column("cut").to_numpy()
_seg = pq.read_table("work/graph_base_plus.parquet", columns=["seg_id"]).column("seg_id").to_numpy(zero_copy_only=False)
MAIN = pd.Index(pd.unique(_seg[(_cu == np.bincount(_cu).argmax()) & ~_cut])); del _e, _cu, _cut, _seg
C = pd.read_parquet("work/cuts_plus_strict.parquet").merge(pd.read_parquet("work/lwc_unique.parquet")[["src", "src_id", "x", "y"]], on=["src", "src_id"])
cpts = shapely.points(C.x.values, C.y.values); ct = STRtree(cpts)
need = set(SS.seg_id[SS.comp.isin(S.comp)])
ALLSTR = set(SS.seg_id)          # a segment with any stranded piece is not a way out
geo = {}
for f in ROADS:
    pf = pq.ParquetFile(f)
    for rg in range(pf.num_row_groups):
        t = pf.read_row_group(rg, columns=["id", "geometry"]).to_pandas(); t = t[t.id.isin(need)]
        if len(t): geo.update(zip(t.id, shapely.transform(shapely.from_wkb(t.geometry.values), lambda c: np.column_stack(tf.transform(c[:, 0], c[:, 1])))))
rows = []
for k, r in enumerate(S.itertuples()):
    segs = [geo[s] for s in SS.seg_id[SS.comp == r.comp] if s in geo]
    area = shapely.union_all(segs)
    ci = ct.query(area, predicate="dwithin", distance=80)
    area2 = shapely.difference(area, shapely.union_all(shapely.buffer(cpts[ci], 80))) if len(ci) else area
    xmin, ymin, xmax, ymax = area2.bounds
    lo0, la0 = inv.transform(xmin - 60, ymin - 60); lo1, la1 = inv.transform(xmax + 60, ymax + 60)
    cand = []
    for f in ROADS:
        t = duckdb.sql(f"SELECT id, geometry FROM '{f}' WHERE bbox.xmax >= {lo0} AND bbox.xmin <= {lo1} AND bbox.ymax >= {la0} AND bbox.ymin <= {la1}").df()
        t["geometry"] = t.geometry.apply(bytes)
        t = t[(MAIN.get_indexer(t.id.values) >= 0) & ~t.id.isin(ALLSTR)]
        cand += list(shapely.transform(shapely.from_wkb(t.geometry.values), lambda c: np.column_stack(tf.transform(c[:, 0], c[:, 1]))))
    if not cand: continue
    cand = np.array(cand, dtype=object); d = shapely.distance(cand, area2); j = int(np.argmin(d))
    p1, p2 = shapely.ops.nearest_points(area2, cand[j]); mx, my = (p1.x + p2.x) / 2, (p1.y + p2.y) / 2
    X0, Y0 = to3857.transform(mx - 125, my - 125); X1, Y1 = to3857.transform(mx + 125, my + 125)
    url = f"https://basemap.nationalmap.gov/arcgis/rest/services/USGSImageryOnly/MapServer/export?bbox={X0},{Y0},{X1},{Y1}&bboxSR=3857&imageSR=3857&size=700,700&format=jpg&f=image"
    img = Image.open(io.BytesIO(urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "bias-bounty-research/1.0"}), timeout=120).read()))
    fig, ax = plt.subplots(figsize=(4.67, 4.67), dpi=150); ax.imshow(img, extent=(X0, X1, Y0, Y1))
    for gm, col, lw in ((area, "#3987e5", 2.0), (shapely.union_all(list(cand[d < 150])), "#ffffff", 1.2)):
        for part in shapely.get_parts(gm):
            c = np.array(to3857.transform(*shapely.get_coordinates(part).T)).T
            ax.plot(c[:, 0], c[:, 1], color=col, lw=lw, alpha=0.85)
    a = to3857.transform(p1.x, p1.y); b = to3857.transform(p2.x, p2.y)
    ax.plot([a[0], b[0]], [a[1], b[1]], color="#e34948", lw=2.5)
    ax.set_xlim(X0, X1); ax.set_ylim(Y0, Y1); ax.set_axis_off()
    ax.set_title(f"#{k} comp {r.comp}: gap {d[j]:.1f} m, {int(r.bldg)} bldg", fontsize=8)
    fig.tight_layout(pad=0.2); fig.savefig(f"figs_img/nm_{k:02d}_{r.comp}.jpg"); plt.close(fig)
    rows.append(dict(k=k, comp=r.comp, gap_m=round(float(d[j]), 1), bldg=int(r.bldg), lon=inv.transform(mx, my)[0], lat=inv.transform(mx, my)[1]))
pd.DataFrame(rows).to_csv("work/nearmiss_sample.csv", index=False)
print(pd.DataFrame(rows).to_string())
