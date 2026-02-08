"""
Database configuration with SQLModel
"""
from sqlmodel import SQLModel, Session, create_engine
from sqlalchemy import text, inspect
from typing import Generator

from .config import settings

# Create engine based on DATABASE_URL
connect_args = {}
if settings.DATABASE_URL.startswith("sqlite"):
    connect_args = {"check_same_thread": False}

engine = create_engine(
    settings.DATABASE_URL,
    connect_args=connect_args,
    echo=False,  # Set to True for SQL debugging
)


def _fix_inspection_tables():
    """
    Fix inspection tables if they were created with an old schema.
    create_all() doesn't alter existing tables, so if the table exists
    but is missing columns (e.g. 'type'), drop and let create_all() rebuild it.
    """
    insp = inspect(engine)
    if not insp.has_table("job_inspection"):
        return  # Table doesn't exist yet, create_all() will handle it

    columns = [c["name"] for c in insp.get_columns("job_inspection")]
    if "type" in columns:
        return  # Schema is correct

    print("Fixing job_inspection table schema (missing 'type' column)...")
    with engine.begin() as conn:
        conn.execute(text("DROP TABLE IF EXISTS inspection_photo CASCADE"))
        conn.execute(text("DROP TABLE IF EXISTS job_inspection CASCADE"))
    print("Dropped old inspection tables. create_all() will recreate them.")


def create_db_and_tables():
    """Create all database tables"""
    _fix_inspection_tables()
    SQLModel.metadata.create_all(engine)


def get_session() -> Generator[Session, None, None]:
    """Dependency for getting database sessions"""
    with Session(engine) as session:
        yield session
