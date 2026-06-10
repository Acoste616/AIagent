"""Split from tests/test_ai_council.py (audit 3.3) — classes preserved 1:1."""
# ruff: noqa: F403, F405
import unittest

from council_test_shared import *


class RoutingTests(unittest.TestCase):
    def test_plain_message_routes_to_fast_chat(self):
        route = ai_council.route_text("bez prefiksu")

        self.assertEqual(route["command"], "/chat")
        self.assertEqual(route["operators"], ["host"])
        self.assertEqual(route["prompt"], "bez prefiksu")
        self.assertFalse(ai_council.route_needs_task(route))
        self.assertFalse(ai_council.route_should_background(route))

    def test_chat_response_is_clean_brain_reply(self):
        # /chat is now composed by the brain — a clean human reply, no [Council]/debug sludge.
        with patch.object(ai_council, "brain_decide", return_value={"action": "reply", "text": "Tak, jestem — w czym pomóc?"}):
            response = ai_council.poke_chat_response("działasz?", chat_id="553")
        self.assertIn("jestem", response.lower())
        for bad in ("[Council]", "Komendy:", "task-", "DECYZJA:", "ETAP:"):
            self.assertNotIn(bad, response)

    def test_poke_gap_feedback_routes_to_short_operator_gap(self):
        with temp_dir() as tmp:
            root = Path(tmp)
            with patch.object(ai_council, "STATE_DIR", root / "state"), patch.object(
                ai_council, "TASKS_FILE", root / "state" / "tasks.jsonl"
            ), patch.object(ai_council, "IMPROVEMENTS_FILE", root / "state" / "improvements.jsonl"), patch.object(
                ai_council, "LOG_DIR", root / "logs"
            ), patch.object(ai_council, "AUDIT_LOG", root / "logs" / "audit.jsonl"), patch.object(
                ai_council, "WORKSPACES_DIR", root / "workspaces"
            ), patch.object(ai_council, "ARTIFACTS_DIR", root / "artifacts"), patch.object(
                ai_council, "REPORTS_DIR", root / "reports"
            ), patch.object(ai_council, "ERRORS_DIR", root / "errors"), patch.object(
                ai_council, "RECIPES_DIR", root / "recipes"
            ), patch.object(ai_council, "BACKGROUND_JOB_SPECS_DIR", root / "state" / "background_job_specs"):
                route = ai_council.route_message("Ani nie odpowiada on jak poke nie ma takich możliwości, gdzie ten cel?")
                response = ai_council.build_response(route)
                rows = ai_council.read_jsonl(root / "state" / "improvements.jsonl")

        self.assertEqual(route["command"], "/poke-gap")
        self.assertIn("Poke Gap L4.48", response)
        self.assertIn("DECYZJA: masz rację", response)
        self.assertIn("FAKTY:", response)
        self.assertIn("BRAKI P0:", response)
        self.assertIn("TERAZ:", response)
        self.assertIn("iPhone recipe payloady", response)
        self.assertIn("NEXT:", response)
        self.assertIn("/shortcuts recipes", response)
        self.assertIn("TWOJA WIADOMOŚĆ:", response)
        self.assertIn("improvement=imp-", response)
        self.assertNotIn("Drive write/read-before-write", response)
        self.assertNotIn("Gotowe:", response)
        self.assertNotIn("/goal", response)
        self.assertLess(len(response), 900)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["source"], "poke_gap")

    def test_short_greeting_is_clean_local_smalltalk(self):
        # "hej" is smalltalk -> answered locally (no LLM call), clean, no [Council].
        with patch.object(ai_council, "request_json") as request_json:
            response = ai_council.poke_chat_response("hej", chat_id="553")
        request_json.assert_not_called()
        self.assertTrue(response.strip())
        self.assertNotIn("[Council]", response)

    def test_short_operator_question_can_use_llm_front_without_status_dump(self):
        # poke_chat_should_use_llm is the legacy gate (brain_loop no longer uses it); test its
        # logic with a key present (the suite forces XAI_API_KEY empty by default).
        def grok_cfg(key, default=""):
            return {
                "XAI_API_KEY": "xai-test",
                "AI_COUNCIL_POKE_CHAT_USE_GROK": "true",
                "AI_COUNCIL_POKE_CHAT_OPERATOR": "grok",
            }.get(key, default)

        with patch.object(ai_council, "cfg", side_effect=grok_cfg):
            self.assertTrue(ai_council.poke_chat_should_use_llm("jak to otworzyć tutaj?"))
            self.assertTrue(ai_council.poke_chat_should_use_llm("który model będzie ze mną rozmawiał?"))
            self.assertFalse(ai_council.poke_chat_should_use_llm("co tam u ciebie"))
            self.assertFalse(ai_council.poke_chat_should_use_llm("status"))
            self.assertFalse(ai_council.poke_chat_should_use_llm("co dalej"))

        # L4.94: with Claude as the (default) front voice, small talk gets a natural
        # LLM reply instead of a canned fallback; status/ack stays local and cheap.
        def claude_cfg(key, default=""):
            return {"XAI_API_KEY": "xai-test"}.get(key, default)

        with patch.object(ai_council, "cfg", side_effect=claude_cfg):
            self.assertTrue(ai_council.poke_chat_should_use_llm("co tam u ciebie"))
            self.assertFalse(ai_council.poke_chat_should_use_llm("status"))
            self.assertFalse(ai_council.poke_chat_should_use_llm("ok"))

    def test_default_chat_is_clean_brain_reply(self):
        with patch.object(ai_council, "brain_decide", return_value={"action": "reply", "text": "Jasne — powiedz tylko o czym dokładnie."}):
            response = ai_council.poke_chat_response("normalne krótkie pytanie", chat_id="553")
        self.assertIn("Jasne", response)
        for bad in ("[Council]", "Komendy:", "/goal", "DECYZJA:", "FAKTY:"):
            self.assertNotIn(bad, response)

    def test_co_dalej_routes_to_compact_agent_next(self):
        with temp_dir() as tmp:
            root = Path(tmp)
            with patch.object(ai_council, "IMPROVEMENTS_FILE", root / "state" / "improvements.jsonl"), patch.object(
                ai_council, "TASKS_FILE", root / "state" / "tasks.jsonl"
            ), patch.object(ai_council, "ERRORS_FILE", root / "state" / "errors.jsonl"), patch.object(
                ai_council, "ACTIONS_FILE", root / "state" / "actions.jsonl"
            ), patch.object(ai_council, "NUDGES_FILE", root / "state" / "nudges.jsonl"), patch.object(
                ai_council, "LOG_DIR", root / "logs"
            ), patch.object(ai_council, "AUDIT_LOG", root / "logs" / "audit.jsonl"), patch.object(
                ai_council, "WORKSPACES_DIR", root / "workspaces"
            ), patch.object(ai_council, "ARTIFACTS_DIR", root / "artifacts"), patch.object(
                ai_council, "REPORTS_DIR", root / "reports"
            ), patch.object(ai_council, "RECIPES_DIR", root / "recipes"), patch.object(
                ai_council, "BACKGROUND_JOB_SPECS_DIR", root / "state" / "background_job_specs"
            ):
                ai_council.create_improvement(
                    source="poke_gap",
                    title="Poke Host gap: domyślna odpowiedź Telegrama musi działać jak operator",
                    summary="Fix default UX.",
                    priority="P0",
                )
                route = ai_council.route_message("co dalej", chat_id="553")
                response = ai_council.build_response(route, chat_id="553")

        self.assertEqual(route["command"], "/agent")
        self.assertEqual(route["prompt"], "next")
        self.assertIn(f"Agent Next {ai_council.POKE_NEXT_FRONT_VERSION}", response)
        self.assertIn("Poke Host gap", response)
        self.assertNotIn("PRIORYTET:", response)
        self.assertLess(len(response), 700)

    def test_research_question_about_poke_routes_to_poke_research_background(self):
        route = ai_council.route_message("czy możesz zrobić research poke i powiedzieć co wdrożyć", chat_id="553")

        self.assertEqual(route["command"], "/poke-research")
        self.assertTrue(ai_council.route_should_background(route))
        self.assertIn("research poke", route["prompt"].lower())

    def test_poke_clone_goal_routes_to_grok_prepass_without_slash(self):
        route = ai_council.route_message(
            "Chcę sklonować Poke z OpenClaw i Hermes, ustal funkcje i integracje do wdrożenia",
            chat_id="553",
        )

        self.assertEqual(route["command"], "/poke-research")
        self.assertEqual(route["operators"], ["grok"])
        self.assertEqual(route["mode"], "poke_research_prepass")
        self.assertEqual(route["prepass_version"], ai_council.POKE_RESEARCH_PREPASS_VERSION)
        self.assertTrue(ai_council.route_should_background(route))
        self.assertIn("OpenClaw/Hermes", route["prompt"])
        self.assertIn("najbliższego patcha", route["prompt"])

    def test_poke_missing_features_question_routes_to_grok_prepass(self):
        route = ai_council.route_message("sprawdź czego brakuje do Poke i co wdrożyć najpierw", chat_id="553")

        self.assertEqual(route["command"], "/poke-research")
        self.assertEqual(route["mode"], "poke_research_prepass")
        self.assertTrue(ai_council.route_should_background(route))

    def test_benign_poke_recipe_check_does_not_start_paid_prepass(self):
        route = ai_council.route_message("sprawdź czy ten recipe poke działa", chat_id="553")

        self.assertNotEqual(route["command"], "/poke-research")

    def test_plain_poke_frustration_stays_short_gap_response(self):
        route = ai_council.route_message("Ani nie odpowiada on jak poke nie ma takich możliwości, gdzie ten cel?")

        self.assertEqual(route["command"], "/poke-gap")
        self.assertEqual(route["mode"], "poke_gap")

    def test_empty_agent_next_can_run_feature_evolution_loop(self):
        with temp_dir() as tmp:
            root = Path(tmp)
            with patch.object(ai_council, "IMPROVEMENTS_FILE", root / "state" / "improvements.jsonl"), patch.object(
                ai_council, "TASKS_FILE", root / "state" / "tasks.jsonl"
            ), patch.object(ai_council, "ERRORS_FILE", root / "state" / "errors.jsonl"), patch.object(
                ai_council, "ACTIONS_FILE", root / "state" / "actions.jsonl"
            ), patch.object(ai_council, "NUDGES_FILE", root / "state" / "nudges.jsonl"), patch.object(
                ai_council, "LOG_DIR", root / "logs"
            ), patch.object(
                ai_council, "AUDIT_LOG", root / "logs" / "audit.jsonl"
            ), patch.object(ai_council, "WORKSPACES_DIR", root / "workspaces"), patch.object(
                ai_council, "ARTIFACTS_DIR", root / "artifacts"), patch.object(
                ai_council, "REPORTS_DIR", root / "reports"), patch.object(
                ai_council, "RECIPES_DIR", root / "recipes"), patch.object(
                ai_council, "BACKGROUND_JOB_SPECS_DIR", root / "state" / "background_job_specs"), patch.object(
                ai_council, "shortcut_setup_agent_item", return_value=None
            ):
                response = ai_council.build_response(ai_council.route_message("co dalej", chat_id="553"), chat_id="553")

        self.assertIn("feature_evolution_loop", response)
        self.assertIn("RUN: /agent run feature_evolution_loop", response)

    def test_status_summary_routes_to_front_not_generic_chat(self):
        route = ai_council.route_message("napisz mi krótkie podsumowanie statusu", chat_id="553")

        self.assertEqual(route["command"], "/front")
        self.assertEqual(route["mode"], "front")

    def test_status_summary_front_response_is_compact(self):
        with temp_dir() as tmp:
            root = Path(tmp)
            with patch.object(ai_council, "TASKS_FILE", root / "state" / "tasks.jsonl"), patch.object(
                ai_council, "ERRORS_FILE", root / "state" / "errors.jsonl"
            ), patch.object(ai_council, "AUDIT_LOG", root / "logs" / "audit.jsonl"), patch.object(
                ai_council, "COSTS_FILE", root / "state" / "costs.jsonl"
            ), patch.object(ai_council, "CONTROL_FILE", root / "state" / "control.json"):
                response = ai_council.front_reliability_response("napisz mi krótkie podsumowanie statusu")

        self.assertIn(f"Status {ai_council.POKE_NEXT_FRONT_VERSION}", response)
        self.assertIn("DECYZJA:", response)
        self.assertIn("FAKTY:", response)
        self.assertNotIn("last_telegram_update", response)
        self.assertLess(len(response), 500)

    def test_poke_chat_fallback_gap_is_pure_and_precise(self):
        with temp_dir() as tmp:
            root = Path(tmp)
            with patch.object(ai_council, "IMPROVEMENTS_FILE", root / "state" / "improvements.jsonl"), patch.object(
                ai_council, "TASKS_FILE", root / "state" / "tasks.jsonl"
            ), patch.object(ai_council, "ERRORS_FILE", root / "state" / "errors.jsonl"):
                ai_council.append_jsonl(
                    ai_council.TASKS_FILE,
                    {"task_id": "task-1", "status": "running_background", "created_at": ai_council.utc_now()},
                )
                ai_council.append_jsonl(
                    ai_council.ERRORS_FILE,
                    {"error_id": "err-1", "created_at": ai_council.utc_now(), "message": "x"},
                )
                gap = ai_council.poke_chat_fallback("nie odpowiada jak Poke")
                neutral = ai_council.poke_chat_fallback("pokemon jest spoko")
                rows = ai_council.read_jsonl(root / "state" / "improvements.jsonl")

        self.assertIn("Poke Gap L4.48", gap)
        self.assertIn("improvement=not_logged_chat_fallback", gap)
        self.assertIn("running_tasks=1", gap)
        self.assertIn("errors_24h=1", gap)
        self.assertNotIn("Poke Gap", neutral)
        self.assertEqual(rows, [])

    def test_respond_dry_prints_response_and_audits(self):
        with temp_dir() as tmp:
            root = Path(tmp)
            stdout = io.StringIO()
            with patch.object(ai_council, "LOG_DIR", root / "logs"), patch.object(
                ai_council, "AUDIT_LOG", root / "logs" / "audit.jsonl"
            ), patch.object(ai_council, "CONVERSATIONS_FILE", root / "state" / "conversations.jsonl"), contextlib.redirect_stdout(stdout):
                ai_council.respond_dry("hej", chat_id="553")
                rows = ai_council.read_jsonl(root / "logs" / "audit.jsonl")

        output = stdout.getvalue()
        self.assertTrue(output.strip())
        self.assertNotIn("[Council]", output)
        # L4.93 P0: debug tail (route=/audit_log=) must NOT leak to user-facing output.
        self.assertNotIn("route=", output)
        self.assertNotIn("audit_log=", output)
        self.assertEqual(rows[-1]["status"], "dry_response")

    def test_research_wraps_prompt_as_polish_research_brief(self):
        captured = {}

        def fake_grok(prompt, max_chars=None):
            captured["prompt"] = prompt
            return "[Grok]\nok"

        with patch.object(ai_council, "grok_response", side_effect=fake_grok):
            response = ai_council.build_response({"command": "@research", "prompt": "rynek kancelarii AI"})

        self.assertTrue(response.startswith("[Council]"))
        self.assertIn("Research gotowy", response)
        self.assertIn("ok", response)
        self.assertNotIn("[Grok]", response)
        self.assertIn("brief research", captured["prompt"].lower())
        self.assertIn("po polsku", captured["prompt"].lower())
        self.assertIn("rynek kancelarii AI", captured["prompt"])

    def test_direct_operator_response_uses_unified_front(self):
        with patch.object(ai_council, "codex_response", return_value="[Codex] (123ms)\nTak, działam."):
            response = ai_council.build_response({"command": "@codex", "operators": ["codex"], "prompt": "ping"})

        self.assertTrue(response.startswith("[Council]"))
        self.assertIn("Odpowiedź gotowa", response)
        self.assertIn("Tak, działam.", response)
        self.assertNotIn("[Codex]", response)

    def test_all_operator_response_uses_unified_front(self):
        with patch.object(ai_council, "codex_response", return_value="[Codex]\nfeasibility"), patch.object(
            ai_council, "claude_response", return_value="[Claude]\nplan"
        ), patch.object(ai_council, "grok_route_response", return_value="[Grok]\nresearch"):
            response = ai_council.build_response({"command": "@all", "operators": ["codex", "claude", "grok"], "prompt": "ping"})

        self.assertTrue(response.startswith("[Council]"))
        self.assertIn("Konsultacja gotowa", response)
        self.assertIn("Technicznie: feasibility", response)
        self.assertIn("Plan: plan", response)
        self.assertIn("Research: research", response)
        self.assertNotIn("[Codex]", response)
        self.assertNotIn("[Claude]", response)
        self.assertNotIn("[Grok]", response)

    def test_front_operator_title_ignores_failure_words_in_successful_body(self):
        raw = "[Grok]\nResearch: errors, failed deployments and timeout reports are discussed in the source material."

        response = ai_council.front_operator_response("@research", raw)

        self.assertIn("Research gotowy", response)
        self.assertNotIn("Operator nie wykonał zadania", response)

    def test_front_operator_title_detects_status_prefix_failure(self):
        raw = "[Grok] blocked: global kill switch active"

        response = ai_council.front_operator_response("@research", raw)

        self.assertIn("Operator nie wykonał zadania", response)
        self.assertIn("blocked: global kill switch active", response)

    def test_task_command_routes_to_host_queue(self):
        route = ai_council.route_text("/task zrób research AI Council")

        self.assertEqual(route["command"], "/task")
        self.assertEqual(route["operators"], ["host"])
        self.assertEqual(route["prompt"], "zrób research AI Council")

    def test_capabilities_command_routes_to_host(self):
        route = ai_council.route_text("/capabilities")

        self.assertEqual(route["command"], "/capabilities")
        self.assertEqual(route["operators"], ["host"])

    def test_goal_command_routes_to_host(self):
        route = ai_council.route_text("/goal")

        self.assertEqual(route["command"], "/goal")
        self.assertEqual(route["operators"], ["host"])

    def test_l2_commands_route_to_host_or_council(self):
        cases = {
            "/cost": ("/cost", ["host"]),
            "/control": ("/control", ["host"]),
            "/health": ("/health", ["host"]),
            "/cancel task-1": ("/cancel", ["host"]),
            "/agent": ("/agent", ["host"]),
            "/inbox": ("/agent", ["host"]),
            "/shortcuts": ("/shortcuts", ["host"]),
            "/drafts": ("/drafts", ["host"]),
            "/status task-1": ("/status", ["host"]),
            "/progress task-1": ("/progress", ["host"]),
            "/details task-1": ("/details", ["host"]),
            "/facts task-1": ("/facts", ["host"]),
            "/next task-1": ("/next", ["host"]),
            "/actions": ("/actions", ["host"]),
            "/approve act-1": ("/approve", ["host"]),
            "/deny act-1": ("/deny", ["host"]),
            "/risk wyślij email": ("/risk", ["host"]),
            "/execute act-1": ("/execute", ["host"]),
            "/verify act-1": ("/verify", ["host"]),
            "/rollback act-1": ("/rollback", ["host"]),
            "/memory recent": ("/memory", ["host"]),
            "/jobs": ("/jobs", ["host"]),
            "/propose test": ("/propose", ["host"]),
            "/write shared/test.txt = ok": ("/write", ["host"]),
            "/append shared/test.txt = ok": ("/append", ["host"]),
            "/patch shared/test.txt :: ok => better": ("/patch", ["host"]),
            "/chat test": ("/chat", ["host"]),
            "/plan-action ogarnij temat": ("/plan-action", ["host"]),
            "/start-task task-1": ("/start-task", ["host"]),
            "/errors": ("/errors", ["host"]),
            "/nudges": ("/nudges", ["host"]),
            "/sources": ("/sources", ["host"]),
            "/source search memory Poke": ("/source", ["host"]),
            "/connectors": ("/connectors", ["host"]),
            "/connector check github": ("/connector", ["host"]),
            "/improvements": ("/improvements", ["host"]),
            "/improve next": ("/improve", ["host"]),
            "/followups": ("/followups", ["host"]),
            "/loops": ("/loops", ["host"]),
            "/goal": ("/goal", ["host"]),
            "/flow zrób pełny plan": ("/flow", ["claude-flow"]),
            "@claude-flow zrób pełny plan": ("@claude-flow", ["claude-flow"]),
            "/council zrób plan": ("/council", ["codex", "claude", "grok"]),
        }

        for text, expected in cases.items():
            with self.subTest(text=text):
                route = ai_council.route_text(text)
                self.assertEqual(route["command"], expected[0])
                self.assertEqual(route["operators"], expected[1])

    def test_natural_intents_route_without_slash(self):
        cases = {
            "status": "/status",
            "koszty": "/cost",
            "pokaż kontrolę": "/control",
            "pokaż błędy": "/errors",
            "pokaż nudges": "/nudges",
            "pokaż źródła": "/sources",
            "szukaj w źródłach memory Poke": "/source",
            "pokaż konektory": "/connectors",
            "sprawdź connector github": "/connector",
            "podłącz github": "/connector",
            "sync gmail Poke": "/connector",
            "ogarnij mi research Poke": "/plan-action",
            "przygotuj mi plan wdrożenia": "/plan-action",
            "przygotuj mi raport z gmail": "/plan-action",
            "hej, czy możesz mi jutro przypomnieć o spotkaniu z Tomkiem?": "/plan-action",
            "start task-20260606-120000-abcdef": "/start-task",
            "pokaż ulepszenia": "/improvements",
            "pokaż follow-upy": "/followups",
            "pokaż pętle": "/loops",
            "health": "/health",
            "front status": "/front",
            "czemu bot nie odpowiada": "/front",
            "co dalej": "/agent",
            "agent inbox": "/agent",
            "czym się zająć": "/agent",
            "iphone shortcuts": "/shortcuts",
            "iphone recipes": "/shortcuts",
            "payloady shortcuts": "/shortcuts",
            "pokaż skróty": "/shortcuts",
            "pokaż drafty": "/drafts",
            "draft gmail odpowiedz klientowi": "/connector",
            "anuluj task-1": "/cancel",
            "status task-1": "/status",
            "postęp task-1": "/progress",
            "progress task-1": "/progress",
            "szczegóły task-1": "/details",
            "fakty task-1": "/facts",
            "next task-1": "/next",
            "pokaż kolejkę": "/queue",
            "zapamiętaj cel = test": "/memory",
            "wyszukaj w pamięci test": "/memory",
            "pamięć projektu": "/project-memory",
            "szukaj w pamięci projektu Poke": "/project-memory",
            "zapisz plik shared/a.txt = hello": "/write",
            "dopisz do pliku shared/a.txt = hello": "/append",
            "zmień w pliku shared/a.txt :: hello => cześć": "/patch",
            "zatwierdź act-1": "/approve",
            "uruchom flow sprawdź system": "/flow",
            "uruchom council sprawdź plan": "/council",
            "zrób plan rozwoju systemu": "/flow",
            "zrób research o Poke": "@research",
            "co możesz?": "/capabilities",
            "jak dziś działasz?": "/capabilities",
            "gdzie ten cel i czemu nie odpowiada jak Poke": "/poke-gap",
            "Ani nie odpowiada on jak poke nie ma takich możliwości, o co chodzi gdzie ten cel ?": "/poke-gap",
            "poke parity": "/poke-gap",
        }

        for text, command in cases.items():
            with self.subTest(text=text):
                self.assertEqual(ai_council.route_text(text)["command"], command)

        self.assertEqual(ai_council.route_text("normalne pytanie do codexa")["command"], "/chat")

    def test_reminder_intent_creates_calendar_draft_not_chat(self):
        with temp_dir() as tmp:
            root = Path(tmp)
            with patch.object(ai_council, "TASKS_FILE", root / "state" / "tasks.jsonl"), patch.object(
                ai_council, "ACTIONS_FILE", root / "state" / "actions.jsonl"
            ), patch.object(ai_council, "LOG_DIR", root / "logs"), patch.object(
                ai_council, "AUDIT_LOG", root / "logs" / "audit.jsonl"
            ), patch.object(ai_council, "WORKSPACES_DIR", root / "workspaces"), patch.object(
                ai_council, "ARTIFACTS_DIR", root / "artifacts"
            ), patch.object(ai_council, "REPORTS_DIR", root / "reports"), patch.object(
                ai_council, "ERRORS_DIR", root / "errors"
            ), patch.object(ai_council, "RECIPES_DIR", root / "recipes"), patch.object(
                ai_council, "BACKGROUND_JOB_SPECS_DIR", root / "state" / "background_job_specs"
            ):
                response = ai_council.build_response(
                    ai_council.route_text("hej, czy możesz mi jutro przypomnieć o spotkaniu z Tomkiem?"),
                    chat_id="553",
                )
                action = ai_council.latest_by_id(root / "state" / "actions.jsonl", "action_id", limit=1)[0]

        self.assertIn("Pending action utworzona", response)
        self.assertIn("RYZYKO: R3", response)
        self.assertEqual(action["type"], "integration_draft")
        self.assertEqual(action["risk"], "R3")
        self.assertEqual(action["payload"]["connector"], "calendar")
        self.assertFalse(action["payload"]["external_write"])

    def test_reminder_without_meeting_word_still_creates_calendar_draft(self):
        with temp_dir() as tmp:
            root = Path(tmp)
            with patch.object(ai_council, "TASKS_FILE", root / "state" / "tasks.jsonl"), patch.object(
                ai_council, "ACTIONS_FILE", root / "state" / "actions.jsonl"
            ), patch.object(ai_council, "LOG_DIR", root / "logs"), patch.object(
                ai_council, "AUDIT_LOG", root / "logs" / "audit.jsonl"
            ), patch.object(ai_council, "WORKSPACES_DIR", root / "workspaces"), patch.object(
                ai_council, "ARTIFACTS_DIR", root / "artifacts"
            ), patch.object(ai_council, "REPORTS_DIR", root / "reports"), patch.object(
                ai_council, "ERRORS_DIR", root / "errors"
            ), patch.object(ai_council, "RECIPES_DIR", root / "recipes"), patch.object(
                ai_council, "BACKGROUND_JOB_SPECS_DIR", root / "state" / "background_job_specs"
            ):
                response = ai_council.build_response(ai_council.route_text("przypomnij mi jutro o lekach"), chat_id="553")
                action = ai_council.latest_by_id(root / "state" / "actions.jsonl", "action_id", limit=1)[0]

        self.assertIn("integration draft `calendar`", response)
        self.assertEqual(action["payload"]["connector"], "calendar")

    def test_calendar_nouns_do_not_inflate_risk_without_action_intent(self):
        risk, reason = ai_council.risk_level_for_text("spotkanie poszło dobrze i wydarzenie było ciekawe")

        self.assertEqual(risk, "R0")
        self.assertIn("read-only", reason)

    def test_common_event_words_do_not_force_calendar_connector(self):
        self.assertEqual(ai_council.integration_connector_for_intent("send me a reminder summary"), "")
        self.assertEqual(ai_council.integration_connector_for_intent("fajne wydarzenie wczoraj"), "")

    def test_action_planner_autostart_connector_is_subcommand_scoped(self):
        safe, safe_reason = ai_council.action_planner_can_autostart(
            {"approval_required": False, "risk": "R0", "command": "/connector", "prompt": "brief gmail Poke"}
        )
        blocked, blocked_reason = ai_council.action_planner_can_autostart(
            {"approval_required": False, "risk": "R0", "command": "/connector", "prompt": "draft gmail send mail"}
        )
        empty, empty_reason = ai_council.action_planner_can_autostart(
            {"approval_required": False, "risk": "R0", "command": "/connector", "prompt": ""}
        )

        self.assertTrue(safe, safe_reason)
        self.assertFalse(blocked)
        self.assertIn("not auto-start safe", blocked_reason)
        self.assertFalse(empty)
        self.assertIn("(empty)", empty_reason)

    def test_action_planner_autostart_env_gate_can_disable_safe_start(self):
        with patch.object(ai_council, "cfg", side_effect=lambda key, default="": "false" if key == "AI_COUNCIL_ACTION_PLANNER_AUTOSTART_SAFE" else default):
            allowed, reason = ai_council.action_planner_can_autostart(
                {"approval_required": False, "risk": "R0", "command": "/recipe", "prompt": "run research_brief Poke"}
            )

        self.assertFalse(allowed)
        self.assertIn("disabled", reason)

    def test_natural_connector_sync_builds_connector_prompt(self):
        route = ai_council.route_text("sync google drive Poke recipes")
        benign = ai_council.route_text("musisz sync gmail recipes z firmą")

        self.assertEqual(route["command"], "/connector")
        self.assertEqual(route["mode"], "connector_sync")
        self.assertEqual(route["prompt"], "sync drive Poke recipes")
        self.assertEqual(benign["command"], "/chat")

    def test_action_planner_auto_starts_safe_research_recipe(self):
        with temp_dir() as tmp:
            root = Path(tmp)
            with patch.object(ai_council, "TASKS_FILE", root / "state" / "tasks.jsonl"), patch.object(
                ai_council, "ACTIONS_FILE", root / "state" / "actions.jsonl"
            ), patch.object(ai_council, "LOG_DIR", root / "logs"), patch.object(
                ai_council, "AUDIT_LOG", root / "logs" / "audit.jsonl"
            ), patch.object(ai_council, "WORKSPACES_DIR", root / "workspaces"), patch.object(
                ai_council, "ARTIFACTS_DIR", root / "artifacts"
            ), patch.object(ai_council, "REPORTS_DIR", root / "reports"), patch.object(
                ai_council, "ERRORS_DIR", root / "errors"
            ), patch.object(ai_council, "RECIPES_DIR", root / "recipes"), patch.object(
                ai_council, "BACKGROUND_JOB_SPECS_DIR", root / "state" / "background_job_specs"
            ), patch.object(
                ai_council, "start_background_job", return_value="[AI Council] started safe recipe"
            ):
                response = ai_council.action_planner_response("ogarnij mi research Poke funkcje", chat_id="553")
                tasks = ai_council.latest_tasks(limit=1)
                actions = ai_council.read_jsonl(root / "state" / "actions.jsonl")

        self.assertIn("Action Planner L4.16", response)
        self.assertIn("TRYB: recipe", response)
        self.assertIn("live_recipe: research_brief", response)
        self.assertIn("AUTO-START: tak", response)
        self.assertIn("started safe recipe", response)
        self.assertEqual(tasks[0]["status"], "running")
        self.assertEqual(tasks[0]["planner_mode"], "recipe")
        self.assertEqual(tasks[0]["recommended_command"], "/recipe")
        self.assertEqual(tasks[0]["recommended_recipe"], "research_brief")
        self.assertIn("run research_brief", tasks[0]["recommended_prompt"])
        self.assertEqual(actions, [])

    def test_action_planner_side_effect_creates_integration_draft(self):
        with temp_dir() as tmp:
            root = Path(tmp)
            with patch.object(ai_council, "TASKS_FILE", root / "state" / "tasks.jsonl"), patch.object(
                ai_council, "ACTIONS_FILE", root / "state" / "actions.jsonl"
            ), patch.object(ai_council, "LOG_DIR", root / "logs"), patch.object(
                ai_council, "AUDIT_LOG", root / "logs" / "audit.jsonl"
            ), patch.object(ai_council, "WORKSPACES_DIR", root / "workspaces"), patch.object(
                ai_council, "ARTIFACTS_DIR", root / "artifacts"
            ), patch.object(ai_council, "REPORTS_DIR", root / "reports"), patch.object(
                ai_council, "ERRORS_DIR", root / "errors"
            ), patch.object(ai_council, "RECIPES_DIR", root / "recipes"), patch.object(
                ai_council, "BACKGROUND_JOB_SPECS_DIR", root / "state" / "background_job_specs"
            ):
                response = ai_council.action_planner_response("wyślij maila do klienta z ofertą", chat_id="553")
                actions = ai_council.latest_by_id(root / "state" / "actions.jsonl", "action_id", limit=1)
                markup = ai_council.response_reply_markup(response)

        self.assertIn("Pending action utworzona", response)
        self.assertEqual(actions[0]["status"], "pending")
        self.assertEqual(actions[0]["type"], "integration_draft")
        self.assertEqual(actions[0]["risk"], "R4")
        self.assertEqual(actions[0]["payload"]["connector"], "gmail")
        self.assertEqual(actions[0]["payload"]["draft_kind"], "email_draft")
        self.assertFalse(actions[0]["payload"]["external_write"])
        self.assertIn("task_id", actions[0]["payload"])
        callback_data = [button["callback_data"] for row in markup["inline_keyboard"] for button in row]
        self.assertIn(f"approve:{actions[0]['action_id']}", callback_data)
        self.assertIn(f"edit:{actions[0]['action_id']}", callback_data)

    def test_action_planner_read_only_connector_uses_live_recipe_without_approval(self):
        with temp_dir() as tmp:
            root = Path(tmp)
            with patch.object(ai_council, "TASKS_FILE", root / "state" / "tasks.jsonl"), patch.object(
                ai_council, "ACTIONS_FILE", root / "state" / "actions.jsonl"
            ), patch.object(ai_council, "LOG_DIR", root / "logs"), patch.object(
                ai_council, "AUDIT_LOG", root / "logs" / "audit.jsonl"
            ), patch.object(ai_council, "WORKSPACES_DIR", root / "workspaces"), patch.object(
                ai_council, "ARTIFACTS_DIR", root / "artifacts"
            ), patch.object(ai_council, "REPORTS_DIR", root / "reports"), patch.object(
                ai_council, "ERRORS_DIR", root / "errors"
            ), patch.object(ai_council, "RECIPES_DIR", root / "recipes"), patch.object(
                ai_council, "BACKGROUND_JOB_SPECS_DIR", root / "state" / "background_job_specs"
            ), patch.object(
                ai_council, "start_background_job", return_value="[AI Council] started gmail brief"
            ):
                response = ai_council.action_planner_response("przygotuj mi raport z gmail o Poke", chat_id="553")
                actions = ai_council.read_jsonl(root / "state" / "actions.jsonl")
                task = ai_council.latest_tasks(limit=1)[0]

        self.assertIn("TRYB: recipe", response)
        self.assertIn("live_recipe: gmail_context_brief", response)
        self.assertIn("AUTO-START: tak", response)
        self.assertNotIn("Pending action", response)
        self.assertEqual(actions, [])
        self.assertEqual(task["recommended_command"], "/recipe")
        self.assertEqual(task["recommended_recipe"], "gmail_context_brief")
        self.assertIn("run gmail_context_brief", task["recommended_prompt"])

    def test_action_planner_does_not_overclassify_send_me_link_as_r4(self):
        plan = ai_council.action_planner_mode("wyślij mi link do dokumentu")

        self.assertEqual(plan["risk"], "R0")
        self.assertFalse(plan["approval_required"])

    def test_action_planner_r3_schedule_meeting_requires_approval(self):
        plan = ai_council.action_planner_mode("schedule meeting with customer tomorrow")

        self.assertEqual(plan["risk"], "R3")
        self.assertEqual(plan["mode"], "approval")
        self.assertTrue(plan["approval_required"])

    def test_risk_auth_docs_is_not_broad_auth_approval(self):
        risk, _ = ai_council.risk_level_for_text("sprawdź dokumentację auth")

        self.assertEqual(risk, "R0")

    def test_live_recipe_selector_prefers_source_recipe(self):
        with temp_dir() as tmp:
            root = Path(tmp)
            with patch.object(ai_council, "RECIPES_DIR", root / "recipes"):
                selected = ai_council.select_live_recipe("przygotuj mi raport z gmail o Poke")
                suggestions = ai_council.recipe_suggest_response("przygotuj mi raport z gmail o Poke")

        self.assertEqual(selected["name"], "gmail_context_brief")
        self.assertIn("gmail_context_brief", suggestions)
        self.assertIn("/recipe run gmail_context_brief", suggestions)

    def test_loops_response_shows_autonomous_loops(self):
        with temp_dir() as tmp:
            root = Path(tmp)
            with patch.object(ai_council, "RECIPES_DIR", root / "recipes"), patch.object(
                ai_council, "RECIPE_RUNS_FILE", root / "state" / "recipe_runs.jsonl"
            ), patch.object(ai_council, "ERRORS_FILE", root / "state" / "errors.jsonl"), patch.object(
                ai_council, "IMPROVEMENTS_FILE", root / "state" / "improvements.jsonl"
            ), patch.object(ai_council, "LOG_DIR", root / "logs"), patch.object(
                ai_council, "AUDIT_LOG", root / "logs" / "audit.jsonl"
            ), patch.object(ai_council, "WORKSPACES_DIR", root / "workspaces"), patch.object(
                ai_council, "ARTIFACTS_DIR", root / "artifacts"
            ), patch.object(ai_council, "REPORTS_DIR", root / "reports"), patch.object(
                ai_council, "ERRORS_DIR", root / "errors"
            ), patch.object(ai_council, "BACKGROUND_JOB_SPECS_DIR", root / "state" / "background_job_specs"):
                ai_council.append_recipe_run("error_audit_twice_daily", "cron:test", "task-loop", "started")
                response = ai_council.loops_response()

        self.assertIn(f"Autonomous loops {ai_council.AUTONOMOUS_LOOP_VERSION}", response)
        self.assertIn("error_audit_twice_daily", response)
        self.assertIn("feature_evolution_loop", response)
        self.assertIn("cadence=twice_daily", response)
        self.assertIn("next=", response)
        self.assertIn("task-loop", response)

    def test_approve_planner_proposal_reports_checkpoint_next_step(self):
        with temp_dir() as tmp:
            root = Path(tmp)
            with patch.object(ai_council, "TASKS_FILE", root / "state" / "tasks.jsonl"), patch.object(
                ai_council, "ACTIONS_FILE", root / "state" / "actions.jsonl"
            ), patch.object(ai_council, "LOG_DIR", root / "logs"), patch.object(
                ai_council, "AUDIT_LOG", root / "logs" / "audit.jsonl"
            ), patch.object(ai_council, "WORKSPACES_DIR", root / "workspaces"), patch.object(
                ai_council, "ARTIFACTS_DIR", root / "artifacts"
            ), patch.object(ai_council, "REPORTS_DIR", root / "reports"), patch.object(
                ai_council, "ERRORS_DIR", root / "errors"
            ), patch.object(ai_council, "RECIPES_DIR", root / "recipes"), patch.object(
                ai_council, "BACKGROUND_JOB_SPECS_DIR", root / "state" / "background_job_specs"
            ):
                planner = ai_council.action_planner_response("opublikuj wpis na stronie", chat_id="553")
                action_id = re.search(r"id: (act-[A-Za-z0-9_.-]+)", planner).group(1)
                approved = ai_council.approve_response(action_id)
                action = ai_council.get_latest_action(action_id)

        self.assertEqual(action["status"], "approved")
        self.assertIn("Approved planner checkpoint", approved)
        self.assertIn("Nie wykonałem external write", approved)
        self.assertIn("Next: status task-", approved)
        self.assertEqual(action["type"], "planner_proposal")

    def test_approve_followup_starts_safe_background_route(self):
        with temp_dir() as tmp:
            root = Path(tmp)
            with patch.object(ai_council, "TASKS_FILE", root / "state" / "tasks.jsonl"), patch.object(
                ai_council, "ACTIONS_FILE", root / "state" / "actions.jsonl"
            ), patch.object(ai_council, "LOG_DIR", root / "logs"), patch.object(
                ai_council, "AUDIT_LOG", root / "logs" / "audit.jsonl"
            ), patch.object(ai_council, "WORKSPACES_DIR", root / "workspaces"), patch.object(
                ai_council, "ARTIFACTS_DIR", root / "artifacts"
            ), patch.object(ai_council, "REPORTS_DIR", root / "reports"), patch.object(
                ai_council, "ERRORS_DIR", root / "errors"
            ), patch.object(ai_council, "BACKGROUND_JOB_SPECS_DIR", root / "state" / "background_job_specs"), patch.object(
                ai_council, "start_background_job", return_value="[AI Council] follow-up started"
            ) as start:
                action = ai_council.create_action(
                    "Follow-up for task-test: plan improvement",
                    action_type="followup_proposal",
                    risk="R0",
                    payload={
                        "source_task_id": "task-test",
                        "intent": "plan improvement",
                        "recommended_command": "/improve",
                        "recommended_prompt": "apply imp-1",
                    },
                )
                response = ai_council.approve_response(action["action_id"])
                second_response = ai_council.approve_response(action["action_id"])
                latest = ai_council.get_latest_action(action["action_id"])
                tasks = ai_council.latest_tasks(limit=1)

        self.assertIn("follow-up started", response)
        self.assertIn("status `executed`", second_response)
        self.assertEqual(latest["status"], "executed")
        self.assertEqual(latest["payload"]["launched_task_id"], tasks[0]["task_id"])
        start.assert_called_once()
        self.assertEqual(start.call_args.kwargs["task_id"], tasks[0]["task_id"])

    def test_approve_followup_r4_does_not_auto_execute(self):
        with temp_dir() as tmp:
            root = Path(tmp)
            with patch.object(ai_council, "ACTIONS_FILE", root / "state" / "actions.jsonl"), patch.object(
                ai_council, "LOG_DIR", root / "logs"
            ), patch.object(ai_council, "AUDIT_LOG", root / "logs" / "audit.jsonl"), patch.object(
                ai_council, "start_background_job", return_value="should not start"
            ) as start, patch.object(ai_council, "build_response", return_value="should not execute") as build:
                action = ai_council.create_action(
                    "Follow-up for task-test: wyślij maila do klienta",
                    action_type="followup_proposal",
                    risk="R4",
                    payload={
                        "source_task_id": "task-test",
                        "intent": "wyślij maila do klienta",
                        "recommended_command": "/plan-action",
                        "recommended_prompt": "wyślij maila do klienta",
                    },
                )
                response = ai_council.approve_response(action["action_id"])
                latest = ai_council.get_latest_action(action["action_id"])

        self.assertIn("checkpoint", response)
        self.assertEqual(latest["status"], "approved")
        self.assertEqual(start.call_count, 0)
        self.assertEqual(build.call_count, 0)

    def test_approve_followup_recomputes_risk_from_route(self):
        with temp_dir() as tmp:
            root = Path(tmp)
            with patch.object(ai_council, "ACTIONS_FILE", root / "state" / "actions.jsonl"), patch.object(
                ai_council, "LOG_DIR", root / "logs"
            ), patch.object(ai_council, "AUDIT_LOG", root / "logs" / "audit.jsonl"), patch.object(
                ai_council, "start_background_job", return_value="should not start"
            ) as start, patch.object(ai_council, "build_response", return_value="should not execute") as build:
                action = ai_council.create_action(
                    "Follow-up for task-test: declared low risk mail",
                    action_type="followup_proposal",
                    risk="R0",
                    payload={
                        "source_task_id": "task-test",
                        "intent": "wyślij maila do klienta",
                        "recommended_command": "/plan-action",
                        "recommended_prompt": "wyślij maila do klienta",
                    },
                )
                response = ai_council.approve_response(action["action_id"])
                latest = ai_council.get_latest_action(action["action_id"])

        self.assertIn("checkpoint", response)
        self.assertIn("risk: R4", response)
        self.assertEqual(latest["status"], "approved")
        self.assertEqual(start.call_count, 0)
        self.assertEqual(build.call_count, 0)

    def test_edit_callback_marks_pending_action_as_editing(self):
        with temp_dir() as tmp:
            root = Path(tmp)
            with patch.object(ai_council, "ACTIONS_FILE", root / "state" / "actions.jsonl"), patch.object(
                ai_council, "LOG_DIR", root / "logs"
            ), patch.object(ai_council, "AUDIT_LOG", root / "logs" / "audit.jsonl"):
                action = ai_council.create_action("Planner proposal: test", action_type="planner_proposal", risk="R4")
                response, status = ai_council.handle_callback_query({"data": f"edit:{action['action_id']}"})
                edited = ai_council.get_latest_action(action["action_id"])

        self.assertEqual(status, "edit")
        self.assertEqual(edited["status"], "editing")
        self.assertIn("stara akcja", response)

    def test_start_planned_task_uses_recommended_background_route(self):
        with temp_dir() as tmp:
            root = Path(tmp)
            with patch.object(ai_council, "TASKS_FILE", root / "state" / "tasks.jsonl"), patch.object(
                ai_council, "ACTIONS_FILE", root / "state" / "actions.jsonl"
            ), patch.object(ai_council, "LOG_DIR", root / "logs"), patch.object(
                ai_council, "AUDIT_LOG", root / "logs" / "audit.jsonl"
            ), patch.object(ai_council, "WORKSPACES_DIR", root / "workspaces"), patch.object(
                ai_council, "ARTIFACTS_DIR", root / "artifacts"
            ), patch.object(ai_council, "REPORTS_DIR", root / "reports"), patch.object(
                ai_council, "ERRORS_DIR", root / "errors"
            ), patch.object(ai_council, "RECIPES_DIR", root / "recipes"), patch.object(
                ai_council, "BACKGROUND_JOB_SPECS_DIR", root / "state" / "background_job_specs"
            ), patch.object(ai_council, "start_background_job", return_value="[AI Council] task-started") as start:
                planner = ai_council.action_planner_response("ogarnij mi research Poke funkcje", chat_id="553", auto_start=False)
                task_id = re.search(r"task_id: (task-[A-Za-z0-9_.-]+)", planner).group(1)
                response = ai_council.start_planned_task_response(task_id, chat_id="553")
                latest = ai_council.get_latest_task(task_id)

        self.assertIn("task-started", response)
        self.assertEqual(latest["status"], "running")
        start.assert_called_once()
        self.assertEqual(start.call_args.kwargs["task_id"], task_id)

    def test_start_planned_task_foreground_error_marks_failed(self):
        with temp_dir() as tmp:
            root = Path(tmp)
            with patch.object(ai_council, "TASKS_FILE", root / "state" / "tasks.jsonl"), patch.object(
                ai_council, "ACTIONS_FILE", root / "state" / "actions.jsonl"
            ), patch.object(ai_council, "LOG_DIR", root / "logs"), patch.object(
                ai_council, "AUDIT_LOG", root / "logs" / "audit.jsonl"
            ), patch.object(ai_council, "WORKSPACES_DIR", root / "workspaces"), patch.object(
                ai_council, "ARTIFACTS_DIR", root / "artifacts"
            ), patch.object(ai_council, "REPORTS_DIR", root / "reports"), patch.object(
                ai_council, "ERRORS_DIR", root / "errors"
            ), patch.object(ai_council, "RECIPES_DIR", root / "recipes"), patch.object(
                ai_council, "BACKGROUND_JOB_SPECS_DIR", root / "state" / "background_job_specs"
            ), patch.object(ai_council, "build_response", return_value="[Council] Error: connector failed"):
                task = ai_council.create_planned_task(
                    "przygotuj mi raport z gmail",
                    {
                        "mode": "connector",
                        "command": "/connector",
                        "prompt": "brief gmail Poke",
                        "risk": "R0",
                        "risk_reason": "read-only test",
                        "decision": "test",
                        "approval_required": False,
                    },
                )
                response = ai_council.start_planned_task_response(task["task_id"], chat_id="553")
                latest = ai_council.get_latest_task(task["task_id"])

        self.assertIn("connector failed", response)
        self.assertEqual(latest["status"], "failed")

    def test_multiline_command_block_routes_line_by_line(self):
        route = ai_council.route_text("status\n@claude-flow test\n/flow plan")

        self.assertEqual(route["command"], "/multi")
        self.assertEqual(route["operators"], ["host", "claude-flow"])
        self.assertEqual([child["command"] for child in route["routes"]], ["/status", "@claude-flow", "/flow"])

    def test_multiline_command_block_builds_each_response(self):
        route = ai_council.route_text("status\n@claude-flow test")

        with patch.object(ai_council, "claude_flow_response", return_value="[Claude Flow]\nok"):
            response = ai_council.build_response(route)

        self.assertIn("1/2: /status", response)
        self.assertIn("2/2: @claude-flow", response)
        self.assertIn("Plan workflow gotowy", response)
        self.assertIn("ok", response)
        self.assertNotIn("[Claude Flow]", response)

    def test_llm_route_parses_strict_json_and_selects_research(self):
        def fake_cfg(key, default=""):
            if key == "XAI_API_KEY":
                return "xai-test"
            if key == "AI_COUNCIL_LLM_ROUTER":
                return "true"
            return default

        with patch.object(ai_council, "cfg", side_effect=fake_cfg), patch.object(
            ai_council, "reserve_operator_call", return_value=(True, "", {"id": "r1"})
        ), patch.object(ai_council, "finalize_operator_call", return_value=None), patch.object(
            ai_council, "request_json", return_value={"choices": [{"message": {"content": '{"command":"@research","prompt":"nowy Grok","confidence":0.91,"reason":"research"}'}}]}
        ):
            # route_message no longer calls llm_route (the brain owns free-text); test llm_route() directly.
            route = ai_council.llm_route("sprawdź proszę co ludzie piszą o nowym Groku", chat_id="553")

        self.assertEqual(route["command"], "@research")
        self.assertEqual(route["route_source"], "llm")
        self.assertGreaterEqual(route["confidence"], 0.9)

    def test_llm_route_rejects_side_effect_commands(self):
        def fake_cfg(key, default=""):
            if key == "XAI_API_KEY":
                return "xai-test"
            if key == "AI_COUNCIL_LLM_ROUTER":
                return "true"
            return default

        with patch.object(ai_council, "cfg", side_effect=fake_cfg), patch.object(
            ai_council, "reserve_operator_call", return_value=(True, "", {"id": "r1"})
        ), patch.object(ai_council, "finalize_operator_call", return_value=None), patch.object(
            ai_council, "request_json", return_value={"choices": [{"message": {"content": '{"command":"/execute","prompt":"act-1","confidence":0.99,"reason":"danger"}'}}]}
        ):
            route = ai_council.route_message("usuń wszystkie pliki", chat_id="553")

        self.assertEqual(route["command"], "/chat")
        self.assertEqual(route["route_source"], "fallback")

    def test_llm_route_low_confidence_falls_back_to_chat(self):
        def fake_cfg(key, default=""):
            if key == "XAI_API_KEY":
                return "xai-test"
            if key == "AI_COUNCIL_LLM_ROUTER":
                return "true"
            return default

        with patch.object(ai_council, "cfg", side_effect=fake_cfg), patch.object(
            ai_council, "reserve_operator_call", return_value=(True, "", {"id": "r1"})
        ), patch.object(ai_council, "finalize_operator_call", return_value=None), patch.object(
            ai_council, "request_json", return_value={"choices": [{"message": {"content": '{"command":"/flow","prompt":"x","confidence":0.2,"reason":"unclear"}'}}]}
        ):
            route = ai_council.route_message("może coś z tym zrób", chat_id="553")

        self.assertEqual(route["command"], "/chat")
        self.assertEqual(route["route_source"], "fallback")

    def test_llm_route_disabled_without_xai_key(self):
        with patch.object(ai_council, "cfg", return_value=""), patch.object(ai_council, "request_json") as request_json:
            route = ai_council.llm_route("sprawdź internet", chat_id="553")

        self.assertIsNone(route)
        request_json.assert_not_called()

    def test_llm_route_defaults_off_even_with_xai_key(self):
        def fake_cfg(key, default=""):
            if key == "XAI_API_KEY":
                return "xai-test"
            return default

        with patch.object(ai_council, "cfg", side_effect=fake_cfg), patch.object(ai_council, "request_json") as request_json:
            route = ai_council.llm_route("sprawdź internet", chat_id="553")

        self.assertIsNone(route)
        request_json.assert_not_called()

    def test_short_poke_chat_does_not_use_grok_llm(self):
        def fake_cfg(key, default=""):
            values = {
                "XAI_API_KEY": "xai-test",
                "AI_COUNCIL_POKE_CHAT_USE_GROK": "true",
            }
            return values.get(key, default)

        with patch.object(ai_council, "cfg", side_effect=fake_cfg), patch.object(ai_council, "request_json") as request_json:
            response = ai_council.poke_chat_response("Hej", chat_id="553")

        self.assertTrue(response.strip())
        self.assertNotIn("[Council]", response)
        request_json.assert_not_called()

    def test_poke_chat_llm_gate_allows_followups_and_long_value_prompts(self):
        def fake_cfg(key, default=""):
            values = {
                "XAI_API_KEY": "xai-test",
                "AI_COUNCIL_POKE_CHAT_USE_GROK": "true",
                "AI_COUNCIL_POKE_CHAT_LLM_MIN_CHARS": "90",
                "AI_COUNCIL_POKE_CHAT_OPERATOR": "grok",
            }
            return values.get(key, default)

        with patch.object(ai_council, "cfg", side_effect=fake_cfg):
            self.assertTrue(ai_council.poke_chat_should_use_llm("a teraz krócej"))
            self.assertTrue(
                ai_council.poke_chat_should_use_llm(
                    "Wyjaśnij mi proszę spokojnie i konkretnie jak mam dalej używać tego systemu w codziennej pracy."
                )
            )
            self.assertFalse(ai_council.poke_chat_should_use_llm("akceleracja projektu bez dodatkowego kontekstu"))

    def test_route_message_prefers_explicit_then_keyword_then_brain(self):
        # Order is now explicit -> keyword -> brain (/chat). llm_route is retired from
        # route_message so free-text never gets hijacked into a leaky operator command.
        explicit = ai_council.route_message("@codex ping", chat_id="553")
        keyword = ai_council.route_message("status", chat_id="553")
        natural = ai_council.route_message("sprawdź to szerzej", chat_id="553")

        self.assertEqual(explicit["command"], "@codex")
        self.assertEqual(explicit["route_source"], "explicit")
        self.assertEqual(keyword["command"], "/status")
        self.assertEqual(keyword["route_source"], "keyword")
        self.assertEqual(natural["command"], "/chat")
        self.assertEqual(natural["route_source"], "fallback")

    def test_novel_phrasing_goes_to_brain_not_leaky_operator(self):
        # Previously the LLM router classified this into @research (an operator command that
        # leaked plan-mode/[Council]). Now route_message hands novel free-text to the brain
        # (/chat -> brain_loop), which itself decides whether to answer or research — cleanly.
        with patch.object(ai_council, "request_json") as request_json:
            route = ai_council.route_message("ciekawi mnie co inni sądzą o tym nowym modelu", chat_id="553")
        request_json.assert_not_called()
        self.assertEqual(route["command"], "/chat")
        self.assertEqual(route["route_source"], "fallback")

    def test_llm_router_skips_smalltalk_without_grok_call(self):
        def fake_cfg(key, default=""):
            values = {"XAI_API_KEY": "xai-test", "AI_COUNCIL_LLM_ROUTER": "true"}
            return values.get(key, default)

        with patch.object(ai_council, "cfg", side_effect=fake_cfg), patch.object(
            ai_council, "request_json"
        ) as request_json:
            for message in ("hej", "dzięki", "ok spoko"):
                route = ai_council.route_message(message, chat_id="553")
                self.assertEqual(route["command"], "/chat")

        request_json.assert_not_called()

    def test_is_smalltalk_detects_greetings_but_not_intents(self):
        self.assertTrue(ai_council.is_smalltalk("hej"))
        self.assertTrue(ai_council.is_smalltalk("Dzięki!"))
        self.assertTrue(ai_council.is_smalltalk("ok spoko"))
        self.assertFalse(ai_council.is_smalltalk("zrób research o Poke"))
        self.assertFalse(ai_council.is_smalltalk("ciekawi mnie opinia o modelu"))
        self.assertFalse(ai_council.is_smalltalk(""))

    def test_risk_fence_classifies_destructive_phrases(self):
        # L4.64: these were under-gated before (e.g. "pay the invoice" -> R0).
        for phrase in [
            "pay the invoice",
            "remove all files",
            "wipe the disk",
            "deploy to prod",
            "transfer money to account",
            "send email to the client",
            "wyślij maila do klienta",
            "przelej 1000 zł",
            "zapłać fakturę",
        ]:
            level, _ = ai_council.risk_level_for_text(phrase)
            self.assertIn(level, ("R3", "R4"), f"{phrase!r} must be gated, got {level}")

    def test_risk_fence_keeps_benign_phrases_read_only(self):
        for phrase in ["co słychać", "zrób research o Poke", "jaka jest pogoda", "opowiedz mi o nowym modelu"]:
            level, _ = ai_council.risk_level_for_text(phrase)
            self.assertEqual(level, "R0", f"{phrase!r} must stay R0, got {level}")

    def test_llm_router_fence_blocks_destructive_prompt_to_chat(self):
        # The router can pick an allowlisted command, but a destructive prompt
        # riding it must fall back to /chat, never auto-start a task.
        def fake_cfg(key, default=""):
            values = {"XAI_API_KEY": "xai-test", "AI_COUNCIL_LLM_ROUTER": "true"}
            return values.get(key, default)

        with patch.object(ai_council, "cfg", side_effect=fake_cfg), patch.object(
            ai_council, "reserve_operator_call", return_value=(True, "", {"id": "r1"})
        ), patch.object(ai_council, "finalize_operator_call", return_value=None), patch.object(
            ai_council,
            "request_json",
            return_value={"choices": [{"message": {"content": '{"command":"@research","prompt":"pay the invoice","confidence":0.95,"reason":"x"}'}}]},
        ):
            # Benign-looking message reaches the LLM router; the router returns a
            # destructive prompt. The fence must catch it and fall back to /chat.
            route = ai_council.route_message("ciekawi mnie co inni sądzą o tym nowym modelu", chat_id="553")

        self.assertEqual(route["command"], "/chat")
        self.assertEqual(route["route_source"], "fallback")



if __name__ == "__main__":
    unittest.main()
