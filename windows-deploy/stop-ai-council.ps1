$TaskName = "Bartek AI Council Telegram"

Stop-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
Start-Sleep -Seconds 1

$listeners = Get-CimInstance Win32_Process |
    Where-Object CommandLine -Like "*D:\ai-council\ai_council.py serve*"

foreach ($listener in $listeners) {
    try {
        Stop-Process -Id $listener.ProcessId -Force -ErrorAction Stop
        Write-Output "Stopped listener PID $($listener.ProcessId)"
    } catch {
        Write-Output "Could not stop listener PID $($listener.ProcessId): $($_.Exception.Message)"
    }
}

Get-ScheduledTask -TaskName $TaskName | Format-List TaskName,State
