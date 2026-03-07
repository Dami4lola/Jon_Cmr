"""Add sms_log table for SMS reminders

Revision ID: 0011
Revises: 0010
"""
from alembic import op
from sqlalchemy import inspect
import sqlalchemy as sa

revision = "0011"
down_revision = "0010"
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()
    insp = inspect(conn)
    tables = insp.get_table_names()

    if "sms_log" not in tables:
        op.create_table(
            "sms_log",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("job_id", sa.Integer(), sa.ForeignKey("job.id"), nullable=False, index=True),
            sa.Column("client_id", sa.Integer(), sa.ForeignKey("client.id"), nullable=False),
            sa.Column("phone_number", sa.String(20), nullable=False),
            sa.Column("message_body", sa.Text(), nullable=False),
            sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
            sa.Column("twilio_sid", sa.String(50), nullable=True),
            sa.Column("error_message", sa.Text(), nullable=True),
            sa.Column("sent_at", sa.DateTime(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        )


def downgrade() -> None:
    op.drop_table("sms_log")
