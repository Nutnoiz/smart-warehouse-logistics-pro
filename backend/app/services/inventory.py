from datetime import datetime, timezone
import json
from decimal import Decimal
from uuid import uuid4
from fastapi import HTTPException
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from app import models, schemas

def suggested_hu_code(db: Session):
    while True:
        code=f"HU-{datetime.now(timezone.utc):%Y%m%d}-{uuid4().hex[:10].upper()}"
        if not db.scalar(select(models.HandlingUnit.id).where(models.HandlingUnit.hu_code==code)):return code

def movement_no(db: Session) -> str:
    return f"MOV-{datetime.now(timezone.utc):%Y%m%d}-{uuid4().hex[:12].upper()}"

def audit(db:Session,action:str,entity_type:str,entity_id:str,data:dict):
    db.add(models.AuditLog(user_id=db.info.get("user_id"),action=action,entity_type=entity_type,entity_id=str(entity_id),new_data=json.dumps(data,default=str)))

def record_movement(db: Session, movement_type: str, hu: models.HandlingUnit, inventory: models.Inventory, source_location_id=None, destination_location_id=None, source_vehicle_id=None, destination_vehicle_id=None, shipment_id=None):
    movement = models.StockMovement(movement_no=movement_no(db), movement_type=movement_type, source_location_id=source_location_id, destination_location_id=destination_location_id, source_vehicle_id=source_vehicle_id, destination_vehicle_id=destination_vehicle_id, shipment_id=shipment_id, completed_at=datetime.now(timezone.utc))
    db.add(movement); db.flush()
    db.add(models.StockMovementItem(movement_id=movement.id, handling_unit_id=hu.id, product_id=inventory.product_id, quantity=inventory.quantity, unit_of_measure=inventory.unit_of_measure))
    return movement

def receive(db: Session, payload: schemas.ReceiveRequest):
    code=payload.hu_code.strip()
    if not code or (payload.auto_hu_code and db.scalar(select(models.HandlingUnit.id).where(models.HandlingUnit.hu_code==code))):code=suggested_hu_code(db)
    product = db.get(models.Product, payload.product_id)
    station = db.get(models.Station, payload.station_id)
    if not product or not station or station.station_type != models.StationType.INBOUND:
        raise HTTPException(422, "Valid product and INBOUND station are required")
    if not product.is_active or not station.is_active:
        raise HTTPException(409, 'Product or inbound station is inactive')
    location = db.scalar(select(models.Location).where(models.Location.station_id == station.id).with_for_update())
    if not location or location.status == models.LocationStatus.BLOCKED:
        raise HTTPException(409, "Inbound station is unavailable")
    station_load=db.scalar(select(func.count()).select_from(models.HandlingUnit).where(models.HandlingUnit.current_location_id==location.id)) or 0
    if station_load>=station.capacity_hu: raise HTTPException(409,"Inbound station capacity exceeded")
    if db.scalar(select(models.HandlingUnit).where(models.HandlingUnit.hu_code == code)):
        raise HTTPException(409, "HU code already exists")
    try:
        hu = models.HandlingUnit(hu_code=code, hu_type=payload.hu_type, current_location_id=location.id, current_node_type="WAREHOUSE_LOCATION", current_status="RECEIVED",gross_weight_kg=float(product.weight_kg or 0)*payload.quantity)
        db.add(hu); db.flush()
        item = models.HandlingUnitItem(handling_unit_id=hu.id, product_id=product.id, lot_no=payload.lot_no, batch_no=payload.batch_no, quantity=payload.quantity, unit_of_measure=payload.unit_of_measure)
        inv = models.Inventory(product_id=product.id, handling_unit_id=hu.id, location_id=location.id, lot_no=payload.lot_no, batch_no=payload.batch_no, quantity=payload.quantity, reserved_quantity=0, unit_of_measure=payload.unit_of_measure)
        db.add_all([item, inv]); db.flush()
        record_movement(db, "RECEIVE", hu, inv, destination_location_id=location.id)
        db.add(models.WarehouseTask(task_no=f"TSK-PUT-{hu.id:06d}", task_type="PUTAWAY", handling_unit_id=hu.id, source_location_id=location.id))
        audit(db,"RECEIVE","HANDLING_UNIT",hu.id,{"hu_code":hu.hu_code,"location_id":location.id,"quantity":payload.quantity})
        db.commit(); return hu
    except IntegrityError:
        db.rollback(); raise HTTPException(409, 'HU code already exists; request a new suggestion or change the manual code')
    except Exception:
        db.rollback(); raise

def putaway_options(db: Session, hu_code: str):
    hu = db.scalar(select(models.HandlingUnit).where(models.HandlingUnit.hu_code == hu_code))
    if not hu: raise HTTPException(404, "Handling Unit not found")
    inv = db.scalar(select(models.Inventory).where(models.Inventory.handling_unit_id == hu.id))
    if not inv: raise HTTPException(404, "Inventory for Handling Unit not found")
    product = db.get(models.Product, inv.product_id)
    stmt = select(models.Location).join(models.Zone, models.Location.zone_id == models.Zone.id).join(models.Rack, models.Location.rack_id == models.Rack.id).where(models.Location.location_type == "STORAGE", models.Location.status == models.LocationStatus.AVAILABLE, models.Location.is_active.is_(True), models.Zone.is_active.is_(True), models.Rack.is_active.is_(True)).order_by(models.Location.location_code)
    if product.default_storage_profile_id:
        stmt = stmt.where(models.Zone.storage_profile_id == product.default_storage_profile_id)
    locations = db.scalars(stmt).all()
    if not locations: raise HTTPException(409, "No suitable storage location available")
    return locations

def recommend_putaway(db: Session, hu_code: str):
    return putaway_options(db, hu_code)[0]

def return_putaway_options(db: Session, hu_code: str):
    hu = db.scalar(select(models.HandlingUnit).where(models.HandlingUnit.hu_code == hu_code))
    if not hu: raise HTTPException(404, "Handling Unit not found")
    source = db.get(models.Location, hu.current_location_id) if hu.current_location_id else None
    if hu.current_status != "RETURN_HOLD" or not source or not source.station or source.station.station_type != models.StationType.RETURN:
        raise HTTPException(409, "Handling Unit must be at a RETURN station")
    inv = db.scalar(select(models.Inventory).where(models.Inventory.handling_unit_id == hu.id))
    product = db.get(models.Product, inv.product_id) if inv else None
    if not inv or not product: raise HTTPException(404, "Inventory for Handling Unit not found")
    stmt = select(models.Location).join(models.Zone, models.Location.zone_id == models.Zone.id).join(models.Rack, models.Location.rack_id == models.Rack.id).where(models.Location.location_type == "STORAGE", models.Location.status == models.LocationStatus.AVAILABLE, models.Location.is_active.is_(True), models.Zone.is_active.is_(True), models.Rack.is_active.is_(True), or_(models.Zone.zone_code == "RTN", models.Zone.storage_profile_id == product.default_storage_profile_id)).order_by(models.Zone.zone_code != "RTN", models.Location.location_code)
    locations = db.scalars(stmt).all()
    if not locations: raise HTTPException(409, "No return or compatible storage location available")
    return locations

def move_hu(db: Session, hu_code: str, destination_location_id: int, movement_type="TRANSFER", shipment_id=None):
    hu = db.scalar(select(models.HandlingUnit).where(models.HandlingUnit.hu_code == hu_code).with_for_update())
    dest = db.scalar(select(models.Location).where(models.Location.id == destination_location_id).with_for_update())
    if not hu or not dest: raise HTTPException(404, "HU or destination not found")
    if not dest.is_active or dest.status == models.LocationStatus.BLOCKED:
        raise HTTPException(409, 'Destination is inactive or blocked')
    if movement_type == 'RETRIEVE' and not shipment_id:
        source_location = db.get(models.Location, hu.current_location_id) if hu.current_location_id else None
        inv_check = db.scalar(select(models.Inventory).where(models.Inventory.handling_unit_id == hu.id).with_for_update())
        if hu.current_status != 'STORED' or not source_location or source_location.location_type != 'STORAGE' or not inv_check or inv_check.reserved_quantity:
            raise HTTPException(409, 'Retrieval requires unreserved stored goods; use the shipment workflow for reserved goods')
        if not dest.station or dest.station.station_type != models.StationType.CHECKOUT or dest.warehouse_id != source_location.warehouse_id:
            raise HTTPException(409, 'Retrieval destination must be checkout in the same warehouse')
    if movement_type == 'TRANSFER':
        source_location = db.get(models.Location, hu.current_location_id) if hu.current_location_id else None
        inv_check = db.scalar(select(models.Inventory).where(models.Inventory.handling_unit_id == hu.id).with_for_update())
        if hu.current_status != 'STORED' or not source_location or source_location.location_type != 'STORAGE' or not inv_check or inv_check.reserved_quantity:
            raise HTTPException(409, 'Only unreserved stored goods can be transferred')
        if dest.location_type != 'STORAGE' or dest.warehouse_id != source_location.warehouse_id:
            raise HTTPException(409, 'Transfer requires storage in the same warehouse')
        zone_check = db.get(models.Zone, dest.zone_id)
        product_check = db.get(models.Product, inv_check.product_id)
        rack_check = db.get(models.Rack, dest.rack_id)
        if not zone_check or not zone_check.is_active or not rack_check or not rack_check.is_active or (product_check.default_storage_profile_id and zone_check.storage_profile_id != product_check.default_storage_profile_id):
            raise HTTPException(409, 'Destination storage profile is incompatible or inactive')
    if movement_type == 'PUTAWAY' and hu.current_status != 'RECEIVED':
        raise HTTPException(409, 'Putaway requires a received HU at inbound')
    if dest.status in {models.LocationStatus.OCCUPIED, models.LocationStatus.BLOCKED, models.LocationStatus.RESERVED} and dest.location_type == "STORAGE":
        raise HTTPException(409, "Destination is not available")
    if movement_type in {"PUTAWAY", "RETURN_PUTAWAY"}:
        if dest.location_type != "STORAGE" or not dest.is_active:
            raise HTTPException(409, "Putaway destination must be an active storage location")
        inv_for_profile = db.scalar(select(models.Inventory).where(models.Inventory.handling_unit_id == hu.id))
        product_for_profile = db.get(models.Product, inv_for_profile.product_id) if inv_for_profile else None
        zone = db.get(models.Zone, dest.zone_id) if dest.zone_id else None
        rack = db.get(models.Rack, dest.rack_id) if dest.rack_id else None
        if not zone or not zone.is_active or not rack or not rack.is_active:
            raise HTTPException(409, "Putaway destination is inactive")
        if movement_type == "PUTAWAY" and product_for_profile and product_for_profile.default_storage_profile_id and zone.storage_profile_id != product_for_profile.default_storage_profile_id:
            raise HTTPException(409, "Selected location does not match the product storage profile")
        if movement_type == "RETURN_PUTAWAY":
            source_location = db.get(models.Location, hu.current_location_id) if hu.current_location_id else None
            if hu.current_status != "RETURN_HOLD" or not source_location or not source_location.station or source_location.station.station_type != models.StationType.RETURN:
                raise HTTPException(409, "Returned HU must be at a RETURN station")
            if zone.zone_code != "RTN" and product_for_profile and product_for_profile.default_storage_profile_id and zone.storage_profile_id != product_for_profile.default_storage_profile_id:
                raise HTTPException(409, "Normal storage location does not match the product storage profile")
    if dest.location_type=="STATION" and dest.station:
        station_load=db.scalar(select(func.count()).select_from(models.HandlingUnit).where(models.HandlingUnit.current_location_id==dest.id,models.HandlingUnit.id!=hu.id)) or 0
        if station_load>=dest.station.capacity_hu: raise HTTPException(409,"Station capacity exceeded")
    inv = db.scalar(select(models.Inventory).where(models.Inventory.handling_unit_id == hu.id).with_for_update())
    source = hu.current_location_id
    old = db.get(models.Location, source) if source else None
    try:
        if old and old.location_type == "STORAGE": old.status = models.LocationStatus.AVAILABLE
        if dest.location_type == "STORAGE": dest.status = models.LocationStatus.OCCUPIED
        hu.current_location_id = dest.id; hu.current_vehicle_id = None; hu.current_node_type = "WAREHOUSE_LOCATION"
        return_zone = db.get(models.Zone, dest.zone_id) if movement_type == "RETURN_PUTAWAY" and dest.zone_id else None
        hu.current_status = "RETURN_STORED" if return_zone and return_zone.zone_code == "RTN" else {"RETURN":"RETURN_HOLD", "RETRIEVE":"AT_CHECKOUT", "CHECKOUT":"AT_LOADOUT"}.get(movement_type,"STORED")
        inv.location_id = dest.id
        if movement_type == "RETURN_PUTAWAY": inv.reserved_quantity = inv.quantity if return_zone and return_zone.zone_code == "RTN" else 0
        record_movement(db, movement_type, hu, inv, source_location_id=source, destination_location_id=dest.id, shipment_id=shipment_id)
        task = db.scalar(select(models.WarehouseTask).where(models.WarehouseTask.handling_unit_id == hu.id, models.WarehouseTask.task_type == movement_type, models.WarehouseTask.status != "COMPLETED"))
        if task: task.status="COMPLETED"; task.destination_location_id=dest.id; task.completed_at=datetime.now(timezone.utc)
        audit(db,movement_type,"HANDLING_UNIT",hu.id,{"hu_code":hu.hu_code,"source_location_id":source,"destination_location_id":dest.id})
        db.commit(); return hu
    except Exception:
        db.rollback(); raise

def putaway_return(db: Session, hu_code: str, destination_location_id: int):
    valid_ids = {location.id for location in return_putaway_options(db, hu_code)}
    if destination_location_id not in valid_ids: raise HTTPException(409, "Selected location is not valid for this returned HU")
    hu = db.scalar(select(models.HandlingUnit).where(models.HandlingUnit.hu_code == hu_code))
    line = db.scalar(select(models.ShipmentItem).where(models.ShipmentItem.handling_unit_id == hu.id).order_by(models.ShipmentItem.id.desc())) if hu else None
    return move_hu(db, hu_code, destination_location_id, "RETURN_PUTAWAY", line.shipment_id if line else None)

def inventory_search(db: Session, query: str | None = None):
    stmt = select(models.Inventory, models.Product, models.HandlingUnit, models.Location).join(models.Product).join(models.HandlingUnit).outerjoin(models.Location, models.Inventory.location_id == models.Location.id)
    if query:
        like=f"%{query}%"; stmt=stmt.where(or_(models.Product.sku.ilike(like), models.Product.product_name.ilike(like), models.Product.barcode.ilike(like), models.HandlingUnit.hu_code.ilike(like), models.Inventory.lot_no.ilike(like), models.Inventory.batch_no.ilike(like), models.Location.location_code.ilike(like)))
    rows=[]
    for inv, product, hu, loc in db.execute(stmt.order_by(models.Product.sku)).all():
        rows.append({"id":inv.id,"sku":product.sku,"product_name":product.product_name,"hu_code":hu.hu_code,"location_code":loc.location_code if loc else None,"current_node_type":hu.current_node_type,"hu_status":hu.current_status,"location_type":loc.location_type if loc else None,"quantity":float(inv.quantity),"reserved_quantity":float(inv.reserved_quantity),"available_quantity":float(inv.quantity-inv.reserved_quantity),"unit_of_measure":inv.unit_of_measure,"lot_no":inv.lot_no,"batch_no":inv.batch_no})
    return rows

def split_hu(db:Session,payload:schemas.SplitHURequest):
    source=db.scalar(select(models.HandlingUnit).where(models.HandlingUnit.hu_code==payload.source_hu_code).with_for_update());dest=db.scalar(select(models.Location).where(models.Location.id==payload.destination_location_id).with_for_update())
    if not source or not dest:raise HTTPException(404,"Source HU or destination not found")
    if dest.location_type!="STORAGE" or dest.status!=models.LocationStatus.AVAILABLE:raise HTTPException(409,"Split destination must be an available storage location")
    if db.scalar(select(models.HandlingUnit).where(models.HandlingUnit.hu_code==payload.new_hu_code)):raise HTTPException(409,"New HU code already exists")
    inv=db.scalar(select(models.Inventory).where(models.Inventory.handling_unit_id==source.id).with_for_update());item=db.scalar(select(models.HandlingUnitItem).where(models.HandlingUnitItem.handling_unit_id==source.id).with_for_update())
    if not inv or payload.quantity>=float(inv.quantity) or float(inv.quantity-inv.reserved_quantity)<payload.quantity:raise HTTPException(409,"Split quantity must be below available source quantity")
    try:
        ratio=payload.quantity/float(inv.quantity);new=models.HandlingUnit(hu_code=payload.new_hu_code,hu_type=source.hu_type,current_location_id=dest.id,current_node_type="WAREHOUSE_LOCATION",current_status="STORED",gross_weight_kg=float(source.gross_weight_kg or 0)*ratio);db.add(new);db.flush()
        db.add(models.HandlingUnitItem(handling_unit_id=new.id,product_id=item.product_id,lot_no=item.lot_no,batch_no=item.batch_no,expiry_date=item.expiry_date,quantity=payload.quantity,unit_of_measure=item.unit_of_measure));new_inv=models.Inventory(product_id=inv.product_id,handling_unit_id=new.id,location_id=dest.id,lot_no=inv.lot_no,batch_no=inv.batch_no,quantity=payload.quantity,reserved_quantity=0,unit_of_measure=inv.unit_of_measure);db.add(new_inv);split_qty=Decimal(str(payload.quantity));inv.quantity-=split_qty;item.quantity-=split_qty;source.gross_weight_kg=float(source.gross_weight_kg or 0)*(1-ratio);dest.status=models.LocationStatus.OCCUPIED;db.flush();record_movement(db,"ADJUST",new,new_inv,destination_location_id=dest.id);audit(db,"SPLIT_HU","HANDLING_UNIT",source.id,{"new_hu":new.hu_code,"quantity":payload.quantity});db.commit();return new
    except Exception:db.rollback();raise
