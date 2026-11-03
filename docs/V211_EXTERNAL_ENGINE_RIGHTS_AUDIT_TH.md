# NiyomSilp V2.1.1 — ตรวจสิทธิ์และคัดเลือกเอนจินจาก Waifu2x-Extension-GUI

ตรวจสอบเบื้องต้น: 2 พฤศจิกายน 2569 | สถานะ: **งานวิจัย/ทดลองใน PR #18 เท่านั้น**

## กรณีใช้งานที่ต้องตรวจ

ร้านนิยมศิลป์ดีไซน์จะใช้ NiyomSilp บนเครื่องภายในร้านเพื่อปรับปรุง **ภาพงานลูกค้าที่รับค่าจ้าง** แม้ไม่จำหน่ายตัวโปรแกรม ก็ยังเป็นกิจกรรมเชิงพาณิชย์ การอนุญาตให้ใช้ซอฟต์แวร์ส่วนบุคคล (personal use) ไม่ใช่สิทธิ์ครอบคลุมงานร้าน ต้องพิจารณาแยก **(1) ตัว GUI ของบุคคลอื่น (2) ซอร์สโค้ดเอนจิน (3) ไฟล์น้ำหนักโมเดลแต่ละรุ่น (4) ไลบรารี/SDK (5) สิทธิ์แจกจ่ายตัวติดตั้ง**

อ้างอิงเอนจินจาก README ของ Waifu2x-Extension-GUI ณ วันที่ตรวจ: https://github.com/AaronFeng753/Waifu2x-Extension-GUI/blob/master/README.md

- **GUI ของ AaronFeng753:** LICENSE ระบุใช้ฟรีเพื่อใช้ส่วนบุคคลเท่านั้น และแนะนำ Premium สำหรับใช้เชิงพาณิชย์ การมี Premium **ไม่ใช่หลักฐาน** ว่าได้รับสิทธิ์นำโค้ด/GUI/แพ็กเกจไปใช้ใน NiyomSilp โดยตรง: https://github.com/AaronFeng753/Waifu2x-Extension-GUI/blob/master/LICENSE
- **เส้นทางที่เลือก:** รับเอนจินจากเจ้าของโครงการต้นทางโดยตรงตามสิทธิ์ ไม่คัดลอก GUI/ตัวติดตั้ง/ไฟล์จาก Waifu2x-Extension-GUI และไม่ใช้รุ่น Premium เป็นทางลัดสิทธิ์ทรัพย์สินทางปัญญา

## รายการ AI ที่ README ระบุ (ครอบคลุมกลุ่มภาพนิ่งทั้งหมด)

คำว่า *โค้ดใช้ได้* ในตารางไม่ได้แปลว่า *ไฟล์น้ำหนักทุกไฟล์ได้รับอนุญาต* หรือ *ผลงานภาพดีกว่า V2*

| กลุ่ม / เอนจิน | หลักฐานสิทธิ์ที่พบ | สิทธิ์ไฟล์น้ำหนักที่จำเป็นต้องแยกดู | เหมาะกับภาพของร้าน / ขั้นตอน |
| --- | --- | --- | --- |
| **Waifu2x** / waifu2x-ncnn-vulkan | เอนจิน MIT: https://github.com/nihui/waifu2x-ncnn-vulkan/blob/master/LICENSE ; โมเดลต้นฉบับ MIT: https://github.com/nagadomi/waifu2x/blob/master/LICENSE | เจ้าของ nagadomi **ยืนยัน 17 และ 20 ก.ค. 2026** ว่า weights ใน `models/` และรุ่น nunif ที่เผยแพร่ผ่าน release อยู่ภายใต้สิทธิ์เดียวกัน: https://github.com/nagadomi/waifu2x/issues/478 ; ต้องยืนยันว่าไฟล์จริงที่เลือกเป็นรุ่นของเจ้าของที่ได้รับสิทธิ์ ไม่เหมารวม model packs ของบุคคลที่สาม | **เริ่มตัวทดสอบภาพนิ่งอันดับแรก** สำหรับเส้นกราฟิก/ลาย/ภาพวาด/ลด noise; ยังไม่อนุมัติใช้ผลิตจริง |
| **SRMD** / srmd-ncnn-vulkan | เอนจิน MIT: https://github.com/nihui/srmd-ncnn-vulkan/blob/master/LICENSE | ต้นทาง https://github.com/cszn/SRMD ; ยังไม่มีเอกสารสิทธิ์ checkpoint เฉพาะไฟล์ที่ยืนยันในการตรวจนี้ | ทดลองหลังยืนยันที่มาน้ำหนัก; น่าสนใจสำหรับลด noise จากภาพลูกค้า |
| **RealSR** / realsr-ncnn-vulkan | เอนจิน MIT: https://github.com/nihui/realsr-ncnn-vulkan/blob/master/LICENSE ; โค้ด RealSR ต้นทาง Apache-2.0: https://github.com/jixiaozhong/RealSR/blob/master/LICENSE | ต้องตรวจว่าไฟล์ `.bin/.param` ที่จะใช้กับ ncnn เป็น derivative จาก weights ที่อนุญาตเชิงพาณิชย์หรือไม่ | **มีศักยภาพสำหรับภาพถ่ายจริง** คน/สัตว์/สินค้า/พื้นผิว แต่ยังไม่ผ่านสิทธิ์ไฟล์และ A/B |
| **Real-ESRGAN** / RealESRGAN-ncnn-vulkan | โค้ดต้นทาง BSD-3-Clause: https://github.com/xinntao/Real-ESRGAN/blob/master/LICENSE | ต้องตรวจไฟล์ weights ตามชื่อรุ่นและ SHA256; NiyomSilp V2 มีฐานที่ทดสอบและใช้อยู่ | **คง V2 เป็น baseline** ไม่สลับเอนจินเพียงเพราะมี ncnn อีกเวอร์ชัน |
| **Real-CUGAN** / realcugan-ncnn-vulkan | ตัวรัน MIT: https://github.com/nihui/realcugan-ncnn-vulkan/blob/master/LICENSE | ตรวจสิทธิ์ Real-CUGAN ต้นทางและไฟล์ Pro/Se ทุกตัวแยก ไม่ถือว่า MIT ของตัวรันครอบน้ำหนักทุกไฟล์ | เหมาะกับ 2D/ลายเส้นที่เหมาะสม; ทดสอบทีหลังเพราะเสี่ยงเปลี่ยนรูปแบบกราฟิก |
| **Anime4K** | โค้ด MIT: https://github.com/bloc97/Anime4K/blob/master/LICENSE | บางเส้นทางเป็นอัลกอริทึม/ฟิลเตอร์ ไม่จำเป็นต้องมี weight file; ต้องดู build และ dependency จริง | ใช้เปรียบเทียบกราฟิกเส้น/ขอบ; ป้องกัน halo และการลบรายละเอียด |
| **ACNet** / Anime4KCPP | โครงการ Anime4KCPP ระบุโมดูล **video เป็น GPLv3; ส่วนอื่น MIT**: https://github.com/TianZerL/Anime4KCPP | ตรวจว่าบิลด์ ACNet ที่เลือกพ่วง video/GPL หรือมีไฟล์โมเดลจากแหล่งอื่นหรือไม่ | ทดลองเฉพาะ core ภาพนิ่งที่มีสิทธิ์ชัด; ห้ามนำโมดูล GPL มาปิดซอร์สโดยไม่พิจารณาหน้าที่ GPL |
| **RTX Super Resolution (RTX VSR)** | สิทธิ์ SDK ของ NVIDIA เป็น proprietary และมีเงื่อนไขเฉพาะ: https://github.com/NVIDIA/DLSS/blob/main/LICENSE.txt | ไม่ใช่ checkpoint MIT ให้คัดลอก/แจกจ่าย | **พักก่อน** เพราะ GTX 1660 Ti ของร้านไม่ใช่ RTX GPU ตามข้อกำหนด NVIDIA: https://nvidia.custhelp.com/app/answers/detail/a_id/5448 |
| **Waifu2x-caffe** | โค้ด MIT: https://github.com/lltcggie/waifu2x-caffe/blob/master/LICENSE | ตรวจที่มาของโมเดลภายในชุดที่เลือก (เช่น model ที่มาจาก waifu2x) | ตัวรันรุ่นเก่า ซ้ำหน้าที่ Waifu2x-ncnn; **ไม่จำเป็นต้องใส่พร้อมกัน** |
| **Waifu2x-converter** | โครงการ fork ระบุ MIT: https://github.com/DeadSix27/waifu2x-converter-cpp/blob/master/LICENSE ; archived ตั้งแต่ปี 2022 | ตรวจ third-party OpenCV/weights เมื่อเลือก build จริง | ซ้ำหน้าที่ Waifu2x-ncnn; ความสำคัญต่ำ |
| **SRMD-CUDA** | โครงการ https://github.com/MrZihan/Super-resolution-SR-CUDA ไม่มี LICENSE ชัดในรายการไฟล์ที่ตรวจ | **ยังไม่พบสิทธิ์ให้คัดลอก/ดัดแปลงโค้ดหรือโมเดล**; อย่าคาดว่า public repo แปลว่าอนุญาต | **พัก**; ใช้ SRMD-ncnn ที่มี MIT ชัดกว่าเมื่อ weights ผ่านการตรวจ |

**หมายเหตุขอบเขต:** README ระบุ 8 กลุ่มอัลกอริทึมภาพนิ่ง และ 10 เอนจินภาพนิ่งข้างต้น; *ไม่ได้* เป็นหลักฐานว่าตรวจทุกเวอร์ชันและทุก `.bin/.param/.pth` ใน release แล้ว ต้องทำทะเบียน SHA256+URL+LICENSE ต่อไฟล์ก่อนบรรจุตัวติดตั้ง หรือก่อนเรียกว่าได้รับอนุญาตครบทุกโมเดล

### เอนจินวิดีโอ (แยกจากความต้องการงานป้ายภาพนิ่ง)

README ระบุ **RIFE, CAIN, DAIN, IFRNet** และตัวรัน ncnn-vulkan ตามชื่อ ยังไม่ตรวจใบอนุญาต checkpoint รายรุ่นครบ และ **ยังไม่จำเป็นต่อ NiyomSilp V2.1.1 ภาพนิ่ง** จึงไม่ควรเพิ่มภาระพื้นที่/GPU และความเสี่ยงสิทธิ์ในระยะแรก

## สิ่งที่ทำจริงในสาขาทดลองครั้งนี้

- เพิ่ม `tools/v211_external_waifu2x_ab.py` เป็น **ตัวทดสอบเปรียบเทียบแบบ offline** ระหว่าง V2 Real-ESRGAN กับ Waifu2x-ncnn-vulkan ที่ร้านติดตั้ง/จัดหาเองจาก upstream ที่ตรวจสิทธิ์แล้ว
- รับต้นฉบับเดียวกัน ขนาดผลลัพธ์เท่ากัน (2× / 4×) ป้องกันการแก้ไฟล์ต้นฉบับ และสร้างภาพก่อน-หลัง + JSON โดยต่อเข้ากับ `tools/v211_ab_report.py` ที่มีอยู่
- ไม่ดาวน์โหลด weights, ไม่คัดลอกของ AaronFeng753, ไม่บรรจุ binary เพิ่ม, ไม่แตะโปรแกรม V2 ที่ลงอยู่, ไม่ทำ OCR หรือเปลี่ยนข้อความ
- **Fail closed:** รับเฉพาะ PNG สี RGB 8-bit ทึบ ไม่มี ICC/EXIF สำหรับ research crop ไม่เกิน 16 ล้านพิกเซลที่ output; PNG โปร่งใส/ICC/ภาพใบหน้าที่ต้อง restore/ภาพป้ายเต็มผืนต้องทดสอบเส้นทางรักษาสี+alpha+ตัวตนก่อน ห้ามสรุปว่าผ่านแล้ว
- ยังไม่ได้รัน inference จากไฟล์ weights จริงบน GTX 1660 Ti, ยังไม่มีภาพเปรียบเทียบงานลูกค้า, และ **ยังไม่อนุมัติใช้งานจริงหรือเผยแพร่ installer**

## เป้าหมายก่อนเพิ่มโมเดลเข้าสู่โปรแกรม

1. บันทึก `upstream_repo`, รุ่น checkpoint, URL, SHA-256, ใบอนุญาต **โค้ดและ weights**, ข้อกำหนด dependency, ข้อกำหนดรวมใน installer; ปฏิเสธโมเดลที่ยังไม่ผ่าน
2. ทดลองภาพคน/สัตว์/สินค้า/ดอกไม้/ลายไทย/กรอบ/อักษรไทย-จีน-อังกฤษ/สีพื้น/PNG โปร่งใสเทียบกับ V2 เดิมที่ขนาดจริงเท่ากัน **โดยห้ามแก้คำหรือองค์ประกอบต้นฉบับ**
3. ให้ผู้ใช้ตรวจภาพเทียบและยืนยันคุณภาพมากกว่า V2 จริง ทั้งผิวหน้า สีเรียบ ขอบเส้น ลายไทย ชั้น stroke/gradient ตัวอักษรเล็ก และไม่มี halo
4. ตรวจ GPU GTX 1660 Ti 6GB, งานภาพใหญ่ disk-tile, ICC/DPI/alpha, Photoshop/MainTop, ลงตัวติดตั้ง/ถอนติดตั้งและ RIP/งานพิมพ์จริง
5. จึงพิจารณาเพิ่มเป็น **ตัวเลือกในหน้าต่าง NiyomSilp** แบบ opt-in; ห้ามเปลี่ยน default จาก V2 จนผ่านเกณฑ์

> เอกสารนี้เป็นบันทึกตรวจสอบทางเทคนิค/สิทธิ์เบื้องต้น ไม่ใช่คำรับรองทางกฎหมายหรือการรับอนุญาตใช้ไฟล์ทั้งหมด