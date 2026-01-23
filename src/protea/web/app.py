"""FastAPI application factory for Inventory Web UI."""

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from protea import __version__
from protea.config import settings
from protea.db.connection import Database
from protea.services.image_store import ImageStore

logger = logging.getLogger("protea.web")

# Template directory
WEB_DIR = Path(__file__).parent
TEMPLATES_DIR = WEB_DIR / "templates"
STATIC_DIR = WEB_DIR / "static"

# Global templates instance
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))
templates.env.globals["app_version"] = __version__


def _bootstrap_admin_user(db: Database) -> None:
    """Create admin user if no users exist."""
    import sys
    from protea.config import auth_settings
    from protea.tools import auth as auth_tools

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


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan - initialize shared resources."""
    # Initialize database
    db = Database(settings.database_path)
    db.run_migrations()
    app.state.db = db

    # Bootstrap admin user if needed
    _bootstrap_admin_user(db)

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
    from protea.web.routes import auth, images, pages, partials, settings as settings_routes

    app.include_router(auth.router)
    app.include_router(settings_routes.router)
    app.include_router(pages.router)
    app.include_router(partials.router, prefix="/partials")
    app.include_router(images.router, prefix="/images")

    return app
