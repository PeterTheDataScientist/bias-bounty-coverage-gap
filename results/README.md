# Result tables of the low-water-crossing discovery

`discovery/export_results.py` writes these files from the run's own outputs, so a rerun can be compared with them
file for file (`python export_results.py --out DIR`); `discovery/ncei_events.py` writes `ncei/` the same way
(`python ncei_events.py --results DIR`). They stay useful after Overture retires release 2026-08-19.0, which the
analysis needs. The tables are derived databases shared under the ODbL 1.0; the inventory fields are also covered by
the TWDB's permission to copy and distribute, and the NOAA values are public domain. Details and attributions:
[../DATA_LICENCES.md](../DATA_LICENCES.md).

No file here holds a value read or computed from the challenge's strata table (social vulnerability, climate
vulnerability, population, rurality), which the challenge shares under CC BY-SA 4.0: the two share-alike licences
cannot both govern one file. Every table with tracts carries the tract GEOID, and `discovery/join_strata.py` adds
any strata column on your own machine from your own download of the challenge data:

    cd discovery
    python fetch_challenge.py                  the challenge layers, strata table included (skipped if cached)
    python join_strata.py                      svi_overall, ur_class, pop_total, cvi_climate_extreme_events
    python join_strata.py --columns svi_overall svi_household svi_housing_transport

It writes the joined copies to `discovery/work/joined/`, which is never committed. The entry's figures that rest on
the strata table (the rural share of residents, the SVI and CVI contrasts and their intervals) are computed by
`core_numbers.py`, `uncertainty.py` and `who_v4.py` into `discovery/work/` during a run.

## crossings.csv: one row per official crossing in the region (8,454)

The unique crossing set: TxGIO road crossings (pedestrian crossings left out) plus TWDB records more than 50 m from
any TxGIO record, inside the challenge's south-central-tx tracts.

| Column | Meaning |
|---|---|
| `src`, `src_id` | Inventory (`txgio` or `twdb`) and record id (TxGIO objectid, TWDB EXEXPALLID; keep it as text) |
| `lon`, `lat` | Position given by the inventory (WGS84) |
| `GEOID` | 2020 census tract holding the point |
| `county_src` | County named by the inventory |
| `road`, `road_eff` | Road named by TxGIO, and the road name used for matching (for TWDB, read from its description) |
| `stream`, `lwc_type`, `owner`, `origin`, `signage` | TxGIO stream, crossing type, owner, record origin and signage; for TWDB, `origin` is the regional flood planning group |
| `flood_freq`, `exp_type`, `desc` | TWDB flood frequency and exposure type; TxGIO location note or TWDB description |
| `has_name` | The inventory names the road |
| `tier` | How the crossing was matched to an Overture segment: `A_name_verified` (a segment within 100 m carries the same name or route number), `B_unnamed_within_15m`, `C_unverified` (nearest segment within 30 m), `none` |
| `name_verified` | Tier A |
| `d_any`, `d_named` | Metres to the nearest Overture segment, and to the nearest one with the same name (blank: none within 100 m) |
| `on_overture_30m` | An Overture segment lies within 30 m |
| `seg_id` ... `seg_len_m` | The Overture segment the crossing is attributed to: id, distance, class, name, route refs, road_flags values (blank: no flag), surface, the OSM way behind it (`w<id>@<version>`), length |
| `osm_tag_30m` ... `osm_tag_200m` | An OSM element tagged `ford`, `flood_prone=yes` or `hazard` with "flood" lies within 30, 60, 100 or 200 m |
| `in_strict_list` | Closed in the strict version of the test (tiers A and B) |
| `areas_plus_strict` | Ids of the areas in `areas.csv` that this crossing cuts off, space-separated |

## areas.csv: one row per cut-off area (903, of which 739 hold buildings)

Every Overture segment is split at its connectors and the short piece holding each crossing on the strict list is
removed, on the network that also counts service lanes and farm tracks as a way out. An area is a piece of the
network that reached the main network before and does not after.

| Column | Meaning |
|---|---|
| `area_id` | Area id, the one the entry and the maps use (979 is the Bexar example) |
| `buildings` | Microsoft footprints whose nearest road lies in the area |
| `residents_block`, `homes_block` | 2020 Census block population and housing units, shared over the footprints in each block |
| `n_cross`, `n_to_main` | Removed crossing pieces on the area's edge, and how many of them lead straight to the main network |
| `single_crossing` | Behind a single crossing: `n_cross` and `n_to_main` both 1 |
| `road_nodes` | Road network nodes inside the area |
| `tract`, `county` | Tract holding most of its buildings (GEOID); county named by the inventory |
| `crossings` | The crossings on its edge, as `src:src_id`, matching `crossings.csv` |
| `lon`, `lat` | Mean position of its buildings |
| `nearmiss_10m`, `nearmiss_20m`, `nearmiss_40m` | A road inside comes within that distance of a road of the main network away from any crossing, which could be an unmapped link |
| `tiger_verdict`, `tiger_share_reaching_main` | The same crossings cut in the Census Bureau's TIGER roads: `agrees_isolated`, `tiger_has_other_way`, `mixed` or `crossing_road_not_in_tiger`, and the share of sampled buildings that still reach the main TIGER network. Blank: not checked (single-crossing areas with fewer than 10 buildings, other areas with fewer than 30) |
| `careful_set` | TIGER agrees, no near-miss within 20 m, and at least one building: the entry's headline |

The careful set sums to 216 areas, 22,469 buildings, 26,257 residents and 11,236 homes (rounded sums), with 5,549
buildings in the 90 areas behind a single crossing.

## careful_tracts.csv: one row per tract holding a careful-set building (162, in 49 counties)

Sorted by buildings. An area can span tracts, so `careful_areas` sums to more than 216.

| Column | Meaning |
|---|---|
| `GEOID`, `county` | Tract, and county named by the inventories |
| `crossings_official` | Official crossings in the tract |
| `crossings_overture_30m` | Of those, with an Overture segment within 30 m |
| `crossings_marked_ford_flood` | Of those, marked by Overture as a ford or flood-prone road: 0 everywhere, because road_flags has no such value |
| `flood_crossing_attribute_gap` | The challenge's gap formula applied to that attribute, 1 - min(1, marked / official); blank where the tract holds no official crossing |
| `careful_areas`, `careful_buildings`, `careful_buildings_single` | Careful-set areas with buildings in the tract, their footprints in the tract, and of those the ones behind a single crossing |
| `careful_residents`, `careful_homes` | 2020 Census block estimates for those footprints |
| `tiger_agrees`, `tiger_other_way`, `tiger_mixed_or_road_missing`, `tiger_not_checked` | Every cut-off area with buildings in the tract (strict list, plus network), by TIGER verdict; not checked means below the 10 or 30 building threshold |
| `nearmiss_20m_areas` | Of the areas TIGER agrees on, those the 20 m near-miss test removed |
| `road_gap` | The scorecard's road gap (transport component) for the tract, 3 decimals; blank where the tract has no road component |

The columns sum to the careful set: 22,469 buildings, 5,549 behind a single crossing, 26,257 residents, 11,236
homes. The tracts hold 2,147 official crossings, 1,995 of them with an Overture segment within 30 m, none marked.

## crossing_tracts.csv: one row per scored tract holding an official crossing (1,848)

| Column | Meaning |
|---|---|
| `GEOID` | Tract |
| `crossings_official`, `crossings_overture_30m`, `crossings_marked_ford_flood` | As in `careful_tracts.csv` |
| `flood_crossing_attribute_gap` | 1 - min(1, marked / official): 1.0 in every row |
| `road_gap` | The scorecard's road gap, 6 decimals; blank where the tract has no road component (299 tracts). It is exactly 0 in 984 of the 1,549 tracts that have one |

## variants.csv: the six versions of the test, and the careful set

| Column | Meaning |
|---|---|
| `version`, `network`, `crossings` | `network` is `base` (the challenge's road file) or `plus` (also service, track, living_street and unknown roads); `crossings` is `all`, `strict` or `fords` (the strict list, fords only). The last two rows are the lead version (plus, strict) after the TIGER check, and after the near-miss test as well: the careful set |
| `crossings_closed` | Crossings cut (blank for the last two rows) |
| `areas`, `buildings` | Cut-off areas holding buildings, and their footprints |
| `single_areas`, `single_buildings` | The same for areas behind a single crossing |
| `residents_block`, `homes_block`, `single_residents_block`, `single_homes_block` | 2020 Census block estimates, rounded |
| `unlocated_buildings` | Footprints that fell in no Census block (0 in every version) |
| `all_stranded_groups` | Every cut-off piece of network, with or without buildings (blank for the last two rows) |

## core_numbers.json

The careful set's counts as `core_numbers.py` computes them: areas, buildings, residents and homes, tracts,
counties, the single-crossing subset, and the eight counties with the most buildings.

## figures/

`v4_region_map.png` (the region's official crossings and the 216 careful-set areas) and `v4_bexar_979.png` (the
Bexar example, area 979), drawn by `discovery/figures.py` from vector data only: no imagery. The Bexar figure's tract
labels quote the SVI of its two tracts from the challenge's strata table.

## ncei/: NOAA flood reports and the crossings they name

Written by `discovery/ncei_events.py` (step 28) from the bulk files of the NOAA NCEI Storm Events Database, 1996 to
2025 (https://www.ncei.noaa.gov/pub/data/swdi/stormevents/csvfiles/, public domain).

| File | What it holds |
|---|---|
| `ncei_manifest.json` | The 90 files the entry read (details, fatalities and locations for each year): URL, retrieval time (26 Sep 2026, 00:51 to 00:53 UTC), size and sha256, and the directory listing they were picked from. The step checks every file against it and stops on a difference |
| `ncei_summary.json` | Every NOAA figure the entry quotes, each with its definition: events, deaths and injuries in the region, reports that mention a low-water crossing, the vehicle share of deaths, the matches to named crossings, a table per county, and the sources with sha256. `sources.ncei_manifest` names the run's local copy of `ncei_manifest.json` |
| `ncei_events_region.csv` | One row per Flash Flood or Flood event in the region's counties (12,981): ids, type, date, county, deaths and injuries, fatality-file rows (in a vehicle, in water), begin and end points and whether they fall within 25 km of the event's county (`coords_ok`), the nearest official crossing, and one flag per search term for the event narrative (`kw_`) and the episode narrative (`ep_`). No narrative text. The copy in `discovery/work/` also has `ncei_url` (https://www.ncei.noaa.gov/access/storm-events-database/event-details/ followed by `event_id`) and `source_file` (the details file of the event's `YEAR` in the manifest), left out here because they repeat other columns |
| `ncei_crossing_matches.csv` | One row per report and an inventory crossing it may name (1,598): 134 `confirmed`, then 1,464 `ambiguous` rows listed for review with their reasons. Each row gives the rule the match passed or failed, its grade (A: two or more independent checks agree; B: one), the distances to the event's points, the crossing and its Overture segment, class and flags, the careful-set area it borders, the NCEI event page and an excerpt of at most 25 words from the report |

How the entry's NOAA figures come out of these files:

- 12,981 events and 550 deaths (`DEATHS_DIRECT` plus `DEATHS_INDIRECT`) in the region's 185 counties (184 had a flood
  event): the rows of `ncei_events_region.csv`, and `totals` in the summary.
- 738 reports that mention a low-water crossing, with 43 deaths, 155 injuries and 100 reports of rescues or people
  stranded or trapped: the rows whose `kw_low_water_crossing` is true where `narrative_source` is `event`, and whose
  `ep_low_water_crossing` is true where the event narrative is empty (the same rule for `kw_rescue_stranded_trapped`);
  `low_water_crossing_mentions` in the summary.
- 58.3% of the region's flood deaths from 1996 to 2019 in vehicles (225 of 386 fatality-file rows):
  `vehicle_share.years_1996_2019` in the summary.
- 16 fatal events tied to 16 named crossings in 14 counties, with 20 deaths; 9 of the events grade A; 8 crossings an
  ordinary road in Overture (11 deaths) and 8 a bridge (9 deaths): `matches.fatal_at_named_crossing` in the summary,
  which counts the `confirmed` rows of events with deaths whose report puts words of death beside the named road
  (`death_words_near_match`).

The excerpts are cleared of personal names before the table is written here: any name a report gives, found by its
context (an age after it, a title such as Mr or Mrs before it, or "identified as" or "named"), is removed from that
report's excerpts. On these files one report names a person, outside its excerpt, so no excerpt changed; the copy in
`discovery/work/` is the one before this step.

## audit/: the imagery audit of the careful set

A random sample of 40 of the 216 careful-set areas (10 from each size quartile, seed 20260926) was read twice,
independently, from the same renders over USGS orthoimagery, following written rules.
About half the areas could not be settled from imagery. Where both readings settled an area they agreed on 11 of 12.
Among the areas each reading settled, 55% (Wilson 95% interval 34% to 74%) in one and 26% (12% to 49%) in the other are
cut off when the creeks rise; weighted by size quartile, that is 5,067 to 14,426 of the careful set's 22,469 buildings.
Every dry exit found was a track or drive that neither Overture nor TIGER carries. The folder holds the sample
(`audit_sample.csv`), both readings (`audit_verdicts.csv`, `second_rater.csv`), their comparison
(`agreement_summary.md`) and the list of extra close-ups (`extra_views.csv`); no imagery is shipped, and
`discovery/precision_audit.py` draws the images again. The rules, the results and the files:
[audit/README.md](audit/README.md).
