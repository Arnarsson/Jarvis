"""Project Pulse API - weekly heartbeat for project activity.

Tracks project momentum by analyzing:
- Conversation mentions (last 7 days vs previous 7 days)
- GitHub commits (if repo detected)
- Email mentions
- Activity trend (warming/cooling)
"""

import structlog
import subprocess
from datetime import datetime, timedelta, timezone
from collections import defaultdict
from fastapi import APIRouter, HTTPException, Query, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from jarvis_server.config import get_settings
from jarvis_server.vector.qdrant import get_qdrant
from jarvis_server.db.session import get_db

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/api/v2/projects", tags=["projects"])

COLLECTION_NAME = "memory_chunks"

# Import LLM entity classifier
try:
    from jarvis_server.classification.entity_classifier import (
        get_entity_classifications,
        is_project as llm_is_project,
    )
    # Check if OpenAI API key is configured
    settings = get_settings()
    HAS_LLM_CLASSIFIER = bool(settings.openai_api_key)
    if not HAS_LLM_CLASSIFIER:
        logger.warning("OpenAI API key not configured, using rule-based fallback")
except ImportError:
    HAS_LLM_CLASSIFIER = False
    logger.warning("LLM entity classifier not available, using rule-based fallback")

# Known real projects (whitelist)
KNOWN_PROJECTS = {
    "recruitos",
    "jarvis",
    "cmp",
    "sourcetrace",
    "recruitos",
    "jarvis",
    "cmp",
    "sourcetrace",
    "atlas intelligence",
    "nerd",
    "koda",
    "danbolig",
    "source angel",
    "jbia",
    "clawdbot",
    "eureka",
    "dozy",
    "dronewatch",
    "skillsync",
}

# Common English words that are NOT projects
COMMON_ENGLISH_WORDS = {
    "this", "that", "these", "those", "the", "a", "an", "and", "or", "but",
    "if", "then", "else", "when", "where", "what", "why", "how", "who", "which",
    "is", "are", "was", "were", "be", "been", "being", "have", "has", "had",
    "do", "does", "did", "will", "would", "should", "could", "may", "might",
    "can", "must", "shall", "to", "of", "in", "on", "at", "by", "for", "with",
    "from", "as", "about", "into", "through", "during", "before", "after",
    "above", "below", "between", "under", "over", "up", "down", "out", "off",
    "again", "further", "then", "once", "here", "there", "all", "both", "each",
    "few", "more", "most", "other", "some", "such", "no", "nor", "not", "only",
    "own", "same", "so", "than", "too", "very", "just", "now", "also", "back",
    "even", "still", "through", "way", "well", "much", "many", "new", "old",
    "good", "great", "little", "long", "first", "last", "next", "own", "other",
    "right", "big", "different", "small", "large", "high", "low", "local",
    "start", "math", "clean", "light", "background", "hover", "drop", "luke",
    "flat", "shake", "realistic", "chart", "code", "explore", "search", "filter",
    "sort", "page", "view", "edit", "delete", "save", "cancel", "submit", "close",
    "get", "make", "take", "give", "find", "know", "think", "see", "come",
    "want", "use", "work", "try", "ask", "need", "feel", "become", "leave",
    "put", "mean", "keep", "let", "begin", "seem", "help", "show", "hear",
    "play", "run", "move", "like", "live", "believe", "hold", "bring", "happen",
    "write", "provide", "sit", "stand", "lose", "pay", "meet", "include",
    "continue", "set", "learn", "change", "lead", "understand", "watch", "follow",
    "stop", "create", "speak", "read", "allow", "add", "spend", "grow", "open",
    "walk", "win", "offer", "remember", "love", "consider", "appear", "buy",
    "wait", "serve", "die", "send", "expect", "build", "stay", "fall", "cut",
    "reach", "kill", "remain", "suggest", "raise", "pass", "sell", "require",
    "report", "decide", "pull", "looking", "looking", "cards", "via", "using",
}

# Common Danish words that are NOT projects
COMMON_DANISH_WORDS = {
    "hvad", "vi", "jeg", "det", "klar", "så", "men", "eller", "og", "at",
    "en", "et", "der", "som", "på", "med", "kan", "har", "er", "til", "de",
    "af", "ikke", "også", "for", "om", "han", "hun", "dit", "din", "denne",
    "dette", "disse", "var", "bliver", "blevet", "være", "have", "kunne",
    "skulle", "ville", "må", "lige", "meget", "godt", "hvis", "bare", "selv",
    "når", "hvor", "hvorfor", "hvordan", "hvem", "hvilken", "alle", "nogle",
    "noget", "ingen", "intet", "anden", "andet", "andre", "hver", "hvert",
    "mig", "dig", "ham", "hende", "os", "jer", "dem", "min", "mit", "mine",
    "sin", "sit", "sine", "vores", "jeres", "deres",
    "fase", "susanne", "overblik", "sporbart", "website",
}

# Generic single words that are NOT projects
GENERIC_SINGLE_WORDS = {
    "intelligence", "website", "platform", "solution", "system", "service",
    "tool", "app", "application", "software", "dashboard", "portal",
    "product", "project", "program", "plan", "strategy", "campaign",
}


def is_likely_project_name(name: str) -> bool:
    """Determine if a string is likely a project name vs a common word/phrase.
    
    Uses multiple heuristics:
    - Known projects whitelist
    - Common English/Danish word filter
    - Minimum length for single words (4 chars)
    - Multi-word proper noun detection
    """
    if not name or not name.strip():
        return False
    
    name_lower = name.lower().strip()
    
    # Check whitelist of known projects
    if name_lower in KNOWN_PROJECTS:
        return True
    
    # Split into words
    words = name_lower.split()
    
    # Single-word projects
    if len(words) == 1:
        # Must be at least 4 characters
        if len(name_lower) < 4:
            return False
        
        # Reject common English words
        if name_lower in COMMON_ENGLISH_WORDS:
            return False
        
        # Reject common Danish words
        if name_lower in COMMON_DANISH_WORDS:
            return False
        
        # Reject generic single words
        if name_lower in GENERIC_SINGLE_WORDS:
            return False
        
        # Single word, capitalized, 4+ chars, not a common word -> likely a project
        if name[0].isupper() and len(name) >= 4:
            return True
        
        return False
    
    # Multi-word names
    if len(words) > 1:
        # Check if all words are common words (would be a phrase, not a project)
        all_common = all(
            word in COMMON_ENGLISH_WORDS or word in COMMON_DANISH_WORDS
            for word in words
        )
        if all_common:
            return False
        
        # Check if it's a proper noun (all words capitalized)
        if all(w[0].isupper() for w in name.split() if w):
            return True
        
        # At least one word should be 4+ chars and not a common word
        has_meaningful_word = any(
            len(word) >= 4 and word not in COMMON_ENGLISH_WORDS and word not in COMMON_DANISH_WORDS
            for word in words
        )
        if has_meaningful_word:
            return True
    
    return False


# Response Models
class ProjectActivity(BaseModel):
    """Activity data for a project."""
    name: str
    activity_score: int
    status: str  # active, warming, cooling, stale
    trend: str  # up, down, flat
    last_activity: str | None
    conversation_mentions_7d: int
    conversation_mentions_prev_7d: int
    github_commits_7d: int
    github_repo: str | None
    days_since_activity: int | None
    suggested_action: str | None


class ProjectPulseResponse(BaseModel):
    """Project pulse with activity scores."""
    projects: list[ProjectActivity]
    total_projects: int
    active_count: int  # daily activity
    warming_count: int  # weekly activity
    cooling_count: int  # monthly activity
    stale_count: int  # 30+ days no activity


def get_github_commits(repo_name: str, days: int = 7) -> int:
    """Get commit count for a repo in the last N days.
    
    Uses GitHub CLI if available.
    """
    try:
        # Calculate date threshold
        since_date = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
        
        # Try to get commits using gh CLI
        # Assumes repo format: Arnarsson/{repo_name}
        result = subprocess.run(
            [
                "gh", "api",
                f"repos/Arnarsson/{repo_name}/commits",
                f"--jq", f'[.[] | select(.commit.author.date >= "{since_date}")] | length',
                "-q", f"since={since_date}",
                "--paginate",
            ],
            capture_output=True,
            text=True,
            timeout=5,
        )
        
        if result.returncode == 0 and result.stdout.strip():
            return int(result.stdout.strip())
        
        return 0
        
    except (subprocess.TimeoutExpired, ValueError, FileNotFoundError):
        return 0
    except Exception as e:
        logger.debug("github_commits_check_failed", repo=repo_name, error=str(e))
        return 0


@router.get("/pulse", response_model=ProjectPulseResponse)
async def project_pulse(
    min_mentions: int = Query(3, ge=1, description="Minimum mentions to include"),
    include_github: bool = Query(True, description="Check GitHub for commit activity"),
    limit: int = Query(50, ge=1, le=200, description="Max projects to return"),
    db: AsyncSession = Depends(get_db),
) -> ProjectPulseResponse:
    """Generate project activity pulse.
    
    Calculates activity scores for each project based on:
    - Conversation mentions (last 7 days vs previous 7 days)
    - GitHub commits (if repo exists)
    - Trend direction (warming up or cooling down)
    
    Returns projects sorted by activity score.
    """
    try:
        qdrant = get_qdrant()
        now = datetime.now(timezone.utc)
        seven_days_ago = now - timedelta(days=7)
        fourteen_days_ago = now - timedelta(days=14)
        thirty_days_ago = now - timedelta(days=30)
        
        logger.info("project_pulse_scan_starting", include_github=include_github)
        
        # Track project data
        project_tracker = defaultdict(lambda: {
            "mentions_7d": 0,
            "mentions_prev_7d": 0,
            "dates": [],
            "conversations": set(),
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
                    
                    # Track projects (collect all for now, will filter with LLM later)
                    for project in payload.get("projects", []):
                        # Quick basic filtering (very short names, empty strings)
                        if not project or len(project.strip()) < 2:
                            continue
                        
                        project_tracker[project]["conversations"].add(conversation_id)
                        
                        if chunk_date:
                            project_tracker[project]["dates"].append(chunk_date)
                            
                            # Count mentions by time period
                            if chunk_date >= seven_days_ago:
                                project_tracker[project]["mentions_7d"] += 1
                            elif chunk_date >= fourteen_days_ago:
                                project_tracker[project]["mentions_prev_7d"] += 1
                
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
            "project_pulse_scan_complete",
            total_scanned=total_scanned,
            projects_found=len(project_tracker),
        )
        
        # Use LLM to classify entities if available
        if HAS_LLM_CLASSIFIER:
            logger.info("classifying_entities_with_llm", count=len(project_tracker))
            try:
                all_entities = list(project_tracker.keys())
                classifications = await get_entity_classifications(all_entities, db)
                
                # Filter to only entities classified as PROJECT
                project_tracker = {
                    name: data
                    for name, data in project_tracker.items()
                    if llm_is_project(name, classifications.get(name, "NOISE"))
                }
                
                logger.info(
                    "llm_classification_complete",
                    total_entities=len(all_entities),
                    projects_found=len(project_tracker),
                )
            except Exception as e:
                logger.error("llm_classification_failed", error=str(e))
                # Fall back to rule-based filtering
                project_tracker = {
                    name: data
                    for name, data in project_tracker.items()
                    if is_likely_project_name(name)
                }
        else:
            # Use rule-based filtering
            project_tracker = {
                name: data
                for name, data in project_tracker.items()
                if is_likely_project_name(name)
            }
        
        # Filter by minimum mentions
        total_mentions = {
            name: data["mentions_7d"] + data["mentions_prev_7d"]
            for name, data in project_tracker.items()
        }
        
        filtered_projects = {
            name: data
            for name, data in project_tracker.items()
            if total_mentions[name] >= min_mentions
        }
        
        logger.info(
            "projects_filtered",
            after_classification=len(project_tracker),
            after_min_mentions=len(filtered_projects),
            min_mentions=min_mentions,
        )
        
        # Build project activity list
        projects = []
        active_count = 0
        warming_count = 0
        cooling_count = 0
        stale_count = 0
        
        for name, data in filtered_projects.items():
            dates = sorted(data["dates"]) if data["dates"] else []
            last_activity = dates[-1] if dates else None
            
            # Calculate days since activity
            days_since = None
            if last_activity:
                delta = now - last_activity
                days_since = delta.days
            
            # Get GitHub commits if enabled
            github_commits = 0
            github_repo = None
            if include_github:
                # Normalize project name for repo lookup
                repo_candidate = name.lower().replace(" ", "-")
                github_commits = get_github_commits(repo_candidate, days=7)
                if github_commits > 0:
                    github_repo = f"Arnarsson/{repo_candidate}"
            
            # Calculate activity score
            # Weight: recent mentions (3x), previous mentions (1x), github commits (2x)
            activity_score = (
                data["mentions_7d"] * 3 +
                data["mentions_prev_7d"] * 1 +
                github_commits * 2
            )
            
            # Determine trend
            trend = "flat"
            if data["mentions_7d"] > data["mentions_prev_7d"]:
                trend = "up"
            elif data["mentions_7d"] < data["mentions_prev_7d"]:
                trend = "down"
            
            # Determine status
            status = "stale"
            suggested_action = None
            
            if data["mentions_7d"] >= 5 or github_commits >= 3:
                status = "active"
                active_count += 1
                suggested_action = f"Keep momentum on {name}"
            elif data["mentions_7d"] >= 1 or github_commits >= 1:
                status = "warming"
                warming_count += 1
                suggested_action = f"Continue progress on {name}"
            elif last_activity and last_activity >= thirty_days_ago:
                status = "cooling"
                cooling_count += 1
                suggested_action = f"Check in on {name} - activity declining"
            else:
                status = "stale"
                stale_count += 1
                if days_since:
                    suggested_action = f"Revive {name} (inactive for {days_since} days)"
                else:
                    suggested_action = f"Review status of {name}"
            
            projects.append(ProjectActivity(
                name=name,
                activity_score=activity_score,
                status=status,
                trend=trend,
                last_activity=last_activity.isoformat() if last_activity else None,
                conversation_mentions_7d=data["mentions_7d"],
                conversation_mentions_prev_7d=data["mentions_prev_7d"],
                github_commits_7d=github_commits,
                github_repo=github_repo,
                days_since_activity=days_since,
                suggested_action=suggested_action,
            ))
        
        # Sort by activity score descending
        projects.sort(key=lambda x: x.activity_score, reverse=True)
        
        # Apply limit
        projects = projects[:limit]
        
        logger.info(
            "project_pulse_generated",
            total_projects=len(projects),
            active=active_count,
            warming=warming_count,
            cooling=cooling_count,
            stale=stale_count,
        )
        
        return ProjectPulseResponse(
            projects=projects,
            total_projects=len(projects),
            active_count=active_count,
            warming_count=warming_count,
            cooling_count=cooling_count,
            stale_count=stale_count,
        )
        
    except Exception as e:
        logger.error("project_pulse_failed", error=str(e), exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to generate project pulse")
