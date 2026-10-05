import os
import logging
import json
import asyncio
from typing import AsyncGenerator

from dotenv import load_dotenv
from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from groq import APIStatusError, Groq, AsyncGroq
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from qdrant_client.http.models import Filter, FieldCondition, MatchValue

from app.dependencies import get_db, get_current_user
from app.models.chat_session import ChatSession
from app.models.message import Message
from app.models.user import User
from app.qdrant_client import get_qdrant, COLLECTION_NAME
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
    model = os.getenv("GROQ_MODEL", "openai/gpt-oss-20b")

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


async def _get_rag_context(query: str, user_id: int, session_id: int) -> str:
    from app.ingestion.pipeline import _get_model
    model = await _get_model()
    loop = asyncio.get_running_loop()
    query_vector = (await loop.run_in_executor(None, lambda: model.encode([query], convert_to_numpy=True)))[0].tolist()

    search_filter = Filter(must=[
        FieldCondition(key="user_id", match=MatchValue(value=user_id)),
        FieldCondition(key="session_id", match=MatchValue(value=session_id)),
    ])

    client = get_qdrant()
    search_result = await client.query_points(
        collection_name=COLLECTION_NAME,
        query=query_vector,
        query_filter=search_filter,
        limit=5,
        with_payload=True,
    )
    hits = search_result.points

    if not hits:
        return ""

    context_parts = []
    for hit in hits:
        context_parts.append(hit.payload["text"])

    return "\n\n---\n\n".join(context_parts)

async def generate_rag_stream(session_id: int, user_message: str, user_id: int) -> AsyncGenerator[str, None]:
    api_key = os.getenv("GROQ_API_KEY")
    model = os.getenv("GROQ_MODEL", "openai/gpt-oss-20b")

    if not api_key:
        yield f"data: {json.dumps({'error': 'The assistant is not configured. Set GROQ_API_KEY on the backend.'})}\n\n"
        yield "data: [DONE]\n\n"
        return

    full_response = ""
    stage = "retrieving document context"
    try:
        context = await _get_rag_context(user_message, user_id, session_id)

        prompt = f"User Query: {user_message}"
        if context:
            prompt = f"Context information is below.\n---------------------\n{context}\n---------------------\nGiven the context information and no prior knowledge, answer the user's query.\n\nUser Query: {user_message}"

        client = AsyncGroq(api_key=api_key)
        stage = "streaming the Groq response"
        stream = await client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": "You are a helpful assistant for a chat application. Keep answers concise, useful, and markdown-friendly."},
                {"role": "user", "content": prompt},
            ],
            temperature=0.7,
            max_tokens=512,
            stream=True,
        )

        async for chunk in stream:
            content = chunk.choices[0].delta.content
            if content:
                full_response += content
                yield f"data: {json.dumps({'text': content})}\n\n"

        stage = "saving the assistant response"
        from app.database import AsyncSessionLocal
        async with AsyncSessionLocal() as db:
            db_assistant_message = Message(content=full_response, role="assistant", session_id=session_id)
            db.add(db_assistant_message)
            await db.commit()

    except APIStatusError as exc:
        logger.error("Assistant response failed while %s (Groq status=%d).", stage, exc.status_code, exc_info=True)
        if exc.status_code == 404:
            error = f"Groq model '{model}' is unavailable. Set GROQ_MODEL to a model enabled for this API key."
        elif exc.status_code in (401, 403):
            error = "Groq rejected the configured API key. Check GROQ_API_KEY on the backend."
        elif exc.status_code == 429:
            error = "Groq rate limit reached. Please wait briefly and try again."
        else:
            error = "Groq could not complete the response. Check the backend logs for details."
        yield f"data: {json.dumps({'error': error})}\n\n"
    except Exception:
        logger.exception("Assistant response failed while %s.", stage)
        yield f"data: {json.dumps({'error': f'The assistant could not complete this response while {stage}. Check the backend logs.'})}\n\n"

    yield "data: [DONE]\n\n"

router = APIRouter(
    prefix="/chat-sessions",
    tags=["Messages"],
)


@router.post(
    "/{session_id}/messages",
    summary="Create a new message in a chat session and stream response via SSE",
)
async def create_message(
    session_id: int,
    message_data: MessageCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Create a new message in an existing chat session and stream the assistant's reply.

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

    db.add(db_message)
    await db.commit()
    await db.refresh(db_message)

    if message_data.role != "user":
        async def empty_stream():
            yield "data: [DONE]\n\n"
        return StreamingResponse(empty_stream(), media_type="text/event-stream")

    return StreamingResponse(
        generate_rag_stream(session_id, message_data.content, current_user.id),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


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
