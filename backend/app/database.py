"""
Database configuration with SQLModel
"""
from sqlmodel import SQLModel, Session, create_engine
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


def create_db_and_tables():
    """Create all database tables"""
    SQLModel.metadata.create_all(engine)


def get_session() -> Generator[Session, None, None]:
    """Dependency for getting database sessions"""
    with Session(engine) as session:
        yield session
