[Grok X Research] (12415ms)
**Fakty (na podstawie postów z X z okresu 2026-03-01 – 2026-06-06, w tym obowiązkowego threadu 2062575428213285352):**

- **Główne funkcje i sposób działania**: Poke (@interaction) to AI agent żyjący w wiadomościach (głównie iMessage / Apple Messages for Business). Użytkownik pisze do niego jak do osoby – zero appki, zero rejestracji, zero setupu. Oficjalnie zatwierdzony przez Apple jako „pierwszy i jedyny AI agent” na platformie Messages for Business (post z 4 czerwca 2026).  
  Link do głównego posta: https://x.com/interaction/status/2062575428213285352  
  Wcześniejszy post z marca 2026 pokazuje „Poke Recipes” – gotowe automatyzacje (np. Gmail, Calendar, Notion, Strava), które tworzy się w ~10 sekund naturalnym językiem.  
  Link: https://x.com/interaction/status/2034713714415608123

- **UX i ton/voice**: Wygląda i działa jak rozmowa z jedną konkretną osobą („feels like one person”). Ton luźny, przyjacielski, proaktywny. Użytkownicy podkreślają zero friction – „text Poke for free now”.

- **Onboarding i zero setup**: „No download, no signup. Text Poke for free”. Działa od razu po wysłaniu wiadomości.

- **In-thread actions i proactive nudges/followups**: W threadzie widać, że agent ma inicjować follow-upy. Po ogłoszeniu Apple approval wielu użytkowników narzekało na opóźnienia lub brak odpowiedzi w kanale biznesowym (np. „doesn’t respond”, „after 2 hours, no reply”, „left me on read”).

- **Recipes**: Główny mechanizm automatyzacji. Użytkownik tworzy „recipe” w naturalnym języku. Integracje z narzędziami codziennymi.

- **Apple Messages / iMessage approval**: Potwierdzone 4 czerwca 2026 – pierwszy standalone AI agent zatwierdzony przez Apple. Działa w istniejącym wątku iMessage.

- **Developer hints**: Wspomniane „npx poke” (w marcu 2026) oraz „Build with npx poke”.

- **Koszty**: Podstawowe użycie darmowe. Wspomniane „Earn on Poke”.

- **Ograniczenia i skargi użytkowników**:
  - Opóźnienia i brak odpowiedzi zaraz po ogłoszeniu Apple approval (wiele postów z 4–6 czerwca).
  - Problemy z kanałem business („borked”, „not responding in the business channel”).
  - Latency jako bottleneck (wcześniejsze posty).
  - Niektórzy nie widzieli zmian mimo wcześniejszego używania.

- **Memory**: Agent pamięta kontekst wątku i poprzednie interakcje (wynika z opisu „one conversation thread”).

**Hipotezy (niepotwierdzone faktami z postów):**
- Natural language programming wszystkich recipes bezpośrednio w iMessage (użytkownicy sugerują, że „is coming”).
- Wsparcie dla głosu/calling, Discord, RCS.
- Pełna pamięć długoterminowa i proaktywne nudges na poziomie osobistym.

**Lekcje do skopiowania do prywatnego Bartek Telegram / iPhone AI Council (fokus na mechanikach konwersacyjnych po L4.50 Poke Front Quality Guard):**
- Zero setup + życie w istniejącym komunikatorze = najniższy friction.
- Tone/voice „jak jedna osoba” zamiast korporacyjnego AI.
- Recipes jako prosty, wizualny/naturalny sposób na automatyzacje (nie kod).
- In-thread actions + proactive followups/nudges.
- Szybkość i niezawodność jako priorytet (po update’ach infrastruktury).

**Dokładnie jedna najlepsza kolejna funkcja do implementacji w Bartek Telegram AI Council po L4.50:**

**„Recipe Creator”** – mechanizm tworzenia i uruchamiania prostych automatyzacji bezpośrednio w wątku Telegram (analogicznie do Poke Recipes).

**Konkretne wymagania dla Claude i Codex:**

**Dla Claude (prompt / system prompt):**
- „Jesteś Bartek Recipe Creator. Użytkownik pisze naturalnym językiem: 'stwórz recipe: codziennie rano o 8:00 podsumuj moje maile z ostatniej doby i wyślij do mnie w Telegramie'. Natychmiast tworzysz czytelny opis recipe (nazwa + trigger + akcja + potwierdzenie), prosisz o jednoklikowe zatwierdzenie i uruchamiasz. Zero zewnętrznego UI. Zachowuj ton jednej konkretnej osoby.”

**Dla Codex (implementacja):**
- Obsługa natural language → parsowanie triggera (czas, event) + akcji (integracje: Gmail, Calendar, Notion, lokalne pliki).
- Przechowywanie recipes per użytkownik w pamięci kontekstowej wątku.
- Proactive nudges: po uruchomieniu recipe – krótkie potwierdzenie w wątku + ewentualny follow-up.
- Zero setup: recipe działa od razu po zatwierdzeniu w tym samym wątku.
- Ograniczenie: max 5 aktywnych recipes na użytkownika na start (żeby uniknąć latency).

To jest najbardziej bezpośredni, mierzalny i wartościowy next step, który kopiuje najmocniejszą mechanikę Poke bez kopiowania hype’u.
