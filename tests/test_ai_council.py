import base64
import contextlib
import io
import json
import os
import re
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
        self.assertEqual(markup["inline_keyboard"][1][0]["callback_data"], "edit:act-20260606-120000-abcdef")

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

    def test_poke_gap_reply_markup_has_action_cards(self):
        markup = ai_council.response_reply_markup("[Council] Poke Gap L4.99\nDECYZJA: x")
        callback_data = [
            button["callback_data"]
            for row in markup["inline_keyboard"]
            for button in row
        ]

        self.assertEqual(callback_data, ["host:agent", "host:improve-next", "host:poke-research", "host:health"])

    def test_callback_approve_routes_to_approve_response(self):
        with patch.object(ai_council, "approve_response", return_value="[Council] Approved: act-1") as approve:
            response, status = ai_council.handle_callback_query({"data": "approve:act-1"})

        approve.assert_called_once_with("act-1")
        self.assertEqual(status, "approved")
        self.assertIn("Approved", response)

    def test_callback_edit_returns_safe_edit_instruction(self):
        response, status = ai_council.handle_callback_query({"data": "edit:act-1"})

        self.assertEqual(status, "edit")
        self.assertIn("poprawioną intencję", response.lower())

    def test_host_callback_routes_action_cards(self):
        callback = {"data": "host:agent", "message": {"chat": {"id": "553"}}}
        with patch.object(ai_council, "agent_response", return_value="[Council] Agent") as agent:
            response, status = ai_council.handle_callback_query(callback)

        agent.assert_called_once_with("", chat_id="553")
        self.assertEqual(status, "host_agent")
        self.assertIn("Agent", response)

    def test_host_improve_callback_uses_existing_backlog_or_planner(self):
        callback = {"data": "host:improve-next", "message": {"chat": {"id": "553"}}}
        with patch.object(ai_council, "open_improvements", return_value=[{"improvement_id": "imp-1"}]), patch.object(
            ai_council, "improvements_response", return_value="[Council] Improvement"
        ) as improvements:
            response, status = ai_council.handle_callback_query(callback)

        improvements.assert_called_once_with("next")
        self.assertEqual(status, "host_improve_next")
        self.assertIn("Improvement", response)

        with patch.object(ai_council, "open_improvements", return_value=[]), patch.object(
            ai_council, "action_planner_response", return_value="[Council] Action Planner"
        ) as planner:
            response, status = ai_council.handle_callback_query(callback)

        planner.assert_called_once()
        self.assertEqual(planner.call_args.kwargs["chat_id"], "553")
        self.assertEqual(status, "host_improve_next_planner")
        self.assertIn("Action Planner", response)

    def test_host_poke_research_callback_uses_action_planner(self):
        callback = {"data": "host:poke-research", "message": {"chat": {"id": "553"}}}
        with patch.object(ai_council, "action_planner_response", return_value="[Council] Action Planner") as planner:
            response, status = ai_council.handle_callback_query(callback)

        planner.assert_called_once()
        self.assertEqual(planner.call_args.kwargs["chat_id"], "553")
        self.assertIn("Poke parity", planner.call_args.args[0])
        self.assertEqual(status, "host_poke_research")
        self.assertIn("Action Planner", response)

    def test_host_health_and_unknown_callbacks(self):
        with patch.object(ai_council, "health_response", return_value="[Council] Health") as health:
            response, status = ai_council.handle_callback_query({"data": "host:health"})

        health.assert_called_once_with()
        self.assertEqual(status, "host_health")
        self.assertIn("Health", response)

        response, status = ai_council.handle_callback_query({"data": "host:missing"})

        self.assertEqual(status, "unknown_host_action")
        self.assertIn("Nieznany host action", response)

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

    def test_control_pause_blocks_due_recipes_without_marking_window(self):
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
                ai_council, "CONTROL_FILE", root / "state" / "control.json"
            ), patch.object(ai_council, "LOG_DIR", root / "logs"), patch.object(
                ai_council, "AUDIT_LOG", root / "logs" / "audit.jsonl"
            ), patch.object(ai_council, "default_recipes", return_value=recipe), patch.object(
                ai_council, "cfg", side_effect=fake_cfg
            ), patch.object(ai_council, "start_background_job", return_value="[AI Council] task-test") as start:
                ai_council.control_response("pause scheduler test")
                now = datetime(2026, 6, 6, 12, 0, tzinfo=timezone.utc)
                started = ai_council.run_due_recipes(send=False, now=now)
                runs = ai_council.read_jsonl(root / "state" / "recipe_runs.jsonl")

        self.assertEqual(started, 0)
        self.assertEqual(runs, [])
        self.assertEqual(start.call_count, 0)

    def test_default_autonomous_loop_recipes_exist(self):
        recipes = ai_council.default_recipes()

        self.assertIn("error_audit_twice_daily", recipes)
        self.assertIn("feature_evolution_loop", recipes)
        self.assertIn("gmail_context_brief", recipes)
        self.assertIn("calendar_context_brief", recipes)
        self.assertIn("drive_context_brief", recipes)
        error_recipe = recipes["error_audit_twice_daily"]
        feature_recipe = recipes["feature_evolution_loop"]

        self.assertTrue(error_recipe["enabled"])
        self.assertTrue(error_recipe["capture_improvement"])
        self.assertTrue(error_recipe["planner_selectable"])
        self.assertEqual(error_recipe["trigger"]["cron"], "0 9,21 * * *")
        self.assertTrue(any("{previous}" in step.get("prompt", "") for step in error_recipe["steps"]))
        self.assertTrue(feature_recipe["enabled"])
        self.assertTrue(feature_recipe["capture_improvement"])
        self.assertTrue(feature_recipe["planner_selectable"])
        self.assertEqual(feature_recipe["trigger"]["cron"], "15 10 * * *")
        self.assertTrue(any(step["command"] == "@xresearch" for step in feature_recipe["steps"]))
        self.assertTrue(any("{previous}" in step.get("prompt", "") for step in feature_recipe["steps"]))
        self.assertEqual(recipes["gmail_context_brief"]["source_connectors"], ["gmail"])
        self.assertTrue(any(step["prompt"].startswith("sync gmail") for step in recipes["gmail_context_brief"]["steps"]))
        self.assertTrue(recipes["drive_context_brief"]["planner_selectable"])

    def test_recipe_prompt_can_use_previous_step_output(self):
        prompt = ai_council.render_recipe_step_prompt("input={input}\nprevious={previous}", "temat", "wynik groka")

        self.assertIn("input=temat", prompt)
        self.assertIn("previous=wynik groka", prompt)

    def test_claude_flow_uses_opus_48_without_default_budget_cap(self):
        completed = subprocess.CompletedProcess(args=["claude"], returncode=0, stdout="FLOW OK", stderr="")

        with temp_dir() as tmp:
            root = Path(tmp)
            with patch.object(ai_council, "COSTS_FILE", root / "state" / "costs.jsonl"), patch.object(
                ai_council, "LOG_DIR", root / "logs"
            ), patch.object(ai_council, "AUDIT_LOG", root / "logs" / "audit.jsonl"), patch.object(
                ai_council, "command_path", return_value="claude"
            ), patch.object(ai_council, "memory_context_for_prompt", return_value=""), patch.object(
                ai_council, "OPENCLAW_EXPORT", Path("/missing-openclaw")
            ), patch.object(ai_council, "WORKSPACES_DIR", Path("/missing-workspaces")), patch(
                "ai_council.subprocess.run", return_value=completed
            ) as run:
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
        self.assertIn("Poke Gap L4.39", response)
        self.assertIn("DECYZJA: masz rację", response)
        self.assertIn("CO JEST NIE TAK", response)
        self.assertIn("CO ROBIĘ TERAZ", response)
        self.assertIn("CZEGO BRAKUJE DO POKE", response)
        self.assertIn("NEXT:", response)
        self.assertIn("TWOJA WIADOMOŚĆ:", response)
        self.assertIn("improvement=imp-", response)
        self.assertNotIn("Gotowe:", response)
        self.assertNotIn("/goal", response)
        self.assertLess(len(response), 1300)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["source"], "poke_gap")

    def test_short_greeting_has_operator_style_response(self):
        with patch.object(ai_council, "poke_chat_llm_response", return_value=None):
            response = ai_council.build_response(ai_council.route_text("hej"))

        self.assertIn("Jestem", response)
        self.assertIn("Bezpieczne", response)
        self.assertNotIn("Najlepszy następny krok", response)

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

        self.assertIn("Poke Gap L4.39", gap)
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
            ), patch.object(ai_council, "CONVERSATIONS_FILE", root / "state" / "conversations.jsonl"), patch.object(
                ai_council, "poke_chat_llm_response", return_value=None
            ), contextlib.redirect_stdout(stdout):
                ai_council.respond_dry("hej", chat_id="553")
                rows = ai_council.read_jsonl(root / "logs" / "audit.jsonl")

        output = stdout.getvalue()
        self.assertIn("[Council] Jestem", output)
        self.assertIn('"command": "/chat"', output)
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

        self.assertIn("Autonomous loops L4.18", response)
        self.assertIn("error_audit_twice_daily", response)
        self.assertIn("feature_evolution_loop", response)
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

        self.assertIn("[Council]", response)
        request_json.assert_not_called()

    def test_poke_chat_llm_gate_allows_followups_and_long_value_prompts(self):
        def fake_cfg(key, default=""):
            values = {
                "XAI_API_KEY": "xai-test",
                "AI_COUNCIL_POKE_CHAT_USE_GROK": "true",
                "AI_COUNCIL_POKE_CHAT_LLM_MIN_CHARS": "90",
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
        self.assertIn("Jestem", turns[1]["text"])
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
    def test_agent_inbox_prioritizes_safe_followup_and_run_starts_it(self):
        with temp_dir() as tmp:
            root = Path(tmp)
            with patch.object(ai_council, "TASKS_FILE", root / "state" / "tasks.jsonl"), patch.object(
                ai_council, "ACTIONS_FILE", root / "state" / "actions.jsonl"
            ), patch.object(ai_council, "IMPROVEMENTS_FILE", root / "state" / "improvements.jsonl"), patch.object(
                ai_council, "NUDGES_FILE", root / "state" / "nudges.jsonl"
            ), patch.object(ai_council, "ERRORS_FILE", root / "state" / "errors.jsonl"), patch.object(
                ai_council, "COSTS_FILE", root / "state" / "costs.jsonl"
            ), patch.object(ai_council, "LOG_DIR", root / "logs"), patch.object(
                ai_council, "AUDIT_LOG", root / "logs" / "audit.jsonl"
            ), patch.object(ai_council, "WORKSPACES_DIR", root / "workspaces"), patch.object(
                ai_council, "ARTIFACTS_DIR", root / "artifacts"
            ), patch.object(ai_council, "REPORTS_DIR", root / "reports"), patch.object(
                ai_council, "BACKGROUND_JOBS_FILE", root / "state" / "background_jobs.jsonl"
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
                inbox = ai_council.agent_response()
                response = ai_council.agent_response(f"run {action['action_id']}", chat_id="553")
                latest = ai_council.get_latest_action(action["action_id"])

        self.assertIn("Agent Inbox L4.27", inbox)
        self.assertIn(f"RUN: /agent run {action['action_id']}", inbox)
        self.assertIn("follow-up started", response)
        self.assertEqual(latest["status"], "executed")
        start.assert_called_once()

    def test_agent_run_open_improvement_starts_apply_background_task(self):
        with temp_dir() as tmp:
            root = Path(tmp)
            with patch.object(ai_council, "TASKS_FILE", root / "state" / "tasks.jsonl"), patch.object(
                ai_council, "ACTIONS_FILE", root / "state" / "actions.jsonl"
            ), patch.object(ai_council, "IMPROVEMENTS_FILE", root / "state" / "improvements.jsonl"), patch.object(
                ai_council, "NUDGES_FILE", root / "state" / "nudges.jsonl"
            ), patch.object(ai_council, "ERRORS_FILE", root / "state" / "errors.jsonl"), patch.object(
                ai_council, "COSTS_FILE", root / "state" / "costs.jsonl"
            ), patch.object(ai_council, "LOG_DIR", root / "logs"), patch.object(
                ai_council, "AUDIT_LOG", root / "logs" / "audit.jsonl"
            ), patch.object(ai_council, "WORKSPACES_DIR", root / "workspaces"), patch.object(
                ai_council, "ARTIFACTS_DIR", root / "artifacts"
            ), patch.object(ai_council, "REPORTS_DIR", root / "reports"), patch.object(
                ai_council, "BACKGROUND_JOBS_FILE", root / "state" / "background_jobs.jsonl"
            ), patch.object(ai_council, "BACKGROUND_JOB_SPECS_DIR", root / "state" / "background_job_specs"), patch.object(
                ai_council, "start_background_job", return_value="[AI Council] improvement started"
            ) as start:
                improvement = ai_council.create_improvement(
                    source="test_loop",
                    title="Dodaj agent inbox",
                    summary="Potrzebny jeden next action.",
                    priority="P1",
                )
                inbox = ai_council.agent_response()
                response = ai_council.agent_response(f"run {improvement['improvement_id']}", chat_id="553")
                task = ai_council.latest_tasks(limit=1)[0]

        self.assertIn("Dodaj agent inbox", inbox)
        self.assertIn("improvement started", response)
        self.assertEqual(task["command"], "/improve")
        self.assertIn(improvement["improvement_id"], task["prompt"])
        start.assert_called_once()

    def test_agent_runtime_prompt_does_not_trigger_run_parser(self):
        with temp_dir() as tmp:
            root = Path(tmp)
            with patch.object(ai_council, "TASKS_FILE", root / "state" / "tasks.jsonl"), patch.object(
                ai_council, "ACTIONS_FILE", root / "state" / "actions.jsonl"
            ), patch.object(ai_council, "IMPROVEMENTS_FILE", root / "state" / "improvements.jsonl"), patch.object(
                ai_council, "NUDGES_FILE", root / "state" / "nudges.jsonl"
            ), patch.object(ai_council, "ERRORS_FILE", root / "state" / "errors.jsonl"), patch.object(
                ai_council, "COSTS_FILE", root / "state" / "costs.jsonl"
            ), patch.object(ai_council, "start_background_job", return_value="should not start") as start:
                response = ai_council.agent_response("runtime status", chat_id="553")

        self.assertIn("Agent Inbox L4.27", response)
        self.assertEqual(start.call_count, 0)

    def test_proactive_scan_creates_improvement_nudge(self):
        with temp_dir() as tmp:
            root = Path(tmp)
            with patch.object(ai_council, "IMPROVEMENTS_FILE", root / "state" / "improvements.jsonl"), patch.object(
                ai_council, "NUDGES_FILE", root / "state" / "nudges.jsonl"
            ), patch.object(ai_council, "ERRORS_FILE", root / "state" / "errors.jsonl"), patch.object(
                ai_council, "ACTIONS_FILE", root / "state" / "actions.jsonl"
            ), patch.object(ai_council, "TASKS_FILE", root / "state" / "tasks.jsonl"), patch.object(
                ai_council, "COSTS_FILE", root / "state" / "costs.jsonl"
            ):
                improvement = ai_council.create_improvement(
                    source="feature_evolution_loop",
                    title="Następna funkcja",
                    summary="Zaplanuj kolejny sprint.",
                    priority="P2",
                )
                created = ai_council.run_proactive_scan(send=False)
                rows = ai_council.read_jsonl(root / "state" / "nudges.jsonl")

        self.assertEqual(created, 1)
        self.assertEqual(rows[0]["kind"], "improvement")
        self.assertIn(improvement["improvement_id"], rows[0]["next_action"])

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
            ), patch.object(ai_council, "IMPROVEMENTS_FILE", root / "state" / "improvements.jsonl"
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
            ), patch.object(ai_council, "IMPROVEMENTS_FILE", root / "state" / "improvements.jsonl"
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
        self.assertIn("/improve apply", " ".join(result["next_actions"]))
        self.assertEqual(result["followup"]["command"], "/improve")

    def test_save_recipe_artifact_creates_followup_action(self):
        with temp_dir() as tmp:
            root = Path(tmp)
            task_id = "task-20260607-000000-follow"
            route = {"command": "/recipe", "operators": ["host"], "prompt": "run loop"}
            result = {
                "decision": "recipe done",
                "facts": ["candidate ready"],
                "dispute": "",
                "next_actions": ["Follow-up: /improve apply imp-1"],
                "ask_user": "approve follow-up",
                "raw_output": "recipe output",
                "report": "recipe report",
                "followup": {
                    "command": "/improve",
                    "prompt": "apply imp-1",
                    "intent": "Plan improvement imp-1",
                    "risk": "R0",
                    "reason": "test",
                },
            }
            with patch.object(ai_council, "ARTIFACTS_DIR", root / "artifacts"), patch.object(
                ai_council, "ARTIFACT_INDEX_FILE", root / "state" / "artifact_index.jsonl"
            ), patch.object(ai_council, "ACTIONS_FILE", root / "state" / "actions.jsonl"), patch.object(
                ai_council, "MEMORY_DB", root / "memory.sqlite"
            ), patch.object(ai_council, "LOG_DIR", root / "logs"), patch.object(
                ai_council, "AUDIT_LOG", root / "logs" / "audit.jsonl"
            ), patch.object(ai_council, "WORKSPACES_DIR", root / "workspaces"), patch.object(
                ai_council, "REPORTS_DIR", root / "reports"
            ), patch.object(ai_council, "ERRORS_DIR", root / "errors"), patch.object(
                ai_council, "BACKGROUND_JOB_SPECS_DIR", root / "state" / "background_job_specs"
            ):
                artifact = ai_council.save_task_artifacts(task_id, route, result)
                actions = ai_council.read_jsonl(root / "state" / "actions.jsonl")
                next_text = ai_council.next_response(task_id)
                followups = ai_council.followups_response()

        self.assertEqual(actions[0]["type"], "followup_proposal")
        self.assertEqual(actions[0]["status"], "pending")
        self.assertEqual(actions[0]["payload"]["source_task_id"], task_id)
        self.assertEqual(actions[0]["payload"]["recommended_command"], "/improve")
        self.assertEqual(artifact["followup_action_id"], actions[0]["action_id"])
        self.assertIn(f"/approve {actions[0]['action_id']}", next_text)
        self.assertIn(actions[0]["action_id"], followups)

    def test_save_recipe_artifact_respects_followup_chain_depth_limit(self):
        with temp_dir() as tmp:
            root = Path(tmp)
            task_id = "task-20260607-000000-depth"
            route = {
                "command": "/recipe",
                "operators": ["host"],
                "prompt": "run loop",
                "followup_chain_id": "chain-test",
                "followup_depth": 1,
            }
            result = {
                "decision": "recipe done",
                "facts": ["candidate ready"],
                "next_actions": ["Follow-up: /improve apply imp-1"],
                "raw_output": "recipe output",
                "followup": {
                    "command": "/improve",
                    "prompt": "apply imp-1",
                    "intent": "Plan improvement imp-1",
                    "risk": "R0",
                },
            }
            with patch.dict(os.environ, {"AI_COUNCIL_FOLLOWUP_MAX_DEPTH": "1"}), patch.object(
                ai_council, "ARTIFACTS_DIR", root / "artifacts"
            ), patch.object(ai_council, "ARTIFACT_INDEX_FILE", root / "state" / "artifact_index.jsonl"), patch.object(
                ai_council, "ACTIONS_FILE", root / "state" / "actions.jsonl"
            ), patch.object(ai_council, "MEMORY_DB", root / "memory.sqlite"), patch.object(
                ai_council, "LOG_DIR", root / "logs"
            ), patch.object(ai_council, "AUDIT_LOG", root / "logs" / "audit.jsonl"), patch.object(
                ai_council, "WORKSPACES_DIR", root / "workspaces"
            ), patch.object(ai_council, "REPORTS_DIR", root / "reports"), patch.object(
                ai_council, "ERRORS_DIR", root / "errors"
            ), patch.object(ai_council, "BACKGROUND_JOB_SPECS_DIR", root / "state" / "background_job_specs"):
                artifact = ai_council.save_task_artifacts(task_id, route, result)
                actions = ai_council.read_jsonl(root / "state" / "actions.jsonl")
                next_text = ai_council.next_response(task_id)

        self.assertEqual(actions, [])
        self.assertEqual(artifact["followup_action_id"], "")
        self.assertNotIn("Follow-up ready", next_text)

    def test_recipe_policy_blocks_write_step(self):
        recipe = {
            "bad": {
                "name": "bad",
                "description": "unsafe",
                "enabled": True,
                "trigger": {"type": "manual"},
                "steps": [{"command": "/write", "prompt": "shared/x.txt = no"}],
            }
        }
        with temp_dir() as tmp:
            root = Path(tmp)
            with patch.object(ai_council, "RECIPES_DIR", root / "recipes"), patch.object(
                ai_council, "ERRORS_FILE", root / "state" / "errors.jsonl"
            ), patch.object(ai_council, "ERRORS_DIR", root / "errors"), patch.object(
                ai_council, "LOG_DIR", root / "logs"
            ), patch.object(ai_council, "AUDIT_LOG", root / "logs" / "audit.jsonl"), patch.object(
                ai_council, "WORKSPACES_DIR", root / "workspaces"
            ), patch.object(ai_council, "ARTIFACTS_DIR", root / "artifacts"), patch.object(
                ai_council, "REPORTS_DIR", root / "reports"
            ), patch.object(ai_council, "BACKGROUND_JOB_SPECS_DIR", root / "state" / "background_job_specs"), patch.object(
                ai_council, "default_recipes", return_value=recipe
            ), patch.object(ai_council, "build_response", return_value="should not run") as build_response:
                result = ai_council.run_recipe_background("run bad", task_id="task-bad")
                errors = ai_council.read_jsonl(root / "state" / "errors.jsonl")

        self.assertEqual(result["status"], "blocked")
        self.assertIn("/write", result["raw_output"])
        self.assertEqual(build_response.call_count, 0)
        self.assertEqual(errors[0]["context"], "recipe_step_policy")

    def test_recipe_policy_blocks_unknown_connector_action(self):
        allowed, reason = ai_council.recipe_step_is_allowed({"command": "/connector", "prompt": "send gmail hello"})

        self.assertFalse(allowed)
        self.assertIn("not read-only", reason)

    def test_recipe_policy_allows_project_memory_reads_only(self):
        allowed_search, _ = ai_council.recipe_step_is_allowed({"command": "/project-memory", "prompt": "search Poke"})
        allowed_context, _ = ai_council.recipe_step_is_allowed({"command": "/project-memory", "prompt": "context Poke"})
        allowed_rebuild, reason = ai_council.recipe_step_is_allowed({"command": "/project-memory", "prompt": "rebuild"})

        self.assertTrue(allowed_search)
        self.assertTrue(allowed_context)
        self.assertFalse(allowed_rebuild)
        self.assertIn("not read-only", reason)


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

    def test_project_memory_rebuild_is_source_grounded_and_idempotent(self):
        with temp_dir() as tmp:
            root = Path(tmp)
            report = root / "artifacts" / "task-1" / "report.md"
            report.parent.mkdir(parents=True)
            report.write_text("Raport Poke memory spine.", encoding="utf-8")
            artifact = {
                "task_id": "task-1",
                "decision": "Wdrożyć memory spine dla Poke parity.",
                "facts": ["Poke wymaga długiej pamięci", "Artifacts są source-backed"],
                "next_actions": ["Dodać auto recall"],
                "report_path": str(report),
            }
            with patch.object(ai_council, "MEMORY_DB", root / "memory.sqlite"), patch.object(
                ai_council, "ARTIFACT_INDEX_FILE", root / "state" / "artifact_index.jsonl"
            ), patch.object(ai_council, "LOG_DIR", root / "logs"), patch.object(
                ai_council, "AUDIT_LOG", root / "logs" / "audit.jsonl"
            ):
                ai_council.append_jsonl(root / "state" / "artifact_index.jsonl", artifact)
                first = ai_council.project_memory_rebuild()
                created_before = {row["entry_id"]: row["created_at"] for row in ai_council.project_memory_rows("task-1")}
                second = ai_council.project_memory_rebuild()
                rows = ai_council.project_memory_rows("task-1")
                created_after = {row["entry_id"]: row["created_at"] for row in rows}
                response = ai_council.project_memory_response("search Poke")
                context = ai_council.memory_context_for_prompt("Poke parity")

        self.assertEqual(len(first), 3)
        self.assertEqual(len(second), 3)
        self.assertEqual(created_before, created_after)
        self.assertTrue(ai_council.project_memory_entry_id("task-1", "decision").startswith("pmem-"))
        self.assertEqual(len(rows), 3)
        self.assertTrue(all(row["entry_id"].startswith("pmem-") for row in rows))
        self.assertIn("Source:", rows[0]["value"])
        self.assertIn("/details task-1", response)
        self.assertIn("Project memory:", context)
        self.assertIn("source=", context)

    def test_save_task_artifacts_writes_project_memory_spine(self):
        with temp_dir() as tmp:
            root = Path(tmp)
            task_id = "task-20260607-memory"
            route = {"command": "/council", "operators": ["codex", "claude", "grok"], "prompt": "memory spine"}
            result = {
                "decision": "Zapisać memory spine.",
                "facts": ["Project memory jest source-backed"],
                "next_actions": ["Użyć auto recall"],
                "raw_output": "raw",
                "report": "report",
            }
            with patch.object(ai_council, "ARTIFACTS_DIR", root / "artifacts"), patch.object(
                ai_council, "ARTIFACT_INDEX_FILE", root / "state" / "artifact_index.jsonl"
            ), patch.object(ai_council, "MEMORY_DB", root / "memory.sqlite"), patch.object(
                ai_council, "LOG_DIR", root / "logs"
            ), patch.object(ai_council, "AUDIT_LOG", root / "logs" / "audit.jsonl"), patch.object(
                ai_council, "BACKGROUND_JOB_SPECS_DIR", root / "state" / "background_job_specs"
            ):
                ai_council.save_task_artifacts(task_id, route, result)
                rows = ai_council.project_memory_rows("source-backed")

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["task_id"], task_id)
        self.assertIn("Source:", rows[0]["value"])

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

        self.assertIn("Connectors L4.41", response)
        self.assertIn("Drive document executor", response)
        self.assertIn("github | auth_required", response)
        self.assertIn("Ready:", response)
        self.assertIn("/connector check", response)
        self.assertIn("/connector sync", response)
        self.assertIn("/connector draft", response)

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

    def test_connector_sync_gmail_requires_google_oauth_config(self):
        with temp_dir() as tmp:
            root = Path(tmp)
            with patch.object(ai_council, "CONNECTOR_INDEX_DB", root / "state" / "connector_index.sqlite"), patch.object(
                ai_council, "STATE_DIR", root / "state"
            ), patch.object(ai_council, "cfg", side_effect=lambda key, default="": default):
                response = ai_council.connector_response("sync gmail recipes")

        self.assertIn("Connector sync `gmail`", response)
        self.assertIn("status: oauth_required", response)
        self.assertIn("/connector auth gmail", response)

    def test_connector_sync_error_points_to_auth_not_brief(self):
        with patch.object(ai_council, "google_sync_connector", return_value=("oauth_error: http_400 invalid_scope", 0)), patch.object(
            ai_council, "connector_index_count", return_value=0
        ):
            response = ai_council.connector_response("sync gmail recipes")

        self.assertIn("status: oauth_error: http_400 invalid_scope", response)
        self.assertIn("/connector auth gmail", response)
        self.assertIn("/errors recent 10", response)
        self.assertNotIn("/connector brief gmail recipes", response)

    def test_connector_sync_preserves_multi_word_query(self):
        with patch.object(ai_council, "google_sync_connector", return_value=("available", 0)) as sync, patch.object(
            ai_council, "connector_index_count", return_value=0
        ):
            response = ai_council.connector_response("sync drive Poke recipes")

        sync.assert_called_once_with("drive", query="Poke recipes")
        self.assertIn("Connector sync `drive`", response)

    def test_connector_sync_unsupported_does_not_suggest_brief(self):
        response = ai_council.connector_response("sync unknown Poke")

        self.assertIn("status: unsupported", response)
        self.assertIn("Obsługiwane OAuth sync", response)
        self.assertNotIn("/connector brief unknown", response)

    def test_google_sync_limit_is_capped(self):
        def fake_cfg(key, default=""):
            if key == "AI_COUNCIL_GOOGLE_SYNC_LIMIT":
                return "1000"
            if key == "AI_COUNCIL_GOOGLE_SYNC_LIMIT_MAX":
                return "50"
            return default

        with patch.object(ai_council, "cfg", side_effect=fake_cfg), patch.object(
            ai_council, "google_sync_gmail", return_value=("available", 0)
        ) as sync:
            ai_council.google_sync_connector("gmail", query="Poke")

        sync.assert_called_once_with("Poke", limit=50)

    def test_connector_sync_gmail_indexes_oauth_results(self):
        def fake_cfg(key, default=""):
            values = {
                "GOOGLE_CLIENT_ID": "client-id",
                "GOOGLE_CLIENT_SECRET": "client-secret",
                "GOOGLE_REFRESH_TOKEN": "refresh-token",
            }
            return values.get(key, default)

        request_calls = []

        def fake_request(url, **kwargs):
            request_calls.append((url, kwargs))
            if "gmail.googleapis.com/gmail/v1/users/me/messages?" in url:
                return {"messages": [{"id": "m1"}]}
            return {
                "id": "m1",
                "threadId": "t1",
                "snippet": "Poke recipes in email",
                "payload": {
                    "headers": [
                        {"name": "Subject", "value": "Poke Recipes"},
                        {"name": "From", "value": "bartek@example.com"},
                        {"name": "To", "value": "council@example.com"},
                        {"name": "Date", "value": "today"},
                    ]
                },
            }

        with temp_dir() as tmp:
            root = Path(tmp)
            with patch.object(ai_council, "CONNECTOR_INDEX_DB", root / "state" / "connector_index.sqlite"), patch.object(
                ai_council, "STATE_DIR", root / "state"
            ), patch.object(ai_council, "SOURCE_EXPORT_DEFAULTS", {
                "AI_COUNCIL_GMAIL_EXPORT_DIR": root / "sources" / "gmail",
                "AI_COUNCIL_CALENDAR_EXPORT_DIR": root / "sources" / "calendar",
                "AI_COUNCIL_DRIVE_EXPORT_DIR": root / "sources" / "drive",
            }), patch.object(ai_council, "cfg", side_effect=fake_cfg), patch.object(
                ai_council, "request_form_json", return_value={"access_token": "ya29-test"}
            ) as form_request, patch.object(ai_council, "request_json", side_effect=fake_request):
                response = ai_council.connector_response("sync gmail recipes")
                status, results = ai_council.source_search("gmail", "recipes", limit=3)

        form_request.assert_called_once()
        self.assertIn("synced_now: 1", response)
        self.assertNotIn("ya29-test", response)
        self.assertEqual(status, "available_index")
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["source"], "gmail:m1")
        self.assertIn("Poke Recipes", results[0]["title"])
        self.assertTrue(any(call[1]["headers"]["Authorization"] == "Bearer ya29-test" for call in request_calls))

    def test_connector_sync_calendar_indexes_oauth_results(self):
        def fake_cfg(key, default=""):
            values = {
                "GOOGLE_CLIENT_ID": "client-id",
                "GOOGLE_CLIENT_SECRET": "client-secret",
                "GOOGLE_REFRESH_TOKEN": "refresh-token",
            }
            return values.get(key, default)

        with temp_dir() as tmp:
            root = Path(tmp)
            with patch.object(ai_council, "CONNECTOR_INDEX_DB", root / "state" / "connector_index.sqlite"), patch.object(
                ai_council, "STATE_DIR", root / "state"
            ), patch.object(ai_council, "SOURCE_EXPORT_DEFAULTS", {
                "AI_COUNCIL_GMAIL_EXPORT_DIR": root / "sources" / "gmail",
                "AI_COUNCIL_CALENDAR_EXPORT_DIR": root / "sources" / "calendar",
                "AI_COUNCIL_DRIVE_EXPORT_DIR": root / "sources" / "drive",
            }), patch.object(ai_council, "cfg", side_effect=fake_cfg), patch.object(
                ai_council, "request_form_json", return_value={"access_token": "ya29-test"}
            ), patch.object(
                ai_council,
                "request_json",
                return_value={
                    "items": [
                        {
                            "id": "evt1",
                            "summary": "Poke planning meeting",
                            "start": {"dateTime": "2026-06-07T09:00:00Z"},
                            "end": {"dateTime": "2026-06-07T10:00:00Z"},
                            "location": "Telegram",
                            "description": "Discuss recipes",
                            "htmlLink": "https://calendar.google.com/event",
                        }
                    ]
                },
            ):
                response = ai_council.connector_response("sync calendar Poke")
                status, results = ai_council.source_search("calendar", "recipes", limit=3)

        self.assertIn("synced_now: 1", response)
        self.assertEqual(status, "available_index")
        self.assertEqual(results[0]["source"], "calendar:evt1")
        self.assertIn("Poke planning meeting", results[0]["title"])

    def test_connector_sync_drive_indexes_oauth_results(self):
        def fake_cfg(key, default=""):
            values = {
                "GOOGLE_CLIENT_ID": "client-id",
                "GOOGLE_CLIENT_SECRET": "client-secret",
                "GOOGLE_REFRESH_TOKEN": "refresh-token",
            }
            return values.get(key, default)

        with temp_dir() as tmp:
            root = Path(tmp)
            with patch.object(ai_council, "CONNECTOR_INDEX_DB", root / "state" / "connector_index.sqlite"), patch.object(
                ai_council, "STATE_DIR", root / "state"
            ), patch.object(ai_council, "SOURCE_EXPORT_DEFAULTS", {
                "AI_COUNCIL_GMAIL_EXPORT_DIR": root / "sources" / "gmail",
                "AI_COUNCIL_CALENDAR_EXPORT_DIR": root / "sources" / "calendar",
                "AI_COUNCIL_DRIVE_EXPORT_DIR": root / "sources" / "drive",
            }), patch.object(ai_council, "cfg", side_effect=fake_cfg), patch.object(
                ai_council, "request_form_json", return_value={"access_token": "ya29-test"}
            ), patch.object(
                ai_council,
                "request_json",
                return_value={
                    "files": [
                        {
                            "id": "file1",
                            "name": "Poke recipes doc",
                            "mimeType": "application/vnd.google-apps.document",
                            "webViewLink": "https://drive.google.com/file1",
                            "modifiedTime": "2026-06-07T10:00:00Z",
                            "description": "recipes and action planner",
                        }
                    ]
                },
            ):
                response = ai_council.connector_response("sync drive Poke")
                status, results = ai_council.source_search("drive", "action planner", limit=3)

        self.assertIn("synced_now: 1", response)
        self.assertEqual(status, "available_index")
        self.assertEqual(results[0]["source"], "drive:file1")
        self.assertIn("Poke recipes doc", results[0]["title"])

    def test_drive_query_escapes_backslash_and_single_quote(self):
        query = ai_council.drive_query(r"Poke\docs O'Brien")

        self.assertEqual(query, r"name contains 'Poke\\docs O\'Brien' and trashed = false")

    def test_utc_now_rfc3339_z_is_calendar_safe(self):
        value = ai_council.utc_now_rfc3339_z()

        self.assertTrue(value.endswith("Z"))
        self.assertNotIn("+00:00", value)
        self.assertNotIn(".", value)

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

    def test_connector_draft_creates_pending_integration_action(self):
        with temp_dir() as tmp:
            root = Path(tmp)
            with patch.object(ai_council, "ACTIONS_FILE", root / "state" / "actions.jsonl"), patch.object(
                ai_council, "LOG_DIR", root / "logs"
            ), patch.object(ai_council, "AUDIT_LOG", root / "logs" / "audit.jsonl"):
                response = ai_council.connector_response("draft gmail odpowiedz klientowi o statusie wdrożenia")
                action = ai_council.latest_by_id(root / "state" / "actions.jsonl", "action_id", limit=1)[0]
                drafts = ai_council.integration_drafts_response()
                detail = ai_council.integration_drafts_response(f"show {action['action_id']}")

        self.assertIn("Integration draft utworzony L4.28", response)
        self.assertEqual(action["type"], "integration_draft")
        self.assertEqual(action["status"], "pending")
        self.assertEqual(action["payload"]["connector"], "gmail")
        self.assertEqual(action["payload"]["draft_kind"], "email_draft")
        self.assertFalse(action["payload"]["external_write"])
        self.assertIn(action["action_id"], drafts)
        self.assertIn("Integration Draft", detail)
        self.assertIn("missing_fields:", detail)
        self.assertIn("policy: draft-only", detail)

    def test_connector_draft_risk_floors_at_r3_and_show_requires_id(self):
        with temp_dir() as tmp:
            root = Path(tmp)
            with patch.object(ai_council, "ACTIONS_FILE", root / "state" / "actions.jsonl"), patch.object(
                ai_council, "LOG_DIR", root / "logs"
            ), patch.object(ai_council, "AUDIT_LOG", root / "logs" / "audit.jsonl"):
                action = ai_council.create_integration_draft_action("gmail", "hello", risk="")
                missing = ai_council.integration_drafts_response("show")

        self.assertEqual(action["risk"], "R3")
        self.assertEqual(action["payload"]["risk_reason"], "external write/API/contact integration risk")
        self.assertIn("/drafts show <action_id>", missing)

    def test_integration_draft_execute_requires_approval_then_creates_pack(self):
        with temp_dir() as tmp:
            root = Path(tmp)
            with patch.object(ai_council, "ACTIONS_FILE", root / "state" / "actions.jsonl"), patch.object(
                ai_council, "ARTIFACTS_DIR", root / "artifacts"
            ), patch.object(ai_council, "MEMORY_DB", root / "state" / "memory.sqlite"), patch.object(
                ai_council, "LOG_DIR", root / "logs"
            ), patch.object(ai_council, "AUDIT_LOG", root / "logs" / "audit.jsonl"):
                action = ai_council.create_integration_draft_action("calendar", "umów spotkanie z zespołem jutro", risk="R3")
                blocked = ai_council.execute_response(action["action_id"])
                approved = ai_council.approve_response(action["action_id"])
                execute = ai_council.execute_response(action["action_id"])
                verified = ai_council.verify_response(action["action_id"])
                reexecute = ai_council.execute_response(action["action_id"])
                latest = ai_council.get_latest_action(action["action_id"])
                pack = (latest["payload"] or {}).get("execution_pack") or {}
                json_exists = Path(pack["json_path"]).exists()
                markdown_exists = Path(pack["markdown_path"]).exists()

        self.assertIn("wymaga najpierw /approve", blocked)
        self.assertIn("Approved integration draft checkpoint", approved)
        self.assertIn("Nie wykonałem external write", approved)
        self.assertIn("Integration execution pack created", execute)
        self.assertIn("external_write: false", execute)
        self.assertIn("OK", verified)
        self.assertIn("integration execution pack verified", verified)
        self.assertIn("already verified", reexecute)
        self.assertEqual(latest["status"], "verified")
        self.assertTrue(json_exists)
        self.assertTrue(markdown_exists)

    def test_integration_draft_verify_fails_when_pack_file_missing(self):
        with temp_dir() as tmp:
            root = Path(tmp)
            with patch.object(ai_council, "ACTIONS_FILE", root / "state" / "actions.jsonl"), patch.object(
                ai_council, "ARTIFACTS_DIR", root / "artifacts"
            ), patch.object(ai_council, "MEMORY_DB", root / "state" / "memory.sqlite"), patch.object(
                ai_council, "LOG_DIR", root / "logs"
            ), patch.object(ai_council, "AUDIT_LOG", root / "logs" / "audit.jsonl"):
                action = ai_council.create_integration_draft_action("github", "otwórz issue o L4.29 packach", risk="R3")
                ai_council.approve_response(action["action_id"])
                ai_council.execute_response(action["action_id"])
                latest = ai_council.get_latest_action(action["action_id"])
                pack = (latest["payload"] or {}).get("execution_pack") or {}
                Path(pack["json_path"]).unlink()
                verified = ai_council.verify_response(action["action_id"])
                latest = ai_council.get_latest_action(action["action_id"])

        self.assertIn("FAILED", verified)
        self.assertIn("integration execution pack missing files", verified)
        self.assertEqual(latest["status"], "verify_failed")

    def test_provider_plan_for_unverified_draft_writes_blocked_manifest(self):
        with temp_dir() as tmp:
            root = Path(tmp)
            with patch.object(ai_council, "ACTIONS_FILE", root / "state" / "actions.jsonl"), patch.object(
                ai_council, "ARTIFACTS_DIR", root / "artifacts"
            ), patch.object(ai_council, "MEMORY_DB", root / "state" / "memory.sqlite"), patch.object(
                ai_council, "LOG_DIR", root / "logs"
            ), patch.object(ai_council, "AUDIT_LOG", root / "logs" / "audit.jsonl"):
                action = ai_council.create_integration_draft_action("gmail", "napisz draft maila do klienta", risk="R3")
                response = ai_council.provider_response(f"plan {action['action_id']}")
                latest = ai_council.get_latest_action(action["action_id"])
                manifest = (latest["payload"] or {}).get("provider_manifest") or {}
                json_exists = Path(manifest["json_path"]).exists()
                markdown_exists = Path(manifest["markdown_path"]).exists()

        self.assertIn("Manifest L4.30", response)
        self.assertIn("blocked_not_verified", response)
        self.assertEqual(manifest["status"], "blocked_not_verified")
        self.assertFalse(manifest["external_write_performed"])
        self.assertTrue(json_exists)
        self.assertTrue(markdown_exists)

    def test_provider_manifest_after_verified_pack_is_verifiable_and_execute_blocked(self):
        with temp_dir() as tmp:
            root = Path(tmp)
            with patch.object(ai_council, "ACTIONS_FILE", root / "state" / "actions.jsonl"), patch.object(
                ai_council, "ARTIFACTS_DIR", root / "artifacts"
            ), patch.object(ai_council, "MEMORY_DB", root / "state" / "memory.sqlite"), patch.object(
                ai_council, "LOG_DIR", root / "logs"
            ), patch.object(ai_council, "AUDIT_LOG", root / "logs" / "audit.jsonl"), patch.object(
                ai_council, "google_oauth_configured", return_value=True
            ):
                action = ai_council.create_integration_draft_action("calendar", "umów spotkanie z zespołem jutro", risk="R3")
                ai_council.approve_response(action["action_id"])
                ai_council.execute_response(action["action_id"])
                ai_council.verify_response(action["action_id"])
                plan = ai_council.provider_response(f"plan {action['action_id']}")
                show = ai_council.provider_response(f"show {action['action_id']}")
                verify = ai_council.provider_response(f"verify {action['action_id']}")
                execute = ai_council.provider_response(f"execute {action['action_id']}")
                latest = ai_council.get_latest_action(action["action_id"])
                manifest = (latest["payload"] or {}).get("provider_manifest") or {}
                data = json.loads(Path(manifest["json_path"]).read_text(encoding="utf-8"))

        self.assertIn("blocked_missing_fields", plan)
        self.assertIn("missing_fields: attendees, start_time, end_time, timezone", show)
        self.assertIn("OK", verify)
        self.assertIn("provider manifest verified", verify)
        self.assertIn("Request: /provider request", execute)
        self.assertEqual(data["provider_operation"], "calendar.events.insert")
        self.assertFalse(data["external_write_performed"])
        self.assertEqual(data["write_gate"], "disabled_l4_30_manifest_only")

    def test_provider_verify_failure_is_recorded_in_action_history(self):
        with temp_dir() as tmp:
            root = Path(tmp)
            with patch.object(ai_council, "ACTIONS_FILE", root / "state" / "actions.jsonl"), patch.object(
                ai_council, "ARTIFACTS_DIR", root / "artifacts"
            ), patch.object(ai_council, "MEMORY_DB", root / "state" / "memory.sqlite"), patch.object(
                ai_council, "LOG_DIR", root / "logs"
            ), patch.object(ai_council, "AUDIT_LOG", root / "logs" / "audit.jsonl"):
                action = ai_council.create_integration_draft_action("github", "otwórz issue o L4.30 manifestach", risk="R3")
                ai_council.provider_response(f"plan {action['action_id']}")
                latest = ai_council.get_latest_action(action["action_id"])
                manifest = (latest["payload"] or {}).get("provider_manifest") or {}
                Path(manifest["json_path"]).unlink()
                failed = ai_council.provider_response(f"verify {action['action_id']}")
                latest = ai_council.get_latest_action(action["action_id"])

        self.assertIn("FAILED", failed)
        self.assertIn("provider manifest missing files", failed)
        self.assertEqual(latest["provider_manifest_verification_status"], "failed")

    def test_provider_write_request_requires_approval_confirm_and_stays_dry_run(self):
        with temp_dir() as tmp:
            root = Path(tmp)
            with patch.object(ai_council, "ACTIONS_FILE", root / "state" / "actions.jsonl"), patch.object(
                ai_council, "ARTIFACTS_DIR", root / "artifacts"
            ), patch.object(ai_council, "MEMORY_DB", root / "state" / "memory.sqlite"), patch.object(
                ai_council, "LOG_DIR", root / "logs"
            ), patch.object(ai_council, "AUDIT_LOG", root / "logs" / "audit.jsonl"), patch.object(
                ai_council, "google_oauth_configured", return_value=True
            ):
                action = ai_council.create_integration_draft_action("calendar", "umów spotkanie z zespołem jutro", risk="R3")
                ai_council.approve_response(action["action_id"])
                ai_council.execute_response(action["action_id"])
                ai_council.verify_response(action["action_id"])
                ready = ai_council.get_latest_action(action["action_id"])
                payload = {**(ready["payload"] or {})}
                payload["missing_fields"] = []
                payload["draft"] = {
                    "summary": "Spotkanie zespołu",
                    "start": "2026-06-08T10:00:00+02:00",
                    "end": "2026-06-08T10:30:00+02:00",
                    "attendees": ["team@example.com"],
                    "description": "Plan wdrożenia AI Council",
                }
                ai_council.append_jsonl(ai_council.ACTIONS_FILE, {**ready, "updated_at": ai_council.utc_now(), "payload": payload})
                ai_council.provider_response(f"plan {action['action_id']}")
                ai_council.provider_response(f"verify {action['action_id']}")
                request = ai_council.provider_response(f"request {action['action_id']}")
                request_id = re.search(r"id: (act-[A-Za-z0-9_.-]+)", request).group(1)
                request_action = ai_council.get_latest_action(request_id)
                token = (request_action["payload"] or {}).get("confirm_token")
                blocked_pending = ai_council.provider_response(f"execute {request_id} {token}")
                approved = ai_council.approve_response(request_id)
                wrong_token = ai_council.provider_response(f"execute {request_id} wrong")
                executed = ai_council.provider_response(f"execute {request_id} {token}")
                verified = ai_council.provider_response(f"verify {request_id}")
                latest = ai_council.get_latest_action(request_id)
                dry_run = (latest["payload"] or {}).get("provider_write_dry_run") or {}
                data = json.loads(Path(dry_run["json_path"]).read_text(encoding="utf-8"))

        self.assertIn("Pending provider write request", request)
        self.assertEqual(request_action["type"], "provider_write_request")
        self.assertIn("wymaga najpierw /approve", blocked_pending)
        self.assertIn("Approved provider write request checkpoint", approved)
        self.assertIn("wymagany confirm token", wrong_token)
        self.assertIn("Write gate L4.41", executed)
        self.assertIn("external_write_performed: false", executed)
        self.assertIn("OK", verified)
        self.assertIn("provider write request dry-run verified", verified)
        self.assertFalse(data["external_write_performed"])
        self.assertEqual(latest["status"], "verified")

    def test_provider_write_dedupe_key_is_stable_for_json_order(self):
        first = ai_council.provider_write_dedupe_key("github", "github.issues.create", {"title": "T", "body": "B", "labels": ["x"]})
        second = ai_council.provider_write_dedupe_key("github", "github.issues.create", {"labels": ["x"], "body": "B", "title": "T"})

        self.assertEqual(first, second)

    def test_provider_write_request_dedupe_blocks_duplicate_request_creation(self):
        with temp_dir() as tmp:
            root = Path(tmp)
            env = {"AI_COUNCIL_GITHUB_REPO": "Acoste616/AIagent", "GITHUB_TOKEN": "unit-token"}
            with patch.dict(os.environ, env, clear=False), patch.object(
                ai_council, "ACTIONS_FILE", root / "state" / "actions.jsonl"
            ), patch.object(ai_council, "ARTIFACTS_DIR", root / "artifacts"), patch.object(
                ai_council, "MEMORY_DB", root / "state" / "memory.sqlite"
            ), patch.object(ai_council, "LOG_DIR", root / "logs"), patch.object(
                ai_council, "AUDIT_LOG", root / "logs" / "audit.jsonl"
            ), patch.object(ai_council, "github_token", return_value="unit-token"):
                draft = {
                    "repo": "Acoste616/AIagent",
                    "title": "Dedupe request test",
                    "body": "Same provider body.",
                    "labels": ["ai-council"],
                }
                action = ai_council.create_integration_draft_action("github", "otwórz issue dedupe", risk="R3")
                ai_council.approve_response(action["action_id"])
                ai_council.execute_response(action["action_id"])
                ai_council.verify_response(action["action_id"])
                ready = ai_council.get_latest_action(action["action_id"])
                payload = {**(ready["payload"] or {}), "missing_fields": [], "draft": draft}
                ai_council.append_jsonl(ai_council.ACTIONS_FILE, {**ready, "updated_at": ai_council.utc_now(), "payload": payload})
                ai_council.provider_response(f"plan {action['action_id']}")
                ai_council.provider_response(f"verify {action['action_id']}")
                first_request = ai_council.provider_response(f"request {action['action_id']}")

                duplicate = ai_council.create_integration_draft_action("github", "otwórz issue dedupe duplicate", risk="R3")
                ai_council.approve_response(duplicate["action_id"])
                ai_council.execute_response(duplicate["action_id"])
                ai_council.verify_response(duplicate["action_id"])
                ready_duplicate = ai_council.get_latest_action(duplicate["action_id"])
                duplicate_payload = {**(ready_duplicate["payload"] or {}), "missing_fields": [], "draft": dict(draft)}
                ai_council.append_jsonl(ai_council.ACTIONS_FILE, {**ready_duplicate, "updated_at": ai_council.utc_now(), "payload": duplicate_payload})
                ai_council.provider_response(f"plan {duplicate['action_id']}")
                ai_council.provider_response(f"verify {duplicate['action_id']}")
                duplicate_request = ai_council.provider_response(f"request {duplicate['action_id']}")
                provider_requests = [row for row in ai_council.read_jsonl(ai_council.ACTIONS_FILE) if row.get("type") == "provider_write_request"]

        self.assertIn("Pending provider write request", first_request)
        self.assertIn("L4.38 dedupe", duplicate_request)
        self.assertIn("external_write_performed: false", duplicate_request)
        self.assertEqual(len(provider_requests), 1)

    def test_provider_write_request_dedupe_ignores_terminal_blocked_statuses(self):
        for terminal_status in ("write_blocked", "verify_failed"):
            with self.subTest(terminal_status=terminal_status), temp_dir() as tmp:
                root = Path(tmp)
                env = {"AI_COUNCIL_GITHUB_REPO": "Acoste616/AIagent", "GITHUB_TOKEN": "unit-token"}
                with patch.dict(os.environ, env, clear=False), patch.object(
                    ai_council, "ACTIONS_FILE", root / "state" / "actions.jsonl"
                ), patch.object(ai_council, "ARTIFACTS_DIR", root / "artifacts"), patch.object(
                    ai_council, "MEMORY_DB", root / "state" / "memory.sqlite"
                ), patch.object(ai_council, "LOG_DIR", root / "logs"), patch.object(
                    ai_council, "AUDIT_LOG", root / "logs" / "audit.jsonl"
                ), patch.object(ai_council, "github_token", return_value="unit-token"):
                    draft = {
                        "repo": "Acoste616/AIagent",
                        "title": "Dedupe terminal status test",
                        "body": "Same provider body.",
                        "labels": ["ai-council"],
                    }
                    action = ai_council.create_integration_draft_action("github", "otwórz issue terminal dedupe", risk="R3")
                    ai_council.approve_response(action["action_id"])
                    ai_council.execute_response(action["action_id"])
                    ai_council.verify_response(action["action_id"])
                    ready = ai_council.get_latest_action(action["action_id"])
                    payload = {**(ready["payload"] or {}), "missing_fields": [], "draft": draft}
                    ai_council.append_jsonl(ai_council.ACTIONS_FILE, {**ready, "updated_at": ai_council.utc_now(), "payload": payload})
                    ai_council.provider_response(f"plan {action['action_id']}")
                    ai_council.provider_response(f"verify {action['action_id']}")
                    first_request = ai_council.provider_response(f"request {action['action_id']}")
                    request_id = re.search(r"id: (act-[A-Za-z0-9_.-]+)", first_request).group(1)
                    request_action = ai_council.get_latest_action(request_id)
                    ai_council.append_jsonl(ai_council.ACTIONS_FILE, {**request_action, "status": terminal_status, "updated_at": ai_council.utc_now()})

                    duplicate = ai_council.create_integration_draft_action("github", "otwórz issue terminal dedupe duplicate", risk="R3")
                    ai_council.approve_response(duplicate["action_id"])
                    ai_council.execute_response(duplicate["action_id"])
                    ai_council.verify_response(duplicate["action_id"])
                    ready_duplicate = ai_council.get_latest_action(duplicate["action_id"])
                    duplicate_payload = {**(ready_duplicate["payload"] or {}), "missing_fields": [], "draft": dict(draft)}
                    ai_council.append_jsonl(ai_council.ACTIONS_FILE, {**ready_duplicate, "updated_at": ai_council.utc_now(), "payload": duplicate_payload})
                    ai_council.provider_response(f"plan {duplicate['action_id']}")
                    ai_council.provider_response(f"verify {duplicate['action_id']}")
                    duplicate_request = ai_council.provider_response(f"request {duplicate['action_id']}")
                    provider_request_ids = {
                        str(row.get("action_id") or "")
                        for row in ai_council.read_jsonl(ai_council.ACTIONS_FILE)
                        if row.get("type") == "provider_write_request"
                    }

                self.assertIn("Pending provider write request", duplicate_request)
                self.assertEqual(len(provider_request_ids), 2)

    def test_github_provider_write_request_executes_with_gates_and_verifies(self):
        captured: dict[str, object] = {}

        def fake_request_json(url: str, **kwargs):
            if "/search/issues?" in url:
                return {"items": []}
            captured["url"] = url
            captured["kwargs"] = kwargs
            return {
                "id": 123456,
                "number": 7,
                "html_url": "https://github.com/Acoste616/AIagent/issues/7",
                "url": "https://api.github.com/repos/Acoste616/AIagent/issues/7",
                "title": kwargs["payload"]["title"],
            }

        with temp_dir() as tmp:
            root = Path(tmp)
            env = {
                "AI_COUNCIL_PROVIDER_WRITE_ENABLED": "true",
                "AI_COUNCIL_GITHUB_ISSUE_WRITE_ENABLED": "true",
                "AI_COUNCIL_GITHUB_REPO": "Acoste616/AIagent",
                "GITHUB_TOKEN": "unit-token",
            }
            with patch.dict(os.environ, env, clear=False), patch.object(
                ai_council, "ACTIONS_FILE", root / "state" / "actions.jsonl"
            ), patch.object(ai_council, "ARTIFACTS_DIR", root / "artifacts"), patch.object(
                ai_council, "MEMORY_DB", root / "state" / "memory.sqlite"
            ), patch.object(ai_council, "LOG_DIR", root / "logs"), patch.object(
                ai_council, "AUDIT_LOG", root / "logs" / "audit.jsonl"
            ), patch.object(ai_council, "github_token", return_value="unit-token"), patch.object(
                ai_council, "request_json", side_effect=fake_request_json
            ) as request_json:
                action = ai_council.create_integration_draft_action("github", "otwórz issue o L4.32 executorze", risk="R3")
                ai_council.approve_response(action["action_id"])
                ai_council.execute_response(action["action_id"])
                ai_council.verify_response(action["action_id"])
                ready = ai_council.get_latest_action(action["action_id"])
                payload = {**(ready["payload"] or {})}
                payload["missing_fields"] = []
                payload["draft"] = {
                    "repo": "Acoste616/AIagent",
                    "title": "L4.32 executor test",
                    "body": "Verify provider executor flow.",
                    "labels": ["ai-council"],
                }
                ai_council.append_jsonl(ai_council.ACTIONS_FILE, {**ready, "updated_at": ai_council.utc_now(), "payload": payload})
                ai_council.provider_response(f"plan {action['action_id']}")
                ai_council.provider_response(f"verify {action['action_id']}")
                request = ai_council.provider_response(f"request {action['action_id']}")
                request_id = re.search(r"id: (act-[A-Za-z0-9_.-]+)", request).group(1)
                request_action = ai_council.get_latest_action(request_id)
                token = (request_action["payload"] or {}).get("confirm_token")
                ai_council.approve_response(request_id)
                executed = ai_council.provider_response(f"execute {request_id} {token}")
                executed_action = ai_council.get_latest_action(request_id)
                result = (executed_action["payload"] or {}).get("provider_write_result") or {}
                data = json.loads(Path(result["json_path"]).read_text(encoding="utf-8"))
                verified = ai_council.provider_response(f"verify {request_id}")
                latest = ai_council.get_latest_action(request_id)
                ai_council.append_jsonl(ai_council.ACTIONS_FILE, {**latest, "status": "verify_failed", "updated_at": ai_council.utc_now()})
                retry_after_verify_failed = ai_council.provider_response(f"execute {request_id} {token}")

        self.assertIn("GitHub issue executed L4.41", executed)
        self.assertIn("external_write_performed: true", executed)
        self.assertIn("https://github.com/Acoste616/AIagent/issues/7", executed)
        self.assertEqual(captured["url"], "https://api.github.com/repos/Acoste616/AIagent/issues")
        self.assertEqual(captured["kwargs"]["method"], "POST")
        self.assertEqual(captured["kwargs"]["payload"]["title"], "L4.32 executor test")
        self.assertEqual(captured["kwargs"]["payload"]["labels"], ["ai-council"])
        self.assertIn("Authorization", captured["kwargs"]["headers"])
        self.assertEqual(request_json.call_count, 2)
        self.assertTrue(data["external_write_performed"])
        self.assertEqual(data["provider_read_before_write"]["status"], "clear")
        self.assertEqual(data["provider_operation"], "github.issues.create")
        self.assertIn("provider write request result verified", verified)
        self.assertEqual(latest["status"], "verified")
        self.assertIn("wcześniejszy provider POST/result", retry_after_verify_failed)
        self.assertEqual(request_json.call_count, 2)

    def test_provider_write_dedupe_blocks_legacy_duplicate_before_network(self):
        def fake_request_json(url: str, **kwargs):
            if "/search/issues?" in url:
                return {"items": []}
            return {
                "id": 123456,
                "number": 8,
                "html_url": "https://github.com/Acoste616/AIagent/issues/8",
                "url": "https://api.github.com/repos/Acoste616/AIagent/issues/8",
                "title": kwargs["payload"]["title"],
            }

        with temp_dir() as tmp:
            root = Path(tmp)
            env = {
                "AI_COUNCIL_PROVIDER_WRITE_ENABLED": "true",
                "AI_COUNCIL_GITHUB_ISSUE_WRITE_ENABLED": "true",
                "AI_COUNCIL_GITHUB_REPO": "Acoste616/AIagent",
                "GITHUB_TOKEN": "unit-token",
            }
            with patch.dict(os.environ, env, clear=False), patch.object(
                ai_council, "ACTIONS_FILE", root / "state" / "actions.jsonl"
            ), patch.object(ai_council, "ARTIFACTS_DIR", root / "artifacts"), patch.object(
                ai_council, "MEMORY_DB", root / "state" / "memory.sqlite"
            ), patch.object(ai_council, "LOG_DIR", root / "logs"), patch.object(
                ai_council, "AUDIT_LOG", root / "logs" / "audit.jsonl"
            ), patch.object(ai_council, "github_token", return_value="unit-token"), patch.object(
                ai_council, "request_json", side_effect=fake_request_json
            ) as request_json:
                action = ai_council.create_integration_draft_action("github", "otwórz issue dedupe executor", risk="R3")
                ai_council.approve_response(action["action_id"])
                ai_council.execute_response(action["action_id"])
                ai_council.verify_response(action["action_id"])
                ready = ai_council.get_latest_action(action["action_id"])
                payload = {**(ready["payload"] or {})}
                payload["missing_fields"] = []
                payload["draft"] = {
                    "repo": "Acoste616/AIagent",
                    "title": "L4.38 executor dedupe test",
                    "body": "Verify duplicate provider executor flow.",
                    "labels": ["ai-council"],
                }
                ai_council.append_jsonl(ai_council.ACTIONS_FILE, {**ready, "updated_at": ai_council.utc_now(), "payload": payload})
                ai_council.provider_response(f"plan {action['action_id']}")
                ai_council.provider_response(f"verify {action['action_id']}")
                request = ai_council.provider_response(f"request {action['action_id']}")
                request_id = re.search(r"id: (act-[A-Za-z0-9_.-]+)", request).group(1)
                request_action = ai_council.get_latest_action(request_id)
                token = (request_action["payload"] or {}).get("confirm_token")
                ai_council.approve_response(request_id)
                first_execute = ai_council.provider_response(f"execute {request_id} {token}")

                legacy_payload = {**(request_action["payload"] or {}), "confirm_token": "dupetok"}
                legacy_payload.pop("dedupe_key", None)
                duplicate = ai_council.create_action(
                    "Legacy duplicate provider write request",
                    action_type="provider_write_request",
                    risk="R3",
                    payload=legacy_payload,
                )
                ai_council.approve_response(duplicate["action_id"])
                duplicate_execute = ai_council.provider_response(f"execute {duplicate['action_id']} dupetok")
                duplicate_latest = ai_council.get_latest_action(duplicate["action_id"])
                dry_run = (duplicate_latest["payload"] or {}).get("provider_write_dry_run") or {}
                dry_run_text = Path(dry_run["json_path"]).read_text(encoding="utf-8")

        self.assertIn("GitHub issue executed L4.41", first_execute)
        self.assertIn("Write gate L4.38 dedupe", duplicate_execute)
        self.assertIn("external_write_performed: false", duplicate_execute)
        self.assertEqual(duplicate_latest["status"], "write_blocked")
        self.assertTrue((duplicate_latest["payload"] or {}).get("provider_write_dedupe_conflict"))
        self.assertIn("L4.38 dedupe", dry_run_text)
        self.assertEqual(request_json.call_count, 2)

    def test_github_provider_write_failure_is_redacted_verified_and_not_retried(self):
        def fake_request_json(url: str, **kwargs):
            if "/search/issues?" in url:
                return {"items": []}
            return {
                "ok": False,
                "error": "http_422",
                "body_preview": f"validation failed for {kwargs['headers']['Authorization']}",
            }

        with temp_dir() as tmp:
            root = Path(tmp)
            env = {
                "AI_COUNCIL_PROVIDER_WRITE_ENABLED": "true",
                "AI_COUNCIL_GITHUB_ISSUE_WRITE_ENABLED": "true",
                "AI_COUNCIL_GITHUB_REPO": "Acoste616/AIagent",
                "GITHUB_TOKEN": "unit-token",
            }
            with patch.dict(os.environ, env, clear=False), patch.object(
                ai_council, "ACTIONS_FILE", root / "state" / "actions.jsonl"
            ), patch.object(ai_council, "ARTIFACTS_DIR", root / "artifacts"), patch.object(
                ai_council, "MEMORY_DB", root / "state" / "memory.sqlite"
            ), patch.object(ai_council, "LOG_DIR", root / "logs"), patch.object(
                ai_council, "AUDIT_LOG", root / "logs" / "audit.jsonl"
            ), patch.object(ai_council, "github_token", return_value="unit-token"), patch.object(
                ai_council, "request_json", side_effect=fake_request_json
            ) as request_json:
                action = ai_council.create_integration_draft_action("github", "otwórz issue z błędem API", risk="R3")
                ai_council.approve_response(action["action_id"])
                ai_council.execute_response(action["action_id"])
                ai_council.verify_response(action["action_id"])
                ready = ai_council.get_latest_action(action["action_id"])
                payload = {**(ready["payload"] or {})}
                payload["missing_fields"] = []
                payload["draft"] = {
                    "repo": "Acoste616/AIagent",
                    "title": "Failure branch test",
                    "body": "This should fail.",
                    "labels": [],
                }
                ai_council.append_jsonl(ai_council.ACTIONS_FILE, {**ready, "updated_at": ai_council.utc_now(), "payload": payload})
                ai_council.provider_response(f"plan {action['action_id']}")
                ai_council.provider_response(f"verify {action['action_id']}")
                request = ai_council.provider_response(f"request {action['action_id']}")
                request_id = re.search(r"id: (act-[A-Za-z0-9_.-]+)", request).group(1)
                token = (ai_council.get_latest_action(request_id)["payload"] or {}).get("confirm_token")
                ai_council.approve_response(request_id)
                failed = ai_council.provider_response(f"execute {request_id} {token}")
                failed_action = ai_council.get_latest_action(request_id)
                result = (failed_action["payload"] or {}).get("provider_write_result") or {}
                result_text = Path(result["json_path"]).read_text(encoding="utf-8")
                verified = ai_council.provider_response(f"verify {request_id}")
                retry = ai_council.provider_response(f"execute {request_id} {token}")

        self.assertIn("GitHub issue write failed L4.41", failed)
        self.assertIn("manual_check:", failed)
        self.assertIn("external_write_performed: false", failed)
        self.assertNotIn("unit-token", failed)
        self.assertNotIn("unit-token", result_text)
        self.assertIn("[redacted]", result_text)
        self.assertIn("provider write failed; check provider manually", verified)
        self.assertIn("wcześniejszy provider POST/result", retry)
        self.assertEqual(request_json.call_count, 2)

    def test_github_provider_write_blocks_too_long_title_before_network(self):
        with temp_dir() as tmp:
            root = Path(tmp)
            env = {
                "AI_COUNCIL_PROVIDER_WRITE_ENABLED": "true",
                "AI_COUNCIL_GITHUB_ISSUE_WRITE_ENABLED": "true",
                "AI_COUNCIL_GITHUB_REPO": "Acoste616/AIagent",
                "GITHUB_TOKEN": "unit-token",
            }
            with patch.dict(os.environ, env, clear=False), patch.object(
                ai_council, "ACTIONS_FILE", root / "state" / "actions.jsonl"
            ), patch.object(ai_council, "ARTIFACTS_DIR", root / "artifacts"), patch.object(
                ai_council, "MEMORY_DB", root / "state" / "memory.sqlite"
            ), patch.object(ai_council, "LOG_DIR", root / "logs"), patch.object(
                ai_council, "AUDIT_LOG", root / "logs" / "audit.jsonl"
            ), patch.object(ai_council, "github_token", return_value="unit-token"), patch.object(
                ai_council, "request_json", side_effect=AssertionError("provider API should not be called")
            ):
                action = ai_council.create_integration_draft_action("github", "otwórz issue z za długim tytułem", risk="R3")
                ai_council.approve_response(action["action_id"])
                ai_council.execute_response(action["action_id"])
                ai_council.verify_response(action["action_id"])
                ready = ai_council.get_latest_action(action["action_id"])
                payload = {**(ready["payload"] or {})}
                payload["missing_fields"] = []
                payload["draft"] = {
                    "repo": "Acoste616/AIagent",
                    "title": "T" * (ai_council.GITHUB_ISSUE_TITLE_LIMIT + 1),
                    "body": "Should be blocked locally.",
                    "labels": [],
                }
                ai_council.append_jsonl(ai_council.ACTIONS_FILE, {**ready, "updated_at": ai_council.utc_now(), "payload": payload})
                ai_council.provider_response(f"plan {action['action_id']}")
                ai_council.provider_response(f"verify {action['action_id']}")
                request = ai_council.provider_response(f"request {action['action_id']}")
                request_id = re.search(r"id: (act-[A-Za-z0-9_.-]+)", request).group(1)
                token = (ai_council.get_latest_action(request_id)["payload"] or {}).get("confirm_token")
                ai_council.approve_response(request_id)
                executed = ai_council.provider_response(f"execute {request_id} {token}")
                latest = ai_council.get_latest_action(request_id)

        self.assertIn("title too large", executed)
        self.assertIn("external_write_performed: false", executed)
        self.assertEqual(latest["status"], "write_blocked")

    def test_gmail_provider_write_request_creates_draft_with_gates_and_verifies(self):
        captured: dict[str, object] = {}

        def fake_request_json(url: str, **kwargs):
            if url.startswith("https://gmail.googleapis.com/gmail/v1/users/me/drafts?"):
                return {"drafts": []}
            captured["url"] = url
            captured["kwargs"] = kwargs
            return {
                "id": "draft-123",
                "message": {"id": "msg-123", "threadId": "thread-123", "labelIds": ["DRAFT"]},
            }

        with temp_dir() as tmp:
            root = Path(tmp)
            env = {
                "AI_COUNCIL_PROVIDER_WRITE_ENABLED": "true",
                "AI_COUNCIL_GMAIL_DRAFT_WRITE_ENABLED": "true",
                "AI_COUNCIL_GMAIL_FROM": "bartek@example.com",
            }
            with patch.dict(os.environ, env, clear=False), patch.object(
                ai_council, "ACTIONS_FILE", root / "state" / "actions.jsonl"
            ), patch.object(ai_council, "ARTIFACTS_DIR", root / "artifacts"), patch.object(
                ai_council, "MEMORY_DB", root / "state" / "memory.sqlite"
            ), patch.object(ai_council, "LOG_DIR", root / "logs"), patch.object(
                ai_council, "AUDIT_LOG", root / "logs" / "audit.jsonl"
            ), patch.object(ai_council, "google_oauth_configured", return_value=True), patch.object(
                ai_council, "google_access_token", return_value=("available", "gmail-access-token")
            ), patch.object(ai_council, "request_json", side_effect=fake_request_json) as request_json:
                action = ai_council.create_integration_draft_action("gmail", "napisz draft do klienta o statusie", risk="R3")
                ai_council.approve_response(action["action_id"])
                ai_council.execute_response(action["action_id"])
                ai_council.verify_response(action["action_id"])
                ready = ai_council.get_latest_action(action["action_id"])
                payload = {**(ready["payload"] or {})}
                payload["missing_fields"] = []
                payload["draft"] = {
                    "to": "client@example.com",
                    "subject": "AI Council status",
                    "body": "Hello,\n\nCurrent deployment status is ready.\n",
                }
                ai_council.append_jsonl(ai_council.ACTIONS_FILE, {**ready, "updated_at": ai_council.utc_now(), "payload": payload})
                ai_council.provider_response(f"plan {action['action_id']}")
                ai_council.provider_response(f"verify {action['action_id']}")
                request = ai_council.provider_response(f"request {action['action_id']}")
                request_id = re.search(r"id: (act-[A-Za-z0-9_.-]+)", request).group(1)
                token = (ai_council.get_latest_action(request_id)["payload"] or {}).get("confirm_token")
                ai_council.approve_response(request_id)
                executed = ai_council.provider_response(f"execute {request_id} {token}")
                executed_action = ai_council.get_latest_action(request_id)
                result = (executed_action["payload"] or {}).get("provider_write_result") or {}
                data = json.loads(Path(result["json_path"]).read_text(encoding="utf-8"))
                raw = captured["kwargs"]["payload"]["message"]["raw"]
                decoded = base64.urlsafe_b64decode(raw + "=" * (-len(raw) % 4)).decode("utf-8", errors="replace")
                verified = ai_council.provider_response(f"verify {request_id}")

        self.assertIn("Gmail draft executed L4.41", executed)
        self.assertIn("external_write_performed: true", executed)
        self.assertEqual(captured["url"], "https://gmail.googleapis.com/gmail/v1/users/me/drafts")
        self.assertEqual(captured["kwargs"]["method"], "POST")
        self.assertIn("Authorization", captured["kwargs"]["headers"])
        self.assertIn("From: bartek@example.com", decoded)
        self.assertIn("To: client@example.com", decoded)
        self.assertIn("Subject: AI Council status", decoded)
        self.assertIn("Current deployment status is ready", decoded)
        self.assertEqual(request_json.call_count, 2)
        self.assertTrue(data["external_write_performed"])
        self.assertEqual(data["provider_read_before_write"]["status"], "clear")
        self.assertEqual(data["provider_operation"], "gmail.users.drafts.create")
        self.assertEqual(data["provider_id"], "draft-123")
        self.assertEqual(data["provider_message_id"], "msg-123")
        self.assertTrue(data["request_payload"]["metadata"]["from_configured"])
        self.assertIn("provider write request result verified", verified)

    def test_gmail_provider_write_failure_is_not_retried(self):
        def fake_request_json(url: str, **kwargs):
            if url.startswith("https://gmail.googleapis.com/gmail/v1/users/me/drafts?"):
                return {"drafts": []}
            return {"ok": False, "error": "http_400", "body_preview": "gmail validation failed"}

        with temp_dir() as tmp:
            root = Path(tmp)
            env = {
                "AI_COUNCIL_PROVIDER_WRITE_ENABLED": "true",
                "AI_COUNCIL_GMAIL_DRAFT_WRITE_ENABLED": "true",
            }
            with patch.dict(os.environ, env, clear=False), patch.object(
                ai_council, "ACTIONS_FILE", root / "state" / "actions.jsonl"
            ), patch.object(ai_council, "ARTIFACTS_DIR", root / "artifacts"), patch.object(
                ai_council, "MEMORY_DB", root / "state" / "memory.sqlite"
            ), patch.object(ai_council, "LOG_DIR", root / "logs"), patch.object(
                ai_council, "AUDIT_LOG", root / "logs" / "audit.jsonl"
            ), patch.object(ai_council, "google_oauth_configured", return_value=True), patch.object(
                ai_council, "google_access_token", return_value=("available", "gmail-access-token")
            ), patch.object(ai_council, "request_json", side_effect=fake_request_json) as request_json:
                action = ai_council.create_integration_draft_action("gmail", "napisz draft z błędem API", risk="R3")
                ai_council.approve_response(action["action_id"])
                ai_council.execute_response(action["action_id"])
                ai_council.verify_response(action["action_id"])
                ready = ai_council.get_latest_action(action["action_id"])
                payload = {**(ready["payload"] or {})}
                payload["missing_fields"] = []
                payload["draft"] = {
                    "to": "client@example.com",
                    "subject": "Failure branch",
                    "body": "This should fail.",
                }
                ai_council.append_jsonl(ai_council.ACTIONS_FILE, {**ready, "updated_at": ai_council.utc_now(), "payload": payload})
                ai_council.provider_response(f"plan {action['action_id']}")
                ai_council.provider_response(f"verify {action['action_id']}")
                request = ai_council.provider_response(f"request {action['action_id']}")
                request_id = re.search(r"id: (act-[A-Za-z0-9_.-]+)", request).group(1)
                token = (ai_council.get_latest_action(request_id)["payload"] or {}).get("confirm_token")
                ai_council.approve_response(request_id)
                failed = ai_council.provider_response(f"execute {request_id} {token}")
                verified = ai_council.provider_response(f"verify {request_id}")
                retry = ai_council.provider_response(f"execute {request_id} {token}")

        self.assertIn("Gmail draft write failed L4.41", failed)
        self.assertIn("manual_check:", failed)
        self.assertIn("external_write_performed: false", failed)
        self.assertIn("provider write failed; check provider manually", verified)
        self.assertIn("wcześniejszy provider POST/result", retry)
        self.assertEqual(request_json.call_count, 2)

    def test_gmail_provider_write_blocks_when_gate_disabled(self):
        with temp_dir() as tmp:
            root = Path(tmp)
            env = {"AI_COUNCIL_PROVIDER_WRITE_ENABLED": "true"}
            with patch.dict(os.environ, env, clear=False), patch.object(
                ai_council, "ACTIONS_FILE", root / "state" / "actions.jsonl"
            ), patch.object(ai_council, "ARTIFACTS_DIR", root / "artifacts"), patch.object(
                ai_council, "MEMORY_DB", root / "state" / "memory.sqlite"
            ), patch.object(ai_council, "LOG_DIR", root / "logs"), patch.object(
                ai_council, "AUDIT_LOG", root / "logs" / "audit.jsonl"
            ), patch.object(ai_council, "google_oauth_configured", return_value=True), patch.object(
                ai_council, "request_json", side_effect=AssertionError("Gmail API should not be called")
            ):
                action = ai_council.create_integration_draft_action("gmail", "napisz draft do klienta", risk="R3")
                ai_council.approve_response(action["action_id"])
                ai_council.execute_response(action["action_id"])
                ai_council.verify_response(action["action_id"])
                ready = ai_council.get_latest_action(action["action_id"])
                payload = {**(ready["payload"] or {})}
                payload["missing_fields"] = []
                payload["draft"] = {
                    "to": "client@example.com",
                    "subject": "Gate disabled",
                    "body": "Should be blocked.",
                }
                ai_council.append_jsonl(ai_council.ACTIONS_FILE, {**ready, "updated_at": ai_council.utc_now(), "payload": payload})
                ai_council.provider_response(f"plan {action['action_id']}")
                ai_council.provider_response(f"verify {action['action_id']}")
                request = ai_council.provider_response(f"request {action['action_id']}")
                request_id = re.search(r"id: (act-[A-Za-z0-9_.-]+)", request).group(1)
                token = (ai_council.get_latest_action(request_id)["payload"] or {}).get("confirm_token")
                ai_council.approve_response(request_id)
                executed = ai_council.provider_response(f"execute {request_id} {token}")
                latest = ai_council.get_latest_action(request_id)

        self.assertIn("AI_COUNCIL_GMAIL_DRAFT_WRITE_ENABLED=false", executed)
        self.assertIn("external_write_performed: false", executed)
        self.assertEqual(latest["status"], "write_blocked")

    def test_calendar_provider_write_request_creates_event_with_gates_and_verifies(self):
        captured: dict[str, object] = {}

        def fake_request_json(url: str, **kwargs):
            if "singleEvents=true" in url:
                return {"items": []}
            captured["url"] = url
            captured["kwargs"] = kwargs
            return {
                "id": "evt-123",
                "htmlLink": "https://calendar.google.com/event?eid=evt-123",
                "summary": kwargs["payload"]["summary"],
            }

        with temp_dir() as tmp:
            root = Path(tmp)
            env = {
                "AI_COUNCIL_PROVIDER_WRITE_ENABLED": "true",
                "AI_COUNCIL_CALENDAR_EVENT_WRITE_ENABLED": "true",
            }
            with patch.dict(os.environ, env, clear=False), patch.object(
                ai_council, "ACTIONS_FILE", root / "state" / "actions.jsonl"
            ), patch.object(ai_council, "ARTIFACTS_DIR", root / "artifacts"), patch.object(
                ai_council, "MEMORY_DB", root / "state" / "memory.sqlite"
            ), patch.object(ai_council, "LOG_DIR", root / "logs"), patch.object(
                ai_council, "AUDIT_LOG", root / "logs" / "audit.jsonl"
            ), patch.object(ai_council, "google_oauth_configured", return_value=True), patch.object(
                ai_council, "google_access_token", return_value=("available", "calendar-access-token")
            ), patch.object(ai_council, "request_json", side_effect=fake_request_json) as request_json:
                action = ai_council.create_integration_draft_action("calendar", "umów spotkanie zespołu", risk="R3")
                ai_council.approve_response(action["action_id"])
                ai_council.execute_response(action["action_id"])
                ai_council.verify_response(action["action_id"])
                ready = ai_council.get_latest_action(action["action_id"])
                payload = {**(ready["payload"] or {})}
                payload["missing_fields"] = []
                payload["draft"] = {
                    "summary": "AI Council deployment review",
                    "start": "2026-06-08T10:00:00+02:00",
                    "end": "2026-06-08T10:30:00+02:00",
                    "timezone": "Europe/Warsaw",
                    "attendees": ["team@example.com"],
                    "description": "Review L4.34 provider executor.",
                }
                ai_council.append_jsonl(ai_council.ACTIONS_FILE, {**ready, "updated_at": ai_council.utc_now(), "payload": payload})
                ai_council.provider_response(f"plan {action['action_id']}")
                ai_council.provider_response(f"verify {action['action_id']}")
                request = ai_council.provider_response(f"request {action['action_id']}")
                request_id = re.search(r"id: (act-[A-Za-z0-9_.-]+)", request).group(1)
                token = (ai_council.get_latest_action(request_id)["payload"] or {}).get("confirm_token")
                ai_council.approve_response(request_id)
                executed = ai_council.provider_response(f"execute {request_id} {token}")
                executed_action = ai_council.get_latest_action(request_id)
                result = (executed_action["payload"] or {}).get("provider_write_result") or {}
                data = json.loads(Path(result["json_path"]).read_text(encoding="utf-8"))
                verified = ai_council.provider_response(f"verify {request_id}")

        self.assertIn("Calendar event executed L4.41", executed)
        self.assertIn("external_write_performed: true", executed)
        self.assertIn("/calendar/v3/calendars/primary/events?", captured["url"])
        self.assertIn("sendUpdates=none", captured["url"])
        self.assertEqual(captured["kwargs"]["method"], "POST")
        self.assertEqual(captured["kwargs"]["payload"]["summary"], "AI Council deployment review")
        self.assertEqual(captured["kwargs"]["payload"]["start"]["timeZone"], "Europe/Warsaw")
        self.assertEqual(captured["kwargs"]["payload"]["attendees"], [{"email": "team@example.com"}])
        self.assertEqual(request_json.call_count, 2)
        self.assertTrue(data["external_write_performed"])
        self.assertEqual(data["provider_read_before_write"]["status"], "clear")
        self.assertEqual(data["provider_operation"], "calendar.events.insert")
        self.assertEqual(data["provider_id"], "evt-123")
        self.assertEqual(data["html_url"], "https://calendar.google.com/event?eid=evt-123")
        self.assertIn("provider write request result verified", verified)

    def test_calendar_provider_write_failure_is_not_retried(self):
        def fake_request_json(url: str, **kwargs):
            if "singleEvents=true" in url:
                return {"items": []}
            return {"ok": False, "error": "http_400", "body_preview": "calendar validation failed"}

        with temp_dir() as tmp:
            root = Path(tmp)
            env = {
                "AI_COUNCIL_PROVIDER_WRITE_ENABLED": "true",
                "AI_COUNCIL_CALENDAR_EVENT_WRITE_ENABLED": "true",
            }
            with patch.dict(os.environ, env, clear=False), patch.object(
                ai_council, "ACTIONS_FILE", root / "state" / "actions.jsonl"
            ), patch.object(ai_council, "ARTIFACTS_DIR", root / "artifacts"), patch.object(
                ai_council, "MEMORY_DB", root / "state" / "memory.sqlite"
            ), patch.object(ai_council, "LOG_DIR", root / "logs"), patch.object(
                ai_council, "AUDIT_LOG", root / "logs" / "audit.jsonl"
            ), patch.object(ai_council, "google_oauth_configured", return_value=True), patch.object(
                ai_council, "google_access_token", return_value=("available", "calendar-access-token")
            ), patch.object(ai_council, "request_json", side_effect=fake_request_json) as request_json:
                action = ai_council.create_integration_draft_action("calendar", "umów spotkanie z błędem API", risk="R3")
                ai_council.approve_response(action["action_id"])
                ai_council.execute_response(action["action_id"])
                ai_council.verify_response(action["action_id"])
                ready = ai_council.get_latest_action(action["action_id"])
                payload = {**(ready["payload"] or {})}
                payload["missing_fields"] = []
                payload["draft"] = {
                    "summary": "Calendar failure branch",
                    "start": "2026-06-08T10:00:00+02:00",
                    "end": "2026-06-08T10:30:00+02:00",
                    "timezone": "Europe/Warsaw",
                    "attendees": [],
                    "description": "Should fail.",
                }
                ai_council.append_jsonl(ai_council.ACTIONS_FILE, {**ready, "updated_at": ai_council.utc_now(), "payload": payload})
                ai_council.provider_response(f"plan {action['action_id']}")
                ai_council.provider_response(f"verify {action['action_id']}")
                request = ai_council.provider_response(f"request {action['action_id']}")
                request_id = re.search(r"id: (act-[A-Za-z0-9_.-]+)", request).group(1)
                token = (ai_council.get_latest_action(request_id)["payload"] or {}).get("confirm_token")
                ai_council.approve_response(request_id)
                failed = ai_council.provider_response(f"execute {request_id} {token}")
                verified = ai_council.provider_response(f"verify {request_id}")
                retry = ai_council.provider_response(f"execute {request_id} {token}")

        self.assertIn("Calendar event write failed L4.41", failed)
        self.assertIn("manual_check:", failed)
        self.assertIn("external_write_performed: false", failed)
        self.assertIn("provider write failed; check provider manually", verified)
        self.assertIn("wcześniejszy provider POST/result", retry)
        self.assertEqual(request_json.call_count, 2)

    def test_calendar_provider_write_blocks_when_gate_disabled(self):
        with temp_dir() as tmp:
            root = Path(tmp)
            env = {"AI_COUNCIL_PROVIDER_WRITE_ENABLED": "true"}
            with patch.dict(os.environ, env, clear=False), patch.object(
                ai_council, "ACTIONS_FILE", root / "state" / "actions.jsonl"
            ), patch.object(ai_council, "ARTIFACTS_DIR", root / "artifacts"), patch.object(
                ai_council, "MEMORY_DB", root / "state" / "memory.sqlite"
            ), patch.object(ai_council, "LOG_DIR", root / "logs"), patch.object(
                ai_council, "AUDIT_LOG", root / "logs" / "audit.jsonl"
            ), patch.object(ai_council, "google_oauth_configured", return_value=True), patch.object(
                ai_council, "request_json", side_effect=AssertionError("Calendar API should not be called")
            ):
                action = ai_council.create_integration_draft_action("calendar", "umów spotkanie zespołu", risk="R3")
                ai_council.approve_response(action["action_id"])
                ai_council.execute_response(action["action_id"])
                ai_council.verify_response(action["action_id"])
                ready = ai_council.get_latest_action(action["action_id"])
                payload = {**(ready["payload"] or {})}
                payload["missing_fields"] = []
                payload["draft"] = {
                    "summary": "Gate disabled",
                    "start": "2026-06-08T10:00:00+02:00",
                    "end": "2026-06-08T10:30:00+02:00",
                    "timezone": "Europe/Warsaw",
                    "attendees": [],
                    "description": "Should be blocked.",
                }
                ai_council.append_jsonl(ai_council.ACTIONS_FILE, {**ready, "updated_at": ai_council.utc_now(), "payload": payload})
                ai_council.provider_response(f"plan {action['action_id']}")
                ai_council.provider_response(f"verify {action['action_id']}")
                request = ai_council.provider_response(f"request {action['action_id']}")
                request_id = re.search(r"id: (act-[A-Za-z0-9_.-]+)", request).group(1)
                token = (ai_council.get_latest_action(request_id)["payload"] or {}).get("confirm_token")
                ai_council.approve_response(request_id)
                executed = ai_council.provider_response(f"execute {request_id} {token}")
                latest = ai_council.get_latest_action(request_id)

        self.assertIn("AI_COUNCIL_CALENDAR_EVENT_WRITE_ENABLED=false", executed)
        self.assertIn("external_write_performed: false", executed)
        self.assertEqual(latest["status"], "write_blocked")

    def test_calendar_provider_write_blocks_invalid_time_range_before_network(self):
        with temp_dir() as tmp:
            root = Path(tmp)
            env = {
                "AI_COUNCIL_PROVIDER_WRITE_ENABLED": "true",
                "AI_COUNCIL_CALENDAR_EVENT_WRITE_ENABLED": "true",
            }
            with patch.dict(os.environ, env, clear=False), patch.object(
                ai_council, "ACTIONS_FILE", root / "state" / "actions.jsonl"
            ), patch.object(ai_council, "ARTIFACTS_DIR", root / "artifacts"), patch.object(
                ai_council, "MEMORY_DB", root / "state" / "memory.sqlite"
            ), patch.object(ai_council, "LOG_DIR", root / "logs"), patch.object(
                ai_council, "AUDIT_LOG", root / "logs" / "audit.jsonl"
            ), patch.object(ai_council, "google_oauth_configured", return_value=True), patch.object(
                ai_council, "request_json", side_effect=AssertionError("Calendar API should not be called")
            ):
                action = ai_council.create_integration_draft_action("calendar", "umów spotkanie z błędnym czasem", risk="R3")
                ai_council.approve_response(action["action_id"])
                ai_council.execute_response(action["action_id"])
                ai_council.verify_response(action["action_id"])
                ready = ai_council.get_latest_action(action["action_id"])
                payload = {**(ready["payload"] or {})}
                payload["missing_fields"] = []
                payload["draft"] = {
                    "summary": "Invalid time range",
                    "start": "2026-06-08T10:30:00+02:00",
                    "end": "2026-06-08T10:00:00+02:00",
                    "timezone": "Europe/Warsaw",
                    "attendees": [],
                    "description": "Should be blocked before API.",
                }
                ai_council.append_jsonl(ai_council.ACTIONS_FILE, {**ready, "updated_at": ai_council.utc_now(), "payload": payload})
                ai_council.provider_response(f"plan {action['action_id']}")
                ai_council.provider_response(f"verify {action['action_id']}")
                request = ai_council.provider_response(f"request {action['action_id']}")
                request_id = re.search(r"id: (act-[A-Za-z0-9_.-]+)", request).group(1)
                token = (ai_council.get_latest_action(request_id)["payload"] or {}).get("confirm_token")
                ai_council.approve_response(request_id)
                executed = ai_council.provider_response(f"execute {request_id} {token}")
                latest = ai_council.get_latest_action(request_id)

        self.assertIn("end must be after start", executed)
        self.assertIn("external_write_performed: false", executed)
        self.assertEqual(latest["status"], "write_blocked")

    def test_drive_provider_write_blocks_when_drive_gate_disabled(self):
        with temp_dir() as tmp:
            root = Path(tmp)
            env = {
                "AI_COUNCIL_PROVIDER_WRITE_ENABLED": "true",
                "AI_COUNCIL_DRIVE_FILE_WRITE_ENABLED": "false",
            }
            with patch.dict(os.environ, env, clear=False), patch.object(
                ai_council, "ACTIONS_FILE", root / "state" / "actions.jsonl"
            ), patch.object(ai_council, "ARTIFACTS_DIR", root / "artifacts"), patch.object(
                ai_council, "MEMORY_DB", root / "state" / "memory.sqlite"
            ), patch.object(ai_council, "LOG_DIR", root / "logs"), patch.object(
                ai_council, "AUDIT_LOG", root / "logs" / "audit.jsonl"
            ), patch.object(ai_council, "google_oauth_configured", return_value=True), patch.object(
                ai_council, "request_multipart_related_json", side_effect=AssertionError("Drive API should not be called")
            ):
                action = ai_council.create_integration_draft_action("drive", "utwórz dokument o planie wdrożenia", risk="R3")
                ai_council.approve_response(action["action_id"])
                ai_council.execute_response(action["action_id"])
                ai_council.verify_response(action["action_id"])
                ready = ai_council.get_latest_action(action["action_id"])
                payload = {**(ready["payload"] or {})}
                payload["missing_fields"] = []
                payload["draft"] = {
                    "title": "Plan wdrożenia AI Council",
                    "body": "Drive provider write is not enabled in L4.34.",
                    "outline": ["Cel", "Zakres", "Następne kroki"],
                }
                ai_council.append_jsonl(ai_council.ACTIONS_FILE, {**ready, "updated_at": ai_council.utc_now(), "payload": payload})
                ai_council.provider_response(f"plan {action['action_id']}")
                ai_council.provider_response(f"verify {action['action_id']}")
                request = ai_council.provider_response(f"request {action['action_id']}")
                request_id = re.search(r"id: (act-[A-Za-z0-9_.-]+)", request).group(1)
                token = (ai_council.get_latest_action(request_id)["payload"] or {}).get("confirm_token")
                ai_council.approve_response(request_id)
                executed = ai_council.provider_response(f"execute {request_id} {token}")
                latest = ai_council.get_latest_action(request_id)

        self.assertIn("Write gate L4.41", executed)
        self.assertIn("AI_COUNCIL_DRIVE_FILE_WRITE_ENABLED=false", executed)
        self.assertIn("external_write_performed: false", executed)
        self.assertEqual(latest["status"], "write_blocked")

    def test_drive_provider_write_request_executes_with_gates_and_verifies(self):
        captured: dict[str, object] = {}

        def fake_drive_list(url: str, **kwargs):
            return {"files": []}

        def fake_drive_upload(url: str, **kwargs):
            captured["url"] = url
            captured["kwargs"] = kwargs
            return {
                "id": "drive-file-123",
                "name": kwargs["metadata"]["name"],
                "mimeType": "application/vnd.google-apps.document",
                "webViewLink": "https://docs.google.com/document/d/drive-file-123/edit",
            }

        with temp_dir() as tmp:
            root = Path(tmp)
            env = {
                "AI_COUNCIL_PROVIDER_WRITE_ENABLED": "true",
                "AI_COUNCIL_DRIVE_FILE_WRITE_ENABLED": "true",
            }
            with patch.dict(os.environ, env, clear=False), patch.object(
                ai_council, "ACTIONS_FILE", root / "state" / "actions.jsonl"
            ), patch.object(ai_council, "ARTIFACTS_DIR", root / "artifacts"), patch.object(
                ai_council, "MEMORY_DB", root / "state" / "memory.sqlite"
            ), patch.object(ai_council, "LOG_DIR", root / "logs"), patch.object(
                ai_council, "AUDIT_LOG", root / "logs" / "audit.jsonl"
            ), patch.object(ai_council, "google_oauth_configured", return_value=True), patch.object(
                ai_council, "google_access_token", return_value=("available", "google-token")
            ), patch.object(
                ai_council, "request_json", side_effect=fake_drive_list
            ) as request_json, patch.object(
                ai_council, "request_multipart_related_json", side_effect=fake_drive_upload
            ) as drive_upload:
                action = ai_council.create_integration_draft_action("drive", "utwórz dokument o L4.41", risk="R3")
                ai_council.approve_response(action["action_id"])
                ai_council.execute_response(action["action_id"])
                ai_council.verify_response(action["action_id"])
                ready = ai_council.get_latest_action(action["action_id"])
                payload = {**(ready["payload"] or {})}
                payload["missing_fields"] = []
                payload["draft"] = {
                    "title": "L4.41 Drive executor test",
                    "body": "Verify Drive provider executor flow.",
                    "outline": ["Cel", "Zakres", "Weryfikacja"],
                }
                ai_council.append_jsonl(ai_council.ACTIONS_FILE, {**ready, "updated_at": ai_council.utc_now(), "payload": payload})
                ai_council.provider_response(f"plan {action['action_id']}")
                ai_council.provider_response(f"verify {action['action_id']}")
                request = ai_council.provider_response(f"request {action['action_id']}")
                request_id = re.search(r"id: (act-[A-Za-z0-9_.-]+)", request).group(1)
                request_action = ai_council.get_latest_action(request_id)
                token = (request_action["payload"] or {}).get("confirm_token")
                ai_council.approve_response(request_id)
                executed = ai_council.provider_response(f"execute {request_id} {token}")
                executed_action = ai_council.get_latest_action(request_id)
                result = (executed_action["payload"] or {}).get("provider_write_result") or {}
                data = json.loads(Path(result["json_path"]).read_text(encoding="utf-8"))
                verified = ai_council.provider_response(f"verify {request_id}")
                latest = ai_council.get_latest_action(request_id)

        self.assertIn("Drive document executed L4.41", executed)
        self.assertIn("external_write_performed: true", executed)
        self.assertIn("https://docs.google.com/document/d/drive-file-123/edit", executed)
        self.assertIn("uploadType=multipart", captured["url"])
        self.assertIn("fields=", captured["url"])
        self.assertEqual(captured["kwargs"]["metadata"]["name"], "L4.41 Drive executor test")
        self.assertEqual(captured["kwargs"]["metadata"]["mimeType"], "application/vnd.google-apps.document")
        self.assertIn("Outline", captured["kwargs"]["media_text"])
        self.assertIn("Verify Drive provider executor flow.", captured["kwargs"]["media_text"])
        self.assertEqual(drive_upload.call_count, 1)
        self.assertEqual(request_json.call_count, 1)
        self.assertTrue(data["external_write_performed"])
        self.assertEqual(data["provider_read_before_write"]["status"], "clear")
        self.assertEqual(data["provider_operation"], "drive.files.create")
        self.assertEqual(data["html_url"], "https://docs.google.com/document/d/drive-file-123/edit")
        self.assertIn("provider write request result verified", verified)
        self.assertEqual(latest["status"], "verified")

    def test_github_provider_read_before_write_blocks_duplicate_issue_before_post(self):
        search_urls: list[str] = []

        def fake_request_json(url: str, **kwargs):
            if "/search/issues?" in url:
                search_urls.append(url)
                return {
                    "items": [
                        {
                            "id": 123456,
                            "number": 11,
                            "title": 'Duplicate "quoted" issue',
                            "state": "open",
                            "html_url": "https://github.com/Acoste616/AIagent/issues/11",
                        }
                    ]
                }
            raise AssertionError("GitHub POST should not be called")

        with temp_dir() as tmp:
            root = Path(tmp)
            env = {
                "AI_COUNCIL_PROVIDER_WRITE_ENABLED": "true",
                "AI_COUNCIL_GITHUB_ISSUE_WRITE_ENABLED": "true",
                "AI_COUNCIL_GITHUB_REPO": "Acoste616/AIagent",
                "GITHUB_TOKEN": "unit-token",
            }
            with patch.dict(os.environ, env, clear=False), patch.object(
                ai_council, "ACTIONS_FILE", root / "state" / "actions.jsonl"
            ), patch.object(ai_council, "ARTIFACTS_DIR", root / "artifacts"), patch.object(
                ai_council, "MEMORY_DB", root / "state" / "memory.sqlite"
            ), patch.object(ai_council, "LOG_DIR", root / "logs"), patch.object(
                ai_council, "AUDIT_LOG", root / "logs" / "audit.jsonl"
            ), patch.object(ai_council, "github_token", return_value="unit-token"), patch.object(
                ai_council, "request_json", side_effect=fake_request_json
            ) as request_json:
                action = ai_council.create_integration_draft_action("github", "otwórz issue duplicate", risk="R3")
                ai_council.approve_response(action["action_id"])
                ai_council.execute_response(action["action_id"])
                ai_council.verify_response(action["action_id"])
                ready = ai_council.get_latest_action(action["action_id"])
                payload = {**(ready["payload"] or {})}
                payload["missing_fields"] = []
                payload["draft"] = {
                    "repo": "Acoste616/AIagent",
                    "title": 'Duplicate "quoted" issue',
                    "body": "Should be blocked by read-before-write.",
                    "labels": [],
                }
                ai_council.append_jsonl(ai_council.ACTIONS_FILE, {**ready, "updated_at": ai_council.utc_now(), "payload": payload})
                ai_council.provider_response(f"plan {action['action_id']}")
                ai_council.provider_response(f"verify {action['action_id']}")
                request = ai_council.provider_response(f"request {action['action_id']}")
                request_id = re.search(r"id: (act-[A-Za-z0-9_.-]+)", request).group(1)
                token = (ai_council.get_latest_action(request_id)["payload"] or {}).get("confirm_token")
                ai_council.approve_response(request_id)
                executed = ai_council.provider_response(f"execute {request_id} {token}")
                latest = ai_council.get_latest_action(request_id)
                dry_run = (latest["payload"] or {}).get("provider_write_dry_run") or {}
                dry_data = json.loads(Path(dry_run["json_path"]).read_text(encoding="utf-8"))

        self.assertIn("read-before-write", executed)
        self.assertIn("external_write_performed: false", executed)
        self.assertEqual(latest["status"], "write_blocked")
        self.assertEqual((latest["payload"] or {})["provider_read_before_write"]["status"], "conflict")
        self.assertEqual(dry_data["provider_read_before_write"]["status"], "conflict")
        self.assertIn("%5C%22quoted%5C%22", search_urls[0])
        self.assertEqual(request_json.call_count, 1)

    def test_provider_read_before_write_failure_blocks_before_post(self):
        def fake_request_json(url: str, **kwargs):
            if "/search/issues?" in url:
                return {"ok": False, "error": "http_503", "body_preview": "GitHub search temporarily unavailable"}
            raise AssertionError("GitHub POST should not be called after failed preflight")

        with temp_dir() as tmp:
            root = Path(tmp)
            env = {
                "AI_COUNCIL_PROVIDER_WRITE_ENABLED": "true",
                "AI_COUNCIL_GITHUB_ISSUE_WRITE_ENABLED": "true",
                "AI_COUNCIL_GITHUB_REPO": "Acoste616/AIagent",
                "GITHUB_TOKEN": "unit-token",
            }
            with patch.dict(os.environ, env, clear=False), patch.object(
                ai_council, "ACTIONS_FILE", root / "state" / "actions.jsonl"
            ), patch.object(ai_council, "ARTIFACTS_DIR", root / "artifacts"), patch.object(
                ai_council, "MEMORY_DB", root / "state" / "memory.sqlite"
            ), patch.object(ai_council, "LOG_DIR", root / "logs"), patch.object(
                ai_council, "AUDIT_LOG", root / "logs" / "audit.jsonl"
            ), patch.object(ai_council, "github_token", return_value="unit-token"), patch.object(
                ai_council, "request_json", side_effect=fake_request_json
            ) as request_json:
                action = ai_council.create_integration_draft_action("github", "otwórz issue preflight fail", risk="R3")
                ai_council.approve_response(action["action_id"])
                ai_council.execute_response(action["action_id"])
                ai_council.verify_response(action["action_id"])
                ready = ai_council.get_latest_action(action["action_id"])
                payload = {**(ready["payload"] or {})}
                payload["missing_fields"] = []
                payload["draft"] = {
                    "repo": "Acoste616/AIagent",
                    "title": "Preflight failure issue",
                    "body": "Should be blocked by failed read-before-write.",
                    "labels": [],
                }
                ai_council.append_jsonl(ai_council.ACTIONS_FILE, {**ready, "updated_at": ai_council.utc_now(), "payload": payload})
                ai_council.provider_response(f"plan {action['action_id']}")
                ai_council.provider_response(f"verify {action['action_id']}")
                request = ai_council.provider_response(f"request {action['action_id']}")
                request_id = re.search(r"id: (act-[A-Za-z0-9_.-]+)", request).group(1)
                token = (ai_council.get_latest_action(request_id)["payload"] or {}).get("confirm_token")
                ai_council.approve_response(request_id)
                executed = ai_council.provider_response(f"execute {request_id} {token}")
                latest = ai_council.get_latest_action(request_id)

        self.assertIn("read-before-write", executed)
        self.assertIn("external_write_performed: false", executed)
        self.assertEqual(latest["status"], "write_blocked")
        self.assertEqual((latest["payload"] or {})["provider_read_before_write"]["status"], "failed")
        self.assertFalse((latest["payload"] or {}).get("provider_write_result"))
        self.assertEqual(request_json.call_count, 1)

    def test_provider_read_before_write_disabled_flag_skips_preflight_and_allows_write(self):
        captured: dict[str, object] = {}

        def fake_request_json(url: str, **kwargs):
            if "/search/issues?" in url:
                raise AssertionError("GitHub search should not run when read-before-write is disabled")
            captured["url"] = url
            captured["kwargs"] = kwargs
            return {
                "id": 123457,
                "number": 12,
                "html_url": "https://github.com/Acoste616/AIagent/issues/12",
                "url": "https://api.github.com/repos/Acoste616/AIagent/issues/12",
                "title": kwargs["payload"]["title"],
            }

        with temp_dir() as tmp:
            root = Path(tmp)
            env = {
                "AI_COUNCIL_PROVIDER_WRITE_ENABLED": "true",
                "AI_COUNCIL_GITHUB_ISSUE_WRITE_ENABLED": "true",
                "AI_COUNCIL_PROVIDER_READ_BEFORE_WRITE_ENABLED": "false",
                "AI_COUNCIL_GITHUB_REPO": "Acoste616/AIagent",
                "GITHUB_TOKEN": "unit-token",
            }
            with patch.dict(os.environ, env, clear=False), patch.object(
                ai_council, "ACTIONS_FILE", root / "state" / "actions.jsonl"
            ), patch.object(ai_council, "ARTIFACTS_DIR", root / "artifacts"), patch.object(
                ai_council, "MEMORY_DB", root / "state" / "memory.sqlite"
            ), patch.object(ai_council, "LOG_DIR", root / "logs"), patch.object(
                ai_council, "AUDIT_LOG", root / "logs" / "audit.jsonl"
            ), patch.object(ai_council, "github_token", return_value="unit-token"), patch.object(
                ai_council, "request_json", side_effect=fake_request_json
            ) as request_json:
                action = ai_council.create_integration_draft_action("github", "otwórz issue skip preflight", risk="R3")
                ai_council.approve_response(action["action_id"])
                ai_council.execute_response(action["action_id"])
                ai_council.verify_response(action["action_id"])
                ready = ai_council.get_latest_action(action["action_id"])
                payload = {**(ready["payload"] or {})}
                payload["missing_fields"] = []
                payload["draft"] = {
                    "repo": "Acoste616/AIagent",
                    "title": "Disabled preflight issue",
                    "body": "Should skip read-before-write by flag.",
                    "labels": [],
                }
                ai_council.append_jsonl(ai_council.ACTIONS_FILE, {**ready, "updated_at": ai_council.utc_now(), "payload": payload})
                ai_council.provider_response(f"plan {action['action_id']}")
                ai_council.provider_response(f"verify {action['action_id']}")
                request = ai_council.provider_response(f"request {action['action_id']}")
                request_id = re.search(r"id: (act-[A-Za-z0-9_.-]+)", request).group(1)
                token = (ai_council.get_latest_action(request_id)["payload"] or {}).get("confirm_token")
                ai_council.approve_response(request_id)
                executed = ai_council.provider_response(f"execute {request_id} {token}")
                executed_action = ai_council.get_latest_action(request_id)
                result = (executed_action["payload"] or {}).get("provider_write_result") or {}
                data = json.loads(Path(result["json_path"]).read_text(encoding="utf-8"))

        self.assertIn("GitHub issue executed L4.41", executed)
        self.assertEqual(captured["url"], "https://api.github.com/repos/Acoste616/AIagent/issues")
        self.assertEqual(request_json.call_count, 1)
        self.assertEqual(data["provider_read_before_write"]["status"], "skipped")
        self.assertFalse(data["provider_read_before_write"]["enabled"])

    def test_gmail_provider_read_before_write_blocks_duplicate_draft_before_post(self):
        def fake_request_json(url: str, **kwargs):
            if url.startswith("https://gmail.googleapis.com/gmail/v1/users/me/drafts?"):
                return {"drafts": [{"id": "draft-dup"}]}
            if "/gmail/v1/users/me/drafts/draft-dup?" in url:
                return {
                    "id": "draft-dup",
                    "message": {
                        "payload": {
                            "headers": [
                                {"name": "To", "value": "Client <client@example.com>"},
                                {"name": "Subject", "value": "Duplicate draft"},
                            ]
                        }
                    },
                }
            raise AssertionError("Gmail draft POST should not be called")

        with temp_dir() as tmp:
            root = Path(tmp)
            env = {
                "AI_COUNCIL_PROVIDER_WRITE_ENABLED": "true",
                "AI_COUNCIL_GMAIL_DRAFT_WRITE_ENABLED": "true",
            }
            with patch.dict(os.environ, env, clear=False), patch.object(
                ai_council, "ACTIONS_FILE", root / "state" / "actions.jsonl"
            ), patch.object(ai_council, "ARTIFACTS_DIR", root / "artifacts"), patch.object(
                ai_council, "MEMORY_DB", root / "state" / "memory.sqlite"
            ), patch.object(ai_council, "LOG_DIR", root / "logs"), patch.object(
                ai_council, "AUDIT_LOG", root / "logs" / "audit.jsonl"
            ), patch.object(ai_council, "google_oauth_configured", return_value=True), patch.object(
                ai_council, "google_access_token", return_value=("available", "gmail-access-token")
            ), patch.object(ai_council, "request_json", side_effect=fake_request_json) as request_json:
                action = ai_council.create_integration_draft_action("gmail", "napisz duplicate draft", risk="R3")
                ai_council.approve_response(action["action_id"])
                ai_council.execute_response(action["action_id"])
                ai_council.verify_response(action["action_id"])
                ready = ai_council.get_latest_action(action["action_id"])
                payload = {**(ready["payload"] or {})}
                payload["missing_fields"] = []
                payload["draft"] = {
                    "to": "client@example.com",
                    "subject": "Duplicate draft",
                    "body": "Should be blocked by read-before-write.",
                }
                ai_council.append_jsonl(ai_council.ACTIONS_FILE, {**ready, "updated_at": ai_council.utc_now(), "payload": payload})
                ai_council.provider_response(f"plan {action['action_id']}")
                ai_council.provider_response(f"verify {action['action_id']}")
                request = ai_council.provider_response(f"request {action['action_id']}")
                request_id = re.search(r"id: (act-[A-Za-z0-9_.-]+)", request).group(1)
                token = (ai_council.get_latest_action(request_id)["payload"] or {}).get("confirm_token")
                ai_council.approve_response(request_id)
                executed = ai_council.provider_response(f"execute {request_id} {token}")
                latest = ai_council.get_latest_action(request_id)

        self.assertIn("read-before-write", executed)
        self.assertIn("external_write_performed: false", executed)
        self.assertEqual(latest["status"], "write_blocked")
        self.assertEqual((latest["payload"] or {})["provider_read_before_write"]["status"], "conflict")
        self.assertEqual(request_json.call_count, 2)

    def test_calendar_provider_read_before_write_blocks_duplicate_event_before_post(self):
        def fake_request_json(url: str, **kwargs):
            if "singleEvents=true" in url:
                return {
                    "items": [
                        {
                            "id": "evt-dup",
                            "summary": "Duplicate event",
                            "start": {"dateTime": "2026-06-08T10:00:00+02:00"},
                            "end": {"dateTime": "2026-06-08T10:30:00+02:00"},
                            "htmlLink": "https://calendar.google.com/event?eid=evt-dup",
                        }
                    ]
                }
            raise AssertionError("Calendar event POST should not be called")

        with temp_dir() as tmp:
            root = Path(tmp)
            env = {
                "AI_COUNCIL_PROVIDER_WRITE_ENABLED": "true",
                "AI_COUNCIL_CALENDAR_EVENT_WRITE_ENABLED": "true",
            }
            with patch.dict(os.environ, env, clear=False), patch.object(
                ai_council, "ACTIONS_FILE", root / "state" / "actions.jsonl"
            ), patch.object(ai_council, "ARTIFACTS_DIR", root / "artifacts"), patch.object(
                ai_council, "MEMORY_DB", root / "state" / "memory.sqlite"
            ), patch.object(ai_council, "LOG_DIR", root / "logs"), patch.object(
                ai_council, "AUDIT_LOG", root / "logs" / "audit.jsonl"
            ), patch.object(ai_council, "google_oauth_configured", return_value=True), patch.object(
                ai_council, "google_access_token", return_value=("available", "calendar-access-token")
            ), patch.object(ai_council, "request_json", side_effect=fake_request_json) as request_json:
                action = ai_council.create_integration_draft_action("calendar", "umów duplicate event", risk="R3")
                ai_council.approve_response(action["action_id"])
                ai_council.execute_response(action["action_id"])
                ai_council.verify_response(action["action_id"])
                ready = ai_council.get_latest_action(action["action_id"])
                payload = {**(ready["payload"] or {})}
                payload["missing_fields"] = []
                payload["draft"] = {
                    "summary": "Duplicate event",
                    "start": "2026-06-08T10:00:00+02:00",
                    "end": "2026-06-08T10:30:00+02:00",
                    "timezone": "Europe/Warsaw",
                    "attendees": [],
                    "description": "Should be blocked by read-before-write.",
                }
                ai_council.append_jsonl(ai_council.ACTIONS_FILE, {**ready, "updated_at": ai_council.utc_now(), "payload": payload})
                ai_council.provider_response(f"plan {action['action_id']}")
                ai_council.provider_response(f"verify {action['action_id']}")
                request = ai_council.provider_response(f"request {action['action_id']}")
                request_id = re.search(r"id: (act-[A-Za-z0-9_.-]+)", request).group(1)
                token = (ai_council.get_latest_action(request_id)["payload"] or {}).get("confirm_token")
                ai_council.approve_response(request_id)
                executed = ai_council.provider_response(f"execute {request_id} {token}")
                latest = ai_council.get_latest_action(request_id)

        self.assertIn("read-before-write", executed)
        self.assertIn("external_write_performed: false", executed)
        self.assertEqual(latest["status"], "write_blocked")
        self.assertEqual((latest["payload"] or {})["provider_read_before_write"]["status"], "conflict")
        self.assertEqual(request_json.call_count, 1)

    def test_drive_provider_read_before_write_blocks_duplicate_document_before_upload(self):
        def fake_drive_list(url: str, **kwargs):
            return {
                "files": [
                    {
                        "id": "drive-file-dup",
                        "name": "Duplicate document",
                        "mimeType": "application/vnd.google-apps.document",
                        "webViewLink": "https://docs.google.com/document/d/drive-file-dup/edit",
                    }
                ]
            }

        with temp_dir() as tmp:
            root = Path(tmp)
            env = {
                "AI_COUNCIL_PROVIDER_WRITE_ENABLED": "true",
                "AI_COUNCIL_DRIVE_FILE_WRITE_ENABLED": "true",
            }
            with patch.dict(os.environ, env, clear=False), patch.object(
                ai_council, "ACTIONS_FILE", root / "state" / "actions.jsonl"
            ), patch.object(ai_council, "ARTIFACTS_DIR", root / "artifacts"), patch.object(
                ai_council, "MEMORY_DB", root / "state" / "memory.sqlite"
            ), patch.object(ai_council, "LOG_DIR", root / "logs"), patch.object(
                ai_council, "AUDIT_LOG", root / "logs" / "audit.jsonl"
            ), patch.object(ai_council, "google_oauth_configured", return_value=True), patch.object(
                ai_council, "google_access_token", return_value=("available", "google-token")
            ), patch.object(ai_council, "request_json", side_effect=fake_drive_list) as request_json, patch.object(
                ai_council, "request_multipart_related_json", side_effect=AssertionError("Drive upload should not be called")
            ) as upload:
                action = ai_council.create_integration_draft_action("drive", "utwórz duplicate dokument", risk="R3")
                ai_council.approve_response(action["action_id"])
                ai_council.execute_response(action["action_id"])
                ai_council.verify_response(action["action_id"])
                ready = ai_council.get_latest_action(action["action_id"])
                payload = {**(ready["payload"] or {})}
                payload["missing_fields"] = []
                payload["draft"] = {
                    "title": "Duplicate document",
                    "body": "Should be blocked by read-before-write.",
                    "outline": ["Cel", "Zakres"],
                }
                ai_council.append_jsonl(ai_council.ACTIONS_FILE, {**ready, "updated_at": ai_council.utc_now(), "payload": payload})
                ai_council.provider_response(f"plan {action['action_id']}")
                ai_council.provider_response(f"verify {action['action_id']}")
                request = ai_council.provider_response(f"request {action['action_id']}")
                request_id = re.search(r"id: (act-[A-Za-z0-9_.-]+)", request).group(1)
                token = (ai_council.get_latest_action(request_id)["payload"] or {}).get("confirm_token")
                ai_council.approve_response(request_id)
                executed = ai_council.provider_response(f"execute {request_id} {token}")
                latest = ai_council.get_latest_action(request_id)

        self.assertIn("read-before-write", executed)
        self.assertIn("external_write_performed: false", executed)
        self.assertEqual(latest["status"], "write_blocked")
        self.assertEqual((latest["payload"] or {})["provider_read_before_write"]["status"], "conflict")
        self.assertEqual(request_json.call_count, 1)
        self.assertEqual(upload.call_count, 0)

    def test_github_provider_write_request_blocks_when_token_missing_at_execute(self):
        with temp_dir() as tmp:
            root = Path(tmp)
            env = {
                "AI_COUNCIL_PROVIDER_WRITE_ENABLED": "true",
                "AI_COUNCIL_GITHUB_ISSUE_WRITE_ENABLED": "true",
                "AI_COUNCIL_GITHUB_REPO": "Acoste616/AIagent",
            }
            with patch.dict(os.environ, env, clear=False), patch.object(
                ai_council, "ACTIONS_FILE", root / "state" / "actions.jsonl"
            ), patch.object(ai_council, "ARTIFACTS_DIR", root / "artifacts"), patch.object(
                ai_council, "MEMORY_DB", root / "state" / "memory.sqlite"
            ), patch.object(ai_council, "LOG_DIR", root / "logs"), patch.object(
                ai_council, "AUDIT_LOG", root / "logs" / "audit.jsonl"
            ), patch.object(ai_council, "github_token", return_value="unit-token"):
                action = ai_council.create_integration_draft_action("github", "otwórz issue o brakującym tokenie", risk="R3")
                ai_council.approve_response(action["action_id"])
                ai_council.execute_response(action["action_id"])
                ai_council.verify_response(action["action_id"])
                ready = ai_council.get_latest_action(action["action_id"])
                payload = {**(ready["payload"] or {})}
                payload["missing_fields"] = []
                payload["draft"] = {
                    "repo": "Acoste616/AIagent",
                    "title": "Token gate test",
                    "body": "Should not execute without token at execute time.",
                    "labels": [],
                }
                ai_council.append_jsonl(ai_council.ACTIONS_FILE, {**ready, "updated_at": ai_council.utc_now(), "payload": payload})
                ai_council.provider_response(f"plan {action['action_id']}")
                ai_council.provider_response(f"verify {action['action_id']}")
                request = ai_council.provider_response(f"request {action['action_id']}")
                request_id = re.search(r"id: (act-[A-Za-z0-9_.-]+)", request).group(1)
                token = (ai_council.get_latest_action(request_id)["payload"] or {}).get("confirm_token")
                ai_council.approve_response(request_id)

            with patch.dict(os.environ, env, clear=False), patch.object(
                ai_council, "ACTIONS_FILE", root / "state" / "actions.jsonl"
            ), patch.object(ai_council, "ARTIFACTS_DIR", root / "artifacts"), patch.object(
                ai_council, "MEMORY_DB", root / "state" / "memory.sqlite"
            ), patch.object(ai_council, "LOG_DIR", root / "logs"), patch.object(
                ai_council, "AUDIT_LOG", root / "logs" / "audit.jsonl"
            ), patch.object(ai_council, "github_token", return_value=""), patch.object(
                ai_council, "request_json", side_effect=AssertionError("provider API should not be called")
            ):
                executed = ai_council.provider_response(f"execute {request_id} {token}")
                latest = ai_council.get_latest_action(request_id)
                dry_run = (latest["payload"] or {}).get("provider_write_dry_run") or {}
                dry_run_exists = Path(dry_run["json_path"]).exists()

        self.assertIn("GITHUB_TOKEN/GH_TOKEN missing", executed)
        self.assertIn("external_write_performed: false", executed)
        self.assertEqual(latest["status"], "write_blocked")
        self.assertTrue(dry_run_exists)

    def test_provider_write_request_readiness_blocks_missing_fields_and_auth(self):
        with temp_dir() as tmp:
            root = Path(tmp)
            with patch.object(ai_council, "ACTIONS_FILE", root / "state" / "actions.jsonl"), patch.object(
                ai_council, "ARTIFACTS_DIR", root / "artifacts"
            ), patch.object(ai_council, "MEMORY_DB", root / "state" / "memory.sqlite"), patch.object(
                ai_council, "LOG_DIR", root / "logs"
            ), patch.object(ai_council, "AUDIT_LOG", root / "logs" / "audit.jsonl"), patch.object(
                ai_council, "google_oauth_configured", return_value=True
            ):
                action = ai_council.create_integration_draft_action("calendar", "umów spotkanie z zespołem jutro", risk="R3")
                ai_council.approve_response(action["action_id"])
                ai_council.execute_response(action["action_id"])
                ai_council.verify_response(action["action_id"])
                ai_council.provider_response(f"plan {action['action_id']}")
                ai_council.provider_response(f"verify {action['action_id']}")
                missing = ai_council.provider_response(f"request {action['action_id']}")

            with patch.object(ai_council, "ACTIONS_FILE", root / "state2" / "actions.jsonl"), patch.object(
                ai_council, "ARTIFACTS_DIR", root / "artifacts2"
            ), patch.object(ai_council, "MEMORY_DB", root / "state2" / "memory.sqlite"), patch.object(
                ai_council, "LOG_DIR", root / "logs2"
            ), patch.object(ai_council, "AUDIT_LOG", root / "logs2" / "audit.jsonl"), patch.object(
                ai_council, "google_oauth_configured", return_value=False
            ):
                action = ai_council.create_integration_draft_action("calendar", "umów spotkanie z zespołem jutro", risk="R3")
                ai_council.approve_response(action["action_id"])
                ai_council.execute_response(action["action_id"])
                ai_council.verify_response(action["action_id"])
                ready = ai_council.get_latest_action(action["action_id"])
                payload = {**(ready["payload"] or {}), "missing_fields": []}
                ai_council.append_jsonl(ai_council.ACTIONS_FILE, {**ready, "updated_at": ai_council.utc_now(), "payload": payload})
                ai_council.provider_response(f"plan {action['action_id']}")
                ai_council.provider_response(f"verify {action['action_id']}")
                auth = ai_council.provider_response(f"request {action['action_id']}")

        self.assertIn("missing_fields:", missing)
        self.assertIn("auth not configured", auth)

    def test_provider_write_request_verify_failure_sets_verify_failed(self):
        with temp_dir() as tmp:
            root = Path(tmp)
            with patch.object(ai_council, "ACTIONS_FILE", root / "state" / "actions.jsonl"), patch.object(
                ai_council, "ARTIFACTS_DIR", root / "artifacts"
            ), patch.object(ai_council, "MEMORY_DB", root / "state" / "memory.sqlite"), patch.object(
                ai_council, "LOG_DIR", root / "logs"
            ), patch.object(ai_council, "AUDIT_LOG", root / "logs" / "audit.jsonl"), patch.object(
                ai_council, "google_oauth_configured", return_value=True
            ):
                action = ai_council.create_integration_draft_action("calendar", "umów spotkanie z zespołem jutro", risk="R3")
                ai_council.approve_response(action["action_id"])
                ai_council.execute_response(action["action_id"])
                ai_council.verify_response(action["action_id"])
                ready = ai_council.get_latest_action(action["action_id"])
                payload = {**(ready["payload"] or {}), "missing_fields": []}
                payload["draft"] = {
                    "summary": "Spotkanie zespołu",
                    "start": "2026-06-08T10:00:00+02:00",
                    "end": "2026-06-08T10:30:00+02:00",
                    "attendees": ["team@example.com"],
                    "description": "Plan wdrożenia AI Council",
                }
                ai_council.append_jsonl(ai_council.ACTIONS_FILE, {**ready, "updated_at": ai_council.utc_now(), "payload": payload})
                ai_council.provider_response(f"plan {action['action_id']}")
                ai_council.provider_response(f"verify {action['action_id']}")
                request = ai_council.provider_response(f"request {action['action_id']}")
                request_id = re.search(r"id: (act-[A-Za-z0-9_.-]+)", request).group(1)
                token = (ai_council.get_latest_action(request_id)["payload"] or {}).get("confirm_token")
                ai_council.approve_response(request_id)
                ai_council.provider_response(f"execute {request_id} {token}")
                latest = ai_council.get_latest_action(request_id)
                dry_run = (latest["payload"] or {}).get("provider_write_dry_run") or {}
                Path(dry_run["json_path"]).unlink()
                failed = ai_council.provider_response(f"verify {request_id}")
                latest = ai_council.get_latest_action(request_id)

        self.assertIn("FAILED", failed)
        self.assertIn("provider write dry-run missing", failed)
        self.assertEqual(latest["status"], "verify_failed")

    def test_agent_inbox_surfaces_integration_draft_approval(self):
        with temp_dir() as tmp:
            root = Path(tmp)
            with patch.object(ai_council, "TASKS_FILE", root / "state" / "tasks.jsonl"), patch.object(
                ai_council, "ACTIONS_FILE", root / "state" / "actions.jsonl"
            ), patch.object(ai_council, "IMPROVEMENTS_FILE", root / "state" / "improvements.jsonl"), patch.object(
                ai_council, "NUDGES_FILE", root / "state" / "nudges.jsonl"
            ), patch.object(ai_council, "ERRORS_FILE", root / "state" / "errors.jsonl"), patch.object(
                ai_council, "COSTS_FILE", root / "state" / "costs.jsonl"
            ), patch.object(ai_council, "LOG_DIR", root / "logs"), patch.object(ai_council, "AUDIT_LOG", root / "logs" / "audit.jsonl"):
                action = ai_council.create_integration_draft_action("github", "otwórz issue o L4.28 draftach", risk="R3")
                inbox = ai_council.agent_response()

        self.assertIn(action["action_id"], inbox)
        self.assertIn("requires explicit approval", inbox)

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

    def test_operator_reservation_counts_against_daily_limit(self):
        with temp_dir() as tmp:
            root = Path(tmp)
            with patch.object(ai_council, "CONTROL_FILE", root / "state" / "control.json"), patch.object(
                ai_council, "COSTS_FILE", root / "state" / "costs.jsonl"
            ), patch.object(ai_council, "COST_LOCK_FILE", root / "state" / "costs.lock"), patch.dict(
                os.environ,
                {"GROK_DAILY_CALL_LIMIT": "1", "GROK_DAILY_BUDGET_USD": "10"},
                clear=False,
            ):
                allowed, _, reservation = ai_council.reserve_operator_call("grok", task_id="task-1")
                second_allowed, second_reason, second_reservation = ai_council.reserve_operator_call("grok", task_id="task-2")
                cost = ai_council.cost_response()

        self.assertTrue(allowed)
        self.assertIsNotNone(reservation)
        self.assertFalse(second_allowed)
        self.assertIsNone(second_reservation)
        self.assertIn("call limit", second_reason)
        self.assertIn("grok: calls=1", cost)

    def test_operator_reservation_block_detail_keeps_reason(self):
        with temp_dir() as tmp:
            root = Path(tmp)
            with patch.object(ai_council, "CONTROL_FILE", root / "state" / "control.json"), patch.object(
                ai_council, "COSTS_FILE", root / "state" / "costs.jsonl"
            ), patch.object(ai_council, "COST_LOCK_FILE", root / "state" / "costs.lock"), patch.dict(
                os.environ,
                {"GROK_DAILY_CALL_LIMIT": "0", "GROK_DAILY_BUDGET_USD": "0"},
                clear=False,
            ):
                ai_council.control_response("pause models test pause")
                allowed, reason, reservation = ai_council.reserve_operator_call("grok", detail="poke_chat")
                rows = ai_council.usage_today("grok")

        self.assertFalse(allowed)
        self.assertIsNone(reservation)
        self.assertIn("model calls paused", reason)
        self.assertIn("poke_chat: model calls paused", rows[0]["detail"])

    def test_operator_reservation_finalization_is_not_double_counted(self):
        with temp_dir() as tmp:
            root = Path(tmp)
            with patch.object(ai_council, "CONTROL_FILE", root / "state" / "control.json"), patch.object(
                ai_council, "COSTS_FILE", root / "state" / "costs.jsonl"
            ), patch.object(ai_council, "COST_LOCK_FILE", root / "state" / "costs.lock"), patch.dict(
                os.environ,
                {"GROK_DAILY_CALL_LIMIT": "10", "GROK_DAILY_BUDGET_USD": "10"},
                clear=False,
            ):
                allowed, _, reservation = ai_council.reserve_operator_call("grok", task_id="task-1")
                ai_council.finalize_operator_call(reservation, status="completed", duration_ms=123, detail="done")
                collapsed = ai_council.usage_today("grok")
                raw = ai_council.usage_today("grok", collapsed=False)
                cost = ai_council.cost_response()

        self.assertTrue(allowed)
        self.assertEqual(len(raw), 2)
        self.assertEqual(len(collapsed), 1)
        self.assertEqual(collapsed[0]["status"], "completed")
        self.assertIn("grok: calls=1", cost)

    def test_control_kill_switch_blocks_model_calls(self):
        with temp_dir() as tmp:
            root = Path(tmp)
            with patch.object(ai_council, "CONTROL_FILE", root / "state" / "control.json"), patch.object(
                ai_council, "COSTS_FILE", root / "state" / "costs.jsonl"
            ), patch.object(ai_council, "LOG_DIR", root / "logs"), patch.object(
                ai_council, "AUDIT_LOG", root / "logs" / "audit.jsonl"
            ):
                killed = ai_council.control_response("kill test stop")
                allowed, reason = ai_council.operator_call_allowed("codex")
                resumed = ai_council.control_response("resume all")
                allowed_after, _ = ai_council.operator_call_allowed("codex")

        self.assertIn("global_kill_switch: True", killed)
        self.assertFalse(allowed)
        self.assertIn("kill switch", reason)
        self.assertIn("global_kill_switch: False", resumed)
        self.assertTrue(allowed_after)

    def test_control_total_daily_call_limit_blocks_all_operators(self):
        with temp_dir() as tmp:
            root = Path(tmp)
            with patch.object(ai_council, "CONTROL_FILE", root / "state" / "control.json"), patch.object(
                ai_council, "COSTS_FILE", root / "state" / "costs.jsonl"
            ), patch.object(ai_council, "LOG_DIR", root / "logs"), patch.object(
                ai_council, "AUDIT_LOG", root / "logs" / "audit.jsonl"
            ):
                ai_council.control_response("set total-calls 1")
                ai_council.record_operator_usage("codex", task_id="task-1", duration_ms=10)
                allowed, reason = ai_council.operator_call_allowed("claude")
                cost = ai_council.cost_response()

        self.assertFalse(allowed)
        self.assertIn("Global daily call limit", reason)
        self.assertIn("total_call_limit=1", cost)

    def test_control_total_budget_limit_blocks_next_estimated_call(self):
        with temp_dir() as tmp:
            root = Path(tmp)
            with patch.object(ai_council, "CONTROL_FILE", root / "state" / "control.json"), patch.object(
                ai_council, "COSTS_FILE", root / "state" / "costs.jsonl"
            ), patch.object(ai_council, "LOG_DIR", root / "logs"), patch.object(
                ai_council, "AUDIT_LOG", root / "logs" / "audit.jsonl"
            ), patch.dict(os.environ, {"AI_COUNCIL_CODEX_ESTIMATED_COST_USD": "0.25"}, clear=False):
                ai_council.control_response("set total-budget 0.10")
                allowed, reason = ai_council.operator_call_allowed("codex")

        self.assertFalse(allowed)
        self.assertIn("Global estimated budget", reason)

    def test_control_per_operator_limit_blocks_matching_operator_only(self):
        with temp_dir() as tmp:
            root = Path(tmp)
            with patch.object(ai_council, "CONTROL_FILE", root / "state" / "control.json"), patch.object(
                ai_council, "COSTS_FILE", root / "state" / "costs.jsonl"
            ), patch.object(ai_council, "LOG_DIR", root / "logs"), patch.object(
                ai_council, "AUDIT_LOG", root / "logs" / "audit.jsonl"
            ):
                ai_council.control_response("set operator codex calls 1")
                ai_council.record_operator_usage("codex", task_id="task-1", duration_ms=10)
                codex_allowed, codex_reason = ai_council.operator_call_allowed("codex")
                claude_allowed, _ = ai_council.operator_call_allowed("claude")

        self.assertFalse(codex_allowed)
        self.assertIn("codex daily call limit", codex_reason)
        self.assertTrue(claude_allowed)

    def test_control_write_requires_allowed_chat_when_chat_id_present(self):
        with temp_dir() as tmp:
            root = Path(tmp)
            with patch.object(ai_council, "CONTROL_FILE", root / "state" / "control.json"), patch.dict(
                os.environ, {"TELEGRAM_ALLOWED_CHAT_ID": "553"}, clear=False
            ):
                denied = ai_council.control_response("kill nope", chat_id="999")
                status = ai_council.control_response("status", chat_id="999")

        self.assertIn("unauthorized", denied)
        self.assertIn("global_kill_switch: False", status)

    def test_control_invalid_file_fails_closed_for_model_calls(self):
        with temp_dir() as tmp:
            root = Path(tmp)
            control_file = root / "state" / "control.json"
            control_file.parent.mkdir(parents=True, exist_ok=True)
            control_file.write_text("{bad json", encoding="utf-8")
            with patch.object(ai_council, "CONTROL_FILE", control_file), patch.object(
                ai_council, "COSTS_FILE", root / "state" / "costs.jsonl"
            ):
                allowed, reason = ai_council.operator_call_allowed("codex")
                status = ai_council.control_response("status")

        self.assertFalse(allowed)
        self.assertIn("invalid control file", reason)
        self.assertIn("control_file_error", status)

    def test_control_pause_blocks_proactive_scan(self):
        with temp_dir() as tmp:
            root = Path(tmp)
            with patch.object(ai_council, "CONTROL_FILE", root / "state" / "control.json"), patch.object(
                ai_council, "NUDGES_FILE", root / "state" / "nudges.jsonl"
            ), patch.object(ai_council, "ERRORS_FILE", root / "state" / "errors.jsonl"), patch.object(
                ai_council, "ERRORS_DIR", root / "errors"
            ), patch.object(
                ai_council, "ACTIONS_FILE", root / "state" / "actions.jsonl"
            ), patch.object(
                ai_council, "TASKS_FILE", root / "state" / "tasks.jsonl"
            ), patch.object(ai_council, "IMPROVEMENTS_FILE", root / "state" / "improvements.jsonl"
            ), patch.object(ai_council, "COSTS_FILE", root / "state" / "costs.jsonl"), patch.object(
                ai_council, "LOG_DIR", root / "logs"
            ), patch.object(ai_council, "AUDIT_LOG", root / "logs" / "audit.jsonl"), patch.dict(
                os.environ, {"AI_COUNCIL_PROACTIVE_EVENT_BRAIN": "true"}, clear=False
            ):
                ai_council.record_error("test", message="boom", severity="warning")
                ai_council.control_response("pause proactive test")
                blocked = ai_council.run_proactive_scan(send=False)
                ai_council.control_response("resume proactive")
                created = ai_council.run_proactive_scan(send=False)

        self.assertEqual(blocked, 0)
        self.assertEqual(created, 1)

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
                verified_action = ai_council.latest_by_id(root / "actions.jsonl", "action_id", limit=1)[0]
                rolled_back = ai_council.rollback_response(action["action_id"])
                rollback_verified = ai_council.verify_response(action["action_id"])
                latest = ai_council.latest_by_id(root / "actions.jsonl", "action_id", limit=1)[0]

        self.assertEqual(action["risk"], "R1")
        self.assertIn("Approved + executed", executed)
        self.assertIn("OK", verified)
        self.assertIn("write content", verified)
        self.assertEqual(verified_action["status"], "verified")
        self.assertEqual(verified_action["verification_status"], "verified")
        self.assertIn("Rollback executed", rolled_back)
        self.assertIn("OK", rollback_verified)
        self.assertFalse(target.exists())
        self.assertEqual(latest["status"], "rolled_back")
        self.assertEqual(latest["verification_status"], "verified")

    def test_verify_failure_persists_and_rollback_still_works(self):
        with temp_dir() as tmp:
            root = Path(tmp)
            workspaces = root / "workspaces"
            target = workspaces / "shared" / "hello.txt"
            with patch.object(ai_council, "WORKSPACES_DIR", workspaces), patch.object(
                ai_council, "ACTIONS_FILE", root / "actions.jsonl"
            ), patch.object(ai_council, "MEMORY_DB", root / "memory.sqlite"), patch.object(
                ai_council, "LOG_DIR", root / "logs"
            ), patch.object(ai_council, "AUDIT_LOG", root / "logs" / "audit.jsonl"):
                action = ai_council.create_workspace_write_action("shared/hello.txt = expected")
                ai_council.execute_response(action["action_id"])
                target.write_text("tampered", encoding="utf-8")
                failed = ai_council.verify_response(action["action_id"])
                failed_action = ai_council.latest_by_id(root / "actions.jsonl", "action_id", limit=1)[0]
                rolled_back = ai_council.rollback_response(action["action_id"])
                latest = ai_council.latest_by_id(root / "actions.jsonl", "action_id", limit=1)[0]

        self.assertIn("FAILED", failed)
        self.assertNotIn("[Verifier] OK", failed)
        self.assertEqual(failed_action["status"], "verify_failed")
        self.assertEqual(failed_action["verification_status"], "failed")
        self.assertIn("Rollback executed", rolled_back)
        self.assertFalse(target.exists())
        self.assertEqual(latest["status"], "rolled_back")

    def test_verify_pending_action_does_not_unlock_rollback(self):
        with temp_dir() as tmp:
            root = Path(tmp)
            workspaces = root / "workspaces"
            target = workspaces / "shared" / "hello.txt"
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text("original", encoding="utf-8")
            with patch.object(ai_council, "WORKSPACES_DIR", workspaces), patch.object(
                ai_council, "ACTIONS_FILE", root / "actions.jsonl"
            ), patch.object(ai_council, "MEMORY_DB", root / "memory.sqlite"), patch.object(
                ai_council, "LOG_DIR", root / "logs"
            ), patch.object(ai_council, "AUDIT_LOG", root / "logs" / "audit.jsonl"):
                action = ai_council.create_workspace_write_action("shared/hello.txt = expected")
                target.write_text("legit later change", encoding="utf-8")
                failed = ai_council.verify_response(action["action_id"])
                after_verify = ai_council.latest_by_id(root / "actions.jsonl", "action_id", limit=1)[0]
                rollback = ai_council.rollback_response(action["action_id"])
                final_content = target.read_text(encoding="utf-8")

        self.assertIn("FAILED", failed)
        self.assertIn("not executed", failed)
        self.assertEqual(after_verify["status"], "pending")
        self.assertIn("Rollback wymaga executed/verified/verify_failed", rollback)
        self.assertEqual(final_content, "legit later change")

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
                progress = ai_council.latest_progress_events(task_id)
                spec_path = ai_council.background_job_spec_path(task_id)
                spec = ai_council.load_background_job_spec(task_id)
                spec_exists = spec_path.exists()

        self.assertIn("ETAP: START", response)
        self.assertIn("Postęp: ~5%", response)
        self.assertIn("Robię: /flow / claude-flow / duży plan", response)
        self.assertIn(f"Status: /status {task_id}", response)
        self.assertIn(f"/progress {task_id}", response)
        self.assertIn(f"/details {task_id}", response)
        self.assertEqual(latest["status"], "running_background")
        self.assertEqual(latest["worker_pid"], 4321)
        self.assertEqual(progress[-1]["stage"], "START")
        self.assertTrue(spec_exists)
        self.assertFalse(spec["send_running"])
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

        self.assertTrue(result["summary"].startswith("[Council]"))
        self.assertIn("Tak, działam.", result["summary"])
        self.assertNotIn("[Codex]", result["summary"])
        self.assertEqual(result["raw_output"], "[Codex]\nTak, działam.")
        self.assertEqual(result["report"], "[Codex]\nTak, działam.")
        self.assertIn("Details: /details task-1", result["summary"])

    def test_background_direct_operator_failure_sets_failed_status(self):
        route = {"command": "codex_default", "operators": ["codex"], "prompt": "Działasz?"}
        with patch.object(ai_council, "codex_response", return_value="[Codex] unavailable: timeout"):
            result = ai_council.execute_route_for_background(route, chat_id="", task_id="task-1")

        self.assertEqual(result["status"], "failed")
        self.assertIn("Operator nie wykonał zadania", result["summary"])
        self.assertEqual(result["raw_output"], "[Codex] unavailable: timeout")

    def test_background_worker_sends_running_and_final_progress_messages(self):
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
                events = ai_council.latest_progress_events(task_id, limit=10)
                status_text = ai_council.task_status_response(task_id)
                progress_text = ai_council.progress_response(task_id)

        self.assertEqual(code, 0)
        self.assertEqual(send.call_count, 2)
        running_text = send.call_args_list[0].args[1]
        sent_text = send.call_args_list[1].args[1]
        sent_markup = send.call_args_list[1].args[2]
        self.assertIn("ETAP: RUNNING", running_text)
        self.assertIn(f"Status: /status {task_id}", running_text)
        self.assertIn("Tak, działam.", sent_text)
        self.assertEqual([event["stage"] for event in events], ["PREPARING", "RUNNING", "COLLECTING", "DELIVERING", "COMPLETED"])
        self.assertIn("progress:", status_text)
        self.assertIn("COMPLETED 100%", progress_text)
        callback_data = [
            button["callback_data"]
            for row in sent_markup["inline_keyboard"]
            for button in row
        ]
        self.assertIn(f"details:{task_id}", callback_data)
        self.assertIn(f"facts:{task_id}", callback_data)
        self.assertIn(f"next:{task_id}", callback_data)

    def test_background_worker_cancelled_before_run_does_not_send_running(self):
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
                ai_council, "codex_response", return_value="[Codex]\nNie powinno się wykonać."
            ) as codex, patch.object(ai_council, "telegram_send_message", return_value=True) as send, patch.object(
                ai_council, "telegram_send_message_with_markup", return_value=True
            ) as send_markup:
                task = ai_council.create_task("Działasz?", status="running_background", command="codex_default", operators=["codex"])
                task_id = task["task_id"]
                route = {"command": "codex_default", "operators": ["codex"], "prompt": "Działasz?", "task_id": task_id}
                ai_council.save_background_job_spec(route, "553", task_id, send_progress=True)
                ai_council.update_task_status(task_id, "cancelled", "test pre-cancel")
                code = ai_council.run_background_job(task_id)
                latest = ai_council.get_latest_task(task_id)

        self.assertEqual(code, 0)
        self.assertEqual(latest["status"], "cancelled")
        self.assertEqual(send.call_count, 1)
        self.assertIn("ETAP: CANCELLED", send.call_args.args[1])
        self.assertEqual(send_markup.call_count, 0)
        codex.assert_not_called()

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

    def test_shortcut_url_payload_defaults_to_research_recipe(self):
        with temp_dir() as tmp:
            root = Path(tmp)
            with patch.object(ai_council, "TASKS_FILE", root / "state" / "tasks.jsonl"), patch.object(
                ai_council, "BACKGROUND_JOBS_FILE", root / "state" / "background_jobs.jsonl"
            ), patch.object(ai_council, "BACKGROUND_JOB_SPECS_DIR", root / "state" / "background_job_specs"), patch.object(
                ai_council, "LOG_DIR", root / "logs"
            ), patch.object(ai_council, "AUDIT_LOG", root / "logs" / "audit.jsonl"), patch.object(
                ai_council, "start_background_job", return_value="[AI Council] url research started"
            ) as start:
                result = ai_council.process_shortcut_payload(
                    {"url": "https://example.com/poke", "title": "Poke thread", "mode": "url", "send_telegram": False},
                    remote_addr="127.0.0.1",
                )
                task = ai_council.get_latest_task(result["task_id"])
                route = start.call_args.args[0]

        self.assertTrue(result["ok"])
        self.assertEqual(result["status"], "running_background")
        self.assertEqual(result["command"], "/recipe")
        self.assertEqual(task["source"], "iphone_shortcut")
        self.assertIn("run research_brief", task["prompt"])
        self.assertIn("https://example.com/poke", task["prompt"])
        self.assertEqual(route["command"], "/recipe")

    def test_shortcut_action_agent_returns_inbox(self):
        with temp_dir() as tmp:
            root = Path(tmp)
            with patch.object(ai_council, "TASKS_FILE", root / "state" / "tasks.jsonl"), patch.object(
                ai_council, "ACTIONS_FILE", root / "state" / "actions.jsonl"
            ), patch.object(ai_council, "IMPROVEMENTS_FILE", root / "state" / "improvements.jsonl"), patch.object(
                ai_council, "NUDGES_FILE", root / "state" / "nudges.jsonl"
            ), patch.object(ai_council, "ERRORS_FILE", root / "state" / "errors.jsonl"), patch.object(
                ai_council, "COSTS_FILE", root / "state" / "costs.jsonl"
            ), patch.object(ai_council, "LOG_DIR", root / "logs"), patch.object(
                ai_council, "AUDIT_LOG", root / "logs" / "audit.jsonl"
            ):
                result = ai_council.process_shortcut_payload({"action": "agent", "send_telegram": False}, remote_addr="127.0.0.1")

        self.assertTrue(result["ok"])
        self.assertEqual(result["command"], "/agent")
        self.assertIn("Agent Inbox L4.27", result["response"])

    def test_shortcut_mutating_action_is_blocked(self):
        with temp_dir() as tmp:
            root = Path(tmp)
            with patch.object(ai_council, "LOG_DIR", root / "logs"), patch.object(ai_council, "AUDIT_LOG", root / "logs" / "audit.jsonl"):
                result = ai_council.process_shortcut_payload(
                    {"action": "cancel", "task_id": "task-1", "send_telegram": False},
                    remote_addr="127.0.0.1",
                )

        self.assertTrue(result["ok"])
        self.assertEqual(result["status"], "blocked")
        self.assertEqual(result["command"], "/cancel")
        self.assertEqual(result["task_id"], "")
        self.assertIn("wymaga świadomego approval", result["response"])

    def test_shortcut_mode_does_not_hijack_text(self):
        with temp_dir() as tmp:
            root = Path(tmp)
            with patch.object(ai_council, "TASKS_FILE", root / "state" / "tasks.jsonl"), patch.object(
                ai_council, "ARTIFACTS_DIR", root / "artifacts"
            ), patch.object(ai_council, "ARTIFACT_INDEX_FILE", root / "state" / "artifact_index.jsonl"), patch.object(
                ai_council, "MEMORY_DB", root / "state" / "memory.sqlite"
            ), patch.object(ai_council, "LOG_DIR", root / "logs"), patch.object(ai_council, "AUDIT_LOG", root / "logs" / "audit.jsonl"):
                results = [
                    ai_council.process_shortcut_payload(
                        {"mode": mode, "text": "krótkie pytanie " + mode, "send_telegram": False},
                        remote_addr="127.0.0.1",
                    )
                    for mode in ("goal", "agent")
                ]

        for result in results:
            self.assertTrue(result["ok"])
            self.assertEqual(result["command"], "/chat")
            self.assertNotIn("Goal: Bartek Agent OS", result["response"])
            self.assertNotIn("Agent Inbox L4.27", result["response"])

    def test_shortcut_chat_payload_persists_text_for_agent_inbox(self):
        with temp_dir() as tmp:
            root = Path(tmp)
            with patch.object(ai_council, "TASKS_FILE", root / "state" / "tasks.jsonl"), patch.object(
                ai_council, "ARTIFACTS_DIR", root / "artifacts"
            ), patch.object(ai_council, "ARTIFACT_INDEX_FILE", root / "state" / "artifact_index.jsonl"), patch.object(
                ai_council, "MEMORY_DB", root / "state" / "memory.sqlite"
            ), patch.object(ai_council, "ACTIONS_FILE", root / "state" / "actions.jsonl"), patch.object(
                ai_council, "IMPROVEMENTS_FILE", root / "state" / "improvements.jsonl"
            ), patch.object(ai_council, "NUDGES_FILE", root / "state" / "nudges.jsonl"), patch.object(
                ai_council, "ERRORS_FILE", root / "state" / "errors.jsonl"
            ), patch.object(ai_council, "COSTS_FILE", root / "state" / "costs.jsonl"), patch.object(
                ai_council, "LOG_DIR", root / "logs"
            ), patch.object(ai_council, "AUDIT_LOG", root / "logs" / "audit.jsonl"):
                result = ai_council.process_shortcut_payload({"text": "krótkie pytanie", "send_telegram": False}, remote_addr="127.0.0.1")
                task = ai_council.get_latest_task(result["task_id"])
                inbox = ai_council.agent_response()

        self.assertTrue(result["ok"])
        self.assertEqual(result["status"], "responded")
        self.assertEqual(task["source"], "iphone_shortcut_text")
        self.assertEqual(task["status"], "completed")
        self.assertIn("iphone_inputs=1", inbox)
        self.assertIn(result["task_id"], inbox)

    def test_shortcut_chat_payload_idempotency_blocks_duplicate(self):
        with temp_dir() as tmp:
            root = Path(tmp)
            with patch.object(ai_council, "TASKS_FILE", root / "state" / "tasks.jsonl"), patch.object(
                ai_council, "ARTIFACTS_DIR", root / "artifacts"
            ), patch.object(ai_council, "ARTIFACT_INDEX_FILE", root / "state" / "artifact_index.jsonl"), patch.object(
                ai_council, "MEMORY_DB", root / "state" / "memory.sqlite"
            ), patch.object(ai_council, "LOG_DIR", root / "logs"), patch.object(ai_council, "AUDIT_LOG", root / "logs" / "audit.jsonl"):
                payload = {"text": "krótkie pytanie", "idempotency_key": "shortcut-once", "send_telegram": False}
                first = ai_council.process_shortcut_payload(payload, remote_addr="127.0.0.1")
                second = ai_council.process_shortcut_payload(payload, remote_addr="127.0.0.1")
                tasks = ai_council.latest_tasks(limit=10)

        self.assertEqual(first["status"], "responded")
        self.assertEqual(second["status"], "duplicate")
        self.assertEqual(second["task_id"], first["task_id"])
        self.assertEqual(len({task["task_id"] for task in tasks}), 1)

    def test_shortcut_auto_idempotency_is_scoped_by_route(self):
        with temp_dir() as tmp:
            root = Path(tmp)
            with patch.object(ai_council, "TASKS_FILE", root / "state" / "tasks.jsonl"), patch.object(
                ai_council, "BACKGROUND_JOBS_FILE", root / "state" / "background_jobs.jsonl"
            ), patch.object(ai_council, "BACKGROUND_JOB_SPECS_DIR", root / "state" / "background_job_specs"), patch.object(
                ai_council, "ARTIFACTS_DIR", root / "artifacts"
            ), patch.object(ai_council, "ARTIFACT_INDEX_FILE", root / "state" / "artifact_index.jsonl"), patch.object(
                ai_council, "MEMORY_DB", root / "state" / "memory.sqlite"
            ), patch.object(ai_council, "LOG_DIR", root / "logs"), patch.object(
                ai_council, "AUDIT_LOG", root / "logs" / "audit.jsonl"
            ), patch.object(ai_council, "start_background_job", return_value="[AI Council] task started"):
                task_result = ai_council.process_shortcut_payload(
                    {"command": "@research", "text": "krótkie pytanie", "send_telegram": False},
                    remote_addr="127.0.0.1",
                )
                chat_result = ai_council.process_shortcut_payload(
                    {"text": "krótkie pytanie", "send_telegram": False},
                    remote_addr="127.0.0.1",
                )

        self.assertEqual(task_result["status"], "running_background")
        self.assertEqual(chat_result["status"], "responded")
        self.assertNotEqual(task_result["task_id"], chat_result["task_id"])

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

    def test_front_reliability_response_uses_audit_without_network_calls(self):
        with temp_dir() as tmp:
            root = Path(tmp)
            audit_path = root / "logs" / "audit.jsonl"
            lock_path = root / "state" / "telegram_listener.lock"
            offset_path = root / "state" / "telegram_offset"
            lock_path.parent.mkdir(parents=True, exist_ok=True)
            lock_path.write_text("1234", encoding="utf-8")
            offset_path.write_text("43", encoding="utf-8")
            ai_council.append_jsonl(
                audit_path,
                {
                    "timestamp": ai_council.utc_now(),
                    "update_id": 42,
                    "command": "/selftest",
                    "operators": ["host"],
                    "status": "responded",
                    "duration_ms": 7,
                    "send_requested": True,
                },
            )
            with patch.object(ai_council, "AUDIT_LOG", audit_path), patch.object(
                ai_council, "TELEGRAM_LISTENER_LOCK", lock_path
            ), patch.object(ai_council, "OFFSET_FILE", offset_path), patch.object(
                ai_council, "CONTROL_FILE", root / "state" / "control.json"
            ), patch.object(ai_council, "COSTS_FILE", root / "state" / "costs.jsonl"), patch.object(
                ai_council, "ERRORS_FILE", root / "state" / "errors.jsonl"
            ), patch.object(ai_council, "ERRORS_DIR", root / "errors"):
                ai_council.record_operator_usage("grok", status="completed", duration_ms=10)
                response = ai_council.build_response({"command": "/front", "operators": ["host"], "prompt": ""})

        self.assertIn("Front Reliability L4.24", response)
        self.assertIn("last_telegram_update: 42 /selftest responded", response)
        self.assertIn("listener_pid: 1234", response)
        self.assertIn("grok_today: calls=1", response)

    def test_front_reliability_response_reports_paused_models_and_send_failures(self):
        with temp_dir() as tmp:
            root = Path(tmp)
            audit_path = root / "logs" / "audit.jsonl"
            ai_council.append_jsonl(
                audit_path,
                {
                    "timestamp": ai_council.utc_now(),
                    "update_id": 50,
                    "command": "/chat",
                    "operators": ["host"],
                    "status": "send_failed",
                    "duration_ms": 4,
                    "send_requested": True,
                },
            )
            with patch.object(ai_council, "AUDIT_LOG", audit_path), patch.object(
                ai_council, "TELEGRAM_LISTENER_LOCK", root / "state" / "telegram_listener.lock"
            ), patch.object(ai_council, "OFFSET_FILE", root / "state" / "telegram_offset"), patch.object(
                ai_council, "CONTROL_FILE", root / "state" / "control.json"
            ), patch.object(ai_council, "COSTS_FILE", root / "state" / "costs.jsonl"), patch.object(
                ai_council, "ERRORS_FILE", root / "state" / "errors.jsonl"
            ), patch.object(ai_council, "ERRORS_DIR", root / "errors"):
                ai_council.control_response("pause models test")
                response = ai_council.front_reliability_response()

        self.assertIn("były błędy wysyłki Telegram", response)
        self.assertIn("paused=True", response)
        self.assertIn("failed=1", response)

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
        self.assertIn("Dlaczego nie czuje się jeszcze jak Poke", response)
        self.assertIn("Brakuje do Poke-level", response)
        self.assertIn("Progress UX L4.20", response)
        self.assertIn("Unified Front Orchestrator L4.21", response)
        self.assertIn("Project Memory Spine L4.22", response)
        self.assertIn("L4.23 Cost Ledger Reservation", response)
        self.assertIn("L4.24 Poke Front Reliability", response)

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
