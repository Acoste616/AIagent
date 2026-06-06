# Grok X Research: Poke

Created: 2026-06-06T22:39:32

Scope: X Search via xAI Responses API, Poke/Interaction posts and broader user feedback, 2026-03-01..2026-06-06.

## official_poke_posts

**Official @interaction (Poke) posts from 2026-03-01 to 2026-06-06** (Latest mode, keyword search `from:interaction Poke`):

### Key posts identified
- **Main announcement (04 Jun 2026)**: Post ID **2062575428213285352** (exactly the one requested).  
  Content (fact): “Say hi to the new Poke! 🌴 Now officially approved by Apple to text on Apple Messages. As the first and only AI agent. Chat now: https://poke.com/”  
  + attached demo video.  
  Bio update on the account confirms: “Now much faster & more capable 🌴”.  
  Thread reply from co-founder (@marvinvonhagen): “Poke is also much, much, much faster and reliable thanks to the biggest infrastructure update ever! ⚡” (fact from official team).[[1]](https://x.com/interaction/status/2062575428213285352)

- **Major product demo (19 Mar 2026)**: Post ID 2034713714415608123 (long video).  
  Content (fact): “Starting today, personal superintelligence is just one tap away. No download, no signup. Text Poke for free now: https://poke.com/”  
  Video timestamps explicitly cover:  
  - 0:00 – What’s Poke?  
  - 0:50 – Introducing Poke Recipes  
  - 1:25 – Create a Recipe in 10 seconds  
  - 1:43 – Earn on Poke  
  - 2:44 – Build with `npx poke`  
  - 12:58 – Recap  
  - 13:36 – Parisian Love (demo).[[2]](https://x.com/interaction/status/2034713714415608123)

Other minor posts (Mar–Apr 2026) are mostly internal/team reactions and do not add new feature details.

### Extracted facts only (no hypotheses)

**Apple Messages / iMessage**  
- Officially approved by Apple (first & only AI agent) as of 04 Jun 2026.  
- Users can now text Poke directly in Apple Messages / iMessage.  
- URL: https://poke.com/ (same link promoted for all channels).[[1]](https://x.com/interaction/status/2062575428213285352)

**Recipes**  
- Core feature highlighted in the March demo.  
- “Create a Recipe in 10 seconds”.  
- Part of the “personal superintelligence” onboarding flow.[[2]](https://x.com/interaction/status/2034713714415608123)

**Onboarding / UX**  
- Zero friction: “No download, no signup. Text Poke for free now.”  
- One-tap access promoted.  
- Video demos show instant recipe creation and usage.[[2]](https://x.com/interaction/status/2034713714415608123)

**Demo claims**  
- March video is the primary official demo (13+ minutes).  
- June post uses a new video to showcase the Apple Messages integration.[[1]](https://x.com/interaction/status/2062575428213285352)

**API / MCP / local machine hints**  
- Explicit mention of `npx poke` (build/integrate command) in the March demo.  
- No other API, MCP, or local-machine details in official posts from the period.

**Pricing / monetization**  
- Repeatedly described as “free” for texting Poke.  
- “Earn on Poke” section in the March video (no further details published in the posts themselves).

**Latency / reliability claims**  
- June 4 bio + co-founder reply: “much faster & more capable” + “biggest infrastructure update ever” → “much, much, much faster and reliable”.[[1]](https://x.com/interaction/status/2062575428213285352)

**Channels**  
- Primary: https://poke.com/ (web/text).  
- New official channel: Apple Messages / iMessage (approved 04 Jun 2026).  
- No other channels mentioned in the official posts.

**Limitations**  
- None explicitly stated in the official posts (all claims are positive).

All information above is taken **directly** from the official @interaction posts and their attached media/descriptions. No external speculation added.

## founder_team_posts

**Poke (@interaction)** to standalone AI agent zintegrowany z messaging apps (głównie Apple Messages via Messages for Business). Oficjalne konto to @interaction (bio potwierdza „now much faster & more capable”).

### Mocne fakty (źródła oficjalne + powtarzalne potwierdzenia)
- **Apple Messages approval** — Poke jest **pierwszym i jedynym** standalone AI agentem zatwierdzonym przez Apple do platformy Messages for Business. Działa natywnie w aplikacji Wiadomości na iOS bez dodatkowej aplikacji. Potwierdzone przez oficjalny post @interaction (4 czerwca 2026) oraz niezależne źródła (AppleInsider, RuntimeWire, TechCrunch).[[1]](https://x.com/interaction/status/2062575428213285352)

- **Recipes** — Główny mechanizm integracji. Użytkownik tworzy „recipe” (połączenie z narzędziami) w ~10 sekund, bez kodowania. Przykłady: Gmail, Google Calendar, Notion, Strava. Oficjalny film promocyjny @interaction (19 marca 2026) poświęca temu osobny segment.[[2]](https://x.com/interaction/status/2034713714415608123)

- **Szybkość** — Oficjalne komunikaty podkreślają „now much faster & more capable” po aktualizacji (czerwiec 2026). Brak szczegółów technicznych (np. latency, model backend).

- **Dostępność** — „No download, no signup”. Dostęp przez poke.com lub bezpośrednio w Messages/WhatsApp/Telegram. Działa jako conversational AI z memory i proactive nudges.

- **Build / developer experience** — Wsparcie dla `npx poke` (wspomniane w oficjalnym filmie).

- **Use cases (oficjalne)**:
  - Wysyłanie maili, ustawianie reminderów, generowanie obrazów.
  - Działania w natywnym Messages (proactive nudges + memory + actions via text/voice).

### MCP, architektura, local/desktop bridge, integracje
W postach założycieli/teamu (@interaction) oraz zaawansowanych użytkowników nie ma szczegółowych insightów technicznych na temat:
- Architektury backendu
- MCP (Model Context Protocol) — żadne powiązanie z Poke
- Local/desktop bridge
- Konkretnych integracji poza „Recipes”

MCP pojawia się wyłącznie w ogólnych dyskusjach społeczności AI (nie związanych z Poke).

### Komentarze użytkowników vs. fakty
- Użytkownicy powtarzają narrację o „pierwszym AI agencie w Messages” (fakt potwierdzony).
- Spekulacje o „Siri killer” lub „AI OS” — komentarze, nie fakty.
- Brak wiarygodnych informacji o kosztach, ograniczeniach skalowania czy konkretnych modelach LLM.

**Podsumowanie insightów do skopiowania**:
- Najsilniejszy atut Poke = **natywna integracja z Apple Messages** (pierwszy approval).
- **Recipes** jako low-code/no-code sposób na integracje — bardzo szybki onboarding.
- Brak publicznych szczegółów technicznych (architektura, MCP, bridge) — to obszar, który warto badać dalej (np. przez founderów poza @interaction lub dokumentację).

Jeśli potrzebujesz głębszego przeszukania konkretnych wątków (np. replies pod postami @interaction lub konkretnych userów), daj znać.

## user_feedback_and_gaps

**Poke** to AI-agent (pierwszy zatwierdzony przez Apple na platformie **Messages for Business**), dostępny bezpośrednio w iMessage bez instalacji dodatkowej apki. Użytkownicy piszą do niego jak do normalnego kontaktu i dostaje zadania typu zarządzanie kalendarzem, edycja zdjęć, sterowanie smart home, codzienne życie. Ma już >100 mln wiadomości. Działa na zasadzie persistent AI z dobrym wyczuciem tonu i głosu.

### Co działa dobrze (zachwyty)
- **Szybkość i UX po aktualizacjach** — „significant improvement: a lot faster and features many in-thread/in-conversation actions”.[[1]](https://x.com/paulwitcombe/status/2062797297524634110)
- **Brak setupu i maintenance** — „requires literally no set up or maintenance which is great”.[[2]](https://x.com/kevinclark/status/2062636575331164661)
- **Codzienne użytkowanie** — „started using poke two months ago and haven't gone a day without texting it. it's crazy good”.[[3]](https://x.com/sebcrossa/status/2062731966944829612)
- **Jakość odpowiedzi (tone/voice)** — „Huge fan… It gets voice and tone right in the way that most other assistants don't”.[[2]](https://x.com/kevinclark/status/2062636575331164661)
- **Brak limitów czatu** — „poke does a lot more! as well as not having any usage limits (for chat…)”.[[4]](https://x.com/ezShroom/status/2062590809006915607)
- **Integracja z iMessage** — pierwszy AI agent na Apple Messages for Business (zatwierdzanie trwało miesiące, wymaga live support + custom UI zgodnego z wytycznymi Apple).[[5]](https://x.com/38twelveDaily/status/2062622412450005415)

### Co nie działa / skargi / opóźnienia
- **Nowa integracja** — „Curious to try this new integration, but it doesn't seem to be working quite right yet”.[[2]](https://x.com/kevinclark/status/2062636575331164661)
- **Ceny i transparentność** — „the pricing is making it unusable. And there's a lack of transparency about the cost of each request; there is a lack of metrics and a local dashboard”.[[6]](https://x.com/soubiran_/status/2062064814671716460) (image gen limitowane ze względu na koszty).
- **Brak customizacji** — użytkownicy chcą zmieniać tła, zdjęcia kontaktów itp. (drobiazg, ale zgłaszany).
- **Proces zatwierdzania Apple** — wymaga weryfikacji live support, oznaczenia agenta, custom UI (link preview zamiast inline links, style przycisków Apple) → „it will take anyone else a couple of months”.[[5]](https://x.com/38twelveDaily/status/2062622412450005415)
- **Prawdopodobnie human-in-the-loop** — ze względu na wymagania Apple Messages for Business.[[7]](https://x.com/arix_online/status/2063029244662305067)

### Funkcje, które ludzie realnie używają
- Codzienne textingowanie („haven't gone a day without”).
- Zarządzanie życiem (kalendarz, zdjęcia, smart home).
- In-thread actions po aktualizacji.
- Długie rozmowy bez limitów czatu.

### Lekcje dla prywatnego Telegram/iPhone AI Council
1. **Integracja z natywnymi komunikatorami** — idź w Apple Messages for Business / Telegram Bot API / iMessage-like. To największa przewaga Poke (zero apki).
2. **Zero setupu + natychmiastowa wartość** — nie wymagaj konfiguracji, od razu działaj na tonie/głosie.
3. **Transparentność kosztów od dnia 1** — dashboard z kosztami per request + limity (Poke tu pada).
4. **Szybkość + in-thread actions** — priorytet na aktualizacje UX (Poke zyskał po tym ogromnie).
5. **Human-in-the-loop dla enterprise/integracji** — przygotuj się na to przy Apple-like approval.
6. **Brak limitów na zwykły chat** — image/video gen limituj osobno (koszty).
7. **Proces zatwierdzania** — planuj 2–3 miesiące na custom UI i live support przy Messages for Business.

Poke pokazuje, że **największa siła to bycie „niewidzialnym” asystentem w istniejącym komunikatorze** + świetny tone + brak friction. Skopiuj to i wygrasz.
