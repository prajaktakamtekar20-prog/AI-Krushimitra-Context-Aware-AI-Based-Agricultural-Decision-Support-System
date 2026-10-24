import asyncio
import json
import socket
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import httpx

from services import ai_service
from routes import weather as weather_route


class GeminiQuotaTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        ai_service._translated_text_cache.clear()
        ai_service._translation_requests.clear()
        ai_service._gemini_quota_blocked_until = 0.0
        self.groq_key_patch = patch.object(ai_service.settings, "GROQ_API_KEY", "")
        self.groq_key_patch.start()

    async def asyncTearDown(self):
        ai_service._translated_text_cache.clear()
        ai_service._translation_requests.clear()
        ai_service._gemini_quota_blocked_until = 0.0
        self.groq_key_patch.stop()

    async def test_groq_model_is_checked_against_account_model_list(self):
        class FakeModelPage:
            def __aiter__(self):
                async def models():
                    yield SimpleNamespace(id="llama-test-model")
                return models()

        model_list = AsyncMock(return_value=FakeModelPage())
        client = SimpleNamespace(models=SimpleNamespace(list=model_list))
        with patch.object(ai_service, "_groq_model_cache", {}):
            await ai_service._verify_groq_model(
                client,
                "test-key",
                "llama-test-model",
            )
        model_list.assert_awaited_once_with()

    async def test_unavailable_groq_model_returns_configuration_error(self):
        class FakeModelPage:
            def __aiter__(self):
                async def models():
                    yield SimpleNamespace(id="another-model")
                return models()

        client = SimpleNamespace(
            models=SimpleNamespace(
                list=AsyncMock(return_value=FakeModelPage())
            )
        )
        with patch.object(ai_service, "_groq_model_cache", {}):
            with self.assertRaises(ai_service.AIProviderUnavailable) as caught:
                await ai_service._verify_groq_model(client, "test-key", "missing-model")
        self.assertEqual(caught.exception.reason, "groq_model_unavailable")

    async def test_groq_rate_limit_quota_auth_and_missing_model_errors_are_distinct(self):
        from openai import AuthenticationError, NotFoundError, RateLimitError

        request = httpx.Request("POST", ai_service.GROQ_API_BASE_URL + "/chat/completions")
        quota_error = RateLimitError(
            "Quota exceeded",
            response=httpx.Response(429, request=request),
            body={"error": {"code": "insufficient_quota", "message": "Quota exceeded"}},
        )
        rate_error = RateLimitError(
            "Rate limit reached",
            response=httpx.Response(429, request=request),
            body={"error": {"code": "rate_limit_exceeded", "message": "Too many requests"}},
        )
        auth_error = AuthenticationError(
            "Unauthorized",
            response=httpx.Response(401, request=request),
            body={"error": {"message": "Unauthorized"}},
        )
        model_error = NotFoundError(
            "Model not found",
            response=httpx.Response(404, request=request),
            body={"error": {"message": "Model not found"}},
        )

        self.assertEqual(ai_service._groq_error_reason(quota_error), "groq_quota_exceeded")
        self.assertEqual(ai_service._groq_error_reason(rate_error), "groq_rate_limited")
        self.assertEqual(ai_service._groq_error_reason(auth_error), "groq_auth")
        self.assertEqual(ai_service._groq_error_reason(model_error), "groq_model_unavailable")

    async def test_groq_non_streaming_request_uses_configured_model_and_conversation(self):
        completion = SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content="Groq response."))]
        )
        create = AsyncMock(return_value=completion)
        client = SimpleNamespace(
            chat=SimpleNamespace(completions=SimpleNamespace(create=create))
        )
        with (
            patch.object(ai_service.settings, "GROQ_API_KEY", "test-key"),
            patch.object(ai_service.settings, "GROQ_MODEL", "llama-test-model"),
            patch.object(ai_service, "_get_groq_client", return_value=client),
            patch.object(ai_service, "_verify_groq_model", new=AsyncMock()) as verify,
        ):
            answer = await ai_service.call_groq(
                "Question",
                "Use Malayalam.",
                [{"role": "user", "content": "Earlier question"}],
            )

        self.assertEqual(answer, "Groq response.")
        verify.assert_awaited_once_with(client, "test-key", "llama-test-model")
        self.assertEqual(create.await_args.kwargs["model"], "llama-test-model")
        self.assertEqual(create.await_args.kwargs["messages"][1], {
            "role": "user",
            "content": "Earlier question",
        })

    async def test_groq_retries_an_empty_completion_once_with_a_larger_output_budget(self):
        empty = SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content=None))]
        )
        completed = SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content='{"translated":true}'))]
        )
        create = AsyncMock(side_effect=[empty, completed])
        client = SimpleNamespace(
            chat=SimpleNamespace(completions=SimpleNamespace(create=create))
        )
        with (
            patch.object(ai_service.settings, "GROQ_API_KEY", "test-key"),
            patch.object(ai_service.settings, "GROQ_MODEL", "llama-test-model"),
            patch.object(ai_service, "_get_groq_client", return_value=client),
            patch.object(ai_service, "_verify_groq_model", new=AsyncMock()),
        ):
            answer = await ai_service.call_groq(
                "Translate the synthetic diagnosis.",
                "Return JSON only.",
                temperature=0.2,
            )

        self.assertEqual(answer, '{"translated":true}')
        self.assertEqual(create.await_count, 2)
        self.assertEqual(create.await_args_list[0].kwargs["max_tokens"], 1024)
        self.assertEqual(create.await_args_list[1].kwargs["max_tokens"], 2048)

    async def test_groq_stream_preserves_history_language_prompt_and_sse_chunks(self):
        async def chunks():
            yield SimpleNamespace(
                choices=[SimpleNamespace(delta=SimpleNamespace(content="नमस्कार"))]
            )
            yield SimpleNamespace(
                choices=[SimpleNamespace(delta=SimpleNamespace(content=" शेतकरी"))]
            )

        create = AsyncMock(return_value=chunks())
        client = SimpleNamespace(
            chat=SimpleNamespace(completions=SimpleNamespace(create=create))
        )
        with (
            patch.object(ai_service.settings, "GROQ_API_KEY", "test-key"),
            patch.object(ai_service.settings, "GROQ_MODEL", "llama-test-model"),
            patch.object(ai_service, "_get_groq_client", return_value=client),
            patch.object(ai_service, "_verify_groq_model", new=AsyncMock()),
        ):
            events = [
                event
                async for event in ai_service.stream_ai_conversation(
                    "नमस्कार",
                    "Use Marathi (मराठी) for your response.",
                    [{"role": "assistant", "content": "Earlier answer"}],
                )
            ]

        self.assertEqual(
            events,
            [
                {"type": "chunk", "text": "नमस्कार"},
                {"type": "chunk", "text": " शेतकरी"},
                {"type": "done", "source": "groq"},
            ],
        )
        self.assertEqual(create.await_args.kwargs["model"], "llama-test-model")
        self.assertEqual(create.await_args.kwargs["stream"], True)
        self.assertEqual(
            create.await_args.kwargs["messages"][1],
            {"role": "assistant", "content": "Earlier answer"},
        )
        self.assertEqual(
            create.await_args.kwargs["messages"][-1],
            {"role": "user", "content": "नमस्कार"},
        )

    def test_quota_and_rate_limit_responses_are_distinguished(self):
        quota_response = httpx.Response(
            429,
            json={
                "error": {
                    "status": "RESOURCE_EXHAUSTED",
                    "message": "You exceeded your current quota; check billing.",
                }
            },
            request=httpx.Request("POST", "https://example.test"),
        )
        rate_response = httpx.Response(
            429,
            headers={"Retry-After": "2"},
            json={
                "error": {
                    "status": "RESOURCE_EXHAUSTED",
                    "message": "Too many requests per minute.",
                }
            },
            request=httpx.Request("POST", "https://example.test"),
        )

        quota_details = ai_service._gemini_error_details(quota_response, "secret-key")
        rate_details = ai_service._gemini_error_details(rate_response, "secret-key")

        self.assertEqual(
            ai_service._gemini_429_error_type(quota_details["message"]),
            "gemini_quota_exceeded",
        )
        self.assertEqual(
            ai_service._gemini_429_error_type(rate_details["message"]),
            "gemini_rate_limited",
        )
        self.assertEqual(rate_details["retry_after"], "2")

    def test_chat_quota_details_preserve_metric_and_redact_credentials(self):
        metric = "generativelanguage.googleapis.com/generate_content_free_tier_requests"
        response = httpx.Response(
            429,
            json={
                "error": {
                    "status": "RESOURCE_EXHAUSTED",
                    "message": "Quota exceeded. " + ("details " * 80),
                    "details": [
                        {
                            "reason": "RATE_LIMIT_EXCEEDED",
                            "message": "Quota exceeded for metric: " + metric,
                            "metadata": {"api_key": "test-key"},
                        }
                    ],
                }
            },
            request=httpx.Request("POST", "https://example.test"),
        )

        details = ai_service._gemini_error_details(response, "test-key")

        self.assertIn(metric, details["message"])
        self.assertNotIn("test-key", details["message"])
        self.assertIn("[REDACTED]", details["message"])
        self.assertLessEqual(len(details["message"]), 1200)

    def test_chat_and_disease_use_one_shared_model_setting(self):
        with (
            patch.object(ai_service.settings, "GEMINI_MODEL", "shared-gemini-model"),
            patch.object(ai_service.settings, "GEMINI_CHAT_MODEL", "legacy-chat-model"),
            patch.object(ai_service.settings, "GEMINI_VISION_MODEL", "legacy-vision-model"),
        ):
            self.assertEqual(ai_service._get_gemini_model(), "shared-gemini-model")

    async def test_vision_uses_bounded_timeout_and_does_not_retry_slow_provider_failures(self):
        class SDKFailure(Exception):
            code = 503
            message = "provider unavailable"

        interactions = SimpleNamespace(create=AsyncMock(side_effect=SDKFailure()))

        class FakeAsyncClient:
            def __init__(self):
                self.interactions = interactions

            async def __aenter__(self):
                return self

            async def __aexit__(self, *_args):
                return None

        sdk_client = SimpleNamespace(aio=FakeAsyncClient())

        with (
            patch.object(ai_service.settings, "GEMINI_API_KEY", "test-key"),
            patch.object(ai_service.settings, "GEMINI_MODEL", "shared-gemini-model"),
            patch.object(ai_service, "_gemini_quota_blocked_until", 0.0),
            patch("google.genai.Client", return_value=sdk_client) as client_factory,
            patch.object(ai_service.asyncio, "sleep", new=AsyncMock()) as sleep,
            self.assertRaises(ai_service.GeminiVisionUnavailable),
        ):
            await ai_service.call_gemini_vision(
                b"test-image",
                "image/jpeg",
                "Analyze this plant image.",
                "Return JSON.",
            )

        http_options = client_factory.call_args.kwargs["http_options"]
        self.assertEqual(http_options.timeout, ai_service.GEMINI_VISION_TIMEOUT_MS)
        self.assertEqual(ai_service.GEMINI_VISION_TIMEOUT_MS, 20_000)
        self.assertEqual(ai_service.GEMINI_TRANSIENT_RETRIES, 1)
        self.assertEqual(interactions.create.await_count, 1)
        self.assertEqual(
            interactions.create.await_args.kwargs["model"],
            "shared-gemini-model",
        )
        sleep.assert_not_awaited()

    async def test_vision_enforces_deadline_when_sdk_call_does_not(self):
        async def slow_create(**_kwargs):
            await asyncio.sleep(1)

        sdk_client = SimpleNamespace(
            interactions=SimpleNamespace(create=AsyncMock(side_effect=slow_create))
        )
        with (
            patch.object(ai_service.settings, "GEMINI_API_KEY", "test-key"),
            patch.object(ai_service, "_gemini_quota_blocked_until", 0.0),
            patch.object(ai_service, "_get_gemini_vision_client", new=AsyncMock(return_value=sdk_client)),
            patch.object(ai_service, "GEMINI_VISION_TIMEOUT_MS", 10),
            self.assertRaises(ai_service.GeminiVisionUnavailable) as caught,
            self.assertLogs(ai_service.logger, level="WARNING") as logs,
        ):
            started = asyncio.get_running_loop().time()
            await ai_service.call_gemini_vision(
                b"test-image",
                "image/jpeg",
                "Analyze this plant image.",
                "Return JSON.",
            )

        self.assertEqual(caught.exception.error_type, "gemini_timeout")
        self.assertLess(asyncio.get_running_loop().time() - started, 0.5)
        self.assertTrue(any("error_type=gemini_timeout" in message for message in logs.output))
        self.assertFalse(any("test-key" in message for message in logs.output))

    async def test_vision_retries_rate_limit_after_retry_after_within_deadline(self):
        class SDKFailure(Exception):
            code = 429
            message = "RATE_LIMIT_EXCEEDED: Too many requests per minute."
            response = SimpleNamespace(headers={"Retry-After": "2"})

        interactions = SimpleNamespace(create=AsyncMock(
            side_effect=[
                SDKFailure(),
                SimpleNamespace(output_text="analysis result"),
            ]
        ))
        sdk_client = SimpleNamespace(interactions=interactions)

        with (
            patch.object(ai_service.settings, "GEMINI_API_KEY", "test-key"),
            patch.object(ai_service, "_gemini_quota_blocked_until", 0.0),
            patch.object(ai_service, "_get_gemini_vision_client", new=AsyncMock(return_value=sdk_client)),
            patch.object(ai_service.asyncio, "sleep", new=AsyncMock()) as sleep,
            patch.object(ai_service.random, "uniform", return_value=0.0),
        ):
            result = await ai_service.call_gemini_vision(
                b"test-image",
                "image/jpeg",
                "Analyze this plant image.",
                "Return JSON.",
            )

        self.assertEqual(result, "analysis result")
        self.assertEqual(interactions.create.await_count, 2)
        sleep.assert_awaited_once_with(2.0)
        self.assertFalse(ai_service._gemini_quota_cooldown_active())

    async def test_vision_quota_exhaustion_is_not_retried_and_sets_cooldown(self):
        class SDKFailure(Exception):
            code = 429
            message = "You exceeded your current quota; check billing."
            details = {
                "error": {
                    "status": "RESOURCE_EXHAUSTED",
                    "message": "You exceeded your current quota; check billing.",
                }
            }

        interactions = SimpleNamespace(create=AsyncMock(side_effect=SDKFailure()))
        sdk_client = SimpleNamespace(interactions=interactions)
        with (
            patch.object(ai_service.settings, "GEMINI_API_KEY", "test-key"),
            patch.object(ai_service, "_gemini_quota_blocked_until", 0.0),
            patch.object(ai_service, "_get_gemini_vision_client", new=AsyncMock(return_value=sdk_client)),
            self.assertLogs(ai_service.logger, level="WARNING") as logs,
        ):
            with self.assertRaises(ai_service.GeminiVisionUnavailable) as caught:
                await ai_service.call_gemini_vision(
                    b"test-image",
                    "image/jpeg",
                    "Analyze this plant image.",
                    "Return JSON.",
                )
            self.assertTrue(ai_service._gemini_quota_cooldown_active())

        self.assertEqual(caught.exception.error_type, "gemini_quota_exceeded")
        self.assertEqual(interactions.create.await_count, 1)
        self.assertTrue(any("RESOURCE_EXHAUSTED" in message for message in logs.output))
        self.assertFalse(any("test-key" in message for message in logs.output))

    async def test_chat_quota_error_stops_without_trying_other_models(self):
        response = httpx.Response(
            429,
            json={
                "error": {
                    "status": "RESOURCE_EXHAUSTED",
                    "message": "You exceeded your current quota; check billing.",
                }
            },
            request=httpx.Request("POST", "https://example.test"),
        )
        client = type("FakeClient", (), {"post": AsyncMock(return_value=response)})()

        with (
            patch.object(ai_service, "_get_gemini_api_key", return_value="test-key"),
            patch.object(ai_service, "_get_chat_http_client", return_value=client),
            patch.object(ai_service.settings, "GEMINI_MODEL", "gemini-test"),
        ):
            with self.assertRaises(ai_service.AIProviderUnavailable) as caught:
                await ai_service.call_gemini("question", "system prompt")

        self.assertEqual(caught.exception.reason, "quota_exceeded")
        self.assertEqual(client.post.await_count, 1)
        self.assertIn(
            "/models/gemini-test:generateContent",
            client.post.await_args.args[0],
        )

        with self.assertRaises(ai_service.AIProviderUnavailable) as cooldown_error:
            await ai_service.call_gemini("another question", "system prompt")

        self.assertEqual(cooldown_error.exception.reason, "quota_exceeded")
        self.assertEqual(client.post.await_count, 1)

    async def test_chat_retries_transient_server_error_once_for_the_same_model(self):
        response = httpx.Response(
            503,
            request=httpx.Request("POST", "https://example.test"),
        )
        success = httpx.Response(
            200,
            json={
                "candidates": [
                    {
                        "finishReason": "STOP",
                        "content": {"parts": [{"text": "Recovered answer."}]},
                    }
                ]
            },
            request=httpx.Request("POST", "https://example.test"),
        )
        client = type(
            "FakeClient",
            (),
            {"post": AsyncMock(side_effect=[response, success])},
        )()

        with (
            patch.object(ai_service, "_get_gemini_api_key", return_value="test-key"),
            patch.object(ai_service, "_get_chat_http_client", return_value=client),
            patch.object(ai_service.settings, "GEMINI_MODEL", "gemini-test"),
            patch.object(ai_service.asyncio, "sleep", new=AsyncMock()) as sleep,
        ):
            result = await ai_service.call_gemini("question", "system prompt")

        self.assertEqual(result, "Recovered answer.")
        self.assertEqual(client.post.await_count, 2)
        sleep.assert_awaited_once_with(ai_service.GEMINI_RETRY_BASE_DELAY_SECONDS)

    async def test_chat_timeout_retries_once_then_reports_timeout(self):
        timeout = httpx.ReadTimeout(
            "timed out",
            request=httpx.Request("POST", "https://example.test"),
        )
        client = type(
            "FakeClient",
            (),
            {"post": AsyncMock(side_effect=[timeout, timeout])},
        )()
        with (
            patch.object(ai_service, "_get_gemini_api_key", return_value="test-key"),
            patch.object(ai_service, "_get_chat_http_client", return_value=client),
            patch.object(ai_service.settings, "GEMINI_MODEL", "gemini-test"),
            patch.object(ai_service.asyncio, "sleep", new=AsyncMock()) as sleep,
            self.assertLogs(ai_service.logger, level="WARNING"),
        ):
            with self.assertRaises(ai_service.AIProviderUnavailable) as caught:
                await ai_service.call_gemini("question", "system prompt")

        self.assertEqual(caught.exception.reason, "timeout")
        self.assertEqual(client.post.await_count, 2)
        sleep.assert_awaited_once_with(ai_service.GEMINI_RETRY_BASE_DELAY_SECONDS)

    async def test_chat_falls_back_to_openai_when_gemini_provider_fails(self):
        with (
            patch.object(ai_service.settings, "GEMINI_API_KEY", "configured"),
            patch.object(ai_service.settings, "OPENAI_API_KEY", "configured"),
            patch.object(
                ai_service,
                "call_gemini",
                new=AsyncMock(
                    side_effect=ai_service.AIProviderUnavailable("quota_exceeded")
                ),
            ),
            patch.object(
                ai_service,
                "call_openai",
                new=AsyncMock(return_value="OpenAI response"),
            ) as call_openai,
        ):
            answer = await ai_service.call_ai_conversation("question", "system prompt")

        self.assertEqual(answer, ("OpenAI response", "openai"))
        call_openai.assert_awaited_once_with("question", "system prompt", history=None)

    async def test_chat_reports_provider_failure_when_fallback_also_fails(self):
        with (
            patch.object(ai_service.settings, "GEMINI_API_KEY", "configured"),
            patch.object(ai_service.settings, "OPENAI_API_KEY", "configured"),
            patch.object(
                ai_service,
                "call_gemini",
                new=AsyncMock(
                    side_effect=ai_service.AIProviderUnavailable("quota_exceeded")
                ),
            ),
            patch.object(
                ai_service,
                "call_openai",
                new=AsyncMock(
                    side_effect=ai_service.AIProviderUnavailable("openai_quota_exceeded")
                ),
            ),
        ):
            with self.assertRaises(ai_service.AIProviderUnavailable) as caught:
                await ai_service.call_ai_conversation("question", "system prompt")

        self.assertEqual(caught.exception.reason, "all_providers_quota_exceeded")

    async def test_stream_uses_supported_gemini_generate_content_and_keeps_sse_contract(self):
        with (
            patch.object(ai_service.settings, "GEMINI_API_KEY", "configured"),
            patch.object(ai_service.settings, "OPENAI_API_KEY", ""),
            patch.object(
                ai_service,
                "call_gemini",
                new=AsyncMock(return_value="Gemini response"),
            ) as call_gemini,
            patch.object(ai_service, "stream_gemini", new=AsyncMock()) as stream_gemini,
        ):
            events = [
                event
                async for event in ai_service.stream_ai_conversation(
                    "question",
                    "system prompt",
                )
            ]

        self.assertEqual(
            events,
            [
                {"type": "chunk", "text": "Gemini response"},
                {"type": "done", "source": "gemini"},
            ],
        )
        call_gemini.assert_awaited_once_with("question", "system prompt", None)
        stream_gemini.assert_not_awaited()

    async def test_stream_aggregates_quota_failures_from_both_providers(self):
        async def raise_openai_quota(*_args, **_kwargs):
            if False:
                yield ""
            raise ai_service.AIProviderUnavailable("openai_quota_exceeded")

        with (
            patch.object(ai_service.settings, "GEMINI_API_KEY", "configured"),
            patch.object(ai_service.settings, "OPENAI_API_KEY", "configured"),
            patch.object(
                ai_service,
                "call_gemini",
                new=AsyncMock(
                    side_effect=ai_service.AIProviderUnavailable("quota_exceeded")
                ),
            ),
            patch.object(ai_service, "stream_openai", raise_openai_quota),
        ):
            with self.assertRaises(ai_service.AIProviderUnavailable) as caught:
                _ = [
                    event
                    async for event in ai_service.stream_ai_conversation(
                        "question",
                        "system prompt",
                    )
                ]

        self.assertEqual(caught.exception.reason, "all_providers_quota_exceeded")

    async def test_chat_timeout_budget_fits_frontend_request_deadline(self):
        self.assertEqual(ai_service.GEMINI_CHAT_TIMEOUT_SECONDS, 25.0)
        self.assertEqual(ai_service.GEMINI_TRANSIENT_RETRIES, 1)
        self.assertLess(
            ai_service.GEMINI_CHAT_TIMEOUT_SECONDS
            * (ai_service.GEMINI_TRANSIENT_RETRIES + 1)
            + ai_service.GEMINI_RETRY_BASE_DELAY_SECONDS,
            60.0,
        )

    async def test_stream_retries_transient_server_error_before_emitting_text(self):
        class StreamingResponse:
            def __init__(self, status_code, lines=()):
                self.status_code = status_code
                self.lines = lines

            async def __aenter__(self):
                return self

            async def __aexit__(self, *_args):
                return None

            async def aiter_lines(self):
                for line in self.lines:
                    yield line

            async def aread(self):
                return b""

            def raise_for_status(self):
                if self.status_code >= 400:
                    raise httpx.HTTPStatusError(
                        "provider error",
                        request=httpx.Request("POST", "https://example.test"),
                        response=httpx.Response(
                            self.status_code,
                            request=httpx.Request("POST", "https://example.test"),
                        ),
                    )

        class FakeClient:
            def __init__(self):
                self.responses = [
                    StreamingResponse(503),
                    StreamingResponse(
                        200,
                        [
                            "data: "
                            + json.dumps(
                                {
                                    "candidates": [
                                        {
                                            "content": {
                                                "parts": [{"text": "Recovered stream."}]
                                            }
                                        }
                                    ]
                                }
                            )
                        ],
                    ),
                ]
                self.calls = 0

            def stream(self, *_args, **_kwargs):
                response = self.responses[self.calls]
                self.calls += 1
                return response

        client = FakeClient()
        with (
            patch.object(ai_service, "_get_gemini_api_key", return_value="test-key"),
            patch.object(ai_service, "_get_chat_http_client", return_value=client),
            patch.object(ai_service.settings, "GEMINI_MODEL", "gemini-test"),
            patch.object(ai_service.asyncio, "sleep", new=AsyncMock()) as sleep,
        ):
            chunks = [
                chunk
                async for chunk in ai_service.stream_gemini(
                    "question", "system prompt"
                )
            ]

        self.assertEqual(chunks, ["Recovered stream."])
        self.assertEqual(client.calls, 2)
        sleep.assert_awaited_once_with(ai_service.GEMINI_RETRY_BASE_DELAY_SECONDS)

    def test_transport_errors_are_distinguished(self):
        dns_error = httpx.ConnectError(
            "name resolution failed",
            request=httpx.Request("POST", "https://example.test"),
        )
        dns_error.__cause__ = socket.gaierror("name resolution failed")
        connection_error = httpx.ConnectError(
            "connection refused",
            request=httpx.Request("POST", "https://example.test"),
        )
        timeout_error = httpx.ReadTimeout(
            "timed out",
            request=httpx.Request("POST", "https://example.test"),
        )

        self.assertEqual(ai_service._httpx_transport_error_reason(dns_error), "dns_error")
        self.assertEqual(ai_service._httpx_transport_error_reason(connection_error), "connection_error")
        self.assertEqual(ai_service._httpx_transport_error_reason(timeout_error), "timeout")

    async def test_openai_fallback_uses_the_official_sdk(self):
        completion = SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content="A concise answer."))]
        )
        create = AsyncMock(return_value=completion)
        client = SimpleNamespace(
            chat=SimpleNamespace(completions=SimpleNamespace(create=create))
        )

        with (
            patch.object(ai_service.settings, "OPENAI_API_KEY", "test-key"),
            patch.object(ai_service, "_get_openai_client", return_value=client) as get_client,
        ):
            answer = await ai_service.call_openai("question", "system prompt")

        self.assertEqual(answer, "A concise answer.")
        get_client.assert_called_once_with()
        create.assert_awaited_once()
        self.assertEqual(create.await_args.kwargs["model"], ai_service.OPENAI_CHAT_MODEL)
        self.assertEqual(create.await_args.kwargs["messages"][-1], {
            "role": "user",
            "content": "question",
        })
        self.assertNotIn("api_key", create.await_args.kwargs)
        self.assertEqual(ai_service.CHAT_PROVIDER_TIMEOUT_SECONDS, 30.0)

    async def test_openai_streaming_uses_sdk_chunks(self):
        async def chunks():
            yield SimpleNamespace(
                choices=[SimpleNamespace(delta=SimpleNamespace(content="Namaste"))]
            )
            yield SimpleNamespace(
                choices=[SimpleNamespace(delta=SimpleNamespace(content=" farmer"))]
            )

        create = AsyncMock(return_value=chunks())
        client = SimpleNamespace(
            chat=SimpleNamespace(completions=SimpleNamespace(create=create))
        )
        with patch.object(ai_service, "_get_openai_client", return_value=client):
            answer = [
                chunk async for chunk in ai_service.stream_openai("question", "system prompt")
            ]

        self.assertEqual(answer, ["Namaste", " farmer"])
        self.assertTrue(create.await_args.kwargs["stream"])

    async def test_openai_quota_errors_are_distinguished_from_rate_limits(self):
        from openai import APITimeoutError, RateLimitError

        request = httpx.Request("POST", "https://api.openai.com/v1/chat/completions")
        quota_response = httpx.Response(429, request=request)
        quota_error = RateLimitError(
            "Quota exceeded",
            response=quota_response,
            body={"error": {"code": "insufficient_quota", "message": "Quota exceeded"}},
        )
        rate_response = httpx.Response(429, request=request)
        rate_error = RateLimitError(
            "Rate limit reached",
            response=rate_response,
            body={"error": {"code": "rate_limit_exceeded", "message": "Slow down"}},
        )

        self.assertEqual(
            ai_service._openai_error_reason(quota_error),
            "openai_quota_exceeded",
        )
        self.assertEqual(ai_service._openai_error_reason(rate_error), "openai_rate_limit")
        self.assertEqual(
            ai_service._openai_error_reason(APITimeoutError(request=request)),
            "timeout",
        )

    async def test_history_translation_is_cached_and_concurrent_calls_are_deduplicated(self):
        async def translate(prompt, _system_prompt, **_kwargs):
            source = json.loads(prompt.split("\n\n", 1)[1])
            await asyncio.sleep(0.01)
            return json.dumps([f"मराठी: {item}" for item in source], ensure_ascii=False)

        with patch.object(ai_service, "call_ai_model", new=AsyncMock(side_effect=translate)) as model:
            first, concurrent = await asyncio.gather(
                ai_service.translate_texts(["hello", "hello"], "mr"),
                ai_service.translate_texts(["hello", "hello"], "mr"),
            )
            repeated = await ai_service.translate_texts(["hello"], "mr")

        self.assertEqual(first, ["मराठी: hello", "मराठी: hello"])
        self.assertEqual(concurrent, first)
        self.assertEqual(repeated, ["मराठी: hello"])
        self.assertEqual(model.await_count, 1)

    async def test_known_system_messages_use_local_translations_without_provider_call(self):
        with patch.object(ai_service, "call_ai_model", new=AsyncMock()) as model:
            for source_language in ("en", "mr", "hi", "ml"):
                message = ai_service.localized_message(
                    source_language,
                    "translation_unavailable",
                )
                translated = await ai_service.translate_texts([message, message], "ml")
                self.assertEqual(
                    translated,
                    [ai_service.localized_message("ml", "translation_unavailable")] * 2,
                )

        model.assert_not_awaited()

    async def test_translation_rejects_unsupported_language_code(self):
        with self.assertRaises(ValueError):
            await ai_service.translate_texts(["hello"], "kn")

    async def test_malformed_history_translation_json_returns_no_translation(self):
        with patch.object(
            ai_service,
            "call_ai_model",
            new=AsyncMock(return_value='["translated",'),
        ):
            translated = await ai_service._translate_text_batch(["source"], "ml")

        self.assertIsNone(translated)

    async def test_weather_advisory_uses_localized_quota_error_after_translation_failure(self):
        with (
            patch.object(
                weather_route,
                "generate_crop_advisory",
                return_value={"advisories": ["Water according to soil moisture."]},
            ),
            patch.object(
                weather_route,
                "translate_texts",
                new=AsyncMock(
                    side_effect=ai_service.AIProviderUnavailable("quota_exceeded")
                ),
            ),
        ):
            advisory = await weather_route._get_localized_advisory(
                {}, "Tomato", "flowering", "ml"
            )

        self.assertEqual(
            advisory["advisories"],
            [ai_service.localized_message("ml", "translation_quota_unavailable")],
        )

    async def test_history_translation_to_english_does_not_keep_the_previous_language(self):
        with patch.object(
            ai_service,
            "_translate_text_batch",
            new=AsyncMock(return_value=["Clear the field drains."]),
        ) as translate:
            translated = await ai_service.translate_texts(
                ["खेत की नालियाँ साफ़ करें।"],
                "en",
            )

        self.assertEqual(translated, ["Clear the field drains."])
        translate.assert_awaited_once_with(["खेत की नालियाँ साफ़ करें।"], "en")
