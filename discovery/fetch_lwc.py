"""Step 0c. The two statewide Texas low-water-crossing inventories: the Texas Geographic Information Office (TxGIO)
Low Water Crossing layer and the Texas Water Development Board (TWDB) State Flood Plan layer "Low Water Crossing".

    python fetch_lwc.py                                   download both lists as they are today, through their
                                                          public ArcGIS REST query endpoints (no key, no login)
    python fetch_lwc.py --snapshot inputs/lwc_2026-09-24  use the lists exactly as the entry's run read them
    python fetch_lwc.py --convert-only                    rebuild the two tables from raw/*.geojson

A download goes page by page into GeoJSON with WGS84 coordinates and records the retrieval time, the sha256 and
the exact query URLs in raw/retrieval_log.json, so anyone can repeat it. Every mode then writes the two tables
lwc_prepare.py reads, raw/txgio_lwc.parquet and raw/twdb_sfp_lwc.parquet: one row per point, every attribute,
plus _lon and _lat from the point geometry. Both lists are TWDB publications, and the TWDB "freely grants
permission to copy and distribute its materials" (twdb.texas.gov/policies/site)."""
import argparse, datetime, hashlib, json, os, shutil, sys, time, urllib.parse, urllib.request
import pandas as pd
from common import UA, arg_path, need

SRC = {
  "txgio_lwc": "https://feature.geographic.texas.gov/arcgis/rest/services/Basemap/Low_Water_Crossing/MapServer/0/query",
  "twdb_sfp_lwc": "https://gis2.twdb.texas.gov/server/rest/services/OOP_FP_SFPV/Existing_Flood_Risk_Map/FeatureServer/5/query",
}
ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
mode = ap.add_mutually_exclusive_group()
mode.add_argument("--snapshot", metavar="DIR", help="folder holding txgio_lwc.geojson, twdb_sfp_lwc.geojson and retrieval_log.json")
mode.add_argument("--convert-only", action="store_true", help="skip the download and convert raw/*.geojson")
args = ap.parse_args()


def get(url, params):
    q = url + "?" + urllib.parse.urlencode(params)
    for k in range(5):
        try:
            with urllib.request.urlopen(urllib.request.Request(q, headers=UA), timeout=120) as r:
                return json.loads(r.read().decode()), q
        except Exception as e:
            print("retry", k, e, file=sys.stderr); time.sleep(5 * (k + 1))
    sys.exit(f"fetch_lwc.py: the endpoint did not answer after 5 tries:\n  {q}\n"
             f"  To use the lists as the entry's run read them: python fetch_lwc.py --snapshot inputs/lwc_2026-09-24")


def to_table(name):
    """GeoJSON to the table lwc_prepare.py reads: every attribute, plus _lon and _lat from the point geometry."""
    feats = json.load(open(f"raw/{name}.geojson"))["features"]
    d = pd.DataFrame([f["properties"] for f in feats])
    d["_lon"] = [f["geometry"]["coordinates"][0] for f in feats]
    d["_lat"] = [f["geometry"]["coordinates"][1] for f in feats]
    d.to_parquet(f"raw/{name}.parquet")
    print(f"wrote raw/{name}.parquet: {len(d):,} points")


if args.snapshot:
    src = arg_path(args.snapshot)
    need(*(os.path.join(src, f) for f in ["retrieval_log.json"] + [f"{n}.geojson" for n in SRC]))
    for f in ["retrieval_log.json"] + [f"{n}.geojson" for n in SRC]:
        shutil.copyfile(os.path.join(src, f), os.path.join("raw", f))
    print(f"copied the snapshot in {src} to raw/")
elif args.convert_only:
    need(*(f"raw/{n}.geojson" for n in SRC))
else:
    log = {}
    for name, url in SRC.items():
        cnt, _ = get(url, {"where": "1=1", "returnCountOnly": "true", "f": "json"})
        n = cnt["count"]; feats = []; off = 0
        while off < n:
            js, q = get(url, {"where": "1=1", "outFields": "*", "outSR": "4326", "orderByFields": "OBJECTID ASC" if name.startswith("twdb") else "objectid ASC",
                              "resultOffset": off, "resultRecordCount": 1000, "f": "geojson"})
            feats += js["features"]; off += 1000
            print(name, len(feats), "/", n, flush=True)
        fc = {"type": "FeatureCollection", "features": feats}
        p = f"raw/{name}.geojson"; open(p, "w").write(json.dumps(fc))
        log[name] = dict(url=url, count_reported=n, count_downloaded=len(feats),
                         retrieved_utc=datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
                         sha256=hashlib.sha256(open(p, "rb").read()).hexdigest(),
                         example_query=q)
    json.dump(log, open("raw/retrieval_log.json", "w"), indent=1)
    print(json.dumps(log, indent=1))
for name in SRC:
    to_table(name)
