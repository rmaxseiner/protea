"""Tests for location tools."""

import pytest

from inventory_mcp.tools import locations


def test_create_location(test_db):
    """Test creating a location."""
    result = locations.create_location(
        db=test_db,
        name="Garage",
        description="Main garage",
    )
    assert result.name == "Garage"
    assert result.description == "Main garage"
    assert result.id is not None


def test_get_locations(test_db, sample_location):
    """Test listing locations."""
    result = locations.get_locations(test_db)
    assert len(result) >= 1
    assert any(loc.id == sample_location.id for loc in result)


def test_get_location(test_db, sample_location):
    """Test getting a single location."""
    result = locations.get_location(test_db, location_id=sample_location.id)
    assert result.id == sample_location.id
    assert result.name == sample_location.name


def test_get_location_not_found(test_db):
    """Test getting a non-existent location."""
    result = locations.get_location(test_db, location_id="nonexistent-uuid")
    assert "error" in result
    assert result["error_code"] == "NOT_FOUND"


def test_update_location(test_db, sample_location):
    """Test updating a location."""
    result = locations.update_location(
        db=test_db,
        location_id=sample_location.id,
        name="Updated Name",
    )
    assert result.name == "Updated Name"
    assert result.description == sample_location.description


def test_delete_location(test_db):
    """Test deleting a location."""
    # Create a location to delete
    loc = locations.create_location(db=test_db, name="To Delete")

    result = locations.delete_location(test_db, loc.id)
    assert result["success"] is True

    # Verify it's gone
    get_result = locations.get_location(test_db, location_id=loc.id)
    assert "error" in get_result


def test_delete_location_with_bins(test_db, sample_bin):
    """Test that deleting a location with bins fails."""
    result = locations.delete_location(test_db, sample_bin.location_id)
    assert "error" in result
    assert result["error_code"] == "HAS_DEPENDENCIES"


def test_create_duplicate_location(test_db, sample_location):
    """Test creating a location with duplicate name fails."""
    result = locations.create_location(
        db=test_db,
        name=sample_location.name,
    )
    assert "error" in result
    assert result["error_code"] == "ALREADY_EXISTS"
