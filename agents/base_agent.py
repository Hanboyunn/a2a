import time, secrets, uuid, requests
from datetime import datetime, timezone
from common.crypto import sign_msg, params_hash
from fastapi import FastAPI, Request, HTTPException
from typing import Dict, Callable, Optional
import threading

MONITOR_INGEST = "http://127.0.0.1:8100/ingest"
MONITOR_EVAL = "http://127.0.0.1:8100/evaluate"

# Agent registry: agent_id -> endpoint mapping
# 기본 agent 엔드포인트 (하드코딩된 레지스트리)
AGENT_REGISTRY: Dict[str, str] = {
    "agent-orch-01": "http://127.0.0.1:8000/a2a/invoke",
    "agent-user-01": "http://127.0.0.1:8001/a2a/invoke",
    "agent-tool-01": "http://127.0.0.1:8002/a2a/invoke",
    "agent-admin-01": "http://127.0.0.1:8003/a2a/invoke",
}

def utcnow():
    return datetime.now(timezone.utc).replace(tzinfo=None)

def iso_utc():
    return utcnow().isoformat(timespec="seconds") + "Z"

def monitor_log(payload: dict):
    try:
        requests.post(MONITOR_INGEST, json=payload, timeout=3)
    except Exception:
        pass

def build_message(sender_id: str, recipient_id: str, recipient_ep: str,
                  action: str, params: dict):
    msg = {
        "message_id": f"msg-{secrets.token_hex(6)}",
        "correlation_id": f"trace-{uuid.uuid4().hex[:12]}",
        "timestamp": iso_utc(),
        "nonce": secrets.token_hex(4),
        "sender": {"agent_id": sender_id},
        "recipient": {"agent_id": recipient_id, "endpoint": recipient_ep},
        "action": action,
        "params": params,
    }
    msg["params_hash"] = params_hash(params)
    msg["signature"] = sign_msg(msg, fields=[
        "message_id","correlation_id","timestamp","nonce",
        "sender.agent_id","recipient.agent_id","action","params_hash"
    ])
    msg["signature_fields"] = [
        "message_id","correlation_id","timestamp","nonce",
        "sender.agent_id","recipient.agent_id","action","params_hash"
    ]
    return msg

def send_and_log(msg: dict):
    monitor_log({"direction":"out","message":msg})
    ep = msg["recipient"]["endpoint"]
    r = requests.post(ep, json=msg, timeout=5)
    monitor_log({"direction":"in","status":r.status_code,"body":safe_json(r)})
    return r

def safe_json(r):
    try: return r.json()
    except Exception: return {"text": r.text[:400]}

AGENT_MANAGER_URL = "http://127.0.0.1:8200"

def register_agent(agent_id: str, endpoint: str):
    """Register an agent's endpoint in the global registry and Agent Manager"""
    AGENT_REGISTRY[agent_id] = endpoint
    
    # Also register with Agent Management Server
    try:
        requests.post(
            f"{AGENT_MANAGER_URL}/register",
            json={
                "agent_id": agent_id,
                "endpoint": endpoint,
                "agent_type": agent_id.split("-")[1] if "-" in agent_id else "unknown",
                "capabilities": [],
                "metadata": {}
            },
            timeout=2
        )
    except:
        pass  # Agent Manager가 없어도 계속 진행

def get_agent_endpoint(agent_id: str) -> Optional[str]:
    """Get an agent's endpoint from the registry"""
    return AGENT_REGISTRY.get(agent_id)

class BaseAgentServer:
    """Base class for all agent servers with A2A communication capabilities"""
    
    def __init__(self, agent_id: str, port: int, action_handlers: Optional[Dict[str, Callable]] = None):
        self.agent_id = agent_id
        self.port = port
        self.endpoint = f"http://127.0.0.1:{port}/a2a/invoke"
        self.app = FastAPI()
        self.action_handlers = action_handlers or {}
        
        # Register this agent
        register_agent(agent_id, self.endpoint)
        
        # Setup routes
        self._setup_routes()
    
    def _setup_routes(self):
        """Setup FastAPI routes for A2A communication"""
        
        @self.app.post("/a2a/invoke")
        async def invoke(req: Request):
            msg = await req.json()
            # 수신 agent도 Trust Score 계산을 위해 Monitor에 전송
            # sender의 Trust Score를 계산하기 위해 message를 Monitor에 전송
            try:
                requests.post(
                    MONITOR_INGEST,
                    json={"message": msg},
                    timeout=1
                )
            except:
                pass  # Monitor가 응답하지 않아도 계속 진행
            
            monitor_log({
                "direction": "in",
                "agent": self.agent_id,
                "message": msg
            })
            
            # Verify signature
            from common.crypto import verify_msg
            if not verify_msg(msg):
                monitor_log({
                    "alert": "invalid_signature",
                    "agent": self.agent_id,
                    "msg_id": msg.get("message_id")
                })
                raise HTTPException(400, "invalid signature")
            
            # Check if message is for this agent
            recipient_id = msg.get("recipient", {}).get("agent_id")
            if recipient_id and recipient_id != self.agent_id:
                monitor_log({
                    "warning": "message_not_for_this_agent",
                    "agent": self.agent_id,
                    "intended_recipient": recipient_id
                })
            
            # Monitor 정책 평가 (모든 action에 적용)
            action = msg.get("action")
            sender_id = msg.get("sender", {}).get("agent_id", "unknown")
            params = msg.get("params", {})
            
            try:
                eval_response = requests.post(
                    MONITOR_EVAL,
                    json={"message": msg},
                    timeout=2
                )
                if eval_response.status_code == 200:
                    eval_data = eval_response.json()
                    allowed = eval_data.get("allowed", False)
                    trust_score = eval_data.get("trust", 0.0)
                    required_trust = eval_data.get("required_trust", 0.0)
                    revoked_state = eval_data.get("revoked", False)

                    if not allowed or revoked_state:
                        monitor_log({
                            "alert": "action_blocked_by_monitor",
                            "agent": self.agent_id,
                            "sender": sender_id,
                            "action": action,
                            "trust_score": trust_score,
                            "required_trust": required_trust,
                            "revoked": revoked_state
                        })
                        reason = "Agent revoked" if revoked_state else f"Trust score {trust_score:.2f} < required {required_trust:.2f}"
                        raise HTTPException(403, f"Action blocked by monitor: {reason}")
                else:
                    monitor_log({
                        "warning": "monitor_eval_failed",
                        "agent": self.agent_id,
                        "action": action,
                        "status_code": eval_response.status_code
                    })
            except requests.exceptions.RequestException as exc:
                monitor_log({
                    "warning": "monitor_unavailable_for_trust_check",
                    "agent": self.agent_id,
                    "action": action,
                    "error": str(exc)
                })

            # Handle the action
            result = await self._handle_action(action, params, msg)

            monitor_log({
                "direction": "out",
                "agent": self.agent_id,
                "action": action,
                "result": result
            })
            
            # 행동 기반 탐지용 상세 로그 (Monitor에 전송)
            try:
                behavior_log = {
                    "event_type": "action_executed",
                    "executor_agent": self.agent_id,
                    "sender_agent": sender_id,
                    "action": action,
                    "params": params,
                    "result": result,
                    "message_id": msg.get("message_id"),
                    "correlation_id": msg.get("correlation_id"),
                    "timestamp": msg.get("timestamp"),
                    "direction": "in",  # 수신 agent의 관점
                    "execution_status": "success" if isinstance(result, dict) and result.get("status") in ["ok", "received"] else "error",
                    "execution_time_ms": 0  # 필요시 측정 가능
                }
                requests.post(
                    "http://127.0.0.1:8100/api/behavior_log",
                    json=behavior_log,
                    timeout=0.5
                )
            except:
                pass  # Monitor가 응답하지 않아도 계속 진행

            return result
        
        @self.app.get("/status")
        async def status():
            # Update heartbeat in Agent Manager
            try:
                requests.post(
                    f"{AGENT_MANAGER_URL}/heartbeat/{self.agent_id}",
                    timeout=1
                )
            except:
                pass  # Agent Manager가 없어도 계속 진행
            
            return {
                "agent_id": self.agent_id,
                "status": "running",
                "endpoint": self.endpoint,
                "registered_actions": list(self.action_handlers.keys())
            }
        
        @self.app.get("/registry")
        async def registry():
            """Get the current agent registry"""
            return {"registry": AGENT_REGISTRY}
    
    async def _handle_action(self, action: str, params: dict, full_msg: dict):
        """Handle an incoming action"""
        if action in self.action_handlers:
            handler = self.action_handlers[action]
            if callable(handler):
                try:
                    import asyncio
                    import inspect
                    # Check if handler is async
                    if inspect.iscoroutinefunction(handler):
                        return await handler(params, full_msg)
                    else:
                        # Sync handler - run in thread pool
                        loop = asyncio.get_event_loop()
                        return await loop.run_in_executor(None, lambda: handler(params, full_msg))
                except Exception as e:
                    monitor_log({
                        "error": "action_handler_failed",
                        "agent": self.agent_id,
                        "action": action,
                        "error": str(e)
                    })
                    raise HTTPException(500, f"Action handler failed: {str(e)}")
        
        # Default handler
        return {
            "status": "received",
            "agent": self.agent_id,
            "action": action,
            "params": params
        }
    
    def send_to_agent(self, recipient_id: str, action: str, params: dict):
        """Send a message to another agent"""
        recipient_ep = get_agent_endpoint(recipient_id)
        if not recipient_ep:
            raise ValueError(f"Agent {recipient_id} not found in registry")
        
        msg = build_message(
            self.agent_id,
            recipient_id,
            recipient_ep,
            action,
            params
        )
        return send_and_log(msg)
    
    def run(self, host: str = "127.0.0.1"):
        """Run the agent server"""
        import uvicorn
        print(f"[+] {self.agent_id} server starting on {self.endpoint}")
        uvicorn.run(self.app, host=host, port=self.port, log_level="info")
