"""Step 11. Small lookup tables for the figures: which Overture segments are stranded in which group, per variant."""
import argparse, sys, numpy as np, pyarrow.parquet as pq, pyarrow as pa, pyarrow.compute as pc
from common import need
ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
ap.add_argument("network", choices=["base", "plus"]); ap.add_argument("variant", choices=["all", "strict", "fords"])
args = ap.parse_args(); NET, VAR = args.network, args.variant
need(f"work/edges_{NET}_{VAR}.parquet", f"work/graph_base_{NET}.parquet")
e = pq.read_table(f"work/edges_{NET}_{VAR}.parquet")
su = e.column("su").to_numpy(); sv = e.column("sv").to_numpy(); cu = e.column("cu").to_numpy(); cut = e.column("cut").to_numpy()
idx = np.where(su & sv & ~cut)[0]
seg = pq.read_table(f"work/graph_base_{NET}.parquet", columns=["seg_id"]).column("seg_id")
t = pa.table({"comp": cu[idx], "seg_id": pc.take(seg, pa.array(idx))})
pq.write_table(t, f"work/stranded_segs_{NET}_{VAR}.parquet")
print(t.num_rows)
