"""create inspection tables

Revision ID: 0001
Revises:
Create Date: 2026-02-08

Drops and recreates job_inspection and inspection_photo tables
with the correct schema. Safe to run since tables are empty.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0001'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Skip if tables already exist (prevent data loss on re-run)
    from sqlalchemy import inspect as sa_inspect
    inspector = sa_inspect(op.get_bind())
    if 'job_inspection' in inspector.get_table_names():
        return

    op.create_table(
        'job_inspection',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('job_id', sa.Integer(), nullable=False),
        sa.Column('type', sa.String(length=4), nullable=False),
        sa.Column('date', sa.Date(), nullable=False),
        sa.Column('customer_name', sa.String(), nullable=False),
        sa.Column('is_company_truck_required', sa.Boolean(), nullable=False),
        sa.Column('materials_needed', sa.String(), nullable=True),
        sa.Column('special_tools_needed', sa.String(), nullable=True),
        sa.Column('existing_damage_notes', sa.String(), nullable=True),
        sa.Column('flooring_protection_needed', sa.String(), nullable=True),
        sa.Column('dump_run_required', sa.Boolean(), nullable=True),
        sa.Column('customer_keeping_materials', sa.String(), nullable=True),
        sa.Column('materials_to_return', sa.String(), nullable=True),
        sa.Column('inventory_used', sa.String(), nullable=True),
        sa.Column('pickup_required', sa.String(), nullable=True),
        sa.Column('damages_or_quality_concerns', sa.String(), nullable=True),
        sa.Column('scope_change_notes', sa.String(), nullable=True),
        sa.ForeignKeyConstraint(['job_id'], ['job.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_job_inspection_job_id'), 'job_inspection', ['job_id'], unique=False)

    op.create_table(
        'inspection_photo',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('inspection_id', sa.Integer(), nullable=False),
        sa.Column('image_path', sa.String(), nullable=False),
        sa.Column('caption', sa.String(length=200), nullable=True),
        sa.Column('uploaded_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['inspection_id'], ['job_inspection.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_inspection_photo_inspection_id'), 'inspection_photo', ['inspection_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_inspection_photo_inspection_id'), table_name='inspection_photo')
    op.drop_table('inspection_photo')
    op.drop_index(op.f('ix_job_inspection_job_id'), table_name='job_inspection')
    op.drop_table('job_inspection')
