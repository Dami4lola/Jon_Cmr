"""Add redseal_techs/redseal_rate to estimate, uses_redseal to estimate_task

Red Seal is now computed from tasks tagged uses_redseal (hours x
redseal_techs x redseal_rate) instead of a flat manually-entered amount.

Revision ID: 0022
Revises: 0021
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect as sa_inspect

revision = "0022"
down_revision = "0021"
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa_inspect(conn)

    estimate_columns = [c["name"] for c in inspector.get_columns("estimate")]
    if "redseal_techs" not in estimate_columns:
        op.add_column(
            "estimate",
            sa.Column("redseal_techs", sa.Integer(), nullable=False, server_default="0"),
        )
    if "redseal_rate" not in estimate_columns:
        op.add_column(
            "estimate",
            sa.Column("redseal_rate", sa.Numeric(precision=6, scale=2), nullable=False, server_default="100.00"),
        )

    task_columns = [c["name"] for c in inspector.get_columns("estimate_task")]
    if "uses_redseal" not in task_columns:
        op.add_column(
            "estimate_task",
            sa.Column("uses_redseal", sa.Boolean(), nullable=False, server_default=sa.false()),
        )


def downgrade() -> None:
    op.drop_column("estimate_task", "uses_redseal")
    op.drop_column("estimate", "redseal_rate")
    op.drop_column("estimate", "redseal_techs")
