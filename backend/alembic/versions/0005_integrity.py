"""Inventory and exclusive custody database constraints."""
from alembic import op
import sqlalchemy as sa

revision='0005'
down_revision='0004'
branch_labels=None
depends_on=None


def upgrade():
    for table,name,expression in [('inventory','ck_inventory_quantities','quantity >= 0 AND reserved_quantity >= 0 AND reserved_quantity <= quantity'),('handling_units','ck_hu_exclusive_custody','current_location_id IS NULL OR current_vehicle_id IS NULL')]:
        existing={c['name'] for c in sa.inspect(op.get_bind()).get_check_constraints(table)}
        if name not in existing:
            with op.batch_alter_table(table) as batch:
                batch.create_check_constraint(name,expression)


def downgrade():
    with op.batch_alter_table('inventory') as batch:batch.drop_constraint('ck_inventory_quantities',type_='check')
    with op.batch_alter_table('handling_units') as batch:batch.drop_constraint('ck_hu_exclusive_custody',type_='check')
