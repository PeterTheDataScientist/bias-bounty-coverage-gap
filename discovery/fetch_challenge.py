"""Step 0b. The nine south-central-tx challenge layers the discovery reads: tract polygons, the strata tract table,
Overture roads, Microsoft building footprints, TIGER roads, the fire station, EMS station and school layers, and
Overture places (about 1.8 GB together). INPUTS_MANIFEST.csv lists each with its size and sha256.

    python fetch_challenge.py                  download into the shared cache what is missing (the layers still in
                                               the organisers' bucket only; see below)
    python fetch_challenge.py --data-dir DIR   use local copies in DIR instead and download nothing: check that every
                                               layer is there and matches INPUTS_MANIFEST.csv (BIAS_DATA_DIR=DIR is
                                               the same; bash run_all.sh --data-dir DIR sets it for every step)
    python fetch_challenge.py --verify         also check the cached layers against INPUTS_MANIFEST.csv

25 September 2026: the organisers removed the TIGER/Line roads, Microsoft building footprints, HIFLD facilities and
CBP establishments from every region of the bucket (Source Cooperative, no key, no login). Five of the nine files here
are among them, so a fresh run needs a copy made before that date, passed with --data-dir; DIR may hold the files under
the bucket's names (DIR/reference/REGION/FILE, DIR/strata/REGION/FILE, DIR/REGION/FILE or DIR/FILE) or the cache's
(DIR/reference__REGION__FILE). Original public sources: Microsoft Global ML Building Footprints
(https://github.com/microsoft/GlobalMLBuildingFootprints) and U.S. Census Bureau TIGER/Line 2025 roads
(https://www2.census.gov/geo/tiger/TIGER2025/ROADS/); the challenge's copies were clipped to the region, so a new
download from those is not the same file and has not been tested here. The data stays in the cache or your folder and
is never committed: the challenge shares it under CC BY-SA 4.0 and this repository does not redistribute it."""
import argparse, csv, hashlib, os, sys, urllib.error, urllib.request
import common
from common import BUCKET, CACHE, CHALLENGE_KEYS, MANIFEST, REMOVED, REMOVED_NOTE, UA

ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
ap.add_argument("--data-dir", help="folder of local copies of the challenge layers; nothing is downloaded")
ap.add_argument("--verify", action="store_true", help="check cached layers against INPUTS_MANIFEST.csv too")
args = ap.parse_args()
if args.data_dir:
    common.DATA_DIR = os.path.abspath(os.path.expanduser(common.arg_path(args.data_dir)))
DATA_DIR = common.DATA_DIR
if DATA_DIR and not os.path.isdir(DATA_DIR):
    sys.exit(f"--data-dir: {DATA_DIR} is not a folder")
WANT = {r["file"]: r for r in csv.DictReader(open(MANIFEST))}


def check(key, path):
    """Size and sha256 of one file against INPUTS_MANIFEST.csv; returns a problem or None."""
    row = WANT.get(key.split("/")[-1])
    if row is None:
        return f"{key}: not in INPUTS_MANIFEST.csv"
    n = os.path.getsize(path)
    if n != int(row["bytes"]):
        return f"{key}: {n:,} bytes, INPUTS_MANIFEST.csv says {int(row['bytes']):,}"
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for b in iter(lambda: f.read(1 << 22), b""):
            h.update(b)
    if h.hexdigest() != row["sha256"]:
        return f"{key}: sha256 {h.hexdigest()}, INPUTS_MANIFEST.csv says {row['sha256']}"
    return None


missing, bad = [], []
if DATA_DIR:
    for key in CHALLENGE_KEYS:
        p = common.local_copy(key)
        if p is None:
            print(f"MISSING      {key}", flush=True); missing.append(key); continue
        problem = check(key, p)
        print(f"{'DIFFERS' if problem else 'ok':<12} {key}   {p}", flush=True)
        if problem:
            bad.append(problem)
else:
    os.makedirs(CACHE, exist_ok=True)
    for key in CHALLENGE_KEYS:
        dst = common.challenge(key)
        if os.path.exists(dst):
            problem = check(key, dst) if args.verify else None
            print(f"{'DIFFERS' if problem else 'cached':<12} {key}", flush=True)
            if problem:
                bad.append(problem)
            continue
        print(f"downloading  {key}", flush=True)
        try:
            with urllib.request.urlopen(urllib.request.Request(f"{BUCKET}/{key}", headers=UA), timeout=1800) as r, \
                    open(dst + ".part", "wb") as f:
                while True:
                    b = r.read(1 << 22)
                    if not b:
                        break
                    f.write(b)
        except OSError as e:
            if os.path.exists(dst + ".part"):
                os.remove(dst + ".part")
            gone = isinstance(e, urllib.error.HTTPError) and e.code in (403, 404) and any(k in key for k in REMOVED)
            print(f"  {'removed from the bucket' if gone else 'could not download'}: {BUCKET}/{key} ({e})", flush=True)
            missing.append(key)
            continue
        os.rename(dst + ".part", dst)                  # never leave a half-written file under the final name
        problem = check(key, dst)
        if problem:
            bad.append(problem)
if missing or bad:
    msg = []
    if missing:
        where = f"in {DATA_DIR}" if DATA_DIR else f"in {CACHE} and not downloadable"
        msg.append(f"{len(missing)} of the {len(CHALLENGE_KEYS)} layers are not {where}:\n  " + "\n  ".join(missing))
    if bad:
        msg.append(f"{len(bad)} layer(s) differ from INPUTS_MANIFEST.csv, so the run would not reproduce the entry:\n  " + "\n  ".join(bad))
    sys.exit("\n".join(msg) + "\n" + REMOVED_NOTE)
print(f"all {len(CHALLENGE_KEYS)} layers are in {DATA_DIR or CACHE}" +
      (", each matching INPUTS_MANIFEST.csv" if DATA_DIR or args.verify else ""))
