"""Imagery check: USGS National Map orthoimagery (public domain) under the stranded roads and the crossings,
for a visual test that the crossing is a real stream crossing and that no other road leaves the area.
Usage: python imagery_check.py COMP [COMP ...]  (plus/strict groups)"""
import argparse, sys, io, numpy as np, pandas as pd, duckdb, shapely, pyproj, urllib.request, matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from PIL import Image
from common import EXTRA_SEGMENTS, OVT_ROADS, makedirs, need
ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
ap.add_argument("areas", nargs="*", type=int, help="area ids (comp), plus network, strict list")
args = ap.parse_args()
need("work/stranded_segs_plus_strict.parquet", "work/bldg_plus_strict.parquet", "work/edges_plus_strict.parquet",
     "work/cuts_plus_strict.parquet", "work/lwc_unique.parquet", OVT_ROADS, EXTRA_SEGMENTS); makedirs("figs_img")
SS = pd.read_parquet("work/stranded_segs_plus_strict.parquet")
B = pd.read_parquet("work/bldg_plus_strict.parquet")
E = pd.read_parquet("work/edges_plus_strict.parquet", columns=["cu", "cv", "su", "sv", "cut"]); E = E[E.cut]
C = pd.read_parquet("work/cuts_plus_strict.parquet").merge(pd.read_parquet("work/lwc_unique.parquet")[["src", "src_id", "lon", "lat", "road_eff", "stream"]], on=["src", "src_id"])
OV = [OVT_ROADS, EXTRA_SEGMENTS]
to3857 = pyproj.Transformer.from_crs("EPSG:4326", "EPSG:3857", always_xy=True)
con = duckdb.connect()
for comp in args.areas:
    bb = B[B.comp == comp]; segs = set(SS.seg_id[SS.comp == comp])
    ed = E.index[((E.cu == comp) & E.su) | ((E.cv == comp) & E.sv)]
    cr = C[C.edge.isin(ed)]
    lo = np.r_[bb.lon.values, cr.lon.values]; la = np.r_[bb.lat.values, cr.lat.values]
    pad = max(lo.max() - lo.min(), la.max() - la.min()) * 0.25 + 0.002
    x0, x1, y0, y1 = lo.min() - pad, lo.max() + pad, la.min() - pad, la.max() + pad
    X0, Y0 = to3857.transform(x0, y0); X1, Y1 = to3857.transform(x1, y1)
    W = 1600; H = int(W * (Y1 - Y0) / (X1 - X0)); H = max(400, min(H, 2400))
    url = (f"https://basemap.nationalmap.gov/arcgis/rest/services/USGSImageryOnly/MapServer/export?bbox={X0},{Y0},{X1},{Y1}"
           f"&bboxSR=3857&imageSR=3857&size={W},{H}&format=jpg&f=image")
    img = Image.open(io.BytesIO(urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "bias-bounty-research/1.0"}), timeout=120).read()))
    fig, ax = plt.subplots(figsize=(W / 150, H / 150), dpi=150)
    ax.imshow(img, extent=(X0, X1, Y0, Y1))
    for f in OV:
        t = con.execute(f"SELECT id, geometry g FROM '{f}' WHERE bbox.xmax >= {x0} AND bbox.xmin <= {x1} AND bbox.ymax >= {y0} AND bbox.ymin <= {y1}").df()
        for sid, g in zip(t.id, t.g):
            for part in shapely.get_parts(shapely.from_wkb(bytes(g))):
                c = np.array(to3857.transform(*shapely.get_coordinates(part).T)).T
                ax.plot(c[:, 0], c[:, 1], color="#3987e5" if sid in segs else "#ffffff", lw=1.2 if sid in segs else 0.5, alpha=0.9 if sid in segs else 0.6)
    q = np.array(to3857.transform(cr.lon.values, cr.lat.values)).T
    ax.scatter(q[:, 0], q[:, 1], s=120, marker="X", c="#e34948", edgecolor="white", linewidth=1.2, zorder=5)
    ax.set_xlim(X0, X1); ax.set_ylim(Y0, Y1); ax.set_axis_off()
    fig.text(0.01, 0.005, "Imagery: USGS The National Map, USGSImageryOnly (public domain). Blue: stranded roads; white: other Overture roads; red X: official crossing.", fontsize=6, color="white",
             bbox=dict(fc="black", alpha=0.6, ec="none"))
    fig.tight_layout(pad=0); fig.savefig(f"figs_img/img_{comp}.jpg", dpi=150); plt.close(fig)
    print("wrote", comp, W, H, len(bb), len(cr))
