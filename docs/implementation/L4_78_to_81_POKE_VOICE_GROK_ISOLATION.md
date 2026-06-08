# L4.78–L4.81 — Poke voice, Grok isolation, single-call routing, Council verdict

Date: 2026-06-08 · Owner: Claude Opus 4.8 · Status: LANDED (401 passed on Mac).

Zamyka 4 punkty z briefu Bartka: „mamy działający fundament, ale Poke feeling wymaga
dopracowania voice/UX, czystego researchu, mniejszej latencji i realnego werdyktu”.

## L4.79 — Grok isolation (NAJWAŻNIEJSZY: bug/contamination)

**Problem:** research operator dziedziczył prywatną pamięć rozmowy. `grok_response`
i `grok_x_research_response` wstrzykiwały `memory_context_for_prompt(...)` ("Co wiem o
Tobie: lot w piątek") do promptu researchowego → Grok mieszał niepowiązany kontekst
osobisty z faktami źródłowymi.

**Fix:**
- `grok_response(..., inject_memory=False)` — domyślnie **izolowany**. Personalna pamięć
  wstrzykiwana tylko gdy caller jawnie poprosi **i** flaga `AI_COUNCIL_GROK_RESEARCH_MEMORY`
  jest włączona (domyślnie off). Żaden obecny caller (@grok, @research, council judge)
  nie opt-inuje → research jest czysty.
- `grok_x_research_response` — całkowicie usunięta iniekcja pamięci. Operator X+web jest
  z definicji source-based.
- Front chat (`poke_chat_llm_response`) **zachowuje** personalną pamięć — tam jest na
  miejscu (Poke-style „pamiętam, że masz lot w piątek”). To jedyne miejsce z personal memory.

Granica: **research = czysty/źródłowy; front chat = personalny.**

## L4.78 — Master host contract (voice/UX jak Poke)

Jeden kanoniczny głos: `MASTER_HOST_CONTRACT` (stała). Front operator
(`poke_chat_llm_response`) używa go jako system prompt zamiast inline tekstu.

Zasady głosu: krótko (≤3 zdania/≤4 punkty), decyzyjnie, **status-first** z czasownikami:
- `ROBIĘ:` — realny start bezpiecznego kroku teraz.
- `ZROBIŁEM:` — tylko gdy system faktycznie wykonał (zero zmyślania plików/API/publikacji).
- `POTRZEBUJĘ ZGODY:` — akcje zewnętrzne/nieodwracalne (mail, kalendarz, GitHub write,
  publikacja, płatność, delete, deploy).
- `NIE MOGĘ:` — gdy nie wolno/nie da się, wprost + alternatywa.

Plus: prawda o stanie (system nieukończony, brak pełnych connectorów oraz iPhone/iMessage
layer; nigdy „wszystko działa” bez health), pamięć wątku (Telegram = jeden kontakt).

## L4.80 — mniej podwójnych callów Groka przy route+answer

`natural_intent_route` już miał deterministyczne **prefiksy** researchu (startswith:
„zbadaj”, „zrób research”, „sprawdź w internecie”, „research”, „deep research x” → /xresearch,
„zbadaj poke” → /poke-research). Te już omijały LLM router.

Dodane: `deterministic_research_route` łapie **research w środku zdania** którego prefiksy
nie wykrywały (np. „ej, sprawdź w internecie co nowego u OpenAI”, „ciekawi mnie co piszą o
nowym Grok 5”, „co na twitterze o premierze”). Uruchamiane **po** specyficznych routach
startswith (więc /xresearch i /poke-research dalej wygrywają), **przed** action_planner.

Efekt: te wiadomości idą prosto do jednego calla Groka (answer) zamiast płacić dodatkowy
call klasyfikacji w `llm_route()`. Markery są celowo specyficzne („sprawdź w internecie”,
nie samo „sprawdź”), więc niejednoznaczne („sprawdź to szerzej”) dalej trafiają do LLM routera.

X-specyficzne markery → `/xresearch`; web → `@research`.

## L4.81 — Council kończy jednym werdyktem, nie 3 równoległymi odpowiedziami

`@all` dawał 3 osobne bullet-y (Technicznie/Plan/Research) bez rozstrzygnięcia.
Teraz `front_all_response(..., verdict=...)` domyka konsultację blokiem:
`WERDYKT:` (decyzja) · `FAKTY:` · `SPÓR:` (żywy spór głosów) · `NASTĘPNY KROK:` (jeden).

Werdykt liczony **deterministycznie** przez `fallback_council_synthesis` z 3 głosów —
**bez dodatkowego calla Groka** (spójne z celem kosztowym L4.80). Strukturalny `/council`
(background) już wcześniej syntetyzował werdykt; @all był brakującą powierzchnią „parallel answers”.

## Anchors
`grok_response`/`grok_x_research_response` (~15300/15410), `MASTER_HOST_CONTRACT` +
`poke_chat_llm_response` (~15475/15640), `RESEARCH_X_MARKERS`/`RESEARCH_WEB_MARKERS`/
`deterministic_research_route` (przed `natural_intent_route`) + call po `research_prefixes`,
`front_all_response` + `@all` handler w `build_response`.

## Tests (13 nowych, 401 total)
- `GrokIsolationTests` (4): grok_response bez personal memory by default; opt-in+flaga
  wstrzykuje; grok_x_research nigdy nie wstrzykuje; front chat dalej trzyma personal memory.
- `MasterHostContractTests` (2): kontrakt ma czasowniki statusu; poke_chat używa go jako system.
- `DeterministicResearchRouteTests` (5): mid-sentence web → @research bez llm; „co piszą o” →
  @research bez llm; X marker → /xresearch; istniejący prefix /xresearch dalej wygrywa;
  niejednoznaczne dalej idzie do llm.
- `CouncilAllVerdictTests` (2): front_all_response renderuje blok werdyktu; @all syntetyzuje
  jeden werdykt.

## Verification
- Mac: `python3 -m pytest -q tests/test_ai_council.py` → **401 passed**.
- py_compile OK.

## Follow-up
- Opcjonalny LLM-judge werdykt dla `@all` za flagą (domyślnie deterministyczny, by nie
  dokładać kosztu).
- iMessage bridge (Messages.app + AppleScript na Macu) — osobna warstwa; patrz odpowiedź
  na pytanie „czy podepniemy pod iMessage”.
