from datetime import date, datetime, timedelta
import re
from typing import Literal

from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pymongo.errors import DuplicateKeyError, PyMongoError

from auth_utils import assert_user_role, get_current_user
from database import (
    get_buyer_profile_collection,
    get_buyer_requirement_collection,
    get_farmer_offer_collection,
    get_farmer_profile_collection,
    get_marketplace_listing_order_collection,
    get_marketplace_message_collection,
    get_marketplace_notification_collection,
    get_marketplace_order_collection,
    get_produce_listing_collection,
    get_user_collection,
)
from models.marketplace import (
    BuyerProfileInput,
    FarmerOrderRequestInput,
    ListingOrderInput,
    MarketplaceMessageDeleteInput,
    MarketplaceMessageInput,
    OfferInput,
    ProduceInput,
    RequirementInput,
)
from routes.farmer import _sync_profile_crop_listings

router = APIRouter()
OPEN_REQUIREMENT_STATUSES = {"open", "offer_submitted"}


def _search_pattern(value: str) -> str:
    return re.escape(value.strip())


def _crop_key(value: str) -> str:
    return " ".join(str(value or "").split()).casefold()


def _oid(value: str) -> ObjectId:
    try:
        return ObjectId(value)
    except Exception as exc:
        raise HTTPException(status_code=404, detail="Marketplace record not found.") from exc


def _record(doc: dict) -> dict:
    result = dict(doc)
    result["id"] = str(result.pop("_id"))
    for key in (
        "user_id",
        "buyer_id",
        "farmer_id",
        "requirement_id",
        "offer_id",
        "accepted_offer_id",
        "listing_id",
        "recipient_id",
        "sender_id",
        "receiver_id",
        "order_id",
        "reply_to_id",
    ):
        if result.get(key) is not None:
            result[key] = str(result[key])
    return result


async def _buyer_profile(user_id: ObjectId) -> dict:
    profile = await get_buyer_profile_collection().find_one({"user_id": user_id})
    if not profile:
        raise HTTPException(status_code=409, detail="Complete your buyer profile first.")
    return profile


async def _farmer_profile(user_id: ObjectId) -> dict:
    profile = await get_farmer_profile_collection().find_one({"user_id": user_id})
    if not profile:
        raise HTTPException(status_code=403, detail="A farmer profile is required for this action.")
    return profile


async def _requirement_public_record(doc: dict, include_buyer_contact: bool = False) -> dict:
    result = _record(doc)
    projection = {"full_name": 1, "business_name": 1}
    if include_buyer_contact:
        projection["phone"] = 1
    buyer = await get_buyer_profile_collection().find_one(
        {"user_id": doc["buyer_id"]},
        projection,
    )
    result["buyer_name"] = (buyer or {}).get("full_name", "Verified buyer")
    result["business_name"] = (buyer or {}).get("business_name", "")
    if include_buyer_contact:
        result["buyer_phone"] = (buyer or {}).get("phone") or ""
    return result


def _money(value: float) -> float:
    return round(value, 2)


async def _create_order_notification(order: dict, next_status: str) -> None:
    notifications = get_marketplace_notification_collection()
    notification_type = f"order_{next_status}"
    existing = await notifications.find_one(
        {
            "order_id": order["_id"],
            "recipient_id": order["buyer_id"],
            "type": notification_type,
        }
    )
    if existing:
        return
    crop = str(order.get("crop", "produce")).lower()
    decision = "accepted" if next_status == "accepted" else "rejected"
    notification = {
        "recipient_id": order["buyer_id"],
        "order_id": order["_id"],
        "type": notification_type,
        "message": f"Your {crop} order has been {decision} by the farmer.",
        "is_read": False,
        "created_at": datetime.utcnow(),
    }
    try:
        await notifications.insert_one(notification)
    except DuplicateKeyError:
        return


async def _order_for_participant(order_id: str, user_id: ObjectId) -> dict:
    order_oid = _oid(order_id)
    order = await get_marketplace_listing_order_collection().find_one(
        {"_id": order_oid, "buyer_id": user_id}
    )
    if not order:
        order = await get_marketplace_listing_order_collection().find_one(
            {"_id": order_oid, "farmer_id": user_id}
        )
    if not order:
        order = await get_marketplace_order_collection().find_one(
            {"_id": order_oid, "buyer_id": user_id}
        )
    if not order:
        order = await get_marketplace_order_collection().find_one(
            {"_id": order_oid, "farmer_id": user_id}
        )
    if not order:
        raise HTTPException(status_code=404, detail="Order not found.")
    return order


@router.get("/profile")
async def get_buyer_profile(current_user: dict = Depends(get_current_user)):
    assert_user_role(current_user, "buyer")
    profile = await get_buyer_profile_collection().find_one({"user_id": ObjectId(current_user["id"])})
    if not profile:
        raise HTTPException(status_code=404, detail="Buyer profile not found.")
    return _record(profile)


@router.put("/profile")
async def save_buyer_profile(
    data: BuyerProfileInput,
    current_user: dict = Depends(get_current_user),
):
    assert_user_role(current_user, "buyer")
    user_id = ObjectId(current_user["id"])
    profiles = get_buyer_profile_collection()
    doc = data.model_dump()
    doc["updated_at"] = datetime.utcnow()
    existing = await profiles.find_one({"user_id": user_id})
    if existing:
        await profiles.update_one({"_id": existing["_id"], "user_id": user_id}, {"$set": doc})
        saved = await profiles.find_one({"_id": existing["_id"]})
    else:
        doc.update({"user_id": user_id, "created_at": datetime.utcnow()})
        try:
            result = await profiles.insert_one(doc)
        except DuplicateKeyError as exc:
            raise HTTPException(status_code=409, detail="Buyer profile already exists.") from exc
        saved = await profiles.find_one({"_id": result.inserted_id})

    await get_user_collection().update_one(
        {"_id": user_id, "role": "buyer"}, {"$set": {"profile_complete": True}}
    )
    return _record(saved)


@router.post("/requirements", status_code=status.HTTP_201_CREATED)
async def create_requirement(
    data: RequirementInput,
    current_user: dict = Depends(get_current_user),
):
    assert_user_role(current_user, "buyer")
    user_id = ObjectId(current_user["id"])
    buyer = await _buyer_profile(user_id)
    doc = data.model_dump()
    doc.update(
        {
            "buyer_id": user_id,
            "estimated_budget": _money(data.quantity * data.expected_price_per_unit),
            "delivery_date": data.delivery_date.isoformat(),
            "status": "open",
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow(),
        }
    )
    result = await get_buyer_requirement_collection().insert_one(doc)
    doc["_id"] = result.inserted_id
    response = await _requirement_public_record(doc, include_buyer_contact=True)
    response["buyer_name"] = buyer["full_name"]
    return response


@router.get("/requirements")
async def list_requirements(
    mine: bool = False,
    crop: str = "",
    location: str = "",
    min_quantity: float | None = Query(default=None, ge=0),
    max_quantity: float | None = Query(default=None, ge=0),
    min_price: float | None = Query(default=None, ge=0),
    max_price: float | None = Query(default=None, ge=0),
    status_filter: str = Query(default="", alias="status"),
    current_user: dict = Depends(get_current_user),
):
    requirements = get_buyer_requirement_collection()
    user_id = ObjectId(current_user["id"])
    query: dict = {}
    if mine:
        assert_user_role(current_user, "buyer")
        query["buyer_id"] = user_id
        await _buyer_profile(user_id)
    else:
        assert_user_role(current_user, "farmer")
        await _farmer_profile(user_id)
        query["status"] = {"$in": list(OPEN_REQUIREMENT_STATUSES)}
        query["buyer_id"] = {"$ne": user_id}
    if crop.strip():
        query["crop"] = {"$regex": _search_pattern(crop), "$options": "i"}
    if location.strip():
        query["delivery_location"] = {"$regex": _search_pattern(location), "$options": "i"}
    if min_quantity is not None or max_quantity is not None:
        query["quantity"] = {}
        if min_quantity is not None:
            query["quantity"]["$gte"] = min_quantity
        if max_quantity is not None:
            query["quantity"]["$lte"] = max_quantity
    if min_price is not None or max_price is not None:
        if min_price is not None and max_price is not None and min_price > max_price:
            raise HTTPException(status_code=422, detail="Minimum price cannot exceed maximum price.")
        query["expected_price_per_unit"] = {}
        if min_price is not None:
            query["expected_price_per_unit"]["$gte"] = min_price
        if max_price is not None:
            query["expected_price_per_unit"]["$lte"] = max_price
    if mine and status_filter:
        query["status"] = status_filter
    docs = await requirements.find(query, sort=[("created_at", -1)], limit=100).to_list(100)
    return [
        await _requirement_public_record(doc, include_buyer_contact=True)
        for doc in docs
    ]


@router.put("/requirements/{requirement_id}")
async def update_requirement(
    requirement_id: str,
    data: RequirementInput,
    current_user: dict = Depends(get_current_user),
):
    assert_user_role(current_user, "buyer")
    user_id = ObjectId(current_user["id"])
    requirements = get_buyer_requirement_collection()
    existing = await requirements.find_one(
        {"_id": _oid(requirement_id), "buyer_id": user_id}
    )
    if not existing:
        raise HTTPException(status_code=404, detail="Requirement not found.")
    if existing.get("status") not in OPEN_REQUIREMENT_STATUSES:
        raise HTTPException(status_code=409, detail="Only open requirements can be edited.")
    fields = data.model_dump()
    fields["delivery_date"] = data.delivery_date.isoformat()
    fields["estimated_budget"] = _money(data.quantity * data.expected_price_per_unit)
    fields["updated_at"] = datetime.utcnow()
    result = await requirements.update_one(
        {"_id": existing["_id"], "buyer_id": user_id, "status": {"$in": list(OPEN_REQUIREMENT_STATUSES)}},
        {"$set": fields},
    )
    if not result.matched_count:
        raise HTTPException(status_code=409, detail="Requirement changed and could not be updated.")
    updated = await requirements.find_one({"_id": existing["_id"]})
    return await _requirement_public_record(updated, include_buyer_contact=True)


@router.post("/requirements/{requirement_id}/cancel")
async def cancel_requirement(
    requirement_id: str,
    current_user: dict = Depends(get_current_user),
):
    assert_user_role(current_user, "buyer")
    user_id = ObjectId(current_user["id"])
    requirements = get_buyer_requirement_collection()
    existing = await requirements.find_one({"_id": _oid(requirement_id), "buyer_id": user_id})
    if not existing:
        raise HTTPException(status_code=404, detail="Requirement not found.")
    result = await requirements.update_one(
        {"_id": existing["_id"], "buyer_id": user_id, "status": {"$in": list(OPEN_REQUIREMENT_STATUSES)}},
        {"$set": {"status": "cancelled", "updated_at": datetime.utcnow()}},
    )
    if not result.modified_count:
        raise HTTPException(status_code=409, detail="This requirement can no longer be cancelled.")
    await get_farmer_offer_collection().update_many(
        {"requirement_id": existing["_id"], "status": "submitted"},
        {"$set": {"status": "rejected", "updated_at": datetime.utcnow()}},
    )
    return {"id": requirement_id, "status": "cancelled"}


@router.post("/requirements/{requirement_id}/offers", status_code=status.HTTP_201_CREATED)
async def submit_offer(
    requirement_id: str,
    data: OfferInput,
    current_user: dict = Depends(get_current_user),
):
    assert_user_role(current_user, "farmer")
    user_id = ObjectId(current_user["id"])
    farmer = await _farmer_profile(user_id)
    requirement = await get_buyer_requirement_collection().find_one(
        {"_id": _oid(requirement_id), "status": {"$in": list(OPEN_REQUIREMENT_STATUSES)}}
    )
    if not requirement:
        raise HTTPException(status_code=404, detail="Open requirement not found.")
    if requirement["buyer_id"] == user_id:
        raise HTTPException(status_code=403, detail="You cannot offer on your own requirement.")
    if data.quantity > requirement["quantity"]:
        raise HTTPException(status_code=422, detail="Offer quantity cannot exceed the requested quantity.")
    existing_offer = await get_farmer_offer_collection().find_one(
        {"requirement_id": requirement["_id"], "farmer_id": user_id}
    )
    if existing_offer:
        raise HTTPException(status_code=409, detail="You already submitted an offer for this requirement.")
    profile_location = farmer.get("location") or {}
    farmer_name = farmer.get("full_name", current_user.get("full_name", "Farmer"))
    doc = {
        "requirement_id": requirement["_id"],
        "buyer_id": requirement["buyer_id"],
        "farmer_id": user_id,
        "farmer_name": farmer_name,
        "farmer_location": profile_location.get("district", ""),
        "crop": requirement["crop"],
        "quantity": data.quantity,
        "unit": requirement["unit"],
        "price_per_unit": data.price_per_unit,
        "total_amount": _money(data.quantity * data.price_per_unit),
        "message": data.message,
        "delivery_date": data.delivery_date.isoformat(),
        "status": "submitted",
        "created_at": datetime.utcnow(),
        "updated_at": datetime.utcnow(),
    }
    try:
        inserted = await get_farmer_offer_collection().insert_one(doc)
    except DuplicateKeyError as exc:
        raise HTTPException(status_code=409, detail="You already submitted an offer for this requirement.") from exc
    await get_buyer_requirement_collection().update_one(
        {"_id": requirement["_id"], "status": "open"},
        {"$set": {"status": "offer_submitted", "updated_at": datetime.utcnow()}},
    )
    doc["_id"] = inserted.inserted_id
    return _record(doc)


@router.get("/requirements/{requirement_id}/offers")
async def list_requirement_offers(
    requirement_id: str,
    current_user: dict = Depends(get_current_user),
):
    assert_user_role(current_user, "buyer")
    user_id = ObjectId(current_user["id"])
    requirement = await get_buyer_requirement_collection().find_one(
        {"_id": _oid(requirement_id), "buyer_id": user_id}
    )
    if not requirement:
        raise HTTPException(status_code=404, detail="Requirement not found.")
    docs = await get_farmer_offer_collection().find(
        {"requirement_id": requirement["_id"]}, sort=[("created_at", -1)]
    ).to_list(100)
    return [_record(doc) for doc in docs]


@router.post("/requirements/{requirement_id}/offers/{offer_id}/{decision}")
async def decide_offer(
    requirement_id: str,
    offer_id: str,
    decision: Literal["accept", "reject"],
    current_user: dict = Depends(get_current_user),
):
    assert_user_role(current_user, "buyer")
    user_id = ObjectId(current_user["id"])
    req_id = _oid(requirement_id)
    offer_oid = _oid(offer_id)
    requirements = get_buyer_requirement_collection()
    offers = get_farmer_offer_collection()
    requirement = await requirements.find_one({"_id": req_id, "buyer_id": user_id})
    offer = await offers.find_one(
        {"_id": offer_oid, "requirement_id": req_id, "buyer_id": user_id}
    )
    if not requirement or not offer:
        raise HTTPException(status_code=404, detail="Requirement or offer not found.")
    if decision == "reject":
        if requirement.get("status") not in OPEN_REQUIREMENT_STATUSES or offer.get("status") != "submitted":
            raise HTTPException(status_code=409, detail="This offer can no longer be rejected.")
        await offers.update_one(
            {"_id": offer_oid, "status": "submitted"},
            {"$set": {"status": "rejected", "updated_at": datetime.utcnow()}},
        )
        remaining = await offers.count_documents(
            {"requirement_id": req_id, "status": "submitted"}
        )
        if not remaining:
            await requirements.update_one(
                {"_id": req_id, "status": "offer_submitted"},
                {"$set": {"status": "open", "updated_at": datetime.utcnow()}},
            )
        return {"offer_id": offer_id, "status": "rejected"}

    if offer["quantity"] > requirement["quantity"]:
        raise HTTPException(status_code=409, detail="Requirement quantity changed; this offer is no longer valid.")
    if offer.get("status") != "submitted":
        raise HTTPException(status_code=409, detail="Only a submitted offer can be accepted.")
    if requirement.get("status") not in OPEN_REQUIREMENT_STATUSES:
        raise HTTPException(status_code=409, detail="This requirement has already been decided.")
    accepted = await requirements.update_one(
        {
            "_id": req_id,
            "buyer_id": user_id,
            "status": {"$in": list(OPEN_REQUIREMENT_STATUSES)},
        },
        {
            "$set": {
                "status": "accepted",
                "accepted_offer_id": offer_oid,
                "farmer_id": offer["farmer_id"],
                "updated_at": datetime.utcnow(),
            }
        },
    )
    if not accepted.modified_count:
        raise HTTPException(status_code=409, detail="Another offer has already been accepted.")
    order = {
        "requirement_id": req_id,
        "offer_id": offer_oid,
        "buyer_id": user_id,
        "farmer_id": offer["farmer_id"],
        "crop": requirement["crop"],
        "quantity": offer["quantity"],
        "unit": requirement["unit"],
        "price_per_unit": offer["price_per_unit"],
        "total_amount": offer["total_amount"],
        "delivery_location": requirement["delivery_location"],
        "delivery_date": offer["delivery_date"],
        "status": "accepted",
        "created_at": datetime.utcnow(),
        "updated_at": datetime.utcnow(),
    }
    try:
        await get_marketplace_order_collection().insert_one(order)
    except DuplicateKeyError as exc:
        await requirements.update_one(
            {"_id": req_id, "buyer_id": user_id, "accepted_offer_id": offer_oid},
            {"$set": {"status": "offer_submitted", "updated_at": datetime.utcnow()}, "$unset": {"accepted_offer_id": "", "farmer_id": ""}},
        )
        raise HTTPException(status_code=409, detail="An order already exists for this requirement.") from exc
    except PyMongoError:
        await requirements.update_one(
            {"_id": req_id, "buyer_id": user_id, "accepted_offer_id": offer_oid},
            {"$set": {"status": "offer_submitted", "updated_at": datetime.utcnow()}, "$unset": {"accepted_offer_id": "", "farmer_id": ""}},
        )
        raise
    await offers.update_many(
        {"requirement_id": req_id, "status": "submitted"},
        {"$set": {"status": "rejected", "updated_at": datetime.utcnow()}},
    )
    await offers.update_one(
        {"_id": offer_oid},
        {"$set": {"status": "accepted", "updated_at": datetime.utcnow()}},
    )
    return {"offer_id": offer_id, "status": "accepted"}


@router.post("/produce", status_code=status.HTTP_201_CREATED)
async def create_produce_listing(
    data: ProduceInput,
    current_user: dict = Depends(get_current_user),
):
    assert_user_role(current_user, "farmer")
    user_id = ObjectId(current_user["id"])
    farmer = await _farmer_profile(user_id)
    doc = data.model_dump()
    publish = doc.pop("publish", True)
    crop_key = _crop_key(doc["crop"])
    existing_listings = await get_produce_listing_collection().find(
        {"farmer_id": user_id}, limit=1000
    ).to_list(1000)
    existing = next((item for item in existing_listings if (
        item.get("status") != "removed"
        and (item.get("crop_key") or _crop_key(item.get("crop"))) == crop_key
    )), None)
    if existing:
        return await update_produce_listing(str(existing["_id"]), data, current_user)
    hidden_profile_listing = next((item for item in existing_listings if (
        item.get("status") == "removed"
        and item.get("profile_crop_hidden")
        and item.get("profile_crop_key") == crop_key
    )), None)
    if hidden_profile_listing:
        if isinstance(doc.get("available_from"), date):
            doc["available_from"] = doc["available_from"].isoformat()
        doc.update({
            "crop_key": crop_key,
            "status": "available" if publish else "draft",
            "updated_at": datetime.utcnow(),
        })
        restored = await get_produce_listing_collection().update_one(
            {
                "_id": hidden_profile_listing["_id"],
                "farmer_id": user_id,
                "status": "removed",
                "profile_crop_hidden": True,
            },
            {"$set": doc, "$unset": {"profile_crop_hidden": ""}},
        )
        if not restored.matched_count:
            raise HTTPException(
                status_code=409,
                detail="Listing changed while it was being restored. Please try again.",
            )
        listing = await get_produce_listing_collection().find_one(
            {"_id": hidden_profile_listing["_id"], "farmer_id": user_id}
        )
        if not listing:
            raise HTTPException(status_code=404, detail="Produce listing not found.")
        return _record(listing)
    if isinstance(doc.get("available_from"), date):
        doc["available_from"] = doc["available_from"].isoformat()
    doc.update(
        {
            "farmer_id": user_id,
            "farmer_name": farmer.get("full_name", "Farmer"),
            "crop_key": crop_key,
            "status": "available" if publish else "draft",
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow(),
        }
    )
    result = await get_produce_listing_collection().insert_one(doc)
    doc["_id"] = result.inserted_id
    return _record(doc)


@router.put("/produce/{listing_id}")
async def update_produce_listing(
    listing_id: str,
    data: ProduceInput,
    current_user: dict = Depends(get_current_user),
):
    assert_user_role(current_user, "farmer")
    farmer_id = ObjectId(current_user["id"])
    listing_oid = _oid(listing_id)
    listings = get_produce_listing_collection()
    listing = await listings.find_one({"_id": listing_oid, "farmer_id": farmer_id})
    if not listing:
        raise HTTPException(status_code=404, detail="Produce listing not found.")
    if listing.get("status") not in {"available", "draft", "sold"}:
        raise HTTPException(status_code=409, detail="Only active, draft, or sold listings can be edited.")
    active_orders = await get_marketplace_listing_order_collection().count_documents(
        {
            "listing_id": listing_oid,
            "status": {"$in": ["pending", "accepted", "in_progress"]},
        }
    )
    if active_orders:
        raise HTTPException(
            status_code=409,
            detail="This listing has active orders and cannot be edited yet.",
        )
    fields = data.model_dump()
    publish = fields.pop("publish", True)
    if isinstance(fields.get("available_from"), date):
        fields["available_from"] = fields["available_from"].isoformat()
    fields.update({
        "crop_key": _crop_key(fields["crop"]),
        "status": "available" if publish else "draft",
        "updated_at": datetime.utcnow(),
    })
    edited = await listings.update_one(
        {
            "_id": listing_oid,
            "farmer_id": farmer_id,
            "status": listing["status"],
            "quantity": listing["quantity"],
            "price_per_unit": listing["price_per_unit"],
            "unit": listing["unit"],
        },
        {"$set": fields},
    )
    if not edited.matched_count:
        raise HTTPException(status_code=409, detail="Listing changed while you were editing it.")
    updated = await listings.find_one({"_id": listing_oid, "farmer_id": farmer_id})
    if not updated:
        raise HTTPException(status_code=404, detail="Produce listing not found.")
    return _record(updated)


@router.delete("/produce/{listing_id}")
async def remove_produce_listing(
    listing_id: str,
    current_user: dict = Depends(get_current_user),
):
    assert_user_role(current_user, "farmer")
    farmer_id = ObjectId(current_user["id"])
    listing_oid = _oid(listing_id)
    listings = get_produce_listing_collection()
    listing = await listings.find_one({"_id": listing_oid, "farmer_id": farmer_id})
    if not listing:
        raise HTTPException(status_code=404, detail="Produce listing not found.")
    if listing.get("status") not in {"available", "sold", "draft", "paused_profile"}:
        raise HTTPException(status_code=409, detail="This listing can no longer be removed.")
    active_orders = await get_marketplace_listing_order_collection().count_documents(
        {
            "listing_id": listing_oid,
            "status": {"$in": ["pending", "accepted", "in_progress"]},
        }
    )
    if active_orders:
        raise HTTPException(
            status_code=409,
            detail="This listing has active orders and cannot be removed yet.",
        )
    removed = await listings.update_one(
        {
            "_id": listing_oid,
            "farmer_id": farmer_id,
            "status": listing["status"],
            "quantity": listing["quantity"],
            "price_per_unit": listing["price_per_unit"],
            "unit": listing["unit"],
        },
        {"$set": {
            "status": "removed",
            "profile_crop_hidden": bool(listing.get("profile_crop_key")),
            "updated_at": datetime.utcnow(),
        }},
    )
    if not removed.modified_count:
        raise HTTPException(status_code=409, detail="Listing availability has changed.")
    return {"listing_id": listing_id, "status": "removed"}


@router.get("/produce")
async def browse_produce(
    crop: str = "",
    location: str = "",
    category: str = "",
    current_user: dict = Depends(get_current_user),
):
    assert_user_role(current_user, "buyer")
    query: dict = {
        "status": "available",
        "quantity": {"$gt": 0},
        "price_per_unit": {"$gt": 0},
    }
    if crop.strip():
        query["crop"] = {"$regex": _search_pattern(crop), "$options": "i"}
    if location.strip():
        query["location"] = {"$regex": _search_pattern(location), "$options": "i"}
    if category:
        query["category"] = category
    docs = await get_produce_listing_collection().find(
        query, sort=[("created_at", -1)], limit=100
    ).to_list(100)
    return [_record(doc) for doc in docs]


@router.get("/produce/mine")
async def my_produce(current_user: dict = Depends(get_current_user)):
    assert_user_role(current_user, "farmer")
    user_id = ObjectId(current_user["id"])
    farmer = await _farmer_profile(user_id)
    await _sync_profile_crop_listings(farmer)
    docs = await get_produce_listing_collection().find(
        {
            "farmer_id": user_id,
            "status": {"$ne": "removed"},
            "profile_crop_duplicate": {"$ne": True},
        },
        sort=[("created_at", -1)],
        limit=100,
    ).to_list(100)
    return [_record(doc) for doc in docs]


@router.get("/farmers")
async def browse_farmers(
    name: str = "",
    location: str = "",
    crop: str = "",
    current_user: dict = Depends(get_current_user),
):
    assert_user_role(current_user, "buyer")
    profiles = await get_farmer_profile_collection().find(
        {"discoverable": True}, sort=[("full_name", 1)], limit=200
    ).to_list(200)
    if not profiles:
        return []
    profile_ids = [profile["user_id"] for profile in profiles]
    listing_docs = await get_produce_listing_collection().find(
        {
            "farmer_id": {"$in": profile_ids},
            "status": "available",
            "quantity": {"$gt": 0},
            "price_per_unit": {"$gt": 0},
        },
        sort=[("created_at", -1)],
        limit=1000,
    ).to_list(1000)
    listings_by_farmer: dict[str, list[dict]] = {}
    for listing in listing_docs:
        listings_by_farmer.setdefault(str(listing["farmer_id"]), []).append(listing)

    name_search = name.strip().casefold()
    location_search = location.strip().casefold()
    crop_search = crop.strip().casefold()
    result = []
    for profile in profiles:
        location_info = profile.get("location") or {}
        location_label = ", ".join(
            part
            for part in (
                location_info.get("village"),
                location_info.get("district"),
                location_info.get("state"),
            )
            if part
        )
        farmer_id = str(profile["user_id"])
        farmer_listings = listings_by_farmer.get(farmer_id, [])
        available_crops = list(
            dict.fromkeys(listing.get("crop", "") for listing in farmer_listings)
        )
        profile_crops = (profile.get("farming") or {}).get("crops", [])
        if not profile_crops:
            main_crop = (profile.get("farming") or {}).get("crop")
            profile_crops = [main_crop] if main_crop else []
        if name_search and name_search not in profile.get("full_name", "").casefold():
            continue
        if location_search and location_search not in location_label.casefold():
            continue
        all_crops = list(dict.fromkeys(available_crops + profile_crops))
        if crop_search and not any(
            crop_search in item.casefold() for item in available_crops
        ):
            continue
        result.append(
            {
                "id": farmer_id,
                "full_name": profile.get("full_name", "Farmer"),
                "profile_photo_url": profile.get("profile_photo_url"),
                "location": location_label,
                "crops": all_crops,
                "available_crops": available_crops,
                "available_listings": len(farmer_listings),
            }
        )
    return result


@router.get("/farmers/{farmer_id}")
async def public_farmer_profile(
    farmer_id: str,
    current_user: dict = Depends(get_current_user),
):
    assert_user_role(current_user, "buyer")
    user_oid = _oid(farmer_id)
    profile = await get_farmer_profile_collection().find_one(
        {"user_id": user_oid, "discoverable": True}
    )
    if not profile:
        raise HTTPException(status_code=404, detail="Discoverable farmer profile not found.")
    location_info = profile.get("location") or {}
    public_location = {
        key: location_info[key]
        for key in ("state", "district", "taluka", "village")
        if location_info.get(key)
    }
    listings = await get_produce_listing_collection().find(
        {
            "farmer_id": user_oid,
            "status": "available",
            "quantity": {"$gt": 0},
            "price_per_unit": {"$gt": 0},
        },
        sort=[("created_at", -1)],
        limit=100,
    ).to_list(100)
    return {
        "id": str(user_oid),
        "full_name": profile.get("full_name", "Farmer"),
        "profile_photo_url": profile.get("profile_photo_url"),
        "location": public_location,
        "location_label": ", ".join(
            part
            for part in (
                location_info.get("village"),
                location_info.get("taluka"),
                location_info.get("district"),
                location_info.get("state"),
            )
            if part
        ),
        "farming": profile.get("farming", {}),
        "listings": [_record(listing) for listing in listings],
    }


@router.post(
    "/farmers/{farmer_id}/order-requests",
    status_code=status.HTTP_201_CREATED,
)
async def create_farmer_order_request(
    farmer_id: str,
    data: FarmerOrderRequestInput,
    current_user: dict = Depends(get_current_user),
):
    assert_user_role(current_user, "buyer")
    buyer_id = ObjectId(current_user["id"])
    farmer_oid = _oid(farmer_id)
    farmer_profile = await get_farmer_profile_collection().find_one(
        {"user_id": farmer_oid, "discoverable": True}
    )
    if not farmer_profile:
        raise HTTPException(status_code=404, detail="Discoverable farmer profile not found.")
    if farmer_oid == buyer_id:
        raise HTTPException(status_code=403, detail="You cannot send an order request to yourself.")

    buyer_profile = await _buyer_profile(buyer_id)
    orders = get_marketplace_listing_order_collection()
    request_key = str(data.idempotency_key)
    existing = await orders.find_one(
        {"buyer_id": buyer_id, "idempotency_key": request_key}
    )
    if existing:
        if (
            existing.get("order_type") != "farmer_request"
            or existing.get("farmer_id") != farmer_oid
        ):
            raise HTTPException(status_code=409, detail="Order request key has already been used.")
        return _record(existing)

    listing_oid = _oid(data.listing_id) if data.listing_id else None
    listing = None
    if listing_oid:
        listing = await get_produce_listing_collection().find_one(
            {
                "_id": listing_oid,
                "farmer_id": farmer_oid,
                "status": "available",
            }
        )
        if not listing:
            raise HTTPException(
                status_code=409,
                detail="The selected listing is no longer available from this farmer.",
            )
        if listing.get("crop", "").strip().casefold() != data.crop.strip().casefold():
            raise HTTPException(
                status_code=422,
                detail="The requested crop must match the selected listing.",
            )
        if listing.get("quantity", 0) < data.quantity:
            raise HTTPException(
                status_code=409,
                detail="Requested quantity exceeds the selected listing's available stock.",
            )
        if listing.get("unit") != data.unit:
            raise HTTPException(
                status_code=422,
                detail="The requested unit must match the selected listing.",
            )

    buyer_user = await get_user_collection().find_one({"_id": buyer_id}) or {}
    now = datetime.utcnow()
    order = {
        "order_type": "farmer_request",
        "direct_listing_order": True,
        "buyer_id": buyer_id,
        "farmer_id": farmer_oid,
        "listing_id": listing_oid,
        "crop": data.crop,
        "category": (listing or {}).get("category", "Other"),
        "quantity": data.quantity,
        "unit": data.unit,
        "price_per_unit": _money(data.price_per_unit),
        "total_amount": _money(data.quantity * data.price_per_unit),
        "delivery_location": data.delivery_location,
        "delivery_address": "",
        "delivery_date": data.delivery_date.isoformat(),
        "message": data.message,
        "status": "pending",
        "idempotency_key": request_key,
        "stock_reserved": False,
        "stock_restored": False,
        "buyer_name": buyer_profile.get(
            "full_name", buyer_user.get("full_name", "Buyer")
        ),
        "buyer_business_name": buyer_profile.get("business_name", ""),
        "buyer_phone": buyer_profile.get("phone", ""),
        "buyer_whatsapp": buyer_profile.get("whatsapp", ""),
        "buyer_email": buyer_profile.get("email", ""),
        "farmer_name": farmer_profile.get("full_name", "Farmer"),
        "created_at": now,
        "updated_at": now,
    }
    try:
        inserted = await orders.insert_one(order)
    except DuplicateKeyError as exc:
        duplicate = await orders.find_one(
            {"buyer_id": buyer_id, "idempotency_key": request_key}
        )
        if (
            duplicate
            and duplicate.get("order_type") == "farmer_request"
            and duplicate.get("farmer_id") == farmer_oid
        ):
            return _record(duplicate)
        raise HTTPException(
            status_code=409,
            detail="This order request was already submitted.",
        ) from exc
    order["_id"] = inserted.inserted_id
    return _record(order)


@router.post("/produce/{listing_id}/orders", status_code=status.HTTP_201_CREATED)
async def create_listing_order(
    listing_id: str,
    data: ListingOrderInput,
    current_user: dict = Depends(get_current_user),
):
    assert_user_role(current_user, "buyer")
    buyer_id = ObjectId(current_user["id"])
    listing_oid = _oid(listing_id)
    listing_orders = get_marketplace_listing_order_collection()
    request_key = str(data.idempotency_key)

    existing = await listing_orders.find_one(
        {"buyer_id": buyer_id, "idempotency_key": request_key}
    )
    if existing:
        if existing.get("listing_id") != listing_oid:
            raise HTTPException(status_code=409, detail="Order request key has already been used.")
        return _record(existing)

    listings = get_produce_listing_collection()
    listing = await listings.find_one({
        "_id": listing_oid,
        "status": "available",
        "quantity": {"$gt": 0},
        "price_per_unit": {"$gt": 0},
    })
    if not listing:
        raise HTTPException(status_code=404, detail="Produce listing is no longer available.")
    if listing.get("farmer_id") == buyer_id:
        raise HTTPException(status_code=403, detail="You cannot order your own produce listing.")
    if listing.get("unit") not in {"kg", "quintal", "tonne"}:
        raise HTTPException(status_code=409, detail="This listing has an unsupported quantity unit.")

    farmer_id = listing["farmer_id"]
    farmer = await _farmer_profile(farmer_id)
    buyer_profile = await get_buyer_profile_collection().find_one({"user_id": buyer_id})
    buyer_user = await get_user_collection().find_one({"_id": buyer_id}) or {}
    minimum_order = listing.get("min_order_quantity")
    if minimum_order is not None and data.quantity < minimum_order:
        raise HTTPException(
            status_code=422,
            detail=f"The minimum order quantity for this listing is {minimum_order} {listing['unit']}.",
        )
    if listing.get("quantity", 0) < data.quantity:
        raise HTTPException(status_code=409, detail="Requested quantity exceeds available stock.")
    reserved = await listings.update_one(
        {
            "_id": listing_oid,
            "status": "available",
            "quantity": listing["quantity"],
            "price_per_unit": listing["price_per_unit"],
            "unit": listing["unit"],
        },
        {"$inc": {"quantity": -data.quantity}, "$set": {"updated_at": datetime.utcnow()}},
    )
    if not reserved.modified_count:
        current_listing = await listings.find_one({"_id": listing_oid})
        if not current_listing or current_listing.get("status") != "available":
            raise HTTPException(status_code=409, detail="Produce listing is no longer available.")
        if current_listing.get("quantity", 0) < data.quantity:
            raise HTTPException(status_code=409, detail="Requested quantity exceeds available stock.")
        raise HTTPException(
            status_code=409,
            detail="The listing changed while you were ordering. Refresh and try again.",
        )

    remaining = await listings.find_one({"_id": listing_oid})
    if remaining and remaining.get("quantity", 0) <= 0:
        await listings.update_one(
            {"_id": listing_oid, "quantity": {"$lte": 0}},
            {"$set": {"status": "sold", "updated_at": datetime.utcnow()}},
        )

    now = datetime.utcnow()
    order = {
        "buyer_id": buyer_id,
        "farmer_id": farmer_id,
        "listing_id": listing_oid,
        "crop": listing["crop"],
        "category": listing.get("category", "Other"),
        "quantity": data.quantity,
        "unit": listing["unit"],
        "price_per_unit": _money(listing["price_per_unit"]),
        "total_amount": _money(data.quantity * listing["price_per_unit"]),
        "delivery_location": data.delivery_location,
        "delivery_address": data.delivery_address,
        "delivery_date": data.delivery_date.isoformat(),
        "message": data.message,
        "status": "pending",
        "direct_listing_order": True,
        "idempotency_key": request_key,
        "stock_restored": False,
        "buyer_name": (buyer_profile or {}).get(
            "full_name", buyer_user.get("full_name", "Buyer")
        ),
        "buyer_business_name": (buyer_profile or {}).get("business_name", ""),
        "buyer_phone": (buyer_profile or {}).get(
            "phone", buyer_user.get("mobile", "")
        ),
        "buyer_whatsapp": (buyer_profile or {}).get(
            "whatsapp", buyer_user.get("mobile", "")
        ),
        "buyer_email": (buyer_profile or {}).get("email", buyer_user.get("email", "")),
        "farmer_name": farmer.get("full_name", "Farmer"),
        "created_at": now,
        "updated_at": now,
    }
    try:
        result = await listing_orders.insert_one(order)
    except DuplicateKeyError as exc:
        await listings.update_one(
            {"_id": listing_oid},
            {"$inc": {"quantity": data.quantity}, "$set": {"status": "available"}},
        )
        duplicate = await listing_orders.find_one(
            {"buyer_id": buyer_id, "idempotency_key": request_key}
        )
        if duplicate and duplicate.get("listing_id") == listing_oid:
            return _record(duplicate)
        raise HTTPException(status_code=409, detail="This order request was already submitted.") from exc
    except PyMongoError:
        await listings.update_one(
            {"_id": listing_oid},
            {"$inc": {"quantity": data.quantity}, "$set": {"status": "available"}},
        )
        raise
    order["_id"] = result.inserted_id
    return _record(order)


@router.get("/orders")
async def list_orders(current_user: dict = Depends(get_current_user)):
    if current_user.get("role") not in {"buyer", "farmer"}:
        raise HTTPException(status_code=403, detail="A buyer or farmer account is required.")
    user_id = ObjectId(current_user["id"])
    orders = get_marketplace_order_collection()
    buyer_orders = await orders.find(
        {"buyer_id": user_id}, sort=[("created_at", -1)], limit=100
    ).to_list(100)
    farmer_orders = await orders.find(
        {"farmer_id": user_id}, sort=[("created_at", -1)], limit=100
    ).to_list(100)
    direct_orders = get_marketplace_listing_order_collection()
    direct_buyer_orders = await direct_orders.find(
        {"buyer_id": user_id}, sort=[("created_at", -1)], limit=100
    ).to_list(100)
    direct_farmer_orders = await direct_orders.find(
        {"farmer_id": user_id}, sort=[("created_at", -1)], limit=100
    ).to_list(100)
    docs = {
        str(doc["_id"]): doc
        for doc in buyer_orders + farmer_orders + direct_buyer_orders + direct_farmer_orders
    }
    return [_record(doc) for doc in docs.values()]


@router.get("/orders/{order_id}")
async def order_details(
    order_id: str,
    current_user: dict = Depends(get_current_user),
):
    user_id = ObjectId(current_user["id"])
    order_oid = _oid(order_id)
    order = await get_marketplace_listing_order_collection().find_one(
        {"_id": order_oid, "buyer_id": user_id}
    )
    if not order:
        order = await get_marketplace_listing_order_collection().find_one(
            {"_id": order_oid, "farmer_id": user_id}
        )
    if order:
        buyer = await get_buyer_profile_collection().find_one(
            {"user_id": order["buyer_id"]},
            {"full_name": 1, "phone": 1, "whatsapp": 1, "email": 1},
        )
        buyer_user = await get_user_collection().find_one(
            {"_id": order["buyer_id"]}, {"mobile": 1, "email": 1}
        )
        farmer = await get_farmer_profile_collection().find_one(
            {"user_id": order["farmer_id"]}, {"full_name": 1, "mobile": 1}
        )
        farmer_user = await get_user_collection().find_one(
            {"_id": order["farmer_id"]}, {"mobile": 1, "email": 1}
        )
        result = _record(order)
        result["contacts"] = {
            "buyer": {
                "name": (buyer or {}).get("full_name", order.get("buyer_name", "")),
                "phone": (
                    (buyer or {}).get("phone")
                    or (buyer_user or {}).get("mobile")
                    or order.get("buyer_phone", "")
                ),
                "whatsapp": (
                    (buyer or {}).get("whatsapp")
                    or (buyer or {}).get("phone")
                    or (buyer_user or {}).get("mobile")
                    or order.get("buyer_whatsapp", "")
                    or order.get("buyer_phone", "")
                ),
                "email": (
                    (buyer or {}).get("email")
                    or (buyer_user or {}).get("email")
                    or order.get("buyer_email", "")
                ),
            },
            "farmer": {
                "name": order.get("farmer_name", (farmer or {}).get("full_name", "")),
                "phone": (farmer or {}).get("mobile", (farmer_user or {}).get("mobile", "")),
                "email": (farmer_user or {}).get("email", ""),
            },
        }
        return result
    order = await get_marketplace_order_collection().find_one(
        {"_id": order_oid, "buyer_id": user_id}
    )
    if not order:
        order = await get_marketplace_order_collection().find_one(
            {"_id": order_oid, "farmer_id": user_id}
        )
    if not order:
        raise HTTPException(status_code=404, detail="Order not found.")
    buyer = await get_buyer_profile_collection().find_one({"user_id": order["buyer_id"]})
    farmer = await get_farmer_profile_collection().find_one({"user_id": order["farmer_id"]})
    buyer_user = await get_user_collection().find_one({"_id": order["buyer_id"]})
    farmer_user = await get_user_collection().find_one({"_id": order["farmer_id"]})
    result = _record(order)
    result["contacts"] = {
        "buyer": {
            "name": (buyer or {}).get("full_name", ""),
            "phone": (buyer or {}).get("phone", ""),
            "whatsapp": (buyer or {}).get("whatsapp", ""),
            "email": (buyer or {}).get("email", ""),
        },
        "farmer": {
            "name": (farmer or {}).get("full_name", ""),
            "phone": (farmer or {}).get("mobile", (farmer_user or {}).get("mobile", "")),
            "email": (farmer_user or {}).get("email", ""),
        },
    }
    return result


@router.get("/orders/{order_id}/messages")
async def list_order_messages(
    order_id: str,
    limit: int = Query(default=100, ge=1, le=200),
    current_user: dict = Depends(get_current_user),
):
    if current_user.get("role") not in {"buyer", "farmer"}:
        raise HTTPException(status_code=403, detail="A buyer or farmer account is required.")
    order = await _order_for_participant(
        order_id, ObjectId(current_user["id"])
    )
    messages = await get_marketplace_message_collection().find(
        {
            "order_id": order["_id"],
            "sender_id": {"$in": [order["buyer_id"], order["farmer_id"]]},
        },
        sort=[("created_at", -1), ("_id", -1)],
        limit=limit,
    ).to_list(limit)
    messages.reverse()
    messages = [message for message in messages if (
        message.get("buyer_id") in (None, order["buyer_id"])
        and message.get("farmer_id") in (None, order["farmer_id"])
        and not any(str(hidden_id) == str(current_user["id"]) for hidden_id in message.get("deleted_for", []))
    )]
    for message in messages:
        if message.get("buyer_id") is None:
            message["buyer_id"] = order["buyer_id"]
        if message.get("farmer_id") is None:
            message["farmer_id"] = order["farmer_id"]
        if message.get("receiver_id") is None:
            if message["sender_id"] == order["buyer_id"]:
                message["receiver_id"] = order["farmer_id"]
            elif message["sender_id"] == order["farmer_id"]:
                message["receiver_id"] = order["buyer_id"]
        message["is_deleted"] = bool(message.get("deleted_for_everyone"))
        if message["is_deleted"]:
            message["message"] = ""
        message.pop("deleted_for", None)
        message.pop("deleted_by", None)
    return [_record(message) for message in messages]


@router.get("/conversations")
async def list_chat_conversations(current_user: dict = Depends(get_current_user)):
    if current_user.get("role") not in {"buyer", "farmer"}:
        raise HTTPException(status_code=403, detail="A buyer or farmer account is required.")
    user_id = ObjectId(current_user["id"])
    conversations = []
    for order in await list_orders(current_user):
        is_buyer = order["buyer_id"] == str(user_id)
        other_id = order["farmer_id"] if is_buyer else order["buyer_id"]
        profile_collection = get_farmer_profile_collection() if is_buyer else get_buyer_profile_collection()
        other_profile = await profile_collection.find_one({"user_id": ObjectId(other_id)}) or {}
        messages = await list_order_messages(order["id"], 200, current_user)
        latest_message = messages[-1] if messages else None
        counterpart_name = (
            other_profile.get("full_name")
            or order.get("farmer_name" if is_buyer else "buyer_name")
            or ("Farmer" if is_buyer else "Buyer")
        )
        conversations.append({
            **order,
            "counterpart_id": other_id,
            "counterpart_name": counterpart_name,
            "counterpart_avatar": (
                other_profile.get("avatar_url")
                or other_profile.get("photo_url")
                or other_profile.get("profile_image")
                or ""
            ),
            "latest_message": latest_message,
        })
    conversations.sort(
        key=lambda item: str(
            (item.get("latest_message") or {}).get("created_at")
            or item.get("created_at")
            or ""
        ),
        reverse=True,
    )
    return conversations


async def _message_for_order(order: dict, message_id: str) -> dict:
    message = await get_marketplace_message_collection().find_one({
        "_id": _oid(message_id),
        "order_id": order["_id"],
    })
    if (
        not message
        or message.get("sender_id") not in (order["buyer_id"], order["farmer_id"])
        or message.get("buyer_id") not in (None, order["buyer_id"])
        or message.get("farmer_id") not in (None, order["farmer_id"])
    ):
        raise HTTPException(status_code=404, detail="Message not found.")
    return message


@router.post("/orders/{order_id}/messages", status_code=status.HTTP_201_CREATED)
async def create_order_message(
    order_id: str,
    data: MarketplaceMessageInput,
    current_user: dict = Depends(get_current_user),
):
    if current_user.get("role") not in {"buyer", "farmer"}:
        raise HTTPException(status_code=403, detail="A buyer or farmer account is required.")
    user_id = ObjectId(current_user["id"])
    order = await _order_for_participant(order_id, user_id)
    message_collection = get_marketplace_message_collection()
    client_message_id = str(data.client_message_id) if data.client_message_id else None
    if client_message_id:
        existing = await message_collection.find_one({
            "order_id": order["_id"],
            "sender_id": user_id,
            "client_message_id": client_message_id,
        })
        if existing:
            if existing.get("message") != data.message:
                raise HTTPException(status_code=409, detail="Message ID was already used.")
            return _record(existing)

    reply_to = None
    if data.reply_to_id:
        reply_to = await _message_for_order(order, data.reply_to_id)
        if reply_to.get("deleted_for_everyone") or any(
            str(hidden_id) == str(user_id) for hidden_id in reply_to.get("deleted_for", [])
        ):
            raise HTTPException(status_code=404, detail="Reply message not found.")

    sender_name = (
        order.get("buyer_name", "Buyer")
        if order["buyer_id"] == user_id
        else order.get("farmer_name", "Farmer")
    )
    if sender_name in {"Buyer", "Farmer"}:
        profile_collection = (
            get_buyer_profile_collection()
            if order["buyer_id"] == user_id
            else get_farmer_profile_collection()
        )
        profile = await profile_collection.find_one({"user_id": user_id})
        if profile and profile.get("full_name"):
            sender_name = profile["full_name"]
    message = {
        "order_id": order["_id"],
        "buyer_id": order["buyer_id"],
        "farmer_id": order["farmer_id"],
        "order_type": "direct_listing" if order.get("direct_listing_order") else "requirement_offer",
        "sender_id": user_id,
        "receiver_id": (
            order["farmer_id"] if user_id == order["buyer_id"] else order["buyer_id"]
        ),
        "sender_name": sender_name,
        "message": data.message,
        "created_at": datetime.utcnow(),
    }
    if client_message_id:
        message["client_message_id"] = client_message_id
    if reply_to:
        message.update({
            "reply_to_id": reply_to["_id"],
            "reply_to_sender_name": reply_to.get("sender_name", "Participant"),
            "reply_to_message": reply_to.get("message", ""),
        })
    try:
        inserted = await message_collection.insert_one(message)
    except DuplicateKeyError:
        if not client_message_id:
            raise
        existing = await message_collection.find_one({
            "order_id": order["_id"],
            "sender_id": user_id,
            "client_message_id": client_message_id,
        })
        if not existing:
            raise
        return _record(existing)
    message["_id"] = inserted.inserted_id
    return _record(message)


@router.delete("/orders/{order_id}/messages/{message_id}")
async def delete_order_message(
    order_id: str,
    message_id: str,
    data: MarketplaceMessageDeleteInput,
    current_user: dict = Depends(get_current_user),
):
    if current_user.get("role") not in {"buyer", "farmer"}:
        raise HTTPException(status_code=403, detail="A buyer or farmer account is required.")
    user_id = ObjectId(current_user["id"])
    order = await _order_for_participant(order_id, user_id)
    message = await _message_for_order(order, message_id)
    messages = get_marketplace_message_collection()

    if data.scope == "everyone":
        if message.get("sender_id") != user_id:
            raise HTTPException(status_code=403, detail="Only the sender can delete this message for everyone.")
        created_at = message.get("created_at")
        if not isinstance(created_at, datetime) or datetime.utcnow() - created_at.replace(tzinfo=None) > timedelta(minutes=15):
            raise HTTPException(status_code=403, detail="Messages can only be deleted for everyone within 15 minutes.")
        await messages.update_one(
            {"_id": message["_id"], "order_id": order["_id"]},
            {"$set": {
                "message": "",
                "deleted_for_everyone": True,
                "deleted_by": user_id,
                "deleted_at": datetime.utcnow(),
            }},
        )
        return {"id": str(message["_id"]), "scope": data.scope, "is_deleted": True}

    deleted_for = list(message.get("deleted_for", []))
    if not any(str(hidden_id) == str(user_id) for hidden_id in deleted_for):
        deleted_for.append(user_id)
    await messages.update_one(
        {"_id": message["_id"], "order_id": order["_id"]},
        {"$set": {"deleted_for": deleted_for}},
    )
    return {"id": str(message["_id"]), "scope": data.scope, "is_deleted": False}


@router.get("/notifications")
async def list_marketplace_notifications(
    current_user: dict = Depends(get_current_user),
):
    assert_user_role(current_user, "buyer")
    notifications = await get_marketplace_notification_collection().find(
        {"recipient_id": ObjectId(current_user["id"])},
        sort=[("created_at", -1)],
        limit=100,
    ).to_list(100)
    return [_record(notification) for notification in notifications]


@router.post("/notifications/{notification_id}/read")
async def mark_marketplace_notification_read(
    notification_id: str,
    current_user: dict = Depends(get_current_user),
):
    assert_user_role(current_user, "buyer")
    user_id = ObjectId(current_user["id"])
    notification_oid = _oid(notification_id)
    notifications = get_marketplace_notification_collection()
    updated = await notifications.update_one(
        {"_id": notification_oid, "recipient_id": user_id},
        {"$set": {"is_read": True, "read_at": datetime.utcnow()}},
    )
    if not updated.matched_count:
        raise HTTPException(status_code=404, detail="Notification not found.")
    return {"notification_id": notification_id, "is_read": True}


@router.post("/listing-orders/{order_id}/decision")
async def decide_listing_order(
    order_id: str,
    decision: Literal["accept", "reject"],
    current_user: dict = Depends(get_current_user),
):
    assert_user_role(current_user, "farmer")
    farmer_id = ObjectId(current_user["id"])
    order_oid = _oid(order_id)
    orders = get_marketplace_listing_order_collection()
    order = await orders.find_one({"_id": order_oid, "farmer_id": farmer_id})
    if not order:
        raise HTTPException(status_code=404, detail="Order not found.")
    next_status = "accepted" if decision == "accept" else "rejected"
    if order.get("status") == next_status:
        await _create_order_notification(order, next_status)
        return {"order_id": order_id, "status": next_status}
    if order.get("status") != "pending":
        raise HTTPException(status_code=409, detail="Only pending orders can be decided.")

    reserved_listing = None
    if decision == "accept" and order.get("order_type") == "farmer_request" and order.get("listing_id"):
        listings = get_produce_listing_collection()
        listing = await listings.find_one(
            {
                "_id": order["listing_id"],
                "farmer_id": farmer_id,
                "status": "available",
            }
        )
        if not listing or listing.get("quantity", 0) < order["quantity"]:
            raise HTTPException(
                status_code=409,
                detail="The selected listing no longer has enough available stock.",
            )
        reserved = await listings.update_one(
            {
                "_id": listing["_id"],
                "farmer_id": farmer_id,
                "status": "available",
                "quantity": listing["quantity"],
            },
            {
                "$inc": {"quantity": -order["quantity"]},
                "$set": {"updated_at": datetime.utcnow()},
            },
        )
        if not reserved.modified_count:
            raise HTTPException(
                status_code=409,
                detail="The selected listing changed while accepting this request.",
            )
        reserved_listing = listing
        remaining = listing["quantity"] - order["quantity"]
        if remaining <= 0:
            await listings.update_one(
                {"_id": listing["_id"], "quantity": {"$lte": 0}},
                {"$set": {"status": "sold", "updated_at": datetime.utcnow()}},
            )

    status_fields = {"status": next_status, "updated_at": datetime.utcnow()}
    if reserved_listing:
        status_fields["stock_reserved"] = True
    updated = await orders.update_one(
        {"_id": order_oid, "farmer_id": farmer_id, "status": "pending"},
        {"$set": status_fields},
    )
    if not updated.modified_count:
        if reserved_listing:
            await get_produce_listing_collection().update_one(
                {"_id": reserved_listing["_id"]},
                {
                    "$inc": {"quantity": order["quantity"]},
                    "$set": {"status": "available", "updated_at": datetime.utcnow()},
                },
            )
        raise HTTPException(status_code=409, detail="Order status has already changed.")
    if (
        decision == "reject"
        and order.get("listing_id")
        and order.get("order_type") != "farmer_request"
        and not order.get("stock_restored")
    ):
        listings = get_produce_listing_collection()
        restored = await listings.update_one(
            {"_id": order["listing_id"]},
            {
                "$inc": {"quantity": order["quantity"]},
                "$set": {"status": "available", "updated_at": datetime.utcnow()},
            },
        )
        if not restored.modified_count:
            raise HTTPException(status_code=409, detail="Could not restore produce stock.")
        await orders.update_one(
            {"_id": order_oid, "status": "rejected", "stock_restored": False},
            {"$set": {"stock_restored": True}},
        )
    await _create_order_notification(order, next_status)
    return {"order_id": order_id, "status": next_status}


@router.post("/listing-orders/{order_id}/cancel")
async def cancel_listing_order(
    order_id: str,
    current_user: dict = Depends(get_current_user),
):
    assert_user_role(current_user, "buyer")
    buyer_id = ObjectId(current_user["id"])
    order_oid = _oid(order_id)
    orders = get_marketplace_listing_order_collection()
    order = await orders.find_one({"_id": order_oid, "buyer_id": buyer_id})
    if not order:
        raise HTTPException(status_code=404, detail="Order not found.")
    updated = await orders.update_one(
        {"_id": order_oid, "buyer_id": buyer_id, "status": "pending"},
        {"$set": {"status": "cancelled", "updated_at": datetime.utcnow()}},
    )
    if not updated.modified_count:
        raise HTTPException(status_code=409, detail="Only pending orders can be cancelled.")
    should_restore_stock = (
        order.get("listing_id") is not None
        and order.get("order_type") != "farmer_request"
        and not order.get("stock_restored")
    ) or (
        order.get("order_type") == "farmer_request"
        and order.get("stock_reserved") is True
        and not order.get("stock_restored")
    )
    if should_restore_stock:
        restored = await get_produce_listing_collection().update_one(
            {"_id": order["listing_id"]},
            {
                "$inc": {"quantity": order["quantity"]},
                "$set": {"status": "available", "updated_at": datetime.utcnow()},
            },
        )
        if not restored.modified_count:
            raise HTTPException(status_code=409, detail="Could not restore produce stock.")
        await orders.update_one(
            {"_id": order_oid, "status": "cancelled", "stock_restored": False},
            {"$set": {"stock_restored": True}},
        )
    return {"order_id": order_id, "status": "cancelled"}


@router.post("/orders/{order_id}/status")
async def update_order_status(
    order_id: str,
    next_status: Literal["in_progress", "completed"],
    current_user: dict = Depends(get_current_user),
):
    if current_user.get("role") not in {"buyer", "farmer"}:
        raise HTTPException(status_code=403, detail="A buyer or farmer account is required.")
    user_id = ObjectId(current_user["id"])
    orders = get_marketplace_order_collection()
    direct_orders = get_marketplace_listing_order_collection()
    order_collection = orders
    existing = await orders.find_one({"_id": _oid(order_id), "buyer_id": user_id})
    if not existing:
        existing = await orders.find_one({"_id": _oid(order_id), "farmer_id": user_id})
    if not existing:
        order_collection = direct_orders
        existing = await direct_orders.find_one(
            {"_id": _oid(order_id), "buyer_id": user_id}
        )
        if not existing:
            existing = await direct_orders.find_one(
                {"_id": _oid(order_id), "farmer_id": user_id}
            )
    if not existing:
        raise HTTPException(status_code=404, detail="Order not found.")
    allowed_previous = "accepted" if next_status == "in_progress" else "in_progress"
    owner_field = "buyer_id" if existing.get("buyer_id") == user_id else "farmer_id"
    updated = await order_collection.update_one(
        {"_id": existing["_id"], owner_field: user_id, "status": allowed_previous},
        {"$set": {"status": next_status, "updated_at": datetime.utcnow()}},
    )
    if not updated.modified_count:
        raise HTTPException(status_code=409, detail="Invalid order status transition.")
    return {"order_id": order_id, "status": next_status}


@router.get("/dashboard")
async def marketplace_dashboard(current_user: dict = Depends(get_current_user)):
    if current_user.get("role") not in {"farmer", "buyer"}:
        raise HTTPException(status_code=403, detail="A buyer or farmer account is required.")
    user_id = ObjectId(current_user["id"])
    requirements = get_buyer_requirement_collection()
    offers = get_farmer_offer_collection()
    orders = get_marketplace_order_collection()
    listing_orders = get_marketplace_listing_order_collection()
    buyer_requirements = await requirements.find({"buyer_id": user_id}).to_list(1000)
    requirement_ids = [doc["_id"] for doc in buyer_requirements]
    received = await offers.find({"requirement_id": {"$in": requirement_ids}}).to_list(1000)
    farmer_offer_records = await offers.find({"farmer_id": user_id}).to_list(1000)
    my_orders = await orders.find({"buyer_id": user_id}).to_list(1000)
    farmer_orders = await orders.find({"farmer_id": user_id}).to_list(1000)
    my_listing_orders = await listing_orders.find({"buyer_id": user_id}).to_list(1000)
    farmer_listing_orders = await listing_orders.find({"farmer_id": user_id}).to_list(1000)
    all_orders = {
        str(doc["_id"]): doc
        for doc in my_orders + farmer_orders + my_listing_orders + farmer_listing_orders
    }.values()
    result = {
        "role": current_user["role"],
        "is_buyer": current_user["role"] == "buyer",
        "is_farmer": current_user["role"] == "farmer",
        "orders": len(all_orders),
    }
    if current_user["role"] == "buyer":
        result["buyer"] = {
            "requirements": len(buyer_requirements),
            "active_requirements": sum(doc.get("status") in OPEN_REQUIREMENT_STATUSES for doc in buyer_requirements),
            "offers_received": len(received),
            "accepted_offers": sum(doc.get("status") == "accepted" for doc in received),
            "active_orders": sum(
                doc.get("status") in {"accepted", "in_progress"}
                for doc in my_orders + my_listing_orders
            ),
            "completed_orders": sum(
                doc.get("status") == "completed"
                for doc in my_orders + my_listing_orders
            ),
        }
    else:
        result["farmer"] = {
            "available_requirements": await requirements.count_documents(
                {"status": {"$in": list(OPEN_REQUIREMENT_STATUSES)}, "buyer_id": {"$ne": user_id}}
            ),
            "accepted_offers": sum(doc.get("status") == "accepted" for doc in farmer_offer_records),
            "active_orders": sum(
                doc.get("status") in {"accepted", "in_progress"}
                for doc in farmer_orders + farmer_listing_orders
            ),
            "completed_orders": sum(
                doc.get("status") == "completed"
                for doc in farmer_orders + farmer_listing_orders
            ),
        }
    return result
