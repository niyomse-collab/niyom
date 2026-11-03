# V2.1.1 real dual-model CPU A/B proof — 31 October 2026

Status: **research-only execution PASS, visual / print quality NOT CERTIFIED**.

## Reproducible execution

- [GitHub Actions #41152885769](https://github.com/niyomse-collab/niyom/actions/runs/41152885769) — **success**.
- Experimental branch `feature/v2.1.1-super-ai`, Draft PR #18, commit `f4788965f7d99ee6bb87e2cc5e53bc873fe01b9a`.
- Real V2 RealESRGAN_x4plus checkpoint SHA256: `4fa0d38905f75ac06eb49a7951b426670021be3018265fd191d2125df9d682f1`.
- Real HAT_SRx4_ImageNet-pretrain checkpoint SHA256: `4ee053c42461187846dc0e93aa5abd34591c0725a8e044a59000e92ee215e833`.
- Weights verified before actual inference; neither checkpoint is uploaded or published in the artifact.
- Pinned CPU research environment: PyTorch `2.5.1+cpu`, torchvision `0.20.1+cpu`, Spandrel `0.4.2`, BasicSR `1.4.2`, Real-ESRGAN `0.3.0`.
- **Both full NiyomSilp adapter pipelines ran**, not only standalone HAT tile inference: V2 Real-ESRGAN baseline versus V2 Real-ESRGAN + HAT Assist.
- Synthetic reproducible 48 × 40 px mixed graphic / photo-noise test source → both 96 × 80 px RGB PNG, DPI 300. No private customer input was used.
- Research artifact `V211-Real-V2-Plus-HAT-CPU-AB-Synthetic`, ID `13023139903`. It contains original, reference V2, assisted V2.1.1, side-by-side image and A/B JSON report.
- Related lightweight Windows/Ubuntu core CI [#41152885887](https://github.com/niyomse-collab/niyom/actions/runs/41152885887) — **success**.

## Measured differences on this single synthetic crop

| Metric | Measured |
| --- | ---: |
| Visible pixel count | 7,680 |
| Mean absolute RGB channel change, all visible pixels | 3.44705 / 255 |
| Overall pixels with any-channel change > 3/255 | **23.4375%** |
| Original V2 edge-region pixel count | 2,330 |
| V2 edge mean absolute RGB channel change | 9.62604 / 255 |
| V2 edge pixels with any-channel change > 3/255 | **64.8927%** |
| V2 flat-fill pixel count | 814 |
| Flat-fill mean absolute RGB channel change | 0.06593 / 255 |
| Flat-fill pixels with any-channel change > 3/255 | **0.1229%** |

The result confirms that **two different real checkpoints produced a measurable combined output**. The added detail is concentrated near detected V2 colour/shape edges while most flat fills remain very close to V2. The colour-safe blend prevents a bounded luminance detail change from clipping only one RGB channel, which would change brand ink hue.

These metrics do **not** prove HAT is visually better, preserve fine Thai glyph geometry, restore a real human face, prevent halos in full-size imagery, pass a print shop quality check, or improve subjective detail. A difference from the baseline is not necessarily an improvement.

## Mandatory release blockers

1. Inspect at least 3 representative **locally sourced** photographic and vinyl-sign crops: portrait/eyes/mouth, small Thai/English print, saturated flat-colour logos; same source, output size, DPI and colour profile.
2. Verify face Recover/Studio AI actually completes with V2 GFPGAN using selected faces; compare identity and sharpness before/after, never accept a face skip.
3. Run HAT on an NVIDIA GPU (GTX 1660 Ti specifically if available), including peak VRAM, 2x/4x and disk-backed larger images; verify tile seams.
4. Check PNG/TIFF alpha, actual Photoshop/MainTop colour management and printed vinyl at final size.
5. Verify third-party HAT checkpoint and runtime **commercial redistribution permissions** before packaging its weights. Keep additional weights opt-in, not multi-GB mandatory downloads.
6. Build/test Windows V2.1.1 .exe/installer, installed smoke, uninstaller and checksum. Do **not** publish as a stable V2 upgrade.

### Reproduce privately

In an environment with both pinned verified weights and the V2.1.1 source:

```bash
python -m tools.v211_real_dual_model_qa
python -m tools.v211_generate_ab --input /private/sample.png --out /private/quality-v211 --scale 2
```

Use only representative <=16-megapixel output crops for the in-memory A/B report. This limit affects only diagnostic comparison; production large print image processing remains disk-backed.

**Neither successful execution nor green unit tests may be presented as final acceptance or permission to ship an installer.**
