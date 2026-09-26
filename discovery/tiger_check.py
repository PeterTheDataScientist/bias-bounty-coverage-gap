"""Step 8. Independent check of the single-crossing areas against the Census Bureau's own road file
(TIGER roads in the challenge bucket: S1100, S1200, S1400, S1630). For each area: take the TIGER roads within
about 5 km, node them, cut the TIGER road at the crossing, and ask whether the area's buildings can still reach
the main local network. 'agrees' = TIGER also has no other way out.
Usage: python tiger_check.py NETWORK VARIANT [min_buildings]"""
import argparse, sys, numpy as np, pandas as pd, duckdb, shapely, pyproj
from scipy.sparse import coo_matrix
from scipy.sparse.csgraph import connected_components
from lwc_names import same_road
from common import TIGER_ROADS as T, need
ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
ap.add_argument("network", choices=["base", "plus"]); ap.add_argument("variant", choices=["all", "strict", "fords"])
ap.add_argument("min_buildings", nargs="?", type=int, default=10, help="smallest area checked (default 10)")
ap.add_argument("mode", nargs="?", choices=["single", "multi"], default="single",
                help="single: areas behind one crossing; multi: areas behind several (default single)")
args = ap.parse_args(); NET, VAR, MINB, MODE = args.network, args.variant, args.min_buildings, args.mode
need(f"work/groups_b_{NET}_{VAR}.parquet", f"work/bldg_{NET}_{VAR}.parquet", f"work/edges_{NET}_{VAR}.parquet",
     f"work/cuts_{NET}_{VAR}.parquet", "work/lwc_unique.parquet", T)
G = pd.read_parquet(f"work/groups_b_{NET}_{VAR}.parquet")
B = pd.read_parquet(f"work/bldg_{NET}_{VAR}.parquet")
X = pd.read_parquet(f"work/edges_{NET}_{VAR}.parquet")
C = pd.read_parquet(f"work/cuts_{NET}_{VAR}.parquet")
U = pd.read_parquet("work/lwc_unique.parquet")[["src", "src_id", "lon", "lat", "road_eff", "road", "stream", "county_src", "lwc_type", "tier"]]
C = C.merge(U, on=["src", "src_id", "tier", "lwc_type"], how="left")
Xc = X[X.cut]
touch = pd.concat([pd.DataFrame(dict(comp=Xc.cu[Xc.su].values, edge=Xc.index[Xc.su].values)),
                   pd.DataFrame(dict(comp=Xc.cv[Xc.sv].values, edge=Xc.index[Xc.sv].values))]).drop_duplicates()
touch = touch.merge(C[["edge", "src", "src_id", "lon", "lat", "road_eff", "stream", "county_src", "lwc_type"]], on="edge")
tf = pyproj.Transformer.from_crs("EPSG:4326", "EPSG:3083", always_xy=True)
def P(lon, lat):
    x, y = tf.transform(np.asarray(lon), np.asarray(lat)); return np.column_stack([x, y])
con = duckdb.connect(); con.execute("INSTALL spatial; LOAD spatial;")
sel = (G[G.single_crossing & (G.bldg >= MINB)] if MODE == "single" else G[~G.single_crossing & (G.bldg >= MINB)]).sort_values("bldg", ascending=False)
out = []
for _, g in sel.iterrows():
    crs = touch[touch.comp == g.comp]
    if crs.empty: continue
    cr = crs.iloc[0]
    bb = B[B.comp == g.comp]
    lo = np.r_[bb.lon.values, crs.lon.values]; la = np.r_[bb.lat.values, crs.lat.values]
    x0, x1, y0, y1 = lo.min() - 0.05, lo.max() + 0.05, la.min() - 0.05, la.max() + 0.05
    t = con.execute(f"""SELECT FULLNAME, MTFCC, ST_AsWKB(geometry) g FROM '{T}'
        WHERE bbox.xmax >= {x0} AND bbox.xmin <= {x1} AND bbox.ymax >= {y0} AND bbox.ymin <= {y1}""").df()
    if t.empty:
        out.append(dict(comp=g.comp, verdict="no_tiger")); continue
    geo0 = shapely.from_wkb(t.g.apply(bytes).values)
    geo, pidx = shapely.get_parts(geo0, return_index=True)
    geo = shapely.transform(geo, lambda c: P(c[:, 0], c[:, 1]))
    t = t.iloc[pidx].reset_index(drop=True)
    noded = shapely.get_parts(shapely.node(shapely.multilinestrings(list(geo))))
    cutm = np.zeros(len(noded), bool); found = 0; dmin = []; nm_ok = []
    for _, c in crs.iterrows():
        cp = shapely.Point(*P(c.lon, c.lat)[0])
        d = shapely.distance(geo, cp)
        near = np.argsort(d)[:5]
        named = [i for i in near if d[i] <= 60 and same_road(c.road_eff, t.FULLNAME.iloc[i])]
        i0 = named[0] if named else (near[0] if d[near[0]] <= 30 else None)
        if i0 is None: continue
        found += 1; dmin.append(float(d[i0])); nm_ok.append(bool(named))
        road = geo[i0].buffer(1.0)
        rad = max(15.0, float(d[i0]) + 10.0)      # the inventory point can sit off the centreline
        cm = (shapely.distance(noded, cp) <= rad) & shapely.within(noded, road.buffer(0.5))
        if not cm.any(): cm = shapely.distance(noded, cp) <= 5
        cutm |= cm
    if found < len(crs):
        out.append(dict(comp=g.comp, verdict="crossing_road_not_in_tiger", d_tiger=float(max(dmin)) if dmin else np.nan)); continue
    i0 = None
    a = shapely.get_coordinates(shapely.get_point(noded, 0)); b = shapely.get_coordinates(shapely.get_point(noded, -1))
    keys = {}
    ia = np.array([keys.setdefault((round(p[0], 1), round(p[1], 1)), len(keys)) for p in a])
    ib = np.array([keys.setdefault((round(p[0], 1), round(p[1], 1)), len(keys)) for p in b])
    n = len(keys); m = ~cutm
    comp = connected_components(coo_matrix((np.ones(m.sum()), (ia[m], ib[m])), shape=(n, n)), directed=False)[1]
    L = shapely.length(noded)
    clen = np.bincount(comp[ia[m]], weights=L[m], minlength=n)
    main = clen.argmax()
    samp = bb.sample(min(40, len(bb)), random_state=0)
    bp = shapely.points(P(samp.lon.values, samp.lat.values))
    tr = shapely.STRtree(noded[m])
    idx = tr.query_nearest(bp, max_distance=300, return_distance=False)
    pi, ei = idx if isinstance(idx, tuple) or getattr(idx, "ndim", 1) == 2 else (np.arange(len(bp)), idx)
    reach = comp[ia[m][ei]] == main
    frac = float(reach.mean()) if len(reach) else np.nan
    out.append(dict(comp=g.comp, verdict="agrees_isolated" if frac <= 0.2 else ("tiger_has_other_way" if frac >= 0.8 else "mixed"),
                    frac_reach_main=frac, n_cross=len(crs), d_tiger=float(max(dmin)), name_ok=bool(all(nm_ok))))
R = sel[["comp", "bldg", "people", "svi", "GEOID"]].merge(pd.DataFrame(out), on="comp", how="left")
R = R.merge(touch.drop_duplicates("comp")[["comp", "src", "src_id", "road_eff", "stream", "county_src", "lwc_type", "lon", "lat"]], on="comp", how="left")
R.to_parquet(f"work/tiger_check_{NET}_{VAR}{'' if MODE == 'single' else '_multi'}.parquet")
print(R.verdict.value_counts().to_dict())
print("buildings by verdict:", R.groupby("verdict").bldg.sum().to_dict())
pd.set_option("display.width", 250)
print(R.head(30)[["comp", "bldg", "people", "svi", "GEOID", "verdict", "frac_reach_main", "road_eff", "stream", "county_src", "lwc_type"]])
