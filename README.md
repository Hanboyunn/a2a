# 🧠 A2A (Agent-to-Agent) 통신 시스템

Agent 간 직접 통신을 지원하는 분산 시스템입니다. 각 agent는 FastAPI 서버로 동작하며, 서로 직접 메시지를 주고받을 수 있습니다. 모든 통신은 중앙 모니터링 시스템을 통해 감시됩니다.

## 주요 기능

- ✅ **직접 A2A 통신**: Agent들이 orchestrator 없이도 직접 통신 가능
- ✅ **실시간 모니터링**: 모든 agent 통신을 실시간으로 감시
- ✅ **Trust 기반 보안**: 각 agent의 신뢰도 점수 관리
- ✅ **서명 검증**: 모든 메시지에 암호화 서명 적용
- ✅ **Replay 공격 방지**: 중복 메시지 감지 및 차단

## 구조

- **agents/** : 모든 Agent (user, tool, admin, orchestrator 등)
  - 각 agent는 FastAPI 서버로 동작
  - `/a2a/invoke` 엔드포인트를 통해 메시지 수신
  - `BaseAgentServer` 클래스를 상속하여 구현
- **common/** : crypto 서명/검증 모듈
- **monitor/** : 중앙 감시자 (trust / replay / revoked 관리)
  - 실시간 모니터링 대시보드 제공
  - 모든 agent 통신 로깅 및 분석
- **tools/** : RSA keygen 및 그래프 도구

## Agent 포트 구성

- **Monitor**: `http://127.0.0.1:8100`
- **Orchestrator**: `http://127.0.0.1:8000`
- **User Agent**: `http://127.0.0.1:8001`
- **Tool Agent**: `http://127.0.0.1:8002`
- **Admin Agent**: `http://127.0.0.1:8003`

---

## 📖 사용 가이드

**상세한 사용 방법은 [USAGE.md](USAGE.md)를 참고하세요.**

**시스템 아키텍처 및 작동 방식은 [ARCHITECTURE.md](ARCHITECTURE.md)를 참고하세요.**

---

## 빠른 시작

### 1️⃣ 키 생성 및 리소스 초기화
```bash
# 키 생성
python tools/keygen.py

# 리소스 초기화 (샘플 리소스 생성)
python tools/init_resources.py
```

### 2️⃣ 모든 Agent 실행

**Windows:**
```bash
run_all_agents.bat
```

**Linux/Mac:**
```bash
python run_all_agents.py
```

또는 각 agent를 개별적으로 실행:
```bash
# 터미널 1: Monitor
python -m monitor.monitor

# 터미널 2: Orchestrator
python -m agents.orchestrator

# 터미널 3: Tool Agent
python -m agents.tool_agent

# 터미널 4: User Agent
python -m agents.user_agent

# 터미널 5: Admin Agent
python -m agents.admin_agent
```

### 3️⃣ 모니터링 대시보드 확인

브라우저에서 다음 URL을 열어 실시간 모니터링 대시보드를 확인하세요:

```
http://127.0.0.1:8100/dashboard
```

대시보드에서 다음을 확인할 수 있습니다:
- 등록된 agent 목록 및 상태
- 각 agent의 Trust Score
- 최근 통신 이벤트
- 보안 알림

---

## API 엔드포인트

### Monitor API
- `GET /dashboard` - 실시간 모니터링 대시보드 (HTML)
- `GET /api/events?limit=50` - 최근 이벤트 조회 (JSON)
- `GET /api/trust` - Trust Score 조회 (JSON)
- `GET /api/stats` - 통계 정보 조회 (JSON)
- `POST /ingest` - 이벤트 수집 (내부용)

### Agent API (각 agent 공통)
- `POST /a2a/invoke` - A2A 메시지 수신
- `GET /status` - Agent 상태 조회
- `GET /registry` - Agent 레지스트리 조회

---

## Agent 간 통신 예제

### Python에서 다른 agent에게 메시지 보내기

```python
from agents.base_agent import BaseAgentServer

# Agent 서버 생성
agent = BaseAgentServer(
    agent_id="my-agent",
    port=9000,
    action_handlers={}
)

# 다른 agent에게 메시지 전송
response = agent.send_to_agent(
    recipient_id="agent-tool-01",
    action="read_resource",
    params={"resource": "doc-123"}
)

print(response.status_code)
print(response.json())
```

### 직접 HTTP 요청으로 메시지 보내기

```python
import requests
from agents.base_agent import build_message, send_and_log


msg = build_message(
    sender_id="my-agent",
    recipient_id="agent-tool-01",
    recipient_ep="http://127.0.0.1:8002/a2a/invoke",
    action="read_resource",
    params={"resource": "doc-123"}
)

response = send_and_log(msg)
print(response.json())
```

---

## 모니터링 및 감시

모든 agent 통신은 자동으로 monitor로 전송되어 다음을 추적합니다:

1. **Trust Score**: 각 agent의 신뢰도 점수 (0.0 ~ 1.0)
   - 유효한 서명: +0.05
   - Replay 공격 감지: -0.15
   - Revoked agent: 0.0

2. **Replay 공격 감지**: 동일한 nonce나 message_id를 가진 메시지 감지

3. **위험 행동 모니터링**: 
   - High-risk actions: `delete_resource`, `modify_config` (Trust >= 0.8 필요)
   - Low-risk actions: `get_status`, `ping` (Trust >= 0.3 필요)

4. **실시간 알림**: 위험 행동이나 보안 이벤트 발생 시 알림 생성

---

## 개발자 가이드

### 새로운 Agent 추가하기

1. `agents/` 디렉토리에 새 파일 생성
2. `BaseAgentServer`를 상속하여 agent 구현:

```python
from agents.base_agent import BaseAgentServer

AGENT_ID = "agent-new-01"
PORT = 8004

async def handle_my_action(params: dict, full_msg: dict):
    """Custom action handler"""
    return {"status": "ok", "result": "done"}

def main():
    action_handlers = {
        "my_action": handle_my_action,
    }
    
    agent = BaseAgentServer(
        agent_id=AGENT_ID,
        port=PORT,
        action_handlers=action_handlers
    )
    
    agent.run()

if __name__ == "__main__":
    main()
```

3. `agents/base_agent.py`의 `AGENT_REGISTRY`에 새 agent 추가

---

## 문제 해결

### Agent가 서로 통신하지 않는 경우
- 모든 agent가 실행되었는지 확인
- Monitor가 먼저 시작되었는지 확인
- 포트가 충돌하지 않는지 확인

### Trust Score가 업데이트되지 않는 경우
- Monitor가 정상 실행 중인지 확인
- 메시지에 유효한 서명이 포함되어 있는지 확인
- `monitor/data.jsonl` 파일을 확인하여 로그 수집 여부 확인

---

## 라이선스

MIT License
