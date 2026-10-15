import { useEffect, useMemo, useState } from "react";
import {
  NavLink,
  Route,
  Routes,
  useNavigate,
  useParams,
} from "react-router-dom";
import {
  Boxes,
  ChevronRight,
  ClipboardCheck,
  DoorOpen,
  LayoutDashboard,
  Map,
  Menu,
  PackageOpen,
  Plus,
  Search,
  Send,
  Truck,
  Warehouse as WarehouseIcon,
  X,
} from "lucide-react";
import { api, post, upload } from "./api";
import { useResource } from "./pro/useResource";
import { InventoryWorkflowPage, HUActions } from "./pro/HUActions";
import { ShipmentTransport } from "./pro/ShipmentTransport";
import { ShipmentList } from "./pro/ShipmentList";
import { InboundProductPicker } from "./pro/InboundProductPicker";
import { NewTruckButton, RunLoadingWorkspace } from "./pro/TruckLoading";
import QRCode from "react-qr-code";
import type {
  AuditLog,
  Customer,
  Dashboard as DashboardType,
  DeliveryRun,
  Dock,
  Driver,
  Inventory,
  Location,
  PendingPutaway,
  PendingReturn,
  Product,
  Rack,
  Shipment,
  Station,
  StationOverview,
  Vehicle,
  Warehouse,
  WarehouseMapData,
  Zone,
} from "./types";

const nav = [
  ["/dashboard", "ภาพรวม", LayoutDashboard],
  ["/warehouse-map", "แผนผังคลัง", Map],
  ["/racks", "ชั้นวาง", Boxes],
  ["/stations", "จุดรับ-จ่าย", PackageOpen],
  ["/loading-docks", "ประตูโหลด", DoorOpen],
  ["/master-data", "ข้อมูลหลัก", Boxes],
  ["/inventory", "สินค้าและ HU", Search],
  ["/inbound", "รับสินค้า", ClipboardCheck],
  ["/shipments", "การจัดส่ง", Truck],
  ["/delivery-runs", "รอบรถขนส่ง", Truck],
  ["/driver", "Driver Mobile", Send],
  ["/audit", "ประวัติระบบ", ClipboardCheck],
] as const;
function Layout() {
  const [open, setOpen] = useState(false);
  return (
    <div className="shell">
      <aside className={open ? "open" : ""}>
        <div className="brand">
          <span>
            <WarehouseIcon size={22} />
          </span>
          <div>
            SMART<span>WAREHOUSE</span>
          </div>
          <button className="close" onClick={() => setOpen(false)}>
            <X />
          </button>
        </div>
        <p className="nav-title">WAREHOUSE CONTROL</p>
        <nav>
          {nav.map(([to, label, Icon]) => (
            <NavLink key={to} to={to} onClick={() => setOpen(false)}>
              <Icon size={19} />
              {label}
              <ChevronRight size={15} />
            </NavLink>
          ))}
        </nav>
        <div className="warehouse-pill">
          <span className="live-dot" />
          WH01 Online<small>Bangkok Hub</small>
        </div>
      </aside>
      <main>
        <header>
          <button className="menu" onClick={() => setOpen(true)}>
            <Menu />
          </button>
          <div>
            <h1>Smart Warehouse</h1>
            <p>Warehouse · inventory · delivery control</p>
          </div>
          <div className="avatar">AD</div>
        </header>
        <Routes>
          <Route path="*" element={<Dashboard />} />
          <Route path="/dashboard" element={<Dashboard />} />
          <Route path="/warehouse-map" element={<WarehouseMap />} />
          <Route path="/racks" element={<Racks />} />
          <Route path="/racks/:id/map" element={<RackMap />} />
          <Route path="/stations" element={<Stations />} />
          <Route path="/loading-docks" element={<Docks />} />
          <Route path="/master-data" element={<MasterDataPage />} />
          <Route path="/inventory" element={<InventoryPage />} />
          <Route path="/inbound" element={<InboundPage />} />
          <Route path="/shipments" element={<ShipmentsPage />} />
          <Route path="/shipments/:id" element={<ShipmentDetail />} />
          <Route path="/delivery-runs" element={<DeliveryRunsPage />} />
          <Route path="/delivery-runs/:runId" element={<DeliveryRunPage />} />
          <Route
            path="/vehicle-load/:vehicleCode"
            element={<VehicleLoadPage />}
          />
          <Route
            path="/returns/:huCode/putaway"
            element={<ReturnPutawayPage />}
          />
          <Route path="/driver" element={<DriverPage />} />
          <Route path="/audit" element={<AuditPage />} />
        </Routes>
      </main>
    </div>
  );
}

function useLoad<T>(path: string, initial: T) {
  const { data, error, reload } = useResource(path, initial);
  return { data, error, load: reload };
}
function ErrorBox({ message }: { message: string }) {
  return message ? <div className="error">{message}</div> : null;
}
function Metric({
  label,
  value,
  tone = "teal",
}: {
  label: string;
  value: string | number;
  tone?: string;
}) {
  return (
    <div className={`metric ${tone}`}>
      <span>{label}</span>
      <strong>{value}</strong>
      <i />
    </div>
  );
}

function Dashboard() {
  const initial = {
    warehouses: 0,
    zones: 0,
    racks: 0,
    total_locations: 0,
    available_locations: 0,
    occupied_locations: 0,
    blocked_locations: 0,
    stations: 0,
    loading_docks: 0,
    utilization_percent: 0,
    shipments_today: 0,
    ready_to_load: 0,
    in_transit: 0,
    delivered: 0,
    delivery_failed: 0,
    vehicles_available: 0,
    pending_putaway: 0,
    pending_returns: 0,
    trucks_waiting: 0,
    trucks_on_route: 0,
  };
  const { data: d, error } = useLoad<DashboardType>("/dashboard", initial);
  const alerts = [
    {
      label: "สินค้าเข้ารอจัดเก็บ",
      value: d.pending_putaway,
      to: "/inbound",
      tone: "amber",
    },
    {
      label: "สินค้าคืนรอจัดชั้น",
      value: d.pending_returns,
      to: "/dashboard",
      tone: "red",
    },
    {
      label: "รถรอ/กำลังโหลด",
      value: d.trucks_waiting,
      to: "/dashboard",
      tone: "blue",
    },
    {
      label: "รถกำลังนำส่ง",
      value: d.trucks_on_route,
      to: "/driver",
      tone: "green",
    },
  ];
  return (
    <section>
      <div className="page-head">
        <div>
          <p className="eyebrow">OPERATIONS OVERVIEW</p>
          <h2>สถานะคลังและการจัดส่ง</h2>
          <p>ภาพรวม Warehouse & Logistics แบบเรียลไทม์</p>
        </div>
        <span className="date">END-TO-END</span>
      </div>
      <ErrorBox message={error} />
      <div className="metrics">
        <Metric
          label="ตำแหน่งทั้งหมด"
          value={d.total_locations.toLocaleString()}
        />
        <Metric
          label="พร้อมใช้งาน"
          value={d.available_locations.toLocaleString()}
          tone="green"
        />
        <Metric
          label="ใช้งานแล้ว"
          value={d.occupied_locations.toLocaleString()}
          tone="yellow"
        />
        <Metric label="In Transit" value={d.in_transit} tone="teal" />
      </div>
      <div className="logistics-strip">
        <div>
          <span>Shipments Today</span>
          <b>{d.shipments_today}</b>
        </div>
        <div>
          <span>Ready to Load</span>
          <b>{d.ready_to_load}</b>
        </div>
        <div>
          <span>Delivered Today</span>
          <b>{d.delivered}</b>
        </div>
        <div>
          <span>Delivery Failed</span>
          <b>{d.delivery_failed}</b>
        </div>
        <div>
          <span>Vehicles Available</span>
          <b>{d.vehicles_available}</b>
        </div>
      </div>
      <div className="ops-alerts">
        {alerts.map((alert) => (
          <NavLink className={alert.tone} to={alert.to} key={alert.label}>
            <span>{alert.label}</span>
            <b>{alert.value}</b>
            <ChevronRight size={14} />
          </NavLink>
        ))}
      </div>
      <div className="grid two">
        <article className="panel">
          <h3>
            การใช้พื้นที่คลัง <small>{d.utilization_percent}%</small>
          </h3>
          <div className="progress">
            <i style={{ width: `${d.utilization_percent}%` }} />
          </div>
          <div className="mini-grid">
            <div>
              <b>{d.zones}</b>
              <span>โซน</span>
            </div>
            <div>
              <b>{d.racks}</b>
              <span>ชั้นวาง</span>
            </div>
            <div>
              <b>{d.stations}</b>
              <span>สถานี</span>
            </div>
            <div>
              <b>{d.loading_docks}</b>
              <span>ประตูโหลด</span>
            </div>
          </div>
        </article>
        <article className="panel action-panel">
          <p className="eyebrow">QUICK ACTION</p>
          <h3>งานรับและจัดส่งสินค้า</h3>
          <p>รับ HU เข้าคลัง จัดเก็บ และติดตามการส่งมอบครบกระบวนการ</p>
          <NavLink className="button" to="/shipments">
            เปิด Shipment Control <ChevronRight size={16} />
          </NavLink>
        </article>
      </div>
      <StationOverviewPanel />
    </section>
  );
}

function StationOverviewPanel() {
  const {
    data: stations,
    error,
    load,
  } = useLoad<StationOverview[]>("/stations/overview", []);
  const { data: warehouse, load: loadWarehouse } =
    useLoad<WarehouseMapData | null>("/warehouse-map/live", null);
  const { data: runs, load: loadRuns } = useLoad<DeliveryRun[]>(
    "/delivery-runs?active_only=true",
    [],
  );
  useEffect(() => {
    const timer = window.setInterval(() => {
      load();
      loadWarehouse();
      loadRuns();
    }, 10000);
    return () => window.clearInterval(timer);
  }, []);
  const byType = (type: string) =>
    stations.filter((station) => station.station_type === type);
  const totalHu = stations.reduce(
    (total, station) => total + station.hu_count,
    0,
  );
  const storedHu =
    warehouse?.zones.reduce(
      (total, zone) =>
        total + zone.racks.reduce((sum, rack) => sum + rack.hu_count, 0),
      0,
    ) || 0;
  const vehicleLoads = runs.map((run) => ({
    runId: run.id,
    runNo: run.run_no,
    vehicleCode: run.vehicle_code,
    shipments: run.shipments,
    status: run.status,
  }));
  const waitingLoads = vehicleLoads.filter((load) =>
    ["WAITING_DOCK", "AT_DOCK", "LOADING", "READY_TO_DEPART"].includes(
      load.status,
    ),
  );
  const routeLoads = vehicleLoads.filter((load) =>
    ["DEPARTED", "IN_TRANSIT"].includes(load.status),
  );
  const waitingTrucks = waitingLoads.length;
  const routeTrucks = routeLoads.length;
  const loadedHu = [...waitingLoads, ...routeLoads].reduce(
    (total, run) =>
      total +
      run.shipments.reduce(
        (sum, shipment) =>
          sum +
          shipment.items.filter((item) => item.loaded_quantity > 0).length,
        0,
      ),
    0,
  );
  return (
    <div className="digital-twin">
      <div className="twin-head">
        <div>
          <p className="eyebrow">WAREHOUSE DIGITAL TWIN</p>
          <h3>ระบบสายพานและสถานีปฏิบัติงาน</h3>
          <span>
            ข้อมูลจริงจากทุก Station ในกระบวนการหลัก · อัปเดตอัตโนมัติทุก 10
            วินาที
          </span>
        </div>
        <div className="twin-live">
          <i />
          LIVE{" "}
          <b>
            {totalHu} HU ON STATION · {waitingTrucks} TRUCK WAITING ·{" "}
            {routeTrucks} ON ROUTE · {loadedHu} HU ON TRUCK
          </b>
        </div>
      </div>
      <ErrorBox message={error} />
      <div className="factory-floor">
        <div className="factory-grid" />
        <div className="flow-caption">
          <span>RECEIVING</span>
          <span>STORAGE</span>
          <span>QUALITY CHECK</span>
          <span>LOAD STAGING</span>
          <span>LOADING BAY</span>
        </div>
        <div className="factory-flow">
          <ConveyorStationGroup
            type="inbound"
            label="INBOUND"
            stations={byType("INBOUND")}
          />
          <ConveyorBelt />
          <StorageMachine zones={warehouse?.zones || []} huCount={storedHu} />
          <ConveyorBelt />
          <ConveyorStationGroup
            type="checkout"
            label="CHECKOUT"
            stations={byType("CHECKOUT")}
          />
          <ConveyorBelt />
          <ConveyorStationGroup
            type="loadout"
            label="LOADOUT"
            stations={byType("LOADOUT")}
          />
          <ConveyorBelt />
          <TruckDispatch loads={waitingLoads} />
        </div>
        <DeliveryFleetStrip
          loads={routeLoads}
          returnStations={byType("RETURN")}
        />
      </div>
      <div className="twin-legend">
        <span>
          <i className="inbound" />
          รับเข้า
        </span>
        <span>
          <i className="storage" />
          จัดเก็บ
        </span>
        <span>
          <i className="checkout" />
          ตรวจสอบ
        </span>
        <span>
          <i className="loadout" />
          รอขึ้นรถ
        </span>
        <span>
          <i className="yard" />
          รถจอดรอ/กำลังโหลด
        </span>
        <span>
          <i className="dispatch" />
          รถกำลังนำส่ง
        </span>
        <span>
          <i className="return" />
          สินค้าคืน
        </span>
      </div>
    </div>
  );
}

function ConveyorBelt() {
  return (
    <div className="conveyor-belt" aria-hidden="true">
      <div className="belt-surface" />
      <div className="belt-rollers">
        {[1, 2, 3, 4, 5].map((x) => (
          <i key={x} />
        ))}
      </div>
      <ChevronRight />
    </div>
  );
}

function ConveyorStationGroup({
  type,
  label,
  stations,
}: {
  type: string;
  label: string;
  stations: StationOverview[];
}) {
  return (
    <div className={`conveyor-stage ${type}`}>
      <div className="stage-title">
        <span>{label}</span>
        <b>{stations.reduce((sum, station) => sum + station.hu_count, 0)} HU</b>
      </div>
      <div className="station-machines">
        {stations.map((station) => (
          <article className="station-machine" key={station.id}>
            <header>
              <span className="machine-light" />
              <div>
                <b>{station.station_code}</b>
                <small>{station.station_name}</small>
              </div>
              <strong>
                {station.hu_count}/{station.capacity_hu}
              </strong>
            </header>
            <div className="machine-deck">
              <div className="deck-track" />
              {station.items.map((item, index) => (
                <div
                  className={`cargo-box cargo-${index % 4}`}
                  key={item.hu_code}
                  title={`${item.hu_code} · ${item.sku} · ${item.quantity} ${item.unit_of_measure}`}
                >
                  <PackageOpen size={15} />
                  <b>{item.hu_code}</b>
                  <small>{item.sku}</small>
                  <span>
                    {item.quantity} {item.unit_of_measure}
                  </span>
                </div>
              ))}
              {!station.items.length && (
                <span className="station-clear">CLEAR</span>
              )}
            </div>
            <div className="machine-capacity">
              <i
                style={{
                  width: `${Math.min(100, (station.hu_count / station.capacity_hu) * 100)}%`,
                }}
              />
            </div>
          </article>
        ))}
        {!stations.length && <div className="station-offline">NO STATION</div>}
      </div>
    </div>
  );
}

function ReturnFlowStrip({ stations }: { stations: StationOverview[] }) {
  const huCount = stations.reduce((sum, station) => sum + station.hu_count, 0);
  return (
    <div className={`return-strip ${huCount ? "has-items" : "clear"}`}>
      <div className="return-strip-title">
        <span>↶</span>
        <div>
          <b>RETURN / EXCEPTION</b>
          <small>กดสินค้าเพื่อเลือกจัดเก็บเข้าชั้น</small>
        </div>
        <strong>{huCount} HU</strong>
      </div>
      <div className="return-strip-stations">
        {stations.map((station) => (
          <article key={station.id}>
            <header>
              <i />
              <div>
                <b>{station.station_code}</b>
                <small>{station.station_name}</small>
              </div>
              <strong>
                {station.hu_count}/{station.capacity_hu}
              </strong>
            </header>
            <div>
              {station.items.map((item) => (
                <NavLink
                  to={`/returns/${encodeURIComponent(item.hu_code)}/putaway`}
                  key={item.hu_code}
                  title={`จัดเก็บ ${item.hu_code} เข้าชั้น`}
                >
                  <PackageOpen size={10} />
                  <b>{item.hu_code}</b>
                  <small>
                    {item.sku} · {item.quantity} {item.unit_of_measure}
                  </small>
                </NavLink>
              ))}
              {!station.items.length && <em>CLEAR</em>}
            </div>
          </article>
        ))}
        {!stations.length && <em>NO RETURN STATION</em>}
      </div>
    </div>
  );
}

function StorageMachine({
  zones,
  huCount,
}: {
  zones: WarehouseMapData["zones"];
  huCount: number;
}) {
  return (
    <div className="storage-machine">
      <div className="stage-title">
        <span>STORAGE RACK</span>
        <b>{huCount} HU</b>
      </div>
      <div className="mini-racks">
        {zones.map((zone) => (
          <div className="mini-rack" key={zone.id}>
            <strong>{zone.zone_code}</strong>
            <div>
              {zone.racks.slice(0, 3).map((rack) => (
                <i
                  className={rack.hu_count ? "loaded" : ""}
                  style={
                    {
                      "--fill": `${rack.utilization_percent}%`,
                    } as React.CSSProperties
                  }
                  key={rack.id}
                >
                  <span>{rack.hu_count}</span>
                </i>
              ))}
            </div>
            <small>{zone.utilization_percent}%</small>
          </div>
        ))}
      </div>
    </div>
  );
}

const truckStatusLabel: Record<string, string> = {
  PLANNED: "วางแผนรอบรถ",
  WAITING_DOCK: "รถมาถึง · รอช่องโหลด",
  AT_DOCK: "รถอยู่ที่ช่องโหลด",
  READY_TO_LOAD: "รอเข้าช่องโหลด",
  LOADING: "กำลังโหลดสินค้า",
  LOADED: "โหลดเสร็จ รอออก",
  READY_TO_DEPART: "โหลดครบ · รอออก",
  DEPARTED: "ออกจากคลังแล้ว",
  IN_TRANSIT: "กำลังนำส่ง",
  ARRIVED: "ถึงจุดส่ง",
  COMPLETED: "จบรอบรถแล้ว",
};
const transactionLabel: Record<string, string> = {
  RETRIEVE: "นำลงจากชั้น",
  CHECKOUT: "ส่งเข้าจุดตรวจ",
  SPLIT_PICK: "แบ่งสินค้าเพื่อจัดส่ง",
  RESTOCK: "นำส่วนที่เหลือเก็บคืน",
  LOAD: "โหลดขึ้นรถ",
  DELIVER: "ส่งมอบให้ลูกค้า",
  UNLOAD: "นำสินค้าคืนลงจากรถ",
  RETURN_PUTAWAY: "จัดเก็บสินค้าคืนเข้าชั้น",
};
type VehicleLoad = {
  runId: number;
  runNo: string;
  vehicleCode: string;
  shipments: Shipment[];
  status: string;
};
const truckStatusRank: Record<string, number> = {
  READY_TO_LOAD: 1,
  LOADING: 2,
  LOADED: 3,
  DEPARTED: 4,
  IN_TRANSIT: 5,
  ARRIVED: 6,
};

function TruckLane({
  title,
  subtitle,
  loads,
  type,
}: {
  title: string;
  subtitle: string;
  loads: VehicleLoad[];
  type: "yard" | "route";
}) {
  return (
    <div className={`vehicle-lane ${type}`}>
      <div className="vehicle-lane-head">
        <span>
          {title}
          <small>{subtitle}</small>
        </span>
        <b>{loads.length} คัน</b>
      </div>
      <div className="vehicle-cards">
        {loads.length ? (
          loads.map((load) => {
            const cargo = load.shipments.flatMap((shipment) =>
              shipment.items
                .filter((item) => item.loaded_quantity > 0)
                .map((item) => ({ shipment, item })),
            );
            return (
              <NavLink
                to={`/delivery-runs/${load.runId}`}
                className="vehicle-card"
                key={load.runId}
                title="ดูสรุปรอบรถและสินค้าทั้งหมด"
              >
                <div className="vehicle-card-main">
                  <span className="vehicle-icon">
                    <Truck size={19} />
                    <i />
                  </span>
                  <div>
                    <b>{load.vehicleCode}</b>
                    <small>
                      {truckStatusLabel[load.status] || load.status}
                    </small>
                    <em>
                      {load.shipments.length} SHIPMENT · {load.runNo}
                    </em>
                  </div>
                  <strong>
                    {cargo.length} HU <ChevronRight size={9} />
                  </strong>
                </div>
                {cargo.length > 0 && (
                  <div className="vehicle-cargo-list">
                    {cargo.map(({ shipment, item }) => (
                      <span
                        key={`${shipment.id}-${item.id}`}
                        title={`${item.hu_code} · ${item.sku} · ${item.loaded_quantity} ${item.unit_of_measure}`}
                      >
                        <PackageOpen size={9} />
                        <b>{item.hu_code}</b>
                        <small>
                          {item.loaded_quantity} {item.unit_of_measure}
                        </small>
                      </span>
                    ))}
                  </div>
                )}
                <span className="vehicle-card-hint">
                  หนึ่งรอบรถ · {load.shipments.length} รายการส่ง · คลิกดูภายใน
                </span>
              </NavLink>
            );
          })
        ) : (
          <div className="vehicle-empty">
            <Truck size={18} />
            <span>
              {type === "yard" ? "ไม่มีรถจอดรอ" : "ไม่มีรถระหว่างนำส่ง"}
            </span>
          </div>
        )}
      </div>
    </div>
  );
}

function TruckDispatch({ loads }: { loads: VehicleLoad[] }) {
  return (
    <div className="truck-stage vehicle-control-stage">
      <div className="stage-title">
        <span>TRUCK LOADING BAY</span>
        <b>{loads.length} TRUCK</b>
      </div>
      <TruckLane
        title="รถรอรับสินค้า"
        subtitle="WAITING / LOADING / READY"
        loads={loads}
        type="yard"
      />
    </div>
  );
}

function DeliveryFleetStrip({
  loads,
  returnStations,
}: {
  loads: VehicleLoad[];
  returnStations: StationOverview[];
}) {
  return (
    <div className="delivery-return-zone">
      <div className="route-fleet">
        <div className="route-fleet-head">
          <span>
            <Truck size={16} />
            <b>รถกำลังออกไปส่ง</b>
            <small>OUTBOUND DELIVERY FLEET</small>
          </span>
          <strong>{loads.length} คัน</strong>
        </div>
        <div className="route-fleet-cards">
          {loads.map((load) => {
            const cargo = load.shipments.flatMap((shipment) =>
              shipment.items
                .filter((item) => item.loaded_quantity > 0)
                .map((item) => ({ shipment, item })),
            );
            return (
              <NavLink to={`/delivery-runs/${load.runId}`} key={load.runId}>
                <span className="route-truck-icon">
                  <Truck size={24} />
                  <i />
                </span>
                <div>
                  <b>{load.vehicleCode}</b>
                  <small>{truckStatusLabel[load.status] || load.status}</small>
                  <em>
                    {load.shipments.length} รายการส่ง · {cargo.length} HU ·{" "}
                    {load.runNo}
                  </em>
                </div>
                <div className="route-cargo-preview">
                  {cargo.slice(0, 4).map(({ shipment, item }) => (
                    <i
                      key={`${shipment.id}-${item.id}`}
                      title={`${item.hu_code} · ${item.sku}`}
                    >
                      <PackageOpen size={8} />
                    </i>
                  ))}
                  {cargo.length > 4 && <small>+{cargo.length - 4}</small>}
                </div>
                <ChevronRight size={14} />
              </NavLink>
            );
          })}
          {!loads.length && (
            <div className="route-fleet-empty">
              <Truck size={20} />
              <span>ขณะนี้ไม่มีรถที่กำลังออกไปส่ง</span>
            </div>
          )}
        </div>
      </div>
      <ReturnFlowStrip stations={returnStations} />
    </div>
  );
}

const runAction: Record<string, { path: string; label: string; hint: string }> =
  {
    PLANNED: {
      path: "check-in",
      label: "ยืนยันรถมาถึงคลัง",
      hint: "เปลี่ยนเป็นรอเข้าช่องโหลด",
    },
    WAITING_DOCK: {
      path: "enter-dock",
      label: "นำรถเข้าช่องโหลด",
      hint: "ตรวจความจุของ Loading Dock ก่อนเข้า",
    },
    AT_DOCK: {
      path: "start-loading",
      label: "เริ่มโหลดสินค้าทั้งรอบ",
      hint: "Shipment ทุกรายการต้องพร้อมโหลด",
    },
    LOADING: {
      path: "complete-loading",
      label: "ยืนยันโหลดครบทั้งคัน",
      hint: "HU ทุกรายการต้องสแกนขึ้นรถครบ",
    },
    READY_TO_DEPART: {
      path: "depart",
      label: "ปล่อยรถออกจากคลัง",
      hint: "บันทึกเวลาออกจริงให้ทุกรายการส่ง",
    },
    DEPARTED: {
      path: "in-transit",
      label: "ยืนยันกำลังนำส่ง",
      hint: "เปิดสถานะติดตามรถระหว่างทาง",
    },
  };

function DeliveryRunsPage() {
  const { data: runs, error } = useLoad<DeliveryRun[]>("/delivery-runs", []);
  const [query, setQuery] = useState("");
  const [status, setStatus] = useState("ALL");
  const statuses = ["ALL", ...new Set(runs.map((run) => run.status))];
  const filtered = runs.filter(
    (run) =>
      (status === "ALL" || run.status === status) &&
      `${run.run_no} ${run.vehicle_code} ${run.license_plate} ${run.driver_name}`
        .toLowerCase()
        .includes(query.toLowerCase()),
  );
  return (
    <section className="delivery-runs-page">
      <PageTitle
        eyebrow="TRANSPORT HISTORY"
        title="รอบรถขนส่ง"
        action={<NewTruckButton />}
        desc="ลงทะเบียนรถมาถึง → เข้าช่องโหลด → เลือกรายการส่ง → สแกนขึ้นรถ → ปล่อยรถ"
      />
      <ErrorBox message={error} />
      <div className="run-filters">
        <div className="searchbar">
          <Search size={17} />
          <input
            placeholder="ค้นหาเลขรอบ รถ ทะเบียน หรือคนขับ..."
            value={query}
            onChange={(e) => setQuery(e.target.value)}
          />
        </div>
        <select value={status} onChange={(e) => setStatus(e.target.value)}>
          {statuses.map((value) => (
            <option value={value} key={value}>
              {value === "ALL" ? "ทุกสถานะ" : truckStatusLabel[value] || value}
            </option>
          ))}
        </select>
      </div>
      <div className="run-list">
        {filtered.map((run) => {
          const huCount = run.shipments.reduce(
            (sum, shipment) => sum + shipment.items.length,
            0,
          );
          return (
            <NavLink to={`/delivery-runs/${run.id}`} key={run.id}>
              <span className="run-list-truck">
                <Truck size={24} />
              </span>
              <div>
                <small>{run.run_no}</small>
                <h3>
                  {run.vehicle_code} · {run.license_plate}
                </h3>
                <p>
                  {run.driver_name} · Dock {run.loading_dock_code || "-"}
                </p>
              </div>
              <div className="run-list-load">
                <b>{run.shipments.length}</b>
                <small>SHIPMENTS</small>
                <b>{huCount}</b>
                <small>HU</small>
              </div>
              <span className={`status run-${run.status.toLowerCase()}`}>
                {truckStatusLabel[run.status] || run.status}
              </span>
              <div className="run-list-time">
                <small>
                  {run.actual_departure_at
                    ? "ออก " +
                      new Date(run.actual_departure_at).toLocaleString("th-TH")
                    : "ยังไม่ออกจากคลัง"}
                </small>
                {run.completed_at && (
                  <small>
                    จบรอบ {new Date(run.completed_at).toLocaleString("th-TH")}
                  </small>
                )}
              </div>
              <ChevronRight />
            </NavLink>
          );
        })}
        {!filtered.length && (
          <div className="empty panel">ไม่พบรอบรถที่ตรงกับตัวกรอง</div>
        )}
      </div>
    </section>
  );
}

function DeliveryRunPage() {
  const { runId } = useParams();
  const {
    data: run,
    error,
    load,
  } = useLoad<DeliveryRun | null>(`/delivery-runs/${runId}`, null);
  const [actionError, setActionError] = useState("");
  const [saving, setSaving] = useState(false);
  if (!run)
    return (
      <section>
        <ErrorBox message={error} />
      </section>
    );
  const activeShipments = run.shipments.filter((s) => s.status !== "CANCELLED");
  const cargo = activeShipments.flatMap((shipment) =>
    shipment.items
      .filter((item) => item.loaded_quantity > 0)
      .map((item) => ({ shipment, item })),
  );
  const plannedHu = activeShipments.reduce(
    (sum, shipment) => sum + shipment.items.length,
    0,
  );
  const totalLoaded = cargo.reduce(
    (sum, row) => sum + row.item.loaded_quantity,
    0,
  );
  const action = runAction[run.status];
  async function advance() {
    if (!action) return;
    setSaving(true);
    setActionError("");
    try {
      await post(`/delivery-runs/${runId}/${action.path}`, {});
      load();
    } catch (e) {
      setActionError((e as Error).message);
    } finally {
      setSaving(false);
    }
  }
  return (
    <section className="vehicle-load-page delivery-run-page">
      <PageTitle
        eyebrow="DELIVERY RUN CONTROL"
        title={run.run_no}
        desc="หนึ่งรอบรถจริง รวมหลาย Shipment และประวัติการเคลื่อนที่ในรอบเดียว"
        action={
          <NavLink className="ghost" to="/dashboard">
            ← กลับ Dashboard
          </NavLink>
        }
      />
      <ErrorBox message={error || actionError} />
      <div className="vehicle-load-hero">
        <div className="vehicle-load-icon">
          <Truck size={58} />
          <i />
        </div>
        <div>
          <span>รถและสถานะรอบปัจจุบัน</span>
          <h3>
            {run.vehicle_code} · {truckStatusLabel[run.status] || run.status}
          </h3>
          <p>
            {run.license_plate} · {run.driver_name} · Dock{" "}
            {run.loading_dock_code || "-"}
          </p>
        </div>
        <div className="run-hero-stats">
          <b>
            {activeShipments.length}
            <small>SHIPMENTS</small>
          </b>
          <b>
            {cargo.length}/{plannedHu}
            <small>HU LOADED</small>
          </b>
          <b>
            {totalLoaded.toLocaleString()}
            <small>UNITS</small>
          </b>
        </div>
      </div>
      <RunLoadingWorkspace run={run} onChanged={load} />
      {action && run.status !== "WAITING_DOCK" && (
        <article className="panel run-control">
          <div>
            <p className="eyebrow">NEXT OPERATION</p>
            <h3>{action.label}</h3>
            <span>{action.hint}</span>
          </div>
          <button
            className="button"
            disabled={
              saving ||
              (run.status === "AT_DOCK" &&
                (!activeShipments.length ||
                  activeShipments.some((s) => s.status !== "READY_TO_LOAD"))) ||
              (run.status === "LOADING" &&
                (!plannedHu || cargo.length < plannedHu))
            }
            onClick={advance}
          >
            {saving ? "กำลังบันทึก..." : action.label}
            <ChevronRight size={16} />
          </button>
        </article>
      )}
      {run.status === "LOADING" && cargo.length < plannedHu && (
        <div className="run-warning">
          ยังมี {plannedHu - cargo.length} HU ที่ไม่ได้สแกนขึ้นรถ
          สแกนได้จากคิวโหลดด้านบนก่อนยืนยันโหลดครบ
        </div>
      )}
      <article className="panel vehicle-cargo-summary">
        <div className="vehicle-summary-head">
          <div>
            <p className="eyebrow">CARGO ON THIS RUN</p>
            <h3>สินค้าบนรถในรอบนี้</h3>
          </div>
          <span>{cargo.length} HU</span>
        </div>
        {cargo.length ? (
          <div className="vehicle-cargo-grid">
            {cargo.map(({ shipment, item }) => (
              <NavLink
                to={`/shipments/${shipment.id}`}
                key={`${shipment.id}-${item.id}`}
              >
                <PackageOpen size={25} />
                <div>
                  <b>{item.sku}</b>
                  <small>{item.hu_code}</small>
                  <span>
                    {item.loaded_quantity} {item.unit_of_measure}
                  </span>
                </div>
                <ChevronRight size={17} />
                <em>{shipment.shipment_no}</em>
              </NavLink>
            ))}
          </div>
        ) : (
          <div className="empty">ยังไม่มีสินค้าที่สแกนขึ้นรถในรอบนี้</div>
        )}
      </article>
      <div className="run-detail-grid">
        <div>
          <div className="vehicle-shipment-head">
            <div>
              <p className="eyebrow">DELIVERY STOPS</p>
              <h3>รายการส่งทั้งหมดในรอบรถ</h3>
            </div>
            <span>กดเพื่อดู HU และ Transaction</span>
          </div>
          <div className="vehicle-shipment-list">
            {run.shipments.map((shipment) => {
              const loaded = shipment.items.reduce(
                (sum, item) => sum + item.loaded_quantity,
                0,
              );
              return (
                <NavLink to={`/shipments/${shipment.id}`} key={shipment.id}>
                  <div>
                    <span
                      className={`status shipment-${shipment.status.toLowerCase()}`}
                    >
                      {shipment.status}
                    </span>
                    <h3>{shipment.shipment_no}</h3>
                    <p>
                      {shipment.customer_name} · {shipment.destination_name}
                    </p>
                  </div>
                  <div className="vehicle-shipment-items">
                    {shipment.items.map((item) => (
                      <span key={item.id}>
                        <b>{item.sku}</b>
                        <small>
                          {item.hu_code || "รอจัดสรร HU"} ·{" "}
                          {item.loaded_quantity}/{item.planned_quantity}{" "}
                          {item.unit_of_measure}
                        </small>
                      </span>
                    ))}
                  </div>
                  <strong>
                    {shipment.items.length} HU · {loaded} หน่วย
                    <ChevronRight />
                  </strong>
                </NavLink>
              );
            })}
          </div>
        </div>
        <article className="panel timeline run-timeline">
          <h3>ประวัติรอบรถ</h3>
          {run.events.map((event, index) => (
            <div className="timeline-item" key={`${event.event_at}-${index}`}>
              <i />
              <div>
                <b>{truckStatusLabel[event.event_type] || event.event_type}</b>
                <small>
                  {new Date(event.event_at).toLocaleString("th-TH")}
                </small>
                {event.note && <p>{event.note}</p>}
              </div>
            </div>
          ))}
        </article>
      </div>
    </section>
  );
}

function VehicleLoadPage() {
  const { vehicleCode = "" } = useParams();
  const { data: shipments, error } = useLoad<Shipment[]>("/shipments", []);
  const allForVehicle = shipments.filter(
    (shipment) => shipment.vehicle_code === vehicleCode,
  );
  const active = allForVehicle.filter((shipment) =>
    [
      "READY_TO_LOAD",
      "LOADING",
      "LOADED",
      "DEPARTED",
      "IN_TRANSIT",
      "ARRIVED",
    ].includes(shipment.status),
  );
  const current = active.length ? active : allForVehicle.slice(0, 5);
  const cargo = current.flatMap((shipment) =>
    shipment.items
      .filter((item) => item.loaded_quantity > 0)
      .map((item) => ({ shipment, item })),
  );
  const totalQuantity = cargo.reduce(
    (sum, row) => sum + row.item.loaded_quantity,
    0,
  );
  const status = [...current].sort(
    (a, b) =>
      (truckStatusRank[b.status] || 0) - (truckStatusRank[a.status] || 0),
  )[0]?.status;
  return (
    <section className="vehicle-load-page">
      <PageTitle
        eyebrow="VEHICLE LOAD SUMMARY"
        title={vehicleCode}
        desc="ภาพรวมสินค้าทุก Shipment ที่อยู่ในรถคันเดียวกัน"
        action={
          <NavLink className="ghost" to="/dashboard">
            ← กลับ Dashboard
          </NavLink>
        }
      />
      <ErrorBox message={error} />
      <div className="vehicle-load-hero">
        <div className="vehicle-load-icon">
          <Truck size={58} />
          <i />
        </div>
        <div>
          <span>สถานะรถปัจจุบัน</span>
          <h3>
            {truckStatusLabel[status] || status || "ไม่มีงานที่กำลังดำเนินการ"}
          </h3>
          <p>
            {current.length} รายการส่ง · {cargo.length} HU ·{" "}
            {totalQuantity.toLocaleString()} หน่วยบนรถ
          </p>
        </div>
      </div>
      <article className="panel vehicle-cargo-summary">
        <div className="vehicle-summary-head">
          <div>
            <p className="eyebrow">CARGO ON VEHICLE</p>
            <h3>สินค้าในรถคันนี้</h3>
          </div>
          <span>{cargo.length} HU</span>
        </div>
        {cargo.length ? (
          <div className="vehicle-cargo-grid">
            {cargo.map(({ shipment, item }) => (
              <NavLink
                to={`/shipments/${shipment.id}`}
                key={`${shipment.id}-${item.id}`}
              >
                <PackageOpen size={25} />
                <div>
                  <b>{item.sku}</b>
                  <small>{item.hu_code}</small>
                  <span>
                    {item.loaded_quantity} {item.unit_of_measure}
                  </span>
                </div>
                <ChevronRight size={17} />
                <em>{shipment.shipment_no}</em>
              </NavLink>
            ))}
          </div>
        ) : (
          <div className="empty">ยังไม่มีสินค้าที่สแกนขึ้นรถคันนี้</div>
        )}
      </article>
      <div className="vehicle-shipment-head">
        <div>
          <p className="eyebrow">DELIVERY JOBS</p>
          <h3>รายการส่งทั้งหมดในรถ</h3>
        </div>
        <span>กดรายการเพื่อดูรายละเอียดและ Transaction</span>
      </div>
      <div className="vehicle-shipment-list">
        {current.map((shipment) => {
          const loaded = shipment.items.reduce(
            (sum, item) => sum + item.loaded_quantity,
            0,
          );
          return (
            <NavLink to={`/shipments/${shipment.id}`} key={shipment.id}>
              <div>
                <span
                  className={`status shipment-${shipment.status.toLowerCase()}`}
                >
                  {shipment.status}
                </span>
                <h3>{shipment.shipment_no}</h3>
                <p>
                  {shipment.customer_name} · {shipment.destination_name}
                </p>
              </div>
              <div className="vehicle-shipment-items">
                {shipment.items.map((item) => (
                  <span key={item.id}>
                    <b>{item.sku}</b>
                    <small>
                      {item.hu_code || "รอจัดสรร HU"} · {item.loaded_quantity}/
                      {item.planned_quantity} {item.unit_of_measure}
                    </small>
                  </span>
                ))}
              </div>
              <strong>
                {shipment.items.length} HU · {loaded} หน่วย
                <ChevronRight />
              </strong>
            </NavLink>
          );
        })}
        {!current.length && (
          <div className="empty panel">ไม่พบรายการส่งของรถคันนี้</div>
        )}
      </div>
    </section>
  );
}

function ReturnPutawayPage() {
  const { huCode = "" } = useParams();
  const navigate = useNavigate();
  const { data: pending, error: pendingError } = useLoad<PendingReturn[]>(
    "/returns/pending",
    [],
  );
  const [options, setOptions] = useState<Location[]>([]);
  const [selectedLocationId, setSelectedLocationId] = useState(0);
  const [error, setError] = useState("");
  const [saving, setSaving] = useState(false);
  useEffect(() => {
    if (!huCode) return;
    post<Location[]>("/returns/putaway-options", { hu_code: huCode })
      .then((rows) => {
        setOptions(rows);
        setSelectedLocationId(rows[0]?.id || 0);
      })
      .catch((e) => setError(e.message));
  }, [huCode]);
  const item = pending.find((row) => row.hu_code === huCode);
  const selected =
    options.find((location) => location.id === selectedLocationId) ||
    options[0];
  const zoneIds = [
    ...new Set(
      options
        .map((location) => location.zone_id)
        .filter((id): id is number => Boolean(id)),
    ),
  ];
  const rackIds = selected
    ? [
        ...new Set(
          options
            .filter((location) => location.zone_id === selected.zone_id)
            .map((location) => location.rack_id)
            .filter((id): id is number => Boolean(id)),
        ),
      ]
    : [];
  const bayNumbers = selected
    ? [
        ...new Set(
          options
            .filter(
              (location) =>
                location.zone_id === selected.zone_id &&
                location.rack_id === selected.rack_id,
            )
            .map((location) => location.bay_no)
            .filter((value): value is number => Boolean(value)),
        ),
      ]
    : [];
  const levelNumbers = selected
    ? [
        ...new Set(
          options
            .filter(
              (location) =>
                location.zone_id === selected.zone_id &&
                location.rack_id === selected.rack_id &&
                location.bay_no === selected.bay_no,
            )
            .map((location) => location.level_no)
            .filter((value): value is number => Boolean(value)),
        ),
      ]
    : [];
  const positions = selected
    ? options.filter(
        (location) =>
          location.zone_id === selected.zone_id &&
          location.rack_id === selected.rack_id &&
          location.bay_no === selected.bay_no &&
          location.level_no === selected.level_no,
      )
    : [];
  function selectFirst(predicate: (location: Location) => boolean) {
    const match = options.find(predicate);
    if (match) setSelectedLocationId(match.id);
  }
  async function confirm() {
    if (!selected) return;
    setSaving(true);
    setError("");
    try {
      await post("/returns/putaway", {
        hu_code: huCode,
        destination_location_id: selected.id,
      });
      navigate("/dashboard");
    } catch (e) {
      setError((e as Error).message);
      setSaving(false);
    }
  }
  return (
    <section className="return-putaway-page">
      <PageTitle
        eyebrow="RETURN DISPOSITION"
        title="จัดเก็บสินค้าคืนเข้าชั้น"
        desc="ชั้น Return เป็นตัวเลือกแนะนำ หรือเลือกชั้นปกติสำหรับสินค้าภายในบริษัท"
        action={
          <button className="ghost" onClick={() => navigate("/dashboard")}>
            ← กลับ Dashboard
          </button>
        }
      />
      <ErrorBox message={error || pendingError} />
      <div className="grid two return-putaway-layout">
        <article className="panel return-product-card">
          <p className="eyebrow">RETURNED HANDLING UNIT</p>
          <div className="return-product-title">
            <PackageOpen size={34} />
            <div>
              <h3>{huCode}</h3>
              <span className="status shipment-returned">RETURN HOLD</span>
            </div>
          </div>
          {item ? (
            <dl>
              <dt>สินค้า</dt>
              <dd>
                <b>{item.sku}</b>
                <small>{item.product_name}</small>
              </dd>
              <dt>จำนวน</dt>
              <dd>
                {item.quantity} {item.unit_of_measure}
              </dd>
              <dt>Return Station</dt>
              <dd>
                <code>{item.return_station_code}</code>
              </dd>
              <dt>Shipment</dt>
              <dd>{item.shipment_no || "-"}</dd>
            </dl>
          ) : (
            <p className="helper">กำลังโหลดข้อมูลสินค้าคืน...</p>
          )}
        </article>
        <article className="panel">
          <div className="return-storage-note">
            <b>ตำแหน่งแนะนำ: RETURN AREA</b>
            <span>
              เหมาะสำหรับสินค้าของบริษัทอื่น สินค้ารอตรวจสอบ
              หรือรอจัดส่งคืนต้นทาง หากเป็นสินค้าภายใน สามารถเลือก Zone
              ปกติที่รองรับสินค้าได้
            </span>
          </div>
          {selected && (
            <>
              <div className="return-zone-choice">
                <span
                  className={
                    selected.zone_code === "RTN" ? "recommended" : "normal"
                  }
                >
                  {selected.zone_code === "RTN"
                    ? "RETURN AREA · แนะนำ"
                    : "NORMAL STORAGE · ชั้นปกติ"}
                </span>
              </div>
              <div className="putaway-path">
                <label>
                  <span>1 · Zone</span>
                  <select
                    value={selected.zone_id}
                    onChange={(e) =>
                      selectFirst(
                        (location) => location.zone_id === +e.target.value,
                      )
                    }
                  >
                    {zoneIds.map((id) => {
                      const location = options.find(
                        (row) => row.zone_id === id,
                      );
                      return (
                        <option value={id} key={id}>
                          {location?.zone_code === "RTN" ? "★ " : ""}
                          {location?.zone_code || `Zone ${id}`}
                          {location?.zone_code === "RTN"
                            ? " · Return / Supplier Hold"
                            : ""}
                        </option>
                      );
                    })}
                  </select>
                </label>
                <label>
                  <span>2 · Rack</span>
                  <select
                    value={selected.rack_id}
                    onChange={(e) =>
                      selectFirst(
                        (location) =>
                          location.zone_id === selected.zone_id &&
                          location.rack_id === +e.target.value,
                      )
                    }
                  >
                    {rackIds.map((id) => (
                      <option value={id} key={id}>
                        {options.find((row) => row.rack_id === id)?.rack_code ||
                          `Rack ${id}`}
                      </option>
                    ))}
                  </select>
                </label>
                <label>
                  <span>3 · Bay</span>
                  <select
                    value={selected.bay_no}
                    onChange={(e) =>
                      selectFirst(
                        (location) =>
                          location.zone_id === selected.zone_id &&
                          location.rack_id === selected.rack_id &&
                          location.bay_no === +e.target.value,
                      )
                    }
                  >
                    {bayNumbers.map((value) => (
                      <option value={value} key={value}>
                        Bay {String(value).padStart(3, "0")}
                      </option>
                    ))}
                  </select>
                </label>
                <label>
                  <span>4 · Level</span>
                  <select
                    value={selected.level_no}
                    onChange={(e) =>
                      selectFirst(
                        (location) =>
                          location.zone_id === selected.zone_id &&
                          location.rack_id === selected.rack_id &&
                          location.bay_no === selected.bay_no &&
                          location.level_no === +e.target.value,
                      )
                    }
                  >
                    {levelNumbers.map((value) => (
                      <option value={value} key={value}>
                        Level {String(value).padStart(2, "0")}
                      </option>
                    ))}
                  </select>
                </label>
                <label>
                  <span>5 · Position</span>
                  <select
                    value={selected.id}
                    onChange={(e) => setSelectedLocationId(+e.target.value)}
                  >
                    {positions.map((location) => (
                      <option value={location.id} key={location.id}>
                        Position {String(location.position_no).padStart(2, "0")}
                      </option>
                    ))}
                  </select>
                </label>
              </div>
              <div className="selected-return-location">
                <span>ตำแหน่งที่จะจัดเก็บ</span>
                <b>{selected.location_code}</b>
                <small>
                  {selected.zone_code === "RTN"
                    ? "สินค้าจะถูกกักไว้ใน Return Area และยังไม่นับเป็นสินค้าพร้อมเบิก"
                    : "สินค้าจะกลับเป็นสต็อกภายในที่พร้อมใช้งาน"}
                </small>
              </div>
              <button
                className="button wide"
                disabled={saving}
                onClick={confirm}
              >
                {saving ? "กำลังจัดเก็บ..." : "ยืนยันจัดเก็บเข้าชั้น"}
              </button>
            </>
          )}
          {!selected && !error && (
            <div className="empty">กำลังค้นหาตำแหน่งจัดเก็บที่ว่าง...</div>
          )}
        </article>
      </div>
    </section>
  );
}

function WarehouseMap() {
  const { data, error } = useLoad<WarehouseMapData | null>(
    "/warehouse-map/live",
    null,
  );
  return (
    <section>
      <PageTitle
        eyebrow="LIVE WAREHOUSE LAYOUT"
        title="แผนผังคลังสินค้า"
        desc="สถานะ Rack, Location และ Handling Unit จากข้อมูลจริง"
      />
      <ErrorBox message={error} />
      {data && (
        <div className="map-board live-map">
          <div className="map-top">
            <div>
              <span className="map-label">{data.warehouse.warehouse_code}</span>
              <h3>{data.warehouse.warehouse_name}</h3>
            </div>
            <div className="dock-row">
              {data.docks.map((x) => (
                <div className={`dock ${x.status.toLowerCase()}`} key={x.id}>
                  <DoorOpen />{" "}
                  <span>
                    {x.dock_code}
                    <small>{x.status}</small>
                  </span>
                </div>
              ))}
            </div>
          </div>
          <div className="legend map-legend">
            <span>
              <i className="available" />
              ว่าง
            </span>
            <span>
              <i className="occupied" />
              มีสินค้า
            </span>
            <span>
              <i className="reserved" />
              จองแล้ว
            </span>
            <span>
              <i className="blocked" />
              ระงับ
            </span>
          </div>
          <div className="live-zone-grid">
            {data.zones.map((zone) => (
              <article className="live-zone" key={zone.id}>
                <header>
                  <div>
                    <span>ZONE</span>
                    <strong>{zone.zone_code}</strong>
                    <p>{zone.zone_name}</p>
                  </div>
                  <div className="zone-util">
                    <b>{zone.utilization_percent}%</b>
                    <small>UTILIZATION</small>
                  </div>
                </header>
                <div className="zone-progress">
                  <i style={{ width: `${zone.utilization_percent}%` }} />
                </div>
                <div className="zone-stats">
                  <span>
                    <b>{zone.occupied}</b> Occupied
                  </span>
                  <span>
                    <b>{zone.reserved}</b> Reserved
                  </span>
                  <span>
                    <b>{zone.available}</b> Available
                  </span>
                </div>
                <div className="live-racks">
                  {zone.racks.map((rack) => (
                    <NavLink
                      to={`/racks/${rack.id}/map`}
                      className={`live-rack ${rack.blocked === rack.total ? "blocked" : rack.reserved ? "reserved" : rack.occupied ? "occupied" : "available"}`}
                      key={rack.id}
                    >
                      <div className="rack-title">
                        <b>{rack.rack_code}</b>
                        <span>{rack.hu_count} HU</span>
                      </div>
                      <div className="rack-capacity">
                        <i style={{ width: `${rack.utilization_percent}%` }} />
                      </div>
                      <small>
                        {rack.occupied + rack.reserved}/{rack.total} locations
                      </small>
                      {rack.products.length > 0 ? (
                        <div className="rack-products">
                          {rack.products.map((p) => (
                            <span key={p.sku}>
                              {p.sku} · {p.quantity}
                            </span>
                          ))}
                        </div>
                      ) : (
                        <em>Empty rack</em>
                      )}
                      <ChevronRight size={15} />
                    </NavLink>
                  ))}
                </div>
              </article>
            ))}
          </div>
          <div className="live-stations">
            <h3>Operation Stations</h3>
            <div>
              {data.stations.map((s) => (
                <article
                  className={`station-live ${s.station_type.toLowerCase()}`}
                  key={s.id}
                >
                  <PackageOpen size={20} />
                  <span>
                    <b>{s.station_code}</b>
                    <small>{s.station_name}</small>
                  </span>
                  <strong>
                    {s.hu_count}/{s.capacity_hu} HU
                  </strong>
                </article>
              ))}
            </div>
          </div>
        </div>
      )}
    </section>
  );
}

function PageTitle({
  eyebrow,
  title,
  desc,
  action,
}: {
  eyebrow: string;
  title: string;
  desc: string;
  action?: React.ReactNode;
}) {
  return (
    <div className="page-head">
      <div>
        <p className="eyebrow">{eyebrow}</p>
        <h2>{title}</h2>
        <p>{desc}</p>
      </div>
      {action}
    </div>
  );
}
function Modal({
  title,
  onClose,
  children,
}: {
  title: string;
  onClose: () => void;
  children: React.ReactNode;
}) {
  return (
    <div className="modal-bg">
      <div className="modal">
        <div className="modal-head">
          <h3>{title}</h3>
          <button onClick={onClose}>
            <X />
          </button>
        </div>
        {children}
      </div>
    </div>
  );
}
function Field({
  label,
  ...props
}: { label: string } & React.InputHTMLAttributes<HTMLInputElement>) {
  return (
    <label>
      <span>{label}</span>
      <input {...props} />
    </label>
  );
}

function Racks() {
  const q = new URLSearchParams(location.search);
  const zone = q.get("zone");
  const {
    data: racks,
    error,
    load,
  } = useLoad<Rack[]>(`/racks${zone ? `?zone_id=${zone}` : ""}`, []);
  const { data: zones } = useLoad<Zone[]>("/zones", []);
  const [show, setShow] = useState(false);
  const [form, setForm] = useState({
    zone_id: 1,
    aisle_no: 1,
    rack_no: 1,
    rack_name: "",
    bay_count: 6,
    level_count: 6,
    positions_per_level: 2,
  });
  const [formError, setFormError] = useState("");
  async function submit(e: React.FormEvent) {
    e.preventDefault();
    try {
      await post("/racks", form);
      setShow(false);
      load();
    } catch (e) {
      setFormError((e as Error).message);
    }
  }
  return (
    <section>
      <PageTitle
        eyebrow="STORAGE STRUCTURE"
        title="ชั้นวางสินค้า"
        desc="กำหนด Bay, Level และ Position ตามการใช้งานจริง"
        action={
          <button
            className="button"
            onClick={() => {
              setForm((f) => ({ ...f, zone_id: zones[0]?.id || 1 }));
              setShow(true);
            }}
          >
            <Plus size={17} /> เพิ่ม Rack
          </button>
        }
      />
      <ErrorBox message={error} />
      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th>RACK</th>
              <th>ZONE</th>
              <th>AISLE</th>
              <th>ขนาด</th>
              <th>ตำแหน่ง</th>
              <th>สถานะ</th>
              <th />
            </tr>
          </thead>
          <tbody>
            {racks.map((r) => (
              <tr key={r.id}>
                <td>
                  <b>
                    A{String(r.aisle_no).padStart(2, "0")}-R
                    {String(r.rack_no).padStart(2, "0")}
                  </b>
                  <small>{r.rack_name}</small>
                </td>
                <td>
                  {zones.find((z) => z.id === r.zone_id)?.zone_code || "-"}
                </td>
                <td>{r.aisle_no}</td>
                <td>
                  {r.bay_count} Bay × {r.level_count} Level ×{" "}
                  {r.positions_per_level} Pos.
                </td>
                <td>
                  <b>{r.location_count.toLocaleString()}</b>
                </td>
                <td>
                  <span className="status active">ACTIVE</span>
                </td>
                <td>
                  <NavLink className="icon-button" to={`/racks/${r.id}/map`}>
                    <Map size={17} />
                  </NavLink>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        {!racks.length && <div className="empty">ยังไม่มี Rack ในโซนนี้</div>}
      </div>
      {show && (
        <Modal
          title="สร้าง Rack และตำแหน่งจัดเก็บ"
          onClose={() => setShow(false)}
        >
          <form onSubmit={submit}>
            <label>
              <span>โซน</span>
              <select
                value={form.zone_id}
                onChange={(e) => setForm({ ...form, zone_id: +e.target.value })}
              >
                {zones.map((z) => (
                  <option value={z.id} key={z.id}>
                    {z.zone_code} · {z.zone_name}
                  </option>
                ))}
              </select>
            </label>
            <div className="form-grid">
              <Field
                label="Aisle No."
                type="number"
                min="1"
                value={form.aisle_no}
                onChange={(e) =>
                  setForm({ ...form, aisle_no: +e.target.value })
                }
              />
              <Field
                label="Rack No."
                type="number"
                min="1"
                value={form.rack_no}
                onChange={(e) => setForm({ ...form, rack_no: +e.target.value })}
              />
              <Field
                label="จำนวน Bay"
                type="number"
                min="1"
                value={form.bay_count}
                onChange={(e) =>
                  setForm({ ...form, bay_count: +e.target.value })
                }
              />
              <Field
                label="จำนวน Level"
                type="number"
                min="1"
                value={form.level_count}
                onChange={(e) =>
                  setForm({ ...form, level_count: +e.target.value })
                }
              />
              <Field
                label="Position / Level"
                type="number"
                min="1"
                value={form.positions_per_level}
                onChange={(e) =>
                  setForm({ ...form, positions_per_level: +e.target.value })
                }
              />
              <Field
                label="ชื่อ Rack"
                value={form.rack_name}
                onChange={(e) =>
                  setForm({ ...form, rack_name: e.target.value })
                }
              />
            </div>
            <ErrorBox message={formError} />
            <button className="button wide">สร้าง Rack และ Location</button>
          </form>
        </Modal>
      )}
    </section>
  );
}

function RackMap() {
  const { id } = useParams();
  const nav = useNavigate();
  const {
    data: locations,
    error,
    load,
  } = useLoad<Location[]>(`/racks/${id}/locations`, []);
  const [selected, setSelected] = useState<Location | null>(null);
  const [actionHU, setActionHU] = useState("");
  const levels = useMemo(
    () =>
      [...new Set(locations.map((x) => x.level_no || 0))].sort((a, b) => b - a),
    [locations],
  );
  const bays = useMemo(
    () =>
      [...new Set(locations.map((x) => x.bay_no || 0))].sort((a, b) => a - b),
    [locations],
  );
  const gridStyle = { "--bays": bays.length } as React.CSSProperties;
  return (
    <section>
      <PageTitle
        eyebrow="RACK VISUALIZATION"
        title="แผนผัง Rack 2D"
        desc={`${locations.length.toLocaleString()} ตำแหน่ง · คลิกช่องเพื่อดูสินค้าและ HU`}
        action={
          <button className="ghost" onClick={() => nav("/warehouse-map")}>
            ← Warehouse Map
          </button>
        }
      />
      <ErrorBox message={error} />
      <div className="legend">
        <span>
          <i className="available" />
          ว่าง
        </span>
        <span>
          <i className="occupied" />
          มีสินค้า
        </span>
        <span>
          <i className="reserved" />
          จองแล้ว
        </span>
        <span>
          <i className="blocked" />
          ระงับ
        </span>
      </div>
      <div className="rack-map">
        <div className="rack-scroll">
          <div className="rack-header" style={gridStyle}>
            <b>LEVEL</b>
            {bays.map((b) => (
              <b key={b}>BAY {String(b).padStart(2, "0")}</b>
            ))}
          </div>
          {levels.map((level) => (
            <div className="rack-level" style={gridStyle} key={level}>
              <strong>L{String(level).padStart(2, "0")}</strong>
              {bays.map((bay) => (
                <div className="positions" key={bay}>
                  {locations
                    .filter((x) => x.level_no === level && x.bay_no === bay)
                    .map((x) => (
                      <button
                        title={
                          x.hu_code
                            ? `${x.location_code} · ${x.hu_code} · ${x.sku}`
                            : x.location_code
                        }
                        className={`slot ${x.status.toLowerCase()} ${selected?.id === x.id ? "selected" : ""}`}
                        key={x.id}
                        onClick={() => setSelected(x)}
                      >
                        P{x.position_no}
                        {x.hu_code && <i />}
                      </button>
                    ))}
                </div>
              ))}
            </div>
          ))}
        </div>
        {selected && (
          <aside className="location-detail">
            <p className="eyebrow">SELECTED LOCATION</p>
            <h3>{selected.location_code}</h3>
            <dl>
              <dt>Bay</dt>
              <dd>{selected.bay_no}</dd>
              <dt>Level</dt>
              <dd>{selected.level_no}</dd>
              <dt>Position</dt>
              <dd>{selected.position_no}</dd>
              <dt>Status</dt>
              <dd>
                <span className={`status ${selected.status.toLowerCase()}`}>
                  {selected.status}
                </span>
              </dd>
              {selected.hu_code && (
                <>
                  <dt>Handling Unit</dt>
                  <dd>{selected.hu_code}</dd>
                  <dt>SKU</dt>
                  <dd>{selected.sku}</dd>
                  <dt>Product</dt>
                  <dd>{selected.product_name}</dd>
                  <dt>Quantity</dt>
                  <dd>
                    {selected.quantity} {selected.unit_of_measure}
                  </dd>
                  <dt>Reserved</dt>
                  <dd>{selected.reserved_quantity || 0}</dd>
                </>
              )}
            </dl>
            {selected.hu_code && (
              <button
                className="button wide"
                onClick={() => setActionHU(selected.hu_code!)}
              >
                ดำเนินการสินค้าจากชั้นนี้
              </button>
            )}
            {!selected.hu_code && (
              <p className="empty-location">ตำแหน่งนี้ว่าง พร้อมใช้งาน</p>
            )}
          </aside>
        )}
      </div>
      {actionHU && (
        <HUActions
          code={actionHU}
          onClose={() => setActionHU("")}
          onChanged={() => {
            load();
            setSelected(null);
          }}
        />
      )}
    </section>
  );
}

function Stations() {
  const { data: items, error, load } = useLoad<Station[]>("/stations", []);
  const { data: warehouses } = useLoad<Warehouse[]>("/warehouses", []);
  const [show, setShow] = useState(false);
  const [form, setForm] = useState({
    warehouse_id: 1,
    station_name: "",
    station_type: "INBOUND",
    capacity_hu: 20,
    sequence: 1,
  });
  const [err, setErr] = useState("");
  async function submit(e: React.FormEvent) {
    e.preventDefault();
    try {
      await post("/stations", form);
      setShow(false);
      load();
    } catch (e) {
      setErr((e as Error).message);
    }
  }
  return (
    <section>
      <PageTitle
        eyebrow="OPERATION NODES"
        title="จุดรับ–จ่ายสินค้า"
        desc="ทุก Station เป็นตำแหน่งจริงที่ติดตามการเคลื่อนย้ายได้"
        action={
          <button
            className="button"
            onClick={() => {
              setForm((f) => ({ ...f, warehouse_id: warehouses[0]?.id || 1 }));
              setShow(true);
            }}
          >
            <Plus size={17} /> เพิ่ม Station
          </button>
        }
      />
      <ErrorBox message={error} />
      <div className="card-grid">
        {items.map((s) => (
          <article
            className={`station-card ${s.station_type.toLowerCase()}`}
            key={s.id}
          >
            <div className="station-icon">
              <PackageOpen />
            </div>
            <span className="status active">{s.status}</span>
            <p>{s.station_type}</p>
            <h3>{s.station_name}</h3>
            <code>{s.station_code}</code>
            <div className="capacity">
              <span>ความจุ</span>
              <b>{s.capacity_hu} HU</b>
            </div>
          </article>
        ))}
      </div>
      {show && (
        <Modal title="เพิ่มจุดปฏิบัติงาน" onClose={() => setShow(false)}>
          <form onSubmit={submit}>
            <Field
              required
              label="ชื่อ Station"
              value={form.station_name}
              onChange={(e) =>
                setForm({ ...form, station_name: e.target.value })
              }
            />
            <label>
              <span>ประเภท</span>
              <select
                value={form.station_type}
                onChange={(e) =>
                  setForm({ ...form, station_type: e.target.value })
                }
              >
                <option>INBOUND</option>
                <option>CHECKOUT</option>
                <option>LOADOUT</option>
                <option>RETURN</option>
              </select>
            </label>
            <div className="form-grid">
              <Field
                label="ลำดับ"
                type="number"
                min="1"
                value={form.sequence}
                onChange={(e) =>
                  setForm({ ...form, sequence: +e.target.value })
                }
              />
              <Field
                label="ความจุ HU"
                type="number"
                min="1"
                value={form.capacity_hu}
                onChange={(e) =>
                  setForm({ ...form, capacity_hu: +e.target.value })
                }
              />
            </div>
            <ErrorBox message={err} />
            <button className="button wide">สร้าง Station</button>
          </form>
        </Modal>
      )}
    </section>
  );
}

function Docks() {
  const { data: items, error, load } = useLoad<Dock[]>("/loading-docks", []);
  const { data: warehouses } = useLoad<Warehouse[]>("/warehouses", []);
  const [show, setShow] = useState(false);
  const [form, setForm] = useState({
    warehouse_id: 1,
    dock_name: "",
    capacity_vehicle: 1,
    sequence: 1,
  });
  const [err, setErr] = useState("");
  async function submit(e: React.FormEvent) {
    e.preventDefault();
    try {
      await post("/loading-docks", form);
      setShow(false);
      load();
    } catch (e) {
      setErr((e as Error).message);
    }
  }
  return (
    <section>
      <PageTitle
        eyebrow="LOGISTICS HANDOFF"
        title="Loading Docks"
        desc="พื้นที่ส่งมอบระหว่างคลังสินค้าและยานพาหนะ"
        action={
          <button
            className="button"
            onClick={() => {
              setForm((f) => ({ ...f, warehouse_id: warehouses[0]?.id || 1 }));
              setShow(true);
            }}
          >
            <Plus size={17} /> เพิ่ม Dock
          </button>
        }
      />
      <ErrorBox message={error} />
      <div className="dock-cards">
        {items.map((d) => (
          <article key={d.id}>
            <div className="dock-visual">
              <DoorOpen size={52} />
              <span>{d.dock_code}</span>
            </div>
            <div>
              <span className="status active">{d.status}</span>
              <h3>{d.dock_name}</h3>
              <p>รองรับพร้อมกัน {d.capacity_vehicle} คัน</p>
            </div>
          </article>
        ))}
      </div>
      {show && (
        <Modal title="เพิ่ม Loading Dock" onClose={() => setShow(false)}>
          <form onSubmit={submit}>
            <Field
              required
              label="ชื่อ Loading Dock"
              value={form.dock_name}
              onChange={(e) => setForm({ ...form, dock_name: e.target.value })}
            />
            <div className="form-grid">
              <Field
                label="ลำดับ"
                type="number"
                min="1"
                value={form.sequence}
                onChange={(e) =>
                  setForm({ ...form, sequence: +e.target.value })
                }
              />
              <Field
                label="ความจุรถ"
                type="number"
                min="1"
                value={form.capacity_vehicle}
                onChange={(e) =>
                  setForm({ ...form, capacity_vehicle: +e.target.value })
                }
              />
            </div>
            <ErrorBox message={err} />
            <button className="button wide">สร้าง Loading Dock</button>
          </form>
        </Modal>
      )}
    </section>
  );
}

function MasterDataPage() {
  const { data: products, load: loadProducts } = useLoad<Product[]>(
    "/products",
    [],
  );
  const { data: customers, load: loadCustomers } = useLoad<Customer[]>(
    "/customers",
    [],
  );
  const { data: vehicles, load: loadVehicles } = useLoad<Vehicle[]>(
    "/vehicles",
    [],
  );
  const { data: drivers, load: loadDrivers } = useLoad<Driver[]>(
    "/drivers",
    [],
  );
  const [kind, setKind] = useState("");
  const [form, setForm] = useState<Record<string, string>>({});
  const [err, setErr] = useState("");
  const configs: Record<
    string,
    { title: string; fields: string[]; path: string; reload: () => void }
  > = {
    product: {
      title: "เพิ่มสินค้า",
      fields: ["sku", "product_name", "barcode", "size_class"],
      path: "/products",
      reload: loadProducts,
    },
    customer: {
      title: "เพิ่มลูกค้า",
      fields: ["customer_code", "customer_name", "phone", "address_line1", "province"],
      path: "/customers",
      reload: loadCustomers,
    },
    vehicle: {
      title: "เพิ่มรถ",
      fields: ["vehicle_code", "license_plate", "vehicle_type"],
      path: "/vehicles",
      reload: loadVehicles,
    },
    driver: {
      title: "เพิ่มคนขับ",
      fields: ["driver_code", "first_name", "last_name", "phone"],
      path: "/drivers",
      reload: loadDrivers,
    },
  };
  async function submit(e: React.FormEvent) {
    e.preventDefault();
    const cfg = configs[kind];
    try {
      await post(cfg.path, form);
      cfg.reload();
      setKind("");
      setForm({});
    } catch (e) {
      setErr((e as Error).message);
    }
  }
  const cards = [
    {
      kind: "product",
      label: "Products",
      count: products.length,
      items: products.slice(0, 4).map((x) => `${x.sku} · ${x.product_name}`),
    },
    {
      kind: "customer",
      label: "Customers",
      count: customers.length,
      items: customers
        .slice(0, 4)
        .map((x) => `${x.customer_code} · ${x.customer_name} · โทร ${x.phone || 'ยังไม่ระบุ'}`),
    },
    {
      kind: "vehicle",
      label: "Vehicles",
      count: vehicles.length,
      items: vehicles
        .slice(0, 4)
        .map((x) => `${x.vehicle_code} · ${x.license_plate}`),
    },
    {
      kind: "driver",
      label: "Drivers",
      count: drivers.length,
      items: drivers
        .slice(0, 4)
        .map((x) => `${x.driver_code} · ${x.first_name} ${x.last_name}`),
    },
  ];
  return (
    <section>
      <PageTitle
        eyebrow="MASTER DATA"
        title="ข้อมูลหลัก"
        desc="สินค้า ลูกค้า รถขนส่ง และพนักงานขับรถ"
      />
      <div className="master-grid">
        {cards.map((c) => (
          <article className="panel" key={c.kind}>
            <span className="count">{c.count}</span>
            <h3>{c.label}</h3>
            {c.items.map((x, i) => (
              <p key={i}>{x}</p>
            ))}
            <button
              className="ghost wide"
              onClick={() => {
                setKind(c.kind);
                setForm({});
                setErr("");
              }}
            >
              <Plus size={15} /> เพิ่มข้อมูล
            </button>
          </article>
        ))}
      </div>
      {kind && (
        <Modal title={configs[kind].title} onClose={() => setKind("")}>
          <form onSubmit={submit}>
            {configs[kind].fields.map((field) => (
              <Field
                required={!["barcode", "province"].includes(field) && !(kind === "customer" && field === "phone")}
                key={field}
                label={kind === 'customer' ? ({customer_code:'รหัสลูกค้า',customer_name:'ชื่อลูกค้า',phone:'เบอร์โทรลูกค้า',address_line1:'ที่อยู่จัดส่ง',province:'จังหวัด'}[field] || field) : field.replaceAll("_", " ").toUpperCase()}
                type={field === 'phone' ? 'tel' : 'text'}
                autoComplete={field === 'phone' ? 'tel' : undefined}
                maxLength={field === 'phone' ? 40 : undefined}
                value={form[field] || ""}
                onChange={(e) => setForm({ ...form, [field]: e.target.value })}
              />
            ))}
            <ErrorBox message={err} />
            <button className="button wide">บันทึก</button>
          </form>
        </Modal>
      )}
    </section>
  );
}

function InventoryPage() {
  return <InventoryWorkflowPage />;
}

function InboundPage() {
  const [activeHU, setActiveHU] = useState("");
  const [autoCode, setAutoCode] = useState(true);
  const [receiving, setReceiving] = useState(false);
  async function newCode() {
    try {
      const value = await api<{ hu_code: string }>("/inbound/hu-code");
      setForm((current) => ({ ...current, hu_code: value.hu_code }));
      setAutoCode(true);
    } catch (e) {
      setError((e as Error).message);
    }
  }
  useEffect(() => {
    void newCode();
  }, []);
  const {
    data: products,
    loading: productsLoading,
    error: productsError,
    reload: loadProducts,
  } = useResource<Product[]>("/products", []);
  const {
    data: stations,
    loading: stationsLoading,
    error: stationsError,
    reload: loadStations,
  } = useResource<Station[]>("/stations", []);
  const {
    data: pending,
    error: pendingError,
    load: loadPending,
  } = useLoad<PendingPutaway[]>("/putaway/pending", []);
  const [form, setForm] = useState({
    product_id: 0,
    hu_code: "",
    hu_type: "PALLET",
    quantity: 100,
    unit_of_measure: "EA",
    station_id: 0,
    lot_no: "",
    batch_no: "",
  });
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const activeProducts = products.filter((p) => p.is_active);
  const inboundStations = stations.filter(
    (s) => s.station_type === "INBOUND" && s.is_active,
  );
  const stationId = form.station_id || inboundStations[0]?.id || 0;
  const selectedProduct = activeProducts.find((p) => p.id === form.product_id);
  const canReceive =
    !!selectedProduct &&
    inboundStations.some((s) => s.id === stationId) &&
    !productsLoading &&
    !stationsLoading &&
    !productsError &&
    !stationsError;
  const [options, setOptions] = useState<Location[]>([]);
  const [selectedLocationId, setSelectedLocationId] = useState(0);
  const recommended = options[0];
  const selected =
    options.find((x) => x.id === selectedLocationId) || recommended;
  const unique = <T,>(values: T[]) => [...new Set(values)];
  const zoneIds = unique(
    options.map((x) => x.zone_id).filter((x): x is number => x !== undefined),
  );
  const rackIds = unique(
    options
      .filter((x) => x.zone_id === selected?.zone_id)
      .map((x) => x.rack_id)
      .filter((x): x is number => x !== undefined),
  );
  const bayNumbers = unique(
    options
      .filter(
        (x) =>
          x.zone_id === selected?.zone_id && x.rack_id === selected?.rack_id,
      )
      .map((x) => x.bay_no)
      .filter((x): x is number => x !== undefined),
  );
  const levelNumbers = unique(
    options
      .filter(
        (x) =>
          x.zone_id === selected?.zone_id &&
          x.rack_id === selected?.rack_id &&
          x.bay_no === selected?.bay_no,
      )
      .map((x) => x.level_no)
      .filter((x): x is number => x !== undefined),
  );
  const positions = options.filter(
    (x) =>
      x.zone_id === selected?.zone_id &&
      x.rack_id === selected?.rack_id &&
      x.bay_no === selected?.bay_no &&
      x.level_no === selected?.level_no,
  );
  const selectFirst = (predicate: (location: Location) => boolean) => {
    const location = options.find(predicate);
    if (location) setSelectedLocationId(location.id);
  };
  async function loadOptions(huCode: string) {
    setError("");
    try {
      const choices = await post<Location[]>("/putaway/options", {
        hu_code: huCode,
      });
      setOptions(choices);
      setSelectedLocationId(choices[0]?.id || 0);
    } catch (e) {
      setOptions([]);
      setSelectedLocationId(0);
      setError((e as Error).message);
    }
  }
  async function receiveHU(e: React.FormEvent) {
    e.preventDefault();
    if (receiving) return;
    if (!canReceive) {
      setError("กรุณาเลือกสินค้าที่เปิดใช้งานและสถานีรับเข้าที่พร้อมใช้งาน");
      return;
    }
    setReceiving(true);
    setError("");
    setMessage("");
    setOptions([]);
    setSelectedLocationId(0);
    try {
      const data = await post<{ hu_code: string }>("/inbound/receive", {
        ...form,
        auto_hu_code: autoCode,
        product_id: selectedProduct!.id,
        station_id: stationId,
      });
      setMessage(`รับ ${data.hu_code} เข้าคลังแล้ว กรุณาเลือกตำแหน่งจัดเก็บ`);
      setActiveHU(data.hu_code);
      await newCode();
      loadPending();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setReceiving(false);
    }
  }
  async function suggest() {
    await loadOptions(activeHU);
  }
  async function continuePutaway(item: PendingPutaway) {
    setActiveHU(item.hu_code);
    setMessage(`กำลังเลือกตำแหน่งสำหรับ ${item.hu_code}`);
    await loadOptions(item.hu_code);
    window.scrollTo({ top: 0, behavior: "smooth" });
  }
  async function confirm() {
    if (!selected) return;
    setError("");
    try {
      await post("/putaway/confirm", {
        hu_code: activeHU,
        destination_location_id: selected.id,
      });
      setMessage(`${activeHU} จัดเก็บที่ ${selected.location_code} สำเร็จ`);
      setActiveHU("");
      setOptions([]);
      setSelectedLocationId(0);
      loadPending();
    } catch (e) {
      setError((e as Error).message);
    }
  }
  return (
    <section>
      <PageTitle
        eyebrow="INBOUND OPERATION"
        title="รับสินค้าและ Putaway"
        desc="สแกน HU รับเข้าจุด Inbound แล้วเลือกตำแหน่งที่รองรับ Storage Profile"
      />
      {stationsError && (
        <div className="error" role="alert">
          โหลดสถานีรับเข้าไม่สำเร็จ: {stationsError}
          <button className="ghost" onClick={() => void loadStations()}>
            โหลดสถานีใหม่
          </button>
        </div>
      )}
      {!stationsLoading && !stationsError && !inboundStations.length && (
        <div className="pro-notice info">
          ยังไม่มีสถานี Inbound ที่เปิดใช้งาน กรุณาเตรียมสถานีรับเข้าก่อน
        </div>
      )}
      <div className="grid two">
        <article className="panel">
          <h3>1 · Receive Handling Unit</h3>
          <form onSubmit={receiveHU}>
            <InboundProductPicker
              products={products}
              loading={productsLoading}
              error={productsError}
              value={form.product_id}
              onSelect={(id) =>
                setForm((current) => ({ ...current, product_id: id }))
              }
              onReload={() => void loadProducts()}
              onCreated={async (product) => {
                await loadProducts();
                setForm((current) => ({ ...current, product_id: product.id }));
                setMessage(
                  "เพิ่มสินค้า " +
                    product.product_name +
                    " แล้ว กรุณาตรวจจำนวนและยืนยันรับเข้า",
                );
              }}
            />
            <div className="form-grid">
              <Field
                required
                label="HU Code"
                value={form.hu_code}
                onChange={(e) => {
                  setForm({ ...form, hu_code: e.target.value });
                  setAutoCode(false);
                }}
              />
              <label>
                <span>Inbound Station</span>
                <select
                  required
                  disabled={stationsLoading || !inboundStations.length}
                  value={stationId || ""}
                  onChange={(e) =>
                    setForm({ ...form, station_id: +e.target.value })
                  }
                >
                  <option value="">เลือก Station</option>
                  {inboundStations.map((x) => (
                    <option value={x.id} key={x.id}>
                      {x.station_code}
                    </option>
                  ))}
                </select>
              </label>
              <Field
                label="จำนวน"
                type="number"
                min="1"
                value={form.quantity}
                onChange={(e) =>
                  setForm({ ...form, quantity: +e.target.value })
                }
              />
              <Field
                label="Lot No."
                value={form.lot_no}
                onChange={(e) => setForm({ ...form, lot_no: e.target.value })}
              />
            </div>
            <p className="helper">
              {autoCode
                ? "ระบบแนะนำรหัสใหม่ให้อัตโนมัติ · พิมพ์แก้ไขเองได้"
                : "กำลังใช้รหัสที่ระบุเอง · ระบบตรวจไม่ให้ซ้ำ"}
            </p>
            <button
              type="button"
              className="ghost"
              disabled={receiving}
              onClick={() => void newCode()}
            >
              แนะนำ HU Code ใหม่
            </button>
            <button className="button wide" disabled={receiving || !canReceive}>
              {receiving ? "กำลังรับสินค้า…" : "ยืนยันรับสินค้า"}
            </button>
          </form>
        </article>
        <article className="panel">
          <h3>2 · Putaway</h3>
          {activeHU && (
            <p className="helper">
              HU ที่เลือก: <b>{activeHU}</b>
            </p>
          )}
          <p className="helper">
            ระบบแนะนำตำแหน่งเริ่มต้น
            และให้เลือกทีละจุดเฉพาะช่องว่างที่รองรับสินค้า
          </p>
          <button
            className="button wide"
            disabled={!activeHU}
            onClick={suggest}
          >
            ค้นหาตำแหน่งจัดเก็บ
          </button>
          {recommended && selected && (
            <div className="recommend">
              <span>RECOMMENDED LOCATION</span>
              <b>{recommended.location_code}</b>
              <div className="putaway-path">
                <label>
                  <span>1 · Zone</span>
                  <select
                    value={selected.zone_id}
                    onChange={(e) =>
                      selectFirst((x) => x.zone_id === +e.target.value)
                    }
                  >
                    {zoneIds.map((id) => (
                      <option value={id} key={id}>
                        {options.find((x) => x.zone_id === id)?.zone_code ||
                          `Zone ${id}`}
                      </option>
                    ))}
                  </select>
                </label>
                <label>
                  <span>2 · Rack</span>
                  <select
                    value={selected.rack_id}
                    onChange={(e) =>
                      selectFirst(
                        (x) =>
                          x.zone_id === selected.zone_id &&
                          x.rack_id === +e.target.value,
                      )
                    }
                  >
                    {rackIds.map((id) => (
                      <option value={id} key={id}>
                        {options.find((x) => x.rack_id === id)?.rack_code ||
                          `Rack ${id}`}
                      </option>
                    ))}
                  </select>
                </label>
                <label>
                  <span>3 · Bay</span>
                  <select
                    value={selected.bay_no}
                    onChange={(e) =>
                      selectFirst(
                        (x) =>
                          x.zone_id === selected.zone_id &&
                          x.rack_id === selected.rack_id &&
                          x.bay_no === +e.target.value,
                      )
                    }
                  >
                    {bayNumbers.map((value) => (
                      <option value={value} key={value}>
                        Bay {String(value).padStart(3, "0")}
                      </option>
                    ))}
                  </select>
                </label>
                <label>
                  <span>4 · Level</span>
                  <select
                    value={selected.level_no}
                    onChange={(e) =>
                      selectFirst(
                        (x) =>
                          x.zone_id === selected.zone_id &&
                          x.rack_id === selected.rack_id &&
                          x.bay_no === selected.bay_no &&
                          x.level_no === +e.target.value,
                      )
                    }
                  >
                    {levelNumbers.map((value) => (
                      <option value={value} key={value}>
                        Level {String(value).padStart(2, "0")}
                      </option>
                    ))}
                  </select>
                </label>
                <label>
                  <span>5 · Position</span>
                  <select
                    value={selected.id}
                    onChange={(e) => setSelectedLocationId(+e.target.value)}
                  >
                    {positions.map((location) => (
                      <option value={location.id} key={location.id}>
                        Position {String(location.position_no).padStart(2, "0")}
                      </option>
                    ))}
                  </select>
                </label>
              </div>
              <div className="selected-putaway">
                <span>ตำแหน่งที่เลือก</span>
                <b>{selected.location_code}</b>
              </div>
              <button className="button" onClick={confirm}>
                ยืนยัน Putaway ที่เลือก
              </button>
            </div>
          )}
        </article>
      </div>
      <ErrorBox message={error || pendingError} />
      {message && <div className="success">{message}</div>}
      <article className="panel pending-putaway">
        <div className="pending-head">
          <div>
            <p className="eyebrow">PENDING PUTAWAY</p>
            <h3>สินค้ารอเลือกชั้นจัดเก็บ</h3>
          </div>
          <span>{pending.length} HU</span>
        </div>
        {pending.length ? (
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>HANDLING UNIT</th>
                  <th>สินค้า</th>
                  <th>จำนวน</th>
                  <th>จุดรับเข้า</th>
                  <th>รับเข้าเมื่อ</th>
                  <th />
                </tr>
              </thead>
              <tbody>
                {pending.map((item) => (
                  <tr key={item.hu_code}>
                    <td>
                      <b>{item.hu_code}</b>
                      <small>RECEIVED</small>
                    </td>
                    <td>
                      <b>{item.sku}</b>
                      <small>{item.product_name}</small>
                    </td>
                    <td>
                      {item.quantity} {item.unit_of_measure}
                    </td>
                    <td>
                      <code>{item.inbound_location_code}</code>
                    </td>
                    <td>
                      {new Date(item.received_at).toLocaleString("th-TH")}
                    </td>
                    <td>
                      <button
                        className="ghost continue-putaway"
                        onClick={() => continuePutaway(item)}
                      >
                        เลือกตำแหน่งจัดเก็บต่อ
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <div className="empty pending-empty">
            ไม่มีสินค้าค้างที่จุดรับเข้า
          </div>
        )}
      </article>
    </section>
  );
}

function ShipmentsPage() {
  const {
    data: shipments,
    error,
    load,
  } = useLoad<Shipment[]>("/shipments", []);
  const { data: customers } = useLoad<Customer[]>("/customers", []);
  const { data: products } = useLoad<Product[]>("/products", []);
  const { data: warehouses } = useLoad<Warehouse[]>("/warehouses", []);
  const [show, setShow] = useState(false);
  const [err, setErr] = useState("");
  const [form, setForm] = useState({
    customer_id: 0,
    product_id: 0,
    quantity: 100,
    vehicle_id: 0,
    driver_id: 0,
    loading_dock_id: 0,
  });
  async function submit(e: React.FormEvent) {
    e.preventDefault();
    try {
      await post("/shipments", {
        customer_id: form.customer_id || customers[0]?.id,
        origin_warehouse_id: warehouses[0]?.id,
        items: [
          {
            product_id: form.product_id || products[0]?.id,
            planned_quantity: form.quantity,
          },
        ],
      });
      setShow(false);
      load();
    } catch (e) {
      setErr((e as Error).message);
    }
  }
  return (
    <section>
      <PageTitle
        eyebrow="OUTBOUND LOGISTICS"
        title="การจัดส่ง"
        desc="ควบคุม Picking, Loading, Dispatch, Delivery และ Return"
        action={
          <button className="button" onClick={() => setShow(true)}>
            <Plus size={17} /> สร้าง Shipment
          </button>
        }
      />
      <ErrorBox message={error} />
      <ShipmentList shipments={shipments} />
      {show && (
        <Modal title="สร้าง Shipment" onClose={() => setShow(false)}>
          <form onSubmit={submit}>
            <label>
              <span>ลูกค้า</span>
              <select
                aria-label="ลูกค้า"
                value={form.customer_id}
                onChange={(e) =>
                  setForm({ ...form, customer_id: +e.target.value })
                }
              >
                {customers.map((x) => (
                  <option value={x.id} key={x.id}>
                    {x.customer_code} · {x.customer_name}
                  </option>
                ))}
              </select>
            </label>
            <label>
              <span>สินค้า (จัดส่งเต็ม HU)</span>
              <select
                value={form.product_id}
                onChange={(e) =>
                  setForm({ ...form, product_id: +e.target.value })
                }
              >
                {products.map((x) => (
                  <option value={x.id} key={x.id}>
                    {x.sku} · {x.product_name}
                  </option>
                ))}
              </select>
            </label>
            <Field
              label="จำนวน"
              type="number"
              min="1"
              value={form.quantity}
              onChange={(e) => setForm({ ...form, quantity: +e.target.value })}
            />
            <p className="helper">
              สร้างรายการส่งก่อนโดยไม่ผูกรถ หลังสินค้าอยู่ Loadout
              ให้จองและสแกนสินค้าที่หน้ารอบรถเท่านั้น
            </p>
            <ErrorBox message={err} />
            <button className="button wide">สร้าง Shipment</button>
          </form>
        </Modal>
      )}
    </section>
  );
}

function ShipmentDetail() {
  const { id } = useParams();
  const {
    data: s,
    error,
    load,
  } = useLoad<Shipment | null>(`/shipments/${id}`, null);
  const { data: locations } = useLoad<Location[]>(
    "/locations?location_type=STATION",
    [],
  );
  const { data: stations } = useLoad<Station[]>("/stations", []);
  const [checkoutStationId, setCheckoutStationId] = useState(0);
  const [loadoutStationId, setLoadoutStationId] = useState(0);
  const [err, setErr] = useState("");
  const act = async (path: string, body: unknown = {}) => {
    setErr("");
    try {
      await post(`/shipments/${id}/${path}`, body);
      load();
    } catch (e) {
      setErr((e as Error).message);
    }
  };
  if (!s)
    return (
      <section>
        <ErrorBox message={error} />
      </section>
    );
  const checkoutStations = stations.filter(
    (x) => x.station_type === "CHECKOUT" && x.is_active,
  );
  const loadoutStations = stations.filter(
    (x) => x.station_type === "LOADOUT" && x.is_active,
  );
  const checkoutId = checkoutStationId || checkoutStations[0]?.id;
  const loadoutId = loadoutStationId || loadoutStations[0]?.id;
  const checkoutLocation = locations.find((x) => x.station_id === checkoutId);
  const loadoutLocation = locations.find((x) => x.station_id === loadoutId);
  const returnStation = stations.find((x) => x.station_type === "RETURN");
  const allAtLoadout =
    s.items.length > 0 &&
    s.items.every((x) => x.current_station_type === "LOADOUT");
  const totalPlanned = s.items.reduce(
    (sum, item) => sum + item.planned_quantity,
    0,
  );
  const totalLoaded = s.items.reduce(
    (sum, item) => sum + item.loaded_quantity,
    0,
  );
  const totalDelivered = s.items.reduce(
    (sum, item) => sum + item.delivered_quantity,
    0,
  );
  const transactions = s.transactions || [];
  return (
    <section>
      <PageTitle
        eyebrow="DELIVERY TRIP CONTROL"
        title={s.shipment_no}
        desc={`${s.customer_name} · ${s.destination_name}`}
        action={
          <span className={`status shipment-${s.status.toLowerCase()}`}>
            {s.status}
          </span>
        }
      />
      <ErrorBox message={err || error} />
      {[
        "PLANNED",
        "PICKING",
        "READY_TO_LOAD",
        "LOADING",
        "LOADED",
        "DEPARTED",
        "IN_TRANSIT",
        "ARRIVED",
      ].includes(s.status) && (
        <ShipmentTransport shipment={s} />
      )}
      <article className="trip-overview">
        <div>
          <span>รถขนส่ง</span>
          <b>
            <Truck size={18} />
            {s.vehicle_code || "ยังไม่กำหนดรถ"}
          </b>
        </div>
        <div>
          <span>พนักงานขับรถ</span>
          <b>{s.driver_name || "-"}</b>
        </div>
        <div>
          <span>Loading Dock</span>
          <b>{s.loading_dock_code || "-"}</b>
        </div>
        <div>
          <span>สินค้าในรอบ</span>
          <b>
            {s.items.length} HU · {totalLoaded}/{totalPlanned} หน่วยขึ้นรถ
          </b>
        </div>
        <div>
          <span>ออกจากคลัง</span>
          <b>
            {s.actual_departure_at
              ? new Date(s.actual_departure_at).toLocaleString("th-TH")
              : "ยังไม่ออกเดินทาง"}
          </b>
        </div>
      </article>
      <div className="shipment-layout">
        <article className="panel">
          <h3>สินค้าและ HU ในรายการส่งนี้</h3>
          <div className="pro-notice info" aria-label="รายละเอียดปลายทางจัดส่ง">
            <b>ปลายทาง: {s.destination_name}</b>
            <p>{s.destination_address || 'ยังไม่ระบุที่อยู่จัดส่ง'}</p>
            <p>ผู้ติดต่อ: {s.destination_contact_name || s.customer_name} · โทร {s.destination_phone || 'ยังไม่ระบุ'}</p>
          </div>
          {s.status === "PICKING" && (
            <div className="station-routing">
              <label>
                <span>Checkout Station</span>
                <select
                  value={checkoutId || ""}
                  onChange={(e) => setCheckoutStationId(+e.target.value)}
                >
                  {checkoutStations.map((x) => (
                    <option value={x.id} key={x.id}>
                      {x.station_code} · {x.station_name}
                    </option>
                  ))}
                </select>
              </label>
              <ChevronRight />
              <label>
                <span>Loadout Station</span>
                <select
                  value={loadoutId || ""}
                  onChange={(e) => setLoadoutStationId(+e.target.value)}
                >
                  {loadoutStations.map((x) => (
                    <option value={x.id} key={x.id}>
                      {x.station_code} · {x.station_name}
                    </option>
                  ))}
                </select>
              </label>
            </div>
          )}
          {s.items.map((x) => (
            <div className="hu-line outbound-hu" key={x.id}>
              <div>
                <b>{x.sku}</b>
                <small>{x.hu_code || "รอจัดสรร HU"}</small>
                {x.current_location_code && (
                  <code>{x.current_location_code}</code>
                )}
              </div>
              <span>
                <b>
                  {x.planned_quantity} {x.unit_of_measure}
                </b>
                <small>
                  ขึ้นรถ {x.loaded_quantity} · ส่งแล้ว {x.delivered_quantity}
                </small>
                <small>{x.current_status}</small>
              </span>
              {s.status === "PICKING" &&
                x.hu_code &&
                !x.current_station_type && (
                  <button
                    className="ghost"
                    disabled={!checkoutLocation}
                    onClick={() =>
                      act("retrieve", {
                        hu_code: x.hu_code,
                        location_id: checkoutLocation?.id,
                      })
                    }
                  >
                    นำลงชั้น → Checkout
                  </button>
                )}
              {s.status === "PICKING" &&
                x.hu_code &&
                x.current_station_type === "CHECKOUT" && (
                  <button
                    className="ghost inspect-button"
                    disabled={!loadoutLocation}
                    onClick={() =>
                      act("checkout", {
                        hu_code: x.hu_code,
                        location_id: loadoutLocation?.id,
                      })
                    }
                  >
                    ตรวจผ่าน → Loadout
                  </button>
                )}
              {s.status === "PICKING" &&
                x.current_station_type === "LOADOUT" && (
                  <span className="status active">พร้อมขึ้นรถ</span>
                )}
            </div>
          ))}
          <div className="trip-quantity-summary">
            <span>
              แผน <b>{totalPlanned}</b>
            </span>
            <span>
              ขึ้นรถ <b>{totalLoaded}</b>
            </span>
            <span>
              ส่งสำเร็จ <b>{totalDelivered}</b>
            </span>
          </div>
          <div className="process-actions">
            {s.status === "PLANNED" && (
              <button className="button" onClick={() => act("allocate")}>
                Allocate Inventory
              </button>
            )}
            {s.status === "PICKING" && allAtLoadout && (
              <button className="button" onClick={() => act("ready-to-load")}>
                ยืนยันพร้อมโหลดขึ้นรถ
              </button>
            )}
            {s.delivery_run_id &&
              ["READY_TO_LOAD", "LOADING", "LOADED", "DEPARTED"].includes(
                s.status,
              ) && (
                <NavLink
                  className="button"
                  to={`/delivery-runs/${s.delivery_run_id}`}
                >
                  <Truck size={16} /> ควบคุมรถทั้งรอบ {s.delivery_run_no}
                </NavLink>
              )}
            {!s.delivery_run_id && s.status === "READY_TO_LOAD" && (
              <p className="helper">
                พร้อมรอจัดรถ — จองและสแกนสินค้าได้ที่หน้ารอบรถเท่านั้น
              </p>
            )}
            {!s.delivery_run_id && s.status === "DEPARTED" && (
              <button className="button" onClick={() => act("in-transit")}>
                Mark In Transit
              </button>
            )}
            {s.status === "IN_TRANSIT" && (
              <button className="button" onClick={() => act("arrive")}>
                ถึงจุดส่งแล้ว
              </button>
            )}
            {s.status === "DELIVERY_FAILED" && (
              <button className="button" onClick={() => act("return")}>
                นำสินค้ากลับคลัง
              </button>
            )}
            {s.status === "RETURNING" && (
              <button
                className="button"
                onClick={() =>
                  act("return-complete", {
                    return_station_id: returnStation?.id,
                  })
                }
              >
                Unload at Return Station
              </button>
            )}
          </div>
          {["ARRIVED", "DELIVERED"].includes(s.status) && (
            <DeliveryCompletionPanel shipment={s} act={act} reload={load} />
          )}
          {s.delivery_attempts.length > 0 && (
            <div className="delivery-attempts">
              <h3>ประวัติการพยายามส่ง</h3>
              {s.delivery_attempts.map((attempt) => (
                <div key={attempt.attempt_no}>
                  <b>
                    ครั้งที่ {attempt.attempt_no} · {attempt.result}
                  </b>
                  <span>{attempt.failure_reason || "-"}</span>
                  <small>
                    {new Date(attempt.attempted_at).toLocaleString("th-TH")}
                    {attempt.note ? ` · ${attempt.note}` : ""}
                  </small>
                </div>
              ))}
            </div>
          )}
        </article>
        <article className="panel timeline">
          <h3>สถานะการเดินทางรอบนี้</h3>
          {s.tracking.map((x, i) => (
            <div className="timeline-item" key={i}>
              <i />
              <div>
                <b>{truckStatusLabel[x.event_type] || x.event_type}</b>
                <small>{new Date(x.event_at).toLocaleString("th-TH")}</small>
                {x.note && <p>{x.note}</p>}
              </div>
            </div>
          ))}
        </article>
        <article className="panel trip-transactions">
          <div className="trip-transactions-head">
            <div>
              <p className="eyebrow">TRANSACTION LOG</p>
              <h3>ประวัติการส่งต่อสินค้าในรอบ</h3>
            </div>
            <span>{transactions.length} รายการ</span>
          </div>
          {transactions.length ? (
            <div className="table-wrap">
              <table>
                <thead>
                  <tr>
                    <th>เวลา</th>
                    <th>Transaction</th>
                    <th>HU / สินค้า</th>
                    <th>จำนวน</th>
                    <th>จาก</th>
                    <th>ไปยัง</th>
                  </tr>
                </thead>
                <tbody>
                  {transactions.map((tx) => (
                    <tr key={tx.transaction_no}>
                      <td>
                        {new Date(tx.occurred_at).toLocaleString("th-TH")}
                      </td>
                      <td>
                        <b>
                          {transactionLabel[tx.transaction_type] ||
                            tx.transaction_type}
                        </b>
                        <small>{tx.transaction_no}</small>
                      </td>
                      <td>
                        <b>{tx.hu_code || "-"}</b>
                        <small>{tx.sku || "-"}</small>
                      </td>
                      <td>
                        {tx.quantity} {tx.unit_of_measure}
                      </td>
                      <td>
                        <code>{tx.from_node}</code>
                      </td>
                      <td>
                        <code>{tx.to_node}</code>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <div className="empty">
              ยังไม่มี Transaction การเคลื่อนย้ายสินค้าในรอบนี้
            </div>
          )}
        </article>
      </div>
    </section>
  );
}

function DeliveryCompletionPanel({
  shipment,
  act,
  reload,
}: {
  shipment: Shipment;
  act: (path: string, body?: unknown) => Promise<void>;
  reload: () => void;
}) {
  const [receiver, setReceiver] = useState(
    shipment.destination_contact_name || "",
  );
  const [phone, setPhone] = useState(shipment.destination_phone || "");
  const [note, setNote] = useState("");
  const [pin, setPin] = useState(false);
  const [failureReason, setFailureReason] = useState("CUSTOMER_NOT_AVAILABLE");
  const [message, setMessage] = useState("");
  async function deliverSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!receiver.trim()) {
      setMessage("กรุณาระบุชื่อผู้รับสินค้า");
      return;
    }
    setMessage("");
    await act(shipment.status === "DELIVERED" ? "pod" : "deliver", {
      receiver_name: receiver.trim(),
      receiver_phone: phone.trim() || null,
      delivery_pin_verified: pin,
      note: note.trim() || null,
    });
  }
  async function failSubmit(e: React.FormEvent) {
    e.preventDefault();
    setMessage("");
    await act("delivery-failed", {
      failure_reason: failureReason,
      note: note.trim() || null,
    });
  }
  async function uploadEvidence(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const form = new FormData(e.currentTarget);
    if (
      !(form.get("photo") as File)?.size &&
      !(form.get("signature") as File)?.size
    ) {
      setMessage("กรุณาเลือกภาพส่งมอบหรือลายเซ็นอย่างน้อย 1 ไฟล์");
      return;
    }
    try {
      await upload(`/shipments/${shipment.id}/pod-files`, form);
      setMessage("อัปโหลดหลักฐาน POD สำเร็จ");
      reload();
    } catch (error) {
      setMessage((error as Error).message);
    }
  }
  if (shipment.status === "DELIVERED" && shipment.pod)
    return (
      <div className="pod-card">
        <div>
          <p className="eyebrow">PROOF OF DELIVERY</p>
          <h3>ส่งมอบสำเร็จ</h3>
          <dl>
            <dt>ผู้รับ</dt>
            <dd>
              {shipment.pod.receiver_name}
              {shipment.pod.receiver_phone && (
                <small>{shipment.pod.receiver_phone}</small>
              )}
            </dd>
            <dt>PIN</dt>
            <dd>
              {shipment.pod.delivery_pin_verified
                ? "ยืนยันแล้ว"
                : "ไม่ได้ยืนยัน"}
            </dd>
            <dt>เวลา</dt>
            <dd>
              {new Date(shipment.pod.delivered_at).toLocaleString("th-TH")}
            </dd>
          </dl>
        </div>
        <form onSubmit={uploadEvidence}>
          <b>แนบหลักฐานเพิ่มเติม</b>
          <label>
            รูปส่งมอบ
            <input
              name="photo"
              type="file"
              accept="image/png,image/jpeg,image/webp"
            />
          </label>
          <label>
            ลายเซ็น
            <input
              name="signature"
              type="file"
              accept="image/png,image/jpeg,image/webp"
            />
          </label>
          <button className="button">อัปโหลด POD</button>
          {message && <small>{message}</small>}
          <div className="pod-evidence">
            {shipment.pod.photo_file && (
              <a href={shipment.pod.photo_file} target="_blank">
                ดูภาพส่งมอบ
              </a>
            )}
            {shipment.pod.signature_file && (
              <a href={shipment.pod.signature_file} target="_blank">
                ดูลายเซ็น
              </a>
            )}
          </div>
        </form>
      </div>
    );
  if (shipment.status === "DELIVERED")
    return (
      <form className="legacy-pod panel" onSubmit={deliverSubmit}>
        <p className="eyebrow">MISSING POD · IMPORTED RECORD</p>
        <h3>บันทึก POD ย้อนหลัง</h3>
        <p className="helper">
          งานนี้ถูกปิดว่าส่งสำเร็จจากข้อมูลเดิม แต่ยังไม่มีหลักฐานผู้รับ
        </p>
        <div className="form-grid">
          <Field
            required
            label="ชื่อผู้รับสินค้า"
            value={receiver}
            onChange={(e) => setReceiver(e.target.value)}
          />
          <Field
            label="เบอร์โทรผู้รับ"
            value={phone}
            onChange={(e) => setPhone(e.target.value)}
          />
        </div>
        <Field
          label="หมายเหตุ"
          value={note}
          onChange={(e) => setNote(e.target.value)}
        />
        <label className="pin-check">
          <input
            type="checkbox"
            checked={pin}
            onChange={(e) => setPin(e.target.checked)}
          />
          <span>ตรวจสอบ Delivery PIN แล้ว</span>
        </label>
        {message && <ErrorBox message={message} />}
        <button className="button">บันทึก POD ย้อนหลัง</button>
      </form>
    );
  return (
    <div className="delivery-closeout">
      <form onSubmit={deliverSubmit}>
        <p className="eyebrow">DELIVERY CONFIRMATION</p>
        <h3>ยืนยันส่งมอบสินค้า</h3>
        <div className="form-grid">
          <Field
            required
            label="ชื่อผู้รับสินค้า"
            value={receiver}
            onChange={(e) => setReceiver(e.target.value)}
          />
          <Field
            label="เบอร์โทรผู้รับ"
            value={phone}
            onChange={(e) => setPhone(e.target.value)}
          />
        </div>
        <Field
          label="หมายเหตุ"
          value={note}
          onChange={(e) => setNote(e.target.value)}
        />
        <label className="pin-check">
          <input
            type="checkbox"
            checked={pin}
            onChange={(e) => setPin(e.target.checked)}
          />
          <span>ตรวจสอบ Delivery PIN แล้ว</span>
        </label>
        {message && <ErrorBox message={message} />}
        <button className="button wide">ยืนยันส่งมอบ + สร้าง POD</button>
      </form>
      <form className="failure-form" onSubmit={failSubmit}>
        <p className="eyebrow">DELIVERY EXCEPTION</p>
        <h3>ส่งไม่สำเร็จ</h3>
        <label>
          <span>สาเหตุ</span>
          <select
            value={failureReason}
            onChange={(e) => setFailureReason(e.target.value)}
          >
            <option value="CUSTOMER_NOT_AVAILABLE">ไม่พบผู้รับ</option>
            <option value="CUSTOMER_CLOSED">สถานที่ปิด</option>
            <option value="REFUSED">ลูกค้าปฏิเสธรับ</option>
            <option value="ADDRESS_NOT_FOUND">ไม่พบที่อยู่</option>
            <option value="DAMAGED">สินค้าชำรุด</option>
            <option value="OTHER">อื่น ๆ</option>
          </select>
        </label>
        <button className="danger-button wide">บันทึกว่าส่งไม่สำเร็จ</button>
      </form>
    </div>
  );
}

function DriverPage() {
  const { data: runs, error } = useLoad<DeliveryRun[]>(
    "/delivery-runs?active_only=true",
    [],
  );
  const active = runs.filter(
    (run) => !["PLANNED", "COMPLETED", "CANCELLED"].includes(run.status),
  );
  return (
    <section className="driver-page">
      <PageTitle
        eyebrow="DRIVER PWA"
        title="งานจัดส่งของฉัน"
        desc="แสดงรอบรถ จุดส่ง และสถานะงานทั้งหมดในคันเดียว"
      />
      <ErrorBox message={error} />
      {active.map((run) => (
        <article className="driver-run" key={run.id}>
          <NavLink to={`/delivery-runs/${run.id}`} className="driver-run-head">
            <span>
              <Truck size={24} />
            </span>
            <div>
              <small>{run.run_no}</small>
              <h3>
                {run.vehicle_code} ·{" "}
                {truckStatusLabel[run.status] || run.status}
              </h3>
              <p>
                {run.license_plate} · {run.driver_name}
              </p>
            </div>
            <ChevronRight />
          </NavLink>
          <div className="driver-stops">
            {run.shipments.map((shipment, index) => (
              <NavLink to={`/shipments/${shipment.id}`} key={shipment.id}>
                <b>{index + 1}</b>
                <div>
                  <strong>{shipment.destination_name}</strong>
                  <span>{shipment.destination_address}</span>
                  <small>
                    {shipment.shipment_no} · {shipment.items.length} HU ·{" "}
                    {shipment.status}
                  </small>
                </div>
                <ChevronRight />
              </NavLink>
            ))}
          </div>
        </article>
      ))}
      {!active.length && (
        <div className="empty panel">ไม่มีงานจัดส่งที่กำลังดำเนินการ</div>
      )}
    </section>
  );
}

const auditActionLabel: Record<string, string> = {
  CREATE: "สร้างข้อมูล",
  RECEIVE: "รับสินค้า",
  PUTAWAY: "จัดเก็บเข้าชั้น",
  PICK_FROM_LOCATION: "เบิกสินค้าจากชั้น",
  RETRIEVE: "นำลงจากชั้น",
  CHECKOUT: "ตรวจผ่าน Checkout",
  LOAD: "โหลดขึ้นรถ",
  DELIVER: "ส่งมอบสำเร็จ",
  DELIVERY_FAILED: "ส่งไม่สำเร็จ",
  RETURNED: "รับสินค้าคืน",
  RETURN_PUTAWAY: "จัดเก็บสินค้าคืน",
  UPLOAD_POD: "แนบหลักฐาน POD",
  BACKFILL_POD: "บันทึก POD ย้อนหลัง",
};
function AuditPage() {
  const { data: logs, error } = useLoad<AuditLog[]>(
    "/audit-logs?limit=500",
    [],
  );
  const [query, setQuery] = useState("");
  const filtered = logs.filter((log) =>
    `${log.action} ${log.entity_type} ${log.entity_id} ${log.new_data || ""}`
      .toLowerCase()
      .includes(query.toLowerCase()),
  );
  return (
    <section className="audit-page">
      <PageTitle
        eyebrow="TRACEABILITY & AUDIT"
        title="ประวัติการทำรายการระบบ"
        desc="ตรวจสอบว่าเกิดอะไรขึ้น กับข้อมูลใด และเมื่อใด จาก Audit Log ส่วนกลาง"
      />
      <ErrorBox message={error} />
      <div className="searchbar">
        <Search size={18} />
        <input
          placeholder="ค้นหา Action, ประเภทข้อมูล หรือรหัสรายการ..."
          value={query}
          onChange={(e) => setQuery(e.target.value)}
        />
        <span>{filtered.length} รายการ</span>
      </div>
      <div className="table-wrap audit-table">
        <table>
          <thead>
            <tr>
              <th>เวลา</th>
              <th>การทำรายการ</th>
              <th>ประเภทข้อมูล</th>
              <th>รหัส</th>
              <th>รายละเอียด</th>
            </tr>
          </thead>
          <tbody>
            {filtered.map((log) => (
              <tr key={log.id}>
                <td>{new Date(log.created_at).toLocaleString("th-TH")}</td>
                <td>
                  <b>{auditActionLabel[log.action] || log.action}</b>
                  <small>{log.action}</small>
                </td>
                <td>
                  <span className="audit-entity">{log.entity_type}</span>
                </td>
                <td>
                  <code>{log.entity_id}</code>
                </td>
                <td>
                  <code className="audit-data">{log.new_data || "-"}</code>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        {!filtered.length && (
          <div className="empty">ไม่พบประวัติที่ตรงกับคำค้นหา</div>
        )}
      </div>
    </section>
  );
}

function LoginPage({ onLogin }: { onLogin: () => void }) {
  const [username, setUsername] = useState("admin");
  const [password, setPassword] = useState("0000");
  const [error, setError] = useState("");
  async function submit(e: React.FormEvent) {
    e.preventDefault();
    try {
      const result = await post<{ access_token: string }>("/auth/login", {
        username,
        password,
      });
      localStorage.setItem("warehouse_token", result.access_token);
      onLogin();
    } catch (e) {
      setError((e as Error).message);
    }
  }
  return (
    <div className="login-page">
      <div className="login-brand">
        <span>
          <WarehouseIcon />
        </span>
        <b>SMART WAREHOUSE</b>
        <p>Warehouse & Logistics Control</p>
      </div>
      <form className="login-card" onSubmit={submit}>
        <p className="eyebrow">SECURE ACCESS</p>
        <h2>เข้าสู่ระบบ</h2>
        <p>กรุณาใช้บัญชีผู้ดูแลระบบ</p>
        <Field
          label="Username"
          value={username}
          onChange={(e) => setUsername(e.target.value)}
        />
        <Field
          label="Password"
          type="password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
        />
        <ErrorBox message={error} />
        <button className="button wide">เข้าสู่ระบบ</button>
        <small>Demo: admin / 0000</small>
      </form>
    </div>
  );
}

function App() {
  const [authenticated, setAuthenticated] = useState(
    Boolean(localStorage.getItem("warehouse_token")),
  );
  return authenticated ? (
    <Layout />
  ) : (
    <LoginPage onLogin={() => setAuthenticated(true)} />
  );
}
export default App;
export { Layout as LegacyWorkspace };
