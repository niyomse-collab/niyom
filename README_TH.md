# Niyomsil Design AI Enhancer — V1.1 Color Management Build

โปรแกรมสำหรับร้าน **นิยมศิลป์ดีไซน์ (NIYOMSIL DESIGN)** เพื่อเตรียมภาพสำหรับงานป้ายและงานพิมพ์ขนาดใหญ่

## สิ่งที่คงเดิมจาก V1
- V1 Baseline และลำดับการประมวลผล Real-ESRGAN **ไม่เปลี่ยน**
- 4× ยังใช้ Real-ESRGAN เป็นแกนหลักเหมือนเดิม
- ไม่ลด Noise / เกลี่ยสี / เพิ่ม Contrast อัตโนมัติเมื่อเปิด V1 Baseline
- Advanced Enhancement เดิมยังอยู่ครบ
- ถ้า AI backend ไม่พร้อม โปรแกรมจะหยุดแจ้งเตือน ไม่ fallback เป็น Lanczos แบบเงียบ ๆ

Snapshot ของรุ่นก่อนเพิ่ม Color Management ถูกเก็บไว้ที่ branch:
`v1-stable-snapshot`

## Color Mode / ICC / CMYK
เพิ่มเฉพาะขั้นตอนส่งออก:
- เลือก Color Mode: **RGB / CMYK**
- โปรแกรมค้นหา CMYK ICC/ICM ที่ติดตั้งใน Windows Color Folder
- เลือกไฟล์ ICC/ICM ภายนอกได้ เช่น Profile ที่โรงพิมพ์หรือ RIP กำหนด
- การแปลง CMYK ทำหลัง V1 enhancement เสร็จแล้ว จึงไม่เปลี่ยนคุณภาพการประมวลผล AI
- CMYK รองรับ TIFF / JPG / PDF
- PNG ใช้ RGB เท่านั้น
- สำหรับงานพิมพ์แนะนำ **TIFF + ICC** เพื่อรักษา Color Management ชัดเจน

## Branding / UI
- โลโก้: นิยมศิลป์ดีไซน์
- โปรแกรมและตัวติดตั้งใช้โลโก้เดียวกันเป็น Windows icon
- ธีมส่วนหัวดำ–แดง พร้อมกราฟิก accent เล็กน้อย
- Layout และ Workflow หลักของ V1 ไม่เปลี่ยน

## Build Windows
GitHub Actions → **Build Windows Installer** → **Run workflow**

ผลลัพธ์:
- `dist/NiyomsilAIEnhancer/NiyomsilAIEnhancer.exe`
- `release/Niyomsil-Design-AI-Enhancer-Setup-v1.1.0.exe`
- Artifact: `Niyomsil-Design-AI-Enhancer-Windows`

## หมายเหตุเรื่อง ICC
โปรแกรมไม่ได้บังคับ Profile ใด Profile หนึ่ง เพราะงานพิมพ์แต่ละเครื่อง/หมึก/วัสดุ/RIP อาจต้องใช้ ICC ต่างกัน ควรใช้ ICC ที่ร้านหรือผู้ให้บริการพิมพ์กำหนดสำหรับเครื่องจริง
