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

    def test_callback_approve_routes_to_approve_response(self):
        with patch.object(ai_council, "approve_response", return_value="[Council] Approved: act-1") as approve:
            response, status = ai_council.handle_callback_query({"data": "approve:act-1"})

        approve.assert_called_once_with("act-1")
        self.assertEqual(status, "approved")
        self.assertIn("Approved", response)

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
    def test_plain_message_routes_to_codex(self):
        route = ai_council.route_text("bez prefiksu")

        self.assertEqual(route["command"], "codex_default")
        self.assertEqual(route["operators"], ["codex"])
        self.assertEqual(route["prompt"], "bez prefiksu")

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
        }

        for text, command in cases.items():
            with self.subTest(text=text):
                self.assertEqual(ai_council.route_text(text)["command"], command)

        self.assertEqual(ai_council.route_text("normalne pytanie do codexa")["command"], "codex_default")

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
        background = ["krótkie pytanie", "/flow test", "@claude-flow test", "@codex test", "@grok test", "@research test", "@all test", "/council test"]
        for text in background:
            with self.subTest(text=text):
                self.assertTrue(ai_council.route_should_background(ai_council.route_text(text)))

        foreground = ["@claude test", "/status task-1", "/health", "/write shared/a.txt = ok"]
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
            ), patch.object(ai_council, "telegram_send_message", return_value=True) as send:
                task = ai_council.create_task("Działasz?", status="running_background", command="codex_default", operators=["codex"])
                task_id = task["task_id"]
                route = {"command": "codex_default", "operators": ["codex"], "prompt": "Działasz?", "task_id": task_id}
                ai_council.save_background_job_spec(route, "553", task_id, send_progress=True)
                code = ai_council.run_background_job(task_id)

        self.assertEqual(code, 0)
        self.assertEqual(send.call_count, 1)
        sent_text = send.call_args.args[1]
        self.assertNotIn("RUNNING: worker działa", sent_text)
        self.assertIn("Tak, działam.", sent_text)

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
            ), patch.object(ai_council, "telegram_download_file", side_effect=fake_download):
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
            analysis = ai_council.analyze_downloaded_media(
                {
                    "task_id": "task-audio",
                    "local_path": str(audio),
                    "media": {"kind": "voice", "mime_type": "audio/ogg"},
                }
            )

        self.assertEqual(analysis["status"], "transcription_pending")

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


if __name__ == "__main__":
    unittest.main()
