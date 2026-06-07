#!/usr/bin/env python3
from __future__ import annotations

import argparse
import base64
import csv
from datetime import datetime, timezone
import difflib
import hmac
import hashlib
import json
import mimetypes
import os
import re
import signal
import shutil
import sqlite3
import subprocess
import sys
import threading
import time
import traceback
from pathlib import Path
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlencode, urlparse
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
ERRORS_DIR = Path(os.environ.get("AI_COUNCIL_ERRORS_DIR", PROJECT_DIR / "errors")).expanduser()
TASKS_FILE = STATE_DIR / "tasks.jsonl"
ACTIONS_FILE = STATE_DIR / "actions.jsonl"
COUNCIL_JOBS_FILE = STATE_DIR / "council_jobs.jsonl"
BACKGROUND_JOBS_FILE = STATE_DIR / "background_jobs.jsonl"
ARTIFACT_INDEX_FILE = STATE_DIR / "artifact_index.jsonl"
BACKGROUND_JOB_SPECS_DIR = STATE_DIR / "background_job_specs"
COSTS_FILE = STATE_DIR / "costs.jsonl"
COST_LOCK_FILE = STATE_DIR / "costs.lock"
CONTROL_FILE = STATE_DIR / "control.json"
ERRORS_FILE = STATE_DIR / "errors.jsonl"
IMPROVEMENTS_FILE = STATE_DIR / "improvements.jsonl"
CONVERSATIONS_FILE = STATE_DIR / "conversations.jsonl"
TELEGRAM_LISTENER_LOCK = STATE_DIR / "telegram_listener.lock"
MEMORY_DB = STATE_DIR / "memory.sqlite"
CONNECTOR_INDEX_DB = STATE_DIR / "connector_index.sqlite"
RECIPES_DIR = PROJECT_DIR / "recipes"
NUDGES_FILE = STATE_DIR / "nudges.jsonl"
RECIPE_RUNS_FILE = STATE_DIR / "recipe_runs.jsonl"
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
RISK_LEVELS = ("R0", "R1", "R2", "R3", "R4")
AUTO_EXECUTABLE_WORKSPACE_RISKS = {"R1", "low"}
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
    "/recipe",
    "@all",
    "/council",
}
FRONT_OPERATOR_COMMANDS = {
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
    "/recipe",
    "@all",
    "/council",
}
PROGRESS_STAGE_PERCENT = {
    "START": 5,
    "PREPARING": 15,
    "RUNNING": 35,
    "COLLECTING": 70,
    "DELIVERING": 90,
    "COMPLETED": 100,
    "FAILED": 100,
    "CANCELLED": 100,
}
READONLY_RECIPE_COMMANDS = {
    "/health",
    "/selftest",
    "/front",
    "/status",
    "/progress",
    "/agent",
    "/shortcuts",
    "/drafts",
    "/cost",
    "/control",
    "/queue",
    "/artifacts",
    "/errors",
    "/improvements",
    "/followups",
    "/loops",
    "/nudges",
    "/sources",
    "/source",
    "/connectors",
    "/connector",
    "/memory",
    "/project-memory",
    "/chat",
    "@research",
    "@grok",
    "@xresearch",
    "/xresearch",
    "/poke-research",
    "@claude",
    "@claude-flow",
    "/flow",
    "/council",
}
RECIPE_CONNECTOR_READ_ACTIONS = {"check", "status", "auth", "setup", "connect", "search", "find", "brief", "report", "summary", "ingest", "index", "cache", "sync", "oauth-sync"}
INTEGRATION_DRAFT_CONNECTORS = {"gmail", "calendar", "drive", "github"}
RECIPE_SOURCE_READ_ACTIONS = {"search"}
RECIPE_MEMORY_READ_ACTIONS = {"recent", "search"}
RECIPE_PROJECT_MEMORY_READ_ACTIONS = {"", "recent", "show", "search", "context"}
RECIPE_CONTROL_READ_ACTIONS = {"", "status"}
FOLLOWUP_EXECUTABLE_COMMANDS = {
    "/plan-action",
    "/improve",
    "/flow",
    "/council",
    "@research",
    "@xresearch",
    "/xresearch",
    "/poke-research",
    "/recipe",
    "/connector",
    "/source",
    "/chat",
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
        if key.startswith(("TELEGRAM_", "XAI_", "AI_COUNCIL_", "GROK_", "GITHUB_", "GH_", "GOOGLE_")):
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


def utc_now_rfc3339_z() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


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
        ERRORS_DIR,
        RECIPES_DIR,
        BACKGROUND_JOB_SPECS_DIR,
        PROJECT_DIR / "sources",
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


class SingleInstanceLock:
    def __init__(self, path: Path):
        self.path = path
        self.handle = None

    def acquire(self) -> bool:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.handle = self.path.open("a+", encoding="utf-8")
        self.handle.seek(0)
        try:
            if os.name == "nt":
                import msvcrt

                msvcrt.locking(self.handle.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl

                fcntl.flock(self.handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            self.close()
            return False
        self.handle.seek(0)
        self.handle.truncate()
        self.handle.write(str(os.getpid()))
        self.handle.flush()
        return True

    def release(self) -> None:
        if not self.handle:
            return
        try:
            self.handle.seek(0)
            if os.name == "nt":
                import msvcrt

                msvcrt.locking(self.handle.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                import fcntl

                fcntl.flock(self.handle.fileno(), fcntl.LOCK_UN)
        except OSError:
            pass
        self.close()

    def close(self) -> None:
        if self.handle:
            try:
                self.handle.close()
            finally:
                self.handle = None


class BlockingFileLock:
    def __init__(self, path: Path, timeout: float = 5.0, sleep_seconds: float = 0.05):
        self.path = path
        self.timeout = timeout
        self.sleep_seconds = sleep_seconds
        self.lock = SingleInstanceLock(path)

    def __enter__(self):
        deadline = time.time() + self.timeout
        while True:
            if self.lock.acquire():
                return self
            if time.time() >= deadline:
                raise TimeoutError(f"lock timeout: {self.path}")
            time.sleep(self.sleep_seconds)

    def __exit__(self, exc_type, exc, tb):
        self.lock.release()
        return False


def record_error(
    context: str,
    *,
    exc: BaseException | None = None,
    message: str = "",
    event: dict | None = None,
    severity: str = "error",
) -> dict:
    ensure_council_dirs()
    payload = {
        "error_id": f"err-{datetime.now().strftime('%Y%m%d-%H%M%S')}-{short_hash(f'{context}:{message}:{time.time()}')[:6]}",
        "created_at": utc_now(),
        "day": today_utc(),
        "context": compact_line(context, 160),
        "severity": severity,
        "message": compact_line(redact_secrets(message or (str(exc) if exc else "")), 1000),
        "exception_type": type(exc).__name__ if exc else "",
        "traceback": redact_secrets("".join(traceback.format_exception(type(exc), exc, exc.__traceback__)))[:5000] if exc else "",
        "event": sanitize_for_audit(event or {}),
    }
    append_jsonl(ERRORS_FILE, payload)
    append_jsonl(ERRORS_DIR / f"{payload['day']}.jsonl", payload)
    return payload


def error_rows(days: int = 7) -> list[dict]:
    rows = read_jsonl(ERRORS_FILE)
    if days <= 0:
        return rows
    cutoff = datetime.now(timezone.utc).timestamp() - days * 86400
    filtered = []
    for row in rows:
        parsed = parse_utc(str(row.get("created_at") or ""))
        if parsed and parsed.timestamp() >= cutoff:
            filtered.append(row)
    return filtered


def errors_response(prompt: str = "") -> str:
    parts = prompt.strip().split()
    limit = 8
    if parts:
        for token in parts:
            if token.isdigit():
                limit = max(1, min(int(token), 25))
    rows = error_rows(days=7)
    if not rows:
        return f"[Council] Errors: brak zapisanych błędów z ostatnich 7 dni.\nFolder: {ERRORS_DIR}"
    latest = rows[-limit:]
    counts: dict[str, int] = {}
    for row in rows:
        context = str(row.get("context") or "unknown")
        counts[context] = counts.get(context, 0) + 1
    lines = [
        "[Council] Errors",
        f"last_7d: {len(rows)} | showing: {len(latest)}",
        "top_contexts: "
        + ", ".join(f"{name}:{count}" for name, count in sorted(counts.items(), key=lambda item: item[1], reverse=True)[:5]),
        f"folder: {ERRORS_DIR}",
    ]
    for row in latest:
        lines.append(
            f"- {row.get('error_id')} {row.get('created_at')} {row.get('context')} "
            f"{compact_line(str(row.get('message') or row.get('exception_type') or ''), 180)}"
        )
    lines.append("Audit: /recipe run error_audit_twice_daily albo poczekaj na cykl 09:00/21:00.")
    return "\n".join(lines)


def append_conversation_turn(chat_id: str, role: str, text: str, route: dict | None = None) -> dict:
    ensure_council_dirs()
    clean_role = role if role in {"user", "assistant", "system"} else "user"
    turn = {
        "turn_id": f"turn-{datetime.now().strftime('%Y%m%d-%H%M%S')}-{short_hash(f'{chat_id}:{role}:{text}:{time.time()}')[:6]}",
        "created_at": utc_now(),
        "chat_id_hash": short_hash(str(chat_id)),
        "role": clean_role,
        "text": compact_line(redact_secrets(text or ""), int_cfg("AI_COUNCIL_CONVERSATION_TURN_MAX_CHARS", 1200)),
        "command": (route or {}).get("command", ""),
        "route_source": (route or {}).get("route_source", ""),
        "confidence": (route or {}).get("confidence", ""),
    }
    append_jsonl(CONVERSATIONS_FILE, turn)
    return turn


def recent_conversation(chat_id: str, limit: int = 6) -> list[dict]:
    chat_hash = short_hash(str(chat_id))
    rows = [row for row in read_jsonl(CONVERSATIONS_FILE) if row.get("chat_id_hash") == chat_hash]
    return rows[-max(0, limit) :]


def improvement_title_from_text(text: str, fallback: str = "AI Council improvement") -> str:
    for line in extract_fact_lines(text, limit=12):
        clean = re.sub(r"^(decyzja|next|rekomendacja|sprint|wdrożyć|wdrozyc)\s*[:：-]\s*", "", line, flags=re.IGNORECASE)
        clean = compact_line(clean.strip("`*_ "), 120)
        if clean and not clean.lower().startswith(("step ", "using tool", "details:")):
            return clean
    return compact_line(fallback, 120)


def latest_improvements(limit: int = 20) -> list[dict]:
    return latest_by_id(IMPROVEMENTS_FILE, "improvement_id", limit=limit)


def open_improvements(limit: int = 20) -> list[dict]:
    return [row for row in latest_improvements(limit=limit * 3) if row.get("status", "open") == "open"][:limit]


def get_latest_improvement(improvement_id: str) -> dict | None:
    improvement_id = improvement_id.strip()
    latest = {
        row.get("improvement_id"): row
        for row in read_jsonl(IMPROVEMENTS_FILE)
        if row.get("improvement_id")
    }
    return latest.get(improvement_id)


def create_improvement(
    *,
    source: str,
    title: str,
    summary: str,
    task_id: str = "",
    recipe: str = "",
    priority: str = "P2",
    status: str = "open",
) -> dict:
    ensure_council_dirs()
    if task_id:
        existing = [
            row
            for row in read_jsonl(IMPROVEMENTS_FILE)
            if row.get("source_task_id") == task_id and row.get("status", "open") != "superseded"
        ]
        if existing:
            return existing[-1]
    clean_title = compact_line(title or improvement_title_from_text(summary), 140)
    improvement = {
        "improvement_id": f"imp-{datetime.now().strftime('%Y%m%d-%H%M%S')}-{short_hash(f'{source}:{task_id}:{title}:{time.time()}')[:6]}",
        "created_at": utc_now(),
        "updated_at": utc_now(),
        "status": status,
        "priority": priority,
        "source": source,
        "source_task_id": task_id,
        "recipe": recipe,
        "title": clean_title,
        "summary": compact_line(summary, 2000),
        "next_action": f"Codex audit: /improve show <id> -> implementacja z testami. Details: /details {task_id}" if task_id else "Codex audit i implementacja z testami.",
    }
    append_jsonl(IMPROVEMENTS_FILE, improvement)
    return improvement


def create_improvement_from_recipe(recipe: dict, recipe_name: str, task_id: str, raw: str) -> dict | None:
    policy = recipe.get("improvement_policy") or {}
    if not (recipe.get("capture_improvement") or policy.get("enabled")):
        return None
    if recipe_name == "error_audit_twice_daily" and "brak zapisanych błędów" in raw.lower() and "err-" not in raw:
        return None
    title = improvement_title_from_text(raw, fallback=f"Recipe {recipe_name} recommendation")
    return create_improvement(
        source=str(policy.get("source") or f"recipe:{recipe_name}"),
        title=title,
        summary=raw,
        task_id=task_id,
        recipe=recipe_name,
        priority=str(policy.get("priority") or "P2"),
    )


def update_improvement_status(improvement_id: str, status: str) -> dict | None:
    current = get_latest_improvement(improvement_id)
    if not current:
        return None
    updated = {**current, "status": status, "updated_at": utc_now()}
    append_jsonl(IMPROVEMENTS_FILE, updated)
    return updated


def update_improvement_fields(improvement_id: str, **fields) -> dict | None:
    current = get_latest_improvement(improvement_id)
    if not current:
        return None
    updated = {**current, **fields, "updated_at": utc_now()}
    append_jsonl(IMPROVEMENTS_FILE, updated)
    return updated


def build_improvement_apply_prompt(item: dict) -> str:
    return (
        "AI Council improvement apply flow.\n"
        "Cel: zamienić backlog item na konkretny, bezpieczny sprint implementacyjny dla Codex.\n"
        "Nie wykonuj jeszcze zmian plików. Nie rób external write, publikacji, kontaktu, auth/billing/DNS ani kasowania.\n"
        "Wynik ma wskazać: decyzję, scope, dokładne pliki/funkcje, minimalny patch, testy, acceptance criteria, ryzyka i rollback.\n\n"
        f"Improvement ID: {item.get('improvement_id')}\n"
        f"Priority: {item.get('priority')}\n"
        f"Source: {item.get('source')}\n"
        f"Recipe: {item.get('recipe')}\n"
        f"Source task: {item.get('source_task_id')}\n"
        f"Title: {item.get('title')}\n\n"
        f"Summary:\n{item.get('summary')}\n"
    )


def run_improve_background(prompt: str, task_id: str = "") -> dict:
    parts = prompt.strip().split(maxsplit=1)
    if len(parts) < 2 or parts[0].lower() not in {"apply", "plan"}:
        response = improvements_response(prompt)
        return {
            "decision": "Improvement nie został zaplanowany.",
            "facts": [response],
            "dispute": "",
            "next_actions": ["/improve next", "/improvements"],
            "ask_user": "Użyj /improve apply <id> albo /improve plan <id>.",
            "raw_output": response,
            "report": response,
        }
    action = parts[0].lower()
    improvement_id = parts[1].strip()
    item = get_latest_improvement(improvement_id)
    if not item:
        response = f"[Council] Nie znalazłem improvement `{improvement_id}`."
        return {
            "decision": response,
            "facts": [response],
            "dispute": "",
            "next_actions": ["/improvements"],
            "ask_user": "Wybierz istniejący improvement.",
            "raw_output": response,
            "report": response,
        }
    apply_prompt = build_improvement_apply_prompt(item)
    result = build_structured_council_result(apply_prompt, task_id=task_id)
    update_improvement_fields(
        improvement_id,
        status="planned",
        plan_task_id=task_id,
        plan_created_at=utc_now(),
        next_action=f"Przejrzyj plan: /details {task_id}. Po wdrożeniu: /improve done {improvement_id}",
    )
    result["decision"] = f"Improvement `{improvement_id}` zaplanowany przez AI Council."
    result["next_actions"] = [
        f"Przejrzyj plan: /details {task_id}",
        f"Wdrożenie kodu po audycie Codex; po zakończeniu: /improve done {improvement_id}",
        f"Jeśli odrzucasz: /improve dismiss {improvement_id}",
    ]
    result["ask_user"] = "Potwierdź, czy mam wdrożyć plan jako następny patch."
    result["report"] = (
        f"# Improvement apply: {improvement_id}\n\n"
        f"Action: {action}\n\n"
        f"## Backlog item\n\n{format_improvement(item, detailed=True)}\n\n"
        f"## Council plan\n\n{result.get('report') or result.get('raw_output') or ''}"
    )
    result["raw_output"] = result["report"]
    result["summary"] = format_telegram_summary(result, task_id or "manual")
    return result


def format_improvement(item: dict, detailed: bool = False) -> str:
    base = (
        f"{item.get('improvement_id')} [{item.get('status', 'open')}/{item.get('priority', 'P2')}] "
        f"{compact_line(str(item.get('title') or ''), 140)}"
    )
    if not detailed:
        return base
    lines = [
        f"[Council] Improvement {item.get('improvement_id')}",
        f"status: {item.get('status', 'open')}",
        f"priority: {item.get('priority', 'P2')}",
        f"source: {item.get('source', '')}",
        f"task: {item.get('source_task_id', '')}",
        f"recipe: {item.get('recipe', '')}",
        f"title: {item.get('title', '')}",
        "summary:",
        compact_line(str(item.get("summary") or ""), 1800),
        f"next: {item.get('next_action', '')}",
    ]
    return "\n".join(lines)


def improvements_response(prompt: str = "") -> str:
    parts = prompt.strip().split(maxsplit=2)
    action = parts[0].lower() if parts else "list"
    if action in {"list", "open", "recent"}:
        items = open_improvements(limit=10) if action != "recent" else latest_improvements(limit=10)
        if not items:
            return "[Council] Improvements: brak otwartych kandydatów.\nPętle: error_audit_twice_daily i feature_evolution_loop dopiszą tu nowe propozycje."
        lines = ["[Council] Improvements"]
        for index, item in enumerate(items, start=1):
            lines.append(f"{index}. {format_improvement(item)}")
        lines.append("Użyj: /improve next, /improve show <id>, /improve apply <id>, /improve done <id>, /improve dismiss <id>.")
        return "\n".join(lines)
    if action == "next":
        items = open_improvements(limit=1)
        if not items:
            return "[Council] Brak otwartych improvements. Uruchom /recipe run feature_evolution_loop albo poczekaj na cykl."
        return format_improvement(items[0], detailed=True)
    if action == "show" and len(parts) >= 2:
        item = get_latest_improvement(parts[1])
        return format_improvement(item, detailed=True) if item else f"[Council] Nie znalazłem improvement `{parts[1]}`."
    if action in {"apply", "plan"} and len(parts) >= 2:
        return "[Council] Improvement plan/apply działa w tle. Użyj: /improve apply <id>."
    if action in {"done", "dismiss"} and len(parts) >= 2:
        status = "done" if action == "done" else "dismissed"
        item = update_improvement_status(parts[1], status)
        if not item:
            return f"[Council] Nie znalazłem improvement `{parts[1]}`."
        return f"[Council] Improvement `{parts[1]}` -> {status}."
    return "[Council] Improvements: /improvements, /improve next, /improve show <id>, /improve apply <id>, /improve done <id>, /improve dismiss <id>."


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
    task_seed = f"{clean_prompt}:{source}:{command}:{request_id}:{idempotency_key}:{time.time_ns()}"
    task_id = f"task-{datetime.now().strftime('%Y%m%d-%H%M%S')}-{short_hash(task_seed)[:6]}"
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
    if command == "/recipe":
        return str(route.get("prompt") or "").strip().lower().startswith("run ")
    if command == "/improve":
        return str(route.get("prompt") or "").strip().lower().startswith(("apply ", "plan "))
    if command in MODEL_COMMANDS or command in SIDE_EFFECT_COMMANDS:
        return True
    if command == "/multi":
        return any(route_needs_task(child) for child in route.get("routes", []))
    return False


def route_should_background(route: dict) -> bool:
    command = route.get("command")
    if command == "/recipe":
        return str(route.get("prompt") or "").strip().lower().startswith("run ")
    if command == "/improve":
        return str(route.get("prompt") or "").strip().lower().startswith(("apply ", "plan "))
    if command in BACKGROUND_COMMANDS:
        return True
    if command == "/multi":
        return any(route_should_background(child) for child in route.get("routes", []))
    return False


def append_background_job_event(job: dict) -> None:
    append_jsonl(BACKGROUND_JOBS_FILE, job)


def progress_events_path() -> Path:
    return STATE_DIR / "progress_events.jsonl"


def append_progress_event(
    task_id: str,
    route: dict | None,
    stage: str,
    detail: str = "",
    percent: int | None = None,
) -> dict:
    ensure_council_dirs()
    clean_stage = stage.upper().strip()
    clean_percent = percent if percent is not None else PROGRESS_STAGE_PERCENT.get(clean_stage)
    event = {
        "task_id": task_id,
        "created_at": utc_now(),
        "stage": clean_stage,
        "percent": clean_percent,
        "detail": compact_line(redact_secrets(detail), 500),
        "command": (route or {}).get("command", ""),
        "operators": (route or {}).get("operators", []),
        "summary": background_route_summary(route or {}) if route else "",
    }
    append_jsonl(progress_events_path(), event)
    return event


def latest_progress_events(task_id: str, limit: int = 8) -> list[dict]:
    clean_id = task_id.strip()
    if not clean_id:
        return []
    rows = [row for row in read_jsonl(progress_events_path()) if row.get("task_id") == clean_id]
    return rows[-limit:]


def get_latest_background_job(task_id: str) -> dict | None:
    task_id = task_id.strip()
    latest = {row.get("task_id"): row for row in read_jsonl(BACKGROUND_JOBS_FILE) if row.get("task_id")}
    return latest.get(task_id)


def background_job_spec_path(task_id: str) -> Path:
    return BACKGROUND_JOB_SPECS_DIR / f"{task_id}.json"


def save_background_job_spec(
    route: dict,
    chat_id: str,
    task_id: str,
    send_progress: bool = True,
    send_running: bool | None = None,
) -> Path:
    ensure_council_dirs()
    running_enabled = send_progress if send_running is None else send_running
    spec = {
        "task_id": task_id,
        "chat_id": chat_id,
        "route": route,
        "send_progress": send_progress,
        "send_running": running_enabled,
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


def background_route_summary(route: dict) -> str:
    command = str(route.get("command") or "task")
    operators = ", ".join(str(item) for item in (route.get("operators") or [])) or "host"
    prompt = compact_line(str(route.get("prompt") or ""), 130)
    if prompt:
        return f"{command} / {operators} / {prompt}"
    return f"{command} / {operators}"


def background_progress_message(task_id: str, route: dict, stage: str, detail: str = "") -> str:
    stage = stage.upper().strip()
    percent = PROGRESS_STAGE_PERCENT.get(stage)
    stage_details = {
        "START": "przyjąłem zadanie i uruchamiam workera",
        "PREPARING": "przygotowuję kontekst i operatorów",
        "RUNNING": "operator pracuje w tle",
        "COLLECTING": "zbieram wynik i zapisuję artefakty",
        "DELIVERING": "składam krótkie podsumowanie do Telegrama",
        "COMPLETED": "zadanie zakończone",
        "FAILED": "zadanie zakończone błędem",
        "CANCELLED": "zadanie anulowane",
    }
    lines = [
        f"[AI Council] {task_id}",
        f"ETAP: {stage}",
        f"Postęp: ~{percent}%" if percent is not None else "Postęp: w toku",
        f"Robię: {background_route_summary(route)}",
    ]
    if stage_details.get(stage):
        lines.append(f"Stan: {stage_details[stage]}")
    if detail:
        lines.append(f"Info: {compact_line(detail, 220)}")
    if stage in {"START", "PREPARING", "RUNNING", "COLLECTING", "DELIVERING"}:
        lines.extend(
            [
                "NEXT: poczekaj na wynik albo sprawdź status.",
                f"Status: /status {task_id}",
                f"Progress: /progress {task_id}",
                f"Cancel: /cancel {task_id}",
                f"Details: /details {task_id}",
            ]
        )
    elif stage == "COMPLETED":
        lines.extend(
            [
                f"Details: /details {task_id}",
                f"Facts: /facts {task_id}",
                f"Next: /next {task_id}",
            ]
        )
    elif stage == "FAILED":
        lines.extend(
            [
                f"Details: /details {task_id}",
                "NEXT: sprawdź błąd albo uruchom ponownie z doprecyzowaniem.",
            ]
        )
    elif stage == "CANCELLED":
        lines.append("NEXT: zadanie przerwane; możesz uruchomić je ponownie z krótszym zakresem.")
    return "\n".join(lines)


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
    append_progress_event(task_id, clean_route, "START", f"worker pid={proc.pid}")
    update_task_status(
        task_id,
        "running_background",
        "background worker started",
        worker_pid=proc.pid,
        spec_path=str(spec_path),
        background_log=str(log_path),
    )
    return background_progress_message(task_id, clean_route, "START", f"worker pid={proc.pid}")


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


def progress_event_line(event: dict) -> str:
    stamp = str(event.get("created_at") or "")
    short_stamp = stamp[11:19] if len(stamp) >= 19 else stamp
    percent = event.get("percent")
    percent_text = f" {percent}%" if percent is not None else ""
    detail = compact_line(str(event.get("detail") or ""), 120)
    suffix = f" - {detail}" if detail else ""
    return f"- {short_stamp} {event.get('stage', '')}{percent_text}{suffix}"


def progress_timeline_lines(task_id: str, limit: int = 5) -> list[str]:
    events = latest_progress_events(task_id, limit=limit)
    if not events:
        return []
    return ["progress:"] + [progress_event_line(event) for event in events]


def progress_response(task_id: str) -> str:
    task_id = task_id.strip()
    if not task_id:
        running = [task for task in latest_tasks(limit=20) if task.get("status") in {"running", "running_background"}]
        if not running:
            return "[Council] Brak task_id. Nie widzę aktywnych prac w tle. Użyj: /progress task-..."
        task_id = str(running[0].get("task_id") or "")
        if len(running) > 1:
            other_ids = ", ".join(str(task.get("task_id") or "") for task in running[1:4])
            suffix = f" Inne aktywne: {other_ids}" if other_ids else ""
        else:
            suffix = ""
    else:
        suffix = ""
    task = get_latest_task(task_id)
    events = latest_progress_events(task_id, limit=12)
    if not task and not events:
        return f"[Council] Nie znalazłem progress dla `{task_id}`."
    lines = [f"[Council] Progress {task_id}"]
    if suffix:
        lines.append(suffix.strip())
    if task:
        lines.append(f"status: {task.get('status')}")
        lines.append(f"updated: {task.get('updated_at', task.get('created_at', ''))}")
        if task.get("worker_pid"):
            lines.append(f"worker_pid: {task.get('worker_pid')}")
    if events:
        lines.extend(progress_timeline_lines(task_id, limit=12))
    else:
        lines.append("progress: brak eventów; task powstał przed L4.25 albo worker nie wystartował.")
    lines.append(f"Details: /details {task_id}")
    lines.append(f"Cancel: /cancel {task_id}")
    return "\n".join(lines)


def should_send_intermediate_progress(started: float) -> bool:
    threshold = float_cfg("AI_COUNCIL_PROGRESS_STAGE_SEND_SECONDS", 20.0)
    return threshold <= 0 or (time.time() - started) >= threshold


def start_progress_heartbeat(task_id: str, route: dict, chat_id: str, enabled: bool, started: float) -> tuple[threading.Event, threading.Thread] | None:
    interval = float_cfg("AI_COUNCIL_PROGRESS_HEARTBEAT_SECONDS", 45.0)
    if not enabled or not chat_id or interval <= 0:
        return None
    stop_event = threading.Event()

    def heartbeat() -> None:
        while not stop_event.wait(interval):
            if is_cancelled_id(task_id):
                return
            elapsed = int(time.time() - started)
            detail = f"nadal pracuję; elapsed_s={elapsed}"
            append_progress_event(task_id, route, "RUNNING", detail)
            try:
                telegram_send_message_with_markup(
                    chat_id,
                    background_progress_message(task_id, route, "RUNNING", detail),
                    task_reply_markup(task_id),
                )
            except Exception as exc:
                record_error("progress_heartbeat", exc=exc, event={"task_id": task_id})
                return

    thread = threading.Thread(target=heartbeat, name=f"progress-heartbeat-{task_id}", daemon=True)
    thread.start()
    return stop_event, thread


def stop_progress_heartbeat(heartbeat: tuple[threading.Event, threading.Thread] | None) -> None:
    if not heartbeat:
        return
    stop_event, thread = heartbeat
    stop_event.set()
    if thread.is_alive():
        thread.join(timeout=1.0)


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
        lines.extend(progress_timeline_lines(task_id, limit=5))
        if task.get("report_path"):
            lines.append(f"report: {task.get('report_path')}")
        if task.get("planner_mode"):
            lines.append(f"planner_mode: {task.get('planner_mode')}")
        if task.get("recommended_command"):
            lines.append(f"recommended: {task.get('recommended_command')} {compact_line(str(task.get('recommended_prompt') or ''), 140)}")
        if task.get("recommended_recipe"):
            lines.append(f"recipe: {task.get('recommended_recipe')} ({compact_line(str(task.get('recipe_reason') or ''), 120)})")
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


SOURCE_TEXT_SUFFIXES = {
    ".txt",
    ".md",
    ".markdown",
    ".json",
    ".jsonl",
    ".csv",
    ".log",
    ".html",
    ".htm",
    ".xml",
    ".yaml",
    ".yml",
    ".ics",
}


SOURCE_EXPORT_DEFAULTS = {
    "AI_COUNCIL_GMAIL_EXPORT_DIR": PROJECT_DIR / "sources" / "gmail",
    "AI_COUNCIL_CALENDAR_EXPORT_DIR": PROJECT_DIR / "sources" / "calendar",
    "AI_COUNCIL_DRIVE_EXPORT_DIR": PROJECT_DIR / "sources" / "drive",
}

GOOGLE_OAUTH_TOKEN_URL = "https://oauth2.googleapis.com/token"


CONNECTOR_AUTH_GUIDES = {
    "github": [
        "Na desktopie uruchom: gh auth login -h github.com",
        "Potem sprawdź: gh auth status",
        "Alternatywa read-only: ustaw GITHUB_TOKEN albo GH_TOKEN w .env/system env; nie wklejaj tokena w Telegram.",
        "Opcjonalnie ustaw repo: AI_COUNCIL_GITHUB_REPO=Acoste616/AIagent",
    ],
    "memory": ["Gotowe lokalnie. Użyj: /source search memory <query>."],
    "artifacts": ["Gotowe lokalnie. Użyj: /source search artifacts <query>."],
    "openclaw": ["Gotowe, jeśli OPENCLAW_EXPORT istnieje. Użyj: /source search openclaw <query>."],
}


def configured_source_dir(key: str, default: Path | None = None) -> Path | None:
    value = cfg(key)
    if value:
        return Path(value).expanduser()
    return default


def command_status(command: str, args: list[str], timeout: int = 10) -> tuple[bool, str]:
    found = shutil.which(command)
    if not found:
        return False, "command_missing"
    try:
        completed = subprocess.run(
            [found, *args],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        return False, "timeout"
    except OSError as exc:
        return False, compact_line(str(exc), 160)
    detail = (completed.stdout or completed.stderr or "").strip()
    return completed.returncode == 0, compact_line(detail, 260)


def github_token() -> str:
    return cfg("GITHUB_TOKEN") or cfg("GH_TOKEN") or os.environ.get("GITHUB_TOKEN", "") or os.environ.get("GH_TOKEN", "")


def github_headers(token: str = "") -> dict[str, str]:
    headers = {
        "User-Agent": "ai-council-readonly",
        "Accept": "application/vnd.github+json",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def google_oauth_configured() -> bool:
    return bool(cfg("GOOGLE_CLIENT_ID") and cfg("GOOGLE_CLIENT_SECRET") and cfg("GOOGLE_REFRESH_TOKEN"))


def google_access_token() -> tuple[str, str]:
    if not google_oauth_configured():
        return "oauth_required", ""
    data = request_form_json(
        GOOGLE_OAUTH_TOKEN_URL,
        {
            "client_id": cfg("GOOGLE_CLIENT_ID"),
            "client_secret": cfg("GOOGLE_CLIENT_SECRET"),
            "refresh_token": cfg("GOOGLE_REFRESH_TOKEN"),
            "grant_type": "refresh_token",
        },
        timeout=30,
    )
    if data.get("ok") is False:
        detail = compact_line(str(data.get("body_preview") or data.get("reason") or ""), 180)
        suffix = f" {detail}" if detail else ""
        return f"oauth_error: {data.get('error')}{suffix}", ""
    token = str(data.get("access_token") or "")
    if not token:
        return "oauth_error: missing_access_token", ""
    return "available", token


def google_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}", "Accept": "application/json"}


def source_statuses() -> list[dict]:
    openclaw_dir = configured_source_dir("OPENCLAW_EXPORT", OPENCLAW_EXPORT)
    gmail_dir = configured_source_dir("AI_COUNCIL_GMAIL_EXPORT_DIR", SOURCE_EXPORT_DEFAULTS["AI_COUNCIL_GMAIL_EXPORT_DIR"])
    calendar_dir = configured_source_dir("AI_COUNCIL_CALENDAR_EXPORT_DIR", SOURCE_EXPORT_DEFAULTS["AI_COUNCIL_CALENDAR_EXPORT_DIR"])
    drive_dir = configured_source_dir("AI_COUNCIL_DRIVE_EXPORT_DIR", SOURCE_EXPORT_DEFAULTS["AI_COUNCIL_DRIVE_EXPORT_DIR"])
    gmail_indexed = connector_index_count("gmail")
    calendar_indexed = connector_index_count("calendar")
    drive_indexed = connector_index_count("drive")
    google_oauth = google_oauth_configured()
    gh_ok, gh_detail = command_status("gh", ["auth", "status"], timeout=12)
    gh_token_present = bool(github_token())
    github_repo = cfg("AI_COUNCIL_GITHUB_REPO", "Acoste616/AIagent")
    sources = [
        {
            "name": "memory",
            "status": "available",
            "mode": "read-only",
            "detail": str(MEMORY_DB),
            "search": True,
        },
        {
            "name": "artifacts",
            "status": "available" if ARTIFACTS_DIR.exists() or REPORTS_DIR.exists() else "empty",
            "mode": "read-only",
            "detail": f"{ARTIFACTS_DIR}; {REPORTS_DIR}",
            "search": True,
        },
        {
            "name": "openclaw",
            "status": "available" if openclaw_dir and openclaw_dir.exists() else "unavailable",
            "mode": "read-only",
            "detail": str(openclaw_dir or ""),
            "search": bool(openclaw_dir and openclaw_dir.exists()),
        },
        {
            "name": "github",
            "status": "available" if gh_ok else ("token_present" if gh_token_present else "auth_required"),
            "mode": "read-only",
            "detail": github_repo if gh_ok else (f"{github_repo}; token configured; gh auth status: {gh_detail}" if gh_token_present else f"gh auth status: {gh_detail}"),
            "search": gh_ok or gh_token_present or bool_cfg("AI_COUNCIL_GITHUB_PUBLIC_FALLBACK", True),
        },
        {
            "name": "gmail",
            "status": "available" if gmail_dir and gmail_dir.exists() else ("indexed" if gmail_indexed else ("oauth_present" if google_oauth else "auth_required")),
            "mode": "read-only",
            "detail": f"{gmail_dir or 'set AI_COUNCIL_GMAIL_EXPORT_DIR or Gmail OAuth bridge'}; indexed={gmail_indexed}; oauth={'yes' if google_oauth else 'no'}",
            "search": bool(gmail_dir and gmail_dir.exists()) or gmail_indexed > 0,
        },
        {
            "name": "calendar",
            "status": "available" if calendar_dir and calendar_dir.exists() else ("indexed" if calendar_indexed else ("oauth_present" if google_oauth else "auth_required")),
            "mode": "read-only",
            "detail": f"{calendar_dir or 'set AI_COUNCIL_CALENDAR_EXPORT_DIR or Calendar OAuth bridge'}; indexed={calendar_indexed}; oauth={'yes' if google_oauth else 'no'}",
            "search": bool(calendar_dir and calendar_dir.exists()) or calendar_indexed > 0,
        },
        {
            "name": "drive",
            "status": "available" if drive_dir and drive_dir.exists() else ("indexed" if drive_indexed else ("oauth_present" if google_oauth else "auth_required")),
            "mode": "read-only",
            "detail": f"{drive_dir or 'set AI_COUNCIL_DRIVE_EXPORT_DIR or Drive OAuth bridge'}; indexed={drive_indexed}; oauth={'yes' if google_oauth else 'no'}",
            "search": bool(drive_dir and drive_dir.exists()) or drive_indexed > 0,
        },
    ]
    return sources


def source_status(name: str) -> dict | None:
    normalized = name.strip().lower()
    return next((item for item in source_statuses() if item["name"] == normalized), None)


def sources_response() -> str:
    lines = ["[Council] Sources read-only"]
    for item in source_statuses():
        lines.append(
            f"- {item['name']} | {item['status']} | {item['mode']} | search={'yes' if item.get('search') else 'no'} | {compact_line(str(item.get('detail') or ''), 120)}"
        )
    lines.append("Użyj: /source search <name> <query>. Google: /connector sync gmail|calendar|drive <query>. Write/send/schedule wymagają Risk Officer i approval.")
    return "\n".join(lines)


def text_file_matches(path: Path, query: str) -> bool:
    if path.suffix.lower() not in SOURCE_TEXT_SUFFIXES:
        return False
    if not query:
        return True
    try:
        preview = path.read_text(encoding="utf-8", errors="replace")[:20000]
    except OSError:
        return False
    return query.lower() in preview.lower() or query.lower() in path.name.lower()


def search_text_source(paths: list[Path], query: str, limit: int = 5) -> list[dict]:
    results: list[dict] = []
    max_files = int_cfg("AI_COUNCIL_SOURCE_SEARCH_MAX_FILES", 350)
    scanned = 0
    for root in paths:
        if not root or not root.exists():
            continue
        files = [root] if root.is_file() else root.rglob("*")
        for path in files:
            if len(results) >= limit:
                return results
            if scanned >= max_files:
                return results
            if not path.is_file():
                continue
            scanned += 1
            if not path.is_file() or not text_file_matches(path, query):
                continue
            try:
                text = path.read_text(encoding="utf-8", errors="replace")
            except OSError:
                text = ""
            snippet = ""
            if query:
                index = text.lower().find(query.lower())
                if index >= 0:
                    start = max(0, index - 140)
                    snippet = text[start : start + 320]
            if not snippet:
                snippet = text[:320]
            results.append({"source": str(path), "title": path.name, "snippet": compact_line(snippet, 260)})
    return results


def init_connector_index_db() -> None:
    ensure_council_dirs()
    with sqlite3.connect(CONNECTOR_INDEX_DB) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS connector_documents (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                connector TEXT NOT NULL,
                doc_id TEXT UNIQUE NOT NULL,
                title TEXT NOT NULL,
                source TEXT NOT NULL,
                text TEXT NOT NULL,
                metadata TEXT NOT NULL,
                indexed_at TEXT NOT NULL
            )
            """
        )
        try:
            conn.execute(
                """
                CREATE VIRTUAL TABLE IF NOT EXISTS connector_documents_fts
                USING fts5(doc_id, connector, title, source, text)
                """
            )
        except sqlite3.OperationalError:
            pass


def connector_index_upsert(connector: str, title: str, source: str, text: str, metadata: dict | None = None) -> None:
    init_connector_index_db()
    doc_id = f"{connector}:{short_hash(source)}"
    clean_text = text.strip()
    with sqlite3.connect(CONNECTOR_INDEX_DB) as conn:
        conn.execute(
            """
            INSERT OR REPLACE INTO connector_documents
            (connector, doc_id, title, source, text, metadata, indexed_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                connector,
                doc_id,
                title.strip() or source,
                source,
                clean_text,
                json.dumps(metadata or {}, ensure_ascii=False),
                utc_now(),
            ),
        )
        try:
            conn.execute("DELETE FROM connector_documents_fts WHERE doc_id = ?", (doc_id,))
            conn.execute(
                """
                INSERT INTO connector_documents_fts (doc_id, connector, title, source, text)
                VALUES (?, ?, ?, ?, ?)
                """,
                (doc_id, connector, title.strip() or source, source, clean_text),
            )
        except sqlite3.OperationalError:
            pass


def connector_index_count(connector: str) -> int:
    init_connector_index_db()
    with sqlite3.connect(CONNECTOR_INDEX_DB) as conn:
        row = conn.execute("SELECT COUNT(*) FROM connector_documents WHERE connector = ?", (connector,)).fetchone()
    return int(row[0] if row else 0)


def connector_index_search(connector: str, query: str, limit: int = 5) -> list[dict]:
    init_connector_index_db()
    clean_query = query.strip()
    with sqlite3.connect(CONNECTOR_INDEX_DB) as conn:
        conn.row_factory = sqlite3.Row
        if clean_query:
            try:
                phrase = '"' + clean_query.replace('"', '""') + '"'
                rows = conn.execute(
                    """
                    SELECT d.title, d.source, d.text, d.indexed_at
                    FROM connector_documents_fts f
                    JOIN connector_documents d ON d.doc_id = f.doc_id
                    WHERE connector_documents_fts MATCH ? AND d.connector = ?
                    ORDER BY d.id DESC
                    LIMIT ?
                    """,
                    (phrase, connector, limit),
                ).fetchall()
            except sqlite3.OperationalError:
                like = f"%{clean_query}%"
                rows = conn.execute(
                    """
                    SELECT title, source, text, indexed_at
                    FROM connector_documents
                    WHERE connector = ? AND (title LIKE ? OR source LIKE ? OR text LIKE ?)
                    ORDER BY id DESC
                    LIMIT ?
                    """,
                    (connector, like, like, like, limit),
                ).fetchall()
        else:
            rows = conn.execute(
                """
                SELECT title, source, text, indexed_at
                FROM connector_documents
                WHERE connector = ?
                ORDER BY id DESC
                LIMIT ?
                """,
                (connector, limit),
            ).fetchall()
    results = []
    for row in rows:
        text = str(row["text"] or "")
        snippet = text[:320]
        if clean_query:
            index = text.lower().find(clean_query.lower())
            if index >= 0:
                start = max(0, index - 140)
                snippet = text[start : start + 320]
        results.append(
            {
                "source": str(row["source"]),
                "title": str(row["title"]),
                "snippet": compact_line(snippet, 260),
            }
        )
    return results


def merge_source_results(*groups: list[dict], limit: int = 5) -> list[dict]:
    merged: list[dict] = []
    seen: set[str] = set()
    for group in groups:
        for item in group:
            source = str(item.get("source") or "")
            key = source or f"{item.get('title', '')}:{item.get('snippet', '')}"
            if key in seen:
                continue
            seen.add(key)
            merged.append(item)
            if len(merged) >= limit:
                return merged
    return merged


def extract_connector_file_text(path: Path) -> str:
    suffix = path.suffix.lower()
    try:
        if suffix == ".csv":
            csv_rows = int_cfg("AI_COUNCIL_CONNECTOR_INDEX_CSV_ROWS", 40)
            rows = []
            with path.open("r", encoding="utf-8", errors="replace", newline="") as handle:
                reader = csv.reader(handle)
                for index, row in enumerate(reader):
                    if index >= csv_rows:
                        break
                    rows.append(" | ".join(cell.strip() for cell in row if cell.strip()))
            return "\n".join(row for row in rows if row)
        if suffix in SOURCE_TEXT_SUFFIXES:
            return path.read_text(encoding="utf-8", errors="replace")[: int_cfg("AI_COUNCIL_CONNECTOR_INDEX_FILE_CHARS", 30000)]
    except OSError:
        return ""
    return ""


def connector_ingest_source(connector: str, limit: int | None = None) -> tuple[str, int, Path | None]:
    normalized = normalize_connector_name(connector)
    env_map = {
        "gmail": "AI_COUNCIL_GMAIL_EXPORT_DIR",
        "calendar": "AI_COUNCIL_CALENDAR_EXPORT_DIR",
        "drive": "AI_COUNCIL_DRIVE_EXPORT_DIR",
    }
    if normalized not in env_map:
        return "unsupported", 0, None
    root = configured_source_dir(env_map[normalized], SOURCE_EXPORT_DEFAULTS.get(env_map[normalized]))
    if not root or not root.exists():
        return "auth_required", 0, root
    max_files = limit if limit is not None else int_cfg("AI_COUNCIL_CONNECTOR_INGEST_MAX_FILES", 500)
    max_visited = int_cfg("AI_COUNCIL_CONNECTOR_INGEST_MAX_VISITED", max_files * 20)
    indexed = 0
    visited = 0
    files = [root] if root.is_file() else root.rglob("*")
    for path in files:
        visited += 1
        if visited > max_visited:
            break
        if indexed >= max_files:
            break
        if not path.is_file() or path.suffix.lower() not in SOURCE_TEXT_SUFFIXES:
            continue
        text = extract_connector_file_text(path)
        if not text.strip():
            continue
        stat = path.stat()
        connector_index_upsert(
            normalized,
            path.name,
            str(path),
            text,
            {"size": stat.st_size, "mtime": stat.st_mtime},
        )
        indexed += 1
    return "available", indexed, root


def github_public_search(query: str, limit: int = 5) -> tuple[str, list[dict]]:
    if not bool_cfg("AI_COUNCIL_GITHUB_PUBLIC_FALLBACK", True):
        return "public_fallback_disabled", []
    return github_api_search(query, limit=limit, token="", status_label="public_fallback")


def github_api_search(query: str, limit: int = 5, token: str = "", status_label: str = "github_api") -> tuple[str, list[dict]]:
    repo = cfg("AI_COUNCIL_GITHUB_REPO", "Acoste616/AIagent")
    q = f"{query or 'AI Council'} repo:{repo}"
    url = "https://api.github.com/search/issues?" + urlencode({"q": q, "per_page": str(limit)})
    data = request_json(url, headers=github_headers(token))
    if data.get("ok") is False:
        return f"{status_label}_error: {data.get('error')}", []
    results = []
    for item in data.get("items", [])[:limit]:
        labels = ", ".join(label.get("name", "") for label in item.get("labels", []) if isinstance(label, dict))
        snippet = compact_line(str(item.get("body") or item.get("title") or ""), 260)
        if labels:
            snippet = compact_line(f"{snippet} labels={labels}", 260)
        results.append(
            {
                "source": str(item.get("html_url") or repo),
                "title": f"#{item.get('number')} {item.get('title')}",
                "snippet": snippet,
            }
        )
    return status_label, results


def github_source_search(query: str, limit: int = 5) -> tuple[str, list[dict]]:
    gh_ok, gh_detail = command_status("gh", ["auth", "status"], timeout=12)
    if not gh_ok:
        token = github_token()
        if token:
            token_status, token_results = github_api_search(query, limit=limit, token=token, status_label="token_api")
            if token_results:
                return f"{token_status}; gh_unavailable: {gh_detail}", token_results
            if "http_401" in token_status or "http_403" in token_status:
                return f"{token_status}; gh_unavailable: {gh_detail}", []
            public_status, public_results = github_public_search(query, limit=limit)
            if public_results:
                return f"{token_status}; gh_unavailable: {gh_detail}; {public_status}", public_results
            return f"{token_status}; gh_unavailable: {gh_detail}; {public_status}", []
        public_status, public_results = github_public_search(query, limit=limit)
        if public_results:
            return f"auth_required: {gh_detail}; {public_status}", public_results
        return f"auth_required: {gh_detail}; {public_status}", []
    repo = cfg("AI_COUNCIL_GITHUB_REPO", "Acoste616/AIagent")
    found = shutil.which("gh")
    if not found:
        return "command_missing", []
    try:
        completed = subprocess.run(
            [
                found,
                "issue",
                "list",
                "--repo",
                repo,
                "--search",
                query or "AI Council",
                "--limit",
                str(limit),
                "--json",
                "number,title,state,url,updatedAt",
            ],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=20,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return compact_line(str(exc), 200), []
    if completed.returncode != 0:
        return compact_line(completed.stderr or completed.stdout or "github query failed", 240), []
    try:
        issues = json.loads(completed.stdout or "[]")
    except json.JSONDecodeError:
        issues = []
    results = [
        {
            "source": str(item.get("url") or repo),
            "title": f"#{item.get('number')} {item.get('title')}",
            "snippet": f"{item.get('state')} updated {item.get('updatedAt')}",
        }
        for item in issues
    ]
    return "available", results


def source_search(name: str, query: str, limit: int = 5) -> tuple[str, list[dict]]:
    normalized = name.strip().lower()
    if normalized == "memory":
        rows = memory_search(query, limit=limit)
        return "available", [
            {
                "source": f"memory:{row.get('entry_id')}",
                "title": str(row.get("key") or ""),
                "snippet": compact_line(str(row.get("value") or ""), 260),
            }
            for row in rows
        ]
    if normalized == "artifacts":
        return "available", search_text_source([ARTIFACTS_DIR, REPORTS_DIR, CLAUDE_COLLAB_DIR], query, limit=limit)
    if normalized == "openclaw":
        root = configured_source_dir("OPENCLAW_EXPORT", OPENCLAW_EXPORT)
        if not root or not root.exists():
            return "unavailable", []
        return "available", search_text_source([root], query, limit=limit)
    if normalized == "github":
        return github_source_search(query, limit=limit)
    env_map = {
        "gmail": "AI_COUNCIL_GMAIL_EXPORT_DIR",
        "calendar": "AI_COUNCIL_CALENDAR_EXPORT_DIR",
        "drive": "AI_COUNCIL_DRIVE_EXPORT_DIR",
    }
    if normalized in env_map:
        root = configured_source_dir(env_map[normalized], SOURCE_EXPORT_DEFAULTS.get(env_map[normalized]))
        indexed_results = connector_index_search(normalized, query, limit=limit)
        if not root or not root.exists():
            return ("available_index", indexed_results) if indexed_results else ("auth_required", [])
        file_results = search_text_source([root], query, limit=limit)
        combined = merge_source_results(indexed_results, file_results, limit=limit)
        if combined:
            return ("available_index" if indexed_results else "available"), combined
        return "available", []
    return "unknown_source", []


def source_response(prompt: str) -> str:
    parts = prompt.strip().split(maxsplit=2)
    if not parts:
        return sources_response()
    action = parts[0].lower()
    if action == "status":
        return sources_response()
    if action == "search" and len(parts) >= 2:
        name = parts[1]
        query = parts[2] if len(parts) >= 3 else ""
    else:
        name = parts[0]
        query = parts[1] if len(parts) >= 2 else ""
    status, results = source_search(name, query, limit=int_cfg("AI_COUNCIL_SOURCE_SEARCH_LIMIT", 5))
    lines = [f"[Council] Source search `{name}`", f"status: {status}", f"query: {query or '(recent)'}"]
    if not results:
        lines.append("Źródła: brak wyników albo źródło wymaga auth/config.")
    else:
        lines.append("Źródła:")
        for index, item in enumerate(results, start=1):
            lines.append(f"{index}. {compact_line(item.get('title', ''), 90)}")
            lines.append(f"   source: {compact_line(item.get('source', ''), 160)}")
            lines.append(f"   snippet: {compact_line(item.get('snippet', ''), 220)}")
    lines.append("Tryb: read-only. Write/send/schedule wymagają approval.")
    return "\n".join(lines)


def normalize_connector_name(name: str) -> str:
    normalized = normalize_intent_text(name).replace("_", "-")
    aliases = {
        "git": "github",
        "repo": "github",
        "mail": "gmail",
        "email": "gmail",
        "kalendarz": "calendar",
        "calendar": "calendar",
        "docs": "drive",
        "google-drive": "drive",
        "google drive": "drive",
        "openclaw export": "openclaw",
    }
    if normalized in aliases:
        return aliases[normalized]
    if normalized.startswith("google "):
        normalized = normalized.replace("google ", "", 1)
    return aliases.get(normalized, normalized)


def connector_auth_steps(name: str) -> list[str]:
    normalized = normalize_connector_name(name)
    if normalized == "gmail":
        return [
            f"Tryb read-only v0: wyeksportuj/search cache maili do {SOURCE_EXPORT_DEFAULTS['AI_COUNCIL_GMAIL_EXPORT_DIR']} albo ustaw AI_COUNCIL_GMAIL_EXPORT_DIR.",
            "OAuth read-sync: ustaw GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET i GOOGLE_REFRESH_TOKEN w .env/system env.",
            "Potem użyj: /connector sync gmail <query>. Wysyłka maili zostaje R3 i wymaga approval.",
        ]
    if normalized == "calendar":
        return [
            f"Tryb read-only v0: zapisz .ics/.json/.md do {SOURCE_EXPORT_DEFAULTS['AI_COUNCIL_CALENDAR_EXPORT_DIR']} albo ustaw AI_COUNCIL_CALENDAR_EXPORT_DIR.",
            "OAuth read-sync: ustaw GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET i GOOGLE_REFRESH_TOKEN w .env/system env.",
            "Potem użyj: /connector sync calendar <query>. Tworzenie wydarzeń zostaje R3 i wymaga approval.",
        ]
    if normalized == "drive":
        return [
            f"Tryb read-only v0: zsynchronizuj/wyeksportuj Docs/Drive do {SOURCE_EXPORT_DEFAULTS['AI_COUNCIL_DRIVE_EXPORT_DIR']} albo ustaw AI_COUNCIL_DRIVE_EXPORT_DIR.",
            "OAuth read-sync: ustaw GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET i GOOGLE_REFRESH_TOKEN w .env/system env.",
            "Potem użyj: /connector sync drive <query>. Edycja Drive/Docs zostaje R3 i wymaga approval.",
        ]
    return CONNECTOR_AUTH_GUIDES.get(normalized, [])


def connector_statuses() -> list[dict]:
    statuses = []
    google_sync_ready = google_oauth_configured()
    for item in source_statuses():
        name = str(item.get("name") or "")
        status = str(item.get("status") or "unknown")
        ready = status in {"available", "indexed", "oauth_present", "token_present"}
        if name in {"memory", "artifacts", "openclaw"}:
            tier = "local"
        elif name == "github":
            tier = "cli-oauth"
        else:
            tier = "export-or-oauth"
        statuses.append(
            {
                **item,
                "tier": tier,
                "ready": ready,
                "sync": name in {"gmail", "calendar", "drive"} and google_sync_ready,
                "auth_steps": connector_auth_steps(name),
            }
        )
    return statuses


def connector_status(name: str) -> dict | None:
    normalized = normalize_connector_name(name)
    return next((item for item in connector_statuses() if item.get("name") == normalized), None)


def connectors_response() -> str:
    lines = ["[Council] Connectors L4.28 read-sync + integration action drafts"]
    ready = 0
    needs_auth = 0
    for item in connector_statuses():
        if item.get("ready"):
            ready += 1
        elif item.get("status") in {"auth_required", "unavailable"}:
            needs_auth += 1
        lines.append(
            f"- {item['name']} | {item['status']} | {item['tier']} | search={'yes' if item.get('search') else 'no'} | sync={'yes' if item.get('sync') else 'no'} | {compact_line(str(item.get('detail') or ''), 110)}"
        )
    lines.append(f"Ready: {ready}. Needs auth/config: {needs_auth}.")
    lines.append("Użyj: /connector check <name>, /connector auth <name>, /connector ingest <name>, /connector sync <name> <query>, /connector brief <name> <query>, /connector draft <name> <intent>.")
    return "\n".join(lines)


def connector_check_response(name: str) -> str:
    item = connector_status(name)
    if not item:
        return "[Council] Nie znam tego connectora. Użyj: /connectors."
    lines = [
        f"[Council] Connector `{item['name']}`",
        f"status: {item.get('status')}",
        f"tier: {item.get('tier')}",
        f"mode: {item.get('mode')}",
        f"search: {'yes' if item.get('search') else 'no'}",
        f"detail: {compact_line(str(item.get('detail') or ''), 240)}",
    ]
    if item.get("auth_steps"):
        lines.append("Auth/setup:")
        for step in item["auth_steps"]:
            lines.append(f"- {step}")
    lines.append("Granica: read-only teraz; write/send/schedule dopiero po Risk Officer i approval.")
    return "\n".join(lines)


def connector_auth_response(name: str) -> str:
    item = connector_status(name)
    if not item:
        normalized = normalize_connector_name(name)
        steps = connector_auth_steps(normalized)
        if not steps:
            return "[Council] Nie znam tego connectora. Użyj: /connectors."
        item = {"name": normalized, "status": "unknown", "auth_steps": steps}
    lines = [f"[Council] Auth/setup `{item['name']}`", f"current_status: {item.get('status', 'unknown')}"]
    for step in item.get("auth_steps") or ["Brak instrukcji dla tego connectora."]:
        lines.append(f"- {step}")
    lines.append("Nie wklejaj tokenów w Telegram. Sekrety zostają w .env albo w natywnym loginie CLI/OAuth.")
    return "\n".join(lines)


def connector_brief_response(name: str, query: str) -> str:
    normalized = normalize_connector_name(name)
    if not query.strip():
        return (
            f"[Council] Connector brief `{normalized}` wymaga query.\n"
            f"Użyj: /connector brief {normalized} <czego szukać>\n"
            f"Status connectora: /connector check {normalized}"
        )
    status, results = source_search(normalized, query, limit=int_cfg("AI_COUNCIL_CONNECTOR_BRIEF_LIMIT", 8))
    ensure_council_dirs()
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    report_path = REPORTS_DIR / f"connector-brief-{safe_filename(normalized, 'connector')}-{stamp}.md"
    lines = [
        f"# Connector Brief: {normalized}",
        "",
        f"- status: {status}",
        f"- query: {query or '(recent)'}",
        f"- created_at: {utc_now()}",
        "",
        "## Sources",
    ]
    if results:
        for index, item in enumerate(results, start=1):
            lines.extend(
                [
                    f"{index}. {item.get('title', '')}",
                    f"   - source: {item.get('source', '')}",
                    f"   - snippet: {item.get('snippet', '')}",
                ]
            )
    else:
        lines.append("Brak wyników albo connector wymaga auth/config.")
    lines.extend(["", "## Policy", "Read-only. Write/send/schedule wymagają Risk Officer i approval."])
    report_path.write_text("\n".join(lines), encoding="utf-8")
    response = [
        f"[Council] Connector brief `{normalized}`",
        f"status: {status}",
        f"results: {len(results)}",
        f"report: {report_path}",
    ]
    if not results:
        response.append(f"Next: /connector auth {normalized}")
    else:
        response.append(f"Next: /source search {normalized} {query}".strip())
    return "\n".join(response)


def integration_connector_for_intent(text: str) -> str:
    lower = normalize_intent_text(text)
    def has_any(tokens: tuple[str, ...]) -> bool:
        for token in tokens:
            if " " in token:
                if token in lower:
                    return True
            elif re.search(rf"(?<!\w){re.escape(token)}(?!\w)", lower):
                return True
        return False

    if has_any(("gmail", "mail", "maila", "mailu", "email", "emaila", "emailu", "wiadomość email", "wiadomosc email")):
        return "gmail"
    if has_any(("calendar", "kalendarz", "meeting", "spotkanie", "umów", "umow", "schedule")):
        return "calendar"
    if has_any(("github", "issue", "pull request", "pr", "repo", "commit")):
        return "github"
    if has_any(("drive", "docs", "doc", "document", "dokument", "plik")):
        return "drive"
    return ""


def integration_draft_kind(connector: str) -> str:
    return {
        "gmail": "email_draft",
        "calendar": "calendar_event_draft",
        "drive": "drive_document_draft",
        "github": "github_issue_or_pr_draft",
    }.get(connector, "integration_draft")


def integration_draft_payload(connector: str, intent: str, source: str = "", task_id: str = "") -> dict:
    clean = compact_line(intent.strip() or "integration draft", 1200)
    missing: list[str] = []
    if connector == "gmail":
        missing = ["recipient", "exact_subject", "final_body_review"]
        signature = cfg("AI_COUNCIL_SIGNATURE", "Bartek")
        draft = {
            "to": "",
            "subject": f"Draft: {compact_line(clean, 70)}",
            "body": f"Cześć,\n\n{clean}\n\nPozdrawiam,\n{signature}",
        }
    elif connector == "calendar":
        missing = ["attendees", "start_time", "end_time", "timezone"]
        draft = {
            "summary": compact_line(clean, 90),
            "start": "",
            "end": "",
            "attendees": [],
            "description": clean,
        }
    elif connector == "drive":
        missing = ["target_folder_or_file", "final_title"]
        draft = {
            "title": f"Draft: {compact_line(clean, 80)}",
            "outline": ["Cel", clean, "Następne kroki"],
            "body": clean,
        }
    elif connector == "github":
        missing = ["target_repo", "issue_or_pr_type", "labels"]
        draft = {
            "repo": cfg("AI_COUNCIL_GITHUB_REPO", ""),
            "title": compact_line(clean, 90),
            "body": clean,
            "labels": [],
        }
    else:
        missing = ["supported_connector"]
        draft = {"body": clean}
    return {
        "connector": connector,
        "draft_kind": integration_draft_kind(connector),
        "intent": clean,
        "draft": draft,
        "missing_fields": missing,
        "source": source,
        "task_id": task_id,
        "external_write": False,
        "execution_policy": "draft_only; approval records decision but does not send/write/schedule/publish",
    }


def create_integration_draft_action(
    connector: str,
    intent: str,
    *,
    risk: str = "",
    source: str = "connector_draft",
    task_id: str = "",
) -> dict | None:
    normalized = normalize_connector_name(connector)
    if normalized not in INTEGRATION_DRAFT_CONNECTORS:
        return None
    draft_risk, draft_reason = risk_level_for_text(f"{normalized} {intent}")
    if draft_risk == "R0":
        draft_risk = "R3"
        draft_reason = "integration draft targets external write-capable connector"
    if risk:
        draft_risk, draft_reason = stricter_risk((draft_risk, draft_reason), normalize_risk(risk, intent))
    payload = integration_draft_payload(normalized, intent, source=source, task_id=task_id)
    payload["risk_reason"] = draft_reason
    return create_action(
        f"Integration draft `{normalized}`: {compact_line(intent, 180)}",
        action_type="integration_draft",
        risk=draft_risk,
        payload=payload,
    )


def format_integration_draft_action(action: dict, detailed: bool = False) -> str:
    payload = action.get("payload") or {}
    draft = payload.get("draft") or {}
    base = (
        f"{action.get('action_id')} | {action.get('status')} | {action.get('risk')} | "
        f"{payload.get('connector', '')}/{payload.get('draft_kind', '')} | {compact_line(action.get('description', ''), 110)}"
    )
    if not detailed:
        return base
    lines = [
        f"[Council] Integration Draft {action.get('action_id')}",
        f"status: {action.get('status')}",
        f"risk: {action.get('risk')} - {payload.get('risk_reason') or action.get('risk_reason')}",
        f"connector: {payload.get('connector')}",
        f"kind: {payload.get('draft_kind')}",
        f"intent: {payload.get('intent')}",
        f"missing_fields: {', '.join(payload.get('missing_fields') or []) or 'none'}",
        "draft:",
    ]
    for key, value in draft.items():
        lines.append(f"- {key}: {compact_line(json.dumps(value, ensure_ascii=False) if isinstance(value, (list, dict)) else str(value), 260)}")
    lines.extend(
        [
            "policy: draft-only; no external write/send/schedule/publish.",
            f"approve: /approve {action.get('action_id')}",
            f"deny: /deny {action.get('action_id')}",
        ]
    )
    return "\n".join(lines)


def integration_drafts_response(prompt: str = "") -> str:
    parts = prompt.strip().split(maxsplit=1)
    if parts and parts[0].lower() in {"show", "details"} and len(parts) < 2:
        return "[Council] Użyj: /drafts show <action_id>."
    if parts and parts[0].lower() in {"show", "details"} and len(parts) >= 2:
        action = get_latest_action(parts[1])
        if not action or action.get("type") != "integration_draft":
            return f"[Council] Nie znalazłem integration draft `{parts[1]}`."
        return format_integration_draft_action(action, detailed=True)
    rows = [
        action
        for action in latest_by_id(ACTIONS_FILE, "action_id", limit=200)
        if action.get("type") == "integration_draft"
    ]
    if not rows:
        return "[Council] Integration Drafts L4.28: brak draftów.\nUżyj: /connector draft gmail|calendar|drive|github <intencja>."
    lines = ["[Council] Integration Drafts L4.28"]
    for action in rows[:10]:
        lines.append("- " + format_integration_draft_action(action))
    lines.append("Użyj: /drafts show <id>, /approve <id>, /deny <id>. /execute dla R3/R4 jest blokowane.")
    return "\n".join(lines)


def gmail_header(headers: list[dict], name: str) -> str:
    target = name.lower()
    for header in headers or []:
        if str(header.get("name", "")).lower() == target:
            return str(header.get("value") or "")
    return ""


def google_sync_gmail(query: str = "", limit: int = 10) -> tuple[str, int]:
    status, token = google_access_token()
    if not token:
        return status, 0
    params = {"maxResults": str(limit)}
    if query.strip():
        params["q"] = query.strip()
    list_url = "https://gmail.googleapis.com/gmail/v1/users/me/messages?" + urlencode(params)
    data = request_json(list_url, headers=google_headers(token), timeout=30)
    if data.get("ok") is False:
        return f"gmail_error: {data.get('error')}", 0
    indexed = 0
    for item in (data.get("messages") or [])[:limit]:
        message_id = str(item.get("id") or "")
        if not message_id:
            continue
        get_params = [
            ("format", "metadata"),
            ("metadataHeaders", "Subject"),
            ("metadataHeaders", "From"),
            ("metadataHeaders", "To"),
            ("metadataHeaders", "Date"),
        ]
        msg_url = f"https://gmail.googleapis.com/gmail/v1/users/me/messages/{message_id}?" + urlencode(get_params)
        message = request_json(msg_url, headers=google_headers(token), timeout=30)
        if message.get("ok") is False:
            continue
        headers = ((message.get("payload") or {}).get("headers") or [])
        subject = gmail_header(headers, "Subject") or "(no subject)"
        sender = gmail_header(headers, "From")
        to = gmail_header(headers, "To")
        date = gmail_header(headers, "Date")
        snippet = str(message.get("snippet") or "")
        text = f"Subject: {subject}\nFrom: {sender}\nTo: {to}\nDate: {date}\nSnippet: {snippet}"
        connector_index_upsert(
            "gmail",
            subject,
            f"gmail:{message_id}",
            text,
            {"id": message_id, "thread_id": message.get("threadId", ""), "query": query},
        )
        indexed += 1
    return "available", indexed


def google_sync_calendar(query: str = "", limit: int = 10) -> tuple[str, int]:
    status, token = google_access_token()
    if not token:
        return status, 0
    params = {
        "maxResults": str(limit),
        "singleEvents": "true",
        "orderBy": "startTime",
        "timeMin": utc_now_rfc3339_z(),
    }
    if query.strip():
        params["q"] = query.strip()
    url = "https://www.googleapis.com/calendar/v3/calendars/primary/events?" + urlencode(params)
    data = request_json(url, headers=google_headers(token), timeout=30)
    if data.get("ok") is False:
        return f"calendar_error: {data.get('error')}", 0
    indexed = 0
    for event in (data.get("items") or [])[:limit]:
        event_id = str(event.get("id") or "")
        if not event_id:
            continue
        title = str(event.get("summary") or "(untitled event)")
        start = (event.get("start") or {}).get("dateTime") or (event.get("start") or {}).get("date") or ""
        end = (event.get("end") or {}).get("dateTime") or (event.get("end") or {}).get("date") or ""
        location = str(event.get("location") or "")
        description = str(event.get("description") or "")
        text = f"Event: {title}\nStart: {start}\nEnd: {end}\nLocation: {location}\nDescription: {description}"
        connector_index_upsert(
            "calendar",
            title,
            f"calendar:{event_id}",
            text,
            {"id": event_id, "html_link": event.get("htmlLink", ""), "query": query},
        )
        indexed += 1
    return "available", indexed


def drive_query(query: str) -> str:
    clean = query.strip().replace("\\", "\\\\").replace("'", "\\'")
    if clean:
        return f"name contains '{clean}' and trashed = false"
    return "trashed = false"


def google_sync_drive(query: str = "", limit: int = 10) -> tuple[str, int]:
    status, token = google_access_token()
    if not token:
        return status, 0
    params = {
        "pageSize": str(limit),
        "q": drive_query(query),
        "fields": "files(id,name,mimeType,webViewLink,modifiedTime,description)",
    }
    url = "https://www.googleapis.com/drive/v3/files?" + urlencode(params)
    data = request_json(url, headers=google_headers(token), timeout=30)
    if data.get("ok") is False:
        return f"drive_error: {data.get('error')}", 0
    indexed = 0
    for item in (data.get("files") or [])[:limit]:
        file_id = str(item.get("id") or "")
        if not file_id:
            continue
        name = str(item.get("name") or "(untitled file)")
        text = (
            f"File: {name}\n"
            f"MimeType: {item.get('mimeType', '')}\n"
            f"Modified: {item.get('modifiedTime', '')}\n"
            f"Link: {item.get('webViewLink', '')}\n"
            f"Description: {item.get('description', '')}"
        )
        connector_index_upsert(
            "drive",
            name,
            f"drive:{file_id}",
            text,
            {"id": file_id, "web_view_link": item.get("webViewLink", ""), "query": query},
        )
        indexed += 1
    return "available", indexed


def google_sync_connector(name: str, query: str = "") -> tuple[str, int]:
    normalized = normalize_connector_name(name)
    limit = max(1, min(int_cfg("AI_COUNCIL_GOOGLE_SYNC_LIMIT", 10), int_cfg("AI_COUNCIL_GOOGLE_SYNC_LIMIT_MAX", 50)))
    if normalized == "gmail":
        return google_sync_gmail(query, limit=limit)
    if normalized == "calendar":
        return google_sync_calendar(query, limit=limit)
    if normalized == "drive":
        return google_sync_drive(query, limit=limit)
    return "unsupported", 0


def connector_sync_response(name: str, query: str = "") -> str:
    normalized = normalize_connector_name(name)
    status, synced = google_sync_connector(normalized, query=query)
    lines = [
        f"[Council] Connector sync `{normalized}`",
        f"status: {status}",
        f"synced_now: {synced}",
        f"indexed_total: {connector_index_count(normalized) if normalized in {'gmail', 'calendar', 'drive'} else 0}",
    ]
    if status == "oauth_required":
        lines.append(f"Next: /connector auth {normalized}")
    elif status == "unsupported":
        lines.append("Obsługiwane OAuth sync: gmail, calendar, drive.")
    elif "error" in status:
        lines.append(f"Next: sprawdź konfigurację/scopes: /connector auth {normalized}; błędy: /errors recent 10")
    else:
        lines.append(f"Next: /connector brief {normalized} {query or '<query>'}".strip())
    return "\n".join(lines)


def connector_ingest_response(name: str) -> str:
    normalized = normalize_connector_name(name)
    status, indexed, root = connector_ingest_source(normalized)
    lines = [
        f"[Council] Connector ingest `{normalized}`",
        f"status: {status}",
        f"root: {root or '(none)'}",
        f"indexed_now: {indexed}",
        f"indexed_total: {connector_index_count(normalized) if status != 'unsupported' else 0}",
    ]
    if status == "unsupported":
        lines.append("Obsługiwane cache ingest: gmail, calendar, drive.")
    elif status == "auth_required":
        lines.append(f"Next: /connector auth {normalized}")
    else:
        lines.append(f"Next: /connector brief {normalized} <query>")
    return "\n".join(lines)


def connector_response(prompt: str) -> str:
    parts = prompt.strip().split(maxsplit=2)
    if not parts or parts[0].lower() in {"list", "status", "show"}:
        return connectors_response()
    action = parts[0].lower()
    if action in {"check", "status"}:
        if len(parts) < 2:
            return connectors_response()
        return connector_check_response(parts[1])
    if action in {"auth", "setup", "connect", "podłącz", "podlacz"}:
        if len(parts) < 2:
            return connectors_response()
        return connector_auth_response(parts[1])
    if action in {"search", "find"}:
        if len(parts) < 2:
            return connectors_response()
        name = parts[1]
        query = parts[2] if len(parts) >= 3 else ""
        return source_response(f"search {normalize_connector_name(name)} {query}".strip())
    if action in {"brief", "report", "summary"}:
        if len(parts) < 2:
            return connectors_response()
        name = parts[1]
        query = parts[2] if len(parts) >= 3 else ""
        return connector_brief_response(name, query)
    if action in {"ingest", "index", "cache"}:
        if len(parts) < 2:
            return connectors_response()
        return connector_ingest_response(parts[1])
    if action in {"sync", "oauth-sync"}:
        if len(parts) < 2:
            return connectors_response()
        name = parts[1]
        query = parts[2] if len(parts) >= 3 else ""
        return connector_sync_response(name, query=query)
    if action in {"draft", "drafts", "propose", "action"}:
        if action == "drafts" and len(parts) == 1:
            return integration_drafts_response()
        if len(parts) < 2:
            return "[Council] Użyj: /connector draft gmail|calendar|drive|github <intencja>."
        name = parts[1]
        intent = parts[2] if len(parts) >= 3 else ""
        if not intent.strip():
            return f"[Council] Connector draft `{normalize_connector_name(name)}` wymaga intencji.\nUżyj: /connector draft {normalize_connector_name(name)} <co przygotować>."
        action_item = create_integration_draft_action(name, intent, source="connector_command")
        if not action_item:
            return "[Council] Draft obsługuje: gmail, calendar, drive, github."
        return (
            "[Council] Integration draft utworzony L4.28.\n"
            f"id: {action_item['action_id']}\n"
            f"connector: {(action_item.get('payload') or {}).get('connector')}\n"
            f"risk: {action_item.get('risk')} - {(action_item.get('payload') or {}).get('risk_reason') or action_item.get('risk_reason')}\n"
            "external_write: false\n"
            f"missing: {', '.join((action_item.get('payload') or {}).get('missing_fields') or []) or 'none'}\n"
            f"Preview: /drafts show {action_item['action_id']}\n"
            f"Approve checkpoint: /approve {action_item['action_id']}\n"
            f"Deny: /deny {action_item['action_id']}"
        )
    name = parts[0]
    return connector_check_response(name)


def task_artifact_dir(task_id: str) -> Path:
    safe_id = re.sub(r"[^a-zA-Z0-9_.-]", "_", task_id.strip())
    return ARTIFACTS_DIR / safe_id


def safe_filename(value: str, fallback: str = "telegram-media") -> str:
    clean = re.sub(r"[^a-zA-Z0-9_.-]", "_", (value or "").strip())
    clean = clean.strip("._")
    return clean or fallback


def telegram_media_from_message(message: dict) -> dict | None:
    caption = str(message.get("caption") or "").strip()
    if message.get("voice"):
        item = message["voice"]
        return {
            "kind": "voice",
            "file_id": item.get("file_id", ""),
            "file_unique_id": item.get("file_unique_id", ""),
            "file_size": item.get("file_size", 0),
            "mime_type": item.get("mime_type", "audio/ogg"),
            "duration": item.get("duration", 0),
            "caption": caption,
            "file_name": "voice.ogg",
        }
    if message.get("audio"):
        item = message["audio"]
        return {
            "kind": "audio",
            "file_id": item.get("file_id", ""),
            "file_unique_id": item.get("file_unique_id", ""),
            "file_size": item.get("file_size", 0),
            "mime_type": item.get("mime_type", ""),
            "duration": item.get("duration", 0),
            "caption": caption,
            "file_name": item.get("file_name") or "audio",
        }
    if message.get("document"):
        item = message["document"]
        return {
            "kind": "document",
            "file_id": item.get("file_id", ""),
            "file_unique_id": item.get("file_unique_id", ""),
            "file_size": item.get("file_size", 0),
            "mime_type": item.get("mime_type", ""),
            "caption": caption,
            "file_name": item.get("file_name") or "document",
        }
    if message.get("photo"):
        photos = list(message.get("photo") or [])
        if not photos:
            return None
        item = max(photos, key=lambda row: int(row.get("file_size") or row.get("width", 0) * row.get("height", 0) or 0))
        return {
            "kind": "photo",
            "file_id": item.get("file_id", ""),
            "file_unique_id": item.get("file_unique_id", ""),
            "file_size": item.get("file_size", 0),
            "mime_type": "image/jpeg",
            "width": item.get("width", 0),
            "height": item.get("height", 0),
            "caption": caption,
            "file_name": "photo.jpg",
        }
    if message.get("video"):
        item = message["video"]
        return {
            "kind": "video",
            "file_id": item.get("file_id", ""),
            "file_unique_id": item.get("file_unique_id", ""),
            "file_size": item.get("file_size", 0),
            "mime_type": item.get("mime_type", "video/mp4"),
            "duration": item.get("duration", 0),
            "width": item.get("width", 0),
            "height": item.get("height", 0),
            "caption": caption,
            "file_name": item.get("file_name") or "video.mp4",
        }
    return None


def telegram_get_file_info(file_id: str) -> dict:
    if not file_id:
        return {"ok": False, "error": "missing_file_id"}
    return request_json(telegram_url("getFile", {"file_id": file_id}), timeout=20)


def telegram_file_download_url(file_path: str) -> str:
    token = cfg("TELEGRAM_BOT_TOKEN")
    return f"https://api.telegram.org/file/bot{token}/{file_path}"


def telegram_download_file(file_path: str, target: Path, timeout: int = 60) -> tuple[bool, str]:
    if not file_path:
        return False, "missing file_path"
    target.parent.mkdir(parents=True, exist_ok=True)
    req = Request(telegram_file_download_url(file_path), method="GET")
    try:
        with urlopen(req, timeout=timeout) as res:
            target.write_bytes(res.read())
        return True, str(target)
    except HTTPError as exc:
        return False, f"http_{exc.code}"
    except URLError as exc:
        return False, f"url_error: {exc.reason}"
    except TimeoutError:
        return False, "timeout"


def media_target_path(artifact_dir: Path, media: dict, file_path: str = "") -> Path:
    source_name = media.get("file_name") or Path(file_path).name or media.get("kind") or "telegram-media"
    name = safe_filename(str(source_name), "telegram-media")
    if "." not in name:
        suffix = Path(file_path).suffix
        if not suffix:
            suffix = mimetypes.guess_extension(str(media.get("mime_type") or "")) or ""
        name += suffix
    unique = safe_filename(str(media.get("file_unique_id") or media.get("file_id") or short_hash(name)), "file")
    return artifact_dir / "media" / f"{unique}-{name}"


def looks_like_text_media(path: Path, mime_type: str = "") -> bool:
    suffix = path.suffix.lower()
    mime = (mime_type or "").lower()
    return mime.startswith("text/") or suffix in {
        ".txt",
        ".md",
        ".markdown",
        ".csv",
        ".json",
        ".jsonl",
        ".log",
        ".html",
        ".htm",
        ".xml",
        ".yaml",
        ".yml",
    }


def read_text_media_preview(path: Path, limit: int | None = None) -> str:
    max_chars = limit if limit is not None else int_cfg("AI_COUNCIL_MEDIA_TEXT_MAX_CHARS", 6000)
    text = path.read_text(encoding="utf-8", errors="replace")
    if len(text) > max_chars:
        return text[:max_chars] + "\n...[truncated]..."
    return text


def xai_chat_text(data: dict) -> str:
    try:
        return str(data["choices"][0]["message"]["content"]).strip()
    except (KeyError, IndexError, TypeError):
        return xai_response_text(data) or redact_secrets(json.dumps(data, ensure_ascii=False))[:1200]


def grok_image_analysis(local_path: Path, caption: str = "", task_id: str = "") -> str:
    started = time.time()
    allowed, reason, reservation = reserve_operator_call("grok", task_id=task_id, detail="vision")
    if not allowed:
        return f"[Grok Vision] blocked: {reason}"
    key = cfg("XAI_API_KEY")
    if not key:
        finalize_operator_call(reservation, status="failed", duration_ms=0, estimated_usd=0.0, detail="missing XAI_API_KEY")
        return "[Grok Vision] error: missing XAI_API_KEY"
    if not local_path.exists():
        finalize_operator_call(reservation, status="failed", duration_ms=0, estimated_usd=0.0, detail="media file missing")
        return "[Grok Vision] error: media file missing"
    max_bytes = int_cfg("AI_COUNCIL_MEDIA_ANALYSIS_MAX_BYTES", 5_000_000)
    file_size = local_path.stat().st_size
    if file_size > max_bytes:
        finalize_operator_call(reservation, status="blocked", duration_ms=0, estimated_usd=0.0, detail="media too large")
        return f"[Grok Vision] blocked: media too large ({file_size} bytes > {max_bytes})."
    mime_type = mimetypes.guess_type(str(local_path))[0] or "image/jpeg"
    data_url = f"data:{mime_type};base64,{base64.b64encode(local_path.read_bytes()).decode('ascii')}"
    user_text = (
        "Przeanalizuj obraz/screenshot dla prywatnego AI Council Bartka. "
        "Odpowiedz po polsku. Zwróć: 1) co widać, 2) tekst/OCR jeśli jest, "
        "3) najważniejsze fakty, 4) następny najlepszy krok. "
        "Nie zmyślaj, jeśli czegoś nie widać."
    )
    if caption:
        user_text += f"\nKontekst od Bartka: {caption}"
    payload = {
        "model": cfg("AI_COUNCIL_GROK_VISION_MODEL", cfg("AI_COUNCIL_GROK_X_MODEL", "grok-4.3")),
        "messages": [
            {"role": "system", "content": "Jesteś operatorem vision/OCR w AI Council. Odpowiadasz zwięźle po polsku."},
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": user_text},
                    {"type": "image_url", "image_url": {"url": data_url}},
                ],
            },
        ],
        "stream": False,
    }
    data = request_json(
        "https://api.x.ai/v1/chat/completions",
        headers={"Authorization": f"Bearer {key}"},
        method="POST",
        payload=payload,
        timeout=180,
    )
    duration_ms = int((time.time() - started) * 1000)
    if data.get("ok") is False:
        detail = redact_secrets(str(data.get("body_preview", "")))[:500]
        finalize_operator_call(reservation, status="failed", duration_ms=duration_ms, detail=detail[:240])
        return f"[Grok Vision] error: {data.get('error')} {detail}".strip()
    text = xai_chat_text(data)
    finalize_operator_call(reservation, status="completed", duration_ms=duration_ms)
    return f"[Grok Vision]\n{text[: int_cfg('AI_COUNCIL_MEDIA_ANALYSIS_MAX_CHARS', 2400)]}"


def xai_stt_text(data: dict) -> str:
    for key in ("text", "transcript", "transcription"):
        value = data.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return xai_response_text(data)


def xai_stt_transcribe(local_path: Path, mime_type: str = "", task_id: str = "") -> dict:
    started = time.time()
    allowed, reason, reservation = reserve_operator_call("grok", task_id=task_id, detail="stt")
    if not allowed:
        return {"status": "transcription_blocked", "provider": "xai_stt", "text": "", "summary": reason}
    key = cfg("XAI_API_KEY")
    if not key:
        finalize_operator_call(reservation, status="failed", duration_ms=0, estimated_usd=0.0, detail="missing XAI_API_KEY")
        return {"status": "transcription_unavailable", "provider": "xai_stt", "text": "", "summary": "missing XAI_API_KEY"}
    if not local_path.exists():
        finalize_operator_call(reservation, status="failed", duration_ms=0, estimated_usd=0.0, detail="media file missing")
        return {"status": "transcription_failed", "provider": "xai_stt", "text": "", "summary": "media file missing"}
    max_bytes = int_cfg("AI_COUNCIL_STT_MAX_BYTES", 25_000_000)
    file_size = local_path.stat().st_size
    if file_size > max_bytes:
        finalize_operator_call(reservation, status="blocked", duration_ms=0, estimated_usd=0.0, detail="audio too large")
        return {
            "status": "transcription_blocked",
            "provider": "xai_stt",
            "text": "",
            "summary": f"audio too large ({file_size} bytes > {max_bytes})",
        }
    fields = []
    if bool_cfg("AI_COUNCIL_STT_FORMAT", True):
        fields.append(("format", "true"))
        language = cfg("AI_COUNCIL_STT_LANGUAGE", "pl")
        if language:
            fields.append(("language", language))
    keyterms = [item.strip() for item in cfg("AI_COUNCIL_STT_KEYTERMS", "Bartek,Codex,Claude,Grok,AI Council,OpenClaw,Poke").split(",") if item.strip()]
    for term in keyterms[:20]:
        fields.append(("keyterm", term))
    detected_mime = mime_type or mimetypes.guess_type(str(local_path))[0] or "application/octet-stream"
    data = request_multipart_json(
        cfg("AI_COUNCIL_STT_URL", "https://api.x.ai/v1/stt"),
        headers={"Authorization": f"Bearer {key}"},
        fields=fields,
        file_field="file",
        file_path=local_path,
        mime_type=detected_mime,
        timeout=int_cfg("AI_COUNCIL_STT_TIMEOUT", 180),
    )
    duration_ms = int((time.time() - started) * 1000)
    if data.get("ok") is False:
        detail = redact_secrets(str(data.get("body_preview") or data.get("reason") or data.get("error") or ""))[:500]
        finalize_operator_call(reservation, status="failed", duration_ms=duration_ms, detail=f"stt: {detail}"[:240])
        return {"status": "transcription_failed", "provider": "xai_stt", "text": "", "summary": detail or "xAI STT failed"}
    text = xai_stt_text(data)
    if not text:
        finalize_operator_call(reservation, status="failed", duration_ms=duration_ms, detail="stt empty response")
        return {"status": "transcription_failed", "provider": "xai_stt", "text": "", "summary": "empty STT response"}
    finalize_operator_call(reservation, status="completed", duration_ms=duration_ms)
    return {
        "status": "transcribed",
        "provider": "xai_stt",
        "text": text[: int_cfg("AI_COUNCIL_STT_MAX_CHARS", 8000)],
        "summary": compact_line(text, 700),
        "raw": data,
    }


def analyze_downloaded_media(metadata: dict) -> dict:
    local_path = Path(str(metadata.get("local_path") or ""))
    media = metadata.get("media") or {}
    kind = str(media.get("kind") or "")
    mime_type = str(media.get("mime_type") or "")
    if not local_path.exists():
        return {"status": "not_available", "reason": "local media file missing", "text": ""}
    if looks_like_text_media(local_path, mime_type):
        preview = read_text_media_preview(local_path)
        return {
            "status": "text_extracted",
            "provider": "local",
            "text": preview,
            "summary": compact_line(preview, 700),
        }
    if kind in {"photo"} or mime_type.startswith("image/"):
        analysis = grok_image_analysis(local_path, caption=str(media.get("caption") or ""), task_id=str(metadata.get("task_id") or ""))
        status = "vision_analyzed" if analysis.startswith("[Grok Vision]\n") else "vision_failed"
        return {
            "status": status,
            "provider": "xai_grok_vision",
            "text": analysis,
            "summary": compact_line(analysis, 700),
        }
    if kind in {"voice", "audio", "video"} or mime_type.startswith(("audio/", "video/")):
        return xai_stt_transcribe(local_path, mime_type=mime_type, task_id=str(metadata.get("task_id") or ""))
    return {
        "status": "unsupported_media_type",
        "provider": "none",
        "text": "",
        "summary": f"Captured media type is not analyzed yet: kind={kind} mime={mime_type}",
    }


def media_intent_text(media: dict, analysis: dict) -> str:
    if not bool_cfg("AI_COUNCIL_MEDIA_AUTO_ROUTE", True):
        return ""
    status = str(analysis.get("status") or "")
    if status not in {"transcribed", "text_extracted", "vision_analyzed"}:
        return ""
    text = str(analysis.get("text") or analysis.get("summary") or "").strip()
    if not text:
        return ""
    caption = str(media.get("caption") or "").strip()
    if caption and caption not in text:
        text = f"{caption}\n\n{text}"
    max_chars = int_cfg("AI_COUNCIL_MEDIA_INTENT_MAX_CHARS", 3000)
    return text[:max_chars].strip()


def run_media_derived_route(intent_text: str, chat_id: str, parent_task: dict, send_progress: bool = True) -> dict:
    clean_text = intent_text.strip()
    if not clean_text:
        return {"status": "skipped", "reason": "empty intent"}
    route = route_text(clean_text)
    route = {**route, "parent_task_id": parent_task.get("task_id", "")}
    derived = {
        "status": "routed",
        "command": route.get("command", ""),
        "operators": route.get("operators", []),
        "prompt_preview": compact_line(clean_text, 240),
    }
    if route_needs_task(route):
        idem_key = f"media-derived:{parent_task.get('task_id')}:{short_hash(clean_text)}"
        duplicate = find_recent_duplicate(idem_key)
        if duplicate:
            return {
                **derived,
                "status": "duplicate",
                "task_id": duplicate.get("task_id"),
                "response": duplicate_response(duplicate),
            }
        child = create_task(
            clean_text,
            source="telegram_media_intent",
            status="running",
            command=str(route.get("command") or ""),
            operators=route.get("operators", []),
            request_id=short_hash(f"{parent_task.get('task_id')}:{clean_text}"),
            idempotency_key=idem_key,
            chat_id_hash=short_hash(chat_id),
        )
        route = {**route, "task_id": child["task_id"]}
        if route_should_background(route):
            response = start_background_job(route, chat_id=chat_id, task_id=child["task_id"], send_progress=send_progress)
            status = "running_background"
            update_note = "media-derived background response sent"
        else:
            response = build_response(route, chat_id=chat_id)
            status = "waiting_approval" if route.get("command") in SIDE_EFFECT_COMMANDS else "completed"
            update_note = "media-derived response built"
        update_task_status(child["task_id"], status, update_note, parent_task_id=parent_task.get("task_id"))
        return {**derived, "status": status, "task_id": child["task_id"], "response": response}
    response = build_response(route, chat_id=chat_id)
    return {**derived, "status": "responded", "response": response}


def capture_telegram_media_message(message: dict, chat_id: str, update_id: int | None = None) -> tuple[str, dict | None]:
    media = telegram_media_from_message(message)
    if not media:
        return "[Council] Nie znalazłem obsługiwanego media w wiadomości.", None
    media_id = str(media.get("file_unique_id") or media.get("file_id") or update_id or "")
    caption = str(media.get("caption") or "").strip()
    prompt = caption or f"Telegram {media.get('kind')} capture"
    idem_key = f"telegram-media:{chat_id}:{message.get('message_id')}:{media_id}"
    duplicate = find_recent_duplicate(idem_key)
    if duplicate:
        return duplicate_response(duplicate), duplicate
    task = create_task(
        prompt,
        source="telegram_media",
        status="running",
        command="/capture",
        operators=["host"],
        request_id=short_hash(f"{chat_id}:{message.get('message_id')}:{media_id}"),
        idempotency_key=idem_key,
        chat_id_hash=short_hash(chat_id),
        update_id=update_id,
    )
    task_id = task["task_id"]
    artifact_dir = task_artifact_dir(task_id)
    artifact_dir.mkdir(parents=True, exist_ok=True)
    file_info = telegram_get_file_info(str(media.get("file_id") or ""))
    file_path = ""
    local_path = ""
    download_status = "not_downloaded"
    if file_info.get("ok"):
        file_path = str((file_info.get("result") or {}).get("file_path") or "")
        target = media_target_path(artifact_dir, media, file_path=file_path)
        downloaded, detail = telegram_download_file(file_path, target)
        download_status = "downloaded" if downloaded else f"failed: {detail}"
        local_path = str(target) if downloaded else ""
    else:
        download_status = f"getFile failed: {file_info.get('error') or file_info.get('description')}"

    metadata = {
        "task_id": task_id,
        "created_at": utc_now(),
        "telegram_message_id": message.get("message_id"),
        "media": media,
        "telegram_file_path": file_path,
        "local_path": local_path,
        "download_status": download_status,
    }
    analysis = analyze_downloaded_media(metadata) if local_path else {"status": "not_available", "reason": download_status, "text": ""}
    metadata["analysis"] = analysis
    derived = run_media_derived_route(media_intent_text(media, analysis), chat_id, task, send_progress=True)
    metadata["derived_intent"] = derived
    metadata_path = artifact_dir / "media.json"
    metadata_path.write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")
    facts = [
        f"type={media.get('kind')}",
        f"download_status={download_status}",
        f"local_path={local_path or 'not saved'}",
        f"analysis_status={analysis.get('status')}",
        f"derived_status={derived.get('status')}",
    ]
    derived_next = []
    if derived.get("task_id"):
        derived_next.append(f"Sprawdź pracę z media intent: /details {derived.get('task_id')}")
    elif derived.get("response"):
        derived_next.append("Wynik media intent jest w odpowiedzi capture.")
    result = {
        "decision": "Telegram media captured, analyzed and routed as AI Council intent.",
        "facts": facts,
        "dispute": "L3.4 używa tego samego routingu i approval co zwykły tekst; media nie dostaje większych uprawnień.",
        "next_actions": [
            f"Przejrzyj artefakt: /details {task_id}",
            *derived_next,
            "Dodaj opis/cel do tego taska albo poproś o kolejny krok na podstawie analizy.",
        ],
        "ask_user": "Napisz, co mam zrobić z tym plikiem albo wyślij kolejną wiadomość z kontekstem.",
        "raw_output": json.dumps(metadata, ensure_ascii=False, indent=2),
        "report": (
            f"# Telegram media capture: {task_id}\n\n"
            f"Kind: {media.get('kind')}\n\n"
            f"Caption: {caption or '(none)'}\n\n"
            f"Download: {download_status}\n\n"
            f"Local path: {local_path or '(not saved)'}\n\n"
            f"Analysis status: {analysis.get('status')}\n\n"
            f"## Analysis\n\n{analysis.get('text') or analysis.get('summary') or '(none)'}\n\n"
            f"## Derived intent\n\n{json.dumps(derived, ensure_ascii=False, indent=2)}\n\n"
            f"Metadata: {metadata_path}\n"
        ),
    }
    artifact = save_task_artifacts(task_id, {"command": "/capture", "operators": ["host"], "prompt": prompt}, result)
    update_task_status(
        task_id,
        "completed",
        "telegram media captured",
        report_path=artifact.get("report_path"),
        summary_path=artifact.get("summary_path"),
    )
    response = str(artifact.get("summary") or format_telegram_summary(result, task_id))
    if derived.get("response"):
        response += "\n\n[Media intent]\n" + str(derived["response"])
    return response, task


def payload_bool(payload: dict, key: str, default: bool = False) -> bool:
    if key not in payload:
        return default
    value = payload.get(key)
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def shortcut_text_from_payload(payload: dict) -> str:
    parts: list[str] = []
    for key in ("text", "prompt", "query", "transcript", "note"):
        value = str(payload.get(key) or "").strip()
        if value:
            parts.append(value)
    title = str(payload.get("title") or "").strip()
    url = str(payload.get("url") or payload.get("share_url") or "").strip()
    caption = str(payload.get("caption") or "").strip()
    if caption and caption not in parts:
        parts.append(caption)
    if title:
        parts.append(f"Tytuł: {title}")
    if url:
        parts.append(f"URL: {url}")
    return "\n\n".join(parts).strip()


def shortcut_media_kind(mime_type: str, filename: str, explicit_kind: str = "") -> str:
    kind = explicit_kind.strip().lower()
    if kind in {"photo", "image", "screenshot"}:
        return "photo"
    if kind in {"voice", "audio"}:
        return "voice" if kind == "voice" else "audio"
    if kind == "video":
        return "video"
    mime = mime_type.lower()
    if mime.startswith("image/"):
        return "photo"
    if mime.startswith("audio/"):
        return "audio"
    if mime.startswith("video/"):
        return "video"
    suffix = Path(filename).suffix.lower()
    if suffix in {".jpg", ".jpeg", ".png", ".gif", ".webp", ".heic"}:
        return "photo"
    if suffix in {".mp3", ".m4a", ".ogg", ".wav", ".aac"}:
        return "audio"
    if suffix in {".mp4", ".mov", ".webm"}:
        return "video"
    return "document"


def shortcut_media_from_payload(payload: dict) -> tuple[dict | None, bytes, str]:
    encoded = str(payload.get("media_base64") or payload.get("file_base64") or payload.get("attachment_base64") or "").strip()
    if not encoded:
        return None, b"", ""
    mime_from_data_url = ""
    if encoded.startswith("data:") and "," in encoded:
        header, encoded = encoded.split(",", 1)
        mime_from_data_url = header[5:].split(";", 1)[0]
    try:
        data = base64.b64decode(encoded, validate=True)
    except Exception:
        return None, b"", "invalid_base64"
    max_bytes = int_cfg("AI_COUNCIL_SHORTCUT_MAX_BODY_BYTES", 25_000_000)
    if len(data) > max_bytes:
        return None, b"", f"media_too_large:{len(data)}>{max_bytes}"
    filename = safe_filename(str(payload.get("filename") or payload.get("file_name") or "shortcut-media"), "shortcut-media")
    mime_type = str(payload.get("mime_type") or mime_from_data_url or mimetypes.guess_type(filename)[0] or "application/octet-stream")
    if "." not in filename:
        suffix = mimetypes.guess_extension(mime_type) or ""
        filename += suffix
    kind = shortcut_media_kind(mime_type, filename, str(payload.get("kind") or ""))
    caption = shortcut_text_from_payload(payload)
    media = {
        "kind": kind,
        "file_id": "",
        "file_unique_id": short_hash(f"{filename}:{len(data)}:{data[:128].hex()}"),
        "file_size": len(data),
        "mime_type": mime_type,
        "caption": caption,
        "file_name": filename,
    }
    return media, data, ""


def shortcut_send_to_telegram(payload: dict) -> bool:
    return payload_bool(payload, "send_telegram", bool_cfg("AI_COUNCIL_SHORTCUT_SEND_TELEGRAM", True))


def shortcut_chat_id(payload: dict, send_telegram: bool) -> str:
    if not send_telegram:
        return ""
    requested = str(payload.get("chat_id") or "").strip()
    allowed = cfg("TELEGRAM_ALLOWED_CHAT_ID")
    if requested and requested == allowed:
        return requested
    return allowed


def shortcut_target_id(payload: dict) -> str:
    for key in ("task_id", "action_id", "id", "target_id"):
        value = str(payload.get(key) or "").strip()
        if value:
            return value
    return ""


def shortcut_mutation_blocked_response(action: str, target: str) -> str:
    target_text = f" {target}" if target else ""
    return (
        "[Council] iPhone Shortcut action blocked.\n"
        f"DECYZJA: `{action}{target_text}` wymaga świadomego approval w Telegramie.\n"
        "FAKTY:\n"
        "1. Shortcut token daje dostęp do capture/read/status, nie do approve/deny/cancel.\n"
        "2. R3/R4 i mutacje lokalne zostają za approval path.\n"
        f"NEXT: wyślij w Telegramie `/{action}{target_text}` albo sprawdź /agent."
    )


def shortcut_action_route(payload: dict) -> dict | None:
    raw = str(payload.get("action") or payload.get("shortcut_action") or "").strip()
    prompt_text = shortcut_text_from_payload(payload)
    if not raw:
        mode = str(payload.get("mode") or "").strip().lower()
        if not prompt_text and mode in {"agent", "inbox", "shortcuts", "shortcut", "iphone"}:
            raw = mode
    if not raw:
        return None
    lower = raw.lower()
    target = shortcut_target_id(payload)
    if lower in {"cancel", "approve", "deny"}:
        return {
            "command": f"/{lower}",
            "operators": ["host"],
            "prompt": target,
            "mode": "shortcut_blocked_mutation",
            "blocked_action": lower,
            "target_id": target,
        }
    if lower in {"agent", "inbox"}:
        return {"command": "/agent", "operators": ["host"], "prompt": prompt_text, "mode": "agent"}
    if lower in {"shortcuts", "shortcut", "iphone"}:
        return {"command": "/shortcuts", "operators": ["host"], "prompt": "", "mode": "shortcuts"}
    if lower in {"health", "selftest", "goal"}:
        return route_text(f"/{lower}")
    if lower in {"status", "progress", "details", "facts", "next"}:
        return route_text(f"/{lower} {target}".strip())
    if raw.startswith(("/", "@")):
        return route_text(f"{raw} {prompt_text}".strip())
    return None


def shortcut_should_research_url(payload: dict) -> bool:
    url = str(payload.get("url") or payload.get("share_url") or "").strip()
    if not url:
        return False
    mode = str(payload.get("mode") or payload.get("kind") or payload.get("shortcut_type") or "").strip().lower()
    if mode in {"ask", "chat", "note"}:
        return False
    if mode in {"url", "share", "research", "brief", "link"}:
        return True
    return payload_bool(payload, "research", bool_cfg("AI_COUNCIL_SHORTCUT_URL_RESEARCH_DEFAULT", True))


def shortcut_route_for_text(payload: dict, text: str) -> dict:
    command = str(payload.get("command") or payload.get("route") or "").strip()
    if command.startswith(("/", "@")):
        return route_text(f"{command} {text}".strip())
    if shortcut_should_research_url(payload):
        return route_text(f"/recipe run research_brief {text}".strip())
    return route_text(text)


def persist_shortcut_text_artifact(text: str, route: dict, response: str, remote_addr: str, chat_id: str, idem_key: str) -> str:
    task = create_task(
        text,
        source="iphone_shortcut_text",
        status="completed",
        command=str(route.get("command") or ""),
        operators=route.get("operators", []),
        request_id=short_hash(f"{remote_addr}:{idem_key}:responded"),
        idempotency_key=idem_key,
        chat_id_hash=short_hash(chat_id),
    )
    result = {
        "decision": "iPhone Shortcut text handled and stored as Agent Inbox context.",
        "facts": extract_fact_lines(response, limit=3) or [compact_line(text, 180)],
        "dispute": "Text shortcut is read-only unless routed through approval-protected commands.",
        "next_actions": ["/agent", f"/details {task['task_id']}"],
        "ask_user": "Użyj /agent, żeby wybrać następny krok.",
        "raw_output": response,
        "report": f"# iPhone Shortcut text {task['task_id']}\n\nInput:\n{text}\n\nRoute: {route.get('command')}\n\nResponse:\n{response}",
    }
    artifact = save_task_artifacts(task["task_id"], route, result)
    update_task_status(
        task["task_id"],
        "completed",
        "iphone shortcut text persisted",
        report_path=artifact.get("report_path"),
        summary_path=artifact.get("summary_path"),
    )
    return task["task_id"]


def capture_shortcut_media_payload(payload: dict, remote_addr: str = "") -> dict:
    send_telegram = shortcut_send_to_telegram(payload)
    chat_id = shortcut_chat_id(payload, send_telegram)
    media, data, media_error = shortcut_media_from_payload(payload)
    if media_error:
        return {"ok": False, "status": "failed", "error": media_error}
    if not media:
        return {"ok": False, "status": "failed", "error": "missing_media"}
    prompt = shortcut_text_from_payload(payload) or f"iPhone Shortcut {media.get('kind')} capture"
    idem_key = str(payload.get("idempotency_key") or f"shortcut-media:{media.get('file_unique_id')}:{short_hash(prompt)}")
    duplicate = find_recent_duplicate(idem_key)
    if duplicate:
        response = duplicate_response(duplicate)
        if send_telegram and chat_id:
            telegram_send_message_with_markup(chat_id, response, response_reply_markup(response))
        return {"ok": True, "status": "duplicate", "task_id": duplicate.get("task_id"), "response": response}
    task = create_task(
        prompt,
        source="iphone_shortcut_media",
        status="running",
        command="/capture",
        operators=["host"],
        request_id=short_hash(f"{remote_addr}:{idem_key}"),
        idempotency_key=idem_key,
        chat_id_hash=short_hash(chat_id),
    )
    task_id = task["task_id"]
    artifact_dir = task_artifact_dir(task_id)
    target = media_target_path(artifact_dir, media, file_path=str(media.get("file_name") or "shortcut-media"))
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(data)
    metadata = {
        "task_id": task_id,
        "created_at": utc_now(),
        "source": "iphone_shortcut",
        "remote_addr_hash": short_hash(remote_addr),
        "media": media,
        "local_path": str(target),
        "download_status": "provided_by_shortcut",
    }
    analysis = analyze_downloaded_media(metadata)
    metadata["analysis"] = analysis
    derived = run_media_derived_route(media_intent_text(media, analysis), chat_id, task, send_progress=send_telegram)
    metadata["derived_intent"] = derived
    metadata_path = artifact_dir / "media.json"
    metadata_path.write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")
    facts = [
        f"type={media.get('kind')}",
        f"download_status=provided_by_shortcut",
        f"local_path={target}",
        f"analysis_status={analysis.get('status')}",
        f"derived_status={derived.get('status')}",
    ]
    next_actions = []
    if derived.get("task_id"):
        next_actions.append(f"Sprawdź pracę z iPhone Shortcut media intent: /details {derived.get('task_id')}")
    else:
        next_actions.append(f"Przejrzyj capture: /details {task_id}")
    result = {
        "decision": "iPhone Shortcut media captured, analyzed and routed as AI Council intent.",
        "facts": facts,
        "dispute": "Shortcut ingress is private/token-gated; no external writes were executed.",
        "next_actions": next_actions,
        "ask_user": "Sprawdź wynik i zdecyduj, czy kontynuować child task.",
        "raw_output": (
            f"# iPhone Shortcut media capture {task_id}\n\n"
            f"Media: {json.dumps(media, ensure_ascii=False, indent=2)}\n\n"
            f"Local path: {target}\n\n"
            f"Analysis status: {analysis.get('status')}\n\n"
            f"## Analysis\n\n{analysis.get('text') or analysis.get('summary') or '(none)'}\n\n"
            f"## Derived intent\n\n{json.dumps(derived, ensure_ascii=False, indent=2)}\n\n"
            f"Metadata: {metadata_path}\n"
        ),
        "report": (
            f"# iPhone Shortcut media capture {task_id}\n\n"
            f"Local path: {target}\n\n"
            f"Analysis: {analysis.get('status')}\n\n"
            f"Derived: {json.dumps(derived, ensure_ascii=False, indent=2)}\n"
        ),
    }
    artifact = save_task_artifacts(task_id, {"command": "/capture", "operators": ["host"], "prompt": prompt}, result)
    update_task_status(
        task_id,
        "completed",
        "iphone shortcut media captured",
        report_path=artifact.get("report_path"),
        summary_path=artifact.get("summary_path"),
    )
    response = str(artifact.get("summary") or format_telegram_summary(result, task_id))
    if derived.get("response"):
        response += "\n\n[Shortcut media intent]\n" + str(derived["response"])
    if send_telegram and chat_id:
        telegram_send_message_with_markup(chat_id, response, response_reply_markup(response))
    audit(
        {
            "command": "shortcut_media",
            "operators": ["host"],
            "status": "completed",
            "task_id": task_id,
            "remote_addr_hash": short_hash(remote_addr),
            "output_preview": response[:300],
        }
    )
    return {"ok": True, "status": "completed", "task_id": task_id, "response": response, "derived": derived}


def process_shortcut_payload(payload: dict, remote_addr: str = "") -> dict:
    ensure_council_dirs()
    send_telegram = shortcut_send_to_telegram(payload)
    chat_id = shortcut_chat_id(payload, send_telegram)
    action_route = shortcut_action_route(payload)
    if action_route:
        if action_route.get("mode") == "shortcut_blocked_mutation":
            response = shortcut_mutation_blocked_response(
                str(action_route.get("blocked_action") or "").strip("/"),
                str(action_route.get("target_id") or ""),
            )
            status = "blocked"
        else:
            response = build_response(action_route, chat_id=chat_id)
            status = "responded"
        if send_telegram and chat_id:
            telegram_send_message_with_markup(chat_id, response, response_reply_markup(response))
        audit(
            {
                "command": action_route.get("command"),
                "operators": action_route.get("operators", []),
                "status": status,
                "source": "iphone_shortcut_action",
                "remote_addr_hash": short_hash(remote_addr),
                "output_preview": str(response)[:300],
            }
        )
        return {
            "ok": True,
            "status": status,
            "task_id": shortcut_target_id(payload)
            if action_route.get("mode") != "shortcut_blocked_mutation" and str(action_route.get("command")) in {"/status", "/progress", "/details", "/facts", "/next"}
            else "",
            "command": action_route.get("command"),
            "operators": action_route.get("operators", []),
            "response": response,
        }
    if any(payload.get(key) for key in ("media_base64", "file_base64", "attachment_base64")):
        return capture_shortcut_media_payload(payload, remote_addr=remote_addr)
    text = shortcut_text_from_payload(payload)
    if not text:
        return {"ok": False, "status": "failed", "error": "missing_text_or_media"}
    route = shortcut_route_for_text(payload, text)
    route_key = short_hash(str(route.get("command") or route.get("mode") or "text"))
    idem_key = str(payload.get("idempotency_key") or f"shortcut-text:{route_key}:{short_hash(text)}")
    duplicate = find_recent_duplicate(idem_key)
    task = None
    background_started = False
    if duplicate:
        response = duplicate_response(duplicate)
        status = "duplicate"
        task_id = str(duplicate.get("task_id") or "")
    elif route_needs_task(route):
        task_prompt = str(route.get("prompt") or text)
        task = create_task(
            task_prompt,
            source="iphone_shortcut",
            status="running",
            command=str(route.get("command") or ""),
            operators=route.get("operators", []),
            request_id=short_hash(f"{remote_addr}:{idem_key}"),
            idempotency_key=idem_key,
            chat_id_hash=short_hash(chat_id),
        )
        task_id = task["task_id"]
        route = {**route, "task_id": task_id}
        if route_should_background(route):
            background_started = True
            response = start_background_job(route, chat_id=chat_id, task_id=task_id, send_progress=send_telegram)
            status = "running_background"
        else:
            response = build_response(route, chat_id=chat_id)
            status = "waiting_approval" if route.get("command") in SIDE_EFFECT_COMMANDS else "completed"
        update_task_status(task_id, status, "shortcut response built")
    else:
        response = build_response(route, chat_id=chat_id)
        status = "responded"
        task_id = persist_shortcut_text_artifact(text, route, response, remote_addr, chat_id, idem_key)
    if send_telegram and chat_id:
        telegram_send_message_with_markup(chat_id, response, response_reply_markup(response))
    audit(
        {
            "command": route.get("command"),
            "operators": route.get("operators", []),
            "status": status,
            "task_id": task_id,
            "source": "iphone_shortcut",
            "remote_addr_hash": short_hash(remote_addr),
            "background_started": background_started,
            "output_preview": str(response)[:300],
        }
    )
    return {
        "ok": True,
        "status": status,
        "task_id": task_id,
        "command": route.get("command"),
        "operators": route.get("operators", []),
        "response": response,
    }


def shortcut_authorized(headers: dict) -> tuple[bool, str]:
    token = cfg("AI_COUNCIL_SHORTCUT_TOKEN")
    if not token:
        return False, "shortcut_token_not_configured"
    supplied = str(headers.get("X-AI-Council-Token") or headers.get("x-ai-council-token") or "").strip()
    auth = str(headers.get("Authorization") or headers.get("authorization") or "").strip()
    if auth.lower().startswith("bearer "):
        supplied = auth.split(" ", 1)[1].strip()
    if hmac.compare_digest(token, supplied):
        return True, "authorized"
    return False, "invalid_token"


def shortcut_json_response(handler: BaseHTTPRequestHandler, status: int, payload: dict) -> None:
    body = json.dumps(sanitize_for_audit(payload), ensure_ascii=False).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Content-Length", str(len(body)))
    handler.end_headers()
    handler.wfile.write(body)


class ShortcutRequestHandler(BaseHTTPRequestHandler):
    def log_message(self, format: str, *args) -> None:
        print(f"shortcut_http {compact_line(format % args, 180)}")

    def do_GET(self) -> None:
        path = urlparse(self.path).path
        if path in {"/health", "/"}:
            shortcut_json_response(self, 200, {"ok": True, "service": "ai-council-shortcuts", "status": "ready"})
            return
        shortcut_json_response(self, 404, {"ok": False, "error": "not_found"})

    def do_POST(self) -> None:
        path = urlparse(self.path).path
        if path not in {"/shortcut", "/shortcut/task", "/ask"}:
            shortcut_json_response(self, 404, {"ok": False, "error": "not_found"})
            return
        authorized, reason = shortcut_authorized(dict(self.headers.items()))
        if not authorized:
            shortcut_json_response(self, 401, {"ok": False, "error": reason})
            return
        max_body = int_cfg("AI_COUNCIL_SHORTCUT_MAX_BODY_BYTES", 25_000_000)
        length = int(self.headers.get("Content-Length") or "0")
        if length <= 0:
            shortcut_json_response(self, 400, {"ok": False, "error": "empty_body"})
            return
        if length > max_body:
            shortcut_json_response(self, 413, {"ok": False, "error": "body_too_large"})
            return
        try:
            payload = json.loads(self.rfile.read(length).decode("utf-8", errors="replace"))
        except json.JSONDecodeError:
            shortcut_json_response(self, 400, {"ok": False, "error": "invalid_json"})
            return
        if not isinstance(payload, dict):
            shortcut_json_response(self, 400, {"ok": False, "error": "json_object_required"})
            return
        result = process_shortcut_payload(payload, remote_addr=str(self.client_address[0] if self.client_address else ""))
        shortcut_json_response(self, 200 if result.get("ok") else 400, result)


def serve_shortcuts(host: str = "", port: int = 0) -> int:
    token = cfg("AI_COUNCIL_SHORTCUT_TOKEN")
    if not token:
        print("shortcut_server=failed missing AI_COUNCIL_SHORTCUT_TOKEN")
        return 1
    bind_host = host or cfg("AI_COUNCIL_SHORTCUT_HOST", "127.0.0.1")
    bind_port = port or int_cfg("AI_COUNCIL_SHORTCUT_PORT", 8788)
    ensure_council_dirs()
    server = ThreadingHTTPServer((bind_host, bind_port), ShortcutRequestHandler)
    print(f"shortcut_server_started host={bind_host} port={bind_port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("shortcut_server_stopped")
        return 0
    finally:
        server.server_close()
    return 0


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


def followup_action_for_task(task_id: str) -> dict | None:
    latest = latest_by_id(ACTIONS_FILE, "action_id", limit=80)
    for action in latest:
        payload = action.get("payload") or {}
        if action.get("type") == "followup_proposal" and payload.get("source_task_id") == task_id:
            return action
    return None


def followup_seed(next_actions: list[str], facts: list[str], task_id: str) -> str:
    skip_prefixes = (
        "przejrzyj wynik",
        "przejrzyj pełny",
        "przejrzyj pelny",
        "pokaż recipe",
        "pokaz recipe",
        "/details",
        "/facts",
        "/recipe show",
    )
    for action in next_actions:
        clean = compact_line(str(action), 240)
        if clean and not clean.lower().startswith(skip_prefixes):
            return clean
    if facts:
        return f"kontynuuj na podstawie faktu: {compact_line(str(facts[0]), 180)}"
    return f"kontynuuj wynik task {task_id}"


def risk_rank(level: str) -> int:
    try:
        return RISK_LEVELS.index((level or "").strip().upper())
    except ValueError:
        return RISK_LEVELS.index("R2")


def stricter_risk(*items: tuple[str, str]) -> tuple[str, str]:
    clean = [(level, reason) for level, reason in items if level]
    if not clean:
        return "R2", "unknown follow-up risk"
    return max(clean, key=lambda item: risk_rank(item[0]))


def followup_route_risk(command: str, prompt: str, intent: str = "") -> tuple[str, str]:
    command = (command or "").strip()
    text = " ".join(part for part in [command, prompt or "", intent or ""] if part)
    if command not in FOLLOWUP_EXECUTABLE_COMMANDS:
        return "R2", f"{command or '(empty)'} is not follow-up executable"
    if command in SIDE_EFFECT_COMMANDS or command in {"/execute", "/verify", "/rollback", "/approve", "/deny"}:
        return "R4", f"{command} is a side-effect/execution command"
    if command == "/connector":
        action = (prompt or "").split(maxsplit=1)[0].lower() if prompt else ""
        if action and action not in RECIPE_CONNECTOR_READ_ACTIONS:
            return "R3", f"/connector action `{action}` is not read-only follow-up allowed"
    if command == "/source":
        action = (prompt or "").split(maxsplit=1)[0].lower() if prompt else ""
        if action and action not in RECIPE_SOURCE_READ_ACTIONS:
            return "R3", f"/source action `{action}` is not read-only follow-up allowed"
    return risk_level_for_text(text)


def build_followup_payload(task_id: str, route: dict, normalized: dict, result: dict) -> dict:
    explicit = result.get("followup") if isinstance(result.get("followup"), dict) else {}
    if explicit:
        command = str(explicit.get("command") or "/plan-action")
        prompt = str(explicit.get("prompt") or explicit.get("intent") or "")
        intent = str(explicit.get("intent") or prompt)
        declared_risk = normalize_risk(str(explicit.get("risk") or ""), intent or prompt)
        computed_risk = followup_route_risk(command, prompt, intent)
        risk, reason = stricter_risk(declared_risk, computed_risk)
        if risk_rank(computed_risk[0]) > risk_rank(declared_risk[0]):
            reason = f"computed route risk overrides declared risk: {computed_risk[1]}"
        elif explicit.get("reason"):
            reason = str(explicit.get("reason"))
    else:
        seed = followup_seed(normalized.get("next_actions") or [], normalized.get("facts") or [], task_id)
        command = "/plan-action"
        prompt = f"Kontynuuj wynik task {task_id}: {seed}"
        intent = prompt
        risk, reason = followup_route_risk(command, prompt, intent)
    try:
        parent_depth = int(route.get("followup_depth") or route.get("chain_depth") or 0)
    except (TypeError, ValueError):
        parent_depth = 0
    chain_depth = parent_depth + 1
    chain_id = str(route.get("followup_chain_id") or route.get("chain_id") or f"followup:{task_id}")
    return {
        "source_task_id": task_id,
        "source_command": route.get("command", ""),
        "intent": compact_line(intent, 500),
        "recommended_command": command,
        "recommended_prompt": prompt,
        "recommended_route": {
            "command": command,
            "operators": operators_for_command(command),
            "prompt": prompt,
            "mode": "followup",
            "intent": "followup_runner",
            "followup_chain_id": chain_id,
            "followup_depth": chain_depth,
        },
        "followup_chain_id": chain_id,
        "followup_depth": chain_depth,
        "risk": risk,
        "risk_reason": reason,
    }


def maybe_create_followup_action(task_id: str, route: dict, normalized: dict, result: dict) -> dict | None:
    if not bool_cfg("AI_COUNCIL_FOLLOWUP_RUNNER", True):
        return None
    if route.get("command") != "/recipe":
        return None
    if str(result.get("status") or "") in {"blocked", "failed"}:
        return None
    existing = followup_action_for_task(task_id)
    if existing:
        return existing
    payload = build_followup_payload(task_id, route, normalized, result)
    max_depth = int_cfg("AI_COUNCIL_FOLLOWUP_MAX_DEPTH", 3)
    if int(payload.get("followup_depth") or 0) > max_depth:
        return None
    command = str(payload.get("recommended_command") or "")
    if command not in FOLLOWUP_EXECUTABLE_COMMANDS:
        payload["blocked_reason"] = f"command `{command}` is not follow-up executable"
        risk = "R2"
    else:
        risk = str(payload.get("risk") or "R0")
    action = create_action(
        f"Follow-up for {task_id}: {payload.get('intent')}",
        action_type="followup_proposal",
        risk=risk,
        payload=payload,
    )
    return action


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
    followup_action = maybe_create_followup_action(task_id, route, normalized, result)
    if followup_action:
        followup_line = f"Follow-up ready: /approve {followup_action['action_id']} albo /deny {followup_action['action_id']}"
        if followup_line not in normalized["next_actions"]:
            normalized["next_actions"] = [followup_line, *normalized["next_actions"]][:8]
        normalized["followup_action_id"] = followup_action["action_id"]
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
        "followup_action_id": normalized.get("followup_action_id", ""),
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
    save_project_memory_from_artifact(index)
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
    usage_id: str = "",
    task_id: str = "",
    status: str = "completed",
    duration_ms: int = 0,
    estimated_usd: float | None = None,
    detail: str = "",
) -> dict:
    operator = operator_key(operator)
    event = {
        "usage_id": usage_id or f"use-{datetime.now().strftime('%Y%m%d-%H%M%S')}-{short_hash(f'{operator}:{task_id}:{time.time()}')[:6]}",
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


def collapse_usage_events(rows: list[dict]) -> list[dict]:
    latest: dict[str, dict] = {}
    no_id: list[dict] = []
    for row in rows:
        usage_id = str(row.get("usage_id") or "").strip()
        if not usage_id:
            no_id.append(row)
            continue
        latest[usage_id] = row
    return [*no_id, *latest.values()]


def usage_today(operator: str | None = None, *, collapsed: bool = True) -> list[dict]:
    rows = [row for row in read_jsonl(COSTS_FILE) if row.get("day") == today_utc()]
    if operator:
        operator = operator_key(operator)
        rows = [row for row in rows if row.get("operator") == operator]
    return collapse_usage_events(rows) if collapsed else rows


def operator_block_detail(detail: str, reason: str) -> str:
    detail = compact_line(detail, 120)
    reason = compact_line(reason, 220)
    if detail and reason:
        return f"{detail}: {reason}"
    return detail or reason


def reserve_operator_call(operator: str, *, task_id: str = "", detail: str = "") -> tuple[bool, str, dict | None]:
    operator = operator_key(operator)
    try:
        with BlockingFileLock(COST_LOCK_FILE, timeout=float_cfg("AI_COUNCIL_COST_LOCK_TIMEOUT", 5.0)):
            allowed, reason = operator_call_allowed(operator)
            if not allowed:
                record_operator_usage(
                    operator,
                    task_id=task_id,
                    status="blocked",
                    duration_ms=0,
                    estimated_usd=0.0,
                    detail=operator_block_detail(detail, reason),
                )
                return False, reason, None
            event = record_operator_usage(
                operator,
                task_id=task_id,
                status="reserved",
                duration_ms=0,
                estimated_usd=estimated_operator_cost(operator),
                detail=detail or "reserved",
            )
            return True, "", event
    except TimeoutError as exc:
        reason = str(exc)
        record_operator_usage(
            operator,
            task_id=task_id,
            status="blocked",
            duration_ms=0,
            estimated_usd=0.0,
            detail=operator_block_detail(detail, reason),
        )
        return False, reason, None


def finalize_operator_call(
    reservation: dict | None,
    *,
    status: str,
    duration_ms: int = 0,
    estimated_usd: float | None = None,
    detail: str = "",
) -> dict | None:
    if not reservation:
        return None
    usage_id = str(reservation.get("usage_id") or "")
    if not usage_id:
        return None
    final_estimate = reservation.get("estimated_usd") if estimated_usd is None else estimated_usd
    try:
        final_estimate = float(final_estimate or 0.0)
    except (TypeError, ValueError):
        final_estimate = estimated_operator_cost(str(reservation.get("operator") or ""))
    return record_operator_usage(
        str(reservation.get("operator") or ""),
        usage_id=usage_id,
        task_id=str(reservation.get("task_id") or ""),
        status=status,
        duration_ms=duration_ms,
        estimated_usd=final_estimate,
        detail=detail,
    )


def default_control_state() -> dict:
    return {
        "global_kill_switch": False,
        "model_calls_paused": False,
        "scheduled_recipes_paused": False,
        "proactive_scan_paused": False,
        "daily_total_call_limit": 0,
        "daily_total_estimated_usd_limit": 0.0,
        "per_operator": {},
        "reason": "",
        "updated_at": "",
        "updated_by": "system",
    }


def _control_int(value, field: str) -> int:
    try:
        parsed = int(value or 0)
    except (TypeError, ValueError):
        raise ValueError(f"{field} must be an integer") from None
    if parsed < 0:
        raise ValueError(f"{field} must be >= 0")
    return parsed


def _control_float(value, field: str) -> float:
    try:
        parsed = float(value or 0.0)
    except (TypeError, ValueError):
        raise ValueError(f"{field} must be a number") from None
    if parsed < 0:
        raise ValueError(f"{field} must be >= 0")
    return parsed


def validate_control_state(state: dict) -> None:
    for key in ["global_kill_switch", "model_calls_paused", "scheduled_recipes_paused", "proactive_scan_paused"]:
        if key in state and not isinstance(state.get(key), bool):
            raise ValueError(f"{key} must be boolean")
    _control_int(state.get("daily_total_call_limit", 0), "daily_total_call_limit")
    _control_float(state.get("daily_total_estimated_usd_limit", 0.0), "daily_total_estimated_usd_limit")
    per_operator = state.get("per_operator", {})
    if per_operator and not isinstance(per_operator, dict):
        raise ValueError("per_operator must be an object")
    for name, limits in (per_operator or {}).items():
        if not isinstance(name, str) or not isinstance(limits, dict):
            raise ValueError("per_operator entries must be objects")
        _control_int(limits.get("daily_call_limit", 0), f"per_operator.{name}.daily_call_limit")
        _control_float(limits.get("daily_estimated_usd_limit", 0.0), f"per_operator.{name}.daily_estimated_usd_limit")


def load_control_state() -> dict:
    base = default_control_state()
    if not CONTROL_FILE.exists():
        return base
    try:
        raw = json.loads(CONTROL_FILE.read_text(encoding="utf-8", errors="replace") or "{}")
        if not isinstance(raw, dict):
            raise ValueError("control file must contain an object")
        state = {**base, **raw}
        validate_control_state(state)
        return state
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        return {
            **base,
            "global_kill_switch": True,
            "reason": f"invalid control file: {exc}",
            "control_file_error": str(exc),
        }


def save_control_state(state: dict) -> dict:
    merged = {**default_control_state(), **state, "updated_at": utc_now()}
    validate_control_state(merged)
    CONTROL_FILE.parent.mkdir(parents=True, exist_ok=True)
    tmp = CONTROL_FILE.with_name(f"{CONTROL_FILE.name}.tmp-{os.getpid()}-{threading.get_ident()}")
    tmp.write_text(json.dumps(merged, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(tmp, CONTROL_FILE)
    return merged


def control_paused_reason(area: str) -> str:
    state = load_control_state()
    reason = str(state.get("reason") or "no reason")
    if state.get("global_kill_switch"):
        return f"global kill switch active: {reason}"
    if area == "model" and state.get("model_calls_paused"):
        return f"model calls paused: {reason}"
    if area == "scheduler" and state.get("scheduled_recipes_paused"):
        return f"scheduled recipes paused: {reason}"
    if area == "proactive" and state.get("proactive_scan_paused"):
        return f"proactive scan paused: {reason}"
    return ""


def nonblocked_usage(rows: list[dict]) -> list[dict]:
    return [row for row in rows if row.get("status") != "blocked"]


def operator_control_limits(operator: str, state: dict) -> tuple[int, float]:
    operator = operator_key(operator)
    per_operator = state.get("per_operator") or {}
    limits = per_operator.get(operator) if isinstance(per_operator, dict) else {}
    if not isinstance(limits, dict):
        limits = {}
    call_limit = _control_int(limits.get("daily_call_limit", 0), f"per_operator.{operator}.daily_call_limit")
    budget = _control_float(limits.get("daily_estimated_usd_limit", 0.0), f"per_operator.{operator}.daily_estimated_usd_limit")
    return call_limit, budget


def operator_env_call_limits(operator: str) -> list[tuple[str, int]]:
    operator = operator_key(operator)
    env_key = f"AI_COUNCIL_{operator.upper().replace('-', '_')}_DAILY_CALL_LIMIT"
    default_limit = 50 if operator == "claude-flow" else 0
    limits = [(env_key, int_cfg(env_key, default_limit))]
    if operator == "grok":
        limits.append(("GROK_DAILY_CALL_LIMIT", int_cfg("GROK_DAILY_CALL_LIMIT", 0)))
    seen = set()
    result = []
    for name, value in limits:
        if name not in seen and value > 0:
            result.append((name, value))
            seen.add(name)
    return result


def operator_env_budget_limits(operator: str) -> list[tuple[str, float]]:
    operator = operator_key(operator)
    env_key = f"AI_COUNCIL_{operator.upper().replace('-', '_')}_DAILY_BUDGET_USD"
    limits = [(env_key, float_cfg(env_key, 0.0))]
    if operator == "grok":
        limits.append(("GROK_DAILY_BUDGET_USD", float_cfg("GROK_DAILY_BUDGET_USD", 0.0)))
    return [(name, value) for name, value in limits if value > 0]


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


def route_source_summary(limit: int = 200) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in read_jsonl(AUDIT_LOG)[-limit:]:
        source = str(row.get("route_source") or "")
        if not source:
            continue
        counts[source] = counts.get(source, 0) + 1
    return counts


def audit_event_age(row: dict | None) -> str:
    if not row:
        return "none"
    parsed = parse_utc(str(row.get("timestamp") or ""))
    if not parsed:
        return "unknown"
    seconds = max(0, int((datetime.now(timezone.utc) - parsed).total_seconds()))
    if seconds < 90:
        return f"{seconds}s"
    minutes = seconds // 60
    if minutes < 90:
        return f"{minutes}m"
    hours = minutes // 60
    return f"{hours}h"


def latest_telegram_audit(limit: int = 500) -> dict:
    rows = read_jsonl(AUDIT_LOG)[-limit:]
    inbound = [row for row in rows if row.get("update_id") is not None and row.get("command") != "startup"]
    sent = [row for row in inbound if row.get("status") in {"responded", "callback", "facts", "details", "status"}]
    failed = [row for row in inbound if row.get("status") == "send_failed"]
    dry = [row for row in inbound if row.get("status") == "dry_responded" or row.get("dry_send") is True]
    last = inbound[-1] if inbound else None
    return {
        "last": last,
        "last_age": audit_event_age(last),
        "inbound_count": len(inbound),
        "sent_count": len(sent),
        "failed_count": len(failed),
        "dry_count": len(dry),
    }


def front_runtime_snapshot() -> dict:
    usage = operator_usage_summary()
    grok = usage.get("grok", {"calls": 0, "blocked": 0, "estimated_usd": 0.0})
    recent_errors = error_rows(days=1)
    control = load_control_state()
    latest = latest_telegram_audit()
    listener_pid = ""
    try:
        listener_pid = TELEGRAM_LISTENER_LOCK.read_text(encoding="utf-8", errors="replace").strip()
    except OSError:
        listener_pid = ""
    return {
        "latest": latest,
        "offset": read_offset(),
        "listener_pid": listener_pid or "unknown",
        "llm_router": llm_router_enabled() and bool(cfg("XAI_API_KEY")),
        "poke_chat_llm": poke_chat_llm_configured(),
        "models_paused": bool(control.get("model_calls_paused")),
        "kill": bool(control.get("global_kill_switch")),
        "grok_calls": int(grok.get("calls") or 0),
        "grok_blocked": int(grok.get("blocked") or 0),
        "grok_estimated_usd": float(grok.get("estimated_usd") or 0.0),
        "errors_24h": len(recent_errors),
        "send_failed_24h": sum(1 for row in recent_errors if row.get("context") == "telegram_response_send"),
    }


def front_reliability_response(prompt: str = "") -> str:
    snap = front_runtime_snapshot()
    latest = snap["latest"]
    last = latest.get("last") or {}
    last_update = (
        f"{last.get('update_id')} {last.get('command')} {last.get('status')} age={latest.get('last_age')}"
        if last
        else "brak w ostatnim oknie audytu"
    )
    decision = "Front działa lokalnie i nie powinien odpalać Groka dla krótkich wiadomości."
    if snap["kill"] or snap["models_paused"]:
        decision = "Front działa w trybie lokalnym, ale modele są zatrzymane przez /control."
    if latest.get("failed_count"):
        decision = "Front odbiera wiadomości, ale były błędy wysyłki Telegram."
    lines = [
        "[Council] Front Reliability L4.24",
        f"DECYZJA: {decision}",
        "FAKTY:",
        f"1. last_telegram_update: {last_update}",
        f"2. telegram_offset: {snap['offset'] if snap['offset'] is not None else 'none'} | listener_pid: {snap['listener_pid']}",
        f"3. outbound: sent={latest.get('sent_count')} failed={latest.get('failed_count')} dry={latest.get('dry_count')}",
        f"4. models: kill={snap['kill']} paused={snap['models_paused']} llm_router={'on' if snap['llm_router'] else 'off'} poke_chat_llm={'gated' if snap['poke_chat_llm'] else 'off'}",
        f"5. grok_today: calls={snap['grok_calls']} blocked={snap['grok_blocked']} est=${snap['grok_estimated_usd']:.4f}",
        f"6. errors_24h: {snap['errors_24h']} | telegram_send_failed_errors: {snap['send_failed_24h']}",
        "NEXT: jeśli właśnie napisałeś i `last_telegram_update` się nie zmienia, problem jest przed botem: zły chat/bot albo Telegram nie dostarczył update. Jeśli update rośnie, a failed=0, odpowiedź powinna wrócić.",
        "DO CIEBIE: wyślij `/selftest` w Telegramie; jeśli audit nie pokaże nowego update, piszesz nie do tego bota albo Telegram nie dostarcza wiadomości.",
    ]
    if prompt.strip():
        lines.append(f"Prompt: {compact_line(prompt, 180)}")
    return "\n".join(lines)


def operator_call_allowed(operator: str) -> tuple[bool, str]:
    operator = operator_key(operator)
    paused = control_paused_reason("model")
    if paused:
        return False, paused
    state = load_control_state()
    today_rows = usage_today()
    active_rows = nonblocked_usage(today_rows)
    total_call_limit = _control_int(state.get("daily_total_call_limit", 0), "daily_total_call_limit")
    if total_call_limit and len(active_rows) >= total_call_limit:
        return False, f"Global daily call limit reached: {len(active_rows)}/{total_call_limit}"
    total_budget = _control_float(state.get("daily_total_estimated_usd_limit", 0.0), "daily_total_estimated_usd_limit")
    if total_budget:
        used = sum(float(row.get("estimated_usd") or 0.0) for row in active_rows)
        next_cost = estimated_operator_cost(operator)
        if used + next_cost > total_budget:
            return False, f"Global estimated budget reached: {used:.4f}+{next_cost:.4f}>{total_budget:.4f} USD"

    operator_rows = nonblocked_usage(usage_today(operator))
    operator_calls = len(operator_rows)
    control_call_limit, control_budget = operator_control_limits(operator, state)
    call_limits = [("control", control_call_limit) if control_call_limit > 0 else None, *operator_env_call_limits(operator)]
    for source in [item for item in call_limits if item]:
        label, limit = source
        if operator_calls >= limit:
            return False, f"{operator} daily call limit reached via {label}: {operator_calls}/{limit}"
    budget_limits = [("control", control_budget) if control_budget > 0 else None, *operator_env_budget_limits(operator)]
    for source in [item for item in budget_limits if item]:
        label, budget = source
        used = sum(float(row.get("estimated_usd") or 0.0) for row in operator_rows)
        next_cost = estimated_operator_cost(operator)
        if used + next_cost > budget:
            return False, f"{operator} estimated budget reached via {label}: {used:.4f}+{next_cost:.4f}>{budget:.4f} USD"
    return True, ""


def cost_response() -> str:
    summary = operator_usage_summary()
    rows = usage_today()
    total_calls = sum(1 for row in rows if row.get("status") != "blocked")
    total_blocked = sum(1 for row in rows if row.get("status") == "blocked")
    total_time = sum(int(row.get("duration_ms") or 0) for row in rows)
    total_est = sum(float(row.get("estimated_usd") or 0.0) for row in rows)
    control = load_control_state()
    lines = [
        "[Council] Cost/usage today (UTC).",
        f"total_calls: {total_calls} | blocked: {total_blocked} | time: {total_time}ms | est: ${total_est:.4f}",
        f"control: {'KILL' if control.get('global_kill_switch') else 'on'} | models_paused={control.get('model_calls_paused')} | scheduler_paused={control.get('scheduled_recipes_paused')} | total_call_limit={control.get('daily_total_call_limit')} | total_budget=${float(control.get('daily_total_estimated_usd_limit') or 0.0):.4f}",
    ]
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
        "L4.18 guard blokuje modele po kill switch, pauzie i limitach dziennych."
    )
    return "\n".join(lines)


def control_status_lines(state: dict | None = None) -> list[str]:
    state = state or load_control_state()
    per_operator = state.get("per_operator") if isinstance(state.get("per_operator"), dict) else {}
    lines = [
        "[Council] Control L4.18",
        f"global_kill_switch: {bool(state.get('global_kill_switch'))}",
        f"model_calls_paused: {bool(state.get('model_calls_paused'))}",
        f"scheduled_recipes_paused: {bool(state.get('scheduled_recipes_paused'))}",
        f"proactive_scan_paused: {bool(state.get('proactive_scan_paused'))}",
        f"daily_total_call_limit: {int(state.get('daily_total_call_limit') or 0)}",
        f"daily_total_estimated_usd_limit: ${float(state.get('daily_total_estimated_usd_limit') or 0.0):.4f}",
        f"reason: {state.get('reason') or '-'}",
        f"updated_at: {state.get('updated_at') or '-'}",
    ]
    if state.get("control_file_error"):
        lines.append(f"control_file_error: {state.get('control_file_error')}")
    if per_operator:
        lines.append("per_operator:")
        for name in sorted(per_operator):
            limits = per_operator.get(name) if isinstance(per_operator.get(name), dict) else {}
            lines.append(
                f"- {name}: calls={int(limits.get('daily_call_limit') or 0)} budget=${float(limits.get('daily_estimated_usd_limit') or 0.0):.4f}"
            )
    lines.append("Użyj: /control pause|resume [models|scheduler|proactive|all], /control kill, /control set total-calls <n>, /control set total-budget <usd>, /control set operator <name> calls|budget <n>.")
    return lines


def control_response(prompt: str, chat_id: str = "") -> str:
    parts = prompt.strip().split()
    if not parts or parts[0].lower() in {"status", "show"}:
        return "\n".join(control_status_lines())
    allowed_chat = cfg("TELEGRAM_ALLOWED_CHAT_ID")
    if chat_id and allowed_chat and str(chat_id) != str(allowed_chat):
        return "[Council] Control denied: unauthorized chat."
    action = parts[0].lower()
    state = load_control_state()
    reason = " ".join(parts[2:]).strip() if len(parts) > 2 else ""
    if action == "kill":
        reason = " ".join(parts[1:]).strip() or "manual kill switch"
        state.update({"global_kill_switch": True, "reason": reason, "updated_by": "telegram"})
        saved = save_control_state(state)
        return "\n".join(control_status_lines(saved))
    if action in {"unkill", "resume"}:
        target = parts[1].lower() if len(parts) >= 2 else "all"
        if target in {"all", "everything"}:
            state.update(
                {
                    "global_kill_switch": False,
                    "model_calls_paused": False,
                    "scheduled_recipes_paused": False,
                    "proactive_scan_paused": False,
                }
            )
        elif target in {"models", "model"}:
            state["model_calls_paused"] = False
        elif target in {"scheduler", "recipes", "loops"}:
            state["scheduled_recipes_paused"] = False
        elif target in {"proactive", "nudges"}:
            state["proactive_scan_paused"] = False
        else:
            return "[Council] Control: nieznany target. Użyj models, scheduler, proactive albo all."
        state.update({"reason": reason or f"resumed {target}", "updated_by": "telegram"})
        saved = save_control_state(state)
        return "\n".join(control_status_lines(saved))
    if action == "pause":
        target = parts[1].lower() if len(parts) >= 2 else "all"
        if target in {"all", "everything"}:
            state.update({"model_calls_paused": True, "scheduled_recipes_paused": True, "proactive_scan_paused": True})
        elif target in {"models", "model"}:
            state["model_calls_paused"] = True
        elif target in {"scheduler", "recipes", "loops"}:
            state["scheduled_recipes_paused"] = True
        elif target in {"proactive", "nudges"}:
            state["proactive_scan_paused"] = True
        else:
            return "[Council] Control: nieznany target. Użyj models, scheduler, proactive albo all."
        state.update({"reason": reason or f"paused {target}", "updated_by": "telegram"})
        saved = save_control_state(state)
        return "\n".join(control_status_lines(saved))
    if action == "reset":
        saved = save_control_state({**default_control_state(), "reason": "control reset", "updated_by": "telegram"})
        return "\n".join(control_status_lines(saved))
    if action == "set":
        if len(parts) < 3:
            return "[Council] Control set: użyj total-calls <n>, total-budget <usd>, operator <name> calls|budget <n>."
        target = parts[1].lower()
        try:
            if target == "total-calls":
                state["daily_total_call_limit"] = _control_int(parts[2], "daily_total_call_limit")
            elif target == "total-budget":
                state["daily_total_estimated_usd_limit"] = _control_float(parts[2], "daily_total_estimated_usd_limit")
            elif target == "operator" and len(parts) >= 5:
                name = operator_key(parts[2])
                field = parts[3].lower()
                per_operator = state.setdefault("per_operator", {})
                limits = per_operator.setdefault(name, {})
                if field in {"calls", "call-limit", "daily-calls"}:
                    limits["daily_call_limit"] = _control_int(parts[4], f"per_operator.{name}.daily_call_limit")
                elif field in {"budget", "usd", "daily-budget"}:
                    limits["daily_estimated_usd_limit"] = _control_float(parts[4], f"per_operator.{name}.daily_estimated_usd_limit")
                else:
                    return "[Council] Control operator: użyj calls albo budget."
            else:
                return "[Council] Control set: użyj total-calls, total-budget albo operator <name> calls|budget."
        except ValueError as exc:
            return f"[Council] Control set zablokowany: {exc}"
        state.update({"reason": "limits updated", "updated_by": "telegram"})
        saved = save_control_state(state)
        return "\n".join(control_status_lines(saved))
    return "[Council] Control: /control status, pause, resume, kill, unkill, reset, set."


def default_recipes() -> dict[str, dict]:
    return {
        "research_brief": {
            "name": "research_brief",
            "description": "Grok X research brief z faktami, ryzykami i next actions.",
            "enabled": True,
            "trigger": {"type": "manual"},
            "risk": "R0",
            "approval_policy": "auto",
            "planner_selectable": True,
            "intent_keywords": ["research", "zbadaj", "poszukaj", "x.com", "twitter", "poke", "sprawdź internet", "sprawdz internet"],
            "integrations": ["grok", "x_search", "artifacts"],
            "steps": [{"command": "@xresearch", "prompt": "{input}"}],
        },
        "gmail_context_brief": {
            "name": "gmail_context_brief",
            "description": "Synchronizuje Gmail read-only i robi source-backed brief.",
            "enabled": True,
            "trigger": {"type": "manual"},
            "risk": "R0",
            "approval_policy": "auto",
            "planner_selectable": True,
            "source_connectors": ["gmail"],
            "intent_keywords": ["gmail", "mail", "email", "poczta", "raport z gmail", "sprawdź maile", "sprawdz maile"],
            "integrations": ["gmail", "connector_cache", "artifacts"],
            "steps": [
                {"command": "/connector", "prompt": "sync gmail {input}"},
                {"command": "/connector", "prompt": "brief gmail {input}"},
            ],
        },
        "calendar_context_brief": {
            "name": "calendar_context_brief",
            "description": "Synchronizuje Calendar read-only i robi source-backed brief.",
            "enabled": True,
            "trigger": {"type": "manual"},
            "risk": "R0",
            "approval_policy": "auto",
            "planner_selectable": True,
            "source_connectors": ["calendar"],
            "intent_keywords": ["calendar", "kalendarz", "spotkania", "meetingi", "plan dnia", "dzisiejszy dzień", "dzisiejszy dzien"],
            "integrations": ["calendar", "connector_cache", "artifacts"],
            "steps": [
                {"command": "/connector", "prompt": "sync calendar {input}"},
                {"command": "/connector", "prompt": "brief calendar {input}"},
            ],
        },
        "drive_context_brief": {
            "name": "drive_context_brief",
            "description": "Synchronizuje Drive/Docs read-only i robi source-backed brief.",
            "enabled": True,
            "trigger": {"type": "manual"},
            "risk": "R0",
            "approval_policy": "auto",
            "planner_selectable": True,
            "source_connectors": ["drive"],
            "intent_keywords": ["drive", "docs", "google docs", "dokument", "dokumenty", "plik", "pliki"],
            "integrations": ["drive", "docs", "connector_cache", "artifacts"],
            "steps": [
                {"command": "/connector", "prompt": "sync drive {input}"},
                {"command": "/connector", "prompt": "brief drive {input}"},
            ],
        },
        "daily_system_digest": {
            "name": "daily_system_digest",
            "description": "Krótki digest health, kosztów, kolejki i artefaktów.",
            "enabled": True,
            "trigger": {"type": "schedule", "cron": "30 8 * * *"},
            "risk": "R0",
            "approval_policy": "auto",
            "planner_selectable": True,
            "intent_keywords": ["digest", "podsumowanie systemu", "status systemu", "raport systemu"],
            "steps": [
                {"command": "/health", "prompt": ""},
                {"command": "/cost", "prompt": ""},
                {"command": "/queue", "prompt": ""},
                {"command": "/artifacts", "prompt": ""},
                {"command": "/errors", "prompt": "recent 10"},
                {"command": "/improvements", "prompt": "open"},
            ],
        },
        "stuck_tasks_monitor": {
            "name": "stuck_tasks_monitor",
            "description": "Sprawdza stuck/running tasks i kolejkę.",
            "enabled": False,
            "trigger": {"type": "schedule", "interval_seconds": 1800},
            "risk": "R0",
            "approval_policy": "auto",
            "planner_selectable": True,
            "intent_keywords": ["stuck", "zawieszone", "wiszące", "running tasks", "kolejka"],
            "steps": [
                {"command": "/health", "prompt": ""},
                {"command": "/queue", "prompt": ""},
            ],
        },
        "cost_usage_monitor": {
            "name": "cost_usage_monitor",
            "description": "Monitoruje dzienne użycie i estymowany koszt.",
            "enabled": False,
            "trigger": {"type": "schedule", "interval_seconds": 3600},
            "risk": "R0",
            "approval_policy": "auto",
            "planner_selectable": True,
            "intent_keywords": ["koszt", "koszty", "usage", "budżet", "budzet"],
            "steps": [{"command": "/cost", "prompt": ""}],
        },
        "error_audit_twice_daily": {
            "name": "error_audit_twice_daily",
            "description": "Dwa razy dziennie audytuje folder errors i proponuje naprawy kodu.",
            "enabled": True,
            "trigger": {"type": "schedule", "cron": "0 9,21 * * *"},
            "risk": "R0",
            "approval_policy": "auto",
            "capture_improvement": True,
            "planner_selectable": True,
            "intent_keywords": ["błędy", "bledy", "errors", "audyt błędów", "audyt bledow", "debug", "wysypuje", "napraw błędy", "napraw bledy"],
            "integrations": ["errors", "claude-flow", "improvements"],
            "improvement_policy": {"enabled": True, "source": "error_audit_loop", "priority": "P1"},
            "steps": [
                {"command": "/errors", "prompt": "recent 20"},
                {
                    "command": "/flow",
                    "prompt": (
                        "Zrób audyt błędów AI Council na bazie kontekstu poniżej. "
                        "Oceń prawdopodobną przyczynę, wskaż konkretne pliki/funkcje do poprawy, "
                        "zaproponuj minimalny patch i testy. Nie wykonuj zmian zewnętrznych.\n\n"
                        "ERROR_CONTEXT:\n{previous}"
                    ),
                },
            ],
        },
        "feature_evolution_loop": {
            "name": "feature_evolution_loop",
            "description": "Codzienny research Poke/Hermes/OpenClaw i plan kolejnej funkcji do wdrożenia.",
            "enabled": True,
            "trigger": {"type": "schedule", "cron": "15 10 * * *"},
            "risk": "R0",
            "approval_policy": "auto",
            "capture_improvement": True,
            "planner_selectable": True,
            "intent_keywords": ["ulepsz", "rozwijaj", "nowe funkcje", "poke parity", "top 1", "co wdrażać", "co wdrożyć", "co wdrozyc", "następne wdrożenie", "nastepne wdrozenie"],
            "integrations": ["grok", "x_search", "claude-flow", "improvements"],
            "improvement_policy": {"enabled": True, "source": "feature_evolution_loop", "priority": "P2"},
            "steps": [
                {
                    "command": "@xresearch",
                    "prompt": (
                        "Najnowsze funkcje Poke/@interaction, agentów messaging-first, recipes, "
                        "proactive alerts, iPhone/Apple Messages integrations, Hermes/OpenClaw-style execution. "
                        "Wyciągnij fakty, wzorce UX, braki i jedną najważniejszą funkcję do skopiowania lub ulepszenia."
                    ),
                },
                {
                    "command": "/flow",
                    "prompt": (
                        "Na podstawie researchu poniżej oraz repo D:\\ai-council przygotuj plan jednej kolejnej "
                        "implementacji, która najbardziej zbliża system Bartka do Poke-like OpenClaw Agent OS. "
                        "Wynik: decyzja, scope, pliki, testy, ryzyka, acceptance criteria.\n\n"
                        "RESEARCH:\n{previous}"
                    ),
                },
            ],
        },
        "project_next_action": {
            "name": "project_next_action",
            "description": "Claude Flow wybiera najbliższy bezpieczny krok dla projektu.",
            "enabled": True,
            "trigger": {"type": "manual"},
            "risk": "R0",
            "approval_policy": "auto",
            "planner_selectable": True,
            "intent_keywords": ["plan", "wdrożenie", "wdrozenie", "co dalej", "następny krok", "nastepny krok", "projekt"],
            "integrations": ["claude-flow", "artifacts"],
            "steps": [{"command": "/flow", "prompt": "Wybierz najbliższy bezpieczny krok dla: {input}"}],
        },
    }


def ensure_default_recipes() -> None:
    ensure_council_dirs()
    for name, recipe in default_recipes().items():
        path = RECIPES_DIR / f"{name}.json"
        if path.exists():
            try:
                current = json.loads(path.read_text(encoding="utf-8", errors="replace"))
            except json.JSONDecodeError:
                current = {}
            merged = {**recipe, **current}
            if "trigger" not in current and "trigger" in recipe:
                merged["trigger"] = recipe["trigger"]
            if merged != current:
                path.write_text(json.dumps(merged, ensure_ascii=False, indent=2), encoding="utf-8")
        else:
            path.write_text(json.dumps(recipe, ensure_ascii=False, indent=2), encoding="utf-8")


def recipe_path(name: str) -> Path:
    safe_name = re.sub(r"[^a-zA-Z0-9_.-]", "_", name.strip())
    return RECIPES_DIR / f"{safe_name}.json"


def load_recipe(name: str) -> dict | None:
    ensure_default_recipes()
    path = recipe_path(name)
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8", errors="replace"))
    except json.JSONDecodeError:
        return None


def save_recipe(recipe: dict) -> bool:
    name = str(recipe.get("name") or "").strip()
    if not name:
        return False
    ensure_council_dirs()
    recipe_path(name).write_text(json.dumps(recipe, ensure_ascii=False, indent=2), encoding="utf-8")
    return True


def set_recipe_enabled(name: str, enabled: bool) -> str:
    recipe = load_recipe(name)
    if not recipe:
        return f"[Council] Nie znalazłem recipe `{name}`."
    recipe["enabled"] = enabled
    save_recipe(recipe)
    state = "enabled" if enabled else "disabled"
    return f"[Council] Recipe `{name}` {state}."


def list_recipes() -> list[dict]:
    ensure_default_recipes()
    recipes = []
    for path in sorted(RECIPES_DIR.glob("*.json")):
        try:
            recipes.append(json.loads(path.read_text(encoding="utf-8", errors="replace")))
        except json.JSONDecodeError:
            recipes.append({"name": path.stem, "description": "invalid json", "enabled": False})
    return recipes


def recipe_last_run(name: str) -> dict | None:
    rows = [row for row in read_jsonl(RECIPE_RUNS_FILE) if row.get("recipe") == name]
    return rows[-1] if rows else None


def recipe_step_estimated_cost(step: dict) -> float:
    command = str(step.get("command") or "")
    if command in {"@research", "@grok", "@xresearch", "/xresearch", "/poke-research"}:
        return estimated_operator_cost("grok")
    if command in {"/flow", "@claude-flow"}:
        return estimated_operator_cost("claude-flow")
    if command == "@claude":
        return estimated_operator_cost("claude")
    if command in {"@codex", "codex_default"}:
        return estimated_operator_cost("codex")
    if command == "/council":
        return estimated_operator_cost("grok") + estimated_operator_cost("claude") + estimated_operator_cost("codex")
    return 0.0


def recipe_estimated_cost(name: str) -> float:
    recipe = load_recipe(name)
    if not recipe:
        return 0.0
    return sum(recipe_step_estimated_cost(step) for step in recipe.get("steps") or [])


def connector_tokens_for_recipe(recipe: dict) -> list[str]:
    tokens: list[str] = []
    for connector in recipe.get("source_connectors") or []:
        normalized = normalize_connector_name(str(connector))
        if normalized == "gmail":
            tokens.extend(["gmail", "mail", "email", "poczta", "maile"])
        elif normalized == "calendar":
            tokens.extend(["calendar", "kalendarz", "spotkania", "meetingi"])
        elif normalized == "drive":
            tokens.extend(["drive", "docs", "google docs", "dokument", "dokumenty", "plik", "pliki"])
        else:
            tokens.append(normalized)
    return tokens


def recipe_match_score(recipe: dict, prompt: str) -> tuple[int, list[str]]:
    lower = normalize_intent_text(prompt)
    if recipe.get("enabled") is False or not recipe.get("planner_selectable"):
        return 0, []
    name = str(recipe.get("name") or "")
    score = 0
    matches: list[str] = []
    if name and name.replace("_", " ") in lower:
        score += 12
        matches.append(name)
    for keyword in recipe.get("intent_keywords") or []:
        clean = normalize_intent_text(str(keyword))
        if clean and clean in lower:
            score += 6 if " " in clean else 4
            matches.append(clean)
    for token in connector_tokens_for_recipe(recipe):
        if token and token in lower:
            score += 8
            matches.append(token)
    return score, list(dict.fromkeys(matches))


def recipe_candidates_for_intent(prompt: str, limit: int = 5) -> list[dict]:
    candidates: list[dict] = []
    for recipe in list_recipes():
        score, matches = recipe_match_score(recipe, prompt)
        if score <= 0:
            continue
        candidates.append(
            {
                "name": recipe.get("name", ""),
                "description": recipe.get("description", ""),
                "score": score,
                "matches": matches,
                "recipe": recipe,
            }
        )
    candidates.sort(key=lambda item: (-int(item.get("score") or 0), str(item.get("name") or "")))
    return candidates[:limit]


def select_live_recipe(prompt: str) -> dict | None:
    candidates = recipe_candidates_for_intent(prompt, limit=1)
    if not candidates:
        return None
    candidate = candidates[0]
    if int(candidate.get("score") or 0) < 4:
        return None
    matches = ", ".join(candidate.get("matches") or [])
    return {
        "name": candidate.get("name", ""),
        "score": candidate.get("score", 0),
        "reason": f"matched: {matches}" if matches else "matched recipe metadata",
        "description": candidate.get("description", ""),
    }


def recipe_suggest_response(prompt: str) -> str:
    clean = prompt.strip()
    if not clean:
        return "[Council] Recipe suggest: podaj intencję, np. /recipe suggest przygotuj raport z gmail o Poke."
    candidates = recipe_candidates_for_intent(clean, limit=5)
    if not candidates:
        return "[Council] Nie znalazłem pasującej live recipe. Fallback: Action Planner użyje /flow albo /council."
    lines = [f"[Council] Recipe suggestions for: {compact_line(clean, 160)}"]
    for index, item in enumerate(candidates, start=1):
        matches = ", ".join(item.get("matches") or [])
        lines.append(
            f"{index}. {item.get('name')} score={item.get('score')} matches={compact_line(matches, 100)} - {compact_line(str(item.get('description') or ''), 120)}"
        )
    top = candidates[0]
    lines.append(f"NEXT: /recipe run {top.get('name')} {compact_line(clean, 120)}")
    return "\n".join(lines)


def recipes_response() -> str:
    recipes = list_recipes()
    if not recipes:
        return "[Council] Brak recipes."
    lines = ["[Council] Recipes:"]
    for recipe in recipes:
        enabled = "on" if recipe.get("enabled", True) else "off"
        lines.append(f"- {recipe.get('name')} [{enabled}] {compact_line(recipe.get('description', ''), 110)}")
    lines.append("Uruchom: /recipe run <name> <input>")
    lines.append("Zarządzaj: /recipe show|enable|disable <name>")
    return "\n".join(lines)


def loops_response() -> str:
    loop_names = ["error_audit_twice_daily", "feature_evolution_loop"]
    open_count = len(open_improvements(limit=50))
    recent_errors = error_rows(days=1)
    control = load_control_state()
    lines = [
        "[Council] Autonomous loops L4.18",
        f"errors_24h: {len(recent_errors)} | open_improvements: {open_count}",
        f"control: kill={control.get('global_kill_switch')} scheduler_paused={control.get('scheduled_recipes_paused')} proactive_paused={control.get('proactive_scan_paused')}",
    ]
    for name in loop_names:
        recipe = load_recipe(name)
        if not recipe:
            lines.append(f"- {name}: missing")
            continue
        trigger = recipe.get("trigger") or {}
        last = recipe_last_run(name)
        last_text = "never" if not last else f"{last.get('updated_at')} {last.get('status')} {last.get('task_id')}"
        lines.append(
            f"- {name} [{'on' if recipe.get('enabled', True) else 'off'}] trigger={json.dumps(trigger, ensure_ascii=False)} last={last_text}"
        )
    lines.append("Manualnie: /recipe run error_audit_twice_daily albo /recipe run feature_evolution_loop")
    lines.append("Backlog: /improvements | Next: /improve next | Control: /control")
    return "\n".join(lines)


def format_recipe(recipe: dict) -> str:
    steps = recipe.get("steps") or []
    trigger = recipe.get("trigger") or {"type": "manual"}
    lines = [
        f"[Council] Recipe {recipe.get('name')}",
        f"enabled: {recipe.get('enabled', True)}",
        f"trigger: {json.dumps(trigger, ensure_ascii=False)}",
        f"risk: {recipe.get('risk', 'R0')}",
        f"approval: {recipe.get('approval_policy', 'auto')}",
        f"description: {recipe.get('description', '')}",
        "steps:",
    ]
    for index, step in enumerate(steps, start=1):
        lines.append(f"{index}. {step.get('command')} {compact_line(step.get('prompt', ''), 120)}")
    return "\n".join(lines)


def recipe_response(prompt: str) -> str:
    parts = prompt.strip().split(maxsplit=2)
    if not parts:
        return recipes_response()
    action = parts[0].lower()
    if action in {"suggest", "match"}:
        return recipe_suggest_response(" ".join(parts[1:]) if len(parts) >= 2 else "")
    if action == "show" and len(parts) >= 2:
        recipe = load_recipe(parts[1])
        return format_recipe(recipe) if recipe else f"[Council] Nie znalazłem recipe `{parts[1]}`."
    if action in {"enable", "disable"} and len(parts) >= 2:
        return set_recipe_enabled(parts[1], action == "enable")
    if action == "run":
        return "[Council] Recipe run działa w tle. Użyj: /recipe run <name> <input>."
    return "[Council] Recipe: /recipes, /recipe show|enable|disable <name>, /recipe run <name> <input>."


def cron_field_matches(token: str, value: int, *, day_of_week: bool = False) -> bool:
    token = token.strip()
    if token == "*":
        return True
    values = []
    for part in token.split(","):
        part = part.strip()
        if not part:
            continue
        try:
            candidate = int(part)
        except ValueError:
            return False
        if day_of_week and candidate == 7:
            candidate = 0
        values.append(candidate)
    compare = value
    if day_of_week and compare == 7:
        compare = 0
    return compare in values


def recipe_due_window(recipe: dict, now: datetime | None = None) -> tuple[bool, str]:
    trigger = recipe.get("trigger") or {}
    if trigger.get("type") != "schedule":
        return False, ""
    current = now or datetime.now().astimezone()
    interval = int(trigger.get("interval_seconds") or 0)
    if interval > 0:
        bucket = int(current.timestamp() // interval)
        return True, f"interval:{interval}:{bucket}"
    cron = str(trigger.get("cron") or "").strip()
    fields = cron.split()
    if len(fields) != 5:
        return False, ""
    minute, hour, day, month, dow = fields
    cron_dow = current.isoweekday() % 7
    due = (
        cron_field_matches(minute, current.minute)
        and cron_field_matches(hour, current.hour)
        and cron_field_matches(day, current.day)
        and cron_field_matches(month, current.month)
        and cron_field_matches(dow, cron_dow, day_of_week=True)
    )
    if not due:
        return False, ""
    return True, f"cron:{cron}:{current.strftime('%Y%m%d%H%M')}"


def recipe_run_exists(name: str, window_key: str) -> bool:
    return any(
        row.get("recipe") == name and row.get("window_key") == window_key
        for row in read_jsonl(RECIPE_RUNS_FILE)
    )


def append_recipe_run(name: str, window_key: str, task_id: str, status: str) -> None:
    append_jsonl(
        RECIPE_RUNS_FILE,
        {
            "recipe": name,
            "window_key": window_key,
            "task_id": task_id,
            "status": status,
            "updated_at": utc_now(),
        },
    )


def run_due_recipes(send: bool = False, now: datetime | None = None) -> int:
    if not bool_cfg("AI_COUNCIL_RECIPE_SCHEDULER", True):
        return 0
    if control_paused_reason("scheduler"):
        return 0
    chat_id = cfg("TELEGRAM_ALLOWED_CHAT_ID")
    started = 0
    for recipe in list_recipes():
        name = str(recipe.get("name") or "").strip()
        if not name or recipe.get("enabled") is False:
            continue
        due, window_key = recipe_due_window(recipe, now=now)
        if not due or not window_key or recipe_run_exists(name, window_key):
            continue
        trigger = recipe.get("trigger") or {}
        recipe_input = str(trigger.get("input") or "")
        prompt = f"run {name} {recipe_input}".strip()
        route = {
            "command": "/recipe",
            "operators": ["host"],
            "prompt": prompt,
            "mode": "recipe_scheduler",
        }
        task = create_task(
            prompt,
            source="recipe_scheduler",
            status="running",
            command="/recipe",
            operators=["host"],
            idempotency_key=f"recipe:{name}:{window_key}",
            chat_id_hash=short_hash(chat_id),
        )
        append_recipe_run(name, window_key, task["task_id"], "started")
        response = start_background_job(route, chat_id=chat_id, task_id=task["task_id"], send_progress=send)
        if send and chat_id:
            telegram_send_message_with_markup(chat_id, response, response_reply_markup(response))
        else:
            print(response)
        started += 1
    return started


def render_recipe_step_prompt(template: str, recipe_input: str, previous_output: str = "") -> str:
    previous_limit = int_cfg("AI_COUNCIL_RECIPE_PREVIOUS_MAX_CHARS", 6000)
    return (
        (template or "")
        .replace("{input}", recipe_input.strip())
        .replace("{previous}", previous_output.strip()[:previous_limit])
    )


def recipe_step_is_allowed(step: dict) -> tuple[bool, str]:
    command = str(step.get("command") or "").strip()
    prompt = str(step.get("prompt") or "").strip()
    if command not in READONLY_RECIPE_COMMANDS:
        return False, f"{command or '(empty)'} is not allowed in recipes"
    action = prompt.split(maxsplit=1)[0].lower() if prompt else ""
    if command == "/connector" and action and action not in RECIPE_CONNECTOR_READ_ACTIONS:
        return False, f"/connector action `{action}` is not read-only recipe allowed"
    if command == "/source" and action and action not in RECIPE_SOURCE_READ_ACTIONS:
        return False, f"/source action `{action}` is not read-only recipe allowed"
    if command == "/memory" and action and action not in RECIPE_MEMORY_READ_ACTIONS:
        return False, f"/memory action `{action}` is not read-only recipe allowed"
    if command == "/project-memory" and action not in RECIPE_PROJECT_MEMORY_READ_ACTIONS:
        return False, f"/project-memory action `{action}` is not read-only recipe allowed"
    if command == "/control" and action not in RECIPE_CONTROL_READ_ACTIONS:
        return False, f"/control action `{action}` is not read-only recipe allowed"
    return True, ""


def recipe_step_violations(recipe: dict) -> list[str]:
    violations: list[str] = []
    max_steps = int_cfg("AI_COUNCIL_RECIPE_MAX_STEPS", 8)
    steps = recipe.get("steps") or []
    if len(steps) > max_steps:
        violations.append(f"too many steps: {len(steps)} > {max_steps}")
    for index, step in enumerate(steps, start=1):
        allowed, reason = recipe_step_is_allowed(step)
        if not allowed:
            violations.append(f"step {index}: {reason}")
    return violations


def run_recipe_background(prompt: str, task_id: str = "") -> dict:
    parts = prompt.strip().split(maxsplit=2)
    if len(parts) < 2 or parts[0].lower() != "run":
        response = recipe_response(prompt)
        return {
            "decision": "Recipe nie została uruchomiona.",
            "facts": [response],
            "dispute": "",
            "next_actions": [f"Sprawdź recipes: /recipes"],
            "ask_user": "Podaj /recipe run <name> <input>.",
            "raw_output": response,
            "report": response,
        }
    name = parts[1]
    recipe_input = parts[2] if len(parts) >= 3 else ""
    recipe = load_recipe(name)
    if not recipe:
        response = f"[Council] Nie znalazłem recipe `{name}`."
        return {"decision": response, "facts": [response], "dispute": "", "next_actions": ["/recipes"], "ask_user": "Wybierz istniejącą recipe.", "raw_output": response, "report": response}
    if recipe.get("enabled") is False:
        response = f"[Council] Recipe `{name}` jest disabled."
        return {"decision": response, "facts": [response], "dispute": "", "next_actions": [f"/recipe show {name}"], "ask_user": "Włącz recipe zanim ją uruchomisz.", "raw_output": response, "report": response}
    violations = recipe_step_violations(recipe)
    if violations:
        message = "; ".join(violations)
        record_error("recipe_step_policy", message=f"{name}: {message}", severity="warning", event={"recipe": name, "violations": violations})
        response = f"[Council] Recipe `{name}` zablokowana przez policy.\n" + "\n".join(f"- {violation}" for violation in violations)
        return {
            "decision": f"Recipe `{name}` zablokowana.",
            "facts": violations[:3],
            "dispute": "Recipe policy działa deny-by-default; write/external side effects wymagają osobnej approval ścieżki.",
            "next_actions": [f"/recipe show {name}", "/errors recent 10"],
            "ask_user": "Popraw recipe albo użyj jawnej ścieżki approval.",
            "raw_output": response,
            "report": response,
            "status": "blocked",
        }
    outputs = []
    previous_output = ""
    for index, step in enumerate(recipe.get("steps") or [], start=1):
        route = {
            "command": step.get("command", ""),
            "operators": [],
            "prompt": render_recipe_step_prompt(str(step.get("prompt", "")), recipe_input, previous_output),
            "task_id": task_id,
        }
        if not route["command"]:
            continue
        step_response = build_response(route)
        previous_output = step_response
        outputs.append(f"## Step {index}: {route['command']}\n\n{step_response}")
    raw = "\n\n".join(outputs) or "Recipe nie ma kroków."
    facts = extract_fact_lines(raw, limit=3)
    improvement = create_improvement_from_recipe(recipe, name, task_id, raw)
    next_actions = [f"Przejrzyj wynik: /details {task_id}", f"Pokaż recipe: /recipe show {name}"]
    followup = None
    if improvement:
        next_actions.insert(0, f"Follow-up: /improve apply {improvement['improvement_id']}")
        next_actions.insert(1, f"Backlog: /improve show {improvement['improvement_id']}")
        followup = {
            "command": "/improve",
            "prompt": f"apply {improvement['improvement_id']}",
            "intent": f"Zaplanuj wdrożenie improvement {improvement['improvement_id']}: {improvement.get('title', '')}",
            "risk": "R0",
            "reason": "improvement planning only; code changes still require Codex audit and tests",
        }
    result = {
        "decision": f"Recipe `{name}` zakończona.",
        "facts": facts or [f"Recipe `{name}` uruchomiona."],
        "dispute": "Recipe MVP działa deterministycznie; realne write/external actions nadal wymagają approval.",
        "next_actions": next_actions,
        "ask_user": "Zdecyduj, czy kontynuować wynik recipe.",
        "raw_output": raw,
        "report": f"# Recipe run: {name}\n\nInput: {recipe_input}\n\n{raw}",
    }
    if followup:
        result["followup"] = followup
    return result


def shortcut_recent_tasks(limit: int = 5) -> list[dict]:
    window = int_cfg("AI_COUNCIL_SHORTCUT_INBOX_WINDOW_SECONDS", 86400)
    rows: list[dict] = []
    now = datetime.now(timezone.utc)
    for task in latest_tasks(limit=120):
        if not str(task.get("source") or "").startswith("iphone_shortcut"):
            continue
        created = parse_utc(str(task.get("created_at") or ""))
        if created and (now - created).total_seconds() > window:
            continue
        rows.append(task)
        if len(rows) >= limit:
            break
    return rows


def shortcuts_response(prompt: str = "") -> str:
    ensure_council_dirs()
    token_ready = bool(cfg("AI_COUNCIL_SHORTCUT_TOKEN"))
    host = cfg("AI_COUNCIL_SHORTCUT_HOST", "127.0.0.1")
    port = int_cfg("AI_COUNCIL_SHORTCUT_PORT", 8788)
    send_default = bool_cfg("AI_COUNCIL_SHORTCUT_SEND_TELEGRAM", True)
    recent = shortcut_recent_tasks(limit=5)
    lines = [
        "[Council] iPhone Shortcuts L4.27",
        f"token: {'configured' if token_ready else 'missing'}",
        f"endpoint: http://{host}:{port}/shortcut",
        f"send_telegram_default: {send_default}",
        "payloads:",
        "- Ask Council: {\"text\":\"...\"}",
        "- Share URL research: {\"url\":\"https://...\", \"title\":\"...\", \"mode\":\"url\"}",
        "- Voice/screenshot/file: {\"media_base64\":\"...\", \"filename\":\"...\", \"mime_type\":\"...\", \"caption\":\"...\"}",
        "- Control read-only: {\"action\":\"agent\"} albo {\"action\":\"status\", \"task_id\":\"task-...\"}",
        "headers: X-AI-Council-Token albo Authorization: Bearer <token>",
        "safety: capture/read/research/status only; approve/deny/cancel są blokowane w Shortcuts i wymagają Telegram approval.",
    ]
    if recent:
        lines.append("recent:")
        for task in recent:
            lines.append(f"- {task.get('task_id')} | {task.get('status')} | {task.get('command')} | {compact_line(str(task.get('prompt') or ''), 90)}")
    else:
        lines.append("recent: brak iPhone Shortcut tasków.")
    if not token_ready:
        lines.append("NEXT: ustaw AI_COUNCIL_SHORTCUT_TOKEN i uruchom serve-shortcuts przez zatwierdzony launcher.")
    else:
        lines.append("NEXT: wyślij z iPhone Shortcut POST /shortcut albo wpisz /agent po capture.")
    return "\n".join(lines)


def capabilities_response() -> str:
    ensure_council_dirs()
    return (
        "[Council] Poke-like core online.\n"
        "Jak działa: piszesz normalnie. Krótkie rozmowy dostają szybką odpowiedź frontowego operatora; większe intencje idą przez Action Planner, który tworzy task, preview, ryzyko, koszt i next route, a dla typowych spraw wybiera live recipe.\n"
        "Mogę teraz: zrobić research przez Groka/X, uruchomić Claude Flow Opus 4.8 dla dużych planów, odpalić Council Codex+Claude+Grok, użyć Action Plannera bez slashy, pokazać /agent jako jeden priorytetowy inbox/next action, dobrać live recipes dla Gmail/Calendar/Drive/research/error-audit/evolution, przygotować integration drafty Gmail/Calendar/Drive/GitHub za approval bez external write, pokazać /front gdy bot wygląda na cichy, tworzyć follow-up proposals po zakończonej recipe, zatrzymać modele i autonomiczne pętle przez /control, zapisać i śledzić taski, wysyłać START/RUNNING/final progress oraz heartbeat dla długich prac, pokazać pełną historię etapów przez /progress, odpowiadać jednym hostowym głosem dla operatorów, zapisywać source-backed project memory z artifacts, pokazać Details/Facts/Next, analizować voice/photo/document/video, pamiętać ustalenia, logować błędy, prowadzić backlog ulepszeń, wykrywać proaktywne nudges, przeszukiwać read-only sources, pokazać connector readiness/auth setup, indeksować lokalny connector cache, robić publiczny i tokenowy read-only GitHub search, robić read-only Google OAuth sync dla Gmail/Calendar/Drive do lokalnego indeksu, tworzyć source-backed connector briefy, przygotować lokalne write/patch/execute po approval i zapisać durable verifier evidence dla /verify oraz /rollback.\n"
        "Workspace: D:\\ai-council\\workspaces\\{codex,claude,grok,shared}; artefakty: D:\\ai-council\\artifacts.\n"
        "Przykłady bez slashy: `czemu bot nie odpowiada`, `front status`, `ogarnij mi research Poke`, `przygotuj mi raport z gmail`, `sprawdź pętle`, `pokaż kontrolę`, `pokaż follow-upy`, `pamięć projektu`, `szukaj w pamięci projektu Poke`, `start task-...`, `zrób plan ...`, `skonsultuj z council ...`, `zapisz task ...`, `pokaż źródła`, `pokaż konektory`, `sprawdź connector github`, `sync gmail Poke`, `szukaj w źródłach memory Poke`, `pokaż błędy`, `pokaż nudges`, `pokaż ulepszenia`, `status`, `co dalej task-...`, `anuluj task-...`.\n"
        "L4.28: Integration Action Drafts przygotowują Gmail/Calendar/Drive/GitHub drafty jako pending actions; approval zapisuje decyzję, ale nie wykonuje external write.\n"
        "To nadal nie jest pełny Poke: brakuje prywatnego iMessage bridge, execution adapterów dla zatwierdzonych integracji i bardziej proaktywnego prowadzenia tematów przez integracje.\n"
        "Nadal zablokowane bez approval: shell execute, zapis poza workspace, kontakty, publikacja, kasowanie, pieniądze, DNS/auth/billing."
    )


def goal_response() -> str:
    ensure_council_dirs()
    recent_errors = error_rows(days=1)
    improvements_open = open_improvements(limit=50)
    nudges_open = [row for row in latest_nudges(limit=50) if row.get("status") in {"open", "sent"}]
    return (
        "[Council] Goal: Bartek Agent OS = Poke-like + OpenClaw/Hermes execution.\n"
        "Status: NIE jest ukończony. Jeśli bot nie odpowiada jak Poke, to znaczy, że jesteśmy przed parity, nie po niej. Goal zostaje aktywny do Poke parity albo lepiej.\n"
        "Dlaczego nie czuje się jeszcze jak Poke: Poke to messaging-first operator z proaktywnymi recipes, szybkim progress UX i głębokimi integracjami. U nas rdzeń działa, ale proaktywność, pamięć i integracje write-capable nie są jeszcze na tym poziomie.\n"
        "Gotowe: Telegram 24/7 na desktopie, natural intent routing, Action Planner v1 z live recipe selection i L4.28 integration drafts, Follow-up Runner L4.17, Budget Guard/Kill Switch L4.18, Verifier Evidence L4.19, Progress UX L4.20, Unified Front Orchestrator L4.21, Project Memory Spine L4.22, L4.23 Cost Ledger Reservation, L4.24 Poke Front Reliability, L4.25 Rich Progress Streaming, L4.26 Agent Inbox, L4.27 iPhone Primary Capture, L4.28 Gmail/Calendar/Drive/GitHub action drafts, szybki front chat, /front runtime diagnosis, background jobs, cancel/status/progress/details/facts/next, artifacts, memory, media capture/STT/OCR, Grok research/X search, Claude Opus 4.8 Flow, Codex/Claude/Grok Council, Risk Officer, workspace write/patch/execute po approval, recipes, error log, improvement backlog, real Council host synthesis, single-listener lock, Proactive Event Brain v1, Source Integrations read-only v0, Connector Bridge read-only v0, Connector Cache Index v0, GitHub public fallback, GitHub token/API read-only bridge, Google OAuth read-sync dla Gmail/Calendar/Drive.\n"
        "Brakuje do Poke-level: prywatny iMessage bridge, execution adaptery dla zatwierdzonych integracji, natywna ścieżka GitHub CLI auth, opcjonalny token-level streaming i głębsze autonomiczne prowadzenie tematów przez integracje.\n"
        f"Ryzyka teraz: errors_24h={len(recent_errors)}, open_improvements={len(improvements_open)}, open_nudges={len(nudges_open)}.\n"
        "Najbliższy cel wdrożeniowy: L4.29 Integration Execution Adapters - nadal bez auto-write; najpierw adaptery z osobnym execute/verify i twardym approval gate."
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
        "[Council] Online na Desktopie 24/7. L4.28 Integration Action Drafts + iPhone Primary Capture + Agent Inbox + Rich Progress Streaming + Poke Front Reliability + Cost Ledger Reservation + Project Memory Spine + Unified Front Orchestrator + Progress UX + Verifier Evidence + Budget Guard/Kill Switch + Follow-up Runner + Live Recipes + Google OAuth Read Sync: /agent priority inbox, /drafts, /connector draft gmail|calendar|drive|github, /shortcuts status, Share URL -> research brief, shortcut read-only actions/status, Telegram media capture + text/image/STT analysis + media-to-intent routing, /front runtime diagnosis, short chat local-first, gated Grok chat, Action Planner task/preview/risk/cost/live_recipe/draft_action, final delivery cards, START/RUNNING/final progress messages, heartbeat dla długich prac, /progress timeline z COLLECTING/DELIVERING/COMPLETED events, host-wrapped operator responses, source-backed project memory, model-call reservation before expensive calls, LLM router off by default for ordinary chat, follow-up proposals, /control kill/pause/limits, optional token-gated iPhone Shortcuts ingress, inline buttons, recipes scheduler, autonomous error/evolution loops, proactive nudges, source registry, connector readiness/auth setup/cache/Google OAuth sync, GitHub public/token read-only fallback, Risk Officer R0-R4, workspace execute/verify/rollback z durable evidence, natural intent routing, memory auto-recall, actions, background jobs, artifact index, structured council v0, approved workspace write/append/patch, @claude-flow Opus 4.8, task status/cancel/cost/idempotency/stuck detection.\n"
        "Domyślnie: zwykła wiadomość -> szybki front operator; `co dalej` -> /agent z jednym priorytetem; action-like wiadomość -> Action Planner; długie zadanie -> START/RUNNING, heartbeat jeśli trwa długo, potem final delivery card; /status i /progress pokazują pełny timeline etapów; completed artifact -> project memory decision/facts/next with source; @codex/@claude/@grok/@research -> jeden hostowy głos w Telegramie, raw output zostaje w artifacts; planner dobiera live recipes dla research/Gmail/Calendar/Drive/error-audit/evolution; zakończona recipe tworzy follow-up proposal; /verify zapisuje checked evidence dla workspace actions; /rollback działa po executed/verified/verify_failed; /control zatrzymuje modele i autonomiczne pętle; document/text -> local extraction -> route_text; photo/screenshot -> Grok vision/OCR -> route_text; voice/audio/video -> xAI STT REST -> route_text; @claude-flow lub /flow -> Claude Opus 4.8 plan workflow w tle; @xresearch lub /poke-research -> Grok X search w tle; /connector sync -> Gmail/Calendar/Drive read-only OAuth cache; /connector brief -> source-backed raport; /source search -> read-only źródła; /recipe run i scheduled recipes -> recipe w tle; /loops pokazuje error/evolution loops; Proactive Event Brain -> /nudges; brak shell/external actions bez approval.\n"
        f"Usage today: {usage_text}. Stuck: {stuck_text}.\n"
        "Komendy L4.28: /agent, /agent run [id], /drafts, /drafts show <id>, /connector draft <name> <intent>, /shortcuts, /front, /project-memory, /control, /plan-action, /start-task, /followups, /loops, /recipe suggest <intent>, /health, /selftest, /goal, /sources, /source search <name> <query>, /connectors, /connector check|auth|ingest|sync|brief <name>, /nudges, /status <task_id>, /progress <task_id>, /details <task_id>, /facts <task_id>, /next <task_id>, /cancel <task_id>, /cost, /risk, /execute, /verify, /rollback, /recipes, /recipe enable|disable <name>, /xresearch, /poke-research."
    )


def health_response() -> str:
    ensure_council_dirs()
    status = operator_binary_status()
    control = load_control_state()
    running = [task for task in latest_tasks(limit=50) if task.get("status") in {"running", "running_background"}]
    stuck = stuck_tasks(limit=5)
    recent_errors = error_rows(days=1)
    improvements_open = open_improvements(limit=50)
    nudges_open = [row for row in latest_nudges(limit=50) if row.get("status") in {"open", "sent"}]
    route_counts = route_source_summary()
    route_counts_text = ", ".join(f"{key}:{route_counts[key]}" for key in sorted(route_counts)) or "brak"
    offset = read_offset()
    lines = [
        "[Council] Health",
        f"project: {PROJECT_DIR}",
        f"env: {'OK' if ENV_PATH.exists() else 'missing'}",
        f"telegram_offset: {offset if offset is not None else 'none'}",
        f"running_tasks: {len(running)}",
        f"stuck_tasks: {len(stuck)}",
        f"errors_24h: {len(recent_errors)}",
        f"improvements_open: {len(improvements_open)}",
        f"nudges_open: {len(nudges_open)}",
        f"control: kill={control.get('global_kill_switch')} models_paused={control.get('model_calls_paused')} scheduler_paused={control.get('scheduled_recipes_paused')}",
        f"llm_router: {'on' if llm_router_enabled() and cfg('XAI_API_KEY') else 'off'}",
        f"front: L4.28 drafts=on shortcuts=on agent_inbox=on local_short_chat=on progress_timeline=on poke_chat_llm={'gated' if poke_chat_llm_configured() else 'off'} command=/front",
        f"route_sources: {route_counts_text}",
    ]
    for name, item in status.items():
        marker = "OK" if item.get("configured") else "missing"
        extra = ""
        if name == "claude_flow":
            extra = f" model={item.get('model')} mode={item.get('permission_mode')}"
        lines.append(f"{name}: {marker}{extra}")
    if stuck:
        lines.append("stuck: " + ", ".join(task.get("task_id", "") for task in stuck))
    lines.append("quick_check: zwykła wiadomość powinna wracać jako szybki /chat bez task_id.")
    return "\n".join(lines)


def selftest_response() -> str:
    ensure_council_dirs()
    status = operator_binary_status()
    running = [task for task in latest_tasks(limit=50) if task.get("status") in {"running", "running_background"}]
    stuck = stuck_tasks(limit=5)
    required_docs = {
        "grok_x_research": PROJECT_DIR / "docs" / "research" / "grok-x-poke-research-2026-06-06.md",
        "claude_plan": PROJECT_DIR / "docs" / "research" / "claude-opus48-poke-research-full-2026-06-06.md",
        "claude_tournament": PROJECT_DIR / "docs" / "research" / "claude-opus48-tournament-scorecard-2026-06-06.md",
        "target": PROJECT_DIR / "docs" / "POKE_CLONE_TARGET.md",
    }
    doc_status = ", ".join(f"{name}:{'OK' if path.exists() else 'missing'}" for name, path in required_docs.items())
    operator_status = ", ".join(f"{name}:{'OK' if item.get('configured') else 'missing'}" for name, item in status.items())
    shortcut_state = "ready" if cfg("AI_COUNCIL_SHORTCUT_TOKEN") else "token_missing_not_started"
    telegram_state = "configured" if cfg("TELEGRAM_BOT_TOKEN") and cfg("TELEGRAM_ALLOWED_CHAT_ID") else "missing_env"
    lines = [
        "[Council] Selftest",
        "version: L4.28 Integration Action Drafts + iPhone Primary Capture + Agent Inbox + Rich Progress Streaming + Poke Front Reliability + Cost Ledger Reservation + Project Memory Spine + Unified Front Orchestrator + Progress UX + Verifier Evidence + Budget Guard/Kill Switch + Follow-up Runner + Live Recipes + Google OAuth read-sync",
        f"project: {PROJECT_DIR}",
        f"env: {'OK' if ENV_PATH.exists() else 'missing'}",
        f"telegram: {telegram_state}",
        f"operators: {operator_status}",
        f"running_tasks: {len(running)}",
        f"stuck_tasks: {len(stuck)}",
        f"artifacts_dir: {'OK' if ARTIFACTS_DIR.exists() else 'missing'}",
        f"workspaces_dir: {'OK' if WORKSPACES_DIR.exists() else 'missing'}",
        f"docs: {doc_status}",
        f"shortcuts: {shortcut_state}",
        "live_telegram: jeśli widzisz tę wiadomość w Telegramie po wpisaniu /selftest, inbound i outbound działają.",
    ]
    if stuck:
        lines.append("stuck: " + ", ".join(task.get("task_id", "") for task in stuck))
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
    entry_id: str = "",
) -> dict:
    init_memory_db()
    clean_key = key.strip() or "note"
    clean_value = value.strip() or "(empty)"
    entry_id = entry_id.strip() or f"mem-{datetime.now().strftime('%Y%m%d-%H%M%S')}-{short_hash(clean_key + clean_value)[:6]}"
    created_at = utc_now()
    try:
        with sqlite3.connect(MEMORY_DB) as conn:
            existing = conn.execute("SELECT created_at FROM memory_entries WHERE entry_id = ?", (entry_id,)).fetchone()
            if existing and existing[0]:
                created_at = str(existing[0])
    except sqlite3.Error:
        pass
    row = {
        "entry_id": entry_id,
        "created_at": created_at,
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
            conn.execute("DELETE FROM memory_fts WHERE entry_id = ?", (entry_id,))
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
        project_rows = project_memory_rows(prompt, limit=limit)
        rows = memory_search(prompt, limit=limit)
    except Exception:
        return ""
    lines = []
    seen: set[str] = set()
    if project_rows:
        lines.append("Project memory:")
    for row in project_rows:
        seen.add(str(row.get("entry_id") or ""))
        source = compact_line(str(row.get("source") or row.get("task_id") or ""), 72)
        lines.append(f"- {compact_line(row.get('key', ''), 48)}: {compact_line(row.get('value', ''), 180)} | source={source}")
    regular_rows = [row for row in rows if str(row.get("entry_id") or "") not in seen]
    if regular_rows:
        if lines:
            lines.append("Memory:")
    for row in regular_rows:
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


def project_memory_entry_id(task_id: str, section: str) -> str:
    return "pmem-" + short_hash(f"{task_id}:{section}")[:16]


def project_memory_value(body: str, *, task_id: str, source: str) -> str:
    lines = [body.strip()]
    if task_id:
        lines.append(f"Task: {task_id}")
        lines.append(f"Details: /details {task_id}")
    if source:
        lines.append(f"Source: {source}")
    return "\n".join(line for line in lines if line)


def save_project_memory_from_artifact(artifact: dict) -> list[dict]:
    task_id = str(artifact.get("task_id") or "").strip()
    if not task_id:
        return []
    source = str(artifact.get("report_path") or artifact.get("artifact_dir") or "")
    rows: list[dict] = []
    decision = str(artifact.get("decision") or "").strip()
    if decision:
        rows.append(
            memory_save(
                f"project:{task_id}:decision",
                project_memory_value(f"Decision: {decision}", task_id=task_id, source=source),
                kind="project_memory",
                source=source or "artifact",
                task_id=task_id,
                entry_id=project_memory_entry_id(task_id, "decision"),
            )
        )
    facts = [str(item).strip() for item in (artifact.get("facts") or []) if str(item).strip()]
    if facts:
        rows.append(
            memory_save(
                f"project:{task_id}:facts",
                project_memory_value("Facts: " + " | ".join(facts[:8]), task_id=task_id, source=source),
                kind="project_memory",
                source=source or "artifact",
                task_id=task_id,
                entry_id=project_memory_entry_id(task_id, "facts"),
            )
        )
    next_actions = [str(item).strip() for item in (artifact.get("next_actions") or []) if str(item).strip()]
    if next_actions:
        rows.append(
            memory_save(
                f"project:{task_id}:next",
                project_memory_value("Next: " + " | ".join(next_actions[:8]), task_id=task_id, source=source),
                kind="project_memory",
                source=source or "artifact",
                task_id=task_id,
                entry_id=project_memory_entry_id(task_id, "next"),
            )
        )
    return rows


def project_memory_rows(query: str = "", limit: int = 8) -> list[dict]:
    init_memory_db()
    clean_query = query.strip()
    with sqlite3.connect(MEMORY_DB) as conn:
        conn.row_factory = sqlite3.Row
        if clean_query:
            like = f"%{clean_query}%"
            rows = conn.execute(
                """
                SELECT entry_id, created_at, kind, agent, key, value, source, task_id
                FROM memory_entries
                WHERE kind = 'project_memory'
                  AND (key LIKE ? OR value LIKE ? OR source LIKE ? OR task_id LIKE ?)
                ORDER BY id DESC
                LIMIT ?
                """,
                (like, like, like, like, limit),
            ).fetchall()
        else:
            rows = conn.execute(
                """
                SELECT entry_id, created_at, kind, agent, key, value, source, task_id
                FROM memory_entries
                WHERE kind = 'project_memory'
                ORDER BY id DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
    return [dict(row) for row in rows]


def project_memory_rebuild(limit: int = 100) -> list[dict]:
    latest: dict[str, dict] = {}
    for row in read_jsonl(ARTIFACT_INDEX_FILE):
        task_id = str(row.get("task_id") or "")
        if task_id:
            latest[task_id] = row
    rebuilt: list[dict] = []
    for artifact in list(latest.values())[-limit:]:
        rebuilt.extend(save_project_memory_from_artifact(artifact))
    return rebuilt


def project_memory_context_for_prompt(prompt: str, limit: int = 4) -> str:
    try:
        rows = project_memory_rows(prompt, limit=limit)
    except Exception:
        return ""
    lines = []
    for row in rows:
        source = compact_line(str(row.get("source") or row.get("task_id") or ""), 72)
        value = compact_line(str(row.get("value") or ""), 220)
        lines.append(f"- {compact_line(str(row.get('key') or ''), 64)}: {value} | source={source}")
    return "\n".join(lines)


def project_memory_response(prompt: str) -> str:
    stripped = prompt.strip()
    lower = stripped.lower()
    if lower.startswith("rebuild"):
        raw_limit = stripped.split(maxsplit=1)[1].strip() if len(stripped.split(maxsplit=1)) > 1 else ""
        try:
            limit = int(raw_limit) if raw_limit else 100
        except ValueError:
            limit = 100
        rows = project_memory_rebuild(limit=max(1, min(limit, 500)))
        return f"[Council] Project Memory rebuild: zapisano/odświeżono {len(rows)} wpisów z artifact index."
    if lower.startswith("search"):
        query = stripped[6:].strip()
        rows = project_memory_rows(query, limit=10)
        if not rows:
            return f"[Council] Project Memory search: brak wyników dla `{query}`."
        lines = [f"[Council] Project Memory search `{query}`"]
    elif lower.startswith("context"):
        query = stripped[7:].strip()
        context = project_memory_context_for_prompt(query, limit=6)
        return f"[Council] Project Memory context `{query}`\n{context or 'brak trafień'}"
    else:
        rows = project_memory_rows("", limit=10)
        if not rows:
            return "[Council] Project Memory puste. Użyj: /project-memory rebuild."
        lines = ["[Council] Project Memory recent"]
    for row in rows:
        lines.append(
            f"- {row['entry_id']} | {compact_line(row['key'], 48)} | {compact_line(row['value'], 120)}"
        )
    lines.append("Użyj: /project-memory search <tekst>, /project-memory context <tekst>, /project-memory rebuild.")
    return "\n".join(lines)


def risk_level_for_text(text: str) -> tuple[str, str]:
    lower = (text or "").lower()
    if any(
        token in lower
        for token in [
            "billing",
            "płat",
            "payment",
            "money",
            "stripe",
            "dns",
            "delete",
            "usuń",
            "usun",
            "auth token",
            "oauth secret",
            "login credentials",
            "zaloguj",
            "publish",
            "opublikuj",
            "contact customer",
            "kontakt do klienta",
            "skontaktuj",
            "wyślij do klienta",
            "wyslij do klienta",
            "wyślij mail",
            "wyslij mail",
            "wyślij email",
            "wyslij email",
        ]
    ):
        return "R4", "money/publish/contact/delete/DNS/auth/billing risk"
    if any(token in lower for token in ["gmail", "calendar", "drive", "github", "external api", "api write", "email", "send mail", "schedule meeting"]):
        return "R3", "external write/API/contact integration risk"
    if any(token in lower for token in ["shell", "terminal", "powershell", "cmd.exe", "subprocess", "install", "pip install", "npm install", "run command"]):
        return "R2", "sandbox/test/build or command execution risk"
    if any(token in lower for token in ["write", "append", "patch", "zapisz", "dopisz", "zmień", "workspace", "plik"]):
        return "R1", "local reversible workspace write risk"
    return "R0", "read-only response/planning risk"


def normalize_risk(risk: str, description: str = "") -> tuple[str, str]:
    value = (risk or "").strip().upper()
    if value in RISK_LEVELS:
        return value, f"explicit {value}"
    legacy = (risk or "").strip().lower()
    if legacy == "low":
        return "R1", "legacy low mapped to R1"
    if legacy == "high":
        return "R2", "legacy high mapped to R2"
    return risk_level_for_text(description)


def risk_policy(level: str) -> str:
    return {
        "R0": "auto: read-only response, no side effects",
        "R1": "approval required: local reversible workspace write",
        "R2": "approval + sandbox required: local build/test/shell-like risk",
        "R3": "explicit approval required: external write/API/integration",
        "R4": "manual approval outside automation: money/publish/contact/DNS/auth/billing/delete",
    }.get(level, "unknown risk policy")


def risk_response(prompt: str) -> str:
    target = prompt.strip()
    action = get_latest_action(target) if target.startswith("act-") else None
    if action:
        level, reason = normalize_risk(str(action.get("risk") or ""), action.get("description", ""))
        return (
            f"[Risk Officer] {action['action_id']}\n"
            f"risk: {level}\n"
            f"reason: {action.get('risk_reason') or reason}\n"
            f"policy: {risk_policy(level)}\n"
            f"status: {action.get('status')}\n"
            f"type: {action.get('type')}"
        )
    level, reason = risk_level_for_text(target)
    return f"[Risk Officer]\nrisk: {level}\nreason: {reason}\npolicy: {risk_policy(level)}"


def create_action(description: str, *, action_type: str = "manual", risk: str = "medium", payload: dict | None = None) -> dict:
    ensure_council_dirs()
    clean_description = description.strip() or "Brak opisu akcji"
    risk_level, risk_reason = normalize_risk(risk, clean_description)
    action_seed = f"{clean_description}:{action_type}:{risk}:{time.time_ns()}"
    action_id = f"act-{datetime.now().strftime('%Y%m%d-%H%M%S')}-{short_hash(action_seed)[:6]}"
    action = {
        "action_id": action_id,
        "created_at": utc_now(),
        "updated_at": utc_now(),
        "status": "pending",
        "type": action_type,
        "risk": risk_level,
        "risk_reason": risk_reason,
        "approval_policy": risk_policy(risk_level),
        "description": clean_description,
        "path_scope": "D:\\ai-council\\workspaces only",
        "execution": "risk_officer_l3",
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


def action_planner_trigger(text: str) -> bool:
    lower = normalize_intent_text(text)
    if not lower or lower.startswith(("/", "@")):
        return False
    prefixes = (
        "ogarnij",
        "załatw",
        "zalatw",
        "pomóż mi",
        "pomoz mi",
        "przygotuj mi",
        "stwórz mi",
        "stworz mi",
        "zrób dla mnie",
        "zrob dla mnie",
        "zorganizuj",
        "dopilnuj",
        "przypilnuj",
        "ustaw",
        "umów",
        "umow",
        "wyślij",
        "wyslij",
        "napisz mail",
        "napisz email",
        "napisz odpowiedź",
        "napisz odpowiedz",
    )
    return lower.startswith(prefixes)


def action_planner_mode(prompt: str) -> dict:
    lower = normalize_intent_text(prompt)
    risk, reason = risk_level_for_text(prompt)
    draft_connector = integration_connector_for_intent(prompt)
    has_side_effect_verb = any(
        token in lower
        for token in (
            "wyślij mail",
            "wyslij mail",
            "wyślij email",
            "wyslij email",
            "wyślij wiadomość",
            "wyslij wiadomość",
            "wyślij do ",
            "wyslij do ",
            "napisz mail do",
            "napisz email do",
            "opublikuj",
            "usuń",
            "usun",
            "skasuj",
            "kup",
            "zapłać",
            "zaplac",
            "umów",
            "umow",
            "schedule meeting",
            "zadzwoń",
            "zadzwon",
            "contact customer",
            "skontaktuj",
            "dns",
            "billing",
            "auth token",
            "oauth secret",
            "zaloguj",
        )
    )
    mode = "flow"
    command = "/flow"
    route_prompt = prompt.strip()
    decision = "Przygotować plan wykonania i zostawić wykonanie po decyzji użytkownika."
    source_requested = any(token in lower for token in ("gmail", "calendar", "kalendarz", "drive", "docs", "źródł", "zrodl"))
    selected_recipe = None

    if has_side_effect_verb or risk in {"R2", "R4"} or (risk == "R3" and not source_requested):
        mode = "approval"
        command = "/propose"
        decision = "To wygląda na akcję z ryzykiem, więc najpierw powstaje pending action z approval."
        if draft_connector:
            command = "/connector"
            route_prompt = f"draft {draft_connector} {prompt.strip()}".strip()
            decision = f"Przygotować integration draft `{draft_connector}` i zostawić external write za approval."
    else:
        selected_recipe = select_live_recipe(prompt)
    if mode == "approval":
        pass
    elif selected_recipe:
        recipe_name = str(selected_recipe.get("name") or "")
        recipe = load_recipe(recipe_name) or {}
        recipe_risk = str(recipe.get("risk") or "")
        if recipe_risk:
            risk = recipe_risk
            reason = "selected live recipe declared read-only/planning risk" if recipe_risk == "R0" else f"selected live recipe risk {recipe_risk}"
        mode = "recipe"
        command = "/recipe"
        route_prompt = f"run {recipe_name} {prompt.strip()}".strip()
        decision = f"Uruchomić live recipe `{recipe_name}`, bo pasuje do intencji i źródeł."
    elif source_requested and not has_side_effect_verb:
        mode = "connector"
        command = "/connector"
        decision = "Najpierw odczytać źródła read-only albo zrobić connector brief."
        if "drive" in lower or "docs" in lower:
            route_prompt = f"brief drive {prompt.strip()}"
        elif "calendar" in lower or "kalendarz" in lower:
            route_prompt = f"brief calendar {prompt.strip()}"
        else:
            route_prompt = f"brief gmail {prompt.strip()}"
    elif any(token in lower for token in ("council", "claude i grok", "claude i grokiem", "rada ai", "ai council")):
        mode = "council"
        command = "/council"
        decision = "Skonsultować temat przez Council i zapisać decyzję/fakty/next."
    elif any(token in lower for token in ("research", "zbadaj", "poszukaj", "sprawdź internet", "sprawdz internet", "x.com", "twitter", "poke")):
        mode = "research"
        command = "@research"
        decision = "Zrobić research brief i potem wybrać następny krok."
    elif any(token in lower for token in ("recipe", "recept", "codzienny digest", "daily digest")):
        mode = "recipe"
        command = "/recipe"
        route_prompt = f"run project_next_action {prompt.strip()}".strip()
        decision = "Uruchomić istniejącą recipe jako powtarzalny workflow."
    elif any(token in lower for token in ("task", "zadanie", "zapisz do kolejki")):
        mode = "task"
        command = "/task"
        decision = "Zapisać temat jako task i dopiero potem wybrać operatora."

    return {
        "mode": mode,
        "command": command,
        "prompt": route_prompt,
        "risk": risk,
        "risk_reason": reason,
        "decision": decision,
        "approval_required": mode == "approval",
        "draft_connector": draft_connector if mode == "approval" else "",
        "recipe_name": selected_recipe.get("name", "") if selected_recipe else "",
        "recipe_reason": selected_recipe.get("reason", "") if selected_recipe else "",
        "recipe_score": selected_recipe.get("score", 0) if selected_recipe else 0,
    }


def action_planner_estimated_cost(plan: dict) -> float:
    mode = str(plan.get("mode") or "")
    if mode == "research":
        return estimated_operator_cost("grok")
    if mode == "recipe":
        return recipe_estimated_cost(str(plan.get("recipe_name") or ""))
    if mode == "flow":
        return estimated_operator_cost("claude-flow")
    if mode == "council":
        return estimated_operator_cost("grok") + estimated_operator_cost("claude") + estimated_operator_cost("codex")
    return 0.0


def create_planned_task(prompt: str, plan: dict) -> dict:
    task = create_task(
        prompt,
        source="action_planner",
        status="planned",
        command="/plan-action",
        operators=["host"],
    )
    updated = update_task_status(
        task["task_id"],
        "planned",
        "action planner prepared next route",
        planner_mode=plan.get("mode", ""),
        recommended_command=plan.get("command", ""),
        recommended_prompt=plan.get("prompt", ""),
        recommended_route={
            "command": plan.get("command", ""),
            "operators": operators_for_command(str(plan.get("command") or "")),
            "prompt": plan.get("prompt", ""),
            "mode": plan.get("mode", ""),
            "intent": "planner",
            "recipe_name": plan.get("recipe_name", ""),
        },
        risk=plan.get("risk", ""),
        risk_reason=plan.get("risk_reason", ""),
        recommended_recipe=plan.get("recipe_name", ""),
        recipe_reason=plan.get("recipe_reason", ""),
        recipe_score=plan.get("recipe_score", 0),
    )
    return updated or task


def operators_for_command(command: str) -> list[str]:
    if command in {"@research", "@xresearch", "/xresearch", "/poke-research"}:
        return ["grok"]
    if command in {"/flow", "@claude-flow"}:
        return ["claude-flow"]
    if command == "/council":
        return ["codex", "claude", "grok"]
    return ["host"]


def action_planner_response(prompt: str, chat_id: str = "") -> str:
    clean = prompt.strip()
    if not clean:
        return "[Council] Action Planner: napisz, co mam ogarnąć."
    plan = action_planner_mode(clean)
    task = create_planned_task(clean, plan)
    cost = action_planner_estimated_cost(plan)
    action = None
    if plan.get("approval_required"):
        if plan.get("draft_connector"):
            action = create_integration_draft_action(
                str(plan.get("draft_connector") or ""),
                clean,
                risk=plan["risk"],
                source="action_planner",
                task_id=str(task.get("task_id") or ""),
            )
        else:
            action = create_action(
                f"Planner proposal: {clean}",
                action_type="planner_proposal",
                risk=plan["risk"],
                payload={
                    "task_id": task.get("task_id"),
                    "intent": clean,
                    "planner_mode": plan["mode"],
                    "recommended_command": plan["command"],
                    "recommended_prompt": plan["prompt"],
                    "estimated_cost_usd": cost,
                },
            )
    lines = [
        "[Council] Action Planner L4.16",
        f"task_id: {task.get('task_id')}",
        f"DECYZJA: {plan['decision']}",
        f"TRYB: {plan['mode']}",
        f"RYZYKO: {plan['risk']} - {plan['risk_reason']}",
        f"KOSZT_PREVIEW: ${cost:.4f} est.",
        "PREVIEW:",
        f"- intent: {compact_line(clean, 220)}",
        f"- next_route: {plan['command']} {compact_line(str(plan['prompt']), 180)}",
    ]
    if plan.get("recipe_name"):
        lines.append(f"- live_recipe: {plan.get('recipe_name')} ({compact_line(str(plan.get('recipe_reason') or ''), 120)})")
    if action:
        lines.extend(
            [
                "Pending action utworzona.",
                f"id: {action['action_id']}",
                f"type: {action.get('type')}",
                f"approve: /approve {action['action_id']}",
                f"deny: /deny {action['action_id']}",
                "DO CIEBIE: zatwierdź, edytuj intencję nową wiadomością albo anuluj.",
            ]
        )
    else:
        lines.extend(
            [
                "NEXT:",
                f"1. start {task.get('task_id')}",
                f"2. status {task.get('task_id')}",
                "DO CIEBIE: napisz `start task-...`, jeśli mam uruchomić rekomendowany tryb.",
            ]
        )
    return "\n".join(lines)


def start_planned_task_response(prompt: str, chat_id: str = "") -> str:
    target_id = prompt.strip().split()[0] if prompt.strip() else ""
    if not target_id:
        return "[Council] Użyj: start task-..."
    task = get_latest_task(target_id)
    if not task:
        return f"[Council] Nie znalazłem task `{target_id}`."
    if task.get("status") not in {"planned", "queued"}:
        return task_status_response(target_id)
    route = task.get("recommended_route")
    if not isinstance(route, dict) or not route.get("command"):
        return f"[Council] Task `{target_id}` nie ma recommended route.\n{task_status_response(target_id)}"
    route = {**route, "task_id": target_id}
    chat_id = chat_id or cfg("TELEGRAM_ALLOWED_CHAT_ID")
    if route_should_background(route):
        update_task_status(target_id, "running", "planner start requested")
        return start_background_job(route, chat_id=chat_id, task_id=target_id, send_progress=True)
    try:
        response = build_response(route, chat_id=chat_id)
    except Exception as exc:
        response = f"[Council] Error: {compact_line(redact_secrets(str(exc)), 500)}"
        update_task_status(target_id, "failed", redact_secrets(str(exc))[:300])
        return response
    response_lower = response.lower()
    if response.startswith("[Council] Error") or "failed" in response_lower or "nie znalazłem" in response_lower:
        update_task_status(target_id, "failed", "planner route returned error")
    else:
        update_task_status(target_id, "completed", "planner route completed")
    return response


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
    before_content = target.read_text(encoding="utf-8", errors="replace") if target.exists() else ""
    return create_action(
        f"Write workspace file {target}",
        action_type="workspace_write",
        risk="R1",
        payload={
            "path": str(target),
            "content": content,
            "before_exists": target.exists(),
            "before_content": before_content,
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
        risk="R1",
        payload={
            "path": str(target),
            "append_content": append_content,
            "before_exists": target.exists(),
            "before_content": old_content,
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
        risk="R1",
        payload={
            "path": str(target),
            "old": old,
            "new": new,
            "before_exists": True,
            "before_content": current,
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


def followups_response(prompt: str = "") -> str:
    rows = [
        action
        for action in latest_by_id(ACTIONS_FILE, "action_id", limit=50)
        if action.get("type") == "followup_proposal"
    ]
    if not rows:
        return "[Council] Follow-ups: brak propozycji. Zakończona recipe utworzy follow-up automatycznie."
    lines = ["[Council] Follow-ups L4.17"]
    for action in rows[:10]:
        payload = action.get("payload") or {}
        route = f"{payload.get('recommended_command', '')} {payload.get('recommended_prompt', '')}".strip()
        lines.append(
            f"- {action.get('action_id')} | {action.get('status')} | {action.get('risk')} | task={payload.get('source_task_id', '')} | {compact_line(route, 120)}"
        )
    lines.append("Użyj: /approve <id> albo /deny <id>.")
    return "\n".join(lines)


def nudged_ids() -> set[str]:
    return {str(row.get("action_id")) for row in read_jsonl(NUDGES_FILE) if row.get("action_id")}


def nudge_keys() -> set[str]:
    return {str(row.get("nudge_key")) for row in read_jsonl(NUDGES_FILE) if row.get("nudge_key")}


def latest_nudges(limit: int = 10) -> list[dict]:
    rows = [row for row in read_jsonl(NUDGES_FILE) if row.get("nudge_id") or row.get("action_id")]
    return rows[-limit:][::-1]


def format_nudge(row: dict) -> str:
    nudge_id = str(row.get("nudge_id") or row.get("action_id") or "")
    status = str(row.get("status") or "open")
    kind = str(row.get("kind") or ("pending_action" if row.get("action_id") else "nudge"))
    title = str(row.get("title") or row.get("summary") or "Nudge")
    next_action = str(row.get("next_action") or "")
    line = f"- {nudge_id} | {status} | {kind} | {compact_line(title, 120)}"
    return line + (f" | next: {compact_line(next_action, 100)}" if next_action else "")


def nudges_response(prompt: str = "") -> str:
    parts = prompt.strip().split(maxsplit=1)
    if parts and parts[0].lower() in {"ack", "done", "dismiss"} and len(parts) >= 2:
        target = parts[1].strip()
        current = None
        for row in read_jsonl(NUDGES_FILE):
            if row.get("nudge_id") == target or row.get("action_id") == target:
                current = row
        if not current:
            return f"[Council] Nie znalazłem nudge `{target}`."
        updated = {**current, "status": "dismissed", "updated_at": utc_now()}
        append_jsonl(NUDGES_FILE, updated)
        return f"[Council] Nudge `{target}` dismissed."
    rows = latest_nudges(limit=12)
    if not rows:
        return "[Council] Nudges: brak zapisanych proaktywnych sygnałów."
    lines = ["[Council] Nudges"]
    for row in rows:
        lines.append(format_nudge(row))
    lines.append("Użyj: /nudges dismiss <id> albo wykonaj next action z listy.")
    return "\n".join(lines)


def priority_score(value: str) -> int:
    text = str(value or "P2").upper()
    if text.startswith("P0"):
        return 100
    if text.startswith("P1"):
        return 85
    if text.startswith("P2"):
        return 65
    if text.startswith("P3"):
        return 45
    return 65


def pending_actions(limit: int = 30) -> list[dict]:
    return [
        action
        for action in latest_by_id(ACTIONS_FILE, "action_id", limit=limit)
        if action.get("status") == "pending"
    ]


def followup_action_can_run(action: dict) -> tuple[bool, str]:
    if action.get("type") != "followup_proposal":
        return False, "not follow-up"
    payload = action.get("payload") or {}
    command = str(payload.get("recommended_command") or "")
    prompt = str(payload.get("recommended_prompt") or "")
    if command not in FOLLOWUP_EXECUTABLE_COMMANDS:
        return False, f"{command or '(empty)'} not allowlisted"
    execution_risk, execution_reason = followup_route_risk(command, prompt, str(payload.get("intent") or ""))
    effective_risk, _ = stricter_risk((str(action.get("risk") or "R2"), str(action.get("risk_reason") or "")), (execution_risk, execution_reason))
    if effective_risk in {"R3", "R4"}:
        declared = str(action.get("risk_reason") or action.get("risk") or "")
        reason = "; ".join(part for part in [declared, execution_reason] if part)
        return False, f"{effective_risk}: {reason}"
    return True, f"{effective_risk}: safe follow-up route"


def agent_inbox_snapshot() -> dict:
    running = [task for task in latest_tasks(limit=50) if task.get("status") in {"running", "running_background"}]
    stuck = stuck_tasks(limit=5)
    actions = pending_actions(limit=50)
    followups = [action for action in actions if action.get("type") == "followup_proposal"]
    improvements = open_improvements(limit=10)
    nudges = [row for row in latest_nudges(limit=20) if row.get("status", "open") in {"open", "sent"}]
    errors = error_rows(days=1)
    shortcut_tasks = shortcut_recent_tasks(limit=5)
    return {
        "running": running,
        "stuck": stuck,
        "pending_actions": actions,
        "followups": followups,
        "improvements": improvements,
        "nudges": nudges,
        "errors": errors,
        "shortcut_tasks": shortcut_tasks,
    }


def agent_inbox_items(snapshot: dict | None = None, limit: int = 12) -> list[dict]:
    snap = snapshot or agent_inbox_snapshot()
    items: list[dict] = []
    for task in snap["stuck"]:
        task_id = str(task.get("task_id") or "")
        if not task_id:
            continue
        items.append(
            {
                "priority": 105,
                "kind": "stuck_task",
                "id": task_id,
                "title": f"Task wygląda na stuck: {compact_line(str(task.get('prompt') or ''), 120)}",
                "next_action": f"/status {task_id}",
                "run_kind": "",
                "reason": "najpierw diagnoza/cancel, bez automatycznego wykonywania",
            }
        )
    for action in snap["pending_actions"]:
        action_id = str(action.get("action_id") or "")
        if not action_id:
            continue
        can_run, reason = followup_action_can_run(action)
        payload = action.get("payload") or {}
        route_preview = compact_line(f"{payload.get('recommended_command', '')} {payload.get('recommended_prompt', '')}".strip(), 140)
        is_followup = action.get("type") == "followup_proposal"
        items.append(
            {
                "priority": 92 if can_run else (84 if is_followup else 80),
                "kind": "followup" if is_followup else "approval",
                "id": action_id,
                "title": route_preview or compact_line(str(action.get("description") or action.get("type") or ""), 140),
                "next_action": f"/approve {action_id}" if not can_run else f"/agent run {action_id}",
                "run_kind": "approve_followup" if can_run else "",
                "reason": reason if is_followup else f"{action.get('risk', 'R?')} requires explicit approval",
            }
        )
    if snap["errors"]:
        latest_error = snap["errors"][-1]
        items.append(
            {
                "priority": 78,
                "kind": "error_audit",
                "id": str(latest_error.get("error_id") or "errors"),
                "title": f"{len(snap['errors'])} błędów w 24h: {compact_line(str(latest_error.get('context') or ''), 80)}",
                "next_action": "/recipe run error_audit_twice_daily",
                "run_kind": "recipe",
                "recipe": "error_audit_twice_daily",
                "recipe_input": "agent inbox",
                "reason": "scheduled loop może to obsłużyć, ale inbox może uruchomić audyt teraz",
            }
        )
    for item in snap["improvements"][:5]:
        improvement_id = str(item.get("improvement_id") or "")
        if not improvement_id:
            continue
        items.append(
            {
                "priority": priority_score(str(item.get("priority") or "P2")),
                "kind": "improvement",
                "id": improvement_id,
                "title": compact_line(str(item.get("title") or item.get("summary") or ""), 140),
                "next_action": f"/improve apply {improvement_id}",
                "run_kind": "improve_apply",
                "reason": f"{item.get('priority', 'P2')} open backlog item",
            }
        )
    for nudge in snap["nudges"][:5]:
        nudge_id = str(nudge.get("nudge_id") or nudge.get("action_id") or "")
        next_action = str(nudge.get("next_action") or "")
        items.append(
            {
                "priority": 58,
                "kind": str(nudge.get("kind") or "nudge"),
                "id": nudge_id,
                "title": compact_line(str(nudge.get("title") or nudge.get("summary") or ""), 140),
                "next_action": next_action or "/nudges",
                "run_kind": "",
                "reason": "existing proactive signal",
            }
        )
    for task in snap.get("shortcut_tasks", [])[:3]:
        task_id = str(task.get("task_id") or "")
        if not task_id:
            continue
        items.append(
            {
                "priority": 52,
                "kind": "iphone_capture",
                "id": task_id,
                "title": compact_line(str(task.get("prompt") or "iPhone Shortcut capture"), 140),
                "next_action": f"/details {task_id}",
                "run_kind": "",
                "reason": "recent iPhone Shortcut input",
            }
        )
    if not items:
        items.append(
            {
                "priority": 25,
                "kind": "evolution_loop",
                "id": "feature_evolution_loop",
                "title": "Brak pilnych pozycji; uruchom research kolejnej funkcji Poke/OpenClaw.",
                "next_action": "/recipe run feature_evolution_loop",
                "run_kind": "",
                "recipe": "feature_evolution_loop",
                "recipe_input": "agent inbox",
                "reason": "goal aktywny; uruchom ręcznie, jeśli chcesz kosztowną pętlę research/planning",
            }
        )
    return sorted(items, key=lambda item: int(item.get("priority") or 0), reverse=True)[:limit]


def format_agent_item(item: dict, index: int = 1) -> str:
    return (
        f"{index}. [{item.get('kind')}/{item.get('priority')}] {compact_line(str(item.get('title') or ''), 120)}\n"
        f"   id: {item.get('id')} | next: {item.get('next_action')} | reason: {compact_line(str(item.get('reason') or ''), 120)}"
    )


def start_agent_background_route(command: str, prompt: str, chat_id: str, source_id: str) -> str:
    route = route_text(f"{command} {prompt}".strip())
    if not route_should_background(route):
        return build_response(route, chat_id=chat_id)
    idempotency = f"agent:{source_id}:{command}:{prompt}"
    duplicate = find_recent_duplicate(idempotency, window_seconds=int_cfg("AI_COUNCIL_AGENT_IDEMPOTENCY_SECONDS", 600))
    if duplicate:
        return (
            "[Council] Agent run pominięty: podobny task już działa.\n"
            f"id: {duplicate.get('task_id')}\n"
            f"status: {duplicate.get('status')}\n"
            f"Progress: /progress {duplicate.get('task_id')}"
        )
    task = create_task(
        prompt or command,
        source="agent_inbox",
        status="queued",
        command=route.get("command", command),
        operators=route.get("operators", ["host"]),
        idempotency_key=idempotency,
        chat_id_hash=short_hash(chat_id),
    )
    return start_background_job({**route, "task_id": task["task_id"]}, chat_id=chat_id, task_id=task["task_id"], send_progress=True)


def agent_run_response(prompt: str = "", chat_id: str = "") -> str:
    chat_id = chat_id or cfg("TELEGRAM_ALLOWED_CHAT_ID")
    parts = prompt.strip().split(maxsplit=1)
    requested_id = parts[1].strip() if len(parts) > 1 and parts[0].lower() == "run" else ""
    items = agent_inbox_items(limit=20)
    if requested_id:
        matched = [item for item in items if str(item.get("id") or "") == requested_id]
        if not matched:
            return f"[Council] Agent run: nie znalazłem pozycji `{requested_id}` w bieżącym inboxie. Użyj /agent."
        items = matched
    runnable = next((item for item in items if item.get("run_kind")), None)
    if not runnable:
        top = items[0] if items else {}
        return (
            "[Council] Agent run: nie ma bezpiecznego automatycznego kroku.\n"
            f"DECYZJA: {compact_line(str(top.get('title') or 'Sprawdź inbox.'), 180)}\n"
            f"NEXT: {top.get('next_action', '/agent')}\n"
            "DO CIEBIE: użyj wskazanego approval/cancel/status; nie obejdę approval dla R3/R4."
        )
    if runnable.get("run_kind") == "approve_followup":
        return approve_response(str(runnable.get("id") or ""))
    if runnable.get("run_kind") == "improve_apply":
        improvement_id = str(runnable.get("id") or "")
        started = start_agent_background_route("/improve", f"apply {improvement_id}", chat_id, improvement_id)
        return f"[Council] Agent run: startuję plan improvementu `{improvement_id}`.\n{started}"
    if runnable.get("run_kind") == "recipe":
        recipe_name = str(runnable.get("recipe") or runnable.get("id") or "")
        recipe_input = str(runnable.get("recipe_input") or "agent inbox")
        started = start_agent_background_route("/recipe", f"run {recipe_name} {recipe_input}".strip(), chat_id, recipe_name)
        return f"[Council] Agent run: startuję recipe `{recipe_name}`.\n{started}"
    return f"[Council] Agent run: nieobsługiwany run_kind `{runnable.get('run_kind')}`. NEXT: {runnable.get('next_action')}"


def agent_response(prompt: str = "", chat_id: str = "") -> str:
    parts = prompt.strip().split(maxsplit=1)
    first = parts[0].lower() if parts else ""
    if first in {"run", "start", "odpal", "uruchom"}:
        normalized = "run " + parts[1].strip() if len(parts) > 1 else "run"
        return agent_run_response(normalized, chat_id=chat_id)
    snapshot = agent_inbox_snapshot()
    items = agent_inbox_items(snapshot, limit=8)
    top = items[0] if items else {}
    pending_runnable = sum(1 for item in items if item.get("run_kind"))
    lines = [
        "[Council] Agent Inbox L4.27",
        f"DECYZJA: {compact_line(str(top.get('title') or 'Brak pilnych spraw.'), 180)}",
        "FAKTY:",
        f"1. running={len(snapshot['running'])} stuck={len(snapshot['stuck'])} errors_24h={len(snapshot['errors'])}",
        f"2. pending_actions={len(snapshot['pending_actions'])} followups={len(snapshot['followups'])} improvements={len(snapshot['improvements'])}",
        f"3. nudges={len(snapshot['nudges'])} iphone_inputs={len(snapshot.get('shortcut_tasks', []))} safe_auto_candidates={pending_runnable}",
        "PRIORYTET:",
    ]
    for index, item in enumerate(items[:5], start=1):
        lines.append(format_agent_item(item, index=index))
    lines.append(f"NEXT: {top.get('next_action', '/agent')}")
    if top.get("run_kind"):
        lines.append(f"RUN: /agent run {top.get('id')}")
    else:
        lines.append("RUN: brak bezpiecznego auto-run dla top item; wymagany status/cancel/approval.")
    lines.append("DO CIEBIE: jeśli chcesz, wyślij `/agent run`; R3/R4 i external write nadal wymagają jawnego approval.")
    return "\n".join(lines)


def proactive_event_key(kind: str, target: str) -> str:
    return f"{today_utc()}:{kind}:{target}"


def proactive_event(
    kind: str,
    target: str,
    title: str,
    summary: str,
    next_action: str,
    *,
    severity: str = "info",
    action_id: str = "",
) -> dict:
    key = proactive_event_key(kind, target)
    return {
        "nudge_id": f"nudge-{datetime.now().strftime('%Y%m%d-%H%M%S')}-{short_hash(key)[:6]}",
        "nudge_key": key,
        "created_at": utc_now(),
        "kind": kind,
        "severity": severity,
        "status": "open",
        "title": compact_line(title, 180),
        "summary": compact_line(summary, 500),
        "next_action": compact_line(next_action, 180),
        "action_id": action_id,
    }


def detect_proactive_events() -> list[dict]:
    events: list[dict] = []
    recent_errors = error_rows(days=1)
    error_threshold = int_cfg("AI_COUNCIL_PROACTIVE_ERROR_THRESHOLD", 1)
    if len(recent_errors) >= error_threshold and recent_errors:
        latest_error = recent_errors[-1]
        events.append(
            proactive_event(
                "errors",
                str(latest_error.get("error_id") or len(recent_errors)),
                f"{len(recent_errors)} błędów w ostatnich 24h",
                f"Ostatni: {latest_error.get('context')} {latest_error.get('message')}",
                "/errors recent 10",
                severity="warning",
            )
        )

    for task in stuck_tasks(limit=int_cfg("AI_COUNCIL_PROACTIVE_STUCK_LIMIT", 3)):
        task_id = str(task.get("task_id") or "")
        if not task_id:
            continue
        events.append(
            proactive_event(
                "stuck_task",
                task_id,
                f"Task wygląda na stuck: {task_id}",
                f"{task.get('status')} | {compact_line(str(task.get('prompt') or ''), 180)}",
                f"/status {task_id}",
                severity="warning",
            )
        )

    action_threshold = int_cfg("AI_COUNCIL_ACTION_NUDGE_SECONDS", 1800)
    if action_threshold > 0:
        for action in latest_by_id(ACTIONS_FILE, "action_id", limit=20):
            action_id = str(action.get("action_id") or "")
            if not action_id or action.get("status") != "pending":
                continue
            if seconds_since(str(action.get("created_at", ""))) < action_threshold:
                continue
            events.append(
                proactive_event(
                    "pending_action",
                    action_id,
                    f"Akcja czeka na decyzję: {action_id}",
                    str(action.get("description") or action.get("type") or ""),
                    f"/approve {action_id} albo /deny {action_id}",
                    severity="info",
                    action_id=action_id,
                )
            )

    improvements = open_improvements(limit=1)
    if improvements:
        item = improvements[0]
        improvement_id = str(item.get("improvement_id") or "")
        if improvement_id:
            events.append(
                proactive_event(
                    "improvement",
                    improvement_id,
                    f"Następny improvement czeka: {compact_line(str(item.get('title') or ''), 120)}",
                    compact_line(str(item.get("summary") or ""), 240),
                    f"/improve apply {improvement_id}",
                    severity="info" if str(item.get("priority") or "P2").upper() != "P1" else "warning",
                )
            )

    grok_rows = [row for row in usage_today("grok") if row.get("status") != "blocked"]
    call_limit = int_cfg("GROK_DAILY_CALL_LIMIT", 0)
    budget = float_cfg("GROK_DAILY_BUDGET_USD", 0.0)
    thresholds = []
    if call_limit:
        thresholds.append(("calls", len(grok_rows) / call_limit))
    if budget:
        used = sum(float(row.get("estimated_usd") or 0.0) for row in usage_today("grok"))
        thresholds.append(("budget", used / budget))
    warn_ratio = float_cfg("AI_COUNCIL_PROACTIVE_COST_WARN_RATIO", 0.8)
    if thresholds:
        metric, ratio = max(thresholds, key=lambda item: item[1])
        if ratio >= warn_ratio:
            bucket = int(ratio * 10) * 10
            events.append(
                proactive_event(
                    "cost_guard",
                    f"grok:{metric}:{bucket}",
                    f"Grok usage przekroczył {int(warn_ratio * 100)}%",
                    f"Najwyższy wskaźnik: {metric}={ratio:.0%}",
                    "/cost",
                    severity="warning",
                )
            )
    return events


def send_proactive_nudge(chat_id: str, event: dict) -> bool:
    text = (
        "[Council] Proactive nudge\n"
        f"{event.get('title')}\n"
        f"summary: {event.get('summary')}\n"
        f"next: {event.get('next_action')}\n"
        "inbox: /nudges"
    )
    return telegram_send_message_with_markup(chat_id, text, response_reply_markup(text))


def run_proactive_scan(send: bool = False, chat_id: str = "") -> int:
    if not bool_cfg("AI_COUNCIL_PROACTIVE_EVENT_BRAIN", True):
        return 0
    if control_paused_reason("proactive"):
        return 0
    chat_id = chat_id or cfg("TELEGRAM_ALLOWED_CHAT_ID")
    existing = nudge_keys()
    created = 0
    for event in detect_proactive_events():
        key = str(event.get("nudge_key") or "")
        if not key or key in existing:
            continue
        sent = False
        if send and chat_id:
            sent = send_proactive_nudge(chat_id, event)
        append_jsonl(NUDGES_FILE, {**event, "status": "sent" if sent else "open", "sent_at": utc_now() if sent else ""})
        existing.add(key)
        created += 1
    return created


def maybe_send_action_nudges(chat_id: str, send: bool) -> int:
    if not chat_id or not send:
        return 0
    threshold = int_cfg("AI_COUNCIL_ACTION_NUDGE_SECONDS", 1800)
    if threshold <= 0:
        return 0
    already = nudged_ids()
    sent = 0
    for action in latest_by_id(ACTIONS_FILE, "action_id", limit=30):
        action_id = str(action.get("action_id") or "")
        if not action_id or action_id in already or action.get("status") != "pending":
            continue
        if seconds_since(str(action.get("created_at", ""))) < threshold:
            continue
        text = (
            "[Council] Nudge: akcja czeka na decyzję.\n"
            f"id: {action_id}\n"
            f"type: {action.get('type')}\n"
            f"preview: {compact_line(action.get('description', ''), 180)}"
        )
        if telegram_send_message_with_markup(chat_id, text, action_reply_markup(action_id)):
            append_jsonl(NUDGES_FILE, {"action_id": action_id, "created_at": utc_now(), "status": "sent"})
            sent += 1
    return sent


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
    if updated.get("type") == "workspace_write" and updated.get("risk") in AUTO_EXECUTABLE_WORKSPACE_RISKS:
        executed = execute_workspace_write_action(updated)
        if executed.get("status") == "executed":
            return f"[Council] Approved + executed: {executed['action_id']}.\n{executed.get('execution_result')}"
        return f"[Council] Approved, ale wykonanie zablokowane: {executed.get('execution_result')}"
    if updated.get("type") == "workspace_append" and updated.get("risk") in AUTO_EXECUTABLE_WORKSPACE_RISKS:
        executed = execute_workspace_append_action(updated)
        if executed.get("status") == "executed":
            return f"[Council] Approved + executed: {executed['action_id']}.\n{executed.get('execution_result')}"
        return f"[Council] Approved, ale wykonanie zablokowane: {executed.get('execution_result')}"
    if updated.get("type") == "workspace_patch" and updated.get("risk") in AUTO_EXECUTABLE_WORKSPACE_RISKS:
        executed = execute_workspace_patch_action(updated)
        if executed.get("status") == "executed":
            return f"[Council] Approved + executed: {executed['action_id']}.\n{executed.get('execution_result')}"
        return f"[Council] Approved, ale wykonanie zablokowane: {executed.get('execution_result')}"
    if updated.get("type") == "planner_proposal":
        payload = updated.get("payload") or {}
        task_id = str(payload.get("task_id") or "")
        route_preview = compact_line(
            f"{payload.get('recommended_command', '')} {payload.get('recommended_prompt', '')}".strip(),
            220,
        )
        next_line = f"Next: status {task_id}" if task_id else "Next: /actions"
        if task_id and updated.get("risk") in {"R0", "R1"}:
            next_line = f"Next: start {task_id}"
        return (
            f"[Council] Approved planner checkpoint: {updated['action_id']}.\n"
            "Nie wykonałem external write/send/publish. Approval zapisał decyzję i utrzymał audit trail.\n"
            f"route: {route_preview or '(none)'}\n"
            f"{next_line}"
        )
    if updated.get("type") == "integration_draft":
        payload = updated.get("payload") or {}
        missing = ", ".join(payload.get("missing_fields") or []) or "none"
        return (
            f"[Council] Approved integration draft checkpoint: {updated['action_id']}.\n"
            "Nie wykonałem external write/send/schedule/publish. Approval zapisał decyzję i utrzymał audit trail.\n"
            f"connector: {payload.get('connector')}\n"
            f"kind: {payload.get('draft_kind')}\n"
            f"missing_fields: {missing}\n"
            f"Preview: /drafts show {updated['action_id']}\n"
            "Next: ręczne wykonanie poza botem albo kolejna warstwa L4.29 z oddzielnym execution adapterem."
        )
    if updated.get("type") == "followup_proposal":
        payload = updated.get("payload") or {}
        command = str(payload.get("recommended_command") or "")
        prompt_text = str(payload.get("recommended_prompt") or "")
        route_preview = compact_line(f"{command} {prompt_text}".strip(), 220)
        if command not in FOLLOWUP_EXECUTABLE_COMMANDS:
            return (
                f"[Council] Approved follow-up checkpoint: {updated['action_id']}.\n"
                f"Nie uruchamiam route spoza allowlisty L4.17: {route_preview or '(none)'}."
            )
        execution_risk, execution_reason = followup_route_risk(command, prompt_text, str(payload.get("intent") or ""))
        effective_risk, _ = stricter_risk((str(updated.get("risk") or "R2"), str(updated.get("risk_reason") or "")), (execution_risk, execution_reason))
        if effective_risk in {"R3", "R4"}:
            return (
                f"[Council] Approved follow-up checkpoint: {updated['action_id']}.\n"
                "Nie wykonałem external write/send/schedule/publish. R3/R4 wymaga osobnej ścieżki approval/execution.\n"
                f"route: {route_preview or '(none)'}\n"
                f"risk: {effective_risk} ({execution_reason})"
            )
        route = {
            "command": command,
            "operators": operators_for_command(command),
            "prompt": prompt_text,
            "mode": "followup",
            "intent": "followup_runner",
            "followup_chain_id": payload.get("followup_chain_id", ""),
            "followup_depth": payload.get("followup_depth", 0),
        }
        chat_id = cfg("TELEGRAM_ALLOWED_CHAT_ID")
        if route_should_background(route):
            task = create_task(
                prompt_text or route_preview,
                source="followup_runner",
                status="queued",
                command=command,
                operators=route["operators"],
                idempotency_key=f"followup:{updated['action_id']}",
                chat_id_hash=short_hash(chat_id),
            )
            executed = {
                **updated,
                "status": "executed",
                "updated_at": utc_now(),
                "payload": {**payload, "launched_task_id": task["task_id"]},
                "execution_result": f"started follow-up task {task['task_id']}",
            }
            append_jsonl(ACTIONS_FILE, executed)
            started = start_background_job(route, chat_id=chat_id, task_id=task["task_id"], send_progress=True)
            return f"[Council] Approved + follow-up started: {updated['action_id']}.\n{started}"
        response = build_response(route, chat_id=chat_id)
        executed = {
            **updated,
            "status": "executed",
            "updated_at": utc_now(),
            "execution_result": compact_line(response, 500),
        }
        append_jsonl(ACTIONS_FILE, executed)
        return f"[Council] Approved + follow-up executed: {updated['action_id']}.\n{response}"
    return (
        f"[Council] Approved: {updated['action_id']}.\n"
        "Ta akcja nie ma automatycznego wykonania w L3.0."
    )


def deny_response(prompt: str) -> str:
    parts = prompt.strip().split(maxsplit=1)
    if not parts:
        return "[Council] Użyj: /deny <action_id>."
    updated = update_action_status(parts[0], "denied", parts[1] if len(parts) > 1 else "")
    if not updated:
        return f"[Council] Nie znalazłem action `{parts[0]}`."
    return f"[Council] Denied: {updated['action_id']}."


def execute_response(prompt: str) -> str:
    target_id = prompt.strip().split()[0] if prompt.strip() else ""
    if not target_id:
        return "[Council] Użyj: /execute <action_id>."
    action = get_latest_action(target_id)
    if not action:
        return f"[Council] Nie znalazłem action `{target_id}`."
    level, _ = normalize_risk(str(action.get("risk") or ""), action.get("description", ""))
    if level in {"R3", "R4"}:
        return f"[Council] Execute zablokowane przez Risk Officer: {level}. {risk_policy(level)}"
    if action.get("type") not in {"workspace_write", "workspace_append", "workspace_patch"}:
        return f"[Council] Execute nieobsługiwane dla `{action.get('type')}`. {risk_policy(level)}"
    return approve_response(target_id)


def format_verification_checks(checks: list[dict]) -> str:
    lines = []
    for check in checks:
        marker = "OK" if check.get("ok") else "FAILED"
        lines.append(f"- {marker}: {check.get('label')} - {check.get('detail')}")
    return "\n".join(lines)


def verify_action_result(action: dict) -> dict:
    payload = action.get("payload") or {}
    action_type = action.get("type")
    checks: list[dict] = []

    def add(label: str, ok: bool, detail: str) -> None:
        checks.append({"label": label, "ok": bool(ok), "detail": compact_line(detail, 220)})

    target, error = resolve_workspace_path(str(payload.get("path", "")))
    if error or target is None:
        add("workspace path", False, f"blocked: {error}")
        return {"ok": False, "detail": f"blocked: {error}", "checks": checks}
    add("workspace path", True, str(target))
    if action.get("status") == "rolled_back":
        before_exists = bool(payload.get("before_exists", False))
        before_content = str(payload.get("before_content", ""))
        if not before_exists:
            ok = not target.exists()
            add("rollback target removed", ok, "file removed" if ok else "file still exists")
            return {"ok": ok, "detail": "rollback verified: file removed" if ok else "rollback failed: file still exists", "checks": checks}
        if not target.exists():
            add("rollback target exists", False, "file missing")
            return {"ok": False, "detail": "rollback failed: file missing", "checks": checks}
        restored = target.read_text(encoding="utf-8", errors="replace") == before_content
        add("rollback content restored", restored, "before snapshot restored" if restored else "content differs from before snapshot")
        return {"ok": restored, "detail": "rollback verified: before snapshot restored" if restored else "rollback failed: content differs", "checks": checks}
    if action.get("status") not in {"executed", "verified", "verify_failed"}:
        add("action executed", False, f"status={action.get('status')}")
        return {"ok": False, "detail": f"not executed: {action.get('status')}", "checks": checks}
    add("action executed", True, f"status={action.get('status')}")
    if not target.exists():
        add("target exists", False, "target file missing")
        return {"ok": False, "detail": "target file missing", "checks": checks}
    add("target exists", True, str(target))
    current = target.read_text(encoding="utf-8", errors="replace")
    if action_type == "workspace_write":
        ok = current == str(payload.get("content", ""))
        add("write content", ok, "matches expected payload" if ok else "differs from expected payload")
        return {"ok": ok, "detail": "write content matches expected payload" if ok else "write content differs from expected payload", "checks": checks}
    if action_type == "workspace_append":
        expected = str(payload.get("before_content", "")) + str(payload.get("append_content", ""))
        ok = current == expected
        add("append content", ok, "matches before snapshot + appended text" if ok else "differs from expected append result")
        return {"ok": ok, "detail": "append content matches before snapshot + appended text" if ok else "append content differs from expected result", "checks": checks}
    if action_type == "workspace_patch":
        expected = str(payload.get("before_content", "")).replace(str(payload.get("old", "")), str(payload.get("new", "")), 1)
        ok = current == expected
        add("patch content", ok, "matches expected replacement" if ok else "differs from expected replacement")
        return {"ok": ok, "detail": "patch content matches expected replacement" if ok else "patch content differs from expected replacement", "checks": checks}
    add("action type", False, f"unsupported action type: {action_type}")
    return {"ok": False, "detail": f"unsupported action type: {action_type}", "checks": checks}


def verify_action(action: dict) -> tuple[bool, str]:
    result = verify_action_result(action)
    return bool(result.get("ok")), str(result.get("detail") or "")


def append_verification_event(action: dict, result: dict) -> dict:
    if action.get("status") not in {"executed", "verified", "verify_failed", "rolled_back"}:
        return action
    ok = bool(result.get("ok"))
    if action.get("status") == "rolled_back":
        status = "rolled_back"
    else:
        status = "verified" if ok else "verify_failed"
    verified = {
        **action,
        "status": status,
        "updated_at": utc_now(),
        "verified_at": utc_now(),
        "verification_status": "verified" if ok else "failed",
        "verification_result": str(result.get("detail") or ""),
        "verification_checks": result.get("checks") or [],
    }
    append_jsonl(ACTIONS_FILE, verified)
    return verified


def verify_response(prompt: str) -> str:
    target_id = prompt.strip().split()[0] if prompt.strip() else ""
    if not target_id:
        return "[Council] Użyj: /verify <action_id|task_id>."
    action = get_latest_action(target_id)
    if action:
        result = verify_action_result(action)
        ok = bool(result.get("ok"))
        detail = str(result.get("detail") or "")
        append_verification_event(action, result)
        status = "OK" if ok else "FAILED"
        checks = format_verification_checks(result.get("checks") or [])
        return f"[Verifier] {status}: {target_id}\n{detail}" + (f"\n{checks}" if checks else "")
    task = get_latest_task(target_id)
    if task:
        report_path = str(task.get("report_path") or "")
        report_exists = bool(report_path and Path(report_path).exists())
        if task.get("status") == "completed" and report_exists:
            return f"[Verifier] OK: {target_id}\ncompleted with report: {report_path}"
        return f"[Verifier] FAILED: {target_id}\nstatus={task.get('status')} report_exists={report_exists}"
    return f"[Verifier] Nie znalazłem action/task `{target_id}`."


def rollback_response(prompt: str) -> str:
    target_id = prompt.strip().split()[0] if prompt.strip() else ""
    if not target_id:
        return "[Council] Użyj: /rollback <action_id>."
    action = get_latest_action(target_id)
    if not action:
        return f"[Council] Nie znalazłem action `{target_id}`."
    if action.get("status") == "rolled_back":
        return f"[Council] Rollback pominięty: `{target_id}` już ma status rolled_back."
    if action.get("status") not in {"executed", "verified", "verify_failed"}:
        return f"[Council] Rollback wymaga executed/verified/verify_failed action, teraz: `{action.get('status')}`."
    if action.get("type") not in {"workspace_write", "workspace_append", "workspace_patch"}:
        return f"[Council] Rollback nieobsługiwany dla `{action.get('type')}`."
    payload = action.get("payload") or {}
    if "before_exists" not in payload or "before_content" not in payload:
        return "[Council] Rollback zablokowany: brak snapshotu sprzed wykonania."
    target, error = resolve_workspace_path(str(payload.get("path", "")))
    if error or target is None:
        return f"[Council] Rollback zablokowany: {error}"
    if payload.get("before_exists"):
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(str(payload.get("before_content", "")), encoding="utf-8")
        result = f"restored {target}"
    else:
        if target.exists():
            target.unlink()
        result = f"removed {target}"
    rolled_back = {
        **action,
        "status": "rolled_back",
        "updated_at": utc_now(),
        "rollback_result": result,
    }
    append_jsonl(ACTIONS_FILE, rolled_back)
    memory_save(
        f"workspace-rollback:{action.get('action_id')}",
        result,
        kind="action",
        agent="host",
        source="rollback",
        task_id=action.get("action_id", ""),
    )
    return f"[Council] Rollback executed: {target_id}.\n{result}"


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
        f"risk: {action.get('risk')}\n"
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
        f"risk: {action.get('risk')}\n"
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
        f"risk: {action.get('risk')}\n"
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


def first_meaningful_line(text: str, limit: int = 180) -> str:
    for raw in (text or "").splitlines():
        line = raw.strip(" -\t")
        if not line or (line.startswith("[") and line.endswith("]")) or line.startswith("#"):
            continue
        return compact_line(line, limit)
    return ""


def fallback_council_synthesis(clean_prompt: str, claude: str, grok: str, codex: str, task_id: str = "") -> dict:
    grok_facts = extract_fact_lines(grok, limit=3)
    claude_facts = extract_fact_lines(claude, limit=3)
    codex_facts = extract_fact_lines(codex, limit=3)
    facts = (grok_facts + claude_facts + codex_facts)[:3]
    if len(facts) < 3:
        facts.extend(
            [
                "Grok dostarczył research/red-team.",
                "Claude przygotował propozycję planu.",
                "Codex ocenił wykonalność i testowalność.",
            ][len(facts) : 3]
        )
    codex_next = codex_facts[0] if codex_facts else ""
    claude_next = claude_facts[0] if claude_facts else ""
    grok_signal = grok_facts[0] if grok_facts else first_meaningful_line(grok)
    claude_signal = claude_next or first_meaningful_line(claude)
    codex_signal = codex_next or first_meaningful_line(codex)
    decision_seed = codex_next or claude_next or facts[0]
    decision = f"Kontynuować od najmniejszego weryfikowalnego kroku: {compact_line(decision_seed, 180)}"
    dispute = (
        f"Grok: {compact_line(grok_signal or 'brak konkretnego sygnału', 120)} | "
        f"Claude: {compact_line(claude_signal or 'brak konkretnego planu', 120)} | "
        f"Codex: {compact_line(codex_signal or 'brak konkretnego patcha', 120)}"
    )
    next_actions = [
        f"Przejrzyj pełny raport: /details {task_id}" if task_id else "Przejrzyj pełny raport w artifacts.",
        compact_line(codex_signal or claude_signal or f"Doprecyzuj następny patch dla: {clean_prompt}", 220),
        "Jeśli krok ma skutki uboczne, przeprowadź go przez pending action i approval.",
    ]
    return {
        "decision": decision,
        "facts": facts,
        "dispute": dispute,
        "next_actions": next_actions,
        "ask_user": "Potwierdź pierwszy NEXT albo wskaż inny priorytet.",
        "synthesis_source": "fallback",
    }


def normalize_council_synthesis(parsed: dict, fallback: dict, task_id: str = "") -> dict:
    decision = compact_line(str(parsed.get("decision") or fallback["decision"]), 500)
    raw_facts = parsed.get("facts")
    facts = [compact_line(str(item), 220) for item in raw_facts if str(item).strip()] if isinstance(raw_facts, list) else []
    if not facts:
        facts = fallback["facts"]
    raw_next = parsed.get("next_actions")
    next_actions = [compact_line(str(item), 240) for item in raw_next if str(item).strip()] if isinstance(raw_next, list) else []
    if not next_actions:
        next_actions = fallback["next_actions"]
    if task_id and not any(f"/details {task_id}" in action for action in next_actions):
        next_actions.insert(0, f"Przejrzyj pełny raport: /details {task_id}")
    return {
        "decision": decision,
        "facts": facts[:8],
        "dispute": compact_line(str(parsed.get("dispute") or fallback["dispute"]), 500),
        "next_actions": next_actions[:8],
        "ask_user": compact_line(str(parsed.get("ask_user") or fallback["ask_user"]), 300),
        "synthesis_source": "llm_host",
    }


def council_host_synthesis(clean_prompt: str, host_brief: str, claude: str, grok: str, codex: str, task_id: str = "") -> dict:
    fallback = fallback_council_synthesis(clean_prompt, claude, grok, codex, task_id=task_id)
    if not bool_cfg("AI_COUNCIL_COUNCIL_HOST_SYNTHESIS", bool(cfg("XAI_API_KEY"))) or not cfg("XAI_API_KEY"):
        return fallback
    prompt = (
        "Jesteś hostem i sędzią AI Council dla Bartka. Masz rozstrzygnąć trzy głosy: Claude, Grok i Codex. "
        "Zwróć wyłącznie JSON bez markdown w formacie: "
        '{"decision":"...","facts":["..."],"dispute":"...","next_actions":["..."],"ask_user":"..."}.\n'
        "Decyzja musi wynikać z treści głosów. Nie twierdź, że wykonano kod lub akcje zewnętrzne. "
        "Preferuj najmniejszy testowalny następny krok i oznacz ryzyka.\n\n"
        f"Host brief:\n{host_brief}\n\n"
        f"Claude propose:\n{claude[:2500]}\n\n"
        f"Grok research/red-team:\n{grok[:2500]}\n\n"
        f"Codex feasibility:\n{codex[:2500]}"
    )
    response = grok_route_response(prompt, max_chars=int_cfg("AI_COUNCIL_COUNCIL_SYNTHESIS_MAX_CHARS", 2500), task_id=task_id)
    parsed = extract_json_object(response)
    if not parsed:
        fallback["synthesis_source"] = "fallback_no_json"
        return fallback
    return normalize_council_synthesis(parsed, fallback, task_id=task_id)


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
    synthesis = council_host_synthesis(clean_prompt, host_brief, claude, grok, codex, task_id=task_id)
    facts = synthesis["facts"]
    next_actions = synthesis["next_actions"]
    decision = synthesis["decision"]
    dispute = synthesis["dispute"]
    ask_user = synthesis["ask_user"]
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
        + f"\n\nSynthesis source: {synthesis.get('synthesis_source', 'unknown')}\n"
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
    if command == "/recipe":
        return run_recipe_background(str(route.get("prompt", "")), task_id=task_id)
    if command == "/improve":
        return run_improve_background(str(route.get("prompt", "")), task_id=task_id)
    if command in FRONT_OPERATOR_COMMANDS:
        raw = raw_operator_response(command, str(route.get("prompt", "")), task_id=task_id)
        summary = front_operator_response(command, raw, task_id=task_id)
        facts = extract_fact_lines(strip_operator_label(raw), limit=3)
        return {
            "decision": front_operator_title(command, raw) + ".",
            "status": "failed" if operator_failed(raw) else "completed",
            "facts": facts or ["Operator zwrócił wynik zapisany w szczegółach."],
            "dispute": "Host ukrył surowy prefiks operatora w Telegramie; raw output zostaje w artifacts.",
            "next_actions": default_next_actions(task_id, command),
            "ask_user": "Sprawdź wynik i zdecyduj, czy mam kontynuować.",
            "raw_output": raw,
            "report": raw,
            "summary": summary,
        }
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
    heartbeat = None
    try:
        if is_cancelled_id(task_id):
            update_task_status(task_id, "cancelled", "background worker cancelled before run", worker_pid=pid)
            append_background_job_event({"job_id": f"bg-{task_id}", "task_id": task_id, "updated_at": utc_now(), "status": "cancelled", "pid": pid})
            append_progress_event(task_id, route, "CANCELLED", "cancelled before run")
            if send_progress and chat_id:
                telegram_send_message(chat_id, background_progress_message(task_id, route, "CANCELLED"))
            return 0
        append_progress_event(task_id, route, "PREPARING", "worker booted")
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
        append_progress_event(task_id, route, "RUNNING", "worker działa")
        if send_running and chat_id:
            telegram_send_message_with_markup(
                chat_id,
                background_progress_message(task_id, route, "RUNNING", "worker działa"),
                task_reply_markup(task_id),
            )
        heartbeat = start_progress_heartbeat(task_id, route, chat_id, send_progress, started)
        result = execute_route_for_background(route, chat_id, task_id)
        stop_progress_heartbeat(heartbeat)
        heartbeat = None
        append_progress_event(task_id, route, "COLLECTING", "operator returned; saving artifacts")
        send_intermediate = send_progress and chat_id and should_send_intermediate_progress(started)
        if send_intermediate:
            telegram_send_message_with_markup(
                chat_id,
                background_progress_message(task_id, route, "COLLECTING", "zapisuję wynik i artefakty"),
                task_reply_markup(task_id),
            )
        artifact = save_task_artifacts(task_id, route, result)
        duration_ms = int((time.time() - started) * 1000)
        result_status = str(result.get("status") or "")
        if is_cancelled_id(task_id):
            update_task_status(task_id, "cancelled", "background worker cancelled after artifact write", duration_ms=duration_ms, report_path=artifact.get("report_path"))
            append_background_job_event({"job_id": f"bg-{task_id}", "task_id": task_id, "updated_at": utc_now(), "status": "cancelled", "pid": pid})
            append_progress_event(task_id, route, "CANCELLED", "cancelled after artifact write")
            if send_progress and chat_id:
                telegram_send_message(chat_id, background_progress_message(task_id, route, "CANCELLED"))
            return 0
        if result_status in {"blocked", "failed"}:
            update_task_status(
                task_id,
                "failed",
                f"background worker {result_status}",
                duration_ms=duration_ms,
                report_path=artifact.get("report_path"),
                summary_path=artifact.get("summary_path"),
            )
            append_background_job_event(
                {
                    "job_id": f"bg-{task_id}",
                    "task_id": task_id,
                    "updated_at": utc_now(),
                    "status": "failed",
                    "pid": pid,
                    "duration_ms": duration_ms,
                    "report_path": artifact.get("report_path"),
                }
            )
            append_progress_event(task_id, route, "FAILED", f"background worker {result_status}", percent=100)
            if send_progress and chat_id:
                telegram_send_message_with_markup(chat_id, artifact.get("summary", ""), task_delivery_reply_markup(task_id))
            return 1
        append_progress_event(task_id, route, "DELIVERING", "final summary ready")
        if send_intermediate:
            telegram_send_message_with_markup(
                chat_id,
                background_progress_message(task_id, route, "DELIVERING", "wysyłam finalne podsumowanie"),
                task_reply_markup(task_id),
            )
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
        append_progress_event(task_id, route, "COMPLETED", f"duration_ms={duration_ms}", percent=100)
        if send_progress and chat_id:
            telegram_send_message_with_markup(chat_id, artifact.get("summary", ""), task_delivery_reply_markup(task_id))
        return 0
    except Exception as exc:
        stop_progress_heartbeat(heartbeat)
        heartbeat = None
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
        append_progress_event(task_id, route, "FAILED", error, percent=100)
        if send_progress and chat_id:
            telegram_send_message(chat_id, background_progress_message(task_id, route, "FAILED", error))
        return 1
    finally:
        stop_progress_heartbeat(heartbeat)


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


def request_form_json(url: str, fields: dict[str, str], *, timeout: int = 20) -> dict:
    body = urlencode(fields).encode("utf-8")
    req = Request(
        url,
        data=body,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        method="POST",
    )
    try:
        with urlopen(req, timeout=timeout) as res:
            data = json.loads(res.read().decode("utf-8", errors="replace"))
            if isinstance(data, dict):
                data.setdefault("ok", True)
                return data
            return {"ok": False, "error": "invalid_json_shape"}
    except HTTPError as exc:
        body_preview = redact_secrets(exc.read().decode("utf-8", errors="replace"))[:500]
        return {"ok": False, "error": f"http_{exc.code}", "body_preview": body_preview}
    except URLError as exc:
        return {"ok": False, "error": "url_error", "reason": str(exc.reason)}
    except TimeoutError:
        return {"ok": False, "error": "timeout"}
    except json.JSONDecodeError:
        return {"ok": False, "error": "invalid_json"}


def request_multipart_json(
    url: str,
    *,
    headers: dict[str, str] | None = None,
    fields: list[tuple[str, str]] | None = None,
    file_field: str,
    file_path: Path,
    mime_type: str = "application/octet-stream",
    timeout: int = 180,
) -> dict:
    boundary = f"ai-council-{short_hash(str(time.time()))}"
    body = bytearray()
    for key, value in fields or []:
        body.extend(f"--{boundary}\r\n".encode("utf-8"))
        body.extend(f'Content-Disposition: form-data; name="{key}"\r\n\r\n'.encode("utf-8"))
        body.extend(str(value).encode("utf-8"))
        body.extend(b"\r\n")
    filename = safe_filename(file_path.name, "audio")
    body.extend(f"--{boundary}\r\n".encode("utf-8"))
    body.extend(
        f'Content-Disposition: form-data; name="{file_field}"; filename="{filename}"\r\n'.encode("utf-8")
    )
    body.extend(f"Content-Type: {mime_type or 'application/octet-stream'}\r\n\r\n".encode("utf-8"))
    body.extend(file_path.read_bytes())
    body.extend(b"\r\n")
    body.extend(f"--{boundary}--\r\n".encode("utf-8"))
    final_headers = headers.copy() if headers else {}
    final_headers["Content-Type"] = f"multipart/form-data; boundary={boundary}"
    req = Request(url, data=bytes(body), headers=final_headers, method="POST")
    try:
        with urlopen(req, timeout=timeout) as res:
            return json.loads(res.read().decode("utf-8", errors="replace"))
    except HTTPError as exc:
        body_preview = redact_secrets(exc.read().decode("utf-8", errors="replace"))[:500]
        return {"ok": False, "error": f"http_{exc.code}", "body_preview": body_preview}
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
    return telegram_send_message_with_markup(chat_id, text)


def telegram_send_message_with_markup(chat_id: str, text: str, reply_markup: dict | None = None) -> bool:
    ok = True
    chunks = split_telegram_text(text)
    for index, chunk in enumerate(chunks, start=1):
        payload = {
            "chat_id": chat_id,
            "text": chunk,
            "disable_web_page_preview": True,
        }
        if reply_markup and index == 1:
            payload["reply_markup"] = reply_markup
        data = request_json(telegram_url("sendMessage"), method="POST", payload=payload)
        if not data.get("ok"):
            print(f"telegram_sendMessage=failed {data.get('error') or data.get('description')}")
            record_error(
                "telegram_sendMessage",
                message=str(data.get("error") or data.get("description") or data.get("body_preview") or "send failed"),
                event={"chat_id_hash": short_hash(str(chat_id)), "chunk": index, "chunks": len(chunks)},
                severity="warning",
            )
            ok = False
            continue
        if len(chunks) > 1:
            print(f"telegram_sendMessage=ok chunk={index}/{len(chunks)}")
        else:
            print("telegram_sendMessage=ok")
    return ok


def telegram_answer_callback_query(callback_query_id: str, text: str = "") -> bool:
    payload = {"callback_query_id": callback_query_id}
    if text:
        payload["text"] = compact_line(text, 180)
    data = request_json(telegram_url("answerCallbackQuery"), method="POST", payload=payload)
    return bool(data.get("ok"))


def telegram_edit_message_reply_markup(chat_id: str, message_id: str) -> bool:
    payload = {"chat_id": chat_id, "message_id": message_id, "reply_markup": {"inline_keyboard": []}}
    data = request_json(telegram_url("editMessageReplyMarkup"), method="POST", payload=payload)
    return bool(data.get("ok"))


def inline_keyboard(button_rows: list[list[tuple[str, str]]]) -> dict:
    return {
        "inline_keyboard": [
            [{"text": label, "callback_data": data} for label, data in row]
            for row in button_rows
        ]
    }


def action_reply_markup(action_id: str) -> dict:
    return inline_keyboard(
        [
            [("Zatwierdź", f"approve:{action_id}"), ("Anuluj", f"deny:{action_id}")],
            [("Popraw", f"edit:{action_id}"), ("Actions", "actions:latest")],
        ]
    )


def task_reply_markup(task_id: str) -> dict:
    return inline_keyboard(
        [
            [("Status", f"status:{task_id}"), ("Details", f"details:{task_id}")],
            [("Cancel", f"cancel:{task_id}")],
        ]
    )


def task_delivery_reply_markup(task_id: str) -> dict:
    return inline_keyboard(
        [
            [("Status", f"status:{task_id}"), ("Details", f"details:{task_id}")],
            [("Facts", f"facts:{task_id}"), ("Next", f"next:{task_id}")],
            [("Actions", "actions:latest")],
        ]
    )


def response_reply_markup(response: str) -> dict | None:
    action_match = re.search(r"\bid:\s*(act-[A-Za-z0-9_.-]+)", response or "")
    if action_match and "Pending" in response:
        return action_reply_markup(action_match.group(1))
    task_match = re.search(r"\b(task-[0-9]{8}-[0-9]{6}-[A-Za-z0-9]+)", response or "")
    if task_match:
        task_id = task_match.group(1)
        if "DECYZJA:" in (response or "") or f"Details: /details {task_id}" in (response or ""):
            return task_delivery_reply_markup(task_id)
        return task_reply_markup(task_id)
    return None


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


def normalize_intent_text(text: str) -> str:
    return re.sub(r"\s+", " ", text.lower()).strip(" \t\r\n?!.,")


LLM_ROUTER_ALLOWED_COMMANDS = {
    "/chat",
    "/front",
    "/plan-action",
    "@research",
    "/xresearch",
    "/flow",
    "/council",
    "/task",
    "/agent",
    "/shortcuts",
    "/drafts",
    "/status",
    "/progress",
    "/details",
    "/facts",
    "/next",
    "/cost",
    "/control",
    "/errors",
    "/improvements",
    "/loops",
    "/recipes",
    "/recipe",
    "/goal",
    "/nudges",
    "/sources",
    "/source",
    "/connectors",
    "/connector",
    "/project-memory",
}


def llm_router_enabled() -> bool:
    return bool_cfg("AI_COUNCIL_LLM_ROUTER", False)


def llm_router_should_try(text: str) -> bool:
    if not llm_router_enabled() or not cfg("XAI_API_KEY"):
        return False
    clean = normalize_intent_text(text)
    if not clean:
        return False
    triggers = [
        "z tego",
        "teraz",
        "kontynuuj",
        "co dalej",
        "ogarnij",
        "sprawdz",
        "sprawdź",
        "poszukaj",
        "zbadaj",
        "research",
        "plan",
        "zaplanuj",
        "przygotuj",
        "podsumuj",
        "znajdz",
        "znajdź",
        "kalendarz",
        "gmail",
        "drive",
        "github",
        "źródł",
        "zrodl",
        "pamięć",
        "pamiec",
        "poke",
    ]
    return any(marker in clean for marker in triggers)


def extract_json_object(text: str) -> dict | None:
    raw = (text or "").strip()
    if not raw:
        return None
    if raw.startswith("```"):
        raw = re.sub(r"^```(?:json)?", "", raw.strip(), flags=re.IGNORECASE).strip()
        raw = re.sub(r"```$", "", raw).strip()
    start = raw.find("{")
    end = raw.rfind("}")
    if start >= 0 and end > start:
        raw = raw[start : end + 1]
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return None
    return parsed if isinstance(parsed, dict) else None


def llm_route(text: str, chat_id: str = "") -> dict | None:
    clean_text = text.strip()
    if not clean_text or not llm_router_should_try(clean_text):
        return None
    allowed, reason, reservation = reserve_operator_call("grok", detail="llm_router")
    if not allowed:
        return None
    history = recent_conversation(chat_id, limit=int_cfg("AI_COUNCIL_LLM_ROUTER_HISTORY_TURNS", 6)) if chat_id else []
    history_lines = [
        f"{row.get('role')}: {compact_line(str(row.get('text') or ''), 220)}"
        for row in history
        if row.get("text")
    ]
    system_prompt = (
        "Jesteś bezpiecznym routerem intencji dla prywatnego Telegram AI Council Bartka. "
        "Zwracasz wyłącznie JSON bez markdown: "
        '{"command": "...", "prompt": "...", "confidence": 0.0, "reason": "..."}.\n'
        "Dozwolone command: /chat, /plan-action, @research, /xresearch, /flow, /council, /task, /agent, /shortcuts, /drafts, /status, /progress, /details, /facts, /next, /cost, /control, /errors, /improvements, /followups, /loops, /recipes, /recipe, /goal, /nudges, /sources, /source, /connectors, /connector, /project-memory.\n"
        "Nigdy nie wybieraj write/append/patch/execute/rollback/approve/deny/delete/publish/contact/billing/auth/DNS. "
        "Dla destrukcyjnych lub zewnętrznych próśb wybierz /chat i krótko wyjaśnij potrzebę approval. "
        "Dla zwykłego small talku wybierz /chat. Dla live research wybierz @research lub /xresearch. "
        "Dla dużych planów wybierz /flow. Dla multi-agent decyzji wybierz /council. "
        "Dla follow-upów typu 'z tego', 'teraz plan', użyj historii rozmowy."
    )
    user_prompt = (
        "Historia rozmowy:\n"
        + ("\n".join(history_lines[-6:]) if history_lines else "brak")
        + "\n\nWiadomość:\n"
        + clean_text
    )
    payload = {
        "model": cfg("AI_COUNCIL_LLM_ROUTER_MODEL", cfg("AI_COUNCIL_GROK_MODEL", "grok-4.3")),
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "stream": False,
    }
    data = request_json(
        "https://api.x.ai/v1/chat/completions",
        headers={"Authorization": f"Bearer {cfg('XAI_API_KEY')}"},
        method="POST",
        payload=payload,
        timeout=int_cfg("AI_COUNCIL_LLM_ROUTER_TIMEOUT", 20),
    )
    if data.get("ok") is False:
        finalize_operator_call(reservation, status="failed", duration_ms=0, detail="llm_router failed")
        record_error("llm_router", message=str(data.get("error") or data.get("body_preview") or "router failed"), severity="warning")
        return None
    try:
        content = data["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError):
        finalize_operator_call(reservation, status="failed", duration_ms=0, detail="llm_router invalid response")
        return None
    finalize_operator_call(reservation, status="completed", duration_ms=0, detail="llm_router")
    parsed = extract_json_object(str(content))
    if not parsed:
        return None
    command = str(parsed.get("command") or "").strip()
    try:
        confidence = float(parsed.get("confidence") or 0.0)
    except (TypeError, ValueError):
        confidence = 0.0
    if command not in LLM_ROUTER_ALLOWED_COMMANDS or confidence < float_cfg("AI_COUNCIL_LLM_ROUTER_MIN_CONF", 0.6):
        return None
    prompt = str(parsed.get("prompt") or clean_text).strip() or clean_text
    route = route_text(f"{command} {prompt}" if command.startswith("/") else f"{command} {prompt}")
    if route.get("command") != command:
        return None
    route["route_source"] = "llm"
    route["confidence"] = confidence
    route["route_reason"] = compact_line(str(parsed.get("reason") or ""), 220)
    return route


def natural_intent_route(stripped: str, lower: str) -> dict | None:
    if not stripped or stripped.startswith(("@", "/")):
        return None
    lower = normalize_intent_text(lower)

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

    progress_prefixes = ["progress ", "postęp ", "postep ", "pokaż progress ", "pokaz progress ", "pokaż postęp ", "pokaz postep ", "gdzie jest "]
    if lower in {"progress", "postęp", "postep"}:
        return {"command": "/progress", "operators": ["host"], "prompt": "", "mode": "progress", "intent": "natural"}
    if any(lower.startswith(prefix) for prefix in progress_prefixes):
        return {
            "command": "/progress",
            "operators": ["host"],
            "prompt": strip_intent_prefix(stripped, progress_prefixes),
            "mode": "progress",
            "intent": "natural",
        }

    if lower in {"health", "zdrowie", "diagnostyka", "czy system zdrowy"} or lower.startswith(
        ("pokaż health", "pokaz health", "sprawdź health", "sprawdz health")
    ):
        return {"command": "/health", "operators": ["host"], "prompt": "", "mode": "health", "intent": "natural"}

    if lower in {"front", "front status", "front reliability", "czemu nie odpowiada", "dlaczego nie odpowiada", "bot nie odpowiada"} or lower.startswith(
        ("pokaż front", "pokaz front", "sprawdź front", "sprawdz front", "czemu bot nie odpowiada", "dlaczego bot nie odpowiada")
    ):
        return {"command": "/front", "operators": ["host"], "prompt": stripped, "mode": "front", "intent": "natural"}

    if lower in {"selftest", "self test", "test systemu", "sprawdź wszystko", "sprawdz wszystko"} or lower.startswith(
        ("pokaż selftest", "pokaz selftest", "uruchom selftest")
    ):
        return {"command": "/selftest", "operators": ["host"], "prompt": "", "mode": "selftest", "intent": "natural"}

    if lower in {"co umiesz", "co potrafisz", "co możesz", "co mozesz", "capabilities", "możliwości", "mozliwosci"} or lower.startswith(
        ("pokaż możliwości", "pokaz mozliwosci", "pokaż capabilities", "pokaz capabilities", "jak działasz", "jak dzialasz", "jak dziś działasz", "jak dzis dzialasz")
    ):
        return {"command": "/capabilities", "operators": ["host"], "prompt": "", "mode": "capabilities", "intent": "natural"}

    if lower in {"goal", "cel", "jaki jest cel", "gdzie cel", "gdzie jest cel", "poke parity"} or (
        "nie odpowiada" in lower and "poke" in lower
    ) or (
        "nie ma takich" in lower and "możliwo" in lower
    ) or (
        "nie ma takich" in lower and "mozliwo" in lower
    ) or any(
        marker in lower
        for marker in (
            "gdzie ten cel",
            "jaki jest goal",
            "nasz goal",
            "nie odpowiada jak poke",
            "nie jest jak poke",
            "brakuje do poke",
            "poke-level",
            "poke like",
            "poke-like",
        )
    ):
        return {"command": "/goal", "operators": ["host"], "prompt": stripped, "mode": "goal", "intent": "natural"}

    if lower in {"koszty", "cost", "costs", "usage", "zużycie", "zuzycie"} or lower.startswith(
        ("pokaż koszty", "pokaz koszty", "pokaż usage", "pokaz usage")
    ):
        return {"command": "/cost", "operators": ["host"], "prompt": "", "mode": "cost", "intent": "natural"}

    if lower in {"control", "kontrola", "kill switch", "budget guard", "guard", "limity"} or lower.startswith(
        ("pokaż kontrolę", "pokaz kontrole", "pokaż control", "pokaz control", "pokaż limity", "pokaz limity")
    ):
        return {"command": "/control", "operators": ["host"], "prompt": "status", "mode": "control", "intent": "natural"}

    if lower in {"błędy", "bledy", "errors", "error log", "log błędów", "log bledow"} or lower.startswith(
        ("pokaż błędy", "pokaz bledy", "pokaż errors", "pokaz errors", "sprawdź błędy", "sprawdz bledy")
    ):
        return {"command": "/errors", "operators": ["host"], "prompt": "recent", "mode": "errors", "intent": "natural"}

    if lower in {"nudges", "nudge", "proaktywne", "proaktywne sygnały", "proaktywne sygnaly"} or lower.startswith(
        ("pokaż nudges", "pokaz nudges", "pokaż nudge", "pokaz nudge", "pokaż proaktywne", "pokaz proaktywne")
    ):
        return {"command": "/nudges", "operators": ["host"], "prompt": "", "mode": "nudges", "intent": "natural"}

    if lower in {
        "agent",
        "agent inbox",
        "inbox",
        "centrum dowodzenia",
        "co dalej",
        "co teraz",
        "co mam zrobić",
        "co mam zrobic",
        "czym się zająć",
        "czym sie zajac",
        "jaki następny krok",
        "jaki nastepny krok",
    } or lower.startswith(
        ("pokaż agent", "pokaz agent", "pokaż inbox", "pokaz inbox", "agent status", "agent next", "operator status")
    ):
        return {"command": "/agent", "operators": ["host"], "prompt": "", "mode": "agent", "intent": "natural"}

    if lower in {"shortcuts", "iphone shortcuts", "ios shortcuts", "skrót iphone", "skrot iphone", "skróty iphone", "skroty iphone", "iphone inbox"} or lower.startswith(
        ("pokaż shortcuts", "pokaz shortcuts", "pokaż skróty", "pokaz skroty", "pokaż iphone", "pokaz iphone", "sprawdź shortcuts", "sprawdz shortcuts")
    ):
        return {"command": "/shortcuts", "operators": ["host"], "prompt": "", "mode": "shortcuts", "intent": "natural"}

    if lower in {"drafty", "drafts", "integration drafts", "drafty integracji"} or lower.startswith(
        ("pokaż drafty", "pokaz drafty", "pokaż drafts", "pokaz drafts", "pokaż integration drafts", "pokaz integration drafts")
    ):
        return {"command": "/drafts", "operators": ["host"], "prompt": "", "mode": "drafts", "intent": "natural"}

    if lower in {"źródła", "zrodla", "sources", "integracje", "integrations"} or lower.startswith(
        ("pokaż źródła", "pokaz zrodla", "pokaż sources", "pokaz sources", "pokaż integracje", "pokaz integracje")
    ):
        return {"command": "/sources", "operators": ["host"], "prompt": "", "mode": "sources", "intent": "natural"}

    if lower in {"connectors", "konektory", "połączenia", "polaczenia", "podłączenia", "podlaczenia"} or lower.startswith(
        ("pokaż connectors", "pokaz connectors", "pokaż konektory", "pokaz konektory", "pokaż połączenia", "pokaz polaczenia")
    ):
        return {"command": "/connectors", "operators": ["host"], "prompt": "", "mode": "connectors", "intent": "natural"}

    connector_prefixes = ["sprawdź connector", "sprawdz connector", "sprawdź konektor", "sprawdz konektor"]
    if any(lower.startswith(prefix) for prefix in connector_prefixes):
        return {
            "command": "/connector",
            "operators": ["host"],
            "prompt": "check " + strip_intent_prefix(stripped, connector_prefixes),
            "mode": "connector",
            "intent": "natural",
        }

    connector_auth_prefixes = ["podłącz connector", "podlacz connector", "podłącz konektor", "podlacz konektor", "podłącz github", "podlacz github"]
    if any(lower.startswith(prefix) for prefix in connector_auth_prefixes):
        prompt = strip_intent_prefix(stripped, connector_auth_prefixes) or ("github" if "github" in lower else "")
        return {
            "command": "/connector",
            "operators": ["host"],
            "prompt": "auth " + prompt,
            "mode": "connector_auth",
            "intent": "natural",
        }

    connector_draft_prefixes = [
        ("draft gmail", "gmail"),
        ("draft mail", "gmail"),
        ("draft email", "gmail"),
        ("szkic mail", "gmail"),
        ("szkic email", "gmail"),
        ("draft calendar", "calendar"),
        ("draft kalendarz", "calendar"),
        ("draft drive", "drive"),
        ("draft docs", "drive"),
        ("draft github", "github"),
    ]
    for prefix, name in connector_draft_prefixes:
        if lower.startswith(prefix):
            intent = stripped[len(prefix) :].strip(" :,-")
            return {
                "command": "/connector",
                "operators": ["host"],
                "prompt": f"draft {name} {intent}".strip(),
                "mode": "connector_draft",
                "intent": "natural",
            }

    connector_sync_prefixes = [
        ("sync gmail", "gmail"),
        ("sync mail", "gmail"),
        ("zsynchronizuj gmail", "gmail"),
        ("zsynchronizuj mail", "gmail"),
        ("sync calendar", "calendar"),
        ("sync kalendarz", "calendar"),
        ("zsynchronizuj calendar", "calendar"),
        ("zsynchronizuj kalendarz", "calendar"),
        ("sync drive", "drive"),
        ("sync google drive", "drive"),
        ("zsynchronizuj drive", "drive"),
        ("zsynchronizuj google drive", "drive"),
    ]
    for prefix, name in connector_sync_prefixes:
        if lower.startswith(prefix):
            query = stripped[len(prefix) :].strip(" :,-")
            return {
                "command": "/connector",
                "operators": ["host"],
                "prompt": f"sync {name} {query}".strip(),
                "mode": "connector_sync",
                "intent": "natural",
            }

    source_search_prefixes = ["szukaj w źródłach", "szukaj w zrodlach", "source search", "search sources"]
    if any(lower.startswith(prefix) for prefix in source_search_prefixes):
        return {
            "command": "/source",
            "operators": ["host"],
            "prompt": "search " + strip_intent_prefix(stripped, source_search_prefixes),
            "mode": "source_search",
            "intent": "natural",
        }

    if lower in {"ulepszenia", "improvements", "backlog", "co wdrażać", "co wdrazac", "co wdrożyć", "co wdrozyc"} or lower.startswith(
        ("pokaż ulepszenia", "pokaz ulepszenia", "pokaż backlog", "pokaz backlog", "następne wdrożenie", "nastepne wdrozenie")
    ):
        return {"command": "/improvements", "operators": ["host"], "prompt": "", "mode": "improvements", "intent": "natural"}

    if lower in {"followups", "follow-ups", "follow upy", "follow-upy"} or lower.startswith(
        ("pokaż followups", "pokaz followups", "pokaż follow-upy", "pokaz follow-upy", "pokaż follow upy", "pokaz follow upy")
    ):
        return {"command": "/followups", "operators": ["host"], "prompt": "", "mode": "followups", "intent": "natural"}

    if lower in {"loops", "pętle", "petle", "autonomiczne pętle", "autonomiczne petle"} or lower.startswith(
        ("pokaż pętle", "pokaz petle", "pokaż loops", "pokaz loops", "sprawdź pętle", "sprawdz petle")
    ):
        return {"command": "/loops", "operators": ["host"], "prompt": "", "mode": "loops", "intent": "natural"}

    start_task_prefixes = ["start task-", "uruchom task-", "odpal task-"]
    if any(lower.startswith(prefix) for prefix in start_task_prefixes):
        prompt = stripped
        for prefix in start_task_prefixes:
            if lower.startswith(prefix):
                prompt = "task-" + stripped[len(prefix) :].strip(" :,-")
                break
        return {
            "command": "/start-task",
            "operators": ["host"],
            "prompt": prompt,
            "mode": "start_task",
            "intent": "natural",
        }

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

    if lower in {"pamięć projektu", "pamiec projektu", "project memory", "project-memory", "spine", "memory spine"} or lower.startswith(
        ("pokaż pamięć projektu", "pokaz pamiec projektu", "pokaż project memory", "pokaz project memory")
    ):
        return {"command": "/project-memory", "operators": ["host"], "prompt": "recent", "mode": "project_memory", "intent": "natural"}

    project_memory_search_prefixes = [
        "szukaj w pamięci projektu",
        "szukaj w pamieci projektu",
        "przeszukaj pamięć projektu",
        "przeszukaj pamiec projektu",
        "project memory search",
    ]
    if any(lower.startswith(prefix) for prefix in project_memory_search_prefixes):
        return {
            "command": "/project-memory",
            "operators": ["host"],
            "prompt": "search " + strip_intent_prefix(stripped, project_memory_search_prefixes),
            "mode": "project_memory",
            "intent": "natural",
        }

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

    council_prefixes = [
        "uruchom council",
        "zrób council",
        "zrob council",
        "ai council",
        "council job",
        "skonsultuj z council",
        "skonsultuj z claude i grokiem",
        "skonsultuj z claude i grok",
    ]
    if any(lower.startswith(prefix) for prefix in council_prefixes):
        return {
            "command": "/council",
            "operators": ["codex", "claude", "grok"],
            "prompt": strip_intent_prefix(stripped, council_prefixes),
            "mode": "council",
            "intent": "natural",
        }

    flow_prefixes = [
        "uruchom flow",
        "claude flow",
        "pełny claude",
        "pelny claude",
        "dynamic workflow",
        "pełny council",
        "pelny council",
        "zrób plan",
        "zrob plan",
        "przygotuj plan",
        "rozpisz plan",
        "zaplanuj",
        "wdrażaj",
        "wdrazaj",
        "wdrażajcie",
        "wdrazajcie",
        "wdroż",
        "wdroz",
        "implementuj",
    ]
    if any(lower.startswith(prefix) for prefix in flow_prefixes):
        if any(marker in lower for marker in ("council", "claude i grok", "claude i grokiem")):
            return {
                "command": "/council",
                "operators": ["codex", "claude", "grok"],
                "prompt": strip_intent_prefix(stripped, flow_prefixes),
                "mode": "council",
                "intent": "natural",
            }
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

    research_prefixes = [
        "zrób research",
        "zrob research",
        "przygotuj research",
        "zbadaj",
        "sprawdź w internecie",
        "sprawdz w internecie",
        "poszukaj",
        "research",
    ]
    if any(lower.startswith(prefix) for prefix in research_prefixes):
        return {
            "command": "@research",
            "operators": ["grok"],
            "prompt": strip_intent_prefix(stripped, research_prefixes),
            "mode": "research",
            "intent": "natural",
        }

    if action_planner_trigger(stripped):
        return {
            "command": "/plan-action",
            "operators": ["host"],
            "prompt": stripped,
            "mode": "action_planner",
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


def route_message(text: str, chat_id: str = "") -> dict:
    stripped = text.strip()
    lower = stripped.lower()
    if not stripped:
        route = route_text(text)
        route.setdefault("route_source", "empty")
        route.setdefault("confidence", 1.0)
        return route
    if stripped.startswith(("@", "/")) or "\n" in stripped:
        route = route_text(text)
        route.setdefault("route_source", "explicit")
        route.setdefault("confidence", 1.0)
        return route
    natural = natural_intent_route(stripped, lower)
    if natural:
        natural.setdefault("route_source", "keyword")
        natural.setdefault("confidence", 1.0)
        return natural
    llm = llm_route(stripped, chat_id=chat_id)
    if llm:
        return llm
    return {
        "command": "/chat",
        "operators": ["host"],
        "prompt": stripped,
        "mode": "chat",
        "intent": "natural",
        "route_source": "fallback",
        "confidence": 0.0,
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
    if lower.startswith("/plan-action"):
        return {"command": "/plan-action", "operators": ["host"], "prompt": stripped[12:].strip(), "mode": "action_planner"}
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
    if lower.startswith("/goal"):
        return {"command": "/goal", "operators": ["host"], "prompt": stripped[5:].strip(), "mode": "goal"}
    if lower.startswith("/chat"):
        return {"command": "/chat", "operators": ["host"], "prompt": stripped[5:].strip(), "mode": "chat"}
    if lower.startswith("/agent"):
        return {"command": "/agent", "operators": ["host"], "prompt": stripped[6:].strip(), "mode": "agent"}
    if lower.startswith("/inbox"):
        return {"command": "/agent", "operators": ["host"], "prompt": stripped[6:].strip(), "mode": "agent"}
    if lower == "/shortcuts" or lower.startswith("/shortcuts ") or lower == "/shortcut" or lower.startswith("/shortcut "):
        prompt = stripped.split(maxsplit=1)[1].strip() if len(stripped.split(maxsplit=1)) > 1 else ""
        return {"command": "/shortcuts", "operators": ["host"], "prompt": prompt, "mode": "shortcuts"}
    if lower == "/drafts" or lower.startswith("/drafts ") or lower == "/draft" or lower.startswith("/draft "):
        prompt = stripped.split(maxsplit=1)[1].strip() if len(stripped.split(maxsplit=1)) > 1 else ""
        return {"command": "/drafts", "operators": ["host"], "prompt": prompt, "mode": "drafts"}
    if lower.startswith("/start-task"):
        return {"command": "/start-task", "operators": ["host"], "prompt": stripped[11:].strip(), "mode": "start_task"}
    if lower.startswith("/cost"):
        return {"command": "/cost", "operators": ["host"], "prompt": "", "mode": "cost"}
    if lower.startswith("/control"):
        return {"command": "/control", "operators": ["host"], "prompt": stripped[8:].strip(), "mode": "control"}
    if lower.startswith("/errors"):
        return {"command": "/errors", "operators": ["host"], "prompt": stripped[7:].strip(), "mode": "errors"}
    if lower.startswith("/nudges") or lower.startswith("/nudge"):
        prompt = stripped.split(maxsplit=1)[1].strip() if len(stripped.split(maxsplit=1)) > 1 else ""
        return {"command": "/nudges", "operators": ["host"], "prompt": prompt, "mode": "nudges"}
    if lower.startswith("/sources"):
        return {"command": "/sources", "operators": ["host"], "prompt": "", "mode": "sources"}
    if lower.startswith("/connectors"):
        return {"command": "/connectors", "operators": ["host"], "prompt": "", "mode": "connectors"}
    if lower.startswith("/connector"):
        return {"command": "/connector", "operators": ["host"], "prompt": stripped[10:].strip(), "mode": "connector"}
    if lower.startswith("/source"):
        return {"command": "/source", "operators": ["host"], "prompt": stripped[7:].strip(), "mode": "source"}
    if lower.startswith("/improvements"):
        return {"command": "/improvements", "operators": ["host"], "prompt": stripped[13:].strip(), "mode": "improvements"}
    if lower.startswith("/improve"):
        return {"command": "/improve", "operators": ["host"], "prompt": stripped[8:].strip(), "mode": "improvements"}
    if lower.startswith("/followups"):
        return {"command": "/followups", "operators": ["host"], "prompt": stripped[10:].strip(), "mode": "followups"}
    if lower.startswith("/loops"):
        return {"command": "/loops", "operators": ["host"], "prompt": stripped[6:].strip(), "mode": "loops"}
    if lower.startswith("/recipes"):
        return {"command": "/recipes", "operators": ["host"], "prompt": "", "mode": "recipes"}
    if lower.startswith("/recipe"):
        return {"command": "/recipe", "operators": ["host"], "prompt": stripped[7:].strip(), "mode": "recipe"}
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
    if lower.startswith("/risk"):
        return {"command": "/risk", "operators": ["host"], "prompt": stripped[5:].strip(), "mode": "risk"}
    if lower.startswith("/execute"):
        return {"command": "/execute", "operators": ["host"], "prompt": stripped[8:].strip(), "mode": "execute"}
    if lower.startswith("/verify"):
        return {"command": "/verify", "operators": ["host"], "prompt": stripped[7:].strip(), "mode": "verify"}
    if lower.startswith("/rollback"):
        return {"command": "/rollback", "operators": ["host"], "prompt": stripped[9:].strip(), "mode": "rollback"}
    if lower.startswith("/memory"):
        return {"command": "/memory", "operators": ["host"], "prompt": stripped[7:].strip(), "mode": "memory"}
    if lower.startswith("/project-memory"):
        return {"command": "/project-memory", "operators": ["host"], "prompt": stripped[15:].strip(), "mode": "project_memory"}
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
    if lower.startswith("/progress"):
        return {"command": "/progress", "operators": ["host"], "prompt": stripped[9:].strip(), "mode": "progress"}
    if lower.startswith("/health"):
        return {"command": "/health", "operators": ["host"], "prompt": "", "mode": "health"}
    if lower.startswith("/selftest"):
        return {"command": "/selftest", "operators": ["host"], "prompt": "", "mode": "selftest"}
    if lower.startswith("/front"):
        return {"command": "/front", "operators": ["host"], "prompt": stripped[6:].strip(), "mode": "front"}
    if lower.startswith("/workspace"):
        return {"command": "/workspace", "operators": ["host"], "prompt": "", "mode": "workspace"}
    natural_route = natural_intent_route(stripped, lower)
    if natural_route:
        return natural_route
    return {"command": "/chat", "operators": ["host"], "prompt": stripped, "mode": "chat", "intent": "natural"}


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
    allowed, reason, reservation = reserve_operator_call(key, task_id=task_id, detail="subprocess")
    if not allowed:
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
        finalize_operator_call(reservation, status="timeout", duration_ms=duration_ms)
        return f"[{name}] unavailable: timeout after {timeout}s"
    except FileNotFoundError:
        duration_ms = int((time.time() - started) * 1000)
        finalize_operator_call(reservation, status="missing", duration_ms=duration_ms, estimated_usd=0.0)
        return f"[{name}] unavailable: command not found"

    elapsed = int((time.time() - started) * 1000)
    if proc.returncode != 0:
        raw_output = "\n".join(part for part in [proc.stdout, proc.stderr] if part)
        output = clean_operator_output(redact_secrets(raw_output))
        detail = output[:1200] or "no output"
        finalize_operator_call(reservation, status="failed", duration_ms=elapsed, detail=detail[:240])
        return f"[{name}] unavailable: exit {proc.returncode}: {detail}"
    output = clean_operator_output(redact_secrets(proc.stdout or proc.stderr or ""))
    finalize_operator_call(reservation, status="completed", duration_ms=elapsed)
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
    allowed, reason, reservation = reserve_operator_call("grok", task_id=task_id, detail="chat")
    if not allowed:
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
        finalize_operator_call(reservation, status="failed", duration_ms=duration_ms, detail=detail[:240])
        return f"[Grok] error: {data.get('error')} {detail}".strip()
    try:
        text = data["choices"][0]["message"]["content"].strip()
    except (KeyError, IndexError, TypeError):
        text = redact_secrets(json.dumps(data, ensure_ascii=False))[:1200]
    finalize_operator_call(reservation, status="completed", duration_ms=duration_ms)
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
    allowed, reason, reservation = reserve_operator_call("grok", task_id=task_id, detail="x_research")
    if not allowed:
        return f"[Grok X Research] blocked: {reason}"
    key = cfg("XAI_API_KEY")
    if not key:
        finalize_operator_call(reservation, status="failed", duration_ms=0, estimated_usd=0.0, detail="missing XAI_API_KEY")
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
        finalize_operator_call(reservation, status="failed", duration_ms=duration_ms, detail=detail[:240])
        return f"[Grok X Research] error: {data.get('error')} {detail}".strip()
    text = xai_response_text(data)
    if not text:
        text = redact_secrets(json.dumps(data, ensure_ascii=False))[:1600]
    finalize_operator_call(reservation, status="completed", duration_ms=duration_ms)
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


def poke_chat_llm_configured() -> bool:
    return bool_cfg("AI_COUNCIL_POKE_CHAT_USE_GROK", True) and bool(cfg("XAI_API_KEY"))


def poke_chat_fallback(prompt: str) -> str:
    text = prompt.strip()
    lower = normalize_intent_text(text)
    if not text:
        return (
            "[Council] Jestem online.\n"
            "Pisz normalnie: krótkie rzeczy odpowiadam od razu, a większe zamieniam w research, plan, Council albo task.\n"
            "Najprostszy test: `co możesz`, `zrób research o Poke`, `zrób plan ...`, `status`."
        )
    if lower in {"działasz", "dzialasz", "jesteś", "jestes", "żyjesz", "zyjesz", "online"}:
        return (
            "[Council] Działam.\n"
            "Zwykła rozmowa wraca od razu, a cięższe rzeczy idą w tło jako task z Details/Facts/Next."
        )
    if any(marker in lower for marker in ("nie odpowiada", "nie dziala", "nie działa", "gowno", "gówno", "poke")):
        return (
            "[Council] Masz rację: cel Poke-like oznacza szybki osobisty operator, nie wolny task dla każdej wiadomości.\n"
            "Obecna poprawka: zwykłe wiadomości wracają jako /chat, a research/plan/Council eskalują tylko wtedy, gdy wykryję taką intencję."
        )
    if lower in {"co dalej", "co teraz", "jaki nastepny krok", "jaki następny krok"}:
        return (
            "[Council] Następny krok: domknąć Poke-like front, czyli szybka odpowiedź, proaktywne nudges, recipes i integracje bez potrzeby komend.\n"
            "Jeśli chodzi o obecny build: sprawdź `/goal` dla luki do Poke parity albo napisz konkretny cel, a zrobię plan/task."
        )
    return (
        "[Council] Rozpoznaję to jako rozmowę, nie zadanie w tle.\n"
        "Mogę od razu przełączyć to w research, plan, Council, task, source search albo bezpieczną akcję po approval.\n"
        "Najlepszy następny krok: napisz cel w jednym zdaniu albo dopisz `zrób research`, `zrób plan`, `skonsultuj z council`."
    )


def poke_chat_should_use_llm(prompt: str) -> bool:
    if not poke_chat_llm_configured():
        return False
    text = prompt.strip()
    lower = normalize_intent_text(text)
    if not text:
        return False
    local_markers = (
        "dzialasz",
        "działa",
        "jestes",
        "jesteś",
        "online",
        "co dalej",
        "co teraz",
        "status",
        "goal",
        "cel",
        "jak poke",
        "poke parity",
        "poke-level",
        "nie odpowiada",
        "front",
        "health",
        "selftest",
        "koszty",
        "kontrola",
        "limity",
    )
    if lower in {"hej", "hi", "hello", "siema", "yo", "ok", "dobra"}:
        return False
    words = set(lower.split())
    def has_marker(marker: str) -> bool:
        if " " not in marker and len(marker) <= 5:
            return marker in words
        return marker in lower

    if any(has_marker(marker) for marker in local_markers):
        return False
    followup_markers = (
        "a teraz",
        "teraz krócej",
        "teraz krocej",
        "rozwiń",
        "rozwin",
        "doprecyzuj",
        "przeredaguj",
    )
    if any(lower.startswith(marker) for marker in followup_markers):
        return True
    min_chars = int_cfg("AI_COUNCIL_POKE_CHAT_LLM_MIN_CHARS", 90)
    if len(text) < min_chars:
        return False
    value_markers = (
        "wyjaśnij",
        "wyjasnij",
        "przeanalizuj",
        "podsumuj",
        "porównaj",
        "porownaj",
        "napisz",
        "odpisz",
        "pomóż",
        "pomoz",
        "zinterpretuj",
    )
    return len(text) >= max(min_chars, 140) or any(marker in lower for marker in value_markers)


def poke_chat_llm_response(prompt: str, chat_id: str = "") -> str | None:
    if not poke_chat_should_use_llm(prompt):
        return None
    started = time.time()
    allowed, reason, reservation = reserve_operator_call("grok", detail="poke_chat")
    if not allowed:
        return None
    text = prompt.strip()
    memory_context = memory_context_for_prompt(text)
    memory_block = f"\n\nKontekst z pamięci AI Council:\n{memory_context}" if memory_context else ""
    messages = [
        {
            "role": "system",
            "content": (
                "Jesteś frontowym operatorem Bartek Agent OS w Telegramie, styl Poke-like. "
                "Odpowiadasz po polsku, szybko, konkretnie i operacyjnie: bez ściany komend, bez logów, bez technicznego żargonu i bez small talku typu 'co u Ciebie'. "
                "Jeśli pytanie jest zwykłe, odpowiedz normalnie. Jeśli wygląda na większe zadanie, nazwij najlepszy tryb: research, plan, Council, task albo approval. "
                "Jeśli Bartek pyta o stan systemu, cel albo Poke parity, powiedz prawdę: system nie jest jeszcze ukończony i brakuje pełnych connectorów oraz iPhone/iMessage layer. "
                "Nie twierdź, że wykonałeś pliki, API, publikację albo kontakt, jeśli tego realnie nie wykonał system. "
                "Nie mów 'wszystko działa' bez sprawdzenia health. Maks 4 krótkie zdania albo 5 punktów. Na końcu podaj jeden najlepszy następny krok, gdy ma sens."
            ),
        }
    ]
    if chat_id:
        for row in recent_conversation(chat_id, limit=int_cfg("AI_COUNCIL_CHAT_HISTORY_TURNS", 6)):
            role = row.get("role") if row.get("role") in {"user", "assistant"} else "user"
            content = str(row.get("text") or "").strip()
            if content:
                messages.append({"role": role, "content": content})
    messages.append({"role": "user", "content": f"{text}{memory_block}"})
    payload = {
        "model": cfg("AI_COUNCIL_POKE_CHAT_MODEL", cfg("AI_COUNCIL_GROK_MODEL", "grok-4.3")),
        "messages": messages,
        "stream": False,
    }
    data = request_json(
        "https://api.x.ai/v1/chat/completions",
        headers={"Authorization": f"Bearer {cfg('XAI_API_KEY')}"},
        method="POST",
        payload=payload,
        timeout=int_cfg("AI_COUNCIL_POKE_CHAT_TIMEOUT", 35),
    )
    duration_ms = int((time.time() - started) * 1000)
    if data.get("ok") is False:
        detail = redact_secrets(str(data.get("body_preview", "")))[:500]
        finalize_operator_call(reservation, status="failed", duration_ms=duration_ms, detail=f"poke_chat: {detail[:220]}")
        return None
    try:
        answer = data["choices"][0]["message"]["content"].strip()
    except (KeyError, IndexError, TypeError):
        answer = ""
    if not answer:
        finalize_operator_call(reservation, status="failed", duration_ms=duration_ms, detail="poke_chat: empty response")
        return None
    finalize_operator_call(reservation, status="completed", duration_ms=duration_ms, detail="poke_chat")
    return "[Council]\n" + answer[: int_cfg("AI_COUNCIL_POKE_CHAT_MAX_CHARS", 900)]


def poke_chat_response(prompt: str, chat_id: str = "") -> str:
    lower = normalize_intent_text(prompt)
    if lower in {"co umiesz", "co potrafisz", "co możesz", "co mozesz", "możliwości", "mozliwosci"}:
        return capabilities_response()
    llm_response = poke_chat_llm_response(prompt, chat_id=chat_id)
    if llm_response:
        return llm_response
    return poke_chat_fallback(prompt)


def host_response(prompt: str, chat_id: str = "") -> str:
    if not prompt:
        return poke_chat_fallback("")
    return poke_chat_response(prompt, chat_id=chat_id)


def raw_operator_response(command: str, prompt: str, task_id: str = "") -> str:
    if command in {"@codex", "codex_default"}:
        return codex_response(prompt, task_id=task_id)
    if command == "@claude":
        return claude_response(prompt, task_id=task_id)
    if command in {"@claude-flow", "/flow"}:
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
    return host_response(prompt)


def strip_operator_label(raw: str) -> str:
    text = clean_operator_output(redact_secrets(raw or "")).strip()
    if not text:
        return ""
    lines = text.splitlines()
    if not lines:
        return ""
    first = lines[0].strip()
    match = re.match(r"^\[(Codex|Claude|Claude Flow|Grok|Grok X Research|Council)\](?:\s*\([^)]*\))?(?:\s*(.*))?$", first)
    if not match:
        return text
    rest = (match.group(2) or "").strip()
    remaining = "\n".join(lines[1:]).strip()
    if rest:
        return "\n".join(part for part in [rest, remaining] if part).strip()
    return remaining


def operator_failed(raw: str) -> bool:
    text = clean_operator_output(redact_secrets(raw or "")).strip()
    if not text:
        return True
    first = next((line.strip() for line in text.splitlines() if line.strip()), "")
    lowered = first.lower()
    match = re.match(r"^\[(codex|claude|claude flow|grok|grok x research|council)\](?:\s*\([^)]*\))?(?:\s*(.*))?$", lowered)
    status = (match.group(2) if match else lowered).strip()
    return status.startswith(("unavailable", "blocked", "error", "failed", "timeout"))


def front_operator_title(command: str, raw: str) -> str:
    if operator_failed(raw):
        return "Operator nie wykonał zadania"
    if command in {"@research", "@xresearch", "/xresearch", "/poke-research"}:
        return "Research gotowy"
    if command in {"@claude-flow", "/flow"}:
        return "Plan workflow gotowy"
    return "Odpowiedź gotowa"


def front_next_line(command: str, task_id: str = "") -> str:
    if task_id:
        return f"NEXT: /details {task_id}, /facts {task_id}, /next {task_id}"
    if command in {"@research", "@xresearch", "/xresearch", "/poke-research"}:
        return "NEXT: jeśli mam działać dalej, napiszę plan albo utworzę task z tego researchu."
    if command in {"@claude-flow", "/flow"}:
        return "NEXT: wskaż, który punkt planu mam zamienić w bezpieczne action/task."
    if command == "@all":
        return "NEXT: jeśli chcesz decyzję wykonawczą, napiszę krótką syntezę i plan akcji."
    return "NEXT: dopisz, czy mam to rozwinąć w research, plan, Council albo bezpieczną akcję."


def front_operator_response(command: str, raw: str, task_id: str = "") -> str:
    body = strip_operator_label(raw)
    if not body:
        body = "Brak treści odpowiedzi. Sprawdź /health albo uruchom zadanie ponownie."
    limit = int_cfg("AI_COUNCIL_FRONT_OPERATOR_MAX_CHARS", 2200)
    lines = [
        "[Council]",
        f"{front_operator_title(command, raw)}.",
        "",
        body[:limit],
        "",
        front_next_line(command, task_id=task_id),
    ]
    if task_id:
        lines.append(f"Details: /details {task_id}")
    return "\n".join(lines).strip()


def front_all_response(parts: list[tuple[str, str]], task_id: str = "") -> str:
    lines = [
        "[Council]",
        "Konsultacja gotowa.",
        "",
        "Wnioski:",
    ]
    for label, raw in parts:
        cleaned = compact_line(strip_operator_label(raw), 260) or "brak treści"
        lines.append(f"- {label}: {cleaned}")
    lines.extend(["", front_next_line("@all", task_id=task_id)])
    if task_id:
        lines.append(f"Details: /details {task_id}")
    return "\n".join(lines)


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
        return "\n\n".join(responses) if responses else host_response(prompt, chat_id=chat_id)
    if command == "/stop":
        return "[Council] Stop przyjęty. Bounded listener zakończy ten przebieg po obsłudze aktualnej wiadomości."
    if command == "/status":
        return task_status_response(prompt)
    if command == "/progress":
        return progress_response(prompt)
    if command == "/health":
        return health_response()
    if command == "/selftest":
        return selftest_response()
    if command == "/front":
        return front_reliability_response(prompt)
    if command == "/workspace":
        ensure_council_dirs()
        return "[Council] Workspace: D:\\ai-council. L2.5: workspaces, artifacts, reports, state\\tasks.jsonl, state\\actions.jsonl, state\\background_jobs.jsonl, state\\artifact_index.jsonl, state\\costs.jsonl, state\\memory.sqlite. Codex: read-only. Claude quick: bez tools. Claude Flow: Opus 4.8 plan workflow. Grok: API research."
    if command == "/capabilities":
        return capabilities_response()
    if command == "/goal":
        return goal_response()
    if command == "/chat":
        return poke_chat_response(prompt, chat_id=chat_id)
    if command == "/agent":
        return agent_response(prompt, chat_id=chat_id)
    if command == "/shortcuts":
        return shortcuts_response(prompt)
    if command == "/drafts":
        return integration_drafts_response(prompt)
    if command == "/plan-action":
        return action_planner_response(prompt, chat_id=chat_id)
    if command == "/start-task":
        return start_planned_task_response(prompt, chat_id=chat_id)
    if command == "/cost":
        return cost_response()
    if command == "/control":
        return control_response(prompt, chat_id=chat_id)
    if command == "/errors":
        return errors_response(prompt)
    if command == "/nudges":
        return nudges_response(prompt)
    if command == "/sources":
        return sources_response()
    if command == "/connectors":
        return connectors_response()
    if command == "/connector":
        return connector_response(prompt)
    if command == "/source":
        return source_response(prompt)
    if command == "/improvements":
        return improvements_response(prompt)
    if command == "/improve":
        return improvements_response(prompt)
    if command == "/followups":
        return followups_response(prompt)
    if command == "/loops":
        return loops_response()
    if command == "/recipes":
        return recipes_response()
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
    if command == "/risk":
        return risk_response(prompt)
    if command == "/execute":
        return execute_response(prompt)
    if command == "/verify":
        return verify_response(prompt)
    if command == "/rollback":
        return rollback_response(prompt)
    if command == "/memory":
        return memory_response(prompt)
    if command == "/project-memory":
        return project_memory_response(prompt)
    if command == "/recipe":
        return recipe_response(prompt)
    if command == "/council":
        return council_response_for_chat(prompt, chat_id=chat_id, task_id=task_id)
    if command == "/jobs":
        return council_jobs_response()
    if command == "/propose":
        action = create_action(prompt, action_type="manual_proposal", risk="")
        return (
            "[Council] Pending action utworzona.\n"
            f"id: {action['action_id']}\n"
            f"risk: {action.get('risk')}\n"
            "Zatwierdź: /approve <id> albo odrzuć: /deny <id>."
        )
    if command == "/write":
        return write_response(prompt)
    if command == "/append":
        return append_response(prompt)
    if command == "/patch":
        return patch_response(prompt)
    if command in FRONT_OPERATOR_COMMANDS:
        return front_operator_response(command, raw_operator_response(command, prompt, task_id=task_id), task_id=task_id)
    if command == "@all":
        parts = [
            ("Technicznie", codex_response(prompt, task_id=task_id)),
            ("Plan", claude_response(prompt, task_id=task_id)),
            ("Research", grok_route_response(prompt, max_chars=700, task_id=task_id)),
        ]
        return front_all_response(parts, task_id=task_id)
    return host_response(prompt, chat_id=chat_id)


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


def is_allowed_callback(callback: dict) -> bool:
    sender = callback.get("from", {})
    message = callback.get("message") or {}
    chat = message.get("chat") or {}
    return (
        str(sender.get("id")) == cfg("TELEGRAM_ALLOWED_USER_ID")
        and str(chat.get("id")) == cfg("TELEGRAM_ALLOWED_CHAT_ID")
    )


def handle_callback_query(callback: dict) -> tuple[str, str]:
    data = str(callback.get("data") or "")
    if ":" in data:
        action, target = data.split(":", 1)
    else:
        action, target = data, ""
    action = action.lower().strip()
    target = target.strip()
    if action == "approve":
        return approve_response(target), "approved"
    if action == "deny":
        return deny_response(target), "denied"
    if action == "edit":
        current = get_latest_action(target)
        if current and current.get("status") == "pending":
            update_action_status(target, "editing", "edit requested by Bartek")
        return (
            f"[Council] Popraw `{target}`: stara akcja nie będzie już traktowana jako pending. Napisz poprawioną intencję jako nową wiadomość.",
            "edit",
        )
    if action == "cancel":
        return cancel_response(target), "cancelled"
    if action == "status":
        return task_status_response(target), "status"
    if action == "details":
        return details_response(target), "details"
    if action == "facts":
        return facts_response(target), "facts"
    if action == "next":
        return next_response(target), "next"
    if action == "actions":
        return actions_response(), "actions"
    return f"[Council] Nieznany callback `{compact_line(data, 80)}`.", "unknown_callback"


def listen_once(send: bool = False, limit: int = 10, verbose: bool = True) -> int:
    params = {"limit": str(limit), "timeout": "1"}
    offset = read_offset()
    if offset is not None:
        params["offset"] = str(offset)
    data = request_json(telegram_url("getUpdates", params), timeout=5)
    if not data.get("ok"):
        print(f"telegram_getUpdates=failed {data.get('error') or data.get('description')}")
        record_error(
            "telegram_getUpdates",
            message=str(data.get("error") or data.get("description") or data.get("body_preview") or "getUpdates failed"),
            event={"offset": offset, "limit": limit},
            severity="warning",
        )
        return 1

    updates = data.get("result", [])
    if verbose or updates:
        print(f"listen_updates_count={len(updates)}")
    processed = 0
    max_update_id = None
    for update in updates:
        max_update_id = max(max_update_id or update["update_id"], update["update_id"])
        callback = update.get("callback_query")
        if callback:
            chat_id = str(((callback.get("message") or {}).get("chat") or {}).get("id", ""))
            allowed = is_allowed_callback(callback)
            started = time.time()
            response = ""
            status = "ignored_not_allowed"
            if allowed:
                try:
                    response, status = handle_callback_query(callback)
                    if send:
                        telegram_answer_callback_query(str(callback.get("id") or ""), status)
                        message_id = str((callback.get("message") or {}).get("message_id") or "")
                        if chat_id and message_id:
                            telegram_edit_message_reply_markup(chat_id, message_id)
                        sent = telegram_send_message_with_markup(chat_id, response, response_reply_markup(response))
                        if not sent:
                            status = "send_failed"
                    else:
                        print(response)
                except Exception as exc:
                    response = f"[Council] Callback error: {compact_line(redact_secrets(str(exc)), 500)}"
                    status = "failed"
                    record_error(
                        "telegram_callback",
                        exc=exc,
                        event={
                            "update_id": update.get("update_id"),
                            "callback_data": compact_line(str(callback.get("data") or ""), 120),
                            "chat_id_hash": short_hash(chat_id),
                        },
                    )
                    if send and chat_id:
                        telegram_send_message(chat_id, response)
                    else:
                        print(response)
            event = {
                "request_id": short_hash(f"{update.get('update_id')}:{callback.get('data', '')}"),
                "update_id": update.get("update_id"),
                "chat_id_hash": short_hash(chat_id),
                "user_id_hash": short_hash(str((callback.get("from") or {}).get("id", ""))),
                "command": "callback",
                "operators": ["host"],
                "allowed": allowed,
                "status": status,
                "duration_ms": int((time.time() - started) * 1000),
                "output_preview": response[:300],
            }
            audit(event)
            processed += 1
            continue
        message = update.get("message") or update.get("edited_message") or {}
        media = telegram_media_from_message(message)
        text = message.get("text") or message.get("caption") or ""
        chat_id = str((message.get("chat") or {}).get("id", ""))
        allowed = is_allowed_message(message)
        route = (
            {"command": "/capture", "operators": ["host"], "prompt": text or str((media or {}).get("kind") or ""), "mode": "capture"}
            if media
            else route_message(text, chat_id=chat_id)
        )
        event = {
            "request_id": short_hash(f"{update.get('update_id')}:{text}:{(media or {}).get('file_unique_id', '')}"),
            "update_id": update.get("update_id"),
            "chat_id_hash": short_hash(chat_id),
            "user_id_hash": short_hash(str((message.get("from") or {}).get("id", ""))),
            "command": route.get("command"),
            "operators": route.get("operators", []),
            "allowed": allowed,
            "send_requested": send,
            "dry_send_env": bool_cfg("AI_COUNCIL_DRY_SEND", True),
            "prompt_preview": route.get("prompt", "")[:160],
            "media_kind": (media or {}).get("kind", ""),
            "route_source": route.get("route_source", ""),
            "confidence": route.get("confidence", ""),
            "route_reason": route.get("route_reason", ""),
        }
        if not allowed:
            event["status"] = "ignored_not_allowed"
            audit(event)
            continue
        if not text and not media:
            event["status"] = "ignored_no_text"
            audit(event)
            continue

        print(f"processing update={update.get('update_id')} command={route.get('command')} send={send}")
        started = time.time()
        if media:
            try:
                response, media_task = capture_telegram_media_message(message, chat_id=chat_id, update_id=update.get("update_id"))
                event["duration_ms"] = int((time.time() - started) * 1000)
                event["output_preview"] = response[:300]
                if media_task:
                    event["task_id"] = media_task.get("task_id")
                if send:
                    sent = telegram_send_message_with_markup(chat_id, response, response_reply_markup(response))
                    event["status"] = "responded" if sent else "send_failed"
                else:
                    event["status"] = "dry_responded"
                    print(response)
            except Exception as exc:
                response = f"[Council] Media capture error: {compact_line(redact_secrets(str(exc)), 500)}"
                event["duration_ms"] = int((time.time() - started) * 1000)
                event["output_preview"] = response[:300]
                event["status"] = "failed"
                record_error("telegram_media_capture", exc=exc, event=event)
                if send:
                    telegram_send_message(chat_id, response)
                else:
                    print(response)
            audit(event)
            processed += 1
            if chat_id:
                maybe_send_action_nudges(chat_id, send)
            continue

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
            record_error("telegram_message", exc=exc, event=event)
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
            sent = telegram_send_message_with_markup(chat_id, response, response_reply_markup(response))
            event["status"] = "duplicate" if duplicate else ("responded" if sent else "send_failed")
            if not sent:
                record_error("telegram_response_send", message=response[:1000], event=event, severity="warning")
        else:
            event["status"] = "duplicate" if duplicate else "dry_responded"
            print(response)
        append_conversation_turn(chat_id, "user", text, route)
        append_conversation_turn(chat_id, "assistant", response, route)
        audit(event)
        processed += 1
        if allowed and chat_id:
            maybe_send_action_nudges(chat_id, send)

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
        scheduled = run_due_recipes(send=send)
        if scheduled:
            print(f"scheduled_recipes_started={scheduled}")
        nudges = run_proactive_scan(send=send)
        if nudges:
            print(f"proactive_nudges_created={nudges}")
        code = listen_once(send=send, limit=limit, verbose=False)
        after = AUDIT_LOG.stat().st_size if AUDIT_LOG.exists() else before
        if code != 0:
            return code
        if after > before or scheduled or nudges:
            total += 1
        time.sleep(sleep_seconds)
    print(f"listen_loop_done iterations_with_activity={total}")
    return 0


def serve(send: bool = True, limit: int = 10, sleep_seconds: float = 1.5) -> int:
    print(f"serve_started send={send}")
    listener_lock = SingleInstanceLock(TELEGRAM_LISTENER_LOCK)
    if not listener_lock.acquire():
        print(f"serve_already_running lock={TELEGRAM_LISTENER_LOCK}")
        audit(
            {
                "timestamp": utc_now(),
                "command": "serve",
                "operators": ["host"],
                "status": "skipped_already_running",
                "duration_ms": 0,
                "output_preview": f"lock={TELEGRAM_LISTENER_LOCK}",
            }
        )
        return 0
    try:
        log_startup()
        reconciled = reconcile_background_jobs()
        if reconciled:
            print(f"reconciled_background_jobs={len(reconciled)}")
        while True:
            scheduled = run_due_recipes(send=send)
            if scheduled:
                print(f"scheduled_recipes_started={scheduled}")
            nudges = run_proactive_scan(send=send)
            if nudges:
                print(f"proactive_nudges_created={nudges}")
            code = listen_once(send=send, limit=limit, verbose=False)
            if code != 0:
                print(f"serve_poll_error code={code}")
                time.sleep(max(5.0, sleep_seconds))
            else:
                time.sleep(sleep_seconds)
    except KeyboardInterrupt:
        print("serve_stopped")
        return 0
    finally:
        listener_lock.release()


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
    scheduler = sub.add_parser("run-scheduler")
    scheduler.add_argument("--send", action="store_true", help="Actually send Telegram scheduler replies")
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
    shortcuts = sub.add_parser("serve-shortcuts")
    shortcuts.add_argument("--host", default="", help="Shortcuts bind host, default AI_COUNCIL_SHORTCUT_HOST or 127.0.0.1")
    shortcuts.add_argument("--port", type=int, default=0, help="Shortcuts bind port, default AI_COUNCIL_SHORTCUT_PORT or 8788")
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
    if args.cmd == "run-scheduler":
        started = run_due_recipes(send=args.send)
        print(f"scheduled_recipes_started={started}")
        return 0
    if args.cmd == "listen-once":
        return listen_once(send=args.send, limit=args.limit)
    if args.cmd == "listen":
        return listen_loop(send=args.send, seconds=args.seconds, limit=args.limit)
    if args.cmd == "serve":
        return serve(send=args.send, limit=args.limit)
    if args.cmd == "serve-shortcuts":
        return serve_shortcuts(host=args.host, port=args.port)
    if args.cmd == "run-background-job":
        return run_background_job(args.task_id)
    if args.cmd == "dry-route":
        dry_route(" ".join(args.text))
        return 0
    return 2


if __name__ == "__main__":
    sys.exit(main())
