import base64
import json
import os
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import ai_council


def temp_dir():
    try:
        return tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
    except TypeError:
        return tempfile.TemporaryDirectory()


class OperatorOutputTests(unittest.TestCase):
    def test_single_instance_lock_blocks_second_listener(self):
        with temp_dir() as tmp:
            lock_path = Path(tmp) / "state" / "telegram_listener.lock"
            first = ai_council.SingleInstanceLock(lock_path)
            second = ai_council.SingleInstanceLock(lock_path)

            self.assertTrue(first.acquire())
            self.assertFalse(second.acquire())
            first.release()
            self.assertTrue(second.acquire())
            second.release()

    def test_clean_operator_output_removes_windows_process_noise_only(self):
        raw = (
            "SUCCESS: The process with PID 1234 has been terminated.\n"
            "INFO: The process with PID 2222 is still running.\n"
            "ERROR: The process with PID 3333 could not be terminated.\n"
            "Normal ERROR: zachowaj ten błąd\n"
            "Polskie znaki: ąęśćżół\n"
        )

        cleaned = ai_council.clean_operator_output(raw)

        self.assertNotIn("SUCCESS: The process with PID", cleaned)
        self.assertNotIn("INFO: The process with PID", cleaned)
        self.assertNotIn("ERROR: The process with PID 3333", cleaned)
        self.assertIn("Normal ERROR: zachowaj ten błąd", cleaned)
        self.assertIn("Polskie znaki: ąęśćżół", cleaned)

    def test_codex_operator_is_read_only_utf8_and_runs_from_project_dir(self):
        completed = subprocess.CompletedProcess(args=["codex"], returncode=0, stdout="działam ąęśćżół", stderr="")

        with patch.object(ai_council, "command_path", return_value="codex") as command_path, patch(
            "ai_council.subprocess.run", return_value=completed
        ) as run:
            response = ai_council.codex_response("sprawdź status")

        command_path.assert_called_with("CODEX_BIN", "codex", ai_council.DEFAULT_CODEX_BIN)
        args, kwargs = run.call_args
        self.assertEqual(args[0][:5], ["codex", "exec", "--skip-git-repo-check", "--sandbox", "read-only"])
        self.assertIn("sprawdź status", args[0][-1])
        self.assertEqual(kwargs["cwd"], str(ai_council.PROJECT_DIR))
        self.assertEqual(kwargs["timeout"], 120)
        self.assertEqual(kwargs["input"], "")
        self.assertEqual(kwargs["encoding"], "utf-8")
        self.assertEqual(kwargs["errors"], "replace")
        self.assertEqual(kwargs["env"]["PYTHONUTF8"], "1")
        self.assertEqual(kwargs["env"]["PYTHONIOENCODING"], "utf-8")
        self.assertIn("działam ąęśćżół", response)

    def test_codex_unavailable_message_is_clear(self):
        with patch.object(ai_council, "command_path", return_value="codex"), patch(
            "ai_council.subprocess.run", side_effect=FileNotFoundError()
        ):
            response = ai_council.codex_response("ping")

        self.assertTrue(response.startswith("[Codex] unavailable:"))

    def test_codex_operator_prompt_includes_memory_auto_recall(self):
        completed = subprocess.CompletedProcess(args=["codex"], returncode=0, stdout="OK", stderr="")

        with patch.object(ai_council, "command_path", return_value="codex"), patch.object(
            ai_council, "memory_context_for_prompt", return_value="- host | cel: ważny kontekst"
        ), patch("ai_council.subprocess.run", return_value=completed) as run:
            response = ai_council.codex_response("co dalej")

        args, _ = run.call_args
        self.assertIn("OK", response)
        self.assertIn("Kontekst z pamięci AI Council", args[0][-1])
        self.assertIn("ważny kontekst", args[0][-1])

    def test_route_poke_research_to_background_grok_x_search(self):
        route = ai_council.route_text("/poke-research sklonuj funkcje Poke")

        self.assertEqual(route["command"], "/poke-research")
        self.assertEqual(route["operators"], ["grok"])
        self.assertEqual(route["mode"], "poke_research")
        self.assertTrue(ai_council.route_needs_task(route))
        self.assertTrue(ai_council.route_should_background(route))

    def test_xresearch_natural_intent_routes_to_grok(self):
        route = ai_council.route_text("deep research x Poke Apple Messages")

        self.assertEqual(route["command"], "/xresearch")
        self.assertEqual(route["operators"], ["grok"])
        self.assertEqual(route["mode"], "xresearch")

    def test_selftest_routes_from_command_and_natural_intent(self):
        direct = ai_council.route_text("/selftest")
        natural = ai_council.route_text("sprawdź wszystko")

        self.assertEqual(direct["command"], "/selftest")
        self.assertEqual(natural["command"], "/selftest")
        self.assertEqual(natural["mode"], "selftest")

    def test_xai_response_text_extracts_nested_output_text(self):
        data = {
            "output": [
                {
                    "type": "message",
                    "content": [
                        {"type": "output_text", "text": "Pierwszy fakt."},
                        {"type": "output_text", "text": "Drugi fakt."},
                    ],
                }
            ]
        }

        self.assertEqual(ai_council.xai_response_text(data), "Pierwszy fakt.\nDrugi fakt.")

    def test_response_reply_markup_for_pending_action(self):
        markup = ai_council.response_reply_markup("[Council] Pending action utworzona.\nid: act-20260606-120000-abcdef")

        self.assertEqual(markup["inline_keyboard"][0][0]["callback_data"], "approve:act-20260606-120000-abcdef")
        self.assertEqual(markup["inline_keyboard"][0][1]["callback_data"], "deny:act-20260606-120000-abcdef")

    def test_response_reply_markup_for_task(self):
        markup = ai_council.response_reply_markup("[AI Council] task-20260606-120000-abcdef\nSTART")

        self.assertEqual(markup["inline_keyboard"][0][0]["callback_data"], "status:task-20260606-120000-abcdef")
        self.assertEqual(markup["inline_keyboard"][1][0]["callback_data"], "cancel:task-20260606-120000-abcdef")

    def test_response_reply_markup_for_completed_task_uses_delivery_card(self):
        markup = ai_council.response_reply_markup(
            "[AI Council] task-20260606-120000-abcdef\nDECYZJA: gotowe\nDetails: /details task-20260606-120000-abcdef"
        )
        callback_data = [
            button["callback_data"]
            for row in markup["inline_keyboard"]
            for button in row
        ]

        self.assertIn("facts:task-20260606-120000-abcdef", callback_data)
        self.assertIn("next:task-20260606-120000-abcdef", callback_data)
        self.assertNotIn("cancel:task-20260606-120000-abcdef", callback_data)

    def test_task_delivery_reply_markup_has_artifact_buttons_without_cancel(self):
        markup = ai_council.task_delivery_reply_markup("task-20260606-120000-abcdef")
        callback_data = [
            button["callback_data"]
            for row in markup["inline_keyboard"]
            for button in row
        ]

        self.assertIn("details:task-20260606-120000-abcdef", callback_data)
        self.assertIn("facts:task-20260606-120000-abcdef", callback_data)
        self.assertIn("next:task-20260606-120000-abcdef", callback_data)
        self.assertNotIn("cancel:task-20260606-120000-abcdef", callback_data)

    def test_callback_approve_routes_to_approve_response(self):
        with patch.object(ai_council, "approve_response", return_value="[Council] Approved: act-1") as approve:
            response, status = ai_council.handle_callback_query({"data": "approve:act-1"})

        approve.assert_called_once_with("act-1")
        self.assertEqual(status, "approved")
        self.assertIn("Approved", response)

    def test_callback_facts_and_next_route_to_artifact_responses(self):
        with patch.object(ai_council, "facts_response", return_value="[Council] Facts task-1") as facts, patch.object(
            ai_council, "next_response", return_value="[Council] Next task-1"
        ) as next_response:
            facts_text, facts_status = ai_council.handle_callback_query({"data": "facts:task-1"})
            next_text, next_status = ai_council.handle_callback_query({"data": "next:task-1"})

        facts.assert_called_once_with("task-1")
        next_response.assert_called_once_with("task-1")
        self.assertEqual(facts_status, "facts")
        self.assertEqual(next_status, "next")
        self.assertIn("Facts", facts_text)
        self.assertIn("Next", next_text)

    def test_recipe_run_needs_background_task(self):
        route = ai_council.route_text("/recipe run daily_system_digest")

        self.assertEqual(route["command"], "/recipe")
        self.assertTrue(ai_council.route_needs_task(route))
        self.assertTrue(ai_council.route_should_background(route))

    def test_recipe_show_does_not_need_background_task(self):
        route = ai_council.route_text("/recipe show daily_system_digest")

        self.assertEqual(route["command"], "/recipe")
        self.assertFalse(ai_council.route_needs_task(route))
        self.assertFalse(ai_council.route_should_background(route))

    def test_recipe_enable_disable_updates_recipe_file(self):
        with temp_dir() as tmp:
            root = Path(tmp)
            with patch.object(ai_council, "RECIPES_DIR", root / "recipes"), patch.object(
                ai_council, "LOG_DIR", root / "logs"
            ), patch.object(ai_council, "AUDIT_LOG", root / "logs" / "audit.jsonl"):
                disabled = ai_council.recipe_response("disable research_brief")
                disabled_recipe = ai_council.load_recipe("research_brief")
                enabled = ai_council.recipe_response("enable research_brief")
                enabled_recipe = ai_council.load_recipe("research_brief")

        self.assertIn("disabled", disabled)
        self.assertFalse(disabled_recipe["enabled"])
        self.assertIn("enabled", enabled)
        self.assertTrue(enabled_recipe["enabled"])

    def test_recipe_due_window_matches_simple_cron(self):
        recipe = {"trigger": {"type": "schedule", "cron": "30 8 * * *"}}
        due, window = ai_council.recipe_due_window(recipe, now=datetime(2026, 6, 6, 8, 30, tzinfo=timezone.utc))
        not_due, _ = ai_council.recipe_due_window(recipe, now=datetime(2026, 6, 6, 8, 31, tzinfo=timezone.utc))

        self.assertTrue(due)
        self.assertIn("202606060830", window)
        self.assertFalse(not_due)

    def test_run_due_recipes_starts_once_per_window(self):
        recipe = {
            "scheduled_digest": {
                "name": "scheduled_digest",
                "description": "test",
                "enabled": True,
                "trigger": {"type": "schedule", "interval_seconds": 60},
                "risk": "R0",
                "approval_policy": "auto",
                "steps": [{"command": "/health", "prompt": ""}],
            }
        }

        def fake_cfg(key, default=""):
            if key == "AI_COUNCIL_RECIPE_SCHEDULER":
                return "true"
            if key == "TELEGRAM_ALLOWED_CHAT_ID":
                return "553"
            return default

        with temp_dir() as tmp:
            root = Path(tmp)
            with patch.object(ai_council, "RECIPES_DIR", root / "recipes"), patch.object(
                ai_council, "RECIPE_RUNS_FILE", root / "state" / "recipe_runs.jsonl"
            ), patch.object(ai_council, "TASKS_FILE", root / "state" / "tasks.jsonl"), patch.object(
                ai_council, "LOG_DIR", root / "logs"
            ), patch.object(ai_council, "AUDIT_LOG", root / "logs" / "audit.jsonl"), patch.object(
                ai_council, "default_recipes", return_value=recipe
            ), patch.object(ai_council, "cfg", side_effect=fake_cfg), patch.object(
                ai_council, "start_background_job", return_value="[AI Council] task-test"
            ) as start:
                now = datetime(2026, 6, 6, 12, 0, tzinfo=timezone.utc)
                first = ai_council.run_due_recipes(send=False, now=now)
                second = ai_council.run_due_recipes(send=False, now=now)
                runs = ai_council.read_jsonl(root / "state" / "recipe_runs.jsonl")

        self.assertEqual(first, 1)
        self.assertEqual(second, 0)
        self.assertEqual(len(runs), 1)
        start.assert_called_once()

    def test_default_autonomous_loop_recipes_exist(self):
        recipes = ai_council.default_recipes()

        self.assertIn("error_audit_twice_daily", recipes)
        self.assertIn("feature_evolution_loop", recipes)
        error_recipe = recipes["error_audit_twice_daily"]
        feature_recipe = recipes["feature_evolution_loop"]

        self.assertTrue(error_recipe["enabled"])
        self.assertTrue(error_recipe["capture_improvement"])
        self.assertEqual(error_recipe["trigger"]["cron"], "0 9,21 * * *")
        self.assertTrue(any("{previous}" in step.get("prompt", "") for step in error_recipe["steps"]))
        self.assertTrue(feature_recipe["enabled"])
        self.assertTrue(feature_recipe["capture_improvement"])
        self.assertEqual(feature_recipe["trigger"]["cron"], "15 10 * * *")
        self.assertTrue(any(step["command"] == "@xresearch" for step in feature_recipe["steps"]))
        self.assertTrue(any("{previous}" in step.get("prompt", "") for step in feature_recipe["steps"]))

    def test_recipe_prompt_can_use_previous_step_output(self):
        prompt = ai_council.render_recipe_step_prompt("input={input}\nprevious={previous}", "temat", "wynik groka")

        self.assertIn("input=temat", prompt)
        self.assertIn("previous=wynik groka", prompt)

    def test_claude_flow_uses_opus_48_without_default_budget_cap(self):
        completed = subprocess.CompletedProcess(args=["claude"], returncode=0, stdout="FLOW OK", stderr="")

        with patch.object(ai_council, "command_path", return_value="claude"), patch.object(
            ai_council, "memory_context_for_prompt", return_value=""
        ), patch.object(ai_council, "OPENCLAW_EXPORT", Path("/missing-openclaw")), patch.object(
            ai_council, "WORKSPACES_DIR", Path("/missing-workspaces")
        ), patch("ai_council.subprocess.run", return_value=completed) as run:
            response = ai_council.claude_flow_response("zrób pełny plan")

        args, kwargs = run.call_args
        command = args[0]
        self.assertIn("FLOW OK", response)
        self.assertIn("--model", command)
        self.assertEqual(command[command.index("--model") + 1], "claude-opus-4-8")
        self.assertIn("--permission-mode", command)
        self.assertEqual(command[command.index("--permission-mode") + 1], "plan")
        self.assertNotIn("--max-budget-usd", command)
        self.assertNotIn("--tools", command)
        self.assertEqual(kwargs["timeout"], 600)


class RoutingTests(unittest.TestCase):
    def test_plain_message_routes_to_fast_chat(self):
        route = ai_council.route_text("bez prefiksu")

        self.assertEqual(route["command"], "/chat")
        self.assertEqual(route["operators"], ["host"])
        self.assertEqual(route["prompt"], "bez prefiksu")
        self.assertFalse(ai_council.route_needs_task(route))
        self.assertFalse(ai_council.route_should_background(route))

    def test_chat_response_has_poke_style_fallback(self):
        with patch.object(ai_council, "poke_chat_llm_response", return_value=None):
            response = ai_council.build_response(ai_council.route_text("działasz?"))

        self.assertIn("Działam", response)
        self.assertNotIn("Komendy:", response)
        self.assertNotIn("task-", response)

    def test_research_wraps_prompt_as_polish_research_brief(self):
        captured = {}

        def fake_grok(prompt, max_chars=None):
            captured["prompt"] = prompt
            return "[Grok]\nok"

        with patch.object(ai_council, "grok_response", side_effect=fake_grok):
            response = ai_council.build_response({"command": "@research", "prompt": "rynek kancelarii AI"})

        self.assertEqual(response, "[Grok]\nok")
        self.assertIn("brief research", captured["prompt"].lower())
        self.assertIn("po polsku", captured["prompt"].lower())
        self.assertIn("rynek kancelarii AI", captured["prompt"])

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
            "/health": ("/health", ["host"]),
            "/cancel task-1": ("/cancel", ["host"]),
            "/status task-1": ("/status", ["host"]),
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
            "/errors": ("/errors", ["host"]),
            "/nudges": ("/nudges", ["host"]),
            "/sources": ("/sources", ["host"]),
            "/source search memory Poke": ("/source", ["host"]),
            "/connectors": ("/connectors", ["host"]),
            "/connector check github": ("/connector", ["host"]),
            "/improvements": ("/improvements", ["host"]),
            "/improve next": ("/improve", ["host"]),
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
            "pokaż błędy": "/errors",
            "pokaż nudges": "/nudges",
            "pokaż źródła": "/sources",
            "szukaj w źródłach memory Poke": "/source",
            "pokaż konektory": "/connectors",
            "sprawdź connector github": "/connector",
            "podłącz github": "/connector",
            "pokaż ulepszenia": "/improvements",
            "health": "/health",
            "anuluj task-1": "/cancel",
            "status task-1": "/status",
            "szczegóły task-1": "/details",
            "fakty task-1": "/facts",
            "next task-1": "/next",
            "pokaż kolejkę": "/queue",
            "zapamiętaj cel = test": "/memory",
            "wyszukaj w pamięci test": "/memory",
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
            "gdzie ten cel i czemu nie odpowiada jak Poke": "/goal",
            "Ani nie odpowiada on jak poke nie ma takich możliwości, o co chodzi gdzie ten cel ?": "/goal",
        }

        for text, command in cases.items():
            with self.subTest(text=text):
                self.assertEqual(ai_council.route_text(text)["command"], command)

        self.assertEqual(ai_council.route_text("normalne pytanie do codexa")["command"], "/chat")

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
        self.assertIn("[Claude Flow]\nok", response)

    def test_llm_route_parses_strict_json_and_selects_research(self):
        def fake_cfg(key, default=""):
            if key == "XAI_API_KEY":
                return "xai-test"
            if key == "AI_COUNCIL_LLM_ROUTER":
                return "true"
            return default

        with patch.object(ai_council, "cfg", side_effect=fake_cfg), patch.object(
            ai_council, "request_json", return_value={"choices": [{"message": {"content": '{"command":"@research","prompt":"nowy Grok","confidence":0.91,"reason":"research"}'}}]}
        ):
            route = ai_council.route_message("sprawdź proszę co ludzie piszą o nowym Groku", chat_id="553")

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

    def test_route_message_prefers_explicit_then_keyword_then_llm(self):
        with patch.object(ai_council, "llm_route", return_value={"command": "@research", "operators": ["grok"], "prompt": "x", "route_source": "llm", "confidence": 0.9}) as llm:
            explicit = ai_council.route_message("@codex ping", chat_id="553")
            keyword = ai_council.route_message("status", chat_id="553")
            natural = ai_council.route_message("sprawdź to szerzej", chat_id="553")

        self.assertEqual(explicit["command"], "@codex")
        self.assertEqual(explicit["route_source"], "explicit")
        self.assertEqual(keyword["command"], "/status")
        self.assertEqual(keyword["route_source"], "keyword")
        self.assertEqual(natural["command"], "@research")
        self.assertEqual(llm.call_count, 1)


class ConversationThreadTests(unittest.TestCase):
    def test_conversation_thread_roundtrip_isolated_by_chat_id(self):
        with temp_dir() as tmp:
            root = Path(tmp)
            with patch.object(ai_council, "CONVERSATIONS_FILE", root / "state" / "conversations.jsonl"), patch.object(
                ai_council, "LOG_DIR", root / "logs"
            ), patch.object(ai_council, "AUDIT_LOG", root / "logs" / "audit.jsonl"), patch.object(
                ai_council, "WORKSPACES_DIR", root / "workspaces"
            ), patch.object(ai_council, "ARTIFACTS_DIR", root / "artifacts"), patch.object(
                ai_council, "REPORTS_DIR", root / "reports"
            ), patch.object(ai_council, "ERRORS_DIR", root / "errors"), patch.object(
                ai_council, "RECIPES_DIR", root / "recipes"
            ), patch.object(ai_council, "BACKGROUND_JOB_SPECS_DIR", root / "state" / "background_job_specs"):
                ai_council.append_conversation_turn("553", "user", "pierwsze", {"command": "/chat"})
                ai_council.append_conversation_turn("553", "assistant", "drugie", {"command": "/chat"})
                ai_council.append_conversation_turn("999", "user", "obce", {"command": "/chat"})
                turns = ai_council.recent_conversation("553", limit=5)

        self.assertEqual([turn["text"] for turn in turns], ["pierwsze", "drugie"])
        self.assertTrue(all(turn["chat_id_hash"] == ai_council.short_hash("553") for turn in turns))

    def test_poke_chat_includes_recent_conversation_context(self):
        def fake_cfg(key, default=""):
            values = {
                "XAI_API_KEY": "xai-test",
                "AI_COUNCIL_POKE_CHAT_USE_GROK": "true",
                "AI_COUNCIL_POKE_CHAT_MODEL": "grok-test",
            }
            return values.get(key, default)

        with temp_dir() as tmp:
            root = Path(tmp)
            with patch.object(ai_council, "CONVERSATIONS_FILE", root / "state" / "conversations.jsonl"), patch.object(
                ai_council, "COSTS_FILE", root / "state" / "costs.jsonl"
            ), patch.object(ai_council, "LOG_DIR", root / "logs"), patch.object(
                ai_council, "AUDIT_LOG", root / "logs" / "audit.jsonl"
            ), patch.object(ai_council, "WORKSPACES_DIR", root / "workspaces"), patch.object(
                ai_council, "ARTIFACTS_DIR", root / "artifacts"
            ), patch.object(ai_council, "REPORTS_DIR", root / "reports"), patch.object(
                ai_council, "ERRORS_DIR", root / "errors"
            ), patch.object(ai_council, "RECIPES_DIR", root / "recipes"), patch.object(
                ai_council, "BACKGROUND_JOB_SPECS_DIR", root / "state" / "background_job_specs"
            ), patch.object(ai_council, "cfg", side_effect=fake_cfg), patch.object(
                ai_council, "memory_context_for_prompt", return_value=""
            ), patch.object(
                ai_council,
                "request_json",
                return_value={"choices": [{"message": {"content": "Jasne, robię krócej."}}]},
            ) as request_json:
                ai_council.append_conversation_turn("553", "user", "zrób research o Poke")
                ai_council.append_conversation_turn("553", "assistant", "Mam research.")
                response = ai_council.poke_chat_response("a teraz krócej", chat_id="553")

        self.assertIn("Jasne", response)
        messages = request_json.call_args.kwargs["payload"]["messages"]
        self.assertTrue(any(message["content"] == "zrób research o Poke" for message in messages))
        self.assertTrue(any(message["content"] == "Mam research." for message in messages))

    def test_listen_once_persists_user_and_assistant_turns(self):
        update = {
            "update_id": 101,
            "message": {
                "message_id": 1,
                "from": {"id": 553},
                "chat": {"id": 553},
                "text": "hej",
            },
        }

        def fake_cfg(key, default=""):
            values = {
                "TELEGRAM_BOT_TOKEN": "token",
                "TELEGRAM_ALLOWED_USER_ID": "553",
                "TELEGRAM_ALLOWED_CHAT_ID": "553",
                "XAI_API_KEY": "",
                "AI_COUNCIL_LLM_ROUTER": "false",
            }
            return values.get(key, default)

        with temp_dir() as tmp:
            root = Path(tmp)
            with patch.object(ai_council, "CONVERSATIONS_FILE", root / "state" / "conversations.jsonl"), patch.object(
                ai_council, "OFFSET_FILE", root / "state" / "telegram_offset"
            ), patch.object(ai_council, "ACTIONS_FILE", root / "state" / "actions.jsonl"), patch.object(
                ai_council, "LOG_DIR", root / "logs"
            ), patch.object(ai_council, "AUDIT_LOG", root / "logs" / "audit.jsonl"), patch.object(
                ai_council, "WORKSPACES_DIR", root / "workspaces"
            ), patch.object(ai_council, "ARTIFACTS_DIR", root / "artifacts"), patch.object(
                ai_council, "REPORTS_DIR", root / "reports"
            ), patch.object(ai_council, "ERRORS_DIR", root / "errors"), patch.object(
                ai_council, "RECIPES_DIR", root / "recipes"
            ), patch.object(ai_council, "BACKGROUND_JOB_SPECS_DIR", root / "state" / "background_job_specs"), patch.object(
                ai_council, "cfg", side_effect=fake_cfg
            ), patch.object(
                ai_council, "request_json", return_value={"ok": True, "result": [update]}
            ), patch.object(ai_council, "poke_chat_llm_response", return_value=None):
                code = ai_council.listen_once(send=False, limit=1, verbose=False)
                turns = ai_council.read_jsonl(root / "state" / "conversations.jsonl")
                audit_rows = ai_council.read_jsonl(root / "logs" / "audit.jsonl")

        self.assertEqual(code, 0)
        self.assertEqual([turn["role"] for turn in turns], ["user", "assistant"])
        self.assertEqual(turns[0]["text"], "hej")
        self.assertIn("Rozpoznaję to jako rozmowę", turns[1]["text"])
        self.assertEqual(audit_rows[-1]["route_source"], "fallback")
        self.assertEqual(audit_rows[-1]["confidence"], 0.0)


class ErrorStoreTests(unittest.TestCase):
    def test_record_error_writes_state_and_daily_error_files(self):
        with temp_dir() as tmp:
            root = Path(tmp)
            with patch.object(ai_council, "ERRORS_DIR", root / "errors"), patch.object(
                ai_council, "ERRORS_FILE", root / "state" / "errors.jsonl"
            ), patch.object(ai_council, "LOG_DIR", root / "logs"), patch.object(
                ai_council, "AUDIT_LOG", root / "logs" / "audit.jsonl"
            ), patch.object(ai_council, "WORKSPACES_DIR", root / "workspaces"), patch.object(
                ai_council, "ARTIFACTS_DIR", root / "artifacts"
            ), patch.object(ai_council, "REPORTS_DIR", root / "reports"), patch.object(
                ai_council, "RECIPES_DIR", root / "recipes"
            ), patch.object(ai_council, "BACKGROUND_JOB_SPECS_DIR", root / "state" / "background_job_specs"):
                try:
                    raise ValueError("telegram boom")
                except ValueError as exc:
                    error = ai_council.record_error("telegram_message", exc=exc, event={"command": "/chat"})

                rows = ai_council.read_jsonl(root / "state" / "errors.jsonl")
                daily_rows = ai_council.read_jsonl(root / "errors" / f"{error['day']}.jsonl")
                response = ai_council.errors_response("recent 5")

        self.assertEqual(len(rows), 1)
        self.assertEqual(len(daily_rows), 1)
        self.assertEqual(rows[0]["context"], "telegram_message")
        self.assertEqual(rows[0]["exception_type"], "ValueError")
        self.assertIn("telegram boom", rows[0]["traceback"])
        self.assertIn(error["error_id"], response)
        self.assertIn("telegram_message", response)


class ProactiveEventBrainTests(unittest.TestCase):
    def test_proactive_scan_creates_deduped_error_nudge(self):
        with temp_dir() as tmp:
            root = Path(tmp)
            errors_file = root / "state" / "errors.jsonl"
            nudges_file = root / "state" / "nudges.jsonl"
            ai_council.append_jsonl(
                errors_file,
                {
                    "error_id": "err-1",
                    "created_at": ai_council.utc_now(),
                    "day": ai_council.today_utc(),
                    "context": "telegram_getUpdates",
                    "severity": "warning",
                    "message": "http_409",
                },
            )

            with patch.object(ai_council, "ERRORS_FILE", errors_file), patch.object(
                ai_council, "NUDGES_FILE", nudges_file
            ), patch.object(ai_council, "ACTIONS_FILE", root / "state" / "actions.jsonl"), patch.object(
                ai_council, "TASKS_FILE", root / "state" / "tasks.jsonl"
            ), patch.object(ai_council, "COSTS_FILE", root / "state" / "costs.jsonl"):
                first = ai_council.run_proactive_scan(send=False)
                second = ai_council.run_proactive_scan(send=False)
                rows = ai_council.read_jsonl(nudges_file)
                response = ai_council.nudges_response()

        self.assertEqual(first, 1)
        self.assertEqual(second, 0)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["kind"], "errors")
        self.assertIn("/errors recent 10", rows[0]["next_action"])
        self.assertIn("err", rows[0]["nudge_key"])
        self.assertIn("[Council] Nudges", response)

    def test_proactive_scan_creates_pending_action_nudge(self):
        with temp_dir() as tmp:
            root = Path(tmp)
            actions_file = root / "state" / "actions.jsonl"
            nudges_file = root / "state" / "nudges.jsonl"
            ai_council.append_jsonl(
                actions_file,
                {
                    "action_id": "act-1",
                    "created_at": "2020-01-01T00:00:00+00:00",
                    "status": "pending",
                    "type": "manual",
                    "description": "Zatwierdź testową akcję",
                },
            )

            with patch.object(ai_council, "ACTIONS_FILE", actions_file), patch.object(
                ai_council, "NUDGES_FILE", nudges_file
            ), patch.object(ai_council, "ERRORS_FILE", root / "state" / "errors.jsonl"), patch.object(
                ai_council, "TASKS_FILE", root / "state" / "tasks.jsonl"
            ), patch.object(ai_council, "COSTS_FILE", root / "state" / "costs.jsonl"):
                created = ai_council.run_proactive_scan(send=False)
                rows = ai_council.read_jsonl(nudges_file)

        self.assertEqual(created, 1)
        self.assertEqual(rows[0]["kind"], "pending_action")
        self.assertEqual(rows[0]["action_id"], "act-1")
        self.assertIn("/approve act-1", rows[0]["next_action"])

    def test_nudges_response_can_dismiss_nudge(self):
        with temp_dir() as tmp:
            root = Path(tmp)
            nudges_file = root / "state" / "nudges.jsonl"
            ai_council.append_jsonl(
                nudges_file,
                {
                    "nudge_id": "nudge-1",
                    "nudge_key": "key-1",
                    "created_at": ai_council.utc_now(),
                    "kind": "errors",
                    "status": "open",
                    "title": "Błąd",
                    "next_action": "/errors",
                },
            )
            with patch.object(ai_council, "NUDGES_FILE", nudges_file):
                dismissed = ai_council.nudges_response("dismiss nudge-1")
                latest = ai_council.latest_nudges(limit=1)[0]

        self.assertIn("dismissed", dismissed)
        self.assertEqual(latest["status"], "dismissed")


class ImprovementBacklogTests(unittest.TestCase):
    def test_create_show_and_close_improvement(self):
        with temp_dir() as tmp:
            root = Path(tmp)
            with patch.object(ai_council, "IMPROVEMENTS_FILE", root / "state" / "improvements.jsonl"), patch.object(
                ai_council, "LOG_DIR", root / "logs"
            ), patch.object(ai_council, "AUDIT_LOG", root / "logs" / "audit.jsonl"), patch.object(
                ai_council, "WORKSPACES_DIR", root / "workspaces"
            ), patch.object(ai_council, "ARTIFACTS_DIR", root / "artifacts"), patch.object(
                ai_council, "REPORTS_DIR", root / "reports"
            ), patch.object(ai_council, "ERRORS_DIR", root / "errors"), patch.object(
                ai_council, "RECIPES_DIR", root / "recipes"
            ), patch.object(ai_council, "BACKGROUND_JOB_SPECS_DIR", root / "state" / "background_job_specs"):
                improvement = ai_council.create_improvement(
                    source="test_loop",
                    title="Wdrożyć szybkie replies",
                    summary="DECYZJA: Wdrożyć szybkie replies w Telegramu.",
                    task_id="task-1",
                    recipe="feature_evolution_loop",
                )
                listing = ai_council.improvements_response()
                shown = ai_council.improvements_response(f"show {improvement['improvement_id']}")
                done = ai_council.improvements_response(f"done {improvement['improvement_id']}")
                latest = ai_council.get_latest_improvement(improvement["improvement_id"])

        self.assertIn(improvement["improvement_id"], listing)
        self.assertIn("Wdrożyć szybkie replies", shown)
        self.assertIn("done", done)
        self.assertEqual(latest["status"], "done")

    def test_improve_apply_routes_to_background_task(self):
        route = ai_council.route_text("/improve apply imp-1")
        show_route = ai_council.route_text("/improve show imp-1")

        self.assertEqual(route["command"], "/improve")
        self.assertTrue(ai_council.route_needs_task(route))
        self.assertTrue(ai_council.route_should_background(route))
        self.assertFalse(ai_council.route_needs_task(show_route))
        self.assertFalse(ai_council.route_should_background(show_route))

    def test_improve_apply_background_marks_item_planned(self):
        with temp_dir() as tmp:
            root = Path(tmp)
            with patch.object(ai_council, "IMPROVEMENTS_FILE", root / "state" / "improvements.jsonl"), patch.object(
                ai_council, "LOG_DIR", root / "logs"
            ), patch.object(ai_council, "AUDIT_LOG", root / "logs" / "audit.jsonl"), patch.object(
                ai_council, "WORKSPACES_DIR", root / "workspaces"
            ), patch.object(ai_council, "ARTIFACTS_DIR", root / "artifacts"), patch.object(
                ai_council, "REPORTS_DIR", root / "reports"
            ), patch.object(ai_council, "ERRORS_DIR", root / "errors"), patch.object(
                ai_council, "RECIPES_DIR", root / "recipes"
            ), patch.object(ai_council, "BACKGROUND_JOB_SPECS_DIR", root / "state" / "background_job_specs"), patch.object(
                ai_council,
                "build_structured_council_result",
                return_value={
                    "decision": "plan ready",
                    "facts": ["scope wybrany"],
                    "dispute": "",
                    "next_actions": ["wdrożyć test"],
                    "ask_user": "zatwierdź",
                    "raw_output": "plan",
                    "report": "plan",
                },
            ) as council:
                improvement = ai_council.create_improvement(
                    source="test_loop",
                    title="Front Brain",
                    summary="Zbudować LLM router intencji.",
                    task_id="task-source",
                )
                result = ai_council.run_improve_background(f"apply {improvement['improvement_id']}", task_id="task-plan")
                planned = ai_council.get_latest_improvement(improvement["improvement_id"])

        council.assert_called_once()
        self.assertEqual(planned["status"], "planned")
        self.assertEqual(planned["plan_task_id"], "task-plan")
        self.assertIn("/details task-plan", " ".join(result["next_actions"]))
        self.assertIn("/improve done", " ".join(result["next_actions"]))
        self.assertIn("Improvement apply", result["report"])

    def test_recipe_with_capture_improvement_writes_backlog_item(self):
        recipe = {
            "loop": {
                "name": "loop",
                "description": "test loop",
                "enabled": True,
                "trigger": {"type": "manual"},
                "capture_improvement": True,
                "improvement_policy": {"enabled": True, "source": "test_loop", "priority": "P1"},
                "steps": [{"command": "/chat", "prompt": "plan"}],
            }
        }
        with temp_dir() as tmp:
            root = Path(tmp)
            with patch.object(ai_council, "RECIPES_DIR", root / "recipes"), patch.object(
                ai_council, "IMPROVEMENTS_FILE", root / "state" / "improvements.jsonl"
            ), patch.object(ai_council, "LOG_DIR", root / "logs"), patch.object(
                ai_council, "AUDIT_LOG", root / "logs" / "audit.jsonl"
            ), patch.object(ai_council, "WORKSPACES_DIR", root / "workspaces"), patch.object(
                ai_council, "ARTIFACTS_DIR", root / "artifacts"
            ), patch.object(ai_council, "REPORTS_DIR", root / "reports"), patch.object(
                ai_council, "ERRORS_DIR", root / "errors"
            ), patch.object(ai_council, "BACKGROUND_JOB_SPECS_DIR", root / "state" / "background_job_specs"), patch.object(
                ai_council, "default_recipes", return_value=recipe
            ), patch.object(ai_council, "poke_chat_response", return_value="DECYZJA: Wdrożyć backlog loop.\nNEXT: test"):
                result = ai_council.run_recipe_background("run loop", task_id="task-loop")
                rows = ai_council.read_jsonl(root / "state" / "improvements.jsonl")

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["source"], "test_loop")
        self.assertEqual(rows[0]["source_task_id"], "task-loop")
        self.assertEqual(rows[0]["priority"], "P1")
        self.assertIn("/improve show", " ".join(result["next_actions"]))


class L2LedgerTests(unittest.TestCase):
    def test_memory_save_recent_and_search_use_sqlite(self):
        with temp_dir() as tmp:
            root = Path(tmp)
            with patch.object(ai_council, "MEMORY_DB", root / "memory.sqlite"), patch.object(
                ai_council, "LOG_DIR", root / "logs"
            ), patch.object(ai_council, "AUDIT_LOG", root / "logs" / "audit.jsonl"):
                saved = ai_council.memory_save("ai-council", "Bartek testuje pamięć L2", source="test")
                recent = ai_council.memory_recent()
                found = ai_council.memory_search("pamięć")

        self.assertTrue(saved["entry_id"].startswith("mem-"))
        self.assertEqual(recent[0]["key"], "ai-council")
        self.assertEqual(found[0]["entry_id"], saved["entry_id"])

    def test_sources_response_reports_github_auth_required(self):
        with temp_dir() as tmp:
            root = Path(tmp)
            with patch.object(ai_council, "MEMORY_DB", root / "memory.sqlite"), patch.object(
                ai_council, "ARTIFACTS_DIR", root / "artifacts"
            ), patch.object(ai_council, "REPORTS_DIR", root / "reports"), patch.object(
                ai_council, "OPENCLAW_EXPORT", root / "openclaw"
            ), patch.object(ai_council, "command_status", return_value=(False, "token invalid")), patch.object(
                ai_council, "cfg", side_effect=lambda key, default="": default
            ):
                response = ai_council.sources_response()

        self.assertIn("github | auth_required", response)
        self.assertIn("gmail | auth_required", response)
        self.assertIn("Write/send/schedule", response)

    def test_source_search_memory_is_source_backed(self):
        with temp_dir() as tmp:
            root = Path(tmp)
            with patch.object(ai_council, "MEMORY_DB", root / "memory.sqlite"), patch.object(
                ai_council, "LOG_DIR", root / "logs"
            ), patch.object(ai_council, "AUDIT_LOG", root / "logs" / "audit.jsonl"):
                ai_council.memory_save("poke", "Poke ma recipes i Apple Messages.", source="test")
                response = ai_council.source_response("search memory recipes")

        self.assertIn("Source search `memory`", response)
        self.assertIn("memory:mem-", response)
        self.assertIn("Poke ma recipes", response)
        self.assertIn("read-only", response)

    def test_source_search_artifacts_reads_local_files_only(self):
        with temp_dir() as tmp:
            root = Path(tmp)
            artifact = root / "artifacts" / "task-1" / "report.md"
            artifact.parent.mkdir(parents=True)
            artifact.write_text("Raport o Gmail Calendar Drive GitHub read-only.", encoding="utf-8")
            with patch.object(ai_council, "ARTIFACTS_DIR", root / "artifacts"), patch.object(
                ai_council, "REPORTS_DIR", root / "reports"
            ), patch.object(ai_council, "CLAUDE_COLLAB_DIR", root / "claude"):
                status, results = ai_council.source_search("artifacts", "Gmail", limit=3)

        self.assertEqual(status, "available")
        self.assertEqual(len(results), 1)
        self.assertIn("report.md", results[0]["source"])
        self.assertIn("Gmail Calendar", results[0]["snippet"])

    def test_source_search_github_requires_auth_when_gh_invalid(self):
        with patch.object(ai_council, "command_status", return_value=(False, "token invalid")), patch.object(
            ai_council, "request_json", return_value={"ok": False, "error": "url_error"}
        ):
            status, results = ai_council.source_search("github", "issue", limit=3)

        self.assertIn("auth_required", status)
        self.assertEqual(results, [])

    def test_source_search_github_uses_public_fallback_when_gh_invalid(self):
        payload = {
            "items": [
                {
                    "number": 7,
                    "title": "Connector bridge",
                    "html_url": "https://github.com/Acoste616/AIagent/issues/7",
                    "body": "Poke parity connector work",
                    "labels": [{"name": "l4"}],
                }
            ]
        }
        with patch.object(ai_council, "command_status", return_value=(False, "token invalid")), patch.object(
            ai_council, "request_json", return_value=payload
        ):
            status, results = ai_council.source_search("github", "connector", limit=3)

        self.assertIn("auth_required", status)
        self.assertIn("public_fallback", status)
        self.assertEqual(len(results), 1)
        self.assertIn("Connector bridge", results[0]["title"])

    def test_source_search_github_uses_token_api_when_gh_invalid(self):
        payload = {
            "items": [
                {
                    "number": 9,
                    "title": "Private connector task",
                    "html_url": "https://github.com/Acoste616/AIagent/issues/9",
                    "body": "Private repo source",
                    "labels": [],
                }
            ]
        }

        def fake_cfg(key, default=""):
            values = {
                "GITHUB_TOKEN": "ghp_test_token_secret",
                "AI_COUNCIL_GITHUB_REPO": "Acoste616/AIagent",
            }
            return values.get(key, default)

        with patch.object(ai_council, "command_status", return_value=(False, "token invalid")), patch.object(
            ai_council, "request_json", return_value=payload
        ) as request_json, patch.object(ai_council, "cfg", side_effect=fake_cfg):
            status, results = ai_council.source_search("github", "private", limit=3)

        self.assertIn("token_api", status)
        self.assertEqual(len(results), 1)
        self.assertIn("Private connector task", results[0]["title"])
        headers = request_json.call_args.kwargs["headers"]
        self.assertEqual(headers["Authorization"], "Bearer ghp_test_token_secret")
        self.assertIn("api.github.com/search/issues", request_json.call_args.args[0])
        self.assertIn("repo%3AAcoste616%2FAIagent", request_json.call_args.args[0])

    def test_source_search_github_token_auth_error_does_not_fall_back_public(self):
        calls = []

        def fake_request(url, **kwargs):
            calls.append(url)
            return {"ok": False, "error": "http_401"}

        def fake_cfg(key, default=""):
            return {"GITHUB_TOKEN": "ghp_test_token_secret"}.get(key, default)

        with patch.object(ai_council, "command_status", return_value=(False, "token invalid")), patch.object(
            ai_council, "request_json", side_effect=fake_request
        ), patch.object(ai_council, "cfg", side_effect=fake_cfg):
            status, results = ai_council.source_search("github", "private", limit=3)

        self.assertIn("token_api_error: http_401", status)
        self.assertEqual(results, [])
        self.assertEqual(len(calls), 1)

    def test_connectors_response_reports_github_token_present(self):
        def fake_cfg(key, default=""):
            values = {
                "GITHUB_TOKEN": "ghp_test_token_secret",
                "AI_COUNCIL_GITHUB_REPO": "Acoste616/AIagent",
            }
            return values.get(key, default)

        with temp_dir() as tmp:
            root = Path(tmp)
            with patch.object(ai_council, "MEMORY_DB", root / "memory.sqlite"), patch.object(
                ai_council, "ARTIFACTS_DIR", root / "artifacts"
            ), patch.object(ai_council, "REPORTS_DIR", root / "reports"), patch.object(
                ai_council, "OPENCLAW_EXPORT", root / "openclaw"
            ), patch.object(
                ai_council,
                "SOURCE_EXPORT_DEFAULTS",
                {
                    "AI_COUNCIL_GMAIL_EXPORT_DIR": root / "sources" / "gmail",
                    "AI_COUNCIL_CALENDAR_EXPORT_DIR": root / "sources" / "calendar",
                    "AI_COUNCIL_DRIVE_EXPORT_DIR": root / "sources" / "drive",
                },
            ), patch.object(ai_council, "CONNECTOR_INDEX_DB", root / "state" / "connector_index.sqlite"), patch.object(
                ai_council, "STATE_DIR", root / "state"
            ), patch.object(ai_council, "command_status", return_value=(False, "token invalid")), patch.object(
                ai_council, "cfg", side_effect=fake_cfg
            ):
                response = ai_council.connectors_response()

        self.assertIn("github | token_present", response)
        self.assertNotIn("ghp_test_token_secret", response)

    def test_connectors_response_reports_readiness_and_auth(self):
        with temp_dir() as tmp:
            root = Path(tmp)
            with patch.object(ai_council, "MEMORY_DB", root / "memory.sqlite"), patch.object(
                ai_council, "ARTIFACTS_DIR", root / "artifacts"
            ), patch.object(ai_council, "REPORTS_DIR", root / "reports"), patch.object(
                ai_council, "OPENCLAW_EXPORT", root / "openclaw"
            ), patch.object(
                ai_council,
                "SOURCE_EXPORT_DEFAULTS",
                {
                    "AI_COUNCIL_GMAIL_EXPORT_DIR": root / "sources" / "gmail",
                    "AI_COUNCIL_CALENDAR_EXPORT_DIR": root / "sources" / "calendar",
                    "AI_COUNCIL_DRIVE_EXPORT_DIR": root / "sources" / "drive",
                },
            ), patch.object(ai_council, "CONNECTOR_INDEX_DB", root / "state" / "connector_index.sqlite"), patch.object(
                ai_council, "STATE_DIR", root / "state"
            ), patch.object(ai_council, "command_status", return_value=(False, "token invalid")), patch.object(
                ai_council, "cfg", side_effect=lambda key, default="": default
            ):
                response = ai_council.connectors_response()

        self.assertIn("Connectors L4.13", response)
        self.assertIn("github | auth_required", response)
        self.assertIn("Ready:", response)
        self.assertIn("/connector check", response)

    def test_connector_auth_github_returns_nonsecret_setup_steps(self):
        with patch.object(ai_council, "command_status", return_value=(False, "token invalid")), patch.object(
            ai_council, "cfg", side_effect=lambda key, default="": default
        ):
            response = ai_council.connector_response("auth github")

        self.assertIn("gh auth login", response)
        self.assertIn("Nie wklejaj tokenów", response)

    def test_connector_name_aliases_are_normalized(self):
        self.assertEqual(ai_council.normalize_connector_name("google drive"), "drive")
        self.assertEqual(ai_council.normalize_connector_name("google_drive"), "drive")
        self.assertEqual(ai_council.normalize_connector_name("mail"), "gmail")
        self.assertEqual(ai_council.normalize_connector_name("openclaw export"), "openclaw")

    def test_connector_brief_requires_query(self):
        response = ai_council.connector_response("brief artifacts")

        self.assertIn("wymaga query", response)
        self.assertIn("/connector check artifacts", response)

    def test_connector_ingest_indexes_export_cache(self):
        with temp_dir() as tmp:
            root = Path(tmp)
            gmail_dir = root / "sources" / "gmail"
            gmail_dir.mkdir(parents=True)
            (gmail_dir / "mail.md").write_text("Poke parity email cache about recipes.", encoding="utf-8")
            with patch.object(
                ai_council,
                "SOURCE_EXPORT_DEFAULTS",
                {
                    "AI_COUNCIL_GMAIL_EXPORT_DIR": gmail_dir,
                    "AI_COUNCIL_CALENDAR_EXPORT_DIR": root / "sources" / "calendar",
                    "AI_COUNCIL_DRIVE_EXPORT_DIR": root / "sources" / "drive",
                },
            ), patch.object(ai_council, "CONNECTOR_INDEX_DB", root / "state" / "connector_index.sqlite"), patch.object(
                ai_council, "STATE_DIR", root / "state"
            ), patch.object(
                ai_council, "cfg", side_effect=lambda key, default="": default
            ):
                response = ai_council.connector_response("ingest gmail")
                (gmail_dir / "fresh.md").write_text("Fresh recipes file after ingest.", encoding="utf-8")
                status, results = ai_council.source_search("gmail", "recipes", limit=3)

        self.assertIn("indexed_now: 1", response)
        self.assertEqual(status, "available_index")
        self.assertEqual(len(results), 2)
        self.assertIn("email cache", results[0]["snippet"])
        self.assertTrue(any("Fresh recipes" in item["snippet"] for item in results))

    def test_connector_brief_writes_source_backed_report(self):
        with temp_dir() as tmp:
            root = Path(tmp)
            artifact = root / "artifacts" / "task-1" / "report.md"
            artifact.parent.mkdir(parents=True)
            artifact.write_text("Poke connector brief source-backed result.", encoding="utf-8")
            with patch.object(ai_council, "ARTIFACTS_DIR", root / "artifacts"), patch.object(
                ai_council, "REPORTS_DIR", root / "reports"
            ), patch.object(ai_council, "CLAUDE_COLLAB_DIR", root / "claude"), patch.object(
                ai_council, "LOG_DIR", root / "logs"
            ), patch.object(ai_council, "AUDIT_LOG", root / "logs" / "audit.jsonl"):
                response = ai_council.connector_response("brief artifacts Poke")
                report_path = Path(response.split("report: ", 1)[1].splitlines()[0])
                report_text = report_path.read_text(encoding="utf-8")

        self.assertIn("Connector brief `artifacts`", response)
        self.assertIn("results: 1", response)
        self.assertIn("source-backed", report_text)

    def test_action_create_approve_and_deny(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            with patch.object(ai_council, "ACTIONS_FILE", root / "actions.jsonl"), patch.object(
                ai_council, "LOG_DIR", root / "logs"
            ), patch.object(ai_council, "AUDIT_LOG", root / "logs" / "audit.jsonl"):
                action = ai_council.create_action("Przetestuj approval gate", risk="low")
                approved = ai_council.update_action_status(action["action_id"], "approved")
                denied = ai_council.update_action_status(action["action_id"], "denied")
                actions = ai_council.latest_by_id(root / "actions.jsonl", "action_id")

        self.assertTrue(action["action_id"].startswith("act-"))
        self.assertEqual(approved["status"], "approved")
        self.assertEqual(denied["status"], "denied")
        self.assertEqual(actions[0]["status"], "denied")

    def test_task_status_update_cancel_and_status_response(self):
        with temp_dir() as tmp:
            root = Path(tmp)
            with patch.object(ai_council, "TASKS_FILE", root / "tasks.jsonl"), patch.object(
                ai_council, "LOG_DIR", root / "logs"
            ), patch.object(ai_council, "AUDIT_LOG", root / "logs" / "audit.jsonl"):
                task = ai_council.create_task(
                    "pełny flow test",
                    status="running",
                    command="/flow",
                    operators=["claude-flow"],
                    idempotency_key="idem-1",
                )
                updated = ai_council.update_task_status(task["task_id"], "completed", "done", duration_ms=123)
                status = ai_council.task_status_response(task["task_id"])
                cancel = ai_council.cancel_response(task["task_id"])
                latest = ai_council.get_latest_task(task["task_id"])

        self.assertEqual(updated["status"], "completed")
        self.assertIn("duration_ms: 123", status)
        self.assertIn("Cancel pominięty", cancel)
        self.assertEqual(latest["status"], "completed")

    def test_idempotency_finds_recent_duplicate(self):
        with temp_dir() as tmp:
            root = Path(tmp)
            with patch.object(ai_council, "TASKS_FILE", root / "tasks.jsonl"), patch.object(
                ai_council, "LOG_DIR", root / "logs"
            ), patch.object(ai_council, "AUDIT_LOG", root / "logs" / "audit.jsonl"):
                task = ai_council.create_task(
                    "powtórzony prompt",
                    status="running",
                    command="@claude-flow",
                    operators=["claude-flow"],
                    idempotency_key="idem-dup",
                )
                duplicate = ai_council.find_recent_duplicate("idem-dup", window_seconds=300)
                response = ai_council.duplicate_response(duplicate)

        self.assertEqual(duplicate["task_id"], task["task_id"])
        self.assertIn("Duplikat zablokowany", response)

    def test_cost_ledger_and_grok_call_limit(self):
        with temp_dir() as tmp:
            root = Path(tmp)
            with patch.object(ai_council, "COSTS_FILE", root / "costs.jsonl"), patch.dict(
                os.environ,
                {"GROK_DAILY_CALL_LIMIT": "1", "GROK_DAILY_BUDGET_USD": "10"},
                clear=False,
            ):
                ai_council.record_operator_usage("grok", task_id="task-1", duration_ms=50)
                allowed, reason = ai_council.operator_call_allowed("grok")
                cost = ai_council.cost_response()

        self.assertFalse(allowed)
        self.assertIn("call limit", reason)
        self.assertIn("grok: calls=1", cost)

    def test_workspace_write_requires_approval_and_stays_in_workspace(self):
        with temp_dir() as tmp:
            root = Path(tmp)
            workspaces = root / "workspaces"
            with patch.object(ai_council, "WORKSPACES_DIR", workspaces), patch.object(
                ai_council, "ACTIONS_FILE", root / "actions.jsonl"
            ), patch.object(ai_council, "MEMORY_DB", root / "memory.sqlite"), patch.object(
                ai_council, "LOG_DIR", root / "logs"
            ), patch.object(ai_council, "AUDIT_LOG", root / "logs" / "audit.jsonl"):
                action = ai_council.create_workspace_write_action("shared/hello.txt = hello L2.3")
                self.assertEqual(action["status"], "pending")
                self.assertFalse((workspaces / "shared" / "hello.txt").exists())

                response = ai_council.approve_response(action["action_id"])

                self.assertIn("executed", response)
                self.assertEqual((workspaces / "shared" / "hello.txt").read_text(encoding="utf-8"), "hello L2.3")
                latest = ai_council.latest_by_id(root / "actions.jsonl", "action_id", limit=1)[0]
                self.assertEqual(latest["status"], "executed")

    def test_workspace_write_rejects_path_escape(self):
        with temp_dir() as tmp:
            root = Path(tmp)
            with patch.object(ai_council, "WORKSPACES_DIR", root / "workspaces"), patch.object(
                ai_council, "ACTIONS_FILE", root / "actions.jsonl"
            ), patch.object(ai_council, "LOG_DIR", root / "logs"), patch.object(
                ai_council, "AUDIT_LOG", root / "logs" / "audit.jsonl"
            ):
                action = ai_council.create_workspace_write_action("../outside.txt = no")

        self.assertEqual(action["type"], "workspace_write_rejected")
        self.assertEqual(action["risk"], "R2")

    def test_risk_officer_classifies_risk_levels(self):
        self.assertEqual(ai_council.risk_level_for_text("odpowiedz na pytanie")[0], "R0")
        self.assertEqual(ai_council.risk_level_for_text("zapisz plik workspace")[0], "R1")
        self.assertEqual(ai_council.risk_level_for_text("run command in powershell")[0], "R2")
        self.assertEqual(ai_council.risk_level_for_text("gmail api write")[0], "R3")
        self.assertEqual(ai_council.risk_level_for_text("publish and billing change")[0], "R4")

    def test_execute_verify_and_rollback_workspace_write(self):
        with temp_dir() as tmp:
            root = Path(tmp)
            workspaces = root / "workspaces"
            target = workspaces / "shared" / "hello.txt"
            with patch.object(ai_council, "WORKSPACES_DIR", workspaces), patch.object(
                ai_council, "ACTIONS_FILE", root / "actions.jsonl"
            ), patch.object(ai_council, "MEMORY_DB", root / "memory.sqlite"), patch.object(
                ai_council, "LOG_DIR", root / "logs"
            ), patch.object(ai_council, "AUDIT_LOG", root / "logs" / "audit.jsonl"):
                action = ai_council.create_workspace_write_action("shared/hello.txt = hello L3")
                executed = ai_council.execute_response(action["action_id"])
                verified = ai_council.verify_response(action["action_id"])
                rolled_back = ai_council.rollback_response(action["action_id"])
                rollback_verified = ai_council.verify_response(action["action_id"])
                latest = ai_council.latest_by_id(root / "actions.jsonl", "action_id", limit=1)[0]

        self.assertEqual(action["risk"], "R1")
        self.assertIn("Approved + executed", executed)
        self.assertIn("OK", verified)
        self.assertIn("Rollback executed", rolled_back)
        self.assertIn("OK", rollback_verified)
        self.assertFalse(target.exists())
        self.assertEqual(latest["status"], "rolled_back")

    def test_workspace_append_requires_approval_and_stays_in_workspace(self):
        with temp_dir() as tmp:
            root = Path(tmp)
            workspaces = root / "workspaces"
            target = workspaces / "shared" / "hello.txt"
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text("hello", encoding="utf-8")
            with patch.object(ai_council, "WORKSPACES_DIR", workspaces), patch.object(
                ai_council, "ACTIONS_FILE", root / "actions.jsonl"
            ), patch.object(ai_council, "MEMORY_DB", root / "memory.sqlite"), patch.object(
                ai_council, "LOG_DIR", root / "logs"
            ), patch.object(ai_council, "AUDIT_LOG", root / "logs" / "audit.jsonl"):
                action = ai_council.create_workspace_append_action("shared/hello.txt =  L2.3")
                self.assertEqual(action["status"], "pending")

                response = ai_council.approve_response(action["action_id"])

                self.assertIn("executed", response)
                self.assertEqual(target.read_text(encoding="utf-8"), "hello L2.3")
                latest = ai_council.latest_by_id(root / "actions.jsonl", "action_id", limit=1)[0]
                self.assertEqual(latest["status"], "executed")

    def test_workspace_patch_requires_approval_and_stays_in_workspace(self):
        with temp_dir() as tmp:
            root = Path(tmp)
            workspaces = root / "workspaces"
            target = workspaces / "shared" / "hello.txt"
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text("hello old", encoding="utf-8")
            with patch.object(ai_council, "WORKSPACES_DIR", workspaces), patch.object(
                ai_council, "ACTIONS_FILE", root / "actions.jsonl"
            ), patch.object(ai_council, "MEMORY_DB", root / "memory.sqlite"), patch.object(
                ai_council, "LOG_DIR", root / "logs"
            ), patch.object(ai_council, "AUDIT_LOG", root / "logs" / "audit.jsonl"):
                action = ai_council.create_workspace_patch_action("shared/hello.txt :: old => new")
                self.assertEqual(action["status"], "pending")

                response = ai_council.approve_response(action["action_id"])

                self.assertIn("executed", response)
                self.assertEqual(target.read_text(encoding="utf-8"), "hello new")
                latest = ai_council.latest_by_id(root / "actions.jsonl", "action_id", limit=1)[0]
                self.assertEqual(latest["status"], "executed")


class L25BackgroundTests(unittest.TestCase):
    def test_route_should_background_only_explicit_long_routes(self):
        background = ["/flow test", "@claude-flow test", "@codex test", "@grok test", "@research test", "@all test", "/council test"]
        for text in background:
            with self.subTest(text=text):
                self.assertTrue(ai_council.route_should_background(ai_council.route_text(text)))

        foreground = ["krótkie pytanie", "@claude test", "/status task-1", "/health", "/write shared/a.txt = ok"]
        for text in foreground:
            with self.subTest(text=text):
                self.assertFalse(ai_council.route_should_background(ai_council.route_text(text)))

    def test_start_background_job_writes_spec_and_task_pid(self):
        class FakePopen:
            pid = 4321

        with temp_dir() as tmp:
            root = Path(tmp)
            with patch.object(ai_council, "STATE_DIR", root / "state"), patch.object(
                ai_council, "TASKS_FILE", root / "state" / "tasks.jsonl"
            ), patch.object(ai_council, "BACKGROUND_JOBS_FILE", root / "state" / "background_jobs.jsonl"), patch.object(
                ai_council, "BACKGROUND_JOB_SPECS_DIR", root / "state" / "background_job_specs"
            ), patch.object(ai_council, "LOG_DIR", root / "logs"), patch.object(
                ai_council, "AUDIT_LOG", root / "logs" / "audit.jsonl"
            ), patch.object(ai_council, "ARTIFACTS_DIR", root / "artifacts"), patch.object(
                ai_council, "REPORTS_DIR", root / "reports"
            ), patch("ai_council.subprocess.Popen", return_value=FakePopen()) as popen:
                task = ai_council.create_task("duży plan", status="running", command="/flow", operators=["claude-flow"])
                task_id = task["task_id"]
                route = {"command": "/flow", "operators": ["claude-flow"], "prompt": "duży plan", "task_id": task_id}
                response = ai_council.start_background_job(route, chat_id="553", task_id=task_id, send_progress=False)
                latest = ai_council.get_latest_task(task_id)
                spec_path = ai_council.background_job_spec_path(task_id)
                spec_exists = spec_path.exists()

        self.assertIn("START: praca uruchomiona w tle", response)
        self.assertIn(f"/details {task_id}", response)
        self.assertEqual(latest["status"], "running_background")
        self.assertEqual(latest["worker_pid"], 4321)
        self.assertTrue(spec_exists)
        args, kwargs = popen.call_args
        self.assertIn("run-background-job", args[0])
        self.assertIn("--task-id", args[0])

    def test_cancel_kills_worker_pid(self):
        with temp_dir() as tmp:
            root = Path(tmp)
            with patch.object(ai_council, "TASKS_FILE", root / "tasks.jsonl"), patch.object(
                ai_council, "BACKGROUND_JOBS_FILE", root / "background_jobs.jsonl"
            ), patch.object(ai_council, "LOG_DIR", root / "logs"), patch.object(
                ai_council, "AUDIT_LOG", root / "logs" / "audit.jsonl"
            ), patch.object(ai_council, "terminate_pid", return_value=(True, "killed")) as terminate:
                task = ai_council.create_task("flow", status="running_background", command="/flow", operators=["claude-flow"])
                ai_council.update_task_status(task["task_id"], "running_background", "worker", worker_pid=9876)
                response = ai_council.cancel_response(task["task_id"])
                latest = ai_council.get_latest_task(task["task_id"])

        terminate.assert_called_with(9876)
        self.assertIn("pid 9876: killed", response)
        self.assertEqual(latest["status"], "cancelled")

    def test_cancel_does_not_kill_completed_task_pid(self):
        with temp_dir() as tmp:
            root = Path(tmp)
            with patch.object(ai_council, "TASKS_FILE", root / "tasks.jsonl"), patch.object(
                ai_council, "BACKGROUND_JOBS_FILE", root / "background_jobs.jsonl"
            ), patch.object(ai_council, "LOG_DIR", root / "logs"), patch.object(
                ai_council, "AUDIT_LOG", root / "logs" / "audit.jsonl"
            ), patch.object(ai_council, "terminate_pid", return_value=(True, "killed")) as terminate:
                task = ai_council.create_task("flow", status="running_background", command="/flow", operators=["claude-flow"])
                ai_council.update_task_status(task["task_id"], "completed", "done", worker_pid=4242)
                rows_before = len(ai_council.read_jsonl(root / "tasks.jsonl"))
                response = ai_council.cancel_response(task["task_id"])
                rows_after = len(ai_council.read_jsonl(root / "tasks.jsonl"))
                latest = ai_council.get_latest_task(task["task_id"])

        terminate.assert_not_called()
        self.assertIn("Cancel pominięty", response)
        self.assertEqual(rows_before, rows_after)
        self.assertEqual(latest["status"], "completed")

    def test_cancel_is_idempotent_after_first_cancel(self):
        with temp_dir() as tmp:
            root = Path(tmp)
            with patch.object(ai_council, "TASKS_FILE", root / "tasks.jsonl"), patch.object(
                ai_council, "BACKGROUND_JOBS_FILE", root / "background_jobs.jsonl"
            ), patch.object(ai_council, "LOG_DIR", root / "logs"), patch.object(
                ai_council, "AUDIT_LOG", root / "logs" / "audit.jsonl"
            ), patch.object(ai_council, "terminate_pid", return_value=(True, "killed")) as terminate:
                task = ai_council.create_task("flow", status="running_background", command="/flow", operators=["claude-flow"])
                ai_council.update_task_status(task["task_id"], "running_background", "worker", worker_pid=7777)
                first = ai_council.cancel_response(task["task_id"])
                rows_after_first = len(ai_council.read_jsonl(root / "tasks.jsonl"))
                second = ai_council.cancel_response(task["task_id"])
                rows_after_second = len(ai_council.read_jsonl(root / "tasks.jsonl"))

        self.assertIn("Cancel zapisany", first)
        self.assertIn("Cancel pominięty", second)
        self.assertEqual(rows_after_first, rows_after_second)
        terminate.assert_called_once_with(7777)

    def test_telegram_send_message_chunks_long_text_without_loss(self):
        long_text = ("a" * 3990 + "\n") + ("b" * 3990 + "\n") + ("c" * 1200)
        with patch.object(ai_council, "request_json", return_value={"ok": True}) as request_json:
            sent = ai_council.telegram_send_message("553", long_text)

        self.assertTrue(sent)
        payloads = [call.kwargs["payload"] for call in request_json.call_args_list]
        self.assertGreaterEqual(len(payloads), 3)
        self.assertEqual("".join(payload["text"] for payload in payloads), long_text)
        self.assertTrue(all(len(payload["text"]) <= 4000 for payload in payloads))

    def test_reconcile_background_jobs_marks_missing_worker_failed(self):
        with temp_dir() as tmp:
            root = Path(tmp)
            with patch.object(ai_council, "TASKS_FILE", root / "tasks.jsonl"), patch.object(
                ai_council, "BACKGROUND_JOBS_FILE", root / "background_jobs.jsonl"
            ), patch.object(ai_council, "LOG_DIR", root / "logs"), patch.object(
                ai_council, "AUDIT_LOG", root / "logs" / "audit.jsonl"
            ), patch.object(ai_council, "pid_is_running", return_value=False):
                task = ai_council.create_task("flow", status="running_background", command="/flow", operators=["claude-flow"])
                ai_council.update_task_status(task["task_id"], "running_background", "worker", worker_pid=9911)
                reconciled = ai_council.reconcile_background_jobs()
                latest = ai_council.get_latest_task(task["task_id"])

        self.assertEqual(len(reconciled), 1)
        self.assertEqual(latest["status"], "failed")
        self.assertIn("orphaned_on_restart", latest["note"])

    def test_reconcile_background_jobs_keeps_live_worker_running(self):
        with temp_dir() as tmp:
            root = Path(tmp)
            with patch.object(ai_council, "TASKS_FILE", root / "tasks.jsonl"), patch.object(
                ai_council, "BACKGROUND_JOBS_FILE", root / "background_jobs.jsonl"
            ), patch.object(ai_council, "LOG_DIR", root / "logs"), patch.object(
                ai_council, "AUDIT_LOG", root / "logs" / "audit.jsonl"
            ), patch.object(ai_council, "pid_is_running", return_value=True):
                task = ai_council.create_task("flow", status="running_background", command="/flow", operators=["claude-flow"])
                ai_council.update_task_status(task["task_id"], "running_background", "worker", worker_pid=9911)
                reconciled = ai_council.reconcile_background_jobs()
                latest = ai_council.get_latest_task(task["task_id"])

        self.assertEqual(reconciled, [])
        self.assertEqual(latest["status"], "running_background")

    def test_background_direct_operator_summary_contains_real_response(self):
        route = {"command": "codex_default", "operators": ["codex"], "prompt": "Działasz?"}
        with patch.object(ai_council, "codex_response", return_value="[Codex]\nTak, działam."):
            result = ai_council.execute_route_for_background(route, chat_id="", task_id="task-1")

        self.assertIn("Tak, działam.", result["summary"])
        self.assertIn("Details: /details task-1", result["summary"])

    def test_background_worker_sends_final_without_duplicate_running_message(self):
        with temp_dir() as tmp:
            root = Path(tmp)
            with patch.object(ai_council, "STATE_DIR", root / "state"), patch.object(
                ai_council, "TASKS_FILE", root / "state" / "tasks.jsonl"
            ), patch.object(ai_council, "BACKGROUND_JOBS_FILE", root / "state" / "background_jobs.jsonl"), patch.object(
                ai_council, "BACKGROUND_JOB_SPECS_DIR", root / "state" / "background_job_specs"
            ), patch.object(ai_council, "ARTIFACTS_DIR", root / "artifacts"), patch.object(
                ai_council, "ARTIFACT_INDEX_FILE", root / "state" / "artifact_index.jsonl"
            ), patch.object(ai_council, "MEMORY_DB", root / "memory.sqlite"), patch.object(
                ai_council, "LOG_DIR", root / "logs"
            ), patch.object(ai_council, "AUDIT_LOG", root / "logs" / "audit.jsonl"), patch.object(
                ai_council, "codex_response", return_value="[Codex]\nTak, działam."
            ), patch.object(ai_council, "telegram_send_message_with_markup", return_value=True) as send:
                task = ai_council.create_task("Działasz?", status="running_background", command="codex_default", operators=["codex"])
                task_id = task["task_id"]
                route = {"command": "codex_default", "operators": ["codex"], "prompt": "Działasz?", "task_id": task_id}
                ai_council.save_background_job_spec(route, "553", task_id, send_progress=True)
                code = ai_council.run_background_job(task_id)

        self.assertEqual(code, 0)
        self.assertEqual(send.call_count, 1)
        sent_text = send.call_args.args[1]
        sent_markup = send.call_args.args[2]
        self.assertNotIn("RUNNING: worker działa", sent_text)
        self.assertIn("Tak, działam.", sent_text)
        callback_data = [
            button["callback_data"]
            for row in sent_markup["inline_keyboard"]
            for button in row
        ]
        self.assertIn(f"details:{task_id}", callback_data)
        self.assertIn(f"facts:{task_id}", callback_data)
        self.assertIn(f"next:{task_id}", callback_data)

    def test_telegram_media_from_message_picks_largest_photo(self):
        message = {
            "caption": "screenshot do analizy",
            "photo": [
                {"file_id": "small", "file_unique_id": "u-small", "file_size": 10, "width": 90, "height": 90},
                {"file_id": "large", "file_unique_id": "u-large", "file_size": 100, "width": 1280, "height": 900},
            ],
        }

        media = ai_council.telegram_media_from_message(message)

        self.assertEqual(media["kind"], "photo")
        self.assertEqual(media["file_id"], "large")
        self.assertEqual(media["caption"], "screenshot do analizy")

    def test_capture_telegram_media_message_saves_artifact(self):
        def fake_download(file_path, target, timeout=60):
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(b"hello")
            return True, str(target)

        message = {
            "message_id": 42,
            "caption": "plik do taska",
            "document": {
                "file_id": "file-1",
                "file_unique_id": "unique-1",
                "file_name": "brief.txt",
                "mime_type": "text/plain",
                "file_size": 5,
            },
        }
        with temp_dir() as tmp:
            root = Path(tmp)
            with patch.object(ai_council, "TASKS_FILE", root / "state" / "tasks.jsonl"), patch.object(
                ai_council, "ARTIFACTS_DIR", root / "artifacts"
            ), patch.object(ai_council, "ARTIFACT_INDEX_FILE", root / "state" / "artifact_index.jsonl"), patch.object(
                ai_council, "MEMORY_DB", root / "state" / "memory.sqlite"
            ), patch.object(ai_council, "LOG_DIR", root / "logs"), patch.object(
                ai_council, "AUDIT_LOG", root / "logs" / "audit.jsonl"
            ), patch.object(
                ai_council, "telegram_get_file_info", return_value={"ok": True, "result": {"file_path": "documents/brief.txt"}}
            ), patch.object(ai_council, "telegram_download_file", side_effect=fake_download), patch.object(
                ai_council, "start_background_job", return_value="[AI Council] derived-start"
            ):
                response, task = ai_council.capture_telegram_media_message(message, chat_id="553", update_id=100)
                latest = ai_council.get_latest_task(task["task_id"])
                artifact = ai_council.get_latest_task_artifact(task["task_id"])
                media_files = list((root / "artifacts" / task["task_id"] / "media").glob("*"))
                metadata = json.loads((root / "artifacts" / task["task_id"] / "media.json").read_text(encoding="utf-8"))
                report_exists = Path(artifact["report_path"]).exists()
                media_content = media_files[0].read_bytes()

        self.assertIn("Details:", response)
        self.assertEqual(latest["status"], "completed")
        self.assertTrue(report_exists)
        self.assertEqual(len(media_files), 1)
        self.assertEqual(media_content, b"hello")
        self.assertEqual(metadata["analysis"]["status"], "text_extracted")
        self.assertIn("hello", metadata["analysis"]["text"])
        self.assertIn("derived_intent", metadata)

    def test_media_intent_transcript_starts_background_route(self):
        with temp_dir() as tmp:
            root = Path(tmp)
            parent = {"task_id": "task-parent"}
            with patch.object(ai_council, "TASKS_FILE", root / "state" / "tasks.jsonl"), patch.object(
                ai_council, "BACKGROUND_JOBS_FILE", root / "state" / "background_jobs.jsonl"
            ), patch.object(ai_council, "BACKGROUND_JOB_SPECS_DIR", root / "state" / "background_job_specs"), patch.object(
                ai_council, "LOG_DIR", root / "logs"
            ), patch.object(ai_council, "AUDIT_LOG", root / "logs" / "audit.jsonl"), patch.object(
                ai_council, "ARTIFACTS_DIR", root / "artifacts"
            ), patch.object(
                ai_council, "start_background_job", return_value="[AI Council] child started"
            ) as start:
                result = ai_council.run_media_derived_route("uruchom flow zrób plan", "553", parent)
                child = ai_council.latest_tasks(limit=1)[0]

        self.assertEqual(result["status"], "running_background")
        self.assertEqual(result["command"], "/flow")
        self.assertEqual(child["source"], "telegram_media_intent")
        start.assert_called_once()

    def test_media_intent_side_effect_creates_pending_action(self):
        with temp_dir() as tmp:
            root = Path(tmp)
            workspaces = root / "workspaces"
            parent = {"task_id": "task-parent"}
            with patch.object(ai_council, "TASKS_FILE", root / "state" / "tasks.jsonl"), patch.object(
                ai_council, "ACTIONS_FILE", root / "state" / "actions.jsonl"
            ), patch.object(ai_council, "WORKSPACES_DIR", workspaces), patch.object(
                ai_council, "MEMORY_DB", root / "state" / "memory.sqlite"
            ), patch.object(ai_council, "LOG_DIR", root / "logs"), patch.object(
                ai_council, "AUDIT_LOG", root / "logs" / "audit.jsonl"
            ):
                result = ai_council.run_media_derived_route("/write shared/from-voice.txt = hello", "553", parent)
                child = ai_council.latest_tasks(limit=1)[0]
                action = ai_council.latest_by_id(root / "state" / "actions.jsonl", "action_id", limit=1)[0]

        self.assertEqual(result["status"], "waiting_approval")
        self.assertEqual(child["status"], "waiting_approval")
        self.assertEqual(action["status"], "pending")
        self.assertFalse((workspaces / "shared" / "from-voice.txt").exists())

    def test_shortcut_authorized_requires_matching_token(self):
        def fake_cfg(key, default=""):
            if key == "AI_COUNCIL_SHORTCUT_TOKEN":
                return "secret-token"
            return default

        with patch.object(ai_council, "cfg", side_effect=fake_cfg):
            ok, reason = ai_council.shortcut_authorized({"X-AI-Council-Token": "secret-token"})
            bad_ok, bad_reason = ai_council.shortcut_authorized({"X-AI-Council-Token": "wrong"})

        self.assertTrue(ok)
        self.assertEqual(reason, "authorized")
        self.assertFalse(bad_ok)
        self.assertEqual(bad_reason, "invalid_token")

    def test_shortcut_text_payload_starts_background_task(self):
        with temp_dir() as tmp:
            root = Path(tmp)
            with patch.object(ai_council, "TASKS_FILE", root / "state" / "tasks.jsonl"), patch.object(
                ai_council, "BACKGROUND_JOBS_FILE", root / "state" / "background_jobs.jsonl"
            ), patch.object(ai_council, "BACKGROUND_JOB_SPECS_DIR", root / "state" / "background_job_specs"), patch.object(
                ai_council, "LOG_DIR", root / "logs"
            ), patch.object(ai_council, "AUDIT_LOG", root / "logs" / "audit.jsonl"), patch.object(
                ai_council, "start_background_job", return_value="[AI Council] shortcut child started"
            ) as start:
                result = ai_council.process_shortcut_payload(
                    {"text": "uruchom flow zrób plan", "send_telegram": False},
                    remote_addr="127.0.0.1",
                )
                task = ai_council.get_latest_task(result["task_id"])

        self.assertTrue(result["ok"])
        self.assertEqual(result["status"], "running_background")
        self.assertEqual(result["command"], "/flow")
        self.assertEqual(task["source"], "iphone_shortcut")
        start.assert_called_once()

    def test_shortcut_media_payload_saves_capture_and_routes_intent(self):
        media_text = "uruchom flow zrób plan z tego pliku"
        payload = {
            "filename": "note.txt",
            "mime_type": "text/plain",
            "media_base64": base64.b64encode(media_text.encode("utf-8")).decode("ascii"),
            "send_telegram": False,
        }
        with temp_dir() as tmp:
            root = Path(tmp)
            with patch.object(ai_council, "TASKS_FILE", root / "state" / "tasks.jsonl"), patch.object(
                ai_council, "BACKGROUND_JOBS_FILE", root / "state" / "background_jobs.jsonl"
            ), patch.object(ai_council, "BACKGROUND_JOB_SPECS_DIR", root / "state" / "background_job_specs"), patch.object(
                ai_council, "ARTIFACTS_DIR", root / "artifacts"
            ), patch.object(ai_council, "ARTIFACT_INDEX_FILE", root / "state" / "artifact_index.jsonl"), patch.object(
                ai_council, "MEMORY_DB", root / "memory.sqlite"
            ), patch.object(ai_council, "LOG_DIR", root / "logs"), patch.object(
                ai_council, "AUDIT_LOG", root / "logs" / "audit.jsonl"
            ), patch.object(
                ai_council, "start_background_job", return_value="[AI Council] shortcut media child started"
            ) as start:
                result = ai_council.process_shortcut_payload(payload, remote_addr="127.0.0.1")
                parent = ai_council.get_latest_task(result["task_id"])
                artifact = ai_council.get_latest_task_artifact(result["task_id"])
                metadata = json.loads((root / "artifacts" / result["task_id"] / "media.json").read_text(encoding="utf-8"))
                report_exists = Path(artifact["report_path"]).exists()

        self.assertTrue(result["ok"])
        self.assertEqual(result["status"], "completed")
        self.assertEqual(parent["source"], "iphone_shortcut_media")
        self.assertEqual(metadata["analysis"]["status"], "text_extracted")
        self.assertEqual(result["derived"]["status"], "running_background")
        self.assertIn("Details:", result["response"])
        self.assertTrue(report_exists)
        start.assert_called_once()

    def test_grok_image_analysis_sends_data_url(self):
        def fake_cfg(key, default=""):
            values = {
                "XAI_API_KEY": "xai-test-key",
                "AI_COUNCIL_GROK_VISION_MODEL": "grok-test",
                "AI_COUNCIL_MEDIA_ANALYSIS_MAX_BYTES": "5000000",
                "AI_COUNCIL_MEDIA_ANALYSIS_MAX_CHARS": "500",
            }
            return values.get(key, default)

        with temp_dir() as tmp:
            root = Path(tmp)
            image = root / "screen.jpg"
            image.write_bytes(b"fakejpg")
            with patch.object(ai_council, "COSTS_FILE", root / "costs.jsonl"), patch.object(
                ai_council, "cfg", side_effect=fake_cfg
            ), patch.object(
                ai_council,
                "request_json",
                return_value={"choices": [{"message": {"content": "Widzę tekst na ekranie."}}]},
            ) as request_json:
                response = ai_council.grok_image_analysis(image, caption="test", task_id="task-img")

        self.assertIn("Widzę tekst", response)
        payload = request_json.call_args.kwargs["payload"]
        image_url = payload["messages"][1]["content"][1]["image_url"]["url"]
        self.assertTrue(image_url.startswith("data:image/jpeg;base64,"))

    def test_audio_media_analysis_is_transcription_pending(self):
        with temp_dir() as tmp:
            root = Path(tmp)
            audio = root / "voice.ogg"
            audio.write_bytes(b"audio")
            with patch.object(ai_council, "xai_stt_transcribe", return_value={"status": "transcribed", "provider": "xai_stt", "text": "Cześć Bartek", "summary": "Cześć Bartek"}):
                analysis = ai_council.analyze_downloaded_media(
                    {
                        "task_id": "task-audio",
                        "local_path": str(audio),
                        "media": {"kind": "voice", "mime_type": "audio/ogg"},
                    }
                )

        self.assertEqual(analysis["status"], "transcribed")
        self.assertIn("Bartek", analysis["text"])

    def test_xai_stt_transcribe_builds_multipart_request(self):
        def fake_cfg(key, default=""):
            values = {
                "XAI_API_KEY": "xai-test-key",
                "AI_COUNCIL_STT_URL": "https://api.x.ai/v1/stt",
                "AI_COUNCIL_STT_LANGUAGE": "pl",
                "AI_COUNCIL_STT_FORMAT": "true",
                "AI_COUNCIL_STT_KEYTERMS": "Bartek,Codex",
                "AI_COUNCIL_STT_MAX_BYTES": "1000",
                "AI_COUNCIL_STT_MAX_CHARS": "500",
            }
            return values.get(key, default)

        with temp_dir() as tmp:
            root = Path(tmp)
            audio = root / "voice.ogg"
            audio.write_bytes(b"audio")
            with patch.object(ai_council, "COSTS_FILE", root / "costs.jsonl"), patch.object(
                ai_council, "cfg", side_effect=fake_cfg
            ), patch.object(
                ai_council, "request_multipart_json", return_value={"text": "Transkrypt głosówki."}
            ) as request_multipart:
                result = ai_council.xai_stt_transcribe(audio, mime_type="audio/ogg", task_id="task-stt")

        self.assertEqual(result["status"], "transcribed")
        self.assertIn("Transkrypt", result["text"])
        kwargs = request_multipart.call_args.kwargs
        self.assertEqual(kwargs["file_field"], "file")
        self.assertEqual(kwargs["mime_type"], "audio/ogg")
        self.assertIn(("format", "true"), kwargs["fields"])
        self.assertIn(("language", "pl"), kwargs["fields"])
        self.assertIn(("keyterm", "Bartek"), kwargs["fields"])

    def test_xai_stt_transcribe_reports_missing_key(self):
        with temp_dir() as tmp:
            root = Path(tmp)
            audio = root / "voice.ogg"
            audio.write_bytes(b"audio")
            with patch.object(ai_council, "COSTS_FILE", root / "costs.jsonl"), patch.object(
                ai_council, "cfg", return_value=""
            ):
                result = ai_council.xai_stt_transcribe(audio, mime_type="audio/ogg", task_id="task-stt")

        self.assertEqual(result["status"], "transcription_unavailable")

    def test_request_multipart_json_puts_file_after_fields(self):
        class FakeResponse:
            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return False

            def read(self):
                return b'{"text":"ok"}'

        captured = {}

        def fake_urlopen(req, timeout=180):
            captured["body"] = req.data
            captured["content_type"] = req.headers.get("Content-type") or req.headers.get("Content-Type")
            return FakeResponse()

        with temp_dir() as tmp:
            root = Path(tmp)
            audio = root / "voice.ogg"
            audio.write_bytes(b"audio")
            with patch("ai_council.urlopen", side_effect=fake_urlopen):
                data = ai_council.request_multipart_json(
                    "https://api.x.ai/v1/stt",
                    headers={"Authorization": "Bearer test"},
                    fields=[("format", "true"), ("language", "pl")],
                    file_field="file",
                    file_path=audio,
                    mime_type="audio/ogg",
                )

        body = captured["body"]
        self.assertEqual(data["text"], "ok")
        self.assertIn("multipart/form-data", captured["content_type"])
        self.assertLess(body.index(b'name="format"'), body.index(b'name="file"'))
        self.assertIn(b"audio", body)

    def test_audio_media_analysis_is_unavailable_without_key(self):
        with temp_dir() as tmp:
            root = Path(tmp)
            audio = root / "voice.ogg"
            audio.write_bytes(b"audio")
            with patch.object(ai_council, "COSTS_FILE", root / "costs.jsonl"), patch.object(
                ai_council, "cfg", return_value=""
            ):
                analysis = ai_council.analyze_downloaded_media(
                {
                    "task_id": "task-audio",
                    "local_path": str(audio),
                    "media": {"kind": "voice", "mime_type": "audio/ogg"},
                }
            )

        self.assertEqual(analysis["status"], "transcription_unavailable")

    def test_health_response_is_available_without_network_calls(self):
        with temp_dir() as tmp:
            root = Path(tmp)
            with patch.object(ai_council, "STATE_DIR", root / "state"), patch.object(
                ai_council, "TASKS_FILE", root / "state" / "tasks.jsonl"
            ), patch.object(ai_council, "COSTS_FILE", root / "state" / "costs.jsonl"), patch.object(
                ai_council, "OFFSET_FILE", root / "state" / "telegram_offset"
            ), patch.object(ai_council, "LOG_DIR", root / "logs"), patch.object(
                ai_council, "AUDIT_LOG", root / "logs" / "audit.jsonl"
            ), patch.object(ai_council, "ARTIFACTS_DIR", root / "artifacts"), patch.object(
                ai_council, "REPORTS_DIR", root / "reports"
            ), patch.object(ai_council, "operator_binary_status", return_value={"codex": {"configured": True}}):
                response = ai_council.build_response({"command": "/health", "operators": ["host"], "prompt": ""})

        self.assertIn("[Council] Health", response)
        self.assertIn("codex: OK", response)

    def test_goal_response_exposes_poke_parity_gap(self):
        with temp_dir() as tmp:
            root = Path(tmp)
            with patch.object(ai_council, "ERRORS_FILE", root / "state" / "errors.jsonl"), patch.object(
                ai_council, "ERRORS_DIR", root / "errors"
            ), patch.object(ai_council, "IMPROVEMENTS_FILE", root / "state" / "improvements.jsonl"), patch.object(
                ai_council, "LOG_DIR", root / "logs"
            ), patch.object(ai_council, "AUDIT_LOG", root / "logs" / "audit.jsonl"), patch.object(
                ai_council, "WORKSPACES_DIR", root / "workspaces"
            ), patch.object(ai_council, "ARTIFACTS_DIR", root / "artifacts"), patch.object(
                ai_council, "REPORTS_DIR", root / "reports"
            ), patch.object(ai_council, "RECIPES_DIR", root / "recipes"), patch.object(
                ai_council, "BACKGROUND_JOB_SPECS_DIR", root / "state" / "background_job_specs"
            ):
                response = ai_council.build_response({"command": "/goal", "operators": ["host"], "prompt": ""})

        self.assertIn("Goal: Bartek Agent OS", response)
        self.assertIn("NIE jest ukończony", response)
        self.assertIn("Brakuje do Poke-level", response)

    def test_selftest_response_is_available_without_model_calls(self):
        with temp_dir() as tmp:
            root = Path(tmp)
            with patch.object(ai_council, "STATE_DIR", root / "state"), patch.object(
                ai_council, "TASKS_FILE", root / "state" / "tasks.jsonl"
            ), patch.object(ai_council, "ARTIFACTS_DIR", root / "artifacts"), patch.object(
                ai_council, "WORKSPACES_DIR", root / "workspaces"
            ), patch.object(ai_council, "LOG_DIR", root / "logs"), patch.object(
                ai_council, "AUDIT_LOG", root / "logs" / "audit.jsonl"
            ), patch.object(ai_council, "operator_binary_status", return_value={"codex": {"configured": True}}), patch.object(
                ai_council, "cfg", return_value=""
            ):
                response = ai_council.build_response({"command": "/selftest", "operators": ["host"], "prompt": ""})

        self.assertIn("[Council] Selftest", response)
        self.assertIn("operators: codex:OK", response)
        self.assertIn("live_telegram:", response)

    def test_task_artifact_details_facts_and_next(self):
        with temp_dir() as tmp:
            root = Path(tmp)
            task_id = "task-20260606-000000-art"
            route = {"command": "/council", "operators": ["codex", "claude", "grok"], "prompt": "plan"}
            result = {
                "decision": "wdrażać L2.5",
                "facts": ["background działa", "artifact index zapisany", "cancel ma PID"],
                "dispute": "scope creep kontra mały sprint",
                "next_actions": ["testy", "deploy"],
                "ask_user": "potwierdź deploy",
                "raw_output": "pełny raport",
                "report": "# Raport\npełny raport",
            }
            with patch.object(ai_council, "ARTIFACTS_DIR", root / "artifacts"), patch.object(
                ai_council, "ARTIFACT_INDEX_FILE", root / "state" / "artifact_index.jsonl"
            ), patch.object(ai_council, "MEMORY_DB", root / "memory.sqlite"), patch.object(
                ai_council, "LOG_DIR", root / "logs"
            ), patch.object(ai_council, "AUDIT_LOG", root / "logs" / "audit.jsonl"), patch.object(
                ai_council, "STATE_DIR", root / "state"
            ), patch.object(ai_council, "BACKGROUND_JOB_SPECS_DIR", root / "state" / "background_job_specs"):
                artifact = ai_council.save_task_artifacts(task_id, route, result)
                details = ai_council.details_response(task_id)
                facts = ai_council.facts_response(task_id)
                next_text = ai_council.next_response(task_id)
                report_exists = Path(artifact["report_path"]).exists()

        self.assertTrue(report_exists)
        self.assertIn("wdrażać L2.5", details)
        self.assertIn("background działa", facts)
        self.assertIn("deploy", next_text)

    def test_structured_council_result_uses_all_operators_and_summary_template(self):
        with temp_dir() as tmp:
            root = Path(tmp)
            with patch.object(ai_council, "MEMORY_DB", root / "memory.sqlite"), patch.object(
                ai_council, "LOG_DIR", root / "logs"
            ), patch.object(ai_council, "AUDIT_LOG", root / "logs" / "audit.jsonl"), patch.object(
                ai_council, "claude_response", return_value="[Claude]\nplan: background jobs"
            ), patch.object(ai_council, "grok_response", return_value="[Grok]\nfakt: long polling nie może blokować"), patch.object(
                ai_council, "codex_response", return_value="[Codex]\nfeasibility: subprocess worker"
            ):
                result = ai_council.build_structured_council_result("zbuduj council", task_id="task-1")

        self.assertIn("Claude propose", result["report"])
        self.assertIn("Grok research/red-team", result["report"])
        self.assertIn("Codex feasibility", result["report"])
        self.assertIn("DECYZJA:", result["summary"])
        self.assertIn("FAKTY:", result["summary"])
        self.assertIn("Details: /details task-1", result["summary"])

    def test_fallback_council_synthesis_derives_from_operator_outputs(self):
        result = ai_council.fallback_council_synthesis(
            "zbuduj Poke-like Council",
            claude="[Claude]\nPlan: dodać rozmowę i pamięć wątku.",
            grok="[Grok]\nRyzyko: bez proaktywności to nadal zwykły bot.",
            codex="[Codex]\nPatch: wdrożyć realną syntezę hosta i test regresyjny.",
            task_id="task-1",
        )

        self.assertIn("Patch: wdrożyć realną syntezę", result["decision"])
        self.assertIn("Ryzyko: bez proaktywności", result["facts"][0])
        self.assertIn("Grok:", result["dispute"])
        self.assertIn("Claude:", result["dispute"])
        self.assertIn("Codex:", result["dispute"])
        self.assertIn("Patch: wdrożyć realną syntezę", result["next_actions"][1])

    def test_council_host_synthesis_uses_json_judge(self):
        def fake_cfg(key, default=""):
            values = {
                "XAI_API_KEY": "xai-test",
                "AI_COUNCIL_COUNCIL_HOST_SYNTHESIS": "true",
            }
            return values.get(key, default)

        judge_json = json.dumps(
            {
                "decision": "Wdrożyć Front Brain jako pierwszy brak Poke-like.",
                "facts": ["bot ma routowanie", "brakuje proaktywności", "Council musi syntetyzować głosy"],
                "dispute": "Grok ostrzega przed scope creep, Claude proponuje plan, Codex zawęża patch.",
                "next_actions": ["dodać test host synthesis"],
                "ask_user": "Potwierdź deploy.",
            },
            ensure_ascii=False,
        )
        with patch.object(ai_council, "cfg", side_effect=fake_cfg), patch.object(
            ai_council, "grok_route_response", return_value=judge_json
        ) as judge:
            result = ai_council.council_host_synthesis(
                "zbuduj Poke-like Council",
                "Host brief",
                "Claude: plan",
                "Grok: ryzyka",
                "Codex: patch",
                task_id="task-1",
            )

        judge.assert_called_once()
        self.assertEqual(result["synthesis_source"], "llm_host")
        self.assertEqual(result["decision"], "Wdrożyć Front Brain jako pierwszy brak Poke-like.")
        self.assertIn("/details task-1", "\n".join(result["next_actions"]))
        self.assertIn("Council musi syntetyzować głosy", result["facts"])

    def test_structured_council_result_uses_host_synthesis_decision(self):
        synthesis = {
            "decision": "Najpierw naprawić rozmowę jak Poke, potem proaktywność.",
            "facts": ["front operator działa", "brakuje watchers", "brakuje integracji"],
            "dispute": "Scope kontra minimalny patch.",
            "next_actions": ["wdrożyć L4.7", "/details task-1"],
            "ask_user": "Kontynuować L4.7?",
            "synthesis_source": "test_host",
        }
        with temp_dir() as tmp:
            root = Path(tmp)
            with patch.object(ai_council, "MEMORY_DB", root / "memory.sqlite"), patch.object(
                ai_council, "LOG_DIR", root / "logs"
            ), patch.object(ai_council, "AUDIT_LOG", root / "logs" / "audit.jsonl"), patch.object(
                ai_council, "claude_response", return_value="[Claude]\nplan: watchers"
            ), patch.object(ai_council, "grok_response", return_value="[Grok]\nryzyko: brak źródeł"), patch.object(
                ai_council, "codex_response", return_value="[Codex]\npatch: L4.7"
            ), patch.object(ai_council, "council_host_synthesis", return_value=synthesis):
                result = ai_council.build_structured_council_result("zbuduj council", task_id="task-1")

        self.assertEqual(result["decision"], synthesis["decision"])
        self.assertIn("Najpierw naprawić rozmowę jak Poke", result["summary"])
        self.assertIn("Synthesis source: test_host", result["report"])


if __name__ == "__main__":
    unittest.main()
