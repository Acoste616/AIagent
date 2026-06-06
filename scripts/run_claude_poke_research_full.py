from __future__ import annotations

import os
import subprocess
from datetime import datetime
from pathlib import Path


ROOT = Path("D:/ai-council")
OPENCLAW = Path("D:/openclaw-export")
OUT_DIR = OPENCLAW / "shared-drive" / "claude-collab"
ARTIFACTS = ROOT / "artifacts"
MODEL = os.environ.get("AI_COUNCIL_CLAUDE_FLOW_MODEL", "claude-opus-4-8")
CLAUDE_BIN = Path.home() / ".local" / "bin" / "claude.exe"


def latest(pattern: str) -> Path | None:
    items = sorted(ARTIFACTS.glob(pattern), key=lambda p: p.stat().st_mtime, reverse=True)
    return items[0] if items else None


def read_limited(path: Path | None, limit: int) -> str:
    if not path or not path.exists():
        return ""
    return path.read_text(encoding="utf-8", errors="replace")[:limit]


def build_prompt() -> str:
    grok_main = latest("grok-x-poke-research-*/report.md")
    grok_solution = latest("grok-x-poke-solution-research-*.md")
    previous_summary = latest("claude-opus48-poke-research-plan-*.md")
    return f"""
Jesteś Claude Opus 4.8. Poprzedni run zwrócił tylko summary i fałszywie zasugerował istnienie pełnego dokumentu. To jest błąd.

TERAZ MASZ ZWRÓCIĆ PEŁNY RAPORT W ODPOWIEDZI STDOUT. Nie pisz "pełny raport jest w pliku". Nie pisz tylko streszczenia.

Cel: kompletny research + solution design przed AI Council Tournament dla prywatnego Poke-like/OpenClaw-like/Hermes-like Bartek Agent OS.

Masz dostęp do:
- D:\\ai-council
- D:\\openclaw-export
- D:\\openclaw-export\\tools\\hermes-agent
- D:\\openclaw-export\\tools\\multica

Przejrzyj samodzielnie lokalne pliki, jeśli możesz:
- D:\\ai-council\\ai_council.py
- D:\\ai-council\\tests
- D:\\ai-council\\artifacts
- D:\\openclaw-export\\.codex-hybrid\\OPERATING_CONTEXT.md
- D:\\openclaw-export\\shared-drive\\claude\\WORKING_MEMORY.md
- D:\\openclaw-export\\GUIDANCE.md
- D:\\openclaw-export\\MEMORY.md
- Hermes README/AGENTS/docs jeśli są.

Wymagany raport:
# Claude Opus 4.8 Full Research + Solution Design
## 1. Research Summary
## 2. Poke Feature Inventory
## 3. Poke Unknowns / Non-Hallucination Boundaries
## 4. Current AI Council Inventory
## 5. Current UX Failure Analysis
## 6. OpenClaw Assets To Reuse
## 7. Hermes Assets To Reuse
## 8. Target Feature Design
## 9. Deployment Plan With Dependencies
## 10. Minimal Immediate Patches For Codex
## 11. Acceptance Criteria
## 12. Test Plan
## 13. Questions / Decisions For Bartek

Wymagania jakości:
- Minimum 10 konkretnych funkcji docelowych.
- Minimum 8 konkretnych patchy lub zmian.
- Minimum 12 acceptance criteria.
- Oddziel fakty od hipotez.
- Oznacz unknowns.
- Pisz po polsku.
- Nie wykonuj zewnętrznych write/send/publish.
- Nie używaj sekretów.

## Previous Claude Summary To Expand
{read_limited(previous_summary, 6000)}

## Grok Main Poke Research
{read_limited(grok_main, 14000)}

## Grok Implementation Research
{read_limited(grok_solution, 10000)}
""".strip()


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    ARTIFACTS.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    out_file = OUT_DIR / f"claude-opus48-poke-research-full-{stamp}.md"
    mirror_file = ARTIFACTS / f"claude-opus48-poke-research-full-{stamp}.md"
    command = [
        str(CLAUDE_BIN),
        "--no-session-persistence",
        "--model",
        MODEL,
        "--permission-mode",
        "plan",
        "--add-dir",
        str(ROOT),
        "--add-dir",
        str(OPENCLAW),
        "-p",
        build_prompt(),
    ]
    env = os.environ.copy()
    env["PYTHONUTF8"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"
    started = datetime.now().isoformat(timespec="seconds")
    proc = subprocess.run(
        command,
        cwd=str(ROOT),
        input="",
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        timeout=int(os.environ.get("AI_COUNCIL_CLAUDE_RESEARCH_TIMEOUT", "3600")),
        env=env,
    )
    ended = datetime.now().isoformat(timespec="seconds")
    output = (proc.stdout or "") + ("\n\n## STDERR\n\n" + proc.stderr if proc.stderr else "")
    report = (
        f"<!-- started={started} ended={ended} exit={proc.returncode} model={MODEL} -->\n\n"
        + output.strip()
        + "\n"
    )
    out_file.write_text(report, encoding="utf-8")
    mirror_file.write_text(report, encoding="utf-8")
    print(f"exit={proc.returncode}")
    print(f"output={out_file}")
    print(f"mirror={mirror_file}")
    print(f"bytes={len(report.encode('utf-8'))}")
    print(report[:8000])
    return proc.returncode


if __name__ == "__main__":
    raise SystemExit(main())
