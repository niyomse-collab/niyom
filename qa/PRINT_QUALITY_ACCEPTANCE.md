# NiyomSilp V2 — Print Quality Acceptance (PQA) v1

Status: **NOT CERTIFIED** until every mandatory gate has evidence and passes.
Target: `dev/niyomsil-design-v2`, source commit `aa6e8be4c45ee7051f6f04f109dce28c5815beff`, Windows release `v2-large-images-23`.
This is a QA-only procedure. Do not change V1, face backend, Preview/Zoom or V2 processing code for this document.

## Required evidence
Keep private customer artwork OUT of public GitHub. For each case record:
- case ID, SHA256 of source and output, output format, dimensions, DPI, app version and source commit
- machine, CPU/GPU mode, model and six slider values
- input and output images (private QA storage), Photoshop screenshots at 100%, 200%, 400%, observed defects
- reviewer, date, PASS/FAIL and reason
- for production trials: printer/RIP/media/ink settings, ICC profile, photos and physical inspection

## Mandatory gates
| ID | Scenario | Objective acceptance | Human check |
| --- | --- | --- | --- |
| A01 | PNG RGBA memory and disk tiles | output remains RGBA; alpha 0, partial and 255 survive; no unintended opaque pixels | Photoshop checkerboard; composite on white, black and saturated background |
| A02 | TIFF RGBA memory and disk tiles | valid TIFF alpha and DPI metadata; Photoshop shows transparent regions | no black/white background |
| A03 | Alpha fringe | no unexpected opaque border; transparent-edge RGB safe for compositing | inspect contrasting backgrounds at 100/200/400% |
| G01 | Straight, diagonal and curved graphic edges | no missing strokes, doubled edges or obvious halo | side-by-side source/output and printed proof |
| G02 | Flat-color and gradients | no unexpected banding, noise, discoloration or tile seams | Photoshop inspection and printed proof |
| T01 | Thai typography incl. detached vowels/tones | no lost, merged, displaced or substituted glyphs | 100/200/400% review, exact text comparison |
| S01–S06 | denoise, flat_smoothing, text_graphic_boost, sharpness, contrast, saturation | each control at 0 is exact bypass for that control; 100 changes intended pixels; no alpha mutation | check each slider independently in memory and disk tiles |
| F01 | Face Protect / Recover | original identity and face proportions maintained; selected regions respected | human portrait review on actual Windows hardware |
| U01 | Preview / Zoom | preview position, crop and zoom remain correct; exported file corresponds to preview | real Windows GUI walkthrough |
| L01 | Large vinyl 200x70 cm and 700x40 cm at 300 PPI | exact pixel dimensions within rounding; no crash, blank padding or tile seam; actual file opens | Photoshop and print inspection |
| W01 | Windows installer and public release | CI source commit matches release; install, packaged processing, uninstall and real public download pass | install on shop GTX 1660 Ti; CPU/GPU/Auto tested |
| P01 | Vinyl and sticker print proofs | no objectionable visible artifacts at intended viewing distance; color judged against agreed proof and calibrated workflow | physical sign-off by shop owner |

## Test procedure
1. Capture source SHA256 and version. Use a reproducible fixture set, plus privately stored real signage/portrait samples.
2. Run existing `pytest` regression suite on Windows and Ubuntu; archive logs. Synthetic/mocked tests are **not** sufficient for real-world approval.
3. Process each fixture with both in-memory and disk-tile routes where applicable. Test all six sliders individually at 0 and 100, then representative mixed settings. Keep input and output.
4. Compare PNG/TIFF in Photoshop at 100%, 200%, 400% and on contrasting backgrounds; record all defects, including Thai vowels and tone marks.
5. Verify real face enhancement, Preview/Zoom, GPU selection and large print sizes on the shop's GTX 1660 Ti.
6. Produce vinyl and sticker proofs using the actual RIP/printer/media/ink/ICC combination. Record print inspection.
7. Mark every gate PASS only with links to evidence. If missing, mark NOT TESTED, never PASS.

## Certification rule
`CERTIFIED` only if **every mandatory gate** is PASS, with a dated human sign-off for F01, U01 and P01 and a successful Windows release/download test on the exact candidate commit. A single FAIL or NOT TESTED makes overall status `NOT CERTIFIED`. CI success alone means `AUTOMATED TESTS PASSED`, not print certification.

## Current baseline
- Existing automated regression: https://github.com/niyomse-collab/niyom/actions/runs/40604326997
- Windows build and public download verification: https://github.com/niyomse-collab/niyom/actions/runs/40604326998
- Candidate release: https://github.com/niyomse-collab/niyom/releases/tag/v2-large-images-23
- Actual Photoshop and print proof evidence: **NOT TESTED / NOT SUBMITTED**
- Overall: **NOT CERTIFIED**
