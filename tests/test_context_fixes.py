"""L4.109 — context failures from the live transcript (2026-06-11):
(a) a stale food_local clarification ate "Jesteś tu prawda?" as a slot answer,
(b) the brain replied "Sprawdzam co już mamy w repozytorium…" and never came back,
(c) unknown "/model" got a random chat answer.
Covers: clarification TTL + smart escape, the stall-promise sanitizer guard,
and the /unknown slash-command route.
"""
# ruff: noqa: F403, F405
import unittest
from datetime import datetime, timedelta, timezone

from council_test_shared import *


class ClarificationTtlTests(unittest.TestCase):
    def setUp(self):
        self._tmp = temp_dir()
        self.addCleanup(self._tmp.cleanup)
        base = Path(self._tmp.name)
        for attr, name in (("CLARIFICATIONS_FILE", "clarifications.jsonl"),
                           ("CONVERSATIONS_FILE", "conversations.jsonl")):
            p = patch.object(ai_council, attr, base / name)
            p.start()
            self.addCleanup(p.stop)
        self.cid = "l4109-ttl"

    def _age_pending(self, minutes: int):
        """Rewrite the last pending record's created_at to `minutes` ago."""
        path = ai_council.CLARIFICATIONS_FILE
        rows = list(ai_council.read_jsonl(path))
        old = (datetime.now(timezone.utc) - timedelta(minutes=minutes)).isoformat()
        rows[-1]["created_at"] = old
        path.write_text(
            "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8"
        )

    def test_stale_pending_is_ignored_and_cleaned_on_read(self):
        ai_council.set_pending_clarification(self.cid, "food_local", {}, "location")
        self._age_pending(20)  # > default 15 min TTL
        self.assertIsNone(ai_council.get_pending_clarification(self.cid))
        # cleaned: a terminal "expired" record was appended on read
        rows = list(ai_council.read_jsonl(ai_council.CLARIFICATIONS_FILE))
        self.assertEqual(rows[-1]["status"], "expired")
        # and the next message is NOT consumed as a slot answer
        self.assertIsNone(ai_council.conversation_brain_consume("włoska", self.cid))

    def test_fresh_pending_survives_ttl_check(self):
        ai_council.set_pending_clarification(self.cid, "food_local", {}, "cuisine")
        self._age_pending(5)  # < 15 min
        self.assertIsNotNone(ai_council.get_pending_clarification(self.cid))

    def test_ttl_env_override(self):
        ai_council.set_pending_clarification(self.cid, "food_local", {}, "cuisine")
        self._age_pending(5)
        with patch.dict(os.environ, {"AI_COUNCIL_CLARIFICATION_TTL_MIN": "3"}):
            self.assertIsNone(ai_council.get_pending_clarification(self.cid))


class ClarificationEscapeTests(unittest.TestCase):
    """Smart escape: a message that is clearly not a slot answer releases the flow."""

    def setUp(self):
        self._tmp = temp_dir()
        self.addCleanup(self._tmp.cleanup)
        base = Path(self._tmp.name)
        for attr, name in (("CLARIFICATIONS_FILE", "clarifications.jsonl"),
                           ("CONVERSATIONS_FILE", "conversations.jsonl")):
            p = patch.object(ai_council, attr, base / name)
            p.start()
            self.addCleanup(p.stop)
        self.cid = "l4109-escape"

    def test_live_failure_scenario_one_to_one(self):
        # EXACT transcript: pending food_local (location) -> "Jesteś tu prawda ?"
        ai_council.set_pending_clarification(self.cid, "food_local", {"cuisine": "włoska"}, "location")
        self.assertIsNone(ai_council.conversation_brain_consume("Jesteś tu prawda ?", self.cid))
        # pending released, message re-enters normal routing -> /chat (the brain answers)
        self.assertIsNone(ai_council.get_pending_clarification(self.cid))
        rows = list(ai_council.read_jsonl(ai_council.CLARIFICATIONS_FILE))
        self.assertEqual(rows[-1]["status"], "released")
        route = ai_council.route_message("Jesteś tu prawda ?", chat_id=self.cid)
        self.assertEqual(route["command"], "/chat")

    def test_nie_o_to_pytam_escapes_instead_of_filling_slot(self):
        ai_council.set_pending_clarification(self.cid, "food_local", {}, "cuisine")
        route = ai_council.route_message("Nie o to pytam, masz problem z kontekstem", chat_id=self.cid)
        self.assertNotEqual(route.get("intent"), "food_local")
        self.assertIsNone(ai_council.get_pending_clarification(self.cid))

    def test_normal_slot_answer_is_still_consumed(self):
        ai_council.route_message("chcę jedzenie", chat_id=self.cid)  # -> asks cuisine
        r = ai_council.route_message("włoska", chat_id=self.cid)
        self.assertEqual(r["command"], "conversation")
        self.assertEqual(r["intent"], "food_local")
        pending = ai_council.get_pending_clarification(self.cid)
        self.assertIsNotNone(pending)
        self.assertEqual(pending["slots"]["cuisine"], "włoska")

    def test_escape_predicate_matrix(self):
        esc = ai_council.clarification_escape
        self.assertTrue(esc("Jesteś tu prawda ?"))
        self.assertTrue(esc("nie o to pytam"))
        self.assertTrue(esc("czy ty w ogóle działasz"))
        self.assertTrue(esc("zostaw to na razie, inna sprawa"))
        self.assertFalse(esc("włoska"))
        self.assertFalse(esc("do 60 zł"))
        self.assertFalse(esc("niedaleko Niemcewicza"))
        # location slot: GPS/address-looking text is an answer even when oddly phrased
        self.assertFalse(esc("lokalizacja: 52.26100,20.98900", pending_slot="location"))
        self.assertFalse(esc("ul. Niemcewicza 12?", pending_slot="location"))


class BrainStallGuardTests(unittest.TestCase):
    """(b) ZAKAZ 'sprawdzam i znikam' — prompt rule + sanitizer guard."""

    def test_prompt_forbids_promise_without_tool(self):
        self.assertIn("nie masz możliwości wrócić sam z siebie", ai_council.BRAIN_SYSTEM_PROMPT)

    def test_sanitizer_swaps_the_exact_live_failure_reply(self):
        out = ai_council.sanitize_brain_reply(
            "Sprawdzam co już mamy w repozytorium zanim cokolwiek napiszę."
        )
        self.assertNotIn("Sprawdzam", out)
        self.assertIn("nie umiem wracać sam z siebie", out)

    def test_sanitizer_swaps_other_stall_promises(self):
        for stall in ("Zaraz wrócę z wynikiem.", "Daj mi chwilę, ogarnę to.", "Momencik."):
            self.assertIn("nie umiem wracać sam z siebie", ai_council.sanitize_brain_reply(stall), stall)

    def test_sanitizer_keeps_long_real_answer_containing_sprawdzam(self):
        real = (
            "W repozytorium masz już moduł retry w utils.py i testy w tests/test_retry.py. "
            "Jak chcesz, sprawdzam jeszcze pokrycie brzegów, ale najpierw powiedz, "
            "który plik mam wziąć na warsztat."
        )
        self.assertEqual(ai_council.sanitize_brain_reply(real), real)

    def test_sanitizer_keeps_short_normal_reply(self):
        self.assertEqual(ai_council.sanitize_brain_reply("Jasne, zrobione."), "Jasne, zrobione.")


class UnknownSlashCommandTests(unittest.TestCase):
    """(c) '/model' must get an honest 'unknown command', not a random chat answer."""

    def test_model_routes_to_unknown(self):
        route = ai_council.route_text("/model")
        self.assertEqual(route["command"], "/unknown")
        self.assertEqual(route["prompt"], "/model")

    def test_unknown_with_args_keeps_command_token(self):
        route = ai_council.route_text("/model claude-opus")
        self.assertEqual(route["command"], "/unknown")
        self.assertEqual(route["prompt"], "/model")

    def test_build_response_unknown_is_short_and_helpful(self):
        out = ai_council.build_response(ai_council.route_text("/model"))
        self.assertIn("Nie znam komendy", out)
        self.assertIn("/model", out)
        self.assertIn("napisz normalnie", out)

    def test_route_message_explicit_slash_reaches_unknown(self):
        route = ai_council.route_message("/model", chat_id="l4109-cmd")
        self.assertEqual(route["command"], "/unknown")

    def test_known_commands_unaffected(self):
        self.assertEqual(ai_council.route_text("/status")["command"], "/status")
        self.assertEqual(ai_council.route_text("/radar add openai/codex")["command"], "/radar")
        self.assertEqual(ai_council.route_text("/working")["command"], "/working")
        self.assertEqual(ai_council.route_text("/brief")["command"], "/brief")

    def test_paths_and_bare_slash_still_go_to_chat(self):
        self.assertEqual(ai_council.route_text("/Users/bartek/notes.txt")["command"], "/chat")
        self.assertEqual(ai_council.route_text("/")["command"], "/chat")


if __name__ == "__main__":
    unittest.main()
