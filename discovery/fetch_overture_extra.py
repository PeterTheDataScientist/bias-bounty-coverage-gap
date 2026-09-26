"""Step 0e. Robustness data: Overture release 2026-08-19.0 road segments of the classes the challenge file leaves out
(service, track, living_street, unknown), inside the Texas bounding box, read anonymously from the public
Overture bucket (about 580 MB written to work/extra_segments.parquet). Same schema subset as the challenge roads,
so the graph code can read both. Overture keeps only recent releases online; once 2026-08-19.0 is retired this
step cannot be repeated, which is why ../results/ ships the outcomes as tables.

    python fetch_overture_extra.py            download, then compare the file with its row in INPUTS_MANIFEST.csv
    python fetch_overture_extra.py --check    compare an existing work/extra_segments.parquet only (run_all.sh does this
                                              when the file is already there)

INPUTS_MANIFEST.csv gives the size and sha256 of the file the entry's run read (downloaded on 24 Sep 2026; the downloads
of 25 and 26 Sep were byte for byte the same). A file that differs is reported but does not stop the run: DuckDB can
write the same rows as different bytes, so the result tables in ../results/ (git status) and the sha256 values in
../TESTING.md are what show whether anything changed.
Licence: the Overture transportation theme is ODbL 1.0, (c) OpenStreetMap contributors, with data from TomTom
(docs.overturemaps.org/attribution, read 25 Sep 2026)."""
import argparse, csv, hashlib, json, os, time
from common import EXTRA_SEGMENTS, MANIFEST, need
ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
ap.add_argument("--check", action="store_true", help="compare the existing file with INPUTS_MANIFEST.csv; download nothing")
args = ap.parse_args()
REL = "2026-08-19.0"


def compare():
    """Size and sha256 of work/extra_segments.parquet against its row in INPUTS_MANIFEST.csv; prints the outcome."""
    row = next(r for r in csv.DictReader(open(MANIFEST)) if r["file"] == os.path.basename(EXTRA_SEGMENTS))
    h = hashlib.sha256()
    with open(EXTRA_SEGMENTS, "rb") as f:
        for b in iter(lambda: f.read(1 << 22), b""):
            h.update(b)
    n = os.path.getsize(EXTRA_SEGMENTS)
    if n == int(row["bytes"]) and h.hexdigest() == row["sha256"]:
        print(f"{EXTRA_SEGMENTS}: {n:,} bytes, sha256 as in INPUTS_MANIFEST.csv (the file the entry read)")
    else:
        print(f"{EXTRA_SEGMENTS} DIFFERS from INPUTS_MANIFEST.csv: {n:,} bytes, sha256 {h.hexdigest()}; the entry read "
              f"{int(row['bytes']):,} bytes, sha256 {row['sha256']}. The run goes on: compare the tables in ../results/ "
              "(git status) and the sha256 values in ../TESTING.md to see whether any outcome changed.")


if args.check:
    need(EXTRA_SEGMENTS)
    compare()
    raise SystemExit(0)

import duckdb
con = duckdb.connect()
con.execute("INSTALL httpfs; LOAD httpfs; SET threads=2; SET memory_limit='5GB';")
# Unsigned, anonymous requests. The empty values matter: without them DuckDB signs requests with any AWS key it
# finds in the environment, and the public bucket then refuses them (HTTP 403).
con.execute("CREATE OR REPLACE SECRET anon (TYPE s3, PROVIDER config, KEY_ID '', SECRET '', REGION 'us-west-2', URL_STYLE 'vhost');")  # scan: allow (empty values)
t = time.time()
q = f"""
COPY (
  SELECT id, names, class, subclass, connectors, road_flags, sources, geometry, bbox
  FROM read_parquet('s3://overturemaps-us-west-2/release/{REL}/theme=transportation/type=segment/*.parquet')
  WHERE subtype = 'road' AND class IN ('service','track','living_street','unknown')
    AND bbox.xmin > -106.7 AND bbox.xmax < -93.4 AND bbox.ymin > 25.7 AND bbox.ymax < 36.6
) TO 'work/extra_segments.parquet' (FORMAT parquet, COMPRESSION zstd)"""
con.execute(q)
n = con.execute("SELECT class, count(*) FROM 'work/extra_segments.parquet' GROUP BY 1 ORDER BY 2 DESC").fetchall()
print(n, f"{time.time()-t:.0f}s")
json.dump(dict(release=REL, classes=["service", "track", "living_street", "unknown"], bbox=[-106.7, 25.7, -93.4, 36.6],
               retrieved_utc=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), counts=n), open("work/extra_segments.json", "w"), indent=1)
compare()
