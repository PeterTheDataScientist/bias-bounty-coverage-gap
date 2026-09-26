"""Step 13. Every number the writeup quotes, computed from the run's own outputs into work/discovery_numbers.json
(and work/variants_table.csv), then, with --template, filled into a draft. Nothing in the text is typed by hand."""
import argparse, json, re, numpy as np, pandas as pd
from common import STRATA, arg_path, need
ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
ap.add_argument("--template", help="a text file with {{NAME}} placeholders to fill with the numbers")
ap.add_argument("--out", help="where to write the filled template (default: next to it, with _filled added)")
args = ap.parse_args()
need("raw/retrieval_log.json", "work/extra_segments.json", "work/lwc_unique_osm.parquet", "work/osm_fordtags.parquet",
     "work/osm_ways_with_fordnodes.parquet", "work/tracts_lwc.parquet", "work/tiger_check_plus_strict.parquet",
     "work/tiger_check_plus_strict_multi.parquet", "work/bldg_plus_strict.parquet", "work/lwc_all.parquet",
     "work/examples_confirmed.csv", STRATA,
     *(f"work/{k}_{n}_{v}.parquet" for k in ("groups_b", "cuts") for n in ("base", "plus") for v in ("all", "strict", "fords")))
N = {}
f = lambda x: f"{int(round(x)):,}"
pc = lambda a, b: f"{100 * a / b:.1f}%"
log = json.load(open("raw/retrieval_log.json")); ex = json.load(open("work/extra_segments.json"))
N["N_TXGIO"] = f(log["txgio_lwc"]["count_downloaded"]); N["N_TWDB"] = f(log["twdb_sfp_lwc"]["count_downloaded"])
N["T_TXGIO"] = log["txgio_lwc"]["retrieved_utc"].replace("T", " ").replace("Z", ""); N["T_TWDB"] = log["twdb_sfp_lwc"]["retrieved_utc"].replace("T", " ").replace("Z", "")
N["T_OVT"] = ex["retrieved_utc"].replace("T", " ").replace("Z", "")
U = pd.read_parquet("work/lwc_unique_osm.parquet")
N["N_UNIQUE"] = f(len(U)); N["N_TXGIO_IN"] = f((U.src == "txgio").sum()); N["N_TWDB_EXTRA"] = f((U.src == "twdb").sum())
N["N_ON_OVT"] = f(U.on_overture_30m.sum()); N["PCT_ON_OVT"] = pc(U.on_overture_30m.sum(), len(U))
hn = U[U.has_name]; N["N_NAMED"] = f(len(hn)); N["N_NAMEOK"] = f(hn.name_verified.sum()); N["PCT_NAMEOK"] = pc(hn.name_verified.sum(), len(hn))
N["MED_D"] = f"{hn.d_named.median():.1f}"
A = U[U.seg_id.notna()]; N["N_ATTR"] = f(len(A))
N["PCT_LOCAL"] = pc(A.seg_cls.isin(["residential", "unclassified", "tertiary"]).sum(), len(A))
fl = A.seg_flags.fillna("")
N["PCT_NOFLAG"] = pc((fl == "").sum(), len(A)); N["PCT_BRIDGE"] = pc(fl.str.contains("is_bridge").sum(), len(A))
for k, t in (("BRIDGECLASS", "BRIDGE CLASS"), ("VENTED", "VENTED FORD"), ("UNVENTED", "UNVENTED FORD")):
    m = A.lwc_type == t; N[f"PCT_BR_{k}"] = pc(fl[m].str.contains("is_bridge").sum(), m.sum())
F = pd.read_parquet("work/osm_fordtags.parquet"); W = pd.read_parquet("work/osm_ways_with_fordnodes.parquet")
N["N_OSM_TAGS"] = f(len(F)); N["N_OSM_30"] = f(U.osm_tag_30m.sum()); N["PCT_OSM_30"] = pc(U.osm_tag_30m.sum(), len(U)); N["PCT_OSM_100"] = pc(U.osm_tag_100m.sum(), len(U))
way = A.seg_osm_way.str.extract(r"^w(\d+)@")[0].astype(float)
fw = way.isin(set(W.way.astype(float))); N["N_FORDWAY"] = f(fw.sum())
N["N_FORDWAY_NOFLAG"] = f((fw & (fl == "")).sum()); N["N_FORDWAY_BRIDGE"] = f((fw & fl.str.contains("is_bridge")).sum())
N["PCT_OSM_PRE"] = pc((pd.to_datetime(F.ts) < pd.Timestamp("2026-08-04T02:00:00Z")).sum(), len(F))
T = U[U.src == "txgio"]
N["PCT_GAUGE"] = pc((T.signage == "GAUGE").sum(), len(T)); N["PCT_ADV"] = pc((T.signage == "ADV_WARN").sum(), len(T)); N["PCT_NOSIGN"] = pc((T.signage == "NONE").sum(), len(T))
S = pd.read_parquet("work/tracts_lwc.parquet")
h = S[S.has]; N["N_TRACTS_LWC"] = f(len(h)); N["PPL_TRACTS_LWC"] = f(h.pop_total.sum())
N["PCT_T0"] = pc((h.loc[h._t_def, "transport_gap"] == 0).sum(), h._t_def.sum()); N["PCT_TDEF"] = pc(h._t_def.sum(), len(h))
g = S.groupby("ur_class").agg(lwc=("n_lwc", "sum"), pop=("pop_total", "sum"))
N["PERCAP_RURAL"] = f"{g.loc['Rural', 'lwc'] / g.loc['Rural', 'pop'] * 1e5:.0f}"; N["PERCAP_URBAN"] = f"{g.loc['Urban', 'lwc'] / g.loc['Urban', 'pop'] * 1e5:.0f}"
N["PERCAP_RATIO"] = f"{(g.loc['Rural', 'lwc'] / g.loc['Rural', 'pop']) / (g.loc['Urban', 'lwc'] / g.loc['Urban', 'pop']):.0f}"
rows = []
for net in ("base", "plus"):
    for var in ("all", "strict", "fords"):
        G = pd.read_parquet(f"work/groups_b_{net}_{var}.parquet"); C = pd.read_parquet(f"work/cuts_{net}_{var}.parquet")
        s1 = G[G.single_crossing]
        rows.append(dict(network=net, crossings=var, cut=len(C), groups=int((G.bldg > 0).sum()), buildings=int(G.bldg.sum()), people=int(round(G.people.sum())),
                         single_groups=int((s1.bldg > 0).sum()), single_buildings=int(s1.bldg.sum()), single_people=int(round(s1.people.sum()))))
V = pd.DataFrame(rows); V.to_csv("work/variants_table.csv", index=False)
lab = {"base": "challenge roads", "plus": "plus service and track roads"}; labv = {"all": "all crossings", "strict": "strict list", "fords": "strict list, fords only"}
N["TABLE_VARIANTS"] = "\n".join(["Roads counted as a way out | crossings closed | crossings | areas | buildings | people | behind one crossing: areas, buildings, people"] +
    [f"{lab[r.network]} | {labv[r.crossings]} | {r.cut:,} | {r.groups:,} | {r.buildings:,} | {r.people:,} | {r.single_groups:,}, {r.single_buildings:,}, {r.single_people:,}" for r in V.itertuples()])
ps = V[(V.network == "plus") & (V.crossings == "strict")].iloc[0]
N["STRANDED_BLDG"] = f(ps.buildings); N["STRANDED_PPL"] = f(round(ps.people, -3)); N["SINGLE_BLDG"] = f(ps.single_buildings)
R = pd.concat([pd.read_parquet("work/tiger_check_plus_strict.parquet"), pd.read_parquet("work/tiger_check_plus_strict_multi.parquet")])
a = R[R.verdict == "agrees_isolated"]
N["N_TIGER_AGREE"] = f(len(a)); N["N_TIGER_CHECKED"] = f(len(R)); N["TIGER_BLDG"] = f(a.bldg.sum()); N["TIGER_PPL"] = f(round(a.people.sum(), -2))
N["TIGER_TRACTS"] = f(a.GEOID.nunique()); 
B = pd.read_parquet("work/bldg_plus_strict.parquet"); Bc = B[B.comp.isin(a.comp)]
N["TIGER_TRACTS"] = f(Bc.GEOID.nunique()); N["TIGER_COUNTIES"] = f(Bc.GEOID.str[:5].nunique())
Gp = pd.read_parquet("work/groups_b_plus_strict.parquet")
if "nearmiss_20m" in Gp:
    m = Gp.nearmiss_20m; ac = set(a.comp)
    N["NEARMISS_TEXT"] = (f"in {int(m.sum()):,} of {int((Gp.bldg > 0).sum()):,} areas a road inside comes within 20 m of a road outside somewhere other than at a crossing, "
                          f"which could be an unmapped short link. They hold {int(Gp.bldg[m].sum()):,} of the {int(Gp.bldg.sum()):,} buildings; "
                          f"{int(Gp[m & Gp.comp.isin(ac)].bldg.sum()):,} of the TIGER-confirmed buildings are among them, and none of the named places below is.")
else:
    N["NEARMISS_TEXT"] = "{{NEARMISS pending}}"
Sx = pd.read_parquet(STRATA)
Sx = Sx[Sx.GEOID.isin(S.GEOID)]
w = lambda d, c, wt: np.average(d[c].fillna(d[c].median()), weights=d[wt])
B2 = B.merge(Sx[["GEOID", "cvi_climate_extreme_events"]], on="GEOID", how="left")
N["PCT_RURAL_STRANDED"] = pc(B.loc[B.ur_class == "Rural", "ppl"].sum(), B.ppl.sum()); N["PCT_RURAL_REGION"] = pc(Sx.loc[Sx.ur_class == "Rural", "pop_total"].sum(), Sx.pop_total.sum())
N["SVI_STRANDED"] = f"{w(B, 'svi_overall', 'ppl'):.2f}"; N["SVI_REGION"] = f"{w(Sx, 'svi_overall', 'pop_total'):.2f}"
N["CVI_EE_STRANDED"] = f"{w(B2, 'cvi_climate_extreme_events', 'ppl'):.2f}"; N["CVI_EE_REGION"] = f"{w(Sx, 'cvi_climate_extreme_events', 'pop_total'):.2f}"
L = pd.read_parquet("work/lwc_all.parquet"); names = L[L.src == "txgio"].assign(c=lambda d: "48" + d.county_src).groupby(L.GEOID.str[:5]).county_src.agg(lambda s: s.mode().iloc[0])
top = Bc.groupby(Bc.GEOID.str[:5]).size().sort_values(ascending=False).head(8)
N["TOP_COUNTIES"] = ", ".join(f"{names.get(k, k)} ({v:,})" for k, v in top.items())
E = pd.read_csv("work/examples_confirmed.csv", dtype={"tract": str})
bx = E[E.tract == "48029141800"]
if len(bx): N["BEXAR_BLDG"] = f(bx.buildings.iloc[0]); N["BEXAR_TGAP"] = str(bx.transport_gap.iloc[0])
G2 = pd.read_parquet("work/groups_b_plus_strict.parquet")[["comp", "nearmiss_20m"]] if "nearmiss_20m" in pd.read_parquet("work/groups_b_plus_strict.parquet").columns else None
EX = E.copy()
if G2 is not None: EX = EX.merge(G2, on="comp", how="left"); EX = EX[~EX.nearmiss_20m.fillna(True)]
pick = ["48029141800", "48187210606", "48209010811", "48265960301", "48113017008", "48251130212", "48025950600"]
EX = EX[EX.tract.isin(pick)].sort_values("buildings", ascending=False).drop_duplicates("tract")
def flagtxt(x): return "a bridge" if "is_bridge" in str(x) else "an ordinary road"
lines = ["County | crossing(s), inventory type and ID | buildings (people, est.) | tract, SVI | scorecard road gap | the map says"]
for r in EX.itertuples():
    lines.append(f"{r.county} | {r.crossings.title()} | {int(r.buildings):,} ({int(round(r.people, -1)):,}) | {r.tract}, {r.tract_svi} | {r.transport_gap} | {flagtxt(r.overture_flags)}")
N["TABLE_EXAMPLES_AUTO"] = "\n".join(lines)
import os
N["RUNTIME_MIN"] = "{{RUNTIME_MIN}}"
json.dump(N, open("work/discovery_numbers.json", "w"), indent=1)
print(json.dumps(N, indent=1))
if args.template:
    src = arg_path(args.template); dst = arg_path(args.out) if args.out else os.path.splitext(src)[0] + "_filled.txt"
    need(src); d = open(src).read()
    for k, v in N.items(): d = d.replace("{{" + k + "}}", str(v))
    open(dst, "w").write(d)
    print("wrote", dst, "unfilled:", sorted(set(re.findall(r"\{\{([A-Z_0-9 a-z]+)\}\}", d))))
