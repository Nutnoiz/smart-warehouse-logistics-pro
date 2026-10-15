"""Every mutation is explicitly classified; new routes default to administrator only."""
GRANTS = {
    "ADMIN": {"read", "master", "warehouse", "logistics", "count", "approve", "users", "audit"},
    "MANAGER": {"read", "master", "warehouse", "logistics", "count", "approve", "audit"},
    "OPERATOR": {"read", "warehouse", "count"},
    "LOGISTICS": {"read", "logistics"},
    "VIEWER": {"read"},
}


def permission_for(path: str, method: str) -> str:
    if path.startswith("/api/admin/"):
        return "users"
    if path.startswith("/api/audit"):
        return "audit"
    if method in {"GET", "HEAD"}:
        return "read"
    if path.startswith("/api/auth/"):
        return "read"
    if path.startswith("/api/pro/counts"):
        return "approve" if path.endswith("/review") else "count"
    if path.startswith("/api/pro/tasks/"):
        return "warehouse"
    if path.startswith(("/api/inbound/", "/api/putaway/", "/api/returns/", "/api/retrieval/", "/api/station-workflow/", "/api/handling-units/split")) or path == "/api/transfers":
        return "warehouse"
    if path.startswith(("/api/shipments", "/api/delivery-runs", "/api/outbound-picks")):
        return "logistics"
    if path.startswith("/api/master/") or path in {"/api/warehouses", "/api/zones", "/api/racks", "/api/storage-profiles", "/api/stations", "/api/loading-docks", "/api/products", "/api/customers", "/api/vehicles", "/api/drivers"}:
        return "master"
    return "users"
