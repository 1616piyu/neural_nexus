from functools import lru_cache

import numpy as np


MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"
EMBEDDING_DIMENSION = 384


@lru_cache(maxsize=1)
def get_embedding_model():
    """Load the embedding model once and reuse it."""
    from sentence_transformers import SentenceTransformer
    return SentenceTransformer(MODEL_NAME)


def generate_embedding(text):
    """Convert one text string into a normalized embedding vector."""
    if not isinstance(text, str) or not text.strip():
        raise ValueError("Text must not be empty.")

    model = get_embedding_model()

    vector = model.encode(
        text.strip(),
        normalize_embeddings=True,
        convert_to_numpy=True,
    )

    return np.asarray(vector, dtype=np.float32)


def generate_embeddings(texts):
    """Convert multiple text chunks into embedding vectors."""
    if not isinstance(texts, list):
        raise ValueError("texts must be a list.")

    if not texts:
        return np.empty(
            (0, EMBEDDING_DIMENSION),
            dtype=np.float32,
        )

    if any(not isinstance(text, str) or not text.strip() for text in texts):
        raise ValueError("Every text chunk must be a non-empty string.")

    model = get_embedding_model()

    vectors = model.encode(
        texts,
        normalize_embeddings=True,
        convert_to_numpy=True,
        show_progress_bar=False,
    )

    vectors = np.asarray(vectors, dtype=np.float32)

    if vectors.ndim != 2 or vectors.shape[1] != EMBEDDING_DIMENSION:
        raise ValueError("The embedding model returned an unexpected shape.")

    return vectors


def cosine_similarity(query_vector, document_vectors):
    """Calculate cosine similarity between a query and document vectors."""
    query_vector = np.asarray(query_vector, dtype=np.float32)
    document_vectors = np.asarray(document_vectors, dtype=np.float32)

    if query_vector.ndim != 1:
        raise ValueError("Query embedding must be one-dimensional.")

    if document_vectors.ndim != 2:
        raise ValueError("Document embeddings must be two-dimensional.")

    if query_vector.shape[0] != document_vectors.shape[1]:
        raise ValueError("Embedding dimensions do not match.")

    if not np.all(np.isfinite(query_vector)) or not np.all(
        np.isfinite(document_vectors)
    ):
        raise ValueError("Embeddings must contain finite numbers.")

    query_norm = np.linalg.norm(query_vector)
    document_norms = np.linalg.norm(document_vectors, axis=1)

    if query_norm == 0 or np.any(document_norms == 0):
        raise ValueError("Embeddings must not be zero vectors.")

    return (
        document_vectors @ query_vector
    ) / (document_norms * query_norm)