from __future__ import annotations

from colab_leecher.utility.message_safety import (
    escape_html,
    mask_secret,
    safe_href,
    user_error,
)


def test_user_error_returns_generic_message() -> None:
    assert user_error("start the task") == "❌ Couldn't start the task. Please try again."
    assert user_error("") == "❌ Couldn't process your request. Please try again."


def test_mask_secret_hides_sensitive_values() -> None:
    assert mask_secret("1234567890") == "1234...7890"
    assert mask_secret("abcd") == "****"
    assert mask_secret("") == "Not available"


def test_escape_html_escapes_dynamic_content() -> None:
    assert escape_html("<bad 'input'>") == "&lt;bad &#x27;input&#x27;&gt;"


def test_safe_href_allows_expected_schemes() -> None:
    assert safe_href("https://example.com/path") == "https://example.com/path"
    assert safe_href("http://example.com/path") == "http://example.com/path"
    assert safe_href("tg://resolve?domain=test") == "tg://resolve?domain=test"
    assert safe_href("javascript:alert(1)") is None
    assert safe_href("file:///tmp/test.txt") is None
