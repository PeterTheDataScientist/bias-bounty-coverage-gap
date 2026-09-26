"""After step 9, outside the main run. What are the zero-distance near-misses? For each flagged area whose closest approach to the main
network is 0 m (the roads touch away from any crossing), find the Overture segments at the touch point and ask:
  GRADE  one of them carries is_bridge / is_tunnel or a non-zero level there: a bridge or underpass, not a way out.
  TGAP   one segment ENDS on the other with no shared connector: an unmapped junction, so the area may have a way out.
  XCROSS both pass through (neither ends there), no flag, no connector: an at-grade crossing missing its node.
Usage: python nearmiss_touch.py   (plus / strict)"""
import argparse, numpy as np, pandas as pd, duckdb, shapely, pyproj
from common import EXTRA_SEGMENTS, OVT_ROADS, need
argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter).parse_args()
need("work/nearmiss_pairs_plus_strict.csv", "work/groups_b_plus_strict.parquet", "work/stranded_segs_plus_strict.parquet",
     OVT_ROADS, EXTRA_SEGMENTS)
tf = pyproj.Transformer.from_crs("EPSG:3083", "EPSG:4326", always_xy=True)
P = pd.read_csv("work/nearmiss_pairs_plus_strict.csv"); P = P[P.d < 0.5].copy()
G = pd.read_parquet("work/groups_b_plus_strict.parquet")[["comp", "bldg", "single_crossing"]]
P = P.merge(G, on="comp")
SS = pd.read_parquet("work/stranded_segs_plus_strict.parquet")
OV = [OVT_ROADS, EXTRA_SEGMENTS]
con = duckdb.connect()
import pyarrow.parquet as pq
COLS = {f: set(pq.ParquetFile(f).schema_arrow.names) for f in OV}
to3083 = pyproj.Transformer.from_crs("EPSG:4326", "EPSG:3083", always_xy=True)
rows = []
for r in P.itertuples():
    lon, lat = tf.transform(r.x1, r.y1); e = 0.0003
    parts = []
    for f in OV:
        cols = [c for c in ("id", "class", "road_flags", "level_rules", "connectors") if c in COLS[f]]
        q = con.execute(f"""SELECT {', '.join(cols)}, geometry g FROM '{f}'
            WHERE bbox.xmax >= {lon-e} AND bbox.xmin <= {lon+e} AND bbox.ymax >= {lat-e} AND bbox.ymin <= {lat+e}""").df()
        for c in ("road_flags", "level_rules", "connectors"):
            if c not in q: q[c] = None
        parts.append(q)
    t = pd.concat(parts, ignore_index=True)
    pt = shapely.Point(r.x1, r.y1)
    stranded = set(SS.seg_id[SS.comp == r.comp])
    hits = []
    for x in t.itertuples():
        g = shapely.from_wkb(bytes(x.g)); c = np.array(to3083.transform(*shapely.get_coordinates(g).T)).T
        gp = shapely.LineString(c)
        if gp.distance(pt) > 1.0: continue
        pos = gp.project(pt, normalized=True)
        flags = []
        for rf in (x.road_flags if isinstance(x.road_flags, (list, np.ndarray)) else []):
            bt = rf.get('between'); 
            if bt is None or (bt[0] - 0.02 <= pos <= bt[1] + 0.02): flags += list(rf.get('values') if rf.get('values') is not None else [])
        lev = [lr.get('value') for lr in (x.level_rules if isinstance(x.level_rules, (list, np.ndarray)) else []) if lr.get('between') is None or (lr['between'][0] - 0.02 <= pos <= lr['between'][1] + 0.02)]
        conn = [cc.get('connector_id') for cc in (x.connectors if isinstance(x.connectors, (list, np.ndarray)) else []) if abs(cc.get('at') - pos) * gp.length < 1.5]
        hits.append(dict(id=x.id, cls=getattr(x, '_2', None), stranded=x.id in stranded, end=min(pos, 1 - pos) * gp.length < 1.5,
                         flags=flags, level=lev, conn=conn))
    S_ = [h for h in hits if h['stranded']]; M_ = [h for h in hits if not h['stranded']]
    if not S_ or not M_: kind = 'UNRESOLVED'
    elif any(('is_bridge' in h['flags'] or 'is_tunnel' in h['flags'] or any(v not in (0, None) for v in h['level'])) for h in S_ + M_): kind = 'GRADE'
    elif set(sum([h['conn'] for h in S_], [])) & set(sum([h['conn'] for h in M_], [])): kind = 'SHARED_CONNECTOR'
    elif any(h['end'] for h in S_ + M_): kind = 'TGAP'
    else: kind = 'XCROSS'
    rows.append(dict(comp=r.comp, bldg=r.bldg, single=r.single_crossing, kind=kind, lon=round(lon, 6), lat=round(lat, 6),
                     s_cls=';'.join(sorted({str(h['cls']) for h in S_})), m_cls=';'.join(sorted({str(h['cls']) for h in M_})),
                     flags=';'.join(sorted({f for h in S_ + M_ for f in h['flags']}))))
D = pd.DataFrame(rows); D.to_csv("work/nearmiss_touch_plus_strict.csv", index=False)
print(D.groupby('kind').agg(groups=('comp', 'size'), bldg=('bldg', 'sum')).to_string())
print(D.head(40).to_string())
