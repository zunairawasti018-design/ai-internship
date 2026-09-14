from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase


DATABASE_URL = "postgresql+asyncpg://postgres:password@localhost:5432/mydatabase"


class Base(DeclarativeBase):
    pass


engine = create_async_engine(
    DATABASE_URL,
    echo=True
)


AsyncSessionLocal = async_sessionmaker(
    engine,
    expire_on_commit=False
)