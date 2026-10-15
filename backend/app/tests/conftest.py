import os
os.environ["DATABASE_URL"] = "sqlite:///./test_warehouse.db"
import pytest
from fastapi.testclient import TestClient
from app.db.base import Base
from app.db.session import engine
from app.main import app
from app.core.security import create_access_token

@pytest.fixture(autouse=True)
def database():
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    from app.models import User
    from app.db.session import SessionLocal
    from app.core.security import hash_password
    with SessionLocal() as db:
        db.add(User(username='test-admin', password_hash=hash_password('test-password-123'), role='ADMIN'))
        db.commit()
    yield
    Base.metadata.drop_all(engine)

@pytest.fixture
def client():
    return TestClient(app, headers={"Authorization": f"Bearer {create_access_token('test-admin')}"})
