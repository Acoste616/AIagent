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
import base64
import json
import os
import sqlite3
import subprocess
import sys
import time
from pathlib import Path

ALIAS = os.environ.get("AI_COUNCIL_HOST_SSH_ALIAS", "ai-council-desktop")
HOST_DIR = os.environ.get("AI_COUNCIL_HOST_DIR", "D:\\ai-council")
HOST_PY = os.environ.get("AI_COUNCIL_HOST_PYTHON", "python")
TO = os.environ.get("AI_COUNCIL_IMESSAGE_TO", "").strip()
ENABLED = os.environ.get("AI_COUNCIL_IMESSAGE_ENABLED", "").lower() in ("1", "true", "yes", "on")
INBOUND = os.environ.get("AI_COUNCIL_IMESSAGE_INBOUND", "").lower() in ("1", "true", "yes", "on")
INTERVAL = int(os.environ.get("AI_COUNCIL_IMESSAGE_INTERVAL", "15") or "15")

# Inbound (two-way) state — kept outside ~/Documents so launchd can write it.
STATE_DIR = Path(os.path.expanduser("~/.ai_council"))
SENT_LOG = STATE_DIR / "imessage_sent_texts.jsonl"     # anti-loop: texts WE sent
CURSOR_FILE = STATE_DIR / "imessage_inbound_cursor"     # last processed message ROWID
CHAT_DB = Path(os.path.expanduser("~/Library/Messages/chat.db"))
SENT_WINDOW_S = 7200  # only dedup against the last 2h of our own sends


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


# ---- anti-loop sent-text log (shared by outbound + inbound) ----
def _now() -> float:
    return time.time()


def record_sent(text: str) -> None:
    text = (text or "").strip()
    if not text:
        return
    try:
        STATE_DIR.mkdir(parents=True, exist_ok=True)
        with open(SENT_LOG, "a", encoding="utf-8") as f:
            f.write(json.dumps({"t": text, "ts": _now()}, ensure_ascii=False) + "\n")
    except Exception:
        pass


def recent_sent_norms() -> set:
    norms = set()
    try:
        cutoff = _now() - SENT_WINDOW_S
        with open(SENT_LOG, encoding="utf-8") as f:
            for line in f:
                try:
                    r = json.loads(line)
                    if float(r.get("ts", 0)) >= cutoff:
                        norms.add(_norm(str(r.get("t", ""))))
                except Exception:
                    continue
    except OSError:
        pass
    return norms


# ---- inbound (two-way) reader ----
def _decode_ab(blob) -> str:
    if not blob:
        return ""
    try:
        b = bytes(blob)
    except Exception:
        return ""
    i = b.find(b"NSString")
    if i < 0:
        return ""
    j = b.find(b"\x2b", i + 8)
    if j < 0 or j + 1 >= len(b):
        return ""
    p = j + 1
    n = b[p]
    p += 1
    if n == 0x81:
        n = int.from_bytes(b[p:p + 2], "little"); p += 2
    elif n == 0x82:
        n = int.from_bytes(b[p:p + 4], "little"); p += 4
    return b[p:p + n].decode("utf-8", errors="replace")


def _msg_text(text, ab) -> str:
    return str(text) if text else _decode_ab(ab)


def _norm(t) -> str:
    return " ".join(str(t or "").split()).strip().lower()


def _read_cursor():
    try:
        return int(CURSOR_FILE.read_text().strip())
    except Exception:
        return None


def _write_cursor(v) -> None:
    try:
        STATE_DIR.mkdir(parents=True, exist_ok=True)
        CURSOR_FILE.write_text(str(int(v)))
    except Exception:
        pass


def host_respond(text: str) -> str:
    """Forward a user message to the host and return ONLY its reply (quote-safe b64)."""
    b64 = base64.b64encode(text.encode("utf-8")).decode("ascii")
    try:
        p = subprocess.run(_host_cmd(f"respond-b64 --b64 {b64}"), capture_output=True, text=True, timeout=180)
    except Exception:
        return ""
    return (p.stdout or "").strip()


def inbound_cycle() -> int:
    """Read NEW messages in the self-channel chat ONLY, reply to genuine user messages.
    Privacy: only the chat whose identifier == TO is ever read. Loop-safe via the
    sent-text dedup + a ROWID cursor that starts at the current max (no history replay)."""
    if not (INBOUND and TO and CHAT_DB.exists()):
        return 0
    try:
        conn = sqlite3.connect(f"file:{CHAT_DB}?mode=ro", uri=True, timeout=5)
    except sqlite3.Error:
        return 0
    try:
        self_ids = [r[0] for r in conn.execute("SELECT ROWID FROM chat WHERE chat_identifier=?", (TO,))]
        if not self_ids:
            return 0
        ph = ",".join("?" * len(self_ids))
        cur = _read_cursor()
        if cur is None:  # first run: anchor at current max, do NOT replay history
            row = conn.execute(
                f"SELECT MAX(m.ROWID) FROM message m JOIN chat_message_join cmj ON cmj.message_id=m.ROWID "
                f"WHERE cmj.chat_id IN ({ph})", tuple(self_ids)).fetchone()
            _write_cursor(int((row and row[0]) or 0))
            return 0
        rows = conn.execute(
            f"SELECT m.ROWID, m.text, m.attributedBody FROM message m "
            f"JOIN chat_message_join cmj ON cmj.message_id=m.ROWID "
            f"WHERE cmj.chat_id IN ({ph}) AND m.ROWID > ? ORDER BY m.ROWID ASC LIMIT 20",
            tuple(self_ids) + (cur,)).fetchall()
    finally:
        conn.close()
    if not rows:
        return 0
    sent_norms = recent_sent_norms()
    processed = 0
    max_id = cur
    for rid, text, ab in rows:
        max_id = max(max_id, rid)
        body = _msg_text(text, ab).strip()
        if not body or _norm(body) in sent_norms:
            continue  # empty or our own echo -> skip (loop-safety)
        reply = host_respond(body)
        if reply:
            record_sent(reply)          # record BEFORE sending so the echo is deduped
            ok, _ = send(reply)
            if ok:
                processed += 1
                print(f"inbound replied to {rid}")
    _write_cursor(max_id)
    return processed


def cycle() -> int:
    rows = pull()
    n = 0
    for row in rows:
        rid = str(row.get("id") or "")
        if not rid:
            continue
        text = str(row.get("text") or "")
        ok, err = send(text, str(row.get("to") or ""))
        if ok:
            record_sent(text)  # so the inbound reader treats our proactive sends as echoes
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
    print(f"bridge up: alias={ALIAS} interval={INTERVAL}s recipient_set={bool(TO)} inbound={INBOUND}")
    while True:
        try:
            cycle()
        except Exception as exc:
            print(f"cycle error: {type(exc).__name__}: {exc}")
        try:
            inbound_cycle()
        except Exception as exc:
            print(f"inbound error: {type(exc).__name__}: {exc}")
        sys.stdout.flush()
        time.sleep(max(5, INTERVAL))


if __name__ == "__main__":
    sys.exit(main())
