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


PROMPT = """
Jesteś Claude Opus 4.8. Poprzedni tournament zwrócił tylko TL;DR:
- winner: Kandydat G — Hybrid Staged Architecture, 8.15/10
- runner-up: Kandydat B — Recipes-first Poke clone, 7.40/10
- first batch: Etap 0+1, 9 patchy: buttony inline -> recipe engine -> delivery nudge + cost

Teraz NIE wolno pisać "pełny raport jest w pliku". Zwróć tylko właściwy tournament artifact w stdout.

Wymagany output:
# AI Council Tournament Scorecard
## Criteria
## Score Table
Tabela minimum 7 kandydatów:
A Telegram-only incremental
B Recipes-first Poke clone
C Hermes-style tool registry
D OpenClaw memory/proactive OS
E iPhone Shortcuts-first
F Full execution/Risk Officer-first
G Hybrid Staged Architecture

Kolumny:
candidate, speed, reliability, poke_ux, safety, implementation_cost, extensibility, iphone_path, auditability, current_fit, total, verdict

## Winner
## Runner-up
## First Batch: 9 Patches
Podaj dokładnie 9 patchy do wdrożenia teraz, w kolejności.
## Anti-Plan
## Acceptance Criteria

Pisz po polsku. Nie wykonuj żadnych akcji. Nie wspominaj żadnego dodatkowego pliku.
""".strip()


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    ARTIFACTS.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    out_file = OUT_DIR / f"claude-opus48-tournament-scorecard-{stamp}.md"
    mirror_file = ARTIFACTS / f"claude-opus48-tournament-scorecard-{stamp}.md"
    command = [
        str(CLAUDE_BIN),
        "--no-session-persistence",
        "--model",
        MODEL,
        "--permission-mode",
        "plan",
        "-p",
        PROMPT,
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
        timeout=900,
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
    print(report)
    return proc.returncode


if __name__ == "__main__":
    raise SystemExit(main())
