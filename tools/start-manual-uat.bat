@echo off
setlocal
cd /d "%~dp0.."

where py >nul 2>&1
if %errorlevel%==0 (
  set "PY=py"
) else (
  where python >nul 2>&1
  if %errorlevel% neq 0 (
    echo [KU Open DA UAT] Python was not found on PATH.
    echo Install Python, then run this launcher again.
    pause
    exit /b 1
  )
  set "PY=python"
)

echo [KU Open DA UAT] Repository: %CD%
echo [KU Open DA UAT] Checking local backend dependencies...
%PY% -c "import fastapi,uvicorn,pandas,numpy,sklearn,scipy,statsmodels,xgboost,multipart" >nul 2>&1
if %errorlevel% neq 0 (
  echo [KU Open DA UAT] Installing backend requirements for local UAT...
  %PY% -m pip install -r backend\requirements.txt
  if %errorlevel% neq 0 (
    echo [KU Open DA UAT] Backend dependency installation failed.
    pause
    exit /b 1
  )
)

echo [KU Open DA UAT] Starting local FastAPI at http://127.0.0.1:8001/
start "KU Open DA Local FastAPI" cmd /k "%PY% -m uvicorn app.api:app --app-dir backend --host 127.0.0.1 --port 8001"

echo [KU Open DA UAT] Starting NO-CACHE Public/Product server at http://127.0.0.1:8000/
start "KU Open DA Manual UAT Web" cmd /k "%PY% tools\uat_static_server.py"

echo [KU Open DA UAT] Verifying /health, /capabilities and browser-origin CORS...
%PY% tools\uat_preflight.py
if %errorlevel% neq 0 (
  echo.
  echo [KU Open DA UAT] Preflight failed. Do not continue UAT yet.
  echo Check the Local FastAPI window for errors, then run this launcher again.
  pause
  exit /b 1
)

start "" "http://127.0.0.1:8000/index.html?uat=20260825b"

echo.
echo [KU Open DA UAT] PRE-FLIGHT PASS. Browser opened at Public Landing.
echo [KU Open DA UAT] Local frontend : http://127.0.0.1:8000/
echo [KU Open DA UAT] Local FastAPI  : http://127.0.0.1:8001/
echo [KU Open DA UAT] API check      : http://127.0.0.1:8001/capabilities
echo [KU Open DA UAT] Keep BOTH server windows open during UAT.
echo [KU Open DA UAT] Frontend responses disable browser caching for this test session.
echo [KU Open DA UAT] Close both server windows when testing is complete.
pause
endlocal
