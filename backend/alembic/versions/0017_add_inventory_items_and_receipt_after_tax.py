"""Add inventory items table and receipt amount_after_tax

Revision ID: 0017
Revises: 0016
"""
from alembic import op
import sqlalchemy as sa

revision = "0017"
down_revision = "0016"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "receipt",
        sa.Column("amount_after_tax", sa.Numeric(precision=8, scale=2), nullable=True),
    )

    op.create_table(
        "timesheet_inventory_item",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("timesheet_id", sa.Integer(), nullable=False),
        sa.Column("description", sa.String(500), nullable=False),
        sa.Column("quantity", sa.String(100), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["timesheet_id"], ["timesheet.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_timesheet_inventory_item_timesheet_id",
        "timesheet_inventory_item",
        ["timesheet_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_timesheet_inventory_item_timesheet_id", table_name="timesheet_inventory_item")
    op.drop_table("timesheet_inventory_item")
    op.drop_column("receipt", "amount_after_tax")
