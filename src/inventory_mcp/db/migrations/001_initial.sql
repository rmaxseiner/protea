-- migrations/001_initial.sql
-- Initial database schema for inventory-mcp

-- Locations (rooms, areas)
CREATE TABLE IF NOT EXISTS locations (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    description TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Bins (containers within locations)
CREATE TABLE IF NOT EXISTS bins (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    location_id TEXT NOT NULL REFERENCES locations(id),
    description TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(name, location_id)
);

CREATE INDEX IF NOT EXISTS idx_bins_location ON bins(location_id);

-- Categories (hierarchical)
CREATE TABLE IF NOT EXISTS categories (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    parent_id TEXT REFERENCES categories(id),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(name, parent_id)
);

CREATE INDEX IF NOT EXISTS idx_categories_parent ON categories(parent_id);

-- Items
CREATE TABLE IF NOT EXISTS items (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT,
    category_id TEXT REFERENCES categories(id),
    bin_id TEXT NOT NULL REFERENCES bins(id),
    quantity_type TEXT NOT NULL CHECK(quantity_type IN ('exact', 'approximate', 'boolean')),
    quantity_value INTEGER,
    quantity_label TEXT,
    source TEXT NOT NULL CHECK(source IN ('manual', 'vision', 'barcode_lookup')),
    source_reference TEXT,
    photo_url TEXT,
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_items_bin ON items(bin_id);
CREATE INDEX IF NOT EXISTS idx_items_category ON items(category_id);
CREATE INDEX IF NOT EXISTS idx_items_name ON items(name);

-- Full text search for items
CREATE VIRTUAL TABLE IF NOT EXISTS items_fts USING fts5(
    name,
    description,
    content='items',
    content_rowid='rowid'
);

-- Triggers to keep FTS in sync
CREATE TRIGGER IF NOT EXISTS items_ai AFTER INSERT ON items BEGIN
    INSERT INTO items_fts(rowid, name, description)
    VALUES (NEW.rowid, NEW.name, NEW.description);
END;

CREATE TRIGGER IF NOT EXISTS items_ad AFTER DELETE ON items BEGIN
    INSERT INTO items_fts(items_fts, rowid, name, description)
    VALUES('delete', OLD.rowid, OLD.name, OLD.description);
END;

CREATE TRIGGER IF NOT EXISTS items_au AFTER UPDATE ON items BEGIN
    INSERT INTO items_fts(items_fts, rowid, name, description)
    VALUES('delete', OLD.rowid, OLD.name, OLD.description);
    INSERT INTO items_fts(rowid, name, description)
    VALUES (NEW.rowid, NEW.name, NEW.description);
END;

-- Item aliases for fuzzy matching
CREATE TABLE IF NOT EXISTS item_aliases (
    id TEXT PRIMARY KEY,
    item_id TEXT NOT NULL REFERENCES items(id) ON DELETE CASCADE,
    alias TEXT NOT NULL,
    UNIQUE(item_id, alias)
);

CREATE INDEX IF NOT EXISTS idx_item_aliases_item ON item_aliases(item_id);
CREATE INDEX IF NOT EXISTS idx_item_aliases_alias ON item_aliases(alias);

-- FTS for aliases
CREATE VIRTUAL TABLE IF NOT EXISTS aliases_fts USING fts5(
    alias,
    content='item_aliases',
    content_rowid='rowid'
);

CREATE TRIGGER IF NOT EXISTS aliases_ai AFTER INSERT ON item_aliases BEGIN
    INSERT INTO aliases_fts(rowid, alias) VALUES (NEW.rowid, NEW.alias);
END;

CREATE TRIGGER IF NOT EXISTS aliases_ad AFTER DELETE ON item_aliases BEGIN
    INSERT INTO aliases_fts(aliases_fts, rowid, alias)
    VALUES('delete', OLD.rowid, OLD.alias);
END;

-- Bin images
CREATE TABLE IF NOT EXISTS bin_images (
    id TEXT PRIMARY KEY,
    bin_id TEXT NOT NULL REFERENCES bins(id) ON DELETE CASCADE,
    file_path TEXT NOT NULL,
    thumbnail_path TEXT,
    caption TEXT,
    is_primary BOOLEAN DEFAULT FALSE,
    source_session_id TEXT,
    source_session_image_id TEXT,
    width INTEGER,
    height INTEGER,
    file_size_bytes INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_bin_images_bin ON bin_images(bin_id);

-- Activity log
CREATE TABLE IF NOT EXISTS activity_log (
    id TEXT PRIMARY KEY,
    item_id TEXT NOT NULL REFERENCES items(id) ON DELETE CASCADE,
    action TEXT NOT NULL CHECK(action IN ('added', 'removed', 'moved', 'updated', 'used')),
    quantity_change INTEGER,
    from_bin_id TEXT REFERENCES bins(id),
    to_bin_id TEXT REFERENCES bins(id),
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_activity_log_item ON activity_log(item_id);
CREATE INDEX IF NOT EXISTS idx_activity_log_created ON activity_log(created_at);

-- Sessions
CREATE TABLE IF NOT EXISTS sessions (
    id TEXT PRIMARY KEY,
    status TEXT NOT NULL CHECK(status IN ('pending', 'committed', 'cancelled')) DEFAULT 'pending',
    target_bin_id TEXT REFERENCES bins(id),
    target_location_id TEXT REFERENCES locations(id),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    committed_at TIMESTAMP,
    cancelled_at TIMESTAMP,
    commit_summary TEXT
);

CREATE INDEX IF NOT EXISTS idx_sessions_status ON sessions(status);

-- Session images
CREATE TABLE IF NOT EXISTS session_images (
    id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
    file_path TEXT NOT NULL,
    thumbnail_path TEXT,
    original_filename TEXT,
    width INTEGER,
    height INTEGER,
    file_size_bytes INTEGER,
    extracted_data TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_session_images_session ON session_images(session_id);

-- Pending items (in session, not yet committed)
CREATE TABLE IF NOT EXISTS pending_items (
    id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
    source_image_id TEXT REFERENCES session_images(id),
    name TEXT NOT NULL,
    quantity_type TEXT NOT NULL CHECK(quantity_type IN ('exact', 'approximate', 'boolean')) DEFAULT 'boolean',
    quantity_value INTEGER,
    quantity_label TEXT,
    category_id TEXT REFERENCES categories(id),
    confidence REAL,
    source TEXT NOT NULL CHECK(source IN ('vision', 'manual')) DEFAULT 'manual',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_pending_items_session ON pending_items(session_id);

-- Add foreign key references for bin_images after sessions table exists
-- (SQLite doesn't support ALTER TABLE ADD CONSTRAINT, so we handle this at application level)

-- Insert schema version
INSERT INTO schema_version (version) VALUES (1);
