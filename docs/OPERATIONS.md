# Installation and operations

## Demo Windows

ใช้ SETUP.cmd ครั้งแรก แล้ว START_SMART_WAREHOUSE.cmd
เว็บ 5180, API 8010, SQLite warehouse-pro.db; ปิดทั้งสอง terminal เพื่อหยุด
launcher เปิดหน้าต่าง terminal เพราะผู้ใช้ต้องดู error และหยุด process ได้

## Production manual setup (no Docker required)

1. Provision PostgreSQL และ application role ที่ไม่มี superuser privileges
2. Copy backend/.env.production.example เป็น backend/.env แล้วเปลี่ยนค่าทุก CHANGE/REPLACE
3. กำหนด database password และ secret ผ่านระบบ secret ของ host/องค์กร เก็บ .env ออกจาก Git
4. Install backend requirements ใน venv และรัน alembic upgrade head จาก backend
5. รัน python -m app.bootstrap เพื่อสร้างผู้ดูแลเริ่มต้นเท่านั้น ไม่ seed demo
6. รัน uvicorn app.main:app --host 127.0.0.1 --port 8010 ผ่าน service manager ที่ restart ได้
7. Build frontend ด้วย npm ci และ npm run build ใช้ dist ผ่าน reverse proxy HTTPS
8. Proxy /api และ /files ไป backend origin เดียวกัน Cookie POD ต้องมี HTTPS ใน production
9. เพิ่ม rate limits สำหรับ /api/auth/login, request-size limit สำหรับ upload และจำกัด /docs, /openapi.json
10. ตั้ง monitoring health endpoint, error logs, disk space, database availability และ backup failures

## Backup / restore

Demo: หยุด backend ก่อน แล้วใช้ BACKUP_DEMO.cmd เพื่อสร้างสำเนา DB และ uploads ใน backups พร้อม timestamp
Restore demo: หยุด backend, เก็บ DB ปัจจุบันแยกก่อน, copy สำเนา warehouse-pro.db และ uploads กลับ แล้วเปิดตรวจ HU/station/shipments

Production: ใช้ pg_dump -Fc ของ database พร้อม archive uploads ไปที่ backup storage ซึ่งเข้ารหัสและมีสิทธิ์จำกัด
ห้ามอัปโหลด POD และ backup ขึ้น public repository
ทดสอบ pg_restore ใน database ใหม่พร้อม uploads และตรวจจำนวน records, HU custody และ POD ก่อนสลับบริการ
ค่าตั้งต้นที่เสนอ: daily backup, เก็บ 30 วัน, off-site copy และ restore drill รายเดือน; ปรับตาม SLA ของลูกค้า

## Upgrade

หยุดรับรายการชั่วคราว → backup DB/uploads/config → deploy code → alembic upgrade head → smoke test → เปิดรับงาน
ไม่ downgrade schema ที่มีข้อมูลจริงโดยไม่ทดสอบ restore path
โปรเจกต์นี้ไม่ได้ migrate ข้อมูลจาก V1 อัตโนมัติ หากต้องย้ายข้อมูลต้องทำ mapping และ reconciliation ก่อน
