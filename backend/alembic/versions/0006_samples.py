"""Tracked, replaceable home-improvement sample datasets."""
from alembic import op
import sqlalchemy as sa
revision='0006'
down_revision='0005'
branch_labels=None
depends_on=None

def upgrade():
    op.create_table('sample_sets',sa.Column('id',sa.Integer(),primary_key=True),sa.Column('profile',sa.String(20)),sa.Column('manifest',sa.Text(),nullable=False,server_default='{}'),sa.Column('updated_at',sa.DateTime(timezone=True),nullable=False,server_default=sa.func.now()))
    op.execute("INSERT INTO sample_sets (id, manifest) VALUES (1, '{}')")

def downgrade():
    op.drop_table('sample_sets')
