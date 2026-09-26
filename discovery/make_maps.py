"""Figures: one map per named example. Overture roads (plus network), the stranded roads and buildings,
and the official crossings. Colours from the reference palette: stranded = blue, crossing = red with an X
and a text label (never colour alone), everything else recessive grey."""
import argparse, sys, numpy as np, pandas as pd, duckdb, shapely, pyproj, matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
BLUE, RED, GREY, INK, INK2, SURF = "#2a78d6", "#e34948", "#bdbcb6", "#0b0b0b", "#52514e", "#fcfcfb"
from common import EXTRA_SEGMENTS, MS_BUILDINGS as MS, OVT_ROADS, makedirs, need
ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
ap.add_argument("areas", nargs="*", type=int, help="area ids (comp) from work/examples_confirmed.csv")
args = ap.parse_args()
OV = [OVT_ROADS, EXTRA_SEGMENTS]
need("work/examples_confirmed.csv", "work/bldg_plus_strict.parquet", "work/stranded_segs_plus_strict.parquet",
     "work/edges_plus_strict.parquet", "work/cuts_plus_strict.parquet", "work/lwc_unique.parquet", MS, *OV); makedirs("figs")
E = pd.read_csv("work/examples_confirmed.csv")
B = pd.read_parquet("work/bldg_plus_strict.parquet")
SS = pd.read_parquet("work/stranded_segs_plus_strict.parquet")
Ecut = pd.read_parquet("work/edges_plus_strict.parquet", columns=["cu", "cv", "su", "sv", "cut"])
Ecut = Ecut[Ecut.cut]
C = pd.read_parquet("work/cuts_plus_strict.parquet")
L = pd.read_parquet("work/lwc_unique.parquet")[["src", "src_id", "lon", "lat", "road_eff", "stream", "lwc_type"]]
tf = pyproj.Transformer.from_crs("EPSG:4326", "EPSG:3083", always_xy=True)
def P(c): x, y = tf.transform(c[:, 0], c[:, 1]); return np.column_stack([x, y])
con = duckdb.connect()
def load(f, x0, x1, y0, y1, cols):
    t = con.execute(f"SELECT {cols}, geometry g FROM '{f}' WHERE bbox.xmax >= {x0} AND bbox.xmin <= {x1} AND bbox.ymax >= {y0} AND bbox.ymin <= {y1}").df()
    return t, (shapely.transform(shapely.from_wkb(t.g.apply(bytes).values), P) if len(t) else np.array([]))
def draw(comp, fname, title, sub):
    bb = B[B.comp == comp]
    xs = pd.concat([bb.lon]); ys = pd.concat([bb.lat])
    stranded_segs = set(SS.seg_id[SS.comp == comp])
    edges = Ecut.index[((Ecut.cu == comp) & Ecut.su) | ((Ecut.cv == comp) & Ecut.sv)]
    cr = C[C.edge.isin(edges)].merge(L, on=["src", "src_id"])
    lo = np.r_[bb.lon.values, cr.lon.values]; la = np.r_[bb.lat.values, cr.lat.values]
    pad = max(lo.max() - lo.min(), la.max() - la.min()) * 0.35 + 0.004
    x0, x1, y0, y1 = lo.min() - pad, lo.max() + pad, la.min() - pad, la.max() + pad
    fig, ax = plt.subplots(figsize=(7.2, 6.6), dpi=150); fig.patch.set_facecolor(SURF); ax.set_facecolor(SURF)
    msb = con.execute(f"SELECT (bbox.xmin+bbox.xmax)/2 x, (bbox.ymin+bbox.ymax)/2 y FROM '{MS}' WHERE bbox.xmax >= {x0} AND bbox.xmin <= {x1} AND bbox.ymax >= {y0} AND bbox.ymin <= {y1}").df()
    if len(msb):
        q = P(msb[["x", "y"]].values); ax.scatter(q[:, 0], q[:, 1], s=1.2, c="#dcdbd6", lw=0, zorder=1)
    for f in OV:
        t, g = load(f, x0, x1, y0, y1, "id")
        for sid, geom in zip(t.id if len(t) else [], g):
            for part in shapely.get_parts(geom):
                c = shapely.get_coordinates(part)
                inside = sid in stranded_segs
                ax.plot(c[:, 0], c[:, 1], color=BLUE if inside else GREY, lw=1.6 if inside else 0.7, zorder=3 if inside else 2, solid_capstyle="round")
    q = P(bb[["lon", "lat"]].values); ax.scatter(q[:, 0], q[:, 1], s=3, c=BLUE, lw=0, alpha=0.7, zorder=4)
    q = P(cr[["lon", "lat"]].values); ax.scatter(q[:, 0], q[:, 1], s=90, marker="X", c=RED, edgecolor=SURF, linewidth=1.2, zorder=6)
    for (xx, yy), rd, st in zip(q, cr.road_eff.fillna("unnamed road"), cr.stream.fillna("unnamed stream")):
        tc = lambda z: " ".join(w if w[:1].isdigit() or w in ("CR", "FM", "RM", "SH", "US", "IH") else w.capitalize() for w in str(z).split())
        ax.annotate(f"{tc(rd)}\nover {tc(st)}", (xx, yy), xytext=(8, 8), textcoords="offset points", fontsize=7.5, color=INK, zorder=7,
                    bbox=dict(boxstyle="round,pad=0.25", fc=SURF, ec="none", alpha=0.85))
    X0, Y0 = P(np.array([[x0, y0]]))[0]; X1, Y1 = P(np.array([[x1, y1]]))[0]
    ax.set_xlim(X0, X1); ax.set_ylim(Y0, Y1); ax.set_aspect("equal"); ax.set_xticks([]); ax.set_yticks([])
    for s in ax.spines.values(): s.set_visible(False)
    L_ = min([100, 200, 250, 500, 1000, 2000, 5000], key=lambda v: abs(v - (X1 - X0) / 5)); ax.plot([X0 + (X1 - X0) * 0.05, X0 + (X1 - X0) * 0.05 + L_], [Y0 + (Y1 - Y0) * 0.04] * 2, color=INK2, lw=2)
    ax.text(X0 + (X1 - X0) * 0.05, Y0 + (Y1 - Y0) * 0.06, f"{L_/1000:g} km" if L_ >= 1000 else f"{L_:g} m", fontsize=8, color=INK2)
    h = [Line2D([], [], color=BLUE, lw=1.6, label=f"Roads with no mapped way out once the crossing floods ({len(bb):,} buildings)"),
         Line2D([], [], color=GREY, lw=0.7, label="Other roads in Overture (all classes)"),
         Line2D([], [], marker="X", ls="", color=RED, markersize=9, label="Official low-water crossing (TxGIO / TWDB)")]
    ax.legend(handles=h, loc="lower right", fontsize=7.5, frameon=True, facecolor=SURF, edgecolor="#e4e3de", labelcolor=INK)
    fig.suptitle(title, x=0.02, ha="left", fontsize=11.5, color=INK, fontweight="bold")
    ax.set_title(sub, loc="left", fontsize=8.5, color=INK2)
    fig.text(0.02, 0.01, "Roads: Overture 2026-08-19.0 (challenge file plus service and track roads). Buildings: Microsoft footprints (challenge bucket). "
             "Crossings: TxGIO and TWDB inventories, retrieved 24 Sep 2026.", fontsize=6, color=INK2, wrap=True)
    fig.tight_layout(rect=(0, 0.03, 1, 1)); fig.savefig(f"figs/{fname}.png", facecolor=SURF); plt.close(fig)
    print("wrote", fname, len(bb), len(cr))
picks = args.areas
for comp in picks:
    r = E[E.comp == comp].iloc[0]
    draw(comp, f"example_{r.county.lower().replace(' ', '_')}_{comp}",
         f"{r.county} County: {int(r.buildings):,} buildings, {int(r.n_cross)} crossing{'s' if r.n_cross > 1 else ''}, no other road out",
         f"Tract {r.tract}, SVI {r.tract_svi}. Scorecard road gap for this tract: {r.transport_gap}.\nThe Census Bureau's TIGER roads agree: no other way out.")
