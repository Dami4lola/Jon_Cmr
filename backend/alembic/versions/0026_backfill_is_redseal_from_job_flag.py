"""Tick is_redseal on timesheets of genuinely Red Seal jobs

The billed labour rate is now decided solely by Timesheet.is_redseal;
Job.is_redseal_trade no longer prices anything. Without this backfill every existing
flagged job would silently drop from the Red Seal rate to the standard one.

Two deliberate choices in the query below:

  - PAID timesheets are ticked too. is_redseal is billing-only and the invoice
    calculation selects every timesheet on a job regardless of is_paid, so skipping
    paid rows would under-bill Red Seal work already done. It cannot affect a payout -
    the payout engine never reads the field.

  - Jobs with NO estimate are included. Such a flag was set by hand in the Manager
    Dashboard, so it is a real assertion. Only the estimate-with-no-tagged-tasks case
    is excluded: those were flagged by the redseal_techs auto-fill bug fixed in
    4cbf6b6, not by real Red Seal scope, and ticking them would bake that error into
    the data permanently.

Revision ID: 0026
Revises: 0025
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect as sa_inspect

revision = "0026"
down_revision = "0025"
branch_labels = None
depends_on = None


BACKFILL = """
UPDATE timesheet SET is_redseal = true
WHERE job_id IN (
  SELECT j.id FROM job j
  WHERE j.is_redseal_trade = true
    AND NOT EXISTS (
      SELECT 1 FROM estimate e
      WHERE e.job_id = j.id
        AND NOT EXISTS (
          SELECT 1 FROM estimate_task t
          WHERE t.estimate_id = e.id AND t.uses_redseal = true
        )
    )
)
"""


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa_inspect(conn)
    tables = inspector.get_table_names()

    # estimate/estimate_task are needed by the exclusion clause; on a brand-new
    # database there is nothing to backfill anyway.
    required = {"timesheet", "job", "estimate", "estimate_task"}
    if not required.issubset(tables):
        return

    op.execute(sa.text(BACKFILL))


def downgrade() -> None:
    # Deliberately not reversed: un-ticking would also clear flags a worker or manager
    # set by hand after this migration ran, and there is no way to tell them apart.
    pass
