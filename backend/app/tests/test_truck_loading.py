from app.tests.test_end_to_end import setup_flow
from app.tests.test_station_workflow import move

def fixture(client,suffix='truck'):
    data=setup_flow(client,suffix)
    assert client.post('/api/shipments/'+str(data['shipment']['id'])+'/cancel-before-loading',json={}).status_code==200
    vehicles=client.get('/api/vehicles').json();drivers=client.get('/api/drivers').json();docks=client.get('/api/loading-docks').json()
    payload={'origin_warehouse_id':client.get('/api/warehouses').json()[0]['id'],'vehicle_id':vehicles[0]['id'],'driver_id':drivers[0]['id'],'loading_dock_id':docks[0]['id'],'arrived':True}
    r=client.post('/api/delivery-runs',json=payload);assert r.status_code==201,r.text
    return data,payload,r.json()

def shipment(client,hu,qty=100):
    if client.get('/api/station-workflow/'+hu).json()['kind']!='CHECKOUT':move(client,hu,'CHECKOUT')
    r=client.post('/api/shipments/from-checkout',json={'hu_code':hu,'quantity':qty,'customer_id':client.get('/api/customers').json()[0]['id']})
    assert r.status_code==201,r.text
    s=r.json();move(client,s['items'][0]['hu_code'],'LOADOUT')
    return s

def test_empty_truck_arrives_before_any_shipment(client):
    _,p,r=fixture(client,'first')
    assert r['shipments']==[] and r['status']=='WAITING_DOCK'
    assert client.post('/api/delivery-runs',json=p).status_code==409
    assert client.get('/api/truck-loading/choices?warehouse_id='+str(p['origin_warehouse_id'])).json()==[]
    result=client.post(f"/api/delivery-runs/{r['id']}/enter-dock",json={})
    assert result.status_code==200,result.text
    choices=client.get('/api/truck-loading/choices?warehouse_id='+str(p['origin_warehouse_id'])).json()
    assert len(choices)==1 and choices[0]['id']==r['id']
    assert client.post(f"/api/delivery-runs/{r['id']}/start-loading",json={}).status_code==409

def test_incremental_loading_and_departure(client):
    d,p,r=fixture(client,'incremental');rid=r['id']
    client.post(f'/api/delivery-runs/{rid}/enter-dock',json={})
    a=shipment(client,d['hu'],25)
    b=shipment(client,d['hu'],15)
    q=client.get(f'/api/delivery-runs/{rid}/loading-queue').json()
    assert {s['id'] for s in q}=={a['id'],b['id']}
    add=client.post(f'/api/delivery-runs/{rid}/shipments',json={'shipment_id':a['id']})
    assert add.status_code==200,add.text
    assert client.post(f'/api/delivery-runs/{rid}/shipments',json={'shipment_id':a['id']}).json()['shipments'][0]['id']==a['id']
    assert client.post(f'/api/delivery-runs/{rid}/start-loading',json={}).status_code==200
    assert client.post(f'/api/delivery-runs/{rid}/shipments',json={'shipment_id':b['id']}).status_code==200
    assert client.get('/api/shipments/'+str(b['id'])).json()['status']=='LOADING'
    for s in [a,b]:
        assert client.post(f'/api/delivery-runs/{rid}/scan',json={'hu_code':s['items'][0]['hu_code']}).status_code==200
    assert client.post(f'/api/delivery-runs/{rid}/scan',json={'hu_code':a['items'][0]['hu_code']}).status_code==409
    assert client.post(f'/api/delivery-runs/{rid}/scan',json={'hu_code':d['hu']}).status_code==409
    assert client.post(f"/api/delivery-runs/{rid}/shipments/{a['id']}/remove",json={}).status_code==409
    assert client.post(f'/api/delivery-runs/{rid}/complete-loading',json={}).status_code==200
    assert client.post(f'/api/delivery-runs/{rid}/shipments',json={'shipment_id':a['id']}).status_code==409
    assert client.post(f'/api/delivery-runs/{rid}/depart',json={}).status_code==200
    assert client.get('/api/truck-loading/choices?warehouse_id='+str(p['origin_warehouse_id'])).json()==[]
    assert client.get(f'/api/delivery-runs/{rid}').json()['status']=='DEPARTED'

def test_detach_preserves_shipping_and_empty_cancel(client):
    d,p,r=fixture(client,'detach');rid=r['id']
    client.post(f'/api/delivery-runs/{rid}/enter-dock',json={})
    s=shipment(client,d['hu'])
    client.post(f'/api/delivery-runs/{rid}/shipments',json={'shipment_id':s['id']})
    assert client.post(f'/api/delivery-runs/{rid}/cancel-empty',json={}).status_code==409
    assert client.post(f"/api/delivery-runs/{rid}/shipments/{s['id']}/remove",json={}).status_code==200
    assert client.get('/api/shipments/'+str(s['id'])).json()['status']=='READY_TO_LOAD'
    assert client.get('/api/shipments/'+str(s['id'])).json()['vehicle_id'] is None
    assert client.post(f'/api/delivery-runs/{rid}/cancel-empty',json={}).json()['status']=='CANCELLED'
    assert client.get('/api/vehicles').json()[0]['status']=='AVAILABLE'
    assert client.get('/api/drivers').json()[0]['status']=='AVAILABLE'
    assert client.get('/api/loading-docks').json()[0]['status']=='AVAILABLE'

def test_checkout_or_waiting_truck_cannot_be_loaded(client):
    d,p,r=fixture(client,'qcguard');rid=r['id']
    move(client,d['hu'],'CHECKOUT')
    s=client.post('/api/shipments/from-checkout',json={'hu_code':d['hu'],'quantity':100,'customer_id':client.get('/api/customers').json()[0]['id']}).json()
    assert client.post(f'/api/delivery-runs/{rid}/shipments',json={'shipment_id':s['id']}).status_code==409
    client.post(f'/api/delivery-runs/{rid}/enter-dock',json={})
    assert client.post(f'/api/delivery-runs/{rid}/shipments',json={'shipment_id':s['id']}).status_code==409

def test_driver_exclusive_and_foreign_warehouse(client):
    d,p,r=fixture(client,'exclusive')
    v=client.post('/api/vehicles',json={'vehicle_code':'OTHER-V','license_plate':'OTHER','vehicle_type':'TRUCK'}).json()
    assert client.post('/api/delivery-runs',json={**p,'vehicle_id':v['id']}).status_code==409
    client.post(f"/api/delivery-runs/{r['id']}/enter-dock",json={})
    s=shipment(client,d['hu'])
    wh=client.post('/api/warehouses',json={'warehouse_code':'OTHER','warehouse_name':'Other'}).json()
    from app.db.session import SessionLocal
    from app import models
    with SessionLocal() as db:db.get(models.Shipment,s['id']).origin_warehouse_id=wh['id'];db.commit()
    assert client.post(f"/api/delivery-runs/{r['id']}/shipments",json={'shipment_id':s['id']}).status_code==409

def test_capacity_and_permissions(client):
    d,p,r=fixture(client,'capacity')
    client.post(f"/api/delivery-runs/{r['id']}/enter-dock",json={})
    s=shipment(client,d['hu'])
    from app.db.session import SessionLocal
    from app import models
    from app.core.security import create_access_token,hash_password
    with SessionLocal() as db:
        db.get(models.Vehicle,p['vehicle_id']).max_weight_kg=1
        hu=db.get(models.HandlingUnit,s['items'][0]['handling_unit_id']);hu.gross_weight_kg=2
        db.add(models.User(username='readtruck',password_hash=hash_password('test-password'),role='VIEWER'));db.commit()
    assert client.post(f"/api/delivery-runs/{r['id']}/shipments",json={'shipment_id':s['id']}).status_code==409
    assert client.post('/api/delivery-runs',json=p,headers={'Authorization':'Bearer '+create_access_token('readtruck')}).status_code==403

def test_cancelled_shipment_does_not_remove_parked_truck(client):
    d,p,r=fixture(client,'cancelparked');rid=r['id']
    client.post(f'/api/delivery-runs/{rid}/enter-dock',json={})
    s=shipment(client,d['hu'])
    client.post(f'/api/delivery-runs/{rid}/shipments',json={'shipment_id':s['id']})
    assert client.post('/api/shipments/'+str(s['id'])+'/cancel-before-loading',json={}).status_code==200
    assert client.get(f'/api/delivery-runs/{rid}').json()['status']=='AT_DOCK'
    assert client.get('/api/truck-loading/choices?warehouse_id='+str(p['origin_warehouse_id'])).json()[0]['id']==rid
    assert client.post(f'/api/delivery-runs/{rid}/start-loading',json={}).status_code==409
    assert client.post(f'/api/delivery-runs/{rid}/cancel-empty',json={}).status_code==200

def two_trucks(client,suffix):
    data,p,first=fixture(client,suffix)
    assert client.post(f'/api/delivery-runs/{first["id"]}/enter-dock',json={}).status_code==200
    vehicle=client.post('/api/vehicles',json={'vehicle_code':'SECOND','license_plate':'SECOND','vehicle_type':'TRUCK'}).json()
    driver=client.post('/api/drivers',json={'driver_code':'SECOND','first_name':'Second','last_name':'Driver','phone':'0800000000'}).json()
    dock=client.post('/api/loading-docks',json={'warehouse_id':p['origin_warehouse_id'],'dock_name':'Second dock','capacity_vehicle':1,'sequence':2}).json()
    second=client.post('/api/delivery-runs',json={**p,'vehicle_id':vehicle['id'],'driver_id':driver['id'],'loading_dock_id':dock['id']}).json()
    assert client.post(f'/api/delivery-runs/{second["id"]}/enter-dock',json={}).status_code==200
    return data,first['id'],second['id']

def test_reservation_removes_from_other_queue_and_can_transfer_before_scan(client):
    data,a,b=two_trucks(client,'reserve')
    s=shipment(client,data['hu']);sid=s['id']
    for rid in [a,b]:assert sid in {r['id'] for r in client.get(f'/api/delivery-runs/{rid}/loading-queue').json()}
    assert client.post(f'/api/delivery-runs/{a}/shipments',json={'shipment_id':sid}).status_code==200
    assert sid not in {r['id'] for r in client.get(f'/api/delivery-runs/{b}/loading-queue').json()}
    assert client.post(f'/api/delivery-runs/{b}/shipments',json={'shipment_id':sid}).status_code==409
    assert client.post(f'/api/delivery-runs/{a}/shipments/{sid}/remove',json={}).status_code==200
    assert client.post(f'/api/delivery-runs/{b}/shipments',json={'shipment_id':sid}).status_code==200
    assert client.get(f'/api/shipments/{sid}').json()['delivery_run_id']==b

def test_simultaneous_trucks_cannot_reserve_same_shipment(client):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier
    from sqlalchemy import select
    from app import models
    from app.db.session import SessionLocal
    data,a,b=two_trucks(client,'race')
    sid=shipment(client,data['hu'])['id'];barrier=Barrier(2)
    def claim(rid):
        barrier.wait(timeout=10)
        return rid,client.post(f'/api/delivery-runs/{rid}/shipments',json={'shipment_id':sid})
    with ThreadPoolExecutor(max_workers=2) as pool:results=list(pool.map(claim,[a,b]))
    assert sorted(r.status_code for _,r in results)==[200,409]
    winner=next(rid for rid,r in results if r.status_code==200)
    loser=next(rid for rid,r in results if r.status_code==409)
    with SessionLocal() as db:
        links=db.scalars(select(models.DeliveryRunShipment).where(models.DeliveryRunShipment.shipment_id==sid)).all()
        assert len(links)==1 and links[0].delivery_run_id==winner
        assert db.get(models.Shipment,sid).vehicle_id==db.get(models.DeliveryRun,winner).vehicle_id
    assert client.post(f'/api/delivery-runs/{winner}/start-loading',json={}).status_code==200
    assert client.post(f'/api/delivery-runs/{loser}/scan',json={'hu_code':data['hu']}).status_code==409
    assert client.post(f'/api/delivery-runs/{winner}/scan',json={'hu_code':data['hu']}).status_code==200

