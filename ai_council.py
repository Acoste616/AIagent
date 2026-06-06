#!/usr/bin/env python3
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import difflib
import hashlib
import json
import os
import re
import signal
import shutil
import sqlite3
import subprocess
import sys
import threading
import time
from pathlib import Path
from urllib.parse import urlencode
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


os.environ.setdefault("PYTHONUTF8", "1")
os.environ.setdefault("PYTHONIOENCODING", "utf-8")


def configure_utf8_stdio() -> None:
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure:
            try:
                reconfigure(encoding="utf-8", errors="replace")
            except Exception:
                pass


configure_utf8_stdio()


PROJECT_DIR = Path(os.environ.get("AI_COUNCIL_PROJECT_DIR", Path(__file__).resolve().parent)).resolve()
ENV_PATH = Path(os.environ.get("AI_COUNCIL_ENV", Path.home() / ".config" / "ai-council" / ".env")).expanduser()
LOG_DIR = Path(os.environ.get("AI_COUNCIL_LOG_DIR", PROJECT_DIR / "logs")).expanduser()
AUDIT_LOG = LOG_DIR / "audit.jsonl"
STATE_DIR = Path(os.environ.get("AI_COUNCIL_STATE_DIR", PROJECT_DIR / "state")).expanduser()
OFFSET_FILE = STATE_DIR / "telegram_offset"
WORKSPACES_DIR = Path(os.environ.get("AI_COUNCIL_WORKSPACES_DIR", PROJECT_DIR / "workspaces")).expanduser()
ARTIFACTS_DIR = Path(os.environ.get("AI_COUNCIL_ARTIFACTS_DIR", PROJECT_DIR / "artifacts")).expanduser()
REPORTS_DIR = Path(os.environ.get("AI_COUNCIL_REPORTS_DIR", PROJECT_DIR / "reports")).expanduser()
TASKS_FILE = STATE_DIR / "tasks.jsonl"
ACTIONS_FILE = STATE_DIR / "actions.jsonl"
COUNCIL_JOBS_FILE = STATE_DIR / "council_jobs.jsonl"
BACKGROUND_JOBS_FILE = STATE_DIR / "background_jobs.jsonl"
ARTIFACT_INDEX_FILE = STATE_DIR / "artifact_index.jsonl"
BACKGROUND_JOB_SPECS_DIR = STATE_DIR / "background_job_specs"
COSTS_FILE = STATE_DIR / "costs.jsonl"
MEMORY_DB = STATE_DIR / "memory.sqlite"
DEFAULT_OPENCLAW_EXPORT = Path("D:/openclaw-export") if os.name == "nt" else Path.home() / "openclaw-export"
OPENCLAW_EXPORT = Path(os.environ.get("OPENCLAW_EXPORT", DEFAULT_OPENCLAW_EXPORT)).expanduser()
CLAUDE_COLLAB_DIR = Path(
    os.environ.get("AI_COUNCIL_COLLAB_DIR", OPENCLAW_EXPORT / "shared-drive" / "claude-collab")
).expanduser()

REQUIRED_KEYS = [
    "TELEGRAM_BOT_TOKEN",
    "TELEGRAM_ALLOWED_USER_ID",
    "TELEGRAM_ALLOWED_CHAT_ID",
    "XAI_API_KEY",
    "AI_COUNCIL_DRY_SEND",
    "GROK_DAILY_BUDGET_USD",
    "GROK_DAILY_CALL_LIMIT",
]

DEFAULT_CODEX_BIN = "codex.exe" if os.name == "nt" else "codex"
DEFAULT_CLAUDE_BIN = str(Path.home() / ".local" / "bin" / ("claude.exe" if os.name == "nt" else "claude"))
DEFAULT_CLAUDE_FLOW_MODEL = "claude-opus-4-8"
TASK_NAME = "Bartek AI Council Telegram"
NOISE_PREFIXES = (
    "SUCCESS: The process with PID",
    "INFO: The process with PID",
    "ERROR: The process with PID",
)
SECRET_MARKERS = ("TOKEN", "KEY", "SECRET", "PASSWORD")
WORKSPACE_WRITE_MAX_CHARS = 20000
MODEL_COMMANDS = {
    "codex_default",
    "@codex",
    "@claude",
    "@claude-flow",
    "/flow",
    "@grok",
    "@research",
    "@xresearch",
    "/xresearch",
    "/poke-research",
    "@all",
    "/council",
}
SIDE_EFFECT_COMMANDS = {"/write", "/append", "/patch", "/propose"}
BACKGROUND_COMMANDS = {
    "codex_default",
    "@codex",
    "@claude-flow",
    "/flow",
    "@grok",
    "@research",
    "@xresearch",
    "/xresearch",
    "/poke-research",
    "@all",
    "/council",
}


def load_env(path: Path = ENV_PATH) -> dict[str, str]:
    values: dict[str, str] = {}
    if path.exists():
        for raw in path.read_text(encoding="utf-8", errors="replace").splitlines():
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            values[key] = value
    for key, value in os.environ.items():
        if key.startswith(("TELEGRAM_", "XAI_", "AI_COUNCIL_", "GROK_")):
            values[key] = value
    return values


def operator_env() -> dict[str, str]:
    env = os.environ.copy()
    env.setdefault("PYTHONUTF8", "1")
    env.setdefault("PYTHONIOENCODING", "utf-8")
    return env


def redaction_values() -> list[str]:
    values = []
    for key, value in {**load_env(), **os.environ}.items():
        if value and len(value) >= 8 and any(marker in key.upper() for marker in SECRET_MARKERS):
            values.append(value)
    return values


def redact_secrets(text: str) -> str:
    redacted = text
    for value in redaction_values():
        redacted = redacted.replace(value, "[redacted]")
    return redacted


def clean_operator_output(text: str) -> str:
    lines = []
    for line in (text or "").splitlines():
        if any(line.startswith(prefix) for prefix in NOISE_PREFIXES):
            continue
        lines.append(line)
    return "\n".join(lines).strip()


def cfg(key: str, default: str = "") -> str:
    return load_env().get(key, default)


def bool_cfg(key: str, default: bool = False) -> bool:
    value = cfg(key, "true" if default else "false").strip().lower()
    return value in {"1", "true", "yes", "on"}


def int_cfg(key: str, default: int) -> int:
    try:
        return int(cfg(key, str(default)))
    except ValueError:
        return default


def float_cfg(key: str, default: float) -> float:
    try:
        return float(cfg(key, str(default)))
    except ValueError:
        return default


def concise_operator_prompt(prompt: str, operator: str) -> str:
    text = prompt.strip()
    if not text:
        text = f"Powiedz krótko, że {operator} działa."
    memory_context = memory_context_for_prompt(text)
    memory_block = f"\n\nKontekst z pamięci AI Council:\n{memory_context}" if memory_context else ""
    return (
        "Kontekst: odpowiadasz w Telegram AI Council dla Bartka. "
        "Odpowiadaj po polsku, krótko i operacyjnie: maks 4 zdania albo 6 krótkich punktów. "
        "Nie opisuj wewnętrznych szczegółów, sandboxa ani logów, chyba że Bartek pyta o status/system. "
        "Jeśli potrzeba dłuższej analizy, zaproponuj komendę @research albo poproś o zgodę na dłuższą odpowiedź.\n\n"
        f"Pytanie: {text}{memory_block}"
    )


def command_path(env_key: str, command: str, fallback: str) -> str:
    configured = cfg(env_key)
    if configured:
        return configured
    found = shutil.which(command)
    if found:
        return found
    if os.name == "nt" and not command.lower().endswith(".exe"):
        found = shutil.which(f"{command}.exe")
        if found:
            return found
    if fallback and Path(fallback).exists():
        return fallback
    return fallback or command


def short_hash(value: str) -> str:
    if not value:
        return ""
    return hashlib.sha256(value.encode()).hexdigest()[:12]


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def parse_utc(value: str) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            return parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)
    except ValueError:
        return None


def seconds_since(value: str) -> float:
    parsed = parse_utc(value)
    if not parsed:
        return 0.0
    return (datetime.now(timezone.utc) - parsed).total_seconds()


def ensure_council_dirs() -> None:
    for path in [
        LOG_DIR,
        STATE_DIR,
        WORKSPACES_DIR,
        WORKSPACES_DIR / "codex",
        WORKSPACES_DIR / "claude",
        WORKSPACES_DIR / "grok",
        WORKSPACES_DIR / "shared",
        ARTIFACTS_DIR,
        REPORTS_DIR,
        BACKGROUND_JOB_SPECS_DIR,
    ]:
        path.mkdir(parents=True, exist_ok=True)


def compact_line(value: str, limit: int = 100) -> str:
    text = " ".join((value or "").split())
    return text if len(text) <= limit else text[: limit - 1] + "…"


def append_jsonl(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(sanitize_for_audit(payload), ensure_ascii=False) + "\n")


def read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    rows: list[dict] = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        if not line.strip():
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return rows


def read_jsonl_tail(path: Path, limit: int = 8) -> list[dict]:
    return read_jsonl(path)[-limit:]


def latest_by_id(path: Path, id_key: str, limit: int = 10) -> list[dict]:
    latest: dict[str, dict] = {}
    order: list[str] = []
    for row in read_jsonl(path):
        row_id = row.get(id_key)
        if not row_id:
            continue
        if row_id not in latest:
            order.append(row_id)
        latest[row_id] = row
    return [latest[row_id] for row_id in reversed(order[-limit:])]


def create_task(
    prompt: str,
    source: str = "telegram",
    *,
    status: str = "queued",
    command: str = "/task",
    operators: list[str] | None = None,
    request_id: str = "",
    idempotency_key: str = "",
    chat_id_hash: str = "",
    update_id: int | None = None,
) -> dict:
    ensure_council_dirs()
    clean_prompt = prompt.strip()
    if not clean_prompt:
        clean_prompt = "Brak opisu zadania"
    task_id = f"task-{datetime.now().strftime('%Y%m%d-%H%M%S')}-{short_hash(clean_prompt)[:6]}"
    task = {
        "task_id": task_id,
        "created_at": utc_now(),
        "updated_at": utc_now(),
        "source": source,
        "status": status,
        "command": command,
        "operators": operators or ["host"],
        "prompt": clean_prompt,
        "workspace": str(WORKSPACES_DIR / "shared"),
        "next_step": "plan/research first; execution requires approval",
        "request_id": request_id,
        "idempotency_key": idempotency_key,
        "chat_id_hash": chat_id_hash,
        "update_id": update_id,
    }
    append_jsonl(TASKS_FILE, task)
    audit(
        {
            "command": command,
            "operators": operators or ["host"],
            "status": status,
            "duration_ms": 0,
            "task_id": task_id,
            "output_preview": clean_prompt[:300],
        }
    )
    return task


def get_latest_task(task_id: str) -> dict | None:
    task_id = task_id.strip()
    latest = {row.get("task_id"): row for row in read_jsonl(TASKS_FILE) if row.get("task_id")}
    return latest.get(task_id)


def latest_tasks(limit: int = 8) -> list[dict]:
    return latest_by_id(TASKS_FILE, "task_id", limit=limit)


def update_task_status(task_id: str, status: str, note: str = "", **fields) -> dict | None:
    current = get_latest_task(task_id)
    if not current:
        return None
    updated = {
        **current,
        **fields,
        "status": status,
        "updated_at": utc_now(),
    }
    if note:
        updated["note"] = note
    append_jsonl(TASKS_FILE, updated)
    audit(
        {
            "command": "task_status",
            "operators": ["host"],
            "status": status,
            "duration_ms": 0,
            "task_id": task_id,
            "output_preview": note[:300],
        }
    )
    return updated


def route_needs_task(route: dict) -> bool:
    command = route.get("command")
    if command in MODEL_COMMANDS or command in SIDE_EFFECT_COMMANDS:
        return True
    if command == "/multi":
        return any(route_needs_task(child) for child in route.get("routes", []))
    return False


def route_should_background(route: dict) -> bool:
    command = route.get("command")
    if command in BACKGROUND_COMMANDS:
        return True
    if command == "/multi":
        return any(route_should_background(child) for child in route.get("routes", []))
    return False


def append_background_job_event(job: dict) -> None:
    append_jsonl(BACKGROUND_JOBS_FILE, job)


def get_latest_background_job(task_id: str) -> dict | None:
    task_id = task_id.strip()
    latest = {row.get("task_id"): row for row in read_jsonl(BACKGROUND_JOBS_FILE) if row.get("task_id")}
    return latest.get(task_id)


def background_job_spec_path(task_id: str) -> Path:
    return BACKGROUND_JOB_SPECS_DIR / f"{task_id}.json"


def save_background_job_spec(route: dict, chat_id: str, task_id: str, send_progress: bool = True) -> Path:
    ensure_council_dirs()
    spec = {
        "task_id": task_id,
        "chat_id": chat_id,
        "route": route,
        "send_progress": send_progress,
        "send_running": False,
        "created_at": utc_now(),
    }
    path = background_job_spec_path(task_id)
    path.write_text(json.dumps(sanitize_for_audit(spec), ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def load_background_job_spec(task_id: str) -> dict | None:
    path = background_job_spec_path(task_id)
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8", errors="replace"))
    except json.JSONDecodeError:
        return None


def background_log_path(task_id: str) -> Path:
    return LOG_DIR / f"background-{task_id}.log"


def start_background_job(route: dict, chat_id: str, task_id: str, send_progress: bool = True) -> str:
    ensure_council_dirs()
    if not task_id:
        return "[AI Council] Nie mogę uruchomić tła bez task_id."
    clean_route = {**route, "task_id": task_id}
    spec_path = save_background_job_spec(clean_route, chat_id, task_id, send_progress=send_progress)
    log_path = background_log_path(task_id)
    command = [
        sys.executable,
        "-X",
        "utf8",
        "-u",
        str(Path(__file__).resolve()),
        "run-background-job",
        "--task-id",
        task_id,
    ]
    popen_kwargs = {
        "cwd": str(PROJECT_DIR),
        "env": operator_env(),
    }
    if os.name == "nt":
        popen_kwargs["creationflags"] = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
    else:
        popen_kwargs["start_new_session"] = True
    try:
        with log_path.open("a", encoding="utf-8", errors="replace") as log_file:
            proc = subprocess.Popen(command, stdout=log_file, stderr=subprocess.STDOUT, **popen_kwargs)
    except Exception as exc:
        update_task_status(task_id, "failed", f"background start failed: {redact_secrets(str(exc))[:220]}")
        return f"[AI Council] Nie udało się uruchomić pracy w tle dla `{task_id}`: {compact_line(redact_secrets(str(exc)), 300)}"

    event = {
        "job_id": f"bg-{task_id}",
        "task_id": task_id,
        "created_at": utc_now(),
        "updated_at": utc_now(),
        "status": "running",
        "command": route.get("command", ""),
        "operators": route.get("operators", []),
        "prompt": route.get("prompt", ""),
        "chat_id_hash": short_hash(chat_id),
        "pid": proc.pid,
        "spec_path": str(spec_path),
        "log_path": str(log_path),
    }
    append_background_job_event(event)
    update_task_status(
        task_id,
        "running_background",
        "background worker started",
        worker_pid=proc.pid,
        spec_path=str(spec_path),
        background_log=str(log_path),
    )
    return (
        f"[AI Council] task-{task_id.split('task-', 1)[-1]}\n"
        "START: praca uruchomiona w tle.\n"
        f"status: /status {task_id}\n"
        f"cancel: /cancel {task_id}\n"
        f"Details: /details {task_id}"
    )


def terminate_pid(pid: int) -> tuple[bool, str]:
    if pid <= 0:
        return False, "invalid pid"
    if os.name == "nt":
        try:
            proc = subprocess.run(
                ["taskkill", "/PID", str(pid), "/T", "/F"],
                text=True,
                encoding="utf-8",
                errors="replace",
                capture_output=True,
                timeout=15,
            )
        except FileNotFoundError:
            return False, "taskkill not found"
        except subprocess.TimeoutExpired:
            return False, "taskkill timeout"
        output = clean_operator_output((proc.stdout or "") + (proc.stderr or ""))
        return proc.returncode == 0, output or f"taskkill exit {proc.returncode}"
    try:
        os.killpg(pid, signal.SIGTERM)
    except ProcessLookupError:
        return True, "process already stopped"
    except PermissionError as exc:
        return False, str(exc)
    except OSError:
        try:
            os.kill(pid, signal.SIGTERM)
        except ProcessLookupError:
            return True, "process already stopped"
        except OSError as exc:
            return False, str(exc)
    return True, "terminate signal sent"


def pid_is_running(pid: int) -> bool:
    if pid <= 0:
        return False
    if os.name == "nt":
        try:
            proc = subprocess.run(
                ["tasklist", "/FI", f"PID eq {pid}", "/FO", "CSV", "/NH"],
                text=True,
                encoding="utf-8",
                errors="replace",
                capture_output=True,
                timeout=10,
            )
        except (FileNotFoundError, subprocess.TimeoutExpired):
            return False
        output = proc.stdout.strip()
        return proc.returncode == 0 and output and "No tasks are running" not in output
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except OSError:
        return False


def reconcile_background_jobs(limit: int = 200) -> list[dict]:
    reconciled: list[dict] = []
    for task in latest_tasks(limit=limit):
        if task.get("status") != "running_background":
            continue
        raw_pid = task.get("worker_pid") or 0
        try:
            pid = int(raw_pid)
        except (TypeError, ValueError):
            pid = 0
        if pid and pid_is_running(pid):
            continue
        note = "orphaned_on_restart: worker pid missing" if not pid else f"orphaned_on_restart: pid {pid} not running"
        updated = update_task_status(task["task_id"], "failed", note, reconciled_at=utc_now())
        event = {
            "job_id": f"bg-{task['task_id']}",
            "task_id": task["task_id"],
            "updated_at": utc_now(),
            "status": "failed",
            "pid": pid,
            "note": note,
        }
        append_background_job_event(event)
        reconciled.append(updated or event)
    return reconciled


def idempotency_key_for(chat_id: str, text: str) -> str:
    normalized = " ".join((text or "").strip().split()).lower()
    return short_hash(f"{chat_id}:{normalized}")


def find_recent_duplicate(idempotency_key: str, window_seconds: int | None = None) -> dict | None:
    if not idempotency_key:
        return None
    window = window_seconds if window_seconds is not None else int_cfg("AI_COUNCIL_IDEMPOTENCY_WINDOW_SECONDS", 90)
    for task in latest_tasks(limit=50):
        if task.get("idempotency_key") != idempotency_key:
            continue
        if task.get("status") in {"failed", "cancelled"}:
            continue
        if seconds_since(str(task.get("created_at", ""))) <= window:
            return task
    return None


def duplicate_response(task: dict) -> str:
    return (
        "[Council] Duplikat zablokowany przez idempotency window.\n"
        f"id: {task.get('task_id')}\n"
        f"status: {task.get('status')}\n"
        "Jeśli chcesz uruchomić ponownie, zmień treść wiadomości albo poczekaj chwilę."
    )


def stuck_tasks(limit: int = 8) -> list[dict]:
    threshold = int_cfg("AI_COUNCIL_STUCK_SECONDS", 900)
    stuck: list[dict] = []
    for task in latest_tasks(limit=100):
        if task.get("status") not in {"running", "running_background"}:
            continue
        stamp = str(task.get("updated_at") or task.get("created_at") or "")
        if seconds_since(stamp) >= threshold:
            stuck.append(task)
    return stuck[:limit]


def task_status_response(task_id: str) -> str:
    task_id = task_id.strip()
    if not task_id:
        return system_status_response()
    task = get_latest_task(task_id)
    if task:
        lines = [
            f"[Council] Task {task_id}",
            f"status: {task.get('status')}",
            f"command: {task.get('command', '')}",
            f"operators: {', '.join(task.get('operators') or [])}",
            f"updated: {task.get('updated_at', task.get('created_at', ''))}",
            f"prompt: {compact_line(task.get('prompt', ''), 220)}",
        ]
        if task.get("note"):
            lines.append(f"note: {compact_line(task.get('note', ''), 220)}")
        if task.get("duration_ms") is not None:
            lines.append(f"duration_ms: {task.get('duration_ms')}")
        if task.get("worker_pid"):
            lines.append(f"worker_pid: {task.get('worker_pid')}")
        if task.get("report_path"):
            lines.append(f"report: {task.get('report_path')}")
        artifact = get_latest_task_artifact(task_id)
        if artifact:
            lines.append(f"details: /details {task_id}")
            lines.append(f"facts: /facts {task_id}")
            lines.append(f"next: /next {task_id}")
        return "\n".join(lines)

    job = get_latest_job(task_id)
    if job:
        return (
            f"[Council] Council job {task_id}\n"
            f"status: {job.get('status')}\n"
            f"updated: {job.get('updated_at', job.get('created_at', ''))}\n"
            f"prompt: {compact_line(job.get('prompt', ''), 220)}\n"
            f"report: {job.get('report_path', '')}"
        )

    action = get_latest_action(task_id)
    if action:
        return (
            f"[Council] Action {task_id}\n"
            f"status: {action.get('status')}\n"
            f"risk: {action.get('risk')}\n"
            f"type: {action.get('type')}\n"
            f"description: {compact_line(action.get('description', ''), 220)}"
        )

    return f"[Council] Nie znalazłem task/job/action `{task_id}`."


def queue_response(limit: int = 6) -> str:
    tasks = latest_tasks(limit=limit)
    if not tasks:
        return "[Council] Kolejka pusta. Dodaj zadanie: /task opis."
    lines = ["[Council] Ostatnie taski:"]
    for task in tasks:
        prompt = task.get("prompt", "").replace("\n", " ")[:80]
        lines.append(f"- {task.get('task_id')} | {task.get('status')} | {prompt}")
    return "\n".join(lines)


def list_recent_files(paths: list[Path], limit: int = 8) -> list[Path]:
    files: list[Path] = []
    for root in paths:
        if not root.exists():
            continue
        files.extend(path for path in root.rglob("*") if path.is_file())
    return sorted(files, key=lambda path: path.stat().st_mtime, reverse=True)[:limit]


def artifacts_response(limit: int = 8) -> str:
    ensure_council_dirs()
    files = list_recent_files(
        [
            ARTIFACTS_DIR,
            REPORTS_DIR,
            CLAUDE_COLLAB_DIR,
        ],
        limit=limit,
    )
    if not files:
        return "[Council] Brak artefaktów. Workspace jest gotowy: D:\\ai-council\\artifacts."
    lines = ["[Council] Ostatnie artefakty/raporty:"]
    for path in files:
        label = str(path)
        if len(label) > 120:
            label = "..." + label[-117:]
        lines.append(f"- {label}")
    return "\n".join(lines)


def task_artifact_dir(task_id: str) -> Path:
    safe_id = re.sub(r"[^a-zA-Z0-9_.-]", "_", task_id.strip())
    return ARTIFACTS_DIR / safe_id


def extract_fact_lines(text: str, limit: int = 3) -> list[str]:
    facts: list[str] = []
    for raw in (text or "").splitlines():
        line = raw.strip(" -\t")
        if not line:
            continue
        if line.startswith("[") and line.endswith("]"):
            continue
        if line.startswith("#"):
            continue
        if line.lower().startswith(("details:", "next:", "decyzja:", "fakty:", "spór:", "spor:", "do ciebie:")):
            continue
        facts.append(compact_line(line, 190))
        if len(facts) >= limit:
            break
    return facts


def default_next_actions(task_id: str, command: str = "") -> list[str]:
    actions = [f"Przejrzyj pełny wynik: /details {task_id}"]
    if command in {"/flow", "@claude-flow", "/council"}:
        actions.append("Wybierz jeden następny krok i poproś AI Council o wdrożenie albo plan akcji.")
    else:
        actions.append("Daj krótką decyzję: kontynuować, zmienić kierunek, czy zatrzymać.")
    return actions


def format_telegram_summary(result: dict, task_id: str) -> str:
    facts = result.get("facts") or []
    next_actions = result.get("next_actions") or []
    fact_lines = [f"{index}. {compact_line(str(fact), 180)}" for index, fact in enumerate(facts[:3], start=1)]
    if not fact_lines:
        fact_lines = ["1. Brak wyodrębnionych faktów; sprawdź szczegóły."]
    next_text = compact_line("; ".join(str(item) for item in next_actions[:3]) or f"/details {task_id}", 240)
    ask_user = result.get("ask_user") or "Potwierdź następny krok albo doprecyzuj priorytet."
    return (
        f"[AI Council] {task_id}\n"
        f"DECYZJA: {compact_line(str(result.get('decision') or 'Zadanie zakończone.'), 240)}\n"
        "FAKTY:\n"
        + "\n".join(fact_lines)
        + "\n"
        f"SPÓR: {compact_line(str(result.get('dispute') or 'Brak istotnego sporu w krótkiej syntezie.'), 240)}\n"
        f"NEXT: {next_text}\n"
        f"DO CIEBIE: {compact_line(str(ask_user), 220)}\n"
        f"Details: /details {task_id}"
    )


def save_task_artifacts(task_id: str, route: dict, result: dict) -> dict:
    ensure_council_dirs()
    artifact_dir = task_artifact_dir(task_id)
    artifact_dir.mkdir(parents=True, exist_ok=True)
    raw_output = str(result.get("raw_output") or result.get("report") or result.get("summary") or "")
    command = str(route.get("command", ""))
    facts = [str(item) for item in (result.get("facts") or extract_fact_lines(raw_output))]
    if not facts:
        facts = ["Wynik został zapisany w szczegółach taska."]
    next_actions = [str(item) for item in (result.get("next_actions") or default_next_actions(task_id, command))]
    normalized = {
        "decision": str(result.get("decision") or "Zadanie zakończone."),
        "facts": facts[:8],
        "dispute": str(result.get("dispute") or ""),
        "next_actions": next_actions[:8],
        "ask_user": str(result.get("ask_user") or "Potwierdź następny krok."),
        "raw_output": raw_output,
        "report": str(result.get("report") or raw_output),
    }
    summary = str(result.get("summary") or format_telegram_summary(normalized, task_id))
    paths = {
        "raw_path": artifact_dir / "raw.md",
        "report_path": artifact_dir / "report.md",
        "summary_path": artifact_dir / "summary.md",
        "facts_path": artifact_dir / "facts.json",
        "next_path": artifact_dir / "next.json",
    }
    paths["raw_path"].write_text(normalized["raw_output"], encoding="utf-8")
    paths["report_path"].write_text(normalized["report"], encoding="utf-8")
    paths["summary_path"].write_text(summary, encoding="utf-8")
    paths["facts_path"].write_text(json.dumps(normalized["facts"], ensure_ascii=False, indent=2), encoding="utf-8")
    paths["next_path"].write_text(json.dumps(normalized["next_actions"], ensure_ascii=False, indent=2), encoding="utf-8")
    index = {
        "artifact_id": f"artifact-{task_id}",
        "task_id": task_id,
        "created_at": utc_now(),
        "updated_at": utc_now(),
        "command": command,
        "operators": route.get("operators", []),
        "decision": normalized["decision"],
        "facts": normalized["facts"],
        "dispute": normalized["dispute"],
        "next_actions": normalized["next_actions"],
        "ask_user": normalized["ask_user"],
        "summary": summary,
        "raw_preview": compact_line(normalized["raw_output"], 500),
        "artifact_dir": str(artifact_dir),
        **{key: str(value) for key, value in paths.items()},
    }
    append_jsonl(ARTIFACT_INDEX_FILE, index)
    memory_save(
        f"artifact:{task_id}",
        f"{normalized['decision']} -> {paths['report_path']}",
        kind="artifact",
        agent="host",
        source="background",
        task_id=task_id,
    )
    return index


def get_latest_task_artifact(task_id: str) -> dict | None:
    task_id = task_id.strip()
    latest = {row.get("task_id"): row for row in read_jsonl(ARTIFACT_INDEX_FILE) if row.get("task_id")}
    return latest.get(task_id)


def details_response(task_id: str) -> str:
    task_id = task_id.strip()
    if not task_id:
        return "[Council] Użyj: /details <task_id>."
    artifact = get_latest_task_artifact(task_id)
    if not artifact:
        return f"[Council] Artefakt dla `{task_id}` nie jest jeszcze gotowy.\n{task_status_response(task_id)}"
    report_path = Path(str(artifact.get("report_path") or ""))
    report = ""
    if report_path.exists():
        report = report_path.read_text(encoding="utf-8", errors="replace")
    preview = report[:2800] if report else str(artifact.get("summary", ""))[:2800]
    return (
        f"[Council] Details {task_id}\n"
        f"decision: {artifact.get('decision')}\n"
        f"report: {artifact.get('report_path')}\n"
        f"raw: {artifact.get('raw_path')}\n\n"
        f"{preview}"
    )


def facts_response(task_id: str) -> str:
    task_id = task_id.strip()
    if not task_id:
        return "[Council] Użyj: /facts <task_id>."
    artifact = get_latest_task_artifact(task_id)
    if not artifact:
        return f"[Council] Fakty dla `{task_id}` nie są jeszcze gotowe.\n{task_status_response(task_id)}"
    facts = artifact.get("facts") or []
    lines = [f"[Council] Facts {task_id}"]
    for index, fact in enumerate(facts[:8], start=1):
        lines.append(f"{index}. {compact_line(str(fact), 240)}")
    return "\n".join(lines)


def next_response(task_id: str) -> str:
    task_id = task_id.strip()
    if not task_id:
        return "[Council] Użyj: /next <task_id>."
    artifact = get_latest_task_artifact(task_id)
    if not artifact:
        return f"[Council] Next dla `{task_id}` nie jest jeszcze gotowe.\n{task_status_response(task_id)}"
    actions = artifact.get("next_actions") or []
    lines = [f"[Council] Next {task_id}"]
    for index, action in enumerate(actions[:8], start=1):
        lines.append(f"{index}. {compact_line(str(action), 240)}")
    return "\n".join(lines)


def today_utc() -> str:
    return datetime.now(timezone.utc).date().isoformat()


def estimated_operator_cost(operator: str) -> float:
    if operator == "grok":
        return float_cfg("AI_COUNCIL_GROK_ESTIMATED_COST_USD", 0.02)
    if operator == "claude-flow":
        return float_cfg("AI_COUNCIL_CLAUDE_FLOW_ESTIMATED_COST_USD", 0.0)
    return float_cfg(f"AI_COUNCIL_{operator.upper().replace('-', '_')}_ESTIMATED_COST_USD", 0.0)


def record_operator_usage(
    operator: str,
    *,
    task_id: str = "",
    status: str = "completed",
    duration_ms: int = 0,
    estimated_usd: float | None = None,
    detail: str = "",
) -> dict:
    event = {
        "usage_id": f"use-{datetime.now().strftime('%Y%m%d-%H%M%S')}-{short_hash(f'{operator}:{task_id}:{time.time()}')[:6]}",
        "created_at": utc_now(),
        "day": today_utc(),
        "operator": operator,
        "task_id": task_id,
        "status": status,
        "duration_ms": duration_ms,
        "estimated_usd": estimated_operator_cost(operator) if estimated_usd is None else estimated_usd,
        "detail": compact_line(detail, 240),
    }
    append_jsonl(COSTS_FILE, event)
    return event


def usage_today(operator: str | None = None) -> list[dict]:
    rows = [row for row in read_jsonl(COSTS_FILE) if row.get("day") == today_utc()]
    if operator:
        rows = [row for row in rows if row.get("operator") == operator]
    return rows


def operator_usage_summary() -> dict[str, dict]:
    summary: dict[str, dict] = {}
    for row in usage_today():
        operator = str(row.get("operator") or "unknown")
        bucket = summary.setdefault(operator, {"calls": 0, "blocked": 0, "duration_ms": 0, "estimated_usd": 0.0})
        if row.get("status") == "blocked":
            bucket["blocked"] += 1
        else:
            bucket["calls"] += 1
        try:
            bucket["duration_ms"] += int(row.get("duration_ms") or 0)
        except (TypeError, ValueError):
            pass
        try:
            bucket["estimated_usd"] += float(row.get("estimated_usd") or 0.0)
        except (TypeError, ValueError):
            pass
    return summary


def operator_call_allowed(operator: str) -> tuple[bool, str]:
    calls = len([row for row in usage_today(operator) if row.get("status") != "blocked"])
    if operator == "grok":
        call_limit = int_cfg("GROK_DAILY_CALL_LIMIT", 0)
        if call_limit and calls >= call_limit:
            return False, f"Grok daily call limit reached: {calls}/{call_limit}"
        budget = float_cfg("GROK_DAILY_BUDGET_USD", 0.0)
        if budget:
            used = sum(float(row.get("estimated_usd") or 0.0) for row in usage_today("grok"))
            next_cost = estimated_operator_cost("grok")
            if used + next_cost > budget:
                return False, f"Grok estimated budget reached: {used:.4f}+{next_cost:.4f}>{budget:.4f} USD"
    if operator == "claude-flow":
        call_limit = int_cfg("AI_COUNCIL_CLAUDE_FLOW_DAILY_CALL_LIMIT", 50)
        if call_limit and calls >= call_limit:
            return False, f"Claude Flow daily call limit reached: {calls}/{call_limit}"
    return True, ""


def cost_response() -> str:
    summary = operator_usage_summary()
    lines = ["[Council] Cost/usage today (UTC)."]
    if not summary:
        lines.append("Brak zapisanych wywołań operatorów dzisiaj.")
    else:
        for operator in sorted(summary):
            item = summary[operator]
            lines.append(
                f"- {operator}: calls={item['calls']} blocked={item['blocked']} "
                f"time={item['duration_ms']}ms est=${item['estimated_usd']:.4f}"
            )
    lines.append(
        "Uwaga: Codex/Claude przez subskrypcję nie zwracają realnego per-call billing z CLI; "
        "Grok ma guard po call limit i estymowanym budżecie z env."
    )
    return "\n".join(lines)


def capabilities_response() -> str:
    ensure_council_dirs()
    return (
        "[Council] Capabilities L2.5 active.\n"
        "Teraz: Telegram, natural intent routing, Codex read-only, Claude quick no-tools, Claude Flow Opus 4.8, Grok research, Grok X research przez xAI x_search, audit, workspaces, task queue, background jobs także dla zwykłych wiadomości, real cancel PID, artifact index, /details, /facts, /next, /health, actions, memory auto-recall, structured council v0, approved workspace write/append/patch, task status/cost/idempotency/stuck detection.\n"
        "Workspace: D:\\ai-council\\workspaces\\{codex,claude,grok,shared}; artefakty: D:\\ai-council\\artifacts.\n"
        "Komendy i naturalne frazy: status, status <id>, details/fakty/next <id>, koszty, cancel/anuluj <id>, kolejka, pamięć, actions, approve/deny, /write, /append, /patch, /flow, /council, @xresearch, /xresearch, /poke-research.\n"
        "Nadal zablokowane bez approval: shell execute, zapis poza workspace, kontakty, publikacja, kasowanie, pieniądze, DNS/auth/billing."
    )


def system_status_response() -> str:
    stuck = stuck_tasks(limit=3)
    usage = operator_usage_summary()
    usage_bits = []
    for operator in sorted(usage):
        usage_bits.append(f"{operator}:{usage[operator]['calls']}")
    usage_text = ", ".join(usage_bits) if usage_bits else "brak wywołań dzisiaj"
    stuck_text = "brak" if not stuck else ", ".join(task.get("task_id", "") for task in stuck)
    return (
        "[Council] Online na Desktopie 24/7. L2.5 active: natural intent routing, memory auto-recall, actions, background jobs, artifact index, structured council v0, approved workspace write/append/patch, @claude-flow Opus 4.8, task status/cancel/cost/idempotency/stuck detection.\n"
        "Domyślnie: zwykła wiadomość -> Codex read-only w tle; @claude -> Claude quick bez narzędzi; @claude-flow lub /flow -> Claude Opus 4.8 plan workflow w tle; @grok/@research -> Grok w tle; @xresearch lub /poke-research -> Grok X search w tle; brak shell/external actions bez approval.\n"
        f"Usage today: {usage_text}. Stuck: {stuck_text}.\n"
        "Komendy L2.5: /health, /status <task_id>, /details <task_id>, /facts <task_id>, /next <task_id>, /cancel <task_id>, /cost, /xresearch, /poke-research."
    )


def health_response() -> str:
    ensure_council_dirs()
    status = operator_binary_status()
    running = [task for task in latest_tasks(limit=50) if task.get("status") in {"running", "running_background"}]
    stuck = stuck_tasks(limit=5)
    offset = read_offset()
    lines = [
        "[Council] Health",
        f"project: {PROJECT_DIR}",
        f"env: {'OK' if ENV_PATH.exists() else 'missing'}",
        f"telegram_offset: {offset if offset is not None else 'none'}",
        f"running_tasks: {len(running)}",
        f"stuck_tasks: {len(stuck)}",
    ]
    for name, item in status.items():
        marker = "OK" if item.get("configured") else "missing"
        extra = ""
        if name == "claude_flow":
            extra = f" model={item.get('model')} mode={item.get('permission_mode')}"
        lines.append(f"{name}: {marker}{extra}")
    if stuck:
        lines.append("stuck: " + ", ".join(task.get("task_id", "") for task in stuck))
    lines.append("quick_check: jeśli zwykła wiadomość wraca jako task_id, polling nie jest blokowany.")
    return "\n".join(lines)


def init_memory_db() -> None:
    ensure_council_dirs()
    with sqlite3.connect(MEMORY_DB) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS memory_entries (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                entry_id TEXT UNIQUE NOT NULL,
                created_at TEXT NOT NULL,
                kind TEXT NOT NULL,
                agent TEXT NOT NULL,
                key TEXT NOT NULL,
                value TEXT NOT NULL,
                source TEXT NOT NULL,
                task_id TEXT
            )
            """
        )
        try:
            conn.execute(
                """
                CREATE VIRTUAL TABLE IF NOT EXISTS memory_fts
                USING fts5(entry_id, kind, agent, key, value, source)
                """
            )
        except sqlite3.OperationalError:
            # Some SQLite builds can miss FTS5. LIKE fallback still works.
            pass


def memory_save(
    key: str,
    value: str,
    *,
    kind: str = "note",
    agent: str = "host",
    source: str = "telegram",
    task_id: str = "",
) -> dict:
    init_memory_db()
    clean_key = key.strip() or "note"
    clean_value = value.strip() or "(empty)"
    entry_id = f"mem-{datetime.now().strftime('%Y%m%d-%H%M%S')}-{short_hash(clean_key + clean_value)[:6]}"
    row = {
        "entry_id": entry_id,
        "created_at": utc_now(),
        "kind": kind,
        "agent": agent,
        "key": clean_key,
        "value": clean_value,
        "source": source,
        "task_id": task_id,
    }
    with sqlite3.connect(MEMORY_DB) as conn:
        conn.execute(
            """
            INSERT OR REPLACE INTO memory_entries
            (entry_id, created_at, kind, agent, key, value, source, task_id)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                row["entry_id"],
                row["created_at"],
                row["kind"],
                row["agent"],
                row["key"],
                row["value"],
                row["source"],
                row["task_id"],
            ),
        )
        try:
            conn.execute(
                """
                INSERT INTO memory_fts (entry_id, kind, agent, key, value, source)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (entry_id, kind, agent, clean_key, clean_value, source),
            )
        except sqlite3.OperationalError:
            pass
    audit(
        {
            "command": "/memory",
            "operators": ["host"],
            "status": "saved",
            "duration_ms": 0,
            "memory_id": entry_id,
            "output_preview": clean_value[:300],
        }
    )
    return row


def memory_recent(limit: int = 8) -> list[dict]:
    init_memory_db()
    with sqlite3.connect(MEMORY_DB) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            """
            SELECT entry_id, created_at, kind, agent, key, value, source, task_id
            FROM memory_entries
            ORDER BY id DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
        result = [dict(row) for row in rows]
    return result


def memory_search(query: str, limit: int = 8) -> list[dict]:
    init_memory_db()
    clean_query = query.strip()
    if not clean_query:
        return memory_recent(limit)
    with sqlite3.connect(MEMORY_DB) as conn:
        conn.row_factory = sqlite3.Row
        try:
            phrase = '"' + clean_query.replace('"', '""') + '"'
            rows = conn.execute(
                """
                SELECT e.entry_id, e.created_at, e.kind, e.agent, e.key, e.value, e.source, e.task_id
                FROM memory_fts f
                JOIN memory_entries e ON e.entry_id = f.entry_id
                WHERE memory_fts MATCH ?
                ORDER BY e.id DESC
                LIMIT ?
                """,
                (phrase, limit),
            ).fetchall()
        except sqlite3.OperationalError:
            like = f"%{clean_query}%"
            rows = conn.execute(
                """
                SELECT entry_id, created_at, kind, agent, key, value, source, task_id
                FROM memory_entries
                WHERE key LIKE ? OR value LIKE ? OR agent LIKE ? OR kind LIKE ?
                ORDER BY id DESC
                LIMIT ?
                """,
                (like, like, like, like, limit),
            ).fetchall()
        result = [dict(row) for row in rows]
    return result


def memory_context_for_prompt(prompt: str, limit: int = 3) -> str:
    try:
        rows = memory_search(prompt, limit=limit)
    except Exception:
        return ""
    lines = []
    for row in rows:
        lines.append(f"- {row.get('agent', 'host')} | {compact_line(row.get('key', ''), 48)}: {compact_line(row.get('value', ''), 180)}")
    return "\n".join(lines)


def memory_response(prompt: str) -> str:
    stripped = prompt.strip()
    lower = stripped.lower()
    if not stripped or lower == "recent":
        rows = memory_recent()
        if not rows:
            return "[Council] Memory puste. Dodaj: /memory save klucz = treść."
        lines = ["[Council] Memory recent:"]
        for row in rows:
            lines.append(
                f"- {row['entry_id']} | {row['agent']} | {compact_line(row['key'], 36)}: {compact_line(row['value'], 90)}"
            )
        return "\n".join(lines)
    if lower.startswith("search"):
        query = stripped[6:].strip()
        rows = memory_search(query)
        if not rows:
            return f"[Council] Memory search: brak wyników dla `{query}`."
        lines = [f"[Council] Memory search `{query}`:"]
        for row in rows:
            lines.append(
                f"- {row['entry_id']} | {row['agent']} | {compact_line(row['key'], 36)}: {compact_line(row['value'], 90)}"
            )
        return "\n".join(lines)
    if lower.startswith("save"):
        body = stripped[4:].strip()
        if "=" in body:
            key, value = body.split("=", 1)
        else:
            key, value = "note", body
        row = memory_save(key, value)
        return f"[Council] Memory saved: {row['entry_id']} | {compact_line(row['key'], 60)}."
    return "[Council] Memory: użyj /memory recent, /memory search <tekst>, /memory save klucz = treść."


def create_action(description: str, *, action_type: str = "manual", risk: str = "medium", payload: dict | None = None) -> dict:
    ensure_council_dirs()
    clean_description = description.strip() or "Brak opisu akcji"
    action_id = f"act-{datetime.now().strftime('%Y%m%d-%H%M%S')}-{short_hash(clean_description)[:6]}"
    action = {
        "action_id": action_id,
        "created_at": utc_now(),
        "updated_at": utc_now(),
        "status": "pending",
        "type": action_type,
        "risk": risk,
        "description": clean_description,
        "path_scope": "D:\\ai-council\\workspaces only",
        "execution": "not_implemented_l2_mini",
        "payload": payload or {},
    }
    append_jsonl(ACTIONS_FILE, action)
    audit(
        {
            "command": "/actions",
            "operators": ["host"],
            "status": "pending",
            "duration_ms": 0,
            "action_id": action_id,
            "output_preview": clean_description[:300],
        }
    )
    return action


def get_latest_action(action_id: str) -> dict | None:
    action_id = action_id.strip()
    latest = {row.get("action_id"): row for row in read_jsonl(ACTIONS_FILE) if row.get("action_id")}
    return latest.get(action_id)


def resolve_workspace_path(raw_path: str) -> tuple[Path | None, str]:
    ensure_council_dirs()
    clean = raw_path.strip().strip('"').strip("'").replace("\\", "/")
    if not clean:
        return None, "empty path"
    if "\x00" in clean:
        return None, "invalid path"
    candidate = Path(clean)
    if not candidate.is_absolute():
        if "/" not in clean:
            candidate = WORKSPACES_DIR / "shared" / candidate
        else:
            candidate = WORKSPACES_DIR / candidate
    try:
        target = candidate.resolve()
        workspace_root = WORKSPACES_DIR.resolve()
        target.relative_to(workspace_root)
    except (OSError, ValueError):
        return None, "path outside D:\\ai-council\\workspaces"
    if target.is_dir():
        return None, "target is a directory"
    return target, ""


def unified_diff_preview(path: Path, new_content: str, limit: int = 1600) -> str:
    old_content = ""
    if path.exists():
        old_content = path.read_text(encoding="utf-8", errors="replace")
    diff = difflib.unified_diff(
        old_content.splitlines(),
        new_content.splitlines(),
        fromfile=str(path),
        tofile=str(path),
        lineterm="",
        n=3,
    )
    preview = "\n".join(diff)
    if not preview:
        preview = "(no textual diff)"
    if len(preview) > limit:
        preview = preview[: limit - 20] + "\n...diff truncated..."
    return preview


def parse_workspace_write_prompt(prompt: str) -> tuple[str, str] | None:
    body = prompt.strip()
    if not body:
        return None
    for prefix in ["plik ", "file "]:
        if body.lower().startswith(prefix):
            body = body[len(prefix) :].strip()
            break
    if "=" in body:
        path_part, content = body.split("=", 1)
        return path_part.strip(), content.lstrip()
    if "\n" in body:
        path_part, content = body.split("\n", 1)
        return path_part.strip(), content
    return None


def parse_workspace_append_prompt(prompt: str) -> tuple[str, str] | None:
    body = prompt.strip()
    if not body:
        return None
    for prefix in ["plik ", "file "]:
        if body.lower().startswith(prefix):
            body = body[len(prefix) :].strip()
            break
    if "=" in body:
        path_part, content = body.split("=", 1)
        if content.startswith(" "):
            content = content[1:]
        return path_part.strip(), content
    if "\n" in body:
        path_part, content = body.split("\n", 1)
        return path_part.strip(), content
    return None


def parse_workspace_patch_prompt(prompt: str) -> tuple[str, str, str] | None:
    body = prompt.strip()
    if not body:
        return None
    for prefix in ["plik ", "file "]:
        if body.lower().startswith(prefix):
            body = body[len(prefix) :].strip()
            break
    separator = "::" if "::" in body else "=" if "=" in body else ""
    if not separator:
        return None
    path_part, change = body.split(separator, 1)
    if "=>" not in change:
        return None
    old, new = change.split("=>", 1)
    return path_part.strip(), old.strip(), new.strip()


def create_workspace_write_action(prompt: str) -> dict | None:
    parsed = parse_workspace_write_prompt(prompt)
    if not parsed:
        return None
    raw_path, content = parsed
    if len(content) > WORKSPACE_WRITE_MAX_CHARS:
        return create_action(
            f"Rejected workspace write: content too large for {raw_path}",
            action_type="workspace_write_rejected",
            risk="high",
            payload={"raw_path": raw_path, "reason": "content too large"},
        )
    target, error = resolve_workspace_path(raw_path)
    if error or target is None:
        return create_action(
            f"Rejected workspace write: {raw_path} ({error})",
            action_type="workspace_write_rejected",
            risk="high",
            payload={"raw_path": raw_path, "reason": error},
        )
    diff_preview = unified_diff_preview(target, content)
    return create_action(
        f"Write workspace file {target}",
        action_type="workspace_write",
        risk="low",
        payload={
            "path": str(target),
            "content": content,
            "diff_preview": diff_preview,
            "max_chars": WORKSPACE_WRITE_MAX_CHARS,
        },
    )


def create_workspace_append_action(prompt: str) -> dict | None:
    parsed = parse_workspace_append_prompt(prompt)
    if not parsed:
        return None
    raw_path, append_content = parsed
    if len(append_content) > WORKSPACE_WRITE_MAX_CHARS:
        return create_action(
            f"Rejected workspace append: content too large for {raw_path}",
            action_type="workspace_append_rejected",
            risk="high",
            payload={"raw_path": raw_path, "reason": "content too large"},
        )
    target, error = resolve_workspace_path(raw_path)
    if error or target is None:
        return create_action(
            f"Rejected workspace append: {raw_path} ({error})",
            action_type="workspace_append_rejected",
            risk="high",
            payload={"raw_path": raw_path, "reason": error},
        )
    old_content = target.read_text(encoding="utf-8", errors="replace") if target.exists() else ""
    new_content = old_content + append_content
    diff_preview = unified_diff_preview(target, new_content)
    return create_action(
        f"Append workspace file {target}",
        action_type="workspace_append",
        risk="low",
        payload={
            "path": str(target),
            "append_content": append_content,
            "diff_preview": diff_preview,
            "max_chars": WORKSPACE_WRITE_MAX_CHARS,
        },
    )


def create_workspace_patch_action(prompt: str) -> dict | None:
    parsed = parse_workspace_patch_prompt(prompt)
    if not parsed:
        return None
    raw_path, old, new = parsed
    target, error = resolve_workspace_path(raw_path)
    if error or target is None:
        return create_action(
            f"Rejected workspace patch: {raw_path} ({error})",
            action_type="workspace_patch_rejected",
            risk="high",
            payload={"raw_path": raw_path, "reason": error},
        )
    if not target.exists():
        return create_action(
            f"Rejected workspace patch: {target} does not exist",
            action_type="workspace_patch_rejected",
            risk="high",
            payload={"path": str(target), "reason": "file does not exist"},
        )
    current = target.read_text(encoding="utf-8", errors="replace")
    if not old:
        return create_action(
            f"Rejected workspace patch: empty old text for {target}",
            action_type="workspace_patch_rejected",
            risk="high",
            payload={"path": str(target), "reason": "empty old text"},
        )
    if old not in current:
        return create_action(
            f"Rejected workspace patch: old text not found in {target}",
            action_type="workspace_patch_rejected",
            risk="high",
            payload={"path": str(target), "reason": "old text not found"},
        )
    new_content = current.replace(old, new, 1)
    if len(new_content) > WORKSPACE_WRITE_MAX_CHARS:
        return create_action(
            f"Rejected workspace patch: content too large for {target}",
            action_type="workspace_patch_rejected",
            risk="high",
            payload={"path": str(target), "reason": "content too large"},
        )
    diff_preview = unified_diff_preview(target, new_content)
    return create_action(
        f"Patch workspace file {target}",
        action_type="workspace_patch",
        risk="low",
        payload={
            "path": str(target),
            "old": old,
            "new": new,
            "diff_preview": diff_preview,
            "max_chars": WORKSPACE_WRITE_MAX_CHARS,
        },
    )


def execute_workspace_write_action(action: dict) -> dict:
    payload = action.get("payload") or {}
    target, error = resolve_workspace_path(str(payload.get("path", "")))
    if error or target is None:
        executed = {
            **action,
            "status": "failed",
            "updated_at": utc_now(),
            "execution_result": f"blocked: {error}",
        }
        append_jsonl(ACTIONS_FILE, executed)
        return executed
    content = str(payload.get("content", ""))
    if len(content) > WORKSPACE_WRITE_MAX_CHARS:
        executed = {
            **action,
            "status": "failed",
            "updated_at": utc_now(),
            "execution_result": "blocked: content too large",
        }
        append_jsonl(ACTIONS_FILE, executed)
        return executed
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")
    executed = {
        **action,
        "status": "executed",
        "updated_at": utc_now(),
        "execution_result": f"wrote {target}",
    }
    append_jsonl(ACTIONS_FILE, executed)
    memory_save(
        f"workspace-write:{action.get('action_id')}",
        f"{target}",
        kind="action",
        agent="host",
        source="approval",
        task_id=action.get("action_id", ""),
    )
    return executed


def execute_workspace_append_action(action: dict) -> dict:
    payload = action.get("payload") or {}
    target, error = resolve_workspace_path(str(payload.get("path", "")))
    if error or target is None:
        executed = {**action, "status": "failed", "updated_at": utc_now(), "execution_result": f"blocked: {error}"}
        append_jsonl(ACTIONS_FILE, executed)
        return executed
    append_content = str(payload.get("append_content", ""))
    old_content = target.read_text(encoding="utf-8", errors="replace") if target.exists() else ""
    new_content = old_content + append_content
    if len(new_content) > WORKSPACE_WRITE_MAX_CHARS:
        executed = {**action, "status": "failed", "updated_at": utc_now(), "execution_result": "blocked: content too large"}
        append_jsonl(ACTIONS_FILE, executed)
        return executed
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(new_content, encoding="utf-8")
    executed = {**action, "status": "executed", "updated_at": utc_now(), "execution_result": f"appended {target}"}
    append_jsonl(ACTIONS_FILE, executed)
    memory_save(f"workspace-append:{action.get('action_id')}", f"{target}", kind="action", agent="host", source="approval", task_id=action.get("action_id", ""))
    return executed


def execute_workspace_patch_action(action: dict) -> dict:
    payload = action.get("payload") or {}
    target, error = resolve_workspace_path(str(payload.get("path", "")))
    if error or target is None:
        executed = {**action, "status": "failed", "updated_at": utc_now(), "execution_result": f"blocked: {error}"}
        append_jsonl(ACTIONS_FILE, executed)
        return executed
    if not target.exists():
        executed = {**action, "status": "failed", "updated_at": utc_now(), "execution_result": "blocked: file does not exist"}
        append_jsonl(ACTIONS_FILE, executed)
        return executed
    old = str(payload.get("old", ""))
    new = str(payload.get("new", ""))
    current = target.read_text(encoding="utf-8", errors="replace")
    if not old or old not in current:
        executed = {**action, "status": "failed", "updated_at": utc_now(), "execution_result": "blocked: old text not found"}
        append_jsonl(ACTIONS_FILE, executed)
        return executed
    new_content = current.replace(old, new, 1)
    if len(new_content) > WORKSPACE_WRITE_MAX_CHARS:
        executed = {**action, "status": "failed", "updated_at": utc_now(), "execution_result": "blocked: content too large"}
        append_jsonl(ACTIONS_FILE, executed)
        return executed
    target.write_text(new_content, encoding="utf-8")
    executed = {**action, "status": "executed", "updated_at": utc_now(), "execution_result": f"patched {target}"}
    append_jsonl(ACTIONS_FILE, executed)
    memory_save(f"workspace-patch:{action.get('action_id')}", f"{target}", kind="action", agent="host", source="approval", task_id=action.get("action_id", ""))
    return executed


def update_action_status(action_id: str, status: str, note: str = "") -> dict | None:
    action_id = action_id.strip()
    current = get_latest_action(action_id)
    if not current:
        return None
    updated = {**current, "status": status, "updated_at": utc_now(), "decision_note": note}
    append_jsonl(ACTIONS_FILE, updated)
    audit(
        {
            "command": f"/{status}",
            "operators": ["host"],
            "status": status,
            "duration_ms": 0,
            "action_id": action_id,
            "output_preview": note[:300],
        }
    )
    return updated


def actions_response(limit: int = 8) -> str:
    actions = latest_by_id(ACTIONS_FILE, "action_id", limit=limit)
    if not actions:
        return "[Council] Brak pending actions. Dodaj ręcznie: /propose opis akcji albo /write path = content."
    lines = ["[Council] Actions:"]
    for action in actions:
        lines.append(
            f"- {action.get('action_id')} | {action.get('status')} | {action.get('risk')} | {action.get('type')} | {compact_line(action.get('description', ''), 90)}"
        )
        diff_preview = (action.get("payload") or {}).get("diff_preview")
        if diff_preview and action.get("status") == "pending":
            lines.append("  diff: " + compact_line(diff_preview, 220))
    return "\n".join(lines)


def approve_response(prompt: str) -> str:
    parts = prompt.strip().split(maxsplit=1)
    if not parts:
        return "[Council] Użyj: /approve <action_id>."
    current = get_latest_action(parts[0])
    if not current:
        return f"[Council] Nie znalazłem action `{parts[0]}`."
    if current.get("status") not in {"pending", "approved"}:
        return f"[Council] Action `{parts[0]}` ma status `{current.get('status')}`."
    updated = update_action_status(parts[0], "approved", parts[1] if len(parts) > 1 else "")
    if not updated:
        return f"[Council] Nie znalazłem action `{parts[0]}`."
    if updated.get("type") == "workspace_write" and updated.get("risk") == "low":
        executed = execute_workspace_write_action(updated)
        if executed.get("status") == "executed":
            return f"[Council] Approved + executed: {executed['action_id']}.\n{executed.get('execution_result')}"
        return f"[Council] Approved, ale wykonanie zablokowane: {executed.get('execution_result')}"
    if updated.get("type") == "workspace_append" and updated.get("risk") == "low":
        executed = execute_workspace_append_action(updated)
        if executed.get("status") == "executed":
            return f"[Council] Approved + executed: {executed['action_id']}.\n{executed.get('execution_result')}"
        return f"[Council] Approved, ale wykonanie zablokowane: {executed.get('execution_result')}"
    if updated.get("type") == "workspace_patch" and updated.get("risk") == "low":
        executed = execute_workspace_patch_action(updated)
        if executed.get("status") == "executed":
            return f"[Council] Approved + executed: {executed['action_id']}.\n{executed.get('execution_result')}"
        return f"[Council] Approved, ale wykonanie zablokowane: {executed.get('execution_result')}"
    return (
        f"[Council] Approved: {updated['action_id']}.\n"
        "Ta akcja nie ma automatycznego wykonania w L2.5."
    )


def deny_response(prompt: str) -> str:
    parts = prompt.strip().split(maxsplit=1)
    if not parts:
        return "[Council] Użyj: /deny <action_id>."
    updated = update_action_status(parts[0], "denied", parts[1] if len(parts) > 1 else "")
    if not updated:
        return f"[Council] Nie znalazłem action `{parts[0]}`."
    return f"[Council] Denied: {updated['action_id']}."


def write_response(prompt: str) -> str:
    action = create_workspace_write_action(prompt)
    if not action:
        return "[Council] Użyj: /write relative/path.txt = treść pliku."
    if action.get("type") == "workspace_write_rejected":
        return (
            "[Council] Workspace write zablokowany i zapisany jako action wysokiego ryzyka.\n"
            f"id: {action['action_id']}\n"
            f"powód: {(action.get('payload') or {}).get('reason')}"
        )
    diff_preview = (action.get("payload") or {}).get("diff_preview", "")
    return (
        "[Council] Pending workspace write utworzony.\n"
        f"id: {action['action_id']}\n"
        f"approve: /approve {action['action_id']}\n"
        f"diff:\n{diff_preview[:1200]}"
    )


def append_response(prompt: str) -> str:
    action = create_workspace_append_action(prompt)
    if not action:
        return "[Council] Użyj: /append relative/path.txt = tekst do dopisania."
    if action.get("type") == "workspace_append_rejected":
        return (
            "[Council] Workspace append zablokowany i zapisany jako action wysokiego ryzyka.\n"
            f"id: {action['action_id']}\n"
            f"powód: {(action.get('payload') or {}).get('reason')}"
        )
    diff_preview = (action.get("payload") or {}).get("diff_preview", "")
    return (
        "[Council] Pending workspace append utworzony.\n"
        f"id: {action['action_id']}\n"
        f"approve: /approve {action['action_id']}\n"
        f"diff:\n{diff_preview[:1200]}"
    )


def patch_response(prompt: str) -> str:
    action = create_workspace_patch_action(prompt)
    if not action:
        return "[Council] Użyj: /patch relative/path.txt :: stary tekst => nowy tekst."
    if action.get("type") == "workspace_patch_rejected":
        return (
            "[Council] Workspace patch zablokowany i zapisany jako action wysokiego ryzyka.\n"
            f"id: {action['action_id']}\n"
            f"powód: {(action.get('payload') or {}).get('reason')}"
        )
    diff_preview = (action.get("payload") or {}).get("diff_preview", "")
    return (
        "[Council] Pending workspace patch utworzony.\n"
        f"id: {action['action_id']}\n"
        f"approve: /approve {action['action_id']}\n"
        f"diff:\n{diff_preview[:1200]}"
    )


def append_job_event(job: dict) -> None:
    append_jsonl(COUNCIL_JOBS_FILE, job)


def get_latest_job(job_id: str) -> dict | None:
    job_id = job_id.strip()
    latest = {row.get("job_id"): row for row in read_jsonl(COUNCIL_JOBS_FILE) if row.get("job_id")}
    return latest.get(job_id)


def is_cancelled_id(item_id: str) -> bool:
    task = get_latest_task(item_id)
    if task and task.get("status") == "cancelled":
        return True
    job = get_latest_job(item_id)
    return bool(job and job.get("status") == "cancelled")


def cancel_response(prompt: str) -> str:
    target_id = prompt.strip().split()[0] if prompt.strip() else ""
    if not target_id:
        return "[Council] Użyj: /cancel <task_id|job_id>."

    task = get_latest_task(target_id)
    job = get_latest_job(target_id)
    background_job = get_latest_background_job(target_id)
    action = get_latest_action(target_id)
    changed = []
    kill_note = ""
    if task:
        previous_status = str(task.get("status") or "")
        if previous_status in {"completed", "failed", "cancelled"}:
            return f"[Council] Cancel pominięty: {target_id} ma status `{previous_status}`."
        active = previous_status in {"queued", "running", "running_background"}
        update_task_status(target_id, "cancelled", "cancel requested by Bartek")
        changed.append("task")
        raw_pid = task.get("worker_pid") or (background_job or {}).get("pid") or 0
        try:
            pid = int(raw_pid)
        except (TypeError, ValueError):
            pid = 0
        if pid and active:
            killed, detail = terminate_pid(pid)
            kill_note = f"pid {pid}: {'killed' if killed else 'kill_failed'} ({compact_line(detail, 180)})"
            append_background_job_event(
                {
                    **(background_job or {"job_id": f"bg-{target_id}", "task_id": target_id}),
                    "status": "cancelled",
                    "updated_at": utc_now(),
                    "pid": pid,
                    "note": kill_note,
                }
            )
        elif pid:
            kill_note = f"pid {pid}: not killed because task status was `{previous_status}`"
    if job:
        append_job_event({**job, "status": "cancelled", "updated_at": utc_now(), "note": "cancel requested by Bartek"})
        changed.append("job")
    if action and action.get("status") == "pending":
        update_action_status(target_id, "denied", "cancel requested by Bartek")
        changed.append("action")

    if not changed:
        return f"[Council] Nie znalazłem aktywnego task/job/action `{target_id}`."
    suffix = f"\n{kill_note}" if kill_note else "\nbrak aktywnego PID workera do zabicia"
    return f"[Council] Cancel zapisany: {target_id} ({', '.join(changed)}).{suffix}"


def council_jobs_response(limit: int = 6) -> str:
    jobs = latest_by_id(COUNCIL_JOBS_FILE, "job_id", limit=limit)
    if not jobs:
        return "[Council] Brak council jobs. Uruchom: /council opis zadania."
    lines = ["[Council] Council jobs:"]
    for job in jobs:
        lines.append(
            f"- {job.get('job_id')} | {job.get('status')} | {compact_line(job.get('prompt', ''), 76)}"
        )
    return "\n".join(lines)


def build_council_report(job: dict) -> str:
    prompt = job["prompt"]
    remembered = memory_search(prompt, limit=5)
    memory_lines = [
        f"- {row['agent']} | {compact_line(row['key'], 60)}: {compact_line(row['value'], 160)}"
        for row in remembered
    ]
    if not memory_lines:
        memory_lines = ["- brak trafień"]

    task_id = str(job.get("task_id") or job.get("job_id") or "")
    grok = grok_response(build_research_prompt(prompt), max_chars=2200, task_id=task_id)
    claude = claude_response(
        "Zrób krótki plan albo krytykę dla zadania AI Council. "
        "Maks 6 punktów, bez narzędzi.\n\n"
        f"Zadanie: {prompt}",
        task_id=task_id,
    )
    codex = codex_response(
        "Oceń technicznie zadanie dla AI Council w trybie read-only. "
        "Maks 6 punktów, skup się na ryzykach i następnym patchu.\n\n"
        f"Zadanie: {prompt}",
        task_id=task_id,
    )

    return (
        f"# AI Council report: {job['job_id']}\n\n"
        f"Created: {utc_now()}\n\n"
        f"## Task\n\n{prompt}\n\n"
        "## Memory recall\n\n"
        + "\n".join(memory_lines)
        + "\n\n## Grok research\n\n"
        + grok
        + "\n\n## Claude plan/review\n\n"
        + claude
        + "\n\n## Codex technical check\n\n"
        + codex
        + "\n\n## Host decision\n\n"
        "Następny krok powinien zostać zapisany jako pending action i zatwierdzony przez /approve przed write/execute.\n"
    )


def build_structured_council_result(prompt: str, task_id: str = "") -> dict:
    clean_prompt = prompt.strip() or "Oceń AI Council i zaproponuj następny najlepszy krok."
    remembered = memory_search(clean_prompt, limit=5)
    memory_lines = [
        f"- {row['agent']} | {compact_line(row['key'], 60)}: {compact_line(row['value'], 160)}"
        for row in remembered
    ]
    if not memory_lines:
        memory_lines = ["- brak trafień"]

    host_brief = (
        "Cel: przygotować krótką, operacyjną decyzję dla Bartka.\n"
        "Granice Sprintu 1: messaging core, background jobs, cancel, artifacts; bez shell execute, iMessage, Shortcuts i external write.\n"
        f"Zadanie: {clean_prompt}"
    )
    claude = claude_response(
        "AI Council structured v0. Rola: Claude propose.\n"
        "Zaproponuj plan lub decyzję w maks 7 punktach. Nie używaj narzędzi ani zewnętrznych zapisów.\n\n"
        f"{host_brief}",
        task_id=task_id,
    )
    grok = grok_response(
        "AI Council structured v0. Rola: Grok research/red-team.\n"
        "Daj brief research i red-team po polsku: fakty, ryzyka, niepewności, czego nie wiemy.\n\n"
        f"Zadanie: {clean_prompt}",
        max_chars=2200,
        task_id=task_id,
    )
    codex = codex_response(
        "AI Council structured v0. Rola: Codex feasibility.\n"
        "Oceń wykonalność techniczną w trybie read-only. Podaj ryzyka, minimalny następny patch i kryteria testu.\n\n"
        f"{host_brief}",
        task_id=task_id,
    )
    facts = extract_fact_lines("\n".join([grok, claude, codex]), limit=3)
    if len(facts) < 3:
        fallback_facts = [
            "Claude przygotował propozycję rozwiązania.",
            "Grok dostarczył research/red-team i ryzyka.",
            "Codex ocenił wykonalność oraz najbliższy bezpieczny patch.",
        ]
        facts.extend(fallback_facts[len(facts) : 3])
    next_actions = [
        f"Przejrzyj pełny raport: /details {task_id}" if task_id else "Przejrzyj pełny raport w artifacts.",
        "Wybierz jeden najbliższy krok do wdrożenia lub poproś o doprecyzowanie decyzji.",
        "Jeśli krok ma skutki uboczne, przeprowadź go przez pending action i approval.",
    ]
    decision = (
        "Kontynuować małym, weryfikowalnym krokiem: najpierw stabilny messaging/background/artifact core, "
        "dopiero potem execution i integracje."
    )
    dispute = "Grok ma rolę red-team/research, Claude proponuje plan, Codex ogranicza go do wykonalnego i testowalnego kroku."
    ask_user = "Wskaż, który NEXT mam wdrożyć jako kolejny albo napisz, że mam kontynuować według decyzji."
    report = (
        f"# Structured AI Council v0: {task_id or 'manual'}\n\n"
        f"Created: {utc_now()}\n\n"
        f"## Host brief\n\n{host_brief}\n\n"
        "## Memory recall\n\n"
        + "\n".join(memory_lines)
        + "\n\n## Claude propose\n\n"
        + claude
        + "\n\n## Grok research/red-team\n\n"
        + grok
        + "\n\n## Codex feasibility\n\n"
        + codex
        + "\n\n## Host decision\n\n"
        + decision
        + "\n\n## Facts\n\n"
        + "\n".join(f"- {fact}" for fact in facts)
        + "\n\n## Next actions\n\n"
        + "\n".join(f"- {action}" for action in next_actions)
        + "\n"
    )
    result = {
        "decision": decision,
        "facts": facts,
        "dispute": dispute,
        "next_actions": next_actions,
        "ask_user": ask_user,
        "raw_output": report,
        "report": report,
    }
    result["summary"] = format_telegram_summary(result, task_id or "manual")
    return result


def execute_route_for_background(route: dict, chat_id: str, task_id: str) -> dict:
    command = route.get("command")
    worker_route = {**route, "task_id": task_id, "background_worker": True}
    if command == "/multi":
        child_results = []
        raw_parts = []
        for child in route.get("routes", []):
            child_result = execute_route_for_background({**child, "task_id": task_id}, chat_id, task_id)
            child_results.append(child_result)
            raw_parts.append(str(child_result.get("raw_output") or child_result.get("summary") or ""))
        raw = "\n\n".join(raw_parts)
        facts = extract_fact_lines(raw, limit=3)
        return {
            "decision": "Zakończono wielokrokową pracę w tle.",
            "facts": facts,
            "dispute": "Brak jednej ścieżki sporu; wynik zawiera kilka komend.",
            "next_actions": default_next_actions(task_id, command),
            "ask_user": "Sprawdź szczegóły i wskaż, który wynik kontynuować.",
            "raw_output": raw,
            "report": raw,
        }
    if command == "/council":
        return build_structured_council_result(str(route.get("prompt", "")), task_id=task_id)
    response = build_response(worker_route, chat_id=chat_id)
    facts = extract_fact_lines(response, limit=3)
    direct_summary = f"{response}\n\n[AI Council]\ntask: {task_id}\nDetails: /details {task_id}"
    return {
        "decision": "Zadanie zakończone i zapisane jako artifact.",
        "facts": facts or ["Operator zwrócił wynik zapisany w szczegółach."],
        "dispute": "Brak structured council; użyto wskazanego operatora/trybu.",
        "next_actions": default_next_actions(task_id, command),
        "ask_user": "Sprawdź wynik i zdecyduj, czy mam kontynuować.",
        "raw_output": response,
        "report": response,
        "summary": direct_summary,
    }


def run_background_job(task_id: str) -> int:
    spec = load_background_job_spec(task_id)
    if not spec:
        update_task_status(task_id, "failed", "background spec missing")
        return 1
    route = spec.get("route") or {}
    chat_id = str(spec.get("chat_id") or "")
    send_progress = bool(spec.get("send_progress", True))
    send_running = bool(spec.get("send_running", False))
    started = time.time()
    pid = os.getpid()
    update_task_status(task_id, "running_background", "background worker running", worker_pid=pid)
    append_background_job_event(
        {
            "job_id": f"bg-{task_id}",
            "task_id": task_id,
            "updated_at": utc_now(),
            "status": "running",
            "pid": pid,
            "command": route.get("command", ""),
            "operators": route.get("operators", []),
        }
    )
    if send_running and chat_id:
        telegram_send_message(chat_id, f"[AI Council] {task_id}\nRUNNING: worker działa.\nstatus: /status {task_id}")
    try:
        if is_cancelled_id(task_id):
            append_background_job_event({"job_id": f"bg-{task_id}", "task_id": task_id, "updated_at": utc_now(), "status": "cancelled", "pid": pid})
            return 0
        result = execute_route_for_background(route, chat_id, task_id)
        artifact = save_task_artifacts(task_id, route, result)
        duration_ms = int((time.time() - started) * 1000)
        if is_cancelled_id(task_id):
            update_task_status(task_id, "cancelled", "background worker cancelled after artifact write", duration_ms=duration_ms, report_path=artifact.get("report_path"))
            append_background_job_event({"job_id": f"bg-{task_id}", "task_id": task_id, "updated_at": utc_now(), "status": "cancelled", "pid": pid})
            if send_progress and chat_id:
                telegram_send_message(chat_id, f"[AI Council] {task_id}\nCANCELLED.")
            return 0
        update_task_status(
            task_id,
            "completed",
            "background worker completed",
            duration_ms=duration_ms,
            report_path=artifact.get("report_path"),
            summary_path=artifact.get("summary_path"),
        )
        append_background_job_event(
            {
                "job_id": f"bg-{task_id}",
                "task_id": task_id,
                "updated_at": utc_now(),
                "status": "completed",
                "pid": pid,
                "duration_ms": duration_ms,
                "report_path": artifact.get("report_path"),
            }
        )
        if send_progress and chat_id:
            telegram_send_message(chat_id, artifact.get("summary", ""))
        return 0
    except Exception as exc:
        duration_ms = int((time.time() - started) * 1000)
        error = redact_secrets(str(exc))[:500]
        update_task_status(task_id, "failed", error, duration_ms=duration_ms)
        append_background_job_event(
            {
                "job_id": f"bg-{task_id}",
                "task_id": task_id,
                "updated_at": utc_now(),
                "status": "failed",
                "pid": pid,
                "duration_ms": duration_ms,
                "error": error,
            }
        )
        if send_progress and chat_id:
            telegram_send_message(chat_id, f"[AI Council] {task_id}\nFAILED: {compact_line(error, 260)}")
        return 1


def notify_council_job(job: dict, status: str, report_path: str, error: str = "") -> None:
    chat_id = str(job.get("chat_id") or "")
    if not chat_id:
        return
    if status == "completed":
        text = (
            "[Council] Council job completed.\n"
            f"id: {job.get('job_id')}\n"
            f"raport: {report_path}"
        )
    elif status == "cancelled":
        text = (
            "[Council] Council job cancelled.\n"
            f"id: {job.get('job_id')}"
        )
    else:
        text = (
            "[Council] Council job failed.\n"
            f"id: {job.get('job_id')}\n"
            f"error: {compact_line(error, 240)}"
        )
    telegram_send_message(chat_id, text)


def run_council_job(job: dict) -> None:
    running = {**job, "status": "running", "updated_at": utc_now()}
    append_job_event(running)
    if job.get("task_id"):
        update_task_status(job["task_id"], "running_background", f"council job {job['job_id']} running")
    report_path = REPORTS_DIR / f"{job['job_id']}.md"
    try:
        if is_cancelled_id(job["job_id"]) or (job.get("task_id") and is_cancelled_id(job["task_id"])):
            cancelled = {**job, "status": "cancelled", "updated_at": utc_now(), "report_path": str(report_path)}
            append_job_event(cancelled)
            if job.get("task_id"):
                update_task_status(job["task_id"], "cancelled", f"council job {job['job_id']} cancelled before run")
            notify_council_job(job, "cancelled", str(report_path))
            return
        report = build_council_report(job)
        if is_cancelled_id(job["job_id"]) or (job.get("task_id") and is_cancelled_id(job["task_id"])):
            cancelled = {**job, "status": "cancelled", "updated_at": utc_now(), "report_path": str(report_path)}
            append_job_event(cancelled)
            if job.get("task_id"):
                update_task_status(job["task_id"], "cancelled", f"council job {job['job_id']} cancelled after run")
            notify_council_job(job, "cancelled", str(report_path))
            return
        REPORTS_DIR.mkdir(parents=True, exist_ok=True)
        report_path.write_text(report, encoding="utf-8")
        memory_save(
            f"council-report:{job['job_id']}",
            f"{job['prompt']} -> {report_path}",
            kind="council_report",
            agent="host",
            source="council",
            task_id=job["job_id"],
        )
        completed = {
            **job,
            "status": "completed",
            "updated_at": utc_now(),
            "report_path": str(report_path),
        }
        append_job_event(completed)
        if job.get("task_id"):
            update_task_status(job["task_id"], "completed", f"council job {job['job_id']} completed", report_path=str(report_path))
        notify_council_job(job, "completed", str(report_path))
    except Exception as exc:
        failed = {
            **job,
            "status": "failed",
            "updated_at": utc_now(),
            "error": redact_secrets(str(exc))[:500],
            "report_path": str(report_path),
        }
        append_job_event(failed)
        if job.get("task_id"):
            update_task_status(job["task_id"], "failed", redact_secrets(str(exc))[:300], report_path=str(report_path))
        notify_council_job(job, "failed", str(report_path), str(exc))


def start_council_job(prompt: str, chat_id: str = "", task_id: str = "") -> dict:
    ensure_council_dirs()
    clean_prompt = prompt.strip() or "Brak opisu zadania"
    job_id = f"council-{datetime.now().strftime('%Y%m%d-%H%M%S')}-{short_hash(clean_prompt)[:6]}"
    job = {
        "job_id": job_id,
        "created_at": utc_now(),
        "updated_at": utc_now(),
        "status": "queued",
        "prompt": clean_prompt,
        "report_path": str(REPORTS_DIR / f"{job_id}.md"),
        "chat_id": chat_id,
        "task_id": task_id,
    }
    append_job_event(job)
    memory_save(
        f"council-job:{job_id}",
        clean_prompt,
        kind="task",
        agent="host",
        source="council",
        task_id=job_id,
    )
    thread = threading.Thread(target=run_council_job, args=(job,), daemon=True)
    thread.start()
    return job


def council_response(prompt: str) -> str:
    return council_response_for_chat(prompt, "")


def council_response_for_chat(prompt: str, chat_id: str = "", task_id: str = "") -> str:
    if not prompt.strip():
        return council_jobs_response()
    job = start_council_job(prompt, chat_id=chat_id, task_id=task_id)
    task_line = f"task: {task_id}\n" if task_id else ""
    return (
        "[Council] Council job uruchomiony w tle.\n"
        f"id: {job['job_id']}\n"
        f"{task_line}"
        f"raport: {job['report_path']}\n"
        "Sprawdzę w tle i odpiszę po zakończeniu."
    )


def print_env_status() -> bool:
    ensure_council_dirs()
    values = load_env()
    print(f"python={sys.version.split()[0]}")
    print(f"cwd={Path.cwd()}")
    print(f"project_dir={PROJECT_DIR}")
    print(f"workspaces_dir={WORKSPACES_DIR}")
    print(f"artifacts_dir={ARTIFACTS_DIR}")
    print(f"tasks_file={TASKS_FILE}")
    print(f"actions_file={ACTIONS_FILE}")
    print(f"costs_file={COSTS_FILE}")
    print(f"memory_db={MEMORY_DB}")
    print(f"env_path={ENV_PATH}")
    print(f"env_path_exists={ENV_PATH.exists()}")
    ok = True
    for key in REQUIRED_KEYS:
        present = bool(values.get(key))
        ok = ok and present
        print(f"{key}: {'set' if present else 'missing'}")
    return ok


def run_status_command(command: list[str], timeout: int = 20, cwd: Path = PROJECT_DIR) -> tuple[int, str]:
    try:
        proc = subprocess.run(
            command,
            text=True,
            encoding="utf-8",
            errors="replace",
            input="",
            capture_output=True,
            timeout=timeout,
            cwd=str(cwd),
            env=operator_env(),
        )
        return proc.returncode, clean_operator_output(redact_secrets((proc.stdout or "") + (proc.stderr or "")))
    except FileNotFoundError:
        return 127, "command not found"
    except subprocess.TimeoutExpired:
        return 124, "timeout"


def check_codex_status() -> bool:
    code, out = run_status_command([command_path("CODEX_BIN", "codex", DEFAULT_CODEX_BIN), "login", "status"])
    first_line = out.splitlines()[0] if out else "no output"
    print(f"codex_status_code={code}")
    print(f"codex_status={first_line}")
    return code == 0


def check_claude_status() -> bool:
    code, out = run_status_command([command_path("CLAUDE_BIN", "claude", DEFAULT_CLAUDE_BIN), "auth", "status"])
    print(f"claude_status_code={code}")
    try:
        data = json.loads(out)
        print(f"claude_logged_in={data.get('loggedIn')}")
        print(f"claude_auth_method={data.get('authMethod')}")
        print(f"claude_subscription={data.get('subscriptionType')}")
    except json.JSONDecodeError:
        print(f"claude_status={out.splitlines()[0] if out else 'unparsed'}")
    return code == 0


def request_json(
    url: str,
    *,
    headers: dict[str, str] | None = None,
    method: str = "GET",
    payload: dict | None = None,
    timeout: int = 20,
) -> dict:
    body = None
    final_headers = headers.copy() if headers else {}
    if payload is not None:
        body = json.dumps(payload).encode()
        final_headers.setdefault("Content-Type", "application/json")
    req = Request(url, data=body, headers=final_headers, method=method)
    try:
        with urlopen(req, timeout=timeout) as res:
            return json.loads(res.read().decode("utf-8", errors="replace"))
    except HTTPError as exc:
        body = redact_secrets(exc.read().decode("utf-8", errors="replace"))[:500]
        return {"ok": False, "error": f"http_{exc.code}", "body_preview": body}
    except URLError as exc:
        return {"ok": False, "error": "url_error", "reason": str(exc.reason)}
    except TimeoutError:
        return {"ok": False, "error": "timeout"}


def telegram_url(method: str, params: dict[str, str] | None = None) -> str:
    token = cfg("TELEGRAM_BOT_TOKEN")
    url = f"https://api.telegram.org/bot{token}/{method}"
    if params:
        url += "?" + urlencode(params)
    return url


def read_offset() -> int | None:
    try:
        return int(OFFSET_FILE.read_text(encoding="utf-8", errors="replace").strip())
    except (FileNotFoundError, ValueError):
        return None


def write_offset(offset: int) -> None:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    OFFSET_FILE.write_text(str(offset), encoding="utf-8")


def telegram_get_me() -> bool:
    data = request_json(telegram_url("getMe"))
    if not data.get("ok"):
        print(f"telegram_getMe=failed {data.get('error') or data.get('description')}")
        return False
    result = data.get("result", {})
    print("telegram_getMe=ok")
    print(f"telegram_bot_id={result.get('id')}")
    print(f"telegram_bot_username={result.get('username')}")
    return True


def telegram_updates(limit: int = 5) -> bool:
    params = {"limit": str(limit), "timeout": "1"}
    offset = read_offset()
    if offset is not None:
        params["offset"] = str(offset)
    data = request_json(telegram_url("getUpdates", params), timeout=5)
    if not data.get("ok"):
        print(f"telegram_getUpdates=failed {data.get('error') or data.get('description')}")
        return False
    allowed_user = cfg("TELEGRAM_ALLOWED_USER_ID")
    allowed_chat = cfg("TELEGRAM_ALLOWED_CHAT_ID")
    updates = data.get("result", [])
    print(f"telegram_getUpdates=ok count={len(updates)}")
    for update in updates[-limit:]:
        message = update.get("message") or update.get("edited_message") or {}
        sender = message.get("from", {})
        chat = message.get("chat", {})
        text = (message.get("text") or "").replace("\n", " ")[:80]
        is_allowed = str(sender.get("id")) == allowed_user and str(chat.get("id")) == allowed_chat
        print(
            "update "
            f"id={update.get('update_id')} "
            f"user={sender.get('id')} "
            f"chat={chat.get('id')} "
            f"allowed={is_allowed} "
            f"text_preview={text!r}"
        )
    return True


def split_telegram_text(text: str, limit: int = 4000) -> list[str]:
    value = str(text or "")
    if len(value) <= limit:
        return [value]
    chunks: list[str] = []
    start = 0
    while start < len(value):
        end = min(start + limit, len(value))
        if end < len(value):
            newline = value.rfind("\n", start, end)
            if newline > start:
                end = newline + 1
        chunks.append(value[start:end])
        start = end
    return chunks


def telegram_send_message(chat_id: str, text: str) -> bool:
    ok = True
    chunks = split_telegram_text(text)
    for index, chunk in enumerate(chunks, start=1):
        payload = {
            "chat_id": chat_id,
            "text": chunk,
            "disable_web_page_preview": True,
        }
        data = request_json(telegram_url("sendMessage"), method="POST", payload=payload)
        if not data.get("ok"):
            print(f"telegram_sendMessage=failed {data.get('error') or data.get('description')}")
            ok = False
            continue
        if len(chunks) > 1:
            print(f"telegram_sendMessage=ok chunk={index}/{len(chunks)}")
        else:
            print("telegram_sendMessage=ok")
    return ok


def xai_models() -> bool:
    key = cfg("XAI_API_KEY")
    if not key:
        print("xai_models=failed missing_key")
        return False
    data = request_json("https://api.x.ai/v1/models", headers={"Authorization": f"Bearer {key}"})
    if data.get("ok") is False:
        print(f"xai_models=failed {data.get('error')}")
        return False
    models = data.get("data", [])
    grok_models = [m.get("id", "") for m in models if "grok" in m.get("id", "").lower()]
    print("xai_models=ok")
    print(f"xai_grok_models_count={len(grok_models)}")
    for model_id in grok_models[:8]:
        print(f"xai_model={model_id}")
    return True


def check_scheduled_task_status() -> bool:
    if os.name != "nt":
        print("scheduled_task=skipped not_windows")
        return False
    script = f"""
$task = Get-ScheduledTask -TaskName '{TASK_NAME}' -ErrorAction SilentlyContinue
if (-not $task) {{
  Write-Output 'scheduled_task=missing'
  exit 1
}}
$info = Get-ScheduledTaskInfo -TaskName '{TASK_NAME}'
Write-Output 'scheduled_task=ok'
Write-Output ('scheduled_task_state=' + $task.State)
Write-Output ('scheduled_task_last_result=' + $info.LastTaskResult)
Write-Output ('scheduled_task_next_run=' + $info.NextRunTime)
if ($task.State -eq 'Disabled') {{
  exit 1
}}
exit 0
"""
    code, out = run_status_command(["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", script])
    print(out or f"scheduled_task_status_code={code}")
    return code == 0


def strip_intent_prefix(text: str, prefixes: list[str]) -> str:
    lower = text.lower()
    for prefix in prefixes:
        if lower.startswith(prefix):
            return text[len(prefix) :].strip(" :,-")
    return text.strip()


def natural_intent_route(stripped: str, lower: str) -> dict | None:
    if not stripped or stripped.startswith(("@", "/")):
        return None

    status_phrases = {
        "status",
        "jaki status",
        "czy działa",
        "czy dziala",
        "czy bot działa",
        "czy bot dziala",
        "bot status",
    }
    if lower in status_phrases or lower.startswith(("pokaż status", "pokaz status", "sprawdź status", "sprawdz status")):
        return {"command": "/status", "operators": ["host"], "prompt": "", "mode": "status", "intent": "natural"}

    if lower in {"health", "zdrowie", "diagnostyka", "czy system zdrowy"} or lower.startswith(
        ("pokaż health", "pokaz health", "sprawdź health", "sprawdz health")
    ):
        return {"command": "/health", "operators": ["host"], "prompt": "", "mode": "health", "intent": "natural"}

    if lower in {"co umiesz", "co potrafisz", "capabilities", "możliwości", "mozliwosci"} or lower.startswith(
        ("pokaż możliwości", "pokaz mozliwosci", "pokaż capabilities", "pokaz capabilities")
    ):
        return {"command": "/capabilities", "operators": ["host"], "prompt": "", "mode": "capabilities", "intent": "natural"}

    if lower in {"koszty", "cost", "costs", "usage", "zużycie", "zuzycie"} or lower.startswith(
        ("pokaż koszty", "pokaz koszty", "pokaż usage", "pokaz usage")
    ):
        return {"command": "/cost", "operators": ["host"], "prompt": "", "mode": "cost", "intent": "natural"}

    status_id_prefixes = ["status "]
    if any(lower.startswith(prefix) for prefix in status_id_prefixes):
        return {
            "command": "/status",
            "operators": ["host"],
            "prompt": strip_intent_prefix(stripped, status_id_prefixes),
            "mode": "status",
            "intent": "natural",
        }

    cancel_prefixes = ["cancel ", "anuluj ", "zatrzymaj ", "przerwij "]
    if any(lower.startswith(prefix) for prefix in cancel_prefixes):
        return {
            "command": "/cancel",
            "operators": ["host"],
            "prompt": strip_intent_prefix(stripped, cancel_prefixes),
            "mode": "cancel",
            "intent": "natural",
        }

    details_prefixes = ["details ", "szczegóły ", "szczegoly ", "pokaż details ", "pokaz details "]
    if any(lower.startswith(prefix) for prefix in details_prefixes):
        return {
            "command": "/details",
            "operators": ["host"],
            "prompt": strip_intent_prefix(stripped, details_prefixes),
            "mode": "details",
            "intent": "natural",
        }

    facts_prefixes = ["facts ", "fakty ", "pokaż fakty ", "pokaz fakty "]
    if any(lower.startswith(prefix) for prefix in facts_prefixes):
        return {
            "command": "/facts",
            "operators": ["host"],
            "prompt": strip_intent_prefix(stripped, facts_prefixes),
            "mode": "facts",
            "intent": "natural",
        }

    next_prefixes = ["next ", "następne ", "nastepne ", "kolejny krok ", "co dalej "]
    if any(lower.startswith(prefix) for prefix in next_prefixes):
        return {
            "command": "/next",
            "operators": ["host"],
            "prompt": strip_intent_prefix(stripped, next_prefixes),
            "mode": "next",
            "intent": "natural",
        }

    if lower in {"kolejka", "queue", "zadania", "taski"} or lower.startswith(
        ("pokaż kolejkę", "pokaz kolejke", "pokaż zadania", "pokaz zadania", "pokaż taski", "pokaz taski")
    ):
        return {"command": "/queue", "operators": ["host"], "prompt": "", "mode": "queue", "intent": "natural"}

    task_prefixes = ["dodaj task", "stwórz task", "stworz task", "utwórz task", "utworz task", "dodaj zadanie", "stwórz zadanie", "stworz zadanie", "utwórz zadanie", "utworz zadanie"]
    if any(lower.startswith(prefix) for prefix in task_prefixes):
        return {
            "command": "/task",
            "operators": ["host"],
            "prompt": strip_intent_prefix(stripped, task_prefixes),
            "mode": "task",
            "intent": "natural",
        }

    if lower in {"akcje", "actions", "pending actions", "co zatwierdzić", "co zatwierdzic"} or lower.startswith(
        ("pokaż akcje", "pokaz akcje", "pokaż actions", "pokaz actions")
    ):
        return {"command": "/actions", "operators": ["host"], "prompt": "", "mode": "actions", "intent": "natural"}

    approve_prefixes = ["approve ", "zatwierdź ", "zatwierdz ", "akceptuj "]
    if any(lower.startswith(prefix) for prefix in approve_prefixes):
        return {
            "command": "/approve",
            "operators": ["host"],
            "prompt": strip_intent_prefix(stripped, approve_prefixes),
            "mode": "approve",
            "intent": "natural",
        }

    deny_prefixes = ["deny ", "odrzuć ", "odrzuc ", "nie zatwierdzaj "]
    if any(lower.startswith(prefix) for prefix in deny_prefixes):
        return {
            "command": "/deny",
            "operators": ["host"],
            "prompt": strip_intent_prefix(stripped, deny_prefixes),
            "mode": "deny",
            "intent": "natural",
        }

    if lower in {"pamięć", "pamiec", "memory", "pokaż pamięć", "pokaz pamiec"}:
        return {"command": "/memory", "operators": ["host"], "prompt": "recent", "mode": "memory", "intent": "natural"}

    memory_search_prefixes = ["wyszukaj w pamięci", "wyszukaj w pamieci", "szukaj w pamięci", "szukaj w pamieci", "przeszukaj pamięć", "przeszukaj pamiec", "memory search"]
    if any(lower.startswith(prefix) for prefix in memory_search_prefixes):
        return {
            "command": "/memory",
            "operators": ["host"],
            "prompt": "search " + strip_intent_prefix(stripped, memory_search_prefixes),
            "mode": "memory",
            "intent": "natural",
        }

    memory_save_prefixes = ["zapamiętaj", "zapamietaj", "zapisz do pamięci", "zapisz do pamieci", "dodaj do pamięci", "dodaj do pamieci", "memory save"]
    if any(lower.startswith(prefix) for prefix in memory_save_prefixes):
        body = strip_intent_prefix(stripped, memory_save_prefixes)
        if "=" not in body:
            body = "note = " + body
        return {
            "command": "/memory",
            "operators": ["host"],
            "prompt": "save " + body,
            "mode": "memory",
            "intent": "natural",
        }

    write_prefixes = ["zapisz plik", "utwórz plik", "utworz plik", "stwórz plik", "stworz plik", "write file", "zapisz workspace"]
    if any(lower.startswith(prefix) for prefix in write_prefixes):
        return {
            "command": "/write",
            "operators": ["host"],
            "prompt": strip_intent_prefix(stripped, write_prefixes),
            "mode": "write",
            "intent": "natural",
        }

    append_prefixes = ["dopisz do pliku", "append file", "dopisz workspace"]
    if any(lower.startswith(prefix) for prefix in append_prefixes):
        return {
            "command": "/append",
            "operators": ["host"],
            "prompt": strip_intent_prefix(stripped, append_prefixes),
            "mode": "append",
            "intent": "natural",
        }

    patch_prefixes = ["zmień w pliku", "zmien w pliku", "patch file", "podmień w pliku", "podmien w pliku"]
    if any(lower.startswith(prefix) for prefix in patch_prefixes):
        return {
            "command": "/patch",
            "operators": ["host"],
            "prompt": strip_intent_prefix(stripped, patch_prefixes),
            "mode": "patch",
            "intent": "natural",
        }

    council_prefixes = ["uruchom council", "zrób council", "zrob council", "ai council", "council job"]
    if any(lower.startswith(prefix) for prefix in council_prefixes):
        return {
            "command": "/council",
            "operators": ["codex", "claude", "grok"],
            "prompt": strip_intent_prefix(stripped, council_prefixes),
            "mode": "council",
            "intent": "natural",
        }

    flow_prefixes = ["uruchom flow", "claude flow", "pełny claude", "pelny claude", "dynamic workflow", "pełny council", "pelny council"]
    if any(lower.startswith(prefix) for prefix in flow_prefixes):
        return {
            "command": "/flow",
            "operators": ["claude-flow"],
            "prompt": strip_intent_prefix(stripped, flow_prefixes),
            "mode": "flow",
            "intent": "natural",
        }

    xresearch_prefixes = ["deep research x", "głęboki research x", "gleboki research x", "research x", "x research"]
    if any(lower.startswith(prefix) for prefix in xresearch_prefixes):
        return {
            "command": "/xresearch",
            "operators": ["grok"],
            "prompt": strip_intent_prefix(stripped, xresearch_prefixes),
            "mode": "xresearch",
            "intent": "natural",
        }

    poke_prefixes = ["zbadaj poke", "research poke", "poke research", "sklonuj poke"]
    if any(lower.startswith(prefix) for prefix in poke_prefixes):
        return {
            "command": "/poke-research",
            "operators": ["grok"],
            "prompt": strip_intent_prefix(stripped, poke_prefixes),
            "mode": "poke_research",
            "intent": "natural",
        }

    return None


def multiline_command_route(text: str) -> dict | None:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if len(lines) <= 1 or len(lines) > int_cfg("AI_COUNCIL_MULTI_COMMAND_MAX_LINES", 5):
        return None
    routes = []
    for line in lines:
        line_lower = line.lower()
        looks_explicit = line_lower.startswith(("@", "/"))
        looks_natural = natural_intent_route(line, line_lower) is not None
        if not (looks_explicit or looks_natural):
            return None
        route = route_text(line)
        if route.get("command") == "codex_default":
            return None
        routes.append(route)
    operators = []
    for route in routes:
        for operator in route.get("operators", []):
            if operator not in operators:
                operators.append(operator)
    return {
        "command": "/multi",
        "operators": operators or ["host"],
        "prompt": text,
        "routes": routes,
        "mode": "multi",
    }


def route_text(text: str) -> dict:
    stripped = text.strip()
    lower = stripped.lower()
    multi_route = multiline_command_route(stripped)
    if multi_route:
        return multi_route
    if lower.startswith("@codex"):
        return {"command": "@codex", "operators": ["codex"], "prompt": stripped[6:].strip()}
    if lower.startswith("@claude-flow"):
        return {"command": "@claude-flow", "operators": ["claude-flow"], "prompt": stripped[12:].strip(), "mode": "flow"}
    if lower.startswith("@claude"):
        return {"command": "@claude", "operators": ["claude"], "prompt": stripped[7:].strip()}
    if lower.startswith("@grok"):
        return {"command": "@grok", "operators": ["grok"], "prompt": stripped[5:].strip()}
    if lower.startswith("@research"):
        return {"command": "@research", "operators": ["grok"], "prompt": stripped[9:].strip()}
    if lower.startswith("@xresearch"):
        return {"command": "@xresearch", "operators": ["grok"], "prompt": stripped[10:].strip(), "mode": "xresearch"}
    if lower.startswith("@all"):
        return {"command": "@all", "operators": ["codex", "claude", "grok"], "prompt": stripped[4:].strip()}
    if lower.startswith("/plan"):
        return {"command": "/plan", "operators": ["host"], "prompt": stripped[5:].strip(), "mode": "plan_only"}
    if lower.startswith("/dryrun"):
        return {"command": "/dryrun", "operators": ["host"], "prompt": stripped[7:].strip(), "mode": "dryrun"}
    if lower.startswith("/write"):
        return {"command": "/write", "operators": ["host"], "prompt": stripped[6:].strip(), "mode": "write"}
    if lower.startswith("/append"):
        return {"command": "/append", "operators": ["host"], "prompt": stripped[7:].strip(), "mode": "append"}
    if lower.startswith("/patch"):
        return {"command": "/patch", "operators": ["host"], "prompt": stripped[6:].strip(), "mode": "patch"}
    if lower.startswith("/task"):
        return {"command": "/task", "operators": ["host"], "prompt": stripped[5:].strip(), "mode": "task"}
    if lower.startswith("/queue"):
        return {"command": "/queue", "operators": ["host"], "prompt": "", "mode": "queue"}
    if lower.startswith("/artifacts"):
        return {"command": "/artifacts", "operators": ["host"], "prompt": "", "mode": "artifacts"}
    if lower.startswith("/capabilities"):
        return {"command": "/capabilities", "operators": ["host"], "prompt": "", "mode": "capabilities"}
    if lower.startswith("/cost"):
        return {"command": "/cost", "operators": ["host"], "prompt": "", "mode": "cost"}
    if lower.startswith("/cancel"):
        return {"command": "/cancel", "operators": ["host"], "prompt": stripped[7:].strip(), "mode": "cancel"}
    if lower.startswith("/details"):
        return {"command": "/details", "operators": ["host"], "prompt": stripped[8:].strip(), "mode": "details"}
    if lower.startswith("/facts"):
        return {"command": "/facts", "operators": ["host"], "prompt": stripped[6:].strip(), "mode": "facts"}
    if lower.startswith("/next"):
        return {"command": "/next", "operators": ["host"], "prompt": stripped[5:].strip(), "mode": "next"}
    if lower.startswith("/actions"):
        return {"command": "/actions", "operators": ["host"], "prompt": "", "mode": "actions"}
    if lower.startswith("/approve"):
        return {"command": "/approve", "operators": ["host"], "prompt": stripped[8:].strip(), "mode": "approve"}
    if lower.startswith("/deny"):
        return {"command": "/deny", "operators": ["host"], "prompt": stripped[5:].strip(), "mode": "deny"}
    if lower.startswith("/memory"):
        return {"command": "/memory", "operators": ["host"], "prompt": stripped[7:].strip(), "mode": "memory"}
    if lower.startswith("/flow"):
        return {"command": "/flow", "operators": ["claude-flow"], "prompt": stripped[5:].strip(), "mode": "flow"}
    if lower.startswith("/council"):
        return {"command": "/council", "operators": ["codex", "claude", "grok"], "prompt": stripped[8:].strip(), "mode": "council"}
    if lower.startswith("/xresearch"):
        return {"command": "/xresearch", "operators": ["grok"], "prompt": stripped[10:].strip(), "mode": "xresearch"}
    if lower.startswith("/poke-research"):
        return {"command": "/poke-research", "operators": ["grok"], "prompt": stripped[14:].strip(), "mode": "poke_research"}
    if lower.startswith("/jobs"):
        return {"command": "/jobs", "operators": ["host"], "prompt": "", "mode": "jobs"}
    if lower.startswith("/propose"):
        return {"command": "/propose", "operators": ["host"], "prompt": stripped[8:].strip(), "mode": "propose"}
    if lower.startswith("/start"):
        return {"command": "/start", "operators": ["host"], "prompt": "", "mode": "help"}
    if lower.startswith("/stop"):
        return {"command": "/stop", "operators": [], "prompt": "", "mode": "stop"}
    if lower.startswith("/status"):
        return {"command": "/status", "operators": ["host"], "prompt": stripped[7:].strip(), "mode": "status"}
    if lower.startswith("/health"):
        return {"command": "/health", "operators": ["host"], "prompt": "", "mode": "health"}
    if lower.startswith("/workspace"):
        return {"command": "/workspace", "operators": ["host"], "prompt": "", "mode": "workspace"}
    natural_route = natural_intent_route(stripped, lower)
    if natural_route:
        return natural_route
    return {"command": "codex_default", "operators": ["codex"], "prompt": stripped}


def operator_key(name: str) -> str:
    return name.strip().lower().replace(" ", "-")


def call_subprocess_operator(
    name: str,
    command: list[str],
    timeout: int,
    cwd: Path = PROJECT_DIR,
    max_chars: int | None = None,
    task_id: str = "",
) -> str:
    started = time.time()
    key = operator_key(name)
    allowed, reason = operator_call_allowed(key)
    if not allowed:
        record_operator_usage(key, task_id=task_id, status="blocked", duration_ms=0, estimated_usd=0.0, detail=reason)
        return f"[{name}] blocked: {reason}"
    try:
        proc = subprocess.run(
            command,
            text=True,
            encoding="utf-8",
            errors="replace",
            input="",
            capture_output=True,
            timeout=timeout,
            cwd=str(cwd),
            env=operator_env(),
        )
    except subprocess.TimeoutExpired:
        duration_ms = int((time.time() - started) * 1000)
        record_operator_usage(key, task_id=task_id, status="timeout", duration_ms=duration_ms)
        return f"[{name}] unavailable: timeout after {timeout}s"
    except FileNotFoundError:
        duration_ms = int((time.time() - started) * 1000)
        record_operator_usage(key, task_id=task_id, status="missing", duration_ms=duration_ms, estimated_usd=0.0)
        return f"[{name}] unavailable: command not found"

    elapsed = int((time.time() - started) * 1000)
    if proc.returncode != 0:
        raw_output = "\n".join(part for part in [proc.stdout, proc.stderr] if part)
        output = clean_operator_output(redact_secrets(raw_output))
        detail = output[:1200] or "no output"
        record_operator_usage(key, task_id=task_id, status="failed", duration_ms=elapsed, detail=detail[:240])
        return f"[{name}] unavailable: exit {proc.returncode}: {detail}"
    output = clean_operator_output(redact_secrets(proc.stdout or proc.stderr or ""))
    record_operator_usage(key, task_id=task_id, status="completed", duration_ms=elapsed)
    limit = max_chars if max_chars is not None else int_cfg("AI_COUNCIL_MAX_CHARS", 900)
    return f"[{name}] ({elapsed}ms)\n{output[:limit] or 'OK'}"


def codex_response(prompt: str, task_id: str = "") -> str:
    prompt = concise_operator_prompt(prompt, "Codex")
    return call_subprocess_operator(
        "Codex",
        [
            command_path("CODEX_BIN", "codex", DEFAULT_CODEX_BIN),
            "exec",
            "--skip-git-repo-check",
            "--sandbox",
            "read-only",
            prompt,
        ],
        timeout=120,
        max_chars=int_cfg("AI_COUNCIL_MAX_CHARS", 900),
        task_id=task_id,
    )


def claude_response(prompt: str, task_id: str = "") -> str:
    prompt = concise_operator_prompt(prompt, "Claude")
    return call_subprocess_operator(
        "Claude",
        [
            command_path("CLAUDE_BIN", "claude", DEFAULT_CLAUDE_BIN),
            "--no-session-persistence",
            "--permission-mode",
            "dontAsk",
            "--tools",
            "",
            "-p",
            prompt,
        ],
        timeout=120,
        max_chars=int_cfg("AI_COUNCIL_MAX_CHARS", 900),
        task_id=task_id,
    )


def claude_flow_prompt(prompt: str) -> str:
    text = prompt.strip()
    if not text:
        text = "Oceń AI Council i zaproponuj następny najlepszy krok rozwoju."
    memory_context = memory_context_for_prompt(text)
    memory_block = f"\n\nKontekst z pamięci AI Council:\n{memory_context}" if memory_context else ""
    return (
        "Jesteś Claude Opus 4.8 w trybie AI Council Flow dla Bartka. "
        "Używaj dostępnych Claude Code workflows/skills do planowania, review, analizy i projektowania systemu pracy. "
        "Nie wykonuj działań zewnętrznych, płatnych, publikacji, kontaktu z ludźmi, DNS/auth/billing, usuwania ani ryzykownych zmian. "
        "Jeśli potrzeba wykonania, zaproponuj bezpieczne pending actions do zatwierdzenia w AI Council. "
        "Odpowiadaj po polsku, operacyjnie i konkretnie. Dla dużych zadań zwróć: diagnoza, braki, plan iteracji, ryzyka, najbliższy krok.\n\n"
        f"Zadanie: {text}{memory_block}"
    )


def claude_flow_response(prompt: str, task_id: str = "") -> str:
    command = [
        command_path("CLAUDE_BIN", "claude", DEFAULT_CLAUDE_BIN),
        "--no-session-persistence",
        "--model",
        cfg("AI_COUNCIL_CLAUDE_FLOW_MODEL", DEFAULT_CLAUDE_FLOW_MODEL),
        "--permission-mode",
        cfg("AI_COUNCIL_CLAUDE_FLOW_PERMISSION_MODE", "plan"),
        "--add-dir",
        str(PROJECT_DIR),
    ]
    if OPENCLAW_EXPORT.exists():
        command.extend(["--add-dir", str(OPENCLAW_EXPORT)])
    if WORKSPACES_DIR.exists():
        command.extend(["--add-dir", str(WORKSPACES_DIR)])
    extra_dirs = cfg("AI_COUNCIL_CLAUDE_FLOW_EXTRA_DIRS")
    if extra_dirs:
        for raw_dir in re.split(r"[;|]", extra_dirs):
            path = Path(raw_dir.strip()).expanduser()
            if raw_dir.strip() and path.exists() and path.is_dir():
                command.extend(["--add-dir", str(path)])
    budget = cfg("AI_COUNCIL_CLAUDE_FLOW_MAX_BUDGET_USD").strip()
    if budget:
        command.extend(["--max-budget-usd", budget])
    command.extend(["-p", claude_flow_prompt(prompt)])
    return call_subprocess_operator(
        "Claude Flow",
        command,
        timeout=int_cfg("AI_COUNCIL_CLAUDE_FLOW_TIMEOUT", 600),
        max_chars=int_cfg("AI_COUNCIL_FLOW_MAX_CHARS", 2500),
        task_id=task_id,
    )


def grok_response(prompt: str, max_chars: int | None = None, task_id: str = "") -> str:
    started = time.time()
    allowed, reason = operator_call_allowed("grok")
    if not allowed:
        record_operator_usage("grok", task_id=task_id, status="blocked", duration_ms=0, estimated_usd=0.0, detail=reason)
        return f"[Grok] blocked: {reason}"
    if not prompt:
        prompt = "Odpowiedz krótko: AI Council Grok online."
    memory_context = memory_context_for_prompt(prompt)
    if memory_context:
        prompt = f"{prompt}\n\nKontekst z pamięci AI Council:\n{memory_context}"
    key = cfg("XAI_API_KEY")
    payload = {
        "model": "grok-4.3",
        "messages": [
            {
                "role": "system",
                "content": "Odpowiadasz po polsku jako operator research AI Council. Zwięźle: maks 4 zdania, chyba że prompt prosi o research brief.",
            },
            {"role": "user", "content": prompt},
        ],
        "stream": False,
    }
    data = request_json(
        "https://api.x.ai/v1/chat/completions",
        headers={"Authorization": f"Bearer {key}"},
        method="POST",
        payload=payload,
        timeout=120,
    )
    duration_ms = int((time.time() - started) * 1000)
    if data.get("ok") is False:
        detail = redact_secrets(str(data.get("body_preview", "")))[:500]
        record_operator_usage("grok", task_id=task_id, status="failed", duration_ms=duration_ms, detail=detail[:240])
        return f"[Grok] error: {data.get('error')} {detail}".strip()
    try:
        text = data["choices"][0]["message"]["content"].strip()
    except (KeyError, IndexError, TypeError):
        text = redact_secrets(json.dumps(data, ensure_ascii=False))[:1200]
    record_operator_usage("grok", task_id=task_id, status="completed", duration_ms=duration_ms)
    limit = max_chars if max_chars is not None else int_cfg("AI_COUNCIL_MAX_CHARS", 900)
    return f"[Grok]\n{text[:limit]}"


def xai_response_text(data: dict) -> str:
    chunks: list[str] = []

    def walk(node) -> None:
        if isinstance(node, dict):
            node_type = str(node.get("type") or "")
            if node_type in {"output_text", "text"} and isinstance(node.get("text"), str):
                chunks.append(node["text"])
            elif isinstance(node.get("content"), str):
                chunks.append(node["content"])
            for child in node.values():
                walk(child)
        elif isinstance(node, list):
            for child in node:
                walk(child)

    walk(data.get("output"))
    return "\n".join(chunk.strip() for chunk in chunks if chunk.strip())


def build_x_research_prompt(prompt: str) -> str:
    topic = prompt.strip() or "Poke AI agent, @interaction, Apple Messages, Recipes, Poke UX"
    return (
        "Przeprowadź deep research na X po polsku. Oddziel fakty od hipotez. "
        "Podawaj linki do postów, gdy są dostępne. Skup się na: funkcjach, sposobie działania, UX, "
        "automatyzacjach, integracjach, ograniczeniach, kosztach, Apple Messages/iMessage, "
        "lekcjach do skopiowania do prywatnego Telegram/iPhone AI Council.\n\n"
        f"Temat: {topic}"
    )


def build_poke_research_prompt(prompt: str) -> str:
    extra = prompt.strip()
    suffix = f"\nDodatkowy fokus Bartka: {extra}" if extra else ""
    return (
        "Zbadaj Poke / @interaction na X. Obowiązkowo uwzględnij post/thread/status "
        "2062575428213285352 oraz oficjalne i użytkownicze informacje od 2026-03-01 do 2026-06-06. "
        "Wyciągnij: wszystkie publicznie widoczne funkcje, kanały, Apple Messages approval, Recipes, "
        "onboarding, in-thread actions, proactive nudges, memory, developer hints typu npx poke, "
        "feedback użytkowników, skargi, koszty, opóźnienia i ograniczenia. "
        "Na końcu daj konkretne wymagania do sklonowania w Bartek Agent OS."
        f"{suffix}"
    )


def grok_x_research_response(prompt: str, max_chars: int | None = None, task_id: str = "") -> str:
    started = time.time()
    allowed, reason = operator_call_allowed("grok")
    if not allowed:
        record_operator_usage("grok", task_id=task_id, status="blocked", duration_ms=0, estimated_usd=0.0, detail=reason)
        return f"[Grok X Research] blocked: {reason}"
    key = cfg("XAI_API_KEY")
    if not key:
        record_operator_usage("grok", task_id=task_id, status="failed", duration_ms=0, detail="missing XAI_API_KEY")
        return "[Grok X Research] error: missing XAI_API_KEY"
    research_prompt = build_x_research_prompt(prompt)
    memory_context = memory_context_for_prompt(research_prompt)
    if memory_context:
        research_prompt = f"{research_prompt}\n\nKontekst z pamięci AI Council:\n{memory_context}"
    payload = {
        "model": cfg("AI_COUNCIL_GROK_X_MODEL", "grok-4.3"),
        "input": [
            {
                "role": "system",
                "content": (
                    "Jesteś Grok/X research operator dla prywatnego AI Council Bartka. "
                    "Używaj X search, oznaczaj niepewność, nie zmyślaj źródeł i pisz po polsku."
                ),
            },
            {"role": "user", "content": research_prompt},
        ],
        "tools": [
            {
                "type": "x_search",
                "from_date": cfg("AI_COUNCIL_GROK_X_FROM_DATE", "2026-03-01"),
                "to_date": cfg("AI_COUNCIL_GROK_X_TO_DATE", "2026-06-06"),
                "enable_image_understanding": True,
                "enable_video_understanding": True,
            }
        ],
        "store": False,
    }
    data = request_json(
        "https://api.x.ai/v1/responses",
        headers={"Authorization": f"Bearer {key}"},
        method="POST",
        payload=payload,
        timeout=int_cfg("AI_COUNCIL_GROK_X_TIMEOUT", 240),
    )
    duration_ms = int((time.time() - started) * 1000)
    if data.get("ok") is False:
        detail = redact_secrets(str(data.get("body_preview", "")))[:800]
        record_operator_usage("grok", task_id=task_id, status="failed", duration_ms=duration_ms, detail=detail[:240])
        return f"[Grok X Research] error: {data.get('error')} {detail}".strip()
    text = xai_response_text(data)
    if not text:
        text = redact_secrets(json.dumps(data, ensure_ascii=False))[:1600]
    record_operator_usage("grok", task_id=task_id, status="completed", duration_ms=duration_ms)
    limit = max_chars if max_chars is not None else int_cfg("AI_COUNCIL_X_RESEARCH_MAX_CHARS", 5000)
    return f"[Grok X Research] ({duration_ms}ms)\n{text[:limit]}"


def grok_route_response(prompt: str, *, max_chars: int | None = None, task_id: str = "") -> str:
    if task_id:
        return grok_response(prompt, max_chars=max_chars, task_id=task_id)
    return grok_response(prompt, max_chars=max_chars)


def build_research_prompt(prompt: str) -> str:
    topic = prompt.strip() or "temat nie został podany"
    return (
        "Przygotuj brief research po polsku.\n"
        "Format: TL;DR, najważniejsze fakty, ryzyka/niepewności, rekomendowane następne kroki.\n"
        "Bądź konkretny i oznacz, gdy czegoś nie da się potwierdzić bez źródeł live.\n\n"
        f"Temat: {topic}"
    )


def host_response(prompt: str) -> str:
    if not prompt:
        return "[Council] AI Council online. Rozumiem też naturalne intencje: status, health, status <id>, details/fakty/next <id>, koszty, cancel/anuluj <id>, kolejka, pamięć, actions, council, flow, zapisz/dopisz/zmień plik. Komendy: @codex, @claude, @claude-flow, @grok, @research, @xresearch, /poke-research, @all."
    return (
        "[Council]\n"
        "Odebrałem. Routing działa.\n"
        "Komendy: @codex, @claude, @claude-flow, @grok, @research, @xresearch, /poke-research, @all, /task, /queue, /artifacts, /actions, /approve, /deny, /memory, /write, /append, /patch, /flow, /council, /details <id>, /facts <id>, /next <id>, /capabilities, /health, /status <id>, /cancel <id>, /cost."
    )


def build_response(route: dict, chat_id: str = "") -> str:
    command = route.get("command")
    prompt = route.get("prompt", "")
    task_id = route.get("task_id", "")
    if command == "/multi":
        responses = []
        for index, child_route in enumerate(route.get("routes", []), start=1):
            child_route = {**child_route, "task_id": task_id}
            child_command = child_route.get("command", "unknown")
            child_response = build_response(child_route, chat_id=chat_id)
            responses.append(f"[Council] {index}/{len(route.get('routes', []))}: {child_command}\n{child_response}")
        return "\n\n".join(responses) if responses else host_response(prompt)
    if command == "/stop":
        return "[Council] Stop przyjęty. Bounded listener zakończy ten przebieg po obsłudze aktualnej wiadomości."
    if command == "/status":
        return task_status_response(prompt)
    if command == "/health":
        return health_response()
    if command == "/workspace":
        ensure_council_dirs()
        return "[Council] Workspace: D:\\ai-council. L2.5: workspaces, artifacts, reports, state\\tasks.jsonl, state\\actions.jsonl, state\\background_jobs.jsonl, state\\artifact_index.jsonl, state\\costs.jsonl, state\\memory.sqlite. Codex: read-only. Claude quick: bez tools. Claude Flow: Opus 4.8 plan workflow. Grok: API research."
    if command == "/capabilities":
        return capabilities_response()
    if command == "/cost":
        return cost_response()
    if command == "/cancel":
        return cancel_response(prompt)
    if command == "/details":
        return details_response(prompt)
    if command == "/facts":
        return facts_response(prompt)
    if command == "/next":
        return next_response(prompt)
    if command == "/task":
        task = create_task(prompt)
        return (
            "[Council] Task zapisany.\n"
            f"id: {task['task_id']}\n"
            f"status: {task['status']}\n"
            "Następnie: @research dla briefu, @claude dla szybkiego planu, @claude-flow dla pełnego workflow 4.8 albo @codex dla wykonania read-only. Wykonanie write/execute będzie przez /approve w L2/L3."
        )
    if command == "/queue":
        return queue_response()
    if command == "/artifacts":
        return artifacts_response()
    if command == "/actions":
        return actions_response()
    if command == "/approve":
        return approve_response(prompt)
    if command == "/deny":
        return deny_response(prompt)
    if command == "/memory":
        return memory_response(prompt)
    if command == "/flow":
        return claude_flow_response(prompt, task_id=task_id)
    if command == "/council":
        return council_response_for_chat(prompt, chat_id=chat_id, task_id=task_id)
    if command == "/jobs":
        return council_jobs_response()
    if command == "/propose":
        action = create_action(prompt, action_type="manual_proposal", risk="medium")
        return (
            "[Council] Pending action utworzona.\n"
            f"id: {action['action_id']}\n"
            "Zatwierdź: /approve <id> albo odrzuć: /deny <id>."
        )
    if command == "/write":
        return write_response(prompt)
    if command == "/append":
        return append_response(prompt)
    if command == "/patch":
        return patch_response(prompt)
    if command == "@codex":
        return codex_response(prompt, task_id=task_id)
    if command == "codex_default":
        return codex_response(prompt, task_id=task_id)
    if command == "@claude":
        return claude_response(prompt, task_id=task_id)
    if command == "@claude-flow":
        return claude_flow_response(prompt, task_id=task_id)
    if command == "@grok":
        return grok_route_response(prompt, max_chars=int_cfg("AI_COUNCIL_MAX_CHARS", 900), task_id=task_id)
    if command == "@research":
        return grok_route_response(build_research_prompt(prompt), max_chars=int_cfg("AI_COUNCIL_RESEARCH_MAX_CHARS", 1800), task_id=task_id)
    if command == "@xresearch":
        return grok_x_research_response(prompt, max_chars=int_cfg("AI_COUNCIL_X_RESEARCH_MAX_CHARS", 5000), task_id=task_id)
    if command == "/xresearch":
        return grok_x_research_response(prompt, max_chars=int_cfg("AI_COUNCIL_X_RESEARCH_MAX_CHARS", 5000), task_id=task_id)
    if command == "/poke-research":
        return grok_x_research_response(build_poke_research_prompt(prompt), max_chars=int_cfg("AI_COUNCIL_X_RESEARCH_MAX_CHARS", 7000), task_id=task_id)
    if command == "@all":
        parts = [
            codex_response(prompt, task_id=task_id),
            claude_response(prompt, task_id=task_id),
            grok_route_response(prompt, max_chars=700, task_id=task_id),
        ]
        parts.append("[Council]\nKrótko: odpytano Codex, Claude i Grok. Jeśli chcesz decyzję/syntezę zamiast trzech głosów, napisz @research albo poproś o 'syntezę'.")
        return "\n\n".join(parts)
    return host_response(prompt)


def sanitize_for_audit(value):
    if isinstance(value, str):
        return redact_secrets(value)
    if isinstance(value, list):
        return [sanitize_for_audit(item) for item in value]
    if isinstance(value, dict):
        return {key: sanitize_for_audit(item) for key, item in value.items()}
    return value


def audit(event: dict) -> None:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    base = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "update_id": event.get("update_id"),
        "command": event.get("command", ""),
        "operators": event.get("operators", []),
        "status": event.get("status", ""),
        "duration_ms": event.get("duration_ms", 0),
        "output_preview": event.get("output_preview", ""),
    }
    payload = sanitize_for_audit({**base, **event})
    with AUDIT_LOG.open("a", encoding="utf-8") as f:
        f.write(json.dumps(payload, ensure_ascii=False) + "\n")


def command_resolves(path_or_command: str) -> bool:
    path = Path(path_or_command)
    if path.exists():
        return True
    return shutil.which(path_or_command) is not None


def operator_binary_status() -> dict:
    codex_bin = command_path("CODEX_BIN", "codex", DEFAULT_CODEX_BIN)
    claude_bin = command_path("CLAUDE_BIN", "claude", DEFAULT_CLAUDE_BIN)
    return {
        "codex": {"configured": command_resolves(codex_bin), "command": codex_bin},
        "claude": {"configured": command_resolves(claude_bin), "command": claude_bin},
        "claude_flow": {
            "configured": command_resolves(claude_bin),
            "command": claude_bin,
            "model": cfg("AI_COUNCIL_CLAUDE_FLOW_MODEL", DEFAULT_CLAUDE_FLOW_MODEL),
            "permission_mode": cfg("AI_COUNCIL_CLAUDE_FLOW_PERMISSION_MODE", "plan"),
            "budget_cap": cfg("AI_COUNCIL_CLAUDE_FLOW_MAX_BUDGET_USD", ""),
        },
        "grok": {"configured": bool(cfg("XAI_API_KEY"))},
    }


def log_startup() -> None:
    ensure_council_dirs()
    status = operator_binary_status()
    preview = (
        f"python={sys.version.split()[0]} cwd={Path.cwd()} project_dir={PROJECT_DIR} "
        f"env_path={ENV_PATH} env_exists={ENV_PATH.exists()} operators={status}"
    )
    print(f"startup {preview}")
    audit(
        {
            "command": "startup",
            "operators": list(status.keys()),
            "status": "started",
            "duration_ms": 0,
            "output_preview": preview[:500],
            "python": sys.version.split()[0],
            "cwd": str(Path.cwd()),
            "project_dir": str(PROJECT_DIR),
            "env_path": str(ENV_PATH),
            "env_exists": ENV_PATH.exists(),
            "operator_status": status,
        }
    )


def dry_route(text: str) -> None:
    started = time.time()
    route = route_text(text)
    event = {
        "request_id": short_hash(f"{time.time()}:{text}"),
        "command": route.get("command"),
        "operators": route.get("operators", []),
        "status": "dry_route",
        "duration_ms": int((time.time() - started) * 1000),
        "dry_send": bool_cfg("AI_COUNCIL_DRY_SEND", True),
        "action_required": False,
        "task_required": route_needs_task(route),
        "background": route_should_background(route),
        "prompt_preview": route.get("prompt", "")[:160],
    }
    audit(event)
    print(json.dumps(event, indent=2, ensure_ascii=False))
    print(f"audit_log={AUDIT_LOG}")


def is_allowed_message(message: dict) -> bool:
    sender = message.get("from", {})
    chat = message.get("chat", {})
    return (
        str(sender.get("id")) == cfg("TELEGRAM_ALLOWED_USER_ID")
        and str(chat.get("id")) == cfg("TELEGRAM_ALLOWED_CHAT_ID")
    )


def listen_once(send: bool = False, limit: int = 10, verbose: bool = True) -> int:
    params = {"limit": str(limit), "timeout": "1"}
    offset = read_offset()
    if offset is not None:
        params["offset"] = str(offset)
    data = request_json(telegram_url("getUpdates", params), timeout=5)
    if not data.get("ok"):
        print(f"telegram_getUpdates=failed {data.get('error') or data.get('description')}")
        return 1

    updates = data.get("result", [])
    if verbose or updates:
        print(f"listen_updates_count={len(updates)}")
    processed = 0
    max_update_id = None
    for update in updates:
        max_update_id = max(max_update_id or update["update_id"], update["update_id"])
        message = update.get("message") or update.get("edited_message") or {}
        text = message.get("text") or ""
        chat_id = str((message.get("chat") or {}).get("id", ""))
        allowed = is_allowed_message(message)
        route = route_text(text)
        event = {
            "request_id": short_hash(f"{update.get('update_id')}:{text}"),
            "update_id": update.get("update_id"),
            "chat_id_hash": short_hash(chat_id),
            "user_id_hash": short_hash(str((message.get("from") or {}).get("id", ""))),
            "command": route.get("command"),
            "operators": route.get("operators", []),
            "allowed": allowed,
            "send_requested": send,
            "dry_send_env": bool_cfg("AI_COUNCIL_DRY_SEND", True),
            "prompt_preview": route.get("prompt", "")[:160],
        }
        if not allowed:
            event["status"] = "ignored_not_allowed"
            audit(event)
            continue
        if not text:
            event["status"] = "ignored_no_text"
            audit(event)
            continue

        print(f"processing update={update.get('update_id')} command={route.get('command')} send={send}")
        started = time.time()
        task = None
        duplicate = None
        background_started = False
        if route_needs_task(route):
            idem_key = idempotency_key_for(chat_id, text)
            duplicate = find_recent_duplicate(idem_key)
            if duplicate:
                event["task_id"] = duplicate.get("task_id")
                event["idempotency_key"] = idem_key
                response = duplicate_response(duplicate)
            else:
                task = create_task(
                    text,
                    source="telegram_request",
                    status="running",
                    command=route.get("command", ""),
                    operators=route.get("operators", []),
                    request_id=event["request_id"],
                    idempotency_key=idem_key,
                    chat_id_hash=event["chat_id_hash"],
                    update_id=update.get("update_id"),
                )
                event["task_id"] = task.get("task_id")
                event["idempotency_key"] = idem_key
                route = {**route, "task_id": task.get("task_id")}
        try:
            if duplicate:
                response = response
            elif task and route_should_background(route):
                background_started = True
                response = start_background_job(route, chat_id=chat_id, task_id=task["task_id"], send_progress=send)
            else:
                response = build_response(route, chat_id=chat_id)
            response_failed = False
        except Exception as exc:
            response = f"[Council] Error: {compact_line(redact_secrets(str(exc)), 500)}"
            response_failed = True
            if task:
                update_task_status(task["task_id"], "failed", redact_secrets(str(exc))[:300])
        event["duration_ms"] = int((time.time() - started) * 1000)
        event["output_preview"] = response[:300]
        if task and not response_failed:
            if background_started:
                update_task_status(task["task_id"], "running_background", "background response sent", duration_ms=event["duration_ms"])
            elif route.get("command") in SIDE_EFFECT_COMMANDS:
                update_task_status(task["task_id"], "waiting_approval", "pending action created or rejected", duration_ms=event["duration_ms"])
            else:
                update_task_status(task["task_id"], "completed", "response sent", duration_ms=event["duration_ms"])
        if send:
            sent = telegram_send_message(chat_id, response)
            event["status"] = "duplicate" if duplicate else ("responded" if sent else "send_failed")
        else:
            event["status"] = "duplicate" if duplicate else "dry_responded"
            print(response)
        audit(event)
        processed += 1

    if max_update_id is not None:
        write_offset(max_update_id + 1)
        if verbose or processed:
            print(f"offset_saved={max_update_id + 1}")
    if verbose or processed:
        print(f"processed={processed}")
    return 0


def listen_loop(send: bool = False, seconds: int = 120, limit: int = 10, sleep_seconds: float = 1.5) -> int:
    deadline = time.time() + seconds
    total = 0
    print(f"listen_loop_started seconds={seconds} send={send}")
    log_startup()
    reconciled = reconcile_background_jobs()
    if reconciled:
        print(f"reconciled_background_jobs={len(reconciled)}")
    while time.time() < deadline:
        before = AUDIT_LOG.stat().st_size if AUDIT_LOG.exists() else 0
        code = listen_once(send=send, limit=limit, verbose=False)
        after = AUDIT_LOG.stat().st_size if AUDIT_LOG.exists() else before
        if code != 0:
            return code
        if after > before:
            total += 1
        time.sleep(sleep_seconds)
    print(f"listen_loop_done iterations_with_activity={total}")
    return 0


def serve(send: bool = True, limit: int = 10, sleep_seconds: float = 1.5) -> int:
    print(f"serve_started send={send}")
    log_startup()
    reconciled = reconcile_background_jobs()
    if reconciled:
        print(f"reconciled_background_jobs={len(reconciled)}")
    try:
        while True:
            code = listen_once(send=send, limit=limit, verbose=False)
            if code != 0:
                print(f"serve_poll_error code={code}")
                time.sleep(max(5.0, sleep_seconds))
            else:
                time.sleep(sleep_seconds)
    except KeyboardInterrupt:
        print("serve_stopped")
        return 0


def doctor() -> int:
    log_startup()
    ok = print_env_status()
    print("--- auth ---")
    ok = check_codex_status() and ok
    ok = check_claude_status() and ok
    print("--- telegram ---")
    ok = telegram_get_me() and ok
    print("--- xai ---")
    ok = xai_models() and ok
    print("--- scheduled-task ---")
    ok = check_scheduled_task_status() and ok
    return 0 if ok else 1


def main() -> int:
    parser = argparse.ArgumentParser(description="AI Council local dry-run tester")
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("doctor")
    sub.add_parser("env")
    sub.add_parser("telegram-me")
    updates = sub.add_parser("telegram-updates")
    updates.add_argument("--limit", type=int, default=5)
    sub.add_parser("xai-models")
    listen = sub.add_parser("listen-once")
    listen.add_argument("--send", action="store_true", help="Actually send Telegram replies for this bounded run")
    listen.add_argument("--limit", type=int, default=10)
    loop = sub.add_parser("listen")
    loop.add_argument("--send", action="store_true", help="Actually send Telegram replies for this bounded run")
    loop.add_argument("--seconds", type=int, default=120)
    loop.add_argument("--limit", type=int, default=10)
    serve_parser = sub.add_parser("serve")
    serve_parser.add_argument("--send", action="store_true", default=True, help="Actually send Telegram replies")
    serve_parser.add_argument("--limit", type=int, default=10)
    worker = sub.add_parser("run-background-job")
    worker.add_argument("--task-id", required=True)
    route = sub.add_parser("dry-route")
    route.add_argument("text", nargs="+")
    args = parser.parse_args()

    if args.cmd == "doctor":
        return doctor()
    if args.cmd == "env":
        return 0 if print_env_status() else 1
    if args.cmd == "telegram-me":
        return 0 if telegram_get_me() else 1
    if args.cmd == "telegram-updates":
        return 0 if telegram_updates(args.limit) else 1
    if args.cmd == "xai-models":
        return 0 if xai_models() else 1
    if args.cmd == "listen-once":
        return listen_once(send=args.send, limit=args.limit)
    if args.cmd == "listen":
        return listen_loop(send=args.send, seconds=args.seconds, limit=args.limit)
    if args.cmd == "serve":
        return serve(send=args.send, limit=args.limit)
    if args.cmd == "run-background-job":
        return run_background_job(args.task_id)
    if args.cmd == "dry-route":
        dry_route(" ".join(args.text))
        return 0
    return 2


if __name__ == "__main__":
    sys.exit(main())
