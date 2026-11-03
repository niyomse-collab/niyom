# V2.1.1 effect-text and alpha visual QA gate (research only)

This checklist is a **blocking acceptance contract**, not evidence that V2.1.1 outperforms approved V2. Keep PR #18 Draft; no installer, merge, or release based on green unit CI alone.

## Paired-image protocol
- Use licensed/synthetic or locally held private test art; NEVER upload customer sign art to public GitHub. Five customer examples supplied on 31 Oct 2026 are visual references, not degraded/ground-truth pairs.
- Fix identical input, orientation, crop, color space, scale, final pixel dimensions, and export format for approved V2 and V2.1.1. Include original, V2, candidate, and 100%/400% crops. No post-hoc selective sharpening.
- Record checkpoint hashes, route, tile/pad/overlap, CPU/GPU, elapsed time, source/output dimensions, DPI, ICC profile, and whether face recovery was selected.
- A candidate fails if ANY protected region visibly regresses; metrics alone do not override visual review. Record independent reviewer decisions and failures, not only passing crops.

## Independent failure categories
| Category | Required evidence | Reject when |
| --- | --- | --- |
| Thai/English lettering | paired crops of consonants, vowels, tone marks, small prices, numbers, labels | broken/changed glyph, shifted mark, missing detail |
| Flat fill and contours | RGB/edge crops and line profiles inside ink and along straight/curved outlines | dark speckles in SALE 30, fuzzy edge, false halo, interrupted contour |
| Layered outlines | each stroke and registration at corners and curved edges | stroke merges, changes thickness or leaks into fill |
| Gradient / 3D / gloss | color ramps, highlights, bevel, shadow, reflections | banding, false texture, flattened effects, lost specular highlights |
| Intentional brush grain | rough-brush mask and unchanged artistic texture | intentional roughness smoothed away or new random noise |
| Objects and scenery | natural food/plant/fabric/wood and ice/splash closeups | invented texture, plastic foliage, over-smoothed product |
| Face GFPGAN | selected face eye/nose/lip/skin identity crops, V2 Recover/Studio baseline | altered identity, unnatural eyes/teeth, blurred mouth or face QA bypass |
| Transparent PNG/TIFF | alpha 0/partial/255, composite over black/white/checkerboard, reopened file | opaque background, RGB matte fringe, unexpected alpha shift, TIFF alpha loss |
| Print master | large disk tile seams, DPI/ICC, Photoshop/MainTop reopen, RIP and physical vinyl sample | seam, OOM/corrupt output, profile/size loss, printed defect |

## Technical notes
- Alpha 128 and 255 plateaus are useful regression checks but cannot prove fringe-free edges. Evaluate **partially transparent pixels against contrasting matte backgrounds** and compare against V2; Lanczos changes coverage at contours.
- Exact Unicode/font retyping is an opt-in *plain-text reconstruction experiment*, not effect retention. Never substitute it for existing multicolor/outlined raster lettering in production.
- HAT, source-guided ink, ink geometry, SwinIR and NAFNet remain experimental unless an independent paired evaluation passes; do not silently activate.
- Fail closed before export if selected face recovery or protected QA fails. Do not lower thresholds to green CI.
- 1660 Ti 6 GB: tile/offload/CPU fallback may increase runtime, but no silent quality downgrade; validate large disk-tile output separately.

## Status as of 2026-11-01
Core regression run #41244740739 succeeded for commit 6ac6f42, proving deterministic tests only. Real neural multi-image A/B, fringe inspection, Windows TIFF/Photoshop/MainTop and print acceptance are **not certified** by that result.
