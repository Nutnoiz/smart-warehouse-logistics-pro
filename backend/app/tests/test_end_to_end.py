def setup_flow(client, suffix="1"):
    wh=client.post("/api/warehouses",json={"warehouse_code":f"WH{suffix}","warehouse_name":"Flow warehouse"}).json()
    profile=client.post("/api/storage-profiles",json={"profile_code":f"PALLET_{suffix}","profile_name":"Pallet","storage_type":"PALLET_RACK","unit_load_type":"PALLET","size_class":"L","default_bay_count":2,"default_level_count":1,"positions_per_level":1}).json()
    zone=client.post("/api/zones",json={"warehouse_id":wh["id"],"storage_profile_id":profile["id"],"zone_code":"L","zone_name":"Large"}).json()
    rack=client.post("/api/racks",json={"zone_id":zone["id"],"aisle_no":1,"rack_no":1,"bay_count":2,"level_count":1,"positions_per_level":1}).json()
    storage=client.get(f"/api/racks/{rack['id']}/locations").json()[0]
    return_zone=client.post("/api/zones",json={"warehouse_id":wh["id"],"zone_code":"RTN","zone_name":"Return Hold"}).json()
    return_rack=client.post("/api/racks",json={"zone_id":return_zone["id"],"aisle_no":90,"rack_no":1,"bay_count":2,"level_count":1,"positions_per_level":1}).json()
    return_storage=client.get(f"/api/racks/{return_rack['id']}/locations").json()[0]
    inbound=client.post("/api/stations",json={"warehouse_id":wh["id"],"station_name":"Inbound","station_type":"INBOUND","capacity_hu":10,"sequence":1}).json()
    checkout=client.post("/api/stations",json={"warehouse_id":wh["id"],"station_name":"Checkout","station_type":"CHECKOUT","capacity_hu":10,"sequence":1}).json()
    loadout=client.post("/api/stations",json={"warehouse_id":wh["id"],"station_name":"Loadout","station_type":"LOADOUT","capacity_hu":10,"sequence":1}).json()
    returned=client.post("/api/stations",json={"warehouse_id":wh["id"],"station_name":"Return","station_type":"RETURN","capacity_hu":10,"sequence":1}).json()
    dock=client.post("/api/loading-docks",json={"warehouse_id":wh["id"],"dock_name":"Dock","capacity_vehicle":1,"sequence":1}).json()
    product=client.post("/api/products",json={"sku":f"SKU-{suffix}","product_name":"Flow product","size_class":"L","default_storage_profile_id":profile["id"]}).json()
    customer=client.post("/api/customers",json={"customer_code":f"CUS-{suffix}","customer_name":"Customer","address_line1":"Bangkok"}).json()
    vehicle=client.post("/api/vehicles",json={"vehicle_code":f"TRUCK-{suffix}","license_plate":f"PLATE-{suffix}","vehicle_type":"6_WHEEL"}).json()
    driver=client.post("/api/drivers",json={"driver_code":f"DRV-{suffix}","first_name":"Somchai","last_name":"Test","phone":"0800000000"}).json()
    hu_code=f"HU-{suffix}"
    assert client.post("/api/inbound/receive",json={"product_id":product["id"],"hu_code":hu_code,"hu_type":"PALLET","quantity":100,"station_id":inbound["id"]}).status_code==201
    assert client.post("/api/putaway/confirm",json={"hu_code":hu_code,"destination_location_id":storage["id"]}).status_code==200
    shipment=client.post("/api/shipments",json={"customer_id":customer["id"],"origin_warehouse_id":wh["id"],"vehicle_id":vehicle["id"],"driver_id":driver["id"],"loading_dock_id":dock["id"],"items":[{"product_id":product["id"],"planned_quantity":100}]}).json()
    return {"shipment":shipment,"hu":hu_code,"checkout":checkout,"loadout":loadout,"returned":returned,"return_storage":return_storage}

def prepare_loaded(client, data):
    sid=data["shipment"]["id"]
    assert client.post(f"/api/shipments/{sid}/allocate").json()["status"]=="PICKING"
    locations=client.get("/api/locations?location_type=STATION").json()
    checkout_loc=next(x for x in locations if x["station_id"]==data["checkout"]["id"])
    loadout_loc=next(x for x in locations if x["station_id"]==data["loadout"]["id"])
    assert client.post(f"/api/shipments/{sid}/retrieve",json={"hu_code":data["hu"],"location_id":checkout_loc["id"]}).status_code==200
    assert client.post(f"/api/shipments/{sid}/ready-to-load").status_code==409
    assert client.post(f"/api/shipments/{sid}/checkout",json={"hu_code":data["hu"],"location_id":loadout_loc["id"]}).status_code==200
    assert client.post(f"/api/shipments/{sid}/ready-to-load").json()["status"]=="READY_TO_LOAD"
    rid=data['shipment']['delivery_run_id']
    for action in ['check-in','enter-dock','start-loading']:
        assert client.post(f'/api/delivery-runs/{rid}/{action}',json={}).status_code==200
    assert client.post(f'/api/delivery-runs/{rid}/scan',json={'hu_code':data['hu']}).status_code==200
    assert client.post(f'/api/delivery-runs/{rid}/complete-loading',json={}).json()['status']=='READY_TO_DEPART'
    assert client.post(f'/api/delivery-runs/{rid}/depart',json={}).json()['status']=='DEPARTED'
    assert client.post(f"/api/shipments/{sid}/in-transit",json={}).json()["status"]=="IN_TRANSIT"
    assert client.post(f"/api/shipments/{sid}/arrive",json={}).json()["status"]=="ARRIVED"
    return sid

def test_complete_delivery_keeps_custody_and_history_consistent(client):
    data=setup_flow(client,"1");sid=prepare_loaded(client,data)
    delivered=client.post(f"/api/shipments/{sid}/deliver",json={"receiver_name":"Customer Receiver","delivery_pin_verified":True}).json()
    assert delivered["status"]=="DELIVERED"
    hu=client.get(f"/api/handling-units/{data['hu']}").json()
    assert hu["current_node_type"]=="CUSTOMER" and hu["current_location_id"] is None
    assert [x["movement_type"] for x in hu["movements"]][:5]==["DELIVER","LOAD","CHECKOUT","RETRIEVE","PUTAWAY"]
    assert client.get(f"/api/shipments/{sid}/pod").json()["delivery_pin_verified"] is True

def test_delivered_import_can_backfill_pod_once(client):
    data=setup_flow(client,"POD");sid=prepare_loaded(client,data)
    client.post(f"/api/shipments/{sid}/deliver",json={"receiver_name":"Original Receiver"})
    # Simulate a delivered record imported without its separate POD row.
    from app.db.session import SessionLocal
    from app import models
    from sqlalchemy import delete
    with SessionLocal() as db:
        db.execute(delete(models.ProofOfDelivery).where(models.ProofOfDelivery.shipment_id==sid));db.commit()
    response=client.post(f"/api/shipments/{sid}/pod",json={"receiver_name":"Imported Receiver","receiver_phone":"0812345678","delivery_pin_verified":True})
    assert response.status_code==200 and response.json()["pod"]["receiver_name"]=="Imported Receiver"
    assert client.post(f"/api/shipments/{sid}/pod",json={"receiver_name":"Duplicate"}).status_code==409

def test_failed_delivery_returns_to_hold(client):
    data=setup_flow(client,"2");sid=prepare_loaded(client,data)
    assert client.post(f"/api/shipments/{sid}/delivery-failed",json={"failure_reason":"CUSTOMER_CLOSED"}).json()["status"]=="DELIVERY_FAILED"
    assert client.post(f"/api/shipments/{sid}/return",json={}).json()["status"]=="RETURNING"
    result=client.post(f"/api/shipments/{sid}/return-complete",json={"return_station_id":data["returned"]["id"]}).json()
    assert result["status"]=="RETURNED"
    hu=client.get(f"/api/handling-units/{data['hu']}").json()
    assert hu["current_status"]=="RETURN_HOLD" and hu["current_node_type"]=="WAREHOUSE_LOCATION"
    pending=client.get("/api/returns/pending").json()
    assert pending[0]["hu_code"]==data["hu"]
    options=client.post("/api/returns/putaway-options",json={"hu_code":data["hu"]}).json()
    assert options[0]["zone_code"]=="RTN" and {x["zone_code"] for x in options}=={"RTN","L"}
    stored=client.post("/api/returns/putaway",json={"hu_code":data["hu"],"destination_location_id":data["return_storage"]["id"]}).json()
    assert stored["status"]=="RETURN_STORED"
    inventory=client.get(f"/api/inventory/search?q={data['hu']}").json()[0]
    assert inventory["location_code"]==data["return_storage"]["location_code"] and inventory["reserved_quantity"]==100

def test_illegal_transition_is_rejected(client):
    data=setup_flow(client,"3");sid=data["shipment"]["id"]
    assert client.post(f"/api/shipments/{sid}/depart",json={}).status_code==409

def test_split_hu_preserves_total_quantity(client):
    data=setup_flow(client,"4")
    locations=client.get("/api/locations?location_type=STORAGE").json()
    free=next(x for x in locations if x["status"]=="AVAILABLE")
    response=client.post("/api/handling-units/split",json={"source_hu_code":data["hu"],"new_hu_code":"HU-4-SPLIT","quantity":40,"destination_location_id":free["id"]})
    assert response.status_code==200
    rows=client.get("/api/inventory/search?q=SKU-4").json()
    assert sorted(x["quantity"] for x in rows)==[40,60]

def test_live_warehouse_map_reports_real_hu_and_location(client):
    data=setup_flow(client,"5")
    live=client.get("/api/warehouse-map/live").json()
    rack=live["zones"][0]["racks"][0]
    assert rack["occupied"]==1 and rack["hu_count"]==1
    assert rack["products"]==[{"sku":"SKU-5","quantity":100.0}]
    locations=client.get(f"/api/racks/{rack['id']}/locations").json()
    occupied=next(x for x in locations if x["status"]=="OCCUPIED")
    assert occupied["hu_code"]==data["hu"] and occupied["sku"]=="SKU-5"

def test_live_warehouse_map_orders_zones_from_small_to_large(client):
    wh=client.post("/api/warehouses",json={"warehouse_code":"WH-SIZE","warehouse_name":"Size order"}).json()
    for size in ("XL","L","S","M"):
        profile=client.post("/api/storage-profiles",json={"profile_code":f"PROFILE-{size}","profile_name":size,"storage_type":"RACK","unit_load_type":"PALLET","size_class":size,"default_bay_count":1,"default_level_count":1,"positions_per_level":1}).json()
        client.post("/api/zones",json={"warehouse_id":wh["id"],"storage_profile_id":profile["id"],"zone_code":size,"zone_name":size})
    live=client.get(f"/api/warehouse-map/live?warehouse_id={wh['id']}").json()
    assert [zone["zone_code"] for zone in live["zones"]]==["S","M","L","XL"]

def test_station_overview_lists_multiple_hus_at_one_station(client):
    data=setup_flow(client,"6")
    stations=client.get("/api/stations").json()
    inbound=next(x for x in stations if x["station_type"]=="INBOUND")
    locations=client.get("/api/locations?location_type=STATION").json()
    checkout_location=next(x for x in locations if x["station_id"]==data["checkout"]["id"])
    product_id=data["shipment"]["items"][0]["product_id"]
    assert client.post("/api/inbound/receive",json={"product_id":product_id,"hu_code":"HU-6-B","quantity":25,"station_id":inbound["id"]}).status_code==201
    assert client.post('/api/retrieval/confirm',json={'hu_code':data['hu'],'location_id':checkout_location['id']}).status_code==200
    option=client.post('/api/putaway/options',json={'hu_code':'HU-6-B'}).json()[0]
    assert client.post('/api/putaway/confirm',json={'hu_code':'HU-6-B','destination_location_id':option['id']}).status_code==200
    assert client.post('/api/retrieval/confirm',json={'hu_code':'HU-6-B','location_id':checkout_location['id']}).status_code==200
    overview=client.get("/api/stations/overview").json()
    checkout=next(x for x in overview if x["id"]==data["checkout"]["id"])
    assert checkout["hu_count"]==2
    assert {item["hu_code"] for item in checkout["items"]}=={data["hu"],"HU-6-B"}

def outbound_pick_payload(client,data,quantity):
    return {"source_hu_code":data["hu"],"quantity":quantity,"customer_id":client.get("/api/customers").json()[0]["id"],"checkout_station_id":data["checkout"]["id"],"vehicle_id":client.get("/api/vehicles").json()[0]["id"],"driver_id":client.get("/api/drivers").json()[0]["id"],"loading_dock_id":client.get("/api/loading-docks").json()[0]["id"]}

def test_partial_pick_creates_outbound_hu_and_restocks_remainder(client):
    data=setup_flow(client,"7")
    response=client.post("/api/outbound-picks",json=outbound_pick_payload(client,data,30))
    assert response.status_code==201
    shipment=response.json()
    assert shipment["status"]=="PICKING"
    assert shipment["items"][0]["hu_code"].startswith("HU-OUT-")
    assert shipment["items"][0]["current_station_type"]=="CHECKOUT"
    inventory=client.get("/api/inventory/search?q=SKU-7").json()
    original=next(x for x in inventory if x["hu_code"]==data["hu"])
    outbound=next(x for x in inventory if x["hu_code"]!=data["hu"])
    assert original["quantity"]==70 and original["location_type"]=="STORAGE" and original["hu_status"]=="STORED"
    assert outbound["quantity"]==30 and outbound["reserved_quantity"]==30 and outbound["location_type"]=="STATION"
    movements=client.get(f"/api/handling-units/{data['hu']}").json()["movements"]
    assert [x["movement_type"] for x in movements[:2]]==["RESTOCK","RETRIEVE"]

def test_full_hu_pick_moves_original_hu_to_checkout(client):
    data=setup_flow(client,"8")
    shipment=client.post("/api/outbound-picks",json=outbound_pick_payload(client,data,100)).json()
    assert shipment["status"]=="PICKING"
    assert shipment["items"][0]["hu_code"]==data["hu"]
    assert shipment["items"][0]["current_station_type"]=="CHECKOUT"
    row=client.get("/api/inventory/search?q=SKU-8").json()[0]
    assert row["quantity"]==100 and row["reserved_quantity"]==100 and row["location_type"]=="STATION"

def test_same_vehicle_shipments_share_one_delivery_run(client):
    data=setup_flow(client,"9")
    first=data["shipment"]
    customer=client.get("/api/customers").json()[0]
    vehicle=client.get("/api/vehicles").json()[0]
    driver=client.get("/api/drivers").json()[0]
    dock=client.get("/api/loading-docks").json()[0]
    second=client.post("/api/shipments",json={"customer_id":customer["id"],"origin_warehouse_id":1,"vehicle_id":vehicle["id"],"driver_id":driver["id"],"loading_dock_id":dock["id"],"items":[{"product_id":first["items"][0]["product_id"],"planned_quantity":100}]}).json()
    assert first["delivery_run_id"]==second["delivery_run_id"]
    runs=client.get("/api/delivery-runs?active_only=true").json()
    assert len(runs)==1 and len(runs[0]["shipments"])==2

def test_delivery_run_checkin_dock_loading_and_departure(client):
    data=setup_flow(client,"10");shipment=data["shipment"];sid=shipment["id"];run_id=shipment["delivery_run_id"]
    assert client.post(f"/api/shipments/{sid}/allocate").json()["status"]=="PICKING"
    locations=client.get("/api/locations?location_type=STATION").json()
    checkout_loc=next(x for x in locations if x["station_id"]==data["checkout"]["id"])
    loadout_loc=next(x for x in locations if x["station_id"]==data["loadout"]["id"])
    assert client.post(f"/api/shipments/{sid}/retrieve",json={"hu_code":data["hu"],"location_id":checkout_loc["id"]}).status_code==200
    assert client.post(f"/api/shipments/{sid}/checkout",json={"hu_code":data["hu"],"location_id":loadout_loc["id"]}).status_code==200
    assert client.post(f"/api/shipments/{sid}/ready-to-load").json()["status"]=="READY_TO_LOAD"
    assert client.post(f"/api/delivery-runs/{run_id}/check-in",json={}).json()["status"]=="WAITING_DOCK"
    assert client.post(f"/api/delivery-runs/{run_id}/enter-dock",json={}).json()["status"]=="AT_DOCK"
    assert client.post(f"/api/delivery-runs/{run_id}/start-loading",json={}).json()["status"]=="LOADING"
    assert client.post(f"/api/delivery-runs/{run_id}/scan",json={"hu_code":data["hu"]}).status_code==200
    assert client.post(f"/api/delivery-runs/{run_id}/complete-loading",json={}).json()["status"]=="READY_TO_DEPART"
    assert client.post(f"/api/delivery-runs/{run_id}/depart",json={}).json()["status"]=="DEPARTED"
    run=client.post(f"/api/delivery-runs/{run_id}/in-transit",json={}).json()
    assert run["status"]=="IN_TRANSIT" and run["shipments"][0]["status"]=="IN_TRANSIT"
