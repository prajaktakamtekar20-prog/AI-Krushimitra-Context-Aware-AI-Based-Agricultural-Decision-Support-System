import json
import unittest
import io
import asyncio
import re
from pathlib import Path
from unittest.mock import AsyncMock, patch

import httpx
from fastapi import FastAPI

from services import ai_service
from services.disease_knowledge_base import lookup_disease_knowledge
from services.disease_result_localization import DISEASE_RESULT_TRANSLATIONS
from services.disease_result_localization import localize_disease_result
from services.disease_model_service import (
    build_crop_disease_key,
    get_supported_classes,
    map_class_to_disease_key,
    split_class_name,
)
from services.localization import LANGUAGE_NAMES, localized_message, resolve_language
from routes import disease as disease_route
from fastapi import UploadFile
from starlette.datastructures import Headers


class DiseaseLocalizationTests(unittest.IsolatedAsyncioTestCase):
    def test_backend_supports_only_the_four_configured_languages(self):
        self.assertEqual(set(LANGUAGE_NAMES), {"en", "mr", "hi", "ml"})
        for language in LANGUAGE_NAMES:
            self.assertEqual(resolve_language(language.upper()), language)
        with self.assertRaises(ValueError):
            resolve_language("kn")

    def test_shared_disease_dictionary_has_the_same_nonempty_fields_in_all_languages(self):
        self.assertEqual(set(DISEASE_RESULT_TRANSLATIONS), {"en", "mr", "hi", "ml"})
        required_fields = set(DISEASE_RESULT_TRANSLATIONS["en"])
        required_labels = set(DISEASE_RESULT_TRANSLATIONS["en"]["fieldLabels"])
        for language, translations in DISEASE_RESULT_TRANSLATIONS.items():
            with self.subTest(language=language):
                self.assertEqual(set(translations), required_fields)
                self.assertTrue(all(translations[field].strip() for field in (
                    "crop", "disease", "partialNotice", "diagnosticNote"
                )))
                self.assertEqual(set(translations["fieldLabels"]), required_labels)
                self.assertTrue(all(label.strip() for label in translations["fieldLabels"].values()))
                self.assertEqual(len(translations["symptoms"]), 4)
                self.assertEqual(len(translations["causes"]), 4)
                self.assertEqual(len(translations["treatment"]), 4)
                self.assertEqual(len(translations["prevention"]), 5)
                gray = translations["grayLeafSpot"]
                self.assertEqual(len(gray["symptoms"]), 4)
                self.assertEqual(len(gray["causes"]), 4)
                self.assertEqual(len(gray["treatment"]), 4)
                self.assertEqual(len(gray["prevention"]), 5)
                self.assertTrue(all(
                    gray[field].strip()
                    for field in (
                        "crop", "disease", "severity", "diagnosticNote", "safetyWarning"
                    )
                ))
                self.assertEqual(
                    set(translations["severityLabels"]),
                    {
                        "Mild (None)", "Mild", "Mild to Moderate",
                        "Moderate", "Moderate to Severe", "Severe",
                    },
                )
                self.assertTrue(all(translations["severityLabels"].values()))

    def gray_leaf_spot_diagnosis(self):
        knowledge = lookup_disease_knowledge("Corn (Maize)", "corn_leaf_spot")
        self.assertIsNotNone(knowledge)
        return {
            "ok": True,
            "is_valid_plant_image": True,
            "crop": knowledge["crop"],
            "disease": knowledge["disease"],
            "disease_key": "corn_leaf_spot",
            "raw_class": "Corn_(maize)___Cercospora_leaf_spot Gray_leaf_spot",
            "severity": knowledge["severity"],
            "symptoms": knowledge["symptoms"],
            "possible_causes": knowledge["causes"],
            "recommended_management": knowledge["treatment"],
            "prevention": knowledge["prevention"],
            "safety_warnings": [
                "Use only locally registered agrochemicals for this crop and problem; always read "
                "and follow the product label, local agricultural extension recommendations, and "
                "respect re-entry / pre-harvest intervals."
            ],
            "diagnostic_note": (
                "This is a preliminary image-model result, not a confirmed diagnosis. "
                "Model scores are not calibrated probabilities; ask an agricultural expert "
                "to confirm, especially before taking treatment action."
            ),
            "confidence": 96.0,
            "crop_confidence": 99.0,
        }

    def test_gray_leaf_spot_localizes_every_verified_field_and_bullet(self):
        source = self.gray_leaf_spot_diagnosis()
        english_reference = DISEASE_RESULT_TRANSLATIONS["en"]["grayLeafSpot"]
        self.assertEqual(source["crop"], english_reference["crop"])
        self.assertEqual(source["disease"], english_reference["disease"])
        self.assertEqual(source["severity"], english_reference["severity"])
        self.assertEqual(source["symptoms"], english_reference["symptoms"])
        self.assertEqual(source["possible_causes"], english_reference["causes"])
        self.assertEqual(source["recommended_management"], english_reference["treatment"])
        self.assertEqual(source["prevention"], english_reference["prevention"])
        for language, script in (
            ("en", None),
            ("mr", re.compile(r"[\u0900-\u097f]")),
            ("hi", re.compile(r"[\u0900-\u097f]")),
            ("ml", re.compile(r"[\u0d00-\u0d7f]")),
        ):
            with self.subTest(language=language):
                localized = localize_disease_result(source, language)
                translation = DISEASE_RESULT_TRANSLATIONS[language]["grayLeafSpot"]
                self.assertEqual(localized["crop_display"], translation["crop"])
                self.assertEqual(localized["disease_display"], translation["disease"])
                self.assertEqual(localized["severity"], translation["severity"])
                self.assertEqual(localized["symptoms"], translation["symptoms"])
                self.assertEqual(localized["possible_causes"], translation["causes"])
                self.assertEqual(localized["recommended_management"], translation["treatment"])
                self.assertEqual(localized["prevention"], translation["prevention"])
                self.assertEqual(localized["diagnostic_note"], translation["diagnosticNote"])
                self.assertEqual(localized["safety_warnings"], [translation["safetyWarning"]])
                self.assertEqual(localized["confidence"], 96.0)
                self.assertEqual(localized["crop_confidence"], 99.0)
                self.assertTrue(localized["_translation_complete"])
                self.assertEqual(localized["_untranslated_fields"], [])
                self.assertIn("Cercospora zeae-maydis", localized["disease_display"])
                translated_text = " ".join(
                    localized[field] if isinstance(localized[field], str)
                    else " ".join(localized[field])
                    for field in (
                        "symptoms",
                        "possible_causes",
                        "recommended_management",
                        "prevention",
                    )
                )
                for preserved in ("1-4 mm", "12-24+", "22-30°C", "14-21", "1-2", "250 EC"):
                    self.assertIn(preserved, translated_text)

                if script:
                    for field in (
                        "crop_display",
                        "disease_display",
                        "severity",
                        "diagnostic_note",
                    ):
                        self.assertRegex(localized[field], script, field)
                    self.assertTrue(all(
                        script.search(item) for item in localized["safety_warnings"]
                    ))
                    for field in (
                        "symptoms",
                        "possible_causes",
                        "recommended_management",
                        "prevention",
                    ):
                        self.assertTrue(all(script.search(item) for item in localized[field]), field)

    def test_unverified_gray_leaf_spot_evidence_note_is_preserved_and_marked(self):
        diagnosis = self.gray_leaf_spot_diagnosis()
        diagnosis["diagnostic_note"] = (
            "Visible lesions appear rectangular. This is a preliminary image-model result, "
            "not a confirmed diagnosis."
        )
        localized = localize_disease_result(diagnosis, "mr")
        self.assertEqual(localized["diagnostic_note"], diagnosis["diagnostic_note"])
        self.assertIn("diagnostic_note", localized["_untranslated_fields"])
        self.assertFalse(localized["_translation_complete"])
        self.assertIn("निदानाची नोंद", localized["translation_notice"])

    def test_complete_diagnostic_disclaimer_is_localized_without_duplicate_english_text(self):
        diagnosis = self.gray_leaf_spot_diagnosis()
        diagnosis["diagnostic_note"] = (
            "The visual analysis agrees with the local classifier's supported crop/disease class. "
            "Confidence values are model scores, not calibrated probabilities. Chemical instructions "
            "are omitted unless verified against current local product labels. This is a preliminary "
            "image-model result, not a confirmed diagnosis. Model scores are not calibrated "
            "probabilities; ask an agricultural expert to confirm, especially before taking treatment "
            "action."
        )

        for language, script in (
            ("en", None),
            ("mr", re.compile(r"[\u0900-\u097f]")),
            ("hi", re.compile(r"[\u0900-\u097f]")),
            ("ml", re.compile(r"[\u0d00-\u0d7f]")),
        ):
            with self.subTest(language=language):
                localized = localize_disease_result(diagnosis, language)
                expected = DISEASE_RESULT_TRANSLATIONS[language]["diagnosticDisclaimer"]
                self.assertEqual(localized["diagnostic_note"], expected)
                if language != "en":
                    self.assertNotIn(
                        "The visual analysis agrees",
                        localized["diagnostic_note"],
                    )
                self.assertNotIn("diagnostic_note", localized["_untranslated_fields"])
                self.assertTrue(localized["_translation_complete"])
                if script:
                    self.assertRegex(localized["diagnostic_note"], script)

    def test_model_class_translation_coverage_report_matches_all_38_canonical_labels(self):
        fields = (
            "crop_display",
            "disease_display",
            "severity",
            "symptoms",
            "possible_causes",
            "causes",
            "recommended_management",
            "treatment",
            "prevention",
            "safety_warnings",
            "warnings",
            "precautions",
            "diagnostic_note",
            "error",
        )
        source_fields = {
            "crop_display": "crop",
            "disease_display": "disease",
            "causes": "possible_causes",
            "treatment": "recommended_management",
        }
        classes = get_supported_classes()
        self.assertEqual(len(classes), 38)
        report_path = Path(__file__).resolve().parents[2] / "shared" / "disease_translation_coverage.json"
        report = json.loads(report_path.read_text(encoding="utf-8"))
        self.assertEqual(report["canonicalClassCount"], 38)
        self.assertEqual([entry["classId"] for entry in report["classes"]], classes)
        for entry in report["classes"]:
            crop, disease = split_class_name(entry["classId"])
            generic_key = map_class_to_disease_key(entry["classId"])
            disease_key = build_crop_disease_key(crop, generic_key)
            knowledge = lookup_disease_knowledge(crop, disease_key, generic_key)
            self.assertIsNotNone(knowledge, entry["classId"])
            diagnosis = {
                "crop": knowledge["crop"],
                "disease": knowledge["disease"],
                "disease_key": disease_key,
                "raw_class": entry["classId"],
                "severity": knowledge["severity"],
                "symptoms": knowledge["symptoms"],
                "possible_causes": knowledge["causes"],
                "causes": knowledge["causes"],
                "recommended_management": knowledge["treatment"],
                "treatment": knowledge["treatment"],
                "prevention": knowledge["prevention"],
                "diagnostic_note": (
                    "This is a preliminary image-model result, not a confirmed diagnosis. "
                    "Model scores are not calibrated probabilities; ask an agricultural expert "
                    "to confirm, especially before taking treatment action."
                ),
            }
            for language in ("en", "mr", "hi", "ml"):
                localized = localize_disease_result(diagnosis, language)
                observed = {}
                for field in fields:
                    source_field = source_fields.get(field, field)
                    translation_field = {
                        "causes": "possible_causes",
                        "treatment": "recommended_management",
                    }.get(field, field)
                    if not diagnosis.get(source_field):
                        status = "not_applicable"
                    elif language == "en":
                        status = "source_language"
                    elif translation_field in localized["_untranslated_fields"]:
                        status = "missing"
                    else:
                        status = "verified"
                    observed[field] = status
                self.assertEqual(entry["languages"][language]["fields"], observed, entry["classId"])

    def test_disease_upload_and_server_messages_exist_in_all_supported_languages(self):
        message_keys = (
            "image_too_large",
            "image_type_mismatch",
            "disease_server_error",
            "disease_analysis_failed",
            "disease_result_empty",
            "symptoms_unavailable",
        )
        for key in message_keys:
            messages = {
                language: localized_message(language, key)
                for language in LANGUAGE_NAMES
            }
            self.assertTrue(all(message.strip() for message in messages.values()), key)
            self.assertEqual(len(set(messages.values())), 4, key)

    def diagnosis(self):
        return {
            "ok": True,
            "is_valid_plant_image": True,
            "crop": "Tomato",
            "disease": "Early blight",
            "crop_display": "",
            "disease_display": "",
            "severity": "Moderate",
            "symptoms": ["Dark lesions"],
            "possible_causes": ["Fungal infection"],
            "recommended_management": ["Remove affected leaves"],
            "prevention": ["Rotate crops"],
            "safety_warnings": ["Wear protective equipment as stated on the product label."],
            "diagnostic_note": "",
        }

    async def test_incomplete_translation_preserves_successful_diagnosis(self):
        translated_response = {
            "crop_display": "टोमॅटो",
            "disease_display": "अर्ली ब्लाइट (Early blight)",
            "symptoms": ["पानांवरील काळे डाग"],
        }
        with patch.object(
            ai_service,
            "call_ai_model",
            new=AsyncMock(return_value=json.dumps(translated_response, ensure_ascii=False)),
        ):
            result = await ai_service._translate_model_diagnosis(self.diagnosis(), "mr")

        self.assertTrue(result["ok"])
        self.assertEqual(result["crop"], "Tomato")
        self.assertEqual(result["disease"], "Early blight")
        self.assertFalse(result["_translation_complete"])
        self.assertEqual(result["crop_display"], "Tomato")
        self.assertEqual(result["disease_display"], "Early blight")
        self.assertEqual(result["symptoms"], ["Dark lesions"])
        self.assertEqual(result["recommended_management"], ["Remove affected leaves"])
        self.assertIn("symptoms", result["_untranslated_fields"])

    async def test_complete_diagnosis_translation_preserves_prediction_for_each_supported_locale(self):
        translations = {
            "mr": {
                "crop_display": "टोमॅटो",
                "disease_display": "अर्ली ब्लाइट (Early blight)",
                "severity": "मध्यम",
                "symptoms": ["पानांवरील काळे डाग"],
                "possible_causes": ["बुरशीचा संसर्ग"],
                "recommended_management": ["बाधित पाने काढा"],
                "prevention": ["पीक फेरपालट करा"],
                "safety_warnings": ["उत्पादनाच्या लेबलवरील सूचनेनुसार संरक्षण साधने वापरा."],
                "diagnostic_note": "कृषी तज्ज्ञांकडून पुष्टी करा.",
            },
            "hi": {
                "crop_display": "टमाटर",
                "disease_display": "अर्ली ब्लाइट (Early blight)",
                "severity": "मध्यम",
                "symptoms": ["पत्तियों पर काले धब्बे"],
                "possible_causes": ["फफूंद संक्रमण"],
                "recommended_management": ["प्रभावित पत्तियां हटाएं"],
                "prevention": ["फसल चक्र अपनाएं"],
                "safety_warnings": ["उत्पाद के लेबल के निर्देशानुसार सुरक्षा उपकरण पहनें।"],
                "diagnostic_note": "कृषि विशेषज्ञ से पुष्टि करें।",
            },
            "ml": {
                "crop_display": "തക്കാളി",
                "disease_display": "ആദ്യകാല ഇലപ്പുള്ളി (Early blight)",
                "severity": "മിതമായത്",
                "symptoms": ["ഇലകളിൽ കറുത്ത പാടുകൾ"],
                "possible_causes": ["ഫംഗസ് അണുബാധ"],
                "recommended_management": ["ബാധിച്ച ഇലകൾ നീക്കം ചെയ്യുക"],
                "prevention": ["വിളമാറ്റം നടത്തുക"],
                "safety_warnings": ["ഉൽപ്പന്ന ലേബലിലെ നിർദ്ദേശപ്രകാരം സംരക്ഷണ ഉപകരണങ്ങൾ ധരിക്കുക."],
                "diagnostic_note": "കാർഷിക വിദഗ്ധനോട് സ്ഥിരീകരിക്കുക.",
            },
        }
        for language, translation in translations.items():
            with self.subTest(language=language):
                diagnosis = {**self.diagnosis(), "confidence": 91.0, "crop_confidence": 95.0}
                with patch.object(
                    ai_service,
                    "call_ai_model",
                    new=AsyncMock(return_value=json.dumps(translation, ensure_ascii=False)),
                ):
                    result = await ai_service._translate_model_diagnosis(diagnosis, language)

                self.assertTrue(result["_translation_complete"], language)
                self.assertEqual(result["crop"], "Tomato")
                self.assertEqual(result["disease"], "Early blight")
                self.assertEqual(result["confidence"], 91.0)
                self.assertEqual(result["crop_confidence"], 95.0)
                for field, value in translation.items():
                    self.assertEqual(result[field], value, f"{language}.{field}")

    async def test_translation_failure_preserves_original_diagnosis_without_english_success_fallback(self):
        with patch.object(
            ai_service,
            "call_ai_model",
            new=AsyncMock(side_effect=RuntimeError("translation unavailable")),
        ):
            result = await ai_service._translate_model_diagnosis(self.diagnosis(), "mr")

        self.assertTrue(result["ok"])
        self.assertFalse(result["_translation_complete"])
        self.assertEqual(result["crop_display"], "Tomato")
        self.assertEqual(result["disease_display"], "Early blight")
        self.assertEqual(result["symptoms"], ["Dark lesions"])
        self.assertTrue(result["translation_notice"])

    async def test_malformed_translation_json_preserves_original_diagnosis(self):
        original = self.diagnosis()
        with patch.object(
            ai_service,
            "call_ai_model",
            new=AsyncMock(return_value='{"crop_display": "टोमॅटो", "symptoms": ['),
        ):
            translated = await ai_service._translate_model_diagnosis(original, "mr")

        self.assertFalse(translated["_translation_complete"])
        self.assertEqual(translated["crop"], original["crop"])
        self.assertEqual(translated["disease"], original["disease"])
        self.assertEqual(translated["symptoms"], original["symptoms"])
        self.assertEqual(original["symptoms"], ["Dark lesions"])

    async def test_untranslated_english_diagnosis_fields_are_not_reported_as_success(self):
        original = self.diagnosis()
        translated_response = {
            "crop_display": "टमाटर",
            "disease_display": "अर्ली ब्लाइट (Early blight)",
            "severity": "मध्यम",
            "symptoms": ["Dark lesions"],
            "possible_causes": ["फफूंद संक्रमण"],
            "recommended_management": ["प्रभावित पत्तियां हटाएं"],
            "prevention": ["फसल चक्र अपनाएं"],
            "safety_warnings": ["उत्पाद के लेबल के निर्देशानुसार सुरक्षा उपकरण पहनें।"],
            "diagnostic_note": "कृषि विशेषज्ञ से पुष्टि करें।",
        }
        with patch.object(
            ai_service,
            "call_ai_model",
            new=AsyncMock(
                return_value=json.dumps(translated_response, ensure_ascii=False)
            ),
        ):
            result = await ai_service._translate_model_diagnosis(original, "hi")

        self.assertFalse(result["_translation_complete"])
        self.assertEqual(result["symptoms"], original["symptoms"])

    async def test_model_translation_surfaces_quota_exhaustion_after_all_providers_fail(self):
        with (
            patch.object(ai_service.settings, "GROQ_API_KEY", ""),
            patch.object(ai_service, "_get_gemini_api_key", return_value="configured"),
            patch.object(ai_service.settings, "OPENAI_API_KEY", "configured"),
            patch.object(
                ai_service,
                "call_gemini",
                new=AsyncMock(side_effect=ai_service.AIProviderUnavailable("quota_exceeded")),
            ),
            patch.object(
                ai_service,
                "call_openai",
                new=AsyncMock(side_effect=ai_service.AIProviderUnavailable("openai_quota_exceeded")),
            ),
        ):
            with self.assertRaises(ai_service.AIProviderUnavailable) as caught:
                await ai_service.call_ai_model(
                    "translate diagnosis",
                    "translator",
                    raise_on_failure=True,
                    use_groq=True,
                )

        self.assertEqual(caught.exception.reason, "quota_exceeded")

    async def test_model_translation_prefers_configured_groq_before_fallback_providers(self):
        with (
            patch.object(ai_service.settings, "GROQ_API_KEY", "configured"),
            patch.object(ai_service, "_get_gemini_api_key", return_value="configured"),
            patch.object(ai_service.settings, "OPENAI_API_KEY", "configured"),
            patch.object(
                ai_service,
                "call_groq",
                new=AsyncMock(return_value='{"translated": true}'),
            ) as groq,
            patch.object(
                ai_service, "call_gemini", new=AsyncMock(return_value=None)
            ) as gemini,
            patch.object(
                ai_service, "call_openai", new=AsyncMock(return_value=None)
            ) as openai,
        ):
            result = await ai_service.call_ai_model(
                "translate diagnosis",
                "translator",
                raise_on_failure=True,
                use_groq=True,
            )

        self.assertEqual(result, '{"translated": true}')
        gemini.assert_not_awaited()
        openai.assert_not_awaited()
        groq.assert_awaited_once_with(
            "translate diagnosis", "translator", temperature=0.7, max_tokens=1024
        )

    async def test_model_translation_falls_back_to_gemini_when_groq_fails(self):
        with (
            patch.object(ai_service.settings, "GROQ_API_KEY", "configured"),
            patch.object(ai_service, "_get_gemini_api_key", return_value="configured"),
            patch.object(ai_service.settings, "OPENAI_API_KEY", "configured"),
            patch.object(
                ai_service,
                "call_groq",
                new=AsyncMock(
                    side_effect=ai_service.AIProviderUnavailable("groq_rate_limited")
                ),
            ) as groq,
            patch.object(
                ai_service, "call_gemini", new=AsyncMock(return_value="Gemini result")
            ) as gemini,
            patch.object(ai_service, "call_openai", new=AsyncMock()) as openai,
        ):
            result = await ai_service.call_ai_model(
                "translate diagnosis",
                "translator",
                raise_on_failure=True,
                use_groq=True,
            )

        self.assertEqual(result, "Gemini result")
        groq.assert_awaited_once()
        gemini.assert_awaited_once()
        openai.assert_not_awaited()

    async def test_quota_failure_from_every_configured_provider_is_reported_as_quota(self):
        with (
            patch.object(ai_service.settings, "GROQ_API_KEY", "configured"),
            patch.object(ai_service, "_get_gemini_api_key", return_value="configured"),
            patch.object(ai_service.settings, "OPENAI_API_KEY", "configured"),
            patch.object(
                ai_service,
                "call_groq",
                new=AsyncMock(
                    side_effect=ai_service.AIProviderUnavailable("groq_quota_exceeded")
                ),
            ),
            patch.object(
                ai_service,
                "call_gemini",
                new=AsyncMock(side_effect=ai_service.AIProviderUnavailable("quota_exceeded")),
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
                await ai_service.call_ai_model(
                    "translate diagnosis",
                    "translator",
                    raise_on_failure=True,
                    use_groq=True,
                )

        self.assertEqual(caught.exception.reason, "quota_exceeded")

    async def test_translation_endpoint_uses_groq_for_all_four_languages(self):
        translations = {
            "en": {
                "crop_display": "Tomato",
                "disease_display": "Early blight",
                "severity": "Moderate",
                "symptoms": ["Dark lesions"],
                "possible_causes": ["Fungal infection"],
                "recommended_management": ["Remove affected leaves"],
                "prevention": ["Rotate crops"],
                "safety_warnings": ["Wear protective equipment as stated on the product label."],
                "diagnostic_note": "Confirm with an agricultural expert.",
            },
            "mr": {
                "crop_display": "टोमॅटो",
                "disease_display": "अर्ली ब्लाइट (Early blight)",
                "severity": "मध्यम",
                "symptoms": ["पानांवरील काळे डाग"],
                "possible_causes": ["बुरशीचा संसर्ग"],
                "recommended_management": ["बाधित पाने काढा"],
                "prevention": ["पीक फेरपालट करा"],
                "safety_warnings": ["उत्पादनाच्या लेबलवरील सूचनेनुसार संरक्षण साधने वापरा."],
                "diagnostic_note": "कृषी तज्ज्ञांकडून पुष्टी करा.",
            },
            "hi": {
                "crop_display": "टमाटर",
                "disease_display": "अर्ली ब्लाइट (Early blight)",
                "severity": "मध्यम",
                "symptoms": ["पत्तियों पर काले धब्बे"],
                "possible_causes": ["फफूंद संक्रमण"],
                "recommended_management": ["प्रभावित पत्तियां हटाएं"],
                "prevention": ["फसल चक्र अपनाएं"],
                "safety_warnings": ["उत्पाद के लेबल के निर्देशानुसार सुरक्षा उपकरण पहनें।"],
                "diagnostic_note": "कृषि विशेषज्ञ से पुष्टि करें।",
            },
            "ml": {
                "crop_display": "തക്കാളി",
                "disease_display": "ആദ്യകാല ഇലപ്പുള്ളി (Early blight)",
                "severity": "മിതമായത്",
                "symptoms": ["ഇലകളിൽ കറുത്ത പാടുകൾ"],
                "possible_causes": ["ഫംഗസ് അണുബാധ"],
                "recommended_management": ["ബാധിച്ച ഇലകൾ നീക്കം ചെയ്യുക"],
                "prevention": ["വിളമാറ്റം നടത്തുക"],
                "safety_warnings": ["ഉൽപ്പന്ന ലേബലിലെ നിർദ്ദേശപ്രകാരം സംരക്ഷണ ഉപകരണങ്ങൾ ധരിക്കുക."],
                "diagnostic_note": "കാർഷിക വിദഗ്ധനോട് സ്ഥിരീകരിക്കുക.",
            },
        }

        async def groq_translation(
            prompt, _system_prompt, *, temperature=0.7, max_tokens=1024
        ):
            for language, name in LANGUAGE_NAMES.items():
                if f"into {name}" in prompt:
                    return json.dumps(translations[language], ensure_ascii=False)
            self.fail("Translation prompt did not identify one of the supported languages")

        with (
            patch.object(ai_service.settings, "GROQ_API_KEY", "configured"),
            patch.object(ai_service, "_get_gemini_api_key", return_value=""),
            patch.object(ai_service.settings, "OPENAI_API_KEY", ""),
            patch.object(ai_service, "call_groq", new=AsyncMock(side_effect=groq_translation)),
        ):
            for language in ("en", "mr", "hi", "ml"):
                with self.subTest(language=language):
                    response = await disease_route.translate_disease_result(
                        disease_route.DiseaseTranslationRequest(result=self.diagnosis()),
                        language,
                    )
                    self.assertEqual(response["success"], True)
                    if language == "en":
                        self.assertEqual(response["result"]["crop_display"], "Tomato")
                        self.assertEqual(response["result"]["disease_display"], "Early blight")
                        continue
                    for field, value in translations[language].items():
                        self.assertEqual(response["result"][field], value)

    async def test_translation_rejects_unsupported_language_codes(self):
        with self.assertRaises(ValueError):
            await ai_service._translate_model_diagnosis(self.diagnosis(), "kn")

    async def test_supported_confident_local_result_skips_external_vision_for_all_languages(self):
        with (
            patch.object(
                ai_service,
                "predict_disease",
                return_value={
                    "class_name": "Tomato___Early_blight",
                    "confidence": 91.0,
                    "mock_predictor": False,
                    "_timing_ms": {"inference_ms": 12.0},
                },
            ),
            patch.object(
                ai_service,
                "analyze_prediction",
                return_value={
                    "ok": True,
                    "uncertain": False,
                    "crop": "Tomato",
                    "disease": "Early blight",
                    "raw_class": "Tomato___Early_blight",
                    "crop_confidence": 95.0,
                    "disease_confidence": 91.0,
                    "is_healthy": False,
                },
            ),
            patch.object(ai_service, "call_gemini_vision", new=AsyncMock()) as gemini_vision,
        ):
            for language in ("en", "mr", "hi", "ml"):
                result = await ai_service.detect_crop_disease(
                    b"leaf-image-bytes",
                    language=language,
                    content_type="image/jpeg",
                )

                self.assertTrue(result["ok"], language)
                self.assertEqual(result["crop"], "Tomato")
                self.assertEqual(result["raw_class"], "Tomato___Early_blight")
                self.assertEqual(result["confidence"], 91)
                self.assertTrue(result["preliminary"])
                self.assertIn("not a confirmed diagnosis", result["diagnostic_note"])
                self.assertIn("local_disease_knowledge_base", result["_analysis_source"])
                self.assertEqual(result["_timing_ms"]["external_ai_ms"], 0.0)

            gemini_vision.assert_not_awaited()

    async def test_uncertain_local_prediction_returns_caution_without_calling_provider(self):
        with (
            patch.object(
                ai_service,
                "predict_disease",
                return_value={
                    "class_name": "Tomato___Early_blight",
                    "confidence": 61.0,
                    "mock_predictor": False,
                },
            ),
            patch.object(
                ai_service,
                "analyze_prediction",
                return_value={
                    "ok": True,
                    "uncertain": True,
                    "crop": "Tomato",
                    "disease": "Early blight",
                    "raw_class": "Tomato___Early_blight",
                    "crop_confidence": 80.0,
                    "disease_confidence": 61.0,
                },
            ),
            patch.object(ai_service, "call_gemini_vision", new=AsyncMock()) as gemini_vision,
        ):
            result = await ai_service.detect_crop_disease(b"leaf-image-bytes")

        self.assertTrue(result["ok"])
        self.assertTrue(result["uncertain"])
        self.assertIsNone(result["confidence"])
        self.assertIn("too low", result["diagnostic_note"])
        gemini_vision.assert_not_awaited()

    async def test_rejected_local_prediction_returns_uncertainty_without_provider_timeout(self):
        with (
            patch.object(
                ai_service,
                "predict_disease",
                return_value={
                    "class_name": "Tomato___Late_blight",
                    "confidence": 47.0,
                    "mock_predictor": False,
                },
            ),
            patch.object(
                ai_service,
                "analyze_prediction",
                return_value={
                    "ok": False,
                    "error_type": "low_crop_conf",
                    "crop": "Tomato",
                    "crop_confidence": 54.0,
                },
            ),
            patch.object(ai_service, "call_gemini_vision", new=AsyncMock()) as gemini_vision,
        ):
            result = await ai_service.detect_crop_disease(b"uncertain-image")

        self.assertTrue(result["ok"])
        self.assertTrue(result["uncertain"])
        self.assertIsNone(result["confidence"])
        self.assertIn("could not confidently identify", result["diagnostic_note"])
        self.assertEqual(result["_timing_ms"]["external_ai_ms"], 0.0)
        gemini_vision.assert_not_awaited()

    async def test_disease_result_can_be_translated_without_running_image_model(self):
        result = self.diagnosis()
        translated = {
            **result,
            "crop_display": "തക്കാളി",
            "disease_display": "ആദ്യകാല ഇലപ്പുള്ളി (Early blight)",
            "severity": "മിതമായത്",
            "symptoms": ["ഇലകളിൽ കറുത്ത പാടുകൾ"],
            "possible_causes": ["ഫംഗസ് അണുബാധ"],
            "recommended_management": ["ബാധിച്ച ഇലകൾ നീക്കം ചെയ്യുക"],
            "prevention": ["വിളമാറ്റം നടത്തുക"],
            "diagnostic_note": "ഈ ഫലം കാർഷിക വിദഗ്ധൻ സ്ഥിരീകരിക്കണം.",
            "_translation_complete": True,
        }
        request = disease_route.DiseaseTranslationRequest(result=result)
        with (
            patch.object(
                disease_route,
                "_translate_model_diagnosis",
                new=AsyncMock(return_value=translated),
            ) as translate_result,
            patch.object(disease_route, "predict_disease") as model_prediction,
        ):
            response = await disease_route.translate_disease_result(request, "ml")

        translate_result.assert_awaited_once()
        model_prediction.assert_not_called()
        self.assertEqual(translate_result.await_args.args[0]["crop"], "Tomato")
        self.assertEqual(translate_result.await_args.args[1], "ml")
        self.assertTrue(response["success"])
        self.assertEqual(response["result"]["disease_display"], "ആദ്യകാല ഇലപ്പുള്ളി (Early blight)")
        self.assertNotIn("_translation_complete", response["result"])

    async def test_quota_failure_returns_localized_partial_diagnosis(self):
        request = disease_route.DiseaseTranslationRequest(result=self.diagnosis())
        with patch.object(
            disease_route,
            "_translate_model_diagnosis",
            new=AsyncMock(side_effect=ai_service.AIProviderUnavailable("quota_exceeded")),
        ):
            response = await disease_route.translate_disease_result(request, "ml")

        self.assertTrue(response["success"])
        self.assertFalse(response["result"]["translation_complete"])
        self.assertEqual(response["result"]["disease"], "Early blight")
        self.assertEqual(response["result"]["symptoms"], ["Dark lesions"])
        self.assertIn("symptoms", response["result"]["untranslated_fields"])
        self.assertTrue(response["result"]["translation_notice"])

    async def test_malformed_diagnosis_translation_returns_incomplete_original_result(self):
        request = disease_route.DiseaseTranslationRequest(result=self.diagnosis())
        with patch.object(
            disease_route,
            "_translate_model_diagnosis",
            new=AsyncMock(
                return_value={
                    **self.diagnosis(),
                    "_translation_complete": False,
                }
            ),
        ):
            response = await disease_route.translate_disease_result(request, "hi")

        self.assertTrue(response["success"])
        self.assertFalse(response["result"]["translation_complete"])
        self.assertIn("symptoms", response["result"]["untranslated_fields"])
        self.assertEqual(response["result"]["disease"], "Early blight")

    async def test_http_translation_route_uses_shared_local_fallback_after_provider_quotas(self):
        knowledge = lookup_disease_knowledge("Corn (Maize)", "corn_rust")
        self.assertIsNotNone(knowledge)
        result = {
            "crop": knowledge["crop"],
            "disease": knowledge["disease"],
            "disease_key": "corn_rust",
            "severity": knowledge["severity"],
            "symptoms": knowledge["symptoms"],
            "possible_causes": knowledge["causes"],
            "recommended_management": knowledge["treatment"],
            "prevention": knowledge["prevention"],
            "safety_warnings": ["Wear protective equipment as stated on the product label."],
            "confidence": 91.0,
            "crop_confidence": 95.0,
            "is_valid_plant_image": True,
        }
        app = FastAPI()
        app.include_router(disease_route.router, prefix="/api/disease")

        with (
            patch.object(ai_service.settings, "GROQ_API_KEY", "configured"),
            patch.object(ai_service, "_get_gemini_api_key", return_value="configured"),
            patch.object(ai_service.settings, "OPENAI_API_KEY", "configured"),
            patch.object(
                ai_service,
                "call_gemini",
                new=AsyncMock(side_effect=ai_service.AIProviderUnavailable("quota_exceeded")),
            ) as gemini,
            patch.object(
                ai_service,
                "call_openai",
                new=AsyncMock(side_effect=ai_service.AIProviderUnavailable("openai_quota_exceeded")),
            ) as openai,
            patch.object(
                ai_service,
                "call_groq",
                new=AsyncMock(side_effect=ai_service.AIProviderUnavailable("groq_quota_exceeded")),
            ) as groq,
        ):
            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app=app),
                base_url="http://testserver",
            ) as client:
                for language in ("en", "mr", "hi", "ml"):
                    with self.subTest(language=language):
                        response = await client.post(
                            "/api/disease/translate",
                            headers={"X-Language": language},
                            json={"result": result},
                        )
                        self.assertEqual(response.status_code, 200)
                        body = response.json()
                        self.assertTrue(body["success"])
                        translated = body["result"]
                        dictionary_entry = DISEASE_RESULT_TRANSLATIONS[language]
                        self.assertEqual(translated["crop_display"], dictionary_entry["crop"])
                        self.assertEqual(translated["disease_display"], dictionary_entry["disease"])
                        self.assertEqual(translated["symptoms"], dictionary_entry["symptoms"])
                        self.assertEqual(translated["possible_causes"], dictionary_entry["causes"])
                        self.assertEqual(translated["recommended_management"], dictionary_entry["treatment"])
                        self.assertEqual(translated["prevention"], dictionary_entry["prevention"])
                        self.assertEqual(translated["confidence"], 91.0)
                        self.assertEqual(translated["crop_confidence"], 95.0)
                        if language == "en":
                            self.assertTrue(translated["translation_complete"])
                            gemini.assert_not_awaited()
                            openai.assert_not_awaited()
                            groq.assert_not_awaited()
                        else:
                            self.assertFalse(translated["translation_complete"])
                            self.assertEqual(
                                translated["severity"],
                                DISEASE_RESULT_TRANSLATIONS[language]["severityLabels"]["Moderate to Severe"],
                            )
                            self.assertEqual(translated["severity_original"], "Moderate to Severe")
                            self.assertIn("safety_warnings", translated["untranslated_fields"])
                            self.assertTrue(translated["translation_notice"])
                            gemini.assert_awaited_once()
                            openai.assert_awaited_once()
                            groq.assert_awaited_once()
                            gemini.reset_mock()
                            openai.reset_mock()
                            groq.reset_mock()

    async def test_gray_leaf_spot_http_route_uses_complete_local_translation_before_provider(self):
        app = FastAPI()
        app.include_router(disease_route.router, prefix="/api/disease")
        result = self.gray_leaf_spot_diagnosis()
        result["diagnostic_note"] = (
            "The visual analysis agrees with the local classifier's supported crop/disease class. "
            "Confidence values are model scores, not calibrated probabilities. Chemical instructions "
            "are omitted unless verified against current local product labels. This is a preliminary "
            "image-model result, not a confirmed diagnosis. Model scores are not calibrated "
            "probabilities; ask an agricultural expert to confirm, especially before taking treatment "
            "action."
        )
        with (
            patch.object(
                ai_service,
                "call_ai_model",
                new=AsyncMock(
                    side_effect=ai_service.AIProviderUnavailable("openai_quota_exceeded")
                ),
            ) as provider_call,
            patch.object(
                disease_route,
                "localize_disease_result",
                wraps=localize_disease_result,
            ) as local_fallback,
        ):
            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app=app),
                base_url="http://testserver",
            ) as client:
                for language in ("en", "mr", "hi", "ml"):
                    response = await client.post(
                        "/api/disease/translate",
                        headers={"X-Language": language},
                        json={"result": result},
                    )

                    self.assertEqual(response.status_code, 200)
                    translated = response.json()["result"]
                    expected = DISEASE_RESULT_TRANSLATIONS[language]["grayLeafSpot"]
                    self.assertTrue(translated["translation_complete"])
                    self.assertEqual(translated["crop_display"], expected["crop"])
                    self.assertEqual(translated["disease_display"], expected["disease"])
                    self.assertEqual(translated["severity"], expected["severity"])
                    self.assertEqual(translated["symptoms"], expected["symptoms"])
                    self.assertEqual(translated["possible_causes"], expected["causes"])
                    self.assertEqual(translated["recommended_management"], expected["treatment"])
                    self.assertEqual(translated["prevention"], expected["prevention"])
                    self.assertEqual(
                        translated["diagnostic_note"],
                        DISEASE_RESULT_TRANSLATIONS[language]["diagnosticDisclaimer"],
                    )
                    self.assertEqual(translated["safety_warnings"], [expected["safetyWarning"]])
                    self.assertEqual(translated["confidence"], 96.0)
                    self.assertEqual(translated["crop_confidence"], 99.0)

        provider_call.assert_not_awaited()
        self.assertEqual(local_fallback.call_count, 4)

    async def test_http_translation_route_timeout_returns_partial_for_unmapped_disease(self):
        app = FastAPI()
        app.include_router(disease_route.router, prefix="/api/disease")
        with patch.object(
            ai_service,
            "call_ai_model",
            new=AsyncMock(side_effect=asyncio.TimeoutError()),
        ) as provider_call:
            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app=app),
                base_url="http://testserver",
            ) as client:
                response = await client.post(
                    "/api/disease/translate",
                    headers={"X-Language": "mr"},
                    json={"result": self.diagnosis()},
                )

        self.assertEqual(response.status_code, 200)
        translated = response.json()["result"]
        self.assertFalse(translated["translation_complete"])
        self.assertIn("symptoms", translated["untranslated_fields"])
        self.assertIn("लक्षणे", translated["translation_notice"])
        self.assertEqual(translated["symptoms"], ["Dark lesions"])
        provider_call.assert_awaited_once()

    async def test_http_translation_route_returns_original_diagnosis_if_translation_service_returns_none(self):
        app = FastAPI()
        app.include_router(disease_route.router, prefix="/api/disease")
        with patch.object(
            disease_route,
            "_translate_model_diagnosis",
            new=AsyncMock(return_value=None),
        ):
            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app=app),
                base_url="http://testserver",
            ) as client:
                response = await client.post(
                    "/api/disease/translate",
                    headers={"X-Language": "hi"},
                    json={"result": self.diagnosis()},
                )

        self.assertEqual(response.status_code, 200)
        translated = response.json()["result"]
        self.assertFalse(translated["translation_complete"])
        self.assertEqual(translated["disease"], "Early blight")
        self.assertTrue(translated["translation_notice"])

    async def test_http_translation_route_returns_503_only_without_a_usable_fallback(self):
        app = FastAPI()
        app.include_router(disease_route.router, prefix="/api/disease")
        with (
            patch.object(
                disease_route,
                "_translate_model_diagnosis",
                new=AsyncMock(return_value=None),
            ),
            patch.object(disease_route, "localize_disease_result", return_value=None),
        ):
            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app=app),
                base_url="http://testserver",
            ) as client:
                response = await client.post(
                    "/api/disease/translate",
                    headers={"X-Language": "hi"},
                    json={"result": self.diagnosis()},
                )

        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json()["code"], "translation_unavailable")
        self.assertNotIn("result", response.json())

    async def test_gemini_is_called_when_local_model_is_unavailable(self):
        response = json.dumps({
            "is_valid_plant_image": False,
            "crop": "",
            "disease": "",
            "diagnostic_note": "No plant is visible.",
        })
        with (
            patch.object(
                ai_service,
                "predict_disease",
                return_value={
                    "error_type": "model_unavailable",
                    "error_message": "TensorFlow failed to load.",
                    "mock_predictor": True,
                },
            ),
            patch.object(
                ai_service,
                "analyze_prediction",
                return_value={
                    "ok": False,
                    "error_type": "model_unavailable",
                    "error_message": "TensorFlow failed to load.",
                },
            ),
            patch.object(
                ai_service,
                "call_gemini_vision",
                new=AsyncMock(return_value=response),
            ) as gemini_vision,
        ):
            result = await ai_service.detect_crop_disease(b"image-bytes")

        self.assertTrue(result["ok"])
        self.assertFalse(result["is_valid_plant_image"])
        gemini_vision.assert_awaited_once()

    async def test_gemini_quota_failure_preserves_local_model_unavailable_status(self):
        with (
            patch.object(
                ai_service,
                "predict_disease",
                return_value={
                    "error_type": "model_unavailable",
                    "error_message": "TensorFlow failed to load.",
                    "mock_predictor": True,
                },
            ),
            patch.object(
                ai_service,
                "analyze_prediction",
                return_value={
                    "ok": False,
                    "error_type": "model_unavailable",
                    "error_message": "TensorFlow failed to load.",
                },
            ),
            patch.object(
                ai_service,
                "call_gemini_vision",
                new=AsyncMock(
                    side_effect=ai_service.GeminiVisionUnavailable(
                        "gemini_quota_exceeded",
                        "Gemini quota exhausted.",
                    )
                ),
            ),
        ):
            result = await ai_service.detect_crop_disease(b"image-bytes")

        self.assertFalse(result["ok"])
        self.assertEqual(result["error_type"], "gemini_quota_exceeded")
        self.assertEqual(result["_local_model_status"], "unavailable")

    async def test_local_supported_result_does_not_depend_on_gemini_availability(self):
        with (
            patch.object(
                ai_service,
                "predict_disease",
                return_value={
                    "class_name": "Tomato___Early_blight",
                    "confidence": 91.0,
                    "mock_predictor": False,
                },
            ),
            patch.object(
                ai_service,
                "analyze_prediction",
                return_value={
                    "ok": True,
                    "uncertain": False,
                    "crop": "Tomato",
                    "disease": "Early blight",
                    "raw_class": "Tomato___Early_blight",
                    "crop_confidence": 95.0,
                    "disease_confidence": 91.0,
                    "is_healthy": False,
                },
            ),
            patch.object(
                ai_service,
                "call_gemini_vision",
                new=AsyncMock(
                    side_effect=ai_service.GeminiVisionUnavailable(
                        "gemini_provider_unavailable",
                        "Gemini is unavailable.",
                    )
                ),
            ) as gemini_vision,
        ):
            result = await ai_service.detect_crop_disease(
                b"image-bytes",
                content_type="image/jpeg",
            )

        self.assertTrue(result["ok"])
        self.assertEqual(result["disease"], "Early Blight (Tomato)")
        self.assertEqual(result["confidence"], 91)
        gemini_vision.assert_not_awaited()

    async def test_visual_analysis_prompt_uses_requested_language_without_changing_image_payload(self):
        requests = []

        async def fake_vision_call(image_bytes, content_type, text_message, system_prompt):
            requests.append((image_bytes, content_type, text_message, system_prompt))
            return json.dumps(
                {
                    "is_valid_plant_image": False,
                    "crop": "",
                    "disease": "",
                    "diagnostic_note": "No plant is visible.",
                }
            )

        with (
            patch.object(
                ai_service,
                "predict_disease",
                side_effect=RuntimeError("optional classifier unavailable"),
            ),
            patch.object(ai_service, "call_gemini_vision", new=AsyncMock(side_effect=fake_vision_call)),
        ):
            for language in ("en", "mr", "hi", "ml"):
                await ai_service.analyze_plant_image_gemini_primary(
                    image_bytes=b"same-image",
                    content_type="image/jpeg",
                    response_language=language,
                )

        self.assertEqual(len(requests), 4)
        self.assertEqual({request[0] for request in requests}, {b"same-image"})
        prompts = [request[2] for request in requests]
        self.assertEqual(len(set(prompts)), 4)
        self.assertIn("Write user-facing text in English", prompts[0])
        self.assertIn("Marathi (मराठी)", prompts[1])
        self.assertIn("Hindi (हिंदी)", prompts[2])
        self.assertIn("Malayalam (മലയാളം)", prompts[3])
        self.assertTrue(all("Keep crop and disease identifiers canonical" in prompt for prompt in prompts))

    async def test_backend_detection_errors_use_requested_language(self):
        for language in ("en", "mr", "hi", "ml"):
            image = UploadFile(
                file=io.BytesIO(b"image-bytes"),
                filename="leaf.jpg",
                headers=Headers({"content-type": "image/jpeg"}),
            )
            with (
                patch.object(
                    disease_route,
                    "assess_image_quality",
                    return_value={"ok": True, "format": "JPEG", "width": 100, "height": 100},
                ),
                patch.object(
                    disease_route,
                    "detect_crop_disease",
                    new=AsyncMock(
                        return_value={
                            "ok": False,
                            "error": "The crop is unsupported.",
                            "error_type": "unsupported_crop",
                        }
                    ),
                ) as detect,
            ):
                response = await disease_route.detect_disease(
                    image=image,
                    crop=None,
                    language=None,
                    x_language=language,
                    _current_user=None,
                )

            detect.assert_awaited_once_with(
                b"image-bytes",
                "",
                language,
                "image/jpeg",
            )
            body = json.loads(response.body)
            self.assertEqual(response.status_code, 422, language)
            self.assertEqual(body["error"], localized_message(language, "unsupported_crop"), language)

    async def test_gemini_timeout_is_reported_as_timeout_in_selected_language(self):
        for language in ("en", "mr", "hi", "ml"):
            image = UploadFile(
                file=io.BytesIO(b"image-bytes"),
                filename="leaf.jpg",
                headers=Headers({"content-type": "image/jpeg"}),
            )
            with (
                patch.object(
                    disease_route,
                    "assess_image_quality",
                    return_value={"ok": True, "format": "JPEG", "width": 100, "height": 100},
                ),
                patch.object(
                    disease_route,
                    "detect_crop_disease",
                    new=AsyncMock(
                        return_value={
                            "ok": False,
                            "error": "Gemini did not respond before the backend request timeout.",
                            "error_type": "gemini_timeout",
                        }
                    ),
                ),
            ):
                response = await disease_route.detect_disease(
                    image=image,
                    crop=None,
                    language=None,
                    x_language=language,
                    _current_user=None,
                )

            body = json.loads(response.body)
            self.assertEqual(response.status_code, 503, language)
            self.assertEqual(body["error"], localized_message(language, "ai_timeout"), language)

    async def test_gemini_quota_error_also_reports_unavailable_local_model(self):
        image = UploadFile(
            file=io.BytesIO(b"image-bytes"),
            filename="leaf.jpg",
            headers=Headers({"content-type": "image/jpeg"}),
        )
        with (
            patch.object(
                disease_route,
                "assess_image_quality",
                return_value={"ok": True, "format": "JPEG", "width": 100, "height": 100},
            ),
            patch.object(
                disease_route,
                "detect_crop_disease",
                new=AsyncMock(return_value={
                    "ok": False,
                    "error_type": "gemini_quota_exceeded",
                    "_local_model_status": "unavailable",
                    "_timing_ms": {},
                }),
            ),
        ):
            response = await disease_route.detect_disease(
                image=image,
                crop=None,
                language="en",
                x_language="en",
                _current_user=None,
            )

        body = json.loads(response.body)
        self.assertEqual(response.status_code, 503)
        self.assertEqual(body["error_type"], "gemini_quota_exceeded")
        self.assertEqual(body["local_model_status"], "unavailable")
        self.assertIn(localized_message("en", "disease_quota_error"), body["error"])
        self.assertIn(localized_message("en", "disease_model_unavailable"), body["error"])
