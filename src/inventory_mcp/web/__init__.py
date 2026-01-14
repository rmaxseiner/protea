"""Inventory MCP Web UI module."""

import uvicorn
from inventory_mcp.config import settings


def main():
    """Run the web UI server."""
    from inventory_mcp.web.app import create_app

    app = create_app()
    uvicorn.run(
        app,
        host=settings.web_host,
        port=settings.web_port,
    )


if __name__ == "__main__":
    main()
