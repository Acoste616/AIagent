#!/usr/bin/env python3
"""Standalone Mac iMessage bridge for AI Council (L4.89) — launchd-safe.

WHY STANDALONE: the main repo lives under ~/Documents, which macOS TCC protects
against launchd-spawned processes (they get "Operation not permitted" without Full
Disk Access). This script is installed OUTSIDE ~/Documents (e.g. ~/.ai_council/) and
imports NOTHING from the repo, so a LaunchAgent can run it cleanly.

WHAT IT DOES (same relay as scripts/mac_imessage_bridge.py):
  1. pulls pending outbox rows from the Windows host over SSH
     (`ai_council.py imessage-outbox-dump`),
  2. sends each via the logged-in Messages.app (osascript / iMessage),
  3. acks the terminal state back to the host (`imessage-outbox-ack`).

The Windows host stays the single source of truth; this Mac process only sends.
Logs ids/status only — never message bodies or secrets.

Env (set by the LaunchAgent or your shell):
  AI_COUNCIL_IMESSAGE_ENABLED=true
  AI_COUNCIL_IMESSAGE_TO="bdomanskyy@icloud.com"   # self-channel recipient
  AI_COUNCIL_IMESSAGE_INTERVAL=15                  # poll seconds (optional)
  AI_COUNCIL_HOST_SSH_ALIAS=ai-council-desktop     # optional
  AI_COUNCIL_HOST_DIR="D:\\ai-council"             # optional
  AI_COUNCIL_HOST_PYTHON=python                     # optional
"""
import json
import os
import subprocess
import sys
import time

ALIAS = os.environ.get("AI_COUNCIL_HOST_SSH_ALIAS", "ai-council-desktop")
HOST_DIR = os.environ.get("AI_COUNCIL_HOST_DIR", "D:\\ai-council")
HOST_PY = os.environ.get("AI_COUNCIL_HOST_PYTHON", "python")
TO = os.environ.get("AI_COUNCIL_IMESSAGE_TO", "").strip()
ENABLED = os.environ.get("AI_COUNCIL_IMESSAGE_ENABLED", "").lower() in ("1", "true", "yes", "on")
INTERVAL = int(os.environ.get("AI_COUNCIL_IMESSAGE_INTERVAL", "15") or "15")


def _host_cmd(council_args: str) -> list:
    inner = f"cd {HOST_DIR}; {HOST_PY} ai_council.py {council_args}"
    return ["ssh", "-o", "ConnectTimeout=15", ALIAS,
            f'powershell -NoProfile -ExecutionPolicy Bypass -Command "{inner}"']


def pull(limit: int = 25) -> list:
    try:
        p = subprocess.run(_host_cmd(f"imessage-outbox-dump --limit {limit}"),
                           capture_output=True, text=True, timeout=40)
    except Exception:
        return []
    for line in reversed((p.stdout or "").splitlines()):
        line = line.strip()
        if line.startswith("["):
            try:
                rows = json.loads(line)
                return rows if isinstance(rows, list) else []
            except json.JSONDecodeError:
                return []
    return []


def ack(msg_id: str, status: str, detail: str = "") -> None:
    # Quote-safe: NO --detail. Passing `--detail "..."` would nest double quotes
    # inside the host's `powershell -Command "..."` wrapper and break argparse on
    # Windows, so the ack never recorded and the row stayed pending -> infinite
    # resend loop. The status (sent/failed) is all the host needs for terminal
    # state; the failure detail is kept in this Mac runner's own log.
    try:
        subprocess.run(_host_cmd(f"imessage-outbox-ack --id {msg_id} --status {status}"),
                       capture_output=True, text=True, timeout=30)
    except Exception:
        pass


def _asq(value: str) -> str:
    return '"' + str(value).replace("\\", "\\\\").replace('"', '\\"') + '"'


def send(text: str, to: str = "") -> tuple:
    recipient = (to or TO).strip()
    if not recipient or not (text or "").strip():
        return False, "empty"
    script = ('tell application "Messages"\n'
              "  set targetService to 1st service whose service type = iMessage\n"
              f"  set targetBuddy to buddy {_asq(recipient)} of targetService\n"
              f"  send {_asq(text)} to targetBuddy\n"
              "end tell")
    try:
        # 60s, not 25: the FIRST AppleEvent after Messages.app is idle can be slow
        # to set up (cold start), which previously timed out and got mis-acked.
        p = subprocess.run(["osascript", "-e", script], capture_output=True, text=True, timeout=60)
    except Exception as exc:
        return False, str(exc)[:200]
    return (p.returncode == 0), (p.stderr or "").strip()[:200]


def cycle() -> int:
    rows = pull()
    n = 0
    for row in rows:
        rid = str(row.get("id") or "")
        if not rid:
            continue
        ok, err = send(str(row.get("text") or ""), str(row.get("to") or ""))
        ack(rid, "sent" if ok else "failed", "" if ok else err)
        n += 1
        print(f"{'sent' if ok else 'failed'} {rid}{'' if ok else ': ' + err}")
    return n


def main() -> int:
    if sys.platform != "darwin":
        print("refusing: macOS only")
        return 2
    if not ENABLED:
        print("refusing: AI_COUNCIL_IMESSAGE_ENABLED not true")
        return 2
    if not TO:
        print("refusing: AI_COUNCIL_IMESSAGE_TO not set")
        return 2
    print(f"bridge up: alias={ALIAS} interval={INTERVAL}s recipient_set={bool(TO)}")
    while True:
        try:
            cycle()
        except Exception as exc:
            print(f"cycle error: {type(exc).__name__}: {exc}")
        sys.stdout.flush()
        time.sleep(max(5, INTERVAL))


if __name__ == "__main__":
    sys.exit(main())
