# Methodology writeup with a Best Bias Discovery section: exact coverage-gap reconstruction, and Texas low-water crossings the open map carries as ordinary roads

This is my writeup as posted on the challenge's discussion board: one post in two parts, Part 1 the methodology (Best Documentation) and Part 2 the Best Bias Discovery section, with the tables rendered. The appendices Part 1 points to follow the post.

I am Zindi user PeterTheAnalyst. This post is my methodology writeup for the challenge and my entry for both special prizes. Part 1 is the methodology, for Best Documentation, and Part 2 is the clearly labelled Best Bias Discovery section. Code, result tables and figures for both parts: https://github.com/PeterTheDataScientist/bias-bounty-coverage-gap.

Part 1, methodology: the pipeline behind my scored column, one Python file, with the prize's edge cases and 29 alternative conventions and weightings, each measured. With the standard pyproj wheel its output scores a public error of 0.00000301; with PROJ compiled for fused multiply-add it scores exactly 0.

Part 2, Best Bias Discovery: Overture has the road at 93.1% of the 8,454 official low-water crossings in the challenge's Texas region but marks none of them as a crossing that floods, and the scorecard cannot see this. When I close the crossings in Overture's own road network, 22,469 buildings (about 26,300 residents) in 216 areas are left with no mapped road out, and TIGER agrees.

## Contents

- Part 1, methodology (Best Documentation): summary; where the prize text is answered; a note on the four input layers that left the bucket; sections 0 to 11.
- Part 2, Best Bias Discovery: summary; D1 what is missing, and why the scorecard cannot see it; D2 the evidence; D3 who is affected, and why it matters; D4 how this sits next to other entries, and what would close the gap; D5 reproducing it; D6 limits.
- Sources and updates for both parts are at the end.

## Part 1: Methodology (Best Documentation)

*How my scored column is built, and how much each open choice in the specification moves it*

### Summary

- **What it is:** the pipeline behind my scored column, one Python file, with the prize's edge cases and 29 alternative conventions and weightings, each measured. My Best Bias Discovery entry, on Texas low-water crossings, is Part 2 of this post.
- **Score:** public error 0.00000301 with the standard pyproj wheel (1S1Ei46w, my scored column); exactly 0 with PROJ compiled for fused multiply-add (RkEkksFb). Challenge data only; no model, seed, manual step or score file.
- **To reproduce:** python pipeline.py --check --data-dir FOLDER, under 4 minutes on 2 cores and 8 GB, every input checked against a published sha256 (four input layers left the bucket on 25 September: see the note below).
- **New here, as far as I can find after reading every writeup thread:** the reference's arithmetic on an ordinary Intel or AMD machine, by compiling PROJ with -mfma, with a control build matching the pyproj wheel bit for bit and a one-point test of which arithmetic you have; and the scorecard's ratios under every variant, from saved per-tract counts.
- **Credit:** the plateau's cause is wangwu's (thread 34972); the metric reading and exclusion rule are Yanard's (thread 34908); other ideas are credited where used and in section 11.

### Where the prize text is answered

| Prize text | Answered in |
|---|---|
| Clearest, most reproducible methodology writeup | Summary, the note below, sections 2, 9 and 10 |
| Document your data sources | Section 3 and the note below |
| How you computed each component | Sections 1 and 4 |
| Edge cases: zero-population tracts | Section 5 |
| Edge cases: water-dominated tracts | Section 5 |
| Edge cases: tracts with no Overture data | Section 5 |
| Alternative weightings you applied and why | Section 7 (other open choices: section 6) |
| Evaluation page: metric, tract list, file format | Sections 0, 5 and 9 |
| Evaluation page: reflect on the bias scorecard | Section 8 |

### Note, 26 September 2026: four input layers left the bucket

On 25 September the bucket's README added: "TIGER/Line roads, Microsoft building footprints, HIFLD facilities and CBP establishments were removed from every region at the challenge organizers' request." So 24 of my 44 input files now return 404. The other 20 (Overture layers, tract polygons, sample submissions) and the strata tables are unchanged: same size and S3 ETag on 26 September.

To run it now, put the 44 files in one folder, named as in the bucket or in my cache, and run python pipeline.py --check --data-dir FOLDER. documentation/INPUTS_MANIFEST.csv gives each file's size and sha256, and --check stops before building if one differs; without --data-dir the pipeline stops at once, naming the missing files. The organisers hold the removed files. Their public sources:

- TIGER/Line 2025 roads: https://www2.census.gov/geo/tiger/TIGER2025/ROADS/
- Microsoft GlobalML Building Footprints, February 2026 refresh: https://github.com/microsoft/GlobalMLBuildingFootprints
- USGS National Map structures: https://carto.nationalmap.gov/arcgis/rest/services/structures/MapServer
- County Business Patterns: https://www.census.gov/programs-surveys/cbp.html
- HUD USPS crosswalk, which takes CBP from ZIP to tract: https://www.huduser.gov/portal/datasets/usps_crosswalk.html

The challenge cut them to each region, so a rebuild from source may differ; the manifest identifies the right bytes.

### 0. How to read this

Section 6 is the main part: it changes one convention at a time and shows how far the 9,379 values move, so you can see which open choices matter without trusting any score. The board behaves like mean absolute error, not the root mean squared error the evaluation page names (section 9; Yanard, thread 34908, saw it first), so a variant that moves the values by more than twice my error must score worse than my file. That is Yanard's rule too; I call it the magnitude test, and every variant I rule out clears it by a factor of 3.9 or more.

### 1. What is computed

Per census tract, a coverage gap score from 0 (full coverage) to 1 (no coverage). Each component compares an Overture layer with a reference layer:

    gap = 1 - min(1, overture / reference)

A component is undefined where the reference is zero; the composite is "the mean of the components that are defined for that tract" (evaluation page), so the divisor is 1, 2 or 3.

- **transport_gap:** Overture against TIGER/Line named-highway length.
- **building_gap:** Overture against Microsoft building count.
- **poi_gap:** the mean of two halves: fire stations, EMS stations and schools, Overture against the USGS National Map; and all Overture places against Census County Business Patterns establishments.

Scored list: 9,379 tracts (northern-ca 591, eastern-ok 1,192, maricopa-az 1,593, south-central-tx 6,003); all-tract mean 0.058437.

### 2. The pipeline at a glance

One script, pipeline.py, region by region:

    the 44 input files, checked against INPUTS_MANIFEST.csv
    → tract polygons, reprojected to EPSG:5070
    → roads: named-highway classes, reprojected, split at tract boundaries, metres summed per tract
    → buildings: one parquet row group at a time, one centroid per footprint, counted per tract
    → places: filtered by category, counted in every tract each one intersects
    → USGS facilities and CBP establishments: counted or read per tract
    → out/counts.parquet: every count the score needs, one row per scored tract
    → gaps, composite at 6 decimal places → submission.csv, README checks, sha256

sensitivity.py rebuilds sections 6 and 7 (bar the lines marked * and +) from counts.parquet in half a second.

### 3. Data sources

All from the organisers' Source Cooperative bucket, https://data.source.coop/humane-intelligence/bias-bounty-mapping-equity-challenge/ (HTTP 403 without a User-Agent header), retrieved 13 September 2026, re-checked 23 and 26 September. Per region, from reference/: the sample submission (the authoritative tract list); Overture roads, buildings and places (release 2026-08-19.0, as the data page requires); TIGER/Line 2025 roads; Microsoft GlobalML footprints; USGS fire, EMS and school points (files named hifld); and CBP establishments apportioned from ZIP to tract. From strata/: tract polygons, and the strata table, read only for sections 5 and 8. All are OGC:CRS84, longitude then latitude. Not used, per the evaluation page: ACS housing units and hospitals.

Licences: challenge data CC BY-SA 4.0; Overture ODbL for buildings and roads, mostly CDLA Permissive 2.0 for places; Microsoft CDLA Permissive 2.0 per Microsoft, though the challenge README says ODbL; Census and USGS public domain; my code MIT. Details: DATA_LICENCES.md.

### 4. How each component is computed

4.1 transport_gap. TIGER MTFCC S1100 and S1200 against Overture motorway, trunk, primary and secondary. Both layers go to EPSG:5070 (Albers equal area, metres) before any geometry operation; every segment is split at the tract boundaries and each tract credited the length inside it; undefined where a tract has no TIGER named highway. I split rather than give each whole segment to its midpoint's tract because the README publishes the scored tracts with no road component, 218, 253, 869 and 1,704 by region; splitting reproduces all four, and the midpoint rule gives 368, 475, 1,330 and 3,603 (Thelightthatshines, thread 34847, and Yanard first tested road readings against these counts). TIGER stores a road with two route numbers twice (de-coder, thread 34744), and the reference keeps both copies.

4.2 building_gap. Each footprint counts in the tract containing its true polygon centroid, taken in the layer's own longitude and latitude, for Overture and Microsoft alike. None of the 34,860,889 centroids lies exactly on a boundary (Yanard found the same), so within and intersects agree.

4.3 poi_gap. Facilities: Overture places match each USGS layer on categories.primary (fire = fire_department; EMS = ambulance_and_ems_services; schools = elementary_school, middle_school, high_school, school, private_school, public_school). Each type's gap is undefined where the tract has none, and the half is the mean of the defined types. Establishments: all Overture places, including the 4 to 6 percent with no primary category (CBP counts establishments, not categorised ones), against cbp_estab, fractional and unrounded. poi_gap is the mean of the defined halves. Places are counted with intersects: 48 lie exactly on a tract boundary, none in a facility category, and each counts in every tract it touches, 104 assignments across 92 tracts. The USGS facilities use within, but none lies on a boundary (Luca925 and NickyGuants found the same), so both sides of each ratio follow one rule.

4.4 The composite is the mean of the defined components (27 tracts have one, 3,028 two, 6,324 three), written at 6 decimal places, the reference's stored precision.

### 5. The three edge cases the prize names, and four more

Zero-population tracts. 26 scored tracts have no residents (0, 1, 11 and 14 by region, in section 1's order): 16 Census special land-use tracts (codes 98xx), the 2 no-land tracts below and 8 others. Population enters no component, so they are scored like any other; they average 0.134 against 0.058 overall (Thelightthatshines noted this first).

Water-dominated tracts. Seven south-central-tx tracts are all water with no scorable reference, and the organisers drop them from the scored list (48007990000, 48061990000, 48261990000, 48273990000, 48321990000, 48355990000, 48489990000); the pipeline takes each sample submission as the tract list, so 6,010 polygons give 6,003 rows. Another 43 scored tracts are more than half water (2, 1, 0 and 40 by region) and keep their land features: 28 have three components, 13 two, 2 one. Those 2, 48039990000 and 48057990000, have no land: their only reference is 1 and 48 Microsoft footprints, Overture has no building in either, and each scores exactly 1.0. The specification requires that, so I keep it; for preparedness, set them aside, as thibaudlepan (thread 34844) advises.

Tracts with no Overture data. Where the reference has something and Overture nothing, the component is a full gap of 1, never imputed or dropped: 15 tracts have TIGER named highway but no Overture named highway, 2 have Microsoft buildings but no Overture ones (the no-land pair, the only tracts with no Overture feature at all), and none has CBP establishments but no Overture places. The opposite case, no reference, is undefined and leaves the divisor (3,044 tracts have no road component, 6 no building component, 32 no POI component); counting it as zero would record missing reference data as perfect coverage.

Four more fail silently, and the code handles each: GEOID is text (Maricopa is FIPS 04); the layers are longitude then latitude, which some engines flip when told EPSG:4326; maricopa-az includes the New Mexico tract 35023970000; and a left join can drop tracts with nothing to count (Ajitv, thread 34901), so counts come from an inner join mapped back to the scored list. Appendix C of WRITEUP.md has the details.

### 6. The open choices, measured

Each line changes one convention and recomputes all 9,379 values. "out": the mean change exceeds twice my error (0.00000602); "same": nothing moves; "board": a submission decided it; "passes": the change is under that bound, so the magnitude test cannot rule it out. Lines marked * come from tools/extra_variants.py, the + line from a one-off DuckDB check, the rest from sensitivity.py; appendix A of WRITEUP.md has each line's board scores, sources and credits.

| Group | Choice | Tracts | Mean change | Largest | Verdict |
|---|---|---:|---:|---:|---|
| Roads | Whole segment to its midpoint's tract, not split | 3,927 | 0.0359 | 0.444 | out (a) |
| Roads | Split in lon/lat, then measured in EPSG:5070 | 1,789 | 0.000121 | 0.119 | out |
| Roads | Split in lon/lat, measured geodesically | 2,807 | 0.000205 | 0.119 | out |
| Roads | Overture tertiary added to the highway classes | 2,752 | 0.0244 | 0.333 | out, board |
| Roads | TIGER ramps (S1630) added to the reference | 1,977 | 0.00377 | 0.333 | out, board |
| Roads | TIGER byte-identical geometries kept once * | 1,283 | 0.00573 | 0.230 | out |
| Roads | TIGER repeated LINEARID and geometry once * | 73 | 0.000124 | 0.120 | out |
| Roads | Source CRS named EPSG:4326, not OGC:CRS84 * | 0 | 0 | 0 | same |
| Roads | DuckDB spatial instead of GEOS for the split + | 0 | under 1e-16 |  | same |
| Buildings | Centre of the covering bbox, not the true centroid | 48 | 0.00000078 | 0.00139 | board (b) |
| Buildings | Point on surface, not the true centroid * | 92 | 0.0000013 | 0.00102 | exact 0 (c) |
| Buildings | Every footprint touching the tract | 593 | 0.0000441 | 0.340 | out |
| Buildings | A multipolygon footprint counted once per part | 134 | 0.0000235 | 0.0599 | out |
| Buildings | Centroid taken in EPSG:5070, not lon/lat * | 0 | 0 | 0 | same |
| Places and facilities | within instead of intersects for places | 3 | 0.000000097 | 0.00031 | board |
| Places and facilities | A boundary place counted once, lower GEOID * | 2 | 0.000000065 | 0.00031 | passes |
| Places and facilities | Facilities and centroids with intersects * | 0 | 0 | 0 | same |
| Places and facilities | Places with no primary category left out | 241 | 0.000317 | 0.195 | out |
| Places and facilities | Permanently closed places left out * | 213 | 0.00052 | 0.250 | out |
| Output | Full precision instead of 6 decimal places | 5,289 | 0.000000145 | 0.0000005 | board |
| Output | Composite from components rounded to 6 dp | 427 | 0.000000046 | 0.000001 | exact 0 (c) |
| Arithmetic | PROJ built with fused multiply-add | 21 | 0.0000016 | 0.0038 | board: 0 |

(a) It also fails the README counts of section 4.1.

(b) Together with 6 dp output, worth 0.000000142 alone, the centroid took the score from 0.000003552 to 0.00000301.

(c) The fused file scored exactly 0, so a variant on it that moves one public tract scores above 0, and the chance that 92 moved tracts all miss the public 30 percent is 0.7 to the power 92, 6 in 10^15.

### 7. Alternative weightings, and why none is applied

The evaluation page defines the reference as an unweighted mean of the defined components, so no weighting is applied. I built and measured every alternative below, and ruled each one out:

| Alternative weighting | Tracts | Mean change | Largest |
|---|---:|---:|---:|
| CBP residential share (cbp_estab_res) | 1,974 | 0.0221 | 0.462 |
| POI as a flat mean of four terms, not two halves | 1,190 | 0.00349 | 0.0833 |
| Undefined facility types counted as a zero gap | 1,487 | 0.00828 | 0.500 |
| EMS left out of the facilities half | 381 | 0.00265 | 0.250 |
| Facilities half as fire stations only | 1,404 | 0.0116 | 0.250 |
| Composite always divided by three | 1,152 | 0.00217 | 0.667 |
| Ratio not capped at 1 | 9,322 | 1.02 | 356 |

The residential share counts homes, but the README makes the business share the default (cbp_estab equals cbp_estab_bus in every row). Four equal terms ignore the evaluation page's two halves. A zero gap for an undefined facility type, like a divisor of always three, records missing reference data as perfect coverage. EMS is thin (592 stations) and fire stations carry the facilities half, yet dropping EMS, or keeping only fire, moves hundreds of tracts. An uncapped ratio lets surplus (three times the reference road length scores minus 2) cancel a real gap.

### 8. What these choices do to the bias scorecard

My column sits about 0.000003 from the reference, so its scorecard is in effect the reference's: coverage gaps 2.33 times larger in rural than in urban tracts, 2.90 times on tribal land, 1.75 in wildfire hazard tracts, 1.58 at high climate vulnerability and 1.24 at high social vulnerability, but 0.59 for summer heat, because the hottest tracts are more often urban and urban tracts are well mapped.

My column gives the tribal ratio exactly (2.901; the scorecard shows 2.90), so I recomputed it under every variant. These move it by more than 0.1: the midpoint rule to 2.61, TIGER ramps 2.78, the CBP residential share 2.19, undefined facility types as zero 3.11, fire stations only 3.16, a divisor of always three 3.02, and the uncapped ratio 0.52, which reverses the finding (as thibaudlepan showed for buildings). Leaving EMS out gives 2.98; no other line moves it by more than 0.025. Every variant that survives the specification and the board leaves 2.901, and any variant that moves it would change what the scorecard says about tribal land. The midpoint rule also moves the social vulnerability ratio from 1.24 to 1.16, climate vulnerability from 1.58 to 1.43 and legally-defined tribal land from 2.33 to 2.48 (tools/scorecard_ratios.py). My thread 34756 of 14 September said these stay within 0.002; that was wrong, and I have corrected that post (edited 26 September), which is now a methodology note on the road boundary rule.

Part of the pooled 2.90 is geography, and transport gaps are not comparable across regions (evaluation page): 805 of the 858 tribal tracts are in eastern-ok, and within regions the ratio is 1.89 (eastern-ok), 2.62 (maricopa-az) and 1.91 (northern-ca), as ALDFX-ML (thread 34903) argued first.

### 9. Validation

With no score file: the scored tract counts (591, 1,192, 1,593, 6,003) and tracts with no road component (218, 253, 869, 1,704) are asserted in code and match the README, and the share of tracts with an undefined component (21.3, 36.9, 28.5, 54.9 percent for eastern-ok, northern-ca, south-central-tx, maricopa-az) matches the evaluation page's 21, 37, 28 and 55 (thibaudlepan checked first).

The acceptance window. Read as the reference's column means over all 9,379 tracts, rounded to 6 decimals, with undefined components as 0, the four constants in the Data page's SampleSubmission.csv confine each column sum of a correct file to a window 0.0094 wide (built up by malekarkan, Yanard and Pricilegangbe). My scored file's building and POI sums fall inside; its transport sum is 0.0073 above and its composite 0.0050 above, which puts the residual in the roads. Rounding matters: under truncation even the building sum would fall outside.

The residual. Rounding to 6 decimals took my score from 0.000003874 to 0.000003732, a gain almost equal to the mean rounding change (0.000000142 against 0.000000145), so nearly every tract already matched. On 23 September wangwu (thread 34972) traced the rest to floating-point arithmetic and reproduced the reference on arm64: highways that share their lines with tract boundaries land about 0.00000000001 m inside or outside a tract after projection, depending on the last bit, and compilers fuse a multiply and an add into one rounding by default for ARM processors but not in the usual Intel and AMD builds. I checked it without an ARM machine by compiling PROJ 9.5.1 twice under pyproj 3.7.2. With fused multiply-add off, the build matches the pyproj wheel exactly (2,000,000 test points, every tract's road length); with it on (-mfma), 21 composites change, 19 in Texas and, in my build, 2 in Carter County, Oklahoma, and the file scored exactly 0, with GEOS still the ordinary x86 wheel. Its transport column sums to 1048.2997252134437, the figure chizzydev250 (thread 35012) reports from DuckDB on Linux arm64.

The metric and the file. An all-zeros file scored 0.059806101, near my column's mean (0.058437), not its root mean square (0.106164), and the tertiary and ramps variants scored within 4 percent of their mean absolute change: mean absolute error fits. A five-column file with transport_gap zeroed scored the same, so the board reads the second column (as thibaudlepan found); I submit two columns, every row filled.

### 10. Reproducing it

Tested with Python 3.11.15, geopandas 1.1.4, shapely 2.1.2 (GEOS 3.13.1), pyproj 3.7.2 (PROJ 9.5.1), pyarrow 25.0.1, pandas 3.0.2 and numpy 2.4.4. No randomness.

    python pipeline.py --check --data-dir FOLDER

writes the 9,379-row submission.csv, sha256 40aea8185bdf0aa7b2653d237581e6cb8adfa3df59de4a15b1ec06fcc5f7c289, byte for byte the file scored as 1S1Ei46w, as did a second, clean machine and reruns on 25 and 26 September.

    bash tools/build_proj_fma.sh
    PYTHONPATH=proj_fma python pipeline.py --check --data-dir FOLDER

builds PROJ 9.5.1 with -mfma on Intel or AMD Linux (cmake, a C++ compiler and sqlite3 needed), lays it over the pyproj wheel and gives sha256 30110feb61ee848973a9b7543741c7d586fdf850e26da3854816cd26e2486908. python tools/fingerprint.py shows which arithmetic you have: a point in Austin projects to northing 800570.8529844111 without fused multiply-add, 800570.8529844118 with it.

    python pipeline.py --check --extra --data-dir FOLDER
    python sensitivity.py --error 0.00000301
    BIAS_DATA_DIR=FOLDER python tools/extra_variants.py --error 0.00000301
    BIAS_DATA_DIR=FOLDER python tools/scorecard_ratios.py
    python tools/acceptance_window.py out/counts.parquet

rebuild sections 6 to 9 (about 18 and 10 minutes for the two geometry steps); extra_variants.py first asserts that every base count it recomputes equals the pipeline's. The four conventions that decide the scored column sit in a CONV dictionary at the top of pipeline.py. The pipeline stops rather than write a wrong file: on a missing or altered input, a scored GEOID with no polygon, a count that differs from the README, or a tract with no defined component.

Code: https://github.com/PeterTheDataScientist/bias-bounty-coverage-gap , folder documentation/ (MIT licence). The WRITEUP.md at the root of that repository is this post with the tables rendered, plus appendices on each table line, the board path, checking a copy and credits.

### 11. Credits

Published by other entrants before this post and used here, in date order: malekarkan (34703, the sample constant); Colossius97130 (34713, a SHA-256 rebuild); de-coder (34744, TIGER duplicates); thibaudlepan (34844, undefined shares, the second column, the uncapped reversal); Thelightthatshines (34847, zero-population and no-land tracts, README-count tests); Ajitv (34901, the lossy join); ALDFX-ML (34903, geography); Yanard (34908, the metric reading, the magnitude rule, intervals from the constants); Luca925 (34925, facilities on boundaries, the CRS84 shift); NickyGuants (34962, board scores for duplicates and boundary places); wangwu (34972, the fused multiply-add cause); TlT (34980, the checklist); Pricilegangbe (34992, sum windows, repeated TIGER records); PIO (35000, ratios with roads rebuilt); chizzydev250 (35012, the arm64 sum).

## Part 2: Best Bias Discovery

*Texas low-water crossings, where roads go under water, appear on the open map as ordinary roads*

This part is my Best Bias Discovery entry. My Best Documentation entry is Part 1 above, and my earlier post 34756 is a methodology note on the road boundary rule, not this entry. The additional sources in section D2.1 are used for this entry only; my scored submission uses the challenge data alone. Code, result tables and figures: https://github.com/PeterTheDataScientist/bias-bounty-coverage-gap (folders discovery/ and results/). Every number below is produced by that code, and the repository names the output file for each one.

### Summary

Texas publishes 8,454 official low-water crossings inside this challenge's Texas region: places where a road dips through a creek bed and goes under when the creek rises. Overture has the road at 93.1% of them but marks none of them as a crossing that floods, because its road schema has no value that could say so. If I put that attribute through the challenge's own gap formula, it is missing in full (gap 1.000) in every one of the 1,848 tracts that hold a crossing.

The scorecard cannot see this: its road measure compares highway lengths, and 79.1% of the crossings are on local roads. In 984 of the 1,549 crossing tracts that get a road score, the road gap is exactly 0.

The exposure is rural: 147 crossings per 100,000 rural residents against 14 per 100,000 urban residents, ten times higher.

Since 1996, 738 NOAA flood reports from the region's counties mention a low-water crossing, and they record 43 deaths. I can tie 20 deaths to 16 named crossings in the inventories; Overture carries 8 of those 16 crossings as ordinary roads and the other 8 as bridges, and marks none as a ford.

When I close the crossings in Overture's own road network, 22,469 buildings (about 26,300 residents) in 216 areas are left with no mapped road out, and TIGER agrees. Two independent readings of a random sample on aerial imagery put between about a fifth and two thirds of those buildings behind no dry way out at all; where imagery could settle it, the others have a track or drive that neither map carries.

### D1. What is missing, and why the scorecard cannot see it

The road is on the map, so the gap is in an attribute: nothing in the map says that the road floods. All five scorecard metrics compare lengths or counts of features, and no comparison of that kind can detect a missing attribute on a road that is present.

Most crossings are also on roads the scorecard does not measure. The transport gap compares TIGER S1100 and S1200 highways with Overture motorway, trunk, primary and secondary roads, while 79.1% of the crossings are on residential, unclassified or tertiary roads.

Nor is there a flood stratum: the region's strata tract table has 227 columns, and none of them describes flood exposure.

To put this in the challenge's own terms, I applied its gap formula to the attribute. For each tract, flood crossing gap = 1 - min(1, crossings Overture marks as a ford or as flooding / official crossings). It is 1.000 in all 1,848 crossing tracts, because the marked count is zero everywhere. In the same tracts the scorecard's road gap is exactly 0 in 984 of the 1,549 that have a road score, and undefined in the other 299.

### D2. The evidence

D2.1 Sources, with retrieval dates (UTC)

- Texas Geographic Information Office (TxGIO) Low Water Crossing inventory, 8,339 points: https://feature.geographic.texas.gov/arcgis/rest/services/Basemap/Low_Water_Crossing/MapServer/0 (retrieved 24 Sep 2026 07:51).
- Texas Water Development Board (TWDB) State Flood Plan layer "Low Water Crossing", 9,322 points compiled by the regional flood planning groups: https://gis2.twdb.texas.gov/server/rest/services/OOP_FP_SFPV/Existing_Flood_Risk_Map/FeatureServer/5 (retrieved 24 Sep 2026 07:52). Both are TWDB-family publications, and the TWDB site policy reads: "The Texas Water Development Board freely grants permission to copy and distribute its materials." (https://www.twdb.texas.gov/policies/site/, read 26 Sep 2026).
- Overture Maps release 2026-08-19.0 (ODbL): the challenge's own south-central-tx roads file, plus, for one check, the service and track classes that file leaves out (s3://overturemaps-us-west-2/release/2026-08-19.0/theme=transportation/type=segment/, read 24 Sep 2026). Road flag values from the Overture schema, https://github.com/OvertureMaps/schema/blob/main/schema/transportation/segment.yaml (read 26 Sep 2026).
- OpenStreetMap Texas extract (ODbL), replication timestamp 23 Sep 2026 00:03 UTC, sequence 7298377, from the openstreetmap.fr mirror: https://download.openstreetmap.fr/extracts/north-america/us-south/texas.osm.pbf (downloaded 24 Sep 2026).
- Census 2020 block counts of residents and homes, https://tigerweb.geo.census.gov/arcgis/rest/services/TIGERweb/tigerWMS_Census2020/MapServer/10 (queried at run time; last run 26 Sep 2026; public domain).
- USGS orthoimagery from The National Map, for the imagery check in section D2.7: https://basemap.nationalmap.gov/arcgis/rest/services/USGSImageryOnly/MapServer (the 164 audit images rendered 25 Sep 2026; public domain).
- NOAA NCEI Storm Events Database, bulk files 1996 to 2025 (details, fatalities, locations), https://www.ncei.noaa.gov/pub/data/swdi/stormevents/csvfiles/ (retrieved 26 Sep 2026 00:51 to 00:53; public domain).
- From the challenge bucket: tract polygons and strata, Overture roads, Microsoft building footprints and TIGER roads, retrieved 13 to 24 Sep 2026. On 25 Sep the organisers removed the TIGER, Microsoft, HIFLD and CBP layers from the bucket; the repository records the size and sha256 of every challenge file it read and runs from local copies (section D5).

D2.2 The road is on the map. After dropping 181 pedestrian crossings and treating a TWDB point within 50 m of a TxGIO point as the same crossing, 8,454 crossings fall inside the scored tracts. 7,868 (93.1%) have an Overture segment within 30 m. Where the inventory names the road, 6,236 of 7,375 (84.6%) match an Overture segment with the same name or route number, at a median distance of 2.5 m.

D2.3 What the road flags say. The Overture schema lists seven road flags: is_bridge, is_link, is_tunnel, is_under_construction, is_abandoned, is_covered and is_indoor. None can say "ford" or "floods". Of the 7,940 crossings matched to a segment, 69.9% sit on a segment with no flag and 30.1% on one flagged as a bridge, including 21.2% of the vented fords and 9.8% of the unvented ones. Where a ford carries the bridge flag, either the inventory is out of date or the map is wrong, and in both cases a router is told "bridge" and nothing about water.

D2.4 OpenStreetMap tags a few crossings, and Overture drops the tag. The Texas extract holds 18,838 elements tagged ford, flood_prone=yes or hazard=flood, 97.8% of which predate the release. Only 353 of the 8,454 official crossings (4.2%) have one within 30 m. Where the Overture segment is built from an OSM way with a ford node on it (401 crossings), 385 carry no flag in Overture and 16 are marked as bridges.

D2.5 Where the crossings are. Rural tracts (the strata table's ur_class) hold 5,329 crossings for 3.62 million residents; urban tracts hold 3,123 for 22.14 million. That is 147 against 14 per 100,000 residents, a rate ratio of 10.4 (95% interval 8.6 to 12.7 from a bootstrap over tracts; permutation p below 0.0001, seed 20260926).

D2.6 Flood deaths at these crossings. The NCEI Storm Events Database records 12,981 flash flood and flood events in the region's 185 counties from 1996 to 2025, with 550 deaths. 738 of those reports mention a low-water crossing: 43 deaths, 155 injuries, and 100 reports of rescues or people stranded or trapped. For 1996 to 2019, 58.3% of the region's flood deaths (225 of 386) happened in vehicles, in line with the 58% Han and Sharif (2020) found for the whole state from 1959 to 2019.

Where a report names the road, I matched it to the inventories within the same county, and counted a death only where the report puts it beside the named road. 16 fatal events tie to 16 named crossings in 14 counties, with 20 deaths; 9 of those events pass two or more independent checks, such as the event's coordinates falling within 1 km of the crossing. Overture carries 8 of the 16 crossings as ordinary roads with no flag (11 deaths) and 8 as bridges (9 deaths), and none as a ford. Three examples, all ordinary roads in Overture:

- Burnet County, 21 Oct 2009 (NCEI event 195262): one death at Deer Springs Rd over Spring Creek (TxGIO 2031). In Overture's network that crossing is the only road out of 123 buildings, about 130 residents.
- Tom Green County, 4 Jul 2025 (event 1288511): one death at Coke St over a Concho River tributary (TxGIO 6136), the only mapped road out of 18 buildings.
- Bexar County, 14 Oct 2021 (event 980123): two deaths at Graytown Rd over Martinez Creek (TxGIO 6600).

D2.7 What happens when the crossings close. I split every Overture segment at its connectors, removed the short piece that holds each crossing, and asked which areas were connected to the main network before and are not after. Buildings are the Microsoft footprints, each assigned to its nearest road.

The answer depends on which crossings you trust and which roads count as a way out, so the repository has six versions, from 24,738 to 68,155 buildings. The one I lead with uses the strict list (crossings whose road name matches the map, or unnamed ones within 15 m) on a network that also counts every service lane and farm track as an exit: 37,270 buildings in 739 areas, 7,646 of them behind a single crossing.

Two checks shrink that to what I call the careful set. First, the Census Bureau's TIGER roads, drawn independently of OpenStreetMap: I cut the same crossings in TIGER, and in 230 of the 331 areas large enough to check, TIGER agrees that the area is cut off. Second, a near-miss test drops any area where a road inside passes within 20 m of a road outside other than at a crossing. What survives both is 22,469 buildings in 216 areas, about 26,300 residents in about 11,200 homes, across 162 tracts in 49 counties. 5,549 of those buildings, in 90 areas, sit behind a single crossing.

Then I checked whether the areas are cut off on the ground as well as on the map. A random sample of 40 of the 216 areas (10 from each size quarter, seed 20260926) was read twice, independently, from the same aerial imagery renders. About half could not be settled from imagery, mostly because of tree cover. Where both readings could decide, they agreed on 11 of 12 areas. Among the areas each reading could settle, 55% (95% interval 34% to 74%) in one and 26% (12% to 49%) in the other had no way out except across water. Every dry exit found was a track or drive that neither Overture nor TIGER carries. So 22,469 is what a router or a planning tool built on the map would see. The number of buildings physically cut off is smaller: 5,100 to 14,400 on these two readings, about a fifth to two thirds of it.

D2.8 Who lives there. The residents are mostly rural: 68.9% of those in the careful-set areas live in rural tracts, against 14.1% across the region.

On average, the areas are not poorer or more socially vulnerable than the region. Weighted by residents, they score 0.47 on the CDC social vulnerability index (95% interval 0.40 to 0.54) against 0.57 for the region, and they are not higher on any of its four themes. The difference is in exposure: 0.60 on the climate vulnerability index's extreme-events measure (0.59 to 0.62) against 0.51 for the region, and it holds within rural tracts and within urban tracts.

The counties with the most buildings in the careful set are Hays (3,787), Bexar (2,489), Johnson (2,435), Travis (1,608), Bandera (1,559), Llano (1,361), Medina (1,260) and Comal (1,239).

D2.9 Named places. Each passed both network checks; IDs and coordinates are in the repository.

| County (area) | crossing (inventory ID) | buildings, residents | tract: buildings, SVI, scorecard road gap | Overture says |
|---|---|---|---|---|
| Bexar (979) | Southton Rd twice and Henze Rd, San Antonio River tributaries (TxGIO 7382, 7383, 3448) | 1,865, about 1,230 | 48029141800: 1,342, SVI 0.94, road gap 0.003; 48029141700: 523, SVI 0.75, road gap 0.132 | ordinary road |
| Johnson (623) | County Roads 915 and 915A and Sky Rd, six TWDB records | 475, about 910 | 48251130212: SVI 0.67, road gap 0 | ordinary road |
| Guadalupe (921) | Lake Creek Dr over Long Creek (TxGIO 3530) | 218, about 290 | 48187210606: SVI 0.71, road gap 0.318 | ordinary road |
| Hays (952) | G W Haschke Ln over the Blanco River (TxGIO 3362) | 103, about 80 | 48209010811: SVI 0.77, no road score | bridge |
| Bee (1030) | CR 628 over Silver Creek (TxGIO 1824) | 92, about 120 | 48025950600: SVI 0.71, road gap 0 | ordinary road |
| Kerr (266) | Arrow Head Rd over the Guadalupe South Fork (TxGIO 6708) | 76, about 12 | 48265960301: SVI 0.75, road gap 0.325 | bridge |

The last four each sit behind one crossing. All 162 tracts, with their counts, are in results/ in the repository and in the first reply below.

### D3. Who is affected, and why it matters

Evacuation. If a neighbourhood's only road out crosses a creek, the window to leave closes when the creek rises, before the flood peaks. A plan or an app built on the open map cannot tell which neighbourhoods those are. In south Bexar County, 1,865 buildings across two tracts (social vulnerability 0.94 and 0.75) have every mapped road out crossing a San Antonio River tributary at one of three official crossings. The scorecard gives those tracts road gaps of 0.003 and 0.132.

Dispatch. Some cities do feed live closures to navigation apps: San Antonio's HALT network has more than 190 stations linked to Waze and Google Maps (Sharif and Bose, 2026). Most crossings have nothing like it: in this region 12.7% of the TxGIO crossings have a gauge, 2.0% have advance warning signs, and 53.5% have no recorded signage at all. For those, a warning could only come from the static map, which today says "road" or "bridge". At eight of the sixteen crossings tied to a death in section D2.6, the map says "road" and nothing else.

Relief. After the water drops, teams need to know which communities were cut off. Building that list starts with knowing which communities sit behind a crossing, and at present each county rebuilds it by hand.

These crossings will stay for a long time: Austin monitors 67 of them and upgrades about one every three years, which KUT reported would take more than 200 years at the current pace. Sharif and Bose call for warnings that name the roads and crossings expected to flood, which needs the crossings to be on the map first.

### D4. How this sits next to other entries, and what would close the gap

PIO's entry (35000) shows that Overture carries nearly all of TIGER's highway length. That fits what I find (the road is there), and it is also why this gap is invisible to any comparison of lengths or counts. Other entries ask whether features are present or current, while this one is about an attribute the schema cannot hold and tests what that does to reachability on the network.

Overture: add a ford or low-water-crossing value to road_flags, and carry OSM's ford and flood_prone tags through the conversion. Map data: conflate the two Texas inventories, which the TWDB allows anyone to copy, into OSM or straight into Overture. The scorecard: add an attribute check for flood-prone regions, such as the flood crossing gap in section D1, which is 1.000 everywhere in Texas today.

### D5. Reproducing it

discovery/run_all.sh runs every step. On a 2-core, 8 GB machine it took 21 minutes from local copies on 26 Sep (1,278 s, Census block queries included, plus about 4 minutes for the Overture download), and a clean rerun from an empty folder reproduced every network and count figure above (hashes in TESTING.md). fetch_lwc.py pulls both inventories from their public endpoints (no key, no login) and logs retrieval time and sha256; ncei_events.py does the same for the NOAA files.

Two inputs have changed since I ran it. First, on 25 Sep the organisers removed the Microsoft footprints and TIGER roads from the challenge bucket, so the scripts take a --data-dir pointing at local copies and check each file against INPUTS_MANIFEST.csv; the originals are public from Microsoft (GlobalMLBuildingFootprints on GitHub) and the Census Bureau (TIGER/Line 2025). Second, Overture will retire release 2026-08-19.0, so the repository also ships the results as tables: every crossing with its segment, distance, name match, flags and any OSM tag, and every cut-off area with its buildings, residents, TIGER verdict and near-miss flag. Tables derived from Overture and OpenStreetMap are shared under ODbL; strata values are joined locally by a script rather than shipped.

### D6. Limits

Both lists have gaps and stale entries, and I use them as found. A crossing is matched to the map by distance and name. Closing every crossing at once is a worst case, which is why I report the single-crossing numbers separately. Buildings are footprints, not homes; residents and homes are estimates from Census blocks. The imagery check shows that many areas have an unmapped track out, which is itself a gap in both maps, but I do not count those areas as physically cut off. The death matches are my reading of the reports under fixed rules, so they are a lower bound. Only Texas publishes an inventory in this challenge, so the other three regions are unmeasured, although the schema gap applies everywhere.

## Sources

Data sources, each with its URL: Part 1, section 3 and the note on the four layers that left the bucket; Part 2, section D2.1. Other entrants' posts used in Part 1 are credited in its section 11. Cited in Part 2: TxGIO Low Water Crossing MapServer layer 0; TWDB State Flood Plan Existing Flood Risk layer 5; TWDB site policy; Overture schema, transportation/segment.yaml; NOAA NCEI Storm Events Database; Han, Z. and Sharif, H. O. (2020), Vehicle-Related Flood Fatalities in Texas, 1959-2019, Water 12(10), 2884, doi:10.3390/w12102884; Sharif, H. O. and Bose, A. R. (2026), Flash flood mortality in Texas' flash flood alley, Frontiers in Water, doi:10.3389/frwa.2026.1832344; Bernier, N. (16 July 2025), Fixing Austin's low-water crossings would take 200 years at the current pace, KUT.

## Updates

Anything I change after posting is listed here with its date.

## Appendices to Part 1

Paths in these appendices are relative to the folder documentation/.

### Appendix A. Notes behind the table lines of sections 6 and 7

Each line is rebuilt by `sensitivity.py` or, for the lines marked *, by `tools/extra_variants.py`; `out/sensitivity.csv`
and `out/sensitivity_v4.csv` hold the exact values, and `tools/scorecard_ratios.py` the scorecard ratios under each.

- **Whole segment to its midpoint's tract.** Fails the README counts: 368, 475, 1,330 and 3,603 tracts with no road
  component, against 218, 253, 869 and 1,704 (Luca925, thread 34925, reports the same 150 extra in northern-ca).
  On the named highways the scorecard compares, it removes the road component from 2,732 more tracts and moves the
  road gap by more than 0.05 in 2,186 of the 3,603 tracts where both rules define it (61 percent), lower in 40 percent
  and higher in 29 percent.
- **Split in lon/lat.** The segments are split against the tract polygons in longitude and latitude and only then
  measured, in EPSG:5070 or geodesically; either way the pieces differ from a split made after projection.
- **Overture tertiary, TIGER ramps.** The board scored them 0.024547438 and 0.003911991, within 4 percent of their mean
  absolute change (0.0244 and 0.00377), while their root mean square changes are 2.4 and 3.2 times larger.
- **TIGER byte-identical geometries.** TIGER stores a road carrying two route numbers once per number: 8.8, 10.1, 6.9
  and 7.1 percent of named-highway length in northern-ca, eastern-ok, maricopa-az and south-central-tx, the shares
  de-coder (thread 34744) found first. NickyGuants (thread 34962) scored dropping them at 0.0024. The 129 records that
  also repeat LINEARID (0, 84, 11 and 34 by region) move 73 tracts by up to 0.120, the figures Pricilegangbe
  (thread 34992) reports; that board score was 0.000097625.
- **Source CRS named EPSG:4326.** pyproj 3.7.2 picks the same operation for both spellings (an axis swap, the inverse
  of NAD83 to WGS 84 (1), then Conus Albers), and all 9,462,710 projected coordinates of the tract polygons and named
  highways agree bit for bit. DuckDB 1.5.5 does not: with `ST_Transform(..., always_xy := true)` the Austin point of
  `tools/fingerprint.py` reads northing 800570.8529844111 when the source is named EPSG:4326 and 800570.2605298761
  when it is named OGC:CRS84, a shift of 0.93 m, as Pricilegangbe and Luca925 found; Pricilegangbe's board scored the
  OGC:CRS84 build 0.000003691.
- **DuckDB spatial instead of GEOS (the + line).** A one-off check on 14 September, not one of the repository's tools:
  the named highways split against each tract with DuckDB's spatial extension (`ST_Intersection`, both layers
  reprojected with `ST_Transform(geometry, 'EPSG:4326', 'EPSG:5070', always_xy := true)`) give road lengths within a
  relative 1.5e-15 of the GEOS lengths (median 1.4e-16), and the composite moves by at most 3.1e-16, so no tract
  changes at 6 decimal places.
- **Centre of the covering bbox.** The board decided it: see appendix B.
- **Point on surface; composite from components rounded to 6 dp.** The fused multiply-add file scored exactly 0, so
  a variant built on it that moves even one public tract must score above 0. A variant moving k tracts misses the
  public 30 percent entirely with probability about 0.7 to the power k, about 6 in 10^15 for 92 tracts.
- **Centroid taken in EPSG:5070.** `tools/extra_variants.py` projects every footprint to EPSG:5070 and takes the
  centroid there: the count changes in no tract, in all four regions and for both layers.
- **Every footprint touching the tract; a multipolygon counted once per part.** A footprint straddling a boundary counts
  in both tracts; a multipolygon footprint counts once per part, each part by its own centroid. The second is the line
  with the smallest margin over the magnitude test: 0.0000235 against 0.00000602, a factor of 3.9.
- **within instead of intersects for places.** The board decided it: 0.000003874 with within, 0.000003552 with
  intersects, both at full precision. 48 places lie exactly on a boundary in EPSG:5070 (2, 0, 2 and 44 by region; 42
  touch two tracts and 6 touch three or more), none in a facility category. Other entrants count 124 places in 110
  tracts (NickyGuants), 66 in 59 tracts (Yanard) and 58 places (Luca925), with other builds of the points.
- **A boundary place counted once, in the lower GEOID.** Only 2 tracts move, too few for my board to see; NickyGuants
  (0.000003258) and Yanard both scored a one-tract rule worse than counting the place in each tract it touches.
- **Facilities and centroids with intersects.** No USGS facility and none of the 34,860,889 building centroids lies
  exactly on a tract boundary, so the predicate changes nothing; Yanard (thread 34908) showed the bias when the two
  sides of a ratio follow different predicates.
- **Places with no primary category; permanently closed places.** 4 to 6 percent of places per region have no primary
  category. 43,695 places are marked permanently closed (2,926, 4,250, 8,055 and 28,464 by region; NickyGuants counted
  the same 4,250 in eastern-ok). The evaluation page asks for all Overture places, so both stay in.
- **Full precision instead of 6 decimal places.** The board: 0.000003874 at full precision, 0.000003732 at 6 dp.
- **PROJ built with fused multiply-add.** 21 composites change at 6 decimal places, mean 0.0000016, largest 0.0038:
  6 in Lubbock County, 4 in Bexar, 2 each in Caldwell, Dallas and Carter (Oklahoma), one each in Denton, Galveston,
  Hays, Tarrant and Taylor. One of the two Carter tracts, 40019892602, moves by only 0.000008; Luca925 (thread 34925)
  reports one eastern-ok tract in their build. Overture highway length moves by more than a metre in 98 tracts (at most
  291.8 m), TIGER length by at most 0.000000021 m, and two places cross from tract 48113001002 into 48113001101 with no
  effect on any score.
- **Weightings (section 7).** cbp_estab equals cbp_estab_bus in all 9,386 rows of the four CBP files. The uncapped
  ratio's largest change is 356 because one Maricopa tract, 04013422218, has 1,065 Overture buildings against 1
  Microsoft footprint.

### Appendix B. The board path, and the metric

One change per step, each decided by the board:

| Public error | Change from the previous step |
|---:|---|
| 0.000003874 | two-column file (GEOID, coverage_gap_score): split roads, within for places, full precision |
| 0.000003732 | the same values at 6 decimal places |
| 0.000003552 | intersects instead of within for places, full precision |
| 0.00000301 | footprints by true centroid instead of bbox centre, at 6 decimal places: the scored column (1S1Ei46w) |
| 0 | the same file with road lengths from PROJ 9.5.1 built with fused multiply-add (RkEkksFb, 24 September 2026) |

Rounding to 6 decimals removed 0.000000142 of error against a mean rounding change of 0.000000145. That is only
possible if nearly every tract already matched the reference to its stored precision, so whatever error remained had
to sit in a small minority of tracts. The centroid step, taken together with 6 dp output (worth 0.000000142 alone),
moved the score from 0.000003552 to 0.00000301, so the centroid itself accounts for about 0.0000004.

The metric: an all-zeros file scored 0.059806101; my reconstruction has a mean of 0.058437 and a root mean square of
0.106164. A five-column file shaped like the regional sample submission, with transport_gap zeroed and every other
column intact, scored the same 0.059806101: the board reads the second column by position.

### Appendix C. Checking a copy of the inputs

`python pipeline.py --check --data-dir DIR` compares every input's size and sha256 with
[INPUTS_MANIFEST.csv](documentation/INPUTS_MANIFEST.csv) before it builds anything. Past that, these counts, all printed by the
pipeline or recomputable from `out/counts.parquet`, pin the layers down:

| | northern-ca | eastern-ok | maricopa-az | south-central-tx |
|---|---:|---:|---:|---:|
| Overture named-highway segments | 26,050 | 59,436 | 57,516 | 353,790 |
| TIGER named-highway segments | 996 | 5,721 | 1,126 | 11,429 |
| Overture footprints | 1,164,724 | 2,551,694 | 2,908,224 | 11,463,801 |
| Microsoft footprints | 1,138,335 | 2,404,448 | 2,610,544 | 10,619,119 |
| Overture places | 116,897 | 207,369 | 300,046 | 1,300,334 |
| of them with no primary category | 4,795 | 8,494 | 14,746 | 79,103 |

Over the 9,379 scored tracts the building counts sum to the files' row counts, 18,088,443 Overture and 16,772,446
Microsoft footprints, so every footprint's centroid falls in a scored tract. The place counts sum to 1,924,699
assignments: the 1,924,646 places, plus 56 for the 48 places on a boundary counted in every tract they touch, less 3
places in the seven water tracts that are not scored. The road lengths sum to 180,438 km of Overture and 167,920 km of
TIGER named highway (a piece lying on a tract boundary counts in both neighbours), the CBP counts to 899,190.5
establishments, and the USGS layers to 4,628 fire stations, 592 EMS stations and 12,589 schools.

Four failures give no error of their own, and the code handles each:

- GEOID is text. Maricopa is FIPS 04, and an integer read drops the leading zero and breaks every join in that region.
- Axis order. The layers are longitude then latitude; naming EPSG:4326 in some engines flips them and returns infinite
  coordinates. In DuckDB, naming OGC:CRS84 instead avoids the flip but adds the 0.93 m datum shift of appendix A.
- Membership. maricopa-az includes the New Mexico tract 35023970000, and two Oklahoma tracts on the Texas border
  (40013795900 and 40085094200) belong to eastern-ok only. The sample submissions handle both.
- Joins. Counts come from an inner spatial join and are attached back to the scored list by GEOID, so a tract with
  nothing to count keeps its row; Ajitv (thread 34901) shows a DuckDB spatial left join losing exactly those tracts.

### Appendix D. Credits in full

Published by other entrants before the entry, and used or restated in it (UTC dates of the first post):

- 7 Sep, malekarkan (34703): a reconstruction checked against the sample-submission constant.
- 8 Sep, Colossius97130 (34713): a clean-room regeneration of a submitted file, checked by SHA-256.
- 13 Sep, de-coder (34744): TIGER's duplicate geometries (my per-region shares match theirs to the part per million).
- 17 Sep, thibaudlepan (34844): the undefined-share check, conventions measured one at a time, the second-column trap,
  and the uncapped disagreement reversing the tribal ratio.
- 17 Sep, Thelightthatshines (34847): the zero-population average, the two no-land tracts, and a road reading tested
  against the README counts.
- 19 Sep, Ajitv (34901): the DuckDB left join that drops tracts.
- 19 Sep, ALDFX-ML (34903): the pooled tribal ratio inflated by which region the tribal tracts sit in.
- 20 Sep, Yanard (34908): the mean absolute error reading and the twice-the-error rule behind the magnitude test; four
  road readings tested against the README counts; intervals from the sample constants; one predicate on both sides of
  a ratio; no building centroid on a boundary.
- 22 Sep, Luca925 (34925): the midpoint rule's 150 extra undefined tracts in northern-ca, no USGS facility on a
  boundary, and later the OGC:CRS84 effect in DuckDB.
- 23 Sep, NickyGuants (34962): board scores for dropping TIGER duplicates and for one-tract boundary places, and the
  count of closed places.
- 23 Sep, wangwu (34972): the fused multiply-add cause of the plateau, with an exact 0 from arm64.
- 24 Sep, TlT (34980): the checklist of prize text against sections.
- 24 Sep, Pricilegangbe (34992): windows on column sums, the 129 repeated TIGER records, and the Helmert step behind
  OGC:CRS84 in DuckDB.
- 25 Sep, PIO (35000): scorecard ratios with the road component rebuilt.
- 25 Sep, chizzydev250 (35012): the arm64 transport sum my fused build matches.

What I believe is mine, after reading every writeup thread on the board up to 25 September: the reference's arithmetic
on an ordinary Intel or AMD machine, by compiling PROJ with `-mfma` under the standard pyproj wheel in about 2 minutes,
with a `-mno-fma` control that matches the wheel bit for bit (others used ARM hardware, QEMU or an emulation in
Python); the one-point fingerprint that tells which arithmetic an installation has; that x86 build matching a Linux
ARM build to the last digit of the transport sum; the scorecard's ratios recomputed under every variant and read
against each verdict; and every variant's per-tract counts saved beside the scored ones, so the tables and the ratios
rebuild without touching geometry.
