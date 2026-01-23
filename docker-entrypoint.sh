#!/bin/bash
set -e

# Display startup info
echo "==================================="
echo "Protea Inventory System"
echo "==================================="
echo "Database: ${INVENTORY_DATABASE_PATH}"
echo "Images:   ${INVENTORY_IMAGE_BASE_PATH}"

case "$1" in
    web)
        echo "Mode:     Web UI"
        echo "URL:      http://0.0.0.0:${INVENTORY_WEB_PORT}"
        echo "==================================="
        exec protea-web
        ;;
    mcp)
        echo "Mode:     MCP Server (stdio)"
        echo "==================================="
        exec protea
        ;;
    mcp-sse)
        echo "Mode:     MCP SSE Server"
        echo "URL:      http://0.0.0.0:${INVENTORY_MCP_SSE_PORT}/sse"
        echo "==================================="
        exec protea-sse
        ;;
    both)
        echo "Mode:     Web UI + MCP SSE Server"
        echo "Web URL:  http://0.0.0.0:${INVENTORY_WEB_PORT}"
        echo "SSE URL:  http://0.0.0.0:${INVENTORY_MCP_SSE_PORT}/sse"
        echo "==================================="

        # Trap to handle shutdown - kill background process when main exits
        cleanup() {
            echo "Shutting down..."
            kill $SSE_PID 2>/dev/null || true
            wait $SSE_PID 2>/dev/null || true
            exit 0
        }
        trap cleanup SIGTERM SIGINT

        # Start SSE server in background
        protea-sse &
        SSE_PID=$!

        # Start web server in foreground
        protea-web &
        WEB_PID=$!

        # Wait for either process to exit
        wait -n $SSE_PID $WEB_PID

        # If one exits, kill the other
        cleanup
        ;;
    *)
        # Allow running arbitrary commands
        exec "$@"
        ;;
esac
