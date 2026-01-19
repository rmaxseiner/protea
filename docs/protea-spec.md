# Protea Inventory System - Technical Specification

## Overview

A Model Context Protocol (MCP) server for managing physical inventory with multimodal (vision) support. Enables natural language inventory management through any MCP-compatible LLM client.

### Project Goals

1. **Primary:** Build LLM/agent skills - multimodal input, state-changing operations
2. **Secondary:** Practical inventory management for home workshop/lab
3. **Future:** Home Assistant voice integration, web UI

### Key Features

- Voice/text commands: "Add these to my hardware bin" + photo
- Vision extraction: Identify items from photos, read labels/barcodes
- Session workflow: Review/edit extracted items before committing
- Query inventory: "Do I have M3 screws?", "What tape do I have?"
- Track history: When items added, used, moved

---

## Project Structure

```
protea/
  ├── src/
  │   └── protea/
  │       ├── __init__.py
  │       ├── server.py              # MCP server entry point
  │       ├── config.py              # Configuration settings
  │       ├── db/
  │       │   ├── __init__.py
  │       │   ├── connection.py      # SQLite connection management
  │       │   ├── models.py          # Pydantic models / dataclasses
  │       │   ├── queries.py         # Database query functions
  │       │   └── migrations/
  │       │       └── 001_initial.sql
  │       ├── tools/
  │       │   ├── __init__.py        # Tool registration
  │       │   ├── locations.py       # Location CRUD tools
  │       │   ├── bins.py            # Bin CRUD tools
  │       │   ├── items.py           # Item management tools
  │       │   ├── sessions.py        # Session workflow tools
  │       │   ├── search.py          # Search and query tools
  │       │   ├── categories.py      # Category tools
  │       │   ├── aliases.py         # Alias tools
  │       │   └── vision.py          # Vision extraction tools
  │       └── services/
  │           ├── __init__.py
  │           ├── image_store.py     # Image storage service
  │           └── product_lookup.py  # Barcode/ASIN lookup service
  ├── data/
  │   └── .gitkeep
  ├── tests/
  │   ├── __init__.py
  │   ├── conftest.py                # pytest fixtures
  │   ├── test_locations.py
  │   ├── test_bins.py
  │   ├── test_items.py
  │   ├── test_sessions.py
  │   └── test_search.py
  ├── pyproject.toml
  ├── README.md
  └── .gitignore
```

---

## Technology Stack

| Component | Technology | Notes |
|-----------|------------|-------|
| Language | Python 3.11+ | Type hints throughout |
| MCP Server | `mcp` package | Official Anthropic SDK |
| Database | SQLite | FTS5 for search, migrate to Postgres later |
| Migrations | Raw SQL files | Simple version tracking |
| Models | Pydantic v2 | Validation, serialization |
| Image Processing | Pillow | WebP conversion, thumbnails |
| Testing | pytest | In-memory SQLite for integration tests |
| Package Management | pyproject.toml | Modern Python packaging |

---

## Configuration

```python
# src/protea/config.py

from pathlib import Path
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    # Database
    database_path: Path = Path("data/inventory.db")

    # Image storage
    image_base_path: Path = Path("data/images")
    image_format: str = "webp"
    image_quality: int = 85
    thumbnail_size: tuple[int, int] = (200, 200)
    max_image_size_bytes: int = 10 * 1024 * 1024  # 10MB default (typical phone image)

    # Session settings
    session_stale_minutes: int = 30

    # Vision API (optional - for direct extraction)
    # If not set, orchestrating LLM handles vision extraction
    claude_api_key: str | None = None
    claude_model: str = "claude-sonnet-4-20250514"

    # Product lookup APIs (optional)
    amazon_product_api_key: str | None = None
    amazon_product_api_secret: str | None = None
    amazon_partner_tag: str | None = None
    upcitemdb_api_key: str | None = None

    class Config:
        env_prefix = "INVENTORY_"

settings = Settings()
```

**Configuration Notes:**
- **Vision extraction** supports two workflows:
  1. **Orchestrating LLM handles vision**: The LLM client extracts items from images and calls inventory tools directly
  2. **Direct API extraction**: Set `claude_api_key` to enable `extract_items_from_image` tool to call Claude API directly
- **Product lookup** is optional. Set API keys to enable barcode/ASIN lookup via Amazon Product API or UPCitemdb
- **Image size limit** defaults to 10MB (typical smartphone photo). Images exceeding this limit will be rejected with a message asking user to reduce resolution

---

## Error Response Format

All tools use a standardized error response format to ensure consistent handling by LLM clients:

```python
# Successful response - return the model directly
return item  # Item, Bin, Location, etc.

# Error response - return dict with error field
return {
    "error": "Human-readable error message for LLM to relay to user",
    "error_code": "ITEM_NOT_FOUND",  # Machine-readable code
    "details": {  # Optional additional context
        "item_id": "abc-123",
        "suggestion": "Did you mean 'M3 screws' in Hardware Bin?"
    }
}
```

### Error Codes

| Code | Description |
|------|-------------|
| `NOT_FOUND` | Resource (item, bin, location, etc.) not found |
| `ALREADY_EXISTS` | Duplicate name or unique constraint violation |
| `HAS_DEPENDENCIES` | Cannot delete - has child records |
| `INVALID_INPUT` | Validation error (missing required field, invalid value) |
| `SESSION_STALE` | Session is stale, needs user action |
| `SESSION_BLOCKED` | Cannot create session - stale sessions exist |
| `IMAGE_TOO_LARGE` | Image exceeds max_image_size_bytes |
| `API_ERROR` | External API (Claude, Amazon, UPC) failed |
| `NO_TARGET` | Session has no target bin/location at commit |

### Logging

Technical errors (database errors, API failures, unexpected exceptions) are logged via Python's standard logging framework:

```python
import logging
logger = logging.getLogger("protea")

# Log technical details
logger.error("Database error in add_item", exc_info=True)

# Return user-friendly message
return {"error": "Failed to add item. Please try again.", "error_code": "INTERNAL_ERROR"}
```

---

## Database Schema

### Entity Relationship Diagram

```
Location 1 ──< many Bin
Bin 1 ──< many Item
Bin 1 ──< many BinImage
Category 1 ──< many Item
Category 1 ──< many Category (self-referential for hierarchy)
Item 1 ──< many ItemAlias
Item 1 ──< many ActivityLog
Session 1 ──< many SessionImage
Session 1 ──< many PendingItem
SessionImage 1 ──< many PendingItem
```

### SQL Schema

```sql
-- migrations/001_initial.sql

-- Schema version tracking
CREATE TABLE IF NOT EXISTS schema_version (
    version INTEGER PRIMARY KEY,
    applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

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

CREATE INDEX idx_bins_location ON bins(location_id);

-- Bin images
CREATE TABLE IF NOT EXISTS bin_images (
    id TEXT PRIMARY KEY,
    bin_id TEXT NOT NULL REFERENCES bins(id) ON DELETE CASCADE,
    file_path TEXT NOT NULL,
    thumbnail_path TEXT,
    caption TEXT,
    is_primary BOOLEAN DEFAULT FALSE,
    source_session_id TEXT REFERENCES sessions(id),
    source_session_image_id TEXT REFERENCES session_images(id),
    width INTEGER,
    height INTEGER,
    file_size_bytes INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_bin_images_bin ON bin_images(bin_id);

-- Categories (hierarchical)
CREATE TABLE IF NOT EXISTS categories (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    parent_id TEXT REFERENCES categories(id),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(name, parent_id)
);

CREATE INDEX idx_categories_parent ON categories(parent_id);

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
    notes TEXT,  -- Free-form text for product lookup info, user notes
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_items_bin ON items(bin_id);
CREATE INDEX idx_items_category ON items(category_id);
CREATE INDEX idx_items_name ON items(name);

-- Full text search for items
CREATE VIRTUAL TABLE IF NOT EXISTS items_fts USING fts5(
    name,
    description,
    content='items',
    content_rowid='rowid'
);

-- Triggers to keep FTS in sync
CREATE TRIGGER items_ai AFTER INSERT ON items BEGIN
    INSERT INTO items_fts(rowid, name, description)
    VALUES (NEW.rowid, NEW.name, NEW.description);
END;

CREATE TRIGGER items_ad AFTER DELETE ON items BEGIN
    INSERT INTO items_fts(items_fts, rowid, name, description)
    VALUES('delete', OLD.rowid, OLD.name, OLD.description);
END;

CREATE TRIGGER items_au AFTER UPDATE ON items BEGIN
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

CREATE INDEX idx_item_aliases_item ON item_aliases(item_id);
CREATE INDEX idx_item_aliases_alias ON item_aliases(alias);

-- FTS for aliases
CREATE VIRTUAL TABLE IF NOT EXISTS aliases_fts USING fts5(
    alias,
    content='item_aliases',
    content_rowid='rowid'
);

CREATE TRIGGER aliases_ai AFTER INSERT ON item_aliases BEGIN
    INSERT INTO aliases_fts(rowid, alias) VALUES (NEW.rowid, NEW.alias);
END;

CREATE TRIGGER aliases_ad AFTER DELETE ON item_aliases BEGIN
    INSERT INTO aliases_fts(aliases_fts, rowid, alias)
    VALUES('delete', OLD.rowid, OLD.alias);
END;

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

CREATE INDEX idx_activity_log_item ON activity_log(item_id);
CREATE INDEX idx_activity_log_created ON activity_log(created_at);

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
    commit_summary TEXT  -- JSON snapshot of what was committed
);

CREATE INDEX idx_sessions_status ON sessions(status);

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
    extracted_data TEXT,  -- JSON of raw extraction results
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_session_images_session ON session_images(session_id);

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

CREATE INDEX idx_pending_items_session ON pending_items(session_id);

-- Insert schema version
INSERT INTO schema_version (version) VALUES (1);
```

---

## Data Models

### Quantity Semantics

Items use a flexible quantity system to handle real-world inventory scenarios:

| quantity_type | quantity_value | quantity_label | Use Case |
|---------------|----------------|----------------|----------|
| `exact` | 50 | "pieces" | Countable items: "50 M3 screws" |
| `approximate` | 1 | "assorted" | Uncountable: "assorted washers" |
| `approximate` | 1 | "various" | Mixed items: "various bolts" |
| `approximate` | 1 | "roll" | Consumables: "roll of tape" |
| `boolean` | 1 | null | Presence only: "soldering iron" |

- **exact**: Precise count known (e.g., from counting or package label)
- **approximate**: Quantity uncertain, `quantity_label` describes the grouping
- **boolean**: Item exists or doesn't; `quantity_value` always 1

### Photo URL Field

The `photo_url` field on Items references the specific image where the item was detected during vision extraction. This is distinct from `bin_images` which are general photos of the bin contents. The `photo_url` enables:
- Tracing an item back to its source image
- Showing users "this item came from this photo"
- Linking to `session_images` via the stored path

### Item Splitting (Partial Moves)

When `move_item` is called with a partial quantity, the system splits the item:
1. Original item's quantity is reduced
2. New item record created in target bin with moved quantity
3. Both items share the same name, category, and source
4. **Single activity log entry** records the split with references to both item IDs:
   - `action`: "moved"
   - `item_id`: source item ID
   - `quantity_change`: negative (amount moved out)
   - `from_bin_id`: source bin
   - `to_bin_id`: target bin
   - `notes`: JSON with `{"split": true, "new_item_id": "..."}`

```python
# src/protea/db/models.py

from datetime import datetime
from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field
import uuid

def generate_id() -> str:
    return str(uuid.uuid4())

class QuantityType(str, Enum):
    EXACT = "exact"
    APPROXIMATE = "approximate"
    BOOLEAN = "boolean"

class ItemSource(str, Enum):
    MANUAL = "manual"
    VISION = "vision"
    BARCODE_LOOKUP = "barcode_lookup"

class PendingItemSource(str, Enum):
    VISION = "vision"
    MANUAL = "manual"

class SessionStatus(str, Enum):
    PENDING = "pending"
    COMMITTED = "committed"
    CANCELLED = "cancelled"

class ActivityAction(str, Enum):
    ADDED = "added"
    REMOVED = "removed"
    MOVED = "moved"
    UPDATED = "updated"
    USED = "used"

# --- Core Models ---

class Location(BaseModel):
    id: str = Field(default_factory=generate_id)
    name: str
    description: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

class Bin(BaseModel):
    id: str = Field(default_factory=generate_id)
    name: str
    location_id: str
    description: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

class BinImage(BaseModel):
    id: str = Field(default_factory=generate_id)
    bin_id: str
    file_path: str
    thumbnail_path: Optional[str] = None
    caption: Optional[str] = None
    is_primary: bool = False
    source_session_id: Optional[str] = None
    source_session_image_id: Optional[str] = None
    width: Optional[int] = None
    height: Optional[int] = None
    file_size_bytes: Optional[int] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)

class Category(BaseModel):
    id: str = Field(default_factory=generate_id)
    name: str
    parent_id: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)

class Item(BaseModel):
    id: str = Field(default_factory=generate_id)
    name: str
    description: Optional[str] = None
    category_id: Optional[str] = None
    bin_id: str
    quantity_type: QuantityType = QuantityType.BOOLEAN
    quantity_value: Optional[int] = None
    quantity_label: Optional[str] = None
    source: ItemSource = ItemSource.MANUAL
    source_reference: Optional[str] = None
    photo_url: Optional[str] = None
    notes: Optional[str] = None  # Free-form text for product lookup info, user notes, etc.
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

class ItemAlias(BaseModel):
    id: str = Field(default_factory=generate_id)
    item_id: str
    alias: str

class ActivityLog(BaseModel):
    id: str = Field(default_factory=generate_id)
    item_id: str
    action: ActivityAction
    quantity_change: Optional[int] = None
    from_bin_id: Optional[str] = None
    to_bin_id: Optional[str] = None
    notes: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)

# --- Session Models ---

class Session(BaseModel):
    id: str = Field(default_factory=generate_id)
    status: SessionStatus = SessionStatus.PENDING
    target_bin_id: Optional[str] = None
    target_location_id: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    committed_at: Optional[datetime] = None
    cancelled_at: Optional[datetime] = None
    commit_summary: Optional[dict] = None

class SessionImage(BaseModel):
    id: str = Field(default_factory=generate_id)
    session_id: str
    file_path: str
    thumbnail_path: Optional[str] = None
    original_filename: Optional[str] = None
    width: Optional[int] = None
    height: Optional[int] = None
    file_size_bytes: Optional[int] = None
    extracted_data: Optional[dict] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)

class PendingItem(BaseModel):
    id: str = Field(default_factory=generate_id)
    session_id: str
    source_image_id: Optional[str] = None
    name: str
    quantity_type: QuantityType = QuantityType.BOOLEAN
    quantity_value: Optional[int] = None
    quantity_label: Optional[str] = None
    category_id: Optional[str] = None
    confidence: Optional[float] = None
    source: PendingItemSource = PendingItemSource.MANUAL
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

# --- Response Models (with joins) ---

class BinWithLocation(Bin):
    location: Location

class BinDetail(Bin):
    location: Location
    items: list[Item] = []
    images: list[BinImage] = []
    item_count: int = 0
    image_count: int = 0

class ItemWithLocation(Item):
    bin: Bin
    location: Location

class SearchResult(BaseModel):
    item: Item
    bin: Bin
    location: Location
    confidence: float = 1.0

class SessionDetail(Session):
    images: list[SessionImage] = []
    pending_items: list[PendingItem] = []
    is_stale: bool = False
    stale_duration: Optional[str] = None

class ActiveSessionInfo(BaseModel):
    session: Session
    pending_item_count: int
    is_stale: bool
    stale_duration: Optional[str] = None
```

---

## MCP Tools Specification

### Location Tools

```python
# tools/locations.py

@mcp.tool()
def get_locations() -> list[Location]:
    """List all locations"""
    pass

@mcp.tool()
def create_location(name: str, description: str | None = None) -> Location:
    """Create a new location"""
    pass

@mcp.tool()
def update_location(
    location_id: str,
    name: str | None = None,
    description: str | None = None
) -> Location:
    """Update a location"""
    pass

@mcp.tool()
def delete_location(location_id: str) -> dict:
    """Delete a location (fails if bins exist)
    
    Returns: {success: bool, message: str}
    """
    pass
```

### Bin Tools

```python
# tools/bins.py

@mcp.tool()
def get_bins(location_id: str | None = None) -> list[BinWithLocation]:
    """List bins, optionally filtered by location"""
    pass

@mcp.tool()
def get_bin(
    bin_id: str | None = None,
    bin_name: str | None = None,
    include_items: bool = True,
    include_images: bool = False
) -> BinDetail:
    """Get a single bin by ID or name"""
    pass

@mcp.tool()
def create_bin(
    name: str,
    location_id: str,
    description: str | None = None
) -> Bin:
    """Create a new bin"""
    pass

@mcp.tool()
def update_bin(
    bin_id: str,
    name: str | None = None,
    location_id: str | None = None,
    description: str | None = None
) -> Bin:
    """Update a bin"""
    pass

@mcp.tool()
def delete_bin(bin_id: str) -> dict:
    """Delete a bin (fails if items exist)

    Returns: {success: bool, message: str}
    """
    pass

@mcp.tool()
def delete_bins_bulk(bin_ids: list[str]) -> dict:
    """Delete multiple bins at once

    **Constraints:**
    - Bins with items cannot be deleted (must remove items first)

    Returns: {
        success: bool,
        deleted_count: int,
        failed: list[{id: str, error: str}]
    }
    """
    pass
```

### Bin Image Tools

```python
# tools/bins.py (continued)

@mcp.tool()
def get_bin_images(bin_id: str) -> list[BinImage]:
    """Get all images for a bin"""
    pass

@mcp.tool()
def add_bin_image(
    bin_id: str,
    image_base64: str,
    caption: str | None = None,
    is_primary: bool = False
) -> BinImage:
    """Add image to a bin directly (outside session)"""
    pass

@mcp.tool()
def remove_bin_image(image_id: str) -> dict:
    """Remove image from bin
    
    Returns: {success: bool}
    """
    pass

@mcp.tool()
def set_primary_bin_image(bin_id: str, image_id: str) -> BinImage:
    """Set which image is the primary display image"""
    pass
```

### Item Tools

```python
# tools/items.py

@mcp.tool()
def add_item(
    name: str,
    bin_id: str,
    category_id: str | None = None,
    quantity_type: str = "boolean",  # "exact", "approximate", "boolean"
    quantity_value: int | None = None,
    quantity_label: str | None = None,
    description: str | None = None,
    source: str = "manual",  # "manual", "vision", "barcode_lookup"
    source_reference: str | None = None,
    notes: str | None = None  # Free-form text (product lookup info, etc.)
) -> Item:
    """Add an item to inventory"""
    pass

@mcp.tool()
def add_items_bulk(
    items: list[dict],  # [{name, category_id?, quantity_type?, quantity_value?, quantity_label?, notes?}]
    bin_id: str,
    source: str = "vision",
    source_reference: str | None = None
) -> list[Item]:
    """Add multiple items at once (from vision extraction)"""
    pass

@mcp.tool()
def update_item(
    item_id: str,
    name: str | None = None,
    category_id: str | None = None,
    quantity_type: str | None = None,
    quantity_value: int | None = None,
    quantity_label: str | None = None,
    description: str | None = None,
    notes: str | None = None
) -> Item:
    """Update an item"""
    pass

@mcp.tool()
def remove_item(item_id: str, reason: str | None = None) -> dict:
    """Remove an item from inventory entirely
    
    Args:
        reason: "used", "discarded", "lost"
    
    Returns: {success: bool}
    """
    pass

@mcp.tool()
def use_item(
    item_id: str,
    quantity: int = 1,
    notes: str | None = None
) -> Item:
    """Decrement item quantity or mark as used"""
    pass

@mcp.tool()
def move_item(
    item_id: str,
    to_bin_id: str,
    quantity: int | None = None,
    notes: str | None = None
) -> dict:
    """Move item to a different bin

    Args:
        quantity: If provided and less than item's quantity, splits the item

    **Item splitting behavior:**
    - If quantity >= item's quantity: entire item moves
    - If quantity < item's quantity: item splits into two records
      - Original item stays with reduced quantity
      - New item created in target bin with moved quantity

    Returns: {
        moved_item: Item (the item in target bin),
        source_item: Item | None (original item if split, None if fully moved),
        split: bool
    }
    """
    pass

@mcp.tool()
def get_item(item_id: str) -> ItemWithLocation:
    """Get a single item by ID with its bin and location"""
    pass

@mcp.tool()
def delete_items_bulk(
    item_ids: list[str],
    reason: str | None = None
) -> dict:
    """Delete multiple items at once

    Args:
        reason: "used", "discarded", "lost"

    Returns: {
        success: bool,
        deleted_count: int,
        failed: list[{id: str, error: str}]
    }
    """
    pass
```

### Search Tools

```python
# tools/search.py

@mcp.tool()
def search_items(
    query: str,
    location_id: str | None = None,
    bin_id: str | None = None,
    category_id: str | None = None
) -> list[SearchResult]:
    """Search inventory by name, category, or location
    
    Uses fuzzy matching against item names and aliases.
    """
    pass

@mcp.tool()
def find_item(query: str) -> list[SearchResult]:
    """Find where a specific item is located
    
    Returns matches with confidence scores for fuzzy matches.
    """
    pass

@mcp.tool()
def list_items(
    bin_id: str | None = None,
    location_id: str | None = None,
    category_id: str | None = None,
    include_children: bool = True
) -> list[ItemWithLocation]:
    """List items with filters
    
    Args:
        include_children: Include items in subcategories
    """
    pass

@mcp.tool()
def get_item_history(item_id: str) -> list[ActivityLog]:
    """Get activity history for an item"""
    pass
```

### Category Tools

**Category Rules:**
- Categories are hierarchical (parent-child relationships)
- Pre-defined categories are seeded on first run (see Pre-defined Categories section)
- Categories with items cannot be deleted (must reassign items first)

```python
# tools/categories.py

@mcp.tool()
def get_categories(as_tree: bool = False) -> list[Category] | dict:
    """List all categories, optionally as tree structure"""
    pass

@mcp.tool()
def create_category(name: str, parent_id: str | None = None) -> Category:
    """Create a category"""
    pass

@mcp.tool()
def update_category(
    category_id: str,
    name: str | None = None,
    parent_id: str | None = None
) -> Category:
    """Update a category's name or parent"""
    pass

@mcp.tool()
def delete_category(category_id: str) -> dict:
    """Delete a category

    **Behavior:**
    - Cannot delete if category has items (must reassign items first)
    - Empty child categories are cascade-deleted automatically
    - Child categories with items block deletion

    Returns: {
        success: bool,
        message: str,
        deleted_children: list[str]  # IDs of cascade-deleted child categories
    }
    """
    pass
```

### Alias Tools

```python
# tools/aliases.py

@mcp.tool()
def add_alias(item_id: str, alias: str) -> ItemAlias:
    """Add an alias for an item (e.g., 'Allen key' -> 'Hex wrench')"""
    pass

@mcp.tool()
def get_aliases(item_id: str) -> list[ItemAlias]:
    """Get all aliases for an item"""
    pass

@mcp.tool()
def remove_alias(alias_id: str) -> dict:
    """Remove an alias from an item

    Returns: {success: bool}
    """
    pass
```

### Session Tools

**Session Workflow Rules:**
- **Stale sessions**: Sessions not updated within `session_stale_minutes` are marked stale but NOT auto-cancelled
- **Before creating new session**: If stale sessions exist, user must either restore/use one or explicitly cancel them
- **Bin conflicts**: If a new session targets a bin that has a stale session, warn the user
- **Default bin**: If session has only `location_id` at commit time, a bin named "Default" is created in that location

```python
# tools/sessions.py

@mcp.tool()
def get_active_sessions() -> list[ActiveSessionInfo]:
    """Get all pending sessions, with staleness indicator

    Sessions are stale if not updated in 30+ minutes.
    Returns sessions sorted by created_at, with stale sessions flagged.

    **Important**: Before creating a new session, check for stale sessions.
    User should restore, use, or cancel stale sessions before proceeding.
    """
    pass

@mcp.tool()
def create_session(
    bin_id: str | None = None,
    location_id: str | None = None
) -> Session | dict:
    """Create a working session for reviewing/editing items before committing

    **Pre-conditions checked:**
    - If stale sessions exist, returns error with list of stale sessions
      requiring user action (restore or cancel)
    - If target bin has existing pending session, returns warning

    **Target resolution at commit:**
    - If bin_id provided: items go to that bin
    - If only location_id: creates "Default" bin in location at commit time
    - If neither: must be set before commit via set_session_target

    Returns: Session on success, or {error: str, stale_sessions: list} if blocked
    """
    pass

@mcp.tool()
def get_session(session_id: str) -> SessionDetail:
    """Get session with all images and pending items"""
    pass

@mcp.tool()
def add_image_to_session(
    session_id: str,
    image_base64: str,
    extract_items: bool = True,
    context: str | None = None
) -> dict:
    """Add an image to session and optionally extract items
    
    Args:
        context: Hint for extraction, e.g., "this is a hardware bin"
    
    Returns: {
        session_image: SessionImage,
        pending_items: list[PendingItem] (if extract_items),
        labels_detected: list[str],
        suggestions: str
    }
    """
    pass

@mcp.tool()
def update_pending_item(
    session_id: str,
    pending_id: str,
    name: str | None = None,
    quantity_type: str | None = None,
    quantity_value: int | None = None,
    quantity_label: str | None = None,
    category_id: str | None = None
) -> PendingItem:
    """Edit a pending item before committing"""
    pass

@mcp.tool()
def remove_pending_item(session_id: str, pending_id: str) -> dict:
    """Remove an item from pending session
    
    Returns: {success: bool}
    """
    pass

@mcp.tool()
def add_pending_item(
    session_id: str,
    name: str,
    quantity_type: str | None = None,
    quantity_value: int | None = None,
    quantity_label: str | None = None,
    category_id: str | None = None
) -> PendingItem:
    """Manually add an item to pending session"""
    pass

@mcp.tool()
def set_session_target(
    session_id: str,
    bin_id: str | None = None,
    location_id: str | None = None
) -> Session:
    """Set or update the target bin/location for the session"""
    pass

@mcp.tool()
def commit_session(
    session_id: str,
    bin_id: str | None = None
) -> dict:
    """Commit all pending items to inventory

    Args:
        bin_id: Override target bin if not set

    **Target bin resolution:**
    - Uses bin_id parameter if provided
    - Otherwise uses session.target_bin_id
    - If only location_id set, creates bin named "Default" in that location
    - Fails if no target can be determined (no bin_id and no location_id)

    **Side effects:**
    - All session images are copied to bin (always saved)
    - Pending items converted to permanent items
    - Activity log entries created for each item

    Returns: {
        success: bool,
        items_added: list[Item],
        images_saved: list[BinImage],
        bin_created: Bin | None (if default bin was created),
        session: Session (now status=committed)
    }
    """
    pass

@mcp.tool()
def cancel_session(session_id: str, reason: str | None = None) -> Session:
    """Cancel session without committing

    **Side effects:**
    - Session status set to 'cancelled'
    - All session images are deleted from storage
    - Pending items are retained in database for audit trail
    """
    pass

@mcp.tool()
def get_session_history(
    bin_id: str | None = None,
    status: str | None = None,  # "committed", "cancelled"
    limit: int = 20
) -> list[Session]:
    """Get historical sessions (committed/cancelled)"""
    pass
```

### Vision Tools

```python
# tools/vision.py

@mcp.tool()
def extract_items_from_image(
    image_base64: str,
    context: str | None = None
) -> dict:
    """Analyze an image and extract potential inventory items
    
    Args:
        context: Hint like "this is a hardware bin", "these are cables"
    
    Returns: {
        items: [{
            name: str,
            quantity_estimate: str,  # "exact:50" or "approximate:many" or "boolean"
            confidence: float,
            category_suggestion: str
        }],
        labels_detected: list[str],  # Any readable text/barcodes
        suggestions: str  # "I see a product label, want me to look up the details?"
    }
    """
    pass

@mcp.tool()
def lookup_product(
    code: str,
    code_type: str | None = None  # "asin", "upc", "ean"
) -> dict:
    """Lookup product details from barcode/ASIN
    
    Returns: {
        name: str,
        description: str,
        contents: list[str] (for kits),
        source_url: str
    }
    """
    pass
```

---

## Image Storage Service

```python
# src/protea/services/image_store.py

from pathlib import Path
from PIL import Image
import io
import base64

class ImageStore:
    def __init__(self, base_path: Path, image_format: str = "webp", quality: int = 85, thumbnail_size: tuple[int, int] = (200, 200)):
        self.base_path = base_path
        self.image_format = image_format
        self.quality = quality
        self.thumbnail_size = thumbnail_size
        
        # Ensure directories exist
        (self.base_path / "bins").mkdir(parents=True, exist_ok=True)
        (self.base_path / "sessions").mkdir(parents=True, exist_ok=True)
    
    def save_session_image(
        self,
        session_id: str,
        image_base64: str,
        image_id: str,
        original_filename: str | None = None
    ) -> dict:
        """Save image to session directory
        
        Returns: {
            file_path: str,
            thumbnail_path: str,
            width: int,
            height: int,
            file_size_bytes: int
        }
        """
        session_dir = self.base_path / "sessions" / session_id
        session_dir.mkdir(parents=True, exist_ok=True)
        
        # Decode and process image
        image_bytes = base64.b64decode(image_base64)
        img = Image.open(io.BytesIO(image_bytes))
        
        # Save main image
        file_path = session_dir / f"{image_id}.{self.image_format}"
        img.save(file_path, format=self.image_format.upper(), quality=self.quality)
        
        # Create thumbnail
        thumb = img.copy()
        thumb.thumbnail(self.thumbnail_size)
        thumbnail_path = session_dir / f"{image_id}_thumb.{self.image_format}"
        thumb.save(thumbnail_path, format=self.image_format.upper(), quality=self.quality)
        
        return {
            "file_path": str(file_path.relative_to(self.base_path)),
            "thumbnail_path": str(thumbnail_path.relative_to(self.base_path)),
            "width": img.width,
            "height": img.height,
            "file_size_bytes": file_path.stat().st_size
        }
    
    def copy_to_bin(
        self,
        session_image_path: str,
        bin_id: str,
        new_image_id: str
    ) -> dict:
        """Copy session image to bin directory
        
        Returns: {
            file_path: str,
            thumbnail_path: str
        }
        """
        bin_dir = self.base_path / "bins" / bin_id
        bin_dir.mkdir(parents=True, exist_ok=True)
        
        # Copy main image
        src_path = self.base_path / session_image_path
        dst_path = bin_dir / f"{new_image_id}.{self.image_format}"
        
        img = Image.open(src_path)
        img.save(dst_path, format=self.image_format.upper(), quality=self.quality)
        
        # Copy/create thumbnail
        src_thumb = src_path.parent / f"{src_path.stem}_thumb{src_path.suffix}"
        dst_thumb = bin_dir / f"{new_image_id}_thumb.{self.image_format}"
        
        if src_thumb.exists():
            thumb = Image.open(src_thumb)
        else:
            thumb = img.copy()
            thumb.thumbnail(self.thumbnail_size)
        thumb.save(dst_thumb, format=self.image_format.upper(), quality=self.quality)
        
        return {
            "file_path": str(dst_path.relative_to(self.base_path)),
            "thumbnail_path": str(dst_thumb.relative_to(self.base_path))
        }
    
    def delete_image(self, file_path: str) -> bool:
        """Delete an image and its thumbnail"""
        full_path = self.base_path / file_path
        if full_path.exists():
            full_path.unlink()
            
            # Try to delete thumbnail
            thumb_path = full_path.parent / f"{full_path.stem}_thumb{full_path.suffix}"
            if thumb_path.exists():
                thumb_path.unlink()
            
            return True
        return False
    
    def get_absolute_path(self, relative_path: str) -> Path:
        """Get absolute path for an image"""
        return self.base_path / relative_path
```

---

## MCP Server Implementation

```python
# src/protea/server.py

import asyncio
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

from .config import settings
from .db.connection import Database
from .db.models import *
from .services.image_store import ImageStore

# Import all tool modules
from .tools import locations, bins, items, sessions, search, categories, aliases, vision

# Initialize services
db = Database(settings.database_path)
image_store = ImageStore(
    settings.image_base_path,
    settings.image_format,
    settings.image_quality,
    settings.thumbnail_size
)

# Create MCP server
server = Server("protea")

# Register all tools
def register_tools():
    """Register all tools from tool modules"""
    tool_modules = [
        locations,
        bins,
        items,
        sessions,
        search,
        categories,
        aliases,
        vision
    ]
    
    all_tools = []
    for module in tool_modules:
        all_tools.extend(module.get_tools())
    
    return all_tools

@server.list_tools()
async def list_tools() -> list[Tool]:
    """Return list of available tools"""
    return register_tools()

@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    """Route tool calls to appropriate handlers"""
    
    # Tool routing map
    tool_handlers = {
        # Locations
        "get_locations": locations.get_locations,
        "create_location": locations.create_location,
        "update_location": locations.update_location,
        "delete_location": locations.delete_location,
        
        # Bins
        "get_bins": bins.get_bins,
        "get_bin": bins.get_bin,
        "create_bin": bins.create_bin,
        "update_bin": bins.update_bin,
        "delete_bin": bins.delete_bin,
        "delete_bins_bulk": bins.delete_bins_bulk,
        "get_bin_images": bins.get_bin_images,
        "add_bin_image": bins.add_bin_image,
        "remove_bin_image": bins.remove_bin_image,
        "set_primary_bin_image": bins.set_primary_bin_image,

        # Items
        "get_item": items.get_item,
        "add_item": items.add_item,
        "add_items_bulk": items.add_items_bulk,
        "update_item": items.update_item,
        "remove_item": items.remove_item,
        "delete_items_bulk": items.delete_items_bulk,
        "use_item": items.use_item,
        "move_item": items.move_item,

        # Search
        "search_items": search.search_items,
        "find_item": search.find_item,
        "list_items": search.list_items,
        "get_item_history": search.get_item_history,

        # Categories
        "get_categories": categories.get_categories,
        "create_category": categories.create_category,
        "update_category": categories.update_category,
        "delete_category": categories.delete_category,

        # Aliases
        "add_alias": aliases.add_alias,
        "get_aliases": aliases.get_aliases,
        "remove_alias": aliases.remove_alias,
        
        # Sessions
        "get_active_sessions": sessions.get_active_sessions,
        "create_session": sessions.create_session,
        "get_session": sessions.get_session,
        "add_image_to_session": sessions.add_image_to_session,
        "update_pending_item": sessions.update_pending_item,
        "remove_pending_item": sessions.remove_pending_item,
        "add_pending_item": sessions.add_pending_item,
        "set_session_target": sessions.set_session_target,
        "commit_session": sessions.commit_session,
        "cancel_session": sessions.cancel_session,
        "get_session_history": sessions.get_session_history,
        
        # Vision
        "extract_items_from_image": vision.extract_items_from_image,
        "lookup_product": vision.lookup_product,
    }
    
    handler = tool_handlers.get(name)
    if not handler:
        raise ValueError(f"Unknown tool: {name}")
    
    # Inject dependencies
    result = await handler(db=db, image_store=image_store, **arguments)
    
    return [TextContent(type="text", text=result.model_dump_json())]

async def main():
    """Run the MCP server"""
    db.run_migrations()
    
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream)

if __name__ == "__main__":
    asyncio.run(main())
```

---

## Database Connection

```python
# src/protea/db/connection.py

import sqlite3
from pathlib import Path
from contextlib import contextmanager

class Database:
    def __init__(self, db_path: Path | str):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Enable foreign keys and WAL mode
        self._init_connection()
    
    def _init_connection(self):
        """Initialize database with required settings"""
        with self.connection() as conn:
            conn.execute("PRAGMA foreign_keys = ON")
            conn.execute("PRAGMA journal_mode = WAL")
    
    @contextmanager
    def connection(self):
        """Context manager for database connections"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()
    
    def run_migrations(self):
        """Run all pending migrations"""
        migrations_dir = Path(__file__).parent / "migrations"
        
        with self.connection() as conn:
            # Create schema_version table if not exists
            conn.execute("""
                CREATE TABLE IF NOT EXISTS schema_version (
                    version INTEGER PRIMARY KEY,
                    applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Get current version
            result = conn.execute(
                "SELECT MAX(version) as version FROM schema_version"
            ).fetchone()
            current_version = result["version"] or 0
            
            # Find and run pending migrations
            migration_files = sorted(migrations_dir.glob("*.sql"))
            for migration_file in migration_files:
                version = int(migration_file.stem.split("_")[0])
                if version > current_version:
                    print(f"Running migration {migration_file.name}")
                    sql = migration_file.read_text()
                    conn.executescript(sql)
```

---

## Testing Setup

```python
# tests/conftest.py

import pytest
from pathlib import Path
import tempfile

from protea.db.connection import Database
from protea.services.image_store import ImageStore
from protea.config import Settings

@pytest.fixture
def test_settings():
    """Create test settings with temp directories"""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Settings(
            database_path=Path(tmpdir) / "test.db",
            image_base_path=Path(tmpdir) / "images"
        )

@pytest.fixture
def test_db(test_settings):
    """Create test database with migrations"""
    db = Database(test_settings.database_path)
    db.run_migrations()
    return db

@pytest.fixture
def test_image_store(test_settings):
    """Create test image store"""
    return ImageStore(
        test_settings.image_base_path,
        test_settings.image_format,
        test_settings.image_quality,
        test_settings.thumbnail_size
    )

@pytest.fixture
def sample_location(test_db):
    """Create a sample location for testing"""
    from protea.tools import locations
    return locations.create_location(
        db=test_db,
        name="Test Garage",
        description="Test location"
    )

@pytest.fixture
def sample_bin(test_db, sample_location):
    """Create a sample bin for testing"""
    from protea.tools import bins
    return bins.create_bin(
        db=test_db,
        name="Test Bin",
        location_id=sample_location.id,
        description="Test bin"
    )
```

```python
# tests/test_locations.py

import pytest
from protea.tools import locations

def test_create_location(test_db):
    result = locations.create_location(
        db=test_db,
        name="Garage",
        description="Main garage"
    )
    
    assert result.name == "Garage"
    assert result.description == "Main garage"
    assert result.id is not None

def test_get_locations(test_db):
    locations.create_location(db=test_db, name="Garage")
    locations.create_location(db=test_db, name="Workshop")
    
    result = locations.get_locations(db=test_db)
    
    assert len(result) == 2
    names = [loc.name for loc in result]
    assert "Garage" in names
    assert "Workshop" in names

def test_delete_location_with_bins_fails(test_db, sample_bin):
    """Cannot delete location that has bins"""
    from protea.tools import bins
    
    result = locations.delete_location(
        db=test_db,
        location_id=sample_bin.location_id
    )
    
    assert result["success"] is False
    assert "bins" in result["message"].lower()
```

---

## Pre-defined Categories

Categories are seeded on first database migration. Users can add custom categories, but these provide a starting hierarchy for common home workshop/lab items:

```sql
-- migrations/002_seed_categories.sql

-- Hardware
INSERT INTO categories (id, name, parent_id) VALUES
    ('cat-hardware', 'Hardware', NULL),
    ('cat-fasteners', 'Fasteners', 'cat-hardware'),
    ('cat-screws', 'Screws', 'cat-fasteners'),
    ('cat-bolts', 'Bolts', 'cat-fasteners'),
    ('cat-nuts', 'Nuts', 'cat-fasteners'),
    ('cat-washers', 'Washers', 'cat-fasteners'),
    ('cat-nails', 'Nails', 'cat-fasteners'),
    ('cat-anchors', 'Anchors', 'cat-fasteners'),

-- Tools
    ('cat-tools', 'Tools', NULL),
    ('cat-hand-tools', 'Hand Tools', 'cat-tools'),
    ('cat-power-tools', 'Power Tools', 'cat-tools'),
    ('cat-measuring', 'Measuring', 'cat-tools'),

-- Electronics
    ('cat-electronics', 'Electronics', NULL),
    ('cat-components', 'Components', 'cat-electronics'),
    ('cat-cables', 'Cables & Connectors', 'cat-electronics'),
    ('cat-boards', 'Boards & Modules', 'cat-electronics'),

-- Supplies
    ('cat-supplies', 'Supplies', NULL),
    ('cat-adhesives', 'Adhesives & Tape', 'cat-supplies'),
    ('cat-lubricants', 'Lubricants', 'cat-supplies'),
    ('cat-safety', 'Safety Equipment', 'cat-supplies'),

-- Materials
    ('cat-materials', 'Materials', NULL),
    ('cat-wood', 'Wood', 'cat-materials'),
    ('cat-metal', 'Metal', 'cat-materials'),
    ('cat-plastic', 'Plastic', 'cat-materials'),

-- Other
    ('cat-other', 'Other', NULL);
```

### Category Tree Structure

```
Hardware
├── Fasteners
│   ├── Screws
│   ├── Bolts
│   ├── Nuts
│   ├── Washers
│   ├── Nails
│   └── Anchors
Tools
├── Hand Tools
├── Power Tools
└── Measuring
Electronics
├── Components
├── Cables & Connectors
└── Boards & Modules
Supplies
├── Adhesives & Tape
├── Lubricants
└── Safety Equipment
Materials
├── Wood
├── Metal
└── Plastic
Other
```

---

## pyproject.toml

```toml
[project]
name = "protea"
version = "0.1.0"
description = "MCP server for physical inventory management with vision support"
readme = "README.md"
requires-python = ">=3.11"
dependencies = [
    "mcp>=0.9.0",
    "pydantic>=2.0.0",
    "pydantic-settings>=2.0.0",
    "pillow>=10.0.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=7.0.0",
    "pytest-asyncio>=0.21.0",
    "ruff>=0.1.0",
]

[project.scripts]
protea = "protea.server:main"

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.ruff]
line-length = 100
target-version = "py311"

[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]
```

---

## .gitignore

```
# Python
__pycache__/
*.py[cod]
*$py.class
*.so
.Python
build/
develop-eggs/
dist/
downloads/
eggs/
.eggs/
lib/
lib64/
parts/
sdist/
var/
wheels/
*.egg-info/
.installed.cfg
*.egg

# Virtual environments
venv/
ENV/
env/
.venv/

# IDE
.idea/
.vscode/
*.swp
*.swo

# Project specific
data/
!data/.gitkeep
*.db
*.db-journal
*.db-wal

# Testing
.pytest_cache/
.coverage
htmlcov/

# Environment
.env
.env.local
```

---

## Example Interactions

### Adding items with image

```
User: "Add these to my hardware bin" [+ image of screws]

Agent: get_active_sessions() → no active sessions
Agent: create_session(bin_id="hardware-bin-uuid")
Agent: add_image_to_session(session_id="...", image_base64="...", context="hardware")

Response: "I see:
- M3 socket head cap screws (~50)
- M4 hex nuts (~30)
- Assorted washers

Add these to Hardware Bin in Garage?"

User: "Yes"

Agent: commit_session(session_id="...")

Response: "Added 3 items to Hardware Bin. Image saved."
```

### Querying inventory

```
User: "Do I have any M3 screws?"

Agent: find_item(query="M3 screws")

Response: "Yes, you have M3 socket head cap screws (~50) in Hardware Bin, Garage."
```

### Category query

```
User: "What tape do I have?"

Agent: search_items(query="tape")

Response: "You have 3 types of tape:
- Masking tape in Garage/Workbench Bin
- Electrical tape in Garage/Electronics Bin  
- Scotch tape in Office/Desk Drawer"
```

---

## Future Enhancements (Round 2+)

1. **Web UI** - Browse, search, view images
2. **Home Assistant integration** - Voice commands via Assist
3. **Barcode scanning** - Camera-based UPC/ASIN lookup
4. **Low stock alerts** - Notifications when items run low
5. **Reorder links** - Amazon/supplier links for restocking
6. **Export/import** - CSV/JSON backup and restore
7. **Multi-user** - Shared household inventory
8. **PostgreSQL migration** - For concurrent access

---

## Getting Started

1. Clone repository
2. Create virtual environment: `python -m venv venv`
3. Install dependencies: `pip install -e ".[dev]"`
4. Run migrations: `protea --migrate` (or auto on first run)
5. Configure MCP client to connect to server
6. Start using!

```bash
# Run server directly
python -m protea.server

# Or via installed script
protea
```

---

## Design Decisions Summary

Key architectural and design decisions documented in this specification:

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Vision extraction | Both workflows supported | Flexibility - orchestrating LLM can handle, or server can call Claude API directly |
| Product lookup APIs | Amazon Product API + UPCitemdb | Coverage for both ASIN and UPC codes |
| Product lookup storage | Item `notes` field | Free-form text field for lookup results, user annotations |
| Stale session handling | Mark stale, prompt user | User decides to restore or cancel; no auto-delete |
| Session images | Keep on commit, delete on cancel | Preserves valuable photos; cleans up abandoned sessions |
| Default bin | Named "Default", auto-created | Reduces friction; simple naming convention |
| Item splitting | Single activity log entry | References both source and new item for complete traceability |
| Category deletion | Cascade empty children | Convenience; blocks if any child has items |
| Categories | Pre-defined with user extensions | Quick start for common items; fully customizable |
| FTS scope | Items only (prefix matching) | Simple, performant; future: vector search with Chroma |
| Error handling | Standardized format with codes | Consistent LLM-friendly error responses |
| Image size | Configurable, default 10MB | Accommodates phone photos; prevents runaway storage |
