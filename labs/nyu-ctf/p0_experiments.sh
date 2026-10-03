#!/usr/bin/env bash
# P0 experiments from codex's PARAMETER-RESEARCH-2026-10-02 (continuation).
# Arms:
#   A: Signal single-GPU KVMem (Fast) K2          @18202
#   B: Signal single-GPU KVMem (Fast) K4          @18202
#   C: Signal single-GPU full-attn ctx 65536 K2   @18202  (start-model.ps1)
#   D: Swift-mtp single-GPU full-attn ctx 24576 K3 @18202  (start-model.ps1,
#      CORRECT -mtp artifact; fixes the wrong-file bug codex found)
set -u
KEY=$(tr -d '\r\n' < /d/AI/Qwen3.8/.api-key)
OUT=/d/AI/muteki-local/labs/nyu-ctf/p0_experiments.txt
: > "$OUT"
cd /d/AI/muteki-local

kill_all() { powershell -NoProfile -Command "Get-CimInstance Win32_Process | Where-Object { \$_.Name -in 'llama-server.exe','llama-kvmem-server.exe' } | ForEach-Object { Stop-Process -Id \$_.ProcessId -Force }" >/dev/null 2>&1; sleep 4; }

bench() { # label port model
  BENCH_API_KEY="$KEY" BENCH_MODEL="$2" uv run --no-project python labs/nyu-ctf/bench_llm.py "$1" "http://127.0.0.1:$2/v1/chat/completions" 700 3 2>&1 | tee -a "$OUT" | grep -E "MEDIAN|decode|prefill|FAILED"
  echo "" | tee -a "$OUT"
}

wait_up() { for i in $(seq 1 60); do code=$(curl -s -o /dev/null -w '%{http_code}' --max-time 4 "http://127.0.0.1:$1/health" 2>/dev/null); [ "$code" = "200" ] && return 0; sleep 5; done; return 1; }

SIG="D:/AI/Qwen3.8/models/GGUF/Signal/Signal-3.8-27B-AP-IQ3_XXS.gguf"
SWIFTMTP="D:/AI/Qwen3.8/models/GGUF/IQ3_XXS/Swift-1.5-Qwen3.8-27B-GSQ-RCO-IQ3_XXS-mtp.gguf"

echo "### Arm A: Signal KVMem K2 (codex P0-1)" | tee -a "$OUT"
kill_all
powershell -NoProfile -Command "Start-Process -FilePath 'C:\Program Files\PowerShell\7\pwsh.exe' -ArgumentList '-NoLogo','-NoProfile','-File','D:\AI\Qwen3.8\start-signal.ps1','-Mode','Fast','-DraftN','2','-Port','18202','-BindAddress','0.0.0.0' -WindowStyle Minimized" >/dev/null 2>&1
if wait_up 18202; then bench "A-signal-kvmem-K2" 18202 qwen3.8-27b; else echo "Arm A: FAILED TO START" | tee -a "$OUT"; fi

echo "### Arm B: Signal KVMem K4 (codex P0-1)" | tee -a "$OUT"
kill_all
powershell -NoProfile -Command "Start-Process -FilePath 'C:\Program Files\PowerShell\7\pwsh.exe' -ArgumentList '-NoLogo','-NoProfile','-File','D:\AI\Qwen3.8\start-signal.ps1','-Mode','Fast','-DraftN','4','-Port','18202','-BindAddress','0.0.0.0' -WindowStyle Minimized" >/dev/null 2>&1
if wait_up 18202; then bench "B-signal-kvmem-K4" 18202 qwen3.8-27b; else echo "Arm B: FAILED TO START" | tee -a "$OUT"; fi

echo "### Arm C: Signal full-attn ctx 65536 K2 (codex P0-2)" | tee -a "$OUT"
kill_all
powershell -NoProfile -Command "Start-Process -FilePath 'C:\Program Files\PowerShell\7\pwsh.exe' -ArgumentList '-NoLogo','-NoProfile','-File','D:\AI\Qwen3.8\start-model.ps1','-ModelPath','$SIG','-Alias','signal-64k','-GpuMode','single','-Port','18202','-SpecN','2','-ContextSize','65536' -WindowStyle Minimized" >/dev/null 2>&1
if wait_up 18202; then bench "C-signal-full-64k-K2" 18202 signal-64k; else echo "Arm C: FAILED TO START" | tee -a "$OUT"; fi

echo "### Arm D: Swift-mtp full-attn ctx 24576 K3 (codex P0-3, correct artifact)" | tee -a "$OUT"
kill_all
powershell -NoProfile -Command "Start-Process -FilePath 'C:\Program Files\PowerShell\7\pwsh.exe' -ArgumentList '-NoLogo','-NoProfile','-File','D:\AI\Qwen3.8\start-model.ps1','-ModelPath','$SWIFTMTP','-Alias','swift-mtp','-GpuMode','single','-Port','18202','-SpecN','3','-ContextSize','24576' -WindowStyle Minimized" >/dev/null 2>&1
if wait_up 18202; then bench "D-swift-mtp-24k-K3" 18202 swift-mtp; else echo "Arm D: FAILED TO START" | tee -a "$OUT"; fi

echo "### P0 DONE ===" | tee -a "$OUT"
grep -E "^###|decode  =|prefill =|FAILED" "$OUT"
