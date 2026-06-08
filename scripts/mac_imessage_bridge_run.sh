#!/bin/bash
# AI Council — Mac iMessage bridge launcher (L4.89).
#
# Loads the channel env from ~/.ai_council_imessage.env (kept OUT of the repo so
# the recipient/Apple ID is never committed), then runs the outbox drain loop.
# The loop pulls pending rows from the Windows host over SSH and sends each via
# the logged-in Messages.app (osascript). Logs ids/status only — never bodies.
#
# Used by the launchd LaunchAgent (com.bartek.aicouncil.imessage) and runnable by
# hand for debugging:  bash scripts/mac_imessage_bridge_run.sh
set -a
[ -f "$HOME/.ai_council_imessage.env" ] && . "$HOME/.ai_council_imessage.env"
set +a
cd "$(dirname "$0")/.." || exit 1
exec /usr/bin/python3 scripts/mac_imessage_bridge.py --interval "${AI_COUNCIL_IMESSAGE_INTERVAL:-15}"
