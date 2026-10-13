from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI

from backend.app import models  # noqa: F401
from backend.app.api.routes.auth import router as auth_router
from backend.app.api.routes.expedientes import router as expedientes_router
from backend.app.api.routes.system import router as system_router
from backend.app.config import settings
from backend.app.db import engine, SessionLocal
from backend.app.models.base import Base


mcp_app = None
if settings.mcp_enabled:
    from backend.app.mcp_server import build_mcp_app

    mcp_app = build_mcp_app(settings, SessionLocal)


@asynccontextmanager
async def lifespan(_: FastAPI):
    settings.storage_root.mkdir(parents=True, exist_ok=True)
    if settings.allow_sqlite_fallback and settings.database_url.startswith("sqlite"):
        Base.metadata.create_all(bind=engine)
    if mcp_app is None:
        yield
    else:
        async with mcp_app.router.lifespan_context(mcp_app):
            yield


app = FastAPI(title=settings.app_name, lifespan=lifespan)
app.include_router(system_router)
app.include_router(auth_router, prefix=settings.api_prefix)
app.include_router(expedientes_router, prefix=settings.api_prefix)
if mcp_app is not None:
    app.mount("/", mcp_app)
