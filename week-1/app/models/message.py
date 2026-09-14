from sqlalchemy import String, ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Message(Base):
    __tablename__ = "messages"

    id: Mapped[int] = mapped_column(primary_key=True)

    content: Mapped[str] = mapped_column(Text)

    role: Mapped[str] = mapped_column(String(50))

    session_id: Mapped[int] = mapped_column(
        ForeignKey("chat_sessions.id")
    )

    chat_session = relationship(
        "ChatSession",
        back_populates="messages"
    )