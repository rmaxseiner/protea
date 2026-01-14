"""FastAPI dependency injection for web UI."""

from fastapi import Request

from inventory_mcp.db.connection import Database
from inventory_mcp.services.image_store import ImageStore


def get_db(request: Request) -> Database:
    """Get database instance from app state."""
    return request.app.state.db


def get_image_store(request: Request) -> ImageStore:
    """Get image store instance from app state."""
    return request.app.state.image_store
