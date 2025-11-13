# 📖 A2A 시스템 사용 가이드

## 🚀 빠른 시작 (3단계)

### 1단계: 키 생성 (최초 1회만)

먼저 암호화 키를 생성해야 합니다:

```bash
python tools/keygen.py
```

이 명령어는 다음 파일들을 생성합니다:
- `tools/private.pem` - 개인키 (서명용)
- `tools/public.pem` - 공개키 (검증용)

### 2단계: 모든 Agent 실행

**방법 1: 통합 스크립트 사용 (권장)**

Windows:
```bash
run_all_agents.bat
```

Linux/Mac:
```bash
python run_all_agents.py
```

이 스크립트는 다음 순서로 모든 agent를 자동으로 실행합니다:
1. Monitor (포트 8100)
2. Orchestrator (포트 8000)
3. Tool Agent (포트 8002)
4. User Agent (포트 8001)
5. Admin Agent (포트 8003)

**방법 2: 개별 실행 (디버깅용)**

각 agent를 별도 터미널에서 실행하려면:

**터미널 1 - Monitor:**
```bash
python -m monitor.monitor
```
출력 예시:
```
INFO:     Started server process
INFO:     Waiting for application startup.
INFO:     Application startup complete.
INFO:     Uvicorn running on http://127.0.0.1:8100
```

**터미널 2 - Orchestrator:**
```bash
python -m agents.orchestrator
```

**터미널 3 - Tool Agent:**
```bash
python -m agents.tool_agent
```

**터미널 4 - User Agent:**
```bash
python -m agents.user_agent
```

**터미널 5 - Admin Agent:**
```bash
python -m agents.admin_agent
```

### 3단계: 모니터링 대시보드 확인

브라우저에서 다음 URL을 엽니다:

```
http://127.0.0.1:8100/dashboard
```

대시보드가 3초마다 자동으로 새로고침되며 다음 정보를 표시합니다:
- ✅ 등록된 agent 수
- ✅ 각 agent의 Trust Score
- ✅ 최근 통신 이벤트
- ✅ 보안 알림

---

## 📊 모니터링 대시보드 사용법

### 대시보드 화면 구성

1. **상단 통계 박스**
   - Registered Agents: 현재 등록된 agent 수
   - Recent Events: 최근 이벤트 수
   - Revoked Agents: 차단된 agent 수

2. **Agent Trust Scores 테이블**
   - Agent ID: agent 식별자
   - Trust Score: 신뢰도 점수 (0.0 ~ 1.0)
     - 🔴 낮음 (< 0.5): 빨간색
     - 🟡 중간 (0.5 ~ 0.8): 노란색
     - 🟢 높음 (> 0.8): 초록색
   - Status: ACTIVE 또는 REVOKED

3. **Recent Events 섹션**
   - 최근 20개 이벤트 표시
   - 🚨 ALERT: 보안 알림 (빨간색 테두리)
   - 📨 EVENT: 일반 통신 이벤트 (파란색 테두리)

### API를 통한 모니터링

**최근 이벤트 조회:**
```bash
curl http://127.0.0.1:8100/api/events?limit=10
```

**Trust Score 조회:**
```bash
curl http://127.0.0.1:8100/api/trust
```

**통계 정보 조회:**
```bash
curl http://127.0.0.1:8100/api/stats
```

---

## 🔍 Agent 동작 확인

### 각 Agent의 상태 확인

각 agent는 `/status` 엔드포인트를 제공합니다:

```bash
# Orchestrator 상태
curl http://127.0.0.1:8000/status

# User Agent 상태
curl http://127.0.0.1:8001/status

# Tool Agent 상태
curl http://127.0.0.1:8002/status

# Admin Agent 상태
curl http://127.0.0.1:8003/status
```

응답 예시:
```json
{
  "agent_id": "agent-user-01",
  "status": "running",
  "endpoint": "http://127.0.0.1:8001/a2a/invoke",
  "registered_actions": ["read_resource", "get_status", "ping"]
}
```

### Agent 레지스트리 확인

모든 등록된 agent 목록 확인:

```bash
curl http://127.0.0.1:8001/registry
```

---

## 🧪 테스트 시나리오

### 시나리오 1: User Agent가 Tool Agent에게 요청 보내기

User Agent는 자동으로 주기적으로(5초마다) 다른 agent들에게 task를 보냅니다.

대시보드에서 다음을 확인할 수 있습니다:
- User Agent → Tool Agent 통신 이벤트
- Trust Score 변화
- Action 타입 (read_resource, get_status, ping 등)

### 시나리오 2: Admin Agent의 High-Risk Action

Admin Agent는 10초마다 Tool Agent에게 `delete_resource` 요청을 보냅니다.

대시보드에서 확인:
- 🚨 High-risk action 알림
- Trust Score 요구사항 (0.8 이상 필요)
- Action 실행 여부

### 시나리오 3: 직접 메시지 전송 테스트

Python 스크립트로 직접 메시지를 보낼 수 있습니다:

```python
import requests
from agents.base_agent import build_message, send_and_log

# User Agent에서 Tool Agent로 메시지 전송
msg = build_message(
    sender_id="agent-user-01",
    recipient_id="agent-tool-01",
    recipient_ep="http://127.0.0.1:8002/a2a/invoke",
    action="read_resource",
    params={"resource": "test-doc-123"}
)

response = send_and_log(msg)
print(f"Status: {response.status_code}")
print(f"Response: {response.json()}")
```

---

## 🐛 문제 해결

### 문제 1: Agent가 시작되지 않음

**증상:** `ModuleNotFoundError` 또는 포트 충돌

**해결:**
1. 필요한 패키지 설치 확인:
   ```bash
   pip install fastapi uvicorn requests pycryptodome
   ```

2. 포트가 이미 사용 중인지 확인:
   ```bash
   # Windows
   netstat -ano | findstr :8000
   
   # Linux/Mac
   lsof -i :8000
   ```

3. 다른 프로세스가 포트를 사용 중이면 종료하거나 다른 포트 사용

### 문제 2: Agent들이 서로 통신하지 않음

**증상:** 대시보드에 이벤트가 나타나지 않음

**해결:**
1. 모든 agent가 실행되었는지 확인
2. Monitor가 먼저 시작되었는지 확인 (Monitor는 가장 먼저 시작되어야 함)
3. Agent 레지스트리 확인:
   ```bash
   curl http://127.0.0.1:8001/registry
   ```

### 문제 3: Trust Score가 업데이트되지 않음

**증상:** 대시보드에서 Trust Score가 변하지 않음

**해결:**
1. Monitor가 정상 실행 중인지 확인
2. `monitor/data.jsonl` 파일 확인:
   ```bash
   # Windows
   type monitor\data.jsonl
   
   # Linux/Mac
   tail -f monitor/data.jsonl
   ```
3. 메시지에 유효한 서명이 포함되어 있는지 확인

### 문제 4: 키 파일이 없음

**증상:** `FileNotFoundError: tools/private.pem`

**해결:**
```bash
python tools/keygen.py
```

---

## 📝 로그 파일 확인

시스템은 다음 로그 파일을 생성합니다:

- `monitor/data.jsonl` - 모든 통신 이벤트 로그
- `monitor/alerts.jsonl` - 보안 알림 로그

로그 확인 방법:

```bash
# Windows PowerShell
Get-Content monitor\data.jsonl -Tail 20

# Linux/Mac
tail -f monitor/data.jsonl
```

---

## 🎯 다음 단계

1. **대시보드 관찰**: Agent들이 통신하는 것을 실시간으로 관찰
2. **Trust Score 변화 확인**: 시간에 따른 Trust Score 변화 관찰
3. **새로운 Agent 추가**: README의 "개발자 가이드" 섹션 참고
4. **커스텀 Action 추가**: 각 agent에 새로운 action handler 추가

---

## 💡 팁

- **대시보드 자동 새로고침**: 대시보드는 3초마다 자동으로 새로고침됩니다
- **로그 실시간 확인**: `tail -f monitor/data.jsonl`로 실시간 로그 확인
- **Agent 상태 확인**: 각 agent의 `/status` 엔드포인트로 상태 확인
- **종료 방법**: 
  - 통합 스크립트 사용 시: `Ctrl+C`
  - 개별 실행 시: 각 터미널에서 `Ctrl+C`

---

## 📞 추가 도움말

더 자세한 정보는 `README.md`를 참고하세요.

