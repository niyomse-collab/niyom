# V2 beta.23 private artwork — first paired output inspection

Date: 2026-10-28. Customer source files and AI outputs were supplied privately in the conversation and **are not committed or published**. The comparisons below are against standard Lanczos enlargement at the exact same final raster sizes, **not** an independently run Upscayl output and **not** a V2.1 candidate.

## Evidence scope

| Private sample | Source pixel size | AI output pixel size | Output metadata DPI | Transparency |
| --- | ---: | ---: | ---: | --- |
| A (portrait-format food banner) | 682 × 2048 | 3543 × 10625 | about 150 | RGB, not applicable |
| B (landscape-format Thai ceremony banner) | 1672 × 941 | 2953 × 1662 | about 150 | RGB, not applicable |

Images were inspected visually in paired, matched-output-pixel crops: source resized with Pillow Lanczos against the NiyomSilp output. These files were a beta.23 / V2-era output (the V2.1 model path is **not** verified from this file metadata).

- A, upper title/detail crop: mean absolute RGB delta **12.84** across pixels versus Lanczos; **46.3%** of pixels differed by more than 8 in at least one channel.
- A, lower food/photo crop: RGB delta **17.43**; **54.9%** of pixels differed by more than 8 in at least one channel.
- B, upper Thai title: RGB delta **7.12**; **35.7%** differed by more than 8.
- B, lower small Thai lettering: RGB delta **8.48**; **34.5%** differed by more than 8.

These metrics and paired crops confirm that the AI output is materially different from a plain Lanczos resize. The large typography looks crisper in matched crops. These scores **do not** prove correctness or fidelity: invented/reconstructed strokes, wrong vowels/diacritics, halos and photo artifacts must be reviewed separately. Increased Laplacian variance is not a print-quality score. No customer images are stored in this repository.

## Blocking acceptance items

1. Run the latest V2.1 candidate on identical private source files with the **default photo model** and the **optional graphic model explicitly enabled**, at identical output pixels.
2. Verify Thai glyphs and tone marks manually at 100/200/400% and inspect flat-colour artifacts, face details, photographic texture and tiled seams.
3. If comparing Upscayl, obtain the actual Upscayl output, not only model/scale settings shown in its UI.
4. Run RGBA PNG/TIFF alpha checks with the shop's real transparent assets.
5. Keep the result as **NOT_PRINT_CERTIFIED** until Photoshop and physical print evidence exists.

The user's own side-by-side observation is that NiyomSilp looked visibly better than Upscayl for their tested image. This is a user-reported preference, not an independently measured head-to-head result.
