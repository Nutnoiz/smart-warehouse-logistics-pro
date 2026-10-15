"""warehouse master foundation

Revision ID: 0001
Revises:
"""
from alembic import op
from app.db.base import Base
from app import models  # noqa: F401

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None

def upgrade() -> None:
    names = {'warehouses', 'storage_profiles', 'zones', 'racks', 'stations', 'locations', 'loading_docks', 'users'}
    Base.metadata.create_all(bind=op.get_bind(), tables=[t for t in Base.metadata.sorted_tables if t.name in names])

def downgrade() -> None:
    names = {'warehouses', 'storage_profiles', 'zones', 'racks', 'stations', 'locations', 'loading_docks', 'users'}
    Base.metadata.drop_all(bind=op.get_bind(), tables=[t for t in Base.metadata.sorted_tables if t.name in names])

