"""
The target-free acceptance window (section 9 of the entry). The Data-page SampleSubmission.csv carries one constant
per score column; read as the reference's column means over all 9,379 tracts, rounded to 6 decimals, with an
undefined component counted as 0, each constant bounds its column sum to (mean +/- 0.0000005) x 9,379.
(malekarkan 34703 first compared a reconstruction with the composite constant; Yanard 34908 turned the constants
into intervals; Pricilegangbe 34992 stated them as windows on column sums.)

Run from documentation/, after `python pipeline.py --check` (and, for the second file, the fused multiply-add run
in README.md):

    python tools/acceptance_window.py out/counts.parquet [out_fma/counts.parquet]

Check the four constants below against your copy of SampleSubmission.csv before relying on them.
"""
import argparse, math, os, sys
import numpy as np, pandas as pd
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from pipeline import score, CONV

ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
ap.add_argument("counts", nargs="+", help="per-tract counts written by pipeline.py (out/counts.parquet, out_fma/counts.parquet)")
a = ap.parse_args()
for path in a.counts:
    if not os.path.exists(path):
        sys.exit(f"missing {path}: run  python pipeline.py --check  first (it writes out/counts.parquet); "
                 f"out_fma/counts.parquet comes from the fused multiply-add run in README.md")
N = 9379
SAMPLE = {"transport_gap": 0.111771, "building_gap": 0.005601, "poi_gap": 0.051414, "coverage_gap_score": 0.058436}
for path in a.counts:
    c, t, b, p = score(pd.read_parquet(path), CONV["output_decimals"])     # c is the scored column as written
    print(path)
    for (col, m), v in zip(SAMPLE.items(), (t, b, p, c)):
        lo, hi = (m - 5e-7) * N, (m + 5e-7) * N
        s = math.fsum(np.nan_to_num(np.asarray(v, float), nan=0.0))
        where = "inside" if lo <= s <= hi else (f"above by {s - hi:.4f}" if s > hi else f"below by {lo - s:.4f}")
        print(f"  {col:<20} sum {s:.10f}   window [{lo:.4f}, {hi:.4f}]   {where}")
