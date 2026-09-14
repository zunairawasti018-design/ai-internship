from sqlalchemy import String, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Document(Base):
    __tablename__ = "documents"

    id: Mapped[int] = mapped_column(primary_key=True)

    filename: Mapped[str] = mapped_column(String(255))

    file_path: Mapped[str] = mapped_column(String(500))

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id")
    )

    user = relationship(
        "User",
        back_populates="documents"
    )