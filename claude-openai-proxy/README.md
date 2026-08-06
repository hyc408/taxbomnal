# claude-openai-proxy

Claude Pro/Max **OAuth 로그인**을 재사용하여 동작하는 **OpenAI 호환 API 서버**입니다.
Anthropic API Key 없이, Claude Code CLI 의 로그인 세션을 그대로 이용해
OpenAI 형식(`/v1/chat/completions`)으로 요청을 처리합니다.

```
OpenAI Client (Continue, Cline, Roo Code, LangChain 등)
        │
        ▼
OpenAI Compatible FastAPI Server  ← 이 프로젝트
        │
        ▼
Claude Code SDK (claude-agent-sdk)
        │
        ▼
claude CLI (OAuth)  →  Claude Pro/Max Account
```

> ⚠️ **주의 (반드시 읽어주세요)**
> 이 프로젝트는 **개인 연구·개발 목적**으로, 사용자의 Claude Pro/Max 계정
> OAuth 인증을 재사용합니다. 구독 인증을 OpenAI 호환 API 로 재포장하여
> 다수/제3자에게 제공하는 사용 방식은 Anthropic 이용약관에 저촉될 소지가
> 있으며, 이에 따른 계정 관련 책임은 사용자에게 있습니다. 신뢰할 수 있는
> 내부 네트워크에서만 사용하세요.

---

## 목차

- [특징](#특징)
- [요구 사항](#요구-사항)
- [설치 방법](#설치-방법)
- [Claude OAuth 로그인](#claude-oauth-로그인)
- [서버 실행](#서버-실행)
- [엔드포인트](#엔드포인트)
- [curl 테스트](#curl-테스트)
- [Streaming 테스트](#streaming-테스트)
- [클라이언트 설정](#클라이언트-설정)
  - [VSCode Continue](#vscode-continue)
  - [Cline](#cline)
  - [Roo Code](#roo-code)
  - [LangChain 예제](#langchain-예제)
- [Docker](#docker)
- [테스트](#테스트)
- [제약 사항 / 주의](#제약-사항--주의)
- [프로젝트 구조](#프로젝트-구조)

---

## 특징

- **API Key 불필요** — Claude Code CLI 의 OAuth 로그인(`claude login`)을 재사용
- OpenAI 호환 엔드포인트: `/v1/chat/completions`, `/v1/models`
- **스트리밍(SSE)** 지원 (`stream=true`)
- 모델 별칭: `claude-opus`, `claude-sonnet`, `claude-haiku`
- 비동기(async) FastAPI, Pydantic 스키마, 타입 힌트, 상세 로그, UTF-8
- 선택적 프록시 접근 토큰(`PROXY_API_KEY`)으로 접근 제한
- Docker / docker-compose 지원 (OAuth 인증 마운트)

---

## 요구 사항

- **Python 3.12+** (개발/CI 환경에서는 3.11 에서도 동작)
- **Node.js 18+** — `claude-agent-sdk` 가 `claude` CLI 를 호출하기 때문
- **Claude Code CLI** (`@anthropic-ai/claude-code`)
- **Claude Pro / Max 계정**

---

## 설치 방법

```bash
# 1) 저장소로 이동
cd claude-openai-proxy

# 2) (권장) 가상환경
python3 -m venv .venv
source .venv/bin/activate

# 3) Python 의존성 설치
pip install -r requirements.txt

# 4) Claude Code CLI 설치 (Node 필요)
npm install -g @anthropic-ai/claude-code

# 5) 환경설정 파일 준비
cp .env.example .env
```

---

## Claude OAuth 로그인

이 프록시는 **API Key 를 사용하지 않습니다.** 대신 CLI 로그인 세션을 씁니다.

```bash
# Claude Pro/Max 계정으로 OAuth 로그인 (브라우저가 열립니다)
claude login
```

- 이미 로그인되어 있으면 **기존 OAuth 토큰을 그대로 재사용**합니다(재로그인 불필요).
- 로그인 상태 확인은 다음으로 간단히 점검할 수 있습니다.

```bash
# 아무 프롬프트나 던져 응답이 오면 OAuth 정상
claude -p "hello"
```

---

## 서버 실행

```bash
# 방법 A) 모듈 실행 (.env 의 HOST/PORT 사용)
python -m app.main

# 방법 B) uvicorn 직접 실행
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

기동 후 확인:

```bash
curl http://localhost:8000/health
# {"status":"ok","sdk_available":true}
```

> `sdk_available` 이 `false` 이면 `claude-agent-sdk` 또는 `claude` CLI 가 설치/로그인되지 않은 상태입니다.

---

## 엔드포인트

| Method | Path                    | 설명                          |
|--------|-------------------------|-------------------------------|
| GET    | `/`                     | 서비스 정보                   |
| GET    | `/health`               | 상태 확인 (+SDK 가용 여부)    |
| GET    | `/v1/models`            | 모델 목록                     |
| POST   | `/v1/chat/completions`  | Chat Completion (스트리밍 지원) |

`PROXY_API_KEY` 를 설정한 경우, `/v1/chat/completions` 호출 시
`Authorization: Bearer <PROXY_API_KEY>` 헤더가 필요합니다.

---

## curl 테스트

```bash
curl http://localhost:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "claude-sonnet",
    "messages": [{"role": "user", "content": "Hello"}],
    "temperature": 0.2,
    "stream": false
  }'
```

응답(예):

```json
{
  "id": "chatcmpl-...",
  "object": "chat.completion",
  "created": 1785990000,
  "model": "claude-sonnet",
  "choices": [
    {
      "index": 0,
      "message": {"role": "assistant", "content": "Hello! ..."},
      "finish_reason": "stop"
    }
  ],
  "usage": {"prompt_tokens": 5, "completion_tokens": 12, "total_tokens": 17}
}
```

`PROXY_API_KEY` 를 설정한 경우:

```bash
curl http://localhost:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $PROXY_API_KEY" \
  -d '{"model":"claude-sonnet","messages":[{"role":"user","content":"Hello"}]}'
```

---

## Streaming 테스트

```bash
curl -N http://localhost:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "claude-sonnet",
    "messages": [{"role": "user", "content": "Count to five"}],
    "stream": true
  }'
```

`-N` 옵션으로 버퍼링을 끄면 SSE 청크가 순차적으로 출력됩니다.

```
data: {"id":"chatcmpl-...","object":"chat.completion.chunk", ... "delta":{"role":"assistant"}}
data: {"id":"chatcmpl-...", ... "delta":{"content":"One"}}
data: {"id":"chatcmpl-...", ... "delta":{"content":" two"}}
...
data: {"id":"chatcmpl-...", ... "delta":{}, "finish_reason":"stop"}
data: [DONE]
```

---

## 클라이언트 설정

모든 클라이언트에서 **Base URL** 은 `http://localhost:8000/v1` 이며,
API Key 필드에는 임의 값(또는 `PROXY_API_KEY`)을 넣으면 됩니다.

### VSCode Continue

`~/.continue/config.json` (또는 Continue 설정 UI):

```json
{
  "models": [
    {
      "title": "Claude (proxy)",
      "provider": "openai",
      "model": "claude-sonnet",
      "apiBase": "http://localhost:8000/v1",
      "apiKey": "not-needed"
    }
  ]
}
```

> `PROXY_API_KEY` 를 설정했다면 `"apiKey"` 에 그 값을 넣으세요.

### Cline

Cline 설정에서 **API Provider** 를 `OpenAI Compatible` 로 선택 후:

- **Base URL**: `http://localhost:8000/v1`
- **API Key**: `not-needed` (또는 `PROXY_API_KEY`)
- **Model ID**: `claude-sonnet`

### Roo Code

Roo Code 설정에서 **API Provider** 를 `OpenAI Compatible` 로 선택 후:

- **Base URL**: `http://localhost:8000/v1`
- **API Key**: `not-needed` (또는 `PROXY_API_KEY`)
- **Model**: `claude-opus` / `claude-sonnet` / `claude-haiku`

### LangChain 예제

```python
from langchain_openai import ChatOpenAI

llm = ChatOpenAI(
    base_url="http://localhost:8000/v1",
    api_key="not-needed",          # PROXY_API_KEY 설정 시 그 값
    model="claude-sonnet",
    temperature=0.2,
)

print(llm.invoke("한 문장으로 자기소개 해줘").content)

# 스트리밍
for chunk in llm.stream("1부터 5까지 세어줘"):
    print(chunk.content, end="", flush=True)
```

---

## Docker

Docker 로 실행할 때도 **OAuth 로그인은 호스트에서 먼저** 수행하고,
그 인증 디렉터리(`~/.claude`)를 컨테이너에 마운트하여 재사용합니다.

```bash
# 1) 호스트에서 CLI 설치 및 로그인 (최초 1회)
npm install -g @anthropic-ai/claude-code
claude login

# 2) .env 준비
cp .env.example .env

# 3) 빌드 & 실행
docker compose up --build
```

`docker-compose.yml` 이 `${HOME}/.claude` 를 컨테이너의 `/root/.claude` 로
읽기 전용 마운트하므로, 컨테이너 안에서 재로그인할 필요가 없습니다.

---

## 테스트

테스트는 실제 Claude 호출 없이 **SDK 를 mock** 하여 동작하므로,
로그인/네트워크 없이도 통과합니다.

```bash
pip install -r requirements.txt
pytest
```

- `test_health.py` — `/`, `/health`, `/v1/models`
- `test_chat.py` — Chat Completion(비스트리밍), 인증 동작
- `test_streaming.py` — SSE 스트리밍 형식

실제 OAuth 로 동작을 확인하려면 서버를 띄운 뒤 위 [curl 테스트](#curl-테스트)를 사용하세요.

---

## 제약 사항 / 주의

- **Anthropic Console API Key 를 사용하지 않습니다.** 인증은 전적으로
  `claude login` OAuth 세션에 의존합니다.
- `temperature`, `top_p`, `frequency_penalty` 등 일부 OpenAI 파라미터는
  CLI/SDK 경로에서 직접 노출되지 않아 **무시될 수 있습니다**. 요청은 수용하되
  최종 동작에 반영되지 않을 수 있습니다.
- 도구(툴) 사용은 기본적으로 **비활성화**되어 순수 텍스트 응답으로 동작합니다.
- CLI 서브프로세스 기반이므로 동시 요청이 많으면 Claude 구독 **사용량/속도
  제한**의 영향을 받습니다.
- **이용약관 관련 책임은 사용자에게 있습니다.** 개인/내부 개발 환경에서만
  사용하고, 외부에 공개하지 마세요.

---

## 프로젝트 구조

```
claude-openai-proxy/
├── app/
│   ├── main.py           # FastAPI 진입점, 로깅 설정
│   ├── routes.py         # 엔드포인트 (/, /health, /v1/*)
│   ├── claude_client.py  # claude-agent-sdk 래퍼 (OAuth 재사용, 어댑터)
│   ├── models.py         # OpenAI 호환 Pydantic 스키마 + 모델 매핑
│   └── config.py         # .env 설정 로딩
├── tests/                # pytest (SDK Mock)
├── requirements.txt
├── Dockerfile
├── docker-compose.yml
├── .env.example
└── README.md
```
