from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from pathlib import Path
from fastapi.middleware.cors import CORSMiddleware
from app.api import router
from app.pro_api import router as pro_router
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from uuid import uuid4
from app.db.session import SessionLocal
from app.models import User
from app.core.permissions import GRANTS, permission_for
from app.core.config import settings
from app.core.security import decode_claims

app = FastAPI(title="Smart Warehouse Pro API", version="2.0.0-rc.1")
upload_dir=Path("uploads");upload_dir.mkdir(exist_ok=True)
app.mount("/files",StaticFiles(directory=upload_dir),name="files")
app.add_middleware(CORSMiddleware, allow_origins=settings.cors_origins.split(","), allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

@app.middleware("http")
async def require_auth(request: Request, call_next):
    path = request.url.path
    request_id = uuid4().hex
    public = request.method == "OPTIONS" or path in {"/api/health", "/api/auth/login"}
    if (path.startswith("/api/") or path.startswith("/files/")) and not public:
        header = request.headers.get("Authorization", "")
        token = header.removeprefix("Bearer ").strip() if header.startswith("Bearer ") else ""
        if not token and path.startswith('/files/'):
            token = request.cookies.get('warehouse_evidence', '')
        claims = decode_claims(token)
        if not claims:
            return JSONResponse({"detail": "Authentication required"}, status_code=401)
        with SessionLocal() as db:
            user = db.scalar(select(User).where(User.username == claims['sub']))
            if not user or not user.is_active or user.token_version != claims.get('ver'):
                return JSONResponse({'detail': 'บัญชีหรือเซสชันหมดอายุ กรุณาเข้าสู่ระบบใหม่'}, status_code=401)
            if permission_for(path, request.method) not in GRANTS.get(user.role, set()):
                return JSONResponse({'detail': 'บัญชีนี้ไม่มีสิทธิ์ทำรายการ'}, status_code=403)
            request.state.username = user.username
            request.state.user_id = user.id
            request.state.role = user.role
    response = await call_next(request)
    response.headers['X-Request-ID'] = request_id
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['Referrer-Policy'] = 'same-origin'
    response.headers['Cache-Control'] = 'no-store'
    return response

@app.exception_handler(IntegrityError)
async def integrity_error(request, exc):
    return JSONResponse({'detail': 'รายการซ้ำหรือข้อมูลอ้างอิงไม่ถูกต้อง กรุณาตรวจสอบแล้วลองใหม่'}, status_code=409)

app.include_router(pro_router)
app.include_router(router)
