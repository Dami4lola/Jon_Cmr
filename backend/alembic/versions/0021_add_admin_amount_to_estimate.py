"""Add admin_amount rollup to estimate (admin fee is now charged per 7-day period)

Revision ID: 0021
Revises: 0020
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect as sa_inspect

revision = "0021"
down_revision = "0020"
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa_inspect(conn)
    columns = [c["name"] for c in inspector.get_columns("estimate")]

    if "admin_amount" not in columns:
        op.add_column(
            "estimate",
            sa.Column("admin_amount", sa.Numeric(precision=10, scale=2), nullable=False, server_default="0"),
        )


def downgrade() -> None:
    op.drop_column("estimate", "admin_amount")
