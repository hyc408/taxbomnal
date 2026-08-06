"""Health / 기본 엔드포인트 / 모델 목록 테스트."""

from __future__ import annotations

from fastapi.testclient import TestClient


def test_root(client: TestClient) -> None:
    resp = client.get("/")
    assert resp.status_code == 200
    body = resp.json()
    assert body["service"] == "claude-openai-proxy"
    assert "/v1/chat/completions" in body["endpoints"]


def test_health(client: TestClient) -> None:
    resp = client.get("/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert "sdk_available" in body


def test_list_models(client: TestClient) -> None:
    resp = client.get("/v1/models")
    assert resp.status_code == 200
    body = resp.json()
    assert body["object"] == "list"
    ids = {m["id"] for m in body["data"]}
    assert {"claude-opus", "claude-sonnet", "claude-haiku"} <= ids
