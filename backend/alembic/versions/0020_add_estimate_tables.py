"""Add estimate, estimate_task, estimate_equipment_row, estimate_material_row tables

Revision ID: 0020
Revises: 0019
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect as sa_inspect

revision = "0020"
down_revision = "0019"
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa_inspect(conn)
    existing_tables = inspector.get_table_names()

    if "estimate" not in existing_tables:
        op.create_table(
            "estimate",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("job_id", sa.Integer(), nullable=True),
            sa.Column("client_id", sa.Integer(), nullable=True),
            sa.Column("client_name_override", sa.String(100), nullable=True),
            sa.Column("address_override", sa.String(), nullable=True),
            sa.Column("estimate_number", sa.String(20), nullable=False),
            sa.Column("created_date", sa.Date(), nullable=False, server_default=sa.func.current_date()),
            sa.Column("scope_of_work", sa.String(), nullable=True),
            sa.Column("notes", sa.String(), nullable=True),
            sa.Column("crew_size", sa.Integer(), nullable=False, server_default="1"),
            sa.Column("techs_traveling", sa.Integer(), nullable=False, server_default="1"),
            sa.Column("distance_km", sa.Numeric(precision=6, scale=2), nullable=True),
            sa.Column("km_rate", sa.Numeric(precision=5, scale=2), nullable=False, server_default="1.50"),
            sa.Column("dump_fee", sa.Numeric(precision=10, scale=2), nullable=False, server_default="0"),
            sa.Column("permits_fee", sa.Numeric(precision=10, scale=2), nullable=False, server_default="0"),
            sa.Column("admin_fee", sa.Numeric(precision=10, scale=2), nullable=False, server_default="0"),
            sa.Column("redseal_amount", sa.Numeric(precision=10, scale=2), nullable=False, server_default="0"),
            sa.Column("include_admin_fee", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column("include_hst", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column("total_hours", sa.Numeric(precision=8, scale=2), nullable=False, server_default="0"),
            sa.Column("travel_days", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("labour_amount", sa.Numeric(precision=10, scale=2), nullable=False, server_default="0"),
            sa.Column("travel_amount", sa.Numeric(precision=10, scale=2), nullable=False, server_default="0"),
            sa.Column("materials_amount", sa.Numeric(precision=10, scale=2), nullable=False, server_default="0"),
            sa.Column("heavy_equipment_amount", sa.Numeric(precision=10, scale=2), nullable=False, server_default="0"),
            sa.Column("rental_amount", sa.Numeric(precision=10, scale=2), nullable=False, server_default="0"),
            sa.Column("fuel_amount", sa.Numeric(precision=10, scale=2), nullable=False, server_default="0"),
            sa.Column("subtotal", sa.Numeric(precision=10, scale=2), nullable=False, server_default="0"),
            sa.Column("hst_amount", sa.Numeric(precision=10, scale=2), nullable=False, server_default="0"),
            sa.Column("total", sa.Numeric(precision=10, scale=2), nullable=False, server_default="0"),
            sa.Column("status", sa.String(10), nullable=False, server_default="draft"),
            sa.ForeignKeyConstraint(["job_id"], ["job.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["client_id"], ["client.id"]),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_estimate_job_id", "estimate", ["job_id"], unique=True)
        op.create_index("ix_estimate_client_id", "estimate", ["client_id"])
        op.create_index("ix_estimate_estimate_number", "estimate", ["estimate_number"], unique=True)

    if "estimate_task" not in existing_tables:
        op.create_table(
            "estimate_task",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("estimate_id", sa.Integer(), nullable=False),
            sa.Column("phase", sa.String(20), nullable=False),
            sa.Column("description", sa.String(500), nullable=False),
            sa.Column("hours", sa.Numeric(precision=6, scale=2), nullable=False),
            sa.Column("uses_heavy_equipment", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
            sa.ForeignKeyConstraint(["estimate_id"], ["estimate.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_estimate_task_estimate_id", "estimate_task", ["estimate_id"])

    if "estimate_equipment_row" not in existing_tables:
        op.create_table(
            "estimate_equipment_row",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("estimate_id", sa.Integer(), nullable=False),
            sa.Column("category", sa.String(20), nullable=False),
            sa.Column("description", sa.String(500), nullable=False),
            sa.Column("rate", sa.Numeric(precision=10, scale=2), nullable=False, server_default="0"),
            sa.Column("unit", sa.String(50), nullable=False, server_default=""),
            sa.Column("quantity", sa.Numeric(precision=8, scale=2), nullable=False, server_default="1"),
            sa.Column("markup_pct", sa.Numeric(precision=5, scale=2), nullable=False, server_default="0"),
            sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
            sa.ForeignKeyConstraint(["estimate_id"], ["estimate.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_estimate_equipment_row_estimate_id", "estimate_equipment_row", ["estimate_id"])

    if "estimate_material_row" not in existing_tables:
        op.create_table(
            "estimate_material_row",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("estimate_id", sa.Integer(), nullable=False),
            sa.Column("description", sa.String(500), nullable=False),
            sa.Column("quantity", sa.Numeric(precision=8, scale=2), nullable=False, server_default="1"),
            sa.Column("unit_cost", sa.Numeric(precision=10, scale=2), nullable=False, server_default="0"),
            sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
            sa.ForeignKeyConstraint(["estimate_id"], ["estimate.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_estimate_material_row_estimate_id", "estimate_material_row", ["estimate_id"])


def downgrade() -> None:
    op.drop_table("estimate_material_row")
    op.drop_table("estimate_equipment_row")
    op.drop_table("estimate_task")
    op.drop_index("ix_estimate_estimate_number", table_name="estimate")
    op.drop_index("ix_estimate_client_id", table_name="estimate")
    op.drop_index("ix_estimate_job_id", table_name="estimate")
    op.drop_table("estimate")
