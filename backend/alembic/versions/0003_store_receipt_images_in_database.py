"""store receipt images in database

Revision ID: 0003
Revises: 0002
Create Date: 2026-02-23

- Add image_data (LargeBinary) column to receipt for persistent storage
- Add content_type column to receipt
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers
revision = '0003'
down_revision = '0002'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('receipt', sa.Column('image_data', sa.LargeBinary(), nullable=True))
    op.add_column('receipt', sa.Column('content_type', sa.String(), nullable=True, server_default='image/jpeg'))


def downgrade() -> None:
    op.drop_column('receipt', 'content_type')
    op.drop_column('receipt', 'image_data')
