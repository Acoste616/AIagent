# Session Handoff — 2026-06-10 (dla następnej rozmowy)

## Stan: DZIAŁA NA PRODUKCJI (L4.99)

Bartek pisze w iMessage (dowolny ze swoich dwóch wątków-do-siebie: numer +48573465367 albo
bdomanskyy@icloud.com) → most na Macu czyta OBA wątki i **odpowiada w tym, z którego przyszła
wiadomość**. Głosem jest **Claude** (CLI, subskrypcja Max, $0/wiadomość), Grok = fallback +
research, Codex = worker. Telegram = kanał zapasowy.

## Architektura (co jest czym i po co)

| Element | Gdzie | Po co |
|---|---|---|
| `ai_council.py` (~18k linii) | repo + `D:\ai-council\` (produkcja) | cały runtime: routing, Conversation Brain, operatorzy, pamięć, akcje/approval, koszty |
| Conversation Brain | w ai_council.py | clarify-before-act (food/coding sloty), intencje, `brain_decide` = dyspozytor: **Claude→Grok**; narzędzia brain: przypomnienia, fakty, recall, research, kod |
| Most iMessage | `~/.ai_council/imessage_bridge.py` (Mac) + LaunchAgent `com.bartek.aicouncil.imessage` | co 15 s: wysyła outbox z Windows + czyta inbound z `chat.db` (oba uchwyty, env `AI_COUNCIL_IMESSAGE_IDS`), woła `respond-b64` na Windows przez SSH, odpowiada w wątku nadawcy |
| Listener Telegram | scheduled task `Bartek AI Council Telegram` (Windows) | pętla pollingu Telegrama; restart = kill python + `schtasks /Run` |
| Pamięć Hermes | `state/memory.sqlite` + conversations.jsonl (Windows) | fakty (auto-extract quarantine → `/memory pending`), pamięć wątku (iMessage+Telegram = jeden kontekst), preferencje |
| Akcje/approval | `state/actions.jsonl` | risk gates R0–R4; `/approve`/`/deny`; `order_handoff` (draft zamówienia → link, zero płatności); `/undo <plik>` cofa zatwierdzone zapisy |
| Logi/diagnostyka | `~/Library/Logs/ai_council_imessage.log` (Mac), `D:\ai-council\logs|errors|state\costs.jsonl` | `inbound replied to N in <wątek>` = żywy dowód; costs: `detail="brain claude"` |

## Dostęp do Desktopa (Windows)

- Z Maca: `ssh ai-council-desktop` (alias w `~/.ssh/config`, klucz `~/.ssh/codex_ed25519`,
  host `desktop-dk4hiv0.taild2cfba.ts.net` / `100.101.53.21` przez Tailscale, user `Komputer`).
- Produkcja: `D:\ai-council`. Env (sekrety): `C:\Users\Komputer\.config\ai-council\.env`.
- Typowe komendy: `python -X utf8 ai_council.py doctor | respond /health | respond-b64 --b64 <b64>`;
  testy: `python -X utf8 -m pytest -q tests/test_ai_council.py`.
- UWAGA: gdy Desktop śpi/offline (Tailscale "offline"), iMessage NIE odpowiada — obudzić maszynę.
  Backupy deployów: `D:\ai-council\backups\pre-L4.97|pre-L4.98`.
- Z sesji Cowork: dostęp przez plugin Desktop Commander (shell na Macu → ssh dalej).

## Co weszło w tej sesji (L4.93→L4.99, wszystko na GitHub `Acoste616/AIagent` main)

1. L4.93/94: Claude front + zero debug-leaków (`route=`/`audit_log=` usunięte; opt-in
   `AI_COUNCIL_RESPOND_DEBUG_TAIL`), pamięć wątku iMessage + auto-fakty w `respond_b64_reply`.
2. L4.95: `/undo` — snapshot przed każdym approved workspace write.
3. L4.96: ORDER_DRAFT → draft zamówienia z linkiem po `/approve` (bez płatności, bez udawania).
4. L4.97: merge produkcyjnego Conversation Brain (Windows był przed repo!) + deploy.
5. L4.98: **Claude głosem brain** (protokół `TOOL:`), Grok fallback; potwierdzone w costs (13 s, $0).
6. L4.99: most czyta oba wątki self-konwersacji i odpowiada w wątku nadawcy (fix "nie odpowiada
   / dwa wątki" — iPhone wysyła raz z numeru, raz z emaila; `is_from_me=1`, dedup po sent-log).

Testy: 497/497 Mac i Windows. Dokumentacja iteracji: `docs/agent-loop/LOOP_2026-06-09_*.md`.

## Następne kroki (kolejka loopa)

1. Obserwacja 24 h: latencja głosu (~19 s e2e; ew. lżejszy model `AI_COUNCIL_POKE_CHAT_CLAUDE_MODEL`),
   errors_24h, dublowanie brain-food-flow vs ORDER_DRAFT.
2. Proaktywność: `AI_COUNCIL_IMESSAGE_PROACTIVE=true` w .env na Windows (morning brief L4.72 +
   nudges pójdą na iMessage) — jedna linia, wymaga zgody/ręki Bartka (sekrety w .env).
3. Watchdog na sen Desktopa + powiadomienie z Maca, iOS Shortcuts (głos/screenshot/share sheet),
   OpenClaw hands etap 2 (plan/execute/verify na realnych projektach), council E2E.

## Zasady (niezmienne)

Bez zgody Bartka: GitHub push (ta sesja: zgoda była, wykonane), deploy/restart (zgoda była),
sekrety/.env, OAuth/integracje Google, external writes, płatności, kasowanie, kontakt z ludźmi,
nowe daemony. Wysyłka iMessage do Bartka = OK (self-channel). Przy wysyłce z Maca poza mostem:
najpierw dopisać tekst do `~/.ai_council/imessage_sent_texts.jsonl` (anty-echo!).
