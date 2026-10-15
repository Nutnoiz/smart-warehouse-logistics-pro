from app.tests.test_end_to_end import setup_flow
from sqlalchemy import select
from app.db.session import SessionLocal
from app import models

def view(client,code):
    r=client.get('/api/station-workflow/'+code)
    assert r.status_code==200,r.text
    return r.json()

def move(client,code,kind):
    data=view(client,code)
    loc=next(d for d in data['destinations'] if d['kind']==kind)
    r=client.post('/api/station-workflow/move',json={'hu_code':code,'destination_location_id':loc['id'],'note':'QC / sample'})
    assert r.status_code==200,r.text
    return r.json()

def test_suggested_codes_and_manual_duplicate(client):
    setup_flow(client,'auto')
    station=next(s for s in client.get('/api/stations').json() if s['station_type']=='INBOUND')
    product=client.get('/api/products').json()[0]
    code=client.get('/api/inbound/hu-code').json()['hu_code']
    payload={'product_id':product['id'],'station_id':station['id'],'quantity':1,'hu_code':code,'auto_hu_code':True}
    a=client.post('/api/inbound/receive',json=payload)
    b=client.post('/api/inbound/receive',json=payload)
    assert a.status_code==b.status_code==201
    assert a.json()['hu_code']==code
    assert a.json()['hu_code']!=b.json()['hu_code']
    payload['auto_hu_code']=False
    assert client.post('/api/inbound/receive',json=payload).status_code==409
    payload['hu_code']='CUSTOM-HU-01'
    assert client.post('/api/inbound/receive',json=payload).json()['hu_code']=='CUSTOM-HU-01'

def test_qc_without_shipping_and_station_reversal(client):
    d=setup_flow(client,'qc')
    before=len(client.get('/api/shipments').json())
    assert move(client,d['hu'],'CHECKOUT')['status']=='AT_CHECKOUT'
    assert view(client,d['hu'])['can_ship']
    assert not view(client,d['hu'])['shipment_id']
    move(client,d['hu'],'LOADOUT')
    move(client,d['hu'],'CHECKOUT')
    move(client,d['hu'],'INBOUND')
    assert move(client,d['hu'],'STORAGE')['status']=='STORED'
    assert len(client.get('/api/shipments').json())==before

def test_partial_checkout_shipment_and_restock_remainder(client):
    d=setup_flow(client,'partialqc')
    move(client,d['hu'],'CHECKOUT')
    customer=client.get('/api/customers').json()[0]['id']
    r=client.post('/api/shipments/from-checkout',json={'hu_code':d['hu'],'quantity':23,'customer_id':customer})
    assert r.status_code==201,r.text
    shipment=r.json()
    outbound=shipment['items'][0]['hu_code']
    assert outbound!=d['hu']
    assert view(client,outbound)['reserved']==23
    assert view(client,d['hu'])['quantity']==77
    assert view(client,d['hu'])['reserved']==0
    move(client,d['hu'],'STORAGE')
    assert not any(x['kind']=='STORAGE' for x in view(client,outbound)['destinations'])
    move(client,outbound,'LOADOUT')
    move(client,outbound,'CHECKOUT')
    assert client.post('/api/shipments/'+str(shipment['id'])+'/cancel-before-loading',json={}).status_code==200
    assert view(client,outbound)['reserved']==0
    move(client,outbound,'STORAGE')
    rows=client.get('/api/inventory/search').json()
    assert sum(x['quantity'] for x in rows)==100

def test_checkout_full_shipment_and_duplicate_rejected(client):
    d=setup_flow(client,'fullqc')
    move(client,d['hu'],'CHECKOUT')
    customer=client.get('/api/customers').json()[0]['id']
    payload={'hu_code':d['hu'],'quantity':100,'customer_id':customer}
    r=client.post('/api/shipments/from-checkout',json=payload)
    assert r.status_code==201,r.text
    assert r.json()['items'][0]['hu_code']==d['hu']
    assert client.post('/api/shipments/from-checkout',json=payload).status_code==409
    move(client,d['hu'],'LOADOUT')
    sid=r.json()['id']
    assert client.post('/api/shipments/'+str(sid)+'/ready-to-load',json={}).status_code==200
    move(client,d['hu'],'CHECKOUT')
    assert client.get('/api/shipments/'+str(sid)).json()['status']=='PICKING'

def test_cross_warehouse_blocked_and_permissions(client):
    from app.core.security import create_access_token, hash_password
    d=setup_flow(client,'secureqc')
    wh=client.post('/api/warehouses',json={'warehouse_code':'OTHER','warehouse_name':'Other'}).json()
    station=client.post('/api/stations',json={'warehouse_id':wh['id'],'station_name':'Other QC','station_type':'CHECKOUT','capacity_hu':5,'sequence':1}).json()
    location=next(x for x in client.get('/api/locations?location_type=STATION').json() if x['station_id']==station['id'])
    payload={'hu_code':d['hu'],'destination_location_id':location['id']}
    assert client.post('/api/station-workflow/move',json=payload).status_code==409
    with SessionLocal() as db:
        db.add(models.User(username='viewerqc',password_hash=hash_password('test-password'),role='VIEWER'));db.commit()
    response=client.post('/api/station-workflow/move',json=payload,headers={'Authorization':'Bearer '+create_access_token('viewerqc')})
    assert response.status_code==403
    data=view(client,d['hu'])
    dest=next(x for x in data['destinations'] if x['kind']=='CHECKOUT')
    with SessionLocal() as db:
        db.get(models.Location,dest['id']).status=models.LocationStatus.BLOCKED;db.commit()
    assert client.post('/api/station-workflow/move',json={'hu_code':d['hu'],'destination_location_id':dest['id']}).status_code==409

def test_loading_blocks_reverse_and_cancel(client):
    d=setup_flow(client,'loadingqc')
    move(client,d['hu'],'CHECKOUT')
    customer=client.get('/api/customers').json()[0]['id']
    shipment=client.post('/api/shipments/from-checkout',json={'hu_code':d['hu'],'quantity':100,'customer_id':customer}).json()
    move(client,d['hu'],'LOADOUT')
    with SessionLocal() as db:
        db.get(models.Shipment,shipment['id']).status='LOADING';db.commit()
    assert not view(client,d['hu'])['destinations']
    assert client.post('/api/shipments/'+str(shipment['id'])+'/cancel-before-loading',json={}).status_code==409

