# SignPrint AI Enhancer — V0.1.1 Private Build

โปรแกรมแยกอิสระสำหรับเตรียมภาพงานป้าย/งานพิมพ์ขนาดใหญ่ โดยตั้งใจสร้างใหม่เพื่อไม่แก้ไขหรือกระทบ Repository ของ ARM AI Image Enhancer และไม่ใช้ชื่อ โลโก้ QR หรือ Asset ของโครงการดังกล่าว

## จุดเด่น V0.1

- Windows GUI แบบงานป้าย: ด้านซ้ายเป็นค่าควบคุม, กลางเปรียบเทียบต้นฉบับ/ผลลัพธ์, ด้านล่างเป็นคิวงานและ Progress
- Width / Height ล็อกอัตราส่วนและปรับตามกันอัตโนมัติ
- หน่วย mm / cm / m / inch และ DPI
- AI Upscale 2× / 4× / 8× โดยใช้ Real-ESRGAN NCNN/Vulkan เมื่อมี backend
- ถ้ายังไม่มี AI backend โปรแกรมยังทำงานได้ด้วย Lanczos fallback
- Pipeline สำหรับงานป้าย: ลด Noise สี, เกลี่ยพื้นที่สีเรียบโดยรักษาขอบ, ตรวจขอบตัวอักษร/โลโก้แบบไม่ใช้ OCR, เกลี่ยเม็ดสีภายในกราฟิก, Local Contrast และ Anti-Halo Sharpen
- Preview แบบรวดเร็วไม่ต้องรัน AI เต็ม
- Batch processing + Stop
- ส่งออก PNG / TIFF / PDF / JPG พร้อม DPI metadata
- เลือกโฟลเดอร์ผลลัพธ์ได้
- Windows drag & drop เมื่อ build พร้อม `windnd`

## Build เป็น Windows EXE

เครื่องที่ **ใช้โปรแกรมสำเร็จแล้วไม่ต้องติดตั้ง Python** เพราะ PyInstaller จะ bundle runtime ไปในโปรแกรม

เครื่องสำหรับ Build ให้ติดตั้ง Python 3.11+ และ Inno Setup 6 (ถ้าต้องการ Setup EXE) จากนั้นดับเบิลคลิก `BUILD_WINDOWS.bat`

สคริปต์จะ:
1. สร้าง virtual environment สำหรับ build
2. ติดตั้ง dependency
3. ดาวน์โหลด `realesrgan-ncnn-vulkan` จาก official Real-ESRGAN GitHub release
4. สร้าง portable EXE folder ด้วย PyInstaller
5. ถ้ามี Inno Setup 6 จะสร้าง `release/SignPrint-AI-Enhancer-Setup-v0.1.1.exe`

## หมายเหตุคุณภาพ 2× / 4× / 8×

โมเดล `realesrgan-x4plus` เหมาะกับภาพทั่วไปและทำงานหลักที่ 4× ในรุ่นนี้ ดังนั้น 4× จะเป็น native AI pass; 2× ใช้ผล 4× แล้ว downsample คุณภาพสูง และ 8× ใช้ผล AI 4× แล้วขยายปลายทางด้วย Lanczos เพื่อหลีกเลี่ยงการรันโมเดลซ้ำจนรายละเอียดปลอมมากเกินไป

## ความเป็นอิสระจาก ARM AI Image Enhancer

โปรเจกต์นี้ไม่ push, fork, commit หรือแก้ไฟล์ใด ๆ ใน GitHub ของเจ้าของ ARM AI Image Enhancer และไม่ได้ bundle source/asset/branding ของเจ้าของหลักไว้ในชุดนี้
