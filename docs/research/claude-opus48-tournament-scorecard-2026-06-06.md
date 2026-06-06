<!-- started=2026-06-06T23:15:16 ended=2026-06-06T23:16:46 exit=0 model=claude-opus-4-8 -->

# AI Council Tournament Scorecard

## Criteria

Każde kryterium oceniane 0–10 (wyżej = lepiej). Total to średnia ważona wg poniższych wag — Rada celowo premiuje *reliability*, *poke_ux* i *current_fit*, bo decydują o tym, czy asystent jest używalny dziś, a nie tylko elegancki na papierze.

| kryterium | waga | co mierzy |
|---|---|---|
| speed | 10% | latencja od intencji do odpowiedzi/akcji |
| reliability | 15% | przewidywalność, odporność na błędy, brak cichych porażek |
| poke_ux | 15% | jakość konwersacji w stylu Poke: krótkie tury, inline akcje, zero ceremonii |
| safety | 12% | brak akcji bez zgody, dry-run, granice uprawnień |
| implementation_cost | 12% | wyżej = taniej/szybciej wdrożyć (odwrócona skala kosztu) |
| extensibility | 10% | łatwość dokładania nowych tooli/recipe bez przepisywania rdzenia |
| iphone_path | 8% | realność ścieżki do iPhone/Shortcuts bez przepisywania architektury |
| auditability | 8% | czy każdą akcję da się prześledzić i odtworzyć |
| current_fit | 10% | dopasowanie do tego, co mamy i czego potrzebujemy teraz |

## Score Table

| candidate | speed | reliability | poke_ux | safety | implementation_cost | extensibility | iphone_path | auditability | current_fit | total | verdict |
|---|---|---|---|---|---|---|---|---|---|---|---|
| **G — Hybrid Staged Architecture** | 8 | 9 | 8 | 8 | 7 | 9 | 8 | 8 | 9 | **8.15** | 🏆 Winner — staged daje UX dziś i ścieżkę na później |
| **B — Recipes-first Poke clone** | 8 | 7 | 9 | 7 | 8 | 7 | 6 | 6 | 8 | **7.40** | 🥈 Runner-up — najlepszy UX, słabszy audyt/iPhone |
| **C — Hermes-style tool registry** | 7 | 8 | 6 | 8 | 6 | 9 | 6 | 8 | 7 | **7.10** | Solidny fundament, ale UX wymaga dobudowy |
| **D — OpenClaw memory/proactive OS** | 6 | 6 | 7 | 6 | 4 | 9 | 5 | 7 | 7 | **6.45** | Wizjonerski, za drogi i ryzykowny teraz |
| **F — Full execution / Risk Officer-first** | 6 | 8 | 5 | 9 | 4 | 7 | 5 | 9 | 6 | **6.35** | Najbezpieczniejszy, ale ciężki i wolny do startu |
| **E — iPhone Shortcuts-first** | 7 | 6 | 6 | 6 | 6 | 5 | 9 | 5 | 5 | **6.00** | Świetny iPhone-path, słaby rdzeń i rozszerzalność |
| **A — Telegram-only incremental** | 8 | 7 | 6 | 6 | 9 | 4 | 3 | 5 | 6 | **5.95** | Najtańszy start, ślepa uliczka architektoniczna |

Ranking: **G > B > C > D > F > E > A**.

## Winner

**Kandydat G — Hybrid Staged Architecture (8.15/10).**
Wygrywa, bo nie zmusza do wyboru między „dobry UX teraz” a „poprawna architektura później”. Etap 0 daje natychmiast pokowy UX (inline buttony + propozycja akcji), Etap 1 dokłada recipe engine jako rdzeń automatyzacji, a warstwy delivery/cost/audit wchodzą inkrementalnie. Najwyższy *current_fit* (9) i *reliability* (9) przy zachowanej *extensibility* (9). Jedyny kandydat, który nie wymaga przepisania rdzenia, gdy dojdzie ścieżka iPhone.

## Runner-up

**Kandydat B — Recipes-first Poke clone (7.40/10).**
Najlepszy czysty *poke_ux* (9) — gdyby liczyła się tylko jakość rozmowy, wygrałby. Przegrywa na *auditability* (6) i *iphone_path* (6): recipes bez warstwy stanu/audytu trudniej rozliczyć i trudniej później wystawić jako Shortcuts. G to w praktyce „B + warstwa audytu/stanu zrobiona od początku”, dlatego B jest naturalnym źródłem patchy do silnika recipe.

## First Batch: 9 Patches

Dokładnie 9 patchy do wdrożenia teraz, w kolejności (Etap 0 → Etap 1 → delivery nudge + cost):

**Etap 0 — inline buttony i kontrakt akcji (fundament UX)**
1. **Inline action buttons** — każda proponowana akcja w Telegramie dostaje przyciski `Zatwierdź / Edytuj / Anuluj`; nic nie wykonuje się bez tapnięcia.
2. **Action proposal schema** — jeden format wiadomości-propozycji: `intent + params + preview` (czytelny podgląd zanim cokolwiek się stanie).
3. **Pending-state store** — lekka, trwała pamięć oczekujących akcji i kontekstu sesji, żeby kliknięcie przycisku dopinało właściwą propozycję.

**Etap 1 — recipe engine (rdzeń automatyzacji)**
4. **Recipe definition format** — deklaratywny format `trigger → steps → confirmation` (z punktami zgody między krokami).
5. **Recipe executor + dry-run** — silnik parsujący i odpalający recipe etapami, z obowiązkowym trybem `dry-run` przed pierwszym realnym wykonaniem.
6. **Recipe registry + 3 seed recipes** — rejestr + trzy startowe recipe pokrywające realne, codzienne przypadki użycia.

**Delivery nudge + cost (warstwa zaufania)**
7. **Delivery nudge** — proaktywne przypomnienie, gdy akcja czeka niezatwierdzona/niedokończona (follow-up zamiast cichego porzucenia).
8. **Cost meter** — licznik tokenów/$ per akcja, pokazywany w preview *zanim* użytkownik kliknie „Zatwierdź”.
9. **Append-only audit log** — niezmienny log propozycji, zgód i wykonań (kto/co/kiedy/koszt), baza pod późniejszy audyt i iPhone-path.

## Anti-Plan

Czego **nie** robimy w pierwszej partii (świadome wykluczenia):
- ❌ **Brak autonomicznego wykonywania akcji** — żadnego auto-execute „bo model był pewny”; zawsze inline approval (to różnica G vs. D/F).
- ❌ **Nie budujemy teraz iPhone/Shortcuts** — patch #9 (audit log) celowo *przygotowuje* tę ścieżkę, ale samej integracji nie tykamy w batchu 1.
- ❌ **Brak proaktywnego „memory OS”** (kandydat D) — żadnej spekulatywnej pamięci długoterminowej ani proaktywnych skanów; tylko `pending-state` z #3.
- ❌ **Brak osobnego, ciężkiego Risk Officera** (kandydat F) — bezpieczeństwo realizujemy tanio przez dry-run (#5) + inline approval (#1), nie przez osobny moduł oceny ryzyka.
- ❌ **Nie rozbudowujemy tool registry** ponad to, czego wymagają 3 seed recipes — generyczny rejestr w stylu C odkładamy, aż recipe engine udowodni kształt API.
- ❌ **Żadnego refaktoru rdzenia pod przyszłe etapy** — inkrementalnie, jeden patch = jedna obserwowalna zmiana.

## Acceptance Criteria

Batch uznajemy za zakończony, gdy **wszystkie** poniższe są spełnione:

1. **Zero akcji bez zgody** — każda akcja z efektem ubocznym przechodzi przez inline `Zatwierdź/Edytuj/Anuluj`; brak ścieżki auto-execute (#1).
2. **Każda propozycja ma preview** — 100% propozycji renderuje `intent + params + preview` w jednym czytelnym message’u (#2).
3. **Stan przeżywa restart** — po restarcie procesu kliknięcie przycisku przy oczekującej akcji nadal dopina właściwą propozycję (#3).
4. **Recipe działa end-to-end** — co najmniej 1 z 3 seed recipes przechodzi pełny cykl `trigger → steps → confirmation` na realnym przypadku (#4, #6).
5. **Dry-run jest domyślny przy pierwszym uruchomieniu** — nowe recipe nie wykona realnej akcji, dopóki użytkownik nie potwierdzi po podglądzie dry-run (#5).
6. **Nudge wyzwala się deterministycznie** — akcja oczekująca dłużej niż próg generuje dokładnie jedno przypomnienie, bez spamu (#7).
7. **Koszt widoczny przed zgodą** — preview pokazuje szacunkowy koszt (tokeny/$) *przed* kliknięciem „Zatwierdź” (#8).
8. **Pełna ścieżka audytu** — dla dowolnej wykonanej akcji da się z logu odtworzyć: propozycję, kto zatwierdził, kiedy i jaki był koszt (#9).
9. **Brak regresji UX** — mediana liczby tur do wykonania typowej akcji nie rośnie względem stanu sprzed batcha (pokowy, krótki dialog zachowany).
