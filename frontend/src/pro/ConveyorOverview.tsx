import { useEffect, useState, type CSSProperties } from "react";
import { NavLink, useNavigate } from "react-router-dom";
import {
  ArrowRight,
  Boxes,
  CheckCheck,
  ChevronRight,
  CornerDownLeft,
  Maximize2,
  Package,
  Truck,
  X,
} from "lucide-react";
import { useResource } from "./useResource";
import type { DeliveryRun, StationOverview, WarehouseMapData } from "../types";
import "./conveyor.css";

const runLabel: Record<string, string> = {
  PLANNED: "วางแผนรอบ",
  TRUCK_ARRIVED: "รถถึงคลัง",
  WAITING_DOCK: "จอดรอช่องโหลด",
  AT_DOCK: "เข้าช่องโหลด",
  LOADING: "กำลังโหลด",
  READY_TO_DEPART: "พร้อมออกเดินทาง",
  DEPARTED: "ออกเดินทาง",
  IN_TRANSIT: "กำลังนำส่ง",
};
const phases = [
  {
    type: "INBOUND",
    label: "รับสินค้า",
    subtitle: "Receiving",
    color: "#6a9ff8",
    to: "/inbound",
  },
  {
    type: "STORAGE",
    label: "จัดเก็บบนชั้น",
    subtitle: "Storage",
    color: "#ac99ef",
    to: "/warehouse-map",
  },
  {
    type: "CHECKOUT",
    label: "ตรวจสอบสินค้า",
    subtitle: "Checkout",
    color: "#e7bb78",
    to: "/shipments",
  },
  {
    type: "LOADOUT",
    label: "เตรียมส่งออก",
    subtitle: "Loadout",
    color: "#73ccbb",
    to: "/delivery-runs",
  },
];

function PackageDrawing({ color = "#dfb780" }: { color?: string }) {
  return (
    <svg className="cargo-illustration" viewBox="0 0 66 58" aria-hidden="true">
      <ellipse cx="32" cy="52" rx="24" ry="4" fill="#000" opacity=".16" />
      <path d="M8 20 31 9 56 20 33 32Z" fill={color} />
      <path d="M8 20 33 32 33 51 8 38Z" fill={color} />
      <path d="M33 32 56 20 56 38 33 51Z" fill={color} />
      <path d="M33 32 56 20 56 38 33 51Z" fill="#000" opacity=".16" />
      <path d="m20 14 25 12v19l-7 3V29L14 17Z" fill="#fff" opacity=".25" />
      <path d="m13 31 12 6v8l-12-6Z" fill="#fff" opacity=".55" />
      <path d="m37 20 7 3" stroke="#fff" strokeWidth="2" opacity=".4" />
    </svg>
  );
}

function RackDrawing({ occupied }: { occupied: boolean }) {
  return (
    <svg className="rack-illustration" viewBox="0 0 145 115" aria-hidden="true">
      <ellipse cx="74" cy="105" rx="60" ry="6" fill="#030b19" opacity=".35" />
      <path d="m25 28 80-20 25 16-80 22Z" fill="#424668" />
      <path d="m105 8 25 16v72l-25-10Z" fill="#262e48" />
      <path d="M25 28 105 8v78l-80 22Z" fill="#313a59" />
      <path
        d="m27 49 76-20m-76 44 76-21m-76 44 76-20"
        stroke="#818cb1"
        strokeWidth="4"
      />
      <path d="M25 28v80m80-100v78m25-62v72" stroke="#9eaacb" strokeWidth="4" />
      {occupied && (
        <>
          <path d="m35 67 18-5v-14l-18 5Z" fill="#bd9bdc" />
          <path d="m60 59 29-8V37l-29 8Z" fill="#a69cd9" />
          <path d="m34 91 29-8V69l-29 8Z" fill="#719eb6" />
        </>
      )}
      <path d="m29 31 72-19" stroke="#d5ddf3" strokeWidth="1.5" opacity=".5" />
    </svg>
  );
}

function TruckDrawing({ count, moving }: { count: number; moving: boolean }) {
  return (
    <svg
      className={`truck-illustration ${moving ? "is-moving" : ""}`}
      viewBox="0 0 250 114"
      aria-hidden="true"
    >
      <ellipse cx="128" cy="100" rx="106" ry="7" fill="#051025" opacity=".35" />
      {moving && (
        <g stroke="#689cb9" opacity=".45" strokeWidth="2">
          <path d="M4 52h26M10 68h15M5 80h24" />
        </g>
      )}
      <path d="M40 32 60 18h123l-17 14Z" fill="#9bb2d1" />
      <path d="M166 32 183 18v58l-17 13Z" fill="#405979" />
      <rect x="40" y="32" width="126" height="57" rx="3" fill="#718aaf" />
      <rect x="48" y="39" width="109" height="39" rx="2" fill="#263d5a" />
      <path d="M40 81h126v10H40Z" fill="#526b8d" />
      <path
        d="M181 43h28l22 21v27h-50Z"
        fill={moving ? "#75bfc3" : "#aa9cec"}
      />
      <path d="m188 48 17 1 15 17h-32Z" fill="#233653" />
      <path d="M221 69h10v7h-10Z" fill="#f6d489" />
      <path d="M189 73h10" stroke="#e4e8f8" strokeWidth="2" />
      {Array.from({ length: Math.min(count, 8) }, (_, i) => (
        <g key={i}>
          <rect
            x={54 + (i % 4) * 24}
            y={45 + Math.floor(i / 4) * 15}
            width="19"
            height="12"
            rx="1"
            fill={i % 2 ? "#d2a66e" : "#e2c493"}
          />
          <path
            d={`M${63 + (i % 4) * 24} ${45 + Math.floor(i / 4) * 15}v12`}
            stroke="#f6e3bd"
            strokeWidth="3"
          />
        </g>
      ))}
      {[65, 145, 202].map((x) => (
        <g key={x}>
          <circle cx={x} cy="91" r="12" fill="#101b2d" />
          <circle cx={x} cy="91" r="6" fill="#677890" />
          <circle cx={x} cy="91" r="2" fill="#b3c3d8" />
        </g>
      ))}
    </svg>
  );
}

function StationMachine({
  station,
  color,
  onSelect,
  onSelectHU,
}: {
  station: StationOverview;
  color: string;
  onSelect: () => void;
  onSelectHU: (code: string) => void;
}) {
  const occupied = station.hu_count > 0;
  return (
    <article
      className={`scene-station ${occupied ? "has-cargo" : ""}`}
      style={{ "--station-color": color } as CSSProperties}
    >
      <button
        className="machine-heading"
        onClick={onSelect}
        title="ดูสินค้าทั้งหมดบนสถานี"
      >
        <i className={occupied ? "busy" : ""} />
        <div>
          <b>{station.station_name}</b>
          <span>{station.station_code}</span>
        </div>
        <strong>
          {station.hu_count}
          <small>/{station.capacity_hu}</small>
        </strong>
        <Maximize2 size={13} />
      </button>
      <div className="machine-surface">
        <div className="machine-cargo">
          {station.items.map((item, index) => (
            <button
              className="scene-cargo"
              onClick={() => onSelectHU(item.hu_code)}
              key={`${item.hu_code}-${item.sku}-${index}`}
              title={`${item.product_name} · ${item.hu_code} · ${item.quantity} ${item.unit_of_measure}`}
            >
              <PackageDrawing color={color} />
              <div>
                <b>{item.product_name}</b>
                <span>
                  {item.quantity} {item.unit_of_measure}
                </span>
                <small>{item.hu_code}</small>
              </div>
            </button>
          ))}
          {!station.items.length && (
            <div className="scene-station-empty">
              <Boxes size={22} />
              <span>พร้อมรับสินค้า</span>
            </div>
          )}
        </div>
        <div className="machine-rollers">
          <i />
          <i />
          <i />
          <i />
          <i />
          <i />
          <i />
          <i />
          <i />
          <i />
          <i />
        </div>
      </div>
      <footer>
        <span>{occupied ? "มีสินค้าบนสถานี" : "สถานีว่าง"}</span>
        <div>
          <i
            style={{
              width: `${Math.min(100, (station.hu_count / Math.max(1, station.capacity_hu)) * 100)}%`,
            }}
          />
        </div>
      </footer>
    </article>
  );
}

function FleetRun({ run, moving }: { run: DeliveryRun; moving: boolean }) {
  const activeShipments = run.shipments.filter((s) => s.status !== "CANCELLED");
  const cargo = activeShipments.flatMap((s) =>
    s.items.filter((i) => i.current_status === "LOADED"),
  );
  return (
    <NavLink
      className={`scene-truck ${moving ? "on-road" : "at-yard"}`}
      to={`/delivery-runs/${run.id}`}
      aria-label={`ดูรอบรถ ${run.vehicle_code} ${run.run_no}`}
    >
      <div className="truck-card-heading">
        <div>
          <b>{run.vehicle_code}</b>
          <span>{run.license_plate}</span>
        </div>
        <span className="truck-state">
          <i />
          {runLabel[run.status] || run.status}
        </span>
      </div>
      <div className="truck-portrait">
        <div className="truck-road" />
        <TruckDrawing count={cargo.length} moving={moving} />
        <span>{cargo.length} HU บนรถ</span>
      </div>
      <div className="truck-card-details">
        <div>
          <span>คนขับ</span>
          <b>{run.driver_name}</b>
        </div>
        <div>
          <span>{moving ? "รอบการนำส่ง" : "ช่องโหลด"}</span>
          <b>{moving ? run.run_no : run.loading_dock_code || "ยังไม่กำหนด"}</b>
        </div>
      </div>
      <div className="truck-manifest-preview">
        {activeShipments.slice(0, 3).map((s) => (
          <span key={s.id}>
            <Package size={12} />
            <b>{s.customer_name}</b>
            <small>{s.items.length} HU</small>
          </span>
        ))}
        {activeShipments.length > 3 && (
          <small>อีก {activeShipments.length - 3} รายการในรอบนี้</small>
        )}
      </div>
      <footer>
        <b>{activeShipments.length} รายการจัดส่ง</b>
        <span>
          ดูสินค้าในรถ <ArrowRight size={13} />
        </span>
      </footer>
    </NavLink>
  );
}

export function ConveyorOverview({
  stations,
  runs,
  updated,
  error,
  onSelectStation,
  onSelectHU,
}: {
  stations: StationOverview[];
  runs: DeliveryRun[];
  updated: Date | null;
  error: string;
  onSelectStation: (station: StationOverview) => void;
  onSelectHU: (code: string) => void;
}) {
  const { data: map, error: mapError } = useResource<WarehouseMapData | null>(
    "/warehouse-map/live",
    null,
    15000,
  );
  const navigate = useNavigate();
  const [chosenZone, setChosenZone] = useState<
    WarehouseMapData["zones"][number] | null
  >(null);
  useEffect(() => {
    if (!chosenZone) return;
    const key = (e: KeyboardEvent) => {
      if (e.key === "Escape") setChosenZone(null);
    };
    document.addEventListener("keydown", key);
    return () => document.removeEventListener("keydown", key);
  }, [chosenZone]);
  const waiting = runs.filter(
    (r) => !["DEPARTED", "IN_TRANSIT"].includes(r.status),
  );
  const moving = runs.filter((r) =>
    ["DEPARTED", "IN_TRANSIT"].includes(r.status),
  );
  const returns = stations.filter((s) => s.station_type === "RETURN");
  const stored =
    map?.zones.reduce(
      (n, z) => n + z.racks.reduce((s, r) => s + r.hu_count, 0),
      0,
    ) || 0;
  const pendingReturns = returns.reduce((n, s) => n + s.hu_count, 0);
  const failed = Boolean(error || mapError);
  return (
    <div className="conveyor-overview" data-testid="conveyor-overview">
      <div className="scene-toolbar">
        <div>
          <span className="scene-kicker">OPERATIONS DIGITAL TWIN</span>
          <h3>เส้นทางสินค้าภายในคลัง</h3>
          <p>
            ภาพสถานีและตำแหน่งสินค้าจริง · กดสถานีหรือกล่องเพื่อดูรายละเอียด
          </p>
        </div>
        <div className={`scene-connection ${failed ? "disconnected" : ""}`}>
          <span>
            <i />
            {failed ? "ข้อมูลไม่อัปเดต" : "LIVE DATA"}
          </span>
          <small>
            {updated
              ? updated.toLocaleTimeString("th-TH", {
                  timeZone: "Asia/Bangkok",
                  hour: "2-digit",
                  minute: "2-digit",
                  second: "2-digit",
                })
              : "กำลังเชื่อมต่อ"}{" "}
            · อัปเดตทุก 15 วินาที
          </small>
        </div>
      </div>
      {mapError && (
        <div className="scene-error" role="alert">
          {mapError}
        </div>
      )}
      <div
        className="warehouse-scene"
        role="region"
        aria-label="ภาพจำลองกระบวนการภายในคลัง"
      >
        <div className="scene-floor">
          <div className="scene-process">
            {phases.map((phase, index) => (
              <div
                className={`scene-phase phase-${phase.type.toLowerCase()}`}
                style={{ "--phase-color": phase.color } as CSSProperties}
                key={phase.type}
              >
                <div className="scene-phase-title">
                  <span>0{index + 1}</span>
                  <div>
                    <b>{phase.label}</b>
                    <small>{phase.subtitle}</small>
                  </div>
                  <strong>
                    {phase.type === "STORAGE"
                      ? stored
                      : stations
                          .filter((s) => s.station_type === phase.type)
                          .reduce((n, s) => n + s.hu_count, 0)}
                    <small>HU</small>
                  </strong>
                </div>
                <div className="phase-machines">
                  {phase.type === "STORAGE" ? (
                    <div className="scene-storage">
                      {map?.zones.map((z) => (
                        <button
                          className="scene-zone"
                          key={z.id}
                          type="button"
                          aria-label={`ดูชั้นวางโซน ${z.zone_code}`}
                          onClick={() =>
                            z.racks.length === 1
                              ? navigate(`/racks/${z.racks[0].id}/map`)
                              : setChosenZone(z)
                          }
                          title={`เปิดชั้นวางในโซน ${z.zone_code}`}
                        >
                          <RackDrawing
                            occupied={z.racks.some((r) => r.hu_count > 0)}
                          />
                          <div>
                            <b>{z.zone_code}</b>
                            <span>{z.zone_name}</span>
                            <small>
                              {z.racks.reduce((n, r) => n + r.hu_count, 0)} HU ·{" "}
                              {z.racks.length} ชั้นวาง
                            </small>
                          </div>
                          <strong>{z.utilization_percent}%</strong>
                        </button>
                      ))}
                      {!map && (
                        <div className="scene-station-empty">
                          กำลังโหลดชั้นวาง…
                        </div>
                      )}
                    </div>
                  ) : (
                    stations
                      .filter((s) => s.station_type === phase.type)
                      .map((s) => (
                        <StationMachine
                          key={s.id}
                          station={s}
                          color={phase.color}
                          onSelect={() => onSelectStation(s)}
                          onSelectHU={onSelectHU}
                        />
                      ))
                  )}
                  {phase.type !== "STORAGE" &&
                    !stations.some((s) => s.station_type === phase.type) && (
                      <div className="scene-station-empty">
                        ยังไม่มีสถานีในขั้นตอนนี้
                      </div>
                    )}
                </div>
                <NavLink className="scene-phase-action" to={phase.to}>
                  เปิดงาน{phase.label}
                  <ChevronRight size={14} />
                </NavLink>
                {index < phases.length - 1 && (
                  <div className="phase-conveyor" aria-hidden="true">
                    <div />
                    <ChevronRight size={15} />
                    <i />
                    <i />
                  </div>
                )}
              </div>
            ))}
          </div>
          <div className="scene-floor-caption">
            <span>
              <i />
              สินค้าอยู่ที่ตำแหน่งล่าสุดที่บันทึกในระบบ
            </span>
            <span>
              <CheckCheck size={13} /> Inbound → Storage → Checkout → Loadout
            </span>
          </div>
        </div>
      </div>
      <div className="scene-handoff">
        <span />
        <div>
          <CornerDownLeft size={16} /> จาก Loadout
          เข้าสู่พื้นที่โหลดรถและการขนส่ง
        </div>
        <span />
      </div>
      <div className="scene-logistics">
        <section
          className="scene-fleet loading-fleet"
          aria-label="พื้นที่รถเตรียมโหลดและกำลังโหลด"
        >
          <div className="fleet-area-heading">
            <div className="fleet-area-icon">
              <Truck size={22} />
            </div>
            <div>
              <span>LOADING YARD</span>
              <h3>เตรียมรถและโหลดสินค้า</h3>
              <p>รถรอเข้าจอด เข้าช่องโหลด และรอออกเดินทาง</p>
            </div>
            <strong>
              {waiting.length}
              <small>คัน</small>
            </strong>
          </div>
          <div className="scene-fleet-cards">
            {waiting.map((r) => (
              <FleetRun key={r.id} run={r} moving={false} />
            ))}
            {!waiting.length && (
              <div className="scene-fleet-empty">
                <Truck size={36} />
                <b>พื้นที่โหลดพร้อมใช้งาน</b>
                <span>ยังไม่มีรอบรถเตรียมโหลดในขณะนี้</span>
              </div>
            )}
          </div>
          <NavLink className="fleet-area-link" to="/delivery-runs">
            จัดการรอบรถและช่องโหลด
            <ArrowRight size={14} />
          </NavLink>
        </section>
        <section
          className="scene-fleet delivery-fleet"
          aria-label="พื้นที่รถกำลังนำส่ง"
        >
          <div className="fleet-area-heading">
            <div className="fleet-area-icon">
              <Truck size={22} />
            </div>
            <div>
              <span>ON THE ROAD</span>
              <h3>รถกำลังนำส่งสินค้า</h3>
              <p>หนึ่งการ์ดต่อรอบรถ พร้อมรายการสินค้าทั้งคัน</p>
            </div>
            <strong>
              {moving.length}
              <small>คัน</small>
            </strong>
          </div>
          <div className="scene-fleet-cards">
            {moving.map((r) => (
              <FleetRun key={r.id} run={r} moving />
            ))}
            {!moving.length && (
              <div className="scene-fleet-empty">
                <Truck size={36} />
                <b>ยังไม่มีรถกำลังนำส่ง</b>
                <span>รถจะแสดงที่นี่หลังบันทึกออกเดินทาง</span>
              </div>
            )}
          </div>
          <NavLink className="fleet-area-link" to="/driver">
            ติดตามการส่งมอบและ POD
            <ArrowRight size={14} />
          </NavLink>
        </section>
      </div>
      <div className="scene-return-area">
        <div>
          <CornerDownLeft size={18} />
          <span>
            <b>สินค้าคืนรอดำเนินการ</b>
            <small>{pendingReturns} HU · ตรวจสอบก่อนจัดเก็บกลับ</small>
          </span>
        </div>
        <div>
          {returns
            .flatMap((s) => s.items)
            .map((item, i) => (
              <button
                className="return-workflow-item"
                key={`${item.hu_code}-${i}`}
                onClick={() => onSelectHU(item.hu_code)}
              >
                <Package size={15} />
                <span>
                  <b>{item.hu_code}</b>
                  <small>
                    {item.sku} · {item.quantity} {item.unit_of_measure}
                  </small>
                </span>
                <ArrowRight size={13} />
              </button>
            ))}
          {!pendingReturns && (
            <span className="return-clear">ไม่มีสินค้าคืนค้าง</span>
          )}
        </div>
      </div>
      {chosenZone && (
        <div className="pro-overlay" onClick={() => setChosenZone(null)}>
          <div
            className="pro-dialog"
            role="dialog"
            aria-modal="true"
            aria-label={`เลือกชั้นวางโซน ${chosenZone.zone_code}`}
            onClick={(e) => e.stopPropagation()}
          >
            <div className="panel-heading">
              <div>
                <p>ZONE {chosenZone.zone_code}</p>
                <h3>เลือกชั้นวาง · {chosenZone.zone_name}</h3>
              </div>
              <button
                className="pro-icon-button"
                autoFocus
                onClick={() => setChosenZone(null)}
                aria-label="ปิดตัวเลือกชั้นวาง"
              >
                <X size={20} />
              </button>
            </div>
            <div className="zone-rack-options">
              {chosenZone.racks.map((r) => (
                <NavLink
                  key={r.id}
                  to={`/racks/${r.id}/map`}
                  onClick={() => setChosenZone(null)}
                >
                  <RackDrawing occupied={r.hu_count > 0} />
                  <div>
                    <b>{r.rack_code}</b>
                    <small>
                      {r.rack_name || "ชั้นวางสินค้า"} ·{" "}
                      {r.occupied + r.reserved}/{r.total} ตำแหน่งใช้งาน
                    </small>
                  </div>
                  <span>{r.hu_count} HU</span>
                  <ArrowRight size={16} />
                </NavLink>
              ))}
              {!chosenZone.racks.length && (
                <div className="pro-empty">โซนนี้ยังไม่มีชั้นวาง</div>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
