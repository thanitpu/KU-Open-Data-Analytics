@echo off
setlocal EnableExtensions
cd /d "%~dp0\.."
where py >nul 2>nul
if %errorlevel%==0 (set "PYTHON=py -3") else (set "PYTHON=python")
set "WORKER=%CD%\tools\run_due_sources.py"
set "TASKCMD=%PYTHON% "%WORKER%""
schtasks /Create /F /SC HOURLY /MO 1 /TN "KU2D Data Acquisition Service Worker" /TR "%TASKCMD%" >nul
if errorlevel 1 (
  echo Could not create Windows scheduled task. Try Run as administrator.
  pause
  exit /b 1
)
echo KU2D Data Acquisition Service Worker installed.
echo Windows launches it hourly; the app checks each source cadence before acquisition.
echo The browser and local web server do not need to stay open.
echo The PC, internet connection, Python, and configured repository drive must be available.
echo Re-run this installer after moving or upgrading the version folder.
pause
