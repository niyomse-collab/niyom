# NiyomSilp V2.1.1 — Four real AI engines integrated in Windows experimental build (4 November 2026)

Branch: `work/v211-four-engine-v2-bridge-20261103` / Draft PR #20.
**Do not merge/release as accepted V2.1.1 until the shop approves side-by-side image QA.**

## Implemented in experimental branch

- Keep V2 Real-ESRGAN main enhancement, GFPGAN face restoration, sliders, Windows output behaviour and alpha/ICC/DPI print path unchanged.
- Once the user confirms a one-time download, install four native upstream AI executables plus their model assets in private LOCALAPPDATA and validate archive SHA256 and a SHA256-checked manifest. Subsequent usage is offline. Executables/weights are **not bundled in our distributed installer**.
- For a supported 2x AI PNG output, the app calls all four actual installed native executables sequentially on the original input. Missing engines never result in a false claim of a completed fusion; the accepted V2 output stays untouched.
- An additional tiled pixel fusion consumes outputs from all four models. Real-ESRGAN/Waifu2x/Real-CUGAN supply the majority of permitted edge detail; Anime4K only supplies bounded, agreeing edge detail. The fusion retains the original accepted V2 colours, ICC, print DPI and alpha, protects explicitly selected face rectangles and can preserve the entire V2 portrait when automatic face restoration ran without known rectangles.
- After all four pass their individual PNG checks and the fusion gate, save a **separate experimental `*.V211-4AI-QA-xxxxxxxx.png`** next to the V2 print file, and show it as the right-hand preview. It is NOT an automatically accepted or quality-certified print export.
- Intermediate candidate images are deleted by default; explicit `NIYOMSIL_V211_FOUR_AI_EVIDENCE_DIR` can retain them in a private local QA folder for A/B. Customer images must not be uploaded publicly.
- Normal V2 export, TIFF/PDF jobs, unsupported scales, incomplete model installations and machine failures fail closed back to V2 instead of blocking the customer's completed V2 export.

## Windows first-run

In the experimental `v2.1.1` desktop app, one-time confirmation allows downloads of approved upstream packages. After setup, processing eligible 2x jobs calls the four engines automatically, without four per-model switches. There is **no surprise download**; setup can be declined. The models stay under `%LOCALAPPDATA%\NiyomSilp\V211-FourAI-QA`. Optional environment override is `NIYOMSIL_V211_FOUR_AI_MANIFEST`; `NIYOMSIL_V211_FOUR_AI=0` disables research explicitly.

Real-ESRGAN, Waifu2x and Real-CUGAN were previously exercised individually on the shop Windows PC as reported by the owner. That is **not** proof that the newly integrated four-model fusion has passed an A/B comparison on that PC.

## Limitations and unresolved gates

- Only PNG V2 output from an exact **2x** source is supported for the auxiliary four AI integration in this beta; auxiliary limit is **18 megapixels**. Large-format V2 output continues with existing V2 processing; four-model large-image tiling must be built separately before claiming full-size print support.
- A passing Windows installer build proves packaging, not real model inference inside the packaged app. GitHub Windows hosted-runner currently allows Real-CUGAN/Anime4K synthetic real-CLI smoke outputs but Real-ESRGAN/Waifu2x hit `vkCreateInstance failed -9` without a usable Vulkan GPU. The user's Windows PC with GTX 1660 Ti is the relevant test machine for end-to-end fusion.
- Experimental fusion on raster candidates is real implemented code, **not yet proof of better visual quality**. No OCR/retyping is used. The four models' detail contributions must be measured and reviewed for Thai/English/Chinese small lettering, people, animals, objects, line art, flat green areas, gradient ramps, transparency/halo and GFPGAN face retention.
- GPU workload, face ROI auto detection, proper cancellation of subprocesses, memory-bounded four-model processing for large signs, and quality-certified replacement of the print export remain open work.
- Model/engine redistribution and license compliance (including Anime4KCPP GPL) must be reviewed before deciding to bundle third-party binaries into installers; currently models are downloaded directly from their original publishers with user permission.

## Release acceptance

Keep PR #18 and PR #20 unmerged as Draft pending successful GTX 1660 Ti local QA and human review. Never tell the shop that four-engine output is superior to V2 until actual side-by-side evidence supports that statement.
