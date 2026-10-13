"""Semantic search over the user's stored document embeddings."""

import numpy as np

import database
from services.embedding_service import (
    generate_embedding,
    cosine_similarity,
)


def search_documents(user_id, query, top_k=5, document_id=None):
    """
    Find the most relevant document chunks for a user's query.

    Args:
        user_id: Authenticated user's database ID.
        query: Natural-language search question.
        top_k: Maximum number of results to return.
        document_id: Optional document ID to restrict the search.

    Returns:
        A list of matching chunks ordered by similarity.
    """
    if not isinstance(user_id, int) or user_id <= 0:
        raise ValueError("A valid user ID is required.")

    if not isinstance(query, str) or not query.strip():
        raise ValueError("Search query must not be empty.")

    if isinstance(top_k, bool) or not isinstance(top_k, int):
        raise ValueError("top_k must be a positive integer.")

    if top_k <= 0:
        raise ValueError("top_k must be a positive integer.")

    if document_id is not None:
        if (
            isinstance(document_id, bool)
            or not isinstance(document_id, int)
            or document_id <= 0
        ):
            raise ValueError("document_id must be a positive integer.")

    # Retrieve only embeddings belonging to this user.
    rows = database.get_chunk_embeddings(
        user_id=user_id,
        document_id=document_id,
    )

    if not rows:
        return []

    # Convert the question into the same vector space as document chunks.
    query_vector = generate_embedding(query)

    vectors = []
    valid_rows = []

    for row in rows:
        dimension = row["dimension"]
        embedding_bytes = row["embedding"]

        if dimension != query_vector.shape[0]:
            continue

        vector = np.frombuffer(
            embedding_bytes,
            dtype=np.float32,
        )

        if vector.shape[0] != dimension:
            continue

        if not np.all(np.isfinite(vector)):
            continue

        if np.linalg.norm(vector) == 0:
            continue

        vectors.append(vector)
        valid_rows.append(row)

    if not vectors:
        return []

    document_vectors = np.vstack(vectors)

    # Compare the query against every eligible document chunk.
    scores = cosine_similarity(
        query_vector,
        document_vectors,
    )

    ranked_indices = np.argsort(scores)[::-1][:top_k]

    results = []

    for index in ranked_indices:
        row = valid_rows[int(index)]

        results.append({
            "chunk_id": row["chunk_id"],
            "document_id": row["document_id"],
            "chunk_index": row["chunk_index"],
            "content": row["content"],
            "similarity": float(scores[index]),
        })

    return results