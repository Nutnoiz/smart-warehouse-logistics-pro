"""Seed reviewable intermediate stages through the same API workflow as operators."""
from fastapi.testclient import TestClient
from sqlalchemy import select
from app.main import app
from app import models
from app.db.session import SessionLocal
from app.core.config import settings
from app.core.security import create_access_token


def showcase():
    if not settings.demo_mode:
        return
    with SessionLocal() as db:
        admin=db.scalar(select(models.User).where(models.User.role=='ADMIN',models.User.is_active.is_(True)))
        if not admin:return
        token=create_access_token(admin.username,admin.token_version)
    with TestClient(app,headers={'Authorization':f'Bearer {token}'}) as client:
        def get(path):
            response=client.get('/api'+path);response.raise_for_status();return response.json()
        def post(path,payload={}):
            response=client.post('/api'+path,json=payload)
            if response.status_code>=400:raise RuntimeError(f'Demo workflow {path}: {response.text}')
            return response.json()
        products=get('/products');stations=get('/stations');locations=get('/locations?location_type=STATION')
        vehicles=get('/vehicles');drivers=get('/drivers');customers=get('/customers');docks=get('/loading-docks')
        if not products or len(vehicles)<3 or not drivers or not customers or not docks:return
        product=products[0]
        inbound=next(s for s in stations if s['station_type']=='INBOUND')
        checkout=next(s for s in stations if s['station_type']=='CHECKOUT')
        loadout=next(s for s in stations if s['station_type']=='LOADOUT')
        loadout_location=next(l for l in locations if l['station_id']==loadout['id'])
        existing={r['hu_code'] for r in get('/inventory/search')}
        on_route=[]
        for stage,quantity,vehicle_index in [('INBOUND',48,0),('CHECKOUT',24,0),('LOADOUT',36,1),('ROUTE-A',18,2),('ROUTE-B',12,2)]:
            hu=f'DEMO-PRO-{stage}'
            if hu in existing:continue
            post('/inbound/receive',{'product_id':product['id'],'hu_code':hu,'quantity':quantity,'station_id':inbound['id'],'hu_type':'BOX','lot_no':'DEMO-PRO'})
            if stage=='INBOUND':continue
            destination=post('/putaway/options',{'hu_code':hu})[0]
            post('/putaway/confirm',{'hu_code':hu,'destination_location_id':destination['id']})
            shipment=post('/outbound-picks',{'source_hu_code':hu,'quantity':quantity,'customer_id':customers[vehicle_index%len(customers)]['id'],
                'checkout_station_id':checkout['id'],'vehicle_id':vehicles[vehicle_index]['id'],'driver_id':drivers[vehicle_index%len(drivers)]['id'],'loading_dock_id':docks[0]['id']})
            if stage=='CHECKOUT':continue
            shipment=post(f"/shipments/{shipment['id']}/checkout",{'hu_code':hu,'location_id':loadout_location['id']})
            post(f"/shipments/{shipment['id']}/ready-to-load")
            if stage.startswith('ROUTE'):on_route.append((shipment['id'],shipment['delivery_run_id'],hu))
        if on_route:
            rid=on_route[0][1]
            post(f'/delivery-runs/{rid}/check-in')
            post(f'/delivery-runs/{rid}/enter-dock',{'loading_dock_id':docks[0]['id']})
            post(f'/delivery-runs/{rid}/start-loading')
            for sid,_,hu in on_route:post(f'/shipments/{sid}/load-hu',{'hu_code':hu})
            post(f'/delivery-runs/{rid}/complete-loading')
            post(f'/delivery-runs/{rid}/depart')
            post(f'/delivery-runs/{rid}/in-transit')


if __name__=='__main__':showcase()
