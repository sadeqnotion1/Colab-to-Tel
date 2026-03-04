from __future__ import annotations

import builtins
import importlib
import io
import json
import sys
from pathlib import Path


def _import_colab_leecher_with_open(monkeypatch, fake_open):
    original_open = builtins.open

    def wrapped_open(path, *args, **kwargs):
        return fake_open(original_open, path, *args, **kwargs)

    monkeypatch.setattr(builtins, "open", wrapped_open)
    sys.modules.pop("colab_leecher", None)
    return importlib.import_module("colab_leecher")


def test_missing_credentials_does_not_hard_exit(monkeypatch):
    def fake_open(_original_open, path, *args, **kwargs):
        if str(path).endswith("credentials.json"):
            raise FileNotFoundError("simulated missing credentials")
        return _original_open(path, *args, **kwargs)

    module = _import_colab_leecher_with_open(monkeypatch, fake_open)

    assert module.is_runtime_configured() is False
    try:
        module.ensure_runtime_config()
        assert False, "ensure_runtime_config must raise ConfigError when credentials are missing"
    except module.ConfigError:
        pass


def test_valid_credentials_load_runtime_fields(monkeypatch):
    fake_credentials = {
        "API_ID": 12345,
        "API_HASH": "hash",
        "BOT_TOKEN": "token",
        "USER_ID": 999,
        "DUMP_ID": -1001234567890,
    }
    payload = json.dumps(fake_credentials)
    credentials_path = Path("credentials.json")

    def fake_open(original_open, path, *args, **kwargs):
        if Path(path).name == credentials_path.name:
            return io.StringIO(payload)
        return original_open(path, *args, **kwargs)

    module = _import_colab_leecher_with_open(monkeypatch, fake_open)

    assert module.is_runtime_configured() is True
    assert module.API_ID == 12345
    assert module.OWNER == 999
    assert module.DUMP_ID == -1001234567890
