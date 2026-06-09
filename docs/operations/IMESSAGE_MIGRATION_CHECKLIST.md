# iMessage Full-Migration Checklist — "przenoszę się w pełni na iMessage"

Date: 2026-06-09 · Goal: Bartek rozmawia z agentem wyłącznie przez iMessage; Telegram zostaje
jako fallback. Stan kodu: L4.94 na Macu (Claude front + thread memory + auto-facts + zero debug).

## Gate 1 — Deploy L4.93+L4.94 na Windows (wymaga Bartka)

```bash
cd <mac-repo>
chmod +x scripts/deploy/deploy_l494_from_mac.sh
./scripts/deploy/deploy_l494_from_mac.sh           # diff only — sprawdź czy Windows nie ma zmian spoza repo
./scripts/deploy/deploy_l494_from_mac.sh --apply   # backup -> sync -> testy -> smoke (auto-rollback)
```

Jeśli diff pokaże zmiany TYLKO po stronie Windows — najpierw przenieś je do repo (nie nadpisuj ślepo).

## Gate 2 — Konfiguracja Windows .env (C:\Users\Komputer\.config\ai-council\.env)

Nic nie jest wymagane (defaulty = Claude front), ale sprawdź/poznaj przełączniki:

| Klucz | Wartość docelowa | Po co |
|---|---|---|
| `AI_COUNCIL_POKE_CHAT_OPERATOR` | (brak/`claude`) | Claude jako głos frontu |
| `AI_COUNCIL_POKE_CHAT_CLAUDE_ALL_CHAT` | (brak/`true`) | krótkie naturalne wiadomości → żywa odpowiedź |
| `AI_COUNCIL_IMESSAGE_PROACTIVE` | `true` (decyzja Bartka) | nudges/proactive też do iMessage (przez outbox; Mac wysyła) |
| `AI_COUNCIL_RESPOND_DEBUG_TAIL` | brak (off) | debug tail tylko do diagnostyki |
| `AI_COUNCIL_POKE_CHAT_CLAUDE_TIMEOUT` | 90 (zmniejsz przy wolnych odpowiedziach) | latencja |
| `AI_COUNCIL_POKE_CHAT_CLAUDE_MODEL` | opcjonalnie lżejszy model | latencja/koszt |

Edycja .env = sekrety: robi ją Bartek (albo `set-secret` dla kluczy z allowlisty).

## Gate 3 — Mac bridge sanity

```bash
launchctl print gui/$(id -u)/com.bartek.aicouncil.imessage | grep -E "state|last exit"
tail -40 ~/Library/Logs/ai_council_imessage.log
diff ~/.ai_council/imessage_bridge.py <mac-repo>/scripts/mac_imessage_bridge_standalone.py
```

Deployowana kopia bridge'a musi odpowiadać `scripts/mac_imessage_bridge_standalone.py`
(używa `respond-b64`, który po L4.94 ma pamięć wątku i scrub).

## Gate 4 — Live smoke (5 wiadomości z iPhone'a)

| # | Wyślij | Oczekiwane |
|---|---|---|
| 1 | `hej` | krótki ACK, natychmiast, bez LLM |
| 2 | `chce jedzenie` | JEDNO pytanie (lokalizacja/kuchnia/budżet) + propozycja defaultu |
| 3 | odpowiedz na pytanie z #2 | kontynuacja wątku (pamięć!), bez proszenia o kontekst |
| 4 | `zrob research co nowego w agentach AI` | Grok research path, task/artifact |
| 5 | dowolna | ZERO `route=`, `audit_log=`, `[Claude]`, JSON-ów |

Latencja #2–#3: cel < 20 s. Jeśli gorzej → Gate 2 (timeout/model/kill-switch).

## Gate 5 — Proaktywność (opcjonalnie, po Gate 4)

Włącz `AI_COUNCIL_IMESSAGE_PROACTIVE=true` → nudges o utkniętych taskach i proactive pings
wychodzą też na iMessage. Morning brief: następny sprint loopa (recipe + scheduled enqueue).

## Rollback

`./scripts/deploy/deploy_l494_from_mac.sh --rollback pre-L4.94-<timestamp>`
albo flagi: `AI_COUNCIL_POKE_CHAT_OPERATOR=grok`, `AI_COUNCIL_POKE_CHAT_CLAUDE_ALL_CHAT=false`.

## Definicja "przeniesione w pełni"

- [ ] Gate 1–4 zaliczone
- [ ] 24 h normalnego użycia iMessage bez sięgania po Telegram
- [ ] zero debug leaks w 24 h (`/front` czysty, front_quality bez `debug_metadata`)
- [ ] proaktywny ping dotarł na iMessage (Gate 5)
