"""
Qdrant client singleton and collection management.

The collection ``documents`` stores text chunks together with payload fields:
    - user_id    (int)  – owner of the document
    - session_id (int)  – chat session the document belongs to
    - document_id (int) – FK back to the SQL ``documents`` table
    - chunk_index (int) – position of the chunk within the document
    - text        (str) – raw text of the chunk (for retrieval)
    - filename    (str) – original filename

All vector searches are pre-filtered on ``user_id`` + ``session_id`` so that
one tenant never sees another tenant's data.
"""

from __future__ import annotations

import logging
import os

from qdrant_client import AsyncQdrantClient
from qdrant_client.http.models import (
    Distance,
    VectorParams,
    PayloadSchemaType,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Module-level singleton (lazily initialised at startup)
# ---------------------------------------------------------------------------
_qdrant: AsyncQdrantClient | None = None

COLLECTION_NAME = "documents"
VECTOR_SIZE = 384          # all-MiniLM-L6-v2 output dimension
DISTANCE = Distance.COSINE


def get_qdrant() -> AsyncQdrantClient:
    """Return the module-level Qdrant client (must call init_qdrant first)."""
    if _qdrant is None:
        raise RuntimeError("Qdrant client has not been initialised. Call init_qdrant() first.")
    return _qdrant


async def init_qdrant() -> AsyncQdrantClient:
    """
    Create / reuse the AsyncQdrantClient singleton and ensure the collection
    and payload indexes exist.  Call once from the FastAPI lifespan.
    """
    global _qdrant

    host = os.getenv("QDRANT_HOST", "localhost")
    port = int(os.getenv("QDRANT_PORT", "6333"))

    logger.info("Connecting to Qdrant at %s:%s …", host, port)
    _qdrant = AsyncQdrantClient(host=host, port=port)

    # Create collection if it does not exist yet
    collections = await _qdrant.get_collections()
    existing = {c.name for c in collections.collections}

    if COLLECTION_NAME not in existing:
        logger.info("Creating Qdrant collection '%s' …", COLLECTION_NAME)
        await _qdrant.create_collection(
            collection_name=COLLECTION_NAME,
            vectors_config=VectorParams(size=VECTOR_SIZE, distance=DISTANCE),
        )

        # Payload indexes for efficient multi-tenant filtering
        for field, schema_type in [
            ("user_id", PayloadSchemaType.INTEGER),
            ("session_id", PayloadSchemaType.INTEGER),
            ("document_id", PayloadSchemaType.INTEGER),
        ]:
            await _qdrant.create_payload_index(
                collection_name=COLLECTION_NAME,
                field_name=field,
                field_schema=schema_type,
            )
        logger.info("Qdrant collection '%s' ready.", COLLECTION_NAME)
    else:
        logger.info("Qdrant collection '%s' already exists – skipping creation.", COLLECTION_NAME)

    return _qdrant


async def close_qdrant() -> None:
    """Gracefully close the Qdrant connection (call from lifespan shutdown)."""
    global _qdrant
    if _qdrant is not None:
        await _qdrant.close()
        _qdrant = None
        logger.info("Qdrant connection closed.")
