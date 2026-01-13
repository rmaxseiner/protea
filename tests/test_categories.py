"""Tests for category tools."""

import pytest

from inventory_mcp.tools import categories


def test_get_categories(test_db):
    """Test listing categories (includes seeded categories)."""
    result = categories.get_categories(test_db)
    # Should have seeded categories
    assert len(result) > 0

    # Check for some expected seeded categories
    names = [c.name for c in result]
    assert "Hardware" in names
    assert "Tools" in names


def test_get_category(test_db, sample_category):
    """Test getting a single category."""
    result = categories.get_category(test_db, sample_category.id)
    assert result.id == sample_category.id
    assert result.name == sample_category.name


def test_get_category_not_found(test_db):
    """Test getting a non-existent category."""
    result = categories.get_category(test_db, "nonexistent-uuid")
    assert "error" in result
    assert result["error_code"] == "NOT_FOUND"


def test_create_category(test_db):
    """Test creating a category."""
    result = categories.create_category(
        db=test_db,
        name="Custom Category",
    )
    assert result.name == "Custom Category"


def test_create_child_category(test_db, sample_category):
    """Test creating a child category."""
    result = categories.create_category(
        db=test_db,
        name="Child Category",
        parent_id=sample_category.id,
    )
    assert result.parent_id == sample_category.id


def test_update_category(test_db, sample_category):
    """Test updating a category."""
    result = categories.update_category(
        db=test_db,
        category_id=sample_category.id,
        name="Updated Category",
    )
    assert result.name == "Updated Category"


def test_delete_category(test_db):
    """Test deleting a category."""
    cat = categories.create_category(db=test_db, name="To Delete")

    result = categories.delete_category(test_db, cat.id)
    assert result["success"] is True

    # Verify it's gone
    get_result = categories.get_category(test_db, cat.id)
    assert "error" in get_result


def test_delete_category_with_items(test_db, sample_bin, sample_category):
    """Test that deleting a category with items fails."""
    from inventory_mcp.tools import items

    items.add_item(
        db=test_db,
        name="Categorized Item",
        bin_id=sample_bin.id,
        category_id=sample_category.id,
    )

    result = categories.delete_category(test_db, sample_category.id)
    assert "error" in result
    assert result["error_code"] == "HAS_DEPENDENCIES"


def test_delete_category_cascades_empty_children(test_db):
    """Test that deleting a category cascades to empty children."""
    parent = categories.create_category(db=test_db, name="Parent")
    child = categories.create_category(db=test_db, name="Child", parent_id=parent.id)

    result = categories.delete_category(test_db, parent.id)
    assert result["success"] is True

    # Child should also be deleted
    child_result = categories.get_category(test_db, child.id)
    assert "error" in child_result


def test_create_duplicate_category(test_db, sample_category):
    """Test creating a category with duplicate name fails."""
    result = categories.create_category(
        db=test_db,
        name=sample_category.name,
    )
    assert "error" in result
    assert result["error_code"] == "ALREADY_EXISTS"
