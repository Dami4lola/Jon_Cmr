"""
Distance calculation service.

Google Maps Distance Matrix is the primary provider. Mapbox (Geocoding + Directions)
is tried only when Google cannot answer at all - outage, quota, bad key - so a Google
problem no longer silently prices travel at $0.
"""
import logging
import math
from decimal import Decimal
from typing import NamedTuple

import requests

from ..config import settings

logger = logging.getLogger(__name__)

GOOGLE_DISTANCE_MATRIX_URL = "https://maps.googleapis.com/maps/api/distancematrix/json"
MAPBOX_GEOCODE_URL = "https://api.mapbox.com/search/geocode/v6/forward"
MAPBOX_DIRECTIONS_URL = "https://api.mapbox.com/directions/v5/mapbox/driving"

GOOGLE_TIMEOUT_SECONDS = 10
MAPBOX_TIMEOUT_SECONDS = 5


class _ProviderUnavailable(Exception):
    """The provider could not answer; the next provider should be tried."""


class _RouteNotFound(Exception):
    """The provider answered: there is no route to this address."""


class _Route(NamedTuple):
    distance_m: float
    duration_text: str


def _get_json(url: str, params: dict, timeout: int, provider: str) -> dict:
    try:
        response = requests.get(url, params=params, timeout=timeout)
    except requests.RequestException as e:
        raise _ProviderUnavailable(f"{provider} request failed: {e}") from e

    if response.status_code >= 500:
        raise _ProviderUnavailable(f"{provider} returned HTTP {response.status_code}")

    try:
        return response.json()
    except ValueError as e:
        raise _ProviderUnavailable(f"{provider} returned a non-JSON response") from e


def _google_route(destination: str) -> _Route:
    if not settings.GOOGLE_MAPS_API_KEY:
        raise _ProviderUnavailable("GOOGLE_MAPS_API_KEY not set")

    data = _get_json(
        GOOGLE_DISTANCE_MATRIX_URL,
        {
            "origins": settings.OFFICE_ADDRESS,
            "destinations": destination,
            "key": settings.GOOGLE_MAPS_API_KEY,
            "units": "metric",
        },
        GOOGLE_TIMEOUT_SECONDS,
        "Google",
    )

    if data.get("status") != "OK":
        raise _ProviderUnavailable(f"Google API error: {data.get('status')}")

    try:
        element = data["rows"][0]["elements"][0]
        if element.get("status") != "OK":
            raise _RouteNotFound(f"Route not found: {element.get('status')}")
        return _Route(
            distance_m=element["distance"]["value"],
            duration_text=element["duration"]["text"],
        )
    except (KeyError, IndexError, TypeError) as e:
        raise _ProviderUnavailable(f"Google returned an invalid response: {e}") from e


def _mapbox_geocode(address: str, proximity: tuple[float, float] | None = None) -> tuple[float, float]:
    params = {
        "q": address,
        "access_token": settings.MAPBOX_ACCESS_TOKEN,
        "limit": 1,
    }
    if proximity:
        params["proximity"] = f"{proximity[0]},{proximity[1]}"

    data = _get_json(MAPBOX_GEOCODE_URL, params, MAPBOX_TIMEOUT_SECONDS, "Mapbox geocoding")

    features = data.get("features")
    if features is None:
        raise _ProviderUnavailable(f"Mapbox geocoding error: {data.get('message') or data}")
    if not features:
        raise _RouteNotFound(f"Address not found: {address}")

    try:
        lon, lat = features[0]["geometry"]["coordinates"][:2]
        return float(lon), float(lat)
    except (KeyError, IndexError, TypeError, ValueError) as e:
        raise _ProviderUnavailable(f"Mapbox geocoding returned an invalid response: {e}") from e


def _format_duration(seconds: float) -> str:
    """Match Google's duration text, e.g. "1 hour 23 mins"."""
    total_minutes = max(1, round(seconds / 60))
    hours, minutes = divmod(total_minutes, 60)
    parts = []
    if hours:
        parts.append(f"{hours} hour{'s' if hours != 1 else ''}")
    if minutes:
        parts.append(f"{minutes} min{'s' if minutes != 1 else ''}")
    return " ".join(parts)


def _mapbox_route(destination: str) -> _Route:
    if not settings.MAPBOX_ACCESS_TOKEN:
        raise _ProviderUnavailable("MAPBOX_ACCESS_TOKEN not set")

    # Not cached: the fallback is rare, and Mapbox's terms restrict storing
    # temporary geocoding results.
    office = _mapbox_geocode(settings.OFFICE_ADDRESS)
    dest = _mapbox_geocode(destination, proximity=office)

    coords = f"{office[0]},{office[1]};{dest[0]},{dest[1]}"
    data = _get_json(
        f"{MAPBOX_DIRECTIONS_URL}/{coords}",
        {"access_token": settings.MAPBOX_ACCESS_TOKEN, "overview": "false"},
        MAPBOX_TIMEOUT_SECONDS,
        "Mapbox directions",
    )

    code = data.get("code")
    if code in ("NoRoute", "NoSegment"):
        raise _RouteNotFound(f"Route not found: {code}")
    if code != "Ok":
        raise _ProviderUnavailable(f"Mapbox directions error: {code or data.get('message')}")

    try:
        route = data["routes"][0]
        return _Route(
            distance_m=route["distance"],
            duration_text=_format_duration(route["duration"]),
        )
    except (KeyError, IndexError, TypeError) as e:
        raise _ProviderUnavailable(f"Mapbox directions returned an invalid response: {e}") from e


def _lookup_route(destination: str) -> _Route:
    """
    Google first, Mapbox only if Google could not answer.

    A Google "no route / not found" answer is final: Mapbox geocoding is fuzzy and
    would return a best guess for a bad address, and that guess would become a
    billed travel charge.
    """
    try:
        return _google_route(destination)
    except _ProviderUnavailable as google_error:
        if not settings.MAPBOX_ACCESS_TOKEN:
            raise
        logger.warning(
            f"Google distance lookup unavailable for '{destination}' ({google_error}); "
            "falling back to Mapbox"
        )

    route = _mapbox_route(destination)
    logger.warning(f"Distance for '{destination}' served by Mapbox fallback")
    return route


def calculate_distance(destination: str) -> Decimal | None:
    """
    Calculate round trip distance from office to destination.

    Args:
        destination: The destination address

    Returns:
        Round trip distance in kilometers, or None if calculation fails
    """
    if not destination:
        logger.warning("No destination address provided for distance calculation")
        return None

    try:
        route = _lookup_route(destination)
    except _RouteNotFound as e:
        logger.warning(f"Distance lookup for '{destination}': {e}")
        return None
    except _ProviderUnavailable as e:
        logger.error(f"Distance lookup failed for '{destination}': {e}")
        return None

    round_trip_km = (route.distance_m / 1000) * 2
    return Decimal(str(math.ceil(round_trip_km)))


def get_distance_info(destination: str) -> dict:
    """
    Get detailed distance information from office to destination.

    Args:
        destination: The destination address string.

    Returns:
        On success, a dict with keys:
            - one_way_km (int): One-way distance in km (ceiling-rounded).
            - round_trip_km (int): Round-trip distance in km (one_way_km * 2, ceiling-rounded).
            - duration_one_way (str): Human-readable drive time, e.g. "1 hour 23 mins".
            - origin (str): The office address used as the origin.
            - destination (str): The destination address as passed in.

        On failure, a dict with a single key:
            - error (str): Description of what went wrong (no provider configured,
              address not found, network failure, etc.).
    """
    if not settings.GOOGLE_MAPS_API_KEY and not settings.MAPBOX_ACCESS_TOKEN:
        return {"error": "No distance provider configured (Google Maps or Mapbox)"}

    if not destination:
        return {"error": "No destination address provided"}

    try:
        route = _lookup_route(destination)
    except (_RouteNotFound, _ProviderUnavailable) as e:
        return {"error": str(e)}

    one_way_km = route.distance_m / 1000
    return {
        "one_way_km": math.ceil(one_way_km),
        "round_trip_km": math.ceil(one_way_km * 2),
        "duration_one_way": route.duration_text,
        "origin": settings.OFFICE_ADDRESS,
        "destination": destination,
    }
