"""FastAPI application entry point for Jarvis server.

Configures the FastAPI app with routers, middleware, and lifecycle management.
"""

from contextlib import asynccontextmanager
from typing import AsyncGenerator

import structlog
import uvicorn
from arq import create_pool
from arq.connections import RedisSettings
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from jarvis_server import __version__
from jarvis_server.api.calendar import router as calendar_router
from jarvis_server.api.captures import get_storage, router as captures_router
from jarvis_server.api.email import router as email_router
from jarvis_server.api.health import router as health_router
from jarvis_server.api.meetings import router as meetings_router
from jarvis_server.api.search import router as search_router
from jarvis_server.api.timeline import router as timeline_router
from jarvis_server.imports.api import router as import_router
from jarvis_server.config import get_settings

logger = structlog.get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan context manager.

    Handles startup and shutdown events for the application.
    """
    settings = get_settings()

    # Startup
    logger.info(
        "server_starting",
        version=__version__,
        storage_path=str(settings.storage_path),
        database_url=_mask_url(settings.database_url),
        qdrant_host=settings.qdrant_host,
        qdrant_port=settings.qdrant_port,
        log_level=settings.log_level,
    )

    # Ensure storage directory exists
    storage = get_storage()
    logger.info("storage_initialized", path=str(storage.base_path))

    # Initialize ARQ Redis pool for background job enqueueing
    redis_settings = RedisSettings(
        host=settings.redis_host,
        port=settings.redis_port,
    )
    app.state.arq_pool = await create_pool(redis_settings)
    logger.info(
        "arq_pool_initialized",
        redis_host=settings.redis_host,
        redis_port=settings.redis_port,
    )

    yield

    # Shutdown
    await app.state.arq_pool.close()
    logger.info("server_stopping")


def _mask_url(url: str) -> str:
    """Mask sensitive parts of a database URL for logging.

    postgresql+asyncpg://user:password@host:port/db
    -> postgresql+asyncpg://user:***@host:port/db
    """
    if "@" not in url:
        return url

    # Split on @ to separate credentials from host
    before_at, after_at = url.rsplit("@", 1)

    # Find the last : before @ (password separator)
    if ":" in before_at:
        # Find scheme and user:password
        scheme_end = before_at.find("://")
        if scheme_end != -1:
            scheme = before_at[: scheme_end + 3]
            user_pass = before_at[scheme_end + 3 :]

            # Split user:password
            if ":" in user_pass:
                user = user_pass.split(":", 1)[0]
                return f"{scheme}{user}:***@{after_at}"

    return url


def create_app() -> FastAPI:
    """Create and configure the FastAPI application.

    Returns:
        Configured FastAPI application instance.
    """
    settings = get_settings()

    app = FastAPI(
        title="Jarvis Server",
        description="AI Chief of Staff backend - captures, processes, and provides context",
        version=__version__,
        lifespan=lifespan,
    )

    # Configure CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Include routers
    app.include_router(calendar_router)
    app.include_router(captures_router)
    app.include_router(email_router)
    app.include_router(health_router)
    app.include_router(meetings_router)
    app.include_router(search_router)
    app.include_router(timeline_router)
    app.include_router(import_router)

    return app


# Create the application instance
app = create_app()


def run() -> None:
    """Run the server using uvicorn.

    This is the CLI entry point defined in pyproject.toml.
    """
    settings = get_settings()

    # Configure structlog for JSON output
    structlog.configure(
        processors=[
            structlog.stdlib.filter_by_level,
            structlog.stdlib.add_logger_name,
            structlog.stdlib.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.JSONRenderer(),
        ],
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    uvicorn.run(
        "jarvis_server.main:app",
        host="0.0.0.0",
        port=8000,
        reload=False,
        log_level=settings.log_level.lower(),
    )


if __name__ == "__main__":
    run()
