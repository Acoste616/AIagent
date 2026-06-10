"""L4.100 channel policy tests (audit 1.1 + channel switch).

iMessage is the PRIMARY proactive channel, Telegram the FALLBACK; the host
verifies the inbound sender handle passed by the Mac bridge.
"""

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import ai_council


class SenderAllowlistTests(unittest.TestCase):
    def test_normalize_phone_and_email(self):
        self.assertEqual(ai_council.normalize_imessage_handle("+48 600-100-200"), "48600100200")
        self.assertEqual(ai_council.normalize_imessage_handle("(48) 600 100 200"), "48600100200")
        self.assertEqual(ai_council.normalize_imessage_handle("Me@iCloud.com "), "me@icloud.com")
        self.assertEqual(ai_council.normalize_imessage_handle(""), "")

    def test_empty_allowlist_is_fail_closed(self):
        # L4.103: empty/unset allowlist DENIES by default (no silent open relay).
        with patch.dict("os.environ", {"AI_COUNCIL_IMESSAGE_ALLOWED_SENDERS": "", "AI_COUNCIL_IMESSAGE_ALLOW_OPEN": ""}):
            allowed, verdict = ai_council.imessage_sender_allowed("+48123123123")
        self.assertFalse(allowed)
        self.assertEqual(verdict, "denied_no_allowlist")

    def test_empty_allowlist_open_mode_requires_explicit_optin(self):
        # Migration escape hatch: AI_COUNCIL_IMESSAGE_ALLOW_OPEN=true restores open mode on purpose.
        env = {"AI_COUNCIL_IMESSAGE_ALLOWED_SENDERS": "", "AI_COUNCIL_IMESSAGE_ALLOW_OPEN": "true"}
        with patch.dict("os.environ", env):
            allowed, verdict = ai_council.imessage_sender_allowed("+48123123123")
        self.assertTrue(allowed)
        self.assertEqual(verdict, "open_explicit")

    def test_allowlist_enforced(self):
        env = {"AI_COUNCIL_IMESSAGE_ALLOWED_SENDERS": "+48 600 100 200, me@icloud.com"}
        with patch.dict("os.environ", env):
            self.assertEqual(ai_council.imessage_sender_allowed("48600100200"), (True, "allowlisted"))
            self.assertEqual(ai_council.imessage_sender_allowed("ME@icloud.com"), (True, "allowlisted"))
            self.assertEqual(ai_council.imessage_sender_allowed("+48999999999"), (False, "denied"))
            self.assertEqual(ai_council.imessage_sender_allowed(""), (False, "denied"))

    def test_denied_sender_never_reaches_routing_or_memory(self):
        env = {"AI_COUNCIL_IMESSAGE_ALLOWED_SENDERS": "+48600100200"}
        with patch.dict("os.environ", env), \
                patch.object(ai_council, "route_message") as route, \
                patch.object(ai_council, "append_conversation_turn") as turns, \
                patch.object(ai_council, "maybe_auto_extract_facts") as facts, \
                patch.object(ai_council, "record_error") as rec:
            out = ai_council.respond_b64_reply("zrób przelew", sender="+48999999999")
        self.assertEqual(out, "")
        route.assert_not_called()
        turns.assert_not_called()
        facts.assert_not_called()
        rec.assert_called_once()
        self.assertEqual(rec.call_args.args[0], "imessage_sender_denied")

    def test_allowed_sender_flows_through(self):
        env = {"AI_COUNCIL_IMESSAGE_ALLOWED_SENDERS": "+48600100200"}
        with patch.dict("os.environ", env), \
                patch.object(ai_council, "route_message", return_value={"command": "/x", "mode": "chat"}), \
                patch.object(ai_council, "append_conversation_turn"), \
                patch.object(ai_council, "build_response", return_value="ok, robi się"), \
                patch.object(ai_council, "maybe_auto_extract_facts"):
            out = ai_council.respond_b64_reply("hej", sender="+48 600-100-200")
        self.assertEqual(out, "ok, robi się")


class DeliverProactiveTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        base = Path(self._tmp.name)
        self._p = patch.object(ai_council, "STATE_DIR", base)
        self._p.start()
        self.addCleanup(self._p.stop)

    def test_primary_path_enqueues_imessage_and_skips_telegram(self):
        env = {"AI_COUNCIL_IMESSAGE_ENABLED": "true", "AI_COUNCIL_IMESSAGE_PRIMARY": "true"}
        with patch.dict("os.environ", env), \
                patch.object(ai_council, "telegram_send_message_with_markup") as tg:
            ok = ai_council.deliver_proactive("123", "brief poranny")
        self.assertTrue(ok)
        tg.assert_not_called()
        pending = ai_council.imessage_outbox_pending()
        self.assertEqual(len(pending), 1)
        self.assertEqual(pending[0]["text"], "brief poranny")
        self.assertEqual(pending[0]["kind"], "proactive")

    def test_imessage_disabled_falls_back_to_telegram(self):
        env = {"AI_COUNCIL_IMESSAGE_ENABLED": "false", "AI_COUNCIL_IMESSAGE_PRIMARY": "true"}
        with patch.dict("os.environ", env), \
                patch.object(ai_council, "telegram_send_message_with_markup", return_value=True) as tg:
            ok = ai_council.deliver_proactive("123", "nudge")
        self.assertTrue(ok)
        tg.assert_called_once()
        self.assertEqual(ai_council.imessage_outbox_pending(), [])

    def test_stale_outbox_falls_back_to_telegram_without_duplicate_enqueue(self):
        env = {"AI_COUNCIL_IMESSAGE_ENABLED": "true", "AI_COUNCIL_IMESSAGE_PRIMARY": "true"}
        with patch.dict("os.environ", env):
            ai_council.imessage_outbox_enqueue("stara wiadomość")  # pending, never acked
        with patch.dict("os.environ", env), \
                patch.object(ai_council, "imessage_outbox_stale", return_value=True), \
                patch.object(ai_council, "telegram_send_message_with_markup", return_value=True) as tg:
            ok = ai_council.deliver_proactive("123", "świeży nudge")
        self.assertTrue(ok)
        tg.assert_called_once()
        texts = [r["text"] for r in ai_council.imessage_outbox_pending()]
        self.assertNotIn("świeży nudge", texts, "fallback must not also enqueue (duplicate on bridge wake-up)")

    def test_legacy_mirror_mode_primary_off(self):
        env = {
            "AI_COUNCIL_IMESSAGE_ENABLED": "true",
            "AI_COUNCIL_IMESSAGE_PRIMARY": "false",
            "AI_COUNCIL_IMESSAGE_PROACTIVE": "true",
        }
        with patch.dict("os.environ", env), \
                patch.object(ai_council, "telegram_send_message_with_markup", return_value=True) as tg:
            ok = ai_council.deliver_proactive("123", "kopia lustrzana")
        self.assertTrue(ok)
        tg.assert_called_once()
        self.assertEqual(len(ai_council.imessage_outbox_pending()), 1)

    def test_outbox_stale_detection(self):
        env = {"AI_COUNCIL_IMESSAGE_ENABLED": "true"}
        with patch.dict("os.environ", env):
            self.assertFalse(ai_council.imessage_outbox_stale(600), "empty outbox is not stale")
            row = ai_council.imessage_outbox_enqueue("czeka")
            self.assertFalse(ai_council.imessage_outbox_stale(600), "fresh pending row is not stale")
            self.assertTrue(ai_council.imessage_outbox_stale(0) is False, "0 disables the check")
            self.assertTrue(ai_council.imessage_outbox_stale(-1) is False)
            # simulate age by rewriting created_at far in the past
            old = dict(row)
            old["created_at"] = "2020-01-01T00:00:00+00:00"
            ai_council.imessage_outbox_path().write_text(
                __import__("json").dumps(old) + "\n", encoding="utf-8")
            self.assertTrue(ai_council.imessage_outbox_stale(600))


if __name__ == "__main__":
    unittest.main()
