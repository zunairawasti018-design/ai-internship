from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class MessageBase(BaseModel):
    """Base schema for messages."""
    content: str = Field(..., min_length=1, max_length=5000, description="Message content")
    role: str = Field(..., pattern="^(user|assistant|system)$", description="Message role (user/assistant/system)")


class MessageCreate(MessageBase):
    """Schema for creating a new message."""
    session_id: int = Field(..., gt=0, description="ID of the chat session")


class MessageUpdate(BaseModel):
    """Schema for updating a message."""
    content: Optional[str] = Field(None, min_length=1, max_length=5000, description="Updated content")

    model_config = ConfigDict(extra="forbid")


class MessageResponse(MessageBase):
    """Schema for message response."""
    id: int = Field(..., description="Unique identifier")
    session_id: int = Field(..., description="Associated session ID")

    model_config = ConfigDict(
        from_attributes=True,
        serialize_as_any=False
    )


class MessageListResponse(BaseModel):
    """Schema for paginated message list response."""
    total: int = Field(..., ge=0, description="Total number of messages")
    count: int = Field(..., ge=0, description="Number of items in this response")
    items: list[MessageResponse] = Field(default_factory=list, description="List of messages")

    model_config = ConfigDict(extra="forbid")
