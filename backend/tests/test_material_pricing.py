"""
Tests for material_pricing.search_materials: cache hit/miss behavior, staleness
refresh, price parsing, and graceful degradation when SerpApi is unavailable.
"""
from datetime import datetime, timedelta
from unittest.mock import patch

import pytest
import requests
from sqlmodel import Session, SQLModel, create_engine, select

from app.models.material_price_cache import MaterialPriceCache
from app.services import material_pricing


@pytest.fixture
def session():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False})
    SQLModel.metadata.create_all(engine)
    with Session(engine) as s:
        yield s


def _fake_serpapi_response(*titles_prices):
    return {
        "products": [
            {"title": t, "price": p, "thumbnails": ["http://img"], "link": "http://link"}
            for t, p in titles_prices
        ]
    }


class TestParsePrice:
    def test_single_price(self):
        assert material_pricing._parse_price("$8.98") == 8.98

    def test_range_price_uses_median(self):
        assert material_pricing._parse_price("$12.98 - $45.00") == 28.99

    def test_none_or_empty(self):
        assert material_pricing._parse_price(None) is None
        assert material_pricing._parse_price("") is None

    def test_unparseable(self):
        assert material_pricing._parse_price("Call for price") is None


class TestSearchMaterials:
    def test_missing_api_key_returns_empty_list(self, session, monkeypatch):
        monkeypatch.setattr(material_pricing.settings, "SERPAPI_KEY", None)
        with patch("app.services.material_pricing.requests.get") as mock_get:
            result = material_pricing.search_materials(session, "drywall screws")
        mock_get.assert_not_called()
        assert result == []

    def test_cache_miss_calls_serpapi_and_persists(self, session, monkeypatch):
        monkeypatch.setattr(material_pricing.settings, "SERPAPI_KEY", "fake-key")
        with patch("app.services.material_pricing.requests.get") as mock_get:
            mock_get.return_value.json.return_value = _fake_serpapi_response(
                ("Drywall Screws 1lb", "$8.98")
            )
            result = material_pricing.search_materials(session, "drywall screws")

        mock_get.assert_called_once()
        assert len(result) == 1
        assert result[0].product_name == "Drywall Screws 1lb"
        assert result[0].price_value == 8.98

        rows = session.exec(select(MaterialPriceCache)).all()
        assert len(rows) == 1

    def test_cache_hit_skips_http_call(self, session, monkeypatch):
        monkeypatch.setattr(material_pricing.settings, "SERPAPI_KEY", "fake-key")
        session.add(MaterialPriceCache(
            query="drywall screws", product_name="Drywall Screws 1lb",
            price="$8.98", price_value=8.98,
        ))
        session.commit()

        with patch("app.services.material_pricing.requests.get") as mock_get:
            result = material_pricing.search_materials(session, "Drywall Screws")

        mock_get.assert_not_called()
        assert len(result) == 1
        assert result[0].product_name == "Drywall Screws 1lb"

    def test_stale_cache_triggers_refresh_and_replaces_old_rows(self, session, monkeypatch):
        monkeypatch.setattr(material_pricing.settings, "SERPAPI_KEY", "fake-key")
        stale_time = datetime.utcnow() - timedelta(hours=200)
        session.add(MaterialPriceCache(
            query="drywall screws", product_name="Old Product",
            price="$5.00", price_value=5.00, fetched_at=stale_time,
        ))
        session.commit()

        with patch("app.services.material_pricing.requests.get") as mock_get:
            mock_get.return_value.json.return_value = _fake_serpapi_response(
                ("New Product", "$9.99")
            )
            result = material_pricing.search_materials(session, "drywall screws", ttl_hours=168)

        mock_get.assert_called_once()
        rows = session.exec(select(MaterialPriceCache)).all()
        assert len(rows) == 1
        assert rows[0].product_name == "New Product"

    def test_serpapi_request_exception_returns_empty_list(self, session, monkeypatch):
        monkeypatch.setattr(material_pricing.settings, "SERPAPI_KEY", "fake-key")
        with patch("app.services.material_pricing.requests.get", side_effect=requests.RequestException("boom")):
            result = material_pricing.search_materials(session, "drywall screws")
        assert result == []

    def test_serpapi_error_key_returns_empty_list(self, session, monkeypatch):
        monkeypatch.setattr(material_pricing.settings, "SERPAPI_KEY", "fake-key")
        with patch("app.services.material_pricing.requests.get") as mock_get:
            mock_get.return_value.json.return_value = {"error": "Invalid API key"}
            result = material_pricing.search_materials(session, "drywall screws")
        assert result == []

    def test_blank_query_returns_empty_list_without_calling_serpapi(self, session, monkeypatch):
        monkeypatch.setattr(material_pricing.settings, "SERPAPI_KEY", "fake-key")
        with patch("app.services.material_pricing.requests.get") as mock_get:
            result = material_pricing.search_materials(session, "   ")
        mock_get.assert_not_called()
        assert result == []
