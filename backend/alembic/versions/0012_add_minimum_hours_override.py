"""Add minimum_hours_override to timesheet

Revision ID: 0012
Revises: 0011
"""
from alembic import op
from sqlalchemy import inspect
import sqlalchemy as sa

revision = "0012"
down_revision = "0011"
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()
    insp = inspect(conn)
    columns = [c["name"] for c in insp.get_columns("timesheet")]

    if "minimum_hours_override" not in columns:
        op.add_column(
            "timesheet",
            sa.Column("minimum_hours_override", sa.Numeric(4, 2), nullable=True),
        )


def downgrade() -> None:
    op.drop_column("timesheet", "minimum_hours_override")
