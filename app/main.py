from __future__ import annotations

from collections import defaultdict
from datetime import datetime
from time import monotonic
from typing import Any, Callable

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from loguru import logger
from sqlalchemy import select

from app.api.routes import router
from app.core.config import get_settings
from app.database import AsyncSessionLocal, engine
from app.models import Base, User
from app.security import get_password_hash

settings = get_settings()

app = FastAPI(title=settings.app_name, debug=settings.debug)


@app.middleware("http")
async def add_process_time_header(request: Request, call_next: Callable[[Request], Any]):
    start_time = datetime.utcnow()
    response = await call_next(request)
    process_time = (datetime.utcnow() - start_time).total_seconds()
    response.headers["X-Process-Time"] = str(process_time)
    return response


_rate_buckets: defaultdict[str, list[float]] = defaultdict(list)


@app.middleware("http")
async def rate_limit_middleware(request: Request, call_next: Callable[[Request], Any]):
    if request.url.path.startswith("/docs") or request.url.path.startswith("/openapi"):
        return await call_next(request)

    identifier = request.headers.get("X-Forwarded-For") or (request.client.host if request.client else "anonymous")
    window = settings.rate_limit_window_seconds
    now = monotonic()
    hits = [hit for hit in _rate_buckets[identifier] if now - hit < window]
    if len(hits) >= settings.rate_limit_requests:
        return JSONResponse(status_code=429, content={"detail": "Too Many Requests"})
    hits.append(now)
    _rate_buckets[identifier] = hits

    return await call_next(request)


app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_allow_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)


@app.on_event("startup")
async def on_startup() -> None:
    logger.info("Starting up application")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    await _ensure_initial_admin()


async def _ensure_initial_admin() -> None:
    if not settings.initial_admin_email or not settings.initial_admin_password:
        return

    async with AsyncSessionLocal() as session:
        result = await session.execute(select(User).where(User.email == settings.initial_admin_email))
        user = result.scalar_one_or_none()
        if user:
            return
        admin = User(
            email=settings.initial_admin_email,
            full_name="Administrator",
            hashed_password=get_password_hash(settings.initial_admin_password),
        )
        session.add(admin)
        await session.commit()
        logger.info("Seeded initial admin user")


@app.get("/", tags=["status"])
async def root() -> dict[str, str]:
    return {"message": "Rocks monitoramento backend is running"}
