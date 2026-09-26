"""Step 20, part 2. Precision of the careful set from the imagery audit.

Input: ../results/audit/audit_verdicts.csv, the first reading's verdict for each of the 40 sampled areas (made
following written rules: ../results/audit/README.md) after looking at every image precision_audit.py
draws (overview, tiles, three nearest-approach close-ups, and extra close-ups where a link was in doubt; the images
each verdict rests on are listed in its `images` column), and the seeded sample
(work/v4_audit_sample.csv, precision_audit.py sample, seed 20260926, 10 areas from each size quartile). The sample
the run draws must equal the one that was read (../results/audit/audit_sample.csv), or this script stops. The
second reading, ../results/audit/second_rater.csv, is compared with this one by audit_agreement.py.
Verdicts
  isolated                 the only mapped or visible ways out cross at the official crossing(s)
  exit_is_a_ford           an unmapped or unlisted way out exists but it crosses a stream at grade (a ford), so it floods too
  exit_visible             a mapped road or a clearly visible track reaches the main network without an official crossing
  cannot_tell              a link is plausible (driveway, yard, two-track, canopy) but can be neither confirmed nor excluded
Precision (share of areas truly cut off when the crossings flood) is reported two ways: 'flood' counts
exit_is_a_ford as cut off, 'strict' does not. Main estimate: among the areas imagery settles (cannot_tell left
out, assumed to behave like the settled areas of the same size quartile), with a Wilson 95% interval; bounds: every
cannot_tell counted as an exit (lower) or as cut off (upper).
Precision-adjusted buildings, residents and homes: stratified by the four size quartiles, sum over quartiles of (quartile
total) x (quartile precision among settled areas); 95% interval from a stratified bootstrap of the audited areas
(10,000 draws, seed 20260926; a draw with no settled area in a quartile uses that draw's pooled precision).
Outputs: work/v4_audit_verdicts.csv (the verdicts rebuilt on this run's sample: must equal the shipped file),
work/v4_audit_summary.json
"""
import argparse, glob, os, sys, json, numpy as np, pandas as pd
from common import AUDIT, need
from v4_common import careful_set, county_names, wilson, SEED
argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter).parse_args()
NB = 10000
VF, SF = os.path.join(AUDIT, "audit_verdicts.csv"), os.path.join(AUDIT, "audit_sample.csv")
need(VF, SF, "work/v4_audit_sample.csv", "work/v4_audit_strata.csv")
V = pd.read_csv(VF, dtype={"GEOID": str, "images": str}).fillna({"images": ""})
S = pd.read_csv("work/v4_audit_sample.csv", dtype={"GEOID": str})
S0 = pd.read_csv(SF, dtype={"GEOID": str})
ID = ["k", "stratum", "comp", "bldg", "n_cross", "single_crossing", "GEOID"]
if not (S[ID].equals(S0[ID]) and np.allclose(S[["pop_block", "hu_block"]], S0[["pop_block", "hu_block"]], rtol=0, atol=1e-6)):
    sys.exit(f"audit_summary.py: the sample this run drew (work/v4_audit_sample.csv) differs from the audited one ({SF}); "
             "the verdicts belong to that sample, so the precision figures would not")
ST = pd.read_csv("work/v4_audit_strata.csv")
assert len(V) == 40 and set(V.comp) == set(S.comp) and (V.set_index("k").comp == S.set_index("k").comp).all()
G, core, Bc = careful_set()
names = county_names()
A = S.merge(V[["k", "verdict", "reason", "images"]], on="k")
A["county"] = A.GEOID.str[:5].map(names)
A = A.rename(columns={"bldg": "buildings", "pop_block": "residents", "hu_block": "homes"})
A[["k", "stratum", "comp", "GEOID", "county", "buildings", "residents", "homes", "n_cross", "single_crossing", "verdict", "reason", "images"]].round(
    {"residents": 1, "homes": 1}).to_csv("work/v4_audit_verdicts.csv", index=False)
R = pd.read_csv("work/v4_audit_verdicts.csv", dtype={"GEOID": str, "images": str}).fillna({"images": ""})
ID = ["k", "stratum", "comp", "GEOID", "county", "buildings", "n_cross", "single_crossing", "verdict", "reason", "images"]
if not (R.columns.equals(V.columns) and R[ID].equals(V[ID]) and (R[["residents", "homes"]] - V[["residents", "homes"]]).abs().max().max() <= 0.1):
    sys.exit(f"audit_summary.py: the verdict table rebuilt on this run (work/v4_audit_verdicts.csv) differs from {VF}")
cited = sorted({f for x in A.images for f in x.split()})
have = [f for f in cited if os.path.exists(os.path.join("figs_audit", f))]
print(f"verdicts: {len(A)} areas; images cited: {len(cited)}, present in figs_audit/: {len(have)}"
      + ("" if len(have) == len(cited) else " (python precision_audit.py prep, render and extras draw them)"))
cnt = A.verdict.value_counts().to_dict()
by = pd.crosstab(A.stratum, A.verdict)
out = dict(sample=dict(areas=40, per_stratum=10, seed=SEED, strata=ST.round(1).to_dict(orient="records")),
           verdict_counts=cnt, verdict_by_stratum=by.to_dict(orient="index"))
iso_flood = A.verdict.isin(["isolated", "exit_is_a_ford"]); iso_strict = A.verdict.eq("isolated"); settled = ~A.verdict.eq("cannot_tell")
def prec(k, n): lo, hi = wilson(int(k), int(n)); return dict(k=int(k), n=int(n), p=round(k / n, 4), wilson95=[round(lo, 4), round(hi, 4)])
out["precision"] = {
    "flood": dict(settled=prec(iso_flood[settled].sum(), settled.sum()), lower_bound=prec(iso_flood.sum(), 40), upper_bound=prec(iso_flood.sum() + (~settled).sum(), 40)),
    "strict": dict(settled=prec(iso_strict[settled].sum(), settled.sum()), lower_bound=prec(iso_strict.sum(), 40), upper_bound=prec(iso_strict.sum() + (~settled).sum(), 40))}
# stratified adjustment
tot = ST.set_index("stratum")[["buildings", "residents", "homes"]]
def adjusted(df, iso):
    """sum over strata of total x precision among settled areas (pooled precision where a stratum has none settled)."""
    s = ~df.verdict.eq("cannot_tell").values; y = iso.values
    pooled = y[s].mean() if s.any() else np.nan
    res = np.zeros(3)
    for h in (1, 2, 3, 4):
        m = (df.stratum.values == h) & s
        p = y[m].mean() if m.any() else pooled
        res += tot.loc[h].values * p
    return res
def bounds(df, iso, u_as):
    y = np.where(df.verdict.eq("cannot_tell"), u_as, iso.values).astype(float)
    return sum(tot.loc[h].values * y[df.stratum.values == h].mean() for h in (1, 2, 3, 4))
rng = np.random.default_rng(SEED)
idx = {h: np.where(A.stratum.values == h)[0] for h in (1, 2, 3, 4)}
draws = [np.concatenate([rng.choice(idx[h], len(idx[h])) for h in (1, 2, 3, 4)]) for _ in range(NB)]
adj = {}
for key, iso in (("flood", iso_flood), ("strict", iso_strict)):
    pt = adjusted(A, iso)
    bs = np.array([adjusted(A.iloc[d].reset_index(drop=True), iso.iloc[d].reset_index(drop=True)) for d in draws])
    lo, hi = np.percentile(bs, [2.5, 97.5], axis=0)
    lb, ub = bounds(A, iso, 0), bounds(A, iso, 1)
    adj[key] = {k: dict(estimate=int(round(pt[i])), ci95=[int(round(lo[i])), int(round(hi[i]))], lower_bound=int(round(lb[i])), upper_bound=int(round(ub[i])))
                for i, k in enumerate(("buildings", "residents", "homes"))}
    adj[key]["precision_by_stratum_settled"] = {int(h): (round(float(iso[(A.stratum == h) & settled].mean()), 4) if ((A.stratum == h) & settled).any() else None) for h in (1, 2, 3, 4)}
out["adjusted"] = adj
# simple (unstratified) version: pooled precision among settled areas x careful-set totals, Wilson interval carried through
tot_all = dict(buildings=float(core.bldg.sum()), residents=float(core.pop_block.sum()), homes=float(core.hu_block.sum()))
out["adjusted_simple"] = {key: {k: dict(estimate=int(round(v * out["precision"][key]["settled"]["p"])),
                                        wilson95=[int(round(v * out["precision"][key]["settled"]["wilson95"][0])), int(round(v * out["precision"][key]["settled"]["wilson95"][1]))])
                                for k, v in tot_all.items()} for key in ("flood", "strict")}
out["careful_set_totals"] = dict(areas=int(len(core)), buildings=int(core.bldg.sum()), residents=int(round(core.pop_block.sum())), homes=int(round(core.hu_block.sum())))
# building-weighted sensitivity (ratio estimator within strata, settled areas only)
def bw(iso):
    r = 0.0
    for h in (1, 2, 3, 4):
        m = (A.stratum == h) & settled
        r += tot.loc[h, "buildings"] * (A.buildings[m & iso].sum() / A.buildings[m].sum())
    return int(round(r))
out["sensitivity_building_weighted_buildings"] = dict(flood=bw(iso_flood), strict=bw(iso_strict),
    note="within each quartile, share of the settled areas' buildings that are cut off; very sensitive to area 979 (1,865 buildings; its only other exit is a ford)")
out["named_examples_in_sample"] = A[A.comp.isin([979, 921, 952, 266, 623, 1030])][["comp", "verdict", "reason"]].to_dict(orient="records")
json.dump(out, open("work/v4_audit_summary.json", "w"), indent=1)
print(json.dumps(out, indent=1))
