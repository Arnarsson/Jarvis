"""Email API endpoints for OAuth, sync, and message access."""

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from jarvis_server.db.session import get_db
from jarvis_server.email.models import EmailMessage, EmailSyncState
from jarvis_server.email.oauth import (
    CredentialsNotFound,
    GmailAuthRequired,
    credentials_exist,
    is_authenticated,
    start_oauth_flow,
)
from jarvis_server.email.sync import sync_emails

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/api/email", tags=["email"])


class AuthStatusResponse(BaseModel):
    """Response for auth status endpoint."""

    authenticated: bool
    needs_credentials: bool


class AuthStartResponse(BaseModel):
    """Response for auth start endpoint."""

    status: str
    message: str


class EmailMessageResponse(BaseModel):
    """Response model for an email message."""

    id: str
    gmail_message_id: str
    thread_id: str
    subject: str | None = None
    from_address: str | None = None
    from_name: str | None = None
    snippet: str | None = None
    date_sent: str
    is_unread: bool = False
    is_important: bool = False


class EmailMessageDetailResponse(EmailMessageResponse):
    """Detailed response model for an email message with body."""

    to_addresses: str | None = None
    cc_addresses: str | None = None
    body_text: str | None = None
    labels_json: str | None = None


class EmailListResponse(BaseModel):
    """Response for email list endpoint."""

    messages: list[EmailMessageResponse]
    count: int


class SyncResponse(BaseModel):
    """Response for sync endpoint."""

    status: str
    created: int
    updated: int
    deleted: int


class SyncStatusResponse(BaseModel):
    """Response for sync status endpoint."""

    last_sync: str | None = None
    history_id: str | None = None
    message_count: int


@router.get("/auth/status", response_model=AuthStatusResponse)
async def get_auth_status() -> AuthStatusResponse:
    """Check Gmail authentication status.

    Returns:
        Authentication status including whether credentials file exists.
    """
    return AuthStatusResponse(
        authenticated=is_authenticated(),
        needs_credentials=not credentials_exist(),
    )


@router.post("/auth/start", response_model=AuthStartResponse)
async def start_auth() -> AuthStartResponse:
    """Start Gmail OAuth flow.

    This endpoint initiates the OAuth flow. The user must complete
    authentication in their browser. This works when the server
    is running on the same machine as the user's browser.

    Returns:
        Status message about authentication flow.

    Raises:
        HTTPException: If credentials.json is missing.
    """
    try:
        message = start_oauth_flow()
        logger.info("gmail_oauth_completed")
        return AuthStartResponse(status="auth_completed", message=message)
    except CredentialsNotFound as e:
        logger.warning("gmail_credentials_not_found")
        raise HTTPException(
            status_code=400,
            detail=str(e),
        ) from e


@router.get("/messages", response_model=EmailListResponse)
async def list_messages(
    limit: int = 20,
    from_address: str | None = None,
    db: AsyncSession = Depends(get_db),
) -> EmailListResponse:
    """List email messages from the local database.

    Returns emails that have been synced from Gmail.
    Use /sync endpoint (future) to sync emails first.

    Args:
        limit: Maximum messages to return (default 20, max 100).
        from_address: Optional filter by sender address.
        db: Database session.

    Returns:
        List of stored email messages.
    """
    # Cap the limit
    limit = min(limit, 100)

    query = select(EmailMessage).order_by(EmailMessage.date_sent.desc())

    if from_address:
        query = query.where(EmailMessage.from_address == from_address)

    query = query.limit(limit)

    result = await db.execute(query)
    messages = result.scalars().all()

    logger.info("email_messages_listed", count=len(messages))

    return EmailListResponse(
        messages=[
            EmailMessageResponse(
                id=m.id,
                gmail_message_id=m.gmail_message_id,
                thread_id=m.thread_id,
                subject=m.subject,
                from_address=m.from_address,
                from_name=m.from_name,
                snippet=m.snippet,
                date_sent=m.date_sent.isoformat(),
                is_unread=m.is_unread,
                is_important=m.is_important,
            )
            for m in messages
        ],
        count=len(messages),
    )


@router.get("/messages/{message_id}", response_model=EmailMessageDetailResponse)
async def get_message(
    message_id: str,
    db: AsyncSession = Depends(get_db),
) -> EmailMessageDetailResponse:
    """Get a single email message with full details.

    Args:
        message_id: The message ID (internal UUID, not Gmail ID).
        db: Database session.

    Returns:
        Full email message including body.

    Raises:
        HTTPException: If message not found.
    """
    result = await db.execute(
        select(EmailMessage).where(EmailMessage.id == message_id)
    )
    message = result.scalar_one_or_none()

    if not message:
        raise HTTPException(status_code=404, detail="Message not found")

    return EmailMessageDetailResponse(
        id=message.id,
        gmail_message_id=message.gmail_message_id,
        thread_id=message.thread_id,
        subject=message.subject,
        from_address=message.from_address,
        from_name=message.from_name,
        snippet=message.snippet,
        date_sent=message.date_sent.isoformat(),
        is_unread=message.is_unread,
        is_important=message.is_important,
        to_addresses=message.to_addresses,
        cc_addresses=message.cc_addresses,
        body_text=message.body_text,
        labels_json=message.labels_json,
    )


@router.post("/sync", response_model=SyncResponse)
async def trigger_sync(
    full_sync: bool = False,
    db: AsyncSession = Depends(get_db),
) -> SyncResponse:
    """Trigger email sync from Gmail.

    Performs incremental sync by default using Gmail History API.
    Use full_sync=true to force a complete re-sync of recent messages.

    Args:
        full_sync: Force full sync instead of incremental (default False).
        db: Database session.

    Returns:
        Sync results with counts of created/updated/deleted messages.

    Raises:
        HTTPException: If not authenticated with Gmail.
    """
    try:
        result = await sync_emails(db, full_sync=full_sync)
        logger.info(
            "email_sync_completed",
            created=result["created"],
            updated=result["updated"],
            deleted=result["deleted"],
        )
        return SyncResponse(
            status="completed",
            created=result["created"],
            updated=result["updated"],
            deleted=result["deleted"],
        )
    except GmailAuthRequired as e:
        logger.warning("email_sync_auth_required")
        raise HTTPException(
            status_code=401,
            detail=str(e),
        ) from e


@router.get("/sync/status", response_model=SyncStatusResponse)
async def get_sync_status(
    db: AsyncSession = Depends(get_db),
) -> SyncStatusResponse:
    """Get email sync status.

    Returns information about the last sync and current state.

    Args:
        db: Database session.

    Returns:
        Sync status including last sync time, history ID, and message count.
    """
    # Get sync state
    result = await db.execute(
        select(EmailSyncState).where(EmailSyncState.id == "gmail_primary")
    )
    state = result.scalar_one_or_none()

    # Get message count
    count_result = await db.execute(
        select(func.count()).select_from(EmailMessage)
    )
    message_count = count_result.scalar() or 0

    return SyncStatusResponse(
        last_sync=state.updated_at.isoformat() if state else None,
        history_id=state.history_id if state else None,
        message_count=message_count,
    )
