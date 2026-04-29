"""Add km_rate to invoice

Revision ID: 0016
Revises: 0015
"""
from alembic import op
import sqlalchemy as sa

revision = "0016"
down_revision = "0015"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "invoice",
        sa.Column("km_rate", sa.Numeric(precision=5, scale=2), nullable=False, server_default="1.50"),
    )


def downgrade() -> None:
    op.drop_column("invoice", "km_rate")
