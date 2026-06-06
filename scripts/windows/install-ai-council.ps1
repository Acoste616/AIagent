$ErrorActionPreference = "Stop"

$TaskName = "Bartek AI Council Telegram"
$DefaultInstallDir = "D:\ai-council"
if (-not (Test-Path "D:\")) {
  $DefaultInstallDir = Join-Path $env:USERPROFILE "ai-council"
}

$SourceDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$PackageRoot = Split-Path -Parent $SourceDir
$EnvExample = Join-Path $SourceDir ".env.example"
if (-not (Test-Path $EnvExample)) {
  $EnvExample = Join-Path $PackageRoot ".env.example"
}
$InstallDir = $DefaultInstallDir
$LogDir = Join-Path $InstallDir "logs"
$StateDir = Join-Path $InstallDir "state"
$EnvDir = Join-Path $env:USERPROFILE ".config\ai-council"
$EnvFile = Join-Path $EnvDir ".env"

New-Item -ItemType Directory -Force -Path $InstallDir, $LogDir, $StateDir, $EnvDir | Out-Null
Copy-Item -Force (Join-Path $SourceDir "ai_council.py") (Join-Path $InstallDir "ai_council.py")
Copy-Item -Force $EnvExample (Join-Path $InstallDir ".env.example")

if (-not (Test-Path $EnvFile)) {
  Copy-Item -Force $EnvExample $EnvFile
  Write-Host "Created env template: $EnvFile"
  Write-Host "Edit it before expecting the bot to work."
}

$Python = (Get-Command py -ErrorAction SilentlyContinue)
if ($Python) {
  $PythonCommand = "py"
  $PythonArgs = "-3 -X utf8 -u `"$InstallDir\ai_council.py`" serve --send"
} else {
  $Python = (Get-Command python -ErrorAction SilentlyContinue)
  if (-not $Python) {
    throw "Python was not found. Install Python 3 first."
  }
  $PythonCommand = $Python.Source
  $PythonArgs = "-X utf8 -u `"$InstallDir\ai_council.py`" serve --send"
}

$RunScript = Join-Path $InstallDir "run-ai-council.ps1"
@"
`$env:AI_COUNCIL_ENV = "$EnvFile"
`$env:AI_COUNCIL_LOG_DIR = "$LogDir"
`$env:AI_COUNCIL_STATE_DIR = "$StateDir"
`$env:AI_COUNCIL_PROJECT_DIR = "$InstallDir"
`$env:PYTHONUTF8 = "1"
`$env:PYTHONIOENCODING = "utf-8"
`[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new(`$false)
`$OutputEncoding = [System.Text.UTF8Encoding]::new(`$false)
New-Item -ItemType Directory -Force -Path "$LogDir", "$StateDir" | Out-Null
Set-Location "$InstallDir"
& $PythonCommand $PythonArgs *> "$LogDir\service.log"
"@ | Set-Content -Encoding UTF8 $RunScript

$Action = New-ScheduledTaskAction `
  -Execute "powershell.exe" `
  -Argument "-NoProfile -ExecutionPolicy Bypass -File `"$RunScript`"" `
  -WorkingDirectory $InstallDir

$Triggers = @()
$Triggers += New-ScheduledTaskTrigger -AtLogOn
$Triggers += New-ScheduledTaskTrigger -AtStartup
$Settings = New-ScheduledTaskSettingsSet `
  -AllowStartIfOnBatteries `
  -DontStopIfGoingOnBatteries `
  -RestartCount 999 `
  -RestartInterval (New-TimeSpan -Minutes 1) `
  -ExecutionTimeLimit (New-TimeSpan -Seconds 0) `
  -MultipleInstances IgnoreNew

try {
  Register-ScheduledTask `
    -TaskName $TaskName `
    -Action $Action `
    -Trigger $Triggers `
    -Settings $Settings `
    -Description "Telegram AI Council router for Codex, Claude, and Grok" `
    -Force | Out-Null

  Start-ScheduledTask -TaskName $TaskName
  Write-Host "Installed: $TaskName"
} catch {
  $StartupDir = [Environment]::GetFolderPath("Startup")
  $FallbackCmd = Join-Path $StartupDir "ai-council-telegram.cmd"
  @"
@echo off
powershell.exe -NoProfile -ExecutionPolicy Bypass -Command "`$task = Get-ScheduledTask -TaskName '$TaskName' -ErrorAction SilentlyContinue; if (`$task) { Start-ScheduledTask -TaskName '$TaskName' } else { powershell.exe -NoProfile -ExecutionPolicy Bypass -File '$RunScript' }"
"@ | Set-Content -Encoding ASCII $FallbackCmd
  Write-Warning "Scheduled Task registration failed: $($_.Exception.Message)"
  Write-Warning "Scheduled Task registration failed. Startup fallback created: $FallbackCmd"
}
Write-Host "InstallDir: $InstallDir"
Write-Host "EnvFile: $EnvFile"
Write-Host "Logs: $LogDir"
Write-Host "Status: powershell -ExecutionPolicy Bypass -File .\status-ai-council.ps1"
