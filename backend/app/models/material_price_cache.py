"""
Cached Home Depot material price lookups (SerpApi engine=home_depot)
"""
from sqlmodel import SQLModel, Field
from datetime import datetime


class MaterialPriceCache(SQLModel, table=True):
    """One cached search result row for a normalized material search query"""
    __tablename__ = "material_price_cache"

    id: int | None = Field(default=None, primary_key=True)
    query: str = Field(max_length=200, index=True)
    product_name: str = Field(max_length=300)
    price: str | None = Field(default=None, max_length=50)
    price_value: float | None = Field(default=None)
    thumbnail: str | None = Field(default=None, max_length=1000)
    product_url: str | None = Field(default=None, max_length=1000)
    source: str = Field(default="home_depot", max_length=50)
    fetched_at: datetime = Field(default_factory=datetime.utcnow, index=True)
