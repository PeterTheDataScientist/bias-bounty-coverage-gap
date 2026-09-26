"""Paths shared by the discovery scripts, and one check that stops a script with a clear message when an input
is missing.

Every script imports this module first. It moves into this folder, so raw/, work/, figs/ and figs_img/ always
mean the folders next to these scripts, whichever directory you start from. A path you give on a command line
is read relative to the directory you started from.

    python common.py        lists every input the run needs and says which are present

Environment variables (all optional):
    BIAS_DATA_DIR  a folder of local copies of the challenge layers: every script reads them from there and nothing
                   is downloaded (bash run_all.sh --data-dir DIR sets it). The files may sit under the bucket's
                   names (DIR/reference/REGION/FILE, DIR/strata/REGION/FILE, DIR/REGION/FILE or DIR/FILE) or under
                   the cache's (DIR/reference__REGION__FILE). Needed since 25 Sep 2026, see REMOVED_NOTE.
    BIAS_CACHE     the challenge-data cache shared with documentation/pipeline.py (default ../documentation/cache)
    BIAS_COUNTS    per-tract counts written by `python pipeline.py --check --extra`
                   (default ../documentation/out/counts.parquet)
    NCEI_DIR       a folder holding (or to receive) the 90 NOAA Storm Events files ncei_events.py reads (default raw/ncei)
"""
import os, re, sys

HERE = os.path.dirname(os.path.abspath(__file__))
START = os.getcwd()
CACHE = os.path.abspath(os.environ.get("BIAS_CACHE", os.path.join(HERE, os.pardir, "documentation", "cache")))
COUNTS = os.path.abspath(os.environ.get("BIAS_COUNTS", os.path.join(HERE, os.pardir, "documentation", "out", "counts.parquet")))
DATA_DIR = os.path.abspath(os.path.expanduser(os.environ["BIAS_DATA_DIR"])) if os.environ.get("BIAS_DATA_DIR") else None
NCEI_DIR = os.path.abspath(os.path.expanduser(os.environ["NCEI_DIR"])) if os.environ.get("NCEI_DIR") else os.path.join(HERE, "raw", "ncei")
os.chdir(HERE)
for _d in ("raw", "work"):
    os.makedirs(_d, exist_ok=True)

REGION = "south-central-tx"
BUCKET = "https://data.source.coop/humane-intelligence/bias-bounty-mapping-equity-challenge"
UA = {"User-Agent": "bias-bounty-research/1.0"}
MANIFEST = os.path.join(HERE, "INPUTS_MANIFEST.csv")   # file, region, bytes, sha256 of every challenge layer read here
REMOVED = ("census-tiger-roads", "microsoft-buildings", "hifld-", "census-cbp")   # gone from the bucket, 25 Sep 2026
ORIGINAL = {"microsoft-buildings": "Microsoft Global ML Building Footprints, https://github.com/microsoft/GlobalMLBuildingFootprints",
            "census-tiger-roads": "U.S. Census Bureau TIGER/Line 2025 roads, https://www2.census.gov/geo/tiger/TIGER2025/ROADS/",
            "hifld-": "USGS The National Map structures (the bucket README calls the layers HIFLD facilities)"}
REMOVED_NOTE = ("On 25 September 2026 the organisers removed the TIGER/Line roads, Microsoft building footprints, HIFLD\n"
                "facilities and CBP establishments from every region of the challenge bucket, so these layers can no longer\n"
                "be downloaded. Use a copy made before that date: put it in a folder and run\n"
                "    bash run_all.sh --data-dir FOLDER        (or BIAS_DATA_DIR=FOLDER for a single script)\n"
                "INPUTS_MANIFEST.csv gives the size and sha256 of every file the entry read, so you can check your copy.\n"
                "The original public sources are " + "; ".join(ORIGINAL.values()) + ".\n"
                "The challenge's copies were clipped to the region, so a new download from them is not the same file.")


def local_copy(key):
    """A copy of this layer in BIAS_DATA_DIR under the bucket's or the cache's name, or None
    (the same places documentation/pipeline.py --data-dir looks)."""
    folder, region, name = key.split("/")
    for p in (os.path.join(DATA_DIR, key), os.path.join(DATA_DIR, key.replace("/", "__")),
              os.path.join(DATA_DIR, region, name), os.path.join(DATA_DIR, name)):
        if os.path.isfile(p):
            return p
    return None


def challenge(key):
    """Local path of one challenge layer: the copy in BIAS_DATA_DIR when that is set (a path that does not exist if
    the copy is missing, so need() names it), otherwise the shared cache, named as documentation/pipeline.py caches it."""
    if DATA_DIR:
        return local_copy(key) or os.path.join(DATA_DIR, key)
    return os.path.join(CACHE, key.replace("/", "__"))


CHALLENGE_KEYS = [f"strata/{REGION}/{REGION}-census-tracts.parquet",
                  f"strata/{REGION}/{REGION}-strata-tract-table.parquet",
                  f"reference/{REGION}/{REGION}-overture-roads.parquet",
                  f"reference/{REGION}/{REGION}-microsoft-buildings.parquet",
                  f"reference/{REGION}/{REGION}-census-tiger-roads.parquet",
                  f"reference/{REGION}/{REGION}-hifld-fire-stations.csv",
                  f"reference/{REGION}/{REGION}-hifld-ems-stations.csv",
                  f"reference/{REGION}/{REGION}-hifld-schools.csv",
                  f"reference/{REGION}/{REGION}-overture-pois.parquet"]
(TRACTS, STRATA, OVT_ROADS, MS_BUILDINGS, TIGER_ROADS,
 FIRE_STATIONS, EMS_STATIONS, SCHOOLS, OVT_PLACES) = (challenge(k) for k in CHALLENGE_KEYS)
EXTRA_SEGMENTS = "work/extra_segments.parquet"      # Overture service, track, living_street, unknown (fetch_overture_extra.py)
COMPONENTS = "work/bias_components.parquet"         # scorecard components per tract (scorecard_inputs.py)
TRACT_BUILDINGS = "work/tract_ms_bldg.parquet"      # Microsoft footprints per tract (scorecard_inputs.py)
LWC_SNAPSHOT = "inputs/lwc_2026-09-24"              # the two crossing inventories as retrieved on 24 Sep 2026
OSM_EXTRACT = "inputs/osm_2026-09-23"               # OSM ford and flood tags from the Texas extract of 23 Sep 2026
AUDIT = os.path.join(os.pardir, "results", "audit")  # the imagery audit's record: sample, both readings, extra views
NCEI_MANIFEST = os.path.join(os.pardir, "results", "ncei", "ncei_manifest.json")  # the NOAA files the entry read (sha256)
SEED = 20260926                                     # every random step of the later analysis steps (15 to 23)

# which command makes each input, for the error message
MAKERS = [
    (re.escape(COUNTS), "cd ../documentation && python pipeline.py --check --extra"),
    (r"(census-tiger-roads|microsoft-buildings|hifld-|census-cbp)",
     "a copy made before 25 Sep 2026, when this layer was removed from the challenge bucket: bash run_all.sh "
     "--data-dir FOLDER (INPUTS_MANIFEST.csv gives its size and sha256; README.md names the original source)"),
    (re.escape(DATA_DIR) if DATA_DIR else r"(?!x)x", "a copy in the folder given to --data-dir (INPUTS_MANIFEST.csv lists it); "
     "without --data-dir, python fetch_challenge.py downloads the layers still in the bucket"),
    (re.escape(CACHE), "python fetch_challenge.py"),
    (r"osm_(fordtags_texas_extract|ways_with_fordnodes_texas)_2026-09-23\.csv$",
     f"shipped with the repository in discovery/{OSM_EXTRACT}: check the folder given to --extract"),
    (r"^(?!raw/).*(txgio_lwc\.geojson|twdb_sfp_lwc\.geojson|retrieval_log\.json)$",
     f"shipped with the repository in discovery/{LWC_SNAPSHOT}: check the folder given to --snapshot"),
    (r"^raw/(txgio_lwc|twdb_sfp_lwc)\.geojson$", "python fetch_lwc.py (downloads them)"),
    (r"^raw/(txgio_lwc|twdb_sfp_lwc)\.parquet$|^raw/retrieval_log\.json$",
     f"python fetch_lwc.py --snapshot {LWC_SNAPSHOT}   (or python fetch_lwc.py for the lists as they are today)"),
    (r"^raw/texas\.osm\.pbf$", "download texas.osm.pbf, see README.md (or use python osm_fords.py --extract instead)"),
    (r"^work/osm_", f"python osm_fords.py --extract {OSM_EXTRACT}"),
    (r"^work/extra_segments\.", "python fetch_overture_extra.py"),
    (r"^work/(bias_components|tract_ms_bldg)\.parquet$", "python scorecard_inputs.py"),
    (r"^work/lwc_all\.parquet$", "python lwc_prepare.py"),
    (r"^work/lwc_seg_candidates\.parquet$", "python lwc_overture.py"),
    (r"^work/lwc_(unique|all_eval)\.parquet$", "python lwc_match_eval.py"),
    (r"^work/lwc_unique_osm\.parquet$", "python lwc_osm_eval.py"),
    (r"^work/tracts_lwc\.parquet$", "python lwc_tracts.py"),
    (r"^work/(graph_base|edges|cuts)_|^work/groups_(base|plus)_", "python lwc_graph.py NETWORK VARIANT"),
    (r"^work/(bldg|groups_b)_", "python lwc_buildings.py NETWORK VARIANT"),
    (r"^work/tiger_check_", "python tiger_check.py plus strict 10 single; python tiger_check.py plus strict 30 multi"),
    (r"^work/nearmiss_pairs_", "python nearmiss.py plus strict"),
    (r"^work/stranded_segs_", "python stranded_segs.py plus strict"),
    (r"^work/examples_confirmed\.csv$", "python examples.py"),
    (r"^work/(variants_table\.csv|discovery_numbers\.json)$", "python disc_numbers.py"),
    (r"^work/core_numbers\.json$", "python core_numbers.py"),
    (r"^work/v4_(blockpop_|blocks_cache)", "python block_pop_v4.py"),
    (r"^work/v4_variants", "python variants_v4.py"),
    (r"^work/v4_uncertainty", "python uncertainty.py"),
    (r"^work/v4_flood_attr_gap", "python flood_attr_gap.py"),
    (r"^work/v4_who", "python who_v4.py"),
    (r"^work/v4_per_tract_table", "python per_tract_table.py"),
    (r"^work/v4_audit_(sample|strata)\.csv$", "python precision_audit.py sample"),
    (r"^work/v4_audit_prep\.parquet$", "python precision_audit.py prep"),
    (r"^work/v4_audit_(summary\.json|verdicts\.csv)$", "python audit_summary.py"),
    (r"^work/v4_audit_agreement\.json$", "python audit_agreement.py"),
    (r"^figs/v4_", "python figures.py"),
    (r"^work/discovery_numbers_v4\.json$", "python numbers_v4.py"),
    (r"^work/v5_facilities", "python facilities.py"),
    (r"^work/v5_(occupancy|tigerweb_tract_sums)", "python occupancy.py"),
    (r"^work/v5_example_tracts", "python example_tracts.py"),
    (r"^work/discovery_numbers_v5\.json$", "python numbers_v5.py"),
    (r"^work/ncei_", "python ncei_events.py"),
    (r"results/audit/", "shipped with the repository in results/audit/ (the audit's record)"),
    (r"results/ncei/ncei_manifest\.json$", "shipped with the repository in results/ncei/ (the NOAA files the entry read)"),
]


def maker(path):
    for pat, cmd in MAKERS:
        if re.search(pat, path):
            return cmd
    return "an earlier step of run_all.sh"


def need(*paths, columns=None):
    """Stop with a clear message if any input is missing. columns={path: [names]} also checks parquet columns."""
    missing = [p for p in paths if not os.path.exists(p)]
    if missing:
        sys.exit(f"{os.path.basename(sys.argv[0])}: missing input\n" +
                 "\n".join(f"  {p}\n    made by: {maker(p)}" for p in missing))
    for p, cols in (columns or {}).items():
        import pyarrow.parquet as pq
        have = set(pq.ParquetFile(p).schema_arrow.names)
        lack = [c for c in cols if c not in have]
        if lack:
            sys.exit(f"{os.path.basename(sys.argv[0])}: {p} has no column(s) {', '.join(lack)}\n    made by: {maker(p)}")


def arg_path(p):
    """A path from the command line, relative to the directory the script was started from."""
    return p if os.path.isabs(p) else os.path.normpath(os.path.join(START, p))


def makedirs(*dirs):
    for d in dirs:
        os.makedirs(d, exist_ok=True)


if __name__ == "__main__":
    import argparse
    argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter).parse_args()
    rows = [(f"challenge layer ({'data dir' if DATA_DIR else 'cache'})", p) for p in
            (TRACTS, STRATA, OVT_ROADS, MS_BUILDINGS, TIGER_ROADS, FIRE_STATIONS, EMS_STATIONS, SCHOOLS, OVT_PLACES)]
    rows += [("per-tract counts (documentation, --extra)", COUNTS),
             ("crossing inventories", "raw/txgio_lwc.parquet"), ("crossing inventories", "raw/twdb_sfp_lwc.parquet"),
             ("OSM ford and flood tags", "work/osm_fordtags.parquet"), ("OSM ways through fords", "work/osm_ways_with_fordnodes.parquet"),
             ("Overture extra road classes", EXTRA_SEGMENTS), ("scorecard components", COMPONENTS),
             ("footprints per tract", TRACT_BUILDINGS),
             ("imagery audit: first reading (shipped)", os.path.join(AUDIT, "audit_verdicts.csv")),
             ("imagery audit: second reading (shipped)", os.path.join(AUDIT, "second_rater.csv")),
             ("NOAA Storm Events file list (shipped)", NCEI_MANIFEST)]
    print(f"discovery folder: {HERE}\n" + (f"data dir (BIAS_DATA_DIR): {DATA_DIR}\n" if DATA_DIR else f"cache: {CACHE}\n")
          + f"NOAA Storm Events files: {NCEI_DIR}\n")
    for what, p in rows:
        ok = os.path.exists(p)
        print(f"  {'present' if ok else 'MISSING':<8} {what:<44} {p}" + ("" if ok else f"\n           made by: {maker(p)}"))
