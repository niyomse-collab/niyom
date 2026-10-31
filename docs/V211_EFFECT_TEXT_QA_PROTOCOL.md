# V2.1.1 effect-text and mixed-sign QA protocol (research; NOT acceptance)

Status: **SPECIFICATION ONLY**. No effect-retention model or benchmark is implemented or certified by this document. The five user-described artworks are *visual references*, not paired degraded input/native-HR ground truths; they must not be copied into public GitHub or public CI artifacts.

## Two distinct operations

1. **Verified exact-text replacement:** user supplies exact Unicode, matching licensed locally installed font, selected ROI and explicit permission to replace. Current `v211_verified_text` is limited to flat opaque confirmed backgrounds or transparent overlay; never silently replace multicolour, outlined, glossy, gradient, shadowed, embossed, brushed or metallic raster typography with flat fill. Complex effects require separately validated layer/effect reconstruction and user approval.
2. **Effect retention / raster upscale:** preserve the original designed pixels, glyph topology, counters, accent placement, edge layers, colour, gloss, highlights, shadows and intentional texture. No OCR-inferred retyping, invented diacritics, fake edge detail or arbitrary texture smoothing. Baseline is approved V2 Real-ESRGAN + GFPGAN; all assistants opt-in and bypass if uncertain.

## Evaluation strata (independent licensed synthetic fixtures, plus privately reviewed real images)

| Stratum | Inspect at identical output pixels | Fail examples |
| --- | --- | --- |
| Flat text and numbers | Per-layer anti-alias, stroke-width distribution, contour continuity, counters, Thai combining marks | missing dot/tone mark, altered glyph, dark/red/blue speckles in solid ink |
| Multicolour 3D Thai | Hue/gradient continuity, banding, layered outlines (width and registration), bevel, highlights, shadows, specular/metallic gloss | flattened effects, outline drift, fake highlights |
| Brushstroke menu | Intentional coarse edge grain versus newly generated pixel noise, white text over red brush, yellow numeral contours | brush texture erased, halos, fake noise |
| Tiny labels and phone numbers | Exact Unicode/numerals, spacing, colour layers and legibility at 100% | invented numbers, wrong Thai diacritics |
| Food, water and ice | Product texture, sauce shine, splashes, transparent ice, realistic detail | plastic textures, synthetic grain, changed object shape |
| Portrait and fabric | Eye, lip, nose fidelity and identity, skin/fabric texture; selected Recover/Studio AI must run V2 GFPGAN and fail before export on unsuccessful QA | changed identity, blurred eyes/mouth, silently skipped face |
| RGBA PNG/TIFF | Pixel-exact alpha outside intended changes, transparent matte RGB and fringe, ICC/DPI, tile boundaries | filled background, black/white fringe, colour shift |

## Reference and measurement rules

- Generate native HR truth **first** from independently licensed source vector/raster layers and exact Unicode/font, then downsample and apply recorded degradation. Do not call bicubic enlargement of LR 'true HR'.
- For each of at least **three independent signage scenes** (flat ink, multicolour effect text, mixed photo/portrait) and photographic controls, save V2-only and candidate images at identical output dimensions, alpha, ICC, DPI and display scaling. Keep customer files private and outside public CI.
- Report full-image and ROI PSNR/SSIM when true HR exists, plus colour error (Delta E on flat/gradient regions), contour/stroke-width and connected-component/topology changes, multi-outline registration, banding, alpha/fringe and tile-seam checks. Metrics complement, never replace, side-by-side human inspection and printed vinyl approval.
- Record actual checkpoint version, SHA256, commercial redistribution rights (including dependencies), hardware, peak VRAM/RAM, wall time and whether a fallback/bypass happened. A green code CI run is **not** a quality pass.
- Any wrong character, changed face identity, missing tone mark, transparent background corruption, or failed selected-face recovery is an unconditional **FAIL**. Candidate quality regression versus V2 is FAIL; leave optional model off by default.
- GTX 1660 Ti 6 GB must be tested, but CPU/RAM/disk bounded tiles are permitted for larger print jobs. Confirm PNG/TIFF Photoshop import, ICC/DPI and MainTop print results before installer approval.

## Reference categories (descriptions only, no customer images)

1. Green/yellow/pink food signage: hot-pink lettering, thick cream outline, smooth flat ink, '30 บาท', food grain.
2. Fruit soda: yellow/pink/cyan glossy 3D Thai, dark navy/bright blue stacked outlines, white specular highlights, splashes, ice, tiny can labels.
3. Night-time krathong: green/pink/purple glossy Thai, white/black outlines, magenta/yellow banners, reflected light, textured products.
4. Red spicy-salad menu: deliberately rough red brush behind white Thai, yellow numerals, shiny sauce and sharp chillies.
5. Vertical halal food menu: gradient Thai on wood, two portraits, tiny coloured menu descriptions and phone, natural fabric/skin/food texture.

**Release gate remains CLOSED** until independent real V2 A/B, selected-face QA, alpha/ICC/DPI, large tiled output, Windows packaged install/uninstall, Photoshop/MainTop and physical print acceptance are documented. Keep PR #18 Draft and V1/V2 stable untouched.
