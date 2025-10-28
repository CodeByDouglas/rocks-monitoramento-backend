from __future__ import annotations

import asyncio
import os
from collections.abc import AsyncIterator

import pytest
import pytest_asyncio
from asgi_lifespan import LifespanManager
from httpx import AsyncClient


@pytest.fixture(scope="session")
def event_loop() -> AsyncIterator[asyncio.AbstractEventLoop]:
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="session")
def settings_override(tmp_path_factory: pytest.TempPathFactory):
    db_path = tmp_path_factory.mktemp("db") / "test.db"
    os.environ["DATABASE_URL"] = f"sqlite+aiosqlite:///{db_path}"
    os.environ["JWT_SECRET_KEY"] = "test-secret"
    os.environ["JWT_EXPIRATION_MINUTES"] = "120"
    from app.core.config import get_settings

    get_settings.cache_clear()
    settings = get_settings()
    return settings


@pytest.fixture(scope="session")
def app_instance(settings_override):
    from app.main import app

    return app


@pytest_asyncio.fixture(autouse=True)
async def clean_database(settings_override):
    from app.database import engine
    from app.models import Base

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    yield


@pytest_asyncio.fixture()
async def client(app_instance):
    async with LifespanManager(app_instance):
        async with AsyncClient(app=app_instance, base_url="http://testserver") as client:
            yield client
