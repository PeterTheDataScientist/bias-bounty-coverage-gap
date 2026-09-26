"""Step 20, part 3. The imagery audit read twice: how far the two readings agree, what share of the areas each finds cut
off, and how many of the careful set's buildings that implies.

Inputs: the two readings of the 40 sampled areas, shipped in ../results/audit/: audit_verdicts.csv (the first reading)
and second_rater.csv (the second, saved before the first reading's file was opened); and work/v4_audit_strata.csv
(precision_audit.py sample: the careful set's areas, buildings, residents and homes in each size quartile). Both
readings were made independently from the same renders, following written rules (../results/audit/README.md); no
script makes the verdicts, this one only counts them. Labels, first reading = second reading: isolated = ISOLATED,
exit_is_a_ford = EXIT_FORD, exit_visible = EXIT_UNMAPPED, cannot_tell = UNSETTLED.

  agreement           all four classes over the 40 areas, and cut off (isolated or ford) against a dry exit over the areas
                      both readings settle, each with Cohen's kappa
  precision           per reading, the share of the areas it settles that are cut off (isolated, or every other way out a
                      ford), with a Wilson 95% interval; and the same over the areas both settle and agree on
  building_weighted   per reading, the careful set's buildings, residents and homes behind no dry way out: the sum over the
                      four size quartiles of the quartile's total times that quartile's precision among settled areas (the
                      pooled precision where a quartile has none settled), as audit_summary.py computes it for the first
                      reading

Output: work/v4_audit_agreement.json. No randomness."""
import argparse, json, os
import numpy as np, pandas as pd
from common import AUDIT, need
from v4_common import wilson

argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter).parse_args()
R1F, R2F = os.path.join(AUDIT, "audit_verdicts.csv"), os.path.join(AUDIT, "second_rater.csv")
need(R1F, R2F, "work/v4_audit_strata.csv")
MAP = {"isolated": "ISOLATED", "exit_is_a_ford": "EXIT_FORD", "exit_visible": "EXIT_UNMAPPED", "cannot_tell": "UNSETTLED"}
C = ["ISOLATED", "EXIT_FORD", "EXIT_UNMAPPED", "UNSETTLED"]
CUT = {"ISOLATED", "EXIT_FORD"}

R1 = pd.read_csv(R1F)
R2 = pd.read_csv(R2F).rename(columns={"area_id": "comp", "verdict": "v2"})
assert set(R1.verdict) <= set(MAP) and set(R2.v2) <= set(C), "unknown verdict label"
D = R1.assign(v1=R1.verdict.map(MAP))[["k", "stratum", "comp", "v1"]].merge(R2[["comp", "v2"]], on="comp", how="outer", validate="1:1")
D = D.sort_values("k").reset_index(drop=True)
assert len(D) == 40 and D.v1.notna().all() and D.v2.notna().all(), "the two readings must cover the same 40 areas"


def kappa(a, b, cats):
    a, b = np.asarray(a), np.asarray(b)
    po = float(np.mean(a == b)); pe = float(sum(np.mean(a == c) * np.mean(b == c) for c in cats))
    return dict(agree=int((a == b).sum()), n=int(len(a)), share=round(po, 4), chance=round(pe, 4), kappa=round((po - pe) / (1 - pe), 4))


def prec(k, n):
    lo, hi = wilson(int(k), int(n))
    return dict(k=int(k), n=int(n), p=round(k / n, 4), wilson95=[round(lo, 4), round(hi, 4)])


ST = pd.read_csv("work/v4_audit_strata.csv").set_index("stratum")[["buildings", "residents", "homes"]]


def weighted(v):
    """sum over quartiles of the quartile's totals x its precision among settled areas (audit_summary.py's rule)"""
    settled = (v != "UNSETTLED").values; cut = v.isin(CUT).values
    pooled = cut[settled].mean()
    res = np.zeros(3)
    for h in (1, 2, 3, 4):
        m = (D.stratum.values == h) & settled
        res += ST.loc[h].values * (cut[m].mean() if m.any() else pooled)
    return dict(zip(("buildings", "residents", "homes"), (int(round(x)) for x in res)))


both = D[(D.v1 != "UNSETTLED") & (D.v2 != "UNSETTLED")]
b1, b2 = both.v1.isin(CUT), both.v2.isin(CUT)
agree = both[b1 == b2]
total = {k: int(round(float(ST[k].sum()))) for k in ("buildings", "residents", "homes")}
out = dict(
    labels=MAP,
    areas=len(D), settled=dict(reading_1=int((D.v1 != "UNSETTLED").sum()), reading_2=int((D.v2 != "UNSETTLED").sum()), both=len(both)),
    agreement=dict(four_classes=kappa(D.v1, D.v2, C),
                   cut_off_or_dry_exit_where_both_settle=kappa(np.where(b1, "cut_off", "dry_exit"), np.where(b2, "cut_off", "dry_exit"), ["cut_off", "dry_exit"])),
    confusion_four_classes_rows_reading_1={str(i): {str(j): int(v) for j, v in row.items()} for i, row in
                                           pd.crosstab(pd.Categorical(D.v1, C), pd.Categorical(D.v2, C), dropna=False).iterrows()},
    disagreements=[dict(k=int(r.k), area=int(r.comp), reading_1=r.v1, reading_2=r.v2) for r in D[D.v1 != D.v2].itertuples()],
    precision=dict(reading_1=prec(D.v1.isin(CUT)[D.v1 != "UNSETTLED"].sum(), (D.v1 != "UNSETTLED").sum()),
                   reading_2=prec(D.v2.isin(CUT)[D.v2 != "UNSETTLED"].sum(), (D.v2 != "UNSETTLED").sum()),
                   both_settled_and_agreeing=prec(agree.v1.isin(CUT).sum(), len(agree))),
    careful_set_totals=total,
    building_weighted=dict(reading_1=weighted(D.v1), reading_2=weighted(D.v2)))
for r in ("reading_1", "reading_2"):
    out["building_weighted"][r]["share_of_buildings"] = round(out["building_weighted"][r]["buildings"] / total["buildings"], 4)
with open("work/v4_audit_agreement.json", "w") as f:
    json.dump(out, f, indent=1)

a4, a2, p = out["agreement"]["four_classes"], out["agreement"]["cut_off_or_dry_exit_where_both_settle"], out["precision"]
w = out["building_weighted"]
print(f"two readings of {len(D)} areas: same verdict in {a4['agree']} (kappa {a4['kappa']:.3f}); both settle {a2['n']}, "
      f"agree on {a2['agree']} of them (kappa {a2['kappa']:.3f})")
print("cut off among the areas each settles: " + "; ".join(
    f"reading {i} {p[r]['k']} of {p[r]['n']} ({p[r]['p']:.1%}, Wilson {p[r]['wilson95'][0]:.1%} to {p[r]['wilson95'][1]:.1%})"
    for i, r in ((1, "reading_1"), (2, "reading_2"))))
print(f"building-weighted: reading 1 {w['reading_1']['buildings']:,}, reading 2 {w['reading_2']['buildings']:,} of "
      f"{total['buildings']:,} buildings; wrote work/v4_audit_agreement.json")
