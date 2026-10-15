"""delivery runs and vehicle trip control

Revision ID: 0003
Revises: 0002
"""
from alembic import op
import sqlalchemy as sa

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.create_table(
        "delivery_runs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("run_no", sa.String(60), nullable=False),
        sa.Column("origin_warehouse_id", sa.Integer(), sa.ForeignKey("warehouses.id"), nullable=False),
        sa.Column("vehicle_id", sa.Integer(), sa.ForeignKey("vehicles.id"), nullable=False),
        sa.Column("driver_id", sa.Integer(), sa.ForeignKey("drivers.id"), nullable=False),
        sa.Column("loading_dock_id", sa.Integer(), sa.ForeignKey("loading_docks.id"), nullable=True),
        sa.Column("status", sa.String(30), nullable=False, server_default="PLANNED"),
        sa.Column("planned_departure_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("truck_arrived_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("dock_entered_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("loading_started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ready_to_depart_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("actual_departure_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("run_no"),
    )
    op.create_index("ix_delivery_runs_run_no", "delivery_runs", ["run_no"], unique=True)
    op.create_index("ix_delivery_runs_vehicle_id", "delivery_runs", ["vehicle_id"])
    op.create_index("ix_delivery_runs_driver_id", "delivery_runs", ["driver_id"])
    op.create_index("ix_delivery_runs_loading_dock_id", "delivery_runs", ["loading_dock_id"])
    op.create_index("ix_delivery_runs_status", "delivery_runs", ["status"])
    op.create_table(
        "delivery_run_shipments",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("delivery_run_id", sa.Integer(), sa.ForeignKey("delivery_runs.id"), nullable=False),
        sa.Column("shipment_id", sa.Integer(), sa.ForeignKey("shipments.id"), nullable=False),
        sa.Column("stop_sequence", sa.Integer(), nullable=False, server_default="1"),
        sa.UniqueConstraint("shipment_id"),
        sa.UniqueConstraint("delivery_run_id", "stop_sequence"),
    )
    op.create_index("ix_delivery_run_shipments_delivery_run_id", "delivery_run_shipments", ["delivery_run_id"])
    op.create_index("ix_delivery_run_shipments_shipment_id", "delivery_run_shipments", ["shipment_id"])
    op.create_table(
        "delivery_run_events",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("delivery_run_id", sa.Integer(), sa.ForeignKey("delivery_runs.id"), nullable=False),
        sa.Column("event_type", sa.String(30), nullable=False),
        sa.Column("event_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("latitude", sa.Numeric(10, 7), nullable=True),
        sa.Column("longitude", sa.Numeric(10, 7), nullable=True),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_delivery_run_events_delivery_run_id", "delivery_run_events", ["delivery_run_id"])
    op.create_index("ix_delivery_run_events_event_type", "delivery_run_events", ["event_type"])

def downgrade() -> None:
    op.drop_table("delivery_run_events")
    op.drop_table("delivery_run_shipments")
    op.drop_table("delivery_runs")
