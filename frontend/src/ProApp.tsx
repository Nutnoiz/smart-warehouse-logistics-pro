import { createContext, useContext, useEffect, useState } from "react";
import {
  NavLink,
  Route,
  Routes,
  useLocation,
  useNavigate,
} from "react-router-dom";
import {
  Activity,
  ArrowDownToLine,
  ArrowRight,
  BarChart3,
  Boxes,
  Check,
  ClipboardCheck,
  ClipboardList,
  Command,
  Layers3,
  LogOut,
  Map,
  Menu,
  Package,
  RefreshCw,
  Search,
  Settings,
  ShieldCheck,
  Truck,
  Warehouse,
  X,
} from "lucide-react";
import { api, post } from "./api";
import { LegacyWorkspace as OperationalWorkspace } from "./App";
import { useResource } from "./pro/useResource";
import {
  CountPage,
  ReportsPage,
  SettingsPage,
  TasksPage,
  UsersPage,
} from "./pro/Management";
import { TransferPage } from "./pro/Transfer";
import { ConveyorOverview } from "./pro/ConveyorOverview";
import { SampleControls } from "./pro/SampleControls";
import { HUActions } from "./pro/HUActions";
function LegacyWorkspace() {
  const location = useLocation();
  return location.pathname === "/transfer" ? (
    <TransferPage />
  ) : (
    <OperationalWorkspace />
  );
}
import type { DeliveryRun, Inventory, StationOverview } from "./types";

export type Account = {
  id: number;
  username: string;
  role: string;
  permissions: string[];
  demo_mode: boolean;
};
const AccountContext = createContext<Account | null>(null);
export const useAccount = () => useContext(AccountContext)!;
export const roleLabels: Record<string, string> = {
  ADMIN: "ผู้ดูแลระบบ",
  MANAGER: "ผู้จัดการคลัง",
  OPERATOR: "เจ้าหน้าที่คลัง",
  LOGISTICS: "เจ้าหน้าที่ขนส่ง",
  VIEWER: "ดูข้อมูลเท่านั้น",
};
export const statusLabels: Record<string, string> = {
  PLANNED: "วางแผน",
  PICKING: "กำลังเบิก",
  READY_TO_LOAD: "รอโหลด",
  LOADING: "กำลังโหลด",
  LOADED: "โหลดครบ",
  DEPARTED: "ออกเดินทาง",
  IN_TRANSIT: "กำลังนำส่ง",
  ARRIVED: "ถึงปลายทาง",
  DELIVERED: "ส่งสำเร็จ",
  DELIVERY_FAILED: "ส่งไม่สำเร็จ",
  RETURNING: "กำลังคืน",
  RETURNED: "คืนแล้ว",
  CANCELLED: "ยกเลิก",
  PENDING: "รอดำเนินการ",
  IN_PROGRESS: "กำลังทำ",
  COMPLETED: "เสร็จแล้ว",
  APPROVED: "อนุมัติแล้ว",
  REJECTED: "ปฏิเสธ",
  WAITING_DOCK: "จอดรอ",
  AT_DOCK: "เข้าประตูโหลด",
  READY_TO_DEPART: "พร้อมออก",
  STORED: "จัดเก็บแล้ว",
};
export const dateTime = (value: string) =>
  new Date(value).toLocaleString("th-TH", {
    timeZone: "Asia/Bangkok",
    day: "numeric",
    month: "short",
    hour: "2-digit",
    minute: "2-digit",
  });
export function Notice({ error }: { error: string }) {
  return error ? (
    <div className="pro-notice error" role="alert">
      {error}
    </div>
  ) : null;
}
export function PageHead({
  kicker,
  title,
  description,
  action,
}: {
  kicker: string;
  title: string;
  description: string;
  action?: React.ReactNode;
}) {
  return (
    <div className="pro-page-head">
      <div>
        <p>{kicker}</p>
        <h2>{title}</h2>
        <span>{description}</span>
      </div>
      {action}
    </div>
  );
}
export function Badge({ value }: { value: string }) {
  return (
    <span className={`pro-badge badge-${value.toLowerCase()}`}>
      {statusLabels[value] || value}
    </span>
  );
}

const navigation = [
  {
    group: "ศูนย์ควบคุม",
    items: [
      { path: "/dashboard", label: "ภาพรวมปฏิบัติการ", icon: Activity },
      { path: "/tasks", label: "คิวงานคลัง", icon: ClipboardList },
      { path: "/transfer", label: "ย้ายสินค้าระหว่างชั้น", icon: Boxes },
      { path: "/warehouse-map", label: "แผนผังคลังสินค้า", icon: Map },
    ],
  },
  {
    group: "ปฏิบัติงาน",
    items: [
      { path: "/inbound", label: "รับเข้าและจัดเก็บ", icon: ArrowDownToLine },
      { path: "/inventory", label: "ค้นหาและเบิกสินค้า", icon: Search },
      { path: "/shipments", label: "รายการจัดส่ง", icon: Package },
      { path: "/delivery-runs", label: "รอบรถและการโหลด", icon: Truck },
      { path: "/driver", label: "ส่งมอบและ POD", icon: Check },
      { path: "/counts", label: "ตรวจนับสต็อก", icon: ClipboardCheck },
    ],
  },
  {
    group: "บริหารจัดการ",
    items: [
      { path: "/reports", label: "รายงานและส่งออก", icon: BarChart3 },
      { path: "/master-data", label: "ข้อมูลหลัก", icon: Layers3 },
      { path: "/racks", label: "ตั้งค่าชั้นวาง", icon: Boxes },
      { path: "/stations", label: "สถานีปฏิบัติงาน", icon: Warehouse },
      { path: "/loading-docks", label: "ประตูโหลด", icon: Truck },
      {
        path: "/audit",
        label: "ประวัติการทำรายการ",
        icon: ShieldCheck,
        permission: "audit",
      },
      {
        path: "/users",
        label: "ผู้ใช้และสิทธิ์",
        icon: ShieldCheck,
        permission: "users",
      },
      { path: "/settings", label: "ตั้งค่าบัญชีและระบบ", icon: Settings },
    ],
  },
];

function Login({ onLogin }: { onLogin: () => void }) {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  async function submit(e: React.FormEvent) {
    e.preventDefault();
    if (busy) return;
    setBusy(true);
    setError("");
    try {
      const result = await post<{ access_token: string }>("/auth/login", {
        username,
        password,
      });
      localStorage.setItem("warehouse_token", result.access_token);
      onLogin();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <div className="pro-login">
      <div className="login-story">
        <div className="pro-logo">
          <div>
            <Warehouse size={25} />
          </div>
          <span>
            warehouse<span>PRO</span>
          </span>
        </div>
        <div className="story-content">
          <p className="pro-kicker">WAREHOUSE & LOGISTICS PLATFORM</p>
          <h1>
            ทุกสินค้า ทุกตำแหน่ง
            <br />
            <em>ทุกขั้นตอน เชื่อมถึงกัน</em>
          </h1>
          <p>
            จัดการคลังสินค้าและการขนส่งในพื้นที่เดียว
            <br />
            จากรับเข้า จัดเก็บ จนถึงส่งมอบพร้อมหลักฐาน
          </p>
          <div className="login-blueprint">
            {["INBOUND", "STORAGE", "CHECKOUT", "LOADOUT", "DELIVERY"].map(
              (s, i) => (
                <div key={s}>
                  <span>0{i + 1}</span>
                  {i === 4 ? <Truck /> : <Package />}
                  <b>{s}</b>
                  <i />
                </div>
              ),
            )}
          </div>
          <div className="story-benefits">
            <span>
              <ShieldCheck size={16} /> สิทธิ์ตามหน้าที่
            </span>
            <span>
              <Activity size={16} /> ติดตามสินค้า
            </span>
            <span>
              <ClipboardCheck size={16} /> ตรวจสอบย้อนหลัง
            </span>
          </div>
        </div>
        <small>Smart Warehouse Pro · Version 2</small>
      </div>
      <div className="login-form-area">
        <form onSubmit={submit}>
          <div className="login-security">
            <ShieldCheck size={20} />
          </div>
          <p className="pro-kicker">ยินดีต้อนรับกลับ</p>
          <h2>เข้าสู่พื้นที่ทำงาน</h2>
          <p>ใช้บัญชีที่ผู้ดูแลระบบมอบหมายให้คุณ</p>
          <label>
            ชื่อผู้ใช้
            <input
              required
              autoFocus
              autoComplete="username"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              placeholder="กรอกชื่อผู้ใช้"
            />
          </label>
          <label>
            รหัสผ่าน
            <input
              required
              autoComplete="current-password"
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="กรอกรหัสผ่าน"
            />
          </label>
          <Notice error={error} />
          <button className="pro-primary" disabled={busy}>
            {busy ? "กำลังตรวจสอบ…" : "เข้าสู่ระบบ"}
            <ArrowRight size={18} />
          </button>
          <div className="login-help">
            บัญชีตัวอย่างสำหรับตรวจระบบ: <b>admin / 0000</b>
            <small>เปลี่ยนรหัสผ่านก่อนใช้งานจริง</small>
          </div>
        </form>
        <span className="login-footer">
          WAREHOUSE PRO · OPERATIONS, CONNECTED.
        </span>
      </div>
    </div>
  );
}

function QuickSearch({ onClose }: { onClose: () => void }) {
  const [query, setQuery] = useState("");
  const [rows, setRows] = useState<Inventory[]>([]);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const navigate = useNavigate();
  useEffect(() => {
    const controller = new AbortController();
    if (!query.trim()) {
      setRows([]);
      setBusy(false);
      return;
    }
    setBusy(true);
    const timer = setTimeout(() => {
      void api<Inventory[]>(
        `/inventory/search?q=${encodeURIComponent(query)}`,
        { signal: controller.signal },
      )
        .then((data) => {
          setRows(data);
          setError("");
        })
        .catch((e) => {
          if (!controller.signal.aborted) setError(e.message);
        })
        .finally(() => {
          if (!controller.signal.aborted) setBusy(false);
        });
    }, 250);
    return () => {
      clearTimeout(timer);
      controller.abort();
    };
  }, [query]);
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    document.addEventListener("keydown", handler);
    return () => document.removeEventListener("keydown", handler);
  }, [onClose]);
  return (
    <div className="pro-overlay" onClick={onClose}>
      <div
        className="command-palette"
        role="dialog"
        aria-modal="true"
        aria-label="ค้นหาสินค้า"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="command-input">
          <Search />
          <input
            autoFocus
            placeholder="SKU, ชื่อสินค้า, HU, Lot หรือตำแหน่ง…"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
          />
          <button onClick={onClose} aria-label="ปิดค้นหา">
            <X size={20} />
          </button>
        </div>
        <Notice error={error} />
        {busy ? (
          <div className="pro-empty">กำลังค้นหา…</div>
        ) : rows.length ? (
          rows.slice(0, 20).map((row) => (
            <button
              className="command-result"
              key={row.id}
              onClick={() => {
                navigate(`/inventory?q=${encodeURIComponent(query)}`);
                onClose();
              }}
            >
              <Package size={19} />
              <div>
                <b>{row.product_name}</b>
                <span>
                  {row.sku} · {row.hu_code}
                </span>
              </div>
              <div>
                <b>
                  {row.quantity} {row.unit_of_measure}
                </b>
                <span>{row.location_code || row.current_node_type}</span>
              </div>
              <ArrowRight size={16} />
            </button>
          ))
        ) : (
          <div className="pro-empty">
            {query
              ? "ไม่พบสินค้าในคำค้นหานี้"
              : "ค้นหาสินค้าจริงในคลังและระหว่างจัดส่ง"}
          </div>
        )}
        <footer>กด Esc เพื่อปิด · แสดงไม่เกิน 20 รายการ</footer>
      </div>
    </div>
  );
}

function Shell({
  account,
  onLogout,
}: {
  account: Account;
  onLogout: () => void;
}) {
  const [open, setOpen] = useState(false);
  const [search, setSearch] = useState(false);
  const location = useLocation();
  const title =
    location.pathname === "/"
      ? "ภาพรวมปฏิบัติการ"
      : navigation
          .flatMap((g) => g.items)
          .find((i) => i.path === location.pathname)?.label ||
        "รายละเอียดรายการ";
  useEffect(() => {
    setOpen(false);
    window.scrollTo({ top: 0 });
  }, [location.pathname]);
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key === "k") {
        e.preventDefault();
        setSearch((v) => !v);
      }
    };
    document.addEventListener("keydown", handler);
    return () => document.removeEventListener("keydown", handler);
  }, []);
  return (
    <AccountContext.Provider value={account}>
      <div className="pro-shell">
        {open && (
          <div className="nav-backdrop" onClick={() => setOpen(false)} />
        )}
        <aside className={`pro-sidebar ${open ? "is-open" : ""}`}>
          <NavLink to="/dashboard" className="pro-logo">
            <div>
              <Warehouse size={23} />
            </div>
            <span>
              warehouse<span>PRO</span>
            </span>
          </NavLink>
          <div className="workspace-name">
            <span>OPERATIONS WORKSPACE</span>
            <b>คลังสินค้าและการขนส่ง</b>
            <small>ทุกสถานะ เชื่อมต่อในระบบเดียว</small>
          </div>
          <nav>
            {navigation.map((g) => (
              <div className="nav-group" key={g.group}>
                <p>{g.group}</p>
                {g.items
                  .filter(
                    (i) =>
                      !("permission" in i) ||
                      account.permissions.includes(i.permission!),
                  )
                  .map((i) => (
                    <NavLink key={i.path} to={i.path}>
                      <i.icon size={18} />
                      <span>{i.label}</span>
                    </NavLink>
                  ))}
              </div>
            ))}
          </nav>
          <div className="sidebar-account">
            <div>{account.username.slice(0, 2).toUpperCase()}</div>
            <span>
              <b>{account.username}</b>
              <small>{roleLabels[account.role]}</small>
            </span>
            <button
              onClick={onLogout}
              title="ออกจากระบบ"
              aria-label="ออกจากระบบ"
            >
              <LogOut size={18} />
            </button>
          </div>
        </aside>
        <div className="pro-main">
          <header className="pro-topbar">
            <div>
              <button
                className="pro-mobile-menu"
                onClick={() => setOpen(true)}
                aria-label="เปิดเมนู"
              >
                <Menu />
              </button>
              <span>
                พื้นที่ทำงาน <b>/</b> {title}
              </span>
            </div>
            <div>
              <button
                className="pro-search-button"
                onClick={() => setSearch(true)}
              >
                <Search size={16} />
                <span>ค้นหาสินค้า</span>
                <kbd>
                  <Command size={11} /> K
                </kbd>
              </button>
              <span className="pro-environment">
                {account.demo_mode ? "DEMO" : "LIVE"}
              </span>
              <NavLink to="/settings" className="pro-user-avatar">
                {account.username.slice(0, 2).toUpperCase()}
              </NavLink>
            </div>
          </header>
          <div className="pro-content" data-mode={account.role.toLowerCase()}>
            <Routes>
              <Route path="/" element={<CommandCenter />} />
              <Route path="/dashboard" element={<CommandCenter />} />
              <Route path="/tasks" element={<TasksPage />} />
              <Route path="/counts" element={<CountPage />} />
              <Route path="/reports" element={<ReportsPage />} />
              <Route
                path="/settings"
                element={<SettingsPage onLogout={onLogout} />}
              />
              <Route
                path="/users"
                element={
                  account.permissions.includes("users") ? (
                    <UsersPage />
                  ) : (
                    <div className="pro-empty">
                      บัญชีนี้ไม่มีสิทธิ์จัดการผู้ใช้
                    </div>
                  )
                }
              />
              <Route path="*" element={<LegacyWorkspace />} />
            </Routes>
          </div>
          <footer className="pro-app-footer">
            <span>Smart Warehouse Pro</span>
            <span>2.0.0 RC · {roleLabels[account.role]}</span>
          </footer>
        </div>
        {search && <QuickSearch onClose={() => setSearch(false)} />}
      </div>
    </AccountContext.Provider>
  );
}

type Overview = {
  shipments: Record<string, number>;
  stations: Record<string, number>;
  locations: Record<string, number>;
  total_locations: number;
  utilization: number;
  pending_counts: number;
  product_count: number;
  hu_count: number;
  recent: {
    id: number;
    action: string;
    entity: string;
    reference: string;
    username: string;
    at: string;
  }[];
};
const emptyOverview: Overview = {
  shipments: {},
  stations: {},
  locations: {},
  total_locations: 0,
  utilization: 0,
  pending_counts: 0,
  product_count: 0,
  hu_count: 0,
  recent: [],
};
function CommandCenter() {
  const {
    data: d,
    error,
    loading,
    updated,
    reload,
  } = useResource<Overview>("/pro/overview", emptyOverview, 15000);
  const {
    data: stations,
    error: stationError,
    reload: reloadStations,
  } = useResource<StationOverview[]>("/stations/overview", [], 15000);
  const {
    data: runs,
    error: runError,
    reload: reloadRuns,
  } = useResource<DeliveryRun[]>("/delivery-runs?active_only=true", [], 15000);
  const [selected, setSelected] = useState<StationOverview | null>(null);
  const [actionHU, setActionHU] = useState("");
  const [datasetRevision, setDatasetRevision] = useState(0);
  const [flowView, setFlowView] = useState<"cards" | "conveyor">(() =>
    localStorage.getItem("warehouse_dashboard_view") === "conveyor"
      ? "conveyor"
      : "cards",
  );
  useEffect(() => {
    localStorage.setItem("warehouse_dashboard_view", flowView);
  }, [flowView]);
  const stages = [
    {
      key: "INBOUND",
      label: "รับเข้า",
      desc: "ตรวจรับและรอจัดเก็บ",
      to: "/inbound",
      tone: "blue",
    },
    {
      key: "STORAGE",
      label: "จัดเก็บ",
      desc: "ค้นหาและเบิกจากชั้น",
      to: "/warehouse-map",
      tone: "violet",
    },
    {
      key: "CHECKOUT",
      label: "ตรวจสินค้า",
      desc: "ตรวจจำนวนก่อนส่ง",
      to: "/shipments",
      tone: "amber",
    },
    {
      key: "LOADOUT",
      label: "รอโหลด",
      desc: "เตรียมขึ้นรถขนส่ง",
      to: "/delivery-runs",
      tone: "teal",
    },
  ];
  const onRoute = runs.filter((r) =>
    ["DEPARTED", "IN_TRANSIT"].includes(r.status),
  );
  const waiting = runs.filter(
    (r) => !["DEPARTED", "IN_TRANSIT"].includes(r.status),
  );
  return (
    <div className="command-center">
      <PageHead
        kicker="OPERATIONS COMMAND CENTER"
        title="ภาพรวมปฏิบัติการ"
        description="งานที่ต้องทำ สินค้าที่ต้องดู และการจัดส่งที่ต้องติดตาม"
        action={
          <button
            className="pro-secondary"
            onClick={() => {
              void reload();
              void reloadStations();
              void reloadRuns();
            }}
          >
            <RefreshCw size={15} /> อัปเดตข้อมูล
          </button>
        }
      />
      <SampleControls
        onChanged={() => {
          void reload();
          void reloadStations();
          void reloadRuns();
          setSelected(null);
          setDatasetRevision((v) => v + 1);
        }}
      />
      <Notice error={error || stationError || runError} />
      <div className="welcome-banner">
        <div>
          <span>
            <i />{" "}
            {error || stationError || runError
              ? "การเชื่อมต่อขัดข้อง"
              : loading
                ? "กำลังเชื่อมต่อระบบ"
                : "เชื่อมต่อข้อมูลปฏิบัติงาน"}
          </span>
          <h3>ทุกขั้นตอนของคลัง อยู่ในมุมมองเดียว</h3>
          <p>
            เริ่มจากงานรับค้าง ตรวจสินค้าก่อนโหลด
            และดูรถแต่ละรอบพร้อมรายการสินค้า
          </p>
        </div>
        <div className="banner-clock">
          <b>
            {new Date().toLocaleDateString("th-TH", {
              day: "numeric",
              month: "long",
            })}
          </b>
          <span>
            {updated
              ? `ข้อมูลล่าสุด ${updated.toLocaleTimeString("th-TH")}`
              : "กำลังโหลดข้อมูล…"}
          </span>
        </div>
      </div>
      <div className="pro-metrics">
        {[
          {
            label: "สินค้ารอจัดเก็บ",
            value: d.stations.INBOUND || 0,
            unit: "HU",
            icon: ArrowDownToLine,
            to: "/inbound",
            hint: "เริ่ม Putaway",
          },
          {
            label: "พื้นที่จัดเก็บใช้แล้ว",
            value: d.utilization,
            unit: "%",
            icon: Warehouse,
            to: "/warehouse-map",
            hint: `${d.locations.OCCUPIED || 0} / ${d.total_locations} ตำแหน่ง`,
          },
          {
            label: "รถกำลังนำส่ง",
            value: onRoute.length,
            unit: "คัน",
            icon: Truck,
            to: "/driver",
            hint: `${onRoute.reduce((n, r) => n + r.shipments.length, 0)} รายการจัดส่ง`,
          },
          {
            label: "ตรวจนับรออนุมัติ",
            value: d.pending_counts,
            unit: "รายการ",
            icon: ClipboardCheck,
            to: "/counts",
            hint: "ตรวจสอบผลต่างสต็อก",
          },
        ].map((m) => (
          <NavLink to={m.to} className="pro-metric" key={m.label}>
            <div>
              <span>{m.label}</span>
              <m.icon size={18} />
            </div>
            <strong>
              {loading ? "—" : m.value.toLocaleString()}
              <small>{m.unit}</small>
            </strong>
            <footer>
              {m.hint}
              <ArrowRight size={14} />
            </footer>
          </NavLink>
        ))}
      </div>
      <div className="section-heading">
        <div>
          <p>WAREHOUSE FLOW</p>
          <h3>สินค้าอยู่ที่ไหนตอนนี้</h3>
        </div>
        <div
          className="pro-tabs dashboard-view-switch"
          aria-label="มุมมอง Dashboard"
        >
          <button
            className={flowView === "cards" ? "selected" : ""}
            aria-pressed={flowView === "cards"}
            onClick={() => setFlowView("cards")}
          >
            สถานีแบบการ์ด
          </button>
          <button
            className={flowView === "conveyor" ? "selected" : ""}
            aria-pressed={flowView === "conveyor"}
            onClick={() => setFlowView("conveyor")}
          >
            ภาพจำลองสายพาน
          </button>
        </div>
      </div>
      {flowView === "cards" ? (
        <div className="flow-board">
          {stages.map((stage, index) => (
            <div className={`flow-column ${stage.tone}`} key={stage.key}>
              <div className="flow-column-head">
                <div>
                  <span>0{index + 1}</span>
                  <b>{stage.label}</b>
                </div>
                <strong>
                  {stage.key === "STORAGE"
                    ? d.locations.OCCUPIED || 0
                    : d.stations[stage.key] || 0}
                  <small>{stage.key === "STORAGE" ? "ตำแหน่ง" : "HU"}</small>
                </strong>
              </div>
              <p>{stage.desc}</p>
              {stage.key === "STORAGE" ? (
                <NavLink className="storage-overview" to="/warehouse-map">
                  <div className="storage-illustration">
                    {Array.from({ length: 24 }, (_, i) => (
                      <i
                        key={i}
                        className={
                          i < Math.ceil((d.utilization / 100) * 24)
                            ? "filled"
                            : ""
                        }
                      />
                    ))}
                  </div>
                  <span>
                    <b>{d.utilization}%</b> พื้นที่ใช้งาน
                  </span>
                  <small>{d.locations.AVAILABLE || 0} ตำแหน่งว่าง</small>
                </NavLink>
              ) : (
                stations
                  .filter((s) => s.station_type === stage.key)
                  .map((station) => (
                    <article className="flow-station" key={station.id}>
                      <button
                        className="flow-station-heading"
                        onClick={() => setSelected(station)}
                        aria-label={`ดูสินค้าบน ${station.station_name}`}
                      >
                        <div>
                          <i className={station.hu_count ? "busy" : ""} />
                          <b>{station.station_name}</b>
                          <span>
                            {station.hu_count}/{station.capacity_hu}
                          </span>
                        </div>
                        <small>{station.station_code}</small>
                      </button>
                      <div className="station-cargo-preview">
                        {station.items.slice(0, 3).map((item, i) => (
                          <button
                            className="card-hu-action"
                            key={`${item.hu_code}-${i}`}
                            aria-label={`ดำเนินการ ${item.hu_code}`}
                            onClick={() => setActionHU(item.hu_code)}
                          >
                            <Package size={12} />
                            {item.sku}
                            <b>{item.quantity}</b>
                          </button>
                        ))}
                        {!station.items.length && <em>พร้อมรับสินค้า</em>}
                        {station.items.length > 3 && (
                          <em>อีก {station.items.length - 3} รายการ</em>
                        )}
                      </div>
                    </article>
                  ))
              )}
              <NavLink className="flow-next" to={stage.to}>
                เปิดงาน{stage.label}
                <ArrowRight size={14} />
              </NavLink>
            </div>
          ))}
        </div>
      ) : (
        <ConveyorOverview
          onSelectHU={setActionHU}
          key={datasetRevision}
          stations={stations}
          runs={runs}
          updated={updated}
          error={stationError || runError}
          onSelectStation={setSelected}
        />
      )}
      <div
        className="command-lower"
        style={flowView === "conveyor" ? { display: "none" } : undefined}
      >
        <article className="pro-panel fleet-panel">
          <div className="panel-heading">
            <div>
              <p>FLEET & DISPATCH</p>
              <h3>รถและรอบขนส่ง</h3>
            </div>
            <NavLink to="/delivery-runs">
              ดูทุกรอบ <ArrowRight size={14} />
            </NavLink>
          </div>
          <div className="fleet-section">
            <span>
              จอดรอ / กำลังโหลด <b>{waiting.length} คัน</b>
            </span>
            {waiting.map((r) => (
              <RunCard key={r.id} run={r} />
            ))}
            {!waiting.length && (
              <div className="pro-empty compact">ไม่มีรถรอโหลดในขณะนี้</div>
            )}
          </div>
          <div className="fleet-section">
            <span>
              กำลังไปส่ง <b>{onRoute.length} คัน</b>
            </span>
            {onRoute.map((r) => (
              <RunCard key={r.id} run={r} />
            ))}
            {!onRoute.length && (
              <div className="pro-empty compact">ไม่มีรถกำลังนำส่งในขณะนี้</div>
            )}
          </div>
        </article>
        <div className="command-side">
          <article className="pro-panel return-panel">
            <div className="panel-heading">
              <div>
                <p>RETURN & EXCEPTIONS</p>
                <h3>งานคืนสินค้ารอดำเนินการ</h3>
              </div>
              <span>{d.stations.RETURN || 0} HU</span>
            </div>
            {stations
              .filter((s) => s.station_type === "RETURN")
              .flatMap((s) => s.items)
              .map((item, i) => (
                <button
                  className="return-workflow-item"
                  key={`${item.hu_code}-${i}`}
                  onClick={() => setActionHU(item.hu_code)}
                >
                  <div className="return-icon">
                    <Package size={17} />
                  </div>
                  <div>
                    <b>{item.hu_code}</b>
                    <small>
                      {item.sku} · {item.quantity} {item.unit_of_measure}
                    </small>
                  </div>
                  <ArrowRight size={16} />
                </button>
              ))}
            {!d.stations.RETURN && (
              <div className="pro-empty compact">ไม่มีสินค้าคืนรอดำเนินการ</div>
            )}
          </article>
          <article className="pro-panel">
            <div className="panel-heading">
              <div>
                <p>ACTIVITY FEED</p>
                <h3>กิจกรรมล่าสุด</h3>
              </div>
            </div>
            <div className="pro-activity">
              {d.recent.map((item) => (
                <div key={item.id}>
                  <i />
                  <div>
                    <b>{item.action.replaceAll("_", " ")}</b>
                    <small>
                      {item.username} · {item.entity} #{item.reference}
                    </small>
                  </div>
                  <time>{dateTime(item.at)}</time>
                </div>
              ))}
              {!d.recent.length && (
                <div className="pro-empty compact">ยังไม่มีกิจกรรม</div>
              )}
            </div>
          </article>
        </div>
      </div>
      {selected && (
        <div className="pro-overlay" onClick={() => setSelected(null)}>
          <div
            className="station-dialog"
            role="dialog"
            aria-modal="true"
            aria-label="สินค้าบนสถานี"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="panel-heading">
              <div>
                <p>{selected.station_code}</p>
                <h3>{selected.station_name}</h3>
              </div>
              <button
                className="pro-icon-button"
                onClick={() => setSelected(null)}
                aria-label="ปิดรายละเอียด"
              >
                <X />
              </button>
            </div>
            <p className="pro-muted">
              {selected.hu_count} HU · ความจุ {selected.capacity_hu} HU
            </p>
            {selected.items.map((item, i) => (
              <button
                className="station-detail-item"
                key={`${item.hu_code}-${i}`}
                onClick={() => {
                  setActionHU(item.hu_code);
                  setSelected(null);
                }}
              >
                <Package />
                <div>
                  <b>{item.product_name}</b>
                  <small>
                    {item.hu_code} · {item.sku}
                  </small>
                </div>
                <strong>
                  {item.quantity} {item.unit_of_measure}
                </strong>
                <ArrowRight size={16} />
              </button>
            ))}
            {!selected.items.length && (
              <div className="pro-empty">สถานีนี้ยังไม่มีสินค้า</div>
            )}
          </div>
        </div>
      )}
      {actionHU && (
        <HUActions
          code={actionHU}
          onClose={() => setActionHU("")}
          onChanged={() => {
            void reload();
            void reloadStations();
            void reloadRuns();
            setDatasetRevision((v) => v + 1);
          }}
        />
      )}
    </div>
  );
}
function RunCard({ run }: { run: DeliveryRun }) {
  const activeShipments = run.shipments.filter((s) => s.status !== "CANCELLED");
  const hu = activeShipments.reduce(
    (n, s) => n + s.items.filter((i) => i.current_status === "LOADED").length,
    0,
  );
  return (
    <NavLink className="pro-run-card" to={`/delivery-runs/${run.id}`}>
      <div className="run-truck">
        <Truck size={25} />
      </div>
      <div>
        <b>
          {run.vehicle_code} <small>{run.license_plate}</small>
        </b>
        <span>
          {run.driver_name} · {run.run_no}
        </span>
        <div className="run-cargo">
          {activeShipments.slice(0, 4).map((s) => (
            <span key={s.id}>
              <Package size={11} />
              {s.customer_name}
            </span>
          ))}
        </div>
      </div>
      <div>
        <Badge value={run.status} />
        <small>
          {activeShipments.length} รายการ · {hu} HU บนรถ
        </small>
      </div>
      <ArrowRight size={17} />
    </NavLink>
  );
}

export default function ProApp() {
  const [authenticated, setAuthenticated] = useState(
    Boolean(localStorage.getItem("warehouse_token")),
  );
  const [account, setAccount] = useState<Account | null>(null);
  const [error, setError] = useState("");
  const loadAccount = () =>
    api<Account>("/auth/me")
      .then((a) => {
        setAccount(a);
        setError("");
      })
      .catch((e) => setError(e.message));
  useEffect(() => {
    if (authenticated) void loadAccount();
  }, [authenticated]);
  async function logout() {
    try {
      await post("/auth/logout", {});
    } catch {
    } finally {
      localStorage.removeItem("warehouse_token");
      setAccount(null);
      setAuthenticated(false);
    }
  }
  if (!authenticated) return <Login onLogin={() => setAuthenticated(true)} />;
  if (!account)
    return (
      <div className="pro-loading">
        <Warehouse size={32} />
        <h2>กำลังเปิดพื้นที่ทำงาน</h2>
        <Notice error={error} />
        {error && (
          <>
            <button className="pro-primary" onClick={() => void loadAccount()}>
              ลองเชื่อมต่ออีกครั้ง
            </button>
            <button className="pro-secondary" onClick={() => void logout()}>
              กลับไปเข้าสู่ระบบ
            </button>
          </>
        )}
      </div>
    );
  return <Shell account={account} onLogout={() => void logout()} />;
}
