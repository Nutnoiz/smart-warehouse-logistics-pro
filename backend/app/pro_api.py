"""Version 2 application services and operations read models."""
import csv
import io
from datetime import datetime, timezone
from decimal import Decimal
from typing import Literal
from uuid import uuid4
from fastapi import APIRouter, Depends, HTTPException, Request, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field, ConfigDict
from sqlalchemy import select, func
from sqlalchemy.orm import Session
from app import models
from app.pro_models import CycleCount
from app.core.security import hash_password, verify_password
from app.core.permissions import GRANTS
from app.core.config import settings
from app.db.session import get_db
from app.services.inventory import audit, inventory_search, record_movement

router = APIRouter(prefix='/api')

class SampleRequest(BaseModel):
    profile: Literal['single','minimal','medium','large']

@router.get('/pro/samples')
def sample_status(db:Session=Depends(get_db)):
    from app.services.samples import status
    return status(db)

@router.post('/pro/samples')
def create_samples(payload:SampleRequest,db:Session=Depends(get_db)):
    from app.services.samples import change_dataset
    return change_dataset(db,payload.profile)

@router.post('/pro/samples/clear')
def clear_samples(db:Session=Depends(get_db)):
    from app.services.samples import change_dataset
    return change_dataset(db)


class Input(BaseModel):
    model_config = ConfigDict(extra='forbid')


class UserCreate(Input):
    username: str = Field(min_length=3, max_length=60, pattern=r'^[a-zA-Z0-9_.-]+$')
    password: str = Field(min_length=12, max_length=128)
    role: Literal['ADMIN', 'MANAGER', 'OPERATOR', 'LOGISTICS', 'VIEWER']


class UserEdit(Input):
    role: Literal['ADMIN', 'MANAGER', 'OPERATOR', 'LOGISTICS', 'VIEWER']
    is_active: bool


class PasswordChange(Input):
    current_password: str
    new_password: str = Field(min_length=12, max_length=128)


class PasswordReset(Input):
    new_password: str = Field(min_length=12, max_length=128)


class CountCreate(Input):
    inventory_id: int
    counted_quantity: Decimal = Field(ge=0, max_digits=14, decimal_places=3)
    reason: str = Field(min_length=5, max_length=1000)


class CountReview(Input):
    decision: Literal['APPROVED', 'REJECTED']
    note: str = Field(min_length=3, max_length=1000)


def user_view(user):
    return {'id': user.id, 'username': user.username, 'role': user.role, 'is_active': user.is_active, 'created_at': user.created_at}


@router.get('/auth/me')
def me(request: Request, db: Session = Depends(get_db)):
    user = db.get(models.User, request.state.user_id)
    return {**user_view(user), 'permissions': sorted(GRANTS[user.role]), 'demo_mode': settings.demo_mode}


@router.post('/auth/logout')
def logout(request: Request, db: Session = Depends(get_db)):
    user = db.scalar(select(models.User).where(models.User.id == request.state.user_id).with_for_update())
    user.token_version += 1
    audit(db, 'LOGOUT', 'USER', user.id, {}); db.commit()
    return {'ok': True}


@router.post('/auth/password')
def change_password(payload: PasswordChange, request: Request, db: Session = Depends(get_db)):
    user = db.scalar(select(models.User).where(models.User.id == request.state.user_id).with_for_update())
    if not verify_password(payload.current_password, user.password_hash):
        raise HTTPException(403, 'รหัสผ่านเดิมไม่ถูกต้อง')
    user.password_hash = hash_password(payload.new_password); user.token_version += 1
    audit(db, 'PASSWORD_CHANGE', 'USER', user.id, {}); db.commit()
    return {'ok': True}


@router.get('/admin/users')
def users(db: Session = Depends(get_db)):
    return [user_view(u) for u in db.scalars(select(models.User).order_by(models.User.id))]


@router.post('/admin/users', status_code=201)
def create_user(payload: UserCreate, db: Session = Depends(get_db)):
    if db.scalar(select(models.User.id).where(func.lower(models.User.username) == payload.username.lower())):
        raise HTTPException(409, 'ชื่อผู้ใช้นี้มีแล้ว')
    user = models.User(username=payload.username, password_hash=hash_password(payload.password), role=payload.role)
    db.add(user); db.flush()
    audit(db, 'USER_CREATE', 'USER', user.id, {'username': user.username, 'role': user.role}); db.commit()
    return user_view(user)


@router.patch('/admin/users/{user_id}')
def edit_user(user_id: int, payload: UserEdit, request: Request, db: Session = Depends(get_db)):
    # Lock all administrators so simultaneous edits cannot remove the last one.
    db.scalars(select(models.User).where(models.User.role == 'ADMIN').order_by(models.User.id).with_for_update()).all()
    user = db.get(models.User, user_id)
    if not user: raise HTTPException(404, 'ไม่พบบัญชี')
    if user_id == request.state.user_id and (not payload.is_active or payload.role != 'ADMIN'):
        raise HTTPException(409, 'ไม่สามารถปิดบัญชีหรือเปลี่ยนสิทธิ์ของตนเอง')
    active_admins = db.scalar(select(func.count()).select_from(models.User).where(models.User.role == 'ADMIN', models.User.is_active.is_(True)))
    if user.role == 'ADMIN' and user.is_active and active_admins <= 1 and (payload.role != 'ADMIN' or not payload.is_active):
        raise HTTPException(409, 'ต้องมีผู้ดูแลที่ใช้งานได้อย่างน้อยหนึ่งคน')
    user.role = payload.role; user.is_active = payload.is_active; user.token_version += 1
    audit(db, 'USER_UPDATE', 'USER', user.id, {'role': user.role, 'is_active': user.is_active}); db.commit()
    return user_view(user)


@router.post('/admin/users/{user_id}/password')
def reset_password(user_id: int, payload: PasswordReset, db: Session = Depends(get_db)):
    user = db.scalar(select(models.User).where(models.User.id == user_id).with_for_update())
    if not user: raise HTTPException(404, 'ไม่พบบัญชี')
    user.password_hash = hash_password(payload.new_password); user.token_version += 1
    audit(db, 'PASSWORD_RESET', 'USER', user.id, {}); db.commit()
    return {'ok': True}


def count_view(db, count):
    inv = db.get(models.Inventory, count.inventory_id)
    hu = db.get(models.HandlingUnit, inv.handling_unit_id)
    return {'id': count.id, 'count_no': count.count_no, 'hu_code': hu.hu_code,
            'sku': db.get(models.Product, inv.product_id).sku,
            'location_code': db.get(models.Location, count.location_id).location_code,
            'expected_quantity': float(count.expected_quantity), 'counted_quantity': float(count.counted_quantity),
            'variance': float(count.counted_quantity - count.expected_quantity), 'unit': inv.unit_of_measure,
            'status': count.status, 'reason': count.reason, 'created_by': count.created_by,
            'creator': db.get(models.User, count.created_by).username, 'created_at': count.created_at,
            'review_note': count.review_note, 'reviewed_at': count.reviewed_at}

def hu_snapshot(db, hu):
    latest = db.scalar(select(func.max(models.StockMovementItem.id)).where(models.StockMovementItem.handling_unit_id == hu.id)) or 0
    return f'{hu.updated_at}|{latest}'


@router.get('/pro/counts')
def counts(db: Session = Depends(get_db)):
    return [count_view(db, c) for c in db.scalars(select(CycleCount).order_by(CycleCount.id.desc()).limit(500))]


@router.post('/pro/counts', status_code=201)
def create_count(payload: CountCreate, request: Request, db: Session = Depends(get_db)):
    inv = db.scalar(select(models.Inventory).where(models.Inventory.id == payload.inventory_id).with_for_update())
    if not inv: raise HTTPException(404, 'ไม่พบสต็อก')
    hu = db.get(models.HandlingUnit, inv.handling_unit_id)
    loc = db.get(models.Location, inv.location_id)
    if hu.current_status != 'STORED' or inv.reserved_quantity or not loc or loc.location_type != 'STORAGE':
        raise HTTPException(409, 'ตรวจนับได้เฉพาะสต็อกบนชั้นที่ยังไม่ถูกจอง')
    if db.scalar(select(CycleCount.id).where(CycleCount.inventory_id == inv.id, CycleCount.status == 'PENDING')):
        raise HTTPException(409, 'มีรายการตรวจนับรออนุมัติอยู่แล้ว')
    count = CycleCount(count_no=f'CNT-{datetime.now(timezone.utc):%Y%m%d}-{uuid4().hex[:10].upper()}',
        inventory_id=inv.id, location_id=loc.id, expected_quantity=inv.quantity,
        counted_quantity=payload.counted_quantity, inventory_snapshot=str(inv.updated_at),
        hu_snapshot=hu_snapshot(db, hu), reason=payload.reason, created_by=request.state.user_id)
    db.add(count); db.flush()
    audit(db, 'COUNT_SUBMIT', 'CYCLE_COUNT', count.id, {'expected': inv.quantity, 'counted': payload.counted_quantity}); db.commit()
    return count_view(db, count)


@router.post('/pro/counts/{count_id}/review')
def review_count(count_id: int, payload: CountReview, request: Request, db: Session = Depends(get_db)):
    count = db.scalar(select(CycleCount).where(CycleCount.id == count_id).with_for_update())
    if not count or count.status != 'PENDING': raise HTTPException(409, 'รายการนี้ไม่อยู่ในสถานะรออนุมัติ')
    if count.created_by == request.state.user_id: raise HTTPException(409, 'ผู้ตรวจนับต้องเป็นคนละคนกับผู้อนุมัติ')
    inv = db.scalar(select(models.Inventory).where(models.Inventory.id == count.inventory_id).with_for_update())
    hu = db.scalar(select(models.HandlingUnit).where(models.HandlingUnit.id == inv.handling_unit_id).with_for_update())
    if payload.decision == 'APPROVED':
        if inv.quantity != count.expected_quantity or inv.reserved_quantity or inv.location_id != count.location_id or hu.current_status != 'STORED' or str(inv.updated_at) != count.inventory_snapshot or hu_snapshot(db, hu) != count.hu_snapshot:
            raise HTTPException(409, 'สต็อกเปลี่ยนหลังตรวจนับ กรุณาปฏิเสธรายการนี้และนับใหม่')
        delta = count.counted_quantity - inv.quantity
        item = db.scalar(select(models.HandlingUnitItem).where(models.HandlingUnitItem.handling_unit_id == hu.id, models.HandlingUnitItem.product_id == inv.product_id).with_for_update())
        if not item: raise HTTPException(409, 'HU ไม่สอดคล้องกับสต็อก')
        inv.quantity = count.counted_quantity; item.quantity = count.counted_quantity
        product = db.get(models.Product, inv.product_id)
        hu.gross_weight_kg = count.counted_quantity * (product.weight_kg or 0)
        if delta:
            movement = record_movement(db, 'COUNT_ADJUST', hu, inv, source_location_id=inv.location_id, destination_location_id=inv.location_id)
            db.flush()
            line = db.scalar(select(models.StockMovementItem).where(models.StockMovementItem.movement_id == movement.id))
            line.quantity = delta
    count.status = payload.decision; count.reviewed_by = request.state.user_id
    count.review_note = payload.note; count.reviewed_at = datetime.now(timezone.utc)
    audit(db, 'COUNT_' + payload.decision, 'CYCLE_COUNT', count.id, {'variance': count.counted_quantity - count.expected_quantity, 'note': payload.note}); db.commit()
    return count_view(db, count)


@router.get('/pro/tasks')
def tasks(db: Session = Depends(get_db)):
    rows = db.scalars(select(models.WarehouseTask).order_by(models.WarehouseTask.priority, models.WarehouseTask.id.desc()).limit(500))
    result = []
    for task in rows:
        hu = db.get(models.HandlingUnit, task.handling_unit_id) if task.handling_unit_id else None
        loc = db.get(models.Location, task.source_location_id) if task.source_location_id else None
        result.append({'id': task.id, 'task_no': task.task_no, 'task_type': task.task_type, 'status': task.status,
            'priority': task.priority, 'hu_code': hu.hu_code if hu else None, 'source': loc.location_code if loc else None,
            'created_at': task.created_at, 'started_at': task.started_at, 'completed_at': task.completed_at})
    return result


@router.post('/pro/tasks/{task_id}/start')
def start_task(task_id: int, db: Session = Depends(get_db)):
    task = db.scalar(select(models.WarehouseTask).where(models.WarehouseTask.id == task_id).with_for_update())
    if not task or task.status != 'PENDING': raise HTTPException(409, 'งานนี้ไม่อยู่ในสถานะรอเริ่ม')
    task.status = 'IN_PROGRESS'; task.started_at = datetime.now(timezone.utc)
    audit(db, 'TASK_START', 'WAREHOUSE_TASK', task.id, {}); db.commit()
    return {'ok': True}


@router.get('/pro/overview')
def overview(db: Session = Depends(get_db)):
    shipment_groups = dict(db.execute(select(models.Shipment.status, func.count()).group_by(models.Shipment.status)).all())
    station_groups = dict(db.execute(select(models.Station.station_type, func.count(models.HandlingUnit.id)).join(models.Location, models.Location.station_id == models.Station.id).outerjoin(models.HandlingUnit, models.HandlingUnit.current_location_id == models.Location.id).group_by(models.Station.station_type)).all())
    statuses = dict(db.execute(select(models.Location.status, func.count()).where(models.Location.location_type == 'STORAGE').group_by(models.Location.status)).all())
    total = sum(statuses.values())
    recent = db.execute(select(models.AuditLog, models.User.username).outerjoin(models.User, models.User.id == models.AuditLog.user_id).order_by(models.AuditLog.id.desc()).limit(8)).all()
    return {'shipments': shipment_groups, 'stations': station_groups, 'locations': statuses, 'total_locations': total,
        'utilization': round(statuses.get(models.LocationStatus.OCCUPIED, 0) / total * 100, 1) if total else 0,
        'pending_counts': db.scalar(select(func.count()).select_from(CycleCount).where(CycleCount.status == 'PENDING')) or 0,
        'product_count': db.scalar(select(func.count()).select_from(models.Product)) or 0,
        'hu_count': db.scalar(select(func.count()).select_from(models.HandlingUnit)) or 0,
        'recent': [{'id': row.id, 'action': row.action, 'entity': row.entity_type, 'reference': row.entity_id, 'username': username or 'System', 'at': row.created_at} for row, username in recent]}


@router.get('/pro/reports/inventory.csv')
def inventory_csv(q: str = Query('', max_length=100), db: Session = Depends(get_db)):
    rows = inventory_search(db, q)
    output = io.StringIO(); output.write('\ufeff')
    keys = ['sku', 'product_name', 'hu_code', 'location_code', 'hu_status', 'quantity', 'reserved_quantity', 'available_quantity', 'unit_of_measure', 'lot_no', 'batch_no']
    writer = csv.DictWriter(output, fieldnames=keys, extrasaction='ignore'); writer.writeheader()
    for row in rows:
        # Neutralize spreadsheet formulas from imported master data.
        writer.writerow({k: "'" + v if isinstance(v, str) and v.startswith(('=', '+', '-', '@', '\t', '\r', '\n')) else v for k, v in row.items()})
    return StreamingResponse(iter([output.getvalue()]), media_type='text/csv; charset=utf-8', headers={'Content-Disposition': 'attachment; filename=warehouse-inventory.csv'})


@router.get('/pro/readiness')
def readiness():
    return {'version': '2.0.0-rc.1', 'environment': settings.environment, 'demo_mode': settings.demo_mode,
        'database': 'PostgreSQL' if settings.database_url.startswith('postgresql') else 'SQLite',
        'checks': [{'name': 'PostgreSQL สำหรับการใช้งานหลายคน', 'passed': settings.database_url.startswith('postgresql')},
                   {'name': 'ปิดโหมด Demo', 'passed': not settings.demo_mode},
                   {'name': 'JWT secret สำหรับ production', 'passed': len(settings.jwt_secret) >= 32 and settings.jwt_secret != 'development-only-secret'},
                   {'name': 'เปิด production configuration', 'passed': settings.environment == 'production'}]}
