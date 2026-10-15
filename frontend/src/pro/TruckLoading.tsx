import { useEffect, useState } from "react";
import { NavLink, useNavigate } from "react-router-dom";
import { Plus, X } from "lucide-react";
import { post } from "../api";
import { useResource } from "./useResource";
import { useAccount } from "../ProApp";
import type {
  DeliveryRun,
  Shipment,
  Vehicle,
  Driver,
  Dock,
  Warehouse,
} from "../types";
export function NewTruckButton() {
  const account = useAccount(),
    navigate = useNavigate();
  const [show, setShow] = useState(false),
    [warehouse, setWarehouse] = useState(0),
    [vehicle, setVehicle] = useState(0),
    [driver, setDriver] = useState(0),
    [dock, setDock] = useState(0),
    [busy, setBusy] = useState(false),
    [error, setError] = useState("");
  const { data: warehouses } = useResource<Warehouse[]>("/warehouses", []);
  const wh = warehouse || warehouses.find((w) => w.is_active)?.id || 0;
  const { data: vehicles, reload: reloadVehicles } = useResource<Vehicle[]>(
    "/vehicles",
    [],
  );
  const { data: drivers, reload: reloadDrivers } = useResource<Driver[]>(
    "/drivers",
    [],
  );
  const { data: docks } = useResource<Dock[]>(
    "/loading-docks?warehouse_id=" + wh,
    [],
  );
  async function submit(e: React.FormEvent) {
    e.preventDefault();
    if (busy) return;
    setBusy(true);
    setError("");
    try {
      const run = await post<DeliveryRun>("/delivery-runs", {
        origin_warehouse_id: wh,
        vehicle_id: vehicle,
        driver_id: driver,
        loading_dock_id: dock || null,
        arrived: true,
      });
      setShow(false);
      navigate("/delivery-runs/" + run.id);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  if (!account.permissions.includes("logistics")) return null;
  return (
    <>
      <button
        className="pro-primary"
        onClick={() => {
          setShow(true);
          setVehicle(0);
          setDriver(0);
          setDock(0);
          setError("");
          void reloadVehicles();
          void reloadDrivers();
        }}
      >
        <Plus size={16} /> ลงทะเบียนรถมาถึง
      </button>
      {show && (
        <div
          className="pro-overlay"
          onClick={() => {
            if (!busy) setShow(false);
          }}
        >
          <div
            className="pro-dialog"
            role="dialog"
            aria-modal="true"
            aria-label="ลงทะเบียนรถมาถึง"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="panel-heading">
              <h3>ลงทะเบียนรถมาจอดรอ</h3>
              <button
                className="pro-icon-button"
                aria-label="ปิดลงทะเบียนรถ"
                disabled={busy}
                onClick={() => setShow(false)}
              >
                <X />
              </button>
            </div>
            <p className="pro-muted">
              เตรียมรถและคนขับครั้งเดียวต่อรอบ ยังไม่ต้องมี Shipment
            </p>
            <form onSubmit={submit}>
              <label>
                คลัง
                <select
                  aria-label="คลังลงทะเบียนรถ"
                  value={wh}
                  onChange={(e) => {
                    setWarehouse(+e.target.value);
                    setDock(0);
                  }}
                >
                  {warehouses
                    .filter((w) => w.is_active)
                    .map((w) => (
                      <option key={w.id} value={w.id}>
                        {w.warehouse_code} · {w.warehouse_name}
                      </option>
                    ))}
                </select>
              </label>
              <label>
                รถที่มาถึง
                <select
                  required
                  aria-label="รถที่มาถึง"
                  value={vehicle}
                  onChange={(e) => setVehicle(+e.target.value)}
                >
                  <option value="">เลือกรถ</option>
                  {vehicles
                    .filter((v) => v.status === "AVAILABLE")
                    .map((v) => (
                      <option key={v.id} value={v.id}>
                        {v.vehicle_code} · {v.license_plate}
                      </option>
                    ))}
                </select>
              </label>
              <label>
                คนขับรอบนี้
                <select
                  required
                  aria-label="คนขับรอบนี้"
                  value={driver}
                  onChange={(e) => setDriver(+e.target.value)}
                >
                  <option value="">เลือกคนขับ</option>
                  {drivers
                    .filter((d) => d.status === "AVAILABLE")
                    .map((d) => (
                      <option key={d.id} value={d.id}>
                        {d.first_name} {d.last_name}
                      </option>
                    ))}
                </select>
              </label>
              <label>
                ช่องโหลดที่วางแผน
                <select
                  aria-label="ช่องโหลดที่วางแผน"
                  value={dock}
                  onChange={(e) => setDock(+e.target.value)}
                >
                  <option value="">เลือกตอนนำรถเข้าช่อง</option>
                  {docks.map((d) => (
                    <option key={d.id} value={d.id}>
                      {d.dock_code} · {d.status}
                    </option>
                  ))}
                </select>
              </label>
              {error && (
                <div className="pro-notice error" role="alert">
                  {error}
                </div>
              )}
              <button
                className="pro-primary wide"
                disabled={busy || !wh || !vehicle || !driver}
              >
                ยืนยันรถมาถึงและเปิดรอบรถ
              </button>
            </form>
          </div>
        </div>
      )}
    </>
  );
}
export function RunLoadingWorkspace({
  run,
  onChanged,
}: {
  run: DeliveryRun;
  onChanged: () => void;
}) {
  const account = useAccount();
  const [scanCode, setScanCode] = useState("");
  const { data: docks } = useResource<Dock[]>(
    "/loading-docks" +
      (run.origin_warehouse_id
        ? "?warehouse_id=" + run.origin_warehouse_id
        : ""),
    [],
  );
  const { data: queue, reload: reloadQueue, error: queueError, loading: queueLoading } = useResource<Shipment[]>(
    "/delivery-runs/" + run.id + "/loading-queue",
    [],
    10000,
  );
  const [dock, setDock] = useState(run.loading_dock_id || 0),
    [shipment, setShipment] = useState(0),
    [busy, setBusy] = useState(false),
    [error, setError] = useState("");
  useEffect(() => {
    setDock(run.loading_dock_id || 0);
    void reloadQueue();
  }, [run.id, run.status, run.shipments.length, run.loading_dock_id]);
  const permitted = account.permissions.includes("logistics");
  const active = run.shipments.filter((s) => s.status !== "CANCELLED");
  async function act(path: string, body: unknown = {}) {
    if (busy) return;
    setBusy(true);
    setError("");
    try {
      await post("/delivery-runs/" + run.id + "/" + path, body);
      setShipment(0);
      onChanged();
      void reloadQueue();
    } catch (e) {
      setError((e as Error).message);
      setShipment(0);
      onChanged();
      void reloadQueue();
    } finally {
      setBusy(false);
    }
  }
  if (!["PLANNED", "WAITING_DOCK", "AT_DOCK", "LOADING"].includes(run.status))
    return null;
  return (
    <article className="panel truck-load-workspace">
      <p className="eyebrow">TRUCK-FIRST LOADING</p>
      <h3>จัดคิวและโหลดสินค้าของรถคันนี้</h3>
      {run.status === "LOADING" && (
        <form
          className="truck-scan-form"
          onSubmit={(e) => {
            e.preventDefault();
            if (scanCode.trim()) {
              void act("scan", { hu_code: scanCode.trim() });
              setScanCode("");
            }
          }}
        >
          <label>
            สแกน HU Code ขึ้นรถ
            <input
              aria-label="สแกน HU Code ขึ้นรถ"
              autoComplete="off"
              placeholder="ยิง barcode หรือพิมพ์ HU แล้วกด Enter"
              value={scanCode}
              onChange={(e) => setScanCode(e.target.value)}
            />
          </label>
          <button
            className="button"
            disabled={busy || !permitted || !scanCode.trim()}
          >
            ยืนยันสแกน HU
          </button>
        </form>
      )}
      <p className="helper">
        จองรายการให้รถคันนี้ก่อน แล้วสแกน HU เพื่อยืนยันขึ้นรถจริง รายการที่จองแล้วจะไม่อยู่ในคิวรถคันอื่น
      </p>
      {error && (
        <div className="error" role="alert">
          {error}
        </div>
      )}
      {queueError && <div className="error" role="alert">โหลดคิวไม่สำเร็จ: {queueError} <button type="button" onClick={()=>void reloadQueue()}>โหลดคิวใหม่</button></div>}
      {run.status === "WAITING_DOCK" && (
        <form
          onSubmit={(e) => {
            e.preventDefault();
            void act("enter-dock", { loading_dock_id: dock });
          }}
        >
          <label>
            ช่องโหลดที่จะเข้าจอด
            <select
              aria-label="ช่องโหลดที่จะเข้าจอด"
              value={dock}
              onChange={(e) => setDock(+e.target.value)}
            >
              <option value="">เลือกช่องโหลด</option>
              {docks.map((d) => (
                <option
                  key={d.id}
                  value={d.id}
                  disabled={d.status !== "AVAILABLE"}
                >
                  {d.dock_code} · {d.status}
                </option>
              ))}
            </select>
          </label>
          <button className="button" disabled={busy || !dock || !permitted}>
            นำรถเข้าช่องโหลด
          </button>
        </form>
      )}
      {["AT_DOCK", "LOADING"].includes(run.status) && (
        <>
          <form
            onSubmit={(e) => {
              e.preventDefault();
              void act("shipments", { shipment_id: shipment });
            }}
          >
            <label>
              รายการส่งที่ตรวจผ่านและรออยู่ Loadout
              <select
                aria-label="รายการส่งรอโหลด"
                value={queue.some(s=>s.id===shipment)?shipment:""}
                disabled={busy||queueLoading||Boolean(queueError)||!queue.length}
                onChange={(e) => setShipment(+e.target.value)}
              >
                <option value="">เลือกรายการส่ง</option>
                {queue.map((s) => (
                  <option key={s.id} value={s.id}>
                    {s.shipment_no} · {s.customer_name} · {s.items.length} HU
                  </option>
                ))}
              </select>
            </label>
            <button
              className="button"
              disabled={busy || !queue.some(s=>s.id===shipment) || !permitted || queueLoading || Boolean(queueError)}
            >
              จองรายการส่งให้รถคันนี้
            </button>
          </form>
          {!queue.length && !queueLoading && !queueError && (
            <p className="helper">
              ไม่มีรายการส่งรอโหลด — นำสินค้า Checkout ผ่านการตรวจไป Loadout
              ก่อน รายการที่จองให้รถแล้วจะไม่แสดงในคิวนี้
            </p>
          )}
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>รายการส่ง / ลูกค้า</th>
                  <th>สินค้า / HU</th>
                  <th>ขึ้นรถแล้ว</th>
                  <th>คำสั่ง</th>
                </tr>
              </thead>
              <tbody>
                {active.flatMap((s) =>
                  s.items.map((i) => (
                    <tr key={s.id + "-" + i.id}>
                      <td>
                        <NavLink to={"/shipments/" + s.id}>
                          {s.shipment_no}
                        </NavLink>
                        <small>{s.customer_name}</small>
                      </td>
                      <td>
                        <b>{i.sku}</b>
                        <small>{i.hu_code}</small>
                      </td>
                      <td>
                        {i.loaded_quantity}/{i.planned_quantity}{" "}
                        {i.unit_of_measure}
                      </td>
                      <td>
                        {run.status === "LOADING" &&
                          i.loaded_quantity === 0 && (
                            <button
                              className="button small"
                              disabled={busy || !permitted}
                              onClick={async () => {
                                if (busy) return;
                                setBusy(true);
                                setError("");
                                try {
                                  await post(
                                    "/delivery-runs/" + run.id + "/scan",
                                    { hu_code: i.hu_code },
                                  );
                                  onChanged();
                                } catch (e) {
                                  setError((e as Error).message);
                                } finally {
                                  setBusy(false);
                                }
                              }}
                            >
                              สแกนขึ้นรถ {i.hu_code}
                            </button>
                          )}
                        {s.items.every(
                          (item) => item.loaded_quantity === 0,
                        ) && (
                          <button
                            className="ghost"
                            disabled={busy || !permitted}
                            onClick={() => {
                              if (
                                window.confirm(
                                  "ถอด " +
                                    s.shipment_no +
                                    " ออกจากรถ โดยยังคงรายการส่งไว้?",
                                )
                              )
                                void act("shipments/" + s.id + "/remove");
                            }}
                          >
                            ถอนจองรายการส่ง
                          </button>
                        )}
                        {i.loaded_quantity > 0 && (
                          <span className="status active">ขึ้นรถแล้ว</span>
                        )}
                      </td>
                    </tr>
                  )),
                )}
              </tbody>
            </table>
            {!active.length && (
              <div className="empty">
                รถจอดพร้อมแล้ว ยังไม่มีสินค้าในคิวโหลด
              </div>
            )}
          </div>
        </>
      )}
      {!active.length && permitted && (
        <button
          className="ghost"
          disabled={busy}
          onClick={() => {
            if (
              window.confirm("ยกเลิกรอบรถว่างนี้ และคืนรถ/คนขับให้พร้อมใช้งาน?")
            )
              void act("cancel-empty");
          }}
        >
          ยกเลิกรอบรถว่าง
        </button>
      )}
    </article>
  );
}
