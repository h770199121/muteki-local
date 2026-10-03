#!/usr/bin/env bash
# Sweep draft-mtp K (spec-draft-n-max) on the dual-GPU line @18210.
# Discipline from the 3060 case: swap routes first, then tune params; values
# are card-specific and must be re-measured (old single-card scan said n2>n3,
# but that was a different engine/model/GPU combo — falsify first).
# Usage: bash sweep_draftn.sh 2 3 4
set -u
KEY=$(tr -d '\r\n' < /d/AI/Qwen3.8/.api-key)
RESULTS=/d/AI/muteki-local/labs/nyu-ctf/draftn_results.txt
: > "$RESULTS"
cd /d/AI/muteki-local

for N in "$@"; do
  echo "=== K=$N: (re)start dual-GPU model ===" | tee -a "$RESULTS"
  powershell -NoProfile -Command "Get-CimInstance Win32_Process | Where-Object { \$_.Name -in 'llama-server.exe','llama-kvmem-server.exe' } | ForEach-Object { Stop-Process -Id \$_.ProcessId -Force }" >/dev/null 2>&1
  sleep 4
  powershell -NoProfile -Command "Start-Process -FilePath 'D:\AI\muteki-local\labs\nyu-ctf\start_dual_18210.bat' -ArgumentList '$N' -WindowStyle Minimized"
  ok=0
  for i in $(seq 1 90); do
    code=$(curl -s -o /dev/null -w '%{http_code}' --max-time 4 http://127.0.0.1:18210/health 2>/dev/null)
    if [ "$code" = "200" ]; then ok=1; break; fi
    sleep 5
  done
  if [ "$ok" != "1" ]; then echo "K=$N: model failed to start" | tee -a "$RESULTS"; continue; fi
  BENCH_API_KEY="$KEY" BENCH_MODEL=qwen3.8-27b uv run --no-project python labs/nyu-ctf/bench_llm.py "K$N-dual" http://127.0.0.1:18210/v1/chat/completions 700 3 2>&1 | tee -a "$RESULTS"
  echo "" | tee -a "$RESULTS"
done
echo "=== ALL DONE — medians ===" | tee -a "$RESULTS"
grep -E "arm=|decode  =" "$RESULTS" | tee -a "$RESULTS"
