from app import models
from app.db.session import SessionLocal
from app.core.security import hash_password

def create_master(client):
    wh = client.post("/api/warehouses", json={"warehouse_code":"WH01", "warehouse_name":"Test warehouse"}).json()
    profile = client.post("/api/storage-profiles", json={"profile_code":"PALLET_STANDARD", "profile_name":"Pallet", "storage_type":"PALLET_RACK", "unit_load_type":"PALLET", "size_class":"L", "default_bay_count":2, "default_level_count":2, "positions_per_level":2}).json()
    zone = client.post("/api/zones", json={"warehouse_id":wh["id"], "storage_profile_id":profile["id"], "zone_code":"L", "zone_name":"Large"}).json()
    return wh, zone

def test_rack_generates_single_depth_locations(client):
    _, zone = create_master(client)
    response = client.post("/api/racks", json={"zone_id":zone["id"], "aisle_no":3, "rack_no":2, "rack_name":"R2", "bay_count":2, "level_count":2, "positions_per_level":2})
    assert response.status_code == 201
    locations = client.get(f"/api/racks/{response.json()['id']}/locations").json()
    assert len(locations) == 8
    assert locations[0]["location_code"].startswith("WH01-L-A03-R02-B001-L02-P01")
    assert all("depth" not in location for location in locations)

def test_station_is_a_tracked_location(client):
    wh, _ = create_master(client)
    station = client.post("/api/stations", json={"warehouse_id":wh["id"], "station_name":"Inbound 1", "station_type":"INBOUND", "capacity_hu":10, "sequence":1})
    assert station.status_code == 201
    assert station.json()["station_code"] == "WH01-ST-INB-01"
    locations = client.get("/api/locations?location_type=STATION").json()
    assert locations == [{**locations[0]}]
    assert locations[0]["location_code"] == station.json()["station_code"]

def test_duplicate_rack_is_rejected_without_partial_locations(client):
    _, zone = create_master(client)
    payload = {"zone_id":zone["id"], "aisle_no":1, "rack_no":1, "bay_count":2, "level_count":1, "positions_per_level":1}
    assert client.post("/api/racks", json=payload).status_code == 201
    assert client.post("/api/racks", json=payload).status_code == 409
    assert len(client.get("/api/locations?location_type=STORAGE").json()) == 2

def test_login_foundation(client):
    db = SessionLocal(); db.add(models.User(username="admin", password_hash=hash_password("secret"))); db.commit(); db.close()
    good = client.post("/api/auth/login", json={"username":"admin", "password":"secret"})
    assert good.status_code == 200 and good.json()["access_token"]
    assert client.post("/api/auth/login", json={"username":"admin", "password":"bad"}).status_code == 401

def test_protected_api_rejects_missing_token():
    from fastapi.testclient import TestClient
    from app.main import app
    assert TestClient(app).get("/api/dashboard").status_code == 401

def test_cors_preflight_does_not_require_token():
    from fastapi.testclient import TestClient
    from app.main import app
    response=TestClient(app).options("/api/dashboard",headers={"Origin":"http://localhost:5180","Access-Control-Request-Method":"GET"})
    assert response.status_code==200

def test_putaway_allows_manual_selection_only_within_product_profile(client):
    wh, matching_zone = create_master(client)
    matching_rack = client.post("/api/racks", json={"zone_id":matching_zone["id"],"aisle_no":1,"rack_no":1,"bay_count":2,"level_count":1,"positions_per_level":1}).json()
    matching_locations = client.get(f"/api/racks/{matching_rack['id']}/locations").json()
    other_profile = client.post("/api/storage-profiles", json={"profile_code":"SMALL_BIN","profile_name":"Small bin","storage_type":"SHELVING","unit_load_type":"TOTE","size_class":"S","default_bay_count":1,"default_level_count":1,"positions_per_level":1}).json()
    other_zone = client.post("/api/zones", json={"warehouse_id":wh["id"],"storage_profile_id":other_profile["id"],"zone_code":"S","zone_name":"Small"}).json()
    other_rack = client.post("/api/racks", json={"zone_id":other_zone["id"],"aisle_no":2,"rack_no":1,"bay_count":1,"level_count":1,"positions_per_level":1}).json()
    incompatible = client.get(f"/api/racks/{other_rack['id']}/locations").json()[0]
    inbound = client.post("/api/stations", json={"warehouse_id":wh["id"],"station_name":"Inbound","station_type":"INBOUND","capacity_hu":10,"sequence":1}).json()
    product = client.post("/api/products", json={"sku":"SKU-MANUAL","product_name":"Manual putaway","size_class":"L","default_storage_profile_id":matching_zone["storage_profile_id"]}).json()
    assert client.post("/api/inbound/receive", json={"product_id":product["id"],"hu_code":"HU-MANUAL","quantity":10,"station_id":inbound["id"]}).status_code == 201

    pending = client.get("/api/putaway/pending")
    assert pending.status_code == 200
    assert pending.json()[0]["hu_code"] == "HU-MANUAL"
    assert pending.json()[0]["inbound_location_code"] == inbound["station_code"]

    options = client.post("/api/putaway/options", json={"hu_code":"HU-MANUAL"})
    assert options.status_code == 200
    assert [item["id"] for item in options.json()] == [item["id"] for item in matching_locations]
    assert options.json()[0]["zone_code"] == "L"
    assert options.json()[0]["rack_code"] == "A01-R01"
    rejected = client.post("/api/putaway/confirm", json={"hu_code":"HU-MANUAL","destination_location_id":incompatible["id"]})
    assert rejected.status_code == 409
    selected = matching_locations[1]
    assert client.post("/api/putaway/confirm", json={"hu_code":"HU-MANUAL","destination_location_id":selected["id"]}).status_code == 200
    assert client.get("/api/putaway/pending").json() == []
