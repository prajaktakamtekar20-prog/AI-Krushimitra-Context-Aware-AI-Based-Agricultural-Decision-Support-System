import unittest
from datetime import date, datetime, timedelta
from uuid import uuid4
from unittest.mock import patch

from bson import ObjectId
from fastapi import HTTPException
import httpx
from pydantic import ValidationError

import database
from database import (
    get_buyer_profile_collection,
    get_buyer_requirement_collection,
    get_farmer_profile_collection,
    get_marketplace_listing_order_collection,
    get_marketplace_order_collection,
    get_produce_listing_collection,
    get_user_collection,
)
from routes import auth as auth_routes
from routes import buyer_marketplace as marketplace
from routes import farmer as farmer_routes
from models.farmer import (
    FarmerProfileCreate,
    FarmerProfileUpdate,
    FarmingModel,
    LocationModel,
    UserCreate,
    UserLogin,
)
from models.marketplace import (
    BuyerProfileInput,
    FarmerOrderRequestInput,
    ListingOrderInput,
    MarketplaceMessageInput,
    OfferInput,
    ProduceInput,
    RequirementInput,
)


class MarketplaceWorkflowTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.original_get_database = database.get_database
        database._memory_db.clear()
        database._memory_indexes.clear()
        database._mem_db = database._MemoryDatabase()
        database.get_database = lambda: database._mem_db
        self.buyer_id = ObjectId()
        self.farmer_id = ObjectId()
        self.other_farmer_id = ObjectId()
        self.outsider_id = ObjectId()
        users = get_user_collection()
        for user_id, role in (
            (self.buyer_id, "buyer"),
            (self.farmer_id, "farmer"),
            (self.other_farmer_id, "farmer"),
            (self.outsider_id, "buyer"),
        ):
            await users.insert_one({"_id": user_id, "role": role})
        for user_id, name, mobile in (
            (self.farmer_id, "Farmer One", "9876543210"),
            (self.other_farmer_id, "Farmer Two", "9876543211"),
        ):
            await get_farmer_profile_collection().insert_one(
                {
                    "user_id": user_id,
                    "full_name": name,
                    "mobile": mobile,
                    "location": {"district": "Pune"},
                }
            )

    async def asyncTearDown(self):
        database.get_database = self.original_get_database

    @staticmethod
    def buyer_profile_data():
        return BuyerProfileInput(
            full_name="Buyer One",
            business_name="Fresh Shop",
            buyer_type="Retailer",
            crop_preferences=["Tomato"],
            phone="9876543212",
            whatsapp="9876543212",
            email="buyer@example.com",
            delivery_location="Pune",
        )

    @staticmethod
    def requirement_data(crop="Tomato"):
        return RequirementInput(
            crop=crop,
            category="Vegetables",
            quantity=100,
            unit="kg",
            expected_price_per_unit=25,
            delivery_location="Pune",
            delivery_date=date.today() + timedelta(days=4),
            quality_preferences="Grade A",
            description="Fresh produce",
        )

    @staticmethod
    def offer_data(price=22):
        return OfferInput(
            quantity=80,
            price_per_unit=price,
            message="Fresh harvest available",
            delivery_date=date.today() + timedelta(days=3),
        )

    @staticmethod
    def farmer_order_request_data(listing_id=None):
        return FarmerOrderRequestInput(
            crop="Tomato",
            quantity=3,
            unit="kg",
            price_per_unit=23,
            delivery_location="Pune",
            delivery_date=date.today() + timedelta(days=3),
            message="Please deliver fresh produce.",
            listing_id=listing_id,
            idempotency_key=uuid4(),
        )

    async def test_my_requirement_contact_fallback_when_profile_has_no_phone(self):
        buyer = {"id": str(self.buyer_id), "role": "buyer"}
        await get_buyer_profile_collection().insert_one(
            {
                "user_id": self.buyer_id,
                "full_name": "Buyer Without Contact",
                "business_name": "",
            }
        )

        created = await marketplace.create_requirement(self.requirement_data(), buyer)
        self.assertEqual(created["buyer_phone"], "")
        requirements = await marketplace.list_requirements(
            mine=True,
            min_quantity=None,
            max_quantity=None,
            min_price=None,
            max_price=None,
            status_filter="",
            current_user=buyer,
        )
        self.assertEqual(requirements[0]["buyer_phone"], "")
        farmer_requirements = await marketplace.list_requirements(
            mine=False,
            min_quantity=None,
            max_quantity=None,
            min_price=None,
            max_price=None,
            status_filter="",
            current_user={"id": str(self.farmer_id), "role": "farmer"},
        )
        self.assertEqual(farmer_requirements[0]["buyer_phone"], "")

    async def test_buyer_to_farmer_order_workflow_and_contact_privacy(self):
        buyer = {"id": str(self.buyer_id), "role": "buyer"}
        farmer = {"id": str(self.farmer_id), "role": "farmer"}
        await marketplace.save_buyer_profile(self.buyer_profile_data(), buyer)
        updated_profile = await marketplace.save_buyer_profile(
            self.buyer_profile_data().model_copy(update={"business_name": "Updated Shop"}),
            buyer,
        )
        self.assertEqual(updated_profile["business_name"], "Updated Shop")
        self.assertTrue(
            await auth_routes._profile_is_complete(
                {"_id": self.buyer_id, "role": "buyer"}
            )
        )
        self.assertEqual(
            await auth_routes._profile_role({"_id": self.buyer_id, "role": "buyer"}),
            "buyer",
        )
        requirement = await marketplace.create_requirement(self.requirement_data(), buyer)
        self.assertEqual(requirement["estimated_budget"], 2500)
        self.assertEqual(requirement["buyer_phone"], "9876543212")
        own_requirements = await marketplace.list_requirements(
            mine=True,
            min_quantity=None,
            max_quantity=None,
            min_price=None,
            max_price=None,
            status_filter="",
            current_user=buyer,
        )
        self.assertEqual(own_requirements[0]["buyer_phone"], "9876543212")
        edited = await marketplace.update_requirement(
            requirement["id"],
            self.requirement_data().model_copy(update={"description": "Updated details"}),
            buyer,
        )
        self.assertEqual(edited["description"], "Updated details")

        with self.assertRaises(HTTPException) as role_forbidden:
            await marketplace.save_buyer_profile(
                self.buyer_profile_data().model_copy(update={"full_name": "Farmer Buyer"}),
                farmer,
            )
        self.assertEqual(role_forbidden.exception.status_code, 403)
        farmer_account = await get_user_collection().find_one({"_id": self.farmer_id})
        self.assertEqual(farmer_account["role"], "farmer")
        with self.assertRaises(HTTPException) as buyer_forbidden:
            await marketplace.get_buyer_profile(farmer)
        self.assertEqual(buyer_forbidden.exception.status_code, 403)
        with self.assertRaises(HTTPException) as farmer_forbidden:
            await farmer_routes.get_profile(buyer)
        self.assertEqual(farmer_forbidden.exception.status_code, 403)
        listing = await marketplace.create_produce_listing(
            ProduceInput(
                crop="Tomato",
                category="Vegetables",
                quantity=150,
                unit="kg",
                price_per_unit=20,
                location="Pune",
            ),
            farmer,
        )
        self.assertEqual(listing["status"], "available")
        produce_list = await marketplace.browse_produce(
            crop="",
            location="",
            category="",
            current_user=buyer,
        )
        self.assertEqual(len(produce_list), 1)
        self.assertEqual(produce_list[0]["id"], listing["id"])

        visible = await marketplace.list_requirements(
            mine=False,
            min_quantity=None,
            max_quantity=None,
            min_price=None,
            max_price=None,
            status_filter="",
            current_user=farmer,
        )
        self.assertEqual(len(visible), 1)
        self.assertEqual(visible[0]["buyer_phone"], "9876543212")
        self.assertNotIn("whatsapp", visible[0])
        self.assertNotIn("email", visible[0])
        self.assertNotIn("password", visible[0])
        filtered = await marketplace.list_requirements(
            min_quantity=80,
            max_quantity=100,
            min_price=20,
            max_price=26,
            status_filter="",
            current_user=farmer,
        )
        self.assertEqual(len(filtered), 1)

        offer = await marketplace.submit_offer(requirement["id"], self.offer_data(), farmer)
        self.assertEqual(offer["total_amount"], 1760)
        with self.assertRaises(HTTPException) as duplicate:
            await marketplace.submit_offer(requirement["id"], self.offer_data(), farmer)
        self.assertEqual(duplicate.exception.status_code, 409)

        second_offer = await marketplace.submit_offer(
            requirement["id"],
            self.offer_data(24),
            {"id": str(self.other_farmer_id), "role": "farmer"},
        )
        decision = await marketplace.decide_offer(
            requirement["id"], offer["id"], "accept", buyer
        )
        self.assertEqual(decision["status"], "accepted")
        with self.assertRaises(HTTPException) as conflict:
            await marketplace.decide_offer(
                requirement["id"], second_offer["id"], "accept", buyer
            )
        self.assertEqual(conflict.exception.status_code, 409)

        buyer_orders = await marketplace.list_orders(buyer)
        farmer_orders = await marketplace.list_orders(farmer)
        self.assertEqual(len(buyer_orders), 1)
        self.assertEqual(len(farmer_orders), 1)
        order = await marketplace.order_details(buyer_orders[0]["id"], buyer)
        self.assertEqual(order["contacts"]["buyer"]["phone"], "9876543212")
        self.assertEqual(order["contacts"]["farmer"]["phone"], "9876543210")
        with self.assertRaises(HTTPException) as forbidden:
            await marketplace.order_details(
                buyer_orders[0]["id"],
                {"id": str(self.outsider_id), "role": "buyer"},
            )
        self.assertEqual(forbidden.exception.status_code, 404)

        await marketplace.update_order_status(
            buyer_orders[0]["id"], "in_progress", farmer
        )
        await marketplace.update_order_status(
            buyer_orders[0]["id"], "completed", buyer
        )
        completed = await get_marketplace_order_collection().find_one(
            {"_id": ObjectId(buyer_orders[0]["id"])}
        )
        self.assertEqual(completed["status"], "completed")

        rejection_requirement = await marketplace.create_requirement(
            self.requirement_data("Potato"),
            buyer,
        )
        rejected_offer = await marketplace.submit_offer(
            rejection_requirement["id"],
            self.offer_data(),
            farmer,
        )
        rejected = await marketplace.decide_offer(
            rejection_requirement["id"],
            rejected_offer["id"],
            "reject",
            buyer,
        )
        self.assertEqual(rejected["status"], "rejected")

    async def test_dashboard_counts_direct_listing_orders_for_buyer_and_farmer(self):
        buyer = {"id": str(self.buyer_id), "role": "buyer"}
        farmer = {"id": str(self.farmer_id), "role": "farmer"}
        listing_orders = get_marketplace_listing_order_collection()
        await listing_orders.insert_one({
            "buyer_id": self.buyer_id,
            "farmer_id": self.farmer_id,
            "status": "in_progress",
            "created_at": datetime.utcnow(),
        })
        await listing_orders.insert_one({
            "buyer_id": self.buyer_id,
            "farmer_id": self.farmer_id,
            "status": "completed",
            "created_at": datetime.utcnow(),
        })

        buyer_dashboard = await marketplace.marketplace_dashboard(buyer)
        farmer_dashboard = await marketplace.marketplace_dashboard(farmer)

        self.assertEqual(buyer_dashboard["orders"], 2)
        self.assertEqual(buyer_dashboard["buyer"]["active_orders"], 1)
        self.assertEqual(buyer_dashboard["buyer"]["completed_orders"], 1)
        self.assertEqual(farmer_dashboard["orders"], 2)
        self.assertEqual(farmer_dashboard["farmer"]["active_orders"], 1)
        self.assertEqual(farmer_dashboard["farmer"]["completed_orders"], 1)

    async def test_requirement_is_saved_updated_and_reflected_for_farmers(self):
        buyer = {"id": str(self.buyer_id), "role": "buyer"}
        farmer = {"id": str(self.farmer_id), "role": "farmer"}
        await marketplace.save_buyer_profile(self.buyer_profile_data(), buyer)
        requirement = await marketplace.create_requirement(self.requirement_data(), buyer)
        listed = await marketplace.list_requirements(
            mine=False,
            crop="",
            location="",
            min_quantity=None,
            max_quantity=None,
            min_price=None,
            max_price=None,
            status_filter="",
            current_user=farmer,
        )
        self.assertEqual(len(listed), 1)
        self.assertEqual(listed[0]["id"], requirement["id"])
        self.assertEqual(listed[0]["buyer_phone"], "9876543212")
        self.assertEqual(listed[0]["quantity"], 100)
        self.assertEqual(listed[0]["unit"], "kg")
        self.assertEqual(listed[0]["quality_preferences"], "Grade A")
        self.assertEqual(listed[0]["description"], "Fresh produce")

        await marketplace.update_requirement(
            requirement["id"],
            self.requirement_data(crop="Potato"),
            buyer,
        )
        refreshed = await marketplace.list_requirements(
            mine=False,
            crop="",
            location="",
            min_quantity=None,
            max_quantity=None,
            min_price=None,
            max_price=None,
            status_filter="",
            current_user=farmer,
        )
        self.assertEqual(refreshed[0]["crop"], "Potato")

        cancelled = await marketplace.cancel_requirement(requirement["id"], buyer)
        self.assertEqual(cancelled["status"], "cancelled")
        self.assertEqual(
            await marketplace.list_requirements(
                mine=False,
                crop="",
                location="",
                min_quantity=None,
                max_quantity=None,
                min_price=None,
                max_price=None,
                status_filter="",
                current_user=farmer,
            ),
            [],
        )
        saved = await get_buyer_requirement_collection().find_one(
            {"_id": ObjectId(requirement["id"])}
        )
        self.assertEqual(saved["status"], "cancelled")

    async def test_requirement_cancellation_and_profile_isolation(self):
        buyer = {"id": str(self.buyer_id), "role": "buyer"}
        await marketplace.save_buyer_profile(self.buyer_profile_data(), buyer)
        requirement = await marketplace.create_requirement(
            self.requirement_data("Onion"), buyer
        )
        cancelled = await marketplace.cancel_requirement(requirement["id"], buyer)
        self.assertEqual(cancelled["status"], "cancelled")
        with self.assertRaises(HTTPException) as not_owner:
            await marketplace.cancel_requirement(
                requirement["id"],
                {"id": str(self.outsider_id), "role": "buyer"},
            )
        self.assertEqual(not_owner.exception.status_code, 404)
        with self.assertRaises(HTTPException) as no_profile:
            await marketplace.get_buyer_profile(
                {"id": str(self.outsider_id), "role": "buyer"}
            )
        self.assertEqual(no_profile.exception.status_code, 404)

    async def test_input_models_reject_invalid_contact_and_offer_values(self):
        invalid_profile = self.buyer_profile_data().model_dump()
        invalid_profile["phone"] = "123"
        with self.assertRaises(ValidationError):
            BuyerProfileInput(**invalid_profile)
        with self.assertRaises(ValidationError):
            OfferInput(
                quantity=0,
                price_per_unit=20,
                delivery_date=date.today() + timedelta(days=1),
            )

    async def test_marketplace_actions_reject_the_wrong_account_role(self):
        buyer = {"id": str(self.buyer_id), "role": "buyer"}
        farmer = {"id": str(self.farmer_id), "role": "farmer"}
        listing = ProduceInput(
            crop="Tomato",
            category="Vegetables",
            quantity=20,
            unit="kg",
            price_per_unit=10,
            location="Pune",
        )
        with self.assertRaises(HTTPException) as farmer_as_buyer:
            await marketplace.create_requirement(self.requirement_data(), farmer)
        self.assertEqual(farmer_as_buyer.exception.status_code, 403)
        with self.assertRaises(HTTPException) as buyer_as_farmer:
            await marketplace.create_produce_listing(listing, buyer)
        self.assertEqual(buyer_as_farmer.exception.status_code, 403)
        with self.assertRaises(HTTPException) as buyer_offer:
            await marketplace.submit_offer("invalid", self.offer_data(), buyer)
        self.assertEqual(buyer_offer.exception.status_code, 403)
        with self.assertRaises(HTTPException) as farmer_decision:
            await marketplace.decide_offer("invalid", "invalid", "accept", farmer)
        self.assertEqual(farmer_decision.exception.status_code, 403)

    async def test_farmer_profile_order_request_without_listing_and_with_listing(self):
        buyer = {"id": str(self.buyer_id), "role": "buyer"}
        farmer = {"id": str(self.farmer_id), "role": "farmer"}
        other_farmer = {"id": str(self.other_farmer_id), "role": "farmer"}
        await marketplace.save_buyer_profile(self.buyer_profile_data(), buyer)
        await get_farmer_profile_collection().update_one(
            {"user_id": self.farmer_id}, {"$set": {"discoverable": True}}
        )

        request_data = self.farmer_order_request_data()
        request = await marketplace.create_farmer_order_request(
            str(self.farmer_id), request_data, buyer
        )
        self.assertEqual(request["order_type"], "farmer_request")
        self.assertTrue(request["direct_listing_order"])
        self.assertIsNone(request["listing_id"])
        self.assertEqual(request["buyer_id"], str(self.buyer_id))
        self.assertEqual(request["farmer_id"], str(self.farmer_id))
        self.assertEqual(request["status"], "pending")
        duplicate = await marketplace.create_farmer_order_request(
            str(self.farmer_id), request_data, buyer
        )
        self.assertEqual(duplicate["id"], request["id"])

        buyer_orders = await marketplace.list_orders(buyer)
        farmer_orders = await marketplace.list_orders(farmer)
        self.assertEqual([item["id"] for item in buyer_orders], [request["id"]])
        self.assertEqual([item["id"] for item in farmer_orders], [request["id"]])
        with self.assertRaises(HTTPException) as unauthorized_decision:
            await marketplace.decide_listing_order(request["id"], "accept", other_farmer)
        self.assertEqual(unauthorized_decision.exception.status_code, 404)
        accepted = await marketplace.decide_listing_order(request["id"], "accept", farmer)
        self.assertEqual(accepted["status"], "accepted")
        self.assertEqual((await marketplace.list_orders(buyer))[0]["status"], "accepted")
        self.assertEqual((await marketplace.list_orders(farmer))[0]["status"], "accepted")

        listing = await marketplace.create_produce_listing(
            ProduceInput(
                crop="Tomato",
                category="Vegetables",
                quantity=10,
                unit="kg",
                price_per_unit=20,
                location="Pune",
            ),
            farmer,
        )
        linked_request = await marketplace.create_farmer_order_request(
            str(self.farmer_id),
            self.farmer_order_request_data(listing_id=listing["id"]),
            buyer,
        )
        self.assertEqual(linked_request["listing_id"], listing["id"])
        before_accept = await get_produce_listing_collection().find_one(
            {"_id": ObjectId(listing["id"])}
        )
        self.assertEqual(before_accept["quantity"], 10)
        await marketplace.decide_listing_order(linked_request["id"], "accept", farmer)
        after_accept = await get_produce_listing_collection().find_one(
            {"_id": ObjectId(listing["id"])}
        )
        self.assertEqual(after_accept["quantity"], 7)

        rejected_request = await marketplace.create_farmer_order_request(
            str(self.farmer_id), self.farmer_order_request_data(), buyer
        )
        rejected = await marketplace.decide_listing_order(
            rejected_request["id"], "reject", farmer
        )
        self.assertEqual(rejected["status"], "rejected")
        self.assertEqual((await marketplace.list_orders(buyer))[0]["status"], "rejected")
        farmer_order_statuses = {
            item["id"]: item["status"] for item in await marketplace.list_orders(farmer)
        }
        self.assertEqual(farmer_order_statuses[rejected_request["id"]], "rejected")

        no_listing_request = await marketplace.create_farmer_order_request(
            str(self.farmer_id), self.farmer_order_request_data(), buyer
        )
        with self.assertRaises(HTTPException) as wrong_role:
            await marketplace.create_farmer_order_request(
                str(self.farmer_id),
                self.farmer_order_request_data(),
                farmer,
            )
        self.assertEqual(wrong_role.exception.status_code, 403)
        await marketplace.cancel_listing_order(no_listing_request["id"], buyer)
        cancelled = await get_marketplace_listing_order_collection().find_one(
            {"_id": ObjectId(no_listing_request["id"])}
        )
        self.assertEqual(cancelled["status"], "cancelled")

    async def test_direct_listing_order_stock_decisions_and_authorization(self):
        buyer = {"id": str(self.buyer_id), "role": "buyer"}
        farmer = {"id": str(self.farmer_id), "role": "farmer"}
        other_farmer = {"id": str(self.other_farmer_id), "role": "farmer"}
        await marketplace.save_buyer_profile(self.buyer_profile_data(), buyer)
        listing = await marketplace.create_produce_listing(
            ProduceInput(
                crop="Tomato",
                category="Vegetables",
                quantity=8,
                unit="kg",
                price_per_unit=20,
                location="Pune",
            ),
            farmer,
        )
        order_data = ListingOrderInput(
            quantity=3,
            delivery_location="Pune",
            delivery_address="Market Road",
            delivery_date=date.today() + timedelta(days=2),
            message="Please call before delivery.",
            idempotency_key=uuid4(),
        )
        order = await marketplace.create_listing_order(listing["id"], order_data, buyer)
        self.assertEqual(order["status"], "pending")
        self.assertEqual(order["price_per_unit"], 20)
        self.assertEqual(order["total_amount"], 60)
        self.assertEqual(order["farmer_id"], str(self.farmer_id))
        with self.assertRaises(HTTPException) as another_buyer_cancel:
            await marketplace.cancel_listing_order(
                order["id"], {"id": str(self.outsider_id), "role": "buyer"}
            )
        self.assertEqual(another_buyer_cancel.exception.status_code, 404)
        still_pending = await get_marketplace_listing_order_collection().find_one(
            {"_id": ObjectId(order["id"])}
        )
        self.assertEqual(still_pending["status"], "pending")
        with self.assertRaises(HTTPException) as active_listing_edit:
            await marketplace.update_produce_listing(
                listing["id"],
                ProduceInput(
                    crop="Tomato",
                    category="Vegetables",
                    quantity=5,
                    unit="kg",
                    price_per_unit=24,
                    location="Pune",
                ),
                farmer,
            )
        self.assertEqual(active_listing_edit.exception.status_code, 409)
        with self.assertRaises(HTTPException) as active_listing_remove:
            await marketplace.remove_produce_listing(listing["id"], farmer)
        self.assertEqual(active_listing_remove.exception.status_code, 409)
        self.assertEqual(
            (
                await get_produce_listing_collection().find_one(
                    {"_id": ObjectId(listing["id"])}
                )
            )["quantity"],
            5,
        )

        retried = await marketplace.create_listing_order(listing["id"], order_data, buyer)
        self.assertEqual(retried["id"], order["id"])
        self.assertEqual(
            await get_marketplace_listing_order_collection().count_documents(
                {"buyer_id": self.buyer_id}
            ),
            1,
        )
        farmer_orders = await marketplace.list_orders(farmer)
        buyer_orders = await marketplace.list_orders(buyer)
        self.assertEqual([row["id"] for row in farmer_orders], [order["id"]])
        self.assertEqual([row["id"] for row in buyer_orders], [order["id"]])
        outsider_orders = await marketplace.list_orders(
            {"id": str(self.outsider_id), "role": "buyer"}
        )
        self.assertEqual(outsider_orders, [])
        details = await marketplace.order_details(order["id"], farmer)
        self.assertEqual(details["contacts"]["buyer"]["phone"], "9876543212")
        await get_buyer_profile_collection().update_one(
            {"user_id": self.buyer_id},
            {"$set": {"phone": "9876543213", "whatsapp": "9876543214"}},
        )
        refreshed_details = await marketplace.order_details(order["id"], farmer)
        self.assertEqual(refreshed_details["contacts"]["buyer"]["phone"], "9876543213")
        self.assertEqual(refreshed_details["contacts"]["buyer"]["whatsapp"], "9876543214")
        self.assertNotIn("password", refreshed_details["contacts"]["buyer"])
        self.assertNotIn("email_normalized", refreshed_details["contacts"]["buyer"])

        with self.assertRaises(HTTPException) as outsider:
            await marketplace.order_details(order["id"], other_farmer)
        self.assertEqual(outsider.exception.status_code, 404)
        with self.assertRaises(HTTPException) as other_buyer:
            await marketplace.order_details(
                order["id"], {"id": str(self.outsider_id), "role": "buyer"}
            )
        self.assertEqual(other_buyer.exception.status_code, 404)
        with self.assertRaises(HTTPException) as wrong_role:
            await marketplace.create_listing_order(listing["id"], order_data, farmer)
        self.assertEqual(wrong_role.exception.status_code, 403)

        await marketplace.decide_listing_order(order["id"], "reject", farmer)
        restored_listing = await get_produce_listing_collection().find_one(
            {"_id": ObjectId(listing["id"])}
        )
        self.assertEqual(restored_listing["quantity"], 8)
        self.assertEqual(restored_listing["status"], "available")
        repeated_decision = await marketplace.decide_listing_order(
            order["id"], "reject", farmer
        )
        self.assertEqual(repeated_decision["status"], "rejected")
        self.assertEqual(
            (
                await get_produce_listing_collection().find_one(
                    {"_id": ObjectId(listing["id"])}
                )
            )["quantity"],
            8,
        )

        second_order_data = order_data.model_copy(
            update={"quantity": 8, "idempotency_key": uuid4()}
        )
        second_order = await marketplace.create_listing_order(
            listing["id"], second_order_data, buyer
        )
        sold_listing = await get_produce_listing_collection().find_one(
            {"_id": ObjectId(listing["id"])}
        )
        self.assertEqual(sold_listing["quantity"], 0)
        self.assertEqual(sold_listing["status"], "sold")
        await marketplace.cancel_listing_order(second_order["id"], buyer)
        cancelled_order = await get_marketplace_listing_order_collection().find_one(
            {"_id": ObjectId(second_order["id"])}
        )
        self.assertEqual(cancelled_order["status"], "cancelled")
        reopened_listing = await get_produce_listing_collection().find_one(
            {"_id": ObjectId(listing["id"])}
        )
        self.assertEqual(reopened_listing["quantity"], 8)
        self.assertEqual(reopened_listing["status"], "available")
        with self.assertRaises(HTTPException) as repeated_cancel:
            await marketplace.cancel_listing_order(second_order["id"], buyer)
        self.assertEqual(repeated_cancel.exception.status_code, 409)
        still_restored = await get_produce_listing_collection().find_one(
            {"_id": ObjectId(listing["id"])}
        )
        self.assertEqual(still_restored["quantity"], 8)

        third_order = await marketplace.create_listing_order(
            listing["id"],
            order_data.model_copy(
                update={"quantity": 2, "idempotency_key": uuid4()}
            ),
            buyer,
        )
        with self.assertRaises(HTTPException) as unassigned_farmer:
            await marketplace.decide_listing_order(
                third_order["id"], "accept", other_farmer
            )
        self.assertEqual(unassigned_farmer.exception.status_code, 404)
        accepted = await marketplace.decide_listing_order(
            third_order["id"], "accept", farmer
        )
        self.assertEqual(accepted["status"], "accepted")
        refreshed_buyer_orders = await marketplace.list_orders(buyer)
        accepted_order = next(row for row in refreshed_buyer_orders if row["id"] == third_order["id"])
        self.assertEqual(accepted_order["status"], "accepted")
        with self.assertRaises(HTTPException) as accepted_cannot_cancel:
            await marketplace.cancel_listing_order(third_order["id"], buyer)
        self.assertEqual(accepted_cannot_cancel.exception.status_code, 409)
        await marketplace.update_order_status(third_order["id"], "in_progress", farmer)
        await marketplace.update_order_status(third_order["id"], "completed", buyer)
        completed_direct_order = await get_marketplace_listing_order_collection().find_one(
            {"_id": ObjectId(third_order["id"])}
        )
        self.assertEqual(completed_direct_order["status"], "completed")

    async def test_direct_listing_order_rejects_invalid_quantity_and_insufficient_stock(self):
        buyer = {"id": str(self.buyer_id), "role": "buyer"}
        farmer = {"id": str(self.farmer_id), "role": "farmer"}
        listing = await marketplace.create_produce_listing(
            ProduceInput(
                crop="Potato",
                category="Vegetables",
                quantity=2,
                unit="kg",
                price_per_unit=15,
                location="Pune",
            ),
            farmer,
        )
        with self.assertRaises(ValidationError):
            ListingOrderInput(
                quantity=0,
                delivery_location="Pune",
                delivery_date=date.today(),
                idempotency_key=uuid4(),
            )
        excessive = ListingOrderInput(
            quantity=2.1,
            delivery_location="Pune",
            delivery_date=date.today(),
            idempotency_key=uuid4(),
        )
        with self.assertRaises(HTTPException) as out_of_stock:
            await marketplace.create_listing_order(listing["id"], excessive, buyer)
        self.assertEqual(out_of_stock.exception.status_code, 409)
        unchanged = await get_produce_listing_collection().find_one(
            {"_id": ObjectId(listing["id"])}
        )
        self.assertEqual(unchanged["quantity"], 2)

    async def test_farmer_directory_and_listing_management_are_owner_scoped(self):
        buyer = {"id": str(self.buyer_id), "role": "buyer"}
        farmer = {"id": str(self.farmer_id), "role": "farmer"}
        other_farmer = {"id": str(self.other_farmer_id), "role": "farmer"}
        profiles = get_farmer_profile_collection()
        await profiles.update_one(
            {"user_id": self.farmer_id},
            {
                "$set": {
                    "discoverable": True,
                    "profile_photo_url": "https://example.com/farmer.jpg",
                    "location": {
                        "village": "Sample Village",
                        "district": "Pune",
                        "state": "Maharashtra",
                        "latitude": 18.52,
                        "longitude": 73.85,
                    },
                    "farming": {"crop": "Tomato", "crops": ["Tomato", "Onion"]},
                }
            },
        )
        listing = await marketplace.create_produce_listing(
            ProduceInput(
                crop="Tomato",
                category="Vegetables",
                quantity=12,
                unit="kg",
                price_per_unit=18,
                location="Pune",
                image_url="https://example.com/tomato.jpg",
            ),
            farmer,
        )
        directory = await marketplace.browse_farmers(
            name="farmer one",
            location="pune",
            crop="tom",
            current_user=buyer,
        )
        self.assertEqual([entry["id"] for entry in directory], [str(self.farmer_id)])
        public_profile = await marketplace.public_farmer_profile(str(self.farmer_id), buyer)
        self.assertEqual(public_profile["listings"][0]["id"], listing["id"])
        self.assertNotIn("mobile", public_profile)
        self.assertNotIn("latitude", public_profile["location"])
        self.assertNotIn("phone", directory[0])
        with self.assertRaises(HTTPException) as hidden_profile:
            await marketplace.public_farmer_profile(
                str(self.other_farmer_id), buyer
            )
        self.assertEqual(hidden_profile.exception.status_code, 404)
        with self.assertRaises(HTTPException) as farmer_directory_forbidden:
            await marketplace.browse_farmers(
                current_user={"id": str(self.farmer_id), "role": "farmer"}
            )
        self.assertEqual(farmer_directory_forbidden.exception.status_code, 403)

        edited = await marketplace.update_produce_listing(
            listing["id"],
            ProduceInput(
                crop="Tomato",
                category="Vegetables",
                quantity=9,
                unit="kg",
                price_per_unit=19,
                location="Pune",
                description="Updated harvest",
            ),
            farmer,
        )
        self.assertEqual(edited["quantity"], 9)
        self.assertEqual(edited["price_per_unit"], 19)
        with self.assertRaises(HTTPException) as owner_denied:
            await marketplace.update_produce_listing(
                listing["id"],
                ProduceInput(
                    crop="Tomato",
                    category="Vegetables",
                    quantity=9,
                    unit="kg",
                    price_per_unit=19,
                    location="Pune",
                ),
                other_farmer,
            )
        self.assertEqual(owner_denied.exception.status_code, 404)
        removed = await marketplace.remove_produce_listing(listing["id"], farmer)
        self.assertEqual(removed["status"], "removed")
        with self.assertRaises(HTTPException) as repeated_remove:
            await marketplace.remove_produce_listing(listing["id"], farmer)
        self.assertEqual(repeated_remove.exception.status_code, 409)

    async def test_order_notifications_and_chat_are_persisted_and_private(self):
        buyer = {"id": str(self.buyer_id), "role": "buyer"}
        farmer = {"id": str(self.farmer_id), "role": "farmer"}
        outsider = {"id": str(self.outsider_id), "role": "buyer"}
        await marketplace.save_buyer_profile(self.buyer_profile_data(), buyer)
        listing = await marketplace.create_produce_listing(
            ProduceInput(
                crop="Tomato",
                category="Vegetables",
                quantity=10,
                unit="kg",
                price_per_unit=20,
                location="Pune",
            ),
            farmer,
        )
        order = await marketplace.create_listing_order(
            listing["id"],
            ListingOrderInput(
                quantity=2,
                delivery_location="Pune",
                delivery_date=date.today() + timedelta(days=2),
                idempotency_key=uuid4(),
            ),
            buyer,
        )
        buyer_message = await marketplace.create_order_message(
            order["id"], MarketplaceMessageInput(message="Please deliver in the morning."), buyer
        )
        farmer_message = await marketplace.create_order_message(
            order["id"], MarketplaceMessageInput(message="Confirmed."), farmer
        )
        self.assertEqual(buyer_message["sender_id"], str(self.buyer_id))
        self.assertEqual(farmer_message["sender_id"], str(self.farmer_id))
        history = await marketplace.list_order_messages(
            order["id"], 100, farmer
        )
        self.assertEqual(len(history), 2)
        with self.assertRaises(ValidationError):
            MarketplaceMessageInput(message="   ")
        with self.assertRaises(HTTPException) as forbidden_chat:
            await marketplace.list_order_messages(order["id"], 100, outsider)
        self.assertEqual(forbidden_chat.exception.status_code, 404)

        await marketplace.decide_listing_order(order["id"], "accept", farmer)
        buyer_notifications = await marketplace.list_marketplace_notifications(buyer)
        self.assertEqual(len(buyer_notifications), 1)
        self.assertEqual(buyer_notifications[0]["order_id"], order["id"])
        self.assertIn("tomato order has been accepted", buyer_notifications[0]["message"])
        marked = await marketplace.mark_marketplace_notification_read(
            buyer_notifications[0]["id"], buyer
        )
        self.assertTrue(marked["is_read"])
        with self.assertRaises(HTTPException) as notification_private:
            await marketplace.mark_marketplace_notification_read(
                buyer_notifications[0]["id"], outsider
            )
        self.assertEqual(notification_private.exception.status_code, 404)
        with self.assertRaises(HTTPException) as farmer_notifications_forbidden:
            await marketplace.list_marketplace_notifications(farmer)
        self.assertEqual(farmer_notifications_forbidden.exception.status_code, 403)

    async def test_profile_crops_sync_to_owner_drafts_without_duplicates(self):
        farmer_id = ObjectId()
        await get_user_collection().insert_one({"_id": farmer_id, "role": "farmer"})
        farmer = {"id": str(farmer_id), "role": "farmer"}
        profile = FarmerProfileCreate(
            full_name="Crop Sync Farmer",
            mobile="9876543213",
            location=LocationModel(
                state="Maharashtra",
                district="Pune",
                taluka="Haveli",
                village="Wagholi",
                latitude=18.5,
                longitude=73.9,
            ),
            farming=FarmingModel(
                crop="Tomato",
                crops=["Onion", "Potato", " tomato "],
                variety="Local",
                stage="seedling",
                land_area=1,
                land_unit="Acres",
                soil_type="black",
                irrigation="rainfed",
            ),
        )

        await farmer_routes.create_profile(profile, farmer)
        first = await marketplace.my_produce(farmer)
        self.assertEqual({item["crop"] for item in first}, {"Tomato", "Onion", "Potato"})
        self.assertEqual(len(first), 3)
        self.assertTrue(all(item["status"] == "draft" for item in first))
        tomato = next(item for item in first if item["crop"] == "Tomato")
        self.assertEqual(tomato["quantity"], 0)
        self.assertEqual(tomato["price_per_unit"], 0)
        other_farmer = {"id": str(self.other_farmer_id), "role": "farmer"}
        with self.assertRaises(HTTPException) as other_farmer_edit:
            await marketplace.update_produce_listing(
                tomato["id"],
                ProduceInput(
                    crop="Tomato",
                    category="Vegetables",
                    quantity=1,
                    unit="kg",
                    price_per_unit=1,
                    location="Pune",
                    publish=False,
                ),
                other_farmer,
            )
        self.assertEqual(other_farmer_edit.exception.status_code, 404)
        with self.assertRaises(HTTPException) as other_farmer_delete:
            await marketplace.remove_produce_listing(tomato["id"], other_farmer)
        self.assertEqual(other_farmer_delete.exception.status_code, 404)
        buyer = {"id": str(self.outsider_id), "role": "buyer"}
        self.assertEqual(await marketplace.browse_produce(current_user=buyer), [])

        published = await marketplace.update_produce_listing(
            tomato["id"],
            ProduceInput(
                crop="Tomato",
                category="Vegetables",
                quantity=100,
                unit="kg",
                price_per_unit=30,
                location="Pune",
                min_order_quantity=2,
                available_from=date.today() + timedelta(days=4),
            ),
            farmer,
        )
        self.assertEqual(published["id"], tomato["id"])
        self.assertEqual(published["status"], "available")
        self.assertEqual(published["quantity"], 100)
        buyer_listings = await marketplace.browse_produce(current_user=buyer)
        self.assertEqual([item["id"] for item in buyer_listings], [tomato["id"]])

        repriced = await marketplace.update_produce_listing(
            tomato["id"],
            ProduceInput(
                crop="Tomato",
                category="Vegetables",
                quantity=100,
                unit="kg",
                price_per_unit=32,
                location="Pune",
            ),
            farmer,
        )
        self.assertEqual(repriced["id"], tomato["id"])
        self.assertEqual((await marketplace.browse_produce(current_user=buyer))[0]["price_per_unit"], 32)

        updated_farming = FarmingModel(
            crop="Tomato",
            crops=["Onion", "Carrot"],
            variety="Local",
            stage="vegetative",
            land_area=1,
            land_unit="Acres",
            soil_type="black",
            irrigation="rainfed",
        )
        await farmer_routes.update_profile(FarmerProfileUpdate(farming=updated_farming), farmer)
        await farmer_routes.update_profile(FarmerProfileUpdate(farming=updated_farming), farmer)
        synced = await marketplace.my_produce(farmer)
        self.assertEqual(len(synced), 3)
        self.assertEqual({item["crop"] for item in synced}, {"Tomato", "Onion", "Carrot"})
        self.assertEqual(sum(item["crop"] == "Tomato" for item in synced), 1)
        self.assertEqual(next(item for item in synced if item["crop"] == "Tomato")["category"], "Vegetables")
        self.assertEqual(next(item for item in synced if item["crop"] == "Onion")["category"], "Other")
        self.assertEqual(next(item for item in synced if item["crop"] == "Carrot")["category"], "Other")
        all_listings = await get_produce_listing_collection().find({"farmer_id": farmer_id}).to_list(10)
        self.assertEqual(len(all_listings), 4)
        self.assertEqual(next(item for item in all_listings if item["crop"] == "Potato")["status"], "removed")
        onion = next(item for item in synced if item["crop"] == "Onion")
        await marketplace.remove_produce_listing(onion["id"], farmer)
        await farmer_routes.update_profile(FarmerProfileUpdate(farming=updated_farming), farmer)
        after_delete = await marketplace.my_produce(farmer)
        self.assertEqual({item["crop"] for item in after_delete}, {"Tomato", "Carrot"})
        self.assertNotIn(onion["id"], [item["id"] for item in after_delete])

        readded_onion = await marketplace.create_produce_listing(
            ProduceInput(
                crop="Onion",
                category="Vegetables",
                quantity=50,
                unit="kg",
                price_per_unit=15,
                location="Pune",
            ),
            farmer,
        )
        self.assertEqual(readded_onion["id"], onion["id"])
        self.assertEqual(readded_onion["status"], "available")
        onion_listings = [
            item for item in await marketplace.my_produce(farmer)
            if item["crop"] == "Onion"
        ]
        self.assertEqual(len(onion_listings), 1)

        await marketplace.remove_produce_listing(readded_onion["id"], farmer)
        without_onion = updated_farming.model_copy(update={"crops": ["Carrot"]})
        await farmer_routes.update_profile(
            FarmerProfileUpdate(farming=without_onion),
            farmer,
        )
        with_onion_again = updated_farming.model_copy(
            update={"crops": ["Onion", "Carrot"]}
        )
        await farmer_routes.update_profile(
            FarmerProfileUpdate(farming=with_onion_again),
            farmer,
        )
        after_readd = await marketplace.my_produce(farmer)
        restored_onion = next(item for item in after_readd if item["crop"] == "Onion")
        self.assertEqual(restored_onion["id"], onion["id"])
        self.assertEqual(restored_onion["status"], "available")

    async def test_maize_and_wheat_profile_crops_sync_and_publish_independently(self):
        farmer = {"id": str(self.farmer_id), "role": "farmer"}
        buyer = {"id": str(self.buyer_id), "role": "buyer"}
        farming = FarmingModel(
            crop="Maize",
            crops=["Maize", "Wheat"],
            variety="Local",
            stage="vegetative",
            land_area=1,
            land_unit="Acres",
            soil_type="black",
            irrigation="rainfed",
        )
        location = LocationModel(
            state="Maharashtra",
            district="Pune",
            taluka="Haveli",
            village="Wagholi",
            latitude=18.5,
            longitude=73.9,
        )
        maize_id = ObjectId()
        await get_produce_listing_collection().insert_one({
            "_id": maize_id,
            "farmer_id": self.farmer_id,
            "farmer_name": "Farmer One",
            "profile_crop_key": "corn (maize)",
            "crop_key": "corn (maize)",
            "crop": "Corn (Maize)",
            "category": "Other",
            "quantity": 0,
            "unit": "kg",
            "price_per_unit": 25,
            "location": "Pune",
            "description": "Previously sold crop",
            "status": "sold",
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow(),
        })
        await get_marketplace_listing_order_collection().insert_one({
            "listing_id": maize_id,
            "farmer_id": self.farmer_id,
            "buyer_id": self.buyer_id,
            "status": "completed",
            "created_at": datetime.utcnow(),
        })

        await farmer_routes.update_profile(
            FarmerProfileUpdate(farming=farming, location=location),
            farmer,
        )
        profile = await get_farmer_profile_collection().find_one(
            {"user_id": self.farmer_id}
        )
        self.assertEqual(profile["farming"]["crop"], "Corn (Maize)")
        self.assertEqual(profile["farming"]["crops"], ["Corn (Maize)", "Wheat"])

        first_load = await marketplace.my_produce(farmer)
        self.assertEqual(
            {listing["crop"] for listing in first_load},
            {"Corn (Maize)", "Wheat"},
        )
        self.assertEqual(len(first_load), 2)
        maize = next(item for item in first_load if item["crop"] == "Corn (Maize)")
        wheat = next(item for item in first_load if item["crop"] == "Wheat")
        self.assertEqual(maize["status"], "sold")
        self.assertEqual(maize["category"], "Other")
        self.assertEqual(wheat["status"], "draft")
        self.assertEqual(wheat["category"], "Grains")

        def listing_input(crop, price, quantity, publish=False, category="Other"):
            return ProduceInput(
                crop=crop,
                category=category,
                quantity=quantity,
                unit="kg",
                price_per_unit=price,
                location="Pune",
                min_order_quantity=2,
                available_from=date.today() + timedelta(days=5),
                description=f"{crop} harvest",
                publish=publish,
            )

        maize_draft = await marketplace.update_produce_listing(
            maize["id"], listing_input("Corn (Maize)", 20, 80, category="Grains"), farmer
        )
        wheat_draft = await marketplace.update_produce_listing(
            wheat["id"], listing_input("Wheat", 30, 60, category="Fruits"), farmer
        )
        refreshed = await marketplace.my_produce(farmer)
        self.assertEqual(len(refreshed), 2)
        maize_after_reload = next(item for item in refreshed if item["id"] == maize["id"])
        wheat_after_reload = next(item for item in refreshed if item["id"] == wheat["id"])
        for saved, price, quantity, crop in (
            (maize_after_reload, 20, 80, "Corn (Maize)"),
            (wheat_after_reload, 30, 60, "Wheat"),
        ):
            self.assertEqual(saved["price_per_unit"], price)
            self.assertEqual(saved["quantity"], quantity)
            self.assertEqual(saved["min_order_quantity"], 2)
            self.assertEqual(saved["description"], f"{crop} harvest")
            self.assertEqual(saved["status"], "draft")
        self.assertEqual(maize_after_reload["category"], "Grains")
        self.assertEqual(wheat_after_reload["category"], "Fruits")

        published_maize = await marketplace.update_produce_listing(
            maize["id"], listing_input("Corn (Maize)", 20, 80, publish=True), farmer
        )
        self.assertEqual(published_maize["status"], "available")
        self.assertEqual(wheat_draft["status"], "draft")
        buyer_listings = await marketplace.browse_produce(
            current_user=buyer,
        )
        self.assertEqual([item["id"] for item in buyer_listings], [maize["id"]])
        self.assertEqual(buyer_listings[0]["crop"], "Corn (Maize)")
        self.assertEqual(maize_draft["id"], maize["id"])
        self.assertEqual(
            await get_marketplace_listing_order_collection().count_documents(
                {"listing_id": maize_id, "status": "completed"}
            ),
            1,
        )

        await farmer_routes.update_profile(
            FarmerProfileUpdate(farming=farming),
            farmer,
        )
        final_load = await marketplace.my_produce(farmer)
        self.assertEqual(len(final_load), 2)
        self.assertEqual(
            {listing["id"] for listing in final_load},
            {maize["id"], wheat["id"]},
        )
        self.assertEqual(
            next(item for item in final_load if item["id"] == maize["id"])["status"],
            "available",
        )
        self.assertEqual(
            next(item for item in final_load if item["id"] == wheat["id"])["status"],
            "draft",
        )

    async def test_my_listings_backfills_legacy_profile_crops_and_reopens_sold_listing(self):
        farmer = {"id": str(self.farmer_id), "role": "farmer"}
        profile = await get_farmer_profile_collection().find_one(
            {"user_id": self.farmer_id}
        )
        await get_farmer_profile_collection().update_one(
            {"_id": profile["_id"]},
            {"$set": {
                "farming": {
                    "crop": "Tomato",
                    "crops": ["Tomato", "Onion", "Potato"],
                },
            }},
        )
        inserted = await get_produce_listing_collection().insert_one({
            "farmer_id": self.farmer_id,
            "farmer_name": "Farmer One",
            "crop": "Tomato",
            "crop_key": "tomato",
            "category": "Vegetables",
            "quantity": 0,
            "unit": "kg",
            "price_per_unit": 50,
            "location": "Gangai Lawn, Bawdabagh",
            "description": "Existing listing details",
            "image_url": "",
            "status": "sold",
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow(),
        })

        first = await marketplace.my_produce(farmer)
        self.assertEqual({item["crop"] for item in first}, {"Tomato", "Onion", "Potato"})
        self.assertEqual(len(first), 3)
        tomato = next(item for item in first if item["crop"] == "Tomato")
        self.assertEqual(tomato["id"], str(inserted.inserted_id))
        self.assertEqual(tomato["status"], "sold")
        self.assertEqual(tomato["price_per_unit"], 50)
        self.assertEqual(tomato["location"], "Gangai Lawn, Bawdabagh")
        self.assertTrue(all(
            item["status"] == "draft"
            for item in first
            if item["crop"] in {"Onion", "Potato"}
        ))

        published = await marketplace.update_produce_listing(
            tomato["id"],
            ProduceInput(
                crop="Tomato",
                category="Vegetables",
                quantity=100,
                unit="kg",
                price_per_unit=30,
                location="Gangai Lawn, Bawdabagh",
                description="Existing listing details",
                publish=True,
            ),
            farmer,
        )
        self.assertEqual(published["id"], tomato["id"])
        self.assertEqual(published["status"], "available")
        self.assertEqual(published["price_per_unit"], 30)
        self.assertEqual(published["quantity"], 100)

        second = await marketplace.my_produce(farmer)
        self.assertEqual(len(second), 3)
        refreshed_tomato = next(item for item in second if item["crop"] == "Tomato")
        self.assertEqual(refreshed_tomato["id"], tomato["id"])
        self.assertEqual(refreshed_tomato["price_per_unit"], 30)
        self.assertEqual(refreshed_tomato["quantity"], 100)
        self.assertEqual(refreshed_tomato["description"], "Existing listing details")
        buyer = {"id": str(self.outsider_id), "role": "buyer"}
        buyer_listings = await marketplace.browse_produce(
            current_user=buyer,
        )
        self.assertEqual([item["id"] for item in buyer_listings], [tomato["id"]])

    async def test_profile_sync_coalesces_duplicate_crops_and_preserves_listing_data(self):
        farmer_id = ObjectId()
        await get_user_collection().insert_one({"_id": farmer_id, "role": "farmer"})
        farmer = {"id": str(farmer_id), "role": "farmer"}
        profile = FarmerProfileCreate(
            full_name="Duplicate Crop Farmer",
            mobile="9876543214",
            location=LocationModel(
                state="Maharashtra",
                district="Pune",
                taluka="Haveli",
                village="Wagholi",
                latitude=18.5,
                longitude=73.9,
            ),
            farming=FarmingModel(
                crop="Tomato",
                crops=["Onion", "Potato"],
                variety="Local",
                stage="seedling",
                land_area=1,
                land_unit="Acres",
                soil_type="black",
                irrigation="rainfed",
            ),
        )
        await farmer_routes.create_profile(profile, farmer)
        original_tomato = next(
            item for item in await marketplace.my_produce(farmer)
            if item["crop"] == "Tomato"
        )
        duplicate_result = await get_produce_listing_collection().insert_one({
            "farmer_id": farmer_id,
            "farmer_name": "Duplicate Crop Farmer",
            "profile_crop_key": "tomato",
            "crop_key": "tomato",
            "crop": "Tomato",
            "category": "Vegetables",
            "quantity": 100,
            "unit": "kg",
            "price_per_unit": 30,
            "location": "Pune",
            "description": "Ready for harvest",
            "image_url": "",
            "min_order_quantity": 2,
            "available_from": date.today() + timedelta(days=4),
            "status": "available",
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow(),
        })
        duplicate_id = duplicate_result.inserted_id
        order_duplicate_result = await get_produce_listing_collection().insert_one({
            "farmer_id": farmer_id,
            "farmer_name": "Duplicate Crop Farmer",
            "profile_crop_key": "tomato",
            "crop_key": "tomato",
            "crop": "Tomato",
            "category": "Vegetables",
            "quantity": 50,
            "unit": "kg",
            "price_per_unit": 25,
            "location": "Pune",
            "description": "Existing order listing",
            "status": "available",
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow(),
        })
        order_duplicate_id = order_duplicate_result.inserted_id
        listing_orders = get_marketplace_listing_order_collection()
        await listing_orders.insert_one({
            "listing_id": duplicate_id,
            "farmer_id": farmer_id,
            "status": "pending",
        })
        await listing_orders.insert_one({
            "listing_id": order_duplicate_id,
            "farmer_id": farmer_id,
            "status": "pending",
        })

        await farmer_routes.update_profile(
            FarmerProfileUpdate(farming=profile.farming),
            farmer,
        )
        await farmer_routes.update_profile(
            FarmerProfileUpdate(farming=profile.farming),
            farmer,
        )

        visible = await marketplace.my_produce(farmer)
        tomatoes = [item for item in visible if item["crop"] == "Tomato"]
        self.assertEqual(len(tomatoes), 1)
        self.assertEqual(tomatoes[0]["id"], str(duplicate_id))
        self.assertEqual(tomatoes[0]["status"], "available")
        self.assertEqual(tomatoes[0]["price_per_unit"], 30)
        self.assertEqual(tomatoes[0]["quantity"], 100)
        self.assertEqual(tomatoes[0]["description"], "Ready for harvest")
        self.assertEqual(tomatoes[0]["min_order_quantity"], 2)

        archived_original = await get_produce_listing_collection().find_one(
            {"_id": ObjectId(original_tomato["id"])}
        )
        self.assertEqual(archived_original["status"], "removed")
        self.assertNotIn("profile_crop_key", archived_original)
        archived_with_order = await get_produce_listing_collection().find_one(
            {"_id": order_duplicate_id}
        )
        self.assertEqual(archived_with_order["status"], "paused_profile")
        self.assertNotIn("profile_crop_key", archived_with_order)
        retained_orders = await listing_orders.count_documents({
            "listing_id": {"$in": [duplicate_id, order_duplicate_id]}
        })
        self.assertEqual(retained_orders, 2)

    async def test_chat_supports_orders_created_from_accepted_farmer_offers(self):
        buyer = {"id": str(self.buyer_id), "role": "buyer"}
        farmer = {"id": str(self.farmer_id), "role": "farmer"}
        await marketplace.save_buyer_profile(self.buyer_profile_data(), buyer)
        order = {
            "buyer_id": self.buyer_id,
            "farmer_id": self.farmer_id,
            "crop": "Tomato",
            "status": "accepted",
            "created_at": datetime.utcnow(),
        }
        inserted = await get_marketplace_order_collection().insert_one(order)
        order_id = str(inserted.inserted_id)

        buyer_message = await marketplace.create_order_message(
            order_id, MarketplaceMessageInput(message="Hi, checking on the order."), buyer
        )
        farmer_message = await marketplace.create_order_message(
            order_id, MarketplaceMessageInput(message="Hello, it is confirmed."), farmer
        )

        buyer_history = await marketplace.list_order_messages(order_id, 100, buyer)
        farmer_history = await marketplace.list_order_messages(order_id, 100, farmer)
        self.assertEqual([message["id"] for message in buyer_history], [buyer_message["id"], farmer_message["id"]])
        self.assertEqual([message["id"] for message in farmer_history], [buyer_message["id"], farmer_message["id"]])
        self.assertEqual(buyer_message["sender_name"], "Buyer One")
        self.assertEqual(farmer_message["sender_name"], "Farmer One")
        self.assertEqual(buyer_message["order_type"], "requirement_offer")

    async def test_legacy_messages_without_receiver_are_returned_to_correct_participant(self):
        from database import get_marketplace_message_collection

        buyer_id = self.buyer_id
        farmer_id = self.farmer_id
        order_result = await get_marketplace_listing_order_collection().insert_one({
            "buyer_id": buyer_id,
            "farmer_id": farmer_id,
            "crop": "Tomato",
            "direct_listing_order": True,
            "status": "accepted",
            "created_at": datetime.utcnow(),
        })
        order_id = order_result.inserted_id
        await get_marketplace_message_collection().insert_one({
            "order_id": order_id,
            "sender_id": farmer_id,
            "sender_name": "Farmer One",
            "message": "hii",
            "created_at": datetime.utcnow(),
        })
        await get_marketplace_message_collection().insert_one({
            "order_id": order_id,
            "buyer_id": self.outsider_id,
            "farmer_id": farmer_id,
            "sender_id": farmer_id,
            "sender_name": "Farmer One",
            "message": "misassigned",
            "created_at": datetime.utcnow() + timedelta(seconds=1),
        })

        buyer_history = await marketplace.list_order_messages(
            str(order_id), 100, {"id": str(buyer_id), "role": "buyer"}
        )
        farmer_history = await marketplace.list_order_messages(
            str(order_id), 100, {"id": str(farmer_id), "role": "farmer"}
        )
        self.assertEqual(buyer_history, farmer_history)
        self.assertEqual(len(buyer_history), 1)
        self.assertEqual(buyer_history[0]["message"], "hii")
        self.assertEqual(buyer_history[0]["sender_id"], str(farmer_id))
        self.assertEqual(buyer_history[0]["buyer_id"], str(buyer_id))
        self.assertEqual(buyer_history[0]["farmer_id"], str(farmer_id))
        self.assertEqual(buyer_history[0]["receiver_id"], str(buyer_id))

    async def test_authenticated_chat_api_persists_and_returns_same_private_thread(self):
        from auth_utils import create_access_token
        from main import app

        buyer_token_payload = {
            "user_id": str(self.buyer_id),
            "token_version": 0,
        }
        farmer_token_payload = {
            "user_id": str(self.farmer_id),
            "token_version": 0,
        }
        outsider_token_payload = {
            "user_id": str(self.outsider_id),
            "token_version": 0,
        }
        await marketplace.save_buyer_profile(self.buyer_profile_data(), {
            "id": str(self.buyer_id),
            "role": "buyer",
        })
        listing = await marketplace.create_produce_listing(
            ProduceInput(
                crop="Tomato",
                category="Vegetables",
                quantity=10,
                unit="kg",
                price_per_unit=20,
                location="Pune",
            ),
            {"id": str(self.farmer_id), "role": "farmer"},
        )

        with patch.object(database.settings, "SECRET_KEY", "chat-api-test-secret-" * 3):
            buyer = {"Authorization": f"Bearer {create_access_token(buyer_token_payload)}"}
            farmer = {"Authorization": f"Bearer {create_access_token(farmer_token_payload)}"}
            outsider = {"Authorization": f"Bearer {create_access_token(outsider_token_payload)}"}
            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app=app),
                base_url="http://test",
            ) as client:
                order_response = await client.post(
                    f"/api/marketplace/produce/{listing['id']}/orders",
                    headers=buyer,
                    json=ListingOrderInput(
                        quantity=2,
                        delivery_location="Pune",
                        delivery_date=date.today() + timedelta(days=2),
                        idempotency_key=uuid4(),
                    ).model_dump(mode="json"),
                )
                self.assertEqual(order_response.status_code, 201, order_response.text)
                order_id = order_response.json()["id"]
                buyer_client_message_id = str(uuid4())
                buyer_payload = {
                    "message": "Hii 👋🌾",
                    "client_message_id": buyer_client_message_id,
                }

                buyer_send = await client.post(
                    f"/api/marketplace/orders/{order_id}/messages",
                    headers=buyer,
                    json=buyer_payload,
                )
                self.assertEqual(buyer_send.status_code, 201, buyer_send.text)
                duplicate_send = await client.post(
                    f"/api/marketplace/orders/{order_id}/messages",
                    headers=buyer,
                    json=buyer_payload,
                )
                self.assertEqual(duplicate_send.status_code, 201, duplicate_send.text)
                self.assertEqual(duplicate_send.json()["id"], buyer_send.json()["id"])
                farmer_send = await client.post(
                    f"/api/marketplace/orders/{order_id}/messages",
                    headers=farmer,
                    json={"message": "Hello 😊"},
                )
                self.assertEqual(farmer_send.status_code, 201, farmer_send.text)
                reply_send = await client.post(
                    f"/api/marketplace/orders/{order_id}/messages",
                    headers=buyer,
                    json={"message": "Thanks 👍", "reply_to_id": farmer_send.json()["id"]},
                )
                self.assertEqual(reply_send.status_code, 201, reply_send.text)
                self.assertEqual(reply_send.json()["reply_to_message"], "Hello 😊")

                buyer_history = await client.get(
                    f"/api/marketplace/orders/{order_id}/messages",
                    headers=buyer,
                )
                farmer_history = await client.get(
                    f"/api/marketplace/orders/{order_id}/messages",
                    headers=farmer,
                )
                self.assertEqual(buyer_history.status_code, 200, buyer_history.text)
                self.assertEqual(farmer_history.status_code, 200, farmer_history.text)
                buyer_rows = buyer_history.json()
                farmer_rows = farmer_history.json()
                self.assertEqual(
                    [row["id"] for row in buyer_rows],
                    [row["id"] for row in farmer_rows],
                )
                self.assertEqual([row["message"] for row in buyer_rows], ["Hii 👋🌾", "Hello 😊", "Thanks 👍"])
                self.assertEqual(buyer_rows[0]["sender_id"], str(self.buyer_id))
                self.assertEqual(buyer_rows[1]["sender_id"], str(self.farmer_id))
                self.assertEqual(buyer_rows[0]["receiver_id"], str(self.farmer_id))
                self.assertEqual(buyer_rows[1]["receiver_id"], str(self.buyer_id))
                self.assertEqual(buyer_rows[2]["reply_to_id"], farmer_send.json()["id"])

                conversations = await client.get("/api/marketplace/conversations", headers=buyer)
                self.assertEqual(conversations.status_code, 200, conversations.text)
                self.assertEqual(conversations.json()[0]["latest_message"]["message"], "Thanks 👍")
                self.assertEqual(conversations.json()[0]["counterpart_id"], str(self.farmer_id))

                delete_for_me = await client.request(
                    "DELETE",
                    f"/api/marketplace/orders/{order_id}/messages/{buyer_send.json()['id']}",
                    headers=buyer,
                    json={"scope": "me"},
                )
                self.assertEqual(delete_for_me.status_code, 200, delete_for_me.text)
                farmer_delete_own_denied = await client.request(
                    "DELETE",
                    f"/api/marketplace/orders/{order_id}/messages/{reply_send.json()['id']}",
                    headers=farmer,
                    json={"scope": "everyone"},
                )
                self.assertEqual(farmer_delete_own_denied.status_code, 403)
                outsider_delete = await client.request(
                    "DELETE",
                    f"/api/marketplace/orders/{order_id}/messages/{farmer_send.json()['id']}",
                    headers=outsider,
                    json={"scope": "me"},
                )
                self.assertEqual(outsider_delete.status_code, 404)

                delete_everywhere_message = await client.post(
                    f"/api/marketplace/orders/{order_id}/messages",
                    headers=farmer,
                    json={"message": "Remove this"},
                )
                delete_everywhere = await client.request(
                    "DELETE",
                    f"/api/marketplace/orders/{order_id}/messages/{delete_everywhere_message.json()['id']}",
                    headers=farmer,
                    json={"scope": "everyone"},
                )
                self.assertEqual(delete_everywhere.status_code, 200, delete_everywhere.text)
                buyer_after_delete = await client.get(
                    f"/api/marketplace/orders/{order_id}/messages", headers=buyer
                )
                farmer_after_delete = await client.get(
                    f"/api/marketplace/orders/{order_id}/messages", headers=farmer
                )
                self.assertEqual(buyer_after_delete.status_code, 200)
                self.assertEqual(farmer_after_delete.status_code, 200)
                self.assertEqual(len(buyer_after_delete.json()), 3)
                self.assertNotIn(buyer_send.json()["id"], [row["id"] for row in buyer_after_delete.json()])
                self.assertIn(buyer_send.json()["id"], [row["id"] for row in farmer_after_delete.json()])
                self.assertEqual(buyer_after_delete.json()[-1]["is_deleted"], True)
                self.assertEqual(buyer_after_delete.json()[-1]["message"], "")
                self.assertEqual(farmer_after_delete.json()[-1]["is_deleted"], True)

                outsider_history = await client.get(
                    f"/api/marketplace/orders/{order_id}/messages",
                    headers=outsider,
                )
                self.assertEqual(outsider_history.status_code, 404)

                persisted = await database.get_database()[
                    "marketplace_v2_messages"
                ].find({"order_id": ObjectId(order_id)}).to_list(10)
                self.assertEqual(len(persisted), 4)
                self.assertEqual([row["message"] for row in persisted[:3]], ["Hii 👋🌾", "Hello 😊", "Thanks 👍"])
                self.assertEqual(persisted[0]["receiver_id"], self.farmer_id)
                self.assertEqual(persisted[1]["receiver_id"], self.buyer_id)

    async def test_registration_persists_server_validated_role(self):
        original_connected = auth_routes.database_is_connected
        original_indexes = auth_routes.auth_indexes_ready
        original_token_creator = auth_routes.create_access_token
        auth_routes.database_is_connected = lambda: True
        auth_routes.auth_indexes_ready = lambda: True
        auth_routes.create_access_token = lambda data, expires_delta: "test-token"
        try:
            for index, role in enumerate(("buyer", "farmer")):
                payload = UserCreate(
                    full_name=f"New {role.title()}",
                    mobile=f"987654320{index}",
                    email=f"{role}@example.com",
                    password="safe-password-123",
                    role=role,
                )
                response = await auth_routes.register(payload)
                self.assertNotIn("token", response.model_dump())
                login_response = await auth_routes.login(
                    UserLogin(
                        mobile_or_email=payload.mobile,
                        password=payload.password,
                    )
                )
                saved = await get_user_collection().find_one(
                    {"mobile_normalized": payload.mobile}
                )
                self.assertEqual(response.role, role)
                self.assertEqual(login_response.role, role)
                self.assertEqual(saved["role"], role)
                self.assertNotEqual(saved["password"], payload.password)

                with self.assertRaises(HTTPException) as duplicate:
                    await auth_routes.register(payload)
                self.assertEqual(duplicate.exception.status_code, 409)
        finally:
            auth_routes.database_is_connected = original_connected
            auth_routes.auth_indexes_ready = original_indexes
            auth_routes.create_access_token = original_token_creator

        with self.assertRaises(ValidationError):
            UserCreate(
                full_name="Missing Role",
                mobile="9876543214",
                email="missing@example.com",
                password="safe-password-123",
            )
        with self.assertRaises(ValidationError):
            UserCreate(
                full_name="Invalid Role",
                mobile="9876543215",
                email="invalid@example.com",
                password="safe-password-123",
                role="admin",
            )
        with self.assertRaises(ValidationError):
            UserCreate(
                full_name="Weak Password",
                mobile="9876543216",
                email="weak@example.com",
                password="short",
                role="farmer",
            )


    async def test_login_token_restores_role_bound_user_session(self):
        original_connected = auth_routes.database_is_connected
        original_indexes = auth_routes.auth_indexes_ready
        auth_routes.database_is_connected = lambda: True
        auth_routes.auth_indexes_ready = lambda: True
        try:
            with patch.object(
                auth_routes.settings,
                "SECRET_KEY",
                "unit-test-auth-secret-that-is-long-enough",
            ):
                payload = UserCreate(
                    full_name="Session Test Farmer",
                    mobile="9876543217",
                    email="session-farmer@example.com",
                    password="SessionTestPass#2026",
                    role="farmer",
                )
                created = await auth_routes.register(payload)
                login_response = await auth_routes.login(
                    UserLogin(
                        mobile_or_email=payload.email,
                        password=payload.password,
                    )
                )
                from auth_utils import get_current_user

                restored = await get_current_user(token=login_response.token)
                self.assertEqual(restored["id"], created.id)
                self.assertEqual(restored["role"], "farmer")
                self.assertFalse(login_response.profile_complete)
                with self.assertRaises(HTTPException) as invalid_login:
                    await auth_routes.login(
                        UserLogin(
                            mobile_or_email=payload.email,
                            password="wrong-password",
                        )
                    )
                self.assertEqual(invalid_login.exception.status_code, 401)
                await auth_routes.logout(restored)
                with self.assertRaises(HTTPException) as revoked:
                    await get_current_user(token=login_response.token)
                self.assertEqual(revoked.exception.status_code, 401)
        finally:
            auth_routes.database_is_connected = original_connected
            auth_routes.auth_indexes_ready = original_indexes

    async def test_farmer_profile_api_requires_auth_and_returns_current_users_profile(self):
        from auth_utils import create_access_token
        from main import app

        user_id = ObjectId()
        await get_user_collection().insert_one({
            "_id": user_id,
            "full_name": "Authenticated Farmer",
            "mobile": "9876543299",
            "mobile_normalized": "9876543299",
            "role": "farmer",
            "profile_complete": True,
            "token_version": 0,
        })
        profile_data = {
            "user_id": user_id,
            "full_name": "Authenticated Farmer",
            "mobile": "9876543299",
            "location": {
                "state": "Maharashtra",
                "district": "Pune",
                "taluka": "Haveli",
                "village": "Test Village",
                "latitude": 18.52,
                "longitude": 73.85,
            },
            "farming": {
                "crop": "Tomato",
                "crops": ["Tomato"],
                "variety": "Local",
                "stage": "Flowering",
                "land_area": 1,
                "land_unit": "Acres",
                "soil_type": "Black",
                "irrigation": "Drip",
            },
        }

        with patch.object(
            database.settings,
            "SECRET_KEY",
            "farmer-profile-api-test-secret-" * 2,
        ):
            token = create_access_token({
                "user_id": str(user_id),
                "token_version": 0,
            })
            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app=app),
                base_url="http://test",
            ) as client:
                unauthenticated = await client.get("/api/farmer/profile")
                self.assertEqual(unauthenticated.status_code, 401)

                headers = {"Authorization": f"Bearer {token}"}
                account = await client.get("/api/auth/me", headers=headers)
                self.assertEqual(account.status_code, 200, account.text)
                self.assertEqual(account.json()["id"], str(user_id))

                missing_profile = await client.get(
                    "/api/farmer/profile",
                    headers=headers,
                )
                self.assertEqual(missing_profile.status_code, 404)
                self.assertIn("profile not found", missing_profile.json()["detail"])

                await get_farmer_profile_collection().insert_one(profile_data)
                profile = await client.get("/api/farmer/profile", headers=headers)

        self.assertEqual(profile.status_code, 200, profile.text)
        self.assertEqual(profile.json()["user_id"], str(user_id))
        self.assertEqual(profile.json()["full_name"], "Authenticated Farmer")
        self.assertEqual(profile.json()["mobile"], "9876543299")

    async def test_registered_buyer_can_login_and_load_dashboard_without_profile(self):
        original_connected = auth_routes.database_is_connected
        original_indexes = auth_routes.auth_indexes_ready
        auth_routes.database_is_connected = lambda: True
        auth_routes.auth_indexes_ready = lambda: True
        try:
            from main import app

            with patch.object(
                auth_routes.settings,
                "SECRET_KEY",
                "unit-test-buyer-dashboard-secret-that-is-long-enough",
            ):
                async with httpx.AsyncClient(
                    transport=httpx.ASGITransport(app=app),
                    base_url="http://test",
                ) as client:
                    farmer_payload = {
                        "full_name": "Fresh Farmer",
                        "mobile": "9876543217",
                        "email": "fresh-farmer@example.com",
                        "password": "FarmerPass#2026",
                        "role": "farmer",
                    }
                    farmer_registration = await client.post(
                        "/api/auth/register",
                        json=farmer_payload,
                    )
                    self.assertEqual(
                        farmer_registration.status_code,
                        201,
                        farmer_registration.text,
                    )
                    self.assertEqual(farmer_registration.json()["role"], "farmer")

                    duplicate_buyer = await client.post(
                        "/api/auth/register",
                        json={
                            **farmer_payload,
                            "full_name": "Buyer Using Farmer Number",
                            "email": "buyer-duplicate@example.com",
                            "role": "buyer",
                        },
                    )
                    self.assertEqual(duplicate_buyer.status_code, 409)
                    self.assertIn(
                        "already belongs to an account",
                        duplicate_buyer.json()["detail"],
                    )

                    farmer_login = await client.post(
                        "/api/auth/login",
                        json={
                            "mobile_or_email": farmer_payload["mobile"],
                            "password": farmer_payload["password"],
                        },
                    )
                    self.assertEqual(farmer_login.status_code, 200, farmer_login.text)
                    self.assertEqual(farmer_login.json()["role"], "farmer")
                    farmer_headers = {
                        "Authorization": f"Bearer {farmer_login.json()['token']}"
                    }
                    farmer_account = await client.get(
                        "/api/auth/me",
                        headers=farmer_headers,
                    )
                    self.assertEqual(farmer_account.status_code, 200)
                    self.assertEqual(farmer_account.json()["role"], "farmer")
                    farmer_dashboard = await client.get(
                        "/api/marketplace/dashboard",
                        headers=farmer_headers,
                    )
                    self.assertEqual(farmer_dashboard.status_code, 200)
                    self.assertEqual(farmer_dashboard.json()["role"], "farmer")
                    self.assertTrue(farmer_dashboard.json()["is_farmer"])
                    self.assertFalse(farmer_dashboard.json()["is_buyer"])
                    farmer_buyer_profile = await client.get(
                        "/api/marketplace/profile",
                        headers=farmer_headers,
                    )
                    self.assertEqual(farmer_buyer_profile.status_code, 403)

                    payload = {
                        "full_name": "Fresh Buyer",
                        "mobile": "9876543218",
                        "email": "fresh-buyer@example.com",
                        "password": "BuyerPass#2026",
                        "role": "buyer",
                    }
                    registration = await client.post(
                        "/api/auth/register",
                        json=payload,
                    )
                    self.assertEqual(registration.status_code, 201, registration.text)
                    self.assertEqual(registration.json()["role"], "buyer")
                    self.assertNotIn("token", registration.json())

                    login = await client.post(
                        "/api/auth/login",
                        json={
                            "mobile_or_email": payload["email"],
                            "password": payload["password"],
                        },
                    )
                    self.assertEqual(login.status_code, 200, login.text)
                    self.assertEqual(login.json()["id"], registration.json()["id"])
                    self.assertEqual(login.json()["role"], "buyer")

                    authorization = {
                        "Authorization": f"Bearer {login.json()['token']}"
                    }
                    account = await client.get(
                        "/api/auth/me",
                        headers=authorization,
                    )
                    self.assertEqual(account.status_code, 200, account.text)
                    self.assertEqual(account.json()["role"], "buyer")

                    dashboard = await client.get(
                        "/api/marketplace/dashboard",
                        headers=authorization,
                    )
                    self.assertEqual(dashboard.status_code, 200, dashboard.text)
                    self.assertEqual(dashboard.json()["role"], "buyer")
                    self.assertTrue(dashboard.json()["is_buyer"])
                    self.assertFalse(dashboard.json()["is_farmer"])

                    buyer_profile = await client.get(
                        "/api/marketplace/profile",
                        headers=authorization,
                    )
                    self.assertEqual(buyer_profile.status_code, 404)
                    saved_buyer_profile = await client.put(
                        "/api/marketplace/profile",
                        headers=authorization,
                        json={
                            "full_name": "Fresh Buyer",
                            "business_name": "Fresh Buyer Shop",
                            "buyer_type": "Retailer",
                            "crop_preferences": ["Tomato"],
                            "phone": "9876543218",
                            "whatsapp": "9876543218",
                            "email": "fresh-buyer@example.com",
                            "delivery_location": "Pune",
                        },
                    )
                    self.assertEqual(
                        saved_buyer_profile.status_code,
                        200,
                        saved_buyer_profile.text,
                    )
                    self.assertEqual(
                        saved_buyer_profile.json()["business_name"],
                        "Fresh Buyer Shop",
                    )
                    loaded_buyer_profile = await client.get(
                        "/api/marketplace/profile",
                        headers=authorization,
                    )
                    self.assertEqual(loaded_buyer_profile.status_code, 200)
                    self.assertEqual(
                        loaded_buyer_profile.json()["business_name"],
                        "Fresh Buyer Shop",
                    )

                    profile = await get_buyer_profile_collection().find_one(
                        {"user_id": ObjectId(registration.json()["id"])}
                    )
                    self.assertEqual(profile["business_name"], "Fresh Buyer Shop")

                    await client.post("/api/auth/logout", headers=authorization)
                    denied = await client.get(
                        "/api/marketplace/dashboard",
                        headers=authorization,
                    )
                    self.assertEqual(denied.status_code, 401)
        finally:
            auth_routes.database_is_connected = original_connected
            auth_routes.auth_indexes_ready = original_indexes


if __name__ == "__main__":
    unittest.main()
