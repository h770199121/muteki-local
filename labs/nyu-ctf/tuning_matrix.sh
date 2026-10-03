#!/usr/bin/env bash
# Tuning matrix for the unified launcher (start-model.ps1), 2026-10-01.
# Arms: single/dual x spec sweep for every on-disk model family.
# Each arm: kill all llama servers -> launch -> bench_llm (700 tok x3 median).
set -u
PS1LAUNCH="D:/AI/Qwen3.8/start-model.ps1"
KEY=$(tr -d '\r\n' < /d/AI/Qwen3.8/.api-key)
OUT=/d/AI/muteki-local/labs/nyu-ctf/tuning_matrix.txt
: > "$OUT"
cd /d/AI/muteki-local

kill_all() { powershell -NoProfile -Command "Get-CimInstance Win32_Process | Where-Object { \$_.Name -in 'llama-server.exe','llama-kvmem-server.exe' } | ForEach-Object { Stop-Process -Id \$_.ProcessId -Force }" >/dev/null 2>&1; sleep 4; }

arm() { # label model alias mode port specn benchmodel
  local label="$1" model="$2" alias="$3" mode="$4" port="$5" specn="$6" bm="$7"
  echo "=== $label ===" | tee -a "$OUT"
  kill_all
  powershell -NoProfile -Command "Start-Process -FilePath 'C:\Program Files\PowerShell\7\pwsh.exe' -ArgumentList '-NoLogo','-NoProfile','-File','$PS1LAUNCH','-ModelPath','$model','-Alias','$alias','-GpuMode','$mode','-Port','$port','-SpecN','$specn' -WindowStyle Minimized" >/dev/null 2>&1
  local ok=0
  for i in $(seq 1 90); do
    local code=$(curl -s -o /dev/null -w '%{http_code}' --max-time 4 "http://127.0.0.1:$port/health" 2>/dev/null)
    if [ "$code" = "200" ]; then ok=1; break; fi; sleep 5
  done
  if [ "$ok" != "1" ]; then echo "$label: FAILED TO START" | tee -a "$OUT"; return; fi
  BENCH_API_KEY="$KEY" BENCH_MODEL="$bm" uv run --no-project python labs/nyu-ctf/bench_llm.py "$label" "http://127.0.0.1:$port/v1/chat/completions" 700 3 2>&1 | tee -a "$OUT" | grep -E "MEDIAN|decode|prefill"
  echo "" | tee -a "$OUT"
}

Q="D:/AI/Qwen3.8/models/GGUF"   # Windows path (pwsh Resolve-Path cannot read POSIX /d/...)
arm "signal-single-K4"     "$Q/Signal/Signal-3.8-27B-AP-IQ3_XXS.gguf"                 signal-single single 18211 4 signal-single
arm "swiftmtp-dual-K3"     "$Q/IQ3_XXS/Swift-1.5-Qwen3.8-27B-GSQ-RCO-IQ3_XXS-mtp.gguf" swift15-dual dual 18212 3 swift15-dual
arm "swiftmtp-dual-K4"     "$Q/IQ3_XXS/Swift-1.5-Qwen3.8-27B-GSQ-RCO-IQ3_XXS-mtp.gguf" swift15-dual dual 18212 4 swift15-dual
arm "swiftmtp-dual-K5"     "$Q/IQ3_XXS/Swift-1.5-Qwen3.8-27B-GSQ-RCO-IQ3_XXS-mtp.gguf" swift15-dual dual 18212 5 swift15-dual
arm "basemtp-dual-K4"      "$Q/IQ3_XXS/Qwen3.8-27B-GSQ-RCO-IQ3_XXS-mtp.gguf"           base-dual dual 18215 4 base-dual
arm "bonsai-dual-none"     "D:/AI/Ninfer/models/Ternary-Bonsai-2-27B-PTQ1_0.gguf"       bonsai-dual dual 18213 none bonsai-dual
arm "occamy-dual-none"     "$Q/occamy/occamy-1.0-Q4_K_M.gguf"                          occamy-dual dual 18214 none occamy-dual

echo "=== MATRIX DONE ===" | tee -a "$OUT"
grep -E "^===|decode  =|prefill =|FAILED" "$OUT"
