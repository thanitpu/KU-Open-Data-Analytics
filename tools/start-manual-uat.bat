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

echo [KU Open DA UAT] Starting Public/Product web server at http://127.0.0.1:8000/
start "KU Open DA Manual UAT Web" cmd /k "%PY% -m http.server 8000 --bind 127.0.0.1"

timeout /t 4 /nobreak >nul
start "" "http://127.0.0.1:8000/index.html"

echo.
echo [KU Open DA UAT] Browser opened at Public Landing.
echo [KU Open DA UAT] Local frontend : http://127.0.0.1:8000/
echo [KU Open DA UAT] Local FastAPI  : http://127.0.0.1:8001/
echo [KU Open DA UAT] Keep BOTH server windows open during UAT.
echo [KU Open DA UAT] The Product automatically uses port 8001 when opened from localhost/127.0.0.1.
echo [KU Open DA UAT] Close both server windows when testing is complete.
pause
endlocal
