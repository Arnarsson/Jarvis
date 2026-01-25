"""Google Calendar incremental sync service.

Implements the sync mechanism that pulls calendar events from Google Calendar
into the local database using sync tokens for efficient incremental updates.
"""

import json
from datetime import datetime, timedelta, timezone

import structlog
from googleapiclient.errors import HttpError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from jarvis_server.calendar.models import CalendarEvent, SyncState
from jarvis_server.calendar.oauth import get_calendar_service

logger = structlog.get_logger(__name__)


async def get_sync_token(db: AsyncSession, sync_id: str = "calendar_primary") -> str | None:
    """Get stored sync token for incremental sync.

    Args:
        db: Database session.
        sync_id: Identifier for the sync state (default: calendar_primary).

    Returns:
        Sync token if exists, None otherwise.
    """
    result = await db.execute(select(SyncState).where(SyncState.id == sync_id))
    state = result.scalar_one_or_none()
    return state.token if state else None


async def save_sync_token(db: AsyncSession, sync_id: str, token: str) -> None:
    """Save or update sync token.

    Args:
        db: Database session.
        sync_id: Identifier for the sync state.
        token: The sync token to save.
    """
    result = await db.execute(select(SyncState).where(SyncState.id == sync_id))
    state = result.scalar_one_or_none()
    if state:
        state.token = token
    else:
        state = SyncState(id=sync_id, token=token)
        db.add(state)
    await db.commit()


async def delete_sync_token(db: AsyncSession, sync_id: str) -> None:
    """Delete sync token to force full resync.

    Args:
        db: Database session.
        sync_id: Identifier for the sync state to delete.
    """
    result = await db.execute(select(SyncState).where(SyncState.id == sync_id))
    state = result.scalar_one_or_none()
    if state:
        await db.delete(state)
        await db.commit()


async def sync_calendar(db: AsyncSession) -> dict:
    """Sync calendar events using incremental sync.

    On first run or when sync token expires, performs a full sync of events
    from the last 30 days to the next 90 days. Subsequent syncs use the
    sync token to fetch only changed events.

    Args:
        db: Database session.

    Returns:
        Dict with counts: {"created": N, "updated": N, "deleted": N}

    Raises:
        HttpError: If Google Calendar API fails (except 410, which triggers resync).
    """
    service = get_calendar_service()
    sync_token = await get_sync_token(db)

    created, updated, deleted = 0, 0, 0

    try:
        if sync_token:
            # Incremental sync
            logger.info("calendar_sync_incremental", sync_token=sync_token[:20] + "...")
            events_result = (
                service.events()
                .list(calendarId="primary", syncToken=sync_token)
                .execute()
            )
        else:
            # Full sync - get last 30 days and next 90 days
            logger.info("calendar_sync_full")
            time_min = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()
            events_result = (
                service.events()
                .list(
                    calendarId="primary",
                    timeMin=time_min,
                    maxResults=2500,
                    singleEvents=True,
                    orderBy="startTime",
                )
                .execute()
            )

        # Process all pages
        all_items = events_result.get("items", [])
        while "nextPageToken" in events_result:
            events_result = (
                service.events()
                .list(
                    calendarId="primary",
                    pageToken=events_result["nextPageToken"],
                )
                .execute()
            )
            all_items.extend(events_result.get("items", []))

        # Process each event
        for item in all_items:
            google_id = item["id"]

            # Check if cancelled (deleted)
            if item.get("status") == "cancelled":
                result = await db.execute(
                    select(CalendarEvent).where(CalendarEvent.google_event_id == google_id)
                )
                existing = result.scalar_one_or_none()
                if existing:
                    await db.delete(existing)
                    deleted += 1
                continue

            # Parse event data
            event_data = parse_google_event(item)

            # Upsert event
            result = await db.execute(
                select(CalendarEvent).where(CalendarEvent.google_event_id == google_id)
            )
            existing = result.scalar_one_or_none()

            if existing:
                for key, value in event_data.items():
                    setattr(existing, key, value)
                updated += 1
            else:
                event = CalendarEvent(google_event_id=google_id, **event_data)
                db.add(event)
                created += 1

        await db.commit()

        # Save new sync token
        new_token = events_result.get("nextSyncToken")
        if new_token:
            await save_sync_token(db, "calendar_primary", new_token)

        logger.info(
            "calendar_sync_complete", created=created, updated=updated, deleted=deleted
        )
        return {"created": created, "updated": updated, "deleted": deleted}

    except HttpError as e:
        if e.resp.status == 410:
            # Sync token expired - full resync needed
            logger.warning("calendar_sync_token_expired")
            await delete_sync_token(db, "calendar_primary")
            return await sync_calendar(db)  # Retry with full sync
        raise


def parse_google_event(item: dict) -> dict:
    """Parse Google Calendar event into CalendarEvent fields.

    Args:
        item: Google Calendar API event response dict.

    Returns:
        Dict with CalendarEvent field values.
    """
    # Handle all-day events vs timed events
    start = item.get("start", {})
    end = item.get("end", {})

    if "date" in start:
        # All-day event
        start_time = datetime.fromisoformat(start["date"])
        end_time = datetime.fromisoformat(end["date"])
        all_day = True
    else:
        start_time = datetime.fromisoformat(start["dateTime"])
        end_time = datetime.fromisoformat(end["dateTime"])
        all_day = False

    # Extract meeting link from conferenceData or description
    meeting_link = None
    if "conferenceData" in item:
        entry_points = item["conferenceData"].get("entryPoints", [])
        for ep in entry_points:
            if ep.get("entryPointType") == "video":
                meeting_link = ep.get("uri")
                break

    # Serialize attendees
    attendees = item.get("attendees", [])
    attendees_json = json.dumps(attendees) if attendees else None

    return {
        "summary": item.get("summary", "(No title)"),
        "description": item.get("description"),
        "location": item.get("location"),
        "start_time": start_time,
        "end_time": end_time,
        "all_day": all_day,
        "attendees_json": attendees_json,
        "meeting_link": meeting_link,
        "status": item.get("status", "confirmed"),
        "etag": item.get("etag"),
        "synced_at": datetime.now(timezone.utc),
    }
