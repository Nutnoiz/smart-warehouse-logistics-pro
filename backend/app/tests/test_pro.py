import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from app.main import app
from app.models import User, Inventory, AuditLog, StockMovement
from app.db.session import SessionLocal
from app.core.security import hash_password, create_access_token
from app.tests.test_end_to_end import setup_flow


def user_client(role, name):
    with SessionLocal() as db:
        db.add(User(username=name, password_hash=hash_password('password-123456'), role=role)); db.commit()
    return TestClient(app, headers={'Authorization': f'Bearer {create_access_token(name)}'})


def test_viewer_is_read_only_and_cannot_manage_users(client):
    viewer = user_client('VIEWER', 'observer')
    assert viewer.get('/api/pro/overview').status_code == 200
    assert viewer.post('/api/warehouses', json={'warehouse_code':'BAD','warehouse_name':'No'}).status_code == 403
    assert viewer.get('/api/admin/users').status_code == 403
    assert viewer.get('/api/audit-logs').status_code == 403


def test_disabled_user_and_logout_invalidate_tokens(client):
    operator = user_client('OPERATOR', 'staff')
    assert operator.get('/api/auth/me').status_code == 200
    assert operator.post('/api/auth/logout').status_code == 200
    assert operator.get('/api/auth/me').status_code == 401
    with SessionLocal() as db:
        user=db.scalar(select(User).where(User.username=='staff'));user.is_active=False;db.commit()
    assert operator.get('/api/auth/me').status_code == 401


def test_unknown_signed_subject_is_rejected():
    c=TestClient(app,headers={'Authorization':f'Bearer {create_access_token("ghost")}'})
    assert c.get('/api/dashboard').status_code == 401


def test_password_change_revokes_session(client):
    viewer=user_client('VIEWER','observer')
    assert viewer.post('/api/auth/password',json={'current_password':'wrong','new_password':'new-password-12345'}).status_code==403
    assert viewer.post('/api/auth/password',json={'current_password':'password-123456','new_password':'new-password-12345'}).status_code==200
    assert viewer.get('/api/auth/me').status_code==401


def test_login_lockout(client):
    c=TestClient(app)
    for _ in range(8): assert c.post('/api/auth/login',json={'username':'missing','password':'wrong'}).status_code==401
    assert c.post('/api/auth/login',json={'username':'missing','password':'wrong'}).status_code==429


def test_count_requires_separate_approval_and_is_atomic(client):
    setup_flow(client)
    operator=user_client('OPERATOR','counter'); manager=user_client('MANAGER','supervisor')
    inv=client.get('/api/inventory/search').json()[0]
    submitted=operator.post('/api/pro/counts',json={'inventory_id':inv['id'],'counted_quantity':98,'reason':'Monthly cycle count'})
    assert submitted.status_code==201
    cid=submitted.json()['id']
    assert client.get('/api/inventory/search').json()[0]['quantity']==100
    assert operator.post(f'/api/pro/counts/{cid}/review',json={'decision':'APPROVED','note':'Checked'}).status_code==403
    assert manager.post(f'/api/pro/counts/{cid}/review',json={'decision':'APPROVED','note':'Verified independently'}).status_code==200
    assert client.get('/api/inventory/search').json()[0]['quantity']==98
    assert manager.post(f'/api/pro/counts/{cid}/review',json={'decision':'APPROVED','note':'Duplicate'}).status_code==409
    with SessionLocal() as db:
        assert db.scalar(select(StockMovement).where(StockMovement.movement_type=='COUNT_ADJUST'))
        assert db.scalar(select(AuditLog).where(AuditLog.action=='COUNT_APPROVED')).user_id is not None


def test_count_rejects_stale_inventory_and_duplicate_pending(client):
    setup_flow(client); manager=user_client('MANAGER','reviewer')
    inv=client.get('/api/inventory/search').json()[0]
    payload={'inventory_id':inv['id'],'counted_quantity':99,'reason':'Stock inspection'}
    cid=client.post('/api/pro/counts',json=payload).json()['id']
    assert client.post('/api/pro/counts',json=payload).status_code==409
    assert client.post(f'/api/pro/counts/{cid}/review',json={'decision':'APPROVED','note':'Self review'}).status_code==409
    with SessionLocal() as db:
        row=db.get(Inventory,inv['id']);row.reserved_quantity=100;db.commit()
    assert manager.post(f'/api/pro/counts/{cid}/review',json={'decision':'APPROVED','note':'stale'}).status_code==409
    assert manager.post(f'/api/pro/counts/{cid}/review',json={'decision':'REJECTED','note':'Count again'}).status_code==200


def test_csv_export_escapes_formulas(client):
    setup_flow(client)
    from app.models import Product
    with SessionLocal() as db:
        p=db.scalar(select(Product));p.product_name='=HYPERLINK("malicious")';db.commit()
    result=client.get('/api/pro/reports/inventory.csv')
    assert result.status_code==200
    assert "'=HYPERLINK" in result.text


def test_users_exclude_hash_and_cannot_disable_self(client):
    result=client.post('/api/admin/users',json={'username':'warehouse-team','password':'password-123456','role':'OPERATOR'})
    assert result.status_code==201
    assert 'password_hash' not in result.json()
    assert client.post('/api/admin/users',json={'username':'warehouse-team','password':'password-123456','role':'OPERATOR'}).status_code==409
    uid=client.get('/api/auth/me').json()['id']
    assert client.patch(f'/api/admin/users/{uid}',json={'role':'ADMIN','is_active':False}).status_code==409


def test_pod_files_require_authentication():
    assert TestClient(app).get('/files/not-a-file.png').status_code==401


def test_reserved_goods_cannot_be_transferred(client):
    setup_flow(client)
    inv=client.get('/api/inventory/search').json()[0]
    dest=next(x for x in client.get('/api/locations?location_type=STORAGE').json() if x['status']=='AVAILABLE' and '-L-' in x['location_code'])
    with SessionLocal() as db:
        row=db.get(Inventory,inv['id']);row.reserved_quantity=100;db.commit()
    assert client.post('/api/transfers',json={'hu_code':inv['hu_code'],'destination_location_id':dest['id']}).status_code==409


def test_inventory_database_rejects_negative_or_overreserved_quantities(client):
    from sqlalchemy.exc import IntegrityError
    setup_flow(client)
    with SessionLocal() as db:
        row=db.scalar(select(Inventory));row.quantity=-1
        with pytest.raises(IntegrityError):db.commit()
        db.rollback()
        row=db.scalar(select(Inventory));row.reserved_quantity=101
        with pytest.raises(IntegrityError):db.commit()


def test_return_hold_is_not_allocatable(client):
    from app.models import HandlingUnit
    data=setup_flow(client)
    with SessionLocal() as db:
        hu=db.scalar(select(HandlingUnit).where(HandlingUnit.hu_code==data['hu']));hu.current_status='RETURN_HOLD';db.commit()
    assert client.post(f"/api/shipments/{data['shipment']['id']}/allocate").status_code==409


def test_fefo_selects_earliest_expiry_from_eligible_stored_units(client):
    from datetime import date
    from app.models import HandlingUnitItem
    data=setup_flow(client)
    product_id=data['shipment']['items'][0]['product_id']
    inbound=next(s for s in client.get('/api/stations').json() if s['station_type']=='INBOUND')
    assert client.post('/api/inbound/receive',json={'product_id':product_id,'hu_code':'HU-EXPIRING','quantity':100,'station_id':inbound['id']}).status_code==201
    option=client.post('/api/putaway/options',json={'hu_code':'HU-EXPIRING'}).json()[0]
    assert client.post('/api/putaway/confirm',json={'hu_code':'HU-EXPIRING','destination_location_id':option['id']}).status_code==200
    with SessionLocal() as db:
        items=db.scalars(select(HandlingUnitItem).order_by(HandlingUnitItem.id)).all()
        items[0].expiry_date=date(2030,1,1);items[1].expiry_date=date(2027,1,1);db.commit()
    allocated=client.post(f"/api/shipments/{data['shipment']['id']}/allocate?strategy=FEFO")
    assert allocated.status_code==200
    assert allocated.json()['items'][0]['hu_code']=='HU-EXPIRING'
