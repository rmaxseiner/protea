"""Tests for session workflow tools."""

import pytest

from inventory_mcp.db.models import SessionStatus
from inventory_mcp.tools import sessions


def test_create_session(test_db, sample_bin):
    """Test creating a session."""
    result = sessions.create_session(
        db=test_db,
        bin_id=sample_bin.id,
    )
    assert result.target_bin_id == sample_bin.id
    assert result.status == SessionStatus.PENDING


def test_create_session_with_location(test_db, sample_location):
    """Test creating a session with location target."""
    result = sessions.create_session(
        db=test_db,
        location_id=sample_location.id,
    )
    assert result.target_location_id == sample_location.id


def test_get_session(test_db, sample_bin):
    """Test getting a session."""
    session = sessions.create_session(
        db=test_db,
        bin_id=sample_bin.id,
    )

    result = sessions.get_session(test_db, session.id)
    # get_session returns SessionDetail directly
    assert result.id == session.id


def test_get_session_not_found(test_db):
    """Test getting a non-existent session."""
    result = sessions.get_session(test_db, "nonexistent-uuid")
    assert "error" in result
    assert result["error_code"] == "NOT_FOUND"


def test_add_pending_item(test_db, sample_bin):
    """Test adding a pending item to session."""
    session = sessions.create_session(
        db=test_db,
        bin_id=sample_bin.id,
    )

    result = sessions.add_pending_item(
        db=test_db,
        session_id=session.id,
        name="Pending Screw",
        quantity_type="exact",
        quantity_value=25,
    )
    assert result.name == "Pending Screw"
    assert result.quantity_value == 25


def test_update_pending_item(test_db, sample_bin):
    """Test updating a pending item."""
    session = sessions.create_session(
        db=test_db,
        bin_id=sample_bin.id,
    )

    item = sessions.add_pending_item(
        db=test_db,
        session_id=session.id,
        name="Original Name",
    )

    result = sessions.update_pending_item(
        db=test_db,
        session_id=session.id,
        pending_id=item.id,
        name="Updated Name",
    )
    assert result.name == "Updated Name"


def test_remove_pending_item(test_db, sample_bin):
    """Test removing a pending item."""
    session = sessions.create_session(
        db=test_db,
        bin_id=sample_bin.id,
    )

    item = sessions.add_pending_item(
        db=test_db,
        session_id=session.id,
        name="To Remove",
    )

    result = sessions.remove_pending_item(test_db, session.id, item.id)
    assert result["success"] is True


def test_commit_session(test_db, sample_bin, test_image_store):
    """Test committing a session creates real items."""
    from inventory_mcp.tools import search

    session = sessions.create_session(
        db=test_db,
        bin_id=sample_bin.id,
    )

    sessions.add_pending_item(
        db=test_db,
        session_id=session.id,
        name="Commit Test Item",
        quantity_type="exact",
        quantity_value=10,
    )

    result = sessions.commit_session(test_db, test_image_store, session.id)
    assert result["success"] is True
    assert len(result["items_added"]) == 1

    # Verify item was created
    found = search.search_items(test_db, "Commit Test")
    assert len(found) >= 1


def test_cancel_session(test_db, sample_bin, test_image_store):
    """Test canceling a session."""
    session = sessions.create_session(
        db=test_db,
        bin_id=sample_bin.id,
    )

    result = sessions.cancel_session(test_db, test_image_store, session.id)
    assert result.status == SessionStatus.CANCELLED


def test_get_active_sessions(test_db, sample_bin):
    """Test listing active sessions."""
    sessions.create_session(
        db=test_db,
        bin_id=sample_bin.id,
    )

    result = sessions.get_active_sessions(test_db)
    assert len(result) >= 1


def test_set_session_target(test_db, sample_location):
    """Test changing session target."""
    from inventory_mcp.tools import bins

    bin1 = bins.create_bin(db=test_db, name="Target 1", location_id=sample_location.id)
    bin2 = bins.create_bin(db=test_db, name="Target 2", location_id=sample_location.id)

    session = sessions.create_session(
        db=test_db,
        bin_id=bin1.id,
    )

    result = sessions.set_session_target(
        db=test_db,
        session_id=session.id,
        bin_id=bin2.id,
    )
    assert result.target_bin_id == bin2.id


def test_commit_empty_session(test_db, sample_bin, test_image_store):
    """Test committing an empty session succeeds with no items."""
    session = sessions.create_session(
        db=test_db,
        bin_id=sample_bin.id,
    )

    result = sessions.commit_session(test_db, test_image_store, session.id)
    # Empty session still commits successfully, just with 0 items
    assert result["success"] is True
    assert len(result["items_added"]) == 0


def test_session_history(test_db, sample_bin, test_image_store):
    """Test getting session history."""
    session = sessions.create_session(
        db=test_db,
        bin_id=sample_bin.id,
    )

    sessions.add_pending_item(
        db=test_db,
        session_id=session.id,
        name="History Item",
    )

    sessions.commit_session(test_db, test_image_store, session.id)

    history = sessions.get_session_history(test_db)
    assert len(history) >= 1
    assert any(s.id == session.id for s in history)
