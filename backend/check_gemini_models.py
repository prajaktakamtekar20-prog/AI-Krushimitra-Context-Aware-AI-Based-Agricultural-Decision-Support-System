import os
import sys
from pathlib import Path
from typing import Iterable

from dotenv import load_dotenv
from google import genai
from google.genai.errors import APIError
from google.genai import types
import httpx


BACKEND_DIR = Path(__file__).resolve().parent
DEFAULT_MODEL = "gemini-3.8-flash"


def available_model_names(models: Iterable[object]) -> list[str]:
    names = set()
    for model in models:
        name = getattr(model, "name", None) or getattr(model, "base_model_id", None)
        if name:
            names.add(name.removeprefix("models/"))
    return sorted(names, key=str.casefold)


def inspect_model_access(
    models: Iterable[object],
    configured_model: str,
) -> tuple[list[str], bool]:
    available = available_model_names(models)
    normalized_configured = configured_model.strip().removeprefix("models/")
    return available, normalized_configured in available


def main() -> int:
    load_dotenv(BACKEND_DIR / ".env", override=True)
    api_key = (os.getenv("GEMINI_API_KEY") or "").strip()
    if not api_key:
        print("GEMINI_API_KEY is missing from backend/.env.")
        return 1

    configured_model = (
        os.getenv("GEMINI_MODEL")
        or os.getenv("GEMINI_VISION_MODEL")
        or os.getenv("GEMINI_CHAT_MODEL")
        or DEFAULT_MODEL
    ).strip()
    client = None
    try:
        client = genai.Client(
            api_key=api_key,
            http_options=types.HttpOptions(api_version="v1beta", timeout=15_000),
        )
        models, configured_is_available = inspect_model_access(
            client.models.list(),
            configured_model,
        )
    except (APIError, httpx.TransportError, OSError, ValueError) as exc:
        status_code = getattr(exc, "code", None)
        try:
            status_code = int(status_code)
        except (TypeError, ValueError):
            status_code = None

        if status_code in (400, 401, 403):
            message = "Google rejected the API key or denied model-list access. Verify the key and its project access."
        elif status_code == 429:
            message = "Google model-list access is rate-limited or over quota. Check the project's quota."
        elif isinstance(exc, httpx.TimeoutException):
            message = "Could not reach Google's model-list API. Check the backend network connection and retry."
        else:
            message = "Google's model-list request failed. Check the backend network connection and API configuration."
        print(message)
        return 1
    finally:
        if client is not None:
            client.close()

    print(f"Configured vision model: {configured_model}")
    print(f"Configured model listed by Google's model API: {'yes' if configured_is_available else 'no'}")
    print("Models listed for this key:")
    for model in models:
        print(f"- {model}")
    print(
        "Model listing does not prove access to the Interactions API; verify with a real request."
    )
    return 0 if configured_is_available else 2


if __name__ == "__main__":
    sys.exit(main())
