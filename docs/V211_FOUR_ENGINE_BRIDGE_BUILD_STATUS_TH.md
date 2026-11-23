# NiyomSilp V2.1.1 — Four real AI engines integrated in Windows experimental build (4 November 2026)

Branch: work/v211-four-engine-v2-bridge-20261103 / Draft PR #20.
Do not merge/release as accepted V2.1.1 until the shop approves side-by-side image QA.

## Implemented in experimental branch

- Keep V2 Real-ESRGAN main enhancement, GFPGAN face restoration, sliders, Windows output behaviour and alpha/ICC/DPI print path unchanged.
- Once the user confirms a one-time download, install four native upstream AI executables plus their model assets in private LOCALAPPDATA and validate archive SHA256 and a SHA256-checked manifest. Subsequent usage is offline. Executables/weights are not bundled in our distributed installer.
- For supported RGB/RGBA raster source/V2 pairs, the bridge maps the original source onto the accepted V2 target canvas with the same `fit` or `stretch` mode, then creates a private half-target seed. All four installed native executables run sequentially at one native 2x pass each. Overall source-to-target geometry can be 2x, 3x, 4x, 8x, custom or anisotropic, subject to format, pixel, row, disk and minimum-seed guards; these are output-geometry ratios, not native 3x/4x/8x inference or multi-pass processing. Large jobs use libvips disk-backed seed/reference preparation, 512-pixel core tiles with 32-pixel overlap, seam checks and streamed fusion/QA. Odd V2 dimensions are edge-padded and cropped back for the QA PNG. Missing or unverified engines never result in a false claim of completed fusion; accepted V2 stays untouched.
- An additional tiled pixel fusion consumes outputs from all four models. Real-ESRGAN/Waifu2x/Real-CUGAN supply the majority of permitted edge detail; Anime4K only supplies bounded, agreeing edge detail. The fusion retains the original accepted V2 colours, ICC, print DPI and alpha, protects explicitly selected face rectangles and can preserve the entire V2 portrait when automatic face restoration ran without known rectangles.
- After all four pass their individual PNG checks and the fusion gate, save a separate experimental *.V211-4AI-QA-xxxxxxxx.png next to the V2 print file, and show it as the right-hand preview. It is NOT an automatically accepted or quality-certified print export.
- Intermediate candidate images are deleted by default; explicit NIYOMSIL_V211_FOUR_AI_EVIDENCE_DIR can retain them in a private local QA folder for A/B. Customer images must not be uploaded publicly.
- Normal V2 export, PDF/PSD/CMYK jobs, unsupported raster modes/formats or jobs outside the auxiliary limits, incomplete model installations and machine failures fail closed back to V2 instead of blocking the customer's completed V2 export. Supported raster inputs produce a separate PNG QA sidecar; the original print export remains unchanged.

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

- The auxiliary route uses an in-memory path at or below 18 MP and a disk-backed libvips/native-tile/streamed-fusion/streamed-QA path above 18 MP for supported 8-bit RGB/RGBA raster jobs. Large source inputs accept PNG/JPEG/WebP/single-page TIFF/BigTIFF; accepted V2 rasters accept PNG/JPEG/single-page TIFF/BigTIFF. libvips converts these to private PNG seed/reference intermediates. Guards are at most 1,000 MP, at most 64 MiB per output row, a disk-space reserve calculated before work, and a minimum 64×64 large seed. Native tile inference uses 512-pixel cores with 32-pixel overlap and runs one native 2x pass per engine sequentially. Overall source-to-V2 target geometry can be 2x/3x/4x/8x/custom/anisotropic because the source is mapped to a half-target seed; this is not native 3x/4x/8x inference or multi-pass model processing. Unsupported modes/depths, CMYK, multipage TIFF, PDF/PSD, exceeded limits or insufficient disk fail closed to the already-saved V2 output.
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
- การยินยอมดาวน์โหลดมี 2 ช่องทาง: (1) Inno Setup task `installfourai` ซึ่งไม่เลือกไว้โดยค่าเริ่มต้น; หากเลือกจะ provision และตรวจ SHA256 ของ AI ทั้งสี่ก่อนเปิด Editor; (2) หากข้าม task และยังไม่มี Manifest ที่ตรวจครบหรือ `setup-declined.flag`, Editor จะตรวจเฉพาะไฟล์ในเครื่องหลังเปิดประมาณ 600 ms แล้วถาม Yes/No หนึ่งครั้ง (ค่าเริ่มต้น No). Yes เท่านั้นที่เริ่มดาวน์โหลดบน background worker; No บันทึก decline marker เพื่อไม่ถามซ้ำ. ทั้งสองช่องทางไม่เริ่ม network ก่อน affirmative consent. เมื่อ Manifest ผ่านการตรวจครบ งาน V2.1.1 ที่รองรับจะเรียก AI ทั้งสี่แบบ offline โดยอัตโนมัติ. หากไม่ยินยอมหรือ setup ล้มเหลว V2 เดิมยังใช้งานได้.
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

## 12 พฤศจิกายน 2569 — แก้ Windows Candidate #623 ที่ล้มใน PowerShell parser

- ตรวจ Run #623 แล้วพบว่า bridge-tests ผ่าน แต่ windows-v2-candidate ล้มในขั้นตรวจ BUILD_PROOF/installer slices หลัง Frozen Build, packaged import, provisioning check-only, cache cleanup และ diagnostic help ผ่านทั้งหมด
- Root cause เป็น PowerShell syntax error ใน inline provenance block: มีคำสั่ง throw สำหรับตรวจ GITHUB_SHA และวงเล็บปีกกาปิดที่หลงเหลือหลังเปลี่ยนจาก synthetic PR merge SHA มาใช้ PR head SHA ทำให้เกิด ParserError: Unexpected token '}' ก่อนตรวจ SHA256 จริง
- แก้โดยย้าย provenance verifier ไป tools/v211_verify_candidate_provenance.ps1, เพิ่ม PowerShell AST parse step ก่อนยอมรับ Candidate และตรวจ BUILD_PROOF กับ checkout SHA และ V211_EXPECTED_HEAD_SHA แทนการเทียบกับ GITHUB_SHA (ซึ่งเป็น synthetic merge SHA ใน pull_request event); ยังคงตรวจ Base SHA เป็น ancestor และ SHA256 ทุก installer slice
- เพิ่ม regression assertions ให้ workflow ต้อง parse verifier script และผูก expected PR head SHA อย่างชัดเจน
- Run #623: [Windows Candidate](https://github.com/niyomse-collab/niyom/actions/runs/43154174531) — FAILED ที่ provenance script parse; ไม่มี artifact upload และไม่มี Candidate ที่รับรองจาก Run นี้
- Core #1167: [Independent Core](https://github.com/niyomse-collab/niyom/actions/runs/43154174550) — SUCCESS; Official Archive Audit #108: [Audit](https://github.com/niyomse-collab/niyom/actions/runs/43154174571) — SUCCESS; Native CLI #141: [Diagnostic](https://github.com/niyomse-collab/niyom/actions/runs/43154174540) — classified hosted Vulkan failure for Real-ESRGAN/Waifu2x, synthetic outputs only for Real-CUGAN/Anime4KCPP, physical GPU verification 0/4.
- ต้องรอ Windows Candidate run บน commit แก้ไขนี้ให้ bridge-tests, PowerShell AST parse, provenance, installer slice SHA256 และ artifact upload ผ่านทั้งหมดก่อนใช้ Candidate บนเครื่องร้าน
- PR #20 remains Draft/unmerged. PR #18 GFPGAN protected files remain unchanged. No V1/V2 Stable changes, no shop GPU run, no merge/release, no quality certification.

## 12 พฤศจิกายน 2569 — แก้ regression assertion บน Ubuntu หลังแยก PowerShell verifier

- Independent Core #1169 พบ 1 test failure บน Ubuntu: workflow-contract test มองหา path แบบ slash แต่ YAML เรียก PowerShell path แบบ Windows. ไม่ใช่ failure ของ runtime verifier หรือ image pipeline.
- แก้ assertion ให้ตรวจ basename ของ verifier script ซึ่งใช้ได้ทั้ง path separator บน Windows และ Linux; test ยังคงตรวจว่ามี AST ParseFile step, expected PR head SHA, checkout SHA และ base-ancestor check.
- Run #1169: [Independent Core](https://github.com/niyomse-collab/niyom/actions/runs/43163620294) — Ubuntu 943 passed / 3 skipped / 1 failed; Windows ถูกยกเลิกตาม fail-fast หลัง Ubuntu ล้ม. ต้องรอ Core run ใหม่บน commit นี้.
- Windows Candidate #625 ถูกแทนที่ได้ตาม branch-scoped concurrency เมื่อ commit แก้ regression ถูก Push; ต้องใช้ run ใหม่เท่านั้น.
- PR #20 remains Draft/unmerged. No V1/V2 Stable changes, no shop GPU run, no merge/release, no quality certification.


## 13 พฤศจิกายน 2569 — สถานะปัจจุบัน PR #20 / Candidate #680

- ขอบเขต: เฉพาะ Draft PR #20 และสาขา `work/v211-four-engine-v2-bridge-20261103`; PR #18 ยังคงเป็นฐาน V2.1.1/GFPGAN ที่ PR #20 ต่ออยู่ ไม่มีการแก้ V1 หรือ V2 Stable
- PR #20 HEAD: `c89770074851b990698628d8c8e96e121e105a18`; PR #20 ยัง OPEN/DRAFT และไม่ merged
- Windows Candidate #680 [run 43314285413](https://github.com/niyomse-collab/niyom/actions/runs/43314285413) สำเร็จทั้ง bridge-tests และ windows-v2-candidate; Frozen imports, no-download provisioning check-only, isolated cache cleanup, diagnostic dispatch, PowerShell AST, source provenance, installer slice SHA256 และ artifact upload ผ่าน
- Artifact ID `13988039912`, ขนาด **2,584,579,685 bytes**, ZIP SHA256 `cf4c9fe1c6ffd4ad0fadfd3b9b473bbef16977a1d7278bc65891417074892a55`, installer SHA256 `5f18dc8f77e4ddf714645229f76ab4676ab026f5d68f476e2f33ebe409093fd6`; [Artifact #680](https://github.com/niyomse-collab/niyom/actions/runs/43314285413/artifacts/13988039912), หมดอายุ 20 พ.ย. 2569 05:16:55 ICT
- Independent Core #1232 [run 43314285420](https://github.com/niyomse-collab/niyom/actions/runs/43314285420): Windows **953 passed / 1 skipped**, Ubuntu **951 passed / 3 skipped**, compileall ผ่านทั้งสองระบบ
- Official Archive Audit #135 [run 43314285394](https://github.com/niyomse-collab/niyom/actions/runs/43314285394): official archives ทั้งสี่ผ่าน SHA256, safe archive audit และ transactional provisioning ใน ephemeral QA directory; manifest มี engine ครบสี่ แต่สถานะทุกตัวเป็น archive-only / inference-not-verified
- Native CLI Smoke #171 [run 43314285421](https://github.com/niyomse-collab/niyom/actions/runs/43314285421): Real-CUGAN และ Anime4KCPP native process จบ; Real-ESRGAN และ Waifu2x ถูกบล็อกด้วย `vkCreateInstance failed -9`; NVML ไม่พบ, adapter verification 0/4, `candidate_output_validation_complete=false`, `real_inference_verified=false`. นี่เป็น classified diagnostic SUCCESS ไม่ใช่ GPU acceptance
- Frozen Build มี non-fatal PyInstaller warnings ว่า Hosted Runner ไม่พบ `nvcuda.dll` และ optional `tbb12.dll`; ต้องตรวจ dependency บนเครื่องร้านจริง ไม่ bundle driver DLL โดยเดา
- Shop GPU Evidence ยังไม่ได้รัน: ไม่มี consent marker/การอนุมัติเครื่องร้านในรอบนี้. ยังไม่มีหลักฐาน Native GPU 4/4, hard VRAM cap 6 GB, peak VRAM, >18 MP native stress, cancel ระหว่าง native process, A/B เทียบ V2 หรือคุณภาพ Photoshop/MainTop/RIP
- PR #18 protected face/GFPGAN files ที่ตรวจเทียบกับ PR #20 ยังคง byte-identical **5/5**: `face_protection.py`, `large_faces.py`, `v211_face_contract.py`, `test_v211_face_contract.py`, `face_module/__init__.py`
- ไม่พบ executable/DLL/archive/model weights/customer images ในรายการ 68 changed files ของ PR #20. ไม่มีการ merge/release, ไม่เขียนทับ accepted V2 และไม่มีการอ้างว่าคุณภาพเหนือ V2
- ขั้นต่อไป: ติดตั้ง Candidate #680 ในเครื่องร้านและตรวจ BUILD_PROOF/source SHA; หลังได้รับ consent จึงทำ Shop GPU Evidence ด้วย synthetic images/JSON evidence เท่านั้น จากนั้นทำ VRAM/tile/cancel stress และ A/B ที่ได้รับอนุญาต


## 13 พฤศจิกายน 2569 — PR #20 HEAD 128c0eb0 / Windows Candidate #681

- PR #20 HEAD/source: `128c0eb0b8093630b3a7c9ce2a4ba7f1b9418f37` บน `work/v211-four-engine-v2-bridge-20261103`; PR ยังคง OPEN/DRAFT/UNMERGED.
- Windows Candidate #681: [run 43328241363](https://github.com/niyomse-collab/niyom/actions/runs/43328241363) — ทั้ง `bridge-tests` และ `windows-v2-candidate` สำเร็จ. Bridge tests: 321 passed + 63 passed. Frozen build ผ่าน V2 import smoke, packaged provisioning `--check-only` แบบไม่ดาวน์โหลด, isolated consented cache cleanup, diagnostic `--help`, PowerShell provenance parse, BUILD_PROOF/source SHA, installer-slice SHA256 และ artifact upload.
- Artifact ID `13995566000`; ขนาด **2,584,549,542 bytes**; ZIP SHA256 `cb4697045895a331ef6c0859b79bb95b28a2dd1f3aa01e6b5ab7db7a52ebf992`; installer SHA256 `b4e0553d845e2f29b944b85d8dc6caed212404d2a0a97c7ba548c371f1ade6b3`. [Candidate #681 artifact](https://github.com/niyomse-collab/niyom/actions/runs/43328241363/artifacts/13995566000), หมดอายุ **20 พ.ย. 2569 06:42:51 ICT**.
- Independent Core #1235: [run 43328241217](https://github.com/niyomse-collab/niyom/actions/runs/43328241217) — Windows **953 passed / 1 skipped**, Ubuntu **951 passed / 3 skipped**, compileall ผ่านทั้งสองระบบ.
- Official Archive Audit #136: [run 43328241206](https://github.com/niyomse-collab/niyom/actions/runs/43328241206) — official ZIP ทั้งสี่ผ่าน SHA256, archive audit และ transactional provisioning ใน ephemeral QA directory; ทุก engine ยังคงสถานะ `archive_audited_not_inference_verified`, redistribution approval=false.
- Native CLI Smoke #172: [run 43328241400](https://github.com/niyomse-collab/niyom/actions/runs/43328241400) — Real-CUGAN และ Anime4KCPP จบ native process และตรวจ synthetic output ได้; Real-ESRGAN/Waifu2x ถูก block ด้วย hosted-runner `vkCreateInstance failed -9`; NVML ไม่พบ, physical adapter verification **0/4**, `real_inference_verified=false`, `quality_improvement_verified=false`. เป็น diagnostic SUCCESS เท่านั้น ไม่ใช่ GPU/ภาพคุณภาพ acceptance.
- PyInstaller warnings ที่ตรวจจาก Candidate #681: `nvcuda.dll` ไม่พบใน Hosted Runner; `tbb12.dll` ไม่พบเป็น dependency ของ optional Numba TBB extension `numba.np.ufunc.tbbpool`; ยังมี optional hidden-import warnings สำหรับ pycparser/scipy. ทั้งหมดไม่ทำให้ Build ล้ม แต่ frozen import smoke ไม่ได้พิสูจน์ runtime CUDA/Numba บนเครื่องร้าน.
- การจัดประเภท `nvcuda.dll`: เป็น CUDA Driver API library ที่มาจาก NVIDIA driver บนเครื่องปลายทาง ไม่ควรคัดลอก DLL จากเครื่องอื่นหรือฝังใน Installer โดยเดา. Hosted Runner ไม่มี NVIDIA driver จึงไม่สามารถใช้ warning นี้ตัดสินว่าเครื่องร้านขาด DLL.
- การจัดประเภท `tbb12.dll`: Build log ยืนยันว่า `numba` ถูกติดตั้งเป็น dependency ของ `facexlib==0.3.0`; ไม่พบการติดตั้ง TBB runtime ใน build requirements. Numba ระบุว่า TBB เป็น threading layer ทางเลือก, มี `workqueue` เป็น fallback ที่รับประกัน และ default discovery ทนต่อ library ที่หายไป. จึงยังไม่ bundle TBB; ต้องตรวจ Numba/face path จริงบนเครื่องร้านหากพบ runtime error.
- **CUDA driver compatibility blocker ที่ต้องตรวจบนเครื่องร้าน:** Candidate ใช้ `torch==2.11.0+cu128` และ `torchvision==0.26.0+cu128`. Diagnostic ใน `tools/v211_shop_gpu_diagnostic.py` มี floor Windows CUDA 12.x minor compatibility **528.33** และ CUDA 12.8 GA **570.65**; regression test ครอบคลุม driver `451.67` ว่าอยู่ต่ำกว่า floor. ข้อมูลเครื่องร้านล่าสุดที่บันทึกไว้ 5 พ.ย. 2569 คือ GTX 1660 Ti / driver **451.67** / nvidia-smi CUDA **11.0**. หากยังใช้ driver นี้ PyTorch CUDA 12.8 จะไม่อยู่ในช่วง compatibility; V2 core อาจเลือก DirectML/CPU แทน CUDA. นี่ไม่ใช่ข้อสรุปว่า NCNN/Vulkan engines ทั้งสี่ใช้ไม่ได้ เพราะ diagnostic แยก CUDA driver compatibility ออกจาก Vulkan eligibility.
- ก่อนรับรอง Candidate บนเครื่องร้าน ต้องตรวจ driver ปัจจุบันด้วย `nvidia-smi`, ยืนยัน `torch.cuda.is_available()`/device จริงแยกจาก Vulkan inventory, แล้วจึงทำ native PID-to-adapter evidence. หาก driver ยังเป็น 451.67 ให้แก้ driver compatibility gate ก่อนอ้างว่า V2 PyTorch core ใช้ CUDA ได้; ห้าม bundle `nvcuda.dll` หรือเปลี่ยน Torch runtime โดยไม่มี compatibility test.
- ไม่มีการเรียก self-hosted Shop GPU Evidence ในรอบนี้ เพราะไม่มี consent marker/การอนุมัติเครื่องร้าน. ใช้เฉพาะ synthetic PNG/JSON evidence ใน CI; ไม่มีภาพลูกค้าหรือ model weights ใน artifact.
- PR #18 vs PR #20 protected face/GFPGAN files ยัง byte-identical **5/5**: `face_protection.py`, `large_faces.py`, `v211_face_contract.py`, `test_v211_face_contract.py`, `face_module/__init__.py`. Optional HAT Assist route ยังคงเป็น compatibility difference แยกต่างหาก.
- ไม่แก้ V1/V2 Stable, ไม่เขียนทับ accepted V2, ไม่ merge/release และไม่อ้างคุณภาพเหนือ V2. Candidate #681 เป็น Frozen Package/provenance pass เท่านั้น.

## 13 พฤศจิกายน 2569 21:41 ICT — Exact PR HEAD e0eace2 / Windows Candidate #714

ขอบเขตยังคงจำกัดเฉพาะ Draft PR #20 / `work/v211-four-engine-v2-bridge-20261103`; PR #18 ใช้ตรวจรักษา V2/GFPGAN เท่านั้น ไม่มีการแก้ V1 หรือ V2 Stable, ไม่มี Merge/Release และไม่มีการรับรองคุณภาพเหนือ V2

### Source identity และการตรวจ diff

- PR #20 HEAD: `e0eace2c5e31fd98adfadf70a5e879ed088ff585`; base และ PR #18 HEAD: `288dd8501c230a118d9a7e60d2522a2cc7411bcc`.
- Git compare: **800 ahead / 0 behind**, **71 changed files**. Candidate #714 ผูกกับ HEAD นี้โดยตรงจาก artifact metadata (`head_sha=e0eace2...`).
- เทียบจาก Candidate #644 source `f74da870` ถึง HEAD นี้มี 49 commits / 14 changed paths เพิ่มเติม รวมการแยก PyInstaller hidden-import graph สำหรับ V2.1.1, workspace guard สำหรับ build แบบทดลอง, CUDA-driver diagnostic แบบ read-only และ regression tests; Candidate #714 เป็น Candidate ที่ใหม่กว่า #644 และสร้างจาก source ปัจจุบัน.
- Audit รายการ 71 paths ไม่พบ .exe, .dll, ZIP/archive, model weights หรือ path ของ V1.

### Windows Candidate #714 — SUCCESS (2/2 jobs)

[GitHub Actions #714](https://github.com/niyomse-collab/niyom/actions/runs/43409506477)

- `bridge-tests`: syntax, V2-output preservation/four-engine coordination, privacy, model hashes และ official provisioning contracts ผ่าน.
- `windows-v2-candidate`: frozen build, V2 import smoke, packaged provisioning `--check-only` แบบไม่ดาวน์โหลด/ไม่เขียนไฟล์, isolated consented cache-cleanup, diagnostic `--help`, PowerShell provenance verifier, BUILD_PROOF/source SHA, installer-slice SHA256 และ artifact upload ผ่าน.
- Artifact ID `14030826269`; ขนาด **2,584,539,260 bytes**; ZIP SHA256 `7ad69afa81fd5c34fcfe8f287fddf592af467d29f45413fad9d729d104b662e4`.
- [ดาวน์โหลด Experimental Candidate #714](https://github.com/niyomse-collab/niyom/actions/runs/43409506477/artifacts/14030826269); หมดอายุ **20 พ.ย. 2569 18:00:41 ICT**.
- นี่คือ Frozen-package/build-provenance pass ไม่ใช่การติดตั้งแบบ interactive/uninstall บนเครื่องร้าน และไม่ใช่ GPU/quality acceptance.

### Independent Core #1275

[GitHub Actions #1275](https://github.com/niyomse-collab/niyom/actions/runs/43409506571)

- Windows และ Ubuntu: **SUCCESS** ทั้งคู่.
- `pytest` และ `compileall` ผ่านตาม Job Steps ของ exact PR HEAD.

### Official Archive Audit #154

[GitHub Actions #154](https://github.com/niyomse-collab/niyom/actions/runs/43409506460)

- ดาวน์โหลด ZIP ทางการทั้งสี่, ตรวจ SHA256 และ safe archive structure, แล้ว provision แบบ transactional ลง ephemeral QA directory; ไม่ commit archive, executable หรือ weights.
- Audit ยังคงไม่อนุมัติ redistribution; Real-ESRGAN และ Real-CUGAN ใช้ recorded CI SHA256 pins ไม่ใช่ publisher-published digest. การผ่าน archive/provisioning ไม่ใช่การรับรองสิทธิ์ redistributing model weights.

### Native CLI Smoke #196 — อ่าน JSON Artifact แล้ว; diagnostic only

[GitHub Actions #196](https://github.com/niyomse-collab/niyom/actions/runs/43409506333) · [JSON evidence artifact](https://github.com/niyomse-collab/niyom/actions/runs/43409506333/artifacts/14029295757)

- Synthetic RGB และ RGBA/ICC/300-DPI: Real-CUGAN และ Anime4KCPP native process จบด้วย exit code 0 และสร้าง output 2x ที่ผ่าน size/mode/ICC/DPI checks; RGBA alpha ตรงกับ source.
- Real-ESRGAN: `vkCreateInstance failed -9`, exit `0xFFFFFFFF`.
- Waifu2x: `vkCreateInstance failed -9`, exit `0xC0000005` (Access Violation).
- Hosted Runner ไม่มี NVML; physical adapter verification **0/4**. ทั้งสองรายงานกำหนด `real_inference_verified=false`, `runtime_device_use_verified=false`, `quality_improvement_verified=false`.
- Workflow SUCCESS หมายถึงจำแนก hosted Vulkan limitation และเก็บ JSON ได้ ไม่ใช่การทดสอบ GPU 4/4 หรือคุณภาพบน GTX 1660 Ti.

### CUDA driver hint และ build isolation ที่เพิ่มหลัง Candidate #644

- `signprint_ai/v211_cuda_compat.py` อ่าน NVIDIA-SMI แบบ read-only และแสดงคำเตือน PyTorch CUDA 12.8 แบบ non-blocking; ไม่ initialize Torch CUDA, ไม่ดาวน์โหลด driver และไม่ใช้ CUDA hint ไปปิด NCNN/Vulkan engines.
- เกณฑ์ที่โค้ดบันทึกจาก NVIDIA CUDA 12.8 Release Notes: Windows CUDA 12.x minor-compatibility floor **528.33** และ CUDA 12.8 GA toolkit driver **570.65** ([NVIDIA CUDA 12.8 Release Notes](https://docs.nvidia.com/cuda/archive/12.8.0/cuda-toolkit-release-notes/index.html)).
- ข้อมูลเครื่องร้านล่าสุดที่เคยได้รับเมื่อ 5 พ.ย. คือ Driver **451.67**; เป็นข้อมูลย้อนหลัง ไม่ใช่การอ่าน Driver ปัจจุบัน. ต้องตรวจ `nvidia-smi` และ Torch runtime บนเครื่องร้านอีกครั้งก่อนอ้างว่า V2 PyTorch core ใช้ CUDA 12.8 ได้. ประเด็นนี้แยกจาก Vulkan eligibility ของ native engines.
- `build_windows.ps1` และ `NiyomsilV2ArmCore.spec` แยก V2.1.1 graph/installer path ด้วย build metadata; regression tests ตรวจว่า V1 และ stable-V2 ใช้ legacy hidden-import path และไม่รับ V2.1.1 modules. Workspace guard ปฏิเสธการลบ output ที่ไม่มี V2.1.1 provenance ที่ตรวจสอบได้.

### สิ่งที่ยังเป็น release blockers

- ยังไม่มี self-hosted shop GPU run: ไม่มี affirmative shop-GPU consent marker; ไม่ schedule เครื่องร้านโดยอัตโนมัติ.
- ยังไม่มี native physical-adapter proof 4/4, peak VRAM, hard per-process 6 GB cap หรือ stress test บน GTX 1660 Ti.
- >18 MP auxiliary route รองรับเฉพาะ PNG RGB/RGBA แบบ disk-backed; streamed ceiling 1,000 MP / row buffer 64 MiB / disk preflight. JPEG/TIFF/CMYK/PDF/PSD ขนาดใหญ่ยัง V2-only.
- Large target 4x/8x ยังเป็นหนึ่ง native 2x pass จาก half-target seed; ไม่ใช่ native 4x/8x หรือ multi-pass. Cancel ระหว่าง process/tile มี contract tests แต่ยังไม่มี shop stress evidence.
- ยังไม่มี visual A/B ที่เจ้าของร้านรับรองสำหรับใบหน้า, สัตว์, วัตถุ, กรอบ, ลายไทย, ไทย/อังกฤษ/จีน, flat color, gradient, RGBA และไฟล์พิมพ์ Photoshop/MainTop/RIP.
- PR #18 เทียบ PR #20: protected GFPGAN/face-contract Blob SHA ตรงกัน **5/5**. Optional HAT Assist route ยังคง disabled ใน PR #20 และเป็น compatibility difference แยกที่ต้อง review ก่อน merge.
- V2 remains accepted Master; no quality-superiority claim. PR #20 remains OPEN/DRAFT/UNMERGED; no V1/V2 Stable changes, no merge and no release.


## 13 พฤศจิกายน 2569 22:53 ICT — Exact-head Windows Candidate #715 และ Workspace Guard correction

- PR #20 HEAD ที่ Candidate #715 ตรวจคือ `d3b740141f866cb2659da99f6ff249efc7903ea5`; base/PR #18 HEAD ยังคง `288dd8501c230a118d9a7e60d2522a2cc7411bcc`. Compare ยังคง **801 ahead / 0 behind**, 71 changed files.
- Windows Candidate #715 [Actions](https://github.com/niyomse-collab/niyom/actions/runs/43445795010) เสร็จ **SUCCESS 2/2 jobs**: `bridge-tests` และ `windows-v2-candidate`. Build ใช้ source SHA d3b7401 โดยตรง.
- Frozen candidate ผ่าน V2 import smoke, packaged provisioning `--check-only` แบบไม่ดาวน์โหลด/ไม่เขียนไฟล์, isolated consented cache cleanup, diagnostic `--help`, PowerShell provenance parse, BUILD_PROOF/source SHA, installer-slice SHA256 และ artifact upload. นี่เป็น package/provenance pass เท่านั้น ไม่ใช่ shop install หรือ GPU acceptance.
- Artifact ID `14050436108`; size **2,584,629,755 bytes**; ZIP SHA256 `fa59e41c0488b8cb8a5c413925be109998dab4068fbbb6fb17522744a850fdaa`; installer SHA256 `7ce2793d10a87406864faed59777f05c818d8f859d3f10f51423ad9a5cd69f73`. [Experimental Candidate #715](https://github.com/niyomse-collab/niyom/actions/runs/43445795010/artifacts/14050436108); expires **20 พ.ย. 2569 22:14 ICT**.
- Independent Core #1277 [Actions](https://github.com/niyomse-collab/niyom/actions/runs/43445793138): Windows **975 passed / 1 skipped**, Ubuntu **973 passed / 3 skipped**; pytest and compileall passed on both.
- Official Archive Audit #155 [Actions](https://github.com/niyomse-collab/niyom/actions/runs/43445793254): official four ZIPs were hash-checked and transactionally provisioned into ephemeral QA storage; manifest lists all four. Real-ESRGAN and Real-CUGAN use observed CI SHA256 pins (no publisher release digest); Waifu2x and Anime4KCPP have published digest verification. Redistribution approval and model-weight/license certification remain **false**; binaries/weights are not included in the installer.
- Native CLI Smoke #197 [Actions](https://github.com/niyomse-collab/niyom/actions/runs/43445793169), JSON artifact `14048360095`: Real-CUGAN and Anime4KCPP native processes exited 0 and produced validated synthetic 2x RGB/RGBA outputs; RGBA alpha, ICC and 300-DPI metadata passed. Real-ESRGAN and Waifu2x remain blocked by hosted-runner `vkCreateInstance failed -9`; Waifu2x also exited `0xC0000005`. NVML was unavailable and physical adapter verification remains **0/4**; `real_inference_verified=false` and `quality_improvement_verified=false`. Diagnostic SUCCESS is not four-engine GPU acceptance.
- A source audit found a small build-guard mismatch: `build_windows.ps1` and the PyInstaller spec accept both `2.1.1` and `2.1.1-beta.N`, while `tools/v211_build_workspace_guard.py` recognized only beta versions. A clean build was safe, but a previously verified non-beta 2.1.1 workspace was unnecessarily refused. This update aligns the guard regex and adds real temporary-workspace regressions for stable and beta candidates, while retaining refusal for accepted V2/other versions. The change is limited to PR #20.
- The guard/test update creates a new source HEAD after Candidate #715; therefore #715 is evidence for the previous d3b7401 source only. A fresh Candidate and Core run on the new HEAD are required before treating the fix as verified.
- PR #18 protected GFPGAN/face Blob SHA remains identical **5/5** against PR #20. Optional HAT Assist routing remains a separate compatibility difference for review.
- No V1/V2 Stable changes, no merge/release, no customer images or binaries/weights committed, and no claim of quality superiority over V2. V2 remains the accepted master.


## 14 พฤศจิกายน 2569 00:10 ICT — Exact-head Candidate #719

- PR #20 HEAD: `00f837f94d451de6a91016ca2ca6ac67b184772f` on `work/v211-four-engine-v2-bridge-20261103`; PR #20 remains OPEN/DRAFT/UNMERGED and targets PR #18 head `288dd8501c230a118d9a7e60d2522a2cc7411bcc`.
- Windows Candidate #719 [Actions](https://github.com/niyomse-collab/niyom/actions/runs/43457705443) completed SUCCESS **2/2 jobs**: `bridge-tests` and `windows-v2-candidate`. Frozen V2 imports, packaged provisioning `--check-only` without network/write, isolated consented cache cleanup, packaged diagnostic `--help`, provenance PowerShell parse, exact BUILD_PROOF/source SHA, every installer-slice SHA256 and experimental artifact upload passed.
- Artifact ID `14056104466`; size **2,584,453,146 bytes**; ZIP SHA256 `78150f3a6d232207c23a119d9e6d5dfe09cc918e8a5d4603924ac790da9fd7c2`; installer SHA256 `226ddd81d9a112838f05beabf728abcfad22aef822ac544060591aa8d7f65259`. [Download Candidate #719](https://github.com/niyomse-collab/niyom/actions/runs/43457705443/artifacts/14056104466); expires **20 พ.ย. 2569 23:30 ICT**.
- Independent Core #1281 [Actions](https://github.com/niyomse-collab/niyom/actions/runs/43457705513): Windows **979 passed / 1 skipped**; Ubuntu **977 passed / 3 skipped**; compileall passed on both.
- Official Archive Audit #157 [Actions](https://github.com/niyomse-collab/niyom/actions/runs/43457705451): all four official archives were hash-checked, safely audited and transactionally provisioned in ephemeral QA storage. Real-ESRGAN and Real-CUGAN use recorded CI SHA256 pins because publisher digests are unavailable; Waifu2x and Anime4KCPP publisher digests were verified. Model-weight/license certification and redistribution approval remain **false**; native binaries/weights remain excluded from the installer.
- Native CLI Smoke #199 [Actions](https://github.com/niyomse-collab/niyom/actions/runs/43457705526), JSON artifact [14053119786](https://github.com/niyomse-collab/niyom/actions/runs/43457705526/artifacts/14053119786): synthetic RGB and RGBA/ICC/300-DPI only. Real-CUGAN and Anime4KCPP produced validated 2x outputs. Real-ESRGAN and Waifu2x were blocked by hosted-runner `vkCreateInstance failed -9` (Waifu2x also `0xC0000005`). NVML unavailable; physical adapter verification **0/4**; `real_inference_verified=false` and `quality_improvement_verified=false`. Diagnostic workflow SUCCESS is not four-engine GPU acceptance.
- PyInstaller emitted non-fatal missing-module/library warnings for `pycparser.lextab/yacctab`, `scipy.special._cdflib`, driver-provided `nvcuda.dll` and optional `tbb12.dll`; do not bundle driver/optional DLLs by guess. Verify runtime relevance on the shop PC.
- PR #18 versus PR #20 protected GFPGAN/face-contract Blob SHA remains identical **5/5**. The optional HAT Assist route remains separately disabled in PR #20 and requires compatibility review; it was not silently restored.
- No affirmative shop-GPU consent marker was supplied, so no self-hosted shop runner was scheduled. No V1/V2 Stable changes, no customer images or engine binaries/weights committed, no merge/release, and no quality-superiority claim. V2 remains the accepted master.

---

## 14 พฤศจิกายน 2569 — Large TIFF/BigTIFF และ Frozen Import Audit

### การเปลี่ยนแปลงใน PR #20

- `signprint_ai/v211_large_image_bridge.py` เพิ่มการตรวจ TIFF/BigTIFF ด้วย `tifffile.TiffFile` และนับจำนวนหน้า ก่อนเปิด raster หรือเริ่ม GPU; ไฟล์เสียหรือ TIFF หลายหน้าถูกปฏิเสธแบบ fail-closed
- `signprint_ai/v211_four_engine_bridge.py` อนุญาต large-job source และ accepted V2 raster เป็น PNG หรือ single-page RGB/RGBA 8-bit TIFF/BigTIFF; libvips สร้าง private PNG seed/reference ให้ Native Engines และ QA sidecar ยังคงเป็น PNG แยกไฟล์
- JPEG/WebP, multipage TIFF, CMYK และ bit depth ที่ไม่รองรับยังคงใช้ V2-only; ไฟล์ V2 เดิมไม่ถูกเขียนทับ
- พบช่องว่างใน Frozen Build: TIFF reader ถูก import แบบ dynamic; เพิ่ม `tifffile` ใน V2.1.1-only `hiddenimports`, เพิ่ม `tifffile` ใน `NIYOMSIL_IMPORT_SMOKE` และเพิ่ม test ป้องกันไม่ให้ hidden import นี้ไหลไป V1/V2 Stable
- การเปลี่ยนแปลงทั้งหมดอยู่ใน Draft PR #20 สาขา `work/v211-four-engine-v2-bridge-20261103`; ไม่มีการแก้ V1 หรือ V2 Stable

### หลักฐานทดสอบบน HEAD `251c65136168e24fb843fbc67994c36a29571d71`

- Windows Candidate #735: bridge test 333 passed และ privacy/provision/hash test 63 passed; รวม compileall ผ่าน
- Core Regression #1298: Windows 986 passed / 1 skipped; Ubuntu 984 passed / 3 skipped; compileall ผ่านทั้งสองระบบ
- เพิ่ม synthetic 24MP BigTIFF test (6001×4001 baseline, 3000×1000 source): ใช้ libvips disk-backed path, ห้าม Pillow full-raster decode, ตรวจ ICC/DPI และ SHA256 ของ accepted V2 TIFF ก่อน/หลังให้ตรงกัน
- TIFF/BigTIFF matrix ยังมี test สำหรับ classic TIFF, BigTIFF, PNG↔TIFF source/V2 combinations และการปฏิเสธ multipage TIFF ก่อน GPU
- ข้อจำกัดหลักฐาน: 24MP BigTIFF test ยืนยัน seed preparation/QA crop เท่านั้น ไม่ได้ยืนยัน Native Engine inference จริงบน GPU หรือคุณภาพภาพ

### Workflow ล่าสุด

- [Windows Candidate #735](https://github.com/niyomse-collab/niyom/actions/runs/43496718532) — bridge tests ผ่าน; Windows frozen build ยังอยู่ระหว่างขั้น Build V2-based experimental candidate ณ เวลาบันทึกนี้; ยังไม่มี Artifact ให้รับรอง
- [Independent Core #1298](https://github.com/niyomse-collab/niyom/actions/runs/43496718750) — SUCCESS
- [Official Archive Audit #164](https://github.com/niyomse-collab/niyom/actions/runs/43496718704) — SUCCESS; ตรวจ official source/license/SHA256 ของทั้งสี่แพ็กเกจ
- [Native CLI Smoke #211](https://github.com/niyomse-collab/niyom/actions/runs/43496718489) — Diagnostic workflow SUCCESS แต่มี Native process ที่ทำงานได้เพียง 2/4 บน Hosted Runner; NVML/Physical GPU verification 0/4; จึงไม่ใช่หลักฐานว่าเครื่องร้านใช้ GPU จริง
- Candidate #729 และ #733 ถูก supersede/cancel หลังพบและแก้ช่องว่าง Frozen `tifffile` import และขอบเขต test assertion; ไม่ใช่ test failure ของ Candidate #735

### ข้อจำกัดที่ยังเปิดอยู่

- Native CLI #211: Real-CUGAN และ Anime4KCPP สร้าง output ได้; Real-ESRGAN และ Waifu2x ล้มบน Hosted Runner ด้วย Vulkan `vkCreateInstance failed -9` (Waifu2x มี `0xC0000005` เพิ่มเติม); ผลนี้ไม่หักล้างผลราย Engine ที่ผู้ใช้รายงานบน Windows 11 GTX 1660 Ti แต่ยังไม่มี integrated 4-engine run จากเครื่องร้าน
- GPU policy ปัจจุบันกำหนด free VRAM ก่อนเริ่มอย่างน้อย 2048 MiB และ runtime reserve 512 MiB; ยังไม่ใช่ผลวัด peak VRAM หรือ hard-cap stress test บนการ์ด 6 GB
- ยังไม่มี A/B visual QA ที่รับรองว่า V2.1.1 ดีกว่า V2; `quality_certified=false` และ V2 ยังคงเป็น Master
- Archive audit ตรวจ source/license/SHA256 ได้ แต่ `license_redistribution_approved=false`; จึงไม่ bundle native binaries หรือ model weights ใน installer และยังไม่ commit binaries/weights/ภาพลูกค้า

### การคงสภาพ PR และ GFPGAN

- PR #20 ยังคง Open/Draft, HEAD code/test `251c65136168e24fb843fbc67994c36a29571d71`, base `288dd8501c230a118d9a7e60d2522a2cc7411bcc`
- PR #18 ยังคง Open/Draft ที่ base เดิม; protected GFPGAN/face-contract files ตรงกัน 5/5 Blob SHA ระหว่าง PR #18 และ #20; ไม่มี Review Thread ค้าง
- ห้าม merge/release จนกว่าจะมีผล GPU QA จริงและผู้ใช้อนุมัติ


## 14 พฤศจิกายน 2569 — เพิ่ม UI ปกป้องข้อความและเอฟเฟกต์แบบเลือกพื้นที่ (ROI)

- เพิ่ม `signprint_ai/effect_region_selection.py`: หน้าต่างเลือกพื้นที่แบบลากกรอบหลายจุดบนภาพตัวอย่าง รองรับย้อนกรอบล่าสุด/ล้างทั้งหมด/ยกเลิก พิกัดถูกเก็บเป็น normalized ROI อ้างอิงภาพต้นฉบับที่ปรับ EXIF orientation แล้ว
- เชื่อมปุ่ม `เลือกพื้นที่ปกป้องข้อความเอฟเฟกต์` ใน `app_v2.py` กับ per-file ROI map; ตอนเข้าคิวจะส่ง `v211_protected_effect_regions` ให้ Adapter และรวม ROI map ใน completion signature เพื่อบังคับประมวลผลใหม่เมื่อแก้พื้นที่
- Fusion ใช้ ROI เป็น protection mask เพื่อคงพิกเซลจาก V2 ในพื้นที่เลือกเท่านั้น ไม่ใช้ OCR ไม่พิมพ์ทับ ไม่วาดข้อความใหม่ และไม่เปลี่ยน V2 master
- เพิ่ม `tests/test_v211_effect_region_selection.py` ครอบคลุมการ normalize ทิศลากกลับด้าน, clamp ขอบภาพ, drag ขนาดเล็ก และค่าพิกัดผิดรูปแบบ
- Core run #1329 พบ 5 failures จาก test harness เดิมที่สร้าง `SimpleNamespace` โดยไม่มี helper ใหม่ `_effect_region_signature`; แก้ compatibility ใน commit `3c4bcdc9` ให้ fallback เป็น signature ว่างสำหรับ test doubles/legacy callers ขณะที่ App จริงยังใช้ per-file ROI signature
- Candidate #762: bridge-tests ผ่าน; Windows frozen candidate ถูกยกเลิกโดย branch concurrency หลังมี commit ใหม่ จึงไม่ใช่ package acceptance ของ HEAD ล่าสุด
- Archive audit #178 ผ่าน; Native CLI #226 เป็น diagnostic เท่านั้น และยังคงข้อจำกัด Vulkan/NVML ของ Hosted Runner
- Code/UI HEAD หลังแก้ compatibility และปุ่ม Enter ใน dialog: `e7cb7a436a97ee19675bdf8ad739e78722a6ea76`. ต้องรัน Core + Candidate ใหม่บน HEAD นี้ก่อนนับว่าการเปลี่ยน UI ผ่าน CI
- PR #18 protected GFPGAN/face blobs ยังคงต้องตรงกัน 5/5; ยังไม่ Merge/Release และไม่อ้างว่า quality ดีกว่า V2


## 14 พฤศจิกายน 2569 10:09 ICT — Exact code/test HEAD 13c1b3fa และ Windows Candidate #770

### ขอบเขตและการเปลี่ยนแปลงล่าสุด
- PR #20 HEAD ณ เวลาตรวจ: `13c1b3fa64e7d28c51e0f7d5e5733f7a0abe1c49`, branch `work/v211-four-engine-v2-bridge-20261103`, base `288dd8501c230a118d9a7e60d2522a2cc7411bcc`.
- เปรียบเทียบจาก documentation checkpoint `2ae7d34b97ddea8a2e39097530b8f118d8bd92cf`: 31 commits / 15 changed paths; มีการเชื่อม UI เลือก ROI ต่อไฟล์, queue snapshot, adapter routing, disk-backed large-image bridge และ frozen BigTIFF/libvips smoke
- เพิ่ม `signprint_ai/effect_region_selection.py` และ `tests/test_v211_effect_region_selection.py`; App import selector โดยตรง และ `tests/test_v211_effect_roi_queue_integration.py` ตรวจว่า ROI ของแต่ละไฟล์ไม่ปะปนเมื่อ enqueue และถูกส่งถึง bridge หลัง accepted V2 ถูกบันทึกแล้ว
- ROI เป็น pixel-protection mask เท่านั้น ไม่ OCR/retype/redraw ตัวอักษร และไม่แก้ accepted V2 output

### Exact-head CI
- Windows Candidate #770: [GitHub Actions](https://github.com/niyomse-collab/niyom/actions/runs/43541855776) — **SUCCESS 2/2 jobs** บน source SHA `13c1b3f`: bridge-tests และ windows-v2-candidate
- Bridge tests: **348 passed**; privacy/provisioning/manifest/hash suite: **63 passed**
- Independent Core #1338: [GitHub Actions](https://github.com/niyomse-collab/niyom/actions/runs/43541855782) — Windows **1005 passed / 1 skipped**, Ubuntu **1003 passed / 3 skipped**; compileall ผ่านทั้งสองระบบ
- Frozen package smoke: imports ผ่าน; packaged four-engine provisioning `--check-only` ผ่านโดยไม่ดาวน์โหลด/เขียน cache; packaged diagnostic `--help` ผ่าน
- Packaged TIFF/BigTIFF smoke ผ่าน: ตรวจ single-page BigTIFF, streamed libvips seed/QA path, ปฏิเสธ multipage TIFF, ICC/DPI, odd-size crop และยืนยัน SHA256 ของ accepted V2 ไม่เปลี่ยน; ใช้ synthetic files และรายงาน `customer_files_accessed=false`. การทดสอบนี้ไม่ใช่ native GPU inference หรือ visual-quality acceptance
- Artifact ID `14093009417`, size **2,584,650,772 bytes**, ZIP SHA256 `6adbb77bf2af1df0889638ad8d192cfdcb1c125fb635e1fd0c53f34f6316d77d`; [Experimental Candidate #770](https://github.com/niyomse-collab/niyom/actions/runs/43541855776/artifacts/14093009417), expires **21 พ.ย. 2569 09:13 ICT**
- Installer SHA256 จาก Windows build log: `570a1ec134015dc92e6991b5a071a19f124ce917008389ebd20b12ad7dcf0ac5`
- PyInstaller มี non-fatal warnings: `pycparser.lextab/yacctab`, `scipy.special._cdflib`, driver-provided `nvcuda.dll`, และ optional `tbb12.dll` ของ Numba. Frozen import smoke ผ่าน แต่ runtime relevance ยังต้องตรวจบนเครื่องร้าน; ไม่ bundle driver DLL หรือเดา dependency เพิ่ม

### Official assets และ Native CLI
- Official Archive Audit #182: [GitHub Actions](https://github.com/niyomse-collab/niyom/actions/runs/43541855947) — ดาวน์โหลด official Windows archives ทั้งสี่, ตรวจ SHA256, safe audit และ transactional provisioning ไปยัง ephemeral QA directory ผ่าน; manifest มี `real_esrgan`, `waifu2x`, `real_cugan`, `anime4k` ครบ
- Archive pins: Real-ESRGAN `abc02804e17982a3be33675e4d471e91ea374e65b70167abc09e31acb412802d` (observed CI pin, publisher digest unavailable); Waifu2x `7425be94b94e4c8f37a1e433ac0e0100c43790e2c37418f4b65d8235adfbdc87` (published digest); Real-CUGAN `c6e08d46c11704b1e3a1ada9ddd591cb5005f52f132136c8633ba25def400e01` (observed CI pin, publisher digest unavailable); Anime4KCPP `82897b0f03ddb88ab3d1affb745baf99506cfe3ceffaeaf73796c6dea4077f19` (published digest)
- `model_weights_and_license_certified=false` และ `license_redistribution_approved=false`; native binaries/weights ยังคงไม่อยู่ใน installer/repository
- Native CLI Smoke #230: [GitHub Actions](https://github.com/niyomse-collab/niyom/actions/runs/43541855863) — Real-CUGAN และ Anime4KCPP สร้าง synthetic 2x output ได้; Real-ESRGAN และ Waifu2x ติด hosted-runner Vulkan `vkCreateInstance failed -9` (Waifu2x มี `0xC0000005`); NVML library not found, physical adapter verification **0/4**, `real_inference_verified=false`, `quality_improvement_verified=false`. Diagnostic workflow SUCCESS ไม่ใช่การรับรอง GPU/คุณภาพ

### Protected V2/GFPGAN และสถานะปล่อยงาน
- เทียบ Blob SHA ของ protected files ระหว่าง PR #18 HEAD `288dd850` กับ PR #20 HEAD `13c1b3f`: `face_protection.py`, `face_module/__init__.py`, `large_faces.py`, `v211_face_contract.py`, `test_v211_face_contract.py` ตรงกัน **5/5**
- PR #20 และ PR #18 ยังคง OPEN/DRAFT/UNMERGED; V1/V2 Stable ไม่เปลี่ยน; ไม่มี customer images, native binaries หรือ model weights commit
- Candidate #770 เป็น frozen packaging/provenance + synthetic smoke pass เท่านั้น ไม่รับรอง interactive install/uninstall, GPU inference 4/4 บน GTX 1660 Ti, peak VRAM 6 GB, A/B ภาพจริง, Photoshop/MainTop/RIP หรือคุณภาพงานพิมพ์
- `real_inference_verified=false`, `quality_certified=false`; V2 ยังคงเป็น accepted master; ห้าม merge/release จนกว่าผู้ใช้ตรวจ GPU/visual/print evidence และอนุมัติ


## 14 พฤศจิกายน 2569 12:14 ICT — อนุญาต Synthetic-only shop GPU evidence สำหรับ Candidate #771

- ขอบเขตคำสั่ง: ทดสอบ native CLI ทั้งสี่และ end-to-end bridge บน Windows 11 shop GPU ด้วยภาพสังเคราะห์ RGB/RGBA เท่านั้น; ไม่อ่านภาพลูกค้า, ไม่อัปโหลดภาพ, ไม่แก้ V2 output และเก็บเฉพาะ JSON evidence
- Candidate source ที่อนุญาต: `c1cb569935ebbd165b49c3f1c08855d7c713d6a0` (Candidate #771); workflow ต้องตรวจ `BUILD_PROOF.txt` ของ EXE ที่ติดตั้งให้ตรง SHA นี้ก่อนรัน
- การทดสอบต้องผ่าน NVIDIA-SMI/Vulkan inventory, unique GTX 1660 Ti binding, per-engine VRAM preflight และ live PID-to-adapter telemetry สำหรับทั้ง 4 engine; ถ้าเงื่อนไขใดไม่ผ่านให้ fail closed และคง V2 เป็น output ที่ยอมรับ
- Workflow ที่ใช้: [V2.1.1 shop GPU evidence gate](https://github.com/niyomse-collab/niyom/actions/workflows/v211-four-engine-manual-evidence.yml); evidence job ทำงานได้เฉพาะ self-hosted Windows runner label `niyom-shop-gpu`. หาก runner ไม่พร้อม จะไม่มี hosted-runner fallback และไม่ถือว่าได้ทดสอบ GPU จริง
- ผล synthetic GPU acceptance จะยืนยันได้เฉพาะ native execution / adapter / metadata / bridge contract; ไม่ใช่ visual-quality หรือ print certification. `quality_improvement_verified=false`, `visual_quality_certified=false`, `print_quality_certified=false` ต้องคงไว้
- การแก้ไข commit นี้เป็นเอกสารเท่านั้น; ไม่มี Source/Test/Spec/Installer/Workflow code เปลี่ยน, ไม่แตะ V1/V2 Stable, ไม่ Merge/Release

---

## 14 พฤศจิกายน 2569 20:19 ICT — Exact-head verification: PR #20 HEAD d678eef / Windows Candidate #813

### ขอบเขตและการแก้ไข
- PR #20 HEAD ที่ตรวจ: `d678eef845bb44bf049de9ee79f2b0dd8a28bfca`, branch `work/v211-four-engine-v2-bridge-20261103`, base `288dd8501c230a118d9a7e60d2522a2cc7411bcc`.
- พบว่า `tools/v211_four_engine_run.py::_safe_execution_record` เดิม whitelist ค่าเพดาน VRAM แบบ canonical `runtime_vram_max_allowed_device_used_mib` ไม่ครบ ทำให้รายงาน Four-Engine อาจทำค่าขอบเขตที่ QA ต้องใช้หล่นหาย
- แก้ใน commit `959efff4e9b2b7fbc22d5550b4445528eb1e1b63` ให้เก็บทั้ง canonical field และ legacy alias โดยยังคง whitelist-only และไม่คัดลอก private path/argv/raw process output
- เพิ่ม regression ใน commit `d678eef845bb44bf049de9ee79f2b0dd8a28bfca`: `test_safe_execution_record_keeps_canonical_vram_ceiling_field`; ตรวจ canonical + legacy field และยืนยันว่า private path ไม่ถูกคัดลอก

### Exact-head CI
- Windows Candidate **#813**: [Actions](https://github.com/niyomse-collab/niyom/actions/runs/43591999969) — **SUCCESS 2/2 jobs** จาก exact source SHA `d678eef`: `bridge-tests` และ `windows-v2-candidate`.
- Bridge/Fusion/coordination suite: **358 passed**; privacy/provisioning/hash suite: **63 passed**.
- Frozen package checks ผ่าน: V2 imports, single-page BigTIFF + streamed libvips QA path, packaged four-engine provisioning `--check-only` โดยไม่ดาวน์โหลด, consented cache cleanup บน synthetic data, packaged diagnostic `--help`, BUILD_PROOF exact source SHA, และ installer slice SHA256 verification.
- Installer SHA256 จาก Windows build log: `dfb297b9278d0dcc82cef33545fd063eb3f9aac0021e353bc586e33e7eb0bac6`.
- Experimental artifact ID `14113796471`; size **2,584,555,187 bytes**; artifact ZIP SHA256 `7b987465dfe6e437265c73aad940cbf91125abd4a6321982c7f3802236aec4fc`; expires **21 พ.ย. 2569 19:15 ICT**. [Download Candidate #813](https://github.com/niyomse-collab/niyom/actions/runs/43591999969/artifacts/14113796471).
- Candidate #813 เป็น frozen package/provenance acceptance เท่านั้น ไม่ได้ยืนยัน interactive install/uninstall บนเครื่องร้าน, Vulkan adapter use, native GPU 4/4, peak VRAM หรือ print quality.

### Independent Core / Archive / Native CLI
- Independent Core **#1388**: [Actions](https://github.com/niyomse-collab/niyom/actions/runs/43591999925) — Windows **1015 passed / 1 skipped**; Ubuntu **1013 passed / 3 skipped**; compileall ผ่านทั้งสองระบบ.
- Official Archive Audit **#203**: [Actions](https://github.com/niyomse-collab/niyom/actions/runs/43591999959) — ดาวน์โหลด official Windows archives ทั้งสี่, ตรวจ digest และ archive safety, provision ลง ephemeral QA directory ผ่าน. Publisher digest มีสำหรับ Waifu2x/Anime4KCPP; Real-ESRGAN/Real-CUGAN ยังคงเป็น observed CI pins. Model-weight/license certification และ redistribution approval ยังไม่ผ่าน จึงไม่ bundle native binaries/weights.
- Native CLI Smoke **#264**: [Actions](https://github.com/niyomse-collab/niyom/actions/runs/43591999924), JSON artifact [14112711724](https://github.com/niyomse-collab/niyom/actions/runs/43591999924/artifacts/14112711724). บน synthetic RGB และ RGBA/ICC/300-DPI: Real-CUGAN และ Anime4KCPP สร้าง native 2x output ที่ผ่าน metadata/alpha validation; Real-ESRGAN และ Waifu2x ถูก block โดย hosted-runner Vulkan `vkCreateInstance failed -9` (Waifu2x เพิ่มเติม `0xC0000005`). NVML ไม่พบ, physical adapter verification **0/4**.
- Smoke #264 ระบุ `runtime_vram_guard_requested=false`, `runtime_vram_budget_passed=false`, `runtime_device_use_verified=false`; ดังนั้น run นี้ไม่ใช่หลักฐาน VRAM 6GB หรือ GPU acceptance แม้ diagnostic workflow จะจบ SUCCESS เพราะจัดประเภทข้อจำกัดของ Hosted Runner ได้ถูกต้อง.
- `real_inference_verified=false`, `quality_improvement_verified=false`; ไม่มี A/B ภาพจริงหรือ print certification.

### V2/GFPGAN protection และข้อจำกัดการทดสอบร้าน
- Protected files ระหว่าง PR #18 head `288dd8501c230a118d9a7e60d2522a2cc7411bcc` และ PR #20 HEAD `d678eef` ตรงกัน **5/5 Blob SHA**: `face_protection.py`, `large_faces.py`, `v211_face_contract.py`, `test_v211_face_contract.py`, `test_v211_large_face_audit.py`.
- Manual shop workflow มี consent gate และต้องตรวจ BUILD_PROOF ของ Candidate SHA ที่ได้รับอนุญาตตรงกัน; เอกสารก่อนหน้านี้อนุญาต synthetic-only shop GPU evidence สำหรับ Candidate #771 (`c1cb569`) เท่านั้น. Candidate #813 เป็น SHA ใหม่ จึง **ไม่ได้ trigger self-hosted shop GPU run** และไม่ถือว่ามีการอนุญาตติดตั้ง/ทดสอบ Candidate ใหม่นี้บนเครื่องร้าน.
- PR #20 และ PR #18 ยังคง OPEN/DRAFT/UNMERGED; ไม่มี V1/V2 Stable changes, merge/release, customer images หรือ native binaries/weights committed. V2 remains accepted master; quality certification remains false.


## 15 พฤศจิกายน 2569 04:46 ICT — Exact-head Candidate #820 completed; shop GPU evidence still waiting

### PR / source identity
- PR #20 remains OPEN / DRAFT / UNMERGED on `work/v211-four-engine-v2-bridge-20261103`, exact HEAD `644d91e7599ce874f04604339c6597718f465575`; PR #18 remains OPEN / DRAFT / UNMERGED at protected base/head `288dd8501c230a118d9a7e60d2522a2cc7411bcc`.
- Commit `644d91e` changes only `docs/V211_WINDOWS_REAL_FOUR_ENGINE_QA_TH.md` relative to `c60419d` (one file, 11 additions, 0 deletions). No runtime source, tests, spec, installer or workflow changed in that final commit.
- PR #20 currently has 75 changed paths; the changed-file list contains no executable, DLL, archive, model-weight, image, V1/V2 Stable or protected face/GFPGAN path.

### Exact-head CI and frozen Candidate #820
- Windows Candidate #820 [Actions](https://github.com/niyomse-collab/niyom/actions/runs/43640094902) completed SUCCESS, both jobs passed: `bridge-tests` and `windows-v2-candidate`.
- Bridge/Fusion/coordination suite: **359 passed**; privacy/provisioning/manifest/hash suite: **63 passed**.
- Frozen checks passed: V2 import smoke; single-page BigTIFF and streamed libvips path; packaged four-engine provisioning `--check-only` without download/write; isolated consented cache cleanup; packaged diagnostic `--help`; provenance verifier; exact BUILD_PROOF/source SHA; every installer slice SHA256; experimental artifact upload.
- Build log reports `accepted_v2_sha256_unchanged=true`.
- Installer SHA256: `d0ea974cd2d9ab03515440e608501e9d869910b526e1b9c26be0843b2be89eac`.
- Artifact ID `14133305275`; size **2,584,548,820 bytes**; artifact ZIP SHA256 `0e038f0fd40e7f62c051187e5cbed28b34364a5b6790d84a5ef18f3fe1772edd`; expires **22 พ.ย. 2569 04:26:59 ICT**. [Download Candidate #820](https://github.com/niyomse-collab/niyom/actions/runs/43640094902/artifacts/14133305275).
- Candidate #820 is a frozen package/provenance pass only. It does not certify interactive install/uninstall on the shop PC, Vulkan adapter binding, four-engine inference on GTX 1660 Ti, peak 6 GB VRAM, visual A/B, Photoshop/MainTop or print quality.

### Independent Core
- Core #1398 [Actions](https://github.com/niyomse-collab/niyom/actions/runs/43640095121): Windows **1,016 passed / 1 skipped**; Ubuntu **1,014 passed / 3 skipped**; pytest and compileall passed on both.

### Official archive audit #208
- [Actions #208](https://github.com/niyomse-collab/niyom/actions/runs/43640094856): all four official Windows archives downloaded, safely audited, hash-checked and provisioned transactionally into ephemeral QA storage; `all_archives_audited=true` and `all_archives_match_release_or_recorded_hash=true`.
- Real-ESRGAN v0.2.5.0 SHA256 `abc02804e17982a3be33675e4d471e91ea374e65b70167abc09e31acb412802d` and Real-CUGAN 20220728 SHA256 `c6e08d46c11704b1e3a1ada9ddd591cb5005f52f132136c8633ba25def400e01` remain observed CI pins because publisher release digests are unavailable and require independent digest approval.
- Waifu2x 20250915 SHA256 `7425be94b94e4c8f37a1e433ac0e0100c43790e2c37418f4b65d8235adfbdc87` and Anime4KCPP v3.2.0 SHA256 `82897b0f03ddb88ab3d1affb745baf99506cfe3ceffaeaf73796c6dea4077f19` have publisher release digests verified; their current audit field `matches_recorded_ci_sha256` is false, so retain the publisher-digest evidence and do not describe them as matching the older CI pin.
- `all_upstream_digests_pinned=false`, `model_weights_and_license_certified=false`, and `included_in_customer_installer=false`. Archive audit is not inference verification or redistribution approval; native binaries/weights remain excluded from the installer and repository.

### Native CLI Smoke #269 — diagnostic only
- [Actions #269](https://github.com/niyomse-collab/niyom/actions/runs/43640094883) and [JSON artifact #14130534747](https://github.com/niyomse-collab/niyom/actions/runs/43640094883/artifacts/14130534747): Real-CUGAN and Anime4KCPP native processes exited 0 and produced validated 2x synthetic RGB and RGBA outputs; ICC and DPI 300 passed, and the RGBA report confirms exact alpha-pixel preservation.
- Real-ESRGAN was blocked by hosted-runner `vkCreateInstance failed -9` (exit `0xFFFFFFFF`); Waifu2x was blocked by the same Vulkan initialization failure plus exit `0xC0000005`.
- NVML was unavailable; runtime GPU adapter verification **0/4**; runtime VRAM guard was not requested; `real_inference_verified=false`, `candidate_output_validation_complete=false`, and `quality_improvement_verified=false`. The diagnostic workflow's SUCCESS classifies known hosted-runner limits; it is not four-engine GPU or visual-quality acceptance.

### Shop GPU evidence gate
- Push-triggered Shop GPU run #46 [Actions](https://github.com/niyomse-collab/niyom/actions/runs/43640090160) has `gate_status=success`, while the self-hosted `evidence` job remains **PENDING**; no JSON evidence artifact exists yet. This indicates the hosted status check is visible but does not prove that the dedicated shop runner has started.
- The affirmative marker in commit `644d91e` is still authorized for **Candidate #814 only**, source SHA `56820b5e34109d5dee60f7be1912028edbc9ad47`. It does not authorize installing/running Candidate #820 on the shop PC. The workflow must fail closed if the installed BUILD_PROOF or verified manifest does not match.
- Scope remains synthetic RGB/RGBA/ICC/300-DPI only; no customer image access, upload, or accepted V2 output modification.

### Consent behavior verified in current source
- The current `app_v2.py` calls `_offer_v211_four_ai_setup` on first launch. If no verified manifest and no prior decline exist, it shows a Yes/No prompt; downloads start only after Yes. No records a local decline marker to prevent repeated prompts.
- The experimental Inno Setup installer also provides a separate unchecked-by-default task to install all four engines before editor launch. These are two affirmative-consent entry points; neither starts a download without explicit user action.
- If an existing manifest/decline marker is invalid or unsafe, the app warns and keeps V2 available rather than overwriting it.

### Frozen-build warnings requiring shop runtime validation
- PyInstaller emitted non-fatal warnings for missing `pycparser.lextab/yacctab`, `scipy.special._cdflib`, driver-provided `nvcuda.dll`, and optional Numba `tbb12.dll`. Frozen build and packaged smoke checks passed, but those warnings are not proof that every optional runtime path works. Do not bundle a guessed `nvcuda.dll` or unrelated TBB runtime; verify CUDA/NVML against the installed NVIDIA driver and test any Numba path actually used on the shop PC.

### V2/GFPGAN protection and release gate
- Protected Blob SHA between PR #18 base/head `288dd8501c230a118d9a7e60d2522a2cc7411bcc` and PR #20 HEAD `644d91e` is identical **6/6**: `.github/workflows/verify-v211-face.yml`, `signprint_ai/face_module/face_protection.py`, `signprint_ai/large_faces.py`, `signprint_ai/v211_face_contract.py`, `tests/test_v211_face_contract.py`, and `tests/test_v211_large_face_audit.py`.
- PR #20 and PR #18 remain OPEN / DRAFT / UNMERGED. No V1/V2 Stable changes, no merge/release, no customer images or native binaries/weights committed. V2 remains the accepted master; real four-engine shop GPU execution, VRAM stress, visual A/B and print certification remain open.


## 15 พฤศจิกายน 2569 09:42 ICT — Exact-head Candidate #821 / source and GPU gate refresh

### PR identity and review scope
- PR #20 remains OPEN / DRAFT / UNMERGED on `work/v211-four-engine-v2-bridge-20261103`; exact candidate source HEAD: `d34391e3addfd7cec0989ba1cccf51679f3a35f5`. PR #18 remains the V2.1.1/GFPGAN comparison baseline at `288dd8501c230a118d9a7e60d2522a2cc7411bcc`.
- GitHub Compare from PR #18 base to PR #20 HEAD reports 870 commits ahead / 0 behind and 75 changed paths (23,166 additions / 425 deletions). This is ancestry, not 870 changed files. Compared with the earlier documented PR HEAD `2ae7d34b97ddea8a2e39097530b8f118d8bd92cf`, the branch advanced 66 commits touching 27 paths, including source, tests and workflow changes; do not describe the entire interval as documentation-only. The final `d34391e` commit itself is documentation-only relative to Candidate #820 source `644d91e7599ce874f04604339c6597718f465575`.
- No rebase, reset, force-push, merge or release was performed.

### Windows Candidate #821 — exact HEAD success
- [Actions #821](https://github.com/niyomse-collab/niyom/actions/runs/43644765171): SUCCESS, both `bridge-tests` and `windows-v2-candidate` jobs.
- Bridge/Fusion/coordination: 359 passed. Privacy/provisioning/manifest/hash: 63 passed.
- Frozen checks passed: V2 imports; single-page BigTIFF and streamed libvips path; packaged provisioning `--check-only` without download/write; isolated consented cache cleanup; diagnostic `--help`; PowerShell provenance verifier; exact BUILD_PROOF/source SHA; installer-slice SHA256; artifact upload.
- Build log reports `accepted_v2_sha256_unchanged=true`.
- Installer SHA256: `e7003fab275b08dcfc8f17a2bbff9c6ccac4338363dcb49428095f90726cb534`.
- Artifact ID `14133694301`; size 2,584,647,432 bytes; ZIP SHA256 `e08672794be99f1f942747a2ed3b232d233f336f426b7ba0eead29ffb551152b`; expires 22 Nov 2026 05:19 ICT. [Candidate #821 artifact](https://github.com/niyomse-collab/niyom/actions/runs/43644765171/artifacts/14133694301).
- The candidate build's non-fatal warnings include driver-provided `nvcuda.dll` absent on the hosted builder, optional Numba `tbb12.dll`, and optional `pycparser`/SciPy hidden imports. Do not bundle unverified driver/TBB DLLs; verify optional import paths and the installed NVIDIA driver on the shop PC.

### Independent Core regression
- [Core #1400](https://github.com/niyomse-collab/niyom/actions/runs/43644765164): Windows 1,016 passed / 1 skipped; Ubuntu 1,014 passed / 3 skipped; `compileall` passed on both.

### Official archives and native CLI diagnostic
- [Official Archive Audit #209](https://github.com/niyomse-collab/niyom/actions/runs/43644765162): all four official Windows archives were downloaded, SHA256-checked, safely inspected and transactionally provisioned into ephemeral QA storage. Real-ESRGAN and Real-CUGAN still use observed CI pins without publisher release digests; Waifu2x and Anime4KCPP publisher digests were verified. `all_upstream_digests_pinned=false`; model-weight/license certification and redistribution approval remain false. No binaries or weights are included in the installer or repository.
- [Native CLI Smoke #270](https://github.com/niyomse-collab/niyom/actions/runs/43644765183), JSON artifact [14133013037](https://github.com/niyomse-collab/niyom/actions/runs/43644765183/artifacts/14133013037): Real-CUGAN and Anime4KCPP native processes produced validated synthetic 2x RGB and RGBA/ICC/300-DPI outputs. Real-ESRGAN and Waifu2x were blocked by hosted-runner `vkCreateInstance failed -9`; Waifu2x also reported `0xC0000005`. Physical adapter verification was 0/4, the runtime VRAM guard was not requested, and `real_inference_verified=false` / `quality_improvement_verified=false`. Diagnostic workflow SUCCESS is classification of hosted-runner limits, not four-engine GPU acceptance.

### Automatic setup, V2 preservation and large-image guard
- Current source has two affirmative-consent entry points: an unchecked-by-default installer task and a local-only first-launch Yes/No prompt when no verified manifest or prior decline marker exists. `initial_setup_state()` performs local checks only; downloads start only after Yes. No records a local decline marker; a failed download remains retryable. Tests cover no-network local state, first-launch consent ordering, decline suppression and symlink/fail-closed cases.
- Once a verified manifest exists, `NiyomSilpCoreAdapter.process` calls the four-engine bridge after the accepted V2 output is durably saved. It passes the V2 reference into the real-engine runner; production `real_engines=True` plus `v2_reference` requires the runtime GPU probe and enables the 6,144 MiB device-wide VRAM guard with a 512 MiB reserve. Cancellation and fail-closed fallback preserve the V2 raster; a separate QA sidecar is never the accepted print output.
- Large auxiliary jobs above 18 MP use disk-backed tiles only for PNG or single-page 8-bit RGB/RGBA TIFF/BigTIFF source and V2 reference. JPEG/WebP, multipage TIFF, CMYK and unsupported bit depths remain V2-only. The shop diagnostic is designed to require per-process adapter evidence and sampled VRAM budget evidence; actual shop stress remains unverified.
- The optional styled-effect ROI selector protects selected pixels by copying them from accepted V2; it does not OCR, rewrite or reconstruct text. It is separate from engine selection; the four engines remain coordinated automatically.

### Shop GPU and GFPGAN protection
- Shop GPU run #46 [Actions](https://github.com/niyomse-collab/niyom/actions/runs/43640090160) still has hosted `gate_status` SUCCESS and the dedicated self-hosted `evidence` job PENDING, with no diagnostic log or evidence artifact. The existing consent marker authorizes Candidate #814 only; it does not authorize Candidate #821. No new self-hosted shop run was started.
- Six protected V2/GFPGAN files were independently fetched at both PR #18 base and PR #20 HEAD and their Git blob SHAs match 6/6: `.github/workflows/verify-v211-face.yml`, `signprint_ai/face_module/face_protection.py`, `signprint_ai/large_faces.py`, `signprint_ai/v211_face_contract.py`, `tests/test_v211_face_contract.py`, and `tests/test_v211_large_face_audit.py`.
- No V1/V2 Stable changes, customer images, native binaries or model weights were committed. PR #20 and PR #18 remain Draft/unmerged; V2 remains the accepted master. Real four-engine GTX 1660 Ti inference, 6 GB VRAM stress, visual A/B, Photoshop/MainTop and print acceptance remain NOT CERTIFIED.

## 15 พฤศจิกายน 2569 20:57 ICT — Exact PR HEAD c4a2971 / Windows Candidate #845

### PR และขอบเขตการเปลี่ยนแปลง
- PR #20 ยังคง OPEN / DRAFT / UNMERGED บน `work/v211-four-engine-v2-bridge-20261103`; exact HEAD `c4a2971b33c13d4b399a72a6fda8c1654d547d9d`.
- PR #18 ยังคง OPEN / DRAFT / UNMERGED และเป็น base ของ PR #20 ที่ SHA `288dd8501c230a118d9a7e60d2522a2cc7411bcc`.
- Compare จาก PR #20 status HEAD `d34391e3addfd7cec0989ba1cccf51679f3a35f5` ถึง `c4a2971`: 15 commits, 9 changed paths. มีการเปลี่ยน Source ใน spec, `run.py`, four-engine bridge, large-image bridge และ setup CLI พร้อม regression tests; ไม่ใช่ documentation-only interval.
- Commit `c4a2971` ปรับ synthetic stripe ใน `tests/test_v211_four_engine_bridge.py` เพียง 1 บรรทัด เพื่อให้ counterfactual pixel contribution ของทั้งสี่ synthetic processors ตรวจพบได้ ไม่ได้เปลี่ยน Production Fusion weights/algorithm.

### Windows Candidate #845 — exact HEAD success
- [GitHub Actions #845](https://github.com/niyomse-collab/niyom/actions/runs/43718661133): SUCCESS, ทั้ง `bridge-tests` และ `windows-v2-candidate` ผ่านบน exact HEAD `c4a2971`.
- Bridge/Fusion/coordination: **366 passed**; privacy/provisioning/manifest/hash: **63 passed**; รวม **429 passed**.
- Frozen checks ผ่าน: V2 imports, single-page BigTIFF/libvips smoke, packaged provisioning `--check-only` โดยไม่ดาวน์โหลด, isolated consented cache cleanup, diagnostic `--help`, BUILD_PROOF exact source SHA, installer-slice SHA256 และ artifact upload.
- Installer SHA256: `c959487b3d52e41c0ca007c9a5017fe5b52f2dce091a557f3fb85255a9d28150`.
- Artifact ID `14164557743`; size **2,584,578,311 bytes**; artifact ZIP SHA256 `1ecdf59a2cd4e1dfc1570fabc82bf7628884472cbf1da75302572e68efe849b2`; expires **22 พ.ย. 2569 20:53 ICT**. [Download Candidate #845](https://github.com/niyomse-collab/niyom/actions/runs/43718661133/artifacts/14164557743).
- Frozen TIFF smoke ใน `run.py` ใช้ BigTIFF fixture ขนาดเล็ก target **257×193**; ตรวจ header, single-page, streamed seed/QA crop, odd-dimension pad/crop, ICC/DPI และ V2 SHA unchanged. Report ระบุ `gpu_runtime_initialized=false` และ `native_ai_engines_started=false`. นี่ไม่ใช่การทดสอบ Native GPU หรือภาพ >18MP.
- PyInstaller มี non-fatal warnings: `pycparser.lextab/yacctab`, `scipy.special._cdflib`, driver-provided `nvcuda.dll`, optional `tbb12.dll` และ Torch internal optional `expecttest`. Package smoke ทดสอบ SciPy/Numba workqueue/CFFI paths ผ่าน; ห้ามคัดลอก DLL จากแหล่งไม่ตรวจสอบหรือถือว่า warning เหล่านี้ได้รับการรับรองบนเครื่องร้านแล้ว.

### Independent Core regression
- [GitHub Actions #1429](https://github.com/niyomse-collab/niyom/actions/runs/43718661129): Windows **1,023 passed / 1 skipped**; Ubuntu **1,021 passed / 3 skipped**; pytest และ compileall ผ่านทั้งสองระบบ.

### Large BigTIFF >18 MP — Synthetic end-to-end test
- Bridge regression มี `test_large_bigtiff_end_to_end_tiled_fusion_fails_closed_without_real_adapter_evidence`: source TIFF **2,122×2,122**, accepted V2 BigTIFF **4,244×4,244 = 18,011,536 pixels**.
- ใช้ synthetic CPU processors ไม่ใช่ native AI binaries: ทั้งสี่ engine ทำ 9 tiles/engine และตรวจ 12 seam comparisons/engine; fusion ยืนยันว่า synthetic candidates ทั้งสี่มีผลต่อ RGB pixels จริง.
- ผล bridge ที่คาดหวังคือ `gpu_runtime_unverified`, ไม่มี QA sidecar ถูกเผยแพร่, accepted V2 BigTIFF SHA256 ไม่เปลี่ยน และ `quality_certified=false`. นี่พิสูจน์ integration/fail-closed path ใน fixture นี้เท่านั้น ไม่ใช่ Native four-engine inference, VRAM stress หรือ visual quality บนภาพร้าน.

### Official archives และ Native CLI diagnostic
- [Official Archive Audit #223](https://github.com/niyomse-collab/niyom/actions/runs/43718661130): ดาวน์โหลด ตรวจ hash ตรวจ archive และ provision ทั้งสี่ official Windows archives ลง ephemeral QA directory สำเร็จ; manifest มีครบ `real_esrgan, waifu2x, real_cugan, anime4k`.
- Archive SHA256: Real-ESRGAN `abc02804e17982a3be33675e4d471e91ea374e65b70167abc09e31acb412802d` (observed CI pin, no publisher digest); Waifu2x `7425be94b94e4c8f37a1e433ac0e0100c43790e2c37418f4b65d8235adfbdc87` (publisher digest); Real-CUGAN `c6e08d46c11704b1e3a1ada9ddd591cb5005f52f132136c8633ba25def400e01` (observed CI pin, no publisher digest); Anime4KCPP `82897b0f03ddb88ab3d1affb745baf99506cfe3ceffaeaf73796c6dea4077f19` (publisher digest).
- Audit reports `model_weights_and_license_certified=false` and `license_redistribution_approved=false`; native executables/weights remain excluded from the installer and repository.
- [Native CLI Smoke #291](https://github.com/niyomse-collab/niyom/actions/runs/43718661108): actual official CLI runs on synthetic RGB and RGBA/ICC/300-DPI images. Real-CUGAN and Anime4KCPP each produced validated 2x outputs; Real-ESRGAN failed with hosted-runner `vkCreateInstance failed -9`; Waifu2x had the same Vulkan initialization failure plus `0xC0000005`. NVML was unavailable, physical adapter verification **0/4**, VRAM guard was not enabled, `real_inference_verified=false`, and `quality_improvement_verified=false`. Workflow SUCCESS classifies the host limitation; it is not a four-engine GPU or quality pass.
- Native diagnostic JSON artifact ID `14163114095`; ZIP SHA256 `d1f76410f2b66caf4724f86107fdd21ddcecbc84c073e88db09866105c81aaaa`.

### PR #18 / GFPGAN preservation
- PR #18's own face-related changes are additive safeguards: `face_protection.py` corrects Studio AI's completed-face count and marks partial selected-face restoration as incomplete; `large_faces.py` adds per-selected-ROI GFPGAN audit indexing. It does not replace the GFPGAN model or the accepted V2 Real-ESRGAN primary path.
- Comparing PR #20 base `288dd850` with current PR #20 HEAD `c4a2971`, protected Git blob SHA values are identical **5/5**: `face_module/face_protection.py`, `large_faces.py`, `v211_face_contract.py`, `tests/test_v211_face_contract.py`, `tests/test_v211_large_face_audit.py`.
- PR #20's 75 changed paths contain source, tests, workflows and docs; no executable, DLL, archive, model-weight or customer-image file was added.

### Remaining gates
- No shop self-hosted GPU run or exact-head shop consent evidence was available. Real four-engine inference on GTX 1660 Ti, per-process adapter binding, 6 GB VRAM stress, cancellation under native GPU load, real image A/B, Photoshop/MainTop and print acceptance remain NOT CERTIFIED.
- V2 remains the accepted master. PR #20 and PR #18 remain Draft/unmerged; no V1/V2 Stable edits, merge, release or quality-superiority claim.


## 15 พฤศจิกายน 2569 22:49 ICT — Exact PR-head Candidate #720 และ CI refresh

ขอบเขตยังคงเฉพาะ Draft PR #20 / `work/v211-four-engine-v2-bridge-20261103`; PR #18 ใช้เป็นฐานอ้างอิงเพื่อรักษา V2/GFPGAN. รายการนี้เป็นการบันทึกผลที่ตรวจจาก GitHub Actions และ Git blob SHA โดยตรง ไม่ใช่การรับรองคุณภาพภาพหรือ GPU เครื่องร้าน

### Exact source และ Windows Candidate

- PR HEAD ที่ตรวจ: `2ae7d34b97ddea8a2e39097530b8f118d8bd92cf`.
- Windows Candidate **#720** [Actions](https://github.com/niyomse-collab/niyom/actions/runs/43484981826) สำเร็จ **2/2 jobs**: `bridge-tests` และ `windows-v2-candidate`.
- Frozen checks ที่ผ่าน: V2 packaged imports; packaged four-engine provisioning `--check-only` โดยไม่ดาวน์โหลด; isolated consented cache cleanup; packaged diagnostic `--help`; PowerShell provenance verifier parse; BUILD_PROOF ตรง source SHA; installer slice SHA256 ทุกส่วน; และ upload experimental artifact.
- Installer SHA256: `4e47fbc114117e72f70c595aac0b6de1fee73dbc183d3850cb41fc44b4daeda5`.
- Artifact ID `14069031153`; ขนาด **2,584,617,048 bytes**; ZIP SHA256 `a2eb585551032d8f2cdb8ec7ae24e0bf45116dc9eceb19c691ff73e5ece076f6`; หมดอายุ **21 พ.ย. 2569 02:07 ICT**. [Candidate #720 artifact](https://github.com/niyomse-collab/niyom/actions/runs/43484981826/artifacts/14069031153).
- Candidate #720 รับรองเฉพาะ frozen package/provenance และ dispatch แบบไม่ดาวน์โหลด ไม่รับรอง interactive install/uninstall, native GPU 4/4, VRAM, visual A/B หรือคุณภาพงานพิมพ์.

### Independent Core #1283

- [Actions #1283](https://github.com/niyomse-collab/niyom/actions/runs/43484981647): Windows **979 passed / 1 skipped**; Ubuntu **977 passed / 3 skipped**; pytest และ compileall ผ่านทั้งสองระบบ.

### Official Archive Audit #158

- [Actions #158](https://github.com/niyomse-collab/niyom/actions/runs/43484981648) ดาวน์โหลด ตรวจ SHA256 ตรวจ ZIP contents และ provision official Windows archives ทั้งสี่ลง ephemeral QA directory; Manifest แสดงครบ `real_esrgan, waifu2x, real_cugan, anime4k`.
- Real-ESRGAN และ Real-CUGAN ยังใช้ observed CI SHA256 pin เพราะ upstream ไม่เผย publisher digest; Waifu2x และ Anime4KCPP ใช้ published digest.
- ผล audit ยังคง `all_upstream_digests_pinned=false`, `quality_certified=false`, `license_redistribution_approved=false`. Binary/weights ไม่ถูกรวมใน Installer และไม่มีไฟล์เหล่านี้ commit เข้า repository.

### Native CLI Smoke #200 — diagnostic เท่านั้น

- [Actions #200](https://github.com/niyomse-collab/niyom/actions/runs/43484981676), JSON artifact [14065489882](https://github.com/niyomse-collab/niyom/actions/runs/43484981676/artifacts/14065489882). ทดสอบ synthetic RGB และ RGBA พร้อม ICC/300 DPI เท่านั้น.
- Real-CUGAN และ Anime4KCPP: native process เริ่มและจบ exit code 0; ได้ output 2x ที่ผ่าน geometry/metadata checks.
- Real-ESRGAN: `vkCreateInstance failed -9`.
- Waifu2x: `vkCreateInstance failed -9` และ exit `0xC0000005`.
- NVML เป็น `nvml_library_not_found`; physical GPU/PID-to-adapter verification **0/4**; `real_inference_verified=false`; `quality_improvement_verified=false`.
- Workflow job สรุป SUCCESS เพราะจัดประเภทข้อจำกัด Vulkan ของ hosted runner ตามที่กำหนดไว้ ไม่ใช่เพราะ native 4/4 หรือ GPU inference ผ่าน. ผลนี้ไม่หักล้างผลทดสอบที่เจ้าของเคยยืนยันบน Windows 11 GTX 1660 Ti และไม่ใช้แทน Shop GPU Evidence.

### V2 / GFPGAN / HAT compatibility audit

ตรวจ Git blob SHA ระหว่าง PR #18 base `288dd8501c230a118d9a7e60d2522a2cc7411bcc` และ PR #20 HEAD `2ae7d34b97ddea8a2e39097530b8f118d8bd92cf`; protected files **5/5 byte-identical**:

- `signprint_ai/face_module/face_protection.py`
- `signprint_ai/large_faces.py`
- `signprint_ai/v211_face_contract.py`
- `tests/test_v211_face_contract.py`
- `signprint_ai/face_module/__init__.py`

PR #20 ยังคงปิด optional HAT Assist route ที่มีใน PR #18 แยกต่างหาก; นี่ไม่ใช่การเปลี่ยน GFPGAN/Face Protection และต้องคงเป็น compatibility difference ที่เปิดเผยก่อน merge ห้าม restore HAT เงียบ ๆ ในงาน four-engine นี้.

### Consent และข้อจำกัดเครื่องร้าน

- Source ปัจจุบันมี consent สองทาง: installer task แบบ unchecked-by-default; หากข้าม task จะมี local-only Yes/No prompt หลังเปิด editor ประมาณ 600 ms. ตรวจสถานะ Manifest/decline marker โดยไม่เข้าถึงเครือข่าย; download เริ่มหลัง Yes เท่านั้น. หากมี Manifest ครบแล้วจะไม่ถามซ้ำ และงานที่รองรับเรียกทั้งสี่ engine อัตโนมัติแบบ offline. Status document นี้เป็นแหล่งอธิบายพฤติกรรมปัจจุบัน; ข้อความเก่าใน PR description ที่ระบุ installer-only ถูก supersede แล้ว.
- ไม่มี affirmative shop-GPU consent marker จึงไม่ schedule self-hosted runner. ยังไม่มีหลักฐาน Native GPU 4/4, VRAM peak/hard cap 6 GB, stress >18 MP/4x, cancel ระหว่าง native process, A/B ภาพจริง, Photoshop หรือ MainTop RIP.
- PR #20 ยังคง Draft/unmerged; PR #18 ไม่ถูกแก้; ไม่มี V1/V2 Stable changes, ไม่มี customer artwork/binaries/weights commit, ไม่มี merge/release และไม่มีการอ้างว่าคุณภาพเหนือ V2.



## 16 พฤศจิกายน 2569 04:31 ICT — เพิ่มการดึงและ Hash เอกสาร License จากต้นทาง

- Exact parent HEAD: 8e63bd0ec86017ae82bb7cc448787d77dcf609b7 on the V2.1.1 research branch.
- Windows Candidate #854 on that exact parent HEAD completed SUCCESS 2/2 jobs (bridge-tests and windows-v2-candidate). Installer SHA256: e1ab0f085c8543a3e38c43507b26a161ed7f507a3339bddb03e47acea1090b37. Artifact ID: 14180926415; ZIP SHA256: e736bd62d5ef07b47e8b39ca259c8549c5e26e98aa80061b71a7291a4a112d6e; expires 23 Nov 2569 04:07 ICT. This is frozen-package/provenance evidence only, not shop GPU or print acceptance.
- Added a bounded, allowlisted GitHub raw-text retrieval path to tools/v211_official_assets_audit.py. It maps only canonical HTTPS github.com/.../blob/... license URLs to raw.githubusercontent.com, rejects untrusted redirects, caps each document at 1 MiB, validates UTF-8, records HTTP status/bytes/line count/SHA256, and stores hashes/metadata rather than license text.
- The audit now retrieves and hashes six source-license documents: Real-ESRGAN-ncnn-vulkan MIT, Real-ESRGAN project BSD-3-Clause, Waifu2x MIT, Real-CUGAN MIT, Anime4KCPP CLI GPL-3.0 and Anime4KCPP core MIT. The JSON/console output keeps source-license retrieval separate from model-weight rights.
- model_weights_and_license_certified=false and license_redistribution_approved=false remain hard-coded. The new checks do not authorize redistribution and do not certify bundled model weights. Any missing/untrusted/oversized license document makes the provenance workflow fail rather than silently reporting success.
- Added offline regression tests for URL allowlisting, redirect rejection, size limit, UTF-8 validation, SHA256 recording, and all six license-source records without granting redistribution.
- This commit changes only archive/license audit code, its tests, the corresponding workflow and this status document. It does not change inference, fusion, UI, installer payload, V1, V2 Stable, GFPGAN or model weights. Exact-head CI is pending; no shop GPU evidence was started.


## 19 พฤศจิกายน 2569 16:58 ICT — Exact-head Candidate #970 / large-image disk-reserve verification

### PR identity and scope
- PR #20 branch: `work/v211-four-engine-v2-bridge-20261103`; exact code/test HEAD verified: `4726992a39ff1bd9b71ea636a04dbf9b678bb829`. The latest commit only adds the missing local `Path` import to the output-volume disk-guard regression test.
- PR #18 remains the comparison/base at `288dd8501c230a118d9a7e60d2522a2cc7411bcc`. Compare to PR #20 reports **966 commits ahead / 0 behind / 77 changed paths**; this is commit ancestry, not 966 changed files.
- No merge, rebase, reset, force-push or release was performed.

### Windows Candidate #970 — exact HEAD success
- [GitHub Actions #970](https://github.com/niyomse-collab/niyom/actions/runs/44443889725): **SUCCESS, 2/2 jobs** on exact source SHA `4726992a39ff1bd9b71ea636a04dbf9b678bb829`.
- Bridge/Fusion/coordination: **416 passed**; privacy/provisioning/manifest/hash: **69 passed**; source compileall passed.
- Frozen checks passed: V2 packaged imports; streamed single-page BigTIFF/libvips QA path; packaged four-engine provisioning `--check-only` without downloads; consented cache cleanup confined to the current profile; packaged diagnostic `--help`; PowerShell provenance verifier syntax; exact BUILD_PROOF/source SHA; installer-slice SHA256; experimental artifact upload.
- Installer SHA256: `58747389b0fde4791229b4d5847b4737ee49cbd879f2f259a08bcf941eb27666`.
- Artifact ID `14492943659`; size **2,584,761,859 bytes**; ZIP SHA256 `d1789de4c3c4ff8b4bab55aa342507834842d0bbfead0261d69fcbce37ce804e`; expires **26 พ.ย. 2569 09:44 ICT**. [Download Candidate #970](https://github.com/niyomse-collab/niyom/actions/runs/44443889725/artifacts/14492943659).
- Non-fatal hosted-build warnings remain for driver-provided `nvcuda.dll`, optional Numba `tbb12.dll`, `pycparser.lextab/yacctab`, `scipy.special._cdflib` and Torch's optional `expecttest`. Do not bundle guessed driver/TBB DLLs; verify actual CUDA/NVML and optional Numba paths on the shop PC.

### Independent Core #1579
- [GitHub Actions #1579](https://github.com/niyomse-collab/niyom/actions/runs/44443889780): Windows **1,085 passed / 1 skipped**; Ubuntu **1,083 passed / 3 skipped**; compileall passed on both.

### Official archive / source-license audit #296
- [GitHub Actions #296](https://github.com/niyomse-collab/niyom/actions/runs/44443889730): archive audit **32 passed**, provisioning **11 passed**; all four official Windows archives were downloaded, SHA256-checked, safely audited and transactionally provisioned into ephemeral QA storage.
- Archive SHA256: Real-ESRGAN v0.2.5.0 `abc02804e17982a3be33675e4d471e91ea374e65b70167abc09e31acb412802d` (**observed CI pin; no publisher digest**); Waifu2x 20250915 `7425be94b94e4c8f37a1e433ac0e0100c43790e2c37418f4b65d8235adfbdc87` (**published digest**); Real-CUGAN 20220728 `c6e08d46c11704b1e3a1ada9ddd591cb5005f52f132136c8633ba25def400e01` (**observed CI pin; no publisher digest**); Anime4KCPP v3.2.0 `82897b0f03ddb88ab3d1affb745baf99506cfe3ceffaeaf73796c6dea4077f19` (**published digest**).
- Six upstream source-license documents were retrieved and SHA256-hashed. `all_upstream_digests_pinned=false`, `model_weights_and_license_certified=false` and `license_redistribution_approved=false` remain intentional. No native binary, model weight or customer image is committed or bundled.

### Native CLI Smoke #402 — diagnostic only, not 4/4 acceptance
- [GitHub Actions #402](https://github.com/niyomse-collab/niyom/actions/runs/44443889732), JSON report artifact [14492122986](https://github.com/niyomse-collab/niyom/actions/runs/44443889732/artifacts/14492122986): **23 diagnostic tests passed**. On synthetic RGB and RGBA/ICC/300-DPI inputs, Real-CUGAN and Anime4KCPP produced validated 2x outputs; Real-ESRGAN was blocked by hosted-runner `vkCreateInstance failed -9`; Waifu2x was blocked by the same Vulkan initialization failure plus `0xC0000005`.
- `completed_engine_count=2`, `physical_adapter_verification=0/4`, `runtime_vram_budget_passed=false`, `real_inference_verified=false` and `quality_improvement_verified=false`. Workflow SUCCESS classifies known hosted-runner Vulkan limits; it is not a native GPU 4/4 or quality pass and does not replace the owner's Windows 11 GTX 1660 Ti test.

### Large-image, scale and memory policy
- Disk-backed native inference starts above **18 MP**. The disk-reserve guard now checks the nearest existing directory on the actual output/work volume and reserves remaining candidate rasters, already-completed candidate bytes, fusion raster and temporary streamed-PNG space before launching the next engine. Regression coverage includes missing output parents and a shrinking free-space scenario.
- Native tiles remain **512 px with 32 px overlap**; overlap disagreement is checked before stitching. RGBA alpha comes from accepted V2, and cancellation/failure keeps the V2 raster unchanged.
- The auxiliary large-image path accepts PNG or single-page 8-bit RGB/RGBA TIFF/BigTIFF, converted to private PNG seed/reference files. JPEG/WebP, multipage TIFF, CMYK and unsupported bit depths remain V2-only.
- Scale policy is **one native 2x pass on a half-target seed**. Only exact isotropic 2x and 4x source-to-target ratios are accepted. Final 4x uses a half-target seed plus one native 2x pass; 3x, 8x and anisotropic ratios are rejected before manifest loading or native launch. This is not native 4x inference or multi-pass processing. The 6,144 MiB device-wide budget and 512 MiB reserve are enforced by the production guard, but peak VRAM on the shop GTX 1660 Ti has not been measured.

### V2 / GFPGAN and shop acceptance
- Protected files compared by Git Blob SHA between PR #18 base and exact PR #20 HEAD remain byte-identical **6/6**: `.github/workflows/verify-v211-face.yml`, `signprint_ai/face_module/face_protection.py`, `signprint_ai/large_faces.py`, `signprint_ai/v211_face_contract.py`, `tests/test_v211_face_contract.py`, and `tests/test_v211_large_face_audit.py`. The core adapter integration is additive and includes a regression proving that an applied GFPGAN result with unmapped face ROIs forces V2-only output.
- No affirmative exact-head shop-GPU consent marker was supplied; no self-hosted shop runner was started. Native GPU 4/4 on the shop PC, peak VRAM stress, real-image A/B across faces/animals/objects/Thai-English-Chinese text/flat fills/gradients/transparent edges, Photoshop/MainTop and physical print acceptance remain **NOT CERTIFIED**.
- PR #20 and PR #18 remain OPEN / DRAFT / UNMERGED. V2 remains the accepted master. No V1/V2 Stable changes, merge, release, customer images or native binaries/weights committed; no quality-superiority claim.


## 19 พฤศจิกายน 2569 17:44 ICT — Exact PR HEAD Candidate #971 / CI refresh

### PR identity and source scope
- PR #20 remains **OPEN / DRAFT / UNMERGED**, base `feature/v2.1.1-super-ai` at `288dd8501c230a118d9a7e60d2522a2cc7411bcc`; head branch `work/v211-four-engine-v2-bridge-20261103`, exact PR HEAD `98955b1685eaf51228e32cb3e388cc174ea6be6a`.
- Compare against the PR #18 base reports **967 commits ahead / 0 behind / 77 changed paths**. This is commit ancestry, not a changed-file count.
- Compare from the previously tested code/test HEAD `4726992a39ff1bd9b71ea636a04dbf9b678bb829` to the current PR HEAD shows exactly **one changed file**: this status document, **39 additions / 0 deletions**. No production source, tests, workflow, spec or installer input changed after Candidate #970's code/test source.
- PR #18 remains **OPEN / DRAFT / UNMERGED** at base SHA `288dd8501c230a118d9a7e60d2522a2cc7411bcc`. No merge, rebase, reset, force-push or release was performed.

### Windows Candidate #971 — exact PR HEAD success
- [GitHub Actions #971](https://github.com/niyomse-collab/niyom/actions/runs/44502080756): **SUCCESS, 2/2 jobs** on exact PR HEAD `98955b1685eaf51228e32cb3e388cc174ea6be6a`.
- Bridge/Fusion/coordination: **416 passed**; privacy/provisioning/manifest/hash: **69 passed**.
- Frozen candidate checks passed: source syntax; V2 packaged imports; streamed single-page BigTIFF/libvips QA dispatch; packaged four-engine provisioning `--check-only` without downloads; consented model-cache cleanup confined to isolated synthetic/current-profile data; packaged diagnostic `--help`; read-only shop-runner diagnostic parsing; provenance verifier syntax; BUILD_PROOF exact source SHA; every installer slice SHA256; and experimental artifact upload. The workflow did not publish a Release.
- Installer SHA256: `9f6f096029324d5d55900c7b127f76cafa5c8664d4a2f950376f86a872dbb63d`.
- Artifact ID `14519388206`; size **2,584,705,201 bytes**; artifact ZIP SHA256 `e6a509642aa2a5f8bf9ddd60b772c13efd3825d8301bace20d53224fb9873fa0`; expires **26 พ.ย. 2569 17:28:59 ICT**. [Download Candidate #971](https://github.com/niyomse-collab/niyom/actions/runs/44502080756/artifacts/14519388206).
- Non-fatal hosted-runner packaging warnings: driver-provided `nvcuda.dll` unavailable; optional Numba `tbb12.dll`, PyInstaller hidden imports `pycparser.lextab/yacctab` and `scipy.special._cdflib` unavailable; Torch optional `expecttest` and Triton warnings. Do not guess or bundle NVIDIA driver/TBB DLLs. Runtime relevance must be checked on the shop PC.

### Independent Core #1581
- [GitHub Actions #1581](https://github.com/niyomse-collab/niyom/actions/runs/44502080772): Windows **1,085 passed / 1 skipped**; Ubuntu **1,083 passed / 3 skipped**. Pytest and `compileall` completed successfully on both platforms.

### Official Archive / source-license Audit #297
- [GitHub Actions #297](https://github.com/niyomse-collab/niyom/actions/runs/44502080791): archive audit **32 passed**; provisioning **11 passed**. All four official Windows archives were downloaded, hash-checked, safely audited and transactionally provisioned into ephemeral QA storage. Six upstream source-license documents were retrieved and SHA256-hashed.
- Archive SHA256 values are unchanged from #296: Real-ESRGAN v0.2.5.0 `abc02804e17982a3be33675e4d471e91ea374e65b70167abc09e31acb412802d` (**observed CI pin; no publisher digest**); Waifu2x 20250915 `7425be94b94e4c8f37a1e433ac0e0100c43790e2c37418f4b65d8235adfbdc87` (**published digest**); Real-CUGAN 20220728 `c6e08d46c11704b1e3a1ada9ddd591cb5005f52f132136c8633ba25def400e01` (**observed CI pin; no publisher digest**); Anime4KCPP v3.2.0 `82897b0f03ddb88ab3d1affb745baf99506cfe3ceffaeaf73796c6dea4077f19` (**published digest**).
- `all_provenance_checks_passed=true` for archive/source audit and provisioning, but `license_redistribution_approved=false`, `model_weights_and_license_certified=false` and `real_inference_verified=false` remain intentional. Source-license retrieval does not grant model-weight redistribution rights. No native binaries, model weights or customer images were committed or bundled.

### Native CLI Smoke #403 — diagnostic only, not four-engine acceptance
- [GitHub Actions #403](https://github.com/niyomse-collab/niyom/actions/runs/44502080797), JSON report artifact [14517287780](https://github.com/niyomse-collab/niyom/actions/runs/44502080797/artifacts/14517287780): **23 diagnostic tests passed** on synthetic RGB and synthetic RGBA with embedded ICC / 300 DPI.
- Real-CUGAN and Anime4KCPP each started and exited 0, producing validated 2x outputs; alpha, ICC and DPI checks passed for these outputs. This is native CLI execution on a hosted runner, but physical GPU adapter use was not verified.
- Real-ESRGAN was blocked by hosted-runner `vkCreateInstance failed -9`; Waifu2x had the same Vulkan initialization failure plus `0xC0000005`. `completed_engine_count=2`; physical adapter verification **0/4**; `runtime_vram_guard_enabled=false`; `runtime_vram_budget_verified=false`; `real_inference_verified=false`; `quality_improvement_verified=false`. Workflow SUCCESS means the known Vulkan-host limitation was classified, not that four-engine GPU inference passed. This does not negate the owner's earlier Windows 11 GTX 1660 Ti tests, and it is not a substitute for shop evidence.

### PR #18 / V2 / GFPGAN protection
- Direct Git Blob SHA comparison between PR #18 base and exact PR #20 HEAD confirms **6/6 byte-identical**: `.github/workflows/verify-v211-face.yml`, `signprint_ai/face_module/face_protection.py`, `signprint_ai/large_faces.py`, `signprint_ai/v211_face_contract.py`, `tests/test_v211_face_contract.py`, and `tests/test_v211_large_face_audit.py`.
- The additive bridge still fails closed to V2 when applied GFPGAN output cannot be mapped to protected face ROIs. PR #20's optional HAT Assist execution route remains a separate compatibility difference from PR #18 and has not been silently restored.
- No exact-head affirmative shop-GPU consent evidence exists, so no self-hosted shop runner was started. Shop installation/uninstallation, real four-engine inference on GTX 1660 Ti, per-process adapter binding, peak VRAM / 6 GB stress, cancellation under native load, real-image A/B, Photoshop/MainTop and physical print acceptance remain **NOT CERTIFIED**.
- V2 remains the accepted master. PR #20 and PR #18 remain Draft/unmerged. No V1/V2 Stable changes, merge, release, customer images or native binaries/weights committed; no claim of quality superiority over V2.

## 21 พฤศจิกายน 2569 01:54 ICT — Exact-head Candidate #999 / scale-contract correction

### Current source and CI
- PR #20 remains **OPEN / DRAFT / UNMERGED** on `work/v211-four-engine-v2-bridge-20261103`, exact source/test HEAD `a490929598bcbd4be6668c9f3d18ae5da77902a9`; PR #18 remains **OPEN / DRAFT / UNMERGED** and is the base at `288dd8501c230a118d9a7e60d2522a2cc7411bcc`. No V1/V2 Stable change, merge, rebase, force-push or release.
- Windows Candidate #999: [Actions](https://github.com/niyomse-collab/niyom/actions/runs/44785465670) — **SUCCESS 2/2 jobs**. Bridge/Fusion/coordination **432 passed**; privacy/provisioning/hash **69 passed**. Frozen package, isolated Inno consent/success/failure/uninstall fixture, 24 MP BigTIFF/libvips smoke, packaged provisioning `--check-only`, isolated cache cleanup, provenance and installer-slice SHA256 checks passed. This is package/CI acceptance, not shop-PC acceptance.
- Independent Core #1641: [Actions](https://github.com/niyomse-collab/niyom/actions/runs/44785465720) — Windows **1,101 passed / 1 skipped**; Ubuntu **1,099 passed / 3 skipped**; pytest and compileall passed on both.
- Official archive audit #325: [Actions](https://github.com/niyomse-collab/niyom/actions/runs/44785465669) — **32 archive checks + 11 provisioning checks passed**. Real-ESRGAN and Real-CUGAN remain observed CI SHA pins without publisher digests; model-weight rights and redistribution approval remain uncertified.
- Native CLI smoke #441: [Actions](https://github.com/niyomse-collab/niyom/actions/runs/44785465721) — classified diagnostic only. Real-CUGAN and Anime4KCPP produced validated synthetic 2x outputs; Real-ESRGAN was blocked by hosted-runner `vkCreateInstance failed -9`; Waifu2x had the same Vulkan failure plus `0xC0000005`. Physical adapter verification **0/4**, runtime VRAM guard not exercised, `real_inference_verified=false`, `quality_improvement_verified=false`.

### Candidate artifact
- Artifact ID `14655319611`, size **2,584,781,410 bytes**, ZIP SHA256 `f88ae5ce8605d96f0b11ec6af80afe2a15f1161d75feb64b444ce42bc6031a47`; installer SHA256 `cb171e1141a68a03d6832cacb7cfbd30e0279bd71ff47ada7b36b080b399d0aa`.
- [Download Candidate #999](https://github.com/niyomse-collab/niyom/actions/runs/44785465670/artifacts/14655319611) — expires **28 พ.ย. 2569 01:10 ICT**. The candidate is experimental; it is not a stable or accepted print release.

### Current scale and large-image contract — supersedes older 8x notes
- The exact-head runner's `SUPPORTED_FUSION_SCALES` is **(2, 4)**. It rejects 3x, 8x and anisotropic source-to-target geometry before loading the manifest or launching a native engine. Earlier dated notes that described 8x orchestration are historical and do not describe the current code.
- Each engine performs **one native 2x pass**. Final 4x means the original is resized to a half-target seed and then receives one native 2x pass; it is not native 4x or a multi-pass 4x/8x model run. Arbitrary custom print ratios are V2-only when they do not match exact 2x/4x geometry.
- Above 18 MP, the disk-backed path uses 512 px tiles with 32 px overlap, seam validation, disk reserve, V2-derived RGBA alpha, ICC/DPI checks, cancellation and streamed QA. Current large auxiliary path accepts supported PNG and single-page 8-bit RGB/RGBA TIFF/BigTIFF inputs via private PNG intermediates; unsupported modes/formats remain V2-only. The 24 MP Candidate smoke validates the streamed V2/libvips path, not all four native engines on a 24 MP shop image.
- Runtime process cancellation and VRAM monitoring have CI contract coverage, but peak VRAM, native cancellation under load, physical GTX 1660 Ti binding and 4-engine inference remain unverified on the shop PC.

### PR #18 / face protection
- Direct Git Blob SHA comparison against PR #18 base confirms **9/9 protected GFPGAN/face files byte-identical** in PR #20: face protection, detection, selection, face-module init, large-face handling, face contract, face workflow and its two regression tests.
- V2 remains the accepted master. No native binaries, model weights or customer images were committed; no visual A/B, Photoshop/MainTop or physical print acceptance is claimed.


## 21 พฤศจิกายน 2569 03:36 ICT — Exact-head Candidate #1000 / scheduled verification

### PR identity and source scope
- PR #20 remains **OPEN / DRAFT / UNMERGED** on `work/v211-four-engine-v2-bridge-20261103`, exact HEAD `4f587adf8e1ae37b834cecb0dced3175a0d08c2f`; base remains PR #18 head `288dd8501c230a118d9a7e60d2522a2cc7411bcc`. PR #18 is also OPEN / DRAFT / UNMERGED.
- The prior tested code/test HEAD was `a490929598bcbd4be6668c9f3d18ae5da77902a9`. The exact compare to `4f587ad` contains one documentation file only: this status document (+27 / -4); no production source, tests, spec or installer inputs changed after Candidate #999.
- PR #20's changed-file list has no overlap with the six face/GFPGAN-related paths changed by PR #18: `.github/workflows/verify-v211-face.yml`, `signprint_ai/face_module/face_protection.py`, `signprint_ai/large_faces.py`, `signprint_ai/v211_face_contract.py`, `tests/test_v211_face_contract.py`, and `tests/test_v211_large_face_audit.py`. No executable, DLL, model-weight, archive or other binary-like file is present in PR #20's changed-file list.
- No V1/V2 Stable edits, merge, rebase, reset, force-push or release were performed.

### Windows Candidate #1000 — exact HEAD success
- [GitHub Actions #1000](https://github.com/niyomse-collab/niyom/actions/runs/44797755790): **SUCCESS, 2/2 jobs** on exact PR HEAD `4f587adf8e1ae37b834cecb0dced3175a0d08c2f`.
- Bridge/Fusion/coordination: **432 passed**; privacy/provisioning/manifest/hash: **69 passed**. The job log confirms both pytest commands completed successfully.
- Frozen candidate checks passed: V2 imports; isolated Inno Setup consent/success/failure/uninstall lifecycle; verified-download retry fault injection; streamed 24 MP BigTIFF/libvips QA smoke; packaged four-engine provisioning `--check-only` without network access; isolated consented cache cleanup; packaged diagnostic help dispatch; exact BUILD_PROOF/source SHA and installer-slice SHA256 verification; experimental artifact upload. These checks do not execute all four native models on the shop GPU and do not certify print quality.
- Installer SHA256 recorded by the candidate provenance report: `491aaaec0bbb0a263b5bcaddb55fb30f3ef8dd9b0d07fd5f43967d479d505335`.
- Artifact ID `14662475255`; size **2,584,632,106 bytes**; ZIP SHA256 `98392c2370da6acba7a818e05aaa40ffb6407a0a47b16f60fc0706f78eb779f3`; expires **28 พ.ย. 2569 02:31 ICT**. [Download Candidate #1000](https://github.com/niyomse-collab/niyom/actions/runs/44797755790/artifacts/14662475255). This remains an experimental candidate, not a Stable installer or print acceptance.

### Independent Core, archive audit and native CLI
- [Independent Core #1643](https://github.com/niyomse-collab/niyom/actions/runs/44797756085): Windows **1,101 passed / 1 skipped**; Ubuntu **1,099 passed / 3 skipped**; pytest and compileall passed on both.
- [Official Archive Audit #326](https://github.com/niyomse-collab/niyom/actions/runs/44797755747): archive audit **32 passed**, provisioning **11 passed**. Source-license retrieval and archive hashes are not a grant of model-weight redistribution rights; `model_weights_and_license_certified=false` and `license_redistribution_approved=false` remain intentional.
- [Native CLI Smoke #442](https://github.com/niyomse-collab/niyom/actions/runs/44797755777) is diagnostic only: Real-CUGAN and Anime4KCPP produced validated synthetic 2x outputs; Real-ESRGAN and Waifu2x were blocked by hosted-runner Vulkan initialization (`vkCreateInstance failed -9`), with Waifu2x also reporting `0xC0000005`. Physical adapter verification is **0/4**; runtime VRAM stress and four-engine inference on the shop GTX 1660 Ti remain unverified. Workflow SUCCESS means the host limitation was classified, not that 4/4 GPU inference passed.

### Current scale, image and acceptance contract
- Exact supported source-to-target scales remain **2x and 4x only**. Final 4x uses a half-target seed followed by one native 2x pass per engine; it is not native 4x inference or multi-pass 8x. 3x, 8x and anisotropic ratios are rejected before manifest loading/native launch.
- Above 18 MP, the auxiliary path uses disk-backed tiles, seam validation, streamed fusion/PNG output, disk-space preflight, V2-derived RGBA alpha, ICC/DPI checks and cancellation. The 24 MP Candidate check validates the frozen V2/libvips QA path, not four native AI engines on a 24 MP shop image.
- Synthetic Fusion guards cover bounded Anime4K contribution, flat/linear and curved gradients, thin antialiased strokes/diacritic-like marks, RGBA alpha/hidden RGB, protected face/effect regions, ICC/DPI and cancellation. These tests do not replace A/B with real fonts/artwork or human review; the small-mark fixture is geometric and is not a Thai-language font-rendering/legibility test.
- No exact-head affirmative shop-GPU consent marker was supplied; no self-hosted shop runner was started. Native 4/4 inference on Windows 11 GTX 1660 Ti, peak VRAM / 6 GB stress, cancellation under native load, real A/B for people/animals/objects/Thai-English-Chinese text/flat fills/gradients/transparent edges, Photoshop/MainTop and physical print acceptance remain **NOT CERTIFIED**.
- V2 remains the accepted master. PR #20 and PR #18 remain Draft/unmerged. No customer images, native binaries or model weights were committed; no quality-superiority claim is made.

## 21 พฤศจิกายน 2569 05:21 ICT — Scale / large-format contract correction (supersedes earlier scale notes)

- **Correction:** the earlier 01:54 / 03:36 status notes incorrectly interpreted `SUPPORTED_FUSION_SCALES=(2, 4)` as a restriction on the original source-to-print ratio. In the actual bridge call chain, the source is first mapped to the accepted V2 target canvas using the selected `fit` or `stretch` transform, then resized to a private **half-target seed**. The low-level runner therefore validates the seed-to-V2-reference geometry, which is exactly **2×**; this guard is not a source-to-print scale restriction.
- The original source-to-V2 target ratio may be **2×, 3×, 4×, 8×, custom or anisotropic**, subject to minimum seed dimensions, the 1,000 MP streamed limit, 64 MiB row limit, disk reserve and supported formats. Regression coverage includes `test_large_bridge_routes_2x_3x_4x_and_8x_png_through_streamed_seed_and_tiled_runner` (2/3/4/8 parameterized), `test_large_disk_backed_bridge_supports_custom_print_scales_without_extra_native_pass`, and `test_large_streamed_bridge_keeps_native_2x_geometry_for_custom_print_scales`.
- Every engine still performs **one native 2× pass on the half-target seed**. A final 4× or 8× output does not mean native 4×/8× inference and does not use multi-pass AI. The low-level `SUPPORTED_FUSION_SCALES=(2, 4)` remains a guard for direct seed/reference runner calls.
- Large auxiliary inputs are streamed through libvips: source PNG/JPEG/WebP or single-page 8-bit RGB/RGBA TIFF/BigTIFF; accepted V2 reference PNG/JPEG/TIFF/BigTIFF. They are converted to private PNG seed/reference files before native tiled inference. Multipage TIFF, CMYK and unsupported bit depths remain V2-only.
- These are synthetic geometry/streaming regression tests, **not** proof of native GPU use, 6 GB VRAM behavior, image-quality improvement or print acceptance on the shop GTX 1660 Ti. The accepted V2 raster remains untouched and all four native processes must still pass runtime GPU verification before a QA sidecar is exposed.


## 21 พฤศจิกายน 2569 06:40 ICT — Exact-head Candidate #1002 completed

### PR / source identity
- PR #20 remains **OPEN / DRAFT / UNMERGED** at exact HEAD b8bf36f6c6fc334414e847698d24b78df86b7f38 on work/v211-four-engine-v2-bridge-20261103; base remains 288dd8501c230a118d9a7e60d2522a2cc7411bcc (PR #18 head).
- PR #18 remains **OPEN / DRAFT / UNMERGED**, base fix/v21-real-quality, head feature/v2.1.1-super-ai.
- Compare from code/test baseline 4f587adf8e1ae37b834cecb0dced3175a0d08c2f to b8bf36f6c6fc334414e847698d24b78df86b7f38: two documentation commits, one changed file only, docs/V211_FOUR_ENGINE_BRIDGE_BUILD_STATUS_TH.md (+36 / -0). No production source, tests, PyInstaller spec, installer inputs or workflow code changed after Candidate #1000's code/test baseline.

### Windows Candidate #1002 — exact HEAD SUCCESS
- [GitHub Actions #1002](https://github.com/niyomse-collab/niyom/actions/runs/44828922189): **SUCCESS, 2/2 jobs** on exact PR HEAD b8bf36f; both bridge-tests and windows-v2-candidate completed successfully.
- Bridge/Fusion/coordination: **432 passed**; privacy/provisioning/manifest/hash: **69 passed**.
- Frozen candidate checks passed: verified-download retry fault injection without network; V2-based experimental build; Inno Setup synthetic lifecycle (no consent, explicit-consent success, fail-closed setup failure, silent-uninstall cache preservation); frozen V2/import smoke; single-page BigTIFF and streamed libvips QA path; packaged provisioning --check-only without downloads; isolated consented model-cache cleanup; diagnostic --help dispatch; read-only shop-runner and provenance PowerShell syntax; exact BUILD_PROOF/source identity and every installer-slice SHA256; experimental artifact upload.
- The spec explicitly includes hidden imports for signprint_ai.v211_four_engine_bridge, signprint_ai.v211_auto_setup, signprint_ai.v211_setup_cli, tools.v211_four_engine_run, tools.v211_four_engine_coordinator, tools.v211_four_engine_fusion, tools.v211_four_engine_tiled_inference, the manifest/provisioner, GPU binding and telemetry modules. The frozen smoke validates imports/dispatch and packaging contracts; it does **not** run the four native models or prove GPU inference.
- Installer SHA256 from the Windows build log: 7f139627e3b4553ff35c039fb3d137e1943eb1a78e04bd25e38c574fef92a11e.
- Experimental artifact ID 14676728193; size **2,584,697,712 bytes**; ZIP SHA256 2c80d41a5c366a3e1b4d10ece2498b51c4fd35fec1a385a02644707a59352f6c; expires **28 Nov 2026 05:57:56 ICT**. [Download Candidate #1002](https://github.com/niyomse-collab/niyom/actions/runs/44828922189/artifacts/14676728193). This is not a Stable release or shop-PC acceptance.

### Exact-head independent regression
- [Independent Core #1647](https://github.com/niyomse-collab/niyom/actions/runs/44828921821): Windows **1,101 passed / 1 skipped**; Ubuntu **1,099 passed / 3 skipped**; pytest and compileall passed on both.

### Official archive / source-license audit
- [Official Archive Audit #328](https://github.com/niyomse-collab/niyom/actions/runs/44828922176): **32 archive checks + 11 provisioning checks passed**; four official Windows archives were downloaded, hash-checked, safely audited and transactionally provisioned into ephemeral QA storage.
- Archive pins: Real-ESRGAN abc02804e17982a3be33675e4d471e91ea374e65b70167abc09e31acb412802d (observed CI pin; no publisher digest); Waifu2x 7425be94b94e4c8f37a1e433ac0e0100c43790e2c37418f4b65d8235adfbdc87 (published digest); Real-CUGAN c6e08d46c11704b1e3a1ada9ddd591cb5005f52f132136c8633ba25def400e01 (observed CI pin; no publisher digest); Anime4KCPP 82897b0f03ddb88ab3d1affb745baf99506cfe3ceffaeaf73796c6dea4077f19 (published digest).
- Upstream source-license files were retrieved and hashed. all_upstream_digests_pinned=false, model_weights_and_license_certified=false, and license_redistribution_approved=false remain false. Source-license retrieval does not certify model-weight terms or grant redistribution rights. No native binaries/weights were committed.

### Native CLI smoke — classified host limitation, not inference acceptance
- [Native CLI Smoke #444](https://github.com/niyomse-collab/niyom/actions/runs/44828922198): **23 diagnostic tests passed** and official executables were invoked on synthetic RGB and RGBA/ICC/300-DPI images.
- Real-CUGAN and Anime4KCPP produced validated synthetic 2x outputs. Real-ESRGAN was blocked by hosted-runner vkCreateInstance failed -9; Waifu2x had the same Vulkan initialization failure plus 0xC0000005. DXGI found no NVIDIA adapter; physical adapter verification **0/4**; runtime VRAM budget not passed; real_inference_verified=false.
- Workflow SUCCESS means the hosted-runner failures were safely classified and evidence retained, not that four-engine GPU inference passed. Repeat on the shop Windows 11 GTX 1660 Ti before acceptance.

### PR #18 / face protection and safety
- Direct Git Blob SHA comparison from PR #20 base 288dd8501c230a118d9a7e60d2522a2cc7411bcc to PR #20 HEAD b8bf36f confirms **9/9** protected face/GFPGAN files byte-identical: face workflow; face protection, detection, selection and module init; large-face handling; face contract; and its two regression tests.
- PR #20 changed-file list contains **79 paths** and no executable, DLL, archive, model-weight or customer-artwork files. Shared build/spec changes remain guarded to the exact V2.1.1 experimental version; V1 and accepted V2 stable package paths were not changed.
- The 24 MP BigTIFF test remains a frozen V2/libvips streaming QA test, not a four-engine GPU run on a 24 MP shop image. Shop GPU adapter binding, 6 GiB VRAM stress, cancellation under native load, real A/B (people/animals/objects/frames/Thai-English-Chinese lettering/flat colours/gradients/RGBA/faces), Photoshop/MainTop and physical print acceptance remain **NOT CERTIFIED**.
- V2 remains the accepted master. PR #20 and PR #18 remain Draft/unmerged. No V1/V2 Stable modification, merge, release or quality-superiority claim.


## 21 พฤศจิกายน 2569 07:41 ICT — Exact-head Candidate #1003 / HAT compatibility audit

### PR identity and source scope
- PR #20 remains **OPEN / DRAFT / UNMERGED** on `work/v211-four-engine-v2-bridge-20261103`, exact HEAD `69635725ed2b92fc0854d094ecaf33126bb8ce2c`; base remains `288dd8501c230a118d9a7e60d2522a2cc7411bcc`, which is PR #18 HEAD. PR #18 also remains OPEN / DRAFT / UNMERGED.
- Compare from code/test baseline `4f587adf8e1ae37b834cecb0dced3175a0d08c2f` to this HEAD reports **3 documentation-only commits / one changed file**: this status document (+71 lines). No production source, tests, workflow, PyInstaller spec or installer inputs changed after Candidate #1000's code/test baseline.
- PR #20 currently has 79 changed paths. No executable, DLL, native archive, model-weight or customer-artwork file is present in the changed-file list.

### Windows Candidate #1003 — exact HEAD SUCCESS
- [GitHub Actions #1003](https://github.com/niyomse-collab/niyom/actions/runs/44838751293): **SUCCESS, 2/2 jobs** on exact HEAD `69635725`; `bridge-tests` and `windows-v2-candidate` completed successfully.
- The bridge job passed both regression commands: bridge/fusion/coordination **432 passed** and privacy/provisioning/manifest/hash **69 passed**.
- Frozen checks passed: verified-download retry fault injection without network; V2-based experimental build; synthetic Inno Setup consent/success/failure/uninstall lifecycle; frozen V2 import smoke; single-page BigTIFF / streamed libvips QA dispatch; packaged four-engine provisioning `--check-only` without downloads; isolated consented cache cleanup; diagnostic `--help`; read-only shop-runner/provenance script parsing; exact BUILD_PROOF source identity; every installer-slice SHA256; experimental artifact upload. These are package/contract checks, not four native GPU inference.
- Candidate artifact ID `14680599850`; size **2,584,786,557 bytes**; artifact ZIP digest `sha256:2137e3bdbc81bfed17b71c27f4ddb0532e7a4ad2d557723e4f948d74a83142b4`; expires **28 Nov 2569 07:16 ICT**. [Download Candidate #1003](https://github.com/niyomse-collab/niyom/actions/runs/44838751293/artifacts/14680599850). This is an experimental frozen candidate, not a Stable installer or shop-PC acceptance.

### Exact-head Core / official archives / native CLI
- [Independent Core #1649](https://github.com/niyomse-collab/niyom/actions/runs/44838750475): SUCCESS on exact HEAD; Windows **1,101 passed / 1 skipped**, Ubuntu **1,099 passed / 3 skipped**; pytest and compileall passed on both.
- [Official Archive Audit #329](https://github.com/niyomse-collab/niyom/actions/runs/44838750364): SUCCESS; **32 archive checks + 11 provisioning checks**. The four official Windows archives were downloaded, hash-checked, safely audited and transactionally provisioned into ephemeral QA storage. The JSON-only audit artifact is [14679413027](https://github.com/niyomse-collab/niyom/actions/runs/44838750364/artifacts/14679413027). Real-ESRGAN and Real-CUGAN remain observed CI SHA pins without publisher-published digests; source-license retrieval does not certify model-weight terms. `model_weights_and_license_certified=false` and `license_redistribution_approved=false` remain intentional.
- [Native CLI Smoke #445](https://github.com/niyomse-collab/niyom/actions/runs/44838751280): the Windows synthetic diagnostic completed and retained JSON-only report artifact [14680265157](https://github.com/niyomse-collab/niyom/actions/runs/44838751280/artifacts/14680265157). It invokes official binaries only on synthetic RGB and RGBA/ICC/300-DPI images. Its workflow SUCCESS is a classified diagnostic, not four-engine GPU/quality acceptance; the current artifact report must be inspected separately before stating per-engine outcomes. Hosted-runner Vulkan/adapter limitations remain distinct from the owner's earlier shop-PC tests.

### HAT Assist compatibility finding — intentional route retirement in PR #20
- HAT source modules `signprint_ai/v211_hat_assist.py` and `signprint_ai/v211_hat_engine.py` are byte-identical between PR #20 base and HEAD; their files remain in the branch inherited from PR #18.
- However, PR #20's current `signprint_ai/niyomsil_core_adapter.py` removes the `hat` and `v2_hat_assist` selection/creation routes; `signprint_ai/app_v2.py` no longer lists HAT in the photo-model dropdown. New `tests/test_v211_hat_disabled_model_routing.py` explicitly requires these routes to remain unavailable. Therefore HAT Assist is **not active in PR #20**; this is an explicit compatibility decision in the current branch, not an accidental loss caused by the four-engine bridge. HAT remains a separate fifth model/release gate, not one of the four native engines. The manual shop-evidence workflow still records a static HAT reference audit separately.
- The GFPGAN/face path is not retired: the current adapter still calls `self.face_module.apply(...)` and `enforce_requested_face_restoration(...)` after the V2 processing path. Direct Git Blob SHA comparison from PR #20 base to exact HEAD confirms **9/9 byte-identical** protected paths: `.github/workflows/verify-v211-face.yml`, `signprint_ai/face_module/face_protection.py`, `signprint_ai/face_module/detection.py`, `signprint_ai/face_module/selection.py`, `signprint_ai/face_module/__init__.py`, `signprint_ai/large_faces.py`, `signprint_ai/v211_face_contract.py`, `tests/test_v211_face_contract.py`, and `tests/test_v211_large_face_audit.py`.

### Shop acceptance boundary
- The self-hosted workflow requires explicit `workflow_dispatch confirm_shop_gpu=yes` plus the exact installed Candidate source SHA, or an explicit consent marker in a commit message. No such affirmative marker/dispatch was supplied in this run; the shop runner was **not** scheduled or accessed.
- Native 4/4 execution on Windows 11 GTX 1660 Ti, physical adapter binding for every child process, sampled 6 GiB VRAM budget, cancellation under native load, large-image native inference above 18 MP, visual A/B and print acceptance remain **NOT CERTIFIED**. The 24 MP Candidate check is the frozen V2/libvips streaming QA path, not four native engines on a 24 MP shop image.
- Current large-image contract remains disk-backed streaming with tiles/overlap, seam checks, disk reserve, V2-derived alpha, ICC/DPI checks and cancellation. Original source-to-print transforms can be 2x/3x/4x/8x/custom/anisotropic subject to guards; each native engine still performs one 2x pass on the private half-target seed. This is not native 4x/8x inference.
- V2 remains the accepted master. PR #20 and PR #18 remain Draft/unmerged. No V1/V2 Stable modification, merge, release, customer image or native binary/weight commit; no claim that V2.1.1 quality exceeds V2.


## 21 พฤศจิกายน 2569 09:14 ICT — Exact-head Candidate #1004 / latest CI refresh

### PR identity and source scope
- PR #20 remains on work/v211-four-engine-v2-bridge-20261103, exact branch HEAD 1f0174ae3400ec6a27ce2c08d3b7cb6bb43a879b. PR #18 remains the comparison/base for the protected V2/GFPGAN files at 288dd8501c230a118d9a7e60d2522a2cc7411bcc.
- Candidate #1004 checks out and verifies the exact HEAD 1f0174ae3400ec6a27ce2c08d3b7cb6bb43a879b; the Windows build log records V211_EXPECTED_HEAD_SHA and provenance verification for that same SHA.
- Compare from Candidate #1003 code/test baseline 69635725ed2b92fc0854d094ecaf33126bb8ce2c to the current merge-test commit 5deb24405c0ca8ba971172f8476a9e14dcfbcb6f reports one changed path only: this status document (+30 lines). No production source, tests, workflow, PyInstaller spec or installer input changed since Candidate #1003's code/test baseline.

### Windows Candidate #1004 — exact HEAD SUCCESS
- [GitHub Actions #1004](https://github.com/niyomse-collab/niyom/actions/runs/44845770525): SUCCESS, 2/2 jobs (bridge-tests and windows-v2-candidate).
- Bridge/Fusion/coordination: 432 passed; privacy/provisioning/manifest/hash: 69 passed.
- Frozen checks passed: verified-download retry fault injection; experimental V2 build; synthetic Inno Setup consent/success/failure/uninstall lifecycle; frozen V2 imports; single-page BigTIFF/streamed libvips QA; packaged provisioning --check-only without downloads; isolated consented cache cleanup; diagnostic help dispatch; read-only shop-runner diagnostic and provenance verifier; exact BUILD_PROOF/source SHA; every installer-slice SHA256; artifact upload.
- Build version: 2.1.1-beta.1004. Build guard reported v1_files_preserved=true and stable_v2_files_preserved=true.
- Installer SHA256: 093e4d3e0a58e901f07faf6986df5b73bdfbeb37fa89ef84e0c2a24c2c266e98.
- Experimental artifact ID 14684272168; size 2,584,700,994 bytes; ZIP SHA256 75ae75d113ef164d37d823b350ca7e188aacf45ed01bb48f14f998fd5e4fd68b; expires 28 Nov 2026 08:16 ICT. [Download Candidate #1004](https://github.com/niyomse-collab/niyom/actions/runs/44845770525/artifacts/14684272168).
- This remains an experimental frozen-package/provenance pass. It does not certify shop installation, physical GPU inference, visual quality or print output.

### Exact-head Core regression
- [Independent Core #1650](https://github.com/niyomse-collab/niyom/actions/runs/44845770447): SUCCESS. Windows 1,101 passed / 1 skipped; Ubuntu 1,099 passed / 3 skipped; pytest and compileall passed on both platforms.

### Official archive and license-source audit
- [Official Archive Audit #330](https://github.com/niyomse-collab/niyom/actions/runs/44845770494): SUCCESS; 32 archive checks + 11 provisioning checks. All four official Windows archives were downloaded, hash-checked, audited and transactionally provisioned into ephemeral QA storage.
- Real-ESRGAN archive SHA256 abc02804e17982a3be33675e4d471e91ea374e65b70167abc09e31acb412802d and Real-CUGAN c6e08d46c11704b1e3a1ada9ddd591cb5005f52f132136c8633ba25def400e01 remain observed CI pins without publisher digests. Waifu2x and Anime4KCPP archive hashes match published digests.
- Upstream source-license documents were retrieved and hashed. all_upstream_digests_pinned=false, model_weights_and_license_certified=false, and license_redistribution_approved=false remain false. Source-license retrieval does not certify release-specific model-weight terms or redistribution rights.

### Native CLI Smoke — diagnostic only
- [Native CLI Smoke #446](https://github.com/niyomse-collab/niyom/actions/runs/44845770441) completed successfully as a classified synthetic diagnostic, not GPU acceptance.
- Real-CUGAN and Anime4KCPP each exited successfully and produced validated 2x outputs for synthetic RGB and RGBA/ICC/300-DPI inputs. Runtime adapter use was not verified.
- Real-ESRGAN was blocked by hosted-runner Vulkan initialization (vkCreateInstance failed -9). Waifu2x encountered the same Vulkan limitation plus access violation 0xC0000005. NVIDIA DXGI adapter was absent; physical adapter verification 0/4; VRAM guard did not run; real_inference_verified=false.
- The Actions SUCCESS result means failures were classified and evidence retained. It does not mean four-engine GPU inference passed.

### Styled-effect protection audit
- The V2.1.1 UI provides a manual per-image ROI selector for gradient/stroke/glow/shadow text and logos. Only explicitly selected regions are copied from the V2 raster as bit-preserved protected regions.
- No automatic classifier guarantees detection of every styled-effect region when no ROI is selected. The edge/flat-colour/gradient guards are additional safeguards, not a universal substitute for selecting and visually checking complex effects. Keep every four-engine result as a separate QA sidecar; do not treat it as an accepted print master without A/B review.

### V2/GFPGAN preservation and acceptance boundary
- Direct Git Blob SHA comparison of all nine protected face/GFPGAN paths between current PR #20 HEAD and PR #20 base/PR #18 head remains 9/9 byte-identical.
- HAT Assist source files remain present, but its route is intentionally disabled in PR #20; HAT is not one of the four native engines and is not active in this bridge.
- No affirmative exact-head consent for the shop self-hosted GPU runner was supplied; the shop PC was not scheduled or accessed. Native GPU 4/4 on Windows 11 GTX 1660 Ti, per-process adapter binding, 6 GiB VRAM stress, cancellation under native load, >18 MP native inference, visual A/B, Photoshop/MainTop and physical print acceptance remain NOT CERTIFIED.
- PR #20 and PR #18 remain Draft/unmerged. V2 remains the accepted master. No V1/V2 Stable edits, merge, release, customer artwork, native binaries or model weights committed; no claim that V2.1.1 quality exceeds V2.


## 21 พฤศจิกายน 2569 09:55 ICT — Exact-head Candidate #1005 / current-run verification

### PR identity and scope
- PR #20 remains **OPEN / DRAFT / UNMERGED** on `work/v211-four-engine-v2-bridge-20261103`; exact current HEAD at this check: `c8a3e6d0b9db76c59393d9edbcbe2831759e4bc7`.
- PR #18 remains **OPEN / DRAFT / UNMERGED** and its head `288dd8501c230a118d9a7e60d2522a2cc7411bcc` is PR #20's base.
- The documentation-only update below is not part of the Candidate #1005 binary. Candidate #1005 itself was built from the exact HEAD `c8a3e6d0b9db76c59393d9edbcbe2831759e4bc7`; no source/test/spec/installer changes followed that SHA in this report.

### Windows Candidate #1005 — exact HEAD SUCCESS
- [GitHub Actions #1005](https://github.com/niyomse-collab/niyom/actions/runs/44855154694): **SUCCESS, 2/2 jobs** (`bridge-tests`, `windows-v2-candidate`).
- Bridge/Fusion/coordination: **432 passed**. Privacy/provisioning/manifest/hash: **69 passed**.
- Frozen checks passed: verified-download retry fault injection; V2-based experimental build; synthetic Inno Setup consent/uninstall lifecycle; frozen V2 imports; single-page BigTIFF/streamed libvips QA; packaged provisioning `--check-only` without downloads; isolated consented cache cleanup; diagnostic help dispatch; read-only shop-runner and provenance-script parsing; exact BUILD_PROOF/source SHA; every installer-slice SHA256; experimental artifact upload.
- Build version: **2.1.1-beta.1005**. Workspace guard reported `v1_files_preserved=true` and `stable_v2_files_preserved=true`.
- Installer SHA256: `ccf654172d71550cebc410518bde4d784c67ff220251670c9b817fb852d04fdc`.
- Experimental artifact ID **14688615892**; size **2,584,774,375 bytes**; GitHub artifact ZIP SHA256 `f9148f5902d3ace094f5036a413267b44d6a31874653a0da12c87c17e5838aa6`; expires **28 พ.ย. 2569 09:50:45 ICT**. [Download Candidate #1005](https://github.com/niyomse-collab/niyom/actions/runs/44855154694/artifacts/14688615892).
- Non-fatal PyInstaller warnings remain for `pycparser.lextab`, `pycparser.yacctab`, `scipy.special._cdflib`, driver-provided `nvcuda.dll`, and optional Numba `tbb12.dll`. Frozen import/provisioning/diagnostic checks passed. Do not bundle a guessed CUDA driver DLL or optional TBB binary; verify actual runtime relevance on the shop PC.

### Exact-head Independent Core regression
- [Independent Core #1653](https://github.com/niyomse-collab/niyom/actions/runs/44855154686): **SUCCESS** on exact HEAD. Windows **1,101 passed / 1 skipped**; Ubuntu **1,099 passed / 3 skipped**; pytest and compileall passed on both.

### Official archive/provisioning audit
- [Official Archive Audit #331](https://github.com/niyomse-collab/niyom/actions/runs/44855154669): **SUCCESS**; 32 archive checks and 11 provisioning checks passed. All four official Windows archives were downloaded, audited, SHA256-checked, and transactionally provisioned only into ephemeral QA storage.
- Real-ESRGAN archive SHA256 remains observed CI pin `abc02804e17982a3be33675e4d471e91ea374e65b70167abc09e31acb412802d`; Real-CUGAN remains observed CI pin `c6e08d46c11704b1e3a1ada9ddd591cb5005f52f132136c8633ba25def400e01`. Waifu2x and Anime4KCPP match published archive digests.
- Upstream license documents were retrieved and hashed, but `all_upstream_digests_pinned=false`, `model_weights_and_license_certified=false`, and `license_redistribution_approved=false` remain false. Archive provenance and source-license retrieval do not certify every model weight or approve redistribution.

### Native CLI Smoke #447 — diagnostic only, NOT 4/4 acceptance
- [Native CLI Smoke #447](https://github.com/niyomse-collab/niyom/actions/runs/44855154713) completed with workflow conclusion SUCCESS because the known hosted-runner limitations were classified and recorded; it is **not** a four-engine GPU pass.
- On synthetic RGB and RGBA/ICC/300-DPI inputs, Real-CUGAN and Anime4KCPP each produced validated native 2x outputs. Their physical GPU adapter use was not verified.
- Real-ESRGAN failed Vulkan initialization (`vkCreateInstance failed -9`). Waifu2x failed the same Vulkan initialization and also returned access violation `0xC0000005`.
- Each synthetic case reported `completed_engine_count=2`; `candidate_output_validation_complete=false`, `real_inference_verified=false`, `quality_improvement_verified=false`. NVIDIA DXGI adapter was absent, physical adapter verification was **0/4**, and runtime VRAM telemetry was unavailable. This is consistent with a hosted runner without a usable Vulkan/NVIDIA adapter; it does not negate the user's prior GTX 1660 Ti shop-PC tests, but it cannot replace a current exact-candidate shop test.

### PR #18 / GFPGAN preservation recheck
- Direct Git Blob SHA comparison from PR #20 base / PR #18 head `288dd8501c230a118d9a7e60d2522a2cc7411bcc` to exact PR #20 HEAD `c8a3e6d0b9db76c59393d9edbcbe2831759e4bc7` confirms **9/9 byte-identical** protected face/GFPGAN paths:
  - `.github/workflows/verify-v211-face.yml`
  - `signprint_ai/face_module/face_protection.py`
  - `signprint_ai/face_module/detection.py`
  - `signprint_ai/face_module/selection.py`
  - `signprint_ai/face_module/__init__.py`
  - `signprint_ai/large_faces.py`
  - `signprint_ai/v211_face_contract.py`
  - `tests/test_v211_face_contract.py`
  - `tests/test_v211_large_face_audit.py`
- Shared integration files such as `app_v2.py`, `large_image.py`, and `niyomsil_core_adapter.py` are changed by PR #20 to append the four-engine QA stage after durable V2 output. They are not part of the 9-file byte-identity claim; their face-safety behavior is covered by the adapter autorun regressions, including full V2-only preservation when applied GFPGAN faces cannot be mapped to protected ROIs.
- HAT source files remain present, but PR #20 intentionally disables the HAT/HAT Assist selection route; this remains a separate compatibility difference from PR #18, not one of the four native engines.

### Acceptance boundary
- No exact-head affirmative consent for the shop self-hosted GPU runner was supplied; no shop runner or local shop PC was accessed.
- Native 4/4 inference on Windows 11 GTX 1660 Ti, per-process GPU adapter binding, peak 6 GiB VRAM stress, cancellation under native load, >18 MP four-engine inference, real portrait/animal/object/Thai-English-Chinese text/gradient/RGBA A/B, Photoshop/MainTop and physical print acceptance remain **NOT CERTIFIED**.
- V2 remains the accepted master. PR #20 and PR #18 remain Draft/unmerged. No V1/V2 Stable edits, merge, release, customer artwork, native binaries or model weights committed; no claim that V2.1.1 quality exceeds V2.


## 21 พฤศจิกายน 2569 11:02 ICT — Exact-head Candidate #1006 completed

### PR identity and exact-head CI
- PR #20 remains OPEN / DRAFT / UNMERGED on `work/v211-four-engine-v2-bridge-20261103`, exact HEAD `8ac897eff7d409bde3c910a173aa9fab0600f6be`. PR #18 remains OPEN / DRAFT / UNMERGED; its head/base for PR #20 is `288dd8501c230a118d9a7e60d2522a2cc7411bcc`.
- Exact-head Windows Candidate #1006: [Actions #1006](https://github.com/niyomse-collab/niyom/actions/runs/44858743424), SUCCESS 2/2 jobs (`bridge-tests`, `windows-v2-candidate`). Bridge/Fusion/Coordination 432 passed; Privacy/Provisioning/Hash 69 passed.
- Frozen checks passed: synthetic verified-download retry fault injection; V2-based experimental build; synthetic Inno Setup consent/success/failure/uninstall lifecycle; frozen V2 imports; single-page BigTIFF / streamed libvips QA; packaged provisioning `--check-only` without downloads; isolated consented model-cache cleanup; packaged diagnostic `--help`; read-only shop-runner diagnostic parsing; provenance verifier syntax; exact BUILD_PROOF/source SHA; every installer-slice SHA256; experimental artifact upload.
- Build version `2.1.1-beta.1006`. Workspace guard reported `v1_files_preserved=true`, `stable_v2_files_preserved=true`; provenance reported `accepted_v2_sha256_unchanged=true`.
- Installer SHA256: `e1f0a904edaaa2814ae968dad9c0b675fcaf0e9d5f3efdd80efd40c6dc810324`.
- Artifact ID **14689729206**, size **2,584,774,538 bytes**, ZIP SHA256 `2832e77595bb877daae5242e0d462792ecab6682bf09141e936956463d0b95a4`; expires **28 พ.ย. 2569 10:31:13 ICT**. [Download Candidate #1006](https://github.com/niyomse-collab/niyom/actions/runs/44858743424/artifacts/14689729206).
- Candidate #1006 proves frozen build/provenance and synthetic installer lifecycle only. It does not certify interactive install/uninstall, native inference or print output on the shop PC.

### Exact-head Core regression
- [Independent Core #1655](https://github.com/niyomse-collab/niyom/actions/runs/44858743473): SUCCESS on exact HEAD. Windows **1,101 passed / 1 skipped**; Ubuntu **1,099 passed / 3 skipped**; pytest and compileall passed on both.

### Exact-head official archive/provisioning audit
- [Official Archive Audit #332](https://github.com/niyomse-collab/niyom/actions/runs/44858743476): SUCCESS; **32 archive checks + 11 provisioning checks**. All four official Windows archives were downloaded, hash-checked, safely audited, and transactionally provisioned into ephemeral QA storage; the verified manifest contained exactly `real_esrgan`, `waifu2x`, `real_cugan`, and `anime4k`.
- Archive SHA256: Real-ESRGAN `abc02804e17982a3be33675e4d471e91ea374e65b70167abc09e31acb412802d` (observed CI pin; no publisher digest); Waifu2x `7425be94b94e4c8f37a1e433ac0e0100c43790e2c37418f4b65d8235adfbdc87` (published digest); Real-CUGAN `c6e08d46c11704b1e3a1ada9ddd591cb5005f52f132136c8633ba25def400e01` (observed CI pin; no publisher digest); Anime4KCPP `82897b0f03ddb88ab3d1affb745baf99506cfe3ceffaeaf73796c6dea4077f19` (published digest).
- Upstream license documents were retrieved and hashed. `all_upstream_digests_pinned=false`, `model_weights_and_license_certified=false`, and `license_redistribution_approved=false` remain false. Archive audit and source-license retrieval do not certify every release-specific model-weight term or grant redistribution rights. [Audit report artifact 14689165576](https://github.com/niyomse-collab/niyom/actions/runs/44858743476/artifacts/14689165576).

### Exact-head Native CLI Smoke #448 — diagnostic only
- [Native CLI Smoke #448](https://github.com/niyomse-collab/niyom/actions/runs/44858743429) completed with workflow conclusion SUCCESS because known hosted-runner Vulkan limitations were explicitly classified; it is **not** four-engine GPU acceptance.
- On synthetic RGB and RGBA/ICC/300-DPI inputs, Real-CUGAN and Anime4KCPP each exited successfully and produced validated native 2x outputs. Real-ESRGAN failed Vulkan initialization (`vkCreateInstance failed -9`); Waifu2x hit the same Vulkan failure plus access violation `0xC0000005`.
- Both synthetic cases reported `completed_engine_count=2`, `candidate_output_validation_complete=false`, `real_inference_verified=false`, and `quality_improvement_verified=false`. NVIDIA DXGI adapter was absent; physical adapter verification **0/4**; NVML telemetry unavailable; runtime VRAM guard was not enabled. This does not negate the user's prior shop-PC tests, but it cannot replace a current exact-candidate test on the GTX 1660 Ti.
- JSON diagnostic artifact ID **14689255469**, size **3,459 bytes**, ZIP SHA256 `389a5e2dbe5ea90a188cdd04b55a73da8750b0cd60e7b93f54999431d6808c67`; [download from Actions](https://github.com/niyomse-collab/niyom/actions/runs/44858743429/artifacts/14689255469).

### PR #18 / GFPGAN preservation — direct Blob SHA recheck
- Fetched each protected file at PR #20 base / PR #18 head `288dd8501c230a118d9a7e60d2522a2cc7411bcc` and current PR #20 HEAD `8ac897e`; **9/9 Blob SHAs are identical**: face workflow; `face_module/face_protection.py`, `detection.py`, `selection.py`, `__init__.py`; `large_faces.py`; `v211_face_contract.py`; and both face-contract / large-face audit tests.
- PR #20 changes shared integration files `app_v2.py`, `large_image.py`, and `niyomsil_core_adapter.py` to append the optional QA stage after durable V2 output. These are not part of the 9-file byte-identity claim; face-safety regressions preserve the complete V2 output when face/effect ROIs cannot be mapped. HAT Assist source remains in the PR #18 base, but the HAT execution route is intentionally disabled in PR #20 and remains a separate compatibility difference.

### Large-image, scale, VRAM and cancellation — implementation vs acceptance
- Source inspection confirms the bridge selects `prepare_native_2x_inputs_streamed` above 18 MP; libvips converts supported RGB/RGBA source/V2 rasters to private PNG seed/reference files. `tools/v211_four_engine_tiled_inference.py` uses **512 px tiles / 32 px overlap**, validates adjacent overlap seams, reserves disk space for all candidates/fusion, and checks cancellation between tiles. The native runner requires an accepted V2 reference, matching RGB/RGBA and ICC, and a single exact 2x native pass from the half-target seed.
- Runtime policy in source sets a **6,144 MiB device-wide VRAM budget**, **512 MiB reserve**, and a **2,048 MiB minimum free-VRAM prelaunch check**, with per-process adapter/telemetry verification required before a candidate can be published. These are code-level guardrails, not measured shop-PC stress results.
- Overall source-to-print scale can be 2x/3x/4x/custom because the half-target seed is derived from the accepted V2 canvas; each external engine still performs only one native 2x pass. This is **not** native 4x or multi-pass 8x AI. Large auxiliary jobs remain restricted to supported 8-bit RGB/RGBA inputs and streamed PNG paths; CMYK, multipage TIFF, unsupported depths, and unsupported formats stay V2-only.
- The >18 MP tiled path, 4x overall geometry, 6 GiB policy and cancellation have CI/source coverage but remain **NOT CERTIFIED under real four-engine load on the shop GTX 1660 Ti**.

### PyInstaller warning triage
- Candidate #1006 still emits non-fatal warnings for missing `pycparser.lextab`, `pycparser.yacctab`, `scipy.special._cdflib`, driver-provided `nvcuda.dll`, and `tbb12.dll` referenced by Numba's TBB ufunc extension. The frozen V2 imports, provisioning dispatch, diagnostic dispatch, and installer provenance/slice checks all passed.
- Do not bundle a guessed `nvcuda.dll`: it is supplied by the installed NVIDIA driver. Do not bundle a random `tbb12.dll` without proving that the app selects Numba's TBB threading layer. The generated pycparser tables and SciPy submodule warnings are not frozen-import failures in this run, but full runtime validation on the shop PC is still required. No warning was hidden or treated as a GPU acceptance result.

### Acceptance boundary
- No affirmative exact-head consent for the shop self-hosted GPU runner was supplied; no shop runner or local shop PC was accessed.
- Native 4/4 inference on Windows 11 GTX 1660 Ti, per-process adapter binding, 6 GiB stress/cancellation under native load, >18 MP native processing, visual A/B across people/animals/objects/Thai-English-Chinese lettering/gradients/RGBA, Photoshop/MainTop and physical print acceptance remain **NOT CERTIFIED**.
- PR #20 and PR #18 remain OPEN/DRAFT/UNMERGED. V2 remains the accepted master. No V1/V2 Stable changes, merge, release, customer artwork, native binaries or model weights committed; no quality-superiority claim.


## 21 พฤศจิกายน 2569 12:25 ICT — Exact-head Candidate #1007 / CI refresh

### PR identity and source delta
- PR #20 remains **OPEN / DRAFT / UNMERGED** on `work/v211-four-engine-v2-bridge-20261103`; exact PR HEAD at this check: `692c787e9ea17719da4d27c3b422ae49fd2d6269`.
- PR #18 remains **OPEN / DRAFT / UNMERGED** at base/head `288dd8501c230a118d9a7e60d2522a2cc7411bcc`.
- Compare from the previous code/test HEAD `8ac897eff7d409bde3c910a173aa9fab0600f6be` to PR HEAD `692c787e9ea17719da4d27c3b422ae49fd2d6269` shows exactly **one documentation file** changed: this status document (+45 / -0). Production source, tests, PyInstaller spec, workflows and installer inputs are unchanged. Candidate #1007 therefore rebuilds the same production/test baseline with exact current PR provenance.

### Windows Candidate #1007 — SUCCESS 2/2
- [Actions #1007](https://github.com/niyomse-collab/niyom/actions/runs/44864298654): both `bridge-tests` and `windows-v2-candidate` completed SUCCESS on exact PR HEAD `692c787`.
- Bridge/Fusion/coordination: **432 passed**; privacy/provisioning/hash: **69 passed**.
- Frozen checks passed: V2 imports, synthetic Inno Setup no-consent/affirmative-consent/failure/uninstall lifecycle, single-page BigTIFF/libvips QA dispatch, packaged four-engine provisioning `--check-only` without downloads, isolated model-cache cleanup, diagnostic help dispatch, PowerShell syntax, exact BUILD_PROOF/source SHA, every installer-slice SHA256 and artifact upload.
- Candidate version: `2.1.1-beta.1007`. Workspace guard: `v1_files_preserved=true`, `stable_v2_files_preserved=true`; provenance: `accepted_v2_sha256_unchanged=true`.
- Installer SHA256: `7243134470eac4e79ed4f1e5f045d4bb377d33e2af2a2398f1beaa71a831a3e4`.
- Artifact ID **14691916745**, size **2,584,752,504 bytes**, ZIP SHA256 `e73646ce66e777bd7073181c8aaf300f56ad6ba92cebc748cba37b5d0b0f7cb3`; expires **28 พ.ย. 2569 11:30 ICT**. [Download Candidate #1007](https://github.com/niyomse-collab/niyom/actions/runs/44864298654/artifacts/14691916745).
- This remains an experimental frozen-package/provenance pass, not interactive shop installation, native GPU, visual-quality or print acceptance.

### Exact-head regression and provenance
- [Independent Core #1657](https://github.com/niyomse-collab/niyom/actions/runs/44864298691): SUCCESS. Windows **1,101 passed / 1 skipped**; Ubuntu **1,099 passed / 3 skipped**; pytest and compileall passed on both platforms.
- [Official Archive Audit #333](https://github.com/niyomse-collab/niyom/actions/runs/44864298671): SUCCESS; **32 archive checks + 11 provisioning checks**. All four official archives were downloaded, hash-audited and transactionally provisioned into ephemeral QA storage; manifest validation reported exactly `real_esrgan`, `waifu2x`, `real_cugan`, `anime4k`.
- Archive SHA256: Real-ESRGAN `abc02804e17982a3be33675e4d471e91ea374e65b70167abc09e31acb412802d` (observed CI pin; no publisher digest); Waifu2x `7425be94b94e4c8f37a1e433ac0e0100c43790e2c37418f4b65d8235adfbdc87` (published digest); Real-CUGAN `c6e08d46c11704b1e3a1ada9ddd591cb5005f52f132136c8633ba25def400e01` (observed CI pin; no publisher digest); Anime4KCPP `82897b0f03ddb88ab3d1affb745baf99506cfe3ceffaeaf73796c6dea4077f19` (published digest).
- All upstream license documents were retrieved and hashed. `all_upstream_digests_pinned=false`, `model_weights_and_license_certified=false`, and `license_redistribution_approved=false` remain false. Do not bundle or redistribute native binaries/weights on this evidence.

### Native CLI Smoke #449 — diagnostic only
- [Actions #449](https://github.com/niyomse-collab/niyom/actions/runs/44864298718) completed SUCCESS because known hosted-runner limitations were explicitly classified; this is **not** four-engine GPU acceptance.
- On synthetic RGB and RGBA/ICC/300-DPI inputs, Real-CUGAN and Anime4KCPP each produced validated native 2x outputs. Real-ESRGAN failed Vulkan initialization (`vkCreateInstance failed -9`); Waifu2x encountered the same Vulkan failure plus access violation `0xC0000005`.
- Each case reported `completed_engine_count=2`; Real-CUGAN/Anime4K outputs passed synthetic validation, while Real-ESRGAN/Waifu2x did not. NVIDIA adapter verification was **0/4**, NVML/VRAM telemetry was unavailable, runtime VRAM guard was not enabled, `real_inference_verified=false`, and `quality_improvement_verified=false`. The hosted-runner failure does not override the user's earlier Windows 11 GTX 1660 Ti experience, but it cannot certify the shop PC either.
- JSON-only diagnostic artifact ID **14690922737**, size **3,472 bytes**; [download report](https://github.com/niyomse-collab/niyom/actions/runs/44864298718/artifacts/14690922737).

### GFPGAN / fusion / large-image acceptance boundary
- PR #20's compare against its PR #18 base contains no changes to the protected GFPGAN/face modules, large-face handler, face contract or their protected tests/workflow. The previously verified **9/9 byte-identical** face-protection set remains applicable because the only delta since the prior exact-head source audit is documentation.
- The four-engine fusion implementation is wired after all four candidate outputs and is guarded by per-process runtime adapter evidence; fusion reports `quality_certified=false` and writes a separate experimental QA PNG, never over the accepted V2 raster. Missing/unmapped face or styled-effect protection stays V2-only.
- The >18 MP route remains disk-backed (libvips, 512 px tiles, 32 px overlap, seam checks, disk reserve and cancellation). Source-to-print custom scales use one native 2x pass on a half-target seed; this is not native 4x/8x or multi-pass AI. The 6,144 MiB device-wide budget, 512 MiB reserve and 2,048 MiB prelaunch free-VRAM minimum are source-level guardrails, not measured shop-PC stress results.
- No affirmative exact-head shop-GPU consent was supplied; no self-hosted runner or shop PC was accessed. Native 4/4 on GTX 1660 Ti, per-process adapter binding, 6 GiB stress/cancellation, >18 MP native inference, visual A/B across people/animals/objects/Thai-English-Chinese lettering/gradients/RGBA, Photoshop/MainTop and physical print remain **NOT CERTIFIED**.
- PR #20 and PR #18 remain OPEN/DRAFT/UNMERGED. V2 remains accepted master. No V1/V2 Stable edits, merge, release, customer images or native binaries/weights committed; no quality-superiority claim.


## 21 พฤศจิกายน 2569 13:13 ICT — Exact-head Candidate #1008 / Core #1659 / Archive #334

### PR identity and exact source scope
- PR #20 remains **OPEN / DRAFT / UNMERGED** on `work/v211-four-engine-v2-bridge-20261103`, exact head `26f0910c15fcba79a875aa13567c974ba91e0572`, base branch `feature/v2.1.1-super-ai` at `288dd8501c230a118d9a7e60d2522a2cc7411bcc`.
- PR #18 remains **OPEN / DRAFT / UNMERGED**; its head is the exact base SHA of PR #20. PR #18's own base is `fix/v21-real-quality` at `104b380b7e7283471c41643216311ff2c4661c6c`.
- Compare from code/test HEAD `8ac897eff7d409bde3c910a173aa9fab0600f6be` to current PR head `26f0910c15fcba79a875aa13567c974ba91e0572` reports two documentation commits and exactly one changed file: this status document (**+81 / -0**). No production source, tests, PyInstaller spec, workflow, or installer inputs changed after the code/test HEAD.
- Candidate #1008 was triggered by exact PR head `26f0910`; GitHub Actions checked out merge ref `f63d36b16ea9918b0d7803c4618e5f32fb9dfc3f` (PR head merged into base for the test run).

### Windows Candidate #1008 — SUCCESS 2/2
- [Actions #1008](https://github.com/niyomse-collab/niyom/actions/runs/44871202982): both `bridge-tests` and `windows-v2-candidate` completed **SUCCESS**.
- Bridge/Fusion/coordination: **432 passed**; privacy/provisioning/manifest/hash: **69 passed**.
- Frozen candidate steps passed: V2 import smoke; synthetic Inno Setup no-consent/explicit-consent/failure/uninstall lifecycle; single-page BigTIFF and streamed libvips QA; packaged provisioning `--check-only` without downloads; isolated consented cache cleanup and cross-profile rejection; packaged diagnostic dispatch; read-only shop-runner/provenance parsing; BUILD_PROOF and installer-slice SHA256 verification; artifact upload.
- Build version: **2.1.1-beta.1008**. Workspace guard: `v1_files_preserved=true`, `stable_v2_files_preserved=true`; provenance log: `accepted_v2_sha256_unchanged=true`.
- Installer SHA256: `dad734919a74f98e95dabfaca2dc6f8df91759ea6a09f98a0b575d662c9ead62`.
- Experimental artifact ID **14695146905**, size **2,584,749,141 bytes**; artifact ZIP SHA256 `797c4a108447b86abeccc0bb4e79deed525711a6bc9481369bfb836b0f24bde9`; expires **28 Nov 2026 13:03 ICT**. [Download Candidate #1008](https://github.com/niyomse-collab/niyom/actions/runs/44871202982/artifacts/14695146905).
- PyInstaller emitted non-fatal warnings for missing `expecttest` (torch testing-only submodule), `pycparser.lextab/yacctab`, `scipy.special._cdflib`, driver-provided `nvcuda.dll`, and `tbb12.dll` referenced by Numba's optional TBB extension. Frozen import/provisioning/diagnostic and installer provenance checks passed. Do not bundle a guessed NVIDIA driver DLL or random TBB runtime; runtime relevance still needs shop-PC validation.

### Independent Core #1659 — SUCCESS on both platforms
- [Actions #1659](https://github.com/niyomse-collab/niyom/actions/runs/44871203042): Windows **1,101 passed / 1 skipped**; Ubuntu **1,099 passed / 3 skipped**; pytest and compileall passed on both.

### Official Archive Audit #334 — SUCCESS
- [Actions #334](https://github.com/niyomse-collab/niyom/actions/runs/44871202988): **32 archive checks + 11 provisioning checks** passed. All four official Windows archives were downloaded, audited, SHA256-checked, and transactionally provisioned into ephemeral QA storage; the verified manifest contains `real_esrgan`, `waifu2x`, `real_cugan`, and `anime4k`.
- Real-ESRGAN and Real-CUGAN still use observed CI archive pins without publisher-provided archive digests; Waifu2x and Anime4KCPP match published digests. All retrieved upstream license documents were hashed, but `all_upstream_digests_pinned=false`, `model_weights_and_license_certified=false`, and `license_redistribution_approved=false` remain false. This is provenance evidence, not permission to redistribute weights.

### Native CLI Smoke #450 — classified diagnostic only
- [Actions #450](https://github.com/niyomse-collab/niyom/actions/runs/44871202999) completed **SUCCESS as a classified diagnostic**, not as 4/4 GPU or quality acceptance. The workflow downloaded and verified the official archives, then invoked the official binaries on synthetic RGB and RGBA/ICC/300-DPI PNGs.
- Real-CUGAN and Anime4KCPP reported validated native 2x synthetic outputs; adapter use was not verified. Real-ESRGAN failed Vulkan initialization (`vkCreateInstance failed -9`); Waifu2x had the same Vulkan failure plus access violation `0xC0000005`.
- Both cases report `completed_engine_count=2`, `candidate_output_validation_complete=false`, `real_inference_verified=false`, and `quality_improvement_verified=false`. NVIDIA adapter verification is **0/4**; runtime VRAM guard/telemetry was not enabled or measured. The two classified hosted-runner failures explain the diagnostic conclusion and do not establish shop-GPU failure or success.
- JSON-only evidence artifact ID **14693584361**, size **3,430 bytes**, ZIP SHA256 `43f4db88ccd7de5d77b031f59a35660fadd65bee5f32b34ac53feca9a2ed4276`. [Download diagnostic report](https://github.com/niyomse-collab/niyom/actions/runs/44871202999/artifacts/14693584361).

### PR #18 / GFPGAN preservation — direct current-head recheck
- Compared Git Blob SHA for each protected file at PR #20 base `288dd8501c230a118d9a7e60d2522a2cc7411bcc` against current PR #20 head `26f0910c15fcba79a875aa13567c974ba91e0572`. Result: **9/9 byte-identical**:
  - `.github/workflows/verify-v211-face.yml`
  - `signprint_ai/face_module/face_protection.py`
  - `signprint_ai/face_module/detection.py`
  - `signprint_ai/face_module/selection.py`
  - `signprint_ai/face_module/__init__.py`
  - `signprint_ai/large_faces.py`
  - `signprint_ai/v211_face_contract.py`
  - `tests/test_v211_face_contract.py`
  - `tests/test_v211_large_face_audit.py`
- PR #18 itself contains its earlier HAT Assist / face-safety work; PR #20 intentionally disables the HAT execution route as a separate compatibility choice. This is not a GFPGAN file modification.

### Acceptance boundary
- The successful frozen candidate validates packaging, dispatch, consent/uninstall synthetic fixtures, source provenance and installer slices. It does **not** certify interactive install/uninstall on the shop PC, GPU adapter binding, 4/4 inference on the GTX 1660 Ti, 6 GiB VRAM stress, cancellation under native load, >18 MP native inference, visual A/B, Photoshop/MainTop or physical print quality.
- The >18 MP path remains disk-backed with 512 px tiles, 32 px overlap, seam checks, disk reserve and cancellation; source-level GPU policy remains 6,144 MiB budget / 512 MiB reserve / 2,048 MiB minimum free prelaunch VRAM. These are guardrails, not measured stress results. Overall 4x print geometry still uses a half-target seed plus one native 2x pass; it is not native 4x or multipass AI.
- No exact-head affirmative consent for a shop self-hosted GPU run was supplied; no shop PC/runner was accessed. PR #20 and PR #18 remain Draft/unmerged. V2 remains accepted master. No V1/V2 Stable edits, merge, release, customer images, native binaries or model weights committed; no quality-superiority claim.


## 21 พฤศจิกายน 2569 14:25 ICT — Exact-head Candidate #1009 / Core #1661 / Archive #335

### PR identity and source scope
- PR #20 remains **OPEN / DRAFT / UNMERGED** on `work/v211-four-engine-v2-bridge-20261103`, exact head `940ca3f02982bc9ae711b28d403e2c191ab9573a`, base `feature/v2.1.1-super-ai` at `288dd8501c230a118d9a7e60d2522a2cc7411bcc`.
- PR #18 remains **OPEN / DRAFT / UNMERGED**, head `288dd8501c230a118d9a7e60d2522a2cc7411bcc`, base `fix/v21-real-quality` at `104b380b7e7283471c41643216311ff2c4661c6c`.
- Compare from code/test HEAD `8ac897eff7d409bde3c910a173aa9fab0600f6be` to current PR head `940ca3f02982bc9ae711b28d403e2c191ab9573a`: **3 commits, one changed file only**, this status document (**+130 / -0**). No Production Source, tests, workflow, PyInstaller spec or installer inputs changed after the code/test HEAD.
- Current PR has 79 changed files relative to its base. No merge/release action was taken.

### Windows Candidate #1009 — SUCCESS 2/2
- [GitHub Actions #1009](https://github.com/niyomse-collab/niyom/actions/runs/44874710218), exact PR HEAD `940ca3f`: both `bridge-tests` and `windows-v2-candidate` completed **SUCCESS**.
- Bridge/Fusion/coordination tests: **432 passed**. Privacy/provisioning/hash tests: **69 passed**.
- Frozen checks passed: V2 imports; synthetic Inno Setup consent/failure/uninstall lifecycle; single-page BigTIFF and streamed libvips QA; packaged provisioning `--check-only` without downloads; isolated consented cache cleanup and cross-profile rejection; diagnostic help dispatch; read-only shop-runner diagnostic parsing; BUILD_PROOF/source provenance and every installer-slice SHA256; artifact upload.
- Build log explicitly reports `icc_preserved=true`, `dpi_preserved=true`, and `accepted_v2_sha256_unchanged=true`. This is fixture/provenance evidence, not a shop-PC image-quality or print test.
- Installer SHA256: `2fa089c1705f06997ab90db5dec713c86b04fb243bdc33009c0061d0213a5e61`.
- Experimental artifact ID **14696098806**, size **2,584,795,201 bytes**, ZIP SHA256 `b2f8c25da75bb035898ca80c9822642a762ad61e152da7cc39851a99f0a56be2`; expires **28 Nov 2026 13:48:36 ICT**. [Download Candidate #1009](https://github.com/niyomse-collab/niyom/actions/runs/44874710218/artifacts/14696098806).
- Non-fatal PyInstaller warnings remain: missing `expecttest`, generated `pycparser.lextab/yacctab`, `scipy.special._cdflib`, driver-provided `nvcuda.dll`, and optional Numba `tbb12.dll`. Do not bundle guessed driver/runtime DLLs; verify runtime relevance on the shop PC.

### Independent Core #1661 — SUCCESS on Windows and Ubuntu
- [Actions #1661](https://github.com/niyomse-collab/niyom/actions/runs/44874710307): Windows **1,101 passed / 1 skipped**; Ubuntu **1,099 passed / 3 skipped**. Pytest and compileall passed on both.

### Official Archive Audit #335 — SUCCESS, with explicit license boundary
- [Actions #335](https://github.com/niyomse-collab/niyom/actions/runs/44874710193): **32 archive/audit checks** and **11 provisioning tests** passed. Four official Windows archives were downloaded, hash-audited and transactionally provisioned into ephemeral QA storage. Manifest loaded exactly `real_esrgan`, `waifu2x`, `real_cugan`, `anime4k`.
- Archive SHA256 values remain: Real-ESRGAN `abc02804e17982a3be33675e4d471e91ea374e65b70167abc09e31acb412802d` (observed CI pin, no publisher digest); Waifu2x `7425be94b94e4c8f37a1e433ac0e0100c43790e2c37418f4b65d8235adfbdc87` (published digest); Real-CUGAN `c6e08d46c11704b1e3a1ada9ddd591cb5005f52f132136c8633ba25def400e01` (observed CI pin, no publisher digest); Anime4KCPP `82897b0f03ddb88ab3d1affb745baf99506cfe3ceffaeaf73796c6dea4077f19` (published digest).
- All retrieved upstream license documents were hashed. Audit flags remain `all_upstream_digests_pinned=false`, `model_weights_and_license_certified=false`, and `license_redistribution_approved=false`. Do not redistribute or bundle model weights on this evidence.

### Native CLI Smoke #451 — classified diagnostic, not GPU acceptance
- [Actions #451](https://github.com/niyomse-collab/niyom/actions/runs/44874710210) completed **SUCCESS as a classified diagnostic** after invoking official binaries on synthetic RGB and RGBA/ICC/300-DPI inputs.
- Real-CUGAN and Anime4KCPP produced validated native 2x synthetic outputs, but actual GPU adapter binding was **not** verified. Real-ESRGAN failed Vulkan initialization (`vkCreateInstance failed -9`); Waifu2x hit the same Vulkan failure plus access violation `0xC0000005`.
- Both input cases report `completed_engine_count=2`, `candidate_output_validation_complete=false`, `real_inference_verified=false`, and `quality_improvement_verified=false`. NVIDIA DXGI adapter was absent; per-process GPU/VRAM verification was zero. The successful workflow conclusion means known Hosted Runner limitations were classified, not that all four engines passed.
- Diagnostic JSON artifact ID **14695097695**; [download from Actions](https://github.com/niyomse-collab/niyom/actions/runs/44874710210/artifacts/14695097695).

### GFPGAN preservation — direct 9/9 Blob SHA recheck
- Compared each protected file at PR #20 base `288dd8501c230a118d9a7e60d2522a2cc7411bcc` against exact PR #20 head `940ca3f02982bc9ae711b28d403e2c191ab9573a`. **9/9 Git Blob SHAs are identical**: face workflow; `face_protection.py`, `detection.py`, `selection.py`, `face_module/__init__.py`, `large_faces.py`, `v211_face_contract.py`, `test_v211_face_contract.py`, and `test_v211_large_face_audit.py`.
- HAT execution remains a separate compatibility choice; this 9/9 check specifically establishes byte identity of the protected GFPGAN/face files.

### Acceptance boundary
- Candidate #1009 certifies frozen packaging, dispatch fixtures, provenance and installer slice hashes only. It does **not** certify interactive install/uninstall on the shop PC, four-engine GPU inference on Windows 11 GTX 1660 Ti, per-process adapter binding, 6 GiB VRAM stress, cancellation under native load, >18 MP native processing, visual A/B, Photoshop/MainTop or physical print quality.
- Existing source policy remains 512 px tiles / 32 px overlap, 6,144 MiB VRAM budget / 512 MiB reserve / 2,048 MiB minimum free prelaunch check. These are guardrails, not measured shop-PC stress results. Overall 4x output still uses a half-target seed followed by one native 2x pass; it is not native 4x or multipass AI.
- PR #20 and PR #18 remain OPEN/DRAFT/UNMERGED. V2 remains accepted master. No V1/V2 Stable edits, merge, release, customer images, native binaries or model weights committed; no quality-superiority claim.


## 21 พฤศจิกายน 2569 15:17 ICT — Exact-head Candidate #1011 / Core #1665 / Archive #337 / Native CLI #453

### PR identity and source delta
- PR #20 remains **OPEN / DRAFT / UNMERGED** on `work/v211-four-engine-v2-bridge-20261103`, exact checked HEAD `6612b0cd38a97a35455c9e76b4bd31a67741156b`; base remains PR #18 head `288dd8501c230a118d9a7e60d2522a2cc7411bcc`.
- PR #18 remains **OPEN / DRAFT / UNMERGED**. No merge or release action was taken.
- Compare from the previous documented HEAD `940ca3f02982bc9ae711b28d403e2c191ab9573a` to `6612b0c`: **2 commits / 3 files** — the manual shop-evidence workflow (+2/-1), its workflow-contract test (+1), and this status document (+41). No production engine, fusion, adapter, installer, or PyInstaller spec source changed in this delta.
- The shop-evidence workflow correction now allows this status document in its candidate-source freshness allowlist while retaining the explicit consent marker / workflow-dispatch confirmation requirement. A push without `[shop-gpu-evidence yes candidate=<40-character-SHA>]` runs only the hosted status job and does not schedule the physical shop runner.

### Windows Candidate #1011 — SUCCESS 2/2 on exact PR HEAD
- [GitHub Actions #1011](https://github.com/niyomse-collab/niyom/actions/runs/44880538286): event `pull_request`, branch `work/v211-four-engine-v2-bridge-20261103`, head SHA `6612b0c`; both `bridge-tests` and `windows-v2-candidate` completed **SUCCESS**.
- Bridge/Fusion/coordination tests: **432 passed**. Privacy/provisioning/hash tests: **69 passed**.
- Frozen candidate checks passed: synthetic download retry/fail-closed fault injection; V2-based experimental build; synthetic Inno Setup no-consent / explicit-consent / failure / uninstall lifecycle; frozen V2 imports; BigTIFF + streamed libvips QA; packaged provisioning `--check-only` without downloads; isolated consented cache cleanup; diagnostic `--help`; read-only shop-runner diagnostic parsing; provenance verifier syntax; exact BUILD_PROOF/source SHA; installer-slice SHA256 verification; artifact upload.
- Build version: **2.1.1-beta.1011**. Workspace guard reported `v1_files_preserved=true`, `stable_v2_files_preserved=true`; package QA reported `icc_preserved=true`, `dpi_preserved=true`, and `accepted_v2_sha256_unchanged=true`.
- Installer SHA256 from the Windows build log: `0b348edcdfcb415a19166416a83ea3fe16eda91c1fbb64fd10a11ff2f13b4415`.
- Experimental artifact ID **14698846562**, size **2,584,812,774 bytes**, artifact ZIP SHA256 `4f2dc7061ead012476306a5992907d83bd7058976fd08ad826721a1fa2bddeef`; expires **28 พ.ย. 2569 15:01 ICT**. [Download Candidate #1011](https://github.com/niyomse-collab/niyom/actions/runs/44880538286/artifacts/14698846562).
- Candidate #1011 is an exact-head frozen-package/provenance pass with synthetic lifecycle fixtures. It does **not** certify interactive shop installation, physical GPU inference, image-quality improvement, or print acceptance.

### Independent Core #1665 — SUCCESS on exact PR HEAD
- [GitHub Actions #1665](https://github.com/niyomse-collab/niyom/actions/runs/44880538333): Windows **1,101 passed / 1 skipped**; Ubuntu **1,099 passed / 3 skipped**. Pytest and compileall passed on both platforms.

### Official Archive Audit #337 — SUCCESS with license boundary retained
- [GitHub Actions #337](https://github.com/niyomse-collab/niyom/actions/runs/44880538258): **32 archive/audit checks + 11 provisioning checks passed**. All four official Windows archives were downloaded, hash-audited, safely inspected and transactionally provisioned in ephemeral QA storage; `all_provenance_checks_passed=true`.
- Official release asset metadata was rechecked. Waifu2x 20250915 and Anime4KCPP v3.2.0 publish SHA256 digests matching the audited pins. The GitHub release API still returns `digest=null` for the selected Real-ESRGAN v0.2.5.0 and Real-CUGAN 20220728 Windows ZIP assets; their hashes remain **observed CI pins**, not publisher digests.
- The audit explicitly retains `model_weights_and_license_certified=false` and `license_redistribution_approved=false`. Retrieved source-license text and archive hashes do not establish every model-weight/third-party right or permission to redistribute. No native binaries or model weights are committed or bundled.

### Native CLI Smoke #453 — classified diagnostic only, not GPU acceptance
- [GitHub Actions #453](https://github.com/niyomse-collab/niyom/actions/runs/44880538325) completed workflow SUCCESS after classifying the known hosted Windows runner limitations; it is **not** four-engine GPU acceptance.
- Official binaries were invoked on synthetic RGB and RGBA/ICC/300-DPI PNGs. Real-CUGAN and Anime4KCPP produced validated native 2x outputs. Real-ESRGAN failed Vulkan initialization (`vkCreateInstance failed -9`); Waifu2x had the same Vulkan initialization failure plus `0xC0000005`.
- Both synthetic cases report `completed_engine_count=2`, `candidate_output_validation_complete=false`, `real_inference_verified=false`, `quality_improvement_verified=false`, and `runtime_vram_budget_passed=false`. Physical adapter verification remains **0/4**. This is a hosted-runner limitation classification; it neither negates nor re-certifies the owner's earlier Windows 11 GTX 1660 Ti tests.

### PR #18 / GFPGAN preservation — direct exact-head Blob SHA check
- Compared the following nine protected files at PR #20 base / PR #18 head `288dd8501c230a118d9a7e60d2522a2cc7411bcc` against exact PR #20 HEAD `6612b0c`. All **9/9 Git Blob SHAs are identical**: face workflow; `face_protection.py`, `detection.py`, `selection.py`, `face_module/__init__.py`, `large_faces.py`, `v211_face_contract.py`, `test_v211_face_contract.py`, and `test_v211_large_face_audit.py`.
- Shared app/core integration files are not included in this byte-identity count; their face-safety contract remains covered by the adapter regressions. PR #20 continues to disable the HAT Assist execution route as a separate compatibility difference; this is not a GFPGAN file modification.

### Large-image / scale / memory — source and CI coverage, not hardware certification
- Current source uses the disk-backed path above 18 MP, libvips region reads, **512 px native tiles / 32 px overlap**, overlap-seam validation, worst-case disk reservation, per-tile cancellation and streamed PNG output. The fusion pass also processes bounded tiles and writes a separate atomic QA PNG.
- Runtime policy remains **6,144 MiB device-wide VRAM budget**, **512 MiB reserve**, and **2,048 MiB minimum free VRAM before each native process**. These are guardrails and CI-tested logic, not measured peak VRAM under four real engines on the shop GPU.
- Overall source-to-print 4x geometry still creates a half-target seed and performs one native 2x pass per engine. It is **not native 4x or multi-pass 8x inference**. Unsupported modes/depths and formats remain V2-only.
- No affirmative exact-head shop-GPU consent marker was supplied; no self-hosted shop runner or local PC was accessed. Native 4/4 inference on the GTX 1660 Ti, runtime adapter binding, 6 GiB stress, cancellation under native load, >18 MP real inference, visual A/B across people/animals/objects/Thai-English-Chinese lettering/flat fills/gradients/RGBA, Photoshop/MainTop and physical print remain **NOT CERTIFIED**.

### Acceptance boundary
- PR #20 and PR #18 remain OPEN/DRAFT/UNMERGED. V2 remains the accepted master. No V1/V2 Stable edits, merge, release, customer artwork, native binaries or model weights committed; no claim that V2.1.1 quality exceeds V2.


## 22 พฤศจิกายน 2569 17:53 ICT — exact HEAD f364623 / Candidate #1034

### PR identity and latest commit
- PR #20 remains **OPEN / DRAFT / UNMERGED** on `work/v211-four-engine-v2-bridge-20261103`.
- Exact checked branch HEAD: `f3646232349a9212b0970c60c114bcc1310c9dd7`. A direct compare of that SHA against the branch returned **identical / 0 ahead / 0 behind**.
- Commit `f364623` is test-only: it adds `test_detached_halo_does_not_dilate_onto_adjacent_single_hard_edge` in `tests/test_v211_styled_effect_auto_guard.py`. It proves a detached broad halo protection band does not freeze a neighbouring single hard edge. No production source changed in this commit.
- The localized halo production change is earlier commit `18b4c5cd348aec474b081b0e9da11a5c6c6fc63a`; the new exact-head regression locks its intended boundary behavior.
- PR #18 remains OPEN / DRAFT / UNMERGED and is still the base of PR #20 at `288dd8501c230a118d9a7e60d2522a2cc7411bcc`.

### Independent Core #1711 — SUCCESS on exact HEAD
- [GitHub Actions #1711](https://github.com/niyomse-collab/niyom/actions/runs/45005400932): both Windows and Ubuntu jobs completed successfully.
- Windows: **1,128 passed / 1 skipped**. Ubuntu: **1,126 passed / 3 skipped**. `compileall` passed on both platforms.

### Windows Candidate #1034 — SUCCESS 2/2 on exact HEAD
- [GitHub Actions #1034](https://github.com/niyomse-collab/niyom/actions/runs/45005401343): `bridge-tests` and `windows-v2-candidate` both completed **SUCCESS** for source SHA `f3646232349a9212b0970c60c114bcc1310c9dd7`.
- Bridge/Fusion/coordination tests: **454 passed**. Privacy/provisioning/official-assets/manifest-hash tests: **69 passed**. Total in the candidate bridge-test job: **523 passed**.
- Frozen package checks passed: V2 import smoke; synthetic Inno Setup no-consent / affirmative-consent / setup-failure / uninstall lifecycle; BigTIFF + streamed libvips QA; packaged four-engine `--check-only` dispatch without downloads; isolated consented cache cleanup; diagnostic `--help`; read-only shop-runner diagnostic parsing; candidate provenance; exact BUILD_PROOF source SHA; every installer slice SHA256; experimental artifact upload.
- Workspace guard: `v1_files_preserved=true`, `stable_v2_files_preserved=true`. Packaged TIFF QA: `icc_preserved=true`, `dpi_preserved=true`, `accepted_v2_sha256_unchanged=true`, exact odd-target crop; multipage TIFF is explicitly rejected from this single-page path.
- Installer SHA256: `aa9dc66c519f9d6f3a16160301b769fc0d9d1abfa273340c941cc04ea6221401`.
- Experimental artifact ID **14748577237**; size **2,584,755,671 bytes**; artifact ZIP SHA256 `fb08ecd1c824e54ef0c0c8e4af4f163186899766fdec250b40ca77eb5d53b9ad`; expires **29 Nov 2026 16:33 ICT**. [Download Candidate #1034](https://github.com/niyomse-collab/niyom/actions/runs/45005401343/artifacts/14748577237).
- PyInstaller emitted warnings for optional/missing `expecttest`, `pycparser.lextab/yacctab`, `scipy.special._cdflib`, driver-provided `nvcuda.dll`, and optional Numba `tbb12.dll`. The candidate still passed its frozen import and dispatch checks. Do not copy/bundle an NVIDIA driver DLL from another PC; determine whether the optional TBB path is used on the shop PC before changing dependencies.

### Official Archive Audit #360 — SUCCESS, redistribution still NOT approved
- [GitHub Actions #360](https://github.com/niyomse-collab/niyom/actions/runs/45005401057): all four official Windows archives were downloaded, matched their release digest or recorded CI pin, safely audited and transactionally provisioned into ephemeral QA storage. A four-engine manifest loaded successfully.
- Archive SHA256:
  - Real-ESRGAN v0.2.5.0: `abc02804e17982a3be33675e4d471e91ea374e65b70167abc09e31acb412802d` — no publisher digest; recorded CI pin.
  - Waifu2x 20250915: `7425be94b94e4c8f37a1e433ac0e0100c43790e2c37418f4b65d8235adfbdc87` — published digest.
  - Real-CUGAN 20220728: `c6e08d46c11704b1e3a1ada9ddd591cb5005f52f132136c8633ba25def400e01` — no publisher digest; recorded CI pin.
  - Anime4KCPP v3.2.0: `82897b0f03ddb88ab3d1affb745baf99506cfe3ceffaeaf73796c6dea4077f19` — published digest.
- Upstream license documents were retrieved and hashed, including Anime4KCPP's separate GPLv3 CLI/video notice and MIT core notice. The audit explicitly reports `license_redistribution_approved=false` and `model_weights_and_license_certified=false`. Do not bundle or redistribute third-party binaries/weights based only on archive/source-license verification.

### Native CLI Smoke #484 — diagnostic only, NOT four-engine GPU acceptance
- [GitHub Actions #484](https://github.com/niyomse-collab/niyom/actions/runs/45005401106) invoked official binaries on synthetic RGB and RGBA/ICC/300-DPI PNG inputs and retained JSON evidence only.
- Real-CUGAN and Anime4KCPP returned native process exit code 0 in the hosted-runner synthetic cases. Real-ESRGAN failed Vulkan initialization (`vkCreateInstance failed -9`); Waifu2x failed the same initialization and also reported `0xC0000005`.
- The runner reported `completed_engine_count=2`, `candidate_output_validation_complete=false`, `real_inference_verified=false`, `quality_improvement_verified=false`, `runtime_vram_budget_passed=false`; physical NVIDIA/DXGI adapter status was `nvidia_dxgi_adapter_not_present`, so per-engine adapter verification was **0/4**. The workflow SUCCESS means the known hosted-runner limitation was classified, not that all four models or visual quality passed.

### PR #18 protected face/GFPGAN files — direct Blob SHA comparison
- Compared PR #18 base SHA `288dd8501c230a118d9a7e60d2522a2cc7411bcc` against exact PR #20 HEAD `f3646232349a9212b0970c60c114bcc1310c9dd7`.
- All **9/9** protected files are byte-identical: `.github/workflows/build-windows.yml`; `signprint_ai/face_module/face_protection.py`; `signprint_ai/face_module/detection.py`; `signprint_ai/face_module/selection.py`; `signprint_ai/face_module/__init__.py`; `signprint_ai/large_faces.py`; `signprint_ai/v211_face_contract.py`; `tests/test_v211_face_contract.py`; `tests/test_v211_large_face_audit.py`.
- The optional HAT Assist execution route remains a separate compatibility difference in PR #20; it was not restored or treated as a GFPGAN file change.

### Acceptance boundary and next action
- No affirmative exact-head shop-GPU consent marker was present; no self-hosted shop runner or local PC was accessed. Therefore the four native processes have **not** been accepted as running together on the GTX 1660 Ti, and 6 GiB stress, native cancellation under load, real >18 MP inference, visual A/B, Photoshop/MainTop and physical print remain **NOT CERTIFIED**.
- V2 remains the accepted master. PR #20 and PR #18 remain Draft/unmerged. No V1/V2 Stable changes, merge/release, customer images or native binaries/weights committed, and no claim that V2.1.1 is visually superior to V2.


## 22 พฤศจิกายน 2569 19:52 ICT — Exact-head Candidate #1035 re-verification

### Branch identity and source scope
- PR #20 remains OPEN / DRAFT / UNMERGED on `work/v211-four-engine-v2-bridge-20261103`; direct compare confirms the branch is exactly at `5b9c19282118c4394796696f43875fb1e76653a6` (ahead 0 / behind 0 against that SHA).
- Candidate #1035 Windows build log checks out that exact branch commit `5b9c192`, writes it into BUILD_PROOF, and verifies candidate provenance against the same SHA. This is the current experimental installer source.
- The only commit after the preceding production/test HEAD `f3646232349a9212b0970c60c114bcc1310c9dd7` is documentation-only; no production source or test code changed after the Candidate #1034 code/test baseline.
- PR #18 remains OPEN / DRAFT / UNMERGED and is still the base at `288dd8501c230a118d9a7e60d2522a2cc7411bcc`.

### Exact branch Candidate #1035
- Windows Candidate #1035: [Actions run 45014814396](https://github.com/niyomse-collab/niyom/actions/runs/45014814396), SUCCESS **2/2 jobs** (`bridge-tests`, `windows-v2-candidate`), built from exact source `5b9c19282118c4394796696f43875fb1e76653a6`.
- Bridge/fusion/coordination tests: **454 passed**; privacy/provisioning/hash tests: **69 passed**; total **523 passed**.
- Frozen V2 imports, synthetic installer consent/failure/uninstall lifecycle, BigTIFF/libvips QA, packaged provisioning `--check-only` without downloads, diagnostic help dispatch, workspace preservation, BUILD_PROOF/source SHA and every installer-slice SHA256 passed.
- Workspace guard: `v1_files_preserved=true`, `stable_v2_files_preserved=true`; TIFF QA: `icc_preserved=true`, `dpi_preserved=true`, `accepted_v2_sha256_unchanged=true`.
- Version: `2.1.1-beta.1035`; installer SHA256: `a3834a7f179337821d11e1717a028ea9a865f07759ffa42bdf8258a27b0e2203`.
- Artifact ID **14751674915**, size **2,584,826,337 bytes**, ZIP SHA256 `90d8980b4e73ca42432f574ffe95178fe5cad2ca9df1c9b58ab2343fa9fc64dd`; expires **29 Nov 2026 18:27 ICT**. [Download Candidate #1035](https://github.com/niyomse-collab/niyom/actions/runs/45014814396/artifacts/14751674915).
- Candidate #1035 is a frozen package/provenance pass. It does not certify interactive installation on the shop PC, real four-engine inference, visual quality or print output.

### PR merge-snapshot regression and provenance checks
- Independent Core #1713: [Actions run 45014814430](https://github.com/niyomse-collab/niyom/actions/runs/45014814430), SUCCESS on the PR merge snapshot `79d0ef7` (merge of exact PR head `5b9c192` into base `288dd850`): Windows **1,128 passed / 1 skipped**; Ubuntu **1,126 passed / 3 skipped**; compileall passed on both.
- Official Archive Audit #361: [Actions run 45014814382](https://github.com/niyomse-collab/niyom/actions/runs/45014814382), SUCCESS on the same PR merge snapshot. All four official archives were hash-audited and transactionally provisioned into ephemeral QA; manifest validated all four engines. Real-ESRGAN and Real-CUGAN remain recorded CI SHA256 pins because upstream does not publish archive digests. `model_weights_and_license_certified=false` and `license_redistribution_approved=false`; no binaries/weights are bundled or committed.
- Native CLI Smoke #485: [Actions run 45014814363](https://github.com/niyomse-collab/niyom/actions/runs/45014814363), classified diagnostic only on the same PR merge snapshot. Real-CUGAN and Anime4KCPP produced validated synthetic 2x outputs; Real-ESRGAN and Waifu2x were blocked by hosted-runner Vulkan initialization (`vkCreateInstance failed -9`; Waifu2x also `0xC0000005`). NVIDIA DXGI/NVML adapter verification **0/4**; `real_inference_verified=false`, `quality_improvement_verified=false`. Workflow SUCCESS records correct classification of the hosted-runner limitation, not four-engine GPU acceptance.

### Direct V2/GFPGAN protection check
- Direct Git Blob SHA comparison from PR #18 base `288dd8501c230a118d9a7e60d2522a2cc7411bcc` to exact PR #20 branch HEAD `5b9c19282118c4394796696f43875fb1e76653a6` confirms **9/9 protected files byte-identical**: V1 Windows face workflow; GFPGAN face protection, detection, selection and module; large-face protection; V2.1.1 face contract and its regression/audit tests.
- Optional HAT Assist execution remains a separate compatibility difference in PR #20; it is not a GFPGAN file change and has not been silently restored.

### Automatic four-engine behavior and remaining limits
- Once a verified manifest exists, the app invokes the four-engine bridge automatically after the accepted V2 save for supported upscaling jobs; there are no separate per-engine buttons. All four native candidates are run sequentially and are mandatory for four-engine fusion. Real-ESRGAN, Waifu2x and Real-CUGAN determine the primary consensus; Anime4K is deliberately a small bounded corroborating term (0.06) because its output is lower-confidence in the owner's Windows comparisons.
- If GFPGAN/Studio AI ran but its face ROI cannot be mapped, or styled-effect ROI mapping is invalid, the bridge keeps the entire accepted V2 raster and skips the auxiliary engines/QA rather than risk altering protected content.
- Automatic styled-effect protection is still a conservative local heuristic, **not** semantic recognition of every glow, bevel, shadow, stroke or embossed text. Manual effect ROI remains recommended for complete known styled regions; human A/B review is required.
- Large PNG jobs use disk-backed/libvips tiles (512 px core / 32 px overlap), cancellation and a device-wide VRAM guard policy (6,144 MiB budget / 512 MiB reserve / 2,048 MiB prelaunch free threshold). CI BigTIFF/streaming QA is not a real native GPU stress test. The 4x target path remains half-target seed + one native 2x pass, not native 4x or multipass 8x inference.
- PyInstaller non-fatal warnings remain for driver-provided `nvcuda.dll`, optional Numba `tbb12.dll`, and optional imports. Do not copy/bundle driver DLLs or unpinned TBB binaries; runtime relevance must be checked on the shop PC.
- No exact-head affirmative shop-GPU consent marker was present; no self-hosted shop runner was dispatched or accessed. GTX 1660 Ti 4/4 inference, per-process adapter binding, 6 GiB stress, native cancellation under load, >18 MP real inference, visual A/B, Photoshop/MainTop and physical print remain **NOT CERTIFIED**.
- PR #20 and PR #18 remain OPEN/DRAFT/UNMERGED. V2 remains accepted master. No V1/V2 Stable edits, merge/release, customer images or native binaries/weights committed, and no quality-superiority claim.


## 22 พฤศจิกายน 2569 23:22 ICT — Candidate #1038 ปิด Build สำเร็จ

### Exact branch / source
- PR #20 ยังคง OPEN / DRAFT / UNMERGED; branch `work/v211-four-engine-v2-bridge-20261103`; exact source HEAD `4cf82be720868bd560a24a830251979bc9242126`.
- PR #18 ยังคง OPEN / DRAFT / UNMERGED และเป็น base `feature/v2.1.1-super-ai` ที่ `288dd8501c230a118d9a7e60d2522a2cc7411bcc`.
- Compare จาก Candidate #1035 source `5b9c19282118c4394796696f43875fb1e76653a6` ถึง HEAD นี้พบ 3 commits / 3 files เท่านั้น: Windows workflow เพิ่ม styled-effect test, test fixture เพิ่ม 147 บรรทัด และเอกสารสถานะเพิ่ม 36 บรรทัด **ไม่มี Production Source เปลี่ยนหลัง Candidate #1035**.

### Windows Candidate #1038 — SUCCESS
- Actions: https://github.com/niyomse-collab/niyom/actions/runs/45032897907
- ทั้ง `bridge-tests` และ `windows-v2-candidate` สำเร็จ
- Bridge/Fusion/coordination: **460 passed**; privacy/provisioning/hash: **69 passed**.
- Frozen package checks: packaged V2 imports; Inno Setup consent/uninstall lifecycle บน synthetic fixture (no model downloads); single-page BigTIFF และ streamed libvips QA route; packaged provisioning `--check-only` แบบไม่ดาวน์โหลด; synthetic cache cleanup; diagnostic help dispatch; provenance/source SHA และทุก installer-slice SHA256 ผ่าน.
- Candidate provenance ยืนยัน source SHA ตรงกับ `4cf82be720868bd560a24a830251979bc9242126`.
- Installer SHA256: `2bbdb0d4c4a35ef9f411f19d41a0f6bec25cc19e780e0e7ea8e9e09f311431c9`.
- Artifact ID **14759692343**, size **2,584,682,215 bytes**, artifact ZIP SHA256 `70466172db94bea78a81bc03a4ccf5806c1a7879d10ccf2c3009a9cbfd564b17`; expires **29 Nov 2026 21:59:51 ICT**.
- Artifact: https://github.com/niyomse-collab/niyom/actions/runs/45032897907/artifacts/14759692343
- Build emitted non-fatal PyInstaller warnings for driver-provided `nvcuda.dll`, optional Numba `tbb12.dll`, `pycparser.lextab/yacctab`, and `scipy.special._cdflib`. Packaged import smoke passed; do not bundle NVIDIA driver DLLs blindly. The Numba TBB threading path still needs shop-PC runtime verification if used.
- This is a frozen-package/build-provenance pass, not an interactive installation on the shop PC or native GPU/visual/print acceptance.

### Independent Core #1719
- Actions: https://github.com/niyomse-collab/niyom/actions/runs/45032897827
- Windows: **1,129 passed / 1 skipped**.
- Ubuntu: **1,127 passed / 3 skipped**.
- Compileall passed on both systems.

### Official archive audit #364
- Actions: https://github.com/niyomse-collab/niyom/actions/runs/45032897786
- All four official Windows archives passed member/path audit, recorded or published digest checks, and transactional provisioning to ephemeral QA storage; four-engine manifest was generated.
- Waifu2x 20250915 and Anime4KCPP v3.2.0 have published release digests verified. Real-ESRGAN v0.2.5.0 and Real-CUGAN 20220728 have no publisher archive digest; current SHA values are observed CI pins and require independent digest approval.
- Upstream source-license texts were retrieved and hashed, but this is not legal review or model-weight rights certification. `model_weights_and_license_certified=false`, `license_redistribution_approved=false`, and `included_in_customer_installer=false`. Do not redistribute or bundle third-party binaries/weights on this evidence alone.
- Audit report artifact ID **14758227031**: https://github.com/niyomse-collab/niyom/actions/runs/45032897786/artifacts/14758227031

### Native CLI smoke #488 — diagnostic only
- Actions: https://github.com/niyomse-collab/niyom/actions/runs/45032897765
- Real-CUGAN and Anime4KCPP native processes returned validated synthetic 2x RGB and RGBA outputs. The RGBA fixture preserved alpha pixels, ICC and 300-DPI metadata.
- Real-ESRGAN failed Vulkan initialization (`vkCreateInstance failed -9`). Waifu2x failed Vulkan initialization with the same error plus `0xC0000005`.
- NVIDIA/DXGI adapter verification **0/4**; runtime VRAM guard was not requested; `real_inference_verified=false`, `runtime_device_use_verified=false`, `runtime_vram_budget_passed=false`, and `quality_improvement_verified=false`.
- Therefore this run does not prove all-four inference or GPU use on the shop GTX 1660 Ti. It is consistent with a hosted runner lacking a Vulkan-capable NVIDIA adapter and does not invalidate the owner's prior Windows 11 GTX 1660 Ti tests.
- Native diagnostic report artifact ID **14758751907**: https://github.com/niyomse-collab/niyom/actions/runs/45032897765/artifacts/14758751907

### Direct V2 / GFPGAN protection recheck
- Fetched all nine protected files independently at PR #20 base / PR #18 HEAD `288dd8501c230a118d9a7e60d2522a2cc7411bcc` and exact PR #20 HEAD `4cf82be720868bd560a24a830251979bc9242126`; all **9/9 Git Blob SHAs match**: `.github/workflows/build-windows.yml`; `signprint_ai/face_module/face_protection.py`, `detection.py`, `selection.py`, `__init__.py`; `signprint_ai/large_faces.py`; `signprint_ai/v211_face_contract.py`; `tests/test_v211_face_contract.py`; `tests/test_v211_large_face_audit.py`.
- PR #20 still disables the optional HAT Assist execution route present in PR #18. This is a separate compatibility difference, not a GFPGAN file change; it remains disclosed and is not silently restored.
- PR #20 has 82 changed paths; no executable, DLL, archive, model-weight/checkpoint or customer-image files are present. No V1/V2 Stable files were modified.
- No shop self-hosted GPU run was scheduled or accessed; no affirmative exact-head shop-run consent evidence was present.

### Acceptance boundary
- Candidate #1038 is the current frozen package for exact source HEAD `4cf82be`; the prior #1035 package is superseded for current package acceptance.
- Still NOT CERTIFIED: real all-four native inference on shop GTX 1660 Ti; runtime adapter binding; 6 GB VRAM stress; cancel-under-load; >18 MP native four-engine streaming; native 4x/8x multi-pass; real-font Thai/English/Chinese and portrait/animal/object/gradient/RGBA A/B; Photoshop/MainTop/RIP and physical print quality.
- Keep V2 as accepted master. PR #20 remains Draft/unmerged; no merge/release and no claim that V2.1.1 quality exceeds V2.


## 23 November 2026 — correction to the current scale summary

- Corrected the opening summary and current limitation bullets: earlier wording that said 3x, 8x and anisotropic source-to-target geometry were rejected was stale. The live bridge maps the source to the accepted V2 canvas using `fit` or `stretch`, then builds a half-target seed; each native engine still performs exactly one 2x pass.
- The overall source-to-target geometry can therefore be 2x/3x/4x/8x/custom/anisotropic within the current format, pixel, row, disk and minimum-seed guards. This must not be described as native 3x/4x/8x inference or multi-pass AI.
- The large path uses libvips to create private PNG intermediates from supported 8-bit RGB/RGBA source/V2 rasters, then runs sequential 512-pixel-core / 32-pixel-overlap native tiles and streamed fusion/QA. Synthetic bridge tests cover 2x/3x/4x/8x geometry with fake processors; the 8x fixture intentionally fails the Anime4K contribution gate and publishes no fused QA sidecar.
- This correction is documentation-only. It does not certify native GPU 4/4, real >18 MP inference, VRAM/cancel stress, visual A/B or print quality.


## 23 November 2026 — exact PR HEAD Candidate #1040

### Exact source and branch state
- PR #20 remains OPEN / DRAFT / UNMERGED on `work/v211-four-engine-v2-bridge-20261103`; exact HEAD: `bf31703c98b21706ec2db70f2a34ce2e2ce0c91d`.
- PR #18 remains OPEN / DRAFT / UNMERGED and is the base at `288dd8501c230a118d9a7e60d2522a2cc7411bcc`.
- Compare from the preceding Candidate #1038 source `4cf82be720868bd560a24a830251979bc9242126` to this HEAD shows **2 commits / 1 changed file only**: `docs/V211_FOUR_ENGINE_BRIDGE_BUILD_STATUS_TH.md` (**63 additions / 3 deletions**). No production source, tests, installer, spec, model manifest or workflow changed after Candidate #1038.
- Direct Git Blob SHA checks against PR #18 base confirm **9/9 protected files byte-identical**: `.github/workflows/verify-v211-face.yml`; `signprint_ai/face_module/face_protection.py`, `detection.py`, `selection.py`, `__init__.py`; `signprint_ai/large_faces.py`; `signprint_ai/v211_face_contract.py`; `tests/test_v211_face_contract.py`; and `tests/test_v211_large_face_audit.py`.
- PR #20 has 82 changed paths; no executable, DLL, archive, checkpoint/weight or customer-image paths are present. No V1-named paths are present. Optional HAT Assist execution remains disabled in PR #20 as a separate compatibility difference; GFPGAN/face-protection files are unchanged.

### Windows Candidate #1040 — SUCCESS on exact PR HEAD
- Actions: https://github.com/niyomse-collab/niyom/actions/runs/45068009107
- Both jobs passed: `bridge-tests` and `windows-v2-candidate`.
- Bridge/Fusion/coordination tests: **460 passed**; privacy/provisioning/hash tests: **69 passed**; total **529 passed**.
- Frozen checks passed: V2 packaged imports; synthetic Inno Setup consent/failure/uninstall lifecycle; single-page BigTIFF and streamed libvips QA; packaged provisioning `--check-only` without downloads; consented cache-cleanup fixture; diagnostic `--help`; read-only shop-runner and provenance PowerShell syntax; exact BUILD_PROOF/source SHA; every installer-slice SHA256; experimental artifact upload.
- Installer SHA256: `389ba63266c47651d42ee4bbb7e2dea8ffa6ffc74eab148242f58492255ab85a`.
- Artifact ID **14773875767**; size **2,584,695,354 bytes**; ZIP SHA256 `61d4a62dec0fa624b76f4607209fe3fa6df11f38acafcffd012fb20987f81cca`; expires **29 Nov 2026 21:16 UTC / 30 Nov 2026 04:16 ICT**. [Download Candidate #1040](https://github.com/niyomse-collab/niyom/actions/runs/45068009107/artifacts/14773875767).
- Non-fatal PyInstaller warnings remain for `pycparser.lextab/yacctab`, `scipy.special._cdflib`, driver-provided `nvcuda.dll`, and optional `tbb12.dll`. Do not bundle NVIDIA driver DLLs or unpinned TBB binaries; runtime relevance remains a shop-PC check.

### Independent Core #1723 — SUCCESS on the PR merge snapshot
- Actions: https://github.com/niyomse-collab/niyom/actions/runs/45068009075
- Both jobs checked out merge snapshot `9cde9f5` (merge of exact PR HEAD `bf31703` into base `288dd850`).
- Windows: **1,129 passed / 1 skipped**. Ubuntu: **1,127 passed / 3 skipped**. `compileall` passed on both platforms.

### Official Archive Audit #366 — SUCCESS on exact PR HEAD
- Actions: https://github.com/niyomse-collab/niyom/actions/runs/45068009124
- All four official Windows archives were downloaded, hash-audited, path/member-audited and transactionally provisioned into an ephemeral QA directory; a four-engine manifest was generated.
- Archive SHA256: Real-ESRGAN v0.2.5.0 `abc02804e17982a3be33675e4d471e91ea374e65b70167abc09e31acb412802d` (observed CI pin; no publisher digest); Waifu2x 20250915 `7425be94b94e4c8f37a1e433ac0e0100c43790e2c37418f4b65d8235adfbdc87` (published digest); Real-CUGAN 20220728 `c6e08d46c11704b1e3a1ada9ddd591cb5005f52f132136c8633ba25def400e01` (observed CI pin; no publisher digest); Anime4KCPP v3.2.0 `82897b0f03ddb88ab3d1affb745baf99506cfe3ceffaeaf73796c6dea4077f19` (published digest).
- Upstream source-license documents were retrieved and hashed. This is not legal review or model-weight rights certification: `model_weights_and_license_certified=false`, `license_redistribution_approved=false`; native binaries/weights remain excluded from the installer and repository.

### Native CLI Smoke #490 — classified diagnostic only, exact PR HEAD
- Actions: https://github.com/niyomse-collab/niyom/actions/runs/45068009071
- Real-CUGAN and Anime4KCPP produced validated synthetic 2x outputs on the hosted Windows runner.
- Real-ESRGAN was blocked by `vkCreateInstance failed -9`; Waifu2x was blocked by the same Vulkan initialization failure plus `0xC0000005`.
- NVIDIA DXGI/NVML physical adapter verification: **0/4**; runtime VRAM budget: **not passed**; `real_inference_verified=false`; `quality_improvement_verified=false`. The workflow SUCCESS means the hosted-runner limitation was correctly classified, not that all four engines passed GPU inference.
- No self-hosted shop-GPU workflow was dispatched: no affirmative exact-candidate consent was present. The dedicated workflow still requires explicit `confirm_shop_gpu=yes` plus the installed candidate source SHA.

### Current acceptance boundary
- Candidate #1040 supersedes Candidate #1038 for the current PR HEAD package.
- The 23 Nov scale correction describes **overall source-to-target geometry** (2x/3x/4x/8x/custom/anisotropic) created by mapping the source to the accepted V2 canvas and then using a half-target seed. Each external native engine still performs exactly **one native 2x pass**; this is not native 3x/4x/8x inference or multi-pass AI.
- Synthetic bridge tests cover scale geometry; the 8x fixture intentionally fails the Anime4K pixel-contribution gate and publishes no fused QA sidecar.
- Still NOT CERTIFIED: all-four native inference on the shop GTX 1660 Ti; per-process adapter binding; 6 GB peak-VRAM stress; Windows cancel-under-load; real >18 MP native streaming; customer-image A/B for faces, animals, objects, Thai/English/Chinese lettering, flat fills, gradients and RGBA edges; Photoshop/MainTop/RIP and physical print quality.
- V2 remains the accepted master. PR #20 and PR #18 remain Draft/unmerged. No V1/V2 Stable changes, no merge/release, no binaries/weights/customer images committed, and no claim that V2.1.1 quality exceeds V2.
