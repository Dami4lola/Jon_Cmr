"""simplify timesheets and multi-day jobs

Revision ID: 0002
Revises: 0001
Create Date: 2026-02-22

- Remove receipts_total, receipt_card_digits, round_trip_kms from timesheet
- Add break_duration to timesheet
- Replace scheduled_date with start_date/end_date on job
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0002'
down_revision: Union[str, None] = '0001'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # --- Timesheet changes ---
    # Add break_duration column
    op.add_column('timesheet', sa.Column('break_duration', sa.Numeric(precision=4, scale=2), nullable=False, server_default='0'))

    # Remove old columns
    op.drop_column('timesheet', 'round_trip_kms')
    op.drop_column('timesheet', 'receipts_total')
    op.drop_column('timesheet', 'receipt_card_digits')

    # --- Job changes ---
    # Add start_date and end_date columns
    op.add_column('job', sa.Column('start_date', sa.Date(), nullable=True))
    op.add_column('job', sa.Column('end_date', sa.Date(), nullable=True))

    # Migrate existing scheduled_date data to start_date and end_date
    op.execute("UPDATE job SET start_date = scheduled_date, end_date = scheduled_date")

    # Create index on start_date
    op.create_index('ix_job_start_date', 'job', ['start_date'])

    # Drop old scheduled_date column and its index
    op.drop_index('ix_job_scheduled_date', table_name='job')
    op.drop_column('job', 'scheduled_date')


def downgrade() -> None:
    # --- Job changes ---
    op.add_column('job', sa.Column('scheduled_date', sa.Date(), nullable=True))
    op.execute("UPDATE job SET scheduled_date = start_date")
    op.create_index('ix_job_scheduled_date', 'job', ['scheduled_date'])
    op.drop_index('ix_job_start_date', table_name='job')
    op.drop_column('job', 'end_date')
    op.drop_column('job', 'start_date')

    # --- Timesheet changes ---
    op.add_column('timesheet', sa.Column('receipt_card_digits', sa.String(length=4), nullable=True))
    op.add_column('timesheet', sa.Column('receipts_total', sa.Numeric(precision=8, scale=2), nullable=False, server_default='0'))
    op.add_column('timesheet', sa.Column('round_trip_kms', sa.Numeric(precision=6, scale=2), nullable=False, server_default='0'))
    op.drop_column('timesheet', 'break_duration')
