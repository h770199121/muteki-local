@echo off
setlocal EnableDelayedExpansion
cd /d "%~dp0"

echo =====================================================
echo  Muteki-Local - stopping everything (compose + local models)
echo =====================================================

docker info >nul 2>&1
if errorlevel 1 (
    echo [WARN] Docker engine not reachable - containers may already be down.
) else (
    docker compose down
    if errorlevel 1 (
        echo [ERROR] docker compose down failed.
        pause
        exit /b 1
    )
    echo [OK] Muteki-Local containers stopped and removed.
)

rem ---- stop ALL local model lines (they are VRAM-exclusive anyway) ----
rem 18202 Swift-1.5 / 18200 Bonsai / 8888 IQ3_S-Signal (KVMem) + 8890 Occamy
powershell -NoProfile -Command "Get-CimInstance Win32_Process | Where-Object { $_.Name -in 'llama-kvmem-server.exe','llama-server.exe' } | ForEach-Object { Write-Output ('[OK] Stopping model process ' + $_.ProcessId + ' (' + $_.Name + ')'); Stop-Process -Id $_.ProcessId -Force }"

echo.
echo [OK] Muteki-Local fully stopped.
echo     Data is kept in D:\AI\muteki-local\data
echo     Next start: start.bat (brings up Docker, model line B/Swift and the swarm)
echo.
pause
