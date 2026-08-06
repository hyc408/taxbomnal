"""Claude Code SDK 래퍼 (OAuth 재사용).

이 모듈이 `claude-agent-sdk` 와 직접 상호작용하는 유일한 지점이다.
SDK 는 내부적으로 `claude` CLI 를 서브프로세스로 실행하며, CLI 가 보유한
OAuth 인증(`claude login`)을 그대로 재사용한다. 즉 이 프록시는 Anthropic
API Key 를 사용하지 않는다.

OpenAI Chat Completions 요청을 Claude 호출로 변환하는 어댑터 로직을 담는다.
라우터는 이 모듈의 `create_completion` / `stream_completion` 만 호출하므로
테스트에서 손쉽게 mock 할 수 있다.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import AsyncGenerator, Optional

from .models import ChatMessage, resolve_model

logger = logging.getLogger("claude_proxy.client")


@dataclass
class ClaudeResult:
    """Claude 응답 집계 결과(비스트리밍용)."""

    text: str = ""
    input_tokens: int = 0
    output_tokens: int = 0
    finish_reason: str = "stop"
    model: str = ""


# ---------------------------------------------------------------------------
# SDK 가용성 확인
# ---------------------------------------------------------------------------
def sdk_available() -> bool:
    """`claude-agent-sdk` 를 import 할 수 있는지 확인한다.

    /health 엔드포인트에서 환경 점검용으로 사용한다.
    """
    try:
        import claude_agent_sdk  # noqa: F401

        return True
    except Exception as exc:  # pragma: no cover - 환경 의존적
        logger.debug("claude-agent-sdk import 실패: %s", exc)
        return False


# ---------------------------------------------------------------------------
# 메시지 변환 헬퍼
# ---------------------------------------------------------------------------
def _flatten_content(content: object) -> str:
    """메시지 content(문자열 또는 멀티모달 파트 배열)에서 텍스트를 추출한다."""
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for part in content:
            if isinstance(part, dict):
                # OpenAI 멀티모달 형식: {"type": "text", "text": "..."}
                if part.get("type") == "text" and isinstance(part.get("text"), str):
                    parts.append(part["text"])
            elif isinstance(part, str):
                parts.append(part)
        return "\n".join(parts)
    return str(content)


def build_prompt_and_system(
    messages: list[ChatMessage],
) -> tuple[str, Optional[str]]:
    """OpenAI 메시지 배열을 (prompt, system_prompt) 로 변환한다.

    - system 역할 메시지는 모두 모아 system_prompt 로 사용한다.
    - 나머지 대화(user/assistant)는 트랜스크립트 형태로 직렬화하여 하나의
      prompt 문자열로 만든다. 단일 user 메시지뿐이면 그 내용만 그대로 쓴다.
    """
    system_parts: list[str] = []
    convo: list[ChatMessage] = []

    for msg in messages:
        text = _flatten_content(msg.content)
        if msg.role == "system":
            if text:
                system_parts.append(text)
        else:
            convo.append(msg)

    system_prompt = "\n\n".join(system_parts) if system_parts else None

    # 단일 사용자 메시지 → 그대로 프롬프트로 사용(가장 흔한 경우)
    if len(convo) == 1 and convo[0].role == "user":
        return _flatten_content(convo[0].content), system_prompt

    # 다중 턴 → 읽기 쉬운 트랜스크립트로 직렬화
    lines: list[str] = []
    role_label = {
        "user": "User",
        "assistant": "Assistant",
        "tool": "Tool",
        "function": "Function",
    }
    for msg in convo:
        label = role_label.get(msg.role, msg.role.capitalize())
        lines.append(f"{label}: {_flatten_content(msg.content)}")
    # 마지막으로 어시스턴트 응답을 유도
    lines.append("Assistant:")
    return "\n".join(lines), system_prompt


def _build_options(model: str, system_prompt: Optional[str]):
    """`ClaudeAgentOptions` 를 구성한다.

    - 도구를 비활성화하여 순수 텍스트 completion 처럼 동작시킨다.
    - 단일 턴(max_turns=1)으로 제한한다.

    참고: temperature/top_p 등 일부 OpenAI 파라미터는 CLI/SDK 경로에서
    직접 노출되지 않아 무시될 수 있다(README 에 명시).
    """
    from claude_agent_sdk import ClaudeAgentOptions

    kwargs: dict = {
        "model": model,
        "allowed_tools": [],  # 도구 비활성화 → 단순 응답 생성
        "max_turns": 1,
    }
    if system_prompt:
        kwargs["system_prompt"] = system_prompt
    try:
        return ClaudeAgentOptions(**kwargs)
    except TypeError:
        # SDK 버전에 따라 지원 필드가 다를 수 있으므로 최소 구성으로 재시도
        minimal = {"model": model}
        if system_prompt:
            minimal["system_prompt"] = system_prompt
        return ClaudeAgentOptions(**minimal)


def _extract_text_blocks(message: object) -> list[str]:
    """AssistantMessage 에서 텍스트 블록들을 추출한다(버전 방어적)."""
    texts: list[str] = []
    content = getattr(message, "content", None)
    if content is None:
        return texts
    for block in content:
        text = getattr(block, "text", None)
        if isinstance(text, str):
            texts.append(text)
    return texts


def _extract_usage(message: object) -> tuple[int, int]:
    """ResultMessage 에서 (input_tokens, output_tokens) 를 추출한다."""
    usage = getattr(message, "usage", None)
    if isinstance(usage, dict):
        return int(usage.get("input_tokens", 0)), int(usage.get("output_tokens", 0))
    return 0, 0


# ---------------------------------------------------------------------------
# 공개 API — 비스트리밍
# ---------------------------------------------------------------------------
async def create_completion(
    messages: list[ChatMessage],
    model: str,
    temperature: Optional[float] = None,
    max_tokens: Optional[int] = None,
) -> ClaudeResult:
    """단일 응답을 생성한다(비스트리밍).

    Claude 스트림을 끝까지 소비하여 전체 텍스트와 사용량을 집계해 반환한다.
    """
    from claude_agent_sdk import query

    resolved = resolve_model(model)
    prompt, system_prompt = build_prompt_and_system(messages)
    options = _build_options(resolved, system_prompt)

    result = ClaudeResult(model=model)
    collected: list[str] = []

    logger.info("Claude 호출(비스트리밍) model=%s", resolved)
    async for message in query(prompt=prompt, options=options):
        cls_name = type(message).__name__
        if cls_name == "AssistantMessage":
            collected.extend(_extract_text_blocks(message))
        elif cls_name == "ResultMessage":
            in_tok, out_tok = _extract_usage(message)
            result.input_tokens = in_tok
            result.output_tokens = out_tok
            # ResultMessage.result 에 최종 텍스트가 담기는 경우 우선 사용
            final = getattr(message, "result", None)
            if isinstance(final, str) and final:
                collected = [final]

    result.text = "".join(collected)
    result.finish_reason = "stop"
    logger.info(
        "Claude 응답 완료 out_tokens=%s len=%s",
        result.output_tokens,
        len(result.text),
    )
    return result


# ---------------------------------------------------------------------------
# 공개 API — 스트리밍
# ---------------------------------------------------------------------------
async def stream_completion(
    messages: list[ChatMessage],
    model: str,
    temperature: Optional[float] = None,
    max_tokens: Optional[int] = None,
) -> AsyncGenerator[str, None]:
    """텍스트 델타를 순차적으로 yield 한다(스트리밍).

    호출측(라우터)이 이 델타를 OpenAI SSE 청크로 변환한다.
    """
    from claude_agent_sdk import query

    resolved = resolve_model(model)
    prompt, system_prompt = build_prompt_and_system(messages)
    options = _build_options(resolved, system_prompt)

    logger.info("Claude 호출(스트리밍) model=%s", resolved)
    async for message in query(prompt=prompt, options=options):
        if type(message).__name__ == "AssistantMessage":
            for text in _extract_text_blocks(message):
                if text:
                    yield text
