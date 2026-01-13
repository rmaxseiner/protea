"""Item management tools for inventory-mcp."""

import json
from datetime import datetime

from inventory_mcp.db.connection import Database
from inventory_mcp.db.models import (
    ActivityAction,
    ActivityLog,
    Bin,
    Item,
    ItemSource,
    ItemWithLocation,
    Location,
    QuantityType,
)


def _get_item_with_location(db: Database, item_id: str) -> ItemWithLocation | None:
    """Helper to get item with bin and location."""
    row = db.execute_one(
        """
        SELECT i.*, b.name as bin_name, b.description as bin_desc,
               b.created_at as bin_created, b.updated_at as bin_updated,
               l.id as loc_id, l.name as loc_name, l.description as loc_desc,
               l.created_at as loc_created, l.updated_at as loc_updated
        FROM items i
        JOIN bins b ON i.bin_id = b.id
        JOIN locations l ON b.location_id = l.id
        WHERE i.id = ?
        """,
        (item_id,),
    )
    if not row:
        return None

    return ItemWithLocation(
        id=row["id"],
        name=row["name"],
        description=row["description"],
        category_id=row["category_id"],
        bin_id=row["bin_id"],
        quantity_type=row["quantity_type"],
        quantity_value=row["quantity_value"],
        quantity_label=row["quantity_label"],
        source=row["source"],
        source_reference=row["source_reference"],
        photo_url=row["photo_url"],
        notes=row["notes"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
        bin=Bin(
            id=row["bin_id"],
            name=row["bin_name"],
            location_id=row["loc_id"],
            description=row["bin_desc"],
            created_at=row["bin_created"],
            updated_at=row["bin_updated"],
        ),
        location=Location(
            id=row["loc_id"],
            name=row["loc_name"],
            description=row["loc_desc"],
            created_at=row["loc_created"],
            updated_at=row["loc_updated"],
        ),
    )


def _log_activity(
    db: Database,
    item_id: str,
    action: ActivityAction,
    quantity_change: int | None = None,
    from_bin_id: str | None = None,
    to_bin_id: str | None = None,
    notes: str | None = None,
) -> None:
    """Log an activity for an item."""
    log = ActivityLog(
        item_id=item_id,
        action=action,
        quantity_change=quantity_change,
        from_bin_id=from_bin_id,
        to_bin_id=to_bin_id,
        notes=notes,
    )
    with db.connection() as conn:
        conn.execute(
            """
            INSERT INTO activity_log (id, item_id, action, quantity_change, from_bin_id, to_bin_id, notes, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                log.id,
                log.item_id,
                log.action.value,
                log.quantity_change,
                log.from_bin_id,
                log.to_bin_id,
                log.notes,
                log.created_at.isoformat(),
            ),
        )


def get_item(db: Database, item_id: str) -> ItemWithLocation | dict:
    """Get a single item by ID with its bin and location.

    Args:
        db: Database connection
        item_id: Item UUID

    Returns:
        ItemWithLocation or error dict
    """
    item = _get_item_with_location(db, item_id)
    if not item:
        return {
            "error": "Item not found",
            "error_code": "NOT_FOUND",
            "details": {"item_id": item_id},
        }
    return item


def add_item(
    db: Database,
    name: str,
    bin_id: str,
    category_id: str | None = None,
    quantity_type: str = "boolean",
    quantity_value: int | None = None,
    quantity_label: str | None = None,
    description: str | None = None,
    source: str = "manual",
    source_reference: str | None = None,
    notes: str | None = None,
) -> Item | dict:
    """Add an item to inventory.

    Args:
        db: Database connection
        name: Item name
        bin_id: Target bin UUID
        category_id: Optional category UUID
        quantity_type: "exact", "approximate", or "boolean"
        quantity_value: Numeric quantity (1 for boolean)
        quantity_label: Label like "assorted", "roll", etc.
        description: Optional description
        source: "manual", "vision", or "barcode_lookup"
        source_reference: Reference to source (image ID, barcode, etc.)
        notes: Free-form notes

    Returns:
        Created Item or error dict
    """
    # Verify bin exists
    bin_row = db.execute_one("SELECT id FROM bins WHERE id = ?", (bin_id,))
    if not bin_row:
        return {
            "error": "Bin not found",
            "error_code": "NOT_FOUND",
            "details": {"bin_id": bin_id},
        }

    # Verify category if provided
    if category_id:
        cat_row = db.execute_one("SELECT id FROM categories WHERE id = ?", (category_id,))
        if not cat_row:
            return {
                "error": "Category not found",
                "error_code": "NOT_FOUND",
                "details": {"category_id": category_id},
            }

    # Validate quantity_type
    try:
        qt = QuantityType(quantity_type)
    except ValueError:
        return {
            "error": f"Invalid quantity_type: {quantity_type}",
            "error_code": "INVALID_INPUT",
            "details": {"valid_values": ["exact", "approximate", "boolean"]},
        }

    # For boolean, set quantity_value to 1
    if qt == QuantityType.BOOLEAN:
        quantity_value = 1

    # Validate source
    try:
        src = ItemSource(source)
    except ValueError:
        return {
            "error": f"Invalid source: {source}",
            "error_code": "INVALID_INPUT",
            "details": {"valid_values": ["manual", "vision", "barcode_lookup"]},
        }

    item = Item(
        name=name,
        bin_id=bin_id,
        category_id=category_id,
        quantity_type=qt,
        quantity_value=quantity_value,
        quantity_label=quantity_label,
        description=description,
        source=src,
        source_reference=source_reference,
        notes=notes,
    )

    with db.connection() as conn:
        conn.execute(
            """
            INSERT INTO items
            (id, name, description, category_id, bin_id, quantity_type, quantity_value,
             quantity_label, source, source_reference, photo_url, notes, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                item.id,
                item.name,
                item.description,
                item.category_id,
                item.bin_id,
                item.quantity_type.value,
                item.quantity_value,
                item.quantity_label,
                item.source.value,
                item.source_reference,
                item.photo_url,
                item.notes,
                item.created_at.isoformat(),
                item.updated_at.isoformat(),
            ),
        )

    # Log activity
    _log_activity(db, item.id, ActivityAction.ADDED, quantity_change=quantity_value)

    return item


def add_items_bulk(
    db: Database,
    items: list[dict],
    bin_id: str,
    source: str = "vision",
    source_reference: str | None = None,
) -> list[Item] | dict:
    """Add multiple items at once.

    Args:
        db: Database connection
        items: List of item dicts with name, category_id?, quantity_type?, etc.
        bin_id: Target bin UUID
        source: Source for all items
        source_reference: Reference for all items

    Returns:
        List of created Items or error dict
    """
    # Verify bin exists
    bin_row = db.execute_one("SELECT id FROM bins WHERE id = ?", (bin_id,))
    if not bin_row:
        return {
            "error": "Bin not found",
            "error_code": "NOT_FOUND",
            "details": {"bin_id": bin_id},
        }

    created_items = []
    for item_data in items:
        result = add_item(
            db=db,
            name=item_data.get("name", "Unknown"),
            bin_id=bin_id,
            category_id=item_data.get("category_id"),
            quantity_type=item_data.get("quantity_type", "boolean"),
            quantity_value=item_data.get("quantity_value"),
            quantity_label=item_data.get("quantity_label"),
            description=item_data.get("description"),
            source=source,
            source_reference=source_reference,
            notes=item_data.get("notes"),
        )
        if isinstance(result, dict) and "error" in result:
            # Continue on individual item errors but could also return here
            continue
        created_items.append(result)

    return created_items


def update_item(
    db: Database,
    item_id: str,
    name: str | None = None,
    category_id: str | None = None,
    quantity_type: str | None = None,
    quantity_value: int | None = None,
    quantity_label: str | None = None,
    description: str | None = None,
    notes: str | None = None,
) -> Item | dict:
    """Update an item.

    Args:
        db: Database connection
        item_id: Item UUID
        name: New name
        category_id: New category
        quantity_type: New quantity type
        quantity_value: New quantity value
        quantity_label: New quantity label
        description: New description
        notes: New notes

    Returns:
        Updated Item or error dict
    """
    row = db.execute_one("SELECT * FROM items WHERE id = ?", (item_id,))
    if not row:
        return {
            "error": "Item not found",
            "error_code": "NOT_FOUND",
            "details": {"item_id": item_id},
        }

    # Verify new category if provided
    if category_id:
        cat_row = db.execute_one("SELECT id FROM categories WHERE id = ?", (category_id,))
        if not cat_row:
            return {
                "error": "Category not found",
                "error_code": "NOT_FOUND",
                "details": {"category_id": category_id},
            }

    # Build updates
    new_name = name if name is not None else row["name"]
    new_category_id = category_id if category_id is not None else row["category_id"]
    new_quantity_type = quantity_type if quantity_type is not None else row["quantity_type"]
    new_quantity_value = quantity_value if quantity_value is not None else row["quantity_value"]
    new_quantity_label = quantity_label if quantity_label is not None else row["quantity_label"]
    new_description = description if description is not None else row["description"]
    new_notes = notes if notes is not None else row["notes"]
    updated_at = datetime.utcnow()

    with db.connection() as conn:
        conn.execute(
            """
            UPDATE items
            SET name = ?, category_id = ?, quantity_type = ?, quantity_value = ?,
                quantity_label = ?, description = ?, notes = ?, updated_at = ?
            WHERE id = ?
            """,
            (
                new_name,
                new_category_id,
                new_quantity_type,
                new_quantity_value,
                new_quantity_label,
                new_description,
                new_notes,
                updated_at.isoformat(),
                item_id,
            ),
        )

    # Log activity
    _log_activity(db, item_id, ActivityAction.UPDATED)

    return Item(
        id=item_id,
        name=new_name,
        description=new_description,
        category_id=new_category_id,
        bin_id=row["bin_id"],
        quantity_type=new_quantity_type,
        quantity_value=new_quantity_value,
        quantity_label=new_quantity_label,
        source=row["source"],
        source_reference=row["source_reference"],
        photo_url=row["photo_url"],
        notes=new_notes,
        created_at=row["created_at"],
        updated_at=updated_at,
    )


def remove_item(
    db: Database,
    item_id: str,
    reason: str | None = None,
) -> dict:
    """Remove an item from inventory entirely.

    Args:
        db: Database connection
        item_id: Item UUID
        reason: "used", "discarded", "lost"

    Returns:
        Success/error dict
    """
    row = db.execute_one("SELECT * FROM items WHERE id = ?", (item_id,))
    if not row:
        return {
            "error": "Item not found",
            "error_code": "NOT_FOUND",
            "details": {"item_id": item_id},
        }

    # Log activity before deletion
    _log_activity(
        db,
        item_id,
        ActivityAction.REMOVED,
        quantity_change=-(row["quantity_value"] or 0),
        notes=reason,
    )

    with db.connection() as conn:
        # Delete aliases first
        conn.execute("DELETE FROM item_aliases WHERE item_id = ?", (item_id,))
        # Activity log has ON DELETE CASCADE
        conn.execute("DELETE FROM items WHERE id = ?", (item_id,))

    return {
        "success": True,
        "message": f"Item '{row['name']}' removed",
    }


def delete_items_bulk(
    db: Database,
    item_ids: list[str],
    reason: str | None = None,
) -> dict:
    """Delete multiple items at once.

    Args:
        db: Database connection
        item_ids: List of item UUIDs
        reason: Reason for deletion

    Returns:
        Result dict with counts
    """
    deleted = 0
    failed = []

    for item_id in item_ids:
        result = remove_item(db, item_id, reason)
        if result.get("success"):
            deleted += 1
        else:
            failed.append({"id": item_id, "error": result.get("error", "Unknown error")})

    return {
        "success": len(failed) == 0,
        "deleted_count": deleted,
        "failed": failed,
    }


def use_item(
    db: Database,
    item_id: str,
    quantity: int = 1,
    notes: str | None = None,
) -> Item | dict:
    """Decrement item quantity or mark as used.

    Args:
        db: Database connection
        item_id: Item UUID
        quantity: Amount to use (default 1)
        notes: Optional usage notes

    Returns:
        Updated Item or error dict
    """
    row = db.execute_one("SELECT * FROM items WHERE id = ?", (item_id,))
    if not row:
        return {
            "error": "Item not found",
            "error_code": "NOT_FOUND",
            "details": {"item_id": item_id},
        }

    current_qty = row["quantity_value"] or 0
    new_qty = max(0, current_qty - quantity)
    updated_at = datetime.utcnow()

    with db.connection() as conn:
        conn.execute(
            "UPDATE items SET quantity_value = ?, updated_at = ? WHERE id = ?",
            (new_qty, updated_at.isoformat(), item_id),
        )

    # Log activity
    _log_activity(
        db,
        item_id,
        ActivityAction.USED,
        quantity_change=-quantity,
        notes=notes,
    )

    return Item(
        id=item_id,
        name=row["name"],
        description=row["description"],
        category_id=row["category_id"],
        bin_id=row["bin_id"],
        quantity_type=row["quantity_type"],
        quantity_value=new_qty,
        quantity_label=row["quantity_label"],
        source=row["source"],
        source_reference=row["source_reference"],
        photo_url=row["photo_url"],
        notes=row["notes"],
        created_at=row["created_at"],
        updated_at=updated_at,
    )


def move_item(
    db: Database,
    item_id: str,
    to_bin_id: str,
    quantity: int | None = None,
    notes: str | None = None,
) -> dict:
    """Move item to a different bin.

    If quantity is provided and less than item's quantity, splits the item.

    Args:
        db: Database connection
        item_id: Item UUID
        to_bin_id: Target bin UUID
        quantity: Amount to move (None = move all)
        notes: Optional notes

    Returns:
        Dict with moved_item, source_item (if split), and split flag
    """
    row = db.execute_one("SELECT * FROM items WHERE id = ?", (item_id,))
    if not row:
        return {
            "error": "Item not found",
            "error_code": "NOT_FOUND",
            "details": {"item_id": item_id},
        }

    # Verify target bin exists
    bin_row = db.execute_one("SELECT id FROM bins WHERE id = ?", (to_bin_id,))
    if not bin_row:
        return {
            "error": "Target bin not found",
            "error_code": "NOT_FOUND",
            "details": {"to_bin_id": to_bin_id},
        }

    from_bin_id = row["bin_id"]
    current_qty = row["quantity_value"] or 1
    updated_at = datetime.utcnow()

    # Determine if splitting
    if quantity is not None and quantity < current_qty:
        # Split: reduce original, create new item in target
        remaining_qty = current_qty - quantity

        # Update original item
        with db.connection() as conn:
            conn.execute(
                "UPDATE items SET quantity_value = ?, updated_at = ? WHERE id = ?",
                (remaining_qty, updated_at.isoformat(), item_id),
            )

        # Create new item in target bin
        new_item = Item(
            name=row["name"],
            description=row["description"],
            category_id=row["category_id"],
            bin_id=to_bin_id,
            quantity_type=row["quantity_type"],
            quantity_value=quantity,
            quantity_label=row["quantity_label"],
            source=row["source"],
            source_reference=row["source_reference"],
            photo_url=row["photo_url"],
            notes=row["notes"],
        )

        with db.connection() as conn:
            conn.execute(
                """
                INSERT INTO items
                (id, name, description, category_id, bin_id, quantity_type, quantity_value,
                 quantity_label, source, source_reference, photo_url, notes, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    new_item.id,
                    new_item.name,
                    new_item.description,
                    new_item.category_id,
                    new_item.bin_id,
                    new_item.quantity_type.value if isinstance(new_item.quantity_type, QuantityType) else new_item.quantity_type,
                    new_item.quantity_value,
                    new_item.quantity_label,
                    new_item.source.value if isinstance(new_item.source, ItemSource) else new_item.source,
                    new_item.source_reference,
                    new_item.photo_url,
                    new_item.notes,
                    new_item.created_at.isoformat(),
                    new_item.updated_at.isoformat(),
                ),
            )

        # Log activity with split info
        split_notes = json.dumps({"split": True, "new_item_id": new_item.id})
        if notes:
            split_notes = f"{notes}; {split_notes}"
        _log_activity(
            db,
            item_id,
            ActivityAction.MOVED,
            quantity_change=-quantity,
            from_bin_id=from_bin_id,
            to_bin_id=to_bin_id,
            notes=split_notes,
        )

        source_item = Item(
            id=item_id,
            name=row["name"],
            description=row["description"],
            category_id=row["category_id"],
            bin_id=from_bin_id,
            quantity_type=row["quantity_type"],
            quantity_value=remaining_qty,
            quantity_label=row["quantity_label"],
            source=row["source"],
            source_reference=row["source_reference"],
            photo_url=row["photo_url"],
            notes=row["notes"],
            created_at=row["created_at"],
            updated_at=updated_at,
        )

        return {
            "moved_item": new_item,
            "source_item": source_item,
            "split": True,
        }

    else:
        # Move entire item
        with db.connection() as conn:
            conn.execute(
                "UPDATE items SET bin_id = ?, updated_at = ? WHERE id = ?",
                (to_bin_id, updated_at.isoformat(), item_id),
            )

        _log_activity(
            db,
            item_id,
            ActivityAction.MOVED,
            from_bin_id=from_bin_id,
            to_bin_id=to_bin_id,
            notes=notes,
        )

        moved_item = Item(
            id=item_id,
            name=row["name"],
            description=row["description"],
            category_id=row["category_id"],
            bin_id=to_bin_id,
            quantity_type=row["quantity_type"],
            quantity_value=row["quantity_value"],
            quantity_label=row["quantity_label"],
            source=row["source"],
            source_reference=row["source_reference"],
            photo_url=row["photo_url"],
            notes=row["notes"],
            created_at=row["created_at"],
            updated_at=updated_at,
        )

        return {
            "moved_item": moved_item,
            "source_item": None,
            "split": False,
        }
