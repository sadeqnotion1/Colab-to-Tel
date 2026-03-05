from __future__ import annotations

from html import escape
from urllib.parse import urlparse


def user_error(action: str = "process your request") -> str:
    """Return a generic user-facing error message without internal details."""
    action_text = action.strip() if action and action.strip() else "process your request"
    return f"❌ Couldn't {action_text}. Please try again."


def mask_secret(secret: str, reveal_prefix: int = 4, reveal_suffix: int = 4) -> str:
    """Mask secrets before displaying them in chats or logs."""
    if not secret:
        return "Not available"

    value = str(secret).strip()
    if not value:
        return "Not available"

    visible = max(0, reveal_prefix) + max(0, reveal_suffix)
    if len(value) <= visible:
        return "*" * len(value)
    return f"{value[:reveal_prefix]}...{value[-reveal_suffix:]}"


def escape_html(value: object) -> str:
    """Escape dynamic text for HTML parse mode messages."""
    return escape(str(value if value is not None else ""), quote=True)


def safe_href(url: str) -> str | None:
    """Allow only safe URL schemes for HTML anchor tags."""
    if not isinstance(url, str):
        return None

    value = url.strip()
    if not value:
        return None

    parsed = urlparse(value)
    if parsed.scheme not in {"http", "https", "tg"}:
        return None
    if parsed.scheme in {"http", "https"} and not parsed.netloc:
        return None
    if parsed.scheme == "tg" and not (parsed.path or parsed.netloc):
        return None
    return value
