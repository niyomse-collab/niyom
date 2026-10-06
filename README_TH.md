# SignPrint AI Enhancer — V0.1 Private Build

โปรแกรมแยกอิสระสำหรับเตรียมภาพงานป้ายและงานพิมพ์ขนาดใหญ่ โดยสร้างแยกจาก ARM AI Image Enhancer เพื่อไม่แก้ไขหรือกระทบ Repository ของเจ้าของหลัก

## ความสามารถหลัก
- ปรับ Width / Height แบบล็อกอัตราส่วนอัตโนมัติ
- รองรับ mm / cm / m / inch และ DPI
- AI Upscale 2× / 4× / 8×
- ลด Noise และเกลี่ยพื้นสีโดยรักษาขอบ
- เพิ่มความชัดตัวอักษรและโลโก้
- Local Contrast และ Anti-Halo Sharpen
- Preview ก่อนประมวลผลจริง
- Batch processing + Progress + Stop
- ส่งออก PNG / TIFF / PDF / JPG
- ลากไฟล์เข้าโปรแกรมบน Windows

## Build Windows
ดับเบิลคลิก `BUILD_WINDOWS.bat`

ระบบจะสร้าง virtual environment, ติดตั้ง dependency, ดาวน์โหลด Real-ESRGAN NCNN/Vulkan จาก upstream อย่างเป็นทางการ, สร้างโปรแกรมด้วย PyInstaller และสร้าง Installer ด้วย Inno Setup หากมีติดตั้งอยู่

ไฟล์ผลลัพธ์จะอยู่ใน:
- `dist/SignPrintAIEnhancer/`
- `release/SignPrint-AI-Enhancer-Setup-v0.1.0.exe`

## หมายเหตุ
โปรเจกต์นี้ไม่รวม Source, Logo, QR, Donation Link หรือ Asset ของ ARM AI Image Enhancer
