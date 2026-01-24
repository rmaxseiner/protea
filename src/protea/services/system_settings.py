"""System settings service for managing app configuration."""

import logging
import threading
from datetime import datetime, timezone
from typing import Optional

from protea.db.connection import Database
from protea.services import embedding_service

logger = logging.getLogger("protea")

# Available embedding models
EMBEDDING_MODELS = {
    "all-MiniLM-L6-v2": {
        "name": "MiniLM (Fast)",
        "description": "Smaller, faster model. 384 dimensions, ~90MB.",
        "dimensions": 384,
    },
    "all-mpnet-base-v2": {
        "name": "MPNet (Quality)",
        "description": "Larger, better quality. 768 dimensions, ~420MB.",
        "dimensions": 768,
    },
}

# Background regeneration thread
_regen_thread: Optional[threading.Thread] = None


def get_setting(db: Database, key: str, default: str = "") -> str:
    """Get a system setting value."""
    row = db.execute_one(
        "SELECT value FROM system_settings WHERE key = ?",
        (key,),
    )
    return row["value"] if row else default


def set_setting(db: Database, key: str, value: str) -> None:
    """Set a system setting value."""
    now = datetime.now(timezone.utc).isoformat()
    with db.connection() as conn:
        conn.execute(
            """
            INSERT INTO system_settings (key, value, updated_at)
            VALUES (?, ?, ?)
            ON CONFLICT(key) DO UPDATE SET value = ?, updated_at = ?
            """,
            (key, value, now, value, now),
        )


def get_current_model(db: Database) -> str:
    """Get the currently configured embedding model."""
    return get_setting(db, "embedding_model", "all-mpnet-base-v2")


def get_regen_status(db: Database) -> dict:
    """Get the current embedding regeneration status."""
    return {
        "status": get_setting(db, "embedding_regen_status", "idle"),
        "progress": int(get_setting(db, "embedding_regen_progress", "0")),
        "total": int(get_setting(db, "embedding_regen_total", "0")),
        "message": get_setting(db, "embedding_regen_message", ""),
    }


def is_regen_running() -> bool:
    """Check if regeneration is currently running."""
    global _regen_thread
    return _regen_thread is not None and _regen_thread.is_alive()


def change_embedding_model(db: Database, new_model: str) -> dict:
    """Change the embedding model and start regeneration.

    Args:
        db: Database connection
        new_model: Model identifier (e.g., 'all-mpnet-base-v2')

    Returns:
        Status dict with success/error
    """
    global _regen_thread

    if new_model not in EMBEDDING_MODELS:
        return {"error": f"Unknown model: {new_model}"}

    if is_regen_running():
        return {"error": "Embedding regeneration already in progress"}

    current_model = get_current_model(db)
    if new_model == current_model:
        return {"message": "Model unchanged", "model": new_model}

    # Update the setting
    set_setting(db, "embedding_model", new_model)

    # Start regeneration in background
    # Note: We need to get db_path since we'll create a new connection in the thread
    db_path = db.db_path

    _regen_thread = threading.Thread(
        target=_regenerate_embeddings_background,
        args=(db_path, new_model),
        daemon=True,
    )
    _regen_thread.start()

    return {
        "success": True,
        "message": f"Switching to {EMBEDDING_MODELS[new_model]['name']}. Regenerating embeddings...",
        "model": new_model,
    }


def _regenerate_embeddings_background(db_path, model_name: str) -> None:
    """Background task to regenerate all embeddings."""
    # Create new database connection for this thread
    db = Database(db_path)

    try:
        # Update status to running
        set_setting(db, "embedding_regen_status", "running")
        set_setting(db, "embedding_regen_message", f"Loading model {model_name}...")
        set_setting(db, "embedding_regen_progress", "0")

        # Force reload the embedding model with new model name
        # We need to reset the cached model
        embedding_service._model = None
        embedding_service._model_load_attempted = False

        # Temporarily override the settings for this operation
        from protea.config import settings

        original_model = settings.embedding_model
        settings.embedding_model = model_name

        # Get all items
        rows = db.execute("SELECT id, name, description, notes FROM items")
        total = len(rows)

        set_setting(db, "embedding_regen_total", str(total))
        set_setting(db, "embedding_regen_message", f"Regenerating 0/{total} items...")

        if total == 0:
            set_setting(db, "embedding_regen_status", "completed")
            set_setting(db, "embedding_regen_message", "No items to process")
            return

        processed = 0
        failed = 0

        for row in rows:
            item_id = row["id"]
            name = row["name"]
            description = row["description"]
            notes = row["notes"]

            # Build text and generate embedding
            item_text = embedding_service.build_item_text(name, description, notes)
            embedding_blob = embedding_service.generate_embedding(item_text)

            if embedding_blob is None:
                failed += 1
                continue

            # Update the item
            with db.connection() as conn:
                conn.execute(
                    "UPDATE items SET embedding = ? WHERE id = ?",
                    (embedding_blob, item_id),
                )

            processed += 1

            # Update progress every 10 items
            if processed % 10 == 0 or processed == total:
                set_setting(db, "embedding_regen_progress", str(processed))
                set_setting(
                    db, "embedding_regen_message", f"Regenerating {processed}/{total} items..."
                )

        # Restore original model setting (in case something else uses it)
        settings.embedding_model = original_model

        # Update final status
        set_setting(db, "embedding_regen_status", "completed")
        set_setting(db, "embedding_regen_progress", str(processed))
        if failed > 0:
            set_setting(
                db,
                "embedding_regen_message",
                f"Completed: {processed} items, {failed} failed",
            )
        else:
            set_setting(
                db,
                "embedding_regen_message",
                f"Completed: {processed} items regenerated",
            )

        logger.info(f"Embedding regeneration completed: {processed} items, {failed} failed")

    except Exception as e:
        logger.error(f"Embedding regeneration failed: {e}")
        set_setting(db, "embedding_regen_status", "failed")
        set_setting(db, "embedding_regen_message", f"Error: {str(e)}")
