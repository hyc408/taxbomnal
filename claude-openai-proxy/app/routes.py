"""API 라우트 정의.

엔드포인트:
    GET  /                    서비스 정보
    GET  /health              상태 확인
    GET  /v1/models           모델 목록
    POST /v1/chat/completions Chat Completion (스트리밍/비스트리밍)
"""

from __future__ import annotations

import json
import logging
import time
import uuid
from typing import AsyncGenerator, Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from fastapi.responses import StreamingResponse

from . import claude_client
from .config import Settings, get_settings
from .models import (
    EXPOSED_MODELS,
    ChatCompletionChoice,
    ChatCompletionChunk,
    ChatCompletionChunkChoice,
    ChatCompletionRequest,
    ChatCompletionResponse,
    ChatCompletionResponseMessage,
    DeltaMessage,
    ModelCard,
    ModelList,
    Usage,
)

logger = logging.getLogger("claude_proxy.routes")

router = APIRouter()


# ---------------------------------------------------------------------------
# 인증 의존성
# ---------------------------------------------------------------------------
def verify_auth(
    authorization: Optional[str] = Header(default=None),
    settings: Settings = Depends(get_settings),
) -> None:
    """프록시 접근 토큰을 검증한다.

    `PROXY_API_KEY` 가 설정된 경우에만 `Authorization: Bearer <token>` 을
    요구한다. 비어 있으면 인증을 건너뛴다(내부 신뢰 네트워크 전용).
    """
    expected = settings.proxy_api_key
    if not expected:
        return  # 인증 비활성화

    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Missing bearer token")
    token = authorization.split(" ", 1)[1].strip()
    if token != expected:
        raise HTTPException(status_code=401, detail="Invalid API key")


# ---------------------------------------------------------------------------
# 기본 엔드포인트
# ---------------------------------------------------------------------------
@router.get("/")
async def root() -> dict:
    """서비스 소개."""
    return {
        "service": "claude-openai-proxy",
        "description": "OpenAI-compatible proxy backed by Claude Code (OAuth).",
        "endpoints": ["/health", "/v1/models", "/v1/chat/completions"],
    }


@router.get("/health")
async def health() -> dict:
    """상태 확인. Claude SDK 가용 여부를 함께 보고한다."""
    return {
        "status": "ok",
        "sdk_available": claude_client.sdk_available(),
    }


@router.get("/v1/models", response_model=ModelList)
async def list_models() -> ModelList:
    """지원 모델 목록을 반환한다."""
    created = int(time.time())
    return ModelList(
        data=[ModelCard(id=name, created=created) for name in EXPOSED_MODELS]
    )


# ---------------------------------------------------------------------------
# Chat Completions
# ---------------------------------------------------------------------------
def _new_id() -> str:
    return f"chatcmpl-{uuid.uuid4().hex}"


@router.post("/v1/chat/completions", dependencies=[Depends(verify_auth)])
async def chat_completions(req: ChatCompletionRequest, request: Request):
    """OpenAI 형식 Chat Completion 처리."""
    if not req.messages:
        raise HTTPException(status_code=400, detail="`messages` must not be empty")

    if req.stream:
        return StreamingResponse(
            _stream_response(req),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )
    return await _full_response(req)


async def _full_response(req: ChatCompletionRequest) -> ChatCompletionResponse:
    """비스트리밍 응답 생성."""
    try:
        result = await claude_client.create_completion(
            messages=req.messages,
            model=req.model,
            temperature=req.temperature,
            max_tokens=req.max_tokens,
        )
    except Exception as exc:  # noqa: BLE001 - 상위에서 500 으로 변환
        logger.exception("chat completion 실패")
        raise HTTPException(status_code=502, detail=f"Claude 호출 실패: {exc}")

    usage = Usage(
        prompt_tokens=result.input_tokens,
        completion_tokens=result.output_tokens,
        total_tokens=result.input_tokens + result.output_tokens,
    )
    return ChatCompletionResponse(
        id=_new_id(),
        created=int(time.time()),
        model=req.model,
        choices=[
            ChatCompletionChoice(
                index=0,
                message=ChatCompletionResponseMessage(content=result.text),
                finish_reason=result.finish_reason,
            )
        ],
        usage=usage,
    )


async def _stream_response(
    req: ChatCompletionRequest,
) -> AsyncGenerator[str, None]:
    """SSE 스트리밍 응답 생성기.

    OpenAI 스트리밍 규약을 따른다:
      1) 첫 청크에 role 델타
      2) 이후 content 델타들
      3) finish_reason 청크
      4) `data: [DONE]`
    """
    chunk_id = _new_id()
    created = int(time.time())
    model = req.model

    def _sse(chunk: ChatCompletionChunk) -> str:
        return f"data: {chunk.model_dump_json()}\n\n"

    # 1) role 델타
    yield _sse(
        ChatCompletionChunk(
            id=chunk_id,
            created=created,
            model=model,
            choices=[
                ChatCompletionChunkChoice(index=0, delta=DeltaMessage(role="assistant"))
            ],
        )
    )

    try:
        async for text in claude_client.stream_completion(
            messages=req.messages,
            model=req.model,
            temperature=req.temperature,
            max_tokens=req.max_tokens,
        ):
            yield _sse(
                ChatCompletionChunk(
                    id=chunk_id,
                    created=created,
                    model=model,
                    choices=[
                        ChatCompletionChunkChoice(
                            index=0, delta=DeltaMessage(content=text)
                        )
                    ],
                )
            )
    except Exception as exc:  # noqa: BLE001
        logger.exception("streaming 실패")
        # 스트림 도중 오류는 OpenAI 형식 에러 이벤트로 전달
        err = {"error": {"message": str(exc), "type": "upstream_error"}}
        yield f"data: {json.dumps(err, ensure_ascii=False)}\n\n"
        yield "data: [DONE]\n\n"
        return

    # 3) 종료 델타
    yield _sse(
        ChatCompletionChunk(
            id=chunk_id,
            created=created,
            model=model,
            choices=[
                ChatCompletionChunkChoice(
                    index=0, delta=DeltaMessage(), finish_reason="stop"
                )
            ],
        )
    )
    # 4) 종료 신호
    yield "data: [DONE]\n\n"
