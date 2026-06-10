"""Split from tests/test_ai_council.py (audit 3.3) — classes preserved 1:1."""
# ruff: noqa: F403, F405
import unittest

from council_test_shared import *


class IMessageBridgeTests(unittest.TestCase):
    """L4.82: macOS native iMessage/Mail bridge — armed but OFF by default."""

    def test_applescript_quote_escapes(self):
        self.assertEqual(ai_council.applescript_quote('a"b\\c'), '"a\\"b\\\\c"')

    def test_imessage_gated_off_by_default(self):
        # conftest forces the flag off; send must refuse without touching osascript.
        with patch.object(ai_council, "subprocess") as sp:
            out = ai_council.imessage_send("hej")
        self.assertIn("gated", out)
        sp.run.assert_not_called()

    def test_imessage_requires_recipient(self):
        def fake_cfg(key, default=""):
            return {"AI_COUNCIL_IMESSAGE_ENABLED": "true", "AI_COUNCIL_IMESSAGE_TO": ""}.get(key, default)

        with patch.object(ai_council, "cfg", side_effect=fake_cfg):
            out = ai_council.imessage_send("hej")
        self.assertIn("brak odbiorcy", out)

    def test_imessage_send_builds_applescript_and_calls_osascript(self):
        def fake_cfg(key, default=""):
            return {"AI_COUNCIL_IMESSAGE_ENABLED": "true", "AI_COUNCIL_IMESSAGE_TO": "+48555"}.get(key, default)

        captured = {}

        class _Proc:
            returncode = 0
            stdout = ""
            stderr = ""

        def fake_run(args, **kwargs):
            captured["args"] = args
            return _Proc()

        with patch.object(ai_council, "cfg", side_effect=fake_cfg), patch.object(
            ai_council, "on_macos", return_value=True
        ), patch.object(ai_council.subprocess, "run", side_effect=fake_run):
            out = ai_council.imessage_send("cześć \"świat\"")

        self.assertIn("wysłane do +48555", out)
        script = captured["args"][-1]
        self.assertIn("Messages", script)
        self.assertIn("+48555", script)
        self.assertIn('service type = iMessage', script)
        # body is AppleScript-escaped
        self.assertIn('\\"świat\\"', script)

    def test_imessage_off_macos_returns_bridge_required(self):
        def fake_cfg(key, default=""):
            return {"AI_COUNCIL_IMESSAGE_ENABLED": "true", "AI_COUNCIL_IMESSAGE_TO": "+48555"}.get(key, default)

        with patch.object(ai_council, "cfg", side_effect=fake_cfg), patch.object(
            ai_council, "on_macos", return_value=False
        ):
            out = ai_council.imessage_send("hej")
        self.assertIn("bridge_required", out)

    def test_imessage_status_text_has_version_and_status(self):
        text = ai_council.imessage_bridge_status_text()
        self.assertIn(ai_council.IMESSAGE_BRIDGE_VERSION, text)
        self.assertIn("status:", text)
        self.assertIn("/imessage test", text)

    def test_imessage_command_routes_and_dispatches_status(self):
        route = ai_council.route_text("/imessage status")
        self.assertEqual(route["command"], "/imessage")
        out = ai_council.build_response(route)
        self.assertIn("iMessage bridge", out)

    def test_imessage_text_targets_self_not_third_party(self):
        # The /imessage <text> command always queues to self (no third-party recipient).
        captured = {}

        def fake_enqueue(text, to="", kind="manual"):
            captured["to"] = to
            return {"id": "imsg-test"}

        with patch.object(ai_council, "imessage_outbox_enqueue", side_effect=fake_enqueue):
            out = ai_council.imessage_response("przypomnij mi o spotkaniu")
        self.assertEqual(captured["to"], "")
        self.assertIn("zakolejkowane", out)

    def test_mail_gated_off_by_default(self):
        with patch.object(ai_council, "subprocess") as sp:
            out = ai_council.mail_send("S", "B", "x@example.com")
        self.assertIn("gated", out)
        sp.run.assert_not_called()

    def test_health_reports_imessage_bridge(self):
        health = ai_council.health_response()
        self.assertIn("imessage_bridge=", health)
        self.assertIn("mail_bridge=", health)


class IMessageOutboxTests(unittest.TestCase):
    """L4.82: cross-host outbox relay (host enqueues, Mac drains)."""

    def setUp(self):
        self._tmp = temp_dir()
        self.addCleanup(self._tmp.cleanup)
        self._state = Path(self._tmp.name)
        self._patch = patch.object(ai_council, "STATE_DIR", self._state)
        self._patch.start()
        self.addCleanup(self._patch.stop)

    def test_enqueue_then_pending_then_ack_idempotent(self):
        row = ai_council.imessage_outbox_enqueue("cześć", to="+48555", kind="test")
        pending = ai_council.imessage_outbox_pending()
        self.assertEqual(len(pending), 1)
        self.assertEqual(pending[0]["id"], row["id"])
        self.assertEqual(pending[0]["to"], "+48555")

        ai_council.imessage_outbox_ack(row["id"], "sent")
        self.assertEqual(ai_council.imessage_outbox_pending(), [])

    def test_drain_rows_sends_and_acks(self):
        sent_calls = []
        ack_calls = []

        def send_fn(text, to):
            sent_calls.append((text, to))
            return "[iMessage] wysłane do " + (to or "self") + "."

        def ack_fn(mid, status, detail):
            ack_calls.append((mid, status))

        rows = [{"id": "imsg-1", "text": "a", "to": ""}, {"id": "imsg-2", "text": "b", "to": "+48"}]
        results = ai_council.imessage_drain_rows(rows, send_fn, ack_fn)
        self.assertEqual([r["status"] for r in results], ["sent", "sent"])
        self.assertEqual(len(sent_calls), 2)
        self.assertEqual([a[1] for a in ack_calls], ["sent", "sent"])

    def test_drain_rows_marks_failure(self):
        def send_fn(text, to):
            return "[iMessage] nie wysłano: timeout"

        acks = []
        results = ai_council.imessage_drain_rows(
            [{"id": "imsg-x", "text": "a", "to": ""}], send_fn, lambda m, s, d: acks.append((m, s, d))
        )
        self.assertEqual(results[0]["status"], "failed")
        self.assertEqual(acks[0][1], "failed")
        self.assertIn("timeout", acks[0][2])

    def test_imessage_command_text_enqueues(self):
        out = ai_council.imessage_response("przypomnij o spotkaniu jutro")
        self.assertIn("zakolejkowane", out)
        self.assertEqual(len(ai_council.imessage_outbox_pending()), 1)

    def test_proactive_delivery_uses_telegram_when_imessage_disabled(self):
        # conftest forces AI_COUNCIL_IMESSAGE_ENABLED off -> Telegram fallback,
        # nothing may land in the iMessage outbox (L4.100 deliver_proactive).
        with patch.object(ai_council, "telegram_send_message_with_markup", return_value=True) as tg:
            ok = ai_council.deliver_proactive("123", "brief poranny")
        self.assertTrue(ok)
        tg.assert_called_once()
        self.assertEqual(ai_council.imessage_outbox_pending(), [])

    def test_proactive_delivery_enqueues_when_imessage_primary(self):
        # L4.106: Telegram is the default PRIMARY; iMessage-primary is opt-in via env.
        with patch.object(ai_council, "imessage_enabled", return_value=True), \
                patch.dict(os.environ, {"AI_COUNCIL_IMESSAGE_PRIMARY": "true"}, clear=False), \
                patch.object(ai_council, "telegram_send_message_with_markup") as tg:
            ok = ai_council.deliver_proactive("123", "☀️ Brief: 2 akcje czekają")
        self.assertTrue(ok)
        tg.assert_not_called()
        pending = ai_council.imessage_outbox_pending()
        self.assertEqual(len(pending), 1)
        self.assertEqual(pending[0]["kind"], "proactive")
        self.assertEqual(pending[0]["to"], "")


class SetupOnboardingTests(unittest.TestCase):
    """L4.83: /setup onboarding checklist (read-only status)."""

    def test_setup_lists_channels_and_integrations(self):
        out = ai_council.setup_response()
        self.assertIn("Setup / Onboarding", out)
        self.assertIn("Telegram", out)
        self.assertIn("iMessage", out)
        self.assertIn("Google", out)
        self.assertIn("GitHub", out)
        self.assertIn("NEXT:", out)

    def test_setup_routes_explicit_and_natural(self):
        self.assertEqual(ai_council.route_text("/setup")["command"], "/setup")
        natural = ai_council.route_message("co podłączyć", chat_id="553")
        self.assertEqual(natural["command"], "/setup")

    def test_setup_dispatches_in_build_response(self):
        out = ai_council.build_response({"command": "/setup", "prompt": ""})
        self.assertIn("Onboarding", out)

    def test_setup_is_readonly_router_allowed(self):
        self.assertIn("/setup", ai_council.READONLY_RECIPE_COMMANDS)
        self.assertIn("/setup", ai_council.FRONT_QUALITY_TECHNICAL_COMMANDS)
        self.assertIn("/setup", ai_council.LLM_ROUTER_ALLOWED_COMMANDS)


class WatchlistTests(unittest.TestCase):
    """L4.85: topic watchlist + Bartek profile."""

    def setUp(self):
        self._tmp = temp_dir()
        self.addCleanup(self._tmp.cleanup)
        self._state = Path(self._tmp.name)
        p = patch.object(ai_council, "STATE_DIR", self._state)
        p.start()
        self.addCleanup(p.stop)

    def test_default_topics_when_no_file(self):
        topics = ai_council.watch_topics()
        self.assertIn("Poke", topics)
        self.assertIn("OpenClaw", topics)
        self.assertEqual(len(topics), len(ai_council.DEFAULT_WATCH_TOPICS))

    def test_add_remove_dedup_roundtrip(self):
        ai_council.watch_response("add Tesla")
        self.assertIn("Tesla", ai_council.watch_topics())
        ai_council.watch_response("add tesla")  # dedup, case-insensitive
        self.assertEqual(sum(1 for t in ai_council.watch_topics() if t.lower() == "tesla"), 1)
        ai_council.watch_response("remove Tesla")
        self.assertNotIn("tesla", [t.lower() for t in ai_council.watch_topics()])

    def test_clear_then_defaults_returned(self):
        ai_council.watch_response("clear")
        # empty file -> watch_topics() falls back to defaults (never an empty watchlist)
        self.assertEqual(ai_council.watch_topics(), list(ai_council.DEFAULT_WATCH_TOPICS))

    def test_watch_routes_explicit_and_natural(self):
        self.assertEqual(ai_council.route_text("/watch")["command"], "/watch")
        natural = ai_council.route_message("śledź Nvidia Blackwell", chat_id="553")
        self.assertEqual(natural["command"], "/watch")
        self.assertTrue(natural["prompt"].startswith("add "))

    def test_watch_is_readonly_and_front_technical(self):
        self.assertIn("/watch", ai_council.READONLY_RECIPE_COMMANDS)
        self.assertIn("/watch", ai_council.FRONT_QUALITY_TECHNICAL_COMMANDS)
        # Deliberately NOT in the LLM router allowlist (avoids auto-triggering Grok research).
        self.assertNotIn("/watch", ai_council.LLM_ROUTER_ALLOWED_COMMANDS)

    def test_watch_research_one_topic_calls_grok(self):
        captured = {}

        def fake_research(topic, max_chars=None, task_id=""):
            captured["topic"] = topic
            return "[Grok X Research] ok"

        with patch.object(ai_council, "grok_x_research_response", side_effect=fake_research):
            out = ai_council.watch_response("research Poke")
        self.assertEqual(captured["topic"], "Poke")
        self.assertIn("ok", out)

    def test_watch_research_all_combines_topics(self):
        captured = {}

        def fake_research(topic, max_chars=None, task_id=""):
            captured["topic"] = topic
            return "[Grok X Research] ok"

        with patch.object(ai_council, "grok_x_research_response", side_effect=fake_research):
            ai_council.watch_response("research")
        self.assertIn("Poke", captured["topic"])
        self.assertIn("OpenClaw", captured["topic"])

    def test_seed_profile_persists_trusted_facts(self):
        db = self._state / "memory.sqlite"
        with patch.object(ai_council, "MEMORY_DB", db):
            saved = ai_council.seed_bartek_profile()
            self.assertGreaterEqual(saved, 5)
            facts = " ".join(f.get("value", "") for f in ai_council.active_user_facts(limit=30))
        self.assertIn("Europe/Warsaw", facts)
        self.assertIn("approval", facts)

    def test_watch_digest_off_by_default(self):
        # conftest forces AI_COUNCIL_WATCH_DIGEST off -> no Grok call, no brief line.
        with patch.object(ai_council, "grok_x_research_response") as grok:
            self.assertEqual(ai_council.maybe_refresh_watch_digest(), 0)
        grok.assert_not_called()
        self.assertEqual(ai_council.watch_digest_brief_line(), "")

    def test_watch_digest_refreshes_once_when_enabled(self):
        now = datetime(2026, 6, 8, 6, 0, tzinfo=timezone.utc)
        calls = {"n": 0}

        def fake_research(q, max_chars=None, task_id=""):
            calls["n"] += 1
            return "[Grok X Research] Poke wypuścił X; OpenClaw update Y."

        with patch.object(ai_council, "watch_digest_enabled", return_value=True), \
             patch.object(ai_council, "grok_x_research_response", side_effect=fake_research):
            self.assertEqual(ai_council.maybe_refresh_watch_digest(now), 1)
            # second call same day = cached, no extra Grok call
            self.assertEqual(ai_council.maybe_refresh_watch_digest(now), 0)
            self.assertEqual(calls["n"], 1)
            line = ai_council.watch_digest_brief_line(now)
        self.assertIn("Research dnia", line)
        self.assertIn("OpenClaw", line)


class IMessageInboundScaffoldTests(unittest.TestCase):
    """L4.90: inbound (two-way) gating + FDA detection + status (live build needs FDA)."""

    def test_inbound_off_by_default(self):
        self.assertFalse(ai_council.imessage_inbound_enabled())

    def test_apple_date_to_unix_handles_ns_and_seconds(self):
        # 2001-01-01T00:00:00Z is the Apple epoch -> 978307200 unix.
        self.assertEqual(ai_council.apple_date_to_unix(0), 978307200.0)
        # nanoseconds form (modern macOS): 1 day after apple epoch
        self.assertEqual(ai_council.apple_date_to_unix(86400 * 1_000_000_000), 978307200.0 + 86400)
        # seconds form (old macOS): 1 day
        self.assertEqual(ai_council.apple_date_to_unix(86400), 978307200.0 + 86400)
        self.assertEqual(ai_council.apple_date_to_unix("bad"), 0.0)

    def test_full_disk_access_false_off_macos(self):
        with patch.object(ai_council, "on_macos", return_value=False):
            self.assertFalse(ai_council.imessage_full_disk_access())

    def test_inbound_status_guides_fda_when_missing(self):
        with patch.object(ai_council, "imessage_full_disk_access", return_value=False):
            out = ai_council.imessage_inbound_status()
        self.assertIn("Full Disk Access", out)
        self.assertIn("NIE", out)

    def test_inbound_status_ready_when_fda_present(self):
        with patch.object(ai_council, "imessage_full_disk_access", return_value=True):
            out = ai_council.imessage_inbound_status()
        self.assertIn("TAK", out)

    def test_imessage_inbound_command_routes(self):
        with patch.object(ai_council, "imessage_full_disk_access", return_value=False):
            out = ai_council.imessage_response("inbound")
        self.assertIn("inbound", out.lower())
        self.assertIn("Full Disk Access", out)


class IMessageInboundReaderTests(unittest.TestCase):
    """L4.92: attributedBody decoder + self-thread dedup (loop-safety)."""

    @staticmethod
    def _ab(text: str) -> bytes:
        body = text.encode("utf-8")
        prefix = b"\x04\x0bstreamtyped\x81\xe8\x03\x84\x01@\x84\x84\x84\x12NSAttributedString"
        marker = b"NSString\x01\x94\x84\x01\x2b"
        if len(body) < 0x80:
            length = bytes([len(body)])
        else:
            length = b"\x81" + len(body).to_bytes(2, "little")
        return prefix + marker + length + body + b"\x86\x84"

    def test_decode_short_message(self):
        self.assertEqual(ai_council.imessage_decode_attributed_body(self._ab("hej, co tam?")), "hej, co tam?")

    def test_decode_long_message_extended_length(self):
        msg = "x" * 200  # >= 128 -> extended 0x81 + 2-byte length
        self.assertEqual(ai_council.imessage_decode_attributed_body(self._ab(msg)), msg)

    def test_decode_unicode_message(self):
        self.assertEqual(ai_council.imessage_decode_attributed_body(self._ab("zażółć gęślą 🚀")), "zażółć gęślą 🚀")

    def test_decode_empty_or_garbage(self):
        self.assertEqual(ai_council.imessage_decode_attributed_body(b""), "")
        self.assertEqual(ai_council.imessage_decode_attributed_body(b"no marker here"), "")

    def test_message_text_prefers_text_column(self):
        self.assertEqual(ai_council.imessage_message_text("plain text", self._ab("from blob")), "plain text")
        self.assertEqual(ai_council.imessage_message_text(None, self._ab("from blob")), "from blob")
        self.assertEqual(ai_council.imessage_message_text("", self._ab("from blob")), "from blob")

    def test_assistant_echo_dedup(self):
        sent = ["Poranny brief: ...", "ZROBIŁEM: task started"]
        # exact + whitespace/case-insensitive match -> echo (skip)
        self.assertTrue(ai_council.imessage_is_assistant_echo("poranny   brief: ...", sent))
        self.assertTrue(ai_council.imessage_is_assistant_echo("ZROBIŁEM: task started", sent))
        # a genuine user message -> not an echo (process)
        self.assertFalse(ai_council.imessage_is_assistant_echo("jaka jest pogoda?", sent))
        # empty is never processed
        self.assertTrue(ai_council.imessage_is_assistant_echo("", sent))


class SecretRotationTests(unittest.TestCase):
    """L4.91: safe secret rotation into .env (value never echoed)."""

    def setUp(self):
        self._tmp = temp_dir()
        self.addCleanup(self._tmp.cleanup)
        self._env = Path(self._tmp.name) / ".env"
        self._env.write_text(
            'TELEGRAM_BOT_TOKEN="oldtoken"\nXAI_API_KEY="oldxai"\nAI_COUNCIL_LLM_ROUTER=true\n',
            encoding="utf-8",
        )

    def test_rotates_existing_key_and_preserves_others(self):
        res = ai_council.update_env_secret("XAI_API_KEY", "NEWxai123", path=self._env)
        self.assertTrue(res["ok"])
        self.assertTrue(res["replaced"])
        self.assertEqual(res["chars"], len("NEWxai123"))
        self.assertNotIn("value", res)  # never returns the secret
        text = self._env.read_text(encoding="utf-8")
        self.assertIn('XAI_API_KEY="NEWxai123"', text)
        self.assertIn('TELEGRAM_BOT_TOKEN="oldtoken"', text)  # untouched
        self.assertIn("AI_COUNCIL_LLM_ROUTER=true", text)

    def test_appends_when_key_absent(self):
        res = ai_council.update_env_secret("GITHUB_TOKEN", "ghp_new", path=self._env)
        self.assertTrue(res["ok"])
        self.assertFalse(res["replaced"])
        self.assertIn('GITHUB_TOKEN="ghp_new"', self._env.read_text(encoding="utf-8"))

    def test_rejects_non_allowlisted_key(self):
        res = ai_council.update_env_secret("AI_COUNCIL_LLM_ROUTER", "false", path=self._env)
        self.assertFalse(res["ok"])
        # the .env must be unchanged
        self.assertIn("AI_COUNCIL_LLM_ROUTER=true", self._env.read_text(encoding="utf-8"))

    def test_rejects_empty_value(self):
        res = ai_council.update_env_secret("XAI_API_KEY", "   ", path=self._env)
        self.assertFalse(res["ok"])


class ConversationBrainTests(unittest.TestCase):
    """Capability A — unified Conversation Brain.

    Covers the Definition of Done: intent taxonomy, clarify-before-act slot flow,
    food + coding flows, the anti-debug/JSON sanitizer, conservatism (does not hijack
    existing explicit/keyword/llm/fallback routes), and iMessage thread persistence.
    """

    def setUp(self):
        self._tmp = temp_dir()
        self.addCleanup(self._tmp.cleanup)
        base = Path(self._tmp.name)
        self._p1 = patch.object(ai_council, "CLARIFICATIONS_FILE", base / "clarifications.jsonl")
        self._p2 = patch.object(ai_council, "CONVERSATIONS_FILE", base / "conversations.jsonl")
        self._p1.start()
        self.addCleanup(self._p1.stop)
        self._p2.start()
        self.addCleanup(self._p2.stop)
        self.cid = "brainA-553"

    # --- (c) taxonomy: detects the full intent set ---
    def test_classify_intent_covers_full_taxonomy(self):
        cases = {
            "chcę jedzenie": "food_local",
            "popraw kod w utils.py": "coding",
            "przypomnij mi jutro o lekach": "reminder",
            "zapamiętaj że lubię kawę": "memory_save",
            "co wiesz o moim projekcie": "memory_recall",
            "zrób research o agentach AI": "research",
            "stwórz recipe codziennie o 8 health digest": "recipe",
            "zatwierdź": "approval_cancel",
            "usuń wszystkie pliki": "risky_action",
            "hej": "casual_chat",
            "qwerty asdf zxcv": "unknown",
        }
        for text, expected in cases.items():
            self.assertEqual(ai_council.classify_intent(text)["intent"], expected, f"{text!r}")

    # --- (d,g) food: clarify-before-act, one slot per turn, options + approval ---
    def test_food_flow_fills_slots_then_delivers_clean_search(self):
        r = ai_council.route_message("chcę jedzenie", chat_id=self.cid)
        self.assertEqual(r["command"], "conversation")
        self.assertEqual(r["intent"], "food_local")
        self.assertIn("ochotę", ai_council.build_response(r, chat_id=self.cid))
        ai_council.route_message("włoska", chat_id=self.cid)
        ai_council.route_message("do 60 zł", chat_id=self.cid)
        captured = {}

        def fake_research(query, *a, **k):
            captured["q"] = query
            return "Trattoria Roma — ~50 zł, dostawa. Pizza Nuova — ~40 zł, na wynos."

        with patch.object(ai_council, "grok_x_research_response", side_effect=fake_research):
            r = ai_council.route_message("centrum", chat_id=self.cid)
        # all slots filled -> ONE clean delivered result (not an @research route, no [Council])
        self.assertEqual(r["command"], "conversation")
        self.assertEqual(r["intent"], "food_local")
        self.assertIn("Trattoria", r["reply"])
        self.assertNotIn("[Council]", r["reply"])
        self.assertIn("włoska", captured["q"])
        self.assertIn("centrum", captured["q"])
        self.assertIsNone(ai_council.get_pending_clarification(self.cid))

    def test_food_flow_cancel_clears_pending(self):
        ai_council.route_message("chcę jedzenie", chat_id=self.cid)
        self.assertIsNotNone(ai_council.get_pending_clarification(self.cid))
        r = ai_council.route_message("anuluj", chat_id=self.cid)
        self.assertEqual(r["command"], "conversation")
        self.assertIn("odpuszczam", ai_council.build_response(r, chat_id=self.cid).lower())
        self.assertIsNone(ai_council.get_pending_clarification(self.cid))

    def test_food_flow_location_starting_with_nie_is_not_cancelled(self):
        # Regression for the live "asked what I'd eat but couldn't continue" bug: a location
        # answer like "nie wiem"/"niedaleko"/a street "Niemcewicza" must NOT be treated as the
        # cancel word "nie" (startswith) — that silently killed the flow.
        ai_council.route_message("chcę jedzenie", chat_id=self.cid)
        ai_council.route_message("włoska", chat_id=self.cid)
        ai_council.route_message("bez limitu", chat_id=self.cid)  # -> asks location
        captured = {}
        with patch.object(ai_council, "grok_x_research_response",
                          side_effect=lambda q, *a, **k: captured.update(q=q) or "Miejsce A, Miejsce B."):
            r = ai_council.route_message("niedaleko Niemcewicza", chat_id=self.cid)
        self.assertEqual(r["command"], "conversation")
        self.assertNotIn("odpuszczam", r["reply"].lower())   # NOT cancelled
        self.assertIn("Niemcewicza", captured["q"])           # used as the location
        self.assertIsNone(ai_council.get_pending_clarification(self.cid))

    # --- (i) coding: plan/job/test path via delegation ---
    def test_coding_with_target_routes_to_delegate(self):
        r = ai_council.route_message("popraw kod w utils.py", chat_id=self.cid)
        self.assertEqual(r["command"], "/delegate")
        self.assertEqual(r["intent"], "coding")
        self.assertIn("utils.py", r["prompt"])

    def test_coding_without_target_asks_then_delegates(self):
        r = ai_council.route_message("popraw kod", chat_id=self.cid)
        self.assertEqual(r["command"], "conversation")
        self.assertEqual(r["intent"], "coding")
        r = ai_council.route_message("w pliku api.py dodaj retry", chat_id=self.cid)
        self.assertEqual(r["command"], "/delegate")
        self.assertIn("api.py", r["prompt"])
        self.assertIsNone(ai_council.get_pending_clarification(self.cid))

    # --- (a,b,h,j) conservatism: do not hijack existing routes ---
    def test_brain_does_not_hijack_explicit_keyword_or_fallback(self):
        self.assertEqual(ai_council.route_message("@codex ping", chat_id=self.cid)["command"], "@codex")
        self.assertEqual(ai_council.route_message("status", chat_id=self.cid)["command"], "/status")
        rr = ai_council.route_message("zrób research o agentach", chat_id=self.cid)
        self.assertEqual(rr["command"], "@research")
        self.assertEqual(rr["route_source"], "keyword")
        self.assertEqual(ai_council.route_message("hej", chat_id=self.cid)["command"], "/chat")
        self.assertEqual(ai_council.route_message("qwerty asdf zxcv", chat_id=self.cid)["command"], "/chat")

    def test_explicit_command_escapes_pending_clarification(self):
        ai_council.route_message("chcę jedzenie", chat_id=self.cid)
        r = ai_council.route_message("/status", chat_id=self.cid)
        self.assertEqual(r["command"], "/status")
        self.assertIsNotNone(ai_council.get_pending_clarification(self.cid))

    def test_pending_answer_wins_over_keyword_router(self):
        ai_council.route_message("chcę jedzenie", chat_id=self.cid)
        r = ai_council.route_message("włoska", chat_id=self.cid)
        self.assertEqual(r["command"], "conversation")
        self.assertEqual(r["intent"], "food_local")

    # --- (e) enforced anti-debug/JSON sanitizer ---
    def test_sanitize_brain_reply_strips_debug_and_json(self):
        self.assertEqual(
            ai_council.sanitize_brain_reply("route=secret\n[Codex] noise\nNormalna odpowiedź"),
            "Normalna odpowiedź",
        )
        self.assertNotIn("{", ai_council.sanitize_brain_reply('{"command":"/x"}'))
        self.assertTrue(ai_council.sanitize_brain_reply("   ").strip())

    def test_conversation_command_returns_sanitized_reply(self):
        out = ai_council.build_response(
            {"command": "conversation", "reply": "route=secret\n[Codex] x\nCześć Bartek"},
            chat_id=self.cid,
        )
        self.assertEqual(out, "Cześć Bartek")

    # --- (B Step 2) Shortcuts plain text shares the brain; URL/command preserved ---
    def test_shortcut_plain_text_routes_through_brain(self):
        route = ai_council.shortcut_route_for_text({"text": "chcę jedzenie"}, "chcę jedzenie", chat_id=self.cid)
        self.assertEqual(route["command"], "conversation")
        self.assertEqual(route["intent"], "food_local")

    def test_shortcut_url_research_and_explicit_command_preserved(self):
        url_route = ai_council.shortcut_route_for_text(
            {"url": "https://x.com/a", "mode": "url"}, "https://x.com/a", chat_id=self.cid
        )
        self.assertIn("research_brief", str(url_route.get("prompt", "")))
        cmd_route = ai_council.shortcut_route_for_text({"command": "/status"}, "x", chat_id=self.cid)
        self.assertEqual(cmd_route["command"], "/status")

    # --- (B Step 3) GPS location extraction + food-slot auto-fill via Shortcuts ---
    def test_shortcut_text_from_payload_extracts_gps(self):
        text = ai_council.shortcut_text_from_payload(
            {"latitude": 52.261, "longitude": 20.989, "place_name": "Żoliborz"}
        )
        self.assertIn("lokalizacja", text.lower())
        self.assertIn("Żoliborz", text)
        self.assertIn("52.26100", text)

    def test_shortcut_gps_fills_food_location_then_searches(self):
        ai_council.route_message("chcę jedzenie", chat_id=self.cid)   # -> asks cuisine
        ai_council.route_message("włoska", chat_id=self.cid)          # -> asks budget
        ai_council.route_message("do 60 zł", chat_id=self.cid)        # -> asks location
        payload = {"latitude": 52.261, "longitude": 20.989, "place_name": "Żoliborz"}
        text = ai_council.shortcut_text_from_payload(payload)
        captured = {}
        with patch.object(ai_council, "grok_x_research_response",
                          side_effect=lambda q, *a, **k: captured.update(q=q) or "Miejsce A, Miejsce B."):
            route = ai_council.shortcut_route_for_text(payload, text, chat_id=self.cid)
        # GPS pin fills the location slot -> all slots filled -> clean delivered search
        self.assertEqual(route["command"], "conversation")
        self.assertIn("Żoliborz", captured["q"])
        self.assertIsNone(ai_council.get_pending_clarification(self.cid))

    def test_telegram_location_fills_food_slot_via_brain(self):
        loc_text = ai_council.telegram_location_to_text({"latitude": 52.261, "longitude": 20.989})
        self.assertIn("lokalizacja", loc_text)
        self.assertIn("52.26100", loc_text)
        ai_council.route_message("chcę jedzenie", chat_id=self.cid)   # -> cuisine
        ai_council.route_message("sushi", chat_id=self.cid)           # -> budget
        ai_council.route_message("do 80 zł", chat_id=self.cid)        # -> location
        captured = {}
        with patch.object(ai_council, "grok_x_research_response",
                          side_effect=lambda q, *a, **k: captured.update(q=q) or "Sushi A, Sushi B."):
            r = ai_council.route_message(loc_text, chat_id=self.cid)  # GPS pin as the location answer
        self.assertEqual(r["command"], "conversation")
        self.assertIn("sushi", captured["q"])
        self.assertIsNone(ai_council.get_pending_clarification(self.cid))

    # --- (P1) the LLM brain composes clean conversational replies ---
    def test_brain_loop_uses_llm_with_system_prompt_and_context(self):
        def fake_cfg(key, default=""):
            return {
                "XAI_API_KEY": "xai-test",
                "AI_COUNCIL_POKE_CHAT_USE_GROK": "true",
                "AI_COUNCIL_POKE_CHAT_OPERATOR": "grok",
            }.get(key, default)

        ai_council.append_conversation_turn(self.cid, "user", "lecę jutro do Pragi")
        with patch.object(ai_council, "cfg", side_effect=fake_cfg), patch.object(
            ai_council, "memory_context_for_prompt", return_value=""
        ), patch.object(
            ai_council, "request_json",
            return_value={"choices": [{"message": {"content": "Jasne — co konkretnie ogarniamy przed wyjazdem?"}}]},
        ) as rj:
            reply = ai_council.brain_loop("co mam zrobić?", chat_id=self.cid)
        self.assertIn("Jasne", reply)
        self.assertNotIn("[Council]", reply)
        msgs = rj.call_args.kwargs["payload"]["messages"]
        self.assertIn("kumaty kumpel", msgs[0]["content"])            # BRAIN_SYSTEM_PROMPT
        self.assertTrue(any("Pragi" in m["content"] for m in msgs))   # recent conversation included

    def test_brain_loop_without_llm_is_clean_and_honest(self):
        # No LLM at all -> graceful, clean, non-template reply (never the old sludge).
        # brain_decide patched to None so the test never calls a live Claude CLI.
        with patch.object(ai_council, "brain_decide", return_value=None):
            reply = ai_council.brain_loop("zaplanuj mi tydzień", chat_id=self.cid)
        self.assertTrue(reply.strip())
        for bad in ("[Council]", "DECYZJA:", "FAKTY:", "NEXT:", "task-", "Przyjąłem. Najlepszy"):
            self.assertNotIn(bad, reply)

    def test_brain_loop_smalltalk_is_local_no_network(self):
        with patch.object(ai_council, "request_json") as rj:
            reply = ai_council.brain_loop("siema", chat_id=self.cid)
        rj.assert_not_called()
        self.assertTrue(reply.strip())
        self.assertNotIn("[Council]", reply)

    def test_brain_reply_strips_debug_and_operator_labels(self):
        def fake_cfg(key, default=""):
            return {"XAI_API_KEY": "xai-test", "AI_COUNCIL_POKE_CHAT_OPERATOR": "grok"}.get(key, default)

        leaky = "[Grok] noise\nroute=secret\nNormalna odpowiedź dla Bartka."
        with patch.object(ai_council, "cfg", side_effect=fake_cfg), patch.object(
            ai_council, "memory_context_for_prompt", return_value=""
        ), patch.object(
            ai_council, "request_json", return_value={"choices": [{"message": {"content": leaky}}]}
        ):
            reply = ai_council.brain_loop("opowiedz coś", chat_id=self.cid)
        self.assertIn("Normalna odpowiedź", reply)
        self.assertNotIn("[Grok]", reply)
        self.assertNotIn("route=secret", reply)

    # --- (P2/P3) brain tool-calling: act, don't just chat ---
    def test_brain_decide_parses_tool_call(self):
        def fake_cfg(key, default=""):
            return {"XAI_API_KEY": "xai-test", "AI_COUNCIL_POKE_CHAT_OPERATOR": "grok"}.get(key, default)

        tool_resp = {"choices": [{"message": {"content": None, "tool_calls": [
            {"function": {"name": "save_fact", "arguments": '{"fact": "Bartek lubi kawę bez cukru"}'}}]}}]}
        with patch.object(ai_council, "cfg", side_effect=fake_cfg), patch.object(
            ai_council, "memory_context_for_prompt", return_value=""
        ), patch.object(ai_council, "request_json", return_value=tool_resp):
            decision = ai_council.brain_decide("zapisz że lubię kawę bez cukru", chat_id=self.cid)
        self.assertEqual(decision["action"], "save_fact")
        self.assertEqual(decision["args"]["fact"], "Bartek lubi kawę bez cukru")

    def test_brain_execute_save_then_recall_fact_end_to_end(self):
        with temp_dir() as tmp, patch.object(ai_council, "MEMORY_DB", Path(tmp) / "memory.sqlite"):
            saved = ai_council.brain_execute_tool("save_fact", {"fact": "mój lot jest w piątek"}, "zapisz to", self.cid)
            recalled = ai_council.brain_execute_tool("recall_fact", {"query": "kiedy mam lot"}, "kiedy lot", self.cid)
        self.assertIn("Zapamiętane", saved)
        self.assertIn("piątek", recalled)
        self.assertNotIn("[Council]", recalled)

    def test_brain_loop_dispatches_reminder_with_clean_confirmation(self):
        leaky = "[Council] Przypomnienie ✅ (rem-1): „leki” — jutro o 15. Lista: /reminders"
        with patch.object(ai_council, "brain_decide", return_value={"action": "set_reminder", "args": {"what": "leki", "when": "jutro o 15"}}), \
             patch.object(ai_council, "add_reminder", return_value=leaky):
            reply = ai_council.brain_loop("przypomnij mi jutro o 15 o lekach", chat_id=self.cid)
        self.assertIn("przypomn", reply.lower())
        for bad in ("[Council]", "rem-", "/reminders"):
            self.assertNotIn(bad, reply)

    def test_brain_loop_dispatches_save_fact_tool(self):
        with temp_dir() as tmp:
            with patch.object(ai_council, "MEMORY_DB", Path(tmp) / "memory.sqlite"), patch.object(
                ai_council, "brain_decide", return_value={"action": "save_fact", "args": {"fact": "lubię sushi"}}
            ):
                reply = ai_council.brain_loop("zapamiętaj że lubię sushi", chat_id=self.cid)
        self.assertIn("Zapamiętane", reply)
        self.assertIn("sushi", reply)
        self.assertNotIn("[Council]", reply)

    # --- (a) iMessage shares ONE thread: respond-b64 persists turns ---
    def test_imessage_respond_b64_persists_user_and_assistant_turns(self):
        b64 = base64.b64encode(b"hej").decode("ascii")
        argv = ["ai_council.py", "respond-b64", "--b64", b64]
        # L4.103: no --sender means empty handle; with fail-closed allowlist that
        # would be denied, so opt into open mode explicitly for this turn-persist test.
        with patch.dict("os.environ", {"AI_COUNCIL_IMESSAGE_ALLOW_OPEN": "true"}), \
             patch.object(ai_council, "configure_utf8_stdio", lambda: None), \
             patch.object(sys, "argv", argv), \
             contextlib.redirect_stdout(io.StringIO()):
            rc = ai_council.main()
        self.assertEqual(rc, 0)
        turns = ai_council.read_jsonl(ai_council.CONVERSATIONS_FILE)
        roles = [t.get("role") for t in turns]
        self.assertIn("user", roles)
        self.assertIn("assistant", roles)
        self.assertGreaterEqual(len(turns), 2)



if __name__ == "__main__":
    unittest.main()
