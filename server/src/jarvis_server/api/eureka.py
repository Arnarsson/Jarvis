"""Eureka (Clawdbot) integration API endpoints."""

import os
from datetime import datetime, timezone

import httpx
import structlog
from fastapi import APIRouter

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/api/eureka", tags=["eureka"])

CLAWDBOT_GATEWAY_URL = os.environ.get("CLAWDBOT_GATEWAY_URL", "http://host.docker.internal:3377")
CLAWDBOT_TOKEN = os.environ.get("CLAWDBOT_TOKEN", "")


async def _gateway_get(path: str) -> dict | None:
    """Make a GET request to the Clawdbot gateway."""
    try:
        headers = {}
        if CLAWDBOT_TOKEN:
            headers["Authorization"] = f"Bearer {CLAWDBOT_TOKEN}"
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(f"{CLAWDBOT_GATEWAY_URL}{path}", headers=headers)
            if resp.status_code == 200:
                return resp.json()
            logger.warning("Gateway request failed", path=path, status=resp.status_code)
    except Exception as e:
        logger.debug("Gateway unreachable", path=path, error=str(e))
    return None


@router.get("/status")
async def eureka_status():
    """Get Eureka's current status and active workers."""
    # Try to reach Clawdbot gateway for session info
    sessions_data = await _gateway_get("/api/sessions")

    active_workers = []
    recent_workers = []
    online = False

    if sessions_data and isinstance(sessions_data, dict):
        online = True
        sessions = sessions_data.get("sessions", [])
        for s in sessions:
            kind = s.get("kind", "")
            status = s.get("status", "idle")
            worker = {
                "sessionKey": s.get("sessionKey", ""),
                "label": s.get("label") or s.get("agentId") or s.get("sessionKey", "")[:8],
                "status": "running" if status == "active" else "completed" if status == "done" else "idle",
                "task": s.get("task") or s.get("label") or "",
                "startedAt": s.get("startedAt") or s.get("createdAt") or datetime.now(timezone.utc).isoformat(),
                "completedAt": s.get("completedAt"),
                "model": s.get("model", "claude-opus-4-5"),
                "agentId": s.get("agentId", "main"),
            }
            if kind == "subagent" or kind == "spawn":
                if status == "active":
                    active_workers.append(worker)
                else:
                    recent_workers.append(worker)
    else:
        # Gateway not reachable — still report as online if we're running
        online = True

    return {
        "online": online,
        "model": "claude-opus-4-5",
        "activeWorkers": active_workers[:8],
        "recentWorkers": recent_workers[:10],
    }
