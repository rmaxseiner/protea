"""Configuration settings for Inventory MCP Server."""

from pathlib import Path
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # Database
    database_path: Path = Path("data/inventory.db")

    # Image storage
    image_base_path: Path = Path("data/images")
    image_format: str = "webp"
    image_quality: int = 85
    thumbnail_size: tuple[int, int] = (200, 200)
    max_image_size_bytes: int = 10 * 1024 * 1024  # 10MB default

    # Session settings
    session_stale_minutes: int = 30

    # Vision API (optional - for direct extraction)
    claude_api_key: str | None = None
    claude_model: str = "claude-sonnet-4-20250514"

    # Product lookup APIs (optional - stubs for now)
    amazon_product_api_key: str | None = None
    amazon_product_api_secret: str | None = None
    amazon_partner_tag: str | None = None
    upcitemdb_api_key: str | None = None

    model_config = {"env_prefix": "INVENTORY_"}


settings = Settings()
