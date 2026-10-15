# End-to-end architecture

The application is a modular monolith. FastAPI owns the REST boundary; SQLAlchemy services own transactions and invariants; PostgreSQL is the production database. React consumes the API through one typed client.

## Important invariants

1. A rack and all generated storage locations are committed in one transaction.
2. A station and its `STATION` location are committed in one transaction.
3. Warehouse, location, station, and dock codes are unique.
4. Dimensions are stored in storage profiles and rack configuration, not hard-coded into allocation logic.
5. Version 1 storage is single depth. No depth control is exposed or persisted.

## Location code generation

`{warehouse}-{zone}-A{aisle}-R{rack}-B{bay}-L{level}-P{position}`

The generation service enumerates every Bay × Level × Position combination after a rack is flushed, then commits the rack and its locations atomically. A conflicting rack or location code rolls the entire operation back.

## Inventory and custody

`handling_units` stores an indexed current node projection, while `stock_movements` preserves the full audit trail. A custody movement updates the HU, inventory location, location occupancy and movement record atomically. Normal current-location queries never need to replay history.

## Shipment lifecycle

Shipment transitions are allow-listed in the logistics service. Allocation, retrieval, load, delivery and return operations lock the affected shipment, HU, inventory and destination rows. Loading validates shipment membership, duplicate loads are rejected, and delivered quantity cannot exceed the loaded complete HU.
