"""Step 10. Better residents and homes: 2020 Census block counts (POP100, HU100) from the Census Bureau's TIGERweb
service, shared out over the Microsoft footprints in each block (people per footprint and homes per footprint
at block level instead of tract level). Public domain, no key. Usage: python block_pop.py NET VAR"""
import argparse, sys, json, time, urllib.parse, urllib.request, numpy as np, pandas as pd, duckdb, shapely, shapely.geometry
from shapely import STRtree
from common import MS_BUILDINGS as MS, need
ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
ap.add_argument("network", choices=["base", "plus"]); ap.add_argument("variant", choices=["all", "strict", "fords"])
args = ap.parse_args(); NET, VAR = args.network, args.variant
URL = "https://tigerweb.geo.census.gov/arcgis/rest/services/TIGERweb/tigerWMS_Census2020/MapServer/10/query"
need(f"work/bldg_{NET}_{VAR}.parquet", f"work/groups_b_{NET}_{VAR}.parquet", MS)
B = pd.read_parquet(f"work/bldg_{NET}_{VAR}.parquet")
G = pd.read_parquet(f"work/groups_b_{NET}_{VAR}.parquet")
blocks = {}
def fetch(x0, y0, x1, y1):
    q = dict(where="1=1", geometry=f"{x0},{y0},{x1},{y1}", geometryType="esriGeometryEnvelope", inSR=4326, outSR=4326,
             spatialRel="esriSpatialRelIntersects", outFields="GEOID,POP100,HU100", returnGeometry="true", f="geojson")
    for k in range(4):
        try:
            with urllib.request.urlopen(urllib.request.Request(URL + "?" + urllib.parse.urlencode(q), headers={"User-Agent": "bias-bounty-research/1.0"}), timeout=120) as r:
                return json.loads(r.read())["features"]
        except Exception as e:
            time.sleep(3 * (k + 1))
    return []
con = duckdb.connect()
est = []; t0 = time.time()
for i, (comp, bb) in enumerate(B.groupby("comp")):
    x0, x1, y0, y1 = bb.lon.min(), bb.lon.max(), bb.lat.min(), bb.lat.max()
    feats = fetch(x0, y0, x1, y1)
    polys, gids = [], []
    for f in feats:
        gid = f["properties"]["GEOID"]
        if gid not in blocks:
            blocks[gid] = (shapely.geometry.shape(f["geometry"]), f["properties"]["POP100"], f["properties"]["HU100"])
        polys.append(blocks[gid][0]); gids.append(gid)
    if not polys:
        est.append(dict(comp=comp, pop_block=np.nan, hu_block=np.nan)); continue
    ux0, uy0, ux1, uy1 = shapely.bounds(shapely.union_all(polys))
    ms = con.execute(f"SELECT (bbox.xmin+bbox.xmax)/2 x, (bbox.ymin+bbox.ymax)/2 y FROM '{MS}' WHERE bbox.xmax >= {ux0} AND bbox.xmin <= {ux1} AND bbox.ymax >= {uy0} AND bbox.ymin <= {uy1}").df()
    tree = STRtree(polys)
    pi, bi = tree.query(shapely.points(ms.x.values, ms.y.values), predicate="within")
    nb = np.bincount(bi, minlength=len(polys))                 # all footprints per block
    si, sb = tree.query(shapely.points(bb.lon.values, bb.lat.values), predicate="within")
    ppl = sum(blocks[gids[k]][1] / nb[k] for k in sb if nb[k] > 0)
    hu = sum(blocks[gids[k]][2] / nb[k] for k in sb if nb[k] > 0)
    est.append(dict(comp=comp, pop_block=ppl, hu_block=hu, n_located=len(sb), n_bldg=len(bb)))
    if i % 50 == 0: print(i, B.comp.nunique(), f"{time.time()-t0:.0f}s", flush=True)
E = pd.DataFrame(est)
G = G.drop(columns=[c for c in ("pop_block", "hu_block", "n_located", "n_bldg") if c in G.columns]).merge(E, on="comp", how="left")
G.to_parquet(f"work/groups_b_{NET}_{VAR}.parquet")
print("buildings", int(G.bldg.sum()), "people (tract ratio)", int(G.people.sum()), "people (block)", int(G.pop_block.sum()), "homes (block HU)", int(G.hu_block.sum()))
s = G[G.single_crossing]; print("single: buildings", int(s.bldg.sum()), "people (block)", int(s.pop_block.sum()), "homes", int(s.hu_block.sum()))
