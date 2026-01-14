"""Bin management tools for inventory-mcp."""

from datetime import datetime

from inventory_mcp.db.connection import Database
from inventory_mcp.db.models import (
    Bin,
    BinDetail,
    BinImage,
    BinPathPart,
    BinTreeNode,
    BinWithLocation,
    Item,
    Location,
)
from inventory_mcp.services.image_store import ImageStore


# --- Helper Functions for Nested Bins ---


def _get_bin_ancestors(db: Database, bin_id: str) -> list[Bin]:
    """Get all ancestor bins from root to immediate parent.

    Returns list ordered from root ancestor to immediate parent.
    """
    ancestors = []
    current_id = bin_id
    visited = set()  # Prevent infinite loops

    # First get the bin's parent_bin_id
    row = db.execute_one("SELECT parent_bin_id FROM bins WHERE id = ?", (current_id,))
    if not row or not row["parent_bin_id"]:
        return ancestors

    current_id = row["parent_bin_id"]

    while current_id:
        if current_id in visited:
            break  # Circular reference protection
        visited.add(current_id)

        parent_row = db.execute_one("SELECT * FROM bins WHERE id = ?", (current_id,))
        if not parent_row:
            break

        ancestors.insert(
            0,
            Bin(
                id=parent_row["id"],
                name=parent_row["name"],
                location_id=parent_row["location_id"],
                parent_bin_id=parent_row["parent_bin_id"],
                description=parent_row["description"],
                created_at=parent_row["created_at"],
                updated_at=parent_row["updated_at"],
            ),
        )
        current_id = parent_row["parent_bin_id"]

    return ancestors


def _build_bin_path(db: Database, bin_id: str, include_location: bool = True) -> str:
    """Build full path string for a bin.

    Returns path like "Garage/Tool Chest/Drawer 9" or "Tool Chest/Drawer 9".
    """
    row = db.execute_one(
        """
        SELECT b.name, b.location_id, l.name as loc_name
        FROM bins b
        JOIN locations l ON b.location_id = l.id
        WHERE b.id = ?
        """,
        (bin_id,),
    )
    if not row:
        return ""

    ancestors = _get_bin_ancestors(db, bin_id)
    path_parts = [a.name for a in ancestors] + [row["name"]]

    if include_location:
        path_parts.insert(0, row["loc_name"])

    return "/".join(path_parts)


def _is_descendant(db: Database, potential_ancestor_id: str, potential_descendant_id: str) -> bool:
    """Check if potential_ancestor_id is an ancestor of potential_descendant_id.

    Used to prevent circular references when moving bins.
    """
    current_id = potential_descendant_id
    visited = set()

    while current_id:
        if current_id in visited:
            return False  # Circular reference detected, stop
        visited.add(current_id)

        if current_id == potential_ancestor_id:
            return True

        row = db.execute_one("SELECT parent_bin_id FROM bins WHERE id = ?", (current_id,))
        if not row:
            break
        current_id = row["parent_bin_id"]

    return False


def _get_location(db: Database, location_id: str) -> Location | None:
    """Helper to get a location by ID."""
    row = db.execute_one(
        "SELECT * FROM locations WHERE id = ?",
        (location_id,),
    )
    if row:
        return Location(
            id=row["id"],
            name=row["name"],
            description=row["description"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )
    return None


# --- New Nested Bin Tools ---


def get_bin_by_path(
    db: Database,
    path: str,
    location_id: str | None = None,
    location_name: str | None = None,
) -> BinDetail | dict:
    """Resolve a bin by its full path in a single call.

    Path format: "Location/Bin1/Bin2/TargetBin" or "Bin1/Bin2/TargetBin" (if location provided)

    Args:
        db: Database connection
        path: Path string like "Garage/Tool Chest/Drawer 9"
        location_id: Optional location UUID (if path doesn't include location)
        location_name: Optional location name (if path doesn't include location)

    Returns:
        BinDetail or error dict
    """
    parts = [p.strip() for p in path.split("/") if p.strip()]
    if not parts:
        return {"error": "Empty path", "error_code": "INVALID_INPUT"}

    # Determine location
    if location_id:
        loc_row = db.execute_one("SELECT * FROM locations WHERE id = ?", (location_id,))
    elif location_name:
        loc_row = db.execute_one("SELECT * FROM locations WHERE name = ?", (location_name,))
    else:
        # First part is location name
        loc_row = db.execute_one("SELECT * FROM locations WHERE name = ?", (parts[0],))
        parts = parts[1:]  # Remove location from path

    if not loc_row:
        return {"error": "Location not found", "error_code": "NOT_FOUND"}

    if not parts:
        return {"error": "No bin specified in path", "error_code": "INVALID_INPUT"}

    # Walk down the path
    current_parent_id = None
    current_bin_id = None

    for bin_name in parts:
        if current_parent_id:
            row = db.execute_one(
                "SELECT id FROM bins WHERE name = ? AND location_id = ? AND parent_bin_id = ?",
                (bin_name, loc_row["id"], current_parent_id),
            )
        else:
            row = db.execute_one(
                "SELECT id FROM bins WHERE name = ? AND location_id = ? AND parent_bin_id IS NULL",
                (bin_name, loc_row["id"]),
            )

        if not row:
            return {
                "error": f"Bin '{bin_name}' not found in path",
                "error_code": "NOT_FOUND",
                "details": {"path": path, "missing_segment": bin_name},
            }

        current_parent_id = row["id"]
        current_bin_id = row["id"]

    # Get full bin details
    return get_bin(db, bin_id=current_bin_id, include_items=True, include_images=True)


def get_bin_tree(
    db: Database,
    location_id: str | None = None,
    root_bin_id: str | None = None,
    max_depth: int = 10,
) -> dict:
    """Get nested tree structure of bins.

    Args:
        db: Database connection
        location_id: Filter by location
        root_bin_id: Start from specific bin (get subtree)
        max_depth: Maximum nesting depth to prevent runaway recursion

    Returns:
        Dict with tree structure: {"bins": [BinTreeNode, ...]}
    """

    def build_node(bin_row, depth: int = 0) -> dict | None:
        if depth >= max_depth:
            return None

        bin_id = bin_row["id"]

        # Get item count
        item_count = db.execute_one(
            "SELECT COUNT(*) as cnt FROM items WHERE bin_id = ?",
            (bin_id,),
        )

        # Get children
        children_rows = db.execute(
            "SELECT * FROM bins WHERE parent_bin_id = ? ORDER BY name",
            (bin_id,),
        )

        children = []
        for child_row in children_rows:
            child_node = build_node(child_row, depth + 1)
            if child_node:
                children.append(child_node)

        return {
            "id": bin_row["id"],
            "name": bin_row["name"],
            "description": bin_row["description"],
            "parent_bin_id": bin_row["parent_bin_id"],
            "item_count": item_count["cnt"] if item_count else 0,
            "child_count": len(children),
            "children": children,
        }

    if root_bin_id:
        # Get subtree from specific bin
        root_row = db.execute_one("SELECT * FROM bins WHERE id = ?", (root_bin_id,))
        if not root_row:
            return {"error": "Bin not found", "error_code": "NOT_FOUND"}
        node = build_node(root_row)
        return {"bins": [node] if node else []}

    # Get root-level bins (no parent)
    if location_id:
        root_rows = db.execute(
            "SELECT * FROM bins WHERE location_id = ? AND parent_bin_id IS NULL ORDER BY name",
            (location_id,),
        )
    else:
        root_rows = db.execute(
            "SELECT * FROM bins WHERE parent_bin_id IS NULL ORDER BY name"
        )

    bins = []
    for row in root_rows:
        node = build_node(row)
        if node:
            bins.append(node)

    return {"bins": bins}


def get_bins(
    db: Database,
    location_id: str | None = None,
    parent_bin_id: str | None = None,
    root_only: bool = False,
) -> list[BinWithLocation]:
    """List bins, optionally filtered by location or parent.

    Args:
        db: Database connection
        location_id: Optional location filter
        parent_bin_id: Optional parent bin filter (get children of this bin)
        root_only: If True, only return root-level bins (parent_bin_id IS NULL)

    Returns:
        List of bins with their locations
    """
    conditions = []
    params = []

    if location_id:
        conditions.append("b.location_id = ?")
        params.append(location_id)

    if parent_bin_id:
        conditions.append("b.parent_bin_id = ?")
        params.append(parent_bin_id)
    elif root_only:
        conditions.append("b.parent_bin_id IS NULL")

    where_clause = ""
    if conditions:
        where_clause = "WHERE " + " AND ".join(conditions)

    rows = db.execute(
        f"""
        SELECT b.*, l.name as loc_name, l.description as loc_desc,
               l.created_at as loc_created, l.updated_at as loc_updated
        FROM bins b
        JOIN locations l ON b.location_id = l.id
        {where_clause}
        ORDER BY l.name, b.name
        """,
        tuple(params),
    )

    return [
        BinWithLocation(
            id=row["id"],
            name=row["name"],
            location_id=row["location_id"],
            parent_bin_id=row["parent_bin_id"],
            description=row["description"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            location=Location(
                id=row["location_id"],
                name=row["loc_name"],
                description=row["loc_desc"],
                created_at=row["loc_created"],
                updated_at=row["loc_updated"],
            ),
        )
        for row in rows
    ]


def get_bin(
    db: Database,
    bin_id: str | None = None,
    bin_name: str | None = None,
    include_items: bool = True,
    include_images: bool = False,
) -> BinDetail | dict:
    """Get a single bin by ID or name.

    Args:
        db: Database connection
        bin_id: Bin UUID
        bin_name: Bin name (searches across all locations)
        include_items: Include items in response
        include_images: Include images in response

    Returns:
        BinDetail or error dict
    """
    if bin_id:
        row = db.execute_one(
            """
            SELECT b.*, l.name as loc_name, l.description as loc_desc,
                   l.created_at as loc_created, l.updated_at as loc_updated
            FROM bins b
            JOIN locations l ON b.location_id = l.id
            WHERE b.id = ?
            """,
            (bin_id,),
        )
    elif bin_name:
        row = db.execute_one(
            """
            SELECT b.*, l.name as loc_name, l.description as loc_desc,
                   l.created_at as loc_created, l.updated_at as loc_updated
            FROM bins b
            JOIN locations l ON b.location_id = l.id
            WHERE b.name = ?
            """,
            (bin_name,),
        )
    else:
        return {
            "error": "Must provide either bin_id or bin_name",
            "error_code": "INVALID_INPUT",
        }

    if not row:
        return {
            "error": "Bin not found",
            "error_code": "NOT_FOUND",
        }

    location = Location(
        id=row["location_id"],
        name=row["loc_name"],
        description=row["loc_desc"],
        created_at=row["loc_created"],
        updated_at=row["loc_updated"],
    )

    items = []
    if include_items:
        item_rows = db.execute(
            "SELECT * FROM items WHERE bin_id = ? ORDER BY name",
            (row["id"],),
        )
        items = [
            Item(
                id=r["id"],
                name=r["name"],
                description=r["description"],
                category_id=r["category_id"],
                bin_id=r["bin_id"],
                quantity_type=r["quantity_type"],
                quantity_value=r["quantity_value"],
                quantity_label=r["quantity_label"],
                source=r["source"],
                source_reference=r["source_reference"],
                photo_url=r["photo_url"],
                notes=r["notes"],
                created_at=r["created_at"],
                updated_at=r["updated_at"],
            )
            for r in item_rows
        ]

    images = []
    if include_images:
        image_rows = db.execute(
            "SELECT * FROM bin_images WHERE bin_id = ? ORDER BY is_primary DESC, created_at",
            (row["id"],),
        )
        images = [
            BinImage(
                id=r["id"],
                bin_id=r["bin_id"],
                file_path=r["file_path"],
                thumbnail_path=r["thumbnail_path"],
                caption=r["caption"],
                is_primary=bool(r["is_primary"]),
                source_session_id=r["source_session_id"],
                source_session_image_id=r["source_session_image_id"],
                width=r["width"],
                height=r["height"],
                file_size_bytes=r["file_size_bytes"],
                created_at=r["created_at"],
            )
            for r in image_rows
        ]

    # Get counts
    item_count = db.execute_one(
        "SELECT COUNT(*) as cnt FROM items WHERE bin_id = ?",
        (row["id"],),
    )
    image_count = db.execute_one(
        "SELECT COUNT(*) as cnt FROM bin_images WHERE bin_id = ?",
        (row["id"],),
    )

    # Get parent bin if nested
    parent_bin = None
    if row["parent_bin_id"]:
        parent_row = db.execute_one(
            "SELECT * FROM bins WHERE id = ?",
            (row["parent_bin_id"],),
        )
        if parent_row:
            parent_bin = Bin(
                id=parent_row["id"],
                name=parent_row["name"],
                location_id=parent_row["location_id"],
                parent_bin_id=parent_row["parent_bin_id"],
                description=parent_row["description"],
                created_at=parent_row["created_at"],
                updated_at=parent_row["updated_at"],
            )

    # Get child bins
    child_rows = db.execute(
        "SELECT * FROM bins WHERE parent_bin_id = ? ORDER BY name",
        (row["id"],),
    )
    child_bins = [
        Bin(
            id=r["id"],
            name=r["name"],
            location_id=r["location_id"],
            parent_bin_id=r["parent_bin_id"],
            description=r["description"],
            created_at=r["created_at"],
            updated_at=r["updated_at"],
        )
        for r in child_rows
    ]

    # Build path
    ancestor_bins = _get_bin_ancestors(db, row["id"])
    path = [a.name for a in ancestor_bins]
    full_path = _build_bin_path(db, row["id"], include_location=True)

    # Build ancestors list with IDs for navigation links
    ancestors = [BinPathPart(id=location.id, name=location.name, type="location")]
    for ancestor in ancestor_bins:
        ancestors.append(BinPathPart(id=ancestor.id, name=ancestor.name, type="bin"))

    return BinDetail(
        id=row["id"],
        name=row["name"],
        location_id=row["location_id"],
        parent_bin_id=row["parent_bin_id"],
        description=row["description"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
        location=location,
        items=items,
        images=images,
        item_count=item_count["cnt"] if item_count else 0,
        image_count=image_count["cnt"] if image_count else 0,
        parent_bin=parent_bin,
        child_bins=child_bins,
        path=path,
        full_path=full_path,
        ancestors=ancestors,
    )


def create_bin(
    db: Database,
    name: str,
    location_id: str,
    parent_bin_id: str | None = None,
    description: str | None = None,
) -> Bin | dict:
    """Create a new bin, optionally nested inside another bin.

    Args:
        db: Database connection
        name: Bin name
        location_id: Parent location UUID
        parent_bin_id: Optional parent bin UUID for nesting
        description: Optional description

    Returns:
        Created Bin or error dict
    """
    # Verify location exists
    location = _get_location(db, location_id)
    if not location:
        return {
            "error": "Location not found",
            "error_code": "NOT_FOUND",
            "details": {"location_id": location_id},
        }

    # Verify parent bin exists and is in same location
    if parent_bin_id:
        parent_bin = db.execute_one(
            "SELECT * FROM bins WHERE id = ?",
            (parent_bin_id,),
        )
        if not parent_bin:
            return {
                "error": "Parent bin not found",
                "error_code": "NOT_FOUND",
                "details": {"parent_bin_id": parent_bin_id},
            }
        if parent_bin["location_id"] != location_id:
            return {
                "error": "Parent bin must be in the same location",
                "error_code": "INVALID_INPUT",
            }

    # Check for duplicate name at same level (same parent)
    if parent_bin_id:
        existing = db.execute_one(
            "SELECT id FROM bins WHERE name = ? AND location_id = ? AND parent_bin_id = ?",
            (name, location_id, parent_bin_id),
        )
    else:
        existing = db.execute_one(
            "SELECT id FROM bins WHERE name = ? AND location_id = ? AND parent_bin_id IS NULL",
            (name, location_id),
        )

    if existing:
        return {
            "error": f"Bin with name '{name}' already exists at this level",
            "error_code": "ALREADY_EXISTS",
        }

    bin_obj = Bin(
        name=name,
        location_id=location_id,
        parent_bin_id=parent_bin_id,
        description=description,
    )

    with db.connection() as conn:
        conn.execute(
            """
            INSERT INTO bins (id, name, location_id, parent_bin_id, description, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                bin_obj.id,
                bin_obj.name,
                bin_obj.location_id,
                bin_obj.parent_bin_id,
                bin_obj.description,
                bin_obj.created_at.isoformat(),
                bin_obj.updated_at.isoformat(),
            ),
        )

    return bin_obj


def update_bin(
    db: Database,
    bin_id: str,
    name: str | None = None,
    location_id: str | None = None,
    parent_bin_id: str | None = None,
    description: str | None = None,
) -> Bin | dict:
    """Update a bin.

    Args:
        db: Database connection
        bin_id: Bin UUID
        name: New name (optional)
        location_id: New location (optional)
        parent_bin_id: New parent bin (optional, use "" to move to root level)
        description: New description (optional)

    Returns:
        Updated Bin or error dict
    """
    row = db.execute_one("SELECT * FROM bins WHERE id = ?", (bin_id,))
    if not row:
        return {
            "error": "Bin not found",
            "error_code": "NOT_FOUND",
            "details": {"bin_id": bin_id},
        }

    new_name = name if name is not None else row["name"]
    new_location_id = location_id if location_id is not None else row["location_id"]
    new_description = description if description is not None else row["description"]

    # Handle parent_bin_id: None means no change, "" means move to root
    if parent_bin_id is None:
        new_parent_bin_id = row["parent_bin_id"]
    elif parent_bin_id == "":
        new_parent_bin_id = None  # Move to root level
    else:
        new_parent_bin_id = parent_bin_id

    # Verify new location if changed
    if location_id and location_id != row["location_id"]:
        location = _get_location(db, location_id)
        if not location:
            return {
                "error": "New location not found",
                "error_code": "NOT_FOUND",
                "details": {"location_id": location_id},
            }
        # If changing location, must also update parent (can't have parent in different location)
        if new_parent_bin_id:
            parent_row = db.execute_one("SELECT location_id FROM bins WHERE id = ?", (new_parent_bin_id,))
            if parent_row and parent_row["location_id"] != new_location_id:
                return {
                    "error": "Parent bin must be in the same location",
                    "error_code": "INVALID_INPUT",
                }

    # Verify new parent bin if changed
    if parent_bin_id is not None and parent_bin_id != "":
        parent_row = db.execute_one("SELECT * FROM bins WHERE id = ?", (new_parent_bin_id,))
        if not parent_row:
            return {
                "error": "Parent bin not found",
                "error_code": "NOT_FOUND",
                "details": {"parent_bin_id": new_parent_bin_id},
            }
        # Verify parent is in same location
        if parent_row["location_id"] != new_location_id:
            return {
                "error": "Parent bin must be in the same location",
                "error_code": "INVALID_INPUT",
            }
        # Prevent circular reference - can't set parent to self or descendant
        if new_parent_bin_id == bin_id:
            return {
                "error": "Cannot set bin as its own parent",
                "error_code": "CIRCULAR_REFERENCE",
            }
        if _is_descendant(db, bin_id, new_parent_bin_id):
            return {
                "error": "Cannot move bin into its own descendant (would create circular reference)",
                "error_code": "CIRCULAR_REFERENCE",
            }

    # Check for name conflict at target level
    if name or location_id or parent_bin_id is not None:
        if new_parent_bin_id:
            existing = db.execute_one(
                "SELECT id FROM bins WHERE name = ? AND location_id = ? AND parent_bin_id = ? AND id != ?",
                (new_name, new_location_id, new_parent_bin_id, bin_id),
            )
        else:
            existing = db.execute_one(
                "SELECT id FROM bins WHERE name = ? AND location_id = ? AND parent_bin_id IS NULL AND id != ?",
                (new_name, new_location_id, bin_id),
            )
        if existing:
            return {
                "error": f"Bin with name '{new_name}' already exists at this level",
                "error_code": "ALREADY_EXISTS",
            }

    updated_at = datetime.utcnow()

    with db.connection() as conn:
        conn.execute(
            """
            UPDATE bins
            SET name = ?, location_id = ?, parent_bin_id = ?, description = ?, updated_at = ?
            WHERE id = ?
            """,
            (new_name, new_location_id, new_parent_bin_id, new_description, updated_at.isoformat(), bin_id),
        )

    return Bin(
        id=bin_id,
        name=new_name,
        location_id=new_location_id,
        parent_bin_id=new_parent_bin_id,
        description=new_description,
        created_at=row["created_at"],
        updated_at=updated_at,
    )


def delete_bin(db: Database, bin_id: str) -> dict:
    """Delete a bin.

    Fails if the bin has items or child bins.

    Args:
        db: Database connection
        bin_id: Bin UUID

    Returns:
        Success/error dict
    """
    row = db.execute_one("SELECT * FROM bins WHERE id = ?", (bin_id,))
    if not row:
        return {
            "error": "Bin not found",
            "error_code": "NOT_FOUND",
            "details": {"bin_id": bin_id},
        }

    # Check for child bins
    child_count = db.execute_one(
        "SELECT COUNT(*) as cnt FROM bins WHERE parent_bin_id = ?",
        (bin_id,),
    )
    if child_count and child_count["cnt"] > 0:
        return {
            "success": False,
            "error": f"Cannot delete bin with {child_count['cnt']} child bins. Remove or move child bins first.",
            "error_code": "HAS_CHILDREN",
            "details": {"child_count": child_count["cnt"]},
        }

    # Check for items
    item_count = db.execute_one(
        "SELECT COUNT(*) as cnt FROM items WHERE bin_id = ?",
        (bin_id,),
    )
    if item_count and item_count["cnt"] > 0:
        return {
            "success": False,
            "error": f"Cannot delete bin with {item_count['cnt']} items. Remove items first.",
            "error_code": "HAS_DEPENDENCIES",
            "details": {"item_count": item_count["cnt"]},
        }

    with db.connection() as conn:
        # Delete images first (CASCADE should handle this but be explicit)
        conn.execute("DELETE FROM bin_images WHERE bin_id = ?", (bin_id,))
        conn.execute("DELETE FROM bins WHERE id = ?", (bin_id,))

    return {
        "success": True,
        "message": f"Bin '{row['name']}' deleted",
    }


def delete_bins_bulk(db: Database, bin_ids: list[str]) -> dict:
    """Delete multiple bins at once.

    Args:
        db: Database connection
        bin_ids: List of bin UUIDs

    Returns:
        Result dict with success count and failures
    """
    deleted = 0
    failed = []

    for bin_id in bin_ids:
        result = delete_bin(db, bin_id)
        if result.get("success"):
            deleted += 1
        else:
            failed.append({"id": bin_id, "error": result.get("error", "Unknown error")})

    return {
        "success": len(failed) == 0,
        "deleted_count": deleted,
        "failed": failed,
    }


# --- Bin Image Tools ---


def get_bin_images(db: Database, bin_id: str) -> list[BinImage] | dict:
    """Get all images for a bin.

    Args:
        db: Database connection
        bin_id: Bin UUID

    Returns:
        List of BinImage or error dict
    """
    # Verify bin exists
    bin_row = db.execute_one("SELECT id FROM bins WHERE id = ?", (bin_id,))
    if not bin_row:
        return {
            "error": "Bin not found",
            "error_code": "NOT_FOUND",
            "details": {"bin_id": bin_id},
        }

    rows = db.execute(
        "SELECT * FROM bin_images WHERE bin_id = ? ORDER BY is_primary DESC, created_at",
        (bin_id,),
    )

    return [
        BinImage(
            id=row["id"],
            bin_id=row["bin_id"],
            file_path=row["file_path"],
            thumbnail_path=row["thumbnail_path"],
            caption=row["caption"],
            is_primary=bool(row["is_primary"]),
            source_session_id=row["source_session_id"],
            source_session_image_id=row["source_session_image_id"],
            width=row["width"],
            height=row["height"],
            file_size_bytes=row["file_size_bytes"],
            created_at=row["created_at"],
        )
        for row in rows
    ]


def add_bin_image(
    db: Database,
    image_store: ImageStore,
    bin_id: str,
    image_base64: str,
    caption: str | None = None,
    is_primary: bool = False,
) -> BinImage | dict:
    """Add image to a bin directly.

    Args:
        db: Database connection
        image_store: Image storage service
        bin_id: Bin UUID
        image_base64: Base64-encoded image
        caption: Optional caption
        is_primary: Set as primary image

    Returns:
        Created BinImage or error dict
    """
    # Verify bin exists
    bin_row = db.execute_one("SELECT id FROM bins WHERE id = ?", (bin_id,))
    if not bin_row:
        return {
            "error": "Bin not found",
            "error_code": "NOT_FOUND",
            "details": {"bin_id": bin_id},
        }

    # Check image size
    from inventory_mcp.config import settings

    image_bytes = len(image_base64) * 3 // 4  # Approximate decoded size
    if image_bytes > settings.max_image_size_bytes:
        return {
            "error": f"Image too large. Maximum size is {settings.max_image_size_bytes // (1024*1024)}MB",
            "error_code": "IMAGE_TOO_LARGE",
        }

    # Save image
    image = BinImage(bin_id=bin_id, file_path="", caption=caption, is_primary=is_primary)

    try:
        metadata = image_store.save_bin_image(bin_id, image_base64, image.id)
    except Exception as e:
        return {
            "error": f"Failed to save image: {str(e)}",
            "error_code": "INTERNAL_ERROR",
        }

    image.file_path = metadata["file_path"]
    image.thumbnail_path = metadata["thumbnail_path"]
    image.width = metadata["width"]
    image.height = metadata["height"]
    image.file_size_bytes = metadata["file_size_bytes"]

    # If setting as primary, unset other primaries
    with db.connection() as conn:
        if is_primary:
            conn.execute(
                "UPDATE bin_images SET is_primary = 0 WHERE bin_id = ?",
                (bin_id,),
            )

        conn.execute(
            """
            INSERT INTO bin_images
            (id, bin_id, file_path, thumbnail_path, caption, is_primary, width, height, file_size_bytes, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                image.id,
                image.bin_id,
                image.file_path,
                image.thumbnail_path,
                image.caption,
                1 if image.is_primary else 0,
                image.width,
                image.height,
                image.file_size_bytes,
                image.created_at.isoformat(),
            ),
        )

    return image


def remove_bin_image(
    db: Database,
    image_store: ImageStore,
    image_id: str,
) -> dict:
    """Remove image from bin.

    Args:
        db: Database connection
        image_store: Image storage service
        image_id: Image UUID

    Returns:
        Success dict
    """
    row = db.execute_one("SELECT * FROM bin_images WHERE id = ?", (image_id,))
    if not row:
        return {
            "error": "Image not found",
            "error_code": "NOT_FOUND",
            "details": {"image_id": image_id},
        }

    # Delete file
    image_store.delete_image(row["file_path"])

    # Delete record
    with db.connection() as conn:
        conn.execute("DELETE FROM bin_images WHERE id = ?", (image_id,))

    return {"success": True}


def set_primary_bin_image(
    db: Database,
    bin_id: str,
    image_id: str,
) -> BinImage | dict:
    """Set which image is the primary display image.

    Args:
        db: Database connection
        bin_id: Bin UUID
        image_id: Image UUID to set as primary

    Returns:
        Updated BinImage or error dict
    """
    row = db.execute_one(
        "SELECT * FROM bin_images WHERE id = ? AND bin_id = ?",
        (image_id, bin_id),
    )
    if not row:
        return {
            "error": "Image not found in this bin",
            "error_code": "NOT_FOUND",
            "details": {"image_id": image_id, "bin_id": bin_id},
        }

    with db.connection() as conn:
        # Unset all primaries for this bin
        conn.execute(
            "UPDATE bin_images SET is_primary = 0 WHERE bin_id = ?",
            (bin_id,),
        )
        # Set this one as primary
        conn.execute(
            "UPDATE bin_images SET is_primary = 1 WHERE id = ?",
            (image_id,),
        )

    return BinImage(
        id=row["id"],
        bin_id=row["bin_id"],
        file_path=row["file_path"],
        thumbnail_path=row["thumbnail_path"],
        caption=row["caption"],
        is_primary=True,
        source_session_id=row["source_session_id"],
        source_session_image_id=row["source_session_image_id"],
        width=row["width"],
        height=row["height"],
        file_size_bytes=row["file_size_bytes"],
        created_at=row["created_at"],
    )
