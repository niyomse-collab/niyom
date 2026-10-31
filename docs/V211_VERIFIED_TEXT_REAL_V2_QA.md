# V2.1.1 Exact Thai Typography — independently verified text, not automatic AI recovery

**31 October 2026 | Draft PR #18 | V1/V2 stable untouched | NOT a production release**

## Why the previous experiment was rejected

The shop inspected real V2 vs V2+HAT vs ink-geometry and Source-Ink A/B.
The last Source-Ink result **visibly failed**: dark/blue blotches remained
inside red `SALE 30`, and photographic details and edges were not obviously
better. Despite a positive PSNR on one synthetic case, the operator correctly
rejected it. The V2.1.1 adapter now **raises instead of processing** when
`v211_source_guided_ink=True`, to prevent inadvertently outputting the
previously rejected candidate. All accepted V1/V2 files remain unchanged.

## Fundamentally different quality path

If the print shop has the customer's **exact Unicode text and exact installed
font**, do not ask any raster SR model to guess lost dots, glyph holes or Thai
tone marks. Finish the approved V2 picture/face SR first, then re-render the
provided text at the final output pixels using full complex-script shaping.

- `signprint_ai/v211_verified_text.py` accepts a user-confirmed
  `VerifiedTextRegion(x,y,width,height,text,font_path,max_font_px,fill,...)`.
- Either export a **text-only RGBA transparent overlay**, no background,
  or replace only an opaque **uniform flat background** behind the selected
  original text. The latter checks the exterior colour ring and rejects
  gradients, photos, opacity changes, uncertain areas, or selected-face overlap.
- Position/size are fixed to target canvas; font automatically shrinks
  *proportionally* when the text does not fit, never stretches characters.
- `ImageFont.Layout.RAQM` on platforms that support it. The Windows CI
  Pillow wheel has **RAQM disabled**; `signprint_ai/v211_hb_font.py` uses
  actual HarfBuzz glyph shaping plus FreeType glyph rasterization instead.
  Without either verified backend, the app fails closed, not naive per-char
  Thai rendering. Only already installed fonts are read; no font binaries are
  bundled or redistributed.
- `V21Settings.v211_verified_text_regions=()` is **OFF by default** and has
  no production UI yet. Large disk-backed masters with this experimental
  exact-text mode remain blocked until tested.
- Original V2 Real-ESRGAN and GFPGAN face processing remain unchanged.
  The final text overlay occurs **after** face processing and final resize.

### Verified original V2-model A/B with known source text

[Real V2 inference and font QA #41176568833](https://github.com/niyomse-collab/niyom/actions/runs/41176568833),
[proof artifact 13032838141](https://github.com/niyomse-collab/niyom/actions/runs/41176568833/artifacts/13032838141).

A 384×328 native high-resolution ground-truth sign was rendered with
correct, supplied Thai `ซื้อ ชื่อ โปรโมชั่น`, Latin `SALE 30`, and real installed
fonts, along with red/blue blocks and a white rule. The image was downscaled
to 192×164 and blurred/noised. The original official
`RealESRGAN_x4plus.pth` checkpoint (mandatory SHA256 verification) ran on
the *same degraded source* twice. The V2.1.1 run **only** replaced the two
supplied text ROIs at native target resolution.

| Native-HR metric | V2 baseline | Verified exact text | Change |
| --- | ---: | ---: | ---: |
| Whole sign PSNR | 30.1980 dB | 36.1438 dB | **+5.9458 dB** |
| Whole sign SSIM | 0.96484 | 0.98316 | +0.01832 |
| Thai text ROI PSNR | 26.4780 dB | 45.8201 dB | **+19.3421 dB** |
| Red `SALE 30` ROI PSNR | 26.8094 dB | 50.3983 dB | **+23.5889 dB** |
| Pixels outside selected ROIs | — | **bitwise identical to V2** | No changes |

**Interpretation:** This is a real, visible improvement for the *special
case where exact original text and font are already known*. The native-HR
reference was constructed using those exact glyphs. These scores do **not**
prove automatic AI text recovery; they measure exact-font retypesetting,
which is expected to be much more faithful than guessing ink from missing
raster pixels. Do NOT extrapolate the gains to unknown or mixed fonts,
unreadable customer images, photographic content, or physical prints.

### Cross-platform code QA

[Windows/Ubuntu source QA #41176665637](https://github.com/niyomse-collab/niyom/actions/runs/41176665637):
Windows **486 passed/1 skipped**; Ubuntu **484 passed/3 skipped**.
Windows HarfBuzz/FreeType fallback tests exercise actual Thai vowel/tonemark
shaping. The separate full-neural proof used Linux with an installed Thai
font and RAQM. No font shipped to the end user.

Code checks additionally verify ROI bound/face overlap rejection, missing font
and complex shaping fail-closed, no white/black background added to RGBA
overlays, no change outside selected rectangle and refusal to erase existing
text over natural photographic or nonuniform backgrounds.

## Unresolved release blockers

1. This exact-text feature requires **user text + installed matching font +
   confirmed rectangle**; no integrated GUI yet, no fuzzy text detection,
   no OCR language guarantees.
2. Current replacement is allowed only over strictly verified *flat*
   backgrounds; Photoshop manual overlay is the safe alternative for complex
   background art. No unproven inpainting is permitted.
3. Rendered text at extremely large vinyl print dimensions, tiled edits,
   PNG/TIFF CMYK/ICC 300dpi edge profiling, and Photoshop/MainTop production
   have not been measured.
4. **Natural photo/detail/face quality remains unsolved**: the user's actual
   photograph A/B showed unnatural NAFNet faces. GFPGAN V2 selected Recover
   and portrait likeness still need human A/B and GPU/Windows packaged tests.
5. Automatic AI reconstruction of arbitrary raster lettering is NOT solved.
   HAT/SwinIR/NAFNet and previous post-SR ink geometry experiments did not
   meet the shop's visible-leap acceptance. Do not use them as defaults.

**V2.1.1 installer is NOT ready. PR #18 remains Draft/unmerged.**
