"""Tests for bin tools."""

import pytest

from inventory_mcp.tools import bins


def test_create_bin(test_db, sample_location):
    """Test creating a bin."""
    result = bins.create_bin(
        db=test_db,
        name="Hardware Bin",
        location_id=sample_location.id,
        description="Small parts",
    )
    assert result.name == "Hardware Bin"
    assert result.location_id == sample_location.id
    assert result.id is not None


def test_get_bins(test_db, sample_bin):
    """Test listing bins."""
    result = bins.get_bins(test_db)
    assert len(result) >= 1
    assert any(b.id == sample_bin.id for b in result)


def test_get_bins_by_location(test_db, sample_bin):
    """Test listing bins filtered by location."""
    result = bins.get_bins(test_db, location_id=sample_bin.location_id)
    assert len(result) >= 1
    assert all(b.location_id == sample_bin.location_id for b in result)


def test_get_bin(test_db, sample_bin):
    """Test getting a single bin."""
    result = bins.get_bin(test_db, bin_id=sample_bin.id)
    assert result.id == sample_bin.id
    assert result.name == sample_bin.name


def test_get_bin_not_found(test_db):
    """Test getting a non-existent bin."""
    result = bins.get_bin(test_db, bin_id="nonexistent-uuid")
    assert "error" in result
    assert result["error_code"] == "NOT_FOUND"


def test_update_bin(test_db, sample_bin):
    """Test updating a bin."""
    result = bins.update_bin(
        db=test_db,
        bin_id=sample_bin.id,
        name="Updated Bin",
    )
    assert result.name == "Updated Bin"


def test_delete_bin(test_db, sample_location):
    """Test deleting a bin."""
    # Create a bin to delete
    bin_obj = bins.create_bin(
        db=test_db,
        name="To Delete",
        location_id=sample_location.id,
    )

    result = bins.delete_bin(test_db, bin_obj.id)
    assert result["success"] is True

    # Verify it's gone
    get_result = bins.get_bin(test_db, bin_id=bin_obj.id)
    assert "error" in get_result


def test_create_bin_invalid_location(test_db):
    """Test creating a bin with invalid location fails."""
    result = bins.create_bin(
        db=test_db,
        name="Bad Bin",
        location_id="nonexistent-uuid",
    )
    assert "error" in result
    assert result["error_code"] == "NOT_FOUND"


def test_create_duplicate_bin(test_db, sample_bin):
    """Test creating a bin with duplicate name in same location fails."""
    result = bins.create_bin(
        db=test_db,
        name=sample_bin.name,
        location_id=sample_bin.location_id,
    )
    assert "error" in result
    assert result["error_code"] == "ALREADY_EXISTS"
