# agents/user_agent.py
import time, uuid, json, asyncio
import threading
from agents.base_agent import BaseAgentServer, monitor_log

AGENT_ID = "agent-user-01"
PORT = 8001

def generate_task():
    """단일 행동 단위 정의 (랜덤하게 행동 선택 가능)"""
    import random
    actions = ["read_resource", "get_status", "ping"]
    return {
        "action": random.choice(actions),
        "params": {"resource": f"doc-{uuid.uuid4().hex[:6]}"},
    }

async def handle_read_resource(params: dict, full_msg: dict):
    """Handle read_resource action"""
    resource = params.get("resource", "unknown")
    return {
        "status": "ok",
        "action": "read_resource",
        "resource": resource,
        "data": f"Content of {resource}"
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

def periodic_task_runner(agent_server: BaseAgentServer):
    """Periodically send tasks to other agents"""
    import random
    time.sleep(5)  # Wait for other agents to start
    
    # Possible target agents
    target_agents = ["agent-tool-01", "agent-admin-01", "agent-orch-01"]
    
    print(f"[+] {AGENT_ID} periodic task runner started")
    while True:
        try:
            task = generate_task()
            # Randomly select a target agent
            target = random.choice(target_agents)
            
            try:
                response = agent_server.send_to_agent(
                    recipient_id=target,
                    action=task["action"],
                    params=task["params"]
                )
                print(f"[{AGENT_ID}] Sent {task['action']} to {target}: {response.status_code}")
            except ValueError as e:
                # Agent not registered yet, skip
                print(f"[{AGENT_ID}] Target agent not available: {target}")
            except Exception as e:
                print(f"[{AGENT_ID}] Error sending to {target}: {e}")
            
            time.sleep(5)  # ⏱️ 일정 주기마다 task 수행
        except KeyboardInterrupt:
            break
        except Exception as e:
            print(f"[{AGENT_ID}] Error in periodic task: {e}")
            time.sleep(5)

def main():
    # Define action handlers
    action_handlers = {
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
    
    # Start periodic task runner in background thread
    task_thread = threading.Thread(
        target=periodic_task_runner,
        args=(agent,),
        daemon=True
    )
    task_thread.start()
    
    # Run the server
    agent.run()

if __name__ == "__main__":
    main()
