#!/bin/bash
set -e

echo "[1] Launching monitor..."
uvicorn monitor.monitor:app --port 8100 &
sleep 2

echo "[2] Launching tool agent..."
uvicorn agents.tool_agent:app --port 8002 &
sleep 2

echo "[3] Launching orchestrator..."
uvicorn agents.orchestrator:app --port 8000 &
sleep 2

echo "[4] Running user agent..."
python -m agents.user_agent

echo "[5] Generating trust plot..."
python tools/plot_trust.py
