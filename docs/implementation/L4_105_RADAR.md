# L4.105 — RADAR: osobisty zwiad YouTube/X/GitHub

Stan: Mac worktree, NIE wdrożone, NIE commitowane. Testy Mac: 633/633 (601 baza + 32 nowe w `tests/test_radar.py`), ruff clean.

## Co to robi

Raz dziennie (recipe `radar_daily`, cron `0 {AI_COUNCIL_RADAR_HOUR|8} * * *`, lokalnie = rano po quiet hours) albo na żądanie („radar", „co nowego", `/radar`) zbiera nowości z trzech źródeł wg watchlisty Bartka i wysyła JEDEN krótki, ludzki przegląd po polsku (sekcje 🎬/𝕏/⭐, każda pozycja 1 linia + link, na końcu 1 propozycja + pytanie). Flaga: `AI_COUNCIL_RADAR_ENABLED` (default true).

## Watchlista

- Stan: `STATE_DIR/radar_watchlist.json` — `{"topics": [...], "yt_channels": [{"name","channel_id"}], "gh_repos": ["owner/repo"]}`.
- Seed: topics `agenci AI, Claude, Grok, iMessage automation, OpenClaw`; gh_repos `anthropics/claude-code`; yt_channels puste.
- Naturalne komendy (`_nat_radar`, zarejestrowane PRZED `_nat_ops_dashboards`):
  - „obserwuj X" → add (heurystyka `radar_classify_item`: link YouTube → kanał przez `radar_youtube_channel_id`, `owner/repo`/link GitHub → repo, reszta → temat);
  - „przestań obserwować X" → remove; „co obserwujesz"/„watchlista" → lista; „radar"/„co nowego"/„co ciekawego" → przegląd na żądanie.
- UWAGA zmiana routingu: „obserwuj …" szło wcześniej do `/watch add` (L4.85); teraz idzie do radaru. Stary `/watch` zostaje pod „śledź …", „watchlist", `/watch`.

## Źródła (read-only GET, każde fail-safe)

- YouTube: RSS `youtube.com/feeds/videos.xml?channel_id=…`, parser regex (`radar_youtube_entries`), 3 najnowsze, tylko nowsze niż marker per kanał w `STATE_DIR/radar_state.json`.
- GitHub: trending HTML (`parse_github_trending`, top 5 repo+opis) + `api.github.com/repos/{repo}/releases/latest` bez tokena (403/404 cicho; marker per repo raportuje tylko zmianę tagu).
- X: JEDNO wywołanie Groka przez istniejące `grok_x_research_response` (reserve/finalize w środku); blocked/error → pusta sekcja.
- `radar_fetch_text` = tekstowy bliźniak `request_json` (RSS/HTML to nie JSON); nigdy nie rzuca.

## Złożenie i wysyłka

- `radar_digest(send, on_demand)`: scheduled = marker dzienny `last_digest_day` zapisany PRZED pracą (maks 1/dzień, retry nie spamuje); on_demand = zawsze, bez markera.
- Złożenie: JEDNO wywołanie Claude CLI (`radar_claude_compose`, `--tools ""`, reserve `claude`/detail `radar`, kontrakt `RADAR_COMPOSE_CONTRACT`); fallback deterministyczny `radar_fallback_digest` z samych danych.
- Wysyłka `radar_send`: `deliver_proactive` (iMessage-first) ORAZ kopia na Telegram z inline przyciskami — świadomy dual-channel, bo przyciski żyją tylko na Telegramie.
- Przyciski (`radar_reply_markup`, callback ≤64B): `host:radar-x` (Grok X po tematach z watchlisty), `host:radar-gh` (świeży trending — deterministycznie, bez modelu), `host:radar-settings` (watchlista). Obsługa w `host_callback_response`.
- Odpowiedź na żądanie dostaje te same przyciski przez `response_reply_markup` (detekcja nagłówka `🛰 Radar`).

## Rejestracje

`/radar` w `route_text` + `build_response` + `READONLY_RECIPE_COMMANDS` (deny-by-default policy przepuszcza krok recipe); recipe `radar_daily` w `default_recipes` + `DEFAULT_RECIPE_MANAGED_KEYS`; `recipes/radar_daily.json` generuje się przez `ensure_default_recipes`.

## Kompromisy

- Przycisk „GitHub" robi świeży fetch trendingu zamiast `/research github trending` (zero kosztu modelu, ten sam efekt dla użytkownika).
- `radar_collect` aktualizuje markery źródeł także przy on_demand — „nowsze niż ostatni run" znaczy dowolny run.
- `/radar` jest synchroniczny (jak `/watch research`); W1 typing pulse kryje wolniejsze odpowiedzi.
- Link YouTube bez `channel/UC…` wymaga 1 GET strony do wyłuskania channelId; gdy się nie uda — zapis jako temat (uczciwy komunikat).

## Bezpieczeństwo

Zero external writes (tylko GET), zero zmian w guardach/approval path, brak tokenów do GitHub/YouTube, Grok/Claude przez istniejące reserve/finalize (limity kosztów obowiązują).
