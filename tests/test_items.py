"""Tests for item tools."""

from protea.db.models import QuantityType
from protea.tools import items


def test_add_item(test_db, sample_bin):
    """Test adding an item."""
    result = items.add_item(
        db=test_db,
        name="M3 Screws",
        bin_id=sample_bin.id,
        quantity_type="exact",
        quantity_value=50,
    )
    assert result.name == "M3 Screws"
    assert result.bin_id == sample_bin.id
    assert result.quantity_type == QuantityType.EXACT
    assert result.quantity_value == 50


def test_add_item_with_category(test_db, sample_bin, sample_category):
    """Test adding an item with category."""
    result = items.add_item(
        db=test_db,
        name="Phillips Screwdriver",
        bin_id=sample_bin.id,
        category_id=sample_category.id,
        quantity_type="boolean",
    )
    assert result.category_id == sample_category.id


def test_get_item(test_db, sample_bin):
    """Test getting an item."""
    item = items.add_item(
        db=test_db,
        name="Test Item",
        bin_id=sample_bin.id,
    )

    result = items.get_item(test_db, item.id)
    assert result.id == item.id
    assert result.name == item.name


def test_get_item_not_found(test_db):
    """Test getting a non-existent item."""
    result = items.get_item(test_db, "nonexistent-uuid")
    assert "error" in result
    assert result["error_code"] == "NOT_FOUND"


def test_update_item(test_db, sample_bin):
    """Test updating an item."""
    item = items.add_item(
        db=test_db,
        name="Original Name",
        bin_id=sample_bin.id,
    )

    result = items.update_item(
        db=test_db,
        item_id=item.id,
        name="Updated Name",
        description="Now with description",
    )
    assert result.name == "Updated Name"
    assert result.description == "Now with description"


def test_remove_item(test_db, sample_bin):
    """Test removing an item."""
    item = items.add_item(
        db=test_db,
        name="To Remove",
        bin_id=sample_bin.id,
    )

    result = items.remove_item(test_db, item.id)
    assert result["success"] is True

    # Verify it's gone
    get_result = items.get_item(test_db, item.id)
    assert "error" in get_result


def test_use_item_exact(test_db, sample_bin):
    """Test using some quantity of an exact item."""
    item = items.add_item(
        db=test_db,
        name="Nuts",
        bin_id=sample_bin.id,
        quantity_type="exact",
        quantity_value=100,
    )

    result = items.use_item(test_db, item.id, quantity=10)
    assert result.quantity_value == 90


def test_use_item_reduces_to_zero(test_db, sample_bin):
    """Test using all quantity reduces to zero (doesn't error)."""
    item = items.add_item(
        db=test_db,
        name="Bolts",
        bin_id=sample_bin.id,
        quantity_type="exact",
        quantity_value=5,
    )

    # Using more than available goes to 0
    result = items.use_item(test_db, item.id, quantity=10)
    assert result.quantity_value == 0


def test_move_item(test_db, sample_location):
    """Test moving an item to another bin."""
    from protea.tools import bins

    bin1 = bins.create_bin(db=test_db, name="Bin 1", location_id=sample_location.id)
    bin2 = bins.create_bin(db=test_db, name="Bin 2", location_id=sample_location.id)

    item = items.add_item(
        db=test_db,
        name="Mobile Item",
        bin_id=bin1.id,
    )

    result = items.move_item(test_db, item.id, bin2.id)
    assert result["moved_item"].bin_id == bin2.id
    assert result["split"] is False


def test_move_item_partial(test_db, sample_location):
    """Test moving partial quantity creates new item."""
    from protea.tools import bins

    bin1 = bins.create_bin(db=test_db, name="Source", location_id=sample_location.id)
    bin2 = bins.create_bin(db=test_db, name="Dest", location_id=sample_location.id)

    item = items.add_item(
        db=test_db,
        name="Splittable",
        bin_id=bin1.id,
        quantity_type="exact",
        quantity_value=100,
    )

    result = items.move_item(test_db, item.id, bin2.id, quantity=30)

    # Result has moved_item in destination
    assert result["moved_item"].bin_id == bin2.id
    assert result["moved_item"].quantity_value == 30
    assert result["split"] is True

    # Original should have 70 remaining
    assert result["source_item"].quantity_value == 70


def test_add_items_bulk(test_db, sample_bin):
    """Test bulk adding items."""
    items_data = [
        {"name": "Item 1", "quantity_type": "boolean"},
        {"name": "Item 2", "quantity_type": "exact", "quantity_value": 10},
    ]

    result = items.add_items_bulk(
        db=test_db,
        items=items_data,
        bin_id=sample_bin.id,
    )

    # Returns list of created items
    assert isinstance(result, list)
    assert len(result) == 2


def test_delete_items_bulk(test_db, sample_bin):
    """Test bulk deleting items."""
    item1 = items.add_item(db=test_db, name="Bulk 1", bin_id=sample_bin.id)
    item2 = items.add_item(db=test_db, name="Bulk 2", bin_id=sample_bin.id)

    result = items.delete_items_bulk(test_db, [item1.id, item2.id])

    assert result["deleted_count"] == 2
    assert result["failed"] == []


def test_move_items_bulk(test_db, sample_location):
    """Test bulk moving items to a different bin."""
    from protea.tools import bins

    bin1 = bins.create_bin(db=test_db, name="Source Bin", location_id=sample_location.id)
    bin2 = bins.create_bin(db=test_db, name="Target Bin", location_id=sample_location.id)

    item1 = items.add_item(db=test_db, name="Bulk Move 1", bin_id=bin1.id)
    item2 = items.add_item(db=test_db, name="Bulk Move 2", bin_id=bin1.id)
    item3 = items.add_item(db=test_db, name="Bulk Move 3", bin_id=bin1.id)

    moves = [
        {"item_id": item1.id, "to_bin_id": bin2.id},
        {"item_id": item2.id, "to_bin_id": bin2.id},
        {"item_id": item3.id, "to_bin_id": bin2.id},
    ]

    result = items.move_items_bulk(test_db, moves)

    assert result["success"] is True
    assert result["moved_count"] == 3
    assert result["failed_count"] == 0

    # Verify items are now in target bin
    moved1 = items.get_item(test_db, item1.id)
    assert moved1.bin_id == bin2.id


def test_move_items_bulk_partial_failure(test_db, sample_location):
    """Test bulk move with some invalid items."""
    from protea.tools import bins

    bin1 = bins.create_bin(db=test_db, name="Source", location_id=sample_location.id)
    bin2 = bins.create_bin(db=test_db, name="Target", location_id=sample_location.id)

    item1 = items.add_item(db=test_db, name="Valid Item", bin_id=bin1.id)

    moves = [
        {"item_id": item1.id, "to_bin_id": bin2.id},
        {"item_id": "nonexistent-id", "to_bin_id": bin2.id},
        {"item_id": item1.id, "to_bin_id": "nonexistent-bin"},
    ]

    result = items.move_items_bulk(test_db, moves)

    assert result["success"] is False
    assert result["moved_count"] == 1
    assert result["failed_count"] == 2


def test_move_items_bulk_empty_list(test_db):
    """Test bulk move with empty list."""
    result = items.move_items_bulk(test_db, [])

    assert result["success"] is True
    assert result["moved_count"] == 0
