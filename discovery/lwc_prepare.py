"""Step 1. Build one table of official low-water crossings (LWC) from the two statewide Texas inventories,
place each in a 2020 census tract of the challenge's south-central-tx region, and flag near-duplicates
between the two inventories (same crossing listed by both, within 50 m).

Inputs: raw/txgio_lwc.parquet, raw/twdb_sfp_lwc.parquet (fetch_lwc.py), challenge tract polygons.
Output: work/lwc_all.parquet (one row per inventory record) with GEOID, x/y in EPSG:3083 metres.
"""
import argparse
import numpy as np, pandas as pd, geopandas as gpd, shapely
from shapely import STRtree
from common import TRACTS as R, need
argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter).parse_args()
need("raw/txgio_lwc.parquet", "raw/twdb_sfp_lwc.parquet", R)
CRS_M = "EPSG:3083"   # NAD83 / Texas Centric Albers Equal Area, metres

tx = pd.read_parquet("raw/txgio_lwc.parquet")
tx = pd.DataFrame(dict(src="txgio", src_id=tx.objectid.astype(str), lon=tx._lon, lat=tx._lat,
                       road=tx.road.str.strip(), stream=tx.flowsource.str.strip(), lwc_type=tx.lwx_type.str.strip(),
                       owner=tx.owner.str.strip(), origin=tx.source.str.strip(), signage=tx.signage.str.strip(),
                       county_src=tx.county.str.strip().str.title(), flood_freq=None, svi_src=np.nan,
                       exp_type=None, desc=tx.location_1.str.strip()))
tw = pd.read_parquet("raw/twdb_sfp_lwc.parquet")
tw = pd.DataFrame(dict(src="twdb", src_id=tw.EXEXPALLID.astype(str), lon=tw._lon, lat=tw._lat,
                       road=None, stream=None, lwc_type=None, owner=None, origin=tw.RFPG_NAME, signage=None,
                       county_src=tw.COUNTY.str.strip().str.title(), flood_freq=tw.FLOOD_FREQ,
                       svi_src=tw.SVI, exp_type=tw.EXP_TYPE, desc=tw.EXP_DESC))
d = pd.concat([tx, tw], ignore_index=True)
g = gpd.GeoDataFrame(d, geometry=gpd.points_from_xy(d.lon, d.lat), crs="EPSG:4326")

tr = pd.read_parquet(R)
tr = gpd.GeoDataFrame(tr[["GEOID", "COUNTYFP", "pop_total", "pct_urban", "ur_class"]],
                      geometry=shapely.from_wkb(tr.geometry), crs="EPSG:4326")
j = gpd.sjoin(g, tr, how="left", predicate="within").drop(columns="index_right")
j = j[~j.index.duplicated()]
print("records", len(j), "in region tracts", j.GEOID.notna().sum(), "by source:\n", j.groupby("src").GEOID.apply(lambda s: s.notna().sum()))

m = j.to_crs(CRS_M)
j["x"] = m.geometry.x.values; j["y"] = m.geometry.y.values
# cross-inventory duplicates: a TWDB record within 50 m of a TxGIO record is the same crossing
a = j[j.src == "txgio"]; b = j[j.src == "twdb"]
tree = STRtree(shapely.points(a.x.values, a.y.values))
pi, ti = tree.query(shapely.points(b.x.values, b.y.values), predicate="dwithin", distance=50)
j["dup_of_txgio"] = False
j.loc[b.index[np.unique(pi)], "dup_of_txgio"] = True
print("TWDB records within 50 m of a TxGIO record:", j.dup_of_txgio.sum(), "of", len(b))
j = pd.DataFrame(j.drop(columns="geometry"))
j.to_parquet("work/lwc_all.parquet")
inr = j[j.GEOID.notna()]
print("in region: txgio", (inr.src == "txgio").sum(), "(pedestrian", ((inr.src == "txgio") & (inr.lwc_type == "PEDESTRIAN CROSSING")).sum(), ")",
      "twdb", (inr.src == "twdb").sum(), "twdb not dup", ((inr.src == "twdb") & ~inr.dup_of_txgio).sum())
print("tracts with >=1 crossing:", inr.GEOID.nunique())
