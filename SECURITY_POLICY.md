# 🔒 보안 정책 및 악성 Agent 판단 기준

## 현재 시스템의 악성/정상 판단 기준

현재 시스템은 **다층 보안 검증**을 통해 악성 agent를 탐지하고 차단합니다.

---

## 1. 판단 기준 (판단 요소)

### 1.1 서명 검증 (Signature Verification)
```python
sig = bool(msg.get("signature"))
```
- **정상**: 유효한 RSA 서명이 포함된 메시지
- **악성**: 서명이 없거나 무효한 서명
- **영향**: 서명 무효 시 Trust Score 증가 없음 (기본값 유지)

### 1.2 Replay 공격 감지
```python
def is_replay(a, p, n, m, ts, act):
    # 동일한 nonce나 message_id를 가진 메시지 감지
    # High-risk action에 대해서만 체크
```
- **정상**: 새로운 nonce와 message_id를 사용
- **악성**: 동일한 nonce/message_id로 메시지 재전송
- **영향**: Replay 감지 시 Trust Score -0.15

### 1.3 Trust Score 기반 판단
```python
# Trust Score 계산 규칙
if sig:  # 유효한 서명
    t = min(t + 0.05, 1.0)  # +0.05 증가 (최대 1.0)
if rp and act not in LOW_RISK:  # Replay 공격
    t = max(t - 0.15, 0)  # -0.15 감소 (최소 0.0)
```

**Trust Score 범위**: 0.0 ~ 1.0
- **초기값**: 0.35 (새로운 agent)
- **최대값**: 1.0
- **최소값**: 0.0

### 1.4 Action 타입별 요구사항
```python
LOW_RISK = {"get_status", "ping"}
HIGH_RISK = {"delete_resource", "modify_config"}

req_t = 0.8 if act in HIGH_RISK else 0.3
allowed = (t >= req_t) and (aid not in revoked)
```

- **Low-Risk Action** (`get_status`, `ping`):
  - 요구 Trust Score: **≥ 0.3**
  - 대부분의 agent가 수행 가능

- **High-Risk Action** (`delete_resource`, `modify_config`):
  - 요구 Trust Score: **≥ 0.8**
  - 높은 신뢰도가 필요한 작업

---

## 2. 악성 Agent 판단 프로세스

### 2.1 실시간 평가 흐름

```
메시지 수신
    ↓
1. 서명 검증
    ├─ 유효 → Trust +0.05
    └─ 무효 → Trust 변화 없음
    ↓
2. Replay 공격 검사
    ├─ 감지 → Trust -0.15 (High-Risk만)
    └─ 정상 → 변화 없음
    ↓
3. Trust Score vs 요구사항 비교
    ├─ Trust ≥ 요구사항 → 허용
    └─ Trust < 요구사항 → 차단 + 위반 카운트 +1
    ↓
4. 자동 차단 조건 확인
    ├─ Trust ≤ 0.1 → 자동 차단 (revoked)
    └─ 위반 횟수 ≥ 3 → 자동 차단 (revoked)
```

### 2.2 자동 차단 조건

```python
REVOKE_THRESHOLD = 0.1      # Trust Score 임계값
AUTO_REVOKE_STRIKES = 3    # 누적 위반 횟수

if t <= REVOKE_THRESHOLD or violations[aid] >= AUTO_REVOKE_STRIKES:
    revoked.add(aid)  # 자동 차단
```

**차단 조건 (둘 중 하나라도 만족):**
1. **Trust Score ≤ 0.1**: 신뢰도가 매우 낮음
2. **누적 위반 횟수 ≥ 3**: 3번 이상 차단된 요청 시도

---

## 3. 악성 행위 시나리오별 판단

### 시나리오 1: 서명 없는 메시지
```
행위: 서명 없이 메시지 전송
판단: 
  - 서명 검증 실패
  - Trust Score 증가 없음 (0.35 유지)
  - High-Risk Action 시도 → Trust 0.35 < 0.8 → 차단
결과: 위반 카운트 +1, 3회 누적 시 자동 차단
```

### 시나리오 2: Replay 공격
```
행위: 동일한 메시지를 반복 전송
판단:
  - Replay 공격 감지
  - Trust Score -0.15 (예: 0.35 → 0.20)
  - High-Risk Action 시도 → Trust 0.20 < 0.8 → 차단
결과: 위반 카운트 +1, Trust Score 감소
```

### 시나리오 3: Trust Score 부족으로 High-Risk Action 시도
```
행위: Trust Score 0.35인 agent가 delete_resource 시도
판단:
  - Trust 0.35 < 0.8 (요구사항) → 차단
  - 위반 카운트 +1
결과: 3회 누적 시 자동 차단
```

### 시나리오 4: 지속적인 악성 행위
```
1회차: 서명 무효 → Trust 0.35, 위반 +1
2회차: Replay 공격 → Trust 0.20, 위반 +2
3회차: High-Risk 시도 → Trust 0.20 < 0.8, 위반 +3
결과: 위반 횟수 ≥ 3 → 자동 차단 (revoked)
```

---

## 4. 판단 기준 요약표

| 판단 요소 | 정상 기준 | 악성 기준 | 영향 |
|---------|---------|---------|------|
| **서명 검증** | 유효한 RSA 서명 | 서명 없음/무효 | Trust +0.05 (정상) / 변화 없음 (악성) |
| **Replay 공격** | 새로운 nonce/ID | 동일 nonce/ID 재사용 | Trust -0.15 |
| **Trust Score** | ≥ 요구사항 | < 요구사항 | 요청 차단 |
| **위반 누적** | < 3회 | ≥ 3회 | 자동 차단 |
| **Trust 임계값** | > 0.1 | ≤ 0.1 | 자동 차단 |

---

## 5. 현재 시스템의 한계점

### 5.1 명시적 "악성" 판단 없음
- 현재 시스템은 **"차단 조건"**만 있지, **"악성 agent"**라는 명시적 레이블은 없습니다.
- 판단은 다음 기준으로 이루어집니다:
  - Trust Score 부족
  - 위반 횟수 누적
  - Replay 공격 감지

### 5.2 행동 기반 판단
- Agent의 **의도**가 아닌 **행동 결과**로 판단합니다.
- 예: Trust Score가 낮은 agent가 High-Risk Action을 시도하면 차단
- 예: Replay 공격을 감지하면 Trust Score 감소

### 5.3 자동 복구 없음
- 한 번 `revoked`되면 자동으로 복구되지 않습니다.
- 수동으로 `revoked` 세트에서 제거해야 합니다.

---

## 6. 개선 가능한 방향

### 6.1 명시적 악성 패턴 감지
```python
# 예시: 의심스러운 패턴 감지
- 짧은 시간 내 다수의 High-Risk Action 시도
- 서명은 유효하지만 Trust Score가 계속 낮음
- 특정 패턴의 메시지 반복 전송
```

### 6.2 위협 인텔리전스 연동
```python
# 예시: 알려진 악성 agent ID 블랙리스트
- 특정 agent_id가 알려진 악성 목록에 있으면 즉시 차단
- 특정 IP/엔드포인트에서의 요청 차단
```

### 6.3 머신러닝 기반 이상 탐지
```python
# 예시: 정상 행동 패턴 학습
- 정상 agent의 행동 패턴 학습
- 이상 행동 패턴 자동 감지
- 동적 Trust Score 조정
```

---

## 7. 실제 판단 예시

### 예시 1: Admin Agent (Trust Score 0.00)
```
상태: Trust Score 0.00
행위: delete_resource 시도
판단:
  - Trust 0.00 < 0.8 (요구사항)
  - 차단 (403 Forbidden)
  - 위반 카운트 +1
결과: 3회 누적 시 자동 차단
```

### 예시 2: Malicious Agent (Replay 공격)
```
행위: 동일한 메시지 반복 전송
판단:
  - Replay 공격 감지
  - Trust Score -0.15
  - High-Risk Action 시도 → 차단
결과: Trust Score 감소 + 위반 누적
```

### 예시 3: 정상 Agent (Trust Score 0.85)
```
상태: Trust Score 0.85
행위: delete_resource 시도
판단:
  - Trust 0.85 ≥ 0.8 (요구사항)
  - 허용
결과: 요청 처리 성공
```

---

## 결론

현재 시스템은 **"악성 agent"**를 명시적으로 정의하지 않고, **"차단 조건"**을 통해 악성 행위를 방지합니다:

1. **Trust Score 기반**: 신뢰도가 낮으면 High-Risk Action 차단
2. **위반 누적**: 3회 이상 차단되면 자동 차단
3. **Replay 감지**: 중복 메시지 감지 시 Trust Score 감소
4. **서명 검증**: 무효한 서명은 Trust Score 증가 없음

이 방식은 **행동 기반 보안 정책**으로, agent의 의도보다는 **실제 행동 결과**를 기준으로 판단합니다.

