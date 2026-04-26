"""Split job description into title + details, add job_photo table

Revision ID: 0008
Revises: 0007
"""
from alembic import op
from sqlalchemy import inspect
import sqlalchemy as sa

revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()
    insp = inspect(conn)

    # Get current job columns
    job_columns = [c["name"] for c in insp.get_columns("job")]

    # 1. Rename description -> title (only if description still exists)
    if "description" in job_columns and "title" not in job_columns:
        op.alter_column("job", "description", new_column_name="title")

    # 2. Add details column if it doesn't exist
    if "details" not in job_columns:
        op.add_column("job", sa.Column("details", sa.Text(), nullable=True))

    # 3. Create job_photo table if it doesn't exist
    if not insp.has_table("job_photo"):
        op.create_table(
            "job_photo",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("job_id", sa.Integer(), nullable=False),
            sa.Column("public_url", sa.String(), nullable=False),
            sa.Column("content_type", sa.String(), nullable=False),
            sa.Column("caption", sa.String(), nullable=True),
            sa.Column("uploaded_at", sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(["job_id"], ["job.id"]),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_job_photo_job_id", "job_photo", ["job_id"])


def downgrade() -> None:
    op.drop_index("ix_job_photo_job_id", table_name="job_photo")
    op.drop_table("job_photo")
    op.drop_column("job", "details")
    op.alter_column("job", "title", new_column_name="description")
