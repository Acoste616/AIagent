# L4.82 — macOS native messaging bridge (iMessage + Mail), the OpenPoke path

Date: 2026-06-08 · Owner: Claude Opus 4.8 · Status: LANDED, ARMED-but-OFF (411 passed).

Domyka realnie lukę „iPhone/iMessage layer" **bez OAuth i bez Apple Business approval** —
tak jak robi to OpenPoke: wysyłka przez **Messages.app / Mail.app na Macu, jako zalogowany
Bartek**, sterowane AppleScriptem (`osascript`).

## Co robi
- `imessage_send(text, to=self)` — wysyła iMessage przez Messages.app. Domyślny odbiorca =
  **self** (Apple ID/numer Bartka z `AI_COUNCIL_IMESSAGE_TO`) → to kanał asystent→user,
  parity z listenerem Telegrama. Wysyłka do **osoby trzeciej** zostaje akcją zewnętrzną
  za approval/Risk Officer (komenda `/imessage` celowo NIE wystawia odbiorcy — zawsze self).
- `mail_send(subject, body, to)` — wysyłka maila przez Mail.app jako Bartek (alternatywa dla
  Gmail OAuth). Akcja zewnętrzna → gated + przyszły approval.
- `applescript_run` / `applescript_quote` / `on_macos` — bezpieczne prymitywy (redakcja
  sekretów, escape stringów, timeout → czytelny komunikat o TCC).
- `/imessage` (alias `/imsg`): `status` (domyślnie) pokazuje stan mostu; `test` wysyła ping
  do self; `<tekst>` wysyła tekst do self.
- `/health`: `imessage_bridge=L4.82:<status>` + `mail_bridge=<status>`.

## Bezpieczeństwo / domyślne OFF
- **ARMED, ale OFF**: `AI_COUNCIL_IMESSAGE_ENABLED` i `AI_COUNCIL_MAIL_ENABLED` domyślnie
  false → nic nie wyśle, dopóki Bartek nie włączy. Testy wymuszają off (conftest).
- ai_council działa na **Windows**; `osascript` jest tylko na macOS. Poza macOS prymitywy
  zwracają `bridge_required` zamiast próbować cokolwiek wysłać. Deploy na Windows jest
  bezpieczny (most nieaktywny, dochodzi tylko komenda + linia w /health).
- Sekrety redagowane w outpcie osascript.

## Co potrzeba do GO-LIVE (jedyne akcje usera — bez OAuth)
1. **Jeden klik macOS TCC**: Ustawienia → Prywatność i bezpieczeństwo → Automatyzacja →
   zezwól Terminal/osascript na sterowanie **Messages** (i **Mail**). To powód timeoutu
   `-1712` w teście rozpoznawczym.
2. `AI_COUNCIL_IMESSAGE_TO=<Apple ID/numer Bartka>` + `AI_COUNCIL_IMESSAGE_ENABLED=true`.
3. Most musi działać **na Macu** (Messages.app jest tam zalogowany). Otwarta decyzja
   architektury: (A) lekki komponent ai_council w trybie „messages bridge" na Macu drenujący
   outbox z hosta po Tailscale, albo (B) Windows→Mac SSH relay (odwrotny kierunek do
   istniejącego `ai-council-desktop`). Prymityw wysyłki jest gotowy w obu wariantach.

## Anchors
`IMESSAGE_BRIDGE_VERSION` + `on_macos`/`applescript_quote`/`applescript_run`/`imessage_*`/
`mail_*`/`imessage_response` (przed `raw_operator_response`), `/imessage` w `route_text` +
`build_response`, linia w `health_response`.

## Tests (IMessageBridgeTests, 10 / 411 total)
quote-escape, gated-off-by-default (iMessage+Mail), wymaga odbiorcy, buduje AppleScript i woła
osascript (mock), off-macOS→bridge_required, status text, /imessage routes+dispatch, /imessage
<text> idzie do self (nie do osób trzecich), /health raportuje most.

## Verification
- Mac + Windows: pytest zielony (411). py_compile OK.
- Rozpoznanie środowiska: Messages.app i Mail.app obecne na Macu; `osascript` → `-1712`
  (czeka na klik TCC Automation) — potwierdza ścieżkę OpenPoke.

## Cross-host relay (wybrana architektura A — reużywa istniejący SSH Mac→host)
Host (Windows) ENQUEUE → Mac runner DRAIN+SEND → ACK z powrotem. Single source of truth na hoście.
- ai_council (host): `imessage_outbox_enqueue` / `imessage_outbox_pending` / `imessage_outbox_ack`
  (JSONL: `state/imessage_outbox.jsonl` + `state/imessage_sent.jsonl`, idempotencja po id).
- CLI: `imessage-outbox-dump` (Mac pulluje), `imessage-outbox-enqueue`, `imessage-outbox-ack`.
- `/imessage <tekst>` kolejkuje do self; `/imessage outbox` pokazuje kolejkę.
- Mac runner: `scripts/mac_imessage_bridge.py` — pulluje outbox przez `ssh ai-council-desktop`,
  wysyła lokalnie przez `imessage_send` (osascript), acku­je. `--once` albo `--interval N`.
  Rdzeń logiki (`imessage_drain_rows`) jest w ai_council.py i otestowany.
- Round-trip zweryfikowany lokalnie: enqueue → dump → ack → dump=[].

## Follow-up
- Odbiór iMessage (read `~/Library/Messages/chat.db`) wymaga Full Disk Access — osobny TCC.
- Po kliknięciu TCC + `AI_COUNCIL_IMESSAGE_ENABLED=true` + `AI_COUNCIL_IMESSAGE_TO`:
  `python3 scripts/mac_imessage_bridge.py --interval 15` na Macu = żywy kanał. Smoke: `/imessage test`.
