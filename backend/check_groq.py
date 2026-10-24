
import os
import json
import urllib.request
import urllib.error
from dotenv import dotenv_values

# Load configuration from backend/.env
env = dotenv_values(".env")
key = os.getenv("GROQ_API_KEY") or env.get("GROQ_API_KEY")
model = (
    os.getenv("GROQ_MODEL")
    or env.get("GROQ_MODEL")
    or "openai/gpt-oss-20b"
)

if not key:
    print("ERROR: GROQ_API_KEY not found in backend/.env")
    raise SystemExit(1)

print("Configured model:", model)

BASE_URL = "https://api.groq.com/openai/v1"

tests = [
    ("MODEL LIST", "/models", None),
    (
        "CHAT TEST",
        "/chat/completions",
        {
            "model": model,
            "messages": [
                {
                    "role": "user",
                    "content": "Reply only with these words: Groq works"
                }
            ],
            "max_tokens": 100
        }
    )
]

for label, path, payload in tests:
    headers = {
        "Authorization": "Bearer " + key,
        "Content-Type": "application/json",
        "User-Agent": "AI-KrushiMitra/1.0"
    }

    request_data = (
        json.dumps(payload).encode("utf-8")
        if payload is not None
        else None
    )

    req = urllib.request.Request(
        BASE_URL + path,
        data=request_data,
        headers=headers,
        method="POST" if payload is not None else "GET"
    )

    try:
        with urllib.request.urlopen(req, timeout=30) as response:
            result = json.loads(response.read().decode("utf-8"))
            print(f"\n{label}: HTTP {response.status}")

            if payload is None:
                ids = [
                    item.get("id", "")
                    for item in result.get("data", [])
                ]
                print("Model available:", model in ids)
                print(
                    "Matching IDs:",
                    [item for item in ids if "gpt-oss-20b" in item]
                )
            else:
                choices = result.get("choices", [])

                if not choices:
                    print("No choices returned.")
                    print("Response keys:", list(result.keys()))
                    continue

                choice = choices[0]
                message = choice.get("message") or {}
                content = message.get("content")

                print("Finish reason:", choice.get("finish_reason"))
                print("Response content:", repr(content))
                print("Reasoning:", repr(message.get("reasoning")))
                print("Usage:", result.get("usage"))

                if isinstance(content, str) and content.strip():
                    print("CHAT RESULT: SUCCESS")
                else:
                    print("CHAT RESULT: HTTP succeeded, but content is empty.")

    except urllib.error.HTTPError as error:
        print(f"\n{label}: HTTP {error.code}")

        for name in (
            "Server",
            "CF-Ray",
            "Content-Type",
            "Retry-After",
            "x-request-id"
        ):
            value = error.headers.get(name)
            if value:
                print(f"{name}: {value}")

        body = error.read().decode("utf-8", errors="replace")

        try:
            data = json.loads(body)
            details = data.get("error", data)

            if isinstance(details, dict):
                print("Error code:", details.get("code"))
                print("Error type:", details.get("type"))
                print("Error message:", details.get("message"))
            else:
                print("Error response:", str(details)[:500])

        except json.JSONDecodeError:
            print("Error response:", body[:500])

    except Exception as error:
        print(
            f"\n{label}: {type(error).__name__}: {error}"
        )
