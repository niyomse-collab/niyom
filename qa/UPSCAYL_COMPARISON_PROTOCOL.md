# Upscayl vs NiyomSilp V2.1 — controlled print-quality benchmark

**Purpose:** determine whether Upscayl produces better *actual* Thai lettering, graphics, and transparency than NiyomSilp beta.23 / V2.1. This document does not certify either product and does not import Upscayl source code.

## Sources and license boundary
- Upscayl upstream: https://github.com/upscayl/upscayl
- Upscayl is AGPL-3.0. Keep its source/binaries separate from NiyomSilp; do not copy or link its AGPL components into NiyomSilp without license review.
- Compare using standalone released applications, not embedded integrations. Check each model's license independently.
- Upscayl's documentation says it does **not** restore genuinely out-of-focus or heavily blurred images; do not expect faithful Thai glyph reconstruction.

## Reproducible test matrix
| ID | Input | Modes | What must be inspected |
| --- | --- | --- | --- |
| TH01 | Real Thai sign with detached tone marks/vowels and thin strokes | NiyomSilp beta.23, V2.1 candidate, Upscayl (available model names recorded) | Exact glyph shapes, separated marks, stroke width, halos |
| AL01 | RGBA logo with translucent antialiasing | All three; PNG export | Alpha channel, black/white/red compositing, fringing |
| GF01 | Graphic with straight/curved lines and flat color | All three | Jaggies, color noise, banding, unintended shape changes |
| PH01 | Face/photo with small lettering in background | All three | Face identity, artifacts, accidental text corruption |
| TL01 | Large print banner with fine Thai text | NiyomSilp in-memory vs disk tiles; Upscayl if feasible | Tile seams, peak RAM/VRAM, processing time, exact dimensions |

## Fair comparison protocol
1. Store customer originals and outputs privately. Record SHA256, dimensions, format, ICC, alpha, hardware and model version.
2. Use **the same source crop** for every application and **the same final output pixel dimensions**. Never compare a 4x pass against an 8x two-pass output without normalizing sizes. Document each intermediate upscale and resize.
3. Keep AI scale distinct from requested print size. Record NiyomSilp's selected 2x/4x, and whether any hidden second pass occurred.
4. Save lossless PNG/TIFF; preserve alpha when supported. Do not silently treat flattening as success.
5. Compare side by side in Photoshop at 100%, 200%, 400%; composite transparent assets on black, white and saturated backgrounds.
6. Use image-difference statistics only as diagnostics. More changed pixels, sharper edges or higher DPI metadata are **not** proof of better quality.
7. Require a reviewer to mark each visual criterion PASS/FAIL with annotated screenshots. Any invented/altered Thai glyph or missing diacritic fails.
8. If Photoshop review passes, print controlled vinyl and sticker proofs with the shop RIP/ink/media/ICC; physical sign-off is separate.

## Reporting template
| Sample | Tool / version | Model | Scale | Output pixels | Alpha | Thai glyphs | Edge halos | Flat color | Human verdict |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| TH01 | beta.23 | record | record | record | N/A | NOT TESTED | NOT TESTED | NOT TESTED | NOT TESTED |
| TH01 | V2.1 | record | record | record | N/A | NOT TESTED | NOT TESTED | NOT TESTED | NOT TESTED |
| TH01 | Upscayl | record | record | record | N/A | NOT TESTED | NOT TESTED | NOT TESTED | NOT TESTED |

## Release gates
- No merge/build/release based only on synthetic fixture scores.
- Earlier V2.1 regression failure: https://github.com/niyomse-collab/niyom/actions/runs/40633671129 (`Invalid mode for data type` in a streamed-alpha fixture). Later regression on the V2.1 branch passed: https://github.com/niyomse-collab/niyom/actions/runs/40637387958. The latest V2.1 Windows build and actual-artwork quality are **not** thereby certified.
- Do not touch V1.
- Overall status: **BENCHMARK PLANNED; NOT RUN; NOT PRINT-CERTIFIED**.
