"""L4.105 RADAR tests (hermetic — no live YouTube/GitHub/Grok/Claude calls).

The radar may ONLY: read-only GET YouTube RSS / GitHub trending / GitHub releases
(patched here), make ONE Grok X research call and ONE Claude compose call (both
patched), persist its watchlist+markers under STATE_DIR, and deliver one digest
(iMessage-first + Telegram with inline buttons). No external writes.
"""

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import ai_council

FIXED_RSS = """<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <title>Kanal Testowy</title>
  <entry>
    <id>yt:video:AAA</id>
    <title>Nowy film o agentach &amp; LLM</title>
    <link rel="alternate" href="https://www.youtube.com/watch?v=AAA"/>
    <published>2026-06-10T08:00:00+00:00</published>
  </entry>
  <entry>
    <id>yt:video:BBB</id>
    <title>Drugi film</title>
    <link rel="alternate" href="https://www.youtube.com/watch?v=BBB"/>
    <published>2026-06-09T08:00:00+00:00</published>
  </entry>
  <entry>
    <id>yt:video:CCC</id>
    <title>Trzeci film</title>
    <link rel="alternate" href="https://www.youtube.com/watch?v=CCC"/>
    <published>2026-06-08T08:00:00+00:00</published>
  </entry>
  <entry>
    <id>yt:video:DDD</id>
    <title>Czwarty (za stary, poza limitem)</title>
    <link rel="alternate" href="https://www.youtube.com/watch?v=DDD"/>
    <published>2026-06-07T08:00:00+00:00</published>
  </entry>
</feed>
"""

FIXED_TRENDING_HTML = """
<html><body>
<article class="Box-row">
  <h2 class="h3 lh-condensed"><a href="/anthropics/claude-code">claude-code</a></h2>
  <p class="col-9 color-fg-muted my-1 pr-4">Agentic coding tool &amp; CLI</p>
</article>
<article class="Box-row">
  <h2 class="h3 lh-condensed"><a href="/openai/codex">codex</a></h2>
  <p class="col-9">Lightweight coding agent</p>
</article>
<article class="Box-row">
  <h2 class="h3 lh-condensed"><a href="/foo/bar-baz.py">bar</a></h2>
</article>
</body></html>
"""


class RadarWatchlistTests(unittest.TestCase):
    def test_seed_when_file_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            with patch.object(ai_council, "STATE_DIR", Path(tmp)):
                wl = ai_council.radar_watchlist()
        self.assertIn("Claude", wl["topics"])
        self.assertIn("OpenClaw", wl["topics"])
        self.assertIn("anthropics/claude-code", wl["gh_repos"])
        self.assertEqual(wl["yt_channels"], [])

    def test_add_remove_list_roundtrip(self):
        with tempfile.TemporaryDirectory() as tmp:
            with patch.object(ai_council, "STATE_DIR", Path(tmp)):
                out = ai_council.radar_watch_add("openai/codex")
                self.assertIn("openai/codex", out)
                out = ai_council.radar_watch_add("nowy temat AI")
                self.assertIn("nowy temat AI", out)
                # duplicate is a friendly no-op
                self.assertIn("już jest", ai_council.radar_watch_add("nowy temat AI"))
                listing = ai_council.radar_watchlist_text()
                self.assertIn("openai/codex", listing)
                self.assertIn("nowy temat AI", listing)
                out = ai_council.radar_watch_remove("nowy temat AI")
                self.assertIn("Zdjęte", out)
                self.assertNotIn("nowy temat AI", ai_council.radar_watchlist_text())
                self.assertIn("Nie znalazłem", ai_council.radar_watch_remove("czegoś czego nie ma"))

    def test_add_youtube_channel_link_resolves_channel_id(self):
        with tempfile.TemporaryDirectory() as tmp:
            with patch.object(ai_council, "STATE_DIR", Path(tmp)):
                out = ai_council.radar_watch_add("https://www.youtube.com/channel/UCabcdefghij123")
                self.assertIn("filmów", out)
                wl = ai_council.radar_watchlist()
                self.assertEqual(wl["yt_channels"][0]["channel_id"], "UCabcdefghij123")

    def test_unresolvable_youtube_link_falls_back_to_topic(self):
        with tempfile.TemporaryDirectory() as tmp:
            with patch.object(ai_council, "STATE_DIR", Path(tmp)), patch.object(
                ai_council, "radar_fetch_text", return_value=""
            ):
                out = ai_council.radar_watch_add("https://youtu.be/xyz")
                self.assertIn("temat", out)

    def test_classify_item_heuristics(self):
        self.assertEqual(ai_council.radar_classify_item("owner/repo")[0], "gh")
        self.assertEqual(ai_council.radar_classify_item("https://github.com/openai/codex"), ("gh", "openai/codex"))
        self.assertEqual(ai_council.radar_classify_item("https://youtu.be/abc")[0], "yt")
        self.assertEqual(ai_council.radar_classify_item("agenci AI"), ("topic", "agenci AI"))


class RadarNaturalRoutingTests(unittest.TestCase):
    def _route(self, text):
        return ai_council.natural_intent_route(text, text.lower())

    def test_obserwuj_adds_to_radar(self):
        route = self._route("obserwuj OpenClaw")
        self.assertEqual(route["command"], "/radar")
        self.assertEqual(route["prompt"], "add OpenClaw")

    def test_przestan_obserwowac_removes(self):
        route = self._route("przestań obserwować OpenClaw")
        self.assertEqual(route["command"], "/radar")
        self.assertEqual(route["prompt"], "remove OpenClaw")

    def test_co_obserwujesz_and_watchlista_list(self):
        for text in ("co obserwujesz", "watchlista", "co obserwujesz?"):
            route = self._route(text)
            self.assertEqual(route["command"], "/radar", text)
            self.assertEqual(route["prompt"], "list", text)

    def test_radar_and_co_nowego_run_digest(self):
        for text in ("radar", "co nowego", "co ciekawego"):
            route = self._route(text)
            self.assertEqual(route["command"], "/radar", text)
            self.assertEqual(route["prompt"], "", text)

    def test_legacy_watchlist_keyword_still_goes_to_watch(self):
        # routing contract: bare "watchlist" stays on the L4.85 /watch topics
        route = self._route("watchlist")
        self.assertEqual(route["command"], "/watch")

    def test_slash_route(self):
        route = ai_council.route_text("/radar add openai/codex")
        self.assertEqual(route["command"], "/radar")
        self.assertEqual(route["prompt"], "add openai/codex")
        self.assertEqual(route["mode"], "radar")


class RadarParserTests(unittest.TestCase):
    def test_rss_parser_three_newest_with_unescape(self):
        entries = ai_council.radar_youtube_entries(FIXED_RSS, limit=3)
        self.assertEqual(len(entries), 3)
        self.assertEqual(entries[0]["title"], "Nowy film o agentach & LLM")
        self.assertEqual(entries[0]["link"], "https://www.youtube.com/watch?v=AAA")
        self.assertEqual(entries[0]["published"], "2026-06-10T08:00:00+00:00")
        self.assertNotIn("Czwarty", json.dumps(entries, ensure_ascii=False))

    def test_rss_parser_garbage_returns_empty(self):
        for garbage in ("", "<html>nie rss</html>", "<entry><title>bez linku</title></entry>"):
            self.assertEqual(ai_council.radar_youtube_entries(garbage), [], garbage)

    def test_trending_parser_extracts_repo_and_description(self):
        repos = ai_council.parse_github_trending(FIXED_TRENDING_HTML, limit=5)
        self.assertEqual(repos[0]["repo"], "anthropics/claude-code")
        self.assertEqual(repos[0]["description"], "Agentic coding tool & CLI")
        self.assertEqual(repos[1]["repo"], "openai/codex")
        self.assertEqual(repos[2]["repo"], "foo/bar-baz.py")
        self.assertEqual(repos[2]["description"], "")

    def test_trending_parser_garbage_returns_empty(self):
        self.assertEqual(ai_council.parse_github_trending("<html></html>"), [])
        self.assertEqual(ai_council.parse_github_trending(""), [])


class RadarSourceMarkerTests(unittest.TestCase):
    def test_youtube_news_only_newer_than_marker(self):
        state = {"sources": {"yt:UCx": {"last_published": "2026-06-09T08:00:00+00:00"}}}
        with patch.object(ai_council, "radar_fetch_text", return_value=FIXED_RSS):
            fresh = ai_council.radar_youtube_news([{"name": "Kanal", "channel_id": "UCx"}], state)
        self.assertEqual([e["title"] for e in fresh], ["Nowy film o agentach & LLM"])
        self.assertEqual(state["sources"]["yt:UCx"]["last_published"], "2026-06-10T08:00:00+00:00")

    def test_github_release_marker_and_silent_404(self):
        state = {"sources": {}}
        responses = {
            "https://api.github.com/repos/a/b/releases/latest": {"tag_name": "v1.2", "html_url": "https://github.com/a/b/releases/v1.2", "name": "v1.2"},
            "https://api.github.com/repos/c/d/releases/latest": {"ok": False, "error": "http_404"},
        }
        with patch.object(ai_council, "request_json", side_effect=lambda url, **kw: responses[url]):
            out = ai_council.radar_github_releases(["a/b", "c/d"], state)
            self.assertEqual([r["tag"] for r in out], ["v1.2"])
            # same tag again -> nothing new
            out2 = ai_council.radar_github_releases(["a/b", "c/d"], state)
        self.assertEqual(out2, [])


class RadarDigestFailSafeTests(unittest.TestCase):
    def test_digest_composes_when_two_of_three_sources_fail(self):
        """YT + GitHub padają (puste GET-y), zostaje samo X — digest i tak wychodzi."""
        with tempfile.TemporaryDirectory() as tmp:
            with patch.object(ai_council, "STATE_DIR", Path(tmp)), patch.object(
                ai_council, "radar_fetch_text", return_value=""
            ), patch.object(
                ai_council, "request_json", return_value={"ok": False, "error": "http_403"}
            ), patch.object(
                ai_council, "radar_x_highlights", return_value="- Głośny wątek o agentach — https://x.com/i/status/1"
            ), patch.object(ai_council, "radar_claude_compose", return_value=None):
                text = ai_council.radar_digest(send=False, on_demand=True)
        self.assertTrue(text.startswith(ai_council.RADAR_DIGEST_HEADER))
        self.assertIn("𝕏", text)
        self.assertIn("x.com/i/status/1", text)

    def test_all_sources_down_returns_friendly_silence(self):
        with tempfile.TemporaryDirectory() as tmp:
            with patch.object(ai_council, "STATE_DIR", Path(tmp)), patch.object(
                ai_council, "radar_fetch_text", return_value=""
            ), patch.object(
                ai_council, "request_json", return_value={"ok": False, "error": "url_error"}
            ), patch.object(ai_council, "radar_x_highlights", return_value=""):
                text = ai_council.radar_digest(send=False, on_demand=True)
        self.assertIn("cisza", text)
        self.assertTrue(text.startswith(ai_council.RADAR_DIGEST_HEADER))

    def test_x_highlights_blocked_grok_returns_empty(self):
        with patch.object(ai_council, "grok_x_research_response", return_value="[Grok X Research] blocked: daily call limit"):
            self.assertEqual(ai_council.radar_x_highlights(["a"]), "")
        with patch.object(ai_council, "grok_x_research_response", side_effect=RuntimeError("boom")):
            self.assertEqual(ai_council.radar_x_highlights(["a"]), "")

    def test_claude_compose_used_when_available(self):
        data = {"yt": [], "gh_trending": [{"repo": "a/b", "description": "x"}], "gh_releases": [], "x": ""}
        with patch.object(ai_council, "radar_claude_compose", return_value="🛰 Radar — co nowego dla Ciebie\n⭐ a/b — x\nMoże Cię zaciekawi: a/b. Rozwinąć?"):
            text = ai_council.radar_compose_digest(data)
        self.assertIn("⭐ a/b", text)
        with patch.object(ai_council, "radar_claude_compose", return_value="bez nagłówka"):
            text = ai_council.radar_compose_digest(data)
        self.assertTrue(text.startswith(ai_council.RADAR_DIGEST_HEADER))


class RadarDailyMarkerTests(unittest.TestCase):
    def _patched(self, tmp):
        return (
            patch.object(ai_council, "STATE_DIR", Path(tmp)),
            patch.object(ai_council, "radar_collect", return_value={"yt": [], "gh_trending": [{"repo": "a/b", "description": ""}], "gh_releases": [], "x": ""}),
            patch.object(ai_council, "radar_claude_compose", return_value=None),
        )

    def test_scheduled_once_per_day_on_demand_unlimited(self):
        with tempfile.TemporaryDirectory() as tmp:
            sent = []
            p1, p2, p3 = self._patched(tmp)
            with p1, p2, p3, patch.object(ai_council, "radar_send", side_effect=lambda c, t, m=None: sent.append(t) or True):
                first = ai_council.radar_digest(send=True, on_demand=False)
                second = ai_council.radar_digest(send=True, on_demand=False)
                self.assertIn("wysłany", first)
                self.assertIn("już był", second)
                self.assertEqual(len(sent), 1)
                # on-demand ignores the marker and never bumps it
                on_demand_1 = ai_council.radar_digest(send=False, on_demand=True)
                on_demand_2 = ai_council.radar_digest(send=False, on_demand=True)
            self.assertTrue(on_demand_1.startswith(ai_council.RADAR_DIGEST_HEADER))
            self.assertTrue(on_demand_2.startswith(ai_council.RADAR_DIGEST_HEADER))

    def test_disabled_flag_blocks_radar(self):
        with patch.dict("os.environ", {"AI_COUNCIL_RADAR_ENABLED": "false"}):
            out = ai_council.radar_digest(send=False, on_demand=True)
        self.assertIn("wyłączony", out)

    def test_response_dispatch_scheduled_vs_on_demand(self):
        calls = []
        with patch.object(
            ai_council, "radar_digest",
            side_effect=lambda send, on_demand=False, slot="am": calls.append((send, on_demand, slot)) or "ok",
        ):
            ai_council.radar_response("scheduled")
            ai_council.radar_response("scheduled pm")  # L4.107: popołudniowa porcja
            ai_council.radar_response("")
        self.assertEqual(calls, [(True, False, "am"), (True, False, "pm"), (False, True, "am")])

    def test_afternoon_slot_has_independent_daily_marker(self):
        # L4.107: rano i po południu to osobne markery — dwa przeglądy dziennie.
        with tempfile.TemporaryDirectory() as tmp:
            sent = []
            p1, p2, p3 = self._patched(tmp)
            with p1, p2, p3, patch.object(ai_council, "radar_send", side_effect=lambda c, t, m=None: sent.append(t) or True):
                am = ai_council.radar_digest(send=True, on_demand=False, slot="am")
                pm = ai_council.radar_digest(send=True, on_demand=False, slot="pm")
                pm2 = ai_council.radar_digest(send=True, on_demand=False, slot="pm")
        self.assertIn("wysłany", am)
        self.assertIn("wysłany", pm)
        self.assertIn("już był", pm2)
        self.assertEqual(len(sent), 2)


class RadarRecipeAndPolicyTests(unittest.TestCase):
    def test_recipe_registered_and_policy_clean(self):
        recipes = ai_council.default_recipes()
        self.assertIn("radar_daily", recipes)
        recipe = recipes["radar_daily"]
        self.assertTrue(recipe["enabled"])
        self.assertEqual(recipe["recipe_version"], ai_council.RADAR_VERSION)
        self.assertEqual(recipe["trigger"]["cron"], "0 8 * * *")  # 8:00 lokalnie, po quiet hours
        self.assertEqual(recipe["steps"], [{"command": "/radar", "prompt": "scheduled"}])
        self.assertIn("radar_daily", ai_council.DEFAULT_RECIPE_MANAGED_KEYS)
        # deny-by-default recipe policy must actually allow the step
        self.assertEqual(ai_council.recipe_step_violations(recipe), [])

    def test_recipe_hour_from_env(self):
        with patch.dict("os.environ", {"AI_COUNCIL_RADAR_HOUR": "10"}):
            recipe = ai_council.default_recipes()["radar_daily"]
        self.assertEqual(recipe["trigger"]["cron"], "0 10 * * *")

    def test_build_response_dispatches_to_radar(self):
        with patch.object(ai_council, "radar_response", return_value="[Radar] ok") as resp:
            out = ai_council.build_response({"command": "/radar", "operators": ["host"], "prompt": "list"})
        self.assertEqual(out, "[Radar] ok")
        resp.assert_called_once_with("list", task_id="")


class RadarDeliveryButtonsTests(unittest.TestCase):
    def test_reply_markup_buttons_within_callback_limit(self):
        markup = ai_council.radar_reply_markup()
        rows = markup["inline_keyboard"]
        datas = [btn["callback_data"] for row in rows for btn in row]
        self.assertEqual(datas, ["host:radar-x", "host:radar-gh", "host:radar-settings"])
        self.assertTrue(all(len(d.encode("utf-8")) <= 64 for d in datas))

    def test_digest_response_gets_radar_buttons(self):
        markup = ai_council.response_reply_markup("🛰 Radar — co nowego dla Ciebie\n• coś")
        self.assertEqual(markup, ai_council.radar_reply_markup())

    def test_radar_send_passes_buttons_to_telegram(self):
        sent = {}

        def fake_send(chat_id, text, markup=None):
            sent["chat_id"], sent["text"], sent["markup"] = chat_id, text, markup
            return True

        # conftest forces iMessage OFF -> deliver_proactive falls through to Telegram with markup
        with patch.object(ai_council, "telegram_send_message_with_markup", side_effect=fake_send):
            ok = ai_council.radar_send("123", "🛰 Radar — co nowego dla Ciebie", ai_council.radar_reply_markup())
        self.assertTrue(ok)
        self.assertEqual(sent["chat_id"], "123")
        self.assertEqual(sent["markup"], ai_council.radar_reply_markup())

    def test_radar_send_dual_channel_when_imessage_primary(self):
        enqueued, telegram = [], []
        with patch.object(ai_council, "imessage_primary_enabled", return_value=True), patch.object(
            ai_council, "imessage_enabled", return_value=True
        ), patch.object(ai_council, "imessage_outbox_stale", return_value=False), patch.object(
            ai_council, "imessage_outbox_enqueue", side_effect=lambda t, to="", kind="": enqueued.append(t)
        ), patch.object(
            ai_council, "telegram_send_message_with_markup", side_effect=lambda c, t, m=None: telegram.append((t, m)) or True
        ):
            ai_council.radar_send("123", "digest", ai_council.radar_reply_markup())
        self.assertEqual(enqueued, ["digest"])  # iMessage-first
        self.assertEqual(len(telegram), 1)  # plus Telegram copy with buttons
        self.assertEqual(telegram[0][1], ai_council.radar_reply_markup())

    def test_host_callbacks(self):
        with tempfile.TemporaryDirectory() as tmp:
            with patch.object(ai_council, "STATE_DIR", Path(tmp)):
                text, status = ai_council.host_callback_response("radar-settings")
                self.assertEqual(status, "host_radar_settings")
                self.assertIn("obserwuję", text)
                with patch.object(ai_council, "radar_github_trending", return_value=[{"repo": "a/b", "description": "x"}]):
                    text, status = ai_council.host_callback_response("radar-gh")
                self.assertEqual(status, "host_radar_gh")
                self.assertIn("a/b", text)
                with patch.object(ai_council, "grok_x_research_response", return_value="[Grok X Research] ok\npunkty") as grok:
                    text, status = ai_council.host_callback_response("radar-x")
                self.assertEqual(status, "host_radar_x")
                self.assertIn("Claude", grok.call_args[0][0])  # topics from the watchlist seed


if __name__ == "__main__":
    unittest.main()
