import time, threading, uuid
import random
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
    """다양한 시스템 관리 작업 수행"""
    import random
    time.sleep(8)  # Wait for other agents to start
    
    print(f"[+] {ADMIN_ID} periodic admin task runner started")
    task_count = 0
    
    # 실제 시스템 관리 작업 시나리오
    admin_scenarios = [
        {
            "action": "request_task",
            "params": {
                "task": "create_database_backup",
                "params": {
                    "database": "production_db",
                    "backup_type": "full",
                    "retention_days": 30
                }
            },
            "target": "agent-orch-01",
            "description": "프로덕션 DB 백업 생성"
        },
        {
            "action": "request_task",
            "params": {
                "task": "archive_old_logs",
                "params": {
                    "log_directory": "/var/log/app",
                    "days_to_keep": 90,
                    "archive_format": "tar.gz"
                }
            },
            "target": "agent-orch-01",
            "description": "오래된 로그 파일 아카이빙"
        },
        {
            "action": "request_task",
            "params": {
                "task": "update_system_config",
                "params": {
                    "config_key": "api_rate_limit",
                    "new_value": "1000",
                    "restart_required": False
                }
            },
            "target": "agent-orch-01",
            "description": "API 속도 제한 설정 업데이트"
        },
        {
            "action": "request_task",
            "params": {
                "task": "cleanup_temp_files",
                "params": {
                    "directories": ["/tmp/app", "/var/cache"],
                    "max_age_hours": 24
                }
            },
            "target": "agent-orch-01",
            "description": "임시 파일 정리"
        },
        {
            "action": "request_task",
            "params": {
                "task": "rotate_application_logs",
                "params": {
                    "log_file": "/var/log/app/application.log",
                    "max_size_mb": 100,
                    "keep_rotated": 5
                }
            },
            "target": "agent-orch-01",
            "description": "애플리케이션 로그 로테이션"
        },
        {
            "action": "request_task",
            "params": {
                "task": "check_disk_space",
                "params": {
                    "threshold_percent": 80,
                    "paths": ["/", "/var", "/home"]
                }
            },
            "target": "agent-orch-01",
            "description": "디스크 공간 확인"
        },
        {
            "action": "request_task",
            "params": {
                "task": "update_user_permissions",
                "params": {
                    "user_id": f"user-{uuid.uuid4().hex[:8]}",
                    "new_role": random.choice(["admin", "editor", "viewer"]),
                    "resource": "analytics_dashboard"
                }
            },
            "target": "agent-orch-01",
            "description": "사용자 권한 업데이트"
        }
    ]
    
    while True:
        try:
            task_count += 1
            scenario = random.choice(admin_scenarios)
            target = scenario["target"]
            
            try:
                response = agent_server.send_to_agent(
                    recipient_id=target,
                    action=scenario["action"],
                    params=scenario["params"]
                )
                print(f"[{ADMIN_ID}] [{task_count}] {scenario['description']} -> {target}: {response.status_code}")
            except ValueError as e:
                print(f"[{ADMIN_ID}] Target agent not available: {target}")
            except Exception as e:
                print(f"[{ADMIN_ID}] Error: {e}")
            
            # 관리 작업은 8-15초 간격으로 수행
            time.sleep(random.uniform(8, 15))
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