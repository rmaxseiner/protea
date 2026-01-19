"""Pytest fixtures for protea tests."""

import tempfile
from pathlib import Path

import pytest

from protea.config import Settings
from protea.db.connection import Database
from protea.services.image_store import ImageStore


@pytest.fixture
def test_settings():
    """Create test settings with temp directories."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmppath = Path(tmpdir)
        yield Settings(
            database_path=tmppath / "test.db",
            image_base_path=tmppath / "images",
        )


@pytest.fixture
def test_db(test_settings):
    """Create test database with migrations."""
    db = Database(test_settings.database_path)
    db.run_migrations()
    return db


@pytest.fixture
def test_image_store(test_settings):
    """Create test image store."""
    return ImageStore(
        test_settings.image_base_path,
        test_settings.image_format,
        test_settings.image_quality,
        test_settings.thumbnail_size,
    )


@pytest.fixture
def sample_location(test_db):
    """Create a sample location for testing."""
    from protea.tools import locations

    return locations.create_location(
        db=test_db,
        name="Test Garage",
        description="Test location",
    )


@pytest.fixture
def sample_bin(test_db, sample_location):
    """Create a sample bin for testing."""
    from protea.tools import bins

    return bins.create_bin(
        db=test_db,
        name="Test Bin",
        location_id=sample_location.id,
        description="Test bin",
    )


@pytest.fixture
def sample_category(test_db):
    """Create a sample category for testing."""
    from protea.tools import categories

    return categories.create_category(
        db=test_db,
        name="Test Category",
    )
