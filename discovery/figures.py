"""Step 21. Two figures for the repository, vector data only (no imagery tiles anywhere).
  figs/v4_region_map.png     south-central Texas: all 8,454 official crossings, the 216 careful-set stranded areas sized by
                             buildings, county outlines, and the eight counties with most careful-set buildings named
  figs/v4_bexar_979.png      the Bexar example (area 979, tracts 48029141800 and 48029141700): Overture roads, the stranded
                             roads and 1,865 buildings, the three official crossings, tract boundaries
Palette: Okabe and Ito (colour-blind safe): blue #0072B2 for what is stranded, vermillion #D55E00 for crossings (region map:
for the stranded areas), greys for context; crossings are also drawn as an X, so colour is never the only cue.
Projection EPSG:3083 (Texas Centric Albers, metres); the north arrow shows grid north, within a few degrees of true north.
Both figures carry a scale bar, a north arrow, a legend and the attribution line; about 1,900 px wide.
export_results.py copies both into ../results/figures/."""
import argparse, numpy as np, pandas as pd, geopandas as gpd, shapely, pyproj, duckdb, matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from matplotlib.collections import LineCollection
import matplotlib.patheffects as pe
from common import COMPONENTS, EXTRA_SEGMENTS, MS_BUILDINGS, OVT_ROADS, STRATA, TRACTS, makedirs, need
from v4_common import careful_set, county_names, tiger_results
argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter).parse_args()
need(TRACTS, STRATA, COMPONENTS, OVT_ROADS, EXTRA_SEGMENTS, MS_BUILDINGS, "work/lwc_unique.parquet", "work/stranded_segs_plus_strict.parquet",
     "work/edges_plus_strict.parquet", "work/cuts_plus_strict.parquet")
makedirs("figs")
BLUE, VERM, INK, INK2, GREY, LGREY, SURF = "#0072B2", "#D55E00", "#111111", "#4d4d4d", "#9a9a9a", "#d4d4d4", "#ffffff"
ATTR = ("Data: Overture Maps Foundation, OpenStreetMap contributors (ODbL); TxGIO / TWDB; Microsoft Building Footprints; "
        "U.S. Census Bureau.\nOverture release 2026-08-19.0; crossing inventories retrieved 24 Sep 2026.")
halo = [pe.withStroke(linewidth=3, foreground="white")]
tf = pyproj.Transformer.from_crs("EPSG:4326", "EPSG:3083", always_xy=True)
def P(lon, lat): x, y = tf.transform(np.asarray(lon), np.asarray(lat)); return np.column_stack([x, y])
def north_arrow(ax, x, y, size):
    ax.annotate("", xy=(x, y + size), xytext=(x, y), arrowprops=dict(arrowstyle="-|>", lw=1.6, color=INK, mutation_scale=16), zorder=20)
    ax.text(x, y + size * 1.1, "N", ha="center", va="bottom", fontsize=12, fontweight="bold", color=INK, zorder=20, path_effects=halo)
def scale_bar(ax, x, y, length, label, h):
    ax.add_patch(plt.Rectangle((x, y), length / 2, h, fc=INK, ec=INK, zorder=20))
    ax.add_patch(plt.Rectangle((x + length / 2, y), length / 2, h, fc="white", ec=INK, zorder=20))
    for xx, t in ((x, "0"), (x + length, label)):
        ax.text(xx, y + h * 1.8, t, ha="center", va="bottom", fontsize=9, color=INK, zorder=20, path_effects=halo)

G, core, Bc = careful_set()
names = county_names()

# ---------------- (a) region map ----------------
T = gpd.read_parquet(TRACTS, columns=["GEOID", "geometry"]).to_crs("EPSG:3083")
T["cty"] = T.GEOID.str[:5]
C = T.dissolve("cty").reset_index()[["cty", "geometry"]]
region = shapely.union_all(C.geometry.values)
U = pd.read_parquet("work/lwc_unique.parquet", columns=["lon", "lat"])
xy = P(U.lon.values, U.lat.values)
A = Bc.groupby("comp").agg(lon=("lon", "mean"), lat=("lat", "mean"), bldg=("row", "size")).reset_index()
axy = P(A.lon.values, A.lat.values)
topc = Bc.groupby(Bc.GEOID.str[:5]).size().sort_values(ascending=False).head(8)
x0, y0, x1, y1 = region.bounds; W = x1 - x0
# label positions (fractions of the region width, offsets from each county's representative point), chosen to keep
# the labels clear of the dense Austin to San Antonio cluster; a leader line joins label and county
OFF = {"Johnson": (-0.17, -0.02), "Travis": (0.15, 0.05), "Hays": (0.19, 0.0), "Comal": (0.19, -0.06), "Bexar": (0.14, -0.13),
       "Medina": (-0.12, -0.13), "Bandera": (-0.2, -0.04), "Llano": (-0.16, 0.07)}
fig = plt.figure(figsize=(10, 10.6), dpi=190); fig.patch.set_facecolor(SURF)
ax = fig.add_axes([0.02, 0.07, 0.96, 0.82]); ax.set_facecolor(SURF)
C.boundary.plot(ax=ax, color=LGREY, lw=0.5, zorder=1)
C[C.cty.isin(topc.index)].plot(ax=ax, color="#ededed", edgecolor=GREY, lw=0.8, zorder=1)
gpd.GeoSeries([region], crs="EPSG:3083").boundary.plot(ax=ax, color=INK2, lw=1.0, zorder=2)
ax.scatter(xy[:, 0], xy[:, 1], s=1.6, c=INK2, alpha=0.55, lw=0, zorder=3)
order = np.argsort(-A.bldg.values)
ax.scatter(axy[order, 0], axy[order, 1], s=8 + 110 * np.sqrt(A.bldg.values[order] / A.bldg.max()), c=VERM, alpha=0.85, edgecolor="white", lw=0.4, zorder=4)
for cty, n in topc.items():
    nm = names.get(cty, cty); rp = C.loc[C.cty == cty, "geometry"].iloc[0].representative_point()
    dx, dy = OFF.get(nm, (0.1, 0.0)); tx, ty = rp.x + dx * W, rp.y + dy * W
    ax.plot([rp.x, tx], [rp.y, ty], color=INK2, lw=0.7, zorder=5)
    ax.text(tx, ty, f"{nm}\n{n:,} buildings", ha="center", va="center", fontsize=9, fontweight="bold", color=INK, zorder=6,
            bbox=dict(boxstyle="round,pad=0.25", fc="white", ec=GREY, lw=0.6))
pad = 0.03 * W
ax.set_xlim(x0 - pad, x1 + pad); ax.set_ylim(y0 - pad, y1 + pad); ax.set_aspect("equal"); ax.set_xticks([]); ax.set_yticks([])
for s in ax.spines.values(): s.set_visible(False)
scale_bar(ax, x1 - 0.2 * W, y0 + 0.02 * W, 100000, "100 km", W * 0.007)
north_arrow(ax, x1 - 0.01 * W, y1 - 0.1 * W, W * 0.05)
h = [Line2D([], [], marker="o", ls="", color=INK2, markersize=3, alpha=0.7, label=f"Official low-water crossing (TxGIO / TWDB), {len(U):,}"),
     Line2D([], [], marker="o", ls="", color=VERM, markeredgecolor="white", markersize=9,
            label=f"Area left with no mapped road out once its crossings close:\n{len(core):,} areas, {int(core.bldg.sum()):,} buildings (larger circle = more buildings)"),
     plt.Rectangle((0, 0), 1, 1, fc="#ededed", ec=GREY, lw=0.8, label="The eight counties with most such buildings")]
ax.legend(handles=h, loc="lower left", bbox_to_anchor=(0.0, 0.0), fontsize=9, frameon=True, facecolor=SURF, edgecolor="#dddddd", labelcolor=INK)
fig.text(0.02, 0.975, "Low-water crossings in south-central Texas and the areas they cut off", ha="left", va="top", fontsize=14, fontweight="bold", color=INK)
fig.text(0.02, 0.945, "Careful set: every official crossing closed in Overture's own road network (all classes); the Census Bureau's TIGER roads agree;\n"
         "no near-miss within 20 m. Overture's road schema has no value that marks any of these crossings as a ford or flood-prone.",
         ha="left", va="top", fontsize=9, color=INK2)
fig.text(0.02, 0.012, ATTR, fontsize=7.5, color=INK2, va="bottom")
fig.savefig("figs/v4_region_map.png", facecolor=SURF); plt.close(fig)
print("wrote figs/v4_region_map.png; top counties", {names.get(k, k): int(v) for k, v in topc.items()})

# ---------------- (b) Bexar example, area 979 ----------------
COMP = 979
OV = [OVT_ROADS, EXTRA_SEGMENTS]
MS = MS_BUILDINGS
bb = Bc[Bc.comp == COMP]
assert len(bb) == 1865
tg = tiger_results(); assert tg.loc[tg.comp == COMP, "verdict"].iloc[0] == "agrees_isolated"
SS = set(pd.read_parquet("work/stranded_segs_plus_strict.parquet").query("comp == @COMP").seg_id)
E = pd.read_parquet("work/edges_plus_strict.parquet", columns=["cu", "cv", "su", "sv", "cut"]); E = E[E.cut]
edges = E.index[((E.cu == COMP) & E.su) | ((E.cv == COMP) & E.sv)]
CR = pd.read_parquet("work/cuts_plus_strict.parquet", columns=["src", "src_id", "edge"])
CR = CR[CR.edge.isin(edges)].merge(pd.read_parquet("work/lwc_unique.parquet", columns=["src", "src_id", "lon", "lat", "road_eff", "stream", "lwc_type", "seg_flags"]), on=["src", "src_id"])
lo = np.r_[bb.lon.values, CR.lon.values]; la = np.r_[bb.lat.values, CR.lat.values]
padd = 0.06 * max(lo.max() - lo.min(), la.max() - la.min())
bx0, bx1, by0, by1 = lo.min() - padd, lo.max() + padd, la.min() - padd, la.max() + padd
con = duckdb.connect(); con.execute("SET threads=2; SET enable_progress_bar=false; INSTALL spatial; LOAD spatial;")
X0, Y0 = P(np.array([bx0]), np.array([by0]))[0]; X1, Y1 = P(np.array([bx1]), np.array([by1]))[0]
Wd, Hd = X1 - X0, Y1 - Y0
FH = 10.0; mh = 0.80 * FH; mw = mh * Wd / Hd; FW = mw + 4.3
fig = plt.figure(figsize=(FW, FH), dpi=190); fig.patch.set_facecolor(SURF)
ax = fig.add_axes([0.2 / FW, 0.08, mw / FW, 0.80]); ax.set_facecolor(SURF)
ms = con.execute(f"SELECT (bbox.xmin+bbox.xmax)/2 x, (bbox.ymin+bbox.ymax)/2 y FROM '{MS}' WHERE bbox.xmax >= {bx0} AND bbox.xmin <= {bx1} AND bbox.ymax >= {by0} AND bbox.ymin <= {by1}").df()
q = P(ms.x.values, ms.y.values); ax.scatter(q[:, 0], q[:, 1], s=0.8, c=LGREY, lw=0, zorder=1)
other, strand = [], []
for f in OV:
    t = con.execute(f"SELECT id, ST_AsWKB(geometry) g FROM '{f}' WHERE bbox.xmax >= {bx0} AND bbox.xmin <= {bx1} AND bbox.ymax >= {by0} AND bbox.ymin <= {by1}").df()
    for sid, g in zip(t.id, t.g):
        for part in shapely.get_parts(shapely.from_wkb(bytes(g))):
            c = shapely.get_coordinates(part); (strand if sid in SS else other).append(P(c[:, 0], c[:, 1]))
ax.add_collection(LineCollection(other, colors=GREY, linewidths=0.7, zorder=2))
ax.add_collection(LineCollection(strand, colors=BLUE, linewidths=1.3, zorder=3))
q = P(bb.lon.values, bb.lat.values); ax.scatter(q[:, 0], q[:, 1], s=2.4, c=BLUE, lw=0, alpha=0.85, zorder=4)
TR = gpd.read_parquet(TRACTS, columns=["GEOID", "geometry"]); TR = TR[TR.GEOID.isin(bb.GEOID.unique())].to_crs("EPSG:3083")
# draw the tract linework once, so the shared boundary is not drawn twice (two dash patterns would look solid)
for part in shapely.get_parts(shapely.line_merge(shapely.union_all(TR.boundary.values))):
    c = shapely.get_coordinates(part); ax.plot(c[:, 0], c[:, 1], color=INK, lw=1.1, ls=(0, (5, 3)), zorder=5)
S = pd.read_parquet(STRATA, columns=["GEOID", "svi_overall"]).merge(pd.read_parquet(COMPONENTS, columns=["GEOID", "transport_gap", "_t_def"]), on="GEOID")
nb = bb.GEOID.value_counts()
# tract labels inside the map, at the part of each tract that holds its stranded buildings
for gid in nb.index:
    s = S[S.GEOID == gid].iloc[0]; pts = P(bb.loc[bb.GEOID == gid, "lon"].values, bb.loc[bb.GEOID == gid, "lat"].values)
    cx = np.clip(np.median(pts[:, 0]) + (0.22 if gid.endswith("141800") else 0.18) * Wd, X0 + 0.2 * Wd, X1 - 0.2 * Wd)
    cy = np.clip(np.median(pts[:, 1]) + (-0.12 if gid.endswith("141800") else 0.06) * Hd, Y0 + 0.08 * Hd, Y1 - 0.08 * Hd)
    ax.text(cx, cy, f"Tract {gid}\n{int(nb[gid]):,} of the buildings\nSVI {s.svi_overall:.2f}\nscorecard road gap {s.transport_gap:.3f}",
            fontsize=8.5, color=INK, ha="center", va="center", zorder=7, bbox=dict(boxstyle="round,pad=0.3", fc="white", ec=GREY, lw=0.6, alpha=0.9))
q = P(CR.lon.values, CR.lat.values)
ax.scatter(q[:, 0], q[:, 1], s=200, marker="X", c=VERM, edgecolor="white", linewidth=1.3, zorder=8)
LBL = {"7383": ((12, -16), "left")}                  # keep this label off the stranded streets
for (xx, yy), sid in zip(q, CR.src_id):
    (ox, oy), ha = LBL.get(sid, ((-12, 8), "right"))
    ax.annotate(f"TxGIO {sid}", (xx, yy), xytext=(ox, oy), textcoords="offset points", ha=ha, fontsize=8.5, fontweight="bold", color=INK, path_effects=halo, zorder=9)
ax.set_xlim(X0, X1); ax.set_ylim(Y0, Y1); ax.set_aspect("equal"); ax.set_xticks([]); ax.set_yticks([])
for s_ in ax.spines.values(): s_.set_color("#cccccc")
scale_bar(ax, X0 + Wd * 0.05, Y0 + Hd * 0.025, 1000, "1 km", Hd * 0.005)
north_arrow(ax, X0 + Wd * 0.08, Y1 - Hd * 0.1, Hd * 0.045)
# right-hand panel: legend and the three crossings
px = (0.2 + mw + 0.3) / FW
h = [Line2D([], [], color=BLUE, lw=1.8, marker="o", markersize=3, label=f"Roads and buildings with no mapped way out\nonce the crossings close ({len(bb):,} buildings)"),
     Line2D([], [], color=GREY, lw=1.0, label="Other roads in Overture (all classes,\nincluding service and track)"),
     Line2D([], [], marker="X", ls="", color=VERM, markeredgecolor="white", markersize=12, label="Official low-water crossing\n(TxGIO inventory)"),
     Line2D([], [], color=INK, lw=1.1, ls=(0, (5, 3)), label="Census tract boundary"),
     Line2D([], [], marker="o", ls="", color=LGREY, markersize=4, label="Other buildings (Microsoft footprints)")]
fig.legend(handles=h, loc="upper left", bbox_to_anchor=(px, 0.88), fontsize=9, frameon=False, labelcolor=INK, labelspacing=1.0)
tc = lambda z: " ".join(w if (w[:1].isdigit() or w in ("CR", "FM", "RM", "SH", "US", "IH")) else w.capitalize() for w in str(z).split())
lines = ["The three crossings", ""]
for r in CR.sort_values("src_id").itertuples():
    flag = "bridge" if "is_bridge" in str(r.seg_flags) else "no flag"
    lines += [f"TxGIO {r.src_id}: {tc(r.road_eff)}", f"  over {tc(r.stream)}", f"  {tc(r.lwc_type)}; Overture: {flag}", ""]
res = int(round(core.loc[core.comp == COMP, "pop_block"].iloc[0], -1)); hu = int(round(core.loc[core.comp == COMP, "hu_block"].iloc[0], -1))
fr = float(tg.loc[tg.comp == COMP, "frac_reach_main"].iloc[0])
lines += ["2020 Census blocks under these", f"buildings: about {res:,} residents", f"and {hu:,} homes.", "",
          "TIGER check: cut at the same", f"crossings, {fr:.0%} of 40 sampled buildings", "still reach the main TIGER network.", "",
          "Aerial imagery (not shown), read", "twice: one reading finds an unmapped", "track east along a cleared corridor",
          "that fords a creek at grade; the", "other could not settle this area."]
fig.text(px, 0.50, "\n".join(lines), ha="left", va="top", fontsize=9, color=INK, linespacing=1.35)
fig.text(0.2 / FW, 0.975, f"South Bexar County: {len(bb):,} buildings behind three low-water crossings", ha="left", va="top", fontsize=14, fontweight="bold", color=INK)
fig.text(0.2 / FW, 0.94, "Cut at the three official crossings, neither Overture's road network nor the Census Bureau's TIGER roads leave another way out.\n"
         "Overture carries all three roads and marks none of them as a ford or flood-prone.", ha="left", va="top", fontsize=9.2, color=INK2)
fig.text(0.2 / FW, 0.012, ATTR, fontsize=7.5, color=INK2, va="bottom")
fig.savefig("figs/v4_bexar_979.png", facecolor=SURF); plt.close(fig)
print("wrote figs/v4_bexar_979.png;", len(bb), "buildings;", len(CR), "crossings:", list(CR.src + ":" + CR.src_id), "tract split", nb.to_dict(),
      "flags", CR.seg_flags.fillna("").tolist(), f"figure {FW:.2f} x {FH} in")
