# agents/user_agent.py
import time, uuid, json, asyncio
import threading
from agents.base_agent import BaseAgentServer, monitor_log

AGENT_ID = "agent-user-01"
PORT = 8001

def generate_task():
    """실제 사용자 요청 시나리오 생성 - 현실적인 비즈니스 작업"""
    import random
    from datetime import datetime
    
    # 실제 사용자 시나리오: 비즈니스 요청, 데이터 분석, 리포트 생성 등
    scenarios = [
        {
            "action": "request_task",
            "params": {
                "task": "generate_monthly_sales_report",
                "params": {
                    "period": datetime.now().strftime("%Y-%m"),
                    "format": "pdf",
                    "include_charts": True
                }
            },
            "target": "agent-orch-01",
            "description": "월간 매출 리포트 생성 요청"
        },
        {
            "action": "request_task",
            "params": {
                "task": "analyze_customer_data",
                "params": {
                    "dataset": "customer_transactions",
                    "analysis_type": "trend_analysis",
                    "time_range": "last_30_days"
                }
            },
            "target": "agent-orch-01",
            "description": "고객 데이터 트렌드 분석 요청"
        },
        {
            "action": "request_task",
            "params": {
                "task": "search_documents",
                "params": {
                    "query": random.choice(["Q4 strategy", "budget plan", "meeting notes"]),
                    "document_type": random.choice(["pdf", "docx", "txt"]),
                    "max_results": 10
                }
            },
            "target": "agent-orch-01",
            "description": "문서 검색 요청"
        },
        {
            "action": "request_task",
            "params": {
                "task": "generate_weekly_summary",
                "params": {
                    "week": datetime.now().strftime("%Y-W%W"),
                    "sections": ["sales", "marketing", "operations"]
                }
            },
            "target": "agent-orch-01",
            "description": "주간 요약 리포트 생성"
        },
        {
            "action": "request_task",
            "params": {
                "task": "query_database",
                "params": {
                    "query": "SELECT COUNT(*) FROM users WHERE created_at > DATE_SUB(NOW(), INTERVAL 7 DAY)",
                    "database": "analytics_db"
                }
            },
            "target": "agent-orch-01",
            "description": "데이터베이스 쿼리 요청"
        },
        {
            "action": "check_system_health",
            "params": {},
            "target": "agent-tool-01",
            "description": "시스템 상태 확인"
        },
        {
            "action": "get_service_status",
            "params": {
                "service": random.choice(["api", "database", "cache", "queue"])
            },
            "target": "agent-tool-01",
            "description": "서비스 상태 확인"
        }
    ]
    
    return random.choice(scenarios)

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
    """다양한 실제 작업 패턴으로 주기적으로 작업 요청"""
    import random
    time.sleep(5)  # Wait for other agents to start
    
    print(f"[+] {AGENT_ID} periodic task runner started")
    task_count = 0
    
    while True:
        try:
            task = generate_task()
            target = task.get("target", "agent-orch-01")
            
            try:
                response = agent_server.send_to_agent(
                    recipient_id=target,
                    action=task["action"],
                    params=task["params"]
                )
                task_count += 1
                description = task.get("description", task["action"])
                print(f"[{AGENT_ID}] [{task_count}] {description} -> {target}: {response.status_code}")
                
                # 가끔 연속 작업 (실제 워크플로우 시뮬레이션)
                if task_count % 7 == 0:
                    # 복합 워크플로우: 리포트 생성 후 분석 요청
                    try:
                        agent_server.send_to_agent(
                            recipient_id="agent-orch-01",
                            action="request_task",
                            params={
                                "task": "analyze_report_data",
                                "params": {
                                    "report_id": f"report-{uuid.uuid4().hex[:8]}",
                                    "analysis_type": "summary_statistics"
                                }
                            }
                        )
                        print(f"[{AGENT_ID}] [workflow] 연속 작업: 리포트 데이터 분석 요청")
                    except:
                        pass
                
            except ValueError as e:
                print(f"[{AGENT_ID}] Target agent not available: {target}")
            except Exception as e:
                print(f"[{AGENT_ID}] Error sending to {target}: {e}")
            
            # 작업 간격을 다양하게 (3-8초)
            time.sleep(random.uniform(3, 8))
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
