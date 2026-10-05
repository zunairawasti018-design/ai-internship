"""
Document upload & retrieval router.

Endpoints
---------
POST   /documents/sessions/{session_id}/upload
    Upload a file → 202 Accepted + kick off background ingestion.

GET    /documents/sessions/{session_id}
    List all documents for a session (paginated).

GET    /documents/{document_id}/status
    Poll the ingestion status of a specific document.

DELETE /documents/{document_id}
    Delete a document record from Postgres + purge its Qdrant vectors.

POST   /documents/sessions/{session_id}/search
    Semantic similarity search scoped to a user + session.
"""

from __future__ import annotations

import logging
import os
import uuid
from datetime import datetime, timezone

import aiofiles
import aiofiles.os
from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    File,
    HTTPException,
    Query,
    UploadFile,
    status,
)
from qdrant_client.http.models import Filter, FieldCondition, MatchValue
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_current_user, get_db
from app.ingestion.pipeline import ingest_document
from app.models.chat_session import ChatSession
from app.models.document import Document
from app.models.user import User
from app.qdrant_client import get_qdrant, COLLECTION_NAME
from app.schemas.document import (
    ChunkResult,
    DocumentListResponse,
    DocumentStatusResponse,
    DocumentUploadResponse,
    SemanticSearchResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/documents", tags=["Documents"])

# Where uploaded files are stored on disk
UPLOAD_DIR = os.getenv("UPLOAD_DIR", "uploads")

# Allowed MIME types
ALLOWED_CONTENT_TYPES = {
    "application/pdf",
    "text/plain",
    "text/markdown",
    "text/csv",
    "application/octet-stream",  # generic fallback for .txt from some clients
}

MAX_FILE_SIZE_MB = int(os.getenv("MAX_FILE_SIZE_MB", "50"))
MAX_FILE_SIZE_BYTES = MAX_FILE_SIZE_MB * 1024 * 1024


# ---------------------------------------------------------------------------
# Helper – verify session ownership
# ---------------------------------------------------------------------------

async def _get_owned_session(
    session_id: int,
    current_user: User,
    db: AsyncSession,
) -> ChatSession:
    result = await db.execute(
        select(ChatSession).where(ChatSession.id == session_id)
    )
    chat_session = result.scalar_one_or_none()
    if chat_session is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Chat session {session_id} not found",
        )
    if chat_session.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to access this session",
        )
    return chat_session


# ---------------------------------------------------------------------------
# POST /documents/sessions/{session_id}/upload
# ---------------------------------------------------------------------------

@router.post(
    "/sessions/{session_id}/upload",
    response_model=DocumentUploadResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Upload a document and trigger async ingestion",
)
async def upload_document(
    session_id: int,
    background_tasks: BackgroundTasks,
    file: UploadFile = File(..., description="PDF or plain-text file to ingest"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> DocumentUploadResponse:
    """
    Upload a document for ingestion into Qdrant.

    - Returns **202 Accepted** immediately while ingestion runs in the background.
    - Allowed formats: PDF, TXT, MD, CSV (≤ 50 MB by default).
    - Vectors are tagged with ``user_id`` and ``session_id`` for multi-tenant isolation.
    """
    # 1. Verify session ownership
    await _get_owned_session(session_id, current_user, db)

    # 2. Content-type guard (soft check – filename extension is the hard check)
    if file.content_type not in ALLOWED_CONTENT_TYPES:
        _, ext = os.path.splitext((file.filename or "").lower())
        if ext not in {".pdf", ".txt", ".md", ".csv", ".rst"}:
            raise HTTPException(
                status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
                detail=(
                    f"Unsupported file type '{file.content_type}'. "
                    "Allowed: PDF, TXT, MD, CSV."
                ),
            )

    # 3. Persist to disk (stream to avoid loading into RAM)
    os.makedirs(UPLOAD_DIR, exist_ok=True)
    safe_name = f"{uuid.uuid4().hex}_{os.path.basename(file.filename or 'upload')}"
    file_path = os.path.join(UPLOAD_DIR, safe_name)

    total_bytes = 0
    async with aiofiles.open(file_path, "wb") as out_file:
        while chunk := await file.read(1024 * 64):  # 64 KB chunks
            total_bytes += len(chunk)
            if total_bytes > MAX_FILE_SIZE_BYTES:
                await aiofiles.os.remove(file_path)
                raise HTTPException(
                    status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                    detail=f"File exceeds maximum size of {MAX_FILE_SIZE_MB} MB.",
                )
            await out_file.write(chunk)

    # 4. Create the DB record (status = "pending")
    db_doc = Document(
        filename=file.filename or safe_name,
        file_path=file_path,
        user_id=current_user.id,
        session_id=session_id,
        ingestion_status="pending",
    )
    db.add(db_doc)
    await db.commit()
    await db.refresh(db_doc)

    # 5. Fire background ingestion – does NOT block the response
    background_tasks.add_task(
        ingest_document,
        document_id=db_doc.id,
        file_path=file_path,
        filename=db_doc.filename,
        user_id=current_user.id,
        session_id=session_id,
    )

    logger.info(
        "Document %d queued for ingestion (user=%d, session=%d).",
        db_doc.id, current_user.id, session_id,
    )
    return DocumentUploadResponse.model_validate(db_doc)


# ---------------------------------------------------------------------------
# GET /documents/sessions/{session_id}
# ---------------------------------------------------------------------------

@router.get(
    "/sessions/{session_id}",
    response_model=DocumentListResponse,
    summary="List documents for a session",
)
async def list_documents(
    session_id: int,
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> DocumentListResponse:
    """List all documents uploaded to a chat session (paginated)."""
    await _get_owned_session(session_id, current_user, db)

    count_q = select(func.count(Document.id)).where(
        (Document.session_id == session_id) & (Document.user_id == current_user.id)
    )
    total = (await db.execute(count_q)).scalar_one()

    query = (
        select(Document)
        .where(
            (Document.session_id == session_id) & (Document.user_id == current_user.id)
        )
        .order_by(Document.created_at.desc())
        .offset(skip)
        .limit(limit)
    )
    docs = (await db.execute(query)).scalars().all()

    return DocumentListResponse(
        total=total,
        count=len(docs),
        items=[DocumentStatusResponse.model_validate(d) for d in docs],
    )


# ---------------------------------------------------------------------------
# GET /documents/{document_id}/status
# ---------------------------------------------------------------------------

@router.get(
    "/{document_id}/status",
    response_model=DocumentStatusResponse,
    summary="Poll ingestion status of a document",
)
async def get_document_status(
    document_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> DocumentStatusResponse:
    """Return the current ingestion status of a document."""
    result = await db.execute(
        select(Document).where(Document.id == document_id)
    )
    doc = result.scalar_one_or_none()

    if doc is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Document {document_id} not found",
        )
    if doc.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to view this document",
        )
    return DocumentStatusResponse.model_validate(doc)


# ---------------------------------------------------------------------------
# DELETE /documents/{document_id}
# ---------------------------------------------------------------------------

@router.delete(
    "/{document_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a document and purge its vectors",
)
async def delete_document(
    document_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    """
    Delete a document record from Postgres and remove all associated Qdrant vectors.
    The uploaded file on disk is also removed.
    """
    result = await db.execute(
        select(Document).where(Document.id == document_id)
    )
    doc = result.scalar_one_or_none()

    if doc is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Document {document_id} not found",
        )
    if doc.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to delete this document",
        )

    # Remove Qdrant vectors
    try:
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
    except Exception as exc:
        logger.warning("Failed to delete Qdrant vectors for document %d: %s", document_id, exc)

    # Remove from disk
    if os.path.exists(doc.file_path):
        try:
            await aiofiles.os.remove(doc.file_path)
        except OSError as exc:
            logger.warning("Could not remove file %s: %s", doc.file_path, exc)

    # Remove from DB
    await db.execute(delete(Document).where(Document.id == document_id))
    await db.commit()


# ---------------------------------------------------------------------------
# POST /documents/sessions/{session_id}/search
# ---------------------------------------------------------------------------

from pydantic import BaseModel, Field as PydanticField


class SearchRequest(BaseModel):
    query: str = PydanticField(..., min_length=1, max_length=1000)
    top_k: int = PydanticField(5, ge=1, le=20, description="Number of results to return")


@router.post(
    "/sessions/{session_id}/search",
    response_model=SemanticSearchResponse,
    summary="Semantic search within a session's documents",
)
async def search_documents(
    session_id: int,
    request: SearchRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> SemanticSearchResponse:
    """
    Perform multi-tenant semantic similarity search.

    Only vectors tagged with the authenticated user's ``user_id`` **and** the
    given ``session_id`` are searched, guaranteeing tenant isolation.
    """
    await _get_owned_session(session_id, current_user, db)

    # Embed the query
    from app.ingestion.pipeline import _get_model

    model = await _get_model()
    loop = __import__("asyncio").get_running_loop()
    query_vector = (
        await loop.run_in_executor(
            None, lambda: model.encode([request.query], convert_to_numpy=True)
        )
    )[0].tolist()

    # Multi-tenant filter: must match both user_id AND session_id
    search_filter = Filter(
        must=[
            FieldCondition(key="user_id", match=MatchValue(value=current_user.id)),
            FieldCondition(key="session_id", match=MatchValue(value=session_id)),
        ]
    )

    client = get_qdrant()
    search_result = await client.query_points(
        collection_name=COLLECTION_NAME,
        query=query_vector,
        query_filter=search_filter,
        limit=request.top_k,
        with_payload=True,
    )

    results = [
        ChunkResult(
            document_id=hit.payload["document_id"],
            filename=hit.payload["filename"],
            chunk_index=hit.payload["chunk_index"],
            text=hit.payload["text"],
            score=hit.score,
        )
        for hit in search_result.points
    ]

    return SemanticSearchResponse(query=request.query, results=results)
