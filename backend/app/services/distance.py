"""
Distance calculation service using Google Maps API
"""
import logging
import math
import requests
from decimal import Decimal

from ..config import settings

logger = logging.getLogger(__name__)


def calculate_distance(destination: str) -> Decimal | None:
    """
    Calculate round trip distance from office to destination using Google Maps API.

    Args:
        destination: The destination address

    Returns:
        Round trip distance in kilometers, or None if calculation fails
    """
    if not settings.GOOGLE_MAPS_API_KEY:
        logger.warning("GOOGLE_MAPS_API_KEY not set — skipping distance calculation")
        return None

    if not destination:
        logger.warning("No destination address provided for distance calculation")
        return None

    try:
        url = "https://maps.googleapis.com/maps/api/distancematrix/json"
        params = {
            "origins": settings.OFFICE_ADDRESS,
            "destinations": destination,
            "key": settings.GOOGLE_MAPS_API_KEY,
            "units": "metric",
        }

        response = requests.get(url, params=params, timeout=10)
        data = response.json()

        if data.get("status") == "OK":
            element = data["rows"][0]["elements"][0]
            if element.get("status") == "OK":
                distance_m = element["distance"]["value"]
                round_trip_km = (distance_m / 1000) * 2
                return Decimal(str(math.ceil(round_trip_km)))
            else:
                logger.warning(f"Distance API element error for '{destination}': {element.get('status')}")
        else:
            logger.warning(f"Distance API error for '{destination}': {data.get('status')}")

    except requests.RequestException as e:
        logger.error(f"Distance API request failed for '{destination}': {e}")
    except (KeyError, IndexError) as e:
        logger.error(f"Distance API invalid response for '{destination}': {e}")

    return None


def get_distance_info(destination: str) -> dict:
    """
    Get detailed distance information including duration.

    Returns dict with distance_km, duration_text, or error info.
    """
    if not settings.GOOGLE_MAPS_API_KEY:
        return {"error": "Google Maps API key not configured"}

    if not destination:
        return {"error": "No destination address provided"}

    try:
        url = "https://maps.googleapis.com/maps/api/distancematrix/json"
        params = {
            "origins": settings.OFFICE_ADDRESS,
            "destinations": destination,
            "key": settings.GOOGLE_MAPS_API_KEY,
            "units": "metric",
        }

        response = requests.get(url, params=params, timeout=10)
        data = response.json()

        if data.get("status") == "OK":
            element = data["rows"][0]["elements"][0]
            if element.get("status") == "OK":
                distance_m = element["distance"]["value"]
                duration_text = element["duration"]["text"]
                one_way_km = distance_m / 1000

                return {
                    "one_way_km": math.ceil(one_way_km),
                    "round_trip_km": math.ceil(one_way_km * 2),
                    "duration_one_way": duration_text,
                    "origin": settings.OFFICE_ADDRESS,
                    "destination": destination,
                }
            else:
                return {"error": f"Route not found: {element.get('status')}"}
        else:
            return {"error": f"API error: {data.get('status')}"}

    except requests.RequestException as e:
        return {"error": f"Request failed: {str(e)}"}
    except (KeyError, IndexError) as e:
        return {"error": f"Invalid response: {str(e)}"}
