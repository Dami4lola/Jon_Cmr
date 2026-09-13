"""Add heavy_equipment_rate column on estimate

Tasks tagged uses_heavy_equipment now contribute their hours x
heavy_equipment_rate into heavy_equipment_amount, alongside any manually-added
"heavy" Equipment & Fuel rows - previously the checkbox was purely cosmetic.

Revision ID: 0024
Revises: 0023
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect as sa_inspect

revision = "0024"
down_revision = "0023"
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa_inspect(conn)

    estimate_columns = [c["name"] for c in inspector.get_columns("estimate")]
    if "heavy_equipment_rate" not in estimate_columns:
        op.add_column(
            "estimate",
            sa.Column("heavy_equipment_rate", sa.Numeric(precision=10, scale=2), nullable=False, server_default="120.00"),
        )


def downgrade() -> None:
    op.drop_column("estimate", "heavy_equipment_rate")
