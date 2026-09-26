"""Step 18. Who is behind the crossings, from the challenge's strata table only.

1. Searches the strata table's column names for vehicle access, age 65+, disability, mobile homes and limited English
   (CDC SVI variables such as EP_NOVEH, EP_AGE65, EP_DISABL, EP_MOBILE, EP_LIMENG). None exist: the table carries the
   SVI overall rank and its four theme ranks only. The two themes that contain those variables are used instead:
   svi_household (theme 2: age 65+, age 17 and under, disability, single-parent households, limited English) and
   svi_housing_transport (theme 4: multi-unit structures, mobile homes, crowding, no vehicle, group quarters).
2. Resident-weighted means for the careful set's buildings (weights 'ppl', missing filled with the median, exactly as
   core_numbers.py) against all 6,010 tracts (weights pop_total), for the SVI themes and the CVI components, with seeded
   (20260926) bootstrap intervals resampling areas and, separately, tracts (10,000 draws); plus the same inside rural tracts.
Output: work/v4_who.json
"""
import argparse, json, re, numpy as np, pandas as pd
import pyarrow.parquet as pq
from common import need
from v4_common import careful_set, strata, SEED, STRATA
argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter).parse_args()
need(STRATA)
NB = 10000
names = pq.ParquetFile(STRATA).schema_arrow.names
pat = re.compile(r"veh|age_?6|65|elder|senior|disab|mobile|manuf|trailer|english|limeng|language|^ep_|^e_|^rpl|poverty|insur|crowd", re.I)
out = dict(strata_columns=len(names), columns_matching_search=[c for c in names if pat.search(c)],
           svi_columns=[c for c in names if c.startswith("svi_")], cvi_columns=[c for c in names if c.startswith("cvi_")],
           requested_variables_present={k: (k in names) for k in ("EP_NOVEH", "EP_AGE65", "EP_DISABL", "EP_MOBILE", "EP_LIMENG", "E_NOVEH", "E_AGE65")})
COLS = ["svi_overall", "svi_socioeconomic", "svi_household", "svi_minority", "svi_housing_transport",
        "cvi_overall", "cvi_baseline", "cvi_climate", "cvi_baseline_health", "cvi_baseline_socioeconomic", "cvi_baseline_infrastructure",
        "cvi_baseline_environment", "cvi_climate_health", "cvi_climate_socioeconomic", "cvi_climate_extreme_events"]
G, core, Bc = careful_set()
Sx = strata(["GEOID", "pop_total", "ur_class"] + COLS)
B = Bc[["comp", "GEOID", "ppl", "ur_class"]].merge(Sx[["GEOID"] + COLS], on="GEOID", how="left")
res = {}
for unit in ("comp", "GEOID"):
    rng = np.random.default_rng(SEED)
    idx_draws = None
    for c in COLS:
        f = B[c].fillna(B[c].median()); ref = float(np.average(Sx[c].fillna(Sx[c].median()), weights=Sx.pop_total))
        agg = pd.DataFrame(dict(u=B[unit], w=B.ppl, wx=B.ppl * f)).groupby("u")[["w", "wx"]].sum()
        n = len(agg)
        if idx_draws is None: idx_draws = [np.bincount(rng.integers(0, n, n), minlength=n) for _ in range(NB)]
        W, X = agg.w.values, agg.wx.values
        d = np.array([(k @ X) / (k @ W) for k in idx_draws]); p = float(X.sum() / W.sum())
        lo, hi = np.percentile(d, [2.5, 97.5])
        r = res.setdefault(c, dict(region=round(ref, 4), careful=round(p, 4), diff=round(p - ref, 4), missing_filled=int(B[c].isna().sum())))
        r[f"careful_ci95_by_{'area' if unit == 'comp' else 'tract'}"] = [round(float(lo), 4), round(float(hi), 4)]
        r[f"diff_ci95_by_{'area' if unit == 'comp' else 'tract'}"] = [round(float(lo - ref), 4), round(float(hi - ref), 4)]
for c, r in res.items():
    lo, hi = r["diff_ci95_by_tract"]; lo2, hi2 = r["diff_ci95_by_area"]
    r["verdict"] = ("higher" if min(lo, lo2) > 0 else "lower" if max(hi, hi2) < 0 else "no clear difference")
# inside rural tracts only (the careful set is 69% rural by residents)
rur = {}
Br = B[B.ur_class == "Rural"]; Sr = Sx[Sx.ur_class == "Rural"]
rng = np.random.default_rng(SEED); draws = None
for c in COLS:
    f = Br[c].fillna(B[c].median()); ref = float(np.average(Sr[c].fillna(Sx[c].median()), weights=Sr.pop_total))
    agg = pd.DataFrame(dict(u=Br.comp, w=Br.ppl, wx=Br.ppl * f)).groupby("u")[["w", "wx"]].sum(); n = len(agg)
    if draws is None: draws = [np.bincount(rng.integers(0, n, n), minlength=n) for _ in range(NB)]
    d = np.array([(k @ agg.wx.values) / (k @ agg.w.values) for k in draws]); p = float(agg.wx.sum() / agg.w.sum())
    lo, hi = np.percentile(d, [2.5, 97.5])
    rur[c] = dict(rural_region=round(ref, 4), careful_rural=round(p, 4), diff=round(p - ref, 4), diff_ci95_by_area=[round(float(lo - ref), 4), round(float(hi - ref), 4)],
                  verdict="higher" if lo > ref else ("lower" if hi < ref else "no clear difference"))
out["resident_weighted"] = res; out["inside_rural_tracts"] = rur
out["notes"] = ("SVI values are 2022 national percentile ranks (svi_rank_universe = 'us'); CVI values are the U.S. climate vulnerability index "
                "scores as carried in the strata table. Weights: careful-set buildings weighted by their share of tract population ('ppl'); "
                "region = all 6,010 tracts weighted by pop_total. Verdict 'higher'/'lower' only where both the area and the tract bootstrap "
                "intervals of the difference exclude zero.")
json.dump(out, open("work/v4_who.json", "w"), indent=1)
print(json.dumps(out, indent=1))
