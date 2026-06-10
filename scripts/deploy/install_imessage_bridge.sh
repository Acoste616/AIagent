#!/bin/bash
# AI Council — installer for the CANONICAL Mac iMessage bridge (audit 2.3).
#
# Single source of truth: scripts/mac_imessage_bridge_standalone.py in the repo.
# This installs it to ~/.ai_council/imessage_bridge.py (outside ~/Documents so a
# launchd LaunchAgent can run it without Full Disk Access) and (re)loads the
# LaunchAgent. Re-run after every bridge change; `--check` only diffs.
#
# Env lives in ~/.ai_council_imessage.env (never committed). Required keys:
#   AI_COUNCIL_IMESSAGE_ENABLED=true
#   AI_COUNCIL_IMESSAGE_TO="+48XXXXXXXXX"          # PRIMARY: phone-number thread
#   AI_COUNCIL_IMESSAGE_IDS="+48XXXXXXXXX,me@icloud.com"  # threads the bridge reads
#   AI_COUNCIL_IMESSAGE_INBOUND=true
# Host-side allowlist (Windows .env): AI_COUNCIL_IMESSAGE_ALLOWED_SENDERS must
# list the same handles, otherwise respond-b64 denies the relay.
set -euo pipefail

REPO_DIR="$(cd "$(dirname "$0")/../.." && pwd)"
SRC="$REPO_DIR/scripts/mac_imessage_bridge_standalone.py"
DEST_DIR="$HOME/.ai_council"
DEST="$DEST_DIR/imessage_bridge.py"
WRAPPER="$DEST_DIR/imessage_bridge_run.sh"
ENV_FILE="$HOME/.ai_council_imessage.env"
LABEL="com.bartek.aicouncil.imessage"
PLIST="$HOME/Library/LaunchAgents/$LABEL.plist"

if [ "${1:-}" = "--check" ]; then
    if [ -f "$DEST" ] && cmp -s "$SRC" "$DEST"; then
        echo "OK: deployed bridge == repo ($DEST)"
        exit 0
    fi
    echo "DRIFT: $DEST differs from repo (or missing). Run without --check to install."
    diff -u "$DEST" "$SRC" 2>/dev/null | head -40 || true
    exit 1
fi

mkdir -p "$DEST_DIR"
if [ -f "$DEST" ] && cmp -s "$SRC" "$DEST"; then
    echo "bridge already up-to-date: $DEST"
else
    cp "$SRC" "$DEST"
    echo "bridge installed: $DEST"
fi

cat > "$WRAPPER" <<'WRAP'
#!/bin/bash
# Sources the private channel env, then runs the canonical bridge (launchd-safe).
set -a
[ -f "$HOME/.ai_council_imessage.env" ] && . "$HOME/.ai_council_imessage.env"
set +a
exec /usr/bin/python3 "$HOME/.ai_council/imessage_bridge.py"
WRAP
chmod +x "$WRAPPER"

if [ ! -f "$ENV_FILE" ]; then
    cat > "$ENV_FILE" <<'ENVT'
# AI Council iMessage bridge env (private — never commit)
AI_COUNCIL_IMESSAGE_ENABLED=true
AI_COUNCIL_IMESSAGE_TO=""
AI_COUNCIL_IMESSAGE_IDS=""
AI_COUNCIL_IMESSAGE_INBOUND=true
AI_COUNCIL_IMESSAGE_INTERVAL=15
ENVT
    chmod 600 "$ENV_FILE"
    echo "TEMPLATE env created: $ENV_FILE — fill AI_COUNCIL_IMESSAGE_TO/IDS before starting"
fi

if [ ! -f "$PLIST" ] || [ "${1:-}" = "--force-plist" ]; then
    cat > "$PLIST" <<PL
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key><string>$LABEL</string>
    <key>ProgramArguments</key>
    <array><string>/bin/bash</string><string>$WRAPPER</string></array>
    <key>RunAtLoad</key><true/>
    <key>KeepAlive</key><true/>
    <key>StandardOutPath</key><string>$HOME/Library/Logs/ai_council_imessage.log</string>
    <key>StandardErrorPath</key><string>$HOME/Library/Logs/ai_council_imessage.log</string>
</dict>
</plist>
PL
    echo "LaunchAgent plist written: $PLIST"
fi

launchctl bootout "gui/$(id -u)" "$PLIST" 2>/dev/null || true
launchctl bootstrap "gui/$(id -u)" "$PLIST"
echo "LaunchAgent (re)loaded: $LABEL"
echo "log: ~/Library/Logs/ai_council_imessage.log"
