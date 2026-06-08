# L4.83 — /setup onboarding checklist (Poke-style)

Date: 2026-06-08 · Owner: Claude Opus 4.8 · Status: LANDED + DEPLOYED (418 passed).

Poke ma onboarding; my mieliśmy rozproszone flagi. `/setup` (alias `/onboarding`,
naturalnie „co podłączyć"/„konfiguracja") czyta **żywy config** i pokazuje z telefonu,
co działa, co jest gotowe i czeka na 1 ruch usera, a co niepodłączone — każde z konkretną
akcją. Read-only, zero ryzyka.

## Sekcje
- **Kanały:** Telegram, iMessage (status mostu), Mail.app.
- **Integracje:** Google (Gmail/Cal/Drive), GitHub (read/write), Notion/Linear/Spotify/Slack (todo).
- **Mózg:** router intencji (Grok), poranny brief, pamięć/auto-fakty.
- **NEXT:** wybiera jeden najważniejszy brakujący krok (iMessage → Google → reszta).
- Legenda: ✅ działa · 🔒 gotowe, czeka na Twój 1 ruch · ⚪ niepodłączone.

## Anchors
`setup_response` + `_setup_mark` (przed `raw_operator_response`); `/setup` w `route_text`,
`build_response`, `natural_intent_route`.

## Tests (SetupOnboardingTests, 3 / 418 total)
listuje kanały+integracje+NEXT; routuje explicit i naturalnie („co podłączyć"); dispatch w build_response.

## Dlaczego to parytet
Reszta luk Poke (Gmail/Notion/iMessage TCC/budżety/preferencje) to akcje **usera**. `/setup`
zamienia je w klikalną listę zadań zamiast ukrytych flag — to onboarding, którego brakowało.
