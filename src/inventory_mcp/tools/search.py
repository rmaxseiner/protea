"""Search and query tools for inventory-mcp."""

from inventory_mcp.config import settings
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
from inventory_mcp.services import embedding_service
from inventory_mcp.tools.bins import _build_bin_path


def _row_to_search_result(db: Database, row, score: float) -> SearchResult:
    """Convert a database row to a SearchResult."""
    bin_path = _build_bin_path(db, row["bin_id"], include_location=True)
    return SearchResult(
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
        match_score=score,
        bin_path=bin_path,
    )


def _fts_search(
    db: Database,
    query: str,
    filter_sql: str,
    params: list,
) -> dict[str, tuple]:
    """Run FTS search and return dict of item_id -> (row, fts_score)."""
    fts_query = " ".join(f"{term}*" for term in query.split())

    sql = f"""
        SELECT i.*, b.name as bin_name, b.description as bin_desc,
               b.parent_bin_id as bin_parent_id,
               b.created_at as bin_created, b.updated_at as bin_updated,
               l.id as loc_id, l.name as loc_name, l.description as loc_desc,
               l.created_at as loc_created, l.updated_at as loc_updated,
               fts.rank as fts_score
        FROM items i
        JOIN bins b ON i.bin_id = b.id
        JOIN locations l ON b.location_id = l.id
        JOIN items_fts fts ON i.rowid = fts.rowid
        WHERE items_fts MATCH ?
        {filter_sql}
        LIMIT 100
    """
    rows = db.execute(sql, (fts_query, *params))
    return {row["id"]: (row, abs(row["fts_score"]) if row["fts_score"] else 1.0) for row in rows}


def _alias_search(
    db: Database,
    query: str,
    filter_sql: str,
    params: list,
    exclude_ids: set[str],
) -> dict[str, tuple]:
    """Run alias FTS search and return dict of item_id -> (row, fts_score)."""
    fts_query = " ".join(f"{term}*" for term in query.split())

    alias_sql = f"""
        SELECT i.*, b.name as bin_name, b.description as bin_desc,
               b.parent_bin_id as bin_parent_id,
               b.created_at as bin_created, b.updated_at as bin_updated,
               l.id as loc_id, l.name as loc_name, l.description as loc_desc,
               l.created_at as loc_created, l.updated_at as loc_updated,
               fts.rank as fts_score
        FROM items i
        JOIN bins b ON i.bin_id = b.id
        JOIN locations l ON b.location_id = l.id
        JOIN item_aliases a ON i.id = a.item_id
        JOIN aliases_fts fts ON a.rowid = fts.rowid
        WHERE aliases_fts MATCH ?
        {filter_sql}
        LIMIT 100
    """
    rows = db.execute(alias_sql, (fts_query, *params))
    results = {}
    for row in rows:
        if row["id"] not in exclude_ids:
            # Slightly lower score for alias matches
            results[row["id"]] = (row, (abs(row["fts_score"]) if row["fts_score"] else 1.0) * 0.9)
    return results


def _vector_search(
    db: Database,
    query: str,
    filter_sql: str,
    params: list,
) -> dict[str, tuple]:
    """Run vector similarity search and return dict of item_id -> (row, similarity)."""
    if not embedding_service.is_available():
        return {}

    query_embedding = embedding_service.generate_query_embedding(query)
    if query_embedding is None:
        return {}

    # Fetch items with embeddings
    sql = f"""
        SELECT i.*, b.name as bin_name, b.description as bin_desc,
               b.parent_bin_id as bin_parent_id,
               b.created_at as bin_created, b.updated_at as bin_updated,
               l.id as loc_id, l.name as loc_name, l.description as loc_desc,
               l.created_at as loc_created, l.updated_at as loc_updated,
               i.embedding
        FROM items i
        JOIN bins b ON i.bin_id = b.id
        JOIN locations l ON b.location_id = l.id
        WHERE i.embedding IS NOT NULL
        {filter_sql}
    """
    rows = db.execute(sql, tuple(params))

    if not rows:
        return {}

    # Compute similarities
    results = {}
    embeddings = []
    row_list = []

    for row in rows:
        embedding = embedding_service.bytes_to_embedding(row["embedding"])
        embeddings.append(embedding)
        row_list.append(row)

    similarities = embedding_service.batch_cosine_similarity(query_embedding, embeddings)

    for row, similarity in zip(row_list, similarities):
        # Only include items with reasonable similarity (threshold 0.3)
        if similarity >= 0.3:
            results[row["id"]] = (row, similarity)

    return results


def search_items(
    db: Database,
    query: str,
    location_id: str | None = None,
    bin_id: str | None = None,
    category_id: str | None = None,
) -> list[SearchResult]:
    """Search inventory by name, description, or alias.

    Uses hybrid search combining FTS5 full-text search with vector similarity
    when embeddings are available.

    Args:
        db: Database connection
        query: Search query
        location_id: Filter by location
        bin_id: Filter by bin
        category_id: Filter by category

    Returns:
        List of SearchResult with match scores
    """
    # Build SQL filters
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

    # Run FTS search
    fts_results = _fts_search(db, query, filter_sql, params)

    # Run alias search (excluding items already in FTS results)
    alias_results = _alias_search(db, query, filter_sql, params, set(fts_results.keys()))

    # Run vector search
    vector_results = _vector_search(db, query, filter_sql, params)

    # Combine results with weighted scoring
    fts_weight = settings.fts_search_weight
    vector_weight = settings.vector_search_weight

    # Track all unique items and their combined scores
    combined_scores: dict[str, tuple] = {}  # item_id -> (row, combined_score)

    # Process FTS results
    for item_id, (row, fts_score) in fts_results.items():
        vector_score = vector_results.get(item_id, (None, 0.0))[1]
        # Normalize FTS score (FTS rank is negative, closer to 0 is better)
        # Convert to 0-1 scale where higher is better
        normalized_fts = min(1.0, fts_score / 10.0)  # Cap at 1.0
        combined = (normalized_fts * fts_weight) + (vector_score * vector_weight)
        combined_scores[item_id] = (row, combined)

    # Process alias results
    for item_id, (row, fts_score) in alias_results.items():
        if item_id not in combined_scores:
            vector_score = vector_results.get(item_id, (None, 0.0))[1]
            normalized_fts = min(1.0, fts_score / 10.0)
            combined = (normalized_fts * fts_weight) + (vector_score * vector_weight)
            combined_scores[item_id] = (row, combined)

    # Add vector-only results (items not found by FTS but similar semantically)
    for item_id, (row, vector_score) in vector_results.items():
        if item_id not in combined_scores:
            # No FTS match, only vector similarity
            combined = vector_score * vector_weight
            # Require reasonable similarity for vector-only matches
            if vector_score >= 0.4:
                combined_scores[item_id] = (row, combined)

    # Convert to SearchResult objects
    results = []
    for item_id, (row, score) in combined_scores.items():
        results.append(_row_to_search_result(db, row, score))

    # Sort by combined score (highest first)
    results.sort(key=lambda r: r.match_score, reverse=True)

    # Limit results
    return results[:50]


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
