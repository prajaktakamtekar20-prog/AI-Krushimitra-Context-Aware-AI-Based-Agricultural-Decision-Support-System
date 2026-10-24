from datetime import datetime
from typing import Any, Dict, Optional

from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException, Query, status

from auth_utils import assert_user_role, get_current_user
from database import get_farmer_profile_collection, get_database
from services.scheme_service import (
    PRELIMINARY_DISCLAIMER,
    build_match_payload,
    get_scheme_by_id,
    load_schemes,
    _match_to_frontend_shape,
)

router = APIRouter()


def _checklist_collection():
    return get_database()["scheme_checklists"]


async def _load_profile_dict(current_user: dict) -> Dict[str, Any]:
    profiles = get_farmer_profile_collection()
    user_oid = ObjectId(current_user["id"])
    doc = await profiles.find_one({"user_id": user_oid})
    if not doc:
        return {
            "full_name": current_user.get("full_name"),
            "mobile": current_user.get("mobile"),
            "location": {},
            "farming": {},
            "scheme_profile": {},
        }
    return {
        "full_name": doc.get("full_name"),
        "mobile": doc.get("mobile"),
        "location": doc.get("location") or {},
        "farming": doc.get("farming") or {},
        "scheme_profile": doc.get("scheme_profile") or {},
    }


@router.get("")
async def list_or_match_schemes(
    q: str = Query("", description="Search name or keyword"),
    state: str = Query("", description="Filter by state"),
    category: str = Query("", description="Filter by category"),
    crop: str = Query("", description="Filter by crop"),
    benefit_type: str = Query("", description="Filter by benefit type"),
    eligibility_status: str = Query("", description="potentially_eligible | more_information_required | eligibility_criteria_not_met"),
    match: bool = Query(True, description="If true, attach eligibility match using the farmer profile"),
    current_user: dict = Depends(get_current_user),
):
    assert_user_role(current_user, "farmer")
    profile = await _load_profile_dict(current_user)
    filters = {
        "q": q,
        "state": state,
        "category": category,
        "crop": crop,
        "benefit_type": benefit_type,
        "eligibility_status": eligibility_status,
    }
    if match:
        return build_match_payload(profile, filters)
    schemes = []
    from services.scheme_service import filter_schemes

    for s in filter_schemes(query=q, state=state, category=category, crop=crop, benefit_type=benefit_type):
        schemes.append(s)
    return {
        "disclaimer": PRELIMINARY_DISCLAIMER,
        "count": len(schemes),
        "schemes": schemes,
        "is_demo": False,
        "demo_fallback": False,
        "data_source": "Curated scheme database (official URLs/links embedded) - NOT a live government scheme API feed. Always verify on the official scheme portal before applying.",
    }


@router.get("/meta")
async def scheme_meta():
    cats = set()
    benefits = set()
    states = set()
    for s in load_schemes():
        cats.update(s.get("categories") or [])
        benefits.update(s.get("benefit_types") or [])
        for st in s.get("states") or []:
            if str(st).lower() != "all":
                states.add(st)
    return {
        "disclaimer": PRELIMINARY_DISCLAIMER,
        "categories": sorted(cats),
        "benefit_types": sorted(benefits),
        "states": sorted(states),
        "eligibility_statuses": [
            "potentially_eligible",
            "more_information_required",
            "eligibility_criteria_not_met",
        ],
        "is_demo": False,
        "demo_fallback": False,
        "data_source": "Curated scheme metadata from the embedded scheme database (official links embedded per scheme record).",
    }


@router.get("/{scheme_id}")
async def get_scheme_detail(
    scheme_id: str,
    current_user: dict = Depends(get_current_user),
):
    assert_user_role(current_user, "farmer")
    scheme = get_scheme_by_id(scheme_id)
    if not scheme:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Scheme not found")
    profile = await _load_profile_dict(current_user)
    from services.scheme_service import match_farmer_to_scheme

    match_raw = match_farmer_to_scheme(scheme, profile)
    match = _match_to_frontend_shape(match_raw)
    checked = []
    try:
        doc = await _checklist_collection().find_one(
            {"user_id": ObjectId(current_user["id"]), "scheme_id": scheme_id}
        )
        if doc:
            checked = list(doc.get("checked_document_ids") or [])
    except Exception:
        checked = []
    return {
        "disclaimer": PRELIMINARY_DISCLAIMER,
        "scheme": scheme,
        "match": match,
        "checklist_progress": {
            "checked_document_ids": checked,
            "note": "Only tick marks are stored. Do not upload identity document scans here.",
        },
        "is_demo": False,
        "demo_fallback": False,
        "data_source": "Curated scheme database (official URLs/links embedded) - NOT a live government scheme API feed. Always verify on the official scheme portal before applying.",
    }


@router.put("/{scheme_id}/checklist")
async def save_checklist(
    scheme_id: str,
    body: Dict[str, Any],
    current_user: dict = Depends(get_current_user),
):
    assert_user_role(current_user, "farmer")
    scheme = get_scheme_by_id(scheme_id)
    if not scheme:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Scheme not found")
    allowed = {d.get("id") for d in (scheme.get("required_documents") or []) if d.get("id")}
    incoming = body.get("checked_document_ids") or []
    if not isinstance(incoming, list):
        raise HTTPException(status_code=400, detail="checked_document_ids must be a list of document ids")
    checked = [str(x) for x in incoming if str(x) in allowed]
    now = datetime.utcnow()
    await _checklist_collection().update_one(
        {"user_id": ObjectId(current_user["id"]), "scheme_id": scheme_id},
        {
            "$set": {
                "checked_document_ids": checked,
                "updated_at": now,
            },
            "$setOnInsert": {
                "user_id": ObjectId(current_user["id"]),
                "scheme_id": scheme_id,
                "created_at": now,
            },
        },
        upsert=True,
    )
    return {
        "scheme_id": scheme_id,
        "checked_document_ids": checked,
        "is_demo": False,
        "demo_fallback": False,
        "data_source": "Checklist saved to backend database. Document tick-marks only — no identity scans are uploaded.",
    }
