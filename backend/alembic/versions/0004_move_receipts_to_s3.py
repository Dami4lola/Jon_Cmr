"""move receipt images to S3

Revision ID: 0004
Revises: 0003
Create Date: 2026-02-23

- Add public_url column to receipt (S3 URL)
- Drop image_data column (was storing blobs in PostgreSQL)
- Drop image_path column (legacy filesystem path)
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers
revision = '0004'
down_revision = '0003'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('receipt', sa.Column('public_url', sa.String(), nullable=True, server_default=''))
    op.drop_column('receipt', 'image_data')
    op.drop_column('receipt', 'image_path')


def downgrade() -> None:
    op.add_column('receipt', sa.Column('image_path', sa.String(), nullable=True, server_default=''))
    op.add_column('receipt', sa.Column('image_data', sa.LargeBinary(), nullable=True))
    op.drop_column('receipt', 'public_url')
