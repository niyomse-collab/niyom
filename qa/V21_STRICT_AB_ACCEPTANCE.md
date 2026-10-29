# V2.1 strict A/B print and face acceptance — blocking protocol

Status: **BLOCKED / NOT CERTIFIED** until every gate below has evidence from the **exact** V2.1 candidate commit. This is a QA-only protocol; no application, V1, V2 baseline, release, or installer changes are authorized by this document.

## Controlled comparisons (V2 is the quality floor)

For every case, retain the same private original, source SHA-256, exact final pixel dimensions, DPI, output file format, alpha handling, colour mode and ICC profile, print-media/RIP settings, and inspection zoom. Record both executable/source commits, RealESRGAN model hashes, optional Graphic AI state, face mode, all six slider values, processing route (memory/disk tiles), hardware, and processing time.

Run **accepted V2**, **V2.1 default RealESRGAN** and **V2.1 Graphic AI explicitly enabled** as separate outputs. Do not substitute Lanczos, synthetic-only tests, or benchmark numbers for the accepted V2 output. Keep the default model unchanged unless real A/B evidence and license review support a later decision.

Use representative **private real signage**: large and small Thai text with isolated upper/lower vowels and tone marks, straight/diagonal/curved strokes, high-contrast outlines, gradients, solid fill interiors, photographs, real faces, and RGBA cutouts. Include at least one large disk-tiled export and one normal in-memory export. Store all customer artwork, crops, comparison sheets and Photoshop screenshots privately, **never in public GitHub**.

## Required per-case evidence

Record source/output SHA-256, coordinates of identical ROIs, side-by-side pixel-aligned crops at 100%, 200%, 400%, reviewer/date, V2/V2.1 settings and model IDs, plus quantitative diagnostics and a signed visual verdict. Use consistent masks and regions, and avoid comparing differently scaled or differently colour-managed outputs.

| Gate | Mandatory comparison / acceptance |
| --- | --- |
| AB01 Thai text | Exact glyph inventory and spelling, including detached vowels/tone marks, dots and small strokes. No missing, shifted, fused or invented mark. V2.1 must be no worse than V2; report actual defects and positions. |
| AB02 Edges | Compare text edge width/continuity, straight-line deviation, curved-line continuity, corners and object boundaries in aligned ROIs. No new halos, ringing, double edges, jagged strokes or warped objects versus V2. |
| AB03 Letter interiors | Measure grain/residual only in manually verified uniform ink ROIs, excluding intentional textures. Inspect speckle, pinholes and uneven solid fills. V2.1 must not increase visible grain or alter intended colour. |
| AB04 Flat fills/gradients | Compare banding, hue shifts, ICC-managed colour, seams and clipping on the same original. No loss of smooth gradients or flattening of photographs. |
| AB05 Sliders | Independently sweep **all six sliders** at 0/25/50/75/100; record output hashes, ROI pixel deltas and visual response. Zero must bypass the *corresponding* effect, while nonzero steps must cause meaningful, bounded, correctly targeted changes; no alpha mutation or unchanged output from a supposedly active slider. Repeat representative cases with memory and disk tiles. |
| AB06 Face Protect | Real faces must keep original eye, mouth, nose, proportions, identity cues and fine detail; no unnecessary new face generation. Confirm selected face regions and unchanged unselected regions. |
| AB07 Face Recover | Compare with V2 and original at each relevant strength. Reject eye/mouth distortion, excessive smoothing, invented features, colour drift and lost details; fallback to original/upscaled pixels when unsafe. |
| AB08 Studio AI | Verify selected-region-only changes, no unrequested reconstruction, no new identity or broken facial anatomy. Verify Protect/Recover/Studio AI on actual Windows GPU and CPU fallback. |
| AB09 PNG/TIFF | Test transparent, semitransparent and opaque pixels; compare alpha, fringe on white/black/saturated backgrounds, TIFF DPI/ICC and exact exported dimensions. Distinguish deliberately flattened CMYK/JPEG white-matte from RGBA preservation. |
| AB10 Large image | Verify exact print dimensions, bounded memory/disk tiles, seams, cancellation/retry, previews/zoom vs final export, and no white padding or unexpectedly opaque borders. |
| AB11 Packaging | Windows Candidate must be built from the **same commit** as the tested output; verify packaged real inference, install/uninstall, clean-machine dependencies and artifacts. CI success alone is not quality certification. |
| AB12 Physical print | Inspect Photoshop at 100/200/400%, then actual DX11/MainTop/ink/media-specific ICC proof and vinyl/sticker print. Record colour, defects, viewing distance and shop-owner sign-off. Generic GRACoL ICC is not a calibrated vinyl profile. |
| AB13 Licensing | Record provenance, model weight licenses, code licenses and redistribution obligations before using external models or code. Do not copy Upscayl AGPL code or replace RealESRGAN merely because of a benchmark. |

## Decision rules

- **BLOCKED** if any gate is FAIL, missing evidence, NOT TESTED, unverifiable, or shows a quality regression relative to accepted V2. Never promote a synthetic-only PASS to production certification.
- **A/B improvement verified** requires (1) no material regression on any mandatory real-image case and (2) a documented, visually verified improvement in at least one shop-relevant quality dimension with matched settings. A larger sharpness score alone is not improvement.
- Face modes are **hard-stop gates**: any visibly damaged eyes/mouth, altered proportions, identity drift, artificial new face, or lost facial detail is a FAIL even if average image metrics improve.
- The 0/25/50/75/100 sweep must show the per-control bypass and an actual, bounded effect at nonzero settings. If a control is inert, mark FAIL; if the test cannot isolate it, mark NOT TESTED.
- Photoshop, MainTop/ICC and physical print are separate evidence gates. Never claim they passed from CI logs, mocks, or synthetic fixtures.
- **CERTIFIED** only after all gates pass on the exact candidate commit, private evidence is archived, and a dated human sign-off is recorded. Until then keep both PRs Draft; do not merge into dev/main, publish a release or offer the installer for production download.

## Evidence ledger (fill privately; metadata-only summaries may go to GitHub)

| Case ID | Original SHA-256 | V2 commit / output SHA | V2.1 commit / output SHA | Mode / six sliders | Real A/B verdict | Photoshop | Print | Face verdict | Overall |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Pending | NOT SUBMITTED | NOT TESTED | NOT TESTED | NOT TESTED | BLOCKED | NOT TESTED | NOT TESTED | NOT TESTED | BLOCKED |

Current historical V2 CMYK black-matte failure is documented in `qa/PRINT_QUALITY_ACCEPTANCE.md`; it is **not** evidence of a fresh V2.1 fix. Follow `qa/COMPARE_V2_V21.md` for bounded ROI screening and never treat its synthetic/automated metrics as final acceptance.
