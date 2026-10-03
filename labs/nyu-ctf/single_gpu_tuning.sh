#!/usr/bin/env bash
# Single-GPU tuning arms using the Signal-Full recipe (standard llama.cpp)
# on the RTX 2080, vs the KVMem baselines. bench_llm.py discipline throughout.
set -u
PS1="D:/AI/Qwen3.8/start-model.ps1"
KEY=$(tr -d '\r\n' < /d/AI/Qwen3.8/.api-key)
OUT=/d/AI/muteki-local/labs/nyu-ctf/single_gpu_tuning.txt
: > "$OUT"
cd /d/AI/muteki-local

kill_all() { powershell -NoProfile -Command "Get-CimInstance Win32_Process | Where-Object { \$_.Name -in 'llama-server.exe','llama-kvmem-server.exe' } | ForEach-Object { Stop-Process -Id \$_.ProcessId -Force }" >/dev/null 2>&1; sleep 4; }

arm() { # label model alias port specn
  local label="$1" model="$2" alias="$3" port="$4" specn="$5"
  echo "=== $label ===" | tee -a "$OUT"
  kill_all
  powershell -NoProfile -Command "Start-Process -FilePath 'C:\Program Files\PowerShell\7\pwsh.exe' -ArgumentList '-NoLogo','-NoProfile','-File','$PS1','-ModelPath','$model','-Alias','$alias','-GpuMode','single','-Port','$port','-SpecN','$specn' -WindowStyle Minimized" >/dev/null 2>&1
  local ok=0 tries=0
  while [ $tries -lt 90 ]; do
    code=$(curl -s -o /dev/null -w '%{http_code}' --max-time 4 "http://127.0.0.1:$port/health" 2>/dev/null)
    if [ "$code" = "200" ]; then ok=1; break; fi
    tries=$((tries+1)); sleep 5
  done
  if [ "$ok" != "1" ]; then echo "$label: FAILED TO START (waited $((tries*5))s)" | tee -a "$OUT"; return; fi
  BENCH_API_KEY="$KEY" BENCH_MODEL="$alias" uv run --no-project python labs/nyu-ctf/bench_llm.py "$label" "http://127.0.0.1:$port/v1/chat/completions" 700 3 2>&1 | tee -a "$OUT"
  echo "" | tee -a "$OUT"
}

Q="D:/AI/Qwen3.8/models/GGUF"
arm "signal-single-full-K4" "$Q/Signal/Signal-3.8-27B-AP-IQ3_XXS.gguf"            signal-full 18211 4
arm "swift-single-full-K5"  "$Q/IQ3_XXS/Swift-1.5-Qwen3.8-27B-GSQ-RCO-IQ3_XXS.gguf" swift-full 18212 5
arm "occamy-single-full"    "$Q/occamy/occamy-1.0-Q4_K_M.gguf"                     occamy-full 18214 none

echo "=== ARMS DONE ===" | tee -a "$OUT"
grep -E "^===|decode  =|prefill =|FAILED" "$OUT" | tail -14
