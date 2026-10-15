"""Truck-first loading: register arrivals independently, then add staged shipments."""
from datetime import datetime, timezone
from decimal import Decimal
from uuid import uuid4
from fastapi import HTTPException
from sqlalchemy import select, func
from app import models
from app.services.delivery_runs import ACTIVE, get_run, run_event, _run_shipments, _set_shipment_status, _refresh_dock_status
from app.services.inventory import audit
from app.services.logistics import event

def _lock_loading_write(db):
    # SQLite ignores SELECT FOR UPDATE: acquire its write lock before reading state.
    connection=db.connection()
    if connection.dialect.name=='sqlite' and not connection.connection.driver_connection.in_transaction:
        connection.exec_driver_sql('BEGIN IMMEDIATE')

def register(db,p):
    warehouse=db.get(models.Warehouse,p.origin_warehouse_id)
    vehicle=db.scalar(select(models.Vehicle).where(models.Vehicle.id==p.vehicle_id).with_for_update())
    driver=db.scalar(select(models.Driver).where(models.Driver.id==p.driver_id).with_for_update())
    if not warehouse or not warehouse.is_active or not vehicle or not driver or not vehicle.is_active or not driver.is_active:raise HTTPException(422,'คลัง รถ และคนขับต้องพร้อมใช้งาน')
    active=db.scalar(select(models.DeliveryRun).where(models.DeliveryRun.status.in_(ACTIVE),((models.DeliveryRun.vehicle_id==vehicle.id)|(models.DeliveryRun.driver_id==driver.id))))
    if active or vehicle.status!='AVAILABLE' or driver.status!='AVAILABLE':raise HTTPException(409,'รถหรือคนขับมีรอบที่ยังไม่ปิด ไม่สามารถลงทะเบียนซ้ำได้')
    if db.scalar(select(models.HandlingUnit.id).where(models.HandlingUnit.current_vehicle_id==vehicle.id)):raise HTTPException(409,'รถยังมีสินค้าอยู่ ต้องปิดงานรอบเดิมก่อน')
    dock=db.get(models.LoadingDock,p.loading_dock_id) if p.loading_dock_id else None
    if p.loading_dock_id and (not dock or not dock.is_active or dock.warehouse_id!=warehouse.id or dock.status in {'BLOCKED','INACTIVE'}):raise HTTPException(422,'ช่องโหลดไม่พร้อมใช้งานหรืออยู่คนละคลัง')
    run=models.DeliveryRun(run_no='PENDING-'+uuid4().hex,origin_warehouse_id=warehouse.id,vehicle_id=vehicle.id,driver_id=driver.id,loading_dock_id=p.loading_dock_id,status='WAITING_DOCK' if p.arrived else 'PLANNED',truck_arrived_at=datetime.now(timezone.utc) if p.arrived else None)
    db.add(run);db.flush();run.run_no=f'RUN-{datetime.now(timezone.utc):%Y%m%d}-{run.id:05d}'
    vehicle.status='WAITING_DOCK' if p.arrived else 'ASSIGNED';driver.status='ASSIGNED'
    run_event(db,run,'TRUCK_ARRIVED' if p.arrived else 'PLANNED','Registered independently of shipment')
    audit(db,'REGISTER_TRUCK','DELIVERY_RUN',run.id,{'vehicle_id':vehicle.id,'driver_id':driver.id})
    db.commit();return run

def choices(db,warehouse_id):
    return db.scalars(select(models.DeliveryRun).join(models.Vehicle,models.Vehicle.id==models.DeliveryRun.vehicle_id).join(models.Driver,models.Driver.id==models.DeliveryRun.driver_id).join(models.LoadingDock,models.LoadingDock.id==models.DeliveryRun.loading_dock_id).where(models.DeliveryRun.origin_warehouse_id==warehouse_id,models.DeliveryRun.status.in_({'AT_DOCK','LOADING'}),models.Vehicle.is_active.is_(True),models.Driver.is_active.is_(True),models.LoadingDock.is_active.is_(True),models.LoadingDock.status.not_in({'BLOCKED','INACTIVE'})).order_by(models.DeliveryRun.dock_entered_at,models.DeliveryRun.id)).all()

def staged(db,shipment,lock=False):
    if shipment.status not in {'PICKING','READY_TO_LOAD'}:return False
    lines=db.scalars(select(models.ShipmentItem).where(models.ShipmentItem.shipment_id==shipment.id)).all()
    if not lines:return False
    for line in lines:
        hu=db.scalar(select(models.HandlingUnit).where(models.HandlingUnit.id==line.handling_unit_id).with_for_update()) if lock else db.get(models.HandlingUnit,line.handling_unit_id) if line.handling_unit_id else None
        inv=db.scalar(select(models.Inventory).where(models.Inventory.handling_unit_id==line.handling_unit_id).with_for_update()) if lock else db.scalar(select(models.Inventory).where(models.Inventory.handling_unit_id==line.handling_unit_id))
        loc=db.get(models.Location,hu.current_location_id) if hu and hu.current_location_id else None
        if not hu or hu.current_node_type!='WAREHOUSE_LOCATION' or not loc or loc.warehouse_id!=shipment.origin_warehouse_id or not loc.station or loc.station.station_type!=models.StationType.LOADOUT or not loc.is_active or not loc.station.is_active or not inv or inv.quantity!=line.planned_quantity or inv.reserved_quantity!=line.planned_quantity or line.loaded_quantity:return False
    return True

def queue(db,rid):
    run=get_run(db,rid)
    if run.status not in {'AT_DOCK','LOADING'}:return []
    rows=db.scalars(select(models.Shipment).outerjoin(models.DeliveryRunShipment,models.DeliveryRunShipment.shipment_id==models.Shipment.id).where(models.Shipment.origin_warehouse_id==run.origin_warehouse_id,models.Shipment.status.in_({'PICKING','READY_TO_LOAD'}),models.DeliveryRunShipment.id.is_(None)).order_by(models.Shipment.created_at,models.Shipment.id)).all()
    return [s for s in rows if staged(db,s)]

def attach(db,rid,sid):
    _lock_loading_write(db)
    run=get_run(db,rid,True)
    if run.status not in {'AT_DOCK','LOADING'} or not run.loading_dock_id:raise HTTPException(409,'เลือกรถที่เข้าช่องโหลดแล้วเท่านั้น')
    vehicle=db.get(models.Vehicle,run.vehicle_id);driver=db.get(models.Driver,run.driver_id);dock=db.get(models.LoadingDock,run.loading_dock_id)
    if not vehicle.is_active or not driver.is_active or not dock or not dock.is_active or dock.status in {'BLOCKED','INACTIVE'}:raise HTTPException(409,'รถ คนขับ หรือช่องโหลดไม่พร้อมใช้งาน')
    shipment=db.scalar(select(models.Shipment).where(models.Shipment.id==sid).with_for_update())
    if not shipment or shipment.origin_warehouse_id!=run.origin_warehouse_id:raise HTTPException(409,'รายการส่งต้องอยู่คลังเดียวกับรถ')
    existing=db.scalar(select(models.DeliveryRunShipment).where(models.DeliveryRunShipment.shipment_id==sid).with_for_update())
    if existing:
        if existing.delivery_run_id==rid:return run
        owner=db.get(models.DeliveryRun,existing.delivery_run_id)
        raise HTTPException(409,f'รายการส่งถูกจองให้รอบรถ {owner.run_no} แล้ว กรุณาโหลดคิวล่าสุด')
    if not staged(db,shipment,True):raise HTTPException(409,'สินค้าทุกรายการต้องตรวจผ่านและอยู่ Loadout ก่อนเลือกรถ')
    ids=[s.id for s in _run_shipments(db,rid) if s.status!='CANCELLED']+[sid]
    weight=db.scalar(select(func.coalesce(func.sum(models.HandlingUnit.gross_weight_kg),0)).join(models.ShipmentItem,models.ShipmentItem.handling_unit_id==models.HandlingUnit.id).where(models.ShipmentItem.shipment_id.in_(ids))) or 0
    if vehicle.max_weight_kg and Decimal(str(weight))>vehicle.max_weight_kg:raise HTTPException(409,'น้ำหนักรายการส่งเกินความจุรถ กรุณาเลือกรถหรือแยกสินค้าใหม่')
    sequence=(db.scalar(select(func.max(models.DeliveryRunShipment.stop_sequence)).where(models.DeliveryRunShipment.delivery_run_id==rid)) or 0)+1
    db.add(models.DeliveryRunShipment(delivery_run_id=rid,shipment_id=sid,stop_sequence=sequence))
    shipment.vehicle_id=run.vehicle_id;shipment.driver_id=run.driver_id;shipment.loading_dock_id=run.loading_dock_id
    _set_shipment_status(db,shipment,'LOADING' if run.status=='LOADING' else 'READY_TO_LOAD',f'Selected parked truck {run.run_no}')
    run_event(db,run,'SHIPMENT_ADDED',f'{shipment.shipment_no} added')
    audit(db,'SELECT_PARKED_TRUCK','SHIPMENT',sid,{'run_id':rid})
    db.commit();return run

def detach(db,rid,sid):
    _lock_loading_write(db)
    run=get_run(db,rid,True)
    if run.status not in {'AT_DOCK','LOADING'}:raise HTTPException(409,'ถอดรายการได้เฉพาะรถที่ยังโหลดไม่เสร็จ')
    shipment=db.scalar(select(models.Shipment).where(models.Shipment.id==sid).with_for_update())
    link=db.scalar(select(models.DeliveryRunShipment).where(models.DeliveryRunShipment.shipment_id==sid,models.DeliveryRunShipment.delivery_run_id==rid))
    if not shipment or not link:raise HTTPException(404,'ไม่พบรายการในรอบรถ')
    lines=db.scalars(select(models.ShipmentItem).where(models.ShipmentItem.shipment_id==sid).with_for_update()).all()
    for line in lines:
        hu=db.get(models.HandlingUnit,line.handling_unit_id) if line.handling_unit_id else None
        if line.loaded_quantity or (hu and hu.current_node_type=='VEHICLE'):raise HTTPException(409,'มีสินค้าสแกนขึ้นรถแล้ว ไม่สามารถถอดรายการออกได้')
    db.delete(link);shipment.vehicle_id=None;shipment.driver_id=None;shipment.loading_dock_id=None
    _set_shipment_status(db,shipment,'READY_TO_LOAD',f'Removed from {run.run_no}; waiting for another truck')
    run_event(db,run,'SHIPMENT_REMOVED',shipment.shipment_no)
    audit(db,'REMOVE_PARKED_TRUCK','SHIPMENT',sid,{'run_id':rid})
    db.commit();return run

def cancel_empty(db,rid):
    run=get_run(db,rid,True)
    if run.status not in {'PLANNED','WAITING_DOCK','AT_DOCK','LOADING'}:raise HTTPException(409,'รอบรถไม่อยู่ในสถานะที่ยกเลิกได้')
    if any(s.status!='CANCELLED' for s in _run_shipments(db,rid)):raise HTTPException(409,'ถอดรายการส่งออกจากรถก่อนยกเลิกรอบ')
    if db.scalar(select(models.HandlingUnit.id).where(models.HandlingUnit.current_vehicle_id==run.vehicle_id)):raise HTTPException(409,'ยังมีสินค้าอยู่บนรถ')
    run.status='CANCELLED';run.completed_at=datetime.now(timezone.utc);db.get(models.Vehicle,run.vehicle_id).status='AVAILABLE';db.get(models.Driver,run.driver_id).status='AVAILABLE'
    run_event(db,run,'CANCELLED','Empty truck run cancelled')
    audit(db,'CANCEL_EMPTY_RUN','DELIVERY_RUN',rid,{})
    db.flush();_refresh_dock_status(db,run.loading_dock_id);db.commit();return run

def scan(db,rid,code):
    _lock_loading_write(db)
    run=get_run(db,rid,True)
    if run.status!='LOADING':raise HTTPException(409,'เริ่มโหลดรอบรถก่อนสแกนสินค้า')
    hu=db.scalar(select(models.HandlingUnit).where(models.HandlingUnit.hu_code==code.strip()).with_for_update())
    line=db.scalar(select(models.ShipmentItem).join(models.Shipment,models.Shipment.id==models.ShipmentItem.shipment_id).join(models.DeliveryRunShipment,models.DeliveryRunShipment.shipment_id==models.Shipment.id).where(models.DeliveryRunShipment.delivery_run_id==rid,models.ShipmentItem.handling_unit_id==hu.id,models.Shipment.status=='LOADING')) if hu else None
    if not line:raise HTTPException(409,'HU นี้ไม่อยู่ในคิวโหลดของรถคันนี้')
    if line.loaded_quantity:raise HTTPException(409,'HU นี้สแกนขึ้นรถแล้ว')
    from app.services.logistics import load_hu
    load_hu(db,line.shipment_id,hu.hu_code)
    return get_run(db,rid)
