# NiyomSilp Design v2 — สิทธิ์โมเดล / การฝึกต่อ / การตรวจรับ

## สถานะของงาน
เริ่มการวิจัย v2 ภายหลังผู้ใช้ยืนยันว่า v1 ใช้งานผ่านแล้ว โดย **ไม่แก้ไฟล์หรือโมเดลของ v1** และยังไม่มีโมเดลฝึกต่อที่ผ่านการตรวจรับสำหรับใช้งานจริง

เป้าหมายแรก: ฝึกต่อ `RealESRGAN_x4plus.pth` ให้เหมาะกับภาพสำหรับป้ายไวนิลและตัวอักษรไทย งานภาพบุคคล GFPGAN/RetinaFace เป็นแผนระยะถัดไป หลังจากตรวจสิทธิ์แต่ละ checkpoint

## กรอบสิทธิ์ที่ต้องเข้าใจ

| ทรัพย์สิน | สิ่งที่นิยมศิลป์อาจเป็นเจ้าของ / ต้องตรวจ |
| --- | --- |
| ชื่อและเครื่องหมายการค้า NiyomSilp Design | ของผู้ประกอบการตามสิทธิ์ที่มี |
| โค้ดใหม่ที่เขียนเอง | สามารถเป็นงานของร้านตามข้อตกลงผู้เขียน/ผู้รับจ้างและกฎหมาย |
| ภาพชุดฝึก | ต้องเป็นภาพที่ร้านเป็นเจ้าของหรือมีใบอนุญาตครอบคลุมการฝึก AI และการค้า |
| การปรับน้ำหนักโมเดลที่ใช้ pretrained weights ของบุคคลที่สาม | เป็นงานที่ต่อยอดจากโมเดลต้นฉบับ **ไม่ทำให้ร้านถือสิทธิ์ขาดในโมเดลเดิม** |
| Real-ESRGAN source code | BSD-3-Clause; เก็บเครดิต เงื่อนไข และตรวจสิทธิ์ของ checkpoint แยก |
| GFPGAN source code | Apache-2.0 พร้อมข้อจำกัด/สิทธิ์ของ dependency และ weights ที่เกี่ยวข้อง |
| RetinaFace ผ่าน facexlib | facexlib ใช้ MIT แต่ต้องตรวจต้นฉบับอัลกอริทึมและ checkpoint เพิ่มเติม |

เอกสารนี้เป็นกรอบการพัฒนา ไม่ใช่เอกสารยืนยันการได้รับโอนสิทธิ์ทรัพย์สินทางปัญญา หากต้องการ **สิทธิ์ขาดในโมเดลทั้งหมด** ต้องเจรจาสิทธิ์ใน base weights หรือฝึกน้ำหนักใหม่จากศูนย์โดยข้อมูลและเครื่องมือที่มีสิทธิ์ถูกต้อง และให้ผู้เชี่ยวชาญด้านทรัพย์สินทางปัญญาประเมินเป็นรายกรณี

แหล่งอ้างอิงสิทธิ์:
- https://github.com/xinntao/Real-ESRGAN/blob/master/LICENSE
- https://github.com/xinntao/Real-ESRGAN/blob/master/docs/Training.md
- https://github.com/TencentARC/GFPGAN/blob/master/LICENSE
- https://github.com/xinntao/facexlib

## สิ่งที่เพิ่มในสาขา v2

`native_models/finetune_realesrgan.py`: prototype สำหรับฝึกต่อ x4plus จากไฟล์ .pth ที่ผู้ใช้นำมาเอง **ไม่ดาวน์โหลด weights หรือข้อมูลภาพเอง** และไม่เปลี่ยนโมเดลของ v1

- ตรวจ checksum โมเดลตั้งต้น
- บังคับใช้ไฟล์รับรองสิทธิ์ที่ตรวจโดยมนุษย์ และ `--allow-pretrained-derivative`
- ตรวจแหล่งที่มาและ SHA-256 ของภาพทุกรายการใน CSV โดยแยก train/validation และห้ามภาพซ้ำข้ามชุด
- วัด PSNR ของ base model และ bicubic เทียบกับโมเดลฝึกต่อด้วย validation เดิม
- บันทึก checkpoint `CANDIDATE.pth` เฉพาะเมื่อค่า validation ดีขึ้นเหนือ base
- บันทึก `PROVENANCE_V2.json` โดยบอกชัดว่าโมเดลเป็นการฝึกต่อบน weights ภายนอก
- **ไม่ส่งโมเดลทดลองเข้า Windows Installer, ไม่แทน RealESRGAN_x4plus ใน v1, ไม่ส่งภาพฝึกขึ้น GitHub**

## การเตรียมข้อมูล

บนเครื่องฝึกที่มี Python, PyTorch, BasicSR และ CUDA พร้อมใช้งาน เก็บภาพที่ได้รับอนุญาตในโฟลเดอร์ส่วนตัวนอก Git repo

ไฟล์ `inventory.csv` ต้องมีคอลัมน์:
`relative_path,rights_holder,license,rights_proof,sha256,split`
โดย `split` มีเฉพาะ `train` หรือ `val`

ไฟล์ `rights_review.json` ต้องเป็นข้อมูลจริงจากผู้ตรวจสิทธิ์ (ไม่ใช้ค่าตัวอย่างในการฝึกจริง):
```json
{
  "reviewer": "ชื่อผู้ตรวจสิทธิ์ที่ตรวจแล้วจริง",
  "reviewed_at": "2026-10-12",
  "upstream_checkpoint_url": "https://github.com/xinntao/Real-ESRGAN/releases/download/v0.1.0/RealESRGAN_x4plus.pth",
  "upstream_checkpoint_license": "ผลการตรวจสิทธิ์ของ checkpoint ที่ยืนยันได้",
  "commercial_use_approved": true,
  "dataset_rights_confirmed": true
}
```

ข้อควรระวัง: การใส่ค่า `true` ไม่ใช่หลักฐานอนุญาตด้วยตัวเอง ต้องเก็บเอกสารประกอบจริงไว้ภายในร้านด้วย

## ตัวอย่างการทดลอง (สำหรับเครื่องฝึกเท่านั้น ไม่ใช่เครื่องใช้งานโปรแกรม v1)

```powershell
python -m native_models.finetune_realesrgan `
  --pretrained "C:\\model-storage\\RealESRGAN_x4plus.pth" `
  --pretrained-sha256 4fa0d38905f75ac06eb49a7951b426670021be3018265fd191d2125df9d682f1 `
  --rights-review "C:\\private-data\\rights_review.json" `
  --manifest "C:\\private-data\\inventory.csv" `
  --data-dir "C:\\private-data\\images" `
  --output-dir "C:\\private-results\\niyomsil-sign-v2" `
  --epochs 5 --batch-size 1 --patch 128 --device cuda `
  --allow-pretrained-derivative
```

การทดลองแรกใช้ **ภาพ HR ที่จำลอง LR ด้วย Bicubic** เพื่อทดสอบระบบเท่านั้น ยังไม่ครอบคลุม noise, JPEG artifact, ภาพโลโก้, ภาพข้อความไทย หรือกล้องถ่ายจริง ต้องเพิ่มชุดข้อมูลจริงที่มีสิทธิ์ใช้และประเมิน print proof ต่อไป

## เกณฑ์ตรวจรับก่อนเปิดใช้งาน v2

1. หลักฐานสิทธิ์ภาพและ checkpoint ครบ รวมการใช้เชิงพาณิชย์
2. ผลไม่ต่ำกว่า v1 ทั้งภาพป้ายทั่วไป ภาษาไทย โลโก้ และภาพบุคคล
3. การเทียบกับ v1 ใช้ภาพเดียวกัน ขนาดเดียวกัน การตั้งค่าเดียวกัน และ print proof
4. การวัด PSNR/SSIM ที่เหมาะสมเป็นเพียงส่วนหนึ่ง ต้องตรวจการสร้างรายละเอียดเทียม (hallucination), ผิดตัวสะกดไทย และสีเพี้ยน
5. โมเดลที่ฝึกต่อถูกระบุเป็น `NiyomSilp Design v2 (fine-tuned from Real-ESRGAN)` ไม่กล่าวอ้างว่าไม่เกี่ยวข้องกับเจ้าของเดิม
6. สามารถสลับกลับไปใช้ base model หรือ v1 ได้โดยไม่ทำลายตัวติดตั้งเสถียร
