"""
Home Depot material price lookup service, backed by SerpApi's engine=home_depot
search and cached in the DB to avoid hitting SerpApi on every keystroke.
"""
import logging
import re
from datetime import datetime, timedelta

import requests
from sqlmodel import Session, select, delete

from ..config import settings
from ..models.material_price_cache import MaterialPriceCache

logger = logging.getLogger(__name__)

SERPAPI_URL = "https://serpapi.com/search"

_NUMBER_RE = re.compile(r"[\d,]+\.?\d*")


def _normalize_query(query: str) -> str:
    """Lowercase + collapse whitespace so 'Drywall Screws' and 'drywall  screws'
    hit the same cache row."""
    return " ".join(query.strip().lower().split())


def _parse_price(raw: str | float | int | None) -> float | None:
    """Parse a SerpApi price value into a float. SerpApi sometimes returns a plain
    number instead of a "$X.XX" string, so numeric types are accepted as-is. Ranges
    like "$12.98 - $45.00" are resolved to their median, matching a single quoted
    product price."""
    if raw is None:
        return None
    if isinstance(raw, (int, float)):
        return float(raw)

    numbers = [float(n.replace(",", "")) for n in _NUMBER_RE.findall(raw)]
    if not numbers:
        return None
    if len(numbers) == 1:
        return numbers[0]

    return round((numbers[0] + numbers[1]) / 2, 2)


def _get_cached(session: Session, normalized_query: str, ttl_hours: int) -> list[MaterialPriceCache]:
    cutoff = datetime.utcnow() - timedelta(hours=ttl_hours)
    statement = (
        select(MaterialPriceCache)
        .where(MaterialPriceCache.query == normalized_query)
        .where(MaterialPriceCache.fetched_at >= cutoff)
    )
    return list(session.exec(statement).all())


def _fetch_from_serpapi(query: str) -> list[dict]:
    """Call SerpApi engine=home_depot. Returns [] on any failure/missing key -
    never raises, so a broken lookup never breaks the manager's estimate flow."""
    if not settings.SERPAPI_KEY:
        logger.warning("SERPAPI_KEY not set - skipping material price lookup")
        return []

    try:
        params = {
            "engine": "home_depot",
            "q": query,
            "api_key": settings.SERPAPI_KEY,
            "country": "ca",
        }
        response = requests.get(SERPAPI_URL, params=params, timeout=10)
        data = response.json()

        if "error" in data:
            logger.warning(f"SerpApi home_depot error for '{query}': {data['error']}")
            return []

        return data.get("products", [])

    except requests.RequestException as e:
        logger.error(f"SerpApi request failed for '{query}': {e}")
        return []
    except (KeyError, ValueError) as e:
        logger.error(f"SerpApi invalid response for '{query}': {e}")
        return []


def search_materials(session: Session, query: str, ttl_hours: int | None = None) -> list[MaterialPriceCache]:
    """
    Look up Home Depot materials matching `query`, using the DB cache when fresh
    and falling back to a live SerpApi call otherwise. Always returns a list
    (possibly empty) - never raises.
    """
    ttl_hours = ttl_hours if ttl_hours is not None else settings.MATERIAL_PRICE_CACHE_TTL_HOURS
    normalized = _normalize_query(query)
    if not normalized:
        return []

    cached = _get_cached(session, normalized, ttl_hours)
    if cached:
        return cached

    products = _fetch_from_serpapi(query)
    if not products:
        return []

    # Replace any stale rows for this exact query before inserting fresh ones,
    # so the table doesn't grow unbounded per repeated search of the same term.
    session.exec(delete(MaterialPriceCache).where(MaterialPriceCache.query == normalized))

    rows: list[MaterialPriceCache] = []
    for product in products[:20]:
        title = product.get("title")
        if not title:
            continue
        thumbnails = product.get("thumbnails") or []
        raw_price = product.get("price")
        row = MaterialPriceCache(
            query=normalized,
            product_name=title,
            price=str(raw_price) if raw_price is not None else None,
            price_value=_parse_price(raw_price),
            thumbnail=thumbnails[0] if thumbnails else None,
            product_url=product.get("link"),
            source="home_depot",
        )
        session.add(row)
        rows.append(row)

    session.commit()
    for row in rows:
        session.refresh(row)

    return rows
