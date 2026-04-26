"""Add notes to timesheet

Revision ID: 0013
Revises: 0012
"""
from alembic import op
from sqlalchemy import inspect
import sqlalchemy as sa

revision = "0013"
down_revision = "0012"
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()
    insp = inspect(conn)
    columns = [c["name"] for c in insp.get_columns("timesheet")]

    if "notes" not in columns:
        op.add_column(
            "timesheet",
            sa.Column("notes", sa.Text(), nullable=True),
        )


def downgrade() -> None:
    op.drop_column("timesheet", "notes")
