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

## Windows setup-time provisioning and first-launch consent

There are two affirmative-consent paths, both unchecked/off by default:

1. The experimental installer offers an **unchecked-by-default** task: “I agree: download and install all four AI engines for offline use”. If selected, it runs the packaged setup command under the installing user's account, downloads the official upstream archives, verifies SHA256 and archive contents, then installs into %LOCALAPPDATA%\NiyomSilp\V211-FourAI-QA before offering to launch the editor.
2. If the installer task is skipped, the editor performs a **local-only** setup-state check about 600 ms after opening. It does not access the network during this check. When no fully verified four-engine manifest and no prior decline marker exist, it asks one Yes/No question for all four engines. Only Yes starts provisioning on a background worker. No writes a local decline marker and suppresses repeat prompts. A failed download does not write the decline marker, so the user can retry later.

If the installer task completes successfully, the editor finds the verified manifest and does not prompt again. If either consent path is skipped/declined, accepted V2 remains available. Once a verified manifest exists, subsequent eligible V2.1.1 jobs invoke the four installed engines automatically as one coordinated research path, offline and without per-engine switches. The bridge can be explicitly disabled with NIYOMSIL_V211_FOUR_AI=0. No download starts before affirmative consent; customer artwork is never uploaded.

### 11 November 2026 historical correction — superseded on 12 November

For a short-lived revision, the editor first-launch prompt was removed and installer consent was the only setup path. The 12 November revision restored the editor's local-only Yes/No fallback when the installer task is skipped. The current behavior is the two-path flow documented above; this historical note must not be used as the current setup instruction.

The installer command is NiyomsilAIEnhancer.exe --provision-v211-four-ai. The frozen import smoke includes its CLI module. Optional environment override is NIYOMSIL_V211_FOUR_AI_MANIFEST.

Real-ESRGAN, Waifu2x and Real-CUGAN were previously exercised individually on the shop Windows PC as reported by the owner. That is not proof that the newly integrated four-model fusion has passed an A/B comparison on that PC.

## Limitations and unresolved gates

- The auxiliary route uses an in-memory path at or below 18 MP and a disk-backed libvips/native-tile/streamed-fusion/streamed-QA path above 18 MP for supported RGB/RGBA raster jobs. The current guards are at most 1,000 MP, at most 64 MiB per output row, and a disk-space reserve calculated before work; unsupported formats, limits, or insufficient disk fail closed to the already-saved V2 output. The large route currently requires PNG intermediates and uses one native 2x pass per engine on a half-target seed. A 4x/8x target dimension is not native 4x/8x or multi-pass inference. CMYK, PDF and PSD remain V2-only.
- A passing Windows installer build proves packaging, not real model inference inside the packaged app. GitHub Windows hosted-runner currently allows Real-CUGAN/Anime4K synthetic real-CLI smoke outputs but Real-ESRGAN/Waifu2x hit vkCreateInstance failed -9 without a usable Vulkan GPU. The user's Windows PC with GTX 1660 Ti is the relevant test machine for end-to-end fusion.
- Experimental fusion on raster candidates is real implemented code, not yet proof of better visual quality. No OCR/retyping is used. The four models' detail contributions must be measured and reviewed for Thai/English/Chinese small lettering, people, animals, objects, line art, flat green areas, gradient ramps, transparency/halo and GFPGAN face retention.
- Native subprocess cancellation is now wired through the sequential runner: on Windows it terminates the process tree; on POSIX it terminates the process group. Fusion also checks cancellation between bounded tiles. CI regression tests cover cancellation and temporary-output cleanup, but the Windows GPU process-tree behavior still needs verification on the shop PC.
- Disk-backed four-engine tile inference, streamed fusion and streamed QA crop are implemented with synthetic/component regression coverage. Automatic face ROI detection and a measured 6 GB VRAM stress test on the shop GTX 1660 Ti remain open; quality-certified replacement of the print export is not approved.
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
- การยินยอมดาวน์โหลดมีเฉพาะใน Inno Setup task ที่ **ไม่เลือกไว้โดยค่าเริ่มต้น** ผู้ใช้เลือกยินยอมครั้งเดียวระหว่างติดตั้ง แล้วระบบดาวน์โหลด/ตรวจ SHA256/ติดตั้ง AI ทั้งสี่ให้เสร็จก่อนเปิด Editor. Editor จะไม่แสดงหน้าถามดาวน์โหลดเมื่อเปิดครั้งแรกและไม่เริ่มติดตั้งเอง. หากไม่เลือก task โปรแกรมจะเปิด V2 เดิมโดยไม่ถามภายหลัง; หากต้องการติดตั้ง AI เพิ่ม ให้เรียก Installer รุ่นทดลองอีกครั้งและเลือก task เดิม. เมื่อ Manifest ผ่านการตรวจครบ งานที่เข้าเงื่อนไขจะเรียก AI ทั้งสี่แบบออฟไลน์โดยอัตโนมัติ.
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


## 6 พฤศจิกายน 2569 17:50 น. — ตรวจ Regression บน PR HEAD และคิว Windows Candidate ใหม่

- ตรวจ PR #20 HEAD `8e4ace8be9011772eba4b5d6cd22b615ee87c44b` (สาขา `work/v211-four-engine-v2-bridge-20261103`): Open / Draft / Not Merged; GitHub รายงาน mergeable=true. PR #18 ยังคง Open / Draft / Not Merged.
- Independent Core regression ที่ผูกกับ PR HEAD เดียวกันผ่าน run **#42199342233**: Ubuntu **705 passed, 3 skipped**; Windows **707 passed, 1 skipped**; `compileall` ผ่านทั้งสองระบบ. Job logs ยืนยันว่า pytest และ compileall สำเร็จ — https://github.com/niyomse-collab/niyom/actions/runs/42199342233.
- ตรวจ Windows Candidate workflow `.github/workflows/v211-four-engine-bridge-windows.yml`: มี `push` trigger เมื่อแก้ `docs/V211_FOUR_ENGINE_BRIDGE_BUILD_STATUS_TH.md` บน branch นี้ จึงบันทึกผล regression รอบล่าสุดเพื่อให้เกิด Candidate Build ใหม่บน commit ที่ตามมา; การ Build นี้ยังต้องรอผล Actions และห้ามใช้ artifact เก่าแทน.
- Candidate Build ล่าสุดที่ยืนยันได้ก่อนรอบนี้ยังเป็น run **#42179678964** บน code SHA `da466dee0994bcc882de10ac787c4e3010a43a0f`; ไม่รวม Native Vulkan inventory/unique-index gate ที่เพิ่มภายหลัง. Artifact เก่า ID `13486100336` จึงยังไม่ใช่ Candidate acceptance ของ PR HEAD.
- ตรวจ Blob SHA ของ `signprint_ai/face_module/face_protection.py`, `signprint_ai/large_faces.py`, `signprint_ai/v211_face_contract.py` และ `signprint_ai/face_module/__init__.py` ระหว่าง PR #18 head branch `feature/v2.1.1-super-ai` กับ PR #20 branch: ทั้งสี่ไฟล์ตรงกันทุกตัวอักษร.
- ขอบเขต GPU ยังไม่เปลี่ยน: Vulkan inventory เป็นเพียงรายการ Device; NCNN `-g` และ Anime4KCPP `-p/-d` ยังไม่ถูกผูกเข้ากับคำสั่ง inference. `per_engine_backend_selection_verified=false`, `anime4k_backend_selection_verified=false`; ไม่มีการอ้างว่า Native inference ทั้งสี่ผ่านบนเครื่องร้าน.
- ไม่มีการแก้ Production Code ในรอบบันทึกนี้; ไม่มี Binary/Weights/ภาพลูกค้าเพิ่มใน Git; ไม่แก้ V1/V2 Stable, ไม่ Rebase/Force Push, ไม่ Merge/Release.

## 7 November 2026 — disk-backed RGBA fusion validation (not end-to-end large-image inference)

- The fusion stage now validates each RGBA engine candidate's alpha against the **accepted V2 target alpha**, tile by tile. V2 remains the alpha master; candidate RGB detail cannot introduce, erase or shift transparent pixels.
- Above the Pillow raster threshold, the V2 and candidate alpha regions are read through pyvips.Region.fetch; no full-size Pillow decode is needed for candidate alpha validation. Cancellation is checked between alpha-validation tiles as well as during fusion.
- The PNG writer already streams RGBA rows from the disk-backed raster, preserving V2 alpha, ICC and DPI. The new regression forces the libvips path, forbids full Pillow PNG decoding, and verifies that a mismatched candidate alpha fails closed without publishing a QA file.
- **This does not yet enable large four-engine jobs in the app.** tools/v211_four_engine_run.py and the bridge still reject targets above 18 MP before reading the model manifest or launching native engines. Native per-engine tile orchestration, overlap/seam validation, disk-backed candidate stitching, and end-to-end VRAM/cancel stress remain open. Until those are complete, images above 18 MP continue through accepted V2 only.

## 7 พฤศจิกายน 2569 — Native tile inference ระดับ Runner (ยังไม่เปิดใน App)

- เพิ่ม tools/v211_four_engine_tiled_inference.py สำหรับการทดลอง Native 2x แบบแบ่ง Tile: core 512×512 พิกเซล, overlap 32 พิกเซล, ขยาย edge tile ให้มีขนาดอย่างน้อย 64 พิกเซล, เรียกแต่ละ engine แบบ sequential และไม่รัน GPU process พร้อมกัน.
- ใช้ pyvips.Region.fetch อ่าน source/V2 ทีละ Tile; ส่งเฉพาะ PNG tile ให้ Native CLI; ตัดกลับเฉพาะ core ที่ไม่ซ้อนกันและเขียนลง raw raster บนดิสก์ ก่อน encode PNG แบบ streaming. ไม่มีการสร้างภาพ candidate ปลายทางเต็มภาพใน Pillow.
- เปรียบเทียบ prediction ใน overlap ระหว่าง Tile ที่ติดกัน. ถ้า max channel delta เกิน 48 หรือ mean เกิน 6/255 จะปฏิเสธ candidate ของ engine นั้นและไม่เผยแพร่ไฟล์ candidate ที่ไม่สมบูรณ์. ค่าดังกล่าวเป็น fail-closed heuristic ไม่ใช่หลักฐานว่ารอยต่อมองไม่เห็น.
- RGBA ใช้ RGB จาก engine แต่ประกอบ Alpha จาก accepted V2 reference โดยตรง; ICC/DPI มาจาก V2 และตรวจ metadata ของแต่ละ tile ก่อน stitch. ยกเลิกงานแล้วลบ candidate ทั้งชุด; raw/tile files อยู่ใน temporary directory ภายใน output folder และถูกล้างเมื่อจบ.
- tools/v211_four_engine_run.py route งานที่ source/target เกิน 18 MP ไปยัง tiled runner เฉพาะ PNG + V2 reference ที่ผ่าน mode/ICC/geometry preflight, native 2x pass เดียว, ไม่เกิน 1,000 MP และ row buffer ไม่เกิน 64 MiB. งานใหญ่ที่เป็น 4x/8x multi-pass ยังปฏิเสธก่อนอ่าน Manifest/เปิด Native CLI. Full-image three-engine priority preview ถูกข้ามใน tiled mode เพราะ helper เดิมยัง decode ภาพเต็มผ่าน Pillow.
- เพิ่ม tests สำหรับ stitched 2x pixels, ICC/DPI, RGBA alpha จาก V2, seam disagreement, cancellation cleanup, invalid geometry และ integration routing ของ runner; เพิ่ม test file เข้า Windows Candidate workflow.
- ข้อจำกัดสำคัญ: นี่เป็น runner/CLI research path เท่านั้น. signprint_ai/v211_four_engine_bridge.py ยังมี AUXILIARY_MAX_PIXELS = 18,000,000 และ _prepare_native_2x_inputs ยังใช้ Pillow เต็มภาพเพื่อสร้าง half-target seed. ดังนั้น App/Bridge ยังปฏิเสธภาพเกิน 18 MP และจะคง V2-only สำหรับงานใหญ่จนกว่าจะเปลี่ยน seed creation, Manifest setup, QA display และ cancel lifecycle ให้ disk-backed ครบ end-to-end.
- ไม่ได้เปิดใช้งานใน production UI; ไม่มีการอ้าง Native inference จริง, GPU adapter verification, 6 GB VRAM stress, A/B quality หรือ print certification จาก fake-processor tests. Native command outputs ต้องเป็น exact 2x ต่อ tile; model-specific tile behavior ยังต้องทดสอบบนเครื่องร้าน.
- Independent Core regression บน HEAD acb8c5835e029c4de31fc323ab59e2da5e03de9c ถูกเริ่มเป็น run #42372469315; ณ เวลาบันทึก pytest ทั้ง Windows/Ubuntu ยังทำงานอยู่ จึงยังไม่มีผลผ่าน/ล้มเหลวให้รายงาน. Windows Candidate workflow ถูกเพิ่ม test file ใหม่แล้ว แต่ run/artifact บน HEAD นี้ยังต้องยืนยันแยกต่างหาก.
- PR #20 และ PR #18 ยังคง Open / Draft / Not Merged. Blob SHA ของ face_protection.py, large_faces.py, v211_face_contract.py และ face_module/__init__.py ตรงกันครบ 4 ไฟล์. ไม่มีการแก้ V1/V2 Stable, ไม่มี Binary/Weights/ภาพลูกค้าใน Git และไม่มี Merge/Release.

### ผล CI หลังเพิ่ม Native Tile Runner — 7 พฤศจิกายน 2569

- Code/test HEAD ที่ทดสอบ: acb8c5835e029c4de31fc323ab59e2da5e03de9c. Independent Core run #42372469315 สำเร็จทั้งสอง Job: Windows 771 passed / 1 skipped; Ubuntu 769 passed / 3 skipped; compileall ผ่านทั้งสองระบบ. ไม่มี test failure — https://github.com/niyomse-collab/niyom/actions/runs/42372469315.
- Run #42372469315 ใช้ full pytest suite; tests/test_v211_four_engine_tiled_inference.py และ runner integration อยู่ใน suite และผ่าน. Windows/Ubuntu ติดตั้ง requirements_v2_large_images.txt สำเร็จ รวม pyvips.
- PR HEAD หลังบันทึกผลนี้เป็น docs-only commit; ผล 771/769 อ้างอิง code/test commit acb8 ไม่ใช่การอ้างว่า Candidate Installer ของ HEAD ล่าสุดผ่าน.
- Windows Candidate workflow trigger ครอบคลุม tools/v211_*.py และ tests/test_v211_*.py; อย่างไรก็ตาม connector ที่ใช้ตรวจ PR-triggered runs ไม่แสดง push-triggered Candidate run ID/artifact ในรอบนี้. จึงยังไม่ยืนยัน PyInstaller, Frozen Import, BUILD_PROOF, SHA256 หรือ installer artifact บน HEAD ล่าสุด. ติดตามที่ https://github.com/niyomse-collab/niyom/actions/workflows/v211-four-engine-bridge-windows.yml.

### Native Tile Runner: 24 MP evidence, frozen import coverage and latest regression — 7 พฤศจิกายน 2569

- เพิ่ม synthetic 24 MP target regression: source PNG 3,000×2,000 → target 6,000×4,000; แบ่งเป็น 6 tiles ต่อ engine, ตรวจ 7 overlap seams ต่อ engine, stitch candidate ทั้งสี่ด้วย raw disk raster และ streamed PNG writer. ระหว่าง run test บังคับให้ Pillow full-raster load ของ source/V2 ขนาด 3,000×2,000 และ 6,000×4,000 โยน AssertionError; test ผ่านทั้ง Windows และ Ubuntu. V2 reference bytes ต้องไม่เปลี่ยน.
- ลด seam acceptance threshold เป็น max channel delta 48 และ mean 6/255; threshold เป็น conservative heuristic สำหรับปฏิเสธความไม่สอดคล้องที่รุนแรง ไม่ได้พิสูจน์ว่าทุก seam มองไม่เห็น. Native models จริงอาจไม่ผ่าน threshold และต้องทดสอบ/ปรับบนเครื่องร้านโดยยัง fail-closed.
- รวม process evidence ข้ามทุก tile ต่อ engine: จำนวน process ที่เริ่มจริง, elapsed milliseconds รวม, จำนวน tile ที่ตรวจผ่าน และ seam statistics. รายงานยังไม่เก็บ argv, stderr, source path หรือ destination path; last-tile lifecycle ไม่ถูกนำไปแสดงแทนเวลารวมของทั้ง engine.
- เพิ่ม tools.v211_four_engine_tiled_inference ใน hiddenimports ของ NiyomsilV2ArmCore.spec และเพิ่ม import smoke ใน run.py; tests/test_v211_isolated_installer.py ตรวจ hiddenimport นี้ด้วย. Windows Candidate workflow มี test file ใหม่ในรายการ bridge tests แล้ว.
- Independent Core regression บน code/test HEAD 63478d0123e360fbf47715ac0dd953c69733417f ผ่าน run **#42372972482**: Windows **772 passed, 1 skipped**; Ubuntu **770 passed, 3 skipped**; pytest และ compileall ผ่านทั้งสองระบบ — https://github.com/niyomse-collab/niyom/actions/runs/42372972482.
- **Windows Candidate Installer:** การเปลี่ยน tools/tests/spec/run.py อยู่ใน path filters ของ Windows Candidate workflow และ workflow ถูกตั้งให้ Build/Package Smoke/BUILD_PROOF/SHA256/Artifact. อย่างไรก็ตาม Actions connector รอบนี้คืน PR-triggered Independent Core run เท่านั้น; ยังไม่มี push-triggered Candidate run ID หรือ artifact ที่ตรวจยืนยันได้. จึงยังไม่ประกาศว่า Frozen Import Smoke, PyInstaller, Installer SHA256 หรือ artifact ผ่านบน HEAD นี้. ตรวจได้ที่ https://github.com/niyomse-collab/niyom/actions/workflows/v211-four-engine-bridge-windows.yml.
- Bridge/App ยังมี AUXILIARY_MAX_PIXELS = 18,000,000 และ _prepare_native_2x_inputs ยังสร้าง seed ด้วย Pillow เต็มภาพ. ดังนั้น 24 MP result ข้างต้นเป็น runner-level synthetic tile inference เท่านั้น; app ยังคง V2-only สำหรับภาพเกิน 18 MP. ยังต้องทำ disk-backed V2 half-target seed, streamed final crop, UI progress/cancel, 4x/multi-pass, VRAM 6 GB stress และ native model seam A/B บน GTX 1660 Ti ก่อนเปิด end-to-end.


- Disk-capacity preflight now reserves seven raw-raster equivalents at the start (four worst-case candidate PNGs, the active engine's raw staging raster, and the fusion raw raster plus atomic streamed-PNG workspace), with an additional 64 MiB safety margin. Free space is rechecked before each engine so a low-disk condition fails before launching the next native process. Regressions cover both initial under-capacity and disk space dropping after the first engine; the latter confirms no subsequent native processor starts.


## 8 พฤศจิกายน 2569 — เชื่อม Application Bridge กับ Disk-backed Large-image Tile Runner

- เพิ่ม signprint_ai/v211_large_image_bridge.py สำหรับอ่าน Header/ICC/DPI, เตรียม half-target native seed และ V2 reference ด้วย libvips แบบ random-access/streaming; ไม่ใช้ Pillow decode ภาพลูกค้าขนาดใหญ่เต็มภาพ.
- Core Adapter เรียก Four-Engine Bridge ต่อหลัง V2 บันทึกผลสำเร็จ แม้ source หรือ V2 target เกิน 18 MP; V2 ยังคงเป็น Master และ Bridge ยังเป็น opt-in/Manifest-gated.
- งานเป้าหมายเกิน 18 MP ใช้ padded V2 reference, seed ขนาดครึ่งหนึ่ง และ native 2x pass เดียว. RGBA alpha seed มาจาก V2 reference; candidate/fusion alpha ยังคงยึด V2.
- QA crop ขนาดใหญ่ใช้ libvips Region.fetch แบบ bounded blocks และ streamed PNG writer; ตรวจพื้นที่ดิสก์ปลายทางก่อนเขียน sidecar, รองรับ cancel และสร้างไฟล์ QA แยกโดยไม่เขียนทับ V2.
- PyInstaller spec และ Frozen Import Smoke เพิ่ม signprint_ai.v211_large_image_bridge แล้ว.
- เพิ่ม Regression Test ให้ตรวจ 24 MP V2 target, odd-dimension padding, ICC/DPI, disk-backed seed/crop และปฏิเสธ Pillow full-raster decode; ปรับ Adapter test จาก large_image_tiling_pending เป็นการเรียก Bridge หลัง V2 save.
- **สถานะ ณ เวลาบันทึก:** เป็นการเชื่อม Source/Tests ที่ยังต้องรอ GitHub Actions บน HEAD ใหม่. ยังไม่ยืนยัน Windows Candidate Installer/Frozen Smoke ของ Commit ใหม่, Native inference ทั้งสี่บน GTX 1660 Ti, Vulkan adapter จริง, VRAM 6 GB, 4x/8x multi-pass หรือ A/B คุณภาพภาพจริง.
- ขอบเขตยังคง fail-closed: Runner รองรับ native 2x ต่อหนึ่ง pass และ target streaming ไม่เกิน 1,000 MP/row 64 MiB ตามข้อจำกัดเดิม. 4x/8x native multi-pass, CMYK/PDF/PSD Four-Engine, และการรับรองคุณภาพงานพิมพ์ยังไม่ผ่าน.
- PR #20 และ PR #18 คง Open / Draft / Not Merged. V1/V2 Stable ไม่ถูกแก้; ไม่มี Binary, Model Weights หรือภาพลูกค้าใน Git; real_inference_verified=false และ quality_certified=false.

## 8 พฤศจิกายน 2569 — Large-bridge integration regression และ CI ล่าสุด

- Commit `c0d539ad52140f3ef1424d0e045e6f98b31cc3a4` เพิ่ม integration regression `test_large_bridge_routes_streamed_seed_to_tiled_runner_and_streamed_qa`. Test เรียก Bridge จริง → libvips streamed seed/reference → Native Tile Runner จริง → disk-backed Fusion → streamed QA crop โดยแทน native executables ด้วย fake processors และลด threshold เฉพาะใน test เพื่อไม่ต้องสร้างภาพใหญ่ใน orchestration fixture. ตรวจว่า QA sidecar แยกจาก V2 และ V2 bytes/ICC/DPI ไม่เปลี่ยน.
- การทดสอบครั้งแรกใน runs #339/#340 ล้มเพราะ fake manifest คืน plain object ที่ไม่มี `argv` แทน `EngineCommand`; แก้ test fixture ให้ใช้ `EngineCommand` ที่มี input/output placeholders แล้ว. นี่เป็นข้อผิดพลาดของ test fixture ไม่ใช่ production runner/bridge.
- Windows Candidate run **#341 / 42405885215**: Bridge Tests ผ่าน และขั้น Privacy / Model Hash / Official Provisioning Contracts ผ่าน. ณ เวลาบันทึก ขั้น **Build V2-based experimental candidate (PyInstaller)** ยังทำงาน; Frozen Import, diagnostic dispatch, installer-slice SHA256/provenance และ artifact upload ยังไม่ยืนยัน. ติดตาม: https://github.com/niyomse-collab/niyom/actions/runs/42405885215.
- Independent Core run **#872 / 42405889088** บน code/test HEAD `c0d539ad52140f3ef1424d0e045e6f98b31cc3a4` ผ่าน: Windows **778 passed / 1 skipped**; Ubuntu **776 passed / 3 skipped**; compileall ผ่านทั้งสองระบบ. รวม **1,554 passed / 4 skipped**: https://github.com/niyomse-collab/niyom/actions/runs/42405889088.
- Independent Core run **#873 / 42406157395** บน PR HEAD หลัง documentation-only commit `d422fad6988ccf725f93cdb1ef913de3200e2c52` ผ่านผลเท่ากัน: Windows **778 passed / 1 skipped**; Ubuntu **776 passed / 3 skipped**; compileall ผ่าน: https://github.com/niyomse-collab/niyom/actions/runs/42406157395.
- Current PR #20 HEAD `d422fad6988ccf725f93cdb1ef913de3200e2c52` มีเฉพาะการแก้เอกสาร `docs/V211_WINDOWS_REAL_FOUR_ENGINE_QA_TH.md` เพิ่มเติมจาก code/test HEAD `c0d539a`; ไม่มี production-code change หลัง HEAD ที่ Candidate #341 กำลัง build.
- Candidate #338 ที่ผ่านบน HEAD เก่า `b94988714c1404843cbda1aa36737c754c278115` ยังเป็นเพียง artifact อ้างอิงก่อน integration regression: artifact id `13584763815`, SHA256 `f4d8c636d0d71a5095b197f2bcde230df94c10a118270ffdee378f805abcea01`. ห้ามใช้แทน Candidate #341.
- ตรวจ PR #18 เทียบกับ PR #20: Blob SHA ตรงกัน 4/4 สำหรับ `face_protection.py`, `large_faces.py`, `v211_face_contract.py` และ `face_module/__init__.py`. PR #18 และ #20 ยังคง Open / Draft / Not Merged.
- ข้อจำกัดยังคงเดิม: integration regression ใช้ fake processors ไม่ใช่ real native inference; 24 MP seed/crop และ tile-runner tests เป็น component evidence แยกกัน. GPU diagnostic ตรวจ total VRAM ประมาณ 5,500 MiB ขึ้นไปและ device inventory/binding gate แต่ยังไม่ใช่ peak-VRAM stress หรือ proof ว่า process ใช้ adapter จริง. ไม่มี A/B/print-quality certification จากรอบนี้.
- ไม่มีการแก้ V1/V2 Stable, ไม่มีการ commit binaries/weights/customer images, ไม่มี merge หรือ release; `real_inference_verified=false` และ `quality_certified=false` คงเดิม.


## 8 พฤศจิกายน 2569 — ผลปิดงาน Windows Candidate #341

- PR #20 HEAD ปัจจุบันคือ `bee460a247a7cc5c6dc8f7ca1a517a0178ff712b`; code/test HEAD ที่ Candidate สร้างคือ `c0d539ad52140f3ef1424d0e045e6f98b31cc3a4`. Commit ระหว่างสองจุดคือ `d422fad` และ `bee460a` เปลี่ยนเฉพาะเอกสาร ไม่มี production-code หรือ test change หลัง code/test HEAD.
- Windows Candidate **#341 / run 42405885215** เสร็จสมบูรณ์ด้วย conclusion `success`: ทั้ง `bridge-tests` และ `windows-v2-candidate` ผ่าน. Inno Setup 6.7.1 compile, PyInstaller candidate build, packaged-import smoke, diagnostic `--help` dispatch, BUILD_PROOF source-commit check, installer-slice SHA256 verification และ artifact upload ผ่านทั้งหมด.
- Candidate นี้สร้างจาก code/test commit `c0d539ad52140f3ef1424d0e045e6f98b31cc3a4`, version `2.1.1-beta.341`. Installer SHA256: `1c68f03afbdbffc11a9947e01ce428bedfe0346d7f49ebeb15009bddadd33adf`.
- Artifact `NiyomSilp-V2.1.1-four-engine-bridge-EXPERIMENTAL`, ID `13587309021`, ขนาด `2,584,419,343` bytes; SHA256 ของ ZIP artifact: `0882b57c341582a95c35834d30b86bbcdef8974511fb2598061e0b7df42ea56f`. ลิงก์: https://github.com/niyomse-collab/niyom/actions/runs/42405885215/artifacts/13587309021. Artifact หมดอายุ 14 พฤศจิกายน 2569 เวลา 19:42:50 UTC หากยังต้องเก็บต้องดาวน์โหลดก่อนหมดอายุ.
- Independent Core **#874 / run 42406398980** บน PR HEAD `bee460a` ผ่าน: Windows **778 passed / 1 skipped**, Ubuntu **776 passed / 3 skipped**, compileall ผ่านทั้งสองระบบ — https://github.com/niyomse-collab/niyom/actions/runs/42406398980.
- Build log มี warning จาก Hosted Runner ได้แก่ `nvcuda.dll` ไม่อยู่ใน runner, `tbb12.dll` ไม่พบสำหรับ optional Numba TBB pool และ optional PyInstaller collection warnings. สิ่งเหล่านี้ไม่ทำให้ Build/Import Smoke ล้ม; ต้องตรวจการเปิด GUI/การเรียก GPU และ runtime จริงบนเครื่องร้านต่อไป.
- Candidate #341 พิสูจน์ frozen package/provenance/dispatch เท่านั้น ไม่ได้ติดตั้งโปรแกรมบนเครื่องร้าน, ไม่ได้ดาวน์โหลด/ติดตั้งโมเดลให้ผู้ใช้, ไม่ได้พิสูจน์ว่า process ใช้ GTX 1660 Ti จริง และไม่ใช่การทดสอบ Native inference ทั้งสี่หรือคุณภาพภาพ.
- Independent Core #874 เป็นผลบน PR HEAD หลัง documentation-only commits; Candidate #341 สร้างจาก code/test HEAD ที่ตรงกับ source tree ก่อนการแก้เอกสารดังกล่าว. ไม่มีการใช้ Artifact เก่ามาแทน Candidate #341.
- Protected Git Blob SHA เทียบ PR #20 กับ PR #18 ยังคงตรงกัน 4/4: `face_protection.py` `7795bfd409e68e17c80ef0b401b8c099074e22b8`; `large_faces.py` `0faafd0c442e156def34faee7fbf98fc65cf754f`; `v211_face_contract.py` `4d63a947301b559f37bfb68e283b8cd872fcde19`; `face_module/__init__.py` `19f02356a689fd068b12a7240fabbbe62c878352`.
- PR #20 และ PR #18 คง Open / Draft / Not Merged. V1/V2 Stable ไม่ถูกแก้; ไม่มี binary/model weights/customer images ถูก commit; `real_inference_verified=false` และ `quality_certified=false` ยังคงเดิม.

## 8 พฤศจิกายน 2569 — first-launch consent และ regression ล่าสุดบน PR HEAD

- แก้เอกสารให้ตรงกับ Source ปัจจุบัน: นอกจาก Installer task ที่ไม่เลือกไว้โดยค่าเริ่มต้นแล้ว Editor ยังแสดง consent prompt ครั้งแรกเมื่อ Manifest ยังไม่ผ่าน SHA256/engine validation และไม่มี `setup-declined.flag`; ผู้ใช้เลือกยินยอมครั้งเดียวสำหรับ AI ทั้งสี่ หรือปฏิเสธแล้วไม่ถูกถามซ้ำทุกครั้ง. การดาวน์โหลดทำงานบน Background Worker และไม่เริ่มก่อนยินยอม.
- Commit `367908e0b4946b2dafdca47d3e3ca299c0744ce1` ซึ่งเป็น code/test HEAD ที่ Independent Core #893 ครอบคลุม เปลี่ยนเฉพาะ `tests/test_v211_isolated_installer.py` เพื่อให้ Test Contract สอดคล้องกับ first-launch consent. อย่างไรก็ตามการเปรียบเทียบ Candidate code/test SHA `c0d539ad52140f3ef1424d0e045e6f98b31cc3a4` ถึง `367908e` พบ **23 commits / 14 changed files** รวม Production Source ใน `app_v2.py`, `v211_auto_setup.py`, `v211_four_engine_bridge.py`, `v211_setup_cli.py`, `tools/v211_four_engine_fusion.py`, `tools/v211_four_engine_run.py` และ `tools/v211_four_engine_tiled_inference.py`; จึงมีการเปลี่ยน Production Code หลัง Candidate #341 จริง. PR HEAD ปัจจุบันขยับต่อเป็น `513ce2bddd84000977c5830867646df2c836978d` ด้วย documentation-only commits.
- Independent Core run **#893 / 42420255774** ผูกกับ HEAD นี้และสำเร็จทั้งสองระบบ: Windows **781 passed, 1 skipped**; Ubuntu **779 passed, 3 skipped**; `compileall` ผ่านทั้งคู่. Job logs ยืนยัน pytest และ compileall สำเร็จ — https://github.com/niyomse-collab/niyom/actions/runs/42420255774.
- Windows Candidate workflow มี path trigger สำหรับ `tests/test_v211_*.py`, `signprint_ai/**` และ `tools/v211_*.py`; การเปลี่ยน Production Source 7 ไฟล์และ tests ระหว่าง `c0d539a` ถึง `367908e` อยู่ใน filter. แต่ Actions query ที่ตรวจได้ในรอบนี้คืนเฉพาะ PR-triggered runs จึงยังไม่มี push-triggered Candidate run ID/Artifact ที่ยืนยันตรงกับ Production HEAD นี้. Candidate #341 สร้างจาก `c0d539a` ก่อนการเปลี่ยน Production Source ดังกล่าว จึง **ล้าสมัยและห้ามใช้เป็น Frozen/Installer acceptance ของ HEAD ปัจจุบัน**. Documentation-only HEAD `513ce2b` ไม่อยู่ใน Candidate workflow path filter. ติดตาม workflow: https://github.com/niyomse-collab/niyom/actions/workflows/v211-four-engine-bridge-windows.yml.
- Independent Core run **#894 / 42421337196** บน documentation-only PR HEAD `e0752f99f89510e6dc87a875a5a5d760a9a19e27` สำเร็จทั้งสองระบบ: Windows **781 passed, 1 skipped**; Ubuntu **779 passed, 3 skipped**; `compileall` ผ่านทั้งคู่ — https://github.com/niyomse-collab/niyom/actions/runs/42421337196.
- ตรวจ PR #20 เทียบ PR #18 branch `feature/v2.1.1-super-ai`: Git blob SHA ตรงกัน 4/4 สำหรับ `face_protection.py` (`7795bfd409e68e17c80ef0b401b8c099074e22b8`), `large_faces.py` (`0faafd0c442e156def34faee7fbf98fc65cf754f`), `v211_face_contract.py` (`4d63a947301b559f37bfb68e283b8cd872fcde19`) และ `face_module/__init__.py` (`19f02356a689fd068b12a7240fabbbe62c878352`). เป็น Git blob IDs ไม่ใช่ SHA256 ของไฟล์.
- Core regression และ Candidate packaging ไม่ได้พิสูจน์ Native inference ทั้งสี่บน GTX 1660 Ti, การเลือก Vulkan adapter จริง, peak VRAM 6GB, A/B คุณภาพภาพ หรือ Print QA; คง `real_inference_verified=false` และ `quality_certified=false`. PR #20/PR #18 ยังคง Draft; ไม่มี Merge/Release และไม่แก้ V1/V2 Stable.

## 8 พฤศจิกายน 2569 — ICC mismatch guard และ Core #901

- พบช่องโหว่ metadata contract ในทั้ง small-image และ disk-backed large-image seed path: เดิมตรวจ ICC mismatch เฉพาะเมื่อ source มี ICC bytes; กรณี source ไม่มี ICC แต่ accepted V2 มี ICC จะผ่าน แล้ว seed รับ ICC จาก V2 ทำให้ข้อมูล RGB ที่ไม่ระบุ profile ถูกติดป้าย profile โดยไม่มีหลักฐาน.
- แก้ `signprint_ai/v211_four_engine_bridge.py` และ `signprint_ai/v211_large_image_bridge.py` ให้ต้องมี ICC bytes ตรงกันทุกกรณี รวมถึง `None` เทียบกับ bytes; mismatch แบบขาด/มี profile หรือเนื้อหาไม่ตรงจะหยุด auxiliary fusion ก่อนสร้าง work directory และคง accepted V2 output เดิม.
- เพิ่ม `test_small_and_large_seed_paths_reject_one_sided_icc` ครอบคลุมทั้ง source-unprofiled/V2-profiled และ source-profiled/V2-unprofiled ในทั้งสองเส้นทาง. ปรับ fixture ของ valid fusion/TIFF tests ให้ source และ V2 ใช้ sRGB ICC เดียวกัน; ไม่ได้ผ่อนเงื่อนไข production.
- Intermediate Core #900 พบ test-contract mismatch 2 รายการ (regex ของ assertion หนึ่งตำแหน่งยังใช้ข้อความเก่า); แก้ assertion ที่เหลือใน commit `6acda331c981af81603f1718074783bcbaa3cceb`.
- Independent Core run **#901 / 42422193575** บน code/test HEAD `6acda331c981af81603f1718074783bcbaa3cceb` ผ่านทั้งสองระบบ: Windows **783 passed, 1 skipped**; Ubuntu **781 passed, 3 skipped**; `compileall` ผ่านทั้งคู่ — https://github.com/niyomse-collab/niyom/actions/runs/42422193575.
- Candidate #341 ยังไม่ใช่หลักฐานของ code HEAD ปัจจุบัน; push-triggered Candidate run ล่าสุดยังไม่มี Run ID/Artifact ที่ตรวจยืนยันได้จาก Actions connector. ต้องตรวจ Candidate Workflow/Artifact ให้ตรงกับ code/test HEAD `6acda331` ก่อนพิจารณา Frozen package.
- ICC guard นี้เป็นการป้องกัน metadata mismatch เท่านั้น ไม่ใช่การรับรอง colour accuracy หรือภาพพิมพ์จริง; Native inference ทั้งสี่บน GTX 1660 Ti, VRAM 6GB, A/B คุณภาพ และ Photoshop/MainTop ยังไม่รับรอง.

### 8 November 2026 — manifest trust hardening, runtime GPU binding and latest CI

- Manifest loading now checks the repository-pinned upstream archive SHA256 and digest source, exact source/license provenance, expected official executable names, isolated per-engine paths, SHA256 for every model asset, exact model/scale CLI arguments, bounded process timeout, and a common provisioned engine root. A legacy manifest without the newer archive_digest_source field remains accepted only when its archive SHA256 and provenance still match the current repository pins.
- Added regression cases for edited archive pins, changed provenance, external executable/model paths, wrong executable names, unsafe CLI arguments, legacy manifests, and the per-run GPU flags that v211_gpu_device_binding adds (-g for NCNN and -p/-d for Anime4KCPP). This last compatibility check is required because the runtime-bound manifest is loaded again immediately before native subprocess execution.
- During the hardening work, Core #912 exposed a stale package-registry reference (NameError); #913/#914 exposed the ordering of the Anime4K embedded-algorithm exception check. Both were fixed. Core #915 then passed Windows 793 passed / 1 skipped and Ubuntu 791 passed / 3 skipped. Core #916 passed Windows 793 / 1 skipped and Ubuntu 791 / 3 skipped.
- Latest Core #917 on code/test HEAD d313319d92db794ea53056ac08499ccbd96dcdd8 passed: Windows 798 passed / 1 skipped, Ubuntu 796 passed / 3 skipped, with compileall passing on both. Run: https://github.com/niyomse-collab/niyom/actions/runs/42432497673.
- The Windows Candidate workflow is now scoped to the Draft PR #20 head branch and base branch feature/v2.1.1-super-ai, so its PR-triggered run is visible alongside Core checks. Candidate #392 on the same latest code/test HEAD is in progress: https://github.com/niyomse-collab/niyom/actions/runs/42432497663. Candidate #391 was superseded/cancelled by the newer source update.
- Earlier Candidate #380 completed successfully on source HEAD cd93819851ee3877bcd74ca8da9cc831e4e39aa8, but is superseded by the manifest/GPU-binding hardening above. Its installer SHA256 was 151ccfc18ae9e89092af68c15509598f9756e7f9a335793e19ae15cc217dad1a; uploaded artifact ZIP was 2,584,441,682 bytes with digest 7a772a353f6a5d949f4ab103878a99445d9852a6814d52f61ca21a9ad38de525 (artifact ID 13596444870). Do not use that stale artifact as the current candidate. Run: https://github.com/niyomse-collab/niyom/actions/runs/42427638832.
- PR #18 GFPGAN/face-protection files remain byte-identical 4/4. Current PR #20 contains 57 changed source/test/documentation files and no executable, DLL, archive or model-weight files. No V1/V2 Stable files were changed; no merge/release or quality certification was performed.
- The four-engine native GPU run on the shop GTX 1660 Ti, 6 GB VRAM stress, large-print native tile execution, and visual A/B comparison against V2 remain unverified. Hosted-runner Vulkan errors are not treated as proof of shop-PC failure or success.


## 8 พฤศจิกายน 2569 — enforce source-to-print scale before native GPU work

- The bridge now checks the **original source dimensions against the accepted V2 output dimensions**, not only the half-target seed seen by the fixed-2x native runner. This closes a gap where an 8x original target could otherwise look like a valid 2x seed-to-reference job.
- Small auxiliary jobs accept only exact isotropic 2x or 4x source-to-V2 geometry. The 4x path is a half-target seed followed by one native 2x pass; it is not native 4x or multi-pass inference. 3x, 8x, custom and anisotropic geometries fail before GPU binding/native launch.
- Jobs above 18 MP accept only exact 2x PNG source-to-V2 geometry through the disk-backed route. Large 4x/8x and non-PNG source/V2 paths remain V2-only until a separately validated multi-pass/format route exists.
- Regression tests now cover supported small 2x/4x, unsupported small geometries, large exact-2x tiled execution, and large 4x/8x rejection before GPU binding. The tiled fusion fixture uses distinct engine detail strengths so the weaker conditional Anime4K term is tested without artificially increasing its production weight.
- This is an orchestration/guardrail correction. It does not certify Native GPU execution, 6 GB peak VRAM, large-image 4x/8x, or visual quality versus V2.

## 9 พฤศจิกายน 2569 — เปิด Large 4x แบบ disk-backed โดยไม่เพิ่ม Native Pass

- ปรับ Bridge ให้รับ source-to-V2 geometry แบบ PNG ที่เป็น isotropic 2x **หรือ 4x** เมื่อเข้าเส้นทางภาพใหญ่เกิน 18 MP; ทั้งสองกรณีสร้าง seed ครึ่ง target ด้วย libvips แล้วเรียก Native Engine เพียง 2x หนึ่ง pass ต่อ tile.
- สำหรับ 4x จากภาพต้นฉบับ seed มีขนาด 2x ของต้นฉบับ และ Native 2x pass จึงได้ target 4x. นี่ไม่ใช่ Native 4x, ไม่ใช่การรัน AI ต่อเนื่องหลาย pass และไม่เปลี่ยน V2 Master.
- เพิ่ม integration test ให้ใช้ streamed seed/reference, tiled runner, fusion และ QA crop จริงในโค้ด โดยแทนเฉพาะ Native executables ด้วย synthetic processors; ครอบคลุม target scale 2x และ 4x. งาน 8x/3x/custom/anisotropic, non-PNG large, CMYK/PDF/PSD ยังคง fail-closed.
- การทดสอบนี้พิสูจน์ orchestration/disk path เท่านั้น ไม่ใช่ Native inference บน GTX 1660 Ti, ไม่ใช่ peak VRAM 6 GB, ไม่ใช่คุณภาพเหนือ V2 และไม่ใช่ print certification. ต้องรอ CI HEAD ใหม่และทดสอบเครื่องร้าน.


## 9 พฤศจิกายน 2569 — Candidate #451 และเปิด Large 8x แบบ QA-only

- Windows Candidate **#451** บน PR HEAD `3be9bd2ce8702bd545c89eabef024ff1ae98b802` สำเร็จทั้ง `bridge-tests` และ `windows-v2-candidate`. Bridge/Privacy tests ผ่าน **290 รายการ** (231 + 59); Independent Core **#976** ผ่าน Windows **832 passed / 1 skipped** และ Ubuntu **830 passed / 3 skipped**, พร้อม compileall ทั้งสองระบบ.
- Candidate #451 ตรวจ Frozen V2 imports, packaged provisioning `--check-only` แบบไม่ดาวน์โหลด, consented cleanup บน synthetic cache, diagnostic `--help`, BUILD_PROOF source SHA และ installer slice SHA256 ครบ. นี่เป็น Frozen/package provenance pass ไม่ใช่การติดตั้งหรือรัน GPU จริงบนเครื่องร้าน.
- Installer SHA256: `6c078d3805262722bdfca20cea5a60734981d6df8a9af60f8efba264acd6c020`. Artifact ID `13635710275`, ZIP SHA256 `57650a7fecd53e43b6879ec97c7f155bfd34ecc89f2f643400aeb6cc86ff6f98`, ขนาด **2,584,565,314 bytes**; หมดอายุ 15 พ.ย. 2569 21:37 UTC. [Candidate #451](https://github.com/niyomse-collab/niyom/actions/runs/42524375276) · [Artifact](https://github.com/niyomse-collab/niyom/actions/runs/42524375276/artifacts/13635710275).
- PyInstaller มีคำเตือน non-fatal ว่าไม่พบ `nvcuda.dll` และ optional `tbb12.dll` บน Hosted Runner. ไม่ได้เพิ่ม DLL เหล่านี้แบบเดาสุ่ม; ต้องตรวจความเกี่ยวข้องกับ runtime บนเครื่อง GTX 1660 Ti จริง.
- ปรับ Bridge ให้รับ Large PNG geometry แบบ isotropic **2x/4x/8x** เมื่อ source หรือ V2 target เกิน 18 MP. Large 8x สร้าง half-target seed ที่ 4x source geometry แล้วใช้ Native Engine 2x เพียงหนึ่ง pass ต่อ tile; ไม่ใช่ Native 8x และไม่ใช่ multi-pass. Small 8x, 3x, custom, anisotropic และ Large non-PNG ยังคง fail-closed.
- เพิ่ม synthetic integration coverage ให้เส้นทาง streamed seed → tiled runner → fusion → QA crop สำหรับ Large 2x/4x/8x และคงการปฏิเสธ Large 3x. V2 master ไม่ถูกเขียนทับ. การทดสอบนี้ยังไม่ใช่ native GPU inference, peak-VRAM stress หรือ quality A/B.
- Native CLI Smoke #45 ยังคงเป็น diagnostic: Real-CUGAN/Anime4KCPP ทำ synthetic output ได้; Real-ESRGAN/Waifu2x ถูกบล็อกด้วย `vkCreateInstance failed -9` บน Hosted Runner. ต้องทดสอบทั้งสี่บน Windows 11 GTX 1660 Ti ของร้าน.


### 9 พฤศจิกายน 2569 — ตรวจแก้ Large 8x attribution regression

- Core run **#977** บน commit `9983dc1` พบ failure 1 รายการจาก integration fixture ของ Large 8x: native-like synthetic processors ทั้งสี่จบครบ แต่ conditional Anime4K term ไม่เปลี่ยน final 8-bit RGB pixel หลัง edge gate/rounding; ดังนั้น Bridge คืน `four_engine_fusion_contribution_incomplete` และไม่สร้าง QA sidecar. Windows job ถูกยกเลิกหลัง Ubuntu fail-fast; Ubuntu รายงาน **830 passed, 1 failed, 3 skipped**.
- ตรวจ root cause แล้วไม่ลด Anime4K agreement threshold/เพิ่ม production weight เพราะจะทำให้รายละเอียดที่ไม่สอดคล้องกับ 3 primary engines ผ่านโดยไม่มีหลักฐาน. ปรับ regression ให้คาดหวัง fail-closed ที่ถูกต้องสำหรับ fixture 8x นี้: ต้องรัน candidate ทั้งสี่ครบ, primary 3 engines ต้องมี pixel effect, Anime4K ที่ไม่มี effect ต้องทำให้ QA output ถูก withheld และ V2 bytes ต้องคงเดิม. Large 2x/4x ยังคงต้องพิสูจน์ contribution ครบทั้งสี่.
- นี่ไม่ใช่การรับรองว่า Anime4K จะไม่ contribute กับภาพ 8x จริงทุกภาพ; เป็นข้อจำกัดที่พบใน synthetic high-contrast fixture. Native shop-PC A/B ยังจำเป็น.


## 9 พฤศจิกายน 2569 — Candidate #453 สำเร็จบน HEAD 9ff6102

- ตรวจ PR #20 ยังเป็น Draft / Open / Unmerged บน branch `work/v211-four-engine-v2-bridge-20261103`; ไม่มีการเปลี่ยน V1 หรือ V2 Stable.
- Independent Core #978 สำเร็จ: Windows **833 passed / 1 skipped**; Ubuntu **831 passed / 3 skipped**; compileall ผ่านทั้งสองระบบ. [Core #978](https://github.com/niyomse-collab/niyom/actions/runs/42529393896).
- Windows Candidate #453 สำเร็จทั้ง `bridge-tests` และ `windows-v2-candidate`. Bridge/Privacy Regression รวม **291 tests** (232 bridge/fusion/coordination + 59 privacy/provisioning/manifest).
- Frozen candidate checks ผ่าน: packaged V2 import; provisioning `--check-only` โดยไม่ดาวน์โหลด; isolated synthetic cache cleanup; diagnostic `--help` dispatch; BUILD_PROOF ผูกกับ source SHA; ตรวจ SHA256 ทุก installer slice; upload artifact สำเร็จ. Diagnostic `--help` ไม่ใช่การยืนยันว่า GPU runtime ใช้ adapter จริง.
- Artifact: ID `13637810380`; size **2,584,515,637 bytes**; artifact ZIP SHA256 `62e026bf145cdcf4aa75a50468b1f08a9ea62c32fdb0fb4d8f384e97f3f57f3e`; expires **15 Nov 2026 22:41 UTC**. [Candidate #453 / Artifact](https://github.com/niyomse-collab/niyom/actions/runs/42529393923/artifacts/13637810380).
- Official archive audit #42 succeeded on this HEAD: all four official Windows archives were downloaded, checked against published/recorded hashes, safety-audited and transactionally provisioned into an ephemeral QA directory; exact four-engine manifest verification passed. [Audit #42](https://github.com/niyomse-collab/niyom/actions/runs/42529394095). Publisher-published digests remain absent for Real-ESRGAN v0.2.5.0 and Real-CUGAN 20220728; their hashes remain observed CI pins, not publisher attestations. Redistribution approval remains false.
- Native CLI smoke #47 completed as a **classified diagnostic only**: Real-CUGAN and Anime4KCPP produced validated synthetic 2x outputs; Real-ESRGAN and Waifu2x were blocked by hosted-runner Vulkan initialization `vkCreateInstance failed -9`. [CLI smoke #47](https://github.com/niyomse-collab/niyom/actions/runs/42529393862). This does not contradict the owner's earlier individual Windows 11 GTX 1660 Ti tests, but it does not prove integrated four-engine inference or physical GPU binding.
- Large PNG 2x/4x/8x synthetic disk-backed orchestration exists in the current branch, with one native 2x pass per engine on a half-target seed. 4x/8x labels describe source-to-target geometry, **not native 4x/8x or multi-pass inference**. Current evidence does not include a customer-size >18 MP native GPU run, peak 6 GB VRAM measurement, cancellation during a real Windows native process, or visual A/B.
- Rechecked PR #18 face/GFPGAN baseline against PR #20: `face_protection.py`, `large_faces.py`, `v211_face_contract.py`, and `face_module/__init__.py` are byte-identical (4/4).
- No executable/DLL/archive/model weights/customer images were added to Git. PR #20 remains Draft/unmerged; no release, no V1/V2 Stable modification, and no quality-superiority claim.

## 11 พฤศจิกายน 2569 — Candidate #553, Native CLI diagnostic และการคุ้มครอง V2

ขอบเขตยังคงจำกัดเฉพาะ Draft PR #20 / `work/v211-four-engine-v2-bridge-20261103`; ไม่มีการแก้ V1 หรือ V2 Stable, ไม่มี merge/release และไม่ส่งงานไป self-hosted shop runner โดยไม่มี consent marker.

### HEAD และ Candidate ที่ยืนยันจาก GitHub
- Production/test HEAD ที่ Candidate สร้าง: `21366b61a98388324b120585c039598b046fb142`.
- Windows Candidate **#553**: [run #42827575892](https://github.com/niyomse-collab/niyom/actions/runs/42827575892) — ทั้ง `bridge-tests` และ `windows-v2-candidate` สำเร็จ. Bridge tests **286 passed**; privacy/provisioning/hash tests **63 passed**.
- Frozen job ตรวจ V2 imports, packaged provisioning `--check-only` โดยไม่ดาวน์โหลด, isolated cache cleanup, diagnostic `--help`, BUILD_PROOF/source SHA และ SHA256 ของ installer slices ครบ.
- Artifact ID `13772740302`, ขนาด **2,584,696,547 bytes**, ZIP SHA256 `42a104c6f9377bba1544113fed9bac281ba725bcbf3ea8ae36f05b1b15b4a5ec`, installer SHA256 `054e4ce83ac32363fcb603719e259eee282a9d9ddb6cb295baeb7c40ac3cf046`; หมดอายุ **17 พ.ย. 2569 21:15:57 น. ICT**. [Artifact #553](https://github.com/niyomse-collab/niyom/actions/runs/42827575892/artifacts/13772740302).
- Candidate #553 เป็น frozen-package/provenance pass เท่านั้น ไม่รับรองการติดตั้ง/รันบนเครื่องร้าน, Vulkan, Native GPU 4/4, peak VRAM, A/B หรือคุณภาพพิมพ์. ไม่มี native executables/weights ฝังใน installer.

### Core และ Native CLI — แยกผลให้ตรงตามหลักฐาน
- Independent Core **#42827576038** บน production/test HEAD `21366b61`: Windows **897 passed / 1 skipped**, Ubuntu **895 passed / 3 skipped**, compileall ผ่านทั้งคู่. [Core #42827576038](https://github.com/niyomse-collab/niyom/actions/runs/42827576038).
- Native CLI Smoke **#42827576125** เป็น classified diagnostic ไม่ใช่ inference acceptance. บน Hosted Windows, Real-CUGAN และ Anime4KCPP จบ native process และสร้าง synthetic 2x RGB/RGBA output ที่ผ่าน dimension/ICC/DPI/alpha invariants; Real-ESRGAN และ Waifu2x ล้มด้วย `vkCreateInstance failed -9`. NVML ไม่พบ library และ `runtime_device_use_verified=false` สำหรับทั้งสี่. [Native CLI Smoke #42827576125](https://github.com/niyomse-collab/niyom/actions/runs/42827576125).
- Workflow จัดประเภท Vulkan limitation แล้วจึงจบเป็น diagnostic SUCCESS; ห้ามอ่านสีเขียวนี้เป็น Native GPU 4/4 หรือ quality pass. ผล Hosted Runner ไม่ได้หักล้างผลรายตัวที่เจ้าของเคยทดสอบบน Windows 11 GTX 1660 Ti และก็ไม่ใช่หลักฐานว่า integrated four-engine fusion ผ่าน.

### Shop evidence และ consent
- Shop GPU Evidence #24: hosted `gate_status` ผ่าน แต่ `evidence` ถูก SKIPPED เพราะไม่มี affirmative consent/candidate marker; ไม่มีการเข้าถึง self-hosted shop PC. [Shop Evidence #24](https://github.com/niyomse-collab/niyom/actions/runs/42794027373).
- QA document `docs/V211_WINDOWS_REAL_FOUR_ENGINE_QA_TH.md` ได้ปรับข้อมูลจาก Candidate #531 ที่ล้าสมัยเป็น Candidate #553 และบันทึก source SHA, installer/ZIP hashes, artifact ID และวันหมดอายุแล้ว.
- การแก้เอกสารรอบนี้เป็น documentation-only; ไม่มี consent marker จึงไม่อนุญาตให้ workflow schedule self-hosted runner. Commit: [2734ad7](https://github.com/niyomse-collab/niyom/commit/2734ad7ecfa635a98b3651b17c249fd5acb54dbe).

### PR #18 / V2-GFPGAN
- Git Blob SHA ของ `face_protection.py`, `large_faces.py`, `v211_face_contract.py` และ `face_module/__init__.py` เทียบ PR #18 กับ PR #20 ตรงกัน **4/4**; Core Adapter ยังเรียก Face Module เดิม.
- PR #20 ปิด Optional HAT Assist execution route ที่มีใน PR #18 และมี regression test ป้องกันการเรียก route ดังกล่าว. นี่เป็น compatibility difference แยกจาก GFPGAN; ต้องคงบันทึกไว้เป็นประเด็นก่อน merge ไม่ restore HAT โดยอัตโนมัติ.

### สิ่งที่ยังไม่ผ่าน
- Native GPU 4/4 พร้อม physical-adapter telemetry บน Windows 11 GTX 1660 Ti.
- Peak VRAM 6 GB, cancellation ระหว่าง native tiled process, และ large-print >18 MP stress บนเครื่องร้าน.
- Equal-pixel A/B ครบคน/สัตว์/วัตถุ/กรอบ/ลายไทย/ไทย-อังกฤษ-จีน/flat fill/gradient/RGBA/ใบหน้า.
- Photoshop, MainTop, RIP และงานพิมพ์จริง.
- Real-ESRGAN และ Real-CUGAN ยังใช้ observed-CI archive SHA ไม่ใช่ publisher-published digest; model-weight/license certification และ redistribution approval ยังคง false.

**สถานะ:** V2 ยังคง accepted master. PR #20 คง Draft/unmerged; ไม่อ้างว่าคุณภาพเหนือ V2; ไม่มีการแก้ V1/V2 Stable, ไม่มี merge/release และไม่มี binaries/weights/ภาพลูกค้าใน Git.


## 12 พฤศจิกายน 2569 — fail-closed protection สำหรับ styled/FX text (ยังไม่ใช่ text reconstruction)

- เพิ่ม V21Settings.v211_protected_effect_regions เป็น ROI พิกัด normalized จากภาพต้นฉบับ เพื่อให้ผู้เรียกที่มี ROI จากการเลือก/ตัวจำแนกที่เชื่อถือได้ส่งขอบเขตข้อความที่มี gradient, หลายชั้น stroke, glow, shadow, bevel หรือ texture มาให้ Four-Engine QA ได้
- Adapter แปลง ROI ผ่าน transform เดียวกับ fit/stretch ไปยัง canvas V2 จริง; fusion กันพื้นที่ ROI พร้อม safety margin 6 px และคง RGB ของ V2 ในพื้นที่นั้นแบบ pixel-identical ขณะที่ยังประมวลผลพื้นที่อื่นได้
- หาก ROI ไม่ถูกต้องหรือ map ไม่ได้ จะคง V2 และไม่เปิด native engines/ไม่สร้าง QA sidecar (fail-closed)
- ค่าเริ่มต้นเป็น ROI ว่าง จึงยังไม่มี automatic styled-text detector; ต้องมี ROI จากผู้เรียก/ตัวจำแนกก่อน การเปลี่ยนแปลงนี้เป็น protection contract เท่านั้น ไม่ใช่ OCR, การพิมพ์ข้อความใหม่ หรือการกู้คืน gradient/effect ที่หายไป
- เพิ่ม synthetic tests สำหรับ gradient fill, double-stroke/bevel-style region, pixel-exact protection, unprotected-region contribution และ fit/stretch mapping; ภาพ synthetic เท่านั้น ไม่ใช้ภาพลูกค้า
- ยังต้องทำ A/B กับป้ายจริงที่ได้รับอนุญาตและตรวจ Photoshop/MainTop/RIP ก่อนอ้างคุณภาพหรือเปิดใช้จริง


## 12 November 2026 correction — editor first-launch consent

- The V2.1.1 editor now performs a local-only setup-state check 600 ms after the window opens. It does not contact the network while checking for a verified four-engine manifest or the local `setup-declined.flag`.
- If all four engines are already verified, the editor does not prompt. If the user previously selected No, the local decline marker suppresses repeat prompts. If the existing manifest is invalid, the editor warns and fails closed rather than overwriting it.
- When no verified manifest or decline marker exists, the editor asks one Yes/No question for all four official engines. Only Yes starts the background worker through `provision_after_user_consent(consent=True)`; No records the decline locally. A failed download leaves V2 available and does not mark the setup as declined, allowing a later retry.
- The installer checkbox remains an optional earlier consent path. If it is skipped, the editor's first-launch prompt is the consent surface. No individual per-engine buttons are added.
- The downloaded archives remain in the current Windows user's LocalAppData, are SHA256-verified before provisioning, and are not committed or uploaded. Customer artwork is never part of setup.
- This corrects the earlier installer-only wording. The first-launch setup path remains a V2.1.1 experimental feature and is not a shop-PC inference or image-quality certification.


## 12 November 2026 — superseded candidate concurrency

- The Windows candidate workflow now scopes its concurrency group to the PR head branch (or push branch name) and sets `cancel-in-progress: true`. Push and pull-request events for the same branch share one group, so a newer commit replaces an older candidate run instead of waiting behind a stale build from a previous commit.
- This does not merge, release, or change V1/V2 Stable. It only changes the experimental PR #20 CI scheduling policy.

## 12 November 2026 — manifest parent-link preflight hardening

- The manifest safety check now validates every existing component of the selected manifest path during the local-only first-launch state check, including a symlink/junction parent when the final `manifest.json` does not yet exist.
- The same path-component validation is repeated at the consented provisioning boundary **before** any official archive is downloaded. An unsafe parent path returns an invalid setup state / raises a safe-path error without network access.
- Added a directory-symlink regression covering both the no-network status check and the consented provisioning path. Runners that cannot create directory symlinks report the test as skipped rather than treating it as a pass.
- This is path-safety hardening only; it does not alter engine inference, the accepted V2 output, V1, V2 Stable, GFPGAN, or the one-time consent behavior.
