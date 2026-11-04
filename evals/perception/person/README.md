# INP-20 person-gate calibration

INP-20 discards a photo that shows a person before anything is cropped, read, stored or sent. This folder records how
the gate in `services/perception-worker/perception_worker/image.py` was chosen and what it measures. It is development
calibration, not ordinary-camera release evidence (`release_evidence: false`).

## Set (`set.json`, version 2026-10-23.1)

| Group | Items | Source and licence |
| --- | --- | --- |
| People photos | 500 | Open Images validation photos with a human-verified, real (non-depiction) Person/Man/Woman/Boy/Girl/Human face box, sampled by the largest box's share of the frame: 160 large (≥25%), 160 medium (5–25%), 120 small (1–5%), 60 tiny (<1%). CC BY 2.0; author, title and Flickr page per item. |
| Photographed pages | 118 | Open Images validation photos labelled handwriting/document/writing/diagram/whiteboard/blackboard etc., with no human box or human image label, then reviewed by eye: documents, notes, receipts, forms, boards, charts, plans and drawings. 53 candidates were excluded as objects, screens or depictions of people (banknote portraits, pictograms, cartoons). CC BY 2.0. |
| Synthetic worksheets | 862 | Owned pages rendered by `jana_tools.person_calibration render`: 31 typefaces (Pillow's bundled font, Liberation Sans as an Arial stand-in, serif, mono, and 11 handwriting faces) at 20–110 px, landscape and portrait, ruled paper, camera-style desk photos and 12-megapixel phone frames, and 120 diagrams including tall upright apparatus. Fonts are pinned by SHA-256. |
| Regression worksheets | 29 | `evals/perception/regression` (owned). |

Photos are fetched by id and verified by SHA-256; they are never committed. Page labels were reviewed in the
implementation session only; an independent review is still needed.

## Result (`runs/2026-10-23/report.json`, per-item `observations.jsonl`)

Refused photos at each rule, OpenCV 4.14.0 on Linux x86-64:

| Rule | People (500) | Photographed pages (118) | Synthetic (862) | Regression (29) |
| --- | --- | --- | --- | --- |
| Retired: Haar face/body cascades + HOG people detector (any box) | 340 | 49 | 404 | 0 |
| Retired, HOG min weight 0.4 | 334 | 47 | 387 | 0 |
| Retired, HOG min weight 1.0 | 304 | 38 | 281 | 0 |
| Retired, HOG min weight 2.0 | 284 | 29 | 136 | 0 |
| Retired, Haar only (HOG off) | 278 | 28 | 115 | 0 |
| YuNet face score ≥ 0.4 | 411 | 5 | 1 | 0 |
| YuNet ≥ 0.5 | 380 | 3 | 0 | 0 |
| **YuNet ≥ 0.6 (chosen)** | **347** | **1** | **0** | **0** |
| YuNet ≥ 0.7 | 319 | 1 | 0 | 0 |
| YuNet ≥ 0.8 | 275 | 0 | 0 | 0 |

The requested HOG threshold does not exist. HOG fired on 26 of the photographed pages with weights 0.21–2.45 and on
rendered text in all 31 typefaces with weights up to 3.47 (14 of the 22 pages in Pillow's bundled font), while a minimum
weight of 0.4 already lets 6 refused people photos through. Only a weight that switches HOG off passes every page, and the Haar upper/full-body
cascades still refused 28 photographed pages and 115 rendered ones.

Decision (2026-10-23, the project owner in the implementation session; formal product-owner sign-off pending): replace the stack with the
YuNet face detector at score ≥ 0.6, input long edge 1,200 px. By stratum it refuses 130/160 large, 109/160 medium,
83/120 small and 25/60 tiny people photos. 71 photos the retired stack refused now pass and 78 it passed are now
refused. It sees faces only: people photographed from behind or too small to show a face are not refused, which the
retired stack also missed for 160 of these 500 photos. The one refused page is a chalk drawing of an elephant (0.71).
0.5 would refuse 33 more people photos and 2 more pages; that choice belongs to the product owner.

## jana-meta, 3 November 2026 (owner approved 0.4)

jana-meta was started from a copy made before the decision above, so it still ran the retired stack. This branch brings
the gate over at **score >= 0.4**, not 0.6, because the owner's rule for this control is that it must not miss more
people. The people and page counts above were not re-measured; they are computed from `runs/2026-10-23/observations.jsonl`.

| Rule | People refused (500) | Refused before, not now | Not refused before, refused now | Photographed pages (118) | Synthetic (862) | Regression (29) |
| --- | --- | --- | --- | --- | --- | --- |
| Current: any Haar or HOG | 340 | | | 49 | 404 | 0 |
| HOG off | 278 | 62 | 0 | 28 | 115 | 0 |
| Agreement, 2 of the 5 detectors | 145 | 195 | 0 | 9 | 48 | 0 |
| Agreement, 3 of the 5 detectors | 51 | 289 | 0 | 0 | 0 | 0 |
| YuNet >= 0.6 | 347 | 71 | 78 | 1 | 0 | 0 |
| YuNet >= 0.5 | 380 | 55 | 95 | 3 | 0 | 0 |
| **YuNet >= 0.4 (approved)** | **411** | **36** | **107** | **5** | **1** | **0** |

By share of the frame (large, medium, small, tiny), the current stack refuses 122/160, 102/160, 80/120, 36/60 and
YuNet >= 0.4 refuses 143/160, 131/160, 100/120, 37/60. At 0.5 the tiny group falls to 31/60 and at 0.6 to 25/60.

Narrowing the current stack only removes refusals, so requiring agreement or skipping HOG always misses more people.
No rule here both keeps every photo the current stack refuses and fixes the false refusals; the union of YuNet and the
current stack refuses 418 people but still 50 and 404 pages. Of the 89 people photos YuNet >= 0.4 misses, the current
stack fires on 36 (40%), about its rate on photographed pages with nobody in them (49/118, 42%). That suggests many of
those 36 are chance firings, but the observations record no boxes, so it is not proven.

The rendered failure is larger than first measured, on macOS arm64 with the same OpenCV (`runs/2026-11-03/report.json`):
the two-line grid (4 fonts, sizes 28-60 in steps of 4, 6 questions) refuses 7/216, and the three-line worksheet at every
size from 28 to 60 refuses 85/132. It is not size alone: Arial 44 with three lines is refused and any two of those lines pass.

Known limits: faces only, so a person seen from behind is not refused; a drawn or printed face can be refused (the page
set excluded depictions of people, so that rate is unmeasured); thresholds were chosen on this set with no held-out
split; Open Images is not student phone photos; hands holding a page were not measured.

## Reproduce

```sh
cd scripts
../.venv/bin/python -m jana_tools.person_calibration fetch WORK      # photos and fonts, hash-checked
../.venv/bin/python -m jana_tools.person_calibration render WORK     # owned synthetic worksheets
../.venv/bin/python -m jana_tools.person_calibration measure WORK ../evals/perception/person/runs/DATE
```

`select METADATA` regenerates the photo lists from the Open Images validation CSVs (kept page reviews are preserved);
`fetch --record` stores the hashes of newly selected photos. System fonts are looked up under `/usr/share/fonts`
(Ubuntu 24.04 packages listed per font). Rendered bytes depend on the FreeType build, so their hashes are recorded per
run in the observations rather than locked.
