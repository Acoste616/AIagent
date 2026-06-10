"""L4.104 Evolution Factory tests (hermetic — no live Grok/Claude calls).

The factory may ONLY: read reports/errors/conversations/improvements, call the
research+plan operators (patched here), hand a feature goal to the EXISTING
gated self-repair pipeline, append an improvement, and deliver ONE short Polish
message per day. Production changes still go through the self-repair guards.
"""

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import ai_council

GOOD_PLAN = (
    'Oto plan:\n{"title": "Szybsze przypomnienia", '
    '"why_for_bartek": "Przypomnienia będą działać z czatu.", '
    '"kind": "self_repair", "task": "Dodaj parser X i test w tests/."}'
)


class ParseEvolutionPlanTests(unittest.TestCase):
    def test_parses_json_with_surrounding_prose(self):
        plan = ai_council.parse_evolution_plan(GOOD_PLAN)
        self.assertIsNotNone(plan)
        self.assertEqual(plan["title"], "Szybsze przypomnienia")
        self.assertEqual(plan["kind"], "self_repair")
        self.assertIn("parser X", plan["task"])
        self.assertIn("Przypomnienia", plan["why_for_bartek"])

    def test_broken_json_returns_none(self):
        for raw in ("", "nie umiem", '{"title": "x", "kind": ', '{"title": "x"}', "[1,2]"):
            self.assertIsNone(ai_council.parse_evolution_plan(raw), raw)

    def test_unknown_kind_or_missing_task_returns_none(self):
        bad_kind = '{"title": "x", "why_for_bartek": "y", "kind": "deploy", "task": "z"}'
        no_task = '{"title": "x", "why_for_bartek": "y", "kind": "manual", "task": ""}'
        self.assertIsNone(ai_council.parse_evolution_plan(bad_kind))
        self.assertIsNone(ai_council.parse_evolution_plan(no_task))

    def test_analyze_and_plan_defensive_on_broken_model_output(self):
        with patch.object(ai_council, "evolution_claude_plan", return_value="{zepsuty json"):
            self.assertIsNone(ai_council.evolution_analyze_and_plan("research"))
        with patch.object(ai_council, "evolution_claude_plan", return_value=None):
            self.assertIsNone(ai_council.evolution_analyze_and_plan("research"))


class EvolutionResearchFailSafeTests(unittest.TestCase):
    def test_grok_blocked_returns_empty_no_crash(self):
        with tempfile.TemporaryDirectory() as tmp:
            with patch.object(ai_council, "REPORTS_DIR", Path(tmp)), patch.object(
                ai_council, "grok_response", return_value="[Grok] blocked: daily call limit"
            ):
                self.assertEqual(ai_council.evolution_research_pack(), "")

    def test_grok_exception_returns_empty(self):
        with tempfile.TemporaryDirectory() as tmp:
            with patch.object(ai_council, "REPORTS_DIR", Path(tmp)), patch.object(
                ai_council, "grok_response", side_effect=RuntimeError("boom")
            ):
                self.assertEqual(ai_council.evolution_research_pack(), "")

    def test_success_writes_daily_report(self):
        with tempfile.TemporaryDirectory() as tmp:
            reports = Path(tmp)
            with patch.object(ai_council, "REPORTS_DIR", reports), patch.object(
                ai_council, "grok_response", return_value="[Grok]\n1. Pomysł A — bo warto."
            ):
                text = ai_council.evolution_research_pack()
            self.assertIn("Pomysł A", text)
            report = ai_council.evolution_research_report_path()
            self.assertTrue(report.name.startswith("evolution-research-"))
            files = list(reports.glob("evolution-research-*.md"))
            self.assertEqual(len(files), 1)
            self.assertIn("Pomysł A", files[0].read_text(encoding="utf-8"))

    def test_existing_report_reused_without_new_grok_call(self):
        with tempfile.TemporaryDirectory() as tmp:
            reports = Path(tmp)
            with patch.object(ai_council, "REPORTS_DIR", reports):
                ai_council.evolution_research_report_path().write_text("stary raport", encoding="utf-8")
                with patch.object(ai_council, "grok_response") as grok:
                    self.assertEqual(ai_council.evolution_research_pack(), "stary raport")
                grok.assert_not_called()

    def test_cycle_survives_research_failure(self):
        """Grok pada -> cykl dalej działa i wychodzi JEDNA wiadomość."""
        with tempfile.TemporaryDirectory() as tmp:
            sent = []
            with patch.object(ai_council, "STATE_DIR", Path(tmp)), patch.object(
                ai_council, "evolution_research_pack", return_value=""
            ), patch.object(ai_council, "evolution_claude_plan", return_value=None), patch.object(
                ai_council, "evolution_user_turn_counts", return_value={"today": 3, "yesterday": 1}
            ), patch.object(ai_council, "deliver_proactive", side_effect=lambda c, t, m=None: sent.append(t) or True):
                out = ai_council.evolution_cycle(send=True)
            self.assertIn("[Evolution]", out)
            self.assertEqual(len(sent), 1)
            self.assertTrue(sent[0].strip())


class EvolutionDailyMarkerTests(unittest.TestCase):
    def test_max_one_cycle_and_message_per_day(self):
        with tempfile.TemporaryDirectory() as tmp:
            sent = []
            with patch.object(ai_council, "STATE_DIR", Path(tmp)), patch.object(
                ai_council, "evolution_research_pack", return_value=""
            ), patch.object(ai_council, "evolution_analyze_and_plan", return_value=None), patch.object(
                ai_council, "evolution_user_turn_counts", return_value={"today": 1, "yesterday": 0}
            ), patch.object(ai_council, "deliver_proactive", side_effect=lambda c, t, m=None: sent.append(t) or True):
                first = ai_council.evolution_cycle(send=True)
                second = ai_council.evolution_cycle(send=True)
            self.assertIn("[Evolution]", first)
            self.assertIn("juz byl", second)
            self.assertEqual(len(sent), 1)

    def test_disabled_flag_blocks_cycle(self):
        with patch.dict("os.environ", {"AI_COUNCIL_EVOLUTION_ENABLED": "false"}):
            out = ai_council.evolution_cycle(send=False)
        self.assertIn("wylaczona", out)


class EvolutionUsagePulseTests(unittest.TestCase):
    def test_zero_turns_today_sends_encouraging_message_with_fact(self):
        with tempfile.TemporaryDirectory() as tmp:
            sent = []
            with patch.object(ai_council, "STATE_DIR", Path(tmp)), patch.object(
                ai_council, "evolution_research_pack", return_value=""
            ), patch.object(ai_council, "evolution_analyze_and_plan", return_value=None), patch.object(
                ai_council, "evolution_user_turn_counts", return_value={"today": 0, "yesterday": 2}
            ), patch.object(
                ai_council, "active_user_facts", return_value=[{"value": "lot do Oslo w piątek"}]
            ), patch.object(ai_council, "deliver_proactive", side_effect=lambda c, t, m=None: sent.append(t) or True):
                ai_council.evolution_cycle(send=True)
            self.assertEqual(len(sent), 1)
            self.assertIn("Napisz", sent[0])
            self.assertIn("lot do Oslo", sent[0])

    def test_pulse_without_facts_still_has_one_concrete_proposal(self):
        with patch.object(ai_council, "active_user_facts", return_value=[]):
            message = ai_council.evolution_usage_pulse_message()
        self.assertIn("Napisz np.", message)

    def test_user_turn_counts_counts_only_user_role(self):
        with tempfile.TemporaryDirectory() as tmp:
            convo = Path(tmp) / "conversations.jsonl"
            today = ai_council.today_utc()
            rows = [
                {"created_at": f"{today}T08:00:00Z", "role": "user", "text": "hej"},
                {"created_at": f"{today}T08:00:05Z", "role": "assistant", "text": "czesc"},
                {"created_at": f"{today}T09:00:00Z", "role": "user", "text": "co tam"},
            ]
            convo.write_text("\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8")
            with patch.object(ai_council, "CONVERSATIONS_FILE", convo):
                counts = ai_council.evolution_user_turn_counts()
            self.assertEqual(counts["today"], 2)
            self.assertEqual(counts["yesterday"], 0)


class EvolutionBuildDispatchTests(unittest.TestCase):
    def test_self_repair_plan_goes_to_pipeline_as_goal(self):
        plan = {"title": "Lepsze X", "why_for_bartek": "Bo tak.", "kind": "self_repair", "task": "Dodaj X."}
        with tempfile.TemporaryDirectory() as tmp:
            calls = {}

            def fake_repair(send=False, chat_id="", goal=None):
                calls["goal"] = goal
                return "[Self-Repair] ZIELONY patch ... /approve act-123 ..."

            with patch.object(ai_council, "STATE_DIR", Path(tmp)), patch.object(
                ai_council, "evolution_research_pack", return_value=""
            ), patch.object(ai_council, "evolution_analyze_and_plan", return_value=plan), patch.object(
                ai_council, "evolution_user_turn_counts", return_value={"today": 1, "yesterday": 0}
            ), patch.object(ai_council, "run_self_repair_once", side_effect=fake_repair):
                out = ai_council.evolution_cycle(send=False)
            self.assertTrue(str(calls["goal"]["context"]).startswith("goal:"))
            self.assertEqual(calls["goal"]["task"], "Dodaj X.")
            self.assertIn("/approve act-123", out)

    def test_manual_plan_lands_in_improvements_queue(self):
        plan = {"title": "Duża rzecz", "why_for_bartek": "Bo duża.", "kind": "manual", "task": "Zrób dużą rzecz."}
        with tempfile.TemporaryDirectory() as tmp:
            captured = {}

            def fake_improvement(**kwargs):
                captured.update(kwargs)
                return {"improvement_id": "imp-1", **kwargs}

            with patch.object(ai_council, "STATE_DIR", Path(tmp)), patch.object(
                ai_council, "evolution_research_pack", return_value=""
            ), patch.object(ai_council, "evolution_analyze_and_plan", return_value=plan), patch.object(
                ai_council, "evolution_user_turn_counts", return_value={"today": 1, "yesterday": 0}
            ), patch.object(ai_council, "create_improvement", side_effect=fake_improvement):
                out = ai_council.evolution_cycle(send=False)
            self.assertEqual(captured["source"], "evolution_factory")
            self.assertEqual(captured["title"], "Duża rzecz")
            self.assertIn("propozycję", out)

    def test_goal_mode_prompt_and_empty_goal_guard(self):
        candidate = {"kind": "goal", "title": "Lepsze X", "message": "Dodaj X.", "context": "goal:lepsze-x"}
        prompt = ai_council.self_repair_tools_prompt(candidate)
        self.assertIn("ZADANIE DO WDROZENIA", prompt)
        self.assertIn("Dodaj X.", prompt)
        self.assertIn("NO_SAFE_PATCH", prompt)
        blocks_prompt = ai_council.self_repair_prompt(candidate)
        self.assertIn("ZADANIE DO WDROZENIA", blocks_prompt)
        out = ai_council.run_self_repair_once(goal={"context": "goal:x", "task": ""})
        self.assertIn("goal bez zadania", out)


class EvolutionRegistrationTests(unittest.TestCase):
    def test_recipe_registered_like_error_audit(self):
        recipes = ai_council.default_recipes()
        self.assertIn("evolution_factory_daily", recipes)
        recipe = recipes["evolution_factory_daily"]
        self.assertTrue(recipe["enabled"])
        self.assertEqual(recipe["recipe_version"], ai_council.EVOLUTION_FACTORY_VERSION)
        self.assertEqual(recipe["trigger"]["cron"], "0 7 * * *")  # 7:00 lokalnie, po quiet hours
        self.assertEqual(recipe["steps"], [{"command": "/evolve", "prompt": ""}])
        self.assertIn("evolution_factory_daily", ai_council.DEFAULT_RECIPE_MANAGED_KEYS)
        # recipe policy must actually allow the step (deny-by-default otherwise)
        self.assertEqual(ai_council.recipe_step_violations(recipe), [])

    def test_recipe_hour_from_env(self):
        with patch.dict("os.environ", {"AI_COUNCIL_EVOLUTION_HOUR_UTC": "5"}):
            recipe = ai_council.default_recipes()["evolution_factory_daily"]
        self.assertEqual(recipe["trigger"]["cron"], "0 5 * * *")

    def test_evolve_route_and_background(self):
        route = ai_council.route_text("/evolve")
        self.assertEqual(route["command"], "/evolve")
        self.assertEqual(route["mode"], "evolution")
        self.assertEqual(route["operators"], ["host"])
        self.assertTrue(ai_council.route_should_background({"command": "/evolve"}))

    def test_build_response_dispatches_to_cycle(self):
        with patch.object(ai_council, "evolution_cycle", return_value="[Evolution] ok") as cycle:
            out = ai_council.build_response({"command": "/evolve", "operators": ["host"], "prompt": ""})
        self.assertEqual(out, "[Evolution] ok")
        cycle.assert_called_once_with(send=True)


if __name__ == "__main__":
    unittest.main()
