$TaskName = "Bartek AI Council Telegram"
$Task = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
if (-not $Task) {
  Write-Host "Task not installed: $TaskName"
  exit 1
}
$Info = Get-ScheduledTaskInfo -TaskName $TaskName
$Task | Format-List TaskName,State
$Info | Format-List LastRunTime,LastTaskResult,NextRunTime,NumberOfMissedRuns

$DefaultLogDir = "D:\ai-council\logs"
if (-not (Test-Path $DefaultLogDir)) {
  $DefaultLogDir = Join-Path $env:USERPROFILE "ai-council\logs"
}
Write-Host "LogDir: $DefaultLogDir"
Get-ChildItem $DefaultLogDir -ErrorAction SilentlyContinue | Sort-Object LastWriteTime -Descending | Select-Object -First 10
