import requests
from agents.base_agent import BaseAgentServer, monitor_log, get_agent_endpoint
from fastapi import HTTPException

AGENT_ID = "agent-orch-01"
PORT = 8000

# 작업 라우팅 맵: task -> target_agent (실제 작업 기반)
TASK_ROUTING = {
    # 리포트 및 분석 작업
    "generate_monthly_sales_report": "agent-tool-01",
    "generate_weekly_summary": "agent-tool-01",
    "analyze_customer_data": "agent-tool-01",
    "analyze_report_data": "agent-tool-01",
    "analyze_data": "agent-tool-01",
    "generate_report": "agent-tool-01",
    
    # 문서 및 데이터 작업
    "search_documents": "agent-tool-01",
    "query_database": "agent-tool-01",
    "read_resource": "agent-tool-01",
    "write_resource": "agent-tool-01",
    "delete_resource": "agent-tool-01",
    
    # 시스템 관리 작업
    "create_database_backup": "agent-tool-01",
    "archive_old_logs": "agent-tool-01",
    "update_system_config": "agent-tool-01",
    "cleanup_temp_files": "agent-tool-01",
    "rotate_application_logs": "agent-tool-01",
    "check_disk_space": "agent-tool-01",
    "update_user_permissions": "agent-tool-01",
    "cleanup_logs": "agent-tool-01",
    "modify_config": "agent-tool-01",
    
    # 모니터링 작업
    "check_system_health": "agent-tool-01",
    "get_service_status": "agent-tool-01",
    "get_status": "agent-tool-01",
    "ping": "agent-tool-01",
}

async def handle_request_task(params: dict, full_msg: dict):
    """Handle request_task - 작업을 적절한 agent로 라우팅"""
    task = params.get("task", "unknown")
    task_params = params.get("params", {})
    sender_id = full_msg.get("sender", {}).get("agent_id", "unknown")
    
    # 작업 타입에 따라 적절한 agent로 라우팅
    target_agent = TASK_ROUTING.get(task, "agent-tool-01")  # 기본값: tool agent
    
    # Get target agent endpoint
    target_ep = get_agent_endpoint(target_agent)
    if not target_ep:
        raise HTTPException(400, f"Agent {target_agent} not found in registry")
    
    monitor_log({
        "info": "task_routed",
        "agent": AGENT_ID,
        "task": task,
        "from": sender_id,
        "to": target_agent
    })
    
    # Forward the task to target agent
    try:
        forward_msg = full_msg.copy()
        forward_msg["action"] = task
        forward_msg["params"] = task_params
        forward_msg["recipient"] = {
            "agent_id": target_agent,
            "endpoint": target_ep
        }
        
        r = requests.post(target_ep, json=forward_msg, timeout=5)
        monitor_log({
            "direction": "out",
            "agent": AGENT_ID,
            "to": target_agent,
            "task": task,
            "status": r.status_code
        })
        return {
            "status": "forwarded",
            "target": target_agent,
            "task": task,
            "response": r.json() if r.status_code == 200 else {"text": r.text[:200]}
        }
    except Exception as e:
        monitor_log({
            "error": "route_failed",
            "agent": AGENT_ID,
            "to": target_agent,
            "task": task,
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