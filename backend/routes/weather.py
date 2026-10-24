import httpx
from fastapi import APIRouter, Header, HTTPException, Query, status
from typing import Optional

from services.weather_service import (
    get_open_meteo_weather,
    generate_crop_advisory,
    search_weather_locations,
)
from services.ai_service import AIProviderUnavailable, translate_texts
from services.localization import localized_message, resolve_language

router = APIRouter()


@router.get("/search")
async def search_locations(query: str = Query(..., min_length=2, max_length=120)):
    try:
        results = await search_weather_locations(query.strip())
    except (httpx.HTTPError, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Location search is temporarily unavailable. Please try again.",
        ) from exc
    return {"results": results}


async def _get_localized_advisory(weather, crop: str, stage: str, language: str):
    advisory = generate_crop_advisory(weather, crop, stage)
    if not isinstance(advisory, dict):
        return advisory
    result = dict(advisory)
    texts = result.get("advisories", [])
    if language != "en" and texts:
        try:
            translated = await translate_texts(texts, language)
        except AIProviderUnavailable as exc:
            key = (
                "translation_quota_unavailable"
                if exc.reason in {"quota_exceeded", "openai_quota_exceeded"}
                else "translation_unavailable"
            )
            result["advisories"] = [localized_message(language, key)]
        else:
            result["advisories"] = translated
            if translated is None:
                result["advisories"] = [
                    localized_message(language, "translation_unavailable")
                ]
    return result


@router.get("")
async def get_weather_combined(
    lat: float = Query(..., ge=-90.0, le=90.0, description="Latitude"),
    lon: float = Query(..., ge=-180.0, le=180.0, description="Longitude"),
    crop: Optional[str] = Query("", description="Crop name for advisory"),
    stage: Optional[str] = Query("", description="Crop growth stage for advisory"),
    x_language: Optional[str] = Header(default="en", alias="X-Language"),
):
    try:
        language = resolve_language(x_language)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=localized_message("en", "invalid_language"),
        )

    weather = await get_open_meteo_weather(lat, lon)
    if weather is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=localized_message(language, "weather_unavailable"),
        )

    advisory = await _get_localized_advisory(weather, crop or "", stage or "", language)

    return {
        "latitude": lat,
        "longitude": lon,
        "current": weather.get("current"),
        "hourly": weather.get("hourly"),
        "forecast": weather.get("daily"),
        "air_quality": weather.get("air_quality"),
        "fetched_at": weather.get("fetched_at"),
        "timezone": weather.get("timezone"),
        "advisory": advisory.get("advisories") if isinstance(advisory, dict) else advisory,
        "crop": crop,
        "stage": stage,
        "is_demo": bool(weather.get("is_demo")),
        "data_source": weather.get("data_source") or (
            "Live forecast from Open-Meteo (open-meteo.com)"
            if not weather.get("is_demo")
            else "Estimated Demo Weather (Offline / API Unavailable) - NOT live data"
        )
    }


@router.get("/current")
async def get_current_weather(
    lat: float = Query(..., ge=-90.0, le=90.0, description="Latitude"),
    lon: float = Query(..., ge=-180.0, le=180.0, description="Longitude"),
    x_language: Optional[str] = Header(default="en", alias="X-Language"),
):
    try:
        language = resolve_language(x_language)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=localized_message("en", "invalid_language"),
        )

    weather = await get_open_meteo_weather(lat, lon)
    if weather is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=localized_message(language, "weather_unavailable"),
        )
    return {"latitude": lat, "longitude": lon, **weather}


@router.get("/advisory")
async def get_weather_advisory(
    lat: float = Query(..., ge=-90.0, le=90.0, description="Latitude"),
    lon: float = Query(..., ge=-180.0, le=180.0, description="Longitude"),
    crop: str = Query("", description="Crop name"),
    stage: str = Query("", description="Crop growth stage"),
    x_language: Optional[str] = Header(default="en", alias="X-Language"),
):
    try:
        language = resolve_language(x_language)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=localized_message("en", "invalid_language"),
        )

    weather = await get_open_meteo_weather(lat, lon)
    if weather is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=localized_message(language, "weather_unavailable"),
        )

    advisory = await _get_localized_advisory(weather, crop, stage, language)
    return {
        "latitude": lat,
        "longitude": lon,
        "crop": crop,
        "stage": stage,
        **advisory,
        "weather": weather["current"],
    }
