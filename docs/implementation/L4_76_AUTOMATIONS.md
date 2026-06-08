# L4.76 — Automations (recurring actions)

Date: 2026-06-08 · Owner: Claude Opus 4.8 · Status: LANDED + DEPLOYED + LIVE (385 passed).
Poke "Automations" — cykliczne AKCJE (nie tylko tekst). Autonomiczne, zero auth.

## Co robi
- `/automate <schedule> <komenda>` (np. `/automate daily 09:00 /gh issues`, `/automate weekly mon 09:00 /agent`) — gdy nadejdzie czas, system URUCHAMIA komendę i wysyła wynik z prefiksem „🤖 Automatyzacja".
- `/automations` (lista) · `/automations cancel <id>`.
- Reużywa scheduler przypomnień (L4.73) + naturalny parser czasu (L4.73.1).

## Bezpieczeństwo (kluczowe)
`automation_command_safe` — **explicit allowlist read/think**: @research, /flow, /council, /brief, /status, /agent, /cost, /loops, /health, /front, /errors, /improvements, oraz `/gh issues|list` i `/memory facts|recent|search|pending`. **Nigdy write/execute** (/fs commit, /gh issue create, /memory save, provider execute są odrzucane). Walidacja przy dodawaniu I przy uruchomieniu.

## Tests (AutomationTests, 4)
allowlist (safe vs unsafe), add safe/unsafe, runs-when-due (build_response patched), lista oddzielona od przypomnień.

## Verification
- Mac + Windows: **385 passed**.
- Live: `/automate daily 09:00 /gh issues` → „Automatyzacja ✅ (aut-…)"; `/automations` listuje.

## Follow-up
L4.76.1: naturalny język ("codziennie rano rób research o X"); automatyzacje async (research jako background task z dostawą wyniku).
