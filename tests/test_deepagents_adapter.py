"""DeepAgents adapter tests (L4.104)."""
# ruff: noqa: F403, F405
import unittest

from council_test_shared import *


class DeepAgentsAdapterTests(unittest.TestCase):
    def test_deepagent_route_is_explicit_and_not_background_by_default(self):
        route = ai_council.route_text("/deepagent zaplanuj testowy research")

        self.assertEqual(route["command"], "/deepagent")
        self.assertEqual(route["operators"], ["deepagent", "host"])
        self.assertEqual(route["prompt"], "zaplanuj testowy research")
        self.assertFalse(ai_council.route_needs_task(route))
        self.assertFalse(ai_council.route_should_background(route))

    def test_deepagent_disabled_returns_status_without_importing_runtime(self):
        with patch.object(ai_council, "deepagent_module_available", return_value=False), patch.object(
            ai_council, "reserve_operator_call"
        ) as reserve:
            response = ai_council.build_response(ai_council.route_text("/deepagent test"))

        reserve.assert_not_called()
        self.assertIn("L4.104", response)
        self.assertIn("enabled: False", response)
        self.assertIn("python -m pip install", response)

    def test_deepagent_missing_dependency_is_gated_even_when_enabled(self):
        with patch.object(ai_council, "deepagent_enabled", return_value=True), patch.object(
            ai_council, "deepagent_module_available", return_value=False
        ), patch.object(ai_council, "deepagent_model", return_value="fake:model"), patch.object(
            ai_council, "reserve_operator_call"
        ) as reserve:
            response = ai_council.deepagent_response("zrób plan")

        reserve.assert_not_called()
        self.assertIn("installed: False", response)
        self.assertIn("deepagents>=0.6.8,<0.7", response)

    def test_deepagent_invoke_uses_gates_and_extracts_message_text(self):
        class FakeAgent:
            def __init__(self):
                self.calls = []

            def invoke(self, payload, config=None):
                self.calls.append((payload, config))
                return {"messages": [{"role": "assistant", "content": "Plan bezpieczny: użyj /delegate."}]}

        fake = FakeAgent()
        reservation = {"usage_id": "use-deep", "operator": "deepagent", "estimated_usd": 0.0}

        with patch.object(ai_council, "deepagent_enabled", return_value=True), patch.object(
            ai_council, "deepagent_module_available", return_value=True
        ), patch.object(ai_council, "deepagent_model", return_value="fake:model"), patch.object(
            ai_council, "reserve_operator_call", return_value=(True, "", reservation)
        ) as reserve, patch.object(ai_council, "finalize_operator_call") as finalize, patch.object(
            ai_council, "create_deepagent_runner", return_value=fake
        ) as create:
            response = ai_council.deepagent_response("zaplanuj integrację", chat_id="553")

        reserve.assert_called_once_with("deepagent", detail="deepagent invoke")
        create.assert_called_once()
        self.assertEqual(fake.calls[0][0]["messages"][0]["content"], "zaplanuj integrację")
        self.assertIn("thread_id", fake.calls[0][1]["configurable"])
        finalize.assert_called_once()
        self.assertIn("[DeepAgent]", response)
        self.assertIn("Plan bezpieczny", response)

    def test_operator_status_includes_deepagent(self):
        with patch.object(ai_council, "deepagent_module_available", return_value=True), patch.object(
            ai_council, "deepagent_enabled", return_value=True
        ), patch.object(ai_council, "deepagent_model", return_value="fake:model"):
            status = ai_council.operator_binary_status()

        self.assertIn("deepagent", status)
        self.assertTrue(status["deepagent"]["configured"])
        self.assertTrue(status["deepagent"]["enabled"])
        self.assertEqual(status["deepagent"]["model"], "fake:model")
