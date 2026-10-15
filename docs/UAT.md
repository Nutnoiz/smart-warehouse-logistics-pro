# UAT — Warehouse Pro

ใช้ฐานข้อมูลสำเนา ห้ามใช้สต็อกจริงเพื่อลอง workflow

| สถานการณ์ | ผลที่ต้องเห็น |
|---|---|
| เข้า admin / 0000 | Dashboard ข้อมูล demo และป้าย DEMO |
| รับ HU ใหม่แล้วออกจากหน้า | เห็น HU ค้างที่ Inbound และ Pending Putaway |
| เลือกชั้นเอง | เลือกโซน/ชั้น/Bay/Level/Position และยืนยันได้เมื่อ compatible |
| จัดเก็บ | HU อยู่ Rack map ตำแหน่งเดียวและสถานีรับไม่มี HU นั้น |
| Ctrl+K ค้นหา HU | แสดงตำแหน่งจริงและเปิด inventory ที่กรอง HU |
| เบิก 20 จาก 100 | Shipment 20, HU ส่งออกใหม่, ยอดเดิมบนชั้น 80 |
| Checkout → Loadout | กดขั้นตอนถัดไปและเห็น station cargo เปลี่ยน |
| รถเดียวสอง Shipment | Dashboard มีรถคันเดียว กดดูรายการทั้งสองและกดต่อดู shipment |
| รถออก | การ์ดเปลี่ยนจาก waiting/loading เป็น on route |
| ส่งสำเร็จ | สถานะ Delivered, receiver/POD, ประวัติ movement และ truck run ปิดเมื่อครบ |
| ส่งไม่สำเร็จ | คืนเข้าคลังและอยู่ Return Hold ก่อนเลือก Return Rack หรือ normal storage |
| ย้าย HU จองแล้ว | ถูกปฏิเสธและตำแหน่งเดิมยังอยู่ |
| เจ้าหน้าที่นับ 98 จาก 100 | stock ยัง 100 จน manager คนอื่นอนุมัติ |
| อนุมัติหลังสต็อกเปลี่ยน | ถูกปฏิเสธว่าต้องนับใหม่ ไม่มีการปรับยอด |
| อนุมัติ count ซ้ำ | ถูกปฏิเสธและไม่เกิด movement เพิ่ม |
| Viewer ยิง POST โดยตรง | HTTP 403 ไม่เกิดการเขียนข้อมูล |
| เปลี่ยนรหัส / สิทธิ์ / ปิดบัญชี | token เก่าใช้ไม่ได้ |
| export CSV | เปิด Excel ภาษาไทยได้ หน่วยแยกกัน ค่าที่เริ่ม = ไม่ execute |
| มือถือ 390px | sidebar ปิด/เปิดได้ ฟอร์มไม่ล้น และตารางเลื่อนแนวนอนได้ |
| refresh / restart | รายการยังอยู่ ไม่มี seed สร้างข้อมูลซ้ำ |

ก่อนใช้หลายผู้ใช้จริงต้องรัน race tests บน PostgreSQL ตาม readiness gate และบันทึกผลแยกจาก unit/regression tests
