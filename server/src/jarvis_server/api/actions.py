"""
Proactive Action Buttons API
Executes 1-click actions from the command center dashboard.
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional, Dict, Any
import httpx
import os
import logging
from pathlib import Path

router = APIRouter(prefix="/api/v2/actions", tags=["actions"])
logger = logging.getLogger(__name__)


# ────────────────────────────────────────────────────────────────
# Request Models
# ────────────────────────────────────────────────────────────────


class DraftEmailRequest(BaseModel):
    """Request to draft an email reply"""
    to_email: str
    to_name: str
    subject: str
    context: Optional[str] = None  # Original email text or conversation context
    reply_type: str = "professional"  # professional, friendly, brief, detailed


class CreateLinearTaskRequest(BaseModel):
    """Request to create a Linear task"""
    title: str
    description: Optional[str] = None
    priority: int = 3  # 1=urgent, 2=high, 3=medium, 4=low
    team_id: str = "b4f3046f-b603-43fb-94b5-5f17dd9396e0"  # Default team
    state_id: Optional[str] = None  # Leave empty for default "Todo" state


class UpdateLinearTaskRequest(BaseModel):
    """Request to update a Linear task"""
    task_id: str
    state_id: Optional[str] = None  # Change state
    priority: Optional[int] = None  # Change priority


class SendReminderRequest(BaseModel):
    """Request to send a reminder email"""
    to_email: str
    to_name: str
    subject: str
    reminder_text: str


# ────────────────────────────────────────────────────────────────
# Gmail API Integration
# ────────────────────────────────────────────────────────────────


def get_gmail_draft_url(to_email: str, subject: str, body: str) -> str:
    """
    Generate a Gmail compose URL with pre-filled content.
    Opens in browser for user to review and send.
    """
    import urllib.parse
    
    params = {
        "to": to_email,
        "su": subject,
        "body": body,
    }
    query = urllib.parse.urlencode(params)
    return f"https://mail.google.com/mail/?view=cm&{query}"


# ────────────────────────────────────────────────────────────────
# Linear GraphQL Integration
# ────────────────────────────────────────────────────────────────


async def get_linear_api_key() -> str:
    """Load Linear API key from ~/.linear_api_key"""
    key_path = Path.home() / ".linear_api_key"
    if not key_path.exists():
        raise HTTPException(
            status_code=500,
            detail="Linear API key not found. Please create ~/.linear_api_key"
        )
    return key_path.read_text().strip()


async def linear_graphql(query: str, variables: Dict[str, Any] = None) -> Dict[str, Any]:
    """Execute a Linear GraphQL query"""
    api_key = await get_linear_api_key()
    
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "https://api.linear.app/graphql",
            headers={
                "Content-Type": "application/json",
                "Authorization": api_key,
            },
            json={"query": query, "variables": variables or {}},
            timeout=30.0,
        )
        
        if response.status_code != 200:
            raise HTTPException(
                status_code=response.status_code,
                detail=f"Linear API error: {response.text}"
            )
        
        data = response.json()
        if "errors" in data:
            raise HTTPException(
                status_code=400,
                detail=f"Linear GraphQL error: {data['errors']}"
            )
        
        return data["data"]


# ────────────────────────────────────────────────────────────────
# Action Endpoints
# ────────────────────────────────────────────────────────────────


@router.post("/draft-email")
async def draft_email(request: DraftEmailRequest):
    """
    Generate a draft email reply and return a Gmail compose URL.
    
    Returns a URL that opens Gmail with the email pre-filled.
    User can review and edit before sending.
    """
    
    # Generate AI draft email body
    # For now, using a simple template. Could integrate with LLM for smart drafts.
    
    if request.reply_type == "brief":
        body = f"""Hi {request.to_name},

Thanks for reaching out.

{request.context or "I'll get back to you with more details soon."}

Best regards"""
    
    elif request.reply_type == "friendly":
        body = f"""Hey {request.to_name}!

{request.context or "Great to hear from you! Let me know how I can help."}

Cheers!"""
    
    else:  # professional
        body = f"""Dear {request.to_name},

Thank you for your email regarding {request.subject}.

{request.context or "I've reviewed your message and will follow up with you shortly with more information."}

Best regards"""
    
    gmail_url = get_gmail_draft_url(
        to_email=request.to_email,
        subject=f"Re: {request.subject}",
        body=body,
    )
    
    logger.info(f"Generated email draft for {request.to_email}")
    
    return {
        "success": True,
        "gmail_url": gmail_url,
        "draft_body": body,
        "action": "open_gmail",
    }


@router.post("/create-linear-task")
async def create_linear_task(request: CreateLinearTaskRequest):
    """
    Create a new Linear task via GraphQL API.
    
    Returns the created task with identifier and URL.
    """
    
    query = """
    mutation CreateIssue($teamId: String!, $title: String!, $description: String, $priority: Int, $stateId: String) {
      issueCreate(
        input: {
          teamId: $teamId
          title: $title
          description: $description
          priority: $priority
          stateId: $stateId
        }
      ) {
        success
        issue {
          id
          identifier
          title
          url
          state {
            id
            name
          }
        }
      }
    }
    """
    
    variables = {
        "teamId": request.team_id,
        "title": request.title,
        "description": request.description,
        "priority": request.priority,
    }
    
    if request.state_id:
        variables["stateId"] = request.state_id
    
    try:
        data = await linear_graphql(query, variables)
        
        if not data["issueCreate"]["success"]:
            raise HTTPException(status_code=400, detail="Failed to create Linear task")
        
        issue = data["issueCreate"]["issue"]
        
        logger.info(f"Created Linear task: {issue['identifier']} - {issue['title']}")
        
        return {
            "success": True,
            "task": {
                "id": issue["id"],
                "identifier": issue["identifier"],
                "title": issue["title"],
                "url": issue["url"],
                "state": issue["state"]["name"],
            }
        }
    
    except Exception as e:
        logger.error(f"Error creating Linear task: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/update-linear-task")
async def update_linear_task(request: UpdateLinearTaskRequest):
    """
    Update a Linear task (change state or priority).
    
    Common state IDs:
    - In Progress: 941943ae-fa4e-4fac-96cb-a4a8a682999b
    - Done: 3ae46e12-b4dc-4d19-b1b9-fafd7a4eb88a
    """
    
    query = """
    mutation UpdateIssue($id: String!, $stateId: String, $priority: Int) {
      issueUpdate(
        id: $id
        input: {
          stateId: $stateId
          priority: $priority
        }
      ) {
        success
        issue {
          id
          identifier
          title
          state {
            id
            name
          }
          priority
        }
      }
    }
    """
    
    variables = {
        "id": request.task_id,
    }
    
    if request.state_id:
        variables["stateId"] = request.state_id
    
    if request.priority is not None:
        variables["priority"] = request.priority
    
    try:
        data = await linear_graphql(query, variables)
        
        if not data["issueUpdate"]["success"]:
            raise HTTPException(status_code=400, detail="Failed to update Linear task")
        
        issue = data["issueUpdate"]["issue"]
        
        logger.info(f"Updated Linear task: {issue['identifier']}")
        
        return {
            "success": True,
            "task": {
                "id": issue["id"],
                "identifier": issue["identifier"],
                "title": issue["title"],
                "state": issue["state"]["name"],
                "priority": issue["priority"],
            }
        }
    
    except Exception as e:
        logger.error(f"Error updating Linear task: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/send-reminder")
async def send_reminder(request: SendReminderRequest):
    """
    Send a reminder email. Opens Gmail compose window with pre-filled content.
    """
    
    body = f"""Hi {request.to_name},

Just following up on: {request.subject}

{request.reminder_text}

Looking forward to hearing from you!

Best regards"""
    
    gmail_url = get_gmail_draft_url(
        to_email=request.to_email,
        subject=request.subject,
        body=body,
    )
    
    logger.info(f"Generated reminder email for {request.to_email}")
    
    return {
        "success": True,
        "gmail_url": gmail_url,
        "action": "open_gmail",
    }


# ────────────────────────────────────────────────────────────────
# Health Check
# ────────────────────────────────────────────────────────────────


@router.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "ok", "service": "actions-api"}
