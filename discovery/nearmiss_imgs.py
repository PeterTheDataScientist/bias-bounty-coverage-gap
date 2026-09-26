"""Imagery at the closest point between a flagged area's roads and a main-network road (from nearmiss.py).
250 m window of USGS orthoimagery; red line = the gap. Usage: python nearmiss_imgs.py N_SAMPLE"""
import argparse, sys, io, urllib.request, numpy as np, pandas as pd, pyproj, matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from PIL import Image
from common import makedirs, need
ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
ap.add_argument("n_sample", type=int, help="how many flagged pairs to draw (at most all of them)")
args = ap.parse_args()
need("work/nearmiss_pairs_plus_strict.csv", "work/groups_b_plus_strict.parquet"); makedirs("figs_img")
P = pd.read_csv("work/nearmiss_pairs_plus_strict.csv")
G = pd.read_parquet("work/groups_b_plus_strict.parquet")[["comp", "bldg"]]
P = P.merge(G, on="comp"); P = P[P.bldg > 0]
S = P.sample(min(args.n_sample, len(P)), random_state=20260924).reset_index(drop=True)
to3857 = pyproj.Transformer.from_crs("EPSG:3083", "EPSG:3857", always_xy=True); to4326 = pyproj.Transformer.from_crs("EPSG:3083", "EPSG:4326", always_xy=True)
rows = []
for k, r in S.iterrows():
    mx, my = (r.x1 + r.x2) / 2, (r.y1 + r.y2) / 2
    X0, Y0 = to3857.transform(mx - 100, my - 100); X1, Y1 = to3857.transform(mx + 100, my + 100)
    url = f"https://basemap.nationalmap.gov/arcgis/rest/services/USGSImageryOnly/MapServer/export?bbox={X0},{Y0},{X1},{Y1}&bboxSR=3857&imageSR=3857&size=600,600&format=jpg&f=image"
    img = Image.open(io.BytesIO(urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "bias-bounty-research/1.0"}), timeout=120).read()))
    fig, ax = plt.subplots(figsize=(4, 4), dpi=150); ax.imshow(img, extent=(X0, X1, Y0, Y1))
    a = to3857.transform(r.x1, r.y1); b = to3857.transform(r.x2, r.y2)
    ax.scatter([a[0]], [a[1]], s=60, c="#3987e5", edgecolor="white", zorder=5); ax.scatter([b[0]], [b[1]], s=60, c="#ffffff", edgecolor="black", zorder=5)
    ax.plot([a[0], b[0]], [a[1], b[1]], color="#e34948", lw=2)
    ax.set_xlim(X0, X1); ax.set_ylim(Y0, Y1); ax.set_axis_off(); ax.set_title(f"#{k} comp {r.comp}: {r.d:.1f} m, {int(r.bldg)} bldg", fontsize=8)
    fig.tight_layout(pad=0.2); fig.savefig(f"figs_img/nm2_{k:02d}_{r.comp}.jpg"); plt.close(fig)
    lo, la = to4326.transform(mx, my); rows.append(dict(k=k, comp=r.comp, gap_m=round(r.d, 1), bldg=int(r.bldg), lon=lo, lat=la))
pd.DataFrame(rows).to_csv("work/nearmiss_sample_v2.csv", index=False); print(pd.DataFrame(rows).to_string())
