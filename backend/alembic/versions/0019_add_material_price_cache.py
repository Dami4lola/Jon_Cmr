"""Add material_price_cache table for Home Depot price lookups

Revision ID: 0019
Revises: 0018
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect as sa_inspect

revision = "0019"
down_revision = "0018"
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa_inspect(conn)

    if "material_price_cache" not in inspector.get_table_names():
        op.create_table(
            "material_price_cache",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("query", sa.String(200), nullable=False),
            sa.Column("product_name", sa.String(300), nullable=False),
            sa.Column("price", sa.String(50), nullable=True),
            sa.Column("price_value", sa.Float(), nullable=True),
            sa.Column("thumbnail", sa.String(1000), nullable=True),
            sa.Column("product_url", sa.String(1000), nullable=True),
            sa.Column("source", sa.String(50), nullable=False, server_default="home_depot"),
            sa.Column("fetched_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index(
            "ix_material_price_cache_query", "material_price_cache", ["query"]
        )
        op.create_index(
            "ix_material_price_cache_fetched_at", "material_price_cache", ["fetched_at"]
        )


def downgrade() -> None:
    op.drop_index("ix_material_price_cache_fetched_at", table_name="material_price_cache")
    op.drop_index("ix_material_price_cache_query", table_name="material_price_cache")
    op.drop_table("material_price_cache")
