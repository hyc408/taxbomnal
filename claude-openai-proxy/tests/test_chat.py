"""Chat Completion (비스트리밍) 테스트 — SDK Mock 기반."""

from __future__ import annotations

from fastapi.testclient import TestClient


def test_chat_completion_basic(client: TestClient, mock_claude) -> None:
    resp = client.post(
        "/v1/chat/completions",
        json={
            "model": "claude-sonnet",
            "messages": [{"role": "user", "content": "Hello"}],
            "temperature": 0.2,
            "stream": False,
        },
    )
    assert resp.status_code == 200
    body = resp.json()

    # OpenAI 형식 필드 검증
    assert body["object"] == "chat.completion"
    assert body["model"] == "claude-sonnet"
    assert body["id"].startswith("chatcmpl-")
    assert isinstance(body["created"], int)

    choice = body["choices"][0]
    assert choice["index"] == 0
    assert choice["finish_reason"] == "stop"
    assert choice["message"]["role"] == "assistant"
    assert choice["message"]["content"] == "echo: Hello"

    usage = body["usage"]
    assert usage["prompt_tokens"] == 5
    assert usage["completion_tokens"] == 3
    assert usage["total_tokens"] == 8


def test_chat_completion_empty_messages(client: TestClient, mock_claude) -> None:
    resp = client.post(
        "/v1/chat/completions",
        json={"model": "claude-sonnet", "messages": []},
    )
    assert resp.status_code == 400


def test_chat_completion_requires_auth_when_configured(
    client: TestClient, mock_claude, monkeypatch
) -> None:
    # PROXY_API_KEY 를 설정하면 인증을 요구해야 한다.
    from app.config import get_settings

    get_settings.cache_clear()
    monkeypatch.setenv("PROXY_API_KEY", "secret-token")
    get_settings.cache_clear()

    try:
        # 토큰 없음 → 401
        resp = client.post(
            "/v1/chat/completions",
            json={"model": "claude-sonnet", "messages": [{"role": "user", "content": "hi"}]},
        )
        assert resp.status_code == 401

        # 올바른 토큰 → 200
        resp = client.post(
            "/v1/chat/completions",
            headers={"Authorization": "Bearer secret-token"},
            json={"model": "claude-sonnet", "messages": [{"role": "user", "content": "hi"}]},
        )
        assert resp.status_code == 200
    finally:
        get_settings.cache_clear()
