"""Tests for the embedding service."""

import numpy as np
import pytest

from protea.config import settings
from protea.services import embedding_service


class TestBuildItemText:
    """Tests for build_item_text function."""

    def test_name_only(self):
        """Test with just a name."""
        result = embedding_service.build_item_text("Phillips Screwdriver")
        assert result == "Phillips Screwdriver"

    def test_name_and_description(self):
        """Test with name and description."""
        result = embedding_service.build_item_text(
            "Phillips Screwdriver",
            description="A cross-head screwdriver for Phillips screws",
        )
        assert result == "Phillips Screwdriver A cross-head screwdriver for Phillips screws"

    def test_name_and_notes(self):
        """Test with name and notes."""
        result = embedding_service.build_item_text(
            "Phillips Screwdriver",
            notes="Size #2, yellow handle",
        )
        assert result == "Phillips Screwdriver Size #2, yellow handle"

    def test_all_fields(self):
        """Test with all fields."""
        result = embedding_service.build_item_text(
            "Phillips Screwdriver",
            description="A cross-head screwdriver",
            notes="Size #2",
        )
        assert result == "Phillips Screwdriver A cross-head screwdriver Size #2"

    def test_empty_description_ignored(self):
        """Test that empty string description is included but None is not."""
        result = embedding_service.build_item_text("Hammer", description=None)
        assert result == "Hammer"

    def test_empty_notes_ignored(self):
        """Test that None notes are ignored."""
        result = embedding_service.build_item_text("Hammer", notes=None)
        assert result == "Hammer"


class TestEmbeddingConversion:
    """Tests for embedding byte conversion functions."""

    def test_embedding_to_bytes_shape(self):
        """Test that embedding converts to correct byte size."""
        embedding = np.array([0.1, 0.2, 0.3, 0.4], dtype=np.float32)
        result = embedding_service.embedding_to_bytes(embedding)

        # 4 floats * 4 bytes each = 16 bytes
        assert isinstance(result, bytes)
        assert len(result) == 16

    def test_bytes_to_embedding_roundtrip(self):
        """Test roundtrip conversion preserves values."""
        original = np.array([0.1, 0.2, 0.3, 0.4, 0.5], dtype=np.float32)
        as_bytes = embedding_service.embedding_to_bytes(original)
        restored = embedding_service.bytes_to_embedding(as_bytes)

        np.testing.assert_array_almost_equal(original, restored)

    def test_embedding_dimension(self):
        """Test that real embedding has correct dimensions per config."""
        if not embedding_service.is_available():
            pytest.skip("Embedding service not available")

        embedding_bytes = embedding_service.generate_embedding("test text")
        embedding = embedding_service.bytes_to_embedding(embedding_bytes)

        assert embedding.shape == (settings.embedding_dimension,)

    def test_large_embedding_roundtrip(self):
        """Test roundtrip with 384-dimension embedding."""
        original = np.random.rand(384).astype(np.float32)
        as_bytes = embedding_service.embedding_to_bytes(original)
        restored = embedding_service.bytes_to_embedding(as_bytes)

        np.testing.assert_array_almost_equal(original, restored)


class TestCosineSimilarity:
    """Tests for cosine similarity calculation."""

    def test_identical_vectors(self):
        """Test that identical vectors have similarity 1.0."""
        vec = np.array([1.0, 2.0, 3.0], dtype=np.float32)
        similarity = embedding_service.cosine_similarity(vec, vec)
        assert abs(similarity - 1.0) < 0.0001

    def test_orthogonal_vectors(self):
        """Test that orthogonal vectors have similarity 0.0."""
        vec_a = np.array([1.0, 0.0, 0.0], dtype=np.float32)
        vec_b = np.array([0.0, 1.0, 0.0], dtype=np.float32)
        similarity = embedding_service.cosine_similarity(vec_a, vec_b)
        assert abs(similarity) < 0.0001

    def test_opposite_vectors(self):
        """Test that opposite vectors have similarity -1.0."""
        vec_a = np.array([1.0, 2.0, 3.0], dtype=np.float32)
        vec_b = np.array([-1.0, -2.0, -3.0], dtype=np.float32)
        similarity = embedding_service.cosine_similarity(vec_a, vec_b)
        assert abs(similarity - (-1.0)) < 0.0001

    def test_similar_vectors(self):
        """Test that similar vectors have high similarity."""
        vec_a = np.array([1.0, 2.0, 3.0], dtype=np.float32)
        vec_b = np.array([1.1, 2.1, 3.1], dtype=np.float32)
        similarity = embedding_service.cosine_similarity(vec_a, vec_b)
        assert similarity > 0.99

    def test_zero_vector_handling(self):
        """Test that zero vectors return 0 similarity."""
        vec_a = np.array([1.0, 2.0, 3.0], dtype=np.float32)
        vec_zero = np.array([0.0, 0.0, 0.0], dtype=np.float32)
        similarity = embedding_service.cosine_similarity(vec_a, vec_zero)
        assert similarity == 0.0


class TestBatchCosineSimilarity:
    """Tests for batch cosine similarity calculation."""

    def test_empty_list(self):
        """Test with empty embeddings list."""
        query = np.array([1.0, 2.0, 3.0], dtype=np.float32)
        result = embedding_service.batch_cosine_similarity(query, [])
        assert result == []

    def test_single_embedding(self):
        """Test with single embedding."""
        query = np.array([1.0, 0.0, 0.0], dtype=np.float32)
        embeddings = [np.array([1.0, 0.0, 0.0], dtype=np.float32)]
        result = embedding_service.batch_cosine_similarity(query, embeddings)

        assert len(result) == 1
        assert abs(result[0] - 1.0) < 0.0001

    def test_multiple_embeddings(self):
        """Test with multiple embeddings."""
        query = np.array([1.0, 0.0, 0.0], dtype=np.float32)
        embeddings = [
            np.array([1.0, 0.0, 0.0], dtype=np.float32),  # identical
            np.array([0.0, 1.0, 0.0], dtype=np.float32),  # orthogonal
            np.array([0.7, 0.7, 0.0], dtype=np.float32),  # partial
        ]
        result = embedding_service.batch_cosine_similarity(query, embeddings)

        assert len(result) == 3
        assert abs(result[0] - 1.0) < 0.0001  # identical
        assert abs(result[1]) < 0.0001  # orthogonal
        assert 0.5 < result[2] < 0.8  # partial similarity

    def test_ordering_preserved(self):
        """Test that result order matches input order."""
        query = np.array([1.0, 0.0], dtype=np.float32)
        embeddings = [
            np.array([0.0, 1.0], dtype=np.float32),  # low similarity
            np.array([1.0, 0.0], dtype=np.float32),  # high similarity
            np.array([0.5, 0.5], dtype=np.float32),  # medium similarity
        ]
        result = embedding_service.batch_cosine_similarity(query, embeddings)

        # Order should match input, not be sorted by similarity
        assert result[0] < result[1]  # first has lower similarity than second
        assert result[1] > result[2]  # second has higher similarity than third


class TestGenerateEmbedding:
    """Tests for embedding generation."""

    @pytest.fixture(autouse=True)
    def check_availability(self):
        """Skip tests if embedding service is not available."""
        if not embedding_service.is_available():
            pytest.skip("Embedding service not available")

    def test_generates_bytes(self):
        """Test that generate_embedding returns bytes."""
        result = embedding_service.generate_embedding("test text")
        assert isinstance(result, bytes)

    def test_correct_byte_size(self):
        """Test that embedding has correct byte size (dimensions * 4 bytes)."""
        result = embedding_service.generate_embedding("test text")
        assert len(result) == settings.embedding_dimension * 4

    def test_different_texts_different_embeddings(self):
        """Test that different texts produce different embeddings."""
        emb1 = embedding_service.generate_embedding("hammer")
        emb2 = embedding_service.generate_embedding("computer keyboard")

        vec1 = embedding_service.bytes_to_embedding(emb1)
        vec2 = embedding_service.bytes_to_embedding(emb2)

        # Should not be identical
        assert not np.allclose(vec1, vec2)

    def test_similar_texts_similar_embeddings(self):
        """Test that similar texts produce similar embeddings."""
        emb1 = embedding_service.generate_embedding("Phillips head screwdriver")
        emb2 = embedding_service.generate_embedding("Phillips screwdriver tool")

        vec1 = embedding_service.bytes_to_embedding(emb1)
        vec2 = embedding_service.bytes_to_embedding(emb2)

        similarity = embedding_service.cosine_similarity(vec1, vec2)
        assert similarity > 0.8  # Should be quite similar


class TestGenerateQueryEmbedding:
    """Tests for query embedding generation."""

    @pytest.fixture(autouse=True)
    def check_availability(self):
        """Skip tests if embedding service is not available."""
        if not embedding_service.is_available():
            pytest.skip("Embedding service not available")

    def test_generates_numpy_array(self):
        """Test that generate_query_embedding returns numpy array."""
        result = embedding_service.generate_query_embedding("test query")
        assert isinstance(result, np.ndarray)

    def test_correct_dimensions(self):
        """Test that query embedding has correct dimensions per config."""
        result = embedding_service.generate_query_embedding("test query")
        assert result.shape == (settings.embedding_dimension,)

    def test_query_matches_item_embedding(self):
        """Test that query embedding is compatible with item embedding."""
        # Generate item embedding (stored as bytes)
        item_bytes = embedding_service.generate_embedding("cordless drill")
        item_vec = embedding_service.bytes_to_embedding(item_bytes)

        # Generate query embedding (returned as array)
        query_vec = embedding_service.generate_query_embedding("cordless drill")

        # Should be identical (or very close)
        similarity = embedding_service.cosine_similarity(query_vec, item_vec)
        assert similarity > 0.99


class TestIsAvailable:
    """Tests for availability check."""

    def test_returns_boolean(self):
        """Test that is_available returns a boolean."""
        result = embedding_service.is_available()
        assert isinstance(result, bool)

    def test_consistent_results(self):
        """Test that is_available returns consistent results."""
        result1 = embedding_service.is_available()
        result2 = embedding_service.is_available()
        assert result1 == result2
