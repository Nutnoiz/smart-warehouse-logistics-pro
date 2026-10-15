from datetime import datetime, timezone
from decimal import Decimal
from uuid import uuid4
from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from app import models, schemas
from app.services.inventory import audit, move_hu, record_movement

TRANSITIONS = {
    "PLANNED":{"PICKING","CANCELLED"}, "PICKING":{"READY_TO_LOAD","CANCELLED"},
    "READY_TO_LOAD":{"LOADING","CANCELLED"}, "LOADING":{"LOADED"}, "LOADED":{"DEPARTED"},
    "DEPARTED":{"IN_TRANSIT","ARRIVED"}, "IN_TRANSIT":{"ARRIVED"},
    "ARRIVED":{"DELIVERED","DELIVERY_FAILED"}, "DELIVERY_FAILED":{"RETURNING"}, "RETURNING":{"RETURNED"}
}

def event(db: Session, shipment: models.Shipment, event_type: str, note=None, latitude=None, longitude=None):
    db.add(models.ShipmentTrackingEvent(shipment_id=shipment.id, event_type=event_type, note=note, latitude=latitude, longitude=longitude))

def transition(db: Session, shipment: models.Shipment, status: str, note=None, latitude=None, longitude=None):
    if status not in TRANSITIONS.get(shipment.status, set()):
        raise HTTPException(409, f"Illegal shipment transition: {shipment.status} -> {status}")
    shipment.status=status; event(db,shipment,status,note,latitude,longitude)

def next_shipment_no(db: Session):
    return f"SHP-{datetime.now(timezone.utc):%Y%m%d}-{uuid4().hex[:10].upper()}"

def create_shipment(db: Session, payload: schemas.ShipmentCreate):
    customer=db.get(models.Customer,payload.customer_id)
    if not customer or not payload.items: raise HTTPException(422,"Customer and at least one item are required")
    shipment=models.Shipment(shipment_no=next_shipment_no(db),customer_id=customer.id,origin_warehouse_id=payload.origin_warehouse_id,destination_name=customer.customer_name,destination_contact_name=customer.contact_name,destination_phone=customer.phone,destination_address_line1=customer.address_line1,destination_district=customer.district,destination_province=customer.province,destination_postal_code=customer.postal_code,destination_country=customer.country,vehicle_id=payload.vehicle_id,driver_id=payload.driver_id,loading_dock_id=payload.loading_dock_id,planned_departure_at=payload.planned_departure_at)
    db.add(shipment); db.flush()
    for line in payload.items: db.add(models.ShipmentItem(shipment_id=shipment.id,**line.model_dump()))
    event(db,shipment,"PLANNED"); audit(db,"CREATE","SHIPMENT",shipment.id,{"shipment_no":shipment.shipment_no})
    from app.services.delivery_runs import assign_shipment_to_run
    assign_shipment_to_run(db,shipment);db.commit();return shipment

def pick_from_location(db:Session,payload:schemas.PickFromLocationRequest):
    hu=db.scalar(select(models.HandlingUnit).where(models.HandlingUnit.hu_code==payload.source_hu_code).with_for_update())
    inventory=db.scalar(select(models.Inventory).where(models.Inventory.handling_unit_id==hu.id).with_for_update()) if hu else None
    hu_item=db.scalar(select(models.HandlingUnitItem).where(models.HandlingUnitItem.handling_unit_id==hu.id).with_for_update()) if hu else None
    source=db.scalar(select(models.Location).where(models.Location.id==hu.current_location_id).with_for_update()) if hu and hu.current_location_id else None
    customer=db.get(models.Customer,payload.customer_id)
    checkout=db.get(models.Station,payload.checkout_station_id)
    checkout_location=db.scalar(select(models.Location).where(models.Location.station_id==checkout.id).with_for_update()) if checkout else None
    if not hu or not inventory or not hu_item or not source or source.location_type!="STORAGE": raise HTTPException(409,"Source HU must be stored in a rack location")
    if hu.current_status!="STORED" or float(inventory.reserved_quantity)!=0: raise HTTPException(409,"Source HU is not available for outbound picking")
    if not customer: raise HTTPException(422,"Valid customer is required")
    if not checkout or checkout.station_type!=models.StationType.CHECKOUT or not checkout_location: raise HTTPException(422,"Valid CHECKOUT station is required")
    quantity=Decimal(str(payload.quantity));original_quantity=Decimal(str(inventory.quantity))
    if quantity>original_quantity: raise HTTPException(409,"Requested quantity exceeds available HU quantity")
    station_load=db.scalar(select(func.count()).select_from(models.HandlingUnit).where(models.HandlingUnit.current_location_id==checkout_location.id)) or 0
    if station_load>=checkout.capacity_hu: raise HTTPException(409,"Checkout station capacity exceeded")
    try:
        shipment=models.Shipment(shipment_no=next_shipment_no(db),customer_id=customer.id,origin_warehouse_id=source.warehouse_id,destination_name=customer.customer_name,destination_contact_name=customer.contact_name,destination_phone=customer.phone,destination_address_line1=customer.address_line1,destination_district=customer.district,destination_province=customer.province,destination_postal_code=customer.postal_code,destination_country=customer.country,vehicle_id=payload.vehicle_id,driver_id=payload.driver_id,loading_dock_id=payload.loading_dock_id,status="PICKING")
        db.add(shipment);db.flush();event(db,shipment,"PLANNED","Created from inventory location");event(db,shipment,"PICKING","HU retrieved to checkout")
        record_movement(db,"RETRIEVE",hu,inventory,source_location_id=source.id,destination_location_id=checkout_location.id,shipment_id=shipment.id)
        source.status=models.LocationStatus.AVAILABLE
        if quantity==original_quantity:
            outbound_hu=hu;inventory.reserved_quantity=quantity;inventory.location_id=checkout_location.id;hu.current_location_id=checkout_location.id;hu.current_status="AT_CHECKOUT"
        else:
            hu.current_location_id=checkout_location.id;hu.current_status="AT_CHECKOUT";inventory.location_id=checkout_location.id
            ratio=float(quantity/original_quantity)
            outbound_hu=models.HandlingUnit(hu_code=f"HU-OUT-{shipment.id:06d}",hu_type=hu.hu_type,current_location_id=checkout_location.id,current_node_type="WAREHOUSE_LOCATION",current_status="AT_CHECKOUT",gross_weight_kg=float(hu.gross_weight_kg or 0)*ratio)
            db.add(outbound_hu);db.flush()
            db.add(models.HandlingUnitItem(handling_unit_id=outbound_hu.id,product_id=hu_item.product_id,lot_no=hu_item.lot_no,batch_no=hu_item.batch_no,expiry_date=hu_item.expiry_date,quantity=quantity,unit_of_measure=hu_item.unit_of_measure))
            outbound_inventory=models.Inventory(product_id=inventory.product_id,handling_unit_id=outbound_hu.id,location_id=checkout_location.id,lot_no=inventory.lot_no,batch_no=inventory.batch_no,quantity=quantity,reserved_quantity=quantity,unit_of_measure=inventory.unit_of_measure)
            db.add(outbound_inventory);inventory.quantity-=quantity;hu_item.quantity-=quantity;hu.gross_weight_kg=float(hu.gross_weight_kg or 0)*(1-ratio);db.flush()
            record_movement(db,"SPLIT_PICK",outbound_hu,outbound_inventory,source_location_id=checkout_location.id,destination_location_id=checkout_location.id,shipment_id=shipment.id)
            hu.current_location_id=source.id;hu.current_status="STORED";inventory.location_id=source.id;source.status=models.LocationStatus.OCCUPIED
            record_movement(db,"RESTOCK",hu,inventory,source_location_id=checkout_location.id,destination_location_id=source.id,shipment_id=shipment.id)
            inventory=outbound_inventory
        db.add(models.ShipmentItem(shipment_id=shipment.id,product_id=inventory.product_id,handling_unit_id=outbound_hu.id,planned_quantity=quantity,unit_of_measure=inventory.unit_of_measure))
        audit(db,"PICK_FROM_LOCATION","SHIPMENT",shipment.id,{"source_hu_code":payload.source_hu_code,"outbound_hu_code":outbound_hu.hu_code,"quantity":float(quantity),"source_location":source.location_code,"checkout_station":checkout.station_code})
        from app.services.delivery_runs import assign_shipment_to_run
        assign_shipment_to_run(db,shipment)
        db.commit();return shipment
    except Exception:db.rollback();raise

def allocate(db: Session, shipment_id: int, strategy: str = "FIFO"):
    shipment=db.scalar(select(models.Shipment).where(models.Shipment.id==shipment_id).with_for_update())
    if not shipment or shipment.status!="PLANNED": raise HTTPException(409,"Shipment must be PLANNED")
    lines=db.scalars(select(models.ShipmentItem).where(models.ShipmentItem.shipment_id==shipment.id).with_for_update()).all()
    try:
        for line in lines:
            inv=None
            if line.handling_unit_id:
                inv=db.scalar(select(models.Inventory).where(models.Inventory.handling_unit_id==line.handling_unit_id).with_for_update())
            else:
                stmt=select(models.Inventory).join(models.HandlingUnit,models.HandlingUnit.id==models.Inventory.handling_unit_id).join(models.Location,models.Location.id==models.Inventory.location_id).where(models.Inventory.product_id==line.product_id,models.Inventory.quantity==line.planned_quantity,models.Inventory.reserved_quantity==0,models.HandlingUnit.current_status=='STORED',models.Location.location_type=='STORAGE',models.Location.warehouse_id==shipment.origin_warehouse_id,models.Location.is_active.is_(True))
                if strategy.upper()=="FEFO":stmt=stmt.join(models.HandlingUnitItem,models.HandlingUnitItem.handling_unit_id==models.Inventory.handling_unit_id).order_by(models.HandlingUnitItem.expiry_date.asc().nullslast(),models.Inventory.created_at)
                else:stmt=stmt.order_by(models.Inventory.created_at)
                inv=db.scalar(stmt.with_for_update(skip_locked=True).limit(1))
            if not inv: raise HTTPException(409,f"Insufficient inventory for product {line.product_id}")
            if float(inv.quantity) != float(line.planned_quantity) or float(inv.reserved_quantity) != 0:
                raise HTTPException(409,"Version 1 ships complete Handling Units; split the HU before allocation")
            hu=db.get(models.HandlingUnit,inv.handling_unit_id)
            source_location = db.get(models.Location, hu.current_location_id) if hu.current_location_id else None
            if hu.current_status != 'STORED' or not source_location or source_location.location_type != 'STORAGE' or source_location.warehouse_id != shipment.origin_warehouse_id:
                raise HTTPException(409, 'Allocation requires stored goods in the shipment origin warehouse')
            if hu.current_node_type!="WAREHOUSE_LOCATION": raise HTTPException(409,f"HU {hu.hu_code} is not in warehouse")
            line.handling_unit_id=hu.id; inv.reserved_quantity += line.planned_quantity
            if hu.current_location_id and float(inv.reserved_quantity) >= float(inv.quantity):
                db.get(models.Location,hu.current_location_id).status=models.LocationStatus.RESERVED
            db.add(models.WarehouseTask(task_no=f"TSK-RET-{shipment.id:04d}-{hu.id:06d}",task_type="RETRIEVE",shipment_id=shipment.id,handling_unit_id=hu.id,source_location_id=hu.current_location_id))
        transition(db,shipment,"PICKING"); audit(db,"ALLOCATE","SHIPMENT",shipment.id,{"shipment_no":shipment.shipment_no}); db.commit(); return shipment
    except Exception: db.rollback(); raise

def mark_ready(db: Session, shipment_id: int):
    shipment=db.scalar(select(models.Shipment).where(models.Shipment.id==shipment_id).with_for_update())
    if not shipment: raise HTTPException(404,"Shipment not found")
    lines=db.scalars(select(models.ShipmentItem).where(models.ShipmentItem.shipment_id==shipment.id)).all()
    if not lines or any(not line.handling_unit_id for line in lines): raise HTTPException(409,"Shipment is not fully allocated")
    for line in lines:
        hu=db.get(models.HandlingUnit,line.handling_unit_id); loc=db.get(models.Location,hu.current_location_id)
        if not loc or not loc.station or loc.station.station_type!=models.StationType.LOADOUT: raise HTTPException(409,"All HUs must be staged at a LOADOUT station")
    transition(db,shipment,"READY_TO_LOAD"); audit(db,"READY_TO_LOAD","SHIPMENT",shipment.id,{"shipment_no":shipment.shipment_no}); db.commit(); return shipment

def move_shipment_hu(db:Session,shipment_id:int,hu_code:str,destination_location_id:int,step:str):
    shipment=db.get(models.Shipment,shipment_id)
    if not shipment or shipment.status!="PICKING": raise HTTPException(409,"Shipment must be PICKING")
    hu=db.scalar(select(models.HandlingUnit).where(models.HandlingUnit.hu_code==hu_code))
    line=db.scalar(select(models.ShipmentItem).where(models.ShipmentItem.shipment_id==shipment_id,models.ShipmentItem.handling_unit_id==hu.id)) if hu else None
    destination=db.get(models.Location,destination_location_id)
    if not line: raise HTTPException(409,"HU does not belong to shipment")
    if not destination or not destination.station: raise HTTPException(409,"Destination must be a station")
    source=db.get(models.Location,hu.current_location_id) if hu.current_location_id else None
    if step=="RETRIEVE":
        if destination.station.station_type!=models.StationType.CHECKOUT: raise HTTPException(409,"Retrieved HU must go to a CHECKOUT station")
        if not source or source.location_type!="STORAGE": raise HTTPException(409,"HU is not in a storage location")
    elif step=="CHECKOUT":
        if not source or not source.station or source.station.station_type!=models.StationType.CHECKOUT: raise HTTPException(409,"HU must be at a CHECKOUT station")
        if destination.station.station_type!=models.StationType.LOADOUT: raise HTTPException(409,"Checked HU must go to a LOADOUT station")
    else: raise HTTPException(422,"Unsupported station movement")
    move_hu(db,hu_code,destination_location_id,step,shipment_id)
    return db.get(models.Shipment,shipment_id)

def simple_transition(db:Session, shipment_id:int, status:str, action:schemas.ShipmentAction|None=None):
    shipment=db.scalar(select(models.Shipment).where(models.Shipment.id==shipment_id).with_for_update())
    if not shipment: raise HTTPException(404,"Shipment not found")
    if status in {"LOADING","LOADED","DEPARTED","IN_TRANSIT"}:
        run_link=db.scalar(select(models.DeliveryRunShipment).where(models.DeliveryRunShipment.shipment_id==shipment.id))
        run_size=(db.scalar(select(func.count()).select_from(models.DeliveryRunShipment).where(models.DeliveryRunShipment.delivery_run_id==run_link.delivery_run_id)) or 0) if run_link else 0
        if run_size>1: raise HTTPException(409,"Use delivery run control for a multi-shipment vehicle")
    transition(db,shipment,status,action.note if action else None,action.latitude if action else None,action.longitude if action else None)
    now=datetime.now(timezone.utc)
    if status=="LOADING":
        if not all([shipment.vehicle_id,shipment.driver_id,shipment.loading_dock_id]): raise HTTPException(409,"Vehicle, driver and loading dock are required")
        db.get(models.Vehicle,shipment.vehicle_id).status="LOADING"
    if status=="DEPARTED": shipment.actual_departure_at=now; db.get(models.Vehicle,shipment.vehicle_id).status="IN_TRANSIT"
    if status=="ARRIVED": shipment.actual_arrival_at=now
    audit(db,status,"SHIPMENT",shipment.id,{"shipment_no":shipment.shipment_no,"status":status}); db.commit(); return shipment

def load_hu(db:Session,shipment_id:int,hu_code:str):
    shipment=db.scalar(select(models.Shipment).where(models.Shipment.id==shipment_id).with_for_update())
    if not shipment or shipment.status!="LOADING": raise HTTPException(409,"Shipment must be LOADING")
    hu=db.scalar(select(models.HandlingUnit).where(models.HandlingUnit.hu_code==hu_code).with_for_update())
    line=db.scalar(select(models.ShipmentItem).where(models.ShipmentItem.shipment_id==shipment.id,models.ShipmentItem.handling_unit_id==hu.id).with_for_update()) if hu else None
    if not line: raise HTTPException(409,"HU does not belong to shipment")
    if hu.current_node_type=="VEHICLE": raise HTTPException(409,"HU is already loaded")
    source_location=db.get(models.Location,hu.current_location_id) if hu.current_location_id else None
    if not source_location or not source_location.station or source_location.station.station_type!=models.StationType.LOADOUT: raise HTTPException(409,"HU must be at a LOADOUT station before loading")
    inv=db.scalar(select(models.Inventory).where(models.Inventory.handling_unit_id==hu.id).with_for_update())
    vehicle=db.get(models.Vehicle,shipment.vehicle_id)
    if vehicle.max_weight_kg:
        loaded_weight=db.scalar(select(func.coalesce(func.sum(models.HandlingUnit.gross_weight_kg),0)).where(models.HandlingUnit.current_vehicle_id==vehicle.id)) or 0
        if float(loaded_weight)+float(hu.gross_weight_kg or 0)>float(vehicle.max_weight_kg): raise HTTPException(409,"Vehicle maximum weight exceeded")
    source=hu.current_location_id; hu.current_location_id=None; hu.current_vehicle_id=shipment.vehicle_id; hu.current_node_type="VEHICLE"; hu.current_status="LOADED"; inv.location_id=None; line.loaded_quantity=line.planned_quantity
    record_movement(db,"LOAD",hu,inv,source_location_id=source,destination_vehicle_id=shipment.vehicle_id,shipment_id=shipment.id)
    audit(db,"LOAD","HANDLING_UNIT",hu.id,{"shipment_id":shipment.id,"vehicle_id":shipment.vehicle_id}); db.commit(); return shipment

def deliver(db:Session,shipment_id:int,payload:schemas.DeliveryRequest):
    shipment=db.scalar(select(models.Shipment).where(models.Shipment.id==shipment_id).with_for_update())
    if not shipment: raise HTTPException(404,"Shipment not found")
    transition(db,shipment,"DELIVERED",payload.note,payload.latitude,payload.longitude); now=datetime.now(timezone.utc); shipment.delivered_at=now
    lines=db.scalars(select(models.ShipmentItem).where(models.ShipmentItem.shipment_id==shipment.id).with_for_update()).all()
    for line in lines:
        hu=db.get(models.HandlingUnit,line.handling_unit_id); inv=db.scalar(select(models.Inventory).where(models.Inventory.handling_unit_id==hu.id).with_for_update())
        line.delivered_quantity=line.loaded_quantity; inv.quantity-=line.delivered_quantity; inv.reserved_quantity=0; hu.current_vehicle_id=None; hu.current_node_type="CUSTOMER"; hu.current_status="DELIVERED"; record_movement(db,"DELIVER",hu,inv,source_vehicle_id=shipment.vehicle_id,shipment_id=shipment.id)
    db.add(models.ProofOfDelivery(shipment_id=shipment.id,receiver_name=payload.receiver_name,receiver_phone=payload.receiver_phone,delivery_pin_verified=payload.delivery_pin_verified,latitude=payload.latitude,longitude=payload.longitude,note=payload.note,delivered_at=now))
    audit(db,"DELIVER","SHIPMENT",shipment.id,{"receiver_name":payload.receiver_name})
    from app.services.delivery_runs import sync_run_completion
    sync_run_completion(db,shipment.id);db.commit();return shipment

def record_legacy_pod(db:Session,shipment_id:int,payload:schemas.DeliveryRequest):
    shipment=db.get(models.Shipment,shipment_id)
    if not shipment: raise HTTPException(404,"Shipment not found")
    if shipment.status!="DELIVERED": raise HTTPException(409,"POD backfill is only allowed for delivered shipments")
    existing=db.scalar(select(models.ProofOfDelivery).where(models.ProofOfDelivery.shipment_id==shipment.id))
    if existing: raise HTTPException(409,"POD already exists")
    delivered_at=shipment.delivered_at or datetime.now(timezone.utc)
    db.add(models.ProofOfDelivery(shipment_id=shipment.id,receiver_name=payload.receiver_name,receiver_phone=payload.receiver_phone,delivery_pin_verified=payload.delivery_pin_verified,latitude=payload.latitude,longitude=payload.longitude,note=payload.note,delivered_at=delivered_at))
    audit(db,"BACKFILL_POD","SHIPMENT",shipment.id,{"receiver_name":payload.receiver_name});db.commit();return shipment

def fail_delivery(db:Session,shipment_id:int,payload:schemas.FailureRequest):
    shipment=db.scalar(select(models.Shipment).where(models.Shipment.id==shipment_id).with_for_update())
    if not shipment: raise HTTPException(404,"Shipment not found")
    transition(db,shipment,"DELIVERY_FAILED",payload.note,payload.latitude,payload.longitude)
    count=db.scalar(select(func.count()).select_from(models.DeliveryAttempt).where(models.DeliveryAttempt.shipment_id==shipment.id)) or 0
    db.add(models.DeliveryAttempt(shipment_id=shipment.id,attempt_no=count+1,result="FAILED",failure_reason=payload.failure_reason,note=payload.note)); audit(db,"DELIVERY_FAILED","SHIPMENT",shipment.id,{"reason":payload.failure_reason}); db.commit(); return shipment

def start_return(db:Session,shipment_id:int,action:schemas.ShipmentAction):
    return simple_transition(db,shipment_id,"RETURNING",action)

def complete_return(db:Session,shipment_id:int,station_id:int):
    shipment=db.scalar(select(models.Shipment).where(models.Shipment.id==shipment_id).with_for_update())
    station=db.get(models.Station,station_id)
    if not shipment or shipment.status!="RETURNING" or not station or station.station_type!=models.StationType.RETURN: raise HTTPException(409,"RETURNING shipment and RETURN station are required")
    location=db.scalar(select(models.Location).where(models.Location.station_id==station.id).with_for_update())
    lines=db.scalars(select(models.ShipmentItem).where(models.ShipmentItem.shipment_id==shipment.id).with_for_update()).all()
    for line in lines:
        hu=db.scalar(select(models.HandlingUnit).where(models.HandlingUnit.id==line.handling_unit_id).with_for_update()); inv=db.scalar(select(models.Inventory).where(models.Inventory.handling_unit_id==hu.id).with_for_update())
        vehicle_id=hu.current_vehicle_id; hu.current_vehicle_id=None; hu.current_location_id=location.id; hu.current_node_type="WAREHOUSE_LOCATION"; hu.current_status="RETURN_HOLD"; inv.location_id=location.id
        record_movement(db,"UNLOAD",hu,inv,source_vehicle_id=vehicle_id,destination_location_id=location.id,shipment_id=shipment.id)
    transition(db,shipment,"RETURNED");audit(db,"RETURNED","SHIPMENT",shipment.id,{"station_id":station.id})
    from app.services.delivery_runs import sync_run_completion
    sync_run_completion(db,shipment.id);db.commit();return shipment

def shipment_view(db:Session,shipment:models.Shipment):
    customer=db.get(models.Customer,shipment.customer_id); vehicle=db.get(models.Vehicle,shipment.vehicle_id) if shipment.vehicle_id else None; driver=db.get(models.Driver,shipment.driver_id) if shipment.driver_id else None; dock=db.get(models.LoadingDock,shipment.loading_dock_id) if shipment.loading_dock_id else None
    lines=db.scalars(select(models.ShipmentItem).where(models.ShipmentItem.shipment_id==shipment.id)).all(); tracking=db.scalars(select(models.ShipmentTrackingEvent).where(models.ShipmentTrackingEvent.shipment_id==shipment.id).order_by(models.ShipmentTrackingEvent.event_at)).all()
    items=[]
    for line in lines:
        hu=db.get(models.HandlingUnit,line.handling_unit_id) if line.handling_unit_id else None
        location=db.get(models.Location,hu.current_location_id) if hu and hu.current_location_id else None
        items.append({"id":line.id,"product_id":line.product_id,"sku":db.get(models.Product,line.product_id).sku,"handling_unit_id":line.handling_unit_id,"hu_code":hu.hu_code if hu else None,"current_status":hu.current_status if hu else None,"current_location_code":location.location_code if location else None,"current_station_type":location.station.station_type.value if location and location.station else None,"planned_quantity":float(line.planned_quantity),"loaded_quantity":float(line.loaded_quantity),"delivered_quantity":float(line.delivered_quantity),"unit_of_measure":line.unit_of_measure})
    transactions=[]
    movements=db.scalars(select(models.StockMovement).where(models.StockMovement.shipment_id==shipment.id).order_by(models.StockMovement.completed_at,models.StockMovement.id)).all()
    for movement in movements:
        movement_item=db.scalar(select(models.StockMovementItem).where(models.StockMovementItem.movement_id==movement.id))
        if not movement_item: continue
        hu=db.get(models.HandlingUnit,movement_item.handling_unit_id); product=db.get(models.Product,movement_item.product_id)
        source_location=db.get(models.Location,movement.source_location_id) if movement.source_location_id else None
        destination_location=db.get(models.Location,movement.destination_location_id) if movement.destination_location_id else None
        source_vehicle=db.get(models.Vehicle,movement.source_vehicle_id) if movement.source_vehicle_id else None
        destination_vehicle=db.get(models.Vehicle,movement.destination_vehicle_id) if movement.destination_vehicle_id else None
        transactions.append({"transaction_no":movement.movement_no,"transaction_type":movement.movement_type,"occurred_at":movement.completed_at or movement.created_at,"hu_code":hu.hu_code if hu else None,"sku":product.sku if product else None,"quantity":float(movement_item.quantity),"unit_of_measure":movement_item.unit_of_measure,"from_node":source_location.location_code if source_location else (source_vehicle.vehicle_code if source_vehicle else "EXTERNAL"),"to_node":destination_location.location_code if destination_location else (destination_vehicle.vehicle_code if destination_vehicle else "EXTERNAL")})
    attempts=db.scalars(select(models.DeliveryAttempt).where(models.DeliveryAttempt.shipment_id==shipment.id).order_by(models.DeliveryAttempt.attempt_no)).all()
    pod=db.scalar(select(models.ProofOfDelivery).where(models.ProofOfDelivery.shipment_id==shipment.id))
    run_link=db.scalar(select(models.DeliveryRunShipment).where(models.DeliveryRunShipment.shipment_id==shipment.id));run=db.get(models.DeliveryRun,run_link.delivery_run_id) if run_link else None
    destination_address=", ".join(filter(None,[shipment.destination_address_line1,shipment.destination_district,shipment.destination_province,shipment.destination_postal_code]))
    pod_view={"receiver_name":pod.receiver_name,"receiver_phone":pod.receiver_phone,"delivery_pin_verified":pod.delivery_pin_verified,"signature_file":pod.signature_file,"photo_file":pod.photo_file,"delivered_at":pod.delivered_at,"note":pod.note} if pod else None
    return {"id":shipment.id,"shipment_no":shipment.shipment_no,"customer_name":customer.customer_name,"destination_name":shipment.destination_name,"destination_contact_name":shipment.destination_contact_name,"destination_phone":shipment.destination_phone,"destination_address":destination_address,"status":shipment.status,"vehicle_id":shipment.vehicle_id,"driver_id":shipment.driver_id,"loading_dock_id":shipment.loading_dock_id,"origin_warehouse_id":shipment.origin_warehouse_id,"vehicle_code":vehicle.vehicle_code if vehicle else None,"driver_name":f"{driver.first_name} {driver.last_name}" if driver else None,"loading_dock_code":dock.dock_code if dock else None,"delivery_run_id":run.id if run else None,"delivery_run_no":run.run_no if run else None,"actual_departure_at":shipment.actual_departure_at,"delivered_at":shipment.delivered_at,"items":items,"tracking":[{"event_type":x.event_type,"event_at":x.event_at,"note":x.note} for x in tracking],"transactions":transactions,"delivery_attempts":[{"attempt_no":x.attempt_no,"attempted_at":x.attempted_at,"result":x.result,"failure_reason":x.failure_reason,"note":x.note} for x in attempts],"pod":pod_view}
