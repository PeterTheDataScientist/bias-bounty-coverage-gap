# The imagery audit of the careful set

The careful set is 216 areas, 22,469 buildings, that are left with no mapped road out when the official low-water
crossings close: in Overture's road network, with the Census Bureau's TIGER roads agreeing. The audit asks how many of
them are physically cut off when the creeks rise, not only on the map.

## What was done

A random sample of 40 of the 216 areas, 10 from each quartile of building count (seed 20260926,
`discovery/precision_audit.py sample`), was drawn over USGS orthoimagery with the network cut on top: 164 images, an
overview of each area, 1.5 km tiles of the large ones, close-ups where its roads come nearest the main network, and 24
extra close-ups where a link was in doubt.

The sample was read twice, independently, from the same renders, following the written rules below. The second
reading was saved before the file of the first was opened. It looked at the same 164 images,
the first reading's 24 extra close-ups among them (so it could see where the first reading had looked more closely,
though not what it decided), and it drew about 150 further close-ups of the same imagery and map layers for itself,
which are not kept.

## The written rules

First reading, four verdicts:

- `isolated`: the only mapped or visible ways out cross at the official crossings;
- `exit_is_a_ford`: an unmapped or unlisted way out exists, but it crosses a stream at grade, so it floods too;
- `exit_visible`: a mapped road or a clearly visible track reaches the main network without an official crossing;
- `cannot_tell`: a link is plausible (a driveway, a yard, a two-track, tree cover) but can be neither confirmed nor
  excluded.

Second reading, the same four classes (`ISOLATED`, `EXIT_FORD`, `EXIT_UNMAPPED`, `UNSETTLED`) under a stricter rule:
`EXIT_UNMAPPED` only where a continuous route out could be traced end to end, `ISOLATED` only where the whole boundary
was visible and no route crossed it, everything else `UNSETTLED`.

An area is cut off when its verdict is `isolated` or `exit_is_a_ford` (`ISOLATED` or `EXIT_FORD`): every way out
crosses water.

## What the two readings found

`discovery/audit_agreement.py` recomputes every figure below from the files here (into
`discovery/work/v4_audit_agreement.json`); `discovery/audit_summary.py` adds the first reading's bootstrap intervals.

- About half the areas could not be settled from imagery: 20 of the 40 in the first reading and 21 in the second,
  mostly under tree cover or where tracks cannot be traced end to end.
- Where both readings settled an area, they agreed on 11 of 12 (Cohen's kappa 0.82). Over all 40 areas and the four
  classes they gave the same verdict for 24 (kappa 0.37): 15 of the 16 differences are about whether the imagery
  settles an area at all.
- Among the areas each reading settled, 55% (11 of 20; Wilson 95% interval 34% to 74%) in the first reading and 26% (5
  of 19; 12% to 49%) in the second are cut off when the creeks rise.
- Weighted by size quartile (each quartile's buildings times that quartile's share cut off among the areas settled),
  between 5,067 (second reading) and 14,426 (first reading) of the careful set's 22,469 buildings are behind no dry way
  out.
- Every dry exit either reading found was a track or drive that neither Overture nor TIGER carries (one, in area 427 of
  the second reading, follows a cleared power-line corridor).

So 22,469 is what a router or a planning tool built on the maps would see. The number of buildings physically cut off
is smaller: 5,067 to 14,426 on these two readings. The tracks and drives found are themselves a gap in both maps.

Of the six places the entry names, only area 979 (south Bexar County) is in the sample: the first reading finds a
two-track that fords a creek at grade as its only other way out, and the second could not settle it.

## The files

| File | What it holds |
|---|---|
| `audit_sample.csv` | The sample as `precision_audit.py sample` draws it: order `k`, size quartile `stratum`, area `comp`, `bldg`, `n_cross`, `single_crossing`, Census block `pop_block` and `hu_block`, `GEOID`. Every run checks that it draws exactly this sample |
| `audit_verdicts.csv` | The first reading: each area's verdict, one reason, the area's counts and the `images` the verdict rests on |
| `second_rater.csv` | The second reading: `area_id`, `verdict` and `reason` |
| `agreement_summary.md` | The comparison of the two readings as written on 26 Sep 2026: how each was made, agreement, the confusion matrix, precision, and every disagreement with both reasons. The paths it gives (`figs_audit/...`) are those of the working folder; the two verdict files it compares are the ones here, and it quotes the sha256 of `audit_verdicts.csv` |
| `extra_views.csv` | The 24 extra close-ups the first reading asked for: file name, area, centre (lon, lat) and width in metres |

The area counts come from the discovery's tables (ODbL 1.0); the verdicts and reasons are the readings' own text.

## No imagery is shipped

The imagery stays with its source (USGS The National Map, public domain). To draw the 164 images again, under the
names `audit_verdicts.csv` cites, into `discovery/figs_audit/`:

    cd discovery
    python precision_audit.py prep
    python precision_audit.py render
    python precision_audit.py extras

(`AUDIT_IMAGES=1 bash run_all.sh` does the same after a run.) The extra close-ups are centred on the points shown in
each image's title, which give 5 decimal places, so a redrawn close-up can sit up to about a metre from the original
([../../TESTING.md](../../TESTING.md), section 3).
