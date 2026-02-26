"""Add is_redseal_trade to job table

Revision ID: 0006
Revises: 0005
"""
from alembic import op
import sqlalchemy as sa

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("job", sa.Column("is_redseal_trade", sa.Boolean(), server_default="false", nullable=False))


def downgrade() -> None:
    op.drop_column("job", "is_redseal_trade")
