import asyncio
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import httpx

logger = logging.getLogger(__name__)


async def get_open_meteo_weather(lat: float, lon: float) -> Optional[Dict[str, Any]]:
    url = "https://api.open-meteo.com/v1/forecast"
    params = {
        "latitude": lat,
        "longitude": lon,
        "current": (
            "temperature_2m,apparent_temperature,relative_humidity_2m,precipitation,"
            "rain,weather_code,wind_speed_10m,wind_direction_10m,wind_gusts_10m,"
            "surface_pressure"
        ),
        "hourly": (
            "temperature_2m,apparent_temperature,relative_humidity_2m,"
            "precipitation_probability,precipitation,wind_speed_10m,"
            "wind_direction_10m,wind_gusts_10m,weather_code"
        ),
        "daily": (
            "temperature_2m_max,temperature_2m_min,precipitation_probability_max,"
            "precipitation_sum,weather_code,wind_speed_10m_max,wind_gusts_10m_max"
        ),
        "forecast_days": 7,
        "timezone": "auto",
    }

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            forecast_response, air_quality = await asyncio.gather(
                client.get(url, params=params),
                _get_air_quality(client, lat, lon),
            )
            forecast_response.raise_for_status()
            data = forecast_response.json()
            return _parse_weather_data(data, air_quality)
    except (httpx.HTTPError, ValueError, KeyError) as exc:
        logger.warning("Open-Meteo forecast request failed: %s", type(exc).__name__)
        return None


async def _get_air_quality(client: httpx.AsyncClient, lat: float, lon: float) -> Optional[Dict[str, Any]]:
    try:
        response = await client.get(
            "https://air-quality-api.open-meteo.com/v1/air-quality",
            params={
                "latitude": lat,
                "longitude": lon,
                "current": "us_aqi,european_aqi,pm2_5,pm10",
                "timezone": "auto",
            },
        )
        response.raise_for_status()
        data = response.json()
        current = data.get("current") or {}
        if not current:
            return None
        aqi = current.get("us_aqi")
        source = "Open-Meteo Air Quality API (US AQI)"
        if aqi is None:
            aqi = current.get("european_aqi")
            source = "Open-Meteo Air Quality API (European AQI)"
        if aqi is None:
            return None
        return {
            "value": aqi,
            "category": _aqi_category(aqi, source.endswith("US AQI")),
            "source": source,
            "timestamp": current.get("time"),
            "pm2_5": current.get("pm2_5"),
            "pm10": current.get("pm10"),
        }
    except (httpx.HTTPError, ValueError, KeyError) as exc:
        logger.info("Open-Meteo air quality unavailable: %s", type(exc).__name__)
        return None


def _aqi_category(value: float, is_us: bool) -> str:
    if is_us:
        if value <= 50:
            return "Good"
        if value <= 100:
            return "Moderate"
        if value <= 150:
            return "Unhealthy for sensitive groups"
        if value <= 200:
            return "Unhealthy"
        if value <= 300:
            return "Very unhealthy"
        return "Hazardous"
    if value <= 20:
        return "Good"
    if value <= 40:
        return "Fair"
    if value <= 60:
        return "Moderate"
    if value <= 80:
        return "Poor"
    if value <= 100:
        return "Very poor"
    return "Extremely poor"


async def search_weather_locations(query: str) -> List[Dict[str, Any]]:
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(
                "https://geocoding-api.open-meteo.com/v1/search",
                params={"name": query, "count": 8, "language": "en", "format": "json"},
            )
            response.raise_for_status()
            results = response.json().get("results") or []
            return [
                {
                    "id": item.get("id"),
                    "name": item.get("name"),
                    "admin1": item.get("admin1"),
                    "country": item.get("country"),
                    "latitude": item.get("latitude"),
                    "longitude": item.get("longitude"),
                }
                for item in results
                if item.get("name") and item.get("latitude") is not None and item.get("longitude") is not None
            ]
    except (httpx.HTTPError, ValueError, KeyError) as exc:
        logger.warning("Open-Meteo geocoding request failed: %s", type(exc).__name__)
        raise


def _parse_weather_data(
    data: Dict[str, Any], air_quality: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    if not isinstance(data, dict):
        raise ValueError("Weather provider returned an invalid response.")
    current = data.get("current", {})
    hourly = data.get("hourly", {})
    daily = data.get("daily", {})
    if (
        not isinstance(current, dict)
        or not isinstance(current.get("temperature_2m"), (int, float))
    ):
        raise ValueError("Weather provider response did not include current temperature.")
    if not isinstance(hourly, dict) or not isinstance(daily, dict):
        raise ValueError("Weather provider returned incomplete forecast data.")

    current_parsed = {
        "time": current.get("time"),
        "temperature": current.get("temperature_2m"),
        "apparent_temperature": current.get("apparent_temperature"),
        "humidity": current.get("relative_humidity_2m"),
        "precipitation": current.get("precipitation"),
        "weather_code": current.get("weather_code"),
        "wind_speed": current.get("wind_speed_10m"),
        "wind_direction": current.get("wind_direction_10m"),
        "wind_gusts": current.get("wind_gusts_10m"),
        "pressure": current.get("surface_pressure"),
        "rain": current.get("rain"),
    }

    hourly_times = hourly.get("time", [])
    current_time = current.get("time")
    start_hour = next(
        (index for index, hour_time in enumerate(hourly_times) if current_time and hour_time >= current_time),
        0,
    )
    hourly_temps = hourly.get("temperature_2m", [])
    hourly_apparent = hourly.get("apparent_temperature", [])
    hourly_humidities = hourly.get("relative_humidity_2m", [])
    hourly_rain_probs = hourly.get("precipitation_probability", [])
    hourly_precips = hourly.get("precipitation", [])
    hourly_wind_speeds = hourly.get("wind_speed_10m", [])
    hourly_wind_directions = hourly.get("wind_direction_10m", [])
    hourly_wind_gusts = hourly.get("wind_gusts_10m", [])
    hourly_codes = hourly.get("weather_code", [])

    hourly_parsed: List[Dict[str, Any]] = []
    hour_indices = range(start_hour, min(len(hourly_times), start_hour + 24))
    for i in hour_indices:
        hourly_parsed.append({
            "time": hourly_times[i],
            "temp": _value_at(hourly_temps, i),
            "apparent_temperature": _value_at(hourly_apparent, i),
            "humidity": _value_at(hourly_humidities, i),
            "rain_prob": _value_at(hourly_rain_probs, i),
            "precipitation": _value_at(hourly_precips, i),
            "wind_speed": _value_at(hourly_wind_speeds, i),
            "wind_direction": _value_at(hourly_wind_directions, i),
            "wind_gusts": _value_at(hourly_wind_gusts, i),
            "weather_code": _value_at(hourly_codes, i),
        })

    daily_dates = daily.get("time", [])
    daily_max = daily.get("temperature_2m_max", [])
    daily_min = daily.get("temperature_2m_min", [])
    daily_rain_probs = daily.get("precipitation_probability_max", [])
    daily_precip = daily.get("precipitation_sum", [])
    daily_codes = daily.get("weather_code", [])
    daily_wind_speeds = daily.get("wind_speed_10m_max", [])
    daily_wind_gusts = daily.get("wind_gusts_10m_max", [])

    daily_parsed: List[Dict[str, Any]] = []
    max_days = min(7, len(daily_dates))
    for i in range(max_days):
        daily_parsed.append({
            "date": daily_dates[i],
            "temp_max": _value_at(daily_max, i),
            "temp_min": _value_at(daily_min, i),
            "rain_prob_max": _value_at(daily_rain_probs, i),
            "precipitation_sum": _value_at(daily_precip, i),
            "weather_code": _value_at(daily_codes, i),
            "wind_speed_max": _value_at(daily_wind_speeds, i),
            "wind_gusts_max": _value_at(daily_wind_gusts, i),
        })

    return {
        "current": current_parsed,
        "hourly": hourly_parsed,
        "daily": daily_parsed,
        "air_quality": air_quality,
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "timezone": data.get("timezone"),
        "is_demo": False,
        "data_source": "Live forecast from Open-Meteo (open-meteo.com)",
    }


def _value_at(values: list, index: int) -> Optional[Any]:
    return values[index] if index < len(values) else None


def generate_crop_advisory(weather: Dict[str, Any], crop: str, stage: str) -> Dict[str, Any]:
    current = weather.get("current", {})
    hourly = weather.get("hourly", [])
    daily = weather.get("daily", [])

    risk_factors: List[str] = []
    advisories: List[str] = []

    temp = current.get("temperature")
    humidity = current.get("humidity")
    wind_speed = current.get("wind_speed")
    rain = current.get("rain")

    rain_probabilities = [
        h.get("rain_prob") for h in hourly[:12]
        if isinstance(h.get("rain_prob"), (int, float))
    ] + [
        d.get("rain_prob_max") for d in daily[:3]
        if isinstance(d.get("rain_prob_max"), (int, float))
    ]
    overall_rain_prob = max(rain_probabilities) if rain_probabilities else None

    if overall_rain_prob is not None and overall_rain_prob > 70:
        risk_factors.append("heavy_rain_expected")
        advisories.append(
            "Avoid pesticide spraying before rainfall. Check field drainage to prevent waterlogging."
        )
        advisories.append(
            "Ensure proper drainage channels are clear to avoid crop damage from stagnant water."
        )
    elif overall_rain_prob is not None and overall_rain_prob > 40:
        advisories.append(
            "Light rain expected. Plan irrigation activities accordingly and delay spraying if possible."
        )

    stage_lower = stage.lower() if stage else ""
    flowering = "flower" in stage_lower or "bloom" in stage_lower or "फुल" in stage_lower or "पुष्प" in stage_lower
    fruiting = "fruit" in stage_lower or "harvest" in stage_lower or "फळ" in stage_lower or "पिक" in stage_lower

    if temp is not None and temp > 35 and (flowering or fruiting):
        risk_factors.append("high_temperature_stress")
        advisories.append(
            "High temperature may affect flowering and fruit setting. Consider irrigation in early morning or late evening."
        )
        advisories.append(
            "Mulching around crop base can help retain soil moisture during high temperatures."
        )
    elif temp is not None and temp > 40:
        risk_factors.append("extreme_heat")
        advisories.append(
            "Extreme heat conditions detected. Ensure adequate irrigation and consider shade nets if feasible."
        )

    if humidity is not None and humidity < 40:
        risk_factors.append("low_humidity")
        advisories.append(
            "Low humidity conditions. Monitor closely for pest attacks, especially thrips and mites."
        )
        advisories.append(
            "Light irrigation or sprinkling can help maintain micro-climate humidity."
        )

    if wind_speed is not None and wind_speed > 20 and flowering:
        risk_factors.append("strong_winds_pollination")
        advisories.append(
            "Strong winds may affect pollination. Consider hand pollination or windbreaks for high-value crops."
        )
    elif wind_speed is not None and wind_speed > 30:
        risk_factors.append("strong_winds")
        advisories.append(
            "Strong winds expected. Secure any temporary structures and monitor for lodging in tall crops."
        )

    if rain is not None and rain > 5:
        advisories.append(
            "Rainfall detected. Check for standing water and postpone any chemical applications."
        )

    if not advisories:
        advisories.append(
            "Available weather data shows no triggered advisory rule; continue checking local field conditions."
        )

    if crop:
        crop_lower = crop.lower()
        if "rice" in crop_lower or "पाभा" in crop_lower or "चावल" in crop_lower or "तांदूळ" in crop_lower:
            if temp is not None and temp > 35 and flowering:
                advisories.append(
                    f"For {crop}: Maintain adequate water level (5-7 cm) during flowering stage to prevent sterility."
                )
        elif "cotton" in crop_lower or "कापूस" in crop_lower or "सूती" in crop_lower:
            if humidity is not None and humidity < 40:
                advisories.append(
                    f"For {crop}: Dry conditions favor pink bollworm. Install pheromone traps and monitor regularly."
                )
        elif "tomato" in crop_lower or "टोमॅटो" in crop_lower or "टमाटर" in crop_lower:
            if overall_rain_prob is not None and overall_rain_prob > 60:
                advisories.append(
                    f"For {crop}: High rain risk for late blight. Apply prophylactic fungicide spray if not done recently."
                )

    advisory_text = " ".join(advisories)

    weather_summary = (
        f"Current: {temp if temp is not None else 'unavailable'}°C, "
        f"Humidity: {humidity if humidity is not None else 'unavailable'}%, "
        f"Wind: {wind_speed if wind_speed is not None else 'unavailable'} km/h. "
        f"Rain probability next 24h: {overall_rain_prob if overall_rain_prob is not None else 'unavailable'}%. "
        f"Crop: {crop or 'Not specified'}, Stage: {stage or 'Not specified'}."
    )

    return {
        "advisories": advisories,
        "advisory_text": advisory_text,
        "weather_summary": weather_summary,
        "risk_factors": risk_factors,
    }
