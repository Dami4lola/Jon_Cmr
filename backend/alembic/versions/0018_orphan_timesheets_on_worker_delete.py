"""Allow employee deletion: orphan timesheets instead of blocking

Revision ID: 0018
Revises: 0017
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect as sa_inspect

revision = "0018"
down_revision = "0017"
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa_inspect(conn)
    columns = [c["name"] for c in inspector.get_columns("timesheet")]

    with op.batch_alter_table("timesheet") as batch_op:
        if "worker_name_snapshot" not in columns:
            batch_op.add_column(sa.Column("worker_name_snapshot", sa.String(length=100), nullable=True))
        batch_op.alter_column("worker_id", existing_type=sa.Integer(), nullable=True)


def downgrade() -> None:
    with op.batch_alter_table("timesheet") as batch_op:
        batch_op.alter_column("worker_id", existing_type=sa.Integer(), nullable=False)
        batch_op.drop_column("worker_name_snapshot")
