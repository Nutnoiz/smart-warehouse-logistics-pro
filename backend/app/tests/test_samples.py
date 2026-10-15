import pytest
from sqlalchemy import select,func
from fastapi.testclient import TestClient
from app import models as m, schemas as s
from app.db.session import SessionLocal
from app.pro_models import SampleSet
from app.seed import seed
from app.core.security import create_access_token,hash_password
from app.main import app
from app.services.samples import change_dataset

def provision_empty():
    seed()
    with SessionLocal() as db:change_dataset(db)

def test_minimal_and_medium_replace_without_duplicates(client):
    provision_empty()
    first=client.post('/api/pro/samples',json={'profile':'minimal'})
    assert first.status_code==200,first.text
    assert first.json()['counts']['products']==4
    assert first.json()['counts']['handling_units']==12
    second=client.post('/api/pro/samples',json={'profile':'medium'})
    assert second.status_code==200,second.text
    assert second.json()['counts']['products']==12
    assert second.json()['counts']['handling_units']==46
    assert len(client.get('/api/products').json())==12
    runs=client.get('/api/delivery-runs?active_only=true').json()
    assert len(runs)==6
    assert len([r for r in runs if r['status']=='IN_TRANSIT'])==3
    assert all(len(r['shipments'])==3 for r in runs)
    rows=client.get('/api/warehouse-map/live').json()['zones']
    assert all(any(r['hu_count'] for r in z['racks']) for z in rows)

def test_sample_fleet_names_are_permanent_not_workflow_labels(client):
    provision_empty()
    assert client.post('/api/pro/samples',json={'profile':'medium'}).status_code==200
    vehicles=client.get('/api/vehicles').json()
    assert len(vehicles)==7
    assert {v['vehicle_code'] for v in vehicles}=={f'รถขนส่ง {n:02d} (ตัวอย่าง)' for n in range(1,8)}
    assert {v['license_plate'] for v in vehicles}=={f'ทะเบียนตัวอย่าง {n:02d}' for n in range(1,8)}
    assert all('LOAD' not in d['driver_code'] and 'ROAD' not in d['driver_code'] for d in client.get('/api/drivers').json())

def test_legacy_fleet_rename_preserves_runs_and_custom_names(client):
    from app.services.samples import rename_legacy_fleet
    provision_empty()
    client.post('/api/pro/samples',json={'profile':'minimal'})
    with SessionLocal() as db:
        first=db.scalar(select(m.Vehicle).order_by(m.Vehicle.id))
        driver=db.scalar(select(m.Driver).order_by(m.Driver.id))
        first.vehicle_code='DEMO-LOAD-01-ABCDEF';first.license_plate='ตัวอย่าง-LOAD01-ABCDEF'
        driver.driver_code='SAMPLE-ABCDEF-LOAD1';driver.last_name='LOAD 01'
        second=db.scalar(select(m.Vehicle).where(m.Vehicle.id!=first.id).order_by(m.Vehicle.id))
        second.vehicle_code='รถลูกค้าตั้งชื่อเอง';second.license_plate='ทะเบียนลูกค้า'
        original_runs=[(r.id,r.run_no,r.vehicle_id,r.driver_id,r.status) for r in db.scalars(select(m.DeliveryRun).order_by(m.DeliveryRun.id))]
        original_hu=[(hu.id,hu.hu_code,hu.current_vehicle_id) for hu in db.scalars(select(m.HandlingUnit).order_by(m.HandlingUnit.id))]
        db.commit()
        renamed=rename_legacy_fleet(db)
        assert len(renamed)==1
        assert first.vehicle_code=='รถขนส่ง 01 (ตัวอย่าง)'
        assert driver.last_name=='01'
        assert second.vehicle_code=='รถลูกค้าตั้งชื่อเอง'
        assert original_runs==[(r.id,r.run_no,r.vehicle_id,r.driver_id,r.status) for r in db.scalars(select(m.DeliveryRun).order_by(m.DeliveryRun.id))]
        assert original_hu==[(hu.id,hu.hu_code,hu.current_vehicle_id) for hu in db.scalars(select(m.HandlingUnit).order_by(m.HandlingUnit.id))]
        assert rename_legacy_fleet(db)==[]

def test_clear_preserves_non_sample_and_layout_and_stays_empty_after_restart(client):
    provision_empty()
    created=client.post('/api/products',json={'sku':'REAL-01','product_name':'สินค้าทั่วไป','size_class':'S'})
    assert created.status_code==201
    layout_before=len(client.get('/api/locations').json())
    assert client.post('/api/pro/samples',json={'profile':'minimal'}).status_code==200
    catalog_before=client.get('/api/products').json()
    assert client.post('/api/pro/samples/clear').status_code==200
    assert client.get('/api/products').json()==catalog_before
    assert any(p['sku']=='REAL-01' for p in catalog_before)
    assert client.get('/api/inventory/search').json()==[]
    assert client.get('/api/shipments').json()==[]
    assert len(client.get('/api/locations').json())==layout_before
    seed()
    assert client.get('/api/pro/samples').json()['profile'] is None
    assert client.get('/api/inventory/search').json()==[]
    assert client.post('/api/pro/samples/clear').status_code==200

def test_failed_build_restores_prior_dataset(client,monkeypatch):
    provision_empty()
    client.post('/api/pro/samples',json={'profile':'minimal'})
    before=client.get('/api/inventory/search').json()
    from app.services import samples
    def fail(db,profile):
        db.add(m.Product(sku='FAIL-ROLLBACK',product_name='temporary',size_class='S'));db.commit()
        raise RuntimeError('Simulated failure')
    monkeypatch.setattr(samples,'_build',fail)
    with SessionLocal() as db:
        with pytest.raises(RuntimeError):change_dataset(db,'medium')
    assert client.get('/api/inventory/search').json()==before
    assert client.get('/api/pro/samples').json()['profile']=='minimal'
    assert not any(p['sku']=='FAIL-ROLLBACK' for p in client.get('/api/products').json())

def test_sample_permissions_and_production_guard(client,monkeypatch):
    with SessionLocal() as db:
        db.add(m.User(username='viewer-sample',password_hash=hash_password('sample-password'),role='VIEWER'));db.commit()
    viewer=TestClient(app,headers={'Authorization':f'Bearer {create_access_token("viewer-sample")}'})
    assert viewer.post('/api/pro/samples',json={'profile':'minimal'}).status_code==403
    from app.core.config import settings
    monkeypatch.setattr(settings,'demo_mode',False)
    assert client.post('/api/pro/samples',json={'profile':'minimal'}).status_code==403
    assert client.post('/api/pro/samples/clear').status_code==403

def test_clear_keeps_non_sample_shipment_referencing_retained_customer(client):
    provision_empty();client.post('/api/pro/samples',json={'profile':'minimal'})
    customer=client.get('/api/customers').json()[0]
    real=client.post('/api/products',json={'sku':'REAL-01','product_name':'สินค้าจริง','size_class':'S'}).json()
    wh=client.get('/api/warehouses').json()[0]
    shipment=client.post('/api/shipments',json={'customer_id':customer['id'],'origin_warehouse_id':wh['id'],'items':[{'product_id':real['id'],'planned_quantity':1}]}).json()
    result=client.post('/api/pro/samples/clear')
    assert result.status_code==200,result.text
    assert client.get(f"/api/shipments/{shipment['id']}").status_code==200
    assert client.get('/api/pro/samples').json()['profile'] is None

def test_clear_includes_later_operations_on_sample_hus(client):
    provision_empty();client.post('/api/pro/samples',json={'profile':'minimal'})
    pending=client.get('/api/putaway/pending').json()[0]
    location=client.post('/api/putaway/options',json={'hu_code':pending['hu_code']}).json()[0]
    assert client.post('/api/putaway/confirm',json={'hu_code':pending['hu_code'],'destination_location_id':location['id']}).status_code==200
    assert client.post('/api/pro/samples/clear').status_code==200
    assert client.get('/api/inventory/search').json()==[]

def test_legacy_adoption_keeps_catalogue_and_only_clears_operations(client):
    provision_empty()
    with SessionLocal() as db:
        db.add_all([m.Product(sku='BEARING-6204',product_name='Deep Groove Ball Bearing',size_class='S'),m.Product(sku='KEEP-01',product_name='สินค้าทั่วไป',size_class='M')]);db.commit()
        change_dataset(db,'minimal',adopt_legacy=True)
        skus=list(db.scalars(select(m.Product.sku)))
        assert 'BEARING-6204' in skus
        assert 'KEEP-01' in skus

def test_clear_and_rebuild_reuses_persistent_catalogue_and_fleet(client):
    provision_empty()
    client.post('/api/pro/samples',json={'profile':'medium'})
    before={path:client.get('/api/'+path).json() for path in ['products','customers','vehicles','drivers']}
    assert client.post('/api/pro/samples/clear').status_code==200
    for path in before:
        current=client.get('/api/'+path).json()
        assert [(r['id'],r.get('sku',r.get('customer_code',r.get('vehicle_code',r.get('driver_code'))))) for r in current]==[(r['id'],r.get('sku',r.get('customer_code',r.get('vehicle_code',r.get('driver_code'))))) for r in before[path]]
    assert all(v['status']=='AVAILABLE' for v in client.get('/api/vehicles').json())
    assert client.get('/api/inventory/search').json()==[]
    assert client.get('/api/delivery-runs').json()==[]
    assert client.post('/api/pro/samples',json={'profile':'minimal'}).json()['counts']['products']==4
    assert len(client.get('/api/products').json())==12
    assert client.post('/api/pro/samples',json={'profile':'medium'}).status_code==200
    for path in before:
        assert [r['id'] for r in client.get('/api/'+path).json()]==[r['id'] for r in before[path]]

def test_single_sample_starts_only_at_inbound_and_clear_keeps_product(client):
    provision_empty()
    response=client.post('/api/pro/samples',json={'profile':'single'})
    assert response.status_code==200,response.text
    assert response.json()['counts']['products']==1 and response.json()['counts']['handling_units']==1
    rows=client.get('/api/inventory/search').json()
    assert len(rows)==1 and rows[0]['hu_status']=='RECEIVED'
    assert client.get('/api/shipments').json()==[] and client.get('/api/delivery-runs').json()==[]
    catalogue=client.get('/api/products').json()
    assert client.post('/api/pro/samples/clear').status_code==200
    assert client.get('/api/products').json()==catalogue
    assert client.get('/api/inventory/search').json()==[]
    assert client.post('/api/pro/samples',json={'profile':'single'}).status_code==200
    assert client.get('/api/products').json()==catalogue

def test_large_sample_covers_many_trucks_and_retains_catalogue(client):
    provision_empty()
    result=client.post('/api/pro/samples',json={'profile':'large'})
    assert result.status_code==200,result.text
    assert result.json()['counts']['handling_units']==178
    assert result.json()['counts']['products']==12
    rows=client.get('/api/inventory/search').json()
    assert len(rows)==178
    catalogue=client.get('/api/products').json()
    with SessionLocal() as db:
        runs=db.scalars(select(m.DeliveryRun).where(m.DeliveryRun.status.notin_(['COMPLETED','CANCELLED']))).all()
        assert len(runs)==16
    assert client.post('/api/pro/samples/clear').status_code==200
    assert client.get('/api/products').json()==catalogue
    assert client.get('/api/inventory/search').json()==[]
    assert client.post('/api/pro/samples',json={'profile':'large'}).status_code==200
    assert client.get('/api/products').json()==catalogue
    assert len(client.get('/api/vehicles').json())==17

def test_clear_twice_preserves_all_master_details_and_disabled_states(client):
    provision_empty()
    assert client.post('/api/pro/samples',json={'profile':'medium'}).status_code==200
    with SessionLocal() as db:
        product=db.scalar(select(m.Product).order_by(m.Product.id))
        customer=db.scalar(select(m.Customer).order_by(m.Customer.id))
        product.description='รายละเอียดสินค้าที่แก้เอง';product.is_active=False
        customer.customer_name='ลูกค้าที่แก้เอง';customer.phone='0811111111';customer.is_active=False
        db.add(m.Vehicle(vehicle_code='KEEP-BLOCKED',license_plate='KEEP-01',vehicle_type='6_WHEEL',status='MAINTENANCE',is_active=False))
        db.add(m.Driver(driver_code='KEEP-DRIVER',first_name='คนขับ',last_name='เก็บไว้',phone='0822222222',status='UNAVAILABLE',is_active=False))
        db.commit()
    before={path:client.get('/api/'+path).json() for path in ['products','customers','vehicles','drivers']}
    for _ in range(2):
        assert client.post('/api/pro/samples/clear').status_code==200
        for path,rows in before.items():
            after=client.get('/api/'+path).json()
            # Availability is transactional; identifiers and master details stay unchanged.
            clean=lambda data:[{k:v for k,v in r.items() if k not in {'status','updated_at'}} for r in data]
            assert clean(after)==clean(rows)
        assert next(v for v in client.get('/api/vehicles').json() if v['vehicle_code']=='KEEP-BLOCKED')['status']=='MAINTENANCE'
        assert next(d for d in client.get('/api/drivers').json() if d['driver_code']=='KEEP-DRIVER')['status']=='UNAVAILABLE'
        assert client.get('/api/inventory/search').json()==[]
        assert client.get('/api/shipments').json()==[]
        assert client.get('/api/delivery-runs').json()==[]
