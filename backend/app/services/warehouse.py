from datetime import datetime, time, timezone
from zoneinfo import ZoneInfo
from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from app import models, schemas

def warehouse_code(db: Session, warehouse_id: int) -> str:
    code = db.scalar(select(models.Warehouse.warehouse_code).where(models.Warehouse.id == warehouse_id))
    if not code:
        raise HTTPException(404, "Warehouse not found")
    return code.upper()

def create_rack(db: Session, payload: schemas.RackCreate) -> models.Rack:
    zone = db.get(models.Zone, payload.zone_id)
    if not zone:
        raise HTTPException(404, "Zone not found")
    try:
        rack = models.Rack(**payload.model_dump())
        db.add(rack)
        db.flush()
        wh_code = warehouse_code(db, zone.warehouse_id)
        for bay in range(1, rack.bay_count + 1):
            for level in range(1, rack.level_count + 1):
                for position in range(1, rack.positions_per_level + 1):
                    code = f"{wh_code}-{zone.zone_code.upper()}-A{rack.aisle_no:02d}-R{rack.rack_no:02d}-B{bay:03d}-L{level:02d}-P{position:02d}"
                    db.add(models.Location(warehouse_id=zone.warehouse_id, location_code=code, location_type="STORAGE", zone_id=zone.id, rack_id=rack.id, bay_no=bay, level_no=level, position_no=position))
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(409, "Rack or generated location code already exists") from exc
    return rack

def create_station(db: Session, payload: schemas.StationCreate) -> models.Station:
    type_code = {"INBOUND":"INB", "CHECKOUT":"CHK", "LOADOUT":"LOD", "OUTBOUND":"OUT", "RETURN":"RET"}.get(payload.station_type, payload.station_type[:3].upper())
    code = f"{warehouse_code(db, payload.warehouse_id)}-ST-{type_code}-{payload.sequence:02d}"
    station = models.Station(**payload.model_dump(), station_code=code)
    db.add(station)
    db.flush()
    db.add(models.Location(warehouse_id=payload.warehouse_id, location_code=code, location_type="STATION", station_id=station.id))
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(409, "Station code already exists") from exc
    return station

def create_dock(db: Session, payload: schemas.DockCreate) -> models.LoadingDock:
    data = payload.model_dump(exclude={"sequence"})
    dock = models.LoadingDock(**data, dock_code=f"{warehouse_code(db, payload.warehouse_id)}-DOCK-{payload.sequence:02d}")
    db.add(dock)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(409, "Loading dock code already exists") from exc
    return dock

def dashboard(db: Session) -> dict:
    count = lambda model: db.scalar(select(func.count()).select_from(model)) or 0
    total = count(models.Location)
    available = db.scalar(select(func.count()).select_from(models.Location).where(models.Location.status == models.LocationStatus.AVAILABLE)) or 0
    occupied = db.scalar(select(func.count()).select_from(models.Location).where(models.Location.status == models.LocationStatus.OCCUPIED)) or 0
    blocked = db.scalar(select(func.count()).select_from(models.Location).where(models.Location.status == models.LocationStatus.BLOCKED)) or 0
    storage_total = db.scalar(select(func.count()).select_from(models.Location).where(models.Location.location_type == "STORAGE")) or 0
    shipment_count = lambda status: db.scalar(select(func.count()).select_from(models.Shipment).where(models.Shipment.status == status)) or 0
    bangkok=ZoneInfo("Asia/Bangkok");today=datetime.now(bangkok).date();day_start=datetime.combine(today,time.min,bangkok).astimezone(timezone.utc);day_end=datetime.combine(today,time.max,bangkok).astimezone(timezone.utc)
    shipments_today=db.scalar(select(func.count()).select_from(models.Shipment).where(models.Shipment.created_at.between(day_start,day_end))) or 0
    delivered_today=db.scalar(select(func.count()).select_from(models.Shipment).where(models.Shipment.status=="DELIVERED",models.Shipment.delivered_at.between(day_start,day_end))) or 0
    run_count=lambda statuses: db.scalar(select(func.count()).select_from(models.DeliveryRun).where(models.DeliveryRun.status.in_(statuses))) or 0
    return {"warehouses": count(models.Warehouse), "zones": count(models.Zone), "racks": count(models.Rack), "total_locations": total, "available_locations": available, "occupied_locations": occupied, "blocked_locations": blocked, "stations": count(models.Station), "loading_docks": count(models.LoadingDock), "utilization_percent": round(occupied / storage_total * 100, 1) if storage_total else 0, "shipments_today": shipments_today, "ready_to_load": shipment_count("READY_TO_LOAD"), "in_transit": shipment_count("IN_TRANSIT"), "delivered": delivered_today, "delivery_failed": shipment_count("DELIVERY_FAILED"), "vehicles_available": db.scalar(select(func.count()).select_from(models.Vehicle).where(models.Vehicle.status == "AVAILABLE")) or 0, "pending_putaway": db.scalar(select(func.count()).select_from(models.HandlingUnit).where(models.HandlingUnit.current_status=="RECEIVED")) or 0, "pending_returns": db.scalar(select(func.count()).select_from(models.HandlingUnit).where(models.HandlingUnit.current_status=="RETURN_HOLD")) or 0, "trucks_waiting": run_count({"WAITING_DOCK","AT_DOCK","LOADING","READY_TO_DEPART"}), "trucks_on_route": run_count({"DEPARTED","IN_TRANSIT"})}
