# L4.85 — Topic watchlist + Bartek profile (from context answers)

Date: 2026-06-08 · Owner: Claude Opus 4.8 · Status: LANDED + DEPLOYED (429 passed).

Pierwsza warstwa zbudowana **z odpowiedzi Bartka** na pytania kontekstowe. Domyka część
„fully configured operational behavior": asystent zna stałe preferencje Bartka i śledzi
jego tematy researchu.

## Profil Bartka (7a) → trwała pamięć
`seed_bartek_profile()` zapisuje stałe fakty jako zaufane (`source=host_user`, supersede):
strefa Europe/Warsaw, imię Bartek/Bartosz, projekt Agent OS/AIagent, polityka „drafty
najpierw → approval", cisza 23–07, brief 8:00, workspace D:\ai-council / openclaw-export,
kanał Telegram/iPhone→iMessage. CLI: `python ai_council.py seed-profile` (odpalone na hoście).
Asystent ma to teraz w `memory_context_for_prompt` → „Co wiem o Tobie".

Uwaga: brief 8:00 Warsaw i cisza 23–07 Warsaw **już były defaultem** (6 UTC / 21–05 UTC),
więc tu tylko utrwalamy je jako pamięć, bez zmiany configu.

## Watchlist tematów (4b)
12 domyślnych tematów Bartka: Poke, OpenClaw, Hermes, AI agents, Codex, Claude Code,
Grok/xAI, OpenAI, Wdroz.AI, automations, iPhone/iMessage agents, local AI execution.
- Stan w `state/watch_topics.json`; `watch_topics()` nigdy nie zwraca pustki (fallback do defaults).
- `/watch` (alias naturalny „tematy"/„śledź X"): list · add · remove · reset · clear · research.
- `/watch research [temat]` → **on-demand** Grok X+web research (czysty po L4.79). Bez tematu =
  jeden zbiorczy research po wszystkich tematach. **Brak auto-researchu dziennego** — cost-aware (6c).
- Widoczne w `/setup`.

## Bezpieczeństwo / koszt
- `/watch` w READONLY_RECIPE_COMMANDS + FRONT_QUALITY_TECHNICAL_COMMANDS, ale **świadomie NIE**
  w LLM_ROUTER_ALLOWED_COMMANDS — żeby router nie odpalał Grok researchu z luźnej wiadomości.
- Research tylko explicite (`/watch research`), więc zero niespodziewanych kosztów.

## Anchors
`DEFAULT_WATCH_TOPICS`/`watch_topics`/`watch_topics_save`/`watch_response`/`BARTEK_PROFILE_FACTS`/
`seed_bartek_profile` (przed `raw_operator_response`); `/watch` w route_text/build_response/
natural_intent; CLI `seed-profile`; linia w `setup_response`.

## Tests (WatchlistTests, 8 / 429 total)
defaults gdy brak pliku; add/remove/dedup; clear→defaults; route explicit+naturalny „śledź";
allowlist membership (read-only tak, router nie); research 1 temat + zbiorczy wołają Grok;
seed_profile utrwala zaufane fakty (Europe/Warsaw, approval).

## Follow-up
- Opcjonalny, gated dzienny auto-research watchlisty do briefu (domyślnie off — koszt).
- Po Google OAuth: brief wzbogacony o realny kalendarz/maile (4a).
