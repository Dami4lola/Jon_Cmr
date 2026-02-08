"""change materials_needed to text

Revision ID: a1b2c3d4e5f6
Revises: 9a79b61a1d4d
Create Date: 2026-02-07

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, None] = '9a79b61a1d4d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Convert boolean column to text
    # PostgreSQL: use USING to cast existing boolean values to text
    op.alter_column(
        'job_inspection',
        'materials_needed',
        type_=sa.String(),
        existing_type=sa.Boolean(),
        existing_nullable=True,
        postgresql_using="CASE WHEN materials_needed = true THEN 'Yes' WHEN materials_needed = false THEN 'No' ELSE NULL END"
    )


def downgrade() -> None:
    op.alter_column(
        'job_inspection',
        'materials_needed',
        type_=sa.Boolean(),
        existing_type=sa.String(),
        existing_nullable=True,
        postgresql_using="CASE WHEN materials_needed = 'Yes' THEN true WHEN materials_needed = 'No' THEN false ELSE NULL END"
    )
