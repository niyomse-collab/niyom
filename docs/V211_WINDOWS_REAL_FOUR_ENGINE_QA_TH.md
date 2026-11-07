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
- ขอบเขต Four-Engine Bridge ปัจจุบันรองรับ V2 raster RGB/RGBA PNG, JPEG และ TIFF ภายในงบไม่เกิน 18MP เพื่อสร้าง PNG QA sidecar แยกจากไฟล์ V2; CMYK, PDF, PSD และงานเกิน 18MP ใช้ V2 เดิมเท่านั้น
- ทุก Native Engine ยังประมวลผลเพียง 2x หนึ่ง pass จาก seed ครึ่งขนาดของเป้าหมาย ดังนั้นเป้าหมายภาพ 4x/8x เป็นเพียงขนาดปลายทางของ candidate ไม่ใช่ Native 4x/8x หรือ multi-pass inference
- CI ที่ใช้ fake executables หรือ hosted runner ไม่มี Vulkan ไม่ใช่หลักฐาน real inference หรือคุณภาพบน GTX 1660 Ti; ต้องทดสอบบนเครื่องร้านและตรวจภาพ A/B จริงก่อนรับรอง


## 5 พฤศจิกายน 2569 — ตรวจเครื่องร้าน GTX 1660 Ti ด้วยคำสั่งเดียว

เมื่อใช้ Installer รุ่นทดลอง V2.1.1 และเลือกติดตั้ง AI ทั้งสี่ในขั้นตอนติดตั้งแล้ว ให้เปิด PowerShell และรัน:

~~~powershell
& "$env:ProgramFiles\NiyomSilpDesignV211Experimental\NiyomsilAIEnhancer.exe" --diagnose-v211-four-ai --output-dir "$env:USERPROFILE\Desktop\NiyomSilp-V211-GPU-QA"
~~~

รายงานอยู่ที่:

~~~text
%USERPROFILE%\Desktop\NiyomSilp-V211-GPU-QA\shop_gpu_diagnostic.json
~~~

เครื่องมือใหม่นี้:
- ตรวจ NVIDIA GPU, Driver, VRAM และ Vulkan device ที่มองเห็นได้
- ใช้เฉพาะภาพสังเคราะห์ RGB และ RGBA พร้อม sRGB ICC และ 300 DPI
- เรียก Native CLI จริงทั้งสี่ตัวกับภาพทดสอบทั้งสองชนิด โดยตรวจขนาด 2x, Alpha, ICC และ DPI
- จำกัดเวลาแต่ละ Engine ไว้ 180 วินาทีในงานวินิจฉัยนี้
- ลบภาพทดสอบและภาพผลลัพธ์ชั่วคราวหลังจบ เหลือเฉพาะ JSON
- ไม่อ่านภาพลูกค้า ไม่ใช้เครือข่าย ไม่อัปโหลดไฟล์ และไม่แก้ไฟล์ V2 ที่ผ่านการบันทึกแล้ว

การแปลผล:
- `all_four_native_cli_outputs_validated_on_both_synthetic_cases=true` หมายถึง Native CLI ทั้งสี่สร้างผลที่ผ่านการตรวจรูปแบบ/metadata บนภาพสังเคราะห์ทั้ง RGB และ RGBA
- `four_engine_cli_passed_on_gtx1660ti_vulkan_host=true` หมายถึงตรวจพบ GTX 1660 Ti ผ่าน NVIDIA-SMI และ Vulkaninfo พร้อมกับ CLI ทั้งสี่ผ่าน; ยังไม่ใช่การวัดคุณภาพภาพหรือการรับรองว่าแต่ละ CLI เลือก GPU adapter ตัวนั้นโดยตรง
- `quality_improvement_verified`, `visual_quality_certified` และ `print_quality_certified` จะเป็น false เสมอในเครื่องมือนี้

ข้อจำกัดที่ต้องไม่สับสน:
- เป้าหมาย 4x/8x เป็นขนาดภาพปลายทางที่สร้างจาก seed ครึ่งขนาดและใช้ Native 2x เพียงหนึ่ง pass ไม่ใช่ Native 4x/8x หรือ multi-pass inference
- งาน Four-Engine ที่เกิน 18MP ยังไม่รองรับ; งานดังกล่าวต้องกลับไปใช้ V2 เดิมโดยไม่หยุดการส่งออก
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

