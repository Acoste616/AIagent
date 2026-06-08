$ErrorActionPreference = "SilentlyContinue"
Stop-ScheduledTask -TaskName "Bartek AI Council Telegram"
Start-Sleep -Seconds 1
$procs = Get-CimInstance Win32_Process -Filter "name='python.exe'" | Where-Object { $_.CommandLine -like "*serve --send*" }
foreach ($p in $procs) { Stop-Process -Id $p.ProcessId -Force; Write-Output ("killed " + $p.ProcessId) }
Start-Sleep -Seconds 2
Start-ScheduledTask -TaskName "Bartek AI Council Telegram"
Start-Sleep -Seconds 6
$now = Get-CimInstance Win32_Process -Filter "name='python.exe'" | Where-Object { $_.CommandLine -like "*serve --send*" }
foreach ($p in $now) { Write-Output ("running " + $p.ProcessId + " since " + $p.CreationDate) }
Write-Output ("serve_count=" + ($now | Measure-Object).Count)

# WHY THIS EXISTS (L4.83 ops fix):
# run-ai-council.ps1 runs `serve --send` in the FOREGROUND. Telegram allows only ONE
# getUpdates long-poller per bot token, so Stop-ScheduledTask + Start-ScheduledTask does
# NOT reliably replace the listener: the old python serve can orphan and keep polling,
# and the freshly-started serve hits a 409 Conflict and exits — leaving STALE code live.
# To actually deploy new code you MUST kill the running `serve --send` python process,
# THEN start the task. This script does exactly that and verifies serve_count=1.
