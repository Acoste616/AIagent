# Desktop Server Access Runbook

Date: 2026-06-06

## Purpose

The Windows Desktop is Bartek's always-on private server for AI Council/OpenClaw-style work. The Mac accesses it over the private Tailscale network using SSH. No public SSH port is required.

## How Access Works

1. Tailscale creates a private network between Mac and Windows.
2. Windows runs OpenSSH Server (`sshd`) as a Windows service.
3. The Mac authenticates with an SSH private key.
4. Codex can run commands on Windows through SSH and copy files through SCP.

This is how Codex controls Windows:

```bash
ssh ai-council-desktop hostname
ssh ai-council-desktop "powershell -NoProfile -ExecutionPolicy Bypass -Command \"cd D:\\ai-council; python -X utf8 ai_council.py doctor\""
scp local-file ai-council-desktop:D:/ai-council/
```

## Mac SSH Aliases

Configured in:

```text
/Users/bartoszdomanski/.ssh/config
```

Main alias:

```bash
ssh ai-council-desktop
```

Compatible aliases:

```bash
ssh openclaw-desktop
ssh desktop-server
```

Fallback direct Tailscale IP alias:

```bash
ssh openclaw
```

Current host values:

- Hostname: `desktop-dk4hiv0.taild2cfba.ts.net`
- Tailscale IP: `100.101.53.21`
- Windows user: `Komputer`
- Mac key: `/Users/bartoszdomanski/.ssh/codex_ed25519`

## Windows Services

Must stay enabled:

```powershell
Get-Service sshd,Tailscale
```

Expected:

- `sshd`: `Running`, `Automatic`
- `Tailscale`: `Running`, `Automatic`

Power on AC:

```powershell
powercfg /query SCHEME_CURRENT SUB_SLEEP STANDBYIDLE
powercfg /query SCHEME_CURRENT SUB_SLEEP HIBERNATEIDLE
```

Expected:

- sleep after AC: `0x00000000`
- hibernate after AC: `0x00000000`

AI Council service:

```powershell
Get-ScheduledTask -TaskName "Bartek AI Council Telegram"
Get-ScheduledTaskInfo -TaskName "Bartek AI Council Telegram"
```

Expected:

- state: `Running`
- long-running result: `267009`

## Key Paths On Windows

AI Council:

```text
D:\ai-council
D:\ai-council\ai_council.py
D:\ai-council\tests\test_ai_council.py
D:\ai-council\logs
D:\ai-council\state
D:\ai-council\artifacts
D:\ai-council\workspaces
D:\ai-council\windows-deploy
```

Environment file:

```text
C:\Users\Komputer\.config\ai-council\.env
```

Do not print or paste secrets from this file.

OpenClaw export:

```text
D:\openclaw-export
D:\openclaw-export\shared-drive\claude-collab
D:\openclaw-export\.codex-hybrid
```

SSH authorized keys:

```text
C:\Users\Komputer\.ssh\authorized_keys
```

## Routine Commands From Mac

Health:

```bash
ssh ai-council-desktop "powershell -NoProfile -ExecutionPolicy Bypass -Command \"& 'D:\\ai-council\\server-access-status.ps1'\""
```

AI Council doctor:

```bash
ssh ai-council-desktop "powershell -NoProfile -ExecutionPolicy Bypass -Command \"cd D:\\ai-council; python -X utf8 ai_council.py doctor\""
```

Tests:

```bash
ssh ai-council-desktop "powershell -NoProfile -ExecutionPolicy Bypass -Command \"cd D:\\ai-council; python -X utf8 tests\\test_ai_council.py\""
```

Restart AI Council listener:

```bash
ssh ai-council-desktop "powershell -NoProfile -ExecutionPolicy Bypass -Command \"Stop-ScheduledTask -TaskName 'Bartek AI Council Telegram' -ErrorAction SilentlyContinue; Get-CimInstance Win32_Process -Filter 'Name = ''python.exe''' | Where-Object { $_.CommandLine -like '*D:\ai-council\ai_council.py serve*' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force }; Start-ScheduledTask -TaskName 'Bartek AI Council Telegram'\""
```

Copy deployment files:

```bash
scp ai_council.py ai-council-desktop:D:/ai-council/ai_council.py
scp test_ai_council.py ai-council-desktop:D:/ai-council/tests/test_ai_council.py
```

## Tailscale Funnel Note

Current observed state:

```text
https://desktop-dk4hiv0.taild2cfba.ts.net -> 127.0.0.1:8788
```

This is public Funnel exposure and is not required for private Mac-to-PC SSH access. At the time of the check, no local process was listening on `8788`.

Do not rely on Funnel for AI Council server control. Use SSH over Tailscale.

If this Funnel is not intentionally used, it can be disabled later with:

```powershell
tailscale funnel reset
```

Do that only after confirming no webhook or temporary service depends on it.

## If Access Breaks

1. On Mac, make sure Tailscale is running:

```bash
open -a Tailscale
tailscale status
```

2. Test SSH:

```bash
ssh ai-council-desktop hostname
```

3. On Windows, check services locally:

```powershell
Get-Service sshd,Tailscale
Start-Service sshd
Start-Service Tailscale
```

4. Check key permissions:

```powershell
icacls C:\Users\Komputer\.ssh
icacls C:\Users\Komputer\.ssh\authorized_keys
```

5. Check AI Council:

```powershell
cd D:\ai-council
python -X utf8 ai_council.py doctor
```

## Current Verification

Verified on 2026-06-06:

- `ssh ai-council-desktop hostname` -> `DESKTOP-DK4HIV0`
- `ssh openclaw hostname` -> `DESKTOP-DK4HIV0`
- `ssh desktop-server hostname` -> `DESKTOP-DK4HIV0`
- Windows `sshd`: `Running`, `Automatic`
- Windows `Tailscale`: `Running`, `Automatic`
- AI Council scheduled task: `Running`
- AI Council listener process: `python.exe -X utf8 -u D:\ai-council\ai_council.py serve --send`
- Windows power on AC: sleep `0x00000000`, hibernate `0x00000000`
