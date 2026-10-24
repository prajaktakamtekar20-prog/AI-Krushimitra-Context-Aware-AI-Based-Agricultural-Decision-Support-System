import unittest
from contextlib import redirect_stdout
from io import StringIO
from types import SimpleNamespace
from unittest.mock import patch

from check_gemini_models import inspect_model_access, main


class GeminiModelCheckTests(unittest.TestCase):
    def test_lists_models_without_action_metadata(self):
        models = [
            SimpleNamespace(
                name="models/gemini-3.8-flash",
            ),
            SimpleNamespace(
                name="models/gemini-2.5-flash",
            ),
            SimpleNamespace(
                name="models/text-embedding-test",
            ),
        ]

        available, configured_is_available = inspect_model_access(
            models,
            "gemini-3.8-flash",
        )

        self.assertEqual(
            available,
            ["gemini-2.5-flash", "gemini-3.8-flash", "text-embedding-test"],
        )
        self.assertTrue(configured_is_available)

    def test_reports_configured_model_not_listed_for_key(self):
        available, configured_is_available = inspect_model_access(
            [
                SimpleNamespace(
                    name="models/gemini-other",
                )
            ],
            "models/gemini-3.8-flash",
        )

        self.assertEqual(available, ["gemini-other"])
        self.assertFalse(configured_is_available)

    def test_model_listing_uses_key_without_printing_it(self):
        from check_gemini_models import genai

        api_key = "sensitive-test-key"
        client = SimpleNamespace(
            models=SimpleNamespace(
                list=lambda: [
                    SimpleNamespace(
                        name="models/gemini-3.8-flash",
                    )
                ]
            ),
            close=lambda: None,
        )
        environment = {
            "GEMINI_API_KEY": api_key,
            "GEMINI_VISION_MODEL": "gemini-3.8-flash",
        }
        output = StringIO()

        with (
            patch("check_gemini_models.load_dotenv"),
            patch(
                "check_gemini_models.os.getenv",
                side_effect=lambda name: environment.get(name),
            ),
            patch.object(genai, "Client", return_value=client) as client_factory,
            redirect_stdout(output),
        ):
            exit_code = main()

        self.assertEqual(exit_code, 0)
        self.assertEqual(client_factory.call_args.kwargs["api_key"], api_key)
        self.assertIn("Configured model listed by Google's model API: yes", output.getvalue())
        self.assertNotIn(api_key, output.getvalue())


if __name__ == "__main__":
    unittest.main()
