from fastapi import FastAPI

from app.auth.routes import router as auth_router
from app.chat_sessions import router as chat_sessions_router
from app.messages import router as messages_router


app = FastAPI(
    title="Week 1 Backend API",
    description="Complete CRUD API with authentication for chat sessions and messages",
    version="1.0.0"
)


app.include_router(auth_router)
app.include_router(chat_sessions_router)
app.include_router(messages_router)


@app.get("/")
async def root():
    return {
        "message": "API is running"
    }