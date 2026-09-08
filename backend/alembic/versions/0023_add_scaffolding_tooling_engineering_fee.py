"""Add estimate_scaffolding_row, estimate_tooling_row tables and
engineering_fee/scaffolding_amount/tooling_amount columns on estimate

Scaffolding is now 4 fixed component lines (frame/crosser/jack/plank), each
billed at rate_per_day x quantity x estimate.travel_days, instead of a single
generic "scaffolding" equipment row. Tooling/supplies is a new priced section
separate from materials.

Revision ID: 0023
Revises: 0022
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect as sa_inspect

revision = "0023"
down_revision = "0022"
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa_inspect(conn)

    estimate_columns = [c["name"] for c in inspector.get_columns("estimate")]
    if "engineering_fee" not in estimate_columns:
        op.add_column(
            "estimate",
            sa.Column("engineering_fee", sa.Numeric(precision=10, scale=2), nullable=False, server_default="0"),
        )
    if "scaffolding_amount" not in estimate_columns:
        op.add_column(
            "estimate",
            sa.Column("scaffolding_amount", sa.Numeric(precision=10, scale=2), nullable=False, server_default="0"),
        )
    if "tooling_amount" not in estimate_columns:
        op.add_column(
            "estimate",
            sa.Column("tooling_amount", sa.Numeric(precision=10, scale=2), nullable=False, server_default="0"),
        )

    existing_tables = inspector.get_table_names()

    if "estimate_scaffolding_row" not in existing_tables:
        op.create_table(
            "estimate_scaffolding_row",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("estimate_id", sa.Integer(), nullable=False),
            sa.Column("component", sa.String(20), nullable=False),
            sa.Column("rate_per_day", sa.Numeric(precision=10, scale=2), nullable=False, server_default="0"),
            sa.Column("quantity", sa.Numeric(precision=8, scale=2), nullable=False, server_default="0"),
            sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
            sa.ForeignKeyConstraint(["estimate_id"], ["estimate.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_estimate_scaffolding_row_estimate_id", "estimate_scaffolding_row", ["estimate_id"])

    if "estimate_tooling_row" not in existing_tables:
        op.create_table(
            "estimate_tooling_row",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("estimate_id", sa.Integer(), nullable=False),
            sa.Column("description", sa.String(500), nullable=False),
            sa.Column("quantity", sa.Numeric(precision=8, scale=2), nullable=False, server_default="1"),
            sa.Column("unit_cost", sa.Numeric(precision=10, scale=2), nullable=False, server_default="0"),
            sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
            sa.ForeignKeyConstraint(["estimate_id"], ["estimate.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_estimate_tooling_row_estimate_id", "estimate_tooling_row", ["estimate_id"])


def downgrade() -> None:
    op.drop_table("estimate_tooling_row")
    op.drop_table("estimate_scaffolding_row")
    op.drop_column("estimate", "tooling_amount")
    op.drop_column("estimate", "scaffolding_amount")
    op.drop_column("estimate", "engineering_fee")
