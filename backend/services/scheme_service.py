import json
import os
from copy import deepcopy
from typing import Any, Dict, List, Optional, Tuple

SCHEMES_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "government_schemes.json")

_SCHEMES: Optional[List[Dict[str, Any]]] = None

PRELIMINARY_DISCLAIMER = (
    "This match is preliminary and informational only. Government departments, banks, "
    "and implementing agencies make the final eligibility decision. Scheme windows, "
    "benefits, and documents change. Always confirm on the official portal before applying. "
    "Never enter Aadhaar OTP, net-banking password, or UPI PIN in this application."
)


def load_schemes() -> List[Dict[str, Any]]:
    global _SCHEMES
    if _SCHEMES is None:
        with open(SCHEMES_PATH, "r", encoding="utf-8") as f:
            _SCHEMES = json.load(f)
    return _SCHEMES


def get_scheme_by_id(scheme_id: str) -> Optional[Dict[str, Any]]:
    for s in load_schemes():
        if s.get("id") == scheme_id:
            return deepcopy(s)
    return None


def _norm(value: Any) -> str:
    return str(value or "").strip().lower()


def _acres(land_area: Optional[float], land_unit: Optional[str]) -> Optional[float]:
    if land_area is None:
        return None
    try:
        area = float(land_area)
    except (TypeError, ValueError):
        return None
    unit = _norm(land_unit)
    if unit in ("hectares", "hectare", "ha"):
        return area * 2.47105
    return area


def _state_matches(scheme: Dict[str, Any], farmer_state: str) -> Tuple[bool, str]:
    allowed = [str(s) for s in (scheme.get("states") or [])]
    if not allowed or "all" in [a.lower() for a in allowed]:
        return True, "Scheme is listed as central / all-India."
    if not farmer_state:
        return False, "State is required to check this scheme."
    for a in allowed:
        if _norm(a) == _norm(farmer_state):
            return True, f"Scheme applies in {a}."
    return False, f"Scheme is limited to: {', '.join(allowed)}."


def match_farmer_to_scheme(scheme: Dict[str, Any], profile: Dict[str, Any]) -> Dict[str, Any]:
    reasons: List[str] = []
    unverified: List[str] = []
    missing: List[str] = []
    blockers: List[str] = []

    location = profile.get("location") or {}
    farming = profile.get("farming") or {}
    extra = profile.get("scheme_profile") or profile.get("eligibility") or {}

    state = extra.get("state") or location.get("state") or ""
    district = extra.get("district") or location.get("district") or ""
    land_area = extra.get("land_area") if extra.get("land_area") is not None else farming.get("land_area")
    land_unit = extra.get("land_unit") or farming.get("land_unit") or "Acres"
    tenure = _norm(extra.get("land_tenure") or extra.get("land_ownership"))
    category = _norm(extra.get("farmer_category") or extra.get("category"))
    gender = _norm(extra.get("gender"))
    age = extra.get("age")
    crop = extra.get("crop") or farming.get("crop") or ""
    irrigation = _norm(extra.get("irrigation") or farming.get("irrigation"))
    activities = extra.get("activities") or extra.get("agricultural_activities") or []
    if isinstance(activities, str):
        activities = [activities]

    elig = scheme.get("eligibility") or {}
    state_ok, state_reason = _state_matches(scheme, state)
    if not state:
        missing.append("state")
        unverified.append("State of residence / farm is not provided.")
    elif not state_ok:
        blockers.append(state_reason)
    else:
        reasons.append(state_reason)

    if not district:
        missing.append("district")
        unverified.append("District is not provided; some schemes are notified at district level.")

    acres = _acres(land_area, land_unit)
    if elig.get("landholding_required"):
        if acres is None or acres <= 0:
            missing.append("landholding")
            unverified.append("Landholding size is needed because this scheme is typically linked to agricultural land.")
        else:
            reasons.append(f"Landholding of about {acres:.2f} acres is on the farmer profile.")
    elif acres:
        reasons.append(f"Landholding on profile: about {acres:.2f} acres (not always required for this scheme).")

    allowed_tenure = [_norm(t) for t in (elig.get("land_tenure") or [])]
    if allowed_tenure:
        if not tenure:
            missing.append("land_tenure")
            unverified.append(
                "Land ownership / tenancy status is not filled. This scheme may allow "
                f"{', '.join(elig.get('land_tenure') or [])} as per published guidelines."
            )
        elif tenure not in allowed_tenure and tenure not in ("", "unknown", "skip"):
            blockers.append(
                f"Profile tenure '{tenure}' is not in the guideline list "
                f"({', '.join(elig.get('land_tenure') or [])}). A government officer may still decide otherwise."
            )
        else:
            reasons.append(f"Land tenure '{tenure}' is among the types mentioned in scheme notes.")

    if elig.get("requires_notified_crop_area"):
        unverified.append(
            "Crop and village must be in the current season notification. This app cannot verify notifications."
        )
        if crop:
            reasons.append(f"Profile crop is '{crop}'. Confirm it is notified for your village this season.")
        else:
            missing.append("crop")

    if scheme.get("crops") and "all" not in [str(c).lower() for c in scheme.get("crops")]:
        wanted = [_norm(c) for c in scheme["crops"]]
        if crop and _norm(crop) not in wanted and "notified" not in wanted:
            unverified.append(f"Scheme crop filter is {scheme['crops']}; profile crop is '{crop}'.")

    if elig.get("irrigation_preference") and irrigation:
        prefs = [_norm(p) for p in elig["irrigation_preference"]]
        if irrigation in prefs:
            reasons.append(f"Irrigation method '{irrigation}' is relevant to this scheme.")
        else:
            unverified.append(
                f"Irrigation on profile is '{irrigation}'. Confirm the component still applies."
            )
    elif elig.get("irrigation_preference"):
        missing.append("irrigation")
        unverified.append("Irrigation / water-source details are not on the profile.")

    if elig.get("category_may_affect_rate") and not category:
        missing.append("farmer_category")
        unverified.append("Farmer category (e.g. small/marginal, SC/ST) can change subsidy rates and is not filled.")

    if extra.get("already_beneficiary"):
        unverified.append("Existing beneficiary status can affect duplicate applications; confirm on the official portal.")

    if age in (None, ""):
        if scheme.get("id") in ("pm-kisan",):
            unverified.append("Age/date of birth is not required by this matcher for PM-KISAN, but the portal may still ask for it.")
    if not gender:
        unverified.append("Gender is optional here; fill it only if a scheme guideline uses it.")

    if scheme.get("verification_status") != "official_url_verified":
        unverified.append("Some scheme details are only partially verified from official URLs.")

    if scheme.get("id") == "myscheme-directory":
        status = "more_information_required"
        reasons.append("This is an official directory, not a benefit. Use it to find implementing portals.")
    elif blockers:
        status = "eligibility_criteria_not_met"
    elif missing:
        status = "more_information_required"
    else:
        status = "potentially_eligible"

    if status == "potentially_eligible":
        unverified.append("Exclusion lists (income-tax payers, institutional holders, previous benefit, etc.) are not checked here.")

    return {
        "scheme_id": scheme.get("id"),
        "match_status": status,
        "reasons_may_qualify": reasons,
        "unverified_conditions": unverified,
        "missing_fields": missing,
        "blockers": blockers,
        "disclaimer": PRELIMINARY_DISCLAIMER,
    }


def filter_schemes(
    *,
    query: str = "",
    state: str = "",
    category: str = "",
    crop: str = "",
    benefit_type: str = "",
) -> List[Dict[str, Any]]:
    q = _norm(query)
    st = _norm(state)
    cat = _norm(category)
    cr = _norm(crop)
    bt = _norm(benefit_type)
    out = []
    for s in load_schemes():
        blob = " ".join(
            [
                str(s.get("official_name") or ""),
                str(s.get("official_name_mr") or ""),
                str(s.get("official_name_hi") or ""),
                str(s.get("department") or ""),
                str(s.get("benefits_summary") or ""),
                " ".join(s.get("categories") or []),
            ]
        ).lower()
        if q and q not in blob:
            continue
        if st and st not in ("all",):
            allowed = [_norm(x) for x in (s.get("states") or [])]
            if allowed and "all" not in allowed and st not in allowed:
                continue
        if cat and cat not in [_norm(x) for x in (s.get("categories") or [])]:
            continue
        if cr and cr not in ("all",):
            crops = [_norm(x) for x in (s.get("crops") or [])]
            if crops and "all" not in crops and "notified" not in crops and cr not in crops:
                continue
        if bt and bt not in [_norm(x) for x in (s.get("benefit_types") or [])]:
            continue
        out.append(deepcopy(s))
    return out


def _match_to_frontend_shape(m: Dict[str, Any]) -> Dict[str, Any]:
    reasons = m.get("reasons_may_qualify") or m.get("reasons") or []
    missing = m.get("missing_fields") or m.get("missingFields") or []
    blockers = m.get("blockers") or []
    unverified = m.get("unverified_conditions") or m.get("unverified_conditions") or []
    status = m.get("match_status") or m.get("status") or "more_information_required"
    if status == "potentially_eligible":
        score = 82
    elif status == "more_information_required":
        score = 55
    elif status == "eligibility_criteria_not_met":
        score = 28
    else:
        score = 50
    return {
        "status": status,
        "match_status": status,
        "match_score": score,
        "reasons": reasons,
        "reasons_may_qualify": reasons,
        "missing_fields": missing,
        "missingFields": missing,
        "blockers": blockers,
        "unverified_conditions": unverified,
        "accuracy_badge": "Verified against official criteria" if status == "potentially_eligible" else "Indicative \u2014 needs full review",
    }


def build_match_payload(profile: Dict[str, Any], filters: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
    filters = filters or {}
    schemes = filter_schemes(
        query=filters.get("q") or filters.get("query") or "",
        state=filters.get("state") or "",
        category=filters.get("category") or "",
        crop=filters.get("crop") or "",
        benefit_type=filters.get("benefit_type") or "",
    )
    matches = []
    for s in schemes:
        s_copy = deepcopy(s)
        m_raw = match_farmer_to_scheme(s_copy, profile)
        m_fe = _match_to_frontend_shape(m_raw)
        item = {
            **{k: s_copy.get(k) for k in (
                "id", "official_name", "official_name_mr", "official_name_hi",
                "department", "government_level", "states", "categories", "crops",
                "benefit_types", "benefits_summary", "benefits_unverified_note",
                "official_application_url", "official_guidelines_url",
                "deadline", "deadline_note", "last_verified", "verification_status",
                "source_notes", "application_method", "required_documents",
                "application_steps",
            ) if s_copy.get(k) is not None},
            "scheme": s_copy,
            "match": m_fe,
        }
        status_filter = _norm(filters.get("eligibility_status") or filters.get("status") or "")
        if status_filter and status_filter != m_fe["status"]:
            continue
        matches.append(item)

    order = {
        "potentially_eligible": 0,
        "more_information_required": 1,
        "eligibility_criteria_not_met": 2,
    }
    matches.sort(key=lambda x: (order.get((x.get("match") or {}).get("status"), 9), (x.get("official_name") or "")))
    counts = {"potentially_eligible": 0, "more_information_required": 0, "eligibility_criteria_not_met": 0}
    for it in matches:
        st = (it.get("match") or {}).get("status")
        if st in counts:
            counts[st] += 1
    return {
        "disclaimer": PRELIMINARY_DISCLAIMER,
        "count": len(matches),
        "matches": matches,
        "schemes_with_match": matches,
        "schemes": [m.get("scheme") or m for m in matches],
        "match_summary": counts,
        "is_demo": False,
        "data_source": "Curated scheme database (official URLs/links embedded) - NOT a live government scheme API feed. Always verify on the official scheme portal before applying.",
        "demo_fallback": False,
    }
