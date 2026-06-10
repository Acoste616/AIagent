"""Shared imports/helpers for the split AI Council test suite (audit 3.3).
Extracted 1:1 from the former tests/test_ai_council.py header. Imports here
are RE-EXPORTED to the split test modules via star import.
"""
# ruff: noqa: F401
import base64
import contextlib
import io
import json
import os
import re
import subprocess
import sys
import tempfile
import threading
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch
from urllib.request import urlopen

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import ai_council


def temp_dir():
    try:
        return tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
    except TypeError:
        return tempfile.TemporaryDirectory()


