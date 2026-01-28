-- Migration: Add entity_classifications table for caching LLM classifications
-- Run with: docker exec -i jarvis-postgres psql -U jarvis -d jarvis < /path/to/this/file

CREATE TABLE IF NOT EXISTS entity_classifications (
    id SERIAL PRIMARY KEY,
    entity_name VARCHAR(500) NOT NULL,
    entity_type VARCHAR(50) NOT NULL, -- PERSON, PROJECT, COMPANY, TOOL, TOPIC, NOISE
    confidence FLOAT, -- Optional confidence score
    classified_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(entity_name)
);

CREATE INDEX IF NOT EXISTS ix_entity_classifications_name ON entity_classifications(entity_name);
CREATE INDEX IF NOT EXISTS ix_entity_classifications_type ON entity_classifications(entity_type);
CREATE INDEX IF NOT EXISTS ix_entity_classifications_classified_at ON entity_classifications(classified_at);
