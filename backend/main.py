from contextlib import asynccontextmanager
import asyncio
import time
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pymongo.errors import PyMongoError
import logging

from database import (
    settings,
    connect_to_mongo,
    close_mongo_connection,
    database_is_connected,
    ensure_indexes,
)
from routes import auth, farmer, weather, assistant, market, disease, schemes, buyer_marketplace

if not logging.getLogger().handlers:
    logging.basicConfig(level=logging.INFO)

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


def _preload_disease_model():
    from services import disease_model_service

    started = time.perf_counter()
    try:
        disease_model_service._ensure_loaded()
        logger.info(
            "Disease model startup initialization elapsed_ms=%.1f available=%s",
            (time.perf_counter() - started) * 1000,
            disease_model_service.is_real_model_available(),
        )
        if disease_model_service.is_real_model_available():
            disease_model_service.warmup_model()
            print("Crop disease model loaded successfully (real inference).", flush=True)
        else:
            print(
                "Crop disease model is unavailable; local diagnoses will not be generated.",
                flush=True,
            )
    except Exception:
        logger.exception(
            "Crop disease model failed to preload elapsed_ms=%.1f",
            (time.perf_counter() - started) * 1000,
        )


async def _retry_mongo_connection():
    while not database_is_connected():
        await asyncio.sleep(5)
        await connect_to_mongo()
        if database_is_connected():
            await ensure_indexes()


@asynccontextmanager
async def lifespan(app: FastAPI):
    await connect_to_mongo()
    reconnect_task = None
    if database_is_connected():
        await ensure_indexes()
    else:
        logger.warning(
            "MongoDB is not ready; retrying the configured connection in the background."
        )
        reconnect_task = asyncio.create_task(_retry_mongo_connection())
    try:
        from services.ai_service import (
            initialize_chat_http_client,
            initialize_gemini_vision_client,
        )
        await initialize_chat_http_client()
        await initialize_gemini_vision_client()
    except Exception as e:
        logger.warning(
            "Reusable AI client initialization failed (%s).",
            type(e).__name__,
        )
    _preload_disease_model()
    try:
        yield
    finally:
        if reconnect_task:
            reconnect_task.cancel()
            try:
                await reconnect_task
            except asyncio.CancelledError:
                pass
        try:
            from services.ai_service import (
                close_chat_http_client,
                close_gemini_vision_client,
            )
            await close_chat_http_client()
            await close_gemini_vision_client()
        finally:
            await close_mongo_connection()


app = FastAPI(
    title="AI KrushiMitra API",
    description="AI-powered agricultural assistant backend for farmers",
    version="1.0.0",
    lifespan=lifespan,
)

cors_origins = [origin.strip() for origin in settings.CORS_ORIGINS.split(",") if origin.strip()]
google_redirect_origin = settings.GOOGLE_REDIRECT_URI.strip().rstrip("/")
if google_redirect_origin and google_redirect_origin not in cors_origins:
    logger.warning(
        "Google OAuth redirect origin is not present in the CORS allowlist.",
        extra={
            "auth_provider": "google",
            "auth_stage": "cors_configuration",
            "error_code": "GOOGLE_CORS_ORIGIN_MISMATCH",
        },
    )

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins if cors_origins else ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router, prefix="/api/auth", tags=["Authentication"])
app.include_router(farmer.router, prefix="/api/farmer", tags=["Farmer Profile"])
app.include_router(weather.router, prefix="/api/weather", tags=["Weather"])
app.include_router(assistant.router, prefix="/api/assistant", tags=["AI Assistant"])
app.include_router(market.router, prefix="/api/market", tags=["Market Prices"])
app.include_router(buyer_marketplace.router, prefix="/api/marketplace", tags=["Farmer-Buyer Marketplace"])
app.include_router(disease.router, prefix="/api/disease", tags=["Crop Disease"])
app.include_router(schemes.router, prefix="/api/schemes", tags=["Government Schemes"])


async def _database_health():
    try:
        from database import get_database
        ping = await get_database().command("ping")
        db_ok = not bool(ping.get("in_memory"))
        return db_ok, None if db_ok else "InMemoryFallback"
    except RuntimeError:
        return False, "MongoDBUnavailable"
    except PyMongoError as exc:
        logger.error("MongoDB health check failed (%s).", type(exc).__name__)
        return False, type(exc).__name__


@app.exception_handler(RuntimeError)
async def runtime_error_handler(request: Request, exc: RuntimeError):
    msg = str(exc).lower()
    if "mongodb" in msg or "database" in msg:
        return JSONResponse(
            status_code=503,
            content={
                "detail": "Database service is unavailable. Please ensure MongoDB is running.",
                "code": "DB_UNAVAILABLE",
            },
        )
    return JSONResponse(status_code=500, content={"detail": str(exc)})


@app.exception_handler(PyMongoError)
async def mongo_error_handler(request: Request, exc: PyMongoError):
    logger.error("MongoDB request failed (%s).", type(exc).__name__)
    return JSONResponse(
        status_code=503,
        content={
            "detail": "Database service is unavailable. Please try again when MongoDB is reachable.",
            "code": "DB_UNAVAILABLE",
        },
    )


@app.get("/", tags=["Health"])
async def health_check():
    db_ok, db_error = await _database_health()
    return {
        "status": "healthy" if db_ok else "degraded",
        "service": "AI KrushiMitra API",
        "version": "1.0.0",
        "database": "connected" if db_ok else "unavailable",
        "database_error": db_error,
        "docs": "/docs",
    }


@app.get("/api/health", tags=["Health"])
async def api_health():
    db_ok, db_error = await _database_health()
    return {
        "status": "healthy" if db_ok else "degraded",
        "service": "AI KrushiMitra API",
        "database": "connected" if db_ok else "unavailable",
        "database_error": db_error,
    }
