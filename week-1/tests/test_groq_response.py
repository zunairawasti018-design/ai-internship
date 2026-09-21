import os

from app.messages.routes import generate_assistant_reply


def test_generate_assistant_reply_uses_fallback_without_groq_key(monkeypatch):
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    monkeypatch.delenv("GROQ_MODEL", raising=False)

    reply = generate_assistant_reply("Explain the project in one sentence.")

    assert isinstance(reply, str)
    assert len(reply) > 0
    assert "Groq" in reply or "couldn't reach" in reply.lower() or "assistant" in reply.lower()
