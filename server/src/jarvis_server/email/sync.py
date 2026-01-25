"""Gmail incremental sync service.

Implements the sync mechanism that pulls email messages from Gmail
into the local database using the History API for efficient incremental updates.
"""

import base64
import json
from datetime import datetime, timezone
from email.utils import parseaddr, parsedate_to_datetime

import structlog
from googleapiclient.errors import HttpError
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from jarvis_server.email.models import EmailMessage, EmailSyncState
from jarvis_server.email.oauth import get_gmail_service, GmailAuthRequired

logger = structlog.get_logger(__name__)


async def get_history_id(db: AsyncSession, sync_id: str = "gmail_primary") -> str | None:
    """Get stored history ID for incremental sync.

    Args:
        db: Database session.
        sync_id: Identifier for the sync state (default: gmail_primary).

    Returns:
        History ID if exists, None otherwise.
    """
    result = await db.execute(
        select(EmailSyncState).where(EmailSyncState.id == sync_id)
    )
    state = result.scalar_one_or_none()
    return state.history_id if state else None


async def save_history_id(db: AsyncSession, sync_id: str, history_id: str) -> None:
    """Save or update history ID.

    Args:
        db: Database session.
        sync_id: Identifier for the sync state.
        history_id: The history ID to save.
    """
    result = await db.execute(
        select(EmailSyncState).where(EmailSyncState.id == sync_id)
    )
    state = result.scalar_one_or_none()
    if state:
        state.history_id = history_id
    else:
        state = EmailSyncState(id=sync_id, history_id=history_id)
        db.add(state)
    await db.commit()


async def delete_history_id(db: AsyncSession, sync_id: str) -> None:
    """Delete history ID to force full resync.

    Args:
        db: Database session.
        sync_id: Identifier for the sync state to delete.
    """
    result = await db.execute(
        select(EmailSyncState).where(EmailSyncState.id == sync_id)
    )
    state = result.scalar_one_or_none()
    if state:
        await db.delete(state)
        await db.commit()


def parse_email_headers(headers: list[dict]) -> dict:
    """Parse Gmail message headers into dict.

    Args:
        headers: List of header dicts from Gmail API (name, value pairs).

    Returns:
        Dict with Subject, From (name, address), To, Cc, Date.
    """
    result = {
        "subject": None,
        "from_name": None,
        "from_address": None,
        "to_addresses": None,
        "cc_addresses": None,
        "date": None,
    }

    header_map = {h["name"].lower(): h["value"] for h in headers}

    result["subject"] = header_map.get("subject")

    # Parse From header into name and address
    from_header = header_map.get("from", "")
    if from_header:
        name, address = parseaddr(from_header)
        result["from_name"] = name if name else None
        result["from_address"] = address if address else from_header

    # Parse To addresses (can be multiple)
    to_header = header_map.get("to")
    if to_header:
        # Store as JSON array of addresses
        addresses = [parseaddr(addr)[1] or addr.strip() for addr in to_header.split(",")]
        result["to_addresses"] = json.dumps(addresses)

    # Parse Cc addresses
    cc_header = header_map.get("cc")
    if cc_header:
        addresses = [parseaddr(addr)[1] or addr.strip() for addr in cc_header.split(",")]
        result["cc_addresses"] = json.dumps(addresses)

    # Parse Date
    date_header = header_map.get("date")
    if date_header:
        try:
            result["date"] = parsedate_to_datetime(date_header)
        except Exception:
            # Fallback to now if date parsing fails
            result["date"] = datetime.now(timezone.utc)

    return result


def extract_body_text(payload: dict) -> str:
    """Extract plain text body from message payload.

    Handles multipart messages, prefers text/plain,
    falls back to text/html with HTML tag stripping.

    Args:
        payload: Gmail message payload dict.

    Returns:
        Plain text body content, or empty string if none found.
    """
    # Try to find text/plain first, then text/html
    plain_text = _find_body_part(payload, "text/plain")
    if plain_text:
        return plain_text

    html_text = _find_body_part(payload, "text/html")
    if html_text:
        return _strip_html(html_text)

    return ""


def _find_body_part(payload: dict, mime_type: str) -> str | None:
    """Recursively find body part with given MIME type.

    Args:
        payload: Gmail message payload or part.
        mime_type: MIME type to look for (e.g., 'text/plain').

    Returns:
        Decoded body text if found, None otherwise.
    """
    # Check if this part matches
    if payload.get("mimeType") == mime_type:
        body = payload.get("body", {})
        data = body.get("data")
        if data:
            return base64.urlsafe_b64decode(data).decode("utf-8", errors="replace")

    # Check nested parts
    parts = payload.get("parts", [])
    for part in parts:
        result = _find_body_part(part, mime_type)
        if result:
            return result

    return None


def _strip_html(html: str) -> str:
    """Strip HTML tags from text.

    Uses BeautifulSoup if available, falls back to regex.

    Args:
        html: HTML string to strip.

    Returns:
        Plain text with HTML tags removed.
    """
    try:
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(html, "html.parser")
        # Remove script and style elements
        for script in soup(["script", "style"]):
            script.decompose()
        # Get text with newlines preserved
        text = soup.get_text(separator="\n")
        # Clean up whitespace
        lines = (line.strip() for line in text.splitlines())
        return "\n".join(line for line in lines if line)
    except ImportError:
        # Fallback: simple regex stripping
        import re
        clean = re.sub(r"<[^>]+>", "", html)
        return clean.strip()


async def get_message_full(service, message_id: str) -> dict:
    """Fetch full message details from Gmail.

    Args:
        service: Gmail API service.
        message_id: Gmail message ID.

    Returns:
        Full message dict from Gmail API.
    """
    return service.users().messages().get(
        userId="me", id=message_id, format="full"
    ).execute()


async def store_message(db: AsyncSession, message: dict) -> tuple[bool, bool]:
    """Store or update a message in the database.

    Args:
        db: Database session.
        message: Full Gmail message dict.

    Returns:
        Tuple of (was_created, was_updated).
    """
    gmail_id = message["id"]
    thread_id = message["threadId"]

    # Check if exists
    result = await db.execute(
        select(EmailMessage).where(EmailMessage.gmail_message_id == gmail_id)
    )
    existing = result.scalar_one_or_none()

    # Parse message details
    payload = message.get("payload", {})
    headers = payload.get("headers", [])
    parsed = parse_email_headers(headers)
    body_text = extract_body_text(payload)

    # Get labels
    labels = message.get("labelIds", [])
    is_unread = "UNREAD" in labels
    is_important = "IMPORTANT" in labels

    # Determine date_sent
    date_sent = parsed.get("date") or datetime.now(timezone.utc)

    message_data = {
        "thread_id": thread_id,
        "subject": parsed.get("subject"),
        "from_address": parsed.get("from_address"),
        "from_name": parsed.get("from_name"),
        "to_addresses": parsed.get("to_addresses"),
        "cc_addresses": parsed.get("cc_addresses"),
        "snippet": message.get("snippet"),
        "body_text": body_text,
        "date_sent": date_sent,
        "labels_json": json.dumps(labels) if labels else None,
        "is_unread": is_unread,
        "is_important": is_important,
        "synced_at": datetime.now(timezone.utc),
    }

    if existing:
        for key, value in message_data.items():
            setattr(existing, key, value)
        return (False, True)
    else:
        email = EmailMessage(gmail_message_id=gmail_id, **message_data)
        db.add(email)
        return (True, False)


async def initial_sync(
    service, db: AsyncSession, days_back: int = 30
) -> tuple[int, str]:
    """Full sync of recent messages.

    Args:
        service: Gmail API service.
        db: Database session.
        days_back: Number of days back to sync (default 30).

    Returns:
        Tuple of (message_count, history_id).
    """
    logger.info("email_sync_initial", days_back=days_back)

    # Query recent messages
    query = f"newer_than:{days_back}d"
    messages_result = service.users().messages().list(
        userId="me", q=query, maxResults=500
    ).execute()

    all_message_refs = messages_result.get("messages", [])

    # Handle pagination
    while "nextPageToken" in messages_result:
        messages_result = service.users().messages().list(
            userId="me",
            q=query,
            maxResults=500,
            pageToken=messages_result["nextPageToken"],
        ).execute()
        all_message_refs.extend(messages_result.get("messages", []))

    logger.info("email_sync_fetching", count=len(all_message_refs))

    # Fetch and store each message
    count = 0
    for msg_ref in all_message_refs:
        try:
            message = await get_message_full(service, msg_ref["id"])
            created, _ = await store_message(db, message)
            if created:
                count += 1
        except Exception as e:
            logger.warning("email_sync_message_error", message_id=msg_ref["id"], error=str(e))

    await db.commit()

    # Get current history ID from profile
    profile = service.users().getProfile(userId="me").execute()
    history_id = profile.get("historyId")

    logger.info("email_sync_initial_complete", messages=count, history_id=history_id)
    return (count, history_id)


async def incremental_sync(
    service, db: AsyncSession, start_history_id: str
) -> tuple[int, int, int, str]:
    """Incremental sync using Gmail History API.

    Args:
        service: Gmail API service.
        db: Database session.
        start_history_id: History ID from last sync.

    Returns:
        Tuple of (created, updated, deleted, new_history_id).
    """
    logger.info("email_sync_incremental", start_history_id=start_history_id)

    created, updated, deleted = 0, 0, 0
    new_history_id = start_history_id

    try:
        history_result = service.users().history().list(
            userId="me",
            startHistoryId=start_history_id,
            historyTypes=["messageAdded", "messageDeleted"],
        ).execute()

        # Collect all history records
        all_history = history_result.get("history", [])
        while "nextPageToken" in history_result:
            history_result = service.users().history().list(
                userId="me",
                startHistoryId=start_history_id,
                historyTypes=["messageAdded", "messageDeleted"],
                pageToken=history_result["nextPageToken"],
            ).execute()
            all_history.extend(history_result.get("history", []))

        # Process history records
        added_ids = set()
        deleted_ids = set()

        for record in all_history:
            # Handle added messages
            for added in record.get("messagesAdded", []):
                msg_id = added["message"]["id"]
                added_ids.add(msg_id)
                # Remove from deleted if it was there (message moved)
                deleted_ids.discard(msg_id)

            # Handle deleted messages
            for deleted_rec in record.get("messagesDeleted", []):
                msg_id = deleted_rec["message"]["id"]
                deleted_ids.add(msg_id)
                # Remove from added if it was there
                added_ids.discard(msg_id)

        # Fetch and store added messages
        for msg_id in added_ids:
            try:
                message = await get_message_full(service, msg_id)
                was_created, was_updated = await store_message(db, message)
                if was_created:
                    created += 1
                elif was_updated:
                    updated += 1
            except HttpError as e:
                if e.resp.status == 404:
                    # Message was deleted before we could fetch it
                    logger.debug("email_sync_message_gone", message_id=msg_id)
                else:
                    logger.warning("email_sync_message_error", message_id=msg_id, error=str(e))
            except Exception as e:
                logger.warning("email_sync_message_error", message_id=msg_id, error=str(e))

        # Mark deleted messages
        for msg_id in deleted_ids:
            result = await db.execute(
                select(EmailMessage).where(EmailMessage.gmail_message_id == msg_id)
            )
            existing = result.scalar_one_or_none()
            if existing:
                await db.delete(existing)
                deleted += 1

        await db.commit()

        # Get new history ID
        new_history_id = history_result.get("historyId", start_history_id)

    except HttpError as e:
        if e.resp.status in (404, 410):
            # History ID expired or invalid - need full resync
            logger.warning("email_sync_history_expired")
            raise
        raise

    logger.info(
        "email_sync_incremental_complete",
        created=created, updated=updated, deleted=deleted,
        new_history_id=new_history_id,
    )
    return (created, updated, deleted, new_history_id)


async def sync_emails(db: AsyncSession, full_sync: bool = False) -> dict:
    """Main sync entry point.

    Performs either initial or incremental sync based on state.

    Args:
        db: Database session.
        full_sync: Force full sync even if history ID exists.

    Returns:
        Dict with counts: {"created": N, "updated": N, "deleted": N}

    Raises:
        GmailAuthRequired: If not authenticated with Gmail.
    """
    service = get_gmail_service()
    history_id = await get_history_id(db)

    created, updated, deleted = 0, 0, 0

    try:
        if full_sync or not history_id:
            # Initial sync
            count, new_history_id = await initial_sync(service, db)
            created = count
            await save_history_id(db, "gmail_primary", new_history_id)
        else:
            # Incremental sync
            created, updated, deleted, new_history_id = await incremental_sync(
                service, db, history_id
            )
            await save_history_id(db, "gmail_primary", new_history_id)

    except HttpError as e:
        if e.resp.status in (404, 410) and history_id:
            # History expired - do full resync
            logger.warning("email_sync_history_invalid_resync")
            await delete_history_id(db, "gmail_primary")
            return await sync_emails(db, full_sync=True)
        raise

    return {"created": created, "updated": updated, "deleted": deleted}
