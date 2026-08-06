"""OpenAI 호환 요청/응답 Pydantic 스키마.

OpenAI Chat Completions API 형식을 최대한 그대로 따른다.
"""

from __future__ import annotations

from typing import Literal, Optional, Union

from pydantic import BaseModel, Field

# ---------------------------------------------------------------------------
# 모델 별칭 매핑
# ---------------------------------------------------------------------------
# 외부에 공개하는 별칭 -> Claude CLI 가 인식하는 실제 모델 식별자(별칭)
# CLI 는 "opus"/"sonnet"/"haiku" 같은 짧은 별칭을 최신 모델로 해석한다.
MODEL_ALIASES: dict[str, str] = {
    "claude-opus": "opus",
    "claude-sonnet": "sonnet",
    "claude-haiku": "haiku",
}

# /v1/models 에 노출할 모델 목록
EXPOSED_MODELS: list[str] = list(MODEL_ALIASES.keys())

# 매핑에 없는 모델명이 오면 그대로 CLI 에 전달(passthrough)한다.
DEFAULT_MODEL = "claude-sonnet"


def resolve_model(name: Optional[str]) -> str:
    """공개 모델명을 CLI 용 모델 식별자로 변환한다.

    별칭 테이블에 있으면 매핑값을, 없으면 입력값을 그대로 반환한다.
    None/빈 값이면 기본 모델을 사용한다.
    """
    if not name:
        name = DEFAULT_MODEL
    return MODEL_ALIASES.get(name, name)


# ---------------------------------------------------------------------------
# 요청 스키마
# ---------------------------------------------------------------------------
class ChatMessage(BaseModel):
    """대화 메시지 한 건."""

    role: Literal["system", "user", "assistant", "tool", "function"]
    # content 는 문자열 또는 멀티모달 파트 배열이 올 수 있다.
    content: Union[str, list[dict], None] = None
    name: Optional[str] = None


class ChatCompletionRequest(BaseModel):
    """POST /v1/chat/completions 요청 본문."""

    model: str = Field(default=DEFAULT_MODEL)
    messages: list[ChatMessage]
    temperature: Optional[float] = None
    top_p: Optional[float] = None
    max_tokens: Optional[int] = None
    stream: bool = False
    stop: Optional[Union[str, list[str]]] = None
    # 아래 필드들은 호환성을 위해 수용하되 현재 프록시에서 사용하지 않을 수 있다.
    n: Optional[int] = None
    presence_penalty: Optional[float] = None
    frequency_penalty: Optional[float] = None
    user: Optional[str] = None


# ---------------------------------------------------------------------------
# 응답 스키마 (비스트리밍)
# ---------------------------------------------------------------------------
class Usage(BaseModel):
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0


class ChatCompletionResponseMessage(BaseModel):
    role: Literal["assistant"] = "assistant"
    content: str = ""


class ChatCompletionChoice(BaseModel):
    index: int = 0
    message: ChatCompletionResponseMessage
    finish_reason: Optional[str] = "stop"


class ChatCompletionResponse(BaseModel):
    id: str
    object: Literal["chat.completion"] = "chat.completion"
    created: int
    model: str
    choices: list[ChatCompletionChoice]
    usage: Usage


# ---------------------------------------------------------------------------
# 응답 스키마 (스트리밍 청크)
# ---------------------------------------------------------------------------
class DeltaMessage(BaseModel):
    role: Optional[str] = None
    content: Optional[str] = None


class ChatCompletionChunkChoice(BaseModel):
    index: int = 0
    delta: DeltaMessage
    finish_reason: Optional[str] = None


class ChatCompletionChunk(BaseModel):
    id: str
    object: Literal["chat.completion.chunk"] = "chat.completion.chunk"
    created: int
    model: str
    choices: list[ChatCompletionChunkChoice]


# ---------------------------------------------------------------------------
# /v1/models 스키마
# ---------------------------------------------------------------------------
class ModelCard(BaseModel):
    id: str
    object: Literal["model"] = "model"
    created: int
    owned_by: str = "anthropic"


class ModelList(BaseModel):
    object: Literal["list"] = "list"
    data: list[ModelCard]
