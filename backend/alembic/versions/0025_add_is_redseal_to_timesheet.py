"""Add is_redseal to timesheet, widen invoice.total_distance_km

A worker can now tick Red Seal on an individual timesheet, so Red Seal work can be
billed at the Red Seal rate on a job that is not itself flagged as a Red Seal trade.

No backfill: a Red Seal job still bills every hour at the Red Seal rate on the
strength of job.is_redseal_trade alone, so existing rows default to false and every
existing job's labour stays byte-identical. The flag is purely additive - it can raise
a standard job's hours to the Red Seal rate but can never lower a Red Seal job's.

total_distance_km is widened because billing moved from one trip per (date, worker)
to one trip per timesheet, which puts >9999.99 km within reach on a long job.

Revision ID: 0025
Revises: 0024
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect as sa_inspect

revision = "0025"
down_revision = "0024"
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa_inspect(conn)

    tables = inspector.get_table_names()

    if "timesheet" in tables:
        timesheet_columns = [c["name"] for c in inspector.get_columns("timesheet")]
        if "is_redseal" not in timesheet_columns:
            op.add_column(
                "timesheet",
                sa.Column(
                    "is_redseal",
                    sa.Boolean(),
                    nullable=False,
                    server_default=sa.false(),
                ),
            )

    # SQLite has no ALTER COLUMN ... TYPE, and it does not enforce numeric precision
    # in the first place, so the widening is only meaningful (and only possible) on
    # Postgres. Rebuilding the invoice table under SQLite to change a constraint it
    # ignores would be pure cost.
    if "invoice" in tables and conn.dialect.name != "sqlite":
        op.alter_column(
            "invoice",
            "total_distance_km",
            type_=sa.Numeric(precision=8, scale=2),
            existing_nullable=False,
        )


def downgrade() -> None:
    conn = op.get_bind()
    if conn.dialect.name != "sqlite":
        op.alter_column(
            "invoice",
            "total_distance_km",
            type_=sa.Numeric(precision=6, scale=2),
            existing_nullable=False,
        )
    op.drop_column("timesheet", "is_redseal")
