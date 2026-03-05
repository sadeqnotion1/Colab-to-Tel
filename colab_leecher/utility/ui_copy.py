"""Shared user-facing copy and lightweight message formatting helpers."""

from __future__ import annotations

from html import escape
from urllib.parse import unquote, urlparse


SUPPORTED_LINK_SOURCES = "Direct, Magnet, Telegram, Mega, Google Drive, Debrid, Bitso"

_LINK_INPUT_EXAMPLE = (
    "<code>https://example.com/file.ext\n"
    "[name.ext]\n"
    "{zip_password}\n"
    "(unzip_password)</code>"
)


def build_link_prompt(title: str, task_id: str | None = None) -> str:
    """Build a consistent prompt for collecting source links."""
    lines = [
        f"<b>{title}</b>",
        "",
        f"<i>Supported sources: {SUPPORTED_LINK_SOURCES}</i>",
        "",
        _LINK_INPUT_EXAMPLE,
    ]
    if task_id:
        lines.extend(["", f"<i>Task ID: <code>{escape(task_id)}</code></i>"])
    return "\n".join(lines)


def build_upload_destination_prompt() -> str:
    """Build destination selection copy for /gdupload flow."""
    return (
        "<b>Choose Upload Destination</b>\n\n"
        "\u2601\ufe0f <b>Google Drive</b>\n"
        "<i>Upload files to your Drive (requires <code>token.pickle</code>).</i>\n\n"
        "\U0001f4c2 <b>Local Mirror</b>\n"
        "<i>Copy files to <code>/content/Mirrored_Files</code> in this runtime.</i>"
    )


def build_filename_option_prompt(service_name: str) -> str:
    """Build copy for filename extraction/manual selection."""
    safe_service = escape(service_name)
    return (
        f"<b>File Naming for {safe_service}</b>\n\n"
        "Choose how you want to set output filenames."
    )


def build_manual_filenames_prompt(service_name: str, count: int) -> str:
    """Build prompt for manual filename input."""
    safe_service = escape(service_name)
    return (
        f"Reply to this message with <b>{count}</b> filename(s) for <b>{safe_service}</b>, one per line.\n\n"
        "You can also send a raw URL (Gist, Pastebin, Rentry, or .txt) that contains the filenames."
    )


def build_help_text() -> str:
    """Build primary /help response text."""
    return (
        "<b>Available Commands</b>\n\n"
        "<b>Download and Mirror</b>\n"
        "\u2022 <code>/tupload</code> Leech to Telegram\n"
        "\u2022 <code>/gdupload</code> Mirror to Google Drive\n"
        "\u2022 <code>/ytupload</code> Leech YouTube-DL links\n"
        "\u2022 <code>/igupload</code> or <code>/ig</code> Instagram downloader\n"
        "\u2022 <code>/tiktokbulk</code> Bulk TikTok download from Gist\n"
        "\u2022 <code>/drupload</code> Leech from a local folder path\n"
        "\u2022 <code>/mindvalley</code> Download Mindvalley M3U8 content\n"
        "\u2022 <code>/nzb</code> Download from Usenet (.nzb)\n\n"
        "<b>Configuration</b>\n"
        "\u2022 <code>/settings</code>, <code>/setname</code>, <code>/zipaswd</code>, "
        "<code>/unzipaswd</code>, <code>/archivetype</code>\n\n"
        "Use <code>/start</code> to verify the bot is online.\n"
        "Send an image in chat to set the thumbnail."
    )


def summarize_task_name(
    download_name: str | None,
    source_url: str | None,
    *,
    fallback: str = "Task",
    max_length: int = 24,
) -> str:
    """Create a short readable task label from file name/url."""
    candidate = (download_name or "").strip()

    if not candidate and source_url:
        try:
            path = urlparse(source_url).path
            candidate = unquote(path.split("/")[-1]) if path else ""
        except Exception:
            candidate = ""
        if not candidate:
            candidate = source_url.rstrip("/").split("/")[-1]

    if not candidate:
        candidate = fallback

    candidate = " ".join(candidate.replace("\n", " ").split())
    if len(candidate) > max_length:
        return candidate[: max_length - 3].rstrip() + "..."
    return candidate


def build_cancel_task_button_label(
    download_name: str | None,
    source_url: str | None,
    short_id: str,
    *,
    max_name_length: int = 18,
) -> str:
    """Build consistent cancel button text used in task lists."""
    short_name = summarize_task_name(
        download_name,
        source_url,
        fallback=short_id,
        max_length=max_name_length,
    )
    return f"Cancel {short_name} ({short_id})"
