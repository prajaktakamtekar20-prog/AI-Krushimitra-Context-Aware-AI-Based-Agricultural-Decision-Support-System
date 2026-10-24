import json
from pathlib import Path
from typing import Any, Dict, List

from services.localization import LANGUAGE_NAMES, resolve_language


_TRANSLATION_FILE = (
    Path(__file__).resolve().parents[2]
    / "shared"
    / "disease_result_translations.json"
)
DISEASE_RESULT_TRANSLATIONS = json.loads(
    _TRANSLATION_FILE.read_text(encoding="utf-8")
)

if set(DISEASE_RESULT_TRANSLATIONS) != set(LANGUAGE_NAMES):
    raise ValueError("Disease result translations must cover the four supported languages")

_EXPECTED_TRANSLATION_FIELDS = {
    "crop",
    "disease",
    "symptoms",
    "causes",
    "treatment",
    "prevention",
    "diagnosticNote",
    "diagnosticDisclaimer",
    "partialNotice",
    "fieldLabels",
    "grayLeafSpot",
    "severityLabels",
}
_EXPECTED_SEVERITIES = {
    "Mild (None)",
    "Mild",
    "Mild to Moderate",
    "Moderate",
    "Moderate to Severe",
    "Severe",
}
_EXPECTED_FIELD_LABELS = {
    "crop_display",
    "disease_display",
    "severity",
    "symptoms",
    "possible_causes",
    "recommended_management",
    "prevention",
    "safety_warnings",
    "warnings",
    "precautions",
    "diagnostic_note",
    "error",
}
for _language, _translations in DISEASE_RESULT_TRANSLATIONS.items():
    if set(_translations) != _EXPECTED_TRANSLATION_FIELDS:
        raise ValueError(f"Inconsistent disease result translations for {_language}")
    if any(
        not isinstance(_translations.get(field), str)
        or not _translations[field].strip()
        for field in (
            "crop",
            "disease",
            "diagnosticNote",
            "diagnosticDisclaimer",
            "partialNotice",
        )
    ):
        raise ValueError(f"Empty disease result translation for {_language}")
    for field in ("symptoms", "causes", "treatment", "prevention"):
        values = _translations.get(field)
        if not isinstance(values, list) or not values or any(
            not isinstance(value, str) or not value.strip() for value in values
        ):
            raise ValueError(f"Empty {field} disease translation for {_language}")
    labels = _translations.get("fieldLabels")
    if (
        not isinstance(labels, dict)
        or set(labels) != _EXPECTED_FIELD_LABELS
        or any(not isinstance(value, str) or not value.strip() for value in labels.values())
    ):
        raise ValueError(f"Empty disease translation field labels for {_language}")
    severity_labels = _translations.get("severityLabels")
    if (
        not isinstance(severity_labels, dict)
        or set(severity_labels) != _EXPECTED_SEVERITIES
        or any(not isinstance(value, str) or not value.strip() for value in severity_labels.values())
    ):
        raise ValueError(f"Inconsistent disease severity translations for {_language}")
    gray_translation = _translations.get("grayLeafSpot")
    if (
        not isinstance(gray_translation, dict)
        or set(gray_translation)
        != {
            "crop", "disease", "severity", "symptoms", "causes", "treatment",
            "prevention", "diagnosticNote", "safetyWarning",
        }
    ):
        raise ValueError(f"Inconsistent Gray Leaf Spot translations for {_language}")
    if any(
        not isinstance(gray_translation.get(field), str)
        or not gray_translation[field].strip()
        for field in ("crop", "disease", "severity", "diagnosticNote", "safetyWarning")
    ):
        raise ValueError(f"Empty Gray Leaf Spot translation for {_language}")
    for field, count in (
        ("symptoms", 4),
        ("causes", 4),
        ("treatment", 4),
        ("prevention", 5),
    ):
        values = gray_translation.get(field)
        if (
            not isinstance(values, list)
            or len(values) != count
            or any(not isinstance(value, str) or not value.strip() for value in values)
        ):
            raise ValueError(f"Invalid Gray Leaf Spot {field} translation for {_language}")

_TRANSLATABLE_FIELDS = {
    "severity": "severity",
    "symptoms": "symptoms",
    "possible_causes": "possible_causes",
    "recommended_management": "recommended_management",
    "prevention": "prevention",
    "safety_warnings": "safety_warnings",
    "warnings": "warnings",
    "precautions": "precautions",
    "diagnostic_note": "diagnostic_note",
    "error": "error",
}
_LOCALIZED_KEYS = (
    "crop_display",
    "disease_display",
    "symptoms",
    "possible_causes",
    "recommended_management",
    "prevention",
    "diagnostic_note",
)


def _is_common_rust(result: Dict[str, Any]) -> bool:
    source = " ".join(
        str(result.get(key) or "")
        for key in ("disease_key", "disease", "disease_display", "crop")
    ).casefold()
    return any(
        marker in source
        for marker in ("corn_rust", "common rust", "puccinia sorghi")
    )


_GRAY_SAFETY_WARNING = (
    "Use only locally registered agrochemicals for this crop and problem; always read "
    "and follow the product label, local agricultural extension recommendations, and "
    "respect re-entry / pre-harvest intervals."
)


def _is_gray_leaf_spot(result: Dict[str, Any]) -> bool:
    source = " ".join(
        str(result.get(key) or "")
        for key in ("disease_key", "raw_class", "disease", "disease_display")
    ).casefold()
    return any(
        marker in source
        for marker in (
            "corn_leaf_spot",
            "gray_leaf_spot",
            "cercospora zeae-maydis",
            "gray leaf spot",
        )
    )


def _has_complete_diagnostic_disclaimer(note: Any) -> bool:
    if not isinstance(note, str):
        return False
    normalized = note.casefold()
    return all(
        marker in normalized
        for marker in (
            "visual analysis agrees with the local classifier",
            "confidence values are model scores",
            "chemical instructions are omitted unless verified",
            "preliminary image-model result, not a confirmed diagnosis",
            "agricultural expert to confirm",
        )
    )


def _untranslated_fields(
    result: Dict[str, Any],
    localized_fields: set[str],
) -> List[str]:
    fields: List[str] = []
    if result.get("crop") and "crop_display" not in localized_fields:
        fields.append("crop_display")
    if result.get("disease") and "disease_display" not in localized_fields:
        fields.append("disease_display")

    for field, label in _TRANSLATABLE_FIELDS.items():
        value = result.get(field)
        if value and field not in localized_fields and label not in fields:
            fields.append(label)

    if result.get("causes") and "possible_causes" not in localized_fields:
        if "possible_causes" not in fields:
            fields.append("possible_causes")
    if result.get("treatment") and "recommended_management" not in localized_fields:
        if "recommended_management" not in fields:
            fields.append("recommended_management")
    return fields


def localize_disease_result(
    result: Dict[str, Any],
    language: str,
) -> Dict[str, Any]:
    """Apply only the verified shared disease translations and mark missing fields."""
    language = resolve_language(language)
    translated_result = dict(result)
    localized_fields: set[str] = set()
    if _has_complete_diagnostic_disclaimer(result.get("diagnostic_note")):
        translated_result["diagnostic_note"] = DISEASE_RESULT_TRANSLATIONS[language][
            "diagnosticDisclaimer"
        ]
        localized_fields.add("diagnostic_note")

    severity = result.get("severity")
    if language != "en" and isinstance(severity, str):
        severity_translation = DISEASE_RESULT_TRANSLATIONS[language]["severityLabels"].get(
            severity.strip()
        )
        if severity_translation:
            translated_result["severity"] = severity_translation
            translated_result["severity_original"] = severity
            localized_fields.add("severity")

    if _is_common_rust(result):
        translation = DISEASE_RESULT_TRANSLATIONS[language]
        translated_result.update(
            {
                "crop_display": translation["crop"],
                "disease_display": translation["disease"],
                "symptoms": translation["symptoms"],
                "possible_causes": translation["causes"],
                "causes": translation["causes"],
                "recommended_management": translation["treatment"],
                "treatment": translation["treatment"],
                "prevention": translation["prevention"],
                "diagnostic_note": translation["diagnosticNote"],
            }
        )
        localized_fields.update(_LOCALIZED_KEYS)
        if result.get("causes"):
            localized_fields.add("causes")
        if result.get("treatment"):
            localized_fields.add("treatment")

    if _is_gray_leaf_spot(result):
        translation = DISEASE_RESULT_TRANSLATIONS[language]["grayLeafSpot"]
        translated_result.update(
            {
                "crop_display": translation["crop"],
                "disease_display": translation["disease"],
                "severity": translation["severity"],
                "severity_original": result.get("severity", translation["severity"]),
                "symptoms": translation["symptoms"],
                "possible_causes": translation["causes"],
                "causes": translation["causes"],
                "recommended_management": translation["treatment"],
                "treatment": translation["treatment"],
                "prevention": translation["prevention"],
            }
        )
        localized_fields.update(
            {
                "crop_display",
                "disease_display",
                "severity",
                "symptoms",
                "possible_causes",
                "recommended_management",
                "prevention",
            }
        )
        if result.get("causes"):
            localized_fields.add("causes")
        if result.get("treatment"):
            localized_fields.add("treatment")

        # Keep image-specific evidence intact unless it is the standard disclaimer.
        diagnostic_note = result.get("diagnostic_note")
        standard_note = (
            "This is a preliminary image-model result, not a confirmed diagnosis. "
            "Model scores are not calibrated probabilities; ask an agricultural expert "
            "to confirm, especially before taking treatment action."
        )
        if not diagnostic_note or diagnostic_note.strip() == standard_note:
            translated_result["diagnostic_note"] = translation["diagnosticNote"]
            localized_fields.add("diagnostic_note")

        safety_warnings = result.get("safety_warnings")
        if (
            isinstance(safety_warnings, list)
            and safety_warnings
            and all(
                isinstance(warning, str)
                and warning.strip().casefold() == _GRAY_SAFETY_WARNING.casefold()
                for warning in safety_warnings
            )
        ):
            translated_result["safety_warnings"] = [
                translation["safetyWarning"] for _ in safety_warnings
            ]
            localized_fields.add("safety_warnings")

    if language == "en":
        translated_result["crop_display"] = (
            translated_result.get("crop_display") or result.get("crop") or ""
        )
        translated_result["disease_display"] = (
            translated_result.get("disease_display") or result.get("disease") or ""
        )
        translated_result["_untranslated_fields"] = []
        translated_result["_translation_complete"] = True
        return translated_result

    untranslated = _untranslated_fields(result, localized_fields)
    translated_result["crop_display"] = (
        translated_result.get("crop_display") or result.get("crop") or ""
    )
    translated_result["disease_display"] = (
        translated_result.get("disease_display") or result.get("disease") or ""
    )
    translated_result["_untranslated_fields"] = untranslated
    translated_result["_translation_complete"] = not untranslated
    if untranslated:
        locale = DISEASE_RESULT_TRANSLATIONS[language]
        labels = locale["fieldLabels"]
        translated_labels = [
            labels.get(field, field) for field in dict.fromkeys(untranslated)
        ]
        translated_result["translation_notice"] = locale["partialNotice"].format(
            fields=", ".join(translated_labels)
        )
    else:
        translated_result.pop("translation_notice", None)

    if result.get("crop") is not None:
        translated_result["crop_original"] = result["crop"]
    if result.get("disease") is not None:
        translated_result["disease_original"] = result["disease"]
    return translated_result
