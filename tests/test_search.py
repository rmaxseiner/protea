"""Tests for search tools."""


from protea.tools import items, search


def test_search_items_by_name(test_db, sample_bin):
    """Test searching items by name."""
    items.add_item(
        db=test_db,
        name="Phillips Head Screws",
        bin_id=sample_bin.id,
    )

    results = search.search_items(test_db, "Phillips")
    assert len(results) >= 1
    assert any("Phillips" in r.item.name for r in results)


def test_search_items_partial(test_db, sample_bin):
    """Test searching with partial terms."""
    items.add_item(
        db=test_db,
        name="Flathead Screwdriver",
        bin_id=sample_bin.id,
    )

    results = search.search_items(test_db, "Flat")
    assert len(results) >= 1


def test_search_items_by_description(test_db, sample_bin):
    """Test searching items by description."""
    items.add_item(
        db=test_db,
        name="Generic Part",
        bin_id=sample_bin.id,
        description="Stainless steel connector bolt",
    )

    results = search.search_items(test_db, "stainless")
    assert len(results) >= 1


def test_search_items_by_alias(test_db, sample_bin):
    """Test searching items by alias."""
    from protea.tools import aliases

    item = items.add_item(
        db=test_db,
        name="Allen Key Set",
        bin_id=sample_bin.id,
    )

    aliases.add_alias(test_db, item.id, "hex wrench")

    results = search.search_items(test_db, "hex")
    assert len(results) >= 1
    assert any(r.item.id == item.id for r in results)


def test_search_items_no_results(test_db):
    """Test searching with no matches."""
    results = search.search_items(test_db, "xyznonexistent123")
    assert len(results) == 0


def test_search_items_filter_by_location(test_db, sample_bin, sample_location):
    """Test searching with location filter."""
    items.add_item(
        db=test_db,
        name="Location Filter Test",
        bin_id=sample_bin.id,
    )

    results = search.search_items(
        test_db,
        "Location Filter",
        location_id=sample_location.id,
    )
    assert len(results) >= 1
    assert all(r.location.id == sample_location.id for r in results)


def test_find_item(test_db, sample_bin):
    """Test find_item convenience function."""
    items.add_item(
        db=test_db,
        name="Findable Widget",
        bin_id=sample_bin.id,
    )

    results = search.find_item(test_db, "Widget")
    assert len(results) >= 1


def test_list_items(test_db, sample_bin):
    """Test listing all items."""
    items.add_item(db=test_db, name="List Test 1", bin_id=sample_bin.id)
    items.add_item(db=test_db, name="List Test 2", bin_id=sample_bin.id)

    results = search.list_items(test_db)
    assert len(results) >= 2


def test_list_items_by_bin(test_db, sample_bin):
    """Test listing items filtered by bin."""
    items.add_item(db=test_db, name="Bin Filter Test", bin_id=sample_bin.id)

    results = search.list_items(test_db, bin_id=sample_bin.id)
    assert all(item.bin_id == sample_bin.id for item in results)


def test_list_items_by_category(test_db, sample_bin, sample_category):
    """Test listing items filtered by category."""
    items.add_item(
        db=test_db,
        name="Category Filter Test",
        bin_id=sample_bin.id,
        category_id=sample_category.id,
    )

    results = search.list_items(test_db, category_id=sample_category.id)
    assert all(item.category_id == sample_category.id for item in results)


def test_get_item_history(test_db, sample_bin):
    """Test getting item activity history."""
    item = items.add_item(
        db=test_db,
        name="History Test",
        bin_id=sample_bin.id,
        quantity_type="exact",
        quantity_value=100,
    )

    # Use some items to create history
    items.use_item(test_db, item.id, quantity=10)

    history = search.get_item_history(test_db, item.id)
    assert len(history) >= 2  # ADD + USE
