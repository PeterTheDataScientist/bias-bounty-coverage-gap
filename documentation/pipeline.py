"""
Bias Bounty Mapping Equity Challenge: coverage gap score, all four regions, one file.

    python pipeline.py --check --data-dir DIR   read the 44 inputs from DIR (never download), check each
                                                against INPUTS_MANIFEST.csv, build every region, write
                                                submission.csv, assert the README's published counts,
                                                print the sha256
    python pipeline.py --check                  the same, reading cache/ and downloading what is missing
    python pipeline.py --check --extra          also count every alternative convention measured in the
                                                writeup, so sensitivity.py can rebuild its tables

Challenge data only. No model, no random seed, no manual step, and no score file is read at any stage.

On 25 September 2026 the organisers removed the TIGER roads, Microsoft footprints, USGS facility and
CBP layers from their bucket. The Overture layers, tract polygons and sample submissions are still
there, byte for byte the files listed in INPUTS_MANIFEST.csv. So the pipeline now needs a local copy
of the removed layers: DIR may hold the files under the bucket's names (DIR/reference/REGION/FILE,
DIR/strata/REGION/FILE, DIR/REGION/FILE or DIR/FILE) or under the cache's (DIR/reference__REGION__FILE).
BIAS_DATA_DIR=DIR does the same for the tools that import this file.

The four conventions that decide the scored column are the entries in CONV below.
"""
import os, sys, csv, time, hashlib, argparse, urllib.request, urllib.error, warnings
import numpy as np, pandas as pd, geopandas as gpd, shapely, pyarrow.parquet as pq
from pyproj import Geod
warnings.filterwarnings("ignore", category=RuntimeWarning)

CONV = {
    "road_assignment": "clip",        # clip: split at tract boundaries in EPSG:5070 | midpoint: whole segment to its midpoint's tract
    "building_point": "centroid",     # centroid: true polygon centroid | bbox: centre of the covering bbox
    "place_predicate": "intersects",  # intersects: a place on a boundary counts in every tract it touches | within
    "output_decimals": 6,             # the reference is stored at 6 dp; None writes full precision
}

BASE = "https://data.source.coop/humane-intelligence/bias-bounty-mapping-equity-challenge"
UA = {"User-Agent": "Mozilla/5.0 (bias-bounty pipeline)"}   # the bucket returns 403 without one
CACHE = os.environ.get("BIAS_CACHE", "cache")
OUTDIR = os.environ.get("BIAS_OUT", "out")
ALBERS = "EPSG:5070"
REGIONS = ["northern-ca", "eastern-ok", "maricopa-az", "south-central-tx"]
OVT_HWY = ["motorway", "trunk", "primary", "secondary"]
TIGER_HWY = ["S1100", "S1200"]
CATS = {"fire": {"fire_department"},
        "ems": {"ambulance_and_ems_services"},
        "school": {"elementary_school", "middle_school", "high_school", "school",
                   "private_school", "public_school"}}
README = {"northern-ca": (591, 218), "eastern-ok": (1192, 253),
          "maricopa-az": (1593, 869), "south-central-tx": (6003, 1704)}   # scored tracts, tracts with no road component
GEOD = Geod(ellps="WGS84")
DATA_DIR = os.environ.get("BIAS_DATA_DIR")                 # --data-dir: local copies only, never a download
MANIFEST = os.path.join(os.path.dirname(os.path.abspath(__file__)), "INPUTS_MANIFEST.csv")
REMOVED = ("census-tiger-roads", "microsoft-buildings", "hifld-", "census-cbp")   # removed from the bucket, 25 Sep 2026
REMOVED_NOTE = ("The organisers removed the TIGER roads, Microsoft footprints, USGS facility and CBP layers from the\n"
                "challenge bucket on 25 September 2026, so these can no longer be downloaded. INPUTS_MANIFEST.csv lists\n"
                "all 44 inputs with their size and sha256; put copies in one folder and run\n"
                "  python pipeline.py --check --data-dir FOLDER")
T0 = time.time()
def log(m): print(f"[{time.time() - T0:7.1f}s] {m}", flush=True)


def inputs():
    """The 44 files pipeline.py reads, in the order it reads them (INPUTS_MANIFEST.csv, read_by pipeline.py)."""
    keys = []
    for r in REGIONS:
        keys += [f"strata/{r}/{r}-census-tracts.parquet", f"reference/{r}/{r}-sample-submission.csv"]
        keys += [f"reference/{r}/{r}-{n}" for n in (
            "overture-roads.parquet", "census-tiger-roads.parquet", "overture-buildings.parquet", "microsoft-buildings.parquet",
            "overture-pois.parquet", "hifld-fire-stations.csv", "hifld-ems-stations.csv", "hifld-schools.csv", "census-cbp.csv")]
    return keys


def local_copy(key):
    """A copy of this input in DATA_DIR, named as in the bucket (its folder tree, one folder per region, or flat)
    or as in the cache. None if there is none."""
    folder, region, name = key.split("/")
    for p in (os.path.join(DATA_DIR, key), os.path.join(DATA_DIR, key.replace("/", "__")),
              os.path.join(DATA_DIR, region, name), os.path.join(DATA_DIR, name)):
        if os.path.isfile(p):
            return p
    return None


def fetch(key):
    if DATA_DIR:
        p = local_copy(key)
        if p is None:
            sys.exit(f"{key} is not in {DATA_DIR} (looked for {key}, {key.replace('/', '__')}, "
                     f"{'/'.join(key.split('/')[1:])} and {key.split('/')[-1]} there).\n{REMOVED_NOTE}")
        return p
    dst = os.path.join(CACHE, key.replace("/", "__"))
    if not os.path.exists(dst):
        os.makedirs(CACHE, exist_ok=True)
        log(f"  downloading {key}")
        req = urllib.request.Request(f"{BASE}/{key}", headers=UA)
        try:
            with urllib.request.urlopen(req, timeout=1800) as r, open(dst + ".part", "wb") as f:
                while True:
                    b = r.read(1 << 22)
                    if not b:
                        break
                    f.write(b)
        except OSError as e:                                             # URLError, HTTPError, timeouts
            gone = isinstance(e, urllib.error.HTTPError) and e.code == 404 and any(k in key for k in REMOVED)
            sys.exit(f"could not download {BASE}/{key}\n  {e}\n" + (REMOVED_NOTE if gone else
                     f"  pipeline.py needs this layer at {dst}. Check the network, or copy the file there "
                     f"(BIAS_CACHE sets the folder), or use --data-dir."))
        os.rename(dst + ".part", dst)
    return dst


def prepare(keys):
    """Every input on disk before any work starts, or a stop that names what is missing and how to get it."""
    if DATA_DIR:
        missing = [k for k in keys if local_copy(k) is None]
        where = (f"in {DATA_DIR} (looked for DIR/reference/REGION/FILE, DIR/strata/REGION/FILE, DIR/REGION/FILE, "
                 f"DIR/FILE and the cache's DIR/reference__REGION__FILE)")
    else:                                          # the removed layers can only come from a cache made before 25 Sep
        missing = [k for k in keys if any(x in k for x in REMOVED) and not os.path.exists(os.path.join(CACHE, k.replace("/", "__")))]
        where = f"in {CACHE}/ and no longer in the bucket"
    if missing:
        sys.exit(f"{len(missing)} of the {len(keys)} inputs are not {where}:\n  " + "\n  ".join(missing) + f"\n{REMOVED_NOTE}")
    return [fetch(k) for k in keys]                # downloads, in cache mode, whatever is still in the bucket and not cached


def verify(keys, read_by="pipeline.py"):
    """Size and sha256 of every input against INPUTS_MANIFEST.csv; stop before building if any differs."""
    if not os.path.exists(MANIFEST):
        sys.exit(f"missing {MANIFEST}: it ships with pipeline.py and lists every input with its size and sha256")
    want = {row["file"]: row for row in csv.DictReader(open(MANIFEST)) if row["read_by"] == read_by}
    bad, total = [], 0
    for k in keys:
        p, row = fetch(k), want[k.split("/")[-1]]
        h = hashlib.sha256()
        with open(p, "rb") as f:
            for b in iter(lambda: f.read(1 << 23), b""):
                h.update(b)
        n = os.path.getsize(p); total += n
        if n != int(row["bytes"]) or h.hexdigest() != row["sha256"]:
            bad.append(f"{k}: {n} bytes, sha256 {h.hexdigest()} (INPUTS_MANIFEST.csv: {row['bytes']} bytes, sha256 {row['sha256']})")
    if bad:
        sys.exit(f"{len(bad)} input(s) differ from INPUTS_MANIFEST.csv, so the output would not be the scored file:\n  " + "\n  ".join(bad))
    log(f"inputs verified: {len(keys)} files, {total:,} bytes, every size and sha256 as in INPUTS_MANIFEST.csv")


def text_geoid(s):
    """GEOID is text. Maricopa is state FIPS 04 and an integer read drops the leading zero."""
    return s.astype(str).str.zfill(11)


def counts_by_tract(points, tracts, predicate):
    """Inner join, then attach back to the scored list by GEOID. A spatial outer join can drop
    tracts that match nothing."""
    j = gpd.sjoin(points, tracts[["GEOID", "geometry"]], how="inner", predicate=predicate)
    return j.groupby("GEOID").size()


# ---------------------------------------------------------------- roads
def split_lengths(lines_alb, tracts_alb):
    ov = gpd.overlay(lines_alb[["geometry"]], tracts_alb[["GEOID", "geometry"]], how="intersection", keep_geom_type=True)
    return ov.assign(L=ov.length).groupby("GEOID").L.sum()


def road_columns(region, tr_alb, tr_ll, extra):
    out = {}
    for side, key, col, keep, more in (("ovt", "overture-roads", "class", OVT_HWY, ["tertiary"]),
                                       ("tig", "census-tiger-roads", "MTFCC", TIGER_HWY, ["S1630"])):
        g = gpd.read_parquet(fetch(f"reference/{region}/{region}-{key}.parquet"), columns=[col, "geometry"])
        named = g[g[col].isin(keep)].reset_index(drop=True)
        alb = named.to_crs(ALBERS)                                       # project BEFORE any geometry operation
        out[f"{side}_road"] = split_lengths(alb, tr_alb)
        log(f"  {side} named highway: {len(named)} segments")
        if not extra:
            continue
        mid = gpd.GeoDataFrame({"L": alb.length}, geometry=alb.geometry.interpolate(0.5, normalized=True), crs=ALBERS)
        out[f"{side}_road_mid"] = gpd.sjoin(mid, tr_alb[["GEOID", "geometry"]], predicate="within").groupby("GEOID").L.sum()
        ll = gpd.overlay(named[["geometry"]].to_crs("EPSG:4326"), tr_ll[["GEOID", "geometry"]], how="intersection", keep_geom_type=True)
        out[f"{side}_road_ll"] = ll.assign(L=ll.to_crs(ALBERS).length).groupby("GEOID").L.sum()          # split in lon/lat, measure in 5070
        out[f"{side}_road_geo"] = ll.assign(L=[GEOD.geometry_length(x) for x in ll.geometry]).groupby("GEOID").L.sum()   # geodesic
        extra_cls = g[g[col].isin(more)].reset_index(drop=True).to_crs(ALBERS)
        out[f"{side}_road_{more[0].lower()}"] = split_lengths(extra_cls, tr_alb) if len(extra_cls) else pd.Series(dtype=float)
        log(f"  {side} extra road variants: midpoint, lon/lat split, geodesic, {more[0]}")
    return out


# ---------------------------------------------------------------- buildings
def building_columns(region, tr_alb, tr_ll, extra):
    out = {}
    for side, key in (("ovt", "overture-buildings"), ("ms", "microsoft-buildings")):
        pf = pq.ParquetFile(fetch(f"reference/{region}/{region}-{key}.parquet"))
        acc = {k: pd.Series(dtype="int64") for k in ("cen", "bbox", "int", "parts")}
        n = 0
        for g0 in range(0, pf.metadata.num_row_groups, 8):                 # streamed, never a whole layer in memory
            groups = list(range(g0, min(pf.metadata.num_row_groups, g0 + 8)))
            t = pf.read_row_groups(groups, columns=["geometry", "bbox"])
            geoms = shapely.from_wkb(t.column("geometry").to_numpy(zero_copy_only=False))
            n += len(geoms)
            want_cen = CONV["building_point"] == "centroid" or extra
            want_bbox = CONV["building_point"] == "bbox" or extra
            if want_cen:
                pts = gpd.GeoDataFrame(geometry=shapely.centroid(geoms), crs="EPSG:4326")
                acc["cen"] = acc["cen"].add(counts_by_tract(pts, tr_ll, "within"), fill_value=0)
            if want_bbox:
                b = t.column("bbox").combine_chunks()
                x = (np.asarray(b.field("xmin")) + np.asarray(b.field("xmax"))) / 2.0
                y = (np.asarray(b.field("ymin")) + np.asarray(b.field("ymax"))) / 2.0
                pts = gpd.GeoDataFrame(geometry=gpd.points_from_xy(x, y), crs="EPSG:4326").to_crs(ALBERS)
                acc["bbox"] = acc["bbox"].add(counts_by_tract(pts, tr_alb, "within"), fill_value=0)
            if extra:
                polys = gpd.GeoDataFrame(geometry=geoms, crs="EPSG:4326")           # every footprint touching the tract
                acc["int"] = acc["int"].add(counts_by_tract(polys, tr_ll, "intersects"), fill_value=0)
                parts = gpd.GeoDataFrame(geometry=shapely.centroid(shapely.get_parts(geoms)), crs="EPSG:4326")
                acc["parts"] = acc["parts"].add(counts_by_tract(parts, tr_ll, "within"), fill_value=0)   # a multipolygon counts once per part
        out[f"{side}_bldg"] = acc["cen" if CONV["building_point"] == "centroid" else "bbox"]
        if extra:
            for k in ("cen", "bbox", "int", "parts"):
                out[f"{side}_bldg_{k}"] = acc[k]
        log(f"  {side} buildings: {n} footprints")
    return out


# ---------------------------------------------------------------- places, facilities, CBP
def place_columns(region, tr_alb, extra):
    t = pq.read_table(fetch(f"reference/{region}/{region}-overture-pois.parquet"), columns=["bbox", "categories"])
    b = t.column("bbox").combine_chunks()
    x = (np.asarray(b.field("xmin")) + np.asarray(b.field("xmax"))) / 2.0      # a point's bbox is the point
    y = (np.asarray(b.field("ymin")) + np.asarray(b.field("ymax"))) / 2.0
    prim = np.asarray(t.column("categories").combine_chunks().field("primary").to_pylist(), dtype=object)
    pts = gpd.GeoDataFrame(geometry=gpd.points_from_xy(x, y), crs="EPSG:4326").to_crs(ALBERS)
    nonnull = np.array([p is not None for p in prim])
    out = {}
    for pred in ([CONV["place_predicate"]] if not extra else ["intersects", "within"]):
        sfx = "" if pred == CONV["place_predicate"] else f"_{pred}"
        out[f"ovt_places{sfx}"] = counts_by_tract(pts, tr_alb, pred)
        for k, cats in CATS.items():
            sel = np.array([p in cats for p in prim], bool)
            out[f"ovt_{k}{sfx}"] = counts_by_tract(pts[sel], tr_alb, pred)
        if extra:
            out[f"ovt_places_nonnull{sfx}"] = counts_by_tract(pts[nonnull], tr_alb, pred)
    log(f"  places: {len(prim)} ({int((~nonnull).sum())} with no primary category)")
    for k, key in (("fire", "hifld-fire-stations"), ("ems", "hifld-ems-stations"), ("school", "hifld-schools")):
        h = pd.read_csv(fetch(f"reference/{region}/{region}-{key}.csv"))
        hp = gpd.GeoDataFrame(geometry=gpd.points_from_xy(h.lon, h.lat), crs="EPSG:4326").to_crs(ALBERS)
        out[f"ref_{k}"] = counts_by_tract(hp, tr_alb, "within")
    return out


def region_counts(region, extra=False):
    log(f"=== {region}")
    tr = gpd.read_parquet(fetch(f"strata/{region}/{region}-census-tracts.parquet"), columns=["GEOID", "geometry"])
    tr["GEOID"] = text_geoid(tr.GEOID)
    tr_alb, tr_ll = tr.to_crs(ALBERS), tr.to_crs("EPSG:4326")
    scored = pd.read_csv(fetch(f"reference/{region}/{region}-sample-submission.csv"), dtype={"GEOID": str})
    df = pd.DataFrame({"GEOID": text_geoid(scored.GEOID)})
    missing = sorted(set(df.GEOID) - set(tr.GEOID))
    assert not missing, f"{region}: scored tracts with no polygon: {missing[:5]}"
    dropped = sorted(set(tr.GEOID) - set(df.GEOID))
    if dropped:
        log(f"  {len(dropped)} polygons not in the scored list (dropped by the organisers): {' '.join(dropped)}")
    cols = {}
    cols.update(road_columns(region, tr_alb, tr_ll, extra))
    cols.update(building_columns(region, tr_alb, tr_ll, extra))
    cols.update(place_columns(region, tr_alb, extra))
    for name, s in cols.items():
        v = df.GEOID.map(s).fillna(0)
        df[name] = v.astype(float) if "road" in name else v.astype("int64")
    cbp = pd.read_csv(fetch(f"reference/{region}/{region}-census-cbp.csv"), dtype={"GEOID": str})
    cbp["GEOID"] = text_geoid(cbp.GEOID)
    cbp = cbp.set_index("GEOID")
    df["cbp_estab"] = df.GEOID.map(cbp.cbp_estab).astype(float)             # fractional, used unrounded
    if extra:
        df["cbp_estab_res"] = df.GEOID.map(cbp.cbp_estab_res).astype(float)
    df["region"] = region
    return df


# ---------------------------------------------------------------- scoring
def gap(overture, reference, cap=True):
    """1 - min(1, overture/reference). Undefined (NaN) where the reference is zero: nothing to compare."""
    o, r = np.asarray(overture, float), np.asarray(reference, float)
    out = np.full(len(r), np.nan)
    ok = r > 0
    out[ok] = 1.0 - (np.minimum(1.0, o[ok] / r[ok]) if cap else o[ok] / r[ok])
    return out


def mean_defined(*cols):
    st = np.vstack(cols)
    with np.errstate(all="ignore"):
        return np.where(np.all(np.isnan(st), 0), np.nan, np.nanmean(st, axis=0))


def score(df, decimals=None):
    t = gap(df.ovt_road, df.tig_road)
    b = gap(df.ovt_bldg, df.ms_bldg)
    facilities = mean_defined(*(gap(df[f"ovt_{k}"], df[f"ref_{k}"]) for k in CATS))
    p = mean_defined(facilities, gap(df.ovt_places, df.cbp_estab))
    c = mean_defined(t, b, p)
    assert not np.isnan(c).any(), "a scored tract has no defined component"
    c = np.clip(c, 0, 1)
    if decimals is not None:
        c = np.round(c, decimals)
    return c, t, b, p


def write(path, geoid, c, decimals):
    with open(path, "w", newline="") as f:          # two columns only: GEOID, coverage_gap_score
        f.write("GEOID,coverage_gap_score\n")
        for g, v in zip(geoid, c):
            f.write(f"{g},{v:.{decimals}f}\n" if decimals is not None else f"{g},{float(v)!r}\n")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--check", action="store_true", help="check every input against INPUTS_MANIFEST.csv before building, "
                    "and the README's published counts after; print the output's sha256")
    ap.add_argument("--extra", action="store_true", help="also count the alternative conventions sensitivity.py measures")
    ap.add_argument("--data-dir", help="read the 44 inputs from this folder, named as in the bucket or as in cache/, and never download")
    ap.add_argument("--out", default="submission.csv")
    a = ap.parse_args()
    if a.data_dir:
        DATA_DIR = os.path.expanduser(a.data_dir)
    log(f"CONV = {CONV}")
    log(f"inputs: {'local copies in ' + DATA_DIR + ', no download' if DATA_DIR else CACHE + '/, downloading what is missing'}")
    prepare(inputs())
    if a.check:
        verify(inputs())
    df = pd.concat([region_counts(r, a.extra) for r in REGIONS], ignore_index=True)
    df = df.sort_values("GEOID", kind="stable").reset_index(drop=True)      # rows in GEOID order
    os.makedirs(OUTDIR, exist_ok=True)
    df.to_parquet(os.path.join(OUTDIR, "counts.parquet"), index=False)       # per-tract counts, for sensitivity.py
    c, t, b, p = score(df, CONV["output_decimals"])
    write(a.out, df.GEOID, c, CONV["output_decimals"])
    log(f"wrote {a.out}: {len(c)} rows, all-tract mean {c.mean():.6f}")
    if a.check:
        for r, (n, t_undef) in README.items():
            k = (df.region == r).values
            assert k.sum() == n, f"{r}: {k.sum()} scored rows against the README's {n}"
            assert int(np.isnan(t[k]).sum()) == t_undef, f"{r}: {int(np.isnan(t[k]).sum())} with no road component against {t_undef}"
        log("README counts reproduced: scored rows 591 / 1,192 / 1,593 / 6,003, no road component 218 / 253 / 869 / 1,704")
        log(f"undefined components: road {int(np.isnan(t).sum())}, building {int(np.isnan(b).sum())}, POI {int(np.isnan(p).sum())}")
        log(f"sha256 {hashlib.sha256(open(a.out, 'rb').read()).hexdigest()}")
