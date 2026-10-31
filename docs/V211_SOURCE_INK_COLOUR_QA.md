# V2.1.1 — LR source-guided red lettering ink experiment (31 Oct 2026)

## Why this exists
The operator reviewed the actual V2 and V2+geometry native-HR A/B screenshot.
Both show **black/blue mottling inside red "SALE 30" lettering**, despite the
clean source consisting of perfectly flat red ink. The V2+geometry contour
restoration improved blocks +0.20 dB and curves +0.73 dB, but letters
regressed -0.01 dB. This cannot be solved by more generic post-sharpening.

## Implemented research-only path
- `signprint_ai/v211_source_guided_ink.py` uses the original LR image for
  colour support and foreground/background photometric slope estimation; it
  repairs confidently red flat-ink pixels inside **V2** output without OCR,
  glyph regeneration or portrait changes.
- `V21Settings.v211_source_guided_ink=False` by default, no normal UI toggle
  and no new downloaded weight.
- Guarded on source/target flat-texture, strong red colour, 3x3 safe letter
  interiors; bypasses coherent already-flat red blocks, non-red curves,
  natural photos and alpha cutout borders; preserves selected face ROIs.
- Processing runs only on bounded research crops before original V2 GFPGAN;
  disk-backed large masters reject this unverified experimental option.
- V1/V2 stable source, model and release are unchanged.

## Two official Real-ESRGAN V2 checkpoint A/B runs
Both used actual pinned original `RealESRGAN_x4plus` weights on CPU, the
independent 192px ground-truth art, the same blurred 96px LR source, and equal
pixel dimensions. Neither run contains private customer content or model weights.

| Trial / case | PSNR V2 | PSNR assisted | Gain | SSIM gain |
| --- | ---: | ---: | ---: | ---: |
| First implementation red lettering | 27.6156 | 28.5477 | **+0.9321 dB** | +0.00682 |
| Revised anti-alias-preserving red lettering | 27.6156 | 28.3079 | **+0.6923 dB** | +0.00698 |
| Revised red/blue solid blocks | 29.5210 | 29.5210 | **0**, byte-identical | 0 |
| Revised black/gold curves | 35.2041 | 35.2041 | **0**, byte-identical | 0 |
| Revised photograph | 23.0924 | 23.0924 | **0**, byte-identical | 0 |

- [Official weight first real A/B #41174933427](https://github.com/niyomse-collab/niyom/actions/runs/41174933427):
  provisional +0.7 dB screen passed, **but** one independent code test FAILED:
  a fabricated dark-stroke test showed the 0.85 colour projection darkened
  otherwise correct antialiased boundaries.
- [Official weight revised A/B #41175083985](https://github.com/niyomse-collab/niyom/actions/runs/41175083985):
  first failure corrected, complete official inference and artifact succeeded,
  but **0.6923 dB < 0.7000 dB minimum research screen**. Workflow correctly
  **FAILED**: do not reduce gate just to change its colour.
- [Core Windows+Ubuntu #41175083875](https://github.com/niyomse-collab/niyom/actions/runs/41175083875):
  **476 passed, 1 skipped each**, after anti-alias protection correction.
  Green code tests do not mean recovered Thai letters.
- It is not a production feature. The visual red glyph still exhibits colour
  and halo faults, and exact Thai glyphs, numerals, tone marks and the face
  likeness of real people have not been certified.

## Important limitations and next actual-quality experiment
- The current model fixes only strongly red ink in small flat-colour art.
  Other glyph colours and low-quality tiny Thai diacritics are not handled.
- Need **multiple native-HR Thai font cases** with known exact words,
  diacritics and stroke continuity, using available commercial-compatible
  Thai fonts for research. Do not guess missing text from pixels.
- Need a source-support-aware *topology / colour occupancy* repair that
  addresses dark holes, false blue fringe and pixel-normalized flat colours
  without making red strokes wider or losing counters/tone marks. The current
  colour-line projection only partly removes those artifacts.
- Use exact original V2 weights, same output dimensions, read Thai samples at
  target zoom, preserve zero-alpha channel and selected GFPGAN faces.
- Do not conflate synthetic PSNR with visible print improvement; after
  repeatable graphic pass, test large disk-backed RGBA, GPU GTX1660Ti,
  Photoshop/MainTop RIP and printed vinyl.
- Maintain PR #18 as Draft and **do not release V2.1.1** until there is
  visible progress beyond approved V2 on every required content category.
