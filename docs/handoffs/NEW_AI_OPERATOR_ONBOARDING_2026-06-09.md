# New AI Operator Onboarding — Bartek Agent OS

Date: 2026-06-09

## Mission

Przejmujesz projekt `Acoste616/AIagent`. Celem nie jest kolejny chatbot ani system komend.
Celem jest prywatny **Poke++ / Bartek Agent OS**:

- iMessage-first kontakt z Bartkiem, Telegram jako fallback;
- Claude jako główny rozmówca/operator;
- Grok jako research/red-team/X/web/GitHub/Reddit operator;
- GPT/Codex jako opcja i worker do kodu/testów;
- Windows Desktop jako zawsze włączony serwer i lokalne "ręce" OpenClaw;
- pamięć Hermes-like: fakty, preferencje, projekty, źródła, historia decyzji;
- multi-agent council do złożonych zadań;
- zero Gmail/Calendar/Drive/Notion auth w tej fazie, zostawić integracje aplikacji na później.

Produkt ma być "żywy": ma pisać naturalnie, dopytywać, proponować następne kroki,
używać pamięci i narzędzi, a nie odsyłać użytkownika do debugów, komend i JSON.

Nie kopiuj ani nie rekonstruuj żadnego leaked/proprietary promptu Poke. Buduj własny
system z publicznych wzorców messaging-first UX.

## Exact Paths

Mac checkout:

```text
/Users/bartoszdomanski/Documents/Codex/2026-06-06/https-x-com-interaction-status-2062575428213285352/github-AIagent
```

Mac parent workspace:

```text
/Users/bartoszdomanski/Documents/Codex/2026-06-06/https-x-com-interaction-status-2062575428213285352
```

GitHub repo:

```text
Acoste616/AIagent
```

Windows production runtime:

```text
D:\ai-council
D:\ai-council\ai_council.py
D:\ai-council\tests\test_ai_council.py
D:\ai-council\docs
D:\ai-council\logs
D:\ai-council\state
D:\ai-council\artifacts
D:\ai-council\workspaces
D:\ai-council\recipes
D:\ai-council\windows-deploy
```

Windows env file, do not print secrets:

```text
C:\Users\Komputer\.config\ai-council\.env
```

OpenClaw/Hermes export on Windows:

```text
D:\openclaw-export
D:\openclaw-export\.codex-hybrid
D:\openclaw-export\shared-drive
```

Mac iMessage bridge:

```text
/Users/bartoszdomanski/.ai_council/imessage_bridge.py
/Users/bartoszdomanski/.ai_council/imessage_inbound_cursor
/Users/bartoszdomanski/.ai_council/imessage_sent_texts.jsonl
/Users/bartoszdomanski/Library/LaunchAgents/com.bartek.aicouncil.imessage.plist
/Users/bartoszdomanski/Library/Logs/ai_council_imessage.log
```

Mac SSH config:

```text
/Users/bartoszdomanski/.ssh/config
```

Main SSH alias:

```bash
ssh ai-council-desktop
```

Host:

```text
desktop-dk4hiv0.taild2cfba.ts.net
100.101.53.21
Windows user: Komputer
Mac key: /Users/bartoszdomanski/.ssh/codex_ed25519
```

## Verified State On 2026-06-09

- SSH from Mac to Windows works.
- `D:\ai-council` is running on Windows Desktop.
- `python -X utf8 ai_council.py doctor` reports:
  - Telegram token/user/chat configured;
  - Codex logged in through ChatGPT;
  - Claude logged in through `claude.ai`, subscription `max`;
  - Grok/xAI API OK, 9 Grok models visible;
  - scheduled task `Bartek AI Council Telegram` is `Running`.
- Mac launchd job `com.bartek.aicouncil.imessage` is running.
- iMessage bridge is enabled with inbound=true and recipient `bdomanskyy@icloud.com`.
- iMessage log shows multiple `inbound replied to ...` events on 2026-06-09.
- Runtime `/front` says `llm_router=on`, `poke_chat_llm=gated`, `errors_24h` not actionable.
- Runtime still leaks technical tail in some CLI responses: `route={...}` and `audit_log=...`.
  This is P0 for Poke-like polish.

Important sync warning:

- Mac repo `ai_council.py` and tests are smaller than Windows production files.
- Windows production runtime is likely ahead of the Mac checkout.
- Do not blindly overwrite `D:\ai-council` from Mac.
- First compare/sync intentionally, then patch.

## Read First

On Mac:

```bash
cd /Users/bartoszdomanski/Documents/Codex/2026-06-06/https-x-com-interaction-status-2062575428213285352/github-AIagent
git status --short --branch
sed -n '1,220p' CLAUDE.md
sed -n '1,220p' docs/POKE_CLONE_TARGET.md
sed -n '1,220p' docs/implementation/L4_92_IMESSAGE_TWO_WAY_LIVE.md
sed -n '1,220p' docs/operations/DESKTOP_SERVER_ACCESS.md
```

On Windows:

```bash
ssh ai-council-desktop "powershell -NoProfile -ExecutionPolicy Bypass -Command \"cd D:\ai-council; python -X utf8 ai_council.py doctor\""
ssh ai-council-desktop "powershell -NoProfile -ExecutionPolicy Bypass -Command \"cd D:\ai-council; python -X utf8 ai_council.py respond /front\""
```

## Immediate Product Goal

Make the assistant feel alive in iMessage:

1. iMessage is the main user-facing channel.
2. Claude is the default conversational operator/persona.
3. Grok and GPT/Codex remain selectable/support operators by intent or mention.
4. The assistant does not require slash commands for normal use.
5. It asks useful follow-up questions instead of dumping plans.
6. It uses memory and Desktop safely.
7. It hides route/debug/audit internals from user-facing replies.
8. It can coordinate multiple models for complex work.
9. It does not touch Gmail/Calendar/Drive/Notion auth in this phase.

## P0 Work

1. Source-of-truth audit:
   - compare Mac checkout vs `D:\ai-council`;
   - identify files where Windows is ahead;
   - decide whether to pull production back to Mac, patch on Windows, or patch Mac then deploy.

2. User-facing output hygiene:
   - no `route={...}`;
   - no `audit_log=...`;
   - no raw operator labels unless explicitly requested;
   - no long backend status unless `/front`, `/health`, `/doctor`.

3. Claude as main conversation operator:
   - ordinary iMessage chat should route to Claude/persona when useful;
   - keep cheap local handling for tiny ACK/status;
   - Grok for research;
   - Codex/GPT for code execution/implementation support;
   - preserve budget/cost controls.

4. iMessage live smoke:
   - send ordinary message;
   - send incomplete request and verify follow-up question;
   - send "chce jedzenie" and verify location/cuisine/budget style flow;
   - send "zrob research" and verify Grok/task/artifact path;
   - verify no debug tail in final iMessage response.

5. Desktop/OpenClaw hands:
   - keep all external/high-risk actions behind Risk Officer;
   - local read/test/code/docs OK;
   - no external writes or app OAuth setup now.

## Verification Commands

Mac:

```bash
PYTHONPYCACHEPREFIX=/tmp/ai-council-pycache python3 -m py_compile ai_council.py tests/test_ai_council.py
python3 -m pytest -q tests/test_ai_council.py
```

Windows:

```bash
ssh ai-council-desktop "powershell -NoProfile -ExecutionPolicy Bypass -Command \"cd D:\ai-council; python -X utf8 tests\test_ai_council.py\""
ssh ai-council-desktop "powershell -NoProfile -ExecutionPolicy Bypass -Command \"cd D:\ai-council; python -X utf8 ai_council.py respond 'chce jedzenie'\""
ssh ai-council-desktop "powershell -NoProfile -ExecutionPolicy Bypass -Command \"cd D:\ai-council; python -X utf8 ai_council.py respond /front\""
```

Mac bridge:

```bash
launchctl print gui/$(id -u)/com.bartek.aicouncil.imessage
tail -80 ~/Library/Logs/ai_council_imessage.log
```

## Safety

Allowed:

- local reads, diffs, docs, tests, focused patches;
- SSH checks on Windows;
- local runtime smoke;
- writing handoff reports.

Ask Bartek first:

- GitHub push;
- production deploy/restart if not already explicitly approved;
- editing secrets or auth files;
- app OAuth/login setup;
- Gmail/Calendar/Drive/Notion actions;
- external writes;
- payments, publishing, DNS, billing, deleting data, contacting people.

## End Of Round Report

Every round must end with:

- changed files;
- Mac tests;
- Windows tests/live smoke;
- iMessage smoke result;
- whether Claude is now default conversation operator;
- whether Grok/GPT/Codex are available as options;
- remaining blockers;
- exact next step.

