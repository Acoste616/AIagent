"""L4.108 tests: YouTube subscriptions in the radar + natural Gmail/Calendar briefs.

Hermetic — no network, no subprocess. The OAuth helper and request_json are
patched; conftest already blanks GOOGLE_* secrets so oauth is OFF by default.
"""

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import ai_council


def _page(items, next_token=""):
    page = {"items": [
        {"snippet": {"title": name, "resourceId": {"channelId": cid}}} for name, cid in items
    ]}
    if next_token:
        page["nextPageToken"] = next_token
    return page


class RadarYoutubeSubscriptionsTests(unittest.TestCase):
    def test_no_oauth_returns_empty(self):
        # conftest blanks GOOGLE_* -> google_oauth_configured() is False
        self.assertEqual(ai_council.radar_youtube_subscriptions({}), [])

    def test_fetch_paginates_max_two_pages_and_dedupes(self):
        state = {"sources": {}}
        calls = []

        def fake_request(url, **kwargs):
            calls.append(url)
            if "pageToken" not in url:
                return _page([("Kanal A", "UCaaa"), ("Kanal A bis", "UCaaa"), ("Kanal B", "UCbbb")], next_token="T2")
            return _page([("Kanal C", "UCccc")], next_token="T3-nigdy-nie-pobrana")

        with patch.object(ai_council, "google_oauth_configured", return_value=True), patch.object(
            ai_council, "google_access_token", return_value=("available", "tok")
        ), patch.object(ai_council, "request_json", side_effect=fake_request):
            subs = ai_council.radar_youtube_subscriptions(state)

        self.assertEqual(len(calls), 2)  # max 2 strony mimo trzeciego pageToken
        self.assertIn("pageToken=T2", calls[1])
        self.assertEqual([s["channel_id"] for s in subs], ["UCaaa", "UCbbb", "UCccc"])  # dedupe UCaaa
        self.assertEqual(subs[0]["name"], "Kanal A")
        # cache zapisany w przekazanym state (radar_collect zapisze go raz na końcu)
        self.assertEqual(state["yt_subs_day"], ai_council.today_utc())
        self.assertEqual([s["channel_id"] for s in state["yt_subs"]], ["UCaaa", "UCbbb", "UCccc"])

    def test_same_day_cache_skips_api(self):
        state = {
            "yt_subs": [{"name": "Stary", "channel_id": "UCold"}],
            "yt_subs_day": ai_council.today_utc(),
        }
        with patch.object(ai_council, "google_oauth_configured", return_value=True), patch.object(
            ai_council, "google_access_token", side_effect=AssertionError("nie wolno wołać API w cache-day")
        ), patch.object(ai_council, "request_json", side_effect=AssertionError("nie wolno wołać API w cache-day")):
            subs = ai_council.radar_youtube_subscriptions(state)
        self.assertEqual(subs, [{"name": "Stary", "channel_id": "UCold"}])

    def test_api_error_falls_back_to_stale_cache(self):
        state = {
            "yt_subs": [{"name": "Wczorajszy", "channel_id": "UCold"}],
            "yt_subs_day": "2020-01-01",  # nieświeży -> próbuje API
        }
        with patch.object(ai_council, "google_oauth_configured", return_value=True), patch.object(
            ai_council, "google_access_token", return_value=("available", "tok")
        ), patch.object(ai_council, "request_json", return_value={"ok": False, "error": "http_403"}):
            subs = ai_council.radar_youtube_subscriptions(state)
        self.assertEqual([s["channel_id"] for s in subs], ["UCold"])
        self.assertEqual(state["yt_subs_day"], "2020-01-01")  # cache-day NIE podbity po błędzie

    def test_oauth_token_error_falls_back_to_cache(self):
        state = {"yt_subs": [{"name": "C", "channel_id": "UCc"}], "yt_subs_day": "2020-01-01"}
        with patch.object(ai_council, "google_oauth_configured", return_value=True), patch.object(
            ai_council, "google_access_token", return_value=("oauth_error: http_400", "")
        ):
            subs = ai_council.radar_youtube_subscriptions(state)
        self.assertEqual([s["channel_id"] for s in subs], ["UCc"])

    def test_own_state_persists_cache_to_disk(self):
        with tempfile.TemporaryDirectory() as tmp:
            with patch.object(ai_council, "STATE_DIR", Path(tmp)), patch.object(
                ai_council, "google_oauth_configured", return_value=True
            ), patch.object(
                ai_council, "google_access_token", return_value=("available", "tok")
            ), patch.object(
                ai_council, "request_json", return_value=_page([("K", "UCk")])
            ):
                subs = ai_council.radar_youtube_subscriptions()
                self.assertEqual([s["channel_id"] for s in subs], ["UCk"])
                self.assertEqual(ai_council.radar_state().get("yt_subs_day"), ai_council.today_utc())


class RadarChannelsCombinedTests(unittest.TestCase):
    def test_union_dedupe_watchlist_first(self):
        watchlist = {"yt_channels": [{"name": "Watch", "channel_id": "UCw"}, {"name": "Both", "channel_id": "UCboth"}]}
        subs = [{"name": "Both (sub)", "channel_id": "UCboth"}, {"name": "Sub", "channel_id": "UCs"}]
        with patch.object(ai_council, "radar_youtube_subscriptions", return_value=subs):
            channels = ai_council.radar_yt_channels_combined(watchlist, {"sources": {}})
        self.assertEqual([c["channel_id"] for c in channels], ["UCw", "UCboth", "UCs"])
        self.assertEqual(channels[1]["name"], "Both")  # nazwa z watchlisty wygrywa

    def test_limit_env_keeps_watchlist_priority(self):
        watchlist = {"yt_channels": [{"name": f"W{i}", "channel_id": f"UCw{i}"} for i in range(3)]}
        subs = [{"name": f"S{i}", "channel_id": f"UCs{i}"} for i in range(10)]
        with patch.object(ai_council, "radar_youtube_subscriptions", return_value=subs), patch.dict(
            "os.environ", {"AI_COUNCIL_RADAR_YT_MAX_CHANNELS": "4"}
        ):
            channels = ai_council.radar_yt_channels_combined(watchlist, {"sources": {}})
        self.assertEqual([c["channel_id"] for c in channels], ["UCw0", "UCw1", "UCw2", "UCs0"])

    def test_no_oauth_means_watchlist_only(self):
        watchlist = {"yt_channels": [{"name": "Watch", "channel_id": "UCw"}]}
        # bez patcha: conftest blankuje GOOGLE_* -> subskrypcje = []
        channels = ai_council.radar_yt_channels_combined(watchlist, {"sources": {}})
        self.assertEqual([c["channel_id"] for c in channels], ["UCw"])

    def test_radar_collect_survives_subscription_explosion(self):
        """Fail-safe: nawet gdyby unia kanałów rzuciła, radar_collect żyje dalej."""
        with tempfile.TemporaryDirectory() as tmp:
            with patch.object(ai_council, "STATE_DIR", Path(tmp)), patch.object(
                ai_council, "radar_yt_channels_combined", side_effect=RuntimeError("boom")
            ), patch.object(ai_council, "radar_fetch_text", return_value=""), patch.object(
                ai_council, "request_json", return_value={"ok": False, "error": "url_error"}
            ), patch.object(ai_council, "radar_x_highlights", return_value=""):
                data = ai_council.radar_collect()
        self.assertEqual(data["yt"], [])


class GoogleBriefNaturalRoutingTests(unittest.TestCase):
    def _route(self, text):
        return ai_council.natural_intent_route(text, text.lower())

    def test_mail_phrases_route_to_gmail_brief(self):
        for text in ("sprawdź maile", "sprawdz maile", "co w skrzynce", "co na mailu", "przejrzyj maile", "Sprawdź maile?"):
            route = self._route(text)
            self.assertIsNotNone(route, text)
            self.assertEqual(route["command"], "/connector", text)
            self.assertEqual(route["mode"], "connector_brief", text)
            self.assertEqual(route["prompt"], "brief gmail in:inbox", text)

    def test_calendar_phrases_route_to_calendar_brief(self):
        cases = {
            "co mam w kalendarzu": "brief calendar najbliższe",
            "co w kalendarzu": "brief calendar najbliższe",
            "jakie mam spotkania": "brief calendar najbliższe",
            "co mam jutro w kalendarzu": "brief calendar jutro",
            "co mam w kalendarzu w piątek": "brief calendar w piątek",
        }
        for text, prompt in cases.items():
            route = self._route(text)
            self.assertIsNotNone(route, text)
            self.assertEqual(route["command"], "/connector", text)
            self.assertEqual(route["prompt"], prompt, text)

    def test_near_misses_do_not_hit_brief(self):
        # exact-match kontrakt: podobne, ale inne frazy NIE wpadają do connector_brief
        for text in ("sprawdź mailera", "sprawdź maile od szefa", "co w skrzynce biegów", "kalendarz adwentowy"):
            route = self._route(text)
            if route is not None:
                self.assertNotEqual(route.get("mode"), "connector_brief", text)

    def test_existing_contract_phrases_unchanged(self):
        # routing contract: stare frazy connectorowe trzymają swoje trasy
        self.assertEqual(self._route("sync kalendarz jutro")["mode"], "connector_sync")
        self.assertEqual(self._route("draft gmail do Jana o spotkaniu")["mode"], "connector_draft")
        self.assertEqual(self._route("brief")["mode"], "brief")
        self.assertEqual(self._route("co mam dzisiaj")["mode"], "brief")


if __name__ == "__main__":
    unittest.main()
