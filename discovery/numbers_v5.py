"""Step 27. Collect the numbers of steps 24 to 26 (facilities.py, occupancy.py, example_tracts.py) into
work/discovery_numbers_v5.json, from their outputs only."""
import argparse, json, hashlib
from common import need
argparse.ArgumentParser(description=__doc__).parse_args()
need("work/v5_facilities.json", "work/v5_facilities_candidates.csv", "work/v5_occupancy.json", "work/v5_occupancy.txt",
     "work/v5_example_tracts.json", "work/v5_example_tracts.csv", "work/v5_example_tracts.txt", "work/v5_tigerweb_tract_sums.json")
F = json.load(open("work/v5_facilities.json")); O = json.load(open("work/v5_occupancy.json"))
E = json.load(open("work/v5_example_tracts.json"))
sha = lambda p: hashlib.sha256(open(p, "rb").read()).hexdigest()
N = dict(generated_by="numbers_v5.py", date="2026-09-26",
         facilities=dict(summary=F["summary"], method=F["method"], check_against_careful_buildings=F["check_against_careful_buildings"],
                         facility_points=F["facility_points"], candidates_within_300m_of_a_cut_off_piece=F["candidates_within_300m_of_a_cut_off_piece"],
                         counts_by_where=F["counts_by_where"],
                         inside_careful=[{k: r[k] for k in ("source", "kind", "name", "address", "area", "county", "tract", "area_buildings",
                                                            "area_single_crossing", "area_crossings")} for r in F["inside_careful"]],
                         ties=F["ties"]),
         occupancy=dict(block_layer_has_vacancy_fields=O["block_layer_has_vacancy_fields"], block_source=O["block_source"],
                        examples=O["examples"], careful_set=O["careful_set"], lead_version=O["lead_version"],
                        careful_areas_homes_at_least_residents=O["careful_areas_homes_at_least_residents"], region=O["region"],
                        region_rural_tracts=O["region_rural_tracts"], texas_all_blocks=O["texas_all_blocks"],
                        tigerweb_sums_retrieved_utc=O["tigerweb_sums_retrieved_utc"]),
         example_tracts=E,
         files={p: sha(p)[:16] for p in ("work/v5_facilities_candidates.csv", "work/v5_facilities.json", "work/v5_occupancy.json",
                                         "work/v5_occupancy.txt", "work/v5_example_tracts.csv", "work/v5_example_tracts.txt",
                                         "work/v5_example_tracts.json", "work/v5_tigerweb_tract_sums.json")})
json.dump(N, open("work/discovery_numbers_v5.json", "w"), indent=1)
print("wrote work/discovery_numbers_v5.json; keys:", list(N))
print(json.dumps(N["facilities"]["summary"]), json.dumps(N["files"], indent=1))
