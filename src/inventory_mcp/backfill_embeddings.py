"""CLI tool to backfill embeddings for existing items."""

import argparse
import logging
import sys

from inventory_mcp.config import settings
from inventory_mcp.db.connection import Database
from inventory_mcp.services import embedding_service

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger("inventory_mcp.backfill")


def backfill_embeddings(force: bool = False, batch_size: int = 100) -> int:
    """Generate embeddings for items that don't have them.

    Args:
        force: If True, regenerate embeddings for all items
        batch_size: Number of items to process at a time

    Returns:
        Number of items processed
    """
    if not embedding_service.is_available():
        logger.error("Embedding service not available. Check that sentence-transformers is installed.")
        return 0

    db = Database(settings.database_path)

    # Get items that need embeddings
    if force:
        query = "SELECT id, name, description, notes FROM items"
        logger.info("Force mode: regenerating embeddings for all items")
    else:
        query = "SELECT id, name, description, notes FROM items WHERE embedding IS NULL"
        logger.info("Generating embeddings for items without embeddings")

    rows = db.execute(query)
    total = len(rows)

    if total == 0:
        logger.info("No items need embedding generation")
        return 0

    logger.info(f"Found {total} items to process")

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
            logger.warning(f"Failed to generate embedding for item: {name}")
            failed += 1
            continue

        # Update the item
        with db.connection() as conn:
            conn.execute(
                "UPDATE items SET embedding = ? WHERE id = ?",
                (embedding_blob, item_id),
            )

        processed += 1
        if processed % batch_size == 0:
            logger.info(f"Processed {processed}/{total} items...")

    logger.info(f"Completed: {processed} items processed, {failed} failed")
    return processed


def main():
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Backfill embeddings for inventory items"
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Regenerate embeddings for all items, not just those missing them",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=100,
        help="Log progress every N items (default: 100)",
    )

    args = parser.parse_args()

    try:
        count = backfill_embeddings(force=args.force, batch_size=args.batch_size)
        sys.exit(0 if count >= 0 else 1)
    except KeyboardInterrupt:
        logger.info("\nInterrupted by user")
        sys.exit(130)
    except Exception as e:
        logger.error(f"Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
