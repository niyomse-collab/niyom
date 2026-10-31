# V2.1.1 — SwinIR 1× pre-restoration experiment, not a release

## Why this experiment exists
The shop compared actual V2 vs V2 + HAT edge transfer and judged **V2 better**:
unwanted stripes below a circle, less clean thin strokes and no visible quality
leap. HAT-derived post-sharpening is therefore NOT accepted as a production
default. Merely having more changed pixels is not evidence of better art.

### Source-fidelity experiment
1. Keep **V2 Real-ESRGAN** as the primary upscaler and **V2 GFPGAN** face
   Recover/Studio AI afterward.
2. The independent SwinIR `005_colorDN_DFWB_s128w8_SwinIR-M_noise15.pth`
   performs **actual neural 1× colour denoising before V2** (opt-in).
3. Protect face ROIs and source structural text/graphic edges; avoid denoising
   the second 2× pass of an 8× image. The source alpha is handled separately
   by V2.1.1's existing RGBA safe path.
4. The restorer is bounded-tile for large vinyl images; no pixel cap is
   introduced for the print app. The diagnostic A/B tool alone limits itself to
   representative <=16MP crops.
5. Do not alter accepted V1 or V2 or silently fall back to an unrequested
   model. Keep model optional and **never auto-download 123MB to the shop**.

### Trusted upstream checkpoint
- Official source: https://github.com/JingyunLiang/SwinIR
- Official release URL: https://github.com/JingyunLiang/SwinIR/releases/download/v0.0/005_colorDN_DFWB_s128w8_SwinIR-M_noise15.pth
- File size: **122,905,743 bytes**.
- SHA256: `917cd972f7ba80786871add249ad43e4477ce2db59b4ad63e2fa446f7221d013`.
- Provenance-only GitHub Actions: https://github.com/niyomse-collab/niyom/actions/runs/41154552984
- Verify exact size, SHA256, RGB 1× descriptor and SwinIR architecture
  **before** running the model. Do not redistribute this checkpoint until
  weight-specific commercial/redistribution terms are checked.
- Official repo code is Apache-2.0, but verify individual weights and full
  dependencies independently before bundling.

### Quality gate
- Synthetic input contains *known* uncompressed RGB ground truth and
  additive Gaussian noise sigma=15. Calculate source-region PSNR before/after
  actual SwinIR processing; do not claim success if no measurable gain.
- Run identical source through real **V2** and **SwinIR→V2**, with identical
  output dimensions, DPI, ICC, selected face ROIs and V2 finishing.
- Check that the photographic region is cleaner, while Thai glyphs, crisp
  graphics, border geometry, faces and full-opacity colour fills never
  deteriorate. Use a real customer-quality nonprivate test set before launch.
- Do not use PSNR as a proxy for all perceptual or print quality; a high PSNR
  is still insufficient without human crop review and physical print.
- The first real-weight QA failed at 24.698 dB before **and** after because
  Sobel edge detection treated noisy pixels as typography and rejected all
  restoration. The revised contour detector blurs a *copy* only to distinguish
  structural lines from random noise; the image itself is not blurred at this
  stage. This failure is documented, not hidden.
- Latest real-weight QA and Windows regression must pass again before any
  positive quality claim. A visual **leap beyond V2** is the actual release
  acceptance criterion, not green CI on synthetic samples.

### Still blocked
- Licensed distribution of model weights for commercial printing
- Real portrait likeness/eyes/lips, Thai marks and micro-text A/B against V2
- NVIDIA GTX 1660 Ti, large disk-backed RGBA/CMYK export
- Photoshop and MainTop RIP output, vinyl print
- Windows V2.1.1 installer test, uninstall/reinstall and checksum

**PR #18 stays Draft and separate from accepted V1/V2.**


### Real-weight SwinIR re-run: technical pass, leap criterion NOT met

- [Run #41155035986](https://github.com/niyomse-collab/niyom/actions/runs/41155035986) completed SUCCESS with **two real official neural weights**, SHA256-verified at runtime, no client image or weights redistributed.
- Synthetic photo noise σ=15, known 1× clean reference ROI: **24.6977 dB before**, **26.9563 dB after** (SwinIR source restoration gain **+2.2586 dB**).
- End-to-end NiyomSilp pipeline: 2×, 128×128 output, 300 DPI, V2 Real-ESRGAN vs V2 Real-ESRGAN + SwinIR pre-restoration both executed. Source/OAI image output stays in the research ZIP artifact `V211-Real-SwinIR-PreRestore-V2-CPU-QA`, ID `13024693158`.
- In the final 2× comparison, the assisted result differed from V2 in **8.6121%** of pixels by more than 3/255, mean absolute channel change **1.13391**. This shows the changes are **much smaller** than the already-rejected V2+HAT path.
- Independent comparison of both final 2× outputs against the known 1× clean input resized **bicubic** (a proxy, NOT true high-resolution ground truth): **V2 26.964 dB**, **V2+SwinIR 27.244 dB**, net **+0.280 dB**. Comparable Lanczos and nearest-neighbor references give +0.263 and +0.288 dB.
- **Conclusion:** Source denoising definitely works, but end-to-end difference is **NOT** the visible leap the operator explicitly requires. This configuration is **not accepted for release**. Do not claim more pixels changing means higher print quality.
- The research script now records the final-output bicubic proxy gain and a provisional **+1 dB output acceptance screen**; a 1 dB pass would still require human visual and real print checks.
- No portrait identity, Thai diacritics, Windows installer, GPU/GTX1660Ti or real MainTop vinyl proof yet.
