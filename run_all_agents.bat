@echo off
REM Windows용 A2A Agent 실행 스크립트

echo ============================================================
echo A2A Agent System 시작
echo ============================================================
echo.
echo 모니터링 대시보드: http://127.0.0.1:8100/dashboard
echo.
echo 종료하려면 각 창에서 Ctrl+C를 누르거나 창을 닫으세요.
echo.

start "Monitor" cmd /k "python -m monitor.monitor"
timeout /t 2 /nobreak >nul

start "Orchestrator" cmd /k "python -m agents.orchestrator"
timeout /t 2 /nobreak >nul

start "Tool Agent" cmd /k "python -m agents.tool_agent"
timeout /t 2 /nobreak >nul

start "User Agent" cmd /k "python -m agents.user_agent"
timeout /t 2 /nobreak >nul

start "Admin Agent" cmd /k "python -m agents.admin_agent"
timeout /t 2 /nobreak >nul

echo.
echo ============================================================
echo 모든 agent가 시작되었습니다!
echo ============================================================
echo.
echo 실시간 모니터링: http://127.0.0.1:8100/dashboard
echo.
pause

