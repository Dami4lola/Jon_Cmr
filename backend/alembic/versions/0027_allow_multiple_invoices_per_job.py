"""Allow multiple invoices per job, billed by period, at a per-job billable rate

A job can now be invoiced as many times as it takes, at any point in its life, so long
jobs can be progress-billed instead of being carried unbilled until they are marked
complete. Each invoice covers a billing period, and a timesheet's single date puts it in
exactly one of them.

invoice.job_id loses its unique index. The one-invoice-per-job rule was only ever
expressed as a UNIQUE INDEX (ix_invoice_job_id) created by SQLModel's
Field(unique=True, index=True), never as a table-level constraint, so dropping and
recreating the index non-unique is plain DDL on both Postgres and SQLite. The
get_unique_constraints branch below is defensive only.

period_start/period_end are not backfilled: null means unbounded in that direction, so
the null/null every existing row already carries reads as "the whole job", which is
exactly what those invoices billed.

invoice.labour_rate/redseal_rate are new frozen columns - the invoice already froze
km_rate, and labour was stored only as an amount, so an invoice issued before a job's
billable rate changed could not be explained from any row. The server defaults ARE the
historical backfill and are correct: every invoice ever issued was priced at the
LABOUR_RATE/REDSEAL_RATE constants, 80.00 and 100.00.

job.billable_* rates get no server default. Null means "inherit from the estimate, else
the global constant", resolved at read time, and a default would make every existing job
look deliberately overridden.

Revision ID: 0027
Revises: 0026
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect as sa_inspect

revision = "0027"
down_revision = "0026"
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa_inspect(conn)
    tables = inspector.get_table_names()

    if "invoice" in tables:
        invoice_columns = [c["name"] for c in inspector.get_columns("invoice")]

        if "period_start" not in invoice_columns:
            op.add_column("invoice", sa.Column("period_start", sa.Date(), nullable=True))
        if "period_end" not in invoice_columns:
            op.add_column("invoice", sa.Column("period_end", sa.Date(), nullable=True))
        if "labour_rate" not in invoice_columns:
            op.add_column(
                "invoice",
                sa.Column(
                    "labour_rate",
                    sa.Numeric(precision=6, scale=2),
                    nullable=False,
                    server_default="80.00",
                ),
            )
        if "redseal_rate" not in invoice_columns:
            op.add_column(
                "invoice",
                sa.Column(
                    "redseal_rate",
                    sa.Numeric(precision=6, scale=2),
                    nullable=False,
                    server_default="100.00",
                ),
            )

        indexes = {ix["name"]: ix for ix in inspector.get_indexes("invoice")}
        job_id_index = indexes.get("ix_invoice_job_id")
        if job_id_index is None:
            op.create_index("ix_invoice_job_id", "invoice", ["job_id"], unique=False)
        elif job_id_index["unique"]:
            op.drop_index("ix_invoice_job_id", table_name="invoice")
            op.create_index("ix_invoice_job_id", "invoice", ["job_id"], unique=False)

        # Defensive: a database whose invoice table was ever built with a table-level
        # UNIQUE would not be covered above. Postgres only - SQLite reports an inline
        # unique with name=None, which drop_constraint cannot address without a full
        # table rebuild, and the model provably emits an index rather than a constraint.
        if conn.dialect.name != "sqlite":
            for constraint in inspector.get_unique_constraints("invoice"):
                if constraint["column_names"] == ["job_id"] and constraint.get("name"):
                    op.drop_constraint(constraint["name"], "invoice", type_="unique")

    if "job" in tables:
        job_columns = [c["name"] for c in inspector.get_columns("job")]

        if "billable_labour_rate" not in job_columns:
            op.add_column(
                "job",
                sa.Column("billable_labour_rate", sa.Numeric(precision=6, scale=2), nullable=True),
            )
        if "billable_redseal_rate" not in job_columns:
            op.add_column(
                "job",
                sa.Column("billable_redseal_rate", sa.Numeric(precision=6, scale=2), nullable=True),
            )
        if "billable_km_rate" not in job_columns:
            op.add_column(
                "job",
                sa.Column("billable_km_rate", sa.Numeric(precision=5, scale=2), nullable=True),
            )


def downgrade() -> None:
    """
    Restores the one-invoice-per-job unique index.

    This FAILS on any database where a job has more than one invoice, and failing is the
    correct outcome - deleting a customer's invoices to satisfy a constraint is not a
    downgrade. Remove the extra invoices deliberately first if this is really intended.
    """
    op.drop_column("job", "billable_km_rate")
    op.drop_column("job", "billable_redseal_rate")
    op.drop_column("job", "billable_labour_rate")

    op.drop_column("invoice", "redseal_rate")
    op.drop_column("invoice", "labour_rate")
    op.drop_column("invoice", "period_end")
    op.drop_column("invoice", "period_start")

    op.drop_index("ix_invoice_job_id", table_name="invoice")
    op.create_index("ix_invoice_job_id", "invoice", ["job_id"], unique=True)
