# Copyright (C) 2026 Luke Brewerton
# SPDX-License-Identifier: AGPL-3.0-or-later
import logging

import redis
from fastapi import FastAPI
from sqlalchemy import text

from app.config import get_settings
from app.db import engine

settings = get_settings()
logging.basicConfig(level=settings.log_level)


def create_app() -> FastAPI:
    app = FastAPI(title=settings.app_name)

    @app.get("/api/health")
    def health() -> dict[str, str]:
        """Liveness: the process is up. Used by the container healthcheck."""
        return {"status": "ok"}

    @app.get("/api/ready")
    def ready() -> dict[str, object]:
        """Readiness: dependencies are reachable. Useful while bringing the stack up."""
        checks: dict[str, str] = {}
        healthy = True

        try:
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            checks["database"] = "ok"
        except Exception as exc:  # noqa: BLE001 - report, don't crash the endpoint
            checks["database"] = f"error: {exc}"
            healthy = False

        try:
            redis.Redis.from_url(settings.redis_url).ping()
            checks["redis"] = "ok"
        except Exception as exc:  # noqa: BLE001
            checks["redis"] = f"error: {exc}"
            healthy = False

        return {"ready": healthy, "checks": checks}

    from app.api.auth import router as auth_router
    from app.api.cvs import router as cvs_router
    from app.api.jobs import router as jobs_router
    from app.api.profiles import router as profiles_router
    from app.api.sources import admin_router as admin_sources_router
    from app.api.sources import router as sources_router

    app.include_router(auth_router)
    app.include_router(jobs_router)
    app.include_router(profiles_router)
    app.include_router(cvs_router)
    app.include_router(sources_router)
    app.include_router(admin_sources_router)

    return app


app = create_app()
