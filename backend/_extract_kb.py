from pathlib import Path

p = Path(__file__).resolve().parent / "routes" / "disease.py"
text = p.read_text(encoding="utf-8")
start = text.index("DISEASE_DB = {")
end = text.index("\n\n\ndef _get_current_user_optional")
db_src = text[start:end]
out = Path(__file__).resolve().parent / "services" / "disease_knowledge_base.py"
header = '''"""Curated crop-disease knowledge keyed to PlantVillage class labels.

Lookup MUST be exact crop + disease. Never reuse another crop's treatments.
"""
from typing import Any, Dict, List, Optional

from services.disease_model_service import normalize_crop_for_key

'''
footer = '''

def crop_matches_entry(db_entry: Dict[str, Any], detected_crop: str) -> bool:
    if not db_entry or not detected_crop:
        return False
    db_crop_raw = (db_entry.get("crop") or "").strip()
    if not db_crop_raw:
        return False
    detected_key = normalize_crop_for_key(detected_crop)
    if normalize_crop_for_key(db_crop_raw) == detected_key:
        return True
    if "/" in db_crop_raw:
        for part in [p.strip() for p in db_crop_raw.split("/")]:
            if normalize_crop_for_key(part) == detected_key:
                return True
    return False


def lookup_disease_knowledge(
    crop_display: str,
    disease_key: str,
    generic_disease_key: str = "",
) -> Optional[Dict[str, Any]]:
    """Return knowledge only when the entry belongs to the predicted crop."""
    if not crop_display:
        return None
    keys_to_try: List[str] = []
    if disease_key:
        keys_to_try.append(disease_key)
    crop_prefix = normalize_crop_for_key(crop_display) + "_"
    if generic_disease_key:
        keys_to_try.append(crop_prefix + generic_disease_key)

    seen = set()
    for key in keys_to_try:
        if not key or key in seen:
            continue
        seen.add(key)
        entry = DISEASE_DB.get(key)
        if entry and crop_matches_entry(entry, crop_display):
            return {**entry, "_db_key": key}

    # Exact crop-prefixed scan only. Never fall back to another crop or the
    # generic "healthy" key (that would attach the wrong crop's guidance).
    gk = (generic_disease_key or "").lower().replace(" ", "_")
    for key, entry in DISEASE_DB.items():
        if not key.startswith(crop_prefix):
            continue
        if not crop_matches_entry(entry, crop_display):
            continue
        tail = key[len(crop_prefix):]
        if gk and (gk == tail or gk in tail or tail in gk):
            return {**entry, "_db_key": key}
        entry_disease = (entry.get("disease") or "").lower()
        if gk and gk.replace("_", " ") in entry_disease:
            return {**entry, "_db_key": key}
    return None
'''
out.write_text(header + db_src + footer, encoding="utf-8")
print("wrote", out)
print("chars", len(db_src))
