import asyncio
from collections import OrderedDict
from copy import deepcopy
from datetime import datetime, timezone
import logging
from time import monotonic
from typing import Optional

from fastapi import APIRouter, HTTPException, Query, status

from services.market_service import (
    _get_markets_for_district,
    _market_key,
    fetch_external_market_prices,
    generate_demo_market_prices,
)

logger = logging.getLogger(__name__)
router = APIRouter()

_CACHE_TTL_SECONDS = 300
_CACHE_MAX_AGE_SECONDS = 86_400
_CACHE_MAX_ENTRIES = 256
_EXTERNAL_FETCH_TIMEOUT_SECONDS = 4
_price_cache: OrderedDict[tuple[str, str, str], dict] = OrderedDict()
_refresh_tasks: dict[tuple[str, str, str], asyncio.Task] = {}


@router.get("/markets")
async def get_markets(district: str = Query(..., min_length=2, description="District name")):
    return _get_markets_for_district(district)


def _cache_key(crop: str, district: Optional[str], market: Optional[str]):
    return (
        " ".join(crop.casefold().split()),
        " ".join((district or "").casefold().split()),
        " ".join((market or "").casefold().split()),
    )


def _normalize_prices(data, crop: str, market: Optional[str], district_markets: list[str], external_data):
    source_markets = []
    if isinstance(data, dict):
        if isinstance(data.get("markets"), list) and data["markets"]:
            source_markets = list(data["markets"])
        elif isinstance(data.get("prices"), list) and data["prices"]:
            source_markets = list(data["prices"])

    normalized_prices = []
    for market_data in source_markets:
        market_name = (
            market_data.get("market")
            or market_data.get("name")
            or market_data.get("market_name")
            or "Unknown Market"
        )
        if market and _market_key(str(market_name)) != _market_key(market):
            continue
        if market:
            market_name = next(
                name for name in district_markets
                if _market_key(name) == _market_key(market)
            )
        normalized_prices.append({
            "market": market_name,
            "name": market_name,
            "min_price": float(market_data.get("min_price", market_data.get("minPrice", 0)) or 0),
            "max_price": float(market_data.get("max_price", market_data.get("maxPrice", 0)) or 0),
            "modal_price": float(
                market_data.get(
                    "modal_price",
                    market_data.get("modalPrice", market_data.get("average_price", 0)),
                ) or 0
            ),
            "arrival": float(
                market_data.get(
                    "arrival",
                    market_data.get("arrivals", market_data.get("arrived_qty", 100)),
                ) or 100
            ),
            "date": (
                market_data.get("date")
                or market_data.get("arrival_date")
                or market_data.get("reporting_date", "")
            ),
        })

    result = dict(data) if isinstance(data, dict) else {}
    result["markets"] = normalized_prices
    result["prices"] = normalized_prices
    result["crop"] = (data.get("crop") if isinstance(data, dict) else None) or crop
    if "is_demo" not in result:
        result["is_demo"] = not external_data
    if "data_source" not in result or not result["data_source"]:
        result["data_source"] = (
            "Estimated Market Prices (Demo) - For reference only, NOT live APMC data"
            if result["is_demo"]
            else "Market prices"
        )
    if "unit" not in result or not result["unit"]:
        result["unit"] = "₹/Quintal"
    return result


async def _refresh_prices(
    key: tuple[str, str, str],
    crop: str,
    district: Optional[str],
    market: Optional[str],
    district_markets: list[str],
):
    started = monotonic()
    cached = _price_cache.get(key)
    try:
        try:
            try:
                external_data = (
                    await asyncio.wait_for(
                        fetch_external_market_prices(crop, district, market),
                        timeout=_EXTERNAL_FETCH_TIMEOUT_SECONDS,
                    )
                    if district else None
                )
            except asyncio.TimeoutError:
                logger.warning(
                    "External market price source exceeded %.1f seconds",
                    _EXTERNAL_FETCH_TIMEOUT_SECONDS,
                )
                external_data = None
            if external_data is None and cached and not cached["data"].get("is_demo"):
                logger.info("Market prices refresh retained stale external data (%.1f ms)", (monotonic() - started) * 1000)
                return None

            data = external_data or generate_demo_market_prices(crop, district, market)
            result = _normalize_prices(data, crop, market, district_markets, external_data)
            result["last_updated"] = datetime.now(timezone.utc).isoformat()
            _price_cache[key] = {"data": result, "stored_at": monotonic()}
            _price_cache.move_to_end(key)
            while len(_price_cache) > _CACHE_MAX_ENTRIES:
                _price_cache.popitem(last=False)
            return result
        except Exception:
            logger.exception("Market price refresh failed")
            if cached:
                return None
            try:
                data = generate_demo_market_prices(crop, district, market)
                result = _normalize_prices(data, crop, market, district_markets, None)
                result["last_updated"] = datetime.now(timezone.utc).isoformat()
                _price_cache[key] = {"data": result, "stored_at": monotonic()}
                return result
            except ValueError:
                return None
    finally:
        _refresh_tasks.pop(key, None)


def _start_refresh(key, crop, district, market, district_markets):
    task = _refresh_tasks.get(key)
    if task is None or task.done():
        task = asyncio.create_task(
            _refresh_prices(key, crop, district, market, district_markets)
        )
        _refresh_tasks[key] = task
    return task


@router.get("/prices")
async def get_market_prices(
    crop: str = Query(..., min_length=2, description="Crop name"),
    district: Optional[str] = Query(None, description="District name (optional)"),
    location: Optional[str] = Query(None, description="Alias for district (optional)"),
    market: Optional[str] = Query(None, min_length=2, description="Market name (optional)"),
):
    started = monotonic()
    resolved_district = district or location
    if market and not resolved_district:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A district is required when selecting a market",
        )

    district_markets = _get_markets_for_district(resolved_district or "")
    canonical_market = None
    if market:
        canonical_market = next(
            (
                name for name in district_markets
                if _market_key(name) == _market_key(market)
            ),
            None,
        )
        if not canonical_market:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"{market} is not listed in {resolved_district}",
            )

    key = _cache_key(crop, resolved_district, canonical_market)
    cached = _price_cache.get(key)
    if cached:
        age = monotonic() - cached["stored_at"]
        if age <= _CACHE_TTL_SECONDS:
            _price_cache.move_to_end(key)
            result = deepcopy(cached["data"])
            result["cache"] = {"status": "hit", "stale": False, "last_updated": result["last_updated"]}
            logger.info("Market prices cache hit in %.1f ms", (monotonic() - started) * 1000)
            return result
        if age <= _CACHE_MAX_AGE_SECONDS:
            _start_refresh(key, crop, resolved_district, canonical_market, district_markets)
            result = deepcopy(cached["data"])
            result["cache"] = {"status": "stale", "stale": True, "last_updated": result["last_updated"]}
            logger.info("Market prices stale cache served in %.1f ms", (monotonic() - started) * 1000)
            return result

    task = _start_refresh(key, crop, resolved_district, canonical_market, district_markets)
    try:
        result = await asyncio.shield(task)
    except Exception:
        logger.exception("Market price lookup failed")
        if cached:
            result = deepcopy(cached["data"])
            result["cache"] = {"status": "stale", "stale": True, "last_updated": result.get("last_updated")}
            return result
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Market prices are temporarily unavailable. Please try again.",
        )

    if result is None:
        cached = _price_cache.get(key)
        if cached:
            result = deepcopy(cached["data"])
            result["cache"] = {"status": "stale", "stale": True, "last_updated": result.get("last_updated")}
            return result
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Market prices are temporarily unavailable. Please try again.",
        )

    response = deepcopy(result)
    response["cache"] = {"status": "miss", "stale": False, "last_updated": result["last_updated"]}
    logger.info("Market prices cache miss completed in %.1f ms", (monotonic() - started) * 1000)
    return response
