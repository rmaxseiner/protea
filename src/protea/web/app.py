"""FastAPI application factory for Inventory Web UI."""

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from protea import __version__
from protea.config import settings
from protea.db.connection import Database
from protea.services.image_store import ImageStore
from protea.tools import admin
from protea.web.security import CSRFMiddleware, get_csrf_token

logger = logging.getLogger("protea.web")

# Template directory
WEB_DIR = Path(__file__).parent
TEMPLATES_DIR = WEB_DIR / "templates"
STATIC_DIR = WEB_DIR / "static"

# Global templates instance
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))
templates.env.globals["app_version"] = __version__


def csrf_token_input(request: Request) -> str:
    """Generate hidden input field with CSRF token for forms."""
    token = get_csrf_token(request)
    return f'<input type="hidden" name="csrf_token" value="{token}">'


# Add CSRF helper to templates
templates.env.globals["csrf_token_input"] = csrf_token_input


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan - initialize shared resources."""
    # Initialize database
    db = Database(settings.database_path)
    db.run_migrations()
    app.state.db = db

    # Bootstrap admin user if needed
    admin.bootstrap_admin_user(db)

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

    # Add CSRF protection middleware
    # Exempt paths: image uploads, partials (htmx fragments)
    app.add_middleware(
        CSRFMiddleware,
        exempt_paths={"/images/", "/partials/"},
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
