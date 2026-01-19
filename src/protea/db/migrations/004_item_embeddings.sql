-- Migration 004: Add embedding column for vector search
-- Stores sentence-transformer embeddings as BLOB for semantic search

-- Add embedding column to items table
ALTER TABLE items ADD COLUMN embedding BLOB;

-- Index to quickly find items that have embeddings
CREATE INDEX IF NOT EXISTS idx_items_has_embedding ON items(id) WHERE embedding IS NOT NULL;

-- Record migration
INSERT INTO schema_version (version) VALUES (4);
