"""Bin management tools for inventory-mcp."""

from datetime import datetime

from inventory_mcp.db.connection import Database
from inventory_mcp.db.models import (
    Bin,
    BinDetail,
    BinImage,
    BinWithLocation,
    Item,
    Location,
)
from inventory_mcp.services.image_store import ImageStore


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


def get_bins(
    db: Database,
    location_id: str | None = None,
) -> list[BinWithLocation]:
    """List bins, optionally filtered by location.

    Args:
        db: Database connection
        location_id: Optional location filter

    Returns:
        List of bins with their locations
    """
    if location_id:
        rows = db.execute(
            """
            SELECT b.*, l.name as loc_name, l.description as loc_desc,
                   l.created_at as loc_created, l.updated_at as loc_updated
            FROM bins b
            JOIN locations l ON b.location_id = l.id
            WHERE b.location_id = ?
            ORDER BY b.name
            """,
            (location_id,),
        )
    else:
        rows = db.execute(
            """
            SELECT b.*, l.name as loc_name, l.description as loc_desc,
                   l.created_at as loc_created, l.updated_at as loc_updated
            FROM bins b
            JOIN locations l ON b.location_id = l.id
            ORDER BY l.name, b.name
            """
        )

    return [
        BinWithLocation(
            id=row["id"],
            name=row["name"],
            location_id=row["location_id"],
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

    return BinDetail(
        id=row["id"],
        name=row["name"],
        location_id=row["location_id"],
        description=row["description"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
        location=location,
        items=items,
        images=images,
        item_count=item_count["cnt"] if item_count else 0,
        image_count=image_count["cnt"] if image_count else 0,
    )


def create_bin(
    db: Database,
    name: str,
    location_id: str,
    description: str | None = None,
) -> Bin | dict:
    """Create a new bin.

    Args:
        db: Database connection
        name: Bin name
        location_id: Parent location UUID
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

    # Check for duplicate name in same location
    existing = db.execute_one(
        "SELECT id FROM bins WHERE name = ? AND location_id = ?",
        (name, location_id),
    )
    if existing:
        return {
            "error": f"Bin with name '{name}' already exists in this location",
            "error_code": "ALREADY_EXISTS",
        }

    bin_obj = Bin(name=name, location_id=location_id, description=description)

    with db.connection() as conn:
        conn.execute(
            """
            INSERT INTO bins (id, name, location_id, description, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                bin_obj.id,
                bin_obj.name,
                bin_obj.location_id,
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
    description: str | None = None,
) -> Bin | dict:
    """Update a bin.

    Args:
        db: Database connection
        bin_id: Bin UUID
        name: New name (optional)
        location_id: New location (optional)
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

    # Verify new location if changed
    if location_id and location_id != row["location_id"]:
        location = _get_location(db, location_id)
        if not location:
            return {
                "error": "New location not found",
                "error_code": "NOT_FOUND",
                "details": {"location_id": location_id},
            }

    # Check for name conflict in target location
    if name or location_id:
        existing = db.execute_one(
            "SELECT id FROM bins WHERE name = ? AND location_id = ? AND id != ?",
            (new_name, new_location_id, bin_id),
        )
        if existing:
            return {
                "error": f"Bin with name '{new_name}' already exists in target location",
                "error_code": "ALREADY_EXISTS",
            }

    updated_at = datetime.utcnow()

    with db.connection() as conn:
        conn.execute(
            """
            UPDATE bins
            SET name = ?, location_id = ?, description = ?, updated_at = ?
            WHERE id = ?
            """,
            (new_name, new_location_id, new_description, updated_at.isoformat(), bin_id),
        )

    return Bin(
        id=bin_id,
        name=new_name,
        location_id=new_location_id,
        description=new_description,
        created_at=row["created_at"],
        updated_at=updated_at,
    )


def delete_bin(db: Database, bin_id: str) -> dict:
    """Delete a bin.

    Fails if the bin has items.

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
