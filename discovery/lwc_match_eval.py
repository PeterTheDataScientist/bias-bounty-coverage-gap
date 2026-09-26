"""Step 3. Decide which Overture segment carries each official crossing, and what the open map says about it.
Unique crossing set = TxGIO road crossings (pedestrian excluded) + TWDB records not within 50 m of a TxGIO record.
A crossing is 'on an Overture road' if a segment lies within 30 m; 'name-verified' if a segment within 100 m
carries the inventory's road name or route number. Output work/lwc_unique.parquet."""
import argparse, re, numpy as np, pandas as pd
from lwc_names import same_road, unnamed
from common import need
argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter).parse_args()
need("work/lwc_all.parquet", "work/lwc_seg_candidates.parquet")
L = pd.read_parquet("work/lwc_all.parquet"); L = L[L.GEOID.notna()].reset_index(drop=True)
C = pd.read_parquet("work/lwc_seg_candidates.parquet")
# TWDB descriptions often carry the road: "LWC - HACKBERRY RD", "LWC SECONDARY ROAD, UNNAMED STREAM, UNNAMED ROAD"
def twdb_road(desc):
    """Road name inside a TWDB description. Patterns seen: 'LWC - HACKBERRY RD',
    'LWC SECONDARY ROAD, <stream>, COUNTY ROAD 405', 'LWC BRIDGE CLASS , <stream> AT COUNTY ROAD 4757 0.35 MI ...',
    '4300 Marsalis Street @ Dry Branch', '14200 Old Denton Rd. at Alliance Creek'."""
    if not isinstance(desc, str): return None
    d = " ".join(desc.split())
    m = re.match(r"^LWC\s*-\s*(.+)$", d, re.I)
    if m: return m.group(1).strip()
    m = re.match(r"^LWC\s+(?:PRIMARY|SECONDARY)\s+ROAD\s*,\s*[^,]*,\s*(.+)$", d, re.I)
    if m: return m.group(1).strip()
    m = re.match(r"^LWC\s+BRIDGE CLASS\s*,.*?\bAT\s+(.+?)(?:\s+\d+(?:\.\d+)?\s*MI\b.*)?$", d, re.I)
    if m: return m.group(1).strip()
    if d.upper().startswith("LWC") or d.upper() in ("BRIDGE", "CULVERT"): return None
    d = re.split(r"\s+(?:at|@)\s+|@|\s-\s|-\s", d, flags=re.I)[0]
    d = re.sub(r"\(.*?\)", "", re.sub(r"^\d+\s+", "", d)).strip(" .")
    return d or None
L["road_eff"] = np.where(L.src == "txgio", L.road, L.desc.map(twdb_road))
L["unique"] = ((L.src == "txgio") & (L.lwc_type != "PEDESTRIAN CROSSING")) | ((L.src == "twdb") & ~L.dup_of_txgio)
C = C.merge(L[["road_eff"]], left_on="lwc_row", right_index=True)
C["name_ok"] = [same_road(a, b, r) for a, b, r in zip(C.road_eff, C.name, C.refs)]
C = C.sort_values(["lwc_row", "dist_m"])
near = C.groupby("lwc_row").first()
named = C[C.name_ok == True].groupby("lwc_row").first()
L["d_any"] = near.dist_m.reindex(L.index)
L["d_named"] = named.dist_m.reindex(L.index)
L["has_name"] = ~L.road_eff.map(unnamed)
# the segment we attribute the crossing to: name-verified if possible, else nearest within 30 m
pick = named.combine_first(near[near.dist_m <= 30])
for c in ["seg_id", "dist_m", "cls", "name", "refs", "flags", "surface", "osm_way", "seg_len_m"]:
    L["seg_" + c if not c.startswith("seg") else c] = pick[c].reindex(L.index)
L["on_overture_30m"] = L.d_any <= 30
# confidence tiers for the crossing-to-segment attribution
L["tier"] = np.where(L.d_named.notna(), "A_name_verified",
             np.where(~L.has_name & (L.d_any <= 15), "B_unnamed_within_15m",
             np.where(L.seg_id.notna(), "C_unverified", "none")))
L["name_verified"] = L.d_named.notna()
U = L[L.unique].copy()
U.to_parquet("work/lwc_unique.parquet"); L.to_parquet("work/lwc_all_eval.parquet")
print("unique crossings in region:", len(U), " by src:", U.src.value_counts().to_dict())
print("segment within 30 m:", U.on_overture_30m.sum(), f"({U.on_overture_30m.mean():.1%})", " within 60 m:", (U.d_any <= 60).sum(), " within 100 m:", U.d_any.notna().sum())
hn = U[U.has_name]
print("with an inventory road name:", len(hn), " name-verified within 100 m:", hn.name_verified.sum(), f"({hn.name_verified.mean():.1%})",
      " median distance of verified:", round(hn.d_named.median(), 1))
A = U[U.seg_id.notna()]
print("attributed to an Overture segment:", len(A)); print("tiers:", U.tier.value_counts().to_dict())
fl = A.seg_flags.fillna("")
print("flags on attributed segments:", fl.str.split("|").explode().replace("", "(none)").value_counts().to_dict())
print("is_bridge by inventory type:\n", A.assign(br=fl.str.contains("is_bridge")).groupby(A.lwc_type.fillna("TWDB (no type)")).br.agg(["size", "sum", "mean"]))
print("class of attributed segment:", A.seg_cls.value_counts().to_dict())
print("surface:", A.seg_surface.fillna("").replace("", "(not stated)").value_counts().to_dict())
print("osm way present:", A.seg_osm_way.notna().mean())
