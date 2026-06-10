# Agent Loop — Iteracje 7–8 — L4.98: Claude głosem brain + ORDER_DRAFT na live path

Date: 2026-06-09/10 noc · Owner: Claude (loop owner)
Status: **DEPLOYED na D:\ai-council 2026-06-10 rano** (Desktop wrócił online).

DEPLOY WYKONANY: backup `backups/pre-L4.98`, Windows pytest **497/497** (po hermetyzacji 3 testów,
które na Windows wołały żywe Claude CLI), listener zrestartowany, smoke:
`respond-b64` 19.3 s round-trip (Claude CLI 13.2 s), odpowiedź naturalna/ludzka, zero debugu,
`costs.jsonl`: `operator=claude, detail="brain claude", completed, estimated_usd=0.0` —
**North Star potwierdzony na live path: Claude mówi, Grok = fallback/research, koszt głosu $0.**

## OBSERVE

- Po L4.97 produkcja działa i jest czysta, ALE live głos to `brain_decide` na **Groku** —
  North Star mówi: Claude rozmawia, Grok robi research. Mój Claude-dispatcher z L4.93 był
  martwym kodem na live path (`/chat → brain_loop`, nie `poke_chat_llm_response`).
- ORDER_DRAFT (L4.96) też był martwy na live path: brain nie znał kontraktu zamówień,
  a `sanitize_brain_reply` zabiłby linię markera (wygląda jak JSON).

## IMPLEMENT

### L4.98 — Claude jest głosem brain
- `brain_decide` = dyspozytor: `brain_decide_claude` (primary) → `brain_decide_grok` (fallback).
- `brain_decide_claude`: Claude CLI (subskrypcja, bez tools), `--append-system-prompt` =
  BRAIN_SYSTEM_PROMPT + opis BRAIN_TOOLS; narzędzia przez ścisły marker
  `TOOL: {"action":...,"args":{...}}` (parsowany do tej samej decyzji co tool_calls Groka);
  historia+pamięć w prompt; reserve/finalize("claude", detail="brain") — koszty pod kontrolą.
- Smalltalk dalej lokalny (zero kosztu/latencji), Grok brain nietknięty jako fallback.

### L4.98b — ORDER_DRAFT żyje w brain
- BRAIN_SYSTEM_PROMPT dostał sekcję ZAMÓWIENIA (zakaz udawania transakcji, marker ORDER_DRAFT).
- `brain_loop` reply path: `extract_order_draft` PRZED `sanitize_brain_reply`, potem stopka
  `/approve act-...` — draft R1, link handoff po zatwierdzeniu, płatność u Bartka.

## VERIFY

- Mac: **497/497** (4 nowe testy: dyspozytor Claude-first, parser TOOL-markera, gate grok-only,
  brain→order_handoff end-to-end). Testy brain z Windows pozostały zielone (przypięty operator
  grok tam, gdzie mockują xAI API).
- Windows: **PENDING — Tailscale pokazuje desktop-dk4hiv0 offline (ping 100% loss, last seen 5h)**.
  Prawdopodobnie maszyna śpi/reboot. Produkcja zostaje na działającym L4.97.

## Deploy po powrocie Desktopa (dokładna sekwencja)

```bash
cd <mac-repo>
ssh ai-council-desktop "powershell -NoProfile -Command \"cd D:\ai-council; New-Item -ItemType Directory -Force -Path backups/pre-L4.98 | Out-Null; Copy-Item ai_council.py backups/pre-L4.98/; Copy-Item tests/test_ai_council.py backups/pre-L4.98/\""
scp ai_council.py ai-council-desktop:'D:/ai-council/ai_council.py'
scp tests/test_ai_council.py ai-council-desktop:'D:/ai-council/tests/test_ai_council.py'
ssh ai-council-desktop "powershell -NoProfile -Command \"cd D:\ai-council; python -X utf8 -m pytest -q tests/test_ai_council.py\""
# restart listenera (kill python listenera + schtasks /Run) i smoke respond-b64 jak w L4.97
```

Uwaga deploy: zweryfikować flagi `claude` CLI na Windows (`--append-system-prompt` w wersji
zainstalowanej na Desktopie); przy błędzie flagi system sam spadnie na Grok brain (None→fallback),
ale wtedy North Star dalej niespełniony — sprawdzić w smoke `costs.jsonl` detail="brain claude".

## Score: 4/5 (architektura zgodna z North Star; minus za brak deploy/smoke — blocker sprzętowy)

## NEXT 3

1. Deploy L4.98 + smoke z pomiarem latencji Claude CLI (Measure-Command na respond-b64) — gdy Desktop wróci.
2. `AI_COUNCIL_IMESSAGE_PROACTIVE=true` (morning brief + nudges na iMessage) — flaga w .env za zgodą Bartka.
3. Watchdog na sen Desktopa (G-reliability): wykrywanie offline hosta + powiadomienie iMessage przez Mac bridge.
