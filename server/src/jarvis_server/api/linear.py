"""Linear API proxy endpoint for the dashboard.

Fetches tasks from Linear's GraphQL API and returns them in a simplified format.
"""

import os
from pathlib import Path
from typing import Optional

import httpx
import structlog
from fastapi import APIRouter, Query

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/api/v2/linear", tags=["linear"])

LINEAR_API_URL = "https://api.linear.app/graphql"
TEAM_ID = "b4f3046f-b603-43fb-94b5-5f17dd9396e0"


def _get_api_key() -> Optional[str]:
    """Get Linear API key from environment or file."""
    key = os.environ.get("LINEAR_API_KEY")
    if key:
        return key.strip()
    # Try reading from file
    for path in [Path.home() / ".linear_api_key", Path("/data/.linear_api_key")]:
        if path.exists():
            return path.read_text().strip()
    return None


@router.get("/tasks")
async def get_linear_tasks(
    limit: int = Query(default=20, ge=1, le=50),
    states: str = Query(default="started,unstarted", description="Comma-separated state types"),
):
    """Fetch Linear tasks for the team, ordered by priority and update time."""
    api_key = _get_api_key()
    if not api_key:
        logger.warning("linear_api_key_not_found")
        return {"tasks": [], "total": 0, "error": "Linear API key not configured"}

    state_types = [s.strip() for s in states.split(",")]

    query = """
    query($teamId: String!, $first: Int!, $stateTypes: [String!]) {
        team(id: $teamId) {
            issues(
                first: $first,
                filter: { state: { type: { in: $stateTypes } } },
                orderBy: updatedAt
            ) {
                nodes {
                    id
                    identifier
                    title
                    state { name }
                    priority
                    priorityLabel
                    dueDate
                    url
                }
            }
        }
    }
    """

    variables = {
        "teamId": TEAM_ID,
        "first": limit,
        "stateTypes": state_types,
    }

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(
                LINEAR_API_URL,
                json={"query": query, "variables": variables},
                headers={
                    "Content-Type": "application/json",
                    "Authorization": api_key,
                },
            )
            resp.raise_for_status()
            data = resp.json()

        issues = data.get("data", {}).get("team", {}).get("issues", {}).get("nodes", [])

        tasks = []
        for issue in issues:
            tasks.append({
                "id": issue["id"],
                "identifier": issue["identifier"],
                "title": issue["title"],
                "state": issue["state"]["name"],
                "priority": issue["priority"],
                "priorityLabel": issue["priorityLabel"],
                "dueDate": issue.get("dueDate"),
                "url": issue.get("url", f"https://linear.app/issue/{issue['identifier']}"),
            })

        # Sort: in-progress first, then by priority (1=urgent, 4=low)
        state_order = {"In Progress": 0, "Todo": 1}
        tasks.sort(key=lambda t: (state_order.get(t["state"], 2), t["priority"]))

        return {"tasks": tasks, "total": len(tasks)}

    except httpx.HTTPError as e:
        logger.error("linear_api_error", error=str(e))
        return {"tasks": [], "total": 0, "error": str(e)}
    except Exception as e:
        logger.error("linear_unexpected_error", error=str(e))
        return {"tasks": [], "total": 0, "error": "Unexpected error"}
