@echo off
rem ============================================================
rem  Model line runner (project-local, muteki-local\labs\nyu-ctf)
rem  Usage: start_model_line.bat <gguf> <alias> <gpu-key> [port] [spec]
rem    <gpu-key>  : GPU model substring, e.g. "GeForce" (RTX 2080) or
rem                 "Tesla" (T10). Resolved via --list-devices at start,
rem                 IMMUNE to CUDA device-enumeration order changes.
rem    port       : default 18202
rem    spec       : "mtp" for draft-mtp decode (crashes on Swift gguf!)
rem  Examples:
rem    start_model_line.bat "...Swift...gguf" swift15-iq3xxs GeForce 18202
rem    start_model_line.bat "...Signal...gguf" signal38-iq3xxs Tesla 18203
rem  NOTE: the kvmem fork IGNORES CUDA_VISIBLE_DEVICES; the supported
rem        selector is --device CUDA<N> (see --list-devices).
rem ============================================================
setlocal
set "MODEL=%~1"
set "ALIAS=%~2"
set "GKEY=%~3"
set "PORT=%~4"
set "SPEC=%~5"
if "%MODEL%"=="" (echo usage: %~nx0 ^<gguf^> ^<alias^> ^<gpu-key^> [port] [mtp] & exit /b 1)
if "%ALIAS%"=="" (echo usage: %~nx0 ^<gguf^> ^<alias^> ^<gpu-key^> [port] [mtp] & exit /b 1)
if "%GKEY%"=="" (echo usage: %~nx0 ^<gguf^> ^<alias^> ^<gpu-key^> [port] [mtp] & exit /b 1)
if "%PORT%"=="" set PORT=18202

set KBIN=D:\AI\Ninfer\kvmem\kvmem-v0.16.0-rc3-windows-x86_64-cuda13\bin
set "PATH=%KBIN%;%PATH%"

rem Resolve GPU model substring -> CUDAx index via --list-devices
set "CUDAN="
"%KBIN%\llama-kvmem-server.exe" --list-devices > "%TEMP%\kvmem_devices.txt" 2>&1
for /f "tokens=1 delims=:" %%a in ('findstr /i /c:"%GKEY%" "%TEMP%\kvmem_devices.txt"') do set "CUDAN=%%a"
set "CUDAN=%CUDAN: =%
if "%CUDAN%"=="" (
    echo [model-runner] ERROR: no GPU matching "%GKEY%" found:
    type "%TEMP%\kvmem_devices.txt"
    exit /b 1
)

set SPECARGS=--spec-type none
if /i "%SPEC%"=="mtp" set SPECARGS=--spec-type draft-mtp

echo [model-runner] device=%CUDAN% key=%GKEY% port=%PORT% alias=%ALIAS% spec=%SPECARGS%

"%KBIN%\llama-kvmem-server.exe" ^
  -m "%MODEL%" ^
  --alias "%ALIAS%" ^
  --host 0.0.0.0 --port %PORT% ^
  --device %CUDAN% ^
  -c 262144 -ngl 99 ^
  --kv-dtype q8_0 -ub 128 -b 512 ^
  --kvmem-block-tokens 128 ^
  --kvmem-sink-tokens 4096 ^
  --kvmem-budget 32768 ^
  --kvmem-gen-reserve 4096 ^
  --kvmem-cpu-gb 10 ^
  --kvmem-method retrieval ^
  %SPECARGS%
rem NOTE (dual-GPU): full single-line recipe per card. WSL2/Docker memory must be
rem capped in ~/.wslconfig (memory=6GB) or 2x10GB cpu-gb + Docker will OOM (32GB RAM).
