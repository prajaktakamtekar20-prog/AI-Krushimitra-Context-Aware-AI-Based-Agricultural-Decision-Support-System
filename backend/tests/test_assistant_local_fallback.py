import json
import unittest
from unittest.mock import AsyncMock, patch

import httpx
from fastapi import FastAPI

from routes import assistant as assistant_route
from services import ai_service
from services.ai_service import AIProviderUnavailable


class AssistantLocalFallbackTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.groq_key_patch = patch.object(assistant_route.settings, "GROQ_API_KEY", "")
        self.groq_key_patch.start()
        self.app = FastAPI()
        self.app.include_router(assistant_route.router, prefix="/api/assistant")
        self.client = httpx.AsyncClient(
            transport=httpx.ASGITransport(app=self.app),
            base_url="http://testserver",
        )

    async def asyncTearDown(self):
        await self.client.aclose()
        self.groq_key_patch.stop()

    async def test_quota_error_is_not_hidden_by_local_fallback_in_any_language(self):
        questions = {
            "en": "How can I improve soil health?",
            "mr": "मातीचे आरोग्य कसे सुधारावे?",
            "hi": "मिट्टी का स्वास्थ्य कैसे सुधारें?",
            "ml": "മണ്ണിന്റെ ആരോഗ്യം എങ്ങനെ മെച്ചപ്പെടുത്താം?",
        }
        with (
            patch.object(assistant_route.settings, "GEMINI_API_KEY", "configured"),
            patch.object(assistant_route.settings, "OPENAI_API_KEY", ""),
            patch.object(
                assistant_route,
                "call_ai_conversation",
                new=AsyncMock(side_effect=AIProviderUnavailable("quota_exceeded")),
            ) as provider_call,
        ):
            for language, question in questions.items():
                response = await self.client.post(
                    "/api/assistant/chat",
                    headers={"X-Language": language},
                    json={"message": question, "history": []},
                )
                self.assertEqual(response.status_code, 503, language)
                self.assertTrue(response.json()["detail"], language)
                self.assertNotIn("response", response.json(), language)

        self.assertEqual(provider_call.await_count, 4)

    async def test_live_question_keeps_quota_error_instead_of_inventing_answer(self):
        with (
            patch.object(assistant_route.settings, "GEMINI_API_KEY", "configured"),
            patch.object(assistant_route.settings, "OPENAI_API_KEY", ""),
            patch.object(
                assistant_route,
                "call_ai_conversation",
                new=AsyncMock(side_effect=AIProviderUnavailable("quota_exceeded")),
            ),
        ):
            response = await self.client.post(
                "/api/assistant/chat",
                headers={"X-Language": "en"},
                json={"message": "What is today's market price for tomatoes in Pune?", "history": []},
            )

        self.assertEqual(response.status_code, 503)
        self.assertIn("quota is exhausted", response.json()["detail"])

    async def test_kannada_is_not_a_supported_language(self):
        with (
            patch.object(assistant_route.settings, "GEMINI_API_KEY", "configured"),
            patch.object(assistant_route.settings, "OPENAI_API_KEY", ""),
            patch.object(
                assistant_route,
                "call_ai_conversation",
                new=AsyncMock(side_effect=AIProviderUnavailable("quota_exceeded")),
            ),
        ):
            response = await self.client.post(
                "/api/assistant/chat",
                headers={"X-Language": "kn"},
                json={"message": "How can I improve soil health?", "history": []},
            )

        self.assertEqual(response.status_code, 400)
        self.assertIn("Choose English, Marathi, Hindi, or Malayalam", response.json()["detail"])

    async def test_streaming_quota_error_is_not_hidden_by_local_fallback(self):
        async def quota_error(*_args, **_kwargs):
            if False:
                yield {}
            raise AIProviderUnavailable("quota_exceeded")

        with (
            patch.object(assistant_route.settings, "GEMINI_API_KEY", "configured"),
            patch.object(assistant_route.settings, "OPENAI_API_KEY", ""),
            patch.object(assistant_route, "stream_ai_conversation", quota_error),
        ):
            response = await self.client.post(
                "/api/assistant/chat/stream",
                headers={"X-Language": "ml"},
                json={"message": "മണ്ണിന്റെ ആരോഗ്യം എങ്ങനെ?", "history": []},
            )

        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json()["code"], "quota_exceeded")
        self.assertTrue(response.json()["detail"])

    async def test_streaming_quota_error_returns_http_error_with_machine_readable_code(self):
        async def quota_error(*_args, **_kwargs):
            if False:
                yield {}
            raise AIProviderUnavailable("quota_exceeded")

        with (
            patch.object(assistant_route.settings, "GEMINI_API_KEY", "configured"),
            patch.object(assistant_route.settings, "OPENAI_API_KEY", ""),
            patch.object(assistant_route, "stream_ai_conversation", quota_error),
        ):
            response = await self.client.post(
                "/api/assistant/chat/stream",
                headers={"X-Language": "en"},
                json={
                    "message": "What is today's market price for tomatoes in Pune?",
                    "history": [],
                },
            )

        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json()["code"], "quota_exceeded")
        self.assertIn("quota", response.json()["detail"].lower())

    async def test_streaming_error_event_before_first_chunk_returns_http_error(self):
        async def error_event(*_args, **_kwargs):
            yield {
                "type": "error",
                "code": "timeout",
                "detail": "Provider timeout detail",
            }

        with (
            patch.object(assistant_route.settings, "GEMINI_API_KEY", "configured"),
            patch.object(assistant_route, "stream_ai_conversation", error_event),
        ):
            response = await self.client.post(
                "/api/assistant/chat/stream",
                json={"message": "Reply briefly.", "history": []},
            )

        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json()["code"], "timeout")
        self.assertNotIn("Provider timeout detail", response.json()["detail"])

    async def test_openai_quota_error_is_typed_and_explained_in_stream(self):
        async def quota_error(*_args, **_kwargs):
            if False:
                yield {}
            raise AIProviderUnavailable("openai_quota_exceeded")

        with (
            patch.object(assistant_route.settings, "GEMINI_API_KEY", "configured"),
            patch.object(assistant_route.settings, "OPENAI_API_KEY", "configured"),
            patch.object(assistant_route, "stream_ai_conversation", quota_error),
        ):
            response = await self.client.post(
                "/api/assistant/chat/stream",
                headers={"X-Language": "en"},
                json={
                    "message": "What is today's market price for tomatoes in Pune?",
                    "history": [],
                },
            )

        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json()["code"], "openai_quota_exceeded")
        self.assertIn("OpenAI API quota or billing", response.json()["detail"])

    async def test_all_provider_quota_error_keeps_machine_readable_code(self):
        async def quota_error(*_args, **_kwargs):
            if False:
                yield {}
            raise AIProviderUnavailable("all_providers_quota_exceeded")

        with (
            patch.object(assistant_route.settings, "GEMINI_API_KEY", "configured"),
            patch.object(assistant_route.settings, "OPENAI_API_KEY", "configured"),
            patch.object(assistant_route, "stream_ai_conversation", quota_error),
        ):
            response = await self.client.post(
                "/api/assistant/chat/stream",
                headers={"X-Language": "en"},
                json={"message": "Reply briefly.", "history": []},
            )

        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json()["code"], "all_providers_quota_exceeded")
        self.assertIn("quota or billing", response.json()["detail"].lower())

    async def test_groq_stream_route_preserves_all_supported_languages_and_history(self):
        languages = {
            "en": "English",
            "mr": "Marathi (मराठी)",
            "hi": "Hindi (हिंदी)",
            "ml": "Malayalam (മലയാളം)",
        }
        captured_requests = []

        async def fake_groq_stream(message, system_prompt, history=None):
            captured_requests.append((message, system_prompt, history))
            yield f"Reply in {len(captured_requests)}"

        with (
            patch.object(assistant_route.settings, "GROQ_API_KEY", "configured"),
            patch.object(assistant_route.settings, "GROQ_MODEL", "llama-test-model"),
            patch.object(assistant_route.settings, "GEMINI_API_KEY", ""),
            patch.object(assistant_route.settings, "OPENAI_API_KEY", ""),
            patch.object(ai_service, "stream_groq", fake_groq_stream),
        ):
            for index, (language, language_name) in enumerate(languages.items(), start=1):
                response = await self.client.post(
                    "/api/assistant/chat/stream",
                    headers={"X-Language": language},
                    json={
                        "message": "Reply briefly.",
                        "context": {"crop": "maize"},
                        "history": [{"role": "assistant", "content": "Earlier response"}],
                    },
                )
                self.assertEqual(response.status_code, 200, language)
                self.assertIn(
                    f"Reply in {index}",
                    response.text,
                    language,
                )

        self.assertEqual(len(captured_requests), 4)
        for (language, language_name), captured in zip(languages.items(), captured_requests):
            message, prompt, history = captured
            self.assertEqual(message, "Reply briefly.")
            self.assertIn(f"Use {language_name} for your response.", prompt, language)
            self.assertIn("- Crop: maize", prompt, language)
            self.assertEqual(
                history,
                [{"role": "assistant", "content": "Earlier response"}],
                language,
            )

    async def test_streaming_failure_after_first_event_uses_sse_error_contract(self):
        async def partial_then_error(*_args, **_kwargs):
            yield {"type": "chunk", "text": "Partial answer"}
            raise AIProviderUnavailable("provider_error")

        with (
            patch.object(assistant_route.settings, "GEMINI_API_KEY", "configured"),
            patch.object(assistant_route, "stream_ai_conversation", partial_then_error),
        ):
            response = await self.client.post(
                "/api/assistant/chat/stream",
                json={"message": "Reply briefly.", "history": []},
            )

        self.assertEqual(response.status_code, 200)
        events = [
            json.loads(line[5:])
            for line in response.text.splitlines()
            if line.startswith("data:")
        ]
        self.assertEqual(events[0], {"type": "chunk", "text": "Partial answer"})
        self.assertEqual(events[-1]["type"], "error")
        self.assertEqual(events[-1]["code"], "provider_error")

    async def test_local_fallback_works_without_provider_configuration(self):
        with (
            patch.object(assistant_route.settings, "GEMINI_API_KEY", ""),
            patch.object(assistant_route.settings, "OPENAI_API_KEY", ""),
            patch.object(assistant_route, "call_ai_conversation", new=AsyncMock()) as provider_call,
        ):
            response = await self.client.post(
                "/api/assistant/chat",
                headers={"X-Language": "hi"},
                json={"message": "मिट्टी की सेहत कैसे सुधारें?", "history": []},
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["source"], "local_fallback")
        provider_call.assert_not_awaited()

    async def test_openai_only_configuration_is_used_for_assistant_chat(self):
        with (
            patch.object(assistant_route.settings, "GEMINI_API_KEY", ""),
            patch.object(assistant_route.settings, "OPENAI_API_KEY", "configured"),
            patch.object(
                assistant_route,
                "call_ai_conversation",
                new=AsyncMock(return_value=("A provider response.", "openai")),
            ) as provider_call,
        ):
            response = await self.client.post(
                "/api/assistant/chat",
                headers={"X-Language": "ml"},
                json={"message": "How can I improve soil health?", "history": []},
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {
            "response": "A provider response.",
            "source": "openai",
        })
        provider_call.assert_awaited_once()

    async def test_history_translation_returns_quota_error_without_faking_translation(self):
        with patch.object(
            assistant_route,
            "translate_texts",
            new=AsyncMock(
                side_effect=AIProviderUnavailable("quota_exceeded")
            ),
        ):
            response = await self.client.post(
                "/api/assistant/translate-history",
                headers={"X-Language": "ml"},
                json={"messages": ["Original diagnosis text."]},
            )

        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.headers["x-error-code"], "quota_exceeded")
        self.assertIn("ക്വോട്ട", response.json()["detail"])

    async def test_malayalam_local_fallback_is_available_without_provider(self):
        with (
            patch.object(assistant_route.settings, "GEMINI_API_KEY", ""),
            patch.object(assistant_route.settings, "OPENAI_API_KEY", ""),
            patch.object(assistant_route, "call_ai_conversation", new=AsyncMock()) as provider_call,
        ):
            response = await self.client.post(
                "/api/assistant/chat",
                headers={"X-Language": "ml"},
                json={"message": "മണ്ണിന്റെ ആരോഗ്യം എങ്ങനെ മെച്ചപ്പെടുത്താം?", "history": []},
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["source"], "local_fallback")
        self.assertIn("മണ്ണ്", response.json()["response"])
        provider_call.assert_not_awaited()


if __name__ == "__main__":
    unittest.main()
