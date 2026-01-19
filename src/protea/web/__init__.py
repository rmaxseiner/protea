"""Inventory MCP Web UI module."""

import uvicorn
from protea.config import settings


def main():
    """Run the web UI server."""
    from protea.web.app import create_app

    app = create_app()
    uvicorn.run(
        app,
        host=settings.web_host,
        port=settings.web_port,
        proxy_headers=True,
        forwarded_allow_ips="*",
    )


if __name__ == "__main__":
    main()
