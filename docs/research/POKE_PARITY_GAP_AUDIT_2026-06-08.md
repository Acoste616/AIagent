# Poke Parity Gap Audit — 2026-06-08

Wygenerowane przez workflow poke-parity-gap-audit (research Poke z weba + audyt repo).

## KOREKTA Claude (audyt oparł się na dokumentach sprzed tej sesji):
- GitHub write: **NIE dry-run — JEST LIVE**. W tej sesji włączyłem PROVIDER_WRITE_ENABLED + GITHUB_ISSUE_WRITE_ENABLED + token i utworzyłem realne issue #1 (potem zamknięte). GitHub real-write działa end-to-end.
- Local hands (read+write): **włączone** (LOCAL_HANDS + LOCAL_HANDS_WRITE), zademonstrowane na żywo.
- Auto-pamięć (L4.65.2): **włączona** (FACT_AUTO_EXTRACT).
- Router NL (L4.63): **włączony** (llm_router=on).
- Reszta oceny i strategiczny obraz (kanały, proaktywność, real-send dla Gmail/Calendar) — trafne.

---

The actual production system is on `D:\ai-council` (Windows host), and this Mac only holds config/state mirrors. I have enough: the status JSON is the system of record, the codebase isn't on this machine to line-verify, and that's itself a finding worth noting (I'll treat the status JSON as authoritative but flag that I'm assessing from the report, not re-running the line-level audit). 

I have everything I need to write the honest assessment. The task is analysis/synthesis of the two JSON blobs, cross-referenced against the channel reality (Telegram-only inbound confirmed live; no SMS/iMessage/WhatsApp; provider writes are dry-run only; iPhone shortcuts gated off; daily brief not wired). Let me write the report.

## 1. Brutalnie szczerze: gdzie jesteśmy

Szczerze: silnikowo jesteś bliżej Poke niż ci się wydaje, ale **produktowo, jako odczucie użytkownika, jesteś na jakichś 35–45% Poke** — i to optymistycznie. Powód jest brutalny: zbudowałeś bardzo dobry mózg (router intencji + fence ryzyka R0–R4, trójwarstwowa pamięć z anty-poisoningiem, swarm/execution-agent w stylu OpenPoke, autonomiczne pętle, koszt-ledger, weryfikacja+rollback, sandbox plików) — ale ten mózg gada przez **jeden kanał (Telegram)** i prawie wszystko, co dotyka świata zewnętrznego, działa w trybie **dry-run / za flagą / nieaktywowane**. Poke to nie "Gmail + GitHub" — Poke to *bycie wszędzie tam, gdzie człowiek już pisze* (iMessage, SMS, WhatsApp, Telegram), *robienie rzeczy naprawdę* (wysyła maila, nie tworzy draftu w artefakcie), i *odzywanie się samo z siebie* (poranny brief o 8:00, nudge "masz spotkanie za 30 min"). W każdym z tych trzech filarów masz albo placeholder, albo "coded_not_activated".

Najmocniejsza prawda: **twoje gapy to w 80% gapy aktywacji i kanału, a nie gapy kodu.** Provider Write umie złożyć Gmail/Calendar/Drive/GitHub, ale pisze artefakt dry-run i siedzi za `AI_COUNCIL_PROVIDER_WRITE_ENABLED=false`. iPhone Shortcuts są w pełni zakodowane, ale demon stoi (`State: Stopped`, brak `AI_COUNCIL_SHORTCUT_TOKEN`). Daily brief — wprost #1 gap Bartka — **nie jest podłączony** (L4.66 tylko częściowy: recall faktów działa, ale brief/watcher/proaktywne przejmowanie tematu odłożone). Dlatego "utknęło na Gmailu": nie dlatego że nie umiesz więcej, tylko dlatego że każda kolejna integracja i każdy kanał wymaga osobnego auth/decyzji Bartka, a te się nie podpięły.

## 2. Macierz: Poke vs my

| Poke capability | Nasz status | Dowód (z naszego JSON / realiów) | Blocker |
|---|---|---|---|
| **iMessage / Apple Messages for Business** | brak | Brak jakiejkolwiek wzmianki w naszym statusie | Apple wymaga zweryfikowanego konta biznesowego + human fallback + disclosure. Bariera ~niemożliwa solo |
| **SMS** | brak | Brak | Wymaga providera (Poke używa Linq), numeru, kosztu per-user |
| **Telegram** | LIVE | L4.1/L4.2/L4.21: listener Running na D:\ai-council, listen_once + route_message, idempotent po update_id, offset atomowy | — (to twój jedyny żywy kanał i jest solidny) |
| **WhatsApp / RCS** | brak | Brak | Provider + Meta/operator approval |
| **Poranny digest 8:00** | częściowo→brak | L4.66 *partial*: recall faktów żyje, ale "full daily brief + watcher" **deferred**. To wprost #1 gap Bartka | Trzeba dopiąć schedulera briefu + zaciągnięcie kalendarz/mail. SAM, ale zależy od read-auth |
| **Proaktywne nudge / unprompted** | częściowo | L4.9 proaktywny scan "minimal"; brak watcherów event/email w czasie rzeczywistym | Wymaga read-streamu z Gmail/Calendar (auth) + logiki "wait" |
| **Email/event watchers (real-time)** | brak | Brak realtime watchera; mamy tylko twice-daily pętle | Push/poll z providerów + koszt inference per-event |
| **'wait' tool (tłumienie szumu)** | brak | Brak odpowiednika; mamy heartbeat anty-spam (L4.20) ale nie selektywne kasowanie redundancji | SAM — to logika, nie auth |
| **Triggers (scheduled automations)** | LIVE (częściowo) | L4.16/L4.43 /loops: error_audit + feature_evolution z cadence/next-window. Brak dowolnych user-triggerów typu "first Monday" | SAM — rozszerzyć cadence-engine |
| **Automations via webhook/API/MCP** | LIVE | Custom MCP (L4 mcp-servers ekwiwalent), recipe system L4.51-53; inbound webhook nie potwierdzony | Częściowo SAM |
| **Recipes (prebuilt) + Kitchen + marketplace + payouts** | brak | Mamy /recipe creator (L4.51-53) i /loops, ale to nasze pętle, nie marketplace ~436 szablonów, brak payoutów/referrali | Produkt+biznes, nie priorytet parity odczucia |
| **Email & Calendar (Gmail/Outlook)** | LIVE-read / dry-run-write | L4.30-41 Provider Write: Gmail drafts.create (NIE send), Calendar events.insert (sendUpdates=none) — **artefakt dry-run**, gated `PROVIDER_WRITE_ENABLED=false` | Bartek: włączyć flagi + OAuth ready; my: przejść z dry-run na realny send |
| **Productivity (Notion/Linear/Todoist/Asana/Granola)** | brak | Brak; tylko GitHub w connectorach | Auth per-integracja (Bartek) + connector kod |
| **Developer tools (GitHub, Vercel, Sentry...)** | częściowo | GitHub issues.create (dry-run, L4.30-41). Reszta brak | GITHUB_TOKEN jest; flaga write off |
| **Health/Smart-home/Finance (Oura, Hue, Ramp...)** | brak | Brak | Auth per-integracja |
| **Custom MCP integrations** | LIVE (ekwiwalent) | Recipe/connector system; nie potwierdzono pełnego MCP client z X-Poke-User-Id scoping | Częściowo SAM |
| **Web search** | LIVE | @research flow, action planner auto-start | — |
| **Reminders / Voice messages** | brak/częściowo | Reminders nie wyróżnione; voice tylko jako iOS recipe (voice_note_to_task) — **gated, demon Stopped** | Bartek: aktywować Shortcuts |
| **Trójwarstwowa pamięć** | LIVE | L4.65 Hermes: user_fact_save/forget/promote, norm_key, supersession, quarantine; memory.sqlite 63 wiersze; recall eval >=0.75 | — (to twoja najmocniejsza parytetowa karta) |
| **User-taught persistent facts** | LIVE | "zapamiętaj"→user_fact_save→active; /memory facts/forget; recall wstrzykiwany do promptów | — |
| **Onboarding "bouncer"** | brak | Brak persony onboardingowej/negocjacji wejścia | SAM — to prompt/UX, niski priorytet |
| **Interaction Agent (orchestrator)** | LIVE (ekwiwalent) | Action Planner + router (L4.15/L4.35/L4.63) + Agent Inbox (L4.26) | — |
| **Persistent Execution Agents (swarm)** | LIVE (ekwiwalent) | Project Memory Spine + agent memory; pętle trzymają kontekst | — |
| **Multi-model routing** | częściowo | LLM router (L4.63) to cost-gate + fallback, nie pełne routowanie "best model per task" | SAM — rozszerzyć |
| **Negocjowany pricing / koszt** | LIVE (lepiej niż Poke) | L4.18/L4.23 cost-ledger, reservation, /control budget; L4.68 doda per-day cost na delivery cards (bije #1 skargę na Poke) | — |
| **Verification / Rollback** | LIVE (przewaga) | L4.19 /verify + /rollback, artefakty SHA-256, /fs undo. Poke tego nie ma jawnie | — |
| **Local filesystem hands (sandbox)** | LIVE-gated | L4.69/.1 OpenClaw: safe_resolve 7 escapes, red-team przeszedł; OFF (`LOCAL_HANDS=true` wymagane) | Bartek: włączyć flagę (świadomie) |

## 3. Trzy największe luki do "poziomu Poke"

**1. Kanały: jesteś na Telegramie, Poke jest w kieszeni przy iMessage/SMS/WhatsApp.**
WHY: To jest *cała teza Poke* — "AI tak proste jak SMS". Człowiek pisze tam, gdzie już pisze. Telegram w PL to nisza; brak SMS/iMessage oznacza, że asystent nie jest "zawsze pod ręką", tylko "w jednej dodatkowej apce". To największy dystans w *odczuciu*, nawet jeśli mózg jest równy.
CO TRZEBA: realnie — provider SMS (Twilio/Linq-podobny) + numer + budżet per-message. iMessage Business = praktycznie poza zasięgiem solo (Apple approval, human fallback). **Rekomendacja: odpuść iMessage, zrób WhatsApp Business API lub SMS jako drugi kanał.** To wymaga decyzji i $ Bartka.

**2. Realne pisanie do świata: jesteś w trybie dry-run.**
WHY: Poke *wysyła* maila, *tworzy* event z zaproszeniem, *zamyka* issue. Ty składasz poprawny request i zapisujesz artefakt `external_write=false`. Z perspektywy użytkownika "przygotowałem draft w pliku" ≠ "zrobione". To różnica między asystentem a generatorem szkiców.
CO TRZEBA: przełączyć dry-run→real za fence'em R3/R4 z approve. Kod jest (L4.30-41), auth jest (GitHub token, Google OAuth ready). To jest **najtańszy duży skok**: włączenie flag + jedna realna ścieżka send z potwierdzeniem. Decyzja Bartka (ryzyko) + ja przepinam ścieżkę.

**3. Proaktywność: brak porannego briefu i realtime watcherów.**
WHY: To drugie pół duszy Poke — odzywa się samo o 8:00, mówi "Dave odpisał, streścić?", "spotkanie za 30 min bez agendy". Twój scan jest "minimal", brief *deferred*, watcherów email/event realtime nie ma. Bez tego asystent jest *reaktywny* (czeka aż napiszesz) — a Poke jest *proaktywny*.
CO TRZEBA: dopiąć L4.66 full — scheduler briefu 8:00 zaciągający kalendarz+ważne maile + watcher z 'wait'-logiką tłumienia szumu. Recall faktów już działa (L4.66 partial), więc fundament jest. To w dużej mierze SAM, ale brief potrzebuje read-auth do Gmail/Calendar.

## 4. Co blokuje (i czyja to robota)

**Domknę SAM, autonomicznie (kod, bez decyzji/auth):**
- L4.66 full: scheduler porannego briefu + watcher + 'wait'-logika tłumienia szumu (fundament recall już żyje).
- Rozszerzenie triggerów na dowolne wzorce usera ("first Monday", "co wtorek") na bazie istniejącego cadence-engine z /loops.
- Multi-model routing: rozbudowa cost-gate'u (L4.63) do prawdziwego "best model per task".
- 'wait' tool / dedup proaktywnych wiadomości — to czysta logika.
- Per-day cost na delivery cards (L4.68) — już zaplanowane.
- Przepięcie Provider Write z dry-run na realny send **w kodzie** (ale uruchomienie = decyzja Bartka, niżej).

**Wymaga Bartka — i to wyjaśnia, czemu "utknęło na Gmailu":**
- **Flagi aktywacji (decyzja ryzyka, 5 minut roboty):** `AI_COUNCIL_PROVIDER_WRITE_ENABLED=true` + per-connector (`GMAIL_DRAFT_WRITE`, `CALENDAR_EVENT_WRITE`, `GITHUB_ISSUE_WRITE`, `DRIVE_FILE_WRITE`), `AI_COUNCIL_SHORTCUT_TOKEN` + start demona Shortcuts, `AI_COUNCIL_LOCAL_HANDS=true`. Cała ta praca jest **zrobiona i przetestowana** — stoi tylko na twojej zgodzie. To jest realny powód "utknięcia": nie brak kodu, brak przełączonych przełączników.
- **Auth per-integracja (każda nowa to osobny OAuth/token):** Notion, Linear, Todoist, Asana, Oura, Ramp, Vercel itd. Każda integracja Poke = jeden flow autoryzacji, który tylko ty możesz przejść (twoje konta). Dlatego rośnie liniowo i wygląda jak "utknęło na Gmailu+GitHub" — bo tylko te dwa masz podpięte.
- **Kanały (decyzja + $):** SMS/WhatsApp = wybór providera + numer + budżet. iMessage Business = Apple approval (realnie poza zasięgiem solo).
- **Decyzja "real send" (ryzyko R3/R4):** zgoda, że agent naprawdę wysyła maile/płaci — fence jest, ale pociągnięcie spustu to twoja decyzja.

Krótko: **żadna z 3 głównych luk nie jest zablokowana brakiem mojej pracy w pełni — wszystkie trzy mają komponent "Bartek musi podjąć decyzję / przejść auth / dać budżet".** To jest dokładnie ten sufit, o który uderzasz.

## 5. Plan: najkrótsza droga do odczucia "Poke level"

Kolejność wg "największy skok w *odczuciu* na włożony wysiłek":

**Krok 0 — DZIŚ, 15 minut, sam przełączasz flagi (największy skok / zero kodu):**
Włącz `PROVIDER_WRITE_ENABLED` + connector-flags, `SHORTCUT_TOKEN` + start demona, `LOCAL_HANDS`. Z dnia na dzień: asystent *realnie* tworzy draft Gmaila/event/issue (za approve), iPhone Shortcuts żyją (voice→task, share URL→research), ma ręce do plików. To odblokowuje już-zbudowaną wartość. **To jest twój najszybszy „wow".**

**Krok 1 — Real send za fence'em (ja, mały kod + twoja zgoda):**
Jedna ścieżka dry-run→prawdziwy send dla Gmaila z R3/R4 approve. "Napisz i wyślij maila do X" kończy się *wysłanym mailem*, nie artefaktem. To zamyka lukę #2 — psychologicznie przeskok z "generatora draftów" na "asystenta".

**Krok 2 — Poranny brief 8:00 + nudge (ja, L4.66 full):**
Scheduler o 8:00: kalendarz dnia + ważne maile + recall faktów (fundament jest) + 'wait'-tłumienie szumu. To #1 gap Bartka i drugie pół duszy Poke. Po tym asystent *odzywa się sam* — to moment, w którym "czuje się jak Poke".

**Krok 3 — Drugi kanał (twoja decyzja + $):**
WhatsApp Business API albo SMS przez providera. Odpuść iMessage. To przenosi asystenta z "apki Telegram" do "kieszeni". Najdroższy i wymaga ciebie — dlatego ostatni, mimo że konceptualnie to serce Poke.

**Krok 4 — Szerokość integracji (ty: auth, ja: connectory):**
Po jednym OAuth na sesję: Notion + Linear/Todoist (productivity to najczęstszy use-case). Każda kolejna to liniowa praca — ale dopiero po Krokach 0–2, bo bez real-send i briefu więcej integracji = więcej dry-runów, nie więcej wartości.

**Pojedyncze zdanie dla Bartka:** Mózg masz na ~poziomie Poke (pamięć, router, fence, swarm, weryfikacja — miejscami nawet *lepszy*); brakuje ci **żywych rąk (real send), własnego głosu o 8:00 (brief) i bycia w kieszeni (drugi kanał)** — a pierwszy z tych trzech odblokowujesz *dziś, sam, przełącznikiem*, nie kolejnym sprintem.

---
*Uwaga metodologiczna: oceniam na podstawie statusu (system of record) — sam kod `ai_council.py` żyje na `D:\ai-council` (Windows host), nie na tym Macu (tu są tylko mirrory `~/.config/ai-council/.env` i `~/.local/share/ai-council/state`), więc nie re-audytowałem numerów linii. Statusy "LIVE" przyjmuję za raportem; gapy ("brak", "dry-run", "gated") wynikają wprost z treści obu JSON-ów i potwierdzonego realiów: jedyny żywy kanał inbound to Telegram, a każdy write jest `external_write=false` dopóki nie włączysz flag.*