"""Step 0a. The two per-tract tables the discovery takes from the scorecard side, rebuilt from the per-tract counts
that `python pipeline.py --check --extra` writes (documentation/out/counts.parquet):

  work/bias_components.parquet  transport, building and POI gaps and the composite for all 9,379 scored tracts,
                                with _t_def, _b_def and _p_def marking which components are defined
  work/tract_ms_bldg.parquet    Microsoft footprints per tract, the denominator of people per footprint

The entry's run read these tables from an earlier build of my scored column (13 Sep 2026): building point at the
centre of the footprint's bbox, places counted with within, full precision, undefined components stored as 0.
This script rebuilds exactly those values from the --extra counts, so every number in the entry reproduces. The
road component, the only scorecard value the entry quotes, is identical to the final scored column's in every
tract; the composite differs from the final scored column by at most 0.0014 (45 tracts by more than 0.000001)."""
import argparse, warnings
import numpy as np, pandas as pd
from common import COUNTS, COMPONENTS, TRACT_BUILDINGS, need

argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter).parse_args()
USE = ["GEOID", "region", "ovt_road", "tig_road", "ovt_bldg_bbox", "ms_bldg_bbox", "ovt_fire_within", "ovt_ems_within",
       "ovt_school_within", "ovt_places_within", "ref_fire", "ref_ems", "ref_school", "cbp_estab"]
need(COUNTS, columns={COUNTS: USE})
warnings.filterwarnings("ignore", category=RuntimeWarning)          # nanmean of an all-undefined column
c = pd.read_parquet(COUNTS, columns=USE)


def gap(overture, reference):
    """1 - min(1, overture/reference); NaN where the reference is zero (the component is undefined)."""
    o, r = np.asarray(overture, float), np.asarray(reference, float)
    out = np.full(len(r), np.nan)
    ok = r > 0
    out[ok] = 1.0 - np.minimum(1.0, o[ok] / r[ok])
    return out


t = gap(c.ovt_road, c.tig_road)
b = gap(c.ovt_bldg_bbox, c.ms_bldg_bbox)
facilities = np.nanmean(np.vstack([gap(c[f"ovt_{k}_within"], c[f"ref_{k}"]) for k in ("fire", "ems", "school")]), axis=0)
p = np.nanmean(np.vstack([facilities, gap(c.ovt_places_within, c.cbp_estab)]), axis=0)
comp = np.nanmean(np.vstack([t, b, p]), axis=0)
K = pd.DataFrame({"GEOID": c.GEOID, "transport_gap": np.nan_to_num(t), "building_gap": np.nan_to_num(b),
                  "poi_gap": np.nan_to_num(p), "coverage_gap_score": np.nan_to_num(comp)})
K["_t_def"] = ~np.isnan(t); K["_b_def"] = ~np.isnan(b); K["_p_def"] = ~np.isnan(p); K["region"] = c.region.values
K.to_parquet(COMPONENTS, index=False)
pd.DataFrame({"GEOID": c.GEOID, "ms_bldg": c.ms_bldg_bbox}).to_parquet(TRACT_BUILDINGS, index=False)
print(f"wrote {COMPONENTS} and {TRACT_BUILDINGS}: {len(K):,} tracts, road component defined in {int(K._t_def.sum()):,}")
