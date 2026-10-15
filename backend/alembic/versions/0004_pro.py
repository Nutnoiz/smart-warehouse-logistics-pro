"""Pro security and approved inventory counting."""
from alembic import op
import sqlalchemy as sa

revision = '0004'
down_revision = '0003'
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    if 'token_version' not in {c['name'] for c in sa.inspect(bind).get_columns('users')}:
        op.add_column('users', sa.Column('token_version', sa.Integer(), nullable=False, server_default='0'))
    op.create_table('login_attempts',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('username', sa.String(60), nullable=False),
        sa.Column('occurred_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()))
    op.create_index('ix_login_attempts_username', 'login_attempts', ['username'])
    op.create_table('cycle_counts',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('count_no', sa.String(60), nullable=False, unique=True),
        sa.Column('inventory_id', sa.Integer(), sa.ForeignKey('inventory.id'), nullable=False),
        sa.Column('location_id', sa.Integer(), sa.ForeignKey('locations.id'), nullable=False),
        sa.Column('expected_quantity', sa.Numeric(14, 3), nullable=False),
        sa.Column('counted_quantity', sa.Numeric(14, 3), nullable=False),
        sa.Column('inventory_snapshot', sa.String(80), nullable=False),
        sa.Column('hu_snapshot', sa.String(80), nullable=False),
        sa.Column('reason', sa.Text(), nullable=False),
        sa.Column('status', sa.String(24), nullable=False),
        sa.Column('created_by', sa.Integer(), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('reviewed_by', sa.Integer(), sa.ForeignKey('users.id')),
        sa.Column('review_note', sa.Text()),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('reviewed_at', sa.DateTime(timezone=True)),
        sa.CheckConstraint('counted_quantity >= 0', name='ck_count_nonnegative'))


def downgrade():
    op.drop_table('cycle_counts')
    op.drop_table('login_attempts')
    op.drop_column('users', 'token_version')
