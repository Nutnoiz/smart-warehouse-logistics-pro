"""Provision demo layout once. Clearing sample data survives subsequent restarts."""
from sqlalchemy import select
from app import models, schemas
from app.db.session import SessionLocal
from app.core.config import settings
from app.bootstrap import bootstrap
from app.services.warehouse import create_rack, create_station, create_dock


def seed():
    bootstrap()
    if not settings.demo_mode:return
    created=False
    with SessionLocal() as db:
        if db.scalar(select(models.Warehouse.id).limit(1)):return
        wh=models.Warehouse(warehouse_code='WH01',warehouse_name='Bangkok Home & Living Warehouse',address='Bangkok, Thailand')
        db.add(wh);db.flush()
        for index,(code,name,size,levels,positions,weight) in enumerate([
            ('TOTE_SMALL','Small home accessories','S',6,6,100),
            ('CARTON_MEDIUM','Home fixtures and decor','M',6,4,100),
            ('PALLET_STANDARD','Tile and sanitary ware','L',5,2,1500),
            ('OVERSIZE_STANDARD','Furniture and oversized goods','XL',3,1,100)],1):
            p=models.StorageProfile(profile_code=code,profile_name=name,storage_type='PALLET_RACK' if size=='L' else 'SHELF',unit_load_type='PALLET' if size in {'L','XL'} else 'BOX',size_class=size,height_class='H2',default_bay_count=6,default_level_count=levels,positions_per_level=positions,max_weight_kg=weight)
            db.add(p);db.flush();z=models.Zone(warehouse_id=wh.id,storage_profile_id=p.id,zone_code=size,zone_name=name)
            db.add(z);db.commit()
            create_rack(db,schemas.RackCreate(zone_id=z.id,aisle_no=index,rack_no=1,rack_name=f'ชั้นสินค้า {size}',bay_count=6,level_count=levels,positions_per_level=positions))
        rtn=models.Zone(warehouse_id=wh.id,zone_code='RTN',zone_name='Return / Supplier Hold');db.add(rtn);db.commit()
        create_rack(db,schemas.RackCreate(zone_id=rtn.id,aisle_no=90,rack_no=1,rack_name='ชั้นสินค้าคืน',bay_count=6,level_count=3,positions_per_level=2))
        for kind,count in [('INBOUND',3),('CHECKOUT',2),('LOADOUT',2),('RETURN',1)]:
            for sequence in range(1,count+1):create_station(db,schemas.StationCreate(warehouse_id=wh.id,station_name=f'{kind.title()} Station {sequence}',station_type=kind,capacity_hu=20,sequence=sequence))
        for sequence in [1,2]:create_dock(db,schemas.DockCreate(warehouse_id=wh.id,dock_name=f'Loading Dock {sequence}',capacity_vehicle=1,sequence=sequence))
        created=True
    if created:
        from app.services.samples import change_dataset
        with SessionLocal() as db:change_dataset(db,'minimal')


if __name__=='__main__':seed()
