# Niyomsil Design AI Enhancer — V1.0

โปรแกรม **นิยมศิลป์ดีไซน์ (NIYOMSIL DESIGN)** สำหรับปรับความละเอียดภาพเพื่องานป้ายและงานพิมพ์ขนาดใหญ่

## V1 Baseline
ค่าเริ่มต้นของโปรแกรมยึดแนวทาง V1 ที่เน้นรักษารายละเอียด:
- Real-ESRGAN เป็นแกนหลักในการ Upscale
- 4× ใช้ผล AI เป็นหลักโดยตรง
- ไม่ลด Noise / เกลี่ยพื้นสี / เพิ่ม Contrast โดยอัตโนมัติใน V1 Baseline
- Advanced Enhancement เป็นตัวเลือกเสริมเมื่อผู้ใช้ปิด V1 Baseline
- ถ้า Real-ESRGAN backend หาย โปรแกรมจะหยุดแจ้งเตือน ไม่ใช้ Lanczos แทน AI แบบเงียบ ๆ

## Branding
- ชื่อร้าน: นิยมศิลป์ดีไซน์
- English: NIYOMSIL DESIGN
- Logo: เก็บใน `assets/logo.b64` และแสดงในส่วนหัวของโปรแกรม
- ตัวติดตั้ง: `Niyomsil-Design-AI-Enhancer-Setup-v1.0.0.exe`

## Build
GitHub Actions → **Build Windows Installer** → **Run workflow**

Artifact:
`Niyomsil-Design-AI-Enhancer-Windows`

โครงการนี้เป็นโปรแกรมแยกอิสระ และไม่แก้ไข Repository ของ ARM AI Image Enhancer
