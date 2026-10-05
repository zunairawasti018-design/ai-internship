from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Document(Base):
    __tablename__ = "documents"

    id: Mapped[int] = mapped_column(primary_key=True)

    filename: Mapped[str] = mapped_column(String(255))

    file_path: Mapped[str] = mapped_column(String(500))

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id"), nullable=False
    )

    session_id: Mapped[int] = mapped_column(
        ForeignKey("chat_sessions.id"), nullable=False
    )

    # Ingestion lifecycle: pending → processing → done | failed
    ingestion_status: Mapped[str] = mapped_column(
        String(20), default="pending", server_default="pending"
    )

    # Non-null only when ingestion_status == "failed"
    ingestion_error: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    user = relationship("User", back_populates="documents")

    chat_session = relationship("ChatSession", back_populates="documents")