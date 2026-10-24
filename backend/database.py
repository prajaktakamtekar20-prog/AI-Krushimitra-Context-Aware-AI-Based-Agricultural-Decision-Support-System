import os
import logging
from pathlib import Path
from pydantic_settings import BaseSettings
from dotenv import dotenv_values, load_dotenv
from typing import Optional, Any, List, Dict
import copy
import uuid
import time as _time
from urllib.parse import urlsplit
from pymongo.errors import PyMongoError

logger = logging.getLogger(__name__)
BACKEND_ENV_PATH = Path(__file__).resolve().with_name(".env")
_file_gemini_key = (dotenv_values(BACKEND_ENV_PATH).get("GEMINI_API_KEY") or "").strip()
_process_gemini_key = (os.getenv("GEMINI_API_KEY") or "").strip()
if _file_gemini_key and _process_gemini_key and _file_gemini_key != _process_gemini_key:
    logger.warning(
        "GEMINI_API_KEY differs between backend/.env and the process environment; "
        "backend/.env will be used. Key values are not logged."
    )
load_dotenv(dotenv_path=BACKEND_ENV_PATH, override=True)


class Settings(BaseSettings):
    MONGODB_URI: str = os.getenv("MONGODB_URI", "mongodb://localhost:27017")
    DATABASE_NAME: str = os.getenv("DATABASE_NAME", "ai_krushimitra")
    SECRET_KEY: str = os.getenv("SECRET_KEY", "")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "10080"))
    CORS_ORIGINS: str = os.getenv("CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173,http://localhost:3000,http://localhost:5174")
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
    GROQ_API_KEY: str = os.getenv("GROQ_API_KEY", "")
    GROQ_MODEL: str = os.getenv("GROQ_MODEL", "")
    GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")
    GEMINI_MODEL: str = (
        os.getenv("GEMINI_MODEL")
        or os.getenv("GEMINI_VISION_MODEL")
        or os.getenv("GEMINI_CHAT_MODEL")
        or "gemini-3.8-flash"
    )
    GEMINI_CHAT_MODEL: str = os.getenv("GEMINI_CHAT_MODEL", "gemini-flash-latest")
    GEMINI_VISION_MODEL: str = os.getenv("GEMINI_VISION_MODEL", "gemini-3.8-flash")
    DATA_GOV_API_KEY: str = os.getenv("DATA_GOV_API_KEY", "")
    GOOGLE_CLIENT_ID: str = os.getenv("GOOGLE_CLIENT_ID", "")
    GOOGLE_CLIENT_SECRET: str = os.getenv("GOOGLE_CLIENT_SECRET", "")
    GOOGLE_REDIRECT_URI: str = os.getenv("GOOGLE_REDIRECT_URI", "http://localhost:5173")
    ALGORITHM: str = "HS256"

    class Config:
        env_file = str(BACKEND_ENV_PATH)


settings = Settings()

try:
    from motor.motor_asyncio import AsyncIOMotorClient
    _MOTOR_AVAILABLE = True
except Exception:
    AsyncIOMotorClient = None  # type: ignore
    _MOTOR_AVAILABLE = False


try:
    from bson import ObjectId
except Exception:
    class ObjectId:
        def __init__(self, oid=None):
            if oid is None:
                self._id = uuid.uuid4().hex[:24]
            else:
                self._id = str(oid)
        def __str__(self):
            return self._id
        def __repr__(self):
            return "ObjectId('" + self._id + "')"
        def __eq__(self, other):
            if isinstance(other, ObjectId):
                return self._id == other._id
            return str(self._id) == str(other)
        def __hash__(self):
            return hash(self._id)


_client = None  # Optional[AsyncIOMotorClient]


_use_memory_fallback = False
_auth_indexes_ready = False
_memory_db: Dict[str, List[Dict[str, Any]]] = {}
_memory_indexes: Dict[str, set] = {}


def _oid(s):
    if isinstance(s, ObjectId):
        return s
    try:
        return ObjectId(s)
    except Exception:
        return None


class _MemoryCollection:
    def __init__(self, name):
        self.name = name
        if name not in _memory_db:
            _memory_db[name] = []
        if name not in _memory_indexes:
            _memory_indexes[name] = set()

    async def create_index(self, keys, unique=False, sparse=False, **kwargs):
        return None

    def _matches(self, doc, query):
        if not query:
            return True
        for k, v in query.items():
            if k == "_id":
                if isinstance(v, dict) and "$in" in v:
                    oids = []
                    for it in v["$in"]:
                        oids.append(str(_oid(it)))
                    if str(doc.get("_id")) not in oids:
                        return False
                    continue
                docv = doc.get("_id")
                if str(docv) != str(_oid(v)):
                    return False
                continue
            if isinstance(v, dict):
                if "$in" in v:
                    if doc.get(k) not in v["$in"]:
                        return False
                    continue
                if "$gte" in v and (doc.get(k) is None or doc.get(k) < v["$gte"]):
                    return False
                if "$gt" in v and (doc.get(k) is None or doc.get(k) <= v["$gt"]):
                    return False
                if "$lte" in v and (doc.get(k) is None or doc.get(k) > v["$lte"]):
                    return False
                if "$lt" in v and (doc.get(k) is None or doc.get(k) >= v["$lt"]):
                    return False
                if "$ne" in v:
                    if doc.get(k) == v["$ne"]:
                        return False
                    continue
                if "$exists" in v:
                    exists = k in doc and doc[k] is not None
                    want = bool(v["$exists"])
                    if exists != want:
                        return False
                    continue
                continue
            if isinstance(v, str) and k.endswith(".user_id"):
                dk = doc
                for part in k.split("."):
                    if isinstance(dk, dict):
                        dk = dk.get(part)
                    else:
                        dk = None
                if str(dk) != v:
                    return False
                continue
            # dot-path drill
            if "." in k:
                parts = k.split(".")
                dk = doc
                ok = True
                for part in parts:
                    if isinstance(dk, dict):
                        dk = dk.get(part)
                    else:
                        ok = False
                        break
                if not ok or dk != v:
                    return False
                continue
            if doc.get(k) != v:
                return False
        return True

    async def insert_one(self, doc):
        d = copy.deepcopy(doc)
        if "_id" not in d or d["_id"] is None:
            d["_id"] = ObjectId()
        d["_id"] = ObjectId(d["_id"]) if not isinstance(d["_id"], ObjectId) else d["_id"]
        _memory_db[self.name].append(d)
        class _R:
            inserted_id = d["_id"]
        return _R()

    async def insert_many(self, docs):
        ids = []
        for d in docs:
            r = await self.insert_one(d)
            ids.append(r.inserted_id)
        class _R:
            inserted_ids = ids
        return _R()

    async def find_one(self, query, projection=None):
        for d in _memory_db[self.name]:
            if self._matches(d, query or {}):
                out = copy.deepcopy(d)
                if projection:
                    keep = [k for k, v in projection.items() if v]
                    if keep:
                        out = {k: out[k] for k in keep if k in out}
                        if "_id" not in out and "_id" in d:
                            out["_id"] = copy.deepcopy(d["_id"])
                return out
        return None

    def find(self, query=None, projection=None, sort=None, limit=0, skip=0):
        query = query or {}
        results = []
        for d in _memory_db[self.name]:
            if self._matches(d, query):
                results.append(copy.deepcopy(d))
        if sort:
            def sort_key(d):
                keys = []
                for sk, sd in (sort or []):
                    # simple single level
                    v = d.get(sk)
                    keys.append(v if v is not None else "")
                return tuple(keys)
            results.sort(key=sort_key, reverse=(len(sort) > 0 and sort[0][1] == -1))
        if skip:
            results = results[skip:]
        if limit:
            results = results[:limit]
        class _Cursor:
            def __init__(self, items):
                self._items = list(items)
                self._idx = 0
            async def to_list(self, length=None):
                if length:
                    return self._items[:length]
                return list(self._items)
            def __aiter__(self):
                return self
            async def __anext__(self):
                if self._idx >= len(self._items):
                    raise StopAsyncIteration
                item = self._items[self._idx]
                self._idx += 1
                return item
            def sort(self, *args, **kwargs):
                return self
            def limit(self, *args, **kwargs):
                return self
            def skip(self, *args, **kwargs):
                return self
        return _Cursor(results)

    async def count_documents(self, query=None):
        query = query or {}
        c = 0
        for d in _memory_db[self.name]:
            if self._matches(d, query):
                c += 1
        return c

    async def update_one(self, query, update, upsert=False):
        matched = 0
        modified = 0
        upserted_id = None
        for i, d in enumerate(_memory_db[self.name]):
            if self._matches(d, query or {}):
                matched = 1
                new = copy.deepcopy(d)
                if "$set" in update:
                    for k, v in update["$set"].items():
                        self._set_path(new, k, v)
                if "$unset" in update:
                    for k in update["$unset"]:
                        self._unset_path(new, k)
                if "$push" in update:
                    for k, v in update["$push"].items():
                        cur = new.get(k, [])
                        if not isinstance(cur, list):
                            cur = []
                        cur.append(v)
                        new[k] = cur
                if "$inc" in update:
                    for k, v in update["$inc"].items():
                        new[k] = (new.get(k) or 0) + v
                if new != d:
                    modified = 1
                _memory_db[self.name][i] = new
                break
        if matched == 0 and upsert:
            doc = {}
            if "$set" in update:
                for k, v in update["$set"].items():
                    self._set_path(doc, k, v)
            # copy query values to doc
            for k, v in (query or {}).items():
                if not isinstance(v, dict):
                    doc.setdefault(k, v)
            r = await self.insert_one(doc)
            upserted_id = r.inserted_id
            matched = 1
        return type("_R", (), {
            "matched_count": matched,
            "modified_count": modified,
            "upserted_id": upserted_id,
        })()

    async def update_many(self, query, update):
        matched = 0
        modified = 0
        for i, d in enumerate(_memory_db[self.name]):
            if self._matches(d, query or {}):
                matched += 1
                new = copy.deepcopy(d)
                if "$set" in update:
                    for k, v in update["$set"].items():
                        self._set_path(new, k, v)
                if "$push" in update:
                    for k, v in update["$push"].items():
                        cur = new.get(k, [])
                        if not isinstance(cur, list):
                            cur = []
                        cur.append(v)
                        new[k] = cur
                if new != d:
                    modified += 1
                _memory_db[self.name][i] = new
        class _R:
            matched_count = matched
            modified_count = modified
        return _R()

    async def delete_one(self, query):
        query = query or {}
        for i, d in enumerate(_memory_db[self.name]):
            if self._matches(d, query):
                del _memory_db[self.name][i]
                class _R:
                    deleted_count = 1
                return _R()
        class _R:
            deleted_count = 0
        return _R()

    async def delete_many(self, query):
        query = query or {}
        kept = []
        deleted = 0
        for d in _memory_db[self.name]:
            if self._matches(d, query):
                deleted += 1
            else:
                kept.append(d)
        _memory_db[self.name] = kept
        class _R:
            deleted_count = deleted
        return _R()

    async def distinct(self, key, query=None):
        query = query or {}
        values = set()
        for d in _memory_db[self.name]:
            if self._matches(d, query):
                v = d.get(key)
                if v is not None:
                    if isinstance(v, list):
                        for it in v:
                            values.add(it)
                    else:
                        values.add(v)
        return list(values)

    def _set_path(self, d, path, v):
        parts = path.split(".")
        cur = d
        for p in parts[:-1]:
            if p not in cur or not isinstance(cur[p], dict):
                cur[p] = {}
            cur = cur[p]
        cur[parts[-1]] = v

    def _unset_path(self, d, path):
        parts = path.split(".")
        cur = d
        for p in parts[:-1]:
            if p not in cur or not isinstance(cur[p], dict):
                return
            cur = cur[p]
        if parts[-1] in cur:
            del cur[parts[-1]]


class _MemoryDatabase:
    def __init__(self):
        self._collections = {}

    def __getitem__(self, name):
        if name not in self._collections:
            self._collections[name] = _MemoryCollection(name)
        return self._collections[name]

    async def command(self, cmd=None):
        if cmd == "ping":
            return {"ok": 1, "in_memory": True}
        return {"ok": 1}

    async def create_collection(self, name, **kwargs):
        return self[name]


_mem_db = None


def _get_mem_db():
    global _mem_db, _use_memory_fallback
    if _mem_db is None:
        _mem_db = _MemoryDatabase()
    return _mem_db


async def connect_to_mongo():
    global _client, _use_memory_fallback, _auth_indexes_ready
    _use_memory_fallback = False
    if not _MOTOR_AVAILABLE:
        logger.error("Motor is unavailable; MongoDB-backed requests cannot proceed.")
        return
    candidate = AsyncIOMotorClient(settings.MONGODB_URI, serverSelectionTimeoutMS=3000)
    try:
        await candidate.admin.command("ping")
        _client = candidate
        logger.info("Connected to MongoDB successfully.")
    except PyMongoError as exc:
        candidate.close()
        _client = None
        _auth_indexes_ready = False
        try:
            uri_parts = urlsplit(settings.MONGODB_URI)
            host = uri_parts.hostname or "unknown"
            port = uri_parts.port or "default"
            target = f"{host}:{port}"
        except ValueError:
            target = "invalid configured MongoDB URI"
        logger.error(
            "Failed to connect to MongoDB (%s) at %s; authentication and persistence "
            "are unavailable. The API will retry the connection.",
            type(exc).__name__,
            target,
        )


async def close_mongo_connection():
    global _client
    if _client:
        _client.close()
        _client = None
        logger.info("MongoDB connection closed.")


def get_database():
    if _client is not None:
        return _client[settings.DATABASE_NAME]
    raise RuntimeError("MongoDB is unavailable. Verify MONGODB_URI and ensure MongoDB is running.")


def auth_indexes_ready() -> bool:
    return _auth_indexes_ready


def database_is_connected() -> bool:
    return _client is not None


def _normalized_email(value: Any) -> str | None:
    if not isinstance(value, str) or not value.strip():
        return None
    return value.strip().lower()


def _normalized_mobile(value: Any) -> str | None:
    if not isinstance(value, str) or not value.strip():
        return None
    digits = "".join(character for character in value if character.isdigit())
    if len(digits) == 12 and digits.startswith("91"):
        digits = digits[2:]
    elif len(digits) == 11 and digits.startswith("0"):
        digits = digits[1:]
    return digits if len(digits) == 10 else None


async def _migrate_auth_identifiers(users) -> bool:
    documents = await users.find(
        {}, {"email": 1, "mobile": 1, "email_normalized": 1, "mobile_normalized": 1}
    ).to_list(length=None)
    identifiers = {"email_normalized": {}, "mobile_normalized": {}}
    values_by_id = {}
    for document in documents:
        values = {
            "email_normalized": _normalized_email(
                document.get("email_normalized") or document.get("email")
            ),
            "mobile_normalized": _normalized_mobile(
                document.get("mobile_normalized") or document.get("mobile")
            ),
        }
        values_by_id[document["_id"]] = values
        for field, value in values.items():
            if value:
                identifiers[field].setdefault(value, []).append(document["_id"])

    conflicts = {
        field: {value for value, ids in values.items() if len(ids) > 1}
        for field, values in identifiers.items()
    }
    for document in documents:
        values = values_by_id[document["_id"]]
        updates = {
            field: value
            for field, value in values.items()
            if value and value not in conflicts[field]
            and document.get(field) != value
        }
        if updates:
            await users.update_one({"_id": document["_id"]}, {"$set": updates})

    conflict_count = sum(len(values) for values in conflicts.values())
    if conflict_count:
        logger.error(
            "Found %s normalized email/mobile conflicts in existing users; "
            "records were preserved and new registrations are disabled until resolved.",
            conflict_count,
        )
    return conflict_count == 0


def get_user_collection():
    return get_database()["users"]


def get_farmer_profile_collection():
    return get_database()["farmer_profiles"]


def get_buyer_profile_collection():
    return get_database()["marketplace_v2_buyer_profiles"]


def get_buyer_requirement_collection():
    return get_database()["marketplace_v2_requirements"]


def get_farmer_offer_collection():
    return get_database()["marketplace_v2_farmer_offers"]


def get_marketplace_order_collection():
    return get_database()["marketplace_v2_orders"]


def get_marketplace_listing_order_collection():
    return get_database()["marketplace_v2_listing_orders"]


def get_marketplace_notification_collection():
    return get_database()["marketplace_v2_notifications"]


def get_marketplace_message_collection():
    return get_database()["marketplace_v2_messages"]


def get_produce_listing_collection():
    return get_database()["marketplace_v2_produce"]


def get_scheme_checklist_collection():
    return get_database()["scheme_checklists"]


async def ensure_indexes():
    global _auth_indexes_ready
    _auth_indexes_ready = False
    try:
        db = get_database()
        users = db["users"]
        identifiers_are_unique = await _migrate_auth_identifiers(users)
        if hasattr(users, "index_information"):
            indexes = await users.index_information()
            for name, index in indexes.items():
                keys = [tuple(key) for key in index.get("key", [])]
                if keys == [("mobile", 1)] and not index.get("sparse"):
                    await users.drop_index(name)
        await users.create_index("mobile", unique=True, sparse=True)
        await users.create_index("email", unique=True, sparse=True)
        await users.create_index("mobile_normalized", unique=True, sparse=True)
        await users.create_index("email_normalized", unique=True, sparse=True)
        await users.create_index("google_sub", unique=True, sparse=True)
        _auth_indexes_ready = identifiers_are_unique
    except Exception as exc:
        logger.error(
            "Could not prepare MongoDB authentication indexes (%s).",
            type(exc).__name__,
        )
        return

    try:
        await db["farmer_profiles"].create_index("user_id", unique=True)
        await db["marketplace_v2_buyer_profiles"].create_index("user_id", unique=True)
        await db["marketplace_v2_requirements"].create_index(
            [("status", 1), ("created_at", -1)]
        )
        await db["marketplace_v2_requirements"].create_index(
            [("buyer_id", 1), ("created_at", -1)]
        )
        await db["marketplace_v2_farmer_offers"].create_index(
            [("requirement_id", 1), ("farmer_id", 1)], unique=True
        )
        await db["marketplace_v2_farmer_offers"].create_index(
            [("farmer_id", 1), ("created_at", -1)]
        )
        await db["marketplace_v2_orders"].create_index(
            "requirement_id", unique=True
        )
        await db["marketplace_v2_orders"].create_index(
            [("buyer_id", 1), ("created_at", -1)]
        )
        await db["marketplace_v2_orders"].create_index(
            [("farmer_id", 1), ("created_at", -1)]
        )
        await db["marketplace_v2_listing_orders"].create_index(
            [("buyer_id", 1), ("idempotency_key", 1)], unique=True
        )
        await db["marketplace_v2_listing_orders"].create_index(
            [("buyer_id", 1), ("created_at", -1)]
        )
        await db["marketplace_v2_listing_orders"].create_index(
            [("farmer_id", 1), ("created_at", -1)]
        )
        await db["marketplace_v2_listing_orders"].create_index(
            [("listing_id", 1), ("created_at", -1)]
        )
        await db["marketplace_v2_notifications"].create_index(
            [("recipient_id", 1), ("created_at", -1)]
        )
        await db["marketplace_v2_notifications"].create_index(
            [("order_id", 1), ("recipient_id", 1), ("type", 1)], unique=True
        )
        await db["marketplace_v2_messages"].create_index(
            [("order_id", 1), ("created_at", 1)]
        )
        await db["marketplace_v2_messages"].create_index(
            [("order_id", 1), ("sender_id", 1), ("client_message_id", 1)],
            unique=True,
            partialFilterExpression={"client_message_id": {"$type": "string"}},
        )
        await db["marketplace_v2_produce"].create_index(
            [("status", 1), ("created_at", -1)]
        )
        await db["marketplace_v2_produce"].create_index(
            [("farmer_id", 1), ("profile_crop_key", 1)],
            unique=True,
            partialFilterExpression={"profile_crop_key": {"$type": "string"}},
        )
        await db["scheme_checklists"].create_index(
            [("user_id", 1), ("scheme_id", 1)], unique=True
        )
        logger.info("Database indexes ensured.")
    except Exception as exc:
        logger.error(
            "Could not ensure one or more MongoDB indexes (%s).",
            type(exc).__name__,
        )
