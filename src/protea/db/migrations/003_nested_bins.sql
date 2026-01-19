-- Migration 003: Add nested bins support
-- Allows bins to contain other bins (e.g., Tool Chest -> Drawer 9)

-- SQLite doesn't support ALTER TABLE DROP CONSTRAINT, so we need to recreate the table
-- to update the uniqueness constraint from (name, location_id) to (name, location_id, parent_bin_id)

-- Step 0: Clean up any failed previous migration attempt
DROP TABLE IF EXISTS bins_new;

-- Step 1: Create new bins table with updated schema
CREATE TABLE bins_new (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    location_id TEXT NOT NULL REFERENCES locations(id),
    parent_bin_id TEXT REFERENCES bins_new(id),
    description TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Step 2: Copy data from old table (existing bins get NULL parent_bin_id)
INSERT INTO bins_new (id, name, location_id, parent_bin_id, description, created_at, updated_at)
SELECT id, name, location_id, NULL, description, created_at, updated_at FROM bins;

-- Step 3: Drop old table and indexes
DROP INDEX IF EXISTS idx_bins_location;
DROP TABLE bins;

-- Step 4: Rename new table to bins
ALTER TABLE bins_new RENAME TO bins;

-- Step 5: Recreate indexes
CREATE INDEX IF NOT EXISTS idx_bins_location ON bins(location_id);
CREATE INDEX IF NOT EXISTS idx_bins_parent ON bins(parent_bin_id);

-- Step 6: Create a unique index that handles NULL parent_bin_id correctly
-- SQLite treats each NULL as unique, so we need a partial index approach:
-- Root-level bins: unique on (name, location_id) where parent_bin_id IS NULL
-- Nested bins: unique on (name, location_id, parent_bin_id)
CREATE UNIQUE INDEX IF NOT EXISTS idx_bins_unique_root ON bins(name, location_id) WHERE parent_bin_id IS NULL;
CREATE UNIQUE INDEX IF NOT EXISTS idx_bins_unique_nested ON bins(name, location_id, parent_bin_id) WHERE parent_bin_id IS NOT NULL;

-- Record migration
INSERT INTO schema_version (version) VALUES (3);
