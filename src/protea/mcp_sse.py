"""MCP Server with SSE transport for remote connections."""

import logging

import uvicorn
from mcp.server.sse import SseServerTransport
from starlette.applications import Starlette
from starlette.responses import JSONResponse
from starlette.routing import Mount, Route

from protea.config import auth_settings, settings
from protea.server import server, db
from protea.tools import auth as auth_tools

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("protea.sse")


def _bootstrap_admin_user() -> None:
    """Create admin user if no users exist (for SSE server startup)."""
    import sys

    user_count = auth_tools.get_user_count(db)
    if user_count > 0:
        return

    # Generate or use provided password
    password = auth_settings.admin_password
    if not password:
        password = auth_tools.generate_random_password()

    result = auth_tools.create_user(
        db,
        username="admin",
        password=password,
        is_admin=True,
        must_change_password=True,
    )

    if isinstance(result, dict) and "error" in result:
        logger.error(f"Failed to create admin user: {result['error']}")
        return

    # Use print() to ensure this critical message is always visible in logs
    print("=" * 50, file=sys.stderr, flush=True)
    print("FIRST-RUN: Admin user created", file=sys.stderr, flush=True)
    print("Username: admin", file=sys.stderr, flush=True)
    print(f"Password: {password}", file=sys.stderr, flush=True)
    print("=" * 50, file=sys.stderr, flush=True)


def create_sse_app() -> Starlette:
    """Create Starlette app with MCP SSE endpoint."""
    # Create SSE transport
    sse = SseServerTransport("/messages/")

    async def handle_sse(request):
        """Handle SSE connection with API key authentication."""
        # Check if auth is required
        if auth_settings.auth_required:
            # Get Authorization header
            auth_header = request.headers.get("authorization", "")

            if not auth_header.startswith("Bearer "):
                return JSONResponse(
                    {"error": "Missing or invalid Authorization header. Use: Bearer <api_key>"},
                    status_code=401,
                )

            token = auth_header[7:]  # Remove "Bearer " prefix

            # Check legacy single-key mode first
            if auth_settings.api_key and token == auth_settings.api_key:
                logger.debug("Authenticated via legacy PROTEA_API_KEY")
            else:
                # Validate against database API keys
                user = auth_tools.validate_api_key(db, token)
                if not user:
                    return JSONResponse(
                        {"error": "Invalid API key"},
                        status_code=401,
                    )
                logger.debug(f"Authenticated as user: {user.username}")

        try:
            async with sse.connect_sse(request.scope, request.receive, request._send) as streams:
                await server.run(streams[0], streams[1], server.create_initialization_options())
        except Exception as e:
            logger.error(f"SSE connection error: {e}", exc_info=True)
            return JSONResponse(
                {"error": f"SSE connection error: {str(e)}"},
                status_code=500,
            )

    # Health check endpoint (no auth required)
    async def health(request):
        return JSONResponse({"status": "ok", "service": "protea-sse"})

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

    # Bootstrap admin user if needed
    _bootstrap_admin_user()

    if auth_settings.auth_required:
        logger.info("Authentication ENABLED - API key required for connections")
    else:
        logger.info("Authentication DISABLED - all connections allowed")

    logger.info(
        f"Starting MCP SSE Server on http://{settings.mcp_sse_host}:{settings.mcp_sse_port}"
    )

    app = create_sse_app()
    uvicorn.run(
        app,
        host=settings.mcp_sse_host,
        port=settings.mcp_sse_port,
        log_level="info",
        proxy_headers=True,
        forwarded_allow_ips="*",
    )


if __name__ == "__main__":
    main()
