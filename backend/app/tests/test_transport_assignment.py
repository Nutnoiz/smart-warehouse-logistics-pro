from app.tests.test_end_to_end import setup_flow
from app.tests.test_station_workflow import move

def checkout_shipment(client,suffix='deferred'):
    data=setup_flow(client,suffix)
    assert client.post('/api/shipments/'+str(data['shipment']['id'])+'/cancel-before-loading',json={}).status_code==200
    move(client,data['hu'],'CHECKOUT')
    response=client.post('/api/shipments/from-checkout',json={'hu_code':data['hu'],'quantity':100,'customer_id':client.get('/api/customers').json()[0]['id']})
    assert response.status_code==201,response.text
    return data,response.json()

def transport(client):
    return {'vehicle_id':client.get('/api/vehicles').json()[0]['id'],'driver_id':client.get('/api/drivers').json()[0]['id'],'loading_dock_id':client.get('/api/loading-docks').json()[0]['id']}

def test_deferred_transport_is_reserved_and_loaded_only_in_run(client):
    data,shipment=checkout_shipment(client,'assign');sid=shipment['id']
    move(client,data['hu'],'LOADOUT')
    assert client.post(f'/api/shipments/{sid}/ready-to-load',json={}).status_code==200
    payload=transport(client)
    for action,body in [('transport',payload),('start-loading',{}),('load-hu',{'hu_code':data['hu']}),('complete-loading',{}),('depart',{})]:
        response=client.post(f'/api/shipments/{sid}/{action}',json=body)
        assert response.status_code==409,response.text
        assert 'รอบรถ' in response.json()['detail']
    run=client.post('/api/delivery-runs',json={**payload,'origin_warehouse_id':shipment['origin_warehouse_id'],'arrived':True})
    assert run.status_code==201,run.text
    rid=run.json()['id']
    assert client.post(f'/api/delivery-runs/{rid}/enter-dock',json={}).status_code==200
    assert client.post(f'/api/delivery-runs/{rid}/shipments',json={'shipment_id':sid}).status_code==200
    assert client.get(f'/api/station-workflow/{data["hu"]}').json()['delivery_run_id']==rid
    for action,body in [('start-loading',{}),('scan',{'hu_code':data['hu']}),('complete-loading',{}),('depart',{})]:
        response=client.post(f'/api/delivery-runs/{rid}/{action}',json=body)
        assert response.status_code==200,response.text
    assert client.get(f'/api/shipments/{sid}').json()['status']=='DEPARTED'

def test_run_registration_rejects_cross_warehouse_and_invalid_resources(client):
    _,shipment=checkout_shipment(client,'assignsafe');payload=transport(client)
    wh=client.post('/api/warehouses',json={'warehouse_code':'OTHER','warehouse_name':'Other'}).json()
    dock=client.post('/api/loading-docks',json={'warehouse_id':wh['id'],'dock_name':'Other dock','capacity_vehicle':1,'sequence':1}).json()
    body={**payload,'origin_warehouse_id':shipment['origin_warehouse_id'],'arrived':True}
    assert client.post('/api/delivery-runs',json={**body,'loading_dock_id':dock['id']}).status_code==422
    assert client.post('/api/delivery-runs',json={**body,'driver_id':999999}).status_code==422
    result=client.get(f'/api/shipments/{shipment["id"]}').json()
    assert result['vehicle_id'] is None and result['delivery_run_id'] is None

def test_existing_run_missing_dock_is_completed_in_run_workspace(client):
    _,shipment=checkout_shipment(client,'assigndock');payload=transport(client)
    run=client.post('/api/delivery-runs',json={**payload,'loading_dock_id':None,'origin_warehouse_id':shipment['origin_warehouse_id'],'arrived':True}).json()
    response=client.post(f'/api/delivery-runs/{run["id"]}/enter-dock',json={'loading_dock_id':payload['loading_dock_id']})
    assert response.status_code==200,response.text
    assert response.json()['loading_dock_code']
