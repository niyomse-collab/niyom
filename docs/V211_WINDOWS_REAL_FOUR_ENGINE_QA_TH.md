# Windows 11 QA: NiyomSilp V2.1.1 + four engines

สถานะ: ผ่านขั้นตอนตรวจ ZIP ทางการและสร้าง Manifest จากไฟล์จริงบน Windows CI
ยัง **ไม่ใช่** ผลพิสูจน์ real inference ของสี่ตัวหรือคุณภาพเหนือ V2; ห้าม Merge/Release ก่อน QA ภาพจริง

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
- งาน Four-Engine ขนาดปกติรองรับ RGB/RGBA PNG/JPEG/TIFF เมื่อผ่านการตรวจ mode, ICC, alpha และ output contract. **Disk-backed Four-Engine สำหรับงานเกิน 18MP รองรับเฉพาะ PNG** ทั้ง source, accepted V2 reference และ native candidates; ใช้ libvips random-access regions, native tile runner, streamed fusion และ streamed QA crop. JPEG/TIFF เกิน 18MP, CMYK, PDF, PSD และไฟล์ที่ libvips อ่านไม่ได้ให้คง V2 เดิมโดยไม่เรียก auxiliary engines. ขีดจำกัด streamed path คือไม่เกิน 1,000 MP, row buffer ไม่เกิน 64 MiB และต้องผ่าน disk-space preflight.
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
- งาน RGB/RGBA **PNG** เกิน 18MP มี disk-backed Four-Engine route ใน source branch; JPEG/TIFF ขนาดดังกล่าวยังคงใช้ V2 เท่านั้น. ผล CI เป็น synthetic/fake-processor evidence ไม่ใช่ real inference บน GTX 1660 Ti และยังไม่รับรอง VRAM 6GB หรือคุณภาพงานพิมพ์
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
