param(
    [string]$ProjectDir = "D:\ai-council",
    [switch]$AllowScanFallback
)

$ErrorActionPreference = "Stop"
$StateDir = Join-Path $ProjectDir "state"
$PidFile = Join-Path $StateDir "shortcuts_listener.pid"

function Get-ShortcutProcessFromPidFile {
    param([string]$Path)
    if (-not (Test-Path $Path)) {
        return $null
    }
    $pidText = Get-Content -Path $Path -ErrorAction SilentlyContinue | Select-Object -First 1
    $shortcutPid = 0
    if (-not [int]::TryParse([string]$pidText, [ref]$shortcutPid)) {
        return $null
    }
    $process = Get-CimInstance Win32_Process -Filter "ProcessId = $shortcutPid" -ErrorAction SilentlyContinue
    if ($process -and $process.CommandLine -and $process.CommandLine.Contains("ai_council.py") -and $process.CommandLine.Contains("serve-shortcuts")) {
        return $process
    }
    return $null
}

$pidBackedProcess = Get-ShortcutProcessFromPidFile -Path $PidFile
$running = @()
if ($pidBackedProcess) {
    $running = @($pidBackedProcess)
} elseif ($AllowScanFallback) {
    $running = Get-CimInstance Win32_Process |
        Where-Object { $_.CommandLine -and $_.CommandLine.Contains("ai_council.py") -and $_.CommandLine.Contains("serve-shortcuts") }
}

if (-not $running) {
    Write-Host "Shortcuts service is not running."
    if (Test-Path $PidFile) {
        Remove-Item $PidFile -Force
    }
    if (-not $AllowScanFallback) {
        $scanCandidates = Get-CimInstance Win32_Process |
            Where-Object { $_.CommandLine -and $_.CommandLine.Contains("ai_council.py") -and $_.CommandLine.Contains("serve-shortcuts") }
        if ($scanCandidates) {
            Write-Host "Scan candidates exist but were not stopped. Re-run with -AllowScanFallback if this is an orphaned Shortcuts process."
            $scanCandidates | Select-Object ProcessId, CommandLine
        }
    }
    exit 0
}

foreach ($process in $running) {
    Write-Host "Stopping PID $($process.ProcessId)"
    Stop-Process -Id $process.ProcessId -ErrorAction SilentlyContinue
    Start-Sleep -Seconds 2
    $stillRunning = Get-CimInstance Win32_Process -Filter "ProcessId = $($process.ProcessId)" -ErrorAction SilentlyContinue
    if ($stillRunning) {
        Stop-Process -Id $process.ProcessId -Force
    }
}

if (Test-Path $PidFile) {
    Remove-Item $PidFile -Force
}

Write-Host "Shortcuts service stopped."
