import { describe, it, expect } from "vitest";
import { matchesShipment, type ShipmentFilters } from "./ShipmentList";
import type { Shipment } from "../types";
const base: ShipmentFilters = {
  q: "",
  status: "ALL",
  vehicle: "ALL",
  run: "ALL",
  customer: "ALL",
};
const row = {
  id: 1,
  shipment_no: "SHP-001",
  status: "LOADING",
  customer_name: "บ้านตัวอย่าง",
  destination_name: "บ้านตัวอย่าง",
  destination_address: "กรุงเทพมหานคร",
  vehicle_code: "รถขนส่ง 05",
  delivery_run_id: 9,
  delivery_run_no: "RUN-009",
  driver_name: "สมชาย",
  items: [{ sku: "HOME-LAMP", hu_code: "HU-ABC" }],
} as Shipment;
describe("shipment filters", () => {
  it("shows all by default", () =>
    expect(matchesShipment(row, base)).toBe(true));
  it("filters exact status and open group", () => {
    expect(matchesShipment(row, { ...base, status: "LOADING" })).toBe(true);
    expect(matchesShipment(row, { ...base, status: "DELIVERED" })).toBe(false);
    for (const status of ["DELIVERED", "RETURNED", "CANCELLED"])
      expect(
        matchesShipment({ ...row, status }, { ...base, status: "ACTIVE" }),
      ).toBe(false);
  });
  it("filters vehicle and unassigned", () => {
    expect(matchesShipment(row, { ...base, vehicle: "รถขนส่ง 05" })).toBe(true);
    expect(matchesShipment(row, { ...base, vehicle: "UNASSIGNED" })).toBe(
      false,
    );
    expect(
      matchesShipment(
        { ...row, vehicle_code: undefined },
        { ...base, vehicle: "UNASSIGNED" },
      ),
    ).toBe(true);
  });
  it("distinguishes rounds and no round", () => {
    expect(matchesShipment(row, { ...base, run: "9" })).toBe(true);
    expect(matchesShipment(row, { ...base, run: "8" })).toBe(false);
    expect(
      matchesShipment(
        { ...row, delivery_run_id: undefined },
        { ...base, run: "UNASSIGNED" },
      ),
    ).toBe(true);
  });
  it("searches trimmed case-insensitive HU SKU customer round and driver", () => {
    for (const q of [
      " hu-abc ",
      "home-lamp",
      "บ้านตัวอย่าง",
      "run-009",
      "สมชาย",
    ])
      expect(matchesShipment(row, { ...base, q })).toBe(true);
    expect(matchesShipment(row, { ...base, q: "ไม่มีสินค้านี้" })).toBe(false);
  });
  it("combines all selected criteria", () => {
    const f = {
      ...base,
      status: "LOADING",
      vehicle: "รถขนส่ง 05",
      run: "9",
      customer: "บ้านตัวอย่าง",
      q: "lamp",
    };
    expect(matchesShipment(row, f)).toBe(true);
    expect(matchesShipment(row, { ...f, customer: "อีกลูกค้า" })).toBe(false);
  });
});
