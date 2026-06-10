#!/bin/bash
# L4.103 deploy pack — RUN ON BARTEK'S MAC (uses `ssh ai-council-desktop`).
#
# Why a new script: deploy_l494_from_mac.sh is stale — it syncs the monolithic
# tests/test_ai_council.py which no longer exists (split into tests/test_council_*.py
# in L4.100) and ignores the bridge, pyproject.toml and the new L4.103 test files.
# This one syncs the CURRENT fileset and runs the FULL Windows test suite.
#
#   ./scripts/deploy/deploy_l4103_from_mac.sh            # phase 1: diff Mac vs Windows (read-only)
#   ./scripts/deploy/deploy_l4103_from_mac.sh --apply    # phase 2: backup -> sync -> FULL tests -> smoke (auto-rollback)
#   ./scripts/deploy/deploy_l4103_from_mac.sh --restart  # phase 3: kill+restart the Telegram listener (picks up new code)
#   ./scripts/deploy/deploy_l4103_from_mac.sh --rollback <backup_dir_name>
#
# Syncs: ai_council.py, the WHOLE tests/ dir, pyproject.toml, scripts/, .github/workflows/ci.yml, docs/ (additive).
# Never touches .env, state/, logs/, errors/, listeners (except the explicit --restart phase).
#
# PRE-FLIGHT (do once on the Mac before --apply):
#   rm -f .git/index.lock                 # clear the stale lock left by the audit session
#   git rm --cached docs/.DS_Store || true
#   python3 -m pytest -q tests            # must be green locally (expected: 575 passed)
#
# SAFE re iMessage fail-closed: Windows .env already has
#   AI_COUNCIL_IMESSAGE_ALLOWED_SENDERS=+48573465367,bdomanskyy@icloud.com (L4.100),
# so L4.103 fail-closed keeps the channel LIVE. No env change required. The new
# L4.103 flags (AI_COUNCIL_SELF_REPAIR_MAX_DIFF_LINES, _ADVERSARIAL,
# AI_COUNCIL_IMESSAGE_ALLOW_OPEN) all have safe defaults — set none to deploy.
set -euo pipefail

ALIAS="${AI_COUNCIL_HOST_SSH_ALIAS:-ai-council-desktop}"
MAC_REPO="$(cd "$(dirname "$0")/../.." && pwd)"
WIN_DIR='D:/ai-council'
TS="$(date +%Y%m%d-%H%M%S)"
TMP="$(mktemp -d /tmp/l4103-deploy-XXXX)"

ps_run() { ssh "$ALIAS" "powershell -NoProfile -ExecutionPolicy Bypass -Command \"$1\""; }

phase_diff() {
  echo "== PHASE 1: diff Mac vs Windows (read-only) =="
  scp -q "$ALIAS:$WIN_DIR/ai_council.py" "$TMP/win_ai_council.py" || { echo "scp ai_council.py failed — is the desktop awake & reachable?"; exit 1; }
  if diff -q "$TMP/win_ai_council.py" "$MAC_REPO/ai_council.py" >/dev/null 2>&1; then
    echo "ai_council.py: IDENTICAL"
  else
    diff "$TMP/win_ai_council.py" "$MAC_REPO/ai_council.py" | head -60
    echo "...(lines: windows=$(wc -l < "$TMP/win_ai_council.py") mac=$(wc -l < "$MAC_REPO/ai_council.py"))"
  fi
  echo "-- Windows test files currently present:"
  ps_run "cd $WIN_DIR; Get-ChildItem tests/*.py | Select-Object -ExpandProperty Name"
  echo
  echo "UWAGA: jeśli Windows ma w ai_council.py linie tylko po stronie '<' (zmiany, których nie ma na Macu),"
  echo "NIE rób --apply zanim ich nie przeniesiesz do repo. Pełny diff: diff $TMP/win_ai_council.py $MAC_REPO/ai_council.py"
}

phase_apply() {
  echo "== PHASE 2: backup -> sync -> FULL tests -> smoke =="
  BK="backups/pre-L4.103-$TS"
  echo "-- backup -> $WIN_DIR/$BK (ai_council.py + whole tests/ + pyproject.toml)"
  ps_run "cd $WIN_DIR; New-Item -ItemType Directory -Force -Path '$BK/tests' | Out-Null; Copy-Item ai_council.py '$BK/'; Copy-Item pyproject.toml '$BK/' -ErrorAction SilentlyContinue; Copy-Item tests/*.py '$BK/tests/'"

  echo "-- sync ai_council.py + pyproject.toml"
  scp -q "$MAC_REPO/ai_council.py" "$ALIAS:$WIN_DIR/ai_council.py"
  scp -q "$MAC_REPO/pyproject.toml" "$ALIAS:$WIN_DIR/pyproject.toml"

  echo "-- sync WHOLE tests/ dir (and remove a stale monolith if present on Windows)"
  ps_run "cd $WIN_DIR; if (Test-Path tests/test_ai_council.py) { Remove-Item tests/test_ai_council.py -Force }"
  scp -q "$MAC_REPO"/tests/*.py "$ALIAS:$WIN_DIR/tests/"

  echo "-- sync scripts/ (bridge sanitization) + CI"
  scp -q "$MAC_REPO/scripts/mac_imessage_bridge_standalone.py" "$ALIAS:$WIN_DIR/scripts/" || true
  ps_run "cd $WIN_DIR; New-Item -ItemType Directory -Force -Path .github/workflows | Out-Null" || true
  scp -q "$MAC_REPO/.github/workflows/ci.yml" "$ALIAS:$WIN_DIR/.github/workflows/" || true

  echo "-- additive docs"
  ps_run "cd $WIN_DIR; New-Item -ItemType Directory -Force -Path docs/audit, docs/implementation | Out-Null" || true
  scp -q "$MAC_REPO/docs/audit/REPO_AUDIT_2026-06-10_v2_CLAUDE_FULL.md" "$ALIAS:$WIN_DIR/docs/audit/" || true
  scp -q "$MAC_REPO/docs/audit/AUDIT_ADDENDUM_DECISIONS_2026-06-10.md" "$ALIAS:$WIN_DIR/docs/audit/" || true
  scp -q "$MAC_REPO/docs/implementation/L4_103_AUDIT_REMEDIATION_LOOP.md" "$ALIAS:$WIN_DIR/docs/implementation/" || true

  echo "-- FULL test suite on Windows"
  if ! ps_run "cd $WIN_DIR; python -X utf8 -m pytest -q tests"; then
    echo "!! TESTS FAILED — rolling back ai_council.py + tests/ + pyproject.toml"
    ps_run "cd $WIN_DIR; Copy-Item '$BK/ai_council.py' ai_council.py -Force; Copy-Item '$BK/pyproject.toml' pyproject.toml -Force -ErrorAction SilentlyContinue; Get-ChildItem tests/*.py | Remove-Item -Force; Copy-Item '$BK/tests/*.py' tests/"
    echo "Rolled back to $BK"; exit 1
  fi

  echo "-- smoke: /health"
  ps_run "cd $WIN_DIR; python -X utf8 ai_council.py respond /health" | tail -6
  echo "-- smoke: doctor imessage allowlist line (expect OK, not FAIL-CLOSED)"
  ps_run "cd $WIN_DIR; python -X utf8 ai_council.py doctor" 2>&1 | grep -i "imessage_allowlist" || echo "(doctor ran; check output above)"
  echo "-- smoke: respond-b64 (expect a reply, no route=/audit_log= tail)"
  B64=$(printf 'co robisz' | base64)
  OUT=$(ps_run "cd $WIN_DIR; python -X utf8 ai_council.py respond-b64 --b64 $B64")
  echo "$OUT"
  if echo "$OUT" | grep -qE '^\s*(route=|audit_log=)'; then echo "!! DEBUG TAIL LEAK"; exit 1; fi
  echo
  echo "OK. Backup: $WIN_DIR/$BK"
  echo "Listener still runs OLD code in memory until restarted — run: $0 --restart"
}

phase_restart() {
  echo "== PHASE 3: restart Telegram listener so it loads the new code =="
  scp -q "$MAC_REPO/windows-deploy/restart-ai-council.ps1" "$ALIAS:$WIN_DIR/windows-deploy/restart-ai-council.ps1" || true
  ssh "$ALIAS" "powershell -NoProfile -ExecutionPolicy Bypass -File '$WIN_DIR/windows-deploy/restart-ai-council.ps1'"
  echo "Expect 'serve_count=1' above. If 0 or >1, re-run or inspect."
}

phase_rollback() {
  BK="backups/$1"
  echo "== ROLLBACK from $WIN_DIR/$BK =="
  ps_run "cd $WIN_DIR; Copy-Item '$BK/ai_council.py' ai_council.py -Force; Copy-Item '$BK/pyproject.toml' pyproject.toml -Force -ErrorAction SilentlyContinue; Get-ChildItem tests/*.py | Remove-Item -Force; Copy-Item '$BK/tests/*.py' tests/"
  ps_run "cd $WIN_DIR; python -X utf8 -m pytest -q tests" || true
  echo "Done. Restart listener with --restart if you rolled back live code."
}

case "${1:-}" in
  --apply)    phase_diff; echo; read -r -p "Kontynuować APPLY (backup+sync+full tests+smoke)? [y/N] " a; [ "$a" = "y" ] && phase_apply || echo "Przerwano.";;
  --restart)  phase_restart;;
  --rollback) shift; [ -n "${1:-}" ] || { echo "Podaj nazwę backupu (np. pre-L4.103-20260610-120000)"; exit 2; }; phase_rollback "$1";;
  *)          phase_diff;;
esac
