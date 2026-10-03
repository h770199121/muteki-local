@echo off
setlocal EnableDelayedExpansion
cd /d "%~dp0"

rem ============================================================
rem  Muteki-Local unified launcher (2026-10-03, ASCII-only)
rem  Pick model -> pick single/dual -> auto switch_line + compose.
rem  Speeds: bench_llm.py (1128/700 x3 median) on 2080 + T10.
rem  draft-n defaults are measured sweet spots per model AND mode.
rem
rem  Model / mode         decode t/s       prefill t/s
rem  Swift-mtp  single    26.4 (K3)        386
rem  Swift-mtp  dual      35.0 (K5)        516
rem  Signal     single    36.2 (K4)        410
rem  Signal     dual      40.7 (K4)        588
rem  Occamy     dual      60.2             1591   (fastest)
rem  Bonsai     single    20.8             239
rem  base-mtp   dual      33.1 (K4)        516
rem  base-mtp   single    ~26 est (K3)     ~386   (untested)
rem ============================================================

echo =====================================================
echo   Muteki-Local - pick a model
echo =====================================================
echo.
echo  [1] Swift-1.5-mtp   single 26.4 (K3) / dual 35.0 (K5)  prefill 386-516
echo  [2] Signal          single 36.2 (K4) / dual 40.7 (K4)  prefill 410-588
echo  [3] Occamy Q4_K_M   DUAL ONLY  60.2                    prefill 1591
echo  [4] Bonsai PTQ1_0   SINGLE ONLY  20.8                  prefill 239
echo  [5] base-mtp        single ~26 est (K3) / dual 33.1 (K4)
echo.
set /p MODEL_CHOICE="Select model [1-5]: "

set "MODEL="
set "ALIAS="
set "GPUMODE="
set "PORT="
set "CTX="
set "SPECN=none"
set "LINE="

if "%MODEL_CHOICE%"=="1" (
    set "MODEL=D:\AI\Qwen3.8\models\GGUF\IQ3_XXS\Swift-1.5-Qwen3.8-27B-GSQ-RCO-IQ3_XXS-mtp.gguf"
    set "ALIAS=swift15-iq3xxs"
    set "GPUMODE=single"
    set "PORT=18202"
    set "CTX=24576"
    set "SPECN=3"
    set "LINE=X2"
)
if "%MODEL_CHOICE%"=="2" (
    set "MODEL=D:\AI\Qwen3.8\models\GGUF\Signal\Signal-3.8-27B-AP-IQ3_XXS.gguf"
    set "ALIAS=signal38-iq3xxs"
    set "GPUMODE=dual"
    set "PORT=18210"
    set "SPECN=4"
    set "LINE=FULL"
)
if "%MODEL_CHOICE%"=="3" (
    set "MODEL=D:\AI\Qwen3.8\models\GGUF\occamy\occamy-1.0-Q4_K_M.gguf"
    set "ALIAS=occamy-1.0"
    set "GPUMODE=dual"
    set "PORT=18214"
    set "CTX=131072"
    set "SPECN=none"
    set "LINE=C"
)
if "%MODEL_CHOICE%"=="4" (
    set "MODEL=D:\AI\Ninfer\models\Ternary-Bonsai-2-27B-PTQ1_0.gguf"
    set "ALIAS=Ternary-Bonsai-2-27B-PTQ1_0.gguf"
    set "GPUMODE=single"
    set "PORT=18200"
    set "CTX=262144"
    set "SPECN=none"
    set "LINE=B"
)
if "%MODEL_CHOICE%"=="5" (
    set "MODEL=D:\AI\Qwen3.8\models\GGUF\IQ3_XXS\Qwen3.8-27B-GSQ-RCO-IQ3_XXS-mtp.gguf"
    set "ALIAS=base-mtp-iq3xxs"
    set "GPUMODE=dual"
    set "PORT=18215"
    set "CTX=131072"
    set "SPECN=4"
    set "LINE=BM2"
)
if "%MODEL_CHOICE%"=="" (
    echo [ERROR] invalid selection.
    pause
    exit /b 1
)

rem ---- GPU mode (goto-flow; set /p never inside parenthesized blocks) ----
if "%MODEL_CHOICE%"=="2" goto :mode_signal
if "%MODEL_CHOICE%"=="1" goto :mode_swift
if "%MODEL_CHOICE%"=="5" goto :mode_base
goto :mode_done

:mode_signal
echo  Signal mode: [1] single KVMem K4 36.2 t/s   [2] dual Full K4 40.7 t/s
set /p GPU_CHOICE="Select 1 or 2, default 2 dual: "
if "%GPU_CHOICE%"=="1" (
    set "GPUMODE=single"
    set "PORT=18202"
    set "LINE=X3"
)
if not "%GPUMODE%"=="single" set "GPUMODE=dual"
goto :mode_done

:mode_swift
echo  Swift-mtp mode: [1] single K3 26.4 t/s   [2] dual K5 35.0 t/s
set /p GPU_CHOICE="Select 1 or 2, default 1 single: "
if "%GPU_CHOICE%"=="2" (
    set "GPUMODE=dual"
    set "PORT=18212"
    set "CTX=131072"
    set "SPECN=5"
    set "LINE=X2D"
)
goto :mode_done

:mode_base
echo  base-mtp mode: [1] single K3 est ~26 t/s (UNVERIFIED)   [2] dual K4 33.1 t/s
set /p GPU_CHOICE="Select 1 or 2, default 2 dual: "
if "%GPU_CHOICE%"=="1" (
    set "GPUMODE=single"
    set "PORT=18202"
    set "CTX=24576"
    set "SPECN=3"
    set "LINE=BM"
)
goto :mode_done

:mode_done
echo =====================================================
echo  Starting: %ALIAS% ^| %GPUMODE% ^| port %PORT% ^| spec %SPECN% ^| ctx %CTX% ^| line %LINE%
echo =====================================================

rem ---- 1) Docker ----
docker info >nul 2>&1
if errorlevel 1 (
    echo [..] Docker not running - starting Docker Desktop ...
    start "" "C:\Program Files\Docker\Docker\Docker Desktop.exe"
    set /a docker_waits=0
)
:waitdocker
docker info >nul 2>&1
if errorlevel 1 (
    set /a docker_waits+=1
    if !docker_waits! geq 36 (
        echo [ERROR] Docker engine not ready after ~3 min.
        goto :fail
    )
    ping -n 6 127.0.0.1 >nul
    goto :waitdocker
)
echo [OK] Docker engine is up.

rem ---- 2) Model (VRAM-exclusive: stop all llama processes first) ----
powershell -NoProfile -Command "Get-CimInstance Win32_Process | Where-Object { $_.Name -in 'llama-server.exe','llama-kvmem-server.exe' } | ForEach-Object { Write-Output ('[OK] Stopped old model process ' + $_.ProcessId); Stop-Process -Id $_.ProcessId -Force }"
ping -n 4 127.0.0.1 >nul
echo [..] Launching model minimized ...

rem Signal single optimum = KVMem Fast K4 (port 18202, own launcher);
rem Signal dual optimum = Full layer-split 262K (18210 wrapper).
if "%MODEL_CHOICE%"=="2" if "%GPUMODE%"=="single" (
    powershell -NoProfile -Command "Start-Process -FilePath 'C:\Program Files\PowerShell\7\pwsh.exe' -ArgumentList '-NoLogo','-NoProfile','-File','D:\AI\Qwen3.8\start-signal.ps1','-Mode','Fast','-DraftN','4','-ModelAlias','%ALIAS%','-Port','%PORT%','-BindAddress','0.0.0.0' -WindowStyle Minimized"
    goto :waitmodel
)
if "%MODEL_CHOICE%"=="2" if "%GPUMODE%"=="dual" (
    powershell -NoProfile -Command "Start-Process -FilePath 'D:\AI\muteki-local\labs\nyu-ctf\start_dual_18210.bat' -WindowStyle Minimized"
    goto :waitmodel
)
rem Bonsai single optimum = KVMem (18200) via card-bound launcher
if "%MODEL_CHOICE%"=="4" (
    powershell -NoProfile -Command "Start-Process -FilePath 'D:\AI\muteki-local\labs\nyu-ctf\start_model_line.bat' -ArgumentList '\"%MODEL%\"','%ALIAS%','GeForce','%PORT%' -WindowStyle Minimized"
    goto :waitmodel
)
rem generic: standard engine via start-model.ps1
powershell -NoProfile -Command "Start-Process -FilePath 'C:\Program Files\PowerShell\7\pwsh.exe' -ArgumentList '-NoLogo','-NoProfile','-File','D:\AI\Qwen3.8\start-model.ps1','-ModelPath','%MODEL%','-Alias','%ALIAS%','-GpuMode','%GPUMODE%','-Port','%PORT%','-SpecN','%SPECN%','-ContextSize','%CTX%' -WindowStyle Minimized"

set /a model_waits=0
:waitmodel
%SystemRoot%\System32\curl.exe -sf -o nul -m 6 http://localhost:%PORT%/health
if errorlevel 1 (
    set /a model_waits+=1
    if !model_waits! geq 90 (
        echo [ERROR] Model @%PORT% still down after ~7 min. Check the minimized model window.
        goto :fail
    )
    ping -n 6 127.0.0.1 >nul
    goto :waitmodel
)
echo [OK] Model is up (localhost:%PORT%, %ALIAS%).

rem ---- 3) point the swarm at this model ----
uv run --no-project python D:\AI\muteki-local\labs\nyu-ctf\switch_line.py --line %LINE% 2>nul || echo [WARN] switch_line %LINE% failed - set swarm endpoint manually.

rem ---- 4) Control plane ----
docker compose up -d
if errorlevel 1 (
    echo [ERROR] docker compose up failed.
    goto :fail
)
echo.
echo [..] Waiting for backend on :8010 ...
set /a tries=0
:waitapi
ping -n 4 127.0.0.1 >nul
set /a tries+=1
%SystemRoot%\System32\curl.exe -sf -o nul -m 3 http://localhost:8010/api/health
if errorlevel 1 (
    if !tries! lss 25 goto waitapi
    echo [WARN] Backend not up within ~100s. Check: docker compose logs web-api
    goto :status
)
echo [OK] Backend is healthy.

:status
echo.
docker compose ps
set "WEBPASS="
for /f "usebackq tokens=1* delims==" %%a in ("%~dp0.env") do (
    if /i "%%a"=="MUTEKI_WEB_PASSWORD" set "WEBPASS=%%b"
)
if defined WEBPASS echo !WEBPASS!|clip
echo.
echo ============================================
echo  Web UI   : http://localhost:3011
echo  API      : http://localhost:8010/docs
if defined WEBPASS (
    echo  Password : !WEBPASS!  ^(copied^)
)
echo  Model    : %ALIAS% ^| %GPUMODE% ^| port %PORT% ^| spec %SPECN%
echo  Swarm    : line %LINE%
echo  Logs     : docker compose logs -f
echo ============================================
echo.
echo Keep this window open, or press a key to close (services keep running).
pause >nul
exit /b 0

:fail
echo.
echo [FAILED] Start aborted - read the last error above.
pause
exit /b 1
