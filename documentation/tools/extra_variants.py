"""
Variants added in version 4 of the writeup (section 6), measured the same way as sensitivity.py:
one convention changed, all 9,379 values recomputed, tracts moved / mean absolute change / largest change,
the magnitude-test verdict and the scorecard's tribal ratio. Run from documentation/ after
`python pipeline.py --check` (or `--check --extra`): it reads out/counts.parquet and the challenge layers, from
cache/ or, with BIAS_DATA_DIR=DIR, from DIR (see README.md).

    python tools/extra_variants.py --error 0.00000301

Each recomputed base count is asserted equal to out/counts.parquet before its variant is trusted.
About 10 minutes on 2 cores, almost all of it the building pass. Writes out/counts_v4.parquet (the new per-tract
counts) and out/sensitivity_v4.csv (the table).

  TIGER duplicates  records whose geometry is byte-identical to another record's kept once (concurrent routes),
                    and, separately, records repeating both LINEARID and geometry kept once
  CRS spelling      every tract and named-highway vertex projected from OGC:CRS84 and from EPSG:4326, compared bit for bit
  predicate         USGS facilities counted with intersects like the places; building centroids exactly on a boundary
  places            a boundary place counted once (lower GEOID); permanently closed places left out
  building point    point on surface instead of the true centroid; the centroid taken after projecting to EPSG:5070
"""
import os, sys, time, argparse
import numpy as np, pandas as pd, geopandas as gpd, shapely, pyarrow.parquet as pq
from pyproj import Transformer
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import pipeline as P

ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
ap.add_argument("--error", type=float, required=True, help="the scored file's public error, for the magnitude test")
a = ap.parse_args()
T0 = time.time()
def log(m): print(f"[{time.time() - T0:7.1f}s] {m}", flush=True)
SRC = os.path.join(P.OUTDIR, "counts.parquet")
if not os.path.exists(SRC):
    sys.exit(f"missing {SRC}: run  python pipeline.py --check  first (it writes the per-tract counts)")
X = pd.read_parquet(SRC)
XI = X.set_index("GEOID")
tf = {s: Transformer.from_crs(s, P.ALBERS, always_xy=True) for s in ("OGC:CRS84", "EPSG:4326")}
crs_n = crs_bad = fac_touch = cen_touch = 0
cols = []
for r in P.REGIONS:
    log(f"=== {r}")
    sc = XI[XI.region == r]
    res = pd.DataFrame(index=sc.index)
    tr = gpd.read_parquet(P.fetch(f"strata/{r}/{r}-census-tracts.parquet"), columns=["GEOID", "geometry"])
    tr["GEOID"] = P.text_geoid(tr.GEOID)
    tr_alb, tr_ll = tr.to_crs(P.ALBERS), tr.to_crs("EPSG:4326")
    def crs_check(geoms):
        global crs_n, crs_bad
        xy = shapely.get_coordinates(np.asarray(geoms))
        u = np.column_stack(tf["OGC:CRS84"].transform(xy[:, 0], xy[:, 1])).view(np.uint64)
        v = np.column_stack(tf["EPSG:4326"].transform(xy[:, 0], xy[:, 1])).view(np.uint64)
        crs_n += len(xy); crs_bad += int((u != v).any(axis=1).sum())
    crs_check(tr.geometry.values)
    # roads: TIGER duplicates
    t = pq.read_table(P.fetch(f"reference/{r}/{r}-census-tiger-roads.parquet"), columns=["LINEARID", "MTFCC", "geometry"]).to_pandas()
    t = t[t.MTFCC.isin(P.TIGER_HWY)].reset_index(drop=True)
    g = gpd.GeoDataFrame(geometry=shapely.from_wkb(t.geometry.values), crs="OGC:CRS84")
    crs_check(g.geometry.values)
    o = gpd.read_parquet(P.fetch(f"reference/{r}/{r}-overture-roads.parquet"), columns=["class", "geometry"])
    crs_check(o[o["class"].isin(P.OVT_HWY)].geometry.values); del o
    alb = g.to_crs(P.ALBERS)
    keep_geom = ~pd.Series(list(t.geometry.values)).duplicated().values
    keep_id = ~pd.DataFrame({"i": t.LINEARID.values, "w": list(t.geometry.values)}).duplicated().values
    base = sc.index.map(P.split_lengths(alb, tr_alb)).fillna(0).values.astype(float)
    assert np.array_equal(base, sc.tig_road.values), f"{r}: TIGER control failed"
    for name, keep in (("geom", keep_geom), ("id", keep_id)):
        res[f"tig_road_dedup_{name}"] = sc.index.map(P.split_lengths(alb[keep].reset_index(drop=True), tr_alb)).fillna(0).values.astype(float)
    L = alb.length.values
    log(f"  TIGER named highway: {len(t)} records; byte-identical geometry repeats: {int((~keep_geom).sum())} records, "
        f"{L[~keep_geom].sum() / L.sum():.4%} of length; LINEARID and geometry repeats: {int((~keep_id).sum())}")
    # facilities: intersects, and points exactly on a boundary
    for k, key in (("fire", "hifld-fire-stations"), ("ems", "hifld-ems-stations"), ("school", "hifld-schools")):
        h = pd.read_csv(P.fetch(f"reference/{r}/{r}-{key}.csv"))
        hp = gpd.GeoDataFrame(geometry=gpd.points_from_xy(h.lon, h.lat), crs="EPSG:4326").to_crs(P.ALBERS)
        assert np.array_equal(sc.index.map(P.counts_by_tract(hp, tr_alb, "within")).fillna(0).values, sc[f"ref_{k}"].values)
        res[f"ref_{k}_int"] = sc.index.map(P.counts_by_tract(hp, tr_alb, "intersects")).fillna(0).values
        fac_touch += len(gpd.sjoin(hp, tr_alb[["GEOID", "geometry"]], how="inner", predicate="touches"))
    # places, built exactly as pipeline.place_columns builds them
    pt = pq.read_table(P.fetch(f"reference/{r}/{r}-overture-pois.parquet"), columns=["bbox", "categories", "operating_status"])
    b = pt.column("bbox").combine_chunks()
    x = (np.asarray(b.field("xmin")) + np.asarray(b.field("xmax"))) / 2.0
    y = (np.asarray(b.field("ymin")) + np.asarray(b.field("ymax"))) / 2.0
    prim = np.asarray(pt.column("categories").combine_chunks().field("primary").to_pylist(), dtype=object)
    is_open = np.asarray(pt.column("operating_status").to_pylist(), dtype=object) != "permanently_closed"
    pts = gpd.GeoDataFrame({"pid": np.arange(len(x))}, geometry=gpd.points_from_xy(x, y), crs="EPSG:4326").to_crs(P.ALBERS)
    j = gpd.sjoin(pts, tr_alb[["GEOID", "geometry"]], how="inner", predicate="intersects")[["pid", "GEOID"]]
    one = j.sort_values(["pid", "GEOID"]).drop_duplicates("pid")
    sel = {"places": np.ones(len(x), bool), **{k: np.array([q in c for q in prim], bool) for k, c in P.CATS.items()}}
    for k, m in sel.items():
        assert np.array_equal(sc.index.map(j[m[j.pid.values]].groupby("GEOID").size()).fillna(0).values, sc[f"ovt_{k}"].values)
        res[f"ovt_{k}_one"] = sc.index.map(one[m[one.pid.values]].groupby("GEOID").size()).fillna(0).values
        res[f"ovt_{k}_open"] = sc.index.map(j[(m & is_open)[j.pid.values]].groupby("GEOID").size()).fillna(0).values
    log(f"  places: {len(x)}, {int((~is_open).sum())} permanently closed")
    # buildings: centroid control, centroids on a boundary, point on surface, centroid taken after projection
    for side, key in (("ovt", "overture-buildings"), ("ms", "microsoft-buildings")):
        pf = pq.ParquetFile(P.fetch(f"reference/{r}/{r}-{key}.parquet"))
        cen = pd.Series(dtype="int64"); pos = pd.Series(dtype="int64"); alb = pd.Series(dtype="int64")
        for g0 in range(0, pf.metadata.num_row_groups, 8):
            geoms = shapely.from_wkb(pf.read_row_groups(list(range(g0, min(pf.metadata.num_row_groups, g0 + 8))),
                                                        columns=["geometry"]).column("geometry").to_numpy(zero_copy_only=False))
            c = gpd.GeoDataFrame(geometry=shapely.centroid(geoms), crs="EPSG:4326")
            cen = cen.add(P.counts_by_tract(c, tr_ll, "within"), fill_value=0)
            cen_touch += len(gpd.sjoin(c, tr_ll[["GEOID", "geometry"]], how="inner", predicate="touches"))
            pos = pos.add(P.counts_by_tract(gpd.GeoDataFrame(geometry=shapely.point_on_surface(geoms), crs="EPSG:4326"), tr_ll, "within"), fill_value=0)
            ca = gpd.GeoSeries(geoms, crs="EPSG:4326").to_crs(P.ALBERS).centroid          # the centroid of the projected polygon
            alb = alb.add(P.counts_by_tract(gpd.GeoDataFrame(geometry=ca, crs=P.ALBERS), tr_alb, "within"), fill_value=0)
        assert np.array_equal(sc.index.map(cen).fillna(0).values, sc[f"{side}_bldg"].values), f"{r} {side}: building control failed"
        res[f"{side}_bldg_pos"] = sc.index.map(pos).fillna(0).values
        res[f"{side}_bldg_alb"] = sc.index.map(alb).fillna(0).values
        log(f"  {side} buildings: control passed; centroid taken in EPSG:5070 changes the count in "
            f"{int((res[f'{side}_bldg_alb'].values != sc[f'{side}_bldg'].values).sum())} tracts")
    cols.append(res.reset_index())
E = pd.concat(cols)
E.to_parquet(os.path.join(P.OUTDIR, "counts_v4.parquet"), index=False)
df = X.merge(E, on="GEOID", how="left", validate="1:1")
log(f"CRS spelling: {crs_n:,} projected coordinates compared, {crs_bad} differ in any bit "
    f"({tf['EPSG:4326'].description}, the same operation for both spellings: {tf['EPSG:4326'].definition == tf['OGC:CRS84'].definition})")
log(f"USGS facilities exactly on a tract boundary: {fac_touch}; building centroids exactly on a tract boundary: {cen_touch}")

def build(road=("ovt_road", "tig_road"), bldg=("ovt_bldg", "ms_bldg"), pl="", ref=""):
    t = P.gap(df[road[0]], df[road[1]]); b = P.gap(df[bldg[0]], df[bldg[1]])
    fac = P.mean_defined(*(P.gap(df[f"ovt_{k}{pl}"], df[f"ref_{k}{ref}"]) for k in P.CATS))
    p = P.mean_defined(fac, P.gap(df[f"ovt_places{pl}"], df.cbp_estab))
    return np.round(np.clip(np.nan_to_num(P.mean_defined(t, b, p), nan=0.0), 0, 1), P.CONV["output_decimals"])
base = build()
assert np.array_equal(base, P.score(X, P.CONV["output_decimals"])[0])
st = pd.concat([pd.read_parquet(P.fetch(f"strata/{r}/{r}-strata-tract-table.parquet"), columns=["GEOID", "tribal_any"]) for r in P.REGIONS])
st["GEOID"] = P.text_geoid(st.GEOID)
trib = df.GEOID.map(st.drop_duplicates("GEOID").set_index("GEOID").tribal_any).fillna(False).astype(bool).values
thr = 2 * a.error
print(f"\nmagnitude test rules out mean |change| above {thr:.3e}; base tribal ratio {base[trib].mean() / base[~trib].mean():.3f}\n")
rows = []
for group, name, v in (
        ("roads", "TIGER records with byte-identical geometry kept once", build(road=("ovt_road", "tig_road_dedup_geom"))),
        ("roads", "TIGER records repeating LINEARID and geometry kept once", build(road=("ovt_road", "tig_road_dedup_id"))),
        ("roads", "source CRS named EPSG:4326 instead of OGC:CRS84", base if crs_bad == 0 else None),
        ("buildings", "point on surface instead of the true centroid", build(bldg=("ovt_bldg_pos", "ms_bldg_pos"))),
        ("buildings", "true centroid taken in EPSG:5070 instead of lon/lat", build(bldg=("ovt_bldg_alb", "ms_bldg_alb"))),
        ("predicate", "USGS facilities and building centroids counted with intersects",
         build(ref="_int") if cen_touch == 0 else None),
        ("places", "a boundary place counted once, in the lower GEOID", build(pl="_one")),
        ("places", "permanently closed places left out", build(pl="_open"))):
    if v is None:
        print(f"{group:<10} {name}: needs a full recount, not handled here"); continue
    d = np.abs(v - base); mv = int((d > 1e-12).sum())
    verdict = "identical" if mv == 0 else ("ruled out" if d.mean() > thr else "passes, needs the board")
    rows.append((group, name, mv, d.mean(), d.max(), verdict, v[trib].mean() / v[~trib].mean()))
    print(f"{group:<10} {name:<66} {mv:>5} tracts  mean {d.mean():.3e}  max {d.max():.3e}  {verdict:<24} tribal {rows[-1][-1]:.3f}")
pd.DataFrame(rows, columns=["group", "variant", "tracts_moved", "mean_abs_change", "max_abs_change", "verdict", "tribal_ratio"]).to_csv(
    os.path.join(P.OUTDIR, "sensitivity_v4.csv"), index=False)
