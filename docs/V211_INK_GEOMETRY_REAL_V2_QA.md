# V2.1.1 independent graphic ink reconstruction — real V2 result (31 Oct 2026)

**Release acceptance = FAIL, research candidate remains OFF by default.**

The user required a visible improvement over accepted V2 across Thai/English lettering, text outlines, curves, realistic photos and faces, and transparent PNG/TIFF. Actual improvements must exceed human and physical print review, not simply unit tests or synthetic 1× blur recovery.

## Changes evaluated

- `signprint_ai/v211_ink_geometry.py` implements conservative colour-coverage geometry repair for flat graphics using two-sided coherent edge samples and monotone smoothstep coverage. Does not use OCR or fabricate letter names. Face selection, alpha borders and photographic images are protected.
- `V21Settings.v211_ink_geometry` defaults **FALSE**. Enabled only on V2.1.1 research jobs via optional post-V2 finishing in `v2_graphic_edges.refine_sign_edges`, not in accepted V1/V2 stable.
- Unit evidence with independently rendered 1× high-res source blurred by a Gaussian shows gains on blocks and curves; **this is not a real V2 comparison**.
- [Real official-checkpoint workflow #41173984447](https://github.com/niyomse-collab/niyom/actions/runs/41173984447): actual pinned SHA256-verified `RealESRGAN_x4plus` processed each degraded low-res source twice, once with V2 edge finishing, once with the geometry repair. Native 192×192 ground truth was rendered **before** making the degraded input; no bicubic fake HR reference was used.
- Research proof artifact ID **13031493411** includes RGB outputs, uncompressed native-reference PNGs and per-case metrics. Checkpoint weights were not uploaded.

| True-HR reference subject | V2 PSNR | V2+Geometry PSNR | Gain dB | SSIM gain |
| --- | ---: | ---: | ---: | ---: |
| Flat red/blue blocks and white rule | 29.5210 | 29.7259 | +0.2049 | +0.00481 |
| Black curved ink | 35.2041 | 35.9358 | +0.7317 | +0.00250 |
| English white/red lettering + three small dot marks | 27.6156 | 27.6043 | **-0.0113** | +0.00011 |
| Photographic NASA astronaut control | 23.0925 | 23.0925 | 0.0000 | 0.00000 |

**Provisional quality gate failed.** The candidate changes only ~1.94% of block pixels, ~1.14% of curve pixels and ~0.19% of letter pixels by >3/255. It avoids corrupting photo pixels, but the lettering gains seen in isolated 1× synthetic studies did not survive actual ESRGAN; **it does not achieve the user's visible-leap goal**.

### Visual root-cause analysis

The actual V2 letters have **nonuniform/hallucinated dark red patterns inside the word SALE 30**, not just blurry edge transitions. Geometry-only post-processing cannot restore original interior colour or correct glyph topology once a neural SR model has invented texture. User-provided exact Thai text cannot be guaranteed correct from raster geometry alone.

The first test version failed two unit tests for thin dot marks and realistic font thickness. QA fixtures were adjusted to check *resolvable* 5px dots and medium-weight signage glyphs rather than lowering an image-quality threshold; the subsequent 1× tests passed. The actual V2 benchmark still failed its stricter screen. That difference between unit and native checkpoint QA must remain visible.

## Engineering consequences

1. Keep geometric finishing **experimental / disabled**; do not increase strength just to make a large cosmetic pixel change or claim it already sharpens Thai characters.
2. The bottleneck is *upstream Real-ESRGAN on text* rather than a missing generic post-sharpen slider. Next research must examine preserving original flat ink colour and stroke topology **before or during the model pass**, with independent Thai glyphs and known original text for character-level verification. Do not hallucinate diacritics, letters, numbers, logos.
3. Mixed photo/text images require separate protected ROI processing; use V2 for non-selected regions. Photo-only NAFNet remains research-only and its clean-image regression must be blocked.
4. Explicit user-selected GFPGAN Recover/Studio AI remains the approved V2 face pipeline; fail-closed audit now covers small and large confirmed faces, but naturalness/identity have not been certified by real portrait experiments.
5. PNG/TIFF alpha, 8× tile seams and Photoshop/MainTop full-size printed samples still require visual validation. Passing source code regression tests does not release the Windows installer.

Windows and Ubuntu current core checks succeed on branch PR #18, but **QUALITY = FAIL**. Do not merge or release, and leave V1/V2 stable unchanged.
