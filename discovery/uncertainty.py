"""Step 16. Intervals and tests for the entry's 'who lives there' contrasts.

(a) Seeded bootstrap (seed 20260926, 10,000 draws) of the resident-weighted CDC SVI and CVI extreme-events values of
    the careful set, resampling whole AREAS (216) and, separately, whole TRACTS (162). The region values are a census
    of all 6,010 tracts in the strata table, so they are fixed. Point estimates are rebuilt exactly as core_numbers.py
    builds them (weights = the building's share of its tract population, 'ppl'; missing values filled with the median).
    Also: the same contrasts within rural and within urban tracts, because the careful set is 69% rural and the
    region 14% rural.
(b) Rural v urban official crossings per 100,000 residents over the 6,003 scored tracts (work/tracts_lwc.parquet, the
    object disc_numbers.py uses): counts, an exact conditional (Clopper-Pearson) Poisson rate-ratio interval, a
    tract-level cluster bootstrap interval, and a tract-level permutation test of the urban/rural label (seeded).
Output: work/v4_uncertainty.json
"""
import argparse, json, numpy as np, pandas as pd
from scipy.stats import beta
from common import need
from v4_common import careful_set, wavg, strata, SEED
argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter).parse_args()
need("work/tracts_lwc.parquet")
NB = 10000
out = {}
G, core, Bc = careful_set()
Sx = strata(["GEOID", "pop_total", "ur_class", "svi_overall", "cvi_climate_extreme_events"])
B = Bc.merge(Sx[["GEOID", "cvi_climate_extreme_events"]], on="GEOID", how="left")
# point estimates, exactly as core_numbers.py
pt = dict(svi_core=wavg(Bc, "svi_overall", "ppl"), svi_region=wavg(Sx, "svi_overall", "pop_total"),
          cvi_ee_core=wavg(B, "cvi_climate_extreme_events", "ppl"), cvi_ee_region=wavg(Sx, "cvi_climate_extreme_events", "pop_total"))
B["svi_f"] = B.svi_overall.fillna(B.svi_overall.median()); B["cvi_f"] = B.cvi_climate_extreme_events.fillna(B.cvi_climate_extreme_events.median())
B["w_svi"] = B.ppl * B.svi_f; B["w_cvi"] = B.ppl * B.cvi_f
out["n_missing_filled"] = dict(svi=int(B.svi_overall.isna().sum()), cvi_ee=int(B.cvi_climate_extreme_events.isna().sum()))

def boot(df, unit, cols, rng):
    """Ratio-of-sums bootstrap: resample whole units with replacement; returns (point, draws) per column."""
    agg = df.groupby(unit)[["ppl"] + [f"w_{c}" for c in cols]].sum()
    W = agg.ppl.values; n = len(agg)
    draws = {c: np.empty(NB) for c in cols}
    for b in range(NB):
        k = np.bincount(rng.integers(0, n, n), minlength=n)
        den = k @ W
        for c in cols: draws[c][b] = (k @ agg[f"w_{c}"].values) / den
    return {c: (float(agg[f"w_{c}"].sum() / W.sum()), draws[c]) for c in cols}, n

def summ(p, d, ref):
    lo, hi = np.percentile(d, [2.5, 97.5])
    return dict(core=round(p, 4), core_ci95=[round(float(lo), 4), round(float(hi), 4)], region=round(ref, 4),
                diff=round(p - ref, 4), diff_ci95=[round(float(lo - ref), 4), round(float(hi - ref), 4)],
                share_draws_core_above_region=round(float((d > ref).mean()), 4))

for unit in ("comp", "GEOID"):
    rng = np.random.default_rng(SEED)
    res, n = boot(B, unit, ["svi", "cvi"], rng)
    assert abs(res["svi"][0] - pt["svi_core"]) < 1e-12 and abs(res["cvi"][0] - pt["cvi_ee_core"]) < 1e-12
    out[f"bootstrap_by_{'area' if unit == 'comp' else 'tract'}"] = dict(
        units=n, draws=NB, seed=SEED, svi=summ(res["svi"][0], res["svi"][1], pt["svi_region"]),
        cvi_extreme_events=summ(res["cvi"][0], res["cvi"][1], pt["cvi_ee_region"]))

# within rural and within urban tracts (the careful set is mostly rural; the region mostly urban)
Sxr = Sx.copy(); Sxr["svi_f"] = Sxr.svi_overall.fillna(Sxr.svi_overall.median()); Sxr["cvi_f"] = Sxr.cvi_climate_extreme_events.fillna(Sxr.cvi_climate_extreme_events.median())
strat = {}
for cls in ("Rural", "Urban"):
    s = Sxr[Sxr.ur_class == cls]; ref_s = float(np.average(s.svi_f, weights=s.pop_total)); ref_c = float(np.average(s.cvi_f, weights=s.pop_total))
    b = B[B.ur_class == cls]
    rng = np.random.default_rng(SEED)
    res, n = boot(b, "comp", ["svi", "cvi"], rng)
    strat[cls] = dict(areas_with_buildings_here=n, buildings=int(len(b)), residents_ppl=round(float(b.ppl.sum()), 1),
                      svi=summ(res["svi"][0], res["svi"][1], ref_s), cvi_extreme_events=summ(res["cvi"][0], res["cvi"][1], ref_c))
# region values re-weighted to the careful set's rural/urban mix of residents (direct standardisation)
known = B[B.ur_class.isin(["Rural", "Urban"])]
pr = float(known.loc[known.ur_class == "Rural", "ppl"].sum() / known.ppl.sum())
std = {k: round(pr * strat["Rural"][k]["region"] + (1 - pr) * strat["Urban"][k]["region"], 4) for k in ("svi", "cvi_extreme_events")}
out["within_rural_urban"] = dict(rural_share_of_careful_residents=round(pr, 4), by_class=strat,
                                 region_reweighted_to_careful_mix=std,
                                 note="region values are resident-weighted over the strata table's tracts of that class, medians filled over the whole table")
out["point_estimates_core_numbers"] = {k: round(v, 4) for k, v in pt.items()}

# (b) rural v urban crossings per 100,000 residents
S = pd.read_parquet("work/tracts_lwc.parquet", columns=["GEOID", "ur_class", "pop_total", "n_lwc"])
k = S[S.ur_class.isin(["Rural", "Urban"])].reset_index(drop=True)
xr, Tr = float(k.loc[k.ur_class == "Rural", "n_lwc"].sum()), float(k.loc[k.ur_class == "Rural", "pop_total"].sum())
xu, Tu = float(k.loc[k.ur_class == "Urban", "n_lwc"].sum()), float(k.loc[k.ur_class == "Urban", "pop_total"].sum())
rr = (xr / Tr) / (xu / Tu); n = xr + xu
pl, pu = beta.ppf(0.025, xr, n - xr + 1), beta.ppf(0.975, xr + 1, n - xr)
rr_ci = [pl / (1 - pl) * Tu / Tr, pu / (1 - pu) * Tu / Tr]
rng = np.random.default_rng(SEED)
lab = (k.ur_class == "Rural").values; c = k.n_lwc.values.astype(float); p = k.pop_total.values.astype(float)
def ratio(m): return (c[m].sum() / p[m].sum()) / (c[~m].sum() / p[~m].sum())
perm = np.array([ratio(rng.permutation(lab)) for _ in range(NB)])
rng = np.random.default_rng(SEED)
ir, iu = np.where(lab)[0], np.where(~lab)[0]
bs = []
for _ in range(NB):
    a = rng.choice(ir, len(ir)); b = rng.choice(iu, len(iu))
    bs.append((c[a].sum() / p[a].sum()) / (c[b].sum() / p[b].sum()))
bs = np.array(bs)
out["rural_urban_rate"] = dict(
    tracts=dict(rural=int(lab.sum()), urban=int((~lab).sum()), excluded_no_class=int(len(S) - len(k)), crossings_in_excluded=int(S.n_lwc.sum() - n)),
    crossings=dict(rural=int(xr), urban=int(xu)), residents=dict(rural=int(Tr), urban=int(Tu)),
    per_100k=dict(rural=round(xr / Tr * 1e5, 2), urban=round(xu / Tu * 1e5, 2)), rate_ratio=round(rr, 3),
    exact_poisson_ci95=[round(float(x), 3) for x in rr_ci],
    cluster_bootstrap_ci95=[round(float(x), 3) for x in np.percentile(bs, [2.5, 97.5])],
    permutation=dict(draws=NB, seed=SEED, statistic="rate ratio, rural/urban labels shuffled across tracts",
                     max_permuted=round(float(perm.max()), 3), p_one_sided=float((1 + (perm >= rr).sum()) / (1 + NB))))
json.dump(out, open("work/v4_uncertainty.json", "w"), indent=1)
print(json.dumps(out, indent=1))
