from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import delete, select, func

from app.dependencies import get_db, get_current_user
from app.models.chat_session import ChatSession
from app.models.message import Message
from app.models.user import User
from app.schemas import (
    ChatSessionCreate,
    ChatSessionUpdate,
    ChatSessionResponse,
    ChatSessionListResponse,
)


router = APIRouter(
    prefix="/chat-sessions",
    tags=["Chat Sessions"],
)


@router.post(
    "",
    response_model=ChatSessionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new chat session",
)
async def create_chat_session(
    chat_session_data: ChatSessionCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ChatSessionResponse:
    """
    Create a new chat session for the authenticated user.

    - **title**: Name of the chat session (required, 1-200 characters)
    - **user_id**: Must match the authenticated user's ID
    
    **Permissions**: Only authenticated users can create sessions
    
    **Error Responses**:
    - 400: Invalid user_id (must match authenticated user)
    - 401: Unauthorized (invalid or missing JWT token)
    - 422: Validation error (title length, etc.)
    """
    # Verify user_id matches authenticated user
    if chat_session_data.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot create session for another user",
        )

    # Create new chat session instance
    db_chat_session = ChatSession(
        title=chat_session_data.title,
        user_id=chat_session_data.user_id,
    )

    db.add(db_chat_session)
    await db.commit()
    await db.refresh(db_chat_session)

    return ChatSessionResponse.model_validate(db_chat_session)


@router.get(
    "",
    response_model=ChatSessionListResponse,
    summary="List authenticated user's chat sessions",
)
async def list_chat_sessions(
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(10, ge=1, le=100, description="Number of records to retrieve"),
    title: str | None = Query(None, max_length=200, description="Filter by title (partial match)"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ChatSessionListResponse:
    """
    List chat sessions for the authenticated user with pagination and optional filtering.

    - **skip**: Number of records to skip (default: 0)
    - **limit**: Number of records to return (default: 10, max: 100)
    - **title**: Optional partial title filter
    
    **Permissions**: Only authenticated users can list their own sessions
    """
    query = select(ChatSession).where(ChatSession.user_id == current_user.id)

    if title:
        query = query.where(ChatSession.title.ilike(f"%{title}%"))

    # Get total count
    count_query = select(func.count(ChatSession.id)).where(
        ChatSession.user_id == current_user.id
    )
    if title:
        count_query = count_query.where(ChatSession.title.ilike(f"%{title}%"))

    total_result = await db.execute(count_query)
    total = total_result.scalar_one()

    # Get paginated results
    query = query.offset(skip).limit(limit).order_by(ChatSession.created_at.desc())
    result = await db.execute(query)
    sessions = result.scalars().all()

    return ChatSessionListResponse(
        total=total,
        count=len(sessions),
        items=[
            ChatSessionResponse.model_validate(session) for session in sessions
        ],
    )


@router.get(
    "/{session_id}",
    response_model=ChatSessionResponse,
    summary="Get a specific chat session",
)
async def get_chat_session(
    session_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ChatSessionResponse:
    """
    Retrieve a specific chat session by its ID.

    - **session_id**: The ID of the chat session to retrieve
    
    **Permissions**: Only the session owner can view it
    
    **Error Responses**:
    - 404: Session not found
    - 403: Forbidden (session belongs to another user)
    - 401: Unauthorized
    """
    result = await db.execute(
        select(ChatSession).where(ChatSession.id == session_id)
    )
    db_session = result.scalar_one_or_none()

    if db_session is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Chat session with ID {session_id} not found",
        )

    # Verify ownership
    if db_session.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to view this session",
        )

    return ChatSessionResponse.model_validate(db_session)


@router.put(
    "/{session_id}",
    response_model=ChatSessionResponse,
    summary="Update a chat session",
)
async def update_chat_session(
    session_id: int,
    update_data: ChatSessionUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ChatSessionResponse:
    """
    Update an existing chat session.

    - **session_id**: The ID of the chat session to update
    - **title**: New title (optional)
    
    **Permissions**: Only the session owner can update it
    
    **Error Responses**:
    - 404: Session not found
    - 403: Forbidden (session belongs to another user)
    - 401: Unauthorized
    """
    result = await db.execute(
        select(ChatSession).where(ChatSession.id == session_id)
    )
    db_session = result.scalar_one_or_none()

    if db_session is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Chat session with ID {session_id} not found",
        )

    # Verify ownership
    if db_session.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to update this session",
        )

    # Update fields if provided
    if update_data.title is not None:
        db_session.title = update_data.title

    db.add(db_session)
    await db.commit()
    await db.refresh(db_session)

    return ChatSessionResponse.model_validate(db_session)


@router.patch(
    "/{session_id}",
    response_model=ChatSessionResponse,
    summary="Partially update a chat session",
)
async def patch_chat_session(
    session_id: int,
    update_data: ChatSessionUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ChatSessionResponse:
    """
    Partially update a chat session (same as PUT).

    - **session_id**: The ID of the chat session to update
    - **title**: New title (optional)
    
    **Permissions**: Only the session owner can update it
    """
    return await update_chat_session(session_id, update_data, current_user, db)


@router.delete(
    "/{session_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a chat session",
)
async def delete_chat_session(
    session_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    """
    Delete a specific chat session by its ID.

    - **session_id**: The ID of the chat session to delete
    
    **Permissions**: Only the session owner can delete it
    
    **Note**: Deleting a session also deletes all associated messages (cascade delete)
    
    **Error Responses**:
    - 404: Session not found
    - 403: Forbidden (session belongs to another user)
    - 401: Unauthorized
    """
    result = await db.execute(
        select(ChatSession).where(ChatSession.id == session_id)
    )
    db_session = result.scalar_one_or_none()

    if db_session is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Chat session with ID {session_id} not found",
        )

    # Verify ownership
    if db_session.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to delete this session",
        )

    await db.execute(delete(Message).where(Message.session_id == session_id))
    await db.execute(delete(ChatSession).where(ChatSession.id == session_id))
    await db.commit()
