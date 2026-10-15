"""Demo-only dataset management. All writes use one outer transaction.

Service commits are savepoints. A failed build restores the previous dataset.
Explicit ownership and foreign-key checks prevent deleting non-sample business data.
"""
import json
import re
from collections import defaultdict
from datetime import datetime, timezone
from uuid import uuid4
from fastapi import HTTPException
from sqlalchemy import event, func, select
from sqlalchemy.orm import Session
from app import models as m, schemas as s
from app.db.base import Base
from app.pro_models import SampleSet, CycleCount
from app.core.config import settings
from app.services.inventory import receive, move_hu, putaway_options, putaway_return, audit
from app.services.logistics import pick_from_location, move_shipment_hu, mark_ready, load_hu, simple_transition, fail_delivery, start_return, complete_return
from app.services import delivery_runs as transport

CATALOG = [
    ('S','LED-9W','หลอดไฟ LED 9W แสงวอร์มไวท์',.1,24,'EA'),
    ('S','SWITCH','สวิตช์ไฟติดผนัง 1 ช่อง',.15,12,'EA'),
    ('S','HANDLE','มือจับประตูสเตนเลส',.3,8,'EA'),
    ('M','FAUCET','ก๊อกอ่างล้างหน้าทรงสูง',1.4,6,'EA'),
    ('M','LAMP','โคมไฟตั้งโต๊ะสไตล์มินิมอล',2.5,4,'EA'),
    ('M','BIN-20L','ถังขยะสเตนเลส 20 ลิตร',3,3,'EA'),
    ('L','TILE-60','กระเบื้องแกรนิตโต้ 60×60 ซม.',28,5,'BOX'),
    ('L','TOILET','สุขภัณฑ์ชิ้นเดียว',35,2,'EA'),
    ('L','VANITY','อ่างล้างหน้าพร้อมเคาน์เตอร์',40,2,'EA'),
    ('XL','WARDROBE','ตู้เสื้อผ้า 2 บาน สไตล์โมเดิร์น',45,1,'EA'),
    ('XL','DINING','โต๊ะทานอาหาร 4 ที่นั่ง',55,1,'EA'),
    ('XL','SHELF','ชั้นวางของโลหะ 5 ชั้น',18,2,'EA'),
]
OWNABLE={'products','customers','vehicles','drivers','handling_units','handling_unit_items','inventory','warehouse_tasks','shipments','shipment_items','stock_movements','stock_movement_items','shipment_tracking_events','delivery_attempts','proof_of_delivery','delivery_runs','delivery_run_shipments','delivery_run_events','cycle_counts','audit_logs'}
MASTER_TABLES={'products','customers','vehicles','drivers'}

def require_demo():
    if not settings.demo_mode or settings.environment=='production':
        raise HTTPException(403,'เครื่องมือข้อมูลตัวอย่างใช้ได้เฉพาะโหมด Demo')

def fleet_labels(db):
    """Stable per-vehicle labels, independent of operational state or sample batch."""
    number=1
    while True:
        code=f'รถขนส่ง {number:02d} (ตัวอย่าง)'
        plate=f'ทะเบียนตัวอย่าง {number:02d}'
        driver=f'DRIVER-DEMO-{number:02d}'
        if not db.scalar(select(m.Vehicle.id).where((m.Vehicle.vehicle_code==code)|(m.Vehicle.license_plate==plate))) and not db.scalar(select(m.Driver.id).where(m.Driver.driver_code==driver)):
            return code,plate,driver,f'{number:02d}'
        number+=1

def rename_legacy_fleet(db):
    """Rename only untouched legacy masters explicitly owned by the sample set."""
    require_demo()
    state=db.get(SampleSet,1)
    manifest=json.loads(state.manifest) if state else {}
    changed=[]
    try:
        for v in db.scalars(select(m.Vehicle).where(m.Vehicle.id.in_(manifest.get('vehicles',[]))).order_by(m.Vehicle.id)):
            match=re.fullmatch(r'DEMO-(RETURN|ROAD|LOAD)-(\d{2})-([0-9A-F]{6})',v.vehicle_code)
            if not match:continue
            kind,num,tag=match.groups()
            if v.license_plate!=f'ตัวอย่าง-{kind}{num}-{tag}':continue
            code,plate,driver_code,label=fleet_labels(db)
            old={'vehicle_code':v.vehicle_code,'license_plate':v.license_plate}
            v.vehicle_code=code;v.license_plate=plate
            driver=db.scalar(select(m.Driver).where(m.Driver.id.in_(manifest.get('drivers',[])),m.Driver.driver_code==f'SAMPLE-{tag}-{kind}{int(num)}'))
            if driver and driver.first_name=='คนขับตัวอย่าง' and driver.last_name==f'{kind} {num}':
                driver.driver_code=driver_code;driver.last_name=label
                audit(db,'RENAME_SAMPLE_DRIVER','DRIVER',driver.id,{'driver_code':driver_code,'name':f'คนขับตัวอย่าง {label}'})
            audit(db,'RENAME_SAMPLE_VEHICLE','VEHICLE',v.id,{'before':old,'after':{'vehicle_code':code,'license_plate':plate}})
            db.flush();changed.append({'id':v.id,'before':old['vehicle_code'],'after':code})
        db.commit();return changed
    except Exception:
        db.rollback();raise

def status(db):
    state=db.get(SampleSet,1)
    manifest=json.loads(state.manifest) if state else {}
    counts={name:len(ids) for name,ids in manifest.items() if name in {'handling_units','shipments','vehicles'}} if state and state.profile else {}
    if state and state.profile:counts['products']=db.scalar(select(func.count(func.distinct(m.Inventory.product_id))).where(m.Inventory.handling_unit_id.in_(manifest.get('handling_units',[])))) or 0
    return {'profile':state.profile if state else None,'demo_mode':settings.demo_mode,'counts':counts,
            'catalog_products':db.scalar(select(func.count()).select_from(m.Product)) or 0,'updated_at':state.updated_at if state else None}

def _owned_rows(db, model, ids):
    return db.scalars(select(model).where(model.id.in_(ids))).all() if ids else []

def _expand_owned(db, manifest):
    """Include later operations/splits on sample-only goods; mixed shipments are blocked."""
    owned={name:set(ids) for name,ids in manifest.items()}
    products=owned.get('products',set())
    if not products:return owned
    hu_ids=set(owned.get('handling_units',set()))
    hu_ids.update(db.scalars(select(m.Inventory.handling_unit_id).where(m.Inventory.product_id.in_(products))))
    hu_ids.update(db.scalars(select(m.HandlingUnitItem.handling_unit_id).where(m.HandlingUnitItem.product_id.in_(products))))
    if db.scalar(select(m.HandlingUnitItem.id).where(m.HandlingUnitItem.handling_unit_id.in_(hu_ids),m.HandlingUnitItem.product_id.not_in(products)).limit(1)):
        raise HTTPException(409,'มี HU ที่รวมสินค้าจริงกับสินค้า sample กรุณาแยกสินค้าก่อนล้าง')
    owned['handling_units']=hu_ids
    shipments=set(owned.get('shipments',set()))
    shipments.update(db.scalars(select(m.ShipmentItem.shipment_id).where(m.ShipmentItem.product_id.in_(products))))
    if db.scalar(select(m.ShipmentItem.id).where(m.ShipmentItem.shipment_id.in_(shipments),m.ShipmentItem.product_id.not_in(products)).limit(1)):
        raise HTTPException(409,'มีรายการส่งที่ผสมสินค้าจริงกับ sample จึงยังล้างไม่ได้')
    owned['shipments']=shipments
    runs=set(owned.get('delivery_runs',set()))
    runs.update(db.scalars(select(m.DeliveryRunShipment.delivery_run_id).where(m.DeliveryRunShipment.shipment_id.in_(shipments))))
    runs.update(db.scalars(select(m.DeliveryRun.id).outerjoin(m.DeliveryRunShipment,m.DeliveryRunShipment.delivery_run_id==m.DeliveryRun.id).where(m.DeliveryRun.vehicle_id.in_(owned.get('vehicles',set())),m.DeliveryRunShipment.id.is_(None))))
    if db.scalar(select(m.DeliveryRunShipment.id).where(m.DeliveryRunShipment.delivery_run_id.in_(runs),m.DeliveryRunShipment.shipment_id.not_in(shipments)).limit(1)):
        raise HTTPException(409,'รถ sample มีรายการส่งอื่นร่วมรอบ กรุณาแยกรายการก่อนล้าง')
    owned['delivery_runs']=runs
    movements=set(owned.get('stock_movements',set()))
    movements.update(db.scalars(select(m.StockMovementItem.movement_id).where(m.StockMovementItem.handling_unit_id.in_(hu_ids))))
    if db.scalar(select(m.StockMovementItem.id).where(m.StockMovementItem.movement_id.in_(movements),m.StockMovementItem.product_id.not_in(products)).limit(1)):
        raise HTTPException(409,'มีการเคลื่อนย้ายสินค้าจริงร่วมกับ sample จึงยังล้างไม่ได้')
    owned['stock_movements']=movements
    parents={'products':products,'handling_units':hu_ids,'shipments':shipments,'delivery_runs':runs,'stock_movements':movements}
    # Follow foreign keys down to inventory, tasks, POD, counts and tracking events.
    for _ in range(4):
        changed=False
        for name in OWNABLE-{'audit_logs','products','customers','vehicles','drivers','handling_units','shipments','delivery_runs','stock_movements'}:
            table=Base.metadata.tables[name]
            for fk in table.foreign_keys:
                if fk.column.table.name in {'customers','vehicles','drivers'}:continue
                ids=owned.get(fk.column.table.name,set())
                if ids:
                    new=set(db.scalars(select(table.c.id).where(fk.parent.in_(ids))))
                    previous=owned.setdefault(name,set());before=len(previous);previous.update(new);changed|=len(previous)!=before
        if not changed:break
    entities={'PRODUCT':'products','HANDLING_UNIT':'handling_units','SHIPMENT':'shipments','DELIVERY_RUN':'delivery_runs','CYCLE_COUNT':'cycle_counts','WAREHOUSE_TASK':'warehouse_tasks'}
    for entity,table in entities.items():
        ids=owned.get(table,set())
        if ids:owned.setdefault('audit_logs',set()).update(db.scalars(select(m.AuditLog.id).where(m.AuditLog.entity_type==entity,m.AuditLog.entity_id.in_([str(x) for x in ids]))))
    return owned

def _clear(db, manifest):
    owned=_expand_owned(db,manifest)
    if not owned:return
    # Operational reset never deletes the persistent catalogue or other masters.
    master_ids={name:owned.pop(name,set()) for name in MASTER_TABLES}
    if owned.get('audit_logs'):
        master_logs=set(db.scalars(select(m.AuditLog.id).where(m.AuditLog.id.in_(owned['audit_logs']),m.AuditLog.entity_type.in_({'PRODUCT','CUSTOMER','VEHICLE','DRIVER'}))))
        owned['audit_logs']-=master_logs
    # Never cascade an owned master record into unrelated customer-created records.
    for table in Base.metadata.sorted_tables:
        if 'id' not in table.c:continue
        for fk in table.foreign_keys:
            parent_ids=owned.get(fk.column.table.name,set())
            if parent_ids and db.scalar(select(table.c.id).where(fk.parent.in_(parent_ids),table.c.id.not_in(owned.get(table.name,set()))).limit(1)):
                raise HTTPException(409,f'ข้อมูล {table.name} นอกชุด sample อ้างอิงอยู่ จึงยังล้างไม่ได้')
    locations=set(db.scalars(select(m.HandlingUnit.current_location_id).where(m.HandlingUnit.id.in_(owned.get('handling_units',set())),m.HandlingUnit.current_location_id.is_not(None))))
    locations.update(db.scalars(select(m.StockMovement.source_location_id).where(m.StockMovement.id.in_(owned.get('stock_movements',set())),m.StockMovement.source_location_id.is_not(None))))
    locations.update(db.scalars(select(m.StockMovement.destination_location_id).where(m.StockMovement.id.in_(owned.get('stock_movements',set())),m.StockMovement.destination_location_id.is_not(None))))
    docks=set(db.scalars(select(m.DeliveryRun.loading_dock_id).where(m.DeliveryRun.id.in_(owned.get('delivery_runs',set())),m.DeliveryRun.loading_dock_id.is_not(None))))
    for table in reversed(Base.metadata.sorted_tables):
        if table.name in MASTER_TABLES:continue
        ids=owned.get(table.name,set())
        if ids:db.execute(table.delete().where(table.c.id.in_(ids)))
    db.expire_all()
    for loc in _owned_rows(db,m.Location,locations):
        if loc.location_type!='STORAGE' or loc.status==m.LocationStatus.BLOCKED:continue
        remaining=db.scalar(select(func.count()).select_from(m.HandlingUnit).where(m.HandlingUnit.current_location_id==loc.id)) or 0
        reserved=db.scalar(select(func.sum(m.Inventory.reserved_quantity)).where(m.Inventory.location_id==loc.id)) or 0
        loc.status=m.LocationStatus.RESERVED if remaining and reserved else m.LocationStatus.OCCUPIED if remaining else m.LocationStatus.AVAILABLE
    for dock in _owned_rows(db,m.LoadingDock,docks):
        if dock.status not in {'BLOCKED','INACTIVE'}:transport._refresh_dock_status(db,dock.id)
    for vehicle in _owned_rows(db,m.Vehicle,master_ids['vehicles']):
        active=db.scalar(select(m.DeliveryRun.id).where(m.DeliveryRun.vehicle_id==vehicle.id,m.DeliveryRun.status.in_(transport.ACTIVE)).limit(1))
        cargo=db.scalar(select(m.HandlingUnit.id).where(m.HandlingUnit.current_vehicle_id==vehicle.id).limit(1))
        if not active and not cargo and vehicle.status not in {'BLOCKED','INACTIVE','MAINTENANCE'}:vehicle.status='AVAILABLE'
    for driver in _owned_rows(db,m.Driver,master_ids['drivers']):
        active=db.scalar(select(m.DeliveryRun.id).where(m.DeliveryRun.driver_id==driver.id,m.DeliveryRun.status.in_(transport.ACTIVE)).limit(1))
        if not active and driver.status not in {'BLOCKED','INACTIVE','UNAVAILABLE'}:driver.status='AVAILABLE'
    db.flush()

def _adopt_legacy(db):
    products=db.scalars(select(m.Product).where(m.Product.sku.in_(['BEARING-6204','MOTOR-2HP','PUMP-050']))).all()
    if not products:return {}
    # Exact seeded names distinguish the previous demo catalogue from operational goods.
    expected={'BEARING-6204':'Deep Groove Ball Bearing','MOTOR-2HP':'Industrial Motor 2HP','PUMP-050':'Centrifugal Pump'}
    if any(p.product_name!=expected[p.sku] for p in products):raise HTTPException(409,'สินค้า demo เดิมถูกแก้ไข กรุณาตรวจข้อมูลก่อนแทนที่')
    manifest={'products':[p.id for p in products]}
    for cls,column,codes in [(m.Customer,m.Customer.customer_code,['CUS001','CUS002','CUS003']),(m.Vehicle,m.Vehicle.vehicle_code,[f'TRUCK-{i:03d}' for i in range(1,6)]),(m.Driver,m.Driver.driver_code,[f'DRV-{i:03d}' for i in range(1,6)])]:
        manifest[cls.__tablename__]=list(db.scalars(select(cls.id).where(column.in_(codes))))
    return manifest

def change_dataset(db, profile=None, adopt_legacy=False):
    require_demo()
    if profile not in {None,'single','minimal','medium','large'}:raise HTTPException(422,'Unknown sample size')
    connection=db.connection()
    if connection.dialect.name=='sqlite':connection.exec_driver_sql('BEGIN IMMEDIATE')
    # Lock a stable row across administrators before creating/locking the singleton state.
    db.scalar(select(m.User).where(m.User.role=='ADMIN').order_by(m.User.id).limit(1).with_for_update())
    state=db.scalar(select(SampleSet).where(SampleSet.id==1).with_for_update())
    if not state:state=SampleSet(id=1,manifest='{}');db.add(state);db.flush()
    previous=json.loads(state.manifest)
    if adopt_legacy:
        for name,ids in _adopt_legacy(db).items():previous[name]=sorted(set(previous.get(name,[]))|set(ids))
    child=Session(bind=connection,join_transaction_mode='create_savepoint',autoflush=False,expire_on_commit=False)
    child.info.update(db.info)
    created=defaultdict(set)
    @event.listens_for(child,'after_flush')
    def track_new(session,context):
        for obj in session.new:
            if getattr(obj,'__tablename__',None) in OWNABLE and getattr(obj,'id',None) is not None:created[obj.__tablename__].add(obj.id)
    try:
        _clear(child,previous)
        child.commit()
        child.info['sample_master_ids']={name:previous.get(name,[]) for name in MASTER_TABLES}
        if profile:_build(child,profile)
        child.commit()
        for name in MASTER_TABLES:created[name].update(previous.get(name,[]))
        state.profile=profile
        state.manifest=json.dumps({k:sorted(v) for k,v in created.items() if profile or k in MASTER_TABLES})
        state.updated_at=datetime.now(timezone.utc)
        audit(db,'SAMPLE_CREATE' if profile else 'SAMPLE_CLEAR','SAMPLE_SET','1',{'profile':profile,'created_hu':len(created.get('handling_units',[]))})
        db.commit()
    except Exception:
        child.rollback();db.rollback();raise
    finally:child.close()
    return status(db)

def _build(db, profile):
    wh=db.scalar(select(m.Warehouse).where(m.Warehouse.is_active.is_(True)).order_by(m.Warehouse.id))
    if not wh:raise HTTPException(409,'ต้องสร้างคลังและชั้นวางก่อนสร้าง sample')
    zones={z.zone_code:z for z in db.scalars(select(m.Zone).where(m.Zone.warehouse_id==wh.id,m.Zone.is_active.is_(True)))}
    if not all(z in zones for z in ['S','M','L','XL','RTN']):raise HTTPException(409,'ต้องมีโซน S, M, L, XL และ RTN เพื่อสร้างชุดตัวอย่าง')
    stations={typ:db.scalars(select(m.Station).where(m.Station.warehouse_id==wh.id,m.Station.station_type==typ,m.Station.is_active.is_(True)).order_by(m.Station.sequence)).all() for typ in ['INBOUND','CHECKOUT','LOADOUT','RETURN']}
    docks=db.scalars(select(m.LoadingDock).where(m.LoadingDock.warehouse_id==wh.id,m.LoadingDock.is_active.is_(True)).order_by(m.LoadingDock.id)).all()
    if not all(stations.values()) or len(docks)<2:raise HTTPException(409,'ต้องมีสถานีครบและประตูโหลดอย่างน้อยสองจุด')
    large=profile=='large'
    tag=uuid4().hex[:6].upper();n=8 if large else (1 if profile in {'single','minimal'} else 3)
    retained=db.info.get('sample_master_ids',{})
    existing_products=_owned_rows(db,m.Product,retained.get('products',[]))
    existing_customers=sorted(_owned_rows(db,m.Customer,retained.get('customers',[])),key=lambda x:x.id)
    existing_vehicles=sorted([v for v in _owned_rows(db,m.Vehicle,retained.get('vehicles',[])) if v.is_active and v.status=='AVAILABLE' and float(v.max_weight_kg or 0)>=8000],key=lambda x:x.id)
    existing_drivers=sorted([d for d in _owned_rows(db,m.Driver,retained.get('drivers',[])) if d.is_active and d.status=='AVAILABLE'],key=lambda x:x.id)
    selected=[CATALOG[3]] if profile=='single' else [p for i,p in enumerate(CATALOG) if profile in {'medium','large'} or i%3==0]
    products=[];quantities={}
    for size,code,name,weight,quantity,unit in selected:
        p=next((p for p in existing_products if p.sku.startswith(f'HOME-{code}-') and p.is_active and p.size_class==size and p.default_storage_profile_id==zones[size].storage_profile_id),None)
        if not p:
            p=m.Product(sku=f'HOME-{code}-{tag}',product_name=name,barcode=f'SAMPLE-{tag}-{code}',size_class=size,velocity_class='B',height_class='H2',default_storage_profile_id=zones[size].storage_profile_id,weight_kg=weight)
            db.add(p);db.flush()
        products.append(p);quantities[p.id]=(quantity,unit)
    customers=[]
    for i in range(1 if profile=='single' else min(3,max(2,n))):
        c=next((c for c in existing_customers if c.is_active and c not in customers),None)
        if not c:
            c=m.Customer(customer_code=f'SAMPLE-{tag}-CUS{i+1}',customer_name=['บ้านตัวอย่าง สุขุมวิท','บ้านตัวอย่าง บางนา','โครงการบ้านสวน รังสิต'][i],contact_name='ผู้รับตัวอย่าง',phone='0800000000',address_line1='99 ถนนตัวอย่าง',province='กรุงเทพมหานคร',country='Thailand')
            db.add(c)
        customers.append(c)
    db.flush()
    counter=0
    def hu(product=None, stage='STORED', index=0):
        nonlocal counter
        counter+=1;product=product or products[(counter-1)%len(products)];quantity,unit=quantities[product.id]
        obj=receive(db,s.ReceiveRequest(product_id=product.id,hu_code=f'SAMPLE-{tag}-HU{counter:03d}',hu_type='PALLET' if product.size_class in {'L','XL'} else 'BOX',quantity=quantity,unit_of_measure=unit,station_id=stations['INBOUND'][index%len(stations['INBOUND'])].id,lot_no=f'HOME-DEMO-{tag}'))
        if stage!='INBOUND':move_hu(db,obj.hu_code,putaway_options(db,obj.hu_code)[0].id,'PUTAWAY')
        return obj
    def fleet(kind, number):
        code,plate,driver_code,label=fleet_labels(db)
        v=existing_vehicles.pop(0) if existing_vehicles else m.Vehicle(vehicle_code=code,license_plate=plate,vehicle_type='6_WHEEL',max_weight_kg=8000)
        d=existing_drivers.pop(0) if existing_drivers else m.Driver(driver_code=driver_code,first_name='คนขับตัวอย่าง',last_name=label,phone='0800000000')
        db.add_all([v,d]);db.flush();return v,d
    def shipment(obj,v,d,index=0,dock=None):
        inv=db.scalar(select(m.Inventory).where(m.Inventory.handling_unit_id==obj.id))
        return pick_from_location(db,s.PickFromLocationRequest(source_hu_code=obj.hu_code,quantity=float(inv.quantity),customer_id=customers[index%len(customers)].id,checkout_station_id=stations['CHECKOUT'][index%len(stations['CHECKOUT'])].id,vehicle_id=v.id if v else None,driver_id=d.id if d else None,loading_dock_id=dock.id if dock else None))
    def stage_loadout(sh,obj,index=0):
        loc=db.scalar(select(m.Location).where(m.Location.station_id==stations['LOADOUT'][index%len(stations['LOADOUT'])].id))
        move_shipment_hu(db,sh.id,obj.hu_code,loc.id,'CHECKOUT');mark_ready(db,sh.id)
    def run_id(sh):return db.scalar(select(m.DeliveryRunShipment.delivery_run_id).where(m.DeliveryRunShipment.shipment_id==sh.id))
    action=s.DeliveryRunAction(note='ข้อมูลตัวอย่างตกแต่งบ้าน')
    if profile=='single':
        fleet('DEMO',1)
        hu(products[0],stage='INBOUND')
        return
    def travel(rid, pairs, dock):
        transport.check_in(db,rid,action);transport.enter_dock(db,rid,s.DeliveryRunDockRequest(loading_dock_id=dock.id));transport.start_loading(db,rid,action)
        for sh,obj in pairs:load_hu(db,sh.id,obj.hu_code)
        transport.complete_loading(db,rid,action);transport.depart(db,rid,action);transport.mark_in_transit(db,rid,action)
    # Real stock in every normal zone, plus inbound and staging work.
    for _ in range(4 if large else 1):
        for p in products:hu(p)
    for i in range(18 if large else (1 if n==1 else 5)):hu(stage='INBOUND',index=i)
    for i in range(12 if large else n):shipment(hu(),None,None,i)
    for i in range(8 if large else n):
        obj=hu();sh=shipment(obj,None,None,i);stage_loadout(sh,obj,i)
    # Returns use a completed failed-delivery trip; some stay on return station, others RTN.
    rv,rd=fleet('RETURN',1)
    for i in range(12 if large else (2 if n==1 else 5)):
        obj=hu();sh=shipment(obj,rv,rd,i,docks[0]);stage_loadout(sh,obj,i);travel(run_id(sh),[(sh,obj)],docks[0])
        simple_transition(db,sh.id,'ARRIVED',s.ShipmentAction(note='ตัวอย่างนำส่งไม่สำเร็จ'))
        fail_delivery(db,sh.id,s.FailureRequest(failure_reason='CUSTOMER_UNAVAILABLE',note='ไม่มีผู้รับสินค้า'));start_return(db,sh.id,s.ShipmentAction())
        complete_return(db,sh.id,stations['RETURN'][0].id)
        if i < (4 if large else (1 if n==1 else 2)):
            dest=db.scalar(select(m.Location).where(m.Location.zone_id==zones['RTN'].id,m.Location.status==m.LocationStatus.AVAILABLE,m.Location.is_active.is_(True)).order_by(m.Location.location_code))
            if not dest:raise HTTPException(409,'ชั้น RTN ไม่มีพื้นที่สำหรับ sample')
            putaway_return(db,obj.hu_code,dest.id)
    # Road fleet is prepared first so docks are free for its departure.
    for i in range(n):
        v,d=fleet('ROAD',i+1);pairs=[]
        for j in range(6 if large else (2 if n==1 else 3)):
            obj=hu();sh=shipment(obj,v,d,j,docks[i%len(docks)]);stage_loadout(sh,obj,j);pairs.append((sh,obj))
        travel(run_id(pairs[0][0]),pairs,docks[i%len(docks)])
    # Loading fleet occupies the lower dashboard area; extra trucks wait for a dock.
    for i in range(n):
        v,d=fleet('LOAD',i+1);pairs=[]
        for j in range(4 if large else (1 if n==1 else 3)):
            obj=hu();sh=shipment(obj,v,d,j,docks[i%len(docks)]);stage_loadout(sh,obj,j);pairs.append((sh,obj))
        rid=run_id(pairs[0][0]);transport.check_in(db,rid,action)
        if i<len(docks):
            transport.enter_dock(db,rid,s.DeliveryRunDockRequest(loading_dock_id=docks[i].id));transport.start_loading(db,rid,action)
            load_hu(db,pairs[0][0].id,pairs[0][1].hu_code)
