"""Split from tests/test_ai_council.py (audit 3.3) — classes preserved 1:1."""
# ruff: noqa: F403, F405
import unittest

from council_test_shared import *


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

    def test_subprocess_operator_timeout_is_recorded_as_error(self):
        with temp_dir() as tmp:
            root = Path(tmp)
            with patch.object(ai_council, "ERRORS_FILE", root / "state" / "errors.jsonl"), patch.object(
                ai_council, "ERRORS_DIR", root / "errors"
            ), patch.object(ai_council, "LOG_DIR", root / "logs"), patch.object(
                ai_council, "AUDIT_LOG", root / "logs" / "audit.jsonl"), patch.object(
                ai_council, "reserve_operator_call", return_value=(True, "", {"usage_id": "use-test", "operator": "claude-flow"})
            ), patch.object(ai_council, "finalize_operator_call"), patch(
                "ai_council.subprocess.run", side_effect=subprocess.TimeoutExpired(["claude"], timeout=7)
            ):
                response = ai_council.call_subprocess_operator(
                    "Claude Flow",
                    ["claude", "-p", "plan"],
                    timeout=7,
                    task_id="task-timeout",
                )
                errors = ai_council.read_jsonl(root / "state" / "errors.jsonl")

        self.assertIn("timeout after 7s", response)
        self.assertEqual(errors[0]["context"], "operator_claude-flow")
        self.assertEqual(errors[0]["message"], "Claude Flow timeout after 7s")
        self.assertEqual(errors[0]["event"]["task_id"], "task-timeout")

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

    def test_poke_research_background_creates_claude_handoff_followup(self):
        with temp_dir() as tmp:
            root = Path(tmp)
            task_id = "task-20260608-120000-abcdef"
            route = {"command": "/poke-research", "operators": ["grok"], "prompt": "sklonuj Poke"}
            with patch.object(ai_council, "ARTIFACTS_DIR", root / "artifacts"), patch.object(
                ai_council, "ARTIFACT_INDEX_FILE", root / "state" / "artifact_index.jsonl"
            ), patch.object(ai_council, "ACTIONS_FILE", root / "state" / "actions.jsonl"), patch.object(
                ai_council, "MEMORY_DB", root / "state" / "memory.sqlite"
            ), patch.object(ai_council, "raw_operator_response", return_value="[Grok X Research]\nPoke fact 1\nPoke fact 2"):
                result = ai_council.execute_route_for_background(route, chat_id="553", task_id=task_id)
                artifact = ai_council.save_task_artifacts(task_id, route, result)
                actions = ai_council.read_jsonl(root / "state" / "actions.jsonl")

        self.assertEqual(result["followup"]["command"], "/flow")
        self.assertEqual(len(actions), 1)
        action = actions[0]
        payload = action["payload"]
        self.assertEqual(action["type"], "followup_proposal")
        self.assertEqual(action["status"], "pending")
        self.assertEqual(payload["source_task_id"], task_id)
        self.assertEqual(payload["source_command"], "/poke-research")
        self.assertEqual(payload["recommended_command"], "/flow")
        self.assertEqual(action["risk"], "R0")
        self.assertEqual(payload["risk"], "R0")
        self.assertIn(ai_council.POKE_RESEARCH_HANDOFF_VERSION, payload["recommended_prompt"])
        self.assertIn(str(root / "artifacts" / task_id / "raw.md"), payload["recommended_prompt"])
        self.assertIn(str(root / "artifacts" / task_id / "report.md"), payload["recommended_prompt"])
        self.assertIn("Follow-up ready: /approve", artifact["summary"])
        self.assertEqual(artifact["followup_action_id"], action["action_id"])

    def test_approved_poke_research_handoff_starts_claude_flow(self):
        with temp_dir() as tmp:
            root = Path(tmp)
            task_id = "task-20260608-120000-flowok"
            route = {"command": "/poke-research", "operators": ["grok"], "prompt": "sklonuj Poke"}
            with patch.object(ai_council, "ARTIFACTS_DIR", root / "artifacts"), patch.object(
                ai_council, "ARTIFACT_INDEX_FILE", root / "state" / "artifact_index.jsonl"
            ), patch.object(ai_council, "ACTIONS_FILE", root / "state" / "actions.jsonl"), patch.object(
                ai_council, "TASKS_FILE", root / "state" / "tasks.jsonl"
            ), patch.object(ai_council, "MEMORY_DB", root / "state" / "memory.sqlite"), patch.object(
                ai_council, "BACKGROUND_JOB_SPECS_DIR", root / "state" / "background_job_specs"
            ), patch.object(ai_council, "raw_operator_response", return_value="[Grok X Research]\nPoke fact"), patch.object(
                ai_council, "start_background_job", return_value="[AI Council] Claude Flow started"
            ) as start:
                result = ai_council.execute_route_for_background(route, chat_id="553", task_id=task_id)
                artifact = ai_council.save_task_artifacts(task_id, route, result)
                response = ai_council.approve_response(artifact["followup_action_id"])

        self.assertIn("follow-up started", response)
        start.assert_called_once()
        started_route = start.call_args.args[0]
        self.assertEqual(started_route["command"], "/flow")
        self.assertIn(ai_council.POKE_RESEARCH_HANDOFF_VERSION, started_route["prompt"])

    def test_claude_flow_after_poke_handoff_creates_delegate_followup(self):
        with temp_dir() as tmp:
            root = Path(tmp)
            task_id = "task-20260608-120000-delegate"
            prompt = f"{ai_council.POKE_RESEARCH_HANDOFF_VERSION} Claude Flow handoff po Grok Poke research"
            route = {"command": "/flow", "operators": ["claude-flow"], "prompt": prompt}
            with patch.object(ai_council, "ARTIFACTS_DIR", root / "artifacts"), patch.object(
                ai_council, "ARTIFACT_INDEX_FILE", root / "state" / "artifact_index.jsonl"
            ), patch.object(ai_council, "ACTIONS_FILE", root / "state" / "actions.jsonl"), patch.object(
                ai_council, "MEMORY_DB", root / "state" / "memory.sqlite"
            ), patch.object(ai_council, "raw_operator_response", return_value="[Claude Flow]\nPlan: implementuj minimalny krok"):
                result = ai_council.execute_route_for_background(route, chat_id="553", task_id=task_id)
                artifact = ai_council.save_task_artifacts(task_id, route, result)
                actions = ai_council.read_jsonl(root / "state" / "actions.jsonl")

        self.assertEqual(result["followup"]["command"], "/delegate")
        self.assertEqual(len(actions), 1)
        action = actions[0]
        payload = action["payload"]
        self.assertEqual(action["type"], "followup_proposal")
        self.assertEqual(action["status"], "pending")
        self.assertEqual(action["risk"], "R1")
        self.assertEqual(payload["recommended_command"], "/delegate")
        self.assertEqual(payload["recommended_route"]["operators"], ["grok", "claude-flow", "codex-worker", "host"])
        self.assertIn(ai_council.CLAUDE_DELEGATE_HANDOFF_VERSION, payload["recommended_prompt"])
        self.assertIn(str(root / "artifacts" / task_id / "report.md"), payload["recommended_prompt"])
        self.assertIn("Follow-up ready: /approve", artifact["summary"])

    def test_at_claude_flow_after_poke_handoff_creates_delegate_followup(self):
        with temp_dir() as tmp:
            root = Path(tmp)
            task_id = "task-20260608-120000-atflow"
            prompt = f"{ai_council.POKE_RESEARCH_HANDOFF_VERSION} Claude Flow handoff po Grok Poke research"
            route = {"command": "@claude-flow", "operators": ["claude-flow"], "prompt": prompt}
            with patch.object(ai_council, "ARTIFACTS_DIR", root / "artifacts"), patch.object(
                ai_council, "ARTIFACT_INDEX_FILE", root / "state" / "artifact_index.jsonl"
            ), patch.object(ai_council, "ACTIONS_FILE", root / "state" / "actions.jsonl"), patch.object(
                ai_council, "MEMORY_DB", root / "state" / "memory.sqlite"
            ), patch.object(ai_council, "raw_operator_response", return_value="[Claude Flow]\nPlan: implementuj minimalny krok"):
                result = ai_council.execute_route_for_background(route, chat_id="553", task_id=task_id)
                artifact = ai_council.save_task_artifacts(task_id, route, result)
                actions = ai_council.read_jsonl(root / "state" / "actions.jsonl")

        self.assertEqual(result["followup"]["command"], "/delegate")
        self.assertEqual(len(actions), 1)
        self.assertEqual(actions[0]["payload"]["recommended_command"], "/delegate")
        self.assertIn("Follow-up ready: /approve", artifact["summary"])

    def test_approved_claude_delegate_handoff_creates_delegate_pack(self):
        with temp_dir() as tmp:
            root = Path(tmp)
            task_id = "task-20260608-120000-delegok"
            prompt = f"{ai_council.POKE_RESEARCH_HANDOFF_VERSION} Claude Flow handoff po Grok Poke research"
            route = {"command": "/flow", "operators": ["claude-flow"], "prompt": prompt}
            with patch.object(ai_council, "ARTIFACTS_DIR", root / "artifacts"), patch.object(
                ai_council, "ARTIFACT_INDEX_FILE", root / "state" / "artifact_index.jsonl"
            ), patch.object(ai_council, "ACTIONS_FILE", root / "state" / "actions.jsonl"), patch.object(
                ai_council, "TASKS_FILE", root / "state" / "tasks.jsonl"
            ), patch.object(ai_council, "MEMORY_DB", root / "state" / "memory.sqlite"), patch.object(
                ai_council, "raw_operator_response", return_value="[Claude Flow]\nPlan: implementuj minimalny krok"
            ), patch.object(ai_council, "codex_worker_delegate_response", return_value="[Council] Codex Worker Delegation ready") as delegate:
                result = ai_council.execute_route_for_background(route, chat_id="553", task_id=task_id)
                artifact = ai_council.save_task_artifacts(task_id, route, result)
                response = ai_council.approve_response(artifact["followup_action_id"])

        self.assertIn("follow-up executed", response)
        delegate.assert_called_once()
        self.assertIn(ai_council.CLAUDE_DELEGATE_HANDOFF_VERSION, delegate.call_args.args[0])

    def test_plain_claude_flow_does_not_create_delegate_followup(self):
        with temp_dir() as tmp:
            root = Path(tmp)
            task_id = "task-20260608-120000-plain"
            route = {"command": "/flow", "operators": ["claude-flow"], "prompt": "zrób plan"}
            with patch.object(ai_council, "ARTIFACTS_DIR", root / "artifacts"), patch.object(
                ai_council, "ARTIFACT_INDEX_FILE", root / "state" / "artifact_index.jsonl"
            ), patch.object(ai_council, "ACTIONS_FILE", root / "state" / "actions.jsonl"), patch.object(
                ai_council, "MEMORY_DB", root / "state" / "memory.sqlite"
            ), patch.object(ai_council, "raw_operator_response", return_value="[Claude Flow]\nPlan"):
                result = ai_council.execute_route_for_background(route, chat_id="553", task_id=task_id)
                ai_council.save_task_artifacts(task_id, route, result)
                actions = ai_council.read_jsonl(root / "state" / "actions.jsonl")

        self.assertNotIn("followup", result)
        self.assertEqual(actions, [])

    def test_failed_claude_flow_after_poke_handoff_does_not_create_delegate_followup(self):
        with temp_dir() as tmp:
            root = Path(tmp)
            task_id = "task-20260608-120000-flowbad"
            prompt = f"{ai_council.POKE_RESEARCH_HANDOFF_VERSION} Claude Flow handoff po Grok Poke research"
            route = {"command": "/flow", "operators": ["claude-flow"], "prompt": prompt}
            with patch.object(ai_council, "ARTIFACTS_DIR", root / "artifacts"), patch.object(
                ai_council, "ARTIFACT_INDEX_FILE", root / "state" / "artifact_index.jsonl"
            ), patch.object(ai_council, "ACTIONS_FILE", root / "state" / "actions.jsonl"), patch.object(
                ai_council, "MEMORY_DB", root / "state" / "memory.sqlite"
            ), patch.object(ai_council, "raw_operator_response", return_value="[Claude Flow] timeout after 120s"):
                result = ai_council.execute_route_for_background(route, chat_id="553", task_id=task_id)
                ai_council.save_task_artifacts(task_id, route, result)
                actions = ai_council.read_jsonl(root / "state" / "actions.jsonl")

        self.assertEqual(result["status"], "failed")
        self.assertNotIn("followup", result)
        self.assertEqual(actions, [])

    def test_failed_poke_research_does_not_create_claude_handoff(self):
        with temp_dir() as tmp:
            root = Path(tmp)
            task_id = "task-20260608-120000-badbad"
            route = {"command": "/poke-research", "operators": ["grok"], "prompt": "sklonuj Poke"}
            with patch.object(ai_council, "ARTIFACTS_DIR", root / "artifacts"), patch.object(
                ai_council, "ARTIFACT_INDEX_FILE", root / "state" / "artifact_index.jsonl"
            ), patch.object(ai_council, "ACTIONS_FILE", root / "state" / "actions.jsonl"), patch.object(
                ai_council, "MEMORY_DB", root / "state" / "memory.sqlite"
            ), patch.object(ai_council, "raw_operator_response", return_value="[Grok X Research] error: unavailable"):
                result = ai_council.execute_route_for_background(route, chat_id="553", task_id=task_id)
                ai_council.save_task_artifacts(task_id, route, result)
                actions = ai_council.read_jsonl(root / "state" / "actions.jsonl")

        self.assertEqual(result["status"], "failed")
        self.assertNotIn("followup", result)
        self.assertEqual(actions, [])

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

    def test_grok_x_research_uses_x_and_web_search_with_current_date(self):
        captured = {}

        def fake_cfg(key: str, default: str = "") -> str:
            if key == "XAI_API_KEY":
                return "test-key"
            return default

        def fake_request_json(url, headers=None, method="GET", payload=None, timeout=30):
            captured["url"] = url
            captured["payload"] = payload
            return {"output": [{"type": "output_text", "text": "Research OK"}]}

        with patch.object(ai_council, "cfg", side_effect=fake_cfg), patch.object(
            ai_council, "reserve_operator_call", return_value=(True, "", {"usage_id": "use-test", "operator": "grok"})
        ), patch.object(ai_council, "finalize_operator_call") as finalize, patch.object(
            ai_council, "memory_context_for_prompt", return_value=""
        ), patch.object(ai_council, "request_json", side_effect=fake_request_json):
            response = ai_council.grok_x_research_response("Poke features", max_chars=500)

        self.assertEqual(captured["url"], "https://api.x.ai/v1/responses")
        tools = captured["payload"]["tools"]
        self.assertEqual([tool["type"] for tool in tools], ["x_search", "web_search"])
        self.assertEqual(tools[0]["from_date"], "2026-03-01")
        self.assertEqual(tools[0]["to_date"], datetime.now(timezone.utc).date().isoformat())
        self.assertIn(ai_council.GROK_RESEARCH_VERSION, response)
        self.assertIn("Research OK", response)
        finalize.assert_called_once()

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

    def test_background_delivery_markup_for_followup_has_approve_and_task_buttons(self):
        markup = ai_council.background_delivery_reply_markup(
            "Research gotowy.\nFollow-up ready: /approve act-20260608-120000-abcdef albo /deny act-20260608-120000-abcdef",
            "task-20260608-120000-fedcba",
        )
        callback_data = [
            button["callback_data"]
            for row in markup["inline_keyboard"]
            for button in row
        ]

        self.assertIn("approve:act-20260608-120000-abcdef", callback_data)
        self.assertIn("deny:act-20260608-120000-abcdef", callback_data)
        self.assertIn("details:task-20260608-120000-fedcba", callback_data)
        self.assertIn("facts:task-20260608-120000-fedcba", callback_data)
        self.assertIn("next:task-20260608-120000-fedcba", callback_data)

    def test_background_delivery_markup_for_claude_flow_followup_has_approve_button(self):
        markup = ai_council.background_delivery_reply_markup(
            "Plan workflow gotowy.\nFollow-up ready: /approve act-20260608-120000-flowup albo /deny act-20260608-120000-flowup",
            "task-20260608-120000-planok",
        )
        callback_data = [
            button["callback_data"]
            for row in markup["inline_keyboard"]
            for button in row
        ]

        self.assertIn("approve:act-20260608-120000-flowup", callback_data)
        self.assertIn("deny:act-20260608-120000-flowup", callback_data)
        self.assertIn("details:task-20260608-120000-planok", callback_data)

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

    def test_recipe_creator_natural_intent_routes_to_recipe_create(self):
        route = ai_council.route_message("stwórz recipe codziennie o 8 health digest")

        self.assertEqual(route["command"], "/recipe")
        self.assertEqual(route["mode"], "recipe_creator")
        self.assertTrue(route["prompt"].startswith("create codziennie o 8"))
        self.assertFalse(ai_council.route_needs_task(route))

    def test_recipe_creator_explicit_name_uses_name_not_preposition(self):
        name = ai_council.recipe_creator_name_from_intent("codziennie o 8 o nazwie smoke_l451_test health digest")

        self.assertEqual(name, "smoke_l451_test")

    def test_recipe_creator_creates_pending_action_not_recipe_file(self):
        with temp_dir() as tmp:
            root = Path(tmp)
            with patch.object(ai_council, "RECIPES_DIR", root / "recipes"), patch.object(
                ai_council, "ACTIONS_FILE", root / "state" / "actions.jsonl"
            ), patch.object(ai_council, "LOG_DIR", root / "logs"), patch.object(
                ai_council, "AUDIT_LOG", root / "logs" / "audit.jsonl"
            ), patch.object(ai_council, "WORKSPACES_DIR", root / "workspaces"), patch.object(
                ai_council, "ARTIFACTS_DIR", root / "artifacts"
            ), patch.object(ai_council, "REPORTS_DIR", root / "reports"), patch.object(
                ai_council, "ERRORS_DIR", root / "errors"
            ), patch.object(ai_council, "BACKGROUND_JOB_SPECS_DIR", root / "state" / "background_job_specs"):
                response = ai_council.recipe_response("create codziennie o 8 health digest")
                actions = ai_council.read_jsonl(root / "state" / "actions.jsonl")
                recipe_files = list((root / "recipes").glob("*.json"))

        self.assertIn("Recipe Creator L4.51", response)
        self.assertIn("Pending action utworzona", response)
        self.assertEqual(actions[0]["type"], "recipe_create")
        self.assertEqual(actions[0]["risk"], "R1")
        self.assertEqual(actions[0]["payload"]["recipe"]["trigger"]["cron"], "0 8 * * *")
        self.assertEqual(recipe_files, [])
        self.assertIsNotNone(ai_council.response_reply_markup(response))

    def test_recipe_creator_approve_saves_disabled_recipe(self):
        with temp_dir() as tmp:
            root = Path(tmp)
            with patch.object(ai_council, "RECIPES_DIR", root / "recipes"), patch.object(
                ai_council, "ACTIONS_FILE", root / "state" / "actions.jsonl"
            ), patch.object(ai_council, "MEMORY_DB", root / "memory.sqlite"), patch.object(
                ai_council, "LOG_DIR", root / "logs"
            ), patch.object(ai_council, "AUDIT_LOG", root / "logs" / "audit.jsonl"), patch.object(
                ai_council, "WORKSPACES_DIR", root / "workspaces"
            ), patch.object(ai_council, "ARTIFACTS_DIR", root / "artifacts"), patch.object(
                ai_council, "REPORTS_DIR", root / "reports"
            ), patch.object(ai_council, "ERRORS_DIR", root / "errors"), patch.object(
                ai_council, "BACKGROUND_JOB_SPECS_DIR", root / "state" / "background_job_specs"):
                create_response = ai_council.recipe_response("create codziennie o 8 health digest")
                action_id = re.search(r"id:\s*(act-[A-Za-z0-9_.-]+)", create_response).group(1)
                approve = ai_council.approve_response(action_id)
                action_rows = ai_council.read_jsonl(root / "state" / "actions.jsonl")
                recipe_name = action_rows[-1]["payload"]["recipe"]["name"]
                recipe = ai_council.load_recipe(recipe_name)

        self.assertIn("Approved + recipe saved", approve)
        self.assertEqual(action_rows[-1]["status"], "executed")
        self.assertIsNotNone(recipe)
        self.assertFalse(recipe["enabled"])
        self.assertEqual(recipe["recipe_version"], "L4.51")
        self.assertEqual(recipe["steps"][0]["command"], "/health")

    def test_recipe_creator_approve_returns_activation_card(self):
        with temp_dir() as tmp:
            root = Path(tmp)
            with patch.object(ai_council, "RECIPES_DIR", root / "recipes"), patch.object(
                ai_council, "ACTIONS_FILE", root / "state" / "actions.jsonl"
            ), patch.object(ai_council, "MEMORY_DB", root / "memory.sqlite"), patch.object(
                ai_council, "LOG_DIR", root / "logs"
            ), patch.object(ai_council, "AUDIT_LOG", root / "logs" / "audit.jsonl"), patch.object(
                ai_council, "WORKSPACES_DIR", root / "workspaces"
            ), patch.object(ai_council, "ARTIFACTS_DIR", root / "artifacts"), patch.object(
                ai_council, "REPORTS_DIR", root / "reports"
            ), patch.object(ai_council, "ERRORS_DIR", root / "errors"), patch.object(
                ai_council, "BACKGROUND_JOB_SPECS_DIR", root / "state" / "background_job_specs"):
                create_response = ai_council.recipe_response("create codziennie o 8 health digest")
                action_id = re.search(r"id:\s*(act-[A-Za-z0-9_.-]+)", create_response).group(1)
                approve = ai_council.approve_response(action_id)
                markup = ai_council.response_reply_markup(approve)

        self.assertIn("Recipe Activation L4.52", approve)
        self.assertIn("activation: recipe health_digest", approve)
        self.assertIsNotNone(markup)
        buttons = [button["text"] for row in markup["inline_keyboard"] for button in row]
        self.assertIn("Test", buttons)
        self.assertIn("Enable", buttons)

    def test_recipe_activation_enable_blocks_custom_recipe_limit(self):
        with temp_dir() as tmp:
            root = Path(tmp)
            with patch.object(ai_council, "RECIPES_DIR", root / "recipes"), patch.dict(
                os.environ, {"AI_COUNCIL_RECIPE_ACTIVE_LIMIT": "5"}, clear=False
            ):
                for index in range(5):
                    ai_council.save_recipe(
                        {
                            "name": f"custom_{index}",
                            "created_by": "recipe_creator_v0",
                            "enabled": True,
                            "steps": [{"command": "/health", "prompt": ""}],
                        }
                    )
                ai_council.save_recipe(
                    {
                        "name": "custom_six",
                        "created_by": "recipe_creator_v0",
                        "enabled": False,
                        "steps": [{"command": "/health", "prompt": ""}],
                    }
                )
                response = ai_council.set_recipe_enabled("custom_six", True)
                recipe = ai_council.load_recipe("custom_six")

        self.assertIn("active custom recipe limit", response)
        self.assertFalse(recipe["enabled"])

    def test_recipe_test_allows_disabled_recipe_without_enabling(self):
        with temp_dir() as tmp:
            root = Path(tmp)
            with patch.object(ai_council, "RECIPES_DIR", root / "recipes"), patch.object(
                ai_council, "LOG_DIR", root / "logs"
            ), patch.object(ai_council, "AUDIT_LOG", root / "logs" / "audit.jsonl"), patch.object(
                ai_council, "WORKSPACES_DIR", root / "workspaces"
            ), patch.object(ai_council, "ARTIFACTS_DIR", root / "artifacts"), patch.object(
                ai_council, "REPORTS_DIR", root / "reports"
            ), patch.object(ai_council, "ERRORS_DIR", root / "errors"):
                ai_council.save_recipe(
                    {
                        "name": "health_digest",
                        "created_by": "recipe_creator_v0",
                        "enabled": False,
                        "steps": [{"command": "/health", "prompt": ""}],
                    }
                )
                run_result = ai_council.run_recipe_background("run health_digest", task_id="task-run")
                test_result = ai_council.run_recipe_background("test health_digest", task_id="task-test")
                recipe = ai_council.load_recipe("health_digest")

        self.assertIn("disabled", run_result["decision"])
        self.assertIn("test zakończony", test_result["decision"])
        self.assertFalse(recipe["enabled"])

    def test_recipe_test_summary_adds_activation_followup(self):
        with temp_dir() as tmp:
            root = Path(tmp)
            with patch.object(ai_council, "RECIPES_DIR", root / "recipes"), patch.object(
                ai_council, "LOG_DIR", root / "logs"
            ), patch.object(ai_council, "AUDIT_LOG", root / "logs" / "audit.jsonl"), patch.object(
                ai_council, "WORKSPACES_DIR", root / "workspaces"
            ), patch.object(ai_council, "ARTIFACTS_DIR", root / "artifacts"), patch.object(
                ai_council, "REPORTS_DIR", root / "reports"
            ), patch.object(ai_council, "ERRORS_DIR", root / "errors"):
                ai_council.save_recipe(
                    {
                        "name": "health_digest",
                        "created_by": "recipe_creator_v0",
                        "enabled": False,
                        "steps": [{"command": "/health", "prompt": ""}],
                    }
                )
                result = ai_council.run_recipe_background("test health_digest", task_id="task-test")
                markup = ai_council.background_delivery_reply_markup(result["summary"], "task-test")

        self.assertIn("Recipe Test Follow-up L4.53", result["summary"])
        self.assertIn("activation: recipe health_digest", result["summary"])
        buttons = [button["text"] for row in markup["inline_keyboard"] for button in row]
        self.assertIn("Enable", buttons)
        self.assertIn("Details", buttons)

    def test_background_delivery_ignores_unanchored_activation_text(self):
        response = "[AI Council] task\nDECYZJA: activation: recipe fake_recipe\nDetails: /details task-1"
        markup = ai_council.background_delivery_reply_markup(response, "task-1")
        buttons = [button["text"] for row in markup["inline_keyboard"] for button in row]

        self.assertIn("Status", buttons)
        self.assertIn("Details", buttons)
        self.assertNotIn("Enable", buttons)

    def test_blocked_recipe_test_has_no_activation_followup_markup(self):
        result = {
            "decision": "Recipe `unsafe_recipe` zablokowana.",
            "facts": ["step 1: /execute is not allowed in recipes"],
            "dispute": "blocked",
            "next_actions": ["/recipe show unsafe_recipe"],
            "ask_user": "Popraw recipe.",
            "raw_output": "blocked",
            "report": "blocked",
            "status": "blocked",
        }
        summary = ai_council.format_telegram_summary(result, "task-blocked")
        markup = ai_council.background_delivery_reply_markup(summary, "task-blocked")
        buttons = [button["text"] for row in markup["inline_keyboard"] for button in row]

        self.assertNotIn("Recipe Test Follow-up", summary)
        self.assertNotIn("Enable", buttons)
        self.assertIn("Details", buttons)

    def test_recipe_activation_callback_enable_uses_policy(self):
        with temp_dir() as tmp:
            root = Path(tmp)
            with patch.object(ai_council, "RECIPES_DIR", root / "recipes"):
                ai_council.save_recipe(
                    {
                        "name": "health_digest",
                        "created_by": "recipe_creator_v0",
                        "enabled": False,
                        "steps": [{"command": "/health", "prompt": ""}],
                    }
                )
                response, status = ai_council.handle_callback_query(
                    {"data": "recipe-enable:health_digest", "message": {"chat": {"id": "1"}}}
                )
                recipe = ai_council.load_recipe("health_digest")

        self.assertEqual(status, "recipe_enable")
        self.assertIn("aktywna", response)
        self.assertTrue(recipe["enabled"])

    def test_recipe_activation_callback_uses_canonical_recipe_token(self):
        with temp_dir() as tmp:
            root = Path(tmp)
            with patch.object(ai_council, "RECIPES_DIR", root / "recipes"):
                ai_council.save_recipe(
                    {
                        "name": "custom long name",
                        "created_by": "recipe_creator_v0",
                        "enabled": False,
                        "steps": [{"command": "/health", "prompt": ""}],
                    }
                )
                summary = ai_council.recipe_activation_summary("custom long name")
                markup = ai_council.response_reply_markup(summary)
                callback_data = markup["inline_keyboard"][0][1]["callback_data"]
                response, status = ai_council.handle_callback_query(
                    {"data": callback_data, "message": {"chat": {"id": "1"}}}
                )
                recipe = ai_council.load_recipe("custom long name")

        self.assertIn("activation: recipe custom_long_name", summary)
        self.assertEqual(callback_data, "recipe-enable:custom_long_name")
        self.assertEqual(status, "recipe_enable")
        self.assertIn("aktywna", response)
        self.assertTrue(recipe["enabled"])

    def test_recipe_test_blocks_unsafe_disabled_recipe(self):
        with temp_dir() as tmp:
            root = Path(tmp)
            with patch.object(ai_council, "RECIPES_DIR", root / "recipes"), patch.object(
                ai_council, "LOG_DIR", root / "logs"
            ), patch.object(ai_council, "AUDIT_LOG", root / "logs" / "audit.jsonl"), patch.object(
                ai_council, "WORKSPACES_DIR", root / "workspaces"
            ), patch.object(ai_council, "ARTIFACTS_DIR", root / "artifacts"), patch.object(
                ai_council, "REPORTS_DIR", root / "reports"
            ), patch.object(ai_council, "ERRORS_DIR", root / "errors"):
                ai_council.save_recipe(
                    {
                        "name": "unsafe_recipe",
                        "created_by": "recipe_creator_v0",
                        "enabled": False,
                        "steps": [{"command": "/execute", "prompt": "act-1"}],
                    }
                )
                result = ai_council.run_recipe_background("test unsafe_recipe", task_id="task-unsafe")

        self.assertIn("zablokowana", result["decision"])
        self.assertTrue(any("/execute" in fact for fact in result["facts"]))

    def test_recipe_creator_blocks_existing_recipe_name_before_action(self):
        with temp_dir() as tmp:
            root = Path(tmp)
            with patch.object(ai_council, "RECIPES_DIR", root / "recipes"), patch.object(
                ai_council, "ACTIONS_FILE", root / "state" / "actions.jsonl"
            ), patch.object(ai_council, "LOG_DIR", root / "logs"), patch.object(
                ai_council, "AUDIT_LOG", root / "logs" / "audit.jsonl"
            ), patch.object(ai_council, "WORKSPACES_DIR", root / "workspaces"), patch.object(
                ai_council, "ARTIFACTS_DIR", root / "artifacts"
            ), patch.object(ai_council, "REPORTS_DIR", root / "reports"), patch.object(
                ai_council, "ERRORS_DIR", root / "errors"
            ), patch.object(ai_council, "BACKGROUND_JOB_SPECS_DIR", root / "state" / "background_job_specs"):
                ai_council.save_recipe(
                    {
                        "name": "health_digest",
                        "description": "existing",
                        "enabled": True,
                        "steps": [{"command": "/health", "prompt": ""}],
                    }
                )
                response = ai_council.recipe_response("create codziennie o 8 health digest")
                actions = ai_council.read_jsonl(root / "state" / "actions.jsonl")
                recipe = ai_council.load_recipe("health_digest")

        self.assertIn("już istnieje", response)
        self.assertEqual(actions, [])
        self.assertEqual(recipe["description"], "existing")
        self.assertTrue(recipe["enabled"])

    def test_recipe_creator_approve_blocks_race_overwrite(self):
        with temp_dir() as tmp:
            root = Path(tmp)
            with patch.object(ai_council, "RECIPES_DIR", root / "recipes"), patch.object(
                ai_council, "ACTIONS_FILE", root / "state" / "actions.jsonl"
            ), patch.object(ai_council, "MEMORY_DB", root / "memory.sqlite"), patch.object(
                ai_council, "LOG_DIR", root / "logs"
            ), patch.object(ai_council, "AUDIT_LOG", root / "logs" / "audit.jsonl"), patch.object(
                ai_council, "WORKSPACES_DIR", root / "workspaces"
            ), patch.object(ai_council, "ARTIFACTS_DIR", root / "artifacts"), patch.object(
                ai_council, "REPORTS_DIR", root / "reports"
            ), patch.object(ai_council, "ERRORS_DIR", root / "errors"), patch.object(
                ai_council, "BACKGROUND_JOB_SPECS_DIR", root / "state" / "background_job_specs"):
                recipe, violations = ai_council.build_recipe_from_intent("codziennie o 8 health digest")
                self.assertEqual(violations, [])
                action = ai_council.create_recipe_action("codziennie o 8 health digest", recipe)
                ai_council.save_recipe(
                    {
                        "name": recipe["name"],
                        "description": "race winner",
                        "enabled": True,
                        "steps": [{"command": "/health", "prompt": ""}],
                    }
                )
                approve = ai_council.approve_response(action["action_id"])
                saved = ai_council.load_recipe(recipe["name"])

        self.assertIn("zablokowane", approve)
        self.assertIn("already exists", approve)
        self.assertEqual(saved["description"], "race winner")
        self.assertTrue(saved["enabled"])

    def test_recipe_creator_allows_readonly_gmail_brief_but_blocks_send(self):
        recipe, violations = ai_council.build_recipe_from_intent("codziennie o 8 podsumuj maile z ostatniej doby")
        blocked_recipe, blocked = ai_council.build_recipe_from_intent("codziennie o 8 wyślij mail do klienta")

        self.assertEqual(violations, [])
        self.assertEqual(recipe["steps"][0]["command"], "/connector")
        self.assertIn("brief gmail", recipe["steps"][0]["prompt"])
        self.assertIsNone(blocked_recipe)
        self.assertTrue(any("external" in item for item in blocked))

    def test_recipe_test_route_runs_in_background(self):
        route = ai_council.route_message("/recipe test health_digest")
        natural = ai_council.route_message("test recipe health_digest")

        self.assertEqual(route["command"], "/recipe")
        self.assertTrue(ai_council.route_needs_task(route))
        self.assertTrue(ai_council.route_should_background(route))
        self.assertEqual(natural["command"], "/recipe")
        self.assertEqual(natural["prompt"], "test health_digest")
        self.assertTrue(ai_council.route_should_background(natural))

    def test_recipe_due_window_matches_simple_cron(self):
        recipe = {"trigger": {"type": "schedule", "cron": "30 8 * * *"}}
        due, window = ai_council.recipe_due_window(recipe, now=datetime(2026, 6, 6, 8, 30, tzinfo=timezone.utc))
        not_due, _ = ai_council.recipe_due_window(recipe, now=datetime(2026, 6, 6, 8, 31, tzinfo=timezone.utc))

        self.assertTrue(due)
        self.assertIn("202606060830", window)
        self.assertFalse(not_due)

    def test_feature_evolution_loop_has_two_due_windows(self):
        recipe = ai_council.default_recipes()["feature_evolution_loop"]
        morning, _ = ai_council.recipe_due_window(recipe, now=datetime(2026, 6, 6, 10, 15, tzinfo=timezone.utc))
        evening, _ = ai_council.recipe_due_window(recipe, now=datetime(2026, 6, 6, 22, 15, tzinfo=timezone.utc))
        not_due, _ = ai_council.recipe_due_window(recipe, now=datetime(2026, 6, 6, 10, 16, tzinfo=timezone.utc))
        next_windows = ai_council.recipe_next_windows(
            recipe, now=datetime(2026, 6, 6, 10, 16, tzinfo=timezone.utc), limit=2
        )
        interval_windows = ai_council.recipe_next_windows({"trigger": {"type": "schedule", "interval_seconds": 60}})

        self.assertTrue(morning)
        self.assertTrue(evening)
        self.assertFalse(not_due)
        self.assertIn("2026-06-06 22:15", next_windows[0])
        self.assertIn("2026-06-07 10:15", next_windows[1])
        self.assertEqual(interval_windows, [])

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
        self.assertTrue(any(step["command"] == "@grok" for step in error_recipe["steps"]))
        self.assertTrue(any("{previous}" in step.get("prompt", "") for step in error_recipe["steps"]))
        self.assertTrue(feature_recipe["enabled"])
        self.assertEqual(feature_recipe["recipe_version"], ai_council.AUTONOMOUS_LOOP_VERSION)
        self.assertEqual(feature_recipe["cadence"], "twice_daily")
        self.assertTrue(feature_recipe["capture_improvement"])
        self.assertTrue(feature_recipe["planner_selectable"])
        self.assertEqual(feature_recipe["trigger"]["cron"], "15 10,22 * * *")
        self.assertTrue(any(step["command"] == "@xresearch" for step in feature_recipe["steps"]))
        self.assertTrue(any("{previous}" in step.get("prompt", "") for step in feature_recipe["steps"]))
        self.assertEqual(recipes["gmail_context_brief"]["source_connectors"], ["gmail"])
        self.assertTrue(any(step["prompt"].startswith("sync gmail") for step in recipes["gmail_context_brief"]["steps"]))
        self.assertTrue(recipes["drive_context_brief"]["planner_selectable"])

    def test_default_loop_recipe_migration_updates_cadence_preserves_enabled(self):
        with temp_dir() as tmp:
            root = Path(tmp)
            recipes_dir = root / "recipes"
            recipes_dir.mkdir(parents=True, exist_ok=True)
            (recipes_dir / "feature_evolution_loop.json").write_text(
                json.dumps(
                    {
                        "name": "feature_evolution_loop",
                        "description": "old",
                        "enabled": False,
                        "trigger": {"type": "schedule", "cron": "15 10 * * *"},
                        "steps": [{"command": "/health", "prompt": ""}],
                    }
                ),
                encoding="utf-8",
            )
            (recipes_dir / "error_audit_twice_daily.json").write_text(
                json.dumps(
                    {
                        "name": "error_audit_twice_daily",
                        "description": "old",
                        "enabled": True,
                        "trigger": {"type": "schedule", "cron": "0 9 * * *"},
                        "steps": [{"command": "/health", "prompt": ""}],
                    }
                ),
                encoding="utf-8",
            )
            with patch.object(ai_council, "PROJECT_DIR", root), patch.object(
                ai_council, "STATE_DIR", root / "state"
            ), patch.object(ai_council, "LOG_DIR", root / "logs"), patch.object(
                ai_council, "WORKSPACES_DIR", root / "workspaces"
            ), patch.object(ai_council, "ARTIFACTS_DIR", root / "artifacts"), patch.object(
                ai_council, "REPORTS_DIR", root / "reports"
            ), patch.object(ai_council, "ERRORS_DIR", root / "errors"), patch.object(
                ai_council, "BACKGROUND_JOB_SPECS_DIR", root / "state" / "background_job_specs"
            ), patch.object(ai_council, "RECIPES_DIR", recipes_dir):
                ai_council.ensure_default_recipes()
                migrated = ai_council.load_recipe("feature_evolution_loop")
                error_migrated = ai_council.load_recipe("error_audit_twice_daily")

        self.assertFalse(migrated["enabled"])
        self.assertEqual(migrated["recipe_version"], ai_council.AUTONOMOUS_LOOP_VERSION)
        self.assertEqual(migrated["cadence"], "twice_daily")
        self.assertEqual(migrated["trigger"]["cron"], "15 10,22 * * *")
        self.assertTrue(any(step["command"] == "@xresearch" for step in migrated["steps"]))
        self.assertTrue(error_migrated["enabled"])
        self.assertEqual(error_migrated["recipe_version"], ai_council.AUTONOMOUS_LOOP_VERSION)
        self.assertEqual(error_migrated["trigger"]["cron"], "0 9,21 * * *")
        self.assertTrue(any(step["command"] == "@grok" for step in error_migrated["steps"]))

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



if __name__ == "__main__":
    unittest.main()
