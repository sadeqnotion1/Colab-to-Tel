"""
Enhanced Telegram Bot UI Components
Provides modern, beautiful message templates and formatting utilities
"""

from typing import Optional, List, Dict, Any
from datetime import datetime


class Emoji:
    """Emoji constants for consistent usage"""
    # Status
    SUCCESS = "✅"
    ERROR = "❌"
    WARNING = "⚠️"
    INFO = "ℹ️"
    LOADING = "⏳"

    # Actions
    DOWNLOAD = "📥"
    UPLOAD = "📤"
    PROCESS = "⚙️"
    EXTRACT = "📂"
    COMPRESS = "🗜️"

    # File types
    VIDEO = "🎥"
    AUDIO = "🎵"
    DOCUMENT = "📄"
    PHOTO = "🖼️"
    ARCHIVE = "📦"
    FOLDER = "📁"

    # Progress
    SPEED = "⚡"
    TIME = "⏱️"
    ETA = "⏳"
    SIZE = "💾"

    # UI
    ARROW_RIGHT = "▶️"
    ARROW_LEFT = "◀️"
    BULLET = "•"
    DASH = "—"
    CHECK = "✓"
    CROSS = "✗"

    # Misc
    FIRE = "🔥"
    ROCKET = "🚀"
    STAR = "⭐"
    SPARKLE = "✨"
    LINK = "🔗"
    TAG = "🏷️"
    BRAIN = "🧠"


class Box:
    """Box drawing characters for beautiful layouts"""
    # Single line
    TOP_LEFT = "╭"
    TOP_RIGHT = "╮"
    BOTTOM_LEFT = "╰"
    BOTTOM_RIGHT = "╯"
    HORIZONTAL = "─"
    VERTICAL = "│"
    MIDDLE_LEFT = "├"
    MIDDLE_RIGHT = "┤"

    # Double line
    D_TOP_LEFT = "╔"
    D_TOP_RIGHT = "╗"
    D_BOTTOM_LEFT = "╚"
    D_BOTTOM_RIGHT = "╝"
    D_HORIZONTAL = "═"
    D_VERTICAL = "║"

    # Heavy
    H_HORIZONTAL = "━"
    H_VERTICAL = "┃"


class ProgressBar:
    """Enhanced progress bar generator"""

    @staticmethod
    def generate(percentage: float, length: int = 12, style: str = "blocks") -> str:
        """
        Generate a progress bar

        Args:
            percentage: Completion percentage (0-100)
            length: Bar length in characters
            style: bar style - 'blocks', 'circles', 'squares', 'dots', 'arrows'

        Returns:
            Formatted progress bar string
        """
        percentage = max(0, min(100, percentage))
        filled = int((percentage / 100) * length)

        styles = {
            'blocks': ('█', '░'),
            'circles': ('●', '○'),
            'squares': ('■', '□'),
            'dots': ('⬤', '◯'),
            'arrows': ('▰', '▱'),
            'gradient': ('█', '▓', '▒', '░'),  # For smooth gradients
        }

        if style == 'gradient' and length >= 4:
            # Smooth gradient effect
            chars = styles['gradient']
            full_blocks = filled
            partial = int(((percentage / 100) * length - filled) * len(chars))

            bar = chars[0] * full_blocks
            if partial > 0 and filled < length:
                bar += chars[partial]
                bar += chars[-1] * (length - filled - 1)
            else:
                bar += chars[-1] * (length - filled)
            return bar

        filled_char, empty_char = styles.get(style, styles['blocks'])
        return filled_char * filled + empty_char * (length - filled)

    @staticmethod
    def with_percentage(percentage: float, length: int = 12, style: str = "blocks") -> str:
        """Generate progress bar with percentage"""
        bar = ProgressBar.generate(percentage, length, style)
        return f"[{bar}] {percentage:.1f}%"

    @staticmethod
    def custom(percentage: float, prefix: str = "", suffix: str = "",
               length: int = 12, style: str = "blocks") -> str:
        """Generate custom progress bar with prefix/suffix"""
        bar = ProgressBar.generate(percentage, length, style)
        return f"{prefix}[{bar}]{suffix}".strip()


class MessageTemplate:
    """Pre-built message templates for common scenarios"""

    @staticmethod
    def header(title: str, emoji: str = "") -> str:
        """Create a bold header"""
        return f"<b>{emoji} {title}</b>\n" if emoji else f"<b>{title}</b>\n"

    @staticmethod
    def field(label: str, value: str, emoji: str = "", use_code: bool = False) -> str:
        """Create a labeled field"""
        emoji_str = f"{emoji} " if emoji else ""
        value_formatted = f"<code>{value}</code>" if use_code else value
        return f"{emoji_str}<b>{label}:</b> {value_formatted}"

    @staticmethod
    def divider(char: str = "─", length: int = 25) -> str:
        """Create a divider line"""
        return char * length

    @staticmethod
    def box_list(items: List[tuple], title: str = None) -> str:
        """
        Create a boxed list

        Args:
            items: List of (emoji, label, value) tuples
            title: Optional title for the box

        Returns:
            Formatted box string
        """
        lines = []

        if title:
            lines.append(f"<b>{title}</b>")

        for i, item in enumerate(items):
            if len(item) == 2:
                emoji, value = item
                label = ""
            else:
                emoji, label, value = item

            if i == 0:
                prefix = Box.TOP_LEFT
            elif i == len(items) - 1:
                prefix = Box.BOTTOM_LEFT
            else:
                prefix = Box.MIDDLE_LEFT

            label_str = f"<b>{label}:</b> " if label else ""
            lines.append(f"{prefix}{emoji} {label_str}{value}")

        return "\n".join(lines)

    @staticmethod
    def card(title: str, items: Dict[str, Any], emoji_map: Dict[str, str] = None) -> str:
        """
        Create a card-style message

        Args:
            title: Card title
            items: Dict of label: value pairs
            emoji_map: Optional dict mapping labels to emojis
        """
        emoji_map = emoji_map or {}
        lines = [f"<b>{Emoji.SPARKLE} {title}</b>\n"]

        for i, (label, value) in enumerate(items.items()):
            emoji = emoji_map.get(label, Emoji.BULLET)

            if i == 0:
                prefix = Box.TOP_LEFT
            elif i == len(items) - 1:
                prefix = Box.BOTTOM_LEFT
            else:
                prefix = Box.MIDDLE_LEFT

            lines.append(f"{prefix}{emoji} <b>{label}:</b> {value}")

        return "\n".join(lines)

    @staticmethod
    def status_message(
        title: str,
        status: str,
        progress: float = None,
        details: Dict[str, str] = None,
        show_progress_bar: bool = True
    ) -> str:
        """
        Create a comprehensive status message

        Args:
            title: Main title
            status: Current status text
            progress: Progress percentage (0-100)
            details: Additional details dict
            show_progress_bar: Whether to show progress bar
        """
        lines = [f"<b>{Emoji.ROCKET} {title}</b>\n"]

        # Status line
        lines.append(f"{Box.TOP_LEFT}{Emoji.INFO} <b>Status:</b> <i>{status}</i>")

        # Progress bar
        if progress is not None and show_progress_bar:
            bar = ProgressBar.generate(progress, 12, 'blocks')
            lines.append(f"{Box.MIDDLE_LEFT}「{bar}」 <b>{progress:.1f}%</b>")

        # Details
        if details:
            detail_items = list(details.items())
            for i, (key, value) in enumerate(detail_items):
                is_last = (i == len(detail_items) - 1)
                prefix = Box.BOTTOM_LEFT if is_last else Box.MIDDLE_LEFT
                lines.append(f"{prefix}{Emoji.BULLET} <b>{key}:</b> {value}")

        return "\n".join(lines)

    @staticmethod
    def error_message(
        title: str,
        error: str,
        details: str = None,
        solution: str = None
    ) -> str:
        """Create a formatted error message"""
        lines = [f"<b>{Emoji.ERROR} {title}</b>\n"]

        lines.append(f"{Box.TOP_LEFT}{Emoji.WARNING} <b>Error:</b> <code>{error}</code>")

        if details:
            lines.append(f"{Box.MIDDLE_LEFT}{Emoji.INFO} <b>Details:</b> {details}")

        if solution:
            lines.append(f"{Box.BOTTOM_LEFT}{Emoji.BRAIN} <b>Solution:</b> <i>{solution}</i>")
        else:
            # Update the last line to use BOTTOM_LEFT
            if len(lines) > 1:
                lines[-1] = lines[-1].replace(Box.MIDDLE_LEFT, Box.BOTTOM_LEFT, 1)

        return "\n".join(lines)

    @staticmethod
    def success_message(
        title: str,
        summary: Dict[str, str],
        files: List[str] = None,
        show_hashtag: bool = True
    ) -> str:
        """Create a success/completion message"""
        lines = []

        if show_hashtag:
            hashtag = title.upper().replace(" ", "_")
            lines.append(f"#{hashtag} {Emoji.FIRE}\n")

        lines.append(f"<b>{Emoji.SUCCESS} {title}</b>\n")

        # Summary items
        summary_items = list(summary.items())
        for i, (key, value) in enumerate(summary_items):
            if i == 0:
                prefix = Box.TOP_LEFT
            elif files or i < len(summary_items) - 1:
                prefix = Box.MIDDLE_LEFT
            else:
                prefix = Box.BOTTOM_LEFT

            lines.append(f"{prefix}{Emoji.BULLET} <b>{key}:</b> {value}")

        # Files list
        if files:
            lines.append(f"{Box.MIDDLE_LEFT}{Emoji.FILE} <b>Files:</b>")
            for i, file in enumerate(files):
                is_last = (i == len(files) - 1)
                prefix = Box.BOTTOM_LEFT if is_last else Box.MIDDLE_LEFT
                lines.append(f"{prefix}  {Emoji.ARROW_RIGHT} <code>{file}</code>")

        return "\n".join(lines)

    @staticmethod
    def menu_header(title: str, description: str = None, emoji: str = Emoji.ROCKET) -> str:
        """Create a menu header"""
        lines = [f"<b>{emoji} {title}</b>"]

        if description:
            lines.append(f"\n<i>{description}</i>")

        lines.append("")  # Empty line
        return "\n".join(lines)

    @staticmethod
    def option_list(options: List[tuple], numbered: bool = True) -> str:
        """
        Create a numbered/bulleted option list

        Args:
            options: List of (title, description) tuples
            numbered: Use numbers instead of bullets
        """
        lines = []

        for i, (title, description) in enumerate(options, 1):
            prefix = f"<b>{i}.</b>" if numbered else f"{Emoji.BULLET}"
            lines.append(f"{prefix} <b>{title}</b>")
            if description:
                lines.append(f"   <i>{description}</i>")
            lines.append("")  # Empty line between options

        return "\n".join(lines)


class TimeFormatter:
    """Format time durations"""

    @staticmethod
    def format_seconds(seconds: float) -> str:
        """Format seconds into human readable format"""
        if seconds < 60:
            return f"{int(seconds)}s"
        elif seconds < 3600:
            minutes = int(seconds // 60)
            secs = int(seconds % 60)
            return f"{minutes}m {secs}s"
        else:
            hours = int(seconds // 3600)
            minutes = int((seconds % 3600) // 60)
            return f"{hours}h {minutes}m"

    @staticmethod
    def format_eta(seconds: float) -> str:
        """Format ETA with special handling"""
        if seconds < 0 or seconds > 86400 * 7:  # More than a week
            return "Calculating..."
        return TimeFormatter.format_seconds(seconds)


class SizeFormatter:
    """Format file sizes"""

    @staticmethod
    def format_bytes(bytes_size: int, precision: int = 2) -> str:
        """Format bytes into human readable size"""
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if bytes_size < 1024.0:
                return f"{bytes_size:.{precision}f} {unit}"
            bytes_size /= 1024.0
        return f"{bytes_size:.{precision}f} PB"

    @staticmethod
    def format_speed(bytes_per_second: float) -> str:
        """Format speed (bytes/second)"""
        return f"{SizeFormatter.format_bytes(bytes_per_second)}/s"


# Quick access file type emojis
FILE = Emoji.DOCUMENT
