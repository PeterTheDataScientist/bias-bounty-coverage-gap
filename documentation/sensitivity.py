"""
Sections 6 and 7 of the writeup, rebuilt from the per-tract counts that
`python pipeline.py --check --extra` saves to out/counts.parquet.

Each variant changes ONE convention of the scored build and recomputes all 9,379 values.
Reported: tracts whose value moves, mean absolute change, largest change. Under a mean absolute
error metric, the mean absolute change is the most a variant can move the score, so a variant whose
mean change exceeds twice the current error would already score worse than the scored file.

    python sensitivity.py --error 0.00000301

With --arith, it adds the arithmetic row from a second run made under tools/build_proj_fma.sh:

    BIAS_OUT=out_fma PYTHONPATH=proj_fma python pipeline.py --check --out submission_fma.csv
    python sensitivity.py --error 0.00000301 --arith out_fma/counts.parquet

tools/scorecard_ratios.py imports this file for the same variants (variants() below).
"""
import argparse, os, sys
import numpy as np, pandas as pd
from pipeline import CONV, CATS, gap, mean_defined, OUTDIR

SRC = os.path.join(OUTDIR, "counts.parquet")
dec = CONV["output_decimals"]


def load(path=SRC):
    """The per-tract counts of a `pipeline.py --check --extra` run."""
    if not os.path.exists(path):
        sys.exit(f"missing {path}: run  python pipeline.py --check --extra  first (it writes the per-tract counts)")
    df = pd.read_parquet(path)
    if not {"ovt_road_mid", "ovt_bldg_int", "ovt_places_within", "cbp_estab_res"} <= set(df.columns):
        sys.exit(f"{path} holds only the scored counts: rerun  python pipeline.py --check --extra  to add the alternatives")
    return df


def build(df, road=("ovt_road", "tig_road"), bldg=("ovt_bldg", "ms_bldg"), places="ovt_places", fac_sfx="",
          cbp="cbp_estab", poi="halves", undefined_fac="skip", divisor="defined", cap=True, decimals=dec,
          round_components=False, frame=None):
    d = df if frame is None else frame
    t = gap(d[road[0]], d[road[1]], cap)
    b = gap(d[bldg[0]], d[bldg[1]], cap)
    per = {k: gap(d[f"ovt_{k}{fac_sfx}"], d[f"ref_{k}"], cap) for k in CATS}
    if undefined_fac == "zero":
        per = {k: np.nan_to_num(v) for k, v in per.items()}
    est = gap(d[places], d[cbp], cap)
    if poi == "halves":   p = mean_defined(mean_defined(*per.values()), est)
    elif poi == "flat4":  p = mean_defined(*per.values(), est)
    elif poi == "no_ems": p = mean_defined(mean_defined(per["fire"], per["school"]), est)
    elif poi == "fire":   p = mean_defined(per["fire"], est)
    if round_components:                                   # components stored at 6 dp, composite averaged from them
        t, b, p = (np.round(v, 6) for v in (t, b, p))
    if divisor == "defined":
        c = mean_defined(t, b, p)
    else:
        c = (np.nan_to_num(t) + np.nan_to_num(b) + np.nan_to_num(p)) / 3.0
    c = np.nan_to_num(c, nan=0.0)
    if cap:
        c = np.clip(c, 0, 1)
    return np.round(c, decimals) if decimals is not None else c


other_bldg = ("ovt_bldg_bbox", "ms_bldg_bbox") if CONV["building_point"] == "centroid" else ("ovt_bldg_cen", "ms_bldg_cen")
other_pred = "within" if CONV["place_predicate"] == "intersects" else "intersects"
VARIANTS = [
    ("roads", "whole segment by midpoint instead of split", dict(road=("ovt_road_mid", "tig_road_mid"))),
    ("roads", "split in lon/lat, then measured in EPSG:5070", dict(road=("ovt_road_ll", "tig_road_ll"))),
    ("roads", "split in lon/lat and measured geodesically", dict(road=("ovt_road_geo", "tig_road_geo"))),
    ("roads", "Overture tertiary added to the highway classes", "tertiary"),
    ("roads", "TIGER ramps (S1630) added to the reference", "ramps"),
    ("buildings", f"{'bbox centre' if other_bldg[0].endswith('bbox') else 'true centroid'} instead of the scored building point", dict(bldg=other_bldg)),
    ("buildings", "every footprint touching the tract (straddlers count twice)", dict(bldg=("ovt_bldg_int", "ms_bldg_int"))),
    ("buildings", "a multipolygon footprint counted once per part", dict(bldg=("ovt_bldg_parts", "ms_bldg_parts"))),
    ("places", f"{other_pred} instead of {CONV['place_predicate']}", dict(places=f"ovt_places_{other_pred}", fac_sfx=f"_{other_pred}")),
    ("places", "places with no primary category left out", dict(places="ovt_places_nonnull")),
    ("weighting", "CBP residential share (cbp_estab_res)", dict(cbp="cbp_estab_res")),
    ("weighting", "POI as a flat mean of four terms", dict(poi="flat4")),
    ("weighting", "undefined facility types counted as a zero gap", dict(undefined_fac="zero")),
    ("weighting", "EMS left out of the facilities half", dict(poi="no_ems")),
    ("weighting", "facilities half as fire stations only", dict(poi="fire")),
    ("weighting", "composite always divided by three", dict(divisor="three")),
    ("weighting", "ratio not capped at 1", dict(cap=False)),
    ("output", "composite averaged from components already rounded to 6 dp", dict(round_components=True)),
    ("output", "full precision instead of 6 decimal places" if dec is not None else "6 decimal places", dict(decimals=None if dec is not None else 6)),
]


def variants(df, arith=None):
    """(group, name, all 9,379 values) for every variant, in table order; arith adds the fused multiply-add row."""
    rows = VARIANTS + ([("arithmetic", "PROJ built with fused multiply-add instead of the pyproj wheel", dict(frame=arith))]
                       if arith is not None else [])
    for group, name, spec in rows:
        if spec == "tertiary":
            v = build(df, road=("_o", "tig_road"), frame=df.assign(_o=df.ovt_road + df.ovt_road_tertiary))
        elif spec == "ramps":
            v = build(df, road=("ovt_road", "_r"), frame=df.assign(_r=df.tig_road + df.tig_road_s1630))
        else:
            v = build(df, **spec)
        yield group, name, v


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--error", type=float, required=True, help="the scored file's public error, for the magnitude test")
    ap.add_argument("--arith", help="counts.parquet from a run under tools/build_proj_fma.sh; adds the fused multiply-add row")
    a = ap.parse_args()
    if a.arith and not os.path.exists(a.arith):
        sys.exit(f"missing {a.arith}: run the FMA build first (see the docstring at the top of this file)")
    df = load()
    alt = None
    if a.arith:                                            # every count from the second run, same conventions
        alt = pd.read_parquet(a.arith)
        assert (alt.GEOID.values == df.GEOID.values).all(), "the two runs must cover the same tracts in the same order"
    base = build(df)
    thr = 2 * a.error
    print(f"baseline: CONV = {CONV}; error {a.error:.3e}; magnitude test rules out mean |change| above {thr:.3e}\n")
    rows = []
    for group, name, v in variants(df, alt):
        d = np.abs(v - base)
        mv = int((d > 1e-12).sum())
        verdict = "identical" if mv == 0 else ("ruled out" if d.mean() > thr else "passes, needs the board")
        rows.append((group, name, mv, d.mean(), d.max(), verdict))
        print(f"{group:<10} {name:<62} {mv:>5} tracts  mean {d.mean():.3e}  max {d.max():.3e}  {verdict}")
    pd.DataFrame(rows, columns=["group", "variant", "tracts_moved", "mean_abs_change", "max_abs_change", "verdict"]).to_csv(
        os.path.join(OUTDIR, "sensitivity.csv"), index=False)
