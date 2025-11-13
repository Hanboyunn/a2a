#!/usr/bin/env python3
"""
모든 A2A agent를 실행하는 통합 스크립트
"""
import subprocess
import sys
import time
import signal
import os
from pathlib import Path

# 프로세스 리스트
processes = []

def signal_handler(sig, frame):
    """Ctrl+C 핸들러 - 모든 프로세스 종료"""
    print("\n\n[!] 종료 신호 수신. 모든 agent 종료 중...")
    for proc in processes:
        try:
            proc.terminate()
        except:
            pass
    time.sleep(1)
    for proc in processes:
        try:
            proc.kill()
        except:
            pass
    sys.exit(0)

def check_port(port):
    """포트가 사용 중인지 확인"""
    import socket
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(1)
            result = s.connect_ex(('127.0.0.1', port))
            return result == 0
    except:
        return False

def run_agent(name, module, port=None):
    """Agent를 별도 프로세스로 실행"""
    cmd = [sys.executable, "-m", module]
    if port:
        print(f"[+] Starting {name} on port {port}...")
    else:
        print(f"[+] Starting {name}...")
    
    # 로그 디렉토리 생성
    import os
    os.makedirs("logs", exist_ok=True)
    
    # Windows와 Linux 모두에서 작동하도록 설정
    if sys.platform == "win32":
        # Windows: 각 agent를 별도 콘솔 창에서 실행 (사용자가 볼 수 있도록)
        # start 명령어를 사용하여 새 창에서 실행
        import subprocess as sp
        try:
            # Windows start 명령어로 새 창 열기
            sp.Popen(
                f'start "{name}" cmd /k "python -m {module}"',
                shell=True
            )
            # 더미 프로세스 객체 반환 (실제로는 추적 불가)
            class DummyProc:
                def poll(self):
                    return None  # 항상 실행 중으로 표시
            proc = DummyProc()
        except Exception as e:
            print(f"    ⚠ Failed to start {name} in new window: {e}")
            # 폴백: 백그라운드 실행
            log_file = open(f"logs/{name.lower().replace(' ', '_')}.log", "w", encoding="utf-8")
            proc = subprocess.Popen(
                cmd,
                stdout=log_file,
                stderr=subprocess.STDOUT,
                text=True
            )
    else:
        # Linux/Mac: 출력을 파일로 리다이렉트
        log_file = open(f"logs/{name.lower().replace(' ', '_')}.log", "w")
        proc = subprocess.Popen(
            cmd,
            stdout=log_file,
            stderr=subprocess.STDOUT,
            text=True
        )
    
    processes.append(proc)
    
    # 포트가 있는 경우 서버가 시작될 때까지 대기
    if port:
        max_wait = 10
        waited = 0
        while waited < max_wait:
            if check_port(port):
                print(f"    ✓ {name} started successfully on port {port}")
                return proc
            time.sleep(0.5)
            waited += 0.5
        print(f"    ⚠ {name} may not have started (port {port} not responding)")
    
    return proc

def main():
    # Signal handler 등록
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    print("=" * 60)
    print("🤖 A2A Agent System 시작")
    print("=" * 60)
    print("\n모니터링 대시보드: http://127.0.0.1:8100/dashboard")
    print("API 엔드포인트:")
    print("  - Monitor: http://127.0.0.1:8100")
    print("  - Orchestrator: http://127.0.0.1:8000")
    print("  - User Agent: http://127.0.0.1:8001")
    print("  - Tool Agent: http://127.0.0.1:8002")
    print("  - Admin Agent: http://127.0.0.1:8003")
    print("\n⚠️  각 agent가 별도 창에서 실행됩니다.")
    print("⚠️  종료하려면 각 창에서 Ctrl+C를 누르거나 창을 닫으세요.")
    print("\n💡 Windows에서는 run_all_agents.bat를 사용하는 것을 권장합니다.\n")
    
    # 1. Monitor 시작
    run_agent("Monitor", "monitor.monitor", 8100)
    time.sleep(2)
    
    # 2. Orchestrator 시작
    run_agent("Orchestrator", "agents.orchestrator", 8000)
    time.sleep(2)
    
    # 3. Tool Agent 시작
    run_agent("Tool Agent", "agents.tool_agent", 8002)
    time.sleep(2)
    
    # 4. User Agent 시작
    run_agent("User Agent", "agents.user_agent", 8001)
    time.sleep(2)
    
    # 5. Admin Agent 시작
    run_agent("Admin Agent", "agents.admin_agent", 8003)
    time.sleep(2)
    
    print("\n" + "=" * 60)
    print("✅ 모든 agent가 시작되었습니다!")
    print("=" * 60)
    print("\n실시간 모니터링: http://127.0.0.1:8100/dashboard")
    print("\n로그를 확인하려면 각 agent의 출력을 확인하세요.")
    print("종료하려면 Ctrl+C를 누르세요.\n")
    
    # 프로세스 모니터링 (포트 체크 방식)
    agent_ports = [8100, 8000, 8002, 8001, 8003]
    agent_names = ["Monitor", "Orchestrator", "Tool Agent", "User Agent", "Admin Agent"]
    
    print("\n[모니터링 중...]")
    print("각 agent의 로그는 logs/ 디렉토리에서 확인할 수 있습니다.\n")
    
    try:
        while True:
            # 포트를 통해 실제로 서버가 실행 중인지 확인
            running_agents = []
            for port, name in zip(agent_ports, agent_names):
                if check_port(port):
                    running_agents.append(name)
            
            # 종료된 프로세스 확인
            for i, proc in enumerate(processes):
                if proc.poll() is not None:
                    # 프로세스가 종료되었지만 포트는 여전히 열려있을 수 있음 (재시작됨)
                    pass
            
            time.sleep(5)
    except KeyboardInterrupt:
        print("\n\n[!] 종료 신호 수신...")
        signal_handler(None, None)

if __name__ == "__main__":
    main()

