"""inventory and logistics domains

Revision ID: 0002
Revises: 0001
"""
from alembic import op
from app.db.base import Base
from app import models  # noqa: F401

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None

def upgrade() -> None:
    excluded = {'delivery_runs', 'delivery_run_shipments', 'delivery_run_events', 'cycle_counts', 'login_attempts', 'sample_sets'}
    Base.metadata.create_all(bind=op.get_bind(), tables=[t for t in Base.metadata.sorted_tables if t.name not in excluded])

def downgrade() -> None:
    for table in reversed(Base.metadata.sorted_tables):
        if table.name not in {"warehouses","storage_profiles","zones","racks","stations","locations","loading_docks","users"}:
            table.drop(bind=op.get_bind(), checkfirst=True)
