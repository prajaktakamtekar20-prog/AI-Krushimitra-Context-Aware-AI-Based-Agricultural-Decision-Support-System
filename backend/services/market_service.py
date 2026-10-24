import httpx
import logging
import random
from datetime import date
from typing import Dict, Any, List, Optional


BASE_PRICES: Dict[str, Dict[str, float]] = {
    "tomato": {"min": 25.0, "max": 60.0, "unit": "kg"},
    "onion": {"min": 20.0, "max": 45.0, "unit": "kg"},
    "potato": {"min": 18.0, "max": 40.0, "unit": "kg"},
    "rice": {"min": 32.0, "max": 55.0, "unit": "kg"},
    "paddy": {"min": 20.0, "max": 38.0, "unit": "kg"},
    "wheat": {"min": 28.0, "max": 45.0, "unit": "kg"},
    "sugarcane": {"min": 350.0, "max": 420.0, "unit": "quintal"},
    "grapes": {"min": 60.0, "max": 150.0, "unit": "kg"},
    "cotton": {"min": 6500.0, "max": 8500.0, "unit": "quintal"},
    "soybean": {"min": 40.0, "max": 65.0, "unit": "kg"},
    "maize": {"min": 22.0, "max": 40.0, "unit": "kg"},
    "tur": {"min": 80.0, "max": 130.0, "unit": "kg"},
    "moong": {"min": 90.0, "max": 150.0, "unit": "kg"},
    "groundnut": {"min": 55.0, "max": 90.0, "unit": "kg"},
    "chilli": {"min": 80.0, "max": 180.0, "unit": "kg"},
    "bajra": {"min": 20.0, "max": 35.0, "unit": "kg"},
    "jowar": {"min": 22.0, "max": 38.0, "unit": "kg"},
}

DISTRICT_MARKETS: Dict[str, List[str]] = {
    "kolhapur": ["Kapiltirth Market", "Shahupuri Market", "Kolhapur APMC", "Laxmipuri Market"],
    "sangli": ["Sangli Market", "Miraj Market", "Tasgaon Market", "Islampur Market", "Vita Market"],
    "satara": ["Satara Market", "Karad Market", "Phaltan Market", "Wai Market", "Man Market"],
    "ratnagiri": ["Ratnagiri APMC", "Chiplun APMC", "Khed APMC", "Dapoli APMC", "Rajapur APMC"],
    "sindhudurg": ["Sawantwadi APMC", "Malvan APMC", "Vengurla APMC", "Kudal APMC", "Sindhudurg APMC"],
    "pune": ["Pune APMC (Market Yard)", "Pimpri-Chinchwad APMC", "Baramati APMC", "Junnar APMC", "Indapur APMC"],
    "mumbai": ["Navi Mumbai APMC (Vashi)", "Mumbai Wholesale Market", "Bhiwandi APMC", "Thane APMC", "Kalyan APMC"],
    "nashik": ["Nashik APMC", "Sinnar APMC", "Malegaon APMC", "Niphad APMC"],
    "nagpur": ["Nagpur APMC"],
    "aurangabad": ["Aurangabad APMC", "Paithan APMC", "Gangapur APMC", "Vaijapur APMC"],
    "ahmednagar": ["Ahmednagar APMC", "Shrirampur APMC", "Rahuri APMC", "Sangamner APMC", "Pathardi APMC"],
}


def _get_crop_key(crop_name: str) -> str:
    crop_lower = crop_name.lower().strip()
    for key in BASE_PRICES:
        if key in crop_lower:
            return key
    for key in BASE_PRICES:
        if crop_lower in key:
            return key
    return "other"


def _market_key(market_name: str) -> str:
    key = "".join(character for character in market_name.casefold() if character.isalnum())
    for suffix in ("market", "apmc", "mandi"):
        if key.endswith(suffix):
            return key[:-len(suffix)]
    return key


def _get_markets_for_district(district: str) -> List[str]:
    if not district:
        return []
    d_lower = district.lower().strip()
    return DISTRICT_MARKETS.get(d_lower, [f"{district.strip().title()} APMC"])


async def fetch_external_market_prices(
    crop: str,
    district: Optional[str] = None,
    market: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    crop_key = _get_crop_key(crop)
    crop_key_for_api = crop
    state = "Maharashtra"
    district_name = district or ""

    apis_to_try = [
        (
            f"https://api.data.gov.in/resource/9ef84268-d588-465a-a308-a864a43d0070",
            {
                "api-key": "579b464db66ec23bdd000c701dd0cbf8",
                "format": "json",
                "filters[state]": state,
                "filters[district]": district_name,
                "filters[commodity]": crop_key_for_api,
                "limit": 100,
            },
        ),
    ]

    for url, params in apis_to_try:
        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(3.0, connect=1.5)) as client:
                response = await client.get(url, params=params)
                if response.status_code == 200:
                    data = response.json()
                    if "records" in data and len(data["records"]) > 0:
                        return _parse_external_prices(data["records"], crop, district, market)
        except (httpx.HTTPError, ValueError) as e:
            logging.getLogger(__name__).warning(
                "External market API request failed (%s).", type(e).__name__
            )
            continue

    return None


def _parse_external_prices(
    records: List[Dict[str, Any]],
    crop: str,
    district: Optional[str],
    market: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    markets: List[Dict[str, Any]] = []
    for rec in records if market else records[:5]:
        try:
            min_price = float(rec.get("min_price", 0) or rec.get("Min_x0020_Price", 0) or 0)
            max_price = float(rec.get("max_price", 0) or rec.get("Max_x0020_Price", 0) or 0)
            modal_price = float(rec.get("modal_price", 0) or rec.get("Modal_x0020_Price", 0) or 0)
            arrival = float(rec.get("arrival_date", 100) or rec.get("Arrival_x0020_Date", 100) or 100)
            market_name = rec.get("market", rec.get("Market", rec.get("market_center", "Unknown Market")))
            if market and _market_key(str(market_name)) != _market_key(market):
                continue
            price_date = rec.get("arrival_date", date.today().isoformat())

            if min_price == 0 and modal_price > 0:
                min_price = modal_price * 0.85
            if max_price == 0 and modal_price > 0:
                max_price = modal_price * 1.15
            if modal_price == 0 and (min_price > 0 or max_price > 0):
                modal_price = (min_price + max_price) / 2

            markets.append({
                "name": str(market_name).title(),
                "min_price": round(min_price, 2),
                "max_price": round(max_price, 2),
                "modal_price": round(modal_price, 2),
                "arrival": round(arrival, 1),
                "date": str(price_date),
            })
        except (ValueError, TypeError):
            continue

    if not markets:
        return None

    markets = markets[:1] if market else markets[:5]

    return {
        "crop": crop,
        "location": district or "Multiple locations",
        "markets": markets,
        "unit": "₹/Quintal",
        "base_unit": "quintal",
        "data_source": "Live APMC data from data.gov.in / Agmarknet",
        "is_demo": False,
    }


def generate_demo_market_prices(
    crop: str,
    district: Optional[str] = None,
    market: Optional[str] = None,
) -> Dict[str, Any]:
    crop_key = _get_crop_key(crop)
    base = BASE_PRICES.get(crop_key, {"min": 30.0, "max": 80.0, "unit": "kg"})
    unit = base["unit"]

    base_min = base["min"]
    base_max = base["max"]

    markets_list = _get_markets_for_district(district or "")
    if market:
        matching_market = next(
            (name for name in markets_list if _market_key(name) == _market_key(market)),
            None,
        )
        if not matching_market:
            raise ValueError(f"{market} does not belong to {district or 'a selected district'}")
        markets_list = [matching_market]
    selected_markets = markets_list[:5]

    markets: List[Dict[str, Any]] = []
    today = date.today().isoformat()
    random.seed(hash(crop.lower() + (district or "").lower() + (market or "").lower() + today))

    center_variance = random.uniform(-0.05, 0.05)
    center_price = ((base_min + base_max) / 2) * (1 + center_variance)

    for i, market_name in enumerate(selected_markets):
        market_bias = random.uniform(-0.08, 0.08)
        spread = random.uniform(0.05, 0.20)

        modal = center_price * (1 + market_bias)
        min_price = modal * (1 - spread)
        max_price = modal * (1 + spread + random.uniform(0, 0.05))

        arrival_base = 500 if unit == "quintal" else 50
        arrival = round(arrival_base * random.uniform(0.3, 2.2), 1)

        markets.append({
            "name": market_name,
            "min_price": round(min_price, 2),
            "max_price": round(max_price, 2),
            "modal_price": round(modal, 2),
            "arrival": arrival,
            "date": today,
        })

    markets.sort(key=lambda m: m["modal_price"], reverse=True)

    unit_display = f"₹/{unit.title()}" if unit in {"kg", "quintal"} else unit
    return {
        "crop": crop,
        "location": district or "All Markets",
        "markets": markets,
        "unit": unit_display,
        "base_unit": unit,
        "data_source": "Estimated Market Prices (Demo) - For reference only, NOT live APMC data",
        "is_demo": True,
    }
