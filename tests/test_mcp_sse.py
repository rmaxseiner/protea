"""Tests for MCP SSE transport server."""

import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest
from starlette.testclient import TestClient

from protea.config import Settings
from protea.db.connection import Database


@pytest.fixture
def sse_settings():
    """Create test settings for SSE tests."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmppath = Path(tmpdir)
        yield Settings(
            database_path=tmppath / "test.db",
            image_base_path=tmppath / "images",
            mcp_sse_host="127.0.0.1",
            mcp_sse_port=8081,
        )


@pytest.fixture
def sse_db(sse_settings):
    """Create test database for SSE tests."""
    db = Database(sse_settings.database_path)
    db.run_migrations()
    return db


class TestCreateSseApp:
    """Tests for create_sse_app function."""

    def test_creates_starlette_app(self, sse_db):
        """Test that create_sse_app returns a Starlette app."""
        with patch('protea.mcp_sse.db', sse_db):
            from protea.mcp_sse import create_sse_app
            from starlette.applications import Starlette

            app = create_sse_app()

            assert isinstance(app, Starlette)

    def test_app_has_health_route(self, sse_db):
        """Test that the app has a health check route."""
        with patch('protea.mcp_sse.db', sse_db):
            from protea.mcp_sse import create_sse_app

            app = create_sse_app()

            # Check routes exist
            route_paths = [route.path for route in app.routes if hasattr(route, 'path')]
            assert "/health" in route_paths

    def test_app_has_sse_route(self, sse_db):
        """Test that the app has an SSE route."""
        with patch('protea.mcp_sse.db', sse_db):
            from protea.mcp_sse import create_sse_app

            app = create_sse_app()

            route_paths = [route.path for route in app.routes if hasattr(route, 'path')]
            assert "/sse" in route_paths

    def test_app_has_messages_mount(self, sse_db):
        """Test that the app has a messages mount for POST handling."""
        with patch('protea.mcp_sse.db', sse_db):
            from protea.mcp_sse import create_sse_app
            from starlette.routing import Mount

            app = create_sse_app()

            # Find the mount
            mounts = [route for route in app.routes if isinstance(route, Mount)]
            mount_paths = [m.path for m in mounts]
            assert "/messages/" in mount_paths or "/messages" in mount_paths


class TestHealthEndpoint:
    """Tests for the health check endpoint."""

    def test_health_returns_ok(self, sse_db):
        """Test that health endpoint returns OK status."""
        with patch('protea.mcp_sse.db', sse_db):
            from protea.mcp_sse import create_sse_app

            app = create_sse_app()
            client = TestClient(app, raise_server_exceptions=False)

            response = client.get("/health")

            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "ok"
            assert data["service"] == "protea-sse"

    def test_health_returns_json(self, sse_db):
        """Test that health endpoint returns JSON content type."""
        with patch('protea.mcp_sse.db', sse_db):
            from protea.mcp_sse import create_sse_app

            app = create_sse_app()
            client = TestClient(app, raise_server_exceptions=False)

            response = client.get("/health")

            assert "application/json" in response.headers["content-type"]


class TestMainFunction:
    """Tests for the main entry point."""

    def test_main_runs_migrations(self, sse_db, sse_settings):
        """Test that main runs database migrations."""
        mock_uvicorn = MagicMock()

        with patch('protea.mcp_sse.db', sse_db):
            with patch('protea.mcp_sse.settings', sse_settings):
                with patch('protea.mcp_sse.uvicorn', mock_uvicorn):
                    # We need to patch db.run_migrations to track if it was called
                    with patch.object(sse_db, 'run_migrations') as mock_migrations:
                        from protea.mcp_sse import main

                        main()

                        # Migrations should have been called
                        mock_migrations.assert_called_once()

    def test_main_starts_uvicorn(self, sse_db, sse_settings):
        """Test that main starts uvicorn server."""
        mock_uvicorn = MagicMock()

        with patch('protea.mcp_sse.db', sse_db):
            with patch('protea.mcp_sse.settings', sse_settings):
                with patch('protea.mcp_sse.uvicorn', mock_uvicorn):
                    from protea.mcp_sse import main

                    main()

                    # Uvicorn.run should have been called
                    mock_uvicorn.run.assert_called_once()

    def test_main_uses_settings_for_host_port(self, sse_db, sse_settings):
        """Test that main uses settings for host and port."""
        mock_uvicorn = MagicMock()

        with patch('protea.mcp_sse.db', sse_db):
            with patch('protea.mcp_sse.settings', sse_settings):
                with patch('protea.mcp_sse.uvicorn', mock_uvicorn):
                    from protea.mcp_sse import main

                    main()

                    # Check uvicorn was called with correct host/port
                    call_kwargs = mock_uvicorn.run.call_args.kwargs
                    assert call_kwargs["host"] == "127.0.0.1"
                    assert call_kwargs["port"] == 8081
