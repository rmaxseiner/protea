"""Tests for MCP server routing and serialization."""

import json
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from protea.config import Settings
from protea.db.connection import Database
from protea.db.models import Location, Bin, Item
from protea.services.image_store import ImageStore
from protea.tools import locations as locations_tools
from protea.tools import bins as bins_tools
from protea.tools import items as items_tools
from protea.tools import categories as categories_tools


@pytest.fixture
def mcp_settings():
    """Create test settings for MCP tests."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmppath = Path(tmpdir)
        yield Settings(
            database_path=tmppath / "test.db",
            image_base_path=tmppath / "images",
        )


@pytest.fixture
def mcp_db(mcp_settings):
    """Create test database for MCP tests."""
    db = Database(mcp_settings.database_path)
    db.run_migrations()
    return db


@pytest.fixture
def mcp_image_store(mcp_settings):
    """Create test image store for MCP tests."""
    return ImageStore(
        mcp_settings.image_base_path,
        mcp_settings.image_format,
        mcp_settings.image_quality,
        mcp_settings.thumbnail_size,
    )


@pytest.fixture
def mcp_location(mcp_db):
    """Create a sample location for MCP tests."""
    return locations_tools.create_location(
        db=mcp_db,
        name="MCP Test Location",
        description="Test location for MCP",
    )


@pytest.fixture
def mcp_bin(mcp_db, mcp_location):
    """Create a sample bin for MCP tests."""
    return bins_tools.create_bin(
        db=mcp_db,
        name="MCP Test Bin",
        location_id=mcp_location.id,
        description="Test bin for MCP",
    )


@pytest.fixture
def mcp_item(mcp_db, mcp_bin):
    """Create a sample item for MCP tests."""
    return items_tools.add_item(
        db=mcp_db,
        name="MCP Test Item",
        bin_id=mcp_bin.id,
        quantity_type="exact",
        quantity_value=5,
    )


# =============================================================================
# Serialization Tests
# =============================================================================


class TestSerializeResult:
    """Tests for _serialize_result function."""

    def test_serialize_pydantic_model(self, mcp_location):
        """Test serializing a Pydantic model."""
        from protea.server import _serialize_result

        result = _serialize_result(mcp_location)
        parsed = json.loads(result)

        assert parsed["name"] == "MCP Test Location"
        assert "id" in parsed

    def test_serialize_list_of_models(self, mcp_db, mcp_location):
        """Test serializing a list of Pydantic models."""
        from protea.server import _serialize_result

        locations = locations_tools.get_locations(mcp_db)
        result = _serialize_result(locations)
        parsed = json.loads(result)

        assert isinstance(parsed, list)
        assert len(parsed) >= 1
        assert parsed[0]["name"] == "MCP Test Location"

    def test_serialize_dict(self):
        """Test serializing a plain dict."""
        from protea.server import _serialize_result

        data = {"error": "Test error", "code": 123}
        result = _serialize_result(data)
        parsed = json.loads(result)

        assert parsed["error"] == "Test error"
        assert parsed["code"] == 123

    def test_serialize_dict_with_datetime(self, mcp_location):
        """Test serializing dict with datetime values."""
        from protea.server import _serialize_result
        from datetime import datetime

        data = {"created": datetime.now(), "name": "test"}
        result = _serialize_result(data)
        parsed = json.loads(result)

        assert "created" in parsed
        assert parsed["name"] == "test"

    def test_serialize_primitive(self):
        """Test serializing primitive values."""
        from protea.server import _serialize_result

        result = _serialize_result("simple string")
        parsed = json.loads(result)

        assert parsed["result"] == "simple string"


# =============================================================================
# Tool Handler Tests
# =============================================================================


class TestHandleTool:
    """Tests for _handle_tool routing function."""

    @pytest.mark.asyncio
    async def test_handle_get_locations(self, mcp_db, mcp_location):
        """Test handling get_locations tool."""
        # We need to patch the global db in server module
        with patch('protea.server.db', mcp_db):
            from protea.server import _handle_tool

            result = await _handle_tool("get_locations", {})

            assert isinstance(result, list)
            assert len(result) >= 1
            assert result[0].name == "MCP Test Location"

    @pytest.mark.asyncio
    async def test_handle_get_location_by_id(self, mcp_db, mcp_location):
        """Test handling get_location tool with ID."""
        with patch('protea.server.db', mcp_db):
            from protea.server import _handle_tool

            result = await _handle_tool("get_location", {"location_id": mcp_location.id})

            assert result.name == "MCP Test Location"

    @pytest.mark.asyncio
    async def test_handle_create_location(self, mcp_db):
        """Test handling create_location tool."""
        with patch('protea.server.db', mcp_db):
            from protea.server import _handle_tool

            result = await _handle_tool("create_location", {
                "name": "New MCP Location",
                "description": "Created via MCP"
            })

            assert result.name == "New MCP Location"

    @pytest.mark.asyncio
    async def test_handle_get_bins(self, mcp_db, mcp_bin):
        """Test handling get_bins tool."""
        with patch('protea.server.db', mcp_db):
            from protea.server import _handle_tool

            result = await _handle_tool("get_bins", {})

            assert isinstance(result, list)
            assert len(result) >= 1

    @pytest.mark.asyncio
    async def test_handle_get_bin(self, mcp_db, mcp_bin):
        """Test handling get_bin tool."""
        with patch('protea.server.db', mcp_db):
            from protea.server import _handle_tool

            result = await _handle_tool("get_bin", {"bin_id": mcp_bin.id})

            assert result.name == "MCP Test Bin"

    @pytest.mark.asyncio
    async def test_handle_create_bin(self, mcp_db, mcp_location):
        """Test handling create_bin tool."""
        with patch('protea.server.db', mcp_db):
            from protea.server import _handle_tool

            result = await _handle_tool("create_bin", {
                "name": "New MCP Bin",
                "location_id": mcp_location.id,
            })

            assert result.name == "New MCP Bin"

    @pytest.mark.asyncio
    async def test_handle_get_item(self, mcp_db, mcp_item):
        """Test handling get_item tool."""
        with patch('protea.server.db', mcp_db):
            from protea.server import _handle_tool

            result = await _handle_tool("get_item", {"item_id": mcp_item.id})

            assert result.name == "MCP Test Item"

    @pytest.mark.asyncio
    async def test_handle_add_item(self, mcp_db, mcp_bin):
        """Test handling add_item tool."""
        with patch('protea.server.db', mcp_db):
            from protea.server import _handle_tool

            result = await _handle_tool("add_item", {
                "name": "New MCP Item",
                "bin_id": mcp_bin.id,
                "quantity_type": "exact",
                "quantity_value": 10,
            })

            assert result.name == "New MCP Item"
            assert result.quantity_value == 10

    @pytest.mark.asyncio
    async def test_handle_search_items(self, mcp_db, mcp_item):
        """Test handling search_items tool."""
        with patch('protea.server.db', mcp_db):
            from protea.server import _handle_tool

            result = await _handle_tool("search_items", {"query": "MCP Test"})

            assert isinstance(result, list)
            assert len(result) >= 1

    @pytest.mark.asyncio
    async def test_handle_unknown_tool(self, mcp_db):
        """Test handling unknown tool returns error."""
        with patch('protea.server.db', mcp_db):
            from protea.server import _handle_tool

            result = await _handle_tool("unknown_tool_xyz", {})

            assert isinstance(result, dict)
            assert "error" in result
            assert result["error_code"] == "NOT_FOUND"

    @pytest.mark.asyncio
    async def test_handle_get_categories(self, mcp_db):
        """Test handling get_categories tool."""
        with patch('protea.server.db', mcp_db):
            from protea.server import _handle_tool

            result = await _handle_tool("get_categories", {})

            assert isinstance(result, list)

    @pytest.mark.asyncio
    async def test_handle_create_category(self, mcp_db):
        """Test handling create_category tool."""
        with patch('protea.server.db', mcp_db):
            from protea.server import _handle_tool

            result = await _handle_tool("create_category", {"name": "MCP Category"})

            assert result.name == "MCP Category"

    @pytest.mark.asyncio
    async def test_handle_get_active_sessions(self, mcp_db):
        """Test handling get_active_sessions tool."""
        with patch('protea.server.db', mcp_db):
            from protea.server import _handle_tool

            result = await _handle_tool("get_active_sessions", {})

            assert isinstance(result, list)

    @pytest.mark.asyncio
    async def test_handle_create_session(self, mcp_db, mcp_bin):
        """Test handling create_session tool."""
        with patch('protea.server.db', mcp_db):
            from protea.server import _handle_tool

            result = await _handle_tool("create_session", {"bin_id": mcp_bin.id})

            assert result.target_bin_id == mcp_bin.id

    @pytest.mark.asyncio
    async def test_handle_lookup_product(self, mcp_db):
        """Test handling lookup_product tool."""
        with patch('protea.server.db', mcp_db):
            from protea.server import _handle_tool

            result = await _handle_tool("lookup_product", {"code": "B0ABC12345"})

            assert result["_stub"] is True
            assert result["code"] == "B0ABC12345"

    @pytest.mark.asyncio
    async def test_handle_get_bin_tree(self, mcp_db, mcp_location, mcp_bin):
        """Test handling get_bin_tree tool."""
        with patch('protea.server.db', mcp_db):
            from protea.server import _handle_tool

            result = await _handle_tool("get_bin_tree", {"location_id": mcp_location.id})

            assert "bins" in result

    @pytest.mark.asyncio
    async def test_handle_list_items(self, mcp_db, mcp_item, mcp_bin):
        """Test handling list_items tool."""
        with patch('protea.server.db', mcp_db):
            from protea.server import _handle_tool

            result = await _handle_tool("list_items", {"bin_id": mcp_bin.id})

            assert isinstance(result, list)


# =============================================================================
# Call Tool Wrapper Tests
# =============================================================================


class TestCallTool:
    """Tests for call_tool async wrapper."""

    @pytest.mark.asyncio
    async def test_call_tool_success(self, mcp_db, mcp_location):
        """Test call_tool returns TextContent on success."""
        with patch('protea.server.db', mcp_db):
            from protea.server import call_tool

            result = await call_tool("get_locations", {})

            assert len(result) == 1
            assert result[0].type == "text"

            # Should be valid JSON
            parsed = json.loads(result[0].text)
            assert isinstance(parsed, list)

    @pytest.mark.asyncio
    async def test_call_tool_unknown_tool(self, mcp_db):
        """Test call_tool handles unknown tool gracefully."""
        with patch('protea.server.db', mcp_db):
            from protea.server import call_tool

            result = await call_tool("nonexistent_tool", {})

            assert len(result) == 1
            parsed = json.loads(result[0].text)
            assert "error" in parsed


# =============================================================================
# List Tools Tests
# =============================================================================


class TestListTools:
    """Tests for list_tools handler."""

    @pytest.mark.asyncio
    async def test_list_tools_returns_all_tools(self):
        """Test that list_tools returns all defined tools."""
        from protea.server import list_tools, TOOLS

        result = await list_tools()

        assert len(result) == len(TOOLS)

        # Check some expected tool names exist
        tool_names = [t.name for t in result]
        assert "get_locations" in tool_names
        assert "get_bins" in tool_names
        assert "search_items" in tool_names
        assert "create_session" in tool_names

    @pytest.mark.asyncio
    async def test_tools_have_valid_schemas(self):
        """Test that all tools have valid input schemas."""
        from protea.server import TOOLS

        for tool in TOOLS:
            assert tool.name is not None
            assert tool.description is not None
            assert tool.inputSchema is not None
            assert "type" in tool.inputSchema
            assert tool.inputSchema["type"] == "object"
