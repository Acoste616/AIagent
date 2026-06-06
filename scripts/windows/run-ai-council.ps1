$env:AI_COUNCIL_ENV = "C:\Users\Komputer\.config\ai-council\.env"
$env:AI_COUNCIL_LOG_DIR = "D:\ai-council\logs"
$env:AI_COUNCIL_STATE_DIR = "D:\ai-council\state"
$env:AI_COUNCIL_PROJECT_DIR = "D:\ai-council"
$env:PYTHONUTF8 = "1"
$env:PYTHONIOENCODING = "utf-8"

[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false)
$OutputEncoding = [System.Text.UTF8Encoding]::new($false)

New-Item -ItemType Directory -Force -Path "D:\ai-council\logs", "D:\ai-council\state" | Out-Null
Set-Location "D:\ai-council"

$pythonCommand = Get-Command python -ErrorAction SilentlyContinue
if ($pythonCommand) {
  & $pythonCommand.Source -X utf8 -u "D:\ai-council\ai_council.py" serve --send *> "D:\ai-council\logs\service.log"
  exit $LASTEXITCODE
}

& py -3 -X utf8 -u "D:\ai-council\ai_council.py" serve --send *> "D:\ai-council\logs\service.log"
exit $LASTEXITCODE
