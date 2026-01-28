"""Conversation pattern detector - analyzes memory chunks for recurring themes and patterns.

Run with: python -m jarvis_server.patterns.conversation_detector
"""

import asyncio
import logging
from datetime import datetime, timedelta
from collections import defaultdict
from uuid import uuid4

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from jarvis_server.config import get_settings
from jarvis_server.db.session import AsyncSessionLocal
from jarvis_server.db.models import DetectedPattern
from jarvis_server.vector.qdrant import get_qdrant

logger = structlog.get_logger(__name__)

COLLECTION_NAME = "memory_chunks"
COMMITMENT_PHRASES = [
    "i'll do",
    "i'll follow up",
    "let's follow up",
    "next week we should",
    "i'll get back to you",
    "i'll send",
    "i'll share",
    "i'll check",
    "i'll look into",
    "i'll reach out",
    "remind me to",
    "todo:",
    "need to do",
]


async def scan_memory_chunks():
    """Scan all memory chunks and extract metadata."""
    qdrant = get_qdrant()
    
    logger.info("Starting memory scan...")
    
    # Track patterns
    people_tracker = defaultdict(lambda: {"count": 0, "conversations": set(), "dates": []})
    topics_tracker = defaultdict(lambda: {"count": 0, "conversations": set(), "dates": []})
    projects_tracker = defaultdict(lambda: {"count": 0, "conversations": set(), "dates": []})
    commitment_tracker = []
    
    # Scroll through all points
    offset = None
    total_scanned = 0
    
    while True:
        try:
            result = qdrant.client.scroll(
                collection_name=COLLECTION_NAME,
                limit=1000,
                offset=offset,
                with_payload=True,
                with_vectors=False,
            )
            
            points, next_offset = result
            
            if not points:
                break
            
            for point in points:
                payload = point.payload or {}
                
                # Extract metadata
                conversation_id = payload.get("conversation_id", "")
                chunk_text = payload.get("chunk_text", "").lower()
                date_str = payload.get("conversation_date")
                
                # Parse date
                chunk_date = None
                if date_str:
                    try:
                        chunk_date = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
                    except:
                        pass
                
                # Track people
                for person in payload.get("people", []):
                    people_tracker[person]["count"] += 1
                    people_tracker[person]["conversations"].add(conversation_id)
                    if chunk_date:
                        people_tracker[person]["dates"].append(chunk_date)
                
                # Track topics
                for topic in payload.get("topics", []):
                    topics_tracker[topic]["count"] += 1
                    topics_tracker[topic]["conversations"].add(conversation_id)
                    if chunk_date:
                        topics_tracker[topic]["dates"].append(chunk_date)
                
                # Track projects
                for project in payload.get("projects", []):
                    projects_tracker[project]["count"] += 1
                    projects_tracker[project]["conversations"].add(conversation_id)
                    if chunk_date:
                        projects_tracker[project]["dates"].append(chunk_date)
                
                # Detect commitment phrases
                for phrase in COMMITMENT_PHRASES:
                    if phrase in chunk_text:
                        commitment_tracker.append({
                            "text": chunk_text[:200],
                            "conversation_id": conversation_id,
                            "date": chunk_date,
                            "phrase": phrase,
                        })
            
            total_scanned += len(points)
            if total_scanned % 5000 == 0:
                logger.info(f"Scanned {total_scanned} chunks...")
            
            if next_offset is None:
                break
            
            offset = next_offset
            
        except Exception as e:
            logger.error(f"Error during scan: {e}")
            break
    
    logger.info(f"Scan complete: {total_scanned} chunks analyzed")
    
    return {
        "people": people_tracker,
        "topics": topics_tracker,
        "projects": projects_tracker,
        "commitments": commitment_tracker,
    }


async def detect_patterns(scan_data: dict):
    """Detect patterns from scanned data and save to database."""
    async with AsyncSessionLocal() as session:
        patterns = []
        from datetime import timezone
        now = datetime.now(timezone.utc)
        thirty_days_ago = now - timedelta(days=30)
        
        # Pattern 1: Recurring people (mentioned 5+ times)
        for person, data in scan_data["people"].items():
            if data["count"] >= 5:
                dates = sorted(data["dates"]) if data["dates"] else []
                first_seen = dates[0] if dates else now
                last_seen = dates[-1] if dates else now
                
                # Check if person hasn't been mentioned recently
                is_stale = last_seen < thirty_days_ago if dates else False
                
                pattern = DetectedPattern(
                    id=str(uuid4()),
                    pattern_type="recurring_person" if not is_stale else "stale_person",
                    pattern_key=person,
                    description=f"{person} mentioned {data['count']} times across {len(data['conversations'])} conversations",
                    frequency=data["count"],
                    first_seen=first_seen,
                    last_seen=last_seen,
                    suggested_action=f"Reach out to {person}" if is_stale else f"Keep in touch with {person}",
                    status="active",
                )
                pattern.conversation_ids = list(data["conversations"])[:20]  # Limit to 20
                patterns.append(pattern)
        
        # Pattern 2: Recurring topics (mentioned 10+ times)
        for topic, data in scan_data["topics"].items():
            if data["count"] >= 10:
                dates = sorted(data["dates"]) if data["dates"] else []
                first_seen = dates[0] if dates else now
                last_seen = dates[-1] if dates else now
                
                is_stale = last_seen < thirty_days_ago if dates else False
                
                pattern = DetectedPattern(
                    id=str(uuid4()),
                    pattern_type="recurring_topic" if not is_stale else "unfinished_business",
                    pattern_key=topic,
                    description=f"'{topic}' discussed {data['count']} times across {len(data['conversations'])} conversations",
                    frequency=data["count"],
                    first_seen=first_seen,
                    last_seen=last_seen,
                    suggested_action=f"Review status of {topic}" if is_stale else f"Actively discussing {topic}",
                    status="active",
                )
                pattern.conversation_ids = list(data["conversations"])[:20]
                patterns.append(pattern)
        
        # Pattern 3: Stale projects (mentioned 5+ times but not recently)
        for project, data in scan_data["projects"].items():
            if data["count"] >= 5:
                dates = sorted(data["dates"]) if data["dates"] else []
                first_seen = dates[0] if dates else now
                last_seen = dates[-1] if dates else now
                
                is_stale = last_seen < thirty_days_ago if dates else False
                
                if is_stale:
                    pattern = DetectedPattern(
                        id=str(uuid4()),
                        pattern_type="stale_project",
                        pattern_key=project,
                        description=f"Project '{project}' was discussed {data['count']} times but hasn't been mentioned in 30+ days",
                        frequency=data["count"],
                        first_seen=first_seen,
                        last_seen=last_seen,
                        suggested_action=f"Check status of {project} - may need follow-up",
                        status="active",
                    )
                    pattern.conversation_ids = list(data["conversations"])[:20]
                    patterns.append(pattern)
        
        # Pattern 4: Broken promises (commitments from 7+ days ago)
        seven_days_ago = now - timedelta(days=7)
        for commitment in scan_data["commitments"]:
            if commitment["date"] and commitment["date"] < seven_days_ago:
                pattern = DetectedPattern(
                    id=str(uuid4()),
                    pattern_type="broken_promise",
                    pattern_key=commitment["phrase"],
                    description=f"Commitment made {(now - commitment['date']).days} days ago: '{commitment['text'][:100]}...'",
                    frequency=1,
                    first_seen=commitment["date"],
                    last_seen=commitment["date"],
                    suggested_action=f"Follow up on commitment: '{commitment['phrase']}'",
                    status="active",
                )
                pattern.conversation_ids = [commitment["conversation_id"]]
                patterns.append(pattern)
        
        # Save patterns to database
        logger.info(f"Detected {len(patterns)} patterns")
        
        # Clear old active patterns first
        await session.execute(
            select(DetectedPattern).where(DetectedPattern.status == "active")
        )
        result = await session.execute(
            select(DetectedPattern).where(DetectedPattern.status == "active")
        )
        old_patterns = result.scalars().all()
        for old in old_patterns:
            old.status = "dismissed"
        
        # Add new patterns
        for pattern in patterns:
            session.add(pattern)
        
        await session.commit()
        logger.info(f"Saved {len(patterns)} patterns to database")
        
        return patterns


async def main():
    """Main pattern detection pipeline."""
    logger.info("=" * 60)
    logger.info("CONVERSATION PATTERN DETECTOR")
    logger.info("=" * 60)
    
    # Scan memory chunks
    scan_data = await scan_memory_chunks()
    
    # Detect patterns
    patterns = await detect_patterns(scan_data)
    
    # Summary
    logger.info("=" * 60)
    logger.info("DETECTION COMPLETE")
    logger.info("=" * 60)
    logger.info(f"Recurring people: {sum(1 for p in patterns if p.pattern_type == 'recurring_person')}")
    logger.info(f"Stale people: {sum(1 for p in patterns if p.pattern_type == 'stale_person')}")
    logger.info(f"Recurring topics: {sum(1 for p in patterns if p.pattern_type == 'recurring_topic')}")
    logger.info(f"Unfinished business: {sum(1 for p in patterns if p.pattern_type == 'unfinished_business')}")
    logger.info(f"Stale projects: {sum(1 for p in patterns if p.pattern_type == 'stale_project')}")
    logger.info(f"Broken promises: {sum(1 for p in patterns if p.pattern_type == 'broken_promise')}")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())
