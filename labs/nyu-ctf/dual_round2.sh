#!/usr/bin/env bash
# Dual-GPU tuning round 2 (codex P1/P2):
#   Part 1 — content-type K re-scan (code/zh; en already covered) at K2/K3/K4
#   Part 2 — --spec-draft-p-min sweep (0/0.2/0.4) at K4, en content
# Target: Signal dual layer-split @18210. Restarts between K arms; p-min needs
# no restart? It IS captured at graph capture -> restart per p-min value too.
set -u
PS1="D:/AI/Qwen3.8/start-signal.ps1"
KEY=$(tr -d '\r\n' < /d/AI/Qwen3.8/.api-key)
OUT=/d/AI/muteki-local/labs/nyu-ctf/dual_round2.txt
: > "$OUT"
cd /d/AI/muteki-local

kill_all() { powershell -NoProfile -Command "Get-CimInstance Win32_Process | Where-Object { \$_.Name -in 'llama-server.exe','llama-kvmem-server.exe' } | ForEach-Object { Stop-Process -Id \$_.ProcessId -Force }" >/dev/null 2>&1; sleep 4; }

launch() { # port k pmin
  powershell -NoProfile -Command "Start-Process -FilePath 'C:\Program Files\PowerShell\7\pwsh.exe' -ArgumentList '-NoLogo','-NoProfile','-File','$PS1','-Mode','Full','-DraftN','$2','-BindAddress','0.0.0.0','-Port','$1','-ApiKeyFile','D:\AI\Qwen3.8\.api-key','-PMIN','$3' -WindowStyle Minimized" >/dev/null 2>&1
}

wait_up() { for i in $(seq 1 90); do code=$(curl -s -o /dev/null -w '%{http_code}' --max-time 4 "http://127.0.0.1:$1/health" 2>/dev/null); [ "$code" = "200" ] && return 0; sleep 5; done; return 1; }

echo "### Part 1: content-type K re-scan" | tee -a "$OUT"
for K in 2 3 4; do
  kill_all
  launch 18210 "$K" 0
  wait_up 18210 || { echo "K$K: FAILED TO START" | tee -a "$OUT"; continue; }
  for CT in code zh; do
    BENCH_API_KEY="$KEY" BENCH_MODEL=qwen3.8-27b uv run --no-project python labs/nyu-ctf/bench_ct.py "K$K-$CT" "http://127.0.0.1:18210/v1/chat/completions" "$CT" 700 3 2>&1 | tee -a "$OUT" | grep -E "MEDIAN|FAILED"
  done
done

echo "### Part 2: --spec-draft-p-min sweep (K4, en)" | tee -a "$OUT"
for PM in 0 0.2 0.4; do
  kill_all
  launch 18210 4 "$PM"
  wait_up 18210 || { echo "p-min $PM: FAILED TO START" | tee -a "$OUT"; continue; }
  BENCH_API_KEY="$KEY" BENCH_MODEL=qwen3.8-27b uv run --no-project python labs/nyu-ctf/bench_llm.py "K4-pmin$PM" "http://127.0.0.1:18210/v1/chat/completions" 700 3 2>&1 | tee -a "$OUT" | grep -E "MEDIAN|FAILED"
done

echo "### ROUND2 DONE ===" | tee -a "$OUT"
