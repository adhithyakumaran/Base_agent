@echo off
REM Start QA orchestrator from repo root on Windows
cd /d "%~dp0.."
set PYTHONPATH=src;.
if exist .env (
  for /f "usebackq tokens=1,* delims==" %%a in (".env") do (
    set "line=%%a"
    if not "!line:~0,1!"=="#" (
      set "%%a=%%b"
    )
  )
)
set QA_AUTOMATION_DIR=%CD%\automation
set QA_RUNNER=playwright
echo Repo: %CD%
echo Automation: %QA_AUTOMATION_DIR%
python scripts\check_setup.py
if errorlevel 1 (
  echo.
  echo Setup check failed. Fix issues above before starting server.
  pause
  exit /b 1
)
echo.
echo Starting agent on http://127.0.0.1:43124 ...
python scripts\local_agent_server.py --host 127.0.0.1 --port 43124
pause
