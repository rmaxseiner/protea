"""Category management tools for inventory-mcp."""

from inventory_mcp.db.connection import Database
from inventory_mcp.db.models import Category


def get_categories(
    db: Database,
    as_tree: bool = False,
) -> list[Category] | dict:
    """List all categories, optionally as tree structure.

    Args:
        db: Database connection
        as_tree: If True, return nested tree structure

    Returns:
        List of categories or tree dict
    """
    rows = db.execute("SELECT * FROM categories ORDER BY name")

    categories = [
        Category(
            id=row["id"],
            name=row["name"],
            parent_id=row["parent_id"],
            created_at=row["created_at"],
        )
        for row in rows
    ]

    if not as_tree:
        return categories

    # Build tree structure
    by_id = {c.id: {"category": c, "children": []} for c in categories}
    roots = []

    for cat in categories:
        node = by_id[cat.id]
        if cat.parent_id and cat.parent_id in by_id:
            by_id[cat.parent_id]["children"].append(node)
        else:
            roots.append(node)

    def build_tree(node: dict) -> dict:
        return {
            "id": node["category"].id,
            "name": node["category"].name,
            "children": [build_tree(child) for child in node["children"]],
        }

    return {"categories": [build_tree(root) for root in roots]}


def get_category(db: Database, category_id: str) -> Category | dict:
    """Get a category by ID.

    Args:
        db: Database connection
        category_id: Category UUID

    Returns:
        Category or error dict
    """
    row = db.execute_one("SELECT * FROM categories WHERE id = ?", (category_id,))
    if not row:
        return {
            "error": "Category not found",
            "error_code": "NOT_FOUND",
            "details": {"category_id": category_id},
        }

    return Category(
        id=row["id"],
        name=row["name"],
        parent_id=row["parent_id"],
        created_at=row["created_at"],
    )


def create_category(
    db: Database,
    name: str,
    parent_id: str | None = None,
) -> Category | dict:
    """Create a category.

    Args:
        db: Database connection
        name: Category name
        parent_id: Optional parent category UUID

    Returns:
        Created Category or error dict
    """
    # Verify parent exists if provided
    if parent_id:
        parent = db.execute_one("SELECT id FROM categories WHERE id = ?", (parent_id,))
        if not parent:
            return {
                "error": "Parent category not found",
                "error_code": "NOT_FOUND",
                "details": {"parent_id": parent_id},
            }

    # Check for duplicate name under same parent
    existing = db.execute_one(
        "SELECT id FROM categories WHERE name = ? AND (parent_id = ? OR (parent_id IS NULL AND ? IS NULL))",
        (name, parent_id, parent_id),
    )
    if existing:
        return {
            "error": f"Category '{name}' already exists at this level",
            "error_code": "ALREADY_EXISTS",
        }

    category = Category(name=name, parent_id=parent_id)

    with db.connection() as conn:
        conn.execute(
            """
            INSERT INTO categories (id, name, parent_id, created_at)
            VALUES (?, ?, ?, ?)
            """,
            (
                category.id,
                category.name,
                category.parent_id,
                category.created_at.isoformat(),
            ),
        )

    return category


def update_category(
    db: Database,
    category_id: str,
    name: str | None = None,
    parent_id: str | None = None,
) -> Category | dict:
    """Update a category's name or parent.

    Args:
        db: Database connection
        category_id: Category UUID
        name: New name
        parent_id: New parent (use empty string to move to root)

    Returns:
        Updated Category or error dict
    """
    row = db.execute_one("SELECT * FROM categories WHERE id = ?", (category_id,))
    if not row:
        return {
            "error": "Category not found",
            "error_code": "NOT_FOUND",
            "details": {"category_id": category_id},
        }

    new_name = name if name is not None else row["name"]

    # Handle parent_id update
    if parent_id == "":
        # Move to root
        new_parent_id = None
    elif parent_id is not None:
        # Verify new parent exists
        parent = db.execute_one("SELECT id FROM categories WHERE id = ?", (parent_id,))
        if not parent:
            return {
                "error": "Parent category not found",
                "error_code": "NOT_FOUND",
                "details": {"parent_id": parent_id},
            }
        # Prevent circular reference
        if parent_id == category_id:
            return {
                "error": "Cannot set category as its own parent",
                "error_code": "INVALID_INPUT",
            }
        new_parent_id = parent_id
    else:
        new_parent_id = row["parent_id"]

    # Check for duplicate name under new parent
    existing = db.execute_one(
        """
        SELECT id FROM categories
        WHERE name = ? AND id != ?
        AND (parent_id = ? OR (parent_id IS NULL AND ? IS NULL))
        """,
        (new_name, category_id, new_parent_id, new_parent_id),
    )
    if existing:
        return {
            "error": f"Category '{new_name}' already exists at this level",
            "error_code": "ALREADY_EXISTS",
        }

    with db.connection() as conn:
        conn.execute(
            "UPDATE categories SET name = ?, parent_id = ? WHERE id = ?",
            (new_name, new_parent_id, category_id),
        )

    return Category(
        id=category_id,
        name=new_name,
        parent_id=new_parent_id,
        created_at=row["created_at"],
    )


def _get_child_category_ids(db: Database, category_id: str) -> list[str]:
    """Recursively get all child category IDs."""
    children = db.execute(
        "SELECT id FROM categories WHERE parent_id = ?",
        (category_id,),
    )
    child_ids = [row["id"] for row in children]

    all_ids = list(child_ids)
    for child_id in child_ids:
        all_ids.extend(_get_child_category_ids(db, child_id))

    return all_ids


def delete_category(db: Database, category_id: str) -> dict:
    """Delete a category.

    Cannot delete if category has items. Empty child categories are cascade-deleted.

    Args:
        db: Database connection
        category_id: Category UUID

    Returns:
        Result dict with deleted_children list
    """
    row = db.execute_one("SELECT * FROM categories WHERE id = ?", (category_id,))
    if not row:
        return {
            "error": "Category not found",
            "error_code": "NOT_FOUND",
            "details": {"category_id": category_id},
        }

    # Check if this category has items
    item_count = db.execute_one(
        "SELECT COUNT(*) as cnt FROM items WHERE category_id = ?",
        (category_id,),
    )
    if item_count and item_count["cnt"] > 0:
        return {
            "success": False,
            "error": f"Cannot delete category with {item_count['cnt']} items. Reassign items first.",
            "error_code": "HAS_DEPENDENCIES",
            "details": {"item_count": item_count["cnt"]},
        }

    # Get all child categories
    child_ids = _get_child_category_ids(db, category_id)

    # Check if any children have items
    for child_id in child_ids:
        child_items = db.execute_one(
            "SELECT COUNT(*) as cnt FROM items WHERE category_id = ?",
            (child_id,),
        )
        if child_items and child_items["cnt"] > 0:
            return {
                "success": False,
                "error": "Cannot delete category - a child category has items",
                "error_code": "HAS_DEPENDENCIES",
                "details": {"child_category_id": child_id, "item_count": child_items["cnt"]},
            }

    # Delete children first (empty ones only, already verified)
    deleted_children = []
    with db.connection() as conn:
        for child_id in reversed(child_ids):  # Delete deepest first
            conn.execute("DELETE FROM categories WHERE id = ?", (child_id,))
            deleted_children.append(child_id)

        conn.execute("DELETE FROM categories WHERE id = ?", (category_id,))

    return {
        "success": True,
        "message": f"Category '{row['name']}' deleted",
        "deleted_children": deleted_children,
    }
