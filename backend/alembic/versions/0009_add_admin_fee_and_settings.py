"""Add admin_fee to invoice, create app_settings table

Revision ID: 0009
Revises: 0008
"""
from alembic import op
from sqlalchemy import inspect
import sqlalchemy as sa

revision = "0009"
down_revision = "0008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()
    insp = inspect(conn)

    # 1. Add admin_fee column to invoice table
    invoice_columns = [c["name"] for c in insp.get_columns("invoice")]
    if "admin_fee" not in invoice_columns:
        op.add_column(
            "invoice",
            sa.Column("admin_fee", sa.Numeric(10, 2), server_default="0", nullable=False),
        )

    # 2. Create app_settings table
    tables = insp.get_table_names()
    if "app_settings" not in tables:
        op.create_table(
            "app_settings",
            sa.Column("key", sa.String(100), primary_key=True),
            sa.Column("value", sa.String(500), nullable=False),
        )


def downgrade() -> None:
    op.drop_table("app_settings")
    op.drop_column("invoice", "admin_fee")
