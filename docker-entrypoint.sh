#!/bin/bash
set -e

# Display startup info
echo "==================================="
echo "Inventory MCP Server"
echo "==================================="
echo "Database: ${INVENTORY_DATABASE_PATH}"
echo "Images:   ${INVENTORY_IMAGE_BASE_PATH}"

case "$1" in
    web)
        echo "Mode:     Web UI"
        echo "URL:      http://0.0.0.0:${INVENTORY_WEB_PORT}"
        echo "==================================="
        exec inventory-web
        ;;
    mcp)
        echo "Mode:     MCP Server (stdio)"
        echo "==================================="
        exec inventory-mcp
        ;;
    mcp-sse)
        echo "Mode:     MCP SSE Server"
        echo "URL:      http://0.0.0.0:${INVENTORY_MCP_SSE_PORT}/sse"
        echo "==================================="
        exec inventory-mcp-sse
        ;;
    *)
        # Allow running arbitrary commands
        exec "$@"
        ;;
esac
