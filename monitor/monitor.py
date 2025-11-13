import time, requests, json
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, FileResponse
from pathlib import Path
from datetime import datetime
from monitor.plot_utils import plot_trust  # 👈 종료 시 자동 그래프 생성
from collections import deque
from contextlib import asynccontextmanager

def baseline_refresh_worker():
    """주기적으로 baseline 모델 새로고침"""
    import threading
    while True:
        try:
            time.sleep(60)  # 1분마다 새로고침
            from monitor.baseline_model import baseline_model
            baseline_model.load_from_logs(limit=10000)
        except Exception as e:
            print(f"[Baseline] Refresh error: {e}")

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    try:
        # Baseline 모델 초기 로드
        from monitor.baseline_model import baseline_model
        baseline_model.load_from_logs(limit=10000)
        print("[+] Baseline models loaded")
        
        # Baseline 새로고침 워커 시작
        import threading
        refresh_thread = threading.Thread(target=baseline_refresh_worker, daemon=True)
        refresh_thread.start()
        print("[+] Baseline refresh worker started")
    except Exception as e:
        print(f"⚠️ Baseline 초기화 중 오류: {e}")
    
    yield
    
    # Shutdown
    print("\n📊 서버 종료 감지: trust_timeline.png 생성 중...")
    try:
        plot_trust()
        print("✅ trust_timeline.png 갱신 완료!")
    except Exception as e:
        print(f"⚠️ 그래프 생성 중 오류 발생: {e}")

app = FastAPI(lifespan=lifespan)

# 로그 파일 경로
DATA = "monitor/data.jsonl"
ALERTS = "monitor/alerts.jsonl"
BEHAVIOR_LOG = "monitor/behavior_log.jsonl"  # 행동 기반 탐지용 상세 로그

trust = {}
revoked = set()
recent = {}
violations = {}

# 실시간 모니터링을 위한 메모리 버퍼 (최근 100개 이벤트)
recent_events = deque(maxlen=100)

# Low-risk actions: 읽기 작업, 상태 확인, 일반적인 요청
LOW_RISK = {
    "get_status", "ping", "read_resource",
    "request_task",  # Orchestrator를 통한 작업 요청
    "search_documents", "query_database",
    "check_system_health", "get_service_status",
    "analyze_customer_data", "analyze_data", "analyze_report_data",
    "generate_report", "generate_monthly_sales_report", "generate_weekly_summary",
    "cleanup_logs", "check_disk_space"
}

# High-risk actions: 삭제, 수정, 권한 변경 등 위험한 작업
HIGH_RISK = {
    "delete_resource",
    "modify_config", "update_system_config",
    "create_database_backup",  # 백업 생성은 중요하지만 위험할 수 있음
    "update_user_permissions",
    "archive_old_logs",  # 로그 삭제는 위험할 수 있음
    "cleanup_temp_files", "rotate_application_logs"
}

# Trust 기반 차단 임계값
REVOKE_THRESHOLD = 0.1
AUTO_REVOKE_STRIKES = 3

def now():
    return datetime.utcnow().isoformat() + "Z"

def log(path, obj):
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(obj) + "\n")

def record_event(event_type: str, data: dict):
    recent_events.append({
        "timestamp": now(),
        "type": event_type,
        "data": data
    })

def record_alert(aid: str, reason: dict):
    alert_data = {
        "ts": now(),
        "sender": aid,
        "reason": reason
    }
    log(ALERTS, alert_data)
    record_event("alert", alert_data)

def log_behavior(action_log: dict):
    """행동 기반 탐지용 상세 로그 기록"""
    behavior_entry = {
        "timestamp": now(),
        **action_log  # 모든 행동 정보 포함
    }
    log(BEHAVIOR_LOG, behavior_entry)

def evaluate_message(payload: dict, *, log_event: bool = True):
    if log_event:
        # payload를 먼저 로그에 저장 (나중에 trust 추가)
        log_entry = payload.copy()
        log(DATA, log_entry)
        record_event("ingest", payload)

    msg = payload.get("message")
    if not msg:
        return {"status": "logged"}

    aid = msg.get("sender", {}).get("agent_id") or payload.get("agent", "unknown")
    act = msg.get("action", "unknown")
    sig = bool(msg.get("signature"))
    # Required trust score 계산 개선
    if act in HIGH_RISK:
        req_t = 0.7  # High-risk는 0.7 이상 필요 (0.8에서 완화)
    elif act in LOW_RISK:
        req_t = 0.2  # Low-risk는 0.2 이상 필요 (0.3에서 완화)
    else:
        # 알 수 없는 action은 기본적으로 중간 수준 요구
        req_t = 0.4
    rh = msg.get("params_hash")
    n = msg.get("nonce")
    mid = msg.get("message_id")

    if log_event:
        rp = is_replay(aid, rh, n, mid, now(), act)
        t = update_trust(aid, sig, rp, aid in revoked, act)
        allowed = (t >= req_t) and (aid not in revoked)

        result = {
            "status": "evaluated",
            "sig_valid": sig,
            "replay": rp,
            "revoked": aid in revoked,
            "trust": t,
            "required_trust": req_t,
            "allowed": allowed
        }

        if not allowed:
            # Low-risk action이 차단된 경우는 위반 횟수를 증가시키지 않음
            # (정상적인 agent가 trust score가 일시적으로 낮아서 차단될 수 있음)
            if act not in LOW_RISK:
                # High-risk action만 위반 횟수 증가
                violations[aid] = violations.get(aid, 0) + 1
            reason = {
                "sig_valid": sig,
                "replay": rp,
                "revoked": aid in revoked,
                "trust": t,
                "required_trust": req_t,
                "violations": violations.get(aid, 0)
            }
            record_alert(aid, reason)

            # 일정 조건 만족 시 자동 차단
            if t <= REVOKE_THRESHOLD or violations.get(aid, 0) >= AUTO_REVOKE_STRIKES:
                if aid not in revoked:
                    revoked.add(aid)
                    reason["action"] = "auto_revoke"
                    record_alert(aid, reason)
                result["revoked"] = True
                result["allowed"] = False
        else:
            # 허용된 경우 위반 카운트 감소
            if aid in violations:
                violations[aid] = max(0, violations[aid] - 1)
        return result
    else:
        # 로그 없이 현재 상태 기반으로 평가 (상태 변경 없음)
        t = trust.get(aid, 0.5)  # 초기값을 0.5로 변경
        allowed = (t >= req_t) and (aid not in revoked)
        rp = False
    return {
            "status": "evaluated",
        "sig_valid": sig,
        "replay": rp,
        "revoked": aid in revoked,
        "trust": t,
        "required_trust": req_t,
        "allowed": allowed
    }

@app.post("/ingest")
async def ingest(req: Request):
    payload = await req.json()
    result = evaluate_message(payload, log_event=True)
    
    # Baseline 모델 업데이트 및 이상 탐지
    msg = payload.get("message", {})
    if msg:
        from monitor.baseline_model import baseline_model
        sender_id = msg.get("sender", {}).get("agent_id", "unknown")
        action = msg.get("action", "unknown")
        recipient_id = msg.get("recipient", {}).get("agent_id")
        timestamp = msg.get("timestamp", now())
        
        # Baseline 업데이트
        baseline_model.update_baseline(sender_id, action, recipient_id, timestamp)
        
        # 이상 탐지
        anomaly_result = baseline_model.detect_anomaly(sender_id, action, recipient_id, timestamp)
        if anomaly_result.get("has_anomaly"):
            record_alert(sender_id, {
                "type": "behavioral_anomaly",
                "anomalies": anomaly_result.get("anomalies", []),
                "action": action
            })
    
    # 행동 기반 탐지용 상세 로그 기록
    if msg:
        sender_id = msg.get("sender", {}).get("agent_id", "unknown")
        recipient_id = msg.get("recipient", {}).get("agent_id", "unknown")
        action = msg.get("action", "unknown")
        params = msg.get("params", {})
        
        behavior_log = {
            "event_type": "action_attempt",
            "sender_agent": sender_id,
            "recipient_agent": recipient_id,
            "action": action,
            "params": params,
            "message_id": msg.get("message_id"),
            "correlation_id": msg.get("correlation_id"),
            "timestamp": msg.get("timestamp"),
            "signature_valid": bool(msg.get("signature")),
            "trust_score": result.get("trust") if isinstance(result, dict) else None,
            "required_trust": 0.7 if action in HIGH_RISK else (0.2 if action in LOW_RISK else 0.4),
            "allowed": result.get("allowed") if isinstance(result, dict) else None,
            "blocked": not result.get("allowed") if isinstance(result, dict) else None,
            "revoked": result.get("revoked") if isinstance(result, dict) else False,
            "replay_detected": result.get("replay") if isinstance(result, dict) else False,
            "violation_count": violations.get(sender_id, 0),
            "risk_level": "high" if action in HIGH_RISK else "low",
            "direction": "out"  # Monitor에 도착한 메시지는 발신 메시지
        }
        log_behavior(behavior_log)
    
    # Trust Score를 추가로 로그에 기록
    if isinstance(result, dict) and "trust" in result:
        trust_entry = {
            "timestamp": now(),
            "message": payload.get("message", {}),
            "trust": result["trust"],
            "agent": payload.get("message", {}).get("sender", {}).get("agent_id", "unknown")
        }
        log(DATA, trust_entry)
        
        # recent_events에도 trust score 추가 (타임라인 그래프용)
        # 가장 최근 ingest 이벤트를 찾아서 trust score 추가
        if recent_events:
            last_event = recent_events[-1]
            if last_event.get("type") == "ingest" and last_event.get("data") == payload:
                last_event["data"] = payload.copy()
                last_event["data"]["trust"] = result["trust"]
    return result

@app.post("/evaluate")
async def evaluate(req: Request):
    payload = await req.json()
    return evaluate_message(payload, log_event=False)

def is_replay(a, p, n, m, ts, act):
    k = (a, p)
    pr = recent.get(k)
    recent[k] = {"ts": ts, "nonce": n, "msg": m}
    if not pr:
        return False
    if act in LOW_RISK:
        return False
    return pr["nonce"] == n or pr["msg"] == m

def update_trust(a, sig, rp, rev, act):
    """Trust score 업데이트 로직 개선"""
    # 초기 trust score: 0.5 (더 관대한 시작점)
    t = trust.get(a, 0.5)
    
    if rev:
        return 0.0
    
    # Replay attack 감지 시 큰 페널티
    if rp:
        if act in HIGH_RISK:
            t = max(t - 0.3, 0)  # High-risk replay는 큰 페널티
        else:
            t = max(t - 0.15, 0)  # Low-risk replay는 작은 페널티
    
    # Signature 검증
    if sig:
        # 유효한 signature면 신뢰도 증가
        if act in LOW_RISK:
            t = min(t + 0.02, 1.0)  # Low-risk는 작은 증가
        else:
            t = min(t + 0.05, 1.0)  # High-risk는 더 큰 증가 (신뢰할 수 있는 agent)
    else:
        # Signature가 없으면 약간 감소 (하지만 너무 가혹하지 않게)
        if act in HIGH_RISK:
            t = max(t - 0.1, 0)  # High-risk는 signature 필수
        # Low-risk는 signature 없어도 허용 (기존 시스템 호환)
    
    # 정상적인 행동 패턴 보상 (Low-risk action 성공)
    if act in LOW_RISK and not rp:
        t = min(t + 0.01, 1.0)  # 정상적인 low-risk 행동은 약간 보상
    
    trust[a] = t
    return t

@app.get("/dashboard")
async def dashboard():
    """실시간 모니터링 대시보드"""
    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>A2A Agent Monitor Dashboard</title>
        <meta http-equiv="refresh" content="3">
        <style>
            body {{ font-family: monospace; margin: 20px; background: #1e1e1e; color: #d4d4d4; }}
            h1 {{ color: #4ec9b0; }}
            .stats {{ display: flex; gap: 20px; margin: 20px 0; }}
            .stat-box {{ background: #252526; padding: 15px; border-radius: 5px; border: 1px solid #3e3e42; }}
            .stat-box h3 {{ margin: 0 0 10px 0; color: #569cd6; }}
            .stat-value {{ font-size: 24px; color: #4ec9b0; }}
            .events {{ background: #252526; padding: 15px; border-radius: 5px; margin: 20px 0; max-height: 500px; overflow-y: auto; }}
            .event {{ padding: 8px; margin: 5px 0; border-left: 3px solid #3e3e42; background: #1e1e1e; }}
            .event.alert {{ border-left-color: #f48771; }}
            .event.ingest {{ border-left-color: #4ec9b0; }}
            .trust-table {{ width: 100%; border-collapse: collapse; margin: 20px 0; }}
            .trust-table th, .trust-table td {{ padding: 10px; text-align: left; border: 1px solid #3e3e42; }}
            .trust-table th {{ background: #2d2d30; color: #569cd6; }}
            .trust-low {{ color: #f48771; }}
            .trust-medium {{ color: #dcdcaa; }}
            .trust-high {{ color: #4ec9b0; }}
        </style>
    </head>
    <body>
        <h1>🤖 A2A Agent Monitor Dashboard</h1>
        
        <div class="stats">
            <div class="stat-box">
                <h3>Registered Agents</h3>
                <div class="stat-value">{len(trust)}</div>
            </div>
            <div class="stat-box">
                <h3>Recent Events</h3>
                <div class="stat-value">{len(recent_events)}</div>
            </div>
            <div class="stat-box">
                <h3>Revoked Agents</h3>
                <div class="stat-value">{len(revoked)}</div>
            </div>
        </div>
        
        <h2>Agent Trust Scores</h2>
        <div style="margin-bottom: 10px; padding: 10px; background: #252526; border-radius: 5px;">
            <strong>Status 기준:</strong><br>
            • <span style="color: #f48771;">REVOKED</span>: Trust Score ≤ {REVOKE_THRESHOLD} 또는 위반 횟수 ≥ {AUTO_REVOKE_STRIKES}회<br>
            • <span style="color: #4ec9b0;">ACTIVE</span>: REVOKED 조건을 만족하지 않음
        </div>
        <table class="trust-table">
            <tr>
                <th>Agent ID</th>
                <th>Trust Score</th>
                <th>Status</th>
                <th>위반 횟수</th>
            </tr>
    """
    
    # 모든 등록된 agent 표시 (trust에 없는 agent도 표시)
    all_agents = set(trust.keys())
    # AGENT_REGISTRY에서도 agent 목록 가져오기
    from agents.base_agent import AGENT_REGISTRY
    for agent_id in AGENT_REGISTRY.keys():
        all_agents.add(agent_id)
    
    for agent_id in sorted(all_agents):
        trust_score = trust.get(agent_id, 0.5)  # 기본값 0.5
        status = "REVOKED" if agent_id in revoked else "ACTIVE"
        violation_count = violations.get(agent_id, 0)
        trust_class = "trust-low" if trust_score < 0.5 else "trust-medium" if trust_score < 0.8 else "trust-high"
        html += f"""
            <tr>
                <td>{agent_id}</td>
                <td class="{trust_class}">{trust_score:.2f}</td>
                <td>{status}</td>
                <td>{violation_count}</td>
            </tr>
        """
    
    html += """
        </table>
        
        <h2>Agent Interaction Network</h2>
        <div style="background: #252526; padding: 15px; border-radius: 5px; margin: 20px 0;">
            <div id="networkContainer" style="height: 400px; border: 1px solid #3e3e42; border-radius: 5px;"></div>
            <div id="networkError" style="color: #f48771; display: none; margin-top: 10px;"></div>
            <p style="margin-top: 10px; font-size: 12px; color: #858585;">
                💡 화살표는 메시지 전송 방향을 나타냅니다. 노드를 드래그하여 배치를 변경할 수 있습니다.
            </p>
        </div>
        
        <h2>Agent Activity Graph</h2>
        <div style="background: #252526; padding: 15px; border-radius: 5px; margin: 20px 0;">
            <canvas id="activityChart" style="max-height: 400px;"></canvas>
            <div id="activityError" style="color: #f48771; display: none; margin-top: 10px;"></div>
        </div>
        
        <h2>Agent Trust Timelines</h2>
        <div style="background: #252526; padding: 15px; border-radius: 5px; margin: 20px 0;">
            <p style="color: #d4d4d4; margin-bottom: 15px;">
                📊 각 Agent의 Trust Score 변화와 Alert 발생 시점을 시각화합니다.
            </p>
            <div id="trustTimelinesContainer"></div>
        </div>
        
        <h2>Baseline Models</h2>
        <div style="background: #252526; padding: 15px; border-radius: 5px; margin: 20px 0;">
            <p style="color: #d4d4d4; margin-bottom: 10px;">
                🧠 각 Agent의 행동 패턴 Baseline 모델 정보
            </p>
            <div id="baselinesContainer"></div>
        </div>
        
        <h2>Recent Events (Last 20)</h2>
        <div class="events">
    """
    
    for event in list(recent_events)[-20:]:
        event_type = event.get("type", "unknown")
        timestamp = event.get("timestamp", "unknown")
        data = event.get("data", {})
        
        if event_type == "alert":
            html += f'<div class="event alert">'
            html += f'<strong>🚨 ALERT</strong> [{timestamp}]<br>'
            html += f'Sender: {data.get("sender", "unknown")}<br>'
            html += f'Reason: {json.dumps(data.get("reason", {}), indent=2)}'
        else:
            html += f'<div class="event ingest">'
            html += f'<strong>📨 EVENT</strong> [{timestamp}]<br>'
            direction = data.get("direction", "unknown")
            agent = data.get("agent", "unknown")
            action = data.get("action") or (data.get("message", {}).get("action") if data.get("message") else "unknown")
            html += f'Direction: {direction} | Agent: {agent} | Action: {action}'
        
        html += '</div>'
    
    html += """
        </div>
        
        <p><small>Auto-refresh every 3 seconds | Last updated: """ + now() + """</small></p>
        
        <script src="https://unpkg.com/vis-network@latest/standalone/umd/vis-network.min.js"></script>
        <script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
        <script>
            let network = null;
            let activityChart = null;
            
            // Agent Interaction Network Graph
            async function loadNetworkGraph() {
                try {
                    const container = document.getElementById('networkContainer');
                    if (!container) {
                        console.error('Network container not found');
                        return;
                    }
                    
                    if (network) {
                        network.destroy();
                    }
                    
                    const response = await fetch('/api/activity?limit=200');
                    if (!response.ok) {
                        throw new Error('Failed to fetch: ' + response.status);
                    }
                    
                    const data = await response.json();
                    const activity = data.activity || {};
                    
                    // 상호작용 데이터 가져오기
                    const networkResponse = await fetch('/api/interactions?limit=200');
                    if (!networkResponse.ok) {
                        throw new Error('Failed to fetch interactions: ' + networkResponse.status);
                    }
                    
                    const networkData = await networkResponse.json();
                    const interactions = networkData.interactions || {};
                    const revokedAgents = networkData.revoked || [];
                    
                    // 모든 agent 수집
                    const allAgents = new Set();
                    Object.keys(interactions).forEach(from => {
                        allAgents.add(from);
                        Object.keys(interactions[from]).forEach(to => {
                            allAgents.add(to);
                        });
                    });
                    
                    if (allAgents.size === 0) {
                        container.innerHTML = '<p style="color: #d4d4d4; text-align: center; padding: 20px;">No interaction data available yet</p>';
                        return;
                    }
                    
                    // Nodes 생성
                    const nodes = Array.from(allAgents).map((agent, idx) => {
                        const colors = ['#4ec9b0', '#569cd6', '#dcdcaa', '#f48771', '#9cdcfe'];
                        const isRevoked = revokedAgents.includes(agent);
                        return {
                            id: agent,
                            label: agent.replace('agent-', '').replace('-01', ''),
                            color: {
                                background: isRevoked ? '#f48771' : colors[idx % colors.length],
                                border: isRevoked ? '#ff0000' : colors[idx % colors.length],
                                highlight: {
                                    background: isRevoked ? '#ff6666' : colors[idx % colors.length] + 'CC',
                                    border: isRevoked ? '#ff0000' : colors[idx % colors.length]
                                }
                            },
                            font: { color: '#d4d4d4', size: 14 },
                            shape: 'box',
                            borderWidth: isRevoked ? 3 : 2
                        };
                    });
                    
                    // Edges 생성 (화살표) - 겹침 방지 및 가시성 개선
                    const edges = [];
                    const actionColors = {
                        'delete_resource': '#f48771',
                        'modify_config': '#f48771',
                        'read_resource': '#4ec9b0',
                        'write_resource': '#569cd6',
                        'get_status': '#dcdcaa',
                        'ping': '#9cdcfe',
                        'request_task': '#c586c0',
                        'analyze_data': '#c586c0',
                        'generate_report': '#c586c0',
                        'cleanup_logs': '#c586c0'
                    };
                    
                    Object.keys(interactions).forEach(from => {
                        Object.keys(interactions[from]).forEach(to => {
                            const count = interactions[from][to];
                            // 화살표를 얇게 하되 가시성 유지, 겹침 방지
                            edges.push({
                                from: from,
                                to: to,
                                arrows: {
                                    to: {
                                        enabled: true,
                                        scaleFactor: 1.2,  // 적당한 크기
                                        type: 'arrow'
                                    }
                                },
                                label: count > 1 ? String(count) : '',
                                color: { 
                                    color: '#4ec9b0',  // 밝은 청록색
                                    highlight: '#9cdcfe',
                                    opacity: 0.9
                                },
                                width: Math.min(Math.max(count * 0.8, 2), 8),  // 2-8px로 제한
                                font: { 
                                    color: '#ffffff',
                                    size: 12,
                                    align: 'middle',
                                    strokeWidth: 2,
                                    strokeColor: '#1e1e1e'
                                },
                                smooth: {
                                    type: 'curvedCW',  // 곡선으로 겹침 방지
                                    roundness: 0.3
                                },
                                selectionWidth: 4,
                                length: 200  // 최소 길이 설정
                            });
                        });
                    });
                    
                    const graphData = { nodes: nodes, edges: edges };
                    
                    const options = {
                        nodes: {
                            shape: 'box',
                            font: { color: '#d4d4d4', size: 14 },
                            borderWidth: 2
                        },
                        edges: {
                            arrows: {
                                to: {
                                    enabled: true,
                                    scaleFactor: 1.2,
                                    type: 'arrow'
                                }
                            },
                            smooth: {
                                type: 'curvedCW',  // 곡선으로 겹침 방지
                                roundness: 0.3
                            },
                            color: {
                                color: '#4ec9b0',
                                highlight: '#9cdcfe',
                                opacity: 0.9
                            },
                            width: 2,
                            selectionWidth: 4
                        },
                        physics: {
                            enabled: true,
                            stabilization: { 
                                iterations: 200,  // 더 많은 반복으로 안정화
                                fit: true
                            },
                            barnesHut: {
                                gravitationalConstant: -2000,  // 노드 간 거리 증가
                                centralGravity: 0.1,
                                springLength: 200,  // 스프링 길이 증가
                                springConstant: 0.04,
                                damping: 0.09
                            }
                        },
                        interaction: {
                            dragNodes: true,
                            dragView: true,
                            zoomView: true
                        }
                    };
                    
                    network = new vis.Network(container, graphData, options);
                } catch (error) {
                    console.error('Error loading network graph:', error);
                    const errorDiv = document.getElementById('networkError');
                    if (errorDiv) {
                        errorDiv.textContent = 'Error: ' + error.message;
                        errorDiv.style.display = 'block';
                    }
                }
            }
            
            async function loadActivityChart() {
                try {
                    const canvas = document.getElementById('activityChart');
                    if (!canvas) {
                        console.error('Activity chart canvas not found');
                        return;
                    }
                    
                    if (activityChart) {
                        activityChart.destroy();
                    }
                    
                    const response = await fetch('/api/activity?limit=200');
                    if (!response.ok) {
                        throw new Error('Failed to fetch: ' + response.status);
                    }
                    
                    const data = await response.json();
                    const activity = data.activity || {};
                    
                    const agents = Object.keys(activity);
                    if (agents.length === 0) {
                        canvas.parentElement.innerHTML = '<p style="color: #d4d4d4; text-align: center; padding: 20px;">No activity data available yet</p>';
                        return;
                    }
                    
                    // 모든 action 타입 수집
                    const allActions = new Set();
                    agents.forEach(agent => {
                        if (activity[agent] && activity[agent].actions) {
                            Object.keys(activity[agent].actions).forEach(action => allActions.add(action));
                        }
                    });
                    
                    if (allActions.size === 0) {
                        canvas.parentElement.innerHTML = '<p style="color: #d4d4d4; text-align: center; padding: 20px;">No action data available yet</p>';
                        return;
                    }
                    
                    // 각 action별로 dataset 생성
                    const datasets = Array.from(allActions).map((action, idx) => {
                        const colors = ['#4ec9b0', '#569cd6', '#dcdcaa', '#f48771', '#9cdcfe', '#ce9178', '#c586c0'];
                        return {
                            label: action,
                            data: agents.map(agent => {
                                return (activity[agent] && activity[agent].actions && activity[agent].actions[action]) || 0;
                            }),
                            backgroundColor: colors[idx % colors.length] + '80',
                            borderColor: colors[idx % colors.length],
                            borderWidth: 1
                        };
                    });
                    
                    activityChart = new Chart(canvas, {
                        type: 'bar',
                        data: {
                            labels: agents,
                            datasets: datasets
                        },
                        options: {
                            responsive: true,
                            maintainAspectRatio: false,
                            plugins: {
                                legend: { 
                                    position: 'top',
                                    labels: { color: '#d4d4d4' }
                                },
                                title: { 
                                    display: true, 
                                    text: 'Agent Actions by Type (각 Agent의 행동 분포)',
                                    color: '#d4d4d4',
                                    font: { size: 14 }
                                }
                            },
                            scales: {
                                x: { 
                                    ticks: { color: '#d4d4d4' }, 
                                    grid: { color: '#3e3e42' } 
                                },
                                y: { 
                                    ticks: { color: '#d4d4d4' }, 
                                    grid: { color: '#3e3e42' },
                                    beginAtZero: true
                                }
                            }
                        }
                    });
                } catch (error) {
                    console.error('Error loading activity chart:', error);
                    const errorDiv = document.getElementById('activityError');
                    if (errorDiv) {
                        errorDiv.textContent = 'Error: ' + error.message;
                        errorDiv.style.display = 'block';
                    }
                }
            }
            
            // vis-network와 Chart.js 로드 대기 후 그래프 로드
            let trustTimelineCharts = {};
            
            async function loadTrustTimelines() {
                try {
                    const container = document.getElementById('trustTimelinesContainer');
                    if (!container) return;
                    
                    // 모든 agent 목록 가져오기
                    const agentsResponse = await fetch('/api/trust');
                    if (!agentsResponse.ok) return;
                    const agentsData = await agentsResponse.json();
                    const agents = Object.keys(agentsData.trust || {});
                    
                    if (agents.length === 0) {
                        container.innerHTML = '<p style="color: #d4d4d4; text-align: center; padding: 20px;">No agent data available yet</p>';
                        return;
                    }
                    
                    container.innerHTML = '';
                    
                    // 각 agent별로 timeline 그래프 생성
                    for (const agentId of agents) {
                        const timelineResponse = await fetch(`/api/agent_timeline/${agentId}?limit=200`);
                        if (!timelineResponse.ok) continue;
                        
                        const timelineData = await timelineResponse.json();
                        const timeline = timelineData.timeline || [];
                        const alerts = timelineData.alerts || [];
                        
                        if (timeline.length === 0) continue;
                        
                        // 그래프 컨테이너 생성
                        const chartDiv = document.createElement('div');
                        chartDiv.style.marginBottom = '30px';
                        chartDiv.style.background = '#1e1e1e';
                        chartDiv.style.padding = '15px';
                        chartDiv.style.borderRadius = '5px';
                        chartDiv.innerHTML = `
                            <h3 style="color: #569cd6; margin-top: 0;">${agentId}</h3>
                            <canvas id="timeline_${agentId}" style="max-height: 300px;"></canvas>
                        `;
                        container.appendChild(chartDiv);
                        
                        // Chart.js로 그래프 생성
                        const canvas = document.getElementById(`timeline_${agentId}`);
                        if (!canvas) continue;
                        
                        const ctx = canvas.getContext('2d');
                        
                        // Trust score 데이터 준비
                        const labels = timeline.map(t => {
                            const date = new Date(t.timestamp);
                            return date.toLocaleTimeString();
                        });
                        const trustScores = timeline.map(t => t.trust);
                        
                        // Alert 시점 마커 데이터
                        const alertAnnotations = alerts.map(alert => {
                            const alertTime = new Date(alert.timestamp);
                            const alertIndex = timeline.findIndex(t => {
                                const tTime = new Date(t.timestamp);
                                return Math.abs(tTime - alertTime) < 60000; // 1분 이내
                            });
                            return alertIndex >= 0 ? alertIndex : null;
                        }).filter(idx => idx !== null);
                        
                        // 기존 차트 제거
                        if (trustTimelineCharts[agentId]) {
                            trustTimelineCharts[agentId].destroy();
                        }
                        
                        trustTimelineCharts[agentId] = new Chart(ctx, {
                            type: 'line',
                            data: {
                                labels: labels,
                                datasets: [{
                                    label: 'Trust Score',
                                    data: trustScores,
                                    borderColor: '#4ec9b0',
                                    backgroundColor: 'rgba(78, 201, 176, 0.1)',
                                    borderWidth: 2,
                                    fill: true,
                                    tension: 0.4
                                }, {
                                    label: 'Alerts',
                                    data: alertAnnotations.map(idx => trustScores[idx] || null),
                                    borderColor: '#f48771',
                                    backgroundColor: '#f48771',
                                    pointRadius: 6,
                                    pointHoverRadius: 8,
                                    showLine: false,
                                    pointStyle: 'triangle'
                                }]
                            },
                            options: {
                                responsive: true,
                                maintainAspectRatio: false,
                                plugins: {
                                    legend: {
                                        labels: { color: '#d4d4d4' }
                                    },
                                    title: {
                                        display: true,
                                        text: `${agentId} Trust Score Timeline`,
                                        color: '#d4d4d4',
                                        font: { size: 14 }
                                    },
                                    tooltip: {
                                        callbacks: {
                                            label: function(context) {
                                                if (context.datasetIndex === 0) {
                                                    return `Trust: ${context.parsed.y.toFixed(3)}`;
                                                } else {
                                                    return 'Alert';
                                                }
                                            }
                                        }
                                    }
                                },
                                scales: {
                                    x: {
                                        ticks: { color: '#d4d4d4', maxRotation: 45 },
                                        grid: { color: '#3e3e42' }
                                    },
                                    y: {
                                        ticks: { color: '#d4d4d4' },
                                        grid: { color: '#3e3e42' },
                                        min: 0,
                                        max: 1
                                    }
                                }
                            }
                        });
                    }
                } catch (error) {
                    console.error('Error loading trust timelines:', error);
                }
            }
            
            async function loadBaselines() {
                try {
                    const container = document.getElementById('baselinesContainer');
                    if (!container) return;
                    
                    const response = await fetch('/api/baselines');
                    if (!response.ok) {
                        container.innerHTML = '<p style="color: #858585;">Baseline data not available yet</p>';
                        return;
                    }
                    
                    const data = await response.json();
                    const baselines = data.baselines || {};
                    
                    if (Object.keys(baselines).length === 0) {
                        container.innerHTML = '<p style="color: #858585;">No baseline models available yet. Baseline models are built as agents perform actions.</p>';
                        return;
                    }
                    
                    let html = '<div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); gap: 15px;">';
                    
                    for (const [agentId, baseline] of Object.entries(baselines)) {
                        html += `
                            <div style="background: #1e1e1e; padding: 15px; border-radius: 5px; border: 1px solid #3e3e42;">
                                <h4 style="color: #569cd6; margin-top: 0;">${agentId}</h4>
                                <p style="color: #d4d4d4; font-size: 12px; margin: 5px 0;">
                                    <strong>Total Actions:</strong> ${baseline.total_actions}<br>
                                    <strong>Avg Interval:</strong> ${baseline.avg_interval_seconds.toFixed(1)}s<br>
                                    <strong>Top Actions:</strong> ${Object.entries(baseline.action_frequencies)
                                        .sort((a, b) => b[1] - a[1])
                                        .slice(0, 3)
                                        .map(([action, freq]) => `${action} (${(freq * 100).toFixed(1)}%)`)
                                        .join(', ')}
                                </p>
                            </div>
                        `;
                    }
                    
                    html += '</div>';
                    container.innerHTML = html;
                } catch (error) {
                    console.error('Error loading baselines:', error);
                    const container = document.getElementById('baselinesContainer');
                    if (container) {
                        container.innerHTML = '<p style="color: #f48771;">Error loading baseline data</p>';
                    }
                }
            }
            
            function initCharts() {
                if (typeof vis === 'undefined' || typeof Chart === 'undefined') {
                    setTimeout(initCharts, 100);
                    return;
                }
                loadNetworkGraph();
                loadActivityChart();
                loadTrustTimelines();
                loadBaselines();
            }
            
            if (document.readyState === 'loading') {
                document.addEventListener('DOMContentLoaded', initCharts);
            } else {
                initCharts();
            }
        </script>
    </body>
    </html>
    """
    return HTMLResponse(content=html)

@app.get("/api/events")
async def get_events(limit: int = 50):
    """Get recent events as JSON"""
    return {
        "events": list(recent_events)[-limit:],
        "total": len(recent_events)
    }

@app.get("/api/trust")
async def get_trust():
    """Get current trust scores"""
    return {
        "trust": trust,
        "revoked": list(revoked)
    }

@app.get("/api/stats")
async def get_stats():
    """Get monitoring statistics"""
    return {
        "total_agents": len(trust),
        "revoked_agents": len(revoked),
        "recent_events": len(recent_events),
        "trust_scores": trust
    }

@app.get("/api/activity")
async def get_activity(limit: int = 100):
    """Get agent activity data for graph visualization"""
    # data.jsonl과 recent_events에서 agent별 행위 추출
    activity_data = {}
    
    # recent_events에서 추출
    for event in list(recent_events)[-limit:]:
        data = event.get("data", {})
        msg = data.get("message", {})
        agent = data.get("agent") or msg.get("sender", {}).get("agent_id", "unknown")
        action = data.get("action") or msg.get("action", "unknown")
        direction = data.get("direction", "unknown")
        
        if agent == "unknown" or action == "unknown":
            continue
        
        if agent not in activity_data:
            activity_data[agent] = {
                "actions": {},
                "total": 0,
                "timeline": []
            }
        
        timestamp = event.get("timestamp", "")
        activity_data[agent]["total"] += 1
        activity_data[agent]["actions"][action] = activity_data[agent]["actions"].get(action, 0) + 1
        activity_data[agent]["timeline"].append({
            "timestamp": timestamp,
            "action": action,
            "direction": direction
        })
    
    # data.jsonl에서도 추출 (최근 데이터)
    try:
        with open(DATA, "r", encoding="utf-8") as f:
            lines = f.readlines()
            for line in lines[-limit*2:]:  # 더 많은 데이터 읽기
                try:
                    row = json.loads(line.strip())
                    msg = row.get("message", {})
                    direction = row.get("direction", "unknown")
                    
                    if direction == "out":  # 발신 메시지만
                        agent = msg.get("sender", {}).get("agent_id", "unknown")
                        action = msg.get("action", "unknown")
                        
                        if agent == "unknown" or action == "unknown":
                            continue
                        
                        if agent not in activity_data:
                            activity_data[agent] = {
                                "actions": {},
                                "total": 0,
                                "timeline": []
                            }
                        
                        timestamp = msg.get("timestamp") or row.get("timestamp", "")
                        activity_data[agent]["total"] += 1
                        activity_data[agent]["actions"][action] = activity_data[agent]["actions"].get(action, 0) + 1
                except:
                    continue
    except:
        pass
    
    return {
        "activity": activity_data,
        "total_events": len(recent_events)
    }

@app.get("/api/trust_timeline")
async def get_trust_timeline(limit: int = 200):
    """Get trust score timeline data for graph"""
    # data.jsonl에서 Trust Score 타임라인 추출 (주요 데이터 소스)
    timeline_data = {}
    
    try:
        with open(DATA, "r", encoding="utf-8") as f:
            lines = f.readlines()
            # 최근 데이터부터 읽기 (더 많은 데이터)
            for line in lines[-limit*2:]:
                try:
                    row = json.loads(line.strip())
                    
                    # Trust Score가 있는 경우만
                    trust_val = row.get("trust")
                    if trust_val is None:
                        continue
                    
                    # agent ID 추출
                    aid = row.get("agent", "unknown")
                    if aid == "unknown":
                        msg = row.get("message", {})
                        aid = msg.get("sender", {}).get("agent_id", "unknown")
                    
                    if aid == "unknown":
                        continue
                    
                    # timestamp 추출
                    timestamp = row.get("timestamp")
                    if not timestamp:
                        msg = row.get("message", {})
                        timestamp = msg.get("timestamp") or row.get("ts")
                    
                    if not timestamp:
                        continue
                    
                    if aid not in timeline_data:
                        timeline_data[aid] = []
                    
                    # 중복 제거를 위해 문자열로 변환하여 비교
                    entry = {"timestamp": timestamp, "trust": float(trust_val)}
                    entry_str = f"{timestamp}:{trust_val}"
                    
                    # 중복 체크
                    is_duplicate = False
                    for existing in timeline_data[aid]:
                        if existing.get("timestamp") == timestamp and abs(existing.get("trust", 0) - float(trust_val)) < 0.001:
                            is_duplicate = True
                            break
                    
                    if not is_duplicate:
                        timeline_data[aid].append(entry)
                except Exception as e:
                    continue
    except Exception as e:
        pass
    
    # recent_events에서도 추출 (보조 데이터)
    for event in list(recent_events)[-limit:]:
        data = event.get("data", {})
        trust_val = data.get("trust")
        
        if trust_val is None:
            continue
        
        msg = data.get("message", {})
        aid = msg.get("sender", {}).get("agent_id") or data.get("agent", "unknown")
        
        if aid == "unknown":
            continue
        
        timestamp = event.get("timestamp") or msg.get("timestamp") or data.get("timestamp")
        if not timestamp:
            continue
        
        if aid not in timeline_data:
            timeline_data[aid] = []
        
        # 중복 체크
        is_duplicate = False
        for existing in timeline_data[aid]:
            if existing.get("timestamp") == timestamp and abs(existing.get("trust", 0) - float(trust_val)) < 0.001:
                is_duplicate = True
                break
        
        if not is_duplicate:
            timeline_data[aid].append({
                "timestamp": timestamp,
                "trust": float(trust_val)
            })
    
    # 각 agent별로 시간순 정렬
    for aid in timeline_data:
        timeline_data[aid].sort(key=lambda x: x["timestamp"])
        # 최근 데이터만 유지 (너무 많으면 제한)
        if len(timeline_data[aid]) > limit:
            timeline_data[aid] = timeline_data[aid][-limit:]
    
    return {"timeline": timeline_data}

@app.get("/static/trust_timeline.png")
async def get_static_trust_graph():
    """정적 Trust Score 그래프 이미지 제공"""
    graph_path = Path("monitor/trust_timeline.png")
    if graph_path.exists():
        return FileResponse(graph_path, media_type="image/png")
    else:
        # 그래프가 없으면 생성 시도
        try:
            plot_trust()
            if graph_path.exists():
                return FileResponse(graph_path, media_type="image/png")
        except Exception as e:
            pass
        return HTMLResponse(content="<p>Graph not available</p>", status_code=404)

@app.get("/api/interactions")
async def get_interactions(limit: int = 200):
    """Agent 간 상호작용 데이터 제공 (네트워크 그래프용)"""
    interactions = {}  # {from_agent: {to_agent: count}}
    
    # recent_events에서 상호작용 추출
    for event in list(recent_events)[-limit:]:
        data = event.get("data", {})
        msg = data.get("message", {})
        from_agent = msg.get("sender", {}).get("agent_id")
        to_agent = msg.get("recipient", {}).get("agent_id")
        
        if from_agent and to_agent and from_agent != to_agent:
            if from_agent not in interactions:
                interactions[from_agent] = {}
            interactions[from_agent][to_agent] = interactions[from_agent].get(to_agent, 0) + 1
    
    # data.jsonl에서도 추출 (최근 데이터)
    try:
        with open(DATA, "r", encoding="utf-8") as f:
            lines = f.readlines()
            for line in lines[-limit*2:]:
                try:
                    row = json.loads(line.strip())
                    msg = row.get("message", {})
                    direction = row.get("direction", "unknown")
                    
                    if direction == "out":  # 발신 메시지만
                        from_agent = msg.get("sender", {}).get("agent_id")
                        to_agent = msg.get("recipient", {}).get("agent_id")
                        
                        if from_agent and to_agent and from_agent != to_agent:
                            if from_agent not in interactions:
                                interactions[from_agent] = {}
                            interactions[from_agent][to_agent] = interactions[from_agent].get(to_agent, 0) + 1
                except:
                    continue
    except:
        pass
    
    return {
        "interactions": interactions,
        "revoked": list(revoked)
    }

@app.post("/api/behavior_log")
async def receive_behavior_log(req: Request):
    """Agent로부터 행동 실행 로그 수신"""
    behavior_data = await req.json()
    log_behavior(behavior_data)
    return {"status": "logged"}

@app.get("/api/agent_timeline/{agent_id}")
async def get_agent_timeline(agent_id: str, limit: int = 500):
    """특정 agent의 trust timeline과 alert 정보"""
    timeline_data = []
    alerts_data = []
    
    # Trust timeline 데이터 수집
    try:
        with open(DATA, "r", encoding="utf-8") as f:
            lines = f.readlines()
            for line in lines[-limit*2:]:
                try:
                    row = json.loads(line.strip())
                    msg = row.get("message", {})
                    aid = msg.get("sender", {}).get("agent_id") or row.get("agent", "unknown")
                    
                    if aid != agent_id:
                        continue
                    
                    trust_val = row.get("trust")
                    timestamp = row.get("timestamp") or msg.get("timestamp")
                    
                    if trust_val is not None and timestamp:
                        timeline_data.append({
                            "timestamp": timestamp,
                            "trust": float(trust_val)
                        })
                except:
                    continue
    except:
        pass
    
    # Alert 데이터 수집
    try:
        with open(ALERTS, "r", encoding="utf-8") as f:
            lines = f.readlines()
            for line in lines[-limit:]:
                try:
                    alert = json.loads(line.strip())
                    if alert.get("sender") == agent_id:
                        alerts_data.append({
                            "timestamp": alert.get("ts"),
                            "reason": alert.get("reason", {}),
                            "type": alert.get("reason", {}).get("type", "unknown")
                        })
                except:
                    continue
    except:
        pass
    
    # 시간순 정렬
    timeline_data.sort(key=lambda x: x["timestamp"])
    alerts_data.sort(key=lambda x: x["timestamp"])
    
    return {
        "agent_id": agent_id,
        "timeline": timeline_data[-limit:],
        "alerts": alerts_data[-limit:]
    }

@app.get("/api/baseline/{agent_id}")
async def get_agent_baseline(agent_id: str):
    """Agent의 baseline 모델 정보"""
    from monitor.baseline_model import baseline_model
    baseline = baseline_model.get_baseline(agent_id)
    if not baseline:
        return {"agent_id": agent_id, "baseline": None, "message": "No baseline data yet"}
    return {"agent_id": agent_id, "baseline": baseline}

@app.get("/api/baselines")
async def get_all_baselines():
    """모든 agent의 baseline 정보"""
    from monitor.baseline_model import baseline_model
    return {"baselines": baseline_model.get_all_baselines()}

@app.get("/api/debug")
async def debug_info():
    """디버깅 정보 제공"""
    return {
        "recent_events_count": len(recent_events),
        "trust_scores": trust,
        "revoked_agents": list(revoked),
        "violations": violations,
        "data_file_exists": Path(DATA).exists(),
        "data_file_size": Path(DATA).stat().st_size if Path(DATA).exists() else 0,
        "behavior_log_exists": Path(BEHAVIOR_LOG).exists(),
        "behavior_log_size": Path(BEHAVIOR_LOG).stat().st_size if Path(BEHAVIOR_LOG).exists() else 0,
        "graph_file_exists": Path("monitor/trust_timeline.png").exists()
    }

# 🚀 서버 종료 시 자동 그래프 갱신은 lifespan 이벤트 핸들러에서 처리됩니다

if __name__ == "__main__":
    import uvicorn
    print("[+] Monitor server starting on http://127.0.0.1:8100")
    print("[+] Dashboard: http://127.0.0.1:8100/dashboard")
    uvicorn.run(app, host="127.0.0.1", port=8100, log_level="info")
