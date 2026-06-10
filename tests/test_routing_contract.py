"""Golden-path routing contract (audit task 0.3).

Table-driven safety net for ``natural_intent_route``: one representative phrase
per inline branch, asserting the routed ``mode`` (and ``command``). This file is
the regression net for the dispatch-table refactor (audit task 2.1) — any change
to the router that alters which branch wins for these phrases MUST be a
conscious decision, not an accident.

Style note: phrases are taken verbatim from the trigger sets in
``natural_intent_route`` so the contract tests the *public behaviour*
(message -> route), not internal call order. No mocks.
"""

import unittest

import ai_council


# (message, expected_mode, expected_command). expected_mode None => router must
# decline (fall through to the next routing stage).
GOLDEN_ROUTES = [
    # host status / diagnostics
    ("status", "status", "/status"),
    ("progress", "progress", "/progress"),
    ("gdzie jest task-abc", "progress", "/progress"),
    ("health", "health", "/health"),
    ("front", "front", "/front"),
    ("czemu nie odpowiada", "front", "/front"),
    ("selftest", "selftest", "/selftest"),
    ("co umiesz", "capabilities", "/capabilities"),
    ("poke parity", "poke_gap", "/poke-gap"),
    ("setup", "setup", "/setup"),
    # ops dashboards
    ("koszty", "cost", "/cost"),
    ("limity", "control", "/control"),
    ("błędy", "errors", "/errors"),
    ("nudges", "nudges", "/nudges"),
    ("co dalej", "agent_next", "/agent"),
    ("shortcuts", "shortcuts", "/shortcuts"),
    ("drafty", "drafts", "/drafts"),
    ("źródła", "sources", "/sources"),
    ("connectors", "connectors", "/connectors"),
    ("backlog", "improvements", "/improvements"),
    ("followups", "followups", "/followups"),
    ("loops", "loops", "/loops"),
    ("kolejka", "queue", "/queue"),
    ("akcje", "actions", "/actions"),
    ("goal", "goal", "/goal"),
    ("watchlist", "watch", "/watch"),
    ("śledź ceny gpu", "watch", "/watch"),
    # connectors
    ("sprawdź connector github", "connector", "/connector"),
    ("podłącz github", "connector_auth", "/connector"),
    ("draft gmail do Jana o spotkaniu", "connector_draft", "/connector"),
    ("sync kalendarz jutro", "connector_sync", "/connector"),
    ("szukaj w źródłach faktury", "source_search", "/source"),
    # task lifecycle
    ("start task-20260607-1", "start_task", "/start-task"),
    ("status task-abc", "status", "/status"),
    ("anuluj task-abc", "cancel", "/cancel"),
    ("szczegóły task-abc", "details", "/details"),
    ("fakty task-abc", "facts", "/facts"),
    ("next task-abc", "next", "/next"),
    ("dodaj task posprzątaj garaż", "task", "/task"),
    # approvals
    ("approve act-1", "approve", "/approve"),
    ("odrzuć act-1", "deny", "/deny"),
    # memory
    ("pamięć", "memory", "/memory"),
    ("pamięć projektu", "project_memory", "/project-memory"),
    ("szukaj w pamięci projektu deploy", "project_memory", "/project-memory"),
    ("szukaj w pamięci kawa", "memory", "/memory"),
    ("zapamiętaj że wolę espresso", "memory", "/memory"),
    # reminders / brief / fs / gh
    ("przypomnij mi o 15:00 weź leki", "remind", "/remind"),
    ("brief", "brief", "/brief"),
    ("przypomnienia", "remind", "/reminders"),
    ("pokaż pliki", "fs", "/fs"),
    ("przeczytaj plik notes.txt", "fs", "/fs"),
    ("issues", "gh", "/gh"),
    ("stwórz issue zepsuty status", "gh", "/gh"),
    # workspace writes
    ("zapisz plik notes.md hello", "write", "/write"),
    ("dopisz do pliku notes.md hello", "append", "/append"),
    ("zmień w pliku notes.md a na b", "patch", "/patch"),
    # heavy operators
    ("deleguj do codexa napraw testy", "delegate", "/delegate"),
    ("uruchom council oceń architekturę", "council", "/council"),
    ("zrób plan na sprint", "flow", "/flow"),
    ("claude flow przeanalizuj repo", "flow", "/flow"),
    ("research x co mówią o xai", "xresearch", "/xresearch"),
    # claimed by the earlier poke-research PREPASS branch, not the plain one:
    ("zbadaj poke onboarding", "poke_research_prepass", "/poke-research"),
    ("czy możesz zrobić research o bateriach", "research", "@research"),
    ("research ceny mieszkań w Łodzi", "research", "@research"),
    # must decline (router returns None -> later stages decide)
    ("/status", None, None),
    ("@codex hej", None, None),
    ("", None, None),
]


class RoutingContractTests(unittest.TestCase):
    def route(self, message: str):
        return ai_council.natural_intent_route(message, message.lower())

    def test_golden_routes(self):
        for message, mode, command in GOLDEN_ROUTES:
            with self.subTest(message=message):
                route = self.route(message)
                if mode is None:
                    self.assertIsNone(route, f"expected decline for {message!r}, got {route!r}")
                    continue
                self.assertIsNotNone(route, f"expected mode={mode!r} for {message!r}, router declined")
                self.assertEqual(route.get("mode"), mode, f"message={message!r} routed to {route.get('mode')!r}")
                self.assertEqual(route.get("command"), command, f"message={message!r} command {route.get('command')!r}")
                self.assertEqual(route.get("intent"), "natural")

    def test_prompt_extraction_samples(self):
        # A few branches must also carry a usable prompt, not just a mode.
        route = self.route("śledź ceny gpu")
        self.assertEqual(route["prompt"], "add ceny gpu")
        route = self.route("sprawdź connector github")
        self.assertEqual(route["prompt"], "check github")
        route = self.route("zapamiętaj że wolę espresso")
        self.assertTrue(route["prompt"].startswith("fact "), route["prompt"])
        route = self.route("anuluj task-abc")
        self.assertEqual(route["prompt"], "task-abc")

    def test_priority_order_is_contract(self):
        # "gdzie jest cel" is claimed by the earlier progress prefix, NOT poke_gap.
        # If a refactor reorders rules, this documents today's winner.
        route = self.route("gdzie jest cel")
        self.assertEqual(route["mode"], "progress")
        # "co dalej" exact -> agent inbox; "co dalej <id>" -> /next prefix route.
        self.assertEqual(self.route("co dalej")["mode"], "agent_next")
        self.assertEqual(self.route("co dalej task-1")["mode"], "next")


if __name__ == "__main__":
    unittest.main()
