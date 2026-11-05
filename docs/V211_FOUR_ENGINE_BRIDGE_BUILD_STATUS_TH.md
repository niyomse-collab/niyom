# NiyomSilp V2.1.1 — Four real AI engines integrated in Windows experimental build (4 November 2026)

Branch: work/v211-four-engine-v2-bridge-20261103 / Draft PR #20.
Do not merge/release as accepted V2.1.1 until the shop approves side-by-side image QA.

## Implemented in experimental branch

- Keep V2 Real-ESRGAN main enhancement, GFPGAN face restoration, sliders, Windows output behaviour and alpha/ICC/DPI print path unchanged.
- Once the user confirms a one-time download, install four native upstream AI executables plus their model assets in private LOCALAPPDATA and validate archive SHA256 and a SHA256-checked manifest. Subsequent usage is offline. Executables/weights are not bundled in our distributed installer.
- For supported RGB/RGBA raster outputs (PNG/JPEG/TIFF), the app prepares a private half-target seed from the original source and runs all four installed native 2x executables sequentially. Odd V2 dimensions are edge-padded for inference and cropped back for the QA PNG. This allows custom, 4x and 8x target dimensions to enter the same 2x native pass; it is not native 4x/8x inference or a multi-pass claim. Missing engines never result in a false claim of completed fusion; accepted V2 stays untouched.
- An additional tiled pixel fusion consumes outputs from all four models. Real-ESRGAN/Waifu2x/Real-CUGAN supply the majority of permitted edge detail; Anime4K only supplies bounded, agreeing edge detail. The fusion retains the original accepted V2 colours, ICC, print DPI and alpha, protects explicitly selected face rectangles and can preserve the entire V2 portrait when automatic face restoration ran without known rectangles.
- After all four pass their individual PNG checks and the fusion gate, save a separate experimental *.V211-4AI-QA-xxxxxxxx.png next to the V2 print file, and show it as the right-hand preview. It is NOT an automatically accepted or quality-certified print export.
- Intermediate candidate images are deleted by default; explicit NIYOMSIL_V211_FOUR_AI_EVIDENCE_DIR can retain them in a private local QA folder for A/B. Customer images must not be uploaded publicly.
- Normal V2 export, PDF/PSD/CMYK jobs, unsupported scales, incomplete model installations and machine failures fail closed back to V2 instead of blocking the customer's completed V2 export. RGB/RGBA TIFF and JPEG are supported only as raster inputs to a separate PNG QA sidecar; the original print export remains unchanged.

## Windows setup-time provisioning

The experimental installer offers an **unchecked-by-default affirmative-consent task**. The user must actively tick “I agree: download and install all four AI engines for offline use” before any network download starts. If selected, it runs the packaged setup command under the installing user's account, downloads the official upstream archives, verifies SHA256 and archive contents, then installs into %LOCALAPPDATA%\NiyomSilp\V211-FourAI-QA. The setup must finish before the installer offers to launch the editor. This keeps the download/consent step inside installation; opening the image editor never triggers a download or consent prompt. The task can be unchecked for an offline/no-download installation; in that case the accepted V2 processing path remains available and the four-engine research bridge reports models not installed. Subsequent eligible jobs use the installed engines offline, without per-model switches.

The command is NiyomsilAIEnhancer.exe --provision-v211-four-ai; the frozen import smoke includes its CLI module. Optional environment override is NIYOMSIL_V211_FOUR_AI_MANIFEST; NIYOMSIL_V211_FOUR_AI=0 disables research explicitly.

Real-ESRGAN, Waifu2x and Real-CUGAN were previously exercised individually on the shop Windows PC as reported by the owner. That is not proof that the newly integrated four-model fusion has passed an A/B comparison on that PC.

## Limitations and unresolved gates

- The auxiliary route currently supports RGB/RGBA PNG, JPEG and TIFF V2 rasters up to 18 megapixels. It uses a native 2x engine pass on a seed sized to half the padded V2 target, so arbitrary output dimensions including 4x/8x targets can be previewed without claiming native 4x/8x inference. CMYK, PDF, PSD and outputs above 18MP remain V2-only; large-format four-engine tile streaming is still pending.
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
- The auxiliary route now normalizes arbitrary RGB/RGBA PNG/JPEG/TIFF target dimensions to a fixed native 2x engine pass using a half-target seed, including edge-padding/cropping for odd dimensions. It remains limited to <=18MP and is not native 4x/8x or multi-pass inference. PDF/PSD, CMYK and larger jobs still continue through V2 only.
- These are integration and cancellation safeguards, not evidence of real inference on the shop GPU or improved image quality. The four-engine Windows candidate build and the owner's GTX 1660 Ti A/B review remain release gates.

## 5 November 2026 — installer completion gate hardening

- The installer removes stale success state before the selected provisioning task runs and creates a fresh setup-pending.flag marker for that attempt.
- The first installer Run entry performs provisioning before the optional editor launch. Silent installations pass --silent, still run the selected provisioning task, and record a local setup log instead of creating a hidden Tk window.
- The setup CLI publishes setup-complete.flag atomically only after all four exact engine names and the terminal setup status have been verified, then removes the pending marker.
- The editor launch Run entry is gated by the fresh completion marker and absence of the pending marker whenever the four-engine task is selected. A failed or incomplete provisioning attempt therefore cannot reuse an old success marker or launch the editor as if setup succeeded.
- The custom installer exit code is evaluated at ssDone, after all Run entries have completed. Checking at ssPostInstall was too early because the provisioning command had not yet published its fresh completion marker; the gate now also covers silent installs where editor launch is skipped.
- If the selected four-engine setup did not publish a fresh marker, Inno Setup returns a nonzero custom exit code. If the task is unchecked, the editor can still launch and the accepted V2 path remains available.
- This is source-level and CI-testable installer control flow. The packaged installer still requires a real interactive and silent Windows install/uninstall test before customer deployment.


## 5 November 2026 — arbitrary raster target-size normalization

- The bridge now derives a private half-target seed from the original raster and runs each fixed 2x native CLI once, then fuses against the accepted V2 raster at its requested dimensions. This supports custom/stretch dimensions and 4x/8x target sizes within the 18MP auxiliary budget without pretending that the native model itself ran at 4x/8x.
- Odd target dimensions are edge-padded to even dimensions for the 2x engines and cropped back before the QA sidecar is published. RGB/RGBA PNG, JPEG and TIFF V2 rasters are accepted; TIFF/JPEG outputs produce a local PNG QA sidecar and the original print file is not modified.
- CMYK, PDF, PSD and targets above 18MP remain on the accepted V2 path only. No native large-image streaming or print-quality promotion is claimed.


## 5 November 2026 — Fit/Stretch geometry alignment

- The native 2x seed now follows the same resize policy as the accepted V2 raster. `stretch` fills the half-target dimensions; `fit` preserves the source aspect ratio and centers it on the same background as the V2 reference.
- This prevents the four auxiliary models from generating displaced edges on wide/tall artwork and then blending those displaced details onto a letterboxed V2 image.
- The V2 adapter passes its actual resize mode to the bridge. The QA report records the mode used.
- Synthetic regression covers a 2:1 source fitted to a square target and the corresponding stretch case. This is geometry correctness only, not visual-quality certification.


## 6 พฤศจิกายน 2569 — per-engine pixel contribution gate

- Fusion เพิ่มการวัดแบบ leave-one-engine-out: คำนวณผล RGB ปลายทางซ้ำโดยถอด contribution ของ Engine ทีละตัว แล้วเปรียบเทียบหลัง edge gating, luminance clipping และ quantization
- `engine_pixel_effect_pixels` และ `engine_pixel_effect_verified` แสดงว่าการตัด Engine แต่ละตัวออกทำให้พิกเซล RGB ของผลลัพธ์เปลี่ยนจริงหรือไม่
- Bridge จะรายงาน `four_engine_fusion_preview_ready` เฉพาะเมื่อทั้งสี่ Engine เปลี่ยนพิกเซลปลายทางอย่างน้อยหนึ่งตำแหน่ง; หากไม่ครบจะใช้ `four_engine_fusion_contribution_incomplete` และ UI แจ้งเตือนอย่างชัดเจน
- QA sidecar ยังคงแยกจาก accepted V2 raster; ไม่มีการ promote candidate เป็นไฟล์ส่งพิมพ์ และ `quality_certified=false` เสมอจนกว่าจะผ่าน Native inference บนเครื่องร้านและ A/B review
- Synthetic regression บน HEAD `422c2fe487e039345fb31203066b5912702e5e39`: Independent Core Windows **691 passed, 1 skipped**; Ubuntu **689 passed, 3 skipped**; compileall ผ่านทั้งสองระบบ — [GitHub Actions #42104603371](https://github.com/niyomse-collab/niyom/actions/runs/42104603371)
- Windows Candidate Build เป็น push-triggered workflow; run ล่าสุดของ candidate ยังไม่มี run/artifact ที่ยืนยันได้จากข้อมูลที่ตรวจรอบนี้ จึงไม่ใช้ Candidate รุ่นเก่าหรือ Regression run มาแทนหลักฐาน Installer
- ตรวจ PR #18 แล้ว: SHA256 ของ `face_module/face_protection.py` และ `large_faces.py` ตรงกับ PR #20; ไฟล์ Face/GFPGAN เหล่านี้ไม่ได้ถูกแก้ใน PR #20

## 6 พฤศจิกายน 2569 — Windows V2.1.1 candidate build สำเร็จ

- Windows candidate run **#42104504040** สำเร็จบน code commit `810884321a0cbc1ad8d1c8facf0502b7f37ce191`: bridge-tests ผ่าน, Inno Setup compile ผ่าน, PyInstaller build ผ่าน, packaged imports smoke ผ่าน และอัปโหลด artifact สำเร็จ — [GitHub Actions #42104504040](https://github.com/niyomse-collab/niyom/actions/runs/42104504040)
- PR #20 HEAD ปัจจุบัน `aad0112042d2cca64c84f3747c0d552ee722bb3c` มี commit หลัง build ที่เปลี่ยนเฉพาะเอกสารสองรายการ (`docs/V211_WINDOWS_REAL_FOUR_ENGINE_QA_TH.md` และเอกสารสถานะนี้); ไม่มี Source หรือ Installer logic เปลี่ยนหลัง code commit ที่ Build ผ่าน
- Artifact: [NiyomSilp-V2.1.1-four-engine-bridge-EXPERIMENTAL](https://github.com/niyomse-collab/niyom/actions/runs/42104504040/artifacts/13453780090), ขนาด 2,583,985,588 bytes. Installer `NiyomSilp-Design-v211-EXPERIMENTAL-Setup.exe` SHA256: `09bb700df05af0c42e6eb3e2871dfc86fa661764f2ecaa981f5da463e23a0731`. Artifact เป็น candidate ทดลองเท่านั้น ไม่มี Release เผยแพร่
- Build log มี PyInstaller collection warnings บางโมดูล รวมถึง `torchvision.transforms.functional_tensor` และ `nvcuda.dll`; runtime compatibility hook อยู่ใน package และ packaged imports smoke ผ่านแล้ว. อย่างไรก็ตาม import smoke ไม่ใช่การทดสอบ GUI, inference, GPU หรือการติดตั้ง/ถอนการติดตั้งจริงบนเครื่องร้าน
- Latest Independent Core regression ที่ PR HEAD `aad0112`: Windows **691 passed, 1 skipped**; Ubuntu **689 passed, 3 skipped**; compileall ผ่านทั้งสองระบบ — [GitHub Actions #42104965348](https://github.com/niyomse-collab/niyom/actions/runs/42104965348)
- Intermediate regression failures `#42104393057` และ `#42104495980` เกิดจาก assertions ใน tests ที่ยังคาดหวัง status เดิม `four_engine_fusion_preview_ready`; หลังปรับ tests ให้ตรวจ per-engine pixel contribution gate แล้ว regression ล่าสุดผ่าน. ไม่ได้เปลี่ยน gate กลับเพื่อทำให้ tests ผ่าน
- Candidate build และ synthetic regression ยังไม่รับรอง Native inference ทั้งสี่บน GTX 1660 Ti, ไม่รับรอง GPU adapter, A/B quality, 18MP+ tiling, interactive/silent install-uninstall หรือ print output. คง `quality_certified=false`; ห้าม merge/release จนกว่าจะผ่านการทดสอบบนเครื่องร้านและผู้ใช้อนุมัติ
