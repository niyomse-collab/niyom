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
- ตรวจ PR #18 แล้ว: Git blob SHA ของ `face_module/face_protection.py` และ `large_faces.py` ตรงกับ PR #20 (เป็นค่า Git object SHA ไม่ใช่ SHA256 ของ bytes ในไฟล์); ไฟล์ Face/GFPGAN เหล่านี้ไม่ได้ถูกแก้ใน PR #20

## 6 พฤศจิกายน 2569 — Windows V2.1.1 candidate build สำเร็จ

- Windows candidate run **#42104504040** สำเร็จบน code commit `810884321a0cbc1ad8d1c8facf0502b7f37ce191`: bridge-tests ผ่าน, Inno Setup compile ผ่าน, PyInstaller build ผ่าน, packaged imports smoke ผ่าน และอัปโหลด artifact สำเร็จ — [GitHub Actions #42104504040](https://github.com/niyomse-collab/niyom/actions/runs/42104504040)
- Candidate สร้างจาก code SHA `810884321a0cbc1ad8d1c8facf0502b7f37ce191`; commit ถัดมา `422c2fe`, `aad0112` และการบันทึกสถานะนี้เปลี่ยนเฉพาะเอกสาร (`docs/V211_WINDOWS_REAL_FOUR_ENGINE_QA_TH.md` และเอกสารสถานะนี้) ไม่มี Source หรือ Installer logic เปลี่ยนหลัง code commit ที่ Build ผ่าน
- Artifact: [NiyomSilp-V2.1.1-four-engine-bridge-EXPERIMENTAL](https://github.com/niyomse-collab/niyom/actions/runs/42104504040/artifacts/13453780090), ขนาด 2,583,985,588 bytes. Installer `NiyomSilp-Design-v211-EXPERIMENTAL-Setup.exe` SHA256: `09bb700df05af0c42e6eb3e2871dfc86fa661764f2ecaa981f5da463e23a0731`. Artifact เป็น candidate ทดลองเท่านั้น ไม่มี Release เผยแพร่
- Build log มี PyInstaller collection warnings บางโมดูล รวมถึง `torchvision.transforms.functional_tensor` และ `nvcuda.dll`; runtime compatibility hook อยู่ใน package และ packaged imports smoke ผ่านแล้ว. อย่างไรก็ตาม import smoke ไม่ใช่การทดสอบ GUI, inference, GPU หรือการติดตั้ง/ถอนการติดตั้งจริงบนเครื่องร้าน
- Independent Core regression บน commit `aad0112` (docs-only descendant ของ code SHA ที่ Build): Windows **691 passed, 1 skipped**; Ubuntu **689 passed, 3 skipped**; compileall ผ่านทั้งสองระบบ — [GitHub Actions #42104965348](https://github.com/niyomse-collab/niyom/actions/runs/42104965348)
- Intermediate regression failures `#42104393057` และ `#42104495980` เกิดจาก assertions ใน tests ที่ยังคาดหวัง status เดิม `four_engine_fusion_preview_ready`; หลังปรับ tests ให้ตรวจ per-engine pixel contribution gate แล้ว regression ล่าสุดผ่าน. ไม่ได้เปลี่ยน gate กลับเพื่อทำให้ tests ผ่าน
- Candidate build และ synthetic regression ยังไม่รับรอง Native inference ทั้งสี่บน GTX 1660 Ti, ไม่รับรอง GPU adapter, A/B quality, 18MP+ tiling, interactive/silent install-uninstall หรือ print output. คง `quality_certified=false`; ห้าม merge/release จนกว่าจะผ่านการทดสอบบนเครื่องร้านและผู้ใช้อนุมัติ

## 6 พฤศจิกายน 2569 — เรียก Four-Engine QA หลัง V2 disk-tile สำหรับงานไม่เกิน 18MP

- ก่อนหน้านี้ Core Adapter คืนผลจาก `process_large` ทันทีเมื่อ V2 เลือก disk-tile path ทำให้ Four-Engine Bridge ไม่ถูกเรียก แม้ source และภาพ V2 สุดท้ายจะยังอยู่ภายในงบของ Bridge
- ปรับ Adapter ให้ V2 บันทึกไฟล์เสร็จก่อน แล้วจึงเรียก Four-Engine Bridge ต่อสำหรับงานที่ทั้ง source และ target ไม่เกิน 18MP โดยยังคงใช้ V2 disk-tile path เดิมและส่งต่อ Cancel/face-protection/resize mode
- งานที่ source หรือ target เกิน 18MP ยังคงประมวลผล V2 ตามเดิม แต่รายงาน `large_image_tiling_pending`; ไม่มีการเริ่ม Native AI สี่ตัวในกรณีนี้
- Bridge ตรวจขนาด source และ target จาก header ก่อน EXIF transpose, convert หรือ edge-pad เพื่อไม่ให้ภาพเกินงบถูกคัดลอกเข้า RAM ก่อนถูกปฏิเสธ
- นี่เป็นการขยายการเชื่อมต่อหลัง V2 disk-tile สำหรับงานไม่เกิน 18MP เท่านั้น **ยังไม่ใช่ Four-Engine tile streaming สำหรับภาพเกิน 18MP**; Candidate images และ Fusion ยังใช้ Pillow full-image memory ภายในเพดานดังกล่าว
- ยังต้องทดสอบ RAM/VRAM 6GB, cancel ระหว่าง Native subprocess, Native inference บน GTX 1660 Ti และ A/B ภาพจริงก่อนรับรองคุณภาพ

## 6 พฤศจิกายน 2569 — ตรวจ CI และ Candidate ล่าสุดของ PR #20

- PR #20 ยังคงเป็น **Open / Draft / Not Merged** บนสาขา `work/v211-four-engine-v2-bridge-20261103`; HEAD ก่อนบันทึกสถานะนี้คือ `5de1637aae760e915dab5d1219b16ae75020473c`.
- Windows Candidate Build **#42120682388** สำเร็จทั้ง `bridge-tests` และ `windows-v2-candidate` บน code SHA `bd2d70993c6ef81e00381d38294c5f60f71e8b54`: Inno Setup compile, PyInstaller frozen build, packaged-import smoke และ artifact upload ผ่าน — [GitHub Actions #42120682388](https://github.com/niyomse-collab/niyom/actions/runs/42120682388).
- Installer ที่สร้างใน run นี้คือ `NiyomSilp-Design-v211-EXPERIMENTAL-Setup.exe`; SHA256 จาก Build Log: `f6e0b979148224c291792618efabff43269dc333ae47038c564e87457d307007`.
- Artifact ID `13458799960`, ขนาด `2,584,051,721` bytes; SHA256 ของ **ZIP artifact** คือ `4df4880cd9eea87825e7d715c833fb3fffe4789ceaefa84921ed9351f60c9467` (คนละค่าและคนละไฟล์กับ Installer SHA256). [ดาวน์โหลด Candidate Artifact](https://github.com/niyomse-collab/niyom/actions/runs/42120682388/artifacts/13458799960).
- เปรียบเทียบ Candidate code SHA กับ PR HEAD พบว่า HEAD ปัจจุบันมีเพิ่มเพียง 1 commit ที่เปลี่ยน `tests/test_large_image.py` จำนวน 1 บรรทัดเพิ่ม/1 บรรทัดลบ; ไม่มี production source, PyInstaller spec หรือ Installer logic เปลี่ยนหลัง Candidate Build. ดังนั้นตัวโปรแกรมใน Candidate ตรงกับ production source ปัจจุบัน แต่ Candidate workflow ไม่ได้ Build ซ้ำบน HEAD ใหม่เพราะ path filter ของ Windows workflow ไม่รวม `tests/test_large_image.py`; regression workflow ตรวจ HEAD ปัจจุบันแยกต่างหากแล้ว.
- Independent Core regression บน PR HEAD `5de1637aae760e915dab5d1219b16ae75020473c` ผ่าน: Windows **695 passed, 1 skipped**; Ubuntu **693 passed, 3 skipped**; compileall ผ่านทั้งสองระบบ — [GitHub Actions #42120858426](https://github.com/niyomse-collab/niyom/actions/runs/42120858426).
- Build Log ยังมี PyInstaller warnings เรื่อง `torchvision.transforms.functional_tensor`, `scipy.special._cdflib`, `nvcuda.dll` และ `tbb12.dll`; Build และ packaged-import smoke ผ่าน แต่ warning เหล่านี้ยังต้องตรวจ runtime GFPGAN/CUDA บนเครื่องจริง. การไม่มี `nvcuda.dll` บน Hosted Runner ไม่ใช่ผลทดสอบ GTX 1660 Ti.
- Official archive audit ล่าสุดที่ตรวจได้คือ run **#42024220154** บน commit `a36165b08e2dcebc439c5685f08f5fc0877dbb81`; audit tool, provisioner และ manifest loader ไม่ได้เปลี่ยนหลัง run นั้น. ZIP ทั้งสี่ผ่าน archive/hash audit; Waifu2x และ Anime4KCPP มี upstream release digest, ส่วน Real-ESRGAN และ Real-CUGAN ใช้ recorded CI SHA256 เพราะ upstream ไม่มี digest. รายงานยังคง `license_redistribution_approved=false` และ `real_inference_verified=false` — [GitHub Actions #42024220154](https://github.com/niyomse-collab/niyom/actions/runs/42024220154).
- Native CLI smoke ล่าสุดที่ตรวจ log ได้คือ run **#42064430048** บน commit เก่ากว่า `2b3c011a85e671bce67a4414d511cdb1bcadc825`: Real-CUGAN และ Anime4KCPP สร้าง output ที่ผ่านการตรวจเบื้องต้น; Real-ESRGAN และ Waifu2x ถูก block ด้วย `vkCreateInstance failed -9` บน Hosted Runner. `real_inference_verified=false`. QA script/workflow มีการเปลี่ยนหลัง commit นั้น จึงต้อง rerun smoke บน HEAD ปัจจุบันก่อนใช้อ้างอิงผลของ QA code ล่าสุด; run นี้ไม่ใช่หลักฐาน GPU ร้าน — [GitHub Actions #42064430048](https://github.com/niyomse-collab/niyom/actions/runs/42064430048).
- ตรวจไฟล์ Face/GFPGAN ระหว่าง PR #18 และ PR #20: `signprint_ai/face_module/face_protection.py` Git blob SHA `7795bfd409e68e17c80ef0b401b8c099074e22b8`, `signprint_ai/large_faces.py` Git blob SHA `0faafd0c442e156def34faee7fbf98fc65cf754f`, และ `signprint_ai/face_module/__init__.py` Git blob SHA `19f02356a689fd068b12a7240fabbbe62c878352` ตรงกันทั้งสอง PR (เป็น Git object IDs ไม่ใช่ file-content SHA256).
- Candidate, regression และ archive audit ไม่พิสูจน์ Native inference ทั้งสี่บน GTX 1660 Ti, adapter/device ที่ Engine ใช้จริง, RAM/VRAM 6GB, 18MP+ streaming, 4x/8x multi-pass, A/B หรือคุณภาพงานพิมพ์. คง `quality_certified=false`; PR #20 และ PR #18 ต้องเป็น Draft ต่อไปจนผ่าน QA เครื่องร้านและผู้ใช้อนุมัติ.

## 6 พฤศจิกายน 2569 — ผล Windows Candidate และ Regression หลังแก้ BasicSR packaging

- PR #20 HEAD ที่ทดสอบคือ `b0e75779a328a765f1746cbe98e882d8f6904c54` บนสาขา `work/v211-four-engine-v2-bridge-20261103`; PR ยังคง Open / Draft / Not Merged.
- แก้ PyInstaller analysis path: `NiyomsilV2ArmCore.spec` ติดตั้ง compatibility alias แบบจำกัดสำหรับ `torchvision.transforms.functional_tensor.rgb_to_grayscale` ก่อน static filesystem discovery ผ่าน `discover_package_modules`; ไม่เรียก `collect_submodules("basicsr")` ใน isolated interpreter และยังคง runtime hook `pyi_rth_basicsr_compat.py`.
- Windows Candidate run **#42133672277** สร้างจาก HEAD เดียวกันและสำเร็จทั้ง `bridge-tests` กับ `windows-v2-candidate`: bridge tests **111 passed**; Inno Setup compile, PyInstaller frozen build, packaged imports smoke (`Test-V2-Package.ps1 -Mode imports`) และ artifact upload ผ่าน — [GitHub Actions #42133672277](https://github.com/niyomse-collab/niyom/actions/runs/42133672277).
- Installer: `NiyomSilp-Design-v211-EXPERIMENTAL-Setup.exe`; SHA256 จาก Build Log: `295623a3d39a232d41a56ff14d7e3c5f230de91505fc0ed6157c758b5ada9949`.
- Artifact ID `13465963318`, ขนาด `2,584,386,813` bytes; SHA256 ของ ZIP artifact: `ab6a4e4a7fd82217e083ed91c4e9fcf7625c1bb4d9612e2050dbc20fbc819415`. [ดาวน์โหลด Candidate Artifact](https://github.com/niyomse-collab/niyom/actions/runs/42133672277/artifacts/13465963318). Artifact หมดอายุวันที่ 13 พฤศจิกายน 2569 เวลา 00:32 UTC หากยังไม่ดาวน์โหลดก่อนหน้านั้นต้องสร้าง artifact ใหม่.
- Independent Core regression บน HEAD เดียวกัน **#42133684495** ผ่านทั้งสองระบบ: Windows **696 passed, 1 skipped**; Ubuntu **694 passed, 3 skipped**; `compileall` ผ่านทั้งคู่ — [GitHub Actions #42133684495](https://github.com/niyomse-collab/niyom/actions/runs/42133684495).
- Build Log ไม่พบคำเตือน missing import เดิม `torchvision.transforms.functional_tensor`; ยังมีคำเตือน PyInstaller อื่น เช่น `pycparser.lextab/yacctab`, `scipy.special._cdflib`, `nvcuda.dll`, `tbb12.dll` และ dependency/deprecation notices. สิ่งเหล่านี้ไม่ทำให้ Candidate Build หรือ packaged-import smoke ล้ม แต่ยังต้องตรวจ runtime บนเครื่องจริง; `nvcuda.dll` ที่ไม่พบใน Hosted Runner ไม่ใช่หลักฐานว่า GTX 1660 Ti ของร้านมีปัญหา.
- ความยินยอมดาวน์โหลดอยู่ใน Inno Setup เป็น task ที่ **ไม่เลือกไว้โดยค่าเริ่มต้น**; ผู้ใช้ต้องเลือกข้อความยินยอมเองจึงเริ่มดาวน์โหลด/ตรวจ SHA256 ไปยัง LOCALAPPDATA ก่อนเสนอเปิดโปรแกรม. หากไม่เลือก โปรแกรมยังใช้ V2 เดิมได้และไม่มีการดาวน์โหลด. การเปิด Editor เองไม่แสดง consent prompt; นี่เป็น installer-time consent ไม่ใช่ first-launch prompt.
- ตรวจ PR #18 เทียบ PR #20 base/head: Git blob SHA ของ `signprint_ai/face_module/face_protection.py` = `7795bfd409e68e17c80ef0b401b8c099074e22b8`, `signprint_ai/large_faces.py` = `0faafd0c442e156def34faee7fbf98fc65cf754f`, และ `signprint_ai/v211_face_contract.py` = `4d63a947301b559f37bfb68e283b8cd872fcde19` ตรงกันระหว่าง PR #20 base และ head; PR #18 ยัง Open / Draft และไม่มี review submission ใหม่. ค่าเหล่านี้เป็น Git blob IDs ไม่ใช่ SHA256 ของไฟล์.
- Candidate Build และ packaged-import smoke **ไม่ใช่** การติดตั้ง/ถอนการติดตั้งจริง, GUI/runtime GFPGAN test, Native inference, การยืนยันว่า Engine เลือก GTX 1660 Ti adapter, หรือ visual/print QA. Native inference ทั้งสี่บนเครื่องร้าน, RAM/VRAM 6GB, 18MP+ four-engine streaming, native 4x/8x multi-pass, A/B และสิทธิ์ model weights ยังไม่ผ่านการรับรอง. คง `quality_certified=false`; ห้าม Merge/Release จนผ่าน QA เครื่องร้านและผู้ใช้อนุมัติ.


## 6 พฤศจิกายน 2569 — ตรวจ HEAD ล่าสุดหลังแก้ Manifest Validation

- PR #20 HEAD: `11fc95195ce7a07764a5c4483e09d4efaf78dc61`; สถานะ Open / Draft / Not Merged. Commit `437338149055ce8b7ac8c1b0a8f3c05f41dcb957` แก้ `signprint_ai/v211_auto_setup.py` ให้ไม่ถือว่า Manifest ที่มีเพียงไฟล์อยู่เป็นการติดตั้งสำเร็จ แต่เรียก `load_real_engine_manifest()` และต้องตรวจผ่านครบชื่อ Engine ทั้งสี่; Commit `11fc95195ce7a07764a5c4483e09d4efaf78dc61` เพิ่ม tests สำหรับ placeholder manifest และ explicit override ที่มี Engine ไม่ครบ.
- Windows Candidate Build **#42144813089** สำเร็จบน HEAD เดียวกัน: `bridge-tests` และ `windows-v2-candidate` ผ่าน; Bridge suite **112 passed in 2.79s**; Inno Setup compile, PyInstaller frozen build, packaged V2 imports smoke และ artifact upload ผ่าน — [GitHub Actions #42144813089](https://github.com/niyomse-collab/niyom/actions/runs/42144813089).
- Installer: `NiyomSilp-Design-v211-EXPERIMENTAL-Setup.exe`; SHA256 จาก Build Log: `bac1d1c3d482601e559f6f38b5a721bb65787781007f9ade0ec144e375da2539`.
- Artifact ID `13470383540`, ขนาด `2,584,347,716` bytes; SHA256 ของ ZIP artifact: `00c1e587ed499dcab19bdc1063ebbb2fc3f94715fe59b91fa5f5ac23c6bf0fc5`. [ดาวน์โหลด Candidate Artifact](https://github.com/niyomse-collab/niyom/actions/runs/42144813089/artifacts/13470383540). Artifact หมดอายุ `2026-11-13T02:03:06Z` (13 พฤศจิกายน 2569 เวลา 09:03 น. ประเทศไทย).
- Independent Core regression บน HEAD เดียวกัน **#42144818209** ผ่านทั้งสองระบบ: Windows **697 passed, 1 skipped**; Ubuntu **695 passed, 3 skipped**; `compileall` ผ่านทั้งคู่ — [GitHub Actions #42144818209](https://github.com/niyomse-collab/niyom/actions/runs/42144818209).
- Build log ยังมี non-fatal PyInstaller warnings: `pycparser.lextab`, `pycparser.yacctab`, `scipy.special._cdflib`, `nvcuda.dll` และ `tbb12.dll`; packaged-import smoke ผ่าน แต่ warnings เหล่านี้ยังไม่ใช่การยืนยัน runtime ของ GFPGAN/CUDA บนเครื่องร้าน. Actions ยังแสดง Node.js 20 deprecation warning สำหรับ workflow actions; ไม่ทำให้ run นี้ล้ม.
- Candidate job ใช้ `Test-V2-Package.ps1 -Mode imports` และระบุชัดว่าเป็น packaged-import check **โดยไม่อ้าง real four-engine inference**. ไม่ได้ติดตั้ง/ถอนการติดตั้ง GUI จริงบนเครื่องร้าน และไม่ได้ยืนยัน GPU Adapter หรือคุณภาพภาพ.
- Native CLI smoke ที่ตรวจ log ได้ล่าสุดยังเป็น **#42064430048** บน commit เก่ากว่า `2b3c011a85e671bce67a4414d511cdb1bcadc825`: RGB และ RGBA/ICC synthetic reports ต่างคง `real_inference_verified=false`; Real-CUGAN และ Anime4KCPP มีสถานะ `binary_executed_and_2x_output_validated`, ขณะที่ Real-ESRGAN และ Waifu2x ถูกจัดเป็น `vulkan_initialization_failed` จาก `vkCreateInstance failed -9` บน Hosted Runner. นี่ไม่ใช่ผลทดสอบ GTX 1660 Ti ของร้าน และไม่ใช่ QA ของ HEAD ล่าสุด — [GitHub Actions #42064430048](https://github.com/niyomse-collab/niyom/actions/runs/42064430048).
- Official archive audit tool, provisioner และ manifest loader ยังมี Git blob SHA เดิมเมื่อเทียบจาก commit audit `a36165b08e2dcebc439c5685f08f5fc0877dbb81` ถึง HEAD นี้; audit logic จึงไม่ได้เปลี่ยนหลัง run #42024220154. สถานะสิทธิ์แจกจ่ายยังคง `license_redistribution_approved=false`; ห้าม bundle third-party binaries/weights จนตรวจสิทธิ์ครบ.
- ตรวจ PR #18 ซึ่งยัง Open / Draft / Not Merged, HEAD `288dd8501c230a118d9a7e60d2522a2cc7411bcc`. Git blob SHA ระหว่าง PR #18 HEAD, PR #20 base และ PR #20 HEAD ตรงกันสำหรับ `signprint_ai/face_module/face_protection.py` (`7795bfd409e68e17c80ef0b401b8c099074e22b8`), `signprint_ai/large_faces.py` (`0faafd0c442e156def34faee7fbf98fc65cf754f`), `signprint_ai/v211_face_contract.py` (`4d63a947301b559f37bfb68e283b8cd872fcde19`) และ `signprint_ai/face_module/__init__.py` (`19f02356a689fd068b12a7240fabbbe62c878352`). ค่าเหล่านี้เป็น Git blob IDs ไม่ใช่ SHA256 ของไฟล์.
- คง `real_inference_verified=false` และ `quality_certified=false` จนกว่าจะผ่าน Native inference ทั้งสี่บน Windows 11 GTX 1660 Ti, ตรวจ device/backend ที่แต่ละ Engine ใช้, A/B ภาพจริง, VRAM 6GB, ภาพเกิน 18MP และ Print QA. PR #20 และ PR #18 ต้องคง Draft; ไม่มี Merge หรือ Release.


## 6 พฤศจิกายน 2569 — ตรวจซ้ำ PR #20 / PR #18 และ Local GPU Diagnostic

- PR #20 ยัง Open / Draft / Not Merged; branch HEAD ปัจจุบันคือ `1cb9b5106f57c41c0233da39bcaea33fe5c09d05`. เปรียบเทียบกับ Candidate code SHA `11fc95195ce7a07764a5c4483e09d4efaf78dc61` พบว่ามีเพียง commit `1cb9b51` ที่แก้เอกสารสถานะไฟล์นี้ 15 บรรทัด; ไม่มี production source, installer, PyInstaller spec หรือ workflow code เปลี่ยนหลัง Candidate Build.
- Independent Core regression บน branch HEAD `1cb9b51` ผ่านทั้งสองระบบใน run **#42152707571**: Windows **697 passed, 1 skipped**; Ubuntu **695 passed, 3 skipped**; `compileall` ผ่านทั้งสองระบบ — [GitHub Actions #42152707571](https://github.com/niyomse-collab/niyom/actions/runs/42152707571).
- Windows Candidate Build ของ code SHA `11fc951` ผ่านทั้ง `bridge-tests` และ `windows-v2-candidate` ใน run **#42144813089**. Bridge suite **112 passed in 2.79s**; Inno Setup compile, PyInstaller frozen build, packaged-import smoke และ artifact upload ผ่าน. Candidate step ระบุชัดว่าเป็น import check และ **ไม่ได้อ้าง real four-engine inference** — [GitHub Actions #42144813089](https://github.com/niyomse-collab/niyom/actions/runs/42144813089).
- Installer `NiyomSilp-Design-v211-EXPERIMENTAL-Setup.exe` SHA256 จาก Build Log: `bac1d1c3d482601e559f6f38b5a721bb65787781007f9ade0ec144e375da2539`. Artifact ID `13470383540`, ขนาด **2,584,347,716 bytes**, ZIP SHA256 `00c1e587ed499dcab19bdc1063ebbb2fc3f94715fe59b91fa5f5ac23c6bf0fc5`; [ดาวน์โหลด Candidate Artifact](https://github.com/niyomse-collab/niyom/actions/runs/42144813089/artifacts/13470383540). Artifact หมดอายุ `2026-11-13T02:03:06Z`.
- Build warnings ที่ยังไม่ทำให้ Job ล้ม: `pycparser.lextab`, `pycparser.yacctab`, `scipy.special._cdflib`, `nvcuda.dll`, `tbb12.dll` และ Node.js 20 deprecation ของ GitHub Actions. ต้องตรวจ runtime บน Windows เครื่องร้าน; warning `nvcuda.dll` บน Hosted Runner ไม่ใช่หลักฐานว่า GTX 1660 Ti ของร้านผิดปกติ.
- PR #18 ยัง Open / Draft / Not Merged, HEAD `288dd8501c230a118d9a7e60d2522a2cc7411bcc`. เมื่อเทียบ PR #18 HEAD กับ PR #20 base `05d0b2145fd60baf06431edee6f61f0873b77163` พบ PR #18 มีเพิ่ม 1 commit ซึ่งเปลี่ยนเฉพาะ `.github/workflows/v211-four-engine-manual-evidence.yml`; PR #20 มี workflow รุ่นของสาขาตนเองซึ่ง checkout `work/v211-four-engine-v2-bridge-20261103`. Git blob SHA ของ `signprint_ai/face_module/face_protection.py`, `signprint_ai/large_faces.py`, `signprint_ai/v211_face_contract.py` และ `signprint_ai/face_module/__init__.py` ยังคงตรงกันทั้ง PR #18 HEAD, PR #20 base และ PR #20 HEAD. ไม่มีการแก้ V2/GFPGAN face source.
- Local diagnostic ถูกบรรจุใน Frozen EXE แล้ว; หลังติดตั้ง V2.1.1 และเลือก one-time four-engine setup ให้รัน PowerShell บนเครื่องร้าน:

```powershell
& "$env:ProgramFiles\NiyomSilpDesignV211Experimental\NiyomsilAIEnhancer.exe" --diagnose-v211-four-ai --output-dir "$env:USERPROFILE\Desktop\NiyomSilp-V211-GPU-QA"
```

- Diagnostic สร้างภาพสังเคราะห์ RGB/RGBA เท่านั้น; ตรวจ NVIDIA-SMI, Vulkan loader, `vulkaninfo`, การเห็น GTX 1660 Ti ในทั้ง NVIDIA-SMI/Vulkan, งบ VRAM ประมาณ 6 GiB และรัน Native CLI ทั้งสี่เพื่อตรวจ output dimensions, alpha, ICC และ DPI. ผล JSON อยู่ใน `shop_gpu_diagnostic.json`; ไม่มีการเปิดภาพลูกค้า, network, upload หรือเก็บภาพทดสอบ. ค่า `four_engine_cli_passed_on_gtx1660ti_vulkan_host=true` จะเป็นจริงเมื่อทั้งสี่ CLI ผ่านและตรวจพบสภาพแวดล้อม GPU/Vulkan ตามเกณฑ์ แต่ยังไม่พิสูจน์ว่าแต่ละ CLI เลือก adapter เดียวกันหรือคุณภาพภาพดีขึ้น.
- สถานะ release ยังคง `real_inference_verified=false` และ `quality_certified=false` จนกว่าจะมีรายงาน diagnostic จากเครื่องร้าน, ตรวจ device/backend จริง, A/B ภาพคน/สัตว์/วัตถุ/กรอบ/ลายไทย/อักษรไทย-อังกฤษ-จีน/พื้นสีเรียบ/gradient/ขอบ RGBA/ใบหน้า, ทดสอบงานเกิน 18MP, VRAM 6GB และ print workflow. ปัจจุบัน >18MP, CMYK/PDF/PSD four-engine route และ Native 4x/8x multi-pass ยังไม่รองรับ; output ปกติยังเป็น V2 และ Four-Engine QA เป็น sidecar แยกเท่านั้น.
- ห้าม Merge/Release; ห้ามแก้ V1 หรือ V2 Stable; ไม่ Commit binary, weights หรือภาพลูกค้า.



## 6 พฤศจิกายน 2569 — แยกผล Native CLI ตาม Backend (Diagnostic schema 3)

- Real-ESRGAN, Waifu2x และ Real-CUGAN เป็นกลุ่ม NCNN/Vulkan จึงรายงานแยกเป็น ncnn_vulkan_engine_names และ three_ncnn_vulkan_engines_passed_on_gtx1660ti_vulkan_ready_host.
- Anime4KCPP v3.2.0 เป็นอีก backend family: processor auto อาจเลือก CPU/OpenCL/CUDA; ไม่ใช่ NCNN/Vulkan และไม่ควรนับเป็นหลักฐาน Vulkan inference.
- anime4k_cli_outputs_validated_on_both_synthetic_cases แยกการผ่าน CLI/Output ของ Anime4K ออกจากผลของสาม NCNN engines; anime4k_backend_inventory แสดงรายการ processor/device ที่มี แต่ยังไม่พิสูจน์การเลือกจริง.
- per_engine_backend_selection_verified และ anime4k_backend_selection_verified เป็น false จนกว่าจะมี telemetry จาก process ขณะ inference บนเครื่องร้าน.
- all_four_cli_validated_on_gtx1660ti_vulkan_equipped_host หมายถึงทั้งสี่ CLI ผ่านบนเครื่องที่ตรวจพบ GTX 1660 Ti และ Vulkan พร้อมกันเท่านั้น ไม่ได้อ้างว่าทุก process ใช้ GTX adapter. ฟิลด์เดิม four_engine_cli_passed_on_gtx1660ti_vulkan_host คงไว้เพื่อ compatibility และมีความหมายเดียวกัน.
- เพิ่ม Regression แยกกรณี Anime4K ล้มแต่สาม NCNN ผ่าน และกรณี NCNN ตัวใดตัวหนึ่งล้ม; ไม่มีการเปลี่ยนการประมวลผลภาพ, Installer, Fusion, V1 หรือ V2 Stable.

## 6 พฤศจิกายน 2569 — ปกป้อง RGB ใต้ขอบโปร่งใสของ PNG ระหว่าง Four-Engine Fusion

- ตรวจพบช่องว่างใน QA เดิม: Fusion คัดลอก Alpha จาก V2 ได้ตรง แต่ยังอาจเปลี่ยนค่า RGB ใต้พิกเซลที่ Alpha เป็น 0 หรือเป็นขอบ antialias (Alpha 1–254). ค่านี้มองไม่เห็นทันทีบนพื้นหลังบางชนิด แต่มีโอกาสเกิด fringe เมื่อโปรแกรมจัดหน้า/พิมพ์ resample PNG.
- Commit `220de9f420a51576b8ff84aff579bcf8621aa4ff` ปรับ Fusion ให้สร้าง edge gate จาก Alpha ของ V2 ในแต่ละ tile และอนุญาต detail fusion เฉพาะพิกเซลที่ Alpha = 255; พิกเซลโปร่งใสและกึ่งโปร่งใสคง RGB/Alpha จาก V2 เดิม.
- Commit `da466dee0994bcc882de10ac787c4e3010a43a0f` เพิ่ม Regression `test_rgba_fusion_preserves_rgb_under_transparent_and_antialiased_edges` ซึ่งตรวจ RGB ของทุกพิกเซลที่ Alpha < 255 ให้ตรงกับ V2 แบบ pixel-identical.
- Independent Core regression ที่ครอบคลุม branch code นี้ผ่าน: Windows **701 passed, 1 skipped**; Ubuntu **699 passed, 3 skipped**; compileall ผ่านทั้งสองระบบ — [GitHub Actions #42179684393](https://github.com/niyomse-collab/niyom/actions/runs/42179684393).
- Windows Candidate Build ที่ยืนยันได้ล่าสุดก่อนการแก้ RGBA คือ **#42170845434** บน HEAD `ae8f5cae9c75159c476e4b956939617f810c13a1`; Build, packaged-import smoke และ artifact upload ผ่าน แต่ Artifact นี้ **ยังไม่มี** การแก้ RGBA สอง Commit ข้างต้น จึงห้ามใช้เป็น Installer acceptance ของโค้ดล่าสุด. ต้อง Build Candidate ใหม่บน HEAD หลังการแก้.
- PR #20 ยังคง Open / Draft / Not Merged. PR #18 ยัง Open / Draft / Not Merged. Git blob SHA ของ `face_protection.py`, `large_faces.py`, `v211_face_contract.py` และ `face_module/__init__.py` ยังคงตรงกันระหว่าง PR #18 HEAD, PR #20 base และ PR #20 head.
- PR #20 ยังคง Open / Draft / Not Merged. Base คือ `feature/v2.1.1-super-ai` ซึ่งเป็น head branch ของ PR #18. Compare ปัจจุบันรายงาน `diverged`, `ahead_by=233`, `behind_by=1`, merge base `05d0b2145fd60baf06431edee6f61f0873b77163`; แต่ Pull Request API ณ 6 พ.ย. 2569 14:51 น. ประเทศไทยรายงาน `mergeable=true`, `mergeable_state=clean`. ดังนั้น branch ยังไม่ fast-forward ตรงกัน แต่ GitHub ไม่พบ merge conflict ในขณะตรวจ; ไม่จำเป็นต้อง force-push/rebase/เปลี่ยน base เพื่อคงสถานะ Draft. ให้ตรวจ refs ใหม่ก่อนการ merge ในอนาคต และคง PR #18/#20 เป็น Draft จนผ่านเกณฑ์คุณภาพและเจ้าของอนุมัติ.
- คง `real_inference_verified=false`, `quality_certified=false`, `print_quality_certified=false`. การทดสอบนี้เป็น synthetic pixel regression ไม่ใช่ Native inference หรือ Print QA บน GTX 1660 Ti.


## 6 พฤศจิกายน 2569 14:51 น. — ตรวจ Candidate ล่าสุดหลังแก้ RGBA และสถานะ PR

- PR #20 HEAD ปัจจุบันคือ `412d4e8e96939425843d1143ad7ff74046859633`; ยังคง Open / Draft / Not Merged. Commit `412d4e8` เปลี่ยนเฉพาะเอกสารสถานะ; code commit ล่าสุดที่มีการแก้ Fusion/Regression คือ `da466dee0994bcc882de10ac787c4e3010a43a0f` (ทดสอบ RGB ใต้ Alpha 0–254 ให้ pixel-identical กับ V2). Commit `45b2af8` ไม่มีไฟล์เปลี่ยนแปลง.
- Windows Candidate Build **#42179678964** บน code SHA `da466dee0994bcc882de10ac787c4e3010a43a0f` สำเร็จ: `bridge-tests` ผ่าน, Inno Setup compile ผ่าน, PyInstaller frozen build ผ่าน, packaged `NIYOMSIL_IMPORT_SMOKE` ผ่าน และ artifact upload ผ่าน — [GitHub Actions #42179678964](https://github.com/niyomse-collab/niyom/actions/runs/42179678964).
- Installer SHA256 จาก Build Log: `5a24827508d5bb0a3aa8743af727e679abe488f030bc4fa61fd1d6e6141b0e9d`. Artifact ID `13486100336`, ขนาด `2,584,350,276` bytes; SHA256 ของ ZIP artifact `202d75d2d352d0eaa95b8804601051bb9a7fee557e44ba7d877e80313ec09d6a`. [ดาวน์โหลด Experimental Candidate](https://github.com/niyomse-collab/niyom/actions/runs/42179678964/artifacts/13486100336); หมดอายุ `2026-11-13T07:34:23Z` (13 พ.ย. 2569 14:34 น. ประเทศไทย).
- Build Log มี non-fatal PyInstaller warnings ได้แก่ `pycparser.lextab/yacctab`, `scipy.special._cdflib`, `nvcuda.dll`, `tbb12.dll` และ Node.js 20 deprecation warnings ของ GitHub Actions. ไม่มีรายการใดทำให้ Build หรือ import smoke ล้ม แต่ runtime บนเครื่องร้านยังต้องตรวจ.
- Packaged import smoke เรียก `run.py` และ import `signprint_ai.v211_auto_setup`, `signprint_ai.v211_setup_cli`, bridge, background fusion, provisioner, runner, fusion และ GPU diagnostic จริง; ทดสอบ libvips 8×8 เพิ่มเติม. Smoke นี้ **ไม่ดาวน์โหลดโมเดล ไม่เรียก Native GPU inference และไม่ทดสอบ GUI/install/uninstall**.
- ตรวจ `installer_v211_experimental.iss` เพิ่มเติม: ตัวโปรแกรมติดตั้งแยกไว้ที่ `{autopf}\\NiyomSilpDesignV211Experimental` และป้องกัน path V1/V2 Stable; แต่โมเดลที่ผู้ใช้ยินยอมดาวน์โหลดอยู่ภายนอกใน `%LOCALAPPDATA%\\NiyomSilp\\V211-FourAI-QA` และ `.iss` ปัจจุบันไม่มี `[UninstallRun]`/ขั้นตอนลบโฟลเดอร์นี้. ดังนั้น **Uninstall ปัจจุบันไม่ได้รับรองว่าจะลบโมเดล/weights ใน LOCALAPPDATA** (โดยปกติจะคงไว้หลังถอนตัวแอป); ยังไม่ทดสอบบนเครื่องร้านและยังไม่มี cleanup prompt แยก. ไม่ได้ลบไฟล์ใด ๆ; ต้องเพิ่มตัวเลือกให้ผู้ใช้ยืนยันลบ cache แยกต่างหากก่อนจะอ้างว่า clean uninstall.
- Independent Core regression บน HEAD `412d4e8` ผ่าน run **#42179872334**: Windows **701 passed, 1 skipped**; Ubuntu **699 passed, 3 skipped**; compileall ผ่านทั้งสองระบบ — [GitHub Actions #42179872334](https://github.com/niyomse-collab/niyom/actions/runs/42179872334).
- ตรวจ PR #18 ยัง Open / Draft / Not Merged, HEAD `288dd8501c230a118d9a7e60d2522a2cc7411bcc`. Git blob SHA ของ `face_protection.py`, `large_faces.py`, `v211_face_contract.py` และ `face_module/__init__.py` ตรงกันระหว่าง base branch `feature/v2.1.1-super-ai` กับ PR #20 HEAD ทั้งสี่ไฟล์; PR #20 diff ไม่ได้แก้ไฟล์ Face/GFPGAN เหล่านี้.
- Native CLI smoke ล่าสุดที่มี artifact ให้ตรวจคือ run **#42064430048** บน commit เก่า `2b3c011a85e671bce67a4414d511cdb1bcadc825`: Real-CUGAN และ Anime4KCPP สร้าง 2× output ผ่านทั้ง RGB/RGBA synthetic cases; Real-ESRGAN และ Waifu2x ถูกจัดเป็น `vulkan_initialization_failed` จาก `vkCreateInstance failed -9`. รายงานทั้งสองกรณีคง `real_inference_verified=false`, `quality_improvement_verified=false`; นี่เป็น Hosted Runner ไม่ใช่เครื่อง GTX 1660 Ti ของร้าน และยังไม่มี CLI smoke ใหม่บน HEAD ปัจจุบัน — [GitHub Actions #42064430048](https://github.com/niyomse-collab/niyom/actions/runs/42064430048).
- Workflow `v211-official-four-engine-assets.yml` ยังไม่พบ run ใน Actions ของ branch ที่ตรวจรอบนี้. Code ใช้ release digest ที่เผยแพร่สำหรับ Waifu2x/Anime4K แต่ Real-ESRGAN/Real-CUGAN ใช้ observed SHA256 จาก audit ก่อนหน้าแทน upstream-published digest. License ของ source บางส่วนระบุได้ แต่สิทธิ์ model weights ยังไม่รับรอง; Anime4KCPP เป็น GPL-3.0 และยังไม่มีอนุมัติ redistribution. Installer ไม่ bundle binary/weights; task ดาวน์โหลดจาก upstream แบบ unchecked-by-default และต้องให้ผู้ใช้เลือกยินยอมก่อน.
- ยังคง `real_inference_verified=false`, `quality_certified=false`, `print_quality_certified=false`. Candidate เป็น package/import acceptance เท่านั้น; ต้องทดสอบ installer แบบ interactive/silent/uninstall, Native engines ทั้งสี่บน GTX 1660 Ti/Vulkan, 6GB VRAM, A/B ภาพจริง และ workflow พิมพ์ก่อนพิจารณา merge/release.


## 6 พฤศจิกายน 2569 16:42 น. — Vulkan device inventory โดยไม่ต้องติดตั้ง Vulkan SDK

- ปรับ tools/v211_shop_gpu_diagnostic.py ให้ใช้ vulkaninfo --summary เมื่อมีคำสั่งนี้ และ fallback ไป enumerate ผ่าน vulkan-1.dll / libvulkan.so.1 โดยตรงเมื่อไม่มี vulkaninfo. จึงไม่บังคับให้เครื่องร้านติดตั้ง Vulkan SDK เพียงเพื่อดู physical-device inventory.
- รายงาน Vulkan physical-device index, vendor/device ID และ device type; index มาจาก vkEnumeratePhysicalDevices order ซึ่งเป็นลำดับที่ NCNN -g ใช้. กรณีมีการ์ดรุ่นเดียวกันหลายใบจะเก็บทุก index ไม่รวมชื่อซ้ำ.
- เพิ่มการอ่าน Anime4KCPP --lp และ -l แยก CPU/OpenCL/CUDA; รายงาน device index ของแต่ละ processor และเสนอ CUDA ก่อน OpenCL เมื่อพบ GTX 1660 Ti เพียงหนึ่งรายการ.
- เพิ่ม Regression สำหรับ VkPhysicalDeviceProperties decoder, native loader smoke (best-effort), no-SDK fallback, duplicate adapter names และ Anime4K processor-specific device mapping.
- **ขอบเขตที่ยังไม่เสร็จ:** diagnostic inventory ไม่ได้เปลี่ยน manifest หรือ CLI arguments. Real-ESRGAN/Waifu2x/Real-CUGAN ยังใช้ upstream device default และ Anime4KCPP ยังเป็น processor auto/device 0. processor_selection_verified, device_selection_verified และการรับรองว่าแต่ละ Process ใช้ GTX 1660 Ti ยังคงเป็น false; ห้ามตีความ recommendation ว่าเป็น runtime binding.
- Independent Core regression บน code HEAD a0e3aa2506adf081e610c21f99599892fef710c1 ผ่าน run #42198882994: Windows และ Ubuntu ทั้งสอง Job ผ่าน pytest และ compileall — https://github.com/niyomse-collab/niyom/actions/runs/42198882994.
- Windows Candidate Build ล่าสุดที่ตรวจ artifact ได้ยังเป็น run #42179678964 บน code SHA da466dee0994bcc882de10ac787c4e3010a43a0f. Compare ระหว่าง Candidate SHA กับ HEAD a0e3aa25 พบไฟล์ต่าง 3 รายการ ได้แก่ tools/v211_shop_gpu_diagnostic.py, tests/test_v211_shop_gpu_diagnostic.py และเอกสารนี้. ดังนั้น artifact เดิมยังไม่รวม Native Vulkan fallback และ tests ชุดใหม่; **ห้ามใช้เป็น Candidate acceptance ของ HEAD ปัจจุบัน**. Workflow มี workflow_dispatch แต่รอบนี้ยังไม่มี run ใหม่ที่ยืนยัน Candidate Build บน HEAD ล่าสุด — https://github.com/niyomse-collab/niyom/actions/workflows/v211-four-engine-bridge-windows.yml.
- Artifact เก่า ID 13486100336 ยังไม่หมดอายุ ณ เวลาตรวจ แต่เป็น build ของ SHA เก่า; ไม่ได้ดาวน์โหลดหรือติดตั้งบนเครื่องร้าน.
- PR #20 ยังคง Open / Draft / Not Merged และ PR #18 ยังคง Open / Draft / Not Merged. Blob SHA ของ face_protection.py, large_faces.py, v211_face_contract.py และ face_module/__init__.py ยังตรงกันระหว่าง PR #18 HEAD และ PR #20 HEAD; ไม่มีการแก้ Face/GFPGAN ในชุด diagnostic รอบนี้.
- คง real_inference_verified=false, quality_certified=false, print_quality_certified=false. ยังไม่มี Native four-engine inference บน Windows GTX 1660 Ti, ไม่มี A/B ภาพลูกค้า และไม่มีการทดสอบติดตั้ง/ถอนการติดตั้งบนเครื่องร้าน.


## 6 พฤศจิกายน 2569 — ปิดช่องว่างกรณีพบ GTX 1660 Ti มากกว่าหนึ่ง Vulkan index

- ปรับ GPU-ready gate ให้ต้องมี Vulkan physical-device index ของ GTX 1660 Ti ที่ไม่กำกวม (vulkan_device_index ต้องมีค่า). ถ้าพบการ์ดชื่อเดียวกันหลาย index จะไม่ตั้งสถานะ GPU-ready แม้ชื่อการ์ดจะตรงกัน.
- เพิ่ม Regression ให้กรณี index ไม่ชัดเจนต้องไม่ผ่าน GPU-ready gate; ผลการตรวจ output ของ CLI ยังแยกจากความพร้อมของเครื่องเหมือนเดิม.
- Independent Core regression บน code HEAD a8cd370ab01f2abf464bf65768c607eccdf0ec10 ผ่าน run #42199175096: Windows และ Ubuntu ผ่าน pytest และ compileall — https://github.com/niyomse-collab/niyom/actions/runs/42199175096.
- Windows Candidate Build ยังต้อง dispatch ใหม่เพื่อรวม diagnostic changes; Candidate artifact #42179678964 เป็น SHA เก่า da466dee0994bcc882de10ac787c4e3010a43a0f และไม่ครอบคลุม Native Vulkan loader inventory, Anime4K per-processor mapping หรือ unique-index gate. ห้ามใช้ artifact เก่าแทนการ Build/Install acceptance ของ HEAD ปัจจุบัน.
