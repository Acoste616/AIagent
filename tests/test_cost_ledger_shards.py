"""Audit task 1.3: per-day cost ledger shards + retention.

Budget guards on the hot path must read O(one day) of data; legacy single-file
rows still count during the transition; old shards get pruned.
"""

import json
import tempfile
import unittest
from datetime import datetime, timezone, timedelta
from pathlib import Path
from unittest.mock import patch

import ai_council


class CostShardTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.legacy = Path(self._tmp.name) / "state" / "costs.jsonl"
        self._patch = patch.object(ai_council, "COSTS_FILE", self.legacy)
        self._patch.start()
        self.addCleanup(self._patch.stop)

    def test_record_writes_to_day_shard_and_usage_today_reads_it(self):
        event = ai_council.record_operator_usage("grok", detail="shard test")
        shard = ai_council.costs_file_for_day(event["day"])
        self.assertTrue(shard.exists())
        self.assertFalse(self.legacy.exists(), "new rows must not grow the legacy file")
        rows = ai_council.usage_today("grok")
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["usage_id"], event["usage_id"])

    def test_legacy_rows_still_counted_and_shard_status_wins(self):
        day = ai_council.today_utc()
        self.legacy.parent.mkdir(parents=True, exist_ok=True)
        legacy_rows = [
            {"usage_id": "use-x", "day": day, "operator": "grok", "status": "reserved", "estimated_usd": 0.02},
            {"usage_id": "use-old", "day": "2020-01-01", "operator": "grok", "status": "completed"},
        ]
        self.legacy.write_text("".join(json.dumps(r) + "\n" for r in legacy_rows), encoding="utf-8")
        # completion for the same usage_id lands in the day shard
        ai_council.record_operator_usage("grok", usage_id="use-x", status="completed", estimated_usd=0.05)
        rows = ai_council.usage_today("grok")
        self.assertEqual(len(rows), 1, rows)
        self.assertEqual(rows[0]["status"], "completed")
        self.assertEqual(rows[0]["estimated_usd"], 0.05)

    def test_prune_removes_old_shards_keeps_recent_and_legacy(self):
        day_old = (datetime.now(timezone.utc) - timedelta(days=400)).date().isoformat()
        day_new = ai_council.today_utc()
        for day in (day_old, day_new):
            shard = ai_council.costs_file_for_day(day)
            shard.parent.mkdir(parents=True, exist_ok=True)
            shard.write_text("{}\n", encoding="utf-8")
        self.legacy.parent.mkdir(parents=True, exist_ok=True)
        self.legacy.write_text("{}\n", encoding="utf-8")
        removed = ai_council.prune_cost_shards(90)
        self.assertEqual(removed, 1)
        self.assertFalse(ai_council.costs_file_for_day(day_old).exists())
        self.assertTrue(ai_council.costs_file_for_day(day_new).exists())
        self.assertTrue(self.legacy.exists(), "legacy ledger must never be pruned")

    def test_prune_disabled_with_zero_retention(self):
        day_old = "2020-01-01"
        shard = ai_council.costs_file_for_day(day_old)
        shard.parent.mkdir(parents=True, exist_ok=True)
        shard.write_text("{}\n", encoding="utf-8")
        self.assertEqual(ai_council.prune_cost_shards(0), 0)
        self.assertTrue(shard.exists())


if __name__ == "__main__":
    unittest.main()
