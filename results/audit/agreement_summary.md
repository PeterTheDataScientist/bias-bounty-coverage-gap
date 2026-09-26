# Imagery audit: agreement between two raters

Texas low-water crossing areas, v4 careful set, 40 sampled areas (10 per building-count quartile, seed 20260926). Written 26 Sep 2026.

## Inputs and independence

- Rater 1: `figs_audit/audit_verdicts.csv` (read only, not changed; sha256 `36dcc65bcbc1ba60325841f0a4e9d3f1029210b2662410fa4fac991d906eb89a`).
- Rater 2: `figs_audit/second_rater.csv`, saved before rater 1's file was opened. Rater 2 did not open any file with 'verdict' in its name, `v4_audit_summary.json`, `EVIDENCE_v4.md` or `audit_summary.py` before saving.
- Rater 2 looked at all 164 images in `figs_audit/`. These include rater 1's 24 `extra_c*.jpg` close-ups, so rater 2 could see where rater 1 had looked more closely, though not what rater 1 decided. Rater 2 also rendered about 150 further close-ups from the same USGS imagery and the same `v4_audit_prep.parquet` layers into a scratch folder outside the project.
- Label mapping for rater 1: `isolated` = ISOLATED, `exit_is_a_ford` = EXIT_FORD, `exit_visible` = EXIT_UNMAPPED, `cannot_tell` = UNSETTLED.
- Rater 2 applied the strict rule. EXIT_UNMAPPED only where a continuous route out could be traced. ISOLATED only where the whole boundary was visible and no route crossed it. Everything else was UNSETTLED.

## Agreement

- Four classes, all 40 areas: 24/40 = 60.0% agreement; Cohen's kappa = 0.366 (chance agreement 0.369).
- Binary (ISOLATED or EXIT_FORD versus EXIT_UNMAPPED), the 12 areas both raters settled: 11/12 = 91.7% agreement; Cohen's kappa = 0.824 (chance agreement 0.528).
- 15 of the 16 disagreements are about whether the imagery settles the area at all; only one (area 534) is a disagreement between two settled verdicts.
- Direction of the settleability splits:
    - Rater 1 called 6 areas isolated or ford that rater 2 left unsettled (876, 919, 654, 893, 391, 979).
    - Rater 2 traced exits in 6 areas that rater 1 left unsettled (911, 427, 642, 730, 68, 721), and called one isolated (790).
    - Rater 1 traced exits in 2 areas that rater 2 left unsettled (792, 52).

Four-class confusion matrix (rows rater 1, columns rater 2):

| rater 1 \ rater 2 | ISOLATED | EXIT_FORD | EXIT_UNMAPPED | UNSETTLED | total |
|---|---|---|---|---|---|
| ISOLATED | 4 | 0 | 0 | 5 | 9 |
| EXIT_FORD | 0 | 0 | 1 | 1 | 2 |
| EXIT_UNMAPPED | 0 | 0 | 7 | 2 | 9 |
| UNSETTLED | 1 | 0 | 6 | 13 | 20 |
| total | 5 | 0 | 14 | 21 | 40 |

## Precision (isolated or ford-only among settled areas)

| basis | isolated or ford | settled | precision | Wilson 95% interval |
|---|---|---|---|---|
| (a) rater 1 | 11 | 20 | 55.0% | 34.2% to 74.2% |
| (b) rater 2 | 5 | 19 | 26.3% | 11.8% to 48.8% |
| (c) consensus: both settled and agree | 4 | 11 | 36.4% | 15.2% to 64.6% |

Notes on these figures:

- The sample is self-weighting: each of the 216 areas had a 10/54 chance of selection. So the unweighted shares estimate area-level precision, but only among areas the imagery can settle.
- Settled areas need not be a random subset: whether imagery can settle an area depends on canopy and landscape. Rater 1 settled 20 and rater 2 settled 19. The unsettled rate is similar in every size quartile: rater 1 left 6, 4, 6, 4 of 10 unsettled, rater 2 left 6, 5, 5, 5.
- Among settled areas, the raters differ most in the largest quartile. Isolated or ford by quartile: rater 1 had 1 of 4, 3 of 6, 3 of 4, 4 of 6; rater 2 had 1 of 4, 2 of 5, 1 of 5, 1 of 5.
- The consensus set holds four isolated areas (583, 685, 627, 968) and seven with a visible dry exit (94, 855, 89, 301, 431, 959, 414).

## Every disagreement, with both reasons

| k | area | rater 1 | rater 1 reason | rater 2 | rater 2 reason |
|---|---|---|---|---|---|
| 5 | 792 | EXIT_UNMAPPED | Pasture two-track runs about 240 m to the bend of a mapped road on the same side of the creek | UNSETTLED | A pasture track reaches an arena 30 to 60 m from a white road's driveway, and a creek-bank track from a compound on the area side ends 100 m from an unmapped street; both last links cross open yards with no visible path. |
| 8 | 911 | UNSETTLED | Paddock track and field-edge lane toward a mapped road end; no continuous track | EXIT_UNMAPPED | Yard east of the houses joins an oval track and a field-edge lane running about 500 m south and south-east to the house at a white road's north end; clear of the creek at the crossing. |
| 16 | 790 | UNSETTLED | Street stub ends 58 m from a mapped loop across a tree line | ISOLATED | Only road out is over the marked crossing; the 58 m stub and a field road to the south end at yards and a tree line with no drive through. |
| 17 | 876 | ISOLATED | All three roads out cross at official crossings; woods field and riverbank otherwise | UNSETTLED | A field-edge track from the frontage road ends 20 to 30 m from the westmost yards behind an unbroken hedgerow; any link is hidden under trees. |
| 19 | 919 | ISOLATED | Road between two crossings; open field and scrub with no drive | UNSETTLED | A ranch track runs about 550 m north from the north-west cluster to a tree line beside a farmstead at a white road's end; the last 50 m is under brush. |
| 20 | 427 | UNSETTLED | Lane end 64 m from a mapped road end near houses; possible drive | EXIT_UNMAPPED | The cleared power-line corridor the cyan road follows carries on about 110 m past the road's mapped end to a white road; upland scrub, no watercourse. |
| 24 | 642 | UNSETTLED | Streets end 75 to 130 m from a mapped loop; drives and yards between | EXIT_UNMAPPED | Gravel drive runs from the southern east street's end yard past a barn onto an apron meeting the white loop road about 90 m away; no watercourse. |
| 25 | 654 | ISOLATED | Road between two crossings; forest and pasture with no track | UNSETTLED | A farm compound at a white road's end has sheds 40 m above the north-east branch behind a tree line; a possible path there is not clear, other sides dense woods. |
| 26 | 730 | UNSETTLED | Park corner is 50 m of grass from a mapped lane; tracks to the E not traceable | EXIT_UNMAPPED | Dirt tracks run north from the east houses along the pond dam and the creek's west bank to a dirt road ending at a building on the white U-road; no creek crossed. |
| 27 | 893 | ISOLATED | Woodland between houses on all sides; no drive or track | UNSETTLED | Long subdivision in dense juniper; main-road driveways end 90 to 220 m from the south branches through woods with no visible track. |
| 30 | 52 | EXIT_UNMAPPED | Graded dirt road about 300 m SE to the end of a mapped road | UNSETTLED | Large ranch area; a track from a cyan loop ends about 45 m from a white road end across a fence line, and the dense track web cannot be traced. |
| 32 | 68 | UNSETTLED | Ranch subdivision; dirt roads on both sides of a riparian strip but no visible link | EXIT_UNMAPPED | Dirt track runs about 250 m from a cyan road end round the west end of a wooded band and through scrub onto a white road's track; no channel seen. |
| 33 | 391 | ISOLATED | River meander and creek; every approach crosses the streams the crossings span | UNSETTLED | Long strip; the three nearest approaches cross water, and the east side's web of unmapped tracks cannot be traced end to end. |
| 36 | 534 | EXIT_FORD | Road ford across the Brazos main stem (in TIGER only; not in either inventory) to a mapped road; it floods too | EXIT_UNMAPPED | Dirt ranch road runs about 850 m south from a white road's corner, past a stock pond and along a wooded draw, to houses at the end of a cyan spur; no water crossed. |
| 37 | 721 | UNSETTLED | Lane ends 82 m from a mapped road end across an estate yard | EXIT_UNMAPPED | Gravel driveway runs about 80 m from the white road's west end past a house to the yard where the north cyan road ends; open pasture, no water. |
| 39 | 979 | EXIT_FORD | Unmapped two-track along a cleared corridor to the E fords a creek at grade before reaching the main road | UNSETTLED | Huge area; a cleared utility corridor to the frontage road crosses the mouth of a wooded draw on a bare silt bed and may not be a road, and the rest of the boundary is not verifiable. |

Rater 2 note on area 534, the only disagreement between two settled verdicts: rater 2 also saw the river ford in TIGER at the north-east that rater 1 describes. Rater 2 judged the dry ranch road from a mapped road's corner to the end of a cyan spur to be the deciding exit. A third look at that road, and at whether it crosses the stock pond's draw, would settle this area.
