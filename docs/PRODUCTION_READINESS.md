# Production readiness / Commercial release gate

## Deliverable

V2 เป็น single-company installation ที่ติดตั้งแยกต่อองค์กร ใช้ modular monolith, React/TypeScript, FastAPI/SQLAlchemy และ Alembic
ไม่มีระบบ multi-tenant SaaS, subscription billing, GPS live หรือควบคุมเครื่องจักร
SQLite ใช้ตรวจ demo เท่านั้น PostgreSQL เป็นข้อกำหนดสำหรับหลายผู้ใช้จริง

## Release gate ก่อนขาย / deploy จริง

1. ลงทะเบียนความต้องการลูกค้า: จำนวนคลัง SKU/HU ปริมาณรายการต่อวัน หน่วยสินค้า และสิทธิ์ตามหน้าที่
2. ใช้ PostgreSQL แยก database/user ต่อบริษัท ปิด DEMO_MODE และกำหนด JWT_SECRET แบบสุ่ม ไม่ใช้บัญชี admin/0000
3. ใช้ HTTPS reverse proxy, ปิดการเข้าถึง API โดยตรงจากอินเทอร์เน็ต, จำกัด docs และติดตั้ง security patches
4. ทำ UAT workflow ตาม `UAT.md` กับข้อมูลจริงจำลอง พร้อมรับรองโดยฝ่ายคลังและขนส่ง
5. ทดสอบ PostgreSQL concurrent sessions: double putaway, double allocation/loading/dispatch, double POD และ approval races
6. ทดสอบโหลดตามขนาดลูกค้า กำหนดเวลา API / dashboard ที่ยอมรับได้ และตรวจ query plan / indexes
7. ทำ backup database และ uploads ตามตาราง retention ทดสอบ restore ในเครื่องอื่นและบันทึก RPO/RTO
8. ตรวจ vulnerability ของ dependencies ที่ pin ไว้, ตรวจสิทธิ์, login throttling, token storage และไฟล์อัปโหลด
9. ตรวจ PDPA / ระยะเก็บ POD และข้อมูลลูกค้า แจ้ง privacy policy และกำหนดผู้ดูแลการลบ/ส่งออกข้อมูล
10. เตรียม monitoring, incident response, คู่มือใช้งาน, training, ขอบเขต support/SLA และเอกสารส่งมอบ

## ขอบเขตที่ต้องพัฒนาหรือยืนยันก่อนใช้งานขนาดใหญ่

- หน้าปฏิบัติการเดิมส่วนหนึ่งยังอยู่ใน App.tsx ขนาดใหญ่ ควรทยอยแยก feature และเพิ่ม component tests
- หน้าข้อมูลหลักยังเน้นสร้าง/ปิดใช้งาน การแก้ข้อมูลหลักละเอียด, bulk import และ approval ของ master data ยังต้องเพิ่มตามความต้องการลูกค้า
- สิทธิ์ขณะนี้เป็นระดับบทบาทต่อ installation ทุกคนที่มี read เห็นข้อมูลธุรกิจทั้งหมด ยังไม่มี per-warehouse scope หรือบัญชีคนขับที่จำกัดเฉพาะงานของตน
- นับสต็อกเป็นต่อ inventory row / HU ไม่ใช่ whole-warehouse blind count; ไม่มี valuation/accounting
- คิวงานยังไม่มี assignment, SLA/escalation และ workforce scheduling
- pagination ที่ server ยังไม่ครอบคลุมทุก legacy endpoint; counts/tasks จำกัด 500 รายการล่าสุด
- ภาพรวมสถานีเดิมใช้คลังเริ่มต้น ต้องเพิ่ม warehouse selector และ scoped operation ก่อนติดตั้งหลายคลังจริง
- การจำกัด login failures ต่อบัญชีช่วยเบื้องต้น ต้องเพิ่ม per-IP rate limiting ที่ reverse proxy และ shared store เมื่อ scale หลาย process
- JWT อยู่ใน localStorage จึงต้องตรวจ CSP/XSS สำหรับ production deployment; แนะนำเปลี่ยนเป็น HttpOnly session cookies + CSRF สำหรับ hardening รอบต่อไป
- ไม่อ้างว่าทดสอบ concurrency ด้วย SQLite เทียบเท่า PostgreSQL ต้องใช้ฐานข้อมูลจริงเพื่อรับรอง
- Legacy migrations 0001/0002 ใช้ ORM metadata ที่เลือกตาราง แม้แก้การสร้างตารางรอบรถซ้ำแล้ว ควร freeze historical schema ก่อนปล่อย upgrade path ระยะยาว
- Docker เดิมเป็นไฟล์อ้างอิง V1 ยังไม่ใช่ deployment definition ที่รับรองสำหรับ Pro ให้ใช้คู่มือ manual deployment ก่อน
- การคลิกซ้ำถูกป้องกันในฟอร์มใหม่และบางสถานะ backend แต่ยังไม่มี generalized Idempotency-Key สำหรับทุก mutation

## Security implemented

API authorization, active-user checks, revocation on password/role changes, PBKDF2 password hashes, short-lived signed tokens, independent count approval, private POD access, no operational/POD caching, response request IDs, CSV formula escaping, production config validation และ sanitized integrity errors

สถานะ RC และรายการที่ยังไม่ผ่านจะต้องแจ้งลูกค้าก่อนตกลงส่งมอบ ไม่ควรโฆษณาว่า audited หรือ production-certified
