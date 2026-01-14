"""Pydantic models for inventory-mcp database entities."""

import uuid
from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


def generate_id() -> str:
    """Generate a UUID string for entity IDs."""
    return str(uuid.uuid4())


class QuantityType(str, Enum):
    """Type of quantity tracking for an item."""

    EXACT = "exact"
    APPROXIMATE = "approximate"
    BOOLEAN = "boolean"


class ItemSource(str, Enum):
    """Source of item data."""

    MANUAL = "manual"
    VISION = "vision"
    BARCODE_LOOKUP = "barcode_lookup"


class PendingItemSource(str, Enum):
    """Source of pending item data."""

    VISION = "vision"
    MANUAL = "manual"


class SessionStatus(str, Enum):
    """Status of an inventory session."""

    PENDING = "pending"
    COMMITTED = "committed"
    CANCELLED = "cancelled"


class ActivityAction(str, Enum):
    """Type of activity logged for an item."""

    ADDED = "added"
    REMOVED = "removed"
    MOVED = "moved"
    UPDATED = "updated"
    USED = "used"


# --- Core Models ---


class Location(BaseModel):
    """A physical location (room, area) containing bins."""

    id: str = Field(default_factory=generate_id)
    name: str
    description: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class Bin(BaseModel):
    """A container within a location that holds items.

    Bins can be nested - a bin with parent_bin_id is inside another bin.
    Example: Location(Garage) -> Bin(Tool Chest) -> Bin(Drawer 9) -> Item
    """

    id: str = Field(default_factory=generate_id)
    name: str
    location_id: str
    parent_bin_id: Optional[str] = None  # Parent bin for nesting (None = root level)
    description: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class BinImage(BaseModel):
    """An image associated with a bin."""

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
    """A hierarchical category for organizing items."""

    id: str = Field(default_factory=generate_id)
    name: str
    parent_id: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)


class Item(BaseModel):
    """An inventory item stored in a bin."""

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
    notes: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class ItemAlias(BaseModel):
    """An alternative name for an item (for fuzzy matching)."""

    id: str = Field(default_factory=generate_id)
    item_id: str
    alias: str


class ActivityLog(BaseModel):
    """A log entry for item activity."""

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
    """A working session for reviewing/editing items before committing."""

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
    """An image uploaded during a session."""

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
    """An item pending in a session, not yet committed."""

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
    """Bin with its parent location included."""

    location: Location


class BinDetail(Bin):
    """Bin with full details including items and images."""

    location: Location
    items: list[Item] = []
    images: list[BinImage] = []
    item_count: int = 0
    image_count: int = 0
    parent_bin: Optional[Bin] = None  # Parent bin if nested
    child_bins: list[Bin] = []  # Direct child bins
    path: list[str] = []  # Ancestor bin names from root to parent
    full_path: str = ""  # Full path including location


class BinTreeNode(BaseModel):
    """A bin node in a tree structure for hierarchical display."""

    id: str
    name: str
    description: Optional[str] = None
    parent_bin_id: Optional[str] = None
    item_count: int = 0
    child_count: int = 0
    children: list["BinTreeNode"] = []


# Enable forward reference resolution for recursive model
BinTreeNode.model_rebuild()


class ItemWithLocation(Item):
    """Item with its bin and location included."""

    bin: Bin
    location: Location


class SearchResult(BaseModel):
    """A search result with confidence score."""

    item: Item
    bin: Bin
    location: Location
    match_score: float = 1.0
    bin_path: str = ""  # Full path like "Garage/Tool Chest/Drawer 9"


class SessionDetail(Session):
    """Session with full details including images and pending items."""

    images: list[SessionImage] = []
    pending_items: list[PendingItem] = []
    is_stale: bool = False
    stale_duration_minutes: Optional[int] = None


class ActiveSessionInfo(BaseModel):
    """Summary info about an active session."""

    session: Session
    pending_item_count: int
    image_count: int
    is_stale: bool
    stale_duration_minutes: Optional[int] = None
