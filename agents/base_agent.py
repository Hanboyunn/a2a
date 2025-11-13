import time, secrets, uuid, requests
from datetime import datetime, timezone
from common.crypto import sign_msg, params_hash
from fastapi import FastAPI, Request, HTTPException
from typing import Dict, Callable, Optional
import threading

MONITOR_INGEST = "http://127.0.0.1:8100/ingest"

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

def register_agent(agent_id: str, endpoint: str):
    """Register an agent's endpoint in the global registry"""
    AGENT_REGISTRY[agent_id] = endpoint

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
            
            # Check trust score with monitor before processing high-risk actions
            action = msg.get("action")
            sender_id = msg.get("sender", {}).get("agent_id", "unknown")
            
            HIGH_RISK_ACTIONS = {"delete_resource", "modify_config"}
            if action in HIGH_RISK_ACTIONS:
                # Monitor에 trust score 확인 요청
                try:
                    check_response = requests.post(
                        MONITOR_INGEST,
                        json={"message": msg},
                        timeout=2
                    )
                    if check_response.status_code == 200:
                        check_data = check_response.json()
                        allowed = check_data.get("allowed", False)
                        trust_score = check_data.get("trust", 0.0)
                        required_trust = check_data.get("required_trust", 0.8)
                        
                        if not allowed:
                            monitor_log({
                                "alert": "action_blocked_by_trust_score",
                                "agent": self.agent_id,
                                "sender": sender_id,
                                "action": action,
                                "trust_score": trust_score,
                                "required_trust": required_trust
                            })
                            raise HTTPException(
                                403,
                                f"Action blocked: Trust score {trust_score:.2f} < required {required_trust:.2f}"
                            )
                except requests.exceptions.RequestException:
                    # Monitor가 응답하지 않으면 경고만 하고 계속 진행
                    monitor_log({
                        "warning": "monitor_unavailable_for_trust_check",
                        "agent": self.agent_id,
                        "action": action
                    })
            
            # Handle the action
            params = msg.get("params", {})
            
            result = await self._handle_action(action, params, msg)
            
            monitor_log({
                "direction": "out",
                "agent": self.agent_id,
                "action": action,
                "result": result
            })
            
            return result
        
        @self.app.get("/status")
        async def status():
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
