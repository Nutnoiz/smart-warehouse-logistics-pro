import {NavLink} from 'react-router-dom'
import type {Shipment} from '../types'

export function ShipmentTransport({shipment:s}:{shipment:Shipment}){
  const ready=s.items.length>0&&s.items.every(i=>i.current_station_type==='LOADOUT')
  return <article className="panel transport-assignment">
    <h3>{s.delivery_run_id?'รอบรถของรายการนี้':'การจัดรถและโหลดสินค้า'}</h3>
    {s.delivery_run_id?<>
      <p className="helper">จองให้ {s.vehicle_code} · {s.driver_name} · ช่อง {s.loading_dock_code||'ยังไม่เข้าช่องโหลด'}</p>
      <p className="helper">การจองไม่ใช่การขึ้นรถจริง ตรวจและสแกน HU ที่หน้ารอบรถเท่านั้น</p>
      <NavLink className="button" to={'/delivery-runs/'+s.delivery_run_id}>เปิดรอบรถ {s.delivery_run_no}</NavLink>
    </>:<>
      <p className="pro-notice info">{ready?'สินค้าพร้อมอยู่ Loadout ยังไม่จองรถ เปิดรอบรถที่เข้าช่องโหลดแล้วเพื่อจองรายการนี้':'นำสินค้าทุกรายการตรวจผ่านไป Loadout ก่อน จากนั้นจองและสแกนขึ้นรถที่หน้ารอบรถ'}</p>
      <NavLink className="button" to="/delivery-runs">ไปจัดรถและโหลดสินค้า</NavLink>
    </>}
  </article>
}
