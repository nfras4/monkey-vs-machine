#requires -Version 5.1
<#
.SYNOPSIS
  One-command daily tick + push for monkey-vs-machine.

.DESCRIPTION
  Loads PAGES_URL + MVM_INGEST_TOKEN from scripts\secrets.env, runs the catchup
  script from the day after the last ok tick (or 7 days ago if the DB is empty),
  POSTs each newly-completed tick to the D1 ingest endpoint, then prints today's
  AI picks and a one-line race snapshot.

.PARAMETER DbPath
  Path to the source-of-truth SQLite. Defaults to data\state.db.

.PARAMETER Secrets
  Path to the env file. Defaults to scripts\secrets.env.

.PARAMETER FallbackSinceDays
  When the DB has no prior ok-ticks, how many days back to start catchup. Default 7.

.EXAMPLE
  .\update.ps1
#>
[CmdletBinding()]
param(
    [string]$DbPath = "data\state.db",
    [string]$Secrets = "scripts\secrets.env",
    [int]$FallbackSinceDays = 7
)

$ErrorActionPreference = "Stop"
Set-Location -Path $PSScriptRoot

function Write-Section($msg) {
    Write-Host ""
    Write-Host "-- $msg --" -ForegroundColor Cyan
}

function Fail($msg) {
    Write-Host "FAIL: $msg" -ForegroundColor Red
    exit 1
}

# ---- Load secrets ----------------------------------------------------------
if (-not (Test-Path $Secrets)) {
    Fail "Missing $Secrets. Create it with PAGES_URL=... and MVM_INGEST_TOKEN=..."
}
Get-Content $Secrets | ForEach-Object {
    if ($_ -match '^\s*#') { return }
    if ($_ -match '^\s*([A-Z_][A-Z0-9_]*)\s*=\s*(.+?)\s*$') {
        Set-Item -Path "env:$($Matches[1])" -Value $Matches[2]
    }
}
if (-not $env:PAGES_URL -or -not $env:MVM_INGEST_TOKEN) {
    Fail "PAGES_URL and MVM_INGEST_TOKEN must both be set in $Secrets"
}

if (-not (Test-Path $DbPath)) {
    Fail "No state DB at $DbPath. Run scripts\bootstrap_genesis.py first."
}

# ---- Find catchup window ---------------------------------------------------
Write-Section "Lineage state"
$lastOk = (& python scripts\update_helpers.py --db $DbPath last_ok_date).Trim()
if ($LASTEXITCODE -ne 0) { Fail "update_helpers.py last_ok_date exited $LASTEXITCODE" }

if ([string]::IsNullOrWhiteSpace($lastOk)) {
    $since = (Get-Date).AddDays(-$FallbackSinceDays).ToString("yyyy-MM-dd")
    Write-Host "  No prior ticks. Catching up from $since."
}
else {
    $since = ([datetime]::ParseExact($lastOk, "yyyy-MM-dd", $null)).AddDays(1).ToString("yyyy-MM-dd")
    Write-Host "  Last ok tick: $lastOk. Catching up from $since."
}

$beforeJson = & python scripts\update_helpers.py --db $DbPath ok_dates
$existingBefore = @(($beforeJson | ConvertFrom-Json))

# ---- Catchup ---------------------------------------------------------------
Write-Section "Catchup"
& python scripts\catchup.py --since $since
if ($LASTEXITCODE -ne 0) { Fail "catchup.py exited $LASTEXITCODE" }

$afterJson = & python scripts\update_helpers.py --db $DbPath ok_dates
$existingAfter = @(($afterJson | ConvertFrom-Json))
$newDates = @($existingAfter | Where-Object { $existingBefore -notcontains $_ })

if ($newDates.Count -eq 0) {
    Write-Host "  Nothing new. Already up to date."
    Write-Host ""
    Write-Host "OK done. Last tick: $lastOk" -ForegroundColor Green
    exit 0
}

Write-Host "  $($newDates.Count) new tick(s): $($newDates -join ', ')"

# ---- Push each new tick to D1 ---------------------------------------------
Write-Section "Push to D1"
foreach ($d in $newDates) {
    Write-Host "  -> $d"
    & python scripts\push_to_d1.py --date $d
    if ($LASTEXITCODE -ne 0) { Fail "push_to_d1.py for $d exited $LASTEXITCODE" }
}

# ---- Readout --------------------------------------------------------------
$latest = $newDates[-1]
Write-Section "Today's AI picks ($latest)"
& python scripts\update_helpers.py --db $DbPath picks --date $latest

Write-Section "Race snapshot"
& python scripts\update_helpers.py --db $DbPath snapshot --date $latest

Write-Host ""
Write-Host "OK $($newDates.Count) tick(s) shipped to mvm-dashboard.pages.dev. Last: $latest" -ForegroundColor Green
