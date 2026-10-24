from datetime import date
from typing import Literal
from uuid import UUID
from urllib.parse import urlsplit

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from normalization import normalize_email, normalize_mobile


class BuyerProfileInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    full_name: str = Field(min_length=2, max_length=100)
    business_name: str = Field(default="", max_length=120)
    buyer_type: Literal["Individual", "Retailer", "Wholesaler", "Restaurant", "Distributor", "Other"]
    crop_preferences: list[str] = Field(min_length=1, max_length=25)
    phone: str
    whatsapp: str
    email: str = ""
    delivery_location: str = Field(min_length=2, max_length=180)
    address: str = Field(default="", max_length=500)
    additional_info: str = Field(default="", max_length=1500)

    @field_validator("full_name", "delivery_location")
    @classmethod
    def strip_required_text(cls, value: str) -> str:
        cleaned = value.strip()
        if len(cleaned) < 2:
            raise ValueError("Enter at least two characters.")
        return cleaned

    @field_validator("business_name", "address", "additional_info")
    @classmethod
    def strip_optional_text(cls, value: str) -> str:
        return value.strip()

    @field_validator("crop_preferences")
    @classmethod
    def clean_preferences(cls, values: list[str]) -> list[str]:
        cleaned = list(dict.fromkeys(item.strip() for item in values if item.strip()))
        if not cleaned:
            raise ValueError("Add at least one crop or vegetable preference.")
        return cleaned

    @field_validator("phone", "whatsapp")
    @classmethod
    def validate_phone(cls, value: str) -> str:
        try:
            return normalize_mobile(value)
        except ValueError as exc:
            raise ValueError("Enter a valid phone number.") from exc

    @field_validator("email")
    @classmethod
    def validate_email(cls, value: str) -> str:
        if not value.strip():
            return ""
        try:
            return normalize_email(value)
        except ValueError as exc:
            raise ValueError("Enter a valid email address.") from exc


class RequirementInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    crop: str = Field(min_length=2, max_length=100)
    category: Literal["Vegetables", "Fruits", "Grains", "Pulses", "Other"]
    quantity: float = Field(gt=0, le=1_000_000_000)
    unit: Literal["kg", "quintal", "tonne"]
    expected_price_per_unit: float = Field(gt=0, le=1_000_000_000)
    delivery_location: str = Field(min_length=2, max_length=180)
    delivery_date: date
    quality_preferences: str = Field(default="", max_length=500)
    description: str = Field(default="", max_length=2000)

    @field_validator("crop", "delivery_location")
    @classmethod
    def trim_required_requirement_text(cls, value: str) -> str:
        cleaned = value.strip()
        if len(cleaned) < 2:
            raise ValueError("Enter at least two characters.")
        return cleaned

    @field_validator("quality_preferences", "description")
    @classmethod
    def trim_optional_requirement_text(cls, value: str) -> str:
        return value.strip()

    @field_validator("delivery_date")
    @classmethod
    def require_future_date(cls, value: date) -> date:
        if value < date.today():
            raise ValueError("Delivery date cannot be in the past.")
        return value


class OfferInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    quantity: float = Field(gt=0, le=1_000_000_000)
    price_per_unit: float = Field(gt=0, le=1_000_000_000)
    message: str = Field(default="", max_length=1500)
    delivery_date: date

    @field_validator("message")
    @classmethod
    def trim_message(cls, value: str) -> str:
        return value.strip()

    @field_validator("delivery_date")
    @classmethod
    def require_future_date(cls, value: date) -> date:
        if value < date.today():
            raise ValueError("Delivery date cannot be in the past.")
        return value


class ProduceInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    crop: str = Field(min_length=2, max_length=100)
    category: Literal["Vegetables", "Fruits", "Grains", "Pulses", "Other"]
    quantity: float = Field(ge=0, le=1_000_000_000)
    unit: Literal["kg", "quintal", "tonne"]
    price_per_unit: float = Field(ge=0, le=1_000_000_000)
    location: str = Field(min_length=2, max_length=180)
    description: str = Field(default="", max_length=1200)
    image_url: str = Field(default="", max_length=1000)
    min_order_quantity: float | None = Field(default=None, gt=0, le=1_000_000_000)
    available_from: date | None = None
    publish: bool = True

    @model_validator(mode="after")
    def validate_publishable_listing(self):
        if self.publish and (self.quantity <= 0 or self.price_per_unit <= 0):
            raise ValueError("Price and available quantity must be greater than zero to publish.")
        if self.min_order_quantity is not None and self.quantity > 0 and self.min_order_quantity > self.quantity:
            raise ValueError("Minimum order quantity cannot exceed available quantity.")
        return self

    @field_validator("crop", "location")
    @classmethod
    def trim_required_produce_text(cls, value: str) -> str:
        cleaned = value.strip()
        if len(cleaned) < 2:
            raise ValueError("Enter at least two characters.")
        return cleaned

    @field_validator("description")
    @classmethod
    def trim_produce_description(cls, value: str) -> str:
        return value.strip()

    @field_validator("image_url")
    @classmethod
    def validate_image_url(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            return ""
        parsed = urlsplit(cleaned)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ValueError("Image URL must use HTTP or HTTPS.")
        return cleaned


class MarketplaceMessageInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    message: str = Field(min_length=1, max_length=2000)
    client_message_id: UUID | None = None
    reply_to_id: str | None = Field(default=None, max_length=24)

    @field_validator("message")
    @classmethod
    def require_nonempty_message(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("Message cannot be empty.")
        return cleaned


class MarketplaceMessageDeleteInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    scope: Literal["me", "everyone"]


class ListingOrderInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    quantity: float = Field(gt=0, le=1_000_000_000)
    delivery_location: str = Field(min_length=2, max_length=180)
    delivery_address: str = Field(default="", max_length=500)
    delivery_date: date
    message: str = Field(default="", max_length=1500)
    idempotency_key: UUID

    @field_validator("delivery_location", "delivery_address", "message")
    @classmethod
    def trim_order_text(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned and value:
            return ""
        return cleaned

    @field_validator("delivery_location")
    @classmethod
    def validate_delivery_location(cls, value: str) -> str:
        if len(value.strip()) < 2:
            raise ValueError("Enter a delivery location.")
        return value.strip()

    @field_validator("delivery_date")
    @classmethod
    def require_future_delivery_date(cls, value: date) -> date:
        if value < date.today():
            raise ValueError("Delivery date cannot be in the past.")
        return value


class FarmerOrderRequestInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    crop: str = Field(min_length=2, max_length=100)
    quantity: float = Field(gt=0, le=1_000_000_000)
    unit: Literal["kg", "quintal", "tonne"]
    price_per_unit: float = Field(gt=0, le=1_000_000_000)
    delivery_location: str = Field(min_length=2, max_length=180)
    delivery_date: date
    message: str = Field(default="", max_length=1500)
    listing_id: str | None = None
    idempotency_key: UUID

    @field_validator("crop", "delivery_location")
    @classmethod
    def trim_required_order_request_text(cls, value: str) -> str:
        cleaned = value.strip()
        if len(cleaned) < 2:
            raise ValueError("Enter at least two characters.")
        return cleaned

    @field_validator("message")
    @classmethod
    def trim_order_request_message(cls, value: str) -> str:
        return value.strip()

    @field_validator("delivery_date")
    @classmethod
    def require_future_order_request_date(cls, value: date) -> date:
        if value < date.today():
            raise ValueError("Delivery date cannot be in the past.")
        return value
