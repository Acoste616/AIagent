[Grok X Research] (17377ms)
**Fakty (z linkami do postów, gdzie dostępne):**

- **Poke (@interaction)** to pierwszy zewnętrzny agent AI zatwierdzony przez Apple do natywnej pracy w iMessage/Messages for Business. Użytkownicy komunikują się wyłącznie przez SMS/iMessage (tekst/głos), bez appki i signupu. Agent obsługuje realne zadania: e-maile, kalendarz, rezerwacje, smart home, wyszukiwanie. Apple zarabia na integracji opłatą per-user od startupu.  
  Źródła: [post:12], [post:14], [post:0] (szczegóły approval: miesiące weryfikacji live support, etykietowania agenta, custom UI pod wytyczne Apple – link preview zamiast inline links, button styles).

- **Poke Recipes** = gotowe automatyzacje tworzone w ~10 sekund (przez iMessage lub https://poke.com/kitchen). Po stworzeniu recipe jest natychmiast aktywne – użytkownik wysyła link lub po prostu pisze do Poke. Przykłady:  
  - Domain Tracker (proaktywne alerty o expiry 30/7/1 dni) → https://poke.com/r/ae15scQU_4P  
  - Rain prompt (proaktywne przypomnienie o schowaniu poduszek) → https://poke.com/r/zFCWphQoSnV  
  - Shopify Product Finder, Shein deal hunter, F1 lap scout, Granola notes → Supermemory.  
  Źródła: [post:16], [post:22], [post:28], [post:18], [post:21], [post:23], [post:15], [post:25].

- **Aktywacja i follow-upy**: Recipe działa po wysłaniu linku lub bezpośrednim teksie do Poke. Są wbudowane proaktywne alerty (np. domain expiry, weather). Nie ma osobnego „approval” użytkownika – recipe jest od razu gotowe. Udostępnianie: linki do poke.com/r/...

- **Ograniczenia i friction**:  
  - Apple approval jest bardzo surowy i długi (miesiące).  
  - Automatyzacja iMessage jest generalnie sprzeczna z TOS Apple (wyjątek dla Poke).  
  - Brak szczegółowych danych o limitach rate’ów lub nie-odpowiadaniu w wynikach wyszukiwania.

- **UX i onboarding**: Zero friction dla użytkownika końcowego („no download, no signup”). Recipe Creator jest wbudowany w iMessage. Dobre friction stosowane przy płatnościach/onboardingu w innych appkach (np. 60+ sekund celowo).

- **iMessage vs Telegram**: Poke działa natywnie w iMessage (pierwszy taki agent). Lekcja: integracja z natywnym messagingiem (Telegram Bot API + threads) daje ogromną przewagę UX.

**Hipotezy (niepewne, brak bezpośrednich dowodów):**
- Skargi na „not responding” są rzadkie, bo Poke ma silną infrastrukturę live support (wymagana przy Apple approval) – ale to tylko hipoteza z braku negatywnych postów.
- Proaktywne follow-upy są kluczowym elementem retencji (przykłady domain/rain sugerują, że działają dobrze).
- Koszty: nie ma publicznych danych o cenie dla użytkownika końcowego (prawdopodobnie darmowy); startup płaci Apple.

**Lekcje do skopiowania do prywatnego Telegram AI Council (po Recipe Creator v0):**
- Natychmiastowa aktywacja recipe po stworzeniu (brak osobnego approval flow).
- Proaktywne follow-upy (np. „czy chcesz teraz wykonać X?”).
- Udostępnianie recipe przez link.
- Natywna integracja z messagingiem (Telegram threads + bot commands).
- Zero signup dla użytkownika.

**Bezpieczeństwo dla prywatnego agenta (Gmail/Calendar/Drive read-only first):**
- Zawsze read-only na start.
- Explicit confirmation przed jakąkolwiek akcją write.
- Sandbox + logi + human-in-loop przy sensitive actions.
- Nigdy nie udostępniaj pełnych credentials – tylko scoped OAuth tokens.

**Dokładnie jeden najlepszy next implementation sprint dla Codex:**
**Sprint: „Proactive Recipe Activation + Telegram-native follow-ups (read-only safety)”**  
Cel: Po stworzeniu recipe w v0 – automatyczna aktywacja + proaktywne powiadomienia w Telegramie (np. „Recipe X gotowe. Chcesz test? Tak/Nie”).  
Zakres:  
1. Read-only integracja Gmail/Calendar/Drive (OAuth scoped).  
2. Trigger po stworzeniu recipe → wysłanie linku + pierwszy proaktywny follow-up.  
3. Safety: confirmation gate + read-only only.  
Czas: 1-2 tygodnie. To bezpośrednio klonuje najmocniejsze elementy Poke (aktywacja + proaktywność) przy minimalnym ryzyku.
