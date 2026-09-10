@echo off
REM Start QA orchestrator from repo root on Windows
cd /d "%~dp0.."
set PYTHONPATH=services\agent-runtime;services\qa-orchestrator;.
set QA_DISCOVERY_ROOT=data\discovery-kb
set QA_AUTOMATION_DIR=%CD%\apps\automation
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
