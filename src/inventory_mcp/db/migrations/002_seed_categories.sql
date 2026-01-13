-- migrations/002_seed_categories.sql
-- Pre-defined categories for common home workshop/lab items

-- Hardware
INSERT OR IGNORE INTO categories (id, name, parent_id) VALUES
    ('cat-hardware', 'Hardware', NULL);
INSERT OR IGNORE INTO categories (id, name, parent_id) VALUES
    ('cat-fasteners', 'Fasteners', 'cat-hardware');
INSERT OR IGNORE INTO categories (id, name, parent_id) VALUES
    ('cat-screws', 'Screws', 'cat-fasteners');
INSERT OR IGNORE INTO categories (id, name, parent_id) VALUES
    ('cat-bolts', 'Bolts', 'cat-fasteners');
INSERT OR IGNORE INTO categories (id, name, parent_id) VALUES
    ('cat-nuts', 'Nuts', 'cat-fasteners');
INSERT OR IGNORE INTO categories (id, name, parent_id) VALUES
    ('cat-washers', 'Washers', 'cat-fasteners');
INSERT OR IGNORE INTO categories (id, name, parent_id) VALUES
    ('cat-nails', 'Nails', 'cat-fasteners');
INSERT OR IGNORE INTO categories (id, name, parent_id) VALUES
    ('cat-anchors', 'Anchors', 'cat-fasteners');

-- Tools
INSERT OR IGNORE INTO categories (id, name, parent_id) VALUES
    ('cat-tools', 'Tools', NULL);
INSERT OR IGNORE INTO categories (id, name, parent_id) VALUES
    ('cat-hand-tools', 'Hand Tools', 'cat-tools');
INSERT OR IGNORE INTO categories (id, name, parent_id) VALUES
    ('cat-power-tools', 'Power Tools', 'cat-tools');
INSERT OR IGNORE INTO categories (id, name, parent_id) VALUES
    ('cat-measuring', 'Measuring', 'cat-tools');

-- Electronics
INSERT OR IGNORE INTO categories (id, name, parent_id) VALUES
    ('cat-electronics', 'Electronics', NULL);
INSERT OR IGNORE INTO categories (id, name, parent_id) VALUES
    ('cat-components', 'Components', 'cat-electronics');
INSERT OR IGNORE INTO categories (id, name, parent_id) VALUES
    ('cat-cables', 'Cables & Connectors', 'cat-electronics');
INSERT OR IGNORE INTO categories (id, name, parent_id) VALUES
    ('cat-boards', 'Boards & Modules', 'cat-electronics');

-- Supplies
INSERT OR IGNORE INTO categories (id, name, parent_id) VALUES
    ('cat-supplies', 'Supplies', NULL);
INSERT OR IGNORE INTO categories (id, name, parent_id) VALUES
    ('cat-adhesives', 'Adhesives & Tape', 'cat-supplies');
INSERT OR IGNORE INTO categories (id, name, parent_id) VALUES
    ('cat-lubricants', 'Lubricants', 'cat-supplies');
INSERT OR IGNORE INTO categories (id, name, parent_id) VALUES
    ('cat-safety', 'Safety Equipment', 'cat-supplies');

-- Materials
INSERT OR IGNORE INTO categories (id, name, parent_id) VALUES
    ('cat-materials', 'Materials', NULL);
INSERT OR IGNORE INTO categories (id, name, parent_id) VALUES
    ('cat-wood', 'Wood', 'cat-materials');
INSERT OR IGNORE INTO categories (id, name, parent_id) VALUES
    ('cat-metal', 'Metal', 'cat-materials');
INSERT OR IGNORE INTO categories (id, name, parent_id) VALUES
    ('cat-plastic', 'Plastic', 'cat-materials');

-- Other
INSERT OR IGNORE INTO categories (id, name, parent_id) VALUES
    ('cat-other', 'Other', NULL);

-- Insert schema version
INSERT INTO schema_version (version) VALUES (2);
