import enum
from datetime import datetime
from sqlalchemy import Boolean, CheckConstraint, Date, DateTime, Enum, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base

class StationType(str, enum.Enum):
    INBOUND = "INBOUND"
    CHECKOUT = "CHECKOUT"
    LOADOUT = "LOADOUT"
    OUTBOUND = "OUTBOUND"
    RETURN = "RETURN"

class LocationStatus(str, enum.Enum):
    AVAILABLE = "AVAILABLE"
    OCCUPIED = "OCCUPIED"
    RESERVED = "RESERVED"
    BLOCKED = "BLOCKED"

class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

class Warehouse(TimestampMixin, Base):
    __tablename__ = "warehouses"
    id: Mapped[int] = mapped_column(primary_key=True)
    warehouse_code: Mapped[str] = mapped_column(String(20), unique=True, index=True)
    warehouse_name: Mapped[str] = mapped_column(String(120))
    address: Mapped[str | None] = mapped_column(String(255))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    zones: Mapped[list["Zone"]] = relationship(back_populates="warehouse", cascade="all, delete-orphan")

class StorageProfile(TimestampMixin, Base):
    __tablename__ = "storage_profiles"
    id: Mapped[int] = mapped_column(primary_key=True)
    profile_code: Mapped[str] = mapped_column(String(40), unique=True)
    profile_name: Mapped[str] = mapped_column(String(120))
    storage_type: Mapped[str] = mapped_column(String(40))
    unit_load_type: Mapped[str] = mapped_column(String(40))
    size_class: Mapped[str] = mapped_column(String(4))
    height_class: Mapped[str] = mapped_column(String(4), default="H1")
    location_width_mm: Mapped[int | None]
    location_height_mm: Mapped[int | None]
    location_depth_mm: Mapped[int | None]
    max_weight_kg: Mapped[float | None] = mapped_column(Numeric(12, 2))
    default_bay_count: Mapped[int] = mapped_column(default=1)
    default_level_count: Mapped[int] = mapped_column(default=1)
    positions_per_level: Mapped[int] = mapped_column(default=1)
    is_automated: Mapped[bool] = mapped_column(Boolean, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

class Zone(TimestampMixin, Base):
    __tablename__ = "zones"
    __table_args__ = (UniqueConstraint("warehouse_id", "zone_code"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    warehouse_id: Mapped[int] = mapped_column(ForeignKey("warehouses.id"))
    storage_profile_id: Mapped[int | None] = mapped_column(ForeignKey("storage_profiles.id"))
    zone_code: Mapped[str] = mapped_column(String(8))
    zone_name: Mapped[str] = mapped_column(String(120))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    warehouse: Mapped[Warehouse] = relationship(back_populates="zones")
    storage_profile: Mapped[StorageProfile | None] = relationship()
    racks: Mapped[list["Rack"]] = relationship(back_populates="zone", cascade="all, delete-orphan")

class Rack(TimestampMixin, Base):
    __tablename__ = "racks"
    __table_args__ = (UniqueConstraint("zone_id", "aisle_no", "rack_no"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    zone_id: Mapped[int] = mapped_column(ForeignKey("zones.id"))
    aisle_no: Mapped[int]
    rack_no: Mapped[int]
    rack_name: Mapped[str | None] = mapped_column(String(120))
    bay_count: Mapped[int]
    level_count: Mapped[int]
    positions_per_level: Mapped[int]
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    zone: Mapped[Zone] = relationship(back_populates="racks")
    locations: Mapped[list["Location"]] = relationship(back_populates="rack", cascade="all, delete-orphan")

class Station(TimestampMixin, Base):
    __tablename__ = "stations"
    id: Mapped[int] = mapped_column(primary_key=True)
    warehouse_id: Mapped[int] = mapped_column(ForeignKey("warehouses.id"))
    station_code: Mapped[str] = mapped_column(String(40), unique=True)
    station_name: Mapped[str] = mapped_column(String(120))
    station_type: Mapped[StationType] = mapped_column(Enum(StationType, native_enum=False))
    capacity_hu: Mapped[int] = mapped_column(default=1)
    sequence: Mapped[int] = mapped_column(default=1)
    status: Mapped[LocationStatus] = mapped_column(Enum(LocationStatus, native_enum=False), default=LocationStatus.AVAILABLE)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    location: Mapped["Location"] = relationship(back_populates="station", uselist=False)

class Location(TimestampMixin, Base):
    __tablename__ = "locations"
    id: Mapped[int] = mapped_column(primary_key=True)
    warehouse_id: Mapped[int] = mapped_column(ForeignKey("warehouses.id"))
    location_code: Mapped[str] = mapped_column(String(80), unique=True, index=True)
    location_type: Mapped[str] = mapped_column(String(16))
    zone_id: Mapped[int | None] = mapped_column(ForeignKey("zones.id"))
    rack_id: Mapped[int | None] = mapped_column(ForeignKey("racks.id"))
    bay_no: Mapped[int | None]
    level_no: Mapped[int | None]
    position_no: Mapped[int | None]
    station_id: Mapped[int | None] = mapped_column(ForeignKey("stations.id"), unique=True)
    status: Mapped[LocationStatus] = mapped_column(Enum(LocationStatus, native_enum=False), default=LocationStatus.AVAILABLE)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    rack: Mapped[Rack | None] = relationship(back_populates="locations")
    station: Mapped[Station | None] = relationship(back_populates="location")

class LoadingDock(TimestampMixin, Base):
    __tablename__ = "loading_docks"
    id: Mapped[int] = mapped_column(primary_key=True)
    warehouse_id: Mapped[int] = mapped_column(ForeignKey("warehouses.id"))
    dock_code: Mapped[str] = mapped_column(String(40), unique=True)
    dock_name: Mapped[str] = mapped_column(String(120))
    capacity_vehicle: Mapped[int] = mapped_column(default=1)
    status: Mapped[str] = mapped_column(String(20), default="AVAILABLE")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

class User(TimestampMixin, Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(60), unique=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(40), default="ADMIN")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    token_version: Mapped[int] = mapped_column(Integer, default=0, server_default="0")

class Product(TimestampMixin, Base):
    __tablename__ = "products"
    id: Mapped[int] = mapped_column(primary_key=True)
    sku: Mapped[str] = mapped_column(String(60), unique=True, index=True)
    barcode: Mapped[str | None] = mapped_column(String(100), unique=True)
    product_name: Mapped[str] = mapped_column(String(160))
    description: Mapped[str | None] = mapped_column(Text)
    size_class: Mapped[str] = mapped_column(String(4))
    velocity_class: Mapped[str | None] = mapped_column(String(2))
    height_class: Mapped[str | None] = mapped_column(String(4))
    weight_kg: Mapped[float | None] = mapped_column(Numeric(12, 3))
    default_storage_profile_id: Mapped[int | None] = mapped_column(ForeignKey("storage_profiles.id"))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

class Vehicle(TimestampMixin, Base):
    __tablename__ = "vehicles"
    id: Mapped[int] = mapped_column(primary_key=True)
    vehicle_code: Mapped[str] = mapped_column(String(40), unique=True)
    license_plate: Mapped[str] = mapped_column(String(40), unique=True)
    vehicle_type: Mapped[str] = mapped_column(String(40))
    max_weight_kg: Mapped[float | None] = mapped_column(Numeric(12, 2))
    max_volume_m3: Mapped[float | None] = mapped_column(Numeric(12, 2))
    status: Mapped[str] = mapped_column(String(24), default="AVAILABLE")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

class Driver(TimestampMixin, Base):
    __tablename__ = "drivers"
    id: Mapped[int] = mapped_column(primary_key=True)
    driver_code: Mapped[str] = mapped_column(String(40), unique=True)
    first_name: Mapped[str] = mapped_column(String(80))
    last_name: Mapped[str] = mapped_column(String(80))
    phone: Mapped[str] = mapped_column(String(40))
    license_no: Mapped[str | None] = mapped_column(String(80))
    license_type: Mapped[str | None] = mapped_column(String(40))
    license_expiry: Mapped[datetime | None] = mapped_column(Date)
    status: Mapped[str] = mapped_column(String(24), default="AVAILABLE")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

class Customer(TimestampMixin, Base):
    __tablename__ = "customers"
    id: Mapped[int] = mapped_column(primary_key=True)
    customer_code: Mapped[str] = mapped_column(String(40), unique=True)
    customer_name: Mapped[str] = mapped_column(String(160))
    contact_name: Mapped[str | None] = mapped_column(String(120))
    phone: Mapped[str | None] = mapped_column(String(40))
    email: Mapped[str | None] = mapped_column(String(160))
    address_line1: Mapped[str] = mapped_column(String(255))
    district: Mapped[str | None] = mapped_column(String(120))
    province: Mapped[str | None] = mapped_column(String(120))
    postal_code: Mapped[str | None] = mapped_column(String(20))
    country: Mapped[str] = mapped_column(String(80), default="Thailand")
    latitude: Mapped[float | None] = mapped_column(Numeric(10, 7))
    longitude: Mapped[float | None] = mapped_column(Numeric(10, 7))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

class HandlingUnit(TimestampMixin, Base):
    __tablename__ = "handling_units"
    __table_args__ = (CheckConstraint('current_location_id IS NULL OR current_vehicle_id IS NULL', name='ck_hu_exclusive_custody'),)
    id: Mapped[int] = mapped_column(primary_key=True)
    hu_code: Mapped[str] = mapped_column(String(60), unique=True, index=True)
    hu_type: Mapped[str] = mapped_column(String(30))
    current_location_id: Mapped[int | None] = mapped_column(ForeignKey("locations.id"), index=True)
    current_vehicle_id: Mapped[int | None] = mapped_column(ForeignKey("vehicles.id"), index=True)
    current_node_type: Mapped[str] = mapped_column(String(30), default="EXTERNAL")
    current_status: Mapped[str] = mapped_column(String(30), default="ACTIVE")
    gross_weight_kg: Mapped[float | None] = mapped_column(Numeric(12, 3))

class HandlingUnitItem(Base):
    __tablename__ = "handling_unit_items"
    __table_args__ = (UniqueConstraint("handling_unit_id", "product_id", "lot_no", "batch_no"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    handling_unit_id: Mapped[int] = mapped_column(ForeignKey("handling_units.id"), index=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"), index=True)
    lot_no: Mapped[str | None] = mapped_column(String(80))
    batch_no: Mapped[str | None] = mapped_column(String(80))
    expiry_date: Mapped[datetime | None] = mapped_column(Date)
    quantity: Mapped[float] = mapped_column(Numeric(14, 3))
    unit_of_measure: Mapped[str] = mapped_column(String(20), default="EA")

class Inventory(TimestampMixin, Base):
    __tablename__ = "inventory"
    __table_args__ = (UniqueConstraint("product_id", "handling_unit_id"), CheckConstraint('quantity >= 0 AND reserved_quantity >= 0 AND reserved_quantity <= quantity', name='ck_inventory_quantities'))
    id: Mapped[int] = mapped_column(primary_key=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"), index=True)
    handling_unit_id: Mapped[int] = mapped_column(ForeignKey("handling_units.id"), index=True)
    location_id: Mapped[int | None] = mapped_column(ForeignKey("locations.id"), index=True)
    lot_no: Mapped[str | None] = mapped_column(String(80))
    batch_no: Mapped[str | None] = mapped_column(String(80))
    quantity: Mapped[float] = mapped_column(Numeric(14, 3))
    reserved_quantity: Mapped[float] = mapped_column(Numeric(14, 3), default=0)
    unit_of_measure: Mapped[str] = mapped_column(String(20), default="EA")

class StockMovement(TimestampMixin, Base):
    __tablename__ = "stock_movements"
    id: Mapped[int] = mapped_column(primary_key=True)
    movement_no: Mapped[str] = mapped_column(String(60), unique=True)
    movement_type: Mapped[str] = mapped_column(String(30), index=True)
    source_location_id: Mapped[int | None] = mapped_column(ForeignKey("locations.id"))
    destination_location_id: Mapped[int | None] = mapped_column(ForeignKey("locations.id"))
    source_vehicle_id: Mapped[int | None] = mapped_column(ForeignKey("vehicles.id"))
    destination_vehicle_id: Mapped[int | None] = mapped_column(ForeignKey("vehicles.id"))
    shipment_id: Mapped[int | None] = mapped_column(index=True)
    status: Mapped[str] = mapped_column(String(20), default="COMPLETED")
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

class StockMovementItem(Base):
    __tablename__ = "stock_movement_items"
    id: Mapped[int] = mapped_column(primary_key=True)
    movement_id: Mapped[int] = mapped_column(ForeignKey("stock_movements.id"), index=True)
    handling_unit_id: Mapped[int] = mapped_column(ForeignKey("handling_units.id"), index=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"))
    quantity: Mapped[float] = mapped_column(Numeric(14, 3))
    unit_of_measure: Mapped[str] = mapped_column(String(20))

class WarehouseTask(TimestampMixin, Base):
    __tablename__ = "warehouse_tasks"
    id: Mapped[int] = mapped_column(primary_key=True)
    task_no: Mapped[str] = mapped_column(String(60), unique=True)
    task_type: Mapped[str] = mapped_column(String(30))
    shipment_id: Mapped[int | None] = mapped_column(index=True)
    handling_unit_id: Mapped[int | None] = mapped_column(ForeignKey("handling_units.id"))
    source_location_id: Mapped[int | None] = mapped_column(ForeignKey("locations.id"))
    destination_location_id: Mapped[int | None] = mapped_column(ForeignKey("locations.id"))
    vehicle_id: Mapped[int | None] = mapped_column(ForeignKey("vehicles.id"))
    priority: Mapped[int] = mapped_column(default=5)
    status: Mapped[str] = mapped_column(String(24), default="PENDING")
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

class Shipment(TimestampMixin, Base):
    __tablename__ = "shipments"
    id: Mapped[int] = mapped_column(primary_key=True)
    shipment_no: Mapped[str] = mapped_column(String(60), unique=True, index=True)
    customer_id: Mapped[int] = mapped_column(ForeignKey("customers.id"))
    origin_warehouse_id: Mapped[int] = mapped_column(ForeignKey("warehouses.id"))
    destination_name: Mapped[str] = mapped_column(String(160))
    destination_contact_name: Mapped[str | None] = mapped_column(String(120))
    destination_phone: Mapped[str | None] = mapped_column(String(40))
    destination_address_line1: Mapped[str] = mapped_column(String(255))
    destination_district: Mapped[str | None] = mapped_column(String(120))
    destination_province: Mapped[str | None] = mapped_column(String(120))
    destination_postal_code: Mapped[str | None] = mapped_column(String(20))
    destination_country: Mapped[str] = mapped_column(String(80), default="Thailand")
    vehicle_id: Mapped[int | None] = mapped_column(ForeignKey("vehicles.id"))
    driver_id: Mapped[int | None] = mapped_column(ForeignKey("drivers.id"))
    loading_dock_id: Mapped[int | None] = mapped_column(ForeignKey("loading_docks.id"))
    planned_departure_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    actual_departure_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    actual_arrival_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(30), default="PLANNED", index=True)

class DeliveryRun(TimestampMixin, Base):
    __tablename__ = "delivery_runs"
    id: Mapped[int] = mapped_column(primary_key=True)
    run_no: Mapped[str] = mapped_column(String(60), unique=True, index=True)
    origin_warehouse_id: Mapped[int] = mapped_column(ForeignKey("warehouses.id"))
    vehicle_id: Mapped[int] = mapped_column(ForeignKey("vehicles.id"), index=True)
    driver_id: Mapped[int] = mapped_column(ForeignKey("drivers.id"), index=True)
    loading_dock_id: Mapped[int | None] = mapped_column(ForeignKey("loading_docks.id"), index=True)
    status: Mapped[str] = mapped_column(String(30), default="PLANNED", index=True)
    planned_departure_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    truck_arrived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    dock_entered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    loading_started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    ready_to_depart_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    actual_departure_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

class DeliveryRunShipment(Base):
    __tablename__ = "delivery_run_shipments"
    __table_args__ = (UniqueConstraint("shipment_id"), UniqueConstraint("delivery_run_id", "stop_sequence"))
    id: Mapped[int] = mapped_column(primary_key=True)
    delivery_run_id: Mapped[int] = mapped_column(ForeignKey("delivery_runs.id"), index=True)
    shipment_id: Mapped[int] = mapped_column(ForeignKey("shipments.id"), index=True)
    stop_sequence: Mapped[int] = mapped_column(default=1)

class DeliveryRunEvent(TimestampMixin, Base):
    __tablename__ = "delivery_run_events"
    id: Mapped[int] = mapped_column(primary_key=True)
    delivery_run_id: Mapped[int] = mapped_column(ForeignKey("delivery_runs.id"), index=True)
    event_type: Mapped[str] = mapped_column(String(30), index=True)
    event_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    latitude: Mapped[float | None] = mapped_column(Numeric(10, 7))
    longitude: Mapped[float | None] = mapped_column(Numeric(10, 7))
    note: Mapped[str | None] = mapped_column(Text)

class ShipmentItem(Base):
    __tablename__ = "shipment_items"
    id: Mapped[int] = mapped_column(primary_key=True)
    shipment_id: Mapped[int] = mapped_column(ForeignKey("shipments.id"), index=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"))
    handling_unit_id: Mapped[int | None] = mapped_column(ForeignKey("handling_units.id"), index=True)
    planned_quantity: Mapped[float] = mapped_column(Numeric(14, 3))
    loaded_quantity: Mapped[float] = mapped_column(Numeric(14, 3), default=0)
    delivered_quantity: Mapped[float] = mapped_column(Numeric(14, 3), default=0)
    unit_of_measure: Mapped[str] = mapped_column(String(20), default="EA")

class ShipmentTrackingEvent(TimestampMixin, Base):
    __tablename__ = "shipment_tracking_events"
    id: Mapped[int] = mapped_column(primary_key=True)
    shipment_id: Mapped[int] = mapped_column(ForeignKey("shipments.id"), index=True)
    event_type: Mapped[str] = mapped_column(String(30))
    event_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    latitude: Mapped[float | None] = mapped_column(Numeric(10, 7))
    longitude: Mapped[float | None] = mapped_column(Numeric(10, 7))
    note: Mapped[str | None] = mapped_column(Text)

class DeliveryAttempt(TimestampMixin, Base):
    __tablename__ = "delivery_attempts"
    id: Mapped[int] = mapped_column(primary_key=True)
    shipment_id: Mapped[int] = mapped_column(ForeignKey("shipments.id"), index=True)
    attempt_no: Mapped[int]
    attempted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    result: Mapped[str] = mapped_column(String(30))
    failure_reason: Mapped[str | None] = mapped_column(String(50))
    note: Mapped[str | None] = mapped_column(Text)

class ProofOfDelivery(TimestampMixin, Base):
    __tablename__ = "proof_of_delivery"
    id: Mapped[int] = mapped_column(primary_key=True)
    shipment_id: Mapped[int] = mapped_column(ForeignKey("shipments.id"), unique=True)
    receiver_name: Mapped[str] = mapped_column(String(120))
    receiver_phone: Mapped[str | None] = mapped_column(String(40))
    signature_file: Mapped[str | None] = mapped_column(String(255))
    photo_file: Mapped[str | None] = mapped_column(String(255))
    delivery_pin_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    latitude: Mapped[float | None] = mapped_column(Numeric(10, 7))
    longitude: Mapped[float | None] = mapped_column(Numeric(10, 7))
    delivered_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    note: Mapped[str | None] = mapped_column(Text)

class AuditLog(Base):
    __tablename__ = "audit_logs"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    action: Mapped[str] = mapped_column(String(80))
    entity_type: Mapped[str] = mapped_column(String(80))
    entity_id: Mapped[str] = mapped_column(String(80))
    old_data: Mapped[str | None] = mapped_column(Text)
    new_data: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
