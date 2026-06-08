# L4.92 — iMessage TWO-WAY (inbound) LIVE

Date: 2026-06-08 · Owner: Claude Opus 4.8 · Status: LIVE + verified end-to-end (448 tests). Bartek granted FDA.

Bartek napisał „zrobione fda". Dwukierunkowy iMessage **działa**: Bartek pisze na wątek
„do siebie" → asystent odpowiada (jak Telegram). Zweryfikowane na żywo (reply do msg 596,
zero pętli, kursor 597).

## Jak działa (cały tor)
Mac runner (`~/.ai_council/imessage_bridge.py`, launchd) co 15 s robi:
1. **Outbound** (jak L4.89): pull host outbox → osascript send → ack. Każdą wysyłkę zapisuje
   do `~/.ai_council/imessage_sent_texts.jsonl` (anti-loop).
2. **Inbound** (NOWE): czyta `chat.db` (Full Disk Access) **tylko z wątku self** (chat o
   identyfikatorze == AI_COUNCIL_IMESSAGE_TO), bierze nowe wiadomości `ROWID > kursor`,
   dekoduje tekst, pomija własne echa (dedup po treści vs sent-log), a realne wiadomości
   Bartka forwarduje na host przez `respond-b64` (base64 → quote-safe) i odsyła odpowiedź.

## Bezpieczeństwo / prywatność (kluczowe decyzje)
- **Tylko self-chat**: z 74 rozmów w chat.db czytamy WYŁĄCZNIE wątek `bdomanskyy@icloud.com`.
  Pozostałych 73 konwersacji Bartka most NIGDY nie dotyka.
- **Anti-loop**: w wątku self wiadomości Bartka i asystenta mają `is_from_me=1` (ten sam
  Apple ID), więc rozróżniamy po treści — reply zapisujemy do sent-log PRZED wysłaniem.
  Zweryfikowane: reply (597) nie został przetworzony ponownie.
- **Brak replay historii**: kursor startuje na bieżącym max ROWID; tylko nowe wiadomości.
- **FDA**: budowane i testowane dopiero PO zgodzie Bartka — nie czytaliśmy historii bez zgody.

## attributedBody decoder (macOS 26.5.1)
Na nowym macOS tekst jest w blobie `attributedBody` (kolumna `text`=NULL). Dekoder:
`NSString` + class-chain + `0x2b` + długość (1B, lub `0x81`+2LE / `0x82`+4LE) + UTF-8.
**Zwalidowany 93/93 exact** względem kolumny `text` na żywym chat.db.

## Pliki
- `ai_council.py`: `imessage_decode_attributed_body`, `imessage_message_text`,
  `imessage_is_assistant_echo`, `imessage_norm_text`; CLI `respond-b64` (quote-safe relay).
- `scripts/mac_imessage_bridge_standalone.py`: + sent-log, decoder, self-chat resolve,
  kursor, `inbound_cycle`; outbound zapisuje sent-log.
- Lokalnie: `~/.ai_council/imessage_bridge.py`, plist + env z `AI_COUNCIL_IMESSAGE_INBOUND=true`.
- Stan: `~/.ai_council/imessage_sent_texts.jsonl`, `~/.ai_council/imessage_inbound_cursor`.

## Tests (IMessageInboundReaderTests, 12 nowych / 448)
decoder short/long(0x81)/unicode/garbage; message_text fallback; dedup echo/normalize/empty.
Plus walidacja dekodera 93/93 na realnym chat.db i live E2E (reply do 596, brak pętli).

## Operacje
- Log: `~/Library/Logs/ai_council_imessage.log` (id/status, „inbound replied to N").
- Wyłącz inbound: usuń `AI_COUNCIL_IMESSAGE_INBOUND` z plist/env + reload, albo unload agenta.
