from fastapi import APIRouter, HTTPException, status, Depends
from bson import ObjectId
from datetime import datetime
from pymongo.errors import DuplicateKeyError

from models.farmer import (
    FarmerProfileCreate,
    FarmerProfileUpdate,
    FarmerProfileResponse,
)
from database import (
    get_farmer_profile_collection,
    get_marketplace_listing_order_collection,
    get_produce_listing_collection,
    get_user_collection,
)
from auth_utils import assert_user_role, get_current_user
from normalization import normalize_mobile

router = APIRouter()


def _crop_key(value: str) -> str:
    return " ".join(str(value or "").split()).casefold()


def _default_crop_category(crop: str) -> str:
    key = _crop_key(crop)
    if key == "tomato":
        return "Vegetables"
    if key in {"maize", "corn", "corn (maize)", "wheat"}:
        return "Grains"
    return "Other"


async def _sync_profile_crop_listings(profile: dict) -> None:
    user_id = profile["user_id"]
    farming = profile.get("farming") or {}
    crops = [farming.get("crop"), *(farming.get("crops") or [])]
    desired = {}
    for crop in crops:
        name = " ".join(str(crop or "").split())
        key = _crop_key(name)
        if name and key:
            desired.setdefault(key, name)

    listings = get_produce_listing_collection()
    existing = await listings.find({"farmer_id": user_id}).to_list(1000)
    listings_by_crop = {}
    for listing in existing:
        key = listing.get("profile_crop_key") or listing.get("crop_key") or _crop_key(listing.get("crop"))
        if key:
            listings_by_crop.setdefault(key, []).append(listing)

    now = datetime.utcnow()
    location = (profile.get("location") or {}).get("district", "")
    for key, crop in desired.items():
        candidates = [
            listing for listing in listings_by_crop.get(key, [])
            if not listing.get("profile_crop_duplicate")
            and (listing.get("status") != "removed" or listing.get("profile_crop_key") == key)
        ]
        hidden_profile_listing = next(
            (
                listing for listing in candidates
                if listing.get("profile_crop_key") == key and listing.get("profile_crop_hidden")
            ),
            None,
        )
        if hidden_profile_listing:
            for duplicate in candidates:
                if duplicate["_id"] == hidden_profile_listing["_id"]:
                    continue
                active_orders = await get_marketplace_listing_order_collection().count_documents({
                    "listing_id": duplicate["_id"],
                    "status": {"$in": ["pending", "accepted", "in_progress"]},
                })
                update = {
                    "$set": {
                        "status": "paused_profile" if active_orders else "removed",
                        "profile_crop_duplicate": True,
                        "updated_at": now,
                    }
                }
                if duplicate.get("profile_crop_key") == key:
                    update["$unset"] = {"profile_crop_key": ""}
                await listings.update_one(
                    {"_id": duplicate["_id"], "farmer_id": user_id},
                    update,
                )
            continue

        listing = None
        if candidates:
            active_order_counts = {}
            for candidate in candidates:
                active_order_counts[candidate["_id"]] = await get_marketplace_listing_order_collection().count_documents({
                    "listing_id": candidate["_id"],
                    "status": {"$in": ["pending", "accepted", "in_progress"]},
                })

            def listing_priority(candidate: dict) -> tuple:
                has_valid_offer = (
                    float(candidate.get("quantity") or 0) > 0
                    and float(candidate.get("price_per_unit") or 0) > 0
                )
                return (
                    active_order_counts[candidate["_id"]] > 0,
                    active_order_counts[candidate["_id"]],
                    candidate.get("status") == "available" and has_valid_offer,
                    has_valid_offer,
                    candidate.get("profile_crop_key") == key,
                )

            listing = max(candidates, key=listing_priority)
            for duplicate in candidates:
                if duplicate["_id"] == listing["_id"]:
                    continue
                active_orders = active_order_counts[duplicate["_id"]]
                update = {
                    "$set": {
                        "status": "paused_profile" if active_orders else "removed",
                        "profile_crop_duplicate": True,
                        "updated_at": now,
                    }
                }
                if duplicate.get("profile_crop_key") == key:
                    update["$unset"] = {"profile_crop_key": ""}
                await listings.update_one(
                    {"_id": duplicate["_id"], "farmer_id": user_id},
                    update,
                )

        if listing:
            if listing.get("profile_crop_hidden"):
                continue
            fields = {
                "profile_crop_key": key,
                "crop_key": key,
                "farmer_name": profile.get("full_name", "Farmer"),
                "location": listing.get("location") or location,
                "updated_at": now,
            }
            if listing.get("status") in {"removed", "paused_profile"} and listing.get("profile_crop_key") == key:
                publishable = float(listing.get("quantity") or 0) > 0 and float(listing.get("price_per_unit") or 0) > 0
                fields["status"] = "available" if publishable else "draft"
            try:
                await listings.update_one(
                    {"_id": listing["_id"], "farmer_id": user_id},
                    {"$set": fields},
                )
            except DuplicateKeyError:
                canonical = await listings.find_one({"farmer_id": user_id, "profile_crop_key": key})
                if not canonical:
                    raise
                await listings.update_one(
                    {"_id": canonical["_id"], "farmer_id": user_id},
                    {"$set": fields},
                )
            continue
        new_listing = {
            "farmer_id": user_id,
            "farmer_name": profile.get("full_name", "Farmer"),
            "profile_crop_key": key,
            "crop_key": key,
            "crop": crop,
            "category": _default_crop_category(crop),
            "quantity": 0,
            "unit": "kg",
            "price_per_unit": 0,
            "location": location,
            "description": "",
            "image_url": "",
            "min_order_quantity": None,
            "available_from": None,
            "status": "draft",
            "created_at": now,
            "updated_at": now,
        }
        try:
            await listings.insert_one(new_listing)
        except DuplicateKeyError:
            canonical = await listings.find_one({"farmer_id": user_id, "profile_crop_key": key})
            if not canonical:
                raise
            await listings.update_one(
                {"_id": canonical["_id"], "farmer_id": user_id},
                {"$set": {
                    "crop_key": key,
                    "farmer_name": new_listing["farmer_name"],
                    "location": canonical.get("location") or location,
                    "updated_at": now,
                }},
            )

    for key, crop_listings in listings_by_crop.items():
        if key in desired:
            continue
        for listing in crop_listings:
            if listing.get("profile_crop_key") != key:
                continue
            if listing.get("status") in {"removed", "sold"}:
                if listing.get("profile_crop_hidden"):
                    await listings.update_one(
                        {"_id": listing["_id"], "farmer_id": user_id},
                        {"$unset": {"profile_crop_hidden": ""}},
                    )
                continue
            active_orders = await get_marketplace_listing_order_collection().count_documents({
                "listing_id": listing["_id"],
                "status": {"$in": ["pending", "accepted", "in_progress"]},
            })
            await listings.update_one(
                {"_id": listing["_id"], "farmer_id": user_id},
                {"$set": {
                    "status": "paused_profile" if active_orders else "removed",
                    "updated_at": now,
                }},
            )


def _profile_to_response(doc: dict) -> FarmerProfileResponse:
    return FarmerProfileResponse(
        id=str(doc["_id"]),
        user_id=str(doc["user_id"]),
        full_name=doc["full_name"],
        mobile=doc["mobile"],
        location=doc["location"],
        farming=doc["farming"],
        discoverable=doc.get("discoverable", False),
        profile_photo_url=doc.get("profile_photo_url"),
        scheme_profile=doc.get("scheme_profile"),
        created_at=doc.get("created_at"),
        updated_at=doc.get("updated_at"),
    )


@router.get("/profile", response_model=FarmerProfileResponse)
async def get_profile(current_user: dict = Depends(get_current_user)):
    assert_user_role(current_user, "farmer")
    profiles = get_farmer_profile_collection()
    user_oid = ObjectId(current_user["id"])

    profile = await profiles.find_one({"user_id": user_oid})
    if not profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Farmer profile not found. Please create a profile first.",
        )

    return _profile_to_response(profile)


@router.post("/profile", response_model=FarmerProfileResponse, status_code=status.HTTP_201_CREATED)
async def create_profile(
    profile_data: FarmerProfileCreate,
    current_user: dict = Depends(get_current_user),
):
    assert_user_role(current_user, "farmer")
    profiles = get_farmer_profile_collection()
    users = get_user_collection()
    user_oid = ObjectId(current_user["id"])

    existing_mobile = await users.find_one({"mobile_normalized": profile_data.mobile})
    if not existing_mobile:
        existing_mobile = await users.find_one({"mobile": profile_data.mobile})
    if existing_mobile and str(existing_mobile.get("_id")) != str(user_oid):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Mobile number is already registered to another account.",
        )

    existing = await profiles.find_one({"user_id": user_oid})
    if existing:
        await users.update_one(
            {"_id": user_oid}, {"$set": {"profile_complete": True}}
        )
        return _profile_to_response(existing)

    profile_doc: dict = {
        "user_id": user_oid,
        "full_name": profile_data.full_name,
        "mobile": profile_data.mobile,
        "location": profile_data.location.model_dump(),
        "farming": profile_data.farming.model_dump(),
        "discoverable": profile_data.discoverable,
        "profile_photo_url": profile_data.profile_photo_url,
        "created_at": datetime.utcnow(),
        "updated_at": datetime.utcnow(),
    }
    if profile_data.scheme_profile is not None:
        profile_doc["scheme_profile"] = profile_data.scheme_profile.model_dump()

    try:
        result = await profiles.insert_one(profile_doc)
    except DuplicateKeyError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Farmer profile already exists. Use PUT to update it.",
        ) from exc
    profile_doc["_id"] = result.inserted_id
    try:
        await users.update_one(
            {"_id": user_oid},
            {
                "$set": {
                    "mobile": profile_data.mobile,
                    "mobile_normalized": normalize_mobile(profile_data.mobile),
                    "profile_complete": True,
                }
            },
        )
    except DuplicateKeyError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Mobile number is already registered to another account.",
        ) from exc
    await _sync_profile_crop_listings(profile_doc)
    return _profile_to_response(profile_doc)


@router.put("/profile", response_model=FarmerProfileResponse)
async def update_profile(
    update_data: FarmerProfileUpdate,
    current_user: dict = Depends(get_current_user),
):
    assert_user_role(current_user, "farmer")
    profiles = get_farmer_profile_collection()
    user_oid = ObjectId(current_user["id"])

    existing = await profiles.find_one({"user_id": user_oid})
    if not existing:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Farmer profile not found. Create a profile first using POST.",
        )

    update_fields: dict = {}

    if update_data.full_name is not None:
        update_fields["full_name"] = update_data.full_name
    if update_data.mobile is not None:
        users = get_user_collection()
        existing_mobile = await users.find_one({"mobile_normalized": update_data.mobile})
        if existing_mobile and str(existing_mobile.get("_id")) != str(user_oid):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Mobile number is already registered to another account.",
            )
        update_fields["mobile"] = update_data.mobile
    if update_data.location is not None:
        update_fields["location"] = update_data.location.model_dump()
    if update_data.farming is not None:
        farming_data = update_data.farming.model_dump()
        if "crops" not in update_data.farming.model_fields_set:
            farming_data["crops"] = (existing.get("farming") or {}).get("crops", [])
        update_fields["farming"] = farming_data
    if update_data.discoverable is not None:
        update_fields["discoverable"] = update_data.discoverable
    if "profile_photo_url" in update_data.model_fields_set:
        update_fields["profile_photo_url"] = update_data.profile_photo_url
    if update_data.scheme_profile is not None:
        update_fields["scheme_profile"] = update_data.scheme_profile.model_dump()

    if not update_fields:
        return _profile_to_response(existing)

    update_fields["updated_at"] = datetime.utcnow()

    await profiles.update_one(
        {"_id": existing["_id"]},
        {"$set": update_fields},
    )

    user_updates = {"profile_complete": True}
    if update_data.mobile is not None:
        user_updates["mobile"] = update_data.mobile
        user_updates["mobile_normalized"] = normalize_mobile(update_data.mobile)
    await get_user_collection().update_one({"_id": user_oid}, {"$set": user_updates})

    updated = await profiles.find_one({"_id": existing["_id"]})
    await _sync_profile_crop_listings(updated)
    return _profile_to_response(updated)
