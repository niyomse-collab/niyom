# NiyomSilp V2 — Print Quality Acceptance (PQA) v1

Status: **NOT CERTIFIED** until every mandatory gate has evidence and passes.
Target: `dev/niyomsil-design-v2`, source commit `e696b9e2d1db866c19faef213a0486b741bc9f04`, Windows release `v2-large-images-24` (2026-10-28). This release is V2, **not** an approved V2.1 build.
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
| C01 | CMYK ICC colour management | embedded ICC is readable and has CMYK input space; this does NOT certify colour accuracy | compare printer/ink/media/MainTop RIP ICC with actual vinyl proof |
| C02 | Transparent input exported as CMYK/JPEG | deliberate white-matte flatten is marked opaque export, not an RGBA preservation failure | inspect white-matte borders and print against physical proof |
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
- QA checker (Windows/Ubuntu synthetic, 4f785c4): https://github.com/niyomse-collab/niyom/actions/runs/40651131092
- QA branch core regression (Windows/Ubuntu, 4f785c4): https://github.com/niyomse-collab/niyom/actions/runs/40651131109
- V2.1 Windows candidate (a50aceb): https://github.com/niyomse-collab/niyom/actions/runs/40647828574 — CI build, packaged inference, full installer install/uninstall, and local-payload verification succeeded on 2026-10-28 07:42 UTC. Candidate artifact exists; this is NOT a public release or actual shop/Photoshop print acceptance.
- Existing V2 release: https://github.com/niyomse-collab/niyom/releases/tag/v2-large-images-24
- V2.1 experimental PR: https://github.com/niyomse-collab/niyom/pull/17 (not released or print-certified)
- Actual Photoshop and print proof evidence: **NOT TESTED / NOT SUBMITTED**
- Overall: **NOT CERTIFIED**

## Private print sample observation (2026-10-28)

A user-supplied V2 CMYK TIFF (18,898 × 6,299 pixels, 200 DPI) contains an embedded
**Coated GRACoL 2006 (ISO 12647-2:2004)** CMYK ICC profile (print source is RGBA).
This demonstrates only colour-profile *embedding*, not an ink/media/RIP match.
GRACoL is a generic coated offset press reference, not a calibrated DX11 / MainTop /
Eco Solvent / vinyl device profile. A physical colour proof and a matching printer
media profile are still needed. Private customer images remain excluded from GitHub.

When source PNG has alpha but CMYK TIFF/JPEG is explicitly requested, the export
is an opaque white-matte transformation. QA must show alpha preservation as
NOT_APPLICABLE, not FAIL or PASS. The visual white-matte quality remains NOT_TESTED.

### Automated CMYK black-matte corruption guard

For bounded output rasters with matching source/output aspect ratios, the QA checker now
samples positions well inside zero-alpha source areas. A CMYK print that leaves
high ink density (especially black) at these points **FAILS** rather than being
mistaken for a legitimate white-matte conversion. The guard uses normalized
coordinates and is conservative around antialiased cutout edges.

For very large rasters exceeding the safe full-decode budget, the checker
uses bounded pyvips patch reads when available, otherwise reports
**NOT_TESTED** instead of loading the entire print into memory. The real
18898×6299 CMYK customer sample revealed near-full CMYK ink in transparent input
areas and is known-bad evidence requiring a new V2.1 exported comparison.


## Verified private historical CMYK failure baseline — 2026-10-28

The private customer original and historical V2 CMYK TIFF were inspected locally
using their existing SHA-256 reference. **No customer images were committed to
GitHub.** This is historical V2 evidence and is **not** V2.1 candidate output.

- Transparent input: 2,172 × 724 RGBA; output: 18,898 × 6,299 CMYK TIFF, 200 DPI.
- Embedded output ICC: *Coated GRACoL 2006 (ISO 12647-2:2004)*; not a calibrated
  DX11/MainTop/Eco Solvent/vinyl printer profile.
- 9×9 normalized positions were checked. After excluding positions whose
  nearby source alpha was nonzero, **68 source-zero-alpha positions** remained.
- **61 of 68** (89.7%) contained excessive ink in the prior output according
  to checker thresholds (summed C+M+Y+K >80 or K >40 on 0–255 channels).
  One failed corner held C223 M203 Y184 K249 while source Alpha was 0.
- Historical result: **FAIL**. V2.1 replacement output at the same print size,
  ICC and source remains **NOT_TESTED**.
- A separate experiment converting correctly composited RGB white through
  the *same* embedded profile yielded CMYK (0,0,0,0) at clear source pixels;
  this supports the hidden-RGB hypothesis, but does not prove the updated
  V2.1 installer fixed the original large-size workflow.

Development gates (do not mark print-certified): the exact source must be
re-exported with V2.1 candidate commit a50aceb or newer using the same ICC,
DPI and dimensions; run qa/probe_cmyk_matte.py privately; verify TIFF and
Thai lettering in Photoshop at 100/200/400%; then test on shop media/RIP.
Core regression and packaged smoke success are not substitutes.
