# Niyomsil Design AI Enhancer — V2.0 UI Build

รุ่น V2 ปรับเฉพาะ **หน้าตาโปรแกรม การแสดงสถานะ และ Branding** ตามแบบที่ผู้ใช้กำหนด โดย **ไม่เปลี่ยนแกนประมวลผล V1.1** ที่ผ่านการใช้งานและให้คุณภาพดีแล้ว

## สิ่งที่ล็อกไว้จาก V1.1
- Real-ESRGAN / AI Upscale เดิม
- V1 Baseline เดิม
- Noise / Detail / Sharpen / Contrast logic เดิม
- ระบบขนาดงานพิมพ์และ DPI เดิม
- RGB / CMYK / ICC export เดิม
- การบันทึก PNG / TIFF / PDF / JPG เดิม

ไฟล์แกนประมวลผล `processing.py`, `pipeline.py` และ `realesrgan_ncnn.py` ไม่ได้ถูกแก้เพื่อทำ V2 UI

Snapshot ก่อนเริ่ม V2:
`v1.1-color-stable`

## หน้าตา V2
- ธีมดำ–แดงแบบ NIYOMSIL DESIGN
- โลโก้นิยมศิลป์ดีไซน์แบบพื้นหลังโปร่งใส
- หัวโปรแกรมแบบ Dashboard พร้อมปุ่ม Open / Settings / Enhance / Output / Folder
- แสดง GPU / VRAM / AI Engine / Device
- แผงซ้ายหมายเลข 1–4
- Before / After หมายเลข 5
- Queue + Status + Progress หมายเลข 6
- Export Format / RGB-CMYK / ICC / Output Folder หมายเลข 7–9
- Status Bar ด้านล่างพร้อมเวลาทำงานและ Overall Progress
- ตารางแสดงสถานะและเปอร์เซ็นต์ของแต่ละไฟล์

## ไอคอน
โปรแกรมและตัวติดตั้งใช้โลโก้ NIYOMSIL DESIGN และลบพื้นหลังสีขาวออกก่อนสร้าง Windows ICO

## Build Windows
GitHub Actions → **Build Windows Installer** → **Run workflow**

ผลลัพธ์:
- `dist/NiyomsilAIEnhancer/NiyomsilAIEnhancer.exe`
- `release/Niyomsil-Design-AI-Enhancer-Setup-v2.0.0.exe`
- Artifact: `Niyomsil-Design-AI-Enhancer-V2-Windows`
