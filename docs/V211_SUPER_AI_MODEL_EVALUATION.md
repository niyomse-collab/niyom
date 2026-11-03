# V2.1.1 Super AI — additional upstream model candidates (31 Oct 2026)

## Non-negotiable operating contract

- **V2 Real-ESRGAN remains the primary photo/print engine** and the V2 GFPGAN Recover flow remains the baseline for faces. Do not replace it with a new model by default.
- New models are optional, independent **assist stages**, selected per problem and image region. Each stage must make a measurable, *visible* improvement compared with **V2 on the same source at the same output pixel dimensions** before it can be enabled by default.
- Preserve face shape/identity, Thai text contours/diacritics, ICC/DPI, PNG/TIFF alpha, geometry and the original V2 output when the add-on is disabled.
- Each model requires a separate opt-in checkpoint package, exact upstream source/provenance, pinned SHA256, verified checkpoint license, attributable notices, failure messaging, real CPU/GPU inference and Windows packaging tests. No automatic background downloads or silent fallback. The shop's installed V1 and V2 must never be modified.
- Never treat green synthetic regression tests as proof of portrait sharpness or print suitability.

## Candidates and priority

| Candidate | Intended complementary role in V2.1.1 | Evidence/rights to verify | Current decision |
| --- | --- | --- | --- |
| **SwinIR** | Target **JPEG artifact reduction or denoising** *before* V2, restricted to photographic regions; optional separate 4x detail candidate for comparison | Official Apache-2.0 code; choose a specific compatible upstream checkpoint and inspect weights/notice prior to redistribution; small SR weights can be materially smaller than a diffusion pipeline | **Opt-in 1× denoise15 integrated; real CPU inference passed; visible-leap gate FAILED (+0.280 dB final proxy)** |
| **NAFNet (SIDD or GoPro)** | **Noise removal or deblur on source photographs before V2** where detected degradation justifies it; protect text and faces from smoothing | Official Megvii model; check each specific checkpoint's provenance/license. LibreYOLO's repackaged SIDD model card identifies MIT but width-64 weight is ~464 MB; avoid bundling until accepted | **Priority 2: evaluate and A/B**, not integrated |
| **RestoreFormer++** | Independent **face-only candidate**, compared against V2 GFPGAN; use only when face confidence/identity and sharpness are better; never automatically overwrite the V2 recovered face | Official Apache-2.0 repository; verify checkpoint-specific conditions and third-party components | **Priority 3: evaluate face ROI**, not integrated |
| **DiffBIR v2.1** | Severe real-image degradation / blind restoration as an opt-in research pipeline, not safe on literal lettering or exact portrait identity | Code Apache-2.0; relies on Stable Diffusion 2.1 and checkpoint-specific use terms. Confirm end-to-end commercial rights and weights before packaging | **Hold for licensing/resource/identity review** |
| **HAT** | Add high-frequency edge detail to the existing V2 output, behind a guarded blend excluding selected faces | Experimental checkpoint verified by SHA256; Spandrel loader and HAT CPU sample inference | **Code integrated as V2 + HAT Assist; Windows/GPU/photo-print A/B not certified** |

### Primary sources (upstream and model cards)

- SwinIR official project: https://github.com/JingyunLiang/SwinIR (Apache-2.0 code).
- NAFNet official project: https://github.com/megvii-research/NAFNet ; repackaged SIDD weight details: https://huggingface.co/LibreYOLO/LibreNAFNetl-restore-sidd
- RestoreFormer++ official project: https://github.com/wzhouxiff/RestoreFormerPlusPlus (Apache-2.0 code).
- DiffBIR official project: https://github.com/XPixelGroup/DiffBIR (Apache-2.0 code; underlying models have additional terms).

## SwinIR verified experimental result (31 Oct 2026)

- Exact official colour denoise15 checkpoint: `005_colorDN_DFWB_s128w8_SwinIR-M_noise15.pth`; **122,905,743 bytes**; SHA256 `917cd972f7ba80786871add249ad43e4477ce2db59b4ad63e2fa446f7221d013`.
- SwinIR 1× preprocessing is **already integrated as opt-in before V2**; it is not a replacement for V2 Real-ESRGAN or GFPGAN. No automatic weight download or commercial redistribution is approved.
- [Real-weight CPU inference #41155035986](https://github.com/niyomse-collab/niyom/actions/runs/41155035986) passed. Synthetic σ15 source-photo ROI PSNR rose 24.6977 → 26.9563 dB (**+2.2586 dB**), but equal-pixel final V2 vs SwinIR→V2 gained only **+0.280 dB** against an upscaled clean-image *proxy*, not true high-resolution ground truth.
- **Release quality gate FAILED**: this is not the required visible improvement over V2. Do not enable by default, certify print quality, or offer a tester installer on this evidence. HAT also remains off by default after the operator judged V2 superior due to false edges.
- See [detailed QA](V211_SWINIR_PRE_RESTORE_QA.md). Next research: license-verified NAFNet/Restormer for genuinely degraded photo ROIs and RestoreFormer++ for carefully evaluated face ROIs. Require exact weights/SHA256, real inference, meaningful same-source A/B, face identity, Thai marks, alpha/ICC/DPI, GPU/Windows and actual print validation before adoption.

## Experimental gates before adding any candidate to the UI or installer

1. Confirm specific version, dependency import, upstream checkpoint byte size, SHA256, license and redistributed notices.
2. Run real pinned-weight inference on portrait, text-on-solid-color, JPEG-compressed photo, noisy photo and RGBA examples; record VRAM, runtime and output dimensions.
3. Produce **V2 versus V2+AI side-by-side** output with equal pixels, matching crop and the same color management. Review for *visible* improvement versus halos, invented marks, unexpected skin texture, facial identity drift, noise, Thai vowel/tone-mark corruption and boundary seams.
4. Select candidates only on regions for which they beat the V2 baseline; protect selected faces and typography as relevant, and preserve a plain V2 output for a no-regression comparison.
5. Confirm no excessive disk/RAM/VRAM pressure on GTX 1660 Ti; use optional local model install rather than a giant compulsory installer. Test Windows packaged EXE, reinstall/uninstall and Photoshop/MainTop output.
6. Record failure and excluded cases as explicitly as successes. Keep PR #18 in Draft until acceptance.

**No candidate named above may be described as installed, packaged, commercially cleared or quality-certified just because it appears in this plan.**
