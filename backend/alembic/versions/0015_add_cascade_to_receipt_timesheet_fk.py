"""Add cascade delete for receipt -> timesheet foreign key

Revision ID: 0015
Revises: 0014
"""
from alembic import op
from sqlalchemy import inspect
import sqlalchemy as sa


# revision identifiers
revision = "0015"
down_revision = "0014"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "sqlite":
        return

    inspector = inspect(bind)
    fks = inspector.get_foreign_keys("receipt")

    for fk in fks:
        if fk["referred_table"] == "timesheet" and fk["constrained_columns"] == ["timesheet_id"]:
            constraint_name = fk.get("name") or "receipt_timesheet_id_fkey"
            op.drop_constraint(constraint_name, "receipt", type_="foreignkey")
            op.create_foreign_key(
                constraint_name,
                "receipt",
                "timesheet",
                ["timesheet_id"],
                ["id"],
                ondelete="CASCADE",
            )
            break


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "sqlite":
        return

    inspector = inspect(bind)
    fks = inspector.get_foreign_keys("receipt")

    for fk in fks:
        if fk["referred_table"] == "timesheet" and fk["constrained_columns"] == ["timesheet_id"]:
            constraint_name = fk.get("name") or "receipt_timesheet_id_fkey"
            op.drop_constraint(constraint_name, "receipt", type_="foreignkey")
            op.create_foreign_key(
                constraint_name,
                "receipt",
                "timesheet",
                ["timesheet_id"],
                ["id"],
            )
            break
