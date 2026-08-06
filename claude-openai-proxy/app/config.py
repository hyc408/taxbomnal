"""애플리케이션 설정 로딩 모듈.

`.env` 파일에서 서버 구동에 필요한 설정을 읽어들인다.
Anthropic API Key 는 저장하지 않는다 — 인증은 전적으로 Claude Code CLI 의
OAuth 로그인(`claude login`)을 재사용한다.
"""

from __future__ import annotations

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """환경 변수 기반 설정.

    `.env` 파일 또는 프로세스 환경 변수에서 값을 읽는다.
    """

    # --- 서버 바인딩 ---------------------------------------------------------
    host: str = Field(default="0.0.0.0", description="바인딩 호스트")
    port: int = Field(default=8000, description="바인딩 포트")
    log_level: str = Field(default="INFO", description="로그 레벨")

    # --- 프록시 자체 접근 토큰 (선택) ----------------------------------------
    # Anthropic API Key 가 아니라, 이 프록시에 접근하기 위한 자체 토큰이다.
    # 비어 있으면 인증 없이 누구나 호출할 수 있다(내부 신뢰 네트워크 전용).
    # 값이 설정되면 요청 헤더 `Authorization: Bearer <token>` 을 요구한다.
    proxy_api_key: str = Field(
        default="",
        description="프록시 접근 토큰(선택). 비우면 인증 비활성화.",
    )

    # --- Claude 관련 ---------------------------------------------------------
    # 요청 응답 대기 최대 시간(초). 0 이하이면 무제한.
    request_timeout: float = Field(
        default=300.0, description="단일 요청 처리 타임아웃(초)"
    )

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    """설정 싱글턴을 반환한다(캐시)."""
    return Settings()
