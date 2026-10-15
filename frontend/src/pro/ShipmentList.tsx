import { NavLink, useSearchParams } from "react-router-dom";
import { ChevronRight, Search } from "lucide-react";
import type { Shipment } from "../types";
import "./shipment-filters.css";

export const shipmentStatusLabels: Record<string, string> = {
  PLANNED: "วางแผน",
  PICKING: "ตรวจสินค้า / เตรียมส่ง",
  READY_TO_LOAD: "พร้อมโหลด",
  LOADING: "กำลังโหลด",
  LOADED: "โหลดครบ",
  DEPARTED: "ออกจากคลัง",
  IN_TRANSIT: "กำลังนำส่ง",
  ARRIVED: "ถึงปลายทาง",
  DELIVERED: "ส่งสำเร็จ",
  DELIVERY_FAILED: "ส่งไม่สำเร็จ",
  RETURNING: "กำลังคืนสินค้า",
  RETURNED: "คืนสินค้าแล้ว",
  CANCELLED: "ยกเลิก",
};
export type ShipmentFilters = {
  q: string;
  status: string;
  vehicle: string;
  run: string;
  customer: string;
};
export function matchesShipment(s: Shipment, f: ShipmentFilters) {
  if (
    f.status === "ACTIVE" &&
    ["DELIVERED", "RETURNED", "CANCELLED"].includes(s.status)
  )
    return false;
  if (f.status !== "ALL" && f.status !== "ACTIVE" && s.status !== f.status)
    return false;
  if (f.vehicle === "UNASSIGNED" && s.vehicle_code) return false;
  if (
    f.vehicle !== "ALL" &&
    f.vehicle !== "UNASSIGNED" &&
    s.vehicle_code !== f.vehicle
  )
    return false;
  if (f.run === "UNASSIGNED" && s.delivery_run_id) return false;
  if (
    f.run !== "ALL" &&
    f.run !== "UNASSIGNED" &&
    String(s.delivery_run_id) !== f.run
  )
    return false;
  if (f.customer !== "ALL" && s.customer_name !== f.customer) return false;
  const query = f.q.trim().toLocaleLowerCase();
  const text = [
    s.shipment_no,
    s.customer_name,
    s.destination_name,
    s.destination_address,
    s.vehicle_code,
    s.driver_name,
    s.delivery_run_no,
    ...s.items.flatMap((i) => [i.sku, i.hu_code]),
  ]
    .filter(Boolean)
    .join(" ")
    .toLocaleLowerCase();
  return !query || text.includes(query);
}
export function ShipmentList({ shipments }: { shipments: Shipment[] }) {
  const [params, setParams] = useSearchParams();
  const filters: ShipmentFilters = {
    q: params.get("q") || "",
    status: params.get("status") || "ALL",
    vehicle: params.get("vehicle") || "ALL",
    run: params.get("run") || "ALL",
    customer: params.get("customer") || "ALL",
  };
  function change(key: keyof ShipmentFilters, value: string) {
    // Read the live URL so rapid clear/change events cannot reuse stale filters.
    const next = new URLSearchParams(window.location.search);
    if (!value || value === "ALL") next.delete(key);
    else next.set(key, value);
    if (key === "vehicle") next.delete("run");
    setParams(next, { replace: true });
  }
  function clear() {
    const next = new URLSearchParams(window.location.search);
    for (const k of ["q", "status", "vehicle", "run", "customer"])
      next.delete(k);
    setParams(next, { replace: true });
  }
  const vehicles = [
    ...new Set(
      shipments.map((s) => s.vehicle_code).filter((v): v is string => !!v),
    ),
  ].sort((a, b) => a.localeCompare(b, "th", { numeric: true }));
  const customers = [...new Set(shipments.map((s) => s.customer_name))].sort(
    (a, b) => a.localeCompare(b, "th"),
  );
  const runs = [
    ...new Map(
      shipments
        .filter(
          (s) =>
            s.delivery_run_id &&
            (filters.vehicle === "ALL" || s.vehicle_code === filters.vehicle),
        )
        .map((s) => [
          s.delivery_run_id,
          {
            id: s.delivery_run_id!,
            label: s.delivery_run_no || String(s.delivery_run_id),
            vehicle: s.vehicle_code || "",
          },
        ]),
    ).values(),
  ].sort((a, b) => b.id - a.id);
  const statuses = [
    ...new Set([
      ...Object.keys(shipmentStatusLabels),
      ...shipments.map((s) => s.status),
    ]),
  ];
  const filtered = shipments.filter((s) => matchesShipment(s, filters));
  const isFiltered =
    filters.q !== "" ||
    Object.entries(filters).some(
      ([key, value]) => key !== "q" && value !== "ALL",
    );
  return (
    <>
      <div
        className="shipment-filter-panel"
        role="search"
        aria-label="ตัวกรองรายการส่ง"
      >
        <label className="shipment-query">
          <span>ค้นหารายการส่ง</span>
          <div>
            <Search size={17} />
            <input
              aria-label="ค้นหารายการส่ง"
              placeholder="เลข Shipment, ลูกค้า, HU, SKU หรือรอบรถ"
              value={filters.q}
              onChange={(e) => change("q", e.target.value)}
            />
          </div>
        </label>
        <label>
          <span>สถานะ</span>
          <select
            aria-label="กรองสถานะรายการส่ง"
            value={filters.status}
            onChange={(e) => change("status", e.target.value)}
          >
            <option value="ALL">ทุกสถานะ</option>
            <option value="ACTIVE">งานที่ยังไม่ปิด</option>
            {!["ALL", "ACTIVE", ...statuses].includes(filters.status) && (
              <option value={filters.status}>{filters.status}</option>
            )}
            {statuses.map((s) => (
              <option value={s} key={s}>
                {shipmentStatusLabels[s] || s}
              </option>
            ))}
          </select>
        </label>
        <label>
          <span>รถ</span>
          <select
            aria-label="กรองรถรายการส่ง"
            value={filters.vehicle}
            onChange={(e) => change("vehicle", e.target.value)}
          >
            <option value="ALL">รถทุกคัน</option>
            <option value="UNASSIGNED">ยังไม่กำหนดรถ</option>
            {!["ALL", "UNASSIGNED", ...vehicles].includes(filters.vehicle) && (
              <option value={filters.vehicle}>
                {filters.vehicle} (ไม่พบในชุดนี้)
              </option>
            )}
            {vehicles.map((v) => (
              <option value={v} key={v}>
                {v}
              </option>
            ))}
          </select>
        </label>
        <label>
          <span>รอบขนส่ง</span>
          <select
            aria-label="กรองรอบขนส่ง"
            value={filters.run}
            onChange={(e) => change("run", e.target.value)}
          >
            <option value="ALL">ทุกรอบขนส่ง</option>
            <option value="UNASSIGNED">ยังไม่เข้ารอบรถ</option>
            {!["ALL", "UNASSIGNED", ...runs.map((r) => String(r.id))].includes(
              filters.run,
            ) && (
              <option value={filters.run}>
                รอบ {filters.run} (ไม่พบในตัวเลือก)
              </option>
            )}
            {runs.map((r) => (
              <option value={r.id} key={r.id}>
                {r.label} · {r.vehicle}
              </option>
            ))}
          </select>
        </label>
        <label>
          <span>ลูกค้า</span>
          <select
            aria-label="กรองลูกค้ารายการส่ง"
            value={filters.customer}
            onChange={(e) => change("customer", e.target.value)}
          >
            <option value="ALL">ลูกค้าทั้งหมด</option>
            {!["ALL", ...customers].includes(filters.customer) && (
              <option value={filters.customer}>
                {filters.customer} (ไม่พบในชุดนี้)
              </option>
            )}
            {customers.map((c) => (
              <option value={c} key={c}>
                {c}
              </option>
            ))}
          </select>
        </label>
        <div className="shipment-filter-summary">
          <span role="status">
            แสดง {filtered.length} จาก {shipments.length} รายการ
          </span>
          <button
            type="button"
            className="ghost"
            onClick={clear}
            disabled={!isFiltered}
          >
            ล้างตัวกรอง
          </button>
        </div>
      </div>
      <div className="shipment-grid">
        {filtered.map((s) => (
          <NavLink
            to={"/shipments/" + s.id}
            className="shipment-card"
            key={s.id}
          >
            <div>
              <span className={"status shipment-" + s.status.toLowerCase()}>
                {shipmentStatusLabels[s.status] || s.status}
              </span>
              <h3>{s.shipment_no}</h3>
              <p>{s.customer_name}</p>
            </div>
            <div className="shipment-meta">
              <span>{s.vehicle_code || "ยังไม่กำหนดรถ"}</span>
              <small>{s.delivery_run_no || "ยังไม่เข้ารอบรถ"}</small>
              <b>{s.items.length} HU</b>
            </div>
            <ChevronRight />
          </NavLink>
        ))}
      </div>
      {!filtered.length && (
        <div className="shipment-filter-empty">
          <h3>
            {shipments.length
              ? "ไม่พบรายการที่ตรงกับตัวกรอง"
              : "ยังไม่มีรายการส่ง"}
          </h3>
          <p>
            {shipments.length
              ? "ปรับเงื่อนไขหรือล้างตัวกรองเพื่อดูรายการอื่น"
              : "เมื่อสร้าง Shipment แล้ว รายการจะแสดงที่นี่"}
          </p>
          {isFiltered && (
            <button className="ghost" onClick={clear}>
              แสดงรายการทั้งหมด
            </button>
          )}
        </div>
      )}
    </>
  );
}
