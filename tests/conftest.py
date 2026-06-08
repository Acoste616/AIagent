"""Pytest session isolation for the AI Council test suite.

PROBLEM THIS FIXES (L4.63 follow-up):
``ai_council.py`` freezes its runtime paths at import time::

    STATE_DIR = Path(os.environ.get("AI_COUNCIL_STATE_DIR", PROJECT_DIR / "state"))
    COSTS_FILE = STATE_DIR / "costs.jsonl"   # the real cost ledger
    ...

The intent router (``llm_route`` -> ``reserve_operator_call`` ->
``record_operator_usage`` -> ``append_jsonl(COSTS_FILE, ...)``) therefore writes
to whatever ``STATE_DIR`` resolved to *when the module was imported*. Running the
test suite from the production checkout (e.g. ``D:\\ai-council``) would append
fake ``llm_router`` rows straight into the live ``state/costs.jsonl`` and trip the
budget guards. L4.63 broadened the router cost gate, so far more test messages now
reach that path -- making the leak worse.

FIX:
Redirect the writable runtime directories to a throwaway per-session sandbox
*before* ``ai_council`` is imported. pytest imports every ``conftest.py`` in scope
before it imports the test modules, so setting the env vars here is sufficient --
``ai_council``'s module-level constants pick up the sandbox.

We only override a variable the host has NOT already set, so a deliberate host
override (or an env set by an outer harness) still wins. ``PROJECT_DIR`` is left
untouched so read-only assets (``recipes/``, ``scripts/``) still resolve to the
real repo.
"""

import os
import tempfile
from pathlib import Path

# One throwaway sandbox for the whole test session (auto-cleaned by the OS temp dir).
_SANDBOX = Path(tempfile.mkdtemp(prefix="ai-council-tests-"))

# Map: env var -> subdir under the sandbox. STATE_DIR carries the cost ledger,
# control state, actions, jobs, etc.; the rest are other writable runtime dirs so
# the whole suite is hermetic and safe to run from the production directory.
_REDIRECT = {
    "AI_COUNCIL_STATE_DIR": "state",
    "AI_COUNCIL_LOG_DIR": "logs",
    "AI_COUNCIL_ERRORS_DIR": "errors",
    "AI_COUNCIL_ARTIFACTS_DIR": "artifacts",
    "AI_COUNCIL_REPORTS_DIR": "reports",
    "AI_COUNCIL_WORKSPACES_DIR": "workspaces",
}

for _var, _subdir in _REDIRECT.items():
    if os.environ.get(_var):
        continue  # host override wins
    _target = _SANDBOX / _subdir
    _target.mkdir(parents=True, exist_ok=True)
    os.environ[_var] = str(_target)

# Feature flags + secrets are forced OFF/empty for the suite so "off by default"
# tests are deterministic regardless of the production host's .env (load_env lets
# os.environ override the .env for AI_COUNCIL_*/GITHUB_*/GOOGLE_* keys). Tests that
# need a flag ON enable it locally via patch (cfg / patch.dict(os.environ)), so this
# only neutralizes ambient host state. Also prevents tests from using real tokens.
for _flag in (
    "AI_COUNCIL_PROACTIVE_BRIEF", "AI_COUNCIL_FACT_EXTRACTION", "AI_COUNCIL_FACT_AUTO_EXTRACT",
    "AI_COUNCIL_LOCAL_HANDS", "AI_COUNCIL_LOCAL_HANDS_WRITE", "AI_COUNCIL_LLM_ROUTER",
    "AI_COUNCIL_PROVIDER_WRITE_ENABLED", "AI_COUNCIL_GITHUB_ISSUE_WRITE_ENABLED",
    "AI_COUNCIL_IMESSAGE_ENABLED", "AI_COUNCIL_MAIL_ENABLED", "AI_COUNCIL_GROK_RESEARCH_MEMORY",
    "AI_COUNCIL_IMESSAGE_PROACTIVE",
):
    os.environ[_flag] = "false"
for _secret in ("GITHUB_TOKEN", "GH_TOKEN", "GOOGLE_CLIENT_ID", "GOOGLE_CLIENT_SECRET", "GOOGLE_REFRESH_TOKEN"):
    os.environ.pop(_secret, None)
    os.environ[_secret] = ""
