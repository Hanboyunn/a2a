import requests
from agents.base_agent import BaseAgentServer, monitor_log, get_agent_endpoint
from fastapi import HTTPException

AGENT_ID = "agent-orch-01"
PORT = 8000

async def handle_request_task(params: dict, full_msg: dict):
    """Handle request_task - forward to target agent"""
    task = params.get("task", "unknown")
    task_params = params.get("params", {})
    
    # Extract target agent from recipient
    recipient_id = full_msg.get("recipient", {}).get("agent_id")
    if not recipient_id:
        raise HTTPException(400, "no recipient agent_id")
    
    # Get target agent endpoint
    target_ep = get_agent_endpoint(recipient_id)
    if not target_ep:
        raise HTTPException(400, f"Agent {recipient_id} not found in registry")
    
    # Forward the task
    try:
        forward_msg = full_msg.copy()
        forward_msg["action"] = task
        forward_msg["params"] = task_params
        forward_msg["recipient"]["endpoint"] = target_ep
        
        r = requests.post(target_ep, json=forward_msg, timeout=5)
        monitor_log({
            "direction": "out",
            "agent": AGENT_ID,
            "to": recipient_id,
            "status": r.status_code
        })
        return {
            "status": "forwarded",
            "target": recipient_id,
            "task": task,
            "response": r.json() if r.status_code == 200 else {"text": r.text}
        }
    except Exception as e:
        monitor_log({
            "error": "route_failed",
            "agent": AGENT_ID,
            "to": recipient_id,
            "reason": str(e)
        })
        raise HTTPException(502, f"Route failed: {str(e)}")

def main():
    # Define action handlers
    action_handlers = {
        "request_task": handle_request_task,
    }
    
    # Create agent server
    agent = BaseAgentServer(
        agent_id=AGENT_ID,
        port=PORT,
        action_handlers=action_handlers
    )
    
    # Run the server
    agent.run()

if __name__ == "__main__":
    main()