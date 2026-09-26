"""Join columns of the challenge's strata table to the result tables, on your own machine.

The tables in ../results/ hold values derived from Overture and OpenStreetMap (ODbL 1.0), with public-domain and
permissively licensed ones beside them, plus the tract GEOID. They never hold a value from the challenge's strata
table, which the challenge shares under CC BY-SA 4.0: two share-alike licences cannot both govern one file. This
script puts the two side by side from your own download of the challenge data (python fetch_challenge.py), by tract:

    python join_strata.py                         svi_overall, ur_class, pop_total and cvi_climate_extreme_events
    python join_strata.py --columns svi_overall svi_household svi_housing_transport
    python join_strata.py --list                  every column of the strata table

Every CSV in the results folder (and its audit/ folder) with a GEOID or tract column is written again to
work/joined/ with the strata columns added on the right, prefixed "strata_". The joined files mix ODbL and
CC BY-SA 4.0 material: use them for your own analysis, and do not publish them as one table.
"""
import argparse, glob, os
import pandas as pd
import pyarrow.parquet as pq
from common import STRATA, arg_path, need

DEFAULT = ["svi_overall", "ur_class", "pop_total", "cvi_climate_extreme_events"]
ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
ap.add_argument("--columns", nargs="+", default=DEFAULT, help="strata-table columns to add (default: %(default)s)")
ap.add_argument("--list", action="store_true", help="list the strata table's columns and stop")
ap.add_argument("--results", default=os.path.join(os.pardir, "results"), help="folder of result tables (default ../results)")
ap.add_argument("--out", default=os.path.join("work", "joined"), help="output folder (default work/joined)")
args = ap.parse_args()
need(STRATA)
names = pq.ParquetFile(STRATA).schema_arrow.names
if args.list:
    print(f"{len(names)} columns in {os.path.basename(STRATA)}:\n  " + "\n  ".join(names))
    raise SystemExit
bad = [c for c in args.columns if c not in names]
if bad:
    ap.error(f"not in the strata table: {', '.join(bad)} (python join_strata.py --list shows the columns)")
args.columns = [c for c in dict.fromkeys(args.columns) if c != "GEOID"] or ap.error("give at least one column besides GEOID")
RES = arg_path(args.results) if args.results != ap.get_default("results") else args.results
OUT = arg_path(args.out) if args.out != ap.get_default("out") else args.out
S = pd.read_parquet(STRATA, columns=["GEOID"] + args.columns)
S["GEOID"] = S.GEOID.astype(str).str.zfill(11)
S = S.drop_duplicates("GEOID").rename(columns={c: f"strata_{c}" for c in args.columns})
tables = sorted(glob.glob(os.path.join(RES, "*.csv")) + glob.glob(os.path.join(RES, "audit", "*.csv")))
need(*tables) if tables else need(os.path.join(RES, "crossings.csv"))
done = 0
for f in tables:
    head = pd.read_csv(f, nrows=0).columns
    key = "GEOID" if "GEOID" in head else ("tract" if "tract" in head else None)
    if key is None:
        print(f"  skipped {os.path.relpath(f, RES)}: no GEOID or tract column")
        continue
    T = pd.read_csv(f, dtype={key: str}, keep_default_na=False, na_values=[""])
    J = T.merge(S, left_on=key, right_on="GEOID", how="left", suffixes=("", "_strata"))
    if key != "GEOID":
        J = J.drop(columns=["GEOID"])
    dst = os.path.join(OUT, os.path.relpath(f, RES))
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    J.to_csv(dst, index=False)
    matched = int(J[f"strata_{args.columns[0]}"].notna().sum())
    print(f"  {os.path.relpath(f, RES):<28} {len(T):>6,} rows, joined on {key}, {matched:,} with a value -> {dst}")
    done += 1
print(f"wrote {done} joined tables to {OUT}/ (ODbL and CC BY-SA 4.0 material together: for your own use, not for publishing)")
