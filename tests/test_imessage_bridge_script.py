"""L4.103 smoke tests for the standalone Mac iMessage bridge (audit 1.2 / 0.4).

The bridge runs as its own Mac process and was previously untested. These tests
import it by path (it imports nothing from the repo) and lock down the command
construction that crosses into the host PowerShell — the injection surface.
"""

import importlib.util
import unittest
from pathlib import Path

_BRIDGE_PATH = Path(__file__).resolve().parent.parent / "scripts" / "mac_imessage_bridge_standalone.py"


def _load_bridge():
    spec = importlib.util.spec_from_file_location("mac_bridge_under_test", _BRIDGE_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class BridgeImportTests(unittest.TestCase):
    def test_module_imports(self):
        mod = _load_bridge()
        self.assertTrue(hasattr(mod, "main"))
        self.assertTrue(hasattr(mod, "ack"))


class BridgeSanitizationTests(unittest.TestCase):
    def setUp(self):
        self.mod = _load_bridge()

    def test_safe_msg_id_accepts_ids_and_rejects_injection(self):
        self.assertEqual(self.mod._safe_msg_id("out-20260610-abc_123"), "out-20260610-abc_123")
        self.assertEqual(self.mod._safe_msg_id('"; Start-Process calc'), "")
        self.assertEqual(self.mod._safe_msg_id("$(rm -rf /)"), "")
        self.assertEqual(self.mod._safe_msg_id(""), "")
        self.assertEqual(self.mod._safe_msg_id("a" * 65), "")

    def test_safe_status_only_terminal_values(self):
        self.assertEqual(self.mod._safe_status("sent"), "sent")
        self.assertEqual(self.mod._safe_status("failed"), "failed")
        self.assertEqual(self.mod._safe_status("; evil"), "")

    def test_safe_host_token_blocks_metacharacters(self):
        self.assertEqual(self.mod._safe_host_token("D:\\ai-council", "DEF"), "D:\\ai-council")
        self.assertEqual(self.mod._safe_host_token('D:\\x"; calc', "DEF"), "DEF")
        self.assertEqual(self.mod._safe_host_token("", "DEF"), "DEF")

    def test_ack_refuses_unsafe_id(self):
        calls = []
        orig = self.mod.subprocess.run
        self.mod.subprocess.run = lambda *a, **k: calls.append(a) or None
        try:
            self.mod.ack('"; calc', "sent")
            self.mod.ack("good-id", "bogus-status")
        finally:
            self.mod.subprocess.run = orig
        self.assertEqual(calls, [])  # neither unsafe id nor unsafe status executed

    def test_ack_runs_for_safe_values(self):
        captured = {}

        def fake_run(cmd, *a, **k):
            captured["cmd"] = cmd
            class R:  # noqa: N801
                returncode = 0
                stdout = ""
                stderr = ""
            return R()

        orig = self.mod.subprocess.run
        self.mod.subprocess.run = fake_run
        try:
            self.mod.ack("good-id_1", "sent")
        finally:
            self.mod.subprocess.run = orig
        joined = " ".join(captured["cmd"])
        self.assertIn("imessage-outbox-ack --id good-id_1 --status sent", joined)

    def test_host_cmd_shape(self):
        cmd = self.mod._host_cmd("respond-b64 --b64 AAA")
        self.assertEqual(cmd[0], "ssh")
        self.assertIn("powershell", cmd[-1])
        self.assertIn("respond-b64 --b64 AAA", cmd[-1])


if __name__ == "__main__":
    unittest.main()
