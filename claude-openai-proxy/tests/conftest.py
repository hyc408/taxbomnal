"""pytest 공용 픽스처.

실제 Claude/OAuth 호출 없이 동작하도록 `claude_client` 를 mock 한다.
따라서 무인/CI 환경에서도 통과한다.
"""

from __future__ import annotations

from typing import AsyncGenerator

import pytest
from fastapi.testclient import TestClient

from app import claude_client
from app.claude_client import ClaudeResult
from app.main import app


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


@pytest.fixture
def mock_claude(monkeypatch: pytest.MonkeyPatch):
    """create_completion / stream_completion 을 결정적 응답으로 대체한다."""

    async def fake_create_completion(messages, model, temperature=None, max_tokens=None):
        # 마지막 사용자 메시지를 되돌려주는 형태로 응답을 만든다.
        last = messages[-1].content if messages else ""
        return ClaudeResult(
            text=f"echo: {last}",
            input_tokens=5,
            output_tokens=3,
            finish_reason="stop",
            model=model,
        )

    async def fake_stream_completion(
        messages, model, temperature=None, max_tokens=None
    ) -> AsyncGenerator[str, None]:
        for token in ["Hello", ", ", "world"]:
            yield token

    monkeypatch.setattr(claude_client, "create_completion", fake_create_completion)
    monkeypatch.setattr(claude_client, "stream_completion", fake_stream_completion)
    return monkeypatch
