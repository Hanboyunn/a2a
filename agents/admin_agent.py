import time, threading
from agents.base_agent import BaseAgentServer, monitor_log

ADMIN_ID = "agent-admin-01"
PORT = 8003

async def handle_delete_resource(params: dict, full_msg: dict):
    """Handle delete_resource action (high-risk)"""
    resource_id = params.get("resource_id", "unknown")
    monitor_log({
        "alert": "high_risk_action",
        "agent": ADMIN_ID,
        "action": "delete_resource",
        "resource_id": resource_id
    })
    return {
        "status": "ok",
        "action": "delete_resource",
        "resource_id": resource_id,
        "message": "Resource deletion requested"
    }

async def handle_modify_config(params: dict, full_msg: dict):
    """Handle modify_config action (high-risk)"""
    config_key = params.get("config_key", "unknown")
    monitor_log({
        "alert": "high_risk_action",
        "agent": ADMIN_ID,
        "action": "modify_config",
        "config_key": config_key
    })
    return {
        "status": "ok",
        "action": "modify_config",
        "config_key": config_key,
        "message": "Config modification requested"
    }

async def handle_request_task(params: dict, full_msg: dict):
    """Handle request_task action"""
    task = params.get("task", "unknown")
    task_params = params.get("params", {})
    return {
        "status": "received",
        "task": task,
        "params": task_params
    }

def periodic_admin_tasks(agent_server: BaseAgentServer):
    """Periodically send admin tasks to other agents"""
    time.sleep(8)  # Wait for other agents to start
    
    print(f"[+] {ADMIN_ID} periodic admin task runner started")
    while True:
        try:
            # Send high-risk request to tool agent
            try:
                response = agent_server.send_to_agent(
                    recipient_id="agent-tool-01",
                    action="delete_resource",
                    params={"resource_id": f"critical-db-{int(time.time())}"}
                )
                print(f"[{ADMIN_ID}] Sent delete_resource to tool agent: {response.status_code}")
            except ValueError as e:
                print(f"[{ADMIN_ID}] Tool agent not available yet")
            except Exception as e:
                print(f"[{ADMIN_ID}] Error: {e}")
            
            time.sleep(10)  # Send admin tasks every 10 seconds
        except KeyboardInterrupt:
            break
        except Exception as e:
            print(f"[{ADMIN_ID}] Error in periodic task: {e}")
            time.sleep(10)

def main():
    # Define action handlers
    action_handlers = {
        "delete_resource": handle_delete_resource,
        "modify_config": handle_modify_config,
        "request_task": handle_request_task,
    }
    
    # Create agent server
    agent = BaseAgentServer(
        agent_id=ADMIN_ID,
        port=PORT,
        action_handlers=action_handlers
    )
    
    # Start periodic admin task runner in background thread
    task_thread = threading.Thread(
        target=periodic_admin_tasks,
        args=(agent,),
        daemon=True
    )
    task_thread.start()
    
    # Run the server
    agent.run()

if __name__ == "__main__":
    main()