# Pełen kontekst — pytania do Bartka (żeby AI stało się super-potężne)

Cel: zebrać kontekst, którego nie da się wywnioskować z kodu, żeby budować w stronę
pełnego Poke+ (pamięć jak Hermes, ręce jak OpenClaw, integracje + proaktywność).
**Nie wklejaj tu haseł, tokenów ani kodów** — sekrety ustawiamy osobno (env/skrypty).

Odpowiadaj numerem, np. „2c: tak, Twilio mam".

## 1. Tożsamość i głos
- 1a. Jak asystent ma się zwracać do Ciebie i jakim tonem (per Ty, krótko/decyzyjnie — tak jak teraz, czy inaczej)?
- 1b. Język domyślny: polski zawsze, czy auto-dopasowanie do wiadomości?
- 1c. Czego ma NIGDY nie robić w stylu (np. żadnych emoji? żadnych długich wstępów?)?

## 2. Urządzenia i kanały
- 2a. Główny telefon: iPhone (model/iOS)? Czy iMessage jest tam zalogowany na tym samym Apple ID co Mac?
- 2b. iMessage odbiorca (Twój Apple ID/numer) — ustawisz sam w env na Macu (`AI_COUNCIL_IMESSAGE_TO`), czy mam Cię przez to przeprowadzić?
- 2c. Czy Mac ma być zawsze włączony (most iMessage działa tylko, gdy Mac działa)? Jak nie — fallback na Telegram?
- 2d. Czy chcesz też kanał na komputerze (desktop notyfikacje / okno czatu), czy wystarczy Telegram + iMessage?

## 3. Konta i integracje (zaznacz co MASZ i co CHCESz podłączyć)
- 3a. Google (Gmail/Calendar/Drive) — masz konto? Chcesz pełny dostęp (OAuth) czy tylko Mail.app na Macu?
- 3b. Microsoft/Outlook (Twój email to outlook.com) — podłączać Outlook/365?
- 3c. Notion — używasz? Do czego (notatki/zadania/baza)?
- 3d. Linear/Jira/Asana/Todoist — które, jeśli któreś?
- 3e. Spotify/Apple Music — sterowanie muzyką ma sens?
- 3f. GitHub — który zakres (sam research/issues czy też PR-y)? (token już jest na hoście).
- 3g. Slack/Discord/WhatsApp/Signal — których realnie używasz codziennie?
- 3h. Bankowość/finanse — tylko podgląd (read), czy w ogóle zostawiamy poza systemem?

## 4. Proaktywność (co ma robić SAM, bez pytania)
- 4a. Poranny brief — o której i co ma zawierać (kalendarz, maile, taski, newsy z Twoich tematów)?
- 4b. Tematy do śledzenia na bieżąco (research/X/web): jakie firmy, ludzie, słowa kluczowe?
- 4c. Godziny ciszy (kiedy NIE pingować)?
- 4d. Co ma proaktywnie przypominać/eskalować (np. „odpisz na tego maila", „masz spotkanie za 15 min")?

## 5. Codzienne zadania (gdzie AI ma realnie odciążać)
- 5a. 3 rzeczy, które robisz codziennie i chcesz oddać AI.
- 5b. Czy ma pisać DRAFTY (maile/wiadomości) do Twojej akceptacji, czy też wysyłać po zatwierdzeniu jednym kliknięciem?
- 5c. Czy ma operować na plikach na Macu/Windows (czytać, segregować, tworzyć)? Które foldery są OK, a które zakazane?

## 6. Granice bezpieczeństwa
- 6a. Co wolno SAMODZIELNIE (R0/R1: research, drafty, czytanie plików)?
- 6b. Co ZAWSZE wymaga Twojej zgody (wysyłka maila, posty publiczne, płatności, usuwanie, zmiany ustawień)?
- 6c. Limit budżetu dziennego/miesięcznego na modele (Grok/Claude/Codex) — jaka kwota to „stop i pytaj"?
- 6d. Czy mogę deployować i restartować bota na Windows bez pytania (jak dziś), czy chcesz potwierdzać każdy deploy?

## 7. Pamięć (co ma o Tobie wiedzieć na stałe)
- 7a. Fakty stałe: strefa czasowa, miasto, kluczowe osoby (imiona/role bez danych wrażliwych), preferencje.
- 7b. Czego ma NIE zapamiętywać (tematy/dane wykluczone)?
- 7c. Czy mam aktywnie wyciągać fakty z rozmów (auto-memory) czy tylko gdy powiesz „zapamiętaj"?

## 8. Wizja „super-potężne"
- 8a. Jak wygląda dla Ciebie sukces za 30 dni — co ten asystent ma umieć, czego dziś nie umie?
- 8b. Jedna rzecz, która zrobiłaby na Tobie „wow".

---
Możesz odpowiedzieć na wszystko naraz albo po sekcjach. Każda odpowiedź = konkretna warstwa,
którą zbuduję i przetestuję. Sekcje 2–3 odblokowują integracje; 4–5 nadają proaktywność;
6 ustawia bezpieczne autonomiczne działanie.
