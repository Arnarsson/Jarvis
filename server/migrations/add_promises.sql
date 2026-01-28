-- Migration: Add promises table
-- Run with: docker exec -i jarvis-postgres psql -U jarvis -d jarvis < /path/to/this/file

CREATE TABLE IF NOT EXISTS promises (
    id VARCHAR(36) PRIMARY KEY,
    text TEXT NOT NULL,
    source_conversation_id VARCHAR(36),
    detected_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    due_by TIMESTAMP WITH TIME ZONE,
    status VARCHAR(20) NOT NULL DEFAULT 'pending',
    fulfilled_at TIMESTAMP WITH TIME ZONE
);

CREATE INDEX IF NOT EXISTS ix_promises_status ON promises(status);
CREATE INDEX IF NOT EXISTS ix_promises_detected_at ON promises(detected_at);
CREATE INDEX IF NOT EXISTS ix_promises_due_by ON promises(due_by);
