-- Migration: Add quick_captures table
-- Run with: docker exec jarvis-postgres psql -U jarvis -d jarvis < /path/to/this/file
-- Or via psql inside container

CREATE TABLE IF NOT EXISTS quick_captures (
    id VARCHAR(36) PRIMARY KEY,
    text TEXT NOT NULL,
    tags_json TEXT NOT NULL DEFAULT '[]',
    source VARCHAR(20) NOT NULL DEFAULT 'manual',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS ix_quick_captures_created_at ON quick_captures(created_at);
CREATE INDEX IF NOT EXISTS ix_quick_captures_source ON quick_captures(source);
