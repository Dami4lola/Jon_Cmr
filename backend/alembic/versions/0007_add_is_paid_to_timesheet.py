"""Add is_paid to timesheet table for payroll archiving

Revision ID: 0007
Revises: 0006
"""
from alembic import op
import sqlalchemy as sa

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "timesheet",
        sa.Column("is_paid", sa.Boolean(), server_default=sa.false(), nullable=False),
    )
    op.create_index("ix_timesheet_is_paid", "timesheet", ["is_paid"])


def downgrade() -> None:
    op.drop_index("ix_timesheet_is_paid", table_name="timesheet")
    op.drop_column("timesheet", "is_paid")
