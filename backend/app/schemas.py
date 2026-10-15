from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field

class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)

class WarehouseCreate(BaseModel):
    warehouse_code: str = Field(min_length=2, max_length=20)
    warehouse_name: str
    address: str | None = None
class WarehouseOut(WarehouseCreate, ORMModel):
    id: int
    is_active: bool

class StorageProfileCreate(BaseModel):
    profile_code: str
    profile_name: str
    storage_type: str
    unit_load_type: str
    size_class: str
    height_class: str = "H1"
    location_width_mm: int | None = None
    location_height_mm: int | None = None
    location_depth_mm: int | None = None
    max_weight_kg: float | None = None
    default_bay_count: int = Field(gt=0, le=200)
    default_level_count: int = Field(gt=0, le=50)
    positions_per_level: int = Field(gt=0, le=20)
    is_automated: bool = False
class StorageProfileOut(StorageProfileCreate, ORMModel):
    id: int
    is_active: bool

class ZoneCreate(BaseModel):
    warehouse_id: int
    storage_profile_id: int | None = None
    zone_code: str = Field(min_length=1, max_length=8)
    zone_name: str
class ZoneOut(ZoneCreate, ORMModel):
    id: int
    is_active: bool

class RackCreate(BaseModel):
    zone_id: int
    aisle_no: int = Field(gt=0, le=999)
    rack_no: int = Field(gt=0, le=999)
    rack_name: str | None = None
    bay_count: int = Field(gt=0, le=200)
    level_count: int = Field(gt=0, le=50)
    positions_per_level: int = Field(gt=0, le=20)
class RackOut(RackCreate, ORMModel):
    id: int
    is_active: bool
    location_count: int = 0

class LocationOut(ORMModel):
    id: int
    warehouse_id: int
    location_code: str
    location_type: str
    rack_id: int | None
    zone_id: int | None = None
    zone_code: str | None = None
    rack_code: str | None = None
    station_id: int | None = None
    bay_no: int | None
    level_no: int | None
    position_no: int | None
    status: str
    is_active: bool
    hu_code: str | None = None
    sku: str | None = None
    product_name: str | None = None
    quantity: float | None = None
    reserved_quantity: float | None = None
    unit_of_measure: str | None = None

class StationCreate(BaseModel):
    warehouse_id: int
    station_name: str
    station_type: str
    capacity_hu: int = Field(gt=0)
    sequence: int = Field(gt=0)
class StationOut(StationCreate, ORMModel):
    id: int
    station_code: str
    status: str
    is_active: bool

class DockCreate(BaseModel):
    warehouse_id: int
    dock_name: str
    capacity_vehicle: int = Field(gt=0)
    sequence: int = Field(gt=0)
class DockOut(ORMModel):
    id: int
    warehouse_id: int
    dock_code: str
    dock_name: str
    capacity_vehicle: int
    status: str
    is_active: bool

class LoginRequest(BaseModel):
    username: str
    password: str
class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"

class DashboardOut(BaseModel):
    warehouses: int
    zones: int
    racks: int
    total_locations: int
    available_locations: int
    occupied_locations: int
    blocked_locations: int
    stations: int
    loading_docks: int
    utilization_percent: float
    shipments_today: int
    ready_to_load: int
    in_transit: int
    delivered: int
    delivery_failed: int
    vehicles_available: int
    pending_putaway: int
    pending_returns: int
    trucks_waiting: int
    trucks_on_route: int

class ProductCreate(BaseModel):
    sku: str
    barcode: str | None = None
    product_name: str
    description: str | None = None
    size_class: str = "M"
    velocity_class: str | None = "B"
    height_class: str | None = "H2"
    weight_kg: float | None = None
    default_storage_profile_id: int | None = None
class ProductOut(ProductCreate, ORMModel):
    id: int
    is_active: bool

class ReceiveRequest(BaseModel):
    product_id: int
    hu_code: str = Field(default='', max_length=60, pattern=r'^[^/\\]*$')
    auto_hu_code: bool = False
    hu_type: str = "PALLET"
    quantity: float = Field(gt=0)
    unit_of_measure: str = "EA"
    station_id: int
    lot_no: str | None = None
    batch_no: str | None = None
class MoveRequest(BaseModel):
    hu_code: str
    destination_location_id: int

class StationMoveRequest(MoveRequest):
    note: str = Field(default='', max_length=500)

class CheckoutShipmentRequest(BaseModel):
    hu_code: str
    quantity: float = Field(gt=0)
    customer_id: int
    vehicle_id: int | None = None
    driver_id: int | None = None
    loading_dock_id: int | None = None
class SplitHURequest(BaseModel):
    source_hu_code: str
    new_hu_code: str
    quantity: float = Field(gt=0)
    destination_location_id: int
class RecommendRequest(BaseModel):
    hu_code: str

class PendingPutawayOut(BaseModel):
    hu_code: str
    product_id: int
    sku: str
    product_name: str
    quantity: float
    unit_of_measure: str
    inbound_location_code: str
    received_at: datetime

class InventoryOut(BaseModel):
    id: int
    sku: str
    product_name: str
    hu_code: str
    location_code: str | None
    current_node_type: str
    quantity: float
    reserved_quantity: float
    available_quantity: float
    unit_of_measure: str
    lot_no: str | None
    batch_no: str | None
    hu_status: str
    location_type: str | None

class PickFromLocationRequest(BaseModel):
    source_hu_code: str
    quantity: float = Field(gt=0)
    customer_id: int
    checkout_station_id: int
    vehicle_id: int | None = None
    driver_id: int | None = None
    loading_dock_id: int | None = None

class HUOut(BaseModel):
    id: int
    hu_code: str
    hu_type: str
    current_node_type: str
    current_status: str
    current_location_id: int | None
    current_vehicle_id: int | None
    items: list[dict]
    movements: list[dict]

class CustomerCreate(BaseModel):
    customer_code: str
    customer_name: str
    contact_name: str | None = None
    phone: str | None = None
    email: str | None = None
    address_line1: str
    district: str | None = None
    province: str | None = None
    postal_code: str | None = None
    country: str = "Thailand"
class CustomerOut(CustomerCreate, ORMModel):
    id: int
    is_active: bool

class VehicleCreate(BaseModel):
    vehicle_code: str
    license_plate: str
    vehicle_type: str
    max_weight_kg: float | None = None
    max_volume_m3: float | None = None
class VehicleOut(VehicleCreate, ORMModel):
    id: int
    status: str
    is_active: bool

class DriverCreate(BaseModel):
    driver_code: str
    first_name: str
    last_name: str
    phone: str
    license_no: str | None = None
    license_type: str | None = None
class DriverOut(DriverCreate, ORMModel):
    id: int
    status: str
    is_active: bool

class ShipmentLineCreate(BaseModel):
    product_id: int
    handling_unit_id: int | None = None
    planned_quantity: float = Field(gt=0)
    unit_of_measure: str = "EA"
class ShipmentCreate(BaseModel):
    customer_id: int
    origin_warehouse_id: int
    vehicle_id: int | None = None
    driver_id: int | None = None
    loading_dock_id: int | None = None
    planned_departure_at: datetime | None = None
    items: list[ShipmentLineCreate]
class ShipmentAction(BaseModel):
    hu_code: str | None = None
    location_id: int | None = None
    note: str | None = None
    latitude: float | None = None
    longitude: float | None = None

class ShipmentTransportRequest(BaseModel):
    vehicle_id: int
    driver_id: int
    loading_dock_id: int
class DeliveryRequest(ShipmentAction):
    receiver_name: str
    receiver_phone: str | None = None
    delivery_pin_verified: bool = False
class FailureRequest(ShipmentAction):
    failure_reason: str
class ReturnRequest(ShipmentAction):
    return_station_id: int | None = None
class ActiveRequest(BaseModel):
    is_active: bool

class ShipmentOut(BaseModel):
    id: int
    shipment_no: str
    customer_name: str
    destination_name: str
    destination_contact_name: str | None
    destination_phone: str | None
    destination_address: str
    status: str
    vehicle_id: int | None = None
    driver_id: int | None = None
    loading_dock_id: int | None = None
    origin_warehouse_id: int | None = None
    vehicle_code: str | None
    driver_name: str | None
    loading_dock_code: str | None
    delivery_run_id: int | None
    delivery_run_no: str | None
    actual_departure_at: datetime | None
    delivered_at: datetime | None
    items: list[dict]
    tracking: list[dict]
    transactions: list[dict]
    delivery_attempts: list[dict]
    pod: dict | None

class DeliveryRunAction(BaseModel):
    note: str | None = None
    latitude: float | None = None
    longitude: float | None = None

class DeliveryRunCreate(BaseModel):
    origin_warehouse_id: int
    vehicle_id: int
    driver_id: int
    loading_dock_id: int | None = None
    arrived: bool = True

class RunShipmentRequest(BaseModel):
    shipment_id: int

class DeliveryRunDockRequest(DeliveryRunAction):
    loading_dock_id: int | None = None

class DeliveryRunOut(BaseModel):
    id: int
    run_no: str
    status: str
    origin_warehouse_id: int | None = None
    vehicle_id: int | None = None
    driver_id: int | None = None
    loading_dock_id: int | None = None
    vehicle_code: str
    license_plate: str
    driver_name: str
    loading_dock_code: str | None
    planned_departure_at: datetime | None
    truck_arrived_at: datetime | None
    dock_entered_at: datetime | None
    loading_started_at: datetime | None
    ready_to_depart_at: datetime | None
    actual_departure_at: datetime | None
    completed_at: datetime | None
    shipments: list[dict]
    events: list[dict]
