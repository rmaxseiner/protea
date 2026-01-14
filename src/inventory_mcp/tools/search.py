"""Search and query tools for inventory-mcp."""

from inventory_mcp.db.connection import Database
from inventory_mcp.db.models import (
    ActivityAction,
    ActivityLog,
    Bin,
    Item,
    ItemWithLocation,
    Location,
    SearchResult,
)
from inventory_mcp.tools.bins import _build_bin_path


def search_items(
    db: Database,
    query: str,
    location_id: str | None = None,
    bin_id: str | None = None,
    category_id: str | None = None,
) -> list[SearchResult]:
    """Search inventory by name, description, or alias.

    Uses FTS5 prefix matching for efficient search.

    Args:
        db: Database connection
        query: Search query
        location_id: Filter by location
        bin_id: Filter by bin
        category_id: Filter by category

    Returns:
        List of SearchResult with match scores
    """
    # Prepare query for FTS (add prefix matching)
    fts_query = " ".join(f"{term}*" for term in query.split())

    # Build SQL with filters
    params = []
    filter_clauses = []

    if location_id:
        filter_clauses.append("l.id = ?")
        params.append(location_id)
    if bin_id:
        filter_clauses.append("i.bin_id = ?")
        params.append(bin_id)
    if category_id:
        filter_clauses.append("i.category_id = ?")
        params.append(category_id)

    filter_sql = ""
    if filter_clauses:
        filter_sql = "AND " + " AND ".join(filter_clauses)

    # Search items via FTS
    sql = f"""
        SELECT i.*, b.name as bin_name, b.description as bin_desc,
               b.parent_bin_id as bin_parent_id,
               b.created_at as bin_created, b.updated_at as bin_updated,
               l.id as loc_id, l.name as loc_name, l.description as loc_desc,
               l.created_at as loc_created, l.updated_at as loc_updated,
               fts.rank as score
        FROM items i
        JOIN bins b ON i.bin_id = b.id
        JOIN locations l ON b.location_id = l.id
        JOIN items_fts fts ON i.rowid = fts.rowid
        WHERE items_fts MATCH ?
        {filter_sql}
        ORDER BY fts.rank
        LIMIT 50
    """

    rows = db.execute(sql, (fts_query, *params))

    results = []
    for row in rows:
        # Build bin path for nested bins
        bin_path = _build_bin_path(db, row["bin_id"], include_location=True)
        results.append(
            SearchResult(
                item=Item(
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
                ),
                bin=Bin(
                    id=row["bin_id"],
                    name=row["bin_name"],
                    location_id=row["loc_id"],
                    parent_bin_id=row["bin_parent_id"],
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
                match_score=abs(row["score"]) if row["score"] else 1.0,
                bin_path=bin_path,
            )
        )

    # Also search aliases
    alias_sql = f"""
        SELECT i.*, b.name as bin_name, b.description as bin_desc,
               b.parent_bin_id as bin_parent_id,
               b.created_at as bin_created, b.updated_at as bin_updated,
               l.id as loc_id, l.name as loc_name, l.description as loc_desc,
               l.created_at as loc_created, l.updated_at as loc_updated,
               fts.rank as score
        FROM items i
        JOIN bins b ON i.bin_id = b.id
        JOIN locations l ON b.location_id = l.id
        JOIN item_aliases a ON i.id = a.item_id
        JOIN aliases_fts fts ON a.rowid = fts.rowid
        WHERE aliases_fts MATCH ?
        {filter_sql}
        ORDER BY fts.rank
        LIMIT 50
    """

    alias_rows = db.execute(alias_sql, (fts_query, *params))

    # Add alias matches (avoid duplicates)
    seen_ids = {r.item.id for r in results}
    for row in alias_rows:
        if row["id"] not in seen_ids:
            # Build bin path for nested bins
            bin_path = _build_bin_path(db, row["bin_id"], include_location=True)
            results.append(
                SearchResult(
                    item=Item(
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
                    ),
                    bin=Bin(
                        id=row["bin_id"],
                        name=row["bin_name"],
                        location_id=row["loc_id"],
                        parent_bin_id=row["bin_parent_id"],
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
                    match_score=abs(row["score"]) * 0.9 if row["score"] else 0.9,  # Slightly lower for alias match
                    bin_path=bin_path,
                )
            )
            seen_ids.add(row["id"])

    # Sort by score
    results.sort(key=lambda r: r.match_score, reverse=True)

    return results


def find_item(db: Database, query: str) -> list[SearchResult]:
    """Find where a specific item is located.

    Convenience wrapper around search_items for simple queries.

    Args:
        db: Database connection
        query: Item name to find

    Returns:
        List of matching items with locations
    """
    return search_items(db, query)


def list_items(
    db: Database,
    bin_id: str | None = None,
    location_id: str | None = None,
    category_id: str | None = None,
    include_children: bool = True,
) -> list[ItemWithLocation]:
    """List items with filters.

    Args:
        db: Database connection
        bin_id: Filter by bin
        location_id: Filter by location
        category_id: Filter by category
        include_children: Include items in subcategories

    Returns:
        List of items with their locations
    """
    params = []
    filter_clauses = []

    if bin_id:
        filter_clauses.append("i.bin_id = ?")
        params.append(bin_id)

    if location_id:
        filter_clauses.append("b.location_id = ?")
        params.append(location_id)

    if category_id:
        if include_children:
            # Get all child category IDs
            def get_child_ids(cat_id: str) -> list[str]:
                children = db.execute(
                    "SELECT id FROM categories WHERE parent_id = ?",
                    (cat_id,),
                )
                child_ids = [row["id"] for row in children]
                all_ids = list(child_ids)
                for child_id in child_ids:
                    all_ids.extend(get_child_ids(child_id))
                return all_ids

            all_category_ids = [category_id] + get_child_ids(category_id)
            placeholders = ",".join("?" * len(all_category_ids))
            filter_clauses.append(f"i.category_id IN ({placeholders})")
            params.extend(all_category_ids)
        else:
            filter_clauses.append("i.category_id = ?")
            params.append(category_id)

    filter_sql = ""
    if filter_clauses:
        filter_sql = "WHERE " + " AND ".join(filter_clauses)

    sql = f"""
        SELECT i.*, b.name as bin_name, b.description as bin_desc,
               b.created_at as bin_created, b.updated_at as bin_updated,
               l.id as loc_id, l.name as loc_name, l.description as loc_desc,
               l.created_at as loc_created, l.updated_at as loc_updated
        FROM items i
        JOIN bins b ON i.bin_id = b.id
        JOIN locations l ON b.location_id = l.id
        {filter_sql}
        ORDER BY l.name, b.name, i.name
    """

    rows = db.execute(sql, tuple(params))

    return [
        ItemWithLocation(
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
        for row in rows
    ]


def get_item_history(db: Database, item_id: str) -> list[ActivityLog] | dict:
    """Get activity history for an item.

    Args:
        db: Database connection
        item_id: Item UUID

    Returns:
        List of ActivityLog entries or error dict
    """
    # Verify item exists (or existed - check activity log too)
    item = db.execute_one("SELECT id FROM items WHERE id = ?", (item_id,))
    has_history = db.execute_one(
        "SELECT id FROM activity_log WHERE item_id = ? LIMIT 1",
        (item_id,),
    )

    if not item and not has_history:
        return {
            "error": "Item not found and has no history",
            "error_code": "NOT_FOUND",
            "details": {"item_id": item_id},
        }

    rows = db.execute(
        "SELECT * FROM activity_log WHERE item_id = ? ORDER BY created_at DESC",
        (item_id,),
    )

    return [
        ActivityLog(
            id=row["id"],
            item_id=row["item_id"],
            action=ActivityAction(row["action"]),
            quantity_change=row["quantity_change"],
            from_bin_id=row["from_bin_id"],
            to_bin_id=row["to_bin_id"],
            notes=row["notes"],
            created_at=row["created_at"],
        )
        for row in rows
    ]
