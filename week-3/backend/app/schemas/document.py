"""Pydantic schemas for document upload and retrieval."""

from __future__ import annotations

from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field


IngestionStatus = Literal["pending", "processing", "done", "failed"]


class DocumentUploadResponse(BaseModel):
    """Response returned immediately after a document upload (202 Accepted)."""

    id: int = Field(..., description="Database ID of the created document record")
    filename: str = Field(..., description="Original filename as uploaded")
    session_id: int = Field(..., description="Chat session this document is linked to")
    user_id: int = Field(..., description="Owner's user ID")
    ingestion_status: IngestionStatus = Field(
        ..., description="Current ingestion status (starts as 'pending')"
    )
    created_at: datetime = Field(..., description="Upload timestamp")

    model_config = ConfigDict(from_attributes=True)


class DocumentStatusResponse(DocumentUploadResponse):
    """Response with full status info, including any error message."""

    ingestion_error: Optional[str] = Field(
        None, description="Error message if ingestion failed"
    )


class DocumentListResponse(BaseModel):
    """Paginated list of documents."""

    total: int = Field(..., ge=0)
    count: int = Field(..., ge=0)
    items: list[DocumentStatusResponse]

    model_config = ConfigDict(extra="forbid")


class ChunkResult(BaseModel):
    """A single retrieved text chunk from Qdrant."""

    document_id: int
    filename: str
    chunk_index: int
    text: str
    score: float = Field(..., description="Cosine similarity score (0–1)")


class SemanticSearchResponse(BaseModel):
    """Response for semantic similarity search."""

    query: str
    results: list[ChunkResult]
