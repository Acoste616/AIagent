"""Audit task 1.2: silent failures in critical paths must leave a trace.

Covers: append_jsonl last-resort drop note, sidecar reconcile duplicate guard,
memory-db migration error recording, project-memory context error recording.
"""

import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import ai_council


class AppendDropVisibilityTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.base = Path(self._tmp.name)

    def test_lock_timeout_with_sidecar_failure_writes_drop_note(self):
        target = self.base / "costs.jsonl"

        class AlwaysTimeout:
            def __init__(self, *a, **k):
                pass

            def __enter__(self):
                raise TimeoutError("lock timeout: test")

            def __exit__(self, *a):
                return False

        real_writer = ai_council._write_sidecar_line
        calls = []

        def failing_sidecar(sidecar: Path, line: str) -> None:
            calls.append(sidecar.name)
            if ".sidecar-" in sidecar.name:
                raise OSError("disk says no")
            real_writer(sidecar, line)

        before = ai_council.APPEND_JSONL_DROPS
        with patch.object(ai_council, "BlockingFileLock", AlwaysTimeout), \
                patch.object(ai_council, "_write_sidecar_line", failing_sidecar):
            ai_council.append_jsonl(target, {"row": 1})

        self.assertEqual(ai_council.APPEND_JSONL_DROPS, before + 1)
        dropped = target.with_name(target.name + ".dropped.jsonl")
        self.assertTrue(dropped.exists(), f"drop note missing; sidecar calls: {calls}")
        self.assertIn('"row": 1', dropped.read_text(encoding="utf-8"))

    def test_reconcile_merges_dropped_rows_back(self):
        target = self.base / "costs.jsonl"
        dropped = target.with_name(target.name + ".dropped.jsonl")
        dropped.write_text('{"row": "rescued"}\n', encoding="utf-8")
        ai_council.append_jsonl(target, {"row": "fresh"})
        body = target.read_text(encoding="utf-8")
        self.assertIn("rescued", body)
        self.assertIn("fresh", body)
        self.assertFalse(dropped.exists())

    def test_reconcile_truncates_when_unlink_fails(self):
        target = self.base / "audit.jsonl"
        sidecar = target.with_name(target.name + ".sidecar-99.jsonl")
        sidecar.write_text('{"row": "once"}\n', encoding="utf-8")

        real_unlink = Path.unlink

        def failing_unlink(self, *a, **k):
            if ".sidecar-" in self.name:
                raise OSError("locked by AV scanner")
            return real_unlink(self, *a, **k)

        with patch.object(Path, "unlink", failing_unlink):
            ai_council._reconcile_append_sidecars(target)
        # row merged exactly once, sidecar truncated so a re-run cannot duplicate
        self.assertEqual(target.read_text(encoding="utf-8").count("once"), 1)
        self.assertEqual(sidecar.read_text(encoding="utf-8"), "")
        ai_council._reconcile_append_sidecars(target)
        self.assertEqual(target.read_text(encoding="utf-8").count("once"), 1)


class MigrationVisibilityTests(unittest.TestCase):
    def test_failed_migration_records_error(self):
        with tempfile.TemporaryDirectory() as tmp, \
                patch.object(ai_council, "MEMORY_DB", Path(tmp) / "memory.sqlite"), \
                patch.object(ai_council, "_migrate_memory_columns", side_effect=sqlite3.Error("boom")), \
                patch.object(ai_council, "record_error") as rec:
            ai_council.init_memory_db()
        rec.assert_called_once()
        self.assertEqual(rec.call_args.args[0], "memory_db_migration")

    def test_migration_adds_missing_columns(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "memory.sqlite"
            conn = sqlite3.connect(db)
            try:
                conn.execute(
                    "CREATE TABLE memory_entries (id INTEGER PRIMARY KEY AUTOINCREMENT,"
                    " entry_id TEXT UNIQUE NOT NULL, created_at TEXT NOT NULL, kind TEXT NOT NULL,"
                    " agent TEXT NOT NULL, key TEXT NOT NULL, value TEXT NOT NULL, source TEXT NOT NULL,"
                    " task_id TEXT)"
                )
                ai_council._migrate_memory_columns(conn)
                cols = {r[1] for r in conn.execute("PRAGMA table_info(memory_entries)").fetchall()}
            finally:
                conn.close()  # Windows: unclosed handle -> PermissionError on tempdir cleanup
        self.assertLessEqual({"status", "confidence", "norm_key", "chat_id_hash"}, cols)


class ProjectMemoryContextVisibilityTests(unittest.TestCase):
    def test_context_failure_records_error_and_degrades_gracefully(self):
        with patch.object(ai_council, "project_memory_rows", side_effect=RuntimeError("db gone")), \
                patch.object(ai_council, "record_error") as rec:
            out = ai_council.project_memory_context_for_prompt("anything")
        self.assertEqual(out, "")
        rec.assert_called_once()
        self.assertEqual(rec.call_args.args[0], "project_memory_context")


class ReverseJsonlTests(unittest.TestCase):
    """Audit task 2.4: read_jsonl_tail must read from the END of the file."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.path = Path(self._tmp.name) / "rows.jsonl"

    def test_tail_matches_full_read_semantics(self):
        rows = [{"i": i, "tekst": f"ąężółć-{i}"} for i in range(250)]
        with self.path.open("w", encoding="utf-8") as f:
            f.write("not json\n")
            for row in rows:
                f.write(__import__("json").dumps(row, ensure_ascii=False) + "\n")
        self.assertEqual(ai_council.read_jsonl_tail(self.path, 8), ai_council.read_jsonl(self.path)[-8:])
        self.assertEqual(ai_council.read_jsonl_tail(self.path, 5000), ai_council.read_jsonl(self.path))
        self.assertEqual(ai_council.read_jsonl_tail(self.path, 0), [])
        self.assertEqual(ai_council.read_jsonl_tail(Path(self._tmp.name) / "missing.jsonl", 8), [])

    def test_tail_crosses_block_boundaries(self):
        big = "x" * 70000  # bigger than one 64k read block
        with self.path.open("w", encoding="utf-8") as f:
            for i in range(3):
                f.write(__import__("json").dumps({"i": i, "pad": big}) + "\n")
        tail = ai_council.read_jsonl_tail(self.path, 2)
        self.assertEqual([row["i"] for row in tail], [1, 2])

    def test_get_latest_task_returns_last_row_for_id(self):
        with patch.object(ai_council, "TASKS_FILE", self.path):
            for status in ("created", "running", "done"):
                ai_council.append_jsonl(self.path, {"task_id": "task-z", "status": status})
            ai_council.append_jsonl(self.path, {"task_id": "task-other", "status": "created"})
            row = ai_council.get_latest_task("task-z")
        self.assertIsNotNone(row)
        self.assertEqual(row["status"], "done")


if __name__ == "__main__":
    unittest.main()
