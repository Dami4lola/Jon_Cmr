"""
Tests for the distance service: Google Distance Matrix as primary provider, Mapbox as
the fallback when Google cannot answer, and no fallback when Google says the address
does not exist.
"""
from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest
import requests

from app.services import distance

OFFICE_COORDS = [-75.70, 45.41]
DEST_COORDS = [-76.25, 44.90]


@pytest.fixture(autouse=True)
def keys(monkeypatch):
    monkeypatch.setattr(distance.settings, "GOOGLE_MAPS_API_KEY", "google-key")
    monkeypatch.setattr(distance.settings, "MAPBOX_ACCESS_TOKEN", "mapbox-token")
    monkeypatch.setattr(distance.settings, "OFFICE_ADDRESS", "244 Bell Street North, Ottawa")


def _response(payload, status_code=200):
    resp = MagicMock()
    resp.status_code = status_code
    resp.json.return_value = payload
    return resp


def _google_ok(meters=20_300, duration="25 mins"):
    return _response({
        "status": "OK",
        "rows": [{"elements": [{
            "status": "OK",
            "distance": {"value": meters},
            "duration": {"text": duration},
        }]}],
    })


def _google_element(status):
    return _response({"status": "OK", "rows": [{"elements": [{"status": status}]}]})


def _geocode(coords):
    return _response({"features": [{"geometry": {"coordinates": coords}}]})


def _directions(meters=40_200, seconds=4_980):
    return _response({"code": "Ok", "routes": [{"distance": meters, "duration": seconds}]})


def _router(google, geocode_office=None, geocode_dest=None, directions=None):
    """side_effect for requests.get that dispatches on URL and records the calls."""
    calls = []

    def fake_get(url, params=None, timeout=None):
        calls.append(url)
        if url.startswith(distance.GOOGLE_DISTANCE_MATRIX_URL):
            result = google
        elif url.startswith(distance.MAPBOX_GEOCODE_URL):
            is_office = params["q"] == distance.settings.OFFICE_ADDRESS
            result = geocode_office if is_office else geocode_dest
        elif url.startswith(distance.MAPBOX_DIRECTIONS_URL):
            result = directions
        else:
            raise AssertionError(f"unexpected URL {url}")
        if isinstance(result, Exception):
            raise result
        return result

    return fake_get, calls


def _mapbox_calls(calls):
    return [c for c in calls if c.startswith("https://api.mapbox.com")]


def _healthy_mapbox():
    return dict(
        geocode_office=_geocode(OFFICE_COORDS),
        geocode_dest=_geocode(DEST_COORDS),
        directions=_directions(),
    )


class TestCalculateDistance:
    def test_google_success_never_calls_mapbox(self):
        fake_get, calls = _router(_google_ok(meters=20_300), **_healthy_mapbox())
        with patch("app.services.distance.requests.get", side_effect=fake_get):
            assert distance.calculate_distance("Perth, ON") == Decimal("41")
        assert _mapbox_calls(calls) == []

    def test_google_timeout_falls_back_to_mapbox(self):
        fake_get, calls = _router(requests.Timeout("slow"), **_healthy_mapbox())
        with patch("app.services.distance.requests.get", side_effect=fake_get):
            # 40.2 km one way -> 80.4 round trip -> ceiling 81
            assert distance.calculate_distance("Perth, ON") == Decimal("81")
        assert len(_mapbox_calls(calls)) == 3

    def test_google_quota_error_falls_back_to_mapbox(self):
        google = _response({"status": "OVER_QUERY_LIMIT"})
        fake_get, _ = _router(google, **_healthy_mapbox())
        with patch("app.services.distance.requests.get", side_effect=fake_get):
            assert distance.calculate_distance("Perth, ON") == Decimal("81")

    def test_google_server_error_falls_back_to_mapbox(self):
        google = _response(None, status_code=503)
        google.json.side_effect = ValueError("not json")
        fake_get, _ = _router(google, **_healthy_mapbox())
        with patch("app.services.distance.requests.get", side_effect=fake_get):
            assert distance.calculate_distance("Perth, ON") == Decimal("81")

    def test_google_not_found_is_final(self):
        fake_get, calls = _router(_google_element("NOT_FOUND"), **_healthy_mapbox())
        with patch("app.services.distance.requests.get", side_effect=fake_get):
            assert distance.calculate_distance("asdfgh") is None
        assert _mapbox_calls(calls) == []

    def test_no_google_key_uses_mapbox(self, monkeypatch):
        monkeypatch.setattr(distance.settings, "GOOGLE_MAPS_API_KEY", None)
        fake_get, calls = _router(AssertionError("Google must not be called"), **_healthy_mapbox())
        with patch("app.services.distance.requests.get", side_effect=fake_get):
            assert distance.calculate_distance("Perth, ON") == Decimal("81")
        assert len(_mapbox_calls(calls)) == 3

    def test_google_down_without_mapbox_token_returns_none(self, monkeypatch):
        monkeypatch.setattr(distance.settings, "MAPBOX_ACCESS_TOKEN", None)
        fake_get, calls = _router(requests.ConnectionError("down"), **_healthy_mapbox())
        with patch("app.services.distance.requests.get", side_effect=fake_get):
            assert distance.calculate_distance("Perth, ON") is None
        assert _mapbox_calls(calls) == []

    def test_both_providers_down_returns_none(self):
        fake_get, _ = _router(
            requests.ConnectionError("down"),
            geocode_office=requests.ConnectionError("down"),
            geocode_dest=requests.ConnectionError("down"),
            directions=requests.ConnectionError("down"),
        )
        with patch("app.services.distance.requests.get", side_effect=fake_get):
            assert distance.calculate_distance("Perth, ON") is None

    def test_mapbox_address_not_found_returns_none(self):
        fake_get, calls = _router(
            requests.Timeout("slow"),
            geocode_office=_geocode(OFFICE_COORDS),
            geocode_dest=_response({"features": []}),
            directions=_directions(),
        )
        with patch("app.services.distance.requests.get", side_effect=fake_get):
            assert distance.calculate_distance("asdfgh") is None
        assert not any(c.startswith(distance.MAPBOX_DIRECTIONS_URL) for c in calls)

    def test_mapbox_no_route_returns_none(self):
        fake_get, _ = _router(
            requests.Timeout("slow"),
            geocode_office=_geocode(OFFICE_COORDS),
            geocode_dest=_geocode(DEST_COORDS),
            directions=_response({"code": "NoRoute", "routes": []}),
        )
        with patch("app.services.distance.requests.get", side_effect=fake_get):
            assert distance.calculate_distance("Island, ON") is None

    def test_empty_destination_makes_no_requests(self):
        with patch("app.services.distance.requests.get") as mock_get:
            assert distance.calculate_distance("") is None
        mock_get.assert_not_called()


class TestGetDistanceInfo:
    def test_google_success(self):
        fake_get, _ = _router(_google_ok(meters=20_300, duration="25 mins"))
        with patch("app.services.distance.requests.get", side_effect=fake_get):
            info = distance.get_distance_info("Perth, ON")
        assert info == {
            "one_way_km": 21,
            "round_trip_km": 41,
            "duration_one_way": "25 mins",
            "origin": "244 Bell Street North, Ottawa",
            "destination": "Perth, ON",
        }

    def test_mapbox_fallback_returns_same_shape(self):
        fake_get, _ = _router(requests.Timeout("slow"), **_healthy_mapbox())
        with patch("app.services.distance.requests.get", side_effect=fake_get):
            info = distance.get_distance_info("Perth, ON")
        assert info == {
            "one_way_km": 41,
            "round_trip_km": 81,
            "duration_one_way": "1 hour 23 mins",
            "origin": "244 Bell Street North, Ottawa",
            "destination": "Perth, ON",
        }

    def test_no_provider_configured(self, monkeypatch):
        monkeypatch.setattr(distance.settings, "GOOGLE_MAPS_API_KEY", None)
        monkeypatch.setattr(distance.settings, "MAPBOX_ACCESS_TOKEN", None)
        assert "error" in distance.get_distance_info("Perth, ON")

    def test_not_found_returns_error(self):
        fake_get, _ = _router(_google_element("ZERO_RESULTS"))
        with patch("app.services.distance.requests.get", side_effect=fake_get):
            info = distance.get_distance_info("asdfgh")
        assert info == {"error": "Route not found: ZERO_RESULTS"}


@pytest.mark.parametrize("seconds,expected", [
    (30, "1 min"),
    (1_500, "25 mins"),
    (3_600, "1 hour"),
    (4_980, "1 hour 23 mins"),
    (7_260, "2 hours 1 min"),
])
def test_format_duration(seconds, expected):
    assert distance._format_duration(seconds) == expected
