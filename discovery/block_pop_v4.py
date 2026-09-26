"""Step 14. Census 2020 block residents and homes for ALL SIX versions (network x crossing list).

Same method as block_pop.py (step 10), which runs for plus/strict only: each 2020 Census block's POP100 and HU100
(TIGERweb, tigerWMS_Census2020 layer 10, public domain, no key) are shared equally over the Microsoft footprints
whose bbox centre lies in the block, and a stranded area's residents and homes are the sums over its stranded
footprints. Blocks are cached across versions so each block is fetched and counted once; a block's footprint count
is always taken over the whole block, exactly as block_pop.py does, so the per-area result does not depend on the
order in which areas are processed. The plus/strict run is checked against block_pop.py's own columns.

    python block_pop_v4.py                 all six versions (about 6 to 10 minutes, mostly TIGERweb queries)
    python block_pop_v4.py plus strict     one or more NETWORK VARIANT pairs

Writes (the block cache lets a rerun resume after a network failure):
  work/v4_blocks_cache.parquet                 one row per block fetched (GEOID, POP100, HU100, nb, wkb)
  work/v4_blockpop_bldg_{NET}_{VAR}.parquet    one row per stranded footprint: rg, row, comp, GEOID, block, ppl_blk, hu_blk
  work/v4_blockpop_groups_{NET}_{VAR}.parquet  one row per area: comp, pop_block, hu_block, n_located, n_bldg
"""
import argparse, sys, os, json, time, urllib.parse, urllib.request, numpy as np, pandas as pd, duckdb, shapely, shapely.geometry
from shapely import STRtree
from common import MS_BUILDINGS as MS, UA, need
ALL = [("base", "all"), ("base", "strict"), ("base", "fords"), ("plus", "all"), ("plus", "strict"), ("plus", "fords")]
ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
ap.add_argument("runs", nargs="*", metavar="NETWORK VARIANT", help="pairs such as: base all plus strict (default: all six)")
args = ap.parse_args()
if len(args.runs) % 2: ap.error("give NETWORK VARIANT pairs, for example: plus strict")
RUNS = [(args.runs[i], args.runs[i + 1]) for i in range(0, len(args.runs), 2)] or ALL
for r in RUNS:
    if r not in ALL: ap.error(f"unknown version {r[0]} {r[1]}: NETWORK is base or plus, VARIANT is all, strict or fords")
URL = "https://tigerweb.geo.census.gov/arcgis/rest/services/TIGERweb/tigerWMS_Census2020/MapServer/10/query"
CACHE = "work/v4_blocks_cache.parquet"
need(MS, *(f"work/bldg_{n}_{v}.parquet" for n, v in RUNS))
if ("plus", "strict") in RUNS:
    need("work/groups_b_plus_strict.parquet", columns={"work/groups_b_plus_strict.parquet": ["pop_block", "hu_block", "n_located"]})


def fetch(x0, y0, x1, y1):
    q = dict(where="1=1", geometry=f"{x0},{y0},{x1},{y1}", geometryType="esriGeometryEnvelope", inSR=4326, outSR=4326,
             spatialRel="esriSpatialRelIntersects", outFields="GEOID,POP100,HU100", returnGeometry="true", f="geojson")
    for k in range(5):
        try:
            with urllib.request.urlopen(urllib.request.Request(URL + "?" + urllib.parse.urlencode(q), headers=UA), timeout=120) as r:
                d = json.loads(r.read())
            if "features" in d: return d["features"], d.get("exceededTransferLimit", False)
        except Exception as e:
            print("  fetch retry", k, repr(e)[:120], flush=True)
        time.sleep(3 * (k + 1))
    return None, False

con = duckdb.connect(); con.execute("SET threads=2; SET enable_progress_bar=false;")
# block cache: GEOID -> (polygon, POP100, HU100, nb)
blk = {}
if os.path.exists(CACHE):
    c = pd.read_parquet(CACHE)
    for g, p, h, n, w in zip(c.GEOID, c.POP100, c.HU100, c.nb, c.wkb):
        blk[g] = [shapely.from_wkb(w), int(p), int(h), int(n)]
    print("cache loaded:", len(blk), "blocks", flush=True)
order = list(blk.keys()); tree = STRtree([blk[g][0] for g in order]) if order else None; dirty = False
def add_blocks(feats):
    """Add new blocks and count ALL footprints whose bbox centre lies in each new block."""
    new = []
    for f in feats:
        gid = f["properties"]["GEOID"]
        if gid in blk or f.get("geometry") is None: continue
        blk[gid] = [shapely.geometry.shape(f["geometry"]), int(f["properties"]["POP100"] or 0), int(f["properties"]["HU100"] or 0), 0]
        new.append(gid)
    if not new: return 0
    polys = [blk[g][0] for g in new]
    ux0, uy0, ux1, uy1 = shapely.bounds(shapely.union_all(polys))
    ms = con.execute(f"SELECT (bbox.xmin+bbox.xmax)/2 x, (bbox.ymin+bbox.ymax)/2 y FROM '{MS}' WHERE bbox.xmax >= {ux0} AND bbox.xmin <= {ux1} AND bbox.ymax >= {uy0} AND bbox.ymin <= {uy1}").df()
    t = STRtree(polys)
    pi, bi = t.query(shapely.points(ms.x.values, ms.y.values), predicate="within")
    nb = np.bincount(bi, minlength=len(polys))
    for g, n in zip(new, nb): blk[g][3] = int(n)
    return len(new)
def locate(lon, lat):
    """Block GEOID (or None) for each point, from the cached blocks."""
    global tree, order, dirty
    if dirty or tree is None:
        order = list(blk.keys()); tree = STRtree([blk[g][0] for g in order]); dirty = False
    out = np.array([None] * len(lon), dtype=object)
    if not order: return out
    pi, bi = tree.query(shapely.points(lon, lat), predicate="within")
    out[pi] = np.array(order, dtype=object)[bi]
    return out
def save_cache():
    g = list(blk.keys())
    pd.DataFrame(dict(GEOID=g, POP100=[blk[k][1] for k in g], HU100=[blk[k][2] for k in g], nb=[blk[k][3] for k in g],
                      wkb=[shapely.to_wkb(blk[k][0]) for k in g])).to_parquet(CACHE)
t0 = time.time(); nfetch = 0; fails = []
for NET, VAR in RUNS:
    B = pd.read_parquet(f"work/bldg_{NET}_{VAR}.parquet", columns=["rg", "row", "comp", "lon", "lat", "GEOID"])
    B["block"] = None
    for i, (comp, idx) in enumerate(B.groupby("comp").groups.items()):
        bb = B.loc[idx]
        loc = locate(bb.lon.values, bb.lat.values)
        if (loc == None).any():                                  # some footprints fall in blocks not yet cached
            feats, trunc = fetch(bb.lon.min(), bb.lat.min(), bb.lon.max(), bb.lat.max()); nfetch += 1
            if feats is None: fails.append((NET, VAR, int(comp))); continue
            if trunc: print("  WARNING transfer limit exceeded for comp", comp, flush=True)
            if add_blocks(feats): dirty = True
            loc = locate(bb.lon.values, bb.lat.values)
        B.loc[idx, "block"] = loc
        if i % 100 == 0: print(NET, VAR, i, B.comp.nunique(), "fetches", nfetch, "blocks", len(blk), f"{time.time()-t0:.0f}s", flush=True)
    save_cache()
    ok = B.block.notna()
    B["ppl_blk"] = np.nan; B["hu_blk"] = np.nan
    nb = B.loc[ok, "block"].map(lambda g: blk[g][3]).astype(float)
    B.loc[ok, "ppl_blk"] = B.loc[ok, "block"].map(lambda g: blk[g][1]).astype(float) / nb
    B.loc[ok, "hu_blk"] = B.loc[ok, "block"].map(lambda g: blk[g][2]).astype(float) / nb
    B.drop(columns=["lon", "lat"]).to_parquet(f"work/v4_blockpop_bldg_{NET}_{VAR}.parquet")
    Gp = B.groupby("comp").agg(pop_block=("ppl_blk", "sum"), hu_block=("hu_blk", "sum"), n_located=("block", "count"), n_bldg=("row", "size")).reset_index()
    Gp.to_parquet(f"work/v4_blockpop_groups_{NET}_{VAR}.parquet")
    print(f"== {NET} {VAR}: buildings {len(B)}, located {int(ok.sum())}, residents (block) {Gp.pop_block.sum():.1f}, homes {Gp.hu_block.sum():.1f}, "
          f"fetches so far {nfetch}, blocks {len(blk)}, {time.time()-t0:.0f}s", flush=True)
print("failed fetches:", fails)
if ("plus", "strict") in RUNS:                                   # check against block_pop.py's own output
    G0 = pd.read_parquet("work/groups_b_plus_strict.parquet", columns=["comp", "pop_block", "hu_block", "n_located"])
    Gp = pd.read_parquet("work/v4_blockpop_groups_plus_strict.parquet").merge(G0, on="comp", suffixes=("", "_old"))
    print("check vs block_pop.py (plus strict): max |d residents|", float((Gp.pop_block - Gp.pop_block_old).abs().max()),
          "max |d homes|", float((Gp.hu_block - Gp.hu_block_old).abs().max()), "located differs in", int((Gp.n_located != Gp.n_located_old).sum()), "areas")
if fails:
    sys.exit(f"block_pop_v4.py: TIGERweb did not answer for {len(fails)} area(s), so their residents are missing: {fails[:10]}. "
             "Run it again: blocks already fetched are cached in work/v4_blocks_cache.parquet.")
