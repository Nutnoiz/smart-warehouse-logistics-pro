# Validation record — 15 October 2026

Environment: Windows, Python 3.12, Node 24.14.1, separate project environment, SQLite demo database, Edge headless browser.

- Backend: 58 regression / security / stock-integrity / sample lifecycle tests, including independent truck arrival, exclusive vehicle/driver ownership, parked-truck choices, staged shipment attachment, incremental multi-shipment loading, detach/reattach before scan, weight limits, duplicate/wrong-truck scan rejection, cancellation, complete/depart guards and stable sample-fleet naming without changing run/HU history.
- Frontend: TypeScript and production bundle build; 10 unit tests including API safety and combined shipment filters.
- Browser: login, live dashboard data, Ctrl+K search, 17 operational routes, inventory query deep link, mobile at 390×844 and sidebar open.
- Browser page errors: none during tested routes.
- Shipment filters: status/open work, vehicle/unassigned, delivery round, customer and combined SKU/HU/number search; clear and empty states; URL persistence across reload/detail/back; mobile layout. Uses read-only shipment data.
- Truck-first UI: register an empty arrived truck → enter a free dock → retrieve from rack for QC → create two partial shipments → choose only the parked truck → add a second shipment while loading → detach/reattach before scan → scan from the run and barcode input → complete/depart → one grouped truck on dashboard. Mobile verified during loading and after departure using a separate test database.
- Operational-page regression: rack slot → HU action → Checkout → shipment without transport → Loadout → deferred vehicle/driver/dock assignment → truck check-in → enter dock → start loading → scan HU → complete loading. Modal background and padding verified inside the legacy operational shell on desktop and mobile.
- Workflow browser validation uses a separate SQLite database and API on port 8011: editable HU suggestion, receipt refresh, card and conveyor item actions, checkout without a shipment, loadout reversal, partial shipping, remainder restock, inventory retrieval and mobile modal.
- Schema: 0006 adds tracked sample ownership; demo seed provisions home-improvement examples once and does not repopulate after clearing.
- Screenshots: docs/images/pro-login.png, pro-dashboard.png, pro-mobile.png.
- Frontend package versions and lockfile frozen; backend full requirements.lock.txt records the tested environment.

This is functional RC validation, not PostgreSQL concurrency/load certification, penetration testing, or customer UAT sign-off. Release gates and remaining scope are in PRODUCTION_READINESS.md.
