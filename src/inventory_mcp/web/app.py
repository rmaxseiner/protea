"""FastAPI application factory for Inventory Web UI."""

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from inventory_mcp import __version__
from inventory_mcp.config import settings
from inventory_mcp.db.connection import Database
from inventory_mcp.services.image_store import ImageStore


# Template directory
WEB_DIR = Path(__file__).parent
TEMPLATES_DIR = WEB_DIR / "templates"
STATIC_DIR = WEB_DIR / "static"

# Global templates instance
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))
templates.env.globals["app_version"] = __version__


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan - initialize shared resources."""
    # Initialize database
    db = Database(settings.database_path)
    db.run_migrations()
    app.state.db = db

    # Initialize image store
    app.state.image_store = ImageStore(
        settings.image_base_path,
        settings.image_format,
        settings.image_quality,
        settings.thumbnail_size,
    )

    yield

    # Cleanup (if needed)


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    app = FastAPI(
        title="Inventory Web UI",
        description="Web interface for inventory management",
        version="1.0.0",
        lifespan=lifespan,
    )

    # Mount static files
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

    # Register routes
    from inventory_mcp.web.routes import images, pages, partials

    app.include_router(pages.router)
    app.include_router(partials.router, prefix="/partials")
    app.include_router(images.router, prefix="/images")

    return app
