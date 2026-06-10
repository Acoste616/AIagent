"""Split from tests/test_ai_council.py (audit 3.3) — classes preserved 1:1."""
# ruff: noqa: F403, F405
import unittest

from council_test_shared import *


class GrokIsolationTests(unittest.TestCase):
    """L4.79: research/operator Grok must NOT inherit personal conversation memory."""

    def _fake_cfg(self, key, default=""):
        return {"XAI_API_KEY": "xai-test"}.get(key, default)

    def test_grok_response_does_not_inject_personal_memory_by_default(self):
        captured = {}

        def fake_request_json(url, headers=None, method="GET", payload=None, timeout=30):
            captured["payload"] = payload
            return {"choices": [{"message": {"content": "czysta odpowiedź"}}]}

        with patch.object(ai_council, "cfg", side_effect=self._fake_cfg), patch.object(
            ai_council, "reserve_operator_call", return_value=(True, "", {"id": "r1"})
        ), patch.object(ai_council, "finalize_operator_call", return_value=None), patch.object(
            ai_council, "memory_context_for_prompt", return_value="Co wiem o Tobie:\n- lot jest w piątek"
        ) as mem, patch.object(ai_council, "request_json", side_effect=fake_request_json):
            ai_council.grok_response("najnowsze newsy o modelu X")

        user_content = captured["payload"]["messages"][-1]["content"]
        self.assertNotIn("lot jest w piątek", user_content)
        self.assertNotIn("Kontekst z pamięci", user_content)
        # Isolation should not even pay for a memory lookup.
        mem.assert_not_called()

    def test_grok_response_injects_memory_only_when_opted_in_and_flagged(self):
        captured = {}

        def fake_cfg(key, default=""):
            return {"XAI_API_KEY": "xai-test", "AI_COUNCIL_GROK_RESEARCH_MEMORY": "true"}.get(key, default)

        def fake_request_json(url, headers=None, method="GET", payload=None, timeout=30):
            captured["payload"] = payload
            return {"choices": [{"message": {"content": "ok"}}]}

        with patch.object(ai_council, "cfg", side_effect=fake_cfg), patch.object(
            ai_council, "reserve_operator_call", return_value=(True, "", {"id": "r1"})
        ), patch.object(ai_council, "finalize_operator_call", return_value=None), patch.object(
            ai_council, "memory_context_for_prompt", return_value="Co wiem o Tobie:\n- lot jest w piątek"
        ), patch.object(ai_council, "request_json", side_effect=fake_request_json):
            ai_council.grok_response("przypomnij mój lot", inject_memory=True)

        user_content = captured["payload"]["messages"][-1]["content"]
        self.assertIn("lot jest w piątek", user_content)

    def test_grok_x_research_never_injects_personal_memory(self):
        captured = {}

        def fake_request_json(url, headers=None, method="GET", payload=None, timeout=30):
            captured["payload"] = payload
            return {"output": [{"type": "output_text", "text": "Research OK"}]}

        with patch.object(ai_council, "cfg", side_effect=self._fake_cfg), patch.object(
            ai_council, "reserve_operator_call", return_value=(True, "", {"usage_id": "u1", "operator": "grok"})
        ), patch.object(ai_council, "finalize_operator_call", return_value=None), patch.object(
            ai_council, "memory_context_for_prompt", return_value="Co wiem o Tobie:\n- lot jest w piątek"
        ) as mem, patch.object(ai_council, "request_json", side_effect=fake_request_json):
            ai_council.grok_x_research_response("Poke features", max_chars=500)

        blob = json.dumps(captured["payload"], ensure_ascii=False)
        self.assertNotIn("lot jest w piątek", blob)
        self.assertNotIn("Kontekst z pamięci", blob)
        mem.assert_not_called()

    def test_front_chat_still_keeps_personal_memory(self):
        # Personal memory belongs to the front chat operator (Poke-style), unchanged.
        captured = {}

        def fake_cfg(key, default=""):
            return {
                "XAI_API_KEY": "xai-test",
                "AI_COUNCIL_POKE_CHAT_USE_GROK": "true",
                "AI_COUNCIL_POKE_CHAT_OPERATOR": "grok",
            }.get(key, default)

        def fake_request_json(url, headers=None, method="GET", payload=None, timeout=30):
            captured["payload"] = payload
            return {"choices": [{"message": {"content": "pamiętam"}}]}

        with patch.object(ai_council, "cfg", side_effect=fake_cfg), patch.object(
            ai_council, "reserve_operator_call", return_value=(True, "", {"id": "r1"})
        ), patch.object(ai_council, "finalize_operator_call", return_value=None), patch.object(
            ai_council, "recent_conversation", return_value=[]
        ), patch.object(
            ai_council, "memory_context_for_prompt", return_value="Co wiem o Tobie:\n- lot jest w piątek"
        ), patch.object(ai_council, "request_json", side_effect=fake_request_json):
            ai_council.poke_chat_llm_response(
                "Wyjaśnij proszę dokładnie i konkretnie jak najlepiej zaplanować mój tydzień pod ten wyjazd.",
                chat_id="553",
            )

        blob = json.dumps(captured["payload"], ensure_ascii=False)
        self.assertIn("lot jest w piątek", blob)


class MasterHostContractTests(unittest.TestCase):
    """L4.78: one canonical Poke voice with status verbs."""

    def test_contract_has_status_verbs(self):
        contract = ai_council.MASTER_HOST_CONTRACT
        for verb in ("ROBIĘ", "ZROBIŁEM", "POTRZEBUJĘ ZGODY", "NIE MOGĘ"):
            self.assertIn(verb, contract)

    def test_poke_chat_uses_master_contract_as_system(self):
        captured = {}

        def fake_cfg(key, default=""):
            return {
                "XAI_API_KEY": "xai-test",
                "AI_COUNCIL_POKE_CHAT_USE_GROK": "true",
                "AI_COUNCIL_POKE_CHAT_OPERATOR": "grok",
            }.get(key, default)

        def fake_request_json(url, headers=None, method="GET", payload=None, timeout=30):
            captured["payload"] = payload
            return {"choices": [{"message": {"content": "ok"}}]}

        with patch.object(ai_council, "cfg", side_effect=fake_cfg), patch.object(
            ai_council, "reserve_operator_call", return_value=(True, "", {"id": "r1"})
        ), patch.object(ai_council, "finalize_operator_call", return_value=None), patch.object(
            ai_council, "recent_conversation", return_value=[]
        ), patch.object(ai_council, "memory_context_for_prompt", return_value=""), patch.object(
            ai_council, "request_json", side_effect=fake_request_json
        ):
            ai_council.poke_chat_llm_response(
                "Wyjaśnij proszę dokładnie i konkretnie jak najlepiej rozplanować pracę nad tym projektem w tym tygodniu.",
                chat_id="553",
            )

        system_msg = captured["payload"]["messages"][0]
        self.assertEqual(system_msg["role"], "system")
        self.assertEqual(system_msg["content"], ai_council.MASTER_HOST_CONTRACT)


class PokeChatClaudeOperatorTests(unittest.TestCase):
    """L4.93: Claude is the default front conversation operator; Grok is the fallback."""

    LONG_PROMPT = "Wyjaśnij proszę dokładnie i konkretnie jak najlepiej rozplanować pracę nad tym projektem w tym tygodniu."

    def test_claude_is_default_operator(self):
        with patch.object(ai_council, "cfg", side_effect=lambda key, default="": default):
            self.assertEqual(ai_council.poke_chat_operator(), "claude")
            self.assertTrue(ai_council.poke_chat_claude_configured())
            self.assertTrue(ai_council.poke_chat_llm_configured())

    def test_poke_chat_uses_claude_cli_and_skips_grok(self):
        captured = {}

        class FakeProc:
            returncode = 0
            stdout = "Jasne, robię."
            stderr = ""

        def fake_run(command, **kwargs):
            captured["command"] = command
            return FakeProc()

        def fake_cfg(key, default=""):
            return {"XAI_API_KEY": "xai-test"}.get(key, default)

        with patch.object(ai_council, "cfg", side_effect=fake_cfg), patch.object(
            ai_council, "reserve_operator_call", return_value=(True, "", {"usage_id": "u1", "operator": "claude"})
        ), patch.object(ai_council, "finalize_operator_call", return_value=None), patch.object(
            ai_council, "recent_conversation", return_value=[]
        ), patch.object(ai_council, "memory_context_for_prompt", return_value=""), patch.object(
            ai_council.subprocess, "run", side_effect=fake_run
        ), patch.object(ai_council, "request_json") as grok_call:
            response = ai_council.poke_chat_llm_response(self.LONG_PROMPT, chat_id="553")

        self.assertTrue(response.startswith("[Council]"))
        self.assertIn("Jasne, robię.", response)
        grok_call.assert_not_called()
        command = captured["command"]
        idx = command.index("--append-system-prompt")
        self.assertEqual(command[idx + 1], ai_council.MASTER_HOST_CONTRACT)
        self.assertIn("-p", command)

    def test_claude_failure_falls_back_to_grok(self):
        def fake_cfg(key, default=""):
            return {"XAI_API_KEY": "xai-test"}.get(key, default)

        with patch.object(ai_council, "cfg", side_effect=fake_cfg), patch.object(
            ai_council, "reserve_operator_call", return_value=(True, "", {"usage_id": "u1"})
        ), patch.object(ai_council, "finalize_operator_call", return_value=None), patch.object(
            ai_council, "recent_conversation", return_value=[]
        ), patch.object(ai_council, "memory_context_for_prompt", return_value=""), patch.object(
            ai_council.subprocess, "run", side_effect=FileNotFoundError()
        ), patch.object(
            ai_council, "request_json", return_value={"choices": [{"message": {"content": "grok przejął"}}]}
        ):
            response = ai_council.poke_chat_llm_response(self.LONG_PROMPT, chat_id="553")

        self.assertIn("grok przejął", response)

    def test_strip_debug_metadata_removes_debug_tail(self):
        raw = 'Cześć, zrobione.\nroute={"command": "/chat"}\naudit_log=D:\\ai-council\\logs\\audit.jsonl'
        self.assertEqual(ai_council.strip_debug_metadata(raw), "Cześć, zrobione.")

    def test_claude_gate_takes_short_natural_messages(self):
        # L4.94: "chce jedzenie" must reach the LLM voice (which asks ONE follow-up),
        # not the canned local fallback. Grok-only setups keep the conservative gate.
        with patch.object(ai_council, "cfg", side_effect=lambda key, default="": default):
            self.assertTrue(ai_council.poke_chat_should_use_llm("chce jedzenie"))
            self.assertFalse(ai_council.poke_chat_should_use_llm("ok"))
            self.assertFalse(ai_council.poke_chat_should_use_llm("status"))

        def grok_cfg(key, default=""):
            return {"XAI_API_KEY": "xai-test", "AI_COUNCIL_POKE_CHAT_OPERATOR": "grok"}.get(key, default)

        with patch.object(ai_council, "cfg", side_effect=grok_cfg):
            self.assertFalse(ai_council.poke_chat_should_use_llm("chce jedzenie"))

    def test_contract_requires_single_followup_question(self):
        self.assertIn("DOPYTYWANIE", ai_council.MASTER_HOST_CONTRACT)
        self.assertIn("JEDNO", ai_council.MASTER_HOST_CONTRACT)

    def test_brain_voice_is_claude_first_with_grok_fallback(self):
        # L4.98: brain_decide dispatches Claude first; Grok only when Claude fails.
        with patch.object(
            ai_council, "brain_decide_claude", return_value={"action": "reply", "text": "Hej, jasne."}
        ), patch.object(ai_council, "brain_decide_grok") as grok:
            decision = ai_council.brain_decide("co tam?", chat_id="553")
        self.assertEqual(decision["text"], "Hej, jasne.")
        grok.assert_not_called()

        with patch.object(ai_council, "brain_decide_claude", return_value=None), patch.object(
            ai_council, "brain_decide_grok", return_value={"action": "reply", "text": "grok przejął"}
        ):
            decision = ai_council.brain_decide("co tam?", chat_id="553")
        self.assertEqual(decision["text"], "grok przejął")

    def test_brain_decide_claude_parses_tool_marker_and_reply(self):
        class FakeProc:
            returncode = 0
            stderr = ""
            stdout = 'TOOL: {"action":"save_fact","args":{"fact":"Bartek lubi sushi"}}'

        def fake_cfg(key, default=""):
            return default

        with patch.object(ai_council, "cfg", side_effect=fake_cfg), patch.object(
            ai_council, "reserve_operator_call", return_value=(True, "", {"usage_id": "u1"})
        ), patch.object(ai_council, "finalize_operator_call", return_value=None), patch.object(
            ai_council, "recent_conversation", return_value=[]
        ), patch.object(ai_council, "memory_context_for_prompt", return_value=""), patch.object(
            ai_council.subprocess, "run", return_value=FakeProc()
        ):
            decision = ai_council.brain_decide_claude("zapamiętaj że lubię sushi", chat_id="553")
        self.assertEqual(decision["action"], "save_fact")
        self.assertEqual(decision["args"]["fact"], "Bartek lubi sushi")

        FakeProc.stdout = "Jasne, ogarniam to."
        with patch.object(ai_council, "cfg", side_effect=fake_cfg), patch.object(
            ai_council, "reserve_operator_call", return_value=(True, "", {"usage_id": "u1"})
        ), patch.object(ai_council, "finalize_operator_call", return_value=None), patch.object(
            ai_council, "recent_conversation", return_value=[]
        ), patch.object(ai_council, "memory_context_for_prompt", return_value=""), patch.object(
            ai_council.subprocess, "run", return_value=FakeProc()
        ):
            decision = ai_council.brain_decide_claude("ogarnij temat", chat_id="553")
        self.assertEqual(decision, {"action": "reply", "text": "Jasne, ogarniam to."})

    def test_brain_reply_converts_order_draft_to_pending_action(self):
        # L4.98: order flow is alive on the LIVE path (brain), not only in legacy poke_chat.
        self.assertIn("ORDER_DRAFT", ai_council.BRAIN_SYSTEM_PROMPT)
        self.assertIn("NIGDY", ai_council.BRAIN_SYSTEM_PROMPT)
        with temp_dir() as tmp:
            root = Path(tmp)
            with patch.object(ai_council, "ACTIONS_FILE", root / "state" / "actions.jsonl"), patch.object(
                ai_council, "LOG_DIR", root / "logs"
            ), patch.object(ai_council, "AUDIT_LOG", root / "logs" / "audit.jsonl"), patch.object(
                ai_council, "ensure_council_dirs", return_value=None
            ), patch.object(
                ai_council,
                "brain_decide",
                return_value={
                    "action": "reply",
                    "text": 'Mam komplet, robię draft.\nORDER_DRAFT: {"service":"Pyszne","items":"pepperoni L"}',
                },
            ):
                (root / "state").mkdir(parents=True)
                (root / "logs").mkdir(parents=True)
                reply = ai_council.brain_loop("zamow mi pizze pepperoni z pyszne", chat_id="553")
                rows = ai_council.read_jsonl(root / "state" / "actions.jsonl")

        self.assertNotIn("ORDER_DRAFT", reply)
        self.assertIn("/approve act-", reply)
        self.assertNotIn("[Council]", reply)
        self.assertEqual(rows[-1]["type"], "order_handoff")
        self.assertEqual(rows[-1]["status"], "pending")

    def test_brain_decide_claude_disabled_for_grok_operator(self):
        def grok_cfg(key, default=""):
            return {"AI_COUNCIL_POKE_CHAT_OPERATOR": "grok"}.get(key, default)

        with patch.object(ai_council, "cfg", side_effect=grok_cfg):
            self.assertIsNone(ai_council.brain_decide_claude("hej tam, co słychać?", chat_id="553"))


class OrderHandoffTests(unittest.TestCase):
    """L4.96: 'zamów pizzę' => Claude collects slots, emits ORDER_DRAFT marker,
    system converts it to a pending R1 action; /approve returns a handoff link.
    No payments, no external writes, no pretending the order was placed."""

    def test_contract_forbids_fake_orders_and_defines_marker(self):
        self.assertIn("ORDER_DRAFT", ai_council.MASTER_HOST_CONTRACT)
        self.assertIn("NIGDY nie twierdzisz", ai_council.MASTER_HOST_CONTRACT)

    def test_extract_order_draft_happy_path_strips_marker(self):
        answer = 'Jasne, robię draft.\nORDER_DRAFT: {"service":"Pyszne","items":"pepperoni L","address":"Dom"}'
        cleaned, payload = ai_council.extract_order_draft(answer)
        self.assertEqual(cleaned, "Jasne, robię draft.")
        self.assertEqual(payload["service"], "Pyszne")
        self.assertEqual(payload["items"], "pepperoni L")

    def test_extract_order_draft_rejects_broken_or_incomplete_json(self):
        cleaned, payload = ai_council.extract_order_draft("Ok.\nORDER_DRAFT: {nie-json}")
        self.assertEqual(cleaned, "Ok.")
        self.assertIsNone(payload)
        cleaned2, payload2 = ai_council.extract_order_draft('Ok.\nORDER_DRAFT: {"service":"","items":"x"}')
        self.assertEqual(cleaned2, "Ok.")
        self.assertIsNone(payload2)
        cleaned3, payload3 = ai_council.extract_order_draft("Zwykła odpowiedź bez markera.")
        self.assertEqual(cleaned3, "Zwykła odpowiedź bez markera.")
        self.assertIsNone(payload3)

    def test_attach_order_draft_creates_pending_action_with_footer(self):
        with temp_dir() as tmp:
            root = Path(tmp)
            with patch.object(ai_council, "ACTIONS_FILE", root / "state" / "actions.jsonl"), patch.object(
                ai_council, "LOG_DIR", root / "logs"
            ), patch.object(ai_council, "AUDIT_LOG", root / "logs" / "audit.jsonl"), patch.object(
                ai_council, "ensure_council_dirs", return_value=None
            ):
                (root / "state").mkdir(parents=True)
                (root / "logs").mkdir(parents=True)
                answer = 'Mam komplet.\nORDER_DRAFT: {"service":"Pyszne","items":"pepperoni L","address":"Dom"}'
                final = ai_council.attach_order_draft_if_any(answer, chat_id="553")
                rows = ai_council.read_jsonl(root / "state" / "actions.jsonl")

        self.assertNotIn("ORDER_DRAFT", final)
        self.assertIn("/approve act-", final)
        self.assertEqual(rows[-1]["type"], "order_handoff")
        self.assertEqual(rows[-1]["status"], "pending")
        self.assertIn("deep_link", rows[-1]["payload"])
        self.assertIn("pyszne", rows[-1]["payload"]["deep_link"].lower())

    def test_approve_order_handoff_returns_link_not_fake_execution(self):
        with temp_dir() as tmp:
            root = Path(tmp)
            with patch.object(ai_council, "ACTIONS_FILE", root / "state" / "actions.jsonl"), patch.object(
                ai_council, "LOG_DIR", root / "logs"
            ), patch.object(ai_council, "AUDIT_LOG", root / "logs" / "audit.jsonl"), patch.object(
                ai_council, "ensure_council_dirs", return_value=None
            ):
                (root / "state").mkdir(parents=True)
                (root / "logs").mkdir(parents=True)
                action = ai_council.create_order_handoff_action(
                    {"service": "Glovo", "items": "pad thai", "address": "Dom"}, chat_id="553"
                )
                response = ai_council.approve_response(action["action_id"])
                rows = ai_council.read_jsonl(root / "state" / "actions.jsonl")

        self.assertIn("nie składam i nie płacę", response)
        self.assertIn("glovo", response.lower())
        self.assertIn("Link:", response)
        self.assertEqual(rows[-1]["status"], "executed")
        self.assertIn("external_write_performed=false", rows[-1]["execution_result"])

    def test_order_deep_link_fallback_is_search(self):
        link = ai_council.order_deep_link({"service": "Pizzeria u Stefana", "items": "capricciosa"})
        self.assertIn("google.com/search", link)

    def test_extract_order_draft_strips_all_markers(self):
        answer = (
            'Ok.\nORDER_DRAFT: {"service":"Pyszne","items":"pepperoni"}\n'
            'ORDER_DRAFT: {"service":"Glovo","items":"sushi"}'
        )
        cleaned, payload = ai_council.extract_order_draft(answer)
        self.assertNotIn("ORDER_DRAFT", cleaned)
        self.assertEqual(payload["service"], "Pyszne")


class WorkspaceActionRollbackTests(unittest.TestCase):
    """L4.95: every approved workspace write is snapshotted and undoable via /undo."""

    def _ctx(self, root):
        return [
            patch.object(ai_council, "WORKSPACES_DIR", root / "workspaces"),
            patch.object(ai_council, "STATE_DIR", root / "state"),
            patch.object(ai_council, "ACTIONS_FILE", root / "state" / "actions.jsonl"),
            patch.object(ai_council, "LOG_DIR", root / "logs"),
            patch.object(ai_council, "AUDIT_LOG", root / "logs" / "audit.jsonl"),
            patch.object(ai_council, "ensure_council_dirs", return_value=None),
            patch.object(ai_council, "memory_save", return_value={}),
        ]

    def test_overwrite_is_undoable(self):
        with temp_dir() as tmp:
            root = Path(tmp)
            ctx = self._ctx(root)
            with contextlib.ExitStack() as stack:
                for c in ctx:
                    stack.enter_context(c)
                (root / "workspaces" / "shared").mkdir(parents=True)
                (root / "state").mkdir(parents=True, exist_ok=True)
                (root / "logs").mkdir(parents=True, exist_ok=True)
                target = root / "workspaces" / "shared" / "notes.txt"
                target.write_text("stara treść", encoding="utf-8")
                action = {"action_id": "a1", "payload": {"path": "notes.txt", "content": "nowa treść"}}
                executed = ai_council.execute_workspace_write_action(action)
                self.assertEqual(executed["status"], "executed")
                self.assertEqual(target.read_text(encoding="utf-8"), "nowa treść")
                result = ai_council.workspace_action_undo("notes.txt")
                self.assertIn("Cofnięto", result)
                self.assertEqual(target.read_text(encoding="utf-8"), "stara treść")

    def test_undo_of_new_file_removes_it(self):
        with temp_dir() as tmp:
            root = Path(tmp)
            with contextlib.ExitStack() as stack:
                for c in self._ctx(root):
                    stack.enter_context(c)
                (root / "workspaces" / "shared").mkdir(parents=True)
                (root / "state").mkdir(parents=True, exist_ok=True)
                (root / "logs").mkdir(parents=True, exist_ok=True)
                target = root / "workspaces" / "shared" / "fresh.txt"
                action = {"action_id": "a2", "payload": {"path": "fresh.txt", "content": "hello"}}
                ai_council.execute_workspace_write_action(action)
                self.assertTrue(target.exists())
                result = ai_council.workspace_action_undo("fresh.txt")
                self.assertIn("Cofnięto", result)
                self.assertFalse(target.exists())

    def test_undo_route_and_no_backup_message(self):
        route = ai_council.route_text("/undo notes.txt")
        self.assertEqual(route["command"], "/undo")
        self.assertEqual(route["prompt"], "notes.txt")
        with temp_dir() as tmp:
            root = Path(tmp)
            with contextlib.ExitStack() as stack:
                for c in self._ctx(root):
                    stack.enter_context(c)
                (root / "workspaces" / "shared").mkdir(parents=True)
                self.assertIn("Brak backupu", ai_council.workspace_action_undo("nieistnieje.txt"))


class RespondB64ThreadMemoryTests(unittest.TestCase):
    """L4.94: the iMessage relay path must persist thread memory like Telegram."""

    def test_respond_b64_reply_persists_turns_and_scrubs_debug(self):
        with temp_dir() as tmp:
            root = Path(tmp)
            with patch.object(ai_council, "CONVERSATIONS_FILE", root / "state" / "conversations.jsonl"), patch.object(
                ai_council, "CLARIFICATIONS_FILE", root / "state" / "clarifications.jsonl"
            ), patch.object(ai_council, "LOG_DIR", root / "logs"), patch.object(
                ai_council, "AUDIT_LOG", root / "logs" / "audit.jsonl"
            ), patch.object(
                ai_council, "cfg", side_effect=lambda key, default="": {"TELEGRAM_ALLOWED_CHAT_ID": "553", "AI_COUNCIL_IMESSAGE_ALLOW_OPEN": "true"}.get(key, default)
            ), patch.object(ai_council, "ensure_council_dirs", return_value=None), patch.object(
                ai_council,
                "build_response",
                return_value='Jasne, gdzie jesteś i jaki budżet?\nroute={"command": "/chat"}\naudit_log=x',
            ):
                (root / "state").mkdir(parents=True, exist_ok=True)
                reply = ai_council.respond_b64_reply("chce jedzenie")
                rows = ai_council.read_jsonl(root / "state" / "conversations.jsonl")

        self.assertEqual(reply, "Jasne, gdzie jesteś i jaki budżet?")
        self.assertNotIn("route=", reply)
        roles = [row["role"] for row in rows]
        self.assertEqual(roles, ["user", "assistant"])
        self.assertIn("chce jedzenie", rows[0]["text"])
        self.assertIn("gdzie jesteś", rows[1]["text"])
        self.assertNotIn("route=", rows[1]["text"])

    def test_respond_b64_reply_runs_auto_fact_capture(self):
        with temp_dir() as tmp:
            root = Path(tmp)
            with patch.object(ai_council, "CONVERSATIONS_FILE", root / "state" / "conversations.jsonl"), patch.object(
                ai_council, "CLARIFICATIONS_FILE", root / "state" / "clarifications.jsonl"
            ), patch.object(
                ai_council, "cfg", side_effect=lambda key, default="": {"TELEGRAM_ALLOWED_CHAT_ID": "553", "AI_COUNCIL_IMESSAGE_ALLOW_OPEN": "true"}.get(key, default)
            ), patch.object(ai_council, "ensure_council_dirs", return_value=None), patch.object(
                ai_council, "build_response", return_value="Zapisane."
            ), patch.object(ai_council, "maybe_auto_extract_facts") as capture:
                (root / "state").mkdir(parents=True, exist_ok=True)
                ai_council.respond_b64_reply("mój lot jest w piątek o 7 rano")

        capture.assert_called_once_with("mój lot jest w piątek o 7 rano", "553")


class DeterministicResearchRouteTests(unittest.TestCase):
    """L4.80: mid-sentence research routes deterministically (no extra Grok call)."""

    def test_mid_sentence_web_research_routes_without_llm(self):
        with patch.object(ai_council, "llm_route") as llm:
            route = ai_council.route_message("ej, sprawdź w internecie co nowego u OpenAI", chat_id="553")
        self.assertEqual(route["command"], "@research")
        self.assertEqual(route["route_source"], "keyword")
        llm.assert_not_called()

    def test_co_pisza_o_routes_to_research_without_llm(self):
        with patch.object(ai_council, "llm_route") as llm:
            route = ai_council.route_message("ciekawi mnie co piszą o nowym Grok 5", chat_id="553")
        self.assertEqual(route["command"], "@research")
        llm.assert_not_called()

    def test_x_marker_routes_to_xresearch(self):
        route = ai_council.deterministic_research_route(
            "zobacz co na twitterze o premierze", "zobacz co na twitterze o premierze"
        )
        self.assertEqual(route["command"], "/xresearch")

    def test_existing_xresearch_prefix_still_wins(self):
        # Regression: the specific startswith /xresearch route must beat the new
        # mid-sentence detector.
        route = ai_council.route_text("deep research x Poke Apple Messages")
        self.assertEqual(route["command"], "/xresearch")

    def test_ambiguous_message_goes_to_brain(self):
        # "sprawdź to szerzej" has no web/research keyword -> the brain owns it (/chat),
        # not the retired llm_route operator path (which used to leak plan-mode/[Council]).
        route = ai_council.route_message("sprawdź to szerzej", chat_id="553")
        self.assertEqual(route["command"], "/chat")
        self.assertEqual(route["route_source"], "fallback")


class CouncilAllVerdictTests(unittest.TestCase):
    """L4.81: @all ends on one verdict, not three parallel answers."""

    def test_front_all_response_renders_verdict_block(self):
        parts = [("Technicznie", "[Codex] x"), ("Plan", "[Claude] y"), ("Research", "[Grok] z")]
        verdict = {
            "decision": "Zrób mały weryfikowalny krok A.",
            "facts": ["fakt jeden", "fakt dwa"],
            "dispute": "Grok vs Codex o kolejność.",
            "next_actions": ["Uruchom test A", "potem B"],
        }
        out = ai_council.front_all_response(parts, task_id="task-1", verdict=verdict)
        self.assertIn("WERDYKT: Zrób mały weryfikowalny krok A.", out)
        self.assertIn("FAKTY:", out)
        self.assertIn("fakt jeden", out)
        self.assertIn("SPÓR:", out)
        self.assertIn("NASTĘPNY KROK: Uruchom test A", out)

    def test_all_command_synthesizes_single_verdict(self):
        with patch.object(ai_council, "codex_response", return_value="[Codex] wykonalne"), patch.object(
            ai_council, "claude_response", return_value="[Claude] plan w 3 krokach"
        ), patch.object(ai_council, "grok_route_response", return_value="[Grok] research: brak blokerów"):
            out = ai_council.build_response({"command": "@all", "prompt": "co zrobić z X", "task_id": "task-9"})

        self.assertIn("Głosy:", out)
        self.assertIn("WERDYKT:", out)
        self.assertIn("NASTĘPNY KROK:", out)



if __name__ == "__main__":
    unittest.main()
