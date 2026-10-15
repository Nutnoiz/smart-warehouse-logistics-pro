import { useState } from "react";
import { createPortal } from "react-dom";
import { NavLink } from "react-router-dom";
import { Plus, RefreshCw, X } from "lucide-react";
import { post } from "../api";
import { useAccount } from "../ProApp";
import { useResource } from "./useResource";
import type { Product } from "../types";
import "./inbound-catalog.css";

export function InboundProductPicker({
  products,
  loading,
  error,
  value,
  onSelect,
  onReload,
  onCreated,
}: {
  products: Product[];
  loading: boolean;
  error: string;
  value: number;
  onSelect: (id: number) => void;
  onReload: () => void;
  onCreated: (product: Product) => Promise<void>;
}) {
  const account = useAccount();
  const [show, setShow] = useState(false);
  const active = products.filter((p) => p.is_active);
  return (
    <div className="inbound-product-picker">
      <label>
        <span>สินค้า</span>
        <select
          aria-label="สินค้า"
          required
          value={active.some((p) => p.id === value) ? value : ""}
          disabled={loading || !active.length}
          onChange={(e) => onSelect(+e.target.value)}
        >
          <option value="">
            {loading
              ? "กำลังโหลดสินค้า…"
              : active.length
                ? "เลือกสินค้า"
                : error
                  ? "โหลดรายการสินค้าไม่สำเร็จ"
                  : "ยังไม่มีสินค้าพร้อมรับเข้า"}
          </option>
          {active.map((p) => (
            <option value={p.id} key={p.id}>
              {p.product_name} · {p.sku}
            </option>
          ))}
        </select>
      </label>
      {error && (
        <div className="error" role="alert">
          โหลดรายการสินค้าไม่สำเร็จ: {error}
        </div>
      )}
      {!loading && !error && !active.length && (
        <div className="pro-notice info" role="status">
          {products.length
            ? "สินค้าทั้งหมดถูกปิดใช้งาน กรุณาเปิดใช้งานหรือเพิ่มสินค้าใหม่"
            : "ยังไม่มีข้อมูลสินค้าในระบบ กรุณาเพิ่มสินค้าใหม่ก่อนรับเข้า รายชื่อสินค้าจะคงอยู่แม้ล้างข้อมูลตัวอย่าง"}
        </div>
      )}
      <div className="table-actions">
        <button
          type="button"
          className="ghost"
          disabled={loading}
          onClick={onReload}
        >
          <RefreshCw size={14} /> โหลดรายการสินค้าใหม่
        </button>
        {account.permissions.includes("master") ? (
          <button type="button" className="ghost" onClick={() => setShow(true)}>
            <Plus size={14} /> เพิ่มสินค้าใหม่
          </button>
        ) : (
          <span className="helper">
            หากไม่มีสินค้า กรุณาให้ผู้ดูแลเพิ่มหรือเปิดใช้งานสินค้า
          </span>
        )}
      </div>
      {show && (
        <CreateInboundProduct
          onClose={() => setShow(false)}
          onCreated={async (p) => {
            await onCreated(p);
            setShow(false);
          }}
        />
      )}
    </div>
  );
}
type Profile = {
  id: number;
  profile_name: string;
  profile_code: string;
  size_class: string;
  is_active: boolean;
};
function CreateInboundProduct({
  onClose,
  onCreated,
}: {
  onClose: () => void;
  onCreated: (p: Product) => Promise<void>;
}) {
  const {
    data: profiles,
    loading,
    error: profileError,
    reload,
  } = useResource<Profile[]>("/storage-profiles", []);
  const [sku, setSku] = useState(""),
    [name, setName] = useState(""),
    [barcode, setBarcode] = useState(""),
    [profile, setProfile] = useState(0),
    [weight, setWeight] = useState("0"),
    [busy, setBusy] = useState(false),
    [error, setError] = useState("");
  const selected = profiles.find((p) => p.id === profile && p.is_active);
  async function submit(e: React.FormEvent) {
    e.preventDefault();
    e.stopPropagation();
    if (busy || !selected) return;
    setBusy(true);
    setError("");
    try {
      const p = await post<Product>("/products", {
        sku: sku.trim(),
        product_name: name.trim(),
        barcode: barcode.trim() || null,
        size_class: selected.size_class,
        default_storage_profile_id: selected.id,
        weight_kg: Number(weight),
      });
      await onCreated(p);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  return createPortal(
    <div
      className="pro-overlay"
      onClick={() => {
        if (!busy) onClose();
      }}
    >
      <div
        className="pro-dialog inbound-create-dialog"
        role="dialog"
        aria-modal="true"
        aria-label="เพิ่มสินค้าสำหรับรับเข้า"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="panel-heading">
          <h3>เพิ่มสินค้าสำหรับรับเข้า</h3>
          <button
            className="pro-icon-button"
            type="button"
            aria-label="ปิดเพิ่มสินค้า"
            disabled={busy}
            onClick={onClose}
          >
            <X />
          </button>
        </div>
        <p className="helper">
          บันทึกข้อมูลสินค้าและประเภทจัดเก็บก่อน
          ยังไม่เพิ่มยอดสต็อกจนกว่าจะยืนยันรับเข้า
        </p>
        <form onSubmit={submit}>
          <label>
            รหัสสินค้า SKU
            <input
              aria-label="รหัสสินค้า SKU"
              required
              maxLength={60}
              value={sku}
              onChange={(e) => setSku(e.target.value)}
            />
          </label>
          <label>
            ชื่อสินค้า
            <input
              aria-label="ชื่อสินค้าใหม่"
              required
              maxLength={160}
              value={name}
              onChange={(e) => setName(e.target.value)}
            />
          </label>
          <label>
            บาร์โค้ด (ถ้ามี)
            <input
              aria-label="บาร์โค้ดสินค้าใหม่"
              maxLength={80}
              value={barcode}
              onChange={(e) => setBarcode(e.target.value)}
            />
          </label>
          <label>
            ประเภทจัดเก็บ
            <select
              aria-label="ประเภทจัดเก็บสินค้าใหม่"
              required
              value={profile || ""}
              disabled={loading}
              onChange={(e) => setProfile(+e.target.value)}
            >
              <option value="">เลือกประเภทจัดเก็บ</option>
              {profiles
                .filter((p) => p.is_active)
                .map((p) => (
                  <option key={p.id} value={p.id}>
                    {p.size_class} · {p.profile_name} · {p.profile_code}
                  </option>
                ))}
            </select>
          </label>
          <label>
            น้ำหนักต่อหน่วย (กก.)
            <input
              aria-label="น้ำหนักสินค้าใหม่"
              type="number"
              min="0"
              step=".001"
              required
              value={weight}
              onChange={(e) => setWeight(e.target.value)}
            />
          </label>
          {profileError && (
            <div className="error" role="alert">
              {profileError}
              <button
                type="button"
                className="ghost"
                onClick={() => void reload()}
              >
                ลองโหลดประเภทจัดเก็บอีกครั้ง
              </button>
            </div>
          )}
          {!loading && !profileError && !profiles.some((p) => p.is_active) && (
            <p className="helper">
              ยังไม่มีประเภทจัดเก็บที่เปิดใช้งาน{" "}
              <NavLink to="/settings">เปิดตั้งค่าคลัง</NavLink>{" "}
              เพื่อจัดเตรียมข้อมูลก่อน
            </p>
          )}
          {error && (
            <div className="error" role="alert">
              {error}
            </div>
          )}
          <button
            className="button wide"
            disabled={busy || !sku.trim() || !name.trim() || !selected}
          >
            {busy ? "กำลังบันทึก…" : "บันทึกและเลือกสินค้านี้"}
          </button>
        </form>
      </div>
    </div>,
    document.body,
  );
}
