# Niyomsil Design AI Enhancer — V2.0 ARM Core Build

รุ่น V2 คงดีไซน์ดำ–แดงของ **นิยมศิลป์ดีไซน์** แต่เปลี่ยนแกน AI เป็นสายคุณภาพที่ผ่านการทดสอบแล้วจาก branch `v1-arm-core`

## แกนประมวลผลที่ล็อกไว้
ไฟล์ต่อไปนี้ถูกย้ายจาก `v1-arm-core` แบบตรงไฟล์ และตรวจ SHA แล้วว่าตรงกัน:
- `app/device/device_manager.py`
- `app/engine/engine_manager.py`
- `app/engine/realesrgan_engine.py`

เส้นทางประมวลผล:
**V2 UI → ARMCoreAdapter → EngineManager → RealESRGANEngine → RealESRGAN_x4plus.pth**

รายละเอียด:
- PyTorch CUDA
- RealESRGAN_x4plus
- CUDA tile = 256
- tile_pad = 10
- pre_pad = 0
- FP32 ตามเส้นทางที่ทดสอบ
- 8× = AI 4× pass แล้ว AI 2× pass
- NVIDIA CUDA ถูกเลือกก่อนเมื่อมี GPU รองรับ
- ไม่มี NCNN ใน V2 ARM Core Build
- ไม่มี Denoise / Contrast / Sharpen เพิ่มหลัง ARM AI
- RGB PNG รักษาพิกเซลผลลัพธ์สุดท้ายของ ARM Core
- CMYK / ICC ทำเฉพาะขั้น Export หลัง AI เสร็จ

โมเดล:
`RealESRGAN_x4plus.pth`
SHA256:
`4fa0d38905f75ac06eb49a7951b426670021be3018265fd191d2125df9d682f1`

## V2 UI
- ธีมดำ–แดงเดิม
- Before / After
- Queue และ Progress
- GPU / VRAM / AI Engine / Device
- RGB / CMYK / ICC
- Output Folder
- Status Bar และเวลาทำงาน

## โลโก้ / ไอคอน
โลโก้ NIYOMSIL DESIGN ถูกลบเฉพาะพื้นหลังสีขาวที่เชื่อมกับขอบภาพ แล้วสร้าง Windows ICO แบบ Alpha Transparency
จึงคงส่วนสีขาวที่เป็นรายละเอียดภายในโลโก้ไว้ และไม่มีกรอบพื้นหลังสีขาวบน Taskbar / Shortcut / Installer

## Snapshot
รุ่น V2 NCNN ก่อนเปลี่ยน Core ถูกเก็บไว้ที่:
`v2-ncnn-stable`

## Build
GitHub → Actions → **Build Windows Installer** → **Run workflow**

Artifact:
`Niyomsil-Design-AI-Enhancer-V2-ARM-Core-Windows`

Installer:
`Niyomsil-Design-AI-Enhancer-Setup-v2.0.0.exe`

หมายเหตุ: ชุดติดตั้งรุ่น ARM Core มีขนาดใหญ่กว่ารุ่น NCNN มาก เนื่องจากมี PyTorch/CUDA runtime และโมเดล AI รวมอยู่ในชุดติดตั้ง เพื่อให้เครื่องปลายทางไม่ต้องติดตั้ง Python เอง
