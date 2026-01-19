"""MCP Server for inventory management."""

import asyncio
import json
import logging
from typing import Any

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import TextContent, Tool

from protea.config import settings
from protea.db.connection import Database
from protea.services.image_store import ImageStore
from protea.tools import (
    aliases,
    bins,
    categories,
    items,
    locations,
    search,
    sessions,
    vision,
)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("protea")

# Initialize services
db = Database(settings.database_path)
image_store = ImageStore(
    settings.image_base_path,
    settings.image_format,
    settings.image_quality,
    settings.thumbnail_size,
)

# Create MCP server
server = Server("protea")


def _process_bin_images(bin_id: str, context: str | None = None) -> dict:
    """Process all images for a bin using Claude vision.

    Args:
        bin_id: Bin UUID
        context: Optional context hint

    Returns:
        Dict with extracted items from all images
    """
    import base64
    from pathlib import Path

    # Get bin images
    bin_images = bins.get_bin_images(db, bin_id)
    if isinstance(bin_images, dict) and "error" in bin_images:
        return bin_images

    if not bin_images:
        return {
            "error": "No images found for this bin",
            "error_code": "NO_IMAGES",
            "details": {"bin_id": bin_id},
        }

    all_items = []
    all_labels = []
    all_suggestions = []
    processed_images = 0
    failed_images = []

    for bin_image in bin_images:
        image_path = Path(settings.image_base_path) / bin_image.file_path

        if not image_path.exists():
            failed_images.append({
                "image_id": bin_image.id,
                "error": "Image file not found",
            })
            continue

        try:
            # Read and encode image
            with open(image_path, "rb") as f:
                image_data = f.read()
            image_base64 = base64.b64encode(image_data).decode("utf-8")

            # Extract items using vision
            result = vision.extract_items_from_image(image_base64, context)

            if isinstance(result, dict) and "error" in result:
                failed_images.append({
                    "image_id": bin_image.id,
                    "error": result.get("error"),
                })
                continue

            # Collect results
            all_items.extend(result.get("items", []))
            all_labels.extend(result.get("labels_detected", []))
            if result.get("suggestions"):
                all_suggestions.append(result["suggestions"])
            processed_images += 1

        except Exception as e:
            logger.error(f"Error processing image {bin_image.id}: {e}")
            failed_images.append({
                "image_id": bin_image.id,
                "error": str(e),
            })

    return {
        "bin_id": bin_id,
        "images_processed": processed_images,
        "images_failed": len(failed_images),
        "items": all_items,
        "labels_detected": list(set(all_labels)),
        "suggestions": all_suggestions,
        "failed_images": failed_images if failed_images else None,
    }


def _serialize_result(result: Any) -> str:
    """Serialize a result to JSON string."""
    if hasattr(result, "model_dump"):
        return json.dumps(result.model_dump(), default=str)
    elif isinstance(result, list):
        return json.dumps(
            [r.model_dump() if hasattr(r, "model_dump") else r for r in result],
            default=str,
        )
    elif isinstance(result, dict):
        return json.dumps(result, default=str)
    else:
        return json.dumps({"result": str(result)}, default=str)


# Tool definitions
TOOLS = [
    # Locations
    Tool(
        name="get_locations",
        description="List all locations",
        inputSchema={"type": "object", "properties": {}, "required": []},
    ),
    Tool(
        name="get_location",
        description="Get a location by ID or name",
        inputSchema={
            "type": "object",
            "properties": {
                "location_id": {"type": "string", "description": "Location UUID"},
                "name": {"type": "string", "description": "Location name"},
            },
        },
    ),
    Tool(
        name="create_location",
        description="Create a new location",
        inputSchema={
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "Location name (must be unique)"},
                "description": {"type": "string", "description": "Optional description"},
            },
            "required": ["name"],
        },
    ),
    Tool(
        name="update_location",
        description="Update a location",
        inputSchema={
            "type": "object",
            "properties": {
                "location_id": {"type": "string", "description": "Location UUID"},
                "name": {"type": "string", "description": "New name"},
                "description": {"type": "string", "description": "New description"},
            },
            "required": ["location_id"],
        },
    ),
    Tool(
        name="delete_location",
        description="Delete a location (fails if it has bins)",
        inputSchema={
            "type": "object",
            "properties": {
                "location_id": {"type": "string", "description": "Location UUID"},
            },
            "required": ["location_id"],
        },
    ),
    # Bins
    Tool(
        name="get_bins",
        description="List bins, optionally filtered by location or parent bin",
        inputSchema={
            "type": "object",
            "properties": {
                "location_id": {"type": "string", "description": "Filter by location UUID"},
                "parent_bin_id": {"type": "string", "description": "Filter by parent bin UUID (get children)"},
                "root_only": {"type": "boolean", "description": "Only return root-level bins (no parent)", "default": False},
            },
        },
    ),
    Tool(
        name="get_bin",
        description="Get a single bin by ID or name, with optional items, images, and nested hierarchy info",
        inputSchema={
            "type": "object",
            "properties": {
                "bin_id": {"type": "string", "description": "Bin UUID"},
                "bin_name": {"type": "string", "description": "Bin name"},
                "include_items": {"type": "boolean", "description": "Include items", "default": True},
                "include_images": {"type": "boolean", "description": "Include images", "default": False},
            },
        },
    ),
    Tool(
        name="get_bin_by_path",
        description="Resolve a bin by its full path in a single call (e.g., 'Garage/Tool Chest/Drawer 9')",
        inputSchema={
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Path like 'Location/Bin1/Bin2' or 'Bin1/Bin2' if location provided"},
                "location_id": {"type": "string", "description": "Location UUID if path doesn't include location"},
                "location_name": {"type": "string", "description": "Location name if path doesn't include location"},
            },
            "required": ["path"],
        },
    ),
    Tool(
        name="get_bin_tree",
        description="Get nested tree structure of bins for efficient hierarchy display",
        inputSchema={
            "type": "object",
            "properties": {
                "location_id": {"type": "string", "description": "Filter by location UUID"},
                "root_bin_id": {"type": "string", "description": "Start from specific bin (get subtree)"},
                "max_depth": {"type": "integer", "description": "Maximum nesting depth", "default": 10},
            },
        },
    ),
    Tool(
        name="create_bin",
        description="Create a new bin in a location, optionally nested inside another bin",
        inputSchema={
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "Bin name"},
                "location_id": {"type": "string", "description": "Parent location UUID"},
                "parent_bin_id": {"type": "string", "description": "Parent bin UUID for nesting (optional)"},
                "description": {"type": "string", "description": "Optional description"},
            },
            "required": ["name", "location_id"],
        },
    ),
    Tool(
        name="update_bin",
        description="Update a bin. Use parent_bin_id='' to move to root level",
        inputSchema={
            "type": "object",
            "properties": {
                "bin_id": {"type": "string", "description": "Bin UUID"},
                "name": {"type": "string", "description": "New name"},
                "location_id": {"type": "string", "description": "New location"},
                "parent_bin_id": {"type": "string", "description": "New parent bin (empty string '' to move to root)"},
                "description": {"type": "string", "description": "New description"},
            },
            "required": ["bin_id"],
        },
    ),
    Tool(
        name="delete_bin",
        description="Delete a bin (fails if it has items or child bins)",
        inputSchema={
            "type": "object",
            "properties": {
                "bin_id": {"type": "string", "description": "Bin UUID"},
            },
            "required": ["bin_id"],
        },
    ),
    # Items
    Tool(
        name="get_item",
        description="Get a single item by ID with its bin and location",
        inputSchema={
            "type": "object",
            "properties": {
                "item_id": {"type": "string", "description": "Item UUID"},
            },
            "required": ["item_id"],
        },
    ),
    Tool(
        name="add_item",
        description="Add an item to inventory",
        inputSchema={
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "Item name"},
                "bin_id": {"type": "string", "description": "Target bin UUID"},
                "category_id": {"type": "string", "description": "Category UUID"},
                "quantity_type": {"type": "string", "enum": ["exact", "approximate", "boolean"], "default": "boolean"},
                "quantity_value": {"type": "integer", "description": "Quantity value"},
                "quantity_label": {"type": "string", "description": "Label like 'assorted', 'roll'"},
                "description": {"type": "string", "description": "Item description"},
                "notes": {"type": "string", "description": "Free-form notes"},
            },
            "required": ["name", "bin_id"],
        },
    ),
    Tool(
        name="update_item",
        description="Update an item",
        inputSchema={
            "type": "object",
            "properties": {
                "item_id": {"type": "string", "description": "Item UUID"},
                "name": {"type": "string"},
                "category_id": {"type": "string"},
                "quantity_type": {"type": "string", "enum": ["exact", "approximate", "boolean"]},
                "quantity_value": {"type": "integer"},
                "quantity_label": {"type": "string"},
                "description": {"type": "string"},
                "notes": {"type": "string"},
            },
            "required": ["item_id"],
        },
    ),
    Tool(
        name="remove_item",
        description="Remove an item from inventory",
        inputSchema={
            "type": "object",
            "properties": {
                "item_id": {"type": "string", "description": "Item UUID"},
                "reason": {"type": "string", "description": "Reason: used, discarded, lost"},
            },
            "required": ["item_id"],
        },
    ),
    Tool(
        name="use_item",
        description="Decrement item quantity or mark as used",
        inputSchema={
            "type": "object",
            "properties": {
                "item_id": {"type": "string", "description": "Item UUID"},
                "quantity": {"type": "integer", "description": "Amount to use", "default": 1},
                "notes": {"type": "string", "description": "Usage notes"},
            },
            "required": ["item_id"],
        },
    ),
    Tool(
        name="move_item",
        description="Move item to a different bin. Can split if quantity < total.",
        inputSchema={
            "type": "object",
            "properties": {
                "item_id": {"type": "string", "description": "Item UUID"},
                "to_bin_id": {"type": "string", "description": "Target bin UUID"},
                "quantity": {"type": "integer", "description": "Amount to move (None = all)"},
                "notes": {"type": "string", "description": "Move notes"},
            },
            "required": ["item_id", "to_bin_id"],
        },
    ),
    # Search
    Tool(
        name="search_items",
        description="Search inventory by name, description, or alias",
        inputSchema={
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search query"},
                "location_id": {"type": "string", "description": "Filter by location"},
                "bin_id": {"type": "string", "description": "Filter by bin"},
                "category_id": {"type": "string", "description": "Filter by category"},
            },
            "required": ["query"],
        },
    ),
    Tool(
        name="find_item",
        description="Find where a specific item is located",
        inputSchema={
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Item name to find"},
            },
            "required": ["query"],
        },
    ),
    Tool(
        name="list_items",
        description="List items with filters",
        inputSchema={
            "type": "object",
            "properties": {
                "bin_id": {"type": "string", "description": "Filter by bin"},
                "location_id": {"type": "string", "description": "Filter by location"},
                "category_id": {"type": "string", "description": "Filter by category"},
                "include_children": {"type": "boolean", "description": "Include subcategories", "default": True},
            },
        },
    ),
    Tool(
        name="get_item_history",
        description="Get activity history for an item",
        inputSchema={
            "type": "object",
            "properties": {
                "item_id": {"type": "string", "description": "Item UUID"},
            },
            "required": ["item_id"],
        },
    ),
    # Categories
    Tool(
        name="get_categories",
        description="List all categories, optionally as tree structure",
        inputSchema={
            "type": "object",
            "properties": {
                "as_tree": {"type": "boolean", "description": "Return as nested tree", "default": False},
            },
        },
    ),
    Tool(
        name="create_category",
        description="Create a category",
        inputSchema={
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "Category name"},
                "parent_id": {"type": "string", "description": "Parent category UUID"},
            },
            "required": ["name"],
        },
    ),
    Tool(
        name="update_category",
        description="Update a category",
        inputSchema={
            "type": "object",
            "properties": {
                "category_id": {"type": "string", "description": "Category UUID"},
                "name": {"type": "string"},
                "parent_id": {"type": "string", "description": "New parent (empty string for root)"},
            },
            "required": ["category_id"],
        },
    ),
    Tool(
        name="delete_category",
        description="Delete a category (fails if it has items, cascades empty children)",
        inputSchema={
            "type": "object",
            "properties": {
                "category_id": {"type": "string", "description": "Category UUID"},
            },
            "required": ["category_id"],
        },
    ),
    # Aliases
    Tool(
        name="add_alias",
        description="Add an alias for an item (e.g., 'Allen key' for 'Hex wrench')",
        inputSchema={
            "type": "object",
            "properties": {
                "item_id": {"type": "string", "description": "Item UUID"},
                "alias": {"type": "string", "description": "Alternative name"},
            },
            "required": ["item_id", "alias"],
        },
    ),
    Tool(
        name="get_aliases",
        description="Get all aliases for an item",
        inputSchema={
            "type": "object",
            "properties": {
                "item_id": {"type": "string", "description": "Item UUID"},
            },
            "required": ["item_id"],
        },
    ),
    Tool(
        name="remove_alias",
        description="Remove an alias",
        inputSchema={
            "type": "object",
            "properties": {
                "alias_id": {"type": "string", "description": "Alias UUID"},
            },
            "required": ["alias_id"],
        },
    ),
    # Sessions
    Tool(
        name="get_active_sessions",
        description="Get all pending sessions with staleness indicator",
        inputSchema={"type": "object", "properties": {}},
    ),
    Tool(
        name="create_session",
        description="Create a working session for reviewing/editing items before committing",
        inputSchema={
            "type": "object",
            "properties": {
                "bin_id": {"type": "string", "description": "Target bin UUID"},
                "location_id": {"type": "string", "description": "Target location UUID"},
            },
        },
    ),
    Tool(
        name="get_session",
        description="Get session with all images and pending items",
        inputSchema={
            "type": "object",
            "properties": {
                "session_id": {"type": "string", "description": "Session UUID"},
            },
            "required": ["session_id"],
        },
    ),
    Tool(
        name="add_pending_item",
        description="Manually add an item to pending session",
        inputSchema={
            "type": "object",
            "properties": {
                "session_id": {"type": "string", "description": "Session UUID"},
                "name": {"type": "string", "description": "Item name"},
                "quantity_type": {"type": "string", "enum": ["exact", "approximate", "boolean"]},
                "quantity_value": {"type": "integer"},
                "quantity_label": {"type": "string"},
                "category_id": {"type": "string"},
            },
            "required": ["session_id", "name"],
        },
    ),
    Tool(
        name="update_pending_item",
        description="Edit a pending item before committing",
        inputSchema={
            "type": "object",
            "properties": {
                "session_id": {"type": "string", "description": "Session UUID"},
                "pending_id": {"type": "string", "description": "Pending item UUID"},
                "name": {"type": "string"},
                "quantity_type": {"type": "string", "enum": ["exact", "approximate", "boolean"]},
                "quantity_value": {"type": "integer"},
                "quantity_label": {"type": "string"},
                "category_id": {"type": "string"},
            },
            "required": ["session_id", "pending_id"],
        },
    ),
    Tool(
        name="remove_pending_item",
        description="Remove an item from pending session",
        inputSchema={
            "type": "object",
            "properties": {
                "session_id": {"type": "string", "description": "Session UUID"},
                "pending_id": {"type": "string", "description": "Pending item UUID"},
            },
            "required": ["session_id", "pending_id"],
        },
    ),
    Tool(
        name="set_session_target",
        description="Set or update the target bin/location for a session",
        inputSchema={
            "type": "object",
            "properties": {
                "session_id": {"type": "string", "description": "Session UUID"},
                "bin_id": {"type": "string", "description": "Target bin UUID"},
                "location_id": {"type": "string", "description": "Target location UUID"},
            },
            "required": ["session_id"],
        },
    ),
    Tool(
        name="commit_session",
        description="Commit all pending items to inventory",
        inputSchema={
            "type": "object",
            "properties": {
                "session_id": {"type": "string", "description": "Session UUID"},
                "bin_id": {"type": "string", "description": "Override target bin"},
            },
            "required": ["session_id"],
        },
    ),
    Tool(
        name="cancel_session",
        description="Cancel session without committing (deletes session images)",
        inputSchema={
            "type": "object",
            "properties": {
                "session_id": {"type": "string", "description": "Session UUID"},
                "reason": {"type": "string", "description": "Cancellation reason"},
            },
            "required": ["session_id"],
        },
    ),
    Tool(
        name="get_session_history",
        description="Get historical sessions (committed/cancelled)",
        inputSchema={
            "type": "object",
            "properties": {
                "bin_id": {"type": "string", "description": "Filter by target bin"},
                "status": {"type": "string", "enum": ["committed", "cancelled"]},
                "limit": {"type": "integer", "default": 20},
            },
        },
    ),
    # Product Lookup
    Tool(
        name="lookup_product",
        description="Lookup product details from barcode/ASIN (stub - returns mock data)",
        inputSchema={
            "type": "object",
            "properties": {
                "code": {"type": "string", "description": "Product code (UPC, EAN, ASIN)"},
                "code_type": {"type": "string", "enum": ["asin", "upc", "ean"]},
            },
            "required": ["code"],
        },
    ),
    # Bin Images
    Tool(
        name="get_bin_images",
        description="Get all images for a bin. Use this to see what photos have been uploaded to a bin.",
        inputSchema={
            "type": "object",
            "properties": {
                "bin_id": {"type": "string", "description": "Bin UUID"},
            },
            "required": ["bin_id"],
        },
    ),
    Tool(
        name="process_bin_images",
        description="Process all images for a bin using Claude vision to extract inventory items. Returns list of detected items with quantities and categories. Use this after photos have been uploaded to a bin via the web UI.",
        inputSchema={
            "type": "object",
            "properties": {
                "bin_id": {"type": "string", "description": "Bin UUID"},
                "context": {"type": "string", "description": "Optional context hint (e.g., 'this is an electronics drawer')"},
            },
            "required": ["bin_id"],
        },
    ),
    Tool(
        name="add_items_bulk",
        description="Add multiple items to a bin at once. Use this after processing bin images to add all extracted items.",
        inputSchema={
            "type": "object",
            "properties": {
                "bin_id": {"type": "string", "description": "Target bin UUID"},
                "items": {
                    "type": "array",
                    "description": "List of items to add",
                    "items": {
                        "type": "object",
                        "properties": {
                            "name": {"type": "string", "description": "Item name"},
                            "quantity_type": {"type": "string", "enum": ["exact", "approximate", "boolean"]},
                            "quantity_value": {"type": "integer"},
                            "quantity_label": {"type": "string"},
                            "description": {"type": "string"},
                            "category_id": {"type": "string"},
                        },
                        "required": ["name"],
                    },
                },
            },
            "required": ["bin_id", "items"],
        },
    ),
]


@server.list_tools()
async def list_tools() -> list[Tool]:
    """Return list of available tools."""
    return TOOLS


@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    """Route tool calls to appropriate handlers."""
    try:
        result = await _handle_tool(name, arguments)
        return [TextContent(type="text", text=_serialize_result(result))]
    except Exception as e:
        logger.error(f"Error in tool {name}: {e}", exc_info=True)
        error_result = {
            "error": str(e),
            "error_code": "INTERNAL_ERROR",
        }
        return [TextContent(type="text", text=json.dumps(error_result))]


async def _handle_tool(name: str, arguments: dict) -> Any:
    """Handle a tool call."""
    # Location tools
    if name == "get_locations":
        return locations.get_locations(db)
    elif name == "get_location":
        return locations.get_location(db, **arguments)
    elif name == "create_location":
        return locations.create_location(db, **arguments)
    elif name == "update_location":
        return locations.update_location(db, **arguments)
    elif name == "delete_location":
        return locations.delete_location(db, **arguments)

    # Bin tools
    elif name == "get_bins":
        return bins.get_bins(db, **arguments)
    elif name == "get_bin":
        return bins.get_bin(db, **arguments)
    elif name == "get_bin_by_path":
        return bins.get_bin_by_path(db, **arguments)
    elif name == "get_bin_tree":
        return bins.get_bin_tree(db, **arguments)
    elif name == "create_bin":
        return bins.create_bin(db, **arguments)
    elif name == "update_bin":
        return bins.update_bin(db, **arguments)
    elif name == "delete_bin":
        return bins.delete_bin(db, **arguments)

    # Item tools
    elif name == "get_item":
        return items.get_item(db, **arguments)
    elif name == "add_item":
        return items.add_item(db, **arguments)
    elif name == "update_item":
        return items.update_item(db, **arguments)
    elif name == "remove_item":
        return items.remove_item(db, **arguments)
    elif name == "use_item":
        return items.use_item(db, **arguments)
    elif name == "move_item":
        return items.move_item(db, **arguments)

    # Search tools
    elif name == "search_items":
        return search.search_items(db, **arguments)
    elif name == "find_item":
        return search.find_item(db, **arguments)
    elif name == "list_items":
        return search.list_items(db, **arguments)
    elif name == "get_item_history":
        return search.get_item_history(db, **arguments)

    # Category tools
    elif name == "get_categories":
        return categories.get_categories(db, **arguments)
    elif name == "create_category":
        return categories.create_category(db, **arguments)
    elif name == "update_category":
        return categories.update_category(db, **arguments)
    elif name == "delete_category":
        return categories.delete_category(db, **arguments)

    # Alias tools
    elif name == "add_alias":
        return aliases.add_alias(db, **arguments)
    elif name == "get_aliases":
        return aliases.get_aliases(db, **arguments)
    elif name == "remove_alias":
        return aliases.remove_alias(db, **arguments)

    # Session tools
    elif name == "get_active_sessions":
        return sessions.get_active_sessions(db)
    elif name == "create_session":
        return sessions.create_session(db, **arguments)
    elif name == "get_session":
        return sessions.get_session(db, **arguments)
    elif name == "add_pending_item":
        return sessions.add_pending_item(db, **arguments)
    elif name == "update_pending_item":
        return sessions.update_pending_item(db, **arguments)
    elif name == "remove_pending_item":
        return sessions.remove_pending_item(db, **arguments)
    elif name == "set_session_target":
        return sessions.set_session_target(db, **arguments)
    elif name == "commit_session":
        return sessions.commit_session(db, image_store, **arguments)
    elif name == "cancel_session":
        return sessions.cancel_session(db, image_store, **arguments)
    elif name == "get_session_history":
        return sessions.get_session_history(db, **arguments)

    # Product lookup
    elif name == "lookup_product":
        return vision.lookup_product(**arguments)

    # Bin image tools
    elif name == "get_bin_images":
        return bins.get_bin_images(db, **arguments)
    elif name == "process_bin_images":
        return _process_bin_images(**arguments)
    elif name == "add_items_bulk":
        return items.add_items_bulk(db, **arguments)

    else:
        return {"error": f"Unknown tool: {name}", "error_code": "NOT_FOUND"}


def main():
    """Run the MCP server."""
    # Run migrations on startup
    logger.info("Running database migrations...")
    db.run_migrations()
    logger.info("Migrations complete.")

    logger.info("Starting Inventory MCP Server...")

    async def run():
        async with stdio_server() as (read_stream, write_stream):
            await server.run(read_stream, write_stream, server.create_initialization_options())

    asyncio.run(run())


if __name__ == "__main__":
    main()
