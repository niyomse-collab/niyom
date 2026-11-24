# Windows 11 QA: NiyomSilp V2.1.1 + four engines

สถานะ: ผ่านขั้นตอนตรวจ ZIP ทางการและสร้าง Manifest จากไฟล์จริงบน Windows CI
ยัง **ไม่ใช่** ผลพิสูจน์ real inference ของสี่ตัวหรือคุณภาพเหนือ V2; ห้าม Merge/Release ก่อน QA ภาพจริง

**Source update 20 พ.ย. 2569:** Large jobs above 18 MP now accept RGB/RGBA 8-bit PNG/JPEG/WebP source files and PNG/JPEG/single-page TIFF/BigTIFF accepted-V2 rasters through libvips-to-PNG intermediates. Earlier notes in this document that mark large JPEG/WebP as V2-only are historical and are superseded by the final source correction below. This is preparation/format support, not native GPU or print-quality certification.

## หลักการ
- V2, GFPGAN, เครื่องมือแต่งภาพ, การส่งออก PNG/ICC/DPI และการป้องกันใบหน้า ต้องทำงานเหมือนเดิม
- AI สี่ตัวรันจากภาพต้นฉบับเป็น candidate แยกกันที่ 2x ไม่ขยายต่อกันสี่รอบ
- Real-ESRGAN ใช้ realesrgan-x4plus; Waifu2x ใช้ models-cunet; Real-CUGAN ใช้ models-se; Anime4KCPP CLI v3.2.0 ใช้ factor 2 โดยอัลกอริทึมฝังอยู่ในโปรแกรม
- คงผล V2 แยกจาก candidate และห้ามใช้ผลทดลองทับไฟล์พิมพ์จริงอัตโนมัติ

## เตรียมโมเดลบน Windows ในโฟลเดอร์ซอร์สสาขาทดลอง

~~~powershell
py -3 -m pip install Pillow
$qa = Join-Path $env:LOCALAPPDATA 'NiyomSilp\V211-FourAI-QA'
py -3 -m tools.v211_provision_four_engines --archives-dir "$qa\archives" --install-dir "$qa\engines" --manifest "$qa\manifest.json" --download-missing
~~~

เครื่องมือดาวน์โหลดจาก GitHub ต้นทางหากไม่มี ZIP, ตรวจ SHA-256, แตกไฟล์สู่ QA directory และสร้าง Manifest ของ executable และโมเดลทั้งหมด ไม่แก้ไข V2 Stable
ไม่อัปโหลดภาพลูกค้า และไม่บรรจุ executable/weights ลงใน Windows installer หรือ repo

## ทดสอบใน QA
สำหรับภาพ PNG ต้นฉบับ 512x512 กับผล V2 ขนาด 1024x1024 ตัวอย่างนี้ใช้สเกล 2x (เปลี่ยนตามขนาดจริง):

~~~powershell
py -3 -m tools.v211_four_engine_run "C:\private\source.png" "$qa\private-ab" "$qa\manifest.json" --width 1024 --height 1024 --v2-reference "C:\private\v2-reference.png"
~~~

จะได้ candidate และรายงาน A/B ในพื้นที่ QA ส่วนตัว ไม่ใช่ภาพรับรองพร้อมพิมพ์
กรณีต้องการเปิดตัวช่วยหลังบันทึกภาพ V2 ในโปรแกรมรุ่นทดลองจาก PowerShell session เดียวกัน:

~~~powershell
$env:NIYOMSIL_V211_FOUR_AI = '1'
$env:NIYOMSIL_V211_FOUR_AI_MANIFEST = "$qa\manifest.json"
$env:NIYOMSIL_V211_FOUR_AI_EVIDENCE_DIR = "$qa\private-ab"
~~~

หากไม่เปิด Flag นี้ หรือ engine ล้มเหลว ภาพ V2 ที่บันทึกแล้วต้องไม่เปลี่ยน
ใช้ภาพที่มีสิทธิ์ทดสอบเท่านั้น และห้าม push ภาพลูกค้าขึ้น GitHub สาธารณะ

## CUDA 12.8 driver compatibility for the bundled V2 core

The experimental Windows build pins PyTorch 2.11.0 + CUDA 12.8. The shop diagnostic now reports the NVIDIA-SMI driver against two distinct NVIDIA Windows requirements:

- CUDA 12.x minor-version compatibility floor: **528.33**.
- CUDA 12.8 GA toolkit driver version: **570.65**.

A driver below 528.33 is below the documented CUDA 12.x minor-compatibility floor. A driver from 528.33 up to 570.64 is reported as minor-compatibility-only; it is not reported as meeting the full CUDA 12.8 GA driver version. This static comparison does not prove `torch.cuda.is_available()`, successful model initialization, or inference.

This check is reported separately from NCNN/Vulkan eligibility. It must not be used to block or certify Real-ESRGAN, Waifu2x or Real-CUGAN Vulkan execution. The actual Vulkan physical adapter and each native process still require their own evidence.

## ก่อน Release
- พิสูจน์สี่ executable inference ผ่านในโปรแกรม V2.1.1 ที่ Build จริงบน GTX 1660 Ti
- ตรวจโหมด 2x, 4x, และงานใหญ่ ไม่บังคับ GPU 6 GB จนหน่วยความจำหมด
- A/B กับ V2: ตัวอักษรไทย/อังกฤษ/จีน, สีเขียวด้านหลังตัวอักษร, รอยหยักเส้นโค้ง, สีไล่เฉด, หน้า, PNG alpha, ICC/DPI
- Real inference และ fusion ที่ดีกว่า V2 ยังไม่มีผลรับรอง; Build ผ่านไม่ได้แปลว่าได้ใช้ AI สี่ตัวในไฟล์ส่งออกจริง
- ตรวจสิทธิ์และประกาศลิขสิทธิ์ โดยเฉพาะข้อกำหนด GPL ของ Anime4KCPP ก่อนบรรจุหรือแจกจ่ายซอฟต์แวร์


## การทำงานใน V2.1.1 หลังการเชื่อมต่อ (5 พ.ย. 2569)

- Core Adapter บันทึกไฟล์ V2 ให้เสร็จก่อน จากนั้นจึงเรียก Four-Engine Bridge ด้วยไฟล์ V2 ที่บันทึกแล้ว
- เมื่อครบ 4 engines และ fusion ผ่านการตรวจ จะสร้างไฟล์ QA แยกชื่อ `*.V211-4AI-QA-*.png` และแสดงใน Preview ด้านขวา ไฟล์ V2 ไม่ถูกแทนที่
- คำสั่ง Cancel ถูกส่งไปยัง native subprocess; บน Windows ใช้การหยุด process tree และบน POSIX หยุด process group พร้อมตรวจ Cancel ระหว่าง fusion tiles
- หากยกเลิก/ล้มเหลว ให้ลบ partial candidates และคงไฟล์ V2 เดิม; ถ้าใช้ Evidence Directory แบบส่วนตัว โฟลเดอร์งานที่ยกเลิกจะถูกล้าง
- [Historical note — superseded by the 20 Nov source correction below] งาน Four-Engine ขนาดปกติรองรับ RGB/RGBA PNG/JPEG/TIFF. Current disk-backed jobs above 18 MP accept RGB/RGBA 8-bit PNG/JPEG/WebP/single-page TIFF/BigTIFF source inputs and PNG/JPEG/single-page TIFF/BigTIFF accepted-V2 rasters; libvips converts them to private PNG seed/reference files, and native tiled inference/fusion consumes PNG intermediates. Native candidates are PNG. Multi-page TIFF, CMYK, unsupported bit depths, PDF/PSD and files libvips cannot read remain V2-only. Streamed limits remain 1,000 MP, 64 MiB per row and a disk-space preflight.
- ทุก Native Engine ยังประมวลผลเพียง 2x หนึ่ง pass จาก seed ครึ่งขนาดของเป้าหมาย ดังนั้นเป้าหมายภาพ 4x/8x เป็นเพียงขนาดปลายทางของ candidate ไม่ใช่ Native 4x/8x หรือ multi-pass inference
- CI ที่ใช้ fake executables หรือ hosted runner ไม่มี Vulkan ไม่ใช่หลักฐาน real inference หรือคุณภาพบน GTX 1660 Ti; ต้องทดสอบบนเครื่องร้านและตรวจภาพ A/B จริงก่อนรับรอง


## 5 พฤศจิกายน 2569 — ตรวจเครื่องร้าน GTX 1660 Ti ด้วยคำสั่งเดียว

เมื่อใช้ Installer รุ่นทดลอง V2.1.1 และเลือกติดตั้ง AI ทั้งสี่ในขั้นตอนติดตั้งแล้ว ให้เปิด PowerShell และรัน:

~~~powershell
# This experimental installer is per-user (PrivilegesRequired=lowest).
# Resolve its actual install folder from this user's 64-bit Inno Setup uninstall record.
$subkey = 'Software\Microsoft\Windows\CurrentVersion\Uninstall\{4B6A2C18-0F95-47EE-A6B8-0F2DD7B0CE11}_is1'
$base = [Microsoft.Win32.RegistryKey]::OpenBaseKey(
  [Microsoft.Win32.RegistryHive]::CurrentUser,
  [Microsoft.Win32.RegistryView]::Registry64
)
try {
  $key = $base.OpenSubKey($subkey)
  if ($null -eq $key) { throw 'ไม่พบการติดตั้ง V2.1.1 ใน Windows profile นี้' }
  try { $installDir = [string]$key.GetValue('Inno Setup: App Path') }
  finally { $key.Dispose() }
}
finally { $base.Dispose() }

if ([string]::IsNullOrWhiteSpace($installDir)) { throw 'ไม่พบ Install Path ของ V2.1.1' }
$exe = Join-Path $installDir 'NiyomsilAIEnhancer.exe'
if (-not (Test-Path -LiteralPath $exe -PathType Leaf)) { throw "ไม่พบไฟล์: $exe" }
& $exe --diagnose-v211-four-ai --output-dir "$env:USERPROFILE\Desktop\NiyomSilp-V211-GPU-QA"
~~~

คำสั่งนี้ค้นหา path จาก HKCU ของผู้ใช้ปัจจุบัน เพราะ Installer ใช้ `PrivilegesRequired=lowest` และ `{autopf}` จึงติดตั้งแบบ per-user ไม่ใช่ `%ProgramFiles%` ของทุกบัญชี

รายงานอยู่ที่:

~~~text
%USERPROFILE%\Desktop\NiyomSilp-V211-GPU-QA\shop_gpu_diagnostic.json
~~~

เครื่องมือใหม่นี้:
- ตรวจ NVIDIA GPU, Driver, VRAM และ Vulkan device ที่มองเห็นได้
- ใช้เฉพาะภาพสังเคราะห์ RGB และ RGBA พร้อม sRGB ICC และ 300 DPI
- เรียก Native CLI จริงทั้งสี่ตัวกับภาพทดสอบทั้งสองชนิด โดยตรวจขนาด 2x, Alpha, ICC และ DPI
- จำกัดเวลาแต่ละ Engine ไว้ 180 วินาทีในงานวินิจฉัยนี้
- ต้องมี VRAM ว่างอย่างน้อย 2,048 MiB ก่อน bind/เริ่ม optional Four-Engine; ค่านี้เป็น launch preflight ไม่ใช่การจอง VRAM หรือการรับประกัน peak-memory
- ลบภาพทดสอบและภาพผลลัพธ์ชั่วคราวหลังจบ เหลือเฉพาะ JSON
- ไม่อ่านภาพลูกค้า ไม่ใช้เครือข่าย ไม่อัปโหลดไฟล์ และไม่แก้ไฟล์ V2 ที่ผ่านการบันทึกแล้ว

การแปลผล:
- `all_four_native_cli_outputs_validated_on_both_synthetic_cases=true` หมายถึง Native CLI ทั้งสี่สร้างผลที่ผ่านการตรวจรูปแบบ/metadata บนภาพสังเคราะห์ทั้ง RGB และ RGBA
- `four_engine_cli_passed_on_gtx1660ti_vulkan_host=true` หมายถึงตรวจพบ GTX 1660 Ti ผ่าน NVIDIA-SMI และ Vulkaninfo พร้อมกับ CLI ทั้งสี่ผ่าน; ยังไม่ใช่การวัดคุณภาพภาพหรือการรับรองว่าแต่ละ CLI เลือก GPU adapter ตัวนั้นโดยตรง
- `quality_improvement_verified`, `visual_quality_certified` และ `print_quality_certified` จะเป็น false เสมอในเครื่องมือนี้

ข้อจำกัดที่ต้องไม่สับสน:
- เป้าหมาย 4x/8x เป็นขนาดภาพปลายทางที่สร้างจาก seed ครึ่งขนาดและใช้ Native 2x เพียงหนึ่ง pass ไม่ใช่ Native 4x/8x หรือ multi-pass inference
- [Historical pre-20 Nov format note; superseded by the final source correction] Current >18 MP source/V2 format allowlists are documented in the final section below. The CI described here remains synthetic/fake-processor evidence, not real inference on the GTX 1660 Ti and not 6 GB VRAM or print-quality certification.
- รายงาน JSON นี้เป็นหลักฐานการรัน CLI เท่านั้น การยืนยันคุณภาพยังต้อง A/B ภาพ V2 เทียบ QA และให้เจ้าของร้านตรวจด้วยตา


## 6 พฤศจิกายน 2569 — แยก Backend ของ Anime4KCPP ออกจาก Vulkan

- Real-ESRGAN, Waifu2x และ Real-CUGAN เป็น NCNN/Vulkan executables; Manifest ปัจจุบันไม่ได้ pin \`-g\` เป็น GPU ID เฉพาะ จึงใช้ค่า auto ของ upstream และการพบ GTX 1660 Ti ใน \`nvidia-smi\`/\`vulkaninfo\` ยังไม่ยืนยันว่าแต่ละ process เลือก adapter นี้จริง
- Anime4KCPP v3.2.0 ไม่ใช่ NCNN/Vulkan engine; CLI แยก processor เป็น CPU, OpenCL หรือ CUDA และมีตัวเลือก \`-p/--processor\`, \`-d/--device\`, \`--lp\` เพื่อแสดง processor และ \`-l\` เพื่อแสดงอุปกรณ์ตามเอกสาร upstream
- Manifest ปัจจุบันเรียก Anime4KCPP ด้วย \`-f 2\` โดยไม่ได้ระบุ \`-p\` หรือ \`-d\`; จึงใช้ค่า default \`processor=auto\` และ \`device=0\` ของ CLI ไม่ควรสรุปว่า Anime4KCPP ใช้ CUDA/OpenCL หรือ GTX 1660 Ti เพียงเพราะมี Vulkan GPU
- \`shop_gpu_diagnostic.json\` schema 2 เพิ่ม \`anime4k_backend_inventory\` โดยเรียก \`ac_cli --lp\` และ \`ac_cli -l\` เพื่อบันทึก processor/device ที่มีให้เลือกและตรวจว่ารายชื่ออุปกรณ์มี GTX 1660 Ti หรือไม่ ฟิลด์ \`processor_selection_verified\` และ \`device_selection_verified\` ยังคงเป็น \`false\` เพราะการสำรวจรายการไม่ใช่หลักฐาน backend ที่ถูกใช้ระหว่าง inference
- การพิสูจน์ว่า Engine ใดใช้ GPU ตัวใดจริงยังต้องบันทึก backend/device จาก process ขณะประมวลผลบนเครื่องร้าน; ห้ามใช้รายงาน host readiness แทนหลักฐานนี้

## SHA256 และสิทธิ์ไฟล์

- Real-ESRGAN v0.2.5.0 และ Real-CUGAN 20220728 ใช้ SHA256 ที่สังเกตและบันทึกจาก Windows CI เนื่องจาก upstream release API ไม่มี digest; เป็น pin สำหรับตรวจความคงที่ของไฟล์ ไม่ใช่ publisher-signed digest
- Waifu2x 20250915 และ Anime4KCPP v3.2.0 มีค่า SHA256 pin แยกในทะเบียนแพ็กเกจ; Provisioning ยังตรวจ SHA256 ของ executable และ model assets รายไฟล์ก่อนเผยแพร่ Manifest
- สิทธิ์ของ executable และ model weights เป็นคนละเรื่อง; audit ปัจจุบันยังตั้ง \`model_weights_and_license_certified=false\` และไม่อนุมัติการ redistribute/bundle โดยเฉพาะ Anime4KCPP ซึ่งต้องตรวจ build/module และ GPL/MIT notices ของ binary ที่เลือกก่อนแจกจ่าย


## 6 พฤศจิกายน 2569 — ตรวจว่า AI ทั้งสี่เปลี่ยนพิกเซลจริง

- Fusion เพิ่ม counterfactual attribution แบบ leave-one-engine-out: คำนวณภาพปลายทางซ้ำโดยตัด contribution ของ Engine ทีละตัว แล้วเปรียบเทียบ RGB หลัง edge gating, luminance clipping และการปัดค่าพิกเซล
- `engine_pixel_effect_pixels` ระบุจำนวนพิกเซลที่ผลลัพธ์จริงเปลี่ยนเมื่อถอด Engine ตัวนั้นออก; `engine_pixel_effect_verified` จะเป็น true เฉพาะเมื่อมีผลต่างในพิกเซลจริงอย่างน้อยหนึ่งตำแหน่ง
- `all_four_engine_pixels_contributed=true` จึงหมายถึงทั้งสี่ Engine มีผลต่อพิกเซล RGB ที่ส่งออกจาก fusion จริง ไม่ใช่เพียงสร้าง candidate ได้ครบสี่ไฟล์
- หาก Engine ใดไม่มีผลต่อพิกเซล ระบบจะรายงาน `four_engine_fusion_contribution_incomplete` และ Preview จะแจ้งว่าไม่ครบ 4 ตัว; ยังเก็บ V2 print raster เดิมไว้ และไม่รับรองคุณภาพหรือส่งเสริม candidate อัตโนมัติ
- การทดสอบนี้พิสูจน์เส้นทางคำนวณของภาพสังเคราะห์เท่านั้น; ต้องมี Native inference จริงบน GTX 1660 Ti และ A/B ด้วยสายตาก่อนอนุมัติคุณภาพ



## 6 พฤศจิกายน 2569 — แยกผล Native CLI ตาม Backend (Diagnostic schema 3)

- Real-ESRGAN, Waifu2x และ Real-CUGAN เป็นกลุ่ม NCNN/Vulkan จึงรายงานแยกเป็น ncnn_vulkan_engine_names และ three_ncnn_vulkan_engines_passed_on_gtx1660ti_vulkan_ready_host.
- Anime4KCPP v3.2.0 เป็นอีก backend family: processor auto อาจเลือก CPU/OpenCL/CUDA; ไม่ใช่ NCNN/Vulkan และไม่ควรนับเป็นหลักฐาน Vulkan inference.
- anime4k_cli_outputs_validated_on_both_synthetic_cases แยกการผ่าน CLI/Output ของ Anime4K ออกจากผลของสาม NCNN engines; anime4k_backend_inventory แสดงรายการ processor/device ที่มี แต่ยังไม่พิสูจน์การเลือกจริง.
- per_engine_backend_selection_verified และ anime4k_backend_selection_verified เป็น false จนกว่าจะมี telemetry จาก process ขณะ inference บนเครื่องร้าน.
- all_four_cli_validated_on_gtx1660ti_vulkan_equipped_host หมายถึงทั้งสี่ CLI ผ่านบนเครื่องที่ตรวจพบ GTX 1660 Ti และ Vulkan พร้อมกันเท่านั้น ไม่ได้อ้างว่าทุก process ใช้ GTX adapter. ฟิลด์เดิม four_engine_cli_passed_on_gtx1660ti_vulkan_host คงไว้เพื่อ compatibility และมีความหมายเดียวกัน.
- เพิ่ม Regression แยกกรณี Anime4K ล้มแต่สาม NCNN ผ่าน และกรณี NCNN ตัวใดตัวหนึ่งล้ม; ไม่มีการเปลี่ยนการประมวลผลภาพ, Installer, Fusion, V1 หรือ V2 Stable.


## 6 พฤศจิกายน 2569 — per-engine process evidence (diagnostic update)

- Local `real_inference_report.json` now records each native process start flag, PID, exit code, process elapsed time and total elapsed time for Real-ESRGAN, Waifu2x, Real-CUGAN and Anime4KCPP.
- The report records only backend/device-index CLI flags that were passed (`-g` for NCNN/Vulkan; `-p/-d` for Anime4KCPP). It does not copy raw command lines, local paths, stdout, stderr or customer pixels into the report.
- Timeout and user cancellation have distinct failure classes; a timed-out process is terminated and its partial output is removed before the diagnostic continues.
- `runtime_device_use_verified=false` and per-engine `actual_adapter_verified=false` remain mandatory. PID/exit-code plus configured CLI flags prove process execution and configuration, not that Windows actually scheduled the process on the named GTX 1660 Ti. Adapter-use proof still needs reliable per-process GPU telemetry from the shop PC.
- This update does not change the image pipeline, Fusion, V2/GFPGAN, installer contents, provisioning, model weights or customer files. It adds local diagnostic evidence only; no network access or upload is introduced.

## 7 พฤศจิกายน 2569 — disk-backed RGB Fusion prototype (research only)

- tools/v211_four_engine_fusion.py เปลี่ยนจากการสร้าง Image.new() เต็มภาพเป็น raw raster ชั่วคราวบนดิสก์ เขียนผลแต่ละ tile ตามตำแหน่งแถว/คอลัมน์ แล้วเข้ารหัส PNG แบบ streaming ทีละ scanline และ IDAT chunk ขนาดจำกัด
- การเขียน QA ยังคงเป็น atomic: สร้างไฟล์ชั่วคราวในโฟลเดอร์ปลายทาง ตรวจโครงสร้าง/CRC ของ PNG แล้ว os.replace เมื่อเสร็จเท่านั้น; Cancel หรือพื้นที่ดิสก์ไม่พอจะไม่เขียนทับ QA เดิม
- RGB PNG fusion มีขอบเขตวิจัยไม่เกิน 1,000 MP และจำกัด row buffer 64 MiB พร้อมตรวจพื้นที่ว่างดิสก์ก่อนเริ่ม; อ่าน pixel tiles ของ V2/candidates ด้วย pyvips Region.fetch แบบ 2 มิติ ส่วน Pillow ใช้เฉพาะ header/metadata และภาพเล็กไม่เกิน 18 MP จึงไม่เรียก crop/load เต็มภาพ; ไม่ปิดหรือเปลี่ยน Pillow global decompression guard. Non-PNG large inputs ยังใช้ Pillow safety cap เดิม
- มี synthetic regression ที่ 18.012 MP ซึ่งตรวจว่าไม่มีการสร้าง Pillow canvas เต็มขนาด, ตรวจ ICC/DPI/pixel samples, tile partition equivalence และ atomic cancellation
- **ข้อจำกัดสำคัญ:** นี่เป็นการทำ disk-backed ที่ขั้น Fusion สำหรับ RGB เท่านั้น ไม่ได้เปิด Four-Engine end-to-end เกิน 18 MP เพราะ tools/v211_four_engine_run.py ยังปฏิเสธเกิน 18 MP ก่อนอ่าน Manifest/เรียก Native Process; signprint_ai/v211_background_fusion.py ยังคง fallback ไป V2 สำหรับงานใหญ่
- RGBA Fusion เกิน 18 MP ยัง fail-closed เพราะ alpha restoration/validation ใน Native subprocess และ coordinator ยังมี full-image resize; ห้ามปิด guard นี้จนกว่าจะทำ alpha resampling แบบ disk-backed และทดสอบขอบโปร่งใสจริง
- ยังไม่มี real four-engine inference, GPU adapter telemetry, customer-image A/B หรือ print-quality certification จากการเปลี่ยนแปลงนี้; synthetic CI ไม่ใช่หลักฐานว่า GTX 1660 Ti ใช้ทั้งสี่ engine ได้
- ขั้นต่อไปคือทำ external tile orchestration ให้ Native CLI ทั้งสี่ (รวม Anime4KCPP) ด้วย overlap/context และ disk-backed candidate assembly จากนั้นจึงย้าย runner guard อย่างมีหลักฐาน

## 7 พฤศจิกายน 2569 — official archive audit และ real CLI smoke

- Official archive provenance audit: GitHub Actions run 42360741238 ผ่านครบทุกขั้น (ดาวน์โหลด ZIP จากต้นทาง, ตรวจ SHA256/สมาชิก ZIP/ชื่อ path, สร้าง Manifest และ provision ในโฟลเดอร์ชั่วคราว); อัปโหลดเฉพาะรายงาน SHA256 ไม่เก็บ ZIP/weights/binaries ไว้ใน artifact
- SHA256 ที่ตรวจได้:
  - Real-ESRGAN v0.2.5.0: abc02804e17982a3be33675e4d471e91ea374e65b70167abc09e31acb412802d — ไม่มี publisher digest; เป็น observed pin ที่ต้องอนุมัติอิสระ
  - waifu2x 20250915: 7425be94b94e4c8f37a1e433ac0e0100c43790e2c37418f4b65d8235adfbdc87 — upstream published digest
  - Real-CUGAN 20220728: c6e08d46c11704b1e3a1ada9ddd591cb5005f52f132136c8633ba25def400e01 — ไม่มี publisher digest; เป็น observed pin ที่ต้องอนุมัติอิสระ
  - Anime4KCPP v3.2.0: 82897b0f03ddb88ab3d1affb745baf99506cfe3ceffaeaf73796c6dea4077f19 — upstream published digest
- Real CLI smoke: GitHub Actions run 42360741293 ผ่านขั้นตอนตรวจและจัดประเภทผลบน synthetic RGB และ RGBA/ICC 300 DPI; Real-CUGAN และ Anime4KCPP ประมวลผล synthetic case จบ, ส่วน Real-ESRGAN และ waifu2x ล้มด้วย vkCreateInstance failed -9 บน hosted runner ทั้งสองกรณี
- รายงานระบุ runtime_device_use_verified=false ทุก Engine เพราะ hosted runner ไม่ยืนยัน adapter ที่ใช้งานจริง; ผลนี้ไม่ใช่ GPU pass, ไม่ใช่คุณภาพ pass และไม่แทนการทดสอบ GTX 1660 Ti ของร้าน
- Artifact รายงานเท่านั้น: real CLI report ID 13569905331; archive audit report ID 13569796031. ไม่มี customer artwork หรือ model archive ใน artifact
- License ของ executable แยกจากสิทธิ์ model weights; Anime4KCPP GPL-3.0 ยังไม่อนุมัติ redistribution/bundling และสิทธิ์ weights ของ Waifu2x/Real-CUGAN/Real-ESRGAN ยังเป็น review gate. ห้าม bundle หรือ commit weights/binaries จนกว่าจะปิดการตรวจสิทธิ์



## 8 พฤศจิกายน 2569 — Application Bridge เชื่อม Disk-backed Large-image Tile Runner (research only)

- Core Adapter บันทึกผล V2 ให้เสร็จก่อน แล้วจึงเรียก Four-Engine Bridge แม้ source หรือ V2 target เกิน 18 MP. Bridge ใช้ `prepare_native_2x_inputs_streamed` สร้าง half-target seed และ padded V2 reference ด้วย libvips; Runner เปลี่ยนไปใช้ `run_tiled_candidates`; Fusion อ่าน RGB/RGBA ด้วย libvips regions เมื่อเกิน 18 MP; QA crop ใช้ `save_cropped_png_streamed`. ผล V2 เดิมไม่ถูกเขียนทับ.
- ค่า 18 MP เป็น threshold ที่เปลี่ยนไปใช้ disk-backed path ไม่ใช่ hard cap. ขอบเขตปัจจุบัน: สูงสุด 1,000 MP, row buffer สูงสุด 64 MiB, tile core 512 px / overlap 32 px, disk reserve แบบคำนวณจาก raster จริง และรัน native process ทีละ engine. งานเกินขอบเขตหรือ disk ไม่พอจะ fail closed กลับไปคง V2.
- Large RGBA: candidate alpha ถูกตรวจเทียบกับ accepted V2 alpha แบบ tile-by-tile; พิกเซลโปร่งใส/กึ่งโปร่งใสคงทั้ง RGB และ Alpha จาก V2; ICC/DPI ใช้จาก V2. PNG intermediates เป็นเส้นทางเข้า Native Tile Runner; CMYK/PDF/PSD ไม่อยู่ในขอบเขตนี้.
- Native engine แต่ละตัวทำเพียง 2x หนึ่ง pass บน seed ครึ่งขนาดของ target. ภาพปลายทาง 4x/8x จาก source จึงไม่ใช่ native 4x/8x หรือ multi-pass inference.
- หลักฐาน CI: มี synthetic 24 MP tile-runner test และ 24 MP streamed seed/QA-crop test; เพิ่ม bridge integration test ที่ลด threshold เฉพาะใน test เพื่อบังคับเส้นทาง streamed seed → tiled runner → streamed QA ด้วย fake processors และยืนยัน V2 bytes/ICC/DPI ไม่เปลี่ยน. Integration fixture นี้เป็นภาพเล็ก ไม่ใช่การทดสอบ real 24 MP inference ทั้งสี่ตัว.
- GPU diagnostic ตรวจว่าเครื่องเห็น GTX 1660 Ti ผ่าน NVIDIA-SMI/Vulkan และ total VRAM อย่างน้อยประมาณ 5,500 MiB ก่อน bind device; นี่เป็น capacity gate ไม่ใช่การวัด peak VRAM. ยังไม่มี 6 GB VRAM stress test บนเครื่องร้าน.
- `real_inference_verified=false` และ `quality_certified=false` ยังคงเป็นข้อบังคับจนกว่าจะรัน Native ทั้งสี่บน Windows 11 GTX 1660 Ti, เก็บ backend/device telemetry จริง และทำ A/B/Print QA ภาพจริง. Hosted Runner ที่ไม่มี Vulkan ไม่ใช่หลักฐานลบหรือบวกต่อเครื่องร้าน.


## 8 พฤศจิกายน 2569 — แยก Vulkan CLI กับ Native Loader Inventory (Diagnostic schema 4)

- แก้ความหมายของ `vulkaninfo_succeeded`: เป็น `true` เฉพาะเมื่อเรียก `vulkaninfo --summary` สำเร็จและอ่านรายการอุปกรณ์ได้จริงเท่านั้น
- เพิ่ม `vulkan_device_inventory_succeeded` และ `vulkan_inventory_source` เพื่อบอกว่ารายการอุปกรณ์มาจาก `vulkaninfo` หรือการเรียก Vulkan Loader โดยตรง
- เมื่อเครื่องไม่มีโปรแกรม `vulkaninfo` แต่ `vulkan-1.dll` enumerates อุปกรณ์ได้ รายงานจะไม่กล่าวว่า vulkaninfo สำเร็จอีกต่อไป; GPU binding ใช้ผล inventory ที่ตรวจได้จริงแทนการบังคับให้ติดตั้ง Vulkan SDK
- เพิ่ม Regression สำหรับกรณี Native Loader สำเร็จแต่ vulkaninfo ไม่ได้ติดตั้ง และกรณี inventory ไม่สำเร็จต้องหยุดแบบ fail-closed
- การแก้ไขนี้เป็นการทำให้หลักฐาน GPU ตรงกับสิ่งที่เกิดขึ้นจริง ไม่ใช่หลักฐานคุณภาพภาพหรือ print readiness. Runtime acceptance ยังต้องผ่าน NVML PID-to-device attribution และ non-zero memory หรือ WDDM PDH GPU Engine activity ครบทุก child process; หาก telemetry ของเครื่องร้านไม่พร้อม `runtime_device_use_verified=false` และ fail-closed ตามเดิม

## 9 พฤศจิกายน 2569 — ขอบเขต Large 4x ที่เพิ่มเข้ามา

- งาน PNG RGB/RGBA ที่เกิน 18 MP รองรับ source-to-V2 แบบกำหนดเอง รวมถึง 3x และ anisotropic stretch/squash ผ่าน disk-backed seed/tile path เมื่อผ่าน pixel, row-buffer, disk-space และ minimum-tile checks; JPEG/TIFF ขนาดใหญ่ยังใช้ V2 เท่านั้น.
- ทุกขนาดเป้าหมายสร้าง seed จากครึ่งหนึ่งของ V2 canvas แล้วให้ Native Engine ทำ 2x เพียงหนึ่ง pass; อัตราส่วน source-to-V2 อาจเป็น 2x, 3x, 4x, 8x หรือกำหนดเอง/ไม่เท่ากันสองแกนตาม stretch/fit. ห้ามเรียกผลปลายทางว่า Native 3x/4x/8x หรือ multi-pass AI.
- 3x, custom และ anisotropic source-to-V2 geometry เปิดใช้ใน research path แล้ว: source ถูก resample ตาม resize_mode ไปยัง half-target seed และทุก Native Engine ทำเพียง 2x หนึ่ง pass. Large non-PNG ยังใช้ V2-only; large PNG ผ่าน disk-backed seed/tile path เมื่อผ่าน bounds. Regression `test_large_bridge_routes_2x_3x_4x_and_8x_png_through_streamed_seed_and_tiled_runner` ใช้ fake processors เท่านั้น; fixture 8x ปัจจุบันตั้งใจ fail-closed ที่ Anime4K contribution gate และไม่เผยแพร่ QA sidecar. จึงยังไม่ถือว่า 8x ได้ภาพ Fusion ผ่านหรือผ่าน GPU/VRAM/คุณภาพจริง.
- CI ใช้ synthetic processors เพื่อทดสอบเส้นทางไฟล์/geometry; ต้องทดสอบ Native CLI ทั้งสี่และ A/B ภาพจริงบน GTX 1660 Ti ก่อนรับรอง.

## 9 พฤศจิกายน 2569 — runtime GPU binding update

- ก่อนเรียก Native subprocess ระบบตรวจ NVIDIA-SMI และ Vulkan physical-device inventory แล้วสร้าง manifest ชั่วคราวสำหรับ run นั้น: Real-ESRGAN, Waifu2x และ Real-CUGAN รับ `-g` จาก Vulkan index; Anime4KCPP แยกตรวจ `--lp/-l` แล้วกำหนด `-p/-d` เป็น CUDA หรือ OpenCL device ที่ตรงกับ GTX 1660 Ti.
- Manifest ที่ติดตั้งไว้ไม่ถูกแก้ไข; runtime-bound manifest ถูกลบหลังเรียก runner. หาก inventory หายหรือกำกวม ระบบหยุด Four-Engine assist และคง V2.
- `binding_configured=true` หมายถึง CLI flags ถูกกำหนดจาก inventory เท่านั้น; `runtime_device_use_verified=false` ยังคงบังคับ เพราะยังไม่มี per-process telemetry ยืนยันว่า Native process ใช้ adapter ที่ระบุจริง.


## 9 พฤศจิกายน 2569 — เพิ่ม End-to-end Four-Engine Bridge/Fusion ในคำสั่งตรวจเครื่องร้าน

ปรับ --diagnose-v211-four-ai ให้ตรวจมากกว่าการเรียก Native CLI แยกตัว:

- ยังคงรัน Native CLI ทั้งสี่กับภาพสังเคราะห์ RGB และ RGBA ที่มี sRGB ICC / 300 DPI
- เพิ่มการเรียก maybe_run_four_engine_assist ของ V2.1.1 จริงบนภาพสังเคราะห์ RGBA อีกหนึ่งกรณี โดยใช้ V2 reference สังเคราะห์ที่ขยาย 2x
- ตรวจว่า Bridge เรียกครบ 4 Engine, Fusion ทำงาน, และ engine_pixel_effect_verified เป็น true ครบทั้งสี่ ไม่ใช่เพียงสร้าง candidate ได้ครบ
- อ่านรายงานชั่วคราวเพื่อตรวจว่าทุก Native Process ผ่าน per-process VRAM preflight อย่างน้อยหนึ่งครั้ง และค่าต่ำสุดที่บันทึกได้ไม่น้อยกว่า 2,048 MiB
- ตรวจ SHA256 ของ source และ V2 reference ก่อน/หลัง เพื่อยืนยันว่า Bridge ไม่แก้ไขไฟล์ต้นฉบับหรือ V2 baseline
- ตรวจ PNG, ขนาด, RGB/RGBA, ICC, DPI และ Alpha ของ Fusion Output เทียบกับ V2 reference
- ลบ source/reference/candidates/manifest ชั่วคราวทั้งหมด เหลือเฉพาะ shop_gpu_diagnostic.json; ไม่ใช้ภาพลูกค้า ไม่เข้าถึงเครือข่าย และไม่อัปโหลดภาพ

รายงานเปลี่ยนเป็น schema 5 และเพิ่ม bridge_integration กับ four_engine_bridge_fusion_passed_on_gtx1660ti_configured_host.

**Exit code 0** จะเกิดได้ต่อเมื่อ Native CLI ทั้งสี่ผ่าน RGB/RGBA, Full Bridge/Fusion RGBA ผ่าน metadata/V2-preservation/VRAM checks และมี per-process physical-adapter telemetry ยืนยันว่า Native Process ทั้งสี่ใช้ GTX 1660 Ti ที่เลือกจริงเท่านั้น

**สถานะปัจจุบัน: ยังไม่ผ่าน Runtime GPU Acceptance.** Diagnostic ปัจจุบันตั้ง `runtime_device_use_verified=false` และ `per_engine_runtime_device_use_verified=false` ครบทั้งสี่โดยเจตนา เพราะยังไม่มี telemetry ที่พิสูจน์การใช้ physical adapter ของแต่ละ process ดังนั้นแม้ CLI/Fusion/Device Binding จะผ่าน ก็ต้องคืน exit code 1 และคง V2 เดิมไว้ รายงาน JSON ยังถูกสร้างเพื่อใช้ตรวจสอบขั้นตอนที่ผ่านและจุดที่ขาด

การตรวจนี้เพิ่ม Native Process อีก 4 ครั้งจากเดิม 8 ครั้ง; ค่า timeout เริ่มต้น 180 วินาทีต่อ Process จึงอาจใช้เวลาหลายนาทีตามเครื่องและโมเดล

เมื่อเพิ่ม telemetry จริงแล้ว ต้องทดสอบทั้งกรณีพบ process บน GTX 1660 Ti และกรณีไม่พบ/อ่านไม่ได้ โดยกรณีหลังต้อง fail-closed. แม้ Runtime GPU Acceptance ผ่าน ก็ยังไม่ใช่ A/B ภาพคน/สัตว์/งานป้ายจริง และไม่รับรองคุณภาพเหนือ V2; `quality_improvement_verified`, `visual_quality_certified` และ `print_quality_certified` ยังคงเป็น false.


## GitHub Actions: shop-PC GPU evidence (pre-merge, optional)

The shop evidence workflow remains **self-hosted-only** and never falls back to `windows-latest`. GitHub's `workflow_dispatch` limitation still applies while the file exists only in Draft PR #20, so this branch now also has a narrowly scoped `push` trigger. The push job is skipped unless the commit message contains an explicit consent marker with the exact installed candidate source SHA.

- Register a dedicated Windows 11 shop-PC runner in the repository's **Settings → Actions → Runners** and add the custom label `niyom-shop-gpu`. Use a dedicated Windows account with only the permissions needed for this QA; do not expose unrelated secrets to a self-hosted runner.
- Install the Experimental candidate built from source commit **X** and confirm the installed `BUILD_PROOF.txt` records that full 40-character SHA. Complete the one-time affirmative-consent installation of all four verified engine packages in the same Windows account.
- Only after that installation, make a **documentation-only** commit to this QA document on the PR #20 branch. Include this exact marker in the commit message, replacing X with the installed candidate's full SHA: `[shop-gpu-evidence yes candidate=X]`. The word `yes` is the explicit authorization to run the synthetic-only GPU diagnostic.
- The workflow checks that X is an ancestor of the trigger commit, that changes since X are limited to three non-production evidence-gate files (this workflow, its contract test, and this QA document), and that the installed `BUILD_PROOF.txt` matches X. Any application, model, provisioner, or other test/source change fails closed; install a candidate built from the newer source before retrying.

- **Current Experimental Candidate #553 (10 Nov 2026)** was built from source `21366b61a98388324b120585c039598b046fb142` on `work/v211-four-engine-v2-bridge-20261103`. [Windows Candidate run #553](https://github.com/niyomse-collab/niyom/actions/runs/42827575892) passed both `bridge-tests` and `windows-v2-candidate`; the latter verified frozen V2 imports, packaged provisioning `--check-only` without downloads, isolated cache cleanup, diagnostic `--help`, BUILD_PROOF/source-SHA equality and every installer-slice SHA256. Artifact ID `13772740302`, size **2,584,696,547 bytes**, artifact ZIP SHA256 `42a104c6f9377bba1544113fed9bac281ba725bcbf3ea8ae36f05b1b15b4a5ec`, installer SHA256 `054e4ce83ac32363fcb603719e259eee282a9d9ddb6cb295baeb7c40ac3cf046`; expires **17 Nov 2026 21:15:57 ICT**. [Download Candidate #553](https://github.com/niyomse-collab/niyom/actions/runs/42827575892/artifacts/13772740302). Use it for the shop diagnostic only when the installed `BUILD_PROOF.txt` matches this exact source SHA. This is a frozen-package/provenance pass, **not** shop installation, native GPU 4/4, VRAM, visual A/B or print acceptance.

- The workflow resolves the per-user Inno Setup installation, uses only `%LOCALAPPDATA%\\NiyomSilp\\V211-FourAI-QA\\manifest.json`, and invokes the packaged `--diagnose-v211-four-ai` command. It generates its own synthetic RGB/RGBA test inputs.
- The uploaded artifact contains only `build_identity.json` and `shop_gpu_diagnostic.json`. Synthetic images, native executables, model weights, ZIP archives and customer artwork are not uploaded.
- The `workflow_dispatch` path remains available only if this workflow is later present on the repository default branch; it requires both `confirm_shop_gpu=yes` and the candidate's full source SHA. **Do not merge PR #20 merely to enable dispatch.**
- If a self-hosted runner is not registered, use the one-command local PowerShell diagnostic above instead; do not dispatch this job to a GitHub-hosted runner.

The job still requires top-level and per-engine `runtime_device_use_verified=true` plus `shop_gpu_acceptance_passed=true`. It fails closed on any missing/ambiguous process-to-adapter telemetry. Synthetic evidence never certifies visual improvement, face identity or print quality. This workflow change itself has no consent marker and will not start a shop-PC job.


## 10 พฤศจิกายน 2569 — live NVML PID-to-adapter telemetry (fail-closed)

- เพิ่ม `tools/v211_gpu_process_telemetry.py` ใช้ NVIDIA Management Library (NVML) อ่าน process lists ของทั้ง Graphics และ Compute ขณะ native child process ยังทำงาน โดยรองรับ process API v3 และ fallback v2/v1 เมื่อ symbol มีให้ใช้
- Native subprocess sampler เรียก probe ทันทีหลัง launch และทุกช่วงไม่เกิน 50 ms ระหว่างรอ process; บันทึกเฉพาะสถานะ, จำนวน sample/process, adapter name/index และ API family ไม่บันทึก command line, local path, stdout/stderr หรือภาพ
- การยืนยันต่อ process ต้องพบ PID เดียวกันใน NVML process list ของ GTX 1660 Ti ที่ระบุได้เพียงตัวเดียว และต้องมีหลักฐานการทำงาน GPU อย่างใดอย่างหนึ่ง: (ก) NVML รายงาน GPU memory ของ PID มากกว่า 0 หรือ (ข) บน Windows WDDM ซึ่ง NVIDIA ระบุว่า `usedGpuMemory` เป็น `NVML_VALUE_NOT_AVAILABLE` เสมอ ต้องพบ GPU Engine utilization ของ PID เดียวกันผ่าน Windows PDH อย่างน้อย 2 samples และมี utilization มากกว่า 0. การพบ PID บน adapter อื่น/หลาย adapter, ไม่มี PDH activity, NVML/PDH ใช้ไม่ได้ หรือ process จบก่อนถูก sample จะไม่ผ่าน
- WDDM fallback enumerate instance จริงจาก `GPU Engine` / `GPU Process` performance counters (ไม่เดาชื่อ instance), resolve localized counter names ผ่าน Perflib/PdhLookupPerfNameByIndex, เรียก `PdhEnumObjectsW(bRefresh=True)` เพื่อ refresh object cache แล้วใช้ `PdhEnumObjectItemsW(dwFlags=0)` enumerate instances ก่อนอ่าน `Utilization Percentage`; parse LUID จาก instance แล้วจับคู่กับ LUID ของ NVIDIA adapter ที่ได้จาก DXGI `IDXGIAdapter1::GetDesc1`. จึงต้องผ่านทั้ง PID ใน NVML บน GTX 1660 Ti และ GPU Engine activity ของ PID เดียวกันบน DXGI LUID ของ GTX 1660 Ti; activity จาก Intel/adapter อื่นไม่ผ่าน
- JSON QA แสดง `runtime_gpu_engine_adapter_luid_match=true` และ LUID ของ adapter (ไม่บันทึก PID/command line) เพื่อให้ตรวจย้อนหลังได้; LUID เปลี่ยนได้หลัง reboot/driver update จึงอ่านใหม่ทุก process run
- สำหรับงาน tiled ต้องยืนยันทุก native child process ของแต่ละ engine ไม่ใช่เพียง tile ใด tile หนึ่ง; process ที่ไม่มี telemetry จะทำให้ aggregate ของ engine นั้น fail-closed
- Shop GPU acceptance รวมหลักฐานจาก synthetic RGB, RGBA และ end-to-end bridge/fusion run ทั้งสี่ engine; การตั้งค่า CLI `-g` หรือ `-p/-d` เพียงอย่างเดียวไม่ถือเป็น runtime evidence
- ข้อจำกัด: NVML PID + non-zero memory หรือ NVML PID + WDDM PDH GPU Engine activity เป็นหลักฐานการผูก process กับ adapter และ activity ณ ช่วง sample เท่านั้น ไม่พิสูจน์ว่า GPU ทำทุก instruction หรือคุณภาพภาพดีขึ้น. หาก WDDM ไม่เปิด GPU Engine counters หรือ inference สั้นเกินช่วง sample จะรายงาน unverified ไม่ลดเกณฑ์

อ้างอิง:
- NVIDIA NVML: [nvmlProcessInfo_v1_t](https://docs.nvidia.com/deploy/nvml-api/latest/structnvmlProcessInfo__v1__t.html) — `usedGpuMemory` เป็น `NVML_VALUE_NOT_AVAILABLE` ภายใต้ WDDM
- Microsoft PDH: [PdhEnumObjectsW](https://learn.microsoft.com/en-us/windows/win32/api/pdh/nf-pdh-pdhenumobjectsw) refreshes the object cache; [PdhEnumObjectItemsW](https://learn.microsoft.com/en-us/windows/win32/api/pdh/nf-pdh-pdhenumobjectitemsw) must use `dwFlags=0`; [PdhAddCounterW](https://learn.microsoft.com/en-us/windows/win32/api/pdh/nf-pdh-pdhaddcounterw) and [PdhLookupPerfNameByIndexW](https://learn.microsoft.com/en-us/windows/win32/api/pdh/nf-pdh-pdhlookupperfnamebyindexw) resolve and sample localized counters
- Microsoft DXGI: [DXGI_ADAPTER_DESC1](https://learn.microsoft.com/en-us/windows/win32/api/dxgi/ns-dxgi-dxgi_adapter_desc1) exposes the adapter LUID used to correlate the PDH instance
- แยก ctypes layouts ของ NVML process-info v1/v2/v3 ให้ตรงกับ ABI ของแต่ละ function (v1 = PID/memory; v2/v3 เพิ่ม GPU/compute instance IDs) และเพิ่ม Regression ขนาด struct 16/24/24 bytes เพื่อป้องกัน v2 API เขียนข้อมูลเกิน buffer ของ v1
- เพิ่มตำแหน่งค้นหา `nvml.dll` ของ Windows Standard Driver ที่ `Program Files\\NVIDIA Corporation\\NVSMI` นอกเหนือจาก DLL search path และ `System32`
- เพิ่ม Regression สำหรับ target mismatch, adapter ambiguity, memory unavailable, PID ไม่ปรากฏ, WDDM PID ที่ไม่มี PDH activity, PID mismatch ใน counter instance และ tiled child process ที่มีเพียงบาง process ผ่าน. Frozen spec และ Windows Candidate CI รวม module/test ใหม่แล้ว
- ไม่มีการแก้ V1, V2 Stable, GFPGAN, accepted V2 output, installer model payload หรือ model weights; ไม่เพิ่ม network access และไม่อัปโหลดภาพ

## Candidate source identity for shop GPU evidence — 12 พฤศจิกายน 2569

- The Windows Candidate workflow now checks out the exact PR head SHA for `pull_request` events (and `github.sha` for push/manual dispatch), with full Git history.
- `BUILD_PROOF.txt` records the checked-out source commit. Candidate provenance stores this as `source_commit` and records the Actions event SHA separately as `workflow_commit`.
- For pull requests, the workflow verifies that the current PR base SHA is an ancestor of the checked-out PR head. If the branch is behind its base, packaging fails rather than producing an ambiguous candidate.
- The shop evidence workflow requires the installed `BUILD_PROOF.txt` source commit to be present in the branch history and an ancestor of the evidence workflow revision. Use the exact 40-character **Source commit** printed in the installed `BUILD_PROOF.txt` as `candidate_source_sha`, with `confirm_shop_gpu=yes`.
- The earlier Candidate #616 artifact was built from the synthetic PR merge commit `464b33a33e1dead502a76f0b248ca03d38c30b32`, not the branch head. It remains an experimental package but is **not accepted as the source identity for the branch-ancestry-gated shop workflow**. Build a fresh candidate after this correction before running shop GPU evidence.
- The self-hosted evidence job uses synthetic RGB/RGBA test images only, retains JSON evidence only, and never certifies visual or print quality.


## 13 พฤศจิกายน 2569 — Candidate #644 ปัจจุบันสำหรับ shop evidence (แทน Candidate #553/#616)

- Exact PR #20 source commit: `f74da870ab5d38e5069cd5f9ba8af44055f01e1b` บน `work/v211-four-engine-v2-bridge-20261103`.
- Windows Candidate #644: [run 43283655318](https://github.com/niyomse-collab/niyom/actions/runs/43283655318) — ทั้ง bridge-tests และ frozen Windows candidate ผ่าน. ตรวจ V2 imports, no-download provisioning dispatch, isolated cache cleanup, diagnostic help, provenance verifier, BUILD_PROOF/source SHA และ installer-slice SHA256.
- Artifact ID `13974629144`; size **2,584,568,814 bytes**; ZIP SHA256 `23d57f42a670e4893db143e2513c2b94ee6b6fb2a86992974012e976c2b85386`; installer SHA256 `eb5009350f8507083605ff2d739df821c99f87033ee0f53b4f7486ac079e2828`. [Download Candidate #644](https://github.com/niyomse-collab/niyom/actions/runs/43283655318/artifacts/13974629144). หมดอายุ **20 พ.ย. 2569 02:09 ICT**.
- Candidate นี้ใช้เป็น source identity สำหรับ shop evidence ได้เมื่อผู้ใช้ติดตั้งใน Windows account เดียวกับ manifest และ `BUILD_PROOF.txt` ระบุ source commit ข้างต้นตรงกันเท่านั้น. ต้องยินยอมติดตั้งโมเดลทั้งสี่ก่อน.
- Native CLI Smoke #156 [run 43283655550](https://github.com/niyomse-collab/niyom/actions/runs/43283655550) เป็น diagnostic บน Hosted Windows: Real-CUGAN/Anime4KCPP สร้าง synthetic outputs; Real-ESRGAN/Waifu2x ล้มเพราะ `vkCreateInstance failed -9`; NVML ไม่พบและ adapter verification 0/4. จึงยังต้องรันบน GTX 1660 Ti ที่ติดตั้ง Vulkan/driver จริง.
- Core #1192 [run 43283655718](https://github.com/niyomse-collab/niyom/actions/runs/43283655718): Windows 950 passed / 1 skipped; Ubuntu 948 passed / 3 skipped; compileall ผ่าน.
- Official Archive Audit #120 [run 43283655327](https://github.com/niyomse-collab/niyom/actions/runs/43283655327): official archives ทั้งสี่ผ่าน SHA256/archive audit/transactional manifest provision ใน ephemeral QA directory; ไม่ใช่ real inference acceptance.
- **ยังไม่มีการอนุญาตหรือเรียก self-hosted shop workflow ในรอบนี้.** ห้ามเพิ่ม `[shop-gpu-evidence yes candidate=f74da870ab5d38e5069cd5f9ba8af44055f01e1b]` ใน commit message จนกว่าจะติดตั้ง Candidate #644 และผู้ใช้อนุมัติการทดสอบบนเครื่องร้านอย่างชัดเจน.
- Synthetic evidence ยังคงไม่รับรอง visual quality/print quality. ไม่อัปโหลดภาพลูกค้า; artifact shop workflow ต้องเป็น JSON evidence เท่านั้น.


## 13 พฤศจิกายน 2569 — Candidate #680 ปัจจุบันสำหรับการทดสอบบนเครื่องร้าน

ส่วนนี้ **แทน Candidate #644** สำหรับการติดตั้งทดสอบรอบถัดไป ห้ามใช้ SHA หรือ BUILD_PROOF ของ Candidate เก่าแทนกัน

### Source และ Windows Candidate

- PR #20 HEAD / source commit: `c89770074851b990698628d8c8e96e121e105a18` บน `work/v211-four-engine-v2-bridge-20261103`.
- Windows Candidate #680: [GitHub Actions run 43314285413](https://github.com/niyomse-collab/niyom/actions/runs/43314285413) — ทั้ง `bridge-tests` และ `windows-v2-candidate` สำเร็จ
- Bridge job ผ่าน compileall, Four-Engine coordination/fusion/autorun, V2 output preservation, privacy, official archive hash, provisioning และ manifest fail-closed tests
- Frozen job ผ่าน V2 import smoke, packaged `--provision-v211-four-ai --check-only` แบบไม่ดาวน์โหลด, isolated cache cleanup ที่เก็บไฟล์ไม่รู้จักไว้และปฏิเสธ profile อื่น, diagnostic `--help`, PowerShell AST parse, BUILD_PROOF/source provenance และ SHA256 ของ installer slices ทุกส่วน
- Installer SHA256: `5f18dc8f77e4ddf714645229f76ab4676ab026f5d68f476e2f33ebe409093fd6`
- Artifact ID: `13988039912`; ขนาด **2,584,579,685 bytes**; Artifact ZIP SHA256: `cf4c9fe1c6ffd4ad0fadfd3b9b473bbef16977a1d7278bc65891417074892a55`
- [ดาวน์โหลด Candidate #680](https://github.com/niyomse-collab/niyom/actions/runs/43314285413/artifacts/13988039912) — หมดอายุ **20 พ.ย. 2569 05:16:55 น. ICT** หากหมดอายุให้สร้าง Candidate ใหม่ ห้ามใช้ลิงก์เดิม
- Candidate นี้เป็น Frozen Package / provenance pass เท่านั้น ไม่ใช่การรับรองการติดตั้งหรือ GPU inference บนเครื่องร้าน

### Regression และ Official Assets บน PR HEAD เดียวกัน

- Independent Core #1232: [run 43314285420](https://github.com/niyomse-collab/niyom/actions/runs/43314285420) — Windows **953 passed / 1 skipped**; Ubuntu **951 passed / 3 skipped**; compileall ผ่านทั้งคู่
- Official Archive Audit #135: [run 43314285394](https://github.com/niyomse-collab/niyom/actions/runs/43314285394) — checkout เป็น PR merge commit `ab7b37a` ซึ่งรวม PR head `c8977007` กับ base `288dd850`; ดาวน์โหลดและตรวจ official archives, provision ลง ephemeral QA directory และสร้าง Manifest ครบสี่ engine สำเร็จ
- Archive SHA256 ที่ตรวจ:
  - Real-ESRGAN v0.2.5.0: `abc02804e17982a3be33675e4d471e91ea374e65b70167abc09e31acb412802d` — observed CI pin; ไม่มี publisher digest
  - Waifu2x 20250915: `7425be94b94e4c8f37a1e433ac0e0100c43790e2c37418f4b65d8235adfbdc87` — publisher digest
  - Real-CUGAN 20220728: `c6e08d46c11704b1e3a1ada9ddd591cb5005f52f132136c8633ba25def400e01` — observed CI pin; ไม่มี publisher digest
  - Anime4KCPP v3.2.0: `82897b0f03ddb88ab3d1affb745baf99506cfe3ceffaeaf73796c6dea4077f19` — publisher digest
- Archive audit ระบุทุก engine เป็น `archive_audited_not_inference_verified`; `real_inference_verified=false` และ redistribution approval ยังคง false

### Native CLI diagnostic — ห้ามตีความเป็น GPU/คุณภาพผ่าน

- Native CLI Smoke #171: [run 43314285421](https://github.com/niyomse-collab/niyom/actions/runs/43314285421) — checkout PR merge commit `ab7b37a` ที่มี source PR head `c8977007`
- Real-CUGAN และ Anime4KCPP มี native process execution จบตามที่รายงาน แต่ actual GPU adapter ไม่ได้รับการยืนยัน
- Real-ESRGAN และ Waifu2x ถูกบล็อกด้วย `vkCreateInstance failed -9` บน Hosted Runner
- NVML library ไม่พบ; runtime adapter verification **0/4**; `candidate_output_validation_complete=false`; `real_inference_verified=false`
- Workflow จบ SUCCESS เพราะจัดประเภท Vulkan limitation ที่คาดหมายได้ ไม่ใช่การผ่าน Native GPU 4/4, Four-Engine Fusion หรือ image-quality A/B

### คำเตือนจาก Frozen Build

- PyInstaller บน Hosted Runner รายงานว่าไม่พบ `nvcuda.dll` และ optional `tbb12.dll`; ยังไม่ใช่ build failure แต่ต้องตรวจ dependency บน Windows เครื่องร้านจริง
- ห้ามนำ driver DLL จากเครื่องอื่นมาฝังใน Installer โดยเดา; ให้ใช้ NVIDIA driver ที่ติดตั้งบนเครื่องปลายทางและตรวจ runtime dependency จากหลักฐานจริง
- ไม่มีการรัน self-hosted Shop GPU Evidence ในรอบนี้ ไม่มี consent marker และไม่มีการอัปโหลดภาพลูกค้า

### เกณฑ์ก่อนใช้ผลจาก Candidate #680

ติดตั้ง Candidate #680 ใน Windows account ที่จะทดสอบ แล้วตรวจว่า `BUILD_PROOF.txt` แสดง source commit ข้างต้นตรงตัว จากนั้นต้องได้รับความยินยอมชัดเจนก่อนเรียก Shop GPU Evidence. เก็บเฉพาะ JSON diagnostic/evidence; ทดสอบ adapter/PID, Native Engine 4/4, tiled cancel, peak VRAM และ fail-closed output ก่อน A/B. Candidate #680 ยังไม่รับรอง 6 GB hard cap, ภาพเกิน 18 MP, 4x/8x native inference, Photoshop/MainTop/RIP หรือคุณภาพเหนือ V2.


## 13 พฤศจิกายน 2569 — Candidate #681 ล่าสุดสำหรับรอบทดสอบถัดไป

ส่วนนี้แทน Candidate #680 สำหรับการทดสอบติดตั้งรอบถัดไป; Candidate #680/#644 เป็นหลักฐานย้อนหลังเท่านั้น.

- Source commit: `128c0eb0b8093630b3a7c9ce2a4ba7f1b9418f37`.
- Windows Candidate #681: [run 43328241363](https://github.com/niyomse-collab/niyom/actions/runs/43328241363) — bridge-tests และ windows-v2-candidate ผ่าน.
- Artifact ID `13995566000`, ขนาด **2,584,549,542 bytes**, ZIP SHA256 `cb4697045895a331ef6c0859b79bb95b28a2dd1f3aa01e6b5ab7db7a52ebf992`, installer SHA256 `b4e0553d845e2f29b944b85d8dc6caed212404d2a0a97c7ba548c371f1ade6b3`.
- [ดาวน์โหลด Candidate #681](https://github.com/niyomse-collab/niyom/actions/runs/43328241363/artifacts/13995566000) — หมดอายุ **20 พ.ย. 2569 06:42:51 น. ICT**.
- Independent Core #1235: [run 43328241217](https://github.com/niyomse-collab/niyom/actions/runs/43328241217) — Windows 953 passed / 1 skipped; Ubuntu 951 passed / 3 skipped.
- Official Archive Audit #136: [run 43328241206](https://github.com/niyomse-collab/niyom/actions/runs/43328241206) — official archives 4/4 SHA256/archive audit/transactional provision ผ่าน; ไม่ใช่ native inference.
- Native CLI Smoke #172: [run 43328241400](https://github.com/niyomse-collab/niyom/actions/runs/43328241400) — Real-CUGAN/Anime4KCPP native synthetic outputs ผ่าน; Real-ESRGAN/Waifu2x hosted runner Vulkan blocked; physical adapter verification 0/4; `real_inference_verified=false`.
- Candidate #681 มี PyInstaller warning `nvcuda.dll` และ `tbb12.dll`. ห้ามนำ NVIDIA driver DLL หรือ TBB runtime จากแหล่งที่ไม่ตรวจสอบมาฝังเอง. `nvcuda.dll` ต้องมาจาก NVIDIA driver ที่ติดตั้งบนเครื่อง; `tbb12.dll` เป็น optional Numba TBB threading backend และยังไม่มีหลักฐานว่าจำเป็นต่อ default app path.
- **ตรวจ driver ก่อน Shop GPU acceptance:** Candidate ใช้ PyTorch 2.11.0+cu128. Diagnostic ระบุขั้นต่ำ Windows CUDA 12.x minor compatibility 528.33 และ CUDA 12.8 GA 570.65. Driver ร้านล่าสุดที่บันทึก 5 พ.ย. 2569 คือ 451.67 (nvidia-smi CUDA 11.0); หากยังไม่อัปเดตจะต่ำกว่า CUDA 12.x compatibility floor และ PyTorch CUDA core อาจใช้ DirectML/CPU แทน CUDA. NCNN/Vulkan engine eligibility เป็นคนละเส้นทางและต้องตรวจแยก.
- ก่อนเริ่มทดสอบจริง ตรวจ `nvidia-smi` และ driver ปัจจุบัน, CUDA runtime/device selection, Vulkan GTX 1660 Ti inventory, per-process PID-to-adapter, VRAM และ 4-engine bridge. ห้ามเริ่ม Shop GPU Evidence จนมี affirmative consent/candidate marker ที่อนุมัติอย่างชัดเจน.
- ไม่มี self-hosted shop run ในรอบนี้; ไม่มีภาพลูกค้าใน CI/artifact. Candidate นี้ยังไม่รับรอง real inference 4/4, 6 GB peak VRAM, >18 MP stress, A/B quality หรือ Photoshop/MainTop/RIP.


## 13 พฤศจิกายน 2569 11:35 ICT — Candidate #696 exact-head update

ส่วนนี้เป็นข้อมูลล่าสุดสำหรับ Candidate ที่ใช้ติดตั้งทดสอบรอบถัดไป แทน Candidate #681; Candidate เก่าเก็บไว้เป็นประวัติเท่านั้น

### Source identity และ Windows package

- PR #20 branch HEAD / Candidate source commit: `7e806ecae371dec7a07a71ec1ea9d28cff39bd58`.
- Windows Candidate #696: [Actions run 43344275797](https://github.com/niyomse-collab/niyom/actions/runs/43344275797) — `bridge-tests` และ `windows-v2-candidate` ผ่านครบ 2/2 jobs.
- Bridge/privacy suites: 321 + 63 tests ผ่าน. Frozen V2 import smoke, packaged provisioning `--check-only` (ไม่ดาวน์โหลด/ไม่เขียน Manifest), isolated consented cache cleanup, diagnostic `--help`, PowerShell AST, BUILD_PROOF/source identity, installer-slice SHA256 และ artifact upload ผ่าน.
- Installer SHA256: `acea9ec24309a14ca36946f9db32dcc803823fa6b1431a77ad24347b136ab1b7`.
- Artifact ID `14001449540`; size **2,584,420,453 bytes**; ZIP SHA256 `6be6507218ff4ff589759c440100a7edafbc86974b8514a710e630d3c87b63b`.
- [ดาวน์โหลด Experimental Candidate #696](https://github.com/niyomse-collab/niyom/actions/runs/43344275797/artifacts/14001449540) — ตรวจ ณ 13 พ.ย. 2569 11:35 ICT ว่า artifact ยังไม่หมดอายุ; GitHub ระบุวันหมดอายุ **20 พ.ย. 2569 08:47 ICT**.
- Candidate workflow checkout exact PR head SHA; ห้ามใช้ synthetic merge SHA หรือ BUILD_PROOF จาก Candidate เก่ามาแทน.

### Exact-head regression และ official archives

- Independent Core #1252: [Actions run 43344275807](https://github.com/niyomse-collab/niyom/actions/runs/43344275807) — Windows **970 passed / 1 skipped**, Ubuntu **968 passed / 3 skipped**; compileall ผ่านทั้งคู่.
- Official Archive Audit #143: [Actions run 43344275907](https://github.com/niyomse-collab/niyom/actions/runs/43344275907) — official ZIP ทั้งสี่ผ่าน archive/hash audit และ transactional provision ใน ephemeral QA directory; Manifest มีครบ 4 engines. สถานะยังเป็น `archive_audited_not_inference_verified`.
- Real-ESRGAN และ Real-CUGAN ใช้ recorded CI SHA256 pins เพราะไม่มี publisher-published release digest; Waifu2x และ Anime4KCPP มี publisher digest. `license_redistribution_approved=false` ยังคงเดิม; ห้ามฝัง Binary/Weights หรือแจกจ่ายต่อโดยไม่มีสิทธิ์ที่ยืนยันแล้ว.

### Native CLI smoke — diagnostic เท่านั้น

- Native CLI Smoke #179: [Actions run 43344275898](https://github.com/niyomse-collab/niyom/actions/runs/43344275898).
- Real-CUGAN และ Anime4KCPP native processes สร้าง synthetic outputs ที่ผ่าน output/metadata checks ใน Hosted Windows.
- Real-ESRGAN และ Waifu2x ถูก block ด้วย `vkCreateInstance failed -9` บน Hosted Runner.
- NVML ไม่พร้อมใช้งาน; physical adapter verification **0/4**; `real_inference_verified=false`, `runtime_device_use_verified=false`, `quality_improvement_verified=false`. Workflow SUCCESS หมายถึง diagnostic จัดประเภท Vulkan host limitation ได้ ไม่ใช่ Four-Engine GPU acceptance.

### Frozen build warnings ที่ตรวจจาก job log

- PyInstaller บันทึก missing `nvcuda.dll` (เป็น NVIDIA driver-provided runtime บนเครื่องปลายทาง), `tbb12.dll` (dependency ของ optional Numba TBB backend), และ hidden imports `pycparser.lextab`, `pycparser.yacctab`, `scipy.special._cdflib`; ยังไม่มีหลักฐานว่า warning เหล่านี้ทำให้ Candidate import/provision dispatch ล้ม.
- ห้ามคัดลอก `nvcuda.dll` หรือ `tbb12.dll` จากเครื่องอื่นมาใส่ Installer โดยเดา; ตรวจ dependency/runtime บนเครื่องจริงก่อน และไม่ bundle NVIDIA driver DLL.
- Last recorded shop NVIDIA driver remains **451.67 (5 พ.ย. 2569)**. หากยังไม่เปลี่ยน จะต่ำกว่า CUDA 12.x Windows minor-compatibility floor 528.33 และ CUDA 12.8 GA floor 570.65 ของ PyTorch `cu128` path. ต้องตรวจ Driver ปัจจุบันก่อน; CUDA compatibility เป็นคนละเรื่องกับ Vulkan eligibility ของ native NCNN engines.

### ขอบเขต large-image และ GPU ที่ยังไม่รับรอง

- Large auxiliary path >18 MP ยังจำกัด PNG RGB/RGBA + accepted V2 PNG; JPEG/TIFF/CMYK/PDF/PSD ขนาดใหญ่คง V2-only.
- Large path ทำ native 2x pass แบบ tiled; 4x/8x เป็น target geometry จาก half-target seed + native 2x pass ไม่ใช่ native 4x/8x หรือ multi-pass.
- Prelaunch free-VRAM threshold 2,048 MiB และ runtime whole-device reserve 512 MiB; ยังไม่ใช่ hard 6 GB cap หรือผล peak-VRAM stress บน GTX 1660 Ti.
- ยังไม่มีผลติดตั้ง Candidate #696 บน shop PC, per-child-PID-to-GPU 4/4, >18 MP real GPU/cancel stress, A/B ภาพจริง, Photoshop/MainTop/RIP.

### Shop evidence gate

- ยังไม่เรียก self-hosted `niyom-shop-gpu` runner ในการตรวจครั้งนี้. Workflow ต้องมีการติดตั้ง Candidate #696 ใน Windows account เดียวกับ Manifest และต้องส่ง `confirm_shop_gpu=yes` พร้อม Source commit 40 ตัวจาก `BUILD_PROOF.txt`; push-marker route ต้องใช้ marker ที่อนุมัติชัดเจน. การอัปเดตเอกสารนี้ไม่ใส่ consent marker และไม่ schedule self-hosted job.
- Shop diagnostic ใช้ synthetic RGB/RGBA เท่านั้น; เก็บ JSON evidence เท่านั้น; ห้ามอัปโหลดภาพลูกค้า. Synthetic GPU acceptance ไม่รับรอง visual/print quality.
- V2 ยังคงเป็น accepted Master; `quality_certified=false`. PR #20 คง OPEN/DRAFT/UNMERGED; ไม่แก้ V1/V2 Stable, ไม่ merge และไม่ release.


## 13 พฤศจิกายน 2569 15:02 ICT — Candidate #697 exact-head verification

ส่วนนี้บันทึกผลจาก GitHub Actions สำหรับ PR HEAD `50eeefb2f4c6511f17220d9016f5a51caf653e5c` โดยไม่เปลี่ยน runtime source หรือยกระดับผล Hosted Runner ให้เป็น Shop GPU acceptance

### Exact source / Windows Candidate

- PR #20 HEAD: `50eeefb2f4c6511f17220d9016f5a51caf653e5c` (`50eeefb`); PR #20 ยังคง OPEN/DRAFT/UNMERGED และ PR #18 ยังคง OPEN/DRAFT/UNMERGED
- Windows Candidate #697: [Actions run 43386712354](https://github.com/niyomse-collab/niyom/actions/runs/43386712354), สำเร็จทั้ง `bridge-tests` และ `windows-v2-candidate` (2/2 jobs)
- Bridge/Fusion/coordination: **326 passed**; privacy/provisioning/hash: **63 passed**
- Frozen checks ผ่าน: V2 import smoke, packaged provisioning `--check-only` แบบไม่ดาวน์โหลด/ไม่เขียน Manifest, isolated consented cache cleanup, packaged diagnostic `--help`, BUILD_PROOF/source identity และ installer-slice SHA256 ทุกส่วน
- Installer SHA256: `9fca96d6b6d37a5f8d7fff966abcdb7194425307c27718f0d554ec951f0e8564`
- Artifact ID `14020137320`; size **2,584,555,121 bytes**; ZIP SHA256 `57c8016f62d37506bb39c21195bf1ffe7c455961a115e044321b2d7aed261d4d`; expires **20 พ.ย. 2569 14:59:19 ICT**.
- [Experimental Candidate #697](https://github.com/niyomse-collab/niyom/actions/runs/43386712354/artifacts/14020137320). เป็นแพ็กเกจทดลอง ไม่ใช่ Release และไม่ใช่การรับรองติดตั้ง/คุณภาพบนเครื่องร้าน

### Independent Core regression

- [Core run 43386712415](https://github.com/niyomse-collab/niyom/actions/runs/43386712415) checkout PR merge commit `9952252` ซึ่งรวม PR HEAD `50eeefb` เข้ากับฐาน PR #18
- Windows: **975 passed / 1 skipped**; Ubuntu: **973 passed / 3 skipped**; `compileall` ผ่านทั้งสองระบบ

### Official archives / provenance

- [Official Archive Audit #144](https://github.com/niyomse-collab/niyom/actions/runs/43386712353) ดาวน์โหลด ZIP ทางการทั้งสี่ ตรวจ SHA256, ตรวจสมาชิก ZIP/path, provision แบบ transactional ใน QA ชั่วคราว และสร้าง Manifest ที่โหลดครบ `real_esrgan, waifu2x, real_cugan, anime4k`
- Real-ESRGAN v0.2.5.0: `abc02804e17982a3be33675e4d471e91ea374e65b70167abc09e31acb412802d` (observed CI pin; ไม่มี publisher digest)
- Waifu2x 20250915: `7425be94b94e4c8f37a1e433ac0e0100c43790e2c37418f4b65d8235adfbdc87` (published digest)
- Real-CUGAN 20220728: `c6e08d46c11704b1e3a1ada9ddd591cb5005f52f132136c8633ba25def400e01` (observed CI pin; ไม่มี publisher digest)
- Anime4KCPP v3.2.0: `82897b0f03ddb88ab3d1affb745baf99506cfe3ceffaeaf73796c6dea4077f19` (published digest)
- Audit คง `license_redistribution_approved=false`; ไม่ bundle/commit binaries หรือ weights

### Native CLI Smoke #180 — diagnostic only

- [Actions run 43386712362](https://github.com/niyomse-collab/niyom/actions/runs/43386712362) ใช้ภาพ Synthetic RGB และ RGBA พร้อม ICC/300 DPI; เก็บเฉพาะ JSON evidence
- Real-CUGAN และ Anime4KCPP: native process exit 0 และ synthetic output/metadata checks ผ่านทั้งสองกรณี แต่ actual physical adapter ยังไม่ verified
- Real-ESRGAN: `vkCreateInstance failed -9`, exit `0xFFFFFFFF`
- Waifu2x: `vkCreateInstance failed -9` ร่วมกับ exit `0xC0000005`; classification คือ `vulkan_initialization_failed_with_access_violation`
- Physical adapter verification **0/4**; `real_inference_verified=false`, `runtime_device_use_verified=false`, `quality_improvement_verified=false`
- Workflow SUCCESS หมายถึงจัดประเภทข้อจำกัด Hosted Runner ได้ ไม่ใช่ Four-Engine GPU acceptance หรือคุณภาพเหนือ V2

### Frozen build warnings

- PyInstaller เตือน hidden imports `pycparser.lextab`, `pycparser.yacctab`, `scipy.special._cdflib` ไม่พบ และไม่พบ `nvcuda.dll` / optional `tbb12.dll` บน Hosted Runner
- Build และ packaged dispatch ยังผ่าน; ห้ามคัดลอก NVIDIA driver DLL หรือ TBB runtime จากแหล่งที่ไม่ตรวจสอบเข้า Installer. `nvcuda.dll` ต้องมาจาก NVIDIA driver ที่ติดตั้งบนเครื่องปลายทาง; ตรวจ optional TBB dependency บนเครื่องจริงก่อนตัดสินใจ

### Shop gate / remaining acceptance

- ไม่มี self-hosted `niyom-shop-gpu` job ในรอบนี้. Workflow ต้องมี Candidate ติดตั้งใน Windows account เดียวกับ Manifest และต้องมี explicit consent พร้อม Source SHA 40 ตัว; commit นี้ไม่มี `[shop-gpu-evidence yes candidate=...]` marker
- Driver ร้านที่บันทึกครั้งล่าสุดใน QA record คือ 451.67 (5 พ.ย. 2569); ตรวจ `nvidia-smi` ปัจจุบันก่อนทดสอบ เพราะต่ำกว่า compatibility floor ที่ระบุสำหรับ PyTorch cu128. CUDA และ Vulkan ต้องตรวจแยกกัน
- >18 MP auxiliary path ยังคง PNG RGB/RGBA เท่านั้น; Native inference เป็น 2x หนึ่ง pass. เป้าหมาย 4x/8x ไม่ใช่ Native 4x/8x multi-pass. VRAM preflight 2,048 MiB และ reserve 512 MiB ไม่ใช่ hard 6 GB cap
- A/B ภาพจริง, per-process GPU 4/4, peak VRAM, large-image stress, Photoshop/MainTop/RIP และ print quality ยังไม่ผ่านการรับรอง

### Preservation

- PR #18 vs PR #20 protected face/GFPGAN Blob SHA ยังคงตรงกัน **5/5**: `signprint_ai/face_module/face_protection.py`, `signprint_ai/face_module/__init__.py`, `signprint_ai/large_faces.py`, `signprint_ai/v211_face_contract.py`, `tests/test_v211_face_contract.py`
- Optional HAT Assist execution route ยังคง disabled ใน PR #20 และเป็น compatibility difference ที่ต้อง review แยกก่อน merge
- ไม่มี V1/V2 Stable changes, customer images, binaries หรือ weights committed; V2 ยังคง accepted Master; `quality_certified=false`. ไม่มี merge/release


### Consent-flow correction — verified against current app source (13 พ.ย. 2569)

การตรวจ Source ซ้ำพบว่า current HEAD มี **สองช่องทางยินยอมสำหรับชุด AI ทั้งสี่** ไม่ใช่ installer-only:

1. **Installer consent:** Inno Setup task `installfourai` เป็น unchecked-by-default. หากผู้ใช้เลือก task จะเรียก packaged provisioning ก่อนเปิด Editor; เปิด Editor อัตโนมัติเฉพาะเมื่อมี completion marker ใหม่และไม่มี pending marker
2. **Editor first-launch consent:** หากข้าม task ใน Installer และยังไม่มี Manifest ที่ตรวจครบ/decline marker, `app_v2.py` เรียก `_offer_v211_four_ai_setup` หลังหน้าต่างเริ่มทำงาน. `initial_setup_state()` ตรวจเฉพาะ local files โดยไม่เริ่ม network; Yes/No dialog มีค่าเริ่มต้น No. Yes เริ่ม provisioning บน background worker; No เขียน `setup-declined.flag` เพื่อไม่ถามซ้ำ

เมื่อ Manifest ผ่านการตรวจแล้ว Editor ไม่ถามซ้ำ และงาน V2.1.1 ที่เข้าเงื่อนไขเรียกทั้งสี่แบบ coordinated path อัตโนมัติ ไม่มีปุ่มเลือก Engine แยก. `NIYOMSIL_V211_FOUR_AI=0` เป็น explicit opt-out. หากผู้ใช้ปฏิเสธหรือ setup ล้มเหลว V2 เดิมยังใช้งานได้; ไม่มี network download ก่อน affirmative consent.

**Correction:** ข้อความใน comment วันที่ 11 พ.ย. 2569 ที่ระบุว่า Editor first-launch prompt ถูกถอดออกและ Installer เป็น consent surface เพียงจุดเดียว เป็นสถานะชั่วคราวใน commit `f250184`; source ปัจจุบันและการเปลี่ยนแปลงวันที่ 12 พ.ย. ได้นำ Editor first-launch consent กลับมาแล้ว. ให้ยึด Source ที่ตรวจใน PR HEAD `50eeefb` และ regression tests ปัจจุบันแทนข้อความย้อนหลังดังกล่าว.


## 13 พฤศจิกายน 2569 17:19 ICT — Candidate #710 exact-head verification

บันทึกนี้อัปเดตเฉพาะเอกสาร QA หลังตรวจ GitHub PR, commit-bound Actions, job logs, artifact metadata, archive audit, synthetic native CLI report และ protected GFPGAN blobs อีกครั้ง

### PR / Source identity
- PR #20 HEAD: `fcf40db64483796a3a8f44403238970a387784a4` (`fcf40db`) บน `work/v211-four-engine-v2-bridge-20261103`; base / PR #18 HEAD: `288dd8501c230a118d9a7e60d2522a2cc7411bcc`.
- PR #20 และ PR #18 ยังคง OPEN / DRAFT / UNMERGED; ไม่มี merge/release.
- Changed files ของ PR #20 มี 70 paths; ไม่พบ executable, DLL, archive, model weights หรือ V1-named paths.

### Windows Candidate #710 — exact PR HEAD
- [Actions run 43391215545](https://github.com/niyomse-collab/niyom/actions/runs/43391215545) ใช้ source SHA ตรงกับ PR HEAD `fcf40db`; `bridge-tests` และ `windows-v2-candidate` สำเร็จทั้ง 2/2 jobs.
- Bridge/Fusion/coordination: **326 passed**; privacy/provisioning/manifest-hash: **63 passed**.
- Frozen checks ผ่าน: V2 import smoke, packaged provisioning `--check-only` แบบไม่ดาวน์โหลด/ไม่เขียน Manifest, consented cache cleanup ใน isolated profile, diagnostic `--help`, BUILD_PROOF/source SHA และ installer-slice SHA256 ทุกส่วน.
- Installer SHA256: `b2ae53c57c56494e9749bcaf1192fb8bb340c39b9ad4e6614d8620ac7d1d2bea`.
- Artifact ID `14022194035`; size **2,584,447,083 bytes**; ZIP SHA256 `3f88aea9712b2473f6270b774a5b302b3ce6fb568312409db7f464d92704fa2c`; expires **20 พ.ย. 2569 15:44:40 ICT**.
- [Experimental Candidate #710](https://github.com/niyomse-collab/niyom/actions/runs/43391215545/artifacts/14022194035). เป็น Frozen build/provenance pass เท่านั้น ไม่ใช่การรับรองติดตั้งแบบ interactive, Native GPU 4/4, VRAM, visual A/B หรือคุณภาพงานพิมพ์บนเครื่องร้าน.

### Independent Core regression
- [Actions run 43391215490](https://github.com/niyomse-collab/niyom/actions/runs/43391215490): Windows **975 passed / 1 skipped**; Ubuntu **973 passed / 3 skipped**; compileall ผ่านทั้งสองระบบ.

### Official archive audit — PR workflow merge context
- [Actions run 43391215373](https://github.com/niyomse-collab/niyom/actions/runs/43391215373) ตรวจ ZIP ทางการทั้งสี่, SHA256, ZIP member/path safety และ transactional provisioning ใน ephemeral QA directory; Manifest โหลดครบ `real_esrgan, waifu2x, real_cugan, anime4k`.
- Real-ESRGAN v0.2.5.0: `abc02804e17982a3be33675e4d471e91ea374e65b70167abc09e31acb412802d` (observed CI pin; ไม่มี publisher digest).
- Waifu2x 20250915: `7425be94b94e4c8f37a1e433ac0e0100c43790e2c37418f4b65d8235adfbdc87` (published digest).
- Real-CUGAN 20220728: `c6e08d46c11704b1e3a1ada9ddd591cb5005f52f132136c8633ba25def400e01` (observed CI pin; ไม่มี publisher digest).
- Anime4KCPP v3.2.0: `82897b0f03ddb88ab3d1affb745baf99506cfe3ceffaeaf73796c6dea4077f19` (published digest).
- Audit คง `real_inference_verified=false` และ `license_redistribution_approved=false`; ไม่ bundle/commit binaries หรือ weights.

### Native CLI Smoke #193 — diagnostic only
- [Actions run 43391215415](https://github.com/niyomse-collab/niyom/actions/runs/43391215415) ใช้ synthetic RGB และ RGBA/ICC/300-DPI inputs; เก็บ JSON evidence เท่านั้น.
- Real-CUGAN และ Anime4KCPP: native process start, exit code 0 และ synthetic 2x output checks ผ่าน; physical adapter ยังไม่ verified.
- Real-ESRGAN: `vkCreateInstance failed -9`, exit `0xFFFFFFFF`.
- Waifu2x: `vkCreateInstance failed -9` และ exit `0xC0000005`; จัดประเภท `vulkan_initialization_failed_with_access_violation`.
- Physical adapter verification **0/4**; `real_inference_verified=false`, `runtime_device_use_verified=false`, `quality_improvement_verified=false`. Workflow SUCCESS หมายถึงจำแนก Hosted Runner limitation ได้ ไม่ใช่ GPU/quality pass บน GTX 1660 Ti.

### Frozen build warnings
- PyInstaller warnings: missing hidden imports `pycparser.lextab`, `pycparser.yacctab`, `scipy.special._cdflib`; `nvcuda.dll` not found on Hosted Runner; optional Numba TBB dependency `tbb12.dll` not found; optional `expecttest` missing during Torch test-submodule collection.
- Packaged import and dispatch checks passed. ยังไม่มีหลักฐานว่า warnings เหล่านี้ทำให้ runtime บนเครื่องร้านล้ม; ห้าม bundle NVIDIA driver DLL หรือ TBB DLL จากแหล่งที่ไม่ยืนยัน. ตรวจ dependency บนเครื่องจริงก่อนตัดสินใจ.

### Preservation / remaining gates
- PR #18 vs PR #20 protected face/GFPGAN Blob SHA ตรงกัน **5/5**: `face_protection.py`, `face_module/__init__.py`, `large_faces.py`, `v211_face_contract.py`, `test_v211_face_contract.py`.
- Optional HAT Assist execution route ยัง disabled ใน PR #20; ต้อง review compatibility แยกก่อน merge.
- ไม่มี shop self-hosted GPU run ในรอบนี้; ไม่มี affirmative shop-GPU consent marker.
- >18 MP auxiliary route ยังคง PNG RGB/RGBA only; JPEG/TIFF/CMYK/PDF/PSD ขนาดใหญ่ยัง V2-only. Native tile pass เป็น 2x บน half-target seed; ไม่ใช่ native 4x/8x multi-pass. VRAM preflight 2,048 MiB + reserve 512 MiB ไม่ใช่ hard 6 GB cap.
- Per-process GPU 4/4, peak VRAM, real >18 MP stress/cancel, visual A/B, Photoshop/MainTop/RIP และ print quality ยังไม่ผ่านการรับรอง.
- V2 remains accepted Master; `quality_certified=false`. ไม่แก้ V1/V2 Stable, ไม่ merge และไม่ release.


## 14 พฤศจิกายน 2569 13:24 ICT — Candidate #772 และ Shop GPU Evidence Gate

### Exact PR / Candidate
- PR #20 ยังคง OPEN / DRAFT / UNMERGED; HEAD 4d01c56bd378e45eca0b8d015b948f97983a80a7; base 288dd8501c230a118d9a7e60d2522a2cc7411bcc, ตรงกับ PR #18 HEAD.
- Windows Candidate #772 [Actions](https://github.com/niyomse-collab/niyom/actions/runs/43561005867) สร้างจาก source SHA 4d01c56 และสำเร็จ 2/2 jobs.
- Bridge/Fusion/coordination: **348 passed**; privacy/provisioning/manifest/hash: **63 passed**.
- Frozen V2 imports, packaged provisioning --check-only, isolated consented-cache cleanup, diagnostic --help, BigTIFF/libvips smoke, provenance และ installer-slice SHA256 ผ่าน.
- Installer SHA256: 525db9a252ef0b1ff63b1a5cbce8e0ef84ce6d730305daeffcc998430d97deca.
- Artifact ID 14101246519, size **2,584,661,964 bytes**, ZIP SHA256 924e46926df4c94b9f2fe51b19ccb9cd6dcbdfaceaf7017a107ff591e58d00e0; [Experimental Candidate #772](https://github.com/niyomse-collab/niyom/actions/runs/43561005867/artifacts/14101246519), expires **21 พ.ย. 2569 12:44:06 ICT**.
- Candidate #772 เป็น frozen package/provenance pass เท่านั้น ไม่รับรองการติดตั้ง/ถอนการติดตั้งจริง, native GPU 4/4 หรือคุณภาพภาพ.

### Regression / Official assets / Native diagnostic
- Independent Core #1342 [Actions](https://github.com/niyomse-collab/niyom/actions/runs/43561005894): Windows **1005 passed / 1 skipped**; Ubuntu **1003 passed / 3 skipped**; compileall ผ่านทั้งสองระบบ.
- Official Archive Audit #184 [Actions](https://github.com/niyomse-collab/niyom/actions/runs/43561005888): official archives ทั้ง 4 ผ่าน SHA256, safe audit และ transactional provisioning ใน ephemeral QA; all_archives_audited=true, แต่ all_upstream_digests_pinned=false เพราะ Real-ESRGAN/Real-CUGAN ไม่มี publisher digest. license_redistribution_approved=false; ไม่ bundle binaries/weights.
- Native CLI Smoke #232 [Actions](https://github.com/niyomse-collab/niyom/actions/runs/43561005862): Real-CUGAN และ Anime4KCPP สร้าง synthetic 2x outputs; Real-ESRGAN/Waifu2x ล้มบน Hosted Runner ด้วย vkCreateInstance failed -9 (Waifu2x มี 0xC0000005). NVML ไม่พร้อม, physical adapter verification **0/4**, real_inference_verified=false, runtime_device_use_verified=false, quality_improvement_verified=false. Workflow SUCCESS เป็น diagnostic classification ไม่ใช่ GPU/quality acceptance.
- PyInstaller มี non-fatal warnings สำหรับ driver-provided nvcuda.dll และ optional tbb12.dll; ไม่ bundle DLL เหล่านี้จากการคาดเดา.

### BigTIFF / large image scope
- Candidate frozen smoke ตรวจ single-page BigTIFF, streamed libvips seed/QA, multipage TIFF rejection, ICC/DPI, odd crop และ accepted V2 hash preservation ด้วย synthetic files.
- [Historical pre-20 Nov format note; superseded by the final source correction] Current large source and accepted-V2 formats are listed in the final source-correction section. The native tiled runner/fusion still consumes private PNG intermediates. Multipage TIFF, CMYK, PDF/PSD and unsupported bit depths remain V2-only.
- Disk-backed path ใช้ tile/streaming และมี pixel/disk guards; synthetic smoke ไม่ใช่ native >18MP GPU stress หรือ peak-VRAM 6GB proof.
- Native engine ทำ 2x หนึ่ง pass บน half-target seed; target 4x/8x ไม่ใช่ native 4x/8x multi-pass.

### Shop GPU evidence trigger — fail closed
- Commit นี้อัปเดตเฉพาะ QA document ซึ่งเป็น path ที่ระบุใน push.paths ของ v211-four-engine-manual-evidence.yml; commit message มี explicit marker [shop-gpu-evidence yes candidate=4d01c56bd378e45eca0b8d015b948f97983a80a7].
- Evidence job ต้องทำงานเฉพาะ self-hosted Windows runner label niyom-shop-gpu; ไม่มี Hosted Runner fallback. Preflight ตรวจ installed Candidate BUILD_PROOF.txt ให้ตรง source SHA 4d01c56 และต้องพบ verified four-engine manifest ใน LocalAppData ก่อนเปิด native processes.
- ใช้ synthetic RGB/RGBA เท่านั้น; อัปโหลด JSON evidence เท่านั้น; ไม่มี customer artwork, image upload หรือแก้ accepted V2. หาก candidate/manifest/runner/adapter/telemetry ไม่ครบ ให้ fail closed.
- ยังไม่มี run ID หรือ Artifact ของ self-hosted evidence job ที่ตรวจยืนยันได้ ณ เวลาบันทึกนี้; **ยังไม่อ้างว่าได้รัน GPU บนเครื่องร้านแล้ว**.
- แม้ synthetic GPU gate ผ่าน ก็ยืนยันได้เฉพาะ native process/device/metadata/bridge contract; quality_improvement_verified=false, visual_quality_certified=false, print_quality_certified=false ต้องคงไว้.

### Preservation
- PR #20 base SHA ตรงกับ PR #18 head SHA. Protected face/GFPGAN paths ทั้ง 6 รายการจาก PR #18 ไม่อยู่ใน changed-file list ของ PR #20; PR #20 ไม่แก้ไฟล์เหล่านั้น.
- PR #20 / PR #18 ยังคง Draft; ไม่มี V1/V2 Stable changes, merge หรือ release. V2 ยังคงเป็น accepted master.


## 14 พฤศจิกายน 2569 16:05 ICT — Exact-head Candidate #775 และขอรัน Shop GPU Evidence แบบ Synthetic-only

### Candidate / exact source
- PR #20 HEAD ที่ตรวจจาก branch ref: `686b5cbb347864da8e321d75cc8ac61936a2ad09`; compare branch กับ SHA นี้เป็น identical (0 ahead / 0 behind).
- Windows Candidate #775 [GitHub Actions](https://github.com/niyomse-collab/niyom/actions/runs/43568125068) สร้างจาก exact source SHA ข้างต้นและสำเร็จ 2/2 jobs.
- Bridge/Fusion/coordination: **350 passed**; privacy/provisioning/manifest/hash: **63 passed**.
- Frozen V2 imports, BigTIFF/libvips synthetic smoke, packaged provisioning `--check-only` (no download/write), consented cache cleanup, diagnostic `--help`, BUILD_PROOF exact-source verification และ installer-slice SHA256 ผ่าน.
- Installer SHA256: `13283750e699a115d09eef8578a0da80089275902bce92ab7320569e120ddd09`.
- Artifact ID `14103803599`; size **2,584,530,731 bytes**; ZIP SHA256 `cecff21cb3889a8b1484bfed33c206670102a45f7017cfe5752423aadcd57b33`; [Experimental Candidate #775](https://github.com/niyomse-collab/niyom/actions/runs/43568125068/artifacts/14103803599), expires **21 พ.ย. 2569 14:19 ICT**.
- Candidate #775 เป็น frozen packaging/provenance pass; ไม่ใช่หลักฐาน interactive install/uninstall หรือ GPU inference จริง.

### PR merge-result regression / official archives / native CLI

- **แยก SHA ให้ชัด:** Candidate #775 สร้างจาก PR head `686b5cbb347864da8e321d75cc8ac61936a2ad09`; ส่วน Core #1346, Archive #186 และ Native CLI #235 ทำงานบน PR merge-result commit `622dd608a8745c5786e46b7345e97899061cb75a` ซึ่งเป็น merge ของ head `686b5cbb` เข้า base `288dd850` (PR #18). จึงเป็นผลทดสอบ merge-result ของ PR #20 ไม่ใช่ raw-head run; ไม่ควรเรียกรวมว่า exact-head.
- Independent Core #1346 [Actions](https://github.com/niyomse-collab/niyom/actions/runs/43568125048): Windows **1007 passed / 1 skipped**; Ubuntu **1005 passed / 3 skipped**; compileall ผ่านทั้งสองระบบ.
- Official Archive Audit #186 [Actions](https://github.com/niyomse-collab/niyom/actions/runs/43568125087): official archives ทั้งสี่ผ่าน hash/safe-archive audit และ transactional provisioning ลง ephemeral QA; Manifest พบครบ 4 engines. Real-ESRGAN และ Real-CUGAN ใช้ observed CI SHA256 pins (ไม่มี publisher digest); Waifu2x และ Anime4KCPP มี published digest. `model_weights_and_license_certified=false`, `license_redistribution_approved=false`; ไม่ bundle binaries/weights.
- Native CLI Smoke #235 [Actions](https://github.com/niyomse-collab/niyom/actions/runs/43568125089): Real-CUGAN และ Anime4KCPP สร้าง synthetic 2x outputs; Real-ESRGAN และ Waifu2x ถูก block ด้วย hosted-runner `vkCreateInstance failed -9` (Waifu2x ยังมี `0xC0000005`). NVML unavailable; physical adapter verification **0/4**; `real_inference_verified=false`, `runtime_device_use_verified=false`, `quality_improvement_verified=false`. Diagnostic workflow SUCCESS เป็นการจำแนกข้อจำกัด Hosted Runner ไม่ใช่ GPU/quality pass.
- PyInstaller warnings ที่ตรวจจาก Candidate #775: `pycparser.lextab/yacctab`, `scipy.special._cdflib`, driver-provided `nvcuda.dll`, optional Numba `tbb12.dll`. Frozen import/dispatch checks ผ่าน; ยังไม่พบหลักฐานว่า warning เหล่านี้ทำให้ runtime บนเครื่องร้านล้ม. ไม่ bundle NVIDIA driver DLL หรือ TBB DLL จากการคาดเดา; ตรวจ dependency จริงบนเครื่องร้านก่อนตัดสินใจ.

### Shop GPU evidence — exact Candidate #775, synthetic-only
- Commit นี้เปลี่ยนเฉพาะ QA document เพื่อ trigger workflow ที่กำหนด path นี้ไว้; commit message มี explicit marker `[shop-gpu-evidence yes candidate=686b5cbb347864da8e321d75cc8ac61936a2ad09]`.
- Evidence job ใช้เฉพาะ self-hosted Windows runner label `niyom-shop-gpu`; ไม่มี Hosted Runner fallback. Preflight ต้องพบ Candidate #775 ที่ติดตั้งภายใต้ Windows account เดียวกับ runner โดย `BUILD_PROOF.txt` ต้องตรง source SHA ข้างต้น และต้องมี verified four-engine Manifest ใน LocalAppData.
- ใช้เฉพาะ synthetic RGB และ RGBA/ICC/300-DPI images; ไม่มีการอ่าน/อัปโหลดภาพลูกค้า, ไม่มี network download ระหว่าง diagnostic, และ upload ได้เฉพาะ JSON evidence.
- หาก runner, installed Candidate, Manifest, Vulkan/GTX 1660 Ti binding, per-process telemetry หรือ VRAM preflight ไม่ครบ workflow ต้อง fail closed และ V2 ยังคงเป็น accepted output. หาก Candidate #775 ยังไม่ได้ติดตั้งใน shop runner, job จะหยุดที่ preflight ไม่ติดตั้งโปรแกรมแทนผู้ใช้.
- แม้ synthetic GPU gate ผ่าน จะรับรองได้เฉพาะ native process/device/metadata/bridge contract; ไม่ใช่ visual A/B หรือ print certification. `quality_improvement_verified=false`, `visual_quality_certified=false`, `print_quality_certified=false` ต้องคงไว้.

### Remaining gates / preservation
- >18 MP native GPU stress, 6 GB hard cap/peak VRAM, cancel-under-load, visual A/B (people/animals/objects/Thai/English/Chinese/flat/gradient/alpha), Photoshop/MainTop/RIP และ physical print quality ยังไม่รับรอง.
- PR #18 protected GFPGAN/face files remain byte-identical **5/5** against PR #20 (Blob SHA checked at exact HEAD); optional HAT Assist execution remains a separate compatibility difference, not silently restored.
- PR #20 / PR #18 remain OPEN / DRAFT / UNMERGED. V1/V2 Stable unchanged; no customer images, native binaries or weights committed; no merge/release. V2 remains accepted master; `quality_certified=false`.


## 14 พฤศจิกายน 2569 — Runtime VRAM device-wide budget guard

- เพิ่มเพดานการใช้งานหน่วยความจำ GPU แบบ device-wide **6,144 MiB** และรักษาพื้นที่สำรอง **512 MiB**; บน GTX 1660 Ti ที่รายงานหน่วยความจำ 6 GiB จะยอมรับค่า device-used สูงสุดที่ตรวจวัดได้ **5,632 MiB**.
- งบนี้นับรวม Windows Desktop, Photoshop และโปรแกรม GPU อื่นทั้งหมด ไม่ใช่โควตาเฉพาะ process ของ AI. หากเครื่องมี VRAM รวมต่ำกว่า 6 GiB เพดานใช้งานจะลดตามความจุจริง.
- Native subprocess จะสุ่มตรวจ NVML ระหว่างทำงาน (รอบ polling ประมาณ 50 ms); หาก telemetry หาย, free ต่ำกว่า reserve หรือ device-used เกิน budget จะหยุด process tree, ลบ partial output และไม่เผยแพร่ QA candidate.
- รายงาน JSON จะแสดง budget, maximum device-used, peak sampled device-used, minimum free และสถานะต่อ Engine. Shop GPU Evidence ต้องมีอย่างน้อยสอง sample ต่อ Engine และผ่านทั้งสี่ตัว.
- **ข้อจำกัดสำคัญ:** นี่เป็น sampled monitor-and-terminate guard ไม่ใช่ driver-level hard allocation quota; GPU อาจใช้หน่วยความจำเกินชั่วคราวระหว่าง sample ได้. ต้องทดสอบ peak VRAM/การยกเลิกระหว่างโหลดบนเครื่องร้านจริงก่อนรับรอง.
- การเปลี่ยนแปลงนี้อยู่เฉพาะ PR #20 และไม่เปลี่ยน V1/V2 Stable. V2 ที่บันทึกแล้วคงเป็น accepted master หาก guard ปฏิเสธงานเสริม.


## 14 พฤศจิกายน 2569 — แยกค่า VRAM ที่วัดได้ออกจากเพดานนโยบาย

- `runtime_vram_peak_used_mib` คือค่าสูงสุดของหน่วยความจำ GPU ที่สังเกตได้จากตัวอย่าง NVML ระหว่าง Process ทำงาน เป็น sampled peak ไม่ใช่ hardware trace แบบทุก microsecond
- `runtime_vram_max_allowed_device_used_mib` คือเพดานการใช้งานที่อนุญาตตามนโยบาย 6,144 MiB budget หัก 512 MiB reserve (สูงสุด 5,632 MiB บน Adapter 6 GiB) ไม่ใช่ค่าการใช้งานจริง
- ฟิลด์เดิม `runtime_vram_max_device_used_mib` ยังคงอยู่เป็น alias เพื่อความเข้ากันได้กับรายงานเก่า แต่ตัวตรวจรับรองใหม่ต้องใช้ชื่อ `runtime_vram_max_allowed_device_used_mib` เท่านั้น
- รายงาน `shop_gpu_diagnostic.json` ใช้ชื่อ `maximum_allowed_device_used_mib` เพื่อไม่ให้ตีความเพดานนโยบายเป็น Peak VRAM ที่วัดได้
- การตรวจยังเป็น sampled monitor-and-terminate guard แบบ Device-wide; ไม่ใช่ Driver-enforced per-process hard quota และอาจ overshoot ระหว่าง sample ได้



## 15 พฤศจิกายน 2569 00:15 ICT — Synthetic-only shop GPU authorization for Candidate #814

- ผู้ใช้สั่งให้ทดสอบ Native AI ทั้งสี่บน Windows ที่มี Vulkan GPU และให้ QA แบบ fail-closed; บันทึกการอนุญาตนี้จำกัดเฉพาะ **synthetic-only diagnostic** ของ Candidate #814 ไม่ใช่การอนุญาตใช้ภาพลูกค้าหรือรับรองคุณภาพงานพิมพ์
- Installed candidate source SHA ที่อนุญาต: `56820b5e34109d5dee60f7be1912028edbc9ad47` (Windows Candidate #814). Self-hosted workflow ต้องตรวจ `BUILD_PROOF.txt` ของโปรแกรมที่ติดตั้งให้ตรง SHA นี้ก่อนเรียก diagnostic; หากไม่ตรง, ไม่มี installation/manifest, หรือ runner ไม่พร้อม ให้ fail closed และไม่มี hosted fallback.
- ขอบเขต: synthetic RGB และ RGBA/ICC/300-DPI เท่านั้น; ตรวจ Vulkan/NVIDIA inventory, unique GTX 1660 Ti binding, live PID-to-adapter telemetry ของทั้งสี่ Engine, native 2x outputs, bridge/fusion contract, sampled device-wide VRAM budget 6,144 MiB พร้อม reserve 512 MiB, cancellation/cleanup และ privacy flags.
- ห้ามใช้ customer artwork, ห้ามอ่าน/อัปโหลด/เก็บภาพผู้ใช้, ห้ามดาวน์โหลดโมเดลระหว่าง diagnostic, ห้ามแก้ accepted V2 output. Workflow เก็บเฉพาะ JSON evidence และลบ workspace ชั่วคราว.
- ผลที่ผ่านจะยืนยันเฉพาะ synthetic native inference/device/VRAM/bridge contract บนเครื่องที่รันจริง; ต้องคง `quality_improvement_verified=false`, `visual_quality_certified=false`, `print_quality_certified=false` จนกว่าจะมี A/B ภาพจริงที่ผู้ใช้ตรวจและอนุมัติ.

---

## 15 พฤศจิกายน 2569 03:54 ICT — re-dispatch synthetic-only shop GPU evidence for Candidate #814

- Reuse the existing affirmative authorization for the **same installed Candidate #814** only: `56820b5e34109d5dee60f7be1912028edbc9ad47`.
- The previous push-triggered run #44 remained Pending with zero jobs. The concurrency observability correction is now present in the current workflow; run #45 confirmed the hosted status job can finish independently, while its evidence job was correctly skipped because it had no consent marker.
- This documentation-only commit carries the same explicit marker: `[shop-gpu-evidence yes candidate=56820b5e34109d5dee60f7be1912028edbc9ad47]`. It does **not** authorize Candidate #815, #816, or any later build.
- The evidence workflow must verify the shop installation's `BUILD_PROOF.txt`, four-engine manifest, executable hash, per-process GTX 1660 Ti adapter telemetry, 6 GiB budget / 512 MiB reserve, and synthetic RGB/RGBA/ICC/300-DPI outputs. If Candidate #814 is not installed or the dedicated shop runner is unavailable, the job must remain blocked/fail closed.
- Scope remains synthetic-only: no customer images, no network downloads, no image uploads or retention, no accepted V2 output changes. A passing synthetic diagnostic does not certify visual or print quality.
- Only this QA document is changed. PR #20 remains Draft; PR #18/V2/GFPGAN, V1 and accepted V2 remain untouched. No merge or release.


## 15 พฤศจิกายน 2569 12:53 ICT — Synthetic-only shop GPU evidence authorization for Candidate #828

- ผู้ใช้สั่งให้ดำเนินการทดสอบ Native AI ทั้งสี่บน Windows ที่มี Vulkan GPU พร้อม QA แบบ fail-closed; การอนุญาตครั้งนี้จำกัดเฉพาะ **synthetic-only diagnostic ของ Candidate #828** ไม่ใช่การอนุญาตใช้ภาพลูกค้า ไม่ใช่การรับรองคุณภาพภาพ และไม่ใช่การอนุมัติ Merge/Release.
- Installed candidate source SHA ที่อนุญาต: `b2ef5aec1e6753b4e4abcbb611fe46b5c349106b`. Candidate #828 [Actions](https://github.com/niyomse-collab/niyom/actions/runs/43678965614) สำเร็จ 2/2 jobs; installer SHA256 `ab0d45bde39858effff6aa576a9e969382777aa18182cb9b780be88e65e5b2c5`; artifact ID `14148700319`. Self-hosted preflight ต้องพบ installed `BUILD_PROOF.txt` ที่ตรง SHA นี้และ verified four-engine Manifest ใน LocalAppData ของ Windows account เดียวกับ runner; หากไม่ตรงหรือไม่มีไฟล์ ให้หยุดก่อนเรียก Native Process.
- Push marker นี้อนุญาตให้ workflow ตรวจ Candidate #828 ที่ติดตั้งอยู่แล้วเท่านั้น; workflow ไม่ติดตั้ง Candidate แทนผู้ใช้, ไม่ดาวน์โหลดโมเดล, ไม่แก้โปรแกรมหรือ driver, และไม่มี Hosted Runner fallback.
- ขอบเขตข้อมูล: synthetic RGB และ RGBA/ICC/300-DPI เท่านั้น; ห้ามอ่าน/อัปโหลด/เก็บภาพลูกค้า; อัปโหลดได้เฉพาะ JSON evidence และลบ workspace ชั่วคราว.
- เกณฑ์ fail-closed: ต้องตรวจ Manifest/hash, Vulkan/NVIDIA inventory, unique GTX 1660 Ti binding, PID-to-adapter evidence ของ child process ทุกตัว, native 2x outputs ของทั้งสี่, Bridge/Fusion contract, device-wide VRAM budget 6,144 MiB พร้อม reserve 512 MiB, cancellation/cleanup และ privacy flags. ถ้าขาดหลักฐานข้อใด ให้ workflow fail และ V2 ยังคงเป็น accepted output.
- แม้ synthetic GPU gate ผ่าน จะยืนยันได้เฉพาะ native process/device/VRAM/bridge contract บนเครื่องที่รันจริง; ต้องคง `quality_improvement_verified=false`, `visual_quality_certified=false`, `print_quality_certified=false` จนกว่าจะมี A/B ภาพจริงที่ตรวจโดยผู้ใช้และการทดสอบพิมพ์.
- Candidate #828 hosted Native CLI Smoke #274 ยังคงเป็น diagnostic เท่านั้น: Real-CUGAN/Anime4KCPP synthetic 2x outputs ผ่าน แต่ adapter use ไม่ได้ยืนยัน; Real-ESRGAN/Waifu2x ถูก block ด้วย hosted-runner Vulkan initialization. ห้ามนำผล Hosted Runner มาแทนผล Shop GPU.


## 15 พฤศจิกายน 2569 16:59 ICT — Synthetic-only shop GPU authorization for Candidate #838

- คำสั่งพัฒนาต่อของเจ้าของโครงการอนุญาตให้ทดสอบ Native AI ทั้งสี่บน Windows 11 GTX 1660 Ti ที่มี Vulkan โดยใช้ **synthetic-only diagnostic** แบบ fail-closed สำหรับ Candidate #838 เท่านั้น; ไม่ใช่การอนุญาตใช้ภาพลูกค้า ไม่ใช่การรับรองคุณภาพ และไม่ใช่การอนุมัติ Merge/Release.
- Candidate source SHA: `f330203a353fa23855818206e6ea6f5a39ca444e`; Windows Candidate #838 [Actions](https://github.com/niyomse-collab/niyom/actions/runs/43690524869) สำเร็จ 2/2 jobs. Installer SHA256: `ae44ff036ecdae7e392bab693bae1cd2bf55196ae8acfbf247193505b1502a0b`; artifact ID `14153190406`; ZIP SHA256 `ddb09dd9eed0e2b9c93c1c5196b4263a5dbac2bcf9f3cf0335c2ff016662a834`; artifact expires **22 พฤศจิกายน 2569 15:01:38 ICT**. [ดาวน์โหลด Candidate #838](https://github.com/niyomse-collab/niyom/actions/runs/43690524869/artifacts/14153190406).
- การอนุญาตนี้ผูกกับ Candidate #838 เท่านั้น. Self-hosted preflight ต้องพบโปรแกรมที่ติดตั้งแล้วใน Windows profile เดียวกับ runner, ตรวจ `BUILD_PROOF.txt` ให้ตรง source SHA, ตรวจ executable SHA256 และ verified four-engine Manifest; หากไม่มี Runner, ไม่พบ Candidate #838, Manifest/hash ไม่ตรง หรือ GPU evidence ไม่ครบ ให้คงสถานะ pending/fail และห้ามใช้ Hosted Runner แทน.
- Push marker นี้เป็น **documentation-only commit** ที่ตามหลัง Candidate #838; workflow ต้องยอมรับเฉพาะความต่างของ QA document/workflow/test contract ตาม allow-list. ห้ามเปลี่ยน Source, Spec, Installer, Manifest หรือ Model ระหว่างใช้ Candidate นี้.
- ขอบเขตทดสอบ: synthetic RGB และ RGBA/ICC/300-DPI; Real-ESRGAN, Waifu2x และ Real-CUGAN ต้อง bind Vulkan `-g` ไปยัง GTX 1660 Ti; Anime4KCPP ต้องเลือก CUDA/OpenCL `-p/-d` แยกต่างหาก. ต้องมี live PID-to-adapter evidence ของ child process ทุกตัว, DXGI LUID เมื่อใช้ WDDM fallback, sampled device-wide VRAM budget 6,144 MiB พร้อม reserve 512 MiB, native output validation, bridge/fusion contract, cancellation/cleanup และ privacy flags.
- ห้ามอ่าน/อัปโหลด/เก็บภาพลูกค้า, ห้ามดาวน์โหลดโมเดลระหว่าง diagnostic, ห้ามแก้ accepted V2 output. อัปโหลดได้เฉพาะ JSON evidence และลบ workspace ชั่วคราว.
- Shop GPU Evidence #47 เดิมผูกกับ Candidate #828 (`b2ef5aec1e6753b4e4abcbb611fe46b5c349106b`) และยัง Queued; ห้ามนำมาใช้รับรอง Candidate #838. การทดสอบ Candidate #838 ต้องมี run ใหม่ที่ตรวจ source SHA ตามบันทึกนี้.
- แม้ Synthetic GPU gate ผ่าน จะรับรองได้เฉพาะ native process/device/VRAM/bridge contract บนเครื่องที่รันจริงเท่านั้น; ต้องคง `quality_improvement_verified=false`, `visual_quality_certified=false`, `print_quality_certified=false` จนกว่าจะมี A/B ภาพจริงที่เจ้าของตรวจและอนุมัติ.


## 16 พฤศจิกายน 2569 — Source correction: large TIFF and runtime GPU binding

บันทึกส่วนก่อนหน้านี้บางย่อหน้าเป็นประวัติของ implementation รุ่นก่อนหน้า ให้ยึดพฤติกรรมจาก Source HEAD ปัจจุบันดังนี้:

- **Large image >18 MP (historical summary superseded by the final source correction):** The current allowlists are `_LARGE_STREAMED_SOURCE_FORMATS` and `_LARGE_STREAMED_V2_FORMATS` in `signprint_ai/v211_four_engine_bridge.py`. Source inputs accept RGB/RGBA 8-bit PNG/JPEG/WebP/single-page TIFF/BigTIFF; accepted V2 rasters accept PNG/JPEG/single-page TIFF/BigTIFF. libvips creates private PNG seed/reference intermediates, and native tiled inference/fusion consumes PNG. Multi-page TIFF, CMYK and unsupported bit depths remain V2-only.
- **Native scale:** เป้าหมาย 2x/3x/4x/8x หรือ anisotropic เป็นขนาดปลายทางของ V2 canvas; native executable แต่ละตัวทำเพียงหนึ่ง 2x pass บน seed ครึ่งขนาดของ V2 target. จึงไม่ใช่ native 4x/8x หรือ multi-pass inference. Disk-backed tiled runner จำกัด native pass ที่ 2x และตรวจ overlap/seam ก่อน fusion.
- **GPU binding:** persistent installed manifest ไม่จำเป็นต้องมี device index คงที่. ก่อนเริ่มงาน Bridge สร้าง ephemeral bound manifest: Real-ESRGAN, Waifu2x และ Real-CUGAN ได้ Vulkan `-g` index ที่ตรวจพบแบบไม่กำกวม; Anime4KCPP ได้ processor `-p cuda` หรือ `-p opencl` และ device `-d` จาก inventory ของ Anime4KCPP. ไฟล์ manifest ที่ติดตั้งถาวรไม่ถูกแก้ไข. การเห็นชื่อ adapter ใน inventory หรือการตั้งค่า CLI ยังไม่ใช่หลักฐาน runtime; ต้องตรวจ PID/backend telemetry ระหว่าง process จริงของแต่ละ Engine.
- **Backend distinction:** Anime4KCPP ไม่ใช่ NCNN/Vulkan. การตรวจ Vulkan readiness ใช้กับสาม NCNN engines เท่านั้น; Anime4KCPP ต้องพิสูจน์ CUDA/OpenCL device ที่เลือกและ telemetry ของ process แยกต่างหาก. ข้อความก่อนหน้าที่บอกว่า runtime manifest ไม่ส่ง `-p/-d` ให้ Anime4KCPP เป็นข้อมูลของ manifest ก่อน runtime binding.
- **Acceptance remains unchanged:** Synthetic/hosted CI ไม่รับรอง native GPU 4/4, 6 GB VRAM stress, ภาพจริง A/B, Photoshop, MainTop RIP หรือ print quality. QA sidecar ยังต้องผ่าน contribution จากทั้งสี่ Engine และ live per-process adapter evidence; accepted V2 raster ไม่ถูกแทนที่.

## 17 พฤศจิกายน 2569 — แยก DXGI adapter ที่ไม่พบออกจากกรณีชื่อซ้ำ

- Native CLI Smoke #339 บน GitHub-hosted Windows รายงาน `target_dxgi_adapter_not_unique` ระหว่าง NVML/WDDM telemetry; status เดิมใช้ทั้งกรณีไม่พบ GTX 1660 Ti ใน DXGI inventory และกรณีพบหลายรายการ จึงบอกสาเหตุไม่ชัด
- ปรับเป็น `target_dxgi_adapter_missing` เมื่อไม่พบ NVIDIA DXGI adapter ที่ตรงกับเป้าหมาย และ `target_dxgi_adapter_ambiguous` เมื่อพบมากกว่าหนึ่งรายการ ทั้งสองกรณียังคง fail-closed และยังไม่ยืนยัน PID-to-GPU; legacy status เดิมยังถูกจัดเป็น conflict เพื่ออ่านหลักฐานเก่าได้
- การแก้ไขนี้ปรับเฉพาะการจำแนก telemetry ไม่ได้เปลี่ยนวิธีเลือก GPU, ไม่ข้าม VRAM guard และไม่ทำให้ Hosted Runner กลายเป็นหลักฐาน GPU ของเครื่องร้าน
- Regression เพิ่มทั้ง missing/ambiguous classification และตรวจว่าแต่ละสถานะยกเลิก positive sample ก่อนหน้าได้
## 17 พฤศจิกายน 2569 — ป้องกัน DXGI Adapter LUID ที่ผิดรูปแบบ

- _target_dxgi_luid() รับเฉพาะ LUID แบบ tuple 2 ค่า ซึ่งแต่ละค่าเป็น integer unsigned 32-bit; ปฏิเสธค่าที่หายไป, tuple ผิดขนาด, boolean, ค่าติดลบ และค่าที่เกิน 32-bit ด้วยสถานะ target_dxgi_adapter_luid_invalid.
- เมื่อ WDDM activity ยังรายงาน PID แต่ DXGI inventory ไม่มีหลักฐานที่ตรวจสอบได้ ผลลัพธ์จะส่งต่อสถานะ DXGI ที่แท้จริง เช่น dxgi_adapter_enumeration_unavailable หรือ target_dxgi_adapter_luid_invalid แทนการแสดงเพียง gpu_engine_activity_observed; ทุกกรณียังคง verified=false และ vram_verified=false.
- Regression เพิ่มกรณี LUID หาย/ผิดรูปแบบและตรวจว่าไม่มี positive GPU evidence หลุดผ่าน.
- Source commit: 5a120b49862e05f4892acdd8df2bbc2ed35ffacd; test commit: 9f607d570ed903445fc1baac49e9fd563246bec6.
- Core #1505 ผ่าน Windows 1,059 passed / 1 skipped และ Ubuntu 1,057 passed / 3 skipped; Candidate #915 ผ่าน Bridge/Fusion/Privacy/Provisioning tests แล้ว โดย Frozen Windows build ยังทำงานอยู่ ณ เวลาบันทึกนี้.
- การเปลี่ยนแปลงนี้เป็นการตรวจหลักฐาน telemetry เท่านั้น ไม่ทำให้ Hosted Runner ยืนยัน GPU ของร้าน และไม่เปลี่ยน V1/V2 Stable หรือ accepted V2.

## 17 พฤศจิกายน 2569 15:29 ICT — Exact-head Candidate #916 / current CI verification

- PR #20 HEAD: `3d170431c7dc1ffc8c0877d0ac7406bf355a5147`; production/test code HEAD: `9f607d570ed903445fc1baac49e9fd563246bec6`. Git compare confirms the only commit after the production/test HEAD changes this QA document by 8 additions / 0 deletions. No application source, tests, installer, spec, manifest, engine runner or fusion code changed after the code/test HEAD.
- Windows Candidate #916 [Actions](https://github.com/niyomse-collab/niyom/actions/runs/44022551976), attempt 2, completed **SUCCESS 2/2 jobs** on exact PR HEAD. `bridge-tests` and `windows-v2-candidate` both passed. The bridge job executed the coordination/fusion/privacy/provisioning regression suites. The frozen candidate checked packaged V2 imports, single-page BigTIFF/libvips path, no-download provisioning dispatch, isolated consented cache cleanup, diagnostic help dispatch, BUILD_PROOF/source SHA and every installer slice SHA256. It uploaded an experimental artifact; this is not a Release or shop-PC acceptance.
- Candidate artifact ID `14306066878`; size **2,584,667,502 bytes**; expires **24 พ.ย. 2569 13:47:49 ICT**. [Download Candidate #916](https://github.com/niyomse-collab/niyom/actions/runs/44022551976/artifacts/14306066878).
- Independent Core #1507 [Actions](https://github.com/niyomse-collab/niyom/actions/runs/44022551999): Windows **1,059 passed / 1 skipped**; Ubuntu **1,057 passed / 3 skipped**; pytest and compileall passed on both.
- Official Archive Audit #263 [Actions](https://github.com/niyomse-collab/niyom/actions/runs/44022552024), JSON artifact ID `14301079213`: all four official Windows archives were downloaded, SHA256-audited, safely inspected and transactionally provisioned into ephemeral QA storage. All upstream license documents were retrieved and hashed. Real-ESRGAN and Real-CUGAN still use observed CI archive pins (no publisher release digest); Waifu2x and Anime4KCPP publisher digests were verified. `model_weights_and_license_certified=false`, `license_redistribution_approved=false`, and `included_in_customer_installer=false` remain mandatory.
- Native CLI Smoke #353 [Actions](https://github.com/niyomse-collab/niyom/actions/runs/44022552027), JSON artifact ID `14301378473`, is a **classified diagnostic only**. On synthetic RGB and RGBA/ICC/300-DPI inputs, Real-CUGAN and Anime4KCPP each started a native process, exited 0 and produced validated 2x outputs. Real-ESRGAN failed with hosted-runner `vkCreateInstance failed -9`; Waifu2x failed with the same Vulkan initialization error and `0xC0000005`. DXGI target adapter was missing; physical adapter verification **0/4**; VRAM guard was not enabled; `real_inference_verified=false`, `runtime_device_use_verified=false`, and `quality_improvement_verified=false`. The workflow SUCCESS means the known host limitations were classified, not that four-engine GPU inference passed.
- Shop GPU Evidence #52 [Actions](https://github.com/niyomse-collab/niyom/actions/runs/44022545335): hosted `gate_status` succeeded, but the `evidence` job on `niyom-shop-gpu` was **SKIPPED** because this event had no affirmative consent marker. No self-hosted shop PC was accessed. The earlier synthetic-only authorization recorded in this document was limited to Candidate #838 and cannot be reused for Candidate #916. A new exact-candidate authorization and an already-installed Candidate #916 with matching `BUILD_PROOF.txt` and verified manifest are required before the self-hosted evidence job can run.
- PR #18 base remains `288dd8501c230a118d9a7e60d2522a2cc7411bcc`. Protected face/GFPGAN files remain byte-identical **6/6** by Git Blob SHA: `face_protection.py`, `detection.py`, `selection.py`, `face_module/__init__.py`, `large_faces.py`, and `v211_face_contract.py`.
- PR #20 and PR #18 remain OPEN / DRAFT / UNMERGED. No V1/V2 Stable edits, no native binaries/model weights/customer images committed, no merge/release, and no visual-quality superiority claim. >18 MP shop GPU stress, measured 6 GB VRAM peak, cancellation under native GPU load, visual A/B and print/RIP acceptance remain open. V2 remains the accepted master.


## 17 พฤศจิกายน 2569 15:56 ICT — Synthetic-only shop GPU evidence authorization for Candidate #916

- เจ้าของโครงการสั่งให้ทดสอบ Native AI ทั้งสี่บน Windows 11 GTX 1660 Ti ที่มี Vulkan พร้อม QA แบบ fail-closed. การอนุญาตนี้จำกัดเฉพาะ **synthetic-only diagnostic** ไม่ใช่การใช้ภาพลูกค้า ไม่ใช่การรับรองคุณภาพภาพ และไม่ใช่การอนุมัติ Merge/Release.
- Candidate #916 source SHA ที่ใช้ทดสอบ: `3d170431c7dc1ffc8c0877d0ac7406bf355a5147`; Windows Candidate #916 [Actions](https://github.com/niyomse-collab/niyom/actions/runs/44022551976) สำเร็จ 2/2 jobs; artifact ID `14306066878`. Git compare ยืนยันว่า Candidate #916 ถึง PR #20 HEAD ปัจจุบัน `a88a072ead58a4254afb5ac87a3447ffdbbc8ff3` เปลี่ยนเพียงเอกสาร QA ไฟล์นี้ ไม่มี Source/Tests/Installer/Spec/Manifest/Fusion changes; จึงใช้ Candidate #916 ตรวจ runtime contract ของ code ปัจจุบันได้ระหว่าง Candidate #917 ที่กำลัง Build ใหม่.
- Commit marker นี้อนุญาตให้ Shop GPU Evidence workflow **ตรวจเฉพาะ Candidate #916 ที่ติดตั้งอยู่แล้ว** ใน Windows account ของ self-hosted runner. ต้องตรวจ `BUILD_PROOF.txt` ให้ตรง source SHA ข้างต้น, executable hash และ verified four-engine manifest ใน LocalAppData ก่อนเรียก Native Process. หากไม่พบ Candidate #916, manifest/hash ไม่ตรง หรือไม่มี runner ให้ fail/skip โดยไม่ติดตั้งโปรแกรมหรือดาวน์โหลดโมเดลแทนผู้ใช้.
- ขอบเขตทดสอบ: synthetic RGB และ RGBA/ICC/300-DPI เท่านั้น; ห้ามอ่าน/อัปโหลด/เก็บภาพลูกค้า, ห้ามดาวน์โหลดโมเดลหรือเปลี่ยน Driver ระหว่าง diagnostic, ห้ามแก้ accepted V2 output. อัปโหลดได้เฉพาะ JSON evidence และลบ workspace ชั่วคราว.
- เกณฑ์ fail-closed: ต้องพิสูจน์ native output 2x ของทั้งสี่, binding ของ Real-ESRGAN/Waifu2x/Real-CUGAN ไปยัง GTX 1660 Ti ผ่าน Vulkan, backend/device ของ Anime4KCPP ผ่าน CUDA/OpenCL แยกต่างหาก, PID-to-adapter telemetry ของทุก process, device-wide VRAM budget 6,144 MiB พร้อม reserve 512 MiB, bridge/fusion, cancellation/cleanup และ privacy flags. หากขาดข้อใด ให้คงผลเป็นไม่ผ่านและรักษา V2.
- แม้ synthetic GPU gate ผ่าน จะยืนยันเฉพาะ native process/device/VRAM/bridge contract บนเครื่องที่รันจริงเท่านั้น; ต้องคง `quality_improvement_verified=false`, `visual_quality_certified=false`, `print_quality_certified=false` จนกว่าจะมี A/B ภาพจริงที่เจ้าของตรวจและอนุมัติ.


## 20 พฤศจิกายน 2569 — Source correction: large JPEG/WebP inputs

This section supersedes earlier historical statements in this document that limited the >18 MP auxiliary route to PNG or marked large JPEG/WebP inputs as V2-only.

- At PR #20 current HEAD `60a7705f480670c93c6728b95734c097a003d67f` (the large-format source/test files are unchanged since `a9f84b517f4b8cf133932b4d74102a916b299e97`), `signprint_ai/v211_four_engine_bridge.py` defines large source formats as RGB/RGBA 8-bit PNG, JPEG, WebP, and single-page TIFF/BigTIFF. Accepted V2 raster formats are PNG, JPEG, and single-page TIFF/BigTIFF. WebP is supported as a large **source** format, not as an accepted V2 output format.
- `signprint_ai/v211_large_image_bridge.py` reads the source and accepted V2 raster through libvips random-access graphs and creates private PNG seed/reference intermediates. `tools/v211_four_engine_tiled_inference.py` continues to consume PNG intermediates only; it does not decode the original large JPEG/WebP/TIFF in Pillow.
- TIFF/BigTIFF must contain exactly one page. CMYK, multipage TIFF, unsupported bit depths/modes, PDF/PSD, and formats outside the allowlists remain V2-only. Source and accepted V2 mode/ICC presence and bytes must satisfy the existing fail-closed metadata contract.
- Regression `test_large_bridge_streams_real_over_18mp_rasters_without_pillow_decode` uses synthetic 4,501 × 4,001 rasters (**18,008,501 pixels**) for JPEG/WebP/PNG source and PNG/JPEG accepted-V2 combinations. It asserts that Pillow does not decode the full large raster, checks half-target seed/reference geometry, ICC and 300-DPI metadata, and confirms the accepted V2 file remains byte-identical. The test deliberately stops at runtime GPU binding (`gpu_binding_unverified`); it does **not** launch the four native engines, prove GPU use, measure peak VRAM, or certify image quality.
- JPEG/WebP EXIF orientation preflight also has a regression that reads orientation from container metadata without invoking a full pixel decode.
- Candidate #990 previously passed the frozen single-page 24 MP BigTIFF seed/reference/streamed-QA smoke. On current HEAD, Windows Candidate #1014 also passed the frozen BigTIFF/libvips QA step ([Actions #1014](https://github.com/niyomse-collab/niyom/actions/runs/44905348360)). These package smokes do not run native AI inference on the 24 MP image.
- Native execution remains one 2× pass per engine on a half-target seed. A final 3×/4×/8× target size is not native 3×/4×/8× inference or multi-pass super-resolution. Real >18 MP GPU stress, per-process GTX 1660 Ti adapter proof, 6 GB peak-VRAM measurement, cancellation during native load, visual A/B, Photoshop/MainTop and print acceptance remain open.


## 21 พฤศจิกายน 2569 — read-only Shop Runner preflight hardening

- `tools/Test-V211-ShopRunner.ps1` เป็น local preflight แบบอ่านอย่างเดียว; เรียกจาก checkout ของ branch นี้ ภายใต้ Windows account เดียวกับที่ติดตั้ง Candidate และ provision Manifest:
  `pwsh -NoProfile -ExecutionPolicy Bypass -File .\\tools\\Test-V211-ShopRunner.ps1 -ExpectedCandidateSha <40-character-source-SHA>`
- Preflight จะยอมรับ service-mode เมื่อ service ที่กำลังทำงานมี .runner metadata ถูกต้อง, service account ตรงกับ interactive user และมี Runner.Listener.exe ที่ยืนยัน owner ได้ครบทุก process; interactive-mode ยอมรับ listener ได้เมื่อทุก process เป็น account ปัจจุบันและตรวจ owner ได้.
- NVIDIA-SMI ต้องพบ GTX 1660 Ti หนึ่งตัวพอดี, memory reading ต้องอยู่ในช่วงที่ถูกต้อง และ total VRAM ต้องไม่น้อยกว่า 5,500 MiB; ต้องพบ vulkan-1.dll ใน System32 ด้วย.
- JSON เพิ่มจำนวน runner service/listener, owner verification, จำนวน adapter match และผลตรวจ capacity. manifest_hashes_verified=false และ github_runner_labels_verified_locally=false ยังคงเป็นค่าบังคับ: local script ไม่ได้แทนการตรวจ Manifest SHA256 ใน packaged diagnostic หรือการยืนยัน label ใน GitHub.
- Script ไม่ดาวน์โหลดโมเดล, ไม่เปลี่ยน service/registry/driver, ไม่เปิด Native Engine, ไม่แตะภาพลูกค้า และไม่เขียนไฟล์. สถานะ ready หมายถึง local prerequisites เท่านั้น ไม่ใช่การอนุมัติให้เริ่ม self-hosted job; ต้องมี exact Candidate BUILD_PROOF และ explicit owner consent แยกต่างหาก.


## 22 พฤศจิกายน 2569 — local V2 vs Four-Engine A/B review pack

- The V2.1.1 bridge now writes a small companion .qa.json beside each accepted QA sidecar only after all four native child processes are verified on the selected GTX 1660 Ti and every engine contributes to the fused pixels. It contains SHA256 bindings for the original source, accepted V2 raster, QA PNG, native seed/reference and four engine candidates; it contains no file paths, command lines, logs or image pixels.
- tools/v211_four_engine_ab_report.py consumes the original source, accepted V2 PNG, V2.1.1 QA PNG and companion evidence JSON. It verifies source/V2/candidate hashes, four-engine contribution, physical adapter evidence, equal dimensions, RGB/RGBA mode, exact ICC/DPI and exact V2 alpha before creating review images.
- Run locally on the shop PC, using a new output directory outside the repository:
  ~~~powershell
  python tools/v211_four_engine_ab_report.py --source "D:\private\source.png" --v2-reference "D:\private\accepted-v2.png" --candidate "D:\private\accepted-v2.V211-4AI-QA-12345678.png" --evidence "D:\private\accepted-v2.V211-4AI-QA-12345678.qa.json" --output-dir "$env:LOCALAPPDATA\NiyomSilp\V211-FourAI-QA\AB-Review"
  ~~~
- Output includes a full-image side-by-side contact sheet, default 3×3 review crops (or explicit --crop x,y,width,height selections), and ab_report.json. Images above 18 MP are read with bounded libvips regions; no customer pixels are uploaded or written into Git.
- The report measures pixel differences only. It never labels a candidate better, never certifies visual/print quality, and requires human review. It records that the bridge binds the source and accepted V2 files to one invocation but does not independently prove the historical generation of the accepted V2 raster.


## 23 พฤศจิกายน 2569 — ระบุหมวดภาพในชุด A/B Review

เครื่องมือ `tools/v211_four_engine_ab_report.py` รองรับการติดป้ายกำกับ crop ที่ผู้ใช้เลือกเอง เพื่อให้ตรวจภาพ V2 เทียบ V2.1.1 แยกตามหมวดงานได้ โดยไม่ให้โปรแกรมเดาความหมายของภาพหรือสร้างคะแนนคุณภาพจากชื่อหมวด

ตัวอย่าง (ทุก path เป็นไฟล์ Local ที่ผู้ใช้เตรียมไว้):

```powershell
python -m tools.v211_four_engine_ab_report `
  --source "D:\\private-qa\\source.png" `
  --v2-reference "D:\\private-qa\\accepted-v2.png" `
  --candidate "D:\\private-qa\\four-engine-qa.png" `
  --evidence "D:\\private-qa\\four-engine-qa.qa.json" `
  --output-dir "D:\\private-qa\\ab-review" `
  --crop 120,80,512,512 --crop-label face `
  --crop 720,120,512,512 --crop-label thai_text `
  --crop 80,700,512,512 --crop-label flat_color `
  --crop 900,700,512,512 --crop-label rgba_edge
```

หมวดที่ใช้ได้:
- `face`, `animal`, `object`, `frame`
- `thai_text`, `english_text`, `chinese_text`
- `flat_color`, `gradient`, `rgba_edge`

ข้อกำหนด:
- แต่ละ `--crop` ต้องมี `--crop-label` หนึ่งรายการตามลำดับเดียวกัน
- ถ้าจำนวน label ไม่ตรงกับ crop หรือใช้ label นอก allowlist ระบบจะหยุดก่อนสร้าง contact sheet
- รายงานเก็บเฉพาะชื่อหมวด พิกัด crop และชื่อไฟล์ review; ไม่เก็บ local path, command line หรือพิกเซลภาพใน JSON
- ไฟล์ contact sheet/crop และภาพทั้งหมดอยู่ในโฟลเดอร์ Local ที่ระบุ โดย output directory ต้องอยู่นอก Git repository
- Label เป็นข้อมูลที่ผู้ใช้กำหนดเพื่อจัดระเบียบการตรวจด้วยสายตา ไม่ใช่ OCR, object/face recognition หรือคะแนนคุณภาพ
- ระบบยังบังคับตรวจ SHA256 ของ source/V2/candidate/evidence, ขนาดพิกเซล, RGB/RGBA, ICC, DPI และ Alpha ก่อนสร้างชุด review
- รายงานยังคง `quality_certified=false`, `visual_quality_certified=false`, `print_quality_certified=false`; ต้องให้มนุษย์ตรวจภาพและทดสอบงานพิมพ์จริงก่อนตัดสิน

ตัวอย่างนี้เป็นการสร้างชุด A/B แบบ Offline เท่านั้น ไม่มีการอัปโหลดภาพลูกค้าหรือส่งภาพไป GitHub Actions


## 24 พฤศจิกายน 2569 — A/B แบบครบ 12 หมวด

เพิ่มตัวช่วย `tools.v211_four_engine_ab_batch` สำหรับจัดชุดเปรียบเทียบ V2 กับ V2.1.1 จากไฟล์ท้องถิ่น 12 กรณี โดยแต่ละกรณีต้องมี Source, accepted V2, QA candidate, sidecar หลักฐาน และ crop ที่ผู้ใช้เลือกเอง

หมวดที่ต้องมีอย่างละหนึ่งกรณี:
1. `person` — ภาพบุคคล/ลำตัว
2. `animal` — สัตว์
3. `object` — วัตถุ
4. `frame` — กรอบ/เส้นขอบ
5. `thai_pattern` — ลายไทย
6. `thai_text` — อักษรไทย
7. `english_text` — อักษรอังกฤษ
8. `chinese_text` — อักษรจีน
9. `flat_color` — พื้นสีเรียบ
10. `gradient` — สีไล่เฉด
11. `rgba_edge` — ขอบโปร่งใส
12. `face` — รายละเอียดใบหน้าและการรักษาอัตลักษณ์

ไฟล์ Manifest เป็น JSON schema 1 มี `cases` จำนวน 12 รายการพอดี แต่ละรายการใช้ key `label`, `source`, `v2_reference`, `candidate`, `evidence`, `crop` โดย path ที่ไม่ใช่ absolute จะอ้างอิงจากโฟลเดอร์ของ Manifest และ `crop` เป็น `[x, y, width, height]` ที่ผู้ใช้เลือกในภาพจริง

ตัวอย่างการรัน:

~~~powershell
py -3 -m tools.v211_four_engine_ab_batch --manifest "$qa\\ab-12-categories.json" --output-dir "$qa\\ab-12-review"
~~~

ผลลัพธ์อยู่ในโฟลเดอร์ QA ส่วนตัว ได้แก่ `ab_12_category_report.json`, รายงาน/ภาพ crop แยกตามหมวด และ `ab_12_category_contact_sheet.png` เมื่อครบทั้ง 12 หมวดและทุกกรณีผ่าน preflight เท่านั้น

สถานะ `ready_for_human_review` หมายถึงไฟล์และ metadata พร้อมให้คนตรวจ ไม่ใช่การรับรองคุณภาพภาพหรือความพร้อมพิมพ์ Sidecar ยังไม่ใช่ลายเซ็นเข้ารหัส จึงไม่ยืนยันความแท้ของหลักฐานด้วยตัวเอง รายงานจะไม่บันทึก path ต้นฉบับ คำสั่ง หรือ pixel data ลงใน JSON และไม่ส่งภาพไป GitHub

ห้ามใช้ภาพลูกค้าที่ไม่มีสิทธิ์ทดสอบ ห้าม commit ภาพ/weights/binaries และห้ามแทนที่ accepted V2 จากผล A/B โดยอัตโนมัติ

## 24 พฤศจิกายน 2569 21:16 ICT — อนุญาต Shop GPU Synthetic Evidence สำหรับ Candidate #1066

ผู้ใช้สั่งให้ดำเนินการตรวจ Native Engine ทั้งสี่บน Windows 11 GTX 1660 Ti จึงใช้ commit marker สำหรับ workflow เฉพาะเครื่องร้าน โดยอ้าง Candidate source commit ที่ตรวจสอบตรงกับ HEAD ก่อนเริ่มงาน:

- Candidate source: `43cd37023817a4ea7f899da337e0257927ccc220`
- Windows Candidate #1066: https://github.com/niyomse-collab/niyom/actions/runs/45328851064
- Experimental artifact ID: `14892112052`; installer SHA256: `a908d24ac8f8b3f7e65285ee76d0be9ef2408b17f1a5a6f21f7199612ebfeafd`; artifact ZIP SHA256: `07f87b76deb2fa3412fb65f2e21399984b3d2d7dbc75c9e3b992a9f115b9996b`.

การ trigger นี้เปลี่ยนเฉพาะเอกสาร และขอให้ workflow ตรวจ BUILD_PROOF/Manifest ที่ติดตั้งไว้แล้วก่อนทำงานเท่านั้น ไม่สั่งติดตั้งหรือดาวน์โหลดโมเดลแทนผู้ใช้ หาก Candidate หรือ Manifest ไม่ตรง/ไม่มี ให้หยุดก่อน Native inference

ขอบเขต workflow:
- ใช้ synthetic RGB และ RGBA/ICC/300-DPI images เท่านั้น ไม่เปิดไฟล์งานลูกค้า
- ตรวจ PID-to-adapter ของแต่ละ Native process, GPU backend, VRAM budget และ Four-Engine bridge แบบ fail-closed
- อัปโหลดเฉพาะ JSON evidence; ไม่อัปโหลดภาพ, archive, executable หรือ model weights
- หาก runner, driver, Vulkan, adapter telemetry หรือ VRAM ไม่พร้อม ให้รายงาน blocker และคง accepted V2 เป็น Master
- ผล synthetic GPU evidence ไม่ใช่ A/B visual quality หรือ print-quality certification

Commit marker นี้อนุญาตเฉพาะการทำงานของ `v211-four-engine-manual-evidence.yml` บน runner label `niyom-shop-gpu`; ไม่อนุญาต Merge, Release, เปลี่ยน V1/V2 Stable หรือเขียนทับ accepted V2
