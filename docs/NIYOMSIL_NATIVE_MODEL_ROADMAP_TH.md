# แผนพัฒนาโมเดลของนิยมศิลป์แทนโมเดลภายนอกใน v1

เป้าหมายของ v2 คือค่อย ๆ แทนส่วน AI ที่ v1 ยังอาศัยโมเดลภายนอก/สาย ARM เดิม ด้วยโมเดลที่นิยมศิลป์ดีไซน์มีสิทธิ์ใช้งานและตรวจสอบที่มาได้จริง

ข้อสำคัญ: การเปลี่ยนชื่อไฟล์ เปลี่ยนชื่อปุ่ม หรือเปลี่ยนข้อความเครดิต **ไม่ทำให้เป็นเจ้าของลิขสิทธิ์โมเดล** หากน้ำหนักโมเดลยังมาจาก Real-ESRGAN, GFPGAN, RetinaFace หรือ checkpoint ภายนอก โมเดลนั้นยังต้องถือเป็นงานต่อยอดและต้องคงเครดิต/เงื่อนไขเดิม

## รายการที่ต้องแทนจาก v1

| งานใน v1 | โมเดล/องค์ประกอบเดิม | สถานะสิทธิ์ปัจจุบัน | เส้นทาง v2 ที่ต้องทำ |
| --- | --- | --- | --- |
| Super Resolution สำหรับงานป้าย | Real-ESRGAN `RealESRGAN_x4plus.pth` | โมเดลภายนอก ไม่ใช่สิทธิ์ขาดของร้าน | ฝึก `niyomsil-sr-v1` จากศูนย์ด้วยภาพที่ร้านมีสิทธิ์ หรือทำ fine-tune แบบระบุว่าเป็น derivative |
| Face Recovery / Studio AI | GFPGAN `GFPGANv1.4.pth` | โมเดลภายนอก ไม่ใช่โมเดลภาพบุคคลของร้าน | พัฒนา `niyomsil-face-v1` แยกต่างหากด้วยข้อมูลใบหน้าที่ได้รับอนุญาตชัดเจน |
| Face Detection | RetinaFace/facexlib `detection_Resnet50_Final.pth` | detector/checkpoint ภายนอก | พัฒนา/ฝึก detector ของร้าน หรือใช้โมเดลที่มีสัญญาอนุญาตเชิงพาณิชย์ชัดเจนและบันทึก provenance |
| Runtime/ชื่อสาย ARM เดิม | คำอ้างอิง ARM ใน build/docs/tests บางจุด | เป็นประวัติแหล่งที่มา ไม่ใช่แบรนด์เป้าหมาย | เปลี่ยนชื่อภายในเป็น NiyomSilp Native เมื่อ runtime ไม่พึ่งโมเดล/adapter เดิมแล้ว |

## เงื่อนไขก่อนเรียกว่า “โมเดลของนิยมศิลป์”

1. ต้องมี training manifest ที่บันทึก `relative_path, rights_holder, license, rights_proof, sha256, split`
2. ต้องมีหลักฐานสิทธิ์ภาพฝึกและภาพทดสอบ เก็บภายในร้าน ไม่ commit ขึ้น GitHub
3. ต้องฝึกจาก random initialization หรือมีเอกสารโอนสิทธิ์/อนุญาต base weights ที่ชัดเจน
4. ต้องมี provenance JSON ระบุที่มา, checksum, config, จำนวนภาพ, seed, metric และวันที่ฝึก
   และตรวจด้วย `python -m native_models.validate_provenance <TRAINING_PROVENANCE.json>`
5. ต้องผ่าน benchmark เทียบ v1 ด้วย validation set เดียวกัน และผ่านการตรวจงานพิมพ์จริง
6. ต้องรักษาทางถอยกลับไป v1 ที่ผ่านตรวจรับแล้ว จนกว่า v2 จะผ่านครบทุกหมวด

## ลำดับพัฒนา

### ระยะ 1: Native SR สำหรับงานป้าย

- ใช้ `native_models/niyomsil_sr.py`, `train_sr.py`, `run_sr.py`
- เป้าหมาย: แทน `RealESRGAN_x4plus.pth` สำหรับงานป้ายทั่วไป, ตัวอักษรไทย, โลโก้ และพื้นสีเรียบ
- เกณฑ์ผ่าน: ไม่แพ้ v1 ในภาพ validation, ไม่ทำตัวอักษรไทยผิด, ไม่ทำ alpha โลโก้หาย, สีพื้นเรียบไม่เกิด noise

### ระยะ 2: Native Face สำหรับภาพบุคคล

- สร้างโมเดลแยก ไม่รวมกับ SR งานป้ายทั่วไป
- ต้องมีข้อมูลใบหน้าที่เจ้าของภาพอนุญาตให้ใช้ฝึก AI อย่างชัดเจน
- เตรียม manifest ส่วนตัวด้วย `python -m native_models.prepare_face_dataset --dataset-dir <private-faces> --consent-dir <private-consent> --output <private-face-manifest.csv> --confirm-consent`
- consent JSON ของแต่ละ subject ต้องมี `subject_id`, `consent_scope` ที่รวม `commercial_ai_training`, และ `rights_holder`
- เกณฑ์ผ่าน: ใบหน้าไม่เพี้ยน, ดวงตาธรรมชาติ, ผิวไม่พลาสติก, identity ไม่หลุด และไม่ hallucinate รายละเอียดที่ทำให้คนเปลี่ยน

### ระยะ 3: Native Detector / Selector

- แทน RetinaFace/facexlib ด้วย detector ที่มีสิทธิ์ถูกต้อง
- เป้าหมาย native คือ `niyomsil-detector-v1`
- ใช้ manifest เดียวกับ Native Face ได้ โดยจัดข้อมูลไว้ใต้ `face_detection/<subject_id>/...` และใส่ sidecar `image.png.json` ที่ระบุ `face_bbox` เมื่อมี annotation
- ระหว่างยังไม่พร้อม สามารถใช้ detector ภายนอกได้เฉพาะเมื่อระบุเครดิตและไม่อ้างว่าเป็นโมเดลของร้าน

### ระยะ 4: Native Runtime และ Installer

- เปลี่ยนชื่อ adapter/build proof จาก ARM compatibility เป็น NiyomSilp Native
- ตัวติดตั้ง v2 ต้องแพ็กเฉพาะโมเดลที่ผ่าน provenance และตรวจรับแล้ว
- ห้ามแทน v1 stable จนกว่า CI, benchmark และ print proof จะผ่านครบ

## สถานะ ณ ตอนนี้

- v1 ยังใช้ Real-ESRGAN, GFPGAN และ RetinaFace ตามที่ระบุใน release note
- v2 มีโครงสำหรับเตรียมข้อมูล, ฝึก SR จากศูนย์, รัน checkpoint ทดลอง และวัดผลเทียบ v1 แล้ว
- v2 มีโครงสำหรับทำ manifest ภาพบุคคล/annotation ตรวจจับใบหน้าที่บังคับ consent แล้ว
- ตรวจสถานะการแทนโมเดลได้ด้วย `python -m native_models.model_replacement_status --repo-root .`
- ตรวจ provenance ก่อนเรียกโมเดลว่า native ได้ด้วย `python -m native_models.validate_provenance <TRAINING_PROVENANCE.json>`
- ยังไม่มีน้ำหนักโมเดลนิยมศิลป์ที่ฝึกเสร็จและผ่านตรวจรับ
- ยังไม่มี v2 installer สำหรับใช้งานจริง

