"""MCP Server with SSE transport for remote connections."""

import logging

import uvicorn
from mcp.server.sse import SseServerTransport
from starlette.applications import Starlette
from starlette.routing import Mount, Route

from inventory_mcp.config import settings
from inventory_mcp.db.connection import Database
from inventory_mcp.server import server, db

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("inventory_mcp.sse")


def create_sse_app() -> Starlette:
    """Create Starlette app with MCP SSE endpoint."""
    # Create SSE transport
    sse = SseServerTransport("/messages/")

    async def handle_sse(request):
        """Handle SSE connection."""
        async with sse.connect_sse(
            request.scope, request.receive, request._send
        ) as streams:
            await server.run(
                streams[0], streams[1], server.create_initialization_options()
            )

    # Health check endpoint
    async def health(request):
        from starlette.responses import JSONResponse
        return JSONResponse({"status": "ok", "service": "inventory-mcp-sse"})

    app = Starlette(
        debug=False,
        routes=[
            Route("/health", health),
            Route("/sse", endpoint=handle_sse),
            Mount("/messages/", app=sse.handle_post_message),
        ],
    )

    return app


def main():
    """Run the MCP SSE server."""
    # Run migrations on startup
    logger.info("Running database migrations...")
    db.run_migrations()
    logger.info("Migrations complete.")

    logger.info(
        f"Starting MCP SSE Server on http://{settings.mcp_sse_host}:{settings.mcp_sse_port}"
    )

    app = create_sse_app()
    uvicorn.run(
        app,
        host=settings.mcp_sse_host,
        port=settings.mcp_sse_port,
        log_level="info",
    )


if __name__ == "__main__":
    main()
