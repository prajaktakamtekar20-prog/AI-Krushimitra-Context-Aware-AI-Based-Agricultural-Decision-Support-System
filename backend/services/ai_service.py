import asyncio
import base64
import email.utils
import hashlib
import random
import socket
import time
from collections import OrderedDict
import httpx
import re
import json
import logging
from typing import Dict, Any, Optional, List, Tuple

from database import settings
from services.disease_model_service import (
    predict_disease,
    map_class_to_disease_key,
    split_class_name,
    analyze_prediction,
    build_crop_disease_key,
    normalize_crop_for_key,
    match_declared_crop,
    get_supported_classes,
    get_supported_crops,
    load_inference_config,
    ERROR_DB_VALIDATION,
    ERROR_UNCERTAIN,
)
from services.disease_knowledge_base import lookup_disease_knowledge
from services.disease_result_localization import localize_disease_result
from services.localization import (
    LANGUAGE_NAMES,
    localized_message,
    resolve_language,
    translate_known_message,
)

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
GEMINI_TRANSIENT_RETRIES = 1
GEMINI_MAX_CONCURRENT_VISION_REQUESTS = 2
GEMINI_MAX_RETRY_AFTER_SECONDS = 30.0
GEMINI_RETRY_BASE_DELAY_SECONDS = 0.5
_gemini_vision_semaphore = asyncio.Semaphore(GEMINI_MAX_CONCURRENT_VISION_REQUESTS)
GEMINI_VISION_TIMEOUT_MS = 20_000
_gemini_vision_client = None
_gemini_vision_client_key: Optional[str] = None
_gemini_vision_client_lock = asyncio.Lock()
CHAT_PROVIDER_TIMEOUT_SECONDS = 30.0
GEMINI_CHAT_TIMEOUT_SECONDS = 25.0
_chat_http_client: Optional[httpx.AsyncClient] = None
_openai_client = None
_openai_client_key: Optional[str] = None
_groq_client = None
_groq_client_key: Optional[str] = None
_groq_model_cache: Dict[Tuple[str, str], float] = {}
GROQ_API_BASE_URL = "https://api.groq.com/openai/v1"
GROQ_MODEL_CACHE_SECONDS = 300.0
OPENAI_CHAT_MODEL = "gpt-4.1-mini"
_translated_text_cache: OrderedDict[Tuple[str, str], str] = OrderedDict()
_translation_requests: Dict[Tuple[str, Tuple[str, ...]], asyncio.Task[Optional[List[str]]]] = {}
TRANSLATED_TEXT_CACHE_LIMIT = 512
GEMINI_QUOTA_COOLDOWN_SECONDS = 300
_gemini_quota_blocked_until = 0.0


def _get_chat_http_client() -> httpx.AsyncClient:
    global _chat_http_client
    if _chat_http_client is None or _chat_http_client.is_closed:
        _chat_http_client = httpx.AsyncClient(timeout=GEMINI_CHAT_TIMEOUT_SECONDS)
    return _chat_http_client


def _get_openai_client():
    global _openai_client, _openai_client_key
    api_key = (settings.OPENAI_API_KEY or "").strip()
    if not api_key:
        return None
    if _openai_client is None or _openai_client_key != api_key:
        from openai import AsyncOpenAI

        _openai_client = AsyncOpenAI(
            api_key=api_key,
            timeout=CHAT_PROVIDER_TIMEOUT_SECONDS,
            max_retries=0,
        )
        _openai_client_key = api_key
    return _openai_client


def _get_groq_client():
    global _groq_client, _groq_client_key
    api_key = (settings.GROQ_API_KEY or "").strip()
    if not api_key:
        return None
    if _groq_client is None or _groq_client_key != api_key:
        from openai import AsyncOpenAI

        _groq_client = AsyncOpenAI(
            api_key=api_key,
            base_url=GROQ_API_BASE_URL,
            timeout=CHAT_PROVIDER_TIMEOUT_SECONDS,
            max_retries=0,
        )
        _groq_client_key = api_key
        _groq_model_cache.clear()
    return _groq_client


async def initialize_chat_http_client() -> None:
    _get_chat_http_client()
    if settings.OPENAI_API_KEY:
        _get_openai_client()
    if settings.GROQ_API_KEY:
        _get_groq_client()


async def close_chat_http_client() -> None:
    global _chat_http_client, _openai_client, _openai_client_key
    global _groq_client, _groq_client_key
    if _chat_http_client is not None and not _chat_http_client.is_closed:
        await _chat_http_client.aclose()
    _chat_http_client = None
    if _openai_client is not None:
        await _openai_client.close()
    _openai_client = None
    _openai_client_key = None
    if _groq_client is not None:
        await _groq_client.close()
    _groq_client = None
    _groq_client_key = None
    _groq_model_cache.clear()


async def _get_gemini_vision_client():
    global _gemini_vision_client, _gemini_vision_client_key
    api_key = _get_gemini_api_key()
    if not api_key:
        raise GeminiVisionUnavailable(
            "gemini_api_key_missing",
            "Gemini API key is not configured.",
        )
    if _gemini_vision_client is not None and _gemini_vision_client_key == api_key:
        return _gemini_vision_client.aio

    from google import genai
    from google.genai import types

    async with _gemini_vision_client_lock:
        if _gemini_vision_client is not None and _gemini_vision_client_key == api_key:
            return _gemini_vision_client.aio
        if _gemini_vision_client is not None:
            await _gemini_vision_client.aio.aclose()
        _gemini_vision_client = genai.Client(
            api_key=api_key,
            http_options=types.HttpOptions(
                api_version="v1beta",
                timeout=GEMINI_VISION_TIMEOUT_MS,
                retry_options=types.HttpRetryOptions(attempts=1),
            ),
        )
        _gemini_vision_client_key = api_key
        return _gemini_vision_client.aio


async def initialize_gemini_vision_client() -> None:
    if _get_gemini_api_key():
        await _get_gemini_vision_client()


async def close_gemini_vision_client() -> None:
    global _gemini_vision_client, _gemini_vision_client_key
    if _gemini_vision_client is not None:
        await _gemini_vision_client.aio.aclose()
    _gemini_vision_client = None
    _gemini_vision_client_key = None

def _get_gemini_api_key() -> str:
    return (settings.GEMINI_API_KEY or "").strip()


def _get_gemini_model() -> str:
    return (
        (settings.GEMINI_MODEL or "").strip()
        or (settings.GEMINI_VISION_MODEL or "").strip()
        or (settings.GEMINI_CHAT_MODEL or "").strip()
        or "gemini-3.8-flash"
    )


def _safe_gemini_error_detail(exc: Exception, api_key: str) -> str:
    response = getattr(exc, "response", None)
    response_details = getattr(exc, "details", None)
    if not isinstance(response_details, (dict, list)) and response is not None:
        try:
            response_details = response.json()
        except (AttributeError, ValueError):
            response_details = None

    if isinstance(response_details, dict):
        error = response_details.get("error", response_details)
        if isinstance(error, dict):
            parts = [error.get("status"), error.get("message")]
            for item in error.get("details", []):
                if isinstance(item, dict):
                    parts.extend((item.get("reason"), item.get("message")))
            detail = " ".join(str(part) for part in parts if part)
        else:
            detail = str(getattr(exc, "message", "") or exc)
    elif isinstance(response_details, list):
        detail = " ".join(str(item) for item in response_details)
    else:
        detail = str(getattr(exc, "message", "") or exc)
    if api_key:
        detail = detail.replace(api_key, "[REDACTED]")
    detail = re.sub(r"\bAIza[0-9A-Za-z_-]{20,}\b", "[REDACTED]", detail)
    detail = re.sub(
        r"(?i)\b(api[_ -]?key)\s*[:=]\s*[^\s,;]+",
        r"\1=[REDACTED]",
        detail,
    )
    detail = re.sub(
        r"(?i)\b(bearer)\s+[A-Za-z0-9._~+/=-]+",
        r"\1 [REDACTED]",
        detail,
    )
    return re.sub(r"\s+", " ", detail).strip()[:600]


def _gemini_vision_status_code(exc: Exception, detail: str) -> Optional[int]:
    status_code = getattr(exc, "code", None)
    try:
        return int(status_code)
    except (TypeError, ValueError):
        match = re.search(r"(?:error code|http(?: status)?)\s*[:=]?\s*(\d{3})", detail, re.IGNORECASE)
        return int(match.group(1)) if match else None


def _gemini_vision_error_category(status_code: Optional[int], detail: str) -> Tuple[str, str]:
    normalized = detail.casefold()
    if status_code is None and any(
        term in normalized for term in ("request timed out", "timed out", "timeout")
    ):
        return "gemini_timeout", (
            "Gemini did not respond before the backend request timeout. Please retry."
        )
    if any(term in normalized for term in ("api_key_invalid", "api key not valid", "invalid api key")):
        return "gemini_invalid_key", "The Gemini API key is invalid. Check the backend key configuration."
    if status_code == 401:
        return "gemini_invalid_key", "The Gemini API key was rejected. Check the backend key configuration."
    if status_code == 403 or any(
        term in normalized for term in ("permission_denied", "permission denied", "not authorized")
    ):
        return "gemini_permission_denied", (
            "The Gemini API key does not have permission to use the configured model or API."
        )
    if status_code == 404 or any(term in normalized for term in ("model_not_found", "model not found")):
        return "gemini_model_not_found", (
            "The configured Gemini vision model was not found for this API. "
            "Check the model name and API-key model access."
        )
    if status_code == 429:
        return _gemini_429_error_type(detail), (
            "Gemini API quota is exhausted. Check the Google AI project quota and billing settings."
            if _gemini_429_error_type(detail) == "gemini_quota_exceeded"
            else "Gemini is temporarily rate-limiting requests. Please wait before trying again."
        )
    return "", ""


def _gemini_interaction_text(response: Any) -> str:
    output_text = getattr(response, "output_text", None)
    if isinstance(output_text, str):
        return output_text.strip()

    outputs = getattr(response, "outputs", None) or []
    return "".join(
        text
        for output in outputs
        if (text := getattr(output, "text", None))
    ).strip()


def _gemini_429_error_type(detail: str) -> str:
    normalized = detail.casefold()
    if any(
        term in normalized
        for term in (
            "current quota",
            "billing",
            "quota exceeded",
            "quota_limit",
            "quota metric",
            "check quota",
        )
    ):
        return "gemini_quota_exceeded"
    if any(
        term in normalized
        for term in (
            "per minute",
            "per second",
            "rate limit",
            "rate_limit_exceeded",
            "too many requests",
        )
    ):
        return "gemini_rate_limited"
    return "gemini_rate_limited"


def _mark_gemini_quota_exhausted() -> None:
    global _gemini_quota_blocked_until
    _gemini_quota_blocked_until = time.monotonic() + GEMINI_QUOTA_COOLDOWN_SECONDS


def _gemini_quota_cooldown_active() -> bool:
    return time.monotonic() < _gemini_quota_blocked_until


def _gemini_retry_delay_seconds(exc: Exception) -> Optional[float]:
    response = getattr(exc, "response", None)
    headers = getattr(response, "headers", None) or getattr(exc, "headers", None)
    retry_after = headers.get("Retry-After") if headers else None
    if retry_after:
        try:
            return max(0.0, float(retry_after))
        except (TypeError, ValueError):
            try:
                retry_at = email.utils.parsedate_to_datetime(retry_after)
                return max(0.0, retry_at.timestamp() - time.time())
            except (TypeError, ValueError, OverflowError):
                pass

    retry_delay = getattr(exc, "retry_delay", None)
    if retry_delay is not None:
        seconds = getattr(retry_delay, "seconds", None)
        nanos = getattr(retry_delay, "nanos", 0) or 0
        if seconds is not None:
            return max(0.0, float(seconds) + float(nanos) / 1_000_000_000)

    detail = str(getattr(exc, "message", "") or exc)
    match = re.search(r"(?i)(?:retry(?:delay| in)?)[\s:=\"]+(\d+(?:\.\d+)?)\s*s", detail)
    if not match:
        return None
    return max(0.0, float(match.group(1)))


def _gemini_error_details(response: httpx.Response, api_key: str) -> Dict[str, str]:
    try:
        payload = response.json()
    except ValueError:
        payload = {}
    error = payload.get("error", {}) if isinstance(payload, dict) else {}
    if not isinstance(error, dict):
        error = {}
    error_details = error.get("details", [])
    detail_text = json.dumps(error_details, ensure_ascii=False) if error_details else ""
    reason = next(
        (
            item.get("reason", "")
            for item in error_details
            if isinstance(item, dict) and item.get("reason")
        ),
        "",
    )
    message = " ".join(
        str(value).strip()
        for value in (error.get("message"), error.get("status"), detail_text)
        if value
    )
    safe_detail = message
    if api_key:
        safe_detail = safe_detail.replace(api_key, "[REDACTED]")
    safe_detail = re.sub(r"\bAIza[0-9A-Za-z_-]{20,}\b", "[REDACTED]", safe_detail)
    safe_detail = re.sub(
        r"(?i)\b(api[_ -]?key)\s*[:=]\s*[^\s,;]+",
        r"\1=[REDACTED]",
        safe_detail,
    )
    safe_detail = re.sub(
        r"(?i)\b(bearer)\s+[A-Za-z0-9._~+/=-]+",
        r"\1 [REDACTED]",
        safe_detail,
    )
    return {
        "reason": str(reason),
        "status": str(error.get("status", "")),
        "message": re.sub(r"\s+", " ", safe_detail).strip()[:1200],
        "retry_after": response.headers.get("Retry-After", ""),
    }


def _gemini_safety_block_reason(response: Any) -> Optional[str]:
    def enum_name(value: Any) -> str:
        return str(getattr(value, "name", value) or "").rsplit(".", 1)[-1].upper()

    feedback = getattr(response, "prompt_feedback", None)
    block_reason = enum_name(getattr(feedback, "block_reason", None))
    if block_reason not in {"", "0", "BLOCK_REASON_UNSPECIFIED"}:
        return block_reason

    candidates = getattr(response, "candidates", None) or []
    for candidate in candidates:
        finish_reason = enum_name(getattr(candidate, "finish_reason", None))
        if finish_reason in {
            "SAFETY",
            "IMAGE_SAFETY",
            "BLOCKLIST",
            "PROHIBITED_CONTENT",
            "SPII",
        }:
            return finish_reason
    return None


class GeminiVisionUnavailable(RuntimeError):
    def __init__(self, error_type: str, message: str):
        super().__init__(message)
        self.error_type = error_type


def _validate_db_entry_crop(db_entry: Dict[str, Any], detected_crop: str) -> bool:
    if not db_entry:
        return False
    db_crop_raw = db_entry.get("crop", "") or ""
    if not db_crop_raw or not detected_crop:
        return False
    db_crop_key = normalize_crop_for_key(db_crop_raw)
    detected_crop_key = normalize_crop_for_key(detected_crop)
    if db_crop_key == detected_crop_key:
        return True
    if "/" in db_crop_raw:
        parts = [p.strip() for p in db_crop_raw.split("/")]
        for part in parts:
            if normalize_crop_for_key(part) == detected_crop_key:
                return True
    return False


_GEMINI_VISION_PLANT_SYSTEM_PROMPT = """You are an expert agricultural plant disease analysis assistant.
Analyze the uploaded plant IMAGE carefully. Do NOT assume the disease from a predefined database, model labels, or the optional model context provided below. Base your answer strictly on VISIBLE EVIDENCE in the actual image.

Your mandatory reasoning workflow:
1. FIRST — determine whether the image actually contains a recognizable plant, leaf, fruit, or other identifiable crop/plant tissue.
   - If it is NOT a plant image (e.g., person, car, animal, building, landscape without a close plant/leaf, blank, pure text, etc.) you MUST return:
     is_valid_plant_image: false
2. If it IS a plant image but the disease cannot be determined reliably (blurry, too small, bad angle, lighting obscures details, no lesions visible despite your best inspection) then you MUST set:
     disease: "Unknown / Cannot determine reliably"
   and explain why in the diagnostic_note.
3. Never hallucinate a disease that you cannot visually support. Do NOT claim 100% certainty. If you are unsure, choose "Unknown / Cannot determine reliably" and explain.
4. If the plant and a specific disease/problem are visually recognizable from the image, return your most likely diagnosis and EXPLAIN the visible evidence (lesion shape, color, pattern, distribution, target spots, rings, mildew, rust pustules, mosaic, wilting, etc.) inside diagnostic_note.

CONFIDENCE and SEVERITY rules:
- confidence: a single float between 0.0 (pure guess) and 1.0 (fully certain). Usually 0.5–0.95. NEVER 1.0.
- crop_confidence: a separate float between 0.0 and 1.0 for crop identity. Do not copy disease confidence into this field.
- severity: ONLY estimate severity if there is clear visual evidence of how much leaf/fruit area is affected (e.g. few small spots vs. widespread blighting across most of the visible tissue). Valid short strings: "Mild", "Moderate", "Moderate to Severe", "Severe". If you cannot estimate from visual evidence (single isolated lesion photo, closeup too tight, healthy plant), you MUST return severity: null. Do NOT derive severity from confidence %. They are independent.

TREATMENT / MANAGEMENT SAFETY RULES (strictly enforced in recommended_management):
- Prefer Integrated Disease Management order:
  A. Cultural / Sanitation / Canopy / Crop-rotation practices first.
  B. Biological / Organic / Biocontrol options where documented.
  C. Chemical / Synthetic control ONLY IF clearly documented for this crop + problem combination.
- NEVER invent or fabricate any pesticide/fungicide/bactericide brand names, specific dosages, concentrations (%, g/L, mL/L, ppm, kg/ha, oz/gal, lb/A), mixing ratios, exact spray intervals, or precise calendar schedules.
- For any chemical-control bullet you MUST include the safety directive: "Use only locally registered agrochemicals for this crop and problem; always read and follow the product label, local agricultural extension recommendations, and respect re-entry / pre-harvest intervals." Do not write specific numbers.

HEALTHY PLANT case:
- If the image shows a uniformly green, well-structured plant/leaf with no lesions, spots, discoloration, mildew, rust, or visible symptoms, you MUST diagnose as healthy. For disease you may write e.g. "Healthy leaf / No major disease detected" and note the visible cleanliness in diagnostic_note. recommended_management becomes crop-care + preventive-scouting guidance, not treatment.

MODEL CONTEXT rule:
- The user message may include a MobileNet model prediction. Treat it ONLY as an advisory hint. You MUST independently verify from the image. If your visual diagnosis agrees → mention the agreement in diagnostic_note. If you disagree → explicitly state the disagreement in diagnostic_note and why the image evidence supports your call. Do NOT blindly echo the model prediction.

FORCE VALID JSON ONLY output (no markdown, no backticks, no commentary, no bullet lists outside JSON, no extra prose). Exactly this top-level schema and nothing else:
{
  "is_valid_plant_image": true,
  "crop": "Common crop name string or empty string if indeterminate",
  "crop_display": "Localized crop name for display",
  "crop_confidence": null,
  "disease": "Disease name or 'Unknown / Cannot determine reliably' or healthy description",
  "disease_display": "Localized disease name with the canonical English disease name in parentheses",
  "confidence": null,
  "severity": null,
  "symptoms": ["string symptom 1 based on image evidence", "..."],
  "possible_causes": ["string cause 1", "..."],
  "recommended_management": ["string mgmt 1", "..."],
  "prevention": ["string prevention 1", "..."],
  "diagnostic_note": "String summarizing visible evidence, reasoning, model-vs-vision agreement/disagreement note, and/or any uncertainty explanation."
}
Use numeric confidence scores only when the image supports a diagnosis. Use null for crop_confidence or confidence when the corresponding score is unavailable or the image is inconclusive.
All arrays must be strings. Empty arrays are allowed when the image does not support confident items. If is_valid_plant_image is false, crop/disease/symptoms/possible_causes/recommended_management/prevention can be empty/[] but still keep valid JSON shape, and diagnostic_note should briefly say why the image is not a plant.
"""


async def call_gemini_vision(
    image_bytes: bytes,
    content_type: Optional[str],
    text_message: str,
    system_prompt: str,
) -> Optional[str]:
    """Send the uploaded image and analysis prompt through the Gemini Interactions API."""
    api_key = _get_gemini_api_key()
    if not api_key:
        raise GeminiVisionUnavailable(
            "gemini_api_key_missing",
            "Gemini API key is not configured.",
        )
    if _gemini_quota_cooldown_active():
        raise GeminiVisionUnavailable(
            "gemini_quota_exceeded",
            "Gemini API quota was recently exhausted. Check the Google AI project quota and billing settings.",
        )
    if image_bytes is None or len(image_bytes) == 0:
        return None

    try:
        client = await _get_gemini_vision_client()
    except ImportError as exc:
        raise GeminiVisionUnavailable(
            "gemini_sdk_unavailable",
            "The optional Gemini Vision SDK is not installed.",
        ) from exc

    mime_type = (content_type or "image/jpeg").split(";", 1)[0].strip().lower()
    if mime_type not in {"image/jpeg", "image/png", "image/webp"}:
        raise GeminiVisionUnavailable(
            "gemini_request_rejected",
            "Gemini image analysis only accepts JPG, PNG, or WebP images.",
        )

    vision_started = time.perf_counter()
    try:
        async def create_interaction():
            async with _gemini_vision_semaphore:
                return await client.interactions.create(
                    api_version="v1beta",
                    model=_get_gemini_model(),
                    input=[
                        {"type": "text", "text": text_message},
                        {
                            "type": "image",
                            "data": base64.b64encode(image_bytes).decode("ascii"),
                            "mime_type": mime_type,
                        },
                    ],
                    system_instruction=system_prompt,
                    generation_config={"max_output_tokens": 4096, "temperature": 0.4},
                    store=False,
                )

        loop = asyncio.get_running_loop()
        deadline = loop.time() + GEMINI_VISION_TIMEOUT_MS / 1000
        for attempt in range(GEMINI_TRANSIENT_RETRIES + 1):
            try:
                remaining = deadline - loop.time()
                if remaining <= 0:
                    raise asyncio.TimeoutError
                response = await asyncio.wait_for(
                    create_interaction(),
                    timeout=remaining,
                )
                break
            except asyncio.TimeoutError:
                raise
            except Exception as exc:
                status_code = _gemini_vision_status_code(
                    exc,
                    _safe_gemini_error_detail(exc, api_key),
                )
                safe_detail = _safe_gemini_error_detail(exc, api_key)
                if (
                    status_code != 429
                    or _gemini_429_error_type(safe_detail) != "gemini_rate_limited"
                    or attempt >= GEMINI_TRANSIENT_RETRIES
                ):
                    raise

                retry_after = _gemini_retry_delay_seconds(exc)
                exponential_delay = min(
                    GEMINI_RETRY_BASE_DELAY_SECONDS * (2 ** attempt),
                    GEMINI_MAX_RETRY_AFTER_SECONDS,
                )
                exponential_delay += random.uniform(0, exponential_delay / 4)
                delay = (
                    max(retry_after, exponential_delay)
                    if retry_after is not None
                    else exponential_delay
                )
                remaining = deadline - loop.time()
                if (
                    (retry_after is not None and retry_after > GEMINI_MAX_RETRY_AFTER_SECONDS)
                    or delay >= remaining
                ):
                    logger.warning(
                        "Gemini Vision retry skipped error_type=gemini_rate_limited "
                        "retry_after_seconds=%s remaining_ms=%.1f model=%s detail=%s",
                        retry_after,
                        max(0.0, remaining * 1000),
                        _get_gemini_model(),
                        safe_detail,
                    )
                    raise

                logger.warning(
                    "Gemini Vision retry scheduled error_type=gemini_rate_limited "
                    "retry=%d retry_after_seconds=%s delay_seconds=%.2f model=%s detail=%s",
                    attempt + 1,
                    retry_after,
                    delay,
                    _get_gemini_model(),
                    safe_detail,
                )
                await asyncio.sleep(delay)
        text = _gemini_interaction_text(response)
        if not text:
            if _gemini_safety_block_reason(response):
                raise GeminiVisionUnavailable(
                    "gemini_safety_blocked",
                    "Gemini safety filters blocked this analysis request. "
                    "No diagnosis was produced; try an appropriate, non-sensitive plant image.",
                )
            raise GeminiVisionUnavailable(
                "gemini_empty_response",
                "Gemini did not return a usable image analysis.",
            )
        return text
    except GeminiVisionUnavailable:
        raise
    except asyncio.TimeoutError:
        logger.warning(
            "Gemini Vision request failed error_type=gemini_timeout "
            "stage=interactions_create model=%s timeout_ms=%d elapsed_ms=%.1f",
            _get_gemini_model(),
            GEMINI_VISION_TIMEOUT_MS,
            (time.perf_counter() - vision_started) * 1000,
        )
        raise GeminiVisionUnavailable(
            "gemini_timeout",
            "Gemini did not respond before the backend request timeout. Please retry.",
        ) from None
    except Exception as exc:
        error_message = str(getattr(exc, "message", "") or "").lower()
        safe_detail = _safe_gemini_error_detail(exc, api_key)
        status_code = _gemini_vision_status_code(exc, safe_detail)

        error_type, public_message = _gemini_vision_error_category(
            status_code,
            f"{error_message} {safe_detail}",
        )
        if error_type:
            if error_type == "gemini_quota_exceeded":
                _mark_gemini_quota_exhausted()
        elif status_code == 400:
            combined_detail = f"{error_message} {safe_detail}".casefold()
            if "legacy interactions api schema is no longer supported" in combined_detail:
                error_type = "gemini_sdk_incompatible"
                public_message = (
                    "The installed Google GenAI SDK is incompatible with the Gemini image-analysis API. "
                    "Update the backend dependencies and restart the server."
                )
            elif any(term in combined_detail for term in ("api_key", "api key", "credential")):
                error_type = "gemini_invalid_key"
                public_message = "The Gemini API key was rejected. Check the backend key configuration."
            else:
                error_type = "gemini_request_rejected"
                public_message = (
                    "Gemini rejected the image-analysis request configuration or content. "
                    "No diagnosis was produced; check the backend log for the redacted provider reason."
                )
        elif status_code == 503:
            error_type = "gemini_provider_busy"
            public_message = (
                "Gemini is temporarily busy and could not complete the image analysis. "
                "Please wait a moment and try again."
            )
        elif status_code == 429 and _gemini_429_error_type(safe_detail) == "gemini_rate_limited":
            error_type = "gemini_rate_limited"
            public_message = (
                "Gemini is temporarily rate-limiting image analysis. "
                "Please wait a moment and try again."
            )
        elif status_code is not None and status_code >= 500:
            error_type = "gemini_provider_error"
            public_message = (
                "Gemini is temporarily unable to process image analysis. Please try again shortly."
            )
        elif isinstance(exc, (httpx.TransportError, httpx.TimeoutException, TimeoutError, ConnectionError, OSError)):
            error_type = "gemini_provider_unavailable"
            public_message = "Gemini Vision is temporarily unreachable. Check the backend network connection and retry."
        else:
            error_type = "gemini_provider_unavailable"
            public_message = "Gemini Vision could not complete the request. Please retry later."

        logger.warning(
            "Gemini Vision request failed stage=interactions_create error_type=%s "
            "status_code=%s provider_status=%s retry_after_seconds=%s model=%s detail=%s",
            error_type,
            status_code,
            getattr(exc, "status", None),
            _gemini_retry_delay_seconds(exc),
            _get_gemini_model(),
            safe_detail,
        )
        raise GeminiVisionUnavailable(error_type, public_message) from None
    finally:
        logger.info(
            "Disease timing stage=gemini_vision elapsed_ms=%.1f timeout_ms=%d retries=%d",
            (time.perf_counter() - vision_started) * 1000,
            GEMINI_VISION_TIMEOUT_MS,
            GEMINI_TRANSIENT_RETRIES,
        )


def _parse_llm_json(text: str) -> Optional[Dict[str, Any]]:
    """Try direct JSON parse, then regex block, then salvage with bracket closing."""
    if not text:
        return None
    s = text.strip()
    if s.startswith("```"):
        s = re.sub(r"^```(?:json)?", "", s)
        s = re.sub(r"```$", "", s)
        s = s.strip()
    parse_errors: List[str] = []
    obj: Any = None
    try:
        obj = json.loads(s)
    except json.JSONDecodeError as e1:
        parse_errors.append(f"direct: {str(e1)[:120]}")
        m = re.search(r"\{[\s\S]*\}", s)
        if m:
            cand = m.group(0)
            try:
                obj = json.loads(cand)
            except json.JSONDecodeError as e2:
                parse_errors.append(f"regex-block: {str(e2)[:120]}")
        if obj is None:
            repaired = re.sub(r'(?<!\\)\\(?!["\\/bfnrtu])', r"\\\\", s)
            try:
                obj = json.loads(repaired)
            except json.JSONDecodeError as e3:
                parse_errors.append(f"backslash-repair: {str(e3)[:120]}")
    if obj is None:
        salvage = s.rstrip()
        salvage = re.sub(r",+\s*$", "", salvage)
        in_str = False
        escaped = False
        opens: List[str] = []
        for ch in salvage:
            if escaped:
                escaped = False
                continue
            if ch == "\\":
                escaped = True
                continue
            if ch == '"':
                in_str = not in_str
                continue
            if in_str:
                continue
            if ch in "{[":
                opens.append(ch)
            elif ch in "}]":
                if opens:
                    opens.pop()
        if in_str:
            salvage += '"'
            in_str = False
        while opens:
            last = opens.pop()
            close = "}" if last == "{" else "]"
            salvage = salvage.rstrip()
            if not salvage.endswith(close):
                salvage += close
        try:
            obj = json.loads(salvage)
            logger.debug("LLM JSON salvage parse succeeded after bracket repair")
        except json.JSONDecodeError as ex_salvage:
            parse_errors.append(f"salvage: {str(ex_salvage)[:160]}")
            logger.warning("LLM JSON parsing failed parse_errors=%s", parse_errors)
            return None
    if isinstance(obj, dict):
        return obj
    return None


def _validate_and_normalize_vision_result(obj: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """Apply type checks, defaults, backward-compat aliases, and percentage confidence."""
    safe: Dict[str, Any] = {
        "is_valid_plant_image": False,
        "crop": "",
        "crop_display": "",
        "crop_confidence": None,
        "disease": "",
        "disease_display": "",
        "confidence": None,
        "severity": None,
        "symptoms": [],
        "possible_causes": [],
        "recommended_management": [],
        "prevention": [],
        "diagnostic_note": "",
    }
    if isinstance(obj, dict):
        v = obj.get("is_valid_plant_image")
        if isinstance(v, bool):
            safe["is_valid_plant_image"] = v
        elif isinstance(v, int):
            safe["is_valid_plant_image"] = bool(v)
        elif isinstance(v, str):
            normalized_bool = v.strip().lower()
            if normalized_bool in ("true", "yes", "1"):
                safe["is_valid_plant_image"] = True
            elif normalized_bool in ("false", "no", "0"):
                safe["is_valid_plant_image"] = False

        for k in ("crop", "disease", "crop_display", "disease_display"):
            val = obj.get(k)
            if val is None:
                safe[k] = ""
            else:
                try:
                    safe[k] = str(val).strip()
                except Exception:
                    safe[k] = ""

        def parse_confidence(value: Any) -> Optional[float]:
            if isinstance(value, bool) or not isinstance(value, (int, float, str)):
                return None
            try:
                parsed = float(value.strip().rstrip("%")) if isinstance(value, str) else float(value)
            except ValueError:
                return None
            if parsed > 1.5:
                parsed /= 100.0
            return min(max(parsed, 0.0), 1.0)

        parsed_confidence = parse_confidence(obj.get("confidence"))
        if parsed_confidence is not None:
            safe["confidence"] = parsed_confidence
        safe["crop_confidence"] = parse_confidence(obj.get("crop_confidence"))

        sev = obj.get("severity")
        if sev is None:
            safe["severity"] = None
        elif isinstance(sev, str) and sev.strip():
            safe["severity"] = sev.strip()
        else:
            try:
                safe["severity"] = str(sev).strip() or None
            except Exception:
                safe["severity"] = None

        for arr_key in ("symptoms", "possible_causes", "recommended_management", "prevention"):
            items = obj.get(arr_key, [])
            cleaned: List[str] = []
            if isinstance(items, list):
                for it in items:
                    if it is None:
                        continue
                    try:
                        ts = str(it).strip()
                    except Exception:
                        continue
                    if ts:
                        cleaned.append(ts)
            safe[arr_key] = cleaned

        dn = obj.get("diagnostic_note")
        if dn is None:
            safe["diagnostic_note"] = ""
        else:
            try:
                safe["diagnostic_note"] = str(dn).strip()
            except Exception:
                safe["diagnostic_note"] = ""

    if not safe["is_valid_plant_image"] and not safe["diagnostic_note"]:
        safe["diagnostic_note"] = (
            "The uploaded image does not appear to show a recognizable plant, leaf, or crop tissue."
            " Please upload a clear, close-up photo of the affected leaf or fruit."
        )

    return safe


_UNVERIFIED_CHEMICAL_GUIDANCE = re.compile(
    r"\b(?:fungicid\w*|pesticid\w*|bactericid\w*|herbicid\w*|miticid\w*|"
    r"insecticid\w*|agrochemical\w*|mancozeb|captan|dodine|myclobutanil|"
    r"penconazole|tebuconazole|propiconazole|chlorothalonil|cymoxanil|"
    r"fluopicolide|propamocarb|dimethomorph|azoxystrobin|pyraclostrobin|"
    r"copper oxychloride|bordeaux|wettable sulfur|sulphur|sulfur|neem oil|"
    r"bleach|trisodium phosphate|spray(?:s|ing)?|sprayed)\b|"
    r"\b\d+(?:\.\d+)?\s*(?:%|g\s*/\s*l|ml\s*/\s*l|kg\s*/\s*ha|ppm)\b",
    re.IGNORECASE,
)


def _safe_knowledge_list(items: Any, fallback: str) -> List[str]:
    if not isinstance(items, list):
        items = []
    safe_items = [
        str(item).strip()
        for item in items
        if isinstance(item, str)
        and item.strip()
        and not _UNVERIFIED_CHEMICAL_GUIDANCE.search(item)
    ]
    return safe_items or [fallback]


def _uncertain_local_model_result(
    model_analysis: Dict[str, Any],
    reason: str,
    model_timing: Dict[str, float],
) -> Dict[str, Any]:
    result = _uncertain_diagnosis(
        reason,
        crop=str(model_analysis.get("crop") or ""),
        crop_confidence=(
            float(model_analysis["crop_confidence"]) / 100
            if model_analysis.get("crop_confidence") is not None
            else None
        ),
    )
    result["_analysis_source"] = "plantvillage_mobilenetv2_uncertain"
    result["preliminary"] = True
    result["_timing_ms"] = {
        **model_timing,
        "external_ai_ms": 0.0,
        "explanation_ms": 0.0,
        "translation_ms": 0.0,
    }
    return result


def _build_local_model_result(
    model_analysis: Dict[str, Any],
    model_timing: Dict[str, float],
) -> Dict[str, Any]:
    crop = str(model_analysis.get("crop") or "").strip()
    raw_class = str(model_analysis.get("raw_class") or "").strip()
    supported_classes = get_supported_classes()
    if model_analysis.get("uncertain"):
        return _uncertain_local_model_result(
            model_analysis,
            "The model confidence or class separation is too low for a reliable result.",
            model_timing,
        )
    if not crop or not raw_class or raw_class not in supported_classes:
        return _uncertain_local_model_result(
            model_analysis,
            "The model prediction did not map to a supported crop and disease class.",
            model_timing,
        )

    class_crop, _ = split_class_name(raw_class)
    if normalize_crop_for_key(class_crop) != normalize_crop_for_key(crop):
        return _uncertain_local_model_result(
            model_analysis,
            "The model crop and disease class do not match, so no diagnosis was produced.",
            model_timing,
        )

    generic_key = map_class_to_disease_key(raw_class)
    disease_key = build_crop_disease_key(crop, generic_key)
    knowledge = lookup_disease_knowledge(crop, disease_key, generic_key)
    if not knowledge and not model_analysis.get("is_healthy"):
        return _uncertain_local_model_result(
            model_analysis,
            "No crop-specific reference information matched this model class; treatment guidance was withheld.",
            model_timing,
        )

    if knowledge:
        result = _build_curated_vision_result(
            {
                "crop_confidence": float(model_analysis.get("crop_confidence") or 0.0) / 100,
                "confidence": float(model_analysis.get("disease_confidence") or 0.0) / 100,
                "severity": knowledge.get("severity"),
                "diagnostic_note": "",
                "symptoms": [],
            },
            crop,
            raw_class,
            model_analysis,
        )
    else:
        result = {
            "ok": True,
            "is_valid_plant_image": True,
            "crop": crop,
            "crop_confidence": round(float(model_analysis.get("crop_confidence") or 0.0)),
            "disease": "Healthy leaf / no major disease detected",
            "confidence": round(float(model_analysis.get("disease_confidence") or 0.0)),
            "disease_confidence": round(float(model_analysis.get("disease_confidence") or 0.0)),
            "severity": None,
            "symptoms": [],
            "symptoms_basis": "unavailable",
            "possible_causes": [],
            "causes": [],
            "recommended_management": [
                "No treatment is recommended from this image result. Continue regular crop monitoring and follow local crop-specific guidance."
            ],
            "treatment": [
                "No treatment is recommended from this image result. Continue regular crop monitoring and follow local crop-specific guidance."
            ],
            "prevention": [
                "Continue regular field scouting; a healthy-looking leaf image does not rule out other crop problems."
            ],
            "is_healthy": True,
            "uncertain": False,
            "raw_class": raw_class,
            "disease_key": disease_key,
            "recommendation_source": "cautious local healthy-class guidance",
        }

    if not result:
        return _uncertain_local_model_result(
            model_analysis,
            "No crop-specific reference information matched this model class; treatment guidance was withheld.",
            model_timing,
        )

    result["diagnostic_note"] = " ".join(
        part for part in (
            str(result.get("diagnostic_note") or "").strip(),
            "This is a preliminary image-model result, not a confirmed diagnosis. "
            "Ask an agricultural expert to confirm, especially before taking treatment action.",
        ) if part
    )
    result["_analysis_source"] = "plantvillage_mobilenetv2+local_disease_knowledge_base"
    result["preliminary"] = True
    result["_timing_ms"] = {
        **model_timing,
        "external_ai_ms": 0.0,
        "explanation_ms": 0.0,
        "translation_ms": 0.0,
    }
    return result


def _uncertain_diagnosis(
    reason: str,
    crop: str = "",
    crop_confidence: Optional[float] = None,
) -> Dict[str, Any]:
    crop_is_uncertain = not crop
    confidence_pct = round(max(0.0, min(float(crop_confidence or 0.0), 1.0)) * 100)
    return {
        "ok": True,
        "is_valid_plant_image": True,
        "crop": crop,
        "crop_confidence": confidence_pct if crop_confidence is not None else None,
        "disease": "Crop identification uncertain" if crop_is_uncertain else "Disease identification uncertain",
        "confidence": None,
        "disease_confidence": None,
        "severity": None,
        "symptoms": [],
        "symptoms_basis": "unavailable",
        "possible_causes": [],
        "causes": [],
        "recommended_management": [],
        "treatment": [],
        "prevention": [],
        "diagnostic_note": (
            f"{reason} Please upload a clear, close-up image of one leaf and consult a local "
            "agricultural extension officer if uncertainty remains."
        ),
        "is_healthy": False,
        "uncertain": True,
        "_analysis_source": "uncertain",
    }


def _class_name_for_diagnosis(crop: str, disease: str) -> Optional[str]:
    if not crop or not disease:
        return None
    crop_key = normalize_crop_for_key(crop)
    disease_text = disease.strip().lower()
    if "healthy" in disease_text or "no major disease" in disease_text:
        target_key = "healthy"
    else:
        disease_component = disease_text.split("___")[-1]
        disease_component = re.sub(r"[^a-z0-9]+", "_", disease_component).strip("_")
        disease_component = re.sub(r"_+", "_", disease_component)
        aliases = {
            "bacterial_leaf_spot": "bacterial_spot",
            "bacterial_spot": "bacterial_spot",
            "citrus_greening": "haunglongbing",
            "greening": "haunglongbing",
            "huanglongbing": "haunglongbing",
            "haunglongbing": "haunglongbing",
            "yellow_leaf_curl_virus": "tomato_yellow_leaf_curl",
            "tomato_yellow_leaf_curl_virus": "tomato_yellow_leaf_curl",
            "tomato_yellow_leaf_curl": "tomato_yellow_leaf_curl",
            "black_measles": "esca",
            "esca_black_measles": "esca",
            "common_rust": "rust",
            "gray_leaf_spot": "leaf_spot",
            "septoria": "septoria_leaf_spot",
        }
        disease_component = aliases.get(disease_component, disease_component)
        target_key = map_class_to_disease_key(f"{crop}___{disease_component}")
    if target_key == "unknown":
        return None
    for class_name in get_supported_classes():
        class_crop, _ = split_class_name(class_name)
        if (
            normalize_crop_for_key(class_crop) == crop_key
            and map_class_to_disease_key(class_name) == target_key
        ):
            return class_name
    return None


def _build_curated_vision_result(
    norm: Dict[str, Any],
    crop: str,
    class_name: str,
    model_analysis: Optional[Dict[str, Any]],
) -> Optional[Dict[str, Any]]:
    generic_key = map_class_to_disease_key(class_name)
    disease_key = build_crop_disease_key(crop, generic_key)
    knowledge = lookup_disease_knowledge(crop, disease_key, generic_key)
    if not knowledge:
        return None

    treatment_fallback = (
        "No chemical treatment is recommended by this application. Contact a local agricultural "
        "extension officer for crop- and disease-specific options approved for your area."
    )
    local_crop_confidence = None
    local_disease_confidence = None
    local_prediction_disagrees = False
    if isinstance(model_analysis, dict) and model_analysis.get("ok") and not model_analysis.get("uncertain"):
        local_crop = str(model_analysis.get("crop") or "")
        local_class = str(model_analysis.get("raw_class") or "")
        local_prediction_disagrees = (
            normalize_crop_for_key(local_crop) != normalize_crop_for_key(crop)
            or map_class_to_disease_key(local_class) != generic_key
        )
        if not local_prediction_disagrees:
            local_crop_confidence = float(model_analysis.get("crop_confidence") or 0.0)
            local_disease_confidence = float(model_analysis.get("disease_confidence") or 0.0)

    crop_confidence = (
        local_crop_confidence
        if local_crop_confidence is not None
        else float(norm.get("crop_confidence") or 0.0) * 100.0
    )
    disease_confidence = (
        local_disease_confidence
        if local_disease_confidence is not None
        else float(norm.get("confidence") or 0.0) * 100.0
    )
    typical_symptoms = list(knowledge.get("symptoms") or [])
    visual_symptoms = list(norm.get("symptoms") or [])
    note = str(norm.get("diagnostic_note") or "").strip()
    note_parts = [note] if note else []
    if local_disease_confidence is not None:
        note_parts.append(
            "The visual analysis agrees with the local classifier's supported crop/disease class."
        )
    elif local_prediction_disagrees:
        note_parts.append(
            "The local classifier disagreed; this result follows the supported visual-analysis class."
        )
    note_parts.append(
        "Confidence values are model scores, not calibrated probabilities. Chemical instructions "
        "are omitted unless verified against current local product labels."
    )

    return {
        "ok": True,
        "is_valid_plant_image": True,
        "crop": crop,
        "crop_confidence": round(crop_confidence),
        "disease": str(knowledge.get("disease") or norm.get("disease") or ""),
        "confidence": round(disease_confidence),
        "disease_confidence": round(disease_confidence),
        "severity": norm.get("severity"),
        "symptoms": visual_symptoms or typical_symptoms,
        "symptoms_basis": "visual_observation" if visual_symptoms else "typical_reference",
        "possible_causes": list(knowledge.get("causes") or []),
        "causes": list(knowledge.get("causes") or []),
        "recommended_management": _safe_knowledge_list(
            knowledge.get("treatment"), treatment_fallback
        ),
        "treatment": _safe_knowledge_list(knowledge.get("treatment"), treatment_fallback),
        "prevention": _safe_knowledge_list(
            knowledge.get("prevention"),
            "Use disease-free planting material and ask a local extension officer about prevention for this crop.",
        ),
        "diagnostic_note": " ".join(note_parts),
        "is_healthy": generic_key == "healthy",
        "uncertain": False,
        "raw_class": class_name,
        "disease_key": disease_key,
        "recommendation_source": "local crop-specific disease knowledge base",
        "_analysis_source": (
            "gemini_vision+plantvillage_mobilenetv2"
            if local_disease_confidence is not None
            else "gemini_vision+crop_disease_knowledge_base"
        ),
    }


async def analyze_plant_image_gemini_primary(
    image_bytes: bytes,
    content_type: Optional[str] = None,
    optional_user_crop_hint: str = "",
    response_language: str = "en",
    decoded_rgb: Any = None,
) -> Dict[str, Any]:
    """Use supported local predictions first; use Gemini when the local model is unavailable."""

    model_context_note: str = ""
    model_context_for_debug: Optional[Dict[str, Any]] = None
    model_analysis: Optional[Dict[str, Any]] = None
    pred: Optional[Dict[str, Any]] = None
    model_timing: Dict[str, float] = {}
    model_started = time.perf_counter()
    try:
        pred = await asyncio.to_thread(predict_disease, image_bytes, decoded_rgb)
        model_timing = pred.get("_timing_ms", {})
        model_analysis = analyze_prediction(pred)
        if isinstance(model_analysis, dict) and model_analysis.get("ok"):
            model_context_for_debug = {
                "crop": model_analysis.get("crop") or "",
                "disease": model_analysis.get("disease") or "",
                "crop_confidence": model_analysis.get("crop_confidence") or 0.0,
                "disease_confidence": model_analysis.get("disease_confidence") or 0.0,
                "is_healthy": bool(model_analysis.get("is_healthy")),
                "raw_class": model_analysis.get("raw_class") or "",
                "top5": model_analysis.get("top5"),
                "disease_key": model_analysis.get("disease_key"),
                "generic_disease_key": model_analysis.get("generic_disease_key"),
                "class_index": model_analysis.get("class_index"),
            }
    except Exception as mex:
        logger.debug("Local disease model failed: %s", type(mex).__name__)
        model_analysis = None
    finally:
        logger.info(
            "Disease timing stage=local_model elapsed_ms=%.1f",
            (time.perf_counter() - model_started) * 1000,
        )

    if isinstance(model_analysis, dict) and model_analysis.get("ok"):
        local_started = time.perf_counter()
        local_result = _build_local_model_result(model_analysis, model_timing)
        local_result["_timing_ms"]["explanation_ms"] = round(
            (time.perf_counter() - local_started) * 1000, 1
        )
        logger.info(
            "Disease timing stage=local_result elapsed_ms=%.1f source=%s",
            (time.perf_counter() - local_started) * 1000,
            local_result.get("_analysis_source"),
        )
        return local_result
    if (
        isinstance(model_analysis, dict)
        and isinstance(pred, dict)
        and pred.get("class_name")
        and not pred.get("mock_predictor")
    ):
        local_started = time.perf_counter()
        local_result = _uncertain_local_model_result(
            model_analysis,
            "The model could not confidently identify a supported crop and disease class.",
            model_timing,
        )
        local_result["_timing_ms"]["explanation_ms"] = round(
            (time.perf_counter() - local_started) * 1000, 1
        )
        logger.info(
            "Disease timing stage=local_result elapsed_ms=%.1f source=%s rejection=%s",
            (time.perf_counter() - local_started) * 1000,
            local_result.get("_analysis_source"),
            model_analysis.get("error_type", "uncertain"),
        )
        return local_result

    if model_context_for_debug:
        model_context_note = (
            "\n\nOptional local classifier reference (not a diagnosis; independently "
            "verify crop and symptoms from the uploaded image): "
            + json.dumps(
                {
                    "crop": model_context_for_debug["crop"],
                    "disease": model_context_for_debug["disease"],
                    "crop_confidence": model_context_for_debug["crop_confidence"],
                    "disease_confidence": model_context_for_debug["disease_confidence"],
                },
                ensure_ascii=False,
            )
        )

    user_crop_hint_note = ""
    if optional_user_crop_hint and isinstance(optional_user_crop_hint, str) and optional_user_crop_hint.strip():
        user_crop_hint_note = (
            "\n\nUser-registered profile crop hint (again, VERIFY from image only — do not trust blindly): "
            f"{optional_user_crop_hint.strip()}. Disregard if the plant in the image visually differs."
        )

    language_name = LANGUAGE_NAMES[response_language]
    language_instructions = (
        f"\n\nWrite user-facing text in {language_name}. Keep crop and disease identifiers canonical "
        "in English, and use the requested language for crop_display, disease_display, diagnostic_note, "
        "symptoms, possible_causes, recommended_management, prevention, and error. Preserve scientific "
        "organism names, JSON keys, and numeric values."
    )
    user_text = (
        "Analyze the accompanying plant image according to your system instructions."
        + model_context_note
        + user_crop_hint_note
        + language_instructions
        + "\nReturn ONLY the valid JSON object as specified — no extra text."
    )

    raw_text: Optional[str] = None
    gemini_ok = False
    gemini_err_desc = ""
    gemini_error_type = "gemini_vision_unavailable"
    inference_started = time.perf_counter()
    try:
        raw_text = await call_gemini_vision(
            image_bytes=image_bytes,
            content_type=content_type,
            text_message=user_text,
            system_prompt=_GEMINI_VISION_PLANT_SYSTEM_PROMPT,
        )
        if raw_text:
            gemini_ok = True
    except GeminiVisionUnavailable as gex:
        gemini_error_type = gex.error_type
        gemini_err_desc = str(gex)
        logger.warning("Gemini primary analysis unavailable error_type=%s", gemini_error_type)
    except Exception as gex:
        gemini_error_type = "gemini_provider_unavailable"
        gemini_err_desc = type(gex).__name__
        logger.warning("Gemini primary analysis failed exception=%s", gemini_err_desc)
    inference_elapsed_ms = round((time.perf_counter() - inference_started) * 1000, 1)

    if not gemini_ok or not raw_text:
        err_reason = gemini_err_desc or "Gemini Vision API returned empty or all endpoints failed."
        local_model_unavailable = (
            isinstance(model_analysis, dict)
            and model_analysis.get("error_type") == "model_unavailable"
        )
        public_errors = {
            "gemini_api_key_missing": "Disease analysis is not configured on the server. Set GEMINI_API_KEY in the backend environment.",
            "gemini_auth_error": "The Gemini API key is invalid, expired, or lacks model access. Replace GEMINI_API_KEY in the backend environment with a valid key that has Gemini API access.",
            "gemini_quota_exceeded": "Gemini API quota or rate limit reached. Please try again later or check the provider quota.",
            "gemini_model_unavailable": "No configured Gemini Vision model is available. Check the backend model configuration and API access.",
            "gemini_request_rejected": "Gemini rejected this image analysis request. Please try a different image.",
            "gemini_provider_unavailable": "Gemini Vision is temporarily unreachable. Check the backend network connection and provider status.",
            "gemini_provider_busy": "Gemini is temporarily experiencing high demand. Please wait a moment and try again.",
            "gemini_provider_error": "Gemini is temporarily unable to process image analysis. Please try again shortly.",
            "gemini_empty_response": "Gemini returned no usable analysis. Please retry with a clear, close-up photo.",
            "gemini_safety_blocked": "Gemini safety filters blocked this analysis request. No diagnosis was produced; try an appropriate, non-sensitive plant image.",
        }
        base_fail: Dict[str, Any] = {
            "ok": False,
            "error": public_errors.get(
                gemini_error_type,
                "Unable to determine disease from the image. Visual analysis service is temporarily unavailable. Please try again later.",
            ),
            "error_type": gemini_error_type,
            "_analysis_source": "gemini_vision_primary",
            "_gemini_detail": err_reason,
        }
        if local_model_unavailable:
            base_fail["_local_model_status"] = "unavailable"
        base_fail["_timing_ms"] = {
            **model_timing,
            "external_ai_ms": inference_elapsed_ms,
            "explanation_ms": 0.0,
            "translation_ms": 0.0,
        }
        if model_context_for_debug:
            base_fail["_model_prediction_fallback_hint"] = model_context_for_debug
        return base_fail

    parsed = _parse_llm_json(raw_text)
    if parsed is None:
        base_fail2: Dict[str, Any] = {
            "ok": False,
            "error": (
                "Visual analysis produced an unreadable response. Please try again with a clearer, "
                "well-lit close-up photo of the leaf/fruit."
            ),
            "error_type": "gemini_response_parse_failed",
            "_analysis_source": "gemini_vision_primary",
        }
        if model_context_for_debug:
            base_fail2["_model_prediction_fallback_hint"] = model_context_for_debug
        base_fail2["_timing_ms"] = {
            **model_timing,
            "external_ai_ms": inference_elapsed_ms,
            "explanation_ms": 0.0,
            "translation_ms": 0.0,
        }
        return base_fail2

    norm = _validate_and_normalize_vision_result(parsed)
    norm["_timing_ms"] = {"gemini": inference_elapsed_ms}

    if not norm["is_valid_plant_image"]:
        disease_str = "Unknown / Cannot determine reliably"
        is_healthy = False
    else:
        raw_crop = norm["crop"]
        crop_display, crop_supported, original_crop = match_declared_crop(raw_crop)
        if not raw_crop or norm["crop_confidence"] is None:
            uncertain_result = _uncertain_diagnosis(
                "Crop identification uncertain because the visual analysis did not provide a separate, usable crop-confidence score."
            )
            uncertain_result["_timing_ms"] = {
                **model_timing,
                "external_ai_ms": inference_elapsed_ms,
                "explanation_ms": 0.0,
                "translation_ms": 0.0,
            }
            return uncertain_result
        crop_confidence = float(norm["crop_confidence"])
        minimum_confidence = float(load_inference_config()["uncertain_top1_confidence"]) / 100.0
        if crop_confidence < minimum_confidence:
            uncertain_result = _uncertain_diagnosis(
                f"Crop identification uncertain (crop score {crop_confidence * 100:.1f}% is below the conservative threshold).",
                crop=crop_display if crop_supported else "",
                crop_confidence=crop_confidence,
            )
            uncertain_result["_timing_ms"] = {
                **model_timing,
                "external_ai_ms": inference_elapsed_ms,
                "explanation_ms": 0.0,
                "translation_ms": 0.0,
            }
            return uncertain_result
        if not crop_supported or not crop_display:
            unsupported_result = {
                "ok": False,
                "error": (
                    f"The image appears to show {original_crop or raw_crop}, which is not in the "
                    "PlantVillage model's supported crop classes. This app cannot provide a validated "
                    "disease diagnosis for it."
                ),
                "error_type": "unsupported_crop",
                "supported_crops": get_supported_crops(),
                "_analysis_source": "gemini_vision",
            }
            unsupported_result["_timing_ms"] = {
                **model_timing,
                "external_ai_ms": inference_elapsed_ms,
                "explanation_ms": 0.0,
                "translation_ms": 0.0,
            }
            return unsupported_result

        disease_text = str(norm["disease"] or "").strip()
        if (
            not disease_text
            or disease_text.lower() in ("unknown", "unknown / cannot determine reliably")
            or norm["confidence"] is None
            or float(norm["confidence"]) < minimum_confidence
        ):
            uncertain_result = _uncertain_diagnosis(
                "Disease identification uncertain; the image did not provide enough evidence for a supported diagnosis.",
                crop=crop_display,
                crop_confidence=crop_confidence,
            )
            uncertain_result["_timing_ms"] = {
                **model_timing,
                "external_ai_ms": inference_elapsed_ms,
                "explanation_ms": 0.0,
                "translation_ms": 0.0,
            }
            return uncertain_result

        class_names_for_crop = [
            class_name
            for class_name in get_supported_classes()
            if normalize_crop_for_key(split_class_name(class_name)[0])
            == normalize_crop_for_key(crop_display)
        ]
        if (
            len(class_names_for_crop) == 1
            and "healthy" in class_names_for_crop[0].lower()
        ):
            uncertain_result = _uncertain_diagnosis(
                f"{crop_display} has only a healthy-leaf class in the available PlantVillage model, so disease detection for this crop is not supported.",
                crop=crop_display,
                crop_confidence=crop_confidence,
            )
            uncertain_result["_timing_ms"] = {
                **model_timing,
                "external_ai_ms": inference_elapsed_ms,
                "explanation_ms": 0.0,
                "translation_ms": 0.0,
            }
            return uncertain_result

        class_name = _class_name_for_diagnosis(crop_display, disease_text)
        if not class_name:
            uncertain_result = _uncertain_diagnosis(
                f"The reported disease does not match a validated class for {crop_display}; no crop-specific treatment was attached.",
                crop=crop_display,
                crop_confidence=crop_confidence,
            )
            uncertain_result["_timing_ms"] = {
                **model_timing,
                "external_ai_ms": inference_elapsed_ms,
                "explanation_ms": 0.0,
                "translation_ms": 0.0,
            }
            return uncertain_result

        explanation_started = time.perf_counter()
        curated_result = _build_curated_vision_result(
            norm, crop_display, class_name, model_analysis
        )
        explanation_elapsed_ms = (time.perf_counter() - explanation_started) * 1000
        if not curated_result:
            uncertain_result = _uncertain_diagnosis(
                "No crop-specific validated recommendation entry matched the predicted disease; treatment guidance was withheld.",
                crop=crop_display,
                crop_confidence=crop_confidence,
            )
            uncertain_result["_timing_ms"] = {
                **model_timing,
                "external_ai_ms": inference_elapsed_ms,
                "explanation_ms": round(explanation_elapsed_ms, 1),
                "translation_ms": 0.0,
            }
            return uncertain_result
        curated_result["_timing_ms"] = {
            **model_timing,
            "external_ai_ms": inference_elapsed_ms,
            "explanation_ms": round(explanation_elapsed_ms, 1),
            "translation_ms": 0.0,
        }
        return curated_result

    # Non-plant responses are returned in the established API shape.
    norm["crop"] = ""
    norm["disease"] = disease_str

    result: Dict[str, Any] = {
        "ok": True,
        "is_valid_plant_image": bool(norm["is_valid_plant_image"]),
        "crop": norm["crop"],
        "crop_display": norm["crop_display"],
        "disease": disease_str if disease_str else "Unknown / Cannot determine reliably",
        "disease_display": norm["disease_display"],
        "confidence": None,
        "disease_confidence": None,
        "severity": norm["severity"],
        "symptoms": norm["symptoms"],
        "possible_causes": norm["possible_causes"],
        "recommended_management": norm["recommended_management"],
        "prevention": norm["prevention"],
        "diagnostic_note": norm["diagnostic_note"],
        "causes": norm["possible_causes"],
        "treatment": norm["recommended_management"],
        "is_healthy": False,
        "_analysis_source": "gemini_vision_primary",
        "_timing_ms": {
            **model_timing,
            "external_ai_ms": inference_elapsed_ms,
            "explanation_ms": 0.0,
            "translation_ms": 0.0,
        },
    }

    result["crop_confidence"] = None
    if model_context_for_debug:
        result["_model_context"] = model_context_for_debug

    if not norm["is_valid_plant_image"]:
        result["error"] = (
            "Uploaded image does not appear to contain a recognizable plant, leaf, or crop tissue."
            " Please upload a clear close-up photo."
        )
        result["error_type"] = "non_plant_image"

    result["crop_original"] = result["crop"]
    result["disease_original"] = result["disease"]
    result["crop_display"] = result["crop_display"] or result["crop"]
    result["disease_display"] = result["disease_display"] or result["disease"]

    if not result.get("recommended_management") and result.get("treatment"):
        result["recommended_management"] = list(result["treatment"])
    if not result.get("possible_causes") and result.get("causes"):
        result["possible_causes"] = list(result["causes"])

    return result


_DISEASE_REC_SYSTEM_PROMPT = """You are an expert agricultural plant pathologist and extension officer for smallholder farmers.
Your task: Based on a crop + disease detected via AI image analysis, produce a structured farmer-friendly disease information package.
Be accurate, specific, actionable, and India-relevant where possible (crops, cultivars, local IPM practices, extension program guidance).

Strict output format: Only valid JSON, top-level keys exactly:
- severity: short string "Mild" / "Moderate" / "Moderate to Severe" / "Severe" as appropriate for this disease (NOT based on model confidence %)
- symptoms: array of 3-5 concise specific symptom bullets, tailored to this EXACT crop + disease combination, generic crop language forbidden
- causes: array of 3-5 specific cause/epidemiology bullets mentioning pathogen genus/species where known
- treatment: array of 4-6 control options ordered as: (1) Cultural / Sanitation / Canopy management first, (2) Biological / Organic / Biocontrol options, then (3) Chemical / Synthetic options ONLY IF clearly documented for this crop+disease pair. DO NOT invent pesticide product names, dosages, concentrations, mixing ratios, spray volumes, g/L or mL/L numbers, kg/ha rates, percentages, or ppm values. Instead of inventing doses, write a clear directive like: "Any chemical product must match locally registered agrochemicals for this crop and disease; always read and follow the product label, local agricultural extension recommendations, and respect re-entry interval / pre-harvest interval."
- prevention: array of 5-7 crop-specific management / preventive practices.

CRITICAL RULES:
1. NEVER invent pesticide / fungicide / bactericide brand names, specific dosages, concentrations (%, g/L, mL/L, kg/ha, ppm, etc.), or mixing ratios. For any chemical control mention, always add the directive that the farmer must use only locally registered products, follow the product label, and follow local agricultural extension recommendations.
2. NEVER reuse the exact same text between different crop+disease pairs; the generated content must differ between tomato_late_blight vs potato_late_blight vs pepper_bacterial_spot etc.
3. Do NOT output commentary, markdown, backticks, or explanation — ONLY the JSON object.
4. If input disease is "Healthy" / no disease detected, produce a healthy-crop maintenance package under the same 5 keys with symptoms as "No disease symptoms observed; leaves and canopy appear vigorous and uniform", causes listing "Good farm management practices maintained", and treatment/prevention covering appropriate crop care, scouting, nutrition, and preventive canopy / phytosanitary practices.
"""


async def generate_dynamic_disease_recommendation(
    crop: str,
    disease: str,
    is_healthy: bool,
    crop_confidence: float,
    disease_confidence: float,
    raw_class: str = "",
) -> Optional[Dict[str, Any]]:
    """Dynamically generate disease info (symptoms/causes/treatment/prevention/severity) via LLM
    based purely on the detected crop + disease from the image. Returns dict with the 5 keys
    or None if LLM unavailable / fails to produce valid JSON."""
    if not _get_gemini_api_key() and not settings.OPENAI_API_KEY:
        return None
    disease_label = disease or ("Healthy Leaf / No Major Disease Detected" if is_healthy else "Unknown disease")
    user_msg = (
        f"Detected via MobileNetV2 image model:\n"
        f"- Crop: {crop or 'Unknown'}\n"
        f"- Disease: {disease_label}\n"
        f"- Model raw class label: {raw_class or 'N/A'}\n"
        f"- Crop identification confidence: {crop_confidence:.1f}%\n"
        f"- Disease identification confidence: {disease_confidence:.1f}%\n"
        f"- Healthy result: {'Yes' if is_healthy else 'No'}\n\n"
        f"Please output ONLY the JSON object described in your system prompt. No extra text."
    )
    try:
        raw_text = await call_ai_model(user_msg, _DISEASE_REC_SYSTEM_PROMPT)
        if not raw_text:
            return None
        text = raw_text.strip()
        if text.startswith("```"):
            text = re.sub(r"^```(?:json)?", "", text)
            text = re.sub(r"```$", "", text)
            text = text.strip()
        # Try direct parse first
        obj = None
        parse_errors = []
        try:
            obj = json.loads(text)
        except json.JSONDecodeError as e1:
            parse_errors.append(f"direct: {str(e1)[:100]}")
            # Try extracting the first {...} block with a regex
            m = re.search(r"\{[\s\S]*\}", text)
            if m:
                candidate = m.group(0)
                try:
                    obj = json.loads(candidate)
                except json.JSONDecodeError as e2:
                    parse_errors.append(f"regex-block: {str(e2)[:100]}")
            if obj is None:
                # Try line-by-line repair: escape unescaped newlines / backslashes inside string values
                repaired = re.sub(r'(?<!\\)\\(?!["\\/bfnrtu])', r'\\\\', text)
                try:
                    obj = json.loads(repaired)
                except json.JSONDecodeError as e3:
                    parse_errors.append(f"backslash-repair: {str(e3)[:100]}")
        if obj is None:
            print(f"[disease-dyn-reco] JSON parse failed all attempts: {parse_errors}. Text preview: {text[:200]!r}")
            # Salvage attempt: close all unterminated strings / arrays / objects then try to parse
            salvage = text.rstrip()
            # Remove trailing comma(s)
            salvage = re.sub(r",+\s*$", "", salvage)
            # Close any open double-quoted string value (most common truncation)
            in_str = False
            escaped = False
            opens = []  # stack of '{' or '[' brackets
            close_needed = []
            for i, ch in enumerate(salvage):
                if escaped:
                    escaped = False
                    continue
                if ch == '\\':
                    escaped = True
                    continue
                if ch == '"':
                    in_str = not in_str
                    continue
                if in_str:
                    continue
                if ch in '{[':
                    opens.append(ch)
                elif ch == '}]':
                    if opens:
                        opens.pop()
            if in_str:
                salvage += '"'
                in_str = False
            # Close any remaining open braces/brackets in reverse LIFO order
            while opens:
                last = opens.pop()
                needed = '}' if last == '{' else ']'
                salvage = salvage.rstrip()
                if not salvage.endswith(needed):
                    salvage += needed
            try:
                obj = json.loads(salvage)
                print(f"[disease-dyn-reco] Salvage parse SUCCESS after closing brackets/strings.")
            except json.JSONDecodeError as ex_salvage:
                print(f"[disease-dyn-reco] Salvage parse failed: {ex_salvage}. Salvaged text: {salvage[-250:]!r}")
                return None
        if not isinstance(obj, dict):
            return None
        severity = obj.get("severity")
        symptoms = obj.get("symptoms") or []
        causes = obj.get("causes") or []
        treatment = obj.get("treatment") or []
        prevention = obj.get("prevention") or []
        if not isinstance(symptoms, list) or not isinstance(causes, list) \
                or not isinstance(treatment, list) or not isinstance(prevention, list):
            return None
        cleaned = {
            "severity": str(severity) if severity else ("Mild (None)" if is_healthy else "Moderate"),
            "symptoms": [str(s).strip() for s in symptoms if str(s).strip()],
            "causes": [str(c).strip() for c in causes if str(c).strip()],
            "treatment": [str(tr).strip() for tr in treatment if str(tr).strip()],
            "prevention": [str(p).strip() for p in prevention if str(p).strip()],
        }
        if is_healthy and not cleaned["severity"].lower().startswith("mild"):
            cleaned["severity"] = "Mild (None)"
        return cleaned
    except (httpx.HTTPError, json.JSONDecodeError, Exception) as exc:
        print(f"[disease-dyn-reco] LLM generation failed: {exc}")
        return None


async def _translate_model_diagnosis(
    result: Dict[str, Any],
    language: str,
) -> Dict[str, Any]:
    """Translate model-backed display text without changing the classifier's canonical labels."""
    language = resolve_language(language)
    original_result = dict(result)
    if language == "en":
        return localize_disease_result(original_result, language)
    if not original_result.get("possible_causes") and original_result.get("causes"):
        original_result["possible_causes"] = original_result["causes"]
    if not original_result.get("recommended_management") and original_result.get("treatment"):
        original_result["recommended_management"] = original_result["treatment"]

    fields = {
        key: original_result.get(key)
        for key in (
            "crop", "disease", "severity", "symptoms", "possible_causes",
            "recommended_management", "prevention", "safety_warnings", "warnings",
            "precautions", "diagnostic_note", "error",
        )
        if original_result.get(key) is not None
    }
    target_script = {
        "mr": "Devanagari script",
        "hi": "Devanagari script",
        "ml": "Malayalam script",
    }.get(language, "English")
    prompt = (
        "Translate every user-facing text value in this JSON object into "
        f"{LANGUAGE_NAMES[language]}, using {target_script}. Translate every sentence "
        "and every list item; do not leave English prose untranslated. Preserve JSON shape, "
        "list order, and meaning. Do not change crop or disease identifiers, confidence "
        "values, scientific names, or severity facts. Keep canonical crop and disease "
        "values unchanged and add crop_display and disease_display with natural localized "
        "names. For non-English languages, include the original English disease name in "
        "parentheses; do not duplicate it for English. Do not add recommendations or facts. "
        "Return only valid JSON with the same fields plus crop_display and disease_display.\n\n"
        + json.dumps(fields, ensure_ascii=False)
    )
    try:
        raw = await call_ai_model(
            prompt,
            "You are a careful agricultural translator. Translate only; do not add, remove, or alter facts.",
            raise_on_failure=True,
            temperature=0.0,
            max_tokens=4096,
            use_groq=True,
        )
    except AIProviderUnavailable as exc:
        logger.warning(
            "Disease translation provider unavailable language=%s reason=%s; using verified local translations",
            language,
            exc.reason,
        )
        return localize_disease_result(original_result, language)
    except Exception as exc:
        logger.warning(
            "Disease result translation failed language=%s error_type=%s; using verified local translations",
            language,
            type(exc).__name__,
        )
        return localize_disease_result(original_result, language)

    translated = _parse_llm_json(raw or "")
    if not isinstance(translated, dict):
        logger.warning("Disease result translation returned no usable JSON")
        return localize_disease_result(original_result, language)

    target_script_pattern = {
        "mr": re.compile(r"[\u0900-\u097f]"),
        "hi": re.compile(r"[\u0900-\u097f]"),
        "ml": re.compile(r"[\u0d00-\u0d7f]"),
    }.get(language)

    def is_translated_text(value: str) -> bool:
        return target_script_pattern is None or bool(target_script_pattern.search(value))

    translated_result = dict(original_result)
    translation_complete = True
    incomplete_fields = []
    for key in ("severity", "diagnostic_note", "error"):
        value = translated.get(key)
        if isinstance(value, str) and value.strip() and is_translated_text(value):
            translated_result[key] = value.strip()
        elif original_result.get(key):
            translation_complete = False
            incomplete_fields.append(key)
    for key in (
        "symptoms", "possible_causes", "recommended_management", "prevention",
        "safety_warnings", "warnings", "precautions",
    ):
        items = translated.get(key)
        if (
            isinstance(items, list)
            and len(items) == len(original_result.get(key) or [])
            and all(
                isinstance(item, str) and item.strip() and is_translated_text(item)
                for item in items
            )
        ):
            translated_result[key] = [str(item) for item in items]
        elif original_result.get(key):
            translation_complete = False
            incomplete_fields.append(key)

    crop_display = translated.get("crop_display")
    disease_display = translated.get("disease_display")
    translated_result["crop_display"] = (
        crop_display.strip()
        if isinstance(crop_display, str) and crop_display.strip()
        else original_result.get("crop_display") or original_result.get("crop") or ""
    )
    translated_result["disease_display"] = (
        disease_display.strip()
        if isinstance(disease_display, str) and disease_display.strip()
        else original_result.get("disease_display") or original_result.get("disease") or ""
    )
    if not (
        isinstance(crop_display, str)
        and crop_display.strip()
        and is_translated_text(crop_display)
    ):
        translation_complete = False
        incomplete_fields.append("crop_display")
    if not (
        isinstance(disease_display, str)
        and disease_display.strip()
        and is_translated_text(disease_display)
    ):
        translation_complete = False
        incomplete_fields.append("disease_display")
    if not translation_complete:
        logger.warning(
            "Disease result translation incomplete language=%s fields=%s; using verified local translations where available",
            language,
            ",".join(dict.fromkeys(incomplete_fields)),
        )
        return localize_disease_result(original_result, language)

    translated_result["crop_original"] = original_result.get("crop")
    translated_result["disease_original"] = original_result.get("disease")
    translated_result["severity_original"] = original_result.get("severity")
    translated_result["causes"] = translated_result.get(
        "possible_causes", translated_result.get("causes", [])
    )
    translated_result["treatment"] = translated_result.get(
        "recommended_management", translated_result.get("treatment", [])
    )
    translated_result["_translation_complete"] = True
    return translated_result


async def detect_crop_disease(
    image_bytes: bytes,
    crop: str = "",
    language: str = "en",
    content_type: Optional[str] = None,
    decoded_rgb: Any = None,
) -> Dict[str, Any]:
    """Return a supported local diagnosis or an uncertainty result before using provider fallback."""
    if image_bytes is None or len(image_bytes) == 0:
        return {
            "ok": False,
            "error": "Could not read the uploaded image. Please upload a valid JPG, PNG, or WebP plant image.",
            "error_type": "image_invalid",
        }
    analysis_started = time.perf_counter()
    try:
        result = await analyze_plant_image_gemini_primary(
            image_bytes=image_bytes,
            content_type=content_type,
            optional_user_crop_hint=crop,
            response_language=language,
            decoded_rgb=decoded_rgb,
        )
        if isinstance(result, dict):
            result["_timing_ms"] = {
                **result.get("_timing_ms", {}),
                "disease_analysis_ms": round(
                    (time.perf_counter() - analysis_started) * 1000, 1
                )
            }
        return result
    finally:
        logger.info(
            "Disease timing stage=analysis language=%s elapsed_ms=%.1f separate_translation_calls=0",
            language,
            (time.perf_counter() - analysis_started) * 1000,
        )


class AIProviderUnavailable(RuntimeError):
    def __init__(self, reason: str):
        super().__init__(reason)
        self.reason = reason


def _openai_error_reason(exc: Exception) -> str:
    from openai import (
        APIConnectionError,
        APIStatusError,
        APITimeoutError,
        AuthenticationError,
        OpenAIError,
        PermissionDeniedError,
        RateLimitError,
    )

    if isinstance(exc, APITimeoutError):
        return "timeout"
    if isinstance(exc, (AuthenticationError, PermissionDeniedError)):
        return "openai_auth"
    if isinstance(exc, RateLimitError):
        body = getattr(exc, "body", None)
        error = body.get("error", body) if isinstance(body, dict) else {}
        if not isinstance(error, dict):
            error = {}
        error_code = str(error.get("code") or error.get("type") or "").lower()
        error_message = str(error.get("message") or "").lower()
        if (
            error_code in {"insufficient_quota", "billing_hard_limit_reached", "quota_exceeded"}
            or "quota" in error_message
            or "billing" in error_message
        ):
            return "openai_quota_exceeded"
        return "openai_rate_limit"
    if isinstance(exc, APIConnectionError):
        return "connection_error"
    if isinstance(exc, (APIStatusError, OpenAIError)):
        return "provider_error"
    return "provider_error"


def _raise_openai_unavailable(exc: Exception, model: str) -> None:
    reason = _openai_error_reason(exc)
    logger.warning(
        "OpenAI chat request failed reason=%s status=%s error_type=%s model=%s",
        reason,
        getattr(exc, "status_code", None) or "n/a",
        type(exc).__name__,
        model,
    )
    raise AIProviderUnavailable(reason) from exc


def _groq_error_reason(exc: Exception) -> str:
    from openai import (
        APIConnectionError,
        APIStatusError,
        APITimeoutError,
        AuthenticationError,
        OpenAIError,
        PermissionDeniedError,
        RateLimitError,
    )

    if isinstance(exc, APITimeoutError):
        return "timeout"
    if isinstance(exc, (AuthenticationError, PermissionDeniedError)):
        return "groq_auth"
    if isinstance(exc, RateLimitError):
        body = getattr(exc, "body", None)
        error = body.get("error", body) if isinstance(body, dict) else {}
        if not isinstance(error, dict):
            error = {}
        error_code = str(error.get("code") or error.get("type") or "").lower()
        error_message = str(error.get("message") or "").lower()
        if (
            error_code in {"insufficient_quota", "billing_hard_limit_reached", "quota_exceeded"}
            or "quota" in error_message
            or "billing" in error_message
        ):
            return "groq_quota_exceeded"
        return "groq_rate_limited"
    if isinstance(exc, APIConnectionError):
        return "connection_error"
    if isinstance(exc, APIStatusError):
        if exc.status_code in (400, 404):
            return "groq_model_unavailable"
        return "provider_error"
    if isinstance(exc, OpenAIError):
        return "provider_error"
    return "provider_error"


def _raise_groq_unavailable(exc: Exception, model: str) -> None:
    reason = _groq_error_reason(exc)
    logger.warning(
        "Groq chat request failed reason=%s status=%s error_type=%s model=%s",
        reason,
        getattr(exc, "status_code", None) or "n/a",
        type(exc).__name__,
        model,
    )
    raise AIProviderUnavailable(reason) from exc


async def _verify_groq_model(client, api_key: str, model: str) -> None:
    if not model:
        raise AIProviderUnavailable("groq_model_not_configured")
    key_fingerprint = hashlib.sha256(api_key.encode("utf-8")).hexdigest()
    cache_key = (key_fingerprint, model)
    cached_until = _groq_model_cache.get(cache_key, 0.0)
    if cached_until > time.monotonic():
        return

    try:
        available_models = await client.models.list()
        model_ids = set()
        async for available in available_models:
            model_id = getattr(available, "id", "")
            if isinstance(model_id, str):
                model_ids.add(model_id)
    except Exception as exc:
        from openai import OpenAIError

        if isinstance(exc, OpenAIError):
            _raise_groq_unavailable(exc, model)
        raise

    if model not in model_ids:
        logger.warning("Configured Groq model is not available model=%s", model)
        raise AIProviderUnavailable("groq_model_unavailable")
    _groq_model_cache[cache_key] = time.monotonic() + GROQ_MODEL_CACHE_SECONDS


def _httpx_transport_error_reason(error: httpx.HTTPError) -> str:
    if isinstance(error, httpx.TimeoutException):
        return "timeout"
    if isinstance(error, httpx.ConnectError):
        cause = error.__cause__
        while cause is not None:
            if isinstance(cause, socket.gaierror):
                return "dns_error"
            cause = cause.__cause__
        return "connection_error"
    if isinstance(error, httpx.NetworkError):
        return "connection_error"
    return "service"


async def call_gemini(
    message: str,
    system_prompt: str,
    history: Optional[List[Dict[str, str]]] = None,
) -> Optional[str]:
    api_key = _get_gemini_api_key()
    if not api_key:
        return None
    if _gemini_quota_cooldown_active():
        raise AIProviderUnavailable("quota_exceeded")

    candidate_endpoints = [_get_gemini_model()]

    contents: List[Dict[str, Any]] = []
    for item in (history or [])[-6:]:
        role = item.get("role")
        content = item.get("content", "").strip()
        if role in ("user", "assistant") and content:
            contents.append({
                "role": "model" if role == "assistant" else "user",
                "parts": [{"text": content[:1500]}],
            })
    contents.append({"role": "user", "parts": [{"text": message}]})

    base_payload = {
        "systemInstruction": {
            "parts": [{"text": system_prompt}]
        },
        "contents": contents,
        "generationConfig": {
            "maxOutputTokens": 1536,
            "temperature": 0.7,
        }
    }

    client = _get_chat_http_client()
    started = asyncio.get_running_loop().time()
    last_reason = "service"
    for model_name in candidate_endpoints:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent"
        headers = {
            "Content-Type": "application/json",
            "x-goog-api-key": api_key,
        }
        for attempt in range(GEMINI_TRANSIENT_RETRIES + 1):
            try:
                response = await client.post(url, json=base_payload, headers=headers)
                details = (
                    _gemini_error_details(response, api_key)
                    if response.status_code != 200
                    else {}
                )
                if response.status_code in (401, 403) or (
                    response.status_code == 400
                    and details.get("reason") in ("API_KEY_INVALID", "API_KEY_EXPIRED")
                ):
                    last_reason = "auth"
                    break
                if response.status_code == 429:
                    provider_message = details.get("message", "")
                    last_reason = (
                        "quota_exceeded"
                        if _gemini_429_error_type(provider_message) == "gemini_quota_exceeded"
                        else "rate_limit"
                    )
                    if last_reason == "quota_exceeded":
                        _mark_gemini_quota_exhausted()
                    logger.warning(
                        "Gemini chat request received HTTP 429 model=%s provider_status=%s "
                        "retry_after=%s detail=%s",
                        model_name,
                        details.get("status", ""),
                        details.get("retry_after", ""),
                        provider_message,
                    )
                    break
                if response.status_code == 404:
                    last_reason = "model_unavailable"
                    logger.warning(
                        "Gemini chat model unavailable model=%s status=%s",
                        model_name,
                        response.status_code,
                    )
                    break
                if response.status_code >= 500:
                    last_reason = "provider_error"
                    logger.warning(
                        "Gemini chat provider error model=%s status=%s",
                        model_name,
                        response.status_code,
                    )
                    if attempt < GEMINI_TRANSIENT_RETRIES:
                        await asyncio.sleep(
                            GEMINI_RETRY_BASE_DELAY_SECONDS * (2 ** attempt)
                        )
                        continue
                    break
                response.raise_for_status()
                data = response.json()
                candidates = data.get("candidates") or []
                if not candidates:
                    last_reason = "service"
                    break
                first_candidate = candidates[0]
                finish = first_candidate.get("finishReason", "")
                if finish and finish not in ("STOP", "MAX_TOKENS", ""):
                    logger.warning("Gemini chat response ended without an answer finish_reason=%s", finish)
                    last_reason = "service"
                    break
                parts = (first_candidate.get("content") or {}).get("parts") or []
                text = "".join(part.get("text", "") for part in parts if part.get("text"))
                if text.strip():
                    logger.info(
                        "Gemini chat completed model=%s elapsed_ms=%d",
                        model_name,
                        round((asyncio.get_running_loop().time() - started) * 1000),
                    )
                    return text.strip()
                last_reason = "service"
                break
            except httpx.TimeoutException:
                last_reason = "timeout"
                logger.warning("Gemini chat timed out model=%s", model_name)
                if attempt < GEMINI_TRANSIENT_RETRIES:
                    await asyncio.sleep(
                        GEMINI_RETRY_BASE_DELAY_SECONDS * (2 ** attempt)
                    )
                    continue
                break
            except httpx.HTTPStatusError as exc:
                response = exc.response
                details = _gemini_error_details(response, api_key)
                last_reason = (
                    "provider_error"
                    if response.status_code >= 500
                    else "timeout"
                    if response.status_code in (408, 425)
                    else "service"
                )
                logger.warning(
                    "Gemini chat request failed model=%s status=%s provider_status=%s detail=%s",
                    model_name,
                    response.status_code,
                    details.get("status", ""),
                    details.get("message", ""),
                )
                if (
                    response.status_code in (408, 425)
                    and attempt < GEMINI_TRANSIENT_RETRIES
                ):
                    await asyncio.sleep(
                        GEMINI_RETRY_BASE_DELAY_SECONDS * (2 ** attempt)
                    )
                    continue
                break
            except httpx.HTTPError as exc:
                last_reason = _httpx_transport_error_reason(exc)
                logger.warning(
                    "Gemini chat transport failed model=%s error=%s",
                    model_name,
                    type(exc).__name__,
                )
                if (
                    last_reason in {"connection_error", "dns_error"}
                    and attempt < GEMINI_TRANSIENT_RETRIES
                ):
                    await asyncio.sleep(
                        GEMINI_RETRY_BASE_DELAY_SECONDS * (2 ** attempt)
                    )
                    continue
                break

    logger.warning(
        "Gemini chat unavailable reason=%s elapsed_ms=%d",
        last_reason,
        round((asyncio.get_running_loop().time() - started) * 1000),
    )
    raise AIProviderUnavailable(last_reason)


async def stream_gemini(
    message: str,
    system_prompt: str,
    history: Optional[List[Dict[str, str]]] = None,
):
    api_key = _get_gemini_api_key()
    if not api_key:
        raise AIProviderUnavailable("service")
    if _gemini_quota_cooldown_active():
        raise AIProviderUnavailable("quota_exceeded")

    models = [_get_gemini_model()]
    contents = []
    for item in (history or [])[-6:]:
        role = item.get("role")
        content = item.get("content", "").strip()
        if role in ("user", "assistant") and content:
            contents.append({
                "role": "model" if role == "assistant" else "user",
                "parts": [{"text": content[:1500]}],
            })
    contents.append({"role": "user", "parts": [{"text": message}]})
    payload = {
        "systemInstruction": {"parts": [{"text": system_prompt}]},
        "contents": contents,
        "generationConfig": {"maxOutputTokens": 1536, "temperature": 0.7},
    }
    headers = {"Content-Type": "application/json", "x-goog-api-key": api_key}
    client = _get_chat_http_client()
    started = asyncio.get_running_loop().time()
    last_reason = "service"

    for model_name in models:
        url = (
            "https://generativelanguage.googleapis.com/v1beta/models/"
            f"{model_name}:streamGenerateContent?alt=sse"
        )
        for attempt in range(GEMINI_TRANSIENT_RETRIES + 1):
            received_text = False
            try:
                async with client.stream("POST", url, json=payload, headers=headers) as response:
                    if response.status_code in (401, 403):
                        last_reason = "auth"
                        break
                    if response.status_code == 429:
                        await response.aread()
                        details = _gemini_error_details(response, api_key)
                        provider_message = details.get("message", "")
                        last_reason = (
                            "quota_exceeded"
                            if _gemini_429_error_type(provider_message) == "gemini_quota_exceeded"
                            else "rate_limit"
                        )
                        if last_reason == "quota_exceeded":
                            _mark_gemini_quota_exhausted()
                        logger.warning(
                            "Gemini chat stream received HTTP 429 model=%s provider_status=%s "
                            "retry_after=%s detail=%s",
                            model_name,
                            details.get("status", ""),
                            details.get("retry_after", ""),
                            provider_message,
                        )
                        break
                    if response.status_code == 404:
                        last_reason = "model_unavailable"
                        logger.warning(
                            "Gemini streaming model unavailable model=%s status=%s",
                            model_name,
                            response.status_code,
                        )
                        break
                    if response.status_code >= 500:
                        last_reason = "provider_error"
                        logger.warning(
                            "Gemini streaming provider error model=%s status=%s",
                            model_name,
                            response.status_code,
                        )
                        if attempt < GEMINI_TRANSIENT_RETRIES:
                            await asyncio.sleep(
                                GEMINI_RETRY_BASE_DELAY_SECONDS * (2 ** attempt)
                            )
                            continue
                        break
                    response.raise_for_status()
                    async for line in response.aiter_lines():
                        if not line.startswith("data:"):
                            continue
                        raw_data = line[5:].strip()
                        if not raw_data:
                            continue
                        try:
                            data = json.loads(raw_data)
                        except json.JSONDecodeError:
                            logger.warning("Gemini streaming returned malformed event model=%s", model_name)
                            continue
                        candidates = data.get("candidates") or []
                        if not candidates:
                            continue
                        parts = (candidates[0].get("content") or {}).get("parts") or []
                        for part in parts:
                            text = part.get("text")
                            if text:
                                received_text = True
                                yield text
                if received_text:
                    logger.info(
                        "Gemini chat stream completed model=%s elapsed_ms=%d",
                        model_name,
                        round((asyncio.get_running_loop().time() - started) * 1000),
                    )
                    return
                last_reason = "service"
                break
            except httpx.TimeoutException:
                last_reason = "timeout"
                logger.warning("Gemini chat stream timed out model=%s", model_name)
                if not received_text and attempt < GEMINI_TRANSIENT_RETRIES:
                    await asyncio.sleep(
                        GEMINI_RETRY_BASE_DELAY_SECONDS * (2 ** attempt)
                    )
                    continue
                break
            except httpx.HTTPStatusError as exc:
                status_code = exc.response.status_code
                details = _gemini_error_details(exc.response, api_key)
                last_reason = (
                    "provider_error"
                    if status_code >= 500
                    else "timeout"
                    if status_code in (408, 425)
                    else "service"
                )
                logger.warning(
                    "Gemini chat stream failed model=%s status=%s provider_status=%s detail=%s",
                    model_name,
                    status_code,
                    details.get("status", ""),
                    details.get("message", ""),
                )
                if (
                    not received_text
                    and (
                        last_reason == "provider_error"
                        or status_code in (408, 425)
                    )
                    and attempt < GEMINI_TRANSIENT_RETRIES
                ):
                    await asyncio.sleep(
                        GEMINI_RETRY_BASE_DELAY_SECONDS * (2 ** attempt)
                    )
                    continue
                break
            except httpx.HTTPError as exc:
                last_reason = _httpx_transport_error_reason(exc)
                logger.warning(
                    "Gemini chat stream transport failed model=%s error=%s",
                    model_name,
                    type(exc).__name__,
                )
                if (
                    not received_text
                    and last_reason in {"connection_error", "dns_error"}
                    and attempt < GEMINI_TRANSIENT_RETRIES
                ):
                    await asyncio.sleep(
                        GEMINI_RETRY_BASE_DELAY_SECONDS * (2 ** attempt)
                    )
                    continue
                break

    logger.warning(
        "Gemini chat stream unavailable reason=%s elapsed_ms=%d",
        last_reason,
        round((asyncio.get_running_loop().time() - started) * 1000),
    )
    raise AIProviderUnavailable(last_reason)


def _groq_messages(
    message: str,
    system_prompt: str,
    history: Optional[List[Dict[str, str]]],
) -> List[Dict[str, str]]:
    conversation = [{"role": "system", "content": system_prompt}]
    for item in (history or [])[-8:]:
        role = item.get("role")
        content = item.get("content", "").strip()
        if role in ("user", "assistant") and content:
            conversation.append({"role": role, "content": content[:2000]})
    conversation.append({"role": "user", "content": message})
    return conversation


async def call_groq(
    message: str,
    system_prompt: str,
    history: Optional[List[Dict[str, str]]] = None,
    *,
    temperature: float = 0.7,
    max_tokens: int = 1024,
) -> Optional[str]:
    api_key = (settings.GROQ_API_KEY or "").strip()
    if not api_key:
        return None
    model = (settings.GROQ_MODEL or "").strip()
    try:
        client = _get_groq_client()
    except ImportError as exc:
        logger.error("Groq SDK dependency is unavailable.")
        raise AIProviderUnavailable("groq_sdk_unavailable") from exc
    if client is None:
        return None
    await _verify_groq_model(client, api_key, model)

    async def request_completion(max_tokens: int):
        try:
            return await client.chat.completions.create(
                model=model,
                messages=_groq_messages(message, system_prompt, history),
                max_tokens=max_tokens,
                temperature=temperature,
            )
        except Exception as exc:
            from openai import OpenAIError

            if isinstance(exc, OpenAIError):
                _raise_groq_unavailable(exc, model)
            raise

    completion = await request_completion(max_tokens)
    for attempt in range(2):
        choices = getattr(completion, "choices", None) or []
        content = (
            getattr(getattr(choices[0], "message", None), "content", None)
            if choices else None
        )
        if isinstance(content, str) and content.strip():
            return content.strip()
        if attempt == 0:
            logger.warning("Groq chat returned an empty completion; retrying model=%s", model)
            completion = await request_completion(max_tokens * 2)
    logger.warning("Groq chat returned an empty completion after retry model=%s", model)
    raise AIProviderUnavailable("provider_error")


async def stream_groq(
    message: str,
    system_prompt: str,
    history: Optional[List[Dict[str, str]]] = None,
):
    api_key = (settings.GROQ_API_KEY or "").strip()
    if not api_key:
        raise AIProviderUnavailable("groq_not_configured")
    model = (settings.GROQ_MODEL or "").strip()
    try:
        client = _get_groq_client()
    except ImportError as exc:
        logger.error("Groq SDK dependency is unavailable.")
        raise AIProviderUnavailable("groq_sdk_unavailable") from exc
    if client is None:
        raise AIProviderUnavailable("groq_not_configured")
    await _verify_groq_model(client, api_key, model)

    try:
        stream = await client.chat.completions.create(
            model=model,
            messages=_groq_messages(message, system_prompt, history),
            max_tokens=1024,
            temperature=0.7,
            stream=True,
        )
        async for chunk in stream:
            choices = getattr(chunk, "choices", None) or []
            delta = getattr(choices[0], "delta", None) if choices else None
            text = getattr(delta, "content", None)
            if isinstance(text, str) and text:
                yield text
    except Exception as exc:
        from openai import OpenAIError

        if isinstance(exc, OpenAIError):
            _raise_groq_unavailable(exc, model)
        raise


async def stream_ai_conversation(
    message: str,
    system_prompt: str,
    history: Optional[List[Dict[str, str]]] = None,
):
    provider_failures: List[AIProviderUnavailable] = []
    groq_configured = bool(settings.GROQ_API_KEY)
    gemini_configured = bool(_get_gemini_api_key())
    openai_configured = bool(settings.OPENAI_API_KEY)
    if groq_configured:
        received_chunk = False
        try:
            async for chunk in stream_groq(message, system_prompt, history=history):
                received_chunk = True
                yield {"type": "chunk", "text": chunk}
            yield {"type": "done", "source": "groq"}
            return
        except AIProviderUnavailable as exc:
            if received_chunk:
                raise
            if exc.reason in {"groq_model_not_configured", "groq_model_unavailable"}:
                raise
            provider_failures.append(exc)
            logger.warning("Groq assistant stream unavailable reason=%s", exc.reason)
    if gemini_configured:
        try:
            answer = await call_gemini(message, system_prompt, history)
            if answer:
                yield {"type": "chunk", "text": answer}
                yield {"type": "done", "source": "gemini"}
                return
            raise AIProviderUnavailable("service")
        except AIProviderUnavailable as exc:
            provider_failures.append(exc)
            logger.warning("Gemini assistant stream unavailable reason=%s", exc.reason)
    if openai_configured:
        received_chunk = False
        try:
            async for chunk in stream_openai(message, system_prompt, history=history):
                received_chunk = True
                yield {"type": "chunk", "text": chunk}
            yield {"type": "done", "source": "openai"}
            return
        except AIProviderUnavailable as exc:
            if received_chunk:
                raise
            provider_failures.append(exc)
            logger.warning("OpenAI assistant stream unavailable reason=%s", exc.reason)
    if provider_failures:
        quota_reasons = {
            "quota_exceeded",
            "openai_quota_exceeded",
            "groq_quota_exceeded",
        }
        if len(provider_failures) > 1 and all(
            failure.reason in quota_reasons for failure in provider_failures
        ):
            raise AIProviderUnavailable("all_providers_quota_exceeded")
        raise provider_failures[-1]
    if not gemini_configured and not openai_configured:
        raise AIProviderUnavailable("service")


async def call_openai(
    message: str,
    system_prompt: str,
    model: str = OPENAI_CHAT_MODEL,
    history: Optional[List[Dict[str, str]]] = None,
) -> Optional[str]:
    try:
        client = _get_openai_client()
    except ImportError as exc:
        logger.error("OpenAI SDK is unavailable; install the backend dependencies.")
        raise AIProviderUnavailable("openai_sdk_unavailable") from exc
    if client is None:
        return None

    conversation = [{"role": "system", "content": system_prompt}]
    for item in (history or [])[-8:]:
        role = item.get("role")
        content = item.get("content", "").strip()
        if role in ("user", "assistant") and content:
            conversation.append({"role": role, "content": content[:2000]})
    conversation.append({"role": "user", "content": message})

    try:
        completion = await client.chat.completions.create(
            model=model,
            messages=conversation,
            max_completion_tokens=1024,
            temperature=0.7,
        )
    except Exception as exc:
        from openai import OpenAIError

        if isinstance(exc, OpenAIError):
            _raise_openai_unavailable(exc, model)
        raise

    choices = getattr(completion, "choices", None) or []
    content = getattr(getattr(choices[0], "message", None), "content", None) if choices else None
    if isinstance(content, str) and content.strip():
        return content.strip()
    logger.warning("OpenAI chat returned an empty completion model=%s", model)
    raise AIProviderUnavailable("provider_error")


async def stream_openai(
    message: str,
    system_prompt: str,
    model: str = OPENAI_CHAT_MODEL,
    history: Optional[List[Dict[str, str]]] = None,
):
    try:
        client = _get_openai_client()
    except ImportError as exc:
        logger.error("OpenAI SDK is unavailable; install the backend dependencies.")
        raise AIProviderUnavailable("openai_sdk_unavailable") from exc
    if client is None:
        raise AIProviderUnavailable("service")

    conversation = [{"role": "system", "content": system_prompt}]
    for item in (history or [])[-8:]:
        role = item.get("role")
        content = item.get("content", "").strip()
        if role in ("user", "assistant") and content:
            conversation.append({"role": role, "content": content[:2000]})
    conversation.append({"role": "user", "content": message})

    try:
        stream = await client.chat.completions.create(
            model=model,
            messages=conversation,
            max_completion_tokens=1024,
            temperature=0.7,
            stream=True,
        )
        async for chunk in stream:
            choices = getattr(chunk, "choices", None) or []
            delta = getattr(choices[0], "delta", None) if choices else None
            text = getattr(delta, "content", None)
            if isinstance(text, str) and text:
                yield text
    except Exception as exc:
        from openai import OpenAIError

        if isinstance(exc, OpenAIError):
            _raise_openai_unavailable(exc, model)
        raise

async def call_ai_model(
    message: str,
    system_prompt: str,
    *,
    raise_on_failure: bool = False,
    temperature: float = 0.7,
    max_tokens: int = 1024,
    use_groq: bool = False,
) -> Optional[str]:
    failures: List[AIProviderUnavailable] = []
    if use_groq and settings.GROQ_API_KEY:
        provider_started = time.perf_counter()
        try:
            result = await call_groq(
                message,
                system_prompt,
                temperature=temperature,
                max_tokens=max_tokens,
            )
            if result:
                return result
        except AIProviderUnavailable as exc:
            failures.append(exc)
            logger.warning("Groq translation provider unavailable reason=%s", exc.reason)
        finally:
            logger.info(
                "Disease timing stage=translation_provider provider=groq elapsed_ms=%.1f",
                (time.perf_counter() - provider_started) * 1000,
            )
    if _get_gemini_api_key():
        provider_started = time.perf_counter()
        try:
            result = await call_gemini(message, system_prompt)
            if result:
                return result
        except AIProviderUnavailable as exc:
            failures.append(exc)
        finally:
            if use_groq:
                logger.info(
                    "Disease timing stage=translation_provider provider=gemini elapsed_ms=%.1f",
                    (time.perf_counter() - provider_started) * 1000,
                )
    if settings.OPENAI_API_KEY:
        provider_started = time.perf_counter()
        try:
            result = await call_openai(message, system_prompt)
            if result:
                return result
        except AIProviderUnavailable as exc:
            failures.append(exc)
            logger.warning("OpenAI model call unavailable reason=%s", exc.reason)
        finally:
            if use_groq:
                logger.info(
                    "Disease timing stage=translation_provider provider=openai elapsed_ms=%.1f",
                    (time.perf_counter() - provider_started) * 1000,
                )
    if raise_on_failure and failures:
        quota_reasons = {
            "quota_exceeded",
            "openai_quota_exceeded",
            "groq_quota_exceeded",
        }
        if all(failure.reason in quota_reasons for failure in failures):
            raise AIProviderUnavailable("quota_exceeded")
        raise failures[-1]
    return None


async def call_ai_conversation(
    message: str,
    system_prompt: str,
    history: Optional[List[Dict[str, str]]] = None,
) -> Optional[Tuple[str, str]]:
    """Use Groq first for assistant chat, then the existing configured providers."""
    provider_failures: List[AIProviderUnavailable] = []
    if settings.GROQ_API_KEY:
        try:
            result = await call_groq(message, system_prompt, history)
            if result:
                return result, "groq"
        except AIProviderUnavailable as exc:
            if exc.reason in {"groq_model_not_configured", "groq_model_unavailable"}:
                raise
            provider_failures.append(exc)
            logger.warning("Groq assistant request unavailable reason=%s", exc.reason)
    if _get_gemini_api_key():
        try:
            result = await call_gemini(message, system_prompt, history)
            if result:
                return result, "gemini"
        except AIProviderUnavailable as exc:
            provider_failures.append(exc)
            logger.warning("Gemini assistant request unavailable reason=%s", exc.reason)
    if settings.OPENAI_API_KEY:
        try:
            result = await call_openai(message, system_prompt, history=history)
            if result:
                return result, "openai"
        except AIProviderUnavailable as exc:
            provider_failures.append(exc)
            logger.warning("OpenAI assistant request unavailable reason=%s", exc.reason)
    if provider_failures:
        quota_reasons = {
            "quota_exceeded",
            "openai_quota_exceeded",
            "groq_quota_exceeded",
        }
        if len(provider_failures) > 1 and all(
            failure.reason in quota_reasons for failure in provider_failures
        ):
            raise AIProviderUnavailable("all_providers_quota_exceeded")
        raise provider_failures[-1]
    if not settings.GROQ_API_KEY and not _get_gemini_api_key() and not settings.OPENAI_API_KEY:
        return None
    return None


async def translate_texts(texts: List[str], language: str) -> Optional[List[str]]:
    """Translate user-visible text while preserving item order and all factual content."""
    language = resolve_language(language)
    local_translations = {
        text: local
        for text in dict.fromkeys(texts)
        if (local := translate_known_message(text, language)) is not None
    }
    unique_texts = list(dict.fromkeys(texts))
    missing_texts = [
        text for text in unique_texts
        if text not in local_translations and (language, text) not in _translated_text_cache
    ]
    if missing_texts:
        request_key = (language, tuple(missing_texts))
        task = _translation_requests.get(request_key)
        if task is None:
            task = asyncio.create_task(_translate_text_batch(missing_texts, language))
            _translation_requests[request_key] = task
        try:
            translated_missing = await task
        finally:
            if task.done() and _translation_requests.get(request_key) is task:
                del _translation_requests[request_key]
        if translated_missing is None:
            return None
        for source, translated in zip(missing_texts, translated_missing):
            cache_key = (language, source)
            _translated_text_cache[cache_key] = translated
            _translated_text_cache.move_to_end(cache_key)
        while len(_translated_text_cache) > TRANSLATED_TEXT_CACHE_LIMIT:
            _translated_text_cache.popitem(last=False)

    return [
        local_translations[text]
        if text in local_translations
        else _translated_text_cache[(language, text)]
        for text in texts
    ]


async def _translate_text_batch(texts: List[str], language: str) -> Optional[List[str]]:
    prompt = (
        f"Translate each string in this JSON array into {LANGUAGE_NAMES[language]}. "
        "Preserve meaning, order, formatting, numbers, URLs, scientific names, and safety guidance. "
        "Do not add or remove facts. Return only a JSON array of strings with the same number of items.\n\n"
        + json.dumps(texts, ensure_ascii=False)
    )
    raw = await call_ai_model(
        prompt,
        "You are a precise translator. Follow the target language exactly and preserve agricultural terminology.",
        raise_on_failure=True,
    )
    response_text = (raw or "").strip()
    if response_text.startswith("```"):
        response_text = re.sub(r"^```(?:json)?", "", response_text)
        response_text = re.sub(r"```$", "", response_text).strip()
    try:
        parsed = json.loads(response_text)
    except json.JSONDecodeError:
        return None
    if (
        not isinstance(parsed, list)
        or len(parsed) != len(texts)
        or not all(isinstance(item, str) and item.strip() for item in parsed)
    ):
        return None
    return [item.strip() for item in parsed]


def generate_rule_based_response(message: str, context: Dict[str, Any], language: str = "en") -> str:
    msg_lower = message.lower()
    crop = context.get("crop", "")
    stage = context.get("stage", "")
    soil = context.get("soil", "")
    irrigation = context.get("irrigation", "")
    location = context.get("location", {})
    weather = context.get("weather", {})

    district = location.get("district", "") if isinstance(location, dict) else ""
    current_temp = weather.get("current", {}).get("temperature", 0) if isinstance(weather, dict) else 0
    rain_prob = 0
    if isinstance(weather, dict):
        for h in weather.get("hourly", [])[:12]:
            rain_prob = max(rain_prob, h.get("rain_prob", 0))

    if _matches_any(msg_lower, ["water", "irrigation", "पाणी", "पानी", "सिंचन", "न्हवे"]):
        return _get_irrigation_advice(crop, stage, soil, current_temp, language)

    if _matches_any(msg_lower, ["spray", "pesticide", "fertilizer", "फवारणी", "स्प्रे", "किटकनाशक", "खत", "उर्वरक", "छिडकाव"]):
        return _get_spray_advice(crop, stage, rain_prob, current_temp, language)

    if _matches_any(msg_lower, ["pest", "insect", "disease", "कीटक", "कीड़े", "रोग", "बियाणे", "जंतू", "व्याधी"]):
        return _get_pest_advice(crop, stage, language)

    if _matches_any(msg_lower, ["fertilizer", "nutrient", "npk", "urea", "खत", "उर्वरक", "खाद", "पोषक", "युरिया"]):
        return _get_fertilizer_advice(crop, stage, soil, language)

    if _matches_any(msg_lower, ["seed", "sowing", "planting", "बियाणे", "बीज", "पेरणी", "रोपण"]):
        return _get_sowing_advice(crop, language)

    if _matches_any(msg_lower, ["harvest", "yield", "storage", "कापणी", "पिक कापणे", "साठवण", "फळ", "उत्पन्न"]):
        return _get_harvest_advice(crop, stage, language)

    if _matches_any(msg_lower, ["price", "market", "rate", "भाव", "बाजार", "किंमत", "दर"]):
        return _get_market_advice(crop, district, language)

    if _matches_any(msg_lower, ["weather", "rain", "temperature", "climate", "हवामान", "पाऊस", "तापमान", "मोसम"]):
        return _get_weather_discussion(current_temp, rain_prob, language)

    if _matches_any(msg_lower, ["soil", "manure", "compost", "माती", "कोंपोस्ट", "सेंध", "खत", "सालगवहन"]):
        return _get_soil_advice(soil, language)

    return _get_generic_advice(crop, stage, language)


def _matches_any(msg: str, keywords: list) -> bool:
    for kw in keywords:
        if kw.lower() in msg:
            return True
    return False


def _get_irrigation_advice(crop: str, stage: str, soil: str, temp: float, lang: str) -> str:
    crop_str = crop or "your crop"
    soil_note = ""
    if soil:
        if any(s in soil.lower() for s in ["sandy", "वालुकी", "बलुआ"]):
            soil_note = " Sandy soil requires more frequent, light irrigation."
        elif any(s in soil.lower() for s in ["clay", "चिकणी", "मृत्तिका", "चिकनी"]):
            soil_note = " Clay soil retains moisture, reduce frequency to avoid waterlogging."
        elif any(s in soil.lower() for s in ["loam", "दोमट", "बहुरंगी"]):
            soil_note = " Loamy soil is ideal, maintain regular scheduling."

    temp_note = ""
    if temp > 35:
        temp_note = f" Current temp ({temp}°C) is high - prefer early morning or late evening irrigation to reduce evaporation loss."

    if lang == "mr":
        return (
            f"{crop_str} साठी सिंचन सूचना:\n"
            f"टप्पा: {stage or 'माहिती नाही'}.{soil_note}{temp_note}\n"
            f"1. सकाळी 6-9 किंवा संध्याकाळी 5-7 या वेळी सिंचन करा.\n"
            f"2. कोणत्याही फळी/फुलांच्या टप्प्यात ओलावा कमी करू नका.\n"
            f"3. जमिनीच्या पृष्ठभागाला कोरडे वाटल्यास सिंचनाची आवश्यकता वाटते.\n"
            f"4. जास्त सिंचनामुळे मुळे पडतात - ह्यावर लक्ष द्या."
        )
    elif lang == "hi":
        return (
            f"{crop_str} के लिए सिंचन सलाह:\n"
            f"चरण: {stage or 'जानकारी नहीं'}.{soil_note}{temp_note}\n"
            f"1. सुबह 6-9 या शाम 5-7 बजे सिंचन करें।\n"
            f"2. फूल/फल चरण में पानी की कमी न होने दें।\n"
            f"3. मिट्टी की ऊपरी सतह सूखने पर सिंचन करें।\n"
            f"4. अधिक सिंचन से जड़ें सड़ सकती हैं - सावधान रहें।"
        )
    else:
        return (
            f"Irrigation advice for {crop_str}:\n"
            f"Stage: {stage or 'Not specified'}.{soil_note}{temp_note}\n"
            f"1. Water during early morning (6-9 AM) or late evening (5-7 PM) to minimize evaporation.\n"
            f"2. Do not let moisture stress occur during flowering/fruiting stages.\n"
            f"3. Check topsoil - if 2-3 cm is dry, irrigation is needed.\n"
            f"4. Avoid over-irrigation as it can cause root rot and nutrient leaching."
        )


def _get_spray_advice(crop: str, stage: str, rain_prob: float, temp: float, lang: str) -> str:
    rain_warning = ""
    if rain_prob > 50:
        if lang == "mr":
            rain_warning = f" **महत्त्वाचे:** पावसाची शक्यता {rain_prob}% आहे. पावसानंतर किमान 4 ते 6 तास सुरक्षित कालावधी नसल्यास फवारणी टाळा. सर्वोत्तम परिणामांसाठी पावसापूर्वी फवारणी टाळा किंवा त्यांनंतर पुन्हा फवारणी करा."
        elif lang == "hi":
            rain_warning = f" **महत्वपूर्ण:** बारिश की संभावना {rain_prob}% है। बारिश से पहले फवारणी से बचें या बारिश के बाद दोबारा छिड़काव करें। कम से कम 4-6 घंटे सूखे मौसम की आवश्यकता है।"
        else:
            rain_warning = f" **IMPORTANT:** Rain probability is {rain_prob}%. Avoid spraying if less than 4-6 hours of dry weather expected. Best to reschedule after rain or re-apply post-rainfall."

    temp_warning = ""
    if temp > 32:
        if lang == "mr":
            temp_warning = " उच्च तापमानामुळे फवारणी सकाळी किंवा संध्याकाळी करा - दुपारच्या वेळी फवारणी केल्यास जळजळ होऊ शकते व रासायनिक तत्त्वे कमी होतात."
        elif lang == "hi":
            temp_warning = " तापमान अधिक होने से छिड़काव सुबह या शाम को करें - दोपहर में छिड़काव से जलन हो सकती है और प्रभाविता कम हो सकती है।"
        else:
            temp_warning = " High temperature detected - spray during early morning or evening hours. Midday spraying can cause phytotoxicity and reduce efficacy."

    if lang == "mr":
        return (
            f"{crop or 'पीक'} साठी फवारणी सूचना (टप्पा: {stage or 'माहिती नाही'}):{rain_warning}{temp_warning}\n"
            f"1. लागू होणार्या रसायनांचे योग्य प्रमाण वापरा - लेबलवरील सूचनांचे पालन करा.\n"
            f"2. फवारणी करिताना स्वच्छ हातमोजे, शेतकरी बूट, गोगले, हातके यांचा वापर करा.\n"
            f"3. फुलांच्या टप्प्यात कीटकनाशक फवारणी टाळा किंवा कमी प्रमाणात वापरा - परागणासाठी मीठे मासे हानी पोहोचू शकतात.\n"
            f"4. कोणत्याही दोन फवारण्यांमध्ये 7-15 दिवसांचे अंतर ठेवा."
        )
    elif lang == "hi":
        return (
            f"{crop or 'फसल'} के लिए फवारणी सलाह (चरण: {stage or 'जानकारी नहीं'}):{rain_warning}{temp_warning}\n"
            f"1. उचित खुराक का प्रयोग करें - लेबल निर्देशों का सख्ती से पालन करें।\n"
            f"2. सुरक्षा उपकरण - दस्ताने, गॉगल, बूट और मास्क पहनें।\n"
            f"3. फूल चरण में कीटनाशक का छिड़काव न करें - मधुमक्खियों और परागण को नुकसान पहुंच सकता है।\n"
            f"4. दो स्प्रे के बीच 7-15 दिनों का अंतर रखें।"
        )
    else:
        return (
            f"Spraying advice for {crop or 'crop'} (stage: {stage or 'Not specified'}):{rain_warning}{temp_warning}\n"
            f"1. Use recommended dosage - always follow label instructions carefully.\n"
            f"2. Wear protective gear: gloves, goggles, boots, and mask when spraying.\n"
            f"3. Avoid insecticides during flowering stage - it harms pollinators like bees.\n"
            f"4. Maintain 7-15 day interval between consecutive sprays to prevent resistance."
        )


def _get_pest_advice(crop: str, stage: str, lang: str) -> str:
    crop_lower = (crop or "").lower()

    if lang == "mr":
        base = (
            f"{crop or 'पीक'} (टप्पा: {stage or 'माहिती नाही'}) साठी कीटक/रोग नियंत्रण सूचना:\n"
            f"1. प्रथम: जैविक विधी वापरा - नीम अर्क (5 मि.ली./लिटर) किंवा ट्रायकोडर्मा.\n"
            f"2. लवकर शोध: आठवड्याला दोनदा पिकाची तपासणी करा - पानांच्या मागील बाजूस, कांद्यांवर लक्ष द्या.\n"
            f"3. जोडी नियंत्रण: जास्त प्रमाणात संक्रमण झाल्यासच रासायनिक विक्री करा.\n"
            f"4. फवारणीपूर्वी हवामानाचा अंदाज पहा (पाऊस टाळा)."
        )
        if "टोमॅटो" in crop_lower or "tomato" in crop_lower:
            base += "\nटोमॅटो विशेष: लेट ब्लाईटसाठी मॅनकोजेब + मेटालॅक्सिल वापरा. तुरळक सडण्यासाठी कॉपर सल्फेट."
        if "कापूस" in crop_lower or "cotton" in crop_lower:
            base += "\nकापूस विशेष: गुलाबी किडा नियंत्रणासाठी फेरोमोन ट्रॅप्स बसवा. Bt कापूससाठी मार्गदर्शक संख्या (ETL) नंतरच फवारणी करा."
        return base
    elif lang == "hi":
        base = (
            f"{crop or 'फसल'} (चरण: {stage or 'जानकारी नहीं'}) के लिए कीट/रोग प्रबंधन:\n"
            f"1. प्राथमिकता: जैविक नियंत्रण - नीम का अर्क (5 मिली/लीटर) या ट्राइकोडर्मा।\n"
            f"2. जल्दी पहचान: सप्ताह में दो बार फसल का निरीक्षण करें - पत्तियों के निचले हिस्से और तनों को देखें।\n"
            f"3. रासायनिक केवल तभी जब संक्रमण सीमा से अधिक हो।\n"
            f"4. छिड़काव से पहले मौसम की जांच करें - बारिश से बचें।"
        )
        if "टमाटर" in crop_lower or "tomato" in crop_lower:
            base += "\nटमाटर विशेष: लेट ब्लाइट के लिए मैनकोजेब + मेटालैक्सिल। फल सड़न के लिए कॉपर सल्फेट।"
        if "कपास" in crop_lower or "cotton" in crop_lower:
            base += "\nकपास विशेष: गुलाबी सुंडी के लिए फेरोमोन ट्रैप लगाएं। ETL सीमा के बाद ही रसायन spray करें।"
        return base
    else:
        base = (
            f"Pest & Disease Management for {crop or 'crop'} (stage: {stage or 'Not specified'}):\n"
            f"1. First line: Use organic methods - Neem oil (5 ml/liter) or Trichoderma.\n"
            f"2. Early detection: Inspect crop twice weekly - check leaf undersides and stems thoroughly.\n"
            f"3. Use chemicals only if infestation crosses ETL (Economic Threshold Level).\n"
            f"4. Check weather forecast before spraying - avoid before rain."
        )
        if "tomato" in crop_lower:
            base += "\nTomato specific: Use Mancozeb + Metalaxyl for late blight. Copper oxychloride for fruit rot."
        if "cotton" in crop_lower:
            base += "\nCotton specific: Install pheromone traps for Pink Bollworm. Spray only after ETL threshold."
        return base


def _get_fertilizer_advice(crop: str, stage: str, soil: str, lang: str) -> str:
    if lang == "mr":
        return (
            f"{crop or 'पीक'} साठी खत/उर्वरक सूचना (टप्पा: {stage or 'माहिती नाही'}, माती: {soil or 'माहिती नाही'}):\n"
            f"1. मूलभूत: 10-15 टन/हेक्टर गवरण खरपतवार किंवा कोंपोस्ट हा आधारभूत खत पेरणीपूर्वी द्या.\n"
            f"2. NPK: शेतात पिकानुसार NPK (उदा. पाकळ्या- 20:20:20, फळी-13:0:45) पुरवठा करा.\n"
            f"3. सूक्ष्म घटक: झिंक, बोरॉन यांचे पानावर फवारणी करा (फुलांच्या आधी आणि फळी सुरू असताना).\n"
            f"4. युरिया: फळी टप्प्यापूर्वी जास्त युरिया देणे टाळा - गवताची वाढ होईल व पिक कमी."
        )
    elif lang == "hi":
        return (
            f"{crop or 'फसल'} के लिए उर्वरक सलाह (चरण: {stage or 'जानकारी नहीं'}, मिट्टी: {soil or 'जानकारी नहीं'}):\n"
            f"1. बेसल: बुवाई से पहले 10-15 टन/हेक्टर गोबर खाद या कम्पोस्ट डालें।\n"
            f"2. NPK: फसल की आवश्यकता के अनुसार NPK दें (पत्तियों के लिए 20:20:20, फलों के लिए 13:0:45)।\n"
            f"3. सूक्ष्म पोषक: जिंक, बोरॉन का पत्तों पर छिड़काव करें (फूल से पहले और फल लगना शुरू होने पर)।\n"
            f"4. यूरिया: फल चरण से पहले अधिक यूरिया न दें - हरी वृद्धि बढ़ेगी और उत्पादन घटेगा।"
        )
    else:
        return (
            f"Fertilizer advice for {crop or 'crop'} (stage: {stage or 'Not specified'}, soil: {soil or 'Not specified'}):\n"
            f"1. Basal: Apply 10-15 tons/hectare FYM or compost before sowing.\n"
            f"2. NPK: Apply NPK based on crop stage (e.g., 20:20:20 for vegetative, 13:0:45 for fruiting/flowering).\n"
            f"3. Micronutrients: Foliar spray of Zinc + Boron before flowering and at fruit set.\n"
            f"4. Urea: Avoid excess urea before fruiting stage - promotes excess foliage over yield."
        )


def _get_sowing_advice(crop: str, lang: str) -> str:
    if lang == "mr":
        return (
            f"{crop or 'पीक'} साठी पेरणी/रोपण सूचना:\n"
            f"1. योग्य मोसम: जैव-विविधतेच्या संदर्भात ठरवलेल्या योग्य पेरणी कालावधीच पालन करा. Monsun-च्या पूर्वीच 1-2 चावड्या माती भिजवून घ्या.\n"
            f"2. बियाणे दर्जेदार: सरकारी मान्यताप्राप्त बियाणेच खरेदी करा. पेरणीपूर्वी बियाण्यांची टिपण करा (Thiram + Imidacloprid).\n"
            f"3. अंतर: पीकानुसार व्यवस्थित अंतर ठेवा (रेषा आणि रेषेतील दोन्ही).\n"
            f"4. पेरणी खोली: 2-3 सेमी खोली पेरणी उत्तम. जास्त खोली केल्यास बियाण्यांची उगवण कमी होते."
        )
    elif lang == "hi":
        return (
            f"{crop or 'फसल'} की बुवाई/रोपण सलाह:\n"
            f"1. उपयुक्त मौसम: मान्य बुवाई अवधि में ही बुआई करें। मॉनसून से 1-2 दिन पहले मिट्टी भिगोएं।\n"
            f"2. गुणवत्तापूर्ण बीज: सरकारी मान्यता प्राप्त बीज ही खरीदें। बुवाई से पहले बीज का उपचार करें (थिरम + इमिडाक्लोप्रिड)।\n"
            f"3. दूरी: फसल के अनुसार उचित पंक्ति और पौधे की दूरी बनाए रखें।\n"
            f"4. गहराई: 2-3 सेमी गहराई में बुआई सबसे अच्छी है। ज्यादा गहराई से अंकुरण कम होता है।"
        )
    else:
        return (
            f"Sowing/Planting advice for {crop or 'crop'}:\n"
            f"1. Season: Sow during recommended sowing window for your region. Pre-moisten soil 1-2 days before sowing in pre-monsoon.\n"
            f"2. Seed quality: Use certified seeds from reliable sources. Treat seeds before sowing (Thiram + Imidacloprid) for disease protection.\n"
            f"3. Spacing: Maintain proper row-to-row and plant-to-plant spacing as recommended for the crop.\n"
            f"4. Sowing depth: 2-3 cm is ideal. Deeper sowing reduces germination percentage."
        )


def _get_harvest_advice(crop: str, stage: str, lang: str) -> str:
    if lang == "mr":
        return (
            f"{crop or 'पीक'} साठी कापणी/साठवण सूचना (टप्पा: {stage or 'माहिती नाही'}):\n"
            f"1. योग्य वेळ: पिक पूर्णपणे परिपक्व झाल्यावरच कापणी करा. रंग, आकार, कडकपणा हे लक्षात घ्या.\n"
            f"2. साफ सुविधा: स्वच्छ साठवण तयार करा. 12-14% ओलावा असलेल्या भाज्या/धान्य साठवण्यापूर्वी तपासणी करा.\n"
            f"3. क्रमवार विक्री: सर्व पिक एकाच वेळी विकणे टाळा. बाजारभावाची माहिती घेऊन क्रमवारी लावून विक्री करा.\n"
            f"4. उपयुक्त पॅकेजिंग: गुणवत्ता टिकवून ठेवण्यासाठी योग्य पॅकेजिंग वापरा."
        )
    elif lang == "hi":
        return (
            f"{crop or 'फसल'} की कटाई/संग्रहण सलाह (चरण: {stage or 'जानकारी नहीं'}):\n"
            f"1. सही समय: फसल पूरी तरह से पकने पर ही कटाई करें। रंग, आकार, कठोरता देखें।\n"
            f"2. साफ भंडारण: भंडारण से पहले साफ-सुथरे गोदाम की व्यवस्था करें। अनाज का नमी 12-14% होना चाहिए।\n"
            f"3. चरणबद्ध बिक्री: सारी फसल एक साथ न बेचें। बाजार दर देखकर चरणबद्ध रूप से बिक्री करें।\n"
            f"4. उचित पैकेजिंग: गुणवत्ता बनाए रखने के लिए सही पैकेजिंग का उपयोग करें।"
        )
    else:
        return (
            f"Harvest & Storage advice for {crop or 'crop'} (stage: {stage or 'Not specified'}):\n"
            f"1. Timing: Harvest at proper physiological maturity stage. Observe color, size, and firmness indicators.\n"
            f"2. Clean storage: Ensure proper cleaning and drying to 12-14% moisture for grains before storage.\n"
            f"3. Staggered selling: Avoid selling entire produce at once. Monitor market prices and sell in phased manner.\n"
            f"4. Proper packaging: Use appropriate packaging to preserve quality during transport."
        )


def _get_market_advice(crop: str, district: str, lang: str) -> str:
    crop_str = crop or "आपले पीक" if lang in ["mr", "hi"] else "your crop"
    dist_str = f" ({district})" if district else ""

    if lang == "mr":
        return (
            f"{crop_str}{dist_str} साठी बाजार सलाह:\n"
            f"1. बाजारभाव माहिती: जवळच्या APMC बाजारातील दैनिक भाव तपासा. KrushiMitra Market Price वापरा.\n"
            f"2. वेळाची योजना: घाईघाईने विकणे टाळा. उत्तम भावासाठी थोड्या काळासाठी साठवण्याचा विचार करा (संभव असल्यास).\n"
            f"3. गुणवत्ता: गुणवत्ता ठेवा - ग्रेडिंग आणि सॉर्टिंग करा. गुणवत्ता दर्ज्यावरूनच भाव मिळतो.\n"
            f"4. सरकारी योजना: MSP (किमान आधारभूत किंमत) व तत्संबंधित शेतकऱ्यांच्या योजनांचा लाभ घ्या.\n"
            f"5. KrushiMitra वर आपले पीक जाहीर करा - थेट खरेदीदाराशी संपर्क साधा."
        )
    elif lang == "hi":
        return (
            f"{crop_str}{dist_str} के लिए बाजार सलाह:\n"
            f"1. मंडी भाव: निकटतम APMC मंडी का दैनिक भाव देखें। KrushiMitra मार्केट प्राइस फीचर का उपयोग करें।\n"
            f"2. समय: जल्दबाजी में बिक्री न करें। बेहतर कीमत के लिए संभव हो तो थोड़े समय के लिए स्टोर करें।\n"
            f"3. गुणवत्ता: ग्रेडिंग और सॉर्टिंग करें। अच्छी गुणवत्ता पर अच्छी कीमत मिलती है।\n"
            f"4. सरकारी योजनाएं: MSP और किसान कल्याण योजनाओं का लाभ उठाएं।\n"
            f"5. KrushiMitra पर अपना उत्पादन list करें - सीधे खरीदार से संपर्क करें।"
        )
    else:
        return (
            f"Market advice for {crop_str}{dist_str}:\n"
            f"1. Check prices: Monitor daily rates at nearby APMC markets. Use KrushiMitra Market Price feature.\n"
            f"2. Timing: Don't sell in panic. Consider short-term storage for better price realization if possible.\n"
            f"3. Quality: Grade and sort your produce properly. Better quality fetches premium prices.\n"
            f"4. Government schemes: Avail benefits under MSP (Minimum Support Price) and other farmer welfare schemes.\n"
            f"5. List your produce on KrushiMitra Marketplace to connect directly with buyers."
        )


def _get_weather_discussion(temp: float, rain_prob: float, lang: str) -> str:
    if lang == "mr":
        return (
            f"सध्याचे हवामान: तापमान {temp}°C, पावसाची शक्यता {rain_prob}%\n"
            f"• तापमान 30-35°C: सामान्य वाढीसाठी अनुकूल. सकाळी सिंचन उत्तम.\n"
            f"• पावसाची शक्यता 60%+ : फवारणी टाळा, निचोरे (drainage) तपासा.\n"
            f"• 40°C+ : उष्णतेचा ताण, अधिक सिंचन आवश्यक असू शकते.\n"
            f"अधिक तपशीलांसाठी Weather > Advisory वापरा."
        )
    elif lang == "hi":
        return (
            f"वर्तमान मौसम: तापमान {temp}°C, बारिश की संभावना {rain_prob}%\n"
            f"• 30-35°C तापमान: सामान्य विकास के लिए अनुकूल। सुबह सिंचन बेहतर।\n"
            f"• बारिश 60%+ : छिड़काव से बचें, जल निकास की जांच करें।\n"
            f"• 40°C+ : तनावपूर्ण गर्मी, अधिक पानी की जरूरत पड़ सकती है।\n"
            f"अधिक विवरण के लिए Weather > Advisory सुविधा का उपयोग करें।"
        )
    else:
        return (
            f"Current weather discussion: Temperature {temp}°C, Rain probability {rain_prob}%\n"
            f"• 30-35°C: Good for general crop growth. Morning irrigation is optimal.\n"
            f"• Rain prob 60%+: Delay any spraying activities. Check field drainage.\n"
            f"• 40°C+: Heat stress conditions. Monitor crop, may need more frequent watering.\n"
            f"For crop-specific guidance, use Weather > Crop Advisory feature."
        )


def _get_soil_advice(soil: str, lang: str) -> str:
    if lang == "mr":
        return (
            f"माती सुधारणा सूचना (विचारलेली माती: {soil or 'माहिती नाही'}):\n"
            f"1. माती तपासणी: वर्षाला एकदा किंवा दोन वर्षांनी नक्की माती तपासणी करा. NPK, pH, सूक्ष्मघटकांची माहिती मिळेल.\n"
            f"2. जैविक पद्धती: दर वर्षी 10-15 टन/हेक्टर कोंपोस्ट किंवा गवरण खरपतवार घाला. मातीची संरचना आणि जीवनसत्त्वे सुधारतात.\n"
            f"3. फिरती पीकनी: एकाच शेतात वर्षानुवर्षे एकच पीक न घाला. परभणी, तूर, मूग सारख्या विदली पिके घ्या - नायट्रोजन सुधारतात.\n"
            f"4. मल्चिंग: शेतात सूका किंवा लवंग मल्चिंग करा - ओलावा टिकतो, खरपतवार कमी होतात."
        )
    elif lang == "hi":
        return (
            f"मिट्टी सुधार सलाह (दी गई मिट्टी: {soil or 'जानकारी नहीं'}):\n"
            f"1. मिट्टी परीक्षण: साल में एक बार या हर 2 साल में मिट्टी की जांच करवाएं। NPK, pH, सूक्ष्म पोषक तत्वों का पता चलेगा।\n"
            f"2. जैविक खाद: हर साल 10-15 टन/हेक्टर कम्पोस्ट या गोबर खाद डालें। मिट्टी की संरचना और जैव गतिविधि बेहतर होती है।\n"
            f"3. फसल चक्र: एक ही खेत में हर साल एक ही फसल न लगाएं। मूंग, अरहर, चना जैसी दलहन फसलें लगाएं - नाइट्रोजन बढ़ता है।\n"
            f"4. मल्चिंग: खेत में सूखे पत्तों या प्लास्टिक मल्चिंग करें - नमी बनी रहती है, खरपतवार कम होते हैं।"
        )
    else:
        return (
            f"Soil improvement advice (mentioned soil: {soil or 'Not specified'}):\n"
            f"1. Soil testing: Get soil tested annually or every 2 years. Know NPK status, pH, and micronutrient levels.\n"
            f"2. Organic matter: Add 10-15 tons/hectare compost or FYM every year. Improves soil structure and microbial activity.\n"
            f"3. Crop rotation: Don't grow the same crop continuously. Include legumes (pulses) - they fix nitrogen naturally.\n"
            f"4. Mulching: Use organic or plastic mulch - retains moisture, reduces weeds, and maintains soil temperature."
        )


def _get_generic_advice(crop: str, stage: str, lang: str) -> str:
    crop_info = f" for your {crop or 'crop'}"
    stage_info = f" (stage: {stage})" if stage else ""

    if lang == "mr":
        return (
            f"कृषी सलाह{crop_info}{stage_info}:\n"
            f"• {crop or 'पीक'} ची आठवड्याला 2 वेळा तपासणी करा. पाने, कांदे, फुले यांची काळजी घ्या.\n"
            f"• सिंचन: उचित वेळा आणि प्रमाणात द्या. जास्त सिंचनापेक्षा कमी सिंचन हानिकारक.\n"
            f"• खरपतवार: पिकाच्या पहिल्या 30-45 दिवसांतील खरपतवार नियंत्रण महत्त्वाचे.\n"
            f"• रोग/कीटक: लवकर ओळखणे हेच यश. आधी जैविक, नंतर रासायनिक.\n"
            f"• अधिक विशिष्ट सलाहासाठी: पाणी, फवारणी, कीटक, खत आदी विशिष्ट शब्द वापरा किंवा वरील मेनू मधील सुविधा वापरा."
        )
    elif lang == "hi":
        return (
            f"कृषि सलाह{crop_info}{stage_info}:\n"
            f"• {crop or 'फसल'} का सप्ताह में 2 बार निरीक्षण करें। पत्ते, तने, फूलों को ध्यान से देखें।\n"
            f"• सिंचन: सही समय और सही मात्रा में दें। अधिक पानी कम पानी से ज्यादा हानिकारक है।\n"
            f"• खरपतवार: फसल के शुरुआती 30-45 दिनों में खरपतवार नियंत्रण सबसे महत्वपूर्ण है।\n"
            f"• रोग/कीट: जल्दी पहचान सबसे महत्वपूर्ण है। पहले जैविक फिर रासायनिक।\n"
            f"• अधिक विशिष्ट सलाह के लिए: पानी, फवारणी, कीट, खाद आदि विशिष्ट शब्दों का उपयोग करें या उपरोक्त मेनू का उपयोग करें।"
        )
    else:
        return (
            f"General farming advice{crop_info}{stage_info}:\n"
            f"• Inspect {crop or 'crop'} twice weekly. Check leaves, stems, flowers for any issues.\n"
            f"• Irrigation: Water at correct intervals in right quantity. Over-watering is more harmful than under-watering.\n"
            f"• Weeds: First 30-45 days of crop growth are critical for weed management.\n"
            f"• Pests/Diseases: Early identification is key. Try organic solutions first, then chemicals only when needed.\n"
            f"• For more specific advice: Try asking about water, spray, pest, fertilizer, seeds, harvest, or market. Or use feature-specific pages."
        )
