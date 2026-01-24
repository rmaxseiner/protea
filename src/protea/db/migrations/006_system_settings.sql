-- Migration 006: Add system_settings table for storing app configuration
-- Stores key-value pairs for settings like embedding model selection

CREATE TABLE IF NOT EXISTS system_settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Store the current embedding model
INSERT OR IGNORE INTO system_settings (key, value) VALUES ('embedding_model', 'all-mpnet-base-v2');

-- Store embedding regeneration status (idle, running, completed, failed)
INSERT OR IGNORE INTO system_settings (key, value) VALUES ('embedding_regen_status', 'idle');
INSERT OR IGNORE INTO system_settings (key, value) VALUES ('embedding_regen_progress', '0');
INSERT OR IGNORE INTO system_settings (key, value) VALUES ('embedding_regen_total', '0');
INSERT OR IGNORE INTO system_settings (key, value) VALUES ('embedding_regen_message', '');

-- Record migration
INSERT INTO schema_version (version) VALUES (6);
