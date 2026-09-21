import os
import logging
from typing import AsyncGenerator

from dotenv import load_dotenv
from fastapi import APIRouter, Depends, HTTPException, Query, status
from groq import Groq
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.dependencies import get_db, get_current_user
from app.models.chat_session import ChatSession
from app.models.message import Message
from app.models.user import User
from app.schemas import (
    MessageCreate,
    MessageUpdate,
    MessageResponse,
    MessageListResponse,
)


load_dotenv(override=True)

logger = logging.getLogger(__name__)


def generate_assistant_reply(prompt: str) -> str:
    """Generate a reply using Groq if configured, otherwise return a sensible fallback."""
    api_key = os.getenv("GROQ_API_KEY")
    model = os.getenv("GROQ_MODEL", "llama-3.1-8b-instant")

    if not api_key:
        return (
            "I’m ready to help, but the live Groq model isn’t configured yet. "
            "Add GROQ_API_KEY in the backend environment to enable AI replies."
        )

    try:
        client = Groq(api_key=api_key)
        completion = client.chat.completions.create(
            model=model,
            messages=[
                {
                    "role": "system",
                    "content": "You are a helpful assistant for a chat application. Keep answers concise, useful, and markdown-friendly.",
                },
                {"role": "user", "content": prompt},
            ],
            temperature=0.7,
            max_tokens=512,
        )
        reply = completion.choices[0].message.content
        if reply and reply.strip():
            return reply.strip()
    except Exception as e:
        logger.error("Groq API call failed: %s", e, exc_info=True)

    return (
        "I received your message, but Groq is unavailable right now. "
        "Please check the GROQ_API_KEY and model configuration in the backend."
    )


router = APIRouter(
    prefix="/chat-sessions",
    tags=["Messages"],
)


@router.post(
    "/{session_id}/messages",
    response_model=MessageResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new message in a chat session",
)
async def create_message(
    session_id: int,
    message_data: MessageCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> MessageResponse:
    """
    Create a new message in an existing chat session.

    - **session_id**: ID of the chat session
    - **content**: Message content (1-5000 characters)
    - **role**: Message role (user/assistant/system)
    
    **Permissions**: Only the session owner can add messages
    """
    # Verify session exists and user owns it
    result = await db.execute(
        select(ChatSession).where(ChatSession.id == session_id)
    )
    db_session = result.scalar_one_or_none()

    if db_session is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Chat session with ID {session_id} not found",
        )

    if db_session.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to add messages to this session",
        )

    # Create message
    db_message = Message(
        content=message_data.content,
        role=message_data.role,
        session_id=session_id,
    )

    assistant_reply = ""
    if message_data.role == "user":
        assistant_reply = generate_assistant_reply(message_data.content)

    db_assistant_message = Message(
        content=assistant_reply,
        role="assistant",
        session_id=session_id,
    ) if assistant_reply else None

    db.add(db_message)
    if db_assistant_message is not None:
        db.add(db_assistant_message)

    await db.commit()
    await db.refresh(db_message)
    if db_assistant_message is not None:
        await db.refresh(db_assistant_message)

    return MessageResponse.model_validate(db_message)


@router.get(
    "/{session_id}/messages",
    response_model=MessageListResponse,
    summary="List messages in a chat session with pagination",
)
async def list_messages(
    session_id: int,
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(50, ge=1, le=100, description="Number of records to retrieve"),
    role: str | None = Query(None, pattern="^(user|assistant|system)$", description="Filter by message role"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> MessageListResponse:
    """
    List messages in a chat session with pagination and optional filtering.

    - **session_id**: ID of the chat session
    - **skip**: Number of records to skip (default: 0)
    - **limit**: Number of records to return (default: 50, max: 100)
    - **role**: Optional filter by message role
    
    **Permissions**: Only the session owner can view messages
    """
    # Verify session exists and user owns it
    result = await db.execute(
        select(ChatSession).where(ChatSession.id == session_id)
    )
    db_session = result.scalar_one_or_none()

    if db_session is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Chat session with ID {session_id} not found",
        )

    if db_session.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to view messages in this session",
        )

    # Build query
    query = select(Message).where(Message.session_id == session_id)

    if role:
        query = query.where(Message.role == role)

    # Get total count
    count_query = select(func.count(Message.id)).where(Message.session_id == session_id)
    if role:
        count_query = count_query.where(Message.role == role)

    total_result = await db.execute(count_query)
    total = total_result.scalar_one()

    # Get paginated results
    query = query.offset(skip).limit(limit)
    result = await db.execute(query)
    messages = result.scalars().all()

    return MessageListResponse(
        total=total,
        count=len(messages),
        items=[MessageResponse.model_validate(msg) for msg in messages],
    )


@router.get(
    "/{session_id}/messages/{message_id}",
    response_model=MessageResponse,
    summary="Get a specific message from a session",
)
async def get_message(
    session_id: int,
    message_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> MessageResponse:
    """
    Retrieve a specific message from a chat session.

    - **session_id**: ID of the chat session
    - **message_id**: ID of the message to retrieve
    
    **Permissions**: Only the session owner can view messages
    """
    # Verify session exists and user owns it
    result = await db.execute(
        select(ChatSession).where(ChatSession.id == session_id)
    )
    db_session = result.scalar_one_or_none()

    if db_session is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Chat session with ID {session_id} not found",
        )

    if db_session.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to view messages in this session",
        )

    # Get message
    result = await db.execute(
        select(Message).where(
            (Message.id == message_id) & (Message.session_id == session_id)
        )
    )
    db_message = result.scalar_one_or_none()

    if db_message is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Message with ID {message_id} not found in this session",
        )

    return MessageResponse.model_validate(db_message)


@router.put(
    "/{session_id}/messages/{message_id}",
    response_model=MessageResponse,
    summary="Update a message in a session",
)
async def update_message(
    session_id: int,
    message_id: int,
    update_data: MessageUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> MessageResponse:
    """
    Update an existing message in a chat session.

    - **session_id**: ID of the chat session
    - **message_id**: ID of the message to update
    - **content**: New message content (optional)
    
    **Permissions**: Only the session owner can update messages
    """
    # Verify session exists and user owns it
    result = await db.execute(
        select(ChatSession).where(ChatSession.id == session_id)
    )
    db_session = result.scalar_one_or_none()

    if db_session is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Chat session with ID {session_id} not found",
        )

    if db_session.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to update messages in this session",
        )

    # Get message
    result = await db.execute(
        select(Message).where(
            (Message.id == message_id) & (Message.session_id == session_id)
        )
    )
    db_message = result.scalar_one_or_none()

    if db_message is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Message with ID {message_id} not found in this session",
        )

    # Update fields if provided
    if update_data.content is not None:
        db_message.content = update_data.content

    db.add(db_message)
    await db.commit()
    await db.refresh(db_message)

    return MessageResponse.model_validate(db_message)


@router.delete(
    "/{session_id}/messages/{message_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a message from a session",
)
async def delete_message(
    session_id: int,
    message_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    """
    Delete a specific message from a chat session.

    - **session_id**: ID of the chat session
    - **message_id**: ID of the message to delete
    
    **Permissions**: Only the session owner can delete messages
    """
    # Verify session exists and user owns it
    result = await db.execute(
        select(ChatSession).where(ChatSession.id == session_id)
    )
    db_session = result.scalar_one_or_none()

    if db_session is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Chat session with ID {session_id} not found",
        )

    if db_session.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to delete messages in this session",
        )

    # Get message
    result = await db.execute(
        select(Message).where(
            (Message.id == message_id) & (Message.session_id == session_id)
        )
    )
    db_message = result.scalar_one_or_none()

    if db_message is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Message with ID {message_id} not found in this session",
        )

    await db.delete(db_message)
    await db.commit()
