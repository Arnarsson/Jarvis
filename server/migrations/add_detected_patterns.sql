-- Migration: Add detected_patterns table
-- Run with: docker exec -i jarvis-postgres psql -U jarvis -d jarvis < /path/to/this/file

CREATE TABLE IF NOT EXISTS detected_patterns (
    id VARCHAR(36) PRIMARY KEY,
    pattern_type VARCHAR(50) NOT NULL,
    pattern_key VARCHAR(200) NOT NULL,
    description TEXT NOT NULL,
    frequency INTEGER NOT NULL DEFAULT 1,
    first_seen TIMESTAMP WITH TIME ZONE NOT NULL,
    last_seen TIMESTAMP WITH TIME ZONE NOT NULL,
    suggested_action TEXT,
    conversation_ids_json TEXT NOT NULL DEFAULT '[]',
    detected_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    status VARCHAR(20) NOT NULL DEFAULT 'active'
);

CREATE INDEX IF NOT EXISTS ix_detected_patterns_type ON detected_patterns(pattern_type);
CREATE INDEX IF NOT EXISTS ix_detected_patterns_status ON detected_patterns(status);
CREATE INDEX IF NOT EXISTS ix_detected_patterns_last_seen ON detected_patterns(last_seen);
CREATE INDEX IF NOT EXISTS ix_detected_patterns_key ON detected_patterns(pattern_key);
