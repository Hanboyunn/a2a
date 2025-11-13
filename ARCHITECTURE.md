# 🏗️ A2A 시스템 아키텍처

## 전체 시스템 구조

```mermaid
graph TB
    subgraph "Agent Layer"
        UA[User Agent<br/>Port: 8001]
        AA[Admin Agent<br/>Port: 8003]
        TA[Tool Agent<br/>Port: 8002]
        OR[Orchestrator<br/>Port: 8000]
    end
    
    subgraph "Monitor Layer"
        MON[Monitor Server<br/>Port: 8100<br/>Trust Score 관리]
    end
    
    subgraph "Storage"
        LOG[data.jsonl<br/>통신 로그]
        ALT[alerts.jsonl<br/>보안 알림]
    end
    
    UA -->|A2A 통신| TA
    UA -->|A2A 통신| OR
    UA -->|A2A 통신| AA
    AA -->|High-Risk Action| TA
    OR -->|라우팅| TA
    
    UA -.->|모니터링| MON
    AA -.->|모니터링| MON
    TA -.->|모니터링| MON
    OR -.->|모니터링| MON
    
    MON --> LOG
    MON --> ALT
    
    style UA fill:#4ec9b0
    style AA fill:#f48771
    style TA fill:#569cd6
    style OR fill:#dcdcaa
    style MON fill:#9cdcfe
```

## Agent 간 통신 흐름 (일반적인 경우)

```mermaid
sequenceDiagram
    participant SA as Sender Agent<br/>(예: Admin Agent)
    participant MON as Monitor
    participant RA as Receiver Agent<br/>(예: Tool Agent)
    
    Note over SA: 주기적 작업 시작<br/>(10초마다)
    SA->>SA: send_to_agent() 호출
    SA->>SA: build_message()<br/>서명 생성
    SA->>RA: POST /a2a/invoke<br/>(서명된 메시지)
    
    RA->>MON: monitor_log()<br/>수신 이벤트 전송
    RA->>RA: 서명 검증
    alt 서명 유효
        RA->>RA: Action 처리
        RA->>MON: monitor_log()<br/>처리 결과 전송
        RA->>SA: 200 OK + 결과
    else 서명 무효
        RA->>MON: alert: invalid_signature
        RA->>SA: 400 Bad Request
    end
```

## High-Risk Action 처리 흐름 (Trust Score 검증)

```mermaid
sequenceDiagram
    participant AA as Admin Agent<br/>(Trust: 0.00)
    participant TA as Tool Agent
    participant MON as Monitor
    
    Note over AA: delete_resource 요청 생성
    AA->>AA: build_message()<br/>서명 생성
    AA->>TA: POST /a2a/invoke<br/>action: delete_resource
    
    TA->>MON: monitor_log()<br/>수신 이벤트
    TA->>TA: 서명 검증 ✅
    
    Note over TA: High-Risk Action 감지<br/>(delete_resource)
    TA->>MON: POST /ingest<br/>Trust Score 확인 요청
    
    MON->>MON: Trust Score 계산<br/>agent-admin-01: 0.00
    MON->>MON: Required: 0.8
    MON->>MON: allowed = false
    
    MON->>TA: {allowed: false,<br/>trust: 0.00,<br/>required_trust: 0.8}
    
    alt Trust Score 부족
        TA->>MON: alert: action_blocked_by_trust_score
        TA->>AA: 403 Forbidden<br/>"Trust score 0.00 < 0.8"
        Note over AA: 요청 차단됨 ❌
    else Trust Score 충분
        TA->>TA: handle_delete_resource() 실행
        TA->>AA: 200 OK + 결과
    end
```

## Monitor의 Trust Score 관리

```mermaid
graph LR
    subgraph "Trust Score 계산"
        MSG[메시지 수신]
        SIG{서명<br/>유효?}
        RP{Replay<br/>공격?}
        REV{Revoked?}
        ACT{Action<br/>타입?}
        TS[Trust Score<br/>업데이트]
    end
    
    MSG --> SIG
    SIG -->|Yes| TS
    SIG -->|No| TS
    RP --> TS
    REV --> TS
    ACT --> TS
    
    TS -->|High-Risk| REQ[Required: 0.8]
    TS -->|Low-Risk| REQ2[Required: 0.3]
    
    REQ --> ALLOW{Allowed?}
    REQ2 --> ALLOW
    
    ALLOW -->|Yes| PASS[통과]
    ALLOW -->|No| BLOCK[차단 + Alert]
    
    style BLOCK fill:#f48771
    style PASS fill:#4ec9b0
```

## 데이터 흐름 상세

```mermaid
graph TD
    subgraph "1. 메시지 생성"
        A1[Agent A] -->|build_message| A2[서명 생성<br/>params_hash<br/>timestamp<br/>nonce]
        A2 --> A3[서명된 메시지]
    end
    
    subgraph "2. 메시지 전송"
        A3 -->|HTTP POST| B1[Agent B<br/>/a2a/invoke]
    end
    
    subgraph "3. 수신 처리"
        B1 --> B2[서명 검증]
        B2 -->|유효| B3[High-Risk?]
        B2 -->|무효| B4[400 Error]
        B3 -->|Yes| B5[Monitor에<br/>Trust 확인]
        B3 -->|No| B6[Action 처리]
        B5 -->|차단| B7[403 Error]
        B5 -->|통과| B6
    end
    
    subgraph "4. Monitor 로깅"
        B1 -.->|monitor_log| M1[Monitor<br/>/ingest]
        B6 -.->|monitor_log| M1
        M1 --> M2[Trust Score 계산]
        M2 --> M3[data.jsonl]
        M2 -->|Alert| M4[alerts.jsonl]
    end
    
    subgraph "5. 대시보드"
        M3 --> D1[Dashboard<br/>/dashboard]
        M4 --> D1
        D1 --> D2[실시간 모니터링]
    end
    
    style B4 fill:#f48771
    style B7 fill:#f48771
    style B6 fill:#4ec9b0
```

## Agent 역할 및 포트

```mermaid
graph LR
    subgraph "Agent Types"
        U[User Agent<br/>8001<br/>일반 작업]
        A[Admin Agent<br/>8003<br/>관리 작업]
        T[Tool Agent<br/>8002<br/>리소스 처리]
        O[Orchestrator<br/>8000<br/>라우팅]
    end
    
    subgraph "Monitor"
        M[Monitor<br/>8100<br/>감시 및 Trust 관리]
    end
    
    U -->|read_resource<br/>get_status<br/>ping| T
    U -->|다양한 요청| O
    A -->|delete_resource<br/>modify_config| T
    O -->|라우팅| T
    
    U -.->|모니터링| M
    A -.->|모니터링| M
    T -.->|모니터링| M
    O -.->|모니터링| M
    
    style U fill:#4ec9b0
    style A fill:#f48771
    style T fill:#569cd6
    style O fill:#dcdcaa
    style M fill:#9cdcfe
```

## Trust Score 업데이트 규칙

```mermaid
graph TD
    START[메시지 수신] --> CHECK1{Revoked?}
    CHECK1 -->|Yes| TS0[Trust = 0.0]
    CHECK1 -->|No| CHECK2{서명 유효?}
    
    CHECK2 -->|Yes| INC[Trust +0.05<br/>최대 1.0]
    CHECK2 -->|No| KEEP[Trust 유지]
    
    INC --> CHECK3{Replay 공격?}
    KEEP --> CHECK3
    
    CHECK3 -->|Yes + High-Risk| DEC[Trust -0.15<br/>최소 0.0]
    CHECK3 -->|No| SAVE[Trust 저장]
    DEC --> SAVE
    TS0 --> SAVE
    
    SAVE --> EVAL{Action 타입?}
    EVAL -->|High-Risk| REQ1[Required: 0.8]
    EVAL -->|Low-Risk| REQ2[Required: 0.3]
    
    REQ1 --> ALLOW{Trust >= Required?}
    REQ2 --> ALLOW
    
    ALLOW -->|Yes| PASS[통과]
    ALLOW -->|No| BLOCK[차단 + Alert]
    
    style BLOCK fill:#f48771
    style PASS fill:#4ec9b0
    style TS0 fill:#f48771
```

## 보안 검증 단계

```mermaid
graph TD
    MSG[메시지 수신] --> STEP1[1. 서명 검증]
    STEP1 -->|실패| ERR1[400: Invalid Signature]
    STEP1 -->|성공| STEP2[2. Recipient 확인]
    
    STEP2 -->|불일치| WARN[Warning Log]
    STEP2 -->|일치| STEP3[3. High-Risk Action?]
    
    STEP3 -->|No| STEP5[5. Action 처리]
    STEP3 -->|Yes| STEP4[4. Trust Score 확인]
    
    STEP4 -->|Monitor 요청| MON[Monitor /ingest]
    MON -->|allowed: false| ERR2[403: Trust Score 부족]
    MON -->|allowed: true| STEP5
    
    STEP5 --> RESULT[200 OK + 결과]
    
    style ERR1 fill:#f48771
    style ERR2 fill:#f48771
    style RESULT fill:#4ec9b0
    style WARN fill:#dcdcaa
```

## 실제 실행 예시: Admin Agent → Tool Agent

```mermaid
sequenceDiagram
    autonumber
    participant AA as Admin Agent<br/>Trust: 0.00
    participant TA as Tool Agent
    participant MON as Monitor
    participant DASH as Dashboard
    
    Note over AA: 10초마다 반복
    AA->>AA: send_to_agent()<br/>delete_resource
    AA->>AA: build_message()<br/>서명 생성
    AA->>TA: POST /a2a/invoke<br/>delete_resource
    
    TA->>MON: monitor_log()<br/>direction: in
    TA->>TA: verify_msg() ✅
    
    Note over TA: High-Risk 감지
    TA->>MON: POST /ingest<br/>Trust 확인
    
    MON->>MON: Trust 계산<br/>0.00 < 0.8
    MON->>MON: allowed = false
    MON->>MON: Alert 생성
    MON->>TA: {allowed: false}
    
    TA->>MON: monitor_log()<br/>action_blocked
    TA->>AA: 403 Forbidden
    
    MON->>DASH: 실시간 업데이트
    DASH->>DASH: Alert 표시<br/>Trust Score 표시
    
    Note over AA: 요청 실패 로그
```

---

## 주요 컴포넌트 설명

### 1. **Agent Layer**
- **User Agent**: 일반적인 작업 수행 (read_resource, get_status, ping)
- **Admin Agent**: 관리 작업 수행 (delete_resource, modify_config) - High-Risk
- **Tool Agent**: 리소스 처리 담당
- **Orchestrator**: 필요시 메시지 라우팅

### 2. **Monitor Layer**
- 모든 통신 로깅
- Trust Score 계산 및 관리
- Replay 공격 감지
- 보안 알림 생성
- 실시간 대시보드 제공

### 3. **보안 메커니즘**
- **서명 검증**: 모든 메시지에 암호화 서명 필수
- **Trust Score**: Agent 신뢰도 기반 접근 제어
- **Replay 방지**: Nonce 및 Message ID 중복 검사
- **High-Risk Action 차단**: Trust Score < 0.8 시 차단

### 4. **통신 프로토콜**
- HTTP POST 기반
- JSON 메시지 포맷
- 서명 필드 포함
- 비동기 처리 (FastAPI + asyncio)

---

## 파일 구조

```
a2a2/
├── agents/
│   ├── base_agent.py      # BaseAgentServer 클래스
│   ├── user_agent.py       # User Agent
│   ├── admin_agent.py      # Admin Agent
│   ├── tool_agent.py       # Tool Agent
│   └── orchestrator.py     # Orchestrator
├── monitor/
│   ├── monitor.py          # Monitor 서버
│   ├── data.jsonl          # 통신 로그
│   └── alerts.jsonl         # 보안 알림
├── common/
│   └── crypto.py           # 암호화/서명 모듈
└── tools/
    └── keygen.py            # 키 생성
```

