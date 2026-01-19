"""Item alias management tools for protea."""

from protea.db.connection import Database
from protea.db.models import ItemAlias


def get_aliases(db: Database, item_id: str) -> list[ItemAlias] | dict:
    """Get all aliases for an item.

    Args:
        db: Database connection
        item_id: Item UUID

    Returns:
        List of ItemAlias or error dict
    """
    # Verify item exists
    item = db.execute_one("SELECT id FROM items WHERE id = ?", (item_id,))
    if not item:
        return {
            "error": "Item not found",
            "error_code": "NOT_FOUND",
            "details": {"item_id": item_id},
        }

    rows = db.execute(
        "SELECT * FROM item_aliases WHERE item_id = ? ORDER BY alias",
        (item_id,),
    )

    return [
        ItemAlias(
            id=row["id"],
            item_id=row["item_id"],
            alias=row["alias"],
        )
        for row in rows
    ]


def add_alias(
    db: Database,
    item_id: str,
    alias: str,
) -> ItemAlias | dict:
    """Add an alias for an item.

    Args:
        db: Database connection
        item_id: Item UUID
        alias: Alternative name (e.g., 'Allen key' for 'Hex wrench')

    Returns:
        Created ItemAlias or error dict
    """
    # Verify item exists
    item = db.execute_one("SELECT id FROM items WHERE id = ?", (item_id,))
    if not item:
        return {
            "error": "Item not found",
            "error_code": "NOT_FOUND",
            "details": {"item_id": item_id},
        }

    # Check for duplicate alias on this item
    existing = db.execute_one(
        "SELECT id FROM item_aliases WHERE item_id = ? AND alias = ?",
        (item_id, alias),
    )
    if existing:
        return {
            "error": f"Alias '{alias}' already exists for this item",
            "error_code": "ALREADY_EXISTS",
        }

    item_alias = ItemAlias(item_id=item_id, alias=alias)

    with db.connection() as conn:
        conn.execute(
            "INSERT INTO item_aliases (id, item_id, alias) VALUES (?, ?, ?)",
            (item_alias.id, item_alias.item_id, item_alias.alias),
        )

    return item_alias


def remove_alias(db: Database, alias_id: str) -> dict:
    """Remove an alias from an item.

    Args:
        db: Database connection
        alias_id: Alias UUID

    Returns:
        Success dict
    """
    row = db.execute_one("SELECT * FROM item_aliases WHERE id = ?", (alias_id,))
    if not row:
        return {
            "error": "Alias not found",
            "error_code": "NOT_FOUND",
            "details": {"alias_id": alias_id},
        }

    with db.connection() as conn:
        conn.execute("DELETE FROM item_aliases WHERE id = ?", (alias_id,))

    return {"success": True}
