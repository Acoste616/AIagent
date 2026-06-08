#!/usr/bin/env python3
"""Mac-side iMessage bridge runner for AI Council (L4.82).

ai_council runs on the Windows host (the Telegram listener). iMessage can only be
SENT from this Mac, where Messages.app is logged in. This runner:

  1. pulls pending rows from the host outbox over the existing SSH alias
     (`ai-council-desktop`) via `python ai_council.py imessage-outbox-dump`,
  2. sends each via the local Messages.app (osascript, reusing ai_council.imessage_send),
  3. acks the terminal state back to the host (`imessage-outbox-ack`).

The host stays the single source of truth; this Mac process only sends.

ONE-TIME on this Mac (no OAuth, no Apple Business):
  • System Settings → Privacy & Security → Automation → allow Terminal (or your
    Python) to control **Messages** (this clears the -1712 AppleEvent timeout).
  • Export the channel env in THIS process:
        export AI_COUNCIL_IMESSAGE_ENABLED=true
        export AI_COUNCIL_IMESSAGE_TO="+48XXXXXXXXX"   # your Apple ID / phone
  • Confirm the host is reachable: `ssh ai-council-desktop echo ok`

Run:
  AI_COUNCIL_IMESSAGE_ENABLED=true python3 scripts/mac_imessage_bridge.py --once
  AI_COUNCIL_IMESSAGE_ENABLED=true python3 scripts/mac_imessage_bridge.py --interval 15

This script never prints message bodies or secrets beyond ids/status.
"""
import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import ai_council  # noqa: E402

DEFAULT_ALIAS = os.environ.get("AI_COUNCIL_HOST_SSH_ALIAS", "ai-council-desktop")
DEFAULT_HOST_DIR = os.environ.get("AI_COUNCIL_HOST_DIR", "D:\\ai-council")
DEFAULT_HOST_PYTHON = os.environ.get("AI_COUNCIL_HOST_PYTHON", "python")


def _host_cmd(alias: str, host_dir: str, host_python: str, council_args: str) -> list[str]:
    inner = f"cd {host_dir}; {host_python} ai_council.py {council_args}"
    return ["ssh", "-o", "ConnectTimeout=15", alias,
            f'powershell -NoProfile -ExecutionPolicy Bypass -Command "{inner}"']


def host_pull_pending(alias: str, host_dir: str, host_python: str, limit: int) -> list[dict]:
    cmd = _host_cmd(alias, host_dir, host_python, f"imessage-outbox-dump --limit {limit}")
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=40)
    out = (proc.stdout or "").strip()
    # The host prints a single JSON array on the last non-empty line.
    for line in reversed(out.splitlines()):
        line = line.strip()
        if line.startswith("["):
            try:
                rows = json.loads(line)
                return rows if isinstance(rows, list) else []
            except json.JSONDecodeError:
                return []
    return []


def host_ack(alias: str, host_dir: str, host_python: str, msg_id: str, status: str, detail: str = "") -> None:
    safe_detail = detail.replace('"', "'")[:200]
    args = f'imessage-outbox-ack --id {msg_id} --status {status} --detail "{safe_detail}"'
    subprocess.run(_host_cmd(alias, host_dir, host_python, args), capture_output=True, text=True, timeout=30)


def run_once(alias: str, host_dir: str, host_python: str, limit: int) -> int:
    rows = host_pull_pending(alias, host_dir, host_python, limit)
    if not rows:
        return 0
    results = ai_council.imessage_drain_rows(
        rows,
        send_fn=ai_council.imessage_send,
        ack_fn=lambda mid, status, detail: host_ack(alias, host_dir, host_python, mid, status, detail),
    )
    sent = sum(1 for r in results if r["status"] == "sent")
    failed = len(results) - sent
    print(f"drained={len(results)} sent={sent} failed={failed}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="AI Council Mac iMessage bridge runner")
    parser.add_argument("--alias", default=DEFAULT_ALIAS, help="SSH alias of the Windows host")
    parser.add_argument("--host-dir", default=DEFAULT_HOST_DIR)
    parser.add_argument("--host-python", default=DEFAULT_HOST_PYTHON)
    parser.add_argument("--limit", type=int, default=25)
    parser.add_argument("--once", action="store_true", help="Drain once and exit")
    parser.add_argument("--interval", type=int, default=0, help="Poll loop interval seconds (>0 to loop)")
    args = parser.parse_args()

    if not ai_council.on_macos():
        print("refusing: this runner must run on macOS (Messages.app host)")
        return 2
    if not ai_council.imessage_enabled():
        print("refusing: set AI_COUNCIL_IMESSAGE_ENABLED=true (and grant macOS Automation for Messages)")
        return 2

    if args.once or args.interval <= 0:
        return run_once(args.alias, args.host_dir, args.host_python, args.limit)
    while True:
        try:
            run_once(args.alias, args.host_dir, args.host_python, args.limit)
        except Exception as exc:  # keep the loop alive across transient SSH errors
            print(f"cycle error: {type(exc).__name__}: {exc}")
        time.sleep(max(5, args.interval))


if __name__ == "__main__":
    sys.exit(main())
