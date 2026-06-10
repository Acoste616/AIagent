"""L4.101 self-repair loop tests.

The loop may ONLY: read errors, ask Claude for FIND/REPLACE blocks, apply them
to an isolated working copy, verify, and create a pending action. Production
files change exclusively through /approve (with backup + undo).
"""

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import ai_council

VALID_BLOCK = (
    "PATCH_FILE: ai_council.py\n"
    "<<<<FIND\n"
    "MARKER = 1\n"
    "====\n"
    "MARKER = 2\n"
    ">>>>"
)


class RepairBlockTests(unittest.TestCase):
    def test_parse_valid_block(self):
        blocks, err = ai_council.parse_repair_blocks(VALID_BLOCK)
        self.assertEqual(err, "")
        self.assertEqual(blocks, [{"file": "ai_council.py", "find": "MARKER = 1", "replace": "MARKER = 2"}])

    def test_parse_rejects_disallowed_paths(self):
        for bad in ("scripts/x.py", "../evil.py", "C:/x.py", "tests/sub/dir.py"):
            text = VALID_BLOCK.replace("ai_council.py", bad)
            blocks, err = ai_council.parse_repair_blocks(text)
            self.assertEqual(blocks, [], bad)
            self.assertIn("allowlista", err)

    def test_parse_rejects_garbage_and_block_flood(self):
        blocks, err = ai_council.parse_repair_blocks("przepraszam, nie umiem")
        self.assertEqual(blocks, [])
        self.assertIn("brak blokow", err)
        flood = "\n".join(VALID_BLOCK for _ in range(7))
        blocks, err = ai_council.parse_repair_blocks(flood)
        self.assertEqual(blocks, [])
        self.assertIn("za duzo", err)

    def test_file_allowlist(self):
        self.assertTrue(ai_council.self_repair_file_allowed("ai_council.py"))
        self.assertTrue(ai_council.self_repair_file_allowed("tests/test_x.py"))
        self.assertFalse(ai_council.self_repair_file_allowed("tests/sub/x.py"))
        self.assertFalse(ai_council.self_repair_file_allowed("..\\ai_council.py"))
        self.assertFalse(ai_council.self_repair_file_allowed("recipes/x.json"))
        self.assertFalse(ai_council.self_repair_file_allowed(""))

    def test_apply_requires_exactly_one_match(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            target = root / "ai_council.py"
            target.write_text("a = 1\nb = 1\n", encoding="utf-8")
            ok, detail = ai_council.apply_repair_blocks(
                [{"file": "ai_council.py", "find": "a = 1", "replace": "a = 2"}], root)
            self.assertTrue(ok, detail)
            self.assertIn("a = 2", target.read_text(encoding="utf-8"))
            ok, detail = ai_council.apply_repair_blocks(
                [{"file": "ai_council.py", "find": "= ", "replace": "x"}], root)
            self.assertFalse(ok)
            self.assertIn("wystapien=2", detail)
            ok, detail = ai_council.apply_repair_blocks(
                [{"file": "ai_council.py", "find": "nie ma", "replace": "x"}], root)
            self.assertFalse(ok)
            self.assertIn("wystapien=0", detail)


class RepairCandidateTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        base = Path(self._tmp.name)
        for p in (
            patch.object(ai_council, "STATE_DIR", base),
            patch.object(ai_council, "ERRORS_FILE", base / "errors.jsonl"),
        ):
            p.start()
            self.addCleanup(p.stop)

    def test_grouping_ranking_and_attempt_exclusion(self):
        for context, n in (("imessage_enqueue", 3), ("memory_db_migration", 1), ("already_tried", 5)):
            for _ in range(n):
                ai_council.record_error(context, message=f"boom {context}", severity="warning")
        ai_council.record_error("noise", message="info row", severity="info")
        ai_council.self_repair_record("repair-x", "already_tried", "verify_failed")
        candidates = ai_council.self_repair_candidates(days=1)
        contexts = [c["context"] for c in candidates]
        self.assertEqual(contexts[0], "imessage_enqueue")
        self.assertNotIn("already_tried", contexts)
        self.assertNotIn("noise", contexts)
        self.assertEqual(candidates[0]["count"], 3)


class SelfRepairPipelineTests(unittest.TestCase):
    """End-to-end on a miniature PROJECT_DIR — only the Claude call and pytest
    verification are faked; copy/apply/action/backup/undo paths are real."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.base = Path(self._tmp.name)
        proj = self.base / "proj"
        (proj / "tests").mkdir(parents=True)
        (proj / "ai_council.py").write_text("MARKER = 1\n", encoding="utf-8")
        (proj / "pyproject.toml").write_text("[tool.pytest.ini_options]\n", encoding="utf-8")
        (proj / "tests" / "test_mini.py").write_text("def test_ok():\n    assert True\n", encoding="utf-8")
        state = self.base / "state"
        state.mkdir()
        self.proj = proj
        for p in (
            patch.object(ai_council, "PROJECT_DIR", proj),
            patch.object(ai_council, "STATE_DIR", state),
            patch.object(ai_council, "ERRORS_FILE", state / "errors.jsonl"),
            patch.object(ai_council, "ACTIONS_FILE", state / "actions.jsonl"),
        ):
            p.start()
            self.addCleanup(p.stop)

    def _seed_error(self):
        ai_council.record_error("marker_bug", message="MARKER zle ustawiony", severity="error")

    def test_happy_path_creates_pending_action_not_touching_production(self):
        self._seed_error()
        with patch.object(ai_council, "claude_self_repair_response", return_value=VALID_BLOCK), \
                patch.object(ai_council, "verify_repair_workspace", return_value={"ok": True, "step": "pytest", "detail": "1 passed"}):
            out = ai_council.run_self_repair_once()
        self.assertIn("ZIELONY patch", out)
        self.assertIn("/approve act-", out)
        # production untouched until approval
        self.assertEqual((self.proj / "ai_council.py").read_text(encoding="utf-8"), "MARKER = 1\n")
        # working copy DID get the patch
        statuses = [r["status"] for r in ai_council.read_jsonl(ai_council.self_repair_file())]
        self.assertEqual(statuses, ["started", "proposed"])
        actions = ai_council.read_jsonl(ai_council.ACTIONS_FILE)
        self.assertEqual(actions[-1]["type"], "self_repair")
        self.assertEqual(actions[-1]["status"], "pending")

    def test_red_verification_blocks_proposal(self):
        self._seed_error()
        with patch.object(ai_council, "claude_self_repair_response", return_value=VALID_BLOCK), \
                patch.object(ai_council, "verify_repair_workspace", return_value={"ok": False, "step": "pytest", "detail": "1 failed"}):
            out = ai_council.run_self_repair_once()
        self.assertIn("CZERWONA", out)
        self.assertEqual(ai_council.read_jsonl(ai_council.ACTIONS_FILE), [])
        statuses = [r["status"] for r in ai_council.read_jsonl(ai_council.self_repair_file())]
        self.assertEqual(statuses[-1], "verify_failed")

    def test_no_safe_patch_is_respected(self):
        self._seed_error()
        with patch.object(ai_council, "claude_self_repair_response", return_value="NO_SAFE_PATCH wymaga decyzji czlowieka"):
            out = ai_council.run_self_repair_once()
        self.assertIn("odmowil", out)
        self.assertEqual(ai_council.read_jsonl(ai_council.ACTIONS_FILE), [])

    def test_approve_applies_with_backup_and_undo_restores(self):
        self._seed_error()
        with patch.object(ai_council, "claude_self_repair_response", return_value=VALID_BLOCK), \
                patch.object(ai_council, "verify_repair_workspace", return_value={"ok": True, "step": "pytest", "detail": "1 passed"}):
            ai_council.run_self_repair_once()
        action = ai_council.read_jsonl(ai_council.ACTIONS_FILE)[-1]
        executed = ai_council.execute_self_repair_action(action)
        self.assertEqual(executed["status"], "executed", executed.get("execution_result"))
        self.assertEqual((self.proj / "ai_council.py").read_text(encoding="utf-8"), "MARKER = 2\n")
        repair_id = action["payload"]["repair_id"]
        self.assertTrue((ai_council.self_repair_backup_dir(repair_id) / "ai_council.py").exists())
        out = ai_council.self_repair_undo(repair_id)
        self.assertIn("Przywrocono", out)
        self.assertEqual((self.proj / "ai_council.py").read_text(encoding="utf-8"), "MARKER = 1\n")

    def test_broken_patch_on_production_rolls_back_automatically(self):
        self._seed_error()
        bad_block = VALID_BLOCK.replace("MARKER = 2", "def broken(:\n")
        with patch.object(ai_council, "claude_self_repair_response", return_value=bad_block), \
                patch.object(ai_council, "verify_repair_workspace", return_value={"ok": True, "step": "pytest", "detail": "fake green"}):
            ai_council.run_self_repair_once()
        action = ai_council.read_jsonl(ai_council.ACTIONS_FILE)[-1]
        executed = ai_council.execute_self_repair_action(action)
        self.assertEqual(executed["status"], "failed")
        self.assertIn("py_compile", executed["execution_result"])
        self.assertEqual((self.proj / "ai_council.py").read_text(encoding="utf-8"), "MARKER = 1\n")

    def test_real_isolated_verification_runs_pytest(self):
        # No fakes here: prepare + apply + actual py_compile/pytest subprocesses.
        repair_id = "repair-test-real"
        workdir = ai_council.prepare_repair_workspace(repair_id)
        ok, detail = ai_council.apply_repair_blocks(
            [{"file": "ai_council.py", "find": "MARKER = 1", "replace": "MARKER = 3"}], workdir)
        self.assertTrue(ok, detail)
        verdict = ai_council.verify_repair_workspace(workdir)
        self.assertTrue(verdict["ok"], verdict)
        self.assertIn("passed", verdict["detail"])

    def test_disabled_flag_short_circuits(self):
        with patch.dict("os.environ", {"AI_COUNCIL_SELF_REPAIR": "false"}):
            out = ai_council.run_self_repair_once()
        self.assertIn("wylaczony", out)


class SelfRepairRoutingTests(unittest.TestCase):
    def test_slash_and_natural_routes(self):
        route = ai_council.route_text("/self-repair")
        self.assertEqual(route["command"], "/self-repair")
        self.assertEqual(route["mode"], "self_repair")
        natural = ai_council.natural_intent_route("samonaprawa", "samonaprawa")
        self.assertIsNotNone(natural)
        self.assertEqual(natural["command"], "/self-repair")
        self.assertTrue(ai_council.route_should_background({"command": "/self-repair"}))

    def test_recipe_definition_is_loadable(self):
        recipe = json.loads((ai_council.PROJECT_DIR / "recipes" / "self_repair_loop.json").read_text(encoding="utf-8"))
        self.assertTrue(recipe["enabled"])
        self.assertEqual(recipe["steps"][0]["command"], "/self-repair")


if __name__ == "__main__":
    unittest.main()
