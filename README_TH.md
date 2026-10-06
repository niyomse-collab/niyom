# Niyomsil Design AI Enhancer — V1.0 Brand Build

โปรแกรมสำหรับร้าน **นิยมศิลป์ดีไซน์ (NIYOMSIL DESIGN)** เพื่อเตรียมภาพสำหรับงานป้ายและงานพิมพ์ขนาดใหญ่

## แนวทางคุณภาพ V1
- ค่าเริ่มต้นคือ **V1 Baseline**
- ให้ Real-ESRGAN เป็นแกนหลักในการสร้างรายละเอียด
- 4× ใช้ผล AI โดยตรงเป็นหลัก
- V1 Baseline ไม่ลด Noise / เกลี่ยสี / Contrast เพิ่มโดยอัตโนมัติ เพื่อรักษารายละเอียดอาหาร ตัวอักษร โลโก้ และพื้นผิว
- หากต้องการจึงค่อยปิด V1 Baseline แล้วใช้ตัวเลื่อน Advanced Enhancement
- หาก AI backend ไม่พร้อม โปรแกรมจะหยุดแจ้งเตือน และจะไม่ใช้ Lanczos แทน AI แบบเงียบ ๆ

## ความสามารถ
- Width / Height ล็อกอัตราส่วนอัตโนมัติ
- mm / cm / m / inch และ DPI
- AI Upscale 2× / 4× / 8×
- Preview ก่อนประมวลผล
- Batch processing + Progress + Stop
- PNG / TIFF / PDF / JPG
- Windows Drag & Drop
- โลโก้และ Branding นิยมศิลป์ดีไซน์

## Build Windows
รัน `BUILD_WINDOWS.bat` หรือ GitHub Actions → **Build Windows Installer**

ไฟล์สำเร็จ:
- `dist/NiyomsilAIEnhancer/NiyomsilAIEnhancer.exe`
- `release/Niyomsil-Design-AI-Enhancer-Setup-v1.0.0.exe`

## หมายเหตุ
โครงการนี้เป็นโปรแกรมแยกอิสระของนิยมศิลป์ดีไซน์ และไม่แก้ไข Repository ของ ARM AI Image Enhancer
