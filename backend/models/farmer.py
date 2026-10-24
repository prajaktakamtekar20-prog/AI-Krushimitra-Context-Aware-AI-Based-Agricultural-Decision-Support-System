import json
from pathlib import Path
from pydantic import BaseModel, Field, field_validator
from typing import Optional, Literal
from datetime import datetime
from urllib.parse import urlsplit
from normalization import normalize_email, normalize_mobile


PLANTVILLAGE_CROPS = (
    "Apple",
    "Blueberry",
    "Cherry",
    "Corn (Maize)",
    "Grape",
    "Orange",
    "Peach",
    "Bell Pepper",
    "Potato",
    "Raspberry",
    "Soybean",
    "Squash",
    "Strawberry",
    "Tomato",
)


def _crop_key(value: str) -> str:
    return " ".join(
        value.strip().lower().replace("(", "").replace(")", "").replace("_", " ").replace("-", " ").split()
    )


CROP_MASTER = json.loads(
    (Path(__file__).resolve().parents[2] / "shared" / "crops.json").read_text(encoding="utf-8")
)
_CROP_NAMES_BY_KEY = {}
for category in CROP_MASTER:
    for crop in category["crops"]:
        for name in (crop["value"], crop["label"], *crop.get("aliases", [])):
            _CROP_NAMES_BY_KEY[_crop_key(name)] = crop["value"]


def normalize_plantvillage_crop(value: object) -> str:
    if not isinstance(value, str):
        raise ValueError("Crop must be a crop name.")
    crop = value.strip()
    if not crop:
        raise ValueError("Crop must not be blank.")
    return _CROP_NAMES_BY_KEY.get(_crop_key(crop), crop)


def _validate_public_image_url(value: Optional[str]) -> Optional[str]:
    if value is None or not value.strip():
        return None
    parsed = urlsplit(value.strip())
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError("Image URL must use HTTP or HTTPS.")
    return value.strip()


class UserCreate(BaseModel):
    full_name: str = Field(..., min_length=2, max_length=100)
    mobile: str = Field(..., min_length=10, max_length=15)
    email: Optional[str] = Field(None, min_length=5, max_length=254)
    password: str = Field(..., min_length=8, max_length=128)
    role: Literal["farmer", "buyer"]

    @field_validator("full_name")
    @classmethod
    def validate_full_name(cls, value: str) -> str:
        name = value.strip()
        if len(name) < 2:
            raise ValueError("Enter your name.")
        return name

    @field_validator("mobile", mode="before")
    @classmethod
    def validate_mobile(cls, value: object) -> str:
        if not isinstance(value, str):
            raise ValueError("Enter a valid mobile number.")
        return normalize_mobile(value)

    @field_validator("email", mode="before")
    @classmethod
    def validate_email(cls, value: object) -> Optional[str]:
        if value is None or (isinstance(value, str) and not value.strip()):
            return None
        if not isinstance(value, str):
            raise ValueError("Enter a valid email address.")
        return normalize_email(value)

    @field_validator("password")
    @classmethod
    def validate_password_bytes(cls, value: str) -> str:
        if len(value.encode("utf-8")) > 72:
            raise ValueError("Password must be 72 bytes or fewer.")
        return value


class UserLogin(BaseModel):
    mobile_or_email: str = Field(..., min_length=3, max_length=254)
    password: str = Field(..., min_length=1, max_length=128)


class GoogleLogin(BaseModel):
    code: str = Field(..., min_length=20, max_length=4096)
    redirect_uri: str = Field(..., min_length=8, max_length=500)


class UserResponse(BaseModel):
    id: str
    full_name: str
    mobile: str = ""
    email: Optional[str] = None
    token: str
    profile_complete: bool = False
    role: Literal["farmer", "buyer"]


class UserRegistrationResponse(BaseModel):
    id: str
    full_name: str
    mobile: str = ""
    email: Optional[str] = None
    profile_complete: bool = False
    role: Literal["farmer", "buyer"]


class LocationModel(BaseModel):
    state: str = Field(..., min_length=2)
    district: str = Field(..., min_length=2)
    taluka: str = Field(..., min_length=2)
    village: str = Field(..., min_length=2)
    latitude: float = Field(..., ge=-90.0, le=90.0)
    longitude: float = Field(..., ge=-180.0, le=180.0)


class FarmingModel(BaseModel):
    crop: str = Field(..., min_length=2)
    crops: list[str] = Field(default_factory=list, max_length=40)
    variety: str = Field(..., min_length=1)
    stage: str = Field(..., min_length=2)
    land_area: float = Field(..., gt=0)
    land_unit: Literal["Acres", "Hectares"]
    soil_type: str = Field(..., min_length=2)
    irrigation: str = Field(..., min_length=2)

    @field_validator("crop", mode="before")
    @classmethod
    def normalize_crop(cls, value: object) -> str:
        return normalize_plantvillage_crop(value)

    @field_validator("crops", mode="before")
    @classmethod
    def normalize_crops(cls, value: object) -> list[str]:
        if value is None:
            return []
        if not isinstance(value, list):
            raise ValueError("Crops must be a list of crop names.")
        unique_crops = {}
        for entry in value:
            crop = normalize_plantvillage_crop(entry)
            if len(crop) > 80:
                raise ValueError("Crop names must be 80 characters or fewer.")
            unique_crops.setdefault(_crop_key(crop), crop)
        return list(unique_crops.values())


class SchemeProfileModel(BaseModel):
    """Optional eligibility fields used only for government scheme matching."""
    gender: Optional[str] = None
    age: Optional[int] = Field(None, ge=18, le=120)
    farmer_category: Optional[str] = None
    land_tenure: Optional[str] = None
    activities: Optional[list[str]] = None
    annual_income_band: Optional[str] = None
    already_beneficiary: Optional[bool] = None


class FarmerProfileCreate(BaseModel):
    full_name: str = Field(..., min_length=2)
    mobile: str = Field(..., min_length=10)
    location: LocationModel
    farming: FarmingModel
    discoverable: bool = False
    profile_photo_url: Optional[str] = Field(None, max_length=1000)
    scheme_profile: Optional[SchemeProfileModel] = None

    @field_validator("profile_photo_url")
    @classmethod
    def validate_profile_photo_url(cls, value: Optional[str]) -> Optional[str]:
        return _validate_public_image_url(value)

    @field_validator("mobile", mode="before")
    @classmethod
    def validate_mobile(cls, value: object) -> str:
        if not isinstance(value, str):
            raise ValueError("Enter a valid mobile number.")
        return normalize_mobile(value)


class FarmerProfileUpdate(BaseModel):
    full_name: Optional[str] = Field(None, min_length=2)
    mobile: Optional[str] = Field(None, min_length=10)
    location: Optional[LocationModel] = None
    farming: Optional[FarmingModel] = None
    discoverable: Optional[bool] = None
    profile_photo_url: Optional[str] = Field(None, max_length=1000)
    scheme_profile: Optional[SchemeProfileModel] = None

    @field_validator("profile_photo_url")
    @classmethod
    def validate_profile_photo_url(cls, value: Optional[str]) -> Optional[str]:
        return _validate_public_image_url(value)

    @field_validator("mobile", mode="before")
    @classmethod
    def validate_mobile(cls, value: object) -> str:
        if value is None:
            return value
        if not isinstance(value, str):
            raise ValueError("Enter a valid mobile number.")
        return normalize_mobile(value)


class FarmerProfileResponse(BaseModel):
    id: str
    user_id: str
    full_name: str
    mobile: str
    location: LocationModel
    farming: FarmingModel
    discoverable: bool = False
    profile_photo_url: Optional[str] = None
    scheme_profile: Optional[SchemeProfileModel] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
