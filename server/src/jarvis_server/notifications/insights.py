"""Proactive insights detector for follow-up opportunities."""

import structlog
from datetime import datetime, timedelta, timezone
from typing import List
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from jarvis_server.db.session import AsyncSessionLocal

logger = structlog.get_logger(__name__)


class Insight:
    """A proactive insight to push to the user."""
    
    def __init__(self, message: str, priority: int = 0):
        self.message = message
        self.priority = priority  # Higher = more important


async def detect_follow_up_opportunities() -> List[Insight]:
    """Detect people who haven't been contacted in a while.
    
    Analyzes conversation patterns to find people who:
    - Were contacted regularly in the past
    - Haven't been contacted recently (>5 days)
    - Might need a follow-up
    
    Returns:
        List of Insight objects with follow-up suggestions
    """
    insights = []
    
    async with AsyncSessionLocal() as db:
        try:
            # Query for people mentioned in conversations with timing analysis
            query = text("""
                WITH person_mentions AS (
                    -- Get all conversations mentioning people (heuristic: capitalized names)
                    SELECT 
                        DISTINCT unnest(
                            regexp_matches(full_text, '\\m[A-Z][a-z]+(?:\\s+[A-Z][a-z]+)*\\m', 'g')
                        ) as person_name,
                        conversation_date::date as mention_date
                    FROM conversations
                    WHERE conversation_date IS NOT NULL
                        AND conversation_date > NOW() - INTERVAL '60 days'
                        AND source IN ('telegram', 'whatsapp', 'slack')
                ),
                person_stats AS (
                    SELECT 
                        person_name,
                        COUNT(*) as mention_count,
                        MAX(mention_date) as last_mention,
                        MIN(mention_date) as first_mention,
                        NOW()::date - MAX(mention_date) as days_since_last
                    FROM person_mentions
                    GROUP BY person_name
                    HAVING COUNT(*) >= 3  -- At least 3 mentions (regular contact)
                )
                SELECT 
                    person_name,
                    mention_count,
                    last_mention,
                    days_since_last
                FROM person_stats
                WHERE days_since_last >= 5  -- Haven't talked in 5+ days
                    AND days_since_last <= 30  -- But not so long it's irrelevant
                    AND mention_count >= 3
                ORDER BY days_since_last DESC
                LIMIT 5  -- Top 5 follow-ups
            """)
            
            result = await db.execute(query)
            rows = result.fetchall()
            
            for row in rows:
                person_name = row[0]
                days_since = row[3]
                mention_count = row[1]
                
                # Skip common false positives
                if person_name.lower() in ['google', 'github', 'claude', 'openai', 'linear']:
                    continue
                
                # Create insight message
                if days_since >= 14:
                    message = f"🔔 Haven't followed up with {person_name} in {days_since} days (usually chat ~{mention_count}x/month)"
                    priority = 2
                elif days_since >= 7:
                    message = f"💬 It's been {days_since} days since you talked to {person_name}"
                    priority = 1
                else:
                    message = f"👋 Check in with {person_name}? ({days_since} days)"
                    priority = 0
                
                insights.append(Insight(message, priority))
                logger.info(
                    "follow_up_opportunity_detected",
                    person=person_name,
                    days_since=days_since,
                )
            
        except Exception as e:
            logger.error("follow_up_detection_failed", error=str(e), exc_info=True)
    
    return insights


async def detect_all_insights() -> List[Insight]:
    """Detect all types of proactive insights.
    
    Returns:
        List of all insights, sorted by priority
    """
    all_insights = []
    
    # Detect follow-up opportunities
    follow_ups = await detect_follow_up_opportunities()
    all_insights.extend(follow_ups)
    
    # TODO: Add more insight types here:
    # - Upcoming meetings without agenda
    # - Promises/commitments due soon
    # - Patterns detected in screen captures
    # - Important emails without response
    
    # Sort by priority (highest first)
    all_insights.sort(key=lambda x: x.priority, reverse=True)
    
    return all_insights
