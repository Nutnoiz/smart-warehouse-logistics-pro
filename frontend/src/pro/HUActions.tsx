import { useEffect, useState } from "react";
import { NavLink } from "react-router-dom";
import { ArrowRight, Package, X } from "lucide-react";
import { api, post } from "../api";
import { useAccount } from "../ProApp";
import { useResource } from "./useResource";
import type { Customer, Inventory, Shipment } from "../types";
import "./workflow.css";
import QRCode from "react-qr-code";

type Destination = {
  id: number;
  location_code: string;
  kind: string;
  zone_code?: string;
  rack_id?: number;
  bay_no?: number;
  level_no?: number;
  position_no?: number;
};
type Workflow = {
  hu_code: string;
  sku: string;
  product_name: string;
  quantity: number;
  unit: string;
  reserved: number;
  status: string;
  location_code: string;
  kind: string;
  destinations: Destination[];
  shipment_id?: number;
  shipment_no?: string;
  delivery_run_id?: number;
  can_ship: boolean;
  can_cancel: boolean;
};
const labels: Record<string, string> = {
  STORAGE: "จัดเก็บคืนชั้น",
  INBOUND: "ย้อนกลับ Inbound",
  CHECKOUT: "นำไป Checkout / ตรวจ QC",
  LOADOUT: "ส่งต่อ Loadout",
};
export function HUActions({
  code,
  onClose,
  onChanged,
}: {
  code: string;
  onClose: () => void;
  onChanged: () => void;
}) {
  const account = useAccount();
  const [data, setData] = useState<Workflow | null>(null),
    [error, setError] = useState(""),
    [busy, setBusy] = useState(false),
    [notice, setNotice] = useState("");
  const [kind, setKind] = useState(""),
    [dest, setDest] = useState(0),
    [note, setNote] = useState("");
  const [createdShipment, setCreatedShipment] = useState<Shipment | null>(null);
  const [shipping, setShipping] = useState(false),
    [quantity, setQuantity] = useState(1),
    [customer, setCustomer] = useState(0);
  const customerResource = useResource<Customer[]>("/customers", []);
  const customers = customerResource.data.filter(c => c.is_active);
  async function load() {
    try {
      const value = await api<Workflow>(
        "/station-workflow/" + encodeURIComponent(code),
      );
      setData(value);
      setQuantity(value.quantity);
      setDest(0);
      setKind("");
      setShipping(false);
    } catch (e) {
      setError((e as Error).message);
    }
  }
  useEffect(() => {
    void load();
  }, [code]);
  useEffect(() => {
    const close = (e: KeyboardEvent) => {
      if (e.key === "Escape" && !busy) onClose();
    };
    window.addEventListener("keydown", close);
    return () => window.removeEventListener("keydown", close);
  }, [busy, onClose]);
  async function execute(action: () => Promise<unknown>, message: string) {
    if (busy) return;
    setBusy(true);
    setError("");
    try {
      await action();
      setNotice(message);
      onChanged();
      await load();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  const groups = [...new Set(data?.destinations.map((d) => d.kind) || [])];
  const candidates = data?.destinations.filter((d) => d.kind === kind) || [];
  const chosen = candidates.find((d) => d.id === dest) || candidates[0];
  const warehouse = account.permissions.includes("warehouse"),
    logistics = account.permissions.includes("logistics");
  function chooseGroup(value: string) {
    setKind(value);
    setDest(0);
    setShipping(false);
  }
  function first(predicate: (d: Destination) => boolean) {
    setDest(candidates.find(predicate)?.id || 0);
  }
  function values(
    key: keyof Destination,
    predicate: (d: Destination) => boolean,
  ) {
    return [...new Set(candidates.filter(predicate).map((d) => d[key]))];
  }
  return (
    <div
      className="pro-overlay"
      onClick={() => {
        if (!busy) onClose();
      }}
    >
      <div
        className="hu-action-dialog"
        role="dialog"
        aria-modal="true"
        aria-label="ดำเนินการสินค้า"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="panel-heading">
          <div>
            <p>HANDLING UNIT WORKFLOW</p>
            <h3>ดำเนินการสินค้า</h3>
          </div>
          <button
            className="pro-icon-button"
            aria-label="ปิดคำสั่งสินค้า"
            disabled={busy}
            onClick={onClose}
          >
            <X />
          </button>
        </div>
        {createdShipment && (
          <NavLink
            className="pro-primary"
            to={"/shipments/" + createdShipment.id}
          >
            เปิดรายการส่ง {createdShipment.shipment_no} <ArrowRight size={14} />
          </NavLink>
        )}
        {notice && (
          <div className="pro-notice info" role="status">
            {notice}
          </div>
        )}
        {error && (
          <div className="pro-notice error" role="alert">
            {error}
          </div>
        )}
        {!data && !error && (
          <div className="pro-empty">กำลังโหลดสถานะล่าสุด…</div>
        )}
        {data && (
          <>
            <div className="hu-summary">
              <Package />
              <div>
                <h3>{data.product_name}</h3>
                <small>
                  {data.sku} · {data.hu_code}
                </small>
                <b>
                  {data.quantity} {data.unit}
                </b>
                <small>
                  อยู่ที่ {data.location_code} · {data.status}
                </small>
              </div>
            </div>
            {data.kind === "CHECKOUT" && !data.shipment_id && (
              <p className="pro-notice info">
                พักตรวจ QC หรือให้ลูกค้าดูตัวอย่างได้
                ไม่จำเป็นต้องสร้างรายการส่ง
              </p>
            )}
            {data.shipment_id && (
              <div className="hu-commitment">
                <span>
                  จองให้ {data.shipment_no} · {data.reserved} {data.unit}
                </span>
                <NavLink to={"/shipments/" + data.shipment_id}>
                  เปิดรายการส่ง <ArrowRight size={14} />
                </NavLink>
              </div>
            )}
            {data.kind === "LOADOUT" && data.shipment_id && <div className="pro-notice info">
              <p>{data.delivery_run_id ? "รายการนี้จองรอบรถแล้ว สินค้ายังอยู่ Loadout จนกว่าจะสแกนขึ้นรถ" : "สินค้ารอจัดรถ จองรายการและสแกนขึ้นรถที่หน้ารอบรถเท่านั้น"}</p>
              <NavLink className="pro-secondary" to={data.delivery_run_id ? '/delivery-runs/'+data.delivery_run_id : '/delivery-runs'}>{data.delivery_run_id ? 'เปิดรอบรถเพื่อโหลดสินค้า' : 'ไปจัดรถและโหลดสินค้า'}</NavLink>
            </div>}
            <div className="hu-actions">
              {warehouse &&
                groups.map((group) => (
                  <button
                    disabled={busy}
                    key={group}
                    className={
                      "pro-secondary " + (kind === group ? "active" : "")
                    }
                    onClick={() => chooseGroup(group)}
                  >
                    {labels[group]}
                  </button>
                ))}
              {logistics && data.can_ship && (
                <button
                  className="pro-primary"
                  disabled={busy}
                  onClick={() => {
                    setShipping(true);
                    setKind("");
                  }}
                >
                  สร้างรายการส่งจาก Checkout
                </button>
              )}
            </div>
            {kind && warehouse && chosen && (
              <form
                onSubmit={(e) => {
                  e.preventDefault();
                  void execute(
                    () =>
                      post("/station-workflow/move", {
                        hu_code: code,
                        destination_location_id: chosen.id,
                        note,
                      }),
                    "ย้ายสินค้าไป " + chosen.location_code + " เรียบร้อย",
                  );
                }}
              >
                <h4>{labels[kind]}</h4>
                {kind === "STORAGE" ? (
                  <>
                    <div className="form-grid">
                      <label>
                        โซน
                        <select
                          aria-label="โซนจัดเก็บ"
                          value={chosen.zone_code}
                          onChange={(e) =>
                            first((d) => d.zone_code === e.target.value)
                          }
                        >
                          {values("zone_code", () => true).map((v) => (
                            <option key={String(v)}>{String(v)}</option>
                          ))}
                        </select>
                      </label>
                      <label>
                        ชั้นวาง
                        <select
                          aria-label="ชั้นวางจัดเก็บ"
                          value={chosen.rack_id}
                          onChange={(e) =>
                            first(
                              (d) =>
                                d.zone_code === chosen.zone_code &&
                                d.rack_id === +e.target.value,
                            )
                          }
                        >
                          {values(
                            "rack_id",
                            (d) => d.zone_code === chosen.zone_code,
                          ).map((v) => (
                            <option key={String(v)} value={String(v)}>
                              Rack {v}
                            </option>
                          ))}
                        </select>
                      </label>
                    </div>
                    <div className="form-grid">
                      <label>
                        Bay
                        <select
                          value={chosen.bay_no}
                          onChange={(e) =>
                            first(
                              (d) =>
                                d.rack_id === chosen.rack_id &&
                                d.bay_no === +e.target.value,
                            )
                          }
                        >
                          {values(
                            "bay_no",
                            (d) => d.rack_id === chosen.rack_id,
                          ).map((v) => (
                            <option key={String(v)}>{String(v)}</option>
                          ))}
                        </select>
                      </label>
                      <label>
                        Level
                        <select
                          value={chosen.level_no}
                          onChange={(e) =>
                            first(
                              (d) =>
                                d.rack_id === chosen.rack_id &&
                                d.bay_no === chosen.bay_no &&
                                d.level_no === +e.target.value,
                            )
                          }
                        >
                          {values(
                            "level_no",
                            (d) =>
                              d.rack_id === chosen.rack_id &&
                              d.bay_no === chosen.bay_no,
                          ).map((v) => (
                            <option key={String(v)}>{String(v)}</option>
                          ))}
                        </select>
                      </label>
                    </div>
                    <label>
                      Position
                      <select
                        value={chosen.id}
                        onChange={(e) => setDest(+e.target.value)}
                      >
                        {candidates
                          .filter(
                            (d) =>
                              d.rack_id === chosen.rack_id &&
                              d.bay_no === chosen.bay_no &&
                              d.level_no === chosen.level_no,
                          )
                          .map((d) => (
                            <option key={d.id} value={d.id}>
                              {d.position_no}
                            </option>
                          ))}
                      </select>
                    </label>
                  </>
                ) : (
                  <label>
                    สถานีปลายทาง
                    <select
                      aria-label="สถานีปลายทาง"
                      value={chosen.id}
                      onChange={(e) => setDest(+e.target.value)}
                    >
                      {candidates.map((d) => (
                        <option key={d.id} value={d.id}>
                          {d.location_code}
                        </option>
                      ))}
                    </select>
                  </label>
                )}
                <p className="hu-destination">{chosen.location_code}</p>
                <label>
                  หมายเหตุ / วัตถุประสงค์
                  <input
                    value={note}
                    onChange={(e) => setNote(e.target.value)}
                    placeholder="เช่น QC / ให้ลูกค้าดูตัวอย่าง / คืนเข้าชั้น"
                  />
                </label>
                <button className="pro-primary wide" disabled={busy}>
                  ยืนยันย้ายสินค้า
                </button>
              </form>
            )}
            {shipping && data.can_ship && logistics && (
              <form
                onSubmit={(e) => {
                  e.preventDefault();
                  if (customerResource.loading || customerResource.error || !customers.some(c => c.id === customer)) return;
                  void execute(async () => {
                    const s = await post<Shipment>("/shipments/from-checkout", {
                      hu_code: code,
                      quantity,
                      customer_id: customer,
                    });
                    setCreatedShipment(s);
                    return s;
                  }, "สร้างรายการส่งแล้ว ส่วนที่ไม่ได้ส่งยังอยู่ Checkout และเก็บคืนได้");
                }}
              >
                <h4>สร้างรายการส่งเมื่อพร้อมส่งจริง</h4>
                <label>
                  ลูกค้า
                  <select
                    required
                    aria-label="ลูกค้ารายการส่ง"
                    value={customer || ""}
                    disabled={customerResource.loading || Boolean(customerResource.error) || !customers.length}
                    onChange={(e) => setCustomer(+e.target.value)}
                  >
                    <option value="">{customerResource.loading ? "กำลังโหลดรายชื่อลูกค้า…" : "เลือกลูกค้า"}</option>
                    {customers.map((c) => (
                      <option key={c.id} value={c.id}>
                        {c.customer_name}
                      </option>
                    ))}
                  </select>
                </label>
                {customerResource.error && <p role="alert">โหลดรายชื่อลูกค้าไม่สำเร็จ: {customerResource.error} <button type="button" onClick={() => void customerResource.reload()}>ลองโหลดรายชื่อลูกค้าอีกครั้ง</button></p>}
                {!customerResource.loading && !customerResource.error && !customers.length && <p role="status">ยังไม่มีลูกค้าที่เปิดใช้งาน กรุณาเพิ่มลูกค้าที่หน้า <NavLink to="/master-data">ข้อมูลหลัก</NavLink> แล้วลองโหลดรายชื่ออีกครั้ง <button type="button" onClick={() => void customerResource.reload()}>โหลดรายชื่อลูกค้าใหม่</button></p>}
                <label>
                  จำนวนที่ส่ง ({data.unit})
                  <input
                    required
                    aria-label="จำนวนที่ส่ง"
                    type="number"
                    step=".001"
                    min=".001"
                    max={data.quantity}
                    value={quantity}
                    onChange={(e) => setQuantity(+e.target.value)}
                  />
                </label>
                <p className="pro-muted">
                  ส่งทั้งหมดหรือบางส่วนได้ หากส่งบางส่วน ระบบแยก HU
                  ใหม่ให้สินค้าในรายการส่ง
                </p>
                <p className="pro-muted">
                  เลือกเพียงลูกค้าและจำนวนที่ส่ง
                  รถและคนขับเลือกจากรอบรถที่จอดพร้อมแล้วหลังสินค้าไป Loadout
                </p>
                <button
                  className="pro-primary wide"
                  disabled={busy || customerResource.loading || Boolean(customerResource.error) || !customers.some(c => c.id === customer)}
                >
                  ยืนยันสร้างรายการส่ง
                </button>
              </form>
            )}
            {data.can_cancel && logistics && (
              <div className="hu-cancel">
                <p>
                  หากไม่ส่งแล้ว ให้ยกเลิก Shipment
                  ทั้งรายการเพื่อปลดจองสินค้าทุก HU ก่อนเก็บคืนชั้น
                </p>
                <button
                  className="pro-secondary"
                  disabled={busy}
                  onClick={() => {
                    if (
                      window.confirm(
                        "ยกเลิก " +
                          data.shipment_no +
                          " ทั้งรายการ และปลดจองสินค้าทุก HU?",
                      )
                    )
                      void execute(
                        () =>
                          post(
                            "/shipments/" +
                              data.shipment_id +
                              "/cancel-before-loading",
                            {},
                          ),
                        "ยกเลิกรายการส่งและปลดจองแล้ว เลือกเก็บคืนชั้นได้",
                      );
                  }}
                >
                  ยกเลิก Shipment / ปลดจอง
                </button>
              </div>
            )}
            {!groups.length && !data.can_ship && (
              <p className="pro-muted">
                ยังเคลื่อนย้ายไม่ได้ในสถานะนี้ โปรดดำเนินการตามรายการส่ง / รอบรถ
                หรือรอตำแหน่งว่าง
              </p>
            )}
          </>
        )}
      </div>
    </div>
  );
}
export function InventoryWorkflowPage() {
  const [q, setQ] = useState(
      new URLSearchParams(window.location.search).get("q") || "",
    ),
    [code, setCode] = useState("");
  const { data, loading, error, reload } = useResource<Inventory[]>(
    "/inventory/search?q=" + encodeURIComponent(q),
    [],
  );
  return (
    <section className="inventory-page">
      <div className="pro-page-head">
        <p>INVENTORY & QC</p>
        <h2>ค้นหาสินค้าและเบิกออกจากชั้น</h2>
        <p>
          นำสินค้าไป Checkout เพื่อตรวจ QC หรือดูตัวอย่างก่อน
          ไม่บังคับสร้างรายการส่ง
        </p>
      </div>
      <button className="pro-secondary no-print" onClick={() => window.print()}>
        พิมพ์ QR Labels
      </button>
      <div className="pro-search-field searchbar no-print">
        <input
          aria-label="ค้นหาสินค้าสำหรับเบิก"
          placeholder="ค้นหา SKU, ชื่อสินค้า, HU หรือตำแหน่งชั้นวาง..."
          value={q}
          onChange={(e) => setQ(e.target.value)}
        />
        <button className="pro-secondary" onClick={() => void reload()}>
          ค้นหา
        </button>
      </div>
      {error && <div role="alert">{error}</div>}
      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th>QR</th>
              <th>สินค้า</th>
              <th>HU</th>
              <th>ตำแหน่ง / สถานะ</th>
              <th>จำนวน</th>
              <th>จอง</th>
              <th>ดำเนินการ</th>
            </tr>
          </thead>
          <tbody>
            {data.map((i) => (
              <tr key={i.id}>
                <td>
                  <div className="qr">
                    <QRCode value={i.hu_code} size={44} />
                  </div>
                </td>
                <td>
                  <b>{i.product_name}</b>
                  <small>{i.sku}</small>
                </td>
                <td>{i.hu_code}</td>
                <td>
                  {i.location_code || i.current_node_type}
                  <small>{i.hu_status}</small>
                </td>
                <td>
                  {i.quantity} {i.unit_of_measure}
                </td>
                <td>{i.reserved_quantity}</td>
                <td>
                  {i.current_node_type === "WAREHOUSE_LOCATION" && (
                    <button
                      className="pro-secondary small"
                      onClick={() => setCode(i.hu_code)}
                    >
                      {i.location_type === "STORAGE"
                        ? "เลือกจากตำแหน่งนี้"
                        : "ดำเนินการสินค้า"}
                    </button>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        {!data.length && (
          <div className="pro-empty">
            {loading ? "กำลังค้นหา…" : "ไม่พบสินค้า"}
          </div>
        )}
      </div>
      {code && (
        <HUActions
          code={code}
          onClose={() => setCode("")}
          onChanged={() => void reload()}
        />
      )}
    </section>
  );
}
