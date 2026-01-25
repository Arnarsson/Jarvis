"""Web page routes for Jarvis UI.

Serves HTML pages rendered with Jinja2 templates.
"""

from pathlib import Path

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

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
    return templates.TemplateResponse(
        request=request,
        name="settings.html",
        context={"page_title": "Settings"},
    )
