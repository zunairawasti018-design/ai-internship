from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class ChatSessionBase(BaseModel):
    """Base schema for chat session with common fields."""
    title: str = Field(..., min_length=1, max_length=200, description="Title of the chat session")
    user_id: int = Field(..., gt=0, description="ID of the user who owns this session")


class ChatSessionCreate(ChatSessionBase):
    """Schema for creating a new chat session."""
    pass


class ChatSessionUpdate(BaseModel):
    """Schema for updating an existing chat session."""
    title: Optional[str] = Field(None, min_length=1, max_length=200, description="Updated title")

    model_config = ConfigDict(extra="forbid")


class ChatSessionResponse(ChatSessionBase):
    """Schema for chat session response with Pydantic v2 serialization."""
    id: int = Field(..., description="Unique identifier")
    created_at: datetime = Field(..., description="When the session was created")
    updated_at: datetime = Field(..., description="When the session was last updated")

    model_config = ConfigDict(
        from_attributes=True,
        serialize_as_any=False
    )


class ChatSessionDetailResponse(ChatSessionResponse):
    """Detailed schema for chat session with nested data."""
    pass


class ChatSessionListResponse(BaseModel):
    """Schema for paginated list response."""
    total: int = Field(..., ge=0, description="Total number of sessions")
    count: int = Field(..., ge=0, description="Number of items in this response")
    items: list[ChatSessionResponse] = Field(default_factory=list, description="List of sessions")

    model_config = ConfigDict(extra="forbid")
