param(
    [string]$ProjectDir = "D:\ai-council"
)

$ErrorActionPreference = "Stop"
$EnvFile = Join-Path $env:USERPROFILE ".config\ai-council\.env"
$LogDir = Join-Path $ProjectDir "logs"
$StateDir = Join-Path $ProjectDir "state"
$PidFile = Join-Path $StateDir "shortcuts_listener.pid"

function Import-AiCouncilEnv {
    param([string]$Path)
    if (-not (Test-Path $Path)) {
        return
    }
    foreach ($line in Get-Content $Path) {
        if ($line -match '^\s*#') {
            continue
        }
        if ($line -match '^\s*([^=]+?)\s*=\s*(.*)\s*$') {
            $name = $matches[1].Trim()
            $value = $matches[2].Trim()
            if (($value.StartsWith('"') -and $value.EndsWith('"')) -or ($value.StartsWith("'") -and $value.EndsWith("'"))) {
                $value = $value.Substring(1, $value.Length - 2)
            }
            [Environment]::SetEnvironmentVariable($name, $value, "Process")
        }
    }
}

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

Import-AiCouncilEnv -Path $EnvFile

$HostName = $env:AI_COUNCIL_SHORTCUT_HOST
if (-not $HostName) {
    $HostName = "127.0.0.1"
}
$Port = $env:AI_COUNCIL_SHORTCUT_PORT
if (-not $Port) {
    $Port = "8788"
}

$pidBackedProcess = Get-ShortcutProcessFromPidFile -Path $PidFile
$running = @()
if ($pidBackedProcess) {
    $running = @($pidBackedProcess)
}
$scanCandidates = Get-CimInstance Win32_Process |
    Where-Object { $_.CommandLine -and $_.CommandLine.Contains("ai_council.py") -and $_.CommandLine.Contains("serve-shortcuts") }

Write-Host "Bartek AI Council Shortcuts"
Write-Host "Token: $(if ($env:AI_COUNCIL_SHORTCUT_TOKEN) { 'configured' } else { 'missing' })"
Write-Host "Endpoint: http://$HostName`:$Port/shortcut"
Write-Host "PidFile: $PidFile"
Write-Host "Logs: $(Join-Path $LogDir 'shortcuts.log')"
Write-Host "Errors: $(Join-Path $LogDir 'shortcuts.err.log')"

if ($running) {
    Write-Host "State: Running"
    $running | Select-Object ProcessId, CommandLine
} else {
    Write-Host "State: Stopped"
    if ($scanCandidates) {
        Write-Host "ScanCandidates: found process-like command lines without a trusted PID file"
        $scanCandidates | Select-Object ProcessId, CommandLine
    }
}
