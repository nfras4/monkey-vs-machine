@echo off
REM Daily tick wrapper for Windows Task Scheduler.
REM
REM For M1 (laptop-only): just runs the tick. No D1 push.
REM For M2 (after wrangler is set up): uncomment the push_to_d1 lines and
REM populate PAGES_URL and MVM_INGEST_TOKEN below.

cd /d D:\claudecode\monkey-vs-machine

REM === M2 only: D1 publish env vars (left blank for M1) ===
REM set PAGES_URL=https://mvm-dashboard.pages.dev
REM set MVM_INGEST_TOKEN=replace-with-real-token

python scripts\run_tick.py >> data\tick.log 2>&1
if errorlevel 1 (
    echo [%date% %time%] tick failed with errorlevel %errorlevel% >> data\tick.log
    exit /b 1
)

REM === M2 only: push aggregates to D1 ===
REM python scripts\push_to_d1.py >> data\tick.log 2>&1

exit /b 0
