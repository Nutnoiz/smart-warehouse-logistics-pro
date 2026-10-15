from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, Response
from pathlib import Path
from uuid import uuid4
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from app import models, schemas
from app.core.security import create_access_token, verify_password
from app.pro_models import LoginAttempt
from datetime import datetime, timedelta, timezone
from app.db.session import get_db
from app.services.warehouse import create_dock, create_rack, create_station, dashboard
from app.services.inventory import inventory_search, move_hu, putaway_options, putaway_return, receive, recommend_putaway, return_putaway_options, split_hu
from app.services.logistics import allocate, complete_return, create_shipment, deliver, fail_delivery, load_hu, mark_ready, move_shipment_hu, pick_from_location, record_legacy_pod, shipment_view, simple_transition, start_return
from app.services.delivery_runs import check_in as check_in_run, complete_loading as complete_run_loading, depart as depart_run, enter_dock as enter_run_dock, get_run, list_runs, mark_in_transit as run_in_transit, run_view, start_loading as start_run_loading

router = APIRouter(prefix="/api")

def station_overview_rows(db:Session,warehouse_id:int):
    result=[]
    stations=db.scalars(select(models.Station).where(models.Station.warehouse_id==warehouse_id)).all()
    order={"INBOUND":0,"CHECKOUT":1,"LOADOUT":2,"OUTBOUND":3,"RETURN":4}
    stations.sort(key=lambda station:(order.get(station.station_type.value,99),station.sequence))
    for station in stations:
        location=db.scalar(select(models.Location).where(models.Location.station_id==station.id))
        items=[]
        if location:
            rows=db.execute(select(models.HandlingUnit,models.Inventory,models.Product).join(models.Inventory,models.Inventory.handling_unit_id==models.HandlingUnit.id).join(models.Product,models.Product.id==models.Inventory.product_id).where(models.HandlingUnit.current_location_id==location.id).order_by(models.HandlingUnit.created_at)).all()
            for hu,inventory,product in rows:
                shipment_no=db.scalar(select(models.Shipment.shipment_no).join(models.ShipmentItem,models.ShipmentItem.shipment_id==models.Shipment.id).where(models.ShipmentItem.handling_unit_id==hu.id,models.Shipment.status.not_in(["DELIVERED","RETURNED","CANCELLED"])).order_by(models.Shipment.id.desc()).limit(1))
                items.append({"hu_code":hu.hu_code,"sku":product.sku,"product_name":product.product_name,"quantity":float(inventory.quantity),"unit_of_measure":inventory.unit_of_measure,"hu_status":hu.current_status,"shipment_no":shipment_no})
        result.append({"id":station.id,"station_code":station.station_code,"station_name":station.station_name,"station_type":station.station_type.value,"status":station.status.value,"capacity_hu":station.capacity_hu,"hu_count":len(items),"items":items})
    return result

@router.get("/health")
def health():
    return {"status": "ok"}

@router.post("/auth/login", response_model=schemas.TokenResponse)
def login(payload: schemas.LoginRequest, response: Response, db: Session = Depends(get_db)):
    cutoff = datetime.now(timezone.utc) - timedelta(minutes=15)
    attempts = db.scalar(select(func.count()).select_from(LoginAttempt).where(LoginAttempt.username == payload.username, LoginAttempt.occurred_at >= cutoff)) or 0
    if attempts >= 8:
        raise HTTPException(429, "Too many failed attempts. Try again in 15 minutes")
    user = db.scalar(select(models.User).where(models.User.username == payload.username))
    if not user or not user.is_active or not verify_password(payload.password, user.password_hash):
        db.add(LoginAttempt(username=payload.username[:60])); db.commit()
        raise HTTPException(401, "Invalid username or password")
    from sqlalchemy import delete
    db.execute(delete(LoginAttempt).where(LoginAttempt.username == user.username))
    from app.services.inventory import audit
    db.info['user_id'] = user.id
    audit(db, 'LOGIN', 'USER', user.id, {'username': user.username}); db.commit()
    from app.core.config import settings
    token = create_access_token(user.username, user.token_version)
    response.set_cookie('warehouse_evidence', token, httponly=True, secure=settings.environment == 'production', samesite='strict', path='/files', max_age=settings.token_minutes * 60)
    return schemas.TokenResponse(access_token=token)

@router.get("/dashboard", response_model=schemas.DashboardOut)
def get_dashboard(db: Session = Depends(get_db)):
    return dashboard(db)

@router.get("/delivery-runs",response_model=list[schemas.DeliveryRunOut])
def delivery_runs(active_only:bool=False,db:Session=Depends(get_db)):
    return [run_view(db,run) for run in list_runs(db,active_only)]

@router.get("/delivery-runs/{run_id}",response_model=schemas.DeliveryRunOut)
def delivery_run(run_id:int,db:Session=Depends(get_db)):
    return run_view(db,get_run(db,run_id))

@router.post('/delivery-runs',response_model=schemas.DeliveryRunOut,status_code=201)
def register_truck(payload:schemas.DeliveryRunCreate,db:Session=Depends(get_db)):
    from app.services.truck_loading import register
    return run_view(db,register(db,payload))

@router.get('/truck-loading/choices',response_model=list[schemas.DeliveryRunOut])
def ready_trucks(warehouse_id:int,db:Session=Depends(get_db)):
    from app.services.truck_loading import choices
    return [run_view(db,r) for r in choices(db,warehouse_id)]

@router.get('/delivery-runs/{run_id}/loading-queue',response_model=list[schemas.ShipmentOut])
def loading_queue(run_id:int,db:Session=Depends(get_db)):
    from app.services.truck_loading import queue
    return [shipment_view(db,s) for s in queue(db,run_id)]

@router.post('/delivery-runs/{run_id}/shipments',response_model=schemas.DeliveryRunOut)
def attach_loading_shipment(run_id:int,payload:schemas.RunShipmentRequest,db:Session=Depends(get_db)):
    from app.services.truck_loading import attach
    return run_view(db,attach(db,run_id,payload.shipment_id))

@router.post('/delivery-runs/{run_id}/shipments/{shipment_id}/remove',response_model=schemas.DeliveryRunOut)
def remove_loading_shipment(run_id:int,shipment_id:int,db:Session=Depends(get_db)):
    from app.services.truck_loading import detach
    return run_view(db,detach(db,run_id,shipment_id))

@router.post('/delivery-runs/{run_id}/cancel-empty',response_model=schemas.DeliveryRunOut)
def cancel_empty_truck(run_id:int,db:Session=Depends(get_db)):
    from app.services.truck_loading import cancel_empty
    return run_view(db,cancel_empty(db,run_id))

@router.post('/delivery-runs/{run_id}/scan',response_model=schemas.DeliveryRunOut)
def scan_truck_hu(run_id:int,payload:schemas.RecommendRequest,db:Session=Depends(get_db)):
    from app.services.truck_loading import scan
    return run_view(db,scan(db,run_id,payload.hu_code))

@router.post("/delivery-runs/{run_id}/check-in",response_model=schemas.DeliveryRunOut)
def delivery_run_check_in(run_id:int,payload:schemas.DeliveryRunAction=schemas.DeliveryRunAction(),db:Session=Depends(get_db)):
    return run_view(db,check_in_run(db,run_id,payload))

@router.post("/delivery-runs/{run_id}/enter-dock",response_model=schemas.DeliveryRunOut)
def delivery_run_enter_dock(run_id:int,payload:schemas.DeliveryRunDockRequest=schemas.DeliveryRunDockRequest(),db:Session=Depends(get_db)):
    return run_view(db,enter_run_dock(db,run_id,payload))

@router.post("/delivery-runs/{run_id}/start-loading",response_model=schemas.DeliveryRunOut)
def delivery_run_start_loading(run_id:int,payload:schemas.DeliveryRunAction=schemas.DeliveryRunAction(),db:Session=Depends(get_db)):
    return run_view(db,start_run_loading(db,run_id,payload))

@router.post("/delivery-runs/{run_id}/complete-loading",response_model=schemas.DeliveryRunOut)
def delivery_run_complete_loading(run_id:int,payload:schemas.DeliveryRunAction=schemas.DeliveryRunAction(),db:Session=Depends(get_db)):
    return run_view(db,complete_run_loading(db,run_id,payload))

@router.post("/delivery-runs/{run_id}/depart",response_model=schemas.DeliveryRunOut)
def delivery_run_depart(run_id:int,payload:schemas.DeliveryRunAction=schemas.DeliveryRunAction(),db:Session=Depends(get_db)):
    return run_view(db,depart_run(db,run_id,payload))

@router.post("/delivery-runs/{run_id}/in-transit",response_model=schemas.DeliveryRunOut)
def delivery_run_in_transit(run_id:int,payload:schemas.DeliveryRunAction=schemas.DeliveryRunAction(),db:Session=Depends(get_db)):
    return run_view(db,run_in_transit(db,run_id,payload))

@router.get("/warehouses", response_model=list[schemas.WarehouseOut])
def warehouses(db: Session = Depends(get_db)):
    return db.scalars(select(models.Warehouse).order_by(models.Warehouse.warehouse_code)).all()

@router.post("/warehouses", response_model=schemas.WarehouseOut, status_code=201)
def add_warehouse(payload: schemas.WarehouseCreate, db: Session = Depends(get_db)):
    item = models.Warehouse(**payload.model_dump())
    db.add(item); db.commit(); return item

@router.get("/storage-profiles", response_model=list[schemas.StorageProfileOut])
def profiles(db: Session = Depends(get_db)):
    return db.scalars(select(models.StorageProfile).order_by(models.StorageProfile.profile_code)).all()

@router.post("/storage-profiles", response_model=schemas.StorageProfileOut, status_code=201)
def add_profile(payload: schemas.StorageProfileCreate, db: Session = Depends(get_db)):
    item = models.StorageProfile(**payload.model_dump())
    db.add(item); db.commit(); return item

@router.get("/zones", response_model=list[schemas.ZoneOut])
def zones(warehouse_id: int | None = None, db: Session = Depends(get_db)):
    stmt = select(models.Zone).order_by(models.Zone.zone_code)
    if warehouse_id: stmt = stmt.where(models.Zone.warehouse_id == warehouse_id)
    return db.scalars(stmt).all()

@router.post("/zones", response_model=schemas.ZoneOut, status_code=201)
def add_zone(payload: schemas.ZoneCreate, db: Session = Depends(get_db)):
    item = models.Zone(**payload.model_dump())
    db.add(item); db.commit(); return item

@router.get("/racks", response_model=list[schemas.RackOut])
def racks(zone_id: int | None = None, db: Session = Depends(get_db)):
    stmt = select(models.Rack).order_by(models.Rack.aisle_no, models.Rack.rack_no)
    if zone_id: stmt = stmt.where(models.Rack.zone_id == zone_id)
    result = []
    for rack in db.scalars(stmt).all():
        data = schemas.RackOut.model_validate(rack)
        data.location_count = rack.bay_count * rack.level_count * rack.positions_per_level
        result.append(data)
    return result

@router.post("/racks", response_model=schemas.RackOut, status_code=201)
def add_rack(payload: schemas.RackCreate, db: Session = Depends(get_db)):
    rack = create_rack(db, payload)
    data = schemas.RackOut.model_validate(rack)
    data.location_count = rack.bay_count * rack.level_count * rack.positions_per_level
    return data

@router.get("/racks/{rack_id}/locations", response_model=list[schemas.LocationOut])
def rack_locations(rack_id: int, db: Session = Depends(get_db)):
    if not db.get(models.Rack, rack_id): raise HTTPException(404, "Rack not found")
    locations=db.scalars(select(models.Location).where(models.Location.rack_id == rack_id).order_by(models.Location.level_no.desc(), models.Location.bay_no, models.Location.position_no)).all()
    result=[]
    for loc in locations:
        row={"id":loc.id,"warehouse_id":loc.warehouse_id,"location_code":loc.location_code,"location_type":loc.location_type,"rack_id":loc.rack_id,"bay_no":loc.bay_no,"level_no":loc.level_no,"position_no":loc.position_no,"status":loc.status,"is_active":loc.is_active}
        occupied=db.execute(select(models.HandlingUnit,models.Inventory,models.Product).join(models.Inventory,models.Inventory.handling_unit_id==models.HandlingUnit.id).join(models.Product,models.Product.id==models.Inventory.product_id).where(models.HandlingUnit.current_location_id==loc.id)).first()
        if occupied:
            hu,inv,product=occupied;row.update(hu_code=hu.hu_code,sku=product.sku,product_name=product.product_name,quantity=float(inv.quantity),reserved_quantity=float(inv.reserved_quantity),unit_of_measure=inv.unit_of_measure)
        result.append(row)
    return result

@router.get("/warehouse-map/live")
def live_warehouse_map(warehouse_id:int|None=None,db:Session=Depends(get_db)):
    warehouse=db.get(models.Warehouse,warehouse_id) if warehouse_id else db.scalar(select(models.Warehouse).order_by(models.Warehouse.id))
    if not warehouse: raise HTTPException(404,"Warehouse not found")
    zones=[]
    zone_rows=db.scalars(select(models.Zone).where(models.Zone.warehouse_id==warehouse.id)).all()
    size_order={"S":0,"M":1,"L":2,"XL":3}
    zone_rows.sort(key=lambda zone:(size_order.get(zone.storage_profile.size_class if zone.storage_profile else "",99),zone.zone_code))
    for zone in zone_rows:
        racks=[];zone_total=zone_occupied=zone_reserved=zone_blocked=0
        for rack in db.scalars(select(models.Rack).where(models.Rack.zone_id==zone.id).order_by(models.Rack.aisle_no,models.Rack.rack_no)).all():
            counts={status.value:(db.scalar(select(func.count()).select_from(models.Location).where(models.Location.rack_id==rack.id,models.Location.status==status)) or 0) for status in models.LocationStatus}
            hu_count=db.scalar(select(func.count()).select_from(models.HandlingUnit).join(models.Location,models.HandlingUnit.current_location_id==models.Location.id).where(models.Location.rack_id==rack.id)) or 0
            products=db.execute(select(models.Product.sku,func.sum(models.Inventory.quantity)).join(models.Inventory,models.Inventory.product_id==models.Product.id).join(models.HandlingUnit,models.Inventory.handling_unit_id==models.HandlingUnit.id).join(models.Location,models.HandlingUnit.current_location_id==models.Location.id).where(models.Location.rack_id==rack.id).group_by(models.Product.sku).order_by(models.Product.sku).limit(4)).all()
            total=sum(counts.values());zone_total+=total;zone_occupied+=counts["OCCUPIED"];zone_reserved+=counts["RESERVED"];zone_blocked+=counts["BLOCKED"]
            racks.append({"id":rack.id,"rack_code":f"A{rack.aisle_no:02d}-R{rack.rack_no:02d}","rack_name":rack.rack_name,"total":total,"available":counts["AVAILABLE"],"occupied":counts["OCCUPIED"],"reserved":counts["RESERVED"],"blocked":counts["BLOCKED"],"hu_count":hu_count,"utilization_percent":round((counts["OCCUPIED"]+counts["RESERVED"])/total*100,1) if total else 0,"products":[{"sku":sku,"quantity":float(qty)} for sku,qty in products]})
        zones.append({"id":zone.id,"zone_code":zone.zone_code,"zone_name":zone.zone_name,"total":zone_total,"available":zone_total-zone_occupied-zone_reserved-zone_blocked,"occupied":zone_occupied,"reserved":zone_reserved,"blocked":zone_blocked,"utilization_percent":round((zone_occupied+zone_reserved)/zone_total*100,1) if zone_total else 0,"racks":racks})
    stations=station_overview_rows(db,warehouse.id)
    docks=[{"id":x.id,"dock_code":x.dock_code,"dock_name":x.dock_name,"status":x.status,"capacity_vehicle":x.capacity_vehicle} for x in db.scalars(select(models.LoadingDock).where(models.LoadingDock.warehouse_id==warehouse.id).order_by(models.LoadingDock.dock_code)).all()]
    return {"warehouse":{"id":warehouse.id,"warehouse_code":warehouse.warehouse_code,"warehouse_name":warehouse.warehouse_name},"zones":zones,"stations":stations,"docks":docks}

@router.get("/locations", response_model=list[schemas.LocationOut])
def locations(location_type: str | None = None, status: str | None = None, limit: int = Query(500, le=5000), db: Session = Depends(get_db)):
    stmt = select(models.Location).order_by(models.Location.location_code).limit(limit)
    if location_type: stmt = stmt.where(models.Location.location_type == location_type)
    if status: stmt = stmt.where(models.Location.status == status)
    return db.scalars(stmt).all()

@router.get("/stations", response_model=list[schemas.StationOut])
def stations(warehouse_id: int | None = None, db: Session = Depends(get_db)):
    stmt = select(models.Station).order_by(models.Station.sequence)
    if warehouse_id: stmt = stmt.where(models.Station.warehouse_id == warehouse_id)
    return db.scalars(stmt).all()

@router.get("/stations/overview")
def stations_overview(warehouse_id:int|None=None,db:Session=Depends(get_db)):
    warehouse=db.get(models.Warehouse,warehouse_id) if warehouse_id else db.scalar(select(models.Warehouse).order_by(models.Warehouse.id))
    if not warehouse: raise HTTPException(404,"Warehouse not found")
    return station_overview_rows(db,warehouse.id)

@router.post("/stations", response_model=schemas.StationOut, status_code=201)
def add_station(payload: schemas.StationCreate, db: Session = Depends(get_db)):
    if payload.station_type not in {x.value for x in models.StationType}: raise HTTPException(422, "station_type must be INBOUND, CHECKOUT, LOADOUT, OUTBOUND or RETURN")
    return create_station(db, payload)

@router.get("/loading-docks", response_model=list[schemas.DockOut])
def docks(warehouse_id: int | None = None, db: Session = Depends(get_db)):
    stmt = select(models.LoadingDock).order_by(models.LoadingDock.dock_code)
    if warehouse_id: stmt = stmt.where(models.LoadingDock.warehouse_id == warehouse_id)
    result=[]
    for dock in db.scalars(stmt).all():
        status=dock.status
        if dock.is_active and status not in {'BLOCKED','INACTIVE'}:
            count=db.scalar(select(func.count()).select_from(models.DeliveryRun).where(models.DeliveryRun.loading_dock_id==dock.id,models.DeliveryRun.status.in_({'AT_DOCK','LOADING','READY_TO_DEPART'}))) or 0
            status='OCCUPIED' if count>=dock.capacity_vehicle else 'AVAILABLE'
        result.append(schemas.DockOut.model_validate(dock).model_copy(update={'status':status}))
    return result

@router.post("/loading-docks", response_model=schemas.DockOut, status_code=201)
def add_dock(payload: schemas.DockCreate, db: Session = Depends(get_db)):
    return create_dock(db, payload)

@router.get("/products", response_model=list[schemas.ProductOut])
def products(db:Session=Depends(get_db)):
    return db.scalars(select(models.Product).order_by(models.Product.sku)).all()

@router.post("/products",response_model=schemas.ProductOut,status_code=201)
def add_product(payload:schemas.ProductCreate,db:Session=Depends(get_db)):
    item=models.Product(**payload.model_dump()); db.add(item); db.commit(); return item

@router.post("/inbound/receive",status_code=201)
def inbound_receive(payload:schemas.ReceiveRequest,db:Session=Depends(get_db)):
    hu=receive(db,payload); return {"hu_code":hu.hu_code,"status":hu.current_status,"location_id":hu.current_location_id}

@router.get('/inbound/hu-code')
def hu_suggestion(db:Session=Depends(get_db)):
    from app.services.inventory import suggested_hu_code
    return {'hu_code':suggested_hu_code(db)}

@router.get('/station-workflow/{hu_code}')
def station_actions(hu_code:str,db:Session=Depends(get_db)):
    from app.services.station_workflow import workflow_view
    return workflow_view(db,hu_code)

@router.post('/station-workflow/move')
def station_move(payload:schemas.StationMoveRequest,db:Session=Depends(get_db)):
    from app.services.station_workflow import move
    return move(db,payload)

@router.post('/shipments/from-checkout',status_code=201,response_model=schemas.ShipmentOut)
def checkout_shipment(payload:schemas.CheckoutShipmentRequest,db:Session=Depends(get_db)):
    from app.services.station_workflow import ship_from_checkout
    return shipment_view(db,ship_from_checkout(db,payload))

@router.post('/shipments/{shipment_id}/cancel-before-loading',response_model=schemas.ShipmentOut)
def cancel_before_loading(shipment_id:int,db:Session=Depends(get_db)):
    from app.services.station_workflow import cancel
    return shipment_view(db,cancel(db,shipment_id))

@router.post("/putaway/recommend",response_model=schemas.LocationOut)
def putaway_recommend(payload:schemas.RecommendRequest,db:Session=Depends(get_db)):
    return recommend_putaway(db,payload.hu_code)

@router.get("/putaway/pending",response_model=list[schemas.PendingPutawayOut])
def pending_putaway(db:Session=Depends(get_db)):
    rows=db.execute(
        select(models.HandlingUnit,models.Inventory,models.Product,models.Location)
        .join(models.Inventory,models.Inventory.handling_unit_id==models.HandlingUnit.id)
        .join(models.Product,models.Product.id==models.Inventory.product_id)
        .join(models.Location,models.Location.id==models.HandlingUnit.current_location_id)
        .join(models.Station,models.Station.id==models.Location.station_id)
        .where(models.HandlingUnit.current_status=="RECEIVED",models.Station.station_type==models.StationType.INBOUND)
        .order_by(models.HandlingUnit.created_at,models.HandlingUnit.id)
    ).all()
    return [{"hu_code":hu.hu_code,"product_id":product.id,"sku":product.sku,"product_name":product.product_name,"quantity":float(inventory.quantity),"unit_of_measure":inventory.unit_of_measure,"inbound_location_code":location.location_code,"received_at":hu.created_at} for hu,inventory,product,location in rows]

@router.post("/putaway/options",response_model=list[schemas.LocationOut])
def available_putaway_options(payload:schemas.RecommendRequest,db:Session=Depends(get_db)):
    result=[]
    for location in putaway_options(db,payload.hu_code):
        item=schemas.LocationOut.model_validate(location).model_dump()
        item["zone_code"]=location.rack.zone.zone_code
        item["rack_code"]=f"A{location.rack.aisle_no:02d}-R{location.rack.rack_no:02d}"
        result.append(item)
    return result

@router.post("/putaway/confirm")
def putaway_confirm(payload:schemas.MoveRequest,db:Session=Depends(get_db)):
    hu=move_hu(db,payload.hu_code,payload.destination_location_id,"PUTAWAY"); return {"hu_code":hu.hu_code,"status":hu.current_status,"location_id":hu.current_location_id}

@router.get("/returns/pending")
def pending_returns(db:Session=Depends(get_db)):
    rows=db.execute(select(models.HandlingUnit,models.Inventory,models.Product,models.Location,models.Shipment).join(models.Inventory,models.Inventory.handling_unit_id==models.HandlingUnit.id).join(models.Product,models.Product.id==models.Inventory.product_id).join(models.Location,models.Location.id==models.HandlingUnit.current_location_id).join(models.Station,models.Station.id==models.Location.station_id).outerjoin(models.ShipmentItem,models.ShipmentItem.handling_unit_id==models.HandlingUnit.id).outerjoin(models.Shipment,models.Shipment.id==models.ShipmentItem.shipment_id).where(models.HandlingUnit.current_status=="RETURN_HOLD",models.Station.station_type==models.StationType.RETURN).order_by(models.HandlingUnit.created_at,models.HandlingUnit.id)).all()
    return [{"hu_code":hu.hu_code,"sku":product.sku,"product_name":product.product_name,"quantity":float(inventory.quantity),"unit_of_measure":inventory.unit_of_measure,"return_station_code":location.location_code,"shipment_no":shipment.shipment_no if shipment else None} for hu,inventory,product,location,shipment in rows]

@router.post("/returns/putaway-options",response_model=list[schemas.LocationOut])
def available_return_putaway_options(payload:schemas.RecommendRequest,db:Session=Depends(get_db)):
    result=[]
    for location in return_putaway_options(db,payload.hu_code):
        item=schemas.LocationOut.model_validate(location).model_dump();item["zone_code"]=location.rack.zone.zone_code;item["rack_code"]=f"A{location.rack.aisle_no:02d}-R{location.rack.rack_no:02d}";result.append(item)
    return result

@router.post("/returns/putaway")
def confirm_return_putaway(payload:schemas.MoveRequest,db:Session=Depends(get_db)):
    hu=putaway_return(db,payload.hu_code,payload.destination_location_id);return {"hu_code":hu.hu_code,"status":hu.current_status,"location_id":hu.current_location_id}

@router.post("/transfers")
def transfer(payload:schemas.MoveRequest,db:Session=Depends(get_db)):
    hu=move_hu(db,payload.hu_code,payload.destination_location_id,"TRANSFER"); return {"hu_code":hu.hu_code,"status":hu.current_status,"location_id":hu.current_location_id}

@router.post("/handling-units/split")
def split_handling_unit(payload:schemas.SplitHURequest,db:Session=Depends(get_db)):
    hu=split_hu(db,payload);return {"hu_code":hu.hu_code,"status":hu.current_status,"location_id":hu.current_location_id}

@router.post("/retrieval/confirm")
def retrieval(payload:schemas.ShipmentAction,db:Session=Depends(get_db)):
    if not payload.hu_code or not payload.location_id: raise HTTPException(422,"hu_code and location_id are required")
    hu=move_hu(db,payload.hu_code,payload.location_id,"RETRIEVE"); return {"hu_code":hu.hu_code,"status":hu.current_status,"location_id":hu.current_location_id}

@router.get("/inventory/search",response_model=list[schemas.InventoryOut])
def search_inventory(q:str|None=None,db:Session=Depends(get_db)):
    return inventory_search(db,q)

@router.post("/outbound-picks",response_model=schemas.ShipmentOut,status_code=201)
def create_outbound_pick(payload:schemas.PickFromLocationRequest,db:Session=Depends(get_db)):
    return shipment_view(db,pick_from_location(db,payload))

@router.get("/handling-units/{hu_code}",response_model=schemas.HUOut)
def handling_unit(hu_code:str,db:Session=Depends(get_db)):
    hu=db.scalar(select(models.HandlingUnit).where(models.HandlingUnit.hu_code==hu_code))
    if not hu: raise HTTPException(404,"Handling Unit not found")
    items=db.execute(select(models.HandlingUnitItem,models.Product).join(models.Product).where(models.HandlingUnitItem.handling_unit_id==hu.id)).all()
    movements=db.execute(select(models.StockMovement,models.StockMovementItem).join(models.StockMovementItem).where(models.StockMovementItem.handling_unit_id==hu.id).order_by(models.StockMovement.id.desc())).all()
    return {"id":hu.id,"hu_code":hu.hu_code,"hu_type":hu.hu_type,"current_node_type":hu.current_node_type,"current_status":hu.current_status,"current_location_id":hu.current_location_id,"current_vehicle_id":hu.current_vehicle_id,"items":[{"sku":p.sku,"product_name":p.product_name,"quantity":float(i.quantity),"unit_of_measure":i.unit_of_measure,"lot_no":i.lot_no,"batch_no":i.batch_no} for i,p in items],"movements":[{"movement_no":m.movement_no,"movement_type":m.movement_type,"created_at":m.created_at,"quantity":float(mi.quantity)} for m,mi in movements]}

@router.get("/customers",response_model=list[schemas.CustomerOut])
def customers(db:Session=Depends(get_db)): return db.scalars(select(models.Customer).order_by(models.Customer.customer_code)).all()
@router.post("/customers",response_model=schemas.CustomerOut,status_code=201)
def add_customer(payload:schemas.CustomerCreate,db:Session=Depends(get_db)):
    item=models.Customer(**payload.model_dump());db.add(item);db.commit();return item
@router.get("/vehicles",response_model=list[schemas.VehicleOut])
def vehicles(db:Session=Depends(get_db)): return db.scalars(select(models.Vehicle).order_by(models.Vehicle.vehicle_code)).all()
@router.post("/vehicles",response_model=schemas.VehicleOut,status_code=201)
def add_vehicle(payload:schemas.VehicleCreate,db:Session=Depends(get_db)):
    item=models.Vehicle(**payload.model_dump());db.add(item);db.commit();return item
@router.get("/drivers",response_model=list[schemas.DriverOut])
def drivers(db:Session=Depends(get_db)): return db.scalars(select(models.Driver).order_by(models.Driver.driver_code)).all()
@router.post("/drivers",response_model=schemas.DriverOut,status_code=201)
def add_driver(payload:schemas.DriverCreate,db:Session=Depends(get_db)):
    item=models.Driver(**payload.model_dump());db.add(item);db.commit();return item

@router.get("/shipments",response_model=list[schemas.ShipmentOut])
def shipments(db:Session=Depends(get_db)):
    return [shipment_view(db,s) for s in db.scalars(select(models.Shipment).order_by(models.Shipment.created_at.desc())).all()]
@router.post("/shipments",response_model=schemas.ShipmentOut,status_code=201)
def add_shipment(payload:schemas.ShipmentCreate,db:Session=Depends(get_db)): return shipment_view(db,create_shipment(db,payload))
@router.get("/shipments/{shipment_id}",response_model=schemas.ShipmentOut)
def shipment(shipment_id:int,db:Session=Depends(get_db)):
    item=db.get(models.Shipment,shipment_id)
    if not item: raise HTTPException(404,"Shipment not found")
    return shipment_view(db,item)
@router.post("/shipments/{shipment_id}/allocate",response_model=schemas.ShipmentOut)
def shipment_allocate(shipment_id:int,strategy:str=Query("FIFO",pattern="^(FIFO|FEFO)$"),db:Session=Depends(get_db)): return shipment_view(db,allocate(db,shipment_id,strategy))

@router.post('/shipments/{shipment_id}/transport',response_model=schemas.ShipmentOut)
def shipment_transport(shipment_id:int,payload:schemas.ShipmentTransportRequest,db:Session=Depends(get_db)):
    raise HTTPException(409,'จัดรถและจองรายการส่งที่หน้ารอบรถ /delivery-runs เท่านั้น')
@router.post("/shipments/{shipment_id}/ready-to-load",response_model=schemas.ShipmentOut)
def shipment_ready(shipment_id:int,db:Session=Depends(get_db)): return shipment_view(db,mark_ready(db,shipment_id))
@router.post("/shipments/{shipment_id}/retrieve",response_model=schemas.ShipmentOut)
def shipment_retrieve(shipment_id:int,payload:schemas.ShipmentAction,db:Session=Depends(get_db)):
    if not payload.hu_code or not payload.location_id: raise HTTPException(422,"hu_code and location_id are required")
    return shipment_view(db,move_shipment_hu(db,shipment_id,payload.hu_code,payload.location_id,"RETRIEVE"))
@router.post("/shipments/{shipment_id}/checkout",response_model=schemas.ShipmentOut)
def shipment_checkout(shipment_id:int,payload:schemas.ShipmentAction,db:Session=Depends(get_db)):
    if not payload.hu_code or not payload.location_id: raise HTTPException(422,"hu_code and location_id are required")
    return shipment_view(db,move_shipment_hu(db,shipment_id,payload.hu_code,payload.location_id,"CHECKOUT"))
@router.post("/shipments/{shipment_id}/start-loading",response_model=schemas.ShipmentOut)
def shipment_start_loading(shipment_id:int,payload:schemas.ShipmentAction=schemas.ShipmentAction(),db:Session=Depends(get_db)):
    raise HTTPException(409,'เริ่มโหลดที่หน้ารอบรถเท่านั้น')
@router.post("/shipments/{shipment_id}/load-hu",response_model=schemas.ShipmentOut)
def shipment_load_hu(shipment_id:int,payload:schemas.ShipmentAction,db:Session=Depends(get_db)):
    raise HTTPException(409,'สแกนขึ้นรถที่หน้ารอบรถเท่านั้น')
@router.post("/shipments/{shipment_id}/complete-loading",response_model=schemas.ShipmentOut)
def shipment_complete_loading(shipment_id:int,payload:schemas.ShipmentAction=schemas.ShipmentAction(),db:Session=Depends(get_db)):
    raise HTTPException(409,'ยืนยันโหลดครบที่หน้ารอบรถเท่านั้น')
@router.post("/shipments/{shipment_id}/depart",response_model=schemas.ShipmentOut)
def shipment_depart(shipment_id:int,payload:schemas.ShipmentAction=schemas.ShipmentAction(),db:Session=Depends(get_db)):
    raise HTTPException(409,'ปล่อยรถที่หน้ารอบรถเท่านั้น')
@router.post("/shipments/{shipment_id}/in-transit",response_model=schemas.ShipmentOut)
def shipment_in_transit(shipment_id:int,payload:schemas.ShipmentAction=schemas.ShipmentAction(),db:Session=Depends(get_db)): return shipment_view(db,simple_transition(db,shipment_id,"IN_TRANSIT",payload))
@router.post("/shipments/{shipment_id}/arrive",response_model=schemas.ShipmentOut)
def shipment_arrive(shipment_id:int,payload:schemas.ShipmentAction=schemas.ShipmentAction(),db:Session=Depends(get_db)): return shipment_view(db,simple_transition(db,shipment_id,"ARRIVED",payload))
@router.post("/shipments/{shipment_id}/deliver",response_model=schemas.ShipmentOut)
def shipment_deliver(shipment_id:int,payload:schemas.DeliveryRequest,db:Session=Depends(get_db)): return shipment_view(db,deliver(db,shipment_id,payload))
@router.post("/shipments/{shipment_id}/delivery-failed",response_model=schemas.ShipmentOut)
def shipment_failed(shipment_id:int,payload:schemas.FailureRequest,db:Session=Depends(get_db)): return shipment_view(db,fail_delivery(db,shipment_id,payload))
@router.post("/shipments/{shipment_id}/return",response_model=schemas.ShipmentOut)
def shipment_return(shipment_id:int,payload:schemas.ShipmentAction=schemas.ShipmentAction(),db:Session=Depends(get_db)): return shipment_view(db,start_return(db,shipment_id,payload))
@router.post("/shipments/{shipment_id}/return-complete",response_model=schemas.ShipmentOut)
def shipment_return_complete(shipment_id:int,payload:schemas.ReturnRequest,db:Session=Depends(get_db)):
    if not payload.return_station_id: raise HTTPException(422,"return_station_id is required")
    return shipment_view(db,complete_return(db,shipment_id,payload.return_station_id))
@router.get("/shipments/{shipment_id}/tracking")
def tracking(shipment_id:int,db:Session=Depends(get_db)):
    return shipment_view(db,db.get(models.Shipment,shipment_id))["tracking"]
@router.get("/shipments/{shipment_id}/pod")
def pod(shipment_id:int,db:Session=Depends(get_db)):
    item=db.scalar(select(models.ProofOfDelivery).where(models.ProofOfDelivery.shipment_id==shipment_id))
    if not item: raise HTTPException(404,"POD not found")
    return {"receiver_name":item.receiver_name,"receiver_phone":item.receiver_phone,"delivery_pin_verified":item.delivery_pin_verified,"signature_file":item.signature_file,"photo_file":item.photo_file,"delivered_at":item.delivered_at,"note":item.note}

@router.post("/shipments/{shipment_id}/pod",response_model=schemas.ShipmentOut)
def backfill_pod(shipment_id:int,payload:schemas.DeliveryRequest,db:Session=Depends(get_db)):
    return shipment_view(db,record_legacy_pod(db,shipment_id,payload))

@router.post("/shipments/{shipment_id}/pod-files")
async def upload_pod_files(shipment_id:int,signature:UploadFile|None=File(None),photo:UploadFile|None=File(None),db:Session=Depends(get_db)):
    pod=db.scalar(select(models.ProofOfDelivery).where(models.ProofOfDelivery.shipment_id==shipment_id))
    if not pod: raise HTTPException(409,"Confirm delivery before uploading POD evidence")
    upload_dir=Path("uploads");upload_dir.mkdir(exist_ok=True)
    async def save(file:UploadFile|None,prefix:str):
        if not file:return None
        if file.content_type not in {"image/jpeg","image/png","image/webp"}:raise HTTPException(422,"Only JPEG, PNG and WebP images are supported")
        content=await file.read(5*1024*1024+1)
        if len(content)>5*1024*1024:raise HTTPException(413,"POD file exceeds 5 MB")
        suffix={"image/jpeg":".jpg","image/png":".png","image/webp":".webp"}[file.content_type];name=f"{prefix}-{shipment_id}-{uuid4().hex}{suffix}";(upload_dir/name).write_bytes(content);return f"/files/{name}"
    pod.signature_file=await save(signature,"signature") or pod.signature_file;pod.photo_file=await save(photo,"photo") or pod.photo_file
    db.add(models.AuditLog(action="UPLOAD_POD",entity_type="SHIPMENT",entity_id=str(shipment_id),new_data='{"evidence": true}'));db.commit();return {"signature_file":pod.signature_file,"photo_file":pod.photo_file}

MASTER_MODELS={"products":models.Product,"customers":models.Customer,"vehicles":models.Vehicle,"drivers":models.Driver,"warehouses":models.Warehouse,"zones":models.Zone,"stations":models.Station,"loading-docks":models.LoadingDock,"storage-profiles":models.StorageProfile}
@router.patch("/master/{entity}/{item_id}/active")
def set_master_active(entity:str,item_id:int,payload:schemas.ActiveRequest,db:Session=Depends(get_db)):
    model=MASTER_MODELS.get(entity)
    if not model: raise HTTPException(404,"Master entity not found")
    item=db.get(model,item_id)
    if not item: raise HTTPException(404,"Master item not found")
    item.is_active=payload.is_active;db.add(models.AuditLog(action="ACTIVATE" if payload.is_active else "DEACTIVATE",entity_type=entity.upper(),entity_id=str(item_id),new_data=f'{{"is_active": {str(payload.is_active).lower()}}}'));db.commit();return {"id":item_id,"is_active":payload.is_active}

@router.get("/audit-logs")
def audit_logs(limit:int=Query(100,le=500),db:Session=Depends(get_db)):
    rows=db.scalars(select(models.AuditLog).order_by(models.AuditLog.id.desc()).limit(limit)).all()
    return [{"id":x.id,"action":x.action,"entity_type":x.entity_type,"entity_id":x.entity_id,"new_data":x.new_data,"created_at":x.created_at} for x in rows]
