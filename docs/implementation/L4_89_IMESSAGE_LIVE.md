# L4.89 — iMessage channel LIVE + persistent (launchd) + relay bug fixes

Date: 2026-06-08 · Owner: Claude Opus 4.8 · Status: LIVE on Bartek's Mac+Windows (432 tests green).

Bartek powiedział „dawaj imessage". Kanał iMessage jest teraz **realnie żywy i trwały** —
asystent pisze do Bartka na iMessage (jak Telegram), proaktywnie (briefy/nudge).

## Co działa teraz
- **Odbiorca (self-channel)**: `bdomanskyy@icloud.com` — auto-wykryty z lokalnego konta iCloud
  (`defaults read MobileMeAccounts`), usługa MESSAGES aktywna. Bartek nie musiał podawać numeru.
- **TCC Automation**: już było przyznane (rc=0 na `service whose service type = iMessage`). Zero klików.
- **Wysyłka**: przez Messages.app (osascript), realnie dostarczone (potwierdzone live).
- **Cross-host relay**: Windows host enqueue → Mac runner pull (SSH) → osascript send → ack. Działa E2E.
- **Trwałość**: launchd LaunchAgent `com.bartek.aicouncil.imessage` (RunAtLoad + KeepAlive) →
  runner wstaje po reboot/login, sam drenuje outbox co 15 s.
- **Proaktywność**: `AI_COUNCIL_IMESSAGE_PROACTIVE=true` na hoście → briefy/nudge lecą też na iMessage.

## Kluczowy gotcha macOS (rozwiązany)
LaunchAgent NIE może odpalić skryptu spod `~/Documents` — TCC blokuje launchd bez Full Disk
Access („Operation not permitted"). Dlatego runner jest **standalone, poza repo**:
`~/.ai_council/imessage_bridge.py` (kopia `scripts/mac_imessage_bridge_standalone.py`) — nic nie
importuje z repo, tylko SSH pull/ack + osascript send. Env w pliku LaunchAgent (lokalnie).

## Dwa bugi naprawione (powodowały spam!)
1. **ack quoting**: `--detail "..."` zagnieżdżone w hostowym `powershell -Command "..."` psuło
   argparse na Windows → ack nigdy się nie zapisywał → wiadomość zostawała „pending" →
   runner wysyłał ją CO CYKL (spam duplikatów). Fix: ack bez `--detail` (status wystarcza;
   detail trzymany w logu runnera na Macu). Poprawione w obu mostach.
2. **cold-start timeout**: pierwszy AppleEvent po bezczynności Messages bywa wolny; `timeout=20/25`
   padał na pierwszej wysyłce. Fix: `applescript_run` 20→60 s; standalone send 25→60 s.

## Architektura (kto co robi)
- Windows (`D:\ai-council`, serve --send): jedyne źródło prawdy; enqueue do `state/imessage_outbox.jsonl`.
- Mac (`~/.ai_council/imessage_bridge.py` pod launchd): pull → send (Messages.app) → ack.
- Bartek dostaje iMessage „do siebie" na iPhonie (Apple sync), tak jak w Poke.

## Pliki
- `scripts/mac_imessage_bridge_standalone.py` (NOWY) — launchd-safe runner (poza ~/Documents).
- `scripts/mac_imessage_bridge.py` — ack quoting fix (host_ack bez --detail).
- `scripts/mac_imessage_bridge_run.sh` (NOWY) — launcher (gdy repo poza Documents).
- `ai_council.py` — `applescript_run` timeout 60 s.
- Lokalnie (nie w repo): `~/.ai_council/imessage_bridge.py`, `~/Library/LaunchAgents/com.bartek.aicouncil.imessage.plist`,
  `~/.ai_council_imessage.env`. Hosta: `AI_COUNCIL_IMESSAGE_PROACTIVE=true` w realnym `.env`.

## Operacje
- Status: `launchctl list | grep aicouncil` · log: `~/Library/Logs/ai_council_imessage.log` (tylko id/status).
- Stop: `launchctl unload ~/Library/LaunchAgents/com.bartek.aicouncil.imessage.plist`.
- Start: `launchctl load -w ...`.

## NIE zrobione (następna warstwa) — INBOUND dwukierunkowy
Teraz kanał jest OUTBOUND (asystent → Bartek). Pełne dwukierunkowe iMessage (Bartek pisze na
iMessage → asystent odpowiada, jak Telegram) wymaga czytania przychodzących z `~/Library/Messages/chat.db`
(Full Disk Access) na Macu i forwardu do hosta. To osobny build.

## Bezpieczeństwo / uwaga
Podczas diagnozy `.env` (realny: `C:\Users\Komputer\.config\ai-council\.env`) został raz wypisany
z sekretami do sesji. Rekomendacja: rotacja TELEGRAM_BOT_TOKEN / XAI_API_KEY / GITHUB_TOKEN jeśli
transkrypt może być widziany przez osoby trzecie.
