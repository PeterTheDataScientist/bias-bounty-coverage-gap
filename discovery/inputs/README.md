# Inputs shipped with the discovery

Two public sources change over time, so the files the entry's run read are kept here: with them, the crossings and
OSM tags a run reads do not depend on what the live services serve on the day. The NOAA Storm Events files are too
large to keep here; [../../results/ncei/ncei_manifest.json](../../results/ncei/ncei_manifest.json) pins each of them by
sha256 instead. [../../TESTING.md](../../TESTING.md) lists every input a run checks and every one it reads live. Terms
for each file are in [../../DATA_LICENCES.md](../../DATA_LICENCES.md).

## lwc_2026-09-24: the two Texas crossing inventories

| File | Points | Retrieved (UTC) | sha256 of this file |
|---|---:|---|---|
| `txgio_lwc.geojson` | 8,339 | 2026-09-24 07:51:58 | `784bd76f7c2e22f0c85689bf7dd4397c0937fcadf17ba91bf524d13928d0e495` |
| `twdb_sfp_lwc.geojson` | 9,322 | 2026-09-24 07:52:38 | `ac0e8643dd0f73062f33422a014505a9a777ee1b5ee16b66c870828a38b2f470` |

Each keeps the point geometry and the attributes `lwc_prepare.py` reads (TxGIO: objectid, road, flowsource,
lwx_type, owner, source, signage, county, location_1; TWDB: EXEXPALLID, RFPG_NAME, COUNTY, FLOOD_FREQ, SVI,
EXP_TYPE, EXP_DESC), one feature per line. The other attributes are left out, including free-text comment fields.
`retrieval_log.json` is the log `fetch_lwc.py` wrote at download time: endpoint, counts, time, and the sha256 of the
full downloads (`302be1ed...` and `283ae32b...`), which differ from the hashes above because attributes were
dropped. `python fetch_lwc.py --snapshot inputs/lwc_2026-09-24` turns these files into the same tables
`lwc_prepare.py` read on 24 Sep; `python fetch_lwc.py` downloads the lists as they are today instead.

## osm_2026-09-23: OpenStreetMap ford and flood tags

| File | Rows | sha256 |
|---|---:|---|
| `osm_fordtags_texas_extract_2026-09-23.csv` | 18,838 | `d355bd245e99586521e13b1a4b5781e3c2d8611cb7fb6b1912cba7f3b5f42afb` |
| `osm_ways_with_fordnodes_texas_2026-09-23.csv` | 12,190 | `dfa44ab895ada05561723814229a39f71b8219add50c4a4fe7b8dc3ed273289e` |

Both come from the Texas extract on the openstreetmap.fr mirror
(https://download.openstreetmap.fr/extracts/north-america/us-south/texas.osm.pbf), replication sequence 7298377,
timestamp 2026-09-23T00:03:38Z, md5 `86878eb08e87ad724ecb1ed6a0e26d60`. The mirror serves only its latest extract
(about 800 MB), so the tables are kept here. The first holds every element tagged `ford` (other than `ford=no`),
`flood_prone=yes` or `hazard` containing "flood", with its version, edit time and position (a way's position is
the mean of its nodes). The second holds every highway way that passes through a node tagged `ford`, with the ids
of those nodes, space-separated. `python osm_fords.py --extract inputs/osm_2026-09-23` loads both;
`python osm_fords.py --pbf FILE` rebuilds them from an extract you download yourself.
