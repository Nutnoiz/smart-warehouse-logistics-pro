"""Physical station workflow independent of commercial shipping commitments."""
from decimal import Decimal
from fastapi import HTTPException
from sqlalchemy import select, func
from app import models
from app.services.inventory import audit, record_movement, putaway_options, return_putaway_options, suggested_hu_code
from app.services.logistics import event, next_shipment_no

TERMINAL={'CANCELLED','DELIVERED','RETURNED'}

def context(db,code):
    hu=db.scalar(select(models.HandlingUnit).where(models.HandlingUnit.hu_code==code).with_for_update())
    inv=db.scalar(select(models.Inventory).where(models.Inventory.handling_unit_id==hu.id).with_for_update()) if hu else None
    src=db.get(models.Location,hu.current_location_id) if hu and hu.current_location_id else None
    if not hu or not inv or not src or hu.current_node_type!='WAREHOUSE_LOCATION':raise HTTPException(409,'HU must currently be in the warehouse')
    shipment=db.scalar(select(models.Shipment).join(models.ShipmentItem).where(models.ShipmentItem.handling_unit_id==hu.id,models.Shipment.status.not_in(TERMINAL)).with_for_update())
    return hu,inv,src,shipment

def destinations(db,hu,inv,src,shipment):
    result=[]
    if inv.quantity<=0:return []
    kind=src.station.station_type.value if src.station else 'STORAGE'
    if shipment and shipment.status not in {'PICKING','READY_TO_LOAD'}:return []
    if shipment:
        link=db.scalar(select(models.DeliveryRunShipment).where(models.DeliveryRunShipment.shipment_id==shipment.id))
        run=db.get(models.DeliveryRun,link.delivery_run_id) if link else None
        if run and run.status not in {'PLANNED','TRUCK_ARRIVED','WAITING_DOCK','AT_DOCK'}:return []
    if shipment:
        kinds={'CHECKOUT':['LOADOUT'],'LOADOUT':['CHECKOUT']}.get(kind,[])
    elif hu.current_status=='RETURN_HOLD':
        kinds=[]
    elif inv.reserved_quantity:
        return []
    else:
        kinds={'STORAGE':['CHECKOUT'],'INBOUND':['CHECKOUT'],'CHECKOUT':['INBOUND','LOADOUT'],'LOADOUT':['CHECKOUT']}.get(kind,[])
    for loc in db.scalars(select(models.Location).join(models.Station).where(models.Location.warehouse_id==src.warehouse_id,models.Station.station_type.in_(kinds),models.Station.is_active.is_(True),models.Location.is_active.is_(True),models.Location.status!=models.LocationStatus.BLOCKED).order_by(models.Location.location_code)):
        count=db.scalar(select(func.count()).select_from(models.HandlingUnit).where(models.HandlingUnit.current_location_id==loc.id)) or 0
        if count<loc.station.capacity_hu:result.append({'id':loc.id,'location_code':loc.location_code,'kind':loc.station.station_type.value,'zone_code':None,'rack_id':None})
    if not shipment and (not inv.reserved_quantity or hu.current_status=='RETURN_HOLD'):
        try:
            locations=return_putaway_options(db,hu.hu_code) if hu.current_status=='RETURN_HOLD' else putaway_options(db,hu.hu_code)
            for loc in locations:
                if loc.warehouse_id==src.warehouse_id:result.append({'id':loc.id,'location_code':loc.location_code,'kind':'STORAGE','zone_code':loc.rack.zone.zone_code,'rack_id':loc.rack_id,'bay_no':loc.bay_no,'level_no':loc.level_no,'position_no':loc.position_no})
        except HTTPException as exc:
            if exc.status_code!=409:raise
    return result

def workflow_view(db,code):
    hu,inv,src,shipment=context(db,code)
    product=db.get(models.Product,inv.product_id)
    link=db.scalar(select(models.DeliveryRunShipment).where(models.DeliveryRunShipment.shipment_id==shipment.id)) if shipment else None
    return {'hu_code':hu.hu_code,'sku':product.sku,'product_name':product.product_name,'quantity':float(inv.quantity),'unit':inv.unit_of_measure,'reserved':float(inv.reserved_quantity),'status':hu.current_status,'location_code':src.location_code,'kind':src.station.station_type.value if src.station else 'STORAGE','destinations':destinations(db,hu,inv,src,shipment),'shipment_id':shipment.id if shipment else None,'shipment_no':shipment.shipment_no if shipment else None,'delivery_run_id':link.delivery_run_id if link else None,'can_ship':bool(src.station and src.station.station_type==models.StationType.CHECKOUT and not shipment and not inv.reserved_quantity and inv.quantity>0),'can_cancel':bool(shipment and shipment.status in {'PLANNED','PICKING','READY_TO_LOAD'})}

def move(db,payload):
    hu,inv,src,shipment=context(db,payload.hu_code)
    allowed={loc['id'] for loc in destinations(db,hu,inv,src,shipment)}
    dest=db.scalar(select(models.Location).where(models.Location.id==payload.destination_location_id).with_for_update())
    if not dest or dest.id not in allowed:raise HTTPException(409,'Destination is not allowed for the current HU state')
    if dest.station:
        load=db.scalar(select(func.count()).select_from(models.HandlingUnit).where(models.HandlingUnit.current_location_id==dest.id)) or 0
        if load>=dest.station.capacity_hu:raise HTTPException(409,'Station capacity exceeded')
    elif dest.status!=models.LocationStatus.AVAILABLE:raise HTTPException(409,'Storage position is no longer available')
    old_status=hu.current_status
    kind=dest.station.station_type.value if dest.station else 'STORAGE'
    if shipment and kind=='CHECKOUT':
        lines=db.scalars(select(models.ShipmentItem).where(models.ShipmentItem.shipment_id==shipment.id)).all()
        if any(line.loaded_quantity for line in lines):raise HTTPException(409,'Shipment already has loaded cargo')
        shipment.status='PICKING';event(db,shipment,'QC_RECHECK',payload.note)
    if src.location_type=='STORAGE':src.status=models.LocationStatus.AVAILABLE
    if kind=='STORAGE':dest.status=models.LocationStatus.OCCUPIED
    hu.current_location_id=dest.id;inv.location_id=dest.id
    hu.current_status={'STORAGE':'STORED','INBOUND':'RECEIVED','CHECKOUT':'AT_CHECKOUT','LOADOUT':'AT_LOADOUT'}[kind]
    if old_status=='RETURN_HOLD':
        if dest.rack.zone.zone_code=='RTN':hu.current_status='RETURN_STORED';inv.reserved_quantity=inv.quantity
        else:inv.reserved_quantity=0
    movement='RESTOCK' if kind=='STORAGE' else 'STATION_MOVE'
    record_movement(db,movement,hu,inv,source_location_id=src.id,destination_location_id=dest.id,shipment_id=shipment.id if shipment else None)
    audit(db,movement,'HANDLING_UNIT',hu.id,{'source':src.location_code,'destination':dest.location_code,'note':payload.note})
    if kind=='STORAGE':
        for task in db.scalars(select(models.WarehouseTask).where(models.WarehouseTask.handling_unit_id==hu.id,models.WarehouseTask.task_type=='PUTAWAY',models.WarehouseTask.status.in_(['PENDING','IN_PROGRESS']))):task.status='COMPLETED';task.destination_location_id=dest.id
    db.commit();return {'hu_code':hu.hu_code,'status':hu.current_status,'location_code':dest.location_code}

def ship_from_checkout(db,payload):
    hu,inv,src,existing=context(db,payload.hu_code)
    if existing or inv.reserved_quantity or not src.station or src.station.station_type!=models.StationType.CHECKOUT:raise HTTPException(409,'Requires unreserved cargo at checkout')
    qty=Decimal(str(payload.quantity))
    if qty>inv.quantity:raise HTTPException(409,'Quantity exceeds available inventory')
    customer=db.get(models.Customer,payload.customer_id)
    if not customer:raise HTTPException(422,'Valid customer required')
    if bool(payload.vehicle_id)!=bool(payload.driver_id):raise HTTPException(422,'Select vehicle and driver together, or leave both unassigned')
    if payload.vehicle_id and not db.get(models.Vehicle,payload.vehicle_id):raise HTTPException(422,'Vehicle not found')
    if payload.driver_id and not db.get(models.Driver,payload.driver_id):raise HTTPException(422,'Driver not found')
    if payload.loading_dock_id:
        dock=db.get(models.LoadingDock,payload.loading_dock_id)
        if not dock or dock.warehouse_id!=src.warehouse_id:raise HTTPException(422,'Loading dock must belong to the origin warehouse')
    if qty<inv.quantity:
        item=db.scalar(select(models.HandlingUnitItem).where(models.HandlingUnitItem.handling_unit_id==hu.id).with_for_update())
        ratio=float(qty/inv.quantity)
        load=db.scalar(select(func.count()).select_from(models.HandlingUnit).where(models.HandlingUnit.current_location_id==src.id)) or 0
        if load>=src.station.capacity_hu:raise HTTPException(409,'Checkout needs one free HU position to split cargo')
        new=models.HandlingUnit(hu_code=suggested_hu_code(db),hu_type=hu.hu_type,current_location_id=src.id,current_node_type='WAREHOUSE_LOCATION',current_status='AT_CHECKOUT',gross_weight_kg=float(hu.gross_weight_kg or 0)*ratio)
        db.add(new);db.flush()
        db.add(models.HandlingUnitItem(handling_unit_id=new.id,product_id=item.product_id,quantity=qty,unit_of_measure=item.unit_of_measure,lot_no=item.lot_no,batch_no=item.batch_no,expiry_date=item.expiry_date))
        new_inv=models.Inventory(handling_unit_id=new.id,product_id=inv.product_id,location_id=src.id,quantity=qty,reserved_quantity=0,unit_of_measure=inv.unit_of_measure,lot_no=inv.lot_no,batch_no=inv.batch_no)
        inv.quantity-=qty;item.quantity-=qty;hu.gross_weight_kg=float(hu.gross_weight_kg or 0)*(1-ratio);db.add(new_inv);db.flush()
        record_movement(db,'SPLIT_PICK',new,new_inv,source_location_id=src.id,destination_location_id=src.id)
        audit(db,'SPLIT_HU','HANDLING_UNIT',hu.id,{'new_hu':new.hu_code,'quantity':float(qty)})
        hu,inv=new,new_inv
    shipment=models.Shipment(shipment_no=next_shipment_no(db),customer_id=customer.id,origin_warehouse_id=src.warehouse_id,destination_name=customer.customer_name,destination_contact_name=customer.contact_name,destination_phone=customer.phone,destination_address_line1=customer.address_line1,destination_district=customer.district,destination_province=customer.province,destination_postal_code=customer.postal_code,destination_country=customer.country,status='PICKING',vehicle_id=payload.vehicle_id,driver_id=payload.driver_id,loading_dock_id=payload.loading_dock_id)
    db.add(shipment);db.flush();inv.reserved_quantity=qty
    db.add(models.ShipmentItem(shipment_id=shipment.id,product_id=inv.product_id,handling_unit_id=hu.id,planned_quantity=qty,unit_of_measure=inv.unit_of_measure))
    event(db,shipment,'PICKING','Created from checked cargo; remaining cargo stays available at checkout')
    audit(db,'CREATE_FROM_CHECKOUT','SHIPMENT',shipment.id,{'hu_code':hu.hu_code,'quantity':float(qty)})
    from app.services.delivery_runs import assign_shipment_to_run
    assign_shipment_to_run(db,shipment);db.commit();return shipment

def cancel(db,sid):
    shipment=db.scalar(select(models.Shipment).where(models.Shipment.id==sid).with_for_update())
    if not shipment or shipment.status not in {'PLANNED','PICKING','READY_TO_LOAD'}:raise HTTPException(409,'Only shipments before loading can be cancelled')
    link=db.scalar(select(models.DeliveryRunShipment).where(models.DeliveryRunShipment.shipment_id==sid))
    run=db.get(models.DeliveryRun,link.delivery_run_id) if link else None
    if run and run.status not in {'PLANNED','TRUCK_ARRIVED','WAITING_DOCK','AT_DOCK'}:raise HTTPException(409,'Vehicle run has already started loading')
    lines=db.scalars(select(models.ShipmentItem).where(models.ShipmentItem.shipment_id==sid).with_for_update()).all()
    for line in lines:
        if line.loaded_quantity:raise HTTPException(409,'Shipment contains loaded cargo')
        if line.handling_unit_id:
            hu=db.get(models.HandlingUnit,line.handling_unit_id)
            inv=db.scalar(select(models.Inventory).where(models.Inventory.handling_unit_id==hu.id).with_for_update())
            if hu.current_node_type!='WAREHOUSE_LOCATION':raise HTTPException(409,'Cargo is no longer in the warehouse')
            if inv:inv.reserved_quantity=0
            loc=db.get(models.Location,hu.current_location_id)
            if loc and loc.location_type=='STORAGE':loc.status=models.LocationStatus.OCCUPIED
    shipment.status='CANCELLED';event(db,shipment,'CANCELLED','Cancelled before loading; inventory reservations released')
    for task in db.scalars(select(models.WarehouseTask).where(models.WarehouseTask.shipment_id==sid,models.WarehouseTask.status.not_in(['COMPLETED','CANCELLED']))):task.status='CANCELLED'
    audit(db,'CANCELLED','SHIPMENT',sid,{'shipment_no':shipment.shipment_no})
    from app.services.delivery_runs import sync_run_completion
    from app.services.delivery_runs import _refresh_dock_status
    sync_run_completion(db,sid)
    if run:_refresh_dock_status(db,run.loading_dock_id)
    db.commit();return shipment

def assign_transport(db,sid,payload):
    from app.services.delivery_runs import ACTIVE, assign_shipment_to_run, run_event
    shipment=db.scalar(select(models.Shipment).where(models.Shipment.id==sid).with_for_update())
    if not shipment or shipment.status not in {'PLANNED','PICKING','READY_TO_LOAD'}:raise HTTPException(409,'กำหนดรถได้เฉพาะก่อนเริ่มโหลด')
    vehicle=db.scalar(select(models.Vehicle).where(models.Vehicle.id==payload.vehicle_id).with_for_update())
    driver=db.scalar(select(models.Driver).where(models.Driver.id==payload.driver_id).with_for_update())
    dock=db.scalar(select(models.LoadingDock).where(models.LoadingDock.id==payload.loading_dock_id).with_for_update())
    if not vehicle or not driver or not dock or not vehicle.is_active or not driver.is_active or not dock.is_active:raise HTTPException(422,'รถ คนขับ และช่องโหลดต้องพร้อมใช้งาน')
    if dock.warehouse_id!=shipment.origin_warehouse_id:raise HTTPException(409,'ช่องโหลดต้องอยู่คลังเดียวกับสินค้า')
    link=db.scalar(select(models.DeliveryRunShipment).where(models.DeliveryRunShipment.shipment_id==sid).with_for_update())
    run=db.get(models.DeliveryRun,link.delivery_run_id) if link else None
    vehicle_run=db.scalar(select(models.DeliveryRun).where(models.DeliveryRun.vehicle_id==vehicle.id,models.DeliveryRun.status.in_(ACTIVE)).with_for_update())
    driver_run=db.scalar(select(models.DeliveryRun).where(models.DeliveryRun.driver_id==driver.id,models.DeliveryRun.status.in_(ACTIVE)).with_for_update())
    if driver_run and (not vehicle_run or driver_run.id!=vehicle_run.id):raise HTTPException(409,'คนขับอยู่ระหว่างปฏิบัติงานกับรถอีกคัน')
    if vehicle_run and vehicle_run.origin_warehouse_id!=shipment.origin_warehouse_id:raise HTTPException(409,'รถอยู่ในรอบของคลังอื่น')
    if not vehicle_run and (vehicle.status!='AVAILABLE' or driver.status!='AVAILABLE'):raise HTTPException(409,'รถหรือคนขับไม่พร้อมใช้งาน')
    if run:
        if run.status not in {'PLANNED','TRUCK_ARRIVED','WAITING_DOCK'}:raise HTTPException(409,'รถเข้าช่องโหลดแล้ว ไม่สามารถเปลี่ยนข้อมูลขนส่ง')
        if run.vehicle_id!=vehicle.id or run.driver_id!=driver.id:raise HTTPException(409,'รายการผูกกับรอบรถแล้ว ต้องใช้รถและคนขับเดิม')
        run.loading_dock_id=dock.id
        for member in db.scalars(select(models.Shipment).join(models.DeliveryRunShipment).where(models.DeliveryRunShipment.delivery_run_id==run.id)):member.loading_dock_id=dock.id
        run_event(db,run,'TRANSPORT_ASSIGNED','Loading dock assigned')
    else:
        shipment.vehicle_id=vehicle.id;shipment.driver_id=driver.id;shipment.loading_dock_id=dock.id
        run=assign_shipment_to_run(db,shipment)
    event(db,shipment,'TRANSPORT_ASSIGNED',f'Vehicle {vehicle.vehicle_code}, driver {driver.driver_code}, dock {dock.dock_code}')
    audit(db,'TRANSPORT_ASSIGNED','SHIPMENT',sid,{'vehicle_id':vehicle.id,'driver_id':driver.id,'loading_dock_id':dock.id,'run_id':run.id})
    db.commit();return shipment
