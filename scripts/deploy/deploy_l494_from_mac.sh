#!/bin/bash
# L4.94 deploy pack — run ON BARTEK'S MAC (uses `ssh ai-council-desktop`).
# Safe by default: with no flags it only DIFFS Mac repo vs Windows production.
#
#   ./scripts/deploy/deploy_l494_from_mac.sh            # phase 1: diff only (read-only)
#   ./scripts/deploy/deploy_l494_from_mac.sh --apply    # phase 2: backup -> sync -> tests -> smoke (auto-rollback on test failure)
#   ./scripts/deploy/deploy_l494_from_mac.sh --rollback <backup_dir_name>   # phase 3: restore a backup
#
# Deploys ONLY: ai_council.py, tests/test_ai_council.py (+ docs are synced as additive copies).
# Never touches .env, state, logs, listeners.
set -euo pipefail

ALIAS="${AI_COUNCIL_HOST_SSH_ALIAS:-ai-council-desktop}"
MAC_REPO="$(cd "$(dirname "$0")/../.." && pwd)"
WIN_DIR='D:/ai-council'
TS="$(date +%Y%m%d-%H%M%S)"
TMP="$(mktemp -d /tmp/l494-deploy-XXXX)"

ps_run() { ssh "$ALIAS" "powershell -NoProfile -ExecutionPolicy Bypass -Command \"$1\""; }

phase_diff() {
  echo "== PHASE 1: diff Mac vs Windows (read-only) =="
  scp -q "$ALIAS:$WIN_DIR/ai_council.py" "$TMP/win_ai_council.py"
  scp -q "$ALIAS:$WIN_DIR/tests/test_ai_council.py" "$TMP/win_tests.py"
  echo "--- ai_council.py (windows -> mac):"
  diff -q "$TMP/win_ai_council.py" "$MAC_REPO/ai_council.py" >/dev/null 2>&1 \
    && echo "IDENTICAL" \
    || { diff "$TMP/win_ai_council.py" "$MAC_REPO/ai_council.py" | head -40; \
         echo "...(lines: windows=$(wc -l < "$TMP/win_ai_council.py") mac=$(wc -l < "$MAC_REPO/ai_council.py"))"; }
  echo "--- tests/test_ai_council.py:"
  diff -q "$TMP/win_tests.py" "$MAC_REPO/tests/test_ai_council.py" >/dev/null 2>&1 \
    && echo "IDENTICAL" \
    || echo "DIFFERS (lines: windows=$(wc -l < "$TMP/win_tests.py") mac=$(wc -l < "$MAC_REPO/tests/test_ai_council.py"))"
  echo
  echo "UWAGA: jeśli Windows ma zmiany, których nie ma na Macu (linie tylko po stronie '<'),"
  echo "NIE rób --apply zanim nie przeniesiesz ich do repo. Pełny diff: diff $TMP/win_ai_council.py $MAC_REPO/ai_council.py"
}

phase_apply() {
  echo "== PHASE 2: backup -> sync -> tests -> smoke =="
  BK="backups/pre-L4.94-$TS"
  echo "-- backup -> $WIN_DIR/$BK"
  ps_run "cd $WIN_DIR; New-Item -ItemType Directory -Force -Path '$BK' | Out-Null; Copy-Item ai_council.py '$BK/'; Copy-Item tests/test_ai_council.py '$BK/'"
  echo "-- sync files"
  scp -q "$MAC_REPO/ai_council.py" "$ALIAS:$WIN_DIR/ai_council.py"
  scp -q "$MAC_REPO/tests/test_ai_council.py" "$ALIAS:$WIN_DIR/tests/test_ai_council.py"
  ps_run "cd $WIN_DIR; New-Item -ItemType Directory -Force -Path docs/agent-loop | Out-Null" || true
  scp -q "$MAC_REPO/docs/implementation/L4_93_CLAUDE_FRONT_OPERATOR.md" "$ALIAS:$WIN_DIR/docs/implementation/" || true
  scp -q "$MAC_REPO/docs/agent-loop/LOOP_2026-06-09_L4_94.md" "$ALIAS:$WIN_DIR/docs/agent-loop/" || true
  echo "-- tests on Windows"
  if ! ps_run "cd $WIN_DIR; python -X utf8 -m pytest -q tests/test_ai_council.py"; then
    echo "!! TESTS FAILED — rolling back"
    ps_run "cd $WIN_DIR; Copy-Item '$BK/ai_council.py' ai_council.py -Force; Copy-Item '$BK/test_ai_council.py' tests/test_ai_council.py -Force"
    echo "Rolled back to $BK"; exit 1
  fi
  echo "-- smoke: /health"
  ps_run "cd $WIN_DIR; python -X utf8 ai_council.py respond /health" | tail -5
  echo "-- smoke: 'chce jedzenie' przez respond-b64 (oczekiwane: 1 pytanie, zero route=)"
  B64=$(printf 'chce jedzenie' | base64)
  OUT=$(ps_run "cd $WIN_DIR; python -X utf8 ai_council.py respond-b64 --b64 $B64")
  echo "$OUT"
  if echo "$OUT" | grep -qE '^\s*(route=|audit_log=)'; then echo "!! DEBUG TAIL LEAK — sprawdź"; exit 1; fi
  echo
  echo "OK. Backup: $WIN_DIR/$BK . Listener przejmie nowy kod przy następnym cyklu/restarcie taska"
  echo "(restart taska 'Bartek AI Council Telegram' — tylko za Twoją decyzją)."
}

phase_rollback() {
  BK="backups/$1"
  echo "== PHASE 3: rollback from $WIN_DIR/$BK =="
  ps_run "cd $WIN_DIR; Copy-Item '$BK/ai_council.py' ai_council.py -Force; Copy-Item '$BK/test_ai_council.py' tests/test_ai_council.py -Force"
  ps_run "cd $WIN_DIR; python -X utf8 -m pytest -q tests/test_ai_council.py" || true
  echo "Done."
}

case "${1:-}" in
  --apply)    phase_diff; echo; read -r -p "Kontynuować APPLY? [y/N] " a; [ "$a" = "y" ] && phase_apply || echo "Przerwano.";;
  --rollback) shift; [ -n "${1:-}" ] || { echo "Podaj nazwę backupu (np. pre-L4.94-20260609-120000)"; exit 2; }; phase_rollback "$1";;
  *)          phase_diff;;
esac
