# Data used by this repository, and the terms each is shared under

The code is MIT licensed ([LICENSE](LICENSE)). The data below is not: each source keeps its own terms. Licence
statements were read at source on 25 September 2026; the NOAA Storm Events files, added on 26 September, are public
domain as works of the US federal government.

## The terms of each source

| Source | Terms | How this repository uses it |
|---|---|---|
| Challenge data (the organisers' Source Cooperative bucket) | CC BY-SA 4.0 (challenge rules), for the bundle as the organisers share it; the layers inside it also keep their original terms, listed in the rows below | Downloaded by the scripts, never committed |
| Challenge strata table (`REGION-strata-tract-table.parquet`: social and climate vulnerability, population, rurality) | CC BY-SA 4.0 (challenge rules) | Downloaded, never committed; no value from it is in the tables in `results/` (see below) |
| Overture Maps, buildings and transportation themes (release 2026-08-19.0; in the challenge bucket, and the extra road classes `discovery/fetch_overture_extra.py` downloads) | ODbL 1.0, (c) OpenStreetMap contributors; transportation also carries data from TomTom (https://docs.overturemaps.org/attribution/) | The road network the discovery closes; counts per tract in the documentation entry |
| Overture Maps, places theme (in the challenge bucket) | Mostly CDLA Permissive 2.0 (Meta, Microsoft and other sources); Apache 2.0 for Foursquare's records and CC0 1.0 for AllThePlaces' (same page) | Counted per tract by the documentation pipeline |
| Microsoft Global ML Building Footprints (in the challenge bucket) | CDLA Permissive 2.0, per Microsoft's own README and LICENSE (https://github.com/microsoft/GlobalMLBuildingFootprints); the challenge README lists ODbL | Counted per tract and per cut-off area |
| OpenStreetMap: the ford and flood tags of the Texas extract of 23 Sep 2026 (`discovery/inputs/osm_2026-09-23/`), and OSM data inside Overture | ODbL 1.0, https://www.openstreetmap.org/copyright | Shipped as two derived tables; compared with the official crossings |
| TxGIO Low Water Crossing inventory, and the TWDB State Flood Plan layer "Low Water Crossing" (`discovery/inputs/lwc_2026-09-24/`) | TWDB site policy: the TWDB "freely grants permission to copy and distribute its materials" and would appreciate acknowledgment (https://www.twdb.texas.gov/policies/site/); TxGIO is part of the TWDB | Shipped as retrieved on 24 Sep 2026, attributes the analysis reads only |
| U.S. Census Bureau: TIGER/Line roads (in the challenge bucket), 2020 Census block counts (TIGERweb, `discovery/block_pop.py`, `discovery/block_pop_v4.py`), County Business Patterns | Public domain | Road check, residents and homes, establishments |
| NOAA National Centers for Environmental Information (NCEI), Storm Events Database: bulk files 1996 to 2025, details, fatalities and locations (`discovery/ncei_events.py`) | Public domain in the United States, as a work of the US federal government | Downloaded and checked against the 90 sha256 values in `results/ncei/ncei_manifest.json`; the derived tables are shipped in `results/ncei/` |
| USGS The National Map: facilities (in the challenge bucket) and orthoimagery (`discovery/imagery_check.py`, `discovery/precision_audit.py`, `discovery/nearmiss_imgs.py`, `discovery/nearmiss_sample.py`) | Public domain, per the USGS | Imagery is drawn locally for the checks and the audit and is never committed |
| PROJ 9.5.1 source code (`documentation/tools/build_proj_fma.sh`) | MIT, https://proj.org | Downloaded and built locally |

## Why the result tables hold no strata-table value

Most tables in `results/` are derived databases of Overture and OpenStreetMap data, so the ODbL 1.0 requires them to be
shared under the ODbL 1.0. The challenge's strata table is shared under CC BY-SA 4.0, which requires adapted material
to be shared under CC BY-SA 4.0 or a licence it lists as compatible, and neither licence lists the other. One file
holding both kinds of value could not satisfy both, so they are never combined:

- the tables in `results/` hold values derived from Overture and OpenStreetMap, beside values from public-domain
  sources (Census blocks, TIGER, NOAA's Storm Events), permissive ones (Microsoft footprints under CDLA Permissive 2.0)
  and the TWDB inventories under the TWDB's permission, all of which may be included in an ODbL database, plus the
  tract GEOID;
- no value read or computed from the strata table is among them: no social or climate vulnerability score, no
  population and no rurality class, not even a resident estimate built from tract population (the tables use
  2020 Census block counts, which come from the Census Bureau directly);
- `discovery/join_strata.py` joins any strata column to the tables by GEOID on your own machine, from your own
  download of the challenge data, into `discovery/work/joined/`, which is never committed. Those joined copies mix
  ODbL and CC BY-SA 4.0 material: keep them for your own analysis, and do not publish them as one table.

The entry's figures that rest on the strata table (the rural share, the SVI and CVI contrasts and their intervals)
are computed during a run into `discovery/work/` and quoted in the entry's text; they are not shipped as data. The
one place a strata value appears is a picture: the labels of `results/figures/v4_bexar_979.png` quote the SVI of the
two tracts it shows, from the challenge data attributed below.

## Shipped in this repository

| File | What it holds | Terms |
|---|---|---|
| `discovery/inputs/osm_2026-09-23/osm_fordtags_texas_extract_2026-09-23.csv` | The 18,838 OpenStreetMap elements in the Texas extract of 23 Sep 2026 tagged `ford`, `flood_prone=yes` or `hazard=flood` (18,096 nodes, 742 ways): type, id, version, timestamp, those tags, highway, name, waterway, coordinates | ODbL 1.0, derived database |
| `discovery/inputs/osm_2026-09-23/osm_ways_with_fordnodes_texas_2026-09-23.csv` | The 12,190 highway ways in the same extract that pass through a node tagged `ford` | ODbL 1.0, derived database |
| `discovery/inputs/lwc_2026-09-24/txgio_lwc.geojson` | The TxGIO Low Water Crossing inventory as retrieved on 24 Sep 2026 (8,339 points), with the attributes the analysis reads | TWDB permission to copy and distribute |
| `discovery/inputs/lwc_2026-09-24/twdb_sfp_lwc.geojson` | The TWDB State Flood Plan layer "Low Water Crossing" as retrieved on 24 Sep 2026 (9,322 points), with the attributes the analysis reads | TWDB permission to copy and distribute |
| `results/crossings.csv` | One row per official crossing: inventory fields, the Overture segment it sits on and its flags, OSM tags nearby | ODbL 1.0, derived database; the inventory fields also under the TWDB's permission |
| `results/areas.csv` | One row per cut-off area: building counts and positions, Census block residents and homes, crossing ids, TIGER verdict, near-miss flags | ODbL 1.0, derived database |
| `results/careful_tracts.csv`, `results/crossing_tracts.csv` | One row per tract: official crossings, those Overture carries and marks, cut-off buildings with Census block residents and homes, TIGER verdicts, the scorecard's road gap (computed from Overture and TIGER roads) | ODbL 1.0, derived database |
| `results/variants.csv`, `results/core_numbers.json` | Summary figures of the analysis | ODbL 1.0, derived database |
| `results/ncei/ncei_events_region.csv` | One row per NOAA Flash Flood or Flood event in the region's counties, 1996 to 2025: NOAA's fields without the narrative text, keyword flags, and the nearest official crossing | NOAA values public domain; the crossing ids and distances come from the TWDB inventories (TWDB permission) |
| `results/ncei/ncei_crossing_matches.csv` | One row per NOAA report and an official crossing it may name: NOAA's fields, an excerpt of at most 25 words with any personal name removed, the match rules, the crossing and its Overture segment | ODbL 1.0, derived database; NOAA values public domain; inventory fields under the TWDB's permission |
| `results/ncei/ncei_summary.json`, `ncei_manifest.json` | The NOAA figures of the entry with their definitions, and the list of the 90 NOAA files read (URL, retrieval time, size, sha256) | ODbL 1.0 for the counts of Overture-derived areas; NOAA values and the file list public domain |
| `results/audit/audit_sample.csv`, `audit_verdicts.csv`, `second_rater.csv`, `agreement_summary.md`, `extra_views.csv` | The imagery audit's sample; its two readings, made independently from the same renders following written rules, with each area's counts, verdicts and reasons; their comparison; and the centres of the extra close-ups. No imagery | ODbL 1.0 for the area data; the verdicts, reasons and comparison are the readings' own text |
| `results/figures/v4_region_map.png`, `results/figures/v4_bexar_979.png` | Maps drawn from vector data only | Produced works of the sources above; keep the attribution below with them |

## Attribution

- Map data (c) OpenStreetMap contributors, available under the Open Database Licence 1.0.
- Overture Maps Foundation, release 2026-08-19.0: transportation theme (with data from TomTom) and buildings theme
  under the ODbL 1.0, places theme under CDLA Permissive 2.0, Apache 2.0 and CC0 1.0 by source.
- Texas Water Development Board and Texas Geographic Information Office, low-water-crossing inventories.
- Bias Bounty Mapping Equity Challenge data, shared by the organisers under CC BY-SA 4.0.
- Microsoft Global ML Building Footprints, CDLA Permissive 2.0.
- U.S. Census Bureau, TIGER/Line, 2020 Census and County Business Patterns, public domain.
- U.S. Geological Survey, The National Map, public domain.
- NOAA National Centers for Environmental Information, Storm Events Database, public domain.
