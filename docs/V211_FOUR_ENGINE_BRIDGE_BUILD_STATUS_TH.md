# NiyomSilp V2.1.1 — Four real AI engines integrated in Windows experimental build (4 November 2026)

Branch: work/v211-four-engine-v2-bridge-20261103 / Draft PR #20.
Do not merge/release as accepted V2.1.1 until the shop approves side-by-side image QA.

## Implemented in experimental branch

- Keep V2 Real-ESRGAN main enhancement, GFPGAN face restoration, sliders, Windows output behaviour and alpha/ICC/DPI print path unchanged.
- Once the user confirms a one-time download, install four native upstream AI executables plus their model assets in private LOCALAPPDATA and validate archive SHA256 and a SHA256-checked manifest. Subsequent usage is offline. Executables/weights are not bundled in our distributed installer.
- For a supported 2x AI PNG output, the app calls all four actual installed native executables sequentially on the original input. Missing engines never result in a false claim of a completed fusion; the accepted V2 output stays untouched.
- An additional tiled pixel fusion consumes outputs from all four models. Real-ESRGAN/Waifu2x/Real-CUGAN supply the majority of permitted edge detail; Anime4K only supplies bounded, agreeing edge detail. The fusion retains the original accepted V2 colours, ICC, print DPI and alpha, protects explicitly selected face rectangles and can preserve the entire V2 portrait when automatic face restoration ran without known rectangles.
- After all four pass their individual PNG checks and the fusion gate, save a separate experimental *.V211-4AI-QA-xxxxxxxx.png next to the V2 print file, and show it as the right-hand preview. It is NOT an automatically accepted or quality-certified print export.
- Intermediate candidate images are deleted by default; explicit NIYOMSIL_V211_FOUR_AI_EVIDENCE_DIR can retain them in a private local QA folder for A/B. Customer images must not be uploaded publicly.
- Normal V2 export, TIFF/PDF jobs, unsupported scales, incomplete model installations and machine failures fail closed back to V2 instead of blocking the customer's completed V2 export.

## Windows setup-time provisioning

The experimental installer offers a checked-by-default Install all four AI engines for offline use task. If selected, it runs the packaged setup command under the installing user's account, downloads the official upstream archives, verifies SHA256 and archive contents, then installs into %LOCALAPPDATA%\NiyomSilp\V211-FourAI-QA. The setup must finish before the installer offers to launch the editor. This keeps the download/consent step inside installation; opening the image editor never triggers a download or consent prompt. The task can be unchecked for an offline/no-download installation; in that case the accepted V2 processing path remains available and the four-engine research bridge reports models not installed. Subsequent eligible jobs use the installed engines offline, without per-model switches.

The command is NiyomsilAIEnhancer.exe --provision-v211-four-ai; the frozen import smoke includes its CLI module. Optional environment override is NIYOMSIL_V211_FOUR_AI_MANIFEST; NIYOMSIL_V211_FOUR_AI=0 disables research explicitly.

Real-ESRGAN, Waifu2x and Real-CUGAN were previously exercised individually on the shop Windows PC as reported by the owner. That is not proof that the newly integrated four-model fusion has passed an A/B comparison on that PC.

## Limitations and unresolved gates

- Only PNG V2 output from an exact 2x source is supported for the auxiliary four AI integration in this beta; auxiliary limit is 18 megapixels. Large-format V2 output continues with existing V2 processing; four-model large-image tiling must be built separately before claiming full-size print support.
- A passing Windows installer build proves packaging, not real model inference inside the packaged app. GitHub Windows hosted-runner currently allows Real-CUGAN/Anime4K synthetic real-CLI smoke outputs but Real-ESRGAN/Waifu2x hit vkCreateInstance failed -9 without a usable Vulkan GPU. The user's Windows PC with GTX 1660 Ti is the relevant test machine for end-to-end fusion.
- Experimental fusion on raster candidates is real implemented code, not yet proof of better visual quality. No OCR/retyping is used. The four models' detail contributions must be measured and reviewed for Thai/English/Chinese small lettering, people, animals, objects, line art, flat green areas, gradient ramps, transparency/halo and GFPGAN face retention.
- Native subprocess cancellation is now wired through the sequential runner: on Windows it terminates the process tree; on POSIX it terminates the process group. Fusion also checks cancellation between bounded tiles. CI regression tests cover cancellation and temporary-output cleanup, but the Windows GPU process-tree behavior still needs verification on the shop PC.
- Automatic face ROI detection, memory-bounded four-model processing for large signs, and quality-certified replacement of the print export remain open work.
- Model/engine redistribution and license compliance (including Anime4KCPP GPL) must be reviewed before deciding to bundle third-party binaries into installers; currently models are downloaded directly from their original publishers with user permission.

## Release acceptance

Keep PR #18 and PR #20 unmerged as Draft pending successful GTX 1660 Ti local QA and human review. Never tell the shop that four-engine output is superior to V2 until actual side-by-side evidence supports that statement.

## 5 November 2026 — post-save QA and cancellation integration

- The V2 adapter now completes and writes the accepted V2 export before calling maybe_run_four_engine_assist. The old pre-save in-memory research hook is no longer the app's execution path.
- The app receives the bridge's four_engine_fusion_output path, so the right-hand preview can display the actual separate *.V211-4AI-QA-*.png sidecar when all four engines and fusion succeed.
- Cancellation is passed from the V2 job into each native subprocess and into tiled fusion. A cancelled or failed auxiliary run reports its own status and leaves the saved V2 file intact; incomplete persistent evidence folders are removed on cancellation.
- The supported auxiliary route remains exact 2x RGB/RGBA PNG and <=18 MP. Other scales, TIFF/PDF/CMYK, and larger jobs continue through V2 only and are explicitly reported as unsupported for the four-engine sidecar.
- These are integration and cancellation safeguards, not evidence of real inference on the shop GPU or improved image quality. The four-engine Windows candidate build and the owner's GTX 1660 Ti A/B review remain release gates.

## 5 November 2026 — installer completion gate hardening

- The installer removes stale success state before the selected provisioning task runs and creates a fresh setup-pending.flag marker for that attempt.
- The first installer Run entry performs provisioning before the optional editor launch. Silent installations pass --silent, still run the selected provisioning task, and record a local setup log instead of creating a hidden Tk window.
- The setup CLI publishes setup-complete.flag atomically only after all four exact engine names and the terminal setup status have been verified, then removes the pending marker.
- The editor launch Run entry is gated by the fresh completion marker and absence of the pending marker whenever the four-engine task is selected. A failed or incomplete provisioning attempt therefore cannot reuse an old success marker or launch the editor as if setup succeeded.
- Inno Setup captures a nonzero custom installer exit code if the selected four-engine setup did not publish a fresh marker. If the task is unchecked, the editor can still launch and the accepted V2 path remains available.
- This is source-level and CI-testable installer control flow. The packaged installer still requires a real interactive and silent Windows install/uninstall test before customer deployment.
