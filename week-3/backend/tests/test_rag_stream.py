import asyncio
import json

import app.messages.routes as message_routes


def _event_payload(event: str) -> dict[str, str]:
    return json.loads(event.removeprefix("data: ").strip())


def test_rag_stream_reports_missing_groq_configuration(monkeypatch):
    monkeypatch.delenv("GROQ_API_KEY", raising=False)

    async def collect_events():
        return [
            event
            async for event in message_routes.generate_rag_stream(
                session_id=1,
                user_message="hello",
                user_id=1,
            )
        ]

    events = asyncio.run(collect_events())

    assert "GROQ_API_KEY" in _event_payload(events[0])["error"]
    assert events[1] == "data: [DONE]\n\n"


def test_rag_stream_reports_context_retrieval_failure(monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "test-key")

    async def fail_context(*args):
        raise RuntimeError("private backend detail")

    monkeypatch.setattr(message_routes, "_get_rag_context", fail_context)

    async def collect_events():
        return [
            event
            async for event in message_routes.generate_rag_stream(
                session_id=1,
                user_message="hello",
                user_id=1,
            )
        ]

    events = asyncio.run(collect_events())

    assert _event_payload(events[0])["error"] == (
        "The assistant could not complete this response while "
        "retrieving document context. Check the backend logs."
    )
    assert "private backend detail" not in events[0]
    assert events[1] == "data: [DONE]\n\n"
