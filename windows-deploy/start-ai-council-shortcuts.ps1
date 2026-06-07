param(
    [string]$ProjectDir = "D:\ai-council",
    [string]$HostName = "",
    [int]$Port = 0
)

$ErrorActionPreference = "Stop"
$EnvFile = Join-Path $env:USERPROFILE ".config\ai-council\.env"
$ScriptPath = Join-Path $ProjectDir "ai_council.py"
$LogDir = Join-Path $ProjectDir "logs"
$StateDir = Join-Path $ProjectDir "state"
$StdoutLog = Join-Path $LogDir "shortcuts.log"
$StderrLog = Join-Path $LogDir "shortcuts.err.log"
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

if (-not (Test-Path $ScriptPath)) {
    Write-Error "Missing ai_council.py at $ScriptPath"
    exit 1
}

if (-not $env:AI_COUNCIL_SHORTCUT_TOKEN) {
    Write-Error "Missing AI_COUNCIL_SHORTCUT_TOKEN. Set it in $EnvFile before starting Shortcuts."
    exit 1
}

if (-not $HostName) {
    $HostName = $env:AI_COUNCIL_SHORTCUT_HOST
}
if (-not $HostName) {
    $HostName = "127.0.0.1"
}
if ($Port -le 0) {
    if ($env:AI_COUNCIL_SHORTCUT_PORT) {
        $Port = [int]$env:AI_COUNCIL_SHORTCUT_PORT
    } else {
        $Port = 8788
    }
}

New-Item -ItemType Directory -Path $LogDir -Force | Out-Null
New-Item -ItemType Directory -Path $StateDir -Force | Out-Null

$pidBackedProcess = Get-ShortcutProcessFromPidFile -Path $PidFile
if ($pidBackedProcess) {
    Write-Host "Shortcuts service already running."
    $pidBackedProcess | Select-Object ProcessId, CommandLine
    exit 0
}
if (Test-Path $PidFile) {
    Remove-Item $PidFile -Force
}

$running = Get-CimInstance Win32_Process |
    Where-Object { $_.CommandLine -and $_.CommandLine.Contains("ai_council.py") -and $_.CommandLine.Contains("serve-shortcuts") }

if ($running) {
    Write-Host "Shortcuts service appears to be running without a matching PID file."
    $running | Select-Object ProcessId, CommandLine
    exit 0
}

$pythonArgs = @("-3", $ScriptPath, "serve-shortcuts", "--host", $HostName, "--port", "$Port")
$process = Start-Process -FilePath "py" -ArgumentList $pythonArgs -WorkingDirectory $ProjectDir -WindowStyle Hidden -RedirectStandardOutput $StdoutLog -RedirectStandardError $StderrLog -PassThru
Start-Sleep -Seconds 1
$started = Get-CimInstance Win32_Process -Filter "ProcessId = $($process.Id)" -ErrorAction SilentlyContinue
if (-not $started) {
    if (Test-Path $PidFile) {
        Remove-Item $PidFile -Force
    }
    Write-Error "Shortcuts process exited immediately. Check $StderrLog"
    exit 1
}
$process.Id | Set-Content -Path $PidFile -Encoding ASCII

Write-Host "Started Bartek AI Council Shortcuts"
Write-Host "PID: $($process.Id)"
Write-Host "Endpoint: http://$HostName`:$Port/shortcut"
Write-Host "Logs: $StdoutLog"
Write-Host "Errors: $StderrLog"
