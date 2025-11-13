import json
import os
from datetime import datetime

# 로그 저장 경로
ROOT_DIR = "monitor"
DATA_FILE = os.path.join(ROOT_DIR, "data.jsonl")
ALERTS_FILE = os.path.join(ROOT_DIR, "alerts.jsonl")

# 폴더 없으면 자동 생성
os.makedirs(ROOT_DIR, exist_ok=True)

def _write_jsonl(path: str, record: dict):
    """JSONL 형식으로 로그를 한 줄씩 append"""
    try:
        with open(path, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
    except Exception as e:
        print(f"[!] Failed to write {path}: {e}")

def add_message(msg: dict):
    """
    일반 메시지를 data.jsonl에 저장
    - monitor.py에서 수집된 agent 트래픽 기록용
    """
    entry = {
        "ts": datetime.utcnow().isoformat() + "Z",
        "message": msg
    }
    _write_jsonl(DATA_FILE, entry)

def add_alert(reason: dict):
    """
    경고/위험 이벤트를 alerts.jsonl에 저장
    - 신뢰도 낮음, 리플레이, 폐기된 agent 등
    """
    entry = {
        "ts": datetime.utcnow().isoformat() + "Z",
        "reason": reason
    }
    _write_jsonl(ALERTS_FILE, entry)

def clear_logs():
    """data.jsonl, alerts.jsonl 초기화"""
    open(DATA_FILE, "w").close()
    open(ALERTS_FILE, "w").close()
    print("✅ Cleared monitor logs (data.jsonl, alerts.jsonl)")
