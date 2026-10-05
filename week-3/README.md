# Week 3 — Real-Time RAG Application

An interactive full-stack RAG application where users upload documents and ask questions with live, token-by-token streaming responses.

## Features

- JWT-authenticated chat sessions and messages
- PDF and text document uploads with background parsing, chunking, and embedding
- Qdrant vector storage and retrieval scoped to the authenticated user and chat session
- Groq-powered answers streamed to the browser over Server-Sent Events
- Live ingestion status, automatic chat scrolling, and cancel-generation support

## Project layout

- `backend/` — FastAPI, PostgreSQL, Qdrant, document ingestion, and SSE chat API
- `frontend/` — Next.js chat, session management, document uploads, and streaming UI

## Run locally

### 1. Start PostgreSQL and Qdrant

From `week-3/backend`:

```powershell
docker compose up -d
```

### 2. Configure and start the backend

From `week-3/backend`, create a virtual environment, install dependencies, and prepare a local environment file:

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
```

Edit `.env` and set `SECRET_KEY` to a long random value. Set `GROQ_API_KEY` to a Groq API key to enable AI answers. Then run:

```powershell
alembic upgrade head
uvicorn app.main:app --reload
```

The API and Swagger UI are available at `http://127.0.0.1:8000` and `http://127.0.0.1:8000/docs`.

### 3. Configure and start the frontend

From `week-3/frontend`:

```powershell
npm ci
Copy-Item .env.example .env.local
npm run dev
```

Open `http://localhost:3000`, register an account, create a chat, upload a PDF or text file, and ask a question about it.

## Run checks

From `week-3/backend`:

```powershell
python -m pytest tests -q
```

From `week-3/frontend`:

```powershell
npm run lint
npm run build
```

The embedding model (`all-MiniLM-L6-v2`) is downloaded by Sentence Transformers the first time it is needed. Keep `.env`, `.env.local`, uploaded documents, and local virtual environments out of Git.
