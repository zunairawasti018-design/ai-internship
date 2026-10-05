"""
Async document ingestion pipeline.

Flow
----
1. Read the uploaded file from disk (PDF or plain-text).
2. Split the text into overlapping chunks.
3. Embed each chunk with ``sentence-transformers`` (all-MiniLM-L6-v2).
4. Upsert the embeddings into Qdrant tagged with user_id + session_id.
5. Update the ``documents`` row status in Postgres (pending → done / failed).

This module is intentionally dependency-light: it only imports from the
standard library, ``sentence_transformers``, and the project's own
``qdrant_client`` module so it can be called from a
``fastapi.BackgroundTasks`` callback without dragging in the full ORM layer.
"""

from __future__ import annotations

import asyncio
import io
import logging
import os
import uuid
from typing import Sequence

from qdrant_client.http.models import PointStruct, Filter, FieldCondition, MatchValue

from app.qdrant_client import get_qdrant, COLLECTION_NAME

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Lazy model cache – the embedding model is ~90 MB and should load once
# ---------------------------------------------------------------------------
_embedding_model = None
_model_lock = asyncio.Lock()

EMBEDDING_MODEL_NAME = os.getenv(
    "EMBEDDING_MODEL", "all-MiniLM-L6-v2"
)

CHUNK_SIZE = int(os.getenv("INGESTION_CHUNK_SIZE", "512"))       # characters
CHUNK_OVERLAP = int(os.getenv("INGESTION_CHUNK_OVERLAP", "64"))  # characters
UPSERT_BATCH = 64


async def _get_model():
    """Return the (lazily loaded) SentenceTransformer model."""
    global _embedding_model
    if _embedding_model is None:
        async with _model_lock:
            if _embedding_model is None:  # double-check after acquiring lock
                from sentence_transformers import SentenceTransformer  # type: ignore
                logger.info("Loading embedding model '%s' …", EMBEDDING_MODEL_NAME)
                # Model loading is CPU-bound – run in a thread pool
                loop = asyncio.get_running_loop()
                _embedding_model = await loop.run_in_executor(
                    None, SentenceTransformer, EMBEDDING_MODEL_NAME
                )
                logger.info("Embedding model loaded.")
    return _embedding_model


# ---------------------------------------------------------------------------
# Text extraction helpers
# ---------------------------------------------------------------------------

def _extract_text_from_pdf(data: bytes) -> str:
    """Extract raw text from PDF bytes using pypdf."""
    import pypdf  # type: ignore

    reader = pypdf.PdfReader(io.BytesIO(data))
    parts = []
    for page in reader.pages:
        text = page.extract_text()
        if text:
            parts.append(text)
    return "\n".join(parts)


def _extract_text(file_path: str, filename: str) -> str:
    """Dispatch to the correct extractor based on file extension."""
    _, ext = os.path.splitext(filename.lower())
    with open(file_path, "rb") as fh:
        data = fh.read()

    if ext == ".pdf":
        return _extract_text_from_pdf(data)
    # Treat everything else as UTF-8 text (txt, md, rst, csv …)
    return data.decode("utf-8", errors="replace")


# ---------------------------------------------------------------------------
# Chunking
# ---------------------------------------------------------------------------

def _chunk_text(text: str, chunk_size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> list[str]:
    """Split *text* into overlapping fixed-size character windows."""
    if not text.strip():
        return []
    chunks: list[str] = []
    start = 0
    while start < len(text):
        end = min(start + chunk_size, len(text))
        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)
        if end == len(text):
            break
        start += chunk_size - overlap
    return chunks


# ---------------------------------------------------------------------------
# Embedding
# ---------------------------------------------------------------------------

async def _embed_chunks(chunks: list[str]) -> list[list[float]]:
    """Return a list of embedding vectors for each chunk."""
    model = await _get_model()
    loop = asyncio.get_running_loop()
    embeddings = await loop.run_in_executor(
        None, lambda: model.encode(chunks, show_progress_bar=False, convert_to_numpy=True)
    )
    return [emb.tolist() for emb in embeddings]


# ---------------------------------------------------------------------------
# Qdrant upsert
# ---------------------------------------------------------------------------

async def _delete_existing_vectors(document_id: int) -> None:
    """Remove any previously stored vectors for this document (for re-ingestion)."""
    client = get_qdrant()
    await client.delete(
        collection_name=COLLECTION_NAME,
        points_selector=Filter(
            must=[
                FieldCondition(
                    key="document_id",
                    match=MatchValue(value=document_id),
                )
            ]
        ),
    )


async def _upsert_points(
    chunks: list[str],
    embeddings: list[list[float]],
    *,
    user_id: int,
    session_id: int,
    document_id: int,
    filename: str,
) -> None:
    """Batch-upsert all (chunk, embedding) pairs into Qdrant."""
    client = get_qdrant()
    points: list[PointStruct] = [
        PointStruct(
            id=str(uuid.uuid4()),
            vector=embedding,
            payload={
                "user_id": user_id,
                "session_id": session_id,
                "document_id": document_id,
                "chunk_index": idx,
                "text": chunk,
                "filename": filename,
            },
        )
        for idx, (chunk, embedding) in enumerate(zip(chunks, embeddings))
    ]

    for batch_start in range(0, len(points), UPSERT_BATCH):
        batch = points[batch_start : batch_start + UPSERT_BATCH]
        await client.upsert(collection_name=COLLECTION_NAME, points=batch)

    logger.info(
        "Upserted %d vectors for document_id=%d (user=%d, session=%d).",
        len(points), document_id, user_id, session_id,
    )


# ---------------------------------------------------------------------------
# Postgres status helpers (imported lazily to avoid circular imports)
# ---------------------------------------------------------------------------

async def _update_status(document_id: int, status: str, error: str | None = None) -> None:
    """Persist ingestion status back to the SQL documents table."""
    from app.database import AsyncSessionLocal
    from app.models.document import Document
    from sqlalchemy import select

    async with AsyncSessionLocal() as db:
        result = await db.execute(select(Document).where(Document.id == document_id))
        doc = result.scalar_one_or_none()
        if doc is None:
            logger.warning("Document %d not found when updating status.", document_id)
            return
        doc.ingestion_status = status
        if error:
            doc.ingestion_error = error[:500]
        db.add(doc)
        await db.commit()


# ---------------------------------------------------------------------------
# Public entry point – called as a FastAPI BackgroundTask
# ---------------------------------------------------------------------------

async def ingest_document(
    *,
    document_id: int,
    file_path: str,
    filename: str,
    user_id: int,
    session_id: int,
) -> None:
    """
    Full ingestion pipeline executed asynchronously in the background.

    Steps
    -----
    1. Mark document as ``processing``.
    2. Extract text from disk.
    3. Chunk the text.
    4. Embed chunks.
    5. Delete old vectors (idempotent re-ingestion).
    6. Upsert new vectors.
    7. Mark document as ``done`` (or ``failed`` on error).
    """
    logger.info(
        "Starting ingestion: document_id=%d user_id=%d session_id=%d filename='%s'",
        document_id, user_id, session_id, filename,
    )

    await _update_status(document_id, "processing")

    try:
        # --- 1. Extract text ---------------------------------------------------
        loop = asyncio.get_running_loop()
        text = await loop.run_in_executor(None, _extract_text, file_path, filename)

        if not text.strip():
            raise ValueError("No extractable text was found in the uploaded document.")

        # --- 2. Chunk ---------------------------------------------------------
        chunks = _chunk_text(text)
        logger.info("Document %d split into %d chunks.", document_id, len(chunks))

        # --- 3. Embed ---------------------------------------------------------
        embeddings = await _embed_chunks(chunks)

        # --- 4. Remove stale vectors (re-ingestion) ----------------------------
        await _delete_existing_vectors(document_id)

        # --- 5. Upsert --------------------------------------------------------
        await _upsert_points(
            chunks,
            embeddings,
            user_id=user_id,
            session_id=session_id,
            document_id=document_id,
            filename=filename,
        )

        await _update_status(document_id, "done")
        logger.info("Ingestion complete for document_id=%d.", document_id)

    except Exception as exc:
        logger.exception("Ingestion failed for document_id=%d: %s", document_id, exc)
        await _update_status(document_id, "failed", error=str(exc))
