"""Entity classification using LLM for bilingual (Danish/English) entity detection.

Classifies entities as: PERSON, PROJECT, COMPANY, TOOL, TOPIC, or NOISE
Results are cached in database to avoid repeated API calls.
"""

import openai
import structlog
import json
from typing import Dict, List
from datetime import datetime, timezone

from jarvis_server.config import get_settings

logger = structlog.get_logger(__name__)


CLASSIFICATION_PROMPT = """You are an entity classifier for a bilingual (Danish and English) personal knowledge system.

Classify each entity below as ONE of: PERSON, PROJECT, COMPANY, TOOL, TOPIC, or NOISE

Rules:
- PERSON: Actual human names only (e.g., "Sven Arnarsson", "Carsten Timm", "Anne Clara")
- PROJECT: Named projects or products (e.g., "RecruitOS", "Jarvis", "Atlas Intelligence", "Nytårskur")  
- COMPANY: Organization names (e.g., "Google", "Facebook", "Microsoft")
- TOOL: Software tools/platforms (e.g., "Docker", "Linear", "GitHub", "Claude Desktop")
- TOPIC: Subjects or concepts (e.g., "Error Handling", "Prompt Engineering", "Operations Automation")
- NOISE: Common words, phrases, verbs, articles (e.g., "This", "The", "Hvad", "Changes Made", "Set Up")

The text may be in Danish or English. Understand both languages naturally.
- "Hvad" (Danish for "What") is NOISE
- "Jeg" (Danish for "I") is NOISE  
- "Carsten Timm" is a PERSON regardless of language
- "Nytårskur" (Danish for "New Year's Course") could be PROJECT or TOPIC depending on context

Return ONLY a JSON object mapping each entity to its classification:
{
  "Entity Name": "CLASSIFICATION",
  ...
}

Entities to classify:
{entities}"""


async def classify_entities_batch(entities: List[str]) -> Dict[str, str]:
    """Classify a batch of entities using OpenAI GPT-4o-mini.
    
    Args:
        entities: List of entity names to classify
        
    Returns:
        Dictionary mapping entity name to classification (PERSON, PROJECT, etc.)
    """
    if not entities:
        return {}
    
    settings = get_settings()
    if not settings.openai_api_key:
        logger.error("openai_api_key_not_configured")
        # Fallback: return all as NOISE
        return {entity: "NOISE" for entity in entities}
    
    try:
        client = openai.AsyncOpenAI(api_key=settings.openai_api_key)
        
        # Format entities as numbered list for the prompt
        entities_str = "\n".join(f"{i+1}. {entity}" for i, entity in enumerate(entities))
        
        prompt = CLASSIFICATION_PROMPT.format(entities=entities_str)
        
        # Call GPT-4o-mini (fast and cheap)
        response = await client.chat.completions.create(
            model="gpt-4o-mini",
            max_tokens=2000,
            temperature=0,
            response_format={"type": "json_object"},
            messages=[{"role": "user", "content": prompt}],
        )
        
        # Parse JSON response
        response_text = response.choices[0].message.content
        
        # Extract JSON from markdown code blocks if present
        if "```json" in response_text:
            response_text = response_text.split("```json")[1].split("```")[0]
        elif "```" in response_text:
            response_text = response_text.split("```")[1].split("```")[0]
        
        classifications = json.loads(response_text.strip())
        
        logger.info(
            "entities_classified",
            batch_size=len(entities),
            classifications_count=len(classifications),
        )
        
        return classifications
        
    except Exception as e:
        logger.error("entity_classification_failed", error=str(e), exc_info=True)
        # Fallback: return all as NOISE
        return {entity: "NOISE" for entity in entities}


async def get_entity_classifications(
    entities: List[str],
    db,  # AsyncSession
    force_refresh: bool = False,
) -> Dict[str, str]:
    """Get entity classifications with caching.
    
    Checks database cache first, then classifies unknown entities via LLM.
    
    Args:
        entities: List of entity names to classify
        db: Database session
        force_refresh: Force re-classification even if cached
        
    Returns:
        Dictionary mapping entity name to classification
    """
    from sqlalchemy import select, text
    
    if not entities:
        return {}
    
    classifications = {}
    entities_to_classify = []
    
    if not force_refresh:
        # Check cache for existing classifications
        try:
            result = await db.execute(
                text(
                    "SELECT entity_name, entity_type FROM entity_classifications "
                    "WHERE entity_name = ANY(:names)"
                ),
                {"names": entities}
            )
            cached = result.fetchall()
            
            for row in cached:
                classifications[row[0]] = row[1]
            
            # Find entities not in cache
            entities_to_classify = [e for e in entities if e not in classifications]
            
            logger.info(
                "entity_cache_check",
                total=len(entities),
                cached=len(classifications),
                to_classify=len(entities_to_classify),
            )
            
        except Exception as e:
            logger.error("entity_cache_check_failed", error=str(e))
            entities_to_classify = entities
    else:
        entities_to_classify = entities
    
    # Classify uncached entities
    if entities_to_classify:
        # Process in batches of 50 to avoid token limits
        batch_size = 50
        for i in range(0, len(entities_to_classify), batch_size):
            batch = entities_to_classify[i:i+batch_size]
            batch_classifications = await classify_entities_batch(batch)
            
            # Save to cache
            try:
                for entity, classification in batch_classifications.items():
                    # Insert or update
                    await db.execute(
                        text(
                            "INSERT INTO entity_classifications (entity_name, entity_type) "
                            "VALUES (:name, :type) "
                            "ON CONFLICT (entity_name) DO UPDATE SET "
                            "entity_type = EXCLUDED.entity_type, "
                            "classified_at = CURRENT_TIMESTAMP"
                        ),
                        {"name": entity, "type": classification}
                    )
                
                await db.commit()
                
                classifications.update(batch_classifications)
                
            except Exception as e:
                logger.error("entity_cache_save_failed", error=str(e))
                await db.rollback()
                # Still use the classifications even if caching failed
                classifications.update(batch_classifications)
    
    return classifications


def is_person(entity: str, classification: str) -> bool:
    """Check if an entity is classified as a person."""
    return classification == "PERSON"


def is_project(entity: str, classification: str) -> bool:
    """Check if an entity is classified as a project."""
    return classification == "PROJECT"
