"""Session workflow tools for inventory-mcp."""

import json
from datetime import datetime

from inventory_mcp.config import settings
from inventory_mcp.db.connection import Database
from inventory_mcp.db.models import (
    ActiveSessionInfo,
    Bin,
    BinImage,
    Item,
    ItemSource,
    PendingItem,
    PendingItemSource,
    QuantityType,
    Session,
    SessionDetail,
    SessionImage,
    SessionStatus,
)
from inventory_mcp.services.image_store import ImageStore


def _calculate_staleness(session: Session) -> tuple[bool, int | None]:
    """Calculate if session is stale and duration."""
    if session.status != SessionStatus.PENDING:
        return False, None

    now = datetime.utcnow()
    updated = session.updated_at
    if isinstance(updated, str):
        updated = datetime.fromisoformat(updated)

    delta_minutes = int((now - updated).total_seconds() / 60)
    is_stale = delta_minutes >= settings.session_stale_minutes
    return is_stale, delta_minutes if is_stale else None


def get_active_sessions(db: Database) -> list[ActiveSessionInfo]:
    """Get all pending sessions with staleness indicator.

    Returns:
        List of active session summaries
    """
    rows = db.execute(
        "SELECT * FROM sessions WHERE status = ? ORDER BY created_at",
        (SessionStatus.PENDING.value,),
    )

    results = []
    for row in rows:
        session = Session(
            id=row["id"],
            status=SessionStatus(row["status"]),
            target_bin_id=row["target_bin_id"],
            target_location_id=row["target_location_id"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            committed_at=row["committed_at"],
            cancelled_at=row["cancelled_at"],
            commit_summary=json.loads(row["commit_summary"]) if row["commit_summary"] else None,
        )

        # Get counts
        pending_count = db.execute_one(
            "SELECT COUNT(*) as cnt FROM pending_items WHERE session_id = ?",
            (session.id,),
        )
        image_count = db.execute_one(
            "SELECT COUNT(*) as cnt FROM session_images WHERE session_id = ?",
            (session.id,),
        )

        is_stale, stale_duration = _calculate_staleness(session)

        results.append(
            ActiveSessionInfo(
                session=session,
                pending_item_count=pending_count["cnt"] if pending_count else 0,
                image_count=image_count["cnt"] if image_count else 0,
                is_stale=is_stale,
                stale_duration_minutes=stale_duration,
            )
        )

    return results


def create_session(
    db: Database,
    bin_id: str | None = None,
    location_id: str | None = None,
) -> Session | dict:
    """Create a working session for reviewing/editing items before committing.

    Args:
        db: Database connection
        bin_id: Target bin UUID
        location_id: Target location UUID (if no bin specified)

    Returns:
        Created Session or error dict
    """
    # Check for stale sessions
    active = get_active_sessions(db)
    stale_sessions = [s for s in active if s.is_stale]

    if stale_sessions:
        return {
            "error": "Stale sessions exist. Please restore or cancel them first.",
            "error_code": "SESSION_BLOCKED",
            "stale_sessions": [
                {
                    "id": s.session.id,
                    "created_at": s.session.created_at.isoformat() if isinstance(s.session.created_at, datetime) else s.session.created_at,
                    "stale_minutes": s.stale_duration_minutes,
                    "pending_items": s.pending_item_count,
                }
                for s in stale_sessions
            ],
        }

    # Verify bin exists if provided
    if bin_id:
        bin_row = db.execute_one("SELECT id FROM bins WHERE id = ?", (bin_id,))
        if not bin_row:
            return {
                "error": "Bin not found",
                "error_code": "NOT_FOUND",
                "details": {"bin_id": bin_id},
            }

        # Warn if another pending session targets this bin
        existing = db.execute_one(
            "SELECT id FROM sessions WHERE target_bin_id = ? AND status = ?",
            (bin_id, SessionStatus.PENDING.value),
        )
        if existing:
            return {
                "error": "Another pending session targets this bin",
                "error_code": "SESSION_BLOCKED",
                "details": {"existing_session_id": existing["id"]},
            }

    # Verify location exists if provided
    if location_id:
        loc_row = db.execute_one("SELECT id FROM locations WHERE id = ?", (location_id,))
        if not loc_row:
            return {
                "error": "Location not found",
                "error_code": "NOT_FOUND",
                "details": {"location_id": location_id},
            }

    session = Session(
        target_bin_id=bin_id,
        target_location_id=location_id,
    )

    with db.connection() as conn:
        conn.execute(
            """
            INSERT INTO sessions (id, status, target_bin_id, target_location_id, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                session.id,
                session.status.value,
                session.target_bin_id,
                session.target_location_id,
                session.created_at.isoformat(),
                session.updated_at.isoformat(),
            ),
        )

    return session


def get_session(db: Database, session_id: str) -> SessionDetail | dict:
    """Get session with all images and pending items.

    Args:
        db: Database connection
        session_id: Session UUID

    Returns:
        SessionDetail or error dict
    """
    row = db.execute_one("SELECT * FROM sessions WHERE id = ?", (session_id,))
    if not row:
        return {
            "error": "Session not found",
            "error_code": "NOT_FOUND",
            "details": {"session_id": session_id},
        }

    session = Session(
        id=row["id"],
        status=SessionStatus(row["status"]),
        target_bin_id=row["target_bin_id"],
        target_location_id=row["target_location_id"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
        committed_at=row["committed_at"],
        cancelled_at=row["cancelled_at"],
        commit_summary=json.loads(row["commit_summary"]) if row["commit_summary"] else None,
    )

    # Get images
    image_rows = db.execute(
        "SELECT * FROM session_images WHERE session_id = ? ORDER BY created_at",
        (session_id,),
    )
    images = [
        SessionImage(
            id=r["id"],
            session_id=r["session_id"],
            file_path=r["file_path"],
            thumbnail_path=r["thumbnail_path"],
            original_filename=r["original_filename"],
            width=r["width"],
            height=r["height"],
            file_size_bytes=r["file_size_bytes"],
            extracted_data=json.loads(r["extracted_data"]) if r["extracted_data"] else None,
            created_at=r["created_at"],
        )
        for r in image_rows
    ]

    # Get pending items
    pending_rows = db.execute(
        "SELECT * FROM pending_items WHERE session_id = ? ORDER BY created_at",
        (session_id,),
    )
    pending_items = [
        PendingItem(
            id=r["id"],
            session_id=r["session_id"],
            source_image_id=r["source_image_id"],
            name=r["name"],
            quantity_type=QuantityType(r["quantity_type"]),
            quantity_value=r["quantity_value"],
            quantity_label=r["quantity_label"],
            category_id=r["category_id"],
            confidence=r["confidence"],
            source=PendingItemSource(r["source"]),
            created_at=r["created_at"],
            updated_at=r["updated_at"],
        )
        for r in pending_rows
    ]

    is_stale, stale_duration = _calculate_staleness(session)

    return SessionDetail(
        id=session.id,
        status=session.status,
        target_bin_id=session.target_bin_id,
        target_location_id=session.target_location_id,
        created_at=session.created_at,
        updated_at=session.updated_at,
        committed_at=session.committed_at,
        cancelled_at=session.cancelled_at,
        commit_summary=session.commit_summary,
        images=images,
        pending_items=pending_items,
        is_stale=is_stale,
        stale_duration_minutes=stale_duration,
    )


def add_image_to_session(
    db: Database,
    image_store: ImageStore,
    session_id: str,
    image_base64: str,
    original_filename: str | None = None,
) -> dict:
    """Add an image to session.

    Args:
        db: Database connection
        image_store: Image storage service
        session_id: Session UUID
        image_base64: Base64-encoded image
        original_filename: Original filename

    Returns:
        Dict with session_image
    """
    # Verify session exists and is pending
    session = db.execute_one(
        "SELECT * FROM sessions WHERE id = ?",
        (session_id,),
    )
    if not session:
        return {
            "error": "Session not found",
            "error_code": "NOT_FOUND",
            "details": {"session_id": session_id},
        }

    if session["status"] != SessionStatus.PENDING.value:
        return {
            "error": "Session is not pending",
            "error_code": "INVALID_INPUT",
            "details": {"status": session["status"]},
        }

    # Check image size
    image_bytes = len(image_base64) * 3 // 4
    if image_bytes > settings.max_image_size_bytes:
        return {
            "error": f"Image too large. Maximum size is {settings.max_image_size_bytes // (1024*1024)}MB",
            "error_code": "IMAGE_TOO_LARGE",
        }

    # Save image
    session_image = SessionImage(
        session_id=session_id,
        file_path="",
        original_filename=original_filename,
    )

    try:
        metadata = image_store.save_session_image(
            session_id,
            image_base64,
            session_image.id,
            original_filename,
        )
    except Exception as e:
        return {
            "error": f"Failed to save image: {str(e)}",
            "error_code": "INTERNAL_ERROR",
        }

    session_image.file_path = metadata["file_path"]
    session_image.thumbnail_path = metadata["thumbnail_path"]
    session_image.width = metadata["width"]
    session_image.height = metadata["height"]
    session_image.file_size_bytes = metadata["file_size_bytes"]

    with db.connection() as conn:
        conn.execute(
            """
            INSERT INTO session_images
            (id, session_id, file_path, thumbnail_path, original_filename, width, height, file_size_bytes, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                session_image.id,
                session_image.session_id,
                session_image.file_path,
                session_image.thumbnail_path,
                session_image.original_filename,
                session_image.width,
                session_image.height,
                session_image.file_size_bytes,
                session_image.created_at.isoformat(),
            ),
        )

        # Update session updated_at
        conn.execute(
            "UPDATE sessions SET updated_at = ? WHERE id = ?",
            (datetime.utcnow().isoformat(), session_id),
        )

    return {
        "session_image": session_image,
    }


def add_pending_item(
    db: Database,
    session_id: str,
    name: str,
    quantity_type: str | None = None,
    quantity_value: int | None = None,
    quantity_label: str | None = None,
    category_id: str | None = None,
    source_image_id: str | None = None,
    confidence: float | None = None,
    source: str = "manual",
) -> PendingItem | dict:
    """Add an item to pending session.

    Args:
        db: Database connection
        session_id: Session UUID
        name: Item name
        quantity_type: "exact", "approximate", or "boolean"
        quantity_value: Quantity value
        quantity_label: Label like "assorted"
        category_id: Category UUID
        source_image_id: Source image UUID
        confidence: Vision extraction confidence
        source: "vision" or "manual"

    Returns:
        Created PendingItem or error dict
    """
    # Verify session exists and is pending
    session = db.execute_one(
        "SELECT * FROM sessions WHERE id = ?",
        (session_id,),
    )
    if not session:
        return {
            "error": "Session not found",
            "error_code": "NOT_FOUND",
        }

    if session["status"] != SessionStatus.PENDING.value:
        return {
            "error": "Session is not pending",
            "error_code": "INVALID_INPUT",
        }

    qt = QuantityType(quantity_type) if quantity_type else QuantityType.BOOLEAN
    src = PendingItemSource(source) if source else PendingItemSource.MANUAL

    if qt == QuantityType.BOOLEAN:
        quantity_value = 1

    pending = PendingItem(
        session_id=session_id,
        source_image_id=source_image_id,
        name=name,
        quantity_type=qt,
        quantity_value=quantity_value,
        quantity_label=quantity_label,
        category_id=category_id,
        confidence=confidence,
        source=src,
    )

    with db.connection() as conn:
        conn.execute(
            """
            INSERT INTO pending_items
            (id, session_id, source_image_id, name, quantity_type, quantity_value,
             quantity_label, category_id, confidence, source, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                pending.id,
                pending.session_id,
                pending.source_image_id,
                pending.name,
                pending.quantity_type.value,
                pending.quantity_value,
                pending.quantity_label,
                pending.category_id,
                pending.confidence,
                pending.source.value,
                pending.created_at.isoformat(),
                pending.updated_at.isoformat(),
            ),
        )

        # Update session
        conn.execute(
            "UPDATE sessions SET updated_at = ? WHERE id = ?",
            (datetime.utcnow().isoformat(), session_id),
        )

    return pending


def update_pending_item(
    db: Database,
    session_id: str,
    pending_id: str,
    name: str | None = None,
    quantity_type: str | None = None,
    quantity_value: int | None = None,
    quantity_label: str | None = None,
    category_id: str | None = None,
) -> PendingItem | dict:
    """Edit a pending item before committing.

    Args:
        db: Database connection
        session_id: Session UUID
        pending_id: Pending item UUID
        name: New name
        quantity_type: New quantity type
        quantity_value: New quantity value
        quantity_label: New quantity label
        category_id: New category

    Returns:
        Updated PendingItem or error dict
    """
    row = db.execute_one(
        "SELECT * FROM pending_items WHERE id = ? AND session_id = ?",
        (pending_id, session_id),
    )
    if not row:
        return {
            "error": "Pending item not found in this session",
            "error_code": "NOT_FOUND",
        }

    new_name = name if name is not None else row["name"]
    new_quantity_type = quantity_type if quantity_type is not None else row["quantity_type"]
    new_quantity_value = quantity_value if quantity_value is not None else row["quantity_value"]
    new_quantity_label = quantity_label if quantity_label is not None else row["quantity_label"]
    new_category_id = category_id if category_id is not None else row["category_id"]
    updated_at = datetime.utcnow()

    with db.connection() as conn:
        conn.execute(
            """
            UPDATE pending_items
            SET name = ?, quantity_type = ?, quantity_value = ?, quantity_label = ?,
                category_id = ?, updated_at = ?
            WHERE id = ?
            """,
            (
                new_name,
                new_quantity_type,
                new_quantity_value,
                new_quantity_label,
                new_category_id,
                updated_at.isoformat(),
                pending_id,
            ),
        )

        conn.execute(
            "UPDATE sessions SET updated_at = ? WHERE id = ?",
            (updated_at.isoformat(), session_id),
        )

    return PendingItem(
        id=pending_id,
        session_id=session_id,
        source_image_id=row["source_image_id"],
        name=new_name,
        quantity_type=QuantityType(new_quantity_type),
        quantity_value=new_quantity_value,
        quantity_label=new_quantity_label,
        category_id=new_category_id,
        confidence=row["confidence"],
        source=PendingItemSource(row["source"]),
        created_at=row["created_at"],
        updated_at=updated_at,
    )


def remove_pending_item(
    db: Database,
    session_id: str,
    pending_id: str,
) -> dict:
    """Remove an item from pending session.

    Args:
        db: Database connection
        session_id: Session UUID
        pending_id: Pending item UUID

    Returns:
        Success dict
    """
    row = db.execute_one(
        "SELECT id FROM pending_items WHERE id = ? AND session_id = ?",
        (pending_id, session_id),
    )
    if not row:
        return {
            "error": "Pending item not found in this session",
            "error_code": "NOT_FOUND",
        }

    with db.connection() as conn:
        conn.execute("DELETE FROM pending_items WHERE id = ?", (pending_id,))
        conn.execute(
            "UPDATE sessions SET updated_at = ? WHERE id = ?",
            (datetime.utcnow().isoformat(), session_id),
        )

    return {"success": True}


def set_session_target(
    db: Database,
    session_id: str,
    bin_id: str | None = None,
    location_id: str | None = None,
) -> Session | dict:
    """Set or update the target bin/location for the session.

    Args:
        db: Database connection
        session_id: Session UUID
        bin_id: Target bin UUID
        location_id: Target location UUID

    Returns:
        Updated Session or error dict
    """
    row = db.execute_one("SELECT * FROM sessions WHERE id = ?", (session_id,))
    if not row:
        return {
            "error": "Session not found",
            "error_code": "NOT_FOUND",
        }

    if row["status"] != SessionStatus.PENDING.value:
        return {
            "error": "Session is not pending",
            "error_code": "INVALID_INPUT",
        }

    # Verify bin/location exist
    if bin_id:
        bin_row = db.execute_one("SELECT id FROM bins WHERE id = ?", (bin_id,))
        if not bin_row:
            return {
                "error": "Bin not found",
                "error_code": "NOT_FOUND",
            }

    if location_id:
        loc_row = db.execute_one("SELECT id FROM locations WHERE id = ?", (location_id,))
        if not loc_row:
            return {
                "error": "Location not found",
                "error_code": "NOT_FOUND",
            }

    updated_at = datetime.utcnow()

    with db.connection() as conn:
        conn.execute(
            """
            UPDATE sessions
            SET target_bin_id = ?, target_location_id = ?, updated_at = ?
            WHERE id = ?
            """,
            (bin_id, location_id, updated_at.isoformat(), session_id),
        )

    return Session(
        id=session_id,
        status=SessionStatus(row["status"]),
        target_bin_id=bin_id,
        target_location_id=location_id,
        created_at=row["created_at"],
        updated_at=updated_at,
        committed_at=row["committed_at"],
        cancelled_at=row["cancelled_at"],
    )


def commit_session(
    db: Database,
    image_store: ImageStore,
    session_id: str,
    bin_id: str | None = None,
) -> dict:
    """Commit all pending items to inventory.

    Args:
        db: Database connection
        image_store: Image storage service
        session_id: Session UUID
        bin_id: Override target bin

    Returns:
        Result dict with items_added, images_saved, bin_created
    """
    session_detail = get_session(db, session_id)
    if isinstance(session_detail, dict) and "error" in session_detail:
        return session_detail

    if session_detail.status != SessionStatus.PENDING:
        return {
            "error": "Session is not pending",
            "error_code": "INVALID_INPUT",
        }

    # Determine target bin
    target_bin_id = bin_id or session_detail.target_bin_id
    created_bin = None

    if not target_bin_id:
        # Try to create default bin from location
        if session_detail.target_location_id:
            from inventory_mcp.tools.bins import create_bin

            result = create_bin(
                db,
                name="Default",
                location_id=session_detail.target_location_id,
            )
            if isinstance(result, dict) and "error" in result:
                # Default bin might already exist
                existing = db.execute_one(
                    "SELECT id FROM bins WHERE name = ? AND location_id = ?",
                    ("Default", session_detail.target_location_id),
                )
                if existing:
                    target_bin_id = existing["id"]
                else:
                    return result
            else:
                target_bin_id = result.id
                created_bin = result
        else:
            return {
                "error": "No target bin specified and no location to create default bin",
                "error_code": "NO_TARGET",
            }

    # Create items from pending items
    from inventory_mcp.tools.items import add_item

    items_added = []
    for pending in session_detail.pending_items:
        # Determine photo_url from source image
        photo_url = None
        if pending.source_image_id:
            img = next(
                (i for i in session_detail.images if i.id == pending.source_image_id),
                None,
            )
            if img:
                photo_url = img.file_path

        result = add_item(
            db=db,
            name=pending.name,
            bin_id=target_bin_id,
            category_id=pending.category_id,
            quantity_type=pending.quantity_type.value,
            quantity_value=pending.quantity_value,
            quantity_label=pending.quantity_label,
            source=ItemSource.VISION.value if pending.source == PendingItemSource.VISION else ItemSource.MANUAL.value,
            source_reference=session_id,
        )

        if isinstance(result, Item):
            # Update photo_url
            if photo_url:
                with db.connection() as conn:
                    conn.execute(
                        "UPDATE items SET photo_url = ? WHERE id = ?",
                        (photo_url, result.id),
                    )
                result.photo_url = photo_url
            items_added.append(result)

    # Copy session images to bin
    images_saved = []
    for session_image in session_detail.images:
        try:
            metadata = image_store.copy_to_bin(
                session_image.file_path,
                target_bin_id,
                session_image.id + "_bin",
            )

            bin_image = BinImage(
                bin_id=target_bin_id,
                file_path=metadata["file_path"],
                thumbnail_path=metadata["thumbnail_path"],
                source_session_id=session_id,
                source_session_image_id=session_image.id,
                width=metadata["width"],
                height=metadata["height"],
                file_size_bytes=metadata["file_size_bytes"],
            )

            with db.connection() as conn:
                conn.execute(
                    """
                    INSERT INTO bin_images
                    (id, bin_id, file_path, thumbnail_path, source_session_id, source_session_image_id,
                     width, height, file_size_bytes, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        bin_image.id,
                        bin_image.bin_id,
                        bin_image.file_path,
                        bin_image.thumbnail_path,
                        bin_image.source_session_id,
                        bin_image.source_session_image_id,
                        bin_image.width,
                        bin_image.height,
                        bin_image.file_size_bytes,
                        bin_image.created_at.isoformat(),
                    ),
                )

            images_saved.append(bin_image)
        except Exception:
            # Continue on image copy errors
            pass

    # Update session status
    committed_at = datetime.utcnow()
    commit_summary = {
        "items_added": len(items_added),
        "images_saved": len(images_saved),
        "target_bin_id": target_bin_id,
    }

    with db.connection() as conn:
        conn.execute(
            """
            UPDATE sessions
            SET status = ?, committed_at = ?, commit_summary = ?, updated_at = ?
            WHERE id = ?
            """,
            (
                SessionStatus.COMMITTED.value,
                committed_at.isoformat(),
                json.dumps(commit_summary),
                committed_at.isoformat(),
                session_id,
            ),
        )

    return {
        "success": True,
        "items_added": items_added,
        "images_saved": images_saved,
        "bin_created": created_bin,
        "session": Session(
            id=session_id,
            status=SessionStatus.COMMITTED,
            target_bin_id=target_bin_id,
            target_location_id=session_detail.target_location_id,
            created_at=session_detail.created_at,
            updated_at=committed_at,
            committed_at=committed_at,
            commit_summary=commit_summary,
        ),
    }


def cancel_session(
    db: Database,
    image_store: ImageStore,
    session_id: str,
    reason: str | None = None,
) -> Session | dict:
    """Cancel session without committing.

    Deletes session images.

    Args:
        db: Database connection
        image_store: Image storage service
        session_id: Session UUID
        reason: Optional cancellation reason

    Returns:
        Cancelled Session or error dict
    """
    row = db.execute_one("SELECT * FROM sessions WHERE id = ?", (session_id,))
    if not row:
        return {
            "error": "Session not found",
            "error_code": "NOT_FOUND",
        }

    if row["status"] != SessionStatus.PENDING.value:
        return {
            "error": "Session is not pending",
            "error_code": "INVALID_INPUT",
        }

    # Delete session images
    image_store.delete_session_images(session_id)

    cancelled_at = datetime.utcnow()

    with db.connection() as conn:
        conn.execute(
            """
            UPDATE sessions
            SET status = ?, cancelled_at = ?, updated_at = ?, commit_summary = ?
            WHERE id = ?
            """,
            (
                SessionStatus.CANCELLED.value,
                cancelled_at.isoformat(),
                cancelled_at.isoformat(),
                json.dumps({"reason": reason}) if reason else None,
                session_id,
            ),
        )

    return Session(
        id=session_id,
        status=SessionStatus.CANCELLED,
        target_bin_id=row["target_bin_id"],
        target_location_id=row["target_location_id"],
        created_at=row["created_at"],
        updated_at=cancelled_at,
        cancelled_at=cancelled_at,
    )


def get_session_history(
    db: Database,
    bin_id: str | None = None,
    status: str | None = None,
    limit: int = 20,
) -> list[Session]:
    """Get historical sessions (committed/cancelled).

    Args:
        db: Database connection
        bin_id: Filter by target bin
        status: Filter by status ("committed", "cancelled")
        limit: Max results

    Returns:
        List of sessions
    """
    params = []
    filter_clauses = []

    if bin_id:
        filter_clauses.append("target_bin_id = ?")
        params.append(bin_id)

    if status:
        filter_clauses.append("status = ?")
        params.append(status)
    else:
        filter_clauses.append("status IN (?, ?)")
        params.extend([SessionStatus.COMMITTED.value, SessionStatus.CANCELLED.value])

    filter_sql = "WHERE " + " AND ".join(filter_clauses)

    rows = db.execute(
        f"""
        SELECT * FROM sessions
        {filter_sql}
        ORDER BY updated_at DESC
        LIMIT ?
        """,
        (*params, limit),
    )

    return [
        Session(
            id=row["id"],
            status=SessionStatus(row["status"]),
            target_bin_id=row["target_bin_id"],
            target_location_id=row["target_location_id"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            committed_at=row["committed_at"],
            cancelled_at=row["cancelled_at"],
            commit_summary=json.loads(row["commit_summary"]) if row["commit_summary"] else None,
        )
        for row in rows
    ]
