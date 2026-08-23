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
    echo Install Python or start a local web server on port 8000 manually.
    pause
    exit /b 1
  )
  set "PY=python"
)

echo [KU Open DA UAT] Repository: %CD%
echo [KU Open DA UAT] Starting local server at http://127.0.0.1:8000/
start "KU Open DA Manual UAT Server" cmd /k "%PY% -m http.server 8000 --bind 127.0.0.1"
timeout /t 2 /nobreak >nul
start "" "http://127.0.0.1:8000/index.html"

echo [KU Open DA UAT] Browser opened at Public Landing.
echo [KU Open DA UAT] Keep the server window open during UAT.
echo [KU Open DA UAT] Close the server window when testing is complete.
pause
endlocal
