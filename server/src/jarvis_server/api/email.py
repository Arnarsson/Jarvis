"""Email API endpoints for OAuth, sync, and message access."""

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from jarvis_server.db.session import get_db
from jarvis_server.email.classifier import classify_email
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
    category: str | None = None


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
    category: str | None = None,
    db: AsyncSession = Depends(get_db),
) -> EmailListResponse:
    """List email messages from the local database.

    Returns emails that have been synced from Gmail.

    Args:
        limit: Maximum messages to return (default 20, max 100).
        from_address: Optional filter by sender address.
        category: Optional filter by category (priority, newsletter, notification, low_priority).
        db: Database session.

    Returns:
        List of stored email messages.
    """
    # Cap the limit
    limit = min(limit, 100)

    query = select(EmailMessage).order_by(EmailMessage.date_sent.desc())

    if from_address:
        query = query.where(EmailMessage.from_address == from_address)

    if category:
        query = query.where(EmailMessage.category == category)

    query = query.limit(limit)

    result = await db.execute(query)
    messages = result.scalars().all()

    logger.info("email_messages_listed", count=len(messages), category=category)

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
                category=m.category,
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
        category=message.category,
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


# ---------------------------------------------------------------------------
# Category endpoints
# ---------------------------------------------------------------------------


class CategoryCount(BaseModel):
    """Count for a single category."""

    name: str
    total: int
    unread: int


class CategoryCountsResponse(BaseModel):
    """Response for category counts endpoint."""

    categories: list[CategoryCount]


class ClassifyResponse(BaseModel):
    """Response for classify backfill endpoint."""

    classified: int


@router.get("/categories/counts", response_model=CategoryCountsResponse)
async def get_category_counts(
    db: AsyncSession = Depends(get_db),
) -> CategoryCountsResponse:
    """Get per-category total and unread counts.

    Returns:
        List of categories with total and unread counts.
    """
    category_names = ["priority", "newsletter", "notification", "low_priority"]
    categories = []

    for name in category_names:
        # Total count for this category
        total_result = await db.execute(
            select(func.count())
            .select_from(EmailMessage)
            .where(EmailMessage.category == name)
        )
        total = total_result.scalar() or 0

        # Unread count for this category
        unread_result = await db.execute(
            select(func.count())
            .select_from(EmailMessage)
            .where(EmailMessage.category == name, EmailMessage.is_unread == True)  # noqa: E712
        )
        unread = unread_result.scalar() or 0

        categories.append(CategoryCount(name=name, total=total, unread=unread))

    return CategoryCountsResponse(categories=categories)


@router.post("/classify", response_model=ClassifyResponse)
async def classify_messages(
    db: AsyncSession = Depends(get_db),
) -> ClassifyResponse:
    """Backfill: classify all uncategorized messages.

    Runs the heuristic classifier on every message that has no category set.

    Returns:
        Count of messages classified.
    """
    result = await db.execute(
        select(EmailMessage).where(EmailMessage.category == None)  # noqa: E711
    )
    messages = result.scalars().all()

    classified = 0
    for msg in messages:
        msg.category = classify_email(msg)
        classified += 1

    await db.commit()
    logger.info("email_classify_backfill", classified=classified)

    return ClassifyResponse(classified=classified)


# ---------------------------------------------------------------------------
# Decisions endpoint
# ---------------------------------------------------------------------------


class DecisionItem(BaseModel):
    """A single decision-requiring email."""

    id: str
    subject: str | None
    from_address: str | None
    from_name: str | None
    date_sent: str
    snippet: str | None
    decision_type: str
    urgency: str


class DecisionsResponse(BaseModel):
    """Response for decisions endpoint."""

    decisions: list[DecisionItem]
    count: int


@router.get("/v2/decisions", response_model=DecisionsResponse)
async def get_pending_decisions(
    limit: int = 20,
    db: AsyncSession = Depends(get_db),
) -> DecisionsResponse:
    """Get emails that require decisions or approvals.

    Scans recent emails for decision-requiring phrases in subject or body.

    Args:
        limit: Maximum decisions to return (default 20, max 50).
        db: Database session.

    Returns:
        List of emails requiring decisions.
    """
    from sqlalchemy import or_

    limit = min(limit, 50)

    # Decision-requiring phrases
    decision_phrases = [
        "please approve",
        "need your decision",
        "waiting for confirmation",
        "action required",
        "please confirm",
        "your approval",
        "sign off",
        "need to decide",
        "pending your",
        "RSVP",
        "deadline",
    ]

    # Build OR conditions for subject and body
    conditions = []
    for phrase in decision_phrases:
        conditions.append(EmailMessage.subject.ilike(f"%{phrase}%"))
        conditions.append(EmailMessage.body_text.ilike(f"%{phrase}%"))

    # Query for matching emails
    query = (
        select(EmailMessage)
        .where(or_(*conditions))
        .order_by(EmailMessage.date_sent.desc())
        .limit(limit)
    )

    result = await db.execute(query)
    messages = result.scalars().all()

    decisions = []
    for msg in messages:
        # Determine decision type based on keywords
        subject_lower = (msg.subject or "").lower()
        body_lower = (msg.body_text or "").lower()
        combined = subject_lower + " " + body_lower

        if "approve" in combined or "approval" in combined:
            decision_type = "approval"
        elif "confirm" in combined or "rsvp" in combined:
            decision_type = "confirmation"
        elif "deadline" in combined or "asap" in combined:
            decision_type = "deadline"
        elif "sign off" in combined:
            decision_type = "sign-off"
        else:
            decision_type = "action"

        # Determine urgency
        urgency = "normal"
        if any(prefix in subject_lower for prefix in ["re:", "fw:"]):
            urgency = "high"
        elif any(word in subject_lower for word in ["urgent", "asap", "immediate"]):
            urgency = "high"

        decisions.append(
            DecisionItem(
                id=msg.id,
                subject=msg.subject,
                from_address=msg.from_address,
                from_name=msg.from_name,
                date_sent=msg.date_sent.isoformat(),
                snippet=msg.snippet,
                decision_type=decision_type,
                urgency=urgency,
            )
        )

    logger.info("pending_decisions_retrieved", count=len(decisions))

    return DecisionsResponse(decisions=decisions, count=len(decisions))
