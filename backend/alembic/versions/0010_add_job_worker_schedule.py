"""Add job_worker_schedule table for day-level tech assignments

Revision ID: 0010
Revises: 0009
"""
from alembic import op
from sqlalchemy import inspect
import sqlalchemy as sa

revision = "0010"
down_revision = "0009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()
    insp = inspect(conn)
    tables = insp.get_table_names()

    if "job_worker_schedule" not in tables:
        op.create_table(
            "job_worker_schedule",
            sa.Column("job_id", sa.Integer(), sa.ForeignKey("job.id"), primary_key=True),
            sa.Column("worker_id", sa.Integer(), sa.ForeignKey("worker.id"), primary_key=True),
            sa.Column("date", sa.Date(), primary_key=True),
        )

    # Data migration: populate schedule from existing job_worker_link entries
    # For each assigned worker, create schedule entries for each day in the job's date range
    conn.execute(sa.text("""
        INSERT OR IGNORE INTO job_worker_schedule (job_id, worker_id, date)
        SELECT jwl.job_id, jwl.worker_id, j.start_date
        FROM job_worker_link jwl
        JOIN job j ON j.id = jwl.job_id
        WHERE j.start_date IS NOT NULL
        AND NOT EXISTS (
            SELECT 1 FROM job_worker_schedule jws
            WHERE jws.job_id = jwl.job_id AND jws.worker_id = jwl.worker_id
        )
    """))


def downgrade() -> None:
    op.drop_table("job_worker_schedule")
