"""People Graph API - contact frequency map and relationship radar.

Analyzes memory chunks to track:
- Contact frequency (how often mentioned)
- Recency (last mentioned)
- Context (associated projects)
- Reconnection opportunities
"""

import structlog
from datetime import datetime, timedelta, timezone
from collections import defaultdict
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from jarvis_server.config import get_settings
from jarvis_server.vector.qdrant import get_qdrant
from jarvis_server.db.session import get_db
from jarvis_server.db.models import DetectedPattern

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/api/v2/people", tags=["people"])

COLLECTION_NAME = "memory_chunks"

# Import LLM entity classifier
try:
    from jarvis_server.classification.entity_classifier import (
        get_entity_classifications,
        is_person as llm_is_person,
    )
    # Check if OpenAI API key is configured
    from jarvis_server.config import get_settings as _get_settings
    _settings = _get_settings()
    HAS_LLM_CLASSIFIER = bool(_settings.openai_api_key)
    if not HAS_LLM_CLASSIFIER:
        logger.warning("OpenAI API key not configured, using rule-based fallback")
except ImportError:
    HAS_LLM_CLASSIFIER = False
    logger.warning("LLM entity classifier not available, using rule-based fallback")

# Blocklist of known false positives (phrases/topics incorrectly tagged as people)
NAME_BLOCKLIST = {
    "operations automation",
    "changes made",
    "what changed",
    "source angel",
    "next steps",
    "key features",
    "google ads",
    "google tag",
    "google sheet",
    "google sheets",
    "google analytics",
    "google calendar",
    "analysis tool",
    "prompt engineering",
    "business developer",
    "data analysis",
    "market research",
    "user experience",
    "project manager",
    "system admin",
    "tech support",
    "customer service",
    "sales team",
    "marketing team",
    "design team",
    "dev team",
    "engineering team",
    "product team",
    "senior developer",
    "lead engineer",
    "chief architect",
    "technical lead",
    "scrum master",
    "product owner",
    "business analyst",
    "quality assurance",
    "user interface",
    "user story",
    "sprint planning",
    "code review",
    "pull request",
    "merge conflict",
    "claude desktop",
    "claude sonnet",
    "chatgpt",
    "error handling",
    "exception handling",
    "content creation",
    "content strategy",
    "seo optimization",
    "git",
    "github",
    "gitlab",
    "bitbucket",
    "docker",
    "kubernetes",
    "aws",
    "azure",
    "gcp",
    "atlas intelligence",
    "bright star",
    "north star",
    "key performance",
    "performance indicators",
    "machine learning",
    "deep learning",
    "neural network",
    "artificial intelligence",
    "bright data",
    "key results",
    "set up",
    "log in",
    "sign up",
    "sign in",
    "check out",
    "follow up",
    "scale up",
    "start up",
    "shut down",
    "break down",
    "roll out",
    "pick up",
    "environment variables",
    "atlas consulting",
    "through rate",
    "click through",
    "conversion rate",
    "bounce rate",
    "barry energy",
    "ad group",
    "ad campaign",
    "campaign performance",
    "model context",
    "context window",
    "linked",
    "linkedin",
    "open",
    "close",
    "save",
    "load",
    "run",
    "stop",
    "action items",
    "custom instructions",
    "vercel",
    "home assistant",
    "your name",
    "facebook pixel",
    "facebook ads",
    "twitter ads",
    "linkedin ads",
    "instagram ads",
    "tiktok ads",
    "social media",
    "landing page",
    "chat",
    "over time",
    "high quality",
    "seven consult",
    "docker compose",
    "coolify",
    "looker studio",
    "key observations",
    "landing pages",
    "quality score",
    "page speed",
    "load time",
    "health auto",
    "agent kit",
    "what you",
    "what we",
    "executive summary",
    "beyond beta",
    "apps script",
    "event tracking",
    "hej sven",
    "app router",
    "hello world",
    "thank you",
    "best regards",
    "tech stack",
    "key takeaways",
    "cost per",
    "dit navn",
    "shot example",
    "additional tips",
    "best practices",
    "quick start",
    "getting started",
    "environment variables",
    "key results",
    "set up",
    "through rate",
    "click through rate",
    "facebook pixel",
    "docker compose",
    "landing page",
    "landing pages",
    "web page",
    "home page",
    "contact form",
    "search bar",
    "nav bar",
    "side bar",
    "menu bar",
    "status bar",
    "tool bar",
    "scroll bar",
    "wait but",
    "target zone",
    "linear",
    "seven oceans",
    "growth hacking",
    "samlet karakter",
    "zone of",
    "rate of",
    "level of",
    "type of",
    "kind of",
    "sort of",
    "part of",
    "end of",
    "start of",
    "top of",
    "bottom of",
    "side of",
    "technical assessment",
    "together tracker",
    "consent mode",
    "ad copy",
    "next",
    "elon musk",
    "steve jobs",
    "mark zuckerberg",
    "jeff bezos",
    "bill gates",
    "larry page",
    "sergey brin",
}

# Words that indicate a phrase is NOT a person name
TOPIC_INDICATORS = {
    "automation", "system", "process", "tool", "feature", "analysis",
    "research", "management", "service", "support", "development",
    "engineering", "marketing", "design", "sales", "product",
    "platform", "software", "application", "database", "api",
    "integration", "workflow", "pipeline", "infrastructure", "deployment",
    "configuration", "optimization", "monitoring", "testing", "debugging",
    "prompt", "template", "framework", "library", "module", "component",
    "interface", "backend", "frontend", "fullstack", "devops", "cloud",
    "analytics", "metrics", "dashboard", "report", "export", "import",
    "consulting", "consultancy", "consulting", "energy", "variables",
    "variable", "constants", "parameters", "arguments", "configuration",
    "rate", "ratio", "percentage", "conversion", "click", "impression",
    "campaign", "group", "segment", "cohort", "audience", "targeting",
    "model", "context", "window", "token", "embedding", "vector",
    "items", "instructions", "pixel", "assistant", "helper", "wizard",
    "action", "custom", "default", "standard", "advanced", "basic",
    "media", "social", "page", "pages", "chat", "quality", "consult",
    "consulting", "compose", "studio", "observations", "observation",
    "speed", "score", "time", "loading", "coolify",
    "stack", "takeaways", "tips", "cost", "example", "examples",
    "practices", "quick", "getting", "started", "per",
}

# Verbs that indicate a phrase is NOT a person name
VERB_INDICATORS = {
    "made", "changed", "updated", "created", "deleted", "added", "removed",
    "modified", "fixed", "improved", "optimized", "refactored", "deployed",
    "tested", "debugged", "reviewed", "approved", "rejected", "merged",
    "committed", "pushed", "pulled", "forked", "cloned", "branched",
}

# Common first names (small sample - can be expanded)
COMMON_FIRST_NAMES = {
    "sven", "thomas", "christopher", "chris", "hjalti", "avnit", "nikolaj",
    "michael", "jesper", "daniel", "marco", "anne", "atlas", "kristian",
    "jimmy", "john", "james", "robert", "mary", "patricia", "linda",
    "barbara", "elizabeth", "jennifer", "maria", "susan", "margaret",
    "dorothy", "lisa", "nancy", "karen", "betty", "helen", "sandra",
    "donna", "carol", "ruth", "sharon", "michelle", "laura", "sarah",
    "kimberly", "deborah", "jessica", "shirley", "cynthia", "angela",
    "melissa", "brenda", "amy", "anna", "rebecca", "virginia", "kathleen",
    "david", "richard", "charles", "joseph", "donald", "kenneth",
    "steven", "edward", "brian", "ronald", "anthony", "kevin", "jason",
    "matthew", "gary", "timothy", "jose", "larry", "jeffrey", "frank",
    "scott", "eric", "stephen", "andrew", "raymond", "gregory", "joshua",
    "jerry", "dennis", "walter", "patrick", "peter", "harold", "douglas",
    "henry", "carl", "arthur", "ryan", "roger", "joe", "juan", "jack",
    "albert", "jonathan", "justin", "terry", "gerald", "keith", "samuel",
    "willie", "ralph", "lawrence", "nicholas", "roy", "benjamin", "bruce",
    "brandon", "adam", "harry", "fred", "wayne", "billy", "steve", "louis",
    "jeremy", "aaron", "randy", "howard", "eugene", "carlos", "russell",
    "bobby", "victor", "martin", "ernest", "phillip", "todd", "jesse",
    "craig", "alan", "shawn", "clarence", "sean", "philip", "chris",
    "johnny", "earl", "jimmy", "antonio", "danny", "bryan", "tony",
    "luis", "mike", "stanley", "leonard", "nathan", "dale", "manuel",
    "rodney", "curtis", "norman", "allen", "marvin", "vincent", "glenn",
    "jeffery", "travis", "jeff", "chad", "jacob", "lee", "melvin",
    "alfred", "kyle", "francis", "bradley", "jesus", "herbert", "frederick",
    "ray", "joel", "edwin", "don", "eddie", "ricky", "troy", "randall",
}


def is_likely_person_name(name: str) -> bool:
    """Determine if a string is likely a person name vs a topic/phrase.
    
    Uses multiple heuristics:
    - Blocklist check
    - Word count (1-3 words for names)
    - Contains topic indicators
    - Contains verbs
    - Starts with common first name
    - Product/brand prefixes
    """
    if not name or not name.strip():
        return False
    
    name_lower = name.lower().strip()
    
    # Check blocklist
    if name_lower in NAME_BLOCKLIST:
        return False
    
    # Reject placeholder names and common phrases
    if "your" in name_lower or "my" in name_lower:
        return False
    
    # Check for product/brand prefixes (Google X, Claude X, etc.)
    product_prefixes = ["google", "claude", "chatgpt", "openai", "microsoft", "apple", "amazon"]
    for prefix in product_prefixes:
        if name_lower.startswith(prefix + " "):
            return False
    
    # Split into words
    words = name_lower.split()
    
    # Reject phrases starting with question/greeting words
    question_words = ["what", "when", "where", "why", "how", "who", "which"]
    greeting_words = ["hello", "hi", "hey", "hej", "hola", "bonjour"]
    first_word_lower = words[0] if words else ""
    if first_word_lower in question_words or first_word_lower in greeting_words:
        return False
    
    # Names should be 1-3 words (e.g., "John", "John Smith", "Anne Clara")
    if len(words) > 3 or len(words) == 0:
        return False
    
    # Check for topic indicators
    for word in words:
        if word in TOPIC_INDICATORS:
            return False
    
    # Check for verbs
    for word in words:
        if word in VERB_INDICATORS:
            return False
    
    # Reject if contains common tech/business terms
    tech_terms = ["error", "exception", "handling", "creation", "strategy", "optimization", 
                  "intelligence", "star", "performance", "indicators", "learning", "network",
                  "data", "results", "insights", "metrics", "report", "dashboard"]
    for term in tech_terms:
        if term in name_lower:
            return False
    
    # Reject two-word phrases that are clearly actions or commands
    if len(words) == 2:
        action_patterns = [
            ("set", "up"), ("log", "in"), ("sign", "up"), ("sign", "in"),
            ("check", "out"), ("follow", "up"), ("scale", "up"), ("start", "up"),
            ("shut", "down"), ("break", "down"), ("roll", "out"), ("pick", "up"),
            ("key", "results"), ("key", "performance"),
        ]
        word_tuple = tuple(words)
        if word_tuple in action_patterns:
            return False
    
    # Check if first word is a common first name
    first_word = words[0]
    if first_word in COMMON_FIRST_NAMES:
        return True
    
    # If single word and not a common name, likely not a person
    if len(words) == 1:
        # Reject common single-word verbs/actions even if capitalized
        single_word_blocklist = [
            "git", "docker", "aws", "gcp", "api", "sdk", "cli",
            "open", "close", "save", "load", "run", "stop", "start",
            "linked", "link", "connect", "sync", "export", "import",
            "create", "delete", "update", "edit", "view", "read", "write",
            "vercel", "netlify", "heroku", "railway", "render",
            "danish", "english", "french", "german", "spanish", "italian",
            "google", "facebook", "twitter", "linkedin", "instagram", "tiktok",
            "apple", "microsoft", "amazon", "netflix", "spotify", "uber",
            "linear", "notion", "slack", "discord", "zoom", "teams",
            "figma", "sketch", "photoshop", "illustrator", "canva",
            "trello", "asana", "jira", "github", "gitlab", "bitbucket",
        ]
        if name_lower in single_word_blocklist:
            return False
        
        # Reject well-known companies/brands
        if name_lower in ["google", "facebook", "apple", "microsoft", "amazon", "linear"]:
            return False
        
        # Reject possessive forms (ends with 's but not common names)
        if name_lower.endswith("s") and name_lower not in COMMON_FIRST_NAMES:
            # Could be "Johns", "Mikes", etc. - likely possessive
            base_name = name_lower[:-1]
            if base_name in COMMON_FIRST_NAMES:
                return False  # Likely possessive like "Sven's"
        
        # Could be a nickname or uncommon name, but be conservative
        # Check if it's capitalized in original (proper noun indicator)
        if name[0].isupper():
            # Additional check: single word names should be at least 3 chars
            if len(name) >= 3:
                return True
        return False
    
    # For 2-3 word names, check if at least one word is a known first name
    for word in words:
        if word in COMMON_FIRST_NAMES:
            return True
    
    # If we reach here, it's a 2-3 word phrase without known names
    # Check if it's capitalized (proper noun) - conservative allow
    if all(w[0].isupper() for w in name.split() if w):
        # Still reject if it contains common non-name patterns
        if any(indicator in name_lower for indicator in ["tool", "system", "process"]):
            return False
        return True
    
    return False


# Response Models
class PersonContact(BaseModel):
    """Contact information for a person."""
    name: str
    frequency: int
    last_seen: str | None
    first_seen: str | None
    days_since_contact: int | None
    projects: list[str]
    topics: list[str]
    status: str  # active, fading, stale
    suggested_action: str | None
    conversation_count: int


class PeopleGraphResponse(BaseModel):
    """People graph with contact frequency map."""
    contacts: list[PersonContact]
    total_people: int
    active_count: int  # contacted in last 7 days
    fading_count: int  # 7-30 days
    stale_count: int  # 30+ days
    top_5: list[str]  # most frequently mentioned


@router.get("/graph", response_model=PeopleGraphResponse)
async def people_graph(
    min_frequency: int = Query(3, ge=1, description="Minimum mentions to include"),
    limit: int = Query(100, ge=1, le=500, description="Max people to return"),
    db: AsyncSession = Depends(get_db),
) -> PeopleGraphResponse:
    """Generate contact frequency map from memory chunks.
    
    Scans conversation history to identify:
    - Who you talk about most
    - When you last mentioned them
    - What projects they're associated with
    - Reconnection opportunities
    """
    try:
        qdrant = get_qdrant()
        now = datetime.now(timezone.utc)
        
        logger.info("people_graph_scan_starting", min_frequency=min_frequency)
        
        # Track people data
        people_tracker = defaultdict(lambda: {
            "count": 0,
            "conversations": set(),
            "dates": [],
            "projects": set(),
            "topics": set(),
        })
        
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
                    date_str = payload.get("conversation_date")
                    
                    # Parse date
                    chunk_date = None
                    if date_str:
                        try:
                            chunk_date = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
                        except:
                            pass
                    
                    # Track people (collect all for now, will filter with LLM later)
                    for person in payload.get("people", []):
                        # Quick basic filtering (very short names, empty strings)
                        if not person or len(person.strip()) < 2:
                            continue
                        
                        people_tracker[person]["count"] += 1
                        people_tracker[person]["conversations"].add(conversation_id)
                        if chunk_date:
                            people_tracker[person]["dates"].append(chunk_date)
                        
                        # Track associated projects
                        for project in payload.get("projects", []):
                            people_tracker[person]["projects"].add(project)
                        
                        # Track associated topics
                        for topic in payload.get("topics", []):
                            people_tracker[person]["topics"].add(topic)
                
                total_scanned += len(points)
                if total_scanned % 10000 == 0:
                    logger.info(f"Scanned {total_scanned} chunks...")
                
                if next_offset is None:
                    break
                
                offset = next_offset
                
            except Exception as e:
                logger.error(f"Error during scan: {e}")
                break
        
        logger.info(
            "people_graph_scan_complete",
            total_scanned=total_scanned,
            people_found=len(people_tracker),
        )
        
        # Use LLM to classify entities if available
        if HAS_LLM_CLASSIFIER:
            logger.info("classifying_entities_with_llm", count=len(people_tracker))
            try:
                all_entities = list(people_tracker.keys())
                classifications = await get_entity_classifications(all_entities, db)
                
                # Filter to only entities classified as PERSON
                people_tracker = {
                    name: data
                    for name, data in people_tracker.items()
                    if llm_is_person(name, classifications.get(name, "NOISE"))
                }
                
                logger.info(
                    "llm_classification_complete",
                    total_entities=len(all_entities),
                    people_found=len(people_tracker),
                )
            except Exception as e:
                logger.error("llm_classification_failed", error=str(e))
                # Fall back to rule-based filtering
                people_tracker = {
                    name: data
                    for name, data in people_tracker.items()
                    if is_likely_person_name(name)
                }
        else:
            # Use rule-based filtering
            people_tracker = {
                name: data
                for name, data in people_tracker.items()
                if is_likely_person_name(name)
            }
        
        # Filter by minimum frequency
        filtered_people = {
            name: data
            for name, data in people_tracker.items()
            if data["count"] >= min_frequency
        }
        
        logger.info(
            "people_filtered",
            after_classification=len(people_tracker),
            after_min_frequency=len(filtered_people),
            min_frequency=min_frequency,
        )
        
        # Build contact list
        contacts = []
        active_count = 0
        fading_count = 0
        stale_count = 0
        
        for name, data in filtered_people.items():
            dates = sorted(data["dates"]) if data["dates"] else []
            first_seen = dates[0] if dates else None
            last_seen = dates[-1] if dates else None
            
            # Calculate days since contact
            days_since = None
            status = "unknown"
            suggested_action = None
            
            if last_seen:
                delta = now - last_seen
                days_since = delta.days
                
                if days_since <= 7:
                    status = "active"
                    active_count += 1
                    suggested_action = f"Stay in touch with {name}"
                elif days_since <= 30:
                    status = "fading"
                    fading_count += 1
                    suggested_action = f"Consider reaching out to {name}"
                else:
                    status = "stale"
                    stale_count += 1
                    suggested_action = f"Reconnect with {name} (no contact for {days_since} days)"
            
            contacts.append(PersonContact(
                name=name,
                frequency=data["count"],
                last_seen=last_seen.isoformat() if last_seen else None,
                first_seen=first_seen.isoformat() if first_seen else None,
                days_since_contact=days_since,
                projects=list(data["projects"])[:10],  # Limit to 10
                topics=list(data["topics"])[:10],
                status=status,
                suggested_action=suggested_action,
                conversation_count=len(data["conversations"]),
            ))
        
        # Sort by frequency descending
        contacts.sort(key=lambda x: x.frequency, reverse=True)
        
        # Get top 5 names
        top_5 = [c.name for c in contacts[:5]]
        
        # Apply limit
        contacts = contacts[:limit]
        
        logger.info(
            "people_graph_generated",
            total_people=len(contacts),
            active=active_count,
            fading=fading_count,
            stale=stale_count,
        )
        
        return PeopleGraphResponse(
            contacts=contacts,
            total_people=len(contacts),
            active_count=active_count,
            fading_count=fading_count,
            stale_count=stale_count,
            top_5=top_5,
        )
        
    except Exception as e:
        logger.error("people_graph_failed", error=str(e), exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to generate people graph")
