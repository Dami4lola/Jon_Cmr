"""Add invoice charge breakdown fields

Revision ID: 0005
Revises: 0004
"""
from alembic import op
import sqlalchemy as sa

revision = '0005'
down_revision = '0004'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('invoice', sa.Column('labour_amount', sa.Numeric(10, 2), server_default='0', nullable=False))
    op.add_column('invoice', sa.Column('travel_amount', sa.Numeric(10, 2), server_default='0', nullable=False))
    op.add_column('invoice', sa.Column('materials_amount', sa.Numeric(10, 2), server_default='0', nullable=False))
    op.add_column('invoice', sa.Column('inventory_materials', sa.Numeric(10, 2), server_default='0', nullable=False))
    op.add_column('invoice', sa.Column('dump_fee', sa.Numeric(10, 2), server_default='0', nullable=False))
    op.add_column('invoice', sa.Column('total_labour_hours', sa.Numeric(8, 2), server_default='0', nullable=False))
    op.add_column('invoice', sa.Column('total_distance_km', sa.Numeric(6, 2), server_default='0', nullable=False))
    op.add_column('invoice', sa.Column('scope_of_work', sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column('invoice', 'scope_of_work')
    op.drop_column('invoice', 'total_distance_km')
    op.drop_column('invoice', 'total_labour_hours')
    op.drop_column('invoice', 'dump_fee')
    op.drop_column('invoice', 'inventory_materials')
    op.drop_column('invoice', 'materials_amount')
    op.drop_column('invoice', 'travel_amount')
    op.drop_column('invoice', 'labour_amount')
