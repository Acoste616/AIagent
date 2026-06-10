"""L4.103 visibility (decyzja 6): the system must signal that it is alive and
working — W1 Telegram 'typing…' pulse, W4 'co robisz?' live status."""

import time
import unittest
from unittest.mock import patch

from council_test_shared import *  # noqa: F401,F403

import ai_council


class TelegramTypingPulseTests(unittest.TestCase):
    def test_pulse_sends_initial_and_repeats(self):
        calls = []
        with patch.object(ai_council, "telegram_send_typing", lambda cid: calls.append(cid) or True):
            with ai_council.TelegramTypingPulse("123", enabled=True, interval=0.05):
                time.sleep(0.13)
        self.assertIn("123", calls)
        self.assertGreaterEqual(len(calls), 2)

    def test_pulse_disabled_is_noop(self):
        calls = []
        with patch.object(ai_council, "telegram_send_typing", lambda cid: calls.append(cid) or True):
            with ai_council.TelegramTypingPulse("123", enabled=False):
                time.sleep(0.05)
        self.assertEqual(calls, [])

    def test_pulse_empty_chat_id_is_noop(self):
        calls = []
        with patch.object(ai_council, "telegram_send_typing", lambda cid: calls.append(cid) or True):
            with ai_council.TelegramTypingPulse("", enabled=True):
                time.sleep(0.05)
        self.assertEqual(calls, [])

    def test_send_typing_without_chat_id_returns_false(self):
        self.assertFalse(ai_council.telegram_send_typing(""))

    def test_pulse_never_raises_when_send_fails(self):
        def boom(_cid):
            raise RuntimeError("network down")
        # telegram_send_typing swallows internally; pulse must stay silent too.
        with patch.object(ai_council, "request_json", side_effect=boom):
            self.assertFalse(ai_council.telegram_send_typing("123"))
            with ai_council.TelegramTypingPulse("123", enabled=True, interval=0.05):
                time.sleep(0.06)


class LiveStatusW4Tests(unittest.TestCase):
    def test_co_robisz_routes_to_working(self):
        for phrase in ("co robisz?", "nad czym pracujesz", "co teraz robisz", "czym się zajmujesz"):
            route = ai_council.route_text(phrase)
            self.assertEqual(route["command"], "/working", phrase)

    def test_live_status_idle_message(self):
        with patch.object(ai_council, "latest_tasks", return_value=[]), \
                patch.object(ai_council, "stuck_tasks", return_value=[]):
            out = ai_council.live_status_response()
        self.assertIn("nic nie miel", out.lower())

    def test_live_status_lists_running_tasks(self):
        running = [{"task_id": "task-1", "status": "running", "text": "research Poke",
                    "created_at": ai_council.utc_now(), "updated_at": ai_council.utc_now()}]
        with patch.object(ai_council, "latest_tasks", return_value=running), \
                patch.object(ai_council, "stuck_tasks", return_value=[]), \
                patch.object(ai_council, "latest_progress_events", return_value=[{"stage": "grok", "percent": 40}]):
            out = ai_council.live_status_response()
        self.assertIn("Pracuję nad 1", out)
        self.assertIn("research Poke", out)
        self.assertIn("grok", out)
        self.assertIn("/progress task-1", out)

    def test_live_status_flags_stuck(self):
        running = [{"task_id": "task-9", "status": "running_background", "text": "long job",
                    "created_at": ai_council.utc_now(), "updated_at": ai_council.utc_now()}]
        with patch.object(ai_council, "latest_tasks", return_value=running), \
                patch.object(ai_council, "stuck_tasks", return_value=running), \
                patch.object(ai_council, "latest_progress_events", return_value=[]):
            out = ai_council.live_status_response()
        self.assertIn("utknęło", out)

    def test_fmt_elapsed(self):
        self.assertEqual(ai_council._fmt_elapsed(45), "45s")
        self.assertEqual(ai_council._fmt_elapsed(125), "2m05s")
        self.assertEqual(ai_council._fmt_elapsed(3700), "1h01m")


class RecentConversationTailTests(unittest.TestCase):
    def test_reads_last_n_for_chat_in_order(self):
        with temp_dir() as tmp:  # noqa: F405
            path = Path(tmp) / "conversations.jsonl"  # noqa: F405
            h = ai_council.short_hash("555")
            other = ai_council.short_hash("999")
            rows = []
            for i in range(20):
                rows.append({"chat_id_hash": h, "role": "user", "text": f"m{i}"})
                rows.append({"chat_id_hash": other, "role": "user", "text": f"x{i}"})
            with patch.object(ai_council, "CONVERSATIONS_FILE", path):
                for r in rows:
                    ai_council.append_jsonl(path, r)
                out = ai_council.recent_conversation("555", limit=3)
        self.assertEqual([r["text"] for r in out], ["m17", "m18", "m19"])

    def test_limit_zero_returns_empty(self):
        with temp_dir() as tmp:  # noqa: F405
            path = Path(tmp) / "conversations.jsonl"  # noqa: F405
            with patch.object(ai_council, "CONVERSATIONS_FILE", path):
                ai_council.append_jsonl(path, {"chat_id_hash": ai_council.short_hash("1"), "text": "a"})
                self.assertEqual(ai_council.recent_conversation("1", limit=0), [])


if __name__ == "__main__":
    unittest.main()
