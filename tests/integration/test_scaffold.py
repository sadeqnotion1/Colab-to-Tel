from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.integration
def test_credentials_template_has_required_keys():
    template_path = REPO_ROOT / "credentials.json.example"
    assert template_path.exists(), "credentials.json.example must exist"

    with template_path.open("r", encoding="utf-8") as file_handle:
        data = json.load(file_handle)

    required = {"API_ID", "API_HASH", "BOT_TOKEN", "USER_ID", "DUMP_ID"}
    assert required.issubset(set(data.keys()))


@pytest.mark.integration
def test_sensitive_file_policy_passes_for_current_repo_state():
    result = subprocess.run(
        [sys.executable, "scripts/security/block_sensitive_files.py"],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
    )

    assert result.returncode == 0, result.stdout + result.stderr
