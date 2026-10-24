import json
import logging
import time
from fastapi import APIRouter, Header, HTTPException, status
from typing import Optional, Dict, Any, List
from pydantic import BaseModel
from fastapi.responses import JSONResponse, StreamingResponse

from services.weather_service import get_open_meteo_weather
from services.ai_service import (
    AIProviderUnavailable,
    call_ai_conversation,
    stream_ai_conversation,
    translate_texts,
)
from services.assistant_fallback import local_agricultural_answer
from database import settings
from services.localization import LANGUAGE_NAMES, localized_message, resolve_language

router = APIRouter()
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


class ChatRequest(BaseModel):
    message: str
    context: Optional[Dict[str, Any]] = None
    history: Optional[List[Dict[str, str]]] = None


class ChatResponse(BaseModel):
    response: str
    source: str


class HistoryTranslationRequest(BaseModel):
    messages: List[str]


class HistoryTranslationResponse(BaseModel):
    messages: List[str]


def _needs_current_weather(message: str) -> bool:
    weather_terms = (
        "weather", "forecast", "rain", "rainfall", "temperature", "humidity",
        "wind", "irrigat", "water today", "water now", "tomorrow",
        "मौसम", "बारिश", "वर्षा", "तापमान", "नमी", "हवा", "सिंचाई", "पानी",
        "हवामान", "पाऊस", "पर्जन्य", "तापमान", "आर्द्रता", "वारा", "सिंचन", "पाणी",
        "കാലാവസ്ഥ", "മഴ", "താപനില", "ഈർപ്പം", "കാറ്റ്", "ജലസേചനം", "വെള്ളം",
        "ಹವಾಮಾನ", "ಮಳೆ", "ಮಳೆಯ", "ತಾಪಮಾನ", "ತೇವಾಂಶ", "ಗಾಳಿ", "ನೀರಾವರಿ", "ನೀರು",
    )
    normalized = message.casefold()
    return any(term.casefold() in normalized for term in weather_terms)


def _provider_error_detail(language: str, reason: str) -> str:
    error_key = {
        "auth": "ai_auth_error",
        "quota_exceeded": "ai_quota_exceeded",
        "openai_quota_exceeded": "ai_provider_quota_exceeded",
        "all_providers_quota_exceeded": "ai_provider_quota_exceeded",
        "groq_auth": "ai_auth_error",
        "groq_rate_limited": "ai_rate_limited",
        "groq_quota_exceeded": "ai_provider_error",
        "groq_not_configured": "ai_not_configured",
        "groq_model_not_configured": "ai_not_configured",
        "groq_model_unavailable": "ai_model_unavailable",
        "groq_sdk_unavailable": "ai_provider_error",
        "openai_auth": "ai_auth_error",
        "openai_rate_limit": "ai_rate_limited",
        "openai_auth": "ai_auth_error",
        "openai_sdk_unavailable": "ai_provider_error",
        "rate_limit": "ai_rate_limited",
        "timeout": "ai_timeout",
        "dns_error": "ai_dns_error",
        "connection_error": "ai_connection_error",
        "provider_error": "ai_provider_error",
        "model_unavailable": "ai_model_unavailable",
    }.get(reason, "ai_unavailable")
    return localized_message(language, error_key)


async def _prepare_chat(req: ChatRequest, language: str):
    message = req.message.strip()
    if not message:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=localized_message(language, "invalid_message"),
        )
    if len(message) > 8000:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=localized_message(language, "message_too_long"),
        )

    context = req.context or {}
    crop = context.get("crop", "")
    stage = context.get("stage", "")
    soil = context.get("soil") or context.get("soilType") or context.get("soil_type") or ""
    irrigation = context.get("irrigation", "")
    location = context.get("location", {})
    weather = context.get("weather")
    if (
        not weather
        and _needs_current_weather(message)
        and isinstance(location, dict)
    ):
        lat = location.get("latitude")
        lon = location.get("longitude")
        if lat is not None and lon is not None:
            try:
                weather = await get_open_meteo_weather(lat, lon)
            except Exception:
                logger.exception("Assistant weather context lookup failed")

    weather_desc = "not available"
    if weather and isinstance(weather, dict):
        current = weather.get("current", {})
        weather_desc = (
            f"Temperature: {current.get('temperature', 'N/A')}°C, "
            f"Humidity: {current.get('humidity', 'N/A')}%, "
            f"Rain: {current.get('rain', 0)}mm, "
            f"Wind: {current.get('wind_speed', 'N/A')} km/h"
        )

    conversation_history = []
    for item in (req.history or [])[-6:]:
        role = item.get("role")
        content = item.get("content", "").strip()
        if role in ("user", "assistant") and content:
            conversation_history.append({"role": role, "content": content[:1500]})

    lang_name = LANGUAGE_NAMES[language]
    system_prompt = (
        f"You are KrushiMitra, a capable, friendly conversational AI and an expert agricultural assistant. "
        f"Answer the user's actual question directly and naturally. You can discuss general topics as well as "
        f"agriculture; do not turn unrelated questions into farming advice. Respond to greetings naturally, "
        f"explain concepts clearly, and ask a focused follow-up only when it would materially improve the answer. "
        f"Generate each answer from the current question and the conversation history; do not use canned or fixed replies.\n\n"
        f"Use {lang_name} for your response. Understand messages written in English, Marathi, Hindi, or Malayalam. "
        f"Keep responding in the selected application language unless the user explicitly asks for another supported language.\n\n"
        f"Farmer context (use only when relevant; missing values are not facts):\n"
        f"- Crop: {crop or 'Not specified'}\n"
        f"- Growth Stage: {stage or 'Not specified'}\n"
        f"- Soil Type: {soil or 'Not specified'}\n"
        f"- Irrigation: {irrigation or 'Not specified'}\n"
        f"- Location: {location.get('district', '') + ', ' if isinstance(location, dict) and location.get('district') else ''}"
        f"{location.get('state', '') if isinstance(location, dict) and location.get('state') else 'Not specified'}\n"
        f"- Current Weather: {weather_desc}\n\n"
        f"Rules:\n"
        f"1. Do not claim to have checked live weather, market prices, scheme eligibility, or current regulations unless reliable current data is included in the context. Be clear when you do not have live data.\n"
        f"2. For farming advice, tailor guidance to the crop, stage, soil, location, and weather when supplied. If key details are missing, state assumptions or ask a relevant question.\n"
        f"3. Never invent disease diagnoses from text alone, pesticide/fungicide brands, dosages, concentrations, or mixing ratios. For chemicals, advise using only locally registered products and following the label, local agricultural guidance, and re-entry / pre-harvest intervals.\n"
        f"4. Prefer practical integrated crop management and safer cultural or biological methods. Recommend an agricultural expert for uncertain diagnosis or high-risk decisions.\n"
        f"5. Do not add a farming disclaimer to ordinary greetings or unrelated general questions. For consequential agricultural advice, briefly remind the user to confirm locally."
    )
    return message, conversation_history, system_prompt


@router.post("/chat", response_model=ChatResponse)
async def chat_with_assistant(
    req: ChatRequest,
    x_language: Optional[str] = Header(default="en", alias="X-Language"),
):
    try:
        language = resolve_language(x_language)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=localized_message("en", "invalid_language"),
        )
    request_started = time.perf_counter()
    message, conversation_history, system_prompt = await _prepare_chat(req, language)
    has_provider_key = bool(
        settings.GROQ_API_KEY or settings.GEMINI_API_KEY or settings.OPENAI_API_KEY
    )
    if has_provider_key:
        try:
            generated = await call_ai_conversation(message, system_prompt, conversation_history)
        except AIProviderUnavailable as exc:
            logger.warning(
                "Assistant provider unavailable reason=%s elapsed_ms=%d",
                exc.reason,
                round((time.perf_counter() - request_started) * 1000),
            )
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=_provider_error_detail(language, exc.reason),
                headers={"X-Error-Code": exc.reason},
            )
        if generated:
            ai_response, ai_source = generated
            logger.info(
                "Assistant chat request completed source=%s elapsed_ms=%d",
                ai_source,
                round((time.perf_counter() - request_started) * 1000),
            )
            return ChatResponse(response=ai_response, source=ai_source)
    else:
        local_answer = local_agricultural_answer(message, language)
        if local_answer:
            return ChatResponse(response=local_answer, source="local_fallback")

    error_key = "ai_unavailable" if has_provider_key else "ai_not_configured"
    raise HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail=localized_message(language, error_key),
        headers={"X-Error-Code": "provider_error" if has_provider_key else "not_configured"},
    )


@router.post("/chat/stream")
async def stream_chat_with_assistant(
    req: ChatRequest,
    x_language: Optional[str] = Header(default="en", alias="X-Language"),
):
    try:
        language = resolve_language(x_language)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=localized_message("en", "invalid_language"),
        )

    request_started = time.perf_counter()
    message, conversation_history, system_prompt = await _prepare_chat(req, language)
    has_provider_key = bool(
        settings.GROQ_API_KEY or settings.GEMINI_API_KEY or settings.OPENAI_API_KEY
    )

    if not has_provider_key:
        local_answer = local_agricultural_answer(message, language)
        if not local_answer:
            return JSONResponse(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                content={
                    "detail": localized_message(language, "ai_not_configured"),
                    "code": "not_configured",
                },
            )

        async def local_events():
            yield f"data: {json.dumps({'type': 'chunk', 'text': local_answer}, ensure_ascii=False)}\n\n"
            yield f"data: {json.dumps({'type': 'done', 'source': 'local_fallback'}, ensure_ascii=False)}\n\n"

        return StreamingResponse(
            local_events(),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )

    provider_events = stream_ai_conversation(
        message,
        system_prompt,
        conversation_history,
    )
    try:
        first_event = await provider_events.__anext__()
    except StopAsyncIteration:
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={
                "detail": localized_message(language, "ai_unavailable"),
                "code": "provider_error",
            },
        )
    except AIProviderUnavailable as exc:
        logger.warning(
            "Assistant streaming provider unavailable before first event reason=%s",
            exc.reason,
        )
        logger.warning(
            "Assistant stream failed elapsed_ms=%d",
            round((time.perf_counter() - request_started) * 1000),
        )
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={
                "detail": _provider_error_detail(language, exc.reason),
                "code": exc.reason,
            },
        )
    if first_event.get("type") == "error":
        reason = first_event.get("code")
        if not isinstance(reason, str) or not reason:
            reason = "provider_error"
        logger.warning(
            "Assistant streaming provider returned an error before first event reason=%s",
            reason,
        )
        logger.warning(
            "Assistant stream failed elapsed_ms=%d",
            round((time.perf_counter() - request_started) * 1000),
        )
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={
                "detail": _provider_error_detail(language, reason),
                "code": reason,
            },
        )

    async def events():
        first_chunk_logged = False
        try:
            for event in (first_event,):
                if event.get("type") == "chunk" and not first_chunk_logged:
                    logger.info(
                        "Assistant stream first chunk elapsed_ms=%d",
                        round((time.perf_counter() - request_started) * 1000),
                    )
                    first_chunk_logged = True
                if event.get("type") == "done":
                    logger.info(
                        "Assistant stream completed source=%s elapsed_ms=%d",
                        event.get("source", "unknown"),
                        round((time.perf_counter() - request_started) * 1000),
                    )
                yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
            async for event in provider_events:
                if event.get("type") == "chunk" and not first_chunk_logged:
                    logger.info(
                        "Assistant stream first chunk elapsed_ms=%d",
                        round((time.perf_counter() - request_started) * 1000),
                    )
                    first_chunk_logged = True
                if event.get("type") == "done":
                    logger.info(
                        "Assistant stream completed source=%s elapsed_ms=%d",
                        event.get("source", "unknown"),
                        round((time.perf_counter() - request_started) * 1000),
                    )
                yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
        except AIProviderUnavailable as exc:
            logger.warning("Assistant streaming provider unavailable reason=%s", exc.reason)
            logger.warning(
                "Assistant stream failed elapsed_ms=%d",
                round((time.perf_counter() - request_started) * 1000),
            )
            error = {
                "type": "error",
                "code": exc.reason,
                "detail": _provider_error_detail(language, exc.reason),
            }
            yield f"data: {json.dumps(error, ensure_ascii=False)}\n\n"
        except Exception:
            logger.exception("Assistant streaming response failed")
            error = {
                "type": "error",
                "detail": localized_message(language, "ai_unavailable"),
            }
            yield f"data: {json.dumps(error, ensure_ascii=False)}\n\n"

    return StreamingResponse(
        events(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.post("/translate-history", response_model=HistoryTranslationResponse)
async def translate_assistant_history(
    req: HistoryTranslationRequest,
    x_language: Optional[str] = Header(default="en", alias="X-Language"),
):
    try:
        language = resolve_language(x_language)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=localized_message("en", "invalid_language"),
        )

    if len(req.messages) > 20 or any(len(message) > 4000 for message in req.messages):
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=localized_message(language, "ai_unavailable"),
        )
    try:
        translated = await translate_texts(req.messages, language)
    except AIProviderUnavailable as exc:
        key = (
            "translation_quota_unavailable"
            if exc.reason in {"quota_exceeded", "openai_quota_exceeded"}
            else "translation_unavailable"
        )
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=localized_message(language, key),
            headers={"X-Error-Code": exc.reason},
        )
    if translated is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=localized_message(language, "translation_unavailable"),
        )
    return HistoryTranslationResponse(messages=translated)
