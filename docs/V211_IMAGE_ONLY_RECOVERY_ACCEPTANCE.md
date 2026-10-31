# NiyomSilp V2.1.1 — IMAGE-ONLY RESTORATION CONTRACT (31 Oct 2026)

> Owner-approved scope. **Preserve V2; improve V2 image quality, not image content.**
> Applies only to `feature/v2.1.1-super-ai` / Draft PR #18.
> **Not a release or evidence that V2.1.1 currently beats V2.**

## Product behavior — non-negotiable

Input is a flattened RGB/RGBA image from a generative AI or customer. The job is
to reduce blur, colour noise, grain, broken/jagged contours and scaling damage,
then upscale/export for the ordered print size **using the accepted V2 workflow**.

- Keep every original character, digit, diacritic, price, logo, object and design
  effect. This includes Thai, Latin/English, Chinese and any other script.
- **No OCR-based editing, text prediction, retyping, compositing glyphs, flat
  colour text substitution, rewriting prices, or overlaying reconstructed text.**
  The legacy `v211_verified_text_regions` input is now rejected at the
  production adapter boundary *before inference/export*, even if explicitly set.
- Improve blurred strokes as **image edges** only. Preserve each exterior outline,
  stroke-width relationship, layered colour edge, antialiasing, bevel, 3D gloss,
  highlight, shadow, gradient and deliberate soft glow.
- Preserve original identity and realistic detail of faces; use accepted V2
  GFPGAN face path when Recover/Studio AI is selected.
- Real leaves stay leaves, food stays food, glass stays glass, fabric stays fabric.
  No plastic/waxy smoothing, invented veins, spurious detail, changed shape,
  artificial skin or hallucinated products.
- Transparent PNG/TIFF keeps transparency and clean colour at every cutout edge:
  no opaque matte, gray/white/black fringe or blurred/expanded silhouette.
- Preserve approved V1, approved V2 and the independent Offline Text
  Reconstruction project unchanged. No merge/release while quality is worse.

## A/B acceptance matrix — **every category**, no Thai-only focus

| Image input/ROI category | Compare to accepted V2 at same output pixels | Immediate failure |
| --- | --- | --- |
| Small Latin, English and numerals | Blur, counters, thin curves, exact numbers, fine contours | New/missing/merged characters or smeared price |
| Thai, stacked vowel/tone and ornate styles | Original diacritic positions, glyph holes, rounded curves, layered outlines | Changed glyph, detached mark or colour layer |
| Chinese and mixed-script microtext | Dense strokes, internal gaps, diagonal/horizontal detail | Wrong stroke topology or reconstructed meaning |
| 3D/FX text across all scripts | Sharp outer colour boundaries; smooth inner gradients/glow/shadow | Flattened gradients, thick halos, lost bevel |
| Straight/curved graphics, outlines, logos | Geometric continuity and colour separation | Warping, oversharpen, extra contours |
| Portraits, hair, skin | Same person, eyes/nose/lips, real skin texture; face recovery must actually run | Face identity drift, waxy face, skipped recover |
| Foliage, leaves, trees and flowers | Natural venation, branches, believable texture | Plastic/waxy surfaces, invented parts |
| Food, products, water, glass, metal, cloth | Natural material texture and highlight physics | Smoothed plastic food, altered product labels |
| Flat colours, gradients, patterns | Reduced grain without banding or hue shift | Black/blue stains, posterization, smudges |
| Alpha cutouts and fine ornaments | Clean boundary on black/white/red mattes, unchanged transparency | White/black fringe, opacity/background damage |
| Whole scene and large-print tiles | Consistent face/ink/texture and smooth tiles at 2x/4x | Tile seams or mismatched colour/tone |
| PNG/TIFF/PDF / Photoshop / MainTop | Exact requested print pixels, appropriate PPI, ICC and alpha policies | Unsupported or corrupted export |

## Procedure and status

1. **Source:** original real customer/AI raster stored locally/private (never
   pushed to GitHub), accepted V2 output, experimental V2.1.1 output.
2. **Fair comparison:** same *source*, scale (2x/4x), print size, ICC, PPI,
   face region/mode, and model device/settings. Keep clear model logs.
3. **Review:** original | V2 | V2.1.1 at 100% pixels and intended print
   viewing size; include tiny glyph, layered FX, face, leaves, fabrics and
   alpha cutout crops. A metric increase or passed CI **does not prove
   an actual improvement**.
4. **Texture diagnostic:** `tools.v211_signage_roi_audit` now accepts
   `foliage`, `fabric`, `natural_texture`, `skin`, `food_texture`,
   plus Latin/Chinese/mixed-script text ROI categories. A pronounced
   high-frequency energy decrease/increase raises a *review signal*, not an
   AI restoration score. Human inspection is mandatory, especially to catch
   leaf -> plastic and added imaginary detail.
5. **Uncertainty:** if a crop cannot be improved safely, default to approved
   V2 for that crop/job; do not silently substitute a new model and do not
   declare the experimental model better.

### Evidence status at time of writing

- **Implemented in PR branch:** pre-inference block of legacy text redrawing;
  regression tests for the block; ROI taxonomy and texture review flags.
- **Not completed/certified:** same-input real-checkpoint V2 vs V2.1.1 quality
  test across all categories, native high-resolution ground truth for real
  images, object identity and texture visual acceptance, Windows GPU,
  full-size tiled print, physical vinyl and MainTop/Photoshop round trip.
- **Release state:** keep Draft PR #18 unmerged, unreleased. Do not present a
  V2.1.1 installer until all category regressions are addressed, and
  significant V2 improvements are visible on actual source images.

## Example private A/B audit

```bash
python -m tools.v211_generate_ab --input private/sample.png --out private/ab --scale 2
python -m tools.v211_signage_roi_audit --source private/sample.png --v2 private/ab/V2_reference.png --super private/ab/V211_V2_plus_HAT.png --regions private/rois.json --out private/audit
```

Example `rois.json` (normalized boxes; select actual ROIs per artwork):

```json
{"regions":[
 {"id":"tiny_cn","kind":"chinese_text","box":[0.05,0.10,0.40,0.25]},
 {"id":"leaf","kind":"foliage","box":[0.45,0.35,0.90,0.85]},
 {"id":"skin","kind":"skin","box":[0.12,0.35,0.36,0.65]},
 {"id":"alpha_edge","kind":"transparent_edge","box":[0.01,0.01,0.12,0.12]}
]}
```

These are **only command examples**, not evidence a real sample/model run
occurred. A/B tooling is bounded to <=16 MP representative crops and requires
real model weights; large-format production processing uses separate tiling.
