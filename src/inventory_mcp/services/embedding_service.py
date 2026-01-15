"""Embedding service for semantic/vector search."""

import logging
from typing import Optional

import numpy as np

from inventory_mcp.config import settings

logger = logging.getLogger("inventory_mcp")

# Lazy-load the model to avoid slow startup
_model = None
_model_load_attempted = False


def _load_model():
    """Load the sentence transformer model (lazy initialization)."""
    global _model, _model_load_attempted

    if _model_load_attempted:
        return _model

    _model_load_attempted = True

    if not settings.embedding_enabled:
        logger.info("Embedding disabled via config")
        return None

    try:
        from sentence_transformers import SentenceTransformer

        logger.info(f"Loading embedding model: {settings.embedding_model}")
        _model = SentenceTransformer(settings.embedding_model)
        logger.info("Embedding model loaded successfully")
        return _model
    except ImportError:
        logger.warning("sentence-transformers not installed, vector search disabled")
        return None
    except Exception as e:
        logger.error(f"Failed to load embedding model: {e}")
        return None


def is_available() -> bool:
    """Check if embedding service is available."""
    return _load_model() is not None


def build_item_text(name: str, description: Optional[str] = None, notes: Optional[str] = None) -> str:
    """Build searchable text from item fields.

    Args:
        name: Item name (required)
        description: Item description (optional)
        notes: Item notes (optional)

    Returns:
        Combined text for embedding
    """
    parts = [name]
    if description:
        parts.append(description)
    if notes:
        parts.append(notes)
    return " ".join(parts)


def generate_embedding(text: str) -> Optional[bytes]:
    """Generate embedding bytes for storage in SQLite.

    Args:
        text: Text to embed

    Returns:
        Embedding as bytes (BLOB), or None if unavailable
    """
    model = _load_model()
    if model is None:
        return None

    try:
        embedding = model.encode(text, convert_to_numpy=True)
        return embedding_to_bytes(embedding)
    except Exception as e:
        logger.error(f"Failed to generate embedding: {e}")
        return None


def generate_query_embedding(query: str) -> Optional[np.ndarray]:
    """Generate embedding array for search queries.

    Args:
        query: Search query text

    Returns:
        Embedding as numpy array, or None if unavailable
    """
    model = _load_model()
    if model is None:
        return None

    try:
        return model.encode(query, convert_to_numpy=True)
    except Exception as e:
        logger.error(f"Failed to generate query embedding: {e}")
        return None


def embedding_to_bytes(embedding: np.ndarray) -> bytes:
    """Convert numpy array to bytes for SQLite BLOB storage.

    Args:
        embedding: Numpy array of floats

    Returns:
        Bytes representation
    """
    return embedding.astype(np.float32).tobytes()


def bytes_to_embedding(data: bytes) -> np.ndarray:
    """Convert SQLite BLOB bytes back to numpy array.

    Args:
        data: Bytes from database

    Returns:
        Numpy array of floats
    """
    return np.frombuffer(data, dtype=np.float32)


def cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    """Compute cosine similarity between two embeddings.

    Args:
        a: First embedding vector
        b: Second embedding vector

    Returns:
        Cosine similarity score (0 to 1 for normalized vectors)
    """
    dot_product = np.dot(a, b)
    norm_a = np.linalg.norm(a)
    norm_b = np.linalg.norm(b)

    if norm_a == 0 or norm_b == 0:
        return 0.0

    return float(dot_product / (norm_a * norm_b))


def batch_cosine_similarity(query_embedding: np.ndarray, embeddings: list[np.ndarray]) -> list[float]:
    """Compute cosine similarity between query and multiple embeddings.

    Args:
        query_embedding: Query vector
        embeddings: List of embedding vectors to compare

    Returns:
        List of similarity scores
    """
    if not embeddings:
        return []

    # Stack embeddings into matrix for efficient computation
    matrix = np.vstack(embeddings)

    # Normalize query
    query_norm = query_embedding / np.linalg.norm(query_embedding)

    # Normalize each row
    norms = np.linalg.norm(matrix, axis=1, keepdims=True)
    norms[norms == 0] = 1  # Avoid division by zero
    matrix_norm = matrix / norms

    # Compute all similarities at once
    similarities = matrix_norm @ query_norm

    return similarities.tolist()
