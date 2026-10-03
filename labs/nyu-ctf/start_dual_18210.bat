@echo off
rem ============================================================
rem  Dual-GPU model launcher @18210 (called by start.bat dual)
rem  Signal-3.8-27B layer-split across RTX 2080 + Tesla T10,
rem  standard llama.cpp + draft-mtp, ref: start-server-signal-full.bat
rem  Usage: start_dual_18210.bat [draft-n]
rem
rem  DEFAULT CHANGED 4 -> 2 on 2026-10-03. Read before editing.
rem  The old K4 default came from the 700-token RECITATION bench
rem  (sweep 2026-10-01: K2=31.0, K3=34.9, K4=38.1, K5=37.5, K6=36.6).
rem  That protocol does NOT represent this box's real workload.
rem  Original-generation protocol (thinking off, 3x median, 131072):
rem    K2 = 23.4 essay / 28.8 code / 26.0 zh   <- best overall  (default now)
rem    K3 = 22.0 essay / 29.6 code / 26.2 zh   <- best for code-heavy work
rem    K4 = 19.8 essay / 26.1 code / 24.3 zh   <- 15% SLOWER than K2
rem  This box runs CTF / agent tasks, i.e. generation, so K2 is the default.
rem  Pass an explicit argument to override, e.g. start_dual_18210.bat 3
rem  for code-heavy runs. Verify the banner prints "MTP <n>" after changing.
rem ============================================================
set "DRAFTN=%~1"
if "%DRAFTN%"=="" set DRAFTN=2
"C:\Program Files\PowerShell\7\pwsh.exe" -NoLogo -NoProfile -Command "& 'D:\AI\Qwen3.8\start-signal.ps1' -Mode Full -BindAddress 0.0.0.0 -Port 18210 -ApiKeyFile 'D:\AI\Qwen3.8\.api-key' -DraftN %DRAFTN%"
exit /b %errorlevel%
