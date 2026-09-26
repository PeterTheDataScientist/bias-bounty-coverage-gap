"""Step 24. Facilities behind the crossings: the schools, fire stations and EMS stations that sit inside the careful
set's 216 cut-off areas.

Method. A facility is inside an area by exactly the rule that put a building there in lwc_buildings.py:
  1. the road network is the 'plus' network of the lead version (Overture roads split at their connectors, service
     lanes and farm tracks included), each road piece labelled by the strict-list cut (work/edges_plus_strict.parquet
     row for row with work/graph_base_plus.parquet): the cut crossing piece, a piece of a cut-off area (its area id),
     or any other piece;
  2. only points within 300 m of some cut-off piece are considered;
  3. each such point goes to its nearest road piece within 300 m, searched among the pieces of every segment that lies
     within 400 m of a cut-off piece;
  4. if that piece belongs to a careful-set area (TIGER agrees, no 20 m near-miss, at least one building), the point
     is inside that area. A point equally near two pieces with different labels (for example at a junction) is
     reported as a tie, not broken.
Check before use: the same function applied to the Microsoft footprints (bbox centres, as lwc_buildings.py) gives back
the careful set's 22,469 buildings area by area, and the lead version's 37,270 but for 2 exact ties.

Facility layers (points): the challenge's fire station, EMS station and school layers (USGS The National Map
structures, which the bucket README calls HIFLD facilities; removed from the bucket on 25 Sep 2026, so they come
from a local copy, see fetch_challenge.py), and, as a cross-check from a layer still in the bucket, the challenge's
Overture places whose primary category is one the scorecard counts (documentation/pipeline.py CATS:
fire_department; ambulance_and_ems_services; elementary_school, middle_school, high_school, school, private_school,
public_school).
Outputs (work/ only, not shipped in ../results/): work/v5_facilities_candidates.csv (every facility point within
300 m of a cut-off piece, with its label), work/v5_facilities.json
"""
import argparse, json, time
import numpy as np, pandas as pd, pyarrow as pa, pyarrow.parquet as pq, pyarrow.compute as pc
import shapely, shapely.ops, pyproj, duckdb, geopandas as gpd
from shapely import STRtree
from common import EMS_STATIONS, EXTRA_SEGMENTS, FIRE_STATIONS, MS_BUILDINGS, OVT_PLACES, OVT_ROADS, SCHOOLS, TRACTS, need
from v4_common import careful_set, county_names

argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter).parse_args()
ROADS = [OVT_ROADS, EXTRA_SEGMENTS]
HIFLD = {"fire station": FIRE_STATIONS, "EMS station": EMS_STATIONS, "school": SCHOOLS}
need(*ROADS, MS_BUILDINGS, TRACTS, OVT_PLACES, *HIFLD.values(), "work/edges_plus_strict.parquet", "work/graph_base_plus.parquet",
     "work/bldg_plus_strict.parquet", "work/cuts_plus_strict.parquet", "work/lwc_unique.parquet")
CATS = {"fire station": ["fire_department"], "EMS station": ["ambulance_and_ems_services"],
        "school": ["elementary_school", "middle_school", "high_school", "school", "private_school", "public_school"]}
BUILD_R, LOCAL_R = 300.0, 400.0                      # lwc_buildings.py: dwithin 300 of a cut-off piece; local 400
t0 = time.time()
def log(m): print(f"[{time.time() - t0:6.1f}s] {m}", flush=True)
tf = pyproj.Transformer.from_crs("EPSG:4326", "EPSG:3083", always_xy=True)
def proj(c):
    x, y = tf.transform(c[:, 0], c[:, 1]); return np.column_stack([x, y])

# ---- 1. labels of every road piece, as lwc_buildings.py: -2 cut piece, area id if cut off, -1 otherwise
e = pq.read_table("work/edges_plus_strict.parquet", columns=["cu", "su", "sv", "cut"])
lab = np.where(e.column("cut").to_numpy(), -2,
               np.where(e.column("su").to_numpy() & e.column("sv").to_numpy(), e.column("cu").to_numpy(), -1)).astype(np.int64)
del e
g = pq.read_table("work/graph_base_plus.parquet", columns=["seg_id", "a0", "a1"])
SEG = g.column("seg_id"); A0 = g.column("a0").to_numpy(); A1 = g.column("a1").to_numpy(); del g
assert len(lab) == len(SEG)
G, core, Bc = careful_set()
CAREFUL = set(int(c) for c in core.comp)
PLUS_STRICT_BLDG = set(int(c) for c in G.comp[G.bldg > 0])
log(f"road pieces {len(lab):,}; cut-off pieces {(lab >= 0).sum():,}; careful areas {len(CAREFUL)}")

def pieces_of(ids):
    """seg_id -> [graph row, ...] in graph order, for the given segment ids."""
    mask = pc.is_in(SEG, value_set=pa.array(sorted(ids), type=SEG.type)).to_numpy(zero_copy_only=False)
    idx = np.where(mask)[0]; sids = pc.take(SEG, pa.array(idx)).to_pylist()
    out = {}
    for i, s in zip(idx, sids): out.setdefault(s, []).append(int(i))
    return out

def cut_geoms(t, rows_of, keep=None):
    """Sub-piece geometries (EPSG:3083) for the segments in table t, as lwc_buildings.subedges()."""
    og, ol = [], []
    geo = shapely.transform(shapely.from_wkb(t.geometry.values), proj)
    for sid, gm in zip(t.id.values, geo):
        for i in rows_of[sid]:
            if keep is not None and not keep(lab[i]): continue
            try: s = shapely.ops.substring(gm, A0[i], A1[i], normalized=True)
            except Exception: s = gm
            og.append(s); ol.append(lab[i])
    return og, ol

# ---- 2. every cut-off piece (all plus/strict areas, as lwc_buildings.py)
rows_s = pieces_of(set(pc.take(SEG, pa.array(np.where(lab >= 0)[0])).to_pylist()))
sg, sl = [], []
for f in ROADS:
    pf = pq.ParquetFile(f)
    for rg in range(pf.num_row_groups):
        t = pf.read_row_group(rg, columns=["id", "geometry"]).to_pandas(); t = t[t.id.isin(rows_s.keys())]
        if len(t):
            a, b = cut_geoms(t, rows_s, keep=lambda L: L >= 0); sg += a; sl += b
SG = STRtree(np.array(sg, dtype=object)); SL = np.array(sl)
log(f"cut-off pieces with geometry {len(sg):,}")

def assign(lonlat):
    """Area label for each point by the building rule; returns a DataFrame (i, label, dist_m, tie_labels)."""
    pts = shapely.points(proj(np.asarray(lonlat, float)))
    cand = np.unique(SG.query(pts, predicate="dwithin", distance=BUILD_R)[0])
    res = pd.DataFrame(dict(i=np.arange(len(pts)), label=np.nan, dist_m=np.nan, tie_labels=""))
    if len(cand) == 0: return res
    cp = pts[cand]; CT = STRtree(cp)
    ids_near = set()
    for f in ROADS:                                   # segments within 300 m of a candidate AND within 400 m of a cut-off piece
        pf = pq.ParquetFile(f)
        for rg in range(pf.num_row_groups):
            t = pf.read_row_group(rg, columns=["id", "geometry"]).to_pandas()
            gm = shapely.transform(shapely.from_wkb(t.geometry.values), proj)
            near_c = np.unique(CT.query(gm, predicate="dwithin", distance=BUILD_R)[0])
            if len(near_c) == 0: continue
            near_s = np.unique(SG.query(gm[near_c], predicate="dwithin", distance=LOCAL_R)[0])
            ids_near.update(t.id.values[near_c[near_s]])
    rows_l = pieces_of(ids_near)
    lg, ll = [], []
    for f in ROADS:
        pf = pq.ParquetFile(f)
        for rg in range(pf.num_row_groups):
            t = pf.read_row_group(rg, columns=["id", "geometry"]).to_pandas(); t = t[t.id.isin(rows_l.keys())]
            if len(t):
                a, b = cut_geoms(t, rows_l); lg += a; ll += b
    LT = STRtree(np.array(lg, dtype=object)); LL = np.array(ll)
    (pi, ei), d = LT.query_nearest(cp, max_distance=BUILD_R, return_distance=True, all_matches=True)
    m = pd.DataFrame(dict(p=pi, lab=LL[ei], d=d)).drop_duplicates(["p", "lab"])
    first = m.groupby("p").agg(lab=("lab", "first"), d=("d", "min"), n=("lab", "size"))
    res.loc[cand[first.index.values], "dist_m"] = first.d.values
    one = first[first.n == 1]
    res.loc[cand[one.index.values], "label"] = one.lab.values
    for p in first.index[first.n > 1]:
        res.loc[cand[p], "tie_labels"] = " ".join(str(v) for v in sorted(set(int(x) for x in m.lab[m.p == p])))
    return res

# ---- 3. check: the rule gives back the careful set's buildings
pf = pq.ParquetFile(MS_BUILDINGS); rows = []
for rg in range(pf.num_row_groups):
    b = pf.read_row_group(rg, columns=["bbox"]).column("bbox").combine_chunks()
    x = (b.field("xmin").to_numpy() + b.field("xmax").to_numpy()) / 2; y = (b.field("ymin").to_numpy() + b.field("ymax").to_numpy()) / 2
    pts = shapely.points(proj(np.column_stack([x, y])))
    c = np.unique(SG.query(pts, predicate="dwithin", distance=BUILD_R)[0])
    if len(c): rows.append(pd.DataFrame(dict(rg=rg, row=c, lon=x[c], lat=y[c])))
MSC = pd.concat(rows, ignore_index=True); del rows
log(f"footprints within 300 m of a cut-off piece: {len(MSC):,}")
a = assign(MSC[["lon", "lat"]].values)
MSC["label"] = a.label.values; MSC["tie"] = a.tie_labels.values
mine = MSC[MSC.label.isin(CAREFUL)][["rg", "row", "label"]].astype(int)
ref = Bc[["rg", "row", "comp"]].astype(int)
j = ref.merge(mine, on=["rg", "row"], how="outer", indicator=True)
same = int(((j._merge == "both") & (j.comp == j.label)).sum())
Ball = pd.read_parquet("work/bldg_plus_strict.parquet", columns=["rg", "row", "comp"]).astype(int)
ja = Ball.merge(MSC[["rg", "row", "label", "tie"]], on=["rg", "row"], how="left")
ties_a = ja[ja.tie.fillna("") != ""]
check = dict(careful_buildings_reference=int(len(ref)), reassigned_same_area=same,
             reference_only=int((j._merge == "left_only").sum()), rule_only=int((j._merge == "right_only").sum()),
             different_area=int(((j._merge == "both") & (j.comp != j.label)).sum()),
             ties_among_reference=int(MSC.merge(ref, on=["rg", "row"]).tie.ne("").sum()),
             lead_version_buildings_reference=int(len(Ball)), lead_version_reassigned_same_area=int((ja.label == ja.comp).sum()),
             lead_version_ties=int(len(ties_a)),
             lead_version_ties_including_reference_area=int(sum(str(c) in t.split() for c, t in zip(ties_a.comp, ties_a.tie))),
             lead_version_other=int(len(ja) - (ja.label == ja.comp).sum() - len(ties_a)),
             rule_assigns_to_lead_areas_not_in_reference=int(len(MSC[MSC.label.notna() & (MSC.label >= 0)].merge(Ball, on=["rg", "row"], how="left", indicator=True).query("_merge == 'left_only'"))))
log(f"check: {check}")
if check["reassigned_same_area"] != check["careful_buildings_reference"] or check["rule_only"] or check["different_area"]:
    raise SystemExit("the rule does not give back the careful set's buildings; the facility counts would not be comparable")

# ---- 4. facility points
F = []
for kind, f in HIFLD.items():
    h = pd.read_csv(f, dtype=str)
    F.append(pd.DataFrame(dict(source="USGS/HIFLD layer", kind=kind, fid=h["permanent_identifier"], name=h["name"],
                               address=(h["address"].fillna("") + ", " + h["city"].fillna("")).str.strip(", "),
                               lon=h["lon"].astype(float), lat=h["lat"].astype(float), category="")))
con = duckdb.connect(); con.execute("SET threads=2; SET memory_limit='1500MB'; SET enable_progress_bar=false;")
allc = [c for v in CATS.values() for c in v]
P = con.execute(f"""SELECT id, names.primary AS name, categories.primary AS category, operating_status,
       coalesce(addresses[1].freeform, '') || ', ' || coalesce(addresses[1].locality, '') AS address,
       (bbox.xmin + bbox.xmax) / 2 AS lon, (bbox.ymin + bbox.ymax) / 2 AS lat
       FROM '{OVT_PLACES}' WHERE categories.primary IN ({", ".join("'" + c + "'" for c in allc)})""").df()
kind_of = {c: k for k, v in CATS.items() for c in v}
F.append(pd.DataFrame(dict(source="Overture places", kind=P.category.map(kind_of), fid=P.id, name=P.name,
                           address=P.address.str.strip(", "), lon=P.lon, lat=P.lat,
                           category=P.category + np.where(P.operating_status.fillna("open") != "open", " (" + P.operating_status.fillna("") + ")", ""))))
F = pd.concat(F, ignore_index=True)
log(f"facility points: {F.groupby(['source', 'kind']).size().to_dict()}")
a = assign(F[["lon", "lat"]].values)
F["label"] = a.label.values; F["dist_m"] = a.dist_m.values; F["tie_labels"] = a.tie_labels.values
C = F[F.dist_m.notna()].copy()
def where(r):
    if r.tie_labels:
        labs = [int(v) for v in r.tie_labels.split()]
        return "tie, one side careful" if any(v in CAREFUL for v in labs) else "tie, no careful side"
    L = int(r.label)
    if L in CAREFUL: return "inside careful area"
    if L in PLUS_STRICT_BLDG: return "inside other cut-off area (lead version)"
    if L >= 0: return "inside cut-off area without buildings"
    return "crossing piece" if L == -2 else "outside (connected road)"
C["where"] = C.apply(where, axis=1)
# context for the inside ones
tr = pd.read_parquet(TRACTS, columns=["GEOID", "geometry"])
tr = gpd.GeoDataFrame(tr[["GEOID"]], geometry=shapely.from_wkb(tr.geometry), crs="EPSG:4326")      # as lwc_buildings.py
gp = gpd.GeoDataFrame(C, geometry=gpd.points_from_xy(C.lon, C.lat), crs="EPSG:4326")
C = pd.DataFrame(gpd.sjoin(gp, tr, how="left", predicate="within").drop(columns=["geometry", "index_right"]))
names = county_names(); C["county"] = C.GEOID.str[:5].map(names)
X = pd.read_parquet("work/edges_plus_strict.parquet", columns=["cu", "cv", "su", "sv", "cut"])
Xc = X[X.cut]; del X
touch = pd.concat([pd.DataFrame(dict(comp=Xc.cu[Xc.su].values, edge=Xc.index[Xc.su].values)),
                   pd.DataFrame(dict(comp=Xc.cv[Xc.sv].values, edge=Xc.index[Xc.sv].values))]).drop_duplicates()
cuts = pd.read_parquet("work/cuts_plus_strict.parquet", columns=["edge", "src", "src_id"]).merge(
    pd.read_parquet("work/lwc_unique.parquet", columns=["src", "src_id", "road_eff", "stream", "lwc_type"]), on=["src", "src_id"])
touch = touch.merge(cuts, on="edge")
def crossings_of(comp):
    t = touch[touch.comp == comp]
    return "; ".join(f"{r.src}:{r.src_id} {r.road_eff if isinstance(r.road_eff, str) else 'unnamed road'} over "
                     f"{r.stream if isinstance(r.stream, str) else 'unnamed stream'}" for r in t.itertuples())
gi = G.set_index("comp")
C["area"] = np.where(C["where"] == "inside careful area", C.label, np.nan)
C["area_buildings"] = C.area.map(lambda c: np.nan if pd.isna(c) else int(gi.loc[int(c), "bldg"]))
C["area_single_crossing"] = C.area.map(lambda c: "" if pd.isna(c) else bool(gi.loc[int(c), "single_crossing"]))
C["area_crossings"] = C.area.map(lambda c: "" if pd.isna(c) else crossings_of(int(c)))
C = C.sort_values(["where", "source", "kind", "name"]).reset_index(drop=True)
C.to_csv("work/v5_facilities_candidates.csv", index=False)
cnt = C.groupby(["source", "kind", "where"]).size().unstack(fill_value=0)
inside = C[C["where"] == "inside careful area"]
hif = inside[inside.source == "USGS/HIFLD layer"]; ovt = inside[inside.source == "Overture places"]
summary = dict(usgs_hifld={k: int((hif.kind == k).sum()) for k in HIFLD}, usgs_hifld_areas=int(hif.area.nunique()),
               usgs_hifld_single_crossing=int(hif.area_single_crossing.astype(bool).sum()),
               overture_places={k: int((ovt.kind == k).sum()) for k in CATS}, overture_places_areas=int(ovt.area.nunique()),
               lead_version_usgs_hifld={k: int(((C.source == "USGS/HIFLD layer") & (C.kind == k) & C["where"].isin(["inside careful area", "inside other cut-off area (lead version)"])).sum()) for k in HIFLD})
out = dict(summary=summary, method="building-to-road rule of lwc_buildings.py (nearest plus-network piece within 300 m; local pieces within 400 m of a cut-off piece); ties listed",
           check_against_careful_buildings=check,
           facility_points={f"{s_} / {k_}": int(v) for (s_, k_), v in F.groupby(["source", "kind"]).size().items()},
           candidates_within_300m_of_a_cut_off_piece=int(len(C)),
           counts_by_where={f"{s} / {k}": {w: int(v) for w, v in row.items() if v} for (s, k), row in cnt.iterrows()},
           inside_careful=[dict(source=r.source, kind=r.kind, name=r.name, category=r.category, address=r.address, lon=round(r.lon, 6), lat=round(r.lat, 6),
                                area=int(r.area), county=r.county, tract=r.GEOID, area_buildings=int(r.area_buildings),
                                area_single_crossing=bool(r.area_single_crossing), area_crossings=r.area_crossings, dist_to_road_m=round(r.dist_m, 1))
                           for r in inside.itertuples()],
           ties=[dict(source=r.source, kind=r.kind, name=r.name, tie_labels=r.tie_labels, careful_side=[int(v) for v in r.tie_labels.split() if int(v) in CAREFUL])
                 for r in C[C.tie_labels != ""].itertuples()])
json.dump(out, open("work/v5_facilities.json", "w"), indent=1, default=str)
print(json.dumps(dict(summary=summary, check=check), indent=1))
for r in out["inside_careful"]:
    print(f"  {r['source']:<17} {r['kind']:<13} {r['name']}, {r['address']} (area {r['area']}, {r['county']}, tract {r['tract']})")
log("wrote work/v5_facilities.json and work/v5_facilities_candidates.csv")
