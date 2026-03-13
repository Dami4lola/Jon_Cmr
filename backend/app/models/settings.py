"""
Application settings model (key-value store)
"""
from sqlmodel import SQLModel, Field


class AppSettings(SQLModel, table=True):
    """Simple key-value settings table"""
    __tablename__ = "app_settings"

    key: str = Field(primary_key=True, max_length=100)
    value: str = Field(max_length=500)
