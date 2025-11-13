# 🤖 Agent 역할 및 행위 분석

## 1. 악성 행위 탐지 방식

현재 시스템은 **서명 검증과 Replay 공격만**으로 탐지하는 것이 아닙니다. 다음과 같은 **다층 보안 검증**을 수행합니다:

### 탐지 메커니즘 (5가지)

1. **서명 검증 (Signature Verification)**
   - 유효한 서명: Trust Score +0.05
   - 무효한 서명: Trust Score 변화 없음

2. **Replay 공격 감지**
   - 동일한 nonce/message_id 재사용 감지
   - High-Risk Action에 대해서만 체크
   - 감지 시: Trust Score -0.15

3. **Trust Score 기반 판단**
   - Low-Risk Action: Trust ≥ 0.3 필요
   - High-Risk Action: Trust ≥ 0.8 필요
   - Trust 부족 시 요청 차단

4. **위반 횟수 누적**
   - 차단된 요청마다 위반 카운트 +1
   - 3회 누적 시 자동 차단

5. **자동 차단 (Revoked)**
   - Trust Score ≤ 0.1 → 자동 차단
   - 위반 횟수 ≥ 3 → 자동 차단

**결론**: 서명 검증과 Replay 공격만이 아니라, **Trust Score + 위반 누적 + 자동 차단**까지 포함한 종합적인 보안 시스템입니다.

---

## 2. 각 Agent의 역할 및 현재 행위

### 2.1 User Agent (`agent-user-01`)

**역할**: 일반 사용자 작업 수행

**주요 기능**:
- `read_resource`: 리소스 읽기
- `get_status`: 상태 확인
- `ping`: 연결 확인

**현재 행위**:
```python
# 5초마다 반복
while True:
    # 랜덤하게 action 선택
    actions = ["read_resource", "get_status", "ping"]
    action = random.choice(actions)
    
    # 랜덤하게 target agent 선택
    target_agents = ["agent-tool-01", "agent-admin-01", "agent-orch-01"]
    target = random.choice(target_agents)
    
    # 요청 전송
    send_to_agent(target, action, params)
    time.sleep(5)
```

**특징**:
- ✅ Low-Risk Action만 수행 (Trust ≥ 0.3 필요)
- ✅ 정상적인 사용자 행동 패턴
- ✅ 다양한 agent와 통신

---

### 2.2 Admin Agent (`agent-admin-01`)

**역할**: 관리자 작업 수행 (High-Risk)

**주요 기능**:
- `delete_resource`: 리소스 삭제 (High-Risk)
- `modify_config`: 설정 수정 (High-Risk)
- `request_task`: 작업 요청

**현재 행위**:
```python
# 10초마다 반복
while True:
    # Tool Agent에게 delete_resource 요청
    send_to_agent(
        recipient_id="agent-tool-01",
        action="delete_resource",
        params={"resource_id": f"critical-db-{timestamp}"}
    )
    time.sleep(10)
```

**특징**:
- ⚠️ High-Risk Action 수행 (Trust ≥ 0.8 필요)
- ⚠️ Trust Score가 낮으면 차단됨
- ⚠️ 현재 Trust Score 0.00이므로 계속 차단됨

**문제점**:
- Trust Score가 0.00인데 High-Risk Action을 계속 시도
- 3회 누적 시 자동 차단됨

---

### 2.3 Tool Agent (`agent-tool-01`)

**역할**: 리소스 처리 담당

**주요 기능**:
- `delete_resource`: 리소스 삭제 실행
- `read_resource`: 리소스 읽기
- `get_status`: 상태 확인
- `ping`: 연결 확인

**현재 행위**:
```python
# 요청을 받으면 처리
@app.post("/a2a/invoke")
async def invoke():
    # 1. 서명 검증
    # 2. Trust Score 확인 (High-Risk Action인 경우)
    # 3. Action 처리
    # 4. 결과 반환
```

**특징**:
- ✅ 요청받은 작업을 처리
- ✅ Trust Score 검증 후 처리
- ✅ High-Risk Action은 Trust Score 확인 필수

**보안 역할**:
- Trust Score가 낮은 agent의 High-Risk 요청을 차단
- 403 Forbidden 반환

---

### 2.4 Orchestrator (`agent-orch-01`)

**역할**: 메시지 라우팅 및 중계

**주요 기능**:
- `request_task`: 작업 요청을 다른 agent로 전달

**현재 행위**:
```python
async def handle_request_task():
    # 요청받은 task를 target agent로 전달
    task = params.get("task")
    recipient_id = full_msg.get("recipient", {}).get("agent_id")
    
    # Target agent로 메시지 전달
    forward_msg = full_msg.copy()
    forward_msg["action"] = task
    requests.post(target_ep, json=forward_msg)
```

**특징**:
- ✅ 메시지 중계 역할
- ✅ Agent 간 직접 통신을 지원
- ✅ 라우팅 실패 시 502 에러 반환

---

### 2.5 Monitor (`monitor`)

**역할**: 중앙 감시 및 보안 정책 적용

**주요 기능**:
- 모든 통신 로깅
- Trust Score 계산 및 관리
- Replay 공격 감지
- 자동 차단 (revoked)
- 실시간 대시보드 제공

**현재 행위**:
```python
@app.post("/ingest")
async def ingest():
    # 메시지 평가
    evaluate_message(payload, log_event=True)

@app.post("/evaluate")
async def evaluate():
    # Trust Score 확인 (상태 변경 없음)
    evaluate_message(payload, log_event=False)
```

**특징**:
- ✅ 모든 agent 통신 감시
- ✅ Trust Score 실시간 계산
- ✅ 자동 차단 결정
- ✅ 알림 생성

---

## 3. Agent 간 통신 패턴

### 정상 통신 패턴

```
User Agent (5초마다)
  ├─→ Tool Agent: read_resource, get_status, ping
  ├─→ Admin Agent: get_status, ping
  └─→ Orchestrator: request_task

Admin Agent (10초마다)
  └─→ Tool Agent: delete_resource (High-Risk)
      ├─ Trust Score 확인
      ├─ Trust ≥ 0.8 → 허용 ✅
      └─ Trust < 0.8 → 차단 ❌ (403)
```

### 현재 문제 상황

```
Admin Agent (Trust: 0.00)
  └─→ Tool Agent: delete_resource
      ├─ Trust Score 확인: 0.00 < 0.8
      ├─ 차단 (403 Forbidden)
      ├─ 위반 카운트 +1
      └─ 3회 누적 시 자동 차단 (revoked)
```

---

## 4. 각 Agent의 보안 관련 행위

### 4.1 정상 Agent (User Agent)
- ✅ Low-Risk Action만 수행
- ✅ 유효한 서명 사용
- ✅ 새로운 nonce/message_id 사용
- ✅ Trust Score 유지/증가

### 4.2 의심스러운 Agent (Admin Agent)
- ⚠️ High-Risk Action 시도
- ⚠️ Trust Score 부족으로 차단
- ⚠️ 위반 누적 중
- ⚠️ 자동 차단 위험

### 4.3 보안 Agent (Tool Agent)
- ✅ Trust Score 검증 수행
- ✅ High-Risk Action 차단
- ✅ 보안 정책 적용

### 4.4 중계 Agent (Orchestrator)
- ✅ 메시지 라우팅
- ✅ 직접적인 보안 검증 없음 (수신 agent가 검증)

---

## 5. 개선 가능한 점

### 5.1 Admin Agent의 Trust Score 문제
**현재**: Trust Score 0.00인데 High-Risk Action 계속 시도
**개선**: 
- Admin Agent도 Low-Risk Action으로 Trust Score를 먼저 쌓아야 함
- 또는 Admin Agent에게 초기 Trust Score를 높게 부여

### 5.2 행위 패턴 기반 탐지 부재
**현재**: Trust Score와 위반 횟수만으로 판단
**개선**:
- 짧은 시간 내 다수의 High-Risk Action 시도 감지
- 비정상적인 통신 패턴 감지
- 특정 agent와의 과도한 통신 감지

### 5.3 역할 기반 접근 제어 (RBAC) 부재
**현재**: Trust Score만으로 판단
**개선**:
- Agent 역할(role) 기반 권한 관리
- Admin Agent는 delete_resource 권한 부여
- User Agent는 read_resource만 가능

---

## 결론

1. **악성 행위 탐지**: 서명 검증 + Replay 공격 + Trust Score + 위반 누적 + 자동 차단 (5가지)

2. **각 Agent 역할**:
   - **User Agent**: 일반 작업 (Low-Risk)
   - **Admin Agent**: 관리 작업 (High-Risk) - 현재 Trust 부족으로 차단됨
   - **Tool Agent**: 리소스 처리 + 보안 검증
   - **Orchestrator**: 메시지 라우팅
   - **Monitor**: 중앙 감시 및 보안 정책 적용

3. **현재 문제**: Admin Agent가 Trust Score 0.00인데 High-Risk Action을 계속 시도하여 자동 차단 위험

