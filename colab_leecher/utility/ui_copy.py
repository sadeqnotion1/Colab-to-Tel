"""Shared user-facing copy and lightweight message formatting helpers."""

from __future__ import annotations

from html import escape
from urllib.parse import unquote, urlparse


SUPPORTED_LINK_SOURCES = "Direct, Magnet, Telegram, Mega, Google Drive, Debrid, NZB, Bitso"

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


def build_start_welcome_text() -> str:
    """Build the /start greeting copy."""
    return (
        "<b>Colab Leecher</b>\n\n"
        "Use <code>/help</code> to see available commands.\n"
        "Use <code>/tupload</code>, <code>/gdupload</code>, or <code>/drupload</code> to start a task."
    )


def build_cannot_start_task_message(reason: str) -> str:
    """Build a consistent task-limit rejection message."""
    return (
        "<b>Cannot Start Task</b>\n\n"
        f"{escape(reason)}\n\n"
        "Use <code>/tasks</code> to view active tasks."
    )


def build_pending_task_warning(short_id: str) -> str:
    """Build warning shown when user already has a pending setup task."""
    safe_id = escape(short_id)
    return (
        f"<b>Pending Task Exists</b> (<code>{safe_id}</code>)\n"
        "Send your links, or use <code>/cancel</code> to start over."
    )


def build_directory_path_prompt(task_id: str) -> str:
    """Build prompt for /drupload directory path input."""
    safe_task_id = escape(task_id)
    return (
        "<b>Dir Leech</b> Send folder path\n\n"
        "Send the full path to your directory:\n\n"
        "<code>/path/to/folder</code>\n\n"
        f"<i>Task ID: <code>{safe_task_id}</code></i>"
    )


def build_tiktok_bulk_gist_prompt(task_id: str) -> str:
    """Build prompt for /tiktokbulk gist input."""
    safe_task_id = escape(task_id)
    return (
        "<b>TikTok Bulk Download</b> Send a GitHub Gist URL\n\n"
        "<b>Format:</b>\n"
        "• Create a GitHub Gist with TikTok URLs (one per line)\n"
        "• Send the <b>RAW</b> Gist URL here\n\n"
        "<b>Example:</b>\n"
        "<code>https://gist.githubusercontent.com/username/abc123/raw/links.txt</code>\n\n"
        f"<i>Task ID: <code>{safe_task_id}</code></i>"
    )


def build_ytdl_prompt() -> str:
    """Build /ytdl prompt text."""
    return (
        "<b>YTDL Leech</b> Send link(s)\n\n"
        "<code>https://link1.mp4</code>"
    )


def build_instagram_prompt() -> str:
    """Build /ig prompt text."""
    return (
        "<b>Instagram Leech</b> Send link(s)\n\n"
        "<b>Supported:</b>\n"
        "• Individual posts, reels, and IGTV\n"
        "• Entire profiles (batch download)\n\n"
        "<b>Examples:</b>\n"
        "<code>https://instagram.com/username/</code> (all posts)\n"
        "<code>https://instagram.com/p/xyz</code> (single post)\n"
        "<code>https://instagram.com/reel/abc</code> (reel)"
    )


def build_nzbcloud_prompt() -> str:
    """Build /nzbcloud prompt text."""
    return (
        "<b>NZBcloud Leech</b> Send a Gist/Pastebin URL\n\n"
        "<b>Required Format:</b>\n"
        "<code>TITLE=filename.mkv\nhttps://files.nzbcloud.com/.../play?token=...</code>\n\n"
        "<b>Browser Extension:</b>\n"
        "• Click \"Create Gist\" (auto-copies to clipboard)\n"
        "• Paste the gist URL here\n\n"
        "<b>Supported Sources:</b>\n"
        "• GitHub Gist raw URLs\n"
        "• Pastebin raw URLs\n"
        "• Rentry raw URLs"
    )


def build_extract_archive_prompt() -> str:
    """Build /extract prompt text."""
    return (
        "<b>Extract Archive</b>\n\n"
        "Send the archive path and optional file filter:\n\n"
        "<b>Examples:</b>\n"
        "<code>/content/drive/MyDrive/file.part01.rar</code>\n"
        "<code>/content/drive/MyDrive/file.rar .mkv</code>\n"
        "<code>/content/drive/MyDrive/file.zip .mkv,.mp4</code>\n\n"
        "<b>Format:</b>\n"
        "<code>&lt;path&gt;</code> or <code>&lt;path&gt; &lt;filter&gt;</code>\n\n"
        "Cancel with <code>/cancel</code>"
    )


def build_mindvalley_prompt() -> str:
    """Build /mindvalley prompt text."""
    return (
        "<b>Mindvalley Course Downloader</b>\n\n"
        "<b>Send your M3U8 URLs</b> (choose one option):\n\n"
        "<b>Option 1:</b> Full download (video + audio + subtitle)\n"
        "<code>TITLE=My Lesson Name</code> (optional - custom filename)\n"
        "<code>https://...video.m3u8</code>\n"
        "<code>https://...audio.m3u8</code> (optional)\n"
        "<code>https://...subtitle.webvtt.m3u8</code> (optional)\n\n"
        "<b>Option 2:</b> Subtitle-only download\n"
        "Send a subtitle URL (contains <code>subtitle</code> or <code>webvtt</code>)\n"
        "<code>TITLE=My Subtitle Name</code> (optional)\n"
        "<code>https://...subtitle.webvtt.m3u8</code>\n"
        "Or use <code>DOWNLOAD_TYPE=subtitle-only</code>\n\n"
        "<b>Option 3:</b> Raw gist URL (with TITLE= first line)\n"
        "<code>https://gist.githubusercontent.com/...</code>\n\n"
        "<i>Tip: Use browser extension to auto-copy with title.</i>\n"
        "<i>Tip: Put long URLs in a gist to avoid character limits.</i>\n"
        "<i>Note: Subtitles are uploaded as SRT and VTT.</i>"
    )


def build_nzb_prompt(active_provider: str | None) -> str:
    """Build /nzb prompt text."""
    provider = escape(active_provider or "Not configured")
    return (
        "<b>NZB Usenet Downloader</b>\n\n"
        "<b>Upload your .nzb file</b> or <b>send NZB URL</b>\n\n"
        "<b>Requirements:</b>\n"
        "• Valid Usenet account configured in <code>credentials.json</code>\n"
        "• NZB file with valid article IDs\n\n"
        "<i>Tip: Supports multi-part RAR archives.</i>\n"
        "<i>Note: Missing articles are skipped.</i>\n\n"
        f"<b>Active Provider:</b> <code>{provider}</code>"
    )


def build_raw_gist_warning() -> str:
    """Build warning for non-raw gist URLs."""
    return (
        "Please use the <b>RAW</b> gist URL. "
        "Click the <b>Raw</b> button on the gist page."
    )


def build_usenet_not_configured_error() -> str:
    """Build NZB provider-missing error text."""
    return (
        "<b>Usenet Not Configured</b>\n\n"
        "Add to <code>credentials.json</code>:\n"
        "<pre><code>{\n"
        "  \"NZB_PROVIDERS\": {\n"
        "    \"provider_name\": {\n"
        "      \"host\": \"news.server.com\",\n"
        "      \"port\": 563,\n"
        "      \"username\": \"user\",\n"
        "      \"password\": \"pass\",\n"
        "      \"ssl\": true,\n"
        "      \"connections\": 8\n"
        "    }\n"
        "  },\n"
        "  \"NZB_DEFAULT_PROVIDER\": \"provider_name\"\n"
        "}\n"
        "</code></pre>"
    )


def build_invalid_provider_configuration_error(provider_name: str) -> str:
    """Build invalid active NZB provider configuration error text."""
    safe_provider = escape(provider_name)
    return (
        "<b>Invalid Provider Configuration</b>\n\n"
        f"Active provider <code>{safe_provider}</code> is missing required fields.\n"
        "Check your <code>credentials.json</code> file."
    )


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


def build_task_in_progress_notice() -> str:
    """Build consistent copy when task_starter is called while busy."""
    return "A task is already in progress. Please wait or use /cancel."


def build_settings_text(
    *,
    stream_upload: str,
    split_video: str,
    convert_video: str,
    caption: str,
    has_prefix: bool,
    has_suffix: bool,
    has_thumbnail: bool,
    has_nzb_cf_cookie: bool,
    has_bitso_identity_cookie: bool,
    has_bitso_session_cookie: bool,
) -> str:
    """Build settings panel text with consistent HTML formatting."""
    prefix_value = "Set" if has_prefix else "Not set"
    suffix_value = "Set" if has_suffix else "Not set"
    thumbnail_value = "Set" if has_thumbnail else "Not set"
    nzb_cf_value = "Set" if has_nzb_cf_cookie else "Not set"
    bitso_identity_value = "Set" if has_bitso_identity_cookie else "Not set"
    bitso_session_value = "Set" if has_bitso_session_cookie else "Not set"

    return (
        "<b>Settings</b>\n\n"
        f"<b>Upload:</b> <i>{escape(stream_upload)}</i>\n"
        f"<b>Split:</b> <i>{escape(split_video)}</i>\n"
        f"<b>Convert:</b> <i>{escape(convert_video)}</i>\n"
        f"<b>Caption:</b> <i>{escape(caption)}</i>\n"
        f"<b>Prefix:</b> <i>{prefix_value}</i>\n"
        f"<b>Suffix:</b> <i>{suffix_value}</i>\n"
        f"<b>Thumbnail:</b> <i>{thumbnail_value}</i>\n\n"
        "<b>Cookies</b>\n"
        f"NZB CF: <i>{nzb_cf_value}</i>\n"
        f"Bitso ID: <i>{bitso_identity_value}</i>\n"
        f"Bitso Sess: <i>{bitso_session_value}</i>"
    )


def build_health_summary_text(
    *,
    is_shutting_down: bool,
    uptime_text: str,
    active_tasks: int,
    max_total_tasks: int,
    background_tasks: int,
    success_rate_text: str,
    avg_task_time_text: str,
    total_down_text: str,
    total_up_text: str,
) -> str:
    """Build queue health report using consistent HTML formatting."""
    status_text = "Shutting down" if is_shutting_down else "Healthy"
    return (
        "<b>System Health Report</b>\n"
        f"<b>Status:</b> {status_text}\n"
        f"<b>Uptime:</b> <code>{escape(uptime_text)}</code>\n"
        f"<b>Active Tasks:</b> <code>{active_tasks}</code> / <code>{max_total_tasks}</code>\n"
        f"<b>Background Tasks:</b> <code>{background_tasks}</code>\n"
        f"<b>Success Rate:</b> <code>{escape(success_rate_text)}</code>\n"
        f"<b>Avg Task Time:</b> <code>{escape(avg_task_time_text)}</code>\n"
        f"<b>Total Down:</b> <code>{escape(total_down_text)}</code>\n"
        f"<b>Total Up:</b> <code>{escape(total_up_text)}</code>"
    )


def build_archiver_progress_text(
    status_head: str,
    *,
    bar: str,
    percentage: float,
    speed_text: str = "N/A",
    eta_text: str = "N/A",
    elapsed_time_text: str,
    source_size_text: str,
) -> str:
    """Build HTML progress text for archive creation updates using Modern UI."""
    return (
        f"{status_head}\n\n"
        f"<b>┌「{bar}」 » {percentage:.1f}%</b>\n"
        f"<b>├⚡️ Speed »</b> <code>{escape(speed_text)}</code>\n"
        f"<b>├⏳ ETA »</b> <code>{escape(eta_text)}</code>\n"
        f"<b>├⏱️ Elapsed »</b> <code>{escape(elapsed_time_text)}</code>\n"
        f"<b>└📦 Source »</b> <code>{escape(source_size_text)}</code>"
    )


def build_archiver_verification_text(
    status_head: str,
    *,
    title: str,
    file_name: str,
    file_size_text: str,
    status_text: str,
) -> str:
    """Build HTML verification text for archive integrity updates."""
    return (
        f"{status_head}\n"
        f"<b>{escape(title)}</b>\n"
        f"<b>File:</b> <code>{escape(file_name)}</code>\n"
        f"<b>Size:</b> <code>{escape(file_size_text)}</code>\n"
        f"<b>Status:</b> {escape(status_text)}"
    )


def build_converter_progress_text(
    *,
    bar: str,
    attempt: str,
    engine: str,
    handler_name: str,
    elapsed_time_text: str,
) -> str:
    """Build HTML conversion progress block for ffmpeg conversion loop."""
    return (
        f"┌ {bar}\n"
        "<b>Status:</b> Converting\n"
        f"<b>Attempt:</b> <code>{escape(str(attempt))}</code>\n"
        f"<b>Engine:</b> <code>{escape(engine)}</code>\n"
        f"<b>Handler:</b> <code>{escape(handler_name)}</code>\n"
        f"<b>Time Spent:</b> <code>{escape(elapsed_time_text)}</code>"
    )
