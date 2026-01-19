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
    max_image_size_bytes: int = 15 * 1024 * 1024  # 15MB default

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

    # Web UI settings
    web_port: int = 8080
    web_host: str = "0.0.0.0"

    # MCP SSE settings
    mcp_sse_port: int = 8081
    mcp_sse_host: str = "0.0.0.0"

    # Embedding/Vector search settings
    embedding_model: str = "all-MiniLM-L6-v2"  # Fast, 384 dimensions
    embedding_dimension: int = 384
    embedding_enabled: bool = True  # Feature flag to disable vector search
    vector_search_weight: float = 0.5  # Weight for vector similarity in hybrid search
    fts_search_weight: float = 0.5  # Weight for FTS score in hybrid search

    model_config = {"env_prefix": "INVENTORY_"}


settings = Settings()
