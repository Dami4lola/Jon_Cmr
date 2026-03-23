"""Add dates JSON column to time_off_request

Revision ID: 0014
Revises: 0013
"""
from alembic import op
from sqlalchemy import inspect
import sqlalchemy as sa

revision = "0014"
down_revision = "0013"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)

    if "time_off_request" in inspector.get_table_names():
        columns = [c["name"] for c in inspector.get_columns("time_off_request")]
        if "dates" not in columns:
            op.add_column(
                "time_off_request",
                sa.Column("dates", sa.JSON(), nullable=True),
            )
            op.execute(
                "UPDATE time_off_request SET dates = '[]' WHERE dates IS NULL"
            )
            op.alter_column("time_off_request", "dates", nullable=False)


def downgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)

    if "time_off_request" in inspector.get_table_names():
        columns = [c["name"] for c in inspector.get_columns("time_off_request")]
        if "dates" in columns:
            op.drop_column("time_off_request", "dates")
