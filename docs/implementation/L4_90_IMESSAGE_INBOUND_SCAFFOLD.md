# L4.90 — iMessage inbound (two-way) scaffolding + FDA gate

Date: 2026-06-08 · Owner: Claude Opus 4.8 · Status: SCAFFOLDED + GATED (438 tests). Live build needs Bartek's FDA grant.

Outbound iMessage jest live (L4.89). Dwukierunkowy (Bartek pisze → asystent odpowiada,
jak Telegram) wymaga czytania `~/Library/Messages/chat.db` na Macu, co potrzebuje
**Full Disk Access** (jednorazowa zgoda użytkownika). Bez FDA nie da się ani zbudować, ani
przetestować odczytu — i celowo NIE czytamy historii wiadomości Bartka bez zgody.

## Co dodane (bezpieczne, testowalne, OFF)
- `imessage_inbound_enabled()` — flaga `AI_COUNCIL_IMESSAGE_INBOUND` (default off).
- `imessage_full_disk_access()` — probe: próbuje read-only `chat.db` → bool. Na Macu Bartka: **NIE**.
- `apple_date_to_unix()` — konwersja `date` z chat.db (ns/​s od 2001-01-01) na unix (testowane).
- `imessage_inbound_status()` + `/imessage inbound` — pokazuje stan i DOKŁADNĄ instrukcję FDA.

## Dlaczego nie zbudowane na żywo
- macOS 26.5.1 → tekst wiadomości jest w blobie `attributedBody` (kolumna `text` = NULL).
  Solidny dekoder trzeba walidować na realnych danych — niemożliwe bez FDA.
- Self-thread (kanał „do siebie"): wiadomości Bartka i asystenta mają `is_from_me=1` (ten sam
  Apple ID) → rozróżnienie wymaga dedup po treści względem logu wysłanych (anti-loop). Do
  zaprojektowania i przetestowania na realnym chat.db po FDA.

## Następny krok (po `zrobione FDA`)
1. Standalone `mac_imessage_inbound.py` (poza ~/Documents, jak outbound): kursor po ROWID,
   dekoder attributedBody, dedup anti-loop, forward `respond` do hosta, reply przez outbox.
2. Testy logiki (dedup, kursor, dekoder na syntetycznym blobie) + test E2E na realnym DB.
3. Gate `AI_COUNCIL_IMESSAGE_INBOUND=true` + osobny LaunchAgent z FDA.

## Tests (IMessageInboundScaffoldTests, 6 / 438)
off-by-default; apple_date ns/s/bad; FDA false off-macOS; status guides FDA gdy brak; status
ready gdy FDA; `/imessage inbound` routuje.
