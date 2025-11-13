#!/usr/bin/env python3
"""
실행 중인 모든 agent 프로세스를 종료하는 스크립트
"""
import subprocess
import sys
import socket

def check_port(port):
    """포트가 사용 중인지 확인"""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(1)
            result = s.connect_ex(('127.0.0.1', port))
            return result == 0
    except:
        return False

def kill_process_on_port(port):
    """특정 포트를 사용하는 프로세스 종료"""
    if sys.platform == "win32":
        try:
            # netstat으로 포트를 사용하는 PID 찾기
            result = subprocess.run(
                f'netstat -ano | findstr :{port}',
                shell=True,
                capture_output=True,
                text=True
            )
            if result.stdout:
                for line in result.stdout.strip().split('\n'):
                    parts = line.split()
                    if len(parts) >= 5 and parts[1].endswith(f':{port}'):
                        pid = parts[-1]
                        try:
                            subprocess.run(f'taskkill /F /PID {pid}', shell=True, capture_output=True)
                            print(f"  ✓ Port {port} (PID {pid}) 종료됨")
                        except:
                            pass
        except Exception as e:
            print(f"  ⚠ Port {port} 종료 실패: {e}")
    else:
        # Linux/Mac
        try:
            result = subprocess.run(
                f'lsof -ti:{port}',
                shell=True,
                capture_output=True,
                text=True
            )
            if result.stdout.strip():
                pids = result.stdout.strip().split('\n')
                for pid in pids:
                    subprocess.run(f'kill -9 {pid}', shell=True, capture_output=True)
                    print(f"  ✓ Port {port} (PID {pid}) 종료됨")
        except:
            pass

def main():
    ports = [8100, 8000, 8001, 8002, 8003]
    names = ["Monitor", "Orchestrator", "User Agent", "Tool Agent", "Admin Agent"]
    
    print("=" * 60)
    print("🛑 A2A Agent 프로세스 종료")
    print("=" * 60)
    print()
    
    for port, name in zip(ports, names):
        if check_port(port):
            print(f"[!] {name} (포트 {port}) 실행 중 - 종료 중...")
            kill_process_on_port(port)
        else:
            print(f"[✓] {name} (포트 {port}) 실행 중이 아님")
    
    print()
    print("=" * 60)
    print("✅ 완료!")
    print("=" * 60)

if __name__ == "__main__":
    main()

