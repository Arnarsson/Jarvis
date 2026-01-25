"""Web page routes for Jarvis UI.

Serves HTML pages rendered with Jinja2 templates.
"""

from pathlib import Path
from urllib.parse import urlparse

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from jarvis_server.config import get_settings

router = APIRouter(tags=["web"])

# Templates directory
templates_dir = Path(__file__).parent / "templates"
templates = Jinja2Templates(directory=templates_dir)


@router.get("/", response_class=HTMLResponse)
async def dashboard(request: Request) -> HTMLResponse:
    """Dashboard page - main entry point."""
    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={"page_title": "Dashboard"},
    )


@router.get("/timeline", response_class=HTMLResponse)
async def timeline(request: Request) -> HTMLResponse:
    """Timeline page - chronological view of captures."""
    return templates.TemplateResponse(
        request=request,
        name="timeline.html",
        context={"page_title": "Timeline"},
    )


@router.get("/search", response_class=HTMLResponse)
async def search(request: Request) -> HTMLResponse:
    """Search page - semantic and keyword search."""
    return templates.TemplateResponse(
        request=request,
        name="search.html",
        context={"page_title": "Search"},
    )


@router.get("/calendar", response_class=HTMLResponse)
async def calendar(request: Request) -> HTMLResponse:
    """Calendar page - events and meetings."""
    return templates.TemplateResponse(
        request=request,
        name="calendar.html",
        context={"page_title": "Calendar"},
    )


@router.get("/settings", response_class=HTMLResponse)
async def settings(request: Request) -> HTMLResponse:
    """Settings page - configuration options."""
    config = get_settings()

    # Parse database URL to show host only (hide credentials)
    parsed_db = urlparse(config.database_url)
    database_host = f"{parsed_db.hostname}:{parsed_db.port}" if parsed_db.port else parsed_db.hostname

    return templates.TemplateResponse(
        request=request,
        name="settings.html",
        context={
            "page_title": "Settings",
            "storage_path": str(config.storage_path),
            "data_dir": str(config.data_dir),
            "database_host": database_host or "localhost",
            "log_level": config.log_level,
        },
    )
