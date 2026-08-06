"""Chat Completion (스트리밍/SSE) 테스트 — SDK Mock 기반."""

from __future__ import annotations

import json

from fastapi.testclient import TestClient


def _parse_sse(raw: str) -> list[str]:
    """SSE 본문에서 `data:` 페이로드들을 추출한다."""
    payloads: list[str] = []
    for line in raw.splitlines():
        line = line.strip()
        if line.startswith("data:"):
            payloads.append(line[len("data:") :].strip())
    return payloads


def test_chat_completion_streaming(client: TestClient, mock_claude) -> None:
    resp = client.post(
        "/v1/chat/completions",
        json={
            "model": "claude-haiku",
            "messages": [{"role": "user", "content": "Hi"}],
            "stream": True,
        },
    )
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/event-stream")

    payloads = _parse_sse(resp.text)
    assert payloads, "SSE 페이로드가 비어 있음"
    assert payloads[-1] == "[DONE]"

    # 첫 청크는 role 델타여야 한다.
    first = json.loads(payloads[0])
    assert first["object"] == "chat.completion.chunk"
    assert first["choices"][0]["delta"].get("role") == "assistant"

    # content 델타들을 이어붙이면 mock 응답과 같아야 한다.
    text = ""
    saw_finish = False
    for p in payloads[1:-1]:
        chunk = json.loads(p)
        delta = chunk["choices"][0]["delta"]
        if delta.get("content"):
            text += delta["content"]
        if chunk["choices"][0].get("finish_reason") == "stop":
            saw_finish = True

    assert text == "Hello, world"
    assert saw_finish
