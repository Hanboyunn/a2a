import time, requests, json
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from datetime import datetime
from monitor.plot_utils import plot_trust  # 👈 종료 시 자동 그래프 생성
from collections import deque
from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
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

trust = {}
revoked = set()
recent = {}

# 실시간 모니터링을 위한 메모리 버퍼 (최근 100개 이벤트)
recent_events = deque(maxlen=100)

LOW_RISK = {"get_status", "ping"}
HIGH_RISK = {"delete_resource", "modify_config"}

def now():
    return datetime.utcnow().isoformat() + "Z"

def log(path, obj):
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(obj) + "\n")

@app.post("/ingest")
async def ingest(req: Request):
    p = await req.json()
    log(DATA, p)
    
    # 실시간 이벤트에 추가
    event = {
        "timestamp": now(),
        "type": "ingest",
        "data": p
    }
    recent_events.append(event)

    msg = p.get("message")
    if not msg:
        return {"status": "logged"}

    aid = msg.get("sender", {}).get("agent_id") or p.get("agent", "unknown")
    act = msg.get("action", "unknown")
    sig = bool(msg.get("signature"))
    rh = msg.get("params_hash")
    n = msg.get("nonce")
    mid = msg.get("message_id")

    rp = is_replay(aid, rh, n, mid, now(), act)
    t = update_trust(aid, sig, rp, aid in revoked, act)

    req_t = 0.8 if act in HIGH_RISK else 0.3
    allowed = (t >= req_t)

    if not allowed:
        alert_data = {
            "ts": now(),
            "sender": aid,
            "reason": {
                "sig_valid": sig,
                "replay": rp,
                "revoked": aid in revoked,
                "trust": t,
                "required_trust": req_t
            }
        }
        log(ALERTS, alert_data)
        recent_events.append({
            "timestamp": now(),
            "type": "alert",
            "data": alert_data
        })

    return {
        "status": "ingested",
        "sig_valid": sig,
        "replay": rp,
        "revoked": aid in revoked,
        "trust": t,
        "required_trust": req_t,
        "allowed": allowed
    }

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
    t = trust.get(a, 0.35)
    if rev:
        return 0.0
    if sig:
        t = min(t + 0.05, 1.0)
    if rp and act not in LOW_RISK:
        t = max(t - 0.15, 0)
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
        <table class="trust-table">
            <tr>
                <th>Agent ID</th>
                <th>Trust Score</th>
                <th>Status</th>
            </tr>
    """
    
    for agent_id, trust_score in sorted(trust.items()):
        status = "REVOKED" if agent_id in revoked else "ACTIVE"
        trust_class = "trust-low" if trust_score < 0.5 else "trust-medium" if trust_score < 0.8 else "trust-high"
        html += f"""
            <tr>
                <td>{agent_id}</td>
                <td class="{trust_class}">{trust_score:.2f}</td>
                <td>{status}</td>
            </tr>
        """
    
    html += """
        </table>
        
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

# 🚀 서버 종료 시 자동 그래프 갱신은 lifespan 이벤트 핸들러에서 처리됩니다

if __name__ == "__main__":
    import uvicorn
    print("[+] Monitor server starting on http://127.0.0.1:8100")
    print("[+] Dashboard: http://127.0.0.1:8100/dashboard")
    uvicorn.run(app, host="127.0.0.1", port=8100, log_level="info")
