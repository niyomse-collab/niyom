# Niyomsil Design AI Enhancer — V2.1.1 Auto Face Select

V2.1.1 รักษา **ARM V2.2.8 / RealESRGAN_x4plus Core** เดิม และเปลี่ยน Face Protect ให้ทำงานแบบอัตโนมัติสำหรับงานป้ายที่มีภาพบุคคล โดยไม่เพิ่มแถบเครื่องมือถาวรใน UI

## หลักการสำคัญ
- ARM Engine เดิมไม่ถูกแก้
- เมื่อเพิ่มภาพ โปรแกรมสแกนหาใบหน้าด้วย RetinaFace อัตโนมัติ
- ถ้า **ไม่พบใบหน้า** ไฟล์จะพร้อมเข้าลำดับ ARM Core เดิมทันที
- ถ้า **พบใบหน้า** โปรแกรมเปิดหน้าต่างภาพและวาดกรอบให้คลิกเลือกใบหน้าที่ต้องการโฟกัส
- GFPGAN ทำงานเฉพาะใบหน้าที่ผู้ใช้เลือก
- ถ้ากดข้าม หรือไม่เลือกใบหน้า ไฟล์ใช้ ARM Core เดิมโดยไม่มี Face Protect
- ถ้า Face Module มีข้อผิดพลาด ผล ARM Core เดิมจะถูกเก็บไว้ ไม่ทำให้งานทั้งไฟล์ล้ม

Snapshot ก่อนเพิ่ม Auto Select:
`v2.1-face-protect-before-auto-select`

Snapshot ก่อนเพิ่ม Face Module:
`v2.0.2-arm-stable-before-face-module`

## Workflow
### ภาพไม่มีบุคคล
**Upload → Auto Face Scan → ไม่พบใบหน้า → ARM Core เดิม → Export**

### ภาพมีบุคคล
**Upload → Auto Face Scan → Popup แสดงภาพเต็ม + กรอบใบหน้า → คลิกเลือก → ARM Core เดิม → Face Protect เฉพาะหน้าที่เลือก → Export**

Popup มีเพียงปุ่ม:
- เลือกทั้งหมด
- ใช้ใบหน้าที่เลือก
- ข้าม Face Protection

ไม่มี Face toolbar เพิ่มในหน้าหลัก

## การเลือกใบหน้า
ตำแหน่งใบหน้าถูกเก็บเป็นพิกัด normalized ต่อไฟล์ และถูกแปลงตามการจัดวาง `ImageOps.contain` เมื่อขนาดป้ายปลายทางมีอัตราส่วนต่างจากต้นฉบับ จึงลดโอกาสเลือกผิดคนหลัง resize

## Multi-file
ระบบคิว V2.0.2 ยังคงหลักเดิม:
- หนึ่ง ARM/CUDA worker ต่อครั้ง
- Auto face detection ใช้ CPU แยก เพื่อไม่แย่ง CUDA กับ ARM Core
- เพิ่มไฟล์ระหว่าง render ได้
- ถ้าไฟล์ใหม่ไม่มีหน้า จะเข้าคิวตามปกติ
- ถ้าพบหน้า จะรอผู้ใช้เลือกก่อนเข้าคิว
- state ของใบหน้าแยกต่อไฟล์ ไม่ปนกัน

## Models
ARM:
- `RealESRGAN_x4plus.pth`

Face module:
- `GFPGANv1.4.pth`
- `detection_Resnet50_Final.pth`

## Build
Artifact:
`Niyomsil-Design-AI-Enhancer-V2.1.1-Auto-Face-Select-Windows`

Installer:
`Niyomsil-Design-AI-Enhancer-Setup-v2.1.1.exe`
