"""Shared loaders for steps 14 to 22. Everything here rebuilds the SAME objects that core_numbers.py builds, from the
same work/ files, so every later number is computed from the objects behind the entry's headline.

Imported by the later steps, not run on its own (python v4_common.py --help describes it)."""
import numpy as np, pandas as pd
from common import COMPONENTS, SEED, STRATA, TRACTS, need

TIGER_RUNS = ["work/tiger_check_plus_strict.parquet", "work/tiger_check_plus_strict_multi.parquet"]
CAREFUL_IN = TIGER_RUNS + ["work/groups_b_plus_strict.parquet", "work/bldg_plus_strict.parquet"]
CAREFUL_COLS = {"work/groups_b_plus_strict.parquet": ["nearmiss_20m", "pop_block", "hu_block"]}


def tiger_results():
    """Both TIGER check runs (single-crossing areas >= 10 buildings, multi-crossing areas >= 30), as core_numbers.py."""
    need(*TIGER_RUNS)
    return pd.concat([pd.read_parquet(TIGER_RUNS[0]).assign(mode="single"),
                      pd.read_parquet(TIGER_RUNS[1]).assign(mode="multi")], ignore_index=True)


def careful_set():
    """(G, core, Bc): all plus/strict areas, the careful set (TIGER agrees AND no 20 m near-miss AND >= 1 building),
    and the careful set's buildings. Identical selection to core_numbers.py."""
    need(*CAREFUL_IN, columns=CAREFUL_COLS)
    R = tiger_results(); a = R[R.verdict == "agrees_isolated"]
    G = pd.read_parquet("work/groups_b_plus_strict.parquet")
    core = G[G.comp.isin(set(a.comp)) & ~G.nearmiss_20m & (G.bldg > 0)].copy()
    B = pd.read_parquet("work/bldg_plus_strict.parquet")
    Bc = B[B.comp.isin(core.comp)].copy()
    return G, core, Bc


def wavg(d, c, wt):
    """core_numbers.py's weighted mean: missing values filled with the column median of the same frame."""
    return float(np.average(d[c].fillna(d[c].median()), weights=d[wt]))


def strata(cols=None):
    """Columns of the challenge's strata table (CC BY-SA 4.0), from the shared cache or BIAS_DATA_DIR."""
    need(STRATA)
    return pd.read_parquet(STRATA, columns=cols)


def county_names():
    """County FIPS (5 chars) -> name, from the inventories' own county field (TxGIO first, TWDB where TxGIO has none)."""
    need("work/lwc_all.parquet")
    L = pd.read_parquet("work/lwc_all.parquet", columns=["src", "GEOID", "county_src"])
    L = L[L.GEOID.notna() & L.county_src.notna()]
    tx = L[L.src == "txgio"].groupby(L.GEOID.str[:5]).county_src.agg(lambda s: s.mode().iloc[0])
    tw = L[L.src == "twdb"].groupby(L.GEOID.str[:5]).county_src.agg(lambda s: s.mode().iloc[0])
    return tx.combine_first(tw).to_dict()


def wilson(k, n, z=1.959963984540054):
    if n == 0: return (float("nan"), float("nan"))
    p = k / n; d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d; h = z * np.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (float(c - h), float(c + h))


if __name__ == "__main__":
    import argparse
    argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter).parse_args()
    print(__doc__)
