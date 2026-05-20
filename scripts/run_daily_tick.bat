@echo off
REM Daily tick wrapper for Windows Task Scheduler.
REM
REM Reads PAGES_URL + MVM_INGEST_TOKEN from a gitignored sibling file:
REM   scripts\secrets.env
REM
REM Format of that file (one KEY=VALUE per line, no quotes):
REM   PAGES_URL=https://mvm-dashboard.pages.dev
REM   MVM_INGEST_TOKEN=<64-char hex token>

cd /d D:\claudecode\monkey-vs-machine

REM Load env vars from secrets.env if present (otherwise D1 push is skipped silently).
if exist scripts\secrets.env (
    for /F "usebackq tokens=1,* delims==" %%a in ("scripts\secrets.env") do (
        if not "%%a"=="" if not "%%a:~0,1%"=="#" set %%a=%%b
    )
)

python scripts\run_tick.py >> data\tick.log 2>&1
if errorlevel 1 (
    echo [%date% %time%] tick failed with errorlevel %errorlevel% >> data\tick.log
    exit /b 1
)

REM D1 push: only runs if PAGES_URL + MVM_INGEST_TOKEN were loaded above.
if defined MVM_INGEST_TOKEN (
    python scripts\push_to_d1.py >> data\tick.log 2>&1
)

exit /b 0
