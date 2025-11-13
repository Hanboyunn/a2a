"""Database models and operations for Agent Management"""
import sqlite3
import json
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, List
from contextlib import contextmanager

DB_PATH = Path("agent_manager/agents.db")

def init_database():
    """Initialize the database with required tables"""
    DB_PATH.parent.mkdir(exist_ok=True)
    
    with get_db_connection() as conn:
        cursor = conn.cursor()
        
        # Agents table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS agents (
                agent_id TEXT PRIMARY KEY,
                endpoint TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'active',
                agent_type TEXT,
                capabilities TEXT,
                registered_at TEXT NOT NULL,
                last_heartbeat TEXT,
                metadata TEXT
            )
        """)
        
        # Agent messages table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS agent_messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                sender_id TEXT NOT NULL,
                recipient_id TEXT NOT NULL,
                action TEXT NOT NULL,
                message_id TEXT UNIQUE,
                timestamp TEXT NOT NULL,
                status TEXT,
                trust_score REAL,
                FOREIGN KEY (sender_id) REFERENCES agents(agent_id),
                FOREIGN KEY (recipient_id) REFERENCES agents(agent_id)
            )
        """)
        
        # Agent health checks table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS agent_health (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                agent_id TEXT NOT NULL,
                check_time TEXT NOT NULL,
                status TEXT NOT NULL,
                response_time_ms INTEGER,
                error_message TEXT,
                FOREIGN KEY (agent_id) REFERENCES agents(agent_id)
            )
        """)
        
        # System configuration table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS system_config (
                config_key TEXT PRIMARY KEY,
                config_value TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                updated_by TEXT
            )
        """)
        
        conn.commit()

@contextmanager
def get_db_connection():
    """Get database connection with automatic commit/rollback"""
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

def register_agent(agent_id: str, endpoint: str, agent_type: Optional[str] = None, 
                  capabilities: Optional[List[str]] = None, metadata: Optional[Dict] = None):
    """Register a new agent or update existing agent"""
    now = datetime.utcnow().isoformat() + "Z"
    capabilities_json = json.dumps(capabilities or [])
    metadata_json = json.dumps(metadata or {})
    
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT OR REPLACE INTO agents 
            (agent_id, endpoint, status, agent_type, capabilities, registered_at, last_heartbeat, metadata)
            VALUES (?, ?, 'active', ?, ?, ?, ?, ?)
        """, (agent_id, endpoint, agent_type, capabilities_json, now, now, metadata_json))
        
        return {
            "agent_id": agent_id,
            "endpoint": endpoint,
            "status": "active",
            "registered_at": now
        }

def unregister_agent(agent_id: str):
    """Unregister an agent"""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("UPDATE agents SET status = 'inactive' WHERE agent_id = ?", (agent_id,))
        return cursor.rowcount > 0

def update_agent_heartbeat(agent_id: str):
    """Update agent's last heartbeat timestamp"""
    now = datetime.utcnow().isoformat() + "Z"
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE agents SET last_heartbeat = ? WHERE agent_id = ?
        """, (now, agent_id))
        return cursor.rowcount > 0

def get_agent(agent_id: str) -> Optional[Dict]:
    """Get agent information"""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM agents WHERE agent_id = ?", (agent_id,))
        row = cursor.fetchone()
        if row:
            return dict(row)
        return None

def list_agents(status: Optional[str] = None) -> List[Dict]:
    """List all agents, optionally filtered by status"""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        if status:
            cursor.execute("SELECT * FROM agents WHERE status = ? ORDER BY registered_at DESC", (status,))
        else:
            cursor.execute("SELECT * FROM agents ORDER BY registered_at DESC")
        return [dict(row) for row in cursor.fetchall()]

def log_message(sender_id: str, recipient_id: str, action: str, 
                message_id: str, status: str = "sent", trust_score: Optional[float] = None):
    """Log agent message"""
    now = datetime.utcnow().isoformat() + "Z"
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT OR IGNORE INTO agent_messages 
            (sender_id, recipient_id, action, message_id, timestamp, status, trust_score)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (sender_id, recipient_id, action, message_id, now, status, trust_score))

def record_health_check(agent_id: str, status: str, response_time_ms: Optional[int] = None, 
                       error_message: Optional[str] = None):
    """Record agent health check result"""
    now = datetime.utcnow().isoformat() + "Z"
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO agent_health (agent_id, check_time, status, response_time_ms, error_message)
            VALUES (?, ?, ?, ?, ?)
        """, (agent_id, now, status, response_time_ms, error_message))

def get_config(config_key: str) -> Optional[str]:
    """Get system configuration value"""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT config_value FROM system_config WHERE config_key = ?", (config_key,))
        row = cursor.fetchone()
        return row[0] if row else None

def set_config(config_key: str, config_value: str, updated_by: Optional[str] = None):
    """Set system configuration value"""
    now = datetime.utcnow().isoformat() + "Z"
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT OR REPLACE INTO system_config (config_key, config_value, updated_at, updated_by)
            VALUES (?, ?, ?, ?)
        """, (config_key, config_value, now, updated_by))

