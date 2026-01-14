#!/bin/bash
# Start the inventory-mcp web server

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

export INVENTORY_DATABASE_PATH="${INVENTORY_DATABASE_PATH:-$PROJECT_DIR/data/inventory.db}"
export INVENTORY_IMAGE_BASE_PATH="${INVENTORY_IMAGE_BASE_PATH:-$PROJECT_DIR/data/images}"

echo "Starting inventory-web..."
echo "  Database: $INVENTORY_DATABASE_PATH"
echo "  Images:   $INVENTORY_IMAGE_BASE_PATH"
echo "  URL:      http://localhost:8080"
echo ""

exec "$PROJECT_DIR/.venv/bin/inventory-web"
