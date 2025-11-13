import asyncio
import os
import json
import uuid
from datetime import datetime
from pathlib import Path
from agents.base_agent import BaseAgentServer, monitor_log

AGENT_ID = "agent-tool-01"
PORT = 8002

# 리소스 저장소 경로
RESOURCES_DIR = Path("resources")
RESOURCE_ACCESS_LOG = Path("monitor/resource_access.jsonl")

# 리소스 디렉토리 초기화
RESOURCES_DIR.mkdir(exist_ok=True)

def log_resource_access(action: str, resource_id: str, agent_id: str, success: bool, details: dict = None):
    """리소스 접근 로그 기록"""
    log_entry = {
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "action": action,
        "resource_id": resource_id,
        "agent_id": agent_id,
        "success": success,
        "details": details or {}
    }
    try:
        with open(RESOURCE_ACCESS_LOG, "a", encoding="utf-8") as f:
            f.write(json.dumps(log_entry) + "\n")
    except Exception as e:
        print(f"[!] Failed to log resource access: {e}")

def get_resource_path(resource_id: str) -> Path:
    """리소스 파일 경로 반환"""
    # 보안: 경로 순회 공격 방지
    safe_id = os.path.basename(resource_id)
    return RESOURCES_DIR / f"{safe_id}.txt"

def ensure_resource_exists(resource_id: str) -> bool:
    """리소스가 존재하는지 확인"""
    resource_path = get_resource_path(resource_id)
    return resource_path.exists()

async def handle_delete_resource(params: dict, full_msg: dict):
    """Handle delete_resource action - 실제 파일 삭제"""
    resource_id = params.get("resource_id", "unknown")
    sender_id = full_msg.get("sender", {}).get("agent_id", "unknown")
    
    # 삭제 시도 로깅
    monitor_log({
        "alert": "high_risk_action_attempt",
        "agent": AGENT_ID,
        "action": "delete_resource",
        "resource_id": resource_id,
        "requested_by": sender_id,
        "timestamp": datetime.utcnow().isoformat() + "Z"
    })
    
    resource_path = get_resource_path(resource_id)
    
    try:
        if not resource_path.exists():
            # 리소스가 존재하지 않음
            log_resource_access("delete_resource", resource_id, sender_id, False, {
                "error": "Resource not found",
                "file_path": str(resource_path)
            })
            monitor_log({
                "warning": "delete_resource_not_found",
                "agent": AGENT_ID,
                "resource_id": resource_id,
                "requested_by": sender_id
            })
            return {
                "status": "error",
                "action": "delete_resource",
                "resource_id": resource_id,
                "error": "Resource not found"
            }
        
        # 실제 파일 삭제
        resource_path.unlink()
        
        # 삭제 성공 로깅
        log_resource_access("delete_resource", resource_id, sender_id, True, {
            "file_path": str(resource_path),
            "deleted_at": datetime.utcnow().isoformat() + "Z"
        })
        
        monitor_log({
            "alert": "high_risk_action_executed",
            "agent": AGENT_ID,
            "action": "delete_resource",
            "resource_id": resource_id,
            "requested_by": sender_id,
            "file_path": str(resource_path),
            "result": "success"
        })
        
        await asyncio.sleep(0.2)  # 처리 시뮬레이션
        return {
            "status": "ok",
            "action": "delete_resource",
            "resource_id": resource_id,
            "result": "Resource deleted successfully",
            "file_path": str(resource_path)
        }
    except Exception as e:
        # 삭제 실패 로깅
        log_resource_access("delete_resource", resource_id, sender_id, False, {
            "error": str(e),
            "file_path": str(resource_path)
        })
        monitor_log({
            "error": "delete_resource_failed",
            "agent": AGENT_ID,
            "resource_id": resource_id,
            "requested_by": sender_id,
            "error": str(e)
        })
        return {
            "status": "error",
            "action": "delete_resource",
            "resource_id": resource_id,
            "error": str(e)
        }

async def handle_read_resource(params: dict, full_msg: dict):
    """Handle read_resource action - 실제 파일 읽기"""
    resource_id = params.get("resource", "unknown")
    sender_id = full_msg.get("sender", {}).get("agent_id", "unknown")
    
    resource_path = get_resource_path(resource_id)
    
    try:
        if not resource_path.exists():
            # 리소스가 존재하지 않음
            log_resource_access("read_resource", resource_id, sender_id, False, {
                "error": "Resource not found",
                "file_path": str(resource_path)
            })
            monitor_log({
                "warning": "read_resource_not_found",
                "agent": AGENT_ID,
                "resource_id": resource_id,
        "requested_by": sender_id
            })
            return {
                "status": "error",
                "action": "read_resource",
                "resource_id": resource_id,
                "error": "Resource not found"
            }
        
        # 실제 파일 읽기
        with open(resource_path, "r", encoding="utf-8") as f:
            content = f.read()
        
        # 읽기 성공 로깅
        log_resource_access("read_resource", resource_id, sender_id, True, {
            "file_path": str(resource_path),
            "content_length": len(content)
        })
        
        monitor_log({
            "info": "read_resource_executed",
            "agent": AGENT_ID,
            "action": "read_resource",
            "resource_id": resource_id,
            "requested_by": sender_id,
            "file_path": str(resource_path),
            "content_length": len(content)
        })
        
        await asyncio.sleep(0.1)  # 처리 시뮬레이션
        return {
            "status": "ok",
            "action": "read_resource",
            "resource_id": resource_id,
            "data": content,
            "file_path": str(resource_path)
        }
    except Exception as e:
        # 읽기 실패 로깅
        log_resource_access("read_resource", resource_id, sender_id, False, {
            "error": str(e),
            "file_path": str(resource_path)
        })
        monitor_log({
            "error": "read_resource_failed",
            "agent": AGENT_ID,
            "resource_id": resource_id,
            "requested_by": sender_id,
            "error": str(e)
        })
        return {
            "status": "error",
            "action": "read_resource",
            "resource_id": resource_id,
            "error": str(e)
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

async def handle_analyze_data(params: dict, full_msg: dict):
    """Handle analyze_data action - 데이터 분석 작업"""
    dataset = params.get("dataset", "unknown")
    analysis_type = params.get("type", "statistics")
    sender_id = full_msg.get("sender", {}).get("agent_id", "unknown")
    
    monitor_log({
        "info": "analyze_data_executed",
        "agent": AGENT_ID,
        "action": "analyze_data",
        "dataset": dataset,
        "type": analysis_type,
        "requested_by": sender_id
    })
    
    await asyncio.sleep(0.3)  # 분석 작업 시뮬레이션
    return {
        "status": "ok",
        "action": "analyze_data",
        "dataset": dataset,
        "type": analysis_type,
        "result": f"Analysis complete: {analysis_type} on {dataset}",
        "summary": {"rows": 1000, "columns": 10, "statistics": "calculated"}
    }

async def handle_generate_report(params: dict, full_msg: dict):
    """Handle generate_report action - 리포트 생성"""
    report_type = params.get("report_type", "daily")
    sender_id = full_msg.get("sender", {}).get("agent_id", "unknown")
    
    monitor_log({
        "info": "generate_report_executed",
        "agent": AGENT_ID,
        "action": "generate_report",
        "report_type": report_type,
        "requested_by": sender_id
    })
    
    await asyncio.sleep(0.5)  # 리포트 생성 시뮬레이션
    return {
        "status": "ok",
        "action": "generate_report",
        "report_type": report_type,
        "report_id": f"report-{uuid.uuid4().hex[:8]}",
        "generated_at": datetime.utcnow().isoformat() + "Z"
    }

async def handle_cleanup_logs(params: dict, full_msg: dict):
    """Handle cleanup_logs action - 로그 정리"""
    days = params.get("days", 7)
    sender_id = full_msg.get("sender", {}).get("agent_id", "unknown")
    
    monitor_log({
        "info": "cleanup_logs_executed",
        "agent": AGENT_ID,
        "action": "cleanup_logs",
        "days": days,
        "requested_by": sender_id
    })
    
    await asyncio.sleep(0.2)
    return {
        "status": "ok",
        "action": "cleanup_logs",
        "days": days,
        "files_cleaned": 10,
        "space_freed": "50MB"
    }

async def handle_generate_monthly_sales_report(params: dict, full_msg: dict):
    """월간 매출 리포트 생성 - 실제 파일 생성"""
    period = params.get("period", "unknown")
    format_type = params.get("format", "pdf")
    include_charts = params.get("include_charts", False)
    sender_id = full_msg.get("sender", {}).get("agent_id", "unknown")
    
    report_id = f"sales-report-{period}-{uuid.uuid4().hex[:8]}"
    report_path = RESOURCES_DIR / f"{report_id}.{format_type}"
    
    # 실제 리포트 파일 생성
    report_content = f"""Monthly Sales Report - {period}
Generated: {datetime.utcnow().isoformat()}Z
Requested by: {sender_id}

Summary:
- Total Revenue: $125,000
- Units Sold: 1,250
- Average Order Value: $100
- Top Product: Product A (350 units)
- Growth Rate: +12.5% vs previous month

{'[Charts included]' if include_charts else '[Charts not included]'}
"""
    
    try:
        with open(report_path, "w", encoding="utf-8") as f:
            f.write(report_content)
        
        monitor_log({
            "info": "monthly_sales_report_generated",
            "agent": AGENT_ID,
            "report_id": report_id,
            "period": period,
            "format": format_type,
            "requested_by": sender_id,
            "file_path": str(report_path)
        })
        
        await asyncio.sleep(0.5)  # 리포트 생성 시뮬레이션
        return {
            "status": "ok",
            "action": "generate_monthly_sales_report",
            "report_id": report_id,
            "period": period,
            "format": format_type,
            "file_path": str(report_path),
            "file_size_bytes": len(report_content),
            "generated_at": datetime.utcnow().isoformat() + "Z"
        }
    except Exception as e:
        return {
            "status": "error",
            "action": "generate_monthly_sales_report",
            "error": str(e)
        }

async def handle_analyze_customer_data(params: dict, full_msg: dict):
    """고객 데이터 분석 수행"""
    dataset = params.get("dataset", "unknown")
    analysis_type = params.get("analysis_type", "basic")
    time_range = params.get("time_range", "unknown")
    sender_id = full_msg.get("sender", {}).get("agent_id", "unknown")
    
    # 실제 분석 수행 시뮬레이션
    await asyncio.sleep(0.4)
    
    analysis_results = {
        "trend_analysis": {
            "total_customers": 12500,
            "new_customers": 450,
            "returning_customers": 3800,
            "churn_rate": 2.3,
            "growth_rate": 8.5,
            "avg_session_duration": "12m 34s",
            "top_segments": ["Segment A (35%)", "Segment B (28%)", "Segment C (22%)"]
        },
        "basic": {
            "total_customers": 12500,
            "active_customers": 8200,
            "inactive_customers": 4300
        }
    }
    
    result = analysis_results.get(analysis_type, analysis_results["basic"])
    
    monitor_log({
        "info": "customer_data_analyzed",
        "agent": AGENT_ID,
        "dataset": dataset,
        "analysis_type": analysis_type,
        "time_range": time_range,
        "requested_by": sender_id
    })
    
    return {
        "status": "ok",
        "action": "analyze_customer_data",
        "dataset": dataset,
        "analysis_type": analysis_type,
        "time_range": time_range,
        "results": result,
        "analysis_completed_at": datetime.utcnow().isoformat() + "Z"
    }

async def handle_search_documents(params: dict, full_msg: dict):
    """문서 검색 수행"""
    query = params.get("query", "")
    document_type = params.get("document_type", "all")
    max_results = params.get("max_results", 10)
    sender_id = full_msg.get("sender", {}).get("agent_id", "unknown")
    
    # 실제 검색 수행 시뮬레이션
    await asyncio.sleep(0.3)
    
    # 검색 결과 시뮬레이션
    search_results = [
        {
            "document_id": f"doc-{uuid.uuid4().hex[:8]}",
            "title": f"Document containing '{query}'",
            "type": document_type if document_type != "all" else "pdf",
            "relevance_score": 0.95 - (i * 0.1),
            "snippet": f"...{query}...",
            "last_modified": datetime.utcnow().isoformat() + "Z"
        }
        for i in range(min(max_results, 5))
    ]
    
    monitor_log({
        "info": "documents_searched",
        "agent": AGENT_ID,
        "query": query,
        "document_type": document_type,
        "results_count": len(search_results),
        "requested_by": sender_id
    })
    
    return {
        "status": "ok",
        "action": "search_documents",
        "query": query,
        "document_type": document_type,
        "results": search_results,
        "total_found": len(search_results),
        "search_completed_at": datetime.utcnow().isoformat() + "Z"
    }

async def handle_generate_weekly_summary(params: dict, full_msg: dict):
    """주간 요약 리포트 생성"""
    week = params.get("week", "unknown")
    sections = params.get("sections", [])
    sender_id = full_msg.get("sender", {}).get("agent_id", "unknown")
    
    summary_id = f"weekly-summary-{week}-{uuid.uuid4().hex[:8]}"
    summary_path = RESOURCES_DIR / f"{summary_id}.txt"
    
    summary_content = f"""Weekly Summary Report - {week}
Generated: {datetime.utcnow().isoformat()}Z
Requested by: {sender_id}

Sections included: {', '.join(sections)}

Sales Section:
- Weekly Revenue: $45,000
- Transactions: 450
- Top Product: Product B

Marketing Section:
- Campaigns Active: 3
- Email Open Rate: 24.5%
- Social Media Engagement: +15%

Operations Section:
- System Uptime: 99.8%
- API Requests: 125,000
- Average Response Time: 120ms
"""
    
    try:
        with open(summary_path, "w", encoding="utf-8") as f:
            f.write(summary_content)
        
        monitor_log({
            "info": "weekly_summary_generated",
            "agent": AGENT_ID,
            "summary_id": summary_id,
            "week": week,
            "sections": sections,
            "requested_by": sender_id
        })
        
        await asyncio.sleep(0.4)
        return {
            "status": "ok",
            "action": "generate_weekly_summary",
            "summary_id": summary_id,
            "week": week,
            "sections": sections,
            "file_path": str(summary_path),
            "generated_at": datetime.utcnow().isoformat() + "Z"
        }
    except Exception as e:
        return {
            "status": "error",
            "action": "generate_weekly_summary",
            "error": str(e)
        }

async def handle_query_database(params: dict, full_msg: dict):
    """데이터베이스 쿼리 수행"""
    query = params.get("query", "")
    database = params.get("database", "unknown")
    sender_id = full_msg.get("sender", {}).get("agent_id", "unknown")
    
    await asyncio.sleep(0.3)
    
    # 쿼리 결과 시뮬레이션
    query_result = {
        "query": query,
        "rows_returned": 1250,
        "execution_time_ms": 45,
        "columns": ["count"],
        "data": [{"count": 1250}]
    }
    
    monitor_log({
        "info": "database_query_executed",
        "agent": AGENT_ID,
        "database": database,
        "query": query[:100],  # 보안상 쿼리 일부만 로깅
        "requested_by": sender_id
    })
    
    return {
        "status": "ok",
        "action": "query_database",
        "database": database,
        "result": query_result,
        "executed_at": datetime.utcnow().isoformat() + "Z"
    }

async def handle_check_system_health(params: dict, full_msg: dict):
    """시스템 상태 확인"""
    sender_id = full_msg.get("sender", {}).get("agent_id", "unknown")
    
    await asyncio.sleep(0.1)
    
    health_status = {
        "overall": "healthy",
        "services": {
            "api": {"status": "running", "uptime": "99.8%", "response_time_ms": 45},
            "database": {"status": "running", "connections": 45, "max_connections": 100},
            "cache": {"status": "running", "hit_rate": "94.2%"},
            "queue": {"status": "running", "pending_jobs": 12}
        },
        "resources": {
            "cpu_usage": "45%",
            "memory_usage": "62%",
            "disk_usage": "58%"
        }
    }
    
    return {
        "status": "ok",
        "action": "check_system_health",
        "health": health_status,
        "checked_at": datetime.utcnow().isoformat() + "Z"
    }

async def handle_get_service_status(params: dict, full_msg: dict):
    """특정 서비스 상태 확인"""
    service = params.get("service", "unknown")
    sender_id = full_msg.get("sender", {}).get("agent_id", "unknown")
    
    await asyncio.sleep(0.1)
    
    service_statuses = {
        "api": {"status": "running", "version": "2.1.0", "uptime": "99.8%", "requests_per_min": 1250},
        "database": {"status": "running", "version": "PostgreSQL 14.5", "connections": 45, "queries_per_sec": 120},
        "cache": {"status": "running", "type": "Redis", "hit_rate": "94.2%", "memory_used": "2.5GB"},
        "queue": {"status": "running", "type": "RabbitMQ", "pending_jobs": 12, "processed_today": 45000}
    }
    
    service_status = service_statuses.get(service, {"status": "unknown", "error": "Service not found"})
    
    return {
        "status": "ok",
        "action": "get_service_status",
        "service": service,
        "details": service_status,
        "checked_at": datetime.utcnow().isoformat() + "Z"
    }

async def handle_create_database_backup(params: dict, full_msg: dict):
    """데이터베이스 백업 생성"""
    database = params.get("database", "unknown")
    backup_type = params.get("backup_type", "full")
    retention_days = params.get("retention_days", 30)
    sender_id = full_msg.get("sender", {}).get("agent_id", "unknown")
    
    backup_id = f"backup-{database}-{datetime.utcnow().strftime('%Y%m%d-%H%M%S')}-{uuid.uuid4().hex[:8]}"
    backup_path = RESOURCES_DIR / f"{backup_id}.sql"
    
    # 백업 파일 생성 시뮬레이션
    backup_content = f"""-- Database Backup: {database}
-- Type: {backup_type}
-- Created: {datetime.utcnow().isoformat()}Z
-- Requested by: {sender_id}
-- Retention: {retention_days} days

-- Backup data would be here...
"""
    
    try:
        with open(backup_path, "w", encoding="utf-8") as f:
            f.write(backup_content)
        
        monitor_log({
            "alert": "database_backup_created",
            "agent": AGENT_ID,
            "backup_id": backup_id,
            "database": database,
            "backup_type": backup_type,
            "requested_by": sender_id,
            "file_path": str(backup_path)
        })
        
        await asyncio.sleep(0.6)  # 백업 생성 시뮬레이션
        return {
            "status": "ok",
            "action": "create_database_backup",
            "backup_id": backup_id,
            "database": database,
            "backup_type": backup_type,
            "file_path": str(backup_path),
            "file_size_bytes": len(backup_content),
            "retention_days": retention_days,
            "created_at": datetime.utcnow().isoformat() + "Z"
        }
    except Exception as e:
        return {
            "status": "error",
            "action": "create_database_backup",
            "error": str(e)
        }

async def handle_archive_old_logs(params: dict, full_msg: dict):
    """오래된 로그 파일 아카이빙"""
    log_directory = params.get("log_directory", "/var/log/app")
    days_to_keep = params.get("days_to_keep", 90)
    archive_format = params.get("archive_format", "tar.gz")
    sender_id = full_msg.get("sender", {}).get("agent_id", "unknown")
    
    archive_id = f"logs-archive-{datetime.utcnow().strftime('%Y%m%d')}-{uuid.uuid4().hex[:8]}"
    archive_path = RESOURCES_DIR / f"{archive_id}.{archive_format}"
    
    # 아카이브 파일 생성 시뮬레이션
    try:
        with open(archive_path, "w", encoding="utf-8") as f:
            f.write(f"# Archived logs from {log_directory}\n# Days to keep: {days_to_keep}\n")
        
        monitor_log({
            "info": "logs_archived",
            "agent": AGENT_ID,
            "archive_id": archive_id,
            "log_directory": log_directory,
            "days_to_keep": days_to_keep,
            "requested_by": sender_id
        })
        
        await asyncio.sleep(0.5)
        return {
            "status": "ok",
            "action": "archive_old_logs",
            "archive_id": archive_id,
            "log_directory": log_directory,
            "days_to_keep": days_to_keep,
            "archive_format": archive_format,
            "file_path": str(archive_path),
            "files_archived": 25,
            "total_size_mb": 125,
            "archived_at": datetime.utcnow().isoformat() + "Z"
        }
    except Exception as e:
        return {
            "status": "error",
            "action": "archive_old_logs",
            "error": str(e)
        }

async def handle_update_system_config(params: dict, full_msg: dict):
    """시스템 설정 업데이트"""
    config_key = params.get("config_key", "unknown")
    new_value = params.get("new_value", "")
    restart_required = params.get("restart_required", False)
    sender_id = full_msg.get("sender", {}).get("agent_id", "unknown")
    
    monitor_log({
        "alert": "system_config_updated",
        "agent": AGENT_ID,
        "config_key": config_key,
        "new_value": new_value,
        "restart_required": restart_required,
        "requested_by": sender_id
    })
    
    await asyncio.sleep(0.2)
    return {
        "status": "ok",
        "action": "update_system_config",
        "config_key": config_key,
        "old_value": "previous_value",
        "new_value": new_value,
        "restart_required": restart_required,
        "updated_at": datetime.utcnow().isoformat() + "Z"
    }

async def handle_cleanup_temp_files(params: dict, full_msg: dict):
    """임시 파일 정리"""
    directories = params.get("directories", [])
    max_age_hours = params.get("max_age_hours", 24)
    sender_id = full_msg.get("sender", {}).get("agent_id", "unknown")
    
    await asyncio.sleep(0.3)
    
    monitor_log({
        "info": "temp_files_cleaned",
        "agent": AGENT_ID,
        "directories": directories,
        "max_age_hours": max_age_hours,
        "requested_by": sender_id
    })
    
    return {
        "status": "ok",
        "action": "cleanup_temp_files",
        "directories": directories,
        "max_age_hours": max_age_hours,
        "files_deleted": 45,
        "space_freed_mb": 250,
        "cleaned_at": datetime.utcnow().isoformat() + "Z"
    }

async def handle_rotate_application_logs(params: dict, full_msg: dict):
    """애플리케이션 로그 로테이션"""
    log_file = params.get("log_file", "/var/log/app/application.log")
    max_size_mb = params.get("max_size_mb", 100)
    keep_rotated = params.get("keep_rotated", 5)
    sender_id = full_msg.get("sender", {}).get("agent_id", "unknown")
    
    await asyncio.sleep(0.2)
    
    monitor_log({
        "info": "application_logs_rotated",
        "agent": AGENT_ID,
        "log_file": log_file,
        "max_size_mb": max_size_mb,
        "keep_rotated": keep_rotated,
        "requested_by": sender_id
    })
    
    return {
        "status": "ok",
        "action": "rotate_application_logs",
        "log_file": log_file,
        "max_size_mb": max_size_mb,
        "keep_rotated": keep_rotated,
        "rotated_files": [f"{log_file}.{i}" for i in range(1, keep_rotated + 1)],
        "rotated_at": datetime.utcnow().isoformat() + "Z"
    }

async def handle_check_disk_space(params: dict, full_msg: dict):
    """디스크 공간 확인"""
    threshold_percent = params.get("threshold_percent", 80)
    paths = params.get("paths", ["/"])
    sender_id = full_msg.get("sender", {}).get("agent_id", "unknown")
    
    await asyncio.sleep(0.1)
    
    disk_status = {
        path: {
            "total_gb": 500,
            "used_gb": 290,
            "available_gb": 210,
            "usage_percent": 58.0,
            "status": "ok" if 58.0 < threshold_percent else "warning"
        }
        for path in paths
    }
    
    return {
        "status": "ok",
        "action": "check_disk_space",
        "threshold_percent": threshold_percent,
        "disk_status": disk_status,
        "checked_at": datetime.utcnow().isoformat() + "Z"
    }

async def handle_update_user_permissions(params: dict, full_msg: dict):
    """사용자 권한 업데이트"""
    user_id = params.get("user_id", "unknown")
    new_role = params.get("new_role", "viewer")
    resource = params.get("resource", "unknown")
    sender_id = full_msg.get("sender", {}).get("agent_id", "unknown")
    
    monitor_log({
        "alert": "user_permissions_updated",
        "agent": AGENT_ID,
        "user_id": user_id,
        "new_role": new_role,
        "resource": resource,
        "requested_by": sender_id
    })
    
    await asyncio.sleep(0.2)
    return {
        "status": "ok",
        "action": "update_user_permissions",
        "user_id": user_id,
        "old_role": "previous_role",
        "new_role": new_role,
        "resource": resource,
        "updated_at": datetime.utcnow().isoformat() + "Z"
    }

async def handle_analyze_report_data(params: dict, full_msg: dict):
    """리포트 데이터 분석"""
    report_id = params.get("report_id", "unknown")
    analysis_type = params.get("analysis_type", "basic")
    sender_id = full_msg.get("sender", {}).get("agent_id", "unknown")
    
    await asyncio.sleep(0.3)
    
    return {
        "status": "ok",
        "action": "analyze_report_data",
        "report_id": report_id,
        "analysis_type": analysis_type,
        "insights": {
            "key_metrics": ["Revenue up 12%", "Customer retention improved"],
            "trends": ["Positive growth trend", "Seasonal patterns detected"],
            "recommendations": ["Continue current strategy", "Focus on top products"]
        },
        "analyzed_at": datetime.utcnow().isoformat() + "Z"
    }

def main():
    # Define action handlers - 실제 작업 수행
    action_handlers = {
        # 기본 작업
        "delete_resource": handle_delete_resource,
        "read_resource": handle_read_resource,
        "get_status": handle_get_status,
        "ping": handle_ping,
        
        # 데이터 분석 및 리포트
        "analyze_data": handle_analyze_data,
        "generate_report": handle_generate_report,
        "generate_monthly_sales_report": handle_generate_monthly_sales_report,
        "generate_weekly_summary": handle_generate_weekly_summary,
        "analyze_customer_data": handle_analyze_customer_data,
        "analyze_report_data": handle_analyze_report_data,
        
        # 문서 및 검색
        "search_documents": handle_search_documents,
        "query_database": handle_query_database,
        
        # 시스템 관리
        "cleanup_logs": handle_cleanup_logs,
        "create_database_backup": handle_create_database_backup,
        "archive_old_logs": handle_archive_old_logs,
        "update_system_config": handle_update_system_config,
        "cleanup_temp_files": handle_cleanup_temp_files,
        "rotate_application_logs": handle_rotate_application_logs,
        "check_disk_space": handle_check_disk_space,
        "update_user_permissions": handle_update_user_permissions,
        
        # 모니터링
        "check_system_health": handle_check_system_health,
        "get_service_status": handle_get_service_status,
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