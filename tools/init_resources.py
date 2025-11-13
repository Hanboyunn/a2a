#!/usr/bin/env python3
"""
리소스 저장소 초기화 및 샘플 데이터 생성
"""
import os
from pathlib import Path

RESOURCES_DIR = Path("resources")

def init_resources():
    """리소스 디렉토리 초기화 및 샘플 리소스 생성"""
    # 리소스 디렉토리 생성
    RESOURCES_DIR.mkdir(exist_ok=True)
    
    # 샘플 리소스 생성
    sample_resources = {
        "doc-001": "This is a sample document with important information.\nCreated: 2024-01-01",
        "doc-002": "Another document containing user data.\nStatus: Active",
        "doc-003": "Configuration file for system settings.\nVersion: 1.0",
        "critical-db-01": "Critical database configuration.\n⚠️ DO NOT DELETE",
        "config-main": "Main system configuration.\nKey: value\nPort: 8080",
        "user-data-001": "User profile data.\nName: John Doe\nEmail: john@example.com",
    }
    
    print(f"[+] Initializing resources directory: {RESOURCES_DIR}")
    
    for resource_id, content in sample_resources.items():
        resource_path = RESOURCES_DIR / f"{resource_id}.txt"
        with open(resource_path, "w", encoding="utf-8") as f:
            f.write(content)
        print(f"  ✓ Created: {resource_id}.txt")
    
    print(f"\n[+] Created {len(sample_resources)} sample resources")
    print(f"[+] Resources directory: {RESOURCES_DIR.absolute()}")

if __name__ == "__main__":
    init_resources()

