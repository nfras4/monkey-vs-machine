<#
.SYNOPSIS
  Task Scheduler wrapper around update.ps1 — adds post-logon delay + logging.

.DESCRIPTION
  Sleeps briefly so network finishes coming up after logon, then runs the
  daily tick + push as a child powershell.exe (so Write-Host output is
  captured), with stdout/stderr merged into data\tick-log\<stamp>.log.
  Designed to be invoked by the "MVM Daily Tick" scheduled task.

.PARAMETER Delay
  Seconds to sleep before running. Defaults to 30. Pass -Delay 0 for manual smoke tests.
#>
[CmdletBinding()]
param([int]$Delay = 30)

$ErrorActionPreference = "Continue"
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

$logDir = Join-Path $root "data\tick-log"
New-Item -ItemType Directory -Path $logDir -Force | Out-Null

# Prune logs older than 30 days so this doesn't grow unbounded.
Get-ChildItem -Path $logDir -Filter "*.log" -ErrorAction SilentlyContinue |
    Where-Object { $_.LastWriteTime -lt (Get-Date).AddDays(-30) } |
    Remove-Item -Force -ErrorAction SilentlyContinue

$stamp = Get-Date -Format "yyyy-MM-dd_HHmmss"
$log = Join-Path $logDir "$stamp.log"
$stdoutTmp = "$log.stdout"
$stderrTmp = "$log.stderr"

"[$stamp] scheduled-update starting (delay=${Delay}s)" |
    Out-File -FilePath $log -Encoding utf8

if ($Delay -gt 0) { Start-Sleep -Seconds $Delay }

# Run update.ps1 as a child process so Write-Host output lands in stdout
# (PowerShell only routes Write-Host to host streams in the current process,
# but a child invoked via Start-Process writes it to its own stdout).
$proc = Start-Process -FilePath "powershell.exe" `
    -ArgumentList @(
        "-ExecutionPolicy", "Bypass",
        "-NoProfile",
        "-File", "$root\update.ps1"
    ) `
    -NoNewWindow `
    -PassThru `
    -Wait `
    -RedirectStandardOutput $stdoutTmp `
    -RedirectStandardError $stderrTmp

$code = $proc.ExitCode

# Merge child output into the main log
if (Test-Path $stdoutTmp) {
    Get-Content $stdoutTmp | Out-File -FilePath $log -Append -Encoding utf8
    Remove-Item $stdoutTmp -Force
}
if (Test-Path $stderrTmp) {
    $errLines = Get-Content $stderrTmp
    if ($errLines) {
        $errLines | ForEach-Object { "[stderr] $_" } |
            Out-File -FilePath $log -Append -Encoding utf8
    }
    Remove-Item $stderrTmp -Force
}

"[$(Get-Date -Format yyyy-MM-dd_HHmmss)] scheduled-update finished (exit=$code)" |
    Out-File -FilePath $log -Append -Encoding utf8

exit $code
