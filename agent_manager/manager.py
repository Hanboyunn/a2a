"""Agent Management Server - Centralized agent registry and management"""
import time
import threading
import requests
from datetime import datetime, timedelta
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from typing import Dict, List, Optional
import uvicorn

from agent_manager.database import (
    init_database, register_agent, unregister_agent, update_agent_heartbeat,
    get_agent, list_agents, log_message, record_health_check,
    get_config, set_config
)

app = FastAPI(title="Agent Management Server")

# Health check interval (seconds)
HEALTH_CHECK_INTERVAL = 30
HEARTBEAT_TIMEOUT = 60  # Agent is considered dead if no heartbeat for 60 seconds

def health_check_worker():
    """Background worker to check agent health"""
    while True:
        try:
            agents = list_agents(status="active")
            for agent_data in agents:
                agent_id = agent_data["agent_id"]
                endpoint = agent_data["endpoint"]
                
                # Check if agent is responding
                health_endpoint = endpoint.replace("/a2a/invoke", "/status")
                start_time = time.time()
                try:
                    response = requests.get(health_endpoint, timeout=5)
                    response_time = int((time.time() - start_time) * 1000)
                    
                    if response.status_code == 200:
                        record_health_check(agent_id, "healthy", response_time)
                        update_agent_heartbeat(agent_id)
                    else:
                        record_health_check(agent_id, "unhealthy", response_time, 
                                          f"HTTP {response.status_code}")
                except requests.exceptions.RequestException as e:
                    response_time = int((time.time() - start_time) * 1000)
                    record_health_check(agent_id, "unhealthy", response_time, str(e))
                    
                    # Mark as inactive if consistently failing
                    last_heartbeat = agent_data.get("last_heartbeat")
                    if last_heartbeat:
                        last_hb_time = datetime.fromisoformat(last_heartbeat.replace("Z", "+00:00"))
                        if datetime.now(last_hb_time.tzinfo) - last_hb_time > timedelta(seconds=HEARTBEAT_TIMEOUT):
                            unregister_agent(agent_id)
                            
        except Exception as e:
            print(f"[Health Check] Error: {e}")
        
        time.sleep(HEALTH_CHECK_INTERVAL)

@app.on_event("startup")
async def startup():
    """Initialize database and start health check worker"""
    init_database()
    print("[+] Agent Management Server initialized")
    
    # Start health check worker
    health_thread = threading.Thread(target=health_check_worker, daemon=True)
    health_thread.start()
    print("[+] Health check worker started")

@app.post("/register")
async def register(req: Request):
    """Register a new agent"""
    data = await req.json()
    agent_id = data.get("agent_id")
    endpoint = data.get("endpoint")
    agent_type = data.get("agent_type")
    capabilities = data.get("capabilities", [])
    metadata = data.get("metadata", {})
    
    if not agent_id or not endpoint:
        raise HTTPException(400, "agent_id and endpoint are required")
    
    result = register_agent(agent_id, endpoint, agent_type, capabilities, metadata)
    return {"status": "registered", **result}

@app.post("/unregister/{agent_id}")
async def unregister(agent_id: str):
    """Unregister an agent"""
    success = unregister_agent(agent_id)
    if not success:
        raise HTTPException(404, f"Agent {agent_id} not found")
    return {"status": "unregistered", "agent_id": agent_id}

@app.post("/heartbeat/{agent_id}")
async def heartbeat(agent_id: str):
    """Update agent heartbeat"""
    success = update_agent_heartbeat(agent_id)
    if not success:
        raise HTTPException(404, f"Agent {agent_id} not found")
    return {"status": "ok", "agent_id": agent_id, "timestamp": datetime.utcnow().isoformat() + "Z"}

@app.get("/agents")
async def get_agents(status: Optional[str] = None):
    """List all agents"""
    agents = list_agents(status=status)
    return {"agents": agents, "count": len(agents)}

@app.get("/agents/{agent_id}")
async def get_agent_info(agent_id: str):
    """Get agent information"""
    agent = get_agent(agent_id)
    if not agent:
        raise HTTPException(404, f"Agent {agent_id} not found")
    return agent

@app.get("/agents/{agent_id}/health")
async def get_agent_health(agent_id: str, limit: int = 10):
    """Get agent health check history"""
    from agent_manager.database import get_db_connection
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT * FROM agent_health 
            WHERE agent_id = ? 
            ORDER BY check_time DESC 
            LIMIT ?
        """, (agent_id, limit))
        rows = cursor.fetchall()
        return {"health_checks": [dict(row) for row in rows]}

@app.get("/registry")
async def get_registry():
    """Get agent registry (for compatibility with existing system)"""
    agents = list_agents(status="active")
    registry = {agent["agent_id"]: agent["endpoint"] for agent in agents}
    return {"registry": registry}

@app.post("/config/{config_key}")
async def set_config_value(config_key: str, req: Request):
    """Set system configuration"""
    data = await req.json()
    config_value = data.get("value")
    updated_by = data.get("updated_by")
    
    if config_value is None:
        raise HTTPException(400, "value is required")
    
    set_config(config_key, str(config_value), updated_by)
    return {"status": "ok", "config_key": config_key, "value": config_value}

@app.get("/config/{config_key}")
async def get_config_value(config_key: str):
    """Get system configuration"""
    value = get_config(config_key)
    if value is None:
        raise HTTPException(404, f"Config {config_key} not found")
    return {"config_key": config_key, "value": value}

@app.get("/stats")
async def get_stats():
    """Get system statistics"""
    agents = list_agents()
    active_count = len([a for a in agents if a["status"] == "active"])
    
    from agent_manager.database import get_db_connection
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM agent_messages")
        message_count = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM agent_health WHERE status = 'healthy'")
        healthy_count = cursor.fetchone()[0]
    
    return {
        "total_agents": len(agents),
        "active_agents": active_count,
        "total_messages": message_count,
        "healthy_agents": healthy_count
    }

if __name__ == "__main__":
    print("[+] Agent Management Server starting on http://127.0.0.1:8200")
    print("[+] API Docs: http://127.0.0.1:8200/docs")
    uvicorn.run(app, host="127.0.0.1", port=8200, log_level="info")

