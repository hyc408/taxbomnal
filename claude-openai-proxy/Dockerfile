# ---------------------------------------------------------------------------
# claude-openai-proxy 이미지
#
# Python(FastAPI 서버) + Node.js(@anthropic-ai/claude-code CLI) 를 함께 포함한다.
# claude-agent-sdk 가 내부적으로 `claude` CLI 를 실행하므로 Node/CLI 가 필요하다.
#
# 인증(OAuth)은 이미지에 굽지 않는다. 실행 시 호스트의 Claude 인증 디렉터리
# (~/.claude)를 컨테이너에 마운트하여 `claude login` 결과를 재사용한다.
# docker-compose.yml 참고.
# ---------------------------------------------------------------------------
FROM python:3.12-slim

# Node.js 설치 (Claude Code CLI 실행용)
RUN apt-get update \
    && apt-get install -y --no-install-recommends curl ca-certificates gnupg \
    && curl -fsSL https://deb.nodesource.com/setup_22.x | bash - \
    && apt-get install -y --no-install-recommends nodejs \
    && rm -rf /var/lib/apt/lists/*

# Claude Code CLI 전역 설치
RUN npm install -g @anthropic-ai/claude-code

WORKDIR /app

# 의존성 먼저 설치(레이어 캐시 활용)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 애플리케이션 코드
COPY app ./app

EXPOSE 8000

# HOST/PORT 등은 .env 또는 환경변수로 주입
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
