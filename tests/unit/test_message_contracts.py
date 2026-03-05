from __future__ import annotations

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]


def _read(relative_path: str) -> str:
    return (REPO_ROOT / relative_path).read_text(encoding="utf-8")


def test_sabnzbd_notification_masks_api_key() -> None:
    source = _read("colab_leecher/__main__.py")
    assert "masked_api_key = mask_secret(api_key)" in source
    assert "<code>{api_key}</code>" not in source


def test_debug_handler_no_plaintext_message_logging_by_default() -> None:
    source = _read("colab_leecher/__main__.py")
    assert "DEBUG_MESSAGE_PREVIEW" in source
    assert "text: {message.text[:50]" not in source


def test_settings_handler_replies_when_unauthorized() -> None:
    source = _read("colab_leecher/__main__.py")
    assert 'await message.reply_text("❌ Unauthorized.")' in source


def test_summary_formatter_escapes_dynamic_html_fields() -> None:
    source = _read("colab_leecher/utility/handler.py")
    assert "display_name = escape_html(" in source
    assert "safe_file_name = escape_html(file_name)" in source
    assert "safe_href(file_link)" in source
