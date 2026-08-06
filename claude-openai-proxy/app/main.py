"""FastAPI 애플리케이션 진입점.

로깅을 설정하고 라우터를 등록한다. `python -m app.main` 또는
`uvicorn app.main:app` 으로 실행할 수 있다.
"""

from __future__ import annotations

import logging

from fastapi import FastAPI

from .config import get_settings
from .routes import router


def _configure_logging(level: str) -> None:
    """루트 로거를 UTF-8 콘솔 출력으로 설정한다."""
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
    )


def create_app() -> FastAPI:
    """FastAPI 앱 팩토리."""
    settings = get_settings()
    _configure_logging(settings.log_level)

    app = FastAPI(
        title="claude-openai-proxy",
        version="0.1.0",
        description=(
            "OpenAI-compatible API server backed by Claude Code SDK (OAuth). "
            "Anthropic API Key 를 사용하지 않고 Claude Pro/Max OAuth 로그인을 재사용한다."
        ),
    )
    app.include_router(router)

    logger = logging.getLogger("claude_proxy")
    logger.info(
        "claude-openai-proxy 시작 준비 완료 (host=%s port=%s auth=%s)",
        settings.host,
        settings.port,
        "on" if settings.proxy_api_key else "off",
    )
    return app


app = create_app()


def main() -> None:
    """개발용 실행 헬퍼."""
    import uvicorn

    settings = get_settings()
    uvicorn.run(
        "app.main:app",
        host=settings.host,
        port=settings.port,
        log_level=settings.log_level.lower(),
    )


if __name__ == "__main__":
    main()
