import numpy as np
import pytest

from services.embedding_service import (
    cosine_similarity,
    generate_embedding,

)


def test_cosine_similarity():
    query = np.array([1.0, 0.0, 0.0])
    documents = np.array([
        [1.0, 0.0, 0.0],
        [0.0, 1.0, 0.0],
        [-1.0, 0.0, 0.0],
    ])

    scores = cosine_similarity(query, documents)

    assert scores[0] == pytest.approx(1.0)
    assert scores[1] == pytest.approx(0.0)
    assert scores[2] == pytest.approx(-1.0)


def test_reject_mismatched_dimensions():
    with pytest.raises(ValueError, match="dimensions"):
        cosine_similarity(
            np.array([1.0, 0.0]),
            np.array([[1.0, 0.0, 0.0]]),
        )


def test_reject_invalid_query_shape():
    with pytest.raises(ValueError, match="one-dimensional"):
        cosine_similarity(
            np.array([[1.0, 0.0]]),
            np.array([[1.0, 0.0]]),
        )


def test_reject_zero_vectors():
    with pytest.raises(ValueError, match="zero vectors"):
        cosine_similarity(
            np.array([0.0, 0.0]),
            np.array([[1.0, 0.0]]),
        )


def test_reject_non_finite_values():
    with pytest.raises(ValueError, match="finite"):
        cosine_similarity(
            np.array([float("nan"), 0.0]),
            np.array([[1.0, 0.0]]),
        )


def test_reject_empty_text():
    with pytest.raises(ValueError, match="must not be empty"):
        generate_embedding("   ")