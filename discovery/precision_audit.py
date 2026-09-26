"""Step 20. Imagery precision audit of the careful set (216 areas). The verdicts are two independent readings of the
same images, following written rules (../results/audit/README.md); no script makes them.
They are shipped in ../results/audit/ (audit_verdicts.csv and second_rater.csv), and audit_summary.py and
audit_agreement.py turn them into the precision figures. This script makes the sample and re-renders every image
the verdicts cite; the images are never committed (imagery terms), they are drawn into figs_audit/.

  python precision_audit.py sample   seeded (20260926) sample of 40 areas, stratified by size: the 216 areas are
                                     ranked by building count and cut into four quartiles of 54; 10 are drawn from each,
                                     so every area has the same chance (10/54) and the sample is self-weighting.
                                     -> work/v4_audit_sample.csv, work/v4_audit_strata.csv
  python precision_audit.py prep     for each sampled area, the road pieces in a window around it, labelled from the
                                     network cut itself (work/edges_plus_strict.parquet + work/graph_base_plus.parquet):
                                     this area's stranded sub-edges, the cut crossing sub-edges, main-network sub-edges,
                                     sub-edges of other isolated pieces; plus TIGER roads and the area's buildings.
                                     -> work/v4_audit_prep.parquet (geometry in EPSG:3083, metres)
  python precision_audit.py render [AREA ...]
                                     imagery from the same source as imagery_check.py and nearmiss_imgs.py (USGS The
                                     National Map, USGSImageryOnly export), one overview per area plus 1.5 km tiles for
                                     large areas and close-ups at up to three places where the area's roads come nearest
                                     to a main-network road (outside 80 m of its crossings, as nearmiss.py measures).
                                     -> figs_audit/a*_0overview.jpg, _tiles*.jpg, _zooms.jpg, work/v4_audit_render.csv
  python precision_audit.py extras   the extra close-ups the first reading asked for where a link was in doubt, at the points
                                     listed in ../results/audit/extra_views.csv -> figs_audit/extra_c*.jpg
  python precision_audit.py zoom AREA LON LAT [SIZE_M]   an extra close-up anywhere, for a doubtful case
  python precision_audit.py tiles AREA [PX PY TILE]      the tiles' boxes in lon/lat (and a pixel of one tile)
  python precision_audit.py px AREA PX PY                a pixel of an area's overview image in lon/lat
  python precision_audit.py pxzoom AREA PX PY [SIZE_M]   an extra close-up centred on that pixel
Imagery is for the audit only and is not used in any published figure.
"""
import argparse, sys, os, io, time, json, urllib.request, numpy as np, pandas as pd, pyarrow as pa, pyarrow.parquet as pq, pyarrow.compute as pc
import shapely, shapely.ops, pyproj, duckdb, matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from PIL import Image
from shapely import STRtree
from common import AUDIT, EXTRA_SEGMENTS, OVT_ROADS, TIGER_ROADS, UA, makedirs, need
from v4_common import careful_set, SEED

ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
sub = ap.add_subparsers(dest="cmd", required=True, metavar="COMMAND")
sub.add_parser("sample", help="the seeded sample of 40 areas")
sub.add_parser("prep", help="the road pieces around each sampled area")
p_ = sub.add_parser("render", help="overview, tiles and close-ups for every sampled area (or the areas given)")
p_.add_argument("areas", nargs="*", type=int)
p_ = sub.add_parser("extras", help="the extra close-ups listed in results/audit/extra_views.csv")
p_.add_argument("--views", default=os.path.join(AUDIT, "extra_views.csv"))
p_ = sub.add_parser("zoom", help="an extra close-up: AREA LON LAT [SIZE_M]")
p_.add_argument("area", type=int); p_.add_argument("lon", type=float); p_.add_argument("lat", type=float)
p_.add_argument("size", type=float, nargs="?", default=400.0)
p_ = sub.add_parser("tiles", help="tile boxes of an area: AREA [PX PY TILE]")
p_.add_argument("area", type=int); p_.add_argument("px", type=float, nargs="?"); p_.add_argument("py", type=float, nargs="?")
p_.add_argument("tile", type=int, nargs="?")
for name in ("px", "pxzoom"):
    p_ = sub.add_parser(name, help="overview pixel to lon/lat" + (", then an extra close-up there" if name == "pxzoom" else ""))
    p_.add_argument("area", type=int); p_.add_argument("px", type=float); p_.add_argument("py", type=float)
    if name == "pxzoom": p_.add_argument("size", type=float, nargs="?", default=400.0)
args = ap.parse_args()
OV = [OVT_ROADS, EXTRA_SEGMENTS]
TIGER = TIGER_ROADS
to3083 = pyproj.Transformer.from_crs("EPSG:4326", "EPSG:3083", always_xy=True)
to4326 = pyproj.Transformer.from_crs("EPSG:3083", "EPSG:4326", always_xy=True)
m2web = pyproj.Transformer.from_crs("EPSG:3083", "EPSG:3857", always_xy=True)
def P(c): x, y = to3083.transform(c[:, 0], c[:, 1]); return np.column_stack([x, y])
makedirs("figs_audit")

def do_sample():
    G, core, Bc = careful_set()
    c = core.sort_values(["bldg", "comp"]).reset_index(drop=True)
    assert len(c) == 216
    c["stratum"] = np.repeat([1, 2, 3, 4], 54)
    rng = np.random.default_rng(SEED)
    picks = []
    for s in (1, 2, 3, 4):
        m = c[c.stratum == s].sort_values("comp").reset_index(drop=True)
        picks.append(m.iloc[np.sort(rng.choice(len(m), 10, replace=False))])
    S = pd.concat(picks).reset_index(drop=True); S.insert(0, "k", np.arange(len(S)))
    S[["k", "stratum", "comp", "bldg", "n_cross", "single_crossing", "pop_block", "hu_block", "GEOID"]].to_csv("work/v4_audit_sample.csv", index=False)
    st = c.groupby("stratum").agg(areas=("comp", "size"), bldg_min=("bldg", "min"), bldg_max=("bldg", "max"), buildings=("bldg", "sum"),
                                  residents=("pop_block", "sum"), homes=("hu_block", "sum")).reset_index()
    st.to_csv("work/v4_audit_strata.csv", index=False)
    print(st.to_string()); print(S[["k", "stratum", "comp", "bldg", "n_cross", "GEOID"]].to_string())

def seg_geoms(ids):
    """id -> LineString in EPSG:3083 for the given Overture ids, from both road files (row group scan)."""
    out = {}
    ids = set(ids)
    for f in OV:
        pf = pq.ParquetFile(f)
        for rg in range(pf.num_row_groups):
            t = pf.read_row_group(rg, columns=["id", "geometry"]).to_pandas(); t = t[t.id.isin(ids)]
            if len(t): out.update(zip(t.id.values, shapely.transform(shapely.from_wkb(t.geometry.values), P)))
    return out

def do_prep():
    need("work/v4_audit_sample.csv", "work/edges_plus_strict.parquet", "work/graph_base_plus.parquet", "work/bldg_plus_strict.parquet",
         "work/cuts_plus_strict.parquet", "work/lwc_unique.parquet", *OV, TIGER)
    S = pd.read_csv("work/v4_audit_sample.csv")
    e = pq.read_table("work/edges_plus_strict.parquet", columns=["cu", "cv", "su", "sv", "cut"])
    cu, cv, su, sv, cut = (e.column(k).to_numpy() for k in ("cu", "cv", "su", "sv", "cut")); del e
    g1 = np.bincount(cu).argmax()                         # the main network after the cut, as nearmiss.py
    lab = np.where(cut, -2, np.where(su & sv, cu, np.where(cu == g1, -1, -3)))
    g = pq.read_table("work/graph_base_plus.parquet", columns=["seg_id", "a0", "a1"])
    segcol = g.column("seg_id"); a0 = g.column("a0").to_numpy(); a1 = g.column("a1").to_numpy(); del g
    B = pd.read_parquet("work/bldg_plus_strict.parquet", columns=["comp", "lon", "lat"])
    C = pd.read_parquet("work/cuts_plus_strict.parquet", columns=["src", "src_id", "edge"]).merge(
        pd.read_parquet("work/lwc_unique.parquet", columns=["src", "src_id", "lon", "lat", "road_eff", "stream", "lwc_type"]), on=["src", "src_id"])
    # 1. each area's own stranded sub-edges and its cut crossing sub-edges -> window
    own = {}
    for comp in S.comp:
        idx = np.where(lab == comp)[0]
        cidx = np.where(cut & (((cu == comp) & su) | ((cv == comp) & sv)))[0]
        own[comp] = (idx, cidx)
    ids_needed = pc.unique(pc.take(segcol, pa.array(np.concatenate([np.r_[i, j] for i, j in own.values()])))).to_pylist()
    geo = seg_geoms(ids_needed)
    con = duckdb.connect(); con.execute("SET threads=2; SET enable_progress_bar=false; INSTALL spatial; LOAD spatial;")
    rows = []
    for comp in S.comp:
        idx, cidx = own[comp]
        parts = []
        for i, s in zip(idx, pc.take(segcol, pa.array(idx)).to_pylist()):
            try: parts.append(shapely.ops.substring(geo[s], a0[i], a1[i], normalized=True))
            except Exception: parts.append(geo[s])
        bb = B[B.comp == comp]; cr = C[C.edge.isin(cidx)]
        xy = np.vstack([P(bb[["lon", "lat"]].values), P(cr[["lon", "lat"]].values)] + [shapely.get_coordinates(p) for p in parts])
        x0, y0 = xy.min(0); x1, y1 = xy.max(0)
        pad = max(0.25 * max(x1 - x0, y1 - y0), 250.0)
        X0, Y0, X1, Y1 = x0 - pad, y0 - pad, x1 + pad, y1 + pad
        lo0, la0 = to4326.transform(X0, Y0); lo1, la1 = to4326.transform(X1, Y1)
        lo0b, la0b = to4326.transform(X0, Y1); lo1b, la1b = to4326.transform(X1, Y0)
        lo0, lo1, la0, la1 = min(lo0, lo0b), max(lo1, lo1b), min(la0, la1b), max(la1, la0b)
        # 2. every Overture segment in the window, split into its sub-edges and labelled from the cut
        wid, wg = [], []
        for f in OV:
            t = con.execute(f"SELECT id, ST_AsWKB(geometry) g FROM '{f}' WHERE bbox.xmax >= {lo0} AND bbox.xmin <= {lo1} AND bbox.ymax >= {la0} AND bbox.ymin <= {la1}").df()
            if len(t): wid += list(t.id.values); wg += list(shapely.transform(shapely.from_wkb(t.g.apply(bytes).values), P))
        wgeo = dict(zip(wid, wg))
        mask = pc.is_in(segcol, value_set=pa.array(list(wgeo.keys()))).to_numpy(zero_copy_only=False)
        widx = np.where(mask)[0]; wsid = pc.take(segcol, pa.array(widx)).to_pylist(); cset = set(cidx.tolist())
        for i, s in zip(widx, wsid):
            L = lab[i]
            kind = "stranded" if L == comp else ("cut" if L == -2 else ("main" if L == -1 else "other"))
            if kind == "cut" and int(i) not in cset: kind = "cut_other"
            try: gg = shapely.ops.substring(wgeo[s], a0[i], a1[i], normalized=True)
            except Exception: gg = wgeo[s]
            rows.append(dict(comp=comp, kind=kind, seg_id=s, wkb=shapely.to_wkb(gg)))
        # 3. TIGER roads in the window
        t = con.execute(f"SELECT FULLNAME, MTFCC, ST_AsWKB(geometry) g FROM '{TIGER}' WHERE bbox.xmax >= {lo0} AND bbox.xmin <= {lo1} AND bbox.ymax >= {la0} AND bbox.ymin <= {la1}").df()
        if len(t):
            tg = shapely.transform(shapely.from_wkb(t.g.apply(bytes).values), P)
            for gg, nm in zip(tg, t.FULLNAME.fillna("")): rows.append(dict(comp=comp, kind="tiger", seg_id=nm, wkb=shapely.to_wkb(gg)))
        for x, y in P(bb[["lon", "lat"]].values): rows.append(dict(comp=comp, kind="building", seg_id="", wkb=shapely.to_wkb(shapely.Point(x, y))))
        for r in cr.itertuples():
            x, y = P(np.array([[r.lon, r.lat]]))[0]
            rows.append(dict(comp=comp, kind="crossing", seg_id=f"{r.src}:{r.src_id} {r.road_eff} over {r.stream} ({r.lwc_type})", wkb=shapely.to_wkb(shapely.Point(x, y))))
        rows.append(dict(comp=comp, kind="window", seg_id="", wkb=shapely.to_wkb(shapely.box(X0, Y0, X1, Y1))))
        print("prepared", comp, "window km", round((X1 - X0) / 1000, 2), round((Y1 - Y0) / 1000, 2), "stranded pieces", len(idx), "crossings", len(cr), flush=True)
    pd.DataFrame(rows).to_parquet("work/v4_audit_prep.parquet")

STY = {"tiger": dict(color="#ffd400", lw=0.9, ls=(0, (4, 3)), zorder=2), "main": dict(color="#ffffff", lw=0.9, zorder=3),
       "other": dict(color="#ff9f1c", lw=1.1, zorder=3), "cut_other": dict(color="#ff9f1c", lw=1.1, zorder=3),
       "stranded": dict(color="#00d5ff", lw=1.8, zorder=4), "cut": dict(color="#ff2d2d", lw=2.8, zorder=5)}
def fetch_img(X0, Y0, X1, Y1, W, H):
    url = (f"https://basemap.nationalmap.gov/arcgis/rest/services/USGSImageryOnly/MapServer/export?bbox={X0},{Y0},{X1},{Y1}"
           f"&bboxSR=3857&imageSR=3857&size={W},{H}&format=jpg&f=image")
    for k in range(4):
        try:
            return Image.open(io.BytesIO(urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=120).read()))
        except Exception as e:
            print("  imagery retry", k, repr(e)[:100], flush=True); time.sleep(3 * (k + 1))
    raise RuntimeError("imagery fetch failed")
from matplotlib.collections import LineCollection
def layers(D):
    """Per-kind line lists in EPSG:3857, plus building and crossing points, built once per area."""
    L = {}
    for kind in ("tiger", "main", "other", "cut_other", "stranded", "cut"):
        segs = []
        for w in D.loc[D.kind == kind, "wkb"]:
            for part in shapely.get_parts(shapely.from_wkb(w)):
                c = shapely.get_coordinates(part)
                if len(c) < 2: continue
                x, y = m2web.transform(c[:, 0], c[:, 1]); segs.append(np.column_stack([x, y]))
        L[kind] = segs
    for kind in ("building", "crossing"):
        b = D[D.kind == kind]
        c = shapely.get_coordinates(shapely.from_wkb(b.wkb.values)) if len(b) else np.zeros((0, 2))
        L[kind] = np.column_stack(m2web.transform(c[:, 0], c[:, 1])) if len(c) else np.zeros((0, 2))
    return L
def draw(L, box, fname, title, longside=1800, link=None, grid=()):
    """box in EPSG:3083 metres; draws every layer over the imagery; link = ((x1,y1),(x2,y2),label); grid = [(box, label)]."""
    X0, Y0 = m2web.transform(box[0], box[1]); X1, Y1 = m2web.transform(box[2], box[3])
    if (X1 - X0) >= (Y1 - Y0): W = longside; H = max(300, int(W * (Y1 - Y0) / (X1 - X0)))
    else: H = longside; W = max(300, int(H * (X1 - X0) / (Y1 - Y0)))
    img = fetch_img(X0, Y0, X1, Y1, W, H)
    fig = plt.figure(figsize=(W / 150, H / 150), dpi=150); ax = fig.add_axes([0, 0, 1, 1])
    ax.imshow(img, extent=(X0, X1, Y0, Y1), aspect="auto")
    for kind in ("tiger", "main", "other", "cut_other", "stranded", "cut"):
        if L[kind]:
            st = STY[kind]
            ax.add_collection(LineCollection(L[kind], colors=st["color"], linewidths=st["lw"], linestyles=[st.get("ls", "solid")], zorder=st["zorder"], capstyle="round"))
    if len(L["building"]): ax.scatter(L["building"][:, 0], L["building"][:, 1], s=5 if longside > 1000 else 12, c="#ff4fd8", lw=0, zorder=6)
    if len(L["crossing"]): ax.scatter(L["crossing"][:, 0], L["crossing"][:, 1], s=150, marker="X", c="#ff2d2d", edgecolor="white", linewidth=1.2, zorder=7)
    if link is not None:
        (ax_, ay_), (bx_, by_), lbl = link
        p = m2web.transform([ax_, bx_], [ay_, by_]); ax.plot(p[0], p[1], color="#ff2d2d", lw=1.6, ls=(0, (2, 2)), zorder=8)
        ax.text(np.mean(p[0]), np.mean(p[1]), lbl, color="white", fontsize=8, zorder=9, bbox=dict(fc="black", alpha=0.6, ec="none"))
    for gb, gl in grid:
        a = m2web.transform(gb[0], gb[1]); b = m2web.transform(gb[2], gb[3])
        ax.plot([a[0], b[0], b[0], a[0], a[0]], [a[1], a[1], b[1], b[1], a[1]], color="white", lw=0.8, alpha=0.8, zorder=8)
        ax.text(a[0] + (b[0] - a[0]) * 0.03, b[1] - (b[1] - a[1]) * 0.12, gl, color="white", fontsize=9, zorder=9, bbox=dict(fc="black", alpha=0.5, ec="none"))
    ax.set_xlim(X0, X1); ax.set_ylim(Y0, Y1); ax.set_axis_off()
    sb = 100 if (box[2] - box[0]) < 1500 else (500 if (box[2] - box[0]) < 6000 else 1000)
    sx, sy = m2web.transform([box[0] + (box[2] - box[0]) * 0.04, box[0] + (box[2] - box[0]) * 0.04 + sb], [box[1] + (box[3] - box[1]) * 0.05] * 2)
    ax.plot(sx, sy, color="white", lw=3, zorder=9); ax.text(sx[0], sy[0] + (Y1 - Y0) * 0.012, f"{sb} m", color="white", fontsize=8, zorder=9)
    fig.text(0.01, 0.995, title, fontsize=8, color="white", va="top", bbox=dict(fc="black", alpha=0.65, ec="none"))
    fig.text(0.01, 0.005, "USGS imagery (public domain). Cyan: this area's roads; red: cut crossing piece + X official crossing; white: main network; "
             "orange: other unconnected pieces; yellow dashed: TIGER; pink: this area's buildings.", fontsize=6, color="white", bbox=dict(fc="black", alpha=0.6, ec="none"))
    fig.savefig(fname, dpi=150); plt.close(fig)
def tiles_for(D, tile=1500.0, buf=150.0):
    """Square tiles (EPSG:3083) covering a 150 m buffer of the area's roads and buildings."""
    g = shapely.from_wkb(D.loc[D.kind.isin(["stranded", "cut", "building"]), "wkb"].values)
    U = shapely.union_all(shapely.buffer(g, buf)); x0, y0, x1, y1 = shapely.bounds(U)
    nx, ny = int(np.ceil((x1 - x0) / tile)), int(np.ceil((y1 - y0) / tile))
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2; ox, oy = cx - nx * tile / 2, cy - ny * tile / 2
    out = []
    for j in range(ny - 1, -1, -1):
        for i in range(nx):
            b = (ox + i * tile, oy + j * tile, ox + (i + 1) * tile, oy + (j + 1) * tile)
            if shapely.intersects(U, shapely.box(*b)): out.append(b)
    return out
def montage(files, out, cols):
    ims = [Image.open(f) for f in files]; w = max(i.width for i in ims); h = max(i.height for i in ims)
    rows = int(np.ceil(len(ims) / cols)); sheet = Image.new("RGB", (cols * w, rows * h), "black")
    for n, im in enumerate(ims): sheet.paste(im, ((n % cols) * w, (n // cols) * h))
    sheet.save(out, quality=88)

def exit_candidates(D, k=3, sep=300.0, maxd=1500.0):
    """Up to k places, at least sep m apart, where the area's roads (outside 80 m of its crossings) come nearest a main road."""
    st = shapely.from_wkb(D.loc[D.kind == "stranded", "wkb"].values); mn = shapely.from_wkb(D.loc[D.kind == "main", "wkb"].values)
    cr = shapely.from_wkb(D.loc[D.kind == "crossing", "wkb"].values)
    if len(st) == 0 or len(mn) == 0: return []
    area = shapely.union_all(st)
    if len(cr): area = shapely.difference(area, shapely.union_all(shapely.buffer(cr, 80)))
    pieces = [p for p in shapely.get_parts(area) if not p.is_empty]
    if not pieces: return []
    tr = STRtree(mn); pairs = []
    for p in pieces:
        for seg in shapely.get_parts(p):
            L = seg.length; pts = shapely.line_interpolate_point(seg, np.linspace(0, L, max(2, int(L // 25) + 1)))
            ii, dd = tr.query_nearest(pts, max_distance=maxd, return_distance=True)
            for (pi, mi), d in zip(ii.T, dd):
                a, b = shapely.ops.nearest_points(seg, mn[mi]); pairs.append((float(a.distance(b)), a.x, a.y, b.x, b.y))
    pairs.sort(); out = []
    for d, ax_, ay_, bx_, by_ in pairs:
        if all(np.hypot(ax_ - o[1], ay_ - o[2]) > sep for o in out): out.append((d, ax_, ay_, bx_, by_))
        if len(out) == k: break
    return out

def do_render(only=None, tile_over=2000.0):
    need("work/v4_audit_sample.csv", "work/v4_audit_prep.parquet")
    S = pd.read_csv("work/v4_audit_sample.csv"); A = pd.read_parquet("work/v4_audit_prep.parquet")
    meta = []
    for r in S.itertuples():
        if only and r.comp not in only: continue
        D = A[A.comp == r.comp]; L = layers(D); stem = f"figs_audit/a{r.k:02d}_s{r.stratum}_c{r.comp}"
        box = shapely.bounds(shapely.from_wkb(D.loc[D.kind == "window", "wkb"].iloc[0]))
        title = f"audit #{r.k} (stratum {r.stratum}) area {r.comp}: {int(r.bldg)} buildings, {int(r.n_cross)} crossing(s), tract {r.GEOID}"
        tl = tiles_for(D) if max(box[2] - box[0], box[3] - box[1]) > tile_over else []
        draw(L, box, f"{stem}_0overview.jpg", title, grid=[(b, f"T{n + 1}") for n, b in enumerate(tl)])
        tf = []
        for n, b in enumerate(tl):
            f = f"{stem}_t{n + 1:02d}.jpg"; draw(L, b, f, f"area {r.comp} tile T{n + 1} (1.5 km)", longside=900); tf.append(f)
        for q in range(0, len(tf), 4): montage(tf[q:q + 4], f"{stem}_tiles{q // 4 + 1}.jpg", 2)
        for f in tf: os.remove(f)                       # the montages hold the same pixels; keep the folder small
        ec = exit_candidates(D); zf = []
        for j, (d, ax_, ay_, bx_, by_) in enumerate(ec, 1):
            mx, my = (ax_ + bx_) / 2, (ay_ + by_) / 2; h = max(150.0, d / 2 + 60)
            f = f"{stem}_z{j}.jpg"; zf.append(f)
            draw(L, (mx - h, my - h, mx + h, my + h), f, f"area {r.comp}: nearest approach {j} to a main-network road, {d:.0f} m", longside=800,
                 link=((ax_, ay_), (bx_, by_), f"{d:.0f} m"))
            lo, la = to4326.transform(mx, my)
            meta.append(dict(k=r.k, comp=r.comp, cand=j, gap_m=round(d, 1), lon=round(lo, 6), lat=round(la, 6)))
        if zf: montage(zf, f"{stem}_zooms.jpg", min(3, len(zf)))
        for f in zf: os.remove(f)
        print("rendered", r.k, r.comp, "tiles", len(tl), "candidates", [round(x[0]) for x in ec], flush=True)
    if not only: pd.DataFrame(meta).to_csv("work/v4_audit_render.csv", index=False)

def do_zoom(comp, lon, lat, size, name=None):
    need("work/v4_audit_prep.parquet")
    A = pd.read_parquet("work/v4_audit_prep.parquet"); D = A[A.comp == comp]; L = layers(D)
    x, y = to3083.transform(lon, lat); h = size / 2
    i = 1
    while name is None and os.path.exists(f"figs_audit/extra_c{comp}_{i}.jpg"): i += 1
    f = f"figs_audit/{name}" if name else f"figs_audit/extra_c{comp}_{i}.jpg"
    draw(L, (x - h, y - h, x + h, y + h), f, f"area {comp}: extra close-up at {lat:.5f}, {lon:.5f} ({size:.0f} m)", longside=900)
    print("wrote", f)

def do_extras(views):
    """Re-draw every extra close-up the verdicts cite, under its original name."""
    need(views)
    for r in pd.read_csv(views).itertuples():
        do_zoom(int(r.comp), float(r.lon), float(r.lat), float(r.size_m), name=r.file)

def do_tiles(comp, px=None, py=None, tile_no=None):
    """Print each tile's box in lon/lat (and, given a tile number and pixel position in that 900 px tile, the lon/lat there)."""
    need("work/v4_audit_prep.parquet")
    A = pd.read_parquet("work/v4_audit_prep.parquet"); D = A[A.comp == comp]
    for n, b in enumerate(tiles_for(D), 1):
        lo0, la0 = to4326.transform(b[0], b[1]); lo1, la1 = to4326.transform(b[2], b[3])
        line = f"T{n}: lon {lo0:.5f}..{lo1:.5f} lat {la0:.5f}..{la1:.5f}"
        if tile_no == n and px is not None:
            x = b[0] + px / 900 * (b[2] - b[0]); y = b[3] - py / 900 * (b[3] - b[1]); lo, la = to4326.transform(x, y)
            line += f"  -> pixel ({px:.0f},{py:.0f}) is lon {lo:.6f} lat {la:.6f}"
        print(line)

def do_px(comp, px, py):
    """Pixel (px, py) on an area's overview image -> lon/lat (the overview spans the prepared window exactly)."""
    import glob
    need("work/v4_audit_prep.parquet")
    if not glob.glob(f"figs_audit/a*_c{comp}_0overview.jpg"): sys.exit(f"no overview image of area {comp}: python precision_audit.py render {comp}")
    A = pd.read_parquet("work/v4_audit_prep.parquet"); D = A[A.comp == comp]
    b = shapely.bounds(shapely.from_wkb(D.loc[D.kind == "window", "wkb"].iloc[0]))
    f = glob.glob(f"figs_audit/a*_c{comp}_0overview.jpg")[0]; W, H = Image.open(f).size
    X0, Y0 = m2web.transform(b[0], b[1]); X1, Y1 = m2web.transform(b[2], b[3])
    X = X0 + px / W * (X1 - X0); Y = Y1 - py / H * (Y1 - Y0)
    lo, la = pyproj.Transformer.from_crs("EPSG:3857", "EPSG:4326", always_xy=True).transform(X, Y)
    print(f"{comp} overview {W}x{H}: pixel ({px:.0f},{py:.0f}) -> lon {lo:.6f} lat {la:.6f}")
    return lo, la

if args.cmd == "sample": do_sample()
elif args.cmd == "prep": do_prep()
elif args.cmd == "render": do_render(args.areas or None)
elif args.cmd == "extras": do_extras(args.views)
elif args.cmd == "zoom": do_zoom(args.area, args.lon, args.lat, args.size)
elif args.cmd == "tiles": do_tiles(args.area, args.px, args.py, args.tile)
elif args.cmd == "px": do_px(args.area, args.px, args.py)
elif args.cmd == "pxzoom":
    lo, la = do_px(args.area, args.px, args.py); do_zoom(args.area, lo, la, args.size)
