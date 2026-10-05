from contextlib import asynccontextmanager
from typing import AsyncGenerator

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

load_dotenv()

from app.auth.routes import router as auth_router
from app.chat_sessions import router as chat_sessions_router
from app.messages import router as messages_router
from app.documents import router as documents_router
from app.qdrant_client import init_qdrant, close_qdrant


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Initialise Qdrant collection on startup; close cleanly on shutdown."""
    await init_qdrant()
    yield
    await close_qdrant()


app = FastAPI(
    title="Week 3 RAG Backend API",
    description=(
        "Complete CRUD API with authentication for chat sessions, messages, "
        "and multi-tenant document ingestion via Qdrant."
    ),
    version="2.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:3001",
        "http://127.0.0.1:3001",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


app.include_router(auth_router)
app.include_router(chat_sessions_router)
app.include_router(messages_router)
app.include_router(documents_router)


@app.get("/")
async def root():
    return {"message": "API is running", "version": "2.0.0"}