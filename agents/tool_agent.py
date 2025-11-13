import asyncio
from agents.base_agent import BaseAgentServer, monitor_log

AGENT_ID = "agent-tool-01"
PORT = 8002

async def handle_delete_resource(params: dict, full_msg: dict):
    """Handle delete_resource action"""
    resource_id = params.get("resource_id", "unknown")
    monitor_log({
        "alert": "high_risk_action_executed",
        "agent": AGENT_ID,
        "action": "delete_resource",
        "resource_id": resource_id
    })
    await asyncio.sleep(0.2)
    return {
        "status": "ok",
        "action": "delete_resource",
        "resource_id": resource_id,
        "result": "Resource deleted"
    }

async def handle_read_resource(params: dict, full_msg: dict):
    """Handle read_resource action"""
    resource = params.get("resource", "unknown")
    await asyncio.sleep(0.1)
    return {
        "status": "ok",
        "action": "read_resource",
        "resource": resource,
        "result": f"Read data from {resource}"
    }

async def handle_get_status(params: dict, full_msg: dict):
    """Handle get_status action"""
    return {
        "status": "ok",
        "agent": AGENT_ID,
        "uptime": "running"
    }

async def handle_ping(params: dict, full_msg: dict):
    """Handle ping action"""
    return {
        "status": "pong",
        "agent": AGENT_ID
    }

def main():
    # Define action handlers
    action_handlers = {
        "delete_resource": handle_delete_resource,
        "read_resource": handle_read_resource,
        "get_status": handle_get_status,
        "ping": handle_ping,
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