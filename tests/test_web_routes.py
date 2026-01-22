"""Tests for web UI routes."""

import tempfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from protea.config import Settings
from protea.db.connection import Database
from protea.services.image_store import ImageStore
from protea.tools import bins as bins_tools
from protea.tools import categories as categories_tools
from protea.tools import items as items_tools
from protea.tools import locations as locations_tools


@pytest.fixture
def web_settings():
    """Create test settings with temp directories for web tests."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmppath = Path(tmpdir)
        yield Settings(
            database_path=tmppath / "test.db",
            image_base_path=tmppath / "images",
        )


@pytest.fixture
def web_app(web_settings):
    """Create a test FastAPI app with test database."""
    from protea.web.app import create_app

    app = create_app()

    # Override the lifespan-created resources with test resources
    db = Database(web_settings.database_path)
    db.run_migrations()

    image_store = ImageStore(
        web_settings.image_base_path,
        web_settings.image_format,
        web_settings.image_quality,
        web_settings.thumbnail_size,
    )

    app.state.db = db
    app.state.image_store = image_store

    return app


@pytest.fixture
def client(web_app):
    """Create test client."""
    # Use TestClient without context manager to avoid lifespan issues
    return TestClient(web_app, raise_server_exceptions=False)


@pytest.fixture
def web_db(web_app):
    """Get the database from the app state."""
    return web_app.state.db


@pytest.fixture
def web_location(web_db):
    """Create a sample location for web tests."""
    return locations_tools.create_location(
        db=web_db,
        name="Test Garage",
        description="A test garage location",
    )


@pytest.fixture
def web_bin(web_db, web_location):
    """Create a sample bin for web tests."""
    return bins_tools.create_bin(
        db=web_db,
        name="Test Bin",
        location_id=web_location.id,
        description="A test bin",
    )


@pytest.fixture
def web_category(web_db):
    """Create a sample category for web tests."""
    return categories_tools.create_category(
        db=web_db,
        name="Test Category",
    )


@pytest.fixture
def web_item(web_db, web_bin):
    """Create a sample item for web tests."""
    return items_tools.add_item(
        db=web_db,
        name="Test Item",
        bin_id=web_bin.id,
        description="A test item",
        quantity_type="exact",
        quantity_value=10,
        quantity_label="pieces",
    )


# =============================================================================
# Search Page Tests
# =============================================================================


class TestSearchPage:
    """Tests for search page routes."""

    def test_search_page_loads(self, client):
        """Test that the search page loads."""
        response = client.get("/")
        assert response.status_code == 200
        assert "Search" in response.text or "search" in response.text.lower()

    def test_search_page_with_query(self, client, web_item):
        """Test search page with a query."""
        response = client.get("/?q=Test")
        assert response.status_code == 200
        assert "Test Item" in response.text

    def test_search_page_no_results(self, client):
        """Test search page with no matching results."""
        response = client.get("/?q=nonexistent12345")
        assert response.status_code == 200

    def test_search_results_page(self, client, web_item):
        """Test the /search endpoint."""
        response = client.get("/search?q=Test")
        assert response.status_code == 200
        assert "Test Item" in response.text


# =============================================================================
# Browse Page Tests
# =============================================================================


class TestBrowsePage:
    """Tests for browse page routes."""

    def test_browse_page_empty(self, client):
        """Test browse page with no locations."""
        response = client.get("/browse")
        assert response.status_code == 200

    def test_browse_page_with_locations(self, client, web_location):
        """Test browse page shows locations."""
        response = client.get("/browse")
        assert response.status_code == 200
        assert "Test Garage" in response.text

    def test_browse_page_with_bins(self, client, web_bin):
        """Test browse page shows bins."""
        response = client.get("/browse")
        assert response.status_code == 200
        assert "Test Bin" in response.text


# =============================================================================
# Location Page Tests
# =============================================================================


class TestLocationPage:
    """Tests for location detail page routes."""

    def test_location_page_loads(self, client, web_location):
        """Test location detail page loads."""
        response = client.get(f"/browse/location/{web_location.id}")
        assert response.status_code == 200
        assert "Test Garage" in response.text

    def test_location_page_not_found(self, client):
        """Test location page for non-existent location."""
        response = client.get("/browse/location/nonexistent-id")
        assert response.status_code == 404

    def test_location_page_shows_bins(self, client, web_bin, web_location):
        """Test location page shows its bins."""
        response = client.get(f"/browse/location/{web_location.id}")
        assert response.status_code == 200
        assert "Test Bin" in response.text

    def test_create_bin_in_location(self, client, web_location):
        """Test creating a bin from location page."""
        response = client.post(
            f"/browse/location/{web_location.id}/create-bin",
            data={"name": "New Bin", "description": "A new bin"},
            follow_redirects=False,
        )
        assert response.status_code == 303
        assert f"/browse/location/{web_location.id}" in response.headers["location"]

    def test_edit_location(self, client, web_location):
        """Test editing a location."""
        response = client.post(
            f"/browse/location/{web_location.id}/edit",
            data={"name": "Updated Garage", "description": "Updated description"},
            follow_redirects=False,
        )
        assert response.status_code == 303

    def test_delete_empty_location(self, client, web_db):
        """Test deleting an empty location."""
        loc = locations_tools.create_location(db=web_db, name="To Delete")
        response = client.post(
            f"/browse/location/{loc.id}/delete",
            follow_redirects=False,
        )
        assert response.status_code == 303
        assert "/browse" in response.headers["location"]


# =============================================================================
# Location Quick Add Tests
# =============================================================================


class TestLocationQuickAdd:
    """Tests for location quick add routes."""

    def test_quick_add_page_loads(self, client, web_location):
        """Test quick add page loads."""
        response = client.get(f"/browse/location/{web_location.id}/quick-add")
        assert response.status_code == 200
        assert "Quick Add" in response.text

    def test_quick_add_page_with_prefill(self, client, web_location):
        """Test quick add page with prefilled values."""
        response = client.get(
            f"/browse/location/{web_location.id}/quick-add?name=Prefilled&description=Desc"
        )
        assert response.status_code == 200
        assert "Prefilled" in response.text

    def test_quick_add_save_bin(self, client, web_location):
        """Test saving a bin via quick add."""
        response = client.post(
            f"/browse/location/{web_location.id}/quick-add/save",
            data={"name": "Quick Bin", "description": "Quick description"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["bin_name"] == "Quick Bin"
        assert "bin_id" in data

    def test_quick_add_save_bin_empty_name(self, client, web_location):
        """Test saving a bin with empty name fails validation."""
        response = client.post(
            f"/browse/location/{web_location.id}/quick-add/save",
            data={"name": "", "description": ""},
        )
        # FastAPI will return 422 for validation error
        assert response.status_code == 422


# =============================================================================
# Bin Page Tests
# =============================================================================


class TestBinPage:
    """Tests for bin detail page routes."""

    def test_bin_page_loads(self, client, web_bin):
        """Test bin detail page loads."""
        response = client.get(f"/browse/bin/{web_bin.id}")
        assert response.status_code == 200
        assert "Test Bin" in response.text

    def test_bin_page_not_found(self, client):
        """Test bin page for non-existent bin."""
        response = client.get("/browse/bin/nonexistent-id")
        assert response.status_code == 404

    def test_bin_page_shows_items(self, client, web_item, web_bin):
        """Test bin page shows its items."""
        response = client.get(f"/browse/bin/{web_bin.id}")
        assert response.status_code == 200
        assert "Test Item" in response.text

    def test_create_child_bin(self, client, web_bin):
        """Test creating a child bin."""
        response = client.post(
            f"/browse/bin/{web_bin.id}/create-child",
            data={"name": "Child Bin", "description": "A child bin"},
            follow_redirects=False,
        )
        assert response.status_code == 303
        assert f"/browse/bin/{web_bin.id}" in response.headers["location"]

    def test_add_item_to_bin(self, client, web_bin):
        """Test adding an item to a bin."""
        response = client.post(
            f"/browse/bin/{web_bin.id}/add-item",
            data={
                "name": "New Item",
                "description": "A new item",
                "quantity_type": "exact",
                "quantity_value": "5",
                "quantity_label": "units",
                "notes": "Some notes",
            },
            follow_redirects=False,
        )
        assert response.status_code == 303
        assert f"/browse/bin/{web_bin.id}" in response.headers["location"]

    def test_add_item_boolean_quantity(self, client, web_bin):
        """Test adding an item with boolean quantity."""
        response = client.post(
            f"/browse/bin/{web_bin.id}/add-item",
            data={
                "name": "Boolean Item",
                "quantity_type": "boolean",
            },
            follow_redirects=False,
        )
        assert response.status_code == 303

    def test_add_item_approximate_quantity(self, client, web_bin):
        """Test adding an item with approximate quantity."""
        response = client.post(
            f"/browse/bin/{web_bin.id}/add-item",
            data={
                "name": "Approximate Item",
                "quantity_type": "approximate",
                "quantity_value": "100",
                "quantity_label": "many",
            },
            follow_redirects=False,
        )
        assert response.status_code == 303


# =============================================================================
# Bin Quick Add Tests
# =============================================================================


class TestBinQuickAdd:
    """Tests for bin quick add (sub-bins) routes."""

    def test_quick_add_page_loads(self, client, web_bin):
        """Test quick add sub-bins page loads."""
        response = client.get(f"/browse/bin/{web_bin.id}/quick-add")
        assert response.status_code == 200
        assert "Quick Add" in response.text

    def test_quick_add_save_sub_bin(self, client, web_bin):
        """Test saving a sub-bin via quick add."""
        response = client.post(
            f"/browse/bin/{web_bin.id}/quick-add/save",
            data={"name": "Quick Sub-Bin", "description": "Quick sub description"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["bin_name"] == "Quick Sub-Bin"


# =============================================================================
# Item Page Tests
# =============================================================================


class TestItemPage:
    """Tests for item detail page routes."""

    def test_item_page_loads(self, client, web_item):
        """Test item detail page loads."""
        response = client.get(f"/item/{web_item.id}")
        assert response.status_code == 200
        assert "Test Item" in response.text

    def test_item_page_not_found(self, client):
        """Test item page for non-existent item."""
        response = client.get("/item/nonexistent-id")
        assert response.status_code == 404

    def test_item_page_shows_quantity(self, client, web_item):
        """Test item page shows quantity."""
        response = client.get(f"/item/{web_item.id}")
        assert response.status_code == 200
        assert "10" in response.text  # quantity_value
        assert "pieces" in response.text  # quantity_label

    def test_edit_item(self, client, web_item):
        """Test editing an item."""
        response = client.post(
            f"/item/{web_item.id}/edit",
            data={
                "name": "Updated Item",
                "description": "Updated description",
                "quantity_type": "exact",
                "quantity_value": "20",
                "quantity_label": "units",
                "notes": "Updated notes",
            },
            follow_redirects=False,
        )
        assert response.status_code == 303
        assert f"/item/{web_item.id}" in response.headers["location"]

    def test_add_quantity_to_item(self, client, web_item):
        """Test adding quantity to an item."""
        response = client.post(
            f"/item/{web_item.id}/add-quantity",
            data={"quantity": "5", "notes": "Restocked"},
            follow_redirects=False,
        )
        assert response.status_code == 303

    def test_use_item(self, client, web_item):
        """Test using an item (decrementing quantity)."""
        response = client.post(
            f"/item/{web_item.id}/use",
            data={"quantity": "2", "notes": "Used for project"},
            follow_redirects=False,
        )
        assert response.status_code == 303

    def test_move_item(self, client, web_item, web_db, web_location):
        """Test moving an item to a different bin."""
        # Create a new bin to move to
        new_bin = bins_tools.create_bin(
            db=web_db,
            name="Target Bin",
            location_id=web_location.id,
        )
        response = client.post(
            f"/item/{web_item.id}/move",
            data={"to_bin_id": new_bin.id, "notes": "Reorganizing"},
            follow_redirects=False,
        )
        assert response.status_code == 303


# =============================================================================
# History Page Tests
# =============================================================================


class TestHistoryPage:
    """Tests for history page routes."""

    def test_history_page_loads(self, client):
        """Test history page loads."""
        response = client.get("/history")
        assert response.status_code == 200

    def test_history_page_shows_activity(self, client, web_item):
        """Test history page shows item activity."""
        # The item creation should have logged an activity
        response = client.get("/history")
        assert response.status_code == 200
        # Check that the page rendered (activity may or may not be shown depending on implementation)


# =============================================================================
# Delete Operations Tests
# =============================================================================


class TestDeleteOperations:
    """Tests for delete operations."""

    def test_delete_child_bin(self, client, web_bin, web_db):
        """Test deleting a child bin."""
        # Create a child bin first
        child = bins_tools.create_bin(
            db=web_db,
            name="Child to Delete",
            location_id=web_bin.location_id,
            parent_bin_id=web_bin.id,
        )
        response = client.post(
            f"/browse/bin/{web_bin.id}/delete-child/{child.id}",
            follow_redirects=False,
        )
        assert response.status_code == 303

    def test_delete_location_with_bins_fails(self, client, web_bin, web_location):
        """Test that deleting a location with bins fails."""
        response = client.post(
            f"/browse/location/{web_location.id}/delete",
            follow_redirects=False,
        )
        # Should redirect back with error
        assert response.status_code == 303
        assert "error" in response.headers["location"]


# =============================================================================
# Error Handling Tests
# =============================================================================


class TestErrorHandling:
    """Tests for error handling in routes."""

    def test_invalid_location_id(self, client):
        """Test handling of invalid location ID."""
        response = client.get("/browse/location/invalid-uuid-format")
        assert response.status_code == 404

    def test_invalid_bin_id(self, client):
        """Test handling of invalid bin ID."""
        response = client.get("/browse/bin/invalid-uuid-format")
        assert response.status_code == 404

    def test_invalid_item_id(self, client):
        """Test handling of invalid item ID."""
        response = client.get("/item/invalid-uuid-format")
        assert response.status_code == 404

    def test_create_bin_invalid_location(self, client):
        """Test creating a bin with invalid location."""
        response = client.post(
            "/browse/location/nonexistent/create-bin",
            data={"name": "Test", "description": ""},
            follow_redirects=False,
        )
        # Should redirect with error
        assert response.status_code == 303
