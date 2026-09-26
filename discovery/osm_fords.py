"""Step 0d. OpenStreetMap side: every ford / flood-prone / flood-hazard tag in the Texas extract
(openstreetmap.fr mirror, texas.osm.pbf, replication timestamp 2026-09-23T00:03:38Z, md5 86878eb08e87ad724ecb1ed6a0e26d60),
with version and timestamp, and the highway ways that pass through ford nodes.
Licence: ODbL 1.0, (c) OpenStreetMap contributors.

    python osm_fords.py --extract inputs/osm_2026-09-23   the two tables as the entry's run built them from the
                                                          23 Sep extract (shipped in this repository, ODbL 1.0)
    python osm_fords.py --pbf raw/texas.osm.pbf           build them from a Texas extract you downloaded (about
                                                          800 MB); the mirror serves only its latest extract,
                                                          so the counts will not match the entry's exactly

Either way it writes work/osm_fordtags.parquet and work/osm_ways_with_fordnodes.parquet."""
import argparse, os, time
import numpy as np, pandas as pd
from common import OSM_EXTRACT, arg_path, need as need_input

ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
src = ap.add_mutually_exclusive_group(required=True)
src.add_argument("--extract", metavar="DIR", help=f"folder with the two shipped CSV tables (normally {OSM_EXTRACT})")
src.add_argument("--pbf", metavar="FILE", help="a Texas .osm.pbf extract")
args = ap.parse_args()
t0 = time.time()

if args.extract:
    d = arg_path(args.extract)
    TAGS, WAYS = (os.path.join(d, f) for f in ("osm_fordtags_texas_extract_2026-09-23.csv", "osm_ways_with_fordnodes_texas_2026-09-23.csv"))
    need_input(TAGS, WAYS)
    # read every value exactly as written: empty means missing, nothing else does, and floats round-trip bit for bit
    txt = dict(keep_default_na=False, na_values=[""], float_precision="round_trip")
    F = pd.read_csv(TAGS, dtype={c: "str" for c in ("type", "ts", "ford", "flood_prone", "hazard", "highway", "name")} | {"waterway": "object"}, **txt)
    W = pd.read_csv(WAYS, dtype={c: "str" for c in ("ts", "highway", "name", "ref", "ford_nodes")}, **txt)
    W["ford_nodes"] = [[int(x) for x in s.split()] for s in W.ford_nodes]
else:
    import osmium
    PBF = arg_path(args.pbf)
    need_input(PBF)
    def wanted(tg):
        ford = tg.get("ford"); fp_ = tg.get("flood_prone"); hz = tg.get("hazard")
        return (ford is not None and ford != "no") or fp_ == "yes" or (hz is not None and "flood" in hz)
    rows = []; wayrefs = {}
    fp = osmium.FileProcessor(PBF, osmium.osm.NODE | osmium.osm.WAY).with_filter(osmium.filter.KeyFilter("ford", "flood_prone", "hazard"))
    for o in fp:
        tg = dict(o.tags)
        if not wanted(tg): continue
        isn = o.is_node()
        rows.append(dict(type="n" if isn else "w", id=o.id, version=o.version, ts=o.timestamp.isoformat(),
                         ford=tg.get("ford"), flood_prone=tg.get("flood_prone"), hazard=tg.get("hazard"), highway=tg.get("highway"),
                         name=tg.get("name"), waterway=tg.get("waterway"),
                         lon=o.location.lon if isn else None, lat=o.location.lat if isn else None))
        if not isn: wayrefs[o.id] = [n.ref for n in o.nodes]
    F = pd.DataFrame(rows)
    print("tagged elements", len(F), f"{time.time()-t0:.0f}s", flush=True)
    fordnodes = set(F.id[(F.type == "n") & F.ford.notna()])
    W = []
    for w in osmium.FileProcessor(PBF, osmium.osm.WAY).with_filter(osmium.filter.KeyFilter("highway")):
        hit = None
        for n in w.nodes:
            if n.ref in fordnodes:
                hit = (hit or []) + [n.ref]
        if hit:
            W.append(dict(way=w.id, version=w.version, ts=w.timestamp.isoformat(), highway=w.tags.get("highway"),
                          name=w.tags.get("name"), ref=w.tags.get("ref"), n_ford_nodes=len(hit), ford_nodes=hit))
    W = pd.DataFrame(W)
    print("highway ways through ford nodes", len(W), f"{time.time()-t0:.0f}s", flush=True)
    need = set(r for refs in wayrefs.values() for r in refs)
    loc = {}
    if need:
        for n in osmium.FileProcessor(PBF, osmium.osm.NODE).with_filter(osmium.filter.IdFilter(need)):
            loc[n.id] = (n.location.lon, n.location.lat)
    for i, r in F[F.type == "w"].iterrows():
        pts = [loc[x] for x in wayrefs[r.id] if x in loc]
        if pts:
            F.at[i, "lon"] = float(np.mean([p[0] for p in pts])); F.at[i, "lat"] = float(np.mean([p[1] for p in pts]))
F.to_parquet("work/osm_fordtags.parquet"); W.to_parquet("work/osm_ways_with_fordnodes.parquet")
print(F.groupby(["type"]).size().to_dict()); print(F.ford.value_counts(dropna=False).head(10).to_dict())
print("flood_prone", (F.flood_prone == "yes").sum(), "hazard~flood", F.hazard.notna().sum())
print("ways through ford nodes by highway:", W.highway.value_counts().head(12).to_dict() if len(W) else {}, f"{time.time()-t0:.0f}s")
