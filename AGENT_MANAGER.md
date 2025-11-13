# Agent Management Server

Agent Management Server는 모든 agent를 중앙에서 관리하는 서버입니다.

## 주요 기능

### 1. Agent 등록 및 관리
- 동적 agent 등록/해제
- Agent 상태 추적 (active/inactive)
- Agent 메타데이터 관리

### 2. 데이터베이스 (SQLite)
- **agents**: Agent 정보 저장
- **agent_messages**: Agent 간 메시지 로그
- **agent_health**: Health check 기록
- **system_config**: 시스템 설정

### 3. Health Check
- 주기적으로 agent 상태 확인 (30초마다)
- Heartbeat 기반 생존 확인
- 응답하지 않는 agent 자동 비활성화

### 4. Service Discovery
- `/registry` 엔드포인트로 활성 agent 목록 제공
- 기존 시스템과 호환

## API 엔드포인트

### Agent 관리
- `POST /register` - Agent 등록
- `POST /unregister/{agent_id}` - Agent 해제
- `POST /heartbeat/{agent_id}` - Heartbeat 업데이트
- `GET /agents` - 모든 agent 목록
- `GET /agents/{agent_id}` - 특정 agent 정보
- `GET /agents/{agent_id}/health` - Agent health check 기록

### Registry
- `GET /registry` - Agent registry (기존 시스템 호환)

### 설정 관리
- `GET /config/{config_key}` - 설정 조회
- `POST /config/{config_key}` - 설정 업데이트

### 통계
- `GET /stats` - 시스템 통계

## 사용 방법

### 1. 서버 실행
```bash
python -m agent_manager.manager
```

또는 `run_all_agents.py`를 실행하면 자동으로 시작됩니다.

### 2. Agent 자동 등록
각 agent가 시작되면 자동으로 Agent Manager에 등록됩니다.

### 3. API 문서
FastAPI 자동 문서: http://127.0.0.1:8200/docs

## 데이터베이스

SQLite 데이터베이스는 `agent_manager/agents.db`에 저장됩니다.

### 스키마

**agents**
- agent_id (PRIMARY KEY)
- endpoint
- status (active/inactive)
- agent_type
- capabilities (JSON)
- registered_at
- last_heartbeat
- metadata (JSON)

**agent_messages**
- id (AUTOINCREMENT)
- sender_id
- recipient_id
- action
- message_id (UNIQUE)
- timestamp
- status
- trust_score

**agent_health**
- id (AUTOINCREMENT)
- agent_id
- check_time
- status (healthy/unhealthy)
- response_time_ms
- error_message

**system_config**
- config_key (PRIMARY KEY)
- config_value
- updated_at
- updated_by

## 통합

기존 시스템과의 통합:
- `BaseAgentServer`가 시작 시 자동 등록
- `/status` 엔드포인트 호출 시 heartbeat 업데이트
- Monitor와 독립적으로 동작

