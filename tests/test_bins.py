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


# --- Nested Bins Tests ---


def test_create_nested_bin(test_db, sample_location):
    """Test creating a nested bin inside another bin."""
    # Create parent bin
    parent = bins.create_bin(
        db=test_db,
        name="Tool Chest",
        location_id=sample_location.id,
    )
    assert parent.id is not None

    # Create nested bin
    child = bins.create_bin(
        db=test_db,
        name="Drawer 1",
        location_id=sample_location.id,
        parent_bin_id=parent.id,
    )
    assert child.name == "Drawer 1"
    assert child.parent_bin_id == parent.id
    assert child.location_id == sample_location.id


def test_create_deeply_nested_bin(test_db, sample_location):
    """Test creating deeply nested bins (3 levels)."""
    level1 = bins.create_bin(db=test_db, name="Cabinet", location_id=sample_location.id)
    level2 = bins.create_bin(
        db=test_db,
        name="Shelf",
        location_id=sample_location.id,
        parent_bin_id=level1.id,
    )
    level3 = bins.create_bin(
        db=test_db,
        name="Box",
        location_id=sample_location.id,
        parent_bin_id=level2.id,
    )

    assert level3.parent_bin_id == level2.id

    # Get the deepest bin and check hierarchy
    result = bins.get_bin(test_db, bin_id=level3.id)
    assert result.parent_bin is not None
    assert result.parent_bin.id == level2.id
    assert len(result.path) == 2  # ["Cabinet", "Shelf"]
    assert result.path[0] == "Cabinet"
    assert result.path[1] == "Shelf"


def test_duplicate_name_allowed_in_different_parents(test_db, sample_location):
    """Test that same name is allowed in different parent bins."""
    parent1 = bins.create_bin(db=test_db, name="Parent1", location_id=sample_location.id)
    parent2 = bins.create_bin(db=test_db, name="Parent2", location_id=sample_location.id)

    # Create "Drawer" in both parents - should succeed
    child1 = bins.create_bin(
        db=test_db,
        name="Drawer",
        location_id=sample_location.id,
        parent_bin_id=parent1.id,
    )
    child2 = bins.create_bin(
        db=test_db,
        name="Drawer",
        location_id=sample_location.id,
        parent_bin_id=parent2.id,
    )

    assert child1.id != child2.id
    assert child1.name == child2.name


def test_duplicate_name_blocked_in_same_parent(test_db, sample_location):
    """Test that same name is blocked in same parent bin."""
    parent = bins.create_bin(db=test_db, name="Parent", location_id=sample_location.id)

    bins.create_bin(
        db=test_db,
        name="Drawer",
        location_id=sample_location.id,
        parent_bin_id=parent.id,
    )

    # Try to create duplicate
    result = bins.create_bin(
        db=test_db,
        name="Drawer",
        location_id=sample_location.id,
        parent_bin_id=parent.id,
    )
    assert "error" in result
    assert result["error_code"] == "ALREADY_EXISTS"


def test_get_bin_tree(test_db, sample_location):
    """Test getting bin tree structure."""
    # Create hierarchy
    root = bins.create_bin(db=test_db, name="Root Bin", location_id=sample_location.id)
    child1 = bins.create_bin(
        db=test_db,
        name="Child 1",
        location_id=sample_location.id,
        parent_bin_id=root.id,
    )
    child2 = bins.create_bin(
        db=test_db,
        name="Child 2",
        location_id=sample_location.id,
        parent_bin_id=root.id,
    )

    result = bins.get_bin_tree(test_db, location_id=sample_location.id)
    assert "bins" in result
    assert len(result["bins"]) >= 1

    # Find our root bin in the tree
    root_node = next((b for b in result["bins"] if b["id"] == root.id), None)
    assert root_node is not None
    assert root_node["child_count"] == 2
    assert len(root_node["children"]) == 2


def test_get_bin_by_path(test_db, sample_location):
    """Test resolving bin by path."""
    # Create hierarchy
    chest = bins.create_bin(db=test_db, name="Tool Chest", location_id=sample_location.id)
    drawer = bins.create_bin(
        db=test_db,
        name="Drawer 9",
        location_id=sample_location.id,
        parent_bin_id=chest.id,
    )

    # Resolve by full path (including location)
    result = bins.get_bin_by_path(
        test_db,
        path=f"{sample_location.name}/Tool Chest/Drawer 9",
    )
    assert result.id == drawer.id
    assert result.name == "Drawer 9"


def test_get_bin_by_path_with_location_name(test_db, sample_location):
    """Test resolving bin by path with explicit location name."""
    chest = bins.create_bin(db=test_db, name="Chest A", location_id=sample_location.id)

    result = bins.get_bin_by_path(
        test_db,
        path="Chest A",
        location_name=sample_location.name,
    )
    assert result.id == chest.id


def test_get_bin_by_path_not_found(test_db, sample_location):
    """Test path resolution with non-existent segment."""
    bins.create_bin(db=test_db, name="Exists", location_id=sample_location.id)

    result = bins.get_bin_by_path(
        test_db,
        path=f"{sample_location.name}/Exists/DoesNotExist",
    )
    assert "error" in result
    assert result["error_code"] == "NOT_FOUND"


def test_get_bins_root_only(test_db, sample_location):
    """Test listing only root-level bins."""
    root = bins.create_bin(db=test_db, name="Root Only", location_id=sample_location.id)
    bins.create_bin(
        db=test_db,
        name="Nested Only",
        location_id=sample_location.id,
        parent_bin_id=root.id,
    )

    result = bins.get_bins(test_db, location_id=sample_location.id, root_only=True)

    # Should include root but not nested
    root_ids = [b.id for b in result]
    assert root.id in root_ids
    # All results should have no parent
    assert all(b.parent_bin_id is None for b in result)


def test_get_bins_by_parent(test_db, sample_location):
    """Test listing bins by parent."""
    parent = bins.create_bin(db=test_db, name="Parent Bin", location_id=sample_location.id)
    child1 = bins.create_bin(
        db=test_db,
        name="Child A",
        location_id=sample_location.id,
        parent_bin_id=parent.id,
    )
    child2 = bins.create_bin(
        db=test_db,
        name="Child B",
        location_id=sample_location.id,
        parent_bin_id=parent.id,
    )

    result = bins.get_bins(test_db, parent_bin_id=parent.id)
    assert len(result) == 2
    child_ids = [b.id for b in result]
    assert child1.id in child_ids
    assert child2.id in child_ids


def test_delete_bin_with_children_fails(test_db, sample_location):
    """Test that deleting a bin with children fails."""
    parent = bins.create_bin(db=test_db, name="Parent To Delete", location_id=sample_location.id)
    bins.create_bin(
        db=test_db,
        name="Child Blocking",
        location_id=sample_location.id,
        parent_bin_id=parent.id,
    )

    result = bins.delete_bin(test_db, parent.id)
    assert result["success"] is False
    assert result["error_code"] == "HAS_CHILDREN"


def test_update_bin_parent(test_db, sample_location):
    """Test moving a bin to a different parent."""
    parent1 = bins.create_bin(db=test_db, name="Parent One", location_id=sample_location.id)
    parent2 = bins.create_bin(db=test_db, name="Parent Two", location_id=sample_location.id)
    child = bins.create_bin(
        db=test_db,
        name="Movable Child",
        location_id=sample_location.id,
        parent_bin_id=parent1.id,
    )

    # Move child to parent2
    result = bins.update_bin(test_db, bin_id=child.id, parent_bin_id=parent2.id)
    assert result.parent_bin_id == parent2.id


def test_update_bin_move_to_root(test_db, sample_location):
    """Test moving a nested bin to root level."""
    parent = bins.create_bin(db=test_db, name="Former Parent", location_id=sample_location.id)
    child = bins.create_bin(
        db=test_db,
        name="Soon Root",
        location_id=sample_location.id,
        parent_bin_id=parent.id,
    )

    # Move to root by passing empty string
    result = bins.update_bin(test_db, bin_id=child.id, parent_bin_id="")
    assert result.parent_bin_id is None


def test_circular_reference_self_parent(test_db, sample_location):
    """Test that a bin cannot be its own parent."""
    bin_obj = bins.create_bin(db=test_db, name="Self Loop", location_id=sample_location.id)

    result = bins.update_bin(test_db, bin_id=bin_obj.id, parent_bin_id=bin_obj.id)
    assert "error" in result
    assert result["error_code"] == "CIRCULAR_REFERENCE"


def test_circular_reference_descendant(test_db, sample_location):
    """Test that a bin cannot be moved into its own descendant."""
    grandparent = bins.create_bin(db=test_db, name="Grandparent", location_id=sample_location.id)
    parent = bins.create_bin(
        db=test_db,
        name="Parent",
        location_id=sample_location.id,
        parent_bin_id=grandparent.id,
    )
    child = bins.create_bin(
        db=test_db,
        name="Child",
        location_id=sample_location.id,
        parent_bin_id=parent.id,
    )

    # Try to make grandparent a child of child (would create circular reference)
    result = bins.update_bin(test_db, bin_id=grandparent.id, parent_bin_id=child.id)
    assert "error" in result
    assert result["error_code"] == "CIRCULAR_REFERENCE"


def test_get_bin_full_path(test_db, sample_location):
    """Test that get_bin returns full_path correctly."""
    chest = bins.create_bin(db=test_db, name="Big Chest", location_id=sample_location.id)
    drawer = bins.create_bin(
        db=test_db,
        name="Small Drawer",
        location_id=sample_location.id,
        parent_bin_id=chest.id,
    )

    result = bins.get_bin(test_db, bin_id=drawer.id)
    expected_path = f"{sample_location.name}/Big Chest/Small Drawer"
    assert result.full_path == expected_path
