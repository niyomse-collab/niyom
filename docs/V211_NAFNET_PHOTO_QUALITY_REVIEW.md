# V2.1.1 NAFNet + V2: actual image-quality findings (31 Oct 2026)

**Status: PHOTO-SPECIFIC PROGRESS, FULL V2.1.1 RELEASE QUALITY = FAIL.**

The operator's requirement is a clear quality leap over accepted V2, with no blurry faces, distorted Thai writing, spurious straight/curved borders, damaged flat ink or failed alpha. A successful model inference or green unit test is NOT quality certification.

## Confirmed real-model research

- Branch `feature/v2.1.1-super-ai`, Draft PR #18; no V1 or V2 stable file modified.
- [Real photo and synthetic sign proof — GitHub Actions #41170969833](https://github.com/niyomse-collab/niyom/actions/runs/41170969833). Research artifact `V211-NAFNet-GoPro-V2-TrueHR-AB-Research`, ID `13030129708`. Contains no customer photos or model weights.
- Official V2 `RealESRGAN_x4plus` and NAFNet-GoPro width64 checkpoint weights were pinned and SHA256 verified, then run on CPU. Commercial redistribution terms for the specific GoPro checkpoint have NOT been certified.
- Low-resolution input was created by downsampling **independent native high-resolution photographic reference** and deliberately adding motion blur. Evaluation compares same-size output directly against actual reference, never an upscaled low-resolution proxy.

### Photograph: NASA astronaut sample (384px ground truth, 192px blurred input)

| Method | HR PSNR | HR SSIM |
| --- | ---: | ---: |
| Accepted V2 Real-ESRGAN | 19.2404 dB | 0.57519 |
| NAFNet high-pass/sign-ink-safe blend -> V2 | 20.5848 dB | 0.63906 |
| **Full NAFNet photo-only restoration -> V2** | **22.6311 dB** | **0.73285** |

**Photo-only improvement vs V2:** **+3.3907 dB PSNR** and **+0.15766 SSIM** on this example. At 1x, NAFNet raw denoising recovered from 19.8828 to 24.5166 dB, but the mixed-signage high-pass blend reached only 21.4362 dB, which explains the prior loss of improvement. A distinct `v2_nafnet_photo_only` research-only engine routes the actual 1x network output into unmodified V2 Real-ESRGAN and preserves selected face ROIs prior to V2 GFPGAN.

Visual examination shows greater detail than V2 on this blurred source **but eyes/mouth and some skin texture can look artificial**. PSNR improvement does not establish identity fidelity, human acceptance or the safety of recovering faces with V2 GFPGAN. Do not market as finished.

### Independent checks prevent cherry-picking

| Case | Candidate HR PSNR gain over V2 | HR SSIM gain | Assessment |
| --- | ---: | ---: | --- |
| Blurred astronaut | **+3.3907 dB** | **+0.15766** | Promising, one photograph |
| Blurred coffee photograph | **+0.9290 dB** | **+0.03062** | Some improvement, below provisional +1 dB |
| **Unblurred astronaut control** | **-0.6419 dB** | **-0.00836** | **Regression** — NAFNet should not run here |

**Photo-domain provisional gate = false.** Sharp original photography must retain approved V2 output. A user-selected or verified *blurred-photo-only* mode, with a reliable safe bypass on clean input, is needed before any default recommendation.

### Native-HR signage/ink experiments

NAFNet GoPro applied broadly across synthetic red/blue logo and fine black/white graphic edges remains objectively worse than V2 (horizontal motion case overall **-1.4105 dB**, flat ink **-7.0444 dB**; clean control overall **-1.8110 dB**, flat ink **-7.6981 dB**). The previously added high-pass masks do not solve this. **Never** feed the entire sign or Thai typography to this photo-trained model. The workflow correctly ends FAILURE for full-domain quality, while retaining all research samples.

## Implementation constraints

- `v2_nafnet_photo_only` is **research-only and not exposed as a customer/production UI choice**. The app's default remains V2.
- Use photo-only model **only** on selected/confirmed photographic areas; lettering/logos/solid fills retain V2. No silent fallback, no whole-signage processing.
- Explicit selected face rectangles remain pixel-identical before downstream GFPGAN V2; real end-to-end face Recover / Studio AI identity must still be proven.
- Research mode does not ship pretrained weight files. Verify model code, dependencies and exact checkpoint-commercial rights before any paid-shop redistribution.
- Continue tests on multiple independent photos, camera degradations, sharp controls and mixed artwork, with actual V2 comparison and human visual review. A provisional +2 dB on one astronaut is not a universal or printable quality leap.
- NVIDIA/GTX 1660 Ti GPU, very large disk-backed tiles, RGBA/ICC/DPI, Photoshop/MainTop and vinyl print, Windows installer/reinstall/uninstall remain blockers.

## Next engineering decision

1. Validate a **conservative blur/degradation gate**, with a complete V2 bypass on clean inputs and a manually selected photo-only region for mixed signs. Test independently on more content; generic Laplacian thresholds alone can misclassify smooth photos, so do not enable such a heuristic by default without evidence.
2. Test V2 GFPGAN Recover/Studio AI explicitly with the NAFNet photo pipeline, selected face regions and human checking of eyes, mouth, contours and identity.
3. Re-evaluate against true HR reference and clean controls at larger crop sizes; only proceed if photo and graphic domains remain nonregressing.
4. Keep PR #18 **Draft/unmerged** until visible improvements in face, text, flat ink and physical prints are demonstrated.
