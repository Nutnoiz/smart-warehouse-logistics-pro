from datetime import datetime, timezone
from uuid import uuid4

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app import models, schemas


PRE_DEPARTURE = {"PLANNED", "TRUCK_ARRIVED", "WAITING_DOCK", "AT_DOCK", "LOADING", "READY_TO_DEPART"}
ACTIVE = PRE_DEPARTURE | {"DEPARTED", "IN_TRANSIT"}
TERMINAL_SHIPMENTS = {"DELIVERED", "RETURNED", "CANCELLED"}


def run_event(db: Session, run: models.DeliveryRun, event_type: str, note=None, latitude=None, longitude=None):
    db.add(models.DeliveryRunEvent(delivery_run_id=run.id, event_type=event_type, note=note, latitude=latitude, longitude=longitude))


def _set_shipment_status(db: Session, shipment: models.Shipment, status: str, note=None, latitude=None, longitude=None):
    shipment.status = status
    db.add(models.ShipmentTrackingEvent(shipment_id=shipment.id, event_type=status, note=note, latitude=latitude, longitude=longitude))


def _run_shipments(db: Session, run_id: int):
    return db.scalars(select(models.Shipment).join(models.DeliveryRunShipment, models.DeliveryRunShipment.shipment_id == models.Shipment.id).where(models.DeliveryRunShipment.delivery_run_id == run_id).order_by(models.DeliveryRunShipment.stop_sequence)).all()


def _refresh_dock_status(db: Session, dock_id: int | None):
    if not dock_id: return
    dock = db.get(models.LoadingDock, dock_id)
    if not dock: return
    occupied = db.scalar(select(func.count()).select_from(models.DeliveryRun).where(models.DeliveryRun.loading_dock_id == dock_id, models.DeliveryRun.status.in_({"AT_DOCK", "LOADING", "READY_TO_DEPART"}))) or 0
    dock.status = "OCCUPIED" if occupied >= dock.capacity_vehicle else "AVAILABLE"


def assign_shipment_to_run(db: Session, shipment: models.Shipment):
    existing = db.scalar(select(models.DeliveryRunShipment).where(models.DeliveryRunShipment.shipment_id == shipment.id))
    if existing: return db.get(models.DeliveryRun, existing.delivery_run_id)
    if not shipment.vehicle_id or not shipment.driver_id: return None
    db.scalar(select(models.Vehicle).where(models.Vehicle.id == shipment.vehicle_id).with_for_update())
    active_run = db.scalar(select(models.DeliveryRun).where(models.DeliveryRun.vehicle_id == shipment.vehicle_id, models.DeliveryRun.status.in_(ACTIVE)).order_by(models.DeliveryRun.id.desc()).with_for_update())
    if active_run:
        if active_run.status not in {"PLANNED", "TRUCK_ARRIVED", "WAITING_DOCK", "AT_DOCK"}:
            raise HTTPException(409, f"Vehicle already has active run {active_run.run_no} in status {active_run.status}")
        if active_run.driver_id != shipment.driver_id or active_run.loading_dock_id != shipment.loading_dock_id:
            raise HTTPException(409, f"Vehicle already assigned to {active_run.run_no} with a different driver or dock")
        run = active_run
    else:
        run = models.DeliveryRun(run_no=f"PENDING-{uuid4().hex}", origin_warehouse_id=shipment.origin_warehouse_id, vehicle_id=shipment.vehicle_id, driver_id=shipment.driver_id, loading_dock_id=shipment.loading_dock_id, planned_departure_at=shipment.planned_departure_at)
        db.add(run); db.flush(); run.run_no = f"RUN-{datetime.now(timezone.utc):%Y%m%d}-{run.id:05d}"; run_event(db, run, "PLANNED", "Delivery run created")
        vehicle = db.get(models.Vehicle, run.vehicle_id); driver = db.get(models.Driver, run.driver_id)
        if vehicle: vehicle.status = "ASSIGNED"
        if driver: driver.status = "ASSIGNED"
    sequence = (db.scalar(select(func.max(models.DeliveryRunShipment.stop_sequence)).where(models.DeliveryRunShipment.delivery_run_id == run.id)) or 0) + 1
    db.add(models.DeliveryRunShipment(delivery_run_id=run.id, shipment_id=shipment.id, stop_sequence=sequence)); db.flush()
    return run


def ensure_delivery_runs(db: Session):
    unassigned = db.scalars(select(models.Shipment).outerjoin(models.DeliveryRunShipment, models.DeliveryRunShipment.shipment_id == models.Shipment.id).where(models.DeliveryRunShipment.id.is_(None), models.Shipment.vehicle_id.is_not(None), models.Shipment.driver_id.is_not(None)).order_by(models.Shipment.id)).all()
    active_groups = {}
    for shipment in unassigned:
        if shipment.status in TERMINAL_SHIPMENTS:
            run = models.DeliveryRun(run_no=f"PENDING-{uuid4().hex}", origin_warehouse_id=shipment.origin_warehouse_id, vehicle_id=shipment.vehicle_id, driver_id=shipment.driver_id, loading_dock_id=shipment.loading_dock_id, status="COMPLETED", planned_departure_at=shipment.planned_departure_at, actual_departure_at=shipment.actual_departure_at, completed_at=shipment.delivered_at or shipment.updated_at)
            db.add(run);db.flush();run.run_no=f"RUN-{shipment.created_at:%Y%m%d}-{run.id:05d}";db.add(models.DeliveryRunShipment(delivery_run_id=run.id,shipment_id=shipment.id,stop_sequence=1));run_event(db,run,"COMPLETED","Backfilled from completed shipment");db.flush()
            continue
        key=(shipment.vehicle_id,shipment.driver_id,shipment.loading_dock_id)
        run=active_groups.get(key)
        if not run:
            status_map={"LOADING":"LOADING","LOADED":"READY_TO_DEPART","DEPARTED":"DEPARTED","IN_TRANSIT":"IN_TRANSIT","ARRIVED":"IN_TRANSIT"}
            run=models.DeliveryRun(run_no=f"PENDING-{uuid4().hex}",origin_warehouse_id=shipment.origin_warehouse_id,vehicle_id=shipment.vehicle_id,driver_id=shipment.driver_id,loading_dock_id=shipment.loading_dock_id,status=status_map.get(shipment.status,"PLANNED"),planned_departure_at=shipment.planned_departure_at,actual_departure_at=shipment.actual_departure_at)
            db.add(run);db.flush();run.run_no=f"RUN-{shipment.created_at:%Y%m%d}-{run.id:05d}";run_event(db,run,run.status,"Backfilled from active shipments");active_groups[key]=run
        sequence=(db.scalar(select(func.max(models.DeliveryRunShipment.stop_sequence)).where(models.DeliveryRunShipment.delivery_run_id==run.id)) or 0)+1
        db.add(models.DeliveryRunShipment(delivery_run_id=run.id,shipment_id=shipment.id,stop_sequence=sequence));db.flush()
    status_rank={"PLANNED":0,"PICKING":0,"READY_TO_LOAD":1,"LOADING":2,"LOADED":3,"DEPARTED":4,"IN_TRANSIT":5,"ARRIVED":5}
    run_status={0:"PLANNED",1:"PLANNED",2:"LOADING",3:"READY_TO_DEPART",4:"DEPARTED",5:"IN_TRANSIT"}
    for run in db.scalars(select(models.DeliveryRun)).all():
        shipments=_run_shipments(db,run.id)
        if shipments and all(shipment.status in TERMINAL_SHIPMENTS for shipment in shipments):
            if run.status in {"WAITING_DOCK","AT_DOCK","LOADING"} and all(s.status=="CANCELLED" for s in shipments):continue
            run.status="COMPLETED";run.completed_at=run.completed_at or max((shipment.delivered_at or shipment.updated_at for shipment in shipments),default=datetime.now(timezone.utc))
        elif run.status=="PLANNED" and shipments:
            run.status=run_status[max(status_rank.get(shipment.status,0) for shipment in shipments)]
    db.commit()


def get_run(db: Session, run_id: int, lock=False):
    stmt=select(models.DeliveryRun).where(models.DeliveryRun.id==run_id)
    run=db.scalar(stmt.with_for_update() if lock else stmt)
    if not run: raise HTTPException(404,"Delivery run not found")
    return run


def list_runs(db: Session, active_only=False):
    stmt=select(models.DeliveryRun).order_by(models.DeliveryRun.created_at.desc(),models.DeliveryRun.id.desc())
    if active_only: stmt=stmt.where(models.DeliveryRun.status.in_(ACTIVE))
    return db.scalars(stmt).all()


def check_in(db: Session, run_id: int, action: schemas.DeliveryRunAction):
    run=get_run(db,run_id,True)
    if run.status!="PLANNED": raise HTTPException(409,"Delivery run must be PLANNED")
    now=datetime.now(timezone.utc);run.status="WAITING_DOCK";run.truck_arrived_at=now
    vehicle=db.get(models.Vehicle,run.vehicle_id);driver=db.get(models.Driver,run.driver_id)
    vehicle.status="WAITING_DOCK";driver.status="ASSIGNED"
    run_event(db,run,"TRUCK_ARRIVED",action.note,action.latitude,action.longitude);run_event(db,run,"WAITING_DOCK","Waiting for loading dock")
    db.commit();return run


def enter_dock(db: Session, run_id: int, payload: schemas.DeliveryRunDockRequest):
    run=get_run(db,run_id,True)
    if run.status!="WAITING_DOCK": raise HTTPException(409,"ยืนยันรถมาถึงคลังก่อนเข้าช่องโหลด")
    if payload.loading_dock_id: run.loading_dock_id=payload.loading_dock_id
    dock=db.scalar(select(models.LoadingDock).where(models.LoadingDock.id==run.loading_dock_id).with_for_update()) if run.loading_dock_id else None
    if not dock or not dock.is_active or dock.status in {"BLOCKED","INACTIVE"} or dock.warehouse_id!=run.origin_warehouse_id: raise HTTPException(409,"เลือกช่องโหลดที่พร้อมใช้งานในคลังเดียวกัน")
    occupied=db.scalar(select(func.count()).select_from(models.DeliveryRun).where(models.DeliveryRun.loading_dock_id==dock.id,models.DeliveryRun.status.in_({"AT_DOCK","LOADING","READY_TO_DEPART"}),models.DeliveryRun.id!=run.id)) or 0
    if occupied>=dock.capacity_vehicle: raise HTTPException(409,"Loading dock is full")
    for shipment in _run_shipments(db,run.id):shipment.loading_dock_id=dock.id
    run.status="AT_DOCK";run.dock_entered_at=datetime.now(timezone.utc);db.get(models.Vehicle,run.vehicle_id).status="AT_DOCK";run_event(db,run,"AT_DOCK",payload.note,payload.latitude,payload.longitude);db.flush();_refresh_dock_status(db,dock.id);db.commit();return run


def start_loading(db: Session, run_id: int, action: schemas.DeliveryRunAction):
    run=get_run(db,run_id,True)
    if run.status!="AT_DOCK": raise HTTPException(409,"Truck must be AT_DOCK before loading")
    shipments=[s for s in _run_shipments(db,run.id) if s.status!="CANCELLED"]
    if not shipments or any(shipment.status!="READY_TO_LOAD" for shipment in shipments): raise HTTPException(409,"Every shipment in the run must be READY_TO_LOAD")
    from app.services.truck_loading import staged
    if any(not staged(db,shipment,True) for shipment in shipments):raise HTTPException(409,"สินค้าทุก HU ต้องอยู่ Loadout และจองครบก่อนเริ่มโหลด")
    for shipment in shipments:_set_shipment_status(db,shipment,"LOADING",f"Loading on {run.run_no}")
    run.status="LOADING";run.loading_started_at=datetime.now(timezone.utc);db.get(models.Vehicle,run.vehicle_id).status="LOADING";run_event(db,run,"LOADING",action.note,action.latitude,action.longitude);db.commit();return run


def complete_loading(db: Session, run_id: int, action: schemas.DeliveryRunAction):
    run=get_run(db,run_id,True)
    if run.status!="LOADING": raise HTTPException(409,"Delivery run must be LOADING")
    shipments=[s for s in _run_shipments(db,run.id) if s.status!="CANCELLED"]
    if not shipments:raise HTTPException(409,"เพิ่มรายการส่งและสแกนสินค้าก่อนยืนยันโหลดครบ")
    for shipment in shipments:
        lines=db.scalars(select(models.ShipmentItem).where(models.ShipmentItem.shipment_id==shipment.id)).all()
        if not lines or any(line.loaded_quantity<line.planned_quantity for line in lines): raise HTTPException(409,f"Shipment {shipment.shipment_no} is not fully loaded")
        if any(not db.get(models.HandlingUnit,line.handling_unit_id) or db.get(models.HandlingUnit,line.handling_unit_id).current_vehicle_id!=run.vehicle_id for line in lines):raise HTTPException(409,"สินค้าไม่ได้อยู่บนรถของรอบนี้ครบ")
    for shipment in shipments:
        if shipment.status=="LOADING":_set_shipment_status(db,shipment,"LOADED",f"Loaded on {run.run_no}")
    run.status="READY_TO_DEPART";run.ready_to_depart_at=datetime.now(timezone.utc);db.get(models.Vehicle,run.vehicle_id).status="READY_TO_DEPART";run_event(db,run,"READY_TO_DEPART",action.note,action.latitude,action.longitude);db.commit();return run


def depart(db: Session, run_id: int, action: schemas.DeliveryRunAction):
    run=get_run(db,run_id,True)
    if run.status!="READY_TO_DEPART": raise HTTPException(409,"Delivery run must be READY_TO_DEPART")
    shipments=[s for s in _run_shipments(db,run.id) if s.status!="CANCELLED"];now=datetime.now(timezone.utc)
    if not shipments or any(shipment.status!="LOADED" for shipment in shipments): raise HTTPException(409,"Every shipment must be LOADED")
    for shipment in shipments:shipment.actual_departure_at=now;_set_shipment_status(db,shipment,"DEPARTED",f"Departed on {run.run_no}")
    run.status="DEPARTED";run.actual_departure_at=now;db.get(models.Vehicle,run.vehicle_id).status="IN_TRANSIT";db.get(models.Driver,run.driver_id).status="IN_TRANSIT";run_event(db,run,"DEPARTED",action.note,action.latitude,action.longitude);dock_id=run.loading_dock_id;db.flush();_refresh_dock_status(db,dock_id);db.commit();return run


def mark_in_transit(db: Session, run_id: int, action: schemas.DeliveryRunAction):
    run=get_run(db,run_id,True)
    if run.status!="DEPARTED": raise HTTPException(409,"Delivery run must be DEPARTED")
    for shipment in _run_shipments(db,run.id):
        if shipment.status=="DEPARTED":_set_shipment_status(db,shipment,"IN_TRANSIT",f"In transit on {run.run_no}")
    run.status="IN_TRANSIT";run_event(db,run,"IN_TRANSIT",action.note,action.latitude,action.longitude);db.commit();return run


def sync_run_completion(db: Session, shipment_id: int):
    link=db.scalar(select(models.DeliveryRunShipment).where(models.DeliveryRunShipment.shipment_id==shipment_id))
    if not link:return
    run=db.get(models.DeliveryRun,link.delivery_run_id);shipments=_run_shipments(db,run.id)
    if shipments and all(shipment.status in TERMINAL_SHIPMENTS for shipment in shipments):
        if run.status in {"WAITING_DOCK","AT_DOCK","LOADING"} and all(s.status=="CANCELLED" for s in shipments):return
        run.status="COMPLETED";run.completed_at=datetime.now(timezone.utc);vehicle=db.get(models.Vehicle,run.vehicle_id);driver=db.get(models.Driver,run.driver_id)
        if vehicle:vehicle.status="AVAILABLE"
        if driver:driver.status="AVAILABLE"
        run_event(db,run,"COMPLETED","All shipments completed")


def run_view(db: Session, run: models.DeliveryRun):
    from app.services.logistics import shipment_view
    vehicle=db.get(models.Vehicle,run.vehicle_id);driver=db.get(models.Driver,run.driver_id);dock=db.get(models.LoadingDock,run.loading_dock_id) if run.loading_dock_id else None
    events=db.scalars(select(models.DeliveryRunEvent).where(models.DeliveryRunEvent.delivery_run_id==run.id).order_by(models.DeliveryRunEvent.event_at,models.DeliveryRunEvent.id)).all()
    shipments=_run_shipments(db,run.id)
    return {"id":run.id,"run_no":run.run_no,"status":run.status,"origin_warehouse_id":run.origin_warehouse_id,"vehicle_id":run.vehicle_id,"driver_id":run.driver_id,"loading_dock_id":run.loading_dock_id,"vehicle_code":vehicle.vehicle_code,"license_plate":vehicle.license_plate,"driver_name":f"{driver.first_name} {driver.last_name}","loading_dock_code":dock.dock_code if dock else None,"planned_departure_at":run.planned_departure_at,"truck_arrived_at":run.truck_arrived_at,"dock_entered_at":run.dock_entered_at,"loading_started_at":run.loading_started_at,"ready_to_depart_at":run.ready_to_depart_at,"actual_departure_at":run.actual_departure_at,"completed_at":run.completed_at,"shipments":[shipment_view(db,shipment) for shipment in shipments],"events":[{"event_type":event.event_type,"event_at":event.event_at,"note":event.note,"latitude":float(event.latitude) if event.latitude is not None else None,"longitude":float(event.longitude) if event.longitude is not None else None} for event in events]}
