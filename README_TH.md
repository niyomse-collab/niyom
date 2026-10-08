# Niyomsil Design AI Enhancer — V2.1 Face Protect Build

V2.1 รักษา **ARM V2.2.8 / RealESRGAN_x4plus Core** ของ V2.0.2 ไว้ และเพิ่ม Face Protection เป็นโมดูลเสริมแยกต่างหากสำหรับงานป้ายที่มีภาพบุคคล

## กฎความเข้ากันได้
- Face Protection ค่าเริ่มต้น = **OFF**
- เมื่อ OFF โปรแกรมใช้เส้นทาง ARM Core เดิมของ V2.0.2
- ไม่มี GFPGAN / FaceXLib เข้ามาเปลี่ยนภาพเมื่อปิดโมดูล
- ARM Engine files ไม่ถูกแก้เพื่อเพิ่ม Face Protection
- หาก Face Protection เกิดข้อผิดพลาด โปรแกรมเก็บผล ARM Core เดิมและข้ามโมดูลใบหน้าแทนการทำให้งานล้ม

Snapshot ก่อนเพิ่ม Face Module:
`v2.0.2-arm-stable-before-face-module`

## Processing path
เมื่อ Face Protection ปิด:
**V2.1 UI → ARMCoreAdapter → EngineManager → RealESRGANEngine → Export**

เมื่อ Face Protection เปิด:
**V2.1 UI → ARM Core เดิม → Face Protect (GFPGAN + RetinaFace) → Export**

## Face Protection
โหมด:
- **Protect** — ค่าแนะนำสำหรับงานป้าย เน้นรักษาโครงหน้าและจำกัดความแรงสูงสุด
- **Recover** — ฟื้นฟูใบหน้าแรงกว่า ใช้เมื่อหน้าต้นฉบับเบลอหรือเสียรายละเอียดมาก

ค่าเริ่มต้น:
- Face Protection: OFF
- Mode: Protect
- Strength: 35

ระบบจะ:
1. ประมวลผลภาพด้วย ARM Core เดิมก่อน
2. ตรวจจับใบหน้าด้วย RetinaFace เฉพาะเมื่อเปิด Face Protection
3. ฟื้นฟู crop ใบหน้าด้วย GFPGAN
4. Blend ใบหน้ากลับแบบอนุรักษ์โครงหน้า
5. หากไม่พบใบหน้า จะใช้ผล ARM เดิม
6. หากภาพใหญ่เกินขีดจำกัดหน่วยความจำของโมดูลใบหน้า จะข้าม Face Protect และใช้ผล ARM เดิม

## Models
ARM:
- `RealESRGAN_x4plus.pth`

Face Protect:
- `GFPGANv1.4.pth`
- `detection_Resnet50_Final.pth`

Face models ถูกแพ็กใน Installer เพื่อใช้งานแบบ offline หลังติดตั้ง

## Multi-file
ระบบคิว V2.0.2 ยังคงเดิม:
- หนึ่ง ARM/CUDA worker ต่อครั้ง
- เพิ่มไฟล์ระหว่างประมวลผลได้
- ไฟล์ใหม่เข้าคิวต่อโดยไม่เปิด worker แข่ง GPU
- Face Protection ใช้ค่าที่ถูก snapshot ต่อ job

## Build
GitHub → Actions → **Build Windows Installer**

Artifact:
`Niyomsil-Design-AI-Enhancer-V2.1-Face-Protect-Windows`

Installer:
`Niyomsil-Design-AI-Enhancer-Setup-v2.1.0.exe`
